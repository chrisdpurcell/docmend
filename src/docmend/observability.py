"""Logging framework and run-ID conventions — spec §18.5, NFR-003, OQ-017 (MS-0 item 3).

Cross-file contract:
- The run-ID minted by :func:`new_run_id` is THE per-run correlation key: it names
  the log file, is bound into every log line, and is the same identifier the
  DR-001..DR-004 artifacts record (§18.5).
- Two sinks with deliberately decoupled levels (OQ-017): the console renderer on
  stderr follows ``--verbose``/``--quiet``, while the per-run JSON Lines file is
  always DEBUG-floored — a quiet run must still be diagnosable after the fact
  (NFR-003), which is why the flags never touch the file sink.
- One log file per run (``docmend-{run_id}.jsonl``), a first-class sibling of the
  run artifacts — never a rotated/deleted long-lived file, mirroring §7.4/§18.6
  retention ("the tool never deletes its own manifests or backups").
- Console goes to stderr so machine-readable output on stdout is never interleaved
  with human log noise.
- Log lines carry relative paths and hashes, never document body content (§13.5);
  that constraint binds the *callers* emitting events, recorded here as the schema
  contract: ts / level / run_id / command / event [+ path, action, reason, detail].
"""

import logging
import secrets
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from structlog.typing import EventDict, Processor

#: Wire format of a run-ID: UTC second-resolution timestamp + 6 hex chars of
#: randomness (collision guard for runs started within the same second).
RUN_ID_FORMAT = "run_{YYYYMMDDTHHMMSSZ}_{6 lowercase hex}"
HEARTBEAT_INTERVAL_SECONDS = 30.0

type ProgressEvent = dict[str, object]
type ProgressEmitter = Callable[[ProgressEvent], None]
type MonotonicClock = Callable[[], float]


@dataclass(slots=True)
class ProgressHeartbeat:
    """Emit best-effort, aggregate-only stage liveness at record boundaries.

    This object never schedules work. Callers invoke :meth:`advance` only after
    control returns between records, so a native call can delay both the
    cooperative watchdog and these events exactly as documented in §18.5.
    """

    stage: str
    emit: ProgressEmitter
    clock: MonotonicClock = time.monotonic
    interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS
    _started_at: float | None = field(default=None, init=False, repr=False)
    _last_emitted_at: float | None = field(default=None, init=False, repr=False)
    _total: int | None = field(default=None, init=False, repr=False)
    _last_counts: tuple[int, int, int] = field(default=(0, 0, 0), init=False, repr=False)
    _terminal: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.stage:
            raise ValueError("heartbeat stage must not be empty")
        if self.interval_seconds <= 0:
            raise ValueError("heartbeat interval must be positive")

    def start(self, *, total: int | None) -> None:
        """Start one stage and emit its input count when known."""
        if self._started_at is not None:
            raise RuntimeError("heartbeat already started")
        if total is not None and (type(total) is not int or total < 0):
            raise ValueError("heartbeat total must be a non-negative integer or None")
        now = self.clock()
        self._started_at = now
        self._last_emitted_at = now
        self._total = total
        self.emit(self._event("stage.start", now, processed=0, skipped=0, failed=0))

    @property
    def counts(self) -> tuple[int, int, int]:
        """Return the latest cumulative processed, skipped, and failed counts."""
        return self._last_counts

    @property
    def is_terminal(self) -> bool:
        """Return whether a complete or incomplete event has already been emitted."""
        return self._terminal

    def advance(self, *, processed: int, skipped: int, failed: int) -> None:
        """Record one deterministic boundary and emit when the target interval elapsed."""
        now = self._require_active()
        self._validate_counts(processed, skipped, failed)
        self._last_counts = (processed, skipped, failed)
        assert self._last_emitted_at is not None
        if now - self._last_emitted_at < self.interval_seconds:
            return
        self.emit(
            self._event(
                "stage.heartbeat",
                now,
                processed=processed,
                skipped=skipped,
                failed=failed,
            )
        )
        self._last_emitted_at = now

    def finish(
        self,
        *,
        processed: int,
        skipped: int,
        failed: int,
        not_attempted: int = 0,
        artifact_bytes: int | None = None,
        peak_rss_bytes: int | None = None,
    ) -> None:
        """Emit the successful terminal totals and optional aggregate measurements."""
        if type(not_attempted) is not int or not_attempted < 0:
            raise ValueError("heartbeat not-attempted count must be a non-negative integer")
        if self._total is not None and processed + not_attempted != self._total:
            raise ValueError("completed heartbeat must account for its total")
        extra: ProgressEvent = {}
        if not_attempted:
            extra["not_attempted"] = not_attempted
        if artifact_bytes is not None:
            extra["artifact_bytes"] = artifact_bytes
        if peak_rss_bytes is not None:
            extra["peak_rss_bytes"] = peak_rss_bytes
        self._terminal_event(
            "stage.complete",
            processed=processed,
            skipped=skipped,
            failed=failed,
            extra=extra,
        )

    def incomplete(
        self,
        *,
        processed: int,
        skipped: int,
        failed: int,
        reason: str,
    ) -> None:
        """Emit aggregate progress for a handled stage failure."""
        if not reason:
            raise ValueError("incomplete heartbeat reason must not be empty")
        self._terminal_event(
            "stage.incomplete",
            processed=processed,
            skipped=skipped,
            failed=failed,
            extra={"reason": reason},
        )

    def _terminal_event(
        self,
        event: str,
        *,
        processed: int,
        skipped: int,
        failed: int,
        extra: ProgressEvent,
    ) -> None:
        now = self._require_active()
        self._validate_counts(processed, skipped, failed)
        self._last_counts = (processed, skipped, failed)
        self.emit(
            self._event(
                event,
                now,
                processed=processed,
                skipped=skipped,
                failed=failed,
                extra=extra,
            )
        )
        self._terminal = True

    def _require_active(self) -> float:
        if self._started_at is None:
            raise RuntimeError("heartbeat has not started")
        if self._terminal:
            raise RuntimeError("heartbeat is already terminal")
        return self.clock()

    def _validate_counts(self, processed: int, skipped: int, failed: int) -> None:
        counts = (processed, skipped, failed)
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("heartbeat counts must be non-negative integers")
        if any(
            current < previous for current, previous in zip(counts, self._last_counts, strict=True)
        ):
            raise ValueError("heartbeat counts must be monotonic")
        if self._total is not None and processed > self._total:
            raise ValueError("heartbeat processed count exceeds total")

    def _event(
        self,
        event: str,
        now: float,
        *,
        processed: int,
        skipped: int,
        failed: int,
        extra: ProgressEvent | None = None,
    ) -> ProgressEvent:
        assert self._started_at is not None
        elapsed = max(0.0, now - self._started_at)
        payload: ProgressEvent = {
            "event": event,
            "stage": self.stage,
            "total": self._total,
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "elapsed_seconds": elapsed,
            "rate_per_second": processed / elapsed if elapsed else 0.0,
        }
        if extra is not None:
            payload.update(extra)
        return payload


def emit_progress_to_log(event: ProgressEvent) -> None:
    """Adapt a progress mapping to structlog without changing its event name."""
    event_name = str(event["event"])
    fields = {key: value for key, value in event.items() if key != "event"}
    get_logger(__name__).info(event_name, **fields)


def new_run_id(now: datetime | None = None) -> str:
    """Mint a run-ID, e.g. ``run_20260706T142150Z_8f3a1c``.

    Sortable by start time, filesystem-safe, and unique enough for a
    single-user tool; recorded in artifacts and log lines alike (§18.5).
    """
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{stamp}_{secrets.token_hex(3)}"


def console_level(verbose: int, quiet: bool) -> int:
    """Map ``--verbose``/``--quiet`` to the console sink's level (OQ-017 table).

    quiet -> ERROR; default -> WARNING; -v -> INFO; -vv+ -> DEBUG. Flag
    exclusivity is enforced upstream by the CLI (IR-005), not here.
    """
    if quiet:
        return logging.ERROR
    if verbose >= 2:
        return logging.DEBUG
    if verbose == 1:
        return logging.INFO
    return logging.WARNING


def _uppercase_level(_logger: object, _name: str, event_dict: EventDict) -> EventDict:
    # The OQ-017 field schema uses stdlib's uppercase level names (DEBUG/INFO/...);
    # structlog's add_log_level emits lowercase, so normalize here.
    if "level" in event_dict:
        event_dict["level"] = str(event_dict["level"]).upper()
    return event_dict


def configure_logging(
    *,
    run_id: str,
    command: str,
    log_dir: Path,
    verbose: int = 0,
    quiet: bool = False,
) -> Path:
    """Wire structlog through stdlib handlers for one run; return the log file path.

    Idempotent per process: replaces the root logger's handlers rather than
    appending, so a re-configure (tests, future in-process reuse) never
    double-writes lines.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"docmend-{run_id}.jsonl"

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts")
    # Shared by structlog-native and foreign (stdlib) log records so both sinks
    # see an identical field schema.
    pre_chain: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        _uppercase_level,
        timestamper,
    ]

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # DEBUG floor, never governed by flags (OQ-017)
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.dict_tracebacks,  # exc_info as data, keeps lines valid JSON
                structlog.processors.JSONRenderer(),
            ],
            foreign_pre_chain=pre_chain,
        )
    )

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(console_level(verbose, quiet))
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(),  # rich-rendered tracebacks when a TTY
            ],
            foreign_pre_chain=pre_chain,
        )
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = [file_handler, console_handler]

    structlog.configure(
        processors=[
            *pre_chain,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,  # reconfiguration must take effect (tests, reuse)
    )
    # Every subsequent log call in this run carries the correlation fields
    # automatically — including across thread/async boundaries (contextvars).
    structlog.contextvars.bind_contextvars(run_id=run_id, command=command)

    return log_path


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Project-standard accessor so call sites never import structlog directly."""
    return structlog.stdlib.get_logger(name)
