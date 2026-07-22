"""Self-build and orchestrate the installed-wheel DMR-08 qualification lane."""

import argparse
import os
import platform
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Never, Protocol, cast

from docmend.artifacts import (
    ArtifactError,
    read_inventory,
    read_plan_snapshot,
    read_report_snapshot,
    read_verify_report,
)
from docmend.config import DocmendConfig
from docmend.scale_build import (
    BuildContractError,
    BuildRequest,
    CandidateBuild,
    CandidateWorkspaceLease,
    SourceProvenance,
    inspect_candidate_source,
    prepare_candidate,
    recheck_candidate_source,
)
from docmend.scale_corpus import (
    ScaleCorpusSummary,
    ScaleRecipeCounts,
    recipe_counts,
    summarize_scale_corpus,
)
from docmend.scale_evidence import (
    FILE_SIZE_RSS_LIMIT_BYTES,
    ArtifactSizeName,
    FileSizeCaseEvidence,
    FileSizeStageEvidence,
    OutcomeReason,
    PreflightEvidence,
    QualificationTotals,
    ReferenceEnvironment,
    ScaleEvidence,
    ScaleEvidenceError,
    StageEvidence,
    StageName,
    ThresholdContext,
    ThresholdVerdict,
    WorkflowRuntimeVerdict,
    current_artifact_schema_versions,
    evaluate_thresholds,
    load_threshold_context,
    read_reference_environment_snapshot,
    select_evidence_outcome,
    write_reference_environment,
    write_scale_evidence,
)
from docmend.scale_reconcile import (
    PipelinePaths,
    PipelineReconciliation,
    QualificationFailure,
    QualificationIncomplete,
    reconcile_pipeline,
    validate_pipeline_prefix,
)
from docmend.scale_resources import (
    INVENTORY_BYTES_PER_INPUT,
    MANIFEST_BYTES_PER_ACTION,
    PLAN_BYTES_PER_INPUT,
    REPORT_BYTES_PER_ACTION,
    STRUCTURED_LOG_BYTES_PER_INPUT_STAGE,
    SUPERVISOR_PRIVATE_BYTES_PER_FILE,
    VERIFY_BYTES_PER_INPUT,
    CapacityPlacement,
    Requirement,
    ResourcePreflightError,
    build_preflight_evidence,
    check_capacity,
    compare_reference_environment,
    observe_reference_environment,
    qualification_requirements,
    qualification_verify_stdout_allowance,
)
from docmend.scale_stage import (
    StageContractError,
    StageRequest,
    StageResult,
    load_stage_request,
    load_stage_result,
    write_stage_request,
)
from docmend.writer.manifest import read_manifest_chain

type BindingTier = Literal["pilot", "scheduled", "release", "file-size"]
type CardinalityTier = Literal["pilot", "scheduled", "release"]
_BINDING_COUNTS: Mapping[CardinalityTier, int] = MappingProxyType(
    {"pilot": 100_000, "scheduled": 100_000, "release": 1_000_000}
)
_BINDING_TIERS: tuple[BindingTier, ...] = ("pilot", "scheduled", "release", "file-size")
_STAGES = ("scan", "plan", "apply", "verify")


class QualificationInputError(Exception):
    """Invocation, provenance, or destination failed before evidence began."""


class QualificationHarnessError(Exception):
    """Evidence-model construction failed at execution time, not on input.

    Distinct from QualificationInputError so qualify()'s (OSError, ValueError)
    input-error mapping cannot mislabel a verdict-construction disagreement as
    exit 2. main() maps this to exit 1 with no evidence published (F-015).
    """


class ExecutionInterrupted(Exception):
    """Unexpected harness failure carrying the last internally valid checkpoint."""

    def __init__(self, checkpoint: ExecutionResult) -> None:
        super().__init__("qualification execution was interrupted")
        self.checkpoint = checkpoint


@dataclass(frozen=True, slots=True)
class FileSizeCase:
    """One identifier-free private matrix recipe."""

    size_mib: int
    encoding: Literal["utf-8", "windows-1252"]
    preservation: Literal["external", "tool"]


def file_size_cases(max_file_size_mib: int) -> tuple[FileSizeCase, ...]:
    """Derive the deterministic quartile matrix from the configured maximum.

    Quartiles round upward so a non-divisible maximum never understates a
    boundary. Duplicate sizes collapse for small configured maxima. Tool
    backups are limited to the two maximum-sized encoding cases.
    """

    if type(max_file_size_mib) is not int or max_file_size_mib < 1:
        raise ValueError("maximum file size must be a positive integer MiB value")
    sizes = tuple(
        sorted(
            {
                1,
                *((max_file_size_mib * numerator + 3) // 4 for numerator in range(1, 5)),
            }
        )
    )
    encodings: tuple[Literal["utf-8", "windows-1252"], ...] = (
        "utf-8",
        "windows-1252",
    )
    external = tuple(
        FileSizeCase(size_mib=size, encoding=encoding, preservation="external")
        for size in sizes
        for encoding in encodings
    )
    tool = tuple(
        FileSizeCase(
            size_mib=max_file_size_mib,
            encoding=encoding,
            preservation="tool",
        )
        for encoding in encodings
    )
    return tuple(dict.fromkeys((*external, *tool)))


@dataclass(frozen=True, slots=True)
class QualificationRequest:
    tier: BindingTier
    diagnostic: bool
    count: int
    repository: Path
    workspace: Path
    reference_environment: Path
    thresholds: Path | None
    evidence_out: Path
    accept_to: Path | None
    python_executable: Path


@dataclass(frozen=True, slots=True)
class ReferenceCaptureRequest:
    repository: Path
    workspace: Path
    output: Path


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Complete or phase-truthful output from the private execution service."""

    wheel_sha256: str | None
    preflight: PreflightEvidence | None
    stages: tuple[StageEvidence, ...]
    totals: QualificationTotals
    thresholds: ThresholdVerdict | None
    workflow_runtime: WorkflowRuntimeVerdict | None
    reasons: tuple[OutcomeReason, ...]
    started_at: datetime
    completed_at: datetime
    python_version: str
    kernel_version: str
    corpus_bytes: int
    file_size_cases: tuple[FileSizeCaseEvidence, ...] | None = None
    candidate: CandidateBuild | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    workspace_lease: CandidateWorkspaceLease | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True, slots=True)
class QualificationOutcome:
    evidence: ScaleEvidence
    exit_code: int
    evidence_published: bool
    accepted_path: Path | None


@dataclass(frozen=True, slots=True)
class QualificationWorkspacePaths:
    """Private deterministic paths beneath one never-reused build workspace."""

    root: Path
    pipeline: Path
    corpus: Path
    inventory: Path
    plan: Path
    report: Path
    verify_report: Path
    supervisor: Path

    @classmethod
    def beneath(cls, root: Path) -> QualificationWorkspacePaths:
        pipeline = root / "pipeline"
        return cls(
            root=root,
            pipeline=pipeline,
            corpus=pipeline / "corpus",
            inventory=pipeline / "inventory.json",
            plan=pipeline / "plan.json",
            report=pipeline / "report.json",
            verify_report=pipeline / "verify-report.json",
            supervisor=root / "supervisor",
        )

    def manifest(self, run_id: str) -> Path:
        return self.pipeline / ".docmend" / f"docmend-{run_id}-manifest.jsonl"

    def reconciliation(self) -> PipelinePaths:
        return PipelinePaths(
            pipeline=self.pipeline,
            corpus=self.corpus,
            inventory=self.inventory,
            plan=self.plan,
            report=self.report,
            verify_report=self.verify_report,
        )


@dataclass(frozen=True, slots=True)
class StageAccounting:
    scanned: int = 0
    actions: int = 0
    clean_noops: int = 0
    plan_skips: int = 0
    applied: int = 0
    apply_skips: int = 0
    failures: int = 0
    not_attempted: int = 0
    verified: int = 0
    observed_findings: int = 0


@dataclass(frozen=True, slots=True)
class StageArtifactObservation:
    run_id: str
    artifact_bytes: Mapping[ArtifactSizeName, int]
    accounting: StageAccounting
    capacity_estimate_exceeded: bool = False
    public_failure: Literal["conservation-mismatch", "finding-mismatch"] | None = None


@dataclass(frozen=True, slots=True)
class StageLaunch:
    wrapper_exit_code: int
    result: StageResult | None


class CandidateRuntime(Protocol):
    """Injectable private boundaries used by the real candidate pipeline."""

    def preflight(
        self,
        paths: QualificationWorkspacePaths,
        summary: ScaleCorpusSummary,
        reference: ReferenceEnvironment,
    ) -> PreflightEvidence: ...

    def materialize(
        self,
        path: Path,
        count: int,
        *,
        fragment_size: int,
    ) -> ScaleCorpusSummary: ...

    def launch(
        self,
        candidate: CandidateBuild,
        request: StageRequest,
        *,
        private_workspace: Path,
        on_dispatch: Callable[[], None],
    ) -> StageLaunch: ...

    def validate_artifact(
        self,
        stage: str,
        result: StageResult,
        *,
        paths: QualificationWorkspacePaths,
        private_workspace: Path,
        count: int,
        planned_actions: int,
        allowances: Mapping[str, int],
    ) -> StageArtifactObservation: ...

    def reconcile(
        self,
        paths: PipelinePaths,
        *,
        count: int,
    ) -> PipelineReconciliation: ...

    def monotonic(self) -> float: ...

    def now(self) -> datetime: ...


class CandidateBuilder(Protocol):
    def prepare(
        self,
        request: QualificationRequest,
        source: SourceProvenance,
    ) -> CandidateBuild: ...


@dataclass(frozen=True, slots=True)
class FileSizeRunResult:
    preflight: PreflightEvidence | None
    cases: tuple[FileSizeCaseEvidence, ...]
    reasons: tuple[OutcomeReason, ...]


class FileSizeRuntime(Protocol):
    def run_file_size_matrix(
        self,
        request: QualificationRequest,
        candidate: CandidateBuild,
        reference_environment: ReferenceEnvironment,
        recipes: tuple[FileSizeCase, ...],
    ) -> FileSizeRunResult: ...


class QualificationServices(Protocol):
    """High-level seams around private IO used by the public lifecycle."""

    def inspect_source(self, repository: Path) -> SourceProvenance: ...

    def load_reference(self, path: Path) -> tuple[ReferenceEnvironment, str]: ...

    def load_threshold(self, path: Path, reference_sha256: str) -> ThresholdContext: ...

    def execute(
        self,
        request: QualificationRequest,
        source: SourceProvenance,
        reference: ReferenceEnvironment,
        reference_sha256: str,
        threshold_context: ThresholdContext | None,
    ) -> ExecutionResult: ...

    def recheck_source(self, source: SourceProvenance) -> None: ...

    def publish(
        self,
        evidence: ScaleEvidence,
        path: Path,
        *,
        accepted: bool,
        threshold_path: Path | None,
    ) -> None: ...


class ReferenceCaptureServices(Protocol):
    def observe(self, workspace: Path) -> ReferenceEnvironment: ...

    def publish_reference(self, environment: ReferenceEnvironment, path: Path) -> None: ...


@dataclass(frozen=True, slots=True)
class _HeldDirectory:
    path: Path
    descriptor: int = field(repr=False)
    device: int
    inode: int

    @classmethod
    def open(cls, path: Path) -> _HeldDirectory:
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            metadata = os.fstat(descriptor)
            held = cls(
                path=path, descriptor=descriptor, device=metadata.st_dev, inode=metadata.st_ino
            )
            held.require_current_identity()
        except OSError, ValueError:
            os.close(descriptor)
            raise
        return held

    def require_current_identity(self) -> None:
        held = os.fstat(self.descriptor)
        current = self.path.lstat()
        if (
            not stat.S_ISDIR(held.st_mode)
            or not stat.S_ISDIR(current.st_mode)
            or (held.st_dev, held.st_ino) != (self.device, self.inode)
            or (current.st_dev, current.st_ino) != (self.device, self.inode)
            or self.path.resolve(strict=True) != self.path
        ):
            raise OSError("held publication directory identity changed")

    def close(self) -> None:
        os.close(self.descriptor)


@dataclass(frozen=True, slots=True)
class _PublicationTarget:
    directory: _HeldDirectory
    name: str

    @property
    def lexical_path(self) -> Path:
        return self.directory.path / self.name

    @property
    def bound_path(self) -> Path:
        return Path(f"/proc/self/fd/{self.directory.descriptor}") / self.name

    @property
    def key(self) -> tuple[int, int, str]:
        return self.directory.device, self.directory.inode, self.name

    def require_absent(self) -> None:
        self.directory.require_current_identity()
        try:
            os.stat(self.name, dir_fd=self.directory.descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise FileExistsError(f"publication destination already exists: {self.lexical_path}")


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise QualificationInputError(message)


def _parser() -> _ArgumentParser:
    parser = _ArgumentParser(prog="qualify_scale.py", allow_abbrev=False)
    parser.add_argument("--capture-reference", action="store_true")
    parser.add_argument("--tier", choices=_BINDING_TIERS)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--count", type=int)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reference-environment", type=Path)
    parser.add_argument("--thresholds", type=Path)
    parser.add_argument("--evidence-out", type=Path)
    parser.add_argument("--accept-to", type=Path)
    return parser


def _real_root(cwd: Path | None) -> Path:
    root = Path.cwd() if cwd is None else cwd
    try:
        metadata = root.lstat()
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise QualificationInputError("repository must be an existing directory") from exc
    if root.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise QualificationInputError("repository must be a real directory")
    return resolved


def _absolute(path: Path) -> Path:
    return path.absolute().resolve(strict=False)


def _real_parent(path: Path, *, label: str) -> None:
    parent = path.parent
    try:
        metadata = parent.lstat()
        resolved = parent.resolve(strict=True)
    except OSError as exc:
        raise QualificationInputError(f"{label} parent must be an existing directory") from exc
    if parent.is_symlink() or not stat.S_ISDIR(metadata.st_mode) or resolved != parent:
        raise QualificationInputError(f"{label} parent must be a real directory")


def _absent_external(path: Path, repository: Path, *, label: str) -> Path:
    value = _absolute(path)
    _real_parent(value, label=label)
    if value.exists() or value.is_symlink():
        raise QualificationInputError(f"{label} must be absent")
    if value.is_relative_to(repository):
        raise QualificationInputError(f"{label} must be outside the repository checkout")
    return value


def _existing_file(path: Path, *, label: str) -> Path:
    value = _absolute(path)
    try:
        metadata = value.lstat()
    except OSError as exc:
        raise QualificationInputError(f"{label} must be an existing regular file") from exc
    if value.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise QualificationInputError(f"{label} must be an existing regular file")
    return value


def _existing_directory(path: Path, *, label: str) -> Path:
    value = _absolute(path)
    try:
        metadata = value.lstat()
        resolved = value.resolve(strict=True)
    except OSError as exc:
        raise QualificationInputError(f"{label} must be an existing real directory") from exc
    if value.is_symlink() or not stat.S_ISDIR(metadata.st_mode) or resolved != value:
        raise QualificationInputError(f"{label} must be an existing real directory")
    return value


def parse_args(
    argv: Sequence[str] | None = None,
    *,
    cwd: Path | None = None,
) -> QualificationRequest | ReferenceCaptureRequest:
    """Parse and fully preflight the finite Task 6B invocation surface."""

    arguments = tuple(sys.argv[1:] if argv is None else argv)
    values = _parser().parse_args(arguments)
    repository = _real_root(cwd)
    if values.capture_reference:
        qualification_values = (
            values.tier,
            values.diagnostic,
            values.count,
            values.reference_environment,
            values.thresholds,
            values.evidence_out,
            values.accept_to,
        )
        if any(value not in (None, False) for value in qualification_values):
            raise QualificationInputError("--capture-reference is exclusive of qualification flags")
        if values.workspace is None or values.output is None:
            raise QualificationInputError("--capture-reference requires --workspace and --output")
        workspace = _absent_external(values.workspace, repository, label="workspace")
        output = _absent_external(values.output, repository, label="output")
        if workspace == output:
            raise QualificationInputError("workspace and output must be distinct")
        return ReferenceCaptureRequest(
            repository=repository,
            workspace=workspace,
            output=output,
        )

    if values.output is not None:
        raise QualificationInputError("--output is exclusive to --capture-reference")
    if values.tier is None:
        raise QualificationInputError("qualification requires --tier")
    if values.workspace is None:
        raise QualificationInputError("qualification requires --workspace")
    if values.reference_environment is None:
        raise QualificationInputError("qualification requires --reference-environment")
    if values.evidence_out is None:
        raise QualificationInputError("qualification requires --evidence-out")
    tier = cast("BindingTier", values.tier)
    if tier == "file-size":
        if values.count is not None:
            raise QualificationInputError("file-size qualification derives its matrix from config")
        if values.thresholds is not None:
            raise QualificationInputError("file-size qualification does not accept --thresholds")
        count = len(file_size_cases(DocmendConfig().limits.max_file_size_mib))
    else:
        cardinality_tier = tier
        if values.count is not None and not values.diagnostic:
            raise QualificationInputError(
                "binding tier count is fixed; --count requires --diagnostic"
            )
        if (
            values.count is not None
            and cardinality_tier != "pilot"
            and values.count != _BINDING_COUNTS[cardinality_tier]
        ):
            raise QualificationInputError(
                "--count override is supported only for pilot diagnostic qualification"
            )
        count = _BINDING_COUNTS[cardinality_tier] if values.count is None else values.count
        if type(count) is not int or not 1 <= count <= 1_000_000:
            raise QualificationInputError("--count must be an integer from 1 to 1000000")
        if cardinality_tier in {"scheduled", "release"} and values.thresholds is None:
            raise QualificationInputError(f"{tier} qualification requires --thresholds")
        if cardinality_tier == "pilot" and values.thresholds is not None:
            raise QualificationInputError("pilot qualification does not accept --thresholds")
    if values.diagnostic and values.accept_to is not None:
        raise QualificationInputError("diagnostic qualification cannot accept evidence")
    if tier == "file-size" and not values.diagnostic and values.accept_to is None:
        raise QualificationInputError("binding file-size qualification requires --accept-to")
    accept_to = (
        _existing_directory(values.accept_to, label="accept-to")
        if values.accept_to is not None
        else None
    )
    workspace = _absent_external(values.workspace, repository, label="workspace")
    evidence_out = _absent_external(
        values.evidence_out,
        repository,
        label="evidence output",
    )
    if workspace == evidence_out:
        raise QualificationInputError("workspace and evidence output must be distinct")
    return QualificationRequest(
        tier=tier,
        diagnostic=values.diagnostic,
        count=count,
        repository=repository,
        workspace=workspace,
        reference_environment=_existing_file(
            values.reference_environment,
            label="reference environment",
        ),
        thresholds=(
            _existing_file(values.thresholds, label="thresholds")
            if values.thresholds is not None
            else None
        ),
        evidence_out=evidence_out,
        accept_to=accept_to,
        python_executable=Path(sys.executable).resolve(strict=True),
    )


class _SummaryLike(Protocol):
    @property
    def count(self) -> int: ...

    @property
    def recipe_counts(self) -> ScaleRecipeCounts: ...


def qualification_named_allowances(
    summary: _SummaryLike,
) -> Mapping[str, Mapping[str, int]]:
    """Return all public stage-size ceilings from the scale resource constants."""

    action_count = summary.recipe_counts.actions
    structured = STRUCTURED_LOG_BYTES_PER_INPUT_STAGE * summary.count
    private_output = SUPERVISOR_PRIVATE_BYTES_PER_FILE
    verify_stdout = qualification_verify_stdout_allowance(
        expected_findings=summary.recipe_counts.skips
    )
    values: dict[str, Mapping[str, int]] = {
        "scan": MappingProxyType(
            {
                "inventory": INVENTORY_BYTES_PER_INPUT * summary.count,
                "structured-log": structured,
                "stdout-log": private_output,
                "stderr-log": private_output,
            }
        ),
        "plan": MappingProxyType(
            {
                "plan": PLAN_BYTES_PER_INPUT * summary.count,
                "structured-log": structured,
                "stdout-log": private_output,
                "stderr-log": private_output,
            }
        ),
        "apply": MappingProxyType(
            {
                "report": REPORT_BYTES_PER_ACTION * action_count,
                "manifest": MANIFEST_BYTES_PER_ACTION * action_count,
                "structured-log": structured,
                "stdout-log": private_output,
                "stderr-log": private_output,
            }
        ),
        "verify": MappingProxyType(
            {
                "verify-report": VERIFY_BYTES_PER_INPUT * summary.count,
                "structured-log": structured,
                "stdout-log": verify_stdout,
                "stderr-log": private_output,
            }
        ),
    }
    return MappingProxyType(values)


def accepted_evidence_name(commit: str, tier: BindingTier, count: int) -> str:
    if not len(commit) == 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError("candidate commit must be exactly 40 lowercase hex characters")
    if tier == "file-size":
        return f"{commit}-file-size.json"
    if tier not in _BINDING_COUNTS:
        raise ValueError("accepted evidence tier is unsupported")
    if type(count) is not int or count <= 0:
        raise ValueError("accepted evidence count must be positive")
    return f"{commit}-{tier}-{count}.json"


def _mkdir_private(path: Path) -> None:
    try:
        path.mkdir(mode=0o700)
        path.chmod(0o700, follow_symlinks=False)
    except OSError as exc:
        raise RuntimeError(
            f"private qualification directory could not be created: {path.name}"
        ) from exc


def _stage_private_environment(
    candidate: CandidateBuild,
    private_workspace: Path,
) -> dict[str, str]:
    roots = {
        "HOME": private_workspace / "home",
        "XDG_STATE_HOME": private_workspace / "state",
        "XDG_CONFIG_HOME": private_workspace / "config",
        "TMPDIR": private_workspace / "tmp",
    }
    for path in roots.values():
        _mkdir_private(path)
    return {
        **{name: str(path) for name, path in roots.items()},
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": f"{candidate.venv / 'bin'}:{os.defpath}",
        "PYTHONNOUSERSITE": "1",
        "TZ": "UTC",
    }


def build_stage_request(
    stage: str,
    candidate: CandidateBuild,
    paths: QualificationWorkspacePaths,
    *,
    private_workspace: Path,
    manifest_path: Path | None,
) -> StageRequest:
    """Construct one exact candidate-CLI request with private fixed environment."""

    candidate.require_current_identity()
    executable = str(candidate.executable)
    if stage == "scan":
        argv = (executable, "scan", str(paths.corpus), "--report", str(paths.inventory))
    elif stage == "plan":
        argv = (
            executable,
            "plan",
            "--inventory",
            str(paths.inventory),
            "--out",
            str(paths.plan),
        )
    elif stage == "apply":
        argv = (
            executable,
            "apply",
            str(paths.plan),
            "--write",
            "--preserved-by",
            "external",
            "--report",
            str(paths.report),
        )
    elif stage == "verify":
        if manifest_path is None:
            raise ValueError("verify request requires the validated apply manifest")
        argv = (
            executable,
            "verify",
            str(paths.corpus),
            "--plan",
            str(paths.plan),
            "--manifest",
            str(manifest_path),
            "--report",
            str(paths.report),
            "--out",
            str(paths.verify_report),
        )
    else:
        raise ValueError("stage must name scan, plan, apply, or verify")
    request = StageRequest(
        stage=stage,
        argv=argv,
        cwd=paths.pipeline,
        environment=_stage_private_environment(candidate, private_workspace),
        stdout=f"{stage}.stdout",
        stderr=f"{stage}.stderr",
    )
    candidate.require_current_identity()
    return request


def _regular_size(path: Path, *, kind: str) -> int:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise ArtifactError(f"{kind} is missing or not a no-follow file") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ArtifactError(f"{kind} is not a regular file")
        return metadata.st_size
    finally:
        os.close(descriptor)


@dataclass(frozen=True, slots=True)
class _DefaultCandidateBuilder:
    def prepare(
        self,
        request: QualificationRequest,
        source: SourceProvenance,
    ) -> CandidateBuild:
        return prepare_candidate(
            BuildRequest(
                repository=request.repository,
                workspace=request.workspace,
                python_executable=request.python_executable,
            ),
            source=source,
        )


def _materialize_file_size_case(path: Path, recipe: FileSizeCase) -> int:
    _mkdir_private(path)
    target = path / "input.txt"
    total = recipe.size_mib * 1024**2
    pattern = (
        "café résumé UTF-8\r\n".encode()
        if recipe.encoding == "utf-8"
        else "café déjà vu Windows\r\n".encode("windows-1252")
    )
    descriptor = os.open(
        target,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
    )
    try:

        def write_all(data: bytes) -> None:
            remaining_data = memoryview(data)
            while remaining_data:
                written = os.write(descriptor, remaining_data)
                if written <= 0:
                    raise OSError("file-size materialization made no progress")
                remaining_data = remaining_data[written:]

        chunk = pattern * max(1, (1024 * 1024) // len(pattern))
        remaining = total
        while remaining >= len(chunk):
            write_all(chunk)
            remaining -= len(chunk)
        if remaining:
            repeats, padding = divmod(remaining, len(pattern))
            write_all(pattern * repeats + b"x" * padding)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return total


def _file_size_stage_request(
    stage: str,
    candidate: CandidateBuild,
    paths: QualificationWorkspacePaths,
    recipe: FileSizeCase,
    *,
    private_workspace: Path,
    manifest_path: Path | None,
) -> StageRequest:
    candidate.require_current_identity()
    executable = str(candidate.executable)
    if stage == "scan":
        argv = (executable, "scan", str(paths.corpus), "--report", str(paths.inventory))
    elif stage == "plan":
        argv = (
            executable,
            "plan",
            "--inventory",
            str(paths.inventory),
            "--out",
            str(paths.plan),
        )
    elif stage == "apply":
        preservation = (
            ("--preserved-by", "external")
            if recipe.preservation == "external"
            else ("--backup-dir", str(paths.root / "backups"))
        )
        argv = (
            executable,
            "apply",
            str(paths.plan),
            "--write",
            *preservation,
            "--report",
            str(paths.report),
        )
    elif stage == "verify":
        if manifest_path is None:
            raise ValueError("file-size verify requires a validated apply manifest")
        argv = (
            executable,
            "verify",
            str(paths.corpus),
            "--plan",
            str(paths.plan),
            "--manifest",
            str(manifest_path),
            "--report",
            str(paths.report),
            "--out",
            str(paths.verify_report),
        )
    else:
        raise ValueError("unknown file-size stage")
    return StageRequest(
        stage=stage,
        argv=argv,
        cwd=paths.pipeline,
        environment=_stage_private_environment(candidate, private_workspace),
        stdout=f"{stage}.stdout",
        stderr=f"{stage}.stderr",
    )


def _incomplete_file_size_stage(
    stage: StageName, *, elapsed_seconds: float = 0.0
) -> FileSizeStageEvidence:
    return FileSizeStageEvidence(
        stage=stage,
        elapsed_seconds=elapsed_seconds,
        peak_rss_bytes=None,
        vm_swap_peak_bytes=None,
        exit_code=None,
        completed=False,
        artifact_validated=False,
        timeout_outcome="not-measured",
        backup_bytes=0,
    )


def _file_size_case_evidence(
    recipe: FileSizeCase,
    stages: Sequence[FileSizeStageEvidence],
    *,
    scanned_files: int,
    scanned_bytes: int,
    planned_actions: int,
    applied_actions: int,
    verified_actions: int,
    expected_findings: int,
    observed_findings: int,
) -> FileSizeCaseEvidence:
    stage_tuple = tuple(stages)
    peak = max(
        (stage.peak_rss_bytes or 0 for stage in stage_tuple),
        default=0,
    )
    backup_bytes = sum(stage.backup_bytes for stage in stage_tuple)
    rss_passed = peak < FILE_SIZE_RSS_LIMIT_BYTES
    watchdog_passed = all(stage.timeout_outcome != "watchdog-timeout" for stage in stage_tuple)
    source_bytes = recipe.size_mib * 1024**2
    coverage_reconciled = (
        scanned_files == planned_actions == applied_actions == verified_actions == 1
        and scanned_bytes == source_bytes
    )
    findings_reconciled = expected_findings == observed_findings
    complete = tuple(stage.stage for stage in stage_tuple) == _STAGES and all(
        stage.completed
        and stage.artifact_validated
        and stage.exit_code == 0
        and stage.vm_swap_peak_bytes == 0
        for stage in stage_tuple
    )
    backup_ok = recipe.preservation == "external" or backup_bytes == source_bytes
    return FileSizeCaseEvidence(
        size_mib=recipe.size_mib,
        encoding=recipe.encoding,
        preservation=recipe.preservation,
        source_bytes=source_bytes,
        stages=stage_tuple,
        backup_bytes=backup_bytes,
        scanned_files=scanned_files,
        scanned_bytes=scanned_bytes,
        planned_actions=planned_actions,
        applied_actions=applied_actions,
        verified_actions=verified_actions,
        expected_findings=expected_findings,
        observed_findings=observed_findings,
        peak_rss_bytes=peak,
        rss_limit_bytes=FILE_SIZE_RSS_LIMIT_BYTES,
        rss_passed=rss_passed,
        watchdog_passed=watchdog_passed,
        coverage_reconciled=coverage_reconciled,
        findings_reconciled=findings_reconciled,
        passed=(
            complete
            and backup_ok
            and rss_passed
            and watchdog_passed
            and coverage_reconciled
            and findings_reconciled
        ),
    )


@dataclass(frozen=True, slots=True)
class DefaultCandidateRuntime:
    """Real Linux resource, supervisor, artifact, and reconciliation service."""

    def preflight(
        self,
        paths: QualificationWorkspacePaths,
        summary: ScaleCorpusSummary,
        reference: ReferenceEnvironment,
    ) -> PreflightEvidence:
        observation = observe_reference_environment(paths.root)
        comparison = compare_reference_environment(
            observation.environment,
            reference,
            mount_projection=observation.mount_projection,
        )
        with ExitStack() as stack:
            placements = tuple(
                stack.enter_context(
                    CapacityPlacement(
                        path=path,
                        fragment_size=os.statvfs(path).f_frsize,
                    )
                )
                for path in (
                    paths.root,
                    paths.pipeline,
                    paths.pipeline,
                    paths.supervisor,
                )
            )
            requirements = qualification_requirements(
                workspace=placements[0],
                corpus=placements[1],
                artifact=placements[2],
                supervisor=placements[3],
                summary=summary,
            )
            capacity = check_capacity(requirements)
        return build_preflight_evidence(capacity, comparison)

    def run_file_size_matrix(
        self,
        request: QualificationRequest,
        candidate: CandidateBuild,
        reference_environment: ReferenceEnvironment,
        recipes: tuple[FileSizeCase, ...],
    ) -> FileSizeRunResult:
        checkpoint_started = datetime.now(UTC)
        candidate.require_current_identity()
        matrix_root = request.workspace / "file-size"
        _mkdir_private(matrix_root)
        observation = observe_reference_environment(request.workspace)
        comparison = compare_reference_environment(
            observation.environment,
            reference_environment,
            mount_projection=observation.mount_projection,
        )
        source_bytes = sum(recipe.size_mib * 1024**2 for recipe in recipes)
        tool_backup_bytes = sum(
            recipe.size_mib * 1024**2 for recipe in recipes if recipe.preservation == "tool"
        )
        fragment_size = os.statvfs(request.workspace).f_frsize
        with CapacityPlacement(
            path=request.workspace,
            fragment_size=fragment_size,
        ) as placement:
            capacity = check_capacity(
                (
                    Requirement(
                        path=request.workspace,
                        bytes=2 * source_bytes + tool_backup_bytes + 256 * 1024**2,
                        inodes=32 * len(recipes) + 64,
                        placement=placement,
                    ),
                )
            )
        preflight = build_preflight_evidence(capacity, comparison)
        reasons: list[OutcomeReason] = []
        capacity_ok = (
            bool(preflight.filesystems)
            and all(item.passed for item in preflight.filesystems)
            and preflight.capacity_margin_met
            and preflight.ram_requirement_met
        )
        if not capacity_ok:
            return FileSizeRunResult(
                preflight=preflight,
                cases=tuple(_pending_file_size_case(recipe) for recipe in recipes),
                reasons=("capacity-insufficient",),
            )
        if not preflight.reference_environment_match or not preflight.binding_filesystem:
            reasons.append("reference-mismatch")

        case_evidence: list[FileSizeCaseEvidence] = []

        def interrupt(
            exc: Exception,
            *,
            current_case: FileSizeCaseEvidence | None,
            next_recipe_index: int,
        ) -> Never:
            cases = (
                *case_evidence,
                *((current_case,) if current_case is not None else ()),
                *(_pending_file_size_case(recipe) for recipe in recipes[next_recipe_index:]),
            )
            raise ExecutionInterrupted(
                ExecutionResult(
                    wheel_sha256=candidate.wheel_sha256,
                    preflight=preflight,
                    stages=(),
                    totals=_zero_qualification_totals(),
                    thresholds=None,
                    workflow_runtime=None,
                    reasons=tuple(dict.fromkeys(reasons)),
                    started_at=checkpoint_started,
                    completed_at=max(checkpoint_started, datetime.now(UTC)),
                    python_version=platform.python_version(),
                    kernel_version=platform.release(),
                    corpus_bytes=sum(case.source_bytes for case in cases),
                    file_size_cases=cases,
                    candidate=candidate,
                    workspace_lease=candidate.workspace_lease,
                )
            ) from exc

        for index, recipe in enumerate(recipes):
            try:
                candidate.require_current_identity()
            except BuildContractError:
                case_evidence.extend(
                    _pending_file_size_case(pending) for pending in recipes[index:]
                )
                reasons.append("provenance-changed")
                break
            case_root = matrix_root / f"case-{index:02d}"
            try:
                _mkdir_private(case_root)
                paths = QualificationWorkspacePaths.beneath(case_root)
                _mkdir_private(paths.pipeline)
                _mkdir_private(paths.supervisor)
                _materialize_file_size_case(paths.corpus, recipe)
            except OSError:
                case_evidence.append(_pending_file_size_case(recipe))
                reasons.append("corpus-materialization-failed")
                continue
            except Exception as exc:
                interrupt(exc, current_case=None, next_recipe_index=index)
            stages: list[FileSizeStageEvidence] = []
            scanned_files = 0
            scanned_bytes = 0
            planned_actions = 0
            applied_actions = 0
            verified_actions = 0
            expected_findings = 0
            observed_findings = 0
            manifest_path: Path | None = None
            case_failed = False
            provenance_changed = False

            for stage in _STAGES:
                private_workspace = paths.supervisor / stage
                try:
                    _mkdir_private(private_workspace)
                    stage_request = _file_size_stage_request(
                        stage,
                        candidate,
                        paths,
                        recipe,
                        private_workspace=private_workspace,
                        manifest_path=manifest_path,
                    )
                    launch = self.launch(
                        candidate,
                        stage_request,
                        private_workspace=private_workspace,
                        on_dispatch=lambda: None,
                    )
                except BuildContractError:
                    stages.append(_incomplete_file_size_stage(stage))
                    reasons.append("provenance-changed")
                    case_failed = True
                    provenance_changed = True
                    break
                except OSError, RuntimeError, StageContractError, ValueError:
                    stages.append(_incomplete_file_size_stage(stage))
                    reasons.append("supervisor-failed")
                    case_failed = True
                    break
                except Exception as exc:
                    stages.append(_incomplete_file_size_stage(stage))
                    current_case = _file_size_case_evidence(
                        recipe,
                        stages,
                        scanned_files=scanned_files,
                        scanned_bytes=scanned_bytes,
                        planned_actions=planned_actions,
                        applied_actions=applied_actions,
                        verified_actions=verified_actions,
                        expected_findings=expected_findings,
                        observed_findings=observed_findings,
                    )
                    interrupt(
                        exc,
                        current_case=current_case,
                        next_recipe_index=index + 1,
                    )
                result = launch.result
                if launch.wrapper_exit_code != 0 or result is None or not result.completed:
                    stages.append(
                        _incomplete_file_size_stage(
                            stage,
                            elapsed_seconds=(result.elapsed_seconds if result is not None else 0.0),
                        )
                    )
                    reasons.append("supervisor-failed")
                    case_failed = True
                    break
                if (
                    result.stage != stage
                    or result.stdout != stage_request.stdout
                    or result.stderr != stage_request.stderr
                    or result.peak_rss_bytes is None
                    or result.exit_code is None
                ):
                    stages.append(
                        _incomplete_file_size_stage(stage, elapsed_seconds=result.elapsed_seconds)
                    )
                    reasons.append("supervisor-failed")
                    case_failed = True
                    break

                timeout_outcome: Literal[
                    "within-budget", "watchdog-timeout", "not-applicable", "not-measured"
                ] = "not-measured" if stage in {"scan", "plan"} else "not-applicable"
                backup_bytes = 0
                artifact_validated = False
                try:
                    if stage == "scan":
                        inventory = read_inventory(paths.inventory)
                        scanned_files = inventory.totals.files
                        scanned_bytes = sum(item.size_bytes for item in inventory.files)
                        timeout_outcome = (
                            "watchdog-timeout"
                            if inventory.totals.skipped_by_reason.timeout
                            else "within-budget"
                        )
                        if (
                            scanned_files != 1
                            or inventory.totals.skipped != 0
                            or len(inventory.files) != 1
                            or scanned_bytes != recipe.size_mib * 1024**2
                        ):
                            reasons.append("conservation-mismatch")
                            case_failed = True
                    elif stage == "plan":
                        plan, _plan_sha256 = read_plan_snapshot(paths.plan)
                        planned_actions = plan.totals.actions
                        timeout_outcome = (
                            "watchdog-timeout"
                            if any(skip.reason == "timeout" for skip in plan.skips)
                            else "within-budget"
                        )
                        if planned_actions != 1 or plan.totals.skips != 0:
                            reasons.append("conservation-mismatch")
                            case_failed = True
                    elif stage == "apply":
                        report, _report_sha256 = read_report_snapshot(paths.report)
                        applied_actions = report.totals.applied
                        manifest_path = paths.manifest(report.run_id)
                        chain = read_manifest_chain(
                            (manifest_path,),
                            check_backup_objects=recipe.preservation == "tool",
                        )
                        backup_paths = {
                            record.backup_path
                            for manifest_set in chain.sets
                            for record in manifest_set.records
                            if record.backup_path is not None
                        }
                        backup_bytes = sum(
                            Path(path).stat(follow_symlinks=False).st_size for path in backup_paths
                        )
                        if (
                            applied_actions != 1
                            or report.totals.failed
                            or report.totals.not_attempted
                        ):
                            reasons.append("conservation-mismatch")
                            case_failed = True
                        # A tool-preservation backup whose size diverges from the
                        # source is a conservation defect the count checks above
                        # cannot see; mirror _file_size_case_evidence's backup_ok
                        # (backup_bytes == source_bytes) so the case fails with a
                        # reason instead of passing into evidence construction and
                        # tripping _reconcile_file_size_tier's ValueError (F-014).
                        if (
                            recipe.preservation == "tool"
                            and backup_bytes != recipe.size_mib * 1024**2
                        ):
                            reasons.append("conservation-mismatch")
                            case_failed = True
                    else:
                        verify_report = read_verify_report(paths.verify_report)
                        verified_actions = verify_report.checked_files
                        observed_findings = len(verify_report.findings)
                        if observed_findings != expected_findings:
                            reasons.append("finding-mismatch")
                            case_failed = True
                    artifact_validated = True
                except ArtifactError, OSError, ValueError:
                    reasons.append("artifact-invalid")
                    case_failed = True
                except Exception as exc:
                    stages.append(
                        FileSizeStageEvidence(
                            stage=stage,
                            elapsed_seconds=result.elapsed_seconds,
                            peak_rss_bytes=result.peak_rss_bytes,
                            vm_swap_peak_bytes=result.vm_swap_peak_bytes,
                            exit_code=result.exit_code,
                            completed=True,
                            artifact_validated=False,
                            timeout_outcome=(
                                "not-measured" if stage in {"scan", "plan"} else "not-applicable"
                            ),
                            backup_bytes=0,
                        )
                    )
                    current_case = _file_size_case_evidence(
                        recipe,
                        stages,
                        scanned_files=scanned_files,
                        scanned_bytes=scanned_bytes,
                        planned_actions=planned_actions,
                        applied_actions=applied_actions,
                        verified_actions=verified_actions,
                        expected_findings=expected_findings,
                        observed_findings=observed_findings,
                    )
                    interrupt(
                        exc,
                        current_case=current_case,
                        next_recipe_index=index + 1,
                    )

                stages.append(
                    FileSizeStageEvidence(
                        stage=stage,
                        elapsed_seconds=result.elapsed_seconds,
                        peak_rss_bytes=result.peak_rss_bytes,
                        vm_swap_peak_bytes=result.vm_swap_peak_bytes,
                        exit_code=result.exit_code,
                        completed=True,
                        artifact_validated=artifact_validated,
                        timeout_outcome=timeout_outcome,
                        backup_bytes=backup_bytes,
                    )
                )
                if result.exit_code != 0:
                    reasons.append("stage-exit")
                    case_failed = True
                if result.vm_swap_peak_bytes is None or result.vm_swap_peak_bytes != 0:
                    reasons.append("telemetry-unavailable")
                    case_failed = True
                if timeout_outcome == "watchdog-timeout":
                    reasons.append("threshold-exceeded")
                    case_failed = True
                if result.peak_rss_bytes >= FILE_SIZE_RSS_LIMIT_BYTES:
                    reasons.append("threshold-exceeded")
                    case_failed = True
                if case_failed:
                    break

            try:
                completed_case = _file_size_case_evidence(
                    recipe,
                    stages,
                    scanned_files=scanned_files,
                    scanned_bytes=scanned_bytes,
                    planned_actions=planned_actions,
                    applied_actions=applied_actions,
                    verified_actions=verified_actions,
                    expected_findings=expected_findings,
                    observed_findings=observed_findings,
                )
            except Exception as exc:
                interrupt(exc, current_case=None, next_recipe_index=index)
            case_evidence.append(completed_case)
            if provenance_changed:
                case_evidence.extend(
                    _pending_file_size_case(pending) for pending in recipes[index + 1 :]
                )
                break
        try:
            candidate.require_current_identity()
        except BuildContractError:
            reasons.append("provenance-changed")
        except Exception as exc:
            interrupt(exc, current_case=None, next_recipe_index=len(recipes))
        return FileSizeRunResult(
            preflight=preflight,
            cases=tuple(case_evidence),
            reasons=tuple(dict.fromkeys(reasons)),
        )

    def materialize(
        self,
        path: Path,
        count: int,
        *,
        fragment_size: int,
    ) -> ScaleCorpusSummary:
        from docmend.scale_corpus import materialize_scale_corpus

        return materialize_scale_corpus(path, count, fragment_size=fragment_size)

    def launch(
        self,
        candidate: CandidateBuild,
        request: StageRequest,
        *,
        private_workspace: Path,
        on_dispatch: Callable[[], None],
    ) -> StageLaunch:
        request_path = private_workspace / "request.json"
        result_path = private_workspace / "result.json"
        write_stage_request(request, request_path)
        if load_stage_request(request_path) != request:
            raise StageContractError("stage request round-trip mismatch")
        environment = {
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": os.environ.get("PATH", os.defpath),
            "PYTHONNOUSERSITE": "1",
            "TZ": "UTC",
        }
        candidate.require_current_identity()
        on_dispatch()
        try:
            completed = subprocess.run(
                (
                    str(candidate.venv_python),
                    "-I",
                    str(candidate.source_snapshot / "scripts/measure_scale_stage.py"),
                    str(request_path),
                    str(result_path),
                ),
                cwd=private_workspace,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        finally:
            candidate.require_current_identity()
        if completed.returncode != 0:
            return StageLaunch(wrapper_exit_code=completed.returncode, result=None)
        return StageLaunch(
            wrapper_exit_code=0,
            result=load_stage_result(result_path),
        )

    def validate_artifact(
        self,
        stage: str,
        result: StageResult,
        *,
        paths: QualificationWorkspacePaths,
        private_workspace: Path,
        count: int,
        planned_actions: int,
        allowances: Mapping[str, int],
    ) -> StageArtifactObservation:
        prefix = validate_pipeline_prefix(
            paths.reconciliation(),
            count=count,
            through=stage,
        )
        artifact_bytes = cast(
            "dict[ArtifactSizeName, int]",
            {
                "stdout-log": _regular_size(
                    private_workspace / result.stdout,
                    kind=f"{stage} stdout",
                ),
                "stderr-log": _regular_size(
                    private_workspace / result.stderr,
                    kind=f"{stage} stderr",
                ),
                **prefix.artifact_bytes,
            },
        )
        if stage == "scan":
            accounting = StageAccounting(scanned=prefix.scanned_files)
        elif stage == "plan":
            accounting = StageAccounting(
                actions=prefix.planned_actions,
                clean_noops=prefix.plan_noops,
                plan_skips=prefix.plan_skips,
            )
        elif stage == "apply":
            accounting = StageAccounting(
                applied=prefix.applied_actions,
                apply_skips=prefix.apply_skips,
                failures=prefix.failures,
                not_attempted=prefix.not_attempted,
            )
        elif stage == "verify":
            accounting = StageAccounting(
                verified=prefix.verified_actions,
                observed_findings=prefix.observed_findings,
            )
        else:
            raise ArtifactError("unknown qualification stage")
        request_size = _regular_size(private_workspace / "request.json", kind="stage request")
        result_size = _regular_size(private_workspace / "result.json", kind="stage result")
        exceeded = (
            request_size > SUPERVISOR_PRIVATE_BYTES_PER_FILE
            or result_size > SUPERVISOR_PRIVATE_BYTES_PER_FILE
            or any(size > allowances[name] for name, size in artifact_bytes.items())
        )
        return StageArtifactObservation(
            run_id=prefix.run_id,
            artifact_bytes=MappingProxyType(artifact_bytes),
            accounting=accounting,
            capacity_estimate_exceeded=exceeded,
            public_failure=prefix.public_failure,
        )

    def reconcile(
        self,
        paths: PipelinePaths,
        *,
        count: int,
    ) -> PipelineReconciliation:
        return reconcile_pipeline(paths, count=count, _allow_public_mismatch=True)

    def monotonic(self) -> float:
        return time.monotonic()

    def now(self) -> datetime:
        return datetime.now(UTC)


_DEFAULT_BUILDER = _DefaultCandidateBuilder()
_DEFAULT_RUNTIME = DefaultCandidateRuntime()


@dataclass(frozen=True, slots=True)
class DefaultQualificationServices:
    builder: CandidateBuilder = field(default=_DEFAULT_BUILDER, repr=False)
    runtime: CandidateRuntime | FileSizeRuntime = field(default=_DEFAULT_RUNTIME, repr=False)

    def inspect_source(self, repository: Path) -> SourceProvenance:
        return inspect_candidate_source(repository)

    def load_reference(self, path: Path) -> tuple[ReferenceEnvironment, str]:
        return read_reference_environment_snapshot(path)

    def load_threshold(self, path: Path, reference_sha256: str) -> ThresholdContext:
        return load_threshold_context(path, reference_environment_sha256=reference_sha256)

    def execute(
        self,
        request: QualificationRequest,
        source: SourceProvenance,
        reference: ReferenceEnvironment,
        reference_sha256: str,
        threshold_context: ThresholdContext | None,
    ) -> ExecutionResult:
        if request.tier == "file-size":
            return execute_file_size_lane(
                request,
                source,
                reference,
                builder=self.builder,
                runtime=cast("FileSizeRuntime", self.runtime),
            )
        return _execute_default(
            request,
            source,
            reference,
            reference_sha256,
            threshold_context,
            builder=self.builder,
            runtime=cast("CandidateRuntime", self.runtime),
        )

    def recheck_source(self, source: SourceProvenance) -> None:
        recheck_candidate_source(source)

    def publish(
        self,
        evidence: ScaleEvidence,
        path: Path,
        *,
        accepted: bool,
        threshold_path: Path | None,
    ) -> None:
        write_scale_evidence(
            evidence,
            path,
            accepted=accepted,
            threshold_baseline_path=threshold_path,
        )


_DEFAULT_SERVICES = DefaultQualificationServices()


def _empty_totals(count: int) -> QualificationTotals:
    return QualificationTotals(
        scanned=0,
        actions=0,
        clean_noops=0,
        plan_skips=0,
        applied=0,
        apply_skips=0,
        failures=0,
        not_attempted=0,
        verified=0,
        expected_findings=recipe_counts(count).skips,
        observed_findings=0,
    )


def _zero_qualification_totals() -> QualificationTotals:
    return QualificationTotals(
        scanned=0,
        actions=0,
        clean_noops=0,
        plan_skips=0,
        applied=0,
        apply_skips=0,
        failures=0,
        not_attempted=0,
        verified=0,
        expected_findings=0,
        observed_findings=0,
    )


def _pending_file_size_case(recipe: FileSizeCase) -> FileSizeCaseEvidence:
    return FileSizeCaseEvidence(
        size_mib=recipe.size_mib,
        encoding=recipe.encoding,
        preservation=recipe.preservation,
        source_bytes=recipe.size_mib * 1024**2,
        stages=(),
        backup_bytes=0,
        scanned_files=0,
        scanned_bytes=0,
        planned_actions=0,
        applied_actions=0,
        verified_actions=0,
        expected_findings=0,
        observed_findings=0,
        peak_rss_bytes=0,
        rss_limit_bytes=FILE_SIZE_RSS_LIMIT_BYTES,
        rss_passed=True,
        watchdog_passed=True,
        coverage_reconciled=False,
        findings_reconciled=True,
        passed=False,
    )


def execute_file_size_lane(
    request: QualificationRequest,
    source: SourceProvenance,
    reference_environment: ReferenceEnvironment,
    *,
    builder: CandidateBuilder,
    runtime: FileSizeRuntime,
) -> ExecutionResult:
    """Build the inspected candidate and execute its complete file-size matrix."""

    if request.tier != "file-size":
        raise ValueError("file-size execution requires the file-size tier")
    started = datetime.now(UTC)
    recipes = file_size_cases(DocmendConfig().limits.max_file_size_mib)
    try:
        candidate = builder.prepare(request, source)
    except BuildContractError as exc:
        reason: OutcomeReason
        if exc.failure_kind == "build":
            reason = "build-failed"
        elif exc.failure_kind == "install":
            reason = "install-failed"
        else:
            reason = "provenance-changed"
        return ExecutionResult(
            wheel_sha256=exc.wheel_sha256,
            preflight=None,
            stages=(),
            totals=_zero_qualification_totals(),
            thresholds=None,
            workflow_runtime=None,
            reasons=(reason,),
            started_at=started,
            completed_at=datetime.now(UTC),
            python_version=platform.python_version(),
            kernel_version=platform.release(),
            corpus_bytes=sum(recipe.size_mib * 1024**2 for recipe in recipes),
            file_size_cases=tuple(_pending_file_size_case(recipe) for recipe in recipes),
            workspace_lease=exc.workspace_lease,
        )
    if candidate.commit != source.commit:
        candidate.workspace_lease.close()
        raise BuildContractError("candidate build commit disagrees with inspected HEAD")
    try:
        result = runtime.run_file_size_matrix(
            request,
            candidate,
            reference_environment,
            recipes,
        )
    except ExecutionInterrupted as exc:
        raise ExecutionInterrupted(replace(exc.checkpoint, started_at=started)) from exc
    except Exception as exc:
        pending = tuple(_pending_file_size_case(recipe) for recipe in recipes)
        raise ExecutionInterrupted(
            ExecutionResult(
                wheel_sha256=candidate.wheel_sha256,
                preflight=None,
                stages=(),
                totals=_zero_qualification_totals(),
                thresholds=None,
                workflow_runtime=None,
                reasons=(),
                started_at=started,
                completed_at=max(started, datetime.now(UTC)),
                python_version=platform.python_version(),
                kernel_version=platform.release(),
                corpus_bytes=sum(case.source_bytes for case in pending),
                file_size_cases=pending,
                candidate=candidate,
                workspace_lease=candidate.workspace_lease,
            )
        ) from exc
    reasons = list(result.reasons)
    if any(
        stage.completed and stage.exit_code != 0 for case in result.cases for stage in case.stages
    ):
        reasons.append("stage-exit")
    if any(
        case.has_trustworthy_conservation_failure() or case.has_trustworthy_backup_failure()
        for case in result.cases
    ):
        reasons.append("conservation-mismatch")
    if any(case.has_trustworthy_finding_failure() for case in result.cases):
        reasons.append("finding-mismatch")
    if any(not case.rss_passed or not case.watchdog_passed for case in result.cases):
        reasons.append("threshold-exceeded")
    return ExecutionResult(
        wheel_sha256=candidate.wheel_sha256,
        preflight=result.preflight,
        stages=(),
        totals=_zero_qualification_totals(),
        thresholds=None,
        workflow_runtime=None,
        reasons=tuple(dict.fromkeys(reasons)),
        started_at=started,
        completed_at=datetime.now(UTC),
        python_version=platform.python_version(),
        kernel_version=platform.release(),
        corpus_bytes=sum(case.source_bytes for case in result.cases),
        file_size_cases=result.cases,
        candidate=candidate,
        workspace_lease=candidate.workspace_lease,
    )


def _execute_default(
    request: QualificationRequest,
    source: SourceProvenance,
    _reference: ReferenceEnvironment,
    _reference_sha256: str,
    _threshold_context: ThresholdContext | None,
    *,
    builder: CandidateBuilder,
    runtime: CandidateRuntime,
) -> ExecutionResult:
    """Private execution implementation; completed below the public lifecycle."""

    started = datetime.now(UTC)
    fragment_size = os.statvfs(request.workspace.parent).f_frsize
    summary = summarize_scale_corpus(request.count, fragment_size=fragment_size)
    try:
        candidate = builder.prepare(request, source)
    except BuildContractError as exc:
        if exc.failure_kind == "build":
            reason: OutcomeReason = "build-failed"
        elif exc.failure_kind == "install":
            reason = "install-failed"
        else:
            reason = "provenance-changed"
        return ExecutionResult(
            wheel_sha256=exc.wheel_sha256,
            preflight=None,
            stages=(),
            totals=(
                _zero_qualification_totals()
                if request.tier == "file-size"
                else _empty_totals(request.count)
            ),
            thresholds=None,
            workflow_runtime=None,
            reasons=(reason,),
            started_at=started,
            completed_at=datetime.now(UTC),
            python_version=platform.python_version(),
            kernel_version=platform.release(),
            corpus_bytes=summary.file_bytes,
            workspace_lease=exc.workspace_lease,
        )
    return _run_candidate_pipeline(
        request,
        source,
        candidate,
        summary,
        _reference,
        _reference_sha256,
        _threshold_context,
        started=started,
        runtime=runtime,
    )


def _run_candidate_pipeline(
    request: QualificationRequest,
    source: SourceProvenance,
    candidate: CandidateBuild,
    summary: ScaleCorpusSummary,
    reference: ReferenceEnvironment,
    reference_sha256: str,
    threshold_context: ThresholdContext | None,
    *,
    started: datetime,
    runtime: CandidateRuntime,
) -> ExecutionResult:
    del source, reference_sha256
    paths = QualificationWorkspacePaths.beneath(request.workspace)
    stages: list[StageEvidence] = []
    reasons: list[OutcomeReason] = []
    preflight: PreflightEvidence | None = None
    threshold_verdict: ThresholdVerdict | None = None
    workflow_runtime: WorkflowRuntimeVerdict | None = None
    totals = _empty_totals(request.count)
    workflow_started: float | None = None
    workflow_ended: float | None = None

    def finalize_workflow_runtime() -> None:
        nonlocal workflow_runtime
        if request.tier != "release" or workflow_started is None:
            return
        ended = workflow_ended if workflow_ended is not None else workflow_started
        outer_elapsed = max(0.0, ended - workflow_started)
        public_elapsed = max(outer_elapsed, sum(stage.elapsed_seconds for stage in stages))
        workflow_runtime = WorkflowRuntimeVerdict(
            elapsed_seconds=public_elapsed,
            limit_seconds=43_200,
            passed=public_elapsed <= 43_200,
        )
        if not workflow_runtime.passed and "runtime-limit-exceeded" not in reasons:
            reasons.append("runtime-limit-exceeded")

    def finish() -> ExecutionResult:
        finalize_workflow_runtime()
        try:
            completed_at = max(started, runtime.now())
        except Exception:
            completed_at = max(started, datetime.now(UTC))
        return ExecutionResult(
            wheel_sha256=candidate.wheel_sha256,
            preflight=preflight,
            stages=tuple(stages),
            totals=totals,
            thresholds=threshold_verdict,
            workflow_runtime=workflow_runtime,
            reasons=tuple(reasons),
            started_at=started,
            completed_at=completed_at,
            python_version=platform.python_version(),
            kernel_version=platform.release(),
            corpus_bytes=summary.file_bytes,
            candidate=candidate,
            workspace_lease=candidate.workspace_lease,
        )

    def checked_monotonic() -> float:
        try:
            return runtime.monotonic()
        except Exception as exc:
            if "harness-error" not in reasons:
                reasons.append("harness-error")
            raise ExecutionInterrupted(finish()) from exc

    def mark_workflow_end() -> None:
        nonlocal workflow_ended
        if workflow_started is not None:
            workflow_ended = checked_monotonic()

    def workspace_is_current() -> bool:
        try:
            candidate.require_current_identity()
        except BuildContractError:
            if "harness-error" not in reasons:
                reasons.append("harness-error")
            return False
        return True

    if not workspace_is_current():
        return finish()
    try:
        _mkdir_private(paths.pipeline)
        _mkdir_private(paths.supervisor)
    except OSError, RuntimeError:
        reasons.append("harness-error")
        return finish()
    except Exception as exc:
        reasons.append("harness-error")
        raise ExecutionInterrupted(finish()) from exc
    try:
        preflight = runtime.preflight(paths, summary, reference)
    except OSError, ResourcePreflightError, ValueError:
        reasons.append("reference-observation-unavailable")
        return finish()
    except Exception as exc:
        reasons.append("harness-error")
        raise ExecutionInterrupted(finish()) from exc
    if not workspace_is_current():
        return finish()
    capacity_ok = (
        bool(preflight.filesystems)
        and all(item.passed for item in preflight.filesystems)
        and preflight.capacity_margin_met
        and preflight.ram_requirement_met
    )
    if not capacity_ok:
        reasons.append("capacity-insufficient")
        return finish()
    if not preflight.reference_environment_match or not preflight.binding_filesystem:
        reasons.append("reference-mismatch")

    try:
        materialized = runtime.materialize(
            paths.corpus,
            request.count,
            fragment_size=summary.fragment_size,
        )
    except OSError, RuntimeError, ValueError:
        reasons.append("corpus-materialization-failed")
        return finish()
    except Exception as exc:
        reasons.append("harness-error")
        raise ExecutionInterrupted(finish()) from exc
    if not workspace_is_current():
        return finish()
    if materialized != summary:
        reasons.append("corpus-materialization-failed")
        return finish()

    allowances = qualification_named_allowances(summary)
    manifest_path: Path | None = None
    for stage in _STAGES:
        if not workspace_is_current():
            break
        private_workspace = paths.supervisor / stage
        try:
            _mkdir_private(private_workspace)
            stage_request = build_stage_request(
                stage,
                candidate,
                paths,
                private_workspace=private_workspace,
                manifest_path=manifest_path,
            )
        except OSError, RuntimeError, StageContractError, ValueError:
            reasons.append("harness-error")
            break
        except Exception as exc:
            reasons.append("harness-error")
            raise ExecutionInterrupted(finish()) from exc
        if not workspace_is_current():
            break
        dispatched = False

        def on_dispatch(current_stage: str = stage) -> None:
            nonlocal dispatched, workflow_started
            if current_stage == "scan" and request.tier == "release":
                workflow_started = checked_monotonic()
            dispatched = True

        try:
            launch = runtime.launch(
                candidate,
                stage_request,
                private_workspace=private_workspace,
                on_dispatch=on_dispatch,
            )
        except ExecutionInterrupted:
            raise
        except OSError, RuntimeError, StageContractError:
            if dispatched:
                stages.append(_incomplete_stage(stage))
            reasons.append("supervisor-failed")
            mark_workflow_end()
            break
        except Exception as exc:
            if dispatched:
                stages.append(_incomplete_stage(stage))
            reasons.append("harness-error")
            mark_workflow_end()
            raise ExecutionInterrupted(finish()) from exc
        if not dispatched:
            reasons.append("harness-error")
            break
        if not workspace_is_current():
            stages.append(
                _incomplete_stage(
                    stage,
                    elapsed=launch.result.elapsed_seconds if launch.result is not None else 0.0,
                )
            )
            mark_workflow_end()
            break
        result = launch.result
        if launch.wrapper_exit_code != 0 or result is None:
            stages.append(_incomplete_stage(stage))
            reasons.append("supervisor-failed")
            mark_workflow_end()
            break
        if (
            result.stage != stage
            or result.stdout != stage_request.stdout
            or result.stderr != stage_request.stderr
        ):
            stages.append(_incomplete_stage(stage, elapsed=result.elapsed_seconds))
            reasons.append("supervisor-failed")
            mark_workflow_end()
            break
        if not result.completed:
            stages.append(_incomplete_stage(stage, elapsed=result.elapsed_seconds))
            reasons.append("supervisor-failed")
            mark_workflow_end()
            break
        assert result.peak_rss_bytes is not None
        assert result.exit_code is not None
        expected_exit = 1 if stage == "verify" and totals.expected_findings else 0
        unexpected_exit = result.exit_code != expected_exit
        try:
            observation = runtime.validate_artifact(
                stage,
                result,
                paths=paths,
                private_workspace=private_workspace,
                count=request.count,
                planned_actions=totals.actions,
                allowances=allowances[stage],
            )
        except (
            ArtifactError,
            OSError,
            QualificationFailure,
            QualificationIncomplete,
            ValueError,
        ):
            stages.append(
                _measured_stage(
                    stage,
                    result,
                    summary=summary,
                    file_units=_stage_file_units(stage, request.count, totals.actions),
                    run_id=None,
                    artifact_bytes={},
                )
            )
            if unexpected_exit:
                reasons.append("stage-exit")
            reasons.append("artifact-invalid")
            mark_workflow_end()
            break
        except Exception as exc:
            stages.append(
                _measured_stage(
                    stage,
                    result,
                    summary=summary,
                    file_units=_stage_file_units(stage, request.count, totals.actions),
                    run_id=None,
                    artifact_bytes={},
                )
            )
            reasons.append("harness-error")
            raise ExecutionInterrupted(finish()) from exc
        stages.append(
            _measured_stage(
                stage,
                result,
                summary=summary,
                file_units=_stage_file_units(stage, request.count, totals.actions),
                run_id=observation.run_id,
                artifact_bytes=observation.artifact_bytes,
            )
        )
        totals = _merge_accounting(totals, observation.accounting)
        if unexpected_exit:
            reasons.append("stage-exit")
        if observation.public_failure is not None:
            reasons.append(observation.public_failure)
        if not workspace_is_current():
            mark_workflow_end()
            break
        if stage == "apply":
            manifest_path = paths.manifest(observation.run_id)
        if unexpected_exit or observation.public_failure is not None:
            mark_workflow_end()
            break
        if result.vm_swap_peak_bytes is None or result.vm_swap_peak_bytes != 0:
            reasons.append("telemetry-unavailable")
            mark_workflow_end()
            break
        if observation.capacity_estimate_exceeded:
            reasons.append("capacity-estimate-exceeded")
            mark_workflow_end()
            break
        mark_workflow_end()

    complete_stages = len(stages) == 4 and all(stage.artifact_validated for stage in stages)
    blocking = any(reason not in {"reference-mismatch"} for reason in reasons)
    if complete_stages and not blocking and workspace_is_current():
        try:
            reconciliation = runtime.reconcile(paths.reconciliation(), count=request.count)
            _require_reconciliation_matches_stages(reconciliation, stages)
        except QualificationIncomplete:
            reasons.append("artifact-invalid")
        except QualificationFailure as exc:
            reasons.append(
                "finding-mismatch" if str(exc) == "finding-mismatch" else "conservation-mismatch"
            )
        except Exception as exc:
            reasons.append("harness-error")
            raise ExecutionInterrupted(finish()) from exc
        else:
            totals = QualificationTotals(
                scanned=reconciliation.scanned_files,
                actions=reconciliation.planned_actions,
                clean_noops=reconciliation.plan_noops,
                plan_skips=reconciliation.plan_skips,
                applied=reconciliation.applied_actions,
                apply_skips=0,
                failures=0,
                not_attempted=0,
                verified=reconciliation.verified_actions,
                expected_findings=sum(reconciliation.expected_findings.values()),
                observed_findings=sum(reconciliation.observed_findings.values()),
            )
            if reconciliation.public_failure is not None:
                reasons.append(reconciliation.public_failure)
            elif request.tier in {"scheduled", "release"}:
                if threshold_context is None:
                    reasons.append("harness-error")
                else:
                    peaks: dict[StageName, int] = {
                        stage.stage: cast("int", stage.peak_rss_bytes) for stage in stages
                    }
                    try:
                        threshold_verdict = evaluate_thresholds(
                            threshold_context,
                            file_count=cast("Literal[100_000, 1_000_000]", request.count),
                            stage_peak_rss=peaks,
                        )
                    except ValueError:
                        reasons.append("harness-error")
                    else:
                        if not threshold_verdict.passed:
                            reasons.append("threshold-exceeded")
        workspace_is_current()

    if request.tier == "release" and workflow_started is not None:
        if workflow_ended is None:
            mark_workflow_end()
        finalize_workflow_runtime()
    return finish()


def _incomplete_stage(stage: str, *, elapsed: float = 0.0) -> StageEvidence:
    return StageEvidence(
        stage=cast("Literal['scan', 'plan', 'apply', 'verify']", stage),
        run_id=None,
        elapsed_seconds=elapsed,
        files_per_second=0.0,
        bytes_per_second=0.0,
        peak_rss_bytes=None,
        python_allocation_peak_bytes=None,
        vm_swap_peak_bytes=None,
        exit_code=None,
        completed=False,
        artifact_validated=False,
        artifact_bytes={},
    )


def _stage_file_units(stage: str, count: int, planned_actions: int) -> int:
    return count if stage in {"scan", "plan"} else planned_actions


def _measured_stage(
    stage: str,
    result: StageResult,
    *,
    summary: ScaleCorpusSummary,
    file_units: int,
    run_id: str | None,
    artifact_bytes: Mapping[ArtifactSizeName, int],
) -> StageEvidence:
    elapsed = result.elapsed_seconds
    return StageEvidence(
        stage=cast("Literal['scan', 'plan', 'apply', 'verify']", stage),
        run_id=run_id,
        elapsed_seconds=elapsed,
        files_per_second=(file_units / elapsed if elapsed else 0.0),
        bytes_per_second=(summary.file_bytes / elapsed if elapsed else 0.0),
        peak_rss_bytes=result.peak_rss_bytes,
        python_allocation_peak_bytes=None,
        vm_swap_peak_bytes=result.vm_swap_peak_bytes,
        exit_code=result.exit_code,
        completed=True,
        artifact_validated=run_id is not None,
        artifact_bytes=dict(artifact_bytes),
    )


def _merge_accounting(
    totals: QualificationTotals,
    accounting: StageAccounting,
) -> QualificationTotals:
    return totals.model_copy(
        update={
            "scanned": totals.scanned + accounting.scanned,
            "actions": totals.actions + accounting.actions,
            "clean_noops": totals.clean_noops + accounting.clean_noops,
            "plan_skips": totals.plan_skips + accounting.plan_skips,
            "applied": totals.applied + accounting.applied,
            "apply_skips": totals.apply_skips + accounting.apply_skips,
            "failures": totals.failures + accounting.failures,
            "not_attempted": totals.not_attempted + accounting.not_attempted,
            "verified": totals.verified + accounting.verified,
            "observed_findings": totals.observed_findings + accounting.observed_findings,
        }
    )


def _require_reconciliation_matches_stages(
    reconciliation: PipelineReconciliation,
    stages: Sequence[StageEvidence],
) -> None:
    run_ids = {stage.stage: stage.run_id for stage in stages}
    if run_ids != reconciliation.stage_run_ids:
        raise QualificationIncomplete("reconciliation run IDs disagree with stage artifacts")
    for stage in stages:
        if stage.run_id is None:
            raise QualificationIncomplete("validated stage lost its run ID")
        for name, size in stage.artifact_bytes.items():
            if name == "structured-log":
                expected = reconciliation.structured_log_bytes[stage.stage]
            elif name in {"stdout-log", "stderr-log"}:
                continue
            else:
                expected = reconciliation.artifact_bytes[name]
            if size != expected:
                raise QualificationIncomplete("reconciliation artifact sizes disagree with stages")


def _precheck_acceptance(
    request: QualificationRequest,
    source: SourceProvenance,
    directory: _HeldDirectory | None,
) -> _PublicationTarget | None:
    if directory is None:
        return None
    target = _PublicationTarget(
        directory,
        accepted_evidence_name(source.commit, request.tier, request.count),
    )
    target.require_absent()
    return target


def _evidence(
    request: QualificationRequest,
    source: SourceProvenance,
    reference_sha256: str,
    threshold_context: ThresholdContext | None,
    execution: ExecutionResult,
    reasons: tuple[OutcomeReason, ...],
) -> ScaleEvidence:
    outcome = select_evidence_outcome(reasons)
    return ScaleEvidence(
        status=outcome.status,
        tier=request.tier,
        candidate_commit=source.commit,
        package_version=source.package_version,
        build_frontend_version=source.build_frontend_version,
        build_backend_version=source.build_backend_version,
        wheel_sha256=execution.wheel_sha256,
        lock_sha256=source.lock_sha256,
        reference_environment_sha256=reference_sha256,
        threshold_baseline_sha256=(
            threshold_context.baseline_sha256 if threshold_context is not None else None
        ),
        artifact_schema_versions=current_artifact_schema_versions(),
        python_version=execution.python_version,
        kernel_version=execution.kernel_version,
        memory_measurement="external-rss",
        cache_classification="warm",
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        preflight=execution.preflight,
        outcome_reason=outcome.reason,
        file_count=request.count,
        corpus_bytes=execution.corpus_bytes,
        stages=list(execution.stages),
        totals=execution.totals,
        thresholds=execution.thresholds,
        workflow_runtime=execution.workflow_runtime,
        file_size_cases=execution.file_size_cases,
        configured_max_file_size_mib=(
            DocmendConfig().limits.max_file_size_mib if request.tier == "file-size" else None
        ),
    )


def _publish_execution(
    request: QualificationRequest,
    services: QualificationServices,
    source: SourceProvenance,
    reference_sha256: str,
    threshold_context: ThresholdContext | None,
    execution: ExecutionResult,
    evidence_target: _PublicationTarget,
    accepted_target: _PublicationTarget | None,
) -> QualificationOutcome:
    """Publish evidence even when the retained private identity is invalid."""

    try:

        def require_private_identity() -> None:
            if execution.candidate is not None:
                execution.candidate.require_current_identity()
            elif execution.workspace_lease is not None:
                execution.workspace_lease.require_current_identity()

        reasons = execution.reasons
        try:
            require_private_identity()
        except BuildContractError:
            if "harness-error" not in reasons:
                reasons = (*reasons, "harness-error")
        if request.diagnostic:
            reasons = (*reasons, "explicit-diagnostic")
        try:
            services.recheck_source(source)
        except BuildContractError, OSError:
            reasons = (*reasons, "provenance-changed")
        try:
            evidence = _evidence(
                request,
                source,
                reference_sha256,
                threshold_context,
                execution,
                reasons,
            )
        except ValueError as exc:
            # A selector/model-validator disagreement (pydantic ValidationError
            # subclasses ValueError) is an execution-time harness fault, not a bad
            # invocation. Route it to exit 1 with nothing published instead of
            # letting qualify's (OSError, ValueError) map it to exit 2 (F-015).
            raise QualificationHarnessError(str(exc)) from exc
        try:
            evidence_target.require_absent()
            services.publish(
                evidence,
                evidence_target.bound_path,
                accepted=False,
                threshold_path=request.thresholds,
            )
            evidence_target.directory.require_current_identity()
        except BuildContractError, FileExistsError, OSError, ScaleEvidenceError:
            return QualificationOutcome(
                evidence=evidence,
                exit_code=1,
                evidence_published=False,
                accepted_path=None,
            )

        exit_code = 0 if evidence.status == "passing" else 1
        if evidence.status == "diagnostic" and request.diagnostic:
            exit_code = 0
        published_acceptance: Path | None = None
        if accepted_target is not None and evidence.status == "passing":
            try:
                accepted_target.require_absent()
                require_private_identity()
                services.recheck_source(source)
                services.publish(
                    evidence,
                    accepted_target.bound_path,
                    accepted=True,
                    threshold_path=request.thresholds,
                )
                accepted_target.directory.require_current_identity()
                require_private_identity()
            except BuildContractError, FileExistsError, OSError, ScaleEvidenceError:
                return QualificationOutcome(
                    evidence=evidence,
                    exit_code=1,
                    evidence_published=True,
                    accepted_path=None,
                )
            published_acceptance = accepted_target.lexical_path
        return QualificationOutcome(
            evidence=evidence,
            exit_code=exit_code,
            evidence_published=True,
            accepted_path=published_acceptance,
        )
    finally:
        if execution.workspace_lease is not None:
            execution.workspace_lease.close()


def _qualify_with_held_destinations(
    request: QualificationRequest,
    services: QualificationServices,
    evidence_directory: _HeldDirectory,
    acceptance_directory: _HeldDirectory | None,
) -> QualificationOutcome:
    evidence_target = _PublicationTarget(evidence_directory, request.evidence_out.name)
    try:
        evidence_target.require_absent()
        workspace_parent = request.workspace.parent.stat(follow_symlinks=False)
        workspace_key = (
            workspace_parent.st_dev,
            workspace_parent.st_ino,
            request.workspace.name,
        )
        if workspace_key == evidence_target.key:
            raise QualificationInputError("workspace aliases a publication destination")
        fragment_size = os.statvfs(request.workspace.parent).f_frsize
        early_corpus_bytes = (
            sum(
                recipe.size_mib * 1024**2
                for recipe in file_size_cases(DocmendConfig().limits.max_file_size_mib)
            )
            if request.tier == "file-size"
            else summarize_scale_corpus(
                request.count,
                fragment_size=fragment_size,
            ).file_bytes
        )
        source = services.inspect_source(request.repository)
        reference, reference_sha256 = services.load_reference(request.reference_environment)
        threshold_context = (
            services.load_threshold(request.thresholds, reference_sha256)
            if request.thresholds is not None
            else None
        )
        accepted_target = _precheck_acceptance(request, source, acceptance_directory)
        if accepted_target is not None and evidence_target.key == accepted_target.key:
            raise QualificationInputError("evidence and acceptance destinations alias")
        if accepted_target is not None and workspace_key == accepted_target.key:
            raise QualificationInputError("workspace aliases a publication destination")
    except QualificationInputError:
        raise
    except (BuildContractError, ScaleEvidenceError, OSError, ValueError) as exc:
        raise QualificationInputError(str(exc)) from exc

    try:
        execution = services.execute(
            request,
            source,
            reference,
            reference_sha256,
            threshold_context,
        )
    except ExecutionInterrupted as exc:
        reasons = exc.checkpoint.reasons
        execution = replace(
            exc.checkpoint,
            reasons=(*reasons, "harness-error") if "harness-error" not in reasons else reasons,
        )
    except Exception:
        now = datetime.now(UTC)
        execution = ExecutionResult(
            wheel_sha256=None,
            preflight=None,
            stages=(),
            totals=(
                _zero_qualification_totals()
                if request.tier == "file-size"
                else _empty_totals(request.count)
            ),
            thresholds=None,
            workflow_runtime=None,
            reasons=("harness-error",),
            started_at=now,
            completed_at=now,
            python_version=platform.python_version(),
            kernel_version=platform.release(),
            corpus_bytes=early_corpus_bytes,
            file_size_cases=(
                tuple(
                    _pending_file_size_case(recipe)
                    for recipe in file_size_cases(DocmendConfig().limits.max_file_size_mib)
                )
                if request.tier == "file-size"
                else None
            ),
        )
    try:
        evidence_directory.require_current_identity()
        if acceptance_directory is not None:
            acceptance_directory.require_current_identity()
    except OSError:
        if execution.workspace_lease is not None:
            execution.workspace_lease.close()
        evidence = _evidence(
            request,
            source,
            reference_sha256,
            threshold_context,
            execution,
            (*execution.reasons, "harness-error"),
        )
        return QualificationOutcome(evidence, 1, False, None)
    return _publish_execution(
        request,
        services,
        source,
        reference_sha256,
        threshold_context,
        execution,
        evidence_target,
        accepted_target,
    )


def qualify(
    request: QualificationRequest,
    *,
    services: QualificationServices = _DEFAULT_SERVICES,
) -> QualificationOutcome:
    """Run one qualification and enforce held-parent no-clobber publication."""

    evidence_directory: _HeldDirectory | None = None
    acceptance_directory: _HeldDirectory | None = None
    try:
        evidence_directory = _HeldDirectory.open(request.evidence_out.parent)
        if request.accept_to is not None:
            acceptance_directory = _HeldDirectory.open(request.accept_to)
        return _qualify_with_held_destinations(
            request,
            services,
            evidence_directory,
            acceptance_directory,
        )
    except QualificationInputError:
        raise
    except (OSError, ValueError) as exc:
        raise QualificationInputError(str(exc)) from exc
    finally:
        if acceptance_directory is not None:
            acceptance_directory.close()
        if evidence_directory is not None:
            evidence_directory.close()


@dataclass(frozen=True, slots=True)
class DefaultReferenceCaptureServices:
    def observe(self, workspace: Path) -> ReferenceEnvironment:
        return observe_reference_environment(workspace).environment

    def publish_reference(self, environment: ReferenceEnvironment, path: Path) -> None:
        write_reference_environment(environment, path)


_DEFAULT_CAPTURE_SERVICES = DefaultReferenceCaptureServices()


def _open_capture_workspace(workspace: Path) -> int:
    workspace.mkdir(mode=0o700)
    created = workspace.lstat()
    if workspace.is_symlink() or not stat.S_ISDIR(created.st_mode):
        raise OSError("reference-capture workspace identity changed during creation")
    descriptor: int | None = None
    try:
        workspace.chmod(0o700, follow_symlinks=False)
        descriptor = os.open(
            workspace,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        _require_capture_workspace(
            workspace,
            descriptor,
            expected_identity=(created.st_dev, created.st_ino),
        )
    except OSError, ValueError:
        if descriptor is not None:
            os.close(descriptor)
        raise
    assert descriptor is not None
    return descriptor


def _require_capture_workspace(
    workspace: Path,
    descriptor: int,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> None:
    """Reconcile the public name with the held private directory identity."""

    path_metadata = workspace.lstat()
    held_metadata = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(path_metadata.st_mode)
        or not stat.S_ISDIR(held_metadata.st_mode)
        or (
            expected_identity is not None
            and expected_identity != (held_metadata.st_dev, held_metadata.st_ino)
        )
        or (path_metadata.st_dev, path_metadata.st_ino)
        != (held_metadata.st_dev, held_metadata.st_ino)
        or stat.S_IMODE(path_metadata.st_mode) != 0o700
        or stat.S_IMODE(held_metadata.st_mode) != 0o700
        or workspace.resolve(strict=True) != workspace
    ):
        raise OSError("reference-capture workspace identity changed")


def capture_reference(
    request: ReferenceCaptureRequest,
    *,
    services: ReferenceCaptureServices = _DEFAULT_CAPTURE_SERVICES,
) -> int:
    """Capture one public-safe reference through an absent private workspace."""

    descriptor: int | None = None
    output_directory: _HeldDirectory | None = None
    try:
        output_directory = _HeldDirectory.open(request.output.parent)
        output_target = _PublicationTarget(output_directory, request.output.name)
        output_target.require_absent()
        workspace_parent = request.workspace.parent.stat(follow_symlinks=False)
        workspace_key = (
            workspace_parent.st_dev,
            workspace_parent.st_ino,
            request.workspace.name,
        )
        if workspace_key == output_target.key:
            raise ValueError("reference workspace aliases its public output")
        descriptor = _open_capture_workspace(request.workspace)
        environment = services.observe(Path(f"/proc/self/fd/{descriptor}"))
        _require_capture_workspace(request.workspace, descriptor)
        output_directory.require_current_identity()
        services.publish_reference(environment, output_target.bound_path)
        output_directory.require_current_identity()
        _require_capture_workspace(request.workspace, descriptor)
    except FileExistsError, OSError, ResourcePreflightError, ScaleEvidenceError, ValueError:
        return 2
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if output_directory is not None:
            output_directory.close()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point with the qualification exit taxonomy."""

    try:
        request = parse_args(argv)
        if isinstance(request, ReferenceCaptureRequest):
            return capture_reference(request)
        return qualify(request).exit_code
    except QualificationHarnessError:
        return 1
    except QualificationInputError:
        return 2
