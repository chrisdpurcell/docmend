"""Apply-report data model — the DR-003 artifact as strict internal models (OQ-021).

Cross-file contract (adr-0005): src/docmend/schemas/report.schema.json is the
durable external contract; these models CONFORM to it. Identity/hash aliases
are shared with docmend.inventory/docmend.plan; serialization goes through
docmend.artifacts, which validates before disk and enforces the DR-003
totals-equal-outcomes reconciliation rule.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from docmend.inventory import Sha256
from docmend.lineage import PriorAttempt
from docmend.plan import ActionId, ArtifactRef, RunId

REPORT_SCHEMA_VERSION = "2.0"

#: 2.0 (adr-0019): `not-attempted` is the explicit terminal for plan actions a
#: `fail`-policy abort never reached — the report partitions EVERY plan action
#: exactly once, so verify (Plan D) can prove full coverage instead of
#: trailing actions silently vanishing (DMR-05 accounting).
type OutcomeStatus = Literal["applied", "would_apply", "skipped", "failed", "not-attempted"]
#: Closed internal vocabulary for the schema's free-string skip_reason
#: (decision 9): stale hash ERR-002/AW-004, apply-time unreadable ERR-005,
#: collision AW-002, an action-time collision lacking a preservation strategy,
#: EC-005 re-check, snapshot-filter enforcement (FR-012), the runtime
#: containment belt (§13.5), a hard link that appeared in the plan->apply window
#: (DEV-001 commit-boundary re-check; the primary gate is plan-time at
#: planning.py:68, which uses the same reason literal), commit-boundary
#: interference (adr-0020), and resume reconciliation (FR-013, adr-0006) —
#: `already-applied` is the one skip that is NOT a reviewable finding (the CLI
#: excludes it from the exit-1 count).
type ApplySkipReason = Literal[
    "stale-hash",
    "unreadable",
    "collision",
    "collision-unpreserved",
    "shrink-invariant",
    "excluded",
    "containment",
    "hard-link-alias",
    "already-applied",
    "external-interference",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ErrorInfo(BaseModel):
    """Classified failure ({'class': 'ERR-NNN', 'message': ...}); 'class' is a
    Python keyword, hence the alias."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=True,
        serialize_by_alias=True,
        frozen=True,
    )

    error_class: Annotated[str, Field(pattern=r"^ERR-\d{3}$", alias="class")]
    message: str


class ApplyOutcome(_StrictModel):
    action_id: ActionId
    path: Annotated[str, Field(min_length=1)]
    status: OutcomeStatus
    before_sha256: Sha256 | None
    after_sha256: Sha256 | None
    skip_reason: ApplySkipReason | None
    error: ErrorInfo | None


class ReportTotals(_StrictModel):
    applied: Annotated[int, Field(ge=0)]
    would_apply: Annotated[int, Field(ge=0)]
    skipped: Annotated[int, Field(ge=0)]
    failed: Annotated[int, Field(ge=0)]
    not_attempted: Annotated[int, Field(ge=0)] = 0


class Report(_StrictModel):
    """One `docmend apply` result (DR-003) — serialize via docmend.artifacts only."""

    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
    )

    schema_kind: Literal["docmend/report"] = Field(default="docmend/report", alias="schema")
    schema_version: Annotated[str, Field(pattern=r"^2\.\d+$")] = REPORT_SCHEMA_VERSION
    run_id: RunId
    generated_by: Annotated[str, Field(min_length=1)]
    plan_ref: ArtifactRef
    dry_run: bool
    started_at: str
    completed_at: str
    outcomes: list[ApplyOutcome]
    totals: ReportTotals
    # 2.0 attempt lineage (adr-0019, design F6 round 5): the same
    # discriminated edge the manifest header carries — persisted redundantly
    # so the lineage survives whichever artifact an interruption erases.
    # `manifest_sha256` is the hash of THIS attempt's closed manifest, null
    # when the attempt mutated nothing (that null is what distinguishes a
    # genuine report-only attempt from a LOST manifest — review CR-NEW-001).
    prior_attempt: PriorAttempt | None = None
    manifest_sha256: Sha256 | None = None
