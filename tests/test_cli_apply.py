"""`docmend apply` CLI tests (IR-003, IR-005, FR-004, FR-005, FR-018, NFR-004,
AW-005; §18.5 exit taxonomy).

IR-003 acceptance: behaviors per FR-003-FR-006; exits non-zero when the safety
gate refuses. NFR-004 acceptance: out-of-the-box invocation cannot mutate.
"""

import hashlib
import json
import logging
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

import docmend.cli as cli_module
from docmend import lock
from docmend.cli import app
from docmend.report import Report

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_logging() -> Iterator[None]:
    """apply configures real handlers on the root logger; restore them per test."""
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
    """apply acquires the OQ-027 run lock; keep its state dir out of the real
    $XDG_STATE_HOME/~/.local/state so tests never touch developer state."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))


def make_corpus(root: Path) -> None:
    """A small "dirty" corpus: a.txt and c.txt each need a CRLF->LF normalize
    plus the default txt_to_md rename (two operations = a content rewrite,
    not a pure rename); b.md is already clean and produces no action."""
    root.mkdir(exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha body\r\n")
    (root / "c.txt").write_bytes(b"charlie body\r\n")
    (root / "b.md").write_bytes(b"clean\n")


def _hashes(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _make_plan(corpus: Path, *, out: Path = Path("plan.json")) -> Path:
    """Shell `plan <corpus> --out plan.json` via CliRunner; config auto-discovery
    (./docmend.toml in the CWD, if a test wrote one) applies exactly as it does
    for a real invocation."""
    result = runner.invoke(app, ["plan", str(corpus), "--out", str(out)])
    assert result.exit_code in (0, 1), result.output
    return out


class TestApplyDryRunDefault:
    def test_apply_default__dry_run_writes_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-004 acceptance test: `apply PLAN` with no flags at all is the
        out-of-the-box invocation — it must be impossible for it to mutate the
        corpus, regardless of what the plan contains (FR-004)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        before = _hashes(corpus)

        result = runner.invoke(app, ["apply", str(plan_path)])

        assert result.exit_code == 0, result.output
        assert _hashes(corpus) == before
        assert not list(tmp_path.rglob("*-manifest.jsonl"))
        reports = list((tmp_path / ".docmend").glob("docmend-*-report.json"))
        assert len(reports) == 1
        document = json.loads(reports[0].read_text())
        assert document["dry_run"] is True
        assert "would-apply" in result.output

    def test_apply_plan_1_x__exit_2_before_lock_report_or_mutation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        document = json.loads(plan_path.read_text(encoding="utf-8"))
        document["schema_version"] = "1.2"
        document["config"]["parallel"] = {
            "enabled": False,
            "model": "process",
            "workers": "auto",
            "start_method": "forkserver",
            "chunksize": "auto",
            "maxtasksperchild": None,
        }
        plan_path.write_text(json.dumps(document), encoding="utf-8")
        before = _hashes(corpus)

        def lock_should_not_run(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("legacy plan reached the run lock")

        monkeypatch.setattr(cli_module, "_acquire_run_lock_strict", lock_should_not_run)
        result = runner.invoke(app, ["apply", str(plan_path)])

        assert result.exit_code == 2, result.output
        assert "plan schema 1.2" in result.output
        assert "regenerate" in result.output
        assert _hashes(corpus) == before
        assert not list((tmp_path / ".docmend").glob("*-report.json"))
        assert not list((tmp_path / ".docmend").glob("*-manifest.jsonl"))

    def test_apply_dry_run_overwrite_with_configured_backup_dir__no_backup_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """codex CR-001/OQ-014: config alone can never enable writes — even an
        `on_collision = "overwrite"` + `write.backup_dir` snapshot must not
        cause a dry-run apply (no --write) to create the backup destination."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "a.txt").write_bytes(b"alpha body\r\n")
        (corpus / "a.md").write_bytes(b"pre-existing target\n")
        backup_dir = tmp_path / "configured-backup"
        (tmp_path / "docmend.toml").write_text(
            f'[rename]\non_collision = "overwrite"\n\n[write]\nbackup_dir = "{backup_dir.as_posix()}"\n'
        )
        plan_path = _make_plan(corpus)

        result = runner.invoke(app, ["apply", str(plan_path)])

        assert result.exit_code == 0, result.output
        assert not backup_dir.exists()


class TestApplyFlagConflicts:
    def test_apply_write_and_dry_run__mutually_exclusive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IR-003: --write and --dry-run are mutually exclusive (exit 2)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)

        result = runner.invoke(app, ["apply", str(plan_path), "--write", "--dry-run"])
        assert result.exit_code == 2, result.output

    def test_apply_write_and_global_dry_run__mutually_exclusive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IR-003/IR-005: the global -n IS --dry-run, so it conflicts with
        --write too — this is where -n gains its write-capable effect."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)

        result = runner.invoke(app, ["-n", "apply", str(plan_path), "--write"])
        assert result.exit_code == 2, result.output


class TestApplyGate:
    def test_apply_write_without_strategy__gate_refuses_exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-005: a content-rewrite plan with --write and no byte-preserving
        strategy is refused by the gate (exit 3); the library stays untouched
        and the refusal report carries zero outcomes (decision 8)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        before = _hashes(corpus)

        result = runner.invoke(app, ["apply", str(plan_path), "--write"])

        assert result.exit_code == 3, result.output
        assert "refused [" in result.output
        assert _hashes(corpus) == before
        reports = list((tmp_path / ".docmend").glob("docmend-*-report.json"))
        assert len(reports) == 1
        document = json.loads(reports[0].read_text())
        assert document["outcomes"] == []
        assert document["totals"] == {
            "applied": 0,
            "would_apply": 0,
            "skipped": 0,
            "failed": 0,
            "not_attempted": 0,
        }
        assert document["prior_attempt"] is None
        assert document["manifest_sha256"] is None  # refused: nothing mutated

    def test_apply_locked_target__exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AW-005: a second live run against the already-locked target refuses,
        exit 3 — apply must REFUSE, unlike plan's warn-and-proceed posture."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        held = lock.acquire(corpus, run_id="run_20260706T000000Z_00004b", command="apply")
        try:
            result = runner.invoke(app, ["apply", str(plan_path)])
            assert result.exit_code == 3, result.output
            assert "run_20260706T000000Z_00004b" in result.output
        finally:
            held.release()


class TestApplyWrites:
    def test_apply_write_with_backup_dir__mutates_and_reports(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-005/FR-006/FR-018: --write --backup-dir converts the corpus,
        the report totals reconcile with its outcomes, the manifest exists,
        and the console summary line names the applied count."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        backup_dir = tmp_path / "backups"

        result = runner.invoke(
            app, ["apply", str(plan_path), "--write", "--backup-dir", str(backup_dir)]
        )

        assert result.exit_code == 0, result.output
        assert "applied" in result.output
        assert not (corpus / "a.txt").exists()
        assert (corpus / "a.md").read_bytes() == b"alpha body\n"
        assert not (corpus / "c.txt").exists()
        assert (corpus / "c.md").exists()
        reports = list((tmp_path / ".docmend").glob("docmend-*-report.json"))
        assert len(reports) == 1
        document = json.loads(reports[0].read_text())
        counts = Counter(outcome["status"] for outcome in document["outcomes"])
        assert counts.get("applied", 0) == document["totals"]["applied"] == 2
        manifests = list((tmp_path / ".docmend").glob("docmend-*-manifest.jsonl"))
        assert len(manifests) == 1
        assert f"manifest: {Path('.docmend') / manifests[0].name}" in result.output

    def test_apply_single_file_opt_in__no_backup_needed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-006/G-006: a single-action plan may opt into --allow-no-backup
        instead of a full byte-preserving strategy (FR-005 low-risk carve-out)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "solo.txt").write_bytes(b"solo body\r\n")
        plan_path = _make_plan(corpus)

        result = runner.invoke(app, ["apply", str(plan_path), "--write", "--allow-no-backup"])

        assert result.exit_code == 0, result.output
        assert (corpus / "solo.md").exists()
        assert not (corpus / "solo.txt").exists()

    def test_apply_findings__exit_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """FR-003: a file mutated after planning fails its re-hash (AW-004),
        skipping just that action (exit 1) while the rest of the run proceeds."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        (corpus / "a.txt").write_bytes(b"mutated after planning\r\n")
        backup_dir = tmp_path / "backups"

        result = runner.invoke(
            app, ["apply", str(plan_path), "--write", "--backup-dir", str(backup_dir)]
        )

        assert result.exit_code == 1, result.output
        # Stale-hash skip: a.txt is left exactly as mutated, never renamed.
        assert (corpus / "a.txt").read_bytes() == b"mutated after planning\r\n"
        # The unaffected action still proceeds.
        assert (corpus / "c.md").exists()
        assert not (corpus / "c.txt").exists()


class TestApplyInputErrors:
    def test_apply_invalid_plan__exit_2(self, tmp_path: Path) -> None:
        """ERR-006: a JSON file that fails plan schema validation is an input error."""
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")

        result = runner.invoke(app, ["apply", str(bad)])
        assert result.exit_code == 2, result.output

    def test_apply_plan_without_source_root__exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Decision 3: a pre-1.1 plan (no source_root) cannot be applied — the
        error tells the operator to regenerate rather than guessing a root."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        document = json.loads(plan_path.read_text())
        del document["source_root"]
        plan_path.write_text(json.dumps(document))

        result = runner.invoke(app, ["apply", str(plan_path)])

        assert result.exit_code == 2, result.output
        assert "regenerate" in result.output


class TestApplyReportAndVerbosity:
    def test_apply_report_override__honored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--report FILE overrides the default .docmend/ path."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        custom = tmp_path / "custom-report.json"

        result = runner.invoke(app, ["apply", str(plan_path), "--report", str(custom)])

        assert result.exit_code == 0, result.output
        assert custom.exists()
        assert f"report: {custom}" in result.output

    def test_apply_verbose__per_file_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IR-005/OQ-017: -v raises the console sink to INFO, surfacing the
        per-file "apply outcome" line; -q suppresses it entirely."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)

        verbose_result = runner.invoke(app, ["-v", "apply", str(plan_path)])
        assert verbose_result.exit_code == 0, verbose_result.output
        assert "apply outcome" in verbose_result.output

        quiet_result = runner.invoke(app, ["-q", "apply", str(plan_path)])
        assert quiet_result.exit_code == 0, quiet_result.output
        assert "apply outcome" not in quiet_result.output


class TestApplyLogContent:
    """NFR-003: a run is diagnosable from its per-run JSONL log alone. The MS-0
    framework tests (tests/test_observability.py) assert the field schema in
    isolation; this asserts the log *content* an integration run actually
    produces — run-ID correlation, per-file outcome events, and level fields."""

    def test_apply_write__jsonl_log_correlates_and_records_per_file_outcomes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        backup_dir = tmp_path / "backups"

        result = runner.invoke(
            app, ["apply", str(plan_path), "--write", "--backup-dir", str(backup_dir)]
        )
        assert result.exit_code == 0, result.output

        artifact_dir = tmp_path / ".docmend"
        [report] = list(artifact_dir.glob("docmend-*-report.json"))
        run_id = report.name.removeprefix("docmend-").removesuffix("-report.json")

        # The per-run JSONL log is named by the SAME run_id as the artifacts —
        # that filename correlation is what makes a log findable from a report.
        log_path = artifact_dir / f"docmend-{run_id}.jsonl"
        assert log_path.is_file()
        assert (artifact_dir / f"docmend-{run_id}-manifest.jsonl").is_file()

        records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        assert records, "apply produced no structured log records"

        # run_id is bound into every line, and every line carries a level — the
        # two structured fields NFR-003/OQ-017 require for after-the-fact triage.
        assert {record["run_id"] for record in records} == {run_id}
        assert all("level" in record for record in records)

        # Per-file outcome events: one INFO 'apply outcome' per planned action,
        # each naming the file and its status — the per-file audit trail.
        outcomes = [record for record in records if record.get("event") == "apply outcome"]
        assert {"a.txt", "c.txt"} <= {record["path"] for record in outcomes}
        assert all(record["level"] == "INFO" for record in outcomes)
        assert {record["status"] for record in outcomes} == {"applied"}


class TestPartialUndoWarning:
    """Issue #15: an apply that satisfies the gate WITHOUT tool backups leaves a
    manifest that can undo renames but not content rewrites — the operator must
    hear that at apply time, not discover it at restore time."""

    def test_write_with_external_preservation__warns_renames_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)  # a.txt/c.txt: CRLF -> LF content rewrites
        plan_path = _make_plan(corpus)

        result = runner.invoke(
            app, ["apply", str(plan_path), "--write", "--preserved-by", "external"]
        )

        assert result.exit_code == 0, result.output
        assert "undo only its pure renames" in result.output
        assert "2 action(s) with" in result.output

    def test_write_with_backup_dir__no_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)

        result = runner.invoke(
            app, ["apply", str(plan_path), "--write", "--backup-dir", str(tmp_path / "backups")]
        )

        assert result.exit_code == 0, result.output
        assert "pure renames" not in result.output

    def test_rename_only_run__no_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rename-only manifest IS fully restorable without backups — warning
        there would be noise."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "clean.txt").write_bytes(b"already clean\n")  # rename-only action
        plan_path = _make_plan(corpus)

        result = runner.invoke(app, ["apply", str(plan_path), "--write"])

        assert result.exit_code == 0, result.output
        assert "pure renames" not in result.output

    def test_dry_run__no_warning(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Dry runs mutate nothing and record nothing — nothing to warn about."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)

        result = runner.invoke(app, ["apply", str(plan_path)])

        assert result.exit_code == 0, result.output
        assert "pure renames" not in result.output


class TestApplyArtifactGuard:
    """rev 0.26 IR-007 / adr-0021 / DMR-02: apply's report path is guarded
    before the gate, and the report finalizes while the run lock is held."""

    def test_report_inside_corpus__refused_exit_3_before_gate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`apply --report <corpus file>` used to clobber the file even on a
        dry run and even when the write was later refused (DMR-02 repro)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        victim = corpus / "b.md"
        before = victim.read_bytes()
        result = runner.invoke(app, ["apply", str(plan_path), "--report", str(victim)])
        assert result.exit_code == 3
        assert "artifact-destination" in result.output
        assert victim.read_bytes() == before

    def test_resume_run_id_derived_manifest__aliases_as_input_refused_exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The manifest path --resume-run-id derives
        (.docmend/docmend-<ID>-manifest.jsonl) must count as an input artifact
        for the DMR-02 guard, same as an explicit --resume-manifest path —
        otherwise --report could be pointed at it and clobber the very
        manifest apply is about to reconcile against.

        guard_artifact_destination's alias check itself compares resolved
        paths only and does not require the input artifact to exist. But
        `_read_resume_records` (adr-0006) runs BEFORE the guard in apply's own
        pipeline and hard-requires the manifest to be readable (ERR-006, exit
        2) — so an EMPTY (but present) manifest file is created here to reach
        the guard at all; a --resume-run-id naming a manifest that has never
        been written yet is not a reachable state through the CLI.
        """
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        derived_manifest = Path(".docmend") / "docmend-X-manifest.jsonl"
        derived_manifest.parent.mkdir(parents=True, exist_ok=True)
        # 2.0: a readable manifest starts with its header; a header-only file
        # (valid empty set) with the matching root reaches the guard.
        from tests.helpers.manifest2 import header_doc, write_set

        write_set(
            derived_manifest,
            header_doc(
                source_root=str(corpus.resolve()),
                plan_sha256=f"sha256:{hashlib.sha256(plan_path.read_bytes()).hexdigest()}",
            ),
        )
        result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--resume-run-id",
                "X",
                "--report",
                str(derived_manifest),
            ],
        )
        assert result.exit_code == 3, result.output
        assert "artifact-destination" in result.output

    def test_dry_run_existing_report__no_clobber_exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        report = tmp_path / "existing-report.json"
        report.write_bytes(b"pre-existing\n")

        result = runner.invoke(app, ["apply", str(plan_path), "--report", str(report)])

        assert result.exit_code == 2, result.output
        assert "dry runs leave prior artifacts untouched" in result.output
        assert report.read_bytes() == b"pre-existing\n"

    def test_gate_refusal_existing_report__no_clobber_exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        report = tmp_path / "existing-report.json"
        report.write_bytes(b"pre-existing\n")

        result = runner.invoke(app, ["apply", str(plan_path), "--write", "--report", str(report)])

        assert result.exit_code == 3, result.output
        assert "pre-existing artifact preserved" in result.output
        assert report.read_bytes() == b"pre-existing\n"

    def test_write__report_published_inside_run_lock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """rev 0.26: report finalization happens while the run lock is held,
        so a run's artifacts and corpus effects commit under one coordination
        boundary. Spies are installed AFTER plan creation (plan takes its own
        lock) and the event list starts empty for the apply invocation."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)

        events: list[str] = []
        real_release = lock.RunLock.release
        real_write_report = cli_module.artifacts.write_report

        def spy_release(self: lock.RunLock) -> None:
            events.append("lock-released")
            real_release(self)

        def spy_write_report(report: Report, path: Path) -> None:
            events.append("report-written")
            real_write_report(report, path)

        monkeypatch.setattr(lock.RunLock, "release", spy_release)
        monkeypatch.setattr(cli_module.artifacts, "write_report", spy_write_report)

        result = runner.invoke(
            app,
            ["apply", str(plan_path), "--write", "--backup-dir", str(tmp_path / "bk")],
        )
        assert result.exit_code == 0, result.output
        assert "report-written" in events and "lock-released" in events
        assert events.index("report-written") < events.index("lock-released")


class TestReportLineage:
    def test_write_apply_report__carries_closed_manifest_hash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Report 2.0 (adr-0019): the report's manifest_sha256 is the hash of
        this attempt's CLOSED manifest — the redundant lineage anchor a
        successor attempt links against."""
        import hashlib as _hashlib

        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)

        result = runner.invoke(
            app, ["apply", str(plan_path), "--write", "--preserved-by", "external"]
        )

        assert result.exit_code == 0, result.output
        [report_path] = (tmp_path / ".docmend").glob("docmend-*-report.json")
        [manifest_path] = (tmp_path / ".docmend").glob("docmend-*-manifest.jsonl")
        document = json.loads(report_path.read_text())
        expected = f"sha256:{_hashlib.sha256(manifest_path.read_bytes()).hexdigest()}"
        assert document["manifest_sha256"] == expected
        assert document["prior_attempt"] is None  # first attempt
