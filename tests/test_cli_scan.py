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

from docmend import cli, lock
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


@pytest.fixture(autouse=True)
def isolate_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))


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

    def test_legacy_parallel_config__exit_2_before_scan(
        self, corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_path / "legacy.toml"
        config_path.write_text("[parallel]\nenabled = false\n", encoding="utf-8")

        def scan_should_not_run(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("legacy configuration reached discovery.scan")

        monkeypatch.setattr(cli.discovery, "scan", scan_should_not_run)
        result = runner.invoke(
            app,
            ["scan", str(corpus), "--config", str(config_path)],
        )

        assert result.exit_code == 2, result.output
        assert "parallel execution never shipped" in result.output
        assert not list(Path(".docmend").glob("*-inventory.json"))


class TestScanLock:
    def test_same_root_lock_contention__exit_3(self, corpus: Path) -> None:
        held = lock.acquire(corpus.resolve(), run_id="run_20260711T150000Z_000055", command="apply")
        try:
            result = runner.invoke(app, ["scan", str(corpus)])
        finally:
            held.release()
        assert result.exit_code == 3, result.output
        assert "another docmend run holds the lock" in result.output

    def test_lock_creation_failure__warns_and_continues(
        self, corpus: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse_lock(*_args: object, **_kwargs: object) -> lock.RunLock:
            raise PermissionError("state directory is unwritable")

        monkeypatch.setattr(cli.lock, "acquire", refuse_lock)
        result = runner.invoke(app, ["scan", str(corpus)])
        assert result.exit_code == 0, result.output
        assert "run lock unavailable" in result.output


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

    def test_exclude_flag__file_pattern_records_skips(self, corpus: Path) -> None:
        result = runner.invoke(app, ["scan", str(corpus), "--exclude", "**/c.txt"])
        assert result.exit_code == 0
        artifact = next(Path(".docmend").glob("docmend-run_*-inventory.json"))
        inventory = read_inventory(artifact)
        assert [record.path for record in inventory.skipped] == ["sub/c.txt"]

    def test_exclude_flag__directory_pattern_prunes(self, corpus: Path) -> None:
        """Directory excludes prune at the walk: no files and no per-file skip
        records beneath the excluded directory (FR-012 selection unchanged)."""
        result = runner.invoke(app, ["scan", str(corpus), "--exclude", "**/sub/**"])
        assert result.exit_code == 0
        artifact = next(Path(".docmend").glob("docmend-run_*-inventory.json"))
        inventory = read_inventory(artifact)
        assert all(not record.path.startswith("sub/") for record in inventory.files)
        assert inventory.skipped == []


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


class TestScanArtifactGuard:
    """rev 0.26 IR-007 / adr-0021 / DMR-02: unsafe --report destinations are
    refused at exit 3 BEFORE the walk; the OQ-034 default keeps working."""

    def test_report_inside_corpus__refused_exit_3_source_intact(self, corpus: Path) -> None:
        victim = corpus / "a.txt"
        before = victim.read_bytes()
        result = runner.invoke(app, ["scan", str(corpus), "--report", str(victim)])
        assert result.exit_code == 3
        assert "artifact-destination" in result.output
        assert victim.read_bytes() == before

    def test_default_docmend_root__still_works(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OQ-034/NFR-006: the zero-setup default (`scan .` writing under
        ./.docmend/) is binding behavior — the carve-out must keep it."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "doc.txt").write_text("clean\n")
        result = runner.invoke(app, ["scan", "."])
        assert result.exit_code == 0, result.output
        assert list(Path(".docmend").glob("docmend-run_*-inventory.json"))

    def test_docmend_exclusion_removed__default_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The carve-out is licensed by the exclusion (adr-0021): --exclude
        REPLACES the exclude set (OQ-029), so a set without .docmend/
        withdraws the license and the default in-corpus destination refuses."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "doc.txt").write_text("clean\n")
        result = runner.invoke(app, ["scan", ".", "--exclude", "*.bin"])
        assert result.exit_code == 3
        assert "artifact-destination" in result.output
        assert not list(Path(".docmend").glob("docmend-run_*-inventory.json"))

    def test_negated_default_destination__refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """plan-review F2: a negation re-including the exact inventory
        destination withdraws that one destination's license even though the
        rest of .docmend/ stays excluded."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "doc.txt").write_text("clean\n")
        result = runner.invoke(
            app,
            [
                "scan",
                ".",
                "--exclude",
                "**/.docmend/**",
                "--exclude",
                "!.docmend/docmend-*-inventory.json",
            ],
        )
        assert result.exit_code == 3
        assert "artifact-destination" in result.output
        assert not list(Path(".docmend").glob("docmend-run_*-inventory.json"))


class TestTimeoutExit:
    def test_scan_with_timeout_skip__partial_result_exit_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """2026-07-10 review: a watchdog timeout is a PARTIAL scan — the same
        finding class as an unreadable file (exit 1), never a silent success."""
        import docmend.discovery as discovery_module
        from docmend.watchdog import PerFileTimeoutError

        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "slow.txt").write_bytes(b"slow body\r\n")

        real_classify = discovery_module.classify_file

        def timing_out(*args: object, **kwargs: object) -> object:
            raise PerFileTimeoutError(0.0)

        monkeypatch.setattr(discovery_module, "classify_file", timing_out)
        result = runner.invoke(app, ["scan", str(corpus)])
        monkeypatch.setattr(discovery_module, "classify_file", real_classify)

        assert result.exit_code == 1, result.output
        assert "timeout 1" in result.output
