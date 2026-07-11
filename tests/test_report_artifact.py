"""Report artifact round-trip and schema conformance (DR-003, FR-018, IR-007)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from docmend import artifacts
from docmend.artifacts import ArtifactError
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


def test_report_snapshot__model_and_hash_come_from_one_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "report.json"
    report = _report()
    artifacts.write_report(report, out)
    reads = 0
    real_read_bytes = Path.read_bytes

    def read_once(path: Path) -> bytes:
        nonlocal reads
        reads += 1
        if reads > 1:
            raise AssertionError("report snapshot read more than once")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    loaded, digest = artifacts.read_report_snapshot(out)
    assert loaded == report
    assert digest == "sha256:" + __import__("hashlib").sha256(real_read_bytes(out)).hexdigest()
    assert reads == 1


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


class TestReadFailureModes:
    """ERR-008 family: invalid artifacts refuse loudly, with the cause named (DR-003)."""

    def test_missing_file(self, tmp_path: Path) -> None:
        """Missing file raises ArtifactError with "cannot read" message."""
        with pytest.raises(ArtifactError, match="cannot read"):
            artifacts.read_report(tmp_path / "absent.json")

    def test_not_json(self, tmp_path: Path) -> None:
        """Invalid JSON raises ArtifactError with "not valid JSON" message."""
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")
        with pytest.raises(ArtifactError, match="not valid JSON"):
            artifacts.read_report(bad)

    def test_unknown_field_rejected(self, tmp_path: Path) -> None:
        """adr-0005 strictness: additionalProperties:false rejects drift (DR-003)."""
        out = tmp_path / "report.json"
        artifacts.write_report(_report(), out)
        document = json.loads(out.read_text(encoding="utf-8"))
        document["surprise"] = True
        out.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ArtifactError, match="surprise"):
            artifacts.read_report(out)

    def test_wrong_schema_kind_rejected(self, tmp_path: Path) -> None:
        """Wrong schema kind (e.g. docmend/plan) is rejected (DR-003)."""
        out = tmp_path / "report.json"
        artifacts.write_report(_report(), out)
        document = json.loads(out.read_text(encoding="utf-8"))
        document["schema"] = "docmend/plan"
        out.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ArtifactError, match="schema"):
            artifacts.read_report(out)
