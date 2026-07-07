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
    two manifests' APPLIED records cover each completed action exactly once
    (intent records are evidence, not coverage)."""
    faker = seeded_faker()
    root = tmp_path / "root"
    materialize(root, RECIPES, faker)
    control = tmp_path / "control"
    shutil.copytree(root, control)
    config = DocmendConfig()

    control_plan = _plan_for(control, config)
    _execute(control_plan, config, tmp_path / "control-manifest.jsonl")

    plan, first_records = _interrupted_apply(root, config, tmp_path / "manifest.jsonl", monkeypatch)
    # intent₁ + applied₁ for the completed mutation, then the dangling intent₂
    # of the killed action (its atomic_write_bytes raised before writing).
    assert [r.result for r in first_records] == ["intent", "applied", "intent"]

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
    covered = [r.action_id for r in (*first_records, *resume_records) if r.result == "applied"]
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


def _interrupted_after_publish(
    root: Path, config: DocmendConfig, manifest_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Plan, list[ManifestRecord]]:
    """Kill the 1st rename_and_rewrite AFTER its target publish, BEFORE the
    source unlink — the narrow multi-step window. Leaves target published,
    source still present, and a dangling intent record as the only evidence."""
    plan = _plan_for(root, config)
    real = apply_module.atomic_write_bytes

    def publish_then_die(*args: object, **kwargs: object) -> None:
        real(*args, **kwargs)  # type: ignore[arg-type]
        raise _Interrupt("injected kill after target publish")

    monkeypatch.setattr(apply_module, "atomic_write_bytes", publish_then_die)
    with pytest.raises(_Interrupt):
        _execute(plan, config, manifest_path)
    monkeypatch.setattr(apply_module, "atomic_write_bytes", real)
    return plan, read_manifest(manifest_path)


def _interrupted_before_final_record(
    root: Path, config: DocmendConfig, manifest_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Plan, list[ManifestRecord]]:
    """Kill the 1st rename_and_rewrite AFTER the whole mutation (target
    published, source unlinked) but BEFORE its final manifest append — the
    mutation completed with only the intent record as evidence."""
    from docmend.writer.manifest import ManifestWriter

    plan = _plan_for(root, config)
    real_append = ManifestWriter.append

    def append_or_die(self: ManifestWriter, record: ManifestRecord) -> ManifestRecord:
        if record.result != "intent":
            raise _Interrupt("injected kill before final record")
        return real_append(self, record)

    monkeypatch.setattr(ManifestWriter, "append", append_or_die)
    with pytest.raises(_Interrupt):
        _execute(plan, config, manifest_path)
    monkeypatch.setattr(ManifestWriter, "append", real_append)
    return plan, read_manifest(manifest_path)


def test_rename_and_rewrite_write__intent_record_precedes_final_record(tmp_path: Path) -> None:
    """DR-004 hardening: a multi-step mutation appends a `result: "intent"`
    record (expected after-hash included) BEFORE its first mutation, then the
    final record after — a hard kill anywhere in the window leaves evidence
    resume can reconcile. Single-step mutations (pure rewrite) stay one-record:
    their atomic write has no multi-step window."""
    root = tmp_path / "root"
    materialize(
        root,
        [FileRecipe("a.txt", "utf-8", "crlf"), FileRecipe("z.md", "utf-8", "crlf")],
        seeded_faker(),
    )
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path / "manifest.jsonl")

    records = read_manifest(tmp_path / "manifest.jsonl")
    by_path: dict[str, list[ManifestRecord]] = {}
    for record in records:
        by_path.setdefault(Path(record.original_path).name, []).append(record)
    txt = by_path["a.txt"]
    assert [r.result for r in txt] == ["intent", "applied"]
    assert txt[0].operation == "rename_and_rewrite"
    assert txt[0].after_sha256 == txt[1].after_sha256  # intent carries the EXPECTED hash
    assert txt[0].seq < txt[1].seq
    assert [r.result for r in by_path["z.md"]] == ["applied"]


def test_resume_after_kill_between_publish_and_unlink__completes_the_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dangling intent + target matches the expected after-hash + source still
    present: the publish happened, the unlink did not. Resume completes the
    action (removes the source, records applied) — corpus ends identical to an
    uninterrupted control run."""
    root = tmp_path / "root"
    materialize(root, RECIPES, seeded_faker())
    control = tmp_path / "control"
    shutil.copytree(root, control)
    config = DocmendConfig()
    control_plan = _plan_for(control, config)
    _execute(control_plan, config, tmp_path / "control-manifest.jsonl")

    plan, first = _interrupted_after_publish(root, config, tmp_path / "manifest.jsonl", monkeypatch)
    assert [r.result for r in first] == ["intent"]
    assert Path(first[0].original_path).exists()  # unlink never ran

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        resume_records=first,
    )

    assert _hash_tree(root) == _hash_tree(control)
    outcome = next(o for o in report.outcomes if o.action_id == first[0].action_id)
    assert outcome.status == "applied"
    resume_records = read_manifest(tmp_path / "resume-manifest.jsonl")
    applied = [r.action_id for r in (*first, *resume_records) if r.result == "applied"]
    assert sorted(applied) == sorted(a.action_id for a in plan.actions)
    assert len(set(applied)) == len(applied)


def test_resume_after_kill_before_final_record__adopts_completed_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dangling intent + target matches + source gone: the whole mutation
    completed unrecorded. Resume adopts it — applied outcome, applied record in
    the resuming run's manifest — so the union of manifests stays the complete
    restore evidence."""
    root = tmp_path / "root"
    materialize(root, RECIPES, seeded_faker())
    control = tmp_path / "control"
    shutil.copytree(root, control)
    config = DocmendConfig()
    control_plan = _plan_for(control, config)
    _execute(control_plan, config, tmp_path / "control-manifest.jsonl")

    plan, first = _interrupted_before_final_record(
        root, config, tmp_path / "manifest.jsonl", monkeypatch
    )
    assert [r.result for r in first] == ["intent"]
    assert not Path(first[0].original_path).exists()  # mutation fully completed

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        resume_records=first,
    )

    assert _hash_tree(root) == _hash_tree(control)
    outcome = next(o for o in report.outcomes if o.action_id == first[0].action_id)
    assert outcome.status == "applied"
    resume_records = read_manifest(tmp_path / "resume-manifest.jsonl")
    applied = [r.action_id for r in (*first, *resume_records) if r.result == "applied"]
    assert sorted(applied) == sorted(a.action_id for a in plan.actions)
    assert len(set(applied)) == len(applied)


def test_resume_dangling_intent_target_tampered__fails_err002(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dangling intent whose live target matches neither the expected after-hash
    nor a recorded overwritten-hash is external interference: ERR-002, and
    reconciliation mutates nothing."""
    root = tmp_path / "root"
    materialize(root, RECIPES, seeded_faker())
    config = DocmendConfig()
    plan, first = _interrupted_after_publish(root, config, tmp_path / "manifest.jsonl", monkeypatch)
    intent = first[0]
    Path(intent.target_path).write_bytes(b"externally edited in the window\n")
    source_before = Path(intent.original_path).read_bytes()
    target_before = Path(intent.target_path).read_bytes()

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        resume_records=first,
    )

    # The conflicted action's files are untouched (other actions may apply).
    assert Path(intent.original_path).read_bytes() == source_before
    assert Path(intent.target_path).read_bytes() == target_before
    outcome = next(o for o in report.outcomes if o.action_id == intent.action_id)
    assert outcome.status == "failed"
    assert outcome.error is not None and outcome.error.error_class == "ERR-002"


def test_resume_dangling_intent_source_tampered__fails_err002_source_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Published target matches, but the still-present source no longer matches
    the intent's before-hash: someone touched it in the window. Resume must not
    remove it — ERR-002, both files kept as found."""
    root = tmp_path / "root"
    materialize(root, RECIPES, seeded_faker())
    config = DocmendConfig()
    plan, first = _interrupted_after_publish(root, config, tmp_path / "manifest.jsonl", monkeypatch)
    intent = first[0]
    Path(intent.original_path).write_bytes(b"source edited in the window\n")

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        resume_records=first,
    )

    assert Path(intent.original_path).read_bytes() == b"source edited in the window\n"
    outcome = next(o for o in report.outcomes if o.action_id == intent.action_id)
    assert outcome.status == "failed"
    assert outcome.error is not None and outcome.error.error_class == "ERR-002"


def test_resume_intent_over_unclobbered_target__reexecutes_with_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Clobber window: the intent recorded overwritten_sha256 for a pre-existing
    target, then the kill landed before the publish. The live target still holds
    the recorded to-be-overwritten bytes — proof the publish never happened —
    so resume re-executes the action normally under the overwrite policy."""
    from docmend.config import RenameConfig

    root = tmp_path / "root"
    materialize(root, [FileRecipe("a.txt", "utf-8", "crlf")], seeded_faker())
    (root / "a.md").write_bytes(b"old target content\n")
    control = tmp_path / "control"
    shutil.copytree(root, control)
    config = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
    control_plan = _plan_for(control, config)
    _execute(control_plan, config, tmp_path / "control-manifest.jsonl")

    plan = _plan_for(root, config)
    real = apply_module.atomic_write_bytes

    def die_before_publish(*args: object, **kwargs: object) -> None:
        raise _Interrupt("injected kill before target publish")

    monkeypatch.setattr(apply_module, "atomic_write_bytes", die_before_publish)
    with pytest.raises(_Interrupt):
        _execute(plan, config, tmp_path / "manifest.jsonl")
    monkeypatch.setattr(apply_module, "atomic_write_bytes", real)
    first = read_manifest(tmp_path / "manifest.jsonl")
    assert [r.result for r in first] == ["intent"]
    assert first[0].overwritten_sha256 is not None

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        resume_records=first,
    )

    assert _hash_tree(root) == _hash_tree(control)
    outcome = next(o for o in report.outcomes if o.action_id == first[0].action_id)
    assert outcome.status == "applied"


def test_resume_dry_run_dangling_intent__previews_completion_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR-004 under intent reconciliation: a dry-run resume reports the
    pending completion as would_apply and leaves corpus and manifests alone."""
    root = tmp_path / "root"
    materialize(root, RECIPES, seeded_faker())
    config = DocmendConfig()
    plan, first = _interrupted_after_publish(root, config, tmp_path / "manifest.jsonl", monkeypatch)
    before = _hash_tree(root)

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        write=False,
        resume_records=first,
    )

    assert _hash_tree(root) == before
    assert not (tmp_path / "resume-manifest.jsonl").exists()
    outcome = next(o for o in report.outcomes if o.action_id == first[0].action_id)
    assert outcome.status == "would_apply"


def test_resume_stale_duplicate_record_out_of_order__newest_wins(tmp_path: Path) -> None:
    """PR #10 review: an apply→restore→apply chain records one action as
    applied twice; resume must reconcile against the NEWEST record even when
    the operator passes the manifests out of order — otherwise the stale
    record's after-hash raises a spurious ERR-002."""
    root = tmp_path / "root"
    materialize(root, RECIPES, seeded_faker())
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path / "manifest.jsonl")
    records = read_manifest(tmp_path / "manifest.jsonl")
    stale = records[0].model_copy(
        update={"after_sha256": "sha256:" + "f" * 64, "recorded_at": "2020-01-01T00:00:00+00:00"}
    )

    report = _execute(
        plan,
        config,
        tmp_path / "resume-manifest.jsonl",
        run_id=RESUME_RUN_ID,
        resume_records=[*records, stale][::-1],  # stale record deliberately first
    )

    outcome = next(o for o in report.outcomes if o.action_id == records[0].action_id)
    assert (outcome.status, outcome.skip_reason) == ("skipped", "already-applied")
