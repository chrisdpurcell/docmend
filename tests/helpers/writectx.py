"""Test adapters that enter docmend's real write-ceremony factories."""

import contextlib
from collections.abc import Generator, Sequence
from pathlib import Path

import pytest

from docmend import artifacts
from docmend.plan import Plan
from docmend.writer.commit import WriteSafetyContext, apply_write_context, restore_write_context
from docmend.writer.gate import ApplyOptions


@contextlib.contextmanager
def apply_safety(
    plan: Plan,
    *,
    options: ApplyOptions,
    manifest_path: Path,
    report_path: Path,
    run_id: str,
    state_dir: Path,
    resume_manifest_paths: Sequence[Path] = (),
    prior_report_paths: Sequence[Path] = (),
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[WriteSafetyContext]:
    """Materialize a plan and decompose fixture options into factory inputs."""
    assert plan.source_root is not None
    plan_path = state_dir / "plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    artifacts.write_plan(plan, plan_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(state_dir))
    with apply_write_context(
        plan_path,
        run_id=run_id,
        manifest_path=manifest_path,
        report_path=report_path,
        backup_root_override=options.backup_root,
        preserved_by=options.preserved_by,
        allow_no_backup=options.allow_no_backup,
        resume_manifest_paths=resume_manifest_paths,
        prior_report_paths=prior_report_paths,
    ) as safety:
        yield safety


@contextlib.contextmanager
def restore_safety(
    manifest_paths: Sequence[Path],
    *,
    run_id: str,
    manifest_out: Path,
    state_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[WriteSafetyContext]:
    """Enter the restore factory over on-disk manifest evidence."""
    monkeypatch.setenv("XDG_STATE_HOME", str(state_dir))
    with restore_write_context(manifest_paths, run_id=run_id, manifest_out=manifest_out) as safety:
        yield safety
