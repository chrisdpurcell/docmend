"""Inventory data model — the DR-001 artifact as strict internal models (OQ-021).

Cross-file contract (adr-0005): the hand-authored ``src/docmend/schemas/
inventory.schema.json`` is the durable external contract; these pydantic models
CONFORM to it, never define it. Tests cross-check the two so drift fails CI.
Serialization goes through :mod:`docmend.artifacts`, which validates every
produced document against the checked-in schema before it touches disk — a
docmend-produced artifact failing its own contract is a defect, not an input
error.

Field semantics live in the schema's ``description`` strings (single-sourced
there); this module only repeats what a maintainer needs to construct records:
paths are POSIX-relative to ``source_root``, hashes are ``sha256:<hex>``, and
``encoding.detected`` stays ``None`` when only the charset-normalizer legacy
rung (MS-2, FR-007) could decide.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

INVENTORY_SCHEMA_VERSION = "1.2"

type NewlineStyle = Literal["lf", "crlf", "cr", "mixed", "none"]
type BomKind = Literal["utf-8", "utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"]
type DetectionMethod = Literal["bom", "utf8-strict", "ascii", "charset-normalizer"]
# 1.2 (FR-019/OQ-028): a candidate whose classification (including the charset
# detection rung) exceeds limits.per_file_timeout is recorded as a scan skip
# with reason "timeout" rather than a partial FileRecord (ERR-009).
type ScanSkipReason = Literal["excluded", "unreadable", "timeout"]

type RunId = Annotated[str, Field(pattern=r"^run_\d{8}T\d{6}Z_[0-9a-f]{6}$")]
type Sha256 = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


def _contained_relative_path(value: str) -> str:
    # Containment belt (spec §8.5/§13.5): artifacts are operator-editable JSON,
    # so a crafted absolute or '..' path must die at read time, not at apply.
    if value.startswith("/"):
        msg = "path must be relative to source_root, not absolute"
        raise ValueError(msg)
    if ".." in value.split("/"):
        msg = "path must not contain '..' segments"
        raise ValueError(msg)
    return value


type RelativePath = Annotated[str, Field(min_length=1), AfterValidator(_contained_relative_path)]


class _StrictModel(BaseModel):
    # Mirrors the schema's additionalProperties:false; strict typing keeps the
    # model layer as unforgiving as the external contract (OQ-021).
    model_config = ConfigDict(extra="forbid", strict=True)


class DetectedEncoding(_StrictModel):
    name: Annotated[str, Field(min_length=1)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    method: DetectionMethod


class EncodingFacts(_StrictModel):
    bom: BomKind | None
    utf8_valid: bool
    ascii_only: bool
    detected: DetectedEncoding | None


class FileRecord(_StrictModel):
    path: RelativePath
    size_bytes: Annotated[int, Field(ge=0)]
    suffix: str
    mtime_ns: Annotated[int, Field(ge=0)]
    nlink: Annotated[int, Field(ge=1)]
    sha256: Sha256
    newline_style: NewlineStyle
    nul_bytes: bool
    non_ascii_bytes: Annotated[int, Field(ge=0)]
    encoding: EncodingFacts


class SymlinkRecord(_StrictModel):
    path: RelativePath
    target: str
    kind: Literal["file", "directory", "broken", "other"]


class SkipRecord(_StrictModel):
    path: RelativePath
    reason: ScanSkipReason
    detail: str | None


class HardLinkGroup(_StrictModel):
    device: Annotated[int, Field(ge=0)]
    inode: Annotated[int, Field(ge=0)]
    nlink: Annotated[int, Field(ge=2)]
    paths: Annotated[list[RelativePath], Field(min_length=1)]


class ScanConfigRecord(_StrictModel):
    include: list[Annotated[str, Field(min_length=1)]]
    exclude: list[Annotated[str, Field(min_length=1)]]
    # 1.1 (MS-2 final-review Important #1): scan-output provenance beyond filters.
    # None = a pre-1.1 artifact where the fact is unknown; new scans always record.
    encoding_detect: bool | None = None
    detector: Annotated[str, Field(min_length=1)] | None = None


class SkippedByReason(_StrictModel):
    excluded: Annotated[int, Field(ge=0)] = 0
    unreadable: Annotated[int, Field(ge=0)] = 0
    # 1.2 (FR-019): the watchdog-skip counter, so totals.skipped keeps
    # reconciling exactly with the per-reason breakdown (DR-001).
    timeout: Annotated[int, Field(ge=0)] = 0


class InventoryTotals(_StrictModel):
    files: Annotated[int, Field(ge=0)]
    symlinks: Annotated[int, Field(ge=0)]
    skipped: Annotated[int, Field(ge=0)]
    skipped_by_reason: SkippedByReason
    hard_link_groups: Annotated[int, Field(ge=0)]
    total_size_bytes: Annotated[int, Field(ge=0)]


class Inventory(_StrictModel):
    """One `docmend scan` result (DR-001) — serialize via docmend.artifacts only."""

    # "schema" is the wire name (adr-0005 versioning fields) but shadows a
    # deprecated BaseModel attribute, hence the alias; serialize_by_alias keeps
    # model_dump() emitting the contract's key without every caller remembering
    # by_alias=True.
    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
    )

    schema_kind: Literal["docmend/inventory"] = Field(default="docmend/inventory", alias="schema")
    schema_version: Annotated[str, Field(pattern=r"^1\.\d+$")] = INVENTORY_SCHEMA_VERSION
    run_id: RunId
    generated_at: str
    generated_by: str
    requested_path: str
    source_root: str
    scan_config: ScanConfigRecord
    files: list[FileRecord]
    symlinks: list[SymlinkRecord]
    skipped: list[SkipRecord]
    hard_link_groups: list[HardLinkGroup]
    totals: InventoryTotals
