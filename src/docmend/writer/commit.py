"""Commit boundary for descriptor-bound object identity (adr-0020, DMR-06/07).

Every corpus mutation binds to one filesystem object, never merely a pathname.
`bind_file` reads bytes and captures identity through one non-following descriptor;
`check_bound` compares the pathname to that identity and re-resolves containment
immediately before mutation. `check_destination` is the absent-name counterpart,
and `guarded_replace` stages before it authorizes the final replacement.

Holding the original descriptor is insufficient: `fstat` continues to describe
the opened inode after its pathname is repointed. Re-hashing is also insufficient
because an interloper can contain identical bytes. `O_NONBLOCK` prevents a FIFO
from hanging the bind before its non-regular type can be rejected.

`InterferenceError.intermediate` records whether a mutation landed without a
provable rollback. Callers may close an intent as failed only when this is false;
otherwise adjudication must own the lossless intermediate. No rollback removes a
possibly last name of the bound original.

The lstat-to-mutation interval is the accepted POSIX residual window documented by
adr-0020. `CommitHooks` exists only to exercise those windows deterministically.
"""

import contextlib
import errno
import os
import stat
from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, final

from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern
from pydantic import ValidationError

from docmend import lock
from docmend.artifacts import (
    ARTIFACT_DIR_NAME,
    ArtifactError,
    guard_artifact_destination,
    read_plan_snapshot,
    read_report_snapshot,
)
from docmend.config import DocmendConfig
from docmend.lineage import ObjectIdentity, PriorAttempt
from docmend.plan import PLAN_SCHEMA_VERSION, ArtifactRef, Plan
from docmend.report import Report
from docmend.writer.atomic import (
    WriteError,
    abort_staged,
    fsync_dir,
    link_no_clobber,
    publish_staged,
    stage_bytes,
)
from docmend.writer.gate import ApplyOptions, GateRefusal, evaluate_gate
from docmend.writer.manifest import (
    ManifestChain,
    manifest_sha256,
    read_manifest_chain,
)


class InterferenceError(Exception):
    """Report that a pathname no longer names the validated object.

    `intermediate=True` means a mutation landed and the pre-action state could
    not be proven restored, so the caller must leave its journal intent open.
    """

    def __init__(self, message: str, *, intermediate: bool = False) -> None:
        super().__init__(message)
        self.intermediate = intermediate


@dataclass(frozen=True)
class BoundFile:
    """Hold bytes, identity, and mode captured through one descriptor."""

    path: Path
    data: bytes
    identity: ObjectIdentity
    mode: int


@dataclass(frozen=True)
class CommitHooks:
    """Inject deterministic actions immediately before commit-boundary checks."""

    before_step: Callable[[str, Path], None]


def _no_hook(step: str, path: Path) -> None:
    return None


NO_HOOKS: Final = CommitHooks(before_step=_no_hook)


def bind_file(path: Path) -> BoundFile:
    """Read a regular file and capture its identity through one descriptor.

    Symlinks and non-regular files raise `InterferenceError`. Missing or
    unreadable paths retain their `OSError` so callers can preserve the existing
    unreadable-input taxonomy.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            msg = f"{path}: symlink where a regular file was planned"
            raise InterferenceError(msg) from exc
        raise
    try:
        stat_result = os.fstat(fd)
        if not stat.S_ISREG(stat_result.st_mode):
            msg = f"{path}: not a regular file ({stat.filemode(stat_result.st_mode)})"
            raise InterferenceError(msg)
        with os.fdopen(fd, "rb") as file_handle:
            fd = -1
            data = file_handle.read()
    finally:
        if fd >= 0:
            os.close(fd)
    return BoundFile(
        path=path,
        data=data,
        identity=ObjectIdentity(dev=stat_result.st_dev, ino=stat_result.st_ino),
        mode=stat_result.st_mode,
    )


def check_bound(path: Path, identity: ObjectIdentity, *, root_resolved: Path) -> None:
    """Verify that `path` still names `identity` inside the authorized root."""
    try:
        stat_result = os.lstat(path)
    except OSError as exc:
        msg = f"{path}: vanished before commit ({exc.strerror or exc})"
        raise InterferenceError(msg) from exc
    if stat.S_ISLNK(stat_result.st_mode):
        msg = f"{path}: replaced by a symlink before commit"
        raise InterferenceError(msg)
    if stat_result.st_dev != identity.dev or stat_result.st_ino != identity.ino:
        msg = (
            f"{path}: object changed before commit "
            f"(now dev={stat_result.st_dev} ino={stat_result.st_ino}, "
            f"validated dev={identity.dev} ino={identity.ino})"
        )
        raise InterferenceError(msg)
    if not path.resolve().is_relative_to(root_resolved):
        msg = f"{path}: no longer resolves inside {root_resolved} (parent path interposed)"
        raise InterferenceError(msg)


def check_destination(path: Path, *, root_resolved: Path) -> None:
    """Verify that creating an absent name would remain inside the root."""
    if not (path.parent.resolve() / path.name).is_relative_to(root_resolved):
        msg = f"{path}: destination no longer resolves inside {root_resolved} (parent interposed)"
        raise InterferenceError(msg)


type NameObservation = ObjectIdentity | Literal["absent", "symlink", "unobservable"]


def _observe_name(path: Path) -> NameObservation:
    """Observe a pathname without treating permission or I/O errors as absence."""
    try:
        stat_result = os.lstat(path)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            return "absent"
        return "unobservable"
    if stat.S_ISLNK(stat_result.st_mode):
        return "symlink"
    return ObjectIdentity(dev=stat_result.st_dev, ino=stat_result.st_ino)


def _rollback_link(
    target: Path,
    expected: ObjectIdentity,
    *,
    survivor: tuple[Path, ObjectIdentity],
    root_resolved: Path,
    hooks: CommitHooks,
) -> bool:
    """Remove a published link only when the pre-action state is provable."""
    hooks.before_step("rollback", target)
    if not (target.parent.resolve() / target.name).is_relative_to(root_resolved):
        return False
    observed = _observe_name(target)
    if observed == "unobservable":
        return False
    survivor_path, survivor_identity = survivor
    hooks.before_step("rollback-survivor", survivor_path)
    try:
        # The survivor is the final proof before deletion. If it was lost while
        # the target was observed, the published link may be the last copy.
        check_bound(survivor_path, survivor_identity, root_resolved=root_resolved)
    except InterferenceError:
        return False
    if observed != expected:
        return True
    try:
        target.unlink()
    except OSError:
        return False
    return True


def guarded_rename_no_clobber(
    source: Path,
    target: Path,
    source_identity: ObjectIdentity,
    *,
    root_resolved: Path,
    hooks: CommitHooks,
) -> None:
    """Rename by checked link-and-unlink without clobbering the destination.

    `FileExistsError` remains the caller's collision-policy signal. Interference
    after the link retains every possibly last name and sets `intermediate` when
    the pre-action state is not provable.
    """
    hooks.before_step("publish", target)
    check_bound(source, source_identity, root_resolved=root_resolved)
    check_destination(target, root_resolved=root_resolved)
    link_no_clobber(source, target)

    hooks.before_step("unlink", source)
    if _observe_name(source) != source_identity:
        msg = (
            f"{source}: name lost the validated object after link; the published "
            f"link at {target} is retained as the surviving name"
        )
        raise InterferenceError(msg, intermediate=True)
    if not source.resolve().is_relative_to(root_resolved):
        msg = f"{source}: no longer resolves inside {root_resolved} after link"
        raise InterferenceError(msg, intermediate=True)
    if _observe_name(target) != source_identity:
        msg = f"{target}: published name replaced before the source unlink; source retained"
        raise InterferenceError(msg)
    if not target.resolve().is_relative_to(root_resolved):
        msg = f"{target}: no longer resolves inside {root_resolved} after link"
        raise InterferenceError(msg, intermediate=True)
    try:
        source.unlink()
    except OSError as exc:
        if _rollback_link(
            target,
            source_identity,
            survivor=(source, source_identity),
            root_resolved=root_resolved,
            hooks=hooks,
        ):
            msg = f"{source}: rename linked but source not removed ({exc.strerror or exc})"
            raise WriteError(msg) from exc
        msg = (
            f"{source}: rename linked but source not removed ({exc.strerror or exc}); "
            f"rollback unproven, {target} remains as a second name"
        )
        raise InterferenceError(msg, intermediate=True) from exc
    fsync_dir(target.parent)


def guarded_replace(
    target: Path,
    data: bytes,
    *,
    expected: ObjectIdentity,
    mode: int,
    root_resolved: Path,
    hooks: CommitHooks,
    survivor: tuple[Path, ObjectIdentity] | None = None,
    step: str = "replace-target",
) -> None:
    """Stage first, then authorize every object immediately before replacement."""
    staged = stage_bytes(target, data, mode=mode)
    hooks.before_step(step, target)
    try:
        check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)
        check_bound(target, expected, root_resolved=root_resolved)
        if survivor is not None:
            survivor_path, survivor_identity = survivor
            check_bound(survivor_path, survivor_identity, root_resolved=root_resolved)
    except InterferenceError:
        abort_staged(staged, root_resolved=root_resolved)
        raise
    publish_staged(staged, target)


class SafetyRefusedError(Exception):
    """The write ceremony refused before any mutation."""


class LockRefusedError(SafetyRefusedError):
    """The canonical corpus lock could not be acquired."""


class DestinationRefusedError(SafetyRefusedError):
    """An artifact destination did not pass the corpus guard."""


class WriteRefusedError(SafetyRefusedError):
    """The apply safety gate refused the run."""

    def __init__(self, refusals: list[GateRefusal]) -> None:
        super().__init__("; ".join(refusal.message for refusal in refusals))
        self.refusals = refusals


_FACTORY_TOKEN: Final[object] = object()


@dataclass(frozen=True)
class _Attestation:
    """Immutable authority retained for one live write ceremony."""

    command: Literal["apply", "restore"]
    source_root: Path
    run_id: str
    plan_json: str | None
    config_json: str | None
    plan_ref: ArtifactRef | None
    subject_sha256: str | None
    options: ApplyOptions | None
    manifest_path: Path
    report_path: Path | None
    chain: ManifestChain | None
    resume_chain: ManifestChain | None
    prior_attempt: PriorAttempt | None


@final
class WriteSafetyContext:
    """Factory-sealed proof that the exact write ceremony passed."""

    __slots__ = ("_active", "_attest")

    def __init__(
        self, *, _token: object | None = None, _attest: _Attestation | None = None
    ) -> None:
        if _token is not _FACTORY_TOKEN or _attest is None:
            msg = (
                "WriteSafetyContext is factory-sealed: enter "
                "apply_write_context() or restore_write_context()"
            )
            raise TypeError(msg)
        self._active = True
        self._attest = _attest

    def _confirm_active(self, command: Literal["apply", "restore"]) -> _Attestation:
        if not self._active:
            raise RuntimeError("WriteSafetyContext used outside its factory scope")
        if self._attest.command != command:
            msg = (
                "WriteSafetyContext attestation mismatch: issued for "
                f"{self._attest.command!r}, presented to {command!r}"
            )
            raise RuntimeError(msg)
        return self._attest

    def confirm_apply(self, *, run_id: str, manifest_path: Path) -> None:
        attest = self._confirm_active("apply")
        if (run_id, manifest_path.resolve()) != (attest.run_id, attest.manifest_path):
            raise RuntimeError("WriteSafetyContext attestation mismatch for apply")

    def _consume_apply_state(  # pyright: ignore[reportUnusedFunction]
        self,
    ) -> tuple[
        Plan,
        DocmendConfig,
        ArtifactRef,
        ApplyOptions,
        ManifestChain,
        PriorAttempt | None,
    ]:
        attest = self._confirm_active("apply")
        assert attest.plan_json is not None
        assert attest.config_json is not None
        assert attest.plan_ref is not None
        assert attest.options is not None
        assert attest.resume_chain is not None
        return (
            Plan.model_validate_json(attest.plan_json),
            DocmendConfig.model_validate_json(attest.config_json),
            attest.plan_ref,
            attest.options,
            attest.resume_chain,
            attest.prior_attempt,
        )

    def confirm_restore(self, *, run_id: str, manifest_out: Path) -> None:
        attest = self._confirm_active("restore")
        if (run_id, manifest_out.resolve()) != (attest.run_id, attest.manifest_path):
            raise RuntimeError("WriteSafetyContext attestation mismatch for restore")

    def confirm_report(self, report_path: Path) -> None:
        attest = self._confirm_active("apply")
        if attest.report_path is None or report_path.resolve() != attest.report_path:
            raise RuntimeError("WriteSafetyContext attestation mismatch for report")

    @property
    def chain(self) -> ManifestChain:
        attest = self._confirm_active("restore")
        if attest.chain is None:
            raise RuntimeError("restore capability has no validated chain")
        return attest.chain


def _load_apply_predecessors(
    manifest_paths: Sequence[Path],
    report_paths: Sequence[Path],
    *,
    source_root: Path,
    plan_sha256: str,
) -> tuple[ManifestChain, PriorAttempt | None]:
    """Validate the complete no-gap predecessor graph and derive its tip."""
    chain = read_manifest_chain(manifest_paths)
    if not chain.sets and not report_paths:
        return chain, None
    root_text = str(source_root.resolve())
    if chain.sets:
        root_header = chain.sets[0].header
        if root_header.source_root != root_text:
            raise ArtifactError(
                f"{chain.sets[0].path}: manifest source root does not match the plan"
            )
        if root_header.plan_sha256 != plan_sha256:
            raise ArtifactError(f"{chain.sets[0].path}: manifest belongs to a different plan")

    reports: dict[str, tuple[Report, str]] = {}
    for path in report_paths:
        loaded, digest = read_report_snapshot(path)
        if loaded.plan_ref.sha256 != plan_sha256:
            raise ArtifactError(f"{path}: predecessor report belongs to a different plan")
        if loaded.run_id in reports:
            raise ArtifactError(f"{path}: duplicate report for run {loaded.run_id}")
        reports[loaded.run_id] = (loaded, digest)

    chain_by_run = {item.header.run_id: item for item in chain.sets}
    chain_by_sha = {item.sha256: item for item in chain.sets}
    for run_id, (report, _digest) in reports.items():
        if report.manifest_sha256 is None:
            if report.totals.applied:
                raise ArtifactError(
                    f"report for run {run_id} claims applied actions without a manifest; "
                    "mutation evidence is missing"
                )
        else:
            manifest_set = chain_by_sha.get(report.manifest_sha256)
            if manifest_set is None or manifest_set.header.run_id != run_id:
                raise ArtifactError(f"report for run {run_id}: missing mutation evidence")
        matching_set = chain_by_run.get(run_id)
        if matching_set is not None:
            if report.manifest_sha256 != matching_set.sha256:
                raise ArtifactError(
                    f"run {run_id}: manifest and report disagree on manifest identity"
                )
            if matching_set.header.prior_attempt != report.prior_attempt:
                raise ArtifactError(f"run {run_id}: manifest and report disagree on prior_attempt")

    edges: dict[str, PriorAttempt | None] = {
        item.header.run_id: item.header.prior_attempt for item in chain.sets
    }
    for run_id, (report, _digest) in reports.items():
        edges.setdefault(run_id, report.prior_attempt)
    for run_id, edge in edges.items():
        if edge is None:
            continue
        target_manifest = chain_by_run.get(edge.run_id)
        target_report = reports.get(edge.run_id)
        resolved = (
            edge.manifest_sha256 is not None
            and target_manifest is not None
            and target_manifest.sha256 == edge.manifest_sha256
        ) or (
            edge.report_sha256 is not None
            and target_report is not None
            and target_report[1] == edge.report_sha256
        )
        if not resolved:
            raise ArtifactError(
                f"run {run_id} names predecessor {edge.run_id} whose evidence was not supplied"
            )
    referenced = {edge.run_id for edge in edges.values() if edge is not None}
    tips = [run_id for run_id in edges if run_id not in referenced]
    if len(tips) != 1:
        raise ArtifactError(f"predecessor evidence forms {len(tips)} attempt tips; one is required")
    tip = tips[0]
    if tip in reports:
        prior = PriorAttempt(run_id=tip, report_sha256=reports[tip][1], manifest_sha256=None)
    else:
        tip_sha = chain_by_run[tip].sha256
        assert tip_sha is not None
        prior = PriorAttempt(run_id=tip, report_sha256=None, manifest_sha256=tip_sha)
    return chain, prior


def _guard_or_refuse(
    destination: Path,
    *,
    corpus_root: Path,
    input_artifacts: Sequence[Path],
    exclude: PathSpec[GitIgnoreSpecPattern],
) -> None:
    refusal = guard_artifact_destination(
        destination,
        corpus_root=corpus_root,
        input_artifacts=input_artifacts,
        artifact_root=(Path.cwd() / ARTIFACT_DIR_NAME).resolve(),
        exclude=exclude,
    )
    if refusal is not None:
        raise DestinationRefusedError(refusal)


@contextlib.contextmanager
def apply_write_context(
    plan_path: Path,
    *,
    run_id: str,
    manifest_path: Path,
    report_path: Path,
    log_path: Path | None = None,
    backup_root_override: Path | None = None,
    preserved_by: str | None = None,
    allow_no_backup: bool = False,
    resume_manifest_paths: Sequence[Path] = (),
    prior_report_paths: Sequence[Path] = (),
    input_artifacts: Sequence[Path] = (),
    on_refusal: Callable[[list[GateRefusal], ArtifactRef, PriorAttempt | None], None] | None = None,
) -> Generator[WriteSafetyContext]:
    """Issue an attested apply capability while holding the canonical lock."""
    plan_artifact = plan_path.resolve()
    gated_plan, plan_sha256 = read_plan_snapshot(plan_artifact)
    if int(gated_plan.schema_version.split(".")[1]) > int(PLAN_SCHEMA_VERSION.split(".")[1]):
        raise ArtifactError(f"{plan_artifact}: unsupported plan schema {gated_plan.schema_version}")
    try:
        gated_config = DocmendConfig.model_validate(gated_plan.config)
    except ValidationError as exc:
        raise ArtifactError(f"{plan_artifact}: embedded config snapshot invalid: {exc}") from exc
    if gated_plan.source_root is None:
        raise ArtifactError(f"{plan_artifact}: plan has no source_root")
    source_root = Path(gated_plan.source_root).resolve()
    if not source_root.is_dir():
        raise ArtifactError(f"{source_root}: plan source root is not a directory")
    gated_plan = gated_plan.model_copy(update={"source_root": str(source_root)}, deep=True)
    plan_ref = ArtifactRef(path=str(plan_artifact), run_id=gated_plan.run_id, sha256=plan_sha256)
    backup_root = (
        backup_root_override if backup_root_override is not None else gated_config.write.backup_dir
    )
    options = ApplyOptions(
        write=True,
        backup_root=backup_root.resolve() if backup_root is not None else None,
        preserved_by=preserved_by,
        allow_no_backup=allow_no_backup,
    )
    resume_chain, prior_attempt = _load_apply_predecessors(
        resume_manifest_paths,
        prior_report_paths,
        source_root=source_root,
        plan_sha256=plan_sha256,
    )
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, gated_config.paths.exclude)
    guarded_inputs = (
        *input_artifacts,
        plan_artifact,
        *resume_manifest_paths,
        *prior_report_paths,
    )
    for destination in (report_path, manifest_path):
        _guard_or_refuse(
            destination,
            corpus_root=source_root,
            input_artifacts=guarded_inputs,
            exclude=exclude,
        )
    try:
        run_lock = lock.acquire(source_root, run_id=run_id, command="apply")
    except (lock.LockHeldError, OSError) as exc:
        raise LockRefusedError(str(exc)) from exc
    try:
        refusals = evaluate_gate(
            gated_plan,
            gated_config,
            source_root=source_root,
            options=options,
            manifest_dir=manifest_path.resolve().parent,
            report_path=report_path.resolve(),
            log_path=log_path.resolve() if log_path is not None else None,
        )
        if refusals:
            if on_refusal is not None:
                on_refusal(refusals, plan_ref, prior_attempt)
            raise WriteRefusedError(refusals)
        context = WriteSafetyContext(
            _token=_FACTORY_TOKEN,
            _attest=_Attestation(
                command="apply",
                source_root=source_root,
                run_id=run_id,
                plan_json=gated_plan.model_dump_json(),
                config_json=gated_config.model_dump_json(),
                plan_ref=plan_ref,
                subject_sha256=None,
                options=options,
                manifest_path=manifest_path.resolve(),
                report_path=report_path.resolve(),
                chain=None,
                resume_chain=resume_chain,
                prior_attempt=prior_attempt,
            ),
        )
        try:
            yield context
        finally:
            context._active = False  # pyright: ignore[reportPrivateUsage]
    finally:
        run_lock.release()


@contextlib.contextmanager
def restore_write_context(
    manifest_paths: Sequence[Path], *, run_id: str, manifest_out: Path
) -> Generator[WriteSafetyContext]:
    """Issue an attested restore capability over a factory-validated chain."""
    chain = read_manifest_chain(manifest_paths)
    if not chain.sets:
        raise ArtifactError("restore requires at least one manifest")
    root_header = chain.sets[0].header
    source_root = Path(root_header.source_root).resolve()
    _guard_or_refuse(
        manifest_out,
        corpus_root=source_root,
        input_artifacts=tuple(item.path for item in chain.sets),
        exclude=PathSpec.from_lines(GitIgnoreSpecPattern, root_header.effective_excludes),
    )
    try:
        run_lock = lock.acquire(source_root, run_id=run_id, command="restore")
    except (lock.LockHeldError, OSError) as exc:
        raise LockRefusedError(str(exc)) from exc
    tip = chain.sets[-1]
    context = WriteSafetyContext(
        _token=_FACTORY_TOKEN,
        _attest=_Attestation(
            command="restore",
            source_root=source_root,
            run_id=run_id,
            plan_json=None,
            config_json=None,
            plan_ref=None,
            subject_sha256=tip.sha256 or manifest_sha256(tip.path),
            options=None,
            manifest_path=manifest_out.resolve(),
            report_path=None,
            chain=chain,
            resume_chain=None,
            prior_attempt=None,
        ),
    )
    try:
        yield context
    finally:
        context._active = False  # pyright: ignore[reportPrivateUsage]
        run_lock.release()
