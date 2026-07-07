"""Inventory artifact tests (spec: DR-001, IR-007; adr-0005 round-trip contract).

The inventory is the first durable artifact to go live: write -> read must
reproduce an identical model (IR-007), every produced document must validate
against the checked-in schema, and the DR-001 aggregate counts must reconcile
exactly with the per-file records.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docmend.artifacts import ArtifactError, read_inventory, validate_artifact, write_inventory
from docmend.config import DocmendConfig
from docmend.discovery import scan
from docmend.inventory import Inventory

RUN_ID = "run_20260706T000000Z_abc123"


@pytest.fixture
def inventory(tmp_path: Path) -> Inventory:
    corpus = tmp_path / "corpus"
    (corpus / "sub").mkdir(parents=True)
    (corpus / "a.txt").write_text("alpha\n")
    (corpus / "b.txt").write_bytes(b"beta\r\ncaf\xe9\r\n")  # cp1252 é: detected stays null
    (corpus / "sub" / "c.md").write_text("# gamma\n")
    (corpus / "skip.png").write_bytes(b"\x89PNG")
    return scan(
        corpus,
        DocmendConfig(),
        run_id=RUN_ID,
        generated_at=datetime(2026, 7, 6, tzinfo=UTC).isoformat(),
    )


class TestRoundTrip:
    def test_write_read__identical_model(self, inventory: Inventory, tmp_path: Path) -> None:
        """spec: IR-007 — inventory round-trip: write -> read -> identical model."""
        artifact = tmp_path / "out" / "inventory.json"
        write_inventory(inventory, artifact)
        assert read_inventory(artifact) == inventory

    def test_write__leaves_no_temp_file(self, inventory: Inventory, tmp_path: Path) -> None:
        """OQ-003: the artifact is atomic — it exists complete or not at all."""
        artifact = tmp_path / "inventory.json"
        write_inventory(inventory, artifact)
        assert [p.name for p in tmp_path.iterdir() if p.is_file()] == ["inventory.json"]

    def test_written_document__validates_against_checked_in_schema(
        self, inventory: Inventory, tmp_path: Path
    ) -> None:
        """spec: DR-001 — the produced document satisfies the external contract."""
        artifact = tmp_path / "inventory.json"
        write_inventory(inventory, artifact)
        document = json.loads(artifact.read_text(encoding="utf-8"))
        validate_artifact("inventory", document)
        assert document["schema"] == "docmend/inventory"
        assert document["schema_version"] == "1.2"
        assert document["run_id"] == RUN_ID


class TestCountReconciliation:
    def test_totals__reconcile_with_record_arrays(self, inventory: Inventory) -> None:
        """spec: DR-001 — counts must reconcile with per-file records."""
        totals = inventory.totals
        assert totals.files == len(inventory.files) == 3
        assert totals.symlinks == len(inventory.symlinks)
        assert totals.skipped == len(inventory.skipped)
        assert totals.skipped == totals.skipped_by_reason.excluded + (
            totals.skipped_by_reason.unreadable
        )
        assert totals.hard_link_groups == len(inventory.hard_link_groups)
        assert totals.total_size_bytes == sum(record.size_bytes for record in inventory.files)


class TestReadFailureModes:
    """ERR-008 family: invalid artifacts refuse loudly, with the cause named."""

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ArtifactError, match="cannot read"):
            read_inventory(tmp_path / "absent.json")

    def test_not_json(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("not json at all")
        with pytest.raises(ArtifactError, match="not valid JSON"):
            read_inventory(bad)

    def test_unknown_field_rejected(self, inventory: Inventory, tmp_path: Path) -> None:
        """adr-0005 strictness: additionalProperties:false rejects drift."""
        artifact = tmp_path / "inventory.json"
        write_inventory(inventory, artifact)
        document = json.loads(artifact.read_text(encoding="utf-8"))
        document["surprise"] = True
        artifact.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ArtifactError, match="surprise"):
            read_inventory(artifact)

    def test_wrong_schema_kind_rejected(self, inventory: Inventory, tmp_path: Path) -> None:
        artifact = tmp_path / "inventory.json"
        write_inventory(inventory, artifact)
        document = json.loads(artifact.read_text(encoding="utf-8"))
        document["schema"] = "docmend/plan"
        artifact.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ArtifactError, match="schema"):
            read_inventory(artifact)

    def test_bad_timestamp_rejected_by_format_assertion(
        self, inventory: Inventory, tmp_path: Path
    ) -> None:
        """OQ-018: format is asserted, not annotation-only — a malformed
        date-time must fail validation."""
        artifact = tmp_path / "inventory.json"
        write_inventory(inventory, artifact)
        document = json.loads(artifact.read_text(encoding="utf-8"))
        document["generated_at"] = "yesterday-ish"
        artifact.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ArtifactError, match=r"generated_at|date-time"):
            read_inventory(artifact)
