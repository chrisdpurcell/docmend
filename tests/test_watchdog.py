"""Per-file watchdog unit tests (spec: FR-019, OQ-028, ERR-009; DEV-002).

The context manager is the v1 in-process realization of the FR-019 watchdog
(adr-0007 keeps the engine sequential, so there is no worker process to kill).
These tests pin the two properties the scan/plan callers depend on: it raises on
overrun, and it always restores the prior SIGALRM handler and disarms the itimer
so a timeout in one file never leaks an armed alarm into the next.
"""

import signal
import threading
import time
from collections.abc import Iterator

import pytest

from docmend.watchdog import PerFileTimeoutError, per_file_watchdog


@pytest.fixture(autouse=True)
def restore_sigalrm() -> Iterator[None]:
    """Guard the process-wide SIGALRM handler against a leaking test."""
    saved = signal.getsignal(signal.SIGALRM)
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, saved)


def test_watchdog__raises_after_timeout() -> None:
    """FR-019/ERR-009: work exceeding the budget is interrupted, not awaited."""
    start = time.monotonic()
    with pytest.raises(PerFileTimeoutError), per_file_watchdog(0.02):
        time.sleep(5)
    # The alarm fired near 0.02s, nowhere near the 5s the body asked to sleep.
    assert time.monotonic() - start < 1.0


def test_watchdog__fast_body_does_not_raise() -> None:
    """A body that finishes inside the budget passes through untouched."""
    with per_file_watchdog(30):
        result = 1 + 1
    assert result == 2


def test_watchdog__restores_prior_handler_and_disarms_itimer() -> None:
    """The finally block must reinstate the caller's handler and clear the timer,
    so a per-file alarm never survives into the next file."""
    sentinel = signal.getsignal(signal.SIGALRM)

    with per_file_watchdog(30):
        # Inside the scope our own handler is installed and the timer is armed.
        assert signal.getsignal(signal.SIGALRM) is not sentinel
        remaining, _interval = signal.getitimer(signal.ITIMER_REAL)
        assert remaining > 0

    assert signal.getsignal(signal.SIGALRM) is sentinel
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_watchdog__restores_handler_even_on_timeout() -> None:
    """A timeout unwinds through the same finally, so the handler is still
    restored (the next file must start from the caller's handler)."""
    sentinel = signal.getsignal(signal.SIGALRM)
    with pytest.raises(PerFileTimeoutError), per_file_watchdog(0.02):
        time.sleep(5)
    assert signal.getsignal(signal.SIGALRM) is sentinel
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_watchdog__off_main_thread_is_a_noop() -> None:
    """Signals only work on the main thread; off it the manager must plain-yield
    (never raise a ValueError at setup) so it is a safety valve, not a landmine."""
    outcome: list[str] = []

    def worker() -> None:
        try:
            with per_file_watchdog(0.01):
                time.sleep(0.05)  # would time out on the main thread; here it must not
            outcome.append("completed")
        except Exception as exc:  # the test deliberately records any escape
            outcome.append(f"raised:{type(exc).__name__}")

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert outcome == ["completed"]
