"""Atomic filesystem primitives — the NFR-002 mechanism (D-004, adr-0003).

Every mutation path in the writer goes through these two functions; nothing
else in docmend calls os.replace/os.link on library files. Invariants:

- On ANY failure the target is untouched and the temp file is removed
  (ERR-003: "temp file cleaned up; original untouched").
- clobber=False publishes via os.link + unlink-temp: atomic on POSIX and
  EEXIST-safe against a target appearing between the collision check and the
  publish (the TOCTOU window os.replace cannot close). FileExistsError is
  deliberately NOT wrapped — the caller maps it to the collision policy.
- Parent-directory fsync is best-effort ("where practical", D-004): some
  filesystems refuse O_RDONLY dir fsync; durability of the rename itself is
  then the mount's problem, not a docmend error.
"""

import os
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
    tmp = target.with_name(f".{target.name}.docmend-tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, mode & 0o7777)  # noqa: PTH101
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
            os.replace(tmp, target)  # noqa: PTH105
        else:
            os.link(tmp, target)  # FileExistsError on a collision race — caller's policy
            tmp.unlink()
    except FileExistsError:
        tmp.unlink(missing_ok=True)
        raise
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        msg = f"{target}: cannot publish write ({exc.strerror or exc})"
        raise WriteError(msg) from exc
    fsync_dir(target.parent)


def link_no_clobber(source: Path, target: Path) -> None:
    """Give `source`'s inode a second name at `target`, refusing an existing
    target. The lossless half of a rename: after it, BOTH names exist."""
    try:
        os.link(source, target)
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
        os.replace(source, target)  # noqa: PTH105
    except OSError as exc:
        msg = f"{target}: cannot replace with {source} ({exc.strerror or exc})"
        raise WriteError(msg) from exc
    fsync_dir(target.parent)
