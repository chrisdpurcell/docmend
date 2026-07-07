"""verify engine unit tests (FR-014, adr-0012) — the parts the CLI journey in
tests/test_cli_verify.py does not isolate cleanly.
"""

from collections import Counter

from docmend.plan import ArtifactRef
from docmend.report import ApplyOutcome, ErrorInfo, Report, ReportTotals
from docmend.verify import reconcile_manifest, reconcile_report
from docmend.writer.manifest import ManifestRecord

RUN_ID = "run_20260707T000000Z_0000aa"
SHA_A = "sha256:" + "a" * 64
UUID7 = "01980000-0000-7000-8000-000000000001"


def test_reconcile_skips_failed_records() -> None:
    """A result=='failed' record left the original untouched (spec 10.4), so there
    is no applied output to reconcile — reconcile must not manufacture a finding
    (and must not touch the filesystem for it)."""
    failed = ManifestRecord(
        run_id=RUN_ID,
        action_id=f"{RUN_ID}/a1",
        docmend_id=UUID7,
        seq=1,
        recorded_at="2026-07-07T00:00:00+00:00",
        operation="rewrite",
        original_path="/nonexistent/a.txt",
        target_path="/nonexistent/a.txt",
        backup_path=None,
        before_sha256=SHA_A,
        after_sha256=None,
        result="failed",
        error=ErrorInfo(error_class="ERR-003", message="boom"),
    )

    assert reconcile_manifest([failed]) == []


def _applied_record(action_id: str, seq: int = 1) -> ManifestRecord:
    return ManifestRecord(
        run_id=RUN_ID,
        action_id=action_id,
        docmend_id=UUID7,
        seq=seq,
        recorded_at="2026-07-07T00:00:00+00:00",
        operation="rewrite",
        original_path="/x/a.txt",
        target_path="/x/a.txt",
        backup_path=None,
        before_sha256=SHA_A,
        after_sha256=SHA_A,
        result="applied",
        error=None,
    )


def _report(outcomes: list[ApplyOutcome]) -> Report:
    counts = Counter(o.status for o in outcomes)
    return Report(
        run_id=RUN_ID,
        generated_by="docmend test",
        plan_ref=ArtifactRef(path="plan.json", run_id=RUN_ID, sha256=SHA_A),
        dry_run=False,
        started_at="2026-07-07T00:00:00+00:00",
        completed_at="2026-07-07T00:00:01+00:00",
        outcomes=outcomes,
        totals=ReportTotals(
            applied=counts.get("applied", 0),
            would_apply=0,
            skipped=counts.get("skipped", 0),
            failed=counts.get("failed", 0),
        ),
    )


def _applied_outcome(action_id: str) -> ApplyOutcome:
    return ApplyOutcome(
        action_id=action_id,
        path="a.txt",
        status="applied",
        before_sha256=SHA_A,
        after_sha256=SHA_A,
        skip_reason=None,
        error=None,
    )


def test_reconcile_report_clean__no_findings() -> None:
    a1 = f"{RUN_ID}/a1"
    assert reconcile_report(_report([_applied_outcome(a1)]), [_applied_record(a1)]) == []


def test_reconcile_report_mismatch__both_directions_found() -> None:
    """FR-014 accounting: applied-in-report-only and applied-in-manifest-only
    each surface as their own finding."""
    only_report = f"{RUN_ID}/a1"
    only_manifest = f"{RUN_ID}/a2"
    findings = reconcile_report(
        _report([_applied_outcome(only_report)]), [_applied_record(only_manifest)]
    )
    assert {(f.path, f.check) for f in findings} == {
        (only_report, "accounting"),
        (only_manifest, "accounting"),
    }


def test_reconcile_ignores_intent_records() -> None:
    """A 1.3 intent record is a write-ahead marker, not an applied output:
    reconcile_manifest must not hash-check its target (which may not exist),
    and reconcile_report must not count it toward applied accounting — a
    manifest whose intent is closed by an applied record reconciles clean."""
    a1 = f"{RUN_ID}/a1"
    intent = _applied_record(a1, 1).model_copy(
        update={"result": "intent", "target_path": "/nonexistent/never-published.md"}
    )
    assert reconcile_manifest([intent]) == []
    findings = reconcile_report(_report([_applied_outcome(a1)]), [intent, _applied_record(a1, 2)])
    assert findings == []


def test_reconcile_report_duplicate_applied_record__found() -> None:
    """A duplicate applied record for one action would slip past pure set
    comparison; it must surface explicitly."""
    a1 = f"{RUN_ID}/a1"
    findings = reconcile_report(
        _report([_applied_outcome(a1)]), [_applied_record(a1, 1), _applied_record(a1, 2)]
    )
    assert [(f.path, f.check) for f in findings] == [(a1, "accounting")]
    assert "duplicate" in findings[0].detail
