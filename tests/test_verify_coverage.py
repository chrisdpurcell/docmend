"""Attempt-lineage loading and plan-coverage reduction (FR-014, IR-004)."""

from collections import Counter
from pathlib import Path

import pytest
from tests.helpers.manifest2 import SHA_A, SHA_B, header_doc, record_doc, write_set

from docmend import artifacts
from docmend.artifacts import ArtifactError
from docmend.config import DocmendConfig
from docmend.lineage import PriorAttempt
from docmend.plan import ArtifactRef, Plan, PlanTotals
from docmend.report import ApplyOutcome, Report, ReportTotals
from docmend.verify_coverage import load_verification_evidence
from docmend.writer.manifest import manifest_sha256

PLAN_RUN = "run_20260711T100000Z_000001"
RUN_1 = "run_20260711T110000Z_000011"
RUN_2 = "run_20260711T120000Z_000022"
RUN_3 = "run_20260711T130000Z_000033"
RUN_4 = "run_20260711T140000Z_000044"
ACTION_1 = f"{PLAN_RUN}/a1"
TIMESTAMP = "2026-07-11T10:00:00+00:00"


def _write_plan(path: Path) -> tuple[Path, str]:
    plan = Plan(
        run_id=PLAN_RUN,
        generated_at=TIMESTAMP,
        generated_by="docmend test",
        inventory_ref=ArtifactRef(path="inventory.json", run_id=PLAN_RUN, sha256=SHA_A),
        source_root="/synthetic",
        config=DocmendConfig().model_dump(mode="json"),
        actions=[],
        skips=[],
        totals=PlanTotals(actions=0, skips=0),
    )
    artifacts.write_plan(plan, path)
    return path, artifacts.read_plan_snapshot(path)[1]


def _write_report(
    path: Path,
    *,
    run_id: str,
    plan_sha256: str,
    prior_attempt: PriorAttempt | None = None,
    manifest_sha256_value: str | None = None,
    outcomes: tuple[ApplyOutcome, ...] = (),
) -> Path:
    counts = Counter(outcome.status for outcome in outcomes)
    report = Report(
        run_id=run_id,
        generated_by="docmend test",
        plan_ref=ArtifactRef(path="plan.json", run_id=PLAN_RUN, sha256=plan_sha256),
        dry_run=False,
        started_at=TIMESTAMP,
        completed_at=TIMESTAMP,
        outcomes=list(outcomes),
        totals=ReportTotals(
            applied=counts["applied"],
            would_apply=counts["would_apply"],
            skipped=counts["skipped"],
            failed=counts["failed"],
            not_attempted=counts["not-attempted"],
        ),
        prior_attempt=prior_attempt,
        manifest_sha256=manifest_sha256_value,
    )
    artifacts.write_report(report, path)
    return path


def _write_manifest(
    path: Path,
    *,
    run_id: str,
    plan_sha256: str,
    source_root: Path,
    prior_manifest_sha256: str | None = None,
    prior_attempt: PriorAttempt | None = None,
    kind: str = "apply",
    mutation: bool = False,
) -> tuple[Path, str]:
    header = header_doc(
        run_id=run_id,
        kind=kind,
        source_root=str(source_root),
        plan_sha256=plan_sha256,
        prior_manifest_sha256=prior_manifest_sha256,
        prior_attempt=None if prior_attempt is None else prior_attempt.model_dump(mode="json"),
    )
    records: list[dict[str, object]] = []
    if mutation:
        records = [
            record_doc(
                1,
                result="intent",
                run_id=run_id,
                action_id=ACTION_1,
                original_path=str(source_root / "doc.md"),
                target_path=str(source_root / "doc.md"),
            ),
            record_doc(
                1,
                seq=2,
                run_id=run_id,
                action_id=ACTION_1,
                original_path=str(source_root / "doc.md"),
                target_path=str(source_root / "doc.md"),
            ),
        ]
    write_set(path, header, *records)
    return path, manifest_sha256(path)


def _report_hash(path: Path) -> str:
    return artifacts.read_report_snapshot(path)[1]


def _applied_outcome() -> ApplyOutcome:
    return ApplyOutcome(
        action_id=ACTION_1,
        path="doc.md",
        status="applied",
        before_sha256=SHA_A,
        after_sha256=SHA_B,
        skip_reason=None,
        error=None,
    )


def test_report_only_applied_claim__is_accounting_finding(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path / "r1.json",
        run_id=RUN_1,
        plan_sha256=SHA_A,
        outcomes=(_applied_outcome(),),
    )
    evidence = load_verification_evidence(None, [], [report])
    assert [(finding.path, finding.check) for finding in evidence.findings] == [
        (ACTION_1, "accounting")
    ]


def test_manifest_applied_action_omitted_from_present_report__is_accounting_finding(
    tmp_path: Path,
) -> None:
    manifest, manifest_sha = _write_manifest(
        tmp_path / "m1.jsonl",
        run_id=RUN_1,
        plan_sha256=SHA_A,
        source_root=tmp_path,
        mutation=True,
    )
    report = _write_report(
        tmp_path / "r1.json",
        run_id=RUN_1,
        plan_sha256=SHA_A,
        manifest_sha256_value=manifest_sha,
    )
    evidence = load_verification_evidence(None, [manifest], [report])
    assert [(finding.path, finding.check) for finding in evidence.findings] == [
        (ACTION_1, "accounting")
    ]


def test_shuffled_report_only_then_normal_attempt__orders_by_lineage(tmp_path: Path) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    r1 = _write_report(tmp_path / "r1.json", run_id=RUN_1, plan_sha256=plan_sha)
    edge = PriorAttempt(run_id=RUN_1, report_sha256=_report_hash(r1), manifest_sha256=None)
    m2, m2_sha = _write_manifest(
        tmp_path / "m2.jsonl",
        run_id=RUN_2,
        plan_sha256=plan_sha,
        source_root=tmp_path,
        prior_attempt=edge,
    )
    r2 = _write_report(
        tmp_path / "r2.json",
        run_id=RUN_2,
        plan_sha256=plan_sha,
        prior_attempt=edge,
        manifest_sha256_value=m2_sha,
    )

    evidence = load_verification_evidence(plan_path, [m2], [r2, r1])

    assert [attempt.run_id for attempt in evidence.attempts] == [RUN_1, RUN_2]
    assert evidence.findings == ()


def test_manifest_missing_report_then_normal_retry__orders_and_finds_gap(tmp_path: Path) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    m1, m1_sha = _write_manifest(
        tmp_path / "m1.jsonl",
        run_id=RUN_1,
        plan_sha256=plan_sha,
        source_root=tmp_path,
        mutation=True,
    )
    edge = PriorAttempt(run_id=RUN_1, report_sha256=None, manifest_sha256=m1_sha)
    m2, m2_sha = _write_manifest(
        tmp_path / "m2.jsonl",
        run_id=RUN_2,
        plan_sha256=plan_sha,
        source_root=tmp_path,
        prior_manifest_sha256=m1_sha,
        prior_attempt=edge,
    )
    r2 = _write_report(
        tmp_path / "r2.json",
        run_id=RUN_2,
        plan_sha256=plan_sha,
        prior_attempt=edge,
        manifest_sha256_value=m2_sha,
    )

    evidence = load_verification_evidence(plan_path, [m2, m1], [r2])

    assert [attempt.run_id for attempt in evidence.attempts] == [RUN_1, RUN_2]
    assert [(finding.path, finding.check) for finding in evidence.findings] == [
        (RUN_1, "coverage-unprovable")
    ]


def test_composed_lineage__orders_all_shapes_from_shuffled_inputs(tmp_path: Path) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    r1 = _write_report(tmp_path / "r1.json", run_id=RUN_1, plan_sha256=plan_sha)
    edge_2 = PriorAttempt(run_id=RUN_1, report_sha256=_report_hash(r1), manifest_sha256=None)
    m2, m2_sha = _write_manifest(
        tmp_path / "m2.jsonl",
        run_id=RUN_2,
        plan_sha256=plan_sha,
        source_root=tmp_path,
        prior_attempt=edge_2,
        mutation=True,
    )
    edge_3 = PriorAttempt(run_id=RUN_2, report_sha256=None, manifest_sha256=m2_sha)
    m3, m3_sha = _write_manifest(
        tmp_path / "m3.jsonl",
        run_id=RUN_3,
        plan_sha256=plan_sha,
        source_root=tmp_path,
        prior_manifest_sha256=m2_sha,
        prior_attempt=edge_3,
    )
    r3 = _write_report(
        tmp_path / "r3.json",
        run_id=RUN_3,
        plan_sha256=plan_sha,
        prior_attempt=edge_3,
        manifest_sha256_value=m3_sha,
    )

    evidence = load_verification_evidence(plan_path, [m3, m2], [r3, r1])

    assert [attempt.run_id for attempt in evidence.attempts] == [RUN_1, RUN_2, RUN_3]
    assert any(
        finding.check == "coverage-unprovable" and finding.path == RUN_2
        for finding in evidence.findings
    )


def test_apply_restore_chain__restore_orders_last_without_missing_report_finding(
    tmp_path: Path,
) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    m1, m1_sha = _write_manifest(
        tmp_path / "m1.jsonl",
        run_id=RUN_1,
        plan_sha256=plan_sha,
        source_root=tmp_path,
    )
    r1 = _write_report(
        tmp_path / "r1.json",
        run_id=RUN_1,
        plan_sha256=plan_sha,
        manifest_sha256_value=m1_sha,
    )
    restore_edge = PriorAttempt(
        run_id=RUN_1,
        report_sha256=None,
        manifest_sha256=m1_sha,
    )
    m2, _ = _write_manifest(
        tmp_path / "restore.jsonl",
        run_id=RUN_2,
        plan_sha256=plan_sha,
        source_root=tmp_path,
        prior_manifest_sha256=m1_sha,
        prior_attempt=restore_edge,
        kind="restore",
    )

    evidence = load_verification_evidence(plan_path, [m2, m1], [r1])

    assert [(attempt.run_id, attempt.kind) for attempt in evidence.attempts] == [
        (RUN_1, "apply"),
        (RUN_2, "restore"),
    ]
    assert not any(finding.check == "coverage-unprovable" for finding in evidence.findings)


def test_report_claiming_restore_run__is_structural_contradiction(tmp_path: Path) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    m1, m1_sha = _write_manifest(
        tmp_path / "m1.jsonl",
        run_id=RUN_1,
        plan_sha256=plan_sha,
        source_root=tmp_path,
    )
    edge = PriorAttempt(run_id=RUN_1, report_sha256=None, manifest_sha256=m1_sha)
    m2, m2_sha = _write_manifest(
        tmp_path / "restore.jsonl",
        run_id=RUN_2,
        plan_sha256=plan_sha,
        source_root=tmp_path,
        prior_manifest_sha256=m1_sha,
        prior_attempt=edge,
        kind="restore",
    )
    impossible = _write_report(
        tmp_path / "restore-report.json",
        run_id=RUN_2,
        plan_sha256=plan_sha,
        prior_attempt=edge,
        manifest_sha256_value=m2_sha,
    )

    with pytest.raises(ArtifactError, match="restore"):
        load_verification_evidence(plan_path, [m1, m2], [impossible])


def test_supplied_plan_with_no_attempts__is_legal_empty_graph(tmp_path: Path) -> None:
    plan_path, _ = _write_plan(tmp_path / "plan.json")
    evidence = load_verification_evidence(plan_path, [], [])
    assert evidence.attempts == ()
    assert evidence.findings == ()


def test_duplicate_report_for_run__is_input_error(tmp_path: Path) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    r1 = _write_report(tmp_path / "r1.json", run_id=RUN_1, plan_sha256=plan_sha)
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(r1.read_bytes())
    with pytest.raises(ArtifactError, match="more than one report"):
        load_verification_evidence(plan_path, [], [r1, duplicate])


def test_report_header_prior_attempt_disagreement__is_input_error(tmp_path: Path) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    r1 = _write_report(tmp_path / "r1.json", run_id=RUN_1, plan_sha256=plan_sha)
    edge = PriorAttempt(run_id=RUN_1, report_sha256=_report_hash(r1), manifest_sha256=None)
    m2, m2_sha = _write_manifest(
        tmp_path / "m2.jsonl",
        run_id=RUN_2,
        plan_sha256=plan_sha,
        source_root=tmp_path,
        prior_attempt=edge,
    )
    disagreeing = _write_report(
        tmp_path / "r2.json",
        run_id=RUN_2,
        plan_sha256=plan_sha,
        prior_attempt=None,
        manifest_sha256_value=m2_sha,
    )
    with pytest.raises(ArtifactError, match="prior_attempt"):
        load_verification_evidence(plan_path, [m2], [r1, disagreeing])


def test_report_manifest_sha_disagreement__is_input_error(tmp_path: Path) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    m1, _ = _write_manifest(
        tmp_path / "m1.jsonl",
        run_id=RUN_1,
        plan_sha256=plan_sha,
        source_root=tmp_path,
    )
    report = _write_report(
        tmp_path / "r1.json",
        run_id=RUN_1,
        plan_sha256=plan_sha,
        manifest_sha256_value=SHA_B,
    )
    with pytest.raises(ArtifactError, match="manifest_sha256"):
        load_verification_evidence(plan_path, [m1], [report])


def test_plan_report_header_hash_mismatch__is_binding_finding(tmp_path: Path) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    m1, m1_sha = _write_manifest(
        tmp_path / "m1.jsonl",
        run_id=RUN_1,
        plan_sha256=SHA_B,
        source_root=tmp_path,
    )
    report = _write_report(
        tmp_path / "r1.json",
        run_id=RUN_1,
        plan_sha256=plan_sha,
        manifest_sha256_value=m1_sha,
    )
    evidence = load_verification_evidence(plan_path, [m1], [report])
    assert [(finding.path, finding.check) for finding in evidence.findings] == [
        (RUN_1, "coverage-binding")
    ]


def test_unresolved_predecessor_report_hash__is_input_error(tmp_path: Path) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    edge = PriorAttempt(run_id=RUN_1, report_sha256=SHA_A, manifest_sha256=None)
    r2 = _write_report(
        tmp_path / "r2.json",
        run_id=RUN_2,
        plan_sha256=plan_sha,
        prior_attempt=edge,
    )
    with pytest.raises(ArtifactError, match="predecessor"):
        load_verification_evidence(plan_path, [], [r2])


def test_two_roots__is_input_error(tmp_path: Path) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    r1 = _write_report(tmp_path / "r1.json", run_id=RUN_1, plan_sha256=plan_sha)
    r2 = _write_report(tmp_path / "r2.json", run_id=RUN_2, plan_sha256=plan_sha)
    with pytest.raises(ArtifactError, match="exactly one root"):
        load_verification_evidence(plan_path, [], [r2, r1])


def test_two_tips_after_one_root__is_fork_error(tmp_path: Path) -> None:
    plan_path, plan_sha = _write_plan(tmp_path / "plan.json")
    r1 = _write_report(tmp_path / "r1.json", run_id=RUN_1, plan_sha256=plan_sha)
    edge = PriorAttempt(run_id=RUN_1, report_sha256=_report_hash(r1), manifest_sha256=None)
    r2 = _write_report(tmp_path / "r2.json", run_id=RUN_2, plan_sha256=plan_sha, prior_attempt=edge)
    r3 = _write_report(tmp_path / "r3.json", run_id=RUN_3, plan_sha256=plan_sha, prior_attempt=edge)
    with pytest.raises(ArtifactError, match="forks"):
        load_verification_evidence(plan_path, [], [r3, r1, r2])
