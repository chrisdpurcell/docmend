# Safety-Core Plan C — Commit Boundary (DMR-06/07) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind every corpus mutation to one filesystem object instead of a pathname — descriptor-captured `(st_dev, st_ino)` identity checked immediately before every publish and unlink (DMR-06), a no-clobber action-time overwrite invariant (`collision-unpreserved`, DMR-07) — and split the engines into read-only preview and `WriteSafetyContext`-gated mutation entrypoints (F8).

**Architecture:** One new module `src/docmend/writer/commit.py` owns the commit boundary (adr-0020): `bind_file` reads an object's bytes exactly once through an `O_RDONLY | O_NOFOLLOW` descriptor and captures its identity; `check_bound` is the at-commit half — `lstat` (never following symlinks), exact `(st_dev, st_ino)` compare, and a full-path containment re-resolve — called immediately before each pathname mutation step. The same module owns `WriteSafetyContext`, the sealed capability (adr-0004 amendment) whose only factories acquire the run lock, evaluate the apply gate / restore preflight, run the artifact destination guard, and stay held through manifest close and report publication. `writer/apply.py` and `restore.py` consume both halves; `cli.py` rewires to the split entrypoints. Plan B already persists the identities in intent records — this plan hardens their *capture* (descriptor-bound, was `os.stat` by design) and adds the *at-commit re-checks*.

**Tech Stack:** Python 3.14 (PEP 758 in the codebase), pydantic v2 strict models, typer CLI, pytest + coverage, `os.open`/`os.fstat`/`os.lstat` POSIX identity primitives.

**Design sources (binding):** `docs/adr/adr-0020-commit-boundary-object-identity.md`; `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md` §"Commit Boundary (DMR-06/07)" and §"Read/write entrypoint split (F8)"; spec rev 0.26 FR-003/FR-005/FR-011/§13.5. Change control is already landed (spec rev 0.26/0.27, adr-0004 amended, adr-0020 accepted) — no spec/ADR edits in this plan.

## Global Constraints

- Full local gate green at the end of EVERY task before its commit: `uv run python scripts/check.py` (Ruff format+lint, BasedPyright strict, pytest with branch coverage ≥ 97%, pip-audit).
- Never `git add .` / `git add -A` — stage files by explicit name.
- This repository is public: fixtures are synthetic only — never real library documents, paths, or personal content (conventions #6).
- Exit taxonomy is fixed (ADR-0012): safety refusal 3, artifact-input error 2, findings 1, clean 0. Commit-time interference is a per-action skip counting toward exit 1 (design §"Error Taxonomy").
- New skip reasons this plan introduces: `external-interference`, `collision-unpreserved`. No new exit codes. The report JSON schema's `skip_reason` is a free string + description (no enum), so no schema version bump — the reason vocabulary is documented in `report.py`.
- The `lstat`-to-`rename` interval is the ACCEPTED residual window (adr-0020 stated limitation) — do not attempt Linux-only `renameat2` hardening.
- Identity comparison is EXACT `(st_dev, st_ino)`; a device change refuses, never substitutes (docstring contract in `lineage.py`).
- Manifest 2.0 invariants from Plan B are untouched: intent-before-mutation for every kind, terminal repeats immutable fields, staging precedes intent so `expected_published_identity` is knowable pre-mutation.

## File Structure

| File | Role in this plan |
| --- | --- |
| `src/docmend/writer/commit.py` (create) | Commit boundary: `InterferenceError`, `BoundFile`, `bind_file`, `check_bound`, `CommitHooks`, `guarded_rename_no_clobber`; F8: `WriteSafetyContext`, `SafetyRefusedError` family, `apply_write_context`, `restore_write_context` |
| `src/docmend/writer/apply.py` (modify) | Source/target binding, per-step checks, hooks threading, `preview_plan`/`execute_plan` split via shared `_run_plan` |
| `src/docmend/restore.py` (modify) | Live-target binding, per-step inverse checks, `preview_restore`/`run_restore` split via shared `_run_restore` |
| `src/docmend/report.py` (modify) | `ApplySkipReason` gains the two new reasons |
| `src/docmend/writer/gate.py` (modify) | `_overwrite_preservation` docstring demoted to "early feedback, no longer load-bearing" |
| `src/docmend/cli.py` (modify) | apply/restore rewired to preview/factory entrypoints; refusal exception mapping |
| `tests/unit/writer/test_commit.py` (create) | Primitive + factory + sealing unit tests, pairwise predicate matrix |
| `tests/helpers/writectx.py` (create) | `apply_safety`/`restore_safety` context helpers for the e2e test idiom |
| `tests/test_apply.py`, `tests/test_resume.py`, `tests/test_restore.py`, `tests/test_idempotency.py`, `tests/test_restore_drill.py`, `tests/test_scale.py`, `tests/test_cli_apply.py`, `tests/test_cli_resume.py` (modify) | Race regression tests; migration to the split entrypoints |
| `CHANGELOG.md` (modify) | Plan C section under [Unreleased] |

Interference windows and who tests them (design §Testing, "commit-boundary races via the deterministic hooks"): source replacement after validation (Task 4), same-bytes-different-inode replacement (Task 4), parent-symlink interposition (Task 4), target replacement after backup (Task 4), target creation immediately before publish (Task 4), unlink/publish windows of the two-step kinds (Task 5), restore inverse windows (Task 6).

---

### Task 1: Commit-boundary primitives in `writer/commit.py`

**Files:**
- Create: `src/docmend/writer/commit.py`
- Test: `tests/unit/writer/test_commit.py`

**Interfaces:**
- Consumes: `ObjectIdentity` from `docmend.lineage`; `WriteError`, `link_no_clobber`, `fsync_dir` from `docmend.writer.atomic`.
- Produces (later tasks rely on these exact signatures):
  - `class InterferenceError(Exception)`
  - `@dataclass(frozen=True) class BoundFile: path: Path; data: bytes; identity: ObjectIdentity; mode: int`
  - `def bind_file(path: Path) -> BoundFile` — raises `InterferenceError` (symlink/non-regular) or `OSError` (missing/unreadable)
  - `def check_bound(path: Path, identity: ObjectIdentity, *, root_resolved: Path) -> None` — raises `InterferenceError`
  - `@dataclass(frozen=True) class CommitHooks: before_step: Callable[[str, Path], None]` with `NO_HOOKS: Final[CommitHooks]` module constant
  - `def guarded_rename_no_clobber(source: Path, target: Path, source_identity: ObjectIdentity, *, root_resolved: Path, hooks: CommitHooks) -> None` — raises `FileExistsError` (collision race, caller's policy), `InterferenceError`, `WriteError`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/writer/test_commit.py`:

```python
"""Commit-boundary primitives (adr-0020): descriptor-bound identity capture
and the at-commit lstat re-check. All fixtures are synthetic (conventions #6)."""

import os
from pathlib import Path

import pytest
from allpairspy import AllPairs  # pyright: ignore[reportMissingTypeStubs]

from docmend.lineage import ObjectIdentity
from docmend.writer.commit import (
    NO_HOOKS,
    BoundFile,
    CommitHooks,
    InterferenceError,
    bind_file,
    check_bound,
    guarded_rename_no_clobber,
)


class TestBindFile:
    def test_regular_file__bytes_identity_mode(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"hello\n")
        f.chmod(0o640)
        bound = bind_file(f)
        st = os.lstat(f)
        assert bound == BoundFile(
            path=f,
            data=b"hello\n",
            identity=ObjectIdentity(dev=st.st_dev, ino=st.st_ino),
            mode=st.st_mode,
        )

    def test_symlink__interference_not_followed(self, tmp_path: Path) -> None:
        real = tmp_path / "real.txt"
        real.write_bytes(b"payload")
        link = tmp_path / "doc.txt"
        link.symlink_to(real)
        with pytest.raises(InterferenceError, match="symlink"):
            bind_file(link)

    def test_missing__oserror_for_unreadable_mapping(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            bind_file(tmp_path / "absent.txt")

    def test_fifo__interference_not_regular(self, tmp_path: Path) -> None:
        fifo = tmp_path / "doc.txt"
        os.mkfifo(fifo)
        with pytest.raises(InterferenceError, match="regular"):
            bind_file(fifo)


class TestCheckBound:
    def test_unchanged__passes(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"x")
        check_bound(f, bind_file(f).identity, root_resolved=tmp_path.resolve())

    def test_missing__interference(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"x")
        identity = bind_file(f).identity
        f.unlink()
        with pytest.raises(InterferenceError, match="vanished"):
            check_bound(f, identity, root_resolved=tmp_path.resolve())

    def test_replaced_same_bytes_different_inode__interference(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"x")
        identity = bind_file(f).identity
        f.unlink()
        f.write_bytes(b"x")  # identical bytes, new inode — hashes cannot catch this
        with pytest.raises(InterferenceError, match="changed before commit"):
            check_bound(f, identity, root_resolved=tmp_path.resolve())

    def test_replaced_by_symlink_to_original__interference(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"x")
        identity = bind_file(f).identity
        moved = tmp_path / "moved.txt"
        f.rename(moved)
        f.symlink_to(moved)  # lstat sees the LINK, never the referent
        with pytest.raises(InterferenceError, match="symlink"):
            check_bound(f, identity, root_resolved=tmp_path.resolve())

    def test_parent_swapped_for_symlink__interference_even_with_leaf_match(
        self, tmp_path: Path
    ) -> None:
        # O_NOFOLLOW guards only the final component (adr-0020): the leaf
        # inode is UNCHANGED here, only a parent became a symlink pointing
        # outside the root — the containment re-resolve must catch it.
        root = tmp_path / "root"
        (root / "sub").mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        f = root / "sub" / "doc.txt"
        f.write_bytes(b"x")
        identity = bind_file(f).identity
        (root / "sub").rename(outside / "sub")
        (root / "sub").symlink_to(outside / "sub")
        with pytest.raises(InterferenceError, match="resolves"):
            check_bound(f, identity, root_resolved=root.resolve())

    @pytest.mark.parametrize(
        ("mutate", "expected"),
        [
            pytest.param(m, e, id=f"{m}-{e}")
            for m, e in AllPairs(
                [
                    ["unlink", "swap-inode", "symlink", "none"],
                    ["vanished", "changed", "symlink", "ok"],
                ]
            )
            if {"unlink": "vanished", "swap-inode": "changed", "symlink": "symlink", "none": "ok"}[
                m
            ]
            == e
        ],
    )
    def test_predicate_matrix(self, tmp_path: Path, mutate: str, expected: str) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"x")
        identity = bind_file(f).identity
        if mutate == "unlink":
            f.unlink()
        elif mutate == "swap-inode":
            f.unlink()
            f.write_bytes(b"x")
        elif mutate == "symlink":
            other = tmp_path / "o.txt"
            other.write_bytes(b"x")
            f.unlink()
            f.symlink_to(other)
        if expected == "ok":
            check_bound(f, identity, root_resolved=tmp_path.resolve())
        else:
            with pytest.raises(InterferenceError):
                check_bound(f, identity, root_resolved=tmp_path.resolve())


class TestGuardedRenameNoClobber:
    def _bound(self, tmp_path: Path) -> tuple[Path, Path, ObjectIdentity]:
        source = tmp_path / "a.txt"
        source.write_bytes(b"content")
        return source, tmp_path / "a.md", bind_file(source).identity

    def test_happy_path__renames(self, tmp_path: Path) -> None:
        source, target, identity = self._bound(tmp_path)
        guarded_rename_no_clobber(
            source, target, identity, root_resolved=tmp_path.resolve(), hooks=NO_HOOKS
        )
        assert not source.exists()
        assert target.read_bytes() == b"content"

    def test_target_appears_before_link__fileexists_propagates(self, tmp_path: Path) -> None:
        source, target, identity = self._bound(tmp_path)
        hooks = CommitHooks(
            before_step=lambda step, path: target.write_bytes(b"intruder")
            if step == "publish"
            else None
        )
        with pytest.raises(FileExistsError):
            guarded_rename_no_clobber(
                source, target, identity, root_resolved=tmp_path.resolve(), hooks=hooks
            )
        assert source.read_bytes() == b"content"  # untouched
        assert target.read_bytes() == b"intruder"  # never overwritten

    def test_source_swapped_before_link__interference_nothing_mutated(
        self, tmp_path: Path
    ) -> None:
        source, target, identity = self._bound(tmp_path)

        def swap(step: str, path: Path) -> None:
            if step == "publish":
                source.unlink()
                source.write_bytes(b"content")  # same bytes, new inode

        with pytest.raises(InterferenceError):
            guarded_rename_no_clobber(
                source, target, identity, root_resolved=tmp_path.resolve(), hooks=CommitHooks(swap)
            )
        assert not target.exists()

    def test_source_swapped_in_unlink_window__link_rolled_back(self, tmp_path: Path) -> None:
        # The window BETWEEN link and unlink: the interloper's object at the
        # source name must never be unlinked, and our published link must be
        # rolled back so the corpus is byte-identical to the pre-action state.
        source, target, identity = self._bound(tmp_path)

        def swap(step: str, path: Path) -> None:
            if step == "unlink":
                source.unlink()
                source.write_bytes(b"interloper")

        with pytest.raises(InterferenceError):
            guarded_rename_no_clobber(
                source, target, identity, root_resolved=tmp_path.resolve(), hooks=CommitHooks(swap)
            )
        assert source.read_bytes() == b"interloper"  # theirs, untouched
        assert not target.exists()  # ours, rolled back
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/writer/test_commit.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'docmend.writer.commit'`

- [ ] **Step 3: Write the implementation**

Create `src/docmend/writer/commit.py`:

```python
"""Commit boundary — descriptor-bound object identity (adr-0020, DMR-06/07).

Architectural role: every corpus mutation binds to ONE filesystem object,
never a pathname. `bind_file` reads an object's bytes exactly once through
an O_RDONLY|O_NOFOLLOW descriptor and captures its (st_dev, st_ino); every
pathname mutation step (each publish, each unlink) calls `check_bound`
immediately before mutating — lstat (never following symlinks), EXACT
identity compare, and a full-path containment re-resolve, because
O_NOFOLLOW guards only the final component and a parent directory can be
swapped for a symlink independently (adr-0020 decision drivers).

Why not fstat-and-hold: fstat on an open descriptor describes the
ORIGINALLY OPENED inode even after the name is repointed — only a
pathname-vs-captured-identity comparison detects replacement. Why not
re-hash: DMR-06's confirmed defect is a DIFFERENT OBJECT carrying possibly
identical bytes; hash equality cannot close it.

The lstat-to-rename interval is the accepted residual window (adr-0020
stated limitation): portable POSIX rename cannot be made fully
TOCTOU-free; the window shrinks from whole-action seconds to microseconds.
CommitHooks is the deterministic test seam for exactly those windows —
production passes NO_HOOKS.

This module also owns WriteSafetyContext (Task 7, F8/adr-0004 amendment):
the run-scoped half of the same boundary.
"""

import errno
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from docmend.lineage import ObjectIdentity
from docmend.writer.atomic import WriteError, fsync_dir, link_no_clobber


class InterferenceError(Exception):
    """The object a pathname names is not the object the plan validated
    (DMR-06). Callers map this to the `external-interference` skip; nothing
    has been mutated when it raises."""


@dataclass(frozen=True)
class BoundFile:
    """Bytes + identity + mode captured through ONE O_NOFOLLOW descriptor:
    the hash check, transform recompute, and backup that consume `data` are
    thereby statements about exactly the object `identity` names."""

    path: Path
    data: bytes
    identity: ObjectIdentity
    mode: int


@dataclass(frozen=True)
class CommitHooks:
    """Deterministic test seam for the adr-0020 residual windows: called
    with a step name ("publish", "unlink", "replace-target") and the
    pathname immediately BEFORE that step's check_bound + mutate pair."""

    before_step: Callable[[str, Path], None]


def _no_hook(step: str, path: Path) -> None:
    return None


NO_HOOKS: Final = CommitHooks(before_step=_no_hook)


def bind_file(path: Path) -> BoundFile:
    """Open `path` O_RDONLY|O_NOFOLLOW, capture identity via fstat, read all
    bytes through the descriptor. A symlink or non-regular file raises
    InterferenceError (the plan validated a regular file — the object
    changed class since); a missing/unreadable path raises OSError so the
    caller keeps today's `unreadable` (ERR-005) mapping."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            msg = f"{path}: symlink where a regular file was planned"
            raise InterferenceError(msg) from exc
        raise
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            msg = f"{path}: not a regular file ({stat.filemode(st.st_mode)})"
            raise InterferenceError(msg)
        with os.fdopen(fd, "rb") as fh:
            fd = -1  # fdopen owns (and closes) the descriptor now
            data = fh.read()
    finally:
        if fd >= 0:
            os.close(fd)
    return BoundFile(
        path=path,
        data=data,
        identity=ObjectIdentity(dev=st.st_dev, ino=st.st_ino),
        mode=st.st_mode,
    )


def check_bound(path: Path, identity: ObjectIdentity, *, root_resolved: Path) -> None:
    """The at-commit half (adr-0020): called immediately before EVERY
    pathname mutation step. lstat never follows symlinks; the compare is
    exact (st_dev, st_ino); the resolve re-checks containment at the same
    instant so a parent swapped for a symlink fails even when the leaf
    identity matches."""
    try:
        st = os.lstat(path)
    except OSError as exc:
        msg = f"{path}: vanished before commit ({exc.strerror or exc})"
        raise InterferenceError(msg) from exc
    if stat.S_ISLNK(st.st_mode):
        msg = f"{path}: replaced by a symlink before commit"
        raise InterferenceError(msg)
    if st.st_dev != identity.dev or st.st_ino != identity.ino:
        msg = (
            f"{path}: object changed before commit (now dev={st.st_dev} ino={st.st_ino}, "
            f"validated dev={identity.dev} ino={identity.ino})"
        )
        raise InterferenceError(msg)
    if not path.resolve().is_relative_to(root_resolved):
        msg = f"{path}: no longer resolves inside {root_resolved} (parent path interposed)"
        raise InterferenceError(msg)


def guarded_rename_no_clobber(
    source: Path,
    target: Path,
    source_identity: ObjectIdentity,
    *,
    root_resolved: Path,
    hooks: CommitHooks,
) -> None:
    """atomic.rename_no_clobber with the adr-0020 check before BOTH steps —
    the primitive's internal unlink is a pathname mutation and needs its own
    immediately-preceding check (an object swapped in behind the link must
    never be destroyed). Shared by apply's rename and restore's rename
    inverse. FileExistsError (collision race) propagates for the caller's
    policy; on a refused or failed unlink the link is rolled back — exact
    pre-action state, or a lossless both-names superset when even the
    rollback fails (never a missing file)."""
    hooks.before_step("publish", target)
    check_bound(source, source_identity, root_resolved=root_resolved)
    link_no_clobber(source, target)
    hooks.before_step("unlink", source)
    try:
        check_bound(source, source_identity, root_resolved=root_resolved)
    except InterferenceError:
        try:
            target.unlink()
        except OSError:
            # Both names remain on intact inodes (ours at target, the
            # interloper's at source) — lossless residue, and the raised
            # interference already fails the action loudly.
            pass
        raise
    try:
        source.unlink()
    except OSError as exc:
        residue = ""
        try:
            target.unlink()
        except OSError:
            residue = f"; rollback failed, {target} remains as a second name"
        msg = f"{source}: rename linked but source not removed ({exc.strerror or exc}){residue}"
        raise WriteError(msg) from exc
    fsync_dir(target.parent)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/writer/test_commit.py -q`
Expected: PASS (all)

- [ ] **Step 5: Full gate, then commit**

Run: `uv run python scripts/check.py`
Expected: green (coverage may need `test_commit.py` breadth — the matrix test covers the predicate branches).

```bash
git add src/docmend/writer/commit.py tests/unit/writer/test_commit.py
git commit -m "feat(writer): commit-boundary primitives — descriptor-bound identity, at-commit checks (adr-0020)"
```

---

### Task 2: Apply binds the source through a descriptor

**Files:**
- Modify: `src/docmend/writer/apply.py` (the `_execute_action` read/validate head and the identity-capture block)
- Modify: `src/docmend/report.py:31-39` (`ApplySkipReason`)
- Test: `tests/test_apply.py`

**Interfaces:**
- Consumes: `bind_file`, `BoundFile`, `InterferenceError`, `NO_HOOKS` from Task 1.
- Produces: `_execute_action` holds a `bound: BoundFile` for the source; `data`/`mode`/`identities.source` all derive from it. `ApplySkipReason` includes `"external-interference"`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_apply.py` (use the file's existing plan-building helpers — follow the idiom of the neighboring e2e tests):

```python
class TestCommitBoundarySourceBinding:
    def test_symlinked_source_at_apply__external_interference_skip(
        self, tmp_path: Path
    ) -> None:
        """DMR-06 class: between plan and apply the source name was repointed
        at another file via symlink. Today's pathname read follows it; the
        boundary must skip `external-interference` and mutate nothing."""
        root, plan, config, options, manifest_path = self._planned_rewrite(tmp_path)
        source = root / plan.actions[0].path
        payload = source.read_bytes()
        aside = tmp_path / "aside.txt"  # OUTSIDE the corpus root
        source.rename(aside)
        source.symlink_to(aside)
        report = self._execute(plan, config, options, manifest_path)
        outcome = report.outcomes[0]
        assert outcome.status == "skipped"
        assert outcome.skip_reason == "external-interference"
        assert aside.read_bytes() == payload  # the real file untouched
        assert source.is_symlink()  # the interposed link untouched
        assert not manifest_path.exists()  # pre-bind: no intent, no manifest

    def test_source_swapped_same_bytes_before_bind__applies_against_new_object(
        self, tmp_path: Path
    ) -> None:
        """Binding happens at validation time: a swap BEFORE the bind is
        simply the object the run validates (hash still gates it). This pins
        where the window OPENS — Task 4 pins where it closes."""
        root, plan, config, options, manifest_path = self._planned_rewrite(tmp_path)
        source = root / plan.actions[0].path
        payload = source.read_bytes()
        source.unlink()
        source.write_bytes(payload)
        report = self._execute(plan, config, options, manifest_path)
        assert report.outcomes[0].status == "applied"
```

(`_planned_rewrite`/`_execute` are thin wrappers over the file's existing scan→plan→execute helpers; write them once in this class if no exact fit exists, reusing the module's fixture functions.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_apply.py -k CommitBoundarySourceBinding -q`
Expected: FAIL — no `external-interference` reason exists; symlinked source currently reads through the link.

- [ ] **Step 3: Extend `ApplySkipReason`**

In `src/docmend/report.py`, extend the literal (and its neighbors' doc comment if present):

```python
type ApplySkipReason = Literal[
    "stale-hash",
    "unreadable",
    "collision",
    "collision-unpreserved",
    "shrink-invariant",
    "excluded",
    "containment",
    "already-applied",
    "external-interference",
]
```

(`collision-unpreserved` lands here too so the vocabulary changes once; its first emitter is Task 4.)

- [ ] **Step 4: Rewire `_execute_action`'s head onto `bind_file`**

In `src/docmend/writer/apply.py`, replace the pathname read (current lines 369-376):

```python
    source = source_root / action.path
    # FR-003 + adr-0020: the plan's decision only executes against the exact
    # bytes AND the exact object it saw — one O_NOFOLLOW descriptor supplies
    # the bytes for the hash check, the recompute, and the backup, and its
    # fstat identity is what every later commit step re-checks.
    try:
        bound = bind_file(source)
    except InterferenceError as exc:
        log.info("commit boundary refusal at bind", path=action.path, detail=str(exc))
        return _skip(action, "external-interference"), False
    except OSError:
        return _skip(action, "unreadable"), False  # ERR-005
    data = bound.data
    if _sha(data) != action.source_sha256:
        return _skip(action, "stale-hash"), False  # ERR-002, AW-004
```

Then in the staging/identity block (current lines 501-537), delete the `source.stat()` call and derive from the bound object:

```python
    staged: StagedWrite | None = None
    try:
        if kind in ("rewrite", "rename_and_rewrite"):
            staged = stage_bytes(
                target if kind == "rename_and_rewrite" else source,  # type: ignore[arg-type]
                payload,
                mode=bound.mode,
            )
    except (WriteError, OSError) as exc:
        ...  # unchanged failure recording

    identities = _Identities(
        source=bound.identity,
        # Task 3 rebinds this to a descriptor; unchanged here.
        target=_identity(target.stat()) if clobber and target is not None else None,
        expected=staged.identity if staged is not None else bound.identity,
    )
```

Every later `source_stat.st_mode` use (the `mode = source_stat.st_mode` line in the mutation block) becomes `bound.mode`. Import `bind_file`, `InterferenceError` from `docmend.writer.commit`.

- [ ] **Step 5: Run the new tests, then the full apply/resume suites**

Run: `uv run pytest tests/test_apply.py tests/test_resume.py -q`
Expected: PASS — the identity VALUES are unchanged for the honest path (`bind_file` fstat == the old `source.stat()` for a regular file), so no Plan B assertion moves.

- [ ] **Step 6: Full gate, then commit**

```bash
git add src/docmend/writer/apply.py src/docmend/report.py tests/test_apply.py
git commit -m "feat(apply): bind the source to one O_NOFOLLOW descriptor (adr-0020, DMR-06)"
```

---

### Task 3: Apply binds the overwrite target through a descriptor

**Files:**
- Modify: `src/docmend/writer/apply.py` (the clobber block, current lines 422-462, and `identities.target`)
- Modify: `src/docmend/writer/gate.py:116-136` (`_overwrite_preservation` docstring only)
- Test: `tests/test_apply.py`

**Interfaces:**
- Consumes: `bind_file` from Task 1.
- Produces: `target_bound: BoundFile | None` in `_execute_action`; `target_bytes`/`overwritten_sha`/`identities.target` all derive from it. Task 4/5's pre-`os.replace` target checks compare against `target_bound.identity`.

- [ ] **Step 1: Write the failing test**

```python
class TestCommitBoundaryTargetBinding:
    def test_symlinked_overwrite_target__external_interference_skip(
        self, tmp_path: Path
    ) -> None:
        """F3: under overwrite policy the pre-existing target's bytes are
        backed up through ITS descriptor. A symlink at the target name means
        the object the gate licensed clobbering is gone — skip, and back up
        nothing through the link."""
        root, plan, config, options, manifest_path = self._planned_rename_overwrite(tmp_path)
        target = root / plan.actions[0].target_path
        victim = tmp_path / "victim.txt"
        victim.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(victim)
        report = self._execute(plan, config, options, manifest_path)
        assert report.outcomes[0].skip_reason == "external-interference"
        assert victim.exists()  # never clobbered THROUGH the link
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_apply.py -k TargetBinding -q`
Expected: FAIL — today `target.read_bytes()` follows the symlink and the overwrite proceeds.

- [ ] **Step 3: Rebind the clobber block**

Replace the `target_bytes = target.read_bytes()` read with:

```python
    overwritten_sha: str | None = None
    overwritten_backup: Path | None = None
    target_bound: BoundFile | None = None  # clobbered object, kept for CR-NEW-004 rollback
    if clobber:
        assert target is not None
        try:
            # F3: identity captured and bytes read through ONE descriptor —
            # the backup below preserves exactly the object the pre-replace
            # check (Task 4) verifies is still there.
            target_bound = bind_file(target)
        except InterferenceError as exc:
            log.info("commit boundary refusal at target bind", path=action.path, detail=str(exc))
            return _skip(action, "external-interference"), False
        except OSError as exc:
            outcome = _failed(
                action, "ERR-003", f"{target}: unreadable for overwrite backup ({exc})"
            )
            _record(manifest, action, kind, source, target, None, None, None, None, run_id, outcome)
            return outcome, False
        overwritten_sha = _sha(target_bound.data)
        if options.backup_root is not None:
            try:
                overwritten_backup = backup_file(
                    target_bound.data,
                    ...  # unchanged keyword arguments
```

Downstream, the rollback branch's `target_bytes is not None` checks become `target_bound is not None` (rewriting `target_bound.data`), and:

```python
    identities = _Identities(
        source=bound.identity,
        target=target_bound.identity if target_bound is not None else None,
        expected=staged.identity if staged is not None else bound.identity,
    )
```

- [ ] **Step 4: Run tests, full gate, commit**

Run: `uv run pytest tests/test_apply.py tests/test_resume.py -q` then `uv run python scripts/check.py`

Also update `_overwrite_preservation`'s docstring in `gate.py` (no behavior change): append — "Action-time enforcement now lives in the commit boundary (adr-0020/adr-0004 amendment): a target appearing after this gate is published no-clobber and skipped `collision-unpreserved`. This predicate remains early operator feedback, no longer the load-bearing invariant."

```bash
git add src/docmend/writer/apply.py src/docmend/writer/gate.py tests/test_apply.py
git commit -m "feat(apply): bind the overwrite target to its own descriptor (adr-0020 F3)"
```

---

### Task 4: Per-step commit checks — rewrite and rename paths, `collision-unpreserved`

**Files:**
- Modify: `src/docmend/writer/apply.py` (mutation block for `rewrite`/`rename`; hooks threading through `execute_plan` → `_execute_action`; the `FileExistsError` handler)
- Test: `tests/test_apply.py`

**Interfaces:**
- Consumes: `check_bound`, `guarded_rename_no_clobber`, `CommitHooks`, `NO_HOOKS`, `InterferenceError`.
- Produces: `execute_plan(..., hooks: CommitHooks = NO_HOOKS)` threaded to `_execute_action(..., hooks)`; the race-lost skip reason is now `"collision-unpreserved"`; a new `except InterferenceError` arm closes a written intent with a failed ERR-002 terminal and returns the `external-interference` skip.

- [ ] **Step 1: Write the failing tests**

```python
class TestCommitBoundaryRaces:
    """adr-0020 confirmation windows, driven deterministically via CommitHooks."""

    def test_rewrite__source_swapped_same_bytes_after_intent__refused_rolled_forward_nothing(
        self, tmp_path: Path
    ) -> None:
        root, plan, config, options, manifest_path = self._planned_rewrite(tmp_path)
        source = root / plan.actions[0].path

        def swap(step: str, path: Path) -> None:
            if step == "publish":
                payload = source.read_bytes()
                source.unlink()
                source.write_bytes(payload)  # same bytes, different inode

        report = self._execute(plan, config, options, manifest_path, hooks=CommitHooks(swap))
        assert report.outcomes[0].skip_reason == "external-interference"
        # The intent was already journaled — it must not dangle: a failed
        # terminal closes it (mirrors Plan B's race-lost pattern).
        records = read_records(manifest_path)
        assert [r["result"] for r in records] == ["intent", "failed"]
        assert b"\r\n" in source.read_bytes() or source.read_bytes()  # untouched (unnormalized)

    def test_rename__target_created_before_publish__collision_unpreserved(
        self, tmp_path: Path
    ) -> None:
        """DMR-07: a target appearing after the gate is never silently
        overwritten — EEXIST maps to the new skip, distinct from plan-time
        `collision`."""
        root, plan, config, options, manifest_path = self._planned_rename(tmp_path)
        target = root / plan.actions[0].target_path

        def appear(step: str, path: Path) -> None:
            if step == "publish":
                target.write_bytes(b"late arrival")

        report = self._execute(plan, config, options, manifest_path, hooks=CommitHooks(appear))
        assert report.outcomes[0].skip_reason == "collision-unpreserved"
        assert target.read_bytes() == b"late arrival"

    def test_rename_overwrite__target_replaced_after_backup__refused(
        self, tmp_path: Path
    ) -> None:
        """F3's window: the backup preserved object A; by publish time the
        name holds object B. Clobbering B would be an unpreserved loss."""
        root, plan, config, options, manifest_path = self._planned_rename_overwrite(tmp_path)
        target = root / plan.actions[0].target_path

        def swap(step: str, path: Path) -> None:
            if step == "replace-target":
                content = target.read_bytes()
                target.unlink()
                target.write_bytes(content)

        report = self._execute(plan, config, options, manifest_path, hooks=CommitHooks(swap))
        assert report.outcomes[0].skip_reason == "external-interference"

    def test_rewrite__parent_swapped_for_symlink_before_publish__refused(
        self, tmp_path: Path
    ) -> None:
        # Corpus layout with a subdirectory; hook swaps the parent for a
        # symlink to a directory OUTSIDE the root (leaf identity unchanged),
        # exactly the O_NOFOLLOW blind spot check_bound's resolve closes.
        ...
```

(The parent-symlink test builds a nested corpus like Task 1's `test_parent_swapped_for_symlink...`, asserts `external-interference` and that the out-of-root file is untouched. `read_records` comes from `tests/helpers/manifest2.py`.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_apply.py -k CommitBoundaryRaces -q`
Expected: FAIL — `_execute` has no `hooks` parameter yet.

- [ ] **Step 3: Thread hooks and add the checks**

`execute_plan` gains `hooks: CommitHooks = NO_HOOKS` (keyword-only, after `prior_attempt`) and passes it to `_execute_action`, which adds `hooks: CommitHooks` to its signature. The mutation block becomes:

```python
    try:
        if kind == "rewrite":
            assert staged is not None
            hooks.before_step("publish", source)
            check_bound(source, bound.identity, root_resolved=root_resolved)
            publish_staged(staged, source)
        elif kind == "rename":
            assert target is not None
            if clobber:
                assert target_bound is not None
                hooks.before_step("replace-target", target)
                # Both sides re-checked at the commit instant (F2+F3): the
                # source we move and the preserved object we replace.
                check_bound(source, bound.identity, root_resolved=root_resolved)
                check_bound(target, target_bound.identity, root_resolved=root_resolved)
                rename_overwrite(source, target)
            else:
                guarded_rename_no_clobber(
                    source, target, bound.identity, root_resolved=root_resolved, hooks=hooks
                )
        else:  # rename_and_rewrite — Task 5 rewrites this arm
            ...
    except InterferenceError as exc:
        # adr-0020: commit-time interference — nothing (further) mutated;
        # guarded_rename_no_clobber rolled its link back. The intent is
        # already journaled and must not dangle for a live run: it closes
        # with a failed terminal (ERR-002), and the REPORT carries the
        # reviewable external-interference skip (mirrors the race-lost
        # collision pattern below).
        if staged is not None:
            abort_staged(staged)
        interference = _failed(action, "ERR-002", f"{exc} (adr-0020 commit boundary)")
        _record(
            manifest, action, kind, source, target, backup_path, None,
            overwritten_sha, overwritten_backup, run_id, interference, identities,
        )
        return _skip(action, "external-interference"), False
    except FileExistsError:
        ...  # existing handler; its final line changes to:
        return _skip(action, "collision-unpreserved"), False
```

Add `abort_staged` to the `docmend.writer.atomic` import list. The `FileExistsError` handler's failed-terminal message updates to name DMR-07: `"no-clobber publish lost a collision race (FR-011/DMR-07); no mutation occurred"`.

- [ ] **Step 4: Update the existing race-lost test**

`tests/test_apply.py` has an existing assertion that the no-clobber race skips `collision` (Plan B's FR-011 race test) — update it to `collision-unpreserved`. Search: `rg -n '"collision"' tests/test_apply.py tests/test_resume.py` and update only race-window assertions (plan-time and policy collisions stay `"collision"`).

- [ ] **Step 5: Run tests, full gate, commit**

Run: `uv run pytest tests/test_apply.py tests/test_resume.py tests/test_cli_apply.py -q` then the gate.

```bash
git add src/docmend/writer/apply.py tests/test_apply.py tests/test_resume.py
git commit -m "feat(apply): at-commit identity checks for rewrite/rename; collision-unpreserved (DMR-06/07)"
```

---

### Task 5: Per-step commit checks — `rename_and_rewrite` windows

**Files:**
- Modify: `src/docmend/writer/apply.py` (the `rename_and_rewrite` arm and its CR-NEW-004 rollback)
- Test: `tests/test_apply.py`

**Interfaces:**
- Consumes: everything from Task 4.
- Produces: the two-step kind checks the target before publish (clobber) and the source before its unlink, with the existing publish-rollback reused for the unlink-window interference.

- [ ] **Step 1: Write the failing tests**

```python
    def test_rename_and_rewrite__source_swapped_in_unlink_window__publish_rolled_back(
        self, tmp_path: Path
    ) -> None:
        """The target is already published when the source check refuses:
        the publish must roll back to the exact pre-action state (CR-NEW-004
        machinery), the interloper's file at the source name must survive,
        and the intent closes failed."""
        root, plan, config, options, manifest_path = self._planned_rename_rewrite(tmp_path)
        action = plan.actions[0]
        source = root / action.path
        target = root / action.target_path

        def swap(step: str, path: Path) -> None:
            if step == "unlink":
                source.unlink()
                source.write_bytes(b"interloper")

        report = self._execute(plan, config, options, manifest_path, hooks=CommitHooks(swap))
        assert report.outcomes[0].skip_reason == "external-interference"
        assert source.read_bytes() == b"interloper"
        assert not target.exists()  # rolled back
        assert [r["result"] for r in read_records(manifest_path)] == ["intent", "failed"]

    def test_rename_and_rewrite__clobber_target_swapped_before_publish__refused(
        self, tmp_path: Path
    ) -> None:
        # overwrite policy; hook at "publish" swaps the target inode →
        # external-interference, both live files untouched, staged temp gone.
        ...

    def test_rename_and_rewrite__target_appears_before_publish__collision_unpreserved(
        self, tmp_path: Path
    ) -> None:
        # skip policy planned no-clobber; hook at "publish" creates the
        # target → collision-unpreserved (existing FileExistsError path,
        # now named by DMR-07).
        ...
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_apply.py -k rename_and_rewrite -q`
Expected: the new tests FAIL (no checks in that arm yet).

- [ ] **Step 3: Rewrite the arm**

```python
        else:  # rename_and_rewrite
            assert target is not None
            assert staged is not None
            hooks.before_step("publish", target)
            check_bound(source, bound.identity, root_resolved=root_resolved)
            if clobber:
                assert target_bound is not None
                check_bound(target, target_bound.identity, root_resolved=root_resolved)
            publish_staged(staged, target, clobber=clobber)
            hooks.before_step("unlink", source)
            try:
                check_bound(source, bound.identity, root_resolved=root_resolved)
                source.unlink()
            except (InterferenceError, OSError) as unlink_exc:
                # codex CR-NEW-004 + adr-0020: the target is already
                # published; whether the unlink FAILED or was REFUSED
                # (source object swapped — unlinking it would destroy the
                # interloper's file), recording success or plain failure
                # while the corpus changed would lie. Roll the publish back
                # to the exact pre-action state, then surface the original
                # cause: interference re-raises to the ERR-002 arm, an
                # environmental failure keeps its WriteError (ERR-003).
                try:
                    if target_bound is not None:
                        atomic_write_bytes(target, target_bound.data, mode=bound.mode)
                    else:
                        target.unlink()
                except WriteError, OSError:
                    log.error(
                        "apply residue: target published, source not removed, rollback failed",
                        path=action.path,
                        target=str(target),
                    )
                if isinstance(unlink_exc, InterferenceError):
                    raise
                msg = (
                    f"{source}: target published but source not removed; publish "
                    f"rolled back ({unlink_exc.strerror or unlink_exc})"
                )
                raise WriteError(msg) from unlink_exc
```

(The bare `except WriteError, OSError:` keeps the file's deliberate PEP 758 idiom.) Note the pre-existing `mode` local is gone — the rollback uses `bound.mode` directly.

- [ ] **Step 4: Run tests, full gate, commit**

```bash
git add src/docmend/writer/apply.py tests/test_apply.py
git commit -m "feat(apply): rename_and_rewrite commit windows — checked unlink with publish rollback"
```

---

### Task 6: Restore binds the live target and checks every inverse step

**Files:**
- Modify: `src/docmend/restore.py` (`run_restore` signature gains `hooks`; `_restore_one` preflight and mutation block; `_live_matches_after` deleted)
- Test: `tests/test_restore.py`

**Interfaces:**
- Consumes: `bind_file`, `check_bound`, `guarded_rename_no_clobber`, `CommitHooks`, `NO_HOOKS`, `InterferenceError`.
- Produces: `run_restore(chain, *, run_id, write, only_ids, manifest_out, hooks: CommitHooks = NO_HOOKS)`; `_restore_one(record, *, write, run_id, manifest, root_resolved, hooks)`. (Task 9 later splits preview/write — signatures here stay additive.)

- [ ] **Step 1: Write the failing tests**

```python
class TestRestoreCommitBoundary:
    def test_applied_file_swapped_same_bytes_before_inverse__refused(
        self, tmp_path: Path
    ) -> None:
        """The restore preflight hashed the applied file; by commit time the
        name holds a DIFFERENT inode with the same bytes. Hashes pass;
        identity must refuse — mutating would destroy an object the manifest
        never described."""
        ...  # apply a rewrite, swap the applied file inode via hook at
        # "publish", run restore --write, assert outcome.status == "failed",
        # "external-interference" in outcome.detail, corpus untouched, and
        # the restore manifest holds [intent, failed] for the inverse.

    def test_symlinked_applied_file__failed_not_followed(self, tmp_path: Path) -> None:
        ...  # replace the applied file with a symlink before restore;
        # bind_file refuses; outcome failed ERR-002; the referent untouched.

    def test_rename_inverse__original_name_taken_in_window__loss_proof(
        self, tmp_path: Path
    ) -> None:
        ...  # hook at "publish" creates the original name → FileExistsError
        # → failed with collision detail; applied file still present
        # (loss-proof ordering); re-run converges (existing convergence
        # suite covers the re-run half).
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_restore.py -k RestoreCommitBoundary -q`
Expected: FAIL — no `hooks` parameter; same-bytes swap currently restores.

- [ ] **Step 3: Rewire `_restore_one`**

`run_restore` computes `root_resolved = Path(chain.sets[0].header.source_root).resolve()` once and threads `root_resolved`/`hooks` into `_restore_one`. The preflight replaces `_live_matches_after` + `target.stat()` with one bind (closing the read-then-stat gap between them):

```python
    original = Path(record.original_path)
    target = Path(record.target_path)
    try:
        # adr-0020: preflight hash, mode capture, and inverse identity all
        # come from ONE descriptor on the applied file — the object every
        # later step re-checks. Replaces the pathname read + separate stat
        # (which could observe two different objects).
        live = bind_file(target)
    except InterferenceError as exc:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path,
            "failed", f"ERR-002: {exc}",
        )
    except OSError:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path,
            "skipped", "unreadable: applied file missing or unreadable",
        )
    if record.after_sha256 is not None and _sha(live.data) != record.after_sha256:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path,
            "skipped", "modified-since-apply",
        )
    mode = live.mode
    source_identity = live.identity
```

(Delete `_live_matches_after` and the old `target_stat` block; `source_identity` replaces the hand-built `ObjectIdentity(...)`.) The mutation block gains the per-step checks:

```python
        if record.operation == "rewrite":
            assert staged is not None
            hooks.before_step("publish", original)  # original == target for rewrite
            check_bound(target, live.identity, root_resolved=root_resolved)
            publish_staged(staged, original)
        elif record.operation == "rename":
            if clobbered is not None:
                hooks.before_step("publish", original)
                check_bound(target, live.identity, root_resolved=root_resolved)
                link_no_clobber(target, original)
                hooks.before_step("replace-target", target)
                check_bound(target, live.identity, root_resolved=root_resolved)
                atomic_write_bytes(target, clobbered, mode=mode)
            else:
                guarded_rename_no_clobber(
                    target, original, live.identity, root_resolved=root_resolved, hooks=hooks
                )
        else:  # rename_and_rewrite
            assert staged is not None
            hooks.before_step("publish", original)
            publish_staged(staged, original, clobber=False)
            hooks.before_step("unlink", target)
            check_bound(target, live.identity, root_resolved=root_resolved)
            if clobbered is not None:
                atomic_write_bytes(target, clobbered, mode=mode)
            else:
                target.unlink()
    except InterferenceError as exc:
        # No rollback needed: the loss-proof ordering (original reinstated
        # FIRST) means an interference stop leaves a SUPERSET on disk, and
        # the failed inverse terminal + adjudication converge the re-run
        # (adr-0019) — restore never trades a superset for a rollback race.
        if staged is not None:
            abort_staged(staged)
        if manifest is not None and intent is not None:
            manifest.append(
                intent.model_copy(
                    update={
                        "result": "failed",
                        "after_sha256": None,
                        "run_id": run_id,
                        "error": ErrorInfo(error_class="ERR-002", message=str(exc)),
                    }
                )
            )
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path,
            "failed", f"ERR-002: {exc}",
        )
    except (WriteError, OSError, FileExistsError) as exc:
        ...  # existing ERR-003 arm unchanged
```

- [ ] **Step 4: Run tests, full gate, commit**

Run: `uv run pytest tests/test_restore.py tests/test_restore_drill.py -q` then the gate.

```bash
git add src/docmend/restore.py tests/test_restore.py
git commit -m "feat(restore): descriptor-bound inverse commits — identity checks on every step (adr-0020)"
```

---

### Task 7: `WriteSafetyContext` and the two sealed factories

**Files:**
- Modify: `src/docmend/writer/commit.py` (append the F8 half)
- Test: `tests/unit/writer/test_commit.py`

**Interfaces:**
- Consumes: `docmend.lock` (`acquire`, `LockHeldError`, `RunLock`), `docmend.writer.gate` (`ApplyOptions`, `evaluate_gate`, `GateRefusal`), `docmend.artifacts.guard_artifact_destination`, `docmend.writer.manifest.ManifestChain`, `docmend.config.DocmendConfig`, `docmend.plan.Plan`, `pathspec`.
- Produces (Tasks 8-9 rely on these exactly):
  - `class SafetyRefusedError(Exception)` — base; `LockRefusedError(SafetyRefusedError)`, `DestinationRefusedError(SafetyRefusedError)`, `WriteRefusedError(SafetyRefusedError)` with attribute `refusals: list[GateRefusal]`
  - `@final class WriteSafetyContext` — sealed; method `confirm() -> None` raising `RuntimeError` when inactive
  - `apply_write_context(plan, config, *, source_root, options, run_id, manifest_path, report_path, manifest_dir, input_artifacts=(), artifact_root=None, lock_state_dir=None) -> Iterator[WriteSafetyContext]` (contextmanager)
  - `restore_write_context(chain, *, run_id, manifest_out, artifact_root=None, lock_state_dir=None) -> Iterator[WriteSafetyContext]` (contextmanager)

- [ ] **Step 1: Write the failing tests**

```python
class TestWriteSafetyContext:
    def test_direct_construction__typeerror(self) -> None:
        with pytest.raises(TypeError, match="factory-sealed"):
            WriteSafetyContext()

    def test_capability_deactivates_on_factory_exit(self, tmp_path: Path, ...) -> None:
        # build a minimal 1-action plan via the module's helpers
        with apply_write_context(...) as safety:
            safety.confirm()
            leaked = safety
        with pytest.raises(RuntimeError, match="outside its factory scope"):
            leaked.confirm()

    def test_factory_holds_the_run_lock(self, tmp_path: Path) -> None:
        with apply_write_context(..., lock_state_dir=tmp_path / "locks"):
            with pytest.raises(lock.LockHeldError):
                lock.acquire(source_root, run_id="run_x", command="apply",
                             state_dir=tmp_path / "locks")
        lock.acquire(source_root, run_id="run_x", command="apply",
                     state_dir=tmp_path / "locks").release()  # released on exit

    def test_gate_refusal__writerefused_with_refusals(self, tmp_path: Path) -> None:
        # content rewrite + no strategy → gate refuses
        with pytest.raises(WriteRefusedError) as exc_info:
            with apply_write_context(...):
                raise AssertionError("must not yield")
        assert any(r.predicate == "preservation" for r in exc_info.value.refusals)

    def test_in_corpus_manifest_destination__destination_refused(self, tmp_path: Path) -> None:
        # manifest_path pointing at a corpus file → DestinationRefusedError
        ...

    def test_lock_contention__lock_refused(self, tmp_path: Path) -> None:
        # pre-acquire the lock, then the factory must raise LockRefusedError
        ...

    def test_restore_factory__locks_chain_root_and_guards_manifest_out(
        self, tmp_path: Path
    ) -> None:
        ...  # build a chain via tests/helpers/manifest2.write_set; assert
        # lock keyed on header.source_root; in-corpus manifest_out refused.
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/writer/test_commit.py -k WriteSafety -q`
Expected: FAIL — names don't exist.

- [ ] **Step 3: Implement**

Append to `src/docmend/writer/commit.py`:

```python
class SafetyRefusedError(Exception):
    """The write ceremony refused before any mutation (exit 3, ADR-0012)."""


class LockRefusedError(SafetyRefusedError):
    """Run-lock contention, or a lock that cannot be created (AW-005: a
    write-capable command must not proceed unlocked)."""


class DestinationRefusedError(SafetyRefusedError):
    """The artifact destination guard refused a manifest/report destination
    (adr-0021, DMR-02) — engine-level belt behind the CLI's own preflight."""


class WriteRefusedError(SafetyRefusedError):
    """The apply gate refused the run (FR-005). Raised with the lock already
    released — a refused run mutated nothing, so its refusal report needs no
    coordination boundary (the rev 0.26 in-lock rule binds the finalization
    of runs that MUTATE)."""

    def __init__(self, refusals: list[GateRefusal]) -> None:
        super().__init__("; ".join(r.message for r in refusals))
        self.refusals = refusals


_FACTORY_TOKEN: Final[object] = object()


@final
class WriteSafetyContext:
    """Sealed write capability (F8, adr-0004 amendment): proof that the run
    lock is held, the gate passed, and the artifact destinations are
    guarded. The mutation entrypoints (`execute_plan`, `run_restore`)
    REQUIRE one, and only the two factories below can construct it — no
    library caller reaches corpus mutation without the ceremony, while
    read-only preview stays ungated. Deactivates when its factory exits, so
    a reference held past the with-block confers nothing."""

    __slots__ = ("_active",)

    def __init__(self, *, _token: object | None = None) -> None:
        if _token is not _FACTORY_TOKEN:
            msg = (
                "WriteSafetyContext is factory-sealed (F8): enter "
                "apply_write_context() or restore_write_context()"
            )
            raise TypeError(msg)
        self._active = True

    def confirm(self) -> None:
        if not self._active:
            msg = "WriteSafetyContext used outside its factory scope (F8)"
            raise RuntimeError(msg)


def _guard_or_refuse(
    destination: Path,
    *,
    corpus_root: Path,
    input_artifacts: Sequence[Path],
    artifact_root: Path | None,
    exclude: PathSpec[GitIgnoreSpecPattern],
) -> None:
    refusal = guard_artifact_destination(
        destination,
        corpus_root=corpus_root,
        input_artifacts=input_artifacts,
        artifact_root=artifact_root,
        exclude=exclude,
    )
    if refusal is not None:
        raise DestinationRefusedError(refusal)


@contextlib.contextmanager
def apply_write_context(
    plan: Plan,
    config: DocmendConfig,
    *,
    source_root: Path,
    options: ApplyOptions,
    run_id: str,
    manifest_path: Path,
    report_path: Path,
    manifest_dir: Path,
    input_artifacts: Sequence[Path] = (),
    artifact_root: Path | None = None,
    lock_state_dir: Path | None = None,
) -> Iterator[WriteSafetyContext]:
    """The ONLY way to a write-capable apply (F8): guard the run's report
    and manifest destinations, acquire the run lock, evaluate the gate —
    then stay held through manifest close and report publication (the
    caller finalizes both inside this context; rev 0.26)."""
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude)
    for destination in (report_path, manifest_path):
        _guard_or_refuse(
            destination,
            corpus_root=source_root,
            input_artifacts=input_artifacts,
            artifact_root=artifact_root,
            exclude=exclude,
        )
    try:
        run_lock = lock.acquire(
            source_root, run_id=run_id, command="apply", state_dir=lock_state_dir
        )
    except (lock.LockHeldError, OSError) as exc:
        raise LockRefusedError(str(exc)) from exc
    ctx = WriteSafetyContext(_token=_FACTORY_TOKEN)
    try:
        refusals = evaluate_gate(
            plan, config, source_root=source_root, options=options, manifest_dir=manifest_dir
        )
        if refusals:
            raise WriteRefusedError(refusals)
        yield ctx
    finally:
        ctx._active = False  # noqa: SLF001 — factory owns the seal
        run_lock.release()


@contextlib.contextmanager
def restore_write_context(
    chain: ManifestChain,
    *,
    run_id: str,
    manifest_out: Path,
    artifact_root: Path | None = None,
    lock_state_dir: Path | None = None,
) -> Iterator[WriteSafetyContext]:
    """The ONLY way to a write-capable restore (F8): lock keyed on the
    VALIDATED chain's source_root (adr-0019 — identical across the chain by
    rule), and the restore manifest destination guarded with the chain's
    own manifests as protected inputs. A restore run has no config
    snapshot, so the `.docmend/` carve-out is licensed against the DEFAULT
    excludes — conservative: an operator who removed that exclude gets a
    refusal, never a corpus write."""
    source_root = Path(chain.sets[0].header.source_root)
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, DocmendConfig().paths.exclude)
    _guard_or_refuse(
        manifest_out,
        corpus_root=source_root,
        input_artifacts=[s.path for s in chain.sets],
        artifact_root=artifact_root,
        exclude=exclude,
    )
    try:
        run_lock = lock.acquire(
            source_root, run_id=run_id, command="restore", state_dir=lock_state_dir
        )
    except (lock.LockHeldError, OSError) as exc:
        raise LockRefusedError(str(exc)) from exc
    ctx = WriteSafetyContext(_token=_FACTORY_TOKEN)
    try:
        yield ctx
    finally:
        ctx._active = False  # noqa: SLF001
        run_lock.release()
```

Imports to add at the top of `commit.py`: `contextlib`; `Sequence`, `Iterator` from `collections.abc`; `final` from `typing`; `PathSpec` + `GitIgnoreSpecPattern` from pathspec; `docmend.lock as lock`; `guard_artifact_destination` from `docmend.artifacts`; `DocmendConfig`; `Plan`; `ApplyOptions`, `evaluate_gate`, `GateRefusal` from `docmend.writer.gate`; `ManifestChain` from `docmend.writer.manifest`. (No import cycle: nothing in that list imports `commit`.)

- [ ] **Step 4: Run tests, full gate, commit**

```bash
git add src/docmend/writer/commit.py tests/unit/writer/test_commit.py
git commit -m "feat(writer): WriteSafetyContext — sealed lock+gate+guard capability with factories (F8)"
```

---

### Task 8: Apply engine split (`preview_plan` / `execute_plan`) + CLI rewire + test migration

**Files:**
- Modify: `src/docmend/writer/apply.py` (rename `execute_plan` body to `_run_plan`; two public wrappers)
- Modify: `src/docmend/cli.py` (the `apply` command's lock/gate/execute section, current lines 608-670)
- Create: `tests/helpers/writectx.py`
- Modify/Test: `tests/test_apply.py`, `tests/test_resume.py`, `tests/test_idempotency.py`, `tests/test_scale.py`, `tests/test_cli_apply.py`, `tests/test_cli_resume.py`

**Interfaces:**
- Produces:
  - `preview_plan(plan, config, *, run_id, plan_ref, started_at, now=..., resume_chain=None, prior_attempt=None) -> Report` — read-only, synthesizes `ApplyOptions(write=False, backup_root=None, preserved_by=None, allow_no_backup=False)` internally; no manifest, no gate, no capability.
  - `execute_plan(plan, config, *, run_id, plan_ref, plan_sha256, options, manifest_path, started_at, safety: WriteSafetyContext, now=..., resume_chain=None, prior_manifest_sha256=None, prior_attempt=None, hooks=NO_HOOKS) -> Report` — first statements: `safety.confirm()`; `if not options.write: raise ValueError("execute_plan is the mutation entrypoint; use preview_plan (F8)")`.
  - `tests/helpers/writectx.py: apply_safety(plan, config, *, options, manifest_path, report_path, run_id, state_dir) -> ContextManager[WriteSafetyContext]` — thin wrapper filling `source_root=Path(plan.source_root)`, `manifest_dir=manifest_path.parent`, `lock_state_dir=state_dir`.

- [ ] **Step 1: Write the failing engine tests**

```python
class TestEntrypointSplit:
    def test_execute_plan_without_capability__typeerror_at_call(self) -> None:
        # signature makes `safety` required — passing None must fail confirm()
        with pytest.raises(AttributeError):
            execute_plan(..., safety=None)  # type: ignore[arg-type]

    def test_execute_plan_with_expired_capability__runtimeerror(self, tmp_path: Path) -> None:
        with apply_safety(...) as safety:
            pass
        with pytest.raises(RuntimeError, match="factory scope"):
            execute_plan(..., safety=safety)

    def test_preview_plan__no_lock_no_manifest_no_mutation(self, tmp_path: Path) -> None:
        report = preview_plan(plan, config, run_id=..., plan_ref=..., started_at=...)
        assert report.dry_run is True
        assert report.totals.would_apply == len(plan.actions)
        # corpus untouched; no manifest anywhere under tmp_path
```

- [ ] **Step 2: Split the engine**

In `apply.py`: rename the current `execute_plan` to `_run_plan(...)` (same parameters, keep `options`, add `hooks`), then:

```python
def preview_plan(
    plan: Plan,
    config: DocmendConfig,
    *,
    run_id: str,
    plan_ref: ArtifactRef,
    started_at: str,
    now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(),
    resume_chain: ManifestChain | None = None,
    prior_attempt: PriorAttempt | None = None,
) -> Report:
    """Read-only preview (F8/FR-004): today's dry-run behavior, no write
    ceremony — never constructs a ManifestWriter (write=False guarantees the
    manifest branch is dead) and needs no WriteSafetyContext."""
    return _run_plan(
        plan,
        config,
        run_id=run_id,
        plan_ref=plan_ref,
        plan_sha256="",  # header-only field; no manifest is ever opened
        options=ApplyOptions(
            write=False, backup_root=None, preserved_by=None, allow_no_backup=False
        ),
        manifest_path=None,
        started_at=started_at,
        now=now,
        resume_chain=resume_chain,
        prior_manifest_sha256=None,
        prior_attempt=prior_attempt,
        hooks=NO_HOOKS,
    )


def execute_plan(
    plan: Plan,
    config: DocmendConfig,
    *,
    run_id: str,
    plan_ref: ArtifactRef,
    plan_sha256: str,
    options: ApplyOptions,
    manifest_path: Path,
    started_at: str,
    safety: WriteSafetyContext,
    now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(),
    resume_chain: ManifestChain | None = None,
    prior_manifest_sha256: str | None = None,
    prior_attempt: PriorAttempt | None = None,
    hooks: CommitHooks = NO_HOOKS,
) -> Report:
    """The mutation entrypoint (F8): requires the sealed capability, whose
    factory already held the lock, passed the gate, and guarded the
    artifact destinations."""
    safety.confirm()
    if not options.write:
        msg = "execute_plan is the mutation entrypoint; use preview_plan for dry runs (F8)"
        raise ValueError(msg)
    return _run_plan(...)  # forward everything
```

`_run_plan`'s `manifest_path` parameter becomes `Path | None` (only dereferenced when `options.write and plan.actions` — assert there).

- [ ] **Step 3: Create `tests/helpers/writectx.py`**

```python
"""Write-ceremony helpers for the e2e library-API test idiom: every
mutation test enters the real factory (lock in a tmp state dir, real gate,
real guard) — the ceremony itself is under test everywhere it is used."""

import contextlib
from collections.abc import Iterator
from pathlib import Path

from docmend.config import DocmendConfig
from docmend.plan import Plan
from docmend.writer.commit import (
    WriteSafetyContext,
    apply_write_context,
    restore_write_context,
)
from docmend.writer.gate import ApplyOptions
from docmend.writer.manifest import ManifestChain


@contextlib.contextmanager
def apply_safety(
    plan: Plan,
    config: DocmendConfig,
    *,
    options: ApplyOptions,
    manifest_path: Path,
    report_path: Path,
    run_id: str,
    state_dir: Path,
) -> Iterator[WriteSafetyContext]:
    assert plan.source_root is not None
    with apply_write_context(
        plan,
        config,
        source_root=Path(plan.source_root),
        options=options,
        run_id=run_id,
        manifest_path=manifest_path,
        report_path=report_path,
        manifest_dir=manifest_path.parent,
        lock_state_dir=state_dir,
    ) as safety:
        yield safety


@contextlib.contextmanager
def restore_safety(
    chain: ManifestChain, *, run_id: str, manifest_out: Path, state_dir: Path
) -> Iterator[WriteSafetyContext]:
    with restore_write_context(
        chain, run_id=run_id, manifest_out=manifest_out, lock_state_dir=state_dir
    ) as safety:
        yield safety
```

- [ ] **Step 4: Rewire the CLI `apply` command**

Replace cli.py's current lock/gate/execute section (lines 608-670). The CLI-side `_guard_artifact_paths` preflight stays for BOTH modes (early, formatted refusal; the factory's guard is the engine-level belt):

```python
    if write:
        try:
            with commit.apply_write_context(
                plan,
                config,
                source_root=source_root,
                options=options,
                run_id=run_id,
                manifest_path=manifest_path,
                report_path=report_path,
                manifest_dir=artifact_dir,
                input_artifacts=guard_inputs,  # the same list the preflight used
                artifact_root=Path(ARTIFACT_DIR_NAME).resolve(),
            ) as safety:
                # Issue #15 renames-only warning: unchanged block, now inside
                # the context (it presumes a PASSED gate).
                ...
                result = execute_plan(
                    plan, config, run_id=run_id, plan_ref=plan_ref,
                    plan_sha256=..., options=options, manifest_path=manifest_path,
                    started_at=started_at, safety=safety,
                    resume_chain=resume_chain,
                    prior_manifest_sha256=prior_manifest_sha256,
                    prior_attempt=prior_attempt,
                )
                # rev 0.26: manifest hash + report finalize INSIDE the context
                # — the factory holds the lock through report publication.
                if manifest_path.exists():
                    result = result.model_copy(
                        update={"manifest_sha256": manifest.manifest_sha256(manifest_path)}
                    )
                artifacts.write_report(result, report_path)
        except commit.WriteRefusedError as exc:
            for refusal in exc.refusals:
                typer.echo(f"refused [{refusal.predicate}]: {refusal.message}", err=True)
                log.error("gate refusal", predicate=refusal.predicate, detail=refusal.message)
            _write_refusal_report(plan_ref, run_id, started_at, report_path)
            raise typer.Exit(3) from exc
        except commit.SafetyRefusedError as exc:
            typer.echo(f"refused: {exc}", err=True)
            raise typer.Exit(3) from exc
    else:
        # F8: preview keeps today's lock semantics (a dry run still contends
        # with concurrent writers) without the write ceremony.
        run_lock = _acquire_run_lock_strict(source_root, run_id=run_id, command="apply")
        try:
            result = preview_plan(
                plan, config, run_id=run_id, plan_ref=plan_ref, started_at=started_at,
                resume_chain=resume_chain, prior_attempt=prior_attempt,
            )
            artifacts.write_report(result, report_path)
        finally:
            run_lock.release()
```

(`guard_inputs` = hoist the existing `input_artifacts` list construction out of the `_guard_artifact_paths` call so both consumers share it. `_write_refusal_report` now writes after lock release — rationale in `WriteRefusedError`'s docstring; the refusal report path is run-id-unique, so no concurrent-writer hazard.)

- [ ] **Step 5: Migrate the test suite**

Mechanical pattern, applied to every direct `execute_plan(...)` call in `tests/test_apply.py`, `tests/test_resume.py`, `tests/test_idempotency.py`, `tests/test_restore_drill.py` (apply half), `tests/test_scale.py`:

```python
# BEFORE
report = execute_plan(plan, config, run_id=RUN, plan_ref=ref, plan_sha256=SHA,
                      options=options, manifest_path=mp, started_at=TS)
# AFTER (write runs)
with apply_safety(plan, config, options=options, manifest_path=mp,
                  report_path=tmp_path / "report.json", run_id=RUN,
                  state_dir=tmp_path / "locks") as safety:
    report = execute_plan(plan, config, run_id=RUN, plan_ref=ref, plan_sha256=SHA,
                          options=options, manifest_path=mp, started_at=TS,
                          safety=safety)
# AFTER (dry runs)
report = preview_plan(plan, config, run_id=RUN, plan_ref=ref, started_at=TS)
```

`tests/test_scale.py` additionally DROPS its separate `evaluate_gate` call + `assert refusals == []` — the factory evaluates the gate (entering the context asserts it passes). Keep the corpus/report assertions identical. Note: the factory's gate needs `manifest_dir` writable and, for `preserved_by="external"`, passes without a backup probe — no fixture changes.

CLI tests (`test_cli_apply.py`, `test_cli_resume.py`): behavior is meant to be UNCHANGED (same messages, same exit codes, same artifacts) — run them and fix only genuinely moved seams (e.g. a monkeypatch that targeted `cli._acquire_run_lock_strict` for the write path now targets the factory's `lock.acquire`).

- [ ] **Step 6: Run everything, full gate, commit**

Run: `uv run pytest -q` (full suite) then `uv run python scripts/check.py`

```bash
git add src/docmend/writer/apply.py src/docmend/cli.py tests/helpers/writectx.py \
        tests/test_apply.py tests/test_resume.py tests/test_idempotency.py \
        tests/test_scale.py tests/test_cli_apply.py tests/test_cli_resume.py
git commit -m "feat(apply): preview/write entrypoint split — execute_plan requires WriteSafetyContext (F8)"
```

---

### Task 9: Restore engine split (`preview_restore` / `run_restore`) + CLI rewire

**Files:**
- Modify: `src/docmend/restore.py` (rename `run_restore` body to `_run_restore`; two public wrappers)
- Modify: `src/docmend/cli.py` (the `restore` command's lock/execute section, current lines 990-1005)
- Test: `tests/test_restore.py`, `tests/test_restore_drill.py`, `tests/test_cli_resume.py` (restore CLI tests live here/`test_restore.py` — follow the existing layout)

**Interfaces:**
- Produces:
  - `preview_restore(chain, *, run_id, only_ids) -> list[RestoreOutcome]` — read-only (`write=False` path, no manifest).
  - `run_restore(chain, *, run_id, only_ids, manifest_out, safety: WriteSafetyContext, hooks=NO_HOOKS) -> list[RestoreOutcome]` — `safety.confirm()` first.

- [ ] **Step 1: Write the failing tests**

```python
class TestRestoreEntrypointSplit:
    def test_run_restore_with_expired_capability__runtimeerror(self, tmp_path: Path) -> None:
        ...
    def test_preview_restore__no_manifest_written_no_mutation(self, tmp_path: Path) -> None:
        ...
    def test_restore_manifest_destination_inside_corpus__refused_exit_3(
        self, tmp_path: Path
    ) -> None:
        """NEW coverage this split creates: restore's own output manifest now
        passes the destination guard (it never did before Plan C). A
        crafted chain whose source_root contains the default .docmend/ with
        the exclusion removed cannot make restore write into corpus space —
        via the factory directly (CLI uses the default artifact dir)."""
        ...
```

- [ ] **Step 2: Split the engine**

Same shape as Task 8: current `run_restore` becomes `_run_restore(chain, *, run_id, write, only_ids, manifest_out: Path | None, hooks)`; wrappers:

```python
def preview_restore(
    chain: ManifestChain, *, run_id: str, only_ids: frozenset[str] | None
) -> list[RestoreOutcome]:
    """Read-only preview (F8/IR-008): today's dry-run restore."""
    return _run_restore(chain, run_id=run_id, write=False, only_ids=only_ids,
                        manifest_out=None, hooks=NO_HOOKS)


def run_restore(
    chain: ManifestChain,
    *,
    run_id: str,
    only_ids: frozenset[str] | None,
    manifest_out: Path,
    safety: WriteSafetyContext,
    hooks: CommitHooks = NO_HOOKS,
) -> list[RestoreOutcome]:
    safety.confirm()
    return _run_restore(chain, run_id=run_id, write=True, only_ids=only_ids,
                        manifest_out=manifest_out, hooks=hooks)
```

- [ ] **Step 3: Rewire the CLI `restore` command**

```python
    manifest_out = artifact_dir / f"docmend-{run_id}-manifest.jsonl"
    if write:
        try:
            with commit.restore_write_context(
                chain, run_id=run_id, manifest_out=manifest_out,
                artifact_root=Path(ARTIFACT_DIR_NAME).resolve(),
            ) as safety:
                outcomes = run_restore(
                    chain, run_id=run_id,
                    only_ids=frozenset(only_id) if only_id else None,
                    manifest_out=manifest_out, safety=safety,
                )
        except commit.SafetyRefusedError as exc:
            typer.echo(f"refused: {exc}", err=True)
            raise typer.Exit(3) from exc
    else:
        run_lock = _acquire_run_lock_strict(
            Path(chain.sets[0].header.source_root), run_id=run_id, command="restore"
        )
        try:
            outcomes = preview_restore(
                chain, run_id=run_id, only_ids=frozenset(only_id) if only_id else None
            )
        finally:
            run_lock.release()
```

- [ ] **Step 4: Migrate restore tests**

Direct `run_restore(..., write=True, ...)` callers wrap in `restore_safety(...)`; `write=False` callers become `preview_restore(...)`. Same mechanical pattern as Task 8 Step 5.

- [ ] **Step 5: Run everything, full gate, commit**

```bash
git add src/docmend/restore.py src/docmend/cli.py tests/test_restore.py tests/test_restore_drill.py
git commit -m "feat(restore): preview/write split — run_restore requires WriteSafetyContext; guarded manifest destination (F8)"
```

---

### Task 10: Changelog, residual-window statement, coverage top-up

**Files:**
- Modify: `CHANGELOG.md` ([Unreleased])
- Modify: `tests/unit/writer/test_commit.py` (only if the gate's coverage floor demands more branches)

- [ ] **Step 1: Changelog**

Under `## [Unreleased]`, update the intro line to "plans A, B and C of four" / "DMR-01..DMR-04, DMR-06/07", and add after the manifest-2.0 section:

```markdown
### Changed — commit boundary (plan C, BREAKING for library callers)

- **Every mutation commits against the object it validated (adr-0020, DMR-06):** apply and restore read each file's bytes exactly once through an `O_NOFOLLOW` descriptor whose `(st_dev, st_ino)` identity is captured (and journaled, per plan B), and immediately before every publish and unlink the pathname is `lstat`-compared against that identity with containment re-resolved at the same instant. A missing name, a symlink, a parent-directory symlink swap, or a same-bytes-different-inode replacement skips the action as `external-interference` with the corpus untouched. The `lstat`-to-`rename` microsecond interval is the stated residual (POSIX rename cannot be fully TOCTOU-free).
- **Overwrite preservation is an action-time invariant (DMR-07):** an existing overwrite target is backed up through its own descriptor and identity-checked immediately before `os.replace`; when the collision check found no target, publication is no-clobber and a target appearing in the window is skipped `collision-unpreserved` — never silently overwritten. The gate's plan-time overwrite check remains as early feedback only.
- **Read/write entrypoint split (F8):** `preview_plan`/`preview_restore` are the read-only engines (dry-run behavior unchanged); `execute_plan`/`run_restore` now require a `WriteSafetyContext` — a sealed capability whose only factories acquire the run lock, evaluate the apply gate / restore preflight, guard the run's artifact destinations (restore's output manifest is now guarded too), and stay held through manifest close and report publication. Library callers cannot reach corpus mutation without the ceremony; the CLI's behavior is unchanged.
- New skip reasons: `external-interference`, `collision-unpreserved`. No new exit codes; no schema version changes (the report schema's `skip_reason` is an open string).
```

- [ ] **Step 2: Full gate; top up coverage if the floor moved**

Run: `uv run python scripts/check.py`
If branch coverage dipped below 97%, the usual gaps are `commit.py`'s error arms (`fdopen` failure, lock `OSError` wrap, guard-refusal in the restore factory) — cover them in `test_commit.py`, never with pragma exclusions.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md tests/unit/writer/test_commit.py
git commit -m "docs(changelog): plan C — commit boundary, action-time overwrite invariant, F8 split"
```

---

## Self-Review Notes (design-coverage check)

- Design §Commit Boundary F2 (source identity, per-step lstat, parent-path defense) → Tasks 1, 2, 4, 5. F3 (target identity, backup through descriptor, no-clobber + `collision-unpreserved`) → Tasks 3, 4, 5. Residual-window statement → Task 10 + `commit.py` docstring. Deterministic hooks for all five listed windows → Tasks 4, 5, 6 (mapping table in File Structure).
- Design §F8 (preview/write split, sealed capability, factory scope, held through manifest close and report publication) → Tasks 7, 8, 9. "Restore's ManifestSet preflight" is `read_manifest_chain`, which stays in the CLI *before* the factory (the factory receives the already-validated chain — its own preconditions are lock + guard).
- adr-0020 Confirmation list: every named race test exists (Tasks 4-6); the same-bytes/different-inode adjudication probes already landed in Plan B (`tests/unit/writer/test_adjudicate.py`) — this plan adds their LIVE-window counterparts.
- Deliberate decisions a reviewer should weigh: (1) `WriteSafetyContext` lives in `writer/commit.py` — the design's file map adds exactly one module, and the context is the run-scoped half of the same boundary; (2) gate refusals raise after lock release, so the CLI's refusal report writes unlocked — a refused run mutated nothing, and the rev 0.26 in-lock rule binds mutating runs' finalization (rationale in the exception docstring); (3) restore's carve-out licenses against DEFAULT excludes (no config snapshot in a restore run) — refusing more than before, never less; (4) preview keeps today's CLI-side locking per F8's "current lock semantics".
- Type-consistency: `bind_file`/`check_bound`/`BoundFile`/`CommitHooks`/`NO_HOOKS` names and signatures are identical across Tasks 1-6; `safety.confirm()` across 7-9; `apply_safety`/`restore_safety` helper signatures across 8-9.
