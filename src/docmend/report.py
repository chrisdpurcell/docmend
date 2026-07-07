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
from docmend.plan import ActionId, ArtifactRef, RunId

REPORT_SCHEMA_VERSION = "1.0"

type OutcomeStatus = Literal["applied", "would_apply", "skipped", "failed"]
#: Closed internal vocabulary for the schema's free-string skip_reason
#: (decision 9): stale hash ERR-002/AW-004, apply-time unreadable ERR-005,
#: collision AW-002, EC-005 re-check, snapshot-filter enforcement (FR-012),
#: the runtime containment belt (§13.5), and resume reconciliation (FR-013,
#: adr-0006) — `already-applied` is the one skip that is NOT a reviewable
#: finding (the CLI excludes it from the exit-1 count).
type ApplySkipReason = Literal[
    "stale-hash",
    "unreadable",
    "collision",
    "shrink-invariant",
    "excluded",
    "containment",
    "already-applied",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ErrorInfo(BaseModel):
    """Classified failure ({'class': 'ERR-NNN', 'message': ...}); 'class' is a
    Python keyword, hence the alias."""

    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
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


class Report(_StrictModel):
    """One `docmend apply` result (DR-003) — serialize via docmend.artifacts only."""

    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
    )

    schema_kind: Literal["docmend/report"] = Field(default="docmend/report", alias="schema")
    schema_version: Annotated[str, Field(pattern=r"^1\.\d+$")] = REPORT_SCHEMA_VERSION
    run_id: RunId
    generated_by: Annotated[str, Field(min_length=1)]
    plan_ref: ArtifactRef
    dry_run: bool
    started_at: str
    completed_at: str
    outcomes: list[ApplyOutcome]
    totals: ReportTotals
