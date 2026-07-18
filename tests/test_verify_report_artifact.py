"""Verify-report artifact round-trip and schema conformance (FR-014, IR-007)."""

import json
from pathlib import Path

import pytest

from docmend import artifacts
from docmend.verify_report import VerificationInput, VerifyFindingRecord, VerifyReport

RUN_ID = "run_20260711T120000Z_0000aa"
SHA = "sha256:" + "a" * 64


def _report(*, clean: bool = False) -> VerifyReport:
    findings = (
        []
        if clean
        else [
            VerifyFindingRecord(
                path="synthetic/doc.md",
                check="hash",
                detail="mismatch",
            )
        ]
    )
    return VerifyReport(
        run_id=RUN_ID,
        generated_by="docmend test",
        verified_path="synthetic",
        source_root="/synthetic",
        started_at="2026-07-11T12:00:00+00:00",
        completed_at="2026-07-11T12:00:01+00:00",
        inputs=[
            VerificationInput(
                kind="plan",
                path="plan.json",
                run_id=RUN_ID,
                sha256=SHA,
            )
        ],
        checked_files=1,
        findings=findings,
        clean=clean,
    )


def test_verify_report_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "verify.json"
    report = _report()
    artifacts.write_verify_report(report, path)
    assert artifacts.read_verify_report(path) == report


def test_verify_report_serializes_wire_schema_name() -> None:
    document = _report().model_dump(mode="json")
    assert document["schema"] == "docmend/verify-report"
    artifacts.validate_artifact("verify-report", document)


def test_verify_report_clean_must_reconcile(tmp_path: Path) -> None:
    report = _report().model_copy(update={"clean": True})
    with pytest.raises(artifacts.ArtifactError, match="clean verdict"):
        artifacts.write_verify_report(report, tmp_path / "x.json")


def test_read_verify_report_clean_must_reconcile(tmp_path: Path) -> None:
    path = tmp_path / "verify.json"
    document = _report().model_dump(mode="json")
    document["clean"] = True
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(artifacts.ArtifactError, match="clean verdict"):
        artifacts.read_verify_report(path)


@pytest.mark.parametrize("payload", [b"{not json", b"\xff"])
def test_read_verify_report_rejects_unreadable_payload(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "verify.json"
    path.write_bytes(payload)
    with pytest.raises(artifacts.ArtifactError, match="cannot read verify-report"):
        artifacts.read_verify_report(path)
