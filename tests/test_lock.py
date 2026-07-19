"""Run-level lock (OQ-036 proposal; spec OQ-027, AW-005, §8.5).

One live plan/apply/restore per target tree; a second invocation refuses with
exit 3. flock(2) on a file under $XDG_STATE_HOME/docmend/locks keyed by the
hashed resolved source root: the library tree is never touched, different CWDs
still contend, and — because the kernel drops the lock with the holding
process — a crashed run can never leave a stale lock, and no unlink-based
steal race exists (codex CR-004 class, closed by construction).
"""

import errno
import os
import subprocess
import sys
from pathlib import Path

import pytest

from docmend import lock

RUN_ID = "run_20260706T000000Z_00004b"


def test_acquire_then_second_acquire__refuses(tmp_path: Path) -> None:
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()
    held = lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state)
    try:
        with pytest.raises(lock.LockHeldError) as excinfo:
            lock.acquire(
                root, run_id="run_20260706T000001Z_00004c", command="plan", state_dir=state
            )
        assert RUN_ID in str(excinfo.value)  # holder identified in the refusal message
    finally:
        held.release()


def test_holder_write_failure__releases_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A holder-metadata write failure after flock (ENOSPC/EIO) releases the
    lock like every other failure path — a second acquire must then succeed."""
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()

    def _boom(*_args: object, **_kwargs: object) -> int:
        raise OSError(errno.ENOSPC, "no space left on device")

    monkeypatch.setattr(os, "write", _boom)
    with pytest.raises(OSError):
        lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state)
    monkeypatch.undo()
    # A stranded flock would make this raise LockHeldError instead.
    lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state).release()


def test_release__allows_reacquire(tmp_path: Path) -> None:
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()
    lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state).release()
    lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state).release()


def test_dead_holder__lock_auto_released(tmp_path: Path) -> None:
    """A holder that exited (or crashed) leaves no stale lock: flock dies with
    the process, so re-acquisition needs no stale detection at all (CR-004)."""
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()
    script = (
        "import sys; from pathlib import Path; from docmend import lock; "
        "lock.acquire(Path(sys.argv[1]), run_id='run_20260101T000000Z_dead00', "
        "command='apply', state_dir=Path(sys.argv[2]))"
    )
    subprocess.run([sys.executable, "-c", script, str(root), str(state)], check=True)
    lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state).release()


def test_live_holder_in_other_process__refuses(tmp_path: Path) -> None:
    """AW-005 across real processes: a subprocess holds the lock while this
    process tries to acquire."""
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()
    script = (
        "import sys, time; from pathlib import Path; from docmend import lock; "
        "lock.acquire(Path(sys.argv[1]), run_id='run_20260101T000000Z_11ee00', "
        "command='apply', state_dir=Path(sys.argv[2])); print('held', flush=True); "
        "time.sleep(30)"
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", script, str(root), str(state)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "held"
        with pytest.raises(lock.LockHeldError):
            lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state)
    finally:
        holder.kill()
        holder.wait()


def test_different_roots__do_not_contend(tmp_path: Path) -> None:
    state = tmp_path / "state"
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    held = lock.acquire(a, run_id=RUN_ID, command="apply", state_dir=state)
    try:
        lock.acquire(b, run_id=RUN_ID, command="apply", state_dir=state).release()
    finally:
        held.release()


def test_release__is_idempotent(tmp_path: Path) -> None:
    """Interfaces contract: `RunLock.release() -> None (idempotent)` — a second
    release() must not raise (e.g. double-close the descriptor)."""
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()
    held = lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state)
    held.release()
    held.release()  # no-op, not a re-raise of OSError: Bad file descriptor


def test_corrupt_holder_metadata__refusal_message_omits_holder(tmp_path: Path) -> None:
    """A pre-3 (or hand-edited) lock file with unparsable content still refuses
    correctly: `_read_holder` swallows the decode failure and the refusal
    message just drops the parenthetical, per the "best-effort" docstring."""
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()
    script = (
        "import fcntl, os, sys, time; "
        "fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600); "
        "fcntl.flock(fd, fcntl.LOCK_EX); "
        "os.write(fd, b'not json'); os.fsync(fd); "
        "print('held', flush=True); time.sleep(30)"
    )
    path = lock.lock_path(root, state_dir=state)
    path.parent.mkdir(parents=True, exist_ok=True)
    holder = subprocess.Popen(
        [sys.executable, "-c", script, str(path)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "held"
        with pytest.raises(lock.LockHeldError) as excinfo:
            lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state)
        assert "(run_id" not in str(excinfo.value)
    finally:
        holder.kill()
        holder.wait()


def test_acquire__reraises_unexpected_flock_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only contention errnos (EAGAIN/EWOULDBLOCK/EACCES) mean "held"; anything
    else (e.g. ENOSPC) is a real failure that must propagate, not be
    misreported as LockHeldError."""
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()

    def _raise_enospc(_fd: int, _flags: int) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(lock.fcntl, "flock", _raise_enospc)
    with pytest.raises(OSError, match="No space left"):
        lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state)
