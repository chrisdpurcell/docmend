"""Manifest writer/reader (DR-004, IR-007 NDJSON half, adr-0005/adr-0006).

Real filesystem on purpose (OQ-019): the per-record append+fsync durability
behavior is the thing under test. The AOF rule (adr-0006): tolerate only a
torn TRAILING line; hard-abort on any interior corruption.
"""

import json
from pathlib import Path

import pytest

from docmend.artifacts import ArtifactError
from docmend.writer.manifest import ManifestRecord, ManifestWriter, read_manifest

RUN_ID = "run_20260706T000000Z_00006d"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
UUID7 = "01980000-0000-7000-8000-000000000001"


def _record(seq_free_suffix: int) -> ManifestRecord:
    return ManifestRecord(
        run_id=RUN_ID,
        action_id=f"{RUN_ID}/a{seq_free_suffix}",
        docmend_id=UUID7,
        seq=1,  # placeholder; ManifestWriter.append re-stamps
        recorded_at="2026-07-06T00:00:00+00:00",
        operation="rewrite",
        original_path="/corpus/a.txt",
        target_path="/corpus/a.txt",
        backup_path=None,
        before_sha256=SHA_A,
        after_sha256=SHA_B,
        result="applied",
        error=None,
    )


def test_append_read_round_trip__per_record(tmp_path: Path) -> None:
    """IR-007: each NDJSON line parses back to an identical record model (DR-004)."""
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        first = writer.append(_record(1))
        second = writer.append(_record(2))
    assert (first.seq, second.seq) == (1, 2)
    assert read_manifest(path) == [first, second]


def test_torn_trailing_line__tolerated(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        kept = writer.append(_record(1))
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"schema": "docmend/manifest-record", "torn')  # no newline: crash mid-append
    assert read_manifest(path) == [kept]


def test_corrupt_newline_terminated_final_record__hard_aborts(tmp_path: Path) -> None:
    """codex CR-NEW-006: a final line ending in '\\n' was a COMPLETE record —
    if it no longer parses, that is corruption, never a tolerable torn tail."""
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        writer.append(_record(1))
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{corrupt}\n")
    with pytest.raises(ArtifactError):
        read_manifest(path)


def test_first_append_fsyncs_manifest_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """codex CR-NEW-005: creating the manifest file must fsync its directory —
    file fsync alone does not persist a new directory entry."""
    from docmend.writer import manifest as manifest_module

    calls: list[Path] = []
    monkeypatch.setattr(manifest_module, "fsync_dir", calls.append)
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        writer.append(_record(1))
        writer.append(_record(2))
    assert calls == [tmp_path]  # exactly once, on first create


def test_corrupt_interior_line__hard_aborts(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        record = writer.append(_record(1))
    lines = path.read_text(encoding="utf-8")
    path.write_text("{corrupt}\n" + lines, encoding="utf-8")
    with pytest.raises(ArtifactError):
        read_manifest(path)
    del record


def test_schema_invalid_interior_record__hard_aborts(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        writer.append(_record(1))
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["result"] = "not-a-result"
    path.write_text(json.dumps(doc) + "\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ArtifactError):
        read_manifest(path)


def test_zero_appends__no_manifest_file_created(tmp_path: Path) -> None:
    """A write run in which every action skipped leaves NO manifest file —
    an empty manifest would imply mutations happened (lazy-open contract)."""
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID):
        pass
    assert not path.exists()


def test_read_manifest__missing_file_raises_cannot_read(tmp_path: Path) -> None:
    """DR-004, ERR-008 family: mirrors read_inventory/read_plan/read_report (adr-0005)."""
    with pytest.raises(ArtifactError, match="cannot read"):
        read_manifest(tmp_path / "absent.jsonl")


def test_overwrite_fields__round_trip(tmp_path: Path) -> None:
    """Manifest 1.1 (OQ-035): clobbered-target preservation fields."""
    path = tmp_path / "manifest.jsonl"
    record = _record(1).model_copy(
        update={"overwritten_sha256": SHA_B, "overwritten_backup_path": "/backups/run/x.md"}
    )
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        written = writer.append(record)
    assert read_manifest(path)[0] == written


def test_source_root__stamped_by_writer_and_round_trips(tmp_path: Path) -> None:
    """Manifest 1.2 (OQ-036): the writer stamps the apply run's source_root onto
    every record — a run-level constant, stamped like seq/recorded_at — so restore
    can key its lock on it (closes the commonpath-divergence gap, AW-005)."""
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID, source_root="/corpus/root") as writer:
        written = writer.append(_record(1))
    assert written.source_root == "/corpus/root"
    assert read_manifest(path)[0].source_root == "/corpus/root"


def test_source_root__unset_writer_leaves_none(tmp_path: Path) -> None:
    """A writer without a source_root (e.g. restore's inverse manifest) leaves the
    field None — it is optional, not required."""
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        written = writer.append(_record(1))
    assert written.source_root is None
    assert read_manifest(path)[0].source_root is None


def test_pre_1_2_record_missing_source_root_key__still_reads(tmp_path: Path) -> None:
    """Backward compat: a manifest written by the 1.1 writer has no source_root key
    at all; the 1.2 reader must accept it (schema optional, model defaults None)."""
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        writer.append(_record(1))
    doc = json.loads(path.read_text(encoding="utf-8"))
    del doc["source_root"]  # simulate a genuine pre-1.2 on-disk record
    path.write_text(json.dumps(doc) + "\n", encoding="utf-8")
    assert read_manifest(path)[0].source_root is None
