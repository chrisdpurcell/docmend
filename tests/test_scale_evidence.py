"""DMR-08 public qualification evidence and executable-threshold contracts."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Literal, cast

import pytest
from pydantic import ValidationError

import docmend.scale_evidence as evidence_contract
from docmend.artifacts import ARTIFACT_KINDS, sha256_of_file
from docmend.frontmatter import FRONTMATTER_SCHEMA_VERSION
from docmend.inventory import INVENTORY_SCHEMA_VERSION
from docmend.plan import PLAN_SCHEMA_VERSION
from docmend.report import REPORT_SCHEMA_VERSION
from docmend.scale_evidence import (
    FilesystemCapacityEvidence,
    OutcomeReason,
    PreflightEvidence,
    QualificationTotals,
    ReferenceEnvironment,
    ScaleEvidence,
    ScaleEvidenceError,
    StageEvidence,
    StageName,
    ThresholdBaseline,
    ThresholdPointIdentity,
    ThresholdSet,
    ThresholdVerdict,
    derive_thresholds,
    load_threshold_baseline_snapshot,
    load_threshold_limits,
    read_reference_environment,
    read_scale_evidence,
    read_scale_evidence_snapshot,
    validate_qualification_document,
    write_reference_environment,
    write_scale_evidence,
    write_threshold_baseline,
)
from docmend.verify_report import VERIFY_REPORT_SCHEMA_VERSION
from docmend.writer.manifest import MANIFEST_SCHEMA_VERSION

SHA_ZERO = "sha256:" + "0" * 64
SHA_ONE = "sha256:" + "1" * 64
REFERENCE_SHA = "sha256:" + "a" * 64
COMMIT = "b" * 40
STAGE_NAMES: tuple[StageName, ...] = ("scan", "plan", "apply", "verify")


def reference_environment(**updates: object) -> ReferenceEnvironment:
    values: dict[str, object] = {
        "operating_system": "linux",
        "cpu_architecture": "x86_64",
        "cpu_model": "Synthetic Qualification CPU",
        "logical_cpu_count": 8,
        "ram_bytes": 32 * 1024**3,
        "storage_class": "local-ssd",
        "filesystem": "ext4",
        "mount_flags": ("rw", "relatime"),
        "python_version": "3.14.6",
        "kernel_version": "7.0.0-test",
    }
    values.update(updates)
    return ReferenceEnvironment.model_validate(values)


def _capacity(*, passed: bool = True) -> FilesystemCapacityEvidence:
    return FilesystemCapacityEvidence(
        required_bytes=1_250,
        available_bytes=2_000 if passed else 1_000,
        required_inodes=1_250,
        inode_capacity_mode="finite-statvfs",
        available_inodes=2_000 if passed else 1_000,
        margin_fraction=0.25,
        passed=passed,
    )


def _preflight(*, passed: bool = True) -> PreflightEvidence:
    return PreflightEvidence(
        filesystems=(_capacity(passed=passed),),
        capacity_margin_met=True,
        reference_environment_match=passed,
        binding_filesystem=passed,
        ram_requirement_met=passed,
        passed=passed,
    )


_STAGE_ARTIFACT_BYTES: dict[str, dict[str, int]] = {
    "scan": {
        "inventory": 1_024,
        "structured-log": 1_024,
        "stdout-log": 0,
        "stderr-log": 0,
    },
    "plan": {
        "plan": 1_024,
        "structured-log": 1_024,
        "stdout-log": 0,
        "stderr-log": 0,
    },
    "apply": {
        "report": 1_024,
        "manifest": 1_024,
        "structured-log": 1_024,
        "stdout-log": 0,
        "stderr-log": 0,
    },
    "verify": {
        "verify-report": 1_024,
        "structured-log": 1_024,
        "stdout-log": 0,
        "stderr-log": 0,
    },
}


def _stage(stage: str, *, completed: bool = True) -> StageEvidence:
    return StageEvidence.model_validate(
        {
            "stage": stage,
            "run_id": "run_20260713T000000Z_abc123" if completed else None,
            "elapsed_seconds": 1.25,
            "files_per_second": 800.0,
            "bytes_per_second": 819_200.0,
            "peak_rss_bytes": 64 * 1024**2 if completed else None,
            "python_allocation_peak_bytes": None,
            "vm_swap_peak_bytes": 0 if completed else None,
            "exit_code": 0 if completed else None,
            "completed": completed,
            "artifact_validated": completed,
            "artifact_bytes": _STAGE_ARTIFACT_BYTES[stage] if completed else {},
        }
    )


def _totals(count: int) -> QualificationTotals:
    return QualificationTotals(
        scanned=count,
        actions=count,
        clean_noops=0,
        plan_skips=0,
        applied=count,
        apply_skips=0,
        failures=0,
        not_attempted=0,
        verified=count,
        expected_findings=0,
        observed_findings=0,
    )


def scale_evidence(
    *,
    count: int = 100_000,
    status: str = "passing",
    tier: str = "pilot",
    reference_sha: str = REFERENCE_SHA,
    candidate_commit: str = COMMIT,
    build_backend_version: str = "0.11.6",
) -> ScaleEvidence:
    outcome_reason = {
        "passing": None,
        "diagnostic": "explicit-diagnostic",
        "incomplete": "harness-error",
        "failed": "stage-exit",
    }[status]
    values: dict[str, object] = {
        "status": status,
        "tier": tier,
        "candidate_commit": candidate_commit,
        "package_version": "2.0.0",
        "build_frontend_version": "0.11.6",
        "build_backend_version": build_backend_version,
        "wheel_sha256": SHA_ZERO,
        "lock_sha256": SHA_ONE,
        "reference_environment_sha256": reference_sha,
        "artifact_schema_versions": {
            "inventory": "1.2",
            "plan": "2.0",
            "report": "2.0",
            "manifest": "2.0",
            "verify-report": "1.0",
            "frontmatter": "1.0",
        },
        "python_version": "3.14.6",
        "kernel_version": "7.0.0-test",
        "memory_measurement": "external-rss",
        "cache_classification": "warm",
        "started_at": datetime(2026, 7, 13, tzinfo=UTC),
        "completed_at": datetime(2026, 7, 13, 0, 1, tzinfo=UTC),
        "preflight": _preflight(),
        "outcome_reason": outcome_reason,
        "file_count": count,
        "corpus_bytes": count * 1_024,
        "stages": [_stage(stage) for stage in ("scan", "plan", "apply", "verify")],
        "totals": _totals(count),
        "thresholds": None,
        "workflow_runtime": None,
    }
    return ScaleEvidence.model_validate(values)


class TestPublicContract:
    def test_scale_evidence_v3__retains_measured_stage_without_valid_artifact(self) -> None:
        stage = StageEvidence.model_validate(
            {
                "stage": "scan",
                "run_id": None,
                "elapsed_seconds": 1.25,
                "files_per_second": 800.0,
                "bytes_per_second": 819_200.0,
                "peak_rss_bytes": 64 * 1024**2,
                "python_allocation_peak_bytes": None,
                "vm_swap_peak_bytes": 0,
                "exit_code": 0,
                "completed": True,
                "artifact_validated": False,
                "artifact_bytes": {"stdout-log": 1_024, "stderr-log": 0},
            }
        )

        assert ScaleEvidence.model_fields["schema_version"].default == "3.0"
        assert stage.completed is True
        assert stage.artifact_validated is False
        assert stage.run_id is None

    def test_pre_scan_incomplete__records_only_proven_zero_phases(self) -> None:
        document = scale_evidence(status="incomplete").model_dump()
        document["preflight"] = None
        document["outcome_reason"] = "build-failed"
        document["stages"] = []
        document["totals"] = QualificationTotals(
            scanned=0,
            actions=0,
            clean_noops=0,
            plan_skips=0,
            applied=0,
            apply_skips=0,
            failures=0,
            not_attempted=0,
            verified=0,
            expected_findings=25,
            observed_findings=0,
        )

        evidence = ScaleEvidence.model_validate(document)

        assert evidence.preflight is None
        assert evidence.outcome_reason == "build-failed"
        assert evidence.totals.scanned == 0

    @pytest.mark.parametrize(
        "artifact_bytes",
        [
            {"inventory": 1, "stdout-log": 0, "stderr-log": 0},
            {
                "plan": 1,
                "structured-log": 1,
                "stdout-log": 0,
                "stderr-log": 0,
            },
        ],
    )
    def test_artifact_validated_stage__requires_exact_stage_keys(
        self, artifact_bytes: dict[str, int]
    ) -> None:
        document = _stage("scan").model_dump()
        document["artifact_bytes"] = artifact_bytes

        with pytest.raises(ValidationError, match="exact stage artifact keys"):
            StageEvidence.model_validate(document)

    def test_artifact_validated_stage_schema__requires_structured_and_capture_logs(self) -> None:
        document = scale_evidence().model_dump(mode="json")
        stages = cast("list[dict[str, object]]", document["stages"])
        artifact_bytes = cast("dict[str, int]", stages[0]["artifact_bytes"])
        del artifact_bytes["structured-log"]

        with pytest.raises(ScaleEvidenceError, match="artifact_bytes"):
            validate_qualification_document("scale-evidence", document)

    def test_nonpassing_stage_schema__still_requires_an_ordered_unique_prefix(self) -> None:
        document = scale_evidence(status="incomplete").model_dump(mode="json")
        stages = cast("list[dict[str, object]]", document["stages"])
        document["stages"] = [stages[1], stages[0]]
        totals = cast("dict[str, int]", document["totals"])
        totals.update(
            scanned=100_000,
            actions=100_000,
            clean_noops=0,
            plan_skips=0,
            applied=0,
            apply_skips=0,
            failures=0,
            not_attempted=0,
            verified=0,
            observed_findings=0,
        )

        with pytest.raises(ScaleEvidenceError, match="stages"):
            validate_qualification_document("scale-evidence", document)

    def test_nonterminal_unvalidated_stage_schema__is_rejected(self) -> None:
        document = scale_evidence(status="incomplete").model_dump(mode="json")
        stages = cast("list[dict[str, object]]", document["stages"])
        stages[0].update(
            run_id=None,
            artifact_validated=False,
            artifact_bytes={"stdout-log": 0, "stderr-log": 0},
        )
        totals = cast("dict[str, int]", document["totals"])
        totals.update(
            scanned=0,
            actions=0,
            clean_noops=0,
            plan_skips=0,
            applied=0,
            apply_skips=0,
            failures=0,
            not_attempted=0,
            verified=0,
            observed_findings=0,
        )

        with pytest.raises(ScaleEvidenceError, match="stages"):
            validate_qualification_document("scale-evidence", document)

    @pytest.mark.parametrize(
        ("stage_count", "unproven_field"),
        [(0, "scanned"), (1, "actions"), (2, "applied"), (3, "verified")],
    )
    def test_unvalidated_phase_schema__requires_zero_totals(
        self, stage_count: int, unproven_field: str
    ) -> None:
        document = scale_evidence(status="incomplete").model_dump(mode="json")
        stages = cast("list[dict[str, object]]", document["stages"])
        document["stages"] = stages[:stage_count]
        totals = cast("dict[str, int]", document["totals"])
        totals.update(
            scanned=100_000 if stage_count >= 1 else 0,
            actions=100_000 if stage_count >= 2 else 0,
            clean_noops=0,
            plan_skips=0,
            applied=100_000 if stage_count >= 3 else 0,
            apply_skips=0,
            failures=0,
            not_attempted=0,
            verified=100_000 if stage_count >= 4 else 0,
            observed_findings=0,
        )
        totals[unproven_field] = 1

        with pytest.raises(ScaleEvidenceError, match=f"totals.*{unproven_field}"):
            validate_qualification_document("scale-evidence", document)

    def test_status_schema__requires_its_finite_reason_category(self) -> None:
        passing = scale_evidence().model_dump(mode="json")
        passing["outcome_reason"] = "harness-error"
        with pytest.raises(ScaleEvidenceError, match="outcome_reason"):
            validate_qualification_document("scale-evidence", passing)

        incomplete = scale_evidence(status="incomplete").model_dump(mode="json")
        incomplete["outcome_reason"] = "threshold-exceeded"
        with pytest.raises(ScaleEvidenceError, match="outcome_reason"):
            validate_qualification_document("scale-evidence", incomplete)

    def test_qualification_schemas__stay_out_of_product_artifact_registry(self) -> None:
        assert {
            "scale-evidence",
            "reference-environment",
            "scale-thresholds",
        }.isdisjoint(ARTIFACT_KINDS)

    def test_scale_evidence_schema__accepts_only_major_version_three(self) -> None:
        document = scale_evidence().model_dump(mode="json")
        validate_qualification_document("scale-evidence", document)
        assert document["schema_version"] == "3.0"

        document["schema_version"] = "2.0"
        with pytest.raises(ScaleEvidenceError, match="schema_version"):
            validate_qualification_document("scale-evidence", document)

    @pytest.mark.parametrize(
        ("mode", "available_inodes", "passed"),
        [
            ("finite-statvfs", 10, True),
            ("dynamic-metadata", None, True),
            ("dynamic-metadata", None, False),
        ],
    )
    def test_capacity_evidence__reconciles_inode_capacity_modes(
        self, mode: str, available_inodes: int | None, passed: bool
    ) -> None:
        required_bytes = 1 if passed else 2
        capacity = FilesystemCapacityEvidence.model_validate(
            {
                "required_bytes": required_bytes,
                "available_bytes": 1,
                "required_inodes": 10,
                "inode_capacity_mode": mode,
                "available_inodes": available_inodes,
                "margin_fraction": 0.25,
                "passed": passed,
            }
        )
        assert capacity.passed is passed

    @pytest.mark.parametrize(
        ("mode", "available_inodes"),
        [("finite-statvfs", None), ("dynamic-metadata", 10)],
    )
    def test_capacity_evidence__rejects_mode_and_availability_mismatch(
        self, mode: str, available_inodes: int | None
    ) -> None:
        with pytest.raises(ValidationError, match="available_inodes"):
            FilesystemCapacityEvidence.model_validate(
                {
                    "required_bytes": 1,
                    "available_bytes": 1,
                    "required_inodes": 10,
                    "inode_capacity_mode": mode,
                    "available_inodes": available_inodes,
                    "margin_fraction": 0.25,
                    "passed": True,
                }
            )

        document = scale_evidence().model_dump(mode="json")
        preflight = cast("dict[str, object]", document["preflight"])
        filesystems = cast("list[dict[str, object]]", preflight["filesystems"])
        filesystems[0]["inode_capacity_mode"] = mode
        filesystems[0]["available_inodes"] = available_inodes
        with pytest.raises(ScaleEvidenceError, match="available_inodes"):
            validate_qualification_document("scale-evidence", document)

    def test_artifact_schema_versions__come_from_code_owner_constants(self) -> None:
        assert evidence_contract.current_artifact_schema_versions() == {
            "inventory": INVENTORY_SCHEMA_VERSION,
            "plan": PLAN_SCHEMA_VERSION,
            "report": REPORT_SCHEMA_VERSION,
            "manifest": MANIFEST_SCHEMA_VERSION,
            "verify-report": VERIFY_REPORT_SCHEMA_VERSION,
            "frontmatter": FRONTMATTER_SCHEMA_VERSION,
        }

        document = scale_evidence().model_dump()
        versions = cast("dict[str, str]", document["artifact_schema_versions"])
        versions["inventory"] = "9.9"
        historical = ScaleEvidence.model_validate(document)

        assert historical.artifact_schema_versions["inventory"] == "9.9"

    def test_reference_mismatch__requires_an_actual_nonbinding_reference_component(self) -> None:
        document = scale_evidence(status="diagnostic").model_dump()
        document["outcome_reason"] = "reference-mismatch"
        document["preflight"] = _preflight(passed=True)

        with pytest.raises(ValidationError, match="actual reference mismatch"):
            ScaleEvidence.model_validate(document)

        nonbinding_preflight = PreflightEvidence(
            filesystems=(_capacity(),),
            capacity_margin_met=True,
            reference_environment_match=False,
            binding_filesystem=False,
            ram_requirement_met=True,
            passed=False,
        )
        document["preflight"] = nonbinding_preflight
        assert ScaleEvidence.model_validate(document).status == "diagnostic"

        raw = scale_evidence(status="diagnostic").model_dump(mode="json")
        raw["outcome_reason"] = "reference-mismatch"
        raw["preflight"] = nonbinding_preflight.model_dump(mode="json")
        validate_qualification_document("scale-evidence", raw)

    def test_diagnostic_schema__reconciles_reason_with_reference_preflight(self) -> None:
        explicit = scale_evidence(status="diagnostic").model_dump(mode="json")
        explicit_preflight = cast("dict[str, object]", explicit["preflight"])
        explicit_preflight.update(
            reference_environment_match=False,
            binding_filesystem=False,
            passed=False,
        )
        with pytest.raises(ScaleEvidenceError, match="preflight"):
            validate_qualification_document("scale-evidence", explicit)

        mismatch = scale_evidence(status="diagnostic").model_dump(mode="json")
        mismatch["outcome_reason"] = "reference-mismatch"
        with pytest.raises(ScaleEvidenceError, match="preflight"):
            validate_qualification_document("scale-evidence", mismatch)

    def test_preflight_schema__aggregate_matches_component_booleans(self) -> None:
        document = scale_evidence(status="incomplete").model_dump(mode="json")
        preflight = cast("dict[str, object]", document["preflight"])
        preflight["passed"] = False

        with pytest.raises(ScaleEvidenceError, match="preflight"):
            validate_qualification_document("scale-evidence", document)

    @pytest.mark.parametrize(
        ("reasons", "expected_status", "expected_reason"),
        [
            (("runtime-limit-exceeded", "threshold-exceeded"), "failed", "threshold-exceeded"),
            (("reference-mismatch", "threshold-exceeded"), "failed", "threshold-exceeded"),
            (("artifact-invalid", "stage-exit"), "failed", "stage-exit"),
            (("install-failed", "build-failed"), "incomplete", "install-failed"),
            (
                ("explicit-diagnostic", "reference-mismatch"),
                "diagnostic",
                "reference-mismatch",
            ),
            ((), "passing", None),
        ],
    )
    def test_outcome_selection__uses_failure_then_execution_order_precedence(
        self,
        reasons: tuple[OutcomeReason, ...],
        expected_status: str,
        expected_reason: str | None,
    ) -> None:
        outcome = evidence_contract.select_evidence_outcome(reasons)

        assert outcome.status == expected_status
        assert outcome.reason == expected_reason

    def test_trustworthy_stage_exit__cannot_be_downgraded_to_incomplete(self) -> None:
        document = scale_evidence(status="incomplete").model_dump()
        document["outcome_reason"] = "artifact-invalid"
        stages = cast("list[dict[str, object]]", document["stages"])
        stages[2]["exit_code"] = 1

        with pytest.raises(ValidationError, match="trustworthy failure"):
            ScaleEvidence.model_validate(document)

        raw = scale_evidence(status="incomplete").model_dump(mode="json")
        raw["outcome_reason"] = "artifact-invalid"
        raw_stages = cast("list[dict[str, object]]", raw["stages"])
        raw_stages[2]["exit_code"] = 1
        with pytest.raises(ScaleEvidenceError, match=r"status|outcome_reason"):
            validate_qualification_document("scale-evidence", raw)

    def test_schema__cannot_downgrade_threshold_or_runtime_failures(self) -> None:
        limits = ThresholdSet(
            absolute_peak_rss_bytes=100,
            slope_bytes_per_file=10,
            linearity_tolerance=0.2,
        )
        failed_threshold = ThresholdVerdict(
            limits=limits,
            observed_peak_rss_bytes=101,
            observed_slope_bytes_per_file=10,
            observed_linearity_ratio=0.2,
            peak_passed=False,
            slope_passed=True,
            linearity_passed=True,
            passed=False,
        )
        threshold_document = scale_evidence(status="incomplete").model_dump(mode="json")
        threshold_document["thresholds"] = failed_threshold.model_dump(mode="json")
        with pytest.raises(ScaleEvidenceError, match=r"status|outcome_reason"):
            validate_qualification_document("scale-evidence", threshold_document)

        runtime_document = scale_evidence(status="diagnostic").model_dump(mode="json")
        runtime_document.update(
            tier="release",
            threshold_baseline_sha256=SHA_ZERO,
            thresholds=ThresholdVerdict(
                limits=limits,
                observed_peak_rss_bytes=100,
                observed_slope_bytes_per_file=10,
                observed_linearity_ratio=0.2,
                peak_passed=True,
                slope_passed=True,
                linearity_passed=True,
                passed=True,
            ).model_dump(mode="json"),
            workflow_runtime=evidence_contract.WorkflowRuntimeVerdict(
                elapsed_seconds=43_201,
                limit_seconds=43_200,
                passed=False,
            ).model_dump(mode="json"),
        )
        with pytest.raises(ScaleEvidenceError, match=r"status|outcome_reason|workflow_runtime"):
            validate_qualification_document("scale-evidence", runtime_document)

    @pytest.mark.parametrize(
        "reason",
        ["stage-exit", "threshold-exceeded", "runtime-limit-exceeded"],
    )
    def test_schema__failed_reason_requires_its_observation(self, reason: str) -> None:
        document = scale_evidence().model_dump(mode="json")
        document.update(status="failed", outcome_reason=reason)
        if reason == "runtime-limit-exceeded":
            document.update(
                tier="release",
                workflow_runtime=evidence_contract.WorkflowRuntimeVerdict(
                    elapsed_seconds=5,
                    limit_seconds=43_200,
                    passed=True,
                ).model_dump(mode="json"),
            )

        with pytest.raises(ScaleEvidenceError, match=r"stages|thresholds|workflow_runtime"):
            validate_qualification_document("scale-evidence", document)

    @pytest.mark.parametrize(
        ("components", "passed"),
        [
            ((True, True, True), False),
            ((False, True, True), True),
        ],
    )
    def test_threshold_schema__aggregate_matches_component_booleans(
        self, components: tuple[bool, bool, bool], passed: bool
    ) -> None:
        document = scale_evidence().model_dump(mode="json")
        document.update(status="failed", outcome_reason="threshold-exceeded")
        document["thresholds"] = {
            "limits": {
                "absolute_peak_rss_bytes": 100,
                "slope_bytes_per_file": 10,
                "linearity_tolerance": 0.2,
            },
            "observed_peak_rss_bytes": 101,
            "observed_slope_bytes_per_file": 10,
            "observed_linearity_ratio": 0.2,
            "peak_passed": components[0],
            "slope_passed": components[1],
            "linearity_passed": components[2],
            "passed": passed,
        }

        with pytest.raises(ScaleEvidenceError, match="thresholds"):
            validate_qualification_document("scale-evidence", document)

    def test_release_runtime__is_required_after_dispatch_in_model_and_schema(self) -> None:
        totals = {
            "scanned": 0,
            "actions": 0,
            "clean_noops": 0,
            "plan_skips": 0,
            "applied": 0,
            "apply_skips": 0,
            "failures": 0,
            "not_attempted": 0,
            "verified": 0,
            "expected_findings": 25,
            "observed_findings": 0,
        }
        document = scale_evidence(status="incomplete").model_dump()
        document.update(
            tier="release",
            outcome_reason="supervisor-failed",
            stages=[_stage("scan", completed=False)],
            totals=QualificationTotals.model_validate(totals),
            workflow_runtime=None,
        )

        with pytest.raises(ValidationError, match="workflow runtime after scan dispatch"):
            ScaleEvidence.model_validate(document)

        schema_document = scale_evidence(status="incomplete").model_dump(mode="json")
        schema_document.update(
            tier="release",
            outcome_reason="supervisor-failed",
            stages=[_stage("scan", completed=False).model_dump(mode="json")],
            totals=totals,
            workflow_runtime=None,
        )
        with pytest.raises(ScaleEvidenceError, match="workflow_runtime"):
            validate_qualification_document("scale-evidence", schema_document)

    def test_release_runtime__must_be_null_before_scan_dispatch_in_model_and_schema(self) -> None:
        totals = QualificationTotals(
            scanned=0,
            actions=0,
            clean_noops=0,
            plan_skips=0,
            applied=0,
            apply_skips=0,
            failures=0,
            not_attempted=0,
            verified=0,
            expected_findings=25,
            observed_findings=0,
        )
        runtime = evidence_contract.WorkflowRuntimeVerdict(
            elapsed_seconds=0,
            limit_seconds=43_200,
            passed=True,
        )
        document = scale_evidence(status="incomplete").model_dump()
        document.update(
            tier="release",
            outcome_reason="build-failed",
            stages=[],
            totals=totals,
            workflow_runtime=runtime,
        )
        with pytest.raises(ValidationError, match="null before scan dispatch"):
            ScaleEvidence.model_validate(document)

        raw = scale_evidence(status="incomplete").model_dump(mode="json")
        raw.update(
            tier="release",
            outcome_reason="build-failed",
            stages=[],
            totals=totals.model_dump(mode="json"),
            workflow_runtime=runtime.model_dump(mode="json"),
        )
        with pytest.raises(ScaleEvidenceError, match="workflow_runtime"):
            validate_qualification_document("scale-evidence", raw)

    def test_release_runtime__uses_exact_twelve_hour_boundary(self) -> None:
        boundary = evidence_contract.WorkflowRuntimeVerdict(
            elapsed_seconds=43_200.0, limit_seconds=43_200, passed=True
        )
        assert boundary.passed is True

        with pytest.raises(ValidationError, match="runtime verdict"):
            evidence_contract.WorkflowRuntimeVerdict(
                elapsed_seconds=43_200.000_001,
                limit_seconds=43_200,
                passed=True,
            )

    def test_complete_release_runtime__cannot_understate_public_stage_elapsed(self) -> None:
        threshold = ThresholdVerdict(
            limits=ThresholdSet(
                absolute_peak_rss_bytes=100_000_000,
                slope_bytes_per_file=10_000,
                linearity_tolerance=0.2,
            ),
            observed_peak_rss_bytes=90_000_000,
            observed_slope_bytes_per_file=9_000,
            observed_linearity_ratio=0.1,
            peak_passed=True,
            slope_passed=True,
            linearity_passed=True,
            passed=True,
        )
        document = scale_evidence().model_dump()
        document.update(
            tier="release",
            threshold_baseline_sha256=SHA_ZERO,
            thresholds=threshold,
            workflow_runtime=evidence_contract.WorkflowRuntimeVerdict(
                elapsed_seconds=4.999, limit_seconds=43_200, passed=True
            ),
        )

        with pytest.raises(ValidationError, match="understate stage elapsed"):
            ScaleEvidence.model_validate(document)

        document["workflow_runtime"] = evidence_contract.WorkflowRuntimeVerdict(
            elapsed_seconds=5.0, limit_seconds=43_200, passed=True
        )
        assert ScaleEvidence.model_validate(document).workflow_runtime is not None

    def test_partial_prefix__keeps_unvalidated_phase_totals_zero(self) -> None:
        document = scale_evidence(status="incomplete").model_dump()
        document.update(
            outcome_reason="supervisor-failed",
            stages=[_stage("scan"), _stage("plan")],
            totals=QualificationTotals(
                scanned=100_000,
                actions=100_000,
                clean_noops=0,
                plan_skips=0,
                applied=0,
                apply_skips=0,
                failures=0,
                not_attempted=0,
                verified=0,
                expected_findings=25,
                observed_findings=0,
            ),
        )

        evidence = ScaleEvidence.model_validate(document)

        assert tuple(stage.stage for stage in evidence.stages) == ("scan", "plan")
        assert evidence.totals.applied == 0
        assert evidence.totals.verified == 0

    def test_failed_conservation__preserves_discrepant_validated_observation(self) -> None:
        document = scale_evidence().model_dump()
        document["status"] = "failed"
        document["outcome_reason"] = "conservation-mismatch"
        totals = cast("dict[str, object]", document["totals"])
        totals["scanned"] = 99_999

        evidence = ScaleEvidence.model_validate(document)

        assert evidence.status == "failed"
        assert evidence.totals.scanned == 99_999

    def test_failed_conservation__accepts_exact_reducer_verdict_with_validated_stage(
        self,
    ) -> None:
        document = scale_evidence().model_dump()
        document.update(status="failed", outcome_reason="conservation-mismatch")

        evidence = ScaleEvidence.model_validate(document)

        assert evidence.status == "failed"
        assert evidence.outcome_reason == "conservation-mismatch"

    def test_failed_finding__accepts_exact_reducer_verdict_with_validated_verify(
        self,
    ) -> None:
        document = scale_evidence().model_dump()
        document.update(status="failed", outcome_reason="finding-mismatch")

        evidence = ScaleEvidence.model_validate(document)

        assert evidence.status == "failed"
        assert evidence.outcome_reason == "finding-mismatch"

    @pytest.mark.parametrize(
        ("reason", "stage_count"),
        [("conservation-mismatch", 0), ("finding-mismatch", 3)],
    )
    def test_exact_reducer_failure__requires_supporting_validated_stage(
        self, reason: str, stage_count: int
    ) -> None:
        document = scale_evidence(status="incomplete").model_dump()
        document.update(status="failed", outcome_reason=reason)
        stages = cast("list[dict[str, object]]", document["stages"])
        document["stages"] = stages[:stage_count]
        totals = cast("dict[str, object]", document["totals"])
        if stage_count == 0:
            totals.update(
                scanned=0,
                actions=0,
                clean_noops=0,
                plan_skips=0,
                applied=0,
                apply_skips=0,
                failures=0,
                not_attempted=0,
                verified=0,
                observed_findings=0,
            )
        else:
            totals.update(verified=0, observed_findings=0)

        with pytest.raises(ValidationError, match="trustworthy observed failure"):
            ScaleEvidence.model_validate(document)

    def test_binding_evidence__forbids_private_fields(self) -> None:
        forbidden = {
            "hostname",
            "username",
            "argv",
            "stdout",
            "stderr",
            "workspace",
            "corpus_path",
            "device",
            "serial",
            "content",
        }
        assert forbidden.isdisjoint(ScaleEvidence.model_fields)

        document = scale_evidence().model_dump(mode="json")
        document["workspace"] = "/private/workspace"
        with pytest.raises(ScaleEvidenceError, match="workspace"):
            validate_qualification_document("scale-evidence", document)

        stages = cast("list[dict[str, object]]", document["stages"])
        del document["workspace"]
        stages[0]["argv"] = ["docmend", "scan", "/private/corpus"]
        with pytest.raises(ScaleEvidenceError, match="argv"):
            validate_qualification_document("scale-evidence", document)

    @pytest.mark.parametrize(
        "mount_flags",
        [("rw", "subvol=/private"), ("rw", "unknown-flag")],
    )
    def test_reference_environment__rejects_value_bearing_or_unknown_mount_flags(
        self, mount_flags: tuple[str, ...]
    ) -> None:
        with pytest.raises(ValidationError, match="mount_flags"):
            reference_environment(mount_flags=mount_flags)

        document = reference_environment().model_dump(mode="json")
        document["mount_flags"] = list(mount_flags)
        with pytest.raises(ScaleEvidenceError, match="mount_flags"):
            validate_qualification_document("reference-environment", document)

    def test_reference_environment__rejects_identity_and_device_fields(self) -> None:
        document = reference_environment().model_dump(mode="json")
        forbidden = {
            "hostname",
            "username",
            "device",
            "device_id",
            "serial",
            "serial_number",
            "mount_path",
        }
        assert forbidden.isdisjoint(ReferenceEnvironment.model_fields)
        for field in forbidden:
            candidate = dict(document)
            candidate[field] = "synthetic-private-value"
            with pytest.raises(ScaleEvidenceError, match=field):
                validate_qualification_document("reference-environment", candidate)

    def test_reference_environment__accepts_complete_mount_flag_allowlist(self) -> None:
        environment = reference_environment(
            mount_flags=(
                "ro",
                "rw",
                "relatime",
                "noatime",
                "nodiratime",
                "lazytime",
                "sync",
                "dirsync",
            )
        )
        assert len(environment.mount_flags) == 8

    def test_public_models__are_strict_frozen_and_forbid_extras(self) -> None:
        stage = _stage("scan")
        with pytest.raises(ValidationError, match="frozen"):
            stage.completed = False

        document = stage.model_dump()
        document["elapsed_seconds"] = "1.25"
        with pytest.raises(ValidationError, match="elapsed_seconds"):
            StageEvidence.model_validate(document)

        document = stage.model_dump()
        document["hostname"] = "synthetic-host"
        with pytest.raises(ValidationError, match="hostname"):
            StageEvidence.model_validate(document)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("exit_code", 0),
            ("peak_rss_bytes", 1),
            ("python_allocation_peak_bytes", 1),
            ("vm_swap_peak_bytes", 1),
        ],
    )
    def test_incomplete_stage__requires_all_measurement_fields_null(
        self, field: str, value: int
    ) -> None:
        document = _stage("scan", completed=False).model_dump()
        document[field] = value

        with pytest.raises(ValidationError, match="incomplete stage requires null"):
            StageEvidence.model_validate(document)

    def test_incomplete_stage_schema__requires_swap_telemetry_null(self) -> None:
        document = scale_evidence(status="incomplete").model_dump(mode="json")
        stage = _stage("scan", completed=False).model_dump(mode="json")
        stage["vm_swap_peak_bytes"] = 1
        document["stages"] = [stage]
        document["totals"] = QualificationTotals(
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
        ).model_dump(mode="json")

        with pytest.raises(ScaleEvidenceError, match="vm_swap_peak_bytes"):
            validate_qualification_document("scale-evidence", document)

    def test_completed_stage__requires_run_id_in_model_and_schema(self) -> None:
        document = _stage("scan").model_dump(mode="json")
        document["run_id"] = None
        with pytest.raises(ValidationError, match="run_id"):
            StageEvidence.model_validate(document)
        with pytest.raises(ScaleEvidenceError, match="run_id"):
            validate_qualification_document(
                "scale-evidence",
                {
                    **scale_evidence().model_dump(mode="json"),
                    "stages": [document],
                },
            )

        incomplete = _stage("scan", completed=False)
        assert incomplete.run_id is None

    def test_scale_evidence__requires_aware_ordered_timestamps(self) -> None:
        document = scale_evidence().model_dump()
        document["started_at"] = datetime(2026, 7, 13)
        with pytest.raises(ValidationError, match="timezone"):
            ScaleEvidence.model_validate(document)

        document = scale_evidence().model_dump()
        document["completed_at"] = datetime(2026, 7, 12, tzinfo=UTC)
        with pytest.raises(ValidationError, match="completed_at"):
            ScaleEvidence.model_validate(document)

    def test_preflight__reconciles_the_binding_capacity_margin(self) -> None:
        preflight = PreflightEvidence(
            filesystems=(_capacity(),),
            capacity_margin_met=True,
            reference_environment_match=True,
            binding_filesystem=True,
            ram_requirement_met=True,
            passed=True,
        )
        assert preflight.capacity_margin_met is True

        document = preflight.model_dump()
        document["capacity_margin_met"] = False
        with pytest.raises(ValidationError, match="capacity margin"):
            PreflightEvidence.model_validate(document)

        document = preflight.model_dump()
        filesystems = cast("list[dict[str, object]]", document["filesystems"])
        filesystems[0]["margin_fraction"] = 0.0
        with pytest.raises(ValidationError, match="capacity margin"):
            PreflightEvidence.model_validate(document)

        raw = scale_evidence().model_dump(mode="json")
        raw_preflight = cast("dict[str, object]", raw["preflight"])
        raw_filesystems = cast("list[dict[str, object]]", raw_preflight["filesystems"])
        raw_filesystems[0]["margin_fraction"] = 0.0
        with pytest.raises(ScaleEvidenceError, match="margin_fraction"):
            validate_qualification_document("scale-evidence", raw)

    @pytest.mark.parametrize(
        ("margin_fraction", "capacity_margin_met"),
        [(0.25, False), (0.0, True)],
    )
    def test_preflight_schema__reconciles_margin_verdict_when_not_passing(
        self, margin_fraction: float, capacity_margin_met: bool
    ) -> None:
        raw = scale_evidence(status="incomplete").model_dump(mode="json")
        preflight = cast("dict[str, object]", raw["preflight"])
        filesystems = cast("list[dict[str, object]]", preflight["filesystems"])
        filesystems[0]["margin_fraction"] = margin_fraction
        preflight["capacity_margin_met"] = capacity_margin_met
        preflight["passed"] = False
        with pytest.raises(ScaleEvidenceError):
            validate_qualification_document("scale-evidence", raw)

    def test_passing_installed_evidence__requires_exact_wheel_and_completed_pipeline(self) -> None:
        document = scale_evidence().model_dump()
        document["wheel_sha256"] = None
        with pytest.raises(ValidationError, match="wheel_sha256"):
            ScaleEvidence.model_validate(document)

        document = scale_evidence().model_dump()
        document["stages"] = document["stages"][:-1]
        totals = cast("dict[str, object]", document["totals"])
        totals["verified"] = 0
        totals["observed_findings"] = 0
        with pytest.raises(ValidationError, match="scan, plan, apply, verify"):
            ScaleEvidence.model_validate(document)

    def test_passing_evidence__requires_reconciled_preflight_and_totals(self) -> None:
        document = scale_evidence().model_dump()
        document["preflight"] = _preflight(passed=False)
        with pytest.raises(ValidationError, match="passing preflight"):
            ScaleEvidence.model_validate(document)

        document = scale_evidence().model_dump()
        totals = cast("dict[str, object]", document["totals"])
        totals["clean_noops"] = 1
        with pytest.raises(ValidationError, match="trustworthy failure"):
            ScaleEvidence.model_validate(document)

        document = scale_evidence().model_dump()
        totals = cast("dict[str, object]", document["totals"])
        totals["failures"] = 1
        totals["applied"] = cast("int", totals["applied"]) - 1
        with pytest.raises(ValidationError, match="trustworthy failure"):
            ScaleEvidence.model_validate(document)

    def test_passing_evidence__reconciles_stage_exit_codes(self) -> None:
        document = scale_evidence().model_dump()
        stages = cast("list[dict[str, object]]", document["stages"])
        stages[0]["exit_code"] = 1
        with pytest.raises(ValidationError, match="trustworthy failure"):
            ScaleEvidence.model_validate(document)

        document = scale_evidence().model_dump()
        stages = cast("list[dict[str, object]]", document["stages"])
        stages[-1]["exit_code"] = 1
        with pytest.raises(ValidationError, match="trustworthy failure"):
            ScaleEvidence.model_validate(document)

    def test_passing_evidence__requires_zero_child_swap(self) -> None:
        document = scale_evidence().model_dump()
        stages = cast("list[dict[str, object]]", document["stages"])
        stages[1]["vm_swap_peak_bytes"] = 1_024
        with pytest.raises(ValidationError, match="zero child swap"):
            ScaleEvidence.model_validate(document)

        raw = scale_evidence().model_dump(mode="json")
        raw_stages = cast("list[dict[str, object]]", raw["stages"])
        raw_stages[1]["vm_swap_peak_bytes"] = 1_024
        with pytest.raises(ScaleEvidenceError, match="vm_swap_peak_bytes"):
            validate_qualification_document("scale-evidence", raw)

    def test_unavailable_child_swap_is_explicit_and_never_passing(self) -> None:
        stage_document = _stage("scan").model_dump()
        stage_document["vm_swap_peak_bytes"] = None
        stage = StageEvidence.model_validate(stage_document)
        assert stage.completed is True
        assert stage.vm_swap_peak_bytes is None

        incomplete = scale_evidence(status="incomplete").model_dump()
        incomplete_stages = cast("list[dict[str, object]]", incomplete["stages"])
        incomplete_stages[0]["vm_swap_peak_bytes"] = None
        assert ScaleEvidence.model_validate(incomplete).status == "incomplete"

        incomplete_json = scale_evidence(status="incomplete").model_dump(mode="json")
        incomplete_json_stages = cast("list[dict[str, object]]", incomplete_json["stages"])
        incomplete_json_stages[0]["vm_swap_peak_bytes"] = None
        validate_qualification_document("scale-evidence", incomplete_json)
        assert incomplete_json["schema_version"] == "3.0"

        stale_model_version = dict(incomplete)
        stale_model_version["schema_version"] = "2.0"
        with pytest.raises(ValidationError, match="schema_version"):
            ScaleEvidence.model_validate(stale_model_version)

        stale_version = dict(incomplete_json)
        stale_version["schema_version"] = "2.0"
        with pytest.raises(ScaleEvidenceError, match="schema_version"):
            validate_qualification_document("scale-evidence", stale_version)

        passing = scale_evidence().model_dump()
        passing_stages = cast("list[dict[str, object]]", passing["stages"])
        passing_stages[0]["vm_swap_peak_bytes"] = None
        with pytest.raises(ValidationError, match="available child swap"):
            ScaleEvidence.model_validate(passing)

        raw = scale_evidence().model_dump(mode="json")
        raw_stages = cast("list[dict[str, object]]", raw["stages"])
        raw_stages[0]["vm_swap_peak_bytes"] = None
        with pytest.raises(ScaleEvidenceError, match="vm_swap_peak_bytes"):
            validate_qualification_document("scale-evidence", raw)

    def test_public_maps__accept_only_finite_artifact_names(self) -> None:
        stage = _stage("scan").model_dump()
        stage["artifact_bytes"] = {"/private/output": 1}
        with pytest.raises(ValidationError, match="artifact_bytes"):
            StageEvidence.model_validate(stage)

        document = scale_evidence().model_dump()
        versions = cast("dict[str, str]", document["artifact_schema_versions"])
        versions["private-artifact"] = "1.0"
        with pytest.raises(ValidationError, match="artifact_schema_versions"):
            ScaleEvidence.model_validate(document)

        raw = scale_evidence().model_dump(mode="json")
        raw_stages = cast("list[dict[str, object]]", raw["stages"])
        raw_stages[0]["artifact_bytes"] = {"/private/output": 1}
        with pytest.raises(ScaleEvidenceError, match="artifact_bytes"):
            validate_qualification_document("scale-evidence", raw)

    def test_memory_measurement__separates_binding_rss_from_allocation_diagnostics(
        self,
    ) -> None:
        document = scale_evidence(status="diagnostic").model_dump()
        document["memory_measurement"] = "python-allocation"
        stages = cast("list[dict[str, object]]", document["stages"])
        for stage in stages:
            stage["peak_rss_bytes"] = None
            stage["python_allocation_peak_bytes"] = 32 * 1024**2
        diagnostic = ScaleEvidence.model_validate(document)
        assert diagnostic.memory_measurement == "python-allocation"
        assert all(stage.peak_rss_bytes is None for stage in diagnostic.stages)

        mixed = diagnostic.model_dump()
        mixed_stages = cast("list[dict[str, object]]", mixed["stages"])
        mixed_stages[0]["peak_rss_bytes"] = 1
        with pytest.raises(ValidationError, match="memory measurement"):
            ScaleEvidence.model_validate(mixed)

        passing = scale_evidence().model_dump()
        passing["memory_measurement"] = "python-allocation"
        passing_stages = cast("list[dict[str, object]]", passing["stages"])
        for stage in passing_stages:
            stage["peak_rss_bytes"] = None
            stage["python_allocation_peak_bytes"] = 32 * 1024**2
        with pytest.raises(ValidationError, match="diagnostic-only"):
            ScaleEvidence.model_validate(passing)

    def test_public_labels__reject_path_value_and_control_character_leaks(self) -> None:
        for value in ("/private/cpu", r"private\cpu", "cpu\nprivate", "cpu=user"):
            with pytest.raises(ValidationError, match="cpu_model"):
                reference_environment(cpu_model=value)

    def test_passing_scheduled_evidence__requires_threshold_baseline_digest_field(self) -> None:
        verdict = ThresholdVerdict(
            limits=ThresholdSet(
                absolute_peak_rss_bytes=100_000_000,
                slope_bytes_per_file=10_000,
                linearity_tolerance=0.2,
            ),
            observed_peak_rss_bytes=90_000_000,
            observed_slope_bytes_per_file=9_000,
            observed_linearity_ratio=0.1,
            peak_passed=True,
            slope_passed=True,
            linearity_passed=True,
            passed=True,
        )
        document = scale_evidence().model_dump()
        document["tier"] = "scheduled"
        document["thresholds"] = verdict
        document["threshold_baseline_sha256"] = SHA_ZERO
        evidence = ScaleEvidence.model_validate(document)
        assert evidence.threshold_baseline_sha256 == SHA_ZERO

        document["threshold_baseline_sha256"] = None
        with pytest.raises(ValidationError, match="threshold baseline provenance"):
            ScaleEvidence.model_validate(document)

    def test_passing_evidence_schema__reconciles_verify_exit_with_expected_findings(self) -> None:
        document = scale_evidence().model_dump(mode="json")
        stages = cast("list[dict[str, object]]", document["stages"])
        stages[-1]["exit_code"] = 1
        with pytest.raises(ScaleEvidenceError, match="stages"):
            validate_qualification_document("scale-evidence", document)

        totals = cast("dict[str, object]", document["totals"])
        totals["expected_findings"] = 1
        totals["observed_findings"] = 1
        stages[-1]["exit_code"] = 0
        with pytest.raises(ScaleEvidenceError, match="stages"):
            validate_qualification_document("scale-evidence", document)

    @pytest.mark.parametrize(
        ("status", "tier"),
        [("passing", "pr"), ("diagnostic", "pilot")],
    )
    def test_complete_status_schema__requires_four_validated_stages(
        self, status: str, tier: str
    ) -> None:
        document = scale_evidence(status=status, tier=tier).model_dump(mode="json")
        stages = cast("list[dict[str, object]]", document["stages"])
        document["stages"] = stages[:-1]

        with pytest.raises(ScaleEvidenceError, match="stages"):
            validate_qualification_document("scale-evidence", document)


class TestEvidenceIO:
    def test_accepted_evidence__never_overwrites(self, tmp_path: Path) -> None:
        evidence = scale_evidence()
        path = tmp_path / "accepted.json"
        write_scale_evidence(evidence, path, accepted=True)
        original = path.read_bytes()

        with pytest.raises(FileExistsError):
            write_scale_evidence(evidence, path, accepted=True)

        assert path.read_bytes() == original
        assert read_scale_evidence(path) == evidence
        snapshot, digest = read_scale_evidence_snapshot(path)
        assert snapshot == evidence
        assert digest == sha256_of_file(path)

    def test_accepted_evidence__must_be_passing(self, tmp_path: Path) -> None:
        evidence = scale_evidence(status="diagnostic")
        with pytest.raises(ScaleEvidenceError, match="passing"):
            write_scale_evidence(evidence, tmp_path / "diagnostic.json", accepted=True)

    def test_writer__revalidates_mutable_version_map_before_publication(
        self, tmp_path: Path
    ) -> None:
        evidence = scale_evidence()
        evidence.artifact_schema_versions["inventory"] = "9.9"
        destination = tmp_path / "mutated.json"

        with pytest.raises(ScaleEvidenceError, match="current code-owner versions"):
            write_scale_evidence(evidence, destination, accepted=True)

        assert not destination.exists()

    def test_threshold_snapshot__rejects_fifo_without_blocking(self, tmp_path: Path) -> None:
        fifo = tmp_path / "point.json"
        os.mkfifo(fifo, 0o600)
        script = """
from pathlib import Path
import sys
from docmend.scale_evidence import ScaleEvidenceError, _read_payload_beneath

try:
    _read_payload_beneath(Path(sys.argv[1]), sys.argv[2], description="threshold evidence point")
except ScaleEvidenceError:
    raise SystemExit(0)
raise SystemExit(1)
"""

        completed = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path), fifo.name],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )

        assert completed.returncode == 0, completed.stderr

    def test_accepted_scheduled_evidence__requires_matching_validated_baseline(
        self, tmp_path: Path
    ) -> None:
        baseline_path = _write_baseline_fixture(tmp_path / "baseline")
        baseline, digest = load_threshold_baseline_snapshot(
            baseline_path, reference_environment_sha256=REFERENCE_SHA
        )
        verdict = ThresholdVerdict(
            limits=baseline.limits,
            observed_peak_rss_bytes=baseline.limits.absolute_peak_rss_bytes,
            observed_slope_bytes_per_file=baseline.limits.slope_bytes_per_file,
            observed_linearity_ratio=baseline.limits.linearity_tolerance,
            peak_passed=True,
            slope_passed=True,
            linearity_passed=True,
            passed=True,
        )
        document = scale_evidence().model_dump()
        document["tier"] = "scheduled"
        document["thresholds"] = verdict
        document["threshold_baseline_sha256"] = digest
        evidence = ScaleEvidence.model_validate(document)
        accepted_path = tmp_path / "accepted-scheduled.json"

        with pytest.raises(ScaleEvidenceError, match="validated threshold baseline"):
            write_scale_evidence(evidence, accepted_path, accepted=True)

        write_scale_evidence(
            evidence,
            accepted_path,
            accepted=True,
            threshold_baseline_path=baseline_path,
        )
        assert read_scale_evidence(accepted_path) == evidence

        wrong_digest = evidence.model_copy(update={"threshold_baseline_sha256": SHA_ZERO})
        with pytest.raises(ScaleEvidenceError, match="digest does not match"):
            write_scale_evidence(
                wrong_digest,
                tmp_path / "wrong-digest.json",
                accepted=True,
                threshold_baseline_path=baseline_path,
            )

        unrelated_limits = ThresholdSet(
            absolute_peak_rss_bytes=baseline.limits.absolute_peak_rss_bytes + 1,
            slope_bytes_per_file=baseline.limits.slope_bytes_per_file,
            linearity_tolerance=baseline.limits.linearity_tolerance,
        )
        unrelated_verdict = verdict.model_copy(
            update={
                "limits": unrelated_limits,
                "observed_peak_rss_bytes": unrelated_limits.absolute_peak_rss_bytes,
            }
        )
        unrelated_evidence = evidence.model_copy(update={"thresholds": unrelated_verdict})
        with pytest.raises(ScaleEvidenceError, match="limits do not match"):
            write_scale_evidence(
                unrelated_evidence,
                tmp_path / "wrong-limits.json",
                accepted=True,
                threshold_baseline_path=baseline_path,
            )

        point = baseline_path.parent / "supporting" / "point-10000.json"
        point.write_text(point.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with pytest.raises(ScaleEvidenceError, match="hash mismatch"):
            write_scale_evidence(
                evidence,
                tmp_path / "mutated-point.json",
                accepted=True,
                threshold_baseline_path=baseline_path,
            )

    def test_reference_environment__round_trips_and_never_clobbers(self, tmp_path: Path) -> None:
        environment = reference_environment()
        path = tmp_path / "reference.json"
        write_reference_environment(environment, path)
        with pytest.raises(FileExistsError):
            write_reference_environment(environment, path)
        assert read_reference_environment(path) == environment

    def test_reference_environment_snapshot__returns_model_and_digest_from_safe_bytes(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "reference.json"
        write_reference_environment(reference_environment(), path)
        expected_digest = sha256_of_file(path)

        loaded, digest = evidence_contract.read_reference_environment_snapshot(path)

        assert loaded == reference_environment()
        assert digest == expected_digest

        moved = tmp_path / "moved.json"
        path.rename(moved)
        path.symlink_to(moved.name)
        with pytest.raises(ScaleEvidenceError, match="cannot read reference environment"):
            evidence_contract.read_reference_environment_snapshot(path)


class TestThresholdMath:
    def test_stage_memory_series__requires_integer_rss_values(self) -> None:
        with pytest.raises(ValueError, match="positive integers"):
            evidence_contract.StageMemorySeries(
                "scan", cast("int", 1.5), cast("int", Fraction(2, 1))
            )

    @pytest.mark.parametrize("file_count", [True, 999])
    def test_threshold_evaluator__rejects_non_tier_file_counts(self, file_count: object) -> None:
        stage_memory = tuple(
            evidence_contract.StageMemorySeries(stage, 100_000_000, 100_000_000)
            for stage in STAGE_NAMES
        )
        limits = derive_thresholds(stage_memory)
        context = evidence_contract.ThresholdContext(
            baseline=ThresholdBaseline(
                reference_environment_sha256=REFERENCE_SHA,
                measurement_points=(
                    ThresholdPointIdentity(
                        file_count=10_000,
                        evidence="supporting/point-10000.json",
                        evidence_sha256=SHA_ZERO,
                    ),
                    ThresholdPointIdentity(
                        file_count=100_000,
                        evidence="accepted/point-100000.json",
                        evidence_sha256=SHA_ONE,
                    ),
                ),
                target_file_count=1_000_000,
                fitting_method="exact-per-stage-linear-projection",
                limits=limits,
            ),
            baseline_sha256=SHA_ZERO,
            stage_memory=stage_memory,
        )

        with pytest.raises(ValueError, match="file_count"):
            evidence_contract.evaluate_thresholds(
                context,
                file_count=cast("Literal[100_000, 1_000_000]", file_count),
                stage_peak_rss=dict.fromkeys(STAGE_NAMES, 100_000_000),
            )

    def test_threshold_evaluator__requires_integer_stage_peaks(self) -> None:
        stage_memory = tuple(
            evidence_contract.StageMemorySeries(stage, 100_000_000, 100_000_000)
            for stage in STAGE_NAMES
        )
        limits = derive_thresholds(stage_memory)
        context = evidence_contract.ThresholdContext(
            baseline=ThresholdBaseline(
                reference_environment_sha256=REFERENCE_SHA,
                measurement_points=(
                    ThresholdPointIdentity(
                        file_count=10_000,
                        evidence="supporting/point-10000.json",
                        evidence_sha256=SHA_ZERO,
                    ),
                    ThresholdPointIdentity(
                        file_count=100_000,
                        evidence="accepted/point-100000.json",
                        evidence_sha256=SHA_ONE,
                    ),
                ),
                target_file_count=1_000_000,
                fitting_method="exact-per-stage-linear-projection",
                limits=limits,
            ),
            baseline_sha256=SHA_ZERO,
            stage_memory=stage_memory,
        )
        stage_peaks = cast(
            "dict[StageName, int]",
            {**dict.fromkeys(STAGE_NAMES, 100_000_000), "scan": 100_000_000.5},
        )

        with pytest.raises(ValueError, match="positive integers"):
            evidence_contract.evaluate_thresholds(
                context,
                file_count=100_000,
                stage_peak_rss=stage_peaks,
            )

    def test_threshold_absolute_limit__projects_each_stage_to_one_million(self) -> None:
        series = (
            evidence_contract.StageMemorySeries("scan", 100_000_000, 550_000_000),
            evidence_contract.StageMemorySeries("plan", 300_000_000, 350_000_000),
            evidence_contract.StageMemorySeries("apply", 200_000_000, 300_000_000),
            evidence_contract.StageMemorySeries("verify", 150_000_000, 250_000_000),
        )

        limits = derive_thresholds(series)

        assert limits.absolute_peak_rss_bytes == 6_312_500_000
        assert limits.slope_bytes_per_file == 6_250
        assert limits.linearity_tolerance == 0.2

    def test_scheduled_thresholds__exact_slope_boundary_passes_and_one_byte_over_fails(
        self,
    ) -> None:
        stage_memory = tuple(
            evidence_contract.StageMemorySeries(stage, 100_000_000, 100_000_000)
            for stage in STAGE_NAMES
        )
        limits = derive_thresholds(stage_memory)
        baseline = ThresholdBaseline(
            reference_environment_sha256=REFERENCE_SHA,
            measurement_points=(
                ThresholdPointIdentity(
                    file_count=10_000,
                    evidence="supporting/point-10000.json",
                    evidence_sha256=SHA_ZERO,
                ),
                ThresholdPointIdentity(
                    file_count=100_000,
                    evidence="accepted/point-100000.json",
                    evidence_sha256=SHA_ONE,
                ),
            ),
            target_file_count=1_000_000,
            fitting_method="exact-per-stage-linear-projection",
            limits=limits,
        )
        context = evidence_contract.ThresholdContext(
            baseline=baseline,
            baseline_sha256=SHA_ZERO,
            stage_memory=stage_memory,
        )
        at_boundary: dict[StageName, int] = dict.fromkeys(STAGE_NAMES, 100_000_000)
        one_over_rss: dict[StageName, int] = {**at_boundary, "scan": 100_000_001}

        passing = evidence_contract.evaluate_thresholds(
            context, file_count=100_000, stage_peak_rss=at_boundary
        )
        one_over = evidence_contract.evaluate_thresholds(
            context,
            file_count=100_000,
            stage_peak_rss=one_over_rss,
        )

        assert passing.observed_slope_bytes_per_file == 0
        assert passing.passed is True
        assert one_over.observed_slope_bytes_per_file == 1
        assert one_over.slope_passed is False
        assert one_over.passed is False

    def test_release_thresholds__use_exact_three_point_stage_ols(self) -> None:
        stage_memory = (
            evidence_contract.StageMemorySeries("scan", 100_000_000, 550_000_000),
            evidence_contract.StageMemorySeries("plan", 300_000_000, 350_000_000),
            evidence_contract.StageMemorySeries("apply", 200_000_000, 300_000_000),
            evidence_contract.StageMemorySeries("verify", 150_000_000, 250_000_000),
        )
        limits = derive_thresholds(stage_memory)
        context = evidence_contract.ThresholdContext(
            baseline=ThresholdBaseline(
                reference_environment_sha256=REFERENCE_SHA,
                measurement_points=(
                    ThresholdPointIdentity(
                        file_count=10_000,
                        evidence="supporting/point-10000.json",
                        evidence_sha256=SHA_ZERO,
                    ),
                    ThresholdPointIdentity(
                        file_count=100_000,
                        evidence="accepted/point-100000.json",
                        evidence_sha256=SHA_ONE,
                    ),
                ),
                target_file_count=1_000_000,
                fitting_method="exact-per-stage-linear-projection",
                limits=limits,
            ),
            baseline_sha256=SHA_ZERO,
            stage_memory=stage_memory,
        )

        verdict = evidence_contract.evaluate_thresholds(
            context,
            file_count=1_000_000,
            stage_peak_rss={
                "scan": 5_050_000_000,
                "plan": 850_000_000,
                "apply": 1_300_000_000,
                "verify": 1_250_000_000,
            },
        )

        assert verdict.observed_slope_bytes_per_file == 5_000
        assert verdict.observed_linearity_ratio == 0
        assert verdict.passed is True

    def test_threshold_peak__exact_boundary_passes_and_one_byte_over_fails(self) -> None:
        stage_memory = tuple(
            evidence_contract.StageMemorySeries(stage, 100_000_000, 100_000_000)
            for stage in STAGE_NAMES
        )
        limits = derive_thresholds(stage_memory)
        context = evidence_contract.ThresholdContext(
            baseline=ThresholdBaseline(
                reference_environment_sha256=REFERENCE_SHA,
                measurement_points=(
                    ThresholdPointIdentity(
                        file_count=10_000,
                        evidence="supporting/point-10000.json",
                        evidence_sha256=SHA_ZERO,
                    ),
                    ThresholdPointIdentity(
                        file_count=100_000,
                        evidence="accepted/point-100000.json",
                        evidence_sha256=SHA_ONE,
                    ),
                ),
                target_file_count=1_000_000,
                fitting_method="exact-per-stage-linear-projection",
                limits=limits,
            ),
            baseline_sha256=SHA_ZERO,
            stage_memory=stage_memory,
        )
        ordinary: dict[StageName, int] = dict.fromkeys(STAGE_NAMES, 100_000_000)
        boundary_rss: dict[StageName, int] = {
            **ordinary,
            "scan": limits.absolute_peak_rss_bytes,
        }
        one_over_rss: dict[StageName, int] = {
            **ordinary,
            "scan": limits.absolute_peak_rss_bytes + 1,
        }

        boundary = evidence_contract.evaluate_thresholds(
            context,
            file_count=1_000_000,
            stage_peak_rss=boundary_rss,
        )
        one_over = evidence_contract.evaluate_thresholds(
            context,
            file_count=1_000_000,
            stage_peak_rss=one_over_rss,
        )

        assert boundary.peak_passed is True
        assert one_over.peak_passed is False

    def test_threshold_ratio__is_rounded_upward_to_twelve_decimal_places(self) -> None:
        stage_memory = tuple(
            evidence_contract.StageMemorySeries(stage, 3, 3) for stage in STAGE_NAMES
        )
        limits = derive_thresholds(stage_memory)
        context = evidence_contract.ThresholdContext(
            baseline=ThresholdBaseline(
                reference_environment_sha256=REFERENCE_SHA,
                measurement_points=(
                    ThresholdPointIdentity(
                        file_count=10_000,
                        evidence="supporting/point-10000.json",
                        evidence_sha256=SHA_ZERO,
                    ),
                    ThresholdPointIdentity(
                        file_count=100_000,
                        evidence="accepted/point-100000.json",
                        evidence_sha256=SHA_ONE,
                    ),
                ),
                target_file_count=1_000_000,
                fitting_method="exact-per-stage-linear-projection",
                limits=limits,
            ),
            baseline_sha256=SHA_ZERO,
            stage_memory=stage_memory,
        )

        verdict = evidence_contract.evaluate_thresholds(
            context,
            file_count=100_000,
            stage_peak_rss={"scan": 4, "plan": 3, "apply": 3, "verify": 3},
        )

        assert verdict.observed_linearity_ratio == 0.333_333_333_334

    def test_thresholds__clamp_negative_stage_growth_to_zero(self) -> None:
        thresholds = derive_thresholds(
            (
                evidence_contract.StageMemorySeries("scan", 550_000_000, 100_000_000),
                evidence_contract.StageMemorySeries("plan", 10, 10),
                evidence_contract.StageMemorySeries("apply", 10, 10),
                evidence_contract.StageMemorySeries("verify", 10, 10),
            )
        )
        assert thresholds.absolute_peak_rss_bytes == 687_500_000
        assert thresholds.slope_bytes_per_file == 0
        assert thresholds.linearity_tolerance == 0.20

    def test_thresholds__round_fractional_limits_upward(self) -> None:
        thresholds = derive_thresholds(
            (
                evidence_contract.StageMemorySeries("scan", 1, 2),
                evidence_contract.StageMemorySeries("plan", 1, 1),
                evidence_contract.StageMemorySeries("apply", 1, 1),
                evidence_contract.StageMemorySeries("verify", 1, 1),
            )
        )
        assert thresholds.absolute_peak_rss_bytes == 15
        assert thresholds.slope_bytes_per_file == 1

    def test_threshold_verdict__reconciles_limits_and_component_results(self) -> None:
        verdict = ThresholdVerdict(
            limits=ThresholdSet(
                absolute_peak_rss_bytes=100,
                slope_bytes_per_file=10,
                linearity_tolerance=0.2,
            ),
            observed_peak_rss_bytes=99,
            observed_slope_bytes_per_file=9,
            observed_linearity_ratio=0.19,
            peak_passed=True,
            slope_passed=True,
            linearity_passed=True,
            passed=True,
        )
        assert verdict.passed is True

        document = verdict.model_dump()
        document["slope_passed"] = False
        with pytest.raises(ValidationError, match="component verdicts"):
            ThresholdVerdict.model_validate(document)

        document = verdict.model_dump()
        document["observed_linearity_ratio"] = float("nan")
        with pytest.raises(ValidationError, match="finite number"):
            ThresholdVerdict.model_validate(document)


def _write_baseline_fixture(
    root: Path,
    *,
    ten_k_count: int = 10_000,
    ten_k_status: str = "diagnostic",
    ten_k_reference_sha: str = REFERENCE_SHA,
    hundred_k_status: str = "passing",
    hundred_k_reference_sha: str = REFERENCE_SHA,
    hundred_k_commit: str = COMMIT,
    hundred_k_build_backend_version: str = "0.11.6",
) -> Path:
    supporting = root / "supporting" / "point-10000.json"
    accepted = root / "accepted" / "point-100000.json"
    write_scale_evidence(
        scale_evidence(
            count=ten_k_count,
            status=ten_k_status,
            reference_sha=ten_k_reference_sha,
        ),
        supporting,
        accepted=False,
    )
    write_scale_evidence(
        scale_evidence(
            count=100_000,
            status=hundred_k_status,
            reference_sha=hundred_k_reference_sha,
            candidate_commit=hundred_k_commit,
            build_backend_version=hundred_k_build_backend_version,
        ),
        accepted,
        accepted=hundred_k_status == "passing",
    )
    baseline = ThresholdBaseline(
        reference_environment_sha256=REFERENCE_SHA,
        measurement_points=(
            ThresholdPointIdentity(
                file_count=10_000,
                evidence="supporting/point-10000.json",
                evidence_sha256=sha256_of_file(supporting),
            ),
            ThresholdPointIdentity(
                file_count=100_000,
                evidence="accepted/point-100000.json",
                evidence_sha256=sha256_of_file(accepted),
            ),
        ),
        target_file_count=1_000_000,
        fitting_method="exact-per-stage-linear-projection",
        limits=ThresholdSet(
            absolute_peak_rss_bytes=83_886_080,
            slope_bytes_per_file=0,
            linearity_tolerance=0.20,
        ),
    )
    path = root / "thresholds.json"
    write_threshold_baseline(baseline, path)
    return path


class TestThresholdBaseline:
    def test_context_loader__freezes_stage_aligned_point_snapshots(self, tmp_path: Path) -> None:
        path = _write_baseline_fixture(tmp_path)

        context = evidence_contract.load_threshold_context(
            path, reference_environment_sha256=REFERENCE_SHA
        )
        frozen = context.stage_memory
        point = tmp_path / "supporting" / "point-10000.json"
        point.write_text(point.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        observed: dict[StageName, int] = {
            item.stage: item.rss_100k for item in context.stage_memory
        }
        verdict = evidence_contract.evaluate_thresholds(
            context, file_count=100_000, stage_peak_rss=observed
        )

        assert tuple(item.stage for item in frozen) == ("scan", "plan", "apply", "verify")
        assert context.stage_memory == frozen
        assert context.baseline_sha256 == sha256_of_file(path)
        assert verdict.passed is True

    def test_loader__validates_point_hashes_references_and_status(self, tmp_path: Path) -> None:
        path = _write_baseline_fixture(tmp_path)
        limits = load_threshold_limits(
            "scheduled", path, reference_environment_sha256=REFERENCE_SHA
        )
        assert limits == ThresholdSet(
            absolute_peak_rss_bytes=83_886_080,
            slope_bytes_per_file=0,
            linearity_tolerance=0.20,
        )

        baseline, digest = load_threshold_baseline_snapshot(
            path, reference_environment_sha256=REFERENCE_SHA
        )
        assert baseline.limits == limits
        assert digest == sha256_of_file(path)

    @pytest.mark.parametrize("tier", ["scheduled", "release"])
    def test_scheduled_and_release__require_validated_baseline(
        self, tier: Literal["scheduled", "release"], tmp_path: Path
    ) -> None:
        with pytest.raises(ScaleEvidenceError, match="requires a threshold baseline"):
            load_threshold_limits(tier, None, reference_environment_sha256=REFERENCE_SHA)

        path = _write_baseline_fixture(tmp_path)
        loaded = load_threshold_limits(tier, path, reference_environment_sha256=REFERENCE_SHA)
        assert loaded is not None
        assert loaded.absolute_peak_rss_bytes == 83_886_080

    def test_loader__rejects_limits_not_derived_from_pinned_points(self, tmp_path: Path) -> None:
        path = _write_baseline_fixture(tmp_path)
        document = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
        limits = cast("dict[str, object]", document["limits"])
        limits["absolute_peak_rss_bytes"] = 999_999_999
        path.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ScaleEvidenceError, match="limits do not match"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

    def test_loader__requires_shared_candidate_provenance(self, tmp_path: Path) -> None:
        path = _write_baseline_fixture(tmp_path, hundred_k_commit="c" * 40)
        with pytest.raises(ScaleEvidenceError, match="pilot provenance mismatch"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

    def test_loader__requires_shared_build_backend_provenance(self, tmp_path: Path) -> None:
        path = _write_baseline_fixture(tmp_path, hundred_k_build_backend_version="0.11.7")
        with pytest.raises(ScaleEvidenceError, match="pilot provenance mismatch"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

    def test_loader__rejects_unsupported_version_before_generic_schema_error(
        self, tmp_path: Path
    ) -> None:
        path = _write_baseline_fixture(tmp_path)
        document = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
        document["schema_version"] = "1.0"
        path.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ScaleEvidenceError, match=r"unsupported threshold schema version 1\.0"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

    def test_loader__rejects_missing_or_changed_point(self, tmp_path: Path) -> None:
        missing_root = tmp_path / "missing"
        path = _write_baseline_fixture(missing_root)
        (missing_root / "supporting" / "point-10000.json").unlink()
        with pytest.raises(ScaleEvidenceError, match="cannot read threshold evidence point"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

        changed_root = tmp_path / "changed"
        path = _write_baseline_fixture(changed_root)
        point = changed_root / "supporting" / "point-10000.json"
        point.write_text(point.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with pytest.raises(ScaleEvidenceError, match="hash mismatch"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

    def test_loader__rejects_reference_mismatch(self, tmp_path: Path) -> None:
        path = _write_baseline_fixture(tmp_path)
        with pytest.raises(ScaleEvidenceError, match="reference environment mismatch"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=SHA_ZERO)

        other_root = tmp_path / "point-mismatch"
        path = _write_baseline_fixture(other_root, hundred_k_reference_sha=SHA_ZERO)
        with pytest.raises(ScaleEvidenceError, match="reference environment mismatch"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

        ten_k_root = tmp_path / "ten-k-point-mismatch"
        path = _write_baseline_fixture(ten_k_root, ten_k_reference_sha=SHA_ZERO)
        with pytest.raises(ScaleEvidenceError, match="reference environment mismatch"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

    def test_loader__rejects_point_identity_count_mismatch(self, tmp_path: Path) -> None:
        path = _write_baseline_fixture(tmp_path, ten_k_count=10_001)
        with pytest.raises(ScaleEvidenceError, match="count does not match"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

    def test_loader__rejects_nonpassing_100k_point(self, tmp_path: Path) -> None:
        path = _write_baseline_fixture(tmp_path, hundred_k_status="diagnostic")
        with pytest.raises(ScaleEvidenceError, match="100000-file point must be passing"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

    def test_loader__rejects_incomplete_10k_point(self, tmp_path: Path) -> None:
        path = _write_baseline_fixture(tmp_path, ten_k_status="incomplete")
        with pytest.raises(ScaleEvidenceError, match="10000-file point must be passing-quality"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

    def test_threshold_point_identity__rejects_unsafe_names_in_model_and_schema(self) -> None:
        for evidence in (
            ".",
            "./",
            "/absolute.json",
            "../outside.json",
            "supporting/../../outside.json",
            r"supporting\private.json",
            r"C:\private.json",
            "supporting/control\nname.json",
            "supporting/nul\x00name.json",
        ):
            with pytest.raises(ValidationError, match="evidence"):
                ThresholdPointIdentity(
                    file_count=10_000,
                    evidence=evidence,
                    evidence_sha256=SHA_ZERO,
                )

            document = {
                "schema": "docmend/scale-thresholds",
                "schema_version": "2.0",
                "reference_environment_sha256": REFERENCE_SHA,
                "measurement_points": [
                    {
                        "file_count": 10_000,
                        "evidence": evidence,
                        "evidence_sha256": SHA_ZERO,
                    },
                    {
                        "file_count": 100_000,
                        "evidence": "accepted/point-100000.json",
                        "evidence_sha256": SHA_ONE,
                    },
                ],
                "target_file_count": 1_000_000,
                "fitting_method": "exact-per-stage-linear-projection",
                "limits": {
                    "absolute_peak_rss_bytes": 1,
                    "slope_bytes_per_file": 0,
                    "linearity_tolerance": 0.2,
                },
            }
            with pytest.raises(ScaleEvidenceError, match="measurement_points"):
                validate_qualification_document("scale-thresholds", document)

    def test_baseline__requires_ordered_10k_and_100k_points(self) -> None:
        ten_k = ThresholdPointIdentity(
            file_count=10_000,
            evidence="supporting/point-10000.json",
            evidence_sha256=SHA_ZERO,
        )
        hundred_k = ThresholdPointIdentity(
            file_count=100_000,
            evidence="accepted/point-100000.json",
            evidence_sha256=SHA_ONE,
        )
        with pytest.raises(ValidationError, match="10000-file and 100000-file"):
            ThresholdBaseline(
                reference_environment_sha256=REFERENCE_SHA,
                measurement_points=(hundred_k, ten_k),
                target_file_count=1_000_000,
                fitting_method="exact-per-stage-linear-projection",
                limits=ThresholdSet(
                    absolute_peak_rss_bytes=1,
                    slope_bytes_per_file=0,
                    linearity_tolerance=0.2,
                ),
            )

        document = ThresholdBaseline(
            reference_environment_sha256=REFERENCE_SHA,
            measurement_points=(ten_k, hundred_k),
            target_file_count=1_000_000,
            fitting_method="exact-per-stage-linear-projection",
            limits=ThresholdSet(
                absolute_peak_rss_bytes=1,
                slope_bytes_per_file=0,
                linearity_tolerance=0.2,
            ),
        ).model_dump(mode="json")
        points = cast("list[dict[str, object]]", document["measurement_points"])
        document["measurement_points"] = list(reversed(points))
        with pytest.raises(ScaleEvidenceError, match="measurement_points"):
            validate_qualification_document("scale-thresholds", document)

    def test_loader__rejects_symlink_escape(self, tmp_path: Path) -> None:
        evidence_root = tmp_path / "evidence"
        path = _write_baseline_fixture(evidence_root)
        outside = tmp_path / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        point = evidence_root / "supporting" / "point-10000.json"
        point.unlink()
        point.symlink_to(outside)
        with pytest.raises(ScaleEvidenceError, match="escapes its evidence root"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)

    def test_loader__rejects_symlink_even_when_target_stays_beneath_root(
        self, tmp_path: Path
    ) -> None:
        evidence_root = tmp_path / "evidence"
        path = _write_baseline_fixture(evidence_root)
        point = evidence_root / "supporting" / "point-10000.json"
        moved = evidence_root / "supporting" / "moved.json"
        point.rename(moved)
        point.symlink_to(moved.name)

        with pytest.raises(ScaleEvidenceError, match="cannot read threshold evidence point"):
            load_threshold_limits("scheduled", path, reference_environment_sha256=REFERENCE_SHA)
