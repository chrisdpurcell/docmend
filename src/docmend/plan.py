"""Plan data model — the DR-002 artifact as strict internal models (OQ-021).

Cross-file contract (adr-0005): src/docmend/schemas/plan.schema.json is the
durable external contract; these models CONFORM to it. The Operation
vocabulary is imported from docmend.transform.dispatch (single-sourced), and
identity/hash type aliases are shared with docmend.inventory. Serialization
goes through docmend.artifacts, which validates before disk.

``Plan.config`` is intentionally ``dict[str, object]`` rather than a re-modeled
``DocmendConfig`` clone: the schema's ``config_snapshot`` and the existing
strict ``DocmendConfig`` model already own that shape (adr-0005 — models
conform to schemas, never redefine them twice over).
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer

from docmend.inventory import DetectedEncoding, NewlineStyle, RelativePath, RunId, Sha256
from docmend.transform.dispatch import Operation

PLAN_SCHEMA_VERSION = "1.1"

type ActionId = Annotated[str, Field(pattern=r"^run_\d{8}T\d{6}Z_[0-9a-f]{6}/a\d+$")]
type DocmendId = Annotated[
    str,
    Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
]
type PlanSkipReason = Literal[
    "binary-suspect",
    "nul-bytes",
    "utf16-suspect",
    "decode-replacement",
    "low-confidence-encoding",
    "below-non-ascii-floor",
    "collision",
    "hard-link-alias",
    "symlink",
    "oversize",
    "shrink-invariant",
    "excluded",
    "unreadable",
    "changed-since-scan",
]


class _StrictModel(BaseModel):
    # Mirrors the schema's additionalProperties:false; strict typing keeps the
    # model layer as unforgiving as the external contract (OQ-021).
    model_config = ConfigDict(extra="forbid", strict=True)


class ArtifactRef(_StrictModel):
    path: Annotated[str, Field(min_length=1)]
    run_id: RunId
    sha256: Sha256


class ActionProvenance(_StrictModel):
    detected_encoding: DetectedEncoding | None
    newline_style: NewlineStyle


class PlanAction(_StrictModel):
    action_id: ActionId
    docmend_id: DocmendId
    path: RelativePath
    source_sha256: Sha256
    source_size_bytes: Annotated[int, Field(ge=0)]
    operations: Annotated[list[Operation], Field(min_length=1)]
    target_path: RelativePath | None
    provenance: ActionProvenance


class SkipDecision(_StrictModel):
    path: RelativePath
    reason: PlanSkipReason
    detail: str | None


class PlanTotals(_StrictModel):
    actions: Annotated[int, Field(ge=0)]
    skips: Annotated[int, Field(ge=0)]


class Plan(_StrictModel):
    """One `docmend plan` result (DR-002) — serialize via docmend.artifacts only."""

    # "schema" is the wire name (adr-0005 versioning fields) but shadows a
    # deprecated BaseModel attribute, hence the alias; serialize_by_alias keeps
    # model_dump() emitting the contract's key without every caller remembering
    # by_alias=True.
    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
    )

    schema_kind: Literal["docmend/plan"] = Field(default="docmend/plan", alias="schema")
    schema_version: Annotated[str, Field(pattern=r"^1\.\d+$")] = PLAN_SCHEMA_VERSION
    run_id: RunId
    generated_at: str
    generated_by: str
    inventory_ref: ArtifactRef
    source_root: Annotated[str, Field(min_length=1)] | None = None
    config: dict[str, object]
    actions: list[PlanAction]
    skips: list[SkipDecision]
    totals: PlanTotals

    @model_serializer(mode="wrap")
    def _omit_absent_source_root(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        # `source_root` is OPTIONAL in the schema (1.0-plan compat), not
        # nullable — a bare `null` fails validation. None means "field
        # absent" (a pre-1.1 plan or one built without an inventory), so it
        # must never appear as a JSON key at all, only ever be omitted.
        data = handler(self)
        if data.get("source_root") is None:
            data.pop("source_root", None)
        return data
