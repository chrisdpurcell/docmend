"""Installed-wheel scale orchestration, status, and publication contracts."""

import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Literal, cast

import pytest

from docmend.artifacts import ArtifactError
from docmend.scale_build import (
    BuildContractError,
    CandidateArtifactLease,
    CandidateBuild,
    CandidateWorkspaceLease,
    SourceProvenance,
)
from docmend.scale_corpus import ScaleCorpusSummary, recipe_counts
from docmend.scale_evidence import (
    ArtifactSizeName,
    FilesystemCapacityEvidence,
    OutcomeReason,
    PreflightEvidence,
    QualificationTotals,
    ReferenceEnvironment,
    ScaleEvidence,
    StageEvidence,
    StageName,
    ThresholdContext,
    ThresholdSet,
    ThresholdVerdict,
    read_scale_evidence,
    write_reference_environment,
    write_scale_evidence,
)
from docmend.scale_qualification import (
    DefaultCandidateRuntime,
    DefaultQualificationServices,
    ExecutionInterrupted,
    ExecutionResult,
    QualificationInputError,
    QualificationOutcome,
    QualificationRequest,
    QualificationWorkspacePaths,
    ReferenceCaptureRequest,
    StageAccounting,
    StageArtifactObservation,
    StageLaunch,
    accepted_evidence_name,
    capture_reference,
    main,
    parse_args,
    qualification_named_allowances,
    qualify,
)
from docmend.scale_reconcile import (
    PipelinePaths,
    PipelineReconciliation,
    QualificationFailure,
)
from docmend.scale_resources import ResourcePreflightError
from docmend.scale_stage import StageRequest, StageResult

SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
COMMIT = "a" * 40


def _reference() -> ReferenceEnvironment:
    return ReferenceEnvironment(
        operating_system="linux",
        cpu_architecture="x86_64",
        cpu_model="Synthetic CPU",
        logical_cpu_count=8,
        ram_bytes=32 * 1024**3,
        storage_class="local-ssd",
        filesystem="ext4",
        mount_flags=("rw", "relatime"),
        python_version="3.14.0",
        kernel_version="6.12.0",
    )


@pytest.fixture
def invocation_paths(tmp_path: Path) -> dict[str, Path]:
    repository = tmp_path / "repository"
    repository.mkdir()
    reference = tmp_path / "reference.json"
    write_reference_environment(_reference(), reference)
    accepted = tmp_path / "accepted"
    accepted.mkdir()
    return {
        "repository": repository,
        "workspace": tmp_path / "workspace",
        "reference": reference,
        "evidence": tmp_path / "evidence.json",
        "accepted": accepted,
    }


def _qualification_argv(paths: Mapping[str, Path], *extra: str) -> list[str]:
    return [
        "--tier",
        "pilot",
        "--workspace",
        str(paths["workspace"]),
        "--reference-environment",
        str(paths["reference"]),
        "--evidence-out",
        str(paths["evidence"]),
        *extra,
    ]


@pytest.mark.parametrize("tier", ["pilot", "scheduled"])
def test_parse_args__binding_100k_tiers_have_fixed_count(
    invocation_paths: dict[str, Path], tier: str
) -> None:
    argv = _qualification_argv(invocation_paths)
    argv[1] = tier
    if tier == "scheduled":
        thresholds = invocation_paths["repository"].parent / "thresholds.json"
        thresholds.write_text("{}\n", encoding="utf-8")
        argv.extend(("--thresholds", str(thresholds)))

    request = parse_args(argv, cwd=invocation_paths["repository"])

    assert isinstance(request, QualificationRequest)
    assert request.count == 100_000


def test_parse_args__release_binding_count_is_one_million(
    invocation_paths: dict[str, Path], tmp_path: Path
) -> None:
    thresholds = tmp_path / "thresholds.json"
    thresholds.write_text("{}\n", encoding="utf-8")
    argv = _qualification_argv(invocation_paths)
    argv[1] = "release"
    argv.extend(("--thresholds", str(thresholds)))

    request = parse_args(argv, cwd=invocation_paths["repository"])

    assert isinstance(request, QualificationRequest)
    assert request.count == 1_000_000


def test_parse_args__binding_count_cannot_be_overridden(invocation_paths: dict[str, Path]) -> None:
    with pytest.raises(QualificationInputError, match="binding tier count is fixed"):
        parse_args(
            _qualification_argv(invocation_paths, "--count", "999"),
            cwd=invocation_paths["repository"],
        )


def test_parse_args__diagnostic_count_override_is_legal(invocation_paths: dict[str, Path]) -> None:
    request = parse_args(
        _qualification_argv(invocation_paths, "--diagnostic", "--count", "40"),
        cwd=invocation_paths["repository"],
    )

    assert isinstance(request, QualificationRequest)
    assert request.diagnostic
    assert request.count == 40


@pytest.mark.parametrize("tier", ["scheduled", "release"])
def test_parse_args__threshold_diagnostic_count_cannot_be_overridden(
    invocation_paths: dict[str, Path],
    tier: str,
) -> None:
    thresholds = invocation_paths["repository"].parent / "thresholds.json"
    thresholds.write_text("{}\n", encoding="utf-8")
    argv = _qualification_argv(
        invocation_paths,
        "--diagnostic",
        "--count",
        "40",
        "--thresholds",
        str(thresholds),
    )
    argv[1] = tier

    with pytest.raises(QualificationInputError, match=r"count.*pilot diagnostic"):
        parse_args(argv, cwd=invocation_paths["repository"])


@pytest.mark.parametrize(
    ("tier", "fixed_count"),
    [("scheduled", "100000"), ("release", "1000000")],
)
def test_parse_args__threshold_diagnostic_may_repeat_fixed_count(
    invocation_paths: dict[str, Path],
    tier: str,
    fixed_count: str,
) -> None:
    thresholds = invocation_paths["repository"].parent / "thresholds.json"
    thresholds.write_text("{}\n", encoding="utf-8")
    argv = _qualification_argv(
        invocation_paths,
        "--diagnostic",
        "--count",
        fixed_count,
        "--thresholds",
        str(thresholds),
    )
    argv[1] = tier

    request = parse_args(argv, cwd=invocation_paths["repository"])

    assert isinstance(request, QualificationRequest)
    assert request.count == int(fixed_count)


@pytest.mark.parametrize("tier", ["pr", "file-size"])
def test_parse_args__rejects_unimplemented_tiers(
    invocation_paths: dict[str, Path], tier: str
) -> None:
    argv = _qualification_argv(invocation_paths)
    argv[1] = tier

    with pytest.raises(QualificationInputError, match="tier"):
        parse_args(argv, cwd=invocation_paths["repository"])


def test_parse_args__capture_reference_is_exclusive_and_complete(
    invocation_paths: dict[str, Path], tmp_path: Path
) -> None:
    capture = parse_args(
        [
            "--capture-reference",
            "--workspace",
            str(invocation_paths["workspace"]),
            "--output",
            str(tmp_path / "captured.json"),
        ],
        cwd=invocation_paths["repository"],
    )
    assert isinstance(capture, ReferenceCaptureRequest)

    with pytest.raises(QualificationInputError, match="exclusive"):
        parse_args(
            [
                "--capture-reference",
                "--workspace",
                str(invocation_paths["workspace"]),
                "--output",
                str(tmp_path / "other.json"),
                "--tier",
                "pilot",
            ],
            cwd=invocation_paths["repository"],
        )


def test_parse_args__requires_thresholds_for_scheduled_and_release(
    invocation_paths: dict[str, Path],
) -> None:
    argv = _qualification_argv(invocation_paths)
    argv[1] = "scheduled"

    with pytest.raises(QualificationInputError, match="thresholds"):
        parse_args(argv, cwd=invocation_paths["repository"])


def test_parse_args__diagnostic_refuses_acceptance(invocation_paths: dict[str, Path]) -> None:
    with pytest.raises(QualificationInputError, match=r"diagnostic.*accept"):
        parse_args(
            _qualification_argv(
                invocation_paths,
                "--diagnostic",
                "--count",
                "40",
                "--accept-to",
                str(invocation_paths["accepted"]),
            ),
            cwd=invocation_paths["repository"],
        )


@pytest.mark.parametrize("kind", ["preexisting", "inside-checkout"])
def test_parse_args__workspace_must_be_absent_and_external(
    invocation_paths: dict[str, Path], kind: str
) -> None:
    if kind == "preexisting":
        workspace = invocation_paths["workspace"]
        workspace.mkdir()
    else:
        workspace = invocation_paths["repository"] / "workspace"
    argv = _qualification_argv(invocation_paths)
    argv[3] = str(workspace)

    with pytest.raises(QualificationInputError, match=r"workspace.*absent|workspace.*outside"):
        parse_args(argv, cwd=invocation_paths["repository"])


def test_parse_args__ordinary_evidence_must_be_absent_and_outside_checkout(
    invocation_paths: dict[str, Path],
) -> None:
    argv = _qualification_argv(invocation_paths)
    argv[7] = str(invocation_paths["repository"] / "evidence.json")

    with pytest.raises(QualificationInputError, match=r"evidence.*outside"):
        parse_args(argv, cwd=invocation_paths["repository"])


@pytest.mark.parametrize("capture", [False, True])
def test_parse_args__workspace_must_not_alias_public_output(
    invocation_paths: dict[str, Path], capture: bool
) -> None:
    shared = invocation_paths["repository"].parent / "shared-output"
    argv = (
        [
            "--capture-reference",
            "--workspace",
            str(shared),
            "--output",
            str(shared),
        ]
        if capture
        else _qualification_argv(
            {
                **invocation_paths,
                "workspace": shared,
                "evidence": shared,
            }
        )
    )

    with pytest.raises(QualificationInputError, match=r"workspace.*(?:output|evidence)"):
        parse_args(argv, cwd=invocation_paths["repository"])


def test_parse_args__binding_without_acceptance_is_legal(invocation_paths: dict[str, Path]) -> None:
    request = parse_args(_qualification_argv(invocation_paths), cwd=invocation_paths["repository"])

    assert isinstance(request, QualificationRequest)
    assert request.accept_to is None


def test_parse_args__acceptance_must_be_existing_real_directory(
    invocation_paths: dict[str, Path],
) -> None:
    target = invocation_paths["repository"].parent / "not-a-directory"
    target.write_text("file\n", encoding="utf-8")

    with pytest.raises(QualificationInputError, match=r"accept.*directory"):
        parse_args(
            _qualification_argv(invocation_paths, "--accept-to", str(target)),
            cwd=invocation_paths["repository"],
        )


class FakeServices:
    def __init__(self) -> None:
        self.reference_matches = True
        self.reason: OutcomeReason | None = None
        self.fail_artifact_stage: StageName | None = None
        self.acceptance_race = False
        self.evidence_race = False
        self.source = SourceProvenance(
            repository=Path("/synthetic/repository"),
            commit=COMMIT,
            package_name="docmend",
            package_version="1.0.2",
            build_backend="uv_build",
            build_backend_version="0.11.6",
            build_frontend_version="0.11.6",
            pyproject_sha256=SHA_A,
            lock_sha256=SHA_B,
            pyproject_bytes=b"pyproject",
            lock_bytes=b"lock",
        )
        self.rechecks = 0

    def inspect_source(self, repository: Path) -> SourceProvenance:
        return replace(self.source, repository=repository)

    def load_reference(self, path: Path) -> tuple[ReferenceEnvironment, str]:
        del path
        return _reference(), SHA_C

    def load_threshold(self, path: Path, reference_sha256: str) -> ThresholdContext:
        del path, reference_sha256
        raise AssertionError("pilot fake must not load thresholds")

    def execute(
        self,
        request: QualificationRequest,
        source: SourceProvenance,
        reference: ReferenceEnvironment,
        reference_sha256: str,
        threshold_context: ThresholdContext | None,
    ) -> ExecutionResult:
        del source, reference, reference_sha256, threshold_context
        counts = recipe_counts(request.count)
        passed = self.reference_matches
        preflight = PreflightEvidence(
            filesystems=(
                FilesystemCapacityEvidence(
                    required_bytes=1,
                    available_bytes=2,
                    required_inodes=1,
                    inode_capacity_mode="finite-statvfs",
                    available_inodes=2,
                    margin_fraction=0.25,
                    passed=True,
                ),
            ),
            capacity_margin_met=True,
            reference_environment_match=self.reference_matches,
            binding_filesystem=True,
            ram_requirement_met=True,
            passed=passed,
        )
        stage_names: tuple[StageName, ...] = ("scan", "plan", "apply", "verify")
        stages: list[StageEvidence] = []
        artifact_names: dict[StageName, tuple[ArtifactSizeName, ...]] = {
            "scan": ("inventory", "structured-log", "stdout-log", "stderr-log"),
            "plan": ("plan", "structured-log", "stdout-log", "stderr-log"),
            "apply": (
                "report",
                "manifest",
                "structured-log",
                "stdout-log",
                "stderr-log",
            ),
            "verify": ("verify-report", "structured-log", "stdout-log", "stderr-log"),
        }
        for index, stage in enumerate(stage_names):
            if self.fail_artifact_stage == stage:
                stages.append(
                    StageEvidence(
                        stage=stage,
                        run_id=None,
                        elapsed_seconds=1.0,
                        files_per_second=0.0,
                        bytes_per_second=0.0,
                        peak_rss_bytes=1024,
                        python_allocation_peak_bytes=None,
                        vm_swap_peak_bytes=0,
                        exit_code=0,
                        completed=True,
                        artifact_validated=False,
                        artifact_bytes={"stdout-log": 1, "stderr-log": 0},
                    )
                )
                break
            stages.append(
                StageEvidence(
                    stage=stage,
                    run_id=f"run_20260713T12000{index}Z_aaaaa{index}",
                    elapsed_seconds=1.0,
                    files_per_second=float(request.count),
                    bytes_per_second=100.0,
                    peak_rss_bytes=1024 * (index + 1),
                    python_allocation_peak_bytes=None,
                    vm_swap_peak_bytes=(1 if self.reason == "telemetry-unavailable" else 0),
                    exit_code=(1 if stage == "verify" and counts.skips else 0),
                    completed=True,
                    artifact_validated=True,
                    artifact_bytes=dict.fromkeys(artifact_names[stage], 1),
                )
            )
        complete = len(stages) == 4 and all(stage.artifact_validated for stage in stages)
        totals = QualificationTotals(
            scanned=request.count if stages and stages[0].artifact_validated else 0,
            actions=counts.actions if len(stages) > 1 and stages[1].artifact_validated else 0,
            clean_noops=counts.noops if len(stages) > 1 and stages[1].artifact_validated else 0,
            plan_skips=counts.skips if len(stages) > 1 and stages[1].artifact_validated else 0,
            applied=counts.actions if len(stages) > 2 and stages[2].artifact_validated else 0,
            apply_skips=0,
            failures=0,
            not_attempted=0,
            verified=counts.actions if complete else 0,
            expected_findings=counts.skips,
            observed_findings=counts.skips if complete else 0,
        )
        reasons: list[OutcomeReason] = []
        if not self.reference_matches:
            reasons.append("reference-mismatch")
        if self.fail_artifact_stage is not None:
            reasons.append("artifact-invalid")
        if self.reason is not None:
            reasons.append(self.reason)
        now = datetime(2026, 7, 13, 12, tzinfo=UTC)
        return ExecutionResult(
            wheel_sha256=SHA_A,
            preflight=preflight,
            stages=tuple(stages),
            totals=totals,
            thresholds=None,
            workflow_runtime=None,
            reasons=tuple(reasons),
            started_at=now,
            completed_at=now + timedelta(seconds=4),
            python_version="3.14.0",
            kernel_version="6.12.0",
            corpus_bytes=4_000,
        )

    def recheck_source(self, source: SourceProvenance) -> None:
        del source
        self.rechecks += 1

    def publish(
        self,
        evidence: ScaleEvidence,
        path: Path,
        *,
        accepted: bool,
        threshold_path: Path | None,
    ) -> None:
        if (accepted and self.acceptance_race) or (not accepted and self.evidence_race):
            path.write_text("occupied\n", encoding="utf-8")
        write_scale_evidence(
            evidence,
            path,
            accepted=accepted,
            threshold_baseline_path=threshold_path,
        )


def _request(
    paths: Mapping[str, Path], *, diagnostic: bool, accept: bool = False
) -> QualificationRequest:
    extra = ["--diagnostic", "--count", "40"] if diagnostic else []
    if accept:
        extra.extend(("--accept-to", str(paths["accepted"])))
    request = parse_args(_qualification_argv(paths, *extra), cwd=paths["repository"])
    assert isinstance(request, QualificationRequest)
    return request


def test_qualify__complete_explicit_diagnostic_publishes_and_exits_zero(
    invocation_paths: dict[str, Path],
) -> None:
    services = FakeServices()

    outcome = qualify(_request(invocation_paths, diagnostic=True), services=services)

    assert isinstance(outcome, QualificationOutcome)
    assert outcome.exit_code == 0
    assert outcome.evidence.status == "diagnostic"
    assert outcome.evidence.outcome_reason == "explicit-diagnostic"
    assert read_scale_evidence(invocation_paths["evidence"]) == outcome.evidence
    assert services.rechecks == 1


def test_stage_artifact_failure__stops_at_prefix_and_publishes_incomplete(
    invocation_paths: dict[str, Path],
) -> None:
    services = FakeServices()
    services.fail_artifact_stage = "plan"

    outcome = qualify(_request(invocation_paths, diagnostic=True), services=services)

    assert [stage.stage for stage in outcome.evidence.stages] == ["scan", "plan"]
    assert outcome.evidence.status == "incomplete"
    assert outcome.evidence.outcome_reason == "artifact-invalid"
    assert outcome.exit_code == 1


def test_reference_mismatch_binding_request__is_diagnostic_but_nonzero(
    invocation_paths: dict[str, Path],
) -> None:
    services = FakeServices()
    services.reference_matches = False

    outcome = qualify(_request(invocation_paths, diagnostic=False), services=services)

    assert outcome.evidence.status == "diagnostic"
    assert outcome.evidence.outcome_reason == "reference-mismatch"
    assert outcome.exit_code == 1


def test_reference_mismatch_explicit_diagnostic__exits_zero(
    invocation_paths: dict[str, Path],
) -> None:
    services = FakeServices()
    services.reference_matches = False

    outcome = qualify(_request(invocation_paths, diagnostic=True), services=services)

    assert outcome.evidence.outcome_reason == "reference-mismatch"
    assert outcome.exit_code == 0


def test_nonzero_child_swap__uses_telemetry_unavailable_contract(
    invocation_paths: dict[str, Path],
) -> None:
    services = FakeServices()
    services.reason = "telemetry-unavailable"

    outcome = qualify(_request(invocation_paths, diagnostic=True), services=services)

    assert outcome.evidence.status == "incomplete"
    assert outcome.evidence.outcome_reason == "telemetry-unavailable"
    assert outcome.exit_code == 1


def test_capacity_estimate_overrun__is_incomplete(invocation_paths: dict[str, Path]) -> None:
    services = FakeServices()
    services.reason = "capacity-estimate-exceeded"

    outcome = qualify(_request(invocation_paths, diagnostic=True), services=services)

    assert outcome.evidence.status == "incomplete"
    assert outcome.evidence.outcome_reason == "capacity-estimate-exceeded"


def test_publication_race__preserves_occupied_destination_and_exits_one(
    invocation_paths: dict[str, Path],
) -> None:
    services = FakeServices()
    services.evidence_race = True

    outcome = qualify(_request(invocation_paths, diagnostic=True), services=services)

    assert outcome.exit_code == 1
    assert invocation_paths["evidence"].read_text(encoding="utf-8") == "occupied\n"
    assert not outcome.evidence_published


def test_passing_binding_acceptance__uses_full_commit_name_and_identical_bytes(
    invocation_paths: dict[str, Path],
) -> None:
    services = FakeServices()
    request = _request(invocation_paths, diagnostic=False, accept=True)

    outcome = qualify(request, services=services)

    accepted = invocation_paths["accepted"] / f"{COMMIT}-pilot-100000.json"
    assert outcome.exit_code == 0
    assert outcome.evidence.status == "passing"
    assert outcome.accepted_path == accepted
    assert accepted.read_bytes() == invocation_paths["evidence"].read_bytes()
    assert accepted_evidence_name(COMMIT, "pilot", 100_000) == accepted.name


def test_acceptance_race__preserves_ordinary_evidence_and_prior_acceptance(
    invocation_paths: dict[str, Path],
) -> None:
    services = FakeServices()
    services.acceptance_race = True
    request = _request(invocation_paths, diagnostic=False, accept=True)

    outcome = qualify(request, services=services)

    accepted = invocation_paths["accepted"] / f"{COMMIT}-pilot-100000.json"
    assert outcome.exit_code == 1
    assert outcome.evidence_published
    assert read_scale_evidence(invocation_paths["evidence"]).status == "passing"
    assert accepted.read_text(encoding="utf-8") == "occupied\n"


@pytest.mark.parametrize("alias_kind", ["evidence", "acceptance"])
def test_qualify__rejects_workspace_or_destination_alias_before_execution(
    invocation_paths: dict[str, Path], alias_kind: str
) -> None:
    class Services(FakeServices):
        def __init__(self) -> None:
            super().__init__()
            self.executed = False

        def execute(self, *args: object, **kwargs: object) -> ExecutionResult:
            self.executed = True
            return super().execute(*args, **kwargs)  # type: ignore[arg-type]

    services = Services()
    request = _request(invocation_paths, diagnostic=False, accept=True)
    accepted = invocation_paths["accepted"] / f"{COMMIT}-pilot-100000.json"
    request = (
        replace(request, evidence_out=accepted)
        if alias_kind == "evidence"
        else replace(request, workspace=accepted)
    )

    with pytest.raises(QualificationInputError, match="alias"):
        qualify(request, services=services)

    assert not services.executed
    assert not accepted.exists()


def test_qualify__replaced_evidence_parent_is_not_used_for_publication(
    invocation_paths: dict[str, Path],
) -> None:
    original_parent = invocation_paths["evidence"].parent
    held_parent = original_parent.with_name("held-output-parent")

    class Services(FakeServices):
        def execute(self, *args: object, **kwargs: object) -> ExecutionResult:
            result = super().execute(*args, **kwargs)  # type: ignore[arg-type]
            original_parent.replace(held_parent)
            original_parent.mkdir()
            return result

    outcome = qualify(
        _request(invocation_paths, diagnostic=True),
        services=Services(),
    )

    assert outcome.exit_code == 1
    assert not outcome.evidence_published
    assert not invocation_paths["evidence"].exists()
    assert not (held_parent / invocation_paths["evidence"].name).exists()


def test_qualify__replaced_acceptance_parent_preserves_ordinary_evidence(
    invocation_paths: dict[str, Path],
) -> None:
    accepted_parent = invocation_paths["accepted"]
    held_parent = accepted_parent.with_name("held-accepted-parent")

    class Services(FakeServices):
        def publish(
            self,
            evidence: ScaleEvidence,
            path: Path,
            *,
            accepted: bool,
            threshold_path: Path | None,
        ) -> None:
            super().publish(
                evidence,
                path,
                accepted=accepted,
                threshold_path=threshold_path,
            )
            if not accepted:
                accepted_parent.replace(held_parent)
                accepted_parent.mkdir()

    outcome = qualify(
        _request(invocation_paths, diagnostic=False, accept=True),
        services=Services(),
    )

    assert outcome.exit_code == 1
    assert outcome.evidence_published
    assert invocation_paths["evidence"].is_file()
    assert outcome.accepted_path is None
    assert not any(accepted_parent.iterdir())


def test_named_allowances__derive_every_stage_from_summary() -> None:
    class Summary:
        count = 41
        recipe_counts = recipe_counts(41)

    allowances = qualification_named_allowances(Summary())

    assert allowances["scan"]["inventory"] == 41 * 2_048
    assert allowances["plan"]["plan"] == 41 * 4_096
    assert allowances["apply"]["manifest"] == recipe_counts(41).actions * 8_192
    assert allowances["verify"]["verify-report"] == 41 * 1_024


class FakeBuilder:
    def __init__(self) -> None:
        self.failure: Exception | None = None
        self.lease: CandidateWorkspaceLease | None = None

    def prepare(self, request: QualificationRequest, source: SourceProvenance) -> CandidateBuild:
        if self.failure is not None:
            raise self.failure
        request.workspace.mkdir(mode=0o700)
        descriptor = os.open(
            request.workspace,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        self.lease = CandidateWorkspaceLease(request.workspace, descriptor)
        source_snapshot = request.workspace / "source"
        wrapper = source_snapshot / "scripts/measure_scale_stage.py"
        wrapper.parent.mkdir(parents=True)
        wrapper.write_text("raise SystemExit(0)\n", encoding="utf-8")
        venv = request.workspace / "venv"
        venv_bin = venv / "bin"
        venv_bin.mkdir(parents=True)
        venv_python = venv_bin / "python"
        venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
        venv_python.chmod(0o700)
        executable = venv_bin / "docmend"
        executable.write_text("#!/bin/sh\n", encoding="utf-8")
        executable.chmod(0o700)
        return CandidateBuild(
            commit=source.commit,
            package_name=source.package_name,
            package_version=source.package_version,
            build_backend_version=source.build_backend_version,
            build_frontend_version=source.build_frontend_version,
            source_snapshot=source_snapshot,
            wheel=request.workspace / "wheel/docmend.whl",
            wheel_sha256=SHA_A,
            venv=venv,
            venv_python=venv_python,
            executable=executable,
            workspace_lease=self.lease,
            artifact_lease=CandidateArtifactLease.capture(
                executable=executable,
                venv_python=venv_python,
                measurement_wrapper=wrapper,
            ),
        )


class FakeCandidateRuntime:
    def __init__(self) -> None:
        self.requests: list[StageRequest] = []
        self.private_workspaces: list[Path] = []
        self.summary: ScaleCorpusSummary | None = None
        self.materialization_failure: Exception | None = None
        self.wrapper_failure_stage: str | None = None
        self.mismatch_stage: str | None = None
        self.artifact_failure_stage: str | None = None
        self.cross_failure_stage: str | None = None
        self.unexpected_exit_stage: str | None = None
        self.public_failure_stage: str | None = None
        self.public_failure: str | None = None
        self.replace_workspace_after_launch_stage: str | None = None
        self.replace_workspace_after_validation_stage: str | None = None
        self.reconcile_crash: Exception | None = None
        self.reconcile_public_failure: str | None = None
        self.clock_crash_call: int | None = None
        self.clock_calls = 0
        self.reference_match = True
        self.clock = 0.0
        self.stage_elapsed = 1.0

    def preflight(
        self,
        paths: QualificationWorkspacePaths,
        summary: ScaleCorpusSummary,
        reference: ReferenceEnvironment,
    ) -> PreflightEvidence:
        del paths, reference
        self.summary = summary
        return PreflightEvidence(
            filesystems=(
                FilesystemCapacityEvidence(
                    required_bytes=1,
                    available_bytes=2,
                    required_inodes=1,
                    inode_capacity_mode="finite-statvfs",
                    available_inodes=2,
                    margin_fraction=0.25,
                    passed=True,
                ),
            ),
            capacity_margin_met=True,
            reference_environment_match=self.reference_match,
            binding_filesystem=True,
            ram_requirement_met=True,
            passed=self.reference_match,
        )

    def materialize(self, path: Path, count: int, *, fragment_size: int) -> ScaleCorpusSummary:
        del path, count, fragment_size
        if self.materialization_failure is not None:
            raise self.materialization_failure
        assert self.summary is not None
        return self.summary

    def launch(
        self,
        candidate: CandidateBuild,
        request: StageRequest,
        *,
        private_workspace: Path,
        on_dispatch: Callable[[], None],
    ) -> StageLaunch:
        self.requests.append(request)
        self.private_workspaces.append(private_workspace)
        on_dispatch()
        if self.wrapper_failure_stage == request.stage:
            return StageLaunch(wrapper_exit_code=1, result=None)
        counts = recipe_counts(40)
        stdout = "wrong.stdout" if self.mismatch_stage == request.stage else request.stdout
        result = StageResult(
            stage=request.stage,
            completed=True,
            exit_code=(
                2
                if self.unexpected_exit_stage == request.stage
                else 1
                if request.stage == "verify" and counts.skips
                else 0
            ),
            elapsed_seconds=self.stage_elapsed,
            peak_rss_bytes=4096,
            vm_swap_peak_bytes=0,
            tracing_enabled=False,
            stdout=stdout,
            stderr=request.stderr,
            error_code=None,
        )
        launch = StageLaunch(wrapper_exit_code=0, result=result)
        if self.replace_workspace_after_launch_stage == request.stage:
            workspace = candidate.workspace_lease.path
            workspace.replace(workspace.with_name("held-candidate-workspace"))
            workspace.mkdir(mode=0o700)
        return launch

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
        del result, private_workspace, allowances
        if stage not in {"scan", "plan", "apply", "verify"}:
            raise AssertionError("synthetic runtime received an unknown stage")
        stage_name = cast("StageName", stage)
        if self.artifact_failure_stage == stage:
            raise ArtifactError("synthetic invalid artifact")
        if self.cross_failure_stage == stage:
            raise QualificationFailure("synthetic schema-valid cross-binding mismatch")
        counts = recipe_counts(count)
        artifact_names: dict[StageName, tuple[ArtifactSizeName, ...]] = {
            "scan": ("inventory", "structured-log", "stdout-log", "stderr-log"),
            "plan": ("plan", "structured-log", "stdout-log", "stderr-log"),
            "apply": (
                "report",
                "manifest",
                "structured-log",
                "stdout-log",
                "stderr-log",
            ),
            "verify": ("verify-report", "structured-log", "stdout-log", "stderr-log"),
        }
        accounting = {
            "scan": StageAccounting(scanned=count),
            "plan": StageAccounting(
                actions=counts.actions,
                clean_noops=counts.noops,
                plan_skips=counts.skips,
            ),
            "apply": StageAccounting(applied=planned_actions),
            "verify": StageAccounting(
                verified=planned_actions,
                observed_findings=counts.skips,
            ),
        }[stage_name]
        if self.public_failure_stage == stage:
            if self.public_failure == "conservation-mismatch" and stage == "scan":
                accounting = StageAccounting(scanned=count - 1)
            elif self.public_failure == "finding-mismatch" and stage == "verify":
                accounting = StageAccounting(
                    verified=planned_actions,
                    observed_findings=0,
                )
        index = ("scan", "plan", "apply", "verify").index(stage)
        observation = StageArtifactObservation(
            run_id=f"run_20260713T13000{index}Z_bbbbb{index}",
            artifact_bytes=MappingProxyType(dict.fromkeys(artifact_names[stage_name], 1)),
            accounting=accounting,
            public_failure=cast(
                "Literal['conservation-mismatch', 'finding-mismatch'] | None",
                self.public_failure if self.public_failure_stage == stage else None,
            ),
        )
        if self.replace_workspace_after_validation_stage == stage:
            paths.root.replace(paths.root.with_name("held-validated-workspace"))
            paths.root.mkdir(mode=0o700)
        return observation

    def reconcile(self, paths: PipelinePaths, *, count: int) -> PipelineReconciliation:
        del paths
        if self.reconcile_crash is not None:
            raise self.reconcile_crash
        counts = recipe_counts(count)
        return PipelineReconciliation(
            count=count,
            scanned_files=count,
            planned_actions=counts.actions,
            plan_skips=counts.skips,
            plan_noops=counts.noops,
            applied_actions=counts.actions,
            verified_actions=counts.actions,
            stage_run_ids=MappingProxyType(
                {
                    stage: f"run_20260713T13000{index}Z_bbbbb{index}"
                    for index, stage in enumerate(("scan", "plan", "apply", "verify"))
                }
            ),
            artifact_bytes=MappingProxyType(
                {
                    "inventory": 1,
                    "plan": 1,
                    "report": 1,
                    "manifest": 1,
                    "verify-report": 1,
                }
            ),
            structured_log_bytes=MappingProxyType(
                dict.fromkeys(("scan", "plan", "apply", "verify"), 1)
            ),
            expected_findings=MappingProxyType(
                {("lib/39/00/doc000039.txt", "encoding"): counts.skips}
            ),
            observed_findings=MappingProxyType(
                {("lib/39/00/doc000039.txt", "encoding"): counts.skips}
            ),
            manifest_path=Path("/synthetic/manifest.jsonl"),
            public_failure=cast(
                "Literal['conservation-mismatch', 'finding-mismatch'] | None",
                self.reconcile_public_failure,
            ),
        )

    def monotonic(self) -> float:
        self.clock_calls += 1
        if self.clock_calls == self.clock_crash_call:
            raise KeyError("synthetic monotonic clock crash")
        current = self.clock
        self.clock += 1.0
        return current

    def now(self) -> datetime:
        return datetime(2026, 7, 13, 13, tzinfo=UTC)


def _execute_real_seam(
    request: QualificationRequest,
    source: SourceProvenance,
    builder: FakeBuilder,
    runtime: FakeCandidateRuntime,
    *,
    threshold: ThresholdContext | None = None,
) -> ExecutionResult:
    services = DefaultQualificationServices(builder=builder, runtime=runtime)
    return services.execute(request, source, _reference(), SHA_C, threshold)


class _LifecycleServices:
    """Public lifecycle adapter around the real builder/runtime execution seam."""

    def __init__(self, builder: FakeBuilder, runtime: FakeCandidateRuntime) -> None:
        self.defaults = DefaultQualificationServices(builder=builder, runtime=runtime)

    def inspect_source(self, repository: Path) -> SourceProvenance:
        return replace(FakeServices().source, repository=repository)

    def load_reference(self, path: Path) -> tuple[ReferenceEnvironment, str]:
        del path
        return _reference(), SHA_C

    def load_threshold(self, path: Path, reference_sha256: str) -> ThresholdContext:
        del path, reference_sha256
        raise AssertionError("diagnostic pilot must not load thresholds")

    def execute(
        self,
        request: QualificationRequest,
        source: SourceProvenance,
        reference: ReferenceEnvironment,
        reference_sha256: str,
        threshold_context: ThresholdContext | None,
    ) -> ExecutionResult:
        return self.defaults.execute(
            request,
            source,
            reference,
            reference_sha256,
            threshold_context,
        )

    def recheck_source(self, source: SourceProvenance) -> None:
        del source

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


def test_real_execution_seam__uses_four_exact_requests_and_fresh_wrappers(
    invocation_paths: dict[str, Path],
) -> None:
    request = _request(invocation_paths, diagnostic=True)
    builder = FakeBuilder()
    runtime = FakeCandidateRuntime()

    result = _execute_real_seam(request, FakeServices().source, builder, runtime)

    paths = QualificationWorkspacePaths.beneath(request.workspace)
    executable = str(request.workspace / "venv/bin/docmend")
    assert [item.argv for item in runtime.requests] == [
        (executable, "scan", str(paths.corpus), "--report", str(paths.inventory)),
        (
            executable,
            "plan",
            "--inventory",
            str(paths.inventory),
            "--out",
            str(paths.plan),
        ),
        (
            executable,
            "apply",
            str(paths.plan),
            "--write",
            "--preserved-by",
            "external",
            "--report",
            str(paths.report),
        ),
        (
            executable,
            "verify",
            str(paths.corpus),
            "--plan",
            str(paths.plan),
            "--manifest",
            str(paths.manifest("run_20260713T130002Z_bbbbb2")),
            "--report",
            str(paths.report),
            "--out",
            str(paths.verify_report),
        ),
    ]
    assert all(item.cwd == paths.pipeline for item in runtime.requests)
    assert len(set(runtime.private_workspaces)) == 4
    for item in runtime.requests:
        assert item.environment["LANG"] == "C.UTF-8"
        assert item.environment["LC_ALL"] == "C.UTF-8"
        assert item.environment["TZ"] == "UTC"
        assert item.environment["PYTHONNOUSERSITE"] == "1"
        for name in ("HOME", "XDG_STATE_HOME", "XDG_CONFIG_HOME", "TMPDIR"):
            assert Path(item.environment[name]).is_relative_to(request.workspace)
    assert not result.reasons
    assert len(result.stages) == 4


@pytest.mark.parametrize(
    ("failure", "stage", "reason"),
    [
        ("wrapper", "plan", "supervisor-failed"),
        ("mismatch", "plan", "supervisor-failed"),
        ("artifact", "plan", "artifact-invalid"),
    ],
)
def test_real_execution_seam__stops_immediately_at_failed_boundary(
    invocation_paths: dict[str, Path], failure: str, stage: str, reason: str
) -> None:
    request = _request(invocation_paths, diagnostic=True)
    runtime = FakeCandidateRuntime()
    setattr(
        runtime, f"{failure}_failure_stage" if failure != "mismatch" else "mismatch_stage", stage
    )

    result = _execute_real_seam(request, FakeServices().source, FakeBuilder(), runtime)

    assert [request.stage for request in runtime.requests] == ["scan", "plan"]
    assert result.reasons[-1] == reason
    assert [item.stage for item in result.stages] == ["scan", "plan"]


def test_real_execution_seam__schema_valid_cross_binding_failure_stops_downstream(
    invocation_paths: dict[str, Path],
) -> None:
    request = _request(invocation_paths, diagnostic=True)
    runtime = FakeCandidateRuntime()
    runtime.cross_failure_stage = "plan"

    result = _execute_real_seam(request, FakeServices().source, FakeBuilder(), runtime)

    assert [item.stage for item in runtime.requests] == ["scan", "plan"]
    assert result.reasons == ("artifact-invalid",)


@pytest.mark.parametrize(
    ("stage", "reason", "expected_attempts"),
    [
        ("scan", "conservation-mismatch", ["scan"]),
        ("verify", "finding-mismatch", ["scan", "plan", "apply", "verify"]),
    ],
)
def test_real_execution_seam__publishes_raw_publicly_proven_failure(
    invocation_paths: dict[str, Path],
    stage: str,
    reason: str,
    expected_attempts: list[str],
) -> None:
    from docmend.scale_qualification import _evidence  # pyright: ignore[reportPrivateUsage]

    request = _request(invocation_paths, diagnostic=True)
    source = FakeServices().source
    runtime = FakeCandidateRuntime()
    runtime.public_failure_stage = stage
    runtime.public_failure = reason

    result = _execute_real_seam(request, source, FakeBuilder(), runtime)
    evidence = _evidence(request, source, SHA_C, None, result, result.reasons)

    assert [item.stage for item in runtime.requests] == expected_attempts
    assert result.reasons == (reason,)
    assert evidence.status == "failed"
    assert evidence.outcome_reason == reason


def test_real_execution_seam__unexpected_exit_precedes_missing_artifact(
    invocation_paths: dict[str, Path],
) -> None:
    request = _request(invocation_paths, diagnostic=True)
    runtime = FakeCandidateRuntime()
    runtime.unexpected_exit_stage = "plan"
    runtime.artifact_failure_stage = "plan"

    result = _execute_real_seam(request, FakeServices().source, FakeBuilder(), runtime)

    assert [item.stage for item in runtime.requests] == ["scan", "plan"]
    assert result.reasons == ("stage-exit", "artifact-invalid")


@pytest.mark.parametrize("reason", ["conservation-mismatch", "finding-mismatch"])
def test_final_exact_reducer_verdict_is_public_with_equal_aggregate_totals(
    invocation_paths: dict[str, Path], reason: str
) -> None:
    from docmend.scale_qualification import _evidence  # pyright: ignore[reportPrivateUsage]

    request = _request(invocation_paths, diagnostic=True)
    source = FakeServices().source
    runtime = FakeCandidateRuntime()
    runtime.reconcile_public_failure = reason

    result = _execute_real_seam(request, source, FakeBuilder(), runtime)
    evidence = _evidence(request, source, SHA_C, None, result, result.reasons)

    assert result.reasons == (reason,)
    assert len(result.stages) == 4
    assert all(stage.artifact_validated for stage in result.stages)
    assert evidence.status == "failed"
    assert evidence.outcome_reason == reason


def test_reconciliation_stage_identity_disagreement_is_incomplete(
    invocation_paths: dict[str, Path],
) -> None:
    from docmend.scale_qualification import (  # pyright: ignore[reportPrivateUsage]
        _require_reconciliation_matches_stages,  # pyright: ignore[reportPrivateUsage]
    )
    from docmend.scale_reconcile import QualificationIncomplete

    request = _request(invocation_paths, diagnostic=True)
    runtime = FakeCandidateRuntime()
    result = _execute_real_seam(request, FakeServices().source, FakeBuilder(), runtime)
    reconciliation = runtime.reconcile(
        QualificationWorkspacePaths.beneath(request.workspace).reconciliation(),
        count=request.count,
    )
    mismatched_run_ids = dict(reconciliation.stage_run_ids)
    mismatched_run_ids["scan"] = "run_20260713T130009Z_cccccc9"
    mismatch = replace(
        reconciliation,
        stage_run_ids=MappingProxyType(mismatched_run_ids),
    )

    with pytest.raises(QualificationIncomplete, match="run IDs"):
        _require_reconciliation_matches_stages(mismatch, result.stages)


@pytest.mark.parametrize(
    ("message", "expected_reason"),
    [
        ("finding-mismatch", "finding-mismatch"),
        ("synthetic valid fact disagreement", "conservation-mismatch"),
    ],
)
def test_final_reconciliation_fact_disagreement_remains_public_failure(
    invocation_paths: dict[str, Path],
    message: str,
    expected_reason: str,
) -> None:
    from docmend.scale_qualification import _evidence  # pyright: ignore[reportPrivateUsage]

    request = _request(invocation_paths, diagnostic=True)
    source = FakeServices().source
    runtime = FakeCandidateRuntime()
    runtime.reconcile_crash = QualificationFailure(message)

    result = _execute_real_seam(request, source, FakeBuilder(), runtime)
    evidence = _evidence(request, source, SHA_C, None, result, result.reasons)

    assert result.reasons == (expected_reason,)
    assert evidence.status == "failed"
    assert evidence.outcome_reason == expected_reason


def test_real_execution_seam__build_and_materialization_failures_are_phase_truthful(
    invocation_paths: dict[str, Path],
) -> None:
    request = _request(invocation_paths, diagnostic=True)
    builder = FakeBuilder()
    builder.failure = BuildContractError("wheel build failed")
    build = _execute_real_seam(request, FakeServices().source, builder, FakeCandidateRuntime())
    assert build.reasons == ("build-failed",)
    assert build.wheel_sha256 is None
    assert not build.stages

    invocation_paths["workspace"].mkdir(exist_ok=True)
    invocation_paths["workspace"].rmdir()
    runtime = FakeCandidateRuntime()
    runtime.materialization_failure = OSError("synthetic materialization failure")
    materialize = _execute_real_seam(request, FakeServices().source, FakeBuilder(), runtime)
    assert materialize.reasons == ("corpus-materialization-failed",)
    assert materialize.wheel_sha256 == SHA_A
    assert not materialize.stages


def test_qualify__private_pipeline_setup_failure_is_harness_error(
    invocation_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from docmend import scale_qualification

    original = scale_qualification._mkdir_private  # pyright: ignore[reportPrivateUsage]

    def fail_pipeline(path: Path) -> None:
        if path.name == "pipeline":
            raise RuntimeError("synthetic private workspace setup failure")
        original(path)

    monkeypatch.setattr(scale_qualification, "_mkdir_private", fail_pipeline)

    outcome = qualify(
        _request(invocation_paths, diagnostic=True),
        services=_LifecycleServices(FakeBuilder(), FakeCandidateRuntime()),
    )

    assert outcome.evidence_published
    assert outcome.evidence.preflight is None
    assert not outcome.evidence.stages
    assert outcome.evidence.status == "incomplete"
    assert outcome.evidence.outcome_reason == "harness-error"


@pytest.mark.parametrize(
    ("failure_kind", "message", "expected_reason"),
    [
        ("build", "source changed during install", "build-failed"),
        ("install", "ordinary build failure", "install-failed"),
        ("provenance", "pip check failed", "provenance-changed"),
    ],
)
def test_real_execution_seam__build_failure_kind_not_message_selects_reason(
    invocation_paths: dict[str, Path],
    failure_kind: str,
    message: str,
    expected_reason: str,
) -> None:
    builder = FakeBuilder()
    builder.failure = BuildContractError(
        message,
        failure_kind=cast("Literal['build', 'install', 'provenance']", failure_kind),
    )

    result = _execute_real_seam(
        _request(invocation_paths, diagnostic=True),
        FakeServices().source,
        builder,
        FakeCandidateRuntime(),
    )

    assert result.reasons == (expected_reason,)


def test_real_execution_seam__threshold_and_release_runtime_reasons(
    invocation_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    request = replace(_request(invocation_paths, diagnostic=True), tier="release")
    limits = ThresholdSet(
        absolute_peak_rss_bytes=1,
        slope_bytes_per_file=0,
        linearity_tolerance=0.2,
    )
    verdict = ThresholdVerdict(
        limits=limits,
        observed_peak_rss_bytes=4096,
        observed_slope_bytes_per_file=1,
        observed_linearity_ratio=1.0,
        peak_passed=False,
        slope_passed=False,
        linearity_passed=False,
        passed=False,
    )

    def fixed_verdict(
        context: ThresholdContext,
        *,
        file_count: Literal[100_000, 1_000_000],
        stage_peak_rss: Mapping[StageName, int],
    ) -> ThresholdVerdict:
        del context, file_count, stage_peak_rss
        return verdict

    monkeypatch.setattr(
        "docmend.scale_qualification.evaluate_thresholds",
        fixed_verdict,
    )
    runtime = FakeCandidateRuntime()
    runtime.stage_elapsed = 12_000.0

    result = _execute_real_seam(
        request,
        FakeServices().source,
        FakeBuilder(),
        runtime,
        threshold=cast("ThresholdContext", object()),
    )

    assert "threshold-exceeded" in result.reasons
    assert result.workflow_runtime is not None
    assert not result.workflow_runtime.passed
    assert "runtime-limit-exceeded" in result.reasons


@pytest.mark.parametrize(
    ("failure_stage", "expected_stages", "expects_runtime"),
    [("scan", [], False), ("plan", ["scan"], True)],
)
def test_release_stage_setup_failure_does_not_record_undispatched_stage(
    invocation_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
    expected_stages: list[str],
    expects_runtime: bool,
) -> None:
    from docmend import scale_qualification
    from docmend.scale_qualification import _evidence  # pyright: ignore[reportPrivateUsage]

    request = replace(_request(invocation_paths, diagnostic=True), tier="release")
    source = FakeServices().source
    original = cast("Callable[..., StageRequest]", scale_qualification.build_stage_request)

    def fail_request(stage: str, *args: object, **kwargs: object) -> StageRequest:
        from docmend.scale_stage import StageContractError

        if stage == failure_stage:
            raise StageContractError("synthetic pre-dispatch failure")
        return original(stage, *args, **kwargs)

    monkeypatch.setattr("docmend.scale_qualification.build_stage_request", fail_request)

    result = _execute_real_seam(request, source, FakeBuilder(), FakeCandidateRuntime())
    evidence = _evidence(request, source, SHA_C, None, result, result.reasons)

    assert result.reasons == ("harness-error",)
    assert [stage.stage for stage in result.stages] == expected_stages
    assert (result.workflow_runtime is not None) is expects_runtime
    assert evidence.status == "incomplete"


def test_default_runtime_request_failure_occurs_before_dispatch(
    invocation_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(invocation_paths, diagnostic=True)
    builder = FakeBuilder()
    candidate = builder.prepare(request, FakeServices().source)
    private_workspace = request.workspace / "supervisor" / "scan"
    private_workspace.mkdir(parents=True)
    stage_request = StageRequest(
        stage="scan",
        argv=(str(candidate.executable), "scan"),
        cwd=request.workspace,
        environment={"PATH": os.defpath},
        stdout="scan.stdout",
        stderr="scan.stderr",
    )
    dispatched: list[bool] = []

    def fail_write(_request: StageRequest, _path: Path) -> None:
        raise OSError("synthetic request publication failure")

    monkeypatch.setattr("docmend.scale_qualification.write_stage_request", fail_write)
    try:
        with pytest.raises(OSError, match="request publication"):
            DefaultCandidateRuntime().launch(
                candidate,
                stage_request,
                private_workspace=private_workspace,
                on_dispatch=lambda: dispatched.append(True),
            )
    finally:
        candidate.workspace_lease.close()

    assert not dispatched


@pytest.mark.parametrize("artifact", ["executable", "venv-python", "wrapper"])
def test_default_runtime__reconciles_candidate_artifacts_after_dispatch(
    invocation_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
) -> None:
    request = _request(invocation_paths, diagnostic=True)
    builder = FakeBuilder()
    candidate = builder.prepare(request, FakeServices().source)
    supervisor = request.workspace / "supervisor"
    supervisor.mkdir(mode=0o700)
    private_workspace = supervisor / "scan"
    private_workspace.mkdir(mode=0o700)
    stage_request = StageRequest(
        stage="scan",
        argv=(str(candidate.executable), "scan"),
        cwd=request.workspace,
        environment={"PATH": os.defpath},
        stdout="scan.stdout",
        stderr="scan.stderr",
    )
    target = {
        "executable": candidate.executable,
        "venv-python": candidate.venv_python,
        "wrapper": candidate.source_snapshot / "scripts/measure_scale_stage.py",
    }[artifact]
    dispatched: list[bool] = []

    def substitute_during_dispatch(
        argv: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[bytes]:
        del kwargs
        target.write_bytes(b"permanent replacement\n")
        if artifact != "wrapper":
            target.chmod(0o700)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr("docmend.scale_qualification.subprocess.run", substitute_during_dispatch)
    try:
        with pytest.raises(BuildContractError, match=r"candidate.*identity"):
            DefaultCandidateRuntime().launch(
                candidate,
                stage_request,
                private_workspace=private_workspace,
                on_dispatch=lambda: dispatched.append(True),
            )
    finally:
        candidate.workspace_lease.close()

    assert dispatched == [True]


@pytest.mark.parametrize(
    ("clock_crash_call", "expected_stages", "expects_runtime"),
    [(1, [], False), (2, ["scan"], True)],
)
def test_release_clock_failure_retains_valid_lifecycle_checkpoint(
    invocation_paths: dict[str, Path],
    clock_crash_call: int,
    expected_stages: list[str],
    expects_runtime: bool,
) -> None:
    from docmend.scale_qualification import _evidence  # pyright: ignore[reportPrivateUsage]

    request = replace(_request(invocation_paths, diagnostic=True), tier="release")
    source = FakeServices().source
    runtime = FakeCandidateRuntime()
    runtime.clock_crash_call = clock_crash_call

    with pytest.raises(ExecutionInterrupted) as caught:
        _execute_real_seam(request, source, FakeBuilder(), runtime)
    result = caught.value.checkpoint
    try:
        evidence = _evidence(request, source, SHA_C, None, result, result.reasons)
    finally:
        assert result.workspace_lease is not None
        result.workspace_lease.close()

    assert result.reasons == ("harness-error",)
    assert [stage.stage for stage in result.stages] == expected_stages
    assert (result.workflow_runtime is not None) is expects_runtime
    assert evidence.status == "incomplete"


def test_release_workspace_replacement_after_dispatch_retains_attempt_truth(
    invocation_paths: dict[str, Path],
) -> None:
    from docmend.scale_qualification import _evidence  # pyright: ignore[reportPrivateUsage]

    request = replace(_request(invocation_paths, diagnostic=True), tier="release")
    source = FakeServices().source
    runtime = FakeCandidateRuntime()
    runtime.replace_workspace_after_launch_stage = "scan"

    result = _execute_real_seam(request, source, FakeBuilder(), runtime)
    evidence = _evidence(request, source, SHA_C, None, result, result.reasons)

    assert result.reasons == ("harness-error",)
    assert [stage.stage for stage in result.stages] == ["scan"]
    assert not result.stages[0].artifact_validated
    assert result.workflow_runtime is not None
    assert evidence.status == "incomplete"


def test_qualify__invalid_workspace_still_publishes_incomplete_evidence(
    invocation_paths: dict[str, Path],
) -> None:
    builder = FakeBuilder()
    runtime = FakeCandidateRuntime()
    runtime.replace_workspace_after_launch_stage = "scan"

    outcome = qualify(
        _request(invocation_paths, diagnostic=True),
        services=_LifecycleServices(builder, runtime),
    )

    assert outcome.exit_code == 1
    assert outcome.evidence_published
    assert outcome.evidence.status == "incomplete"
    assert outcome.evidence.outcome_reason == "harness-error"
    assert read_scale_evidence(invocation_paths["evidence"]) == outcome.evidence
    assert builder.lease is not None
    with pytest.raises(BuildContractError, match="closed"):
        builder.lease.require_current_identity()


def test_workspace_replacement_after_validation_retains_stage_exit_precedence(
    invocation_paths: dict[str, Path],
) -> None:
    from docmend.scale_qualification import _evidence  # pyright: ignore[reportPrivateUsage]

    request = replace(_request(invocation_paths, diagnostic=True), tier="release")
    source = FakeServices().source
    runtime = FakeCandidateRuntime()
    runtime.unexpected_exit_stage = "scan"
    runtime.replace_workspace_after_validation_stage = "scan"

    result = _execute_real_seam(request, source, FakeBuilder(), runtime)
    evidence = _evidence(request, source, SHA_C, None, result, result.reasons)

    assert result.reasons == ("stage-exit", "harness-error")
    assert result.stages[0].artifact_validated
    assert evidence.status == "failed"
    assert evidence.outcome_reason == "stage-exit"


def test_qualify__late_execution_interrupt_retains_prefix_and_closes_lease(
    invocation_paths: dict[str, Path],
) -> None:
    builder = FakeBuilder()
    runtime = FakeCandidateRuntime()
    runtime.reconcile_crash = KeyError("synthetic late crash")
    defaults = DefaultQualificationServices(builder=builder, runtime=runtime)

    class Services:
        def inspect_source(self, repository: Path) -> SourceProvenance:
            return replace(FakeServices().source, repository=repository)

        def load_reference(self, path: Path) -> tuple[ReferenceEnvironment, str]:
            del path
            return _reference(), SHA_C

        def load_threshold(self, path: Path, reference_sha256: str) -> ThresholdContext:
            del path, reference_sha256
            raise AssertionError("diagnostic pilot must not load thresholds")

        def execute(
            self,
            request: QualificationRequest,
            source: SourceProvenance,
            reference: ReferenceEnvironment,
            reference_sha256: str,
            threshold_context: ThresholdContext | None,
        ) -> ExecutionResult:
            return defaults.execute(
                request,
                source,
                reference,
                reference_sha256,
                threshold_context,
            )

        def recheck_source(self, source: SourceProvenance) -> None:
            del source

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

    outcome = qualify(
        _request(invocation_paths, diagnostic=True),
        services=Services(),
    )

    assert outcome.evidence.status == "incomplete"
    assert outcome.evidence.outcome_reason == "harness-error"
    assert [stage.stage for stage in outcome.evidence.stages] == [
        "scan",
        "plan",
        "apply",
        "verify",
    ]
    assert outcome.evidence.totals.scanned == 40
    assert builder.lease is not None
    with pytest.raises(BuildContractError, match="closed"):
        builder.lease.require_current_identity()


def test_main__input_refusal_returns_two_without_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "never-written.json"

    assert main(["--tier", "pr", "--evidence-out", str(evidence)]) == 2
    assert not evidence.exists()


def test_capture_reference__publishes_once_from_absent_private_workspace(
    invocation_paths: dict[str, Path], tmp_path: Path
) -> None:
    output = tmp_path / "captured-reference.json"
    request = ReferenceCaptureRequest(
        repository=invocation_paths["repository"],
        workspace=invocation_paths["workspace"],
        output=output,
    )

    class Services:
        def observe(self, workspace: Path) -> ReferenceEnvironment:
            assert workspace.stat().st_mode & 0o777 == 0o700
            return _reference()

        def publish_reference(self, environment: ReferenceEnvironment, path: Path) -> None:
            write_reference_environment(environment, path)

    assert capture_reference(request, services=Services()) == 0
    original = output.read_bytes()
    assert capture_reference(request, services=Services()) == 2
    assert output.read_bytes() == original


def test_capture_reference__resource_observation_failure_returns_two(
    invocation_paths: dict[str, Path], tmp_path: Path
) -> None:
    output = tmp_path / "captured-reference.json"
    request = ReferenceCaptureRequest(
        repository=invocation_paths["repository"],
        workspace=invocation_paths["workspace"],
        output=output,
    )

    class Services:
        def observe(self, workspace: Path) -> ReferenceEnvironment:
            del workspace
            raise ResourcePreflightError("synthetic unavailable reference telemetry")

        def publish_reference(self, environment: ReferenceEnvironment, path: Path) -> None:
            del environment, path
            raise AssertionError("failed observation must not publish")

    assert capture_reference(request, services=Services()) == 2
    assert not output.exists()


def test_capture_reference__rejects_workspace_replaced_between_creation_and_open(
    invocation_paths: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "captured-reference.json"
    request = ReferenceCaptureRequest(
        repository=invocation_paths["repository"],
        workspace=invocation_paths["workspace"],
        output=output,
    )
    held = tmp_path / "held-created-workspace"
    original_chmod = Path.chmod
    replaced = False
    observed = False

    def replace_before_chmod(
        path: Path,
        mode: int,
        *,
        follow_symlinks: bool = True,
    ) -> None:
        nonlocal replaced
        if path == request.workspace and not replaced:
            replaced = True
            path.replace(held)
            path.mkdir(mode=0o700)
        original_chmod(path, mode, follow_symlinks=follow_symlinks)

    class Services:
        def observe(self, workspace: Path) -> ReferenceEnvironment:
            nonlocal observed
            del workspace
            observed = True
            return _reference()

        def publish_reference(self, environment: ReferenceEnvironment, path: Path) -> None:
            write_reference_environment(environment, path)

    monkeypatch.setattr(Path, "chmod", replace_before_chmod)

    assert capture_reference(request, services=Services()) == 2
    assert replaced
    assert not observed
    assert not output.exists()


def test_capture_reference__rejects_workspace_replacement_during_observation(
    invocation_paths: dict[str, Path], tmp_path: Path
) -> None:
    output = tmp_path / "captured-reference.json"
    request = ReferenceCaptureRequest(
        repository=invocation_paths["repository"],
        workspace=invocation_paths["workspace"],
        output=output,
    )
    published = False

    class Services:
        def observe(self, workspace: Path) -> ReferenceEnvironment:
            request.workspace.replace(request.workspace.with_name("held-workspace"))
            request.workspace.mkdir(mode=0o700)
            assert workspace.stat().st_mode & 0o777 == 0o700
            return _reference()

        def publish_reference(self, environment: ReferenceEnvironment, path: Path) -> None:
            nonlocal published
            published = True
            write_reference_environment(environment, path)

    assert capture_reference(request, services=Services()) == 2
    assert not published
    assert not output.exists()


def test_capture_reference__observes_held_workspace_during_aba_swap(
    invocation_paths: dict[str, Path], tmp_path: Path
) -> None:
    output = tmp_path / "captured-reference.json"
    request = ReferenceCaptureRequest(
        repository=invocation_paths["repository"],
        workspace=invocation_paths["workspace"],
        output=output,
    )
    observed_held_identity = False

    class Services:
        def observe(self, workspace: Path) -> ReferenceEnvironment:
            nonlocal observed_held_identity
            held = request.workspace.with_name("held-workspace")
            request.workspace.replace(held)
            request.workspace.mkdir(mode=0o700)
            try:
                observed_held_identity = (
                    workspace.stat().st_dev,
                    workspace.stat().st_ino,
                ) == (held.stat().st_dev, held.stat().st_ino)
            finally:
                request.workspace.rmdir()
                held.replace(request.workspace)
            return _reference()

        def publish_reference(self, environment: ReferenceEnvironment, path: Path) -> None:
            write_reference_environment(environment, path)

    assert capture_reference(request, services=Services()) == 0
    assert observed_held_identity
    assert output.is_file()


def test_capture_reference__replaced_output_parent_is_never_used(
    invocation_paths: dict[str, Path], tmp_path: Path
) -> None:
    output_parent = tmp_path / "reference-output"
    output_parent.mkdir()
    held_parent = tmp_path / "held-reference-output"
    output = output_parent / "reference.json"
    request = ReferenceCaptureRequest(
        repository=invocation_paths["repository"],
        workspace=invocation_paths["workspace"],
        output=output,
    )
    published = False

    class Services:
        def observe(self, workspace: Path) -> ReferenceEnvironment:
            del workspace
            output_parent.replace(held_parent)
            output_parent.mkdir()
            return _reference()

        def publish_reference(self, environment: ReferenceEnvironment, path: Path) -> None:
            nonlocal published
            published = True
            write_reference_environment(environment, path)

    assert capture_reference(request, services=Services()) == 2
    assert not published
    assert not output.exists()
    assert not (held_parent / output.name).exists()
