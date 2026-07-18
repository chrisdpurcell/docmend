"""Atomic write primitives (NFR-002, D-004, adr-0003).

Real filesystem, never pyfakefs (OQ-019/adr-0003): fsync/os.replace/os.link
semantics are the subject. Crash-injection: fail each step and assert the
target is either the intact original or the complete output — never a
fragment, never a stray temp file.
"""

import os
from pathlib import Path

import pytest
from tests.helpers import replace_with_new_inode

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
    real_unlink = Path.unlink
    residue: Path | None = None

    def boom(self: Path, missing_ok: bool = False) -> None:
        nonlocal residue
        # Fail on any temp file for this target (randomized names)
        if self.name.startswith(".a.md.") and self.name.endswith(".docmend-tmp"):
            residue = self
            raise OSError(5, "I/O error")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", boom)
    atomic.atomic_write_bytes(target, b"new", clobber=False)
    assert target.read_bytes() == b"new"
    assert (
        residue is not None and residue.exists()
    )  # documented residue: a second name for the same inode


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


def test_stage_open_failure__wraps_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An environmental failure allocating the staged inode is a WriteError."""

    def fail_open(path: os.PathLike[str] | str, flags: int, mode: int = 0o777) -> int:
        raise PermissionError(13, "Permission denied", path)

    monkeypatch.setattr(atomic.os, "open", fail_open)
    with pytest.raises(atomic.WriteError, match="cannot stage write"):
        atomic.stage_bytes(tmp_path / "doc.md", b"payload")


def test_stale_staging_residue__does_not_block_retry(tmp_path: Path) -> None:
    """A hard kill can leave a staging file behind; with the old FIXED temp
    name (.{name}.docmend-tmp) the next attempt's O_EXCL open failed forever.
    Randomized names make residue inert (rev 0.26 / adr-0021 staging rule)."""
    target = tmp_path / "a.md"
    (tmp_path / ".a.md.docmend-tmp").write_bytes(b"legacy stale residue")
    atomic.atomic_write_bytes(target, b"fresh\n")
    assert target.read_bytes() == b"fresh\n"
    assert (tmp_path / ".a.md.docmend-tmp").read_bytes() == b"legacy stale residue"


def test_staging_name_collision__retried_not_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EEXIST on a generated candidate is a NAME COLLISION, not an
    environmental write failure: the writer must retry a fresh name, leave the
    colliding residue untouched, and still publish (plan-review F5)."""
    target = tmp_path / "a.md"
    residue = tmp_path / ".a.md.deadbeef.docmend-tmp"
    residue.write_bytes(b"stale residue from a killed run")
    tokens = iter(["deadbeef", "cafe0000"])
    monkeypatch.setattr(atomic.secrets, "token_hex", lambda _n: next(tokens))  # type: ignore[reportUnknownArgumentType]
    atomic.atomic_write_bytes(target, b"fresh\n")
    assert target.read_bytes() == b"fresh\n"
    assert residue.read_bytes() == b"stale residue from a killed run"
    assert not (tmp_path / ".a.md.cafe0000.docmend-tmp").exists()


def test_staging_name_exhaustion__write_error_original_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 8-attempt staging-name loop's `for...else` bound: if every
    candidate collides (here, token_hex is pinned so all 8 attempts generate
    the same colliding name), allocation must fail as an environmental
    WriteError rather than loop forever — the target must never be created
    and the colliding residue must be left untouched (ERR-003)."""
    target = tmp_path / "a.md"
    residue = tmp_path / ".a.md.deadbeef.docmend-tmp"
    residue.write_bytes(b"stale residue that always collides")

    def fixed_token_hex(nbytes: int) -> str:
        return "deadbeef"

    monkeypatch.setattr(atomic.secrets, "token_hex", fixed_token_hex)
    with pytest.raises(atomic.WriteError, match="cannot stage write"):
        atomic.atomic_write_bytes(target, b"x")
    assert not target.exists()
    assert residue.read_bytes() == b"stale residue that always collides"


class TestStagedWriteApi:
    """Plan B Task 5 (adr-0019/adr-0020 seam): staging exposes the staged
    inode's identity BEFORE publication, so the intent record can carry
    expected_published_identity — atomic publish moves the inode onto the
    target name, so the identity survives the kill window."""

    def test_stage_bytes__target_untouched_identity_matches_temp(self, tmp_path: Path) -> None:
        target = tmp_path / "a.md"
        staged = atomic.stage_bytes(target, b"payload")
        assert not target.exists()
        st = staged.tmp.stat()
        assert (staged.identity.dev, staged.identity.ino) == (st.st_dev, st.st_ino)
        assert staged.tmp.read_bytes() == b"payload"

    def test_publish_staged__inode_moves_onto_target(self, tmp_path: Path) -> None:
        target = tmp_path / "a.md"
        staged = atomic.stage_bytes(target, b"payload")
        atomic.publish_staged(staged, target)
        st = target.stat()
        assert (st.st_dev, st.st_ino) == (staged.identity.dev, staged.identity.ino)
        assert target.read_bytes() == b"payload"

    def test_publish_staged_no_clobber__refuses_existing_target(self, tmp_path: Path) -> None:
        target = tmp_path / "a.md"
        target.write_bytes(b"occupied")
        staged = atomic.stage_bytes(target, b"payload")
        with pytest.raises(FileExistsError):
            atomic.publish_staged(staged, target, clobber=False)
        assert target.read_bytes() == b"occupied"

    def test_publish_failure_after_temp_race__interloper_survives(self, tmp_path: Path) -> None:
        """A publication failure must not delete an object swapped onto the temp name."""
        target = tmp_path / "doc.md"
        staged = atomic.stage_bytes(target, b"payload")
        replace_with_new_inode(staged.tmp, b"interloper")
        target.write_bytes(b"occupied")
        with pytest.raises(FileExistsError):
            atomic.publish_staged(staged, target, clobber=False)
        assert staged.tmp.read_bytes() == b"interloper"

    def test_abort_staged__removes_temp(self, tmp_path: Path) -> None:
        target = tmp_path / "a.md"
        staged = atomic.stage_bytes(target, b"payload")
        atomic.abort_staged(staged)
        assert not staged.tmp.exists()
        atomic.abort_staged(staged)  # idempotent

    def test_stage_bytes__mode_carried(self, tmp_path: Path) -> None:
        target = tmp_path / "a.md"
        staged = atomic.stage_bytes(target, b"payload", mode=0o644)
        atomic.publish_staged(staged, target)
        assert target.stat().st_mode & 0o777 == 0o644

    def test_stage_failure_after_temp_race__interloper_survives(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Failure cleanup is identity-bound when the staged name is replaced."""
        target = tmp_path / "doc.md"

        def swap_name_and_fail(fd: int) -> None:
            staged_name = next(tmp_path.glob(".doc.md.*.docmend-tmp"))
            staged_name.unlink()
            staged_name.write_bytes(b"interloper")
            raise OSError(5, "I/O error")

        monkeypatch.setattr(atomic.os, "fsync", swap_name_and_fail)
        with pytest.raises(atomic.WriteError):
            atomic.stage_bytes(target, b"payload")
        [interloper] = list(tmp_path.glob(".doc.md.*.docmend-tmp"))
        assert interloper.read_bytes() == b"interloper"

    def test_stage_mode_is_descriptor_bound_before_fsync(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The requested mode is applied to the opened inode before its failure window."""
        observed_modes: list[int] = []

        def inspect_mode_and_fail(fd: int) -> None:
            observed_modes.append(os.fstat(fd).st_mode & 0o7777)
            raise OSError(5, "I/O error")

        monkeypatch.setattr(atomic.os, "fsync", inspect_mode_and_fail)
        with pytest.raises(atomic.WriteError):
            atomic.stage_bytes(tmp_path / "doc.md", b"payload", mode=0o640)
        assert observed_modes == [0o640]


class TestAbortStagedIdentity:
    def test_raced_staged_temp__not_unlinked(self, tmp_path: Path) -> None:
        """Abort never deletes an object swapped onto the staged pathname."""
        staged = atomic.stage_bytes(tmp_path / "doc.md", b"payload")
        replace_with_new_inode(staged.tmp, b"interloper")
        atomic.abort_staged(staged)
        assert staged.tmp.read_bytes() == b"interloper"

    def test_own_staged_temp__unlinked_idempotently(self, tmp_path: Path) -> None:
        staged = atomic.stage_bytes(tmp_path / "doc.md", b"payload")
        atomic.abort_staged(staged)
        atomic.abort_staged(staged)
        assert not staged.tmp.exists()

    def test_interposed_parent__not_unlinked(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        sub = root / "sub"
        sub.mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        staged = atomic.stage_bytes(sub / "doc.md", b"payload")
        sub.rename(outside / "sub")
        sub.symlink_to(outside / "sub")
        atomic.abort_staged(staged, root_resolved=root.resolve())
        assert (outside / "sub" / staged.tmp.name).read_bytes() == b"payload"
