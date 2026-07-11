"""Verify engine unit tests (FR-014, adr-0012)."""

import hashlib
from collections import Counter
from pathlib import Path

from tests.helpers.manifest2 import chain_of, record_doc

from docmend.inventory import (
    Inventory,
    InventoryTotals,
    ScanConfigRecord,
    ScanSkipReason,
    SkippedByReason,
    SkipRecord,
    SymlinkRecord,
)
from docmend.plan import ArtifactRef
from docmend.report import ApplyOutcome, ErrorInfo, Report, ReportTotals
from docmend.verify import (
    check_backups,
    check_discovery,
    check_lifecycle,
    check_manifest_root,
    check_outputs,
    manifest_inspection_findings,
    reconcile_manifest,
    reconcile_report,
)
from docmend.writer.manifest import (
    ManifestChain,
    ManifestInspection,
    ManifestInspectionFinding,
    ManifestRecord,
)

RUN_ID = "run_20260707T000000Z_0000aa"
SHA_A = "sha256:" + "a" * 64
UUID7 = "01980000-0000-7000-8000-000000000001"


def _digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _inventory(
    *,
    root: Path,
    skips: tuple[ScanSkipReason, ...] = (),
    symlinks: int = 0,
) -> Inventory:
    skipped = [
        SkipRecord(path=f"skip-{index}.md", reason=reason, detail="synthetic")
        for index, reason in enumerate(skips, start=1)
    ]
    links = [
        SymlinkRecord(path=f"link-{index}.md", target="target.md", kind="file")
        for index in range(1, symlinks + 1)
    ]
    by_reason = Counter(skips)
    return Inventory(
        run_id=RUN_ID,
        generated_at="2026-07-07T00:00:00+00:00",
        generated_by="docmend test",
        requested_path=str(root),
        source_root=str(root),
        scan_config=ScanConfigRecord(include=["**/*.md"], exclude=["**/.docmend/**"]),
        files=[],
        symlinks=links,
        skipped=skipped,
        hard_link_groups=[],
        totals=InventoryTotals(
            files=0,
            symlinks=len(links),
            skipped=len(skipped),
            skipped_by_reason=SkippedByReason(
                excluded=by_reason["excluded"],
                unreadable=by_reason["unreadable"],
                timeout=by_reason["timeout"],
            ),
            hard_link_groups=0,
            total_size_bytes=0,
        ),
    )


def _record(action_seq: int = 1, **overrides: object) -> ManifestRecord:
    overrides.setdefault("run_id", RUN_ID)
    overrides.setdefault("action_id", f"{RUN_ID}/a{action_seq}")
    result = overrides.pop("result", "applied")
    assert isinstance(result, str)
    return ManifestRecord.model_validate(record_doc(action_seq, result=result, **overrides))


def test_discovery_unreadable_and_timeout__findings(tmp_path: Path) -> None:
    findings = check_discovery(_inventory(root=tmp_path, skips=("unreadable", "timeout")))
    assert {finding.check for finding in findings} == {
        "discovery-unreadable",
        "discovery-timeout",
        "zero-checked",
    }


def test_discovery_symlink_only__zero_checked_finding(tmp_path: Path) -> None:
    findings = check_discovery(_inventory(root=tmp_path, symlinks=1))
    assert [(finding.path, finding.check) for finding in findings] == [
        (str(tmp_path), "zero-checked")
    ]


def test_discovery_genuinely_empty__clean(tmp_path: Path) -> None:
    assert check_discovery(_inventory(root=tmp_path)) == []


def test_discovery_all_file_pattern_excluded__clean(tmp_path: Path) -> None:
    assert check_discovery(_inventory(root=tmp_path, skips=("excluded",))) == []


def test_discovery_excluded_directory_pruned__clean(tmp_path: Path) -> None:
    assert check_discovery(_inventory(root=tmp_path / "pruned")) == []


def test_manifest_root_mismatch__finding(tmp_path: Path) -> None:
    chain = chain_of([], source_root="/different-root")
    assert [(finding.check, finding.path) for finding in check_manifest_root(chain, tmp_path)] == [
        ("manifest-root", "/different-root")
    ]


def test_manifest_root_match_and_empty_chain__clean(tmp_path: Path) -> None:
    assert check_manifest_root(chain_of([], source_root=str(tmp_path)), tmp_path) == []
    assert check_manifest_root(ManifestChain(sets=()), tmp_path) == []


def test_manifest_inspection_findings__convert_without_path_reads() -> None:
    inspection = ManifestInspection(
        chain=chain_of([]),
        findings=(
            ManifestInspectionFinding(
                path="/outside/doc.md",
                action_id=f"{RUN_ID}/a1",
                check="manifest-containment",
                detail="outside the source root",
            ),
        ),
    )
    assert [
        (finding.path, finding.check, finding.detail)
        for finding in manifest_inspection_findings(inspection)
    ] == [("/outside/doc.md", "manifest-containment", "outside the source root")]


def test_dangling_intent__lifecycle_finding() -> None:
    chain = chain_of([_record(result="intent")])
    assert [(finding.check, finding.path) for finding in check_lifecycle(chain)] == [
        ("lifecycle", f"{RUN_ID}/a1")
    ]


def test_restore_states__lifecycle_findings() -> None:
    action_id = f"{RUN_ID}/a1"
    for result, expected_state in (
        ("intent", "pending-restore"),
        ("applied", "restored"),
        ("failed", "restore-failed"),
    ):
        restore = _record(
            2,
            result=result,
            undoes_action_id=action_id,
            undoes_run_id=RUN_ID,
        )
        findings = check_lifecycle(chain_of([restore]))
        assert [(finding.path, finding.detail) for finding in findings] == [
            (action_id, expected_state)
        ]


def test_applied_and_failed_states__no_lifecycle_finding() -> None:
    assert check_lifecycle(chain_of([_record(result="applied")])) == []
    assert check_lifecycle(chain_of([_record(result="failed", after_sha256=None)])) == []


def test_outputs__missing_changed_and_clean(tmp_path: Path) -> None:
    target = tmp_path / "doc.md"
    expected = b"expected\n"
    record = _record(target_path=str(target), after_sha256=_digest(expected))
    chain = chain_of([record], source_root=str(tmp_path))

    assert [(finding.check, finding.detail) for finding in check_outputs(chain)] == [
        ("hash", "applied output missing or unreadable")
    ]
    target.write_bytes(b"changed\n")
    assert [(finding.check, finding.detail) for finding in check_outputs(chain)] == [
        ("hash", "live hash does not match recorded after-hash")
    ]
    target.write_bytes(expected)
    assert check_outputs(chain) == []


def test_outputs__unsafe_or_restored_actions_are_not_read(tmp_path: Path) -> None:
    action_id = f"{RUN_ID}/a1"
    missing = tmp_path / "missing.md"
    applied = _record(target_path=str(missing), after_sha256=SHA_A)
    assert check_outputs(chain_of([applied]), unsafe_action_ids={action_id}) == []
    restored = _record(
        2,
        undoes_action_id=action_id,
        undoes_run_id=RUN_ID,
        target_path=str(missing),
    )
    assert check_outputs(chain_of([applied, restored])) == []


def test_source_backup__missing_corrupt_and_clean(tmp_path: Path) -> None:
    backup = tmp_path / "source.bak"
    expected = b"before\n"
    record = _record(backup_path=str(backup), before_sha256=_digest(expected))
    chain = chain_of([record])

    missing = check_backups(chain)
    assert [
        (finding.check, finding.detail.startswith("source backup missing")) for finding in missing
    ] == [("backup", True)]
    backup.write_bytes(b"corrupt\n")
    assert [(finding.check, finding.detail) for finding in check_backups(chain)] == [
        ("backup", "source backup hash does not match recorded before-hash")
    ]
    backup.write_bytes(expected)
    assert check_backups(chain) == []


def test_overwritten_backup__missing_corrupt_and_clean(tmp_path: Path) -> None:
    backup = tmp_path / "overwritten.bak"
    expected = b"overwritten\n"
    record = _record(
        overwritten_backup_path=str(backup),
        overwritten_sha256=_digest(expected),
    )
    chain = chain_of([record])

    missing = check_backups(chain)
    assert [finding.detail.startswith("overwritten backup missing") for finding in missing] == [
        True
    ]
    backup.write_bytes(b"corrupt\n")
    assert [(finding.check, finding.detail) for finding in check_backups(chain)] == [
        ("backup", "overwritten backup hash does not match recorded overwritten-hash")
    ]
    backup.write_bytes(expected)
    assert check_backups(chain) == []


def test_backups__unsafe_action_is_not_read(tmp_path: Path) -> None:
    action_id = f"{RUN_ID}/a1"
    record = _record(backup_path=str(tmp_path / "missing.bak"))
    assert check_backups(chain_of([record]), unsafe_action_ids={action_id}) == []


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
