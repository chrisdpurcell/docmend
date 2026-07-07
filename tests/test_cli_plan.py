"""`docmend plan` CLI tests (IR-002, FR-018 plan half; §18.5 exit taxonomy).

IR-002 acceptance: PATH shorthand scans-then-plans under one run-ID; --inventory
consumes an existing DR-001 artifact; exactly one of the two is required. Also
covered: the DR-002 artifact default path, OQ-029 filter-flag replace semantics,
the exit-code taxonomy (1 = findings, 2 = input error) including the
--fail-on-low-confidence-encoding hardening (AW-003), and NFR-006's single-file
PATH plan leg.
"""

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

from docmend.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_logging() -> Iterator[None]:
    """plan configures real handlers on the root logger; restore them per test."""
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


def make_corpus(root: Path) -> None:
    (root / "a.txt").write_bytes(b"body\r\n")
    (root / "b.md").write_bytes(b"clean\n")


class TestPlanCommand:
    def test_path_shorthand__scans_then_plans_with_inventory_ref(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IR-002: raw PATH performs the scan first and records the inventory reference."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        make_corpus(corpus)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["plan", str(corpus)])
        assert result.exit_code == 0, result.output
        artifact_dir = tmp_path / ".docmend"
        plans = list(artifact_dir.glob("docmend-*-plan.json"))
        inventories = list(artifact_dir.glob("docmend-*-inventory.json"))
        assert len(plans) == 1 and len(inventories) == 1
        document = json.loads(plans[0].read_text())
        assert document["inventory_ref"]["path"] == str(inventories[0])
        assert document["inventory_ref"]["run_id"] == document["run_id"]

    def test_inventory_flag__consumes_existing_artifact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IR-002: --inventory consumes a pre-existing DR-001 artifact instead of scanning."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        make_corpus(corpus)
        monkeypatch.chdir(tmp_path)
        scan_result = runner.invoke(app, ["scan", str(corpus)])
        assert scan_result.exit_code == 0
        inventory_path = next((tmp_path / ".docmend").glob("docmend-*-inventory.json"))
        result = runner.invoke(
            app, ["plan", "--inventory", str(inventory_path), "--out", str(tmp_path / "plan.json")]
        )
        assert result.exit_code == 0, result.output
        document = json.loads((tmp_path / "plan.json").read_text())
        assert document["inventory_ref"]["path"] == str(inventory_path)

    def test_path_and_inventory_together__usage_error(self, tmp_path: Path) -> None:
        """IR-002: PATH and --inventory are mutually exclusive."""
        result = runner.invoke(app, ["plan", str(tmp_path), "--inventory", "x.json"])
        assert result.exit_code == 2

    def test_neither_path_nor_inventory__usage_error(self) -> None:
        """IR-002: exactly one of PATH or --inventory is required."""
        result = runner.invoke(app, ["plan"])
        assert result.exit_code == 2

    def test_corrupt_inventory__err_008_exit_2(self, tmp_path: Path) -> None:
        """ERR-008: invalid inventory refuses plan with exit 2."""
        bad = tmp_path / "inv.json"
        bad.write_text("{not json")
        result = runner.invoke(app, ["plan", "--inventory", str(bad)])
        assert result.exit_code == 2

    def test_config_error__exit_2(self, tmp_path: Path) -> None:
        """IR-002: exits non-zero on config errors."""
        (tmp_path / "bad.toml").write_text("[unknown]\nkey = 1\n")
        result = runner.invoke(app, ["plan", str(tmp_path), "--config", str(tmp_path / "bad.toml")])
        assert result.exit_code == 2

    def test_collision_policy_fail__exit_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-011: fail policy -> non-zero abort, artifact still written (§8.5)."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "foo.txt").write_bytes(b"t\r\n")
        (corpus / "foo.md").write_bytes(b"m\n")
        (tmp_path / "docmend.toml").write_text('[rename]\non_collision = "fail"\n')
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["plan", str(corpus)])
        assert result.exit_code == 1
        assert list((tmp_path / ".docmend").glob("docmend-*-plan.json"))

    def test_fail_on_low_confidence__exit_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AW-003: hardened run aborts non-zero on encoding-gate skips."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "short.txt").write_bytes(b"mostly ascii \xe9\xe8")
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["plan", str(corpus), "--fail-on-low-confidence-encoding"])
        assert result.exit_code == 1

    def test_filter_flags__replace_config_lists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-012/OQ-029: --include replaces, never appends, at plan too."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        make_corpus(corpus)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app, ["plan", str(corpus), "--include", "*.md", "--out", str(tmp_path / "p.json")]
        )
        assert result.exit_code == 0
        document = json.loads((tmp_path / "p.json").read_text())
        assert all(a["path"].endswith(".md") for a in document["actions"])

    def test_single_file_path__first_class(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-006: a single file is a valid PATH with default config (plan leg)."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        make_corpus(corpus)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["plan", str(corpus / "a.txt")])
        assert result.exit_code == 0, result.output
        plans = list((tmp_path / ".docmend").glob("docmend-*-plan.json"))
        assert len(plans) == 1
        document = json.loads(plans[0].read_text())
        assert [action["path"] for action in document["actions"]] == ["a.txt"]
