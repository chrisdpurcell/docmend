"""`docmend apply --resume-*` CLI tests (FR-013, IR-003, adr-0006, AW-001,
ERR-001; §18.5 exit taxonomy).

FR-013 acceptance: kill an apply run mid-batch; re-invoking completes the
remainder; final corpus and (union-of-)manifest records are identical to an
uninterrupted run. `already-applied` skips are NOT findings — a clean resume
exits 0, or unattended re-invocation loops would never converge on success.
"""

import hashlib
import json
import logging
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from tests.helpers.manifest2 import read_records
from typer.testing import CliRunner

from docmend.cli import app
from docmend.writer import apply as apply_module

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_logging() -> Iterator[None]:
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


def make_corpus(root: Path) -> None:
    root.mkdir(exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha body\r\n")
    (root / "c.txt").write_bytes(b"charlie body\r\n")
    (root / "e.txt").write_bytes(b"echo body\r\n")


def _hashes(root: Path) -> dict[str, str]:
    # ".docmend-tmp" staging residue is excluded: a killed run's staged temp
    # is inert tool-owned residue by design (adr-0019/adr-0021); corpus
    # equivalence is judged on documents, not tool residue.
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.name.endswith(".docmend-tmp")
    }


def _make_plan(corpus: Path, *, out: Path = Path("plan.json")) -> Path:
    result = runner.invoke(app, ["plan", str(corpus), "--out", str(out)])
    assert result.exit_code in (0, 1), result.output
    return out


class _Interrupt(RuntimeError):
    """Injected kill — not WriteError/OSError, so apply cannot absorb it."""


def _interrupt_after(monkeypatch: pytest.MonkeyPatch, n: int) -> None:
    """Let the first `n` mutations succeed, then raise on the next (ERR-001)."""
    real = apply_module.publish_staged
    calls = {"n": 0}

    def exploding(*args: object, **kwargs: object) -> None:
        calls["n"] += 1
        if calls["n"] > n:
            raise _Interrupt("injected kill")
        real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(apply_module, "publish_staged", exploding)


def _sole_manifest_run_id(
    artifact_dir: Path, *, exclude: frozenset[str] | set[str] = frozenset()
) -> str:
    ids = {
        p.name.removeprefix("docmend-").removesuffix("-manifest.jsonl")
        for p in artifact_dir.glob("docmend-*-manifest.jsonl")
    } - exclude
    assert len(ids) == 1, sorted(ids)
    return ids.pop()


class TestResumeFlagValidation:
    def test_resume_manifest_missing__exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)

        result = runner.invoke(app, ["apply", str(plan_path), "--resume-run-id", "run_x_nothere"])
        assert result.exit_code == 2, result.output

    def test_resume_manifest_from_other_tree__exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A manifest recorded against a different source root must refuse —
        action-IDs could never match, and silently re-executing everything
        would hide the operator's mistake (ERR-006 posture)."""
        monkeypatch.chdir(tmp_path)
        other = tmp_path / "other"
        make_corpus(other)
        other_plan = _make_plan(other, out=Path("other-plan.json"))
        result = runner.invoke(
            app, ["apply", str(other_plan), "--write", "--preserved-by", "external"]
        )
        assert result.exit_code == 0, result.output
        other_manifest = next((tmp_path / ".docmend").glob("docmend-*-manifest.jsonl"))

        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-manifest",
                str(other_manifest),
            ],
        )
        assert result.exit_code == 2, result.output
        assert "source root" in result.output


class TestKillAndResume:
    def test_kill_and_resume__corpus_matches_uninterrupted_control(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-013 acceptance end-to-end through the CLI: interrupt after one
        mutation, resume via the --resume-run-id sidecar, exit 0 (already-
        applied is not a finding), corpus identical to the control run,
        manifests' records cover each action exactly once."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        control = tmp_path / "control"
        shutil.copytree(corpus, control)
        control_plan = _make_plan(control, out=Path("control-plan.json"))
        result = runner.invoke(
            app, ["apply", str(control_plan), "--write", "--preserved-by", "external"]
        )
        assert result.exit_code == 0, result.output
        control_id = _sole_manifest_run_id(tmp_path / ".docmend")

        plan_path = _make_plan(corpus)
        _interrupt_after(monkeypatch, 1)
        result = runner.invoke(
            app,
            ["apply", str(plan_path), "--write", "--preserved-by", "external"],
            catch_exceptions=True,
        )
        assert isinstance(result.exception, _Interrupt)
        monkeypatch.undo()
        monkeypatch.chdir(tmp_path)  # undo() also reverted the chdir
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
        interrupted_id = _sole_manifest_run_id(tmp_path / ".docmend", exclude={control_id})

        result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-run-id",
                interrupted_id,
            ],
        )
        assert result.exit_code == 0, result.output
        assert "already-applied 1" in result.output

        assert _hashes(corpus) == _hashes(control)
        interrupted_manifest = tmp_path / ".docmend" / f"docmend-{interrupted_id}-manifest.jsonl"
        resume_id = _sole_manifest_run_id(
            tmp_path / ".docmend", exclude={control_id, interrupted_id}
        )
        resume_manifest = tmp_path / ".docmend" / f"docmend-{resume_id}-manifest.jsonl"
        covered = [
            r.action_id
            for path in (interrupted_manifest, resume_manifest)
            for r in read_records(path)
            if r.result == "applied"  # intent records are evidence, not coverage
        ]
        assert len(set(covered)) == len(covered) == 3

    def test_double_resume__two_manifests_chain_exit_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A twice-interrupted run resumes with BOTH prior manifests (the flags
        are repeatable) — with only the latest, earlier completions would
        surface as findings and unattended re-invocation would never go clean."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)

        _interrupt_after(monkeypatch, 1)
        result = runner.invoke(
            app,
            ["apply", str(plan_path), "--write", "--preserved-by", "external"],
            catch_exceptions=True,
        )
        assert isinstance(result.exception, _Interrupt)
        monkeypatch.undo()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
        first_id = _sole_manifest_run_id(tmp_path / ".docmend")

        _interrupt_after(monkeypatch, 1)
        result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-run-id",
                first_id,
            ],
            catch_exceptions=True,
        )
        assert isinstance(result.exception, _Interrupt)
        monkeypatch.undo()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
        second_id = _sole_manifest_run_id(tmp_path / ".docmend", exclude={first_id})

        result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-run-id",
                first_id,
                "--resume-run-id",
                second_id,
            ],
        )
        assert result.exit_code == 0, result.output
        assert "already-applied 2" in result.output

    def test_resume_dry_run__previews_remainder(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-004 under resume: no --write previews what a resume would do."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        _interrupt_after(monkeypatch, 1)
        result = runner.invoke(
            app,
            ["apply", str(plan_path), "--write", "--preserved-by", "external"],
            catch_exceptions=True,
        )
        assert isinstance(result.exception, _Interrupt)
        monkeypatch.undo()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
        run_id = _sole_manifest_run_id(tmp_path / ".docmend")
        before = _hashes(corpus)

        result = runner.invoke(app, ["apply", str(plan_path), "--resume-run-id", run_id])
        assert result.exit_code == 0, result.output
        assert "would-apply: 2" in result.output
        assert "already-applied 1" in result.output
        assert _hashes(corpus) == before


def test_resume_reconciliation_failure__no_phantom_manifest_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PR #10 review: a resume whose only failures come from read-only
    reconciliation (ERR-002) performs zero mutations, so no manifest file is
    created — the console must not print a path to a nonexistent manifest."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    make_corpus(corpus)
    plan_path = _make_plan(corpus)
    result = runner.invoke(app, ["apply", str(plan_path), "--write", "--preserved-by", "external"])
    assert result.exit_code == 0, result.output
    run_id = _sole_manifest_run_id(tmp_path / ".docmend")
    (corpus / "a.md").write_bytes(b"tampered after apply\n")

    result = runner.invoke(
        app,
        [
            "apply",
            str(plan_path),
            "--write",
            "--preserved-by",
            "external",
            "--resume-run-id",
            run_id,
        ],
    )
    assert result.exit_code == 1, result.output
    assert "failed: 1" in result.output
    for line in result.output.splitlines():
        if line.startswith("manifest: "):
            assert Path(line.removeprefix("manifest: ")).exists(), line


class TestAttemptLineageDiscovery:
    """adr-0019 attempt graph (Plan B Task 9): report-only predecessors,
    missing-manifest refusal, --prior-report, and the no-gap rule."""

    def _refused_attempt(self, tmp_path: Path, corpus: Path, plan_path: Path) -> str:
        """A genuine report-only attempt: the FR-005 gate refuses (no
        preservation strategy), leaving a refusal report and NO manifest."""
        result = runner.invoke(app, ["apply", str(plan_path), "--write"])
        assert result.exit_code == 3, result.output
        [report] = (tmp_path / ".docmend").glob("docmend-*-report.json")
        return report.name.removeprefix("docmend-").removesuffix("-report.json")

    def test_report_only_predecessor__empty_chain_resume_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        refused_id = self._refused_attempt(tmp_path, corpus, plan_path)

        result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-run-id",
                refused_id,
            ],
        )

        assert result.exit_code == 0, result.output
        manifests = list((tmp_path / ".docmend").glob("docmend-*-manifest.jsonl"))
        assert len(manifests) == 1
        header = json.loads(manifests[0].read_text().splitlines()[0])
        assert header["prior_manifest_sha256"] is None  # first MANIFEST: a root
        assert header["prior_attempt"]["run_id"] == refused_id
        assert header["prior_attempt"]["report_sha256"] is not None
        assert header["prior_attempt"]["manifest_sha256"] is None

    def test_missing_mutation_manifest__refused_exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CR-NEW-001: a report recording a closed manifest whose file is gone
        is MISSING EVIDENCE — never mistaken for a mutation-free attempt."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        applied = runner.invoke(
            app, ["apply", str(plan_path), "--write", "--preserved-by", "external"]
        )
        assert applied.exit_code == 0, applied.output
        run_id = _sole_manifest_run_id(tmp_path / ".docmend")
        (tmp_path / ".docmend" / f"docmend-{run_id}-manifest.jsonl").unlink()

        result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-run-id",
                run_id,
            ],
        )

        assert result.exit_code == 2, result.output
        assert "missing mutation evidence" in result.output

    def test_predecessor_with_no_evidence__exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)

        result = runner.invoke(
            app,
            ["apply", str(plan_path), "--resume-run-id", "run_20990101T000000Z_dead00"],
        )

        assert result.exit_code == 2, result.output
        assert "no evidence" in result.output

    def test_prior_report_from_different_plan__exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        self._refused_attempt(tmp_path, corpus, plan_path)
        [report] = (tmp_path / ".docmend").glob("docmend-*-report.json")
        other = tmp_path / "other-corpus"
        make_corpus(other)
        other_plan = _make_plan(other, out=Path("other-plan.json"))

        result = runner.invoke(
            app,
            ["apply", str(other_plan), "--prior-report", str(report)],
        )

        assert result.exit_code == 2, result.output
        assert "different plan" in result.output

    def test_relocated_prior_report__accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        refused_id = self._refused_attempt(tmp_path, corpus, plan_path)
        [report] = (tmp_path / ".docmend").glob("docmend-*-report.json")
        relocated = tmp_path / "archive" / "old-report.json"
        relocated.parent.mkdir()
        report.rename(relocated)

        result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--prior-report",
                str(relocated),
            ],
        )

        assert result.exit_code == 0, result.output
        [manifest_path] = (tmp_path / ".docmend").glob("docmend-*-manifest.jsonl")
        header = json.loads(manifest_path.read_text().splitlines()[0])
        assert header["prior_attempt"]["run_id"] == refused_id

    def test_composed_lineage__report_only_then_manifest_only_then_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The design's principal interruption shape (F6 round 5): R1 leaves
        only a report; R2 leaves only a manifest (its report is lost); R3
        connects both — R3's edge names R2 by MANIFEST hash, R2's header
        names R1 by REPORT hash."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        r1 = self._refused_attempt(tmp_path, corpus, plan_path)
        [r1_report] = (tmp_path / ".docmend").glob("docmend-*-report.json")

        # R2: a real write resume of the report-only R1 — then its report is
        # "lost" (the crash-after-manifest-close window).
        r2_result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-run-id",
                r1,
            ],
        )
        assert r2_result.exit_code == 0, r2_result.output
        [r2_manifest] = (tmp_path / ".docmend").glob("docmend-*-manifest.jsonl")
        r2 = r2_manifest.name.removeprefix("docmend-").removesuffix("-manifest.jsonl")
        (tmp_path / ".docmend" / f"docmend-{r2}-report.json").unlink()

        # R3: resume from R2 (manifest-only) — R1's report must ALSO be
        # supplied: R2's header edge names it, and the no-gap rule requires
        # every named ancestor's evidence.
        r3_result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-run-id",
                r2,
                "--prior-report",
                str(r1_report),
            ],
        )
        assert r3_result.exit_code == 0, r3_result.output
        r3_manifests = [
            p for p in (tmp_path / ".docmend").glob("docmend-*-manifest.jsonl") if r2 not in p.name
        ]
        # A fully-reconciled resume mutates nothing → R3 leaves no manifest;
        # its REPORT carries the lineage.
        r3_reports = [
            p
            for p in (tmp_path / ".docmend").glob("docmend-*-report.json")
            if r2 not in p.name and p != r1_report
        ]
        assert not r3_manifests
        assert len(r3_reports) == 1
        document = json.loads(r3_reports[0].read_text())
        assert document["prior_attempt"]["run_id"] == r2
        assert document["prior_attempt"]["manifest_sha256"] is not None
        assert document["prior_attempt"]["report_sha256"] is None
        # And R2's own header names R1 by report hash:
        r2_header = json.loads(r2_manifest.read_text().splitlines()[0])
        assert r2_header["prior_attempt"]["run_id"] == r1
        assert r2_header["prior_attempt"]["report_sha256"] is not None

    def test_no_gap_rule__named_ancestor_missing__exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A manifest whose report-flavored edge names an UNSUPPLIED ancestor
        fails closed before any mutation."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        r1 = self._refused_attempt(tmp_path, corpus, plan_path)
        r2_result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-run-id",
                r1,
            ],
        )
        assert r2_result.exit_code == 0, r2_result.output
        [r2_manifest] = (tmp_path / ".docmend").glob("docmend-*-manifest.jsonl")

        # Supply ONLY R2's manifest: its edge names R1's report — a gap.
        result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-manifest",
                str(r2_manifest),
            ],
        )

        assert result.exit_code == 2, result.output
        assert "no-gap" in result.output or "not supplied" in result.output


class TestAttemptGraphRefusals:
    """The loader's fail-closed arms (adr-0019; CR-006/CR-NEW-001)."""

    def _two_attempts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[Path, str, str]:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        refused = runner.invoke(app, ["apply", str(plan_path), "--write"])
        assert refused.exit_code == 3
        [r1_report] = (tmp_path / ".docmend").glob("docmend-*-report.json")
        r1 = r1_report.name.removeprefix("docmend-").removesuffix("-report.json")
        done = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-run-id",
                r1,
            ],
        )
        assert done.exit_code == 0, done.output
        [r2_manifest] = (tmp_path / ".docmend").glob("docmend-*-manifest.jsonl")
        r2 = r2_manifest.name.removeprefix("docmend-").removesuffix("-manifest.jsonl")
        return plan_path, r1, r2

    def test_duplicate_report_input__exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path, r1, _r2 = self._two_attempts(tmp_path, monkeypatch)
        report = tmp_path / ".docmend" / f"docmend-{r1}-report.json"

        result = runner.invoke(
            app,
            ["apply", str(plan_path), "--prior-report", str(report), "--prior-report", str(report)],
        )

        assert result.exit_code == 2, result.output
        assert "duplicate report" in result.output

    def test_report_only_claiming_applied_outcomes__exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path, _r1, r2 = self._two_attempts(tmp_path, monkeypatch)
        report_path = tmp_path / ".docmend" / f"docmend-{r2}-report.json"
        document = json.loads(report_path.read_text())
        document["manifest_sha256"] = None  # forge: hide the mutation evidence
        report_path.write_text(json.dumps(document))

        result = runner.invoke(app, ["apply", str(plan_path), "--prior-report", str(report_path)])

        assert result.exit_code == 2, result.output
        assert "mutation evidence is missing" in result.output

    def test_manifest_and_report_edge_disagreement__exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path, r1, r2 = self._two_attempts(tmp_path, monkeypatch)
        report_path = tmp_path / ".docmend" / f"docmend-{r2}-report.json"
        document = json.loads(report_path.read_text())
        document["prior_attempt"] = None  # forge: contradict the manifest header
        report_path.write_text(json.dumps(document))

        result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--write",
                "--preserved-by",
                "external",
                "--resume-run-id",
                r2,
                "--prior-report",
                str(tmp_path / ".docmend" / f"docmend-{r1}-report.json"),
            ],
        )

        assert result.exit_code == 2, result.output
        assert "disagree" in result.output

    def test_ambiguous_tips__exit_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two unlinked root attempts = two tips — no deterministic newest."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        first = runner.invoke(app, ["apply", str(plan_path), "--write"])
        assert first.exit_code == 3
        second = runner.invoke(app, ["apply", str(plan_path), "--write"])
        assert second.exit_code == 3
        reports = sorted((tmp_path / ".docmend").glob("docmend-*-report.json"))
        assert len(reports) == 2

        result = runner.invoke(
            app,
            [
                "apply",
                str(plan_path),
                "--prior-report",
                str(reports[0]),
                "--prior-report",
                str(reports[1]),
            ],
        )

        assert result.exit_code == 2, result.output
        assert "attempt tips" in result.output
