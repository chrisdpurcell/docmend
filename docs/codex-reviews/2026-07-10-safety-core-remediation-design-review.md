# Safety-Core Remediation Design Review

Claude Code note: consider using the `superpowers:receiving-code-review` skill.

## Verdict

Verdict: **REVISE AND RE-REVIEW**

The design correctly groups DMR-01 through DMR-07 around shared safety abstractions, but it is not yet implementable without unsafe inference. Six blocking gaps remain in the artifact destination boundary, commit-time identity checks, manifest/restore state model, backup trust boundary, and verify input contract. Two additional change-control and API-boundary issues should be resolved before planning.

## Review Target and Method

- Target: `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md`
- Pinned state: commit `dc2ae9e5eda183365f70cae823421a782c022dce` on `dev`; worktree clean at review start
- Workflow: the `project-standards` `review-spec` workflow, schema version 1.1
- Ground truth checked: SPEC-VHHB revision 0.25; ADRs 0004, 0005, 0006, and 0012; the comprehensive review synthesis; current CLI, planning, writer, restore, verify, artifact, schema, and report code; relevant tests; current repository conventions and handoff pointers
- Live checks: `git status`, `git log`, `pytest --collect-only` (620 tests), and `coverage report --format=total` (97)

## Verified and Held

These parts held against the current repository and need not be re-litigated unless the design changes materially:

- The DMR-01 through DMR-07 problem statements accurately reflect the confirmed synthesis and current code paths.
- The plan-wide output ledger closes the demonstrated `a.md` rewrite versus `a.txt -> a.md` same-plan collision when every action claims its effective output path.
- Backup namespacing by run, action, and role closes the demonstrated source/overwritten-target key collision.
- A manifest header, strict set validation, intent-before-mutation journaling, and one reducer are the right architectural direction for DMR-03 through DMR-05.
- Randomized exclusive staging addresses the fixed-temp truncation and stale-temp retry defects.
- Commit-time overwrite preservation, plan-aware verification, timeout findings, restore selector findings, and write-entrypoint coordination all trace to confirmed review findings.
- All named source modules exist. `writer/commit.py` is the only proposed new module. The current branch still reports 97% coverage.
- A major manifest and backup-layout break is consistent with a v2.0.0 release target, subject to the explicit compatibility decision already recorded in the design.

## Findings

### F1 — 🔴 Blocking: the artifact guard rejects the supported default artifact location

**Defect:** The design refuses every artifact destination inside the corpus root. docmend's accepted default is `./.docmend/` in the invoking directory, and `scan .`, `plan .`, and the single-file journey deliberately write there. For the common `PATH=.` invocation, that directory is inside the corpus root. Implementing the proposed rule literally makes the default workflow refuse before it can emit its required artifacts.

**Evidence:**

- Design lines 91–95 require refusal when a destination lies inside the corpus root.
- SPEC-VHHB §18.2 names `.docmend/` as the tool's default artifact/log directory and default exclusion; OQ-034 records owner sign-off on that convention.
- `src/docmend/cli.py` lines 178–191 and 265–313 write default inventory and plan artifacts below `./.docmend/`.
- `tests/test_cli_scan.py`, `tests/test_cli_plan.py`, and `tests/test_restore_drill.py::test_single_file_journey__scan_plan_apply_with_defaults` treat this as binding behavior.
- NFR-006 requires the default small-scale pipeline to work without extra setup.

**Concrete fix:** Choose and state one coherent boundary. Prefer allowing only the canonical tool-owned artifact root inside the source root after proving it is excluded from discovery and does not alias any selected input; reject every other in-root destination. Alternatively, move the v2 default artifact root outside the corpus and explicitly revise OQ-034, §18.2, CLI help, sidecar discovery, README/runbooks, and tests. Add `scan .`, `plan .`, apply, restore, and verify default-path acceptance tests plus explicit in-corpus source-file rejection tests.

### F2 — 🔴 Blocking: `fstat` on the open descriptor does not detect pathname replacement

**Defect:** The proposed source check opens one descriptor, captures `(st_dev, st_ino)`, then "re-stats the source by descriptor" before publication. `fstat(fd)` continues to describe the originally opened inode even after another process replaces the pathname. Re-resolving containment also does not detect replacement by a different regular file at the same in-root path. This leaves the exact regular-file replacement reproduced in DMR-06 undetected while the design claims that changed device/inode is caught.

**Evidence:**

- Design lines 85–89 define the CommitBoundary mechanism and closure claim.
- DMR-06 records a controlled replacement after the hash check that was silently overwritten.
- Current `src/docmend/writer/apply.py` lines 363–379 demonstrates the pathname-based sequence being replaced; the design must add a pathname-to-descriptor identity comparison, not only a second descriptor stat.

**Concrete fix:** Immediately before each pathname mutation, `lstat`/`stat(..., follow_symlinks=False)` the source name and compare its `(st_dev, st_ino)` with the descriptor's captured identity; reject missing names, symlinks, or mismatches as `external-interference`. Specify directory-descriptor anchoring or an equivalent parent-path defense so `O_NOFOLLOW` on only the final component is not mistaken for full path containment. State which check is repeated for every publish/unlink step and cover regular-file replacement, parent-symlink replacement, and unlink/publish windows with deterministic hooks.

### F3 — 🔴 Blocking: target preservation is not bound to the object actually overwritten

**Defect:** The design backs up a target found at commit time but does not bind the later overwrite to that target's identity. A process can replace the target after docmend reads and backs it up but before `os.replace`; docmend would then clobber a different, unpreserved object. The stated action-time invariant therefore does not fully close DMR-07.

**Evidence:**

- Design line 89 requires any target present at commit to have a verified preservation outcome but specifies no target identity capture or recheck.
- The same section documents only the source-side residual window.
- DMR-07 is specifically a target-appears/changes-after-earlier-check defect; current `src/docmend/writer/apply.py` lines 389–465 separates target inspection/backup from later publication.

**Concrete fix:** Open the existing target without following symlinks, capture its identity, read and back up through that descriptor, then compare the target pathname to that identity immediately before overwrite. If it disappears or changes, skip with `external-interference`; if it appears after an absent-target check, use a no-clobber publish and map `EEXIST` to `collision-unpreserved`. Document the remaining target-side race explicitly and add hooks for target replacement after backup and target creation immediately before publish.

### F4 — 🔴 Blocking: ManifestSet lacks the lineage and inverse model required by the reducer

**Defect:** The design promises one reducer that yields `applied`, `failed`, `pending-intent`, and `restored` across apply, resume, and restore manifests, but the described format cannot represent that history unambiguously. The header example only shows `kind: apply`; record results are only `intent | applied | failed`; no inverse record links a restore to the apply action it undoes; and separate ManifestSets are ordered by wall-clock `recorded_at` rather than durable lineage. `plan_sha256` alone does not prove which manifests form one resume/restore chain or validate that lifecycle records retain identical action facts.

**Evidence:**

- Design lines 54–79 define the header, lifecycle legality, and cross-set reducer.
- Design lines 70 and 81 require journaled restore inverses and convergent re-run without defining their record shape or dangling-intent adjudication states.
- Current `src/docmend/cli.py` lines 447–461 supports repeatable multiply-interrupted resume manifests.
- Current `src/docmend/restore.py` lines 268–284 writes inverse evidence under a new run and new action ID, so a reducer needs an explicit link to the original action; that relationship cannot be inferred safely from timestamps or paths.
- ADR-0006 requires deterministic reconciliation and hard failure rather than guessing.

**Concrete fix:** Define the complete 2.0 wire model before planning: apply and restore header kinds; stable plan/action identity; immutable fields that must match between intent and terminal records; an explicit `undoes`/`inverse_of` reference for restore; prior-manifest hash or another deterministic chain relation; same-plan and same-root constraints across a chain; and exact dangling-intent state tables for every apply and restore operation. Order by validated chain position then record sequence, not wall-clock timestamps. Show at least one complete apply → interrupted resume → interrupted restore example and prove how the reducer reaches `restored`.

### F5 — 🔴 Blocking: "outside source root" is not a sufficient backup trust boundary

**Defect:** ManifestSet accepts any backup path that resolves outside the source root. A crafted manifest can point to any readable external file, set the recorded digest to that file's hash, and cause restore to write those bytes into an in-root document. External preservation declarations do not need arbitrary backup paths; current manifest backup paths represent tool-written backups and are null otherwise. The proposed validation therefore still trusts manifest-controlled recovery input and does not fully close DMR-03.

**Evidence:**

- Design lines 46–50 define a deterministic BackupStore layout.
- Design line 77 validates backup paths only as outside `source_root`.
- Current `src/docmend/restore.py` lines 48–80 and 187–225 reads the recorded paths and trusts them after matching the manifest-provided digest.
- ADR-0004 distinguishes tool-written backup references from Git/external preservation.

**Concrete fix:** Put the resolved tool `backup_root` in the trusted header and require every non-null backup path to resolve beneath it and exactly match the `(run, action, role, relative_path)` BackupStore key. Validate regular-file type, no symlink traversal, role/hash consistency, and source/overwritten-role cardinality before opening any backup. Keep external-preservation records null and route their recovery outside `docmend restore`.

### F6 — 🔴 Blocking: verify's stated inputs cannot prove its required plan coverage

**Defect:** The design says verify is a consumer of Plan, ManifestSet, and BackupStore, but the false-clean fix relies on apply-report-only outcomes: `skipped`, `failed`, and the new `not-attempted` status. A manifest intentionally does not record ordinary skips, and post-abort actions have no manifest record. `verify --plan` cannot establish exactly one terminal outcome per action from the listed inputs, so a literal implementation can remain false-clean.

**Evidence:**

- Design lines 97–109 omit Report from the consumer list while line 105 depends on the report's new status.
- Current `src/docmend/report.py` owns applied/would-apply/skipped/failed outcomes; current `src/docmend/verify.py` already needs Report for cross-artifact accounting.
- ADR-0012 line 68 explicitly defines verify inputs as manifest, report, and plan via flags or sidecar discovery.

**Concrete fix:** Make the apply Report an explicit required input for plan-coverage verification and define how plan, report, and every manifest in the validated chain bind by plan hash/run identity. Specify behavior for a missing report, dry-run reports (`would_apply`), multiple resume reports, report publication interrupted after corpus mutation, and duplicate/missing action outcomes. Define the report totals change for `not-attempted` and add a full action-partition invariant that includes every status.

### F7 — 🟡 Should fix: change control does not reconcile the accepted ADRs it changes

**Defect:** The follow-through lists only new ADRs, but the design changes decisions already owned by accepted ADRs. In particular, artifact/path guard refusal is assigned exit 2 while ADR-0012 assigns path-containment safety refusal exit 3; Manifest 2.0 rejects all 1.x inputs and adds a fifth durable verify artifact while ADR-0005 owns compatibility and four durable artifacts; and the journal/reducer supersedes ADR-0006's current single-step model. Leaving both accepted decisions active creates external inconsistency even after new ADRs are added.

**Evidence:**

- Design lines 120–143 define the changed taxonomy and change-control list.
- ADR-0012 lines 59–68 defines the tool-wide exit taxonomy and path containment as exit 3.
- ADR-0005 lines 57–70 defines the four artifact schemas and compatibility policy.
- ADR-0006 lines 57–74 defines the current recovery model and its manifest 1.3 amendment.
- ADR-0004 owns gate, backup, and restore safety semantics affected by `SafetyContext` and action-time preservation.

**Concrete fix:** Name the ADR disposition in the design: amend or supersede ADRs 0004, 0005, 0006, and 0012; add reciprocal `supersedes`/`superseded_by` metadata and index changes; and state the final exit-code classification for artifact destination refusal, manifest containment failure, commit-time interference, and the ordinary preservation gate. Include the new verify-report schema under the revised artifact-contract owner.

### F8 — 🟡 Should fix: `SafetyContext` has no defined read-only construction path

**Defect:** `execute_plan` and `run_restore` currently serve both dry-run and write modes. The design says both require a `SafetyContext` constructible only after acquiring the run lock and passing the gate. Restore has no apply preservation gate, and apply/restore dry-runs must remain usable without write-safety ceremony. The current statement either over-gates read-only execution or leaves implementers to invent a bypass that weakens the intended engine boundary.

**Evidence:**

- Design line 36 defines the context requirement.
- FR-004 and IR-008 require dry-run defaults.
- Current `src/docmend/cli.py` lines 404–580 and 664–754 call the same engines for preview and write paths.

**Concrete fix:** Split read-only planning/preview from mutation entrypoints, or define distinct sealed `ReadContext` and `WriteSafetyContext` capabilities. Specify exactly which factory acquires the lock, runs the appropriate apply or restore preconditions, owns artifact guard results, and keeps the capability valid through report/manifest finalization.

## Re-Review Gate

The next round should re-check only the revised contracts and their downstream consistency, then confirm:

1. Default `.docmend/` behavior and the artifact guard coexist without an alias/clobber path.
2. Both source and overwrite-target pathname identities are compared with the descriptors whose bytes were validated and backed up.
3. A complete Manifest 2.0 example proves deterministic apply/resume/restore reduction, including interrupted inverse operations.
4. Backup references are constrained to the declared BackupStore, not merely outside the corpus.
5. Plan coverage consumes and binds plan, report(s), and manifest chain(s) with no unrepresented outcome.
6. Existing ADR owners are explicitly amended or superseded and the final exit taxonomy is consistent.

## Round 2 — 2026-07-10

### Verdict

Verdict: **REVISE AND RE-REVIEW**

Round 2 verified the design revision at commit `b072a644556a6fe79be1c7b20c5ffea88e59970e`. Six prior findings are closed: F1, F2, F3, F5, F7, and F8. F4 and F6 remain blocking because their revised rules still omit live states that the current implementation and tests prove can occur. No independent new finding was opened.

### Round 2 Target and Method

- Target revision: commit `b072a644556a6fe79be1c7b20c5ffea88e59970e` on `dev`
- Delta reviewed: 90 insertions and 35 deletions relative to round 1's `dc2ae9e`
- Worktree note: the round-1 review document remained untracked; the target design itself was committed and had no working-tree edits
- Re-verified against: current atomic rename primitives, restore mutation ordering, resume report behavior, SPEC-VHHB, ADRs 0004/0005/0006/0012, and the comprehensive review synthesis
- Document checks: the revised design passed scoped markdownlint and `git diff --check`

### Prior Finding Disposition

| Finding | Round 2 status | Evidence |
| --- | --- | --- |
| F1 | Closed | Design lines 124–131 preserve the canonical `.docmend/` root only while its effective exclusion holds, reject other in-root destinations, run the guard before the pipeline, and add default-path plus rejection tests. |
| F2 | Closed | Lines 114–122 now compare each source pathname's `lstat` identity with the descriptor identity before every publish/unlink and separately re-check parent-path containment. |
| F3 | Closed | Lines 120–122 bind overwrite backup bytes to a target descriptor, compare the pathname identity immediately before replacement, use no-clobber publication after an absent-target observation, and test both target race classes. |
| F4 | Open — blocking | Chain lineage and inverse references are now defined, but the dangling-intent table still omits known intermediate states; details below. |
| F5 | Closed | Lines 48–51 and 64–90 constrain non-null backup references to the header's resolved BackupStore root and derivable `(run, action, role, relative-path)` key, with type/symlink/cardinality checks before access. |
| F6 | Open — blocking | Report is now an explicit verify input, but the multi-report reduction rule conflicts with the existing `already-applied` resume outcome; details below. |
| F7 | Closed | Lines 163–172 and 187–197 assign consistent exit classes and explicitly amend or supersede ADRs 0004, 0005, 0006, and 0012 with reciprocal metadata for ADR-0006. |
| F8 | Closed | Line 38 separates preview entrypoints from mutation entrypoints and defines the sealed `WriteSafetyContext` factory, preconditions, artifact guard, lock lifetime, and finalization ownership. |

### F4 — 🔴 Still blocking: the adjudication table does not cover known partial mutation states

**Remaining defect:** The revised wire model, chain links, immutable-field rule, inverse references, and worked example resolve the representation half of F4. The state table does not yet resolve the execution half. It classifies only full pre-mutation and full post-mutation states for pure rename and all restore inverses. Current primitives deliberately have intermediate, lossless states after their first mutation step. Those states fall through to `external-interference`, so an interruption still fails to converge even though the journal provides enough evidence to finish safely.

**Evidence:**

- Design lines 96–106 cover pure rename only when the source is gone or the target is absent. They do not cover both source and target naming the same captured inode.
- `src/docmend/writer/atomic.py` lines 106–128 implements no-clobber rename as `link` then `unlink`; its contract explicitly states that a crash between them leaves both names pointing at one intact inode.
- Design lines 104–105 collapse every restore operation into only "expected outcome" or "pre-inverse state."
- `src/docmend/restore.py` lines 242–258 has multi-step inverse states: overwrite-rename restore links the applied target back to the original name before replacing the target, and rename-and-rewrite restore reinstates the original before removing or replacing the applied target.
- A kill between either pair of steps produces neither the complete pre-inverse state nor the complete expected outcome. Mapping it to interference contradicts the design's line 110 convergence claim and DMR-04's required direction.

**Concrete fix:** Expand the adjudication contract per operation and overwrite mode. At minimum define: pure rename with both names bound to the captured inode → unlink the source and append `applied`; restore rename with the original relinked but the target not yet reinstated → verify both identities/hashes, finish target reinstatement, append the inverse terminal; restore rename-and-rewrite with the original restored but target cleanup pending → verify the restored original and expected target state, finish cleanup, append the inverse terminal. Enumerate every mutation step's crash-after state and pair each row with a deterministic fault-injection test. Reserve `external-interference` for states that fail all recorded identity/hash predicates.

### F6 — 🔴 Still blocking: `already-applied` cannot be a latest-wins terminal skip

**Remaining defect:** The revised design correctly requires Plan, Report(s), ManifestChain, and BackupStore and adds the full action partition. Its rule that "the latest terminal outcome per action wins" is incompatible with the current, intentional resume report contract. A completed action appears as `applied` in an earlier manifest/report and as `skipped` with reason `already-applied` in every later resume report. Treating the later report status as the terminal outcome changes a successfully applied action into `skipped` and can either contradict the manifest chain or make the partition certify the wrong state.

**Evidence:**

- Design lines 145–150 place `skipped` in the terminal partition and say the latest report outcome wins, without excluding `already-applied`.
- `src/docmend/writer/apply.py` lines 324–348 deliberately emits `skipped/already-applied` after confirming the live output matches the earlier applied record.
- `src/docmend/cli.py` lines 598–603 deliberately excludes `already-applied` from findings so a clean resume converges on exit 0.
- `tests/test_cli_resume.py::TestKillAndResume::test_kill_and_resume__corpus_matches_uninterrupted_control` and `::test_double_resume__two_manifests_chain_exit_0` prove that later reports contain one or more `already-applied` skips while earlier manifests remain the applied-coverage authority.

**Concrete fix:** Define coverage reduction with the ManifestChain lifecycle as the mutation authority. `already-applied` is a nonterminal reconciliation observation that confirms and retains the reducer's existing `applied` state; it never overrides it. Define the allowed cross-run report transitions and precedence explicitly, including `not-attempted -> applied`, retryable `failed -> applied`, and `applied -> already-applied (retain applied)`. Build the final exactly-once partition only after manifest lifecycle reduction plus those report transitions, and add the clean single-resume and double-resume cases to the F6 verification matrix.

### Round 2 Verified and Held

- The complete header/chain model now uses durable predecessor hashes rather than wall-clock ordering.
- Apply and restore records have explicit inverse linkage and immutable intent/terminal fields.
- Backup references, descriptor/pathname identity checks, artifact-root handling, ADR dispositions, error classes, and preview/write entrypoint separation are sufficiently specified for implementation planning once F4 and F6 close.
- No new conflict was found in the output ledger, BackupStore namespacing, version target, deferred-scope boundary, or testing/gate statements.

### Round 3 Re-Review Gate

The next round can be limited to two proofs:

1. The dangling-intent table covers every crash-after-step state for pure rename and each restore inverse, and each known partial state converges rather than becoming generic interference.
2. Verify reduces `already-applied` and other cross-run report transitions without overriding the ManifestChain's terminal mutation state, then proves exactly-one plan coverage over single and multiply interrupted resumes.

## Round 3 — 2026-07-10

### Verdict

Verdict: **REVISE AND RE-REVIEW**

Round 3 verified the design revision at commit `b7550ee`. The exact round-2 defects are fixed: the adjudication table now covers the known crash-after-step intermediates, and `already-applied` can no longer demote an applied lifecycle state. F4 and F6 nevertheless remain blocking on prerequisites those revisions rely on but do not define. No unrelated finding was opened, and F1/F2/F3/F5/F7/F8 remain closed.

### Round 3 Target and Method

- Target revision: commit `b7550ee` on `dev`
- Delta reviewed: 33 insertions and 16 deletions relative to round 2's `b072a64`
- Worktree note: the existing review document remained untracked; the target design itself was committed and unmodified in the worktree
- Re-verified against: Manifest 1.3's concrete fields, the proposed 2.0 additions, commit-boundary identity capture, current failed-record production, Report fields, resume behavior, and the round-2 re-review gate
- Document checks: the revised design passed scoped markdownlint and `git diff --check`

### Round 3 Disposition

| Finding | Round 3 status | Evidence |
| --- | --- | --- |
| F1 | Closed — held | The round-3 delta does not change the artifact-root guard or its tests. |
| F2 | Closed — held | Runtime descriptor/pathname binding is unchanged; F4's persistence gap concerns post-crash evidence, not the live CommitBoundary comparison. |
| F3 | Closed — held | Target descriptor backup/recheck and no-clobber absent-target publication are unchanged. |
| F4 | Open — blocking | The operation-state table is now complete, but its identity predicates are not representable by the described Manifest 2.0 records; details below. |
| F5 | Closed — held | BackupStore root/key/type/symlink/cardinality constraints are unchanged. |
| F6 | Open — blocking | Manifest authority and `already-applied` precedence are fixed, but deterministic ordering and lifecycle legality across report-only/retry attempts remain undefined; details below. |
| F7 | Closed — held | ADR dispositions and exit classifications are unchanged. |
| F8 | Closed — held | Preview/write entrypoint separation and `WriteSafetyContext` ownership are unchanged. |

### F4 — 🔴 Still blocking: restart adjudication relies on identities the manifest does not record

**Residual defect:** The new table correctly enumerates the pre-step, intermediate, and completed states of every current mutation primitive. It says those states are matched through "recorded hashes/identity" and requires re-verifying each object against the record's identities before completing a step. The described 2.0 mutation record has no device/inode identity fields. CommitBoundary captures `(st_dev, st_ino)` only in process memory, which is gone after the kill that makes adjudication necessary. A same-content pathname replacement can therefore satisfy every persisted hash/path predicate while naming a different object, and resume can adopt or unlink it despite DMR-06's object-identity contract.

**Evidence:**

- Design lines 94–96 make recorded identity a state-matching input; the both-names rows at lines 101 and 111 require inode identity.
- Lines 131–135 capture source and overwrite-target identities in the live CommitBoundary but do not route them into durable intent evidence.
- Lines 77–80 say mutation records keep the 1.3 fields and add only `undoes_action_id` and `undoes_run_id`.
- Current `src/docmend/writer/manifest.py` lines 37–75 confirms that the retained 1.3 shape has hashes and paths but no `st_dev`/`st_ino` fields.
- Hash equality is insufficient for DMR-06: its confirmed defect is that validation and mutation can bind to different filesystem objects, not merely different bytes.

**Concrete fix:** Add the pre-mutation source identity and, when present, overwrite-target identity to every intent record and its terminal immutable-field set. Define the identity fields needed by each operation and restore inverse, including how an atomic rewrite's new post-publish inode is treated. The intermediate rows must compare current names with the persisted pre-mutation identities, not only with each other. Add fault tests that kill after intent, replace a source or target with a different inode carrying identical bytes, then prove resume/restore returns `external-interference` without unlinking or adopting it.

### F6 — 🔴 Still blocking: "later" report transitions lack durable ordering and chain legality

**Residual defect:** ManifestChain-first reduction and the `already-applied` special case resolve the round-2 precedence bug. The remaining transition rules use "later run" without defining a durable order for reports that have no corresponding manifest. That case is normal: an abort on the first action can produce `skipped` plus `not-attempted` outcomes and no mutation manifest, and an all-skip retry can do the same. Reports contain timestamps and run IDs but no predecessor link. Caller order or wall-clock order would reintroduce the ambiguity the manifest chain explicitly removed. Separately, the design allows `failed -> applied` retry but its lifecycle rule still says "at most one terminal record" without saying whether that limit is per ManifestSet or across the chain.

**Evidence:**

- Design lines 163–167 define two-pass reduction and cross-run transitions but no report-chain or attempt-order field.
- The proposed report changes at lines 162 and 189 add `not_attempted` and totals/schema updates, not lineage.
- Current `src/docmend/report.py` lines 70–86 contains `run_id`, plan reference, and timestamps only; a report-only run is not orderable through `prior_manifest_sha256`.
- Design line 82 requires pre-mutation failures to append `failed`; line 165 explicitly permits a later successful retry; line 88's unqualified "at most one terminal record" can reject that valid chain or be weakened inconsistently by implementers.
- Current backup and write failure paths produce manifest `failed` records before the source is touched (`tests/test_apply.py` lines 337–395), so this is a reachable lifecycle, not a hypothetical extension.

**Concrete fix:** Give apply reports deterministic attempt lineage—such as a predecessor report hash tied to the same plan—or explicitly constrain and validate an equivalent ordering source. Bind each manifest header and report for a run in both directions, while allowing report-only attempts to occupy the chain. Then state lifecycle legality at both scopes: at most one terminal per action **within one ManifestSet**, plus an explicit cross-set transition table that permits `failed -> intent -> applied`, `not-attempted -> skipped/failed/applied`, and `applied -> already-applied`, while rejecting regressions from `applied` to a contradictory terminal state. Test shuffled input order, a first-action abort with no manifest, an all-skip report-only retry, and a failed-manifest then successful retry.

### Round 3 Verified and Held

- Every current apply and restore mutation step now has a named pre/intermediate/post crash state and deterministic completion action.
- Manifest lifecycle remains authoritative over report observations; `already-applied` correctly confirms rather than overrides `applied`.
- No regression was found in the six closed findings or the previously held output-ledger, BackupStore, versioning, deferred-scope, and gate contracts.

### Round 4 Re-Review Gate

The next round can remain limited to F4 and F6:

1. Manifest 2.0 durably stores every pre-mutation object identity the adjudication table consumes and tests same-bytes/different-inode replacement after a kill.
2. Apply reports have deterministic attempt lineage, and lifecycle legality explicitly distinguishes one-file terminal uniqueness from valid cross-attempt transitions such as failed-then-applied.

## Round 4 — 2026-07-10

### Verdict

Verdict: **REVISE AND RE-REVIEW**

Round 4 verified commit `ae29fdd`. The revision adds the requested identity and attempt-lineage fields and resolves the per-set versus cross-set terminal rule. F4 and F6 remain blocking because the new evidence is unavailable in two explicitly supported interruption cases: `published_identity` is written only in the terminal that a dangling intent lacks, and a report-only predecessor chain cannot cross an attempt whose report never published. No unrelated finding was opened; F1/F2/F3/F5/F7/F8 remain closed.

### Round 4 Target and Method

- Target revision: commit `ae29fdd` on `dev`
- Delta reviewed: 12 insertions and 11 deletions relative to round 3's `b7550ee`
- Worktree note: the existing review remained untracked; the committed design had no worktree edits
- Re-verified against: the intent-before-mutation ordering, terminal-after-mutation ordering, atomic publish identity behavior, current resume CLI inputs, report relocation, and the design's missing-report verification requirement
- Document checks: the revised design passed scoped markdownlint and `git diff --check`

### Round 4 Disposition

| Finding | Round 4 status | Evidence |
| --- | --- | --- |
| F1 | Closed — held | Artifact-root guard behavior is unchanged. |
| F2 | Closed — held | Live source identity capture/comparison is unchanged; F4 remains about durable post-crash evidence. |
| F3 | Closed — held | Live overwrite-target identity and preservation behavior is unchanged. |
| F4 | Open — blocking | Pre-mutation identities are now durable, but the post-publish identity required by dangling-intent adjudication is written only after the dangling window; details below. |
| F5 | Closed — held | BackupStore trust constraints are unchanged. |
| F6 | Open — blocking | Report lineage and cross-set transitions are defined, but the chain cannot represent or continue past the explicitly supported missing-report attempt; details below. |
| F7 | Closed — held | ADR and exit-taxonomy dispositions are unchanged. |
| F8 | Closed — held | Preview/write entrypoint separation is unchanged. |

### F4 — 🔴 Still blocking: `published_identity` is absent exactly when dangling intent needs it

**Residual defect:** Persisting `source_identity` and `target_identity` closes pre-mutation same-bytes replacement. The design stores the post-publish `published_identity` only on the terminal record, then says dangling-intent adjudication consumes it for post-publish states. A dangling intent exists because the process died after the intent and before that terminal. For rewrite and every temp-and-replace publish, the output inode is minted during staging/publication and differs from the pre-mutation source identity. After a kill following publication, the surviving manifest therefore contains no persisted identity for the published inode. Hash/path checks alone again cannot distinguish docmend's output from a same-bytes replacement by another object.

**Evidence:**

- Design line 79 allows `published_identity` to differ between intent and terminal; line 81 explicitly says terminal records add it.
- Line 83 orders the terminal after the corpus mutation.
- Line 95 says dangling-intent post-publish states consume `published_identity`, even though by definition no terminal followed the intent.
- Lines 98–119 adopt or finish post-publish states after the crash; several atomic rewrite/publish rows therefore require an identity unavailable in the surviving evidence.
- The device-renumbering exception at line 81 is also not an exact object-identity check: `(st_dev, st_ino)` is the identity pair. Accepting the same inode number on a different recorded device can match a different object while claiming not to weaken the check.

**Concrete fix:** Stage every replacement output before appending the intent, `fstat` the staged inode, and persist that expected post-publish identity in the **intent** as an immutable field; pure renames can use the persisted source identity because the inode moves rather than changes. The terminal confirms the same expected identity instead of introducing it. Define equivalent staged identities for restore inverses that publish replacement bytes. Require exact `(st_dev, st_ino)` equality; if `st_dev` changes after remount/reboot, refuse as `external-interference` or require an explicitly designed stronger persistent file-handle identity—do not silently substitute `source_root`'s current device. Add kill-after-publish-before-terminal tests with same-bytes/different-inode substitution for rewrite, rename-and-rewrite, and restore replacement paths.

### F6 — 🔴 Still blocking: the report chain cannot survive a missing report

**Residual defect:** `prior_report_sha256` orders report-only attempts and the per-set/cross-set lifecycle rules now permit failed-then-applied retry. The design also explicitly treats a manifest whose report publication was interrupted as a supported verification finding. Those requirements conflict: the next attempt cannot set `prior_report_sha256` to the previous attempt's report because that file does not exist, while setting it to the last older report skips an attempt and violates "previous attempt report." The bidirectional rule that each manifest run must match exactly one report likewise turns the intended missing-report finding into an impossible chain. The current resume interface accepts prior manifests/run IDs, not relocated prior reports, so even an existing non-sidecar report cannot be hashed reliably when constructing the next attempt.

**Evidence:**

- Design line 151 defines `prior_report_sha256` as the previous attempt report and requires each manifest run to match exactly one report.
- Line 168 explicitly supports a manifest chain with a missing report after corpus mutation and classifies it as `coverage unprovable`.
- `src/docmend/cli.py` lines 447–461 accepts only `--resume-manifest` and `--resume-run-id`; lines 440–445 allow reports to be relocated independently.
- A crash after manifest close but before report publication leaves the manifest hash available and the report hash nonexistent—the exact window line 147 moves under the lock but cannot eliminate.

**Concrete fix:** Use one attempt lineage that can point to whichever durable predecessor evidence exists, rather than a report-only chain. For example, define a discriminated `prior_attempt` reference containing the predecessor run ID plus either its report hash or, when the report is missing, its closed manifest hash; report-only attempts point to the prior report. Relax manifest↔report cardinality to at most one report per manifest run, with absence retained as a verify finding. Define how apply obtains the full predecessor attempt chain: add repeatable prior-report inputs for relocated/report-only attempts, while `--resume-run-id` resolves both default sidecars; a manifest-only predecessor remains linkable by its manifest hash. Test manifest-with-missing-report → successful resume, relocated prior report, report-only abort → retry, and shuffled input order.

### Round 4 Verified and Held

- Per-set terminal uniqueness and legal cross-set retry transitions are now explicit.
- Report-only attempts have a deterministic order when every report exists.
- Pre-mutation source and target identities are now represented in intent records.
- No regression was found in the six closed findings or the output-ledger, BackupStore, versioning, deferred-scope, and test-gate contracts.

### Round 5 Re-Review Gate

The next round remains limited to the two surviving evidence gaps:

1. The intent durably records the expected post-publish identity before mutation, with exact device/inode matching and crash tests through the pre-terminal window.
2. One attempt lineage continues across report-only, manifest-plus-report, and manifest-with-missing-report attempts, with explicit CLI discovery/input rules and missing reports remaining findings rather than structural impossibilities.

## Round 5 — 2026-07-10

### Verdict

Verdict: **REVISE AND RE-REVIEW**

Round 5 verified commit `e282fe3`. F4 is closed: every replacement output is staged and identified before intent append, the intent carries the exact expected published identity, and post-kill checks use exact device/inode equality. F6 remains the sole blocker because `prior_attempt` is still described only as a report field; a mutating attempt whose report does not publish leaves a manifest that cannot link to an immediately preceding report-only attempt. F1/F2/F3/F5/F7/F8 remain closed, and no unrelated finding was opened.

### Round 5 Target and Method

- Target revision: commit `e282fe3` on `dev`
- Delta reviewed: 10 insertions and 10 deletions relative to round 4's `ae29fdd`
- Worktree note: the existing review remained untracked; the committed design had no worktree edits
- Re-verified against: manifest header fields, intent/terminal ordering, staged atomic-publish identity, the discriminated predecessor reference, current resume inputs, report relocation, and missing-report handling
- Document checks: the revised design passed scoped markdownlint and `git diff --check`

### Round 5 Disposition

| Finding | Round 5 status | Evidence |
| --- | --- | --- |
| F1 | Closed — held | Artifact-root guard behavior is unchanged. |
| F2 | Closed — held | Live source identity binding is unchanged and now feeds durable intent identity. |
| F3 | Closed — held | Live overwrite-target identity and preservation behavior is unchanged. |
| F4 | Closed | Design lines 77–95 stage and `fstat` replacement outputs before intent append, persist `expected_published_identity` in the intent, require exact `(st_dev, st_ino)` equality, and add pre/post-publish same-bytes replacement tests. |
| F5 | Closed — held | BackupStore trust constraints are unchanged. |
| F6 | Open — blocking | The unified predecessor reference is stored only in reports, so a missing current report can erase the link to a report-only predecessor; details below. |
| F7 | Closed — held | ADR and exit-taxonomy dispositions are unchanged. |
| F8 | Closed — held | Preview/write entrypoint separation is unchanged. |

### F6 — 🔴 Still blocking: the sole surviving manifest does not carry attempt lineage

**Residual defect:** A discriminated predecessor reference can represent either a prior report or a prior manifest and the new CLI inputs can discover both. The reference is added only to apply reports. That is insufficient because a mutating attempt's report is explicitly allowed to be missing after manifest close. If the predecessor was report-only, the current manifest's `prior_manifest_sha256` has nothing to reference. When the current report then fails to publish, no surviving artifact links the current attempt to that report-only predecessor. A later attempt can reference the current manifest, but the earlier report-only attempt remains an unconnected root, so shuffled inputs cannot reconstruct the promised single attempt order.

**Evidence:**

- The manifest header example and field list at design lines 56–75 contain `prior_manifest_sha256` but no `prior_attempt`.
- Line 151 says **apply reports gain** `prior_attempt`; it does not add the same reference to apply-kind manifest headers.
- Line 151 explicitly supports report-only predecessors and manifest-with-missing-report attempts in one lineage, which requires the manifest to preserve their edge when its own report is absent.
- Line 168 keeps a missing current report as a supported `coverage unprovable` finding.
- Concrete sequence: R1 aborts before mutation and leaves report H1 only; R2 receives H1 via `--prior-report`, mutates and closes M2, then dies before H2. M2 has `prior_manifest_sha256 = null`, so the durable edge H1 → M2 is lost.

**Concrete fix:** Put the discriminated `prior_attempt` reference in every apply-kind manifest header **and** every apply report. The value is computed before mutation from the validated predecessor inputs; when both current artifacts exist, they must carry the same predecessor reference and run ID. A report-only attempt persists the edge in its report; a manifest-with-missing-report attempt persists it in its manifest; a normal attempt persists it redundantly in both. Keep `prior_manifest_sha256` as the mutation-ledger subchain link, but derive and validate that subchain against the unified attempt chain. Add the composed regression R1 report-only → R2 manifest-with-missing-report → R3 success, pass all artifacts shuffled, and prove one deterministic attempt order with the missing H2 reported as a finding rather than a broken chain.

### Round 5 Verified and Held

- F4 now covers both pre-publish and post-publish same-bytes/different-inode substitution with evidence available in the surviving intent.
- Staging before intent does not mutate a corpus name; stale randomized staging files are inert and retryable.
- F6's predecessor union, report relocation input, manifest/report cardinality, and cross-attempt lifecycle transitions are otherwise coherent.
- No regression was found in the seven closed findings or the output-ledger, BackupStore, versioning, deferred-scope, and test-gate contracts.

### Round 6 Re-Review Gate

One proof remains:

1. The same discriminated `prior_attempt` edge is persisted in the apply manifest header and report, so a report-only predecessor followed by a manifest-with-missing-report attempt remains connected and deterministically orderable.

## Round 6 — 2026-07-10

### Verdict

Verdict: **APPROVE**

Round 6 verified commit `ccaa085`. F6 is closed: the apply manifest header and apply report now persist the same precomputed `prior_attempt` edge, while `prior_manifest_sha256` remains a validated mutation-only subchain. The composed report-only → manifest-with-missing-report → successful-resume sequence therefore has one durable order even when the middle report is absent. All eight findings are closed, no new blocking or should-fix finding was identified, and this review has converged.

### Round 6 Target and Method

- Target revision: commit `ccaa085` on `dev`
- Delta reviewed: 6 insertions and 4 deletions relative to round 5's `e282fe3`
- Worktree note: the existing review remained the only untracked file; the committed design had no worktree edits
- Re-verified against: the complete design, the F1–F8 ledger, manifest/report hash direction, manifest/report cardinality, current resume and report-location surfaces, the governing SPEC-VHHB and ADR dispositions, and DMR-01 through DMR-07
- Document checks: the revised design and combined review passed scoped markdownlint, Prettier, and whitespace validation

### Round 6 Disposition

| Finding | Round 6 status | Evidence |
| --- | --- | --- |
| F1 | Closed — held | Artifact-root guard behavior and its default `.docmend/` exclusion condition are unchanged. |
| F2 | Closed — held | Source descriptor/pathname identity binding and pre-step revalidation are unchanged. |
| F3 | Closed — held | Overwrite-target identity binding, descriptor-backed preservation, and no-clobber fallback are unchanged. |
| F4 | Closed — held | Every adjudication identity remains durable in the pre-mutation intent, including the staged output identity. |
| F5 | Closed — held | BackupStore containment, key reconstruction, role validation, and no-symlink rules are unchanged. |
| F6 | Closed | Design lines 68 and 77 add `prior_attempt` to the apply manifest header and require the header/report values to be identical; lines 153 and 203 bind and test the full attempt chain, including the missing middle report. |
| F7 | Closed — held | The ADR amendments, supersession, new decisions, and exit taxonomy remain explicit. |
| F8 | Closed — held | Preview/write entrypoint separation and the sealed `WriteSafetyContext` remain explicit. |

### F6 Closure Proof

The Round 5 counterexample is now connected entirely by durable evidence:

1. R1 aborts before mutation and publishes report H1 with `prior_attempt = null`.
2. R2 receives H1, writes manifest M2 with `prior_attempt = (R1, report sha256 H1)`, mutates, closes M2, and dies before publishing H2. M2 survives with the H1 → M2 edge; because M2 is the first mutating manifest, its `prior_manifest_sha256` may remain null without losing attempt lineage.
3. R3 receives M2 and writes both M3 and H3 with the identical `prior_attempt = (R2, manifest sha256 M2)`. M3's `prior_manifest_sha256 = sha256(M2)` also extends the mutation subchain, and H3's `manifest_sha256 = sha256(M3)` binds the two R3 artifacts.

With artifacts supplied in any order, the attempt edges yield R1 → R2 → R3, the manifest edges yield M2 → M3, and the absent H2 remains the specified `coverage unprovable` finding rather than disconnecting either chain. The new composed regression at design line 203 makes this exact proof executable.

### Round 6 Verified and Held

- The seven findings closed before this round remain closed under the complete revised design.
- F6's attempt chain and mutation subchain agree without requiring a report for every mutating attempt.
- The design remains scoped to the safety-core remediation and defers binding contract changes to the required SPEC-VHHB and ADR updates before implementation.
- No 🔴 blocking or 🟡 should-fix findings remain. The specification review is converged.
