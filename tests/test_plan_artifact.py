"""DR-002 plan artifact: model<->schema conformance, round-trip, IDs (adr-0005, IR-007)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from docmend import artifacts
from docmend.config import DocmendConfig
from docmend.plan import (
    ActionProvenance,
    ArtifactRef,
    Plan,
    PlanAction,
    PlanTotals,
    SkipDecision,
)

RUN = "run_20260706T000000Z_abc123"


def sample_plan() -> Plan:
    return Plan(
        run_id=RUN,
        generated_at="2026-07-06T00:00:00+00:00",
        generated_by="docmend 0.1.0",
        inventory_ref=ArtifactRef(
            path=".docmend/docmend-run_20260706T000000Z_abc123-inventory.json",
            run_id=RUN,
            sha256="sha256:" + "0" * 64,
        ),
        config=DocmendConfig().model_dump(mode="json"),
        actions=[
            PlanAction(
                action_id=f"{RUN}/a1",
                docmend_id="019807c0-0000-7000-8000-000000000000",
                path="legacy.txt",
                source_sha256="sha256:" + "1" * 64,
                source_size_bytes=120,
                operations=["reencode", "normalize_newlines", "rename"],
                target_path="legacy.md",
                provenance=ActionProvenance(detected_encoding=None, newline_style="crlf"),
            )
        ],
        skips=[SkipDecision(path="blob.txt", reason="binary-suspect", detail=None)],
        totals=PlanTotals(actions=1, skips=1),
    )


class TestPlanModel:
    def test_dump__validates_against_checked_in_schema(self) -> None:
        artifacts.validate_artifact("plan", sample_plan().model_dump(mode="json"))

    def test_schema_key__serialized_by_alias(self) -> None:
        assert sample_plan().model_dump(mode="json")["schema"] == "docmend/plan"

    def test_action_id__pattern_enforced(self) -> None:
        with pytest.raises(ValidationError):
            PlanAction(
                action_id="not-an-action-id",
                docmend_id="019807c0-0000-7000-8000-000000000000",
                path="x.txt",
                source_sha256="sha256:" + "1" * 64,
                source_size_bytes=1,
                operations=["rename"],
                target_path="x.md",
                provenance=ActionProvenance(detected_encoding=None, newline_style="lf"),
            )

    def test_changed_since_scan_reason__accepted(self) -> None:
        decision = SkipDecision(path="x.txt", reason="changed-since-scan", detail="sha mismatch")
        plan = sample_plan().model_copy(
            update={"skips": [decision], "totals": PlanTotals(actions=1, skips=1)}
        )
        artifacts.validate_artifact("plan", plan.model_dump(mode="json"))


class TestPlanArtifactIO:
    def test_round_trip__identical(self, tmp_path: Path) -> None:
        # IR-007: write -> read -> identical model.
        target = tmp_path / "plan.json"
        plan = sample_plan()
        artifacts.write_plan(plan, target)
        assert artifacts.read_plan(target) == plan

    def test_read_missing_file__raises_artifact_error(self, tmp_path: Path) -> None:
        with pytest.raises(artifacts.ArtifactError, match="cannot read"):
            artifacts.read_plan(tmp_path / "absent.json")

    def test_read_invalid_json__raises_artifact_error(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.json"
        target.write_text("{not json")
        with pytest.raises(artifacts.ArtifactError):
            artifacts.read_plan(target)

    def test_read_schema_violating_document__raises(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.json"
        target.write_text('{"schema": "docmend/plan"}')
        with pytest.raises(artifacts.ArtifactError):
            artifacts.read_plan(target)


class TestSha256OfFile:
    def test_matches__hashlib(self, tmp_path: Path) -> None:
        import hashlib

        target = tmp_path / "f.bin"
        target.write_bytes(b"abc")
        assert artifacts.sha256_of_file(target) == "sha256:" + hashlib.sha256(b"abc").hexdigest()
