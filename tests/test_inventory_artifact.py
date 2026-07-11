"""Inventory artifact tests (spec: DR-001, IR-007; adr-0005 round-trip contract).

The inventory is the first durable artifact to go live: write -> read must
reproduce an identical model (IR-007), every produced document must validate
against the checked-in schema, and the DR-001 aggregate counts must reconcile
exactly with the per-file records.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docmend import artifacts
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


def test_artifact_staging__randomized_and_retry_safe(tmp_path: Path) -> None:
    """DMR-02: the old fixed '<name>.tmp' sibling was a predictable truncation
    target and blocked nothing on collision. Staging must be O_EXCL-random:
    pre-existing residue at the legacy name must be left untouched and must
    not block the write."""
    dest = tmp_path / "out.json"
    legacy_residue = tmp_path / "out.json.tmp"
    legacy_residue.write_bytes(b"victim bytes that must survive")
    artifacts.write_json_artifact({"k": "v"}, dest)
    assert json.loads(dest.read_text()) == {"k": "v"}
    assert legacy_residue.read_bytes() == b"victim bytes that must survive"
    leftovers = sorted(p.name for p in tmp_path.iterdir())
    assert leftovers == ["out.json", "out.json.tmp"]  # staging temp cleaned up
    # F6: modes stay umask-derived — no artifact-mode policy is decided here.
    umask = os.umask(0)
    os.umask(umask)
    assert (dest.stat().st_mode & 0o777) == (0o666 & ~umask)


def test_artifact_staging__serialization_failure_leaves_no_residue(tmp_path: Path) -> None:
    """plan-review F4: json.dump can raise TypeError on a non-serializable
    document; cleanup must cover that class too, not only OSError."""
    dest = tmp_path / "out.json"
    with pytest.raises(TypeError):
        artifacts.write_json_artifact({"k": object()}, dest)
    assert not dest.exists()
    assert list(tmp_path.iterdir()) == []


def test_artifact_staging_exhaustion__oserror_no_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 8-attempt staging-name loop's `for...else` bound: if every
    candidate collides (here, token_hex is pinned so all 8 attempts generate
    the same colliding name), allocation must fail as OSError rather than
    loop forever — no destination is produced and the colliding residue is
    left untouched."""
    dest = tmp_path / "out.json"
    residue = tmp_path / ".out.json.deadbeef.tmp"
    residue.write_bytes(b"stale residue that always collides")

    def fixed_token_hex(nbytes: int) -> str:
        return "deadbeef"

    monkeypatch.setattr(artifacts.secrets, "token_hex", fixed_token_hex)
    with pytest.raises(OSError):
        artifacts.write_json_artifact({"k": "v"}, dest)
    assert not dest.exists()
    assert residue.read_bytes() == b"stale residue that always collides"
