"""Restore engine + `docmend restore` CLI (IR-008, adr-0004, FR-006, ERR-003,
ERR-004, §12.3, §18.6).

Harness: a real write-mode `apply` (via `test_apply`'s `_plan_for`/`_execute`
helpers, imported directly — `tests/` has no `__init__.py`, so pytest's
rootless import mode puts it on `sys.path` and a bare cross-module import
works; confirmed against the full suite before relying on it here) produces
a real manifest over a real corpus, which `run_restore` then replays. CLI
cases additionally drive `docmend restore` end-to-end via `CliRunner`,
mirroring `tests/test_cli_apply.py`'s fixtures.
"""

import hashlib
import logging
from collections.abc import Iterator, Sequence
from dataclasses import replace
from pathlib import Path

import pytest
import structlog
from tests.helpers.manifest2 import header_doc, read_records, write_set
from typer.testing import CliRunner

from corpus import FileRecipe, materialize, seeded_faker
from docmend import lock
from docmend.cli import app
from docmend.config import DocmendConfig, RenameConfig
from docmend.restore import RestoreOutcome, run_restore
from docmend.writer.commit import CommitHooks
from docmend.writer.manifest import (
    ManifestChain,
    ManifestRecord,
    manifest_sha256,
    read_manifest_chain,
    read_manifest_set,
)
from test_apply import _execute, _plan_for  # pyright: ignore[reportPrivateUsage]

RESTORE_RUN_ID = "run_20260706T020000Z_00009a"


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _hash_tree(root: Path) -> dict[str, str]:
    # ".docmend-tmp" staging residue is excluded: a killed run's staged temp
    # is inert tool-owned residue by design (adr-0019/adr-0021); corpus
    # equivalence is judged on documents, not tool residue.
    return {
        str(path.relative_to(root)): _sha(path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.name.endswith(".docmend-tmp")
    }


def _records_for(tmp_path: Path) -> tuple[ManifestRecord, ...]:
    return read_records(tmp_path / "manifest.jsonl")


def _set_with(tmp_path: Path, records: Sequence[ManifestRecord]) -> ManifestChain:
    """A single-set CHAIN over the apply run's REAL validated set with its
    record list swapped for the test's (possibly synthetic) records —
    run_restore consumes chains in 2.0."""
    base = read_manifest_set(tmp_path / "manifest.jsonl")
    filled = replace(base, records=tuple(records), sha256=manifest_sha256(base.path))
    return ManifestChain(sets=(filled,))


# ---------------------------------------------------------------------------
# Engine tests (run_restore)
# ---------------------------------------------------------------------------


def test_restore_dry_run__previews_and_touches_nothing(tmp_path: Path) -> None:
    """IR-008: a dry-run restore previews every applied record without
    mutating the corpus (mirrors apply's FR-004 posture)."""
    root = tmp_path / "root"
    materialize(
        root, [FileRecipe("legacy.md", "windows-1252", "crlf", sentences=15)], seeded_faker()
    )
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    before = _hash_tree(root)

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=False,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes
    assert all(o.status == "would_restore" for o in outcomes)
    assert _hash_tree(root) == before
    assert not (tmp_path / "restore-manifest.jsonl").exists()


def test_restore_rewrite__bytes_match_before_hash(tmp_path: Path) -> None:
    """IR-008 acceptance: after a write restore, the file's bytes hash to the
    manifest's before_sha256 — FR-006's restore-reproduces-the-original claim."""
    root = tmp_path / "root"
    materialize(
        root, [FileRecipe("legacy.md", "windows-1252", "crlf", sentences=15)], seeded_faker()
    )
    original_bytes = (root / "legacy.md").read_bytes()
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    assert records[0].operation == "rewrite"

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "restored"
    assert (root / "legacy.md").read_bytes() == original_bytes
    assert _sha((root / "legacy.md").read_bytes()) == records[0].before_sha256


def test_restore_rewrite__mode_preserved(tmp_path: Path) -> None:
    """IR-008/§8.1: apply carries the source file's mode onto its rewritten
    target (`writer/apply.py`'s own `source.stat().st_mode` pass-through) —
    restore must carry that same mode back onto the reinstated original,
    not leave it at `atomic_write_bytes`'s temp-file default (0o600)."""
    root = tmp_path / "root"
    materialize(
        root, [FileRecipe("legacy.md", "windows-1252", "crlf", sentences=15)], seeded_faker()
    )
    (root / "legacy.md").chmod(0o644)
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    assert records[0].operation == "rewrite"
    # Confirms the fixture actually exercises mode preservation on the apply
    # side too, so a restore-side regression alone is what this test catches.
    assert (root / "legacy.md").stat().st_mode & 0o777 == 0o644

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "restored"
    restored = root / "legacy.md"
    assert restored.stat().st_mode & 0o777 == 0o644
    assert _sha(restored.read_bytes()) == records[0].before_sha256


def test_restore_rename__file_moved_back(tmp_path: Path) -> None:
    """A pure rename record restores by moving the file back — .md gone, .txt
    back with identical bytes (no content was ever changed)."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "clean.txt").write_bytes(b"already clean\n")
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True)
    records = _records_for(tmp_path)
    assert records[0].operation == "rename"

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "restored"
    assert not (root / "clean.md").exists()
    assert (root / "clean.txt").read_bytes() == b"already clean\n"


def test_restore_rename_and_rewrite__original_reproduced(tmp_path: Path) -> None:
    """A rename_and_rewrite record restores the original path with the
    pre-apply bytes and removes the applied target."""
    root = tmp_path / "root"
    materialize(
        root, [FileRecipe("legacy.txt", "windows-1252", "crlf", sentences=15)], seeded_faker()
    )
    original_bytes = (root / "legacy.txt").read_bytes()
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    assert records[0].operation == "rename_and_rewrite"

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "restored"
    assert (root / "legacy.txt").read_bytes() == original_bytes
    assert not (root / "legacy.md").exists()


def test_restore_rename_and_rewrite_overwrite__both_halves_reinstated(tmp_path: Path) -> None:
    """A rename_and_rewrite record that also clobbered a live collision target
    restores BOTH halves in the loss-proof order: the original path gets its
    pre-apply bytes, and the target gets the clobbered file's original bytes
    back (not left holding the transformed payload)."""
    root = tmp_path / "root"
    materialize(
        root, [FileRecipe("legacy.txt", "windows-1252", "crlf", sentences=15)], seeded_faker()
    )
    original_bytes = (root / "legacy.txt").read_bytes()
    config = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
    plan = _plan_for(root, config)
    (root / "legacy.md").write_bytes(b"old target content\n")
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    assert records[0].operation == "rename_and_rewrite"
    assert records[0].overwritten_sha256 is not None
    assert records[0].overwritten_backup_path is not None

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "restored"
    assert (root / "legacy.txt").read_bytes() == original_bytes
    assert (root / "legacy.md").read_bytes() == b"old target content\n"


def test_restore_lifo__later_mutations_undone_first(tmp_path: Path) -> None:
    """adr-0004: replay is LIFO by seq. A two-record manifest over the same
    path lineage (a real apply, plus a hand-crafted second mutation stacked on
    top — a second real apply would be a no-op, FR-017) restores to the FIRST
    record's before state, not the intermediate one."""
    root = tmp_path / "root"
    materialize(root, [FileRecipe("legacy.md", "utf-8", "crlf")], seeded_faker())
    original_bytes = (root / "legacy.md").read_bytes()
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    record1 = next(r for r in _records_for(tmp_path) if r.result == "applied")
    after1_bytes = (root / "legacy.md").read_bytes()
    assert record1.after_sha256 == _sha(after1_bytes)

    # Simulate a second mutation stacked on top of the first (a manually
    # crafted record, since a second real apply is idempotent and produces no
    # action, FR-017): the live file now holds "after2" bytes, and a backup of
    # the pre-second-mutation ("after1") bytes exists for its own record.
    after2_bytes = after1_bytes + b"a second edit\n"
    backup2 = tmp_path / "backup2.bin"
    backup2.write_bytes(after1_bytes)
    (root / "legacy.md").write_bytes(after2_bytes)
    record2 = ManifestRecord(
        run_id=record1.run_id,
        action_id=f"{record1.run_id}/a2",
        docmend_id=record1.docmend_id,
        seq=3,
        recorded_at=record1.recorded_at,
        operation="rewrite",
        original_path=record1.original_path,
        target_path=record1.target_path,
        backup_path=str(backup2),
        before_sha256=_sha(after1_bytes),
        after_sha256=_sha(after2_bytes),
        result="applied",
        error=None,
    )

    outcomes = run_restore(
        _set_with(tmp_path, [record1, record2]),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert [o.status for o in outcomes] == ["restored", "restored"]
    assert (root / "legacy.md").read_bytes() == original_bytes


def test_restore_modified_since_apply__skipped_never_clobbers(tmp_path: Path) -> None:
    """decision 10: a file edited after apply fails its after_sha256 re-check
    and is skipped, never clobbered — the edit survives untouched while other
    records in the same run still restore."""
    root = tmp_path / "root"
    materialize(root, [FileRecipe("legacy.md", "utf-8", "crlf")], seeded_faker())
    root.mkdir(exist_ok=True)
    (root / "clean.txt").write_bytes(b"already clean\n")
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    assert len([r for r in records if r.result == "applied"]) == 2  # 2.0: + intents

    edited = b"edited after apply, never to be lost\n"
    (root / "legacy.md").write_bytes(edited)

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    by_path = {o.path: o for o in outcomes}
    legacy_outcome = by_path[str((root / "legacy.md").resolve())]
    assert legacy_outcome.status == "skipped"
    assert legacy_outcome.detail == "modified-since-apply"
    assert (root / "legacy.md").read_bytes() == edited

    clean_outcome = by_path[str((root / "clean.txt").resolve())]
    assert clean_outcome.status == "restored"
    assert not (root / "clean.md").exists()
    assert (root / "clean.txt").read_bytes() == b"already clean\n"


def test_restore_no_backup_record__skipped(tmp_path: Path) -> None:
    """FR-005: a record with no backup reference (--allow-no-backup at apply)
    is skipped, not clobbered — the operator's own strategy is the recovery
    path there, by design."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "solo.txt").write_bytes(b"solo body\r\n")
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, allow_no_backup=True)
    records = _records_for(tmp_path)
    assert records[0].backup_path is None

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "skipped"
    assert outcomes[0].detail is not None and outcomes[0].detail.startswith("no-backup")
    # Issue #15: the detail must point at the declared preservation as the recovery path.
    assert "preservation" in outcomes[0].detail


def test_restore_backup_hash_mismatch__failed_err004(tmp_path: Path) -> None:
    """ERR-004: a corrupted backup fails the restore before any mutation —
    the live (applied) file is left exactly as it was."""
    root = tmp_path / "root"
    materialize(
        root, [FileRecipe("legacy.md", "windows-1252", "crlf", sentences=15)], seeded_faker()
    )
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    assert records[0].backup_path is not None
    Path(records[0].backup_path).write_bytes(b"corrupted backup bytes")
    live_before = (root / "legacy.md").read_bytes()

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "failed"
    assert outcomes[0].detail is not None
    assert outcomes[0].detail.startswith("ERR-004")
    assert (root / "legacy.md").read_bytes() == live_before


def test_restore_overwrite_record__clobbered_target_reinstated(tmp_path: Path) -> None:
    """An overwrite-collision rename record restores BOTH halves: the
    clobbered target's original content back at the target path, and the
    renamed source back at its original path."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"clean\n")
    config = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
    plan = _plan_for(root, config)
    (root / "a.md").write_bytes(b"old target content\n")
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    assert records[0].overwritten_sha256 is not None
    assert records[0].overwritten_backup_path is not None

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "restored"
    assert (root / "a.md").read_bytes() == b"old target content\n"
    assert (root / "a.txt").read_bytes() == b"clean\n"


def test_restore_overwrite_backup_corrupt__nothing_mutated(tmp_path: Path) -> None:
    """codex CR-003: a corrupted overwritten-target backup fails the restore
    (ERR-004) before any write/unlink — both the applied target and every
    other live file stay byte-for-byte unchanged."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"clean\n")
    config = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
    plan = _plan_for(root, config)
    (root / "a.md").write_bytes(b"old target content\n")
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    assert records[0].overwritten_backup_path is not None
    Path(records[0].overwritten_backup_path).write_bytes(b"corrupted")
    before = _hash_tree(root)

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "failed"
    assert outcomes[0].detail is not None
    assert "ERR-004" in outcomes[0].detail
    assert _hash_tree(root) == before


def test_restore_source_backup_corrupt__nothing_mutated(tmp_path: Path) -> None:
    """codex CR-003 sibling: a corrupted source backup on a rename_and_rewrite
    record fails the restore before any mutation — the applied target
    survives unchanged and the original path stays absent."""
    root = tmp_path / "root"
    materialize(
        root, [FileRecipe("legacy.txt", "windows-1252", "crlf", sentences=15)], seeded_faker()
    )
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    assert records[0].operation == "rename_and_rewrite"
    assert records[0].backup_path is not None
    Path(records[0].backup_path).write_bytes(b"corrupted")
    target_before = (root / "legacy.md").read_bytes()

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "failed"
    assert outcomes[0].detail is not None
    assert "ERR-004" in outcomes[0].detail
    assert (root / "legacy.md").read_bytes() == target_before
    assert not (root / "legacy.txt").exists()


def test_restore_mutation_phase_failure__no_file_lost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """codex CR-003 residual: an environmental failure mid-mutation (the
    unlink half of a rename_and_rewrite restore, monkeypatched to fail) leaves
    a SUPERSET on disk — the reinstated original AND the still-present applied
    target — never a missing file. Re-running restore then surfaces the
    leftover as a collision skip, not silent damage."""
    root = tmp_path / "root"
    materialize(
        root, [FileRecipe("legacy.txt", "windows-1252", "crlf", sentences=15)], seeded_faker()
    )
    original_bytes = (root / "legacy.txt").read_bytes()
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    target_bytes = (root / "legacy.md").read_bytes()

    original_unlink = Path.unlink
    victim = (root / "legacy.md").resolve()

    def _fail_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == victim:
            raise OSError("simulated unlink failure")
        original_unlink(self, *args, **kwargs)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(Path, "unlink", _fail_unlink)

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "failed"
    assert outcomes[0].detail is not None
    assert outcomes[0].detail.startswith("ERR-003")
    # Superset: original reinstated with pre-apply bytes, applied target survives.
    assert (root / "legacy.txt").read_bytes() == original_bytes
    assert (root / "legacy.md").read_bytes() == target_bytes

    monkeypatch.setattr(Path, "unlink", original_unlink)
    rerun = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest-2.jsonl",
    )
    assert rerun[0].status == "skipped"
    assert rerun[0].detail is not None
    assert "collision" in rerun[0].detail


def test_restore_records_its_own_manifest(tmp_path: Path) -> None:
    """A write restore appends one inverse record per restoration to its own
    run manifest — swapped paths/hashes, no backup (restore of a restore is
    not itself preserved, mirroring apply's own manifest semantics)."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "clean.txt").write_bytes(b"already clean\n")
    materialize(root, [FileRecipe("legacy.md", "utf-8", "crlf")], seeded_faker())
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    records = _records_for(tmp_path)
    applied = [r for r in records if r.result == "applied"]
    assert len(applied) == 2  # 2.0: intents ride along as evidence
    manifest_out = tmp_path / "restore-manifest.jsonl"

    outcomes = run_restore(
        _set_with(tmp_path, records),
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=manifest_out,
    )
    assert all(o.status == "restored" for o in outcomes)

    restore_records = read_records(manifest_out)
    # 2.0 (adr-0019): restore journals too — one intent+terminal pair per
    # inverse, each naming the exact apply action it undoes.
    assert len(restore_records) == 2 * len(applied)
    assert [r.result for r in restore_records] == ["intent", "applied"] * len(applied)
    by_original = {r.original_path: r for r in applied}
    by_action = {r.action_id: r for r in applied}
    for inverse in restore_records:
        forward = by_original[inverse.target_path]
        assert inverse.original_path == forward.target_path
        assert inverse.target_path == forward.original_path
        assert inverse.before_sha256 == (forward.after_sha256 or forward.before_sha256)
        assert inverse.after_sha256 == forward.before_sha256
        assert inverse.backup_path is None
        assert inverse.undoes_action_id in by_action
        assert inverse.undoes_run_id == forward.run_id
        if inverse.result == "intent":
            assert inverse.source_identity is not None
            assert inverse.expected_published_identity is not None


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_logging() -> Iterator[None]:
    """restore configures real handlers on the root logger; restore them per test."""
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
    """restore acquires the OQ-027 run lock; keep its state dir out of the
    real $XDG_STATE_HOME/~/.local/state so tests never touch developer state."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))


def _make_plan_cli(corpus: Path, *, out: Path = Path("plan.json")) -> Path:
    result = runner.invoke(app, ["plan", str(corpus), "--out", str(out)])
    assert result.exit_code in (0, 1), result.output
    return out


def _apply_cli(plan_path: Path, *extra: str) -> None:
    result = runner.invoke(app, ["apply", str(plan_path), "--write", *extra])
    assert result.exit_code == 0, result.output


def _manifest_path(tmp_path: Path) -> Path:
    manifests = list((tmp_path / ".docmend").glob("docmend-*-manifest.jsonl"))
    assert len(manifests) == 1
    return manifests[0]


class TestRestoreCliFlagConflicts:
    def test_restore_write_and_global_dry_run__mutually_exclusive_exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IR-005/IR-008: the global -n conflicts with --write, mirroring apply."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "clean.txt").write_bytes(b"already clean\n")
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path)
        manifest_path = _manifest_path(tmp_path)

        result = runner.invoke(app, ["-n", "restore", "--manifest", str(manifest_path), "--write"])

        assert result.exit_code == 2, result.output


class TestRestoreCliInputErrors:
    def test_restore_without_inputs__exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IR-008/2.0: at least one of --manifest/--run-id is required; the
        two are COMBINABLE (an attempt chain may span both input forms)."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["restore"])
        assert result.exit_code == 2, result.output

    def test_restore_manifest_and_run_id_combined__one_chain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A resumed run's two manifests restore as ONE chain regardless of
        which input form names each file."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "clean.txt").write_bytes(b"already clean\n")
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path)
        manifest_path = _manifest_path(tmp_path)
        run_id = manifest_path.name.removeprefix("docmend-").removesuffix("-manifest.jsonl")

        result = runner.invoke(
            app, ["restore", "--manifest", str(manifest_path), "--run-id", run_id]
        )
        # The same file supplied twice is a duplicate-run chain error — but
        # naming ONE attempt via either form alone succeeds identically:
        assert result.exit_code == 2, result.output
        by_flag = runner.invoke(app, ["restore", "--manifest", str(manifest_path)])
        by_id = runner.invoke(app, ["restore", "--run-id", run_id])
        assert by_flag.exit_code == 0, by_flag.output
        assert by_id.exit_code == 0, by_id.output

    def test_restore_run_id__resolves_sidecar_convention(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--run-id resolves .docmend/docmend-<ID>-manifest.jsonl (OQ-034)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "clean.txt").write_bytes(b"already clean\n")
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path)
        manifest_path = _manifest_path(tmp_path)
        run_id = manifest_path.name.removeprefix("docmend-").removesuffix("-manifest.jsonl")

        result = runner.invoke(app, ["restore", "--run-id", run_id, "--write"])

        assert result.exit_code == 0, result.output
        assert not (corpus / "clean.md").exists()
        assert (corpus / "clean.txt").read_bytes() == b"already clean\n"

    def test_restore_corrupt_interior_manifest__exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """adr-0006: a corrupt interior manifest record hard-aborts (ERR-008 family)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "clean.txt").write_bytes(b"already clean\n")
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path)
        manifest_path = _manifest_path(tmp_path)
        manifest_path.write_text("not json at all\n")

        result = runner.invoke(app, ["restore", "--manifest", str(manifest_path)])

        assert result.exit_code == 2, result.output

    def test_restore_header_only_manifest__friendly_message_exit_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """2.0: the friendly no-op case is a HEADER-ONLY manifest (a run killed
        between its header and first record — nothing durably recorded)."""
        monkeypatch.chdir(tmp_path)
        empty = write_set(tmp_path / "empty-manifest.jsonl", header_doc(source_root=str(tmp_path)))

        result = runner.invoke(app, ["restore", "--manifest", str(empty)])

        assert result.exit_code == 0, result.output
        assert "nothing to restore" in result.output

    def test_restore_zero_byte_manifest__malformed_exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """2.0: a zero-byte file has no header — malformed input (ERR-008),
        never a silent no-op (a real 2.0 manifest always starts with its header)."""
        monkeypatch.chdir(tmp_path)
        empty = tmp_path / "empty-manifest.jsonl"
        empty.write_text("")

        result = runner.invoke(app, ["restore", "--manifest", str(empty)])

        assert result.exit_code == 2, result.output
        assert "no header" in result.output


class TestRestoreCliWrites:
    def test_restore_clean_write__exit_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A clean write restore (nothing skipped/failed) exits 0."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "clean.txt").write_bytes(b"already clean\n")
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path)
        manifest_path = _manifest_path(tmp_path)

        result = runner.invoke(app, ["restore", "--manifest", str(manifest_path), "--write"])

        assert result.exit_code == 0, result.output
        assert "restored: 1" in result.output
        assert not (corpus / "clean.md").exists()
        assert (corpus / "clean.txt").exists()

    def test_restore_findings__exit_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A restore with any skipped/failed record exits 1 (§18.5 findings)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "solo.txt").write_bytes(b"solo body\r\n")
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path, "--allow-no-backup")
        manifest_path = _manifest_path(tmp_path)

        result = runner.invoke(app, ["restore", "--manifest", str(manifest_path), "--write"])

        assert result.exit_code == 1, result.output
        assert "skipped: 1" in result.output

    def test_restore_external_preservation_overwrite__skipped_untouched_exit_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """codex CR-NEW-003: a pure overwrite rename applied under
        --preserved-by external (no tool backup) restores as a skip, never a
        false success while the clobbered target stays missing — exit 1, and
        the corpus is byte-for-byte unmutated from its post-apply state."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "a.txt").write_bytes(b"clean\n")
        (corpus / "a.md").write_bytes(b"old target content\n")
        (tmp_path / "docmend.toml").write_text('[rename]\non_collision = "overwrite"\n')
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path, "--preserved-by", "external")
        manifest_path = _manifest_path(tmp_path)
        before = {
            str(p.relative_to(corpus)): p.read_bytes()
            for p in sorted(corpus.rglob("*"))
            if p.is_file()
        }

        result = runner.invoke(app, ["restore", "--manifest", str(manifest_path), "--write"])

        assert result.exit_code == 1, result.output
        assert "skipped: 1" in result.output
        after = {
            str(p.relative_to(corpus)): p.read_bytes()
            for p in sorted(corpus.rglob("*"))
            if p.is_file()
        }
        assert after == before

    def test_restore_id_filter__restores_only_matching_document(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--id restricts replay to the named docmend.id values."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "a.txt").write_bytes(b"already clean a\n")
        (corpus / "b.txt").write_bytes(b"already clean b\n")
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path)
        manifest_path = _manifest_path(tmp_path)
        records = read_records(manifest_path)
        by_path = {Path(r.original_path).name: r for r in records}
        keep_id = by_path["a.txt"].docmend_id

        result = runner.invoke(
            app, ["restore", "--manifest", str(manifest_path), "--write", "--id", keep_id]
        )

        assert result.exit_code == 0, result.output
        assert "restored: 1" in result.output
        assert (corpus / "a.txt").exists()
        assert (corpus / "b.md").exists()  # untouched by the filtered-out record


# 2.0: restore's lock keys on the VALIDATED header's source_root (adr-0019);
# the per-record source_root field and the pre-1.2 commonpath fallback are gone
# with the clean break. Lock behavior is covered end-to-end by
# TestRestoreCliLock below (including the nested-commonpath regression).


class TestRestoreCliLock:
    def test_restore_locked_root__exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AW-005: a live lock on the manifest's common root refuses restore, exit 3."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "clean.txt").write_bytes(b"already clean\n")
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path)
        manifest_path = _manifest_path(tmp_path)
        held = lock.acquire(corpus, run_id="run_20260706T000000Z_00004c", command="restore")
        try:
            result = runner.invoke(app, ["restore", "--manifest", str(manifest_path), "--write"])
            assert result.exit_code == 3, result.output
        finally:
            held.release()

    def test_restore_locked_source_root__nested_files__exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OQ-036 regression: when every mutated file lives in a SUBDIRECTORY (so
        the manifest's commonpath narrows below the source root), a live lock on
        the source root must STILL refuse restore. Pre-fix, restore keyed on the
        nested commonpath and slipped past this lock (exit 0)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        nested = corpus / "nested"
        nested.mkdir(parents=True)
        (nested / "deep.txt").write_bytes(b"already clean\n")
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path)
        manifest_path = _manifest_path(tmp_path)
        # Lock what a concurrent apply holds — the source root, not the nested dir.
        held = lock.acquire(corpus, run_id="run_20260706T000000Z_00004c", command="apply")
        try:
            result = runner.invoke(app, ["restore", "--manifest", str(manifest_path), "--write"])
            assert result.exit_code == 3, result.output
        finally:
            held.release()


class TestRestoreCapabilityLine:
    """Issue #15 (suggestion 2): restore states the run's undo capability UP
    FRONT, derived from the manifest alone — before any per-row skip appears."""

    def test_external_preservation_manifest__renames_only_stated_on_dry_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "a.txt").write_bytes(b"line one\r\nline two\r\n")  # content rewrite
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path, "--preserved-by", "external")
        manifest_path = _manifest_path(tmp_path)

        result = runner.invoke(app, ["restore", "--manifest", str(manifest_path)])

        assert "restore capability: renames-only — 1 content mutation(s)" in result.output
        # The line must NOT assert which FR-005 strategy was used — the manifest
        # cannot distinguish git/external/--allow-no-backup (PR #16 review).
        assert "whatever preservation covered the apply run" in result.output

    def test_tool_backup_manifest__no_capability_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "a.txt").write_bytes(b"line one\r\nline two\r\n")
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path, "--backup-dir", str(tmp_path / "backups"))
        manifest_path = _manifest_path(tmp_path)

        result = runner.invoke(app, ["restore", "--manifest", str(manifest_path)])

        assert "renames-only" not in result.output


# ---------------------------------------------------------------------------
# Interrupted-restore convergence (adr-0019 adjudication; Plan B review CR-005)
# ---------------------------------------------------------------------------


class _Kill(RuntimeError):
    """Injected kill — not WriteError/OSError, so _restore_one cannot absorb it."""


def _applied_chain(tmp_path: Path, recipe_kind: str) -> tuple[Path, Path]:
    """A real write apply over one file of the requested mutation kind;
    returns (corpus root, apply manifest path)."""
    import docmend.restore as restore_module

    del restore_module
    root = tmp_path / "root"
    if recipe_kind == "rewrite":
        materialize(
            root, [FileRecipe("legacy.md", "windows-1252", "crlf", sentences=15)], seeded_faker()
        )
    elif recipe_kind == "rename":
        root.mkdir()
        (root / "clean.txt").write_bytes(b"already clean\n")
    else:  # rename_and_rewrite
        materialize(
            root, [FileRecipe("legacy.txt", "windows-1252", "crlf", sentences=15)], seeded_faker()
        )
    config = DocmendConfig()
    plan = _plan_for(root, config)
    _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
    return root, tmp_path / "manifest.jsonl"


def _interrupted_restore(
    tmp_path: Path,
    apply_manifest: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    patch_name: str,
    after: bool,
) -> Path:
    """Run a write restore with a kill injected around `patch_name` in the
    restore module; returns the interrupted restore manifest path."""
    import docmend.restore as restore_module

    real = getattr(restore_module, patch_name)

    def dying(*args: object, **kwargs: object) -> None:
        if after:
            real(*args, **kwargs)
        raise _Kill(f"injected kill {'after' if after else 'before'} {patch_name}")

    monkeypatch.setattr(restore_module, patch_name, dying)
    restore_out = tmp_path / "restore-manifest.jsonl"
    with pytest.raises(_Kill):
        run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=restore_out,
        )
    monkeypatch.setattr(restore_module, patch_name, real)
    return restore_out


RERUN_ID = "run_20260706T030000Z_0000b1"


def _rerun(apply_manifest: Path, restore_manifest: Path, out: Path) -> list[RestoreOutcome]:
    return run_restore(
        read_manifest_chain([apply_manifest, restore_manifest]),
        run_id=RERUN_ID,
        write=True,
        only_ids=None,
        manifest_out=out,
    )


class TestInterruptedRestoreConvergence:
    def test_rewrite_killed_before_publish__rerun_restores(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, apply_manifest = _applied_chain(tmp_path, "rewrite")
        before_restore = _hash_tree(root)
        restore_manifest = _interrupted_restore(
            tmp_path, apply_manifest, monkeypatch, patch_name="publish_staged", after=False
        )
        assert _hash_tree(root) == before_restore  # kill was pre-mutation
        [dangling] = read_records(restore_manifest)
        assert dangling.result == "intent"

        outcomes = _rerun(apply_manifest, restore_manifest, tmp_path / "rerun-manifest.jsonl")

        assert [o.status for o in outcomes] == ["restored"]
        record = read_records(apply_manifest)[1]
        assert _sha((root / "legacy.md").read_bytes()) == record.before_sha256

    def test_rewrite_killed_after_publish__rerun_adopts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, apply_manifest = _applied_chain(tmp_path, "rewrite")
        restore_manifest = _interrupted_restore(
            tmp_path, apply_manifest, monkeypatch, patch_name="publish_staged", after=True
        )
        record = read_records(apply_manifest)[1]
        assert _sha((root / "legacy.md").read_bytes()) == record.before_sha256  # mutated

        outcomes = _rerun(apply_manifest, restore_manifest, tmp_path / "rerun-manifest.jsonl")

        assert [o.status for o in outcomes] == ["restored"]
        # Adoption: the rerun appended ONLY the closure terminal, no re-mutation.
        rerun_records = read_records(tmp_path / "rerun-manifest.jsonl")
        assert [r.result for r in rerun_records] == ["applied"]

    def test_rename_killed_mid_link_unlink__rerun_finishes(self, tmp_path: Path) -> None:
        """The both-names lossless intermediate: kill between link and unlink."""
        root, apply_manifest = _applied_chain(tmp_path, "rename")

        def kill_after_link(step: str, path: Path) -> None:
            if step == "unlink":
                raise _Kill("injected kill between link and unlink")

        restore_out = tmp_path / "restore-manifest.jsonl"
        with pytest.raises(_Kill):
            run_restore(
                read_manifest_chain([apply_manifest]),
                run_id=RESTORE_RUN_ID,
                write=True,
                only_ids=None,
                manifest_out=restore_out,
                hooks=CommitHooks(kill_after_link),
            )
        assert (root / "clean.md").exists() and (root / "clean.txt").exists()  # both names

        outcomes = _rerun(apply_manifest, restore_out, tmp_path / "rerun-manifest.jsonl")

        assert [o.status for o in outcomes] == ["restored"]
        assert not (root / "clean.md").exists()
        assert (root / "clean.txt").read_bytes() == b"already clean\n"


class TestRestoreCommitBoundary:
    def test_applied_file_swapped_same_bytes_before_inverse__refused(self, tmp_path: Path) -> None:
        root, apply_manifest = _applied_chain(tmp_path, "rewrite")
        target = root / "legacy.md"
        applied = target.read_bytes()

        def swap(step: str, path: Path) -> None:
            if step == "publish":
                target.unlink()
                target.write_bytes(applied)

        restore_out = tmp_path / "restore-manifest.jsonl"
        outcomes = run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=restore_out,
            hooks=CommitHooks(swap),
        )

        assert outcomes[0].status == "failed"
        assert outcomes[0].detail is not None
        assert "external-interference" in outcomes[0].detail
        assert target.read_bytes() == applied
        assert [record.result for record in read_records(restore_out)] == ["intent", "failed"]

    def test_symlinked_applied_file__failed_not_followed(self, tmp_path: Path) -> None:
        root, apply_manifest = _applied_chain(tmp_path, "rewrite")
        target = root / "legacy.md"
        referent = root / "referent.md"
        target.rename(referent)
        payload = referent.read_bytes()
        target.symlink_to(referent)
        restore_out = tmp_path / "restore-manifest.jsonl"

        outcomes = run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=restore_out,
        )

        assert outcomes[0].status == "failed"
        assert outcomes[0].detail is not None and "ERR-002" in outcomes[0].detail
        assert referent.read_bytes() == payload
        assert target.is_symlink()
        assert not restore_out.exists()

    def test_rename_inverse__reinstated_original_replaced__dangling(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        (root / "clean.txt").write_bytes(b"already clean\n")
        (root / "clean.md").write_bytes(b"old target\n")
        config = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
        plan = _plan_for(root, config)
        _execute(plan, config, tmp_path, write=True, backup_root=tmp_path / "backups")
        apply_manifest = tmp_path / "manifest.jsonl"
        original = root / "clean.txt"
        applied = root / "clean.md"

        def swap(step: str, path: Path) -> None:
            if step == "replace-target":
                original.unlink()
                original.write_bytes(b"interloper")

        restore_out = tmp_path / "restore-manifest.jsonl"
        outcomes = run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=restore_out,
            hooks=CommitHooks(swap),
        )

        assert outcomes[0].status == "failed"
        assert outcomes[0].detail is not None and "ERR-002" in outcomes[0].detail
        assert original.read_bytes() == b"interloper"
        assert applied.exists()
        assert [record.result for record in read_records(restore_out)] == ["intent"]

    def test_restore_failed_terminal_then_retry__converges(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import docmend.restore as restore_module

        root, apply_manifest = _applied_chain(tmp_path, "rewrite")

        def broken_stage(*args: object, **kwargs: object) -> object:
            raise WriteError("simulated staging failure")

        from docmend.writer.atomic import WriteError

        real_stage = restore_module.stage_bytes
        monkeypatch.setattr(restore_module, "stage_bytes", broken_stage)
        failed_out = tmp_path / "failed-restore.jsonl"
        first = run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=failed_out,
        )
        assert first[0].status == "failed"
        monkeypatch.setattr(restore_module, "stage_bytes", real_stage)

        retry = run_restore(
            read_manifest_chain([apply_manifest, failed_out]),
            run_id=RERUN_ID,
            write=True,
            only_ids=None,
            manifest_out=tmp_path / "retry-restore.jsonl",
        )

        assert retry[0].status == "restored"
        record = read_records(apply_manifest)[1]
        assert _sha((root / "legacy.md").read_bytes()) == record.before_sha256

    def test_rename_destination_appears_before_inverse__failed_terminal(
        self, tmp_path: Path
    ) -> None:
        root, apply_manifest = _applied_chain(tmp_path, "rename")
        original = root / "clean.txt"
        applied = root / "clean.md"

        def occupy_original(step: str, path: Path) -> None:
            if step == "publish":
                original.write_bytes(b"late arrival")

        restore_out = tmp_path / "restore-manifest.jsonl"
        outcomes = run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=restore_out,
            hooks=CommitHooks(occupy_original),
        )

        assert outcomes[0].status == "failed"
        assert outcomes[0].detail is not None and "ERR-003" in outcomes[0].detail
        assert original.read_bytes() == b"late arrival"
        assert applied.exists()
        assert [record.result for record in read_records(restore_out)] == ["intent", "failed"]

    def test_rename_and_rewrite_error_after_reinstatement__intent_dangling(
        self, tmp_path: Path
    ) -> None:
        root, apply_manifest = _applied_chain(tmp_path, "rename_and_rewrite")
        original = root / "legacy.txt"
        applied = root / "legacy.md"

        def fail_after_reinstate(step: str, path: Path) -> None:
            if step == "unlink":
                raise OSError(5, "I/O error")

        restore_out = tmp_path / "restore-manifest.jsonl"
        outcomes = run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=restore_out,
            hooks=CommitHooks(fail_after_reinstate),
        )

        assert outcomes[0].status == "failed"
        assert outcomes[0].detail is not None and "intermediate preserved" in outcomes[0].detail
        assert original.exists()
        assert applied.exists()
        assert [record.result for record in read_records(restore_out)] == ["intent"]

    def test_rnr_killed_after_reinstate__rerun_finishes_cleanup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, apply_manifest = _applied_chain(tmp_path, "rename_and_rewrite")
        restore_manifest = _interrupted_restore(
            tmp_path, apply_manifest, monkeypatch, patch_name="publish_staged", after=True
        )
        # Reinstatement landed; the applied target still present.
        assert (root / "legacy.txt").exists() and (root / "legacy.md").exists()

        outcomes = _rerun(apply_manifest, restore_manifest, tmp_path / "rerun-manifest.jsonl")

        assert [o.status for o in outcomes] == ["restored"]
        assert not (root / "legacy.md").exists()
        record = read_records(apply_manifest)[1]
        assert _sha((root / "legacy.txt").read_bytes()) == record.before_sha256

    def test_identity_probe__reinstated_original_replaced__rerun_refuses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CR-005 restore identity probe: after the kill, the reinstated
        original is replaced by a NEW inode with identical bytes — the rerun
        must refuse (ERR-002) and leave the applied target untouched."""
        root, apply_manifest = _applied_chain(tmp_path, "rename_and_rewrite")
        restore_manifest = _interrupted_restore(
            tmp_path, apply_manifest, monkeypatch, patch_name="publish_staged", after=True
        )
        original = root / "legacy.txt"
        same_bytes = original.read_bytes()
        original.unlink()
        original.write_bytes(same_bytes)  # identical bytes, different inode

        outcomes = _rerun(apply_manifest, restore_manifest, tmp_path / "rerun-manifest.jsonl")

        assert [o.status for o in outcomes] == ["failed"]
        assert outcomes[0].detail is not None and "ERR-002" in outcomes[0].detail
        assert (root / "legacy.md").exists()  # cleanup was refused, nothing destroyed


class TestRestoreSelectorMiss:
    def test_id_matching_nothing__stderr_finding_exit_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """2026-07-10 review medium theme: a typo'd/stale --id must surface as
        a finding (exit 1), never a silent all-zero success."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "clean.txt").write_bytes(b"already clean\n")
        plan_path = _make_plan_cli(corpus)
        _apply_cli(plan_path)
        manifest_path = _manifest_path(tmp_path)

        result = runner.invoke(
            app,
            [
                "restore",
                "--manifest",
                str(manifest_path),
                "--write",
                "--id",
                "01980000-0000-7000-8000-00000000dead",
            ],
        )

        assert result.exit_code == 1, result.output
        assert "no manifest record matches" in result.output


class TestReducerDrivenStates:
    def test_dangling_apply_intent__skipped_finding(self, tmp_path: Path) -> None:
        """Adjudicating APPLY intents is resume's job — restore surfaces the
        dangling intent as a finding instead of guessing."""
        root, apply_manifest = _applied_chain(tmp_path, "rewrite")
        del root
        # Truncate the terminal: the intent dangles.
        lines = apply_manifest.read_text().splitlines()
        apply_manifest.write_text("\n".join(lines[:-1]) + "\n")

        outcomes = run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=tmp_path / "restore-manifest.jsonl",
        )

        assert [o.status for o in outcomes] == ["skipped"]
        assert outcomes[0].detail is not None
        assert "resume the apply run" in outcomes[0].detail

    def test_fully_restored_chain__already_restored_skips(self, tmp_path: Path) -> None:
        root, apply_manifest = _applied_chain(tmp_path, "rewrite")
        del root
        first_out = tmp_path / "restore-manifest.jsonl"
        first = run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=first_out,
        )
        assert [o.status for o in first] == ["restored"]

        rerun = run_restore(
            read_manifest_chain([apply_manifest, first_out]),
            run_id=RERUN_ID,
            write=True,
            only_ids=None,
            manifest_out=tmp_path / "rerun-manifest.jsonl",
        )

        assert [(o.status, o.detail) for o in rerun] == [("skipped", "already-restored")]
        assert not (tmp_path / "rerun-manifest.jsonl").exists()  # nothing recorded

    def test_staging_failure__failed_record_without_intent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import docmend.restore as restore_module

        root, apply_manifest = _applied_chain(tmp_path, "rewrite")
        del root

        def broken_stage(*args: object, **kwargs: object) -> object:
            raise WriteError("simulated staging failure")

        from docmend.writer.atomic import WriteError

        monkeypatch.setattr(restore_module, "stage_bytes", broken_stage)
        restore_out = tmp_path / "restore-manifest.jsonl"
        outcomes = run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=restore_out,
        )

        assert [o.status for o in outcomes] == ["failed"]
        [record] = read_records(restore_out)
        assert record.result == "failed"
        assert record.source_identity is None  # pre-mutation failure: no intent


class TestRestoreContainmentRefusal:
    def test_out_of_root_record__exit_3_before_any_mutation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DMR-03 closure at the CLI: a crafted manifest whose recorded paths
        escape its own source_root is a SAFETY REFUSAL (exit 3, adr-0012) —
        nothing is read or mutated past validation."""
        monkeypatch.chdir(tmp_path)
        victim = tmp_path / "outside-victim.txt"
        victim.write_bytes(b"must never be touched\n")
        from tests.helpers.manifest2 import header_doc, record_doc, write_set

        crafted = write_set(
            tmp_path / "crafted.jsonl",
            header_doc(source_root=str(tmp_path / "corpus")),
            record_doc(1, original_path=str(victim), target_path=str(victim)),
        )

        result = runner.invoke(app, ["restore", "--manifest", str(crafted), "--write"])

        assert result.exit_code == 3, result.output
        assert "manifest-containment" in result.output
        assert victim.read_bytes() == b"must never be touched\n"


class TestRestoreInputEdges:
    def test_backup_deleted_before_restore__f5_refuses_at_validation(self, tmp_path: Path) -> None:
        """A deleted backup object is caught by the F5 trust boundary AT CHAIN
        VALIDATION — before run_restore reads anything (Plan B review CR-002;
        stricter than the old per-record ERR-004 arm, which now covers only
        content corruption of a present, regular backup file)."""
        from docmend.writer.manifest import ManifestContainmentError

        root, apply_manifest = _applied_chain(tmp_path, "rewrite")
        del root
        # Read without object checks to locate the backup, then delete it.
        loaded = read_manifest_set(apply_manifest, check_backup_objects=False)
        record = next(r for r in loaded.records if r.result == "applied")
        assert record.backup_path is not None
        Path(record.backup_path).unlink()

        with pytest.raises(ManifestContainmentError, match="missing"):
            read_manifest_chain([apply_manifest])

    def test_backup_corrupted_before_restore__failed_err004(self, tmp_path: Path) -> None:
        """Content corruption of a present regular backup file passes F5's
        structural checks and fails the per-record hash verification."""
        root, apply_manifest = _applied_chain(tmp_path, "rewrite")
        del root
        loaded = read_manifest_set(apply_manifest, check_backup_objects=False)
        record = next(r for r in loaded.records if r.result == "applied")
        assert record.backup_path is not None
        Path(record.backup_path).write_bytes(b"corrupted backup bytes\n")

        outcomes = run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=tmp_path / "restore-manifest.jsonl",
        )

        assert [o.status for o in outcomes] == ["failed"]
        assert outcomes[0].detail is not None and "ERR-004" in outcomes[0].detail

    def test_applied_file_deleted__unreadable_skip(self, tmp_path: Path) -> None:
        root, apply_manifest = _applied_chain(tmp_path, "rewrite")
        (root / "legacy.md").unlink()

        outcomes = run_restore(
            read_manifest_chain([apply_manifest]),
            run_id=RESTORE_RUN_ID,
            write=True,
            only_ids=None,
            manifest_out=tmp_path / "restore-manifest.jsonl",
        )

        assert [(o.status, o.detail) for o in outcomes] == [
            ("skipped", "unreadable: applied file missing or unreadable")
        ]

    def test_failed_apply_state__nothing_to_undo(self, tmp_path: Path) -> None:
        from tests.helpers.manifest2 import chain_of, record_doc

        from docmend.writer.manifest import ManifestRecord as MR

        intent = MR.model_validate(record_doc(1, result="intent"))
        failed = MR.model_validate(
            record_doc(1, seq=2, result="failed", after_sha256=None)
            | {"error": {"class": "ERR-003", "message": "boom"}}
        )
        outcomes = run_restore(
            chain_of([intent, failed]),
            run_id=RESTORE_RUN_ID,
            write=False,
            only_ids=None,
            manifest_out=tmp_path / "restore-manifest.jsonl",
        )
        assert outcomes == []
