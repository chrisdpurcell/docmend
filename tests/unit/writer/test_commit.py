"""Commit-boundary primitives (adr-0020): descriptor-bound identity capture
and the at-commit lstat re-check. All fixtures are synthetic (conventions #6)."""

import inspect
import json
import os
import threading
from pathlib import Path
from typing import cast

import pytest
from allpairspy import AllPairs  # pyright: ignore[reportMissingTypeStubs]
from pydantic import ValidationError
from tests.helpers import replace_with_new_inode
from tests.helpers.manifest2 import header_doc, record_doc, write_set
from tests.test_plan_artifact import sample_plan

import docmend.writer.commit as commit_module
from docmend import artifacts, lock
from docmend.lineage import ObjectIdentity
from docmend.writer.atomic import WriteError
from docmend.writer.commit import (
    NO_HOOKS,
    BoundFile,
    CommitHooks,
    DestinationRefusedError,
    InterferenceError,
    WriteSafetyContext,
    _rollback_link,  # pyright: ignore[reportPrivateUsage] - direct boundary regression seam.
    apply_write_context,
    bind_file,
    check_bound,
    check_destination,
    guarded_rename_no_clobber,
    guarded_replace,
    restore_write_context,
)


class TestWriteSafetyContext:
    @staticmethod
    def _plan_path(tmp_path: Path) -> tuple[Path, Path]:
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        plan = sample_plan().model_copy(update={"source_root": str(corpus)})
        plan_path = tmp_path / "plan.json"
        artifacts.write_plan(plan, plan_path)
        return corpus, plan_path

    def test_direct_construction__typeerror(self) -> None:
        with pytest.raises(TypeError, match="factory-sealed"):
            WriteSafetyContext()

    def test_apply_capability__attested_private_and_scope_bound(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        corpus, plan_path = self._plan_path(tmp_path)
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        manifest_path = tmp_path / "manifest.jsonl"
        report_path = tmp_path / "report.json"
        with apply_write_context(
            plan_path,
            run_id="run_20260711T000000Z_000011",
            manifest_path=manifest_path,
            report_path=report_path,
            preserved_by="external",
        ) as safety:
            safety.confirm_apply(run_id="run_20260711T000000Z_000011", manifest_path=manifest_path)
            safety.confirm_report(report_path)
            with pytest.raises(RuntimeError, match="attestation"):
                safety.confirm_apply(
                    run_id="run_20260711T000000Z_000012", manifest_path=manifest_path
                )
            with pytest.raises(AttributeError):
                _ = safety.plan  # type: ignore[attr-defined]
            first_plan, first_config, _, _, chain, _ = safety._consume_apply_state()  # pyright: ignore[reportPrivateUsage]
            first_plan.actions[0].target_path = "elsewhere.md"
            first_config.rename.on_collision = "overwrite"
            second_plan, second_config, _, _, second_chain, _ = safety._consume_apply_state()  # pyright: ignore[reportPrivateUsage]
            assert second_plan.actions[0].target_path == "legacy.md"
            assert second_plan.source_root == str(corpus.resolve())
            assert second_config.rename.on_collision == "skip"
            assert chain.sets == second_chain.sets == ()
            with pytest.raises(lock.LockHeldError):
                lock.acquire(corpus, run_id="probe", command="apply")
            leaked = safety
        with pytest.raises(RuntimeError, match="outside its factory scope"):
            leaked.confirm_report(report_path)

    def test_plan_1_x__rejected_before_gate_lock_or_artifacts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        corpus, plan_path = self._plan_path(tmp_path)
        victim = corpus / "legacy.txt"
        victim.write_bytes(b"legacy body\r\n")
        document = json.loads(plan_path.read_text(encoding="utf-8"))
        document["schema_version"] = "1.2"
        document["config"]["parallel"] = {
            "enabled": False,
            "model": "process",
            "workers": "auto",
            "start_method": "forkserver",
            "chunksize": "auto",
            "maxtasksperchild": None,
        }
        plan_path.write_text(json.dumps(document), encoding="utf-8")
        manifest_path = tmp_path / "manifest.jsonl"
        report_path = tmp_path / "report.json"

        def boundary_should_not_run(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("legacy plan reached a mutation safety boundary")

        monkeypatch.setattr(commit_module.lock, "acquire", boundary_should_not_run)
        monkeypatch.setattr(commit_module, "evaluate_gate", boundary_should_not_run)
        with (
            pytest.raises(artifacts.ArtifactError, match=r"plan schema 1\.2.*regenerate.*v2"),
            apply_write_context(
                plan_path,
                run_id="run_20260711T000000Z_000019",
                manifest_path=manifest_path,
                report_path=report_path,
                preserved_by="external",
            ),
        ):
            raise AssertionError("legacy plan produced a write capability")

        assert victim.read_bytes() == b"legacy body\r\n"
        assert not manifest_path.exists()
        assert not report_path.exists()

    def test_apply_factory__in_corpus_destination_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        corpus, plan_path = self._plan_path(tmp_path)
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        with (
            pytest.raises(DestinationRefusedError, match="inside the corpus"),
            apply_write_context(
                plan_path,
                run_id="run_20260711T000000Z_000014",
                manifest_path=corpus / "manifest.jsonl",
                report_path=tmp_path / "report.json",
                preserved_by="external",
            ),
        ):
            raise AssertionError("destination guard must refuse before yield")

    def test_factories_own_authority_parameters(self) -> None:
        apply_parameters = inspect.signature(apply_write_context).parameters
        restore_parameters = inspect.signature(restore_write_context).parameters
        for forbidden in ("config", "options", "source_root", "lock_state_dir", "artifact_root"):
            assert forbidden not in apply_parameters
        for forbidden in ("source_root", "lock_state_dir", "artifact_root", "exclude"):
            assert forbidden not in restore_parameters

    def test_restore_chain__factory_loaded_and_deep_frozen(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        manifest = write_set(
            tmp_path / "apply.jsonl",
            header_doc(source_root=str(corpus)),
            record_doc(
                1,
                result="intent",
                original_path=str(corpus / "legacy.txt"),
                target_path=str(corpus / "legacy.txt"),
            ),
            record_doc(
                1,
                seq=2,
                original_path=str(corpus / "legacy.txt"),
                target_path=str(corpus / "legacy.txt"),
            ),
        )
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        manifest_out = tmp_path / "restore.jsonl"
        with restore_write_context(
            [manifest],
            run_id="run_20260711T000000Z_000013",
            manifest_out=manifest_out,
        ) as safety:
            safety.confirm_restore(run_id="run_20260711T000000Z_000013", manifest_out=manifest_out)
            assert isinstance(safety.chain.sets, tuple)
            assert isinstance(safety.chain.sets[0].records, tuple)
            with pytest.raises(ValidationError):
                safety.chain.sets[0].header.source_root = "/elsewhere"  # type: ignore[misc]
            with pytest.raises(RuntimeError, match="attestation"):
                safety._consume_apply_state()  # pyright: ignore[reportPrivateUsage]


class TestBindFile:
    def test_regular_file__bytes_identity_mode(self, tmp_path: Path) -> None:
        file = tmp_path / "doc.txt"
        file.write_bytes(b"hello\n")
        file.chmod(0o640)
        bound = bind_file(file)
        stat_result = os.lstat(file)
        assert bound == BoundFile(
            path=file,
            data=b"hello\n",
            identity=ObjectIdentity(dev=stat_result.st_dev, ino=stat_result.st_ino),
            mode=stat_result.st_mode,
        )

    def test_symlink__interference_not_followed(self, tmp_path: Path) -> None:
        real = tmp_path / "real.txt"
        real.write_bytes(b"payload")
        link = tmp_path / "doc.txt"
        link.symlink_to(real)
        with pytest.raises(InterferenceError, match="symlink"):
            bind_file(link)

    def test_missing__oserror_for_unreadable_mapping(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            bind_file(tmp_path / "absent.txt")

    def test_fifo__interference_without_blocking(self, tmp_path: Path) -> None:
        """Refuse a FIFO without waiting for a writer to open its other end."""
        fifo = tmp_path / "doc.txt"
        os.mkfifo(fifo)
        result: list[BaseException | None] = []

        def attempt() -> None:
            try:
                bind_file(fifo)
                result.append(None)
            except BaseException as exc:
                result.append(exc)

        worker = threading.Thread(target=attempt, daemon=True)
        worker.start()
        worker.join(timeout=2.0)
        assert not worker.is_alive(), "bind_file blocked on a FIFO"
        assert isinstance(result[0], InterferenceError)
        assert "regular" in str(result[0])


class TestCheckBound:
    def test_unchanged__passes(self, tmp_path: Path) -> None:
        file = tmp_path / "doc.txt"
        file.write_bytes(b"x")
        check_bound(file, bind_file(file).identity, root_resolved=tmp_path.resolve())

    def test_missing__interference(self, tmp_path: Path) -> None:
        file = tmp_path / "doc.txt"
        file.write_bytes(b"x")
        identity = bind_file(file).identity
        file.unlink()
        with pytest.raises(InterferenceError, match="vanished"):
            check_bound(file, identity, root_resolved=tmp_path.resolve())

    def test_replaced_same_bytes_different_inode__interference(self, tmp_path: Path) -> None:
        file = tmp_path / "doc.txt"
        file.write_bytes(b"x")
        identity = bind_file(file).identity
        replace_with_new_inode(file, b"x")
        with pytest.raises(InterferenceError, match="changed before commit"):
            check_bound(file, identity, root_resolved=tmp_path.resolve())

    def test_replaced_by_symlink_to_original__interference(self, tmp_path: Path) -> None:
        file = tmp_path / "doc.txt"
        file.write_bytes(b"x")
        identity = bind_file(file).identity
        moved = tmp_path / "moved.txt"
        file.rename(moved)
        file.symlink_to(moved)
        with pytest.raises(InterferenceError, match="symlink"):
            check_bound(file, identity, root_resolved=tmp_path.resolve())

    def test_parent_swapped_for_symlink__interference_even_with_leaf_match(
        self, tmp_path: Path
    ) -> None:
        # O_NOFOLLOW protects only the final component. Full containment must
        # also reject a parent redirected outside the authorized corpus.
        root = tmp_path / "root"
        (root / "sub").mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        file = root / "sub" / "doc.txt"
        file.write_bytes(b"x")
        identity = bind_file(file).identity
        (root / "sub").rename(outside / "sub")
        (root / "sub").symlink_to(outside / "sub")
        with pytest.raises(InterferenceError, match="resolves"):
            check_bound(file, identity, root_resolved=root.resolve())

    @pytest.mark.parametrize(
        ("mutate", "expected"),
        [
            pytest.param(mutation, expected, id=f"{mutation}-{expected}")
            for mutation, expected in cast(
                list[tuple[str, str]],
                list(
                    AllPairs(
                        [
                            ["unlink", "swap-inode", "symlink", "none"],
                            ["vanished", "changed", "symlink", "ok"],
                        ]
                    )
                ),
            )
            if {
                "unlink": "vanished",
                "swap-inode": "changed",
                "symlink": "symlink",
                "none": "ok",
            }[mutation]
            == expected
        ],
    )
    def test_predicate_matrix(self, tmp_path: Path, mutate: str, expected: str) -> None:
        file = tmp_path / "doc.txt"
        file.write_bytes(b"x")
        identity = bind_file(file).identity
        if mutate == "unlink":
            file.unlink()
        elif mutate == "swap-inode":
            replace_with_new_inode(file, b"x")
        elif mutate == "symlink":
            other = tmp_path / "other.txt"
            other.write_bytes(b"x")
            file.unlink()
            file.symlink_to(other)
        if expected == "ok":
            check_bound(file, identity, root_resolved=tmp_path.resolve())
        else:
            with pytest.raises(InterferenceError):
                check_bound(file, identity, root_resolved=tmp_path.resolve())


class TestCheckDestination:
    def test_inside_root__passes(self, tmp_path: Path) -> None:
        check_destination(tmp_path / "sub" / "new.md", root_resolved=tmp_path.resolve())

    def test_parent_symlinked_outside__interference(self, tmp_path: Path) -> None:
        """Reject an absent-name publish whose parent now escapes the root."""
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (root / "sub").symlink_to(outside)
        with pytest.raises(InterferenceError, match="resolves"):
            check_destination(root / "sub" / "new.md", root_resolved=root.resolve())


class TestGuardedRenameNoClobber:
    @staticmethod
    def _bound(tmp_path: Path) -> tuple[Path, Path, ObjectIdentity]:
        source = tmp_path / "a.txt"
        source.write_bytes(b"content")
        return source, tmp_path / "a.md", bind_file(source).identity

    def test_happy_path__renames(self, tmp_path: Path) -> None:
        source, target, identity = self._bound(tmp_path)
        guarded_rename_no_clobber(
            source, target, identity, root_resolved=tmp_path.resolve(), hooks=NO_HOOKS
        )
        assert not source.exists()
        assert target.read_bytes() == b"content"

    def test_target_appears_before_link__fileexists_propagates(self, tmp_path: Path) -> None:
        source, target, identity = self._bound(tmp_path)

        def occupy_target(step: str, path: Path) -> None:
            if step == "publish":
                target.write_bytes(b"intruder")

        hooks = CommitHooks(before_step=occupy_target)
        with pytest.raises(FileExistsError):
            guarded_rename_no_clobber(
                source, target, identity, root_resolved=tmp_path.resolve(), hooks=hooks
            )
        assert source.read_bytes() == b"content"
        assert target.read_bytes() == b"intruder"

    def test_source_swapped_before_link__interference_nothing_mutated(self, tmp_path: Path) -> None:
        source, target, identity = self._bound(tmp_path)

        def swap(step: str, path: Path) -> None:
            if step == "publish":
                replace_with_new_inode(source, b"content")

        with pytest.raises(InterferenceError) as exc_info:
            guarded_rename_no_clobber(
                source,
                target,
                identity,
                root_resolved=tmp_path.resolve(),
                hooks=CommitHooks(swap),
            )
        assert exc_info.value.intermediate is False
        assert not target.exists()

    def test_destination_parent_symlinked_outside_before_link__interference(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "root"
        (root / "sub").mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        source = root / "a.txt"
        source.write_bytes(b"content")
        identity = bind_file(source).identity
        target = root / "sub" / "a.md"

        def interpose(step: str, path: Path) -> None:
            if step == "publish":
                (root / "sub").rmdir()
                (root / "sub").symlink_to(outside)

        with pytest.raises(InterferenceError):
            guarded_rename_no_clobber(
                source,
                target,
                identity,
                root_resolved=root.resolve(),
                hooks=CommitHooks(interpose),
            )
        assert source.read_bytes() == b"content"
        assert not (outside / "a.md").exists()

    def test_source_name_lost_in_unlink_window__link_retained_as_last_copy(
        self, tmp_path: Path
    ) -> None:
        source, target, identity = self._bound(tmp_path)

        def swap(step: str, path: Path) -> None:
            if step == "unlink":
                source.unlink()
                source.write_bytes(b"content")

        with pytest.raises(InterferenceError) as exc_info:
            guarded_rename_no_clobber(
                source,
                target,
                identity,
                root_resolved=tmp_path.resolve(),
                hooks=CommitHooks(swap),
            )
        assert exc_info.value.intermediate is True
        stat_result = os.lstat(target)
        assert (stat_result.st_dev, stat_result.st_ino) == (identity.dev, identity.ino)
        assert source.exists()

    def test_published_target_replaced_in_unlink_window__source_retained_proven(
        self, tmp_path: Path
    ) -> None:
        source, target, identity = self._bound(tmp_path)

        def swap(step: str, path: Path) -> None:
            if step == "unlink":
                target.unlink()
                target.write_bytes(b"interloper")

        with pytest.raises(InterferenceError) as exc_info:
            guarded_rename_no_clobber(
                source,
                target,
                identity,
                root_resolved=tmp_path.resolve(),
                hooks=CommitHooks(swap),
            )
        assert exc_info.value.intermediate is False
        assert source.read_bytes() == b"content"
        assert target.read_bytes() == b"interloper"

    def test_source_parent_interposed_after_link__intermediate_retained(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "root"
        sub = root / "sub"
        sub.mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        source = sub / "a.txt"
        source.write_bytes(b"content")
        target = sub / "a.md"
        identity = bind_file(source).identity

        def interpose(step: str, path: Path) -> None:
            if step == "unlink":
                sub.rename(outside / "sub")
                sub.symlink_to(outside / "sub")

        with pytest.raises(InterferenceError) as exc_info:
            guarded_rename_no_clobber(
                source,
                target,
                identity,
                root_resolved=root.resolve(),
                hooks=CommitHooks(interpose),
            )
        assert exc_info.value.intermediate is True
        assert (outside / "sub" / "a.txt").exists()
        assert (outside / "sub" / "a.md").exists()

    def test_target_parent_interposed_after_link__intermediate_retained(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "root"
        sub = root / "sub"
        sub.mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        source = root / "a.txt"
        source.write_bytes(b"content")
        target = sub / "a.md"
        identity = bind_file(source).identity

        def interpose(step: str, path: Path) -> None:
            if step == "unlink":
                sub.rename(outside / "sub")
                sub.symlink_to(outside / "sub")

        with pytest.raises(InterferenceError) as exc_info:
            guarded_rename_no_clobber(
                source,
                target,
                identity,
                root_resolved=root.resolve(),
                hooks=CommitHooks(interpose),
            )
        assert exc_info.value.intermediate is True
        assert source.exists()
        assert (outside / "sub" / "a.md").exists()

    def test_source_unlink_failure__proven_rollback_is_write_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source, target, identity = self._bound(tmp_path)
        real_unlink = Path.unlink

        def fail_source(self: Path, missing_ok: bool = False) -> None:
            if self == source:
                raise OSError(5, "I/O error")
            real_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", fail_source)
        with pytest.raises(WriteError):
            guarded_rename_no_clobber(
                source, target, identity, root_resolved=tmp_path.resolve(), hooks=NO_HOOKS
            )
        assert source.exists()
        assert not target.exists()

    def test_source_unlink_failure__unproven_rollback_is_intermediate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source, target, identity = self._bound(tmp_path)
        moved = tmp_path / "moved.txt"
        real_unlink = Path.unlink

        def fail_source(self: Path, missing_ok: bool = False) -> None:
            if self == source:
                raise OSError(5, "I/O error")
            real_unlink(self, missing_ok=missing_ok)

        def lose_survivor(step: str, path: Path) -> None:
            if step == "rollback-survivor":
                source.rename(moved)

        monkeypatch.setattr(Path, "unlink", fail_source)
        with pytest.raises(InterferenceError) as exc_info:
            guarded_rename_no_clobber(
                source,
                target,
                identity,
                root_resolved=tmp_path.resolve(),
                hooks=CommitHooks(lose_survivor),
            )
        assert exc_info.value.intermediate is True
        assert target.exists()
        assert moved.exists()


class TestGuardedReplace:
    def test_happy_path__replaces_with_mode(self, tmp_path: Path) -> None:
        file = tmp_path / "doc.md"
        file.write_bytes(b"old")
        file.chmod(0o640)
        bound = bind_file(file)
        guarded_replace(
            file,
            b"new",
            expected=bound.identity,
            mode=bound.mode,
            root_resolved=tmp_path.resolve(),
            hooks=NO_HOOKS,
        )
        assert file.read_bytes() == b"new"
        assert (os.lstat(file).st_mode & 0o7777) == 0o640

    def test_target_swapped_inside_stage_window__refused(self, tmp_path: Path) -> None:
        file = tmp_path / "doc.md"
        file.write_bytes(b"old")
        bound = bind_file(file)

        def swap(step: str, path: Path) -> None:
            if step == "replace-target":
                replace_with_new_inode(file, b"interloper")

        with pytest.raises(InterferenceError):
            guarded_replace(
                file,
                b"new",
                expected=bound.identity,
                mode=bound.mode,
                root_resolved=tmp_path.resolve(),
                hooks=CommitHooks(swap),
            )
        assert file.read_bytes() == b"interloper"
        assert not list(tmp_path.glob(".doc.md.*.docmend-tmp"))

    def test_survivor_replaced_inside_stage_window__refused(self, tmp_path: Path) -> None:
        target = tmp_path / "applied.md"
        target.write_bytes(b"applied")
        survivor = tmp_path / "original.txt"
        bound = bind_file(target)
        survivor.hardlink_to(target)

        def swap(step: str, path: Path) -> None:
            if step == "replace-target":
                survivor.unlink()
                survivor.write_bytes(b"interloper")

        with pytest.raises(InterferenceError):
            guarded_replace(
                target,
                b"clobbered",
                expected=bound.identity,
                mode=bound.mode,
                root_resolved=tmp_path.resolve(),
                hooks=CommitHooks(swap),
                survivor=(survivor, bound.identity),
            )
        assert target.read_bytes() == b"applied"
        assert survivor.read_bytes() == b"interloper"


class TestRollbackObservation:
    def test_absent_or_symlink_target__survivor_proves_pre_action_state(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "a.txt"
        source.write_bytes(b"content")
        identity = bind_file(source).identity
        target = tmp_path / "a.md"
        target.hardlink_to(source)
        target.unlink()
        assert _rollback_link(
            target,
            identity,
            survivor=(source, identity),
            root_resolved=tmp_path.resolve(),
            hooks=NO_HOOKS,
        )
        target.symlink_to(tmp_path / "elsewhere")
        assert _rollback_link(
            target,
            identity,
            survivor=(source, identity),
            root_resolved=tmp_path.resolve(),
            hooks=NO_HOOKS,
        )

    def test_interposed_target_parent__rollback_unproven(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        sub = root / "sub"
        sub.mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        source = root / "a.txt"
        source.write_bytes(b"content")
        identity = bind_file(source).identity
        target = sub / "a.md"
        target.hardlink_to(source)
        sub.rename(outside / "sub")
        sub.symlink_to(outside / "sub")
        assert not _rollback_link(
            target,
            identity,
            survivor=(source, identity),
            root_resolved=root.resolve(),
            hooks=NO_HOOKS,
        )

    def test_target_unlink_error__rollback_unproven(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = tmp_path / "a.txt"
        source.write_bytes(b"content")
        identity = bind_file(source).identity
        target = tmp_path / "a.md"
        target.hardlink_to(source)
        real_unlink = Path.unlink

        def fail_target(self: Path, missing_ok: bool = False) -> None:
            if self == target:
                raise OSError(5, "I/O error")
            real_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", fail_target)
        assert not _rollback_link(
            target,
            identity,
            survivor=(source, identity),
            root_resolved=tmp_path.resolve(),
            hooks=NO_HOOKS,
        )

    def test_unobservable_name__rollback_unproven(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = tmp_path / "a.txt"
        source.write_bytes(b"content")
        identity = bind_file(source).identity
        target = tmp_path / "a.md"
        target.hardlink_to(source)
        real_lstat = os.lstat

        def fail_target(
            path: os.PathLike[str] | str, *, dir_fd: int | None = None
        ) -> os.stat_result:
            if Path(path) == target:
                raise PermissionError(13, "Permission denied", target)
            return real_lstat(path, dir_fd=dir_fd)

        monkeypatch.setattr(os, "lstat", fail_target)
        assert not _rollback_link(
            target,
            identity,
            survivor=(source, identity),
            root_resolved=tmp_path.resolve(),
            hooks=NO_HOOKS,
        )

    def test_source_survivor_lost_before_rollback__published_link_retained(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "a.txt"
        source.write_bytes(b"content")
        identity = bind_file(source).identity
        target = tmp_path / "a.md"

        def lose_survivor(step: str, path: Path) -> None:
            if step == "rollback-survivor":
                source.unlink()

        target.hardlink_to(source)
        assert not _rollback_link(
            target,
            identity,
            survivor=(source, identity),
            root_resolved=tmp_path.resolve(),
            hooks=CommitHooks(lose_survivor),
        )
        assert target.exists()
