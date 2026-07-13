"""Public-safe scale qualification evidence (NFR-001, OQ-037/OQ-038).

Qualification documents are repository evidence, not operator run artifacts:
they have a separate schema registry and never join ``ARTIFACT_KINDS``.  The
private harness may retain commands, paths, and child output in its external
workspace; only the aggregate records in this module may cross into the public
evidence tree.
"""

import hashlib
import json
import os
import stat
from collections.abc import Iterable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, Protocol, Self, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)
from pydantic import (
    ValidationError as ModelValidationError,
)

from docmend.artifacts import write_json_artifact
from docmend.inventory import RunId, Sha256

SCALE_EVIDENCE_SCHEMA_VERSION = "1.0"
REFERENCE_ENVIRONMENT_SCHEMA_VERSION = "1.0"
SCALE_THRESHOLDS_SCHEMA_VERSION = "1.0"
BINDING_CAPACITY_MARGIN = 0.25

type QualificationSchemaKind = Literal[
    "scale-evidence", "reference-environment", "scale-thresholds"
]
QUALIFICATION_SCHEMA_KINDS: tuple[QualificationSchemaKind, ...] = (
    "scale-evidence",
    "reference-environment",
    "scale-thresholds",
)

type EvidenceStatus = Literal["passing", "failed", "incomplete", "diagnostic"]
type QualificationTier = Literal["pr", "pilot", "scheduled", "release", "file-size"]
type StageName = Literal["scan", "plan", "apply", "verify"]
type CacheClassification = Literal["cold", "warm", "mixed"]
type MemoryMeasurement = Literal["external-rss", "python-allocation"]
type MountFlag = Literal[
    "ro", "rw", "relatime", "noatime", "nodiratime", "lazytime", "sync", "dirsync"
]
type StorageClass = Literal["local-ssd", "local-hdd", "memory", "network", "unknown"]
type ArtifactSizeName = Literal[
    "inventory", "plan", "report", "manifest", "verify-report", "stdout-log", "stderr-log"
]
type ArtifactSchemaName = Literal[
    "inventory", "plan", "report", "manifest", "verify-report", "frontmatter"
]
type ArtifactSize = Annotated[int, Field(ge=0)]
type ArtifactSchemaVersion = Annotated[str, Field(pattern=r"^\d+\.\d+$")]

_ARTIFACT_SCHEMA_NAMES: tuple[ArtifactSchemaName, ...] = (
    "inventory",
    "plan",
    "report",
    "manifest",
    "verify-report",
    "frontmatter",
)


class ScaleEvidenceError(Exception):
    """A public qualification document is unreadable, unsafe, or inconsistent."""


class _CompiledValidator(Protocol):
    def iter_errors(self, instance: object) -> Iterator[SchemaValidationError]: ...


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


def _public_label(value: str) -> str:
    if any(ord(character) < 32 for character in value) or any(
        character in value for character in "/\\="
    ):
        raise ValueError("public labels cannot contain controls, paths, or key/value data")
    return value


type PublicLabel = Annotated[
    str,
    Field(min_length=1, max_length=256, pattern=r"^[^/\\=\n\r\t]+$"),
    AfterValidator(_public_label),
]


class MemoryPoint(_StrictModel):
    files: Annotated[int, Field(gt=0)]
    peak_rss_bytes: Annotated[int, Field(gt=0)]


class StageEvidence(_StrictModel):
    stage: StageName
    run_id: RunId | None
    elapsed_seconds: Annotated[float, Field(ge=0)]
    files_per_second: Annotated[float, Field(ge=0)]
    bytes_per_second: Annotated[float, Field(ge=0)]
    peak_rss_bytes: Annotated[int, Field(ge=0)] | None
    python_allocation_peak_bytes: Annotated[int, Field(ge=0)] | None
    vm_swap_peak_bytes: Annotated[int, Field(ge=0)]
    exit_code: int
    completed: bool
    artifact_bytes: dict[ArtifactSizeName, ArtifactSize]

    @model_validator(mode="after")
    def _require_run_id_for_completed_stage(self) -> Self:
        if self.completed and self.run_id is None:
            raise ValueError("run_id is required when a stage is completed")
        measurements = sum(
            value is not None for value in (self.peak_rss_bytes, self.python_allocation_peak_bytes)
        )
        if measurements > 1:
            raise ValueError("a stage must never mix RSS and Python allocation measurements")
        if self.completed and measurements == 0:
            raise ValueError("a completed stage requires one memory measurement")
        return self


class FilesystemCapacityEvidence(_StrictModel):
    """One identifier-free capacity aggregate; mount paths/devices stay private."""

    required_bytes: Annotated[int, Field(ge=0)]
    available_bytes: Annotated[int, Field(ge=0)]
    required_inodes: Annotated[int, Field(ge=0)]
    available_inodes: Annotated[int, Field(ge=0)]
    margin_fraction: Annotated[float, Field(ge=0)]
    passed: bool

    @model_validator(mode="after")
    def _reconcile_verdict(self) -> Self:
        expected = (
            self.required_bytes <= self.available_bytes
            and self.required_inodes <= self.available_inodes
        )
        if self.passed != expected:
            raise ValueError("capacity verdict does not reconcile with byte/inode availability")
        return self


class PreflightEvidence(_StrictModel):
    filesystems: tuple[FilesystemCapacityEvidence, ...]
    capacity_margin_met: bool
    reference_environment_match: bool
    binding_filesystem: bool
    ram_requirement_met: bool
    passed: bool

    @model_validator(mode="after")
    def _reconcile_verdict(self) -> Self:
        margin_met = bool(self.filesystems) and all(
            item.margin_fraction == BINDING_CAPACITY_MARGIN for item in self.filesystems
        )
        if self.capacity_margin_met != margin_met:
            raise ValueError("capacity margin verdict does not reconcile with filesystem evidence")
        expected = (
            bool(self.filesystems)
            and all(item.passed for item in self.filesystems)
            and self.capacity_margin_met
            and self.reference_environment_match
            and self.binding_filesystem
            and self.ram_requirement_met
        )
        if self.passed != expected:
            raise ValueError("preflight verdict does not reconcile with its component checks")
        return self


class QualificationTotals(_StrictModel):
    scanned: Annotated[int, Field(ge=0)]
    actions: Annotated[int, Field(ge=0)]
    clean_noops: Annotated[int, Field(ge=0)]
    plan_skips: Annotated[int, Field(ge=0)]
    applied: Annotated[int, Field(ge=0)]
    apply_skips: Annotated[int, Field(ge=0)]
    failures: Annotated[int, Field(ge=0)]
    not_attempted: Annotated[int, Field(ge=0)]
    verified: Annotated[int, Field(ge=0)]
    expected_findings: Annotated[int, Field(ge=0)]
    observed_findings: Annotated[int, Field(ge=0)]


class ThresholdSet(_StrictModel):
    absolute_peak_rss_bytes: Annotated[int, Field(gt=0)]
    slope_bytes_per_file: Annotated[int, Field(ge=0)]
    linearity_tolerance: Annotated[float, Field(ge=0, le=1)]


class ThresholdVerdict(_StrictModel):
    limits: ThresholdSet
    observed_peak_rss_bytes: Annotated[int, Field(ge=0)]
    observed_slope_bytes_per_file: Annotated[float, Field(ge=0)]
    observed_linearity_ratio: Annotated[float, Field(ge=0)]
    peak_passed: bool
    slope_passed: bool
    linearity_passed: bool
    passed: bool

    @model_validator(mode="after")
    def _reconcile_verdict(self) -> Self:
        peak_passed = self.observed_peak_rss_bytes <= self.limits.absolute_peak_rss_bytes
        slope_passed = self.observed_slope_bytes_per_file <= self.limits.slope_bytes_per_file
        linearity_passed = self.observed_linearity_ratio <= self.limits.linearity_tolerance
        if (self.peak_passed, self.slope_passed, self.linearity_passed) != (
            peak_passed,
            slope_passed,
            linearity_passed,
        ):
            raise ValueError("threshold component verdicts do not reconcile with observed values")
        if self.passed != (peak_passed and slope_passed and linearity_passed):
            raise ValueError("aggregate threshold verdict does not reconcile")
        return self


class ScaleEvidence(_StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_kind: Literal["docmend/scale-evidence"] = Field(
        default="docmend/scale-evidence", alias="schema"
    )
    schema_version: Literal["1.0"] = SCALE_EVIDENCE_SCHEMA_VERSION
    status: EvidenceStatus
    tier: QualificationTier
    candidate_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    package_version: PublicLabel
    wheel_sha256: Sha256 | None
    lock_sha256: Sha256
    reference_environment_sha256: Sha256
    threshold_baseline_sha256: Sha256 | None = None
    artifact_schema_versions: dict[ArtifactSchemaName, ArtifactSchemaVersion]
    python_version: PublicLabel
    kernel_version: PublicLabel
    memory_measurement: MemoryMeasurement
    cache_classification: CacheClassification
    started_at: AwareDatetime
    completed_at: AwareDatetime
    preflight: PreflightEvidence
    file_count: Annotated[int, Field(gt=0)]
    corpus_bytes: Annotated[int, Field(ge=0)]
    stages: list[StageEvidence]
    totals: QualificationTotals
    thresholds: ThresholdVerdict | None

    @model_validator(mode="after")
    def _reconcile_public_evidence(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if set(self.artifact_schema_versions) != set(_ARTIFACT_SCHEMA_NAMES):
            raise ValueError(
                "artifact_schema_versions must contain the complete finite artifact set"
            )
        if self.totals.scanned != self.file_count:
            raise ValueError("totals.scanned must equal file_count")
        if (
            self.totals.actions + self.totals.clean_noops + self.totals.plan_skips
            != self.totals.scanned
        ):
            raise ValueError("scan/plan totals do not conserve the corpus")

        if self.memory_measurement == "external-rss":
            mixed = any(stage.python_allocation_peak_bytes is not None for stage in self.stages)
        else:
            mixed = any(stage.peak_rss_bytes is not None for stage in self.stages)
            if self.status != "diagnostic":
                raise ValueError("Python allocation measurement is diagnostic-only")
            if self.thresholds is not None:
                raise ValueError("Python allocation diagnostics cannot carry binding thresholds")
        if mixed:
            raise ValueError("one evidence document must never mix memory measurement methods")

        if self.status != "passing":
            return self
        if not self.preflight.passed:
            raise ValueError("passing evidence requires a passing preflight")
        if self.tier != "pr" and self.wheel_sha256 is None:
            raise ValueError("wheel_sha256 is required for passing installed-wheel evidence")
        if self.tier in {"pilot", "scheduled", "release"}:
            names = tuple(stage.stage for stage in self.stages)
            expected: tuple[StageName, ...] = ("scan", "plan", "apply", "verify")
            if names != expected or not all(stage.completed for stage in self.stages):
                raise ValueError(
                    "passing evidence requires completed scan, plan, apply, verify stages"
                )
            if any(stage.exit_code != 0 for stage in self.stages[:3]):
                raise ValueError("passing scan, plan, and apply must exit 0")
            expected_verify_exit = 1 if self.totals.expected_findings else 0
            if self.stages[3].exit_code != expected_verify_exit:
                raise ValueError("verify exit code does not reconcile with expected findings")
        if any(stage.vm_swap_peak_bytes for stage in self.stages):
            raise ValueError("passing binding evidence requires zero child swap")
        terminal = (
            self.totals.applied
            + self.totals.apply_skips
            + self.totals.failures
            + self.totals.not_attempted
        )
        if terminal != self.totals.actions:
            raise ValueError("apply totals do not reconcile with planned actions")
        if self.totals.failures or self.totals.not_attempted:
            raise ValueError("passing evidence cannot contain failures or not-attempted actions")
        if self.totals.verified != self.totals.actions:
            raise ValueError("passing evidence requires complete plan verification coverage")
        if self.totals.observed_findings != self.totals.expected_findings:
            raise ValueError("passing evidence requires exact expected finding totals")
        if self.tier in {"scheduled", "release"} and (
            self.thresholds is None or not self.thresholds.passed
        ):
            raise ValueError("passing scheduled/release evidence requires passing thresholds")
        if self.tier in {"scheduled", "release"} and self.threshold_baseline_sha256 is None:
            raise ValueError(
                "passing scheduled/release evidence requires threshold baseline provenance"
            )
        return self


class ReferenceEnvironment(_StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_kind: Literal["docmend/reference-environment"] = Field(
        default="docmend/reference-environment", alias="schema"
    )
    schema_version: Literal["1.0"] = REFERENCE_ENVIRONMENT_SCHEMA_VERSION
    operating_system: Literal["linux"]
    cpu_architecture: PublicLabel
    cpu_model: PublicLabel
    logical_cpu_count: Annotated[int, Field(gt=0)]
    ram_bytes: Annotated[int, Field(gt=0)]
    storage_class: StorageClass
    filesystem: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._+-]*$")]
    mount_flags: tuple[MountFlag, ...]
    python_version: PublicLabel
    kernel_version: PublicLabel

    @model_validator(mode="after")
    def _mount_flags_are_unique(self) -> Self:
        if len(set(self.mount_flags)) != len(self.mount_flags):
            raise ValueError("mount_flags must not contain duplicates")
        return self


def _safe_evidence_name(value: str) -> str:
    name = PurePosixPath(value)
    if (
        not name.parts
        or name.is_absolute()
        or name.as_posix() != value
        or ".." in name.parts
        or "\\" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError("evidence must be a canonical safe POSIX-relative name")
    return value


type EvidenceName = Annotated[
    str,
    Field(min_length=1, pattern=r"^[^/\\].*$"),
    AfterValidator(_safe_evidence_name),
]


class ThresholdPointIdentity(_StrictModel):
    file_count: Literal[10_000, 100_000]
    evidence: EvidenceName
    evidence_sha256: Sha256


class ThresholdBaseline(_StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_kind: Literal["docmend/scale-thresholds"] = Field(
        default="docmend/scale-thresholds", alias="schema"
    )
    schema_version: Literal["1.0"] = SCALE_THRESHOLDS_SCHEMA_VERSION
    reference_environment_sha256: Sha256
    measurement_points: tuple[ThresholdPointIdentity, ThresholdPointIdentity]
    fitting_method: Literal["exact-linear-least-squares"]
    limits: ThresholdSet

    @model_validator(mode="after")
    def _require_binding_point_pair(self) -> Self:
        counts = tuple(point.file_count for point in self.measurement_points)
        if counts != (10_000, 100_000):
            raise ValueError(
                "measurement_points must be the ordered 10000-file and 100000-file pair"
            )
        return self


@dataclass(frozen=True, slots=True)
class MemoryFit:
    """Exact least-squares line; fractions prevent pilot-dependent float drift."""

    slope_bytes_per_file: Fraction
    intercept_bytes: Fraction


def fit_peak_rss_slope(points: Iterable[MemoryPoint]) -> MemoryFit:
    """Fit ``peak = intercept + slope * files`` using exact rational arithmetic."""
    values = tuple(points)
    if len(values) < 2:
        raise ValueError("at least two memory points are required")
    if len({point.files for point in values}) != len(values):
        raise ValueError("memory points must use distinct file counts")

    count = len(values)
    sum_x = sum(point.files for point in values)
    sum_y = sum(point.peak_rss_bytes for point in values)
    sum_xy = sum(point.files * point.peak_rss_bytes for point in values)
    sum_x_squared = sum(point.files * point.files for point in values)
    denominator = count * sum_x_squared - sum_x * sum_x
    if denominator == 0:
        raise ValueError("memory points do not define a slope")
    slope = Fraction(count * sum_xy - sum_x * sum_y, denominator)
    if slope < 0:
        raise ValueError("peak RSS slope must not be negative")
    intercept = Fraction(sum_y, count) - slope * Fraction(sum_x, count)
    return MemoryFit(slope_bytes_per_file=slope, intercept_bytes=intercept)


def _as_fraction(value: float | Fraction) -> Fraction:
    return value if isinstance(value, Fraction) else Fraction(str(value))


def _ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def derive_thresholds(
    fit: MemoryFit,
    *,
    largest_peak_bytes: int,
    headroom: float | Fraction = 0.25,
    linearity_tolerance: float = 0.20,
) -> ThresholdSet:
    """Freeze upward-rounded peak/slope limits from pilot observations."""
    if largest_peak_bytes <= 0:
        raise ValueError("largest_peak_bytes must be positive")
    headroom_fraction = _as_fraction(headroom)
    if headroom_fraction < 0:
        raise ValueError("headroom must not be negative")
    multiplier = 1 + headroom_fraction
    return ThresholdSet(
        absolute_peak_rss_bytes=_ceil_fraction(Fraction(largest_peak_bytes) * multiplier),
        slope_bytes_per_file=_ceil_fraction(fit.slope_bytes_per_file * multiplier),
        linearity_tolerance=linearity_tolerance,
    )


def load_qualification_schema(kind: QualificationSchemaKind) -> dict[str, object]:
    """Load one checked-in qualification schema from the installed package."""
    text = (resources.files("docmend.schemas") / f"{kind}.schema.json").read_text("utf-8")
    return cast("dict[str, object]", json.loads(text))


@cache
def _validator_for(kind: QualificationSchemaKind) -> _CompiledValidator:
    schema = load_qualification_schema(kind)
    Draft202012Validator.check_schema(schema)  # pyright: ignore[reportUnknownMemberType]
    return cast(
        "_CompiledValidator",
        Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER),
    )


def validate_qualification_document(kind: QualificationSchemaKind, document: object) -> None:
    """Reject documents outside the strict public qualification contract."""
    errors = sorted(_validator_for(kind).iter_errors(document), key=lambda error: error.json_path)
    if errors:
        findings = "; ".join(f"{error.json_path}: {error.message}" for error in errors)
        raise ScaleEvidenceError(f"{kind} failed schema validation — {findings}")


def _validated_document(model: BaseModel, kind: QualificationSchemaKind) -> dict[str, object]:
    document = cast("dict[str, object]", model.model_dump(mode="json"))
    validate_qualification_document(kind, document)
    return document


def write_scale_evidence(
    evidence: ScaleEvidence,
    path: Path,
    *,
    accepted: bool,
    threshold_baseline_path: Path | None = None,
) -> None:
    """Validate and publish evidence once; accepted locations require a passing run."""
    if accepted and evidence.status != "passing":
        raise ScaleEvidenceError("accepted evidence must have status passing")
    if accepted and evidence.tier in {"scheduled", "release"}:
        if threshold_baseline_path is None:
            raise ScaleEvidenceError(
                "accepted scheduled/release evidence requires a validated threshold baseline"
            )
        baseline, digest = load_threshold_baseline_snapshot(
            threshold_baseline_path,
            reference_environment_sha256=evidence.reference_environment_sha256,
        )
        if evidence.threshold_baseline_sha256 != digest:
            raise ScaleEvidenceError(
                "accepted evidence threshold baseline digest does not match validated bytes"
            )
        if evidence.thresholds is None or evidence.thresholds.limits != baseline.limits:
            raise ScaleEvidenceError(
                "accepted evidence threshold limits do not match the validated baseline"
            )
    document = _validated_document(evidence, "scale-evidence")
    write_json_artifact(document, path, clobber=False)


def write_reference_environment(environment: ReferenceEnvironment, path: Path) -> None:
    document = _validated_document(environment, "reference-environment")
    write_json_artifact(document, path, clobber=False)


def write_threshold_baseline(baseline: ThresholdBaseline, path: Path) -> None:
    document = _validated_document(baseline, "scale-thresholds")
    write_json_artifact(document, path, clobber=False)


def _read_payload(path: Path, *, description: str) -> tuple[bytes, object]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ScaleEvidenceError(f"{path}: cannot read {description} ({exc})") from exc
    return payload, _decode_payload(path, payload, description=description)


def _decode_payload(path: Path, payload: bytes, *, description: str) -> object:
    try:
        document: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScaleEvidenceError(f"{path}: {description} is not valid JSON ({exc})") from exc
    return document


def _close_fd(fd: int) -> None:
    os.close(fd)


def _read_payload_beneath(
    root: Path, relative_name: str, *, description: str
) -> tuple[bytes, object]:
    """Open a regular file beneath ``root`` without following any symlink component."""
    directory_flag = cast("int", getattr(os, "O_DIRECTORY", 0))
    nofollow_flag = cast("int", getattr(os, "O_NOFOLLOW", 0))
    cloexec_flag = cast("int", getattr(os, "O_CLOEXEC", 0))
    directory_flags = os.O_RDONLY | directory_flag | nofollow_flag | cloexec_flag
    file_flags = os.O_RDONLY | nofollow_flag | cloexec_flag
    display_path = root / relative_name
    try:
        with ExitStack() as stack:
            directory_fd = os.open(root, directory_flags)
            stack.callback(_close_fd, directory_fd)
            parts = PurePosixPath(relative_name).parts
            if not parts:
                raise OSError("threshold evidence name has no file component")
            for part in parts[:-1]:
                child_fd = os.open(part, directory_flags, dir_fd=directory_fd)
                stack.callback(_close_fd, child_fd)
                if not stat.S_ISDIR(os.fstat(child_fd).st_mode):
                    raise NotADirectoryError(part)
                directory_fd = child_fd
            file_fd = os.open(parts[-1], file_flags, dir_fd=directory_fd)
            stack.callback(_close_fd, file_fd)
            if not stat.S_ISREG(os.fstat(file_fd).st_mode):
                raise OSError(f"{display_path} is not a regular file")
            chunks: list[bytes] = []
            while chunk := os.read(file_fd, 1 << 20):
                chunks.append(chunk)
            payload = b"".join(chunks)
    except (OSError, ValueError) as exc:
        raise ScaleEvidenceError(f"{display_path}: cannot read {description} ({exc})") from exc
    return payload, _decode_payload(display_path, payload, description=description)


def _scale_evidence_from_snapshot(path: Path, payload: bytes, document: object) -> ScaleEvidence:
    validate_qualification_document("scale-evidence", document)
    try:
        return ScaleEvidence.model_validate_json(payload)
    except ModelValidationError as exc:
        raise ScaleEvidenceError(f"{path}: scale evidence failed model validation ({exc})") from exc


def read_scale_evidence_snapshot(path: Path) -> tuple[ScaleEvidence, str]:
    """Read model and digest from the same immutable byte snapshot."""
    payload, document = _read_payload(path, description="scale evidence")
    evidence = _scale_evidence_from_snapshot(path, payload, document)
    digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    return evidence, digest


def read_scale_evidence(path: Path) -> ScaleEvidence:
    return read_scale_evidence_snapshot(path)[0]


def read_reference_environment(path: Path) -> ReferenceEnvironment:
    payload, document = _read_payload(path, description="reference environment")
    validate_qualification_document("reference-environment", document)
    try:
        return ReferenceEnvironment.model_validate_json(payload)
    except ModelValidationError as exc:
        raise ScaleEvidenceError(
            f"{path}: reference environment failed model validation ({exc})"
        ) from exc


def load_threshold_baseline_snapshot(
    path: Path, *, reference_environment_sha256: Sha256
) -> tuple[ThresholdBaseline, str]:
    """Load a baseline and verify both referenced pilot documents byte-for-byte."""
    payload, document = _read_payload(path, description="threshold baseline")
    if isinstance(document, dict):
        typed_document = cast("dict[str, object]", document)
        version = typed_document.get("schema_version")
        if version != SCALE_THRESHOLDS_SCHEMA_VERSION:
            raise ScaleEvidenceError(f"{path}: unsupported threshold schema version {version}")
    validate_qualification_document("scale-thresholds", cast("object", document))
    try:
        baseline = ThresholdBaseline.model_validate_json(payload)
    except ModelValidationError as exc:
        raise ScaleEvidenceError(
            f"{path}: threshold baseline failed model validation ({exc})"
        ) from exc
    if baseline.reference_environment_sha256 != reference_environment_sha256:
        raise ScaleEvidenceError(f"{path}: reference environment mismatch")

    evidence_root = path.parent.resolve()
    pilot_evidence: list[ScaleEvidence] = []
    memory_points: list[MemoryPoint] = []
    for point in baseline.measurement_points:
        point_path = (path.parent / point.evidence).resolve()
        if not point_path.is_relative_to(evidence_root):
            raise ScaleEvidenceError(f"{path}: threshold evidence point escapes its evidence root")
        point_payload, point_document = _read_payload_beneath(
            evidence_root, point.evidence, description="threshold evidence point"
        )
        digest = f"sha256:{hashlib.sha256(point_payload).hexdigest()}"
        if digest != point.evidence_sha256:
            raise ScaleEvidenceError(f"{point_path}: threshold evidence hash mismatch")
        evidence = _scale_evidence_from_snapshot(point_path, point_payload, point_document)
        if evidence.file_count != point.file_count:
            raise ScaleEvidenceError(
                f"{point_path}: threshold point count does not match its identity"
            )
        if evidence.reference_environment_sha256 != baseline.reference_environment_sha256:
            raise ScaleEvidenceError(f"{point_path}: reference environment mismatch")
        if point.file_count == 100_000 and evidence.status != "passing":
            raise ScaleEvidenceError(f"{point_path}: 100000-file point must be passing")
        if evidence.tier != "pilot":
            raise ScaleEvidenceError(f"{point_path}: threshold evidence must use the pilot tier")
        expected_stages: tuple[StageName, ...] = ("scan", "plan", "apply", "verify")
        if tuple(stage.stage for stage in evidence.stages) != expected_stages or not all(
            stage.completed for stage in evidence.stages
        ):
            raise ScaleEvidenceError(f"{point_path}: threshold evidence pipeline is incomplete")
        if evidence.memory_measurement != "external-rss":
            raise ScaleEvidenceError(f"{point_path}: threshold evidence requires external RSS")
        stage_peaks = [
            stage.peak_rss_bytes for stage in evidence.stages if stage.peak_rss_bytes is not None
        ]
        if len(stage_peaks) != len(evidence.stages) or not stage_peaks or max(stage_peaks) <= 0:
            raise ScaleEvidenceError(f"{point_path}: threshold evidence has no usable RSS peak")
        pilot_evidence.append(evidence)
        memory_points.append(
            MemoryPoint(files=evidence.file_count, peak_rss_bytes=max(stage_peaks))
        )

    first, second = pilot_evidence
    first_provenance = (
        first.candidate_commit,
        first.package_version,
        first.wheel_sha256,
        first.lock_sha256,
        tuple(sorted(first.artifact_schema_versions.items())),
        first.python_version,
        first.kernel_version,
        first.cache_classification,
    )
    second_provenance = (
        second.candidate_commit,
        second.package_version,
        second.wheel_sha256,
        second.lock_sha256,
        tuple(sorted(second.artifact_schema_versions.items())),
        second.python_version,
        second.kernel_version,
        second.cache_classification,
    )
    if first.wheel_sha256 is None or first_provenance != second_provenance:
        raise ScaleEvidenceError(f"{path}: pilot provenance mismatch between threshold points")

    fit = fit_peak_rss_slope(memory_points)
    expected_limits = derive_thresholds(
        fit, largest_peak_bytes=max(point.peak_rss_bytes for point in memory_points)
    )
    if baseline.limits != expected_limits:
        raise ScaleEvidenceError(f"{path}: threshold limits do not match the pinned pilot points")
    baseline_digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    return baseline, baseline_digest


def load_threshold_baseline(
    path: Path, *, reference_environment_sha256: Sha256
) -> ThresholdBaseline:
    return load_threshold_baseline_snapshot(
        path, reference_environment_sha256=reference_environment_sha256
    )[0]


def load_threshold_limits(
    tier: QualificationTier,
    path: Path | None,
    *,
    reference_environment_sha256: Sha256,
) -> ThresholdSet | None:
    """Return executable limits; binding scheduled/release requests cannot omit them."""
    if tier in {"scheduled", "release"} and path is None:
        raise ScaleEvidenceError(f"{tier} qualification requires a threshold baseline")
    if path is None:
        return None
    return load_threshold_baseline(
        path, reference_environment_sha256=reference_environment_sha256
    ).limits
