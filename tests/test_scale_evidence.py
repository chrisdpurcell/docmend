"""DMR-08 public qualification evidence and executable-threshold contracts."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import pytest
from pydantic import ValidationError

from docmend.artifacts import ARTIFACT_KINDS, sha256_of_file
from docmend.scale_evidence import (
    FilesystemCapacityEvidence,
    MemoryPoint,
    PreflightEvidence,
    QualificationTotals,
    ReferenceEnvironment,
    ScaleEvidence,
    ScaleEvidenceError,
    StageEvidence,
    ThresholdBaseline,
    ThresholdPointIdentity,
    ThresholdSet,
    ThresholdVerdict,
    derive_thresholds,
    fit_peak_rss_slope,
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

SHA_ZERO = "sha256:" + "0" * 64
SHA_ONE = "sha256:" + "1" * 64
REFERENCE_SHA = "sha256:" + "a" * 64
COMMIT = "b" * 40


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
        available_inodes=2_000 if passed else 1_000,
        margin_fraction=0.25,
        passed=passed,
    )


def _preflight(*, passed: bool = True) -> PreflightEvidence:
    return PreflightEvidence(
        filesystems=(_capacity(passed=passed),),
        reference_environment_match=passed,
        binding_filesystem=passed,
        ram_requirement_met=passed,
        passed=passed,
    )


def _stage(stage: str, *, completed: bool = True) -> StageEvidence:
    return StageEvidence.model_validate(
        {
            "stage": stage,
            "run_id": "run_20260713T000000Z_abc123" if completed else None,
            "elapsed_seconds": 1.25,
            "files_per_second": 800.0,
            "bytes_per_second": 819_200.0,
            "peak_rss_bytes": 64 * 1024**2,
            "python_allocation_peak_bytes": None,
            "vm_swap_peak_bytes": 0,
            "exit_code": 0,
            "completed": completed,
            "artifact_bytes": {"inventory": 1_024},
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
) -> ScaleEvidence:
    values: dict[str, object] = {
        "status": status,
        "tier": tier,
        "candidate_commit": candidate_commit,
        "package_version": "2.0.0",
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
        "cache_classification": "cold",
        "started_at": datetime(2026, 7, 13, tzinfo=UTC),
        "completed_at": datetime(2026, 7, 13, 0, 1, tzinfo=UTC),
        "preflight": _preflight(),
        "file_count": count,
        "corpus_bytes": count * 1_024,
        "stages": [_stage(stage) for stage in ("scan", "plan", "apply", "verify")],
        "totals": _totals(count),
        "thresholds": None,
    }
    return ScaleEvidence.model_validate(values)


class TestPublicContract:
    def test_qualification_schemas__stay_out_of_product_artifact_registry(self) -> None:
        assert {
            "scale-evidence",
            "reference-environment",
            "scale-thresholds",
        }.isdisjoint(ARTIFACT_KINDS)

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

    def test_passing_installed_evidence__requires_exact_wheel_and_completed_pipeline(self) -> None:
        document = scale_evidence().model_dump()
        document["wheel_sha256"] = None
        with pytest.raises(ValidationError, match="wheel_sha256"):
            ScaleEvidence.model_validate(document)

        document = scale_evidence().model_dump()
        document["stages"] = document["stages"][:-1]
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
        with pytest.raises(ValidationError, match="conserve the corpus"):
            ScaleEvidence.model_validate(document)

        document = scale_evidence().model_dump()
        totals = cast("dict[str, object]", document["totals"])
        totals["failures"] = 1
        totals["applied"] = cast("int", totals["applied"]) - 1
        with pytest.raises(ValidationError, match="cannot contain failures"):
            ScaleEvidence.model_validate(document)

    def test_passing_evidence__reconciles_stage_exit_codes(self) -> None:
        document = scale_evidence().model_dump()
        stages = cast("list[dict[str, object]]", document["stages"])
        stages[0]["exit_code"] = 1
        with pytest.raises(ValidationError, match="scan, plan, and apply must exit 0"):
            ScaleEvidence.model_validate(document)

        document = scale_evidence().model_dump()
        stages = cast("list[dict[str, object]]", document["stages"])
        stages[-1]["exit_code"] = 1
        with pytest.raises(ValidationError, match="verify exit code"):
            ScaleEvidence.model_validate(document)

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
        with pytest.raises(ValidationError, match="never mix"):
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
            observed_slope_bytes_per_file=9_000.0,
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
            observed_slope_bytes_per_file=float(baseline.limits.slope_bytes_per_file),
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

    def test_reference_environment__round_trips_and_never_clobbers(self, tmp_path: Path) -> None:
        environment = reference_environment()
        path = tmp_path / "reference.json"
        write_reference_environment(environment, path)
        with pytest.raises(FileExistsError):
            write_reference_environment(environment, path)
        assert read_reference_environment(path) == environment


class TestThresholdMath:
    def test_fit_peak_rss_slope__is_exact_and_order_independent(self) -> None:
        points = [
            MemoryPoint(files=10_000, peak_rss_bytes=100_000_000),
            MemoryPoint(files=100_000, peak_rss_bytes=550_000_000),
        ]
        fit = fit_peak_rss_slope(points)
        reverse_fit = fit_peak_rss_slope(reversed(points))
        assert fit == reverse_fit
        assert fit.slope_bytes_per_file.numerator == 5_000
        assert fit.slope_bytes_per_file.denominator == 1
        assert fit.intercept_bytes == 50_000_000

    def test_fit_peak_rss_slope__uses_all_points_without_float_rounding(self) -> None:
        fit = fit_peak_rss_slope(
            [
                MemoryPoint(files=1, peak_rss_bytes=1),
                MemoryPoint(files=2, peak_rss_bytes=3),
                MemoryPoint(files=4, peak_rss_bytes=4),
            ]
        )
        assert fit.slope_bytes_per_file.numerator == 13
        assert fit.slope_bytes_per_file.denominator == 14
        assert fit.intercept_bytes.numerator == 1
        assert fit.intercept_bytes.denominator == 2

    @pytest.mark.parametrize(
        "points",
        [
            [MemoryPoint(files=10_000, peak_rss_bytes=1)],
            [
                MemoryPoint(files=10_000, peak_rss_bytes=1),
                MemoryPoint(files=10_000, peak_rss_bytes=2),
            ],
            [
                MemoryPoint(files=10_000, peak_rss_bytes=2),
                MemoryPoint(files=100_000, peak_rss_bytes=1),
            ],
        ],
    )
    def test_fit_peak_rss_slope__rejects_unusable_points(self, points: list[MemoryPoint]) -> None:
        with pytest.raises(ValueError):
            fit_peak_rss_slope(points)

    def test_thresholds__use_pilot_plus_headroom_with_upward_rounding(self) -> None:
        fit = fit_peak_rss_slope(
            [
                MemoryPoint(files=10_000, peak_rss_bytes=100_000_000),
                MemoryPoint(files=100_000, peak_rss_bytes=550_000_000),
            ]
        )
        thresholds = derive_thresholds(fit, largest_peak_bytes=550_000_000, headroom=0.25)
        assert thresholds.absolute_peak_rss_bytes == 687_500_000
        assert thresholds.slope_bytes_per_file == 6_250
        assert thresholds.linearity_tolerance == 0.20

    def test_thresholds__round_fractional_limits_upward(self) -> None:
        fit = fit_peak_rss_slope(
            [
                MemoryPoint(files=1, peak_rss_bytes=1),
                MemoryPoint(files=4, peak_rss_bytes=2),
            ]
        )
        thresholds = derive_thresholds(fit, largest_peak_bytes=3, headroom=0.25)
        assert thresholds.absolute_peak_rss_bytes == 4
        assert thresholds.slope_bytes_per_file == 1

    def test_threshold_verdict__reconciles_limits_and_component_results(self) -> None:
        verdict = ThresholdVerdict(
            limits=ThresholdSet(
                absolute_peak_rss_bytes=100,
                slope_bytes_per_file=10,
                linearity_tolerance=0.2,
            ),
            observed_peak_rss_bytes=99,
            observed_slope_bytes_per_file=9.5,
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
    ten_k_reference_sha: str = REFERENCE_SHA,
    hundred_k_status: str = "passing",
    hundred_k_reference_sha: str = REFERENCE_SHA,
    hundred_k_commit: str = COMMIT,
) -> Path:
    supporting = root / "supporting" / "point-10000.json"
    accepted = root / "accepted" / "point-100000.json"
    write_scale_evidence(
        scale_evidence(
            count=ten_k_count,
            status="diagnostic",
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
        fitting_method="exact-linear-least-squares",
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

    def test_loader__rejects_unsupported_version_before_generic_schema_error(
        self, tmp_path: Path
    ) -> None:
        path = _write_baseline_fixture(tmp_path)
        document = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
        document["schema_version"] = "2.0"
        path.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ScaleEvidenceError, match=r"unsupported threshold schema version 2\.0"):
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
                "schema_version": "1.0",
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
                "fitting_method": "exact-linear-least-squares",
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
                fitting_method="exact-linear-least-squares",
                limits=ThresholdSet(
                    absolute_peak_rss_bytes=1,
                    slope_bytes_per_file=0,
                    linearity_tolerance=0.2,
                ),
            )

        document = ThresholdBaseline(
            reference_environment_sha256=REFERENCE_SHA,
            measurement_points=(ten_k, hundred_k),
            fitting_method="exact-linear-least-squares",
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
