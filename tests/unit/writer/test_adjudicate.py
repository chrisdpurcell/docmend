"""Dangling-intent adjudication table (adr-0019; Plan B Task 7, CR-005).

One test per crash-state row of the design's adjudication table — each builds
the EXACT disk state a kill leaves after the corresponding mutation step —
plus the identity-substitution probes: a same-bytes replacement under a NEW
inode must fail the identity predicate and refuse as external-interference,
never be adopted or unlinked.
"""

import hashlib
import os
from pathlib import Path

import pytest
from tests.helpers.manifest2 import RUN_ID, record_doc

from docmend.writer import adjudicate as adjudicate_module
from docmend.writer.adjudicate import (
    Adjudication,
    adjudicate_dangling_intent,
    finish_remaining,
)
from docmend.writer.commit import CommitHooks
from docmend.writer.manifest import ManifestRecord

BEFORE = b"before bytes\n"
AFTER = b"after bytes\n"
CLOBBERED = b"clobbered target bytes\n"


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _ident(path: Path) -> dict[str, int]:
    st = os.lstat(path)
    return {"dev": st.st_dev, "ino": st.st_ino}


def _intent(
    *,
    operation: str,
    original: Path,
    target: Path,
    source_identity: dict[str, int] | None,
    expected_identity: dict[str, int] | None,
    target_identity: dict[str, int] | None = None,
    before: bytes = BEFORE,
    after: bytes | None = AFTER,
    overwritten: bytes | None = None,
    undoes: str | None = None,
) -> ManifestRecord:
    doc = record_doc(
        1,
        result="intent",
        operation=operation,
        original_path=str(original),
        target_path=str(target),
        before_sha256=_sha(before),
        after_sha256=_sha(after) if after is not None else None,
        source_identity=source_identity,
        expected_published_identity=expected_identity,
        target_identity=target_identity,
        overwritten_sha256=_sha(overwritten) if overwritten is not None else None,
    )
    if undoes is not None:
        doc["undoes_action_id"] = undoes
        doc["undoes_run_id"] = RUN_ID
    return ManifestRecord.model_validate(doc)


class TestApplyRows:
    def test_rewrite_never_happened(self, tmp_path: Path) -> None:
        path = tmp_path / "a.md"
        path.write_bytes(BEFORE)
        intent = _intent(
            operation="rewrite",
            original=path,
            target=path,
            source_identity=_ident(path),
            expected_identity={"dev": 1, "ino": 999},  # staged inode, gone with the kill
        )
        assert adjudicate_dangling_intent(intent).verdict == "never-happened"

    def test_rewrite_completed(self, tmp_path: Path) -> None:
        path = tmp_path / "a.md"
        path.write_bytes(AFTER)
        intent = _intent(
            operation="rewrite",
            original=path,
            target=path,
            source_identity={"dev": 1, "ino": 111},  # the replaced inode
            expected_identity=_ident(path),
        )
        assert adjudicate_dangling_intent(intent).verdict == "completed"

    def test_rewrite_same_bytes_different_inode__refused(self, tmp_path: Path) -> None:
        """The F4 identity probe: identical AFTER bytes under a NEW inode."""
        path = tmp_path / "a.md"
        path.write_bytes(AFTER)
        intent = _intent(
            operation="rewrite",
            original=path,
            target=path,
            source_identity={"dev": 1, "ino": 111},
            expected_identity={"dev": _ident(path)["dev"], "ino": _ident(path)["ino"] + 7},
        )
        verdict = adjudicate_dangling_intent(intent)
        assert verdict.verdict == "external-interference"

    def test_rename_noclobber_never_happened(self, tmp_path: Path) -> None:
        source = tmp_path / "a.txt"
        source.write_bytes(BEFORE)
        intent = _intent(
            operation="rename",
            original=source,
            target=tmp_path / "a.md",
            source_identity=_ident(source),
            expected_identity=_ident(source),
            after=BEFORE,
        )
        assert adjudicate_dangling_intent(intent).verdict == "never-happened"

    def test_rename_noclobber_both_names_one_inode__finish(self, tmp_path: Path) -> None:
        source = tmp_path / "a.txt"
        target = tmp_path / "a.md"
        source.write_bytes(BEFORE)
        os.link(source, target)  # the lossless link-then-unlink intermediate
        intent = _intent(
            operation="rename",
            original=source,
            target=target,
            source_identity=_ident(source),
            expected_identity=_ident(source),
            after=BEFORE,
        )
        verdict = adjudicate_dangling_intent(intent)
        assert verdict.verdict == "finish-remaining"
        finish_remaining(intent, root_resolved=tmp_path.resolve())
        assert not source.exists()
        assert target.read_bytes() == BEFORE

    def test_rename_noclobber_completed(self, tmp_path: Path) -> None:
        source = tmp_path / "a.txt"
        target = tmp_path / "a.md"
        target.write_bytes(BEFORE)
        intent = _intent(
            operation="rename",
            original=source,
            target=target,
            source_identity=_ident(target),  # the inode that moved
            expected_identity=_ident(target),
            after=BEFORE,
        )
        assert adjudicate_dangling_intent(intent).verdict == "completed"

    def test_rename_noclobber_both_names_different_inodes__refused(self, tmp_path: Path) -> None:
        """Identity probe on the both-names row: the target name holds a COPY
        (new inode), not the linked source inode — refuse, never unlink."""
        source = tmp_path / "a.txt"
        target = tmp_path / "a.md"
        source.write_bytes(BEFORE)
        target.write_bytes(BEFORE)  # same bytes, distinct inode
        intent = _intent(
            operation="rename",
            original=source,
            target=target,
            source_identity=_ident(source),
            expected_identity=_ident(source),
            after=BEFORE,
        )
        verdict = adjudicate_dangling_intent(intent)
        assert verdict.verdict == "external-interference"
        assert source.exists() and target.exists()  # nothing destroyed

    def test_rename_overwrite_never_happened(self, tmp_path: Path) -> None:
        source = tmp_path / "a.txt"
        target = tmp_path / "a.md"
        source.write_bytes(BEFORE)
        target.write_bytes(CLOBBERED)
        intent = _intent(
            operation="rename",
            original=source,
            target=target,
            source_identity=_ident(source),
            expected_identity=_ident(source),
            target_identity=_ident(target),
            after=BEFORE,
            overwritten=CLOBBERED,
        )
        assert adjudicate_dangling_intent(intent).verdict == "never-happened"

    def test_rename_overwrite_completed(self, tmp_path: Path) -> None:
        target = tmp_path / "a.md"
        target.write_bytes(BEFORE)
        intent = _intent(
            operation="rename",
            original=tmp_path / "a.txt",
            target=target,
            source_identity=_ident(target),
            expected_identity=_ident(target),
            target_identity={"dev": 1, "ino": 222},  # the clobbered inode, gone
            after=BEFORE,
            overwritten=CLOBBERED,
        )
        assert adjudicate_dangling_intent(intent).verdict == "completed"

    def test_rnr_never_happened(self, tmp_path: Path) -> None:
        source = tmp_path / "a.txt"
        source.write_bytes(BEFORE)
        intent = _intent(
            operation="rename_and_rewrite",
            original=source,
            target=tmp_path / "a.md",
            source_identity=_ident(source),
            expected_identity={"dev": 1, "ino": 999},
        )
        assert adjudicate_dangling_intent(intent).verdict == "never-happened"

    def test_rnr_published_source_present__finish(self, tmp_path: Path) -> None:
        source = tmp_path / "a.txt"
        target = tmp_path / "a.md"
        source.write_bytes(BEFORE)
        target.write_bytes(AFTER)
        intent = _intent(
            operation="rename_and_rewrite",
            original=source,
            target=target,
            source_identity=_ident(source),
            expected_identity=_ident(target),
        )
        verdict = adjudicate_dangling_intent(intent)
        assert verdict.verdict == "finish-remaining"
        finish_remaining(intent, root_resolved=tmp_path.resolve())
        assert not source.exists()
        assert target.read_bytes() == AFTER

    def test_rnr_completed(self, tmp_path: Path) -> None:
        target = tmp_path / "a.md"
        target.write_bytes(AFTER)
        intent = _intent(
            operation="rename_and_rewrite",
            original=tmp_path / "a.txt",
            target=target,
            source_identity={"dev": 1, "ino": 111},
            expected_identity=_ident(target),
        )
        assert adjudicate_dangling_intent(intent).verdict == "completed"

    def test_rnr_published_output_replaced_same_bytes__refused(self, tmp_path: Path) -> None:
        """Identity probe post-publish: the published output was replaced by a
        different inode carrying identical bytes — refuse; never unlink the
        still-present source."""
        source = tmp_path / "a.txt"
        target = tmp_path / "a.md"
        source.write_bytes(BEFORE)
        target.write_bytes(AFTER)
        intent = _intent(
            operation="rename_and_rewrite",
            original=source,
            target=target,
            source_identity=_ident(source),
            expected_identity={"dev": _ident(target)["dev"], "ino": _ident(target)["ino"] + 7},
        )
        verdict = adjudicate_dangling_intent(intent)
        assert verdict.verdict == "external-interference"
        assert source.exists()

    def test_source_replaced_same_bytes_pre_publish__refused(self, tmp_path: Path) -> None:
        """Identity probe pre-publish: the SOURCE was replaced with identical
        bytes under a new inode after the intent — refuse."""
        source = tmp_path / "a.txt"
        source.write_bytes(BEFORE)
        recorded = {"dev": _ident(source)["dev"], "ino": _ident(source)["ino"] + 7}
        intent = _intent(
            operation="rename_and_rewrite",
            original=source,
            target=tmp_path / "a.md",
            source_identity=recorded,
            expected_identity={"dev": 1, "ino": 999},
        )
        assert adjudicate_dangling_intent(intent).verdict == "external-interference"

    def test_symlink_at_recorded_name__refused(self, tmp_path: Path) -> None:
        """lstat never follows: a symlink interposed at the recorded name
        fails every predicate even if its referent holds matching bytes."""
        real = tmp_path / "real.md"
        real.write_bytes(AFTER)
        path = tmp_path / "a.md"
        path.symlink_to(real)
        intent = _intent(
            operation="rewrite",
            original=path,
            target=path,
            source_identity={"dev": 1, "ino": 111},
            expected_identity=_ident(real),
        )
        assert adjudicate_dangling_intent(intent).verdict == "external-interference"


def _inverse_intent(
    *,
    operation: str,
    applied_name: Path,
    original_name: Path,
    source_identity: dict[str, int] | None,
    expected_identity: dict[str, int] | None,
    applied_bytes: bytes = AFTER,
    original_bytes: bytes = BEFORE,
) -> ManifestRecord:
    """An inverse intent: original_path = the LIVE applied name; target_path =
    the reinstated original; before = applied bytes; after = original bytes."""
    return _intent(
        operation=operation,
        original=applied_name,
        target=original_name,
        source_identity=source_identity,
        expected_identity=expected_identity,
        before=applied_bytes,
        after=original_bytes,
        undoes=f"{RUN_ID}/a1",
    )


def _undone_apply(
    tmp_path: Path, *, overwritten: bytes | None = None, backup: bytes | None = None
) -> ManifestRecord:
    doc = record_doc(
        1,
        result="applied",
        overwritten_sha256=_sha(overwritten) if overwritten is not None else None,
        overwritten_backup_path=None,
    )
    if backup is not None:
        backup_path = tmp_path / "clobbered.bin"
        backup_path.write_bytes(backup)
        doc["overwritten_backup_path"] = str(backup_path)
    return ManifestRecord.model_validate(doc)


class TestRestoreInverseRows:
    def test_inverse_rewrite_never_happened(self, tmp_path: Path) -> None:
        path = tmp_path / "a.md"
        path.write_bytes(AFTER)  # still the applied bytes
        intent = _inverse_intent(
            operation="rewrite",
            applied_name=path,
            original_name=path,
            source_identity=_ident(path),
            expected_identity={"dev": 1, "ino": 999},
        )
        assert adjudicate_dangling_intent(intent).verdict == "never-happened"

    def test_inverse_rewrite_completed(self, tmp_path: Path) -> None:
        path = tmp_path / "a.md"
        path.write_bytes(BEFORE)  # reinstated original bytes
        intent = _inverse_intent(
            operation="rewrite",
            applied_name=path,
            original_name=path,
            source_identity={"dev": 1, "ino": 111},
            expected_identity=_ident(path),
        )
        assert adjudicate_dangling_intent(intent).verdict == "completed"

    def test_inverse_rename_never_happened(self, tmp_path: Path) -> None:
        applied = tmp_path / "a.md"
        applied.write_bytes(AFTER)
        intent = _inverse_intent(
            operation="rename",
            applied_name=applied,
            original_name=tmp_path / "a.txt",
            source_identity=_ident(applied),
            expected_identity=_ident(applied),
            original_bytes=AFTER,  # pure rename: bytes never changed
            applied_bytes=AFTER,
        )
        assert adjudicate_dangling_intent(intent).verdict == "never-happened"

    def test_inverse_rename_both_names__finish(self, tmp_path: Path) -> None:
        applied = tmp_path / "a.md"
        original = tmp_path / "a.txt"
        applied.write_bytes(AFTER)
        os.link(applied, original)
        intent = _inverse_intent(
            operation="rename",
            applied_name=applied,
            original_name=original,
            source_identity=_ident(applied),
            expected_identity=_ident(applied),
            original_bytes=AFTER,
            applied_bytes=AFTER,
        )
        verdict = adjudicate_dangling_intent(intent)
        assert verdict.verdict == "finish-remaining"
        finish_remaining(intent, root_resolved=tmp_path.resolve())
        assert not applied.exists()
        assert original.read_bytes() == AFTER

    def test_inverse_rename_completed(self, tmp_path: Path) -> None:
        original = tmp_path / "a.txt"
        original.write_bytes(AFTER)
        intent = _inverse_intent(
            operation="rename",
            applied_name=tmp_path / "a.md",
            original_name=original,
            source_identity=_ident(original),
            expected_identity=_ident(original),
            original_bytes=AFTER,
            applied_bytes=AFTER,
        )
        assert adjudicate_dangling_intent(intent).verdict == "completed"

    def test_inverse_overwrite_rename_relinked__finish_rewrites_clobbered(
        self, tmp_path: Path
    ) -> None:
        applied = tmp_path / "a.md"
        original = tmp_path / "a.txt"
        applied.write_bytes(AFTER)
        os.link(applied, original)  # relink landed; target rewrite remains
        undone = _undone_apply(tmp_path, overwritten=CLOBBERED, backup=CLOBBERED)
        intent = _inverse_intent(
            operation="rename",
            applied_name=applied,
            original_name=original,
            source_identity=_ident(applied),
            expected_identity=_ident(applied),
            original_bytes=AFTER,
            applied_bytes=AFTER,
        )
        verdict = adjudicate_dangling_intent(intent, undone=undone)
        assert verdict.verdict == "finish-remaining"
        finish_remaining(intent, undone=undone, root_resolved=tmp_path.resolve())
        assert applied.read_bytes() == CLOBBERED
        assert original.read_bytes() == AFTER

    def test_inverse_overwrite_rename_completed(self, tmp_path: Path) -> None:
        applied = tmp_path / "a.md"
        original = tmp_path / "a.txt"
        applied.write_bytes(CLOBBERED)
        original.write_bytes(AFTER)
        undone = _undone_apply(tmp_path, overwritten=CLOBBERED)
        intent = _inverse_intent(
            operation="rename",
            applied_name=applied,
            original_name=original,
            source_identity={"dev": 1, "ino": 111},
            expected_identity=_ident(original),
            original_bytes=AFTER,
            applied_bytes=AFTER,
        )
        assert adjudicate_dangling_intent(intent, undone=undone).verdict == "completed"

    def test_inverse_rnr_never_happened(self, tmp_path: Path) -> None:
        applied = tmp_path / "a.md"
        applied.write_bytes(AFTER)
        intent = _inverse_intent(
            operation="rename_and_rewrite",
            applied_name=applied,
            original_name=tmp_path / "a.txt",
            source_identity=_ident(applied),
            expected_identity={"dev": 1, "ino": 999},
        )
        assert adjudicate_dangling_intent(intent).verdict == "never-happened"

    def test_inverse_rnr_reinstated__finish_unlinks_applied(self, tmp_path: Path) -> None:
        applied = tmp_path / "a.md"
        original = tmp_path / "a.txt"
        applied.write_bytes(AFTER)
        original.write_bytes(BEFORE)
        intent = _inverse_intent(
            operation="rename_and_rewrite",
            applied_name=applied,
            original_name=original,
            source_identity=_ident(applied),
            expected_identity=_ident(original),
        )
        verdict = adjudicate_dangling_intent(intent)
        assert verdict.verdict == "finish-remaining"
        finish_remaining(intent, root_resolved=tmp_path.resolve())
        assert not applied.exists()
        assert original.read_bytes() == BEFORE

    def test_inverse_rnr_completed(self, tmp_path: Path) -> None:
        original = tmp_path / "a.txt"
        original.write_bytes(BEFORE)
        intent = _inverse_intent(
            operation="rename_and_rewrite",
            applied_name=tmp_path / "a.md",
            original_name=original,
            source_identity={"dev": 1, "ino": 111},
            expected_identity=_ident(original),
        )
        assert adjudicate_dangling_intent(intent).verdict == "completed"

    def test_inverse_reinstated_original_replaced_same_bytes__refused(self, tmp_path: Path) -> None:
        """Restore identity probe: the reinstated original was replaced by a
        new inode with identical bytes — refuse; never unlink the applied
        name it was supposed to clean up."""
        applied = tmp_path / "a.md"
        original = tmp_path / "a.txt"
        applied.write_bytes(AFTER)
        original.write_bytes(BEFORE)
        intent = _inverse_intent(
            operation="rename_and_rewrite",
            applied_name=applied,
            original_name=original,
            source_identity=_ident(applied),
            expected_identity={
                "dev": _ident(original)["dev"],
                "ino": _ident(original)["ino"] + 7,
            },
        )
        verdict = adjudicate_dangling_intent(intent)
        assert verdict.verdict == "external-interference"
        assert applied.exists()


class TestVerifiedFinish:
    def test_finish_refuses_when_object_changes_after_adjudication(self, tmp_path: Path) -> None:
        source = tmp_path / "a.txt"
        target = tmp_path / "a.md"
        source.write_bytes(BEFORE)
        os.link(source, target)
        intent = _intent(
            operation="rename",
            original=source,
            target=target,
            source_identity=_ident(source),
            expected_identity=_ident(source),
            after=BEFORE,
        )
        assert isinstance(adjudicate_dangling_intent(intent), Adjudication)
        # The object mutates between adjudication and finish:
        source.unlink()
        source.write_bytes(BEFORE)  # same bytes, NEW inode
        from docmend.writer.atomic import WriteError

        with pytest.raises(WriteError, match="refusing"):
            finish_remaining(intent, root_resolved=tmp_path.resolve())


class TestFinishRemainingBoundary:
    def test_observe_nonregular__unobservable_without_blocking(self, tmp_path: Path) -> None:
        fifo = tmp_path / "pipe"
        os.mkfifo(fifo)
        observed = adjudicate_module._observe(fifo)  # pyright: ignore[reportPrivateUsage]
        assert observed.state == "unobservable"

    def test_observe_descriptor_read_error__unobservable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "a.md"
        path.write_bytes(AFTER)

        def fail_fdopen(fd: int, mode: str) -> object:
            raise OSError(5, "I/O error")

        monkeypatch.setattr(adjudicate_module.os, "fdopen", fail_fdopen)
        observed = adjudicate_module._observe(path)  # pyright: ignore[reportPrivateUsage]
        assert observed.state == "unobservable"

    def test_finish_unlink__parent_interposed__refused(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        sub = root / "sub"
        sub.mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        source = sub / "a.txt"
        target = sub / "a.md"
        source.write_bytes(BEFORE)
        os.link(source, target)
        intent = _intent(
            operation="rename",
            original=source,
            target=target,
            source_identity=_ident(source),
            expected_identity=_ident(target),
            after=BEFORE,
        )
        assert adjudicate_dangling_intent(intent).verdict == "finish-remaining"
        sub.rename(outside / "sub")
        sub.symlink_to(outside / "sub")

        from docmend.writer.atomic import WriteError

        with pytest.raises(WriteError):
            finish_remaining(intent, root_resolved=root.resolve())
        assert (outside / "sub" / "a.txt").read_bytes() == BEFORE

    def test_finish_rewrite_from_backup__target_swapped_in_stage_window__refused(
        self, tmp_path: Path
    ) -> None:
        applied = tmp_path / "a.md"
        original = tmp_path / "a.txt"
        applied.write_bytes(AFTER)
        os.link(applied, original)
        undone = _undone_apply(tmp_path, overwritten=CLOBBERED, backup=CLOBBERED)
        intent = _inverse_intent(
            operation="rename",
            applied_name=applied,
            original_name=original,
            source_identity=_ident(applied),
            expected_identity=_ident(original),
            original_bytes=AFTER,
            applied_bytes=AFTER,
        )

        def swap(step: str, path: Path) -> None:
            if step == "replace-target":
                applied.unlink()
                applied.write_bytes(b"interloper")

        from docmend.writer.atomic import WriteError

        with pytest.raises(WriteError):
            finish_remaining(
                intent,
                undone=undone,
                root_resolved=tmp_path.resolve(),
                hooks=CommitHooks(swap),
            )
        assert applied.read_bytes() == b"interloper"

    def test_finish_rewrite_from_backup__preserves_target_mode(self, tmp_path: Path) -> None:
        applied = tmp_path / "a.md"
        original = tmp_path / "a.txt"
        applied.write_bytes(AFTER)
        applied.chmod(0o640)
        os.link(applied, original)
        undone = _undone_apply(tmp_path, overwritten=CLOBBERED, backup=CLOBBERED)
        intent = _inverse_intent(
            operation="rename",
            applied_name=applied,
            original_name=original,
            source_identity=_ident(applied),
            expected_identity=_ident(original),
            original_bytes=AFTER,
            applied_bytes=AFTER,
        )

        finish_remaining(intent, undone=undone, root_resolved=tmp_path.resolve())

        assert applied.read_bytes() == CLOBBERED
        assert os.lstat(applied).st_mode & 0o7777 == 0o640

    def test_finish_rewrite_mode_is_bound_to_verified_descriptor(self, tmp_path: Path) -> None:
        applied = tmp_path / "a.md"
        original = tmp_path / "a.txt"
        applied.write_bytes(AFTER)
        applied.chmod(0o640)
        os.link(applied, original)
        undone = _undone_apply(tmp_path, overwritten=CLOBBERED, backup=CLOBBERED)
        intent = _inverse_intent(
            operation="rename",
            applied_name=applied,
            original_name=original,
            source_identity=_ident(applied),
            expected_identity=_ident(original),
            original_bytes=AFTER,
            applied_bytes=AFTER,
        )

        def swap_mode_then_restore(step: str, path: Path) -> None:
            if step == "replace-target":
                held = tmp_path / "held.md"
                applied.rename(held)
                applied.write_bytes(b"interloper")
                applied.chmod(0o777)
                applied.unlink()
                held.rename(applied)

        finish_remaining(
            intent,
            undone=undone,
            root_resolved=tmp_path.resolve(),
            hooks=CommitHooks(swap_mode_then_restore),
        )

        assert applied.read_bytes() == CLOBBERED
        assert os.lstat(applied).st_mode & 0o7777 == 0o640

    def test_finish_unlink__survivor_swapped_since_adjudication__refused(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "a.txt"
        target = tmp_path / "a.md"
        source.write_bytes(BEFORE)
        os.link(source, target)
        intent = _intent(
            operation="rename",
            original=source,
            target=target,
            source_identity=_ident(source),
            expected_identity=_ident(target),
            after=BEFORE,
        )

        def swap(step: str, path: Path) -> None:
            if step == "unlink":
                target.unlink()
                target.write_bytes(BEFORE)

        from docmend.writer.atomic import WriteError

        with pytest.raises(WriteError):
            finish_remaining(
                intent,
                root_resolved=tmp_path.resolve(),
                hooks=CommitHooks(swap),
            )
        assert source.exists()

    def test_finish_unlink__environmental_error_wrapped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = tmp_path / "a.txt"
        target = tmp_path / "a.md"
        source.write_bytes(BEFORE)
        os.link(source, target)
        intent = _intent(
            operation="rename",
            original=source,
            target=target,
            source_identity=_ident(source),
            expected_identity=_ident(target),
            after=BEFORE,
        )
        real_unlink = Path.unlink

        def fail_source(self: Path, missing_ok: bool = False) -> None:
            if self == source:
                raise OSError(5, "I/O error")
            real_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", fail_source)
        from docmend.writer.atomic import WriteError

        with pytest.raises(WriteError, match="cannot finish"):
            finish_remaining(intent, root_resolved=tmp_path.resolve())

    def test_inverse_rnr_clobber_finish_rewrites_backup(self, tmp_path: Path) -> None:
        applied = tmp_path / "a.md"
        original = tmp_path / "a.txt"
        applied.write_bytes(AFTER)
        original.write_bytes(BEFORE)
        undone = _undone_apply(tmp_path, overwritten=CLOBBERED, backup=CLOBBERED)
        intent = _inverse_intent(
            operation="rename_and_rewrite",
            applied_name=applied,
            original_name=original,
            source_identity=_ident(applied),
            expected_identity=_ident(original),
        )

        finish_remaining(intent, undone=undone, root_resolved=tmp_path.resolve())

        assert applied.read_bytes() == CLOBBERED
        assert original.read_bytes() == BEFORE

    def test_observe__identity_and_bytes_from_one_descriptor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "a.md"
        path.write_bytes(AFTER)

        def forbid_path_read(self: Path) -> bytes:
            raise AssertionError("pathname read_bytes must not be used")

        monkeypatch.setattr(Path, "read_bytes", forbid_path_read)
        observed = adjudicate_module._observe(path)  # pyright: ignore[reportPrivateUsage]
        assert observed.sha256 == _sha(AFTER)

    @pytest.mark.parametrize("error", [PermissionError(13, "denied"), OSError(5, "I/O")])
    def test_observe_metadata_error__unobservable_never_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: OSError
    ) -> None:
        path = tmp_path / "a.md"
        path.write_bytes(AFTER)

        def fail_open(candidate: os.PathLike[str] | str, flags: int) -> int:
            if Path(candidate) == path:
                raise error
            return os.open(candidate, flags)

        monkeypatch.setattr(adjudicate_module.os, "open", fail_open)
        observed = adjudicate_module._observe(path)  # pyright: ignore[reportPrivateUsage]
        assert observed.state == "unobservable"
        assert observed.absent is False
        intent = _intent(
            operation="rewrite",
            original=path,
            target=path,
            source_identity=_ident(path),
            expected_identity=_ident(path),
        )
        assert adjudicate_dangling_intent(intent).verdict == "external-interference"


class TestRefusalArms:
    """The external-interference catch-alls and error paths of each row."""

    def test_overwrite_rename_both_names_absent__refused(self, tmp_path: Path) -> None:
        intent = _intent(
            operation="rename",
            original=tmp_path / "a.txt",
            target=tmp_path / "a.md",
            source_identity={"dev": 1, "ino": 111},
            expected_identity={"dev": 1, "ino": 111},
            after=BEFORE,
            overwritten=CLOBBERED,
        )
        assert adjudicate_dangling_intent(intent).verdict == "external-interference"

    def test_overwrite_rename_unrecognized_state__refused(self, tmp_path: Path) -> None:
        source = tmp_path / "a.txt"
        source.write_bytes(b"unrelated bytes\n")
        intent = _intent(
            operation="rename",
            original=source,
            target=tmp_path / "a.md",
            source_identity=_ident(source),
            expected_identity=_ident(source),
            after=BEFORE,
            overwritten=CLOBBERED,
        )
        assert adjudicate_dangling_intent(intent).verdict == "external-interference"

    def test_overwrite_rename_null_target_identity__never_happened(self, tmp_path: Path) -> None:
        """A recorded overwrite whose intent carries no target identity (the
        pre-Plan-C capture gap) still matches on bytes alone for the target."""
        source = tmp_path / "a.txt"
        target = tmp_path / "a.md"
        source.write_bytes(BEFORE)
        target.write_bytes(CLOBBERED)
        intent = _intent(
            operation="rename",
            original=source,
            target=target,
            source_identity=_ident(source),
            expected_identity=_ident(source),
            target_identity=None,
            after=BEFORE,
            overwritten=CLOBBERED,
        )
        assert adjudicate_dangling_intent(intent).verdict == "never-happened"

    def test_inverse_rewrite_unrecognized__refused(self, tmp_path: Path) -> None:
        path = tmp_path / "a.md"
        path.write_bytes(b"unrelated bytes\n")
        intent = _inverse_intent(
            operation="rewrite",
            applied_name=path,
            original_name=path,
            source_identity=_ident(path),
            expected_identity=_ident(path),
        )
        assert adjudicate_dangling_intent(intent).verdict == "external-interference"

    def test_inverse_rename_unrecognized__refused(self, tmp_path: Path) -> None:
        intent = _inverse_intent(
            operation="rename",
            applied_name=tmp_path / "a.md",
            original_name=tmp_path / "a.txt",
            source_identity={"dev": 1, "ino": 111},
            expected_identity={"dev": 1, "ino": 111},
            original_bytes=AFTER,
            applied_bytes=AFTER,
        )
        assert adjudicate_dangling_intent(intent).verdict == "external-interference"

    def test_inverse_overwrite_rename_unrecognized__refused(self, tmp_path: Path) -> None:
        undone = _undone_apply(tmp_path, overwritten=CLOBBERED)
        intent = _inverse_intent(
            operation="rename",
            applied_name=tmp_path / "a.md",
            original_name=tmp_path / "a.txt",
            source_identity={"dev": 1, "ino": 111},
            expected_identity={"dev": 1, "ino": 111},
            original_bytes=AFTER,
            applied_bytes=AFTER,
        )
        assert adjudicate_dangling_intent(intent, undone=undone).verdict == "external-interference"

    def test_inverse_rnr_unrecognized__refused(self, tmp_path: Path) -> None:
        intent = _inverse_intent(
            operation="rename_and_rewrite",
            applied_name=tmp_path / "a.md",
            original_name=tmp_path / "a.txt",
            source_identity={"dev": 1, "ino": 111},
            expected_identity={"dev": 1, "ino": 999},
        )
        assert adjudicate_dangling_intent(intent).verdict == "external-interference"


class TestFinishErrorPaths:
    def test_finish_rewrite_from_backup_missing_reference__write_error(
        self, tmp_path: Path
    ) -> None:
        """An overwrite-rename inverse whose apply run declared EXTERNAL
        preservation: docmend holds no clobbered bytes — finish must refuse."""
        undone = _undone_apply(tmp_path, overwritten=CLOBBERED)  # no backup file
        intent = _inverse_intent(
            operation="rename",
            applied_name=tmp_path / "a.md",
            original_name=tmp_path / "a.txt",
            source_identity={"dev": 1, "ino": 111},
            expected_identity={"dev": 1, "ino": 111},
        )
        from docmend.writer.atomic import WriteError

        with pytest.raises(WriteError, match="external"):
            finish_remaining(intent, undone=undone, root_resolved=tmp_path.resolve())

    def test_finish_rewrite_from_backup_hash_mismatch__write_error(self, tmp_path: Path) -> None:
        undone = _undone_apply(tmp_path, overwritten=CLOBBERED, backup=b"tampered bytes\n")
        intent = _inverse_intent(
            operation="rename",
            applied_name=tmp_path / "a.md",
            original_name=tmp_path / "a.txt",
            source_identity={"dev": 1, "ino": 111},
            expected_identity={"dev": 1, "ino": 111},
        )
        from docmend.writer.atomic import WriteError

        with pytest.raises(WriteError, match="mismatch"):
            finish_remaining(intent, undone=undone, root_resolved=tmp_path.resolve())

    def test_finish_rewrite_from_backup_unreadable__write_error(self, tmp_path: Path) -> None:
        undone = _undone_apply(tmp_path, overwritten=CLOBBERED, backup=CLOBBERED)
        assert undone.overwritten_backup_path is not None
        Path(undone.overwritten_backup_path).unlink()
        intent = _inverse_intent(
            operation="rename",
            applied_name=tmp_path / "a.md",
            original_name=tmp_path / "a.txt",
            source_identity={"dev": 1, "ino": 111},
            expected_identity={"dev": 1, "ino": 111},
        )
        from docmend.writer.atomic import WriteError

        with pytest.raises(WriteError, match="unreadable"):
            finish_remaining(intent, undone=undone, root_resolved=tmp_path.resolve())
