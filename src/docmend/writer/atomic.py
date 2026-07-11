"""Atomic filesystem primitives — the NFR-002 mechanism (D-004, adr-0003).

Every mutation path in the writer goes through these two functions; nothing
else in docmend calls os.replace/os.link on library files. Invariants:

- On ANY failure the target is untouched and the temp file is removed
  (ERR-003: "temp file cleaned up; original untouched") — with one deliberate
  exception: clobber=False publishes via hardlink + unlink-temp, and if the
  link succeeds but the temp unlink fails, the publish already happened, so
  that failure is swallowed rather than reported as a WriteError (see
  atomic_write_bytes). The stray temp name is lossless residue, not a
  partial write.
- clobber=False publishes via hardlink + unlink-temp: atomic on POSIX and
  EEXIST-safe against a target appearing between the collision check and the
  publish (the TOCTOU window os.replace cannot close). FileExistsError is
  deliberately NOT wrapped — the caller maps it to the collision policy.
- Parent-directory fsync is best-effort ("where practical", D-004): some
  filesystems refuse O_RDONLY dir fsync; durability of the rename itself is
  then the mount's problem, not a docmend error.
"""

import contextlib
import os
import secrets
from pathlib import Path


class WriteError(Exception):
    """A mutation failed environmentally (ERR-003); the original is intact."""


def fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _write_temp(target: Path, data: bytes, mode: int | None) -> Path:
    # Randomized per attempt (rev 0.26): a fixed staging name meant a hard
    # kill's residue blocked every later attempt at the same target with a
    # spurious O_EXCL failure, and made the staging path predictable to an
    # interfering process. Residue from a killed attempt is inert; EEXIST on
    # a candidate is a name collision to retry with a fresh name (bounded so
    # a pathological directory cannot loop forever), never an environmental
    # write failure — those propagate as OSError.
    for _ in range(8):
        tmp = target.with_name(f".{target.name}.{secrets.token_hex(4)}.docmend-tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        break
    else:
        msg = f"{target}: could not allocate a staging name in 8 attempts"
        raise OSError(msg)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            tmp.chmod(mode & 0o7777)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return tmp


def atomic_write_bytes(
    target: Path, data: bytes, *, mode: int | None = None, clobber: bool = True
) -> None:
    """Write `data` to `target` with no partial-write window (NFR-002)."""
    try:
        tmp = _write_temp(target, data, mode)
    except OSError as exc:
        msg = f"{target}: cannot stage write ({exc.strerror or exc})"
        raise WriteError(msg) from exc
    try:
        if clobber:
            tmp.replace(target)
        else:
            target.hardlink_to(tmp)  # FileExistsError on a collision race — caller's policy
    except FileExistsError:
        tmp.unlink(missing_ok=True)
        raise
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        msg = f"{target}: cannot publish write ({exc.strerror or exc})"
        raise WriteError(msg) from exc
    if not clobber:
        # The link above already succeeded, so target now holds the new bytes
        # — the publish happened. The stray staging name is just a second name
        # for that same inode (lossless residue); staging names are randomized
        # per attempt and EEXIST-retried, so residue never blocks a retry.
        # Reporting WriteError here would tell the caller the mutation failed
        # when it didn't — worse than the residue, so we swallow this one
        # deliberately.
        with contextlib.suppress(OSError):
            tmp.unlink()
    fsync_dir(target.parent)


def link_no_clobber(source: Path, target: Path) -> None:
    """Give `source`'s inode a second name at `target`, refusing an existing
    target. The lossless half of a rename: after it, BOTH names exist."""
    try:
        target.hardlink_to(source)
    except FileExistsError:
        raise
    except OSError as exc:
        msg = f"{target}: cannot link rename target ({exc.strerror or exc})"
        raise WriteError(msg) from exc


def rename_no_clobber(source: Path, target: Path) -> None:
    """Move `source` to `target`, refusing an existing target (FR-011).

    link + unlink instead of check-then-os.replace: link is atomic and
    EEXIST-safe; a crash between the two calls leaves BOTH names pointing at
    one intact inode — recoverable, never lossy. v1 renames change only the
    suffix, so source and target always share a directory (same device).
    """
    link_no_clobber(source, target)
    try:
        source.unlink()
    except OSError as exc:
        # Roll the link back so a failed rename leaves the exact pre-action
        # state (codex CR-NEW-004 class); if even that fails, both names
        # remain on one intact inode — superset, lossless, and said so.
        residue = ""
        try:
            target.unlink()
        except OSError:
            residue = f"; rollback failed, {target} remains as a second name"
        msg = f"{source}: rename linked but source not removed ({exc.strerror or exc}){residue}"
        raise WriteError(msg) from exc
    fsync_dir(target.parent)


def rename_overwrite(source: Path, target: Path) -> None:
    """Move `source` onto an existing `target` (FR-011 overwrite policy only).

    The one deliberate clobber in the writer (codex CR-NEW-001): the same
    os.replace + parent-fsync + WriteError contract as every other mutation —
    an overwrite rename must not have weaker crash-durability than a
    no-clobber one. Callers have already backed up the clobbered target.
    """
    try:
        source.replace(target)
    except OSError as exc:
        msg = f"{target}: cannot replace with {source} ({exc.strerror or exc})"
        raise WriteError(msg) from exc
    fsync_dir(target.parent)
