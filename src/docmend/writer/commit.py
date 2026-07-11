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

import errno
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from docmend.lineage import ObjectIdentity
from docmend.writer.atomic import (
    WriteError,
    abort_staged,
    fsync_dir,
    link_no_clobber,
    publish_staged,
    stage_bytes,
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
