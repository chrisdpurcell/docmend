# Safety-Core Plan B Manifest 2.0 Review

## Executive Summary

The plan needs major correction before execution. Five blocking defects would either prevent imports, weaken the backup trust boundary, break report-only attempt lineage, or leave mandatory recovery behavior insufficiently tested.

No internet research was required. The controlling design, ADRs, source tree, and validation gate supplied authoritative local evidence.

## Verdict

Verdict: **NEEDS MAJOR CORRECTION BEFORE EXECUTION**

## Audit Loop Status

- Audit type: First audit
- Plan path: `docs/superpowers/plans/2026-07-10-safety-core-b-manifest-2.md`
- Pinned state: commit `990b5dc` on `dev`; worktree clean at review start
- Significant findings remaining: Yes
- Blocking issue count: 5
- Non-blocking issue count: 2

## What the Plan Gets Right

The plan correctly adopts Manifest 2.0's header-first format, intent-before-mutation journaling, deterministic hash-linked ordering, durable identity evidence, lifecycle reduction, and clean rejection of 1.x manifests. The apply adjudication coverage and exit-code taxonomy broadly match the approved design.

## Adversarial Review Performed

The review checked:

- All 15 tasks against the approved safety-core design and ADR-0019.
- Proposed module ownership against the current Python import graph.
- Backup-path validation against the complete BackupStore trust boundary.
- Attempt-lineage handling against report-only, manifest-only, and normal predecessor shapes.
- Commit checkpoints against the repository's actual full gate.
- Apply and restore crash-window coverage against every adjudication-table row.
- CLI option shapes, report/manifest constructors, relevant tests, and the clean working tree.

No mutating validation or implementation commands were run.

## Round Ledger

| Finding | Severity | Round 1 status | Required closure evidence |
| --- | --- | --- | --- |
| CR-001 | Blocking | Open | Shared wire models have dependency-neutral ownership and clean-process import tests pass. |
| CR-002 | Blocking | Open | ManifestSet enforces every F5 BackupStore filesystem predicate before opening a backup. |
| CR-003 | Blocking | Open | Every retained commit checkpoint can pass `scripts/check.py`. |
| CR-004 | Blocking | Open | Report-only, manifest-only, normal, and relocated predecessor attempts are accepted and validated correctly. |
| CR-005 | Blocking | Open | Every restore adjudication row and replacement-identity probe has deterministic crash coverage. |
| CR-006 | Should fix | Open | Attempt-lineage edges and the manifest subchain cannot disagree. |
| CR-007 | Should fix | Open | The superseding manifest recovery ADR is identified as ADR-0019. |

## Blocking Issues

### CR-001: Proposed model ownership creates two circular imports

- Severity: High
- Status: Confirmed
- Adversarial angle: Can the modules import after Tasks 7 and 10?
- Plan reference: Tasks 1, 7, and 10.
- Finding: `ObjectIdentity` is owned by `writer.manifest`, while Task 7 instructs `writer.atomic` to import it. But `writer.manifest` already imports `fsync_dir` from `writer.atomic`. Task 10 similarly places `PriorAttempt` in `writer.manifest` and requires `report.py` to use it, while `manifest.py -> artifacts.py -> report.py` already forms the opposite dependency.
- Repository evidence: `src/docmend/writer/manifest.py:25-30` imports both `artifacts` and `writer.atomic`; `src/docmend/artifacts.py:37-40` imports `Report`; the proposed ownership is stated in plan lines 26-31.
- External research evidence: Not applicable.
- Why it matters: Tasks 7 and 10 can make package imports fail before tests or CLI startup.
- Recommended action: Move shared wire primitives such as `ObjectIdentity` and `PriorAttempt` into a dependency-neutral model module, or redesign the dependencies so neither `atomic.py` nor `report.py` imports `manifest.py`.
- Suggested validation: Add a clean-process import smoke test covering `docmend.artifacts`, `docmend.report`, `docmend.writer.atomic`, and `docmend.writer.manifest`.

### CR-002: ManifestSet omits mandatory BackupStore trust checks

- Severity: High
- Status: Confirmed
- Adversarial angle: Can a crafted manifest redirect restore through a symlink or non-regular backup?
- Plan reference: Task 4, especially line 195.
- Finding: The plan validates reconstruction and role consistency, but omits three binding checks: the backup must be a regular file, no component below `backup_root` may be a symlink, and there may be at most one path per role per action.
- Repository evidence: The approved design requires all three checks before opening a backup at `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md:48-52`. Task 4's rule list at plan lines 185-226 does not include them.
- External research evidence: Not applicable.
- Why it matters: Restore treats operator-supplied manifests as recovery authority. Path reconstruction alone does not close symlink-component or special-file attacks.
- Recommended action: Add all F5 checks to `read_manifest_set`, classify failures as containment refusals, and ensure they run before `_verified_backup` reads anything.
- Suggested validation: Test a symlinked intermediate directory, symlink leaf, directory/FIFO backup leaf, duplicate role reference, and a valid regular backup.

### CR-003: Several commits are explicitly permitted with a failing full gate

- Severity: High
- Status: Confirmed
- Adversarial angle: Is the task sequence executable under its own commit rules?
- Plan reference: Global Constraint line 20; Tasks 2-7.
- Finding: The plan mandates `scripts/check.py` before every commit, but Task 2 says the full suite need not be green, Task 4 permits known-red CLI tests, and Tasks 3, 5, 6, and 7 prescribe only narrow tests before committing.
- Repository evidence: The contradiction appears at plan lines 20, 164-165, 182-183, 225-226, 243-244, 261-262, and 278-279. `scripts/check.py:19-25` runs formatting, lint, strict typing, the entire test suite with coverage, and dependency audit.
- External research evidence: Not applicable.
- Why it matters: An executor cannot both follow the stated commit policy and follow the task checkpoints.
- Recommended action: Regroup Tasks 1-7 into green vertical slices, defer their commits until dependent consumers are updated, or explicitly define a reviewed exception to the per-commit gate.
- Suggested validation: Run the complete gate immediately before every retained commit checkpoint.

### CR-004: Report-only predecessor attempts cannot be resumed as planned

- Severity: High
- Status: Confirmed
- Adversarial angle: Does lineage work when a predecessor produced a report but no manifest?
- Plan reference: Tasks 9 and 11.
- Finding: Task 9 replaces manifest-record loading with `read_manifest_chain`, while Task 11 leaves `_resume_manifest_paths` unchanged and only derives `prior_attempt` from a resume predecessor's report "when it exists." There is no step to resolve, read, validate, or accept a report-only predecessor when its manifest does not exist.
- Repository evidence: `src/docmend/cli.py:660-675` currently derives only manifest filenames. The approved design at `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md:151-170` requires `--resume-run-id` to resolve both sidecars and supports report-only predecessors. Task 11's tests at plan lines 389-405 cover only a predecessor manifest.
- External research evidence: Not applicable.
- Why it matters: The required `report-only -> manifest-with-missing-report -> success` lineage cannot be constructed, so one of the design's principal interruption shapes remains unsupported.
- Recommended action: Define predecessor-attempt loading separately from mutation-manifest loading. Resolve and validate both default sidecars for `--resume-run-id`, support relocated/report-only predecessor reports, and allow an empty ManifestChain when the immediate predecessor is report-only.
- Suggested validation: Add first-action abort, all-skip report-only retry, relocated report, manifest-only predecessor, and the composed three-attempt regression.

### CR-005: Restore does not receive the mandatory per-row crash matrix

- Severity: High
- Status: Confirmed
- Adversarial angle: Could restore convergence appear green while several crash states remain wrong?
- Plan reference: Tasks 9 and 12.
- Finding: Task 9 specifies one test per apply adjudication row. Task 12 adds only one interrupted multi-step restore inverse. It does not require one kill-after-step test for every restore-inverse row or the same-bytes/different-inode probes for restore replacement paths.
- Repository evidence: The approved design requires one deterministic test for every apply and restore adjudication row at `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md:194-203`. Task 12's narrower test list is at plan lines 407-427.
- External research evidence: Not applicable.
- Why it matters: Restore is the disaster-recovery path; incomplete crash-window coverage could let non-convergent or destructive intermediate states pass the full suite.
- Recommended action: Enumerate every restore adjudication row explicitly and add the restore replacement identity-substitution probes.
- Suggested validation: Parameterize tests directly from a named table of restore operation, crash step, disk state, expected verdict, and convergence result.

## Non-Blocking Issues

### CR-006: Cross-set attempt-link validation is underspecified

- Severity: Medium
- Status: Confirmed
- Adversarial angle: Can the manifest subchain disagree with the attempt chain?
- Plan reference: Task 5.
- Finding: Task 5 checks only that `prior_attempt.run_id` matches the preceding set. It does not require the edge when appropriate, validate a `manifest_sha256` edge against the actual predecessor hash, reject inconsistent root edges, or validate that `prior_manifest_sha256` identifies the newest manifest in the attempt lineage.
- Repository evidence: The stronger invariant is specified at `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md:76-77` and `:151-170`; Task 5's proposed rule is at plan lines 228-244.
- External research evidence: Not applicable.
- Why it matters: A chain can be structurally hash-linked while carrying contradictory attempt metadata, undermining later verify ordering.
- Recommended action: State complete per-kind root/successor invariants and validate every locally provable hash relationship. Defer only relationships that genuinely require report inputs.
- Suggested validation: Add crafted wrong-hash, missing-edge, self-run, duplicate-run, and subchain/attempt-chain disagreement fixtures.

### CR-007: The superseding ADR number is incorrect

- Severity: Low
- Status: Confirmed
- Adversarial angle: Does the plan point implementers to the governing decision?
- Plan reference: Global Constraint line 13.
- Finding: The plan says ADR-0020 supersedes ADR-0006. The Manifest 2.0 recovery decision is ADR-0019; ADR-0020 governs commit-boundary object identity.
- Repository evidence: `docs/adr/adr-0019-manifest-2-recovery-model.md:27-29` declares the supersession; `docs/adr/adr-0020-commit-boundary-object-identity.md:1-5` is a different decision.
- External research evidence: Not applicable.
- Why it matters: It can route implementation questions to the wrong contract.
- Recommended action: Replace `adr-0020` with `adr-0019` in the global constraint.
- Suggested validation: Check all ADR references against filenames and frontmatter IDs.

## Missing Considerations

- Blocking: A dependency-neutral home for shared wire types.
- Blocking: The complete BackupStore filesystem trust-boundary algorithm and tests.
- Blocking: Explicit report-only predecessor discovery and validation.
- Blocking: Exhaustive restore-inverse crash and identity-substitution coverage.
- Non-blocking: Complete attempt-chain versus manifest-subchain invariants.
- Non-blocking: A commit structure that remains green at every required checkpoint.

## Internet Research Performed

No internet research was necessary. The disputed behaviors are governed by repository-local design decisions and directly observable Python imports, CLI declarations, and validation scripts.

## Items to Verify Before Correcting the Plan

- Whether shared wire models belong in a new neutral module or an existing model module.
- Which layer owns validation of predecessor reports before mutation.
- Whether restore headers should carry `backup_root=null` or copy another set's root; the plan should make this match the header's documented per-run meaning.
- Exactly which attempt-lineage invariants Plan B must enforce and which are deliberately deferred to Plan D.
- Whether each proposed commit can satisfy `scripts/check.py` without temporary compatibility shims.

## Required Plan Corrections

1. Relocate `ObjectIdentity` and `PriorAttempt` to eliminate both circular imports.
2. Add every F5 backup trust-boundary predicate and adversarial fixture.
3. Recut Tasks 1-7 into green, committable vertical slices.
4. Define report and manifest predecessor discovery as separate inputs.
5. Add report-only and relocated-report lineage tests.
6. Expand Task 12 to cover every restore adjudication row and identity probe.
7. Strengthen Task 5's attempt/subchain validation rules.
8. Correct the ADR-0019 reference.

## Read-Only Validation Performed

- Inspected the current branch, recent commits, clean worktree, and plan tracking state.
- Read the complete target plan and adversarial plan-audit protocol.
- Compared the plan with the approved safety-core design and ADRs 0019-0021.
- Inspected the import graph across `artifacts.py`, `report.py`, `manifest.py`, and `atomic.py`.
- Inspected current apply/resume/restore CLI options and sidecar resolution.
- Inspected BackupStore key construction and manifest/report constructors.
- Inspected `scripts/check.py` and every proposed commit checkpoint.
- Searched the plan for backup trust checks, report-only handling, lineage validation, and crash-matrix coverage.
- Reconfirmed `dev` remained clean with no diff.

## Recommended Implementation Validation

Run only after correcting and implementing the plan:

1. `uv run python scripts/check.py`
2. Clean-process import smoke tests for the affected modules.
3. Manifest adversarial-fixture suite, including backup symlink/special-file cases.
4. Full apply and restore kill-after-step matrix.
5. Composed report-only to manifest-only to successful-resume lineage regression.
6. `npx prettier --check .`
7. `npx markdownlint-cli2 "**/*.md"`
8. `uv run python scripts/check_traceability.py`
9. The repository's pinned Project Standards spec validation command.

## Final Recommendation

Revise the plan using the findings above, then run a second audit round that preserves the CR identifiers.

## Review Ledger for Next Loop

- Plan path: `docs/superpowers/plans/2026-07-10-safety-core-b-manifest-2.md`
- Audit round: 1
- Open issue IDs: CR-001, CR-002, CR-003, CR-004, CR-005, CR-006, CR-007
- Resolved issue IDs: None
- Superseded issue IDs: None
- Significant findings remaining: Yes
- Next audit should focus on import-layer ownership, complete BackupStore validation, report-only attempt lineage, green commit boundaries, and exhaustive restore crash coverage.

## Round 2 — 2026-07-11

### Verdict

Verdict: **NEEDS MAJOR CORRECTION BEFORE EXECUTION**

Round 2 reviewed commit `7928266` against Round 1's `990b5dc`. The revision closes CR-001, CR-002, CR-005, and CR-007. CR-003 remains open; CR-004 and CR-006 are only partially resolved. Four new findings remain, including two blocking contradictions in lifecycle and report-only recovery.

### Round 2 Target and Method

- Target revision: commit `7928266` on `dev`, synchronized with `origin/dev`
- Delta reviewed: 210 insertions and 214 deletions relative to Round 1's `990b5dc`
- Worktree note: this review report remained the sole untracked file
- Prior audit issue count: 7
- Resolved issue count: 4
- Still-open issue count: 1
- Partially resolved issue count: 2
- New issue count: 4
- Regression count: 2
- Significant findings remaining: Yes
- Re-verified against: the approved safety-core design, ADRs 0019-0021, every current `read_manifest` consumer, current resume CLI options, restore inverse construction, and the repository's full gate
- Live checks: Git status/history and revision diff; current manifest/report constructor and consumer inventory; scoped Prettier and markdownlint checks

### Prior Finding Disposition

| Finding | Round 2 status | Evidence |
| --- | --- | --- |
| CR-001 | Resolved | Shared types move to dependency-neutral `docmend.lineage`, with a clean-process import test and restricted import contract. |
| CR-002 | Resolved | Task 2 now requires exact key reconstruction, regular-file checks, component-wise symlink refusal, role consistency, role uniqueness, and six adversarial fixtures. |
| CR-003 | Still open | Task 2 still cannot finish green: it omits live `read_manifest` consumers and enables strict intent-before-applied validation before all producers journal intents. |
| CR-004 | Partially resolved | Separate report discovery, `--prior-report`, empty-chain handling, and the composed lineage test land, but the root invariant, explicit manifest inputs, and deterministic predecessor selection remain inconsistent. |
| CR-005 | Resolved | Task 10 enumerates all eleven restore adjudication rows and the restore identity-substitution probes. |
| CR-006 | Partially resolved | Manifest-flavored edges and local hash invariants are stronger, but report/manifest attempt ordering and report binding remain incomplete. |
| CR-007 | Resolved | Global Constraints now correctly identify ADR-0019 and distinguish ADR-0020's Plan C scope. |

### CR-003 — Still open: the format-break slice cannot satisfy its full-gate promise

**Evidence:**

- Task 2 deletes `read_manifest`, but its affected-file list and staging command omit current consumers in `tests/test_apply.py`, `tests/test_cli_resume.py`, `tests/test_idempotency.py`, `tests/test_schemas.py`, and the verify CLI path.
- Task 2 makes `read_manifest_set` reject any `applied` record without a preceding intent in the same set. Journal-every-mutation does not land until Task 6, so the existing rewrite and rename producers create manifests the new reader rejects.
- The global green-slice rule is therefore correct in intent but not executable with the stated Task 2 scope.

**Required correction:** Include every current consumer in the format-break slice and either move journal-every-mutation into that slice or delay the strict lifecycle rule until every producer emits intent records.

### CR-004 — Partially resolved: report-only lineage still contradicts chain validation

**Evidence:**

- Task 3 requires the root manifest to carry both `prior_attempt: null` and `prior_manifest_sha256: null`.
- Task 9's principal report-only sequence requires R2, the first manifest after report-only R1, to have `prior_manifest_sha256: null` and a non-null report-flavored `prior_attempt` naming R1.
- `_load_predecessor_attempt(resume_run_ids, prior_reports)` does not consume the existing repeatable `--resume-manifest` paths.
- The plan does not define how “newest predecessor” is derived from lineage when multiple run IDs, reports, and explicit manifests are supplied.

**Required correction:** Permit a first manifest to carry a report-flavored attempt edge with no prior manifest, integrate explicit manifest inputs, and derive the predecessor tip from validated lineage rather than caller order.

### CR-006 — Partially resolved: attempt-chain validation remains incomplete

**Evidence:**

- Task 3 now validates actual manifest hashes, duplicate run IDs, manifest-flavored attempt edges, and locally provable subchain invariants.
- Task 9 validates predecessor reports only for schema parsing and `run_id`; it does not bind `plan_ref.sha256` to the current plan, reconcile the report's `manifest_sha256` with supplied manifests, or validate the report's own `prior_attempt` edge.
- Multiple supplied reports and manifests still lack one deterministic combined attempt-order algorithm.

**Required correction:** Define one combined report/manifest attempt graph and validate every report field available during apply-resume. Defer only checks that genuinely require Plan D's complete verify input set.

### New Blocking Findings

#### CR-NEW-001: Missing mutation manifests are misclassified as report-only attempts

**Defect:** Task 9 says to delete a predecessor manifest, retain its report, and then treat the attempt as report-only with an empty mutation chain. A legitimate report-only attempt has `report.manifest_sha256 == null` because it performed no mutations. A report with a non-null manifest hash whose manifest is absent is missing mutation evidence, not a report-only attempt.

**Evidence:**

- The approved design defines report `manifest_sha256` as the closed manifest's hash, null only when the attempt mutated nothing.
- Task 9 validates only report schema and `run_id`; it does not require null `manifest_sha256` before accepting an empty chain.
- Task 9's test explicitly says “delete the predecessor manifest, keep its report,” which can erase the reducer's mutation authority and allow actions to execute again.

**Impact:** A lost or deleted mutation manifest can be mistaken for evidence that no mutation occurred, permitting duplicate or unsafe re-execution.

**Concrete fix:** Accept a report-only predecessor only when the report has `manifest_sha256: null` and no outcome that requires mutation evidence. Reject a report with a non-null manifest hash unless the matching manifest is supplied and validates. Test a genuine first-action abort separately from a missing mutation manifest; only the first may use an empty chain.

#### CR-NEW-002: Per-set validation makes adjudication terminals unreadable

**Defect:** Task 2 rejects any `applied` record without a preceding intent in the same set. Task 7's `completed` and `finish-remaining` branches append only the missing terminal in a later set. `read_manifest_set` rejects that later set before Task 3 can prove it closes an earlier dangling intent.

**Evidence:**

- Task 2 line 177 requires an intent before every applied terminal within the same set.
- Task 7 line 344 appends a standalone missing terminal after adjudicating an earlier set's dangling intent.
- Task 4's M4 worked example likewise starts by completing M3's dangling restore intent before it journals the next inverse.

**Impact:** The primary interrupted-resume and interrupted-restore convergence paths generate manifests their own reader rejects.

**Concrete fix:** Choose one coherent wire rule and reconcile it with the approved design. The likely model is for `read_manifest_set` to provisionally accept a standalone terminal and for `read_manifest_chain` to require that it close exactly one matching prior dangling intent. Add isolated-set rejection and valid-chain-closure tests for both apply and restore terminals.

### New Non-Blocking Findings

#### CR-NEW-003: Restore header `backup_root` contradicts the approved header meaning

**Defect:** Task 10 copies the apply chain's `backup_root` into the restore header even though the restore run takes no backups and its inverse records have null backup references.

**Evidence:**

- The approved design says `backup_root` is the run's resolved tool backup root, null when the run took no tool backups.
- Current restore inverse construction clears `backup_path` and `overwritten_backup_path`.
- Original apply sets already retain the anchors for every backup restore reads; copying that root into a restore set does not establish a new per-run backup relationship.

**Concrete fix:** Set restore headers to `backup_root: null`, or formally amend the approved contract before redefining the field as an inherited read dependency. Add a direct restore-header assertion.

#### CR-NEW-004: The pushed plan links to an untracked review artifact

**Defect:** Commit `7928266` is synchronized with `origin/dev` and links to this Round 1 review, but this review file remains untracked.

**Impact:** The revision-evidence link is broken for remote readers.

**Concrete fix:** Track this review artifact with the eventual plan-review correction commit. Confirm with `git ls-files --error-unmatch`.

### Regressions

1. CR-NEW-001: The report-only correction conflates legitimate no-manifest attempts with lost mutation manifests.
2. CR-NEW-002: The stricter per-set lifecycle rule explicitly rejects the standalone terminals required by the revised adjudication workflow.

### Round 3 Gate

Round 3 should preserve all CR identifiers and confirm:

1. CR-001, CR-002, CR-005, and CR-007 remain closed.
2. Task 2 names and updates every current `read_manifest` consumer and can pass the full gate without relying on Task 6.
3. Genuine report-only attempts are distinguished from reports whose mutation manifest is missing.
4. A first manifest after a report-only attempt is legal and carries the correct report-flavored edge.
5. Explicit manifests, run IDs, and relocated reports form one deterministic lineage independent of caller order.
6. Standalone adjudication terminals are rejected as isolated evidence but accepted when the full chain proves they close a prior dangling intent.
7. Restore-header `backup_root` matches the approved per-run contract.
8. This review file is tracked so the plan's revision link resolves remotely.

### Round 2 Review Ledger

- Plan path: `docs/superpowers/plans/2026-07-10-safety-core-b-manifest-2.md`
- Audit round: 2
- Open issue IDs: CR-003, CR-004, CR-006, CR-NEW-001, CR-NEW-002, CR-NEW-003, CR-NEW-004
- Resolved issue IDs: CR-001, CR-002, CR-005, CR-007
- Superseded issue IDs: None
- Significant findings remaining: Yes
- Next audit should focus on a genuinely green format-break slice, safe distinction between report-only and missing-manifest attempts, readable cross-set adjudication terminals, deterministic combined attempt ordering, and restore-header semantics.

## Round 3 — 2026-07-11

### Verdict

Verdict: **NEEDS MAJOR CORRECTION BEFORE EXECUTION**

Round 3 reviewed commit `50f3e36` against Round 2's `7928266`. The revision closes CR-003, CR-004, CR-NEW-001, CR-NEW-003, and CR-NEW-004 at the plan level. CR-NEW-002 is only partially resolved because the selected provisional-terminal model still conflicts with the approved design. CR-006 is substantially improved but needs one explicit no-gap invariant. One new blocking green-slice finding, CR-NEW-005, remains in the Report 2.0 task.

### Round 3 Target and Method

- Target revision: commit `50f3e36` on `dev`, synchronized with `origin/dev`
- Delta reviewed: 22 plan insertions and 18 plan deletions relative to Round 2, plus the tracked Round 1-2 review artifact
- Worktree at audit start: clean
- Prior open issue count: 7
- Resolved this round: 5
- Partially resolved this round: 2
- New issue count: 1
- Significant findings remaining: Yes
- Re-verified against: the approved safety-core design, ADR-0019, every current manifest and report constructor, current test-file inventory, and the repository's per-commit full-gate rule
- Live checks: Git status/history and revision diff; exact Task 2, Task 3, Task 8, Task 9, and Task 10 text; current `read_manifest`, `Report`, and `ReportTotals` call sites

### Prior Finding Disposition

| Finding | Round 3 status | Evidence |
| --- | --- | --- |
| CR-001 | Remains resolved | Dependency-neutral `lineage.py` ownership and clean-process import coverage remain unchanged. |
| CR-002 | Remains resolved | The complete F5 trust-boundary rules and adversarial fixtures remain unchanged. |
| CR-003 | Resolved | Task 2 now names all three CLI reader call sites, every current `read_manifest` test consumer, and a provisional set rule that keeps pre-Task-6 producers readable. |
| CR-004 | Resolved | Report-flavored root edges are legal; explicit manifests join the graph; graph-derived tip selection replaces caller order. |
| CR-005 | Remains resolved | The complete restore crash matrix and identity probes remain unchanged. |
| CR-006 | Partially resolved | Report and manifest nodes now share one graph with plan/hash reconciliation, but the graph does not explicitly reject a non-null edge whose predecessor artifact was not supplied. |
| CR-007 | Remains resolved | ADR ownership remains correct. |
| CR-NEW-001 | Resolved | Genuine report-only attempts and missing mutation manifests are separate classes and tests. |
| CR-NEW-002 | Partially resolved | Set/chain mechanics are coherent, but the approved design still says every same-set `applied` requires a preceding intent. |
| CR-NEW-003 | Resolved | Restore headers now carry `backup_root: null`, with a direct assertion. |
| CR-NEW-004 | Resolved | The review artifact is tracked in commit `50f3e36`; the plan's link now resolves remotely. |

### CR-003 — Resolved: the format-break slice is mechanically complete

Task 2 now identifies all three live CLI `read_manifest` call sites and all current test consumers, including the previously omitted apply, resume CLI, idempotency, schema, and verify surfaces. Its explicit-file commit command matches that inventory. The provisional set rule lets existing single-terminal rewrite and rename producers remain readable until Task 6 adds intents, so the Task 2 full-gate checkpoint is achievable as planned.

### CR-004 — Resolved: report-only ancestry and explicit manifests share one graph

Task 3 now permits a root manifest with a report-flavored `prior_attempt` and null `prior_manifest_sha256`. Task 9 accepts explicit manifests, run-ID-derived sidecars, and relocated reports as graph nodes, then selects one tip from graph edges rather than caller order. The shuffled-input, ambiguous-tip, relocated report, explicit-manifest, and composed three-attempt tests cover the original finding.

### CR-006 — Partially resolved: the attempt graph needs an explicit no-gap rule

**Resolved aspects:**

- Reports bind to the current plan hash.
- A report's non-null `manifest_sha256` must match a supplied manifest.
- Report and manifest artifacts for one run must agree on `run_id` and `prior_attempt`.
- Tip selection is graph-derived and ambiguous tips fail closed.

**Remaining defect:** Task 9 does not explicitly say that every non-null `prior_attempt` edge must resolve to exactly one supplied report or manifest node. A node whose edge names an absent report-only predecessor can still be the unique unreferenced tip under the stated algorithm. “Its own `prior_attempt` enters the graph and must be consistent” is not a complete no-gap predicate, and the test list has no missing-ancestor case.

**Required correction:** State that every non-null edge must resolve by both artifact hash and `run_id` to exactly one supplied node; reject zero or multiple matches. Add a manifest whose report-flavored predecessor is absent and assert exit 2 before mutation.

### CR-NEW-001 — Resolved: report-only and missing-manifest attempts are distinct

Task 9 now accepts an empty mutation chain only when the report has `manifest_sha256: null` and zero applied outcomes. A report with a non-null manifest hash requires the matching supplied manifest and exact hash equality; otherwise apply exits 2 with a missing-mutation-evidence error. The plan now requires separate tests for the genuine first-action-abort and deleted-manifest cases.

### CR-NEW-002 — Partially resolved: the wire model works, but change control is incomplete

**Technical closure:** Task 2 provisionally accepts a same-set standalone terminal. Task 3 then requires that terminal to close exactly one earlier dangling intent with full immutable-field agreement. Isolated standalone terminals fail. Apply and restore closure pairs both receive explicit tests.

**Remaining defect:** The approved design still states that, within one ManifestSet, `applied` requires a preceding intent. The revised plan instead makes standalone terminals legal at set scope and moves strict proof to chain scope. This is a sensible resolution of the design's worked-example tension, but it is a contract change, not merely an implementation detail.

**Evidence:**

- Approved design, ManifestSet rules: `applied` requires a preceding intent within one set.
- Revised Task 2: a terminal with no same-set intent is provisionally legal.
- Revised Task 3 and Task 7 depend on that changed rule for adjudication terminals.

**Impact:** Implementing the plan would leave the approved design and the actual ManifestSet validator stating different lifecycle contracts.

**Concrete fix:** Amend the approved design's per-set lifecycle paragraph to state provisional standalone-terminal parsing plus mandatory chain-scope closure, and record the clarification in the plan revision note. If the owner does not approve that amendment, redesign the wire representation so adjudication terminals satisfy the existing per-set rule without inventing a post-mutation intent.

### CR-NEW-003 — Resolved: restore headers use the per-run backup-root meaning

Task 10 now sets `backup_root: null` for restore runs, retains original apply sets as the authority for backups restore reads, and adds a direct header test. This matches the approved design and current inverse-record shape.

### CR-NEW-004 — Resolved: the review artifact is tracked

`git ls-files` now identifies this review path, and commit `50f3e36` carries the plan correction and review record together. The plan's revision link is no longer broken remotely.

### New Blocking Finding

#### CR-NEW-005: Task 8 omits live Report 2.0 constructors and cannot pass its full gate

**Defect:** Task 8 makes `ReportTotals.not_attempted` a required field and adds the Report 2.0 lineage fields, then promises a full gate before commit. Its affected-file list does not include every live constructor that must change.

**Evidence:**

- `src/docmend/cli.py::_write_refusal_report` directly constructs both `Report` and `ReportTotals`; Task 8 does not modify `cli.py` until Task 9.
- `tests/test_report_artifact.py` directly constructs Report models and totals.
- `tests/test_verify.py` directly constructs Report models and totals.
- `tests/test_schemas.py::_minimal_report` must gain the required 2.0 wire members.
- Task 8 names only `report.py`, the report schema, `artifacts.py`, `apply.py`, `tests/test_apply.py`, and the vague phrase “the report/schema test homes.” It neither names `cli.py` nor provides an explicit staging list.

**Impact:** Following Task 8 literally leaves `_write_refusal_report` and multiple tests constructing invalid Report 2.0 objects, so the mandatory full gate fails before Task 9 can repair the CLI.

**Concrete fix:** Add `src/docmend/cli.py`, `tests/test_report_artifact.py`, `tests/test_verify.py`, and `tests/test_schemas.py` to Task 8's affected files and explicit commit scope. Update every constructor with `not_attempted=0`, `prior_attempt=None`, and `manifest_sha256=None` as appropriate. Add one first-action refusal/report-only assertion proving the emitted report carries the complete 2.0 shape.

### Regressions

None found. The remaining CR-NEW-002 defect is a missing contract amendment, not a regression in the revised technical mechanism.

### Round 4 Gate

Round 4 should preserve all identifiers and confirm:

1. CR-001 through CR-005 and CR-007 remain resolved.
2. Every non-null attempt edge resolves to exactly one supplied graph node; a missing report-only ancestor fails closed.
3. The approved design states the same provisional-set/strict-chain lifecycle rule as Tasks 2, 3, and 7, with owner approval recorded where required.
4. Task 8 names and stages every live Report 2.0 constructor and can pass the full gate before Task 9.
5. CR-NEW-001, CR-NEW-003, and CR-NEW-004 remain resolved.

### Round 3 Review Ledger

- Plan path: `docs/superpowers/plans/2026-07-10-safety-core-b-manifest-2.md`
- Audit round: 3
- Open issue IDs: CR-006, CR-NEW-002, CR-NEW-005
- Resolved issue IDs: CR-001, CR-002, CR-003, CR-004, CR-005, CR-007, CR-NEW-001, CR-NEW-003, CR-NEW-004
- Superseded issue IDs: None
- Significant findings remaining: Yes
- Next audit should focus on attempt-graph no-gap enforcement, approved lifecycle-contract alignment, and a complete Report 2.0 green slice.

## Round 4 — 2026-07-11

### Verdict

Verdict: **NO SIGNIFICANT FINDINGS REMAIN**

Round 4 reviewed commit `aec43d0` against Round 3's `50f3e36`. CR-006, CR-NEW-002, and CR-NEW-005 are closed. All earlier closures remain intact, no new significant findings were introduced, and the implementation-plan audit/fix loop can stop.

### Round 4 Target and Method

- Target revision: commit `aec43d0` on `dev`, synchronized with `origin/dev`
- Delta reviewed: 19 plan lines and 4 approved-design lines changed relative to Round 3
- Worktree at audit start: only the preserved, uncommitted Round 3 review appendix in this file
- Prior open issue count: 3
- Resolved issue count: 3
- Still-open issue count: 0
- Partially resolved issue count: 0
- New issue count: 0
- Regression count: 0
- Significant findings remaining: No
- Re-verified against: SPEC-VHHB FR-013/DR-004 and change-control text, ADR-0019's two-scope lifecycle decision, the amended safety-core design, the complete Report/ReportTotals constructor inventory, and the plan's full-gate commit slices
- Live checks: Git status/history and revision diff; scoped Prettier and markdownlint on the revised plan and design; `git diff --check`; exact call-site inventory for Report 2.0

### Finding Disposition

| Finding | Round 4 status | Closure evidence |
| --- | --- | --- |
| CR-001 | Remains resolved | Shared lineage types remain dependency-neutral with clean-process import coverage. |
| CR-002 | Remains resolved | The complete F5 trust boundary and adversarial fixtures remain in Task 2. |
| CR-003 | Remains resolved | The format-break slice retains the complete reader/fixture inventory and a green intermediate lifecycle rule. |
| CR-004 | Remains resolved | Report-only roots, explicit manifests, relocated reports, and graph-derived ordering remain first-class. |
| CR-005 | Remains resolved | The complete restore crash matrix and identity probes remain unchanged. |
| CR-006 | Resolved | Every non-null attempt edge must now resolve by both hash and `run_id` to exactly one supplied node; zero/multiple matches fail before mutation, with a missing-ancestor test. |
| CR-007 | Remains resolved | ADR-0019 remains the recovery-model owner. |
| CR-NEW-001 | Remains resolved | Genuine report-only attempts remain distinct from missing mutation manifests. |
| CR-NEW-002 | Resolved | The approved design now states the same provisional-set/strict-chain terminal rule as Tasks 2, 3, and 7; ADR-0019 and SPEC-VHHB remain compatible. |
| CR-NEW-003 | Remains resolved | Restore headers retain `backup_root: null`. |
| CR-NEW-004 | Remains resolved | The canonical review artifact remains tracked. |
| CR-NEW-005 | Resolved | Task 8 now names, updates, tests, and explicitly stages every live Report 2.0 constructor. |

### CR-006 — Resolved: the attempt graph fails closed on missing ancestors

Task 9 now requires every non-null lineage edge to resolve by both artifact hash and `run_id` to exactly one supplied graph node. Zero matches, including a missing report-only ancestor, and multiple matches exit 2 before mutation. The test list adds the exact missing-ancestor reproduction from Round 3 while retaining shuffled-order, ambiguous-tip, plan-hash, relocated-report, manifest-only, and composed-lineage coverage.

### CR-NEW-002 — Resolved: design, ADR, spec, and plan now agree

The approved design's ManifestSet paragraph now states provisional parsing of a terminal without a same-set intent and mandatory chain-scope proof that it closes exactly one earlier dangling intent with immutable-field agreement. Unclosed standalone terminals remain illegal. This matches Tasks 2, 3, and 7, the adjudication table, and the M4 worked example.

ADR-0019 already defines per-set terminal uniqueness plus a cross-set transition table rather than the superseded same-set-only restriction. SPEC-VHHB requires two-scope lifecycle validation and intent-before-mutation journaling but does not contradict the clarified parsing/closure split. No additional specification revision is required for this internal-consistency clarification.

### CR-NEW-005 — Resolved: Report 2.0 is a complete green slice

Task 8 now includes:

- `src/docmend/cli.py::_write_refusal_report`;
- `src/docmend/writer/apply.py`'s Report construction;
- `tests/test_report_artifact.py`;
- `tests/test_verify.py`;
- `tests/test_schemas.py::_minimal_report`;
- explicit `not_attempted`, `prior_attempt`, and `manifest_sha256` values;
- a refusal-report 2.0 schema assertion; and
- an explicit-file staging command covering every affected file.

The task can therefore satisfy the plan's full-gate-before-commit rule without depending on Task 9.

### Adversarial Recheck

The final pass re-attacked the highest-risk claims:

1. **Lineage gaps:** missing and ambiguous ancestors fail closed before mutation.
2. **Report-only safety:** null versus non-null manifest hashes remain distinct and plan-bound.
3. **Adjudication terminals:** isolated terminals fail; exact prior dangling intents make them legal only at chain scope.
4. **Backup trust:** path derivation, regular-file, no-symlink, role, and uniqueness checks remain mandatory before access.
5. **Restore convergence:** every table row and identity-substitution state remains covered.
6. **Validation false positives:** each commit slice names its affected constructors/consumers and runs the complete repository gate.

No new correctness, safety, data-integrity, maintainability, or validation finding survived this pass.

### Optional Editorial Cleanup

Task 13's combined Markdown-validation line contains awkward escaped Markdown and missing spaces around one `+`. The command still resolves through the repository's markdownlint configuration, and scoped Prettier/markdownlint pass, so this is optional presentation cleanup and does not affect approval.

### Final Recommendation

Claude Code may proceed with the implementation plan as written. Re-review is required only if the plan, approved design, task ordering, lifecycle rules, lineage graph, or validation scope changes materially.

### Round 4 Review Ledger

- Plan path: `docs/superpowers/plans/2026-07-10-safety-core-b-manifest-2.md`
- Audit round: 4
- Open issue IDs: None
- Resolved issue IDs: CR-001, CR-002, CR-003, CR-004, CR-005, CR-006, CR-007, CR-NEW-001, CR-NEW-002, CR-NEW-003, CR-NEW-004, CR-NEW-005
- Superseded issue IDs: None
- Significant findings remaining: No
- Next audit should focus on: Not applicable; the audit/fix loop can stop.
