# Safety-Core Plan C — Commit Boundary (DMR-06/07) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind every corpus mutation to one filesystem object instead of a pathname — descriptor-captured `(st_dev, st_ino)` identity checked immediately before every publish and unlink (DMR-06), a no-clobber action-time overwrite invariant (`collision-unpreserved`, DMR-07) — and split the engines into read-only preview and `WriteSafetyContext`-gated mutation entrypoints (F8).

**Revision note (round 1):** revised per plan-review round 1 (CR-001..CR-009, all verified against `df28beb`): action-time strategy re-check (CR-001); attested capability + factory-owned restore preflight (CR-002); absent-destination/staged-temp/survivor coverage (CR-003); boundary-checked rollback + dangling-intent honesty (CR-004); `O_NONBLOCK` bind (CR-005, reproduced); effective excludes for restore (CR-006 — the round-0 "defaults are conservative" claim was inverted); in-lock, no-clobber refusal reports (CR-007); in-root symlink referents (CR-008); §17.3 traceability task (CR-009).

**Revision note (round 2):** revised per plan-review round 2. CR-001: the action-time window test's migrated form acquires the safety context while the target is absent and creates it inside the context (the round-1 ordering would have refused at the gate once Task 9 migrates the tests). CR-002: the attestation binds digests of the ACTUAL `Plan` and `DocmendConfig` the gate evaluated (recomputed at `confirm_apply` from the presented objects), plus `report_path` with a `confirm_report` seam; `ManifestSet.records`/`ManifestChain.sets` become tuples so `safety.chain` is immutable. CR-003: check-then-`atomic_write_bytes` re-opened the stage-window race — a new `guarded_replace` primitive stages FIRST, then checks staged inode + target identity + containment immediately before publish; used by `_undo_publish`, restore's clobbered-target reinstatement, and adjudication. CR-004: when the SOURCE name loses the bound original after a link, the published link is its possibly-last name and is never removed (lossless intermediate, dangling intent) — the round-1 rollback destroyed it; `_rollback_link` distinguishes identity-lost (proven, nothing ours remains) from containment-lost-with-identity-intact (unproven); `abort_staged` is now identity-checked so a raced staged temp is never blind-unlinked. CR-NEW-001: new Task 7 routes `finish_remaining`'s mutations (both resume and restore invoke them) through the same boundary — its docstring already named Plan C as the closer of that window. CR-NEW-002: the resume composition test premise is corrected (an external-interference verdict leaves the intent dangling; no closure terminal); the restore retry premise was false against a REAL, previously unshipped defect found while verifying it — the chain validator wholesale-rejected the producer's own pre-mutation standalone `failed` shape, making any run with an ordinary staging/backup failure unresumable — fixed, tested, and pushed as `8c2d5f4` with the design's lifecycle sentence disambiguated, so the test premise now stands. CR-NEW-003: the new restore CLI flags are withdrawn; restore instead loads the project's `docmend.toml` via the existing default discovery (no new public interface; flagged below for owner sign-off). This revision also restores the full inline content of every task — the first round-2 commit (`f501c26`) had compressed unchanged tasks to references against the superseded round-1 text, leaving the document non-self-contained.

**Revision note (round 3):** revised per plan-review round 3, all findings verified. CR-002: `ManifestHeader`/`ManifestRecord` become `frozen=True` pydantic models (the writer already stamps via `model_copy`, so producers are unaffected) with an inner-field-mutation regression, and the tuple migration enumerates ALL construction sites (`manifest.py:494/690/703`, `tests/helpers/manifest2.py`, `tests/test_restore.py:66`). CR-003: `guarded_replace` gains a `survivor` parameter verified INSIDE the primitive, immediately before publish — the earlier survivor checks ran before staging, leaving the survivor swappable during it. CR-004: `_rollback_link`/`_undo_publish` check containment FIRST (an identity observation through an interposed parent proves nothing about the real location), `_observe_name` returns a four-state observation so permission/IO errors are "unobservable" (unproven) rather than collapsing into absence, and `abort_staged` gains an optional containment root. CR-006: the round-2 default-discovery claim was inverted a second way — list flags REPLACE the config set, so defaults can re-license `.docmend/**` an operator-replaced set had withdrawn; the fix persists the apply run's effective excludes in the manifest 2.0 header (pre-release additive field) and the restore factory licenses against the RECORDED excludes, with a change-control step for the wire-model addition. CR-NEW-001: adjudication's `_observe` becomes descriptor-bound (identity and bytes from one object) and `_verified_unlink` verifies the required survivor before destroying anything. CR-NEW-004: `publish_staged`'s internal cleanup paths route through identity-checked removal (blind `tmp.unlink` could delete an interloper after a staged-name race). CR-NEW-005: the dry-run report publishes no-clobber (adr-0021: a dry run leaves prior artifacts untouched). CR-NEW-006: the sealed constructor gives `_attest` a `None` default so the sealing `TypeError` — not Python argument binding — is what rejects direct construction. Also fixed: the plan document itself now passes the repo's markdownlint (MD049 underscore emphasis) and Prettier.

**Revision note (round 4):** revised per plan-review round 4, all findings verified (the nested-model assignment reproduced live). CR-002: immutability goes to the leaves — `ObjectIdentity`/`PriorAttempt` (lineage.py) and `ErrorInfo` (report.py) gain `frozen=True`, making the chain deep-frozen through every nesting level; and the apply capability now CARRIES deep copies of the gated `Plan`/`DocmendConfig` (exact symmetry with restore's `safety.chain`) — `execute_plan` consumes `safety.plan`/`safety.config`, so post-confirmation mutation of caller-held objects is structurally unreachable and the round-2 digest machinery is deleted as redundant. CR-004: the `rename_and_rewrite` source-swap outcome is corrected to a DANGLING intent (the interloper destroyed the original's name — pre-action state is unprovable even after our publish rolls back; the round-3 test premise of a `failed` closure violated the plan's own terminal-honesty rule), with the survivor-lost case split by clobber shape; and both engines now pass `root_resolved` to `abort_staged`. CR-006: the `effective_excludes` wire-model addition gains an explicit OWNER-APPROVAL CHECKPOINT — Task 8 must not begin until the owner signs off. CR-NEW-001: `_verified_unlink` re-authorizes the pathname with `check_bound` immediately before the unlink (the descriptor observation closes before deletion), and the survivor is verified after the long target read, containment included. CR-NEW-004: `stage_bytes` becomes descriptor-clean — `os.fchmod` on the open descriptor replaces the pathname `chmod`, the exclusively-created inode's identity is captured at open, and failure cleanup is identity-checked. CR-NEW-007: `Literal` added to Task 1's typing import (the plan's own code failed to import). CR-NEW-008: the entire `effective_excludes` production moves INTO Task 8 (model + schema + both current header constructors + fixtures) so the task gates green atomically; its commit block stages every file the task touches; `read_records`' annotation follows the tuple migration.

**Revision note (round 5):** revised per owner review round 5; implementation remains gated pending a fresh approval round. CR-R5-001: the apply factory now derives the authority root from a private pre-gate plan snapshot — there is no independent `source_root` argument that can lock/guard one corpus while the engine mutates another. CR-R5-002: the capability stores immutable serialized plan/config payloads, exposes no mutable model properties, and reconstructs fresh engine-private models only at execution; the factory copies before gate evaluation, closing both the direct `safety.plan`/`safety.config` bypass and the gate-to-copy race. CR-R5-003: `_rollback_link` and `_undo_publish` verify the surviving source inside the rollback primitive immediately before removing/replacing the published name; if that proof is lost, the output is retained and the intent stays dangling. CR-R5-004: adjudication observations become explicit `regular | absent | symlink | unobservable` states, so EACCES/EIO can never satisfy an absence predicate. CR-R5-005: the three stale existing test seams (directory overwrite target, apply no-clobber injection, restore mid-rename injection) are migrated explicitly. CR-R5-006: adjudicated backup rewrites bind mode and identity through one descriptor. CR-R5-007: unused Task 8 imports are removed.

**Revision note (round 6):** revised per owner review round 6; implementation remains gated pending a fresh approval round. CR-R6-001: the factory resolves the private plan snapshot's source root once, writes that canonical path back into the retained snapshot, and uses the same value for guard/gate/lock/execution — cwd changes and symlink repoints cannot redirect authority. CR-R6-002: Task 9/10 no longer preserve dual-mode `_run_plan`/`_run_restore` helpers; preview and mutation cores are structurally separate, every mutation helper requires an active capability, and no naked `write` boolean reaches a corpus-mutating helper. CR-R6-003: rollback observes/re-authorizes the target first and verifies the survivor last, immediately before destructive unlink. CR-R6-004: the unused Task 9 pathspec imports are removed.

**Revision note (round 7):** revised per owner review round 7; implementation remains gated pending a fresh approval round. CR-R7-001: mutation-mode resume manifests are now PATH inputs to the apply factory; it validates and freezes the chain, binds root/plan hash, and carries the chain/prior-attempt evidence so `execute_plan` accepts no caller-supplied resume state. CR-R7-002: mutation orchestration helpers no longer accept raw action/root/config/record inputs plus an active command token; sealed `_ApplyRun`/`_RestoreRun` states derive every authority-bearing value from the capability, and helpers accept only that state plus a known action ID. CR-R7-003: Task 10 explicitly migrates `tests/test_apply.py` and converts synthetic write-restore chains to valid on-disk manifests (pure ordering tests may stay in-memory). Low-level POSIX/atomic primitives remain internal mechanisms and unit-test seams, not public write-capable engine entrypoints; Python module privacy is not claimed as a sandbox against callers who could invoke `os.replace` directly.

**Revision note (round 8):** revised per owner review round 8; implementation remains gated pending a fresh approval round. CR-R8-001: write apply now gives the factory predecessor manifest **and report** paths; the factory validates the complete no-gap attempt graph and derives `PriorAttempt` itself, preserving legal report-only predecessors. No free-standing attempt edge crosses the public factory boundary. CR-R8-002: the factory consumes the plan artifact path, reads/validates the plan, hashes it, and constructs the complete `ArtifactRef`; `execute_plan` accepts neither `plan_ref` nor `plan_sha256`. The same factory-owned evidence drives the gate, manifest header, report reference, and resume-lineage validation.

**Revision note (round 9):** revised per owner review round 9; implementation remains gated pending a fresh approval round. CR-R9-001: `apply_write_context` no longer accepts a separate `DocmendConfig`; it validates `DocmendConfig` from the factory-read plan's own config snapshot, so the reviewed artifact alone determines transforms, filters, collision policy, guard excludes, gate inputs, and execution. Replacing the plan between a CLI preview read and factory entry cannot carry the earlier config into the write ceremony. CR-R9-002: the CLI's initial plan load now uses `read_plan_snapshot`; preview's model, config, `ArtifactRef`, predecessor validation, and report all derive from that one byte snapshot, with no model/hash reopen seam.

**Revision note (round 10):** revised per owner review round 10; implementation remains gated pending a fresh approval round. CR-R10-001: production factories no longer accept `lock_state_dir`; all supported callers contend in the canonical XDG lock namespace keyed by resolved corpus root, while tests isolate by setting `XDG_STATE_HOME`. CR-R10-002: factories derive the sole ADR-0021 carve-out internally as the invoking directory's canonical `.docmend/`; callers cannot broaden it with `artifact_root`. CR-R10-003: the apply factory accepts only explicit preservation overrides and derives the effective `ApplyOptions`—including the plan-config backup default—from its authoritative config snapshot; the capability carries those options and `execute_plan` accepts no caller options. CR-R10-004: the factory repeats supported-minor, non-null/existing-directory root, and embedded-config applicability checks against its own snapshot. CR-R10-005: the CLI maps factory `ArtifactError` to exit 2 and `ManifestContainmentError` to exit 3, preserving the public taxonomy.

**Owner approval (round 12, 2026-07-11):** APPROVED by independent contract and execution audits; no implementation blocker remains. Round 11's sole finding was a stale `execute_plan(options=...)` sketch parameter after CR-R10-003 moved effective options into the capability; round 12 verified the interface, sketch, capability tuple, CLI, helper, and migrated call sites agree. Implementation may proceed from Task 1; Task 8's separate CR-006 wire-model checkpoint was already owner-approved.

**Architecture:** One new module `src/docmend/writer/commit.py` owns the commit boundary (adr-0020): `bind_file` reads an object's bytes exactly once through an `O_RDONLY | O_NOFOLLOW | O_NONBLOCK` descriptor and captures its identity; `check_bound` is the at-commit half — `lstat` (never following symlinks), exact `(st_dev, st_ino)` compare, and a full-path containment re-resolve — called immediately before each pathname mutation step; `check_destination` is its absent-name counterpart; `guarded_replace` is the stage-first replacement primitive. The same module owns `WriteSafetyContext`, the sealed capability (adr-0004 amendment) whose only factories acquire the run lock, evaluate the apply gate / perform the restore chain preflight, run the artifact destination guard, bind an immutable attestation of exactly what they authorized — immutable serialized snapshots of the gated plan/config and the deep-frozen validated chain — and stay held through manifest close and report publication. The apply authority root is derived from the private plan snapshot, never accepted as an independent caller claim; the mutation engine reconstructs fresh private models from the serialized payload only after attestation. `writer/apply.py`, `restore.py`, and `writer/adjudicate.py` consume both halves; `cli.py` rewires to the split entrypoints. Plan B already persists the identities in intent records — this plan hardens their _capture_ (descriptor-bound, was `os.stat` by design) and adds the _at-commit re-checks_.

**Tech Stack:** Python 3.14 (PEP 758 in the codebase), pydantic v2 strict models, typer CLI, pytest + coverage, `os.open`/`os.fstat`/`os.lstat` POSIX identity primitives.

**Design sources (binding):** `docs/adr/adr-0020-commit-boundary-object-identity.md`; `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md` §"Commit Boundary (DMR-06/07)" and §"Read/write entrypoint split (F8)"; spec rev 0.26 FR-003/FR-005/FR-011/§13.5. Change control is already landed (spec rev 0.26/0.27, adr-0004 amended, adr-0020 accepted) — no _behavioral_ spec/ADR edits in this plan; §17.3 traceability maintenance (Appendix B obligation) is Task 12.

## Global Constraints

- Full local gate green at the end of EVERY task before its commit: `uv run python scripts/check.py` (Ruff format+lint, BasedPyright strict, pytest with branch coverage ≥ 97%, pip-audit).
- Never `git add .` / `git add -A` — stage files by explicit name.
- This repository is public: fixtures are synthetic only — never real library documents, paths, or personal content (conventions #6).
- Exit taxonomy is fixed (ADR-0012): safety refusal 3, artifact-input error 2, findings 1, clean 0. Commit-time interference is a per-action skip counting toward exit 1 (design §"Error Taxonomy").
- New skip reasons this plan introduces: `external-interference`, `collision-unpreserved`. No new exit codes. The report JSON schema's `skip_reason` is a free string + description (no enum), so no schema version bump — the reason vocabulary is documented in `report.py`.
- The `lstat`-to-`rename` interval is the ACCEPTED residual window (adr-0020 stated limitation) — do not attempt Linux-only `renameat2` hardening.
- Identity comparison is EXACT `(st_dev, st_ino)`; a device change refuses, never substitutes (docstring contract in `lineage.py`).
- Manifest 2.0 invariants from Plan B are untouched: intent-before-mutation for every kind, terminal repeats immutable fields, staging precedes intent so `expected_published_identity` is knowable pre-mutation. Standalone pre-mutation `failed` records are chain-legal (`8c2d5f4`).
- **Terminal-honesty rule (CR-004, binding for every task):** a `failed` terminal may be appended ONLY when the corpus is provably in its pre-action state (spec §10.4: Failed means the original is intact). When a mutation step has already landed and its rollback cannot be _proven_ (identity-checked at every rollback touch), the intent stays DANGLING and the action reports `failed` (ERR-002) — resume/restore adjudication owns the intermediate, exactly what the adr-0019 table exists for.
- **Last-copy rule (CR-004 round 2, binding):** no rollback or cleanup step may remove a name that holds the bound original when the original's OTHER name is not provably intact — a published hardlink can be the last surviving name of the validated object, and deleting it is data loss disguised as tidiness. When in doubt, keep the lossless intermediate and leave the intent dangling.
- **Replacement writes stage first (CR-003 round 2, binding):** never check-then-`atomic_write_bytes` on a corpus name — the function stages internally and publishes later, re-opening the window. Use `guarded_replace` (stage → check staged inode + target identity + containment → publish).

## File Structure

| File | Role in this plan |
| --- | --- |
| `src/docmend/writer/commit.py` (create) | Commit boundary: `InterferenceError` (with `intermediate` flag), `BoundFile`, `bind_file`, `check_bound`, `check_destination`, `guarded_replace`, `CommitHooks`, `guarded_rename_no_clobber`; F8: `WriteSafetyContext` (attested; carries immutable serialized gated plan/config payloads and the deep-frozen chain), `SafetyRefusedError` family, `apply_write_context`, `restore_write_context` |
| `src/docmend/writer/atomic.py` (modify) | `abort_staged` becomes identity-checked (CR-004) |
| `src/docmend/writer/apply.py` (modify) | Source/target binding, action-time overwrite invariant, per-step checks, boundary-checked rollback, hooks threading, structurally separate `preview_plan`/`execute_plan` cores (no dual-mode helper) |
| `src/docmend/writer/adjudicate.py` (modify) | `finish_remaining` mutations routed through the boundary — containment, hooks, `guarded_replace` (CR-NEW-001) |
| `src/docmend/writer/manifest.py` (modify) | Deep immutability: `frozen=True` on `ManifestHeader`/`ManifestRecord` + tuple containers at every construction site (CR-002); header gains `effective_excludes` (CR-006) |
| `src/docmend/schemas/manifest-header.schema.json` (modify) | Required `effective_excludes` array — pre-release 2.0 extension (CR-006) |
| `src/docmend/restore.py` (modify) | Live-target binding, per-step inverse checks with survivor verification, dangling-intent policy for intermediates, structurally separate `preview_restore`/`run_restore` cores (no dual-mode helper) |
| `src/docmend/report.py` (modify) | `ApplySkipReason` gains the two new reasons |
| `src/docmend/writer/gate.py` (modify) | `_strategy_active` → public `strategy_active`; `_overwrite_preservation` docstring demoted to "early feedback, no longer load-bearing" |
| `src/docmend/artifacts.py` (modify) | `write_report`/`write_json_artifact` gain a `clobber` passthrough (no-clobber refusal reports, CR-007) |
| `src/docmend/cli.py` (modify) | apply/restore rewired to preview/factory entrypoints; refusal callback; dry-run report publishes no-clobber (CR-NEW-005); restore loads no config — the carve-out authority is the recorded header (CR-006/CR-NEW-003) |
| `docs/specs/docmend.md` (modify, Task 12 only) | §17.3 traceability rows + Document History entry — status accuracy for Plans A/B/C, no behavioral text |
| `tests/unit/writer/test_commit.py` (create) | Primitive + factory + sealing + attestation unit tests, pairwise predicate matrix |
| `tests/unit/writer/test_adjudicate.py` (modify) | Boundary coverage for `finish_remaining` (containment, replace-window, mode) |
| `tests/helpers/writectx.py` (create) | `apply_safety`/`restore_safety` context helpers for the e2e test idiom |
| `tests/test_apply.py`, `tests/test_resume.py`, `tests/test_restore.py`, `tests/test_idempotency.py`, `tests/test_restore_drill.py`, `tests/test_scale.py`, `tests/test_cli_apply.py`, `tests/test_cli_resume.py` (modify) | Race regression tests; migration to the split entrypoints |
| `CHANGELOG.md` (modify) | Plan C section under [Unreleased] |

Interference windows and who tests them (design §Testing + review rounds 1-2): source replacement after validation (Task 4), same-bytes-different-inode replacement (Task 4), parent-symlink interposition (Task 4), destination-parent interposition on an absent target (Task 4), target appearing in the gate→collision-check window (Tasks 3+9, CR-001), target creation immediately before publish (Task 4), target replacement after backup (Task 4), published-target replacement before the source unlink (Tasks 4/5), source-name loss after link — last-copy retention (Tasks 1/4, CR-004), staged-temp replacement before publish and before abort (Tasks 1/4, CR-003/CR-004), replacement-write stage-window (Tasks 1/5/6/7, CR-003), rollback-unproven intermediates (Task 5), adjudication finish windows (Task 7, CR-NEW-001), restore inverse windows including reinstated-original survivor checks and the `restore-failed` retry (Task 6).

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
  - `type NameObservation = ObjectIdentity | Literal["absent", "symlink", "unobservable"]` and `def _observe_name(path: Path) -> NameObservation` — four-state lstat observation (CR-004 round 3: EACCES/EIO is "unobservable", never absence) shared by rollback logic (also imported by `apply.py` Task 5)
  - `def guarded_replace(target: Path, data: bytes, *, expected: ObjectIdentity, mode: int, root_resolved: Path, hooks: CommitHooks, survivor: tuple[Path, ObjectIdentity] | None = None, step: str = "replace-target") -> None` — stage-first replacement (CR-003 rounds 2-3); the survivor is verified INSIDE the primitive, immediately before publish; raises `InterferenceError`, `WriteError`
  - `@dataclass(frozen=True) class CommitHooks: before_step: Callable[[str, Path], None]` with `NO_HOOKS: Final[CommitHooks]` module constant
  - `def guarded_rename_no_clobber(source: Path, target: Path, source_identity: ObjectIdentity, *, root_resolved: Path, hooks: CommitHooks) -> None` — raises `FileExistsError` (collision race, caller's policy), `InterferenceError` (possibly `intermediate=True`), `WriteError`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/writer/test_commit.py`:

```python
"""Commit-boundary primitives (adr-0020): descriptor-bound identity capture
and the at-commit lstat re-check. All fixtures are synthetic (conventions #6)."""

import os
import threading
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
    check_destination,
    guarded_rename_no_clobber,
    guarded_replace,
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

    def test_fifo__interference_without_blocking(self, tmp_path: Path) -> None:
        """CR-005: O_RDONLY on a FIFO blocks until a writer appears; the
        O_NONBLOCK open must refuse it immediately. The thread guard makes a
        regression HANG a visible failure instead of a stuck suite."""
        fifo = tmp_path / "doc.txt"
        os.mkfifo(fifo)
        result: list[BaseException | None] = []

        def attempt() -> None:
            try:
                bind_file(fifo)
                result.append(None)
            except BaseException as exc:  # noqa: BLE001 — recorded for the main thread
                result.append(exc)

        worker = threading.Thread(target=attempt, daemon=True)
        worker.start()
        worker.join(timeout=2.0)
        assert not worker.is_alive(), "bind_file blocked on a FIFO (CR-005 regression)"
        assert isinstance(result[0], InterferenceError)
        assert "regular" in str(result[0])


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


class TestCheckDestination:
    def test_inside_root__passes(self, tmp_path: Path) -> None:
        check_destination(tmp_path / "sub" / "new.md", root_resolved=tmp_path.resolve())

    def test_parent_symlinked_outside__interference(self, tmp_path: Path) -> None:
        """CR-003: a publish that CREATES a name resolves its parent chain at
        the commit instant — a parent swapped for an outward symlink must not
        carry the new entry outside the root."""
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (root / "sub").symlink_to(outside)
        with pytest.raises(InterferenceError, match="resolves"):
            check_destination(root / "sub" / "new.md", root_resolved=root.resolve())


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

        with pytest.raises(InterferenceError) as exc_info:
            guarded_rename_no_clobber(
                source, target, identity, root_resolved=tmp_path.resolve(), hooks=CommitHooks(swap)
            )
        assert exc_info.value.intermediate is False
        assert not target.exists()

    def test_destination_parent_symlinked_outside_before_link__interference(
        self, tmp_path: Path
    ) -> None:
        """CR-003: the TARGET side of a rename is an absent-name publish and
        needs its own containment re-resolve."""
        root = tmp_path / "root"
        (root / "sub").mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        source = root / "a.txt"
        source.write_bytes(b"content")
        identity = bind_file(source).identity
        target = root / "sub" / "a.md"

        def interpose(step: str, path: Path) -> None:
            if step == "publish":
                (root / "sub").rmdir()
                (root / "sub").symlink_to(outside)

        with pytest.raises(InterferenceError):
            guarded_rename_no_clobber(
                source, target, identity, root_resolved=root.resolve(),
                hooks=CommitHooks(interpose),
            )
        assert source.read_bytes() == b"content"
        assert not (outside / "a.md").exists()  # nothing escaped the root

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

    def test_survivor_replaced_inside_stage_window__refused(self, tmp_path: Path) -> None:
        """CR-003 round 3: when replacing `target` makes `survivor` the last
        valid copy, the survivor must hold the expected object AT PUBLISH
        TIME — a pre-staging check can be invalidated during staging, after
        which the replace orphans the only remaining good inode."""
        target = tmp_path / "applied.md"
        target.write_bytes(b"applied")
        survivor = tmp_path / "original.txt"
        bound = bind_file(target)
        survivor.hardlink_to(target)  # the restore-shape: one inode, two names

        def swap(step: str, path: Path) -> None:
            if step == "replace-target":
                survivor.unlink()
                survivor.write_bytes(b"interloper")

        with pytest.raises(InterferenceError):
            guarded_replace(
                target, b"clobbered", expected=bound.identity, mode=bound.mode,
                root_resolved=tmp_path.resolve(), hooks=CommitHooks(swap),
                survivor=(survivor, bound.identity),
            )
        assert target.read_bytes() == b"applied"  # last good copy intact
        assert survivor.read_bytes() == b"interloper"  # theirs, untouched


class TestRollbackObservation:
    def test_unobservable_name__rollback_unproven(self, tmp_path: Path) -> None:
        """CR-004 round 3: an lstat ERROR (here EACCES via a no-x parent) is
        not absence — rollback must report unproven, never 'nothing ours
        remains'."""
        sub = tmp_path / "sub"
        sub.mkdir()
        source = sub / "a.txt"
        source.write_bytes(b"content")
        identity = bind_file(source).identity
        target = sub / "a.md"
        target.hardlink_to(source)
        sub.chmod(0o000)
        try:
            from docmend.writer.commit import _rollback_link

            assert not _rollback_link(
                target,
                identity,
                survivor=(source, identity),
                root_resolved=tmp_path.resolve(),
                hooks=NO_HOOKS,
            )
        finally:
            sub.chmod(0o755)

    def test_source_survivor_lost_before_rollback__published_link_retained(
        self, tmp_path: Path
    ) -> None:
        """CR-R5-003: a failed source unlink does not prove the source still
        survives until rollback. If it is removed in that window, deleting
        the published link would delete the bound original's last name."""
        source = tmp_path / "a.txt"
        source.write_bytes(b"content")
        identity = bind_file(source).identity
        target = tmp_path / "a.md"

        def lose_survivor(step: str, path: Path) -> None:
            if step == "rollback-survivor":
                source.unlink()

        target.hardlink_to(source)
        assert not _rollback_link(
            target,
            identity,
            survivor=(source, identity),
            root_resolved=tmp_path.resolve(),
            hooks=CommitHooks(lose_survivor),
        )
        assert target.exists()  # last valid name retained
```

And extend `TestAbortStagedIdentity` / add the `publish_staged` cleanup regression in `tests/unit/writer/test_atomic.py`:

```python
    def test_publish_failure_after_temp_race__interloper_survives(
        self, tmp_path: Path
    ) -> None:
        """CR-NEW-004: publish_staged's failure cleanup must not blind-unlink
        the staged NAME — after a race it holds someone else's object. Force
        the no-clobber publish to fail (target pre-created) with the temp
        already swapped."""
        target = tmp_path / "doc.md"
        staged = stage_bytes(target, b"payload")
        staged.tmp.unlink()
        staged.tmp.write_bytes(b"interloper")  # raced: same name, new inode
        target.write_bytes(b"occupied")  # forces FileExistsError on the link
        with pytest.raises(FileExistsError):
            publish_staged(staged, target, clobber=False)
        assert staged.tmp.read_bytes() == b"interloper"  # never deleted
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

Run: `uv run pytest tests/unit/writer/test_commit.py tests/unit/writer/test_atomic.py -q` Expected: FAIL — `ModuleNotFoundError: No module named 'docmend.writer.commit'` / `abort_staged` unlinks blindly. No hang (thread-guarded FIFO test).

- [ ] **Step 3: Write the implementation**

Create `src/docmend/writer/commit.py`:

```python
"""Commit boundary — descriptor-bound object identity (adr-0020, DMR-06/07).

Architectural role: every corpus mutation binds to ONE filesystem object,
never a pathname. `bind_file` reads an object's bytes exactly once through
an O_RDONLY|O_NOFOLLOW|O_NONBLOCK descriptor and captures its
(st_dev, st_ino); every pathname mutation step (each publish, each unlink)
calls `check_bound` immediately before mutating — lstat (never following
symlinks), EXACT identity compare, and a full-path containment re-resolve,
because O_NOFOLLOW guards only the final component and a parent directory
can be swapped for a symlink independently (adr-0020 decision drivers).
`check_destination` is the absent-name counterpart for publishes that
CREATE a directory entry, and `guarded_replace` is the stage-first
replacement primitive every corpus-name replacement goes through (review
CR-003: check-then-atomic_write_bytes re-opens the very window this module
exists to close).

Why not fstat-and-hold: fstat on an open descriptor describes the
ORIGINALLY OPENED inode even after the name is repointed — only a
pathname-vs-captured-identity comparison detects replacement. Why not
re-hash: DMR-06's confirmed defect is a DIFFERENT OBJECT carrying possibly
identical bytes; hash equality cannot close it. Why O_NONBLOCK: opening a
FIFO read-only blocks until a writer appears (review CR-005); the flag is
open-time-only semantics for special files and does not change regular-file
reads — fstat then refuses every non-regular object before any read.

InterferenceError.intermediate is the terminal-honesty channel (review
CR-004): False means the corpus is provably in its pre-action state (a
failed terminal is legal); True means a mutation step landed and its
rollback could not be proven — the caller must leave the intent DANGLING
for adjudication, never close it. The last-copy rule is its sibling: no
rollback removes a name holding the bound original unless the original's
other name is provably intact.

The lstat-to-rename interval is the accepted residual window (adr-0020
stated limitation). CommitHooks is the deterministic test seam for exactly
those windows — production passes NO_HOOKS.

This module also owns WriteSafetyContext (Task 8, F8/adr-0004 amendment):
the run-scoped half of the same boundary.
"""

import errno
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from docmend.lineage import ObjectIdentity
from docmend.writer.atomic import (
    WriteError,
    abort_staged,
    fsync_dir,
    link_no_clobber,
    publish_staged,
    stage_bytes,
)


class InterferenceError(Exception):
    """The object a pathname names is not the object the plan validated
    (DMR-06). Callers map this to the `external-interference` skip.
    `intermediate=True` means a mutation step already landed and the
    pre-action state could NOT be proven restored — the terminal-honesty
    rule (CR-004) then forbids closing the intent."""

    def __init__(self, message: str, *, intermediate: bool = False) -> None:
        super().__init__(message)
        self.intermediate = intermediate


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
    """Open `path` O_RDONLY|O_NOFOLLOW|O_NONBLOCK, capture identity via
    fstat, read all bytes through the descriptor. A symlink or non-regular
    file raises InterferenceError (the plan validated a regular file — the
    object changed class since); a missing/unreadable path raises OSError so
    the caller keeps today's `unreadable` (ERR-005) mapping."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
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


def check_destination(path: Path, *, root_resolved: Path) -> None:
    """Absent-name counterpart of `check_bound` (review CR-003): before a
    publish CREATES a directory entry, prove that entry lands inside the
    root — the parent chain is resolved at the commit instant, the leaf
    deliberately not followed (an occupied leaf is the no-clobber
    primitive's EEXIST to report, not this check's)."""
    if not (path.parent.resolve() / path.name).is_relative_to(root_resolved):
        msg = f"{path}: destination no longer resolves inside {root_resolved} (parent interposed)"
        raise InterferenceError(msg)


type NameObservation = ObjectIdentity | Literal["absent", "symlink", "unobservable"]


def _observe_name(path: Path) -> NameObservation:
    """lstat a name into a four-state observation (CR-004 round 3): an
    identity, "absent" (ENOENT/ENOTDIR — the name provably does not exist),
    "symlink" (not the regular-file object we bound), or "unobservable"
    (EACCES, EIO, ... — the name may WELL exist; treating an error as
    absence would let rollback overclaim a proven state)."""
    try:
        st = os.lstat(path)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            return "absent"
        return "unobservable"
    if stat.S_ISLNK(st.st_mode):
        return "symlink"
    return ObjectIdentity(dev=st.st_dev, ino=st.st_ino)


def _rollback_link(
    target: Path,
    expected: ObjectIdentity,
    *,
    survivor: tuple[Path, ObjectIdentity],
    root_resolved: Path,
    hooks: CommitHooks,
) -> bool:
    """Undo a just-created link ONLY while the name provably still holds our
    inode (CR-004: rollback itself must not bypass the boundary). Returns
    True when the pre-action state is proven. Ordering matters (CR-004
    round 3): containment is checked FIRST — under an interposed parent the
    lstat observes some OTHER location's object, so an identity mismatch
    there proves nothing about the real one; every conclusion below is
    conditional on the parent chain still being the one we linked into."""
    hooks.before_step("rollback", target)
    if not (target.parent.resolve() / target.name).is_relative_to(root_resolved):
        return False  # parent interposed: no observation through it is trustworthy
    observed = _observe_name(target)
    if observed == "unobservable":
        return False  # CR-004 rd 3: an error is not absence
    survivor_path, survivor_identity = survivor
    hooks.before_step("rollback-survivor", survivor_path)
    try:
        # CR-R6-003: authorize the target first, then make the survivor the
        # FINAL proof before deletion. If it disappeared while target state
        # was observed, retain the published link as the possible last name.
        check_bound(survivor_path, survivor_identity, root_resolved=root_resolved)
    except InterferenceError:
        return False
    if observed != expected:
        return True  # survivor intact and nothing of ours remains at target
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
        if _rollback_link(
            target,
            source_identity,
            survivor=(source, source_identity),
            root_resolved=root_resolved,
            hooks=hooks,
        ):
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
    survivor: tuple[Path, ObjectIdentity] | None = None,
    step: str = "replace-target",
) -> None:
    """Replace an EXISTING object's bytes without the stage-window race
    (CR-003 round 2): check-then-atomic_write_bytes lets an interloper
    arriving DURING the internal staging be clobbered. Order here: stage
    first, then — immediately before the publish — verify the staged inode,
    the target's identity, containment, AND the survivor (CR-003 round 3):
    when replacing this name makes another name the last valid copy (a
    restore's reinstated original), that name must still hold the expected
    object AT PUBLISH TIME, not merely before staging began — a survivor
    check that runs before this primitive stages can be invalidated during
    the staging it precedes. Every replacement write on a corpus name in
    docmend goes through this, including rollback and adjudication
    finishes."""
    staged = stage_bytes(target, data, mode=mode)
    hooks.before_step(step, target)
    try:
        check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)
        check_bound(target, expected, root_resolved=root_resolved)
        if survivor is not None:
            survivor_path, survivor_identity = survivor
            check_bound(survivor_path, survivor_identity, root_resolved=root_resolved)
    except InterferenceError:
        abort_staged(staged, root_resolved=root_resolved)  # identity+containment-checked
        raise
    publish_staged(staged, target)
```

Modify `src/docmend/writer/atomic.py` (add `import stat`):

```python
def _staged_name_is_ours(staged: StagedWrite) -> bool:
    """lstat the staged NAME against the staged identity — after a
    replacement race the name holds someone else's object (CR-004) and no
    cleanup may touch it. An lstat error is treated as not-ours: cleanup is
    best-effort residue removal, never worth destroying an unknown."""
    try:
        st = os.lstat(staged.tmp)
    except OSError:
        return False
    return not stat.S_ISLNK(st.st_mode) and (st.st_dev, st.st_ino) == (
        staged.identity.dev,
        staged.identity.ino,
    )


def abort_staged(staged: StagedWrite, *, root_resolved: Path | None = None) -> None:
    """Discard an unpublished staged write (idempotent) — identity-checked
    (plan C review CR-004): after a staged-temp replacement race the name
    holds someone else's object; a blind unlink would destroy it. When
    `root_resolved` is given (the commit-boundary callers), containment is
    re-resolved too (CR-004 round 3): an interposed parent makes even a
    matching identity untrustworthy to unlink through."""
    if root_resolved is not None and not (
        staged.tmp.parent.resolve() / staged.tmp.name
    ).is_relative_to(root_resolved):
        return
    if not _staged_name_is_ours(staged):
        return
    staged.tmp.unlink(missing_ok=True)
```

Also in `atomic.py` (review round 3, CR-NEW-004): `publish_staged`'s three internal cleanup paths — the `FileExistsError` arm, the `OSError` arm, and the post-link residue removal — currently call `tmp.unlink(missing_ok=True)` / `tmp.unlink()` blind. Each becomes:

```python
        if _staged_name_is_ours(staged):
            staged.tmp.unlink(missing_ok=True)
```

(with the post-link arm keeping its `contextlib.suppress(OSError)` wrapper and its existing lossless-residue comment). A staged-name replacement followed by a publication failure now leaves the interloper's file intact — the residue is ours to leak, never theirs to delete.

`stage_bytes` itself becomes descriptor-clean (review round 4, CR-NEW-004): it currently `tmp.chmod(...)` by PATHNAME after the descriptor closes and blind-unlinks the temp on failure — both blind pathname mutations inside the module that defines the discipline. Rework its body:

```python
    st = os.fstat(fd)  # OUR exclusively-created inode, identified before any write
    staged = StagedWrite(tmp=tmp, identity=ObjectIdentity(dev=st.st_dev, ino=st.st_ino))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            if mode is not None:
                # Descriptor-bound (CR-NEW-004 round 4): a pathname chmod
                # after close would follow a swapped name onto someone
                # else's object.
                os.fchmod(fh.fileno(), mode & 0o7777)
            os.fsync(fh.fileno())
    except OSError as exc:
        abort_staged(staged)  # identity-checked; a raced name is never deleted
        msg = f"{target}: cannot stage write ({exc.strerror or exc})"
        raise WriteError(msg) from exc
    return staged
```

(The `fd = -1` handoff bookkeeping of the current implementation goes away — `os.fdopen` owns the descriptor from construction, and `abort_staged` operates by name+identity. Add the regression: fail the staging write after a name swap via a monkeypatched `os.fsync`, assert the interloper's file survives; plus a mode test proving `fchmod` applied the mode before any failure window.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/writer/test_commit.py tests/unit/writer/test_atomic.py -q` Expected: PASS (all, within seconds — no FIFO hang)

- [ ] **Step 5: Full gate, then commit**

Run: `uv run python scripts/check.py`

```bash
git add src/docmend/writer/commit.py src/docmend/writer/atomic.py \
        tests/unit/writer/test_commit.py tests/unit/writer/test_atomic.py
git commit -m "feat(writer): commit-boundary primitives — descriptor identity, guarded replace/rename, checked abort (adr-0020)"
```

---

### Task 2: Apply binds the source through a descriptor

**Files:**

- Modify: `src/docmend/writer/apply.py` (the `_execute_action` read/validate head and the identity-capture block)
- Modify: `src/docmend/report.py:31-39` (`ApplySkipReason`)
- Test: `tests/test_apply.py`

**Interfaces:**

- Consumes: `bind_file`, `BoundFile`, `InterferenceError`, `NO_HOOKS` from Task 1.
- Produces: `_execute_action` holds a `bound: BoundFile` for the source; `data`/`mode`/`identities.source` all derive from it. `ApplySkipReason` includes `"external-interference"` and `"collision-unpreserved"`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_apply.py` (use the file's existing plan-building helpers — follow the idiom of the neighboring e2e tests; write `_planned_rewrite`/`_execute` thin wrappers once in this class if no exact fit exists):

```python
class TestCommitBoundarySourceBinding:
    def test_symlinked_source_at_apply__external_interference_skip(
        self, tmp_path: Path
    ) -> None:
        """DMR-06 class: between plan and apply the source name was repointed
        at another file via symlink. Today's pathname read follows it; the
        boundary must skip `external-interference` and mutate nothing. The
        referent stays INSIDE the corpus root so the earlier containment
        check passes and the bind is what refuses (review CR-008)."""
        root, plan, config, options, manifest_path = self._planned_rewrite(tmp_path)
        source = root / plan.actions[0].path
        payload = source.read_bytes()
        aside = root / "aside.txt"  # in-root referent (CR-008)
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

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_apply.py -k CommitBoundarySourceBinding -q` Expected: FAIL — no `external-interference` reason exists; symlinked source currently reads through the link.

- [ ] **Step 3: Extend `ApplySkipReason`**

In `src/docmend/report.py`:

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

(`collision-unpreserved` lands here too so the vocabulary changes once; its first emitter is Task 3.)

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

Every later `source_stat.st_mode` use becomes `bound.mode`. Import `bind_file`, `InterferenceError` from `docmend.writer.commit`.

- [ ] **Step 5: Run the new tests, then the full apply/resume suites**

Run: `uv run pytest tests/test_apply.py tests/test_resume.py -q` Expected: PASS — the identity VALUES are unchanged for the honest path (`bind_file` fstat == the old `source.stat()` for a regular file), so no Plan B assertion moves.

- [ ] **Step 6: Full gate, then commit**

```bash
git add src/docmend/writer/apply.py src/docmend/report.py tests/test_apply.py
git commit -m "feat(apply): bind the source to one O_NOFOLLOW descriptor (adr-0020, DMR-06)"
```

---

### Task 3: Action-time overwrite invariant + target descriptor binding

**Files:**

- Modify: `src/docmend/writer/apply.py` (the collision-policy block and the clobber block, current lines 395-462; `identities.target`)
- Modify: `src/docmend/writer/gate.py` (`_strategy_active` → public `strategy_active`; `_overwrite_preservation` docstring)
- Test: `tests/test_apply.py`

**Interfaces:**

- Consumes: `bind_file` from Task 1; `strategy_active` from gate.
- Produces: the clobber path is entered ONLY under an active preservation strategy (CR-001); `target_bound: BoundFile | None` in `_execute_action`; `overwritten_sha`/backup bytes/`identities.target` all derive from it. Task 4/5's pre-`os.replace` target checks compare against `target_bound.identity`.

- [ ] **Step 1: Write the failing tests**

```python
class TestActionTimeOverwriteInvariant:
    def test_target_appears_after_gate_no_strategy__collision_unpreserved(
        self, tmp_path: Path
    ) -> None:
        """CR-001 (DMR-07's first window): rename-only plan, overwrite
        policy, NO preservation strategy — the gate passes because no target
        exists at gate time. A target appearing before the per-action
        collision check must be skipped `collision-unpreserved`, never
        destroyed with only its hash recorded.

        ORDERING CONTRACT (review round 2, CR-001): at Task 9 this test
        migrates onto apply_write_context, whose gate would refuse a
        pre-existing strategyless overwrite target before the action-time
        check is ever reached. The migrated form MUST acquire the safety
        context while the target is ABSENT and create the target inside
        the context, immediately before execute_plan — deterministically
        exercising the gate->action window. At THIS task `_execute` calls
        the engine directly (no gate runs), so creating it up front is
        equivalent and correct."""
        root, plan, config, options, manifest_path = self._planned_rename_overwrite_policy(
            tmp_path, strategy=None  # rename-only plan passes the gate strategyless
        )
        target = root / plan.actions[0].target_path
        assert not target.exists()  # gate saw no clobbers
        target.write_bytes(b"late arrival")  # appears in the gate->action window
        report = self._execute(plan, config, options, manifest_path)
        outcome = report.outcomes[0]
        assert outcome.status == "skipped"
        assert outcome.skip_reason == "collision-unpreserved"
        assert target.read_bytes() == b"late arrival"  # untouched
        assert (root / plan.actions[0].path).exists()  # source untouched

    def test_target_appears_after_gate_with_strategy__clobbers_with_backup(
        self, tmp_path: Path
    ) -> None:
        """The invariant is about PRESERVATION, not surprise: with an active
        strategy the late target is backed up and legally overwritten —
        mirroring exactly what the gate licenses for gate-time targets."""
        root, plan, config, options, manifest_path = self._planned_rename_overwrite_policy(
            tmp_path, strategy="backup-dir"
        )
        target = root / plan.actions[0].target_path
        target.write_bytes(b"late arrival")
        report = self._execute(plan, config, options, manifest_path)
        assert report.outcomes[0].status == "applied"
        # the overwritten backup exists under the (action, overwritten) key
        # and hashes to the late arrival's bytes — assert via the manifest
        # record's overwritten_backup_path.

class TestCommitBoundaryTargetBinding:
    def test_symlinked_overwrite_target__external_interference_skip(
        self, tmp_path: Path
    ) -> None:
        """F3: under overwrite policy the pre-existing target's bytes are
        backed up through ITS descriptor. A symlink at the target name means
        the object the gate licensed clobbering is gone — skip, and back up
        nothing through the link. In-root referent (CR-008) so the earlier
        containment resolve passes and the BIND is what refuses."""
        root, plan, config, options, manifest_path = self._planned_rename_overwrite(tmp_path)
        target = root / plan.actions[0].target_path
        victim = root / "victim.txt"  # in-root referent (CR-008)
        victim.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(victim)
        report = self._execute(plan, config, options, manifest_path)
        assert report.outcomes[0].skip_reason == "external-interference"
        assert victim.exists()  # never clobbered THROUGH the link
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_apply.py -k "ActionTimeOverwrite or TargetBinding" -q` Expected: FAIL — the late-target case currently clobbers (recording only a hash); the symlink case follows the link.

- [ ] **Step 3: Publish `strategy_active` and enforce the invariant**

In `gate.py`, rename `_strategy_active` to `strategy_active` (update its two gate callers) and extend `_overwrite_preservation`'s docstring: "Action-time enforcement now lives in the commit boundary (adr-0020/adr-0004 amendment): `_execute_action` re-checks `strategy_active` when it discovers an existing target, and a target appearing after this gate without a strategy is skipped `collision-unpreserved`. This predicate remains early operator feedback, no longer the load-bearing invariant."

In `_execute_action`, the collision-policy block becomes:

```python
    clobber = False
    if target is not None and target.exists():
        policy = config.rename.on_collision
        if policy == "skip":
            return _skip(action, "collision"), False  # AW-002
        if policy == "fail":
            return _skip(action, "collision"), True  # non-zero abort (FR-011)
        # DMR-07 (review CR-001): overwrite preservation is an ACTION-TIME
        # invariant. The gate refused only targets that existed at gate
        # time; a target discovered HERE is clobbered only under an active
        # byte-preserving strategy — without one it is skipped, never
        # silently destroyed. Enforced on write runs only: a dry run carries
        # synthesized options (no strategy flags), so firing there would
        # contradict the write run the preview predicts.
        if options.write and not strategy_active(options):
            return _skip(action, "collision-unpreserved"), False
        clobber = True  # policy == "overwrite"
```

- [ ] **Step 4: Rebind the clobber block**

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

Downstream, the rollback branch's `target_bytes is not None` checks become `target_bound is not None`, and:

```python
    identities = _Identities(
        source=bound.identity,
        target=target_bound.identity if target_bound is not None else None,
        expected=staged.identity if staged is not None else bound.identity,
    )
```

Migrate the existing `test_overwrite_target_unreadable__failed_recorded_in_manifest` contract explicitly (CR-R5-005): its fixture is a **directory**, not an unreadable regular file. Under descriptor binding, a non-regular overwrite target is an object-class replacement and therefore `external-interference`, with no manifest (the refusal precedes intent). Rename it to `test_overwrite_target_nonregular__external_interference_no_manifest` and assert the directory and source remain untouched. Keep the separate backup/staging failure tests as the standalone pre-mutation `failed`-record coverage.

- [ ] **Step 5: Run tests, full gate, commit**

Run: `uv run pytest tests/test_apply.py tests/test_resume.py tests/test_gate.py -q` then the gate.

```bash
git add src/docmend/writer/apply.py src/docmend/writer/gate.py tests/test_apply.py
git commit -m "feat(apply): action-time overwrite invariant + descriptor-bound target (DMR-07, adr-0020 F3)"
```

---

### Task 4: Per-step commit checks — rewrite and rename paths

**Files:**

- Modify: `src/docmend/writer/apply.py` (mutation block for `rewrite`/`rename`; hooks threading through `execute_plan` → `_execute_action`; the `FileExistsError` handler; the new `InterferenceError` handler)
- Test: `tests/test_apply.py`

**Interfaces:**

- Consumes: `check_bound`, `check_destination`, `guarded_rename_no_clobber`, `CommitHooks`, `NO_HOOKS`, `InterferenceError`.
- Produces: `execute_plan(..., hooks: CommitHooks = NO_HOOKS)` threaded to `_execute_action(..., hooks)`; the race-lost skip reason is now `"collision-unpreserved"`; the `InterferenceError` handler implements the terminal-honesty rule — `intermediate=False` closes the intent with a failed ERR-002 terminal and skips `external-interference`; `intermediate=True` leaves the intent dangling and reports the action `failed`.

- [ ] **Step 1: Write the failing tests**

```python
class TestCommitBoundaryRaces:
    """adr-0020 confirmation windows, driven deterministically via CommitHooks."""

    def test_rewrite__source_swapped_same_bytes_after_intent__refused_nothing_mutated(
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
        # The intent was already journaled and nothing mutated — pre-action
        # state is proven, so a failed terminal closes it (terminal-honesty).
        records = read_records(manifest_path)
        assert [r["result"] for r in records] == ["intent", "failed"]

    def test_rewrite__staged_temp_swapped_before_publish__refused(
        self, tmp_path: Path
    ) -> None:
        """CR-003: the staged temp's inode is the intent's
        expected_published_identity — publishing a REPLACED temp would put
        unverified bytes into the corpus under our own journal entry. The
        raced temp itself must survive (identity-checked abort, CR-004)."""
        root, plan, config, options, manifest_path = self._planned_rewrite(tmp_path)
        source = root / plan.actions[0].path

        def swap(step: str, path: Path) -> None:
            if step == "publish":
                for tmp in source.parent.glob(f".{source.name}.*.docmend-tmp"):
                    content = tmp.read_bytes()
                    tmp.unlink()
                    tmp.write_bytes(content)  # same bytes, new inode

        report = self._execute(plan, config, options, manifest_path, hooks=CommitHooks(swap))
        assert report.outcomes[0].skip_reason == "external-interference"
        assert [r["result"] for r in read_records(manifest_path)] == ["intent", "failed"]
        # the interloper's file at the temp name survived the abort path
        assert len(list(source.parent.glob(f".{source.name}.*.docmend-tmp"))) == 1

    def test_rename__target_created_before_publish__collision_unpreserved(
        self, tmp_path: Path
    ) -> None:
        """DMR-07's second window: a target appearing after the per-action
        collision check — EEXIST from the no-clobber primitive maps to
        collision-unpreserved, distinct from plan-time `collision`."""
        root, plan, config, options, manifest_path = self._planned_rename(tmp_path)
        target = root / plan.actions[0].target_path

        def appear(step: str, path: Path) -> None:
            if step == "publish":
                target.write_bytes(b"late arrival")

        report = self._execute(plan, config, options, manifest_path, hooks=CommitHooks(appear))
        assert report.outcomes[0].skip_reason == "collision-unpreserved"
        assert target.read_bytes() == b"late arrival"

    def test_rename__published_target_replaced_before_unlink__source_retained(
        self, tmp_path: Path
    ) -> None:
        """CR-003 survivor window at the engine level: interference between
        link and unlink must retain the source (last copy we own) and close
        the intent failed — pre-action state proven (target no longer ours)."""
        root, plan, config, options, manifest_path = self._planned_rename(tmp_path)
        source = root / plan.actions[0].path
        target = root / plan.actions[0].target_path

        def swap(step: str, path: Path) -> None:
            if step == "unlink":
                target.unlink()
                target.write_bytes(b"interloper")

        report = self._execute(plan, config, options, manifest_path, hooks=CommitHooks(swap))
        assert report.outcomes[0].skip_reason == "external-interference"
        assert source.exists()
        assert target.read_bytes() == b"interloper"
        assert [r["result"] for r in read_records(manifest_path)] == ["intent", "failed"]

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
        # Nested corpus; hook swaps the file's parent for a symlink to a
        # directory OUTSIDE the root (leaf identity unchanged) — exactly the
        # O_NOFOLLOW blind spot check_bound's resolve closes. Assert
        # external-interference and the out-of-root tree untouched. Build
        # the fixture like Task 1's TestCheckDestination.
        ...
```

(`read_records` comes from `tests/helpers/manifest2.py`.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_apply.py -k CommitBoundaryRaces -q` Expected: FAIL — `_execute` has no `hooks` parameter yet.

- [ ] **Step 3: Thread hooks and add the checks**

`execute_plan` gains `hooks: CommitHooks = NO_HOOKS` (keyword-only) and passes it to `_execute_action`, which adds `hooks: CommitHooks` to its signature. The `rewrite`/`rename` arms become:

```python
    try:
        if kind == "rewrite":
            assert staged is not None
            hooks.before_step("publish", source)
            check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)  # CR-003
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
        # adr-0020 + terminal-honesty (CR-004): nothing of ours remains
        # mutated when intermediate is False — the intent closes with a
        # failed terminal (ERR-002) and the REPORT carries the reviewable
        # external-interference skip. intermediate=True means a rollback
        # could not be proven (or a last-copy retention): the intent stays
        # DANGLING (adjudication owns the recorded intermediate) and the
        # action reports failed.
        if staged is not None:
            abort_staged(staged, root_resolved=root_resolved)  # identity+containment-checked
        if exc.intermediate:
            log.error(
                "commit interference with unproven rollback; intent left for adjudication",
                path=action.path,
                detail=str(exc),
            )
            return _failed(action, "ERR-002", f"{exc} (resume adjudicates)"), False
        interference = _failed(action, "ERR-002", f"{exc} (adr-0020 commit boundary)")
        _record(
            manifest, action, kind, source, target, backup_path, None,
            overwritten_sha, overwritten_backup, run_id, interference, identities,
        )
        return _skip(action, "external-interference"), False
    except FileExistsError:
        ...  # existing handler; its failed-terminal message gains "DMR-07"
        # and its final line changes to:
        return _skip(action, "collision-unpreserved"), False
```

Add `abort_staged` to the `docmend.writer.atomic` import list if not present.

- [ ] **Step 4: Update the existing race-lost test**

`tests/test_apply.py` has an existing assertion that the no-clobber race skips `collision` (Plan B's FR-011 race test) — update it to `collision-unpreserved`. Search: `rg -n '"collision"' tests/test_apply.py tests/test_resume.py` and update only race-window assertions (plan-time and policy collisions stay `"collision"`).

Migrate that test's injection seam too (CR-R5-005): `test_no_clobber_race_lost__intent_closed_report_skips` currently monkeypatches `apply_module.rename_no_clobber`, which the guarded path no longer calls. Drive the same race through `CommitHooks(before_step=...)` by creating the target at `publish`, then assert `collision-unpreserved` plus the unchanged `intent, failed` manifest shape. Do not leave a stale monkeypatch against a dead symbol.

- [ ] **Step 5: Run tests, full gate, commit**

Run: `uv run pytest tests/test_apply.py tests/test_resume.py tests/test_cli_apply.py -q` then the gate.

```bash
git add src/docmend/writer/apply.py tests/test_apply.py tests/test_resume.py
git commit -m "feat(apply): at-commit identity checks for rewrite/rename — survivor, staged-temp, destination (DMR-06/07)"
```

---

### Task 5: Per-step commit checks — `rename_and_rewrite` windows and boundary-checked rollback

**Files:**

- Modify: `src/docmend/writer/apply.py` (the `rename_and_rewrite` arm; new `_undo_publish` helper replacing the inline CR-NEW-004 rollback)
- Test: `tests/test_apply.py`, `tests/test_resume.py`

**Interfaces:**

- Consumes: everything from Task 4 plus `guarded_replace`, `_observe_name` from `commit`.
- Produces: `_undo_publish(target, expected_identity, target_bound, *, survivor, root_resolved, hooks) -> bool` — boundary-checked publish rollback returning `True` only when the source survivor and pre-action state are proven (CR-004/CR-R5-003); the two-step kind checks staged temp + source + target before publish, and source + published-target survivor before the unlink.

- [ ] **Step 1: Write the failing tests**

```python
    def test_rename_and_rewrite__source_swapped_in_unlink_window__output_retained_dangling(
        self, tmp_path: Path
    ) -> None:
        """The target is already published when the source check refuses:
        the interloper destroyed the source name before rollback can prove a
        survivor. The staged output may now be the only useful copy, so it is
        RETAINED (CR-R5-003); the intent stays DANGLING and the action reports
        failed. A later resume adjudicates external interference without
        touching either name."""
        root, plan, config, options, manifest_path = self._planned_rename_rewrite(tmp_path)
        action = plan.actions[0]
        source = root / action.path
        target = root / action.target_path

        def swap(step: str, path: Path) -> None:
            if step == "unlink":
                source.unlink()
                source.write_bytes(b"interloper")

        report = self._execute(plan, config, options, manifest_path, hooks=CommitHooks(swap))
        outcome = report.outcomes[0]
        assert outcome.status == "failed"
        assert outcome.error is not None and outcome.error.error_class == "ERR-002"
        assert source.read_bytes() == b"interloper"
        assert target.exists()  # rollback refused: output may be the last useful copy
        assert [r["result"] for r in read_records(manifest_path)] == ["intent"]  # dangling

    def test_rename_and_rewrite__published_target_replaced_before_unlink__proven_failed(
        self, tmp_path: Path
    ) -> None:
        """CR-003 + CR-004 (semantics settled round 4): the published name
        was replaced by an interloper before the source unlink. Their object
        must not be touched and the source is retained. NO-CLOBBER shape:
        the source intact IS the pre-action state of our objects (our
        replaced output is re-derivable from it; the foreign file occupies a
        name we never owned pre-action) — consistent with the accepted
        pure-rename survivor-lost rule, the intent closes with a failed
        terminal and the report skips external-interference."""
        root, plan, config, options, manifest_path = self._planned_rename_rewrite(tmp_path)
        action = plan.actions[0]
        source = root / action.path
        target = root / action.target_path

        def swap(step: str, path: Path) -> None:
            if step == "unlink":
                target.unlink()
                target.write_bytes(b"interloper")

        report = self._execute(plan, config, options, manifest_path, hooks=CommitHooks(swap))
        assert report.outcomes[0].skip_reason == "external-interference"
        assert source.exists()  # retained — the original, intact
        assert target.read_bytes() == b"interloper"  # theirs, untouched
        assert [r["result"] for r in read_records(manifest_path)] == ["intent", "failed"]

    def test_rename_and_rewrite_clobber__published_target_replaced__dangling(
        self, tmp_path: Path
    ) -> None:
        """CLOBBER shape of the same window (CR-004 round 4): the OLD target
        we replaced cannot come back — its name is foreign now and its bytes
        live only in the backup — so pre-action is unprovable and the intent
        stays DANGLING; the action reports failed."""
        ...  # overwrite policy with strategy; hook at "unlink" swaps the
        # published target; assert outcome failed ERR-002, source retained,
        # interloper untouched, manifest == [intent] (dangling).

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
        # action (the run-1 intent stays the only record).

    def test_rename_and_rewrite__clobber_target_swapped_before_publish__refused(
        self, tmp_path: Path
    ) -> None:
        # overwrite policy with strategy; hook at "publish" swaps the target
        # inode → external-interference, both live files untouched, staged
        # temp aborted, intent closed failed.
        ...

    def test_rename_and_rewrite__target_appears_before_publish__collision_unpreserved(
        self, tmp_path: Path
    ) -> None:
        # skip policy planned no-clobber; hook at "publish" creates the
        # target → collision-unpreserved (FileExistsError path, DMR-07).
        ...

    def test_rename_and_rewrite__survivor_lost_after_unlink_failure__rollback_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CR-R6-003: force the source unlink to fail, then remove the source
        at `rollback-survivor`, after target authorization. `_undo_publish`
        must retain the published output and leave the intent dangling instead
        of deleting the last useful name or claiming a proven pre-action state."""
        ...
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_apply.py -k rename_and_rewrite -q` Expected: the new tests FAIL (no checks in that arm yet).

- [ ] **Step 3: Write `_undo_publish` and rewrite the arm**

```python
def _undo_publish(
    target: Path,
    expected_identity: ObjectIdentity,
    target_bound: BoundFile | None,
    *,
    survivor: tuple[Path, ObjectIdentity],
    root_resolved: Path,
    hooks: CommitHooks,
) -> bool:
    """Roll a rename_and_rewrite publish back WITHOUT bypassing the boundary
    (review CR-004): returns True when the pre-action state is proven. The
    clobbered-content reinstatement goes through guarded_replace — stage
    first, verify our published inode is still at the name immediately
    before replacing it (CR-003 round 2) — and comes back with the CLOBBERED
    object's mode (round 1 used the source's mode; wrong file). Byte/mode-
    exact, not inode-exact — os.replace cannot resurrect an inode; the
    recorded overwritten backup carries the recovery contract (FR-006)."""
    if target_bound is None:
        survivor_path, survivor_identity = survivor
        hooks.before_step("rollback", target)
        # Containment FIRST (CR-004 round 3): under an interposed parent the
        # observation below describes some OTHER location — an identity
        # mismatch there proves nothing about the real published name.
        if not (target.parent.resolve() / target.name).is_relative_to(root_resolved):
            return False
        observed = _observe_name(target)
        if observed == "unobservable":
            return False  # an lstat error is not absence (CR-004 rd 3)
        hooks.before_step("rollback-survivor", survivor_path)
        try:
            # CR-R6-003: target first, survivor last. The failed unlink did
            # not freeze the source name; losing it here makes the published
            # output a possible last useful copy that rollback must retain.
            check_bound(survivor_path, survivor_identity, root_resolved=root_resolved)
        except InterferenceError:
            return False
        if observed != expected_identity:
            return True  # survivor intact and nothing of ours remains at target
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
            hooks=hooks,
            survivor=survivor,
            step="rollback",
        )
    except (InterferenceError, WriteError):
        return False
    return True
```

The arm:

```python
        else:  # rename_and_rewrite
            assert target is not None
            assert staged is not None
            hooks.before_step("publish", target)
            check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)  # CR-003
            check_bound(source, bound.identity, root_resolved=root_resolved)
            if clobber:
                assert target_bound is not None
                check_bound(target, target_bound.identity, root_resolved=root_resolved)
            else:
                check_destination(target, root_resolved=root_resolved)  # CR-003
            publish_staged(staged, target, clobber=clobber)
            hooks.before_step("unlink", source)
            try:
                check_bound(source, bound.identity, root_resolved=root_resolved)
            except InterferenceError as source_exc:
                # CR-R5-003: the interloper destroyed the ORIGINAL's name.
                # `_undo_publish` therefore cannot prove its survivor and
                # retains the staged output as the last useful copy. The
                # pre-action state is unprovable; leave the intent DANGLING.
                rolled_back = _undo_publish(
                    target,
                    staged.identity,
                    target_bound,
                    survivor=(source, bound.identity),
                    root_resolved=root_resolved,
                    hooks=hooks,
                )
                state = "publish rolled back" if rolled_back else "published output retained"
                msg = f"{source_exc}; {state}, original's pre-action state unprovable"
                raise InterferenceError(msg, intermediate=True) from source_exc
            try:
                # Survivor check (CR-003): the published output must still be
                # OURS before the source name disappears.
                check_bound(target, staged.identity, root_resolved=root_resolved)
            except InterferenceError as survivor_exc:
                # Our output was replaced; the source is intact. No-clobber:
                # that IS the pre-action state of our objects — failed
                # terminal legal. Clobber: the OLD target we replaced cannot
                # come back (its name is foreign now; its bytes live in the
                # backup) — unprovable, dangling (CR-004 round 4).
                if clobber:
                    msg = f"{survivor_exc}; clobbered target unrecovered at a foreign name"
                    raise InterferenceError(msg, intermediate=True) from survivor_exc
                raise
            try:
                source.unlink()
            except OSError as unlink_exc:
                # codex CR-NEW-004, now boundary-checked (CR-004): recording
                # success or plain failure while the corpus changed would
                # lie. Proven rollback -> environmental WriteError (ERR-003,
                # original intact). Unproven -> dangling intent.
                if not _undo_publish(
                    target,
                    staged.identity,
                    target_bound,
                    survivor=(source, bound.identity),
                    root_resolved=root_resolved,
                    hooks=hooks,
                ):
                    msg = (
                        f"{source}: target published but source not removed "
                        f"({unlink_exc.strerror or unlink_exc}); publish rollback unproven"
                    )
                    raise InterferenceError(msg, intermediate=True) from unlink_exc
                msg = (
                    f"{source}: target published but source not removed; publish "
                    f"rolled back ({unlink_exc.strerror or unlink_exc})"
                )
                raise WriteError(msg) from unlink_exc
```

(The `except InterferenceError` handler from Task 4 already implements both terminal-honesty arms; the old inline rollback block and its `mode` local are deleted.)

- [ ] **Step 4: Run tests, full gate, commit**

```bash
git add src/docmend/writer/apply.py tests/test_apply.py tests/test_resume.py
git commit -m "feat(apply): rename_and_rewrite commit windows — guarded rollback, dangling-intent honesty"
```

---

### Task 6: Restore binds the live target and checks every inverse step

**Files:**

- Modify: `src/docmend/restore.py` (`run_restore` signature gains `hooks`; `_restore_one` preflight and mutation block; `_live_matches_after` deleted; explicit `restore-failed` handling)
- Test: `tests/test_restore.py`

**Interfaces:**

- Consumes: `bind_file`, `check_bound`, `check_destination`, `guarded_replace`, `guarded_rename_no_clobber`, `CommitHooks`, `NO_HOOKS`, `InterferenceError`.
- Produces: `run_restore(chain, *, run_id, write, only_ids, manifest_out, hooks: CommitHooks = NO_HOOKS)`; `_restore_one(record, *, write, run_id, manifest, root_resolved, hooks)`. (Task 10 later splits preview/write — signatures here stay additive.)

- [ ] **Step 1: Write the failing tests**

```python
class TestRestoreCommitBoundary:
    def test_applied_file_swapped_same_bytes_before_inverse__refused(
        self, tmp_path: Path
    ) -> None:
        """The restore preflight hashed the applied file; by commit time the
        name holds a DIFFERENT inode with the same bytes. Hashes pass;
        identity must refuse. Nothing mutated -> pre-action proven -> the
        inverse intent closes failed (terminal-honesty)."""
        ...  # apply a rewrite; hook at "publish" swaps the applied file's
        # inode (same bytes); run restore --write; assert outcome.status ==
        # "failed", "external-interference" in outcome.detail, corpus
        # untouched, restore manifest == [header, intent, failed].

    def test_symlinked_applied_file__failed_not_followed(self, tmp_path: Path) -> None:
        ...  # replace the applied file with an IN-ROOT symlink before
        # restore (CR-008 discipline); bind_file refuses; outcome failed
        # ERR-002; the referent untouched; no inverse intent written
        # (refusal precedes staging).

    def test_rename_inverse__reinstated_original_replaced_before_target_step__dangling(
        self, tmp_path: Path
    ) -> None:
        """CR-003 survivor + CR-004 honesty on the restore side: after the
        original is reinstated (link), an interloper replaces it before the
        target-side step. Their object must not be touched, the applied
        target must be retained (loss-proof: never delete the last copy),
        and the inverse intent stays DANGLING for the next run's
        adjudication."""
        ...  # rename apply; restore with hook at "replace-target" (clobber
        # shape) or "unlink" swapping the reinstated original; assert
        # outcome failed ERR-002, applied target still present, restore
        # manifest == [header, intent] (dangling).

    def test_restore_failed_terminal_then_retry__converges(self, tmp_path: Path) -> None:
        """CR-004 + CR-NEW-002: a pre-mutation restore failure (unwritable
        staging) appends the standalone failed inverse — chain-legal since
        8c2d5f4 — and proves nothing was mutated, so the reducer's
        `restore-failed` state falling through to a fresh `_restore_one` is
        correct and must converge, not trip the old collision skip. Fail
        staging (read-only original parent), fix the environment, re-run
        restore over both manifests, assert the action restores cleanly."""
        ...
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_restore.py -k RestoreCommitBoundary -q` Expected: FAIL — no `hooks` parameter; same-bytes swap currently restores.

- [ ] **Step 3: Rewire `_restore_one`**

`run_restore` computes `root_resolved = Path(chain.sets[0].header.source_root).resolve()` once and threads `root_resolved`/`hooks` into `_restore_one` and `_converge_pending_restore`. The preflight replaces `_live_matches_after` + `target.stat()` with one bind (closing the read-then-stat gap between them):

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

(Delete `_live_matches_after` and the old `target_stat` block.) In `run_restore`'s dispatch loop, add an explicit `restore-failed` branch comment where the state falls through to re-execution: "a failed inverse terminal proves nothing was mutated (terminal-honesty, CR-004) — retry is a fresh inverse, and the chain's failed→intent→applied transition is legal." The mutation block gains the per-step checks, a `mutated` flag for the honesty rule, and `guarded_replace` for every clobbered-content reinstatement (CR-003 round 2 — never check-then-`atomic_write_bytes`):

```python
    mutated = False
    try:
        if record.operation == "rewrite":
            assert staged is not None
            hooks.before_step("publish", original)  # original == target for rewrite
            check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)  # CR-003
            check_bound(target, live.identity, root_resolved=root_resolved)
            publish_staged(staged, original)
        elif record.operation == "rename":
            if clobbered is not None:
                hooks.before_step("publish", original)
                check_bound(target, live.identity, root_resolved=root_resolved)
                check_destination(original, root_resolved=root_resolved)  # CR-003
                link_no_clobber(target, original)
                mutated = True
                # Survivor binding (CR-003 round 3): the reinstated original
                # must still be ours AT PUBLISH TIME — guarded_replace checks
                # it inside the primitive, after staging, immediately before
                # the replace (a pre-staging check could be invalidated
                # during the staging it precedes).
                guarded_replace(
                    target, clobbered, expected=live.identity, mode=mode,
                    root_resolved=root_resolved, hooks=hooks,
                    survivor=(original, live.identity),
                )
            else:
                guarded_rename_no_clobber(
                    target, original, live.identity, root_resolved=root_resolved, hooks=hooks
                )
        else:  # rename_and_rewrite
            assert staged is not None
            hooks.before_step("publish", original)
            check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)  # CR-003
            check_destination(original, root_resolved=root_resolved)  # CR-003
            reinstated_identity = staged.identity
            publish_staged(staged, original, clobber=False)
            mutated = True
            hooks.before_step("unlink", target)
            if clobbered is not None:
                # Survivor binding at publish time (CR-003 round 3).
                guarded_replace(
                    target, clobbered, expected=live.identity, mode=mode,
                    root_resolved=root_resolved, hooks=hooks,
                    survivor=(original, reinstated_identity),
                )
            else:
                # Survivor check (CR-003): the reinstated original must exist
                # with the staged identity immediately before the applied
                # target goes away (no staging here — the unlink follows the
                # checks directly).
                check_bound(original, reinstated_identity, root_resolved=root_resolved)
                check_bound(target, live.identity, root_resolved=root_resolved)
                target.unlink()
    except InterferenceError as exc:
        if staged is not None:
            abort_staged(staged, root_resolved=root_resolved)  # CR-004 rd 4
        if mutated or exc.intermediate:
            # Terminal-honesty (CR-004): a step landed and the loss-proof
            # ordering guarantees a SUPERSET on disk — the intent stays
            # DANGLING; the next run's adjudication finishes or refuses from
            # disk state (adr-0019 "reinstatement landed" rows). No rollback
            # is attempted: restore never trades a superset for a race.
            return RestoreOutcome(
                record.action_id, record.docmend_id, record.original_path,
                "failed", f"ERR-002: {exc} (intermediate preserved; re-run adjudicates)",
            )
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
        if staged is not None:
            abort_staged(staged, root_resolved=root_resolved)  # CR-004 rd 4
        if mutated:
            # Same honesty rule for environmental failures after the first
            # landed step: superset on disk, intent dangling.
            return RestoreOutcome(
                record.action_id, record.docmend_id, record.original_path,
                "failed", f"ERR-003: {exc} (intermediate preserved; re-run adjudicates)",
            )
        ...  # existing failed-terminal arm unchanged (pre-mutation: proven)
```

(`guarded_rename_no_clobber` self-reports via `intermediate`; `publish_staged` consuming `staged` makes the later `abort_staged` a no-op by idempotence, and the identity check inside it protects a raced temp.)

Migrate the existing interrupted-restore convergence injection `test_rename_killed_mid_link_unlink__rerun_finishes` (CR-R5-005): it currently monkeypatches `restore_module.rename_no_clobber`, a dead seam after this task. Invoke restore with `CommitHooks` whose `unlink` callback raises the existing synthetic kill **after** the guarded primitive has linked the original name. Keep the both-names intermediate and convergent rerun assertions unchanged.

- [ ] **Step 4: Run tests, full gate, commit**

Run: `uv run pytest tests/test_restore.py tests/test_restore_drill.py -q` then the gate.

```bash
git add src/docmend/restore.py tests/test_restore.py
git commit -m "feat(restore): descriptor-bound inverse commits — survivor checks, guarded replace, dangling-intent honesty (adr-0020)"
```

---

### Task 7: Adjudication finishes go through the boundary (CR-NEW-001)

**Files:**

- Modify: `src/docmend/writer/adjudicate.py` (`finish_remaining`, `_verified_unlink`, `_rewrite_from_backup`)
- Modify: `src/docmend/writer/apply.py` (`_adjudicate_pending_intent` forwards `root_resolved` + hooks), `src/docmend/restore.py` (`_converge_pending_restore` likewise)
- Test: `tests/unit/writer/test_adjudicate.py`

**Interfaces:**

- Consumes: `guarded_replace`, `CommitHooks`, `NO_HOOKS`, `InterferenceError` from Task 1.
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
        # with root_resolved=root; expect WriteError and the out-of-root
        # file untouched.

    def test_finish_rewrite_from_backup__target_swapped_in_stage_window__refused(
        self, tmp_path: Path
    ) -> None:
        """The clobbered-bytes reinstatement is a replacement write and gets
        guarded_replace's stage-first ordering — a hook-injected swap during
        staging must refuse, never clobber."""
        ...  # finish-remaining inverse-rename state; hooks swap the applied
        # name at "replace-target"; expect WriteError, interloper intact.

    def test_finish_rewrite_from_backup__preserves_target_mode(self, tmp_path: Path) -> None:
        ...  # chmod the applied file 0o640 before finish; assert the
        # reinstated clobbered bytes carry 0o640 (guarded_replace mode
        # comes from the observed object, closing a silent 0o600 regression).

    def test_finish_rewrite_from_backup__mode_bound_to_verified_descriptor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CR-R5-006: identity, hash, and mode come from one descriptor; a
        pathname swap cannot lend an interloper's mode to the published
        backup bytes even if the expected inode later returns to the name."""
        ...

    def test_finish_unlink__survivor_swapped_since_adjudication__refused(
        self, tmp_path: Path
    ) -> None:
        """CR-NEW-001 round 3: the finish rows unlink a redundant name
        because the OTHER name holds the document — swap that survivor after
        adjudication (via the unlink hook) and the finish must refuse rather
        than remove the last valid copy."""
        ...  # finish-remaining apply state (both names, one inode); hook at
        # "unlink" replaces the published target with a same-bytes new
        # inode; expect WriteError, source name still present.

    def test_observe__identity_and_bytes_from_one_descriptor(self, tmp_path: Path) -> None:
        """CR-NEW-001 round 3: _observe must not lstat one object and read
        another. Deterministic seam: patch os.lstat? No — assert structurally
        instead: _observe of a regular file returns an observation whose
        sha matches bytes read through the SAME open (compare against a
        concurrent swap using a monkeypatched os.open counter is overkill;
        the structural assertion is that _observe performs exactly one
        os.open and no pathname read_bytes — enforce with a small spy on
        Path.read_bytes raising if called)."""
        ...

    @pytest.mark.parametrize("error", [PermissionError(13, "denied"), OSError(5, "I/O")])
    def test_observe_metadata_error__unobservable_never_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: OSError
    ) -> None:
        """CR-R5-004: EACCES/EIO cannot satisfy an `absent` crash-state row;
        adjudication must refuse instead of re-executing, adopting, or
        finishing from an unobservable name."""
        ...  # cover the absence-sensitive apply and inverse shapes; assert
        # state == "unobservable", absent is False, and the verdict is
        # external-interference.
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/writer/test_adjudicate.py -k Boundary -q` Expected: FAIL — `finish_remaining` has no `root_resolved`/`hooks` parameters.

- [ ] **Step 3: Route the mutations through the boundary**

````python
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


First, `_observe` itself becomes descriptor-bound (review round 3, CR-NEW-001): today it lstats and then `read_bytes()` by pathname, so the identity and the content can come from two DIFFERENT objects when a swap lands between the calls. Rewrite it on the `bind_file` pattern — one `O_RDONLY|O_NOFOLLOW|O_NONBLOCK` open, `fstat` for identity and mode, bytes read through the same descriptor. Do **not** retain the old nullable observation shape: it collapses EACCES/EIO into absence (CR-R5-004). Use an explicit four-state model:

```python
type ObservationState = Literal["regular", "absent", "symlink", "unobservable"]


@dataclass(frozen=True)
class _Observed:
    state: ObservationState
    identity: ObjectIdentity | None
    sha256: str | None
    mode: int | None

    @property
    def absent(self) -> bool:
        return self.state == "absent"
```

Only `ENOENT`/`ENOTDIR` produce `absent`; a symlink produces `symlink`; every
other open/fstat/read failure produces `unobservable`. `_is(...)` additionally
requires `state == "regular"`. Every crash-state row that tests `.absent`
therefore refuses an unobservable name. The `mode` comes from the same `fstat`
as identity and bytes and is consumed by the backup-rewrite path below.

```python
def _verified_unlink(
    path: Path,
    identity: ObjectIdentity | None,
    sha256: str,
    *,
    survivor: tuple[Path, ObjectIdentity | None, str] | None,
    root_resolved: Path,
    hooks: CommitHooks,
) -> None:
    """Destroy one name only after re-verifying (a) the object being
    destroyed, (b) containment at the act instant, and (c) the SURVIVOR that
    makes the destruction safe (review round 3, CR-NEW-001): the finish rows
    unlink a redundant name precisely because the other name holds the
    document — if that other name was swapped since adjudication, this
    unlink would remove the last valid copy."""
    hooks.before_step("unlink", path)
    observed = _observe(path)  # descriptor-bound: identity+bytes of ONE object
    if not _is(observed, identity, sha256):
        msg = f"{path}: object changed between adjudication and unlink; refusing"
        raise WriteError(msg)
    # Survivor AFTER the (potentially long) target read and immediately
    # before the destructive step, containment included (CR-NEW-001 rd 4).
    if survivor is not None:
        survivor_path, survivor_identity, survivor_sha = survivor
        if not _is(_observe(survivor_path), survivor_identity, survivor_sha):
            msg = (
                f"{survivor_path}: surviving name changed between adjudication "
                f"and finish; refusing to unlink {path}"
            )
            raise WriteError(msg)
        assert survivor_identity is not None  # finish rows always recorded it
        try:
            check_bound(survivor_path, survivor_identity, root_resolved=root_resolved)
        except InterferenceError as exc:
            raise WriteError(str(exc)) from exc
    # Re-authorize the PATHNAME at the deletion instant (CR-NEW-001 rd 4):
    # the descriptor observation above closed — the name can have been
    # repointed since. check_bound lstat-compares and re-resolves
    # containment; the lstat-to-unlink interval is the adr-0020 residual.
    assert identity is not None  # _is above proved the identity predicate rows
    try:
        check_bound(path, identity, root_resolved=root_resolved)
    except InterferenceError as exc:
        raise WriteError(str(exc)) from exc
    try:
        path.unlink()
    except OSError as exc:
        msg = f"{path}: cannot finish adjudicated unlink ({exc.strerror or exc})"
        raise WriteError(msg) from exc
````

`finish_remaining`'s dispatch supplies the survivor for each row: the apply rows unlink the SOURCE name, whose survivor is the published target — `(Path(record.target_path), record.expected_published_identity, record.after_sha256)`; the inverse rows unlink the APPLIED name, whose survivor is the reinstated original — `(Path(record.target_path), record.expected_published_identity, record.after_sha256)` on the inverse record (its `target_path` IS the original). The row that rewrites instead of unlinking passes the same survivor through `guarded_replace`:

```python
def _rewrite_from_backup(
    record: ManifestRecord,
    undone: ManifestRecord | None,
    *,
    root_resolved: Path,
    hooks: CommitHooks,
) -> None:
    ...  # backup read + hash verification unchanged; then:
    target = Path(record.original_path)
    observed = _observe(target)  # one descriptor: identity + hash + mode
    assert record.source_identity is not None  # adjudication verdict verified it
    assert record.expected_published_identity is not None
    if not _is(observed, record.source_identity, record.before_sha256):
        msg = f"{target}: object changed before backup rewrite; refusing"
        raise WriteError(msg)
    if observed.mode is None:
        msg = f"{target}: mode unavailable for verified backup rewrite"
        raise WriteError(msg)
    try:
        guarded_replace(
            target, data, expected=record.source_identity, mode=observed.mode,
            root_resolved=root_resolved, hooks=hooks,
            survivor=(Path(record.target_path), record.expected_published_identity),
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
- Modify: `src/docmend/artifacts.py` (`read_plan_snapshot` / `read_report_snapshot`: one byte snapshot supplies both validated model and sha256; canonical `ARTIFACT_DIR_NAME` shared by CLI and factories)
- Modify: `src/docmend/writer/manifest.py` — deep immutability (review round 3, CR-002): `ManifestHeader` and `ManifestRecord` gain `frozen=True` in their `ConfigDict` (safe: `ManifestWriter.append` already stamps via `model_copy`, and every terminal producer uses `model_copy(update=...)`); `ManifestSet.records` becomes `tuple[ManifestRecord, ...]` and `ManifestChain.sets` becomes `tuple[ManifestSet, ...]` at EVERY construction site — `read_manifest_set` (manifest.py:494), the empty chain (manifest.py:690), `_order_chain`'s result (manifest.py:703), `tests/helpers/manifest2.chain_of`, and `tests/test_restore.py:66`. `ManifestHeader` also gains `effective_excludes: tuple[str, ...]` (CR-006, below).
- Modify: `src/docmend/lineage.py` (`ObjectIdentity`/`PriorAttempt` gain `frozen=True`) and `src/docmend/report.py` (`ErrorInfo` gains `frozen=True`) — round 4, CR-002: immutability to the leaves
- Modify: `src/docmend/writer/apply.py` + `src/docmend/restore.py` (the two current `ManifestHeader(...)` constructions gain `effective_excludes` — producers in the SAME task, round 4 CR-NEW-008)
- Modify: `src/docmend/schemas/manifest-header.schema.json` — required array field `effective_excludes` (pre-release 2.0 extension: the clean-break format has never shipped, so no version bump)
- Modify: `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md` + `docs/adr/adr-0019-manifest-2-recovery-model.md` (change-control step below, behind the owner-approval checkpoint)
- Test: `tests/unit/writer/test_commit.py`, `tests/unit/writer/test_manifest.py`, `tests/test_plan_artifact.py`, `tests/test_report_artifact.py`, `tests/test_restore.py`

**Interfaces:**

- Consumes: `docmend.lock` (`acquire`, `LockHeldError`), `docmend.writer.gate` (`ApplyOptions`, `evaluate_gate`, `GateRefusal`), `docmend.artifacts.ArtifactError` / `guard_artifact_destination`, `docmend.writer.manifest` (`ManifestChain`, `read_manifest_chain`, `manifest_sha256`), `docmend.plan.Plan`, `DocmendConfig`, `pathspec`.
- Produces (Tasks 9-10 rely on these exactly):
  - `class SafetyRefusedError(Exception)` — base; `LockRefusedError(SafetyRefusedError)`, `DestinationRefusedError(SafetyRefusedError)`, `WriteRefusedError(SafetyRefusedError)` with attribute `refusals: list[GateRefusal]`
  - `@final class WriteSafetyContext` — sealed AND attested over the ACTUAL gated inputs (CR-002 rounds 2-4, CR-R5-001/002, CR-R7-001, CR-R8-001/002, CR-R10-003): methods `confirm_apply(*, run_id, manifest_path) -> None`, `confirm_restore(*, run_id, manifest_out) -> None`, `confirm_report(report_path: Path) -> None`; private `_consume_apply_state() -> tuple[Plan, DocmendConfig, ArtifactRef, ApplyOptions, ManifestChain, PriorAttempt | None]` reconstructs fresh engine-only plan/config models and returns the factory-derived plan reference/effective options, frozen resume chain, and predecessor edge; property `chain: ManifestChain` remains restore-only
  - `apply_write_context(plan_path, *, run_id, manifest_path, report_path, backup_root_override=None, preserved_by=None, allow_no_backup=False, resume_manifest_paths=(), prior_report_paths=(), input_artifacts=(), on_refusal=None) -> Iterator[WriteSafetyContext]` (contextmanager) — no caller Plan/config/effective options/hash/ref/root/in-memory chain/prior edge/manifest directory/lock namespace/artifact carve-out; the factory reads and applicability-checks the plan artifact (including its authoritative config snapshot), derives effective `ApplyOptions` from that config plus explicit operator overrides, derives the manifest directory from the attested manifest path, derives the canonical lock/artifact namespaces, and loads the complete predecessor graph itself; `on_refusal(refusals, plan_ref, prior_attempt)` receives both factory-derived lineage values
  - `restore_write_context(manifest_paths, *, run_id, manifest_out) -> Iterator[WriteSafetyContext]` (contextmanager) — performs the chain preflight ITSELF (CR-002), uses the canonical XDG lock namespace, and licenses only the internally derived invoking-directory `.docmend/` carve-out against the chain root header's RECORDED `effective_excludes` (CR-006/CR-R10-001/002; no caller-supplied exclude, lock namespace, or artifact root exists)

- [ ] **Step 1: Write the failing tests**

```python
class TestWriteSafetyContext:
    def test_direct_construction__typeerror(self) -> None:
        with pytest.raises(TypeError, match="factory-sealed"):
            WriteSafetyContext()

    def test_capability_deactivates_on_factory_exit(self, tmp_path: Path) -> None:
        with apply_write_context(...) as safety:  # minimal 1-action plan helper
            safety.confirm_apply(**self._matching_attestation_kwargs())
            leaked = safety
        with pytest.raises(RuntimeError, match="outside its factory scope"):
            leaked.confirm_apply(**self._matching_attestation_kwargs())

    def test_attestation_mismatch__each_field_refused(self, tmp_path: Path) -> None:
        """CR-002: a capability issued for run/destination A must not
        authorize B. Effective options are factory-derived, not presented."""
        with apply_write_context(...) as safety:
            good = self._matching_attestation_kwargs()
            for field, bad in [
                ("run_id", "run_20260711T000000Z_ffffff"),
                ("manifest_path", tmp_path / "elsewhere.jsonl"),
            ]:
                with pytest.raises(RuntimeError, match="attestation"):
                    safety.confirm_apply(**{**good, field: bad})

    def test_factory_snapshots_before_gate__caller_mutation_unreachable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CR-R5-002/R9-001: the artifact snapshot is the only plan/config
        authority; gate and execution consume immutable retained payloads."""
        real_gate = evaluate_gate

        def gate_spy(
            gated_plan: Plan,
            gated_config: DocmendConfig,
            *,
            source_root: Path,
            options: ApplyOptions,
            manifest_dir: Path,
        ) -> list[GateRefusal]:
            assert gated_plan is not plan
            assert gated_config == DocmendConfig.model_validate(gated_plan.config)
            plan.actions[0].target_path = "escape.md"  # mutate caller model
            return real_gate(
                gated_plan,
                gated_config,
                source_root=source_root,
                options=options,
                manifest_dir=manifest_dir,
            )

        monkeypatch.setattr(commit_module, "evaluate_gate", gate_spy)
        assert "config" not in inspect.signature(apply_write_context).parameters
        with apply_write_context(plan_path, ...) as safety:
            plan.actions[0].target_path = "escape.md"  # caller-side mutation
            engine_plan, engine_config, _, _, _, _ = safety._consume_apply_state()
            assert engine_plan.actions[0].target_path != "escape.md"
            assert engine_config == DocmendConfig.model_validate(engine_plan.config)

    def test_factory_uses_embedded_config__no_caller_substitution(
        self, tmp_path: Path
    ) -> None:
        """CR-R9-001: no independent config crosses the write boundary.
        Materialize a plan whose embedded collision policy differs from the
        caller's live config and prove gate/execution use the embedded value."""
        assert "config" not in inspect.signature(apply_write_context).parameters
        ...

    def test_factory_derives_effective_options_from_its_plan_snapshot(
        self, tmp_path: Path
    ) -> None:
        """CR-R10-003: an omitted --backup-dir uses the authoritative
        factory snapshot's config, not a value resolved from a prior CLI read."""
        parameters = inspect.signature(apply_write_context).parameters
        assert "options" not in parameters
        assert "backup_root_override" in parameters
        ...  # replace plan A with plan B before factory entry; prove the
        # retained ApplyOptions uses B.config.write.backup_dir. A non-None
        # override still wins per OQ-029 and is resolved once by the factory.

    def test_factory_owns_lock_and_artifact_namespaces(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CR-R10-001/002: supported callers cannot split coordination or
        broaden ADR-0021's carve-out. Tests isolate only via XDG_STATE_HOME."""
        parameters = inspect.signature(apply_write_context).parameters
        assert "lock_state_dir" not in parameters
        assert "artifact_root" not in parameters
        assert "lock_state_dir" not in inspect.signature(
            restore_write_context
        ).parameters
        assert "artifact_root" not in inspect.signature(
            restore_write_context
        ).parameters
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
        ...  # two contexts for one root contend; a broad excluded corpus
        # subtree outside invoking-cwd/.docmend remains destination-refused.

    @pytest.mark.parametrize("bad_plan", ["future_minor", "missing_root", "root_not_dir"])
    def test_factory_repeats_authoritative_plan_applicability_checks(
        self, tmp_path: Path, bad_plan: str
    ) -> None:
        """CR-R10-004: advisory CLI validation cannot license a replacement
        artifact with unsupported semantics or an unusable authority root."""
        ...  # direct factory call refuses before guard, lock, or gate

    def test_apply_payload_has_no_public_mutable_model(self, tmp_path: Path) -> None:
        """CR-R5-002: the round-4 public `safety.plan`/`safety.config`
        properties exposed the exact mutable objects the engine consumed."""
        with apply_write_context(plan_path, ...) as safety:
            with pytest.raises(AttributeError):
                _ = safety.plan
            with pytest.raises(AttributeError):
                _ = safety.config
            first_plan, first_config, _, _, _, _ = safety._consume_apply_state()
            first_plan.actions[0].target_path = "escape.md"
            first_config.rename.on_collision = "overwrite"
            second_plan, second_config, _, _, _, _ = safety._consume_apply_state()
            assert second_plan.actions[0].target_path != "escape.md"
            assert second_config.rename.on_collision != "overwrite"

    def test_authority_root_comes_from_private_plan_snapshot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CR-R5-001: there is no caller-supplied root that can make the
        factory lock/guard corpus A while its retained plan mutates corpus B."""
        assert "source_root" not in inspect.signature(apply_write_context).parameters
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
        with apply_write_context(plan_b_path, ...):
            with pytest.raises(lock.LockHeldError):
                lock.acquire(root_b, run_id="probe", command="apply")
            lock.acquire(root_a, run_id="probe", command="apply").release()

    def test_relative_root_canonicalized_before_cwd_change(self, tmp_path: Path) -> None:
        """CR-R6-001: a schema-valid relative root resolves once during the
        ceremony; chdir before execution cannot redirect the retained plan."""
        ...  # enter from cwd A with source_root="corpus", assert the retained
        # engine plan carries str((cwd_a / "corpus").resolve()), chdir to B,
        # execute, and prove only A/corpus changed and A's lock was held.

    def test_symlink_root_canonicalized_before_repoint(self, tmp_path: Path) -> None:
        """CR-R6-001: repointing an absolute symlink root after the ceremony
        cannot redirect execution away from the canonical corpus."""
        ...  # enter while link -> corpus A, repoint link -> corpus B, execute;
        # retained payload names A's resolved path and only A mutates.

    def test_resume_chain_loaded_and_bound_by_factory(self, tmp_path: Path) -> None:
        """CR-R7-001: mutation mode accepts manifest paths, not a caller-built
        chain. The retained chain is factory-validated, deep-frozen, and must
        match the canonical plan root and plan artifact hash."""
        with apply_write_context(
            plan_path,
            ...,
            resume_manifest_paths=[m1],
            prior_report_paths=[r1],
        ) as safety:
            _, _, derived_ref, _, chain, retained_edge = safety._consume_apply_state()
            assert chain.sets[0].path == m1
            assert retained_edge == expected_edge_from_validated_tip
            assert derived_ref.path == str(plan_path.resolve())
        # report-only, manifest-only, composed no-gap lineages derive their
        # edge; forged/missing evidence, wrong root, and wrong plan refuse.

    def test_restore_capability_has_no_plan(self, tmp_path: Path) -> None:
        with restore_write_context([m1], ...) as safety:
            with pytest.raises(RuntimeError, match="attestation|command"):
                safety._consume_apply_state()

    def test_confirm_report__bound_to_guarded_destination(self, tmp_path: Path) -> None:
        with apply_write_context(..., report_path=tmp_path / "r.json") as safety:
            safety.confirm_report(tmp_path / "r.json")
            with pytest.raises(RuntimeError, match="attestation"):
                safety.confirm_report(tmp_path / "elsewhere.json")

    def test_apply_context_cannot_authorize_restore(self, tmp_path: Path) -> None:
        with apply_write_context(...) as safety:
            with pytest.raises(RuntimeError, match="attestation|command"):
                safety.confirm_restore(run_id=..., manifest_out=...)
            with pytest.raises(RuntimeError, match="restore"):
                _ = safety.chain

    def test_factory_holds_the_run_lock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
        with apply_write_context(...):
            with pytest.raises(lock.LockHeldError):
                lock.acquire(source_root, run_id="run_x", command="apply")
        lock.acquire(source_root, run_id="run_x", command="apply").release()

    def test_gate_refusal__on_refusal_runs_in_lock_then_writerefused(
        self, tmp_path: Path
    ) -> None:
        """CR-007: the refusal callback fires WHILE the lock is held — the
        refusal artifact publishes under the same coordination boundary as
        the refusal decision (rev 0.26)."""
        seen: list[bool] = []

        def probe(
            refusals: list[GateRefusal],
            plan_ref: ArtifactRef,
            prior_attempt: PriorAttempt | None,
        ) -> None:
            with pytest.raises(lock.LockHeldError):
                lock.acquire(source_root, run_id="run_probe", command="apply")
            seen.append(bool(refusals))
            assert plan_ref.path == str(plan_path.resolve())
            assert prior_attempt == expected_edge

        with pytest.raises(WriteRefusedError) as exc_info:
            with apply_write_context(..., on_refusal=probe):
                raise AssertionError("must not yield")
        assert seen == [True]
        assert any(r.predicate == "preservation" for r in exc_info.value.refusals)

    def test_in_corpus_manifest_destination__destination_refused(self, tmp_path: Path) -> None:
        ...

    def test_lock_contention__lock_refused(self, tmp_path: Path) -> None:
        ...

    def test_restore_factory__validates_the_chain_itself(self, tmp_path: Path) -> None:
        """CR-002: the factory consumes manifest PATHS and runs
        read_manifest_chain — a caller-constructed ManifestChain cannot reach
        the capability. A tampered manifest refuses before any lock."""
        bad = tmp_path / "m.jsonl"
        bad.write_text("not a manifest\n")
        with pytest.raises(ArtifactError):
            with restore_write_context([bad], run_id=..., manifest_out=...):
                raise AssertionError("must not yield")

    def test_restore_chain_is_immutable(self, tmp_path: Path) -> None:
        """CR-002 rounds 2-3: the validated chain cannot be mutated between
        preflight and run_restore — the containers are tuples AND the inner
        pydantic models are frozen (tuples alone left every header/record
        field assignable through safety.chain)."""
        with restore_write_context([m1], ...) as safety:
            with pytest.raises((TypeError, AttributeError)):
                safety.chain.sets[0].records.append(anything)  # type: ignore[union-attr]
            with pytest.raises(ValidationError):  # pydantic frozen-instance error
                safety.chain.sets[0].records[0].target_path = "/elsewhere"  # type: ignore[misc]
            with pytest.raises(ValidationError):
                safety.chain.sets[0].header.source_root = "/elsewhere"  # type: ignore[misc]
            # Round 4: frozen must reach the LEAVES — a frozen parent does
            # not freeze nested models (reproduced on dev).
            record = safety.chain.sets[0].records[0]
            assert record.source_identity is not None
            with pytest.raises(ValidationError):
                record.source_identity.dev = 99  # type: ignore[misc]
            with pytest.raises(ValidationError):
                safety.chain.sets[0].header.prior_attempt.run_id = "run_x"  # type: ignore[union-attr,misc]

    def test_restore_factory__locks_chain_root_guards_out_exposes_chain(
        self, tmp_path: Path
    ) -> None:
        ...  # valid single-set chain on disk (tests/helpers/manifest2):
        # assert lock keyed on header.source_root; in-corpus manifest_out
        # refused; safety.chain.sets[0].header.run_id matches; and
        # confirm_restore accepts matching / refuses mismatched run_id.
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/writer/test_commit.py -k WriteSafety -q` Expected: FAIL — names don't exist.

- [ ] **Step 3: Implement**

> **OWNER-APPROVAL CHECKPOINT (review round 4, CR-006): SATISFIED — the owner approved the `effective_excludes` wire-model addition on 2026-07-11** (additive required field in the unreleased manifest 2.0 header, licensed-against-recorded-excludes semantics, recorded via the design + adr-0019 amendment sentences in item 4). Task 8 may execute.

In `manifest.py`, `lineage.py`, and `report.py` (reviews rounds 3-4, CR-002 + CR-006):

1. Add `frozen=True` to `ManifestHeader.model_config` and `ManifestRecord.model_config` — AND to the nested leaf models they embed: `ObjectIdentity` and `PriorAttempt` in `lineage.py`, `ErrorInfo` in `report.py` (round 4: a frozen parent does not freeze its children — `record.source_identity.dev` remained assignable, reproduced live). All five are constructed fresh and never field-assigned anywhere in the tree (the writers stamp via `model_copy`), so this is purely read-side hardening; with every leaf field a primitive, the chain is now deep-frozen at every level.
2. Change `ManifestSet.records` to `tuple[ManifestRecord, ...]` and `ManifestChain.sets` to `tuple[ManifestSet, ...]`, wrapping with `tuple(...)` at ALL FIVE construction sites: `read_manifest_set` (line 494), the empty chain (line 690), `_order_chain`'s caller (line 703), `tests/helpers/manifest2.chain_of`, and `tests/test_restore.py:66`. Align `tests/helpers/manifest2.read_records`' return annotation with what it now returns (`tuple[ManifestRecord, ...]` — round 4, CR-NEW-008).
3. Add to `ManifestHeader` (CR-006 — consumed by Task 10's restore factory; produced IN THIS TASK, item 3a, so the task gates green atomically — round 4, CR-NEW-008):

```python
    # The apply run's EFFECTIVE exclude patterns (adr-0021/plan-C CR-006):
    # the .docmend/ carve-out license restore's artifact guard applies must
    # be judged against the excludes that governed THIS run — list flags
    # REPLACE the config set, so no later invocation can reconstruct them;
    # the header is the only durable witness. tuple + before-validator so
    # the frozen model holds no mutable list.
    effective_excludes: tuple[str, ...]

    @field_validator("effective_excludes", mode="before")
    @classmethod
    def _excludes_to_tuple(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value
```

and the matching required array field in `src/docmend/schemas/manifest-header.schema.json`. The manifest 2.0 format has never shipped (the clean break lands with v2.0.0), so this is a pre-release extension of 2.0, not a version bump — Plan B's manifest fixtures (`tests/helpers/manifest2.header_doc`) gain the field with the stock excludes as default.

Producers land in the SAME task (round 4, CR-NEW-008 — a required field with no producer cannot gate green): the current `execute_plan`'s `ManifestHeader(...)` construction gains `effective_excludes=tuple(config.paths.exclude)` (the engine already holds the config), and `restore.py`'s `run_restore` header construction copies the chain root's: `effective_excludes=root_header.effective_excludes` (a restore run performs no discovery of its own; the license context is the apply's). Task 9's engine split carries both along unchanged.

**Change-control step (owner-approved per the checkpoint above):** append one sentence to the design's manifest 2.0 wire-model section and one to adr-0019's "More Information" ("the header additionally records the run's effective exclude patterns — plan C review CR-006: restore's artifact-destination carve-out must be licensed against the excludes that governed the apply, which per-invocation replacement flags make unreconstructable later"), each with a dated revision-note line.

Add `artifacts.read_plan_snapshot(path) -> tuple[Plan, str]` and `read_report_snapshot(path) -> tuple[Report, str]`: read artifact bytes **once**, decode/JSON-parse/schema-validate/model-validate those bytes, and compute the `sha256:` digest from the same snapshot (CR-R8-001/002). Separate `read_*` followed by `sha256_of_file` is not sufficient: an artifact replacement between those calls would bind artifact A's model to artifact B's hash. Add one-read regressions (spy on `Path.read_bytes`) plus swap-at-second-read regressions proving there is no second read seam for either artifact type.

Move the non-UI lineage logic from `cli._load_resume_inputs` into a reusable `_load_apply_predecessors(manifest_paths, report_paths, *, source_root, plan_sha256) -> tuple[ManifestChain, PriorAttempt | None]` seam owned by `writer/commit.py` (CR-R8-001). Preserve the complete Plan B contract, not a manifest-only subset:

- read/validate/order every supplied manifest and read/schema-validate/hash every supplied report;
- bind every report `plan_ref.sha256` and every manifest header `plan_sha256`/`source_root` to the factory-read plan artifact;
- prove manifest/report agreement for attempts carrying both, distinguish a genuine report-only attempt (`manifest_sha256: null`, zero applied) from missing mutation evidence, and reject duplicate reports;
- build the no-gap attempt graph from recorded `prior_attempt` edges, require every hash+run target to resolve, require one unambiguous tip, and derive the new run's `PriorAttempt` from that tip (report hash preferred when the tip report exists, otherwise validated manifest hash);
- return an empty frozen chain and null edge only when **no** predecessor evidence was supplied. A report-only predecessor is a non-null edge with an empty mutation chain.

This seam raises `ArtifactError` / `ManifestContainmentError`; the CLI only maps them to Typer exits/messages. Both preview loading and the write factory call the same evidence validator, eliminating the prior split between a correct CLI graph and an under-validated engine ceremony.

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
    """The apply gate refused the run (FR-005). The factory's `on_refusal`
    callback has already run IN-LOCK (review CR-007) so refusal artifacts
    publish under the same coordination boundary as the decision; this
    exception then propagates with the lock released."""

    def __init__(self, refusals: list[GateRefusal]) -> None:
        super().__init__("; ".join(r.message for r in refusals))
        self.refusals = refusals


_FACTORY_TOKEN: Final[object] = object()


@dataclass(frozen=True)
class _Attestation:
    """What a capability actually authorized (review CR-002): the mutation
    entrypoints re-present their scalar inputs and any divergence refuses —
    a context acquired for run A cannot authorize run B and an apply
    capability cannot authorize a restore. Apply inputs are CARRIED as
    immutable serialized payloads (CR-R5-002): the factory copies BEFORE the
    gate, gates that private copy, then serializes it. The engine reconstructs
    fresh private models; no caller can mutate the retained representation."""

    command: str  # "apply" | "restore"
    source_root: Path  # resolved
    run_id: str
    plan_json: str | None  # immutable serialization of the GATED private copy
    config_json: str | None  # immutable serialization of the GATED private copy
    plan_ref: ArtifactRef | None  # factory-read/hash-derived plan artifact identity
    subject_sha256: str | None  # chain tip manifest sha (restore)
    options: ApplyOptions | None
    manifest_path: Path  # resolved; restore: manifest_out
    report_path: Path | None  # resolved (apply)
    chain: ManifestChain | None  # restore chain — deep-frozen, factory-validated
    resume_chain: ManifestChain | None  # apply resume chain — same guarantees
    prior_attempt: PriorAttempt | None  # apply edge attested with the chain inputs


@final
class WriteSafetyContext:
    """Sealed, attested write capability (F8, adr-0004 amendment): proof
    that the run lock is held, the gate/preflight passed, and the artifact
    destinations are guarded — FOR EXACTLY the inputs recorded in the
    attestation. Only the two factories construct it; the mutation
    entrypoints confirm their own inputs against it. Deactivates when its
    factory exits, so a reference held past the with-block confers
    nothing."""

    __slots__ = ("_active", "_attest")

    def __init__(
        self, *, _token: object | None = None, _attest: _Attestation | None = None
    ) -> None:
        # _attest defaults to None deliberately (review round 3, CR-NEW-006):
        # without a default, bare WriteSafetyContext() dies on Python
        # argument binding with a "missing keyword-only argument" TypeError
        # and the sealing message below is never reached — the sealing test
        # matches on "factory-sealed", so the seal itself must be what fires.
        if _token is not _FACTORY_TOKEN or _attest is None:
            msg = (
                "WriteSafetyContext is factory-sealed (F8): enter "
                "apply_write_context() or restore_write_context()"
            )
            raise TypeError(msg)
        self._active = True
        self._attest = _attest

    def _confirm_active(self, command: str) -> _Attestation:
        if not self._active:
            msg = "WriteSafetyContext used outside its factory scope (F8)"
            raise RuntimeError(msg)
        if self._attest.command != command:
            msg = (
                f"WriteSafetyContext attestation mismatch: issued for "
                f"{self._attest.command!r}, presented to {command!r} (F8/CR-002)"
            )
            raise RuntimeError(msg)
        return self._attest

    def confirm_apply(
        self,
        *,
        run_id: str,
        manifest_path: Path,
    ) -> None:
        """Confirm the scalar half of the apply attestation."""
        a = self._confirm_active("apply")
        presented = (run_id, manifest_path.resolve())
        issued = (a.run_id, a.manifest_path)
        if presented != issued:
            msg = (
                "WriteSafetyContext attestation mismatch: this capability was "
                "issued for a different run/destination (F8/CR-002)"
            )
            raise RuntimeError(msg)

    def _consume_apply_state(
        self,
    ) -> tuple[
        Plan,
        DocmendConfig,
        ArtifactRef,
        ApplyOptions,
        ManifestChain,
        PriorAttempt | None,
    ]:
        """Reconstruct fresh engine-private models from the immutable gated
        payloads (CR-R5-002). This is deliberately not a public property:
        returning the retained mutable model let callers alter what executed
        after the gate. Repeated calls reconstruct independent objects, so a
        caller probing this private seam cannot mutate retained authority."""
        attest = self._confirm_active("apply")
        assert attest.plan_json is not None
        assert attest.config_json is not None
        assert attest.plan_ref is not None
        assert attest.options is not None
        assert attest.resume_chain is not None
        return (
            Plan.model_validate_json(attest.plan_json),
            DocmendConfig.model_validate_json(attest.config_json),
            attest.plan_ref,
            attest.options,
            attest.resume_chain,
            attest.prior_attempt,
        )

    def confirm_restore(self, *, run_id: str, manifest_out: Path) -> None:
        a = self._confirm_active("restore")
        if (run_id, manifest_out.resolve()) != (a.run_id, a.manifest_path):
            msg = (
                "WriteSafetyContext attestation mismatch: this capability was "
                "issued for a different restore run/destination (F8/CR-002)"
            )
            raise RuntimeError(msg)

    def confirm_report(self, report_path: Path) -> None:
        """The report destination the factory GUARDED is the one that gets
        written (CR-002 round 2) — the CLI confirms before write_report."""
        a = self._confirm_active("apply")
        if a.report_path is None or report_path.resolve() != a.report_path:
            msg = (
                "WriteSafetyContext attestation mismatch: report destination "
                "differs from the guarded one (F8/CR-002)"
            )
            raise RuntimeError(msg)

    @property
    def chain(self) -> ManifestChain:
        """The factory-validated chain (restore contexts only): the engine
        mutates from the SAME immutable object the preflight proved (CR-002)."""
        attest = self._confirm_active("restore")
        assert attest.chain is not None  # restore attestations always carry it
        return attest.chain


def _guard_or_refuse(
    destination: Path,
    *,
    corpus_root: Path,
    input_artifacts: Sequence[Path],
    exclude: PathSpec[GitIgnoreSpecPattern],
) -> None:
    refusal = guard_artifact_destination(
        destination,
        corpus_root=corpus_root,
        input_artifacts=input_artifacts,
        # CR-R10-002: ADR-0021 licenses exactly the invoking directory's
        # canonical .docmend/ root; callers cannot redefine the carve-out.
        artifact_root=(Path.cwd() / ARTIFACT_DIR_NAME).resolve(),
        exclude=exclude,
    )
    if refusal is not None:
        raise DestinationRefusedError(refusal)


@contextlib.contextmanager
def apply_write_context(
    plan_path: Path,
    *,
    run_id: str,
    manifest_path: Path,
    report_path: Path,
    backup_root_override: Path | None = None,
    preserved_by: str | None = None,
    allow_no_backup: bool = False,
    resume_manifest_paths: Sequence[Path] = (),
    prior_report_paths: Sequence[Path] = (),
    input_artifacts: Sequence[Path] = (),
    on_refusal: Callable[
        [list[GateRefusal], ArtifactRef, PriorAttempt | None], None
    ] | None = None,
) -> Iterator[WriteSafetyContext]:
    """The ONLY way to a write-capable apply (F8): guard the run's report
    and manifest destinations, acquire the run lock, evaluate the gate —
    then stay held through manifest close and report publication (the
    caller finalizes both inside this context; rev 0.26). On gate refusal,
    `on_refusal` runs IN-LOCK (CR-007) before WriteRefusedError raises.
    The factory reads and hashes the plan artifact itself (CR-R8-002), derives
    the full predecessor edge from validated manifest/report paths
    (CR-R8-001), canonicalizes the authority root, gates private inputs, then
    retains immutable serializations. No caller-held model/ref/edge reaches
    execution."""
    plan_artifact = plan_path.resolve()
    gated_plan, plan_sha256 = read_plan_snapshot(plan_artifact)
    if int(gated_plan.schema_version.split(".")[1]) > int(
        PLAN_SCHEMA_VERSION.split(".")[1]
    ):
        raise ArtifactError(
            f"{plan_artifact}: unsupported plan schema {gated_plan.schema_version}; "
            f"maximum is {PLAN_SCHEMA_VERSION} (ERR-006)"
        )
    # CR-R9-001: the reviewed plan snapshot is the config authority. A
    # separate caller model could gate/execute policy B against plan A.
    try:
        gated_config = DocmendConfig.model_validate(gated_plan.config)
    except ValidationError as exc:
        raise ArtifactError(
            f"{plan_artifact}: embedded config snapshot invalid (ERR-006): {exc}"
        ) from exc
    plan_ref = ArtifactRef(
        path=str(plan_artifact),
        run_id=gated_plan.run_id,
        sha256=plan_sha256,
    )
    if gated_plan.source_root is None:
        raise ArtifactError(f"{plan_artifact}: plan has no source_root (ERR-006)")
    source_root = Path(gated_plan.source_root).resolve()
    if not source_root.is_dir():
        raise ArtifactError(f"{source_root}: plan source root is not a directory")
    # CR-R6-001: one canonical authority value drives every later layer.
    # Persist it into the private snapshot BEFORE gate/serialization so cwd
    # changes or symlink repoints cannot make the engine re-derive a new root.
    gated_plan = gated_plan.model_copy(update={"source_root": str(source_root)}, deep=True)
    backup_root = (
        backup_root_override
        if backup_root_override is not None
        else gated_config.write.backup_dir
    )
    options = ApplyOptions(
        write=True,
        backup_root=backup_root.resolve() if backup_root is not None else None,
        preserved_by=preserved_by,
        allow_no_backup=allow_no_backup,
    )
    resume_chain, prior_attempt = _load_apply_predecessors(
        resume_manifest_paths,
        prior_report_paths,
        source_root=source_root,
        plan_sha256=plan_ref.sha256,
    )
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, gated_config.paths.exclude)
    for destination in (report_path, manifest_path):
        _guard_or_refuse(
            destination,
            corpus_root=source_root,
            input_artifacts=(
                *input_artifacts,
                plan_artifact,
                *resume_manifest_paths,
                *prior_report_paths,
            ),
            exclude=exclude,
        )
    try:
        run_lock = lock.acquire(source_root, run_id=run_id, command="apply")
    except (lock.LockHeldError, OSError) as exc:
        raise LockRefusedError(str(exc)) from exc
    try:
        refusals = evaluate_gate(
            gated_plan,
            gated_config,
            source_root=source_root,
            options=options,
            manifest_dir=manifest_path.resolve().parent,
        )
        if refusals:
            if on_refusal is not None:
                on_refusal(refusals, plan_ref, prior_attempt)
            raise WriteRefusedError(refusals)
        ctx = WriteSafetyContext(
            _token=_FACTORY_TOKEN,
            _attest=_Attestation(
                command="apply",
                source_root=source_root.resolve(),
                run_id=run_id,
                # Immutable retained authority (CR-R5-002): these are the
                # SAME private copies the gate evaluated, serialized only
                # after it passed. The engine reconstructs fresh models.
                plan_json=gated_plan.model_dump_json(),
                config_json=gated_config.model_dump_json(),
                plan_ref=plan_ref,
                subject_sha256=None,
                options=options,
                manifest_path=manifest_path.resolve(),
                report_path=report_path.resolve(),
                chain=None,
                resume_chain=resume_chain,
                prior_attempt=prior_attempt,
            ),
        )
        try:
            yield ctx
        finally:
            ctx._active = False  # noqa: SLF001 — factory owns the seal
    finally:
        run_lock.release()


@contextlib.contextmanager
def restore_write_context(
    manifest_paths: Sequence[Path],
    *,
    run_id: str,
    manifest_out: Path,
) -> Iterator[WriteSafetyContext]:
    """The ONLY way to a write-capable restore (F8): this factory performs
    the ManifestSet/chain preflight ITSELF (review CR-002) — it consumes
    manifest PATHS and runs read_manifest_chain, so the chain the engine
    mutates from (exposed as `safety.chain`, deep-frozen) is the one the
    preflight proved; a caller-constructed ManifestChain cannot reach the
    capability. ArtifactError / ManifestContainmentError propagate for the
    CLI's existing exit-2/exit-3 mapping. The lock keys on the validated
    chain's source_root (adr-0019). The `.docmend/` carve-out license is
    judged against the chain root header's RECORDED effective excludes
    (review CR-006 round 3): per-invocation replacement flags make the
    apply-time exclude set unreconstructable later — default-discovery
    loading could re-license a destination the operator's replaced set had
    withdrawn (adr-0021's wholesale-withdrawal clause), so the header is
    the only honest authority and there is deliberately no caller-supplied
    exclude parameter to disagree with it."""
    chain = read_manifest_chain(list(manifest_paths))
    if not chain.sets:
        raise ArtifactError("restore requires at least one manifest")
    root_header = chain.sets[0].header
    source_root = Path(root_header.source_root)
    _guard_or_refuse(
        manifest_out,
        corpus_root=source_root,
        input_artifacts=[s.path for s in chain.sets],
        exclude=PathSpec.from_lines(GitIgnoreSpecPattern, root_header.effective_excludes),
    )
    try:
        run_lock = lock.acquire(source_root, run_id=run_id, command="restore")
    except (lock.LockHeldError, OSError) as exc:
        raise LockRefusedError(str(exc)) from exc
    tip = chain.sets[-1]
    ctx = WriteSafetyContext(
        _token=_FACTORY_TOKEN,
        _attest=_Attestation(
            command="restore",
            source_root=source_root.resolve(),
            run_id=run_id,
            plan_json=None,
            config_json=None,
            plan_ref=None,
            subject_sha256=tip.sha256 or manifest_sha256(tip.path),
            options=None,
            manifest_path=manifest_out.resolve(),
            report_path=None,
            chain=chain,
            resume_chain=None,
            prior_attempt=None,
        ),
    )
    try:
        yield ctx
    finally:
        ctx._active = False  # noqa: SLF001
        run_lock.release()
```

Imports to add at the top of `commit.py`: `contextlib`; `Sequence`, `Iterator` from `collections.abc`; `final` from `typing`; `PathSpec` + `GitIgnoreSpecPattern` from pathspec; `ValidationError` from pydantic; `docmend.lock as lock`; `ARTIFACT_DIR_NAME`, `ArtifactError`, `guard_artifact_destination`, `read_plan_snapshot`, `read_report_snapshot` from `docmend.artifacts`; `DocmendConfig`; `PriorAttempt` alongside the existing `ObjectIdentity`; `ArtifactRef`, `PLAN_SCHEMA_VERSION`, `Plan`; `ApplyOptions`, `evaluate_gate`, `GateRefusal` from `docmend.writer.gate`; `ManifestChain`, `ManifestContainmentError`, `read_manifest_chain`, `manifest_sha256` from `docmend.writer.manifest`. Move the existing `ARTIFACT_DIR_NAME = ".docmend"` constant from `cli.py` to `artifacts.py` and import it back into the CLI, so every guard derives one canonical product-owned carve-out without an import cycle (CR-R10-002). (CR-R5-007: do not add the unused `hashlib` or `pydantic.BaseModel` imports; Ruff's per-task gate rejects them.)

- [ ] **Step 4: Run tests (including the full manifest/chain suites for the tuple change), full gate, commit**

Run: `uv run pytest tests/unit/writer/test_commit.py tests/unit/writer/test_manifest.py tests/test_manifest_chain.py tests/test_plan_artifact.py tests/test_report_artifact.py tests/test_restore.py -q` then the gate.

```bash
git add src/docmend/writer/commit.py src/docmend/writer/manifest.py \
        src/docmend/artifacts.py \
        src/docmend/lineage.py src/docmend/report.py \
        src/docmend/writer/apply.py src/docmend/restore.py \
        src/docmend/schemas/manifest-header.schema.json \
        docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md \
        docs/adr/adr-0019-manifest-2-recovery-model.md \
        tests/helpers/manifest2.py tests/test_restore.py \
        tests/test_plan_artifact.py tests/test_report_artifact.py \
        tests/unit/writer/test_commit.py tests/unit/writer/test_manifest.py
git commit -m "feat(writer): attested WriteSafetyContext — immutable gated payloads, deep-frozen chain, factory preflight (F8)"
```

---

### Task 9: Apply engine split (`preview_plan` / `execute_plan`) + CLI rewire + test migration

**Files:**

- Modify: `src/docmend/writer/apply.py` (split the dual-mode whole-run and per-action paths into structurally read-only preview functions and capability-required mutation functions)
- Modify: `src/docmend/cli.py` (the `apply` command's lock/gate/execute section, current lines 608-670)
- Modify: `src/docmend/artifacts.py` (`write_report`/`write_json_artifact` gain `clobber: bool = True`)
- Create: `tests/helpers/writectx.py`
- Modify/Test: `tests/test_apply.py`, `tests/test_resume.py`, `tests/test_idempotency.py`, `tests/test_scale.py`, `tests/test_cli_apply.py`, `tests/test_cli_resume.py`

**Interfaces:**

- Produces:
  - `preview_plan(plan, config, *, run_id, plan_ref, started_at, now=..., resume_chain=None, prior_attempt=None) -> Report` — structurally read-only; no `ApplyOptions`, manifest, gate, capability, hooks, or mutation helper.
  - `execute_plan(*, run_id, manifest_path, started_at, safety: WriteSafetyContext, now=..., hooks=NO_HOOKS) -> Report` — NO plan/ref/hash/config/options/resume parameters (CR-002/CR-R7-001/CR-R8-002/CR-R10-003): after scalar confirmation, the engine consumes the factory-derived plan reference plus plan/config/effective options/resume chain/prior edge only from `safety._consume_apply_state()`.
  - `_preview_action(...)` is structurally read-only: it can read/bind/hash/recompute and return `would_apply`/skip/failure evidence, but its signature has no manifest, backup, hooks, capability, or write flag.
  - `_ApplyRun` is a sealed, immutable orchestration state constructed only inside `execute_plan` from `_consume_apply_state()` plus the attested scalar arguments/manifest writer. `_execute_action(run, action_id)` and mutation adjudication accept no raw action/root/config/options/chain/manifest substitution points; they resolve all such values from `run`.
  - `tests/helpers/writectx.py: apply_safety(plan, *, options, manifest_path, report_path, run_id, state_dir, resume_manifest_paths=(), prior_report_paths=(), monkeypatch) -> ContextManager[WriteSafetyContext]` — test-only adapter materializes the synthetic Plan (including its authoritative config snapshot), points `XDG_STATE_HOME` at `state_dir`, and decomposes its fixture `ApplyOptions` into the production factory's explicit override scalars; no effective-options or lock-namespace object crosses the production boundary.

- [ ] **Step 1: Write the failing engine tests**

```python
class TestEntrypointSplit:
    def test_execute_plan_with_expired_capability__runtimeerror(self, tmp_path: Path) -> None:
        with apply_safety(...) as safety:
            pass
        with pytest.raises(RuntimeError, match="factory scope"):
            execute_plan(..., safety=safety)

    def test_execute_plan_runs_the_gated_copy__not_the_caller_object(
        self, tmp_path: Path
    ) -> None:
        """CR-002 round 4 at the engine seam: there is no plan parameter to
        mismatch — the engine consumes the capability's immutable payload. Mutate the caller-held
        plan after entering the ceremony (retarget an action at an in-root
        victim) and prove the run performed the ORIGINAL gated action, not
        the mutated one."""
        with apply_safety(plan, ...) as safety:
            victim = root / "victim.md"
            plan.actions[0].target_path = "victim.md"  # caller-side sabotage
            report = execute_plan(run_id=RUN, manifest_path=mp,
                                  started_at=TS, safety=safety)
        assert report.outcomes[0].status == "applied"
        assert not victim.exists()  # the mutation never reached execution
        assert (root / original_target).exists()  # the gated action ran

    def test_preview_plan__no_lock_no_manifest_no_mutation(self, tmp_path: Path) -> None:
        report = preview_plan(plan, config, run_id=..., plan_ref=..., started_at=...)
        assert report.dry_run is True
        assert report.totals.would_apply == len(plan.actions)
        # corpus untouched; no manifest anywhere under tmp_path; no lock file

    def test_internal_mutation_helpers_require_sealed_run_state(self, tmp_path: Path) -> None:
        """CR-R7-002: underscore naming is not the boundary. The helper takes
        only a sealed `_ApplyRun` plus an action ID; raw root/config/action/
        chain/manifest substitution is absent from its signature."""
        assert not hasattr(apply_module, "_run_plan")
        assert "write" not in inspect.signature(apply_module._execute_action).parameters
        assert tuple(inspect.signature(apply_module._execute_action).parameters) == (
            "run",
            "action_id",
        )
        with pytest.raises(TypeError, match="engine-sealed"):
            apply_module._ApplyRun(...)
        with pytest.raises(KeyError, match="not in gated plan"):
            apply_module._execute_action(live_run, forged_action_id)

    def test_execute_plan_rejects_caller_supplied_resume_state(self) -> None:
        """CR-R7-001: mutation resume evidence enters through factory paths;
        execute_plan has no resume_chain/prior edge parameters to forge."""
        parameters = inspect.signature(execute_plan).parameters
        assert "resume_chain" not in parameters
        assert "prior_manifest_sha256" not in parameters
        assert "prior_attempt" not in parameters
        assert "plan_ref" not in parameters
        assert "plan_sha256" not in parameters
        assert "options" not in parameters
```

- [ ] **Step 2: Split the engine**

In `apply.py`, do **not** preserve the current dual-mode body as `_run_plan` (CR-R6-002). An underscore function accepting `write=True` would still be a fully ungated mutation engine. Split at both levels:

1. `preview_plan` owns the read-only whole-run loop and calls `_preview_action`. It never constructs `ManifestWriter`, never takes backup or manifest destinations, and has no path to staging, publication, unlink, or `finish_remaining`.
2. `execute_plan` owns the mutation loop. After `confirm_apply`, reject `options.write=False`, consume the gated plan/config/factory-validated resume chain/prior edge, open the attested manifest, and construct a sealed `_ApplyRun`. It calls `_execute_action(run, action_id)`; there is no shared whole-run function with a `write` flag and no caller-provided resume state.
3. Extract the current read-only validation/recompute logic into helpers that have no mutation dependencies. Duplication between `_preview_action` and `_execute_action` is acceptable where sharing would reintroduce a dual-mode function; pure helpers for hashing, recompute, filtering, totals, and report assembly may remain shared.
4. Define `_ApplyRun` as `@dataclass(frozen=True)` with a module-private constructor token. It holds the active `safety`, gated plan/config, canonical root, options, run/report scalars, `ManifestWriter`, validated resume chain, derived prior-manifest hash, attested prior attempt, hooks, include/exclude specs, and an action-ID map frozen with `MappingProxyType`. Its constructor verifies `safety._confirm_active("apply")`; only `execute_plan` possesses the token. `_execute_action(run, action_id)` and mutation adjudication resolve every authority-bearing value from this state and reject an unknown action ID. Remove their raw action/root/config/options/manifest/chain parameters and all `if not options.write` branches. Preview adjudication classifies and reports only; it never finishes or appends a terminal.

Concrete extraction map (so this is not left as an implementation guess):

- `_preview_action` owns the current source bind/hash, filter, containment, recompute/shrink, and collision-policy checks through the existing dry-run `would_apply` return. Under overwrite it predicts the action without the write-only preservation-strategy check, matching today's preview contract.
- `_execute_action(run, action_id)` retains those read checks plus target binding, backups, staging, intent/terminal writes, and the commit boundary; delete its dry-run return entirely. It obtains the action/config/root/options/manifest/hooks only from `run`; `options.write` is asserted by `execute_plan` and is not a control branch below it.
- `_preview_pending_intent` keeps the current read-only verdict mapping: `never-happened -> None`, `external-interference -> failed`, and recognized completed/finish states -> `would_apply`; it cannot call `finish_remaining`. `_adjudicate_pending_intent(run, action_id)` becomes mutation-only and resolves the pending record from `run.resume_chain`; it accepts no caller-supplied record.
- `_reconcile_completed`, lifecycle reduction, outcome partitioning, totals, logging, and report construction remain pure shared helpers. The two public loops call them independently.

The public wrappers are therefore shaped as follows (the omitted bodies are the two **separate** loops described above, not calls to a common dual-mode engine):

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
    ceremony. This function has no manifest or mutation branch and needs no
    WriteSafetyContext."""
    ...  # read-only loop over _preview_action; no write/manifest branch exists


def execute_plan(
    *,
    run_id: str,
    manifest_path: Path,
    started_at: str,
    safety: WriteSafetyContext,
    now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(),
    hooks: CommitHooks = NO_HOOKS,
) -> Report:
    """The mutation entrypoint (F8): requires the sealed capability, proves
    it was issued for exactly this run/destination, and executes THE
    CAPABILITY'S plan, config, and factory-derived effective options — fresh
    values reconstructed from the immutable authority its factory gated
    (CR-R5-002/CR-R10-003). There is no plan/config/options/reference/hash
    parameter to disagree with the factory-read artifact, in exact symmetry
    with restore's `safety.chain`."""
    safety.confirm_apply(run_id=run_id, manifest_path=manifest_path)
    gated_plan, gated_config, plan_ref, options, resume_chain, prior_attempt = (
        safety._consume_apply_state()
    )
    ...  # derive prior-manifest hash, seal _ApplyRun, loop over gated action IDs
```

- [ ] **Step 3: `write_report` no-clobber passthrough (CR-007)**

In `artifacts.py`, `write_json_artifact(document, path)` gains `*, clobber: bool = True` forwarded to its atomic publish; `write_report(report, path)` gains the same and forwards it. `FileExistsError` propagates to the caller (only the `clobber=False` refusal path can see it).

- [ ] **Step 4: Create `tests/helpers/writectx.py`**

```python
"""Write-ceremony helpers for the e2e library-API test idiom: every
mutation test enters the real factory (lock in a tmp state dir, real gate,
real guard) — the ceremony itself is under test everywhere it is used."""

import contextlib
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from docmend import artifacts
from docmend.plan import Plan
from docmend.writer.commit import (
    WriteSafetyContext,
    apply_write_context,
    restore_write_context,
)
from docmend.writer.gate import ApplyOptions


@contextlib.contextmanager
def apply_safety(
    plan: Plan,
    *,
    options: ApplyOptions,
    manifest_path: Path,
    report_path: Path,
    run_id: str,
    state_dir: Path,
    resume_manifest_paths: Sequence[Path] = (),
    prior_report_paths: Sequence[Path] = (),
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[WriteSafetyContext]:
    assert plan.source_root is not None
    plan_path = state_dir / "plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    artifacts.write_plan(plan, plan_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(state_dir))
    with apply_write_context(
        plan_path,
        run_id=run_id,
        manifest_path=manifest_path,
        report_path=report_path,
        # Test fixtures already express explicit effective values; production
        # CLI callers pass only actual command-line overrides (CR-R10-003).
        backup_root_override=options.backup_root,
        preserved_by=options.preserved_by,
        allow_no_backup=options.allow_no_backup,
        resume_manifest_paths=resume_manifest_paths,
        prior_report_paths=prior_report_paths,
    ) as safety:
        yield safety


@contextlib.contextmanager
def restore_safety(
    manifest_paths: list[Path],
    *,
    run_id: str,
    manifest_out: Path,
    state_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[WriteSafetyContext]:
    monkeypatch.setenv("XDG_STATE_HOME", str(state_dir))
    with restore_write_context(
        manifest_paths, run_id=run_id, manifest_out=manifest_out,
    ) as safety:
        yield safety
```

(No exclude parameter anywhere: the factory reads the chain root header's recorded `effective_excludes` — CR-006 round 3. Tests vary the license by writing headers with different `effective_excludes` values via `tests/helpers/manifest2.header_doc`.)

- [ ] **Step 5: Rewire the CLI `apply` command**

Replace cli.py's current lock/gate/execute section (lines 608-670). At the command's initial load, replace `artifacts.read_plan(plan_path)` plus the later `sha256_of_file(plan_path)` with one `plan, plan_sha256 = artifacts.read_plan_snapshot(plan_path)` call. Construct preview's `ArtifactRef` with that returned digest, and use the same model/config/digest for preview predecessor validation, guards, and reporting; do not reopen the plan to hash it (CR-R9-002). Write mode still lets the factory take its own later authoritative snapshot: CLI preflight is advisory, while the factory repeats every applicability check, guard, and gate from its snapshot. Delete the CLI's eager effective `ApplyOptions` construction. It passes only `backup_dir` as an explicit override (resolved once when present), `preserved_by`, and `allow_no_backup`; the factory combines those with its own plan config (CR-R10-003). The CLI-side `_guard_artifact_paths` preflight stays for BOTH modes (early, formatted refusal; the factory's guard is the engine-level belt):

```python
    try:
        plan, plan_sha256 = artifacts.read_plan_snapshot(plan_path)
    except artifacts.ArtifactError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    ...  # schema/root/config checks use this plan snapshot
    plan_ref = ArtifactRef(
        path=str(plan_path), run_id=plan.run_id, sha256=plan_sha256
    )

    if write:
        def _on_refusal(
            refusals: list[commit.GateRefusal],
            factory_plan_ref: ArtifactRef,
            factory_prior_attempt: PriorAttempt | None,
        ) -> None:
            # Runs IN-LOCK (CR-007): messages, log, and the refusal report
            # publish under the same coordination boundary as the decision.
            for refusal in refusals:
                typer.echo(f"refused [{refusal.predicate}]: {refusal.message}", err=True)
                log.error("gate refusal", predicate=refusal.predicate, detail=refusal.message)
            _write_refusal_report(
                factory_plan_ref,
                run_id,
                started_at,
                report_path,
                prior_attempt=factory_prior_attempt,
            )

        try:
            with commit.apply_write_context(
                plan_path,
                run_id=run_id,
                manifest_path=manifest_path,
                report_path=report_path,
                backup_root_override=(
                    backup_dir.resolve() if backup_dir is not None else None
                ),
                preserved_by=(
                    preserved_by.value if preserved_by is not None else None
                ),
                allow_no_backup=allow_no_backup,
                resume_manifest_paths=resume_manifest_paths,
                prior_report_paths=prior_report_paths,
                input_artifacts=guard_inputs,  # the same list the preflight used
                on_refusal=_on_refusal,
            ) as safety:
                # Issue #15 renames-only warning: unchanged block, now inside
                # the context (it presumes a PASSED gate).
                ...
                result = execute_plan(
                    run_id=run_id, manifest_path=manifest_path,
                    started_at=started_at, safety=safety,
                )
                # rev 0.26: manifest hash + report finalize INSIDE the context
                # — the factory holds the lock through report publication.
                if manifest_path.exists():
                    result = result.model_copy(
                        update={"manifest_sha256": manifest.manifest_sha256(manifest_path)}
                    )
                safety.confirm_report(report_path)  # CR-002 rd 2: the guarded destination
                artifacts.write_report(result, report_path)
        except manifest.ManifestContainmentError as exc:
            typer.echo(f"refused: {exc}", err=True)
            raise typer.Exit(3) from exc
        except artifacts.ArtifactError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(2) from exc
        except commit.WriteRefusedError as exc:
            raise typer.Exit(3) from exc  # _on_refusal already reported in-lock
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
            try:
                # adr-0021 decision driver (review round 3, CR-NEW-005): a
                # dry run leaves PRIOR artifacts untouched — its own report
                # publishes no-clobber, so an operator-selected --report
                # naming an existing file keeps that file.
                artifacts.write_report(result, report_path, clobber=False)
            except FileExistsError as exc:
                typer.echo(
                    f"error: report not written: {report_path} already exists "
                    f"(dry runs leave prior artifacts untouched; adr-0021)",
                    err=True,
                )
                raise typer.Exit(2) from exc
        finally:
            run_lock.release()
```

Add the matching CLI regression: dry-run apply with `--report` naming an existing file → exit 2, the pre-existing file byte-identical, the stderr note present (CR-NEW-005).

Add a preview snapshot regression that replaces the plan path if a second read is attempted: in dry-run mode, assert the command reads the plan artifact bytes once, executes the first snapshot's model/config, constructs `plan_ref.sha256` from those exact bytes, validates predecessors against that digest, and never binds plan A's model to plan B's hash (CR-R9-002).

Add write-mode CLI regressions for the authoritative second snapshot (CR-R10-003/004/005): after advisory plan A passes, replace it before factory entry with (a) compatible plan B using a different configured backup directory and prove B's default is retained, (b) a future-minor plan and assert exit 2 before lock/gate/mutation, and (c) an invalid/unreadable artifact and assert exit 2. Add malformed predecessor → `ArtifactError` → exit 2 and containment-invalid predecessor → `ManifestContainmentError` → exit 3 regressions; neither exception may escape Typer.

Refactor `_resume_manifest_paths`/the sidecar-discovery head of `_load_resume_inputs` into `_resolve_resume_evidence_paths(...) -> tuple[list[Path], list[Path]]`. For each `--resume-run-id`, append only sidecars that actually exist and require at least one; never synthesize a nonexistent manifest path for a legal report-only predecessor (CR-R8-001). Combine explicit `--resume-manifest` and `--prior-report` inputs into the returned manifest and report lists.

For write mode, pass those two path lists to `apply_write_context`; do **not** call the CLI loader or construct `prior_attempt`. For preview, call the shared `_load_apply_predecessors` seam and pass its read-only chain/derived edge to `preview_plan`. `guard_inputs` includes the plan and both evidence-path lists; the factory repeats the authoritative guard internally. `_write_refusal_report` switches to the no-clobber write and gains a keyword-only `prior_attempt: PriorAttempt | None`; stamp that factory-derived edge on the refusal report instead of hardcoding null, so a report-only refused resume attempt stays in the attempt graph:

```python
    try:
        artifacts.write_report(..., report_path, clobber=False)
    except FileExistsError:
        # CR-007: a refused run must not replace ANY pre-existing artifact —
        # an operator-selected --report naming an existing file keeps it.
        typer.echo(
            f"refusal report not written: {report_path} already exists "
            f"(pre-existing artifact preserved; §8.5)",
            err=True,
        )
```

- [ ] **Step 6: Migrate the test suite**

Mechanical pattern, applied to every direct `execute_plan(...)` call in `tests/test_apply.py`, `tests/test_resume.py`, `tests/test_idempotency.py`, `tests/test_restore_drill.py` (apply half), `tests/test_scale.py`:

```python
# BEFORE
report = execute_plan(plan, config, run_id=RUN, plan_ref=ref, plan_sha256=SHA,
                      options=options, manifest_path=mp, started_at=TS)
# AFTER (write runs — helper materializes the plan; factory derives ref/hash)
with apply_safety(plan, options=options, manifest_path=mp,
                  report_path=tmp_path / "report.json", run_id=RUN,
                  state_dir=tmp_path / "locks", monkeypatch=monkeypatch) as safety:
    report = execute_plan(run_id=RUN, manifest_path=mp, started_at=TS,
                          safety=safety)
# AFTER (dry runs)
report = preview_plan(plan, config, run_id=RUN, plan_ref=ref, started_at=TS)
```

`tests/test_scale.py` additionally DROPS its separate `evaluate_gate` call + `assert refusals == []` — the factory evaluates the gate (entering the context asserts it passes). Keep the corpus/report assertions identical.

`TestActionTimeOverwriteInvariant` migrates to this exact shape (review round 2, CR-001 — the gate would otherwise refuse the pre-existing strategyless target and the action-time check would never run):

```python
        with apply_safety(plan, options=options, manifest_path=mp,
                          report_path=rp, run_id=RUN,
                          state_dir=tmp_path / "locks",
                          monkeypatch=monkeypatch) as safety:
            # The gate has passed (no target existed). NOW the target appears
            # — inside the gate->action window the invariant exists for.
            target.write_bytes(b"late arrival")
            report = execute_plan(run_id=RUN, manifest_path=mp,
                                  started_at=TS, safety=safety)
        assert report.outcomes[0].skip_reason == "collision-unpreserved"
```

CLI tests (`test_cli_apply.py`, `test_cli_resume.py`): behavior is meant to be UNCHANGED (same messages, same exit codes, same artifacts) — run them and fix only genuinely moved seams (e.g. a monkeypatch that targeted `cli._acquire_run_lock_strict` for the write path now targets the factory's `lock.acquire`). Add one new CLI regression: `--report` naming an existing file + a gate-refused run → exit 3, the pre-existing file byte-identical, the preserved-artifact stderr note present (CR-007).

Resume write tests pass predecessor manifest/report **paths** to `apply_safety(..., resume_manifest_paths=[...], prior_report_paths=[...])`; the factory derives the edge, and tests do not pass a constructed `ManifestChain` or `PriorAttempt` to `execute_plan`. Deliberately forged in-memory chains remain valid preview-only test inputs. Write helpers never accept a separate config; tests vary write policy by changing `plan.config` before materializing the artifact.

Update write-test expectations that used placeholder `SHA`/`ArtifactRef` values: the helper's materialized plan artifact is now the source of truth, so reports and manifest headers must agree with the factory-derived path/run/hash. Preview tests retain their caller-supplied illustrative `ArtifactRef` because preview is read-only and has no write ceremony.

- [ ] **Step 7: Run everything, full gate, commit**

Run: `uv run pytest -q` (full suite) then `uv run python scripts/check.py`

```bash
git add src/docmend/writer/apply.py src/docmend/cli.py src/docmend/artifacts.py \
        tests/helpers/writectx.py tests/test_apply.py tests/test_resume.py \
        tests/test_idempotency.py tests/test_restore_drill.py tests/test_scale.py \
        tests/test_cli_apply.py \
        tests/test_cli_resume.py
git commit -m "feat(apply): preview/write entrypoint split — attested WriteSafetyContext required (F8)"
```

---

### Task 10: Restore engine split (`preview_restore` / `run_restore`) + CLI rewire with effective config

**Files:**

- Modify: `src/docmend/restore.py` (split the dual-mode traversal and per-record helpers into structurally read-only preview functions and capability-required mutation functions)
- Modify: `src/docmend/cli.py` (the `restore` command: effective-config loading, lock/execute section, current lines 990-1005)
- Test: `tests/test_restore.py`, `tests/test_restore_drill.py`, `tests/test_apply.py`, plus the restore CLI tests (follow the existing layout)

**Interfaces:**

- Produces:
  - `preview_restore(chain, *, run_id, only_ids) -> list[RestoreOutcome]` — structurally read-only (no manifest/mutation branch); takes the caller's chain (reading is not gated).
  - `run_restore(*, run_id, only_ids, manifest_out, safety: WriteSafetyContext, hooks=NO_HOOKS) -> list[RestoreOutcome]` — NO chain parameter: the engine mutates from `safety.chain`, the factory-validated immutable object (CR-002); first statement `safety.confirm_restore(run_id=run_id, manifest_out=manifest_out)`.
  - `_preview_restore_one(...)` and preview pending-intent handling have no capability, manifest, hooks, or write flag and never call `finish_remaining`; sealed `_RestoreRun` is constructed only inside `run_restore` from `safety.chain` plus the attested manifest destination/scalars, and `_restore_one(run, action_id)` / `_converge_pending_restore(run, action_id)` accept no raw record/root/chain/manifest substitution points.
  - The restore CLI loads no configuration: the carve-out authority is the chain root header's recorded `effective_excludes`, read inside the factory (CR-006 round 3) — no new CLI options (CR-NEW-003 stays closed).

- [ ] **Step 1: Write the failing tests**

```python
class TestRestoreEntrypointSplit:
    def test_run_restore_takes_chain_from_capability(self, tmp_path: Path) -> None:
        """CR-002: there is no chain parameter to disagree with the
        preflight — the engine restores exactly what the factory validated."""
        ...  # apply, then restore_safety([manifest]) + run_restore(safety=...);
        # assert restoration happened per safety.chain.

    def test_run_restore_with_expired_capability__runtimeerror(self, tmp_path: Path) -> None:
        ...

    def test_run_restore_mismatched_run_id__attestation_refused(self, tmp_path: Path) -> None:
        ...

    def test_preview_restore__no_manifest_written_no_mutation(self, tmp_path: Path) -> None:
        ...

    def test_internal_restore_mutation_helpers_require_sealed_run_state(
        self, tmp_path: Path
    ) -> None:
        """CR-R7-002: no dual-mode helper survives; mutation helpers accept
        only a sealed run plus a lifecycle action ID."""
        assert not hasattr(restore_module, "_run_restore")
        assert "write" not in inspect.signature(restore_module._restore_one).parameters
        assert tuple(inspect.signature(restore_module._restore_one).parameters) == (
            "run",
            "action_id",
        )
        with pytest.raises(TypeError, match="engine-sealed"):
            restore_module._RestoreRun(...)
        with pytest.raises(KeyError, match="not in validated chain"):
            restore_module._restore_one(live_run, forged_action_id)

    def test_recorded_exclusion_replaced__in_corpus_manifest_out_refused(
        self, tmp_path: Path
    ) -> None:
        """CR-006 round 3 + adr-0021's required rejection test at the restore
        seam: the license authority is the chain root header's RECORDED
        effective excludes. A chain whose apply ran with a replacement
        exclude set (no `.docmend/**` coverage) withdraws the carve-out
        wholesale — an in-corpus manifest_out refuses
        (DestinationRefusedError) even though default-discovery excludes
        would have licensed it (the exact inversion rounds 2's approach
        missed: list flags REPLACE, so no later config load can know)."""
        ...  # write a chain via manifest2.write_set whose header carries
        # effective_excludes=("*.bak",) and source_root containing
        # ./.docmend; expect DestinationRefusedError from
        # restore_write_context; an otherwise-identical chain with the
        # stock excludes recorded succeeds.
```

- [ ] **Step 2: Split the engine**

Do **not** retain `_run_restore(..., write=...)` (CR-R6-002). Split the current traversal structurally:

1. `preview_restore` owns a read-only reducer traversal and calls `_preview_restore_one`; pending intents are adjudicated only to produce preview outcomes. It never creates a manifest or calls `finish_remaining`.
2. `run_restore` confirms the capability, takes `safety.chain`, creates the attested restore manifest, seals a `_RestoreRun`, and owns the mutation traversal. `_restore_one(run, action_id)` and `_converge_pending_restore(run, action_id)` are write-only; neither has a `write` parameter or accepts a raw record/root/chain/manifest.
3. Pure reducer ordering, backup verification, hash checks, and outcome formatting may be shared. No shared helper may accept the complete mutation inputs plus a naked boolean that makes it write-capable.

Concrete extraction map:

- `_preview_restore_one` owns the current live-target bind/hash, collision, backup verification, and mode/identity inspection through the existing `would_restore` return; it never stages or creates an inverse record.
- `_RestoreRun` is `@dataclass(frozen=True)` with a module-private constructor token held only by `run_restore`. It contains the active safety context, validated chain, canonical root, lifecycle/apply-terminal maps frozen with `MappingProxyType`, selector, run ID, manifest writer, and hooks; construction confirms the live restore capability. `_restore_one(run, action_id)` derives its record and every authority-bearing value from that state, then performs write-only staging, intent, commit, and terminal work.
- Preview pending-restore handling maps `never-happened -> None`, interference to `failed`, and recognized completed/finish states to `would_restore`. `_converge_pending_restore(run, action_id)` is mutation-only, resolves its intent/undone record from the run maps, and owns `finish_remaining` plus closure-terminal append.
- Lifecycle reduction, LIFO ordering, selector filtering, backup reads/hashes, and outcome formatting are pure shared helpers used by both top-level loops.

The wrappers are shaped as follows; each ellipsis is its own structurally separate loop:

```python
def preview_restore(
    chain: ManifestChain, *, run_id: str, only_ids: frozenset[str] | None
) -> list[RestoreOutcome]:
    """Read-only preview (F8/IR-008): today's dry-run restore."""
    ...  # read-only loop over _preview_restore_one


def run_restore(
    *,
    run_id: str,
    only_ids: frozenset[str] | None,
    manifest_out: Path,
    safety: WriteSafetyContext,
    hooks: CommitHooks = NO_HOOKS,
) -> list[RestoreOutcome]:
    """The mutation entrypoint (F8): restores the chain the FACTORY
    validated — `safety.chain`, not a caller argument (CR-002)."""
    safety.confirm_restore(run_id=run_id, manifest_out=manifest_out)
    ...  # seal _RestoreRun from safety.chain; loop over validated action IDs
```

- [ ] **Step 3: Rewire the CLI `restore` command**

The CLI's existing up-front `read_manifest_chain` stays for BOTH modes (capability message, empty check, dry-run input); the write path hands the PATHS to the factory, whose own validation is authoritative (the second parse is the price of an unforgeable preflight — restore is rare and manifests are line-bounded). Restore loads NO configuration at all (review round 3, CR-006: the carve-out authority is the chain root header's recorded `effective_excludes`, read inside the factory — round 2's default-discovery loading was inverted a second way, since replacement `--exclude` flags at apply time withdraw licenses no later config load can know about; IR-008's interface still gains nothing, keeping CR-NEW-003 closed):

```python
    manifest_out = artifact_dir / f"docmend-{run_id}-manifest.jsonl"
    if write:
        try:
            with commit.restore_write_context(
                manifest_paths,
                run_id=run_id,
                manifest_out=manifest_out,
            ) as safety:
                outcomes = run_restore(
                    run_id=run_id,
                    only_ids=frozenset(only_id) if only_id else None,
                    manifest_out=manifest_out,
                    safety=safety,
                )
        except commit.SafetyRefusedError as exc:
            typer.echo(f"refused: {exc}", err=True)
            raise typer.Exit(3) from exc
        except manifest.ManifestContainmentError as exc:
            typer.echo(f"refused [manifest-containment]: {exc}", err=True)
            raise typer.Exit(3) from exc
        except artifacts.ArtifactError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(2) from exc
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

(The round-2 idea of loading a config on restore is gone entirely — the recorded header is strictly more authoritative than any restore-time reconstruction, and IR-008's interface is untouched.)

- [ ] **Step 4: Migrate restore tests**

Enumerate every direct caller with `rg -n 'run_restore\(' tests` — including `tests/test_apply.py`'s restore drill (CR-R7-003). Write callers become `restore_safety([paths]) + run_restore(safety=...)`; read-only callers become `preview_restore(chain, ...)`.

This migration is **not** mechanical for handcrafted in-memory chains:

- Any test that exercises real write restore must materialize a valid on-disk chain through `tests/helpers/manifest2.write_set` (or the real apply helper), then pass those paths to `restore_safety`. Convert the LIFO test's synthetic second applied record into a valid linked manifest set on disk.
- Tests whose purpose is only reducer ordering/selector behavior may target a pure non-mutating ordering helper with their in-memory `ManifestChain`; they must not call the mutation engine.
- Add a regression that an in-memory chain with a substituted record cannot be supplied to `run_restore` because its signature has no chain parameter.

- [ ] **Step 5: Run everything, full gate, commit**

```bash
git add src/docmend/restore.py src/docmend/cli.py tests/test_apply.py \
        tests/test_restore.py tests/test_restore_drill.py
git commit -m "feat(restore): preview/write split — capability-bound chain, recorded carve-out excludes (F8)"
```

---

### Task 11: Changelog

**Files:**

- Modify: `CHANGELOG.md` ([Unreleased])

- [ ] **Step 1: Changelog**

Under `## [Unreleased]`, update the intro line to "plans A, B and C of four" / "DMR-01..DMR-04, DMR-06/07", and add after the manifest-2.0 section:

```markdown
### Changed — commit boundary (plan C, BREAKING for library callers)

- **Every mutation commits against the object it validated (adr-0020, DMR-06):** apply and restore read each file's bytes exactly once through an `O_NOFOLLOW` descriptor whose `(st_dev, st_ino)` identity is captured (and journaled, per plan B), and immediately before every publish and unlink the pathname is `lstat`-compared against that identity with containment re-resolved at the same instant — including the staged temp about to be published, absent destinations' parent chains, and the surviving object before every destructive second step. Interference caught before mutation skips the action as `external-interference` with the corpus untouched; interference after a lossless first step retains every possibly-last copy, reports failure, and leaves the intent dangling for adjudication. The `lstat`-to-`rename` microsecond interval is the stated residual (POSIX rename cannot be fully TOCTOU-free).
- **Overwrite preservation is an action-time invariant (DMR-07):** a target discovered at action time is clobbered only under an active byte-preserving strategy and is backed up through its own descriptor with an identity check immediately before `os.replace`; a target appearing later is published no-clobber and skipped `collision-unpreserved` — never silently overwritten. The gate's plan-time overwrite check remains as early feedback only.
- **Failed terminals are proofs (spec §10.4):** a `failed` manifest terminal is appended only when the pre-action state is proven — rollbacks are themselves identity-checked, replacement writes stage first, no rollback ever removes the last surviving name of a validated object, and an unprovable intermediate keeps its journal intent for resume/restore adjudication instead of asserting a clean failure.
- **Post-crash adjudication finishes carry the same boundary:** `finish-remaining` residual steps re-resolve containment at the act instant, distinguish unobservable names from absence, use stage-first replacement writes, and preserve mode captured with identity and bytes through the same descriptor.
- **Read/write entrypoint split (F8):** `preview_plan`/`preview_restore` are the read-only engines (dry-run behavior unchanged, except a dry run's report now publishes no-clobber — a pre-existing artifact at the destination is preserved, per adr-0021); `execute_plan`/`run_restore` now require a `WriteSafetyContext` — a sealed capability whose only factories acquire the run lock, evaluate the apply gate / perform the restore chain preflight themselves, guard the run's artifact destinations, and attest exactly which plan/config/chain, root, run, options, and destinations they authorized. Apply authority derives from one factory-read plan byte snapshot, including its embedded config; the capability retains immutable serialized plan/config payloads and the engine reconstructs fresh private models, while the validated restore chain is deep-frozen to its leaves. Preview likewise derives its plan model and `ArtifactRef` digest from one CLI read. Library callers cannot reach corpus mutation without the ceremony, substitute a config independent of the reviewed plan, mutate retained gated models, or use a ceremony for a different root or other inputs; the CLI's public interface is unchanged.
- **The manifest header records the run's effective excludes:** restore's artifact-destination carve-out is licensed against the excludes that governed the APPLY run, read from the chain root header — per-invocation replacement flags made the apply-time exclude set unreconstructable by any later config load (adr-0021's wholesale-withdrawal clause).
- A gate-refused `apply` publishes its refusal report inside the run lock and never replaces a pre-existing report artifact.
- New skip reasons: `external-interference`, `collision-unpreserved`. No new exit codes; no schema version changes (the report schema's `skip_reason` is an open string).
```

- [ ] **Step 2: Full gate, commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): plan C — commit boundary, action-time overwrite invariant, F8 split"
```

---

### Task 12: Spec §17.3 traceability sync (CR-009)

**Files:**

- Modify: `docs/specs/docmend.md` (§17.3 rows + one Document History entry — status accuracy only, no behavioral text)

- [ ] **Step 1: Update the rows Plan C implements**

Per Appendix B, §17.3 must stay current. Update with named Plan C tests:

- **FR-003**: append the commit-boundary evidence — `tests/unit/writer/test_commit.py` (bind/check primitives, predicate matrix), `tests/test_apply.py::TestCommitBoundarySourceBinding` / `TestCommitBoundaryRaces`. Status: the rev 0.26 recontract portion covered here moves from pending to implemented wording.
- **FR-005**: append the `WriteSafetyContext` evidence — `tests/unit/writer/test_commit.py::TestWriteSafetyContext` (sealing, attestation, in-lock refusal callback), `tests/test_apply.py::TestEntrypointSplit`. Status: Complete (rev 0.26 sealed-boundary portion now implemented).
- **FR-011**: append the action-time invariant evidence — `tests/test_apply.py::TestActionTimeOverwriteInvariant`, the `collision-unpreserved` race tests. Status: Complete (rev 0.26 action-time portion now implemented).
- **IR-008**: append the restore-side boundary + factory-preflight evidence — `tests/test_restore.py::TestRestoreCommitBoundary` / `TestRestoreEntrypointSplit`.

- [ ] **Step 2: Reconcile the rows Plans A/B already satisfied (drift found verifying CR-009)**

The following rows still read "pending v2 implementation" although their recontracted portions landed on `dev`: **FR-006** (write-once BackupStore + output ledger — Plan A, `b9d5195..6ae7547`), **FR-013** (journal-every-mutation, chain lineage, adjudication — Plan B), **IR-007** (destination guard, carve-out tests, `O_EXCL` staging — Plan A), **DR-003** (`not-attempted`, totals, lineage — Plan B), **DR-004** (manifest 2.0 — Plan B). Update each with its landed test evidence (Plan A: `tests/unit/writer/test_backup.py`, `tests/test_planning.py` ledger set, the artifact-guard test set; Plan B: `tests/unit/writer/test_manifest.py`, `tests/unit/writer/test_adjudicate.py`, `tests/test_manifest_chain.py`, `tests/test_resume.py`/`tests/test_restore.py` 2.0 sets — use the actual file/class names in the tree). **FR-014** and **IR-004** stay "pending v2 implementation" honestly — that is Plan D. Do not touch requirement statements, only the §17.3 evidence/status columns.

- [ ] **Step 3: Document History entry + validation**

Add one history row (next rev number): "§17.3 traceability sync for the landed safety-core plans A–C — evidence and status columns only, no requirement changes (plan-review CR-009)."

Run: `uv run python scripts/check_traceability.py` and the repo's spec validation (the same checks `validate-specs` CI runs), then the full gate.

- [ ] **Step 4: Commit**

```bash
git add docs/specs/docmend.md
git commit -m "docs(spec): §17.3 traceability sync for plans A-C (review CR-009)"
```

---

## Self-Review Notes (design-coverage check)

- Design §Commit Boundary F2/F3 → Tasks 1-6; the strategy re-check closes the gate→action window (CR-001) and the migrated test provably exercises it (Task 9). Residual-window statement → Task 11 + `commit.py` docstring. Deterministic hooks for every listed window plus rounds 1-2 additions → mapping table in File Structure.
- Design §F8 → Tasks 8-10 — the capability CARRIES immutable serializations of the private plan/config snapshots and effective options the factory gated, with the source root canonicalized into that same snapshot; apply resume manifests and restore manifests are factory-loaded validated chains (CR-R7-001); preview and mutation cores are structurally separate; and sealed `_ApplyRun`/`_RestoreRun` states make supported mutation orchestration derive every action/record/root/config/options/chain/manifest value from the capability (CR-R6-002/CR-R7-002/CR-R10-003). Both factories own the canonical XDG lock namespace and invoking-directory `.docmend/` carve-out (CR-R10-001/002). Low-level POSIX/atomic primitives remain internal mechanisms and unit-test seams, not public engine entrypoints or a claimed Python security sandbox. Every docmend engine mutation still passes adr-0020 checks: live commits, survivor-last rollbacks, staged-temp cleanup, and adjudicated finishes.
- adr-0020 Confirmation list: every named race test exists; the same-bytes/different-inode probes have live-window counterparts; the dangling-intent → resume-adjudication composition test reflects the ACTUAL interference contract (no closure terminal — CR-NEW-002).
- adr-0021's exclusion-removed rejection test exists at the restore seam (Task 10), now against the RECORDED header excludes (round 3).
- Round-3/6 destructive-step audit: every destroy-or-replace verifies (a) the destroyed object, (b) containment at the act instant, and (c) the survivor that makes destruction safe — live commits (`guarded_rename_no_clobber`, `guarded_replace(survivor=...)`), rollbacks (target authorized first, four-state observation, survivor verified last, unobservable ⇒ unproven), staged-temp cleanup (identity-checked in `abort_staged` AND inside `publish_staged`'s own failure paths), and adjudicated finishes (`_verified_unlink(survivor=...)`, descriptor-bound `_observe`).
- Already landed during review (not plan tasks): the chain validator's standalone-failed rejection — a live Plan B defect making any run with a pre-mutation failure unresumable — fixed as `8c2d5f4` with chain + e2e regressions and the design's lifecycle sentence disambiguated (CR-NEW-002).
- Deliberate decisions for the reviewer: (1) `WriteSafetyContext` lives in `writer/commit.py` (one new module, per the design's file map); (2) the action-time strategy re-check fires on write runs only — preview options are synthesized without the operator's strategy flags (Task 3 comment); (3) restore's write path parses the chain twice (CLI messaging + factory preflight) — the price of an unforgeable validated-chain capability; (4) preview keeps today's CLI-side locking per F8's "current lock semantics"; (5) `_undo_publish`/`guarded_replace` prove bytes+mode, not inode — `os.replace` cannot resurrect an inode; the recorded backup carries the recovery contract; (6) restore's carve-out excludes come from the chain root header's recorded `effective_excludes` (CR-006 round 3) — an additive field in the unreleased manifest 2.0 header behind a HARD owner-approval checkpoint at the top of Task 8 (round 4: Tasks 1-7 may proceed while the decision is pending; Task 8 stops without sign-off); no restore CLI surface is added (CR-NEW-003); (6a) the factory deep-copies before gating, then retains immutable serialized payloads and reconstructs fresh engine inputs — cost remains proportional to plan size, with the opt-in scale lane verifying NFR-001; (7) a rename target link is the original inode and is never removable when the source is lost; a `rename_and_rewrite` target is the staged output, but rollback still retains it whenever the source survivor cannot be proven, because it may be the last useful copy (CR-R5-003).
- Type-consistency: primitives' names/signatures identical across Tasks 1-7; `confirm_apply(run_id=, manifest_path=)`/`_consume_apply_state()`/`confirm_restore`/`confirm_report`/`safety.chain` across 8-10; `_ApplyRun`/`_RestoreRun` seal authority-bearing orchestration inputs; `apply_safety`/`restore_safety` across 9-10. The plan artifact's single byte snapshot yields the gated model/config/effective options, `ArtifactRef`, manifest `plan_sha256`, report `plan_ref`, and predecessor-graph binding; no caller supplies any of those identities or the production lock/artifact namespaces.
