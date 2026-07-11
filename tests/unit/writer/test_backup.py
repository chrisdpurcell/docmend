"""Backup verify-then-mutate (FR-006, ERR-004, adr-0004).

The re-read/re-hash step is the point: a silently corrupted or short backup
must abort the mutation BEFORE the original is touched, or there is no
recoverable copy at all. Real filesystem (OQ-019).
"""

import hashlib
from pathlib import Path

import pytest

from docmend.writer import backup

RUN_ID = "run_20260706T000000Z_00007e"


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def test_backup__written_verified_and_returned(tmp_path: Path) -> None:
    data = b"payload bytes\n"
    dest = backup.backup_file(
        data,
        backup_root=tmp_path / "backups",
        run_id=RUN_ID,
        action_seq="a1",
        role="source",
        relative_path="sub/a.txt",
        expected_sha256=_sha(data),
    )
    assert dest == (tmp_path / "backups" / RUN_ID / "a1" / "source" / "sub" / "a.txt").resolve()
    assert dest.is_absolute()  # CR-005: manifest backup paths must survive cwd changes
    assert dest.read_bytes() == data


def test_backup_key_write_once__second_write_raises(tmp_path: Path) -> None:
    """DMR-01 defense in depth: a backup key is write-once — a second write to
    the same (run, action, role, path) key is a defect, never a retry (ERR-004)."""
    data = b"payload"
    backup.backup_file(
        data,
        backup_root=tmp_path / "backups",
        run_id=RUN_ID,
        action_seq="a1",
        role="source",
        relative_path="a.txt",
        expected_sha256=_sha(data),
    )
    with pytest.raises(backup.BackupError, match="write-once"):
        backup.backup_file(
            data,
            backup_root=tmp_path / "backups",
            run_id=RUN_ID,
            action_seq="a1",
            role="source",
            relative_path="a.txt",
            expected_sha256=_sha(data),
        )


def test_backup_roles__same_relative_path_distinct_keys(tmp_path: Path) -> None:
    """The DMR-01 shape: one action's source bytes and another action's
    overwritten-target bytes may share a relative path; roles + action_seq
    keep the keys distinct so neither copy can clobber the other."""
    source = b"original a.md\n"
    clobbered = b"pre-existing a.md target\n"
    dest_source = backup.backup_file(
        source,
        backup_root=tmp_path / "backups",
        run_id=RUN_ID,
        action_seq="a1",
        role="source",
        relative_path="a.md",
        expected_sha256=_sha(source),
    )
    dest_overwritten = backup.backup_file(
        clobbered,
        backup_root=tmp_path / "backups",
        run_id=RUN_ID,
        action_seq="a2",
        role="overwritten",
        relative_path="a.md",
        expected_sha256=_sha(clobbered),
    )
    assert dest_source != dest_overwritten
    assert dest_source.read_bytes() == source
    assert dest_overwritten.read_bytes() == clobbered


def test_backup_hash_mismatch__raises_before_mutation(tmp_path: Path) -> None:
    """ERR-004: a backup whose re-hash does not match the plan's source hash aborts."""
    data = b"payload"
    with pytest.raises(backup.BackupError):
        backup.backup_file(
            data,
            backup_root=tmp_path / "backups",
            run_id=RUN_ID,
            action_seq="a1",
            role="source",
            relative_path="a.txt",
            expected_sha256=_sha(b"different"),
        )


def test_backup_reread_corruption__raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A backup that reads back different bytes (bad disk, races) is ERR-004."""
    data = b"payload"
    real_read_bytes = Path.read_bytes

    def corrupt(self: Path) -> bytes:
        return b"corrupt" if self.name == "a.txt" else real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", corrupt)
    with pytest.raises(backup.BackupError):
        backup.backup_file(
            data,
            backup_root=tmp_path / "backups",
            run_id=RUN_ID,
            action_seq="a1",
            role="source",
            relative_path="a.txt",
            expected_sha256=_sha(data),
        )


def test_backup_destination_unwritable__raises(tmp_path: Path) -> None:
    root = tmp_path / "backups"
    root.mkdir()
    root.chmod(0o500)
    try:
        with pytest.raises(backup.BackupError):
            backup.backup_file(
                b"x",
                backup_root=root,
                run_id=RUN_ID,
                action_seq="a1",
                role="source",
                relative_path="a.txt",
                expected_sha256=_sha(b"x"),
            )
    finally:
        root.chmod(0o700)
