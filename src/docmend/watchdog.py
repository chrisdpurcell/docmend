"""Per-file watchdog — the FR-019/OQ-028 timeout, realized for v1's engine.

Design decision (spec FR-019, ERR-009, R-007; adr-0007): FR-019's requirement
text describes a *process-level* watchdog that "terminates" per-file work — the
form that fits the deferred process pool (adr-0007's concurrency primitive),
where a stuck worker can be killed outright. v1 never spawns that pool:
adr-0007 keeps the engine sequential-in-process until profiling justifies
parallelism, so there is no worker process to terminate. The v1 realization is
therefore an in-process ``signal.setitimer(ITIMER_REAL)`` alarm scoped to one
file: SIGALRM fires after ``per_file_timeout`` seconds and the handler raises
:class:`PerFileTimeoutError` inside the same process, unwinding the current
file's work back to the caller, which records it as a timeout skip and moves on.
The process-level "terminate" form rides the deferred pool; this deviation is
recorded as DEV-002 in the spec's Deviations Log.

Scope contract (FR-019): discovery, detection, and transform-prediction ONLY —
NEVER the writer. The alarm interrupts arbitrary in-progress work by raising at
a bytecode boundary; a mutation half-applied that way could corrupt a library
file, so the writer layer (docmend.writer) is never wrapped. Callers here wrap
read-only classification and pure text prediction, where an interrupted attempt
leaves nothing on disk to repair.
"""

import signal
import threading
from collections.abc import Generator
from contextlib import contextmanager
from types import FrameType


class PerFileTimeoutError(Exception):
    """Per-file processing exceeded ``limits.per_file_timeout`` (FR-019, ERR-009)."""


@contextmanager
def per_file_watchdog(seconds: float) -> Generator[None]:
    """Raise :class:`PerFileTimeoutError` if the body runs longer than ``seconds``.

    No-ops (a plain yield) off the main thread: ``signal.signal`` and
    ``setitimer`` only work there, so a watchdog installed from a worker thread
    would raise ``ValueError`` at setup. This is a safety valve, not the normal
    path — v1's sequential engine always runs on the main thread, and a future
    pool's workers run on the main thread of their own process, so both get the
    real alarm; only in-process threads (which v1 never uses for this work) fall
    through to the no-op.

    The itimer is always disarmed and the prior SIGALRM handler always restored
    in ``finally``, so a timeout in one file never leaks an armed alarm into the
    next.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def _on_alarm(_signum: int, _frame: FrameType | None) -> None:
        msg = f"per-file processing exceeded {seconds}s"
        raise PerFileTimeoutError(msg)

    previous = signal.signal(signal.SIGALRM, _on_alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
