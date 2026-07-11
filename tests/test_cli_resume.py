"""`docmend apply --resume-*` CLI tests (FR-013, IR-003, adr-0006, AW-001,
ERR-001; §18.5 exit taxonomy).

FR-013 acceptance: kill an apply run mid-batch; re-invoking completes the
remainder; final corpus and (union-of-)manifest records are identical to an
uninterrupted run. `already-applied` skips are NOT findings — a clean resume
exits 0, or unattended re-invocation loops would never converge on success.
"""

import hashlib
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
