"""File-size qualification contracts independent of corpus cardinality."""

import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from pydantic import ValidationError

import docmend.scale_qualification as scale_qualification
from docmend.artifacts import read_report_snapshot, read_verify_report
from docmend.config import DocmendConfig
from docmend.scale_build import CandidateBuild, SourceProvenance
from docmend.scale_evidence import (
    FILE_SIZE_RSS_LIMIT_BYTES,
    FileSizeCaseEvidence,
    FileSizeEncoding,
    FileSizePreservation,
    FileSizeStageEvidence,
    FilesystemCapacityEvidence,
    PreflightEvidence,
    QualificationTotals,
    ReferenceEnvironment,
    ScaleEvidence,
    ScaleEvidenceError,
    StageName,
    current_artifact_schema_versions,
    validate_qualification_document,
)
from docmend.scale_qualification import (
    DefaultCandidateRuntime,
    ExecutionInterrupted,
    ExecutionResult,
    FileSizeCase,
    FileSizeRunResult,
    QualificationInputError,
    QualificationRequest,
    StageLaunch,
    accepted_evidence_name,
    execute_file_size_lane,
    file_size_cases,
    parse_args,
)
from docmend.scale_resources import observe_reference_environment
from docmend.scale_stage import StageRequest, StageResult
from docmend.writer.manifest import read_manifest_chain


def _stage(
    stage: StageName,
    *,
    backup_bytes: int = 0,
) -> FileSizeStageEvidence:
    return FileSizeStageEvidence(
        stage=stage,
        elapsed_seconds=1.0,
        peak_rss_bytes=64 * 1024**2,
        vm_swap_peak_bytes=0,
        exit_code=0,
        completed=True,
        artifact_validated=True,
        timeout_outcome=("within-budget" if stage in {"scan", "plan"} else "not-applicable"),
        backup_bytes=backup_bytes,
    )


def _case(
    *,
    size_mib: int = 100,
    encoding: FileSizeEncoding = "utf-8",
    preservation: FileSizePreservation = "external",
) -> FileSizeCaseEvidence:
    source_bytes = size_mib * 1024**2
    backup_bytes = source_bytes if preservation == "tool" else 0
    return FileSizeCaseEvidence(
        size_mib=size_mib,
        encoding=encoding,
        preservation=preservation,
        source_bytes=source_bytes,
        stages=(
            _stage("scan"),
            _stage("plan"),
            _stage("apply", backup_bytes=backup_bytes),
            _stage("verify"),
        ),
        backup_bytes=backup_bytes,
        scanned_files=1,
        scanned_bytes=source_bytes,
        planned_actions=1,
        applied_actions=1,
        verified_actions=1,
        expected_findings=0,
        observed_findings=0,
        peak_rss_bytes=64 * 1024**2,
        rss_limit_bytes=FILE_SIZE_RSS_LIMIT_BYTES,
        rss_passed=True,
        watchdog_passed=True,
        coverage_reconciled=True,
        findings_reconciled=True,
        passed=True,
    )


def _passing_preflight() -> PreflightEvidence:
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
        reference_environment_match=True,
        binding_filesystem=True,
        ram_requirement_met=True,
        passed=True,
    )


def _zero_totals() -> QualificationTotals:
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


def _file_size_evidence() -> ScaleEvidence:
    recipes = file_size_cases(DocmendConfig().limits.max_file_size_mib)
    cases = tuple(
        _case(
            size_mib=recipe.size_mib,
            encoding=recipe.encoding,
            preservation=recipe.preservation,
        )
        for recipe in recipes
    )
    now = datetime.now(UTC)
    return ScaleEvidence(
        status="passing",
        tier="file-size",
        candidate_commit="a" * 40,
        package_version="2.0.0",
        build_frontend_version="0.11.6",
        build_backend_version="0.11.6",
        wheel_sha256="sha256:" + "1" * 64,
        lock_sha256="sha256:" + "2" * 64,
        reference_environment_sha256="sha256:" + "3" * 64,
        artifact_schema_versions=current_artifact_schema_versions(),
        python_version="3.14.0",
        kernel_version="test-kernel",
        memory_measurement="external-rss",
        cache_classification="warm",
        started_at=now,
        completed_at=now,
        preflight=_passing_preflight(),
        outcome_reason=None,
        file_count=len(cases),
        corpus_bytes=sum(case.source_bytes for case in cases),
        stages=[],
        totals=_zero_totals(),
        thresholds=None,
        workflow_runtime=None,
        file_size_cases=cases,
        configured_max_file_size_mib=DocmendConfig().limits.max_file_size_mib,
    )


def test_file_size_matrix__derives_boundaries_from_config() -> None:
    maximum = DocmendConfig().limits.max_file_size_mib
    expected_sizes = {
        1,
        *((maximum * numerator + 3) // 4 for numerator in range(1, 5)),
    }

    cases = file_size_cases(maximum)

    assert max(case.size_mib for case in cases) == maximum
    assert {case.encoding for case in cases} == {"utf-8", "windows-1252"}
    external = [case for case in cases if case.preservation == "external"]
    assert {case.size_mib for case in external} == expected_sizes


def test_file_size_matrix__bounds_tool_backups_to_maximum_cases() -> None:
    maximum = DocmendConfig().limits.max_file_size_mib

    tool_cases = [case for case in file_size_cases(maximum) if case.preservation == "tool"]

    assert {(case.size_mib, case.encoding) for case in tool_cases} == {
        (maximum, "utf-8"),
        (maximum, "windows-1252"),
    }


@given(st.integers(min_value=1, max_value=10_000))
@example(1)
@example(2)
@example(3)
@example(4)
@example(5)
@example(100)
def test_file_size_matrix__any_configured_maximum_is_exact_and_unique(
    maximum: int,
) -> None:
    cases = file_size_cases(maximum)
    expected_sizes = {
        1,
        *((maximum * numerator + 3) // 4 for numerator in range(1, 5)),
    }
    external = {(case.size_mib, case.encoding) for case in cases if case.preservation == "external"}
    tool = {(case.size_mib, case.encoding) for case in cases if case.preservation == "tool"}

    assert max(case.size_mib for case in cases) == maximum
    assert len(cases) == len({(case.size_mib, case.encoding, case.preservation) for case in cases})
    assert all(1 <= case.size_mib <= maximum for case in cases)
    assert external == {
        (size, encoding) for size in expected_sizes for encoding in ("utf-8", "windows-1252")
    }
    assert tool == {(maximum, "utf-8"), (maximum, "windows-1252")}


def test_file_size_case__reconciles_peak_backup_watchdog_and_coverage() -> None:
    evidence = _case(preservation="tool")

    assert evidence.peak_rss_bytes < 2 * 1024**3
    assert evidence.backup_bytes == evidence.source_bytes
    assert evidence.passed is True


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        pytest.param("peak_rss_bytes", FILE_SIZE_RSS_LIMIT_BYTES, "RSS", id="rss"),
        pytest.param("backup_bytes", 0, "backup", id="backup"),
        pytest.param("verified_actions", 0, "coverage", id="coverage"),
        pytest.param("observed_findings", 1, "finding", id="findings"),
    ],
)
def test_file_size_case__rejects_false_passing_verdicts(
    field: str,
    value: object,
    message: str,
) -> None:
    payload = _case(preservation="tool").model_dump(mode="python")
    payload[field] = value

    with pytest.raises(ValidationError, match=message):
        FileSizeCaseEvidence.model_validate(payload)


@pytest.mark.parametrize("field", ["peak_rss_bytes", "exit_code"])
def test_file_size_stage__requires_fresh_child_measurement(field: str) -> None:
    payload = _stage("plan").model_dump(mode="python")
    payload[field] = None

    with pytest.raises(ValidationError, match="completed stage"):
        FileSizeStageEvidence.model_validate(payload)

    document = _file_size_evidence().model_dump(mode="json", by_alias=True)
    document["file_size_cases"][0]["stages"][1][field] = None
    with pytest.raises(ScaleEvidenceError):
        validate_qualification_document("scale-evidence", document)


def test_file_size_stage__distinguishes_child_completion_from_artifact_validation() -> None:
    payload = _stage("verify").model_dump(mode="python")
    payload["artifact_validated"] = False

    evidence = FileSizeStageEvidence.model_validate(payload)

    assert evidence.completed is True
    assert evidence.artifact_validated is False


def test_file_size_stage__validated_watchdog_stage_requires_measured_outcome() -> None:
    payload = _stage("scan").model_dump(mode="python")
    payload["timeout_outcome"] = "not-applicable"

    with pytest.raises(ValidationError, match="measured timeout"):
        FileSizeStageEvidence.model_validate(payload)


@pytest.mark.parametrize("stage", ["scan", "plan"])
def test_file_size_stage__unvalidated_watchdog_stage_rejects_measured_outcome(
    stage: Literal["scan", "plan"],
) -> None:
    payload = _stage(stage).model_dump(mode="python")
    payload.update(artifact_validated=False, timeout_outcome="within-budget")

    with pytest.raises(ValidationError, match="cannot claim a timeout"):
        FileSizeStageEvidence.model_validate(payload)

    document = _file_size_evidence().model_dump(mode="json", by_alias=True)
    stage_index = 0 if stage == "scan" else 1
    document["file_size_cases"][0]["stages"][stage_index].update(
        artifact_validated=False,
        timeout_outcome="within-budget",
    )
    with pytest.raises(ScaleEvidenceError):
        validate_qualification_document("scale-evidence", document)


def test_file_size_evidence__artifact_invalid_is_not_promoted_to_conservation_failure() -> None:
    evidence = _file_size_evidence()
    cases = list(evidence.file_size_cases or ())
    case_payload = cases[0].model_dump(mode="python")
    stages = list(case_payload["stages"])
    stages[-1] = {**stages[-1], "artifact_validated": False}
    case_payload.update(
        stages=tuple(stages),
        verified_actions=0,
        coverage_reconciled=False,
        passed=False,
    )
    cases[0] = FileSizeCaseEvidence.model_validate(case_payload)
    document = evidence.model_dump(mode="python")
    document.update(
        status="incomplete",
        outcome_reason="artifact-invalid",
        file_size_cases=tuple(cases),
    )

    incomplete = ScaleEvidence.model_validate(document)

    assert incomplete.status == "incomplete"
    assert incomplete.outcome_reason == "artifact-invalid"


def test_file_size_evidence__partial_measured_rss_failure_is_trustworthy() -> None:
    evidence = _file_size_evidence()
    cases = list(evidence.file_size_cases or ())
    case_payload = cases[0].model_dump(mode="python")
    scan = case_payload["stages"][0]
    scan.update(peak_rss_bytes=FILE_SIZE_RSS_LIMIT_BYTES)
    case_payload.update(
        stages=(scan,),
        backup_bytes=0,
        planned_actions=0,
        applied_actions=0,
        verified_actions=0,
        peak_rss_bytes=FILE_SIZE_RSS_LIMIT_BYTES,
        rss_passed=False,
        coverage_reconciled=False,
        passed=False,
    )
    cases[0] = FileSizeCaseEvidence.model_validate(case_payload)
    document = evidence.model_dump(mode="python")
    document.update(
        status="failed",
        outcome_reason="threshold-exceeded",
        file_size_cases=tuple(cases),
    )

    failed = ScaleEvidence.model_validate(document)

    assert failed.status == "failed"


def test_file_size_evidence__partial_validated_conservation_failure_is_trustworthy() -> None:
    evidence = _file_size_evidence()
    cases = list(evidence.file_size_cases or ())
    case_payload = cases[0].model_dump(mode="python")
    case_payload.update(
        stages=case_payload["stages"][:2],
        backup_bytes=0,
        planned_actions=0,
        applied_actions=0,
        verified_actions=0,
        coverage_reconciled=False,
        passed=False,
    )
    cases[0] = FileSizeCaseEvidence.model_validate(case_payload)
    document = evidence.model_dump(mode="python")
    document.update(
        status="failed",
        outcome_reason="conservation-mismatch",
        file_size_cases=tuple(cases),
    )

    failed = ScaleEvidence.model_validate(document)

    assert failed.status == "failed"


def test_file_size_evidence__schema_rejects_out_of_order_case_stages() -> None:
    document = _file_size_evidence().model_dump(mode="json", by_alias=True)
    document["file_size_cases"][0]["stages"][1]["stage"] = "scan"

    with pytest.raises(ScaleEvidenceError):
        validate_qualification_document("scale-evidence", document)


def test_file_size_models__contain_no_path_or_document_body_fields() -> None:
    keys = set(_case().model_dump(mode="json"))

    assert not keys & {"path", "body", "content", "hostname", "username"}


def test_file_size_evidence__model_and_schema_accept_exact_matrix() -> None:
    evidence = _file_size_evidence()
    document = evidence.model_dump(mode="json", by_alias=True)

    validate_qualification_document("scale-evidence", document)
    assert len(evidence.file_size_cases or ()) == len(
        file_size_cases(DocmendConfig().limits.max_file_size_mib)
    )


def test_file_size_evidence__requires_nonempty_exact_matrix() -> None:
    payload = _file_size_evidence().model_dump(mode="python")
    payload["file_size_cases"] = ()

    with pytest.raises(ValidationError, match="exact matrix"):
        ScaleEvidence.model_validate(payload)


def test_file_size_evidence__binds_matrix_to_recorded_configured_maximum() -> None:
    payload = _file_size_evidence().model_dump(mode="python")
    payload["configured_max_file_size_mib"] -= 1

    with pytest.raises(ValidationError, match="configured maximum"):
        ScaleEvidence.model_validate(payload)


def test_non_file_size_evidence__rejects_case_payload() -> None:
    payload = _file_size_evidence().model_dump(mode="python")
    payload.update(
        tier="pilot",
        status="incomplete",
        outcome_reason="harness-error",
        preflight=None,
    )

    with pytest.raises(ValidationError, match="only file-size"):
        ScaleEvidence.model_validate(payload)


def test_file_size_evidence__schema_accepts_case_threshold_failure() -> None:
    evidence = _file_size_evidence()
    cases = list(evidence.file_size_cases or ())
    payload = cases[0].model_dump(mode="python")
    stage_payloads = list(payload["stages"])
    for stage in stage_payloads:
        stage["peak_rss_bytes"] = FILE_SIZE_RSS_LIMIT_BYTES
    payload.update(
        stages=tuple(stage_payloads),
        peak_rss_bytes=FILE_SIZE_RSS_LIMIT_BYTES,
        rss_passed=False,
        passed=False,
    )
    cases[0] = FileSizeCaseEvidence.model_validate(payload)
    document = evidence.model_dump(mode="python")
    document.update(
        status="failed",
        outcome_reason="threshold-exceeded",
        file_size_cases=tuple(cases),
    )

    failed = ScaleEvidence.model_validate(document)
    validate_qualification_document(
        "scale-evidence",
        failed.model_dump(mode="json", by_alias=True),
    )


def test_file_size_evidence__incomplete_build_keeps_pending_matrix() -> None:
    evidence = _file_size_evidence()
    pending = tuple(
        FileSizeCaseEvidence.model_validate(
            {
                **case.model_dump(mode="python"),
                "stages": (),
                "backup_bytes": 0,
                "planned_actions": 0,
                "applied_actions": 0,
                "verified_actions": 0,
                "peak_rss_bytes": 0,
                "rss_passed": True,
                "coverage_reconciled": False,
                "passed": False,
            }
        )
        for case in evidence.file_size_cases or ()
    )
    payload = evidence.model_dump(mode="python")
    payload.update(
        status="incomplete",
        outcome_reason="build-failed",
        wheel_sha256=None,
        preflight=None,
        file_size_cases=pending,
    )

    incomplete = ScaleEvidence.model_validate(payload)
    validate_qualification_document(
        "scale-evidence",
        incomplete.model_dump(mode="json", by_alias=True),
    )


def _file_size_argv(root: Path) -> list[str]:
    reference = root / "reference.json"
    reference.write_text("{}", encoding="utf-8")
    accepted = root / "accepted"
    accepted.mkdir()
    return [
        "--tier",
        "file-size",
        "--workspace",
        str(root / "workspace"),
        "--reference-environment",
        str(reference),
        "--evidence-out",
        str(root / "evidence.json"),
        "--accept-to",
        str(accepted),
    ]


def test_parse_args__file_size_binding_requires_acceptance(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    argv = _file_size_argv(tmp_path)

    request = parse_args(argv, cwd=repository)

    assert isinstance(request, QualificationRequest)
    assert request.tier == "file-size"
    assert request.count == len(file_size_cases(DocmendConfig().limits.max_file_size_mib))
    with pytest.raises(QualificationInputError, match="requires --accept-to"):
        parse_args(argv[:-2], cwd=repository)


def test_parse_args__file_size_diagnostic_uses_ordinary_evidence(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    argv = _file_size_argv(tmp_path)
    argv = [*argv[:-2], "--diagnostic"]

    request = parse_args(argv, cwd=repository)

    assert isinstance(request, QualificationRequest)
    assert request.diagnostic is True
    assert request.accept_to is None


def test_accepted_evidence_name__file_size_omits_cardinality() -> None:
    commit = "a" * 40

    assert accepted_evidence_name(commit, "file-size", 12) == f"{commit}-file-size.json"


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
        kernel_version="test-kernel",
    )


def test_file_size_lane__builds_and_runs_the_exact_inspected_head(tmp_path: Path) -> None:
    source = SourceProvenance(
        repository=tmp_path / "repository",
        commit="b" * 40,
        package_name="docmend",
        package_version="2.0.0",
        build_backend="uv_build",
        build_backend_version="0.11.6",
        build_frontend_version="0.11.6",
        pyproject_sha256="sha256:" + "1" * 64,
        lock_sha256="sha256:" + "2" * 64,
        pyproject_bytes=b"pyproject",
        lock_bytes=b"lock",
    )
    request = QualificationRequest(
        tier="file-size",
        diagnostic=True,
        count=len(file_size_cases(DocmendConfig().limits.max_file_size_mib)),
        repository=source.repository,
        workspace=tmp_path / "workspace",
        reference_environment=tmp_path / "reference.json",
        thresholds=None,
        evidence_out=tmp_path / "evidence.json",
        accept_to=None,
        python_executable=Path("/usr/bin/python3.14"),
    )

    class Builder:
        built_commit: str | None = None

        def prepare(
            self,
            request: QualificationRequest,
            source: SourceProvenance,
        ) -> CandidateBuild:
            del request
            self.built_commit = source.commit
            return cast(
                "CandidateBuild",
                SimpleNamespace(
                    commit=source.commit,
                    wheel_sha256="sha256:" + "3" * 64,
                    workspace_lease=None,
                ),
            )

    class Runtime:
        received_commit: str | None = None

        def run_file_size_matrix(
            self,
            request: QualificationRequest,
            candidate: CandidateBuild,
            reference_environment: ReferenceEnvironment,
            recipes: tuple[FileSizeCase, ...],
        ) -> FileSizeRunResult:
            del reference_environment
            self.received_commit = candidate.commit
            assert len(recipes) == request.count
            cases = tuple(
                _case(
                    size_mib=recipe.size_mib,
                    encoding=recipe.encoding,
                    preservation=recipe.preservation,
                )
                for recipe in file_size_cases(DocmendConfig().limits.max_file_size_mib)
            )
            return FileSizeRunResult(
                preflight=_passing_preflight(),
                cases=cases,
                reasons=(),
            )

    builder = Builder()
    runtime = Runtime()

    result = execute_file_size_lane(
        request,
        source,
        _reference(),
        builder=builder,
        runtime=runtime,
    )

    assert builder.built_commit == source.commit
    assert runtime.received_commit == source.commit
    assert result.wheel_sha256 == "sha256:" + "3" * 64
    assert result.file_size_cases is not None
    assert all(case.peak_rss_bytes < FILE_SIZE_RSS_LIMIT_BYTES for case in result.file_size_cases)

    future_started = datetime(2100, 1, 1, tzinfo=UTC)

    class InterruptingRuntime:
        def run_file_size_matrix(
            self,
            request: QualificationRequest,
            candidate: CandidateBuild,
            reference_environment: ReferenceEnvironment,
            recipes: tuple[FileSizeCase, ...],
        ) -> FileSizeRunResult:
            del request, reference_environment
            cases = tuple(
                _case(
                    size_mib=recipe.size_mib,
                    encoding=recipe.encoding,
                    preservation=recipe.preservation,
                )
                for recipe in recipes
            )
            raise ExecutionInterrupted(
                ExecutionResult(
                    wheel_sha256=candidate.wheel_sha256,
                    preflight=_passing_preflight(),
                    stages=(),
                    totals=_zero_totals(),
                    thresholds=None,
                    workflow_runtime=None,
                    reasons=(),
                    started_at=future_started,
                    completed_at=future_started,
                    python_version="3.14.6",
                    kernel_version="test",
                    corpus_bytes=sum(case.source_bytes for case in cases),
                    file_size_cases=cases,
                    candidate=candidate,
                )
            )

    with pytest.raises(ExecutionInterrupted) as caught:
        execute_file_size_lane(
            request,
            source,
            _reference(),
            builder=builder,
            runtime=InterruptingRuntime(),
        )

    assert caught.value.checkpoint.started_at < future_started


@pytest.mark.parametrize(
    ("encoding", "preservation"),
    [
        pytest.param("utf-8", "external", id="utf8-external"),
        pytest.param("windows-1252", "external", id="windows1252-external"),
        pytest.param("utf-8", "tool", id="utf8-tool-backup"),
    ],
)
def test_file_size_stage_commands__one_mib_real_subprocess_pipeline(
    tmp_path: Path,
    encoding: Literal["utf-8", "windows-1252"],
    preservation: Literal["external", "tool"],
) -> None:
    pipeline = tmp_path / "pipeline"
    corpus = pipeline / "corpus"
    corpus.mkdir(parents=True)
    source = corpus / "document.txt"
    seed = "legacy café line  \r\n".encode(encoding)
    source_bytes = 1024**2
    source.write_bytes((seed * (source_bytes // len(seed) + 1))[:source_bytes])

    executable = Path(sys.executable).with_name("docmend")
    inventory = pipeline / "inventory.json"
    plan = pipeline / "plan.json"
    report_path = pipeline / "report.json"
    verify_path = pipeline / "verify.json"

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(executable), *args],
            cwd=pipeline,
            check=False,
            capture_output=True,
            text=True,
        )

    scanned = run("scan", str(corpus), "--report", str(inventory))
    assert scanned.returncode == 0, scanned.stderr
    planned = run("plan", "--inventory", str(inventory), "--out", str(plan))
    assert planned.returncode == 0, planned.stderr

    apply_args = ["apply", str(plan), "--write", "--report", str(report_path)]
    backup_root = pipeline / "backups"
    if preservation == "tool":
        apply_args.extend(("--backup-dir", str(backup_root)))
    else:
        apply_args.extend(("--preserved-by", "external"))
    applied = run(*apply_args)
    assert applied.returncode == 0, applied.stderr

    report, _report_sha256 = read_report_snapshot(report_path)
    manifest = pipeline / ".docmend" / f"docmend-{report.run_id}-manifest.jsonl"
    verified = run(
        "verify",
        str(corpus),
        "--plan",
        str(plan),
        "--manifest",
        str(manifest),
        "--report",
        str(report_path),
        "--out",
        str(verify_path),
    )
    assert verified.returncode == 0, verified.stderr
    verify_report = read_verify_report(verify_path)
    assert verify_report.checked_files == 1
    assert not verify_report.findings

    chain = read_manifest_chain(
        (manifest,),
        check_backup_objects=preservation == "tool",
    )
    backup_paths = {
        record.backup_path
        for manifest_set in chain.sets
        for record in manifest_set.records
        if record.backup_path is not None
    }
    if preservation == "tool":
        assert sum(Path(path).stat().st_size for path in backup_paths) == source_bytes
    else:
        assert backup_paths == set()


def test_default_file_size_runtime__dispatches_four_fresh_measured_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Resource-floor behavior has dedicated coverage; this unit isolates stage dispatch.
    monkeypatch.setattr("docmend.scale_resources.MIN_BINDING_RAM_BYTES", 0)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    request = QualificationRequest(
        tier="file-size",
        diagnostic=True,
        count=1,
        repository=tmp_path / "repository",
        workspace=workspace,
        reference_environment=tmp_path / "reference.json",
        thresholds=None,
        evidence_out=tmp_path / "evidence.json",
        accept_to=None,
        python_executable=Path("/usr/bin/python3.14"),
    )
    workspace_lease = object()
    candidate = cast(
        "CandidateBuild",
        SimpleNamespace(
            commit="c" * 40,
            executable=tmp_path / "venv" / "bin" / "docmend",
            venv=tmp_path / "venv",
            wheel_sha256="sha256:" + "3" * 64,
            workspace_lease=workspace_lease,
            require_current_identity=lambda: None,
        ),
    )
    run_id = "run_20260714T120000Z_abcdef"

    def fake_inventory(_path: Path) -> object:
        return SimpleNamespace(
            totals=SimpleNamespace(
                files=1,
                skipped=0,
                skipped_by_reason=SimpleNamespace(timeout=0),
            ),
            files=(SimpleNamespace(size_bytes=1024**2),),
        )

    def fake_plan(_path: Path) -> object:
        return (
            SimpleNamespace(totals=SimpleNamespace(actions=1, skips=0), skips=()),
            "sha256:" + "1" * 64,
        )

    def fake_report(_path: Path) -> object:
        return (
            SimpleNamespace(
                run_id=run_id,
                totals=SimpleNamespace(applied=1, failed=0, not_attempted=0),
            ),
            "sha256:" + "2" * 64,
        )

    def fake_manifest_chain(
        _paths: tuple[Path, ...],
        *,
        check_backup_objects: bool,
    ) -> object:
        if not check_backup_objects:
            return SimpleNamespace(sets=())
        backup = tmp_path / "tool-backup.bin"
        backup.write_bytes(b"x" * 1024**2)
        return SimpleNamespace(
            sets=(SimpleNamespace(records=(SimpleNamespace(backup_path=str(backup)),)),)
        )

    def fake_verify_report(_path: Path) -> object:
        return SimpleNamespace(checked_files=1, findings=())

    monkeypatch.setattr(
        "docmend.scale_qualification.read_inventory",
        fake_inventory,
    )
    monkeypatch.setattr(
        "docmend.scale_qualification.read_plan_snapshot",
        fake_plan,
    )
    monkeypatch.setattr(
        "docmend.scale_qualification.read_report_snapshot",
        fake_report,
    )
    monkeypatch.setattr(
        "docmend.scale_qualification.read_manifest_chain",
        fake_manifest_chain,
    )
    monkeypatch.setattr(
        "docmend.scale_qualification.read_verify_report",
        fake_verify_report,
    )
    launches: list[tuple[StageRequest, Path]] = []

    class RecordingRuntime(DefaultCandidateRuntime):
        def launch(
            self,
            candidate: CandidateBuild,
            request: StageRequest,
            *,
            private_workspace: Path,
            on_dispatch: Callable[[], None],
        ) -> StageLaunch:
            del candidate
            on_dispatch()
            launches.append((request, private_workspace))
            return StageLaunch(
                wrapper_exit_code=0,
                result=StageResult(
                    stage=request.stage,
                    completed=True,
                    exit_code=0,
                    elapsed_seconds=0.25,
                    peak_rss_bytes=64 * 1024**2,
                    vm_swap_peak_bytes=0,
                    tracing_enabled=False,
                    stdout=request.stdout,
                    stderr=request.stderr,
                    error_code=None,
                ),
            )

    reference = observe_reference_environment(workspace).environment
    result = RecordingRuntime().run_file_size_matrix(
        request,
        candidate,
        reference,
        (
            FileSizeCase(size_mib=1, encoding="utf-8", preservation="external"),
            FileSizeCase(size_mib=1, encoding="windows-1252", preservation="tool"),
        ),
    )

    assert [launch.stage for launch, _private in launches] == [
        "scan",
        "plan",
        "apply",
        "verify",
        "scan",
        "plan",
        "apply",
        "verify",
    ]
    assert len({private for _launch, private in launches}) == 8
    assert {private.parents[1].name for _launch, private in launches} == {
        "case-00",
        "case-01",
    }
    assert set(result.reasons) <= {"reference-mismatch"}
    assert all(case.passed for case in result.cases)
    assert result.cases[1].backup_bytes == 1024**2

    fault_workspace = tmp_path / "fault-workspace"
    fault_workspace.mkdir()
    fault_request = replace(
        request,
        workspace=fault_workspace,
        evidence_out=tmp_path / "fault-evidence.json",
    )
    reference = observe_reference_environment(fault_workspace).environment
    real_mkdir_private = cast(
        "Callable[[Path], None]",
        vars(scale_qualification)["_mkdir_private"],
    )

    def fail_plan_workspace(path: Path) -> None:
        if path.name == "plan":
            raise RuntimeError("injected stage setup failure")
        real_mkdir_private(path)

    def one_case(_maximum: int) -> tuple[FileSizeCase, ...]:
        return (FileSizeCase(size_mib=1, encoding="utf-8", preservation="external"),)

    monkeypatch.setattr("docmend.scale_qualification._mkdir_private", fail_plan_workspace)
    monkeypatch.setattr(scale_qualification, "file_size_cases", one_case)
    source = SourceProvenance(
        repository=tmp_path / "repository",
        commit=candidate.commit,
        package_name="docmend",
        package_version="2.0.0",
        build_backend="uv_build",
        build_backend_version="0.11.6",
        build_frontend_version="0.11.6",
        pyproject_sha256="sha256:" + "4" * 64,
        lock_sha256="sha256:" + "5" * 64,
        pyproject_bytes=b"pyproject",
        lock_bytes=b"lock",
    )

    class Builder:
        def prepare(
            self,
            request: QualificationRequest,
            source: SourceProvenance,
        ) -> CandidateBuild:
            del request, source
            return candidate

    fault = execute_file_size_lane(
        fault_request,
        source,
        reference,
        builder=Builder(),
        runtime=RecordingRuntime(),
    )

    assert "supervisor-failed" in fault.reasons
    assert fault.file_size_cases is not None
    assert [stage.stage for stage in fault.file_size_cases[0].stages] == ["scan", "plan"]
    assert fault.file_size_cases[0].stages[0].artifact_validated is True
    assert fault.file_size_cases[0].stages[1].completed is False
    assert fault.workspace_lease is workspace_lease

    unexpected_workspace = tmp_path / "unexpected-workspace"
    unexpected_workspace.mkdir()
    unexpected_request = replace(
        request,
        workspace=unexpected_workspace,
        evidence_out=tmp_path / "unexpected-evidence.json",
    )
    unexpected_reference = observe_reference_environment(unexpected_workspace).environment
    monkeypatch.setattr("docmend.scale_qualification._mkdir_private", real_mkdir_private)

    def two_cases(_maximum: int) -> tuple[FileSizeCase, ...]:
        return (
            FileSizeCase(size_mib=1, encoding="utf-8", preservation="external"),
            FileSizeCase(size_mib=1, encoding="windows-1252", preservation="external"),
        )

    monkeypatch.setattr(
        scale_qualification,
        "file_size_cases",
        two_cases,
    )
    plan_reads = 0

    def crash_during_second_plan(_path: Path) -> object:
        nonlocal plan_reads
        plan_reads += 1
        if plan_reads == 2:
            raise AssertionError("injected unexpected artifact-reader failure")
        return fake_plan(_path)

    monkeypatch.setattr(
        "docmend.scale_qualification.read_plan_snapshot",
        crash_during_second_plan,
    )

    with pytest.raises(ExecutionInterrupted) as caught:
        execute_file_size_lane(
            unexpected_request,
            source,
            unexpected_reference,
            builder=Builder(),
            runtime=RecordingRuntime(),
        )

    checkpoint = caught.value.checkpoint
    assert checkpoint.wheel_sha256 == candidate.wheel_sha256
    assert checkpoint.preflight is not None
    assert checkpoint.file_size_cases is not None
    assert checkpoint.file_size_cases[0].passed is True
    assert [stage.stage for stage in checkpoint.file_size_cases[1].stages] == ["scan", "plan"]
    assert checkpoint.file_size_cases[1].stages[1].completed is True
    assert checkpoint.file_size_cases[1].stages[1].artifact_validated is False
    assert checkpoint.candidate is candidate
    assert checkpoint.workspace_lease is workspace_lease

    construction_workspace = tmp_path / "construction-workspace"
    construction_workspace.mkdir()
    construction_request = replace(
        request,
        workspace=construction_workspace,
        evidence_out=tmp_path / "construction-evidence.json",
    )
    construction_reference = observe_reference_environment(construction_workspace).environment
    monkeypatch.setattr("docmend.scale_qualification.read_plan_snapshot", fake_plan)
    real_case_evidence = cast(
        "Callable[..., FileSizeCaseEvidence]",
        vars(scale_qualification)["_file_size_case_evidence"],
    )
    case_constructions = 0

    def crash_during_second_case(*args: object, **kwargs: object) -> FileSizeCaseEvidence:
        nonlocal case_constructions
        case_constructions += 1
        if case_constructions == 2:
            raise AssertionError("injected unexpected case-construction failure")
        return real_case_evidence(*args, **kwargs)

    monkeypatch.setattr(
        "docmend.scale_qualification._file_size_case_evidence",
        crash_during_second_case,
    )

    with pytest.raises(ExecutionInterrupted) as caught:
        execute_file_size_lane(
            construction_request,
            source,
            construction_reference,
            builder=Builder(),
            runtime=RecordingRuntime(),
        )

    checkpoint = caught.value.checkpoint
    assert checkpoint.preflight is not None
    assert checkpoint.file_size_cases is not None
    assert checkpoint.file_size_cases[0].passed is True
    assert checkpoint.file_size_cases[1].stages == ()
    assert checkpoint.candidate is candidate
