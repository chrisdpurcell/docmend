"""Automated restore drill (spec §18.6, FR-006 acceptance, IR-008) and the
NFR-006 single-file pipeline leg (scan -> plan -> apply --write).

FR-006: "restoring from manifest+backups reproduces the original corpus."
The drill runs the REAL command surface end-to-end: plan PATH -> apply --write
--backup-dir -> restore --manifest --write, then compares every byte.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from docmend.cli import app

runner = CliRunner()


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.fixture
def drill_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "corpus"
    (root / "sub").mkdir(parents=True)
    (root / "crlf.txt").write_bytes(b"alpha\r\nbeta\r\n")
    (root / "legacy.txt").write_bytes(("café " * 30).encode("windows-1252"))
    (root / "sub" / "trailing.txt").write_bytes(b"gamma  \ndelta\n")
    (root / "clean.md").write_bytes(b"# already clean\n")
    return root


def _artifact(pattern: str, out: str) -> Path:
    match = re.search(pattern, out)
    assert match is not None, out
    return Path(match.group(1))


def test_restore_drill__manifest_replay_reproduces_original_corpus(drill_corpus: Path) -> None:
    """§18.6 + FR-006 + IR-008: the full plan -> apply --write -> restore --write drill."""
    before = _snapshot(drill_corpus)

    planned = runner.invoke(app, ["plan", str(drill_corpus), "--out", "plan.json"])
    assert planned.exit_code == 0, planned.output

    applied = runner.invoke(
        app, ["apply", "plan.json", "--write", "--backup-dir", str(drill_corpus.parent / "backups")]
    )
    assert applied.exit_code == 0, applied.output
    assert _snapshot(drill_corpus) != before  # the corpus really changed
    manifest = _artifact(r"manifest: (\S+)", applied.output)

    restored = runner.invoke(app, ["restore", "--manifest", str(manifest), "--write"])
    assert restored.exit_code == 0, restored.output
    assert _snapshot(drill_corpus) == before  # IR-008: bytes match pre-apply hashes


def test_single_file_journey__scan_plan_apply_with_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR-006/G-006 acceptance: the full scan → plan → apply --write → verify
    journey over ONE file, default configuration, only the FR-005 low-risk
    opt-in — no config file, no backup infrastructure, no parallelism."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    single = tmp_path / "letter.txt"
    single.write_bytes(b"hello\r\nworld")

    # rev 0.26 IR-007/adr-0021: a loose `inventory.json` in the corpus root is
    # now a refused artifact-destination (DMR-02) — the report must land under
    # the licensed .docmend/ carve-out like the tool's own defaults do.
    scanned = runner.invoke(app, ["scan", str(single), "--report", ".docmend/inventory.json"])
    assert scanned.exit_code == 0, scanned.output
    planned = runner.invoke(
        app, ["plan", "--inventory", ".docmend/inventory.json", "--out", "plan.json"]
    )
    assert planned.exit_code == 0, planned.output
    applied = runner.invoke(app, ["apply", "plan.json", "--write", "--allow-no-backup"])
    assert applied.exit_code == 0, applied.output

    converted = tmp_path / "letter.md"
    assert converted.read_bytes() == b"hello\nworld\n"
    assert not single.exists()

    # Verify leg (MS-4): content checks over the single converted file PLUS
    # manifest reconciliation against the apply run, via the run-ID sidecar.
    run_id = _artifact(r"manifest: \.docmend/docmend-(\S+)-manifest\.jsonl", applied.output)
    verified = runner.invoke(app, ["verify", str(converted), "--run-id", str(run_id)])
    assert verified.exit_code == 0, verified.output
    assert "1 files checked, 0 findings" in verified.output


def test_drill_relative_backup_dir__restore_from_other_cwd(
    drill_corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """codex CR-005: a RELATIVE --backup-dir must still yield a manifest that
    restores from a different working directory (IR-008 standalone manifest)."""
    before = _snapshot(drill_corpus)
    runner.invoke(app, ["plan", str(drill_corpus), "--out", "plan.json"])
    applied = runner.invoke(app, ["apply", "plan.json", "--write", "--backup-dir", "backups"])
    assert applied.exit_code == 0, applied.output
    manifest = _artifact(r"manifest: (\S+)", applied.output).resolve()

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    restored = runner.invoke(app, ["restore", "--manifest", str(manifest), "--write"])
    assert restored.exit_code == 0, restored.output
    assert _snapshot(drill_corpus) == before


def test_drill_report_and_manifest_agree(drill_corpus: Path) -> None:
    """DR-003/DR-004 consistency: applied count in the report equals the number
    of applied manifest records (§17.2 Operations row)."""
    runner.invoke(app, ["plan", str(drill_corpus), "--out", "plan.json"])
    applied = runner.invoke(
        app, ["apply", "plan.json", "--write", "--backup-dir", str(drill_corpus.parent / "backups")]
    )
    report_path = _artifact(r"report: (\S+)", applied.output)
    manifest_path = _artifact(r"manifest: (\S+)", applied.output)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert report["totals"]["applied"] == sum(1 for r in records if r["result"] == "applied")
