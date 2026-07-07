"""Scan-config detection provenance (DR-001; MS-2 final-review Important #1).

The inventory must record whether encoding detection ran at scan (and which
detector), so a later plan run with a different config cannot misread
'detected: null' as binary-suspect when detection simply never ran (FR-007,
FR-015 — the skip must be low-confidence-encoding, which
--fail-on-low-confidence-encoding counts).
"""

from importlib.metadata import version
from pathlib import Path

from docmend import discovery, planning
from docmend.config import DocmendConfig, EncodingConfig
from docmend.plan import ArtifactRef

RUN_ID = "run_20260706T000000Z_00003a"
GENERATED_AT = "2026-07-06T00:00:00+00:00"


def _scan(root: Path, config: DocmendConfig):
    return discovery.scan(root, config, run_id=RUN_ID, generated_at=GENERATED_AT)


def _ref() -> ArtifactRef:
    return ArtifactRef(path="inv.json", run_id=RUN_ID, sha256="sha256:" + "0" * 64)


def _legacy_corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    # windows-1252 bytes, invalid as UTF-8, no BOM, no NUL — the legacy rung's case.
    (root / "legacy.txt").write_bytes(("café " * 30).encode("windows-1252"))
    return root


def test_scan_records_detection_provenance__enabled(tmp_path: Path) -> None:
    inventory = _scan(_legacy_corpus(tmp_path), DocmendConfig())
    assert inventory.scan_config.encoding_detect is True
    assert inventory.scan_config.detector == f"charset-normalizer {version('charset-normalizer')}"


def test_scan_records_detection_provenance__disabled(tmp_path: Path) -> None:
    config = DocmendConfig(encoding=EncodingConfig(detect=False))
    inventory = _scan(_legacy_corpus(tmp_path), config)
    assert inventory.scan_config.encoding_detect is False
    assert inventory.scan_config.detector is None


def test_plan_over_detect_off_inventory__skips_low_confidence_not_binary(tmp_path: Path) -> None:
    """FR-007/FR-015: detection-not-run is a low-confidence skip, never binary-suspect."""
    scan_config = DocmendConfig(encoding=EncodingConfig(detect=False))
    inventory = _scan(_legacy_corpus(tmp_path), scan_config)
    # Plan with detection ENABLED — the cross-config case the review flagged.
    plan = planning.build_plan(
        inventory, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT, inventory_ref=_ref()
    )
    (skip,) = plan.skips
    assert skip.reason == "low-confidence-encoding"
    assert skip.detail == "encoding detection was not run at scan"
