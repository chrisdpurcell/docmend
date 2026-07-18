"""Per-file cooperative watchdog for the FR-019/OQ-028 timeout.

Design decision (spec FR-019, ERR-009, R-007; OQ-037): the v2 sequential engine
uses an in-process ``signal.setitimer(ITIMER_REAL)`` alarm scoped to one file.
SIGALRM raises :class:`PerFileTimeoutError` inside the process, unwinding the
current file's work so the caller can record a timeout skip and continue. This
is a cooperative Python boundary, not hard process termination: a native call
that does not return control to the interpreter can delay the exception. No
worker protocol exists in v2; a future hard process boundary requires the
separately approved concurrency design governed by adr-0022.

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
    path — the sequential engine runs this work on the main thread. In-process
    threads fall through to the no-op and therefore must not be treated as a
    hard watchdog boundary.

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
