"""Run-level lock — one live plan/apply/restore per target tree (OQ-027, AW-005).

Location (OQ-036 proposal): $XDG_STATE_HOME/docmend/locks/<sha256(root)>.json,
NOT inside the library tree — plan stays write-free over the library (§3.1) and
a read-only tree stays plannable. Keyed on the RESOLVED source root so
invocations from different CWDs contend correctly.

Mechanism: flock(2), not O_EXCL-create-plus-unlink (codex CR-004). The kernel
owns the lock: it vanishes with the holding process (crash included), so no
stale-PID detection exists to get wrong, and no unlink-by-name step exists
that could remove a competitor's freshly acquired lock (the classic steal
race). Release closes the descriptor and leaves the file behind — an empty
file in the state dir is metadata debris, never a stale lock. Holder JSON is
written into the file purely for the refusal message. Single-machine
semantics by design (A-001: local POSIX filesystem; flock over NFS is out of
scope).
"""

import errno
import fcntl
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


class LockHeldError(Exception):
    """Another live run holds this target's lock (exit 3, AW-005)."""


class RunLock:
    def __init__(self, path: Path, fd: int) -> None:
        self.path = path
        self._fd = fd
        self._released = False

    def release(self) -> None:
        # Closing the descriptor drops the flock; the file deliberately stays
        # (unlinking it would reopen the CR-004 steal race for a competitor
        # blocked on the same inode).
        if not self._released:
            os.close(self._fd)
            self._released = True


def _default_state_dir() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "docmend" / "locks"


def lock_path(source_root: Path, *, state_dir: Path | None = None) -> Path:
    digest = hashlib.sha256(str(source_root.resolve()).encode()).hexdigest()
    return (state_dir if state_dir is not None else _default_state_dir()) / f"{digest}.lock"


def acquire(
    source_root: Path, *, run_id: str, command: str, state_dir: Path | None = None
) -> RunLock:
    path = lock_path(source_root, state_dir=state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        # Contention is EWOULDBLOCK/EAGAIN on Linux (BlockingIOError) but
        # EACCES on some Unixes — treat both as "held", re-raise the rest.
        if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES):
            os.close(fd)
            raise
        holder = _read_holder(fd)
        os.close(fd)
        msg = (
            f"{source_root}: another docmend run holds the lock{holder} — "
            f"AW-005 refuses a second concurrent run against the same target"
        )
        raise LockHeldError(msg) from exc
    # Best-effort holder metadata for the competitor's refusal message; the
    # flock itself, not this JSON, is the mutual exclusion.
    os.ftruncate(fd, 0)
    os.write(
        fd,
        json.dumps(
            {
                "run_id": run_id,
                "pid": os.getpid(),
                "command": command,
                "started_at": datetime.now(UTC).isoformat(),
            }
        ).encode("utf-8"),
    )
    os.fsync(fd)
    return RunLock(path, fd)


def _read_holder(fd: int) -> str:
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        existing: dict[str, object] = json.loads(os.read(fd, 4096).decode("utf-8"))
    except OSError, ValueError:
        return ""
    return (
        f" (run_id {existing.get('run_id')}, pid {existing.get('pid')}, "
        f"command {existing.get('command')})"
    )
