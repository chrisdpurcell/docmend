"""Dangling-intent adjudication — the adr-0019 crash-state table.

A dangling intent (no terminal after it in the chain) means a kill landed
inside that mutation's window. This module decides FROM DISK STATE which step
the kill interrupted, using only the intent's persisted evidence: recorded
hashes plus the exact `(st_dev, st_ino)` identities captured before mutation.

Cross-file contracts:
- Predicates use `lstat` and NEVER follow symlinks: a symlink at a recorded
  name fails the identity predicate outright.
- Identity comparison is exact dev+ino equality (design F4 round 4): a
  same-bytes replacement under a different inode fails the predicate in both
  the pre-publish and post-publish windows and is REFUSED — adjudication
  never adopts or unlinks an object it cannot prove is the recorded one.
- `external-interference` is reserved for states failing every recorded
  predicate (ADR-0006's no-guessing rule carried forward); it is never the
  classification of a known intermediate state.
- Restore-inverse rows (records carrying `undoes_*`) may need the ORIGINAL
  apply record (`undone`) for the clobbered-target backup — the inverse
  record itself holds no backup references.
"""

import errno
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from docmend.lineage import ObjectIdentity
from docmend.writer.atomic import WriteError
from docmend.writer.commit import (
    NO_HOOKS,
    CommitHooks,
    InterferenceError,
    check_bound,
    guarded_replace,
)
from docmend.writer.manifest import ManifestRecord

type AdjudicationVerdict = Literal[
    "never-happened", "completed", "finish-remaining", "external-interference"
]


@dataclass(frozen=True)
class Adjudication:
    verdict: AdjudicationVerdict
    detail: str


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class _Observed:
    """Describe one name from a single non-following descriptor observation."""

    state: ObservationState
    identity: ObjectIdentity | None
    sha256: str | None
    mode: int | None

    @property
    def absent(self) -> bool:
        return self.state == "absent"


type ObservationState = Literal["regular", "absent", "symlink", "unobservable"]


def _observe(path: Path) -> _Observed:
    """Capture identity, bytes, and mode through one non-following descriptor."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            return _Observed("absent", None, None, None)
        if exc.errno == errno.ELOOP:
            return _Observed("symlink", None, None, None)
        return _Observed("unobservable", None, None, None)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return _Observed("unobservable", None, None, None)
        identity = ObjectIdentity(dev=st.st_dev, ino=st.st_ino)
        with os.fdopen(fd, "rb") as file_handle:
            fd = -1
            data = file_handle.read()
    except OSError:
        return _Observed("unobservable", None, None, None)
    finally:
        if fd >= 0:
            os.close(fd)
    return _Observed("regular", identity, _sha(data), st.st_mode)


def _is(observed: _Observed, identity: ObjectIdentity | None, sha256: str | None) -> bool:
    """The core predicate: the observed name binds to the RECORDED inode and
    holds the RECORDED bytes. A null recorded identity never matches (the
    intent failed to persist it — refuse rather than guess)."""
    return (
        identity is not None
        and observed.state == "regular"
        and observed.identity == identity
        and sha256 is not None
        and observed.sha256 == sha256
    )


def _refuse(record: ManifestRecord, detail: str) -> Adjudication:
    return Adjudication(
        verdict="external-interference",
        detail=f"{record.action_id}: {detail} (fails every recorded identity/hash predicate)",
    )


def adjudicate_dangling_intent(
    record: ManifestRecord, *, undone: ManifestRecord | None = None
) -> Adjudication:
    """Classify the crash-after state of a dangling intent's mutation.

    `record` is the dangling intent itself. For restore-inverse intents
    (`undoes_action_id` set), `undone` must be the original apply record —
    the clobbered-target rows verify against ITS backup evidence.
    """
    if record.undoes_action_id is not None:
        return _adjudicate_inverse(record, undone)
    return _adjudicate_apply(record)


def _adjudicate_apply(record: ManifestRecord) -> Adjudication:
    source = _observe(Path(record.original_path))
    target = _observe(Path(record.target_path))

    if record.operation == "rewrite":
        # Single atomic replace of one path.
        if _is(target, record.source_identity, record.before_sha256):
            return Adjudication("never-happened", "path still holds the recorded before state")
        if _is(target, record.expected_published_identity, record.after_sha256):
            return Adjudication("completed", "path holds the expected published output")
        return _refuse(record, "rewrite path matches neither before nor after state")

    if record.operation == "rename":
        if record.overwritten_sha256 is not None:
            # Overwrite flavor: single os.replace moving the source inode.
            if _is(source, record.source_identity, record.before_sha256) and (
                target.sha256 == record.overwritten_sha256
                and _matches_optional(target, record.target_identity)
            ):
                return Adjudication("never-happened", "source intact; target still pre-overwrite")
            if target.absent and source.absent:
                return _refuse(record, "both names absent after an overwrite rename")
            if source.absent and _is(
                target, record.expected_published_identity, record.before_sha256
            ):
                return Adjudication("completed", "source inode moved onto the target name")
            return _refuse(record, "overwrite rename matches no recorded state")
        # No-clobber flavor: link, then unlink — the lossless intermediate
        # leaves BOTH names bound to one intact inode.
        source_ok = _is(source, record.source_identity, record.before_sha256)
        target_ok = _is(target, record.expected_published_identity, record.before_sha256)
        if source_ok and target.absent:
            return Adjudication("never-happened", "source intact; target never linked")
        if source_ok and target_ok:
            return Adjudication(
                "finish-remaining", "both names bound to the recorded inode; unlink remains"
            )
        if source.absent and target_ok:
            return Adjudication("completed", "target linked and source already unlinked")
        return _refuse(record, "no-clobber rename matches no recorded state")

    # rename_and_rewrite: publish target (staged inode), then unlink source.
    source_ok = _is(source, record.source_identity, record.before_sha256)
    published = _is(target, record.expected_published_identity, record.after_sha256)
    target_pre = (
        target.absent
        if record.overwritten_sha256 is None
        else (
            target.sha256 == record.overwritten_sha256
            and _matches_optional(target, record.target_identity)
        )
    )
    if source_ok and target_pre:
        return Adjudication("never-happened", "source intact; target never published")
    if source_ok and published:
        return Adjudication("finish-remaining", "target published; source unlink remains")
    if source.absent and published:
        return Adjudication("completed", "target published and source unlinked")
    return _refuse(record, "rename_and_rewrite matches no recorded state")


def _matches_optional(observed: _Observed, identity: ObjectIdentity | None) -> bool:
    """Target-identity predicate where the intent may legitimately carry null
    (no overwrite target existed at intent time)."""
    if identity is None:
        return True
    return observed.identity == identity


def _adjudicate_inverse(record: ManifestRecord, undone: ManifestRecord | None) -> Adjudication:
    """Restore-inverse rows. The inverse record's original_path is the LIVE
    applied name being undone; target_path is the reinstated original.
    before_sha256 = the applied bytes; after_sha256 = the original bytes."""
    applied_name = _observe(Path(record.original_path))
    original_name = _observe(Path(record.target_path))
    clobbered_sha = undone.overwritten_sha256 if undone is not None else None

    if record.operation == "rewrite":
        # Inverse of a rewrite: single atomic write of the one path.
        if _is(applied_name, record.source_identity, record.before_sha256):
            return Adjudication("never-happened", "path still holds the applied bytes")
        if _is(applied_name, record.expected_published_identity, record.after_sha256):
            return Adjudication("completed", "path holds the reinstated original bytes")
        return _refuse(record, "inverse rewrite matches neither state")

    if record.operation == "rename":
        applied_ok = _is(applied_name, record.source_identity, record.before_sha256)
        reinstated_ok = _is(original_name, record.expected_published_identity, record.before_sha256)
        if clobbered_sha is None:
            # Inverse of a pure rename: link original, unlink applied name.
            if applied_ok and original_name.absent:
                return Adjudication("never-happened", "applied name intact; original not linked")
            if applied_ok and reinstated_ok:
                return Adjudication(
                    "finish-remaining", "both names bound; applied-name unlink remains"
                )
            if applied_name.absent and reinstated_ok:
                return Adjudication("completed", "original reinstated; applied name gone")
            return _refuse(record, "inverse rename matches no recorded state")
        # Inverse of an overwrite rename: relink original, then rewrite the
        # applied name back to the recorded clobbered bytes.
        if applied_ok and original_name.absent:
            return Adjudication("never-happened", "applied name intact; original absent")
        if applied_ok and reinstated_ok:
            return Adjudication(
                "finish-remaining",
                "original relinked; clobbered-target rewrite remains",
            )
        if reinstated_ok and applied_name.sha256 == clobbered_sha:
            return Adjudication("completed", "original reinstated and clobbered target restored")
        return _refuse(record, "inverse overwrite-rename matches no recorded state")

    # Inverse of rename_and_rewrite: reinstate the original (staged write),
    # then clean up the applied target (unlink, or rewrite to clobbered bytes).
    reinstated = _is(original_name, record.expected_published_identity, record.after_sha256)
    applied_intact = _is(applied_name, record.source_identity, record.before_sha256)
    if original_name.absent and applied_intact:
        return Adjudication("never-happened", "original absent; applied target intact")
    if reinstated and applied_intact:
        return Adjudication(
            "finish-remaining", "original reinstated; applied-target cleanup remains"
        )
    cleanup_done = (
        applied_name.absent if clobbered_sha is None else applied_name.sha256 == clobbered_sha
    )
    if reinstated and cleanup_done:
        return Adjudication("completed", "original reinstated and target cleaned up")
    return _refuse(record, "inverse rename_and_rewrite matches no recorded state")


def finish_remaining(
    record: ManifestRecord,
    *,
    undone: ManifestRecord | None = None,
    root_resolved: Path,
    hooks: CommitHooks = NO_HOOKS,
) -> None:
    """Complete the residual step(s) of a `finish-remaining` adjudication.

    The caller has JUST adjudicated, so the involved objects were verified
    against the recorded identities and hashes; each step here re-verifies
    the object it destroys immediately before acting (the adjudicate-to-act
    window is the accepted residual until Plan C's CommitBoundary).
    Raises WriteError on any environmental failure.
    """
    if record.undoes_action_id is None:
        # Apply rows: the only residual step is unlinking the source name.
        _verified_unlink(
            Path(record.original_path),
            record.source_identity,
            record.before_sha256,
            survivor=(
                Path(record.target_path),
                record.expected_published_identity,
                record.after_sha256,
            ),
            root_resolved=root_resolved,
            hooks=hooks,
        )
        return
    clobbered_sha = undone.overwritten_sha256 if undone is not None else None
    if record.operation == "rename" and clobbered_sha is not None:
        # Rewrite the applied name back to the recorded clobbered bytes.
        _rewrite_from_backup(record, undone, root_resolved=root_resolved, hooks=hooks)
        return
    if record.operation == "rename_and_rewrite" and clobbered_sha is not None:
        _rewrite_from_backup(record, undone, root_resolved=root_resolved, hooks=hooks)
        return
    # Pure-rename inverse (or rename_and_rewrite with no clobbered target):
    # the residual step is unlinking the applied name.
    _verified_unlink(
        Path(record.original_path),
        record.source_identity,
        record.before_sha256,
        survivor=(
            Path(record.target_path),
            record.expected_published_identity,
            record.after_sha256,
        ),
        root_resolved=root_resolved,
        hooks=hooks,
    )


def _verified_unlink(
    path: Path,
    identity: ObjectIdentity | None,
    sha256: str,
    *,
    survivor: tuple[Path, ObjectIdentity | None, str | None] | None,
    root_resolved: Path,
    hooks: CommitHooks,
) -> None:
    hooks.before_step("unlink", path)
    observed = _observe(path)
    if not _is(observed, identity, sha256):
        msg = f"{path}: object changed between adjudication and unlink; refusing"
        raise WriteError(msg)
    if survivor is not None:
        survivor_path, survivor_identity, survivor_sha = survivor
        if not _is(_observe(survivor_path), survivor_identity, survivor_sha):
            msg = (
                f"{survivor_path}: surviving name changed between adjudication "
                f"and finish; refusing to unlink {path}"
            )
            raise WriteError(msg)
        assert survivor_identity is not None
        try:
            check_bound(survivor_path, survivor_identity, root_resolved=root_resolved)
        except InterferenceError as exc:
            raise WriteError(str(exc)) from exc
    assert identity is not None
    try:
        check_bound(path, identity, root_resolved=root_resolved)
    except InterferenceError as exc:
        raise WriteError(str(exc)) from exc
    try:
        path.unlink()
    except OSError as exc:
        msg = f"{path}: cannot finish adjudicated unlink ({exc.strerror or exc})"
        raise WriteError(msg) from exc


def _rewrite_from_backup(
    record: ManifestRecord,
    undone: ManifestRecord | None,
    *,
    root_resolved: Path,
    hooks: CommitHooks,
) -> None:
    assert undone is not None  # adjudication verdict required it
    if undone.overwritten_backup_path is None:
        msg = (
            f"{record.action_id}: clobbered target restorable only from external "
            f"preservation; cannot finish the inverse"
        )
        raise WriteError(msg)
    backup = Path(undone.overwritten_backup_path)
    try:
        data = backup.read_bytes()
    except OSError as exc:
        msg = f"{backup}: clobbered-target backup unreadable ({exc.strerror or exc})"
        raise WriteError(msg) from exc
    if _sha(data) != undone.overwritten_sha256:
        msg = f"{backup}: clobbered-target backup hash mismatch (ERR-004)"
        raise WriteError(msg)
    target = Path(record.original_path)
    observed = _observe(target)
    assert record.source_identity is not None
    assert record.expected_published_identity is not None
    if not _is(observed, record.source_identity, record.before_sha256):
        msg = f"{target}: object changed before backup rewrite; refusing"
        raise WriteError(msg)
    if observed.mode is None:
        msg = f"{target}: mode unavailable for verified backup rewrite"
        raise WriteError(msg)
    try:
        guarded_replace(
            target,
            data,
            expected=record.source_identity,
            mode=observed.mode,
            root_resolved=root_resolved,
            hooks=hooks,
            survivor=(Path(record.target_path), record.expected_published_identity),
        )
    except InterferenceError as exc:
        raise WriteError(str(exc)) from exc
