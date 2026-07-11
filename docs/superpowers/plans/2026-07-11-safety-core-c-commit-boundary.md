# Safety-Core Plan C — Commit Boundary (DMR-06/07) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind every corpus mutation to one filesystem object instead of a pathname — descriptor-captured `(st_dev, st_ino)` identity checked immediately before every publish and unlink (DMR-06), a no-clobber action-time overwrite invariant (`collision-unpreserved`, DMR-07) — and split the engines into read-only preview and `WriteSafetyContext`-gated mutation entrypoints (F8).

**Revision note (round 1):** revised per plan-review round 1 (CR-001..CR-009, all verified against `df28beb`): action-time strategy re-check (CR-001); attested capability + factory-owned restore preflight (CR-002); absent-destination/staged-temp/survivor coverage (CR-003); boundary-checked rollback + dangling-intent honesty (CR-004); `O_NONBLOCK` bind (CR-005, reproduced); effective excludes for restore (CR-006 — the round-0 "defaults are conservative" claim was inverted); in-lock, no-clobber refusal reports (CR-007); in-root symlink referents (CR-008); §17.3 traceability task (CR-009).

**Revision note (round 2):** revised per plan-review round 2. CR-001: the action-time window test now acquires the safety context while the target is absent and creates it inside the context (the earlier ordering would have refused at the gate once Task 9 migrates the tests). CR-002: the attestation binds digests of the ACTUAL `Plan` and `DocmendConfig` the gate evaluated (recomputed at `confirm_apply` from the presented objects), plus `report_path` with a `confirm_report` seam; `ManifestSet.records`/`ManifestChain.sets` become tuples so `safety.chain` is immutable. CR-003: check-then-`atomic_write_bytes` re-opened the stage-window race — a new `guarded_replace` primitive stages FIRST, then checks staged inode + target identity + containment immediately before publish; used by `_undo_publish`, restore's clobbered-target reinstatement, and adjudication. CR-004: when the SOURCE name loses the bound original after a link, the published link is its possibly-last name and is never removed (lossless intermediate, dangling intent) — the round-1 rollback destroyed it; `_rollback_link` distinguishes identity-lost (proven, nothing ours remains) from containment-lost-with-identity-intact (unproven); `abort_staged` is now identity-checked so a raced staged temp is never blind-unlinked. CR-NEW-001: new Task 7 routes `finish_remaining`'s mutations (both resume and restore invoke them) through the same boundary — its docstring already named Plan C as the closer of that window. CR-NEW-002: the resume composition test premise is corrected (an external-interference verdict leaves the intent dangling; no closure terminal); the restore retry premise was false against a REAL, previously unshipped defect found while verifying it — the chain validator wholesale-rejected the producer's own pre-mutation standalone `failed` shape, making any run with an ordinary staging/backup failure unresumable — fixed, tested, and pushed as `8c2d5f4` with the design's lifecycle sentence disambiguated, so the test premise now stands. CR-NEW-003: the new restore CLI flags are withdrawn; restore instead loads the project's `docmend.toml` via the existing default discovery (no new public interface; flagged below for owner sign-off).

**Architecture:** One new module `src/docmend/writer/commit.py` owns the commit boundary (adr-0020): `bind_file` reads an object's bytes exactly once through an `O_RDONLY | O_NOFOLLOW | O_NONBLOCK` descriptor and captures its identity; `check_bound` is the at-commit half — `lstat` (never following symlinks), exact `(st_dev, st_ino)` compare, and a full-path containment re-resolve — called immediately before each pathname mutation step; `check_destination` is its absent-name counterpart; `guarded_replace` is the stage-first replacement primitive. The same module owns `WriteSafetyContext`, the sealed capability (adr-0004 amendment) whose only factories acquire the run lock, evaluate the apply gate / perform the restore chain preflight, run the artifact destination guard, bind an immutable attestation of exactly what they authorized (model digests included), and stay held through manifest close and report publication. `writer/apply.py`, `restore.py`, and `writer/adjudicate.py` consume both halves; `cli.py` rewires to the split entrypoints. Plan B already persists the identities in intent records — this plan hardens their *capture* (descriptor-bound, was `os.stat` by design) and adds the *at-commit re-checks*.

**Tech Stack:** Python 3.14 (PEP 758 in the codebase), pydantic v2 strict models, typer CLI, pytest + coverage, `os.open`/`os.fstat`/`os.lstat` POSIX identity primitives.

**Design sources (binding):** `docs/adr/adr-0020-commit-boundary-object-identity.md`; `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md` §"Commit Boundary (DMR-06/07)" and §"Read/write entrypoint split (F8)"; spec rev 0.26 FR-003/FR-005/FR-011/§13.5. Change control is already landed (spec rev 0.26/0.27, adr-0004 amended, adr-0020 accepted) — no *behavioral* spec/ADR edits in this plan; §17.3 traceability maintenance (Appendix B obligation) is Task 12.

## Global Constraints

- Full local gate green at the end of EVERY task before its commit: `uv run python scripts/check.py` (Ruff format+lint, BasedPyright strict, pytest with branch coverage ≥ 97%, pip-audit).
- Never `git add .` / `git add -A` — stage files by explicit name.
- This repository is public: fixtures are synthetic only — never real library documents, paths, or personal content (conventions #6).
- Exit taxonomy is fixed (ADR-0012): safety refusal 3, artifact-input error 2, findings 1, clean 0. Commit-time interference is a per-action skip counting toward exit 1 (design §"Error Taxonomy").
- New skip reasons this plan introduces: `external-interference`, `collision-unpreserved`. No new exit codes. The report JSON schema's `skip_reason` is a free string + description (no enum), so no schema version bump — the reason vocabulary is documented in `report.py`.
- The `lstat`-to-`rename` interval is the ACCEPTED residual window (adr-0020 stated limitation) — do not attempt Linux-only `renameat2` hardening.
- Identity comparison is EXACT `(st_dev, st_ino)`; a device change refuses, never substitutes (docstring contract in `lineage.py`).
- Manifest 2.0 invariants from Plan B are untouched: intent-before-mutation for every kind, terminal repeats immutable fields, staging precedes intent so `expected_published_identity` is knowable pre-mutation. Standalone pre-mutation `failed` records are chain-legal (`8c2d5f4`).
- **Terminal-honesty rule (CR-004, binding for every task):** a `failed` terminal may be appended ONLY when the corpus is provably in its pre-action state (spec §10.4: Failed means the original is intact). When a mutation step has already landed and its rollback cannot be *proven* (identity-checked at every rollback touch), the intent stays DANGLING and the action reports `failed` (ERR-002) — resume/restore adjudication owns the intermediate, exactly what the adr-0019 table exists for.
- **Last-copy rule (CR-004 round 2, binding):** no rollback or cleanup step may remove a name that holds the bound original when the original's OTHER name is not provably intact — a published hardlink can be the last surviving name of the validated object, and deleting it is data loss disguised as tidiness. When in doubt, keep the lossless intermediate and leave the intent dangling.
- **Replacement writes stage first (CR-003 round 2, binding):** never check-then-`atomic_write_bytes` on a corpus name — the function stages internally and publishes later, re-opening the window. Use `guarded_replace` (stage → check staged inode + target identity + containment → publish).

## File Structure

| File | Role in this plan |
| --- | --- |
| `src/docmend/writer/commit.py` (create) | Commit boundary: `InterferenceError` (with `intermediate` flag), `BoundFile`, `bind_file`, `check_bound`, `check_destination`, `guarded_replace`, `CommitHooks`, `guarded_rename_no_clobber`; F8: `WriteSafetyContext` (attested with model digests), `SafetyRefusedError` family, `apply_write_context`, `restore_write_context` |
| `src/docmend/writer/atomic.py` (modify) | `abort_staged` becomes identity-checked (CR-004) |
| `src/docmend/writer/apply.py` (modify) | Source/target binding, action-time overwrite invariant, per-step checks, boundary-checked rollback, hooks threading, `preview_plan`/`execute_plan` split via shared `_run_plan` |
| `src/docmend/writer/adjudicate.py` (modify) | `finish_remaining` mutations routed through the boundary — containment, hooks, `guarded_replace` (CR-NEW-001) |
| `src/docmend/writer/manifest.py` (modify) | `ManifestSet.records`/`ManifestChain.sets` become tuples — the validated chain is immutable (CR-002) |
| `src/docmend/restore.py` (modify) | Live-target binding, per-step inverse checks with survivor verification, dangling-intent policy for intermediates, `preview_restore`/`run_restore` split via shared `_run_restore` |
| `src/docmend/report.py` (modify) | `ApplySkipReason` gains the two new reasons |
| `src/docmend/writer/gate.py` (modify) | `_strategy_active` → public `strategy_active`; `_overwrite_preservation` docstring demoted to "early feedback, no longer load-bearing" |
| `src/docmend/artifacts.py` (modify) | `write_report`/`write_json_artifact` gain a `clobber` passthrough (no-clobber refusal reports, CR-007) |
| `src/docmend/cli.py` (modify) | apply/restore rewired to preview/factory entrypoints; refusal callback; restore loads the default-discovery config for its effective excludes (CR-006/CR-NEW-003 — no new flags) |
| `docs/specs/docmend.md` (modify, Task 12 only) | §17.3 traceability rows + Document History entry — status accuracy for Plans A/B/C, no behavioral text |
| `tests/unit/writer/test_commit.py` (create) | Primitive + factory + sealing + attestation unit tests, pairwise predicate matrix |
| `tests/unit/writer/test_adjudicate.py` (modify) | Boundary coverage for `finish_remaining` (containment, replace-window, mode) |
| `tests/helpers/writectx.py` (create) | `apply_safety`/`restore_safety` context helpers for the e2e test idiom |
| `tests/test_apply.py`, `tests/test_resume.py`, `tests/test_restore.py`, `tests/test_idempotency.py`, `tests/test_restore_drill.py`, `tests/test_scale.py`, `tests/test_cli_apply.py`, `tests/test_cli_resume.py` (modify) | Race regression tests; migration to the split entrypoints |
| `CHANGELOG.md` (modify) | Plan C section under [Unreleased] |

Interference windows and who tests them (design §Testing + review rounds 1-2): source replacement after validation (Task 4), same-bytes-different-inode replacement (Task 4), parent-symlink interposition (Task 4), destination-parent interposition on an absent target (Task 4), target appearing in the gate→collision-check window (Tasks 3+9, CR-001), target creation immediately before publish (Task 4), target replacement after backup (Task 4), published-target replacement before the source unlink (Tasks 4/5), source-name loss after link — last-copy retention (Tasks 1/5, CR-004), staged-temp replacement before publish and before abort (Tasks 1/4, CR-003/CR-004), replacement-write stage-window (Tasks 1/5/6/7, CR-003), rollback-unproven intermediates (Task 5), adjudication finish windows (Task 7, CR-NEW-001), restore inverse windows including reinstated-original survivor checks and the `restore-failed` retry (Task 6).

---

### Task 1: Commit-boundary primitives in `writer/commit.py`

**Files:**
- Create: `src/docmend/writer/commit.py`
- Modify: `src/docmend/writer/atomic.py` (`abort_staged`)
- Test: `tests/unit/writer/test_commit.py`, `tests/unit/writer/test_atomic.py`

**Interfaces:**
- Consumes: `ObjectIdentity` from `docmend.lineage`; `WriteError`, `StagedWrite`, `stage_bytes`, `publish_staged`, `abort_staged`, `link_no_clobber`, `fsync_dir` from `docmend.writer.atomic`.
- Produces (later tasks rely on these exact signatures):
  - `class InterferenceError(Exception)` with `__init__(self, message: str, *, intermediate: bool = False)` and attribute `intermediate: bool` — `True` means the disk is NOT provably pre-action state (terminal-honesty rule applies)
  - `@dataclass(frozen=True) class BoundFile: path: Path; data: bytes; identity: ObjectIdentity; mode: int`
  - `def bind_file(path: Path) -> BoundFile` — raises `InterferenceError` (symlink/non-regular) or `OSError` (missing/unreadable); never blocks on special files (CR-005)
  - `def check_bound(path: Path, identity: ObjectIdentity, *, root_resolved: Path) -> None` — raises `InterferenceError`
  - `def check_destination(path: Path, *, root_resolved: Path) -> None` — absent-name containment (CR-003); raises `InterferenceError`
  - `def guarded_replace(target: Path, data: bytes, *, expected: ObjectIdentity, mode: int, root_resolved: Path, hooks: CommitHooks, step: str = "replace-target") -> None` — stage-first replacement (CR-003 round 2); raises `InterferenceError`, `WriteError`
  - `@dataclass(frozen=True) class CommitHooks: before_step: Callable[[str, Path], None]` with `NO_HOOKS: Final[CommitHooks]` module constant
  - `def guarded_rename_no_clobber(source: Path, target: Path, source_identity: ObjectIdentity, *, root_resolved: Path, hooks: CommitHooks) -> None` — raises `FileExistsError` (collision race, caller's policy), `InterferenceError` (possibly `intermediate=True`), `WriteError`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/writer/test_commit.py`. The round-1 test set stands (bind/check basics, FIFO-with-thread-guard, predicate matrix, destination checks, rename happy path, target-appears, source-swapped-before-link, destination-parent interposition) — reproduce it verbatim from the classes below plus round 1, EXCEPT the unlink-window tests, which encode the round-2 last-copy semantics:

```python
class TestGuardedRenameNoClobber:
    # ... round-1 tests unchanged: happy path, target-appears-before-link,
    # source-swapped-before-link, destination-parent-symlink ...

    def test_source_name_lost_in_unlink_window__link_retained_as_last_copy(
        self, tmp_path: Path
    ) -> None:
        """CR-004 round 2: after the link, the source name lost the bound
        original (swapped for a same-bytes impostor). The target link is now
        the original's possibly-LAST name — the round-1 rollback deleted it,
        which is data loss. It must be RETAINED, the impostor untouched, and
        the intermediate flagged for the dangling-intent path."""
        source, target, identity = self._bound(tmp_path)

        def swap(step: str, path: Path) -> None:
            if step == "unlink":
                source.unlink()
                source.write_bytes(b"content")  # same bytes, different inode

        with pytest.raises(InterferenceError) as exc_info:
            guarded_rename_no_clobber(
                source, target, identity, root_resolved=tmp_path.resolve(), hooks=CommitHooks(swap)
            )
        assert exc_info.value.intermediate is True  # NOT provably pre-action
        st = os.lstat(target)
        assert (st.st_dev, st.st_ino) == (identity.dev, identity.ino)  # last copy retained
        assert source.exists()  # the impostor untouched

    def test_published_target_replaced_in_unlink_window__source_retained_proven(
        self, tmp_path: Path
    ) -> None:
        """Survivor lost but source intact: nothing of ours remains at the
        published name and the source still holds the original — pre-action
        state proven, terminal-honesty allows the failed terminal."""
        source, target, identity = self._bound(tmp_path)

        def swap(step: str, path: Path) -> None:
            if step == "unlink":
                target.unlink()
                target.write_bytes(b"interloper")

        with pytest.raises(InterferenceError) as exc_info:
            guarded_rename_no_clobber(
                source, target, identity, root_resolved=tmp_path.resolve(), hooks=CommitHooks(swap)
            )
        assert exc_info.value.intermediate is False
        assert source.read_bytes() == b"content"  # last copy retained
        assert target.read_bytes() == b"interloper"  # theirs, untouched


class TestGuardedReplace:
    def test_happy_path__replaces_with_mode(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_bytes(b"old")
        f.chmod(0o640)
        bound = bind_file(f)
        guarded_replace(
            f, b"new", expected=bound.identity, mode=bound.mode,
            root_resolved=tmp_path.resolve(), hooks=NO_HOOKS,
        )
        assert f.read_bytes() == b"new"
        assert (os.lstat(f).st_mode & 0o7777) == 0o640

    def test_target_swapped_inside_stage_window__refused(self, tmp_path: Path) -> None:
        """CR-003 round 2: check-then-atomic_write_bytes re-opened the race —
        the interloper arriving DURING staging was clobbered. guarded_replace
        stages first and checks immediately before publish."""
        f = tmp_path / "doc.md"
        f.write_bytes(b"old")
        bound = bind_file(f)

        def swap(step: str, path: Path) -> None:
            if step == "replace-target":
                f.unlink()
                f.write_bytes(b"interloper")

        with pytest.raises(InterferenceError):
            guarded_replace(
                f, b"new", expected=bound.identity, mode=bound.mode,
                root_resolved=tmp_path.resolve(), hooks=CommitHooks(swap),
            )
        assert f.read_bytes() == b"interloper"  # never clobbered
        assert not list(tmp_path.glob(".doc.md.*.docmend-tmp"))  # staged temp cleaned
```

And in `tests/unit/writer/test_atomic.py`:

```python
class TestAbortStagedIdentity:
    def test_raced_staged_temp__not_unlinked(self, tmp_path: Path) -> None:
        """CR-004 round 2: after a staged-temp replacement race, abort must
        not blind-unlink the name — it now holds someone else's object."""
        staged = stage_bytes(tmp_path / "doc.md", b"payload")
        staged.tmp.unlink()
        staged.tmp.write_bytes(b"interloper")
        abort_staged(staged)
        assert staged.tmp.read_bytes() == b"interloper"

    def test_own_staged_temp__unlinked_idempotently(self, tmp_path: Path) -> None:
        staged = stage_bytes(tmp_path / "doc.md", b"payload")
        abort_staged(staged)
        abort_staged(staged)  # idempotent
        assert not staged.tmp.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/writer/test_commit.py tests/unit/writer/test_atomic.py -q`
Expected: FAIL — module missing / `abort_staged` unlinks blindly. No hang (thread-guarded FIFO test).

- [ ] **Step 3: Write the implementation**

`src/docmend/writer/commit.py` — the round-1 module docstring, `InterferenceError`, `BoundFile`, `CommitHooks`/`NO_HOOKS`, `bind_file` (with `O_NONBLOCK`), `check_bound`, and `check_destination` are unchanged from round 1. The observation helper, rollback, rename, and replace primitives:

```python
def _observe_name(path: Path) -> ObjectIdentity | None:
    """lstat a name into an identity; None when the name is absent or holds
    a symlink (either way: not the regular-file object we bound)."""
    try:
        st = os.lstat(path)
    except OSError:
        return None
    if stat.S_ISLNK(st.st_mode):
        return None
    return ObjectIdentity(dev=st.st_dev, ino=st.st_ino)


def _rollback_link(target: Path, expected: ObjectIdentity, root_resolved: Path) -> bool:
    """Undo a just-created link ONLY while the name provably still holds our
    inode (CR-004: rollback itself must not bypass the boundary). Returns
    True when the pre-action state is proven. Granular (CR-004 round 2):
    identity lost at the name -> nothing of ours remains there -> proven;
    identity INTACT but containment lost (parent interposed) -> our inode is
    reachable only through a path we no longer trust -> unproven, do NOT
    unlink through it."""
    observed = _observe_name(target)
    if observed != expected:
        return True
    if not target.resolve().is_relative_to(root_resolved):
        return False
    try:
        target.unlink()
    except OSError:
        return False
    return True


def guarded_rename_no_clobber(
    source: Path,
    target: Path,
    source_identity: ObjectIdentity,
    *,
    root_resolved: Path,
    hooks: CommitHooks,
) -> None:
    """atomic.rename_no_clobber with the adr-0020 checks around BOTH steps.
    FileExistsError (collision race) propagates for the caller's policy.
    Unlink-window outcomes (CR-003/CR-004 round 2):

    - source name lost the original -> the target link is its possibly-LAST
      name; NEVER remove it (last-copy rule) -> intermediate=True, dangling
      intent, adjudication owns the lossless intermediate;
    - published name lost our link, source intact -> pre-action state proven
      -> intermediate=False, failed terminal legal;
    - unlink fails environmentally -> boundary-checked rollback; proven ->
      WriteError (ERR-003), unproven -> intermediate=True.
    """
    hooks.before_step("publish", target)
    check_bound(source, source_identity, root_resolved=root_resolved)
    check_destination(target, root_resolved=root_resolved)
    link_no_clobber(source, target)
    hooks.before_step("unlink", source)
    if _observe_name(source) != source_identity:
        msg = (
            f"{source}: name lost the validated object after link; the published "
            f"link at {target} is retained as the surviving name (last-copy rule)"
        )
        raise InterferenceError(msg, intermediate=True)
    if not source.resolve().is_relative_to(root_resolved):
        msg = f"{source}: no longer resolves inside {root_resolved} after link"
        raise InterferenceError(msg, intermediate=True)
    if _observe_name(target) != source_identity:
        msg = f"{target}: published name replaced before the source unlink; source retained"
        raise InterferenceError(msg)
    if not target.resolve().is_relative_to(root_resolved):
        msg = f"{target}: no longer resolves inside {root_resolved} after link"
        raise InterferenceError(msg, intermediate=True)
    try:
        source.unlink()
    except OSError as exc:
        if _rollback_link(target, source_identity, root_resolved):
            msg = f"{source}: rename linked but source not removed ({exc.strerror or exc})"
            raise WriteError(msg) from exc
        msg = (
            f"{source}: rename linked but source not removed ({exc.strerror or exc}); "
            f"rollback unproven, {target} remains as a second name"
        )
        raise InterferenceError(msg, intermediate=True) from exc
    fsync_dir(target.parent)


def guarded_replace(
    target: Path,
    data: bytes,
    *,
    expected: ObjectIdentity,
    mode: int,
    root_resolved: Path,
    hooks: CommitHooks,
    step: str = "replace-target",
) -> None:
    """Replace an EXISTING object's bytes without the stage-window race
    (CR-003 round 2): check-then-atomic_write_bytes lets an interloper
    arriving DURING the internal staging be clobbered. Order here: stage
    first, then — immediately before the publish — verify the staged inode,
    the target's identity, and containment. Every replacement write on a
    corpus name in docmend goes through this, including rollback and
    adjudication finishes."""
    staged = stage_bytes(target, data, mode=mode)
    hooks.before_step(step, target)
    try:
        check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)
        check_bound(target, expected, root_resolved=root_resolved)
    except InterferenceError:
        abort_staged(staged)  # identity-checked (CR-004) — a raced temp survives
        raise
    publish_staged(staged, target)
```

`src/docmend/writer/atomic.py` — `abort_staged` becomes identity-checked (add `import stat`):

```python
def abort_staged(staged: StagedWrite) -> None:
    """Discard an unpublished staged write (idempotent) — identity-checked
    (plan C review CR-004): after a staged-temp replacement race the name
    holds someone else's object; a blind unlink would destroy it."""
    try:
        st = os.lstat(staged.tmp)
    except OSError:
        return
    if stat.S_ISLNK(st.st_mode) or (st.st_dev, st.st_ino) != (
        staged.identity.dev,
        staged.identity.ino,
    ):
        return
    staged.tmp.unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/writer/test_commit.py tests/unit/writer/test_atomic.py -q`
Expected: PASS (all, within seconds)

- [ ] **Step 5: Full gate, then commit**

```bash
git add src/docmend/writer/commit.py src/docmend/writer/atomic.py \
        tests/unit/writer/test_commit.py tests/unit/writer/test_atomic.py
git commit -m "feat(writer): commit-boundary primitives — descriptor identity, guarded replace/rename, checked abort (adr-0020)"
```

---

### Task 2: Apply binds the source through a descriptor

Unchanged from round 1 (both round-2 reviews passed it): `bind_file` replaces the pathname read in `_execute_action`; `ApplySkipReason` gains `"external-interference"` and `"collision-unpreserved"`; the symlinked-source test uses an in-root referent (CR-008); `bound.mode`/`bound.identity` replace every `source_stat` use.

- [ ] Steps 1-6 as written in round 1 (tests → literal → head rewire → staging/identity block → suites → gate → commit `feat(apply): bind the source to one O_NOFOLLOW descriptor (adr-0020, DMR-06)`).

---

### Task 3: Action-time overwrite invariant + target descriptor binding

**Files/Interfaces:** as round 1 (`strategy_active` published from `gate.py`; clobber path gated on it; `target_bound: BoundFile`; docstring demotion).

- [ ] **Step 1: Write the failing tests** — round-1 tests with ONE structural correction (review round 2, CR-001):

The `TestActionTimeOverwriteInvariant` tests at THIS task call the engine directly (no gate runs — `_execute` is a plain `execute_plan` wrapper until Task 9), so creating the target before `_execute` is fine HERE and exercises exactly the action-time check. Add this comment to the test docstring so Task 9's migration does not silently invert it:

```python
        # ORDERING CONTRACT (review round 2, CR-001): at Task 9 this test
        # migrates onto apply_write_context, whose gate would refuse a
        # pre-existing strategyless overwrite target before the action-time
        # check is ever reached. The migrated form MUST acquire the safety
        # context while the target is ABSENT and create the target inside
        # the context, immediately before execute_plan — deterministically
        # exercising the gate->action window.
```

- [ ] **Steps 2-5** as round 1 (verify failure → `strategy_active` + invariant → target rebind → suites, gate, commit `feat(apply): action-time overwrite invariant + descriptor-bound target (DMR-07, adr-0020 F3)`).

---

### Task 4: Per-step commit checks — rewrite and rename paths

**Files/Interfaces:** as round 1 (hooks threading; checks in the `rewrite`/`rename` arms; `InterferenceError` handler with terminal-honesty; `FileExistsError` → `collision-unpreserved`).

- [ ] **Step 1: Write the failing tests** — the round-1 set stands (source-swap-after-intent, staged-temp-swap, target-created-before-publish, published-target-replaced-before-unlink → source retained + proven failed terminal, target-replaced-after-backup, parent-symlink), PLUS one round-2 addition:

```python
    def test_rename__source_lost_in_unlink_window__dangling_intent_last_copy(
        self, tmp_path: Path
    ) -> None:
        """CR-004 round 2 at the engine level: the source name lost the
        original after the link. The published link is the last copy — it
        must survive, and the intent must stay DANGLING (terminal-honesty:
        the corpus is NOT pre-action; it is a lossless intermediate)."""
        root, plan, config, options, manifest_path = self._planned_rename(tmp_path)
        source = root / plan.actions[0].path
        target = root / plan.actions[0].target_path

        def swap(step: str, path: Path) -> None:
            if step == "unlink":
                payload = source.read_bytes()
                source.unlink()
                source.write_bytes(payload)

        report = self._execute(plan, config, options, manifest_path, hooks=CommitHooks(swap))
        outcome = report.outcomes[0]
        assert outcome.status == "failed"
        assert outcome.error is not None and outcome.error.error_class == "ERR-002"
        assert target.exists()  # last copy retained
        assert [r["result"] for r in read_records(manifest_path)] == ["intent"]  # dangling
```

- [ ] **Steps 2-5** as round 1. The `except InterferenceError` handler is exactly round 1's (both terminal-honesty arms). Commit: `feat(apply): at-commit identity checks for rewrite/rename — survivor, staged-temp, destination (DMR-06/07)`.

---

### Task 5: Per-step commit checks — `rename_and_rewrite` windows and boundary-checked rollback

**Files/Interfaces:** as round 1, with `_undo_publish` now built on `guarded_replace` and the composition test premise corrected (CR-NEW-002).

- [ ] **Step 1: Write the failing tests** — round-1 set stands, with the composition test corrected:

```python
    def test_dangling_interference_intent__resume_adjudicates_and_leaves_it_dangling(
        self, tmp_path: Path
    ) -> None:
        """Terminal-honesty composes with Plan B adjudication (CR-NEW-002):
        a resume over the dangling intent adjudicates external-interference
        from disk (target holds neither the expected identity nor bytes) and
        reports failed ERR-002 WITHOUT touching either file — and WITHOUT
        appending a closure terminal: interference cannot prove any state,
        so the intent legitimately remains dangling for the operator (the
        current `_adjudicate_pending_intent` interference arm appends
        nothing, which is the correct honesty behavior — do not change it)."""
        ...  # run the published-target-replaced scenario, then execute a
        # resume run over the same plan + chain read via read_manifest_chain;
        # assert the resume outcome is failed ERR-002, both files' bytes
        # unchanged, and the RESUME manifest contains NO record for the
        # action (nothing to assert; the run-1 intent stays the only record).
```

- [ ] **Step 3: `_undo_publish` on `guarded_replace`** (replaces round 1's check-then-`atomic_write_bytes`, CR-003 round 2):

```python
def _undo_publish(
    target: Path,
    expected_identity: ObjectIdentity,
    target_bound: BoundFile | None,
    root_resolved: Path,
) -> bool:
    """Roll a rename_and_rewrite publish back WITHOUT bypassing the boundary
    (CR-004): returns True when the pre-action state is proven. The
    clobbered-content reinstatement goes through guarded_replace — stage
    first, verify our published inode is still at the name immediately
    before replacing it — and comes back with the CLOBBERED object's mode
    (round 1 used the source's mode; wrong file). Byte/mode-exact, not
    inode-exact — os.replace cannot resurrect the original inode; the
    recorded overwritten backup carries the recovery contract (FR-006)."""
    if target_bound is None:
        observed = _observe_name(target)
        if observed != expected_identity:
            return True  # nothing of ours remains at the name
        if not target.resolve().is_relative_to(root_resolved):
            return False  # our inode behind an interposed parent (CR-004 rd 2)
        try:
            target.unlink()
        except OSError:
            return False
        return True
    try:
        guarded_replace(
            target,
            target_bound.data,
            expected=expected_identity,
            mode=target_bound.mode,
            root_resolved=root_resolved,
            hooks=NO_HOOKS,
        )
    except (InterferenceError, WriteError):
        return False
    return True
```

(`_observe_name` is imported from `commit`; expose it there as a public-ish helper or re-derive with `os.lstat` — prefer importing to keep one implementation.)

- [ ] Remaining steps as round 1: the `rename_and_rewrite` arm (staged-temp check, clobber/absent destination checks, survivor checks, `_undo_publish` in both the refused-check and failed-unlink paths, InterferenceError re-raise vs WriteError). Note the source-lost sub-case inside this arm's unlink window: `check_bound(source, ...)` failing means the published target holds OUR staged output (not the original — the original's bytes live in the backup or are re-derivable), so `_undo_publish` legitimately removes it; the last-copy rule concerns the RENAME kind, where the target link IS the original inode. State this in a comment. Commit: `feat(apply): rename_and_rewrite commit windows — guarded rollback, dangling-intent honesty`.

---

### Task 6: Restore binds the live target and checks every inverse step

**Files/Interfaces:** as round 1, with two round-2 corrections.

- [ ] **Step 1: tests** — round-1 set stands; the retry test premise is now VALID because the standalone-failed chain defect it tripped over was found and fixed while verifying CR-NEW-002 (`8c2d5f4`, regression-tested in `tests/test_manifest_chain.py` and `tests/test_resume.py`). Keep it as written:

```python
    def test_restore_failed_terminal_then_retry__converges(self, tmp_path: Path) -> None:
        """CR-004 + CR-NEW-002: a pre-mutation restore failure (unwritable
        staging) appends the standalone failed inverse — chain-legal since
        8c2d5f4 — and proves nothing was mutated, so the reducer's
        `restore-failed` state falling through to a fresh `_restore_one` is
        correct and must converge. Fail staging (read-only original parent),
        fix the environment, re-run restore over both manifests, assert the
        action restores cleanly."""
        ...
```

- [ ] **Step 3: rewire** — as round 1 (bind-once preflight, per-step checks, survivor checks, `mutated` flag, dangling-intent arms), with the clobbered-target reinstatements switched from check-then-`atomic_write_bytes` to `guarded_replace` (CR-003 round 2):

```python
        elif record.operation == "rename":
            if clobbered is not None:
                hooks.before_step("publish", original)
                check_bound(target, live.identity, root_resolved=root_resolved)
                check_destination(original, root_resolved=root_resolved)
                link_no_clobber(target, original)
                mutated = True
                # Survivor check + stage-first replacement in ONE primitive:
                # guarded_replace verifies the reinstated original... no —
                # the survivor check is separate; guarded_replace verifies
                # the REPLACED name. Both, explicitly:
                check_bound(original, live.identity, root_resolved=root_resolved)
                guarded_replace(
                    target, clobbered, expected=live.identity, mode=mode,
                    root_resolved=root_resolved, hooks=hooks,
                )
            else:
                guarded_rename_no_clobber(
                    target, original, live.identity, root_resolved=root_resolved, hooks=hooks
                )
        else:  # rename_and_rewrite
            assert staged is not None
            hooks.before_step("publish", original)
            check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)
            check_destination(original, root_resolved=root_resolved)
            reinstated_identity = staged.identity
            publish_staged(staged, original, clobber=False)
            mutated = True
            hooks.before_step("unlink", target)
            check_bound(original, reinstated_identity, root_resolved=root_resolved)
            if clobbered is not None:
                guarded_replace(
                    target, clobbered, expected=live.identity, mode=mode,
                    root_resolved=root_resolved, hooks=hooks, step="replace-target",
                )
            else:
                check_bound(target, live.identity, root_resolved=root_resolved)
                target.unlink()
```

(Clean up the mid-code comment above before landing — it is plan-annotation, not code. The `rewrite` arm is round 1's unchanged.) The `except` arms are round 1's (interference → dangling when `mutated or exc.intermediate`; environmental after first step → dangling; pre-mutation → failed terminal).

- [ ] Remaining steps as round 1. Commit: `feat(restore): descriptor-bound inverse commits — survivor checks, guarded replace, dangling-intent honesty (adr-0020)`.

---

### Task 7: Adjudication finishes go through the boundary (CR-NEW-001)

**Files:**
- Modify: `src/docmend/writer/adjudicate.py` (`finish_remaining`, `_verified_unlink`, `_rewrite_from_backup`)
- Modify: `src/docmend/writer/apply.py` (`_adjudicate_pending_intent` forwards `root_resolved` + hooks), `src/docmend/restore.py` (`_converge_pending_restore` likewise)
- Test: `tests/unit/writer/test_adjudicate.py`

**Interfaces:**
- Consumes: `check_bound`-style containment, `guarded_replace`, `CommitHooks`, `NO_HOOKS`, `InterferenceError` from Task 1.
- Produces: `finish_remaining(record, *, undone=None, root_resolved: Path, hooks: CommitHooks = NO_HOOKS) -> None` — every residual mutation carries the same guarantees as live commits. `finish_remaining`'s current docstring names this exact seam: "the adjudicate-to-act window is the accepted residual until Plan C's CommitBoundary".

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/writer/test_adjudicate.py` (reuse its existing record/fixture builders):

```python
class TestFinishRemainingBoundary:
    def test_finish_unlink__parent_interposed__refused(self, tmp_path: Path) -> None:
        """CR-NEW-001: the residual unlink re-resolves containment at the act
        instant — a parent swapped for an out-of-root symlink between
        adjudication and finish must refuse, exactly like a live commit."""
        ...  # build the finish-remaining apply state (target published,
        # source name still present) in root/sub/, adjudicate, swap
        # root/sub for a symlink to an outside dir, call finish_remaining
        # with root_resolved=root; expect WriteError/InterferenceError and
        # the out-of-root file untouched.

    def test_finish_rewrite_from_backup__target_swapped_in_stage_window__refused(
        self, tmp_path: Path
    ) -> None:
        """The clobbered-bytes reinstatement is a replacement write and gets
        guarded_replace's stage-first ordering — a hook-injected swap during
        staging must refuse, never clobber."""
        ...  # finish-remaining inverse-rename state; hooks swap the applied
        # name at "replace-target"; expect refusal, interloper intact.

    def test_finish_rewrite_from_backup__preserves_target_mode(self, tmp_path: Path) -> None:
        ...  # chmod the applied file 0o640 before finish; assert the
        # reinstated clobbered bytes carry 0o640 (guarded_replace mode
        # comes from the observed object, closing a silent 0o600 regression).
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/writer/test_adjudicate.py -k Boundary -q`
Expected: FAIL — `finish_remaining` has no `root_resolved`/`hooks` parameters.

- [ ] **Step 3: Route the mutations through the boundary**

```python
def finish_remaining(
    record: ManifestRecord,
    *,
    undone: ManifestRecord | None = None,
    root_resolved: Path,
    hooks: CommitHooks = NO_HOOKS,
) -> None:
    """Complete the residual step(s) of a `finish-remaining` adjudication.

    Plan C (CR-NEW-001): each step here is a corpus mutation and carries the
    full commit boundary — the identity+hash re-verification it always had,
    PLUS containment re-resolved at the act instant and stage-first
    replacement writes. The adjudicate-to-act window this closes was the
    stated residual of the Plan B implementation.
    """
    ...  # dispatch unchanged; the two primitives change:


def _verified_unlink(
    path: Path,
    identity: ObjectIdentity | None,
    sha256: str,
    *,
    root_resolved: Path,
    hooks: CommitHooks,
) -> None:
    hooks.before_step("unlink", path)
    observed = _observe(path)
    if not _is(observed, identity, sha256):
        msg = f"{path}: object changed between adjudication and unlink; refusing"
        raise WriteError(msg)
    if not path.resolve().is_relative_to(root_resolved):
        msg = f"{path}: no longer resolves inside {root_resolved}; refusing finish"
        raise WriteError(msg)
    try:
        path.unlink()
    except OSError as exc:
        msg = f"{path}: cannot finish adjudicated unlink ({exc.strerror or exc})"
        raise WriteError(msg) from exc


def _rewrite_from_backup(
    record: ManifestRecord,
    undone: ManifestRecord | None,
    *,
    root_resolved: Path,
    hooks: CommitHooks,
) -> None:
    ...  # backup read + hash verification unchanged; then:
    target = Path(record.original_path)
    st = target.lstat()  # observed object's own mode (silent-0o600 fix)
    assert record.source_identity is not None  # adjudication verdict verified it
    try:
        guarded_replace(
            target, data, expected=record.source_identity, mode=st.st_mode,
            root_resolved=root_resolved, hooks=hooks,
        )
    except InterferenceError as exc:
        raise WriteError(str(exc)) from exc  # callers' existing WriteError contract
```

Callers: `_adjudicate_pending_intent` already has `root_resolved` — forward it (`finish_remaining(record, root_resolved=root_resolved, hooks=hooks)`; thread `hooks` into `_adjudicate_pending_intent`'s signature). `_converge_pending_restore` gains `root_resolved`/`hooks` parameters from `run_restore`'s existing locals.

- [ ] **Step 4: Run tests, full gate, commit**

Run: `uv run pytest tests/unit/writer/test_adjudicate.py tests/test_resume.py tests/test_restore.py -q` then the gate.

```bash
git add src/docmend/writer/adjudicate.py src/docmend/writer/apply.py src/docmend/restore.py \
        tests/unit/writer/test_adjudicate.py
git commit -m "feat(adjudicate): finish-remaining mutations through the commit boundary (CR-NEW-001)"
```

---

### Task 8: Attested `WriteSafetyContext` and the two sealed factories

**Files:**
- Modify: `src/docmend/writer/commit.py` (append the F8 half)
- Modify: `src/docmend/writer/manifest.py` (`ManifestSet.records: tuple[ManifestRecord, ...]`, `ManifestChain.sets: tuple[ManifestSet, ...]` — constructors wrap with `tuple(...)`; adjust `tests/helpers/manifest2.chain_of` accordingly)
- Test: `tests/unit/writer/test_commit.py`

**Interfaces:**
- Consumes: as round 1 plus `hashlib`.
- Produces (Tasks 9-10 rely on these exactly):
  - `SafetyRefusedError` family as round 1 (`LockRefusedError`, `DestinationRefusedError`, `WriteRefusedError.refusals`)
  - `@final class WriteSafetyContext` — sealed AND attested over the ACTUAL gated inputs (CR-002 round 2): methods `confirm_apply(*, plan, config, plan_sha256, source_root, run_id, options, manifest_path) -> None` (recomputes the plan/config model digests from the PRESENTED objects and compares to the digests the factory computed from the objects it GATED), `confirm_restore(*, run_id, manifest_out) -> None`, `confirm_report(report_path: Path) -> None` (the guarded report destination), property `chain: ManifestChain` (restore contexts only; immutable by the tuple change)
  - `apply_write_context(plan, config, *, source_root, options, plan_sha256, run_id, manifest_path, report_path, manifest_dir, input_artifacts=(), artifact_root=None, lock_state_dir=None, on_refusal=None) -> Iterator[WriteSafetyContext]`
  - `restore_write_context(manifest_paths, *, run_id, manifest_out, exclude, artifact_root=None, lock_state_dir=None) -> Iterator[WriteSafetyContext]` — performs the chain preflight ITSELF

- [ ] **Step 1: Write the failing tests** — round-1 set stands (sealing, deactivation, lock held, in-lock `on_refusal` probe, destination/lock refusals, restore factory validates + exposes chain), with the attestation tests extended:

```python
    def test_attestation_binds_the_gated_models_not_a_caller_hash(
        self, tmp_path: Path
    ) -> None:
        """CR-002 round 2: gating benign plan A while declaring plan B's hash
        must not authorize executing B — the digests are computed from the
        OBJECTS the factory gated and recomputed from the objects presented
        at confirm time."""
        with apply_write_context(plan_a, config, ..., plan_sha256=sha_of_b) as safety:
            with pytest.raises(RuntimeError, match="attestation"):
                safety.confirm_apply(plan=plan_b, config=config, plan_sha256=sha_of_b, ...)

    def test_attestation_binds_config(self, tmp_path: Path) -> None:
        ...  # same factory entry; confirm with a config whose collision
        # policy differs -> RuntimeError("attestation")

    def test_confirm_report__bound_to_guarded_destination(self, tmp_path: Path) -> None:
        with apply_write_context(..., report_path=tmp_path / "r.json") as safety:
            safety.confirm_report(tmp_path / "r.json")
            with pytest.raises(RuntimeError, match="attestation"):
                safety.confirm_report(tmp_path / "elsewhere.json")

    def test_restore_chain_is_immutable(self, tmp_path: Path) -> None:
        """CR-002 round 2: the validated chain cannot be mutated between
        preflight and run_restore — sets/records are tuples."""
        with restore_write_context([m1], ...) as safety:
            with pytest.raises((TypeError, AttributeError)):
                safety.chain.sets[0].records.append(anything)  # type: ignore[union-attr]
```

- [ ] **Step 3: Implement** — round 1's exceptions, `_guard_or_refuse`, factory skeletons (in-lock gate + `on_refusal`, lock wrap, guard-first) stand. The attestation:

```python
def _model_digest(model: BaseModel) -> str:
    """Canonical content digest of a pydantic model — what binds the gated
    plan/config to the executed plan/config (CR-002 round 2). model_dump_json
    is deterministic for a given model instance's field values."""
    return hashlib.sha256(model.model_dump_json().encode()).hexdigest()


@dataclass(frozen=True)
class _Attestation:
    command: str  # "apply" | "restore"
    source_root: Path  # resolved
    run_id: str
    plan_digest: str | None  # _model_digest of the GATED Plan (apply)
    config_digest: str | None  # _model_digest of the GATED config (apply)
    plan_sha256: str | None  # the plan ARTIFACT hash the header will carry
    subject_sha256: str | None  # chain tip manifest sha (restore)
    options: ApplyOptions | None
    manifest_path: Path  # resolved; restore: manifest_out
    report_path: Path | None  # resolved (apply)
    chain: ManifestChain | None  # restore only — tuple-frozen, factory-validated
```

`confirm_apply` recomputes `_model_digest(plan)`/`_model_digest(config)` from the presented objects and compares all of `(plan_digest, config_digest, plan_sha256, source_root, run_id, options, manifest_path)`; `confirm_report(report_path)` compares the resolved path; `confirm_restore` as round 1. The apply factory computes the digests from the `plan`/`config` arguments it just gated. The restore factory is round 1's (chain preflight inside, tip sha, `exclude` required) — now yielding a tuple-frozen chain because of the manifest.py change.

- [ ] **Step 4: Run tests (including the full manifest/chain suites for the tuple change), full gate, commit**

Run: `uv run pytest tests/unit/writer/test_commit.py tests/unit/writer/test_manifest.py tests/test_manifest_chain.py tests/test_restore.py -q` then the gate.

```bash
git add src/docmend/writer/commit.py src/docmend/writer/manifest.py \
        tests/helpers/manifest2.py tests/unit/writer/test_commit.py
git commit -m "feat(writer): attested WriteSafetyContext — gated-model digests, immutable chain, factory preflight (F8)"
```

---

### Task 9: Apply engine split (`preview_plan` / `execute_plan`) + CLI rewire + test migration

As round 1 with three round-2 corrections. Files as round 1 (+`artifacts.py` clobber passthrough).

- [ ] **Step 1: engine tests** — round 1's, with the mismatch test now exercising the model-digest binding (present plan B to a plan-A capability holding plan B's *hash* — refused; this is the CR-002 round 2 scenario, already unit-tested at Task 8; here it proves the engine seam calls it).

- [ ] **Step 2: split** — as round 1; `execute_plan`'s confirmation becomes:

```python
    safety.confirm_apply(
        plan=plan,
        config=config,
        plan_sha256=plan_sha256,
        source_root=Path(plan.source_root or ""),
        run_id=run_id,
        options=options,
        manifest_path=manifest_path,
    )
```

- [ ] **Step 3: `write_report` clobber passthrough** — as round 1.

- [ ] **Step 4: `tests/helpers/writectx.py`** — as round 1 (signature already carries `plan_sha256`).

- [ ] **Step 5: CLI rewire** — as round 1 (`_on_refusal` in-lock closure, `plan_sha` hoisted, `guard_inputs` hoisted, no-clobber refusal report with the preserved-artifact stderr note), plus ONE line before the report write:

```python
                safety.confirm_report(report_path)  # CR-002 rd 2: the guarded destination
                artifacts.write_report(result, report_path)
```

- [ ] **Step 6: migrate the test suite** — as round 1, plus the CR-001 restructure this round makes explicit:

`TestActionTimeOverwriteInvariant` migrates to this exact shape (the gate would otherwise refuse the pre-existing strategyless target and the action-time check would never run):

```python
        with apply_safety(plan, config, options=options, plan_sha256=SHA,
                          manifest_path=mp, report_path=rp, run_id=RUN,
                          state_dir=tmp_path / "locks") as safety:
            # The gate has passed (no target existed). NOW the target appears
            # — inside the gate->action window the invariant exists for.
            target.write_bytes(b"late arrival")
            report = execute_plan(plan, config, ..., safety=safety)
        assert report.outcomes[0].skip_reason == "collision-unpreserved"
```

- [ ] **Step 7: full suite, gate, commit** — as round 1. Commit: `feat(apply): preview/write entrypoint split — attested WriteSafetyContext required (F8)`.

---

### Task 10: Restore engine split (`preview_restore` / `run_restore`) + CLI rewire with effective config

As round 1 with the CR-NEW-003 correction: **no new CLI flags.**

- [ ] **Step 1: tests** — round 1's set (capability-bound chain, expired/mismatch, preview purity, exclusion-removed rejection at the factory seam).

- [ ] **Step 2: split** — round 1's `preview_restore` / chain-less `run_restore`.

- [ ] **Step 3: CLI rewire** — round 1's structure, EXCEPT the config source (review round 2, CR-NEW-003 — IR-008's binding interface gains no options): restore resolves its effective excludes through the SAME default discovery every command already uses, with no new public surface:

```python
    # Effective excludes for the artifact-destination carve-out (CR-006):
    # the default discovery (./docmend.toml when present, else defaults) —
    # deliberately NO new restore CLI options (IR-008 unchanged; review
    # CR-NEW-003). An operator who removed the .docmend/** exclusion in
    # their project config gets the refusal that removal implies; one who
    # relies on per-invocation --exclude flags at scan/plan time gets the
    # file+defaults view, the conservative direction for a carve-out
    # LICENSE (fewer licensed destinations, never more).
    config = _load_effective_config(None, None, None)
```

If the owner prefers an explicit `--config` on restore, that is an IR-008 amendment decision — raise it as an OQ rather than deciding here.

- [ ] **Steps 4-5** as round 1 (test migration; suites; gate). Commit: `feat(restore): preview/write split — capability-bound chain, default-discovery carve-out excludes (F8)`.

---

### Task 11: Changelog

As round 1, with these edits to the drafted section: drop the "`restore` gains `--config`/`--include`/`--exclude`" clause (replaced by "restore licenses its artifact destination against the project's `docmend.toml` excludes via the standard default discovery"); add one bullet for CR-NEW-001 ("post-crash adjudication finishes now carry the same commit boundary as live mutations — containment re-resolved at the act instant, stage-first replacement writes, observed-mode preservation") and one for the last-copy rule ("no rollback ever removes the last surviving name of a validated object; unprovable intermediates keep their journal intent for adjudication instead of asserting a clean failure"). Commit: `docs(changelog): plan C — commit boundary, action-time overwrite invariant, F8 split`.

---

### Task 12: Spec §17.3 traceability sync (CR-009)

Unchanged from round 1 (rows FR-003/FR-005/FR-011/IR-008 with named Plan C tests; reconciliation of the already-landed Plan A/B rows — FR-006, FR-013, IR-007, DR-003, DR-004 — that still read "pending v2 implementation"; FR-014/IR-004 stay honestly pending for Plan D; one Document History row; `check_traceability.py` + spec validation + full gate). Commit: `docs(spec): §17.3 traceability sync for plans A-C (review CR-009)`.

---

## Self-Review Notes (design-coverage check)

- Design §Commit Boundary F2/F3 → Tasks 1-6; the strategy re-check closes the gate→action window (CR-001) and the migrated test provably exercises it (Task 9). Residual-window statement → Task 11 + `commit.py` docstring. Deterministic hooks for every listed window plus rounds 1-2 additions → mapping table in File Structure.
- Design §F8 → Tasks 8-10 — the capability attests the GATED models by digest (CR-002 round 2), the restore preflight is factory-owned with a tuple-frozen chain, and adjudication's finish path (invoked by both gated engines) carries the same boundary (CR-NEW-001), so no mutation surface remains outside adr-0020's checks: live commits (Tasks 2-6), rollbacks (Tasks 1/5), staged-temp cleanup (Task 1), and adjudicated finishes (Task 7).
- adr-0020 Confirmation list: every named race test exists; the same-bytes/different-inode probes have live-window counterparts; the dangling-intent → resume-adjudication composition test reflects the ACTUAL interference contract (no closure terminal — CR-NEW-002).
- adr-0021's exclusion-removed rejection test exists at the restore seam (Task 10).
- Already landed during review (not plan tasks): the chain validator's standalone-failed rejection — a live Plan B defect making any run with a pre-mutation failure unresumable — fixed as `8c2d5f4` with chain + e2e regressions and the design's lifecycle sentence disambiguated (CR-NEW-002).
- Deliberate decisions for the reviewer: (1) `WriteSafetyContext` lives in `writer/commit.py` (one new module, per the design's file map); (2) the action-time strategy re-check fires on write runs only — preview options are synthesized without the operator's strategy flags (Task 3 comment); (3) restore's write path parses the chain twice (CLI messaging + factory preflight) — the price of an unforgeable validated-chain capability; (4) preview keeps today's CLI-side locking per F8's "current lock semantics"; (5) `_undo_publish`/`guarded_replace` prove bytes+mode, not inode — `os.replace` cannot resurrect an inode; the recorded backup carries the recovery contract; (6) restore's carve-out excludes come from the default config discovery, not new flags (CR-NEW-003) — an explicit `--config` for restore is an IR-008 amendment left to the owner as an OQ; (7) the rename-kind last-copy rule vs the rename_and_rewrite rollback distinction: a rename's target link IS the original inode (never removable when the source is lost), while a rename_and_rewrite's published target is the staged OUTPUT whose source-side original is independently preserved — stated where the code diverges (Task 5).
- Type-consistency: primitives' names/signatures identical across Tasks 1-7; `confirm_apply(plan=, config=, ...)`/`confirm_restore`/`confirm_report`/`safety.chain` across 8-10; `apply_safety`/`restore_safety` across 9-10; `plan_sha256` threads factory → engine → header as one value, with the model digests carrying the actual-object binding.
