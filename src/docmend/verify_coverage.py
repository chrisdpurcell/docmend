"""Attempt-lineage loading and exactly-once plan certification (FR-014).

Artifact identity and lineage contradictions are input errors because they
prevent deterministic ordering. Once the graph is orderable, missing or
inconsistent certification evidence is returned as a verify finding.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from docmend import artifacts
from docmend.artifacts import ArtifactError
from docmend.lineage import PriorAttempt
from docmend.plan import Plan
from docmend.report import ApplyOutcome, Report
from docmend.verify import VerifyFinding
from docmend.verify_report import VerificationInput
from docmend.writer.manifest import (
    ManifestInspection,
    ManifestSet,
    inspect_manifest_chain,
    reduce_lifecycle,
)


@dataclass(frozen=True)
class AttemptEvidence:
    run_id: str
    kind: Literal["apply", "restore"]
    prior_attempt: PriorAttempt | None
    manifest_set: ManifestSet | None
    report: Report | None
    report_sha256: str | None


@dataclass(frozen=True)
class VerificationEvidence:
    plan: Plan | None
    plan_sha256: str | None
    manifest_inspection: ManifestInspection
    attempts: tuple[AttemptEvidence, ...]
    inputs: tuple[VerificationInput, ...]
    findings: tuple[VerifyFinding, ...]


type CertifiedOutcome = Literal["applied", "failed", "skipped", "not-attempted"]
type ReportObservation = Literal["applied", "failed", "skipped", "not-attempted", "already-applied"]


@dataclass(frozen=True)
class CoverageResult:
    outcomes: Mapping[str, CertifiedOutcome]
    findings: tuple[VerifyFinding, ...]


_ALLOWED_REPORT_TRANSITIONS = frozenset(
    {
        ("not-attempted", "skipped"),
        ("not-attempted", "failed"),
        ("not-attempted", "applied"),
        ("failed", "applied"),
        ("applied", "already-applied"),
    }
)


def _resolve_predecessor(
    edge: PriorAttempt,
    attempts: Mapping[str, AttemptEvidence],
) -> str:
    predecessor = attempts.get(edge.run_id)
    if predecessor is None:
        raise ArtifactError(f"attempt predecessor run {edge.run_id} was not supplied")
    if edge.report_sha256 is not None:
        if predecessor.report_sha256 != edge.report_sha256:
            raise ArtifactError(
                f"attempt predecessor report hash for run {edge.run_id} was not supplied"
            )
    else:
        manifest_sha256 = (
            predecessor.manifest_set.sha256 if predecessor.manifest_set is not None else None
        )
        if manifest_sha256 != edge.manifest_sha256:
            raise ArtifactError(
                f"attempt predecessor manifest hash for run {edge.run_id} was not supplied"
            )
    return edge.run_id


def _order_attempts(attempts: Mapping[str, AttemptEvidence]) -> tuple[AttemptEvidence, ...]:
    successors: dict[str, str] = {}
    for run_id, attempt in attempts.items():
        edge = attempt.prior_attempt
        if edge is None:
            continue
        predecessor = _resolve_predecessor(edge, attempts)
        if predecessor in successors:
            raise ArtifactError(f"attempt lineage forks after run {predecessor}")
        successors[predecessor] = run_id

    roots = [run_id for run_id, attempt in attempts.items() if attempt.prior_attempt is None]
    if len(roots) != 1:
        raise ArtifactError(f"attempt evidence must have exactly one root; found {len(roots)}")

    ordered: list[AttemptEvidence] = []
    current: str | None = roots[0]
    while current is not None:
        ordered.append(attempts[current])
        current = successors.pop(current, None)
    if successors or len(ordered) != len(attempts):
        raise ArtifactError("attempt lineage has an unresolved gap or disconnected tip")
    return tuple(ordered)


def _binding_findings(
    attempts: Sequence[AttemptEvidence],
    *,
    plan: Plan | None,
    plan_sha256: str | None,
) -> list[VerifyFinding]:
    expected = plan_sha256
    if expected is None:
        for attempt in attempts:
            if attempt.manifest_set is not None:
                expected = attempt.manifest_set.header.plan_sha256
                break
            if attempt.report is not None:
                expected = attempt.report.plan_ref.sha256
                break
    findings: list[VerifyFinding] = []
    for attempt in attempts:
        mismatches: list[str] = []
        if (
            expected is not None
            and attempt.manifest_set is not None
            and attempt.manifest_set.header.plan_sha256 != expected
        ):
            mismatches.append("manifest header plan hash")
        if (
            expected is not None
            and attempt.report is not None
            and attempt.report.plan_ref.sha256 != expected
        ):
            mismatches.append("report plan hash")
        if (
            plan is not None
            and attempt.report is not None
            and attempt.report.plan_ref.run_id != plan.run_id
        ):
            mismatches.append("report plan run_id")
        if mismatches:
            findings.append(
                VerifyFinding(
                    attempt.run_id,
                    "coverage-binding",
                    f"artifact evidence disagrees with the plan ({', '.join(mismatches)})",
                )
            )
    return findings


def _accounting_findings(attempts: Sequence[AttemptEvidence]) -> list[VerifyFinding]:
    findings: list[VerifyFinding] = []
    for attempt in attempts:
        if attempt.kind == "restore" or attempt.report is None:
            continue
        report_actions = {outcome.action_id for outcome in attempt.report.outcomes}
        report_applied = {
            outcome.action_id for outcome in attempt.report.outcomes if outcome.status == "applied"
        }
        manifest_applied: set[str] = set()
        if attempt.manifest_set is not None:
            manifest_applied = {
                record.action_id
                for record in attempt.manifest_set.records
                if record.result == "applied"
            }
        for action_id in sorted(report_applied - manifest_applied):
            findings.append(
                VerifyFinding(
                    action_id,
                    "accounting",
                    "report records applied but this attempt has no applied manifest evidence",
                )
            )
        for action_id in sorted(manifest_applied - report_actions):
            findings.append(
                VerifyFinding(
                    action_id,
                    "accounting",
                    "manifest records applied but this attempt's report omits the action",
                )
            )
    return findings


def load_verification_evidence(
    plan_path: Path | None,
    manifest_paths: Sequence[Path],
    report_paths: Sequence[Path],
    *,
    plan_snapshot: tuple[Plan, str] | None = None,
) -> VerificationEvidence:
    """Load immutable artifact snapshots and order their unified attempt graph.

    A supplied ``plan_snapshot`` must be the snapshot read from ``plan_path``;
    it is reused without rereading so callers can reject incompatible plans
    before locking while loading mutation evidence inside the corpus lock.
    """
    plan: Plan | None = None
    plan_sha256: str | None = None
    plan_input: VerificationInput | None = None
    if plan_path is not None:
        plan, plan_sha256 = (
            plan_snapshot if plan_snapshot is not None else artifacts.read_plan_snapshot(plan_path)
        )
        plan_input = VerificationInput(
            kind="plan",
            path=str(plan_path),
            run_id=plan.run_id,
            sha256=plan_sha256,
        )

    inspection = inspect_manifest_chain(manifest_paths)
    attempts: dict[str, AttemptEvidence] = {}
    manifest_inputs: dict[str, VerificationInput] = {}
    for manifest_set in inspection.chain.sets:
        run_id = manifest_set.header.run_id
        if run_id in attempts:
            raise ArtifactError(f"run {run_id} has more than one manifest")
        if manifest_set.sha256 is None:
            raise ArtifactError(f"{manifest_set.path}: validated manifest has no snapshot hash")
        attempts[run_id] = AttemptEvidence(
            run_id=run_id,
            kind=manifest_set.header.kind,
            prior_attempt=manifest_set.header.prior_attempt,
            manifest_set=manifest_set,
            report=None,
            report_sha256=None,
        )
        manifest_inputs[run_id] = VerificationInput(
            kind="manifest",
            path=str(manifest_set.path),
            run_id=run_id,
            sha256=manifest_set.sha256,
        )

    report_inputs: dict[str, VerificationInput] = {}
    for report_path in report_paths:
        report, report_sha256 = artifacts.read_report_snapshot(report_path)
        run_id = report.run_id
        if run_id in report_inputs:
            raise ArtifactError(f"run {run_id} has more than one report")
        current = attempts.get(run_id)
        if current is not None:
            if current.kind == "restore":
                raise ArtifactError(
                    f"run {run_id} is restore-kind and cannot publish an apply report"
                )
            if current.prior_attempt != report.prior_attempt:
                raise ArtifactError(f"run {run_id}: report/header prior_attempt disagreement")
            manifest_sha256 = (
                current.manifest_set.sha256 if current.manifest_set is not None else None
            )
            if report.manifest_sha256 != manifest_sha256:
                raise ArtifactError(f"run {run_id}: report manifest_sha256 disagreement")
            attempts[run_id] = replace(
                current,
                report=report,
                report_sha256=report_sha256,
            )
        else:
            if report.manifest_sha256 is not None:
                raise ArtifactError(
                    f"run {run_id}: report manifest_sha256 names an unsupplied manifest"
                )
            attempts[run_id] = AttemptEvidence(
                run_id=run_id,
                kind="apply",
                prior_attempt=report.prior_attempt,
                manifest_set=None,
                report=report,
                report_sha256=report_sha256,
            )
        report_inputs[run_id] = VerificationInput(
            kind="report",
            path=str(report_path),
            run_id=run_id,
            sha256=report_sha256,
        )

    ordered_attempts = _order_attempts(attempts) if attempts else ()
    findings = _binding_findings(
        ordered_attempts,
        plan=plan,
        plan_sha256=plan_sha256,
    )
    findings.extend(_accounting_findings(ordered_attempts))
    for attempt in ordered_attempts:
        if (
            attempt.kind == "apply"
            and attempt.manifest_set is not None
            and attempt.report is None
            and any(
                record.result in ("intent", "applied") for record in attempt.manifest_set.records
            )
        ):
            findings.append(
                VerifyFinding(
                    attempt.run_id,
                    "coverage-unprovable",
                    "apply mutation evidence exists but its report was not published",
                )
            )

    inputs: list[VerificationInput] = []
    if plan_input is not None:
        inputs.append(plan_input)
    for attempt in ordered_attempts:
        manifest_input = manifest_inputs.get(attempt.run_id)
        if manifest_input is not None:
            inputs.append(manifest_input)
        report_input = report_inputs.get(attempt.run_id)
        if report_input is not None:
            inputs.append(report_input)

    return VerificationEvidence(
        plan=plan,
        plan_sha256=plan_sha256,
        manifest_inspection=inspection,
        attempts=ordered_attempts,
        inputs=tuple(inputs),
        findings=tuple(findings),
    )


def _report_observation(outcome: ApplyOutcome) -> ReportObservation | None:
    if outcome.status == "would_apply":
        return None
    if outcome.status == "skipped" and outcome.skip_reason == "already-applied":
        return "already-applied"
    if outcome.status == "applied":
        return "applied"
    if outcome.status == "failed":
        return "failed"
    if outcome.status == "not-attempted":
        return "not-attempted"
    return "skipped"


def check_plan_coverage(evidence: VerificationEvidence) -> CoverageResult:
    """Reduce ordered mutation and report evidence to one outcome per plan action."""
    if evidence.plan is None or evidence.plan_sha256 is None:
        raise ArtifactError("plan coverage requires a supplied plan artifact")

    plan_counts = Counter(action.action_id for action in evidence.plan.actions)
    plan_actions = set(plan_counts)
    findings: list[VerifyFinding] = [
        VerifyFinding(action_id, "coverage", "plan contains duplicate action IDs")
        for action_id, count in sorted(plan_counts.items())
        if count > 1
    ]

    lifecycle = reduce_lifecycle(evidence.manifest_inspection.chain)
    evidence_actions = set(lifecycle)
    outcomes: dict[str, CertifiedOutcome] = {}
    nonterminal_actions: set[str] = set()
    for action_id, state in sorted(lifecycle.items()):
        if state.state == "applied":
            outcomes[action_id] = "applied"
        elif state.state == "failed":
            outcomes[action_id] = "failed"
        else:
            nonterminal_actions.add(action_id)
            findings.append(
                VerifyFinding(
                    action_id,
                    "coverage",
                    f"manifest lifecycle is {state.state}; plan is not fully applied",
                )
            )

    manifest_applied = {
        record.action_id
        for manifest_set in evidence.manifest_inspection.chain.sets
        if manifest_set.header.kind == "apply"
        for record in manifest_set.records
        if record.result == "applied" and record.undoes_action_id is None
    }
    report_states: dict[str, CertifiedOutcome] = {}
    preview_actions: set[str] = set()
    for attempt in evidence.attempts:
        if attempt.kind == "restore" or attempt.report is None:
            continue
        counts = Counter(outcome.action_id for outcome in attempt.report.outcomes)
        for action_id, count in sorted(counts.items()):
            if count > 1:
                findings.append(
                    VerifyFinding(
                        action_id,
                        "coverage",
                        f"attempt {attempt.run_id} reports the plan action more than once",
                    )
                )
        seen_in_report: set[str] = set()
        for outcome in attempt.report.outcomes:
            action_id = outcome.action_id
            evidence_actions.add(action_id)
            if action_id in seen_in_report:
                continue
            seen_in_report.add(action_id)
            observation = _report_observation(outcome)
            if observation is None:
                preview_actions.add(action_id)
                continue
            if observation in ("applied", "already-applied") and action_id not in manifest_applied:
                findings.append(
                    VerifyFinding(
                        action_id,
                        "coverage",
                        f"report claims {observation} without manifest-applied authority",
                    )
                )
                continue
            previous = report_states.get(action_id)
            if previous is None:
                report_states[action_id] = (
                    "applied" if observation == "already-applied" else observation
                )
                continue
            transition = (previous, observation)
            if transition not in _ALLOWED_REPORT_TRANSITIONS:
                findings.append(
                    VerifyFinding(
                        action_id,
                        "coverage",
                        f"illegal report transition {previous} -> {observation}",
                    )
                )
                continue
            if observation != "already-applied":
                report_states[action_id] = observation

    for action_id, report_state in sorted(report_states.items()):
        mutation_state = lifecycle.get(action_id)
        if mutation_state is None:
            outcomes[action_id] = report_state
            continue
        expected: CertifiedOutcome | None
        if mutation_state.state == "applied":
            expected = "applied"
        elif mutation_state.state == "failed":
            expected = "failed"
        elif mutation_state.state in ("pending-restore", "restored", "restore-failed"):
            expected = "applied"
        else:
            expected = None
        if expected is not None and report_state != expected:
            findings.append(
                VerifyFinding(
                    action_id,
                    "coverage",
                    f"report final state {report_state} contradicts manifest lifecycle "
                    f"{mutation_state.state}",
                )
            )
        elif expected is None:
            findings.append(
                VerifyFinding(
                    action_id,
                    "coverage",
                    f"report terminal {report_state} cannot close manifest lifecycle "
                    f"{mutation_state.state}",
                )
            )

    preview_only = {
        action_id
        for action_id in preview_actions
        if action_id not in outcomes and action_id not in nonterminal_actions
    }
    for action_id in sorted(preview_only):
        findings.append(
            VerifyFinding(
                action_id,
                "coverage-uncertified",
                "dry-run evidence does not certify a terminal plan outcome",
            )
        )

    ordered_plan_actions = dict.fromkeys(action.action_id for action in evidence.plan.actions)
    for action_id in ordered_plan_actions:
        if (
            action_id not in outcomes
            and action_id not in preview_only
            and action_id not in nonterminal_actions
        ):
            findings.append(
                VerifyFinding(action_id, "coverage", "plan action has no terminal outcome")
            )
    for action_id in sorted(evidence_actions - plan_actions):
        findings.append(
            VerifyFinding(action_id, "coverage", "artifact evidence names no plan action")
        )

    return CoverageResult(
        outcomes=MappingProxyType(dict(outcomes)),
        findings=tuple(findings),
    )
