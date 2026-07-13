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
from collections.abc import Iterable, Iterator, Mapping
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
from docmend.frontmatter import FRONTMATTER_SCHEMA_VERSION
from docmend.inventory import INVENTORY_SCHEMA_VERSION, RunId, Sha256
from docmend.plan import PLAN_SCHEMA_VERSION
from docmend.report import REPORT_SCHEMA_VERSION
from docmend.verify_report import VERIFY_REPORT_SCHEMA_VERSION
from docmend.writer.manifest import MANIFEST_SCHEMA_VERSION

SCALE_EVIDENCE_SCHEMA_VERSION = "2.0"
REFERENCE_ENVIRONMENT_SCHEMA_VERSION = "1.0"
SCALE_THRESHOLDS_SCHEMA_VERSION = "2.0"
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
type OutcomeReason = Literal[
    "explicit-diagnostic",
    "reference-mismatch",
    "reference-observation-unavailable",
    "provenance-changed",
    "build-failed",
    "install-failed",
    "capacity-insufficient",
    "capacity-estimate-exceeded",
    "corpus-materialization-failed",
    "supervisor-failed",
    "telemetry-unavailable",
    "stage-exit",
    "artifact-invalid",
    "conservation-mismatch",
    "finding-mismatch",
    "threshold-exceeded",
    "runtime-limit-exceeded",
    "harness-error",
]
type QualificationTier = Literal["pr", "pilot", "scheduled", "release", "file-size"]
type StageName = Literal["scan", "plan", "apply", "verify"]
type CacheClassification = Literal["cold", "warm", "mixed"]
type MemoryMeasurement = Literal["external-rss", "python-allocation"]
type MountFlag = Literal[
    "ro", "rw", "relatime", "noatime", "nodiratime", "lazytime", "sync", "dirsync"
]
type StorageClass = Literal["local-ssd", "local-hdd", "memory", "network", "unknown"]
type ArtifactSizeName = Literal[
    "inventory",
    "plan",
    "report",
    "manifest",
    "verify-report",
    "structured-log",
    "stdout-log",
    "stderr-log",
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


def current_artifact_schema_versions() -> dict[ArtifactSchemaName, ArtifactSchemaVersion]:
    """Return the candidate's product artifact versions from their code owners."""
    return {
        "inventory": INVENTORY_SCHEMA_VERSION,
        "plan": PLAN_SCHEMA_VERSION,
        "report": REPORT_SCHEMA_VERSION,
        "manifest": MANIFEST_SCHEMA_VERSION,
        "verify-report": VERIFY_REPORT_SCHEMA_VERSION,
        "frontmatter": FRONTMATTER_SCHEMA_VERSION,
    }


_STAGE_ARTIFACT_KEYS: dict[StageName, frozenset[ArtifactSizeName]] = {
    "scan": frozenset(("inventory", "structured-log", "stdout-log", "stderr-log")),
    "plan": frozenset(("plan", "structured-log", "stdout-log", "stderr-log")),
    "apply": frozenset(("report", "manifest", "structured-log", "stdout-log", "stderr-log")),
    "verify": frozenset(("verify-report", "structured-log", "stdout-log", "stderr-log")),
}
_STAGE_ORDER: tuple[StageName, ...] = ("scan", "plan", "apply", "verify")
_FAILURE_REASON_PRIORITY: tuple[OutcomeReason, ...] = (
    "stage-exit",
    "conservation-mismatch",
    "finding-mismatch",
    "threshold-exceeded",
    "runtime-limit-exceeded",
)
_FAILURE_REASONS: frozenset[OutcomeReason] = frozenset(_FAILURE_REASON_PRIORITY)
_DIAGNOSTIC_REASONS: frozenset[OutcomeReason] = frozenset(
    ("reference-mismatch", "explicit-diagnostic")
)
_INCOMPLETE_REASONS: frozenset[OutcomeReason] = frozenset(
    (
        "reference-observation-unavailable",
        "provenance-changed",
        "build-failed",
        "install-failed",
        "capacity-insufficient",
        "capacity-estimate-exceeded",
        "corpus-materialization-failed",
        "supervisor-failed",
        "telemetry-unavailable",
        "artifact-invalid",
        "harness-error",
    )
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
    vm_swap_peak_bytes: Annotated[int, Field(ge=0)] | None
    exit_code: int | None
    completed: bool
    artifact_validated: bool
    artifact_bytes: dict[ArtifactSizeName, ArtifactSize]

    @model_validator(mode="after")
    def _reconcile_measurement_and_artifact_state(self) -> Self:
        measurements = sum(
            value is not None for value in (self.peak_rss_bytes, self.python_allocation_peak_bytes)
        )
        if self.completed:
            if self.exit_code is None or measurements != 1:
                raise ValueError(
                    "a completed stage requires an exit code and exactly one memory measurement"
                )
        elif self.exit_code is not None or measurements != 0 or self.vm_swap_peak_bytes is not None:
            raise ValueError(
                "an incomplete stage requires null exit, RSS, allocation, and swap measurements"
            )

        expected_artifacts = _STAGE_ARTIFACT_KEYS[self.stage]
        actual_artifacts = set(self.artifact_bytes)
        if self.artifact_validated:
            if not self.completed or self.run_id is None:
                raise ValueError(
                    "artifact validation requires a completed stage and trusted run_id"
                )
            if frozenset(actual_artifacts) != expected_artifacts:
                raise ValueError(
                    "an artifact-validated stage requires its exact stage artifact keys"
                )
        else:
            if self.run_id is not None:
                raise ValueError("run_id must be null until stage artifacts are validated")
            if not actual_artifacts <= expected_artifacts:
                raise ValueError(
                    "an unvalidated stage may contain only stage-specific artifact keys"
                )
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
    linearity_tolerance: Annotated[float, Field(ge=0.2, le=0.2)] = 0.2


class ThresholdVerdict(_StrictModel):
    limits: ThresholdSet
    observed_peak_rss_bytes: Annotated[int, Field(ge=0)]
    observed_slope_bytes_per_file: Annotated[int, Field(ge=0)]
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


class WorkflowRuntimeVerdict(_StrictModel):
    elapsed_seconds: Annotated[float, Field(ge=0)]
    limit_seconds: Literal[43_200]
    passed: bool

    @model_validator(mode="after")
    def _reconcile_verdict(self) -> Self:
        if self.passed != (self.elapsed_seconds <= self.limit_seconds):
            raise ValueError("workflow runtime verdict does not reconcile")
        return self


@dataclass(frozen=True, slots=True)
class EvidenceOutcome:
    status: EvidenceStatus
    reason: OutcomeReason | None


def select_evidence_outcome(reasons: Iterable[OutcomeReason]) -> EvidenceOutcome:
    """Select the public status and primary reason from observed qualification outcomes.

    The input order is the lifecycle execution order. Trustworthy failures use
    their fixed semantic priority regardless of discovery order.
    """
    observed = tuple(dict.fromkeys(reasons))
    known_reasons = _FAILURE_REASONS | _INCOMPLETE_REASONS | _DIAGNOSTIC_REASONS
    if unknown := set(observed) - known_reasons:
        raise ValueError(f"unknown outcome reasons: {sorted(unknown)}")
    for reason in _FAILURE_REASON_PRIORITY:
        if reason in observed:
            return EvidenceOutcome(status="failed", reason=reason)
    for reason in observed:
        if reason in _INCOMPLETE_REASONS:
            return EvidenceOutcome(status="incomplete", reason=reason)
    if "reference-mismatch" in observed:
        return EvidenceOutcome(status="diagnostic", reason="reference-mismatch")
    if "explicit-diagnostic" in observed:
        return EvidenceOutcome(status="diagnostic", reason="explicit-diagnostic")
    return EvidenceOutcome(status="passing", reason=None)


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
    schema_version: Literal["2.0"] = SCALE_EVIDENCE_SCHEMA_VERSION
    status: EvidenceStatus
    tier: QualificationTier
    candidate_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    package_version: PublicLabel
    build_frontend_version: PublicLabel
    build_backend_version: PublicLabel
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
    preflight: PreflightEvidence | None
    outcome_reason: OutcomeReason | None
    file_count: Annotated[int, Field(gt=0)]
    corpus_bytes: Annotated[int, Field(ge=0)]
    stages: list[StageEvidence]
    totals: QualificationTotals
    thresholds: ThresholdVerdict | None
    workflow_runtime: WorkflowRuntimeVerdict | None

    @model_validator(mode="after")
    def _reconcile_public_evidence(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if set(self.artifact_schema_versions) != set(_ARTIFACT_SCHEMA_NAMES):
            raise ValueError(
                "artifact_schema_versions must contain the complete finite artifact set"
            )

        expected_reason_set: frozenset[OutcomeReason]
        if self.status == "passing":
            if self.outcome_reason is not None:
                raise ValueError("passing evidence must not carry an outcome reason")
        else:
            expected_reason_set = {
                "failed": _FAILURE_REASONS,
                "incomplete": _INCOMPLETE_REASONS,
                "diagnostic": _DIAGNOSTIC_REASONS,
            }[self.status]
            if self.outcome_reason not in expected_reason_set:
                raise ValueError("outcome reason does not match evidence status")

        stage_names = tuple(stage.stage for stage in self.stages)
        if stage_names != _STAGE_ORDER[: len(stage_names)]:
            raise ValueError("stages must be an ordered unique attempted prefix")
        if any(not stage.artifact_validated for stage in self.stages[:-1]):
            raise ValueError("an unvalidated stage must be the terminal attempted stage")

        validated_stages = {stage.stage for stage in self.stages if stage.artifact_validated}
        phase_totals = {
            "scan": (self.totals.scanned,),
            "plan": (self.totals.actions, self.totals.clean_noops, self.totals.plan_skips),
            "apply": (
                self.totals.applied,
                self.totals.apply_skips,
                self.totals.failures,
                self.totals.not_attempted,
            ),
            "verify": (self.totals.verified, self.totals.observed_findings),
        }
        for stage, totals in phase_totals.items():
            if stage not in validated_stages and any(totals):
                raise ValueError(f"{stage} totals must remain zero until its artifact is validated")

        trustworthy_failures: list[OutcomeReason] = []
        for stage in self.stages:
            expected_exit = 1 if stage.stage == "verify" and self.totals.expected_findings else 0
            if stage.completed and stage.exit_code != expected_exit:
                trustworthy_failures.append("stage-exit")
                break
        plan_total = self.totals.actions + self.totals.clean_noops + self.totals.plan_skips
        apply_total = (
            self.totals.applied
            + self.totals.apply_skips
            + self.totals.failures
            + self.totals.not_attempted
        )
        if (
            ("scan" in validated_stages and self.totals.scanned != self.file_count)
            or ("plan" in validated_stages and plan_total != self.totals.scanned)
            or (
                "apply" in validated_stages
                and (
                    apply_total != self.totals.actions
                    or self.totals.failures > 0
                    or self.totals.not_attempted > 0
                )
            )
            or ("verify" in validated_stages and self.totals.verified != self.totals.actions)
        ):
            trustworthy_failures.append("conservation-mismatch")
        if (
            "verify" in validated_stages
            and self.totals.observed_findings != self.totals.expected_findings
        ):
            trustworthy_failures.append("finding-mismatch")
        if self.thresholds is not None and not self.thresholds.passed:
            trustworthy_failures.append("threshold-exceeded")
        if self.workflow_runtime is not None and not self.workflow_runtime.passed:
            trustworthy_failures.append("runtime-limit-exceeded")

        if trustworthy_failures:
            selected_failure = select_evidence_outcome(trustworthy_failures)
            if (
                self.status != selected_failure.status
                or self.outcome_reason != selected_failure.reason
            ):
                raise ValueError(
                    "trustworthy failure status/reason must follow the fixed precedence"
                )
        elif self.status == "failed":
            raise ValueError("failed evidence requires a trustworthy observed failure")

        if self.status != "failed":
            if "scan" in validated_stages and self.totals.scanned != self.file_count:
                raise ValueError("validated scan totals must equal file_count")
            if "plan" in validated_stages and (
                self.totals.actions + self.totals.clean_noops + self.totals.plan_skips
                != self.totals.scanned
            ):
                raise ValueError("scan/plan totals do not conserve the corpus")
            terminal = (
                self.totals.applied
                + self.totals.apply_skips
                + self.totals.failures
                + self.totals.not_attempted
            )
            if "apply" in validated_stages and terminal != self.totals.actions:
                raise ValueError("apply totals do not reconcile with planned actions")
            if "verify" in validated_stages and self.totals.verified != self.totals.actions:
                raise ValueError("verified totals do not provide complete plan coverage")
            if (
                "verify" in validated_stages
                and self.totals.observed_findings != self.totals.expected_findings
            ):
                raise ValueError("observed findings do not match the expected findings")

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

        if self.tier == "release":
            if not self.stages and self.workflow_runtime is not None:
                raise ValueError("release workflow runtime must be null before scan dispatch")
            if self.stages and self.workflow_runtime is None:
                raise ValueError("release evidence requires workflow runtime after scan dispatch")
            if len(validated_stages) == len(_STAGE_ORDER) and self.workflow_runtime is not None:
                stage_elapsed = sum(stage.elapsed_seconds for stage in self.stages)
                if self.workflow_runtime.elapsed_seconds < stage_elapsed:
                    raise ValueError(
                        "complete release workflow runtime cannot understate stage elapsed time"
                    )
        elif self.workflow_runtime is not None:
            raise ValueError("only release evidence may carry workflow runtime")

        if self.status not in {"passing", "diagnostic"}:
            return self
        if self.preflight is None:
            raise ValueError("complete evidence requires a preflight result")
        if self.outcome_reason == "reference-mismatch":
            if (
                not self.preflight.filesystems
                or not all(item.passed for item in self.preflight.filesystems)
                or not self.preflight.capacity_margin_met
                or not self.preflight.ram_requirement_met
            ):
                raise ValueError(
                    "reference-mismatch diagnostics require all non-reference preflight checks"
                )
            if self.preflight.reference_environment_match and self.preflight.binding_filesystem:
                raise ValueError(
                    "reference-mismatch diagnostics require an actual reference mismatch"
                )
        elif not self.preflight.passed:
            raise ValueError("passing or explicit diagnostic evidence requires a passing preflight")
        if self.tier != "pr" and self.wheel_sha256 is None:
            raise ValueError("wheel_sha256 is required for complete installed-wheel evidence")
        if stage_names != _STAGE_ORDER or not all(
            stage.completed and stage.artifact_validated for stage in self.stages
        ):
            raise ValueError(
                "complete evidence requires artifact-validated scan, plan, apply, verify stages"
            )
        if any(stage.exit_code != 0 for stage in self.stages[:3]):
            raise ValueError("complete scan, plan, and apply must exit 0")
        expected_verify_exit = 1 if self.totals.expected_findings else 0
        if self.stages[3].exit_code != expected_verify_exit:
            raise ValueError("verify exit code does not reconcile with expected findings")
        if any(stage.vm_swap_peak_bytes is None for stage in self.stages):
            raise ValueError("complete binding evidence requires available child swap telemetry")
        if any(stage.vm_swap_peak_bytes != 0 for stage in self.stages):
            raise ValueError("complete binding evidence requires zero child swap")
        terminal = (
            self.totals.applied
            + self.totals.apply_skips
            + self.totals.failures
            + self.totals.not_attempted
        )
        if terminal != self.totals.actions:
            raise ValueError("apply totals do not reconcile with planned actions")
        if self.totals.failures or self.totals.not_attempted:
            raise ValueError("complete evidence cannot contain failures or not-attempted actions")
        if self.totals.verified != self.totals.actions:
            raise ValueError("complete evidence requires complete plan verification coverage")
        if self.totals.observed_findings != self.totals.expected_findings:
            raise ValueError("complete evidence requires exact expected finding totals")
        if self.tier in {"scheduled", "release"} and (
            self.thresholds is None or not self.thresholds.passed
        ):
            raise ValueError("complete scheduled/release evidence requires passing thresholds")
        if self.tier in {"scheduled", "release"} and self.threshold_baseline_sha256 is None:
            raise ValueError(
                "complete scheduled/release evidence requires threshold baseline provenance"
            )
        if self.tier == "release" and (
            self.workflow_runtime is None or not self.workflow_runtime.passed
        ):
            raise ValueError("complete release evidence requires a passing workflow runtime")
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
    schema_version: Literal["2.0"] = SCALE_THRESHOLDS_SCHEMA_VERSION
    reference_environment_sha256: Sha256
    measurement_points: tuple[ThresholdPointIdentity, ThresholdPointIdentity]
    target_file_count: Literal[1_000_000]
    fitting_method: Literal["exact-per-stage-linear-projection"]
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


@dataclass(frozen=True, slots=True)
class StageMemorySeries:
    stage: StageName
    rss_10k: int
    rss_100k: int

    def __post_init__(self) -> None:
        if self.stage not in _STAGE_ORDER:
            raise ValueError(f"unknown stage {self.stage}")
        if (
            type(self.rss_10k) is not int
            or type(self.rss_100k) is not int
            or self.rss_10k <= 0
            or self.rss_100k <= 0
        ):
            raise ValueError("stage RSS pilot values must be positive integers")


@dataclass(frozen=True, slots=True)
class ThresholdContext:
    baseline: ThresholdBaseline
    baseline_sha256: Sha256
    stage_memory: tuple[StageMemorySeries, ...]

    def __post_init__(self) -> None:
        if tuple(item.stage for item in self.stage_memory) != _STAGE_ORDER:
            raise ValueError("threshold context stage memory must follow stage order")
        if self.baseline.limits != derive_thresholds(self.stage_memory):
            raise ValueError("threshold context limits do not match its stage memory")


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


def _ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def _stage_growth(series: StageMemorySeries) -> Fraction:
    return max(Fraction(0), Fraction(series.rss_100k - series.rss_10k, 90_000))


def _project_stage_peak(series: StageMemorySeries, file_count: int) -> Fraction:
    growth = _stage_growth(series)
    return max(
        Fraction(series.rss_10k),
        Fraction(series.rss_100k),
        Fraction(series.rss_10k) + growth * (file_count - 10_000),
    )


def derive_thresholds(stage_memory: Iterable[StageMemorySeries]) -> ThresholdSet:
    """Derive the fixed 1M limits from four stage-aligned pilot series."""
    series = tuple(stage_memory)
    if tuple(item.stage for item in series) != _STAGE_ORDER:
        raise ValueError("stage memory must be ordered scan, plan, apply, verify")
    multiplier = Fraction(5, 4)
    return ThresholdSet(
        absolute_peak_rss_bytes=_ceil_fraction(
            max(_project_stage_peak(item, 1_000_000) for item in series) * multiplier
        ),
        slope_bytes_per_file=_ceil_fraction(
            max(_stage_growth(item) for item in series) * multiplier
        ),
        linearity_tolerance=0.2,
    )


def _ordinary_least_squares_slope(points: tuple[tuple[int, int], ...]) -> Fraction:
    count = len(points)
    sum_x = sum(x for x, _ in points)
    sum_y = sum(y for _, y in points)
    sum_xy = sum(x * y for x, y in points)
    sum_x_squared = sum(x * x for x, _ in points)
    denominator = count * sum_x_squared - sum_x * sum_x
    if denominator == 0:
        raise ValueError("memory points do not define a slope")
    return Fraction(count * sum_xy - sum_x * sum_y, denominator)


def _upward_rounded_ratio(value: Fraction) -> float:
    scale = 10**12
    return _ceil_fraction(value * scale) / scale


def evaluate_thresholds(
    context: ThresholdContext,
    *,
    file_count: Literal[100_000, 1_000_000],
    stage_peak_rss: Mapping[StageName, int],
) -> ThresholdVerdict:
    """Evaluate one scheduled or release observation without rereading pilot files."""
    if type(file_count) is not int or file_count not in (100_000, 1_000_000):
        raise ValueError("file_count must be 100000 or 1000000")
    if set(stage_peak_rss) != set(_STAGE_ORDER):
        raise ValueError("stage_peak_rss must contain scan, plan, apply, verify")
    if any(type(value) is not int or value <= 0 for value in stage_peak_rss.values()):
        raise ValueError("stage_peak_rss values must be positive integers")

    if file_count == 100_000:
        observed_slopes = (
            max(Fraction(0), Fraction(stage_peak_rss[item.stage] - item.rss_10k, 90_000))
            for item in context.stage_memory
        )
    else:
        observed_slopes = (
            max(
                Fraction(0),
                _ordinary_least_squares_slope(
                    (
                        (10_000, item.rss_10k),
                        (100_000, item.rss_100k),
                        (1_000_000, stage_peak_rss[item.stage]),
                    )
                ),
            )
            for item in context.stage_memory
        )
    observed_slope = max(observed_slopes)
    linearity = max(
        abs(Fraction(stage_peak_rss[item.stage]) - _project_stage_peak(item, file_count))
        / _project_stage_peak(item, file_count)
        for item in context.stage_memory
    )
    observed_peak = max(stage_peak_rss.values())
    limits = context.baseline.limits
    peak_passed = observed_peak <= limits.absolute_peak_rss_bytes
    slope_passed = observed_slope <= limits.slope_bytes_per_file
    linearity_passed = linearity <= Fraction(1, 5)
    return ThresholdVerdict(
        limits=limits,
        observed_peak_rss_bytes=observed_peak,
        observed_slope_bytes_per_file=_ceil_fraction(observed_slope),
        observed_linearity_ratio=_upward_rounded_ratio(linearity),
        peak_passed=peak_passed,
        slope_passed=slope_passed,
        linearity_passed=linearity_passed,
        passed=peak_passed and slope_passed and linearity_passed,
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
    try:
        revalidated = ScaleEvidence.model_validate(evidence.model_dump())
    except ModelValidationError as exc:
        raise ScaleEvidenceError(f"scale evidence changed after model validation ({exc})") from exc
    if revalidated.artifact_schema_versions != current_artifact_schema_versions():
        raise ScaleEvidenceError(
            "published artifact_schema_versions must match current code-owner versions"
        )
    if accepted and revalidated.status != "passing":
        raise ScaleEvidenceError("accepted evidence must have status passing")
    if accepted and revalidated.tier in {"scheduled", "release"}:
        if threshold_baseline_path is None:
            raise ScaleEvidenceError(
                "accepted scheduled/release evidence requires a validated threshold baseline"
            )
        baseline, digest = load_threshold_baseline_snapshot(
            threshold_baseline_path,
            reference_environment_sha256=revalidated.reference_environment_sha256,
        )
        if revalidated.threshold_baseline_sha256 != digest:
            raise ScaleEvidenceError(
                "accepted evidence threshold baseline digest does not match validated bytes"
            )
        if revalidated.thresholds is None or revalidated.thresholds.limits != baseline.limits:
            raise ScaleEvidenceError(
                "accepted evidence threshold limits do not match the validated baseline"
            )
    document = _validated_document(revalidated, "scale-evidence")
    write_json_artifact(document, path, clobber=False)


def write_reference_environment(environment: ReferenceEnvironment, path: Path) -> None:
    document = _validated_document(environment, "reference-environment")
    write_json_artifact(document, path, clobber=False)


def write_threshold_baseline(baseline: ThresholdBaseline, path: Path) -> None:
    document = _validated_document(baseline, "scale-thresholds")
    write_json_artifact(document, path, clobber=False)


def _read_payload(path: Path, *, description: str) -> tuple[bytes, object]:
    nofollow_flag = cast("int", getattr(os, "O_NOFOLLOW", 0))
    cloexec_flag = cast("int", getattr(os, "O_CLOEXEC", 0))
    nonblock_flag = cast("int", getattr(os, "O_NONBLOCK", 0))
    flags = os.O_RDONLY | nofollow_flag | cloexec_flag | nonblock_flag
    try:
        fd = os.open(path, flags)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError(f"{path} is not a regular file")
            chunks: list[bytes] = []
            while chunk := os.read(fd, 1 << 20):
                chunks.append(chunk)
            payload = b"".join(chunks)
        finally:
            os.close(fd)
    except (OSError, ValueError) as exc:
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
    nonblock_flag = cast("int", getattr(os, "O_NONBLOCK", 0))
    directory_flags = os.O_RDONLY | directory_flag | nofollow_flag | cloexec_flag
    file_flags = os.O_RDONLY | nofollow_flag | cloexec_flag | nonblock_flag
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


def read_reference_environment_snapshot(path: Path) -> tuple[ReferenceEnvironment, str]:
    """Read a validated reference model and digest from one no-follow file snapshot."""
    payload, document = _read_payload(path, description="reference environment")
    validate_qualification_document("reference-environment", document)
    try:
        environment = ReferenceEnvironment.model_validate_json(payload)
    except ModelValidationError as exc:
        raise ScaleEvidenceError(
            f"{path}: reference environment failed model validation ({exc})"
        ) from exc
    digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    return environment, digest


def read_reference_environment(path: Path) -> ReferenceEnvironment:
    return read_reference_environment_snapshot(path)[0]


def _threshold_point_stage_peaks(path: Path, evidence: ScaleEvidence) -> dict[StageName, int]:
    if evidence.tier != "pilot":
        raise ScaleEvidenceError(f"{path}: threshold evidence must use the pilot tier")
    if evidence.file_count == 100_000:
        if evidence.status != "passing":
            raise ScaleEvidenceError(f"{path}: 100000-file point must be passing")
    elif evidence.status not in {"passing", "diagnostic"} or (
        evidence.status == "diagnostic" and evidence.outcome_reason != "explicit-diagnostic"
    ):
        raise ScaleEvidenceError(
            f"{path}: 10000-file point must be passing-quality or explicitly diagnostic"
        )
    if evidence.preflight is None or not evidence.preflight.passed:
        raise ScaleEvidenceError(f"{path}: threshold evidence requires passing preflight")
    if evidence.memory_measurement != "external-rss":
        raise ScaleEvidenceError(f"{path}: threshold evidence requires external RSS")
    if evidence.cache_classification != "warm":
        raise ScaleEvidenceError(f"{path}: threshold evidence requires warm cache")
    if evidence.wheel_sha256 is None:
        raise ScaleEvidenceError(f"{path}: threshold evidence requires installed-wheel provenance")
    if tuple(stage.stage for stage in evidence.stages) != _STAGE_ORDER or not all(
        stage.completed and stage.artifact_validated for stage in evidence.stages
    ):
        raise ScaleEvidenceError(f"{path}: threshold evidence pipeline is incomplete")
    if any(stage.vm_swap_peak_bytes != 0 for stage in evidence.stages):
        raise ScaleEvidenceError(f"{path}: threshold evidence requires zero child swap")
    peaks: dict[StageName, int] = {}
    for stage in evidence.stages:
        if stage.peak_rss_bytes is None or stage.peak_rss_bytes <= 0:
            raise ScaleEvidenceError(f"{path}: threshold evidence has no usable RSS peak")
        peaks[stage.stage] = stage.peak_rss_bytes
    return peaks


def load_threshold_context(path: Path, *, reference_environment_sha256: Sha256) -> ThresholdContext:
    """Load one immutable baseline plus both stage-aligned pilot snapshots."""
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
    stage_peaks: list[dict[StageName, int]] = []
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
        pilot_evidence.append(evidence)
        stage_peaks.append(_threshold_point_stage_peaks(point_path, evidence))

    first, second = pilot_evidence
    first_provenance = (
        first.candidate_commit,
        first.package_version,
        first.build_frontend_version,
        first.build_backend_version,
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
        second.build_frontend_version,
        second.build_backend_version,
        second.wheel_sha256,
        second.lock_sha256,
        tuple(sorted(second.artifact_schema_versions.items())),
        second.python_version,
        second.kernel_version,
        second.cache_classification,
    )
    if first.wheel_sha256 is None or first_provenance != second_provenance:
        raise ScaleEvidenceError(f"{path}: pilot provenance mismatch between threshold points")

    ten_k_peaks, hundred_k_peaks = stage_peaks
    stage_memory = tuple(
        StageMemorySeries(
            stage=stage,
            rss_10k=ten_k_peaks[stage],
            rss_100k=hundred_k_peaks[stage],
        )
        for stage in _STAGE_ORDER
    )
    expected_limits = derive_thresholds(stage_memory)
    if baseline.limits != expected_limits:
        raise ScaleEvidenceError(f"{path}: threshold limits do not match the pinned pilot points")
    baseline_digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    return ThresholdContext(
        baseline=baseline,
        baseline_sha256=baseline_digest,
        stage_memory=stage_memory,
    )


def load_threshold_baseline_snapshot(
    path: Path, *, reference_environment_sha256: Sha256
) -> tuple[ThresholdBaseline, str]:
    """Load baseline compatibility data through the immutable threshold context."""
    context = load_threshold_context(
        path, reference_environment_sha256=reference_environment_sha256
    )
    return context.baseline, context.baseline_sha256


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
