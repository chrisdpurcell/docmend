"""Report artifact round-trip and schema conformance (DR-003, FR-018, IR-007)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from docmend import artifacts
from docmend.plan import ArtifactRef
from docmend.report import ApplyOutcome, ErrorInfo, Report, ReportTotals

RUN_ID = "run_20260706T000000Z_00005c"
SHA = "sha256:" + "a" * 64


def _report() -> Report:
    return Report(
        run_id=RUN_ID,
        generated_by="docmend 0.1.0",
        plan_ref=ArtifactRef(path="plan.json", run_id=RUN_ID, sha256=SHA),
        dry_run=True,
        started_at="2026-07-06T00:00:00+00:00",
        completed_at="2026-07-06T00:00:01+00:00",
        outcomes=[
            ApplyOutcome(
                action_id=f"{RUN_ID}/a1",
                path="a.txt",
                status="would_apply",
                before_sha256=SHA,
                after_sha256=None,
                skip_reason=None,
                error=None,
            ),
            ApplyOutcome(
                action_id=f"{RUN_ID}/a2",
                path="b.txt",
                status="failed",
                before_sha256=SHA,
                after_sha256=None,
                skip_reason=None,
                error=ErrorInfo(error_class="ERR-003", message="disk full"),
            ),
        ],
        totals=ReportTotals(applied=0, would_apply=1, skipped=0, failed=1),
    )


def test_report_round_trip__write_read_identical(tmp_path: Path) -> None:
    """IR-007: write -> read -> identical model (DR-003)."""
    out = tmp_path / "report.json"
    artifacts.write_report(_report(), out)
    assert artifacts.read_report(out) == _report()


def test_report_serializes_wire_names__schema_and_class(tmp_path: Path) -> None:
    document = _report().model_dump(mode="json")
    assert document["schema"] == "docmend/report"
    assert document["outcomes"][1]["error"]["class"] == "ERR-003"
    artifacts.validate_artifact("report", document)


def test_error_class_pattern__rejected_when_malformed() -> None:
    with pytest.raises(ValidationError):
        ErrorInfo(error_class="oops", message="x")


def test_report_totals_mismatch__rejected_by_writer(tmp_path: Path) -> None:
    """DR-003: summary counts must equal per-outcome totals — enforced at write."""
    bad = _report().model_copy(
        update={"totals": ReportTotals(applied=9, would_apply=0, skipped=0, failed=0)}
    )
    with pytest.raises(artifacts.ArtifactError):
        artifacts.write_report(bad, tmp_path / "report.json")
