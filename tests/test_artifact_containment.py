"""Artifact path-containment hardening (spec §8.5/§13.5; MS-2 final-review Important #2).

A crafted or hand-edited inventory/plan with absolute or '..' paths must be
rejected at read time (ERR-008 semantics, exit 2) — the §8.5 apply-time
containment check remains the runtime gate; this is the artifact-layer belt.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from docmend import artifacts
from docmend.config import DocmendConfig
from docmend.inventory import FileRecord

BAD_PATHS = ["/etc/passwd", "../escape.txt", "a/../b.txt", "a/..", ".."]
GOOD_PATHS = ["a.txt", "sub/b.txt", "odd..name.txt", "sub/..hidden", "d../e.txt"]

RUN_ID = "run_20260706T000000Z_000000"


def _file_record(path: str) -> dict[str, object]:
    return {
        "path": path,
        "size_bytes": 1,
        "suffix": ".txt",
        "mtime_ns": 0,
        "nlink": 1,
        "sha256": "sha256:" + "0" * 64,
        "newline_style": "lf",
        "nul_bytes": False,
        "non_ascii_bytes": 0,
        "encoding": {"bom": None, "utf8_valid": True, "ascii_only": True, "detected": None},
    }


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_file_record_model__rejects_escaping_path(bad: str) -> None:
    with pytest.raises(ValidationError):
        FileRecord.model_validate(_file_record(bad))


@pytest.mark.parametrize("good", GOOD_PATHS)
def test_file_record_model__accepts_contained_path(good: str) -> None:
    assert FileRecord.model_validate(_file_record(good)).path == good


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_inventory_schema__rejects_escaping_path(bad: str) -> None:
    with pytest.raises(artifacts.ArtifactError):
        artifacts.validate_artifact("inventory", _minimal_inventory(bad))


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_read_inventory__rejects_crafted_artifact(tmp_path: Path, bad: str) -> None:
    doc = _minimal_inventory(bad)
    target = tmp_path / "inventory.json"
    target.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(artifacts.ArtifactError):
        artifacts.read_inventory(target)


def _minimal_inventory(path: str) -> dict[str, object]:
    record = _file_record(path)
    return {
        "schema": "docmend/inventory",
        "schema_version": "1.1",
        "run_id": RUN_ID,
        "generated_at": "2026-07-06T00:00:00+00:00",
        "generated_by": "docmend 0.1.0",
        "requested_path": "corpus",
        "source_root": "/corpus",
        "scan_config": {"include": ["**/*.txt"], "exclude": []},
        "files": [record],
        "symlinks": [],
        "skipped": [],
        "hard_link_groups": [],
        "totals": {
            "files": 1,
            "symlinks": 0,
            "skipped": 0,
            "skipped_by_reason": {"excluded": 0, "unreadable": 0},
            "hard_link_groups": 0,
            "total_size_bytes": 1,
        },
    }


def _minimal_plan(action_path: str, target_path: str | None) -> dict[str, object]:
    """Minimal DR-002 plan document with one action carrying the given paths."""
    return {
        "schema": "docmend/plan",
        "schema_version": "1.1",
        "run_id": RUN_ID,
        "generated_at": "2026-07-06T00:00:00+00:00",
        "generated_by": "docmend 0.1.0",
        "inventory_ref": {
            "path": "inventory.json",
            "run_id": RUN_ID,
            "sha256": "sha256:" + "0" * 64,
        },
        "config": DocmendConfig().model_dump(mode="json"),
        "actions": [
            {
                "action_id": f"{RUN_ID}/a1",
                "docmend_id": "019807c0-0000-7000-8000-000000000000",
                "path": action_path,
                "source_sha256": "sha256:" + "1" * 64,
                "source_size_bytes": 12,
                "operations": ["rename"],
                "target_path": target_path,
                "provenance": {"detected_encoding": None, "newline_style": "lf"},
            }
        ],
        "skips": [],
        "totals": {"actions": 1, "skips": 0},
    }


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_plan_schema__rejects_escaping_path(bad: str) -> None:
    with pytest.raises(artifacts.ArtifactError):
        artifacts.validate_artifact("plan", _minimal_plan(bad, "ok.md"))


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_plan_schema__rejects_escaping_target_path(bad: str) -> None:
    with pytest.raises(artifacts.ArtifactError):
        artifacts.validate_artifact("plan", _minimal_plan("ok.txt", bad))


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_read_plan__rejects_crafted_artifact(tmp_path: Path, bad: str) -> None:
    doc = _minimal_plan(bad, "ok.md")
    target = tmp_path / "plan.json"
    target.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(artifacts.ArtifactError):
        artifacts.read_plan(target)
