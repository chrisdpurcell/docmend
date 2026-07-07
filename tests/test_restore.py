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
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

from corpus import FileRecipe, materialize, seeded_faker
from docmend import lock
from docmend.cli import app
from docmend.config import DocmendConfig, RenameConfig
from docmend.restore import run_restore
from docmend.writer.manifest import ManifestRecord, read_manifest
from test_apply import _execute, _plan_for  # pyright: ignore[reportPrivateUsage]

RESTORE_RUN_ID = "run_20260706T020000Z_00009a"


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): _sha(path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _records_for(tmp_path: Path) -> list[ManifestRecord]:
    return read_manifest(tmp_path / "manifest.jsonl")


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
        records,
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
        records,
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
        records,
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
        records,
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
        records,
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
        records,
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
    record1 = _records_for(tmp_path)[0]
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
        seq=2,
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
        [record1, record2],
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
    assert len(records) == 2

    edited = b"edited after apply, never to be lost\n"
    (root / "legacy.md").write_bytes(edited)

    outcomes = run_restore(
        records,
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
        records,
        run_id=RESTORE_RUN_ID,
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )

    assert outcomes[0].status == "skipped"
    assert outcomes[0].detail == "no-backup"


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
        records,
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
        records,
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
        records,
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
        records,
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
        records,
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
        records,
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
    assert len(records) == 2
    manifest_out = tmp_path / "restore-manifest.jsonl"

    outcomes = run_restore(
        records, run_id=RESTORE_RUN_ID, write=True, only_ids=None, manifest_out=manifest_out
    )
    assert all(o.status == "restored" for o in outcomes)

    restore_records = read_manifest(manifest_out)
    assert len(restore_records) == len(records)
    by_original = {r.original_path: r for r in records}
    for inverse in restore_records:
        forward = by_original[inverse.target_path]
        assert inverse.original_path == forward.target_path
        assert inverse.target_path == forward.original_path
        assert inverse.before_sha256 == (forward.after_sha256 or forward.before_sha256)
        assert inverse.after_sha256 == forward.before_sha256
        assert inverse.backup_path is None


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
    def test_restore_manifest_and_run_id__mutually_exclusive_exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IR-008: exactly one of --manifest/--run-id is required."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "m.jsonl").write_text("")

        result = runner.invoke(
            app, ["restore", "--manifest", "m.jsonl", "--run-id", "run_20260706T000000Z_000001"]
        )
        assert result.exit_code == 2, result.output

        result = runner.invoke(app, ["restore"])
        assert result.exit_code == 2, result.output

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

    def test_restore_empty_manifest__friendly_message_exit_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty manifest (no applied records) is a friendly no-op, not an error."""
        monkeypatch.chdir(tmp_path)
        empty = tmp_path / "empty-manifest.jsonl"
        empty.write_text("")

        result = runner.invoke(app, ["restore", "--manifest", str(empty)])

        assert result.exit_code == 0, result.output
        assert "nothing to restore" in result.output


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
        records = read_manifest(manifest_path)
        by_path = {Path(r.original_path).name: r for r in records}
        keep_id = by_path["a.txt"].docmend_id

        result = runner.invoke(
            app, ["restore", "--manifest", str(manifest_path), "--write", "--id", keep_id]
        )

        assert result.exit_code == 0, result.output
        assert "restored: 1" in result.output
        assert (corpus / "a.txt").exists()
        assert (corpus / "b.md").exists()  # untouched by the filtered-out record


def _lock_record(*, source_root: str | None, original_path: str) -> ManifestRecord:
    return ManifestRecord(
        run_id=RESTORE_RUN_ID,
        action_id=f"{RESTORE_RUN_ID}/a1",
        docmend_id="01980000-0000-7000-8000-000000000001",
        seq=1,
        recorded_at="2026-07-06T02:00:00+00:00",
        operation="rewrite",
        original_path=original_path,
        target_path=original_path,
        backup_path=None,
        before_sha256="sha256:" + "a" * 64,
        after_sha256="sha256:" + "b" * 64,
        result="applied",
        error=None,
        source_root=source_root,
    )


class TestRestoreLockKey:
    """OQ-036: restore's lock key derivation (`_restore_lock_root`)."""

    def test_prefers_recorded_source_root_over_commonpath(self, tmp_path: Path) -> None:
        """With a 1.2 source_root recorded, restore keys on IT — not the commonpath
        of original paths, which narrows below the root when every mutated file
        shares a subdirectory (the AW-005 divergence gap)."""
        from docmend.cli import _restore_lock_root  # pyright: ignore[reportPrivateUsage]

        root = tmp_path / "root"
        (root / "sub").mkdir(parents=True)
        record = _lock_record(source_root=str(root), original_path=str(root / "sub" / "a.txt"))

        assert _restore_lock_root([record]) == root
        assert _restore_lock_root([record]) != root / "sub"  # the pre-fix commonpath key

    def test_legacy_manifest_without_source_root__falls_back_to_commonpath(
        self, tmp_path: Path
    ) -> None:
        """A pre-1.2 manifest has no source_root; the old commonpath behavior is
        retained so legacy manifests still lock and restore correctly."""
        from docmend.cli import _restore_lock_root  # pyright: ignore[reportPrivateUsage]

        base = tmp_path / "a" / "b"
        base.mkdir(parents=True)
        r1 = _lock_record(source_root=None, original_path=str(base / "x.txt"))
        r2 = _lock_record(source_root=None, original_path=str(base / "y.txt"))

        assert _restore_lock_root([r1, r2]) == base


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
