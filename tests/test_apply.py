"""Apply engine (FR-003/FR-004/FR-006/FR-011/FR-012/FR-017-report-half/FR-018,
NFR-002/NFR-004, EC-005, AW-002/AW-004, ERR-002/ERR-003/ERR-004/ERR-005).

End-to-end over real files: scan -> plan -> execute_plan, asserting per-file
outcomes, manifest records, and corpus state. Real filesystem (OQ-019).
"""

import hashlib
import shutil
from collections import Counter
from pathlib import Path

import pytest
from tests.helpers.manifest2 import read_records

from corpus import FileRecipe, materialize, seeded_faker
from docmend import discovery, planning
from docmend.artifacts import sha256_of_file
from docmend.config import DocmendConfig, RenameConfig, WriteConfig
from docmend.plan import ActionProvenance, ArtifactRef, Plan, PlanAction, PlanTotals
from docmend.restore import run_restore
from docmend.transform.dispatch import Operation, apply_text_transforms, classify_suffix
from docmend.transform.encoding import decode_source, encode_utf8
from docmend.writer import apply as apply_module
from docmend.writer.apply import execute_plan
from docmend.writer.backup import BackupError
from docmend.writer.gate import ApplyOptions
from docmend.writer.manifest import read_manifest_chain, read_manifest_set

RUN_ID = "run_20260706T000000Z_00008f"
PLAN_RUN_ID = "run_20260706T000000Z_00008e"
GENERATED_AT = "2026-07-06T00:00:00+00:00"
NOW = "2026-07-06T00:00:01+00:00"


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _plan_for(root: Path, config: DocmendConfig) -> Plan:
    inventory = discovery.scan(root, config, run_id=PLAN_RUN_ID, generated_at=GENERATED_AT)
    ref = ArtifactRef(path="inv.json", run_id=PLAN_RUN_ID, sha256="sha256:" + "0" * 64)
    return planning.build_plan(
        inventory, config, run_id=PLAN_RUN_ID, generated_at=GENERATED_AT, inventory_ref=ref
    )


def _execute(plan: Plan, config: DocmendConfig, tmp_path: Path, **kwargs: object):
    options = ApplyOptions(
        write=bool(kwargs.pop("write", False)),
        backup_root=kwargs.pop("backup_root", None),  # type: ignore[arg-type]
        preserved_by=kwargs.pop("preserved_by", None),  # type: ignore[arg-type]
        allow_no_backup=bool(kwargs.pop("allow_no_backup", False)),
    )
    assert not kwargs
    return execute_plan(
        plan,
        config,
        run_id=RUN_ID,
        plan_ref=ArtifactRef(path="plan.json", run_id=PLAN_RUN_ID, sha256="sha256:" + "1" * 64),
        plan_sha256="sha256:" + "1" * 64,
        options=options,
        manifest_path=tmp_path / "manifest.jsonl",
        started_at=GENERATED_AT,
        now=lambda: NOW,
    )


def _hash_tree(root: Path) -> dict[str, str]:
    """Recursive per-file hash snapshot, keyed by path relative to `root`."""
    return {
        str(path.relative_to(root)): sha256_of_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_dry_run_default__writes_nothing_reports_would_apply(tmp_path: Path) -> None:
    """FR-004, NFR-004: a dry run inspects but mutates nothing."""
    root = tmp_path / "root"
    materialize(root, [FileRecipe("a.txt", "utf-8", "crlf")], seeded_faker())
    config = DocmendConfig()
    plan = _plan_for(root, config)
    assert len(plan.actions) == 1
    before = _hash_tree(root)

    report = _execute(plan, config, tmp_path, write=False)

    assert _hash_tree(root) == before
    assert not (tmp_path / "manifest.jsonl").exists()
    assert len(report.outcomes) == 1
    outcome = report.outcomes[0]
    assert outcome.status == "would_apply"
    assert outcome.after_sha256 is None
    assert report.dry_run is True
    assert report.totals.would_apply == 1
    assert report.totals.applied == report.totals.skipped == report.totals.failed == 0


def test_write__header_carries_resolved_source_root(tmp_path: Path) -> None:
    """Manifest 2.0 (adr-0019, was OQ-036): the HEADER carries the apply run's
    resolved source root so `docmend restore` can key its lock on it (AW-005);
    records no longer repeat it per line."""
    root = tmp_path / "root"
    materialize(root, [FileRecipe("a.txt", "utf-8", "crlf")], seeded_faker())
    config = DocmendConfig()
    plan = _plan_for(root, config)

    _execute(plan, config, tmp_path, write=True)

    loaded = read_manifest_set(tmp_path / "manifest.jsonl")
    assert loaded.records
    assert plan.source_root is not None
    assert loaded.header.source_root == str(Path(plan.source_root).resolve())
    assert loaded.header.kind == "apply"


def test_write_rewrite_in_place__utf8_lf_and_manifest(tmp_path: Path) -> None:
    """FR-006, FR-008, NFR-002, DR-004: in-place rewrite, verified backup, manifest record."""
    root = tmp_path / "root"
    materialize(
        root, [FileRecipe("legacy.md", "windows-1252", "crlf", sentences=15)], seeded_faker()
    )
    target_file = root / "legacy.md"
    original_bytes = target_file.read_bytes()
    before_sha = _sha(original_bytes)
    config = DocmendConfig()
    plan = _plan_for(root, config)
    action = {a.path: a for a in plan.actions}["legacy.md"]
    assert action.target_path is None  # .md keeps its path (adr-0016)

    backup_root = tmp_path / "backups"
    report = _execute(plan, config, tmp_path, write=True, backup_root=backup_root)

    detected = action.provenance.detected_encoding
    encoding_name = detected.name if detected is not None else "utf-8"
    text = decode_source(original_bytes, bom=None, encoding_name=encoding_name)
    transformed, _ops = apply_text_transforms(
        text,
        classify_suffix(".md"),
        trim_trailing_ws=True,
        final_newline=True,
        collapse_max=3,
        tab_width=None,
    )
    expected_bytes = encode_utf8(transformed)

    assert target_file.read_bytes() == expected_bytes
    outcome = report.outcomes[0]
    assert outcome.status == "applied"
    assert outcome.before_sha256 == before_sha
    assert outcome.after_sha256 == _sha(expected_bytes)
    assert outcome.after_sha256 == sha256_of_file(target_file)

    records = read_records(tmp_path / "manifest.jsonl")
    # 2.0: intent + terminal per mutation; the terminal carries the outcome.
    assert [r.result for r in records] == ["intent", "applied"]
    record = records[1]
    assert record.operation == "rewrite"
    assert record.backup_path is not None
    backup_bytes = Path(record.backup_path).read_bytes()
    assert _sha(backup_bytes) == record.before_sha256 == before_sha


def test_write_rename_only__link_semantics(tmp_path: Path) -> None:
    """FR-010, FR-011: rename is the only op; identical bytes at the new path."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "clean.txt").write_bytes(b"already clean\n")
    config = DocmendConfig()
    plan = _plan_for(root, config)
    action = {a.path: a for a in plan.actions}["clean.txt"]
    assert action.operations == ["rename"]

    report = _execute(plan, config, tmp_path, write=True)

    assert not (root / "clean.txt").exists()
    new_path = root / "clean.md"
    assert new_path.read_bytes() == b"already clean\n"
    outcome = report.outcomes[0]
    assert outcome.status == "applied"
    assert outcome.after_sha256 == outcome.before_sha256

    records = read_records(tmp_path / "manifest.jsonl")
    assert records[0].operation == "rename"
    assert records[0].after_sha256 == records[0].before_sha256


def test_write_rename_and_rewrite__source_survives_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR-002: a publish failure never leaves the source touched."""
    root = tmp_path / "root"
    materialize(root, [FileRecipe("legacy.txt", "utf-8", "crlf")], seeded_faker())
    original_bytes = (root / "legacy.txt").read_bytes()
    config = DocmendConfig()
    plan = _plan_for(root, config)
    action = {a.path: a for a in plan.actions}["legacy.txt"]
    assert "rename" in action.operations and len(action.operations) > 1

    def _boom(*_a: object, **_kw: object) -> None:
        raise apply_module.WriteError("simulated publish failure")

    monkeypatch.setattr(apply_module, "publish_staged", _boom)

    report = _execute(plan, config, tmp_path, write=True)

    outcome = report.outcomes[0]
    assert outcome.status == "failed"
    assert outcome.error is not None
    assert outcome.error.error_class == "ERR-003"
    assert outcome.after_sha256 is None
    assert (root / "legacy.txt").read_bytes() == original_bytes

    records = read_records(tmp_path / "manifest.jsonl")
    # 1.3: the write-ahead intent precedes the mutation attempt; the failure
    # closes it, so this dangling-free pair is exactly what resume expects.
    assert [r.result for r in records] == ["intent", "failed"]


def test_stale_hash__skipped_batch_continues(tmp_path: Path) -> None:
    """FR-003, ERR-002, AW-004: a stale hash skips just that action."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"one\n")
    (root / "b.txt").write_bytes(b"two\n")
    config = DocmendConfig()
    plan = _plan_for(root, config)
    assert {a.path for a in plan.actions} == {"a.txt", "b.txt"}

    (root / "a.txt").write_bytes(b"one CHANGED\n")

    report = _execute(plan, config, tmp_path, write=True)

    outcomes = {o.path: o for o in report.outcomes}
    assert outcomes["a.txt"].status == "skipped"
    assert outcomes["a.txt"].skip_reason == "stale-hash"
    assert outcomes["b.txt"].status == "applied"
    assert (root / "a.txt").read_bytes() == b"one CHANGED\n"
    assert not (root / "b.txt").exists()
    assert (root / "b.md").read_bytes() == b"two\n"


def test_unreadable_at_apply__skipped(tmp_path: Path) -> None:
    """ERR-005: a file deleted between plan and apply is skipped, not fatal."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"here\n")
    config = DocmendConfig()
    plan = _plan_for(root, config)
    (root / "a.txt").unlink()

    report = _execute(plan, config, tmp_path, write=True)

    outcome = report.outcomes[0]
    assert outcome.status == "skipped"
    assert outcome.skip_reason == "unreadable"


def test_collision_policies__skip_fail_overwrite(tmp_path: Path) -> None:
    """FR-011, AW-002, EC-001: the three collision policies at apply time."""
    # skip: target untouched, outcome skipped/collision.
    skip_root = tmp_path / "skip"
    skip_root.mkdir()
    (skip_root / "a.txt").write_bytes(b"clean\n")
    skip_config = DocmendConfig()
    skip_plan = _plan_for(skip_root, skip_config)
    (skip_root / "a.md").write_bytes(b"live collision\n")
    skip_report = _execute(skip_plan, skip_config, tmp_path / "skip-run", write=True)
    outcome = skip_report.outcomes[0]
    assert outcome.status == "skipped"
    assert outcome.skip_reason == "collision"
    assert (skip_root / "a.md").read_bytes() == b"live collision\n"
    assert (skip_root / "a.txt").exists()

    # fail: batch aborts after recording the collision; later actions never run.
    fail_root = tmp_path / "fail"
    fail_root.mkdir()
    (fail_root / "a.txt").write_bytes(b"clean\n")
    (fail_root / "b.txt").write_bytes(b"clean too\n")
    fail_config = DocmendConfig(rename=RenameConfig(on_collision="fail"))
    fail_plan = _plan_for(fail_root, fail_config)
    assert [a.path for a in fail_plan.actions] == ["a.txt", "b.txt"]
    (fail_root / "a.md").write_bytes(b"live collision\n")
    fail_report = _execute(fail_plan, fail_config, tmp_path / "fail-run", write=True)
    # Report 2.0 partition: the abort's unreached action is explicit.
    assert [(o.status, o.skip_reason) for o in fail_report.outcomes] == [
        ("skipped", "collision"),
        ("not-attempted", None),
    ]
    assert (fail_root / "b.txt").exists()  # second action never ran
    assert not (fail_root / "b.md").exists()

    # overwrite: applied, manifest carries the clobbered target's provenance.
    ow_root = tmp_path / "overwrite"
    ow_root.mkdir()
    (ow_root / "a.txt").write_bytes(b"clean\n")
    ow_config = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
    ow_plan = _plan_for(ow_root, ow_config)
    (ow_root / "a.md").write_bytes(b"old target content\n")
    old_target_sha = _sha(b"old target content\n")
    ow_backup_root = tmp_path / "overwrite-backups"
    ow_report = _execute(
        ow_plan, ow_config, tmp_path / "overwrite-run", write=True, backup_root=ow_backup_root
    )
    ow_outcome = ow_report.outcomes[0]
    assert ow_outcome.status == "applied"
    assert (ow_root / "a.md").read_bytes() == b"clean\n"
    ow_records = read_records((tmp_path / "overwrite-run") / "manifest.jsonl")
    ow_record = ow_records[0]
    assert ow_record.overwritten_sha256 == old_target_sha
    assert ow_record.overwritten_backup_path is not None
    assert _sha(Path(ow_record.overwritten_backup_path).read_bytes()) == old_target_sha


def test_overwrite_target_unreadable__failed_recorded_in_manifest(tmp_path: Path) -> None:
    """FR-011, FR-018, DR-003, DR-004: an unreadable overwrite target fails, with a matching
    manifest record — the pre-mutation ERR-003 branch must not skip DR-004's reconciliation."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"clean\n")
    config = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
    plan = _plan_for(root, config)
    original_bytes = (root / "a.txt").read_bytes()

    # Live collision whose target is a directory: target.exists() is True (so
    # the overwrite policy clobbers), but target.read_bytes() raises OSError.
    (root / "a.md").mkdir()

    report = _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")

    outcome = report.outcomes[0]
    assert outcome.status == "failed"
    assert outcome.error is not None
    assert outcome.error.error_class == "ERR-003"
    assert report.totals.failed == 1
    assert (root / "a.txt").read_bytes() == original_bytes

    records = read_records(tmp_path / "manifest.jsonl")
    assert len(records) == 1
    assert records[0].result == "failed"


def test_overwrite_target_backup_failure__failed_recorded_in_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-011, FR-018, DR-003, DR-004: a failed overwrite-target backup fails, with a matching
    manifest record — the pre-mutation ERR-004 branch must not skip DR-004's reconciliation."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"clean\n")
    config = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
    plan = _plan_for(root, config)
    original_bytes = (root / "a.txt").read_bytes()
    (root / "a.md").write_bytes(b"old target content\n")
    original_target_bytes = (root / "a.md").read_bytes()

    def _boom(*_a: object, **_kw: object) -> Path:
        raise BackupError("simulated overwrite-target backup failure")

    monkeypatch.setattr(
        apply_module, "backup_file", _boom
    )  # first call is the overwritten-target backup

    report = _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")

    outcome = report.outcomes[0]
    assert outcome.status == "failed"
    assert outcome.error is not None
    assert outcome.error.error_class == "ERR-004"
    assert report.totals.failed == 1
    assert (root / "a.txt").read_bytes() == original_bytes
    assert (root / "a.md").read_bytes() == original_target_bytes

    records = read_records(tmp_path / "manifest.jsonl")
    assert len(records) == 1
    assert records[0].result == "failed"


def test_backup_failure__aborts_before_original_touched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-006, ERR-004: a failed backup never touches the original."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "note.md").write_bytes(b"line1\r\nline2\r\n")
    config = DocmendConfig()
    plan = _plan_for(root, config)
    original_bytes = (root / "note.md").read_bytes()

    def _boom(*_a: object, **_kw: object) -> Path:
        raise BackupError("simulated backup failure")

    monkeypatch.setattr(apply_module, "backup_file", _boom)

    report = _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")

    outcome = report.outcomes[0]
    assert outcome.status == "failed"
    assert outcome.error is not None
    assert outcome.error.error_class == "ERR-004"
    assert (root / "note.md").read_bytes() == original_bytes


def test_snapshot_filter_enforced__foreign_action_excluded(tmp_path: Path) -> None:
    """FR-012: the plan's action must still pass the snapshot's own filters at apply time."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"clean\n")
    config = DocmendConfig()
    plan = _plan_for(root, config)
    assert len(plan.actions) == 1

    narrowed_config = config.model_copy(
        update={"paths": config.paths.model_copy(update={"include": ["**/*.rst"]})}
    )
    narrowed_plan = plan.model_copy(update={"config": narrowed_config.model_dump(mode="json")})

    report = _execute(narrowed_plan, narrowed_config, tmp_path, write=True)

    outcome = report.outcomes[0]
    assert outcome.status == "skipped"
    assert outcome.skip_reason == "excluded"


def test_shrink_invariant_recheck__skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """EC-005: an apply-time recompute that would shrink content is refused."""
    root = tmp_path / "root"
    materialize(root, [FileRecipe("a.txt", "utf-8", "crlf")], seeded_faker())
    original_bytes = (root / "a.txt").read_bytes()
    config = DocmendConfig()
    plan = _plan_for(root, config)

    def _shrink(text: str, file_class: object, **_kw: object) -> tuple[str, list[object]]:
        return "", []

    monkeypatch.setattr(apply_module, "apply_text_transforms", _shrink)

    report = _execute(plan, config, tmp_path, write=True)

    outcome = report.outcomes[0]
    assert outcome.status == "skipped"
    assert outcome.skip_reason == "shrink-invariant"
    assert (root / "a.txt").read_bytes() == original_bytes


def test_operations_divergence__failed_err006(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decision 4: recomputed operations diverging from the plan's is a hard failure."""
    root = tmp_path / "root"
    materialize(root, [FileRecipe("a.txt", "utf-8", "crlf")], seeded_faker())
    config = DocmendConfig()
    plan = _plan_for(root, config)

    def _diverge(text: str, file_class: object, **_kw: object) -> tuple[str, list[object]]:
        return text, ["frontmatter_migrate"]

    monkeypatch.setattr(apply_module, "apply_text_transforms", _diverge)

    report = _execute(plan, config, tmp_path, write=True)

    outcome = report.outcomes[0]
    assert outcome.status == "failed"
    assert outcome.error is not None
    assert outcome.error.error_class == "ERR-006"


def test_containment_resolve_escape__skipped(tmp_path: Path) -> None:
    """Section 13.5: a parent dir swapped for a symlink since plan time never escapes the root."""
    root = tmp_path / "root"
    sub = root / "sub"
    sub.mkdir(parents=True)
    content = b"line1\r\nline2\r\n"
    (sub / "a.md").write_bytes(content)
    config = DocmendConfig()
    plan = _plan_for(root, config)
    assert {a.path for a in plan.actions} == {"sub/a.md"}

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "a.md").write_bytes(content)
    before_outside = sorted(p.name for p in outside.iterdir())

    shutil.rmtree(sub)
    sub.symlink_to(outside, target_is_directory=True)

    report = _execute(plan, config, tmp_path, write=True)

    outcome = report.outcomes[0]
    assert outcome.status == "skipped"
    assert outcome.skip_reason == "containment"
    assert (outside / "a.md").read_bytes() == content
    assert sorted(p.name for p in outside.iterdir()) == before_outside


def test_report_counts_reconcile__and_manifest_seq_monotonic(tmp_path: Path) -> None:
    """FR-018, DR-003, DR-004: totals reconcile with outcomes; manifest seq is monotonic."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"clean\n")  # rename-only, applies
    materialize(root, [FileRecipe("b.md", "utf-8", "crlf")], seeded_faker())  # rewrite, applies
    (root / "c.txt").write_bytes(b"stale\n")  # goes stale-hash
    (root / "d.txt").write_bytes(b"vanishes\n")  # deleted before apply
    config = DocmendConfig()
    plan = _plan_for(root, config)
    assert {a.path for a in plan.actions} == {"a.txt", "b.md", "c.txt", "d.txt"}

    (root / "c.txt").write_bytes(b"stale CHANGED\n")
    (root / "d.txt").unlink()

    report = _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")

    counts = Counter(o.status for o in report.outcomes)
    assert report.totals.applied == counts.get("applied", 0)
    assert report.totals.would_apply == counts.get("would_apply", 0)
    assert report.totals.skipped == counts.get("skipped", 0)
    assert report.totals.failed == counts.get("failed", 0)
    assert sum(report.totals.__dict__.values()) == len(report.outcomes)

    records = read_records(tmp_path / "manifest.jsonl")
    assert [r.seq for r in records] == list(range(1, len(records) + 1))
    # 2.0 journal-every-mutation: each applied action is an intent+terminal
    # pair; skips write nothing (this fixture produces no failed actions).
    assert len(records) == 2 * counts.get("applied", 0)


def test_empty_plan__clean_report(tmp_path: Path) -> None:
    """A plan with zero actions produces a clean report and no manifest file."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "already-clean.md").write_bytes(b"already clean\n")
    config = DocmendConfig()
    plan = _plan_for(root, config)
    assert plan.actions == []

    report = _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")

    assert report.outcomes == []
    assert report.totals.applied == report.totals.skipped == 0
    assert not (tmp_path / "manifest.jsonl").exists()


def test_dry_run_overwrite_collision_with_backup_dir__writes_nothing(tmp_path: Path) -> None:
    """codex CR-001; FR-004, NFR-004: dry run inspects a live collision but writes nothing."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"clean\n")
    backup_dir = tmp_path / "backups"
    config = DocmendConfig(
        rename=RenameConfig(on_collision="overwrite"), write=WriteConfig(backup_dir=backup_dir)
    )
    plan = _plan_for(root, config)
    (root / "a.md").write_bytes(b"live collision\n")
    before = _hash_tree(tmp_path)

    report = _execute(plan, config, tmp_path, write=False, backup_root=backup_dir)

    outcome = report.outcomes[0]
    assert outcome.status == "would_apply"
    assert not backup_dir.exists()
    assert _hash_tree(tmp_path) == before


def test_all_actions_skip_in_write_mode__no_manifest_file(tmp_path: Path) -> None:
    """Both actions go stale; the lazy-open manifest never touches disk."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"one\n")
    (root / "b.txt").write_bytes(b"two\n")
    config = DocmendConfig()
    plan = _plan_for(root, config)
    (root / "a.txt").write_bytes(b"one CHANGED\n")
    (root / "b.txt").write_bytes(b"two CHANGED\n")

    report = _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")

    assert report.totals.skipped == 2
    assert not (tmp_path / "manifest.jsonl").exists()


def test_rename_and_rewrite_unlink_failure__publish_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """codex CR-NEW-004: a failed source unlink rolls the publish back, no-collision and overwrite."""
    original_unlink = Path.unlink

    def _fail_unlink_for(victim: Path):
        def _wrapper(self: Path, *args: object, **kwargs: object) -> None:
            if self == victim:
                msg = "simulated unlink failure"
                raise OSError(msg)
            original_unlink(self, *args, **kwargs)  # pyright: ignore[reportArgumentType]

        return _wrapper

    # Sub-case (a): no collision — the published target is removed on rollback.
    root_a = tmp_path / "a"
    materialize(root_a, [FileRecipe("legacy.txt", "utf-8", "crlf")], seeded_faker())
    original_bytes_a = (root_a / "legacy.txt").read_bytes()
    config_a = DocmendConfig()
    plan_a = _plan_for(root_a, config_a)
    source_a = Path(plan_a.source_root or "") / "legacy.txt"
    monkeypatch.setattr(Path, "unlink", _fail_unlink_for(source_a))

    report_a = _execute(
        plan_a, config_a, tmp_path / "a-run", write=True, backup_root=tmp_path / "a-backups"
    )
    outcome_a = report_a.outcomes[0]
    assert outcome_a.status == "failed"
    assert outcome_a.error is not None
    assert outcome_a.error.error_class == "ERR-003"
    assert (root_a / "legacy.txt").read_bytes() == original_bytes_a
    assert not (root_a / "legacy.md").exists()
    records_a = read_records((tmp_path / "a-run") / "manifest.jsonl")
    assert [r.result for r in records_a] == ["intent", "failed"]
    monkeypatch.setattr(Path, "unlink", original_unlink)

    # Sub-case (b): live collision under overwrite policy — the clobbered
    # target's original bytes are restored after the rollback.
    root_b = tmp_path / "b"
    materialize(root_b, [FileRecipe("legacy.txt", "utf-8", "crlf")], seeded_faker())
    original_bytes_b = (root_b / "legacy.txt").read_bytes()
    (root_b / "legacy.md").write_bytes(b"old target content\n")
    config_b = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
    plan_b = _plan_for(root_b, config_b)
    source_b = Path(plan_b.source_root or "") / "legacy.txt"
    monkeypatch.setattr(Path, "unlink", _fail_unlink_for(source_b))

    report_b = _execute(
        plan_b, config_b, tmp_path / "b-run", write=True, backup_root=tmp_path / "b-backups"
    )
    outcome_b = report_b.outcomes[0]
    assert outcome_b.status == "failed"
    assert outcome_b.error is not None
    assert outcome_b.error.error_class == "ERR-003"
    assert (root_b / "legacy.txt").read_bytes() == original_bytes_b
    assert (root_b / "legacy.md").read_bytes() == b"old target content\n"


def _sha256(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _dmr01_action(
    run_id: str,
    seq: int,
    path: str,
    ops: list[Operation],
    target: str | None,
    data: bytes,
) -> PlanAction:
    return PlanAction(
        action_id=f"{run_id}/a{seq}",
        docmend_id=f"00000000-0000-7000-8000-00000000000{seq}",
        path=path,
        source_sha256=_sha256(data),
        source_size_bytes=len(data),
        operations=ops,
        target_path=target,
        provenance=ActionProvenance(
            detected_encoding=None,
            newline_style="crlf" if b"\r" in data else "lf",
        ),
    )


def test_dmr01_colliding_backup_keys__both_preserved_and_restorable(tmp_path: Path) -> None:
    """DMR-01 defense in depth: a crafted plan with an in-place rewrite of a.md
    AND a rename a.txt -> a.md (overwrite policy) must preserve every byte
    stream under distinct backup keys, and restore must reproduce both
    originals. The Task 5 output ledger stops the planner emitting this plan,
    but execute_plan accepts crafted plans — the backup layer must not rely on
    the planner being correct."""
    root = tmp_path / "corpus"
    root.mkdir()
    md_original = b"alpha\r\n"  # dirty: CRLF forces a rewrite action
    txt_original = b"bravo\n"  # clean content: rename-only action
    (root / "a.md").write_bytes(md_original)
    (root / "a.txt").write_bytes(txt_original)

    config = DocmendConfig()
    config = config.model_copy(
        update={"rename": config.rename.model_copy(update={"on_collision": "overwrite"})}
    )
    run_id = "run_20260710T000000Z_00d0a1"

    plan = Plan(
        run_id=run_id,
        generated_at="2026-07-10T00:00:00+00:00",
        generated_by="docmend test",
        inventory_ref=ArtifactRef(path="unused", run_id=run_id, sha256=_sha256(b"")),
        source_root=str(root),
        config=config.model_dump(mode="json"),
        actions=[
            _dmr01_action(run_id, 1, "a.md", ["normalize_newlines"], None, md_original),
            _dmr01_action(run_id, 2, "a.txt", ["rename"], "a.md", txt_original),
        ],
        skips=[],
        totals=PlanTotals(actions=2, skips=0),
    )

    backup_root = tmp_path / "backups"
    manifest_path = tmp_path / "manifest.jsonl"
    report = execute_plan(
        plan,
        config,
        run_id=run_id,
        plan_ref=ArtifactRef(path="unused", run_id=run_id, sha256=_sha256(b"")),
        plan_sha256=_sha256(b""),
        options=ApplyOptions(
            write=True, backup_root=backup_root, preserved_by=None, allow_no_backup=False
        ),
        manifest_path=manifest_path,
        started_at="2026-07-10T00:00:00+00:00",
    )
    assert report.totals.applied == 2, [o.status for o in report.outcomes]

    records = read_records(manifest_path)
    backup_paths = {r.backup_path for r in records if r.backup_path is not None} | {
        r.overwritten_backup_path for r in records if r.overwritten_backup_path is not None
    }
    # a1's source copy of a.md, a2's source copy of a.txt, and a2's
    # overwritten-role copy of the (already rewritten) a.md — three distinct
    # keys, none clobbered.
    assert len(backup_paths) == 3
    stored = {Path(p).read_bytes() for p in backup_paths}
    assert stored == {md_original, txt_original, b"alpha\n"}

    outcomes = run_restore(
        read_manifest_chain([manifest_path]),
        run_id="run_20260710T000001Z_00d0a2",
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )
    assert all(o.status == "restored" for o in outcomes), [
        (o.path, o.status, o.detail) for o in outcomes
    ]
    assert (root / "a.md").read_bytes() == md_original
    assert (root / "a.txt").read_bytes() == txt_original


class TestJournalEveryMutation:
    """adr-0019 (DMR-04): EVERY mutation kind appends a fsync'd intent with
    the durable object identities BEFORE any corpus name is touched, and a
    terminal repeating the immutable fields after."""

    IMMUTABLE = (
        "action_id",
        "docmend_id",
        "operation",
        "original_path",
        "target_path",
        "before_sha256",
        "backup_path",
        "overwritten_backup_path",
        "overwritten_sha256",
        "source_identity",
        "target_identity",
        "expected_published_identity",
    )

    def test_every_kind__intent_then_terminal_with_identities(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        materialize(
            root,
            [FileRecipe("rw.md", "windows-1252", "crlf", sentences=15)],
            seeded_faker(),
        )
        (root / "mv.txt").write_bytes(b"clean\n")
        materialize(
            root,
            [FileRecipe("both.txt", "windows-1252", "crlf", sentences=15)],
            seeded_faker(),
        )
        config = DocmendConfig()
        plan = _plan_for(root, config)
        assert len(plan.actions) == 3

        _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")

        records = read_records(tmp_path / "manifest.jsonl")
        by_action: dict[str, list[object]] = {}
        for record in records:
            by_action.setdefault(record.action_id, []).append(record)
        assert len(by_action) == 3
        for group in by_action.values():
            intent, terminal = group  # exactly two records per action
            assert intent.result == "intent"  # type: ignore[union-attr]
            assert terminal.result == "applied"  # type: ignore[union-attr]
            assert intent.source_identity is not None  # type: ignore[union-attr]
            assert intent.expected_published_identity is not None  # type: ignore[union-attr]
            for field in self.IMMUTABLE:
                assert getattr(intent, field) == getattr(terminal, field), field

    def test_pure_rename__expected_identity_is_source_inode(self, tmp_path: Path) -> None:
        """A rename moves the inode: expected_published_identity == the source
        identity, and the LIVE published file carries that exact inode."""
        root = tmp_path / "root"
        root.mkdir()
        (root / "clean.txt").write_bytes(b"already clean\n")
        config = DocmendConfig()
        plan = _plan_for(root, config)
        source_stat = (root / "clean.txt").stat()

        _execute(plan, config, tmp_path, write=True)

        [intent, _terminal] = read_records(tmp_path / "manifest.jsonl")
        assert intent.expected_published_identity == intent.source_identity
        assert intent.source_identity is not None
        assert intent.source_identity.ino == source_stat.st_ino
        published = (root / "clean.md").stat()
        assert intent.expected_published_identity is not None
        assert published.st_ino == intent.expected_published_identity.ino

    def test_rewrite__expected_identity_is_staged_inode_now_live(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        materialize(
            root, [FileRecipe("legacy.md", "windows-1252", "crlf", sentences=15)], seeded_faker()
        )
        config = DocmendConfig()
        plan = _plan_for(root, config)

        _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")

        [intent, _terminal] = read_records(tmp_path / "manifest.jsonl")
        assert intent.expected_published_identity != intent.source_identity
        live = (root / "legacy.md").stat()
        assert intent.expected_published_identity is not None
        assert live.st_ino == intent.expected_published_identity.ino

    def test_pre_mutation_failure__failed_record_without_intent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A staging failure precedes any corpus-name mutation: the manifest
        records `failed` with NO intent and null identities."""
        root = tmp_path / "root"
        materialize(
            root, [FileRecipe("legacy.md", "windows-1252", "crlf", sentences=15)], seeded_faker()
        )
        config = DocmendConfig()
        plan = _plan_for(root, config)

        def broken_stage(*args: object, **kwargs: object) -> object:
            raise apply_module.WriteError("simulated staging failure")

        monkeypatch.setattr(apply_module, "stage_bytes", broken_stage)
        report = _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")

        assert report.outcomes[0].status == "failed"
        [record] = read_records(tmp_path / "manifest.jsonl")
        assert record.result == "failed"
        assert record.source_identity is None
        assert record.expected_published_identity is None


def test_no_clobber_race_lost__intent_closed_report_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-011 race window: a target appearing between the collision check and
    the publish is external interference (ERR-002). The REPORT keeps the
    collision skip; the MANIFEST closes the intent with a failed terminal so
    it never dangles for a live run."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "clean.txt").write_bytes(b"already clean\n")
    config = DocmendConfig()
    plan = _plan_for(root, config)

    real = apply_module.rename_no_clobber

    def race_lost(*args: object, **kwargs: object) -> None:
        raise FileExistsError("target appeared inside the race window")

    monkeypatch.setattr(apply_module, "rename_no_clobber", race_lost)
    report = _execute(plan, config, tmp_path, write=True)
    monkeypatch.setattr(apply_module, "rename_no_clobber", real)

    outcome = report.outcomes[0]
    assert (outcome.status, outcome.skip_reason) == ("skipped", "collision")
    records = read_records(tmp_path / "manifest.jsonl")
    assert [r.result for r in records] == ["intent", "failed"]
    assert records[1].error is not None
    assert records[1].error.error_class == "ERR-002"


def test_fail_policy_abort__trailing_actions_reported_not_attempted(tmp_path: Path) -> None:
    """DMR-05 accounting half (report 2.0): the `fail` collision policy aborts
    mid-plan; every unexecuted trailing action must appear in the report as
    `not-attempted` — the partition invariant: each plan action exactly once."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"clean a\n")
    (root / "z.txt").write_bytes(b"clean z, never reached\n")
    config = DocmendConfig(rename=RenameConfig(on_collision="fail"))
    plan = _plan_for(root, config)
    assert [a.path for a in plan.actions] == ["a.txt", "z.txt"]
    # The colliding target appears AFTER planning — the apply-time `fail`
    # policy is what aborts (a plan-time collision would just skip a.txt).
    (root / "a.md").write_bytes(b"occupies a.txt's target\n")

    report = _execute(plan, config, tmp_path, write=True)

    statuses = [(o.path, o.status) for o in report.outcomes]
    assert statuses == [("a.txt", "skipped"), ("z.txt", "not-attempted")]
    assert report.totals.not_attempted == 1
    assert report.totals.skipped == 1
    assert len(report.outcomes) == len(plan.actions)  # full partition
