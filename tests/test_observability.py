"""Logging framework tests — spec NFR-003, OQ-017 (MS-0 item 3: run-ID/log conventions).

Traceability (spec: NFR-003): per-run correlation fields on every line; a run is
diagnosable from its JSONL file regardless of console verbosity flags.
"""

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
import structlog

from docmend.observability import (
    ProgressHeartbeat,
    configure_logging,
    console_level,
    get_logger,
    new_run_id,
)

RUN_ID_RE = re.compile(r"^run_\d{8}T\d{6}Z_[0-9a-f]{6}$")


@dataclass
class FakeClock:
    now: float = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture(autouse=True)
def isolate_logging() -> Iterator[None]:
    """Restore global logging/structlog state; configure_logging mutates both."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    for handler in root.handlers:
        if handler not in saved_handlers:
            handler.close()
    root.handlers = saved_handlers
    root.setLevel(saved_level)
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


class TestRunId:
    def test_format__sortable_timestamp_plus_entropy(self) -> None:
        assert RUN_ID_RE.match(new_run_id())

    def test_timestamp_part__is_utc_of_given_instant(self) -> None:
        instant = datetime(2026, 7, 6, 14, 21, 50, tzinfo=UTC)
        assert new_run_id(instant).startswith("run_20260706T142150Z_")

    def test_two_ids_same_instant__differ(self) -> None:
        instant = datetime(2026, 7, 6, tzinfo=UTC)
        assert new_run_id(instant) != new_run_id(instant)


class TestConsoleLevelMapping:
    """The OQ-017 verbosity table: quiet=ERROR, default=WARNING, -v=INFO, -vv=DEBUG."""

    @pytest.mark.parametrize(
        ("verbose", "quiet", "expected"),
        [
            (0, True, logging.ERROR),
            (0, False, logging.WARNING),
            (1, False, logging.INFO),
            (2, False, logging.DEBUG),
            (5, False, logging.DEBUG),
        ],
    )
    def test_mapping(self, verbose: int, quiet: bool, expected: int) -> None:
        assert console_level(verbose, quiet) == expected


class TestConfigureLogging:
    def test_log_file__named_by_run_id_in_log_dir(self, tmp_path: Path) -> None:
        run_id = new_run_id()
        log_path = configure_logging(run_id=run_id, command="scan", log_dir=tmp_path / "logs")
        assert log_path == tmp_path / "logs" / f"docmend-{run_id}.jsonl"
        assert log_path.parent.is_dir()

    def test_jsonl_lines__carry_correlation_field_schema(self, tmp_path: Path) -> None:
        """Every line is valid JSON with ts/level/run_id/command/event (NFR-003)."""
        run_id = new_run_id()
        log_path = configure_logging(run_id=run_id, command="scan", log_dir=tmp_path)
        get_logger("test").warning("file.skipped", path="a.txt", reason="low_confidence_encoding")

        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["run_id"] == run_id
        assert record["command"] == "scan"
        assert record["event"] == "file.skipped"
        assert record["level"] == "WARNING"
        assert record["reason"] == "low_confidence_encoding"
        # ts is ISO 8601 UTC per the OQ-017 field schema
        assert datetime.fromisoformat(record["ts"]).tzinfo is not None

    def test_file_sink__debug_floored_even_when_quiet(self, tmp_path: Path) -> None:
        """OQ-017's deliberate asymmetry: --quiet never silences the file record."""
        log_path = configure_logging(
            run_id=new_run_id(), command="apply", log_dir=tmp_path, quiet=True
        )
        get_logger("test").debug("transform.decision", detail="x")

        [line] = log_path.read_text(encoding="utf-8").splitlines()
        assert json.loads(line)["level"] == "DEBUG"

    def test_console_handler__level_follows_flags(self, tmp_path: Path) -> None:
        configure_logging(run_id=new_run_id(), command="scan", log_dir=tmp_path, verbose=1)
        stream_handlers: list[logging.Handler] = [
            h
            for h in logging.getLogger().handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert [h.level for h in stream_handlers] == [logging.INFO]

    def test_reconfigure__replaces_handlers_never_stacks(self, tmp_path: Path) -> None:
        configure_logging(run_id=new_run_id(), command="scan", log_dir=tmp_path)
        configure_logging(run_id=new_run_id(), command="plan", log_dir=tmp_path)
        assert len(logging.getLogger().handlers) == 2  # one file + one console

    def test_stdlib_records__share_the_field_schema(self, tmp_path: Path) -> None:
        """Foreign (plain stdlib logging) records pass through the same processors,
        so third-party library logs stay correlated to the run."""
        run_id = new_run_id()
        log_path = configure_logging(run_id=run_id, command="verify", log_dir=tmp_path)
        logging.getLogger("somelib").warning("external event")

        [line] = log_path.read_text(encoding="utf-8").splitlines()
        record = json.loads(line)
        assert record["run_id"] == run_id
        assert record["event"] == "external event"


class TestProgressHeartbeat:
    def test_lifecycle__emits_aggregate_only_start_heartbeat_and_complete(self) -> None:
        clock = FakeClock()
        emitted: list[dict[str, object]] = []
        heartbeat = ProgressHeartbeat(stage="scan", emit=emitted.append, clock=clock)

        heartbeat.start(total=100)
        clock.advance(29.9)
        heartbeat.advance(processed=4, skipped=1, failed=0)
        assert [event["event"] for event in emitted] == ["stage.start"]

        clock.advance(0.1)
        heartbeat.advance(processed=5, skipped=1, failed=0)
        heartbeat.finish(processed=100, skipped=2, failed=1, artifact_bytes=4_096)

        assert [event["event"] for event in emitted] == [
            "stage.start",
            "stage.heartbeat",
            "stage.complete",
        ]
        assert emitted[1] == {
            "event": "stage.heartbeat",
            "stage": "scan",
            "total": 100,
            "processed": 5,
            "skipped": 1,
            "failed": 0,
            "elapsed_seconds": 30.0,
            "rate_per_second": pytest.approx(1 / 6),
        }
        assert emitted[-1]["artifact_bytes"] == 4_096
        assert not (
            {"path", "detail", "content"} & set().union(*(event.keys() for event in emitted))
        )

    def test_incomplete__is_terminal_and_carries_handled_failure_totals(self) -> None:
        clock = FakeClock()
        emitted: list[dict[str, object]] = []
        heartbeat = ProgressHeartbeat(stage="apply", emit=emitted.append, clock=clock)

        heartbeat.start(total=10)
        clock.advance(3)
        heartbeat.incomplete(processed=2, skipped=0, failed=1, reason="write-refused")

        assert emitted[-1] == {
            "event": "stage.incomplete",
            "stage": "apply",
            "total": 10,
            "processed": 2,
            "skipped": 0,
            "failed": 1,
            "elapsed_seconds": 3.0,
            "rate_per_second": pytest.approx(2 / 3),
            "reason": "write-refused",
        }
        with pytest.raises(RuntimeError, match="terminal"):
            heartbeat.advance(processed=3, skipped=0, failed=1)

    def test_native_stall__cannot_emit_until_control_reaches_record_boundary(self) -> None:
        clock = FakeClock()
        emitted: list[dict[str, object]] = []
        heartbeat = ProgressHeartbeat(stage="verify", emit=emitted.append, clock=clock)

        heartbeat.start(total=None)
        clock.advance(90)
        assert [event["event"] for event in emitted] == ["stage.start"]

        heartbeat.advance(processed=1, skipped=0, failed=0)
        assert emitted[-1]["event"] == "stage.heartbeat"
        assert emitted[-1]["elapsed_seconds"] == 90.0
