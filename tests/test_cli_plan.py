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
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

from docmend import cli, lock
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


@pytest.fixture(autouse=True)
def isolate_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """plan now acquires the OQ-027 run lock; keep its state dir out of the
    real $XDG_STATE_HOME/~/.local/state so tests never touch developer state."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))


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

    @pytest.mark.skipif(os.geteuid() == 0, reason="permission bits do not bind root")
    def test_unreadable_file_in_scan_step__path_shorthand_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """§18.5: the PATH shorthand's own scan step surfaces unreadable findings too.

        `scan corpus` over this same tree exits 1 (test_cli_scan.py's
        equivalent); `plan corpus` must not silently exit 0 just because the
        unreadable file lives in the inventory, not plan.skips.
        """
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        make_corpus(corpus)
        locked = corpus / "locked.txt"
        locked.write_text("secret\n")
        locked.chmod(0)
        monkeypatch.chdir(tmp_path)
        try:
            result = runner.invoke(app, ["plan", str(corpus)])
        finally:
            locked.chmod(0o644)
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
        # b.md is a no-op (already clean) so it appears in neither actions nor
        # skips (FR-017's plan half) — meaning the weaker check this replaces
        # (every action ends in .md) passed vacuously over an empty list. The
        # inventory the PATH shorthand itself wrote is the positive proof that
        # --include replaced, not appended, paths.include: a.txt was never
        # even discovered.
        inventory_path = next((tmp_path / ".docmend").glob("docmend-*-inventory.json"))
        inventory = json.loads(inventory_path.read_text())
        assert [f["path"] for f in inventory["files"]] == ["b.md"]
        assert document["actions"] == []
        assert document["config"]["paths"]["include"] == ["*.md"]

    def test_path_not_exists__exit_2(self, tmp_path: Path) -> None:
        """§18.5: a PATH that doesn't exist is an input error, not a scan attempt."""
        result = runner.invoke(app, ["plan", str(tmp_path / "nope")])
        assert result.exit_code == 2
        assert "no such file or directory" in result.output

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


class TestPlanLock:
    def test_lock_held_by_other_run__refuses_exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OQ-027/AW-005: a second live run against the same target refuses,
        naming the holder, exit 3 — `isolate_state_dir` already points
        $XDG_STATE_HOME at tmp_path, so pre-acquiring here contends for real."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        make_corpus(corpus)
        monkeypatch.chdir(tmp_path)
        # No explicit state_dir: XDG_STATE_HOME is already pointed at tmp_path
        # by the isolate_state_dir fixture, matching the default `plan` uses.
        held = lock.acquire(corpus, run_id="run_20260706T000000Z_00004b", command="apply")
        try:
            result = runner.invoke(app, ["plan", str(corpus)])
            assert result.exit_code == 3
            assert "run_20260706T000000Z_00004b" in result.output
        finally:
            held.release()

    def test_lock_unavailable_oserror__proceeds_without_lock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OQ-036 posture: `plan` is read-only, so a lock the tool can't even
        create (e.g. an unwritable state dir) degrades to a warning, not a
        refusal — the run still completes and exits 0."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        make_corpus(corpus)
        monkeypatch.chdir(tmp_path)

        def _raise_oserror(*_args: object, **_kwargs: object) -> lock.RunLock:
            raise OSError("state dir unwritable")

        monkeypatch.setattr(cli.lock, "acquire", _raise_oserror)
        result = runner.invoke(app, ["plan", str(corpus)])
        assert result.exit_code == 0, result.output
        assert "run lock unavailable" in result.output


class TestPlanArtifactGuard:
    """rev 0.26 IR-007 / adr-0021 / DMR-02 wiring for both plan branches."""

    def test_out_inside_corpus__refused_exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        victim = corpus / "victim.txt"
        victim.write_bytes(b"corpus document\n")
        result = runner.invoke(app, ["plan", str(corpus), "--out", str(victim)])
        assert result.exit_code == 3
        assert "artifact-destination" in result.output
        assert victim.read_bytes() == b"corpus document\n"

    def test_out_aliasing_inventory_input__refused_exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A destination outside the corpus can still corrupt the pipeline by
        aliasing this invocation's own input (adr-0021)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "doc.txt").write_text("clean\n")
        inventory_path = tmp_path / "inventory.json"
        scan_result = runner.invoke(app, ["scan", str(corpus), "--report", str(inventory_path)])
        assert scan_result.exit_code == 0, scan_result.output
        result = runner.invoke(
            app,
            ["plan", "--inventory", str(inventory_path), "--out", str(inventory_path)],
        )
        assert result.exit_code == 3
        assert "artifact-destination" in result.output


class TestTimeoutExit:
    def test_plan_with_timeout_skip__partial_result_exit_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """2026-07-10 review: a content-pass watchdog timeout is a PARTIAL
        plan — the same finding class as unreadable (exit 1)."""
        import docmend.planning as planning_module
        from docmend.watchdog import PerFileTimeoutError

        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "slow.txt").write_bytes(b"slow body\r\n")

        def timing_out(*args: object, **kwargs: object) -> object:
            raise PerFileTimeoutError(0.0)

        monkeypatch.setattr(planning_module, "decode_source", timing_out)
        result = runner.invoke(app, ["plan", str(corpus)])

        assert result.exit_code == 1, result.output
        assert "timeout" in result.output
