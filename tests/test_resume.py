"""Resume engine tests (FR-013, adr-0006, AW-001, ERR-001/ERR-002).

`execute_plan(resume_records=...)` reconciles plan actions against a prior
run's manifest records before the normal per-action ladder: a recorded-applied
action whose live output matches its `after_sha256` skips as `already-applied`;
a mismatch or missing output fails ERR-002 (the file changed since docmend
applied it — resume must surface, never silently proceed); an unrecorded
action executes normally, still behind the FR-003 hash guard.
"""

import hashlib
import shutil
from pathlib import Path

import pytest

from corpus import FileRecipe, materialize, seeded_faker
from docmend import discovery, planning
from docmend.config import DocmendConfig
from docmend.plan import ArtifactRef, Plan
from docmend.report import Report
from docmend.writer import apply as apply_module
from docmend.writer.apply import execute_plan
from docmend.writer.gate import ApplyOptions
from docmend.writer.manifest import ManifestRecord, read_manifest

RUN_ID = "run_20260707T000000Z_0000aa"
RESUME_RUN_ID = "run_20260707T000000Z_0000ab"
PLAN_RUN_ID = "run_20260707T000000Z_0000a9"
GENERATED_AT = "2026-07-07T00:00:00+00:00"
NOW = "2026-07-07T00:00:01+00:00"

RECIPES = [
    FileRecipe("a.txt", "utf-8", "crlf"),
    FileRecipe("c.txt", "utf-8", "crlf"),
    FileRecipe("e.txt", "utf-8", "crlf"),
]


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _plan_for(root: Path, config: DocmendConfig) -> Plan:
    inventory = discovery.scan(root, config, run_id=PLAN_RUN_ID, generated_at=GENERATED_AT)
    ref = ArtifactRef(path="inv.json", run_id=PLAN_RUN_ID, sha256="sha256:" + "0" * 64)
    return planning.build_plan(
        inventory, config, run_id=PLAN_RUN_ID, generated_at=GENERATED_AT, inventory_ref=ref
    )


def _execute(
    plan: Plan,
    config: DocmendConfig,
    manifest_path: Path,
    *,
    run_id: str = RUN_ID,
    write: bool = True,
    resume_records: list[ManifestRecord] | None = None,
) -> Report:
    options = ApplyOptions(
        write=write, backup_root=None, preserved_by="external", allow_no_backup=False
    )
    return execute_plan(
        plan,
        config,
        run_id=run_id,
        plan_ref=ArtifactRef(path="plan.json", run_id=PLAN_RUN_ID, sha256="sha256:" + "1" * 64),
        options=options,
        manifest_path=manifest_path,
        started_at=GENERATED_AT,
        now=lambda: NOW,
        resume_records=resume_records,
    )


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): _sha(path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class _Interrupt(RuntimeError):
    """Injected mid-batch interruption — deliberately NOT WriteError/OSError so
    the per-action failure handling cannot absorb it (models a kill, ERR-001)."""


def _interrupted_apply(
    root: Path, config: DocmendConfig, manifest_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Plan, list[ManifestRecord]]:
    """Apply the plan for `root`, injecting an interrupt before the 2nd mutation.

    Leaves file 1 applied+recorded, files 2..n untouched — the AW-001 crash
    shape (atomic writes mean no partial target can exist).
    """
    plan = _plan_for(root, config)
    real = apply_module.atomic_write_bytes
    calls = {"n": 0}

    def exploding(*args: object, **kwargs: object) -> None:
        calls["n"] += 1
        if calls["n"] >= 2:
            raise _Interrupt("injected kill")
        real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(apply_module, "atomic_write_bytes", exploding)
    with pytest.raises(_Interrupt):
        _execute(plan, config, manifest_path)
    monkeypatch.setattr(apply_module, "atomic_write_bytes", real)
    return plan, read_manifest(manifest_path)


def test_kill_and_resume__corpus_identical_to_uninterrupted_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-013 acceptance / AW-001: kill mid-batch, re-invoke with the prior
    manifest; the final corpus matches an uninterrupted control run and the
    two manifests' records cover each completed action exactly once."""
    faker = seeded_faker()
    root = tmp_path / "root"
    materialize(root, RECIPES, faker)
    control = tmp_path / "control"
    shutil.copytree(root, control)
    config = DocmendConfig()

    control_plan = _plan_for(control, config)
    _execute(control_plan, config, tmp_path / "control-manifest.jsonl")

    plan, first_records = _interrupted_apply(root, config, tmp_path / "manifest.jsonl", monkeypatch)
    assert len(first_records) == 1  # exactly the pre-interrupt mutation

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        resume_records=first_records,
    )

    assert _hash_tree(root) == _hash_tree(control)
    statuses = {o.path: (o.status, o.skip_reason) for o in report.outcomes}
    assert statuses["a.txt"] == ("skipped", "already-applied")
    assert statuses["c.txt"] == ("applied", None)
    assert statuses["e.txt"] == ("applied", None)
    resume_records = read_manifest(tmp_path / "resume-manifest.jsonl")
    covered = [r.action_id for r in (*first_records, *resume_records)]
    assert sorted(covered) == sorted(a.action_id for a in plan.actions)
    assert len(set(covered)) == len(covered)  # no action recorded twice


def test_resume_fully_completed_run__all_already_applied_no_manifest(tmp_path: Path) -> None:
    """FR-017 half: resuming a run that actually finished mutates nothing and
    writes no new manifest (every action reconciles as already-applied)."""
    root = tmp_path / "root"
    materialize(root, RECIPES, seeded_faker())
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path / "manifest.jsonl")
    records = read_manifest(tmp_path / "manifest.jsonl")
    before = _hash_tree(root)

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        resume_records=records,
    )

    assert _hash_tree(root) == before
    assert all(
        o.status == "skipped" and o.skip_reason == "already-applied" for o in report.outcomes
    )
    assert not (tmp_path / "resume-manifest.jsonl").exists()


def test_resume_output_changed_since_apply__fails_err002(tmp_path: Path) -> None:
    """adr-0006 'fail' arm: a recorded-applied output whose live hash no longer
    matches after_sha256 was touched by something else — ERR-002, untouched."""
    root = tmp_path / "root"
    materialize(root, RECIPES, seeded_faker())
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path / "manifest.jsonl")
    records = read_manifest(tmp_path / "manifest.jsonl")
    tampered = Path(records[0].target_path)
    tampered.write_bytes(b"externally edited after apply\n")
    tampered_bytes = tampered.read_bytes()

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        resume_records=records,
    )

    outcome = next(o for o in report.outcomes if o.action_id == records[0].action_id)
    assert outcome.status == "failed"
    assert outcome.error is not None and outcome.error.error_class == "ERR-002"
    assert tampered.read_bytes() == tampered_bytes  # reconciliation never mutates


def test_resume_output_missing__fails_err002(tmp_path: Path) -> None:
    """adr-0006 'fail' arm: a recorded-applied output that vanished is external
    interference, not not-started work — ERR-002, never silently re-created."""
    root = tmp_path / "root"
    materialize(root, RECIPES, seeded_faker())
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path / "manifest.jsonl")
    records = read_manifest(tmp_path / "manifest.jsonl")
    Path(records[0].target_path).unlink()

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        resume_records=records,
    )

    outcome = next(o for o in report.outcomes if o.action_id == records[0].action_id)
    assert outcome.status == "failed"
    assert outcome.error is not None and outcome.error.error_class == "ERR-002"


def test_resume_after_lost_trailing_record__stale_hash_skip_not_corruption(
    tmp_path: Path,
) -> None:
    """The one state a torn trailing manifest line leaves behind: the mutation
    completed but its record was lost. Resume re-executes that action, the
    FR-003 hash guard sees the already-converted source, and the outcome is a
    stale-hash SKIP (reviewable finding) — safe, never a second mutation.
    Uses a rewrite-in-place `.md` action so the source path survives; a lost
    RENAME record would surface as an `unreadable` skip instead (source moved),
    the same reviewable-finding class."""
    root = tmp_path / "root"
    materialize(root, [*RECIPES, FileRecipe("z.md", "utf-8", "crlf")], seeded_faker())
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path / "manifest.jsonl")
    records = read_manifest(tmp_path / "manifest.jsonl")
    lost = next(r for r in records if r.original_path.endswith("z.md"))
    surviving = [r for r in records if r is not lost]
    before = _hash_tree(root)

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        resume_records=surviving,
    )

    assert _hash_tree(root) == before
    outcome = next(o for o in report.outcomes if o.action_id == lost.action_id)
    assert (outcome.status, outcome.skip_reason) == ("skipped", "stale-hash")


def test_resume_dry_run__previews_remainder_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR-004 holds under resume: a dry-run resume reports already-applied vs
    would_apply and leaves corpus and manifests untouched."""
    root = tmp_path / "root"
    materialize(root, RECIPES, seeded_faker())
    config = DocmendConfig()
    plan, first_records = _interrupted_apply(root, config, tmp_path / "manifest.jsonl", monkeypatch)
    before = _hash_tree(root)

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        write=False,
        resume_records=first_records,
    )

    assert _hash_tree(root) == before
    assert not (tmp_path / "resume-manifest.jsonl").exists()
    counts = {(o.status, o.skip_reason) for o in report.outcomes}
    assert counts == {("skipped", "already-applied"), ("would_apply", None)}
