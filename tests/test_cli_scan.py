"""`docmend scan` CLI tests (spec: IR-001, FR-012, NFR-006; §18.5 exit taxonomy).

IR-001 acceptance: the command exists, exits 0 on success, and writes the DR-001
artifact. Also covered: the OQ-034 `.docmend/` default output convention, the
OQ-029 replace (never append) semantics of --include/--exclude, and the exit-code
taxonomy (1 = unreadable-skip findings, 2 = input error).
"""

import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

from docmend.artifacts import read_inventory
from docmend.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_logging() -> Iterator[None]:
    """scan configures real handlers on the root logger; restore them per test."""
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    yield
    for handler in root.handlers:
        if handler not in saved:
            handler.close()
    root.handlers = saved
    root.setLevel(saved_level)
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


@pytest.fixture
def corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A small corpus, with the CWD moved to tmp so .docmend/ lands in the sandbox."""
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "corpus"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("alpha\n")
    (root / "b.md").write_text("# beta\n")
    (root / "sub" / "c.txt").write_bytes(b"gamma\r\n")
    return root


class TestScanCommand:
    def test_scan__exits_zero_and_writes_artifact(self, corpus: Path) -> None:
        """spec: IR-001 — command exists, exit 0, DR-001 artifact written."""
        result = runner.invoke(app, ["scan", str(corpus)])
        assert result.exit_code == 0, result.output
        artifacts = list(Path(".docmend").glob("docmend-run_*-inventory.json"))
        assert len(artifacts) == 1
        inventory = read_inventory(artifacts[0])
        assert {record.path for record in inventory.files} == {"a.txt", "b.md", "sub/c.txt"}
        assert "inventory:" in result.output

    def test_scan__writes_run_log_next_to_artifact(self, corpus: Path) -> None:
        """OQ-034/OQ-017: the run-ID keys both the artifact and the JSONL log."""
        assert runner.invoke(app, ["scan", str(corpus)]).exit_code == 0
        artifact = next(Path(".docmend").glob("docmend-run_*-inventory.json"))
        run_id = artifact.name.removeprefix("docmend-").removesuffix("-inventory.json")
        log_file = Path(".docmend") / f"docmend-{run_id}.jsonl"
        assert log_file.is_file()
        events = [json.loads(line) for line in log_file.read_text().splitlines()]
        assert all(event["run_id"] == run_id for event in events)

    def test_report_flag__overrides_artifact_path(self, corpus: Path, tmp_path: Path) -> None:
        """spec: IR-001 — `scan PATH --report FILE` contract."""
        target = tmp_path / "custom" / "inv.json"
        result = runner.invoke(app, ["scan", str(corpus), "--report", str(target)])
        assert result.exit_code == 0
        assert read_inventory(target).totals.files == 3

    def test_single_file_path__first_class(self, corpus: Path) -> None:
        """spec: NFR-006 — a single file is a valid PATH with default config."""
        result = runner.invoke(app, ["scan", str(corpus / "a.txt")])
        assert result.exit_code == 0
        artifact = next(Path(".docmend").glob("docmend-run_*-inventory.json"))
        inventory = read_inventory(artifact)
        assert [record.path for record in inventory.files] == ["a.txt"]


class TestScanFilters:
    def test_include_flag__replaces_config_list(self, corpus: Path) -> None:
        """spec: FR-012 (OQ-029) — --include REPLACES paths.include, never appends."""
        (corpus / "docmend.toml").write_text('[paths]\ninclude = ["**/*.txt"]\n')
        result = runner.invoke(
            app,
            [
                "scan",
                str(corpus),
                "--config",
                str(corpus / "docmend.toml"),
                "--include",
                "**/*.md",
            ],
        )
        assert result.exit_code == 0
        artifact = next(Path(".docmend").glob("docmend-run_*-inventory.json"))
        inventory = read_inventory(artifact)
        assert [record.path for record in inventory.files] == ["b.md"]
        assert inventory.scan_config.include == ["**/*.md"]

    def test_exclude_flag__records_skips(self, corpus: Path) -> None:
        result = runner.invoke(app, ["scan", str(corpus), "--exclude", "**/sub/**"])
        assert result.exit_code == 0
        artifact = next(Path(".docmend").glob("docmend-run_*-inventory.json"))
        inventory = read_inventory(artifact)
        assert [record.path for record in inventory.skipped] == ["sub/c.txt"]


class TestScanExitCodes:
    def test_missing_path__usage_error_exit_2(self, corpus: Path) -> None:
        """§18.5: nonexistent PATH is an input error."""
        result = runner.invoke(app, ["scan", str(corpus / "nope")])
        assert result.exit_code == 2

    def test_invalid_config__exit_2(self, corpus: Path) -> None:
        """spec: IR-001/IR-006 — a bad config file is an input error, exit 2."""
        bad = corpus / "bad.toml"
        bad.write_text("[paths]\nnonsense = true\n")
        result = runner.invoke(app, ["scan", str(corpus), "--config", str(bad)])
        assert result.exit_code == 2

    @pytest.mark.skipif(os.geteuid() == 0, reason="permission bits do not bind root")
    def test_unreadable_file__findings_exit_1(self, corpus: Path) -> None:
        """§18.5: the scan completes but reports findings (ERR-007) — exit 1."""
        locked = corpus / "locked.txt"
        locked.write_text("secret\n")
        locked.chmod(0)
        try:
            result = runner.invoke(app, ["scan", str(corpus)])
        finally:
            locked.chmod(0o644)
        assert result.exit_code == 1
        assert "unreadable 1" in result.output
