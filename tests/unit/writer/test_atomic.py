"""Atomic write primitives (NFR-002, D-004, adr-0003).

Real filesystem, never pyfakefs (OQ-019/adr-0003): fsync/os.replace/os.link
semantics are the subject. Crash-injection: fail each step and assert the
target is either the intact original or the complete output — never a
fragment, never a stray temp file.
"""

import os
from pathlib import Path

import pytest

from docmend.writer import atomic


def test_atomic_write__replaces_content(tmp_path: Path) -> None:
    """NFR-002: the write lands complete."""
    target = tmp_path / "a.txt"
    target.write_bytes(b"old")
    atomic.atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"new"
    assert list(tmp_path.iterdir()) == [target]  # no temp residue


def test_atomic_write__preserves_mode(tmp_path: Path) -> None:
    """Spec §8.1: permission preservation where reasonable."""
    target = tmp_path / "a.txt"
    target.write_bytes(b"old")
    target.chmod(0o640)
    atomic.atomic_write_bytes(target, b"new", mode=target.stat().st_mode)
    assert (target.stat().st_mode & 0o777) == 0o640


def test_crash_during_replace__original_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR-002 kill-during-write analog: fail at os.replace; file is the intact
    original, and the temp file is cleaned up."""
    target = tmp_path / "a.txt"
    target.write_bytes(b"old")

    def boom(src: object, dst: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(atomic.os, "replace", boom)
    with pytest.raises(atomic.WriteError):
        atomic.atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [target]


def test_no_clobber_publish__raises_when_target_exists(tmp_path: Path) -> None:
    """FR-011/§8.5: the writer refuses to overwrite unless explicitly allowed."""
    target = tmp_path / "a.md"
    target.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        atomic.atomic_write_bytes(target, b"new", clobber=False)
    assert target.read_bytes() == b"existing"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.md"]


def test_no_clobber_publish__creates_when_free(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    atomic.atomic_write_bytes(target, b"new", clobber=False)
    assert target.read_bytes() == b"new"


def test_no_clobber_publish_unlink_failure__publish_stands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR-002: a failed temp-unlink after a successful hardlink must not be
    reported as a WriteError — the publish already happened, so the caller
    would otherwise be told a lie about the mutation's outcome."""
    target = tmp_path / "a.md"
    tmp = target.with_name(f".{target.name}.docmend-tmp")
    real_unlink = Path.unlink

    def boom(self: Path, missing_ok: bool = False) -> None:
        if self == tmp:
            raise OSError(5, "I/O error")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", boom)
    atomic.atomic_write_bytes(target, b"new", clobber=False)
    assert target.read_bytes() == b"new"
    assert tmp.exists()  # documented residue: a second name for the same inode


def test_rename_no_clobber__moves_and_refuses(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_bytes(b"payload")
    atomic.rename_no_clobber(src, tmp_path / "a.md")
    assert not src.exists()
    assert (tmp_path / "a.md").read_bytes() == b"payload"

    other = tmp_path / "b.txt"
    other.write_bytes(b"other")
    blocker = tmp_path / "b.md"
    blocker.write_bytes(b"blocker")
    with pytest.raises(FileExistsError):
        atomic.rename_no_clobber(other, blocker)
    assert other.read_bytes() == b"other"
    assert blocker.read_bytes() == b"blocker"


def test_rename_no_clobber_source_unlink_failure__rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-011/NFR-002: if the link succeeds but removing the source fails,
    rollback must remove the just-created target link, leaving the exact
    pre-action state (codex CR-NEW-004 class)."""
    source = tmp_path / "a.txt"
    source.write_bytes(b"payload")
    target = tmp_path / "a.md"
    real_unlink = Path.unlink

    def boom(self: Path, missing_ok: bool = False) -> None:
        if self == source:
            raise OSError(5, "I/O error")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", boom)
    with pytest.raises(atomic.WriteError):
        atomic.rename_no_clobber(source, target)
    assert not target.exists()
    assert source.read_bytes() == b"payload"


def test_rename_no_clobber_double_failure__residue_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-011/NFR-002: if both the source unlink and the rollback's target
    unlink fail, the failure is reported (never silently swallowed) and both
    names remain pointing at one intact inode — a superset, never lossy."""
    source = tmp_path / "a.txt"
    source.write_bytes(b"payload")
    target = tmp_path / "a.md"

    def boom(self: Path, missing_ok: bool = False) -> None:
        raise OSError(5, "I/O error")

    monkeypatch.setattr(Path, "unlink", boom)
    with pytest.raises(atomic.WriteError, match="second name"):
        atomic.rename_no_clobber(source, target)
    assert source.exists()
    assert target.exists()
    assert source.read_bytes() == target.read_bytes() == b"payload"


def test_rename_overwrite__replaces_and_wraps_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """codex CR-NEW-001: the overwrite rename goes through the same
    WriteError/fsync contract as every other mutation (FR-011, NFR-002)."""
    src = tmp_path / "a.txt"
    src.write_bytes(b"new")
    dst = tmp_path / "a.md"
    dst.write_bytes(b"old")
    atomic.rename_overwrite(src, dst)
    assert not src.exists()
    assert dst.read_bytes() == b"new"

    other = tmp_path / "b.txt"
    other.write_bytes(b"payload")
    blocker = tmp_path / "b.md"
    blocker.write_bytes(b"blocker")

    def boom(src_: object, dst_: object) -> None:
        raise OSError(5, "I/O error")

    monkeypatch.setattr(atomic.os, "replace", boom)
    with pytest.raises(atomic.WriteError):
        atomic.rename_overwrite(other, blocker)
    assert other.read_bytes() == b"payload"
    assert blocker.read_bytes() == b"blocker"


def test_write_failure__wraps_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ERR-003: environmental write errors surface as WriteError with the cause."""
    target = tmp_path / "a.txt"

    real_fsync = os.fsync

    def boom(fd: int) -> None:
        raise OSError(5, "I/O error")

    monkeypatch.setattr(atomic.os, "fsync", boom)
    with pytest.raises(atomic.WriteError):
        atomic.atomic_write_bytes(target, b"new")
    monkeypatch.setattr(atomic.os, "fsync", real_fsync)
    assert list(tmp_path.iterdir()) == []
