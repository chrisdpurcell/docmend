"""Idempotency tests (FR-017; FR-003 duplicate-run; MS-4 exit criteria).

FR-017 acceptance: a second apply over a converted corpus reports zero
mutations and leaves corpus hashes unchanged — in all three re-run shapes an
unattended workflow can produce: same plan re-applied blind (every action
stale-hash-skips behind the FR-003 guard), same plan re-applied with --resume
(every action reconciles already-applied, exit 0), and re-plan over the
converted output (zero actions to begin with, exit 0).
"""

import hashlib
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

from docmend.cli import app
from docmend.writer.manifest import read_manifest

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


def _hashes(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _converted(tmp_path: Path) -> tuple[Path, Path, str]:
    """Scan→plan→apply the corpus once; return (corpus, plan_path, run_id)."""
    corpus = tmp_path / "corpus"
    make_corpus(corpus)
    plan_path = Path("plan.json")
    result = runner.invoke(app, ["plan", str(corpus), "--out", str(plan_path)])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["apply", str(plan_path), "--write", "--preserved-by", "external"])
    assert result.exit_code == 0, result.output
    manifests = list((tmp_path / ".docmend").glob("docmend-*-manifest.jsonl"))
    assert len(manifests) == 1
    run_id = manifests[0].name.removeprefix("docmend-").removesuffix("-manifest.jsonl")
    return corpus, plan_path, run_id


def test_double_apply_same_plan__zero_mutations_all_stale_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-017 acceptance (duplicate-run shape): blindly re-applying the same
    plan mutates nothing — every action stale-hash-skips (the sources were
    renamed/rewritten, so the plan's hashes no longer match anything) and the
    corpus hashes are unchanged. Exit 1 is deliberate: without --resume the
    tool cannot distinguish 'already converted' from 'changed under me', so
    the skips stay reviewable findings (AW-004)."""
    monkeypatch.chdir(tmp_path)
    corpus, plan_path, run_id = _converted(tmp_path)
    before = _hashes(corpus)

    result = runner.invoke(app, ["apply", str(plan_path), "--write", "--preserved-by", "external"])

    assert result.exit_code == 1, result.output
    assert "applied: 0" in result.output
    assert _hashes(corpus) == before
    # Zero mutations means zero new manifest records: still exactly one manifest.
    manifests = list((tmp_path / ".docmend").glob("docmend-*-manifest.jsonl"))
    assert [m.name for m in manifests] == [f"docmend-{run_id}-manifest.jsonl"]


def test_double_apply_with_resume__no_op_exit_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-017 with the FR-013 surface: the same duplicate run under
    --resume-run-id reconciles every action as already-applied and exits 0 —
    the shape an unattended re-invocation loop uses to converge."""
    monkeypatch.chdir(tmp_path)
    corpus, plan_path, run_id = _converted(tmp_path)
    before = _hashes(corpus)

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

    assert result.exit_code == 0, result.output
    assert "applied: 0" in result.output
    assert "already-applied 2" in result.output
    assert _hashes(corpus) == before
    records = read_manifest(tmp_path / ".docmend" / f"docmend-{run_id}-manifest.jsonl")
    assert sum(1 for r in records if r.result == "applied") == 2  # no re-apply records


def test_replan_over_converted_corpus__zero_actions_apply_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-017 acceptance (re-plan shape): planning over already-converted
    output finds nothing to do, and applying that empty plan is a clean no-op
    (exit 0, no manifest, corpus untouched)."""
    monkeypatch.chdir(tmp_path)
    corpus, _plan_path, run_id = _converted(tmp_path)
    before = _hashes(corpus)

    replan = Path("replan.json")
    result = runner.invoke(app, ["plan", str(corpus), "--out", str(replan)])
    assert result.exit_code == 0, result.output
    assert "actions: 0" in result.output

    result = runner.invoke(app, ["apply", str(replan), "--write", "--preserved-by", "external"])
    assert result.exit_code == 0, result.output
    assert "applied: 0" in result.output
    assert _hashes(corpus) == before
    manifests = list((tmp_path / ".docmend").glob("docmend-*-manifest.jsonl"))
    assert [m.name for m in manifests] == [f"docmend-{run_id}-manifest.jsonl"]
