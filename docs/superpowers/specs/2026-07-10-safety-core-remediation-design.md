# Safety-Core Remediation Design

Approved design for remediating the rollout-blocking safety findings DMR-01 through DMR-07 from the [2026-07-10 comprehensive review synthesis](../../codex-reviews/2026-07-10-2034-comprehensive-review-synthesis.md). This document is the design-stage artifact; the binding change lands as a SPEC-VHHB revision plus ADR amendments and new ADRs before implementation (see [Change-control follow-through](#change-control-follow-through)).

Revision note: revised to resolve findings F1–F8 of the [design review](../../codex-reviews/2026-07-10-safety-core-remediation-design-review.md) (artifact-guard default carve-out, descriptor/pathname identity binding on both source and target, the complete manifest 2.0 wire model, backup-store trust boundary, verify input contract, ADR dispositions, and the read/write context split). Revised again per review round 2: the adjudication table now enumerates every crash-after-step state — including the lossless both-names intermediates of the link-then-unlink primitives — and verify's coverage reduction makes the ManifestChain the mutation authority with `already-applied` as a nonterminal confirmation. Revised again per round 3: the object identities the adjudication table consumes are now persisted in intent records, and apply reports carry durable attempt lineage with lifecycle legality stated at both the per-set and cross-set scopes. Revised again per round 4: `expected_published_identity` moves into the intent by staging the output **before** the intent append (so post-publish adjudication has its identity even though the terminal never landed), identity comparison is exact `(st_dev, st_ino)` with device changes refusing rather than substituting, and attempt lineage becomes a discriminated `prior_attempt` reference (report hash or closed-manifest hash) so manifest-with-missing-report attempts stay linkable and missing reports stay findings.

## Decisions Fixed Before Design

- **Decomposition.** The full review remediation splits into four sub-projects, executed in order: (1) this safety core (DMR-01..07 plus directly coupled mediums), (2) the scale and resource contract (DMR-08), (3) release and artifact hardening (DMR-09), (4) observability and documentation. Each gets its own design, plan, and implementation cycle.
- **Compatibility.** Clean break. No real-library runs exist, so manifest 2.0 and the new backup layout carry no 1.x read path. A 1.x manifest is rejected with an error directing the operator to docmend 1.0.2 for restores of pre-2.0 runs.
- **Version target.** The remediation releases as v2.0.0: the manifest format break, backup layout change, new report outcome, and stricter exit semantics are breaking changes under semver.
- **Approach.** Trust-kernel refactor (option A): build the four missing shared abstractions and rewrite the consumers on top of them, rather than patching each finding in place or moving to a WAL-driven two-phase apply.

## Problem Shape

The seven findings reduce to four missing abstractions, not seven bugs:

1. A plan-wide **output-path ledger** — planning reserves only rename targets, so one plan can schedule two actions whose outputs (and backup keys) collide (DMR-01).
2. A **journaled mutation protocol** — the intent-before-mutation record exists for exactly one of three operation kinds and not for restore, so kills leave completed mutations with no durable evidence (DMR-04).
3. A **validated manifest-set model** — records are trusted line by line; no consumer checks run/root coherence, sequence integrity, lifecycle legality, or path containment before reading and mutating recorded paths (DMR-03).
4. An **artifact destination guard** — docmend's own reports and plans can overwrite the corpus they describe (DMR-02).

DMR-05 (false-clean verify) follows from 2 and 3: verify cannot be honest without a lifecycle model. DMR-06/07 (mutation-time races) are the runtime half of the same boundary: validation is bound to pathnames and gate-time state instead of object identity and commit-time state.

## Architecture

New module `writer/commit.py`; substantial rewrites of `writer/manifest.py`, `writer/backup.py`, and `verify.py`; modifications to `planning.py`, `restore.py`, `writer/apply.py`, `artifacts.py`, `writer/atomic.py`, `writer/gate.py`, and `cli.py`. Transforms, discovery, and detection are untouched.

| Abstraction                       | Module               | Closes    |
| --------------------------------- | -------------------- | --------- |
| OutputLedger (plan-time)          | `planning.py`        | DMR-01    |
| BackupStore (run/action/role key) | `writer/backup.py`   | DMR-01    |
| ManifestSet 2.0 + reducer         | `writer/manifest.py` | DMR-03/04 |
| CommitBoundary                    | `writer/commit.py`   | DMR-06/07 |
| Artifact destination guard        | `artifacts.py`       | DMR-02    |
| Verify as pure consumer           | `verify.py`          | DMR-05    |

**Read/write entrypoint split (F8).** The engines split into read-only preview and mutation entrypoints instead of one dual-mode function. `preview_plan` and `preview_restore` keep today's dry-run behavior (default mode, current lock semantics, no write ceremony — FR-004/IR-008). `execute_plan` and `run_restore` require a `WriteSafetyContext`, a sealed capability whose only factory: acquires the run lock, evaluates the apply gate (apply) or the ManifestSet preflight and lock keying (restore), runs the artifact destination guard over the run's report and manifest destinations, and remains held — as a context manager — through manifest close and report publication. Nothing else can construct it, closing the engine-bypass medium without gating read-only use.

## Output Ledger and Backup Store (DMR-01)

**OutputLedger.** `claimed_targets` generalizes to a ledger of every action's effective output path: `target_path` for renames, `path` itself for in-place rewrites. Processing stays in the existing deterministic sorted order.

- Emitting an action claims its output path. A later action whose output is already claimed is skipped at plan time with reason `collision` and a detail naming the claiming action.
- Because in-place rewrites claim their own path, a rename target that equals another action's source is caught by the same rule — the `a.md` rewrite versus `a.txt -> a.md` case.
- The rule is never policy-overridable: `overwrite` licenses clobbering pre-existing files, not another planned action's output (G-005).

**BackupStore.** The layout changes from `<backup_root>/<run_id>/<relative_path>` to `<backup_root>/<run_id>/<action_seq>/<role>/<relative_path>` with `role` one of `source` or `overwritten`.

- Keys are write-once: the destination opens `O_EXCL`, and an existing file at a key raises `BackupError` (ERR-004). A retry is a new run with a new `run_id`, never a rewrite of an existing key.
- **Backup trust boundary (F5).** The manifest header carries the run's resolved `backup_root`. ManifestSet requires every non-null recorded backup path to resolve beneath that root **and** to reconstruct exactly from the record's own `(run_id, action_seq, role, relative_path)` BackupStore key — a backup reference is derivable evidence, never a free-form path. Before any backup is opened, ManifestSet additionally validates: regular file, no symlink in the components below `backup_root`, role consistency with the record's operation (an `overwritten` role requires `overwritten_sha256`), and at most one path per role per action. External-preservation records keep null backup paths; their recovery lives outside `docmend restore`, unchanged (ADR-0004).
- Defense in depth: even a future planner regression cannot reproduce the DMR-01 data loss, because the colliding backups land under different `(action, role)` keys.

## Manifest 2.0 Wire Model (DMR-03/04)

**Format.** Append-only NDJSON with the existing torn-tail rule. Line 1 is a header record; every subsequent line is a mutation record.

```json
{
	"schema": "docmend/manifest-header",
	"schema_version": "2.0",
	"run_id": "R2",
	"kind": "apply",
	"source_root": "/resolved/library",
	"backup_root": "/resolved/backups",
	"plan_sha256": "sha256:…",
	"prior_manifest_sha256": null,
	"created_at": "…"
}
```

- `kind` is `apply` (covers first apply and every resume) or `restore`.
- `backup_root` is the run's resolved tool backup root, or null when the run took no tool backups (F5's trusted anchor).
- `plan_sha256` binds an apply-kind manifest to the exact plan artifact; restore-kind headers carry the same value copied from the chain they undo, so one chain serves one plan.
- `prior_manifest_sha256` is the durable chain link (F4): null for the first apply manifest; for a resume, the sha256 of the manifest file it extends; for a restore, the sha256 of the newest manifest in the chain it undoes; for a restore re-run, the sha256 of the interrupted restore manifest. Manifest files are closed before any successor hashes them, so the hash is stable (a torn tail stays torn).

**Mutation records.** Records keep the 1.3 fields minus `source_root` (now header-owned), with `result` as the lifecycle field: `intent | applied | failed`. Three additions:

- Immutable-field rule: an action's `intent` and terminal record must agree on `action_id`, `docmend_id`, `operation`, `original_path`, `target_path`, `before_sha256`, `after_sha256` (expected vs achieved), both backup references, and all three identity fields below; only `result`, `error`, `seq`, and `recorded_at` may differ. Divergence is a lifecycle violation.
- Restore records carry `undoes_action_id` and `undoes_run_id` naming the original apply action they invert (F4) — the reducer never infers the relationship from timestamps or paths. Apply records carry both as null.
- **Durable object identity (F4 rounds 3–4).** Every identity the adjudication table consumes is persisted in the **intent**, before any corpus document is mutated: `source_identity` — the `(st_dev, st_ino)` CommitBoundary captured from the descriptor it validated; `target_identity` — the overwrite target's identity when one existed at commit (null otherwise); and `expected_published_identity` — the identity of the output object. For every replacement publish (rewrite, the rename_and_rewrite publish, and each restore inverse that writes replacement bytes), the output is **staged first**: the temp file is written and fsync'd under its `O_EXCL` randomized name, `fstat`'d, and that staged inode's identity goes into the intent — atomic publish moves the staged inode onto the target name, so the identity is knowable pre-mutation and survives the kill. For pure renames the inode moves rather than changes, so `expected_published_identity` equals `source_identity`. The terminal record **confirms** the same expected identity; it introduces nothing new. Identity comparison is exact `(st_dev, st_ino)` equality — a changed device after a remount or reboot refuses as `external-interference` (a documented operational limitation of adjudicating an interrupted run across a device renumbering; there is no silent substitution of `source_root`'s current device, which could cross-match bind mounts or swapped disks).

**Journal every mutation.** Every mutation kind — rewrite, rename, rename_and_rewrite, and each restore inverse — appends a fsync'd `intent` record before any corpus document is mutated and a terminal record after. The staging write that precedes the intent is not corpus mutation: it creates only a tool-owned `O_EXCL` randomized temp file, never touches a document name, and a killed run's stale staging file is inert residue cleaned on retry. Pre-mutation failures (unreadable source, backup error, staging failure) append `failed` with no prior intent, asserting no mutation occurred. Cost: two fsync'd appends per completed mutation.

**ManifestSet and chain validation.** `read_manifest_set` validates one file; `read_manifest_chain` orders a set of files by their `prior_manifest_sha256` links. Validated before any referenced path is touched:

- header present; version `2.x` with unsupported-future-minor rejection; any `1.x` file is rejected with the clean-break operator message;
- one `run_id` matching the header; `seq` strictly contiguous from 1;
- lifecycle legality per action, at two explicit scopes (F6 round 3): **within one ManifestSet**, at most one terminal record; `applied` requires a preceding intent; `failed` without an intent asserts no mutation occurred; duplicate applied records are illegal; intent/terminal immutable fields must match. **Across the chain**, the transition table governs: `failed` (any attempt) → `intent` → `applied` in a later set is legal (a retry); `applied` followed by any contradictory apply-kind terminal for the same action is illegal; restore transitions occur only through `undoes` records; after a `restore`-kind set, further apply-kind sets in the same chain are illegal — re-application requires a fresh plan;
- chain coherence: exactly one root manifest, no forks, no gaps; identical `source_root` and `plan_sha256` across the chain; a `restore` kind may only follow the chain tip; restore records must reference `undoes_action_id` values that exist in the chain's apply records;
- containment: every `original_path` and `target_path` resolves inside the header's `source_root`; every backup path satisfies the F5 BackupStore rules above. Violation handling: malformed or lifecycle-invalid files are ERR-008 artifact-input errors (exit 2); containment violations are safety refusals (exit 3, ADR-0012) — except in verify, where both are read-only findings (exit 1).

**One reducer, three consumers.** `reduce_lifecycle(chain)` folds records in chain order, then `seq` — never wall-clock — into one state per original apply action: `pending-intent`, `applied`, `failed`, `pending-restore`, `restored`, `restore-failed`. Resume, restore, and verify all consume this reducer; the three divergent interpretations currently in `apply.py`, `restore.py`, and `verify.py` are deleted.

**Dangling-intent adjudication.** A dangling intent (no terminal record after it in the chain) means a kill landed inside that mutation's window. The consumer adjudicates from disk state, generalizing today's `_reconcile_intent`. The table enumerates the crash-after state of **every mutation step** of every primitive — including the lossless intermediate states the multi-step primitives deliberately leave (`rename_no_clobber` is link-then-unlink, so a kill between the calls leaves both names on one intact inode; the restore inverses stage the original before cleaning up the target). Every recognized state either re-executes from the start or **completes the remaining steps** — after re-verifying each involved object against the record's hashes and identities — and appends the terminal. The identities in these predicates are the **persisted** `source_identity`/`target_identity`/`expected_published_identity` fields of the dangling intent itself — never process memory, and never a terminal record (a dangling intent by definition has none): the both-names rows require both pathnames to `lstat` to the recorded pre-mutation inode, and every post-publish state requires the live output name to `lstat` to the intent's `expected_published_identity` (the staged inode captured before mutation). A same-bytes replacement under a different inode therefore fails the identity predicate in both the pre-publish and post-publish windows, even though every hash matches, and is refused rather than adopted or unlinked. `external-interference` is reserved for states that fail all recorded identity/hash predicates (ADR-0006's no-guessing rule); it is never the classification of a known intermediate state.

| Operation (intent dangling) | Crash-after disk state (matched via recorded hashes/identity) | Adjudication |
| --- | --- | --- |
| rewrite (single atomic step) | path hashes to before | never happened — re-execute |
| rewrite | path hashes to expected after | happened — append terminal `applied` |
| rename, no-clobber (link, then unlink) | source only, before-bytes | never happened — re-execute |
| rename, no-clobber | **both names bound to one inode, before-bytes** | link landed — unlink source, append terminal `applied` |
| rename, no-clobber | target only, before-bytes | happened — append terminal `applied` |
| rename, overwrite (single atomic replace) | source has before-bytes, target holds recorded overwritten bytes | never happened — re-execute |
| rename, overwrite | target has before-bytes, source gone | happened — append terminal `applied` |
| rename_and_rewrite (publish target, then unlink source) | target absent or holds recorded overwritten bytes | never happened — re-execute |
| rename_and_rewrite | **target hashes to expected after, source still has before-bytes** | publish landed — unlink source, append terminal `applied` |
| rename_and_rewrite | target hashes to expected after, source gone | happened — append terminal `applied` |
| restore inverse of rewrite (single atomic step) | original still hashes to after (the applied bytes) | never happened — re-execute the inverse |
| restore inverse of rewrite | original hashes to before | happened — append inverse terminal (`restored`) |
| restore inverse of rename, no clobbered target (link, then unlink) | target only, after-bytes | never happened — re-execute the inverse |
| restore inverse of rename, no clobbered target | **both names bound to one inode** | link landed — unlink target, append inverse terminal |
| restore inverse of rename, no clobbered target | original only, after-bytes | happened — append inverse terminal |
| restore inverse of rename with clobbered target (relink original, then rewrite target) | target has applied bytes, original absent | never happened — re-execute the inverse |
| restore inverse of rename with clobbered target | **original relinked, target still has applied bytes** | verify both identities and the clobbered backup, finish the target rewrite, append inverse terminal |
| restore inverse of rename with clobbered target | original has applied bytes, target holds recorded clobbered bytes | happened — append inverse terminal |
| restore inverse of rename_and_rewrite (reinstate original, then clean up target) | original absent, target has applied bytes | never happened — re-execute the inverse |
| restore inverse of rename_and_rewrite | **original hashes to before, target still has applied bytes** | reinstatement landed — verify the restored original, finish target cleanup (unlink, or rewrite to recorded clobbered bytes), append inverse terminal |
| restore inverse of rename_and_rewrite | original hashes to before, target absent or holds recorded clobbered bytes | happened — append inverse terminal |
| any | fails every recorded identity/hash predicate | `external-interference`; mutate nothing |

Each table row is paired with a deterministic fault-injection test that kills exactly after the corresponding step (see Testing).

**Worked example (F4).** Plan P, actions a1–a3. Apply run R1 writes M1: header (kind apply, plan P, prior null); a1 intent+applied; a2 intent — killed. Resume R2 writes M2 (prior = sha(M1)): adjudicates a2's dangling intent from disk (never happened) and re-executes — a2 intent+applied; a3 intent+applied; a1 needs no record (already terminal in chain). Restore R3 writes M3 (kind restore, prior = sha(M2)): inverse of a3 (undoes a3) intent+applied; inverse of a2 intent — killed. Restore re-run R4 writes M4 (prior = sha(M3)): adjudicates a2's dangling inverse intent, completes it, then inverts a1. `reduce_lifecycle([M1, M2, M3, M4])` yields a1 `restored`, a2 `restored`, a3 `restored` — deterministically, from chain links and seq alone.

**Restore.** The run lock keys on the header's `source_root`. `--only-ids` selecting zero records exits 1 instead of reporting success. Because restore journals its inverses, an interrupted restore converges on re-run via the adjudication table instead of tripping the collision preflight.

## Commit Boundary (DMR-06/07)

**Source identity (F2).** Each mutation binds to one object identity, not a pathname:

- The source opens once with `O_RDONLY | O_NOFOLLOW`; `fstat` captures `(st_dev, st_ino)`; the hash check, transform recompute, and backup all use bytes read from that descriptor. The captured identity is not process-local state: it is written into the action's intent record (`source_identity`, `target_identity` when an overwrite target exists, and `expected_published_identity` — the staged output inode, `fstat`'d after the staging write and before the intent append) so post-kill adjudication verifies against the same objects the live boundary validated, in both the pre-publish and post-publish windows (F4 rounds 3–4).
- Immediately before **each** pathname mutation step — every publish and every unlink — the boundary `lstat`s the source pathname (never following symlinks) and compares its `(st_dev, st_ino)` against the captured descriptor identity. A missing name, a symlink, or an identity mismatch skips the action as `external-interference` with the corpus untouched. `fstat` on the descriptor alone is insufficient by construction: it describes the originally opened inode even after the name is repointed.
- Parent-path defense: `O_NOFOLLOW` guards only the final component, so the boundary re-resolves the full path and re-checks containment against the source root at the same instant as the `lstat` comparison; a parent directory swapped for a symlink fails containment even when the leaf identity matches.

**Target identity (F3).** An existing overwrite target gets the same binding: it opens `O_NOFOLLOW`, its identity is captured, and its bytes are read and backed up **through that descriptor** into the `(action, overwritten)` key. Immediately before `os.replace`, the target pathname is `lstat`-compared against the captured identity — disappeared or changed means `external-interference`, never a clobber of an unpreserved object. When the earlier check found **no** target, publication uses a no-clobber primitive (`link`/`RENAME_NOREPLACE` semantics) and maps `EEXIST` to the new skip `collision-unpreserved` — a target that appears after the gate is never silently overwritten (DMR-07). The gate's plan-time overwrite-preservation check remains as early feedback but is no longer load-bearing.

**Residual windows.** The `lstat`-to-`rename` interval on each side is the accepted residual (portable POSIX rename cannot be fully TOCTOU-free); it shrinks from whole-action seconds to microseconds and is documented as a stated limitation. Deterministic test hooks cover: regular-file replacement after validation, parent-symlink interposition, target replacement after backup, target creation immediately before publish, and the unlink/publish windows.

## Artifact Destination Guard (DMR-02)

One preflight for every CLI artifact write (`scan --report`, `plan --out`, `apply --report`, verify output), with one carve-out (F1):

- The canonical tool artifact root — `.docmend/` in the invoking directory (OQ-034, §18.2) — remains a legal destination even when it lies inside the corpus root, **provided** the effective exclude patterns still cover it (the default `**/.docmend/**` exclude is present, so its contents can never become scan candidates) and the destination does not alias any input artifact of the same invocation. If the operator has removed the `.docmend/` exclusion, the guard refuses: the default workflows (`scan .`, `plan .`, the single-file journey) must keep working without setup (NFR-006), but never by writing into scannable corpus space.
- Every other destination is refused when it resolves (through symlinks) inside the corpus root, aliases an input artifact of the same invocation, or is a non-regular file. Refusal is a safety refusal, exit 3 (ADR-0012), before the pipeline runs — a refused artifact write must not follow a completed scan.
- Staging uses `O_EXCL` randomized temp names in the destination directory, replacing the predictable `<name>.tmp` sibling; the same change lands in `writer/atomic.py`, closing both the truncate-a-victim vector and the stale-temp-blocks-retry medium.
- Apply report finalization moves inside the `WriteSafetyContext`: the guard runs before mutation starts and the report is staged and published while the run lock is held. A refused or dry-run apply leaves prior corpus state and prior artifacts untouched.

## Verify Redesign (DMR-05)

Verify consumes Plan, **Report(s)**, ManifestChain, and BackupStore (F6) — matching ADR-0012's input contract (flags or sidecar discovery). **Attempt lineage (F6 rounds 3–4):** one lineage spans all attempt shapes by pointing at whichever durable predecessor evidence exists. Apply reports gain `manifest_sha256` (the sha256 of the attempt's closed manifest, null when the attempt mutated nothing) and a discriminated `prior_attempt` reference — null for the first attempt, otherwise the predecessor's `run_id` plus **either** its report sha256 **or**, when that report was never published (the crash-after-manifest-close window), its closed manifest sha256. Attempt order is this lineage — never caller order or wall-clock — and every supported attempt shape stays linkable: report-only attempts (first-action abort, all-skip retry) are referenced by report hash; manifest-with-missing-report attempts are referenced by manifest hash, and the missing report **remains a verify finding rather than a structural impossibility**. Manifest↔report cardinality is at most one report per manifest run — absence is the finding, duplication is a contradiction. A manifest's `prior_manifest_sha256` must reference the newest manifest of an earlier attempt in the same lineage, so the two chains cannot disagree. CLI discovery: `--resume-run-id` resolves both default sidecars for a predecessor attempt; a repeatable `--prior-report` input names relocated or report-only predecessor reports; a manifest-only predecessor needs no report input — its manifest hash carries the link. Coverage binding: the report's `plan_ref` hash, the manifest headers' `plan_sha256`, and the plan artifact hash must agree. Every confirmed false-clean path becomes a finding:

| False-clean today | New check |
| --- | --- |
| Missing or corrupt backup, exit 0 | Every applied record's backups (both roles) must exist under the F5 trust boundary and hash to their recorded digests |
| Zero readable files, exit 0 | `checked == 0` while inputs exist is a finding; discovery `unreadable` and `timeout` skips surface as findings |
| Aborted plan's trailing actions invisible | `verify --plan` (the binding interface): every plan action must map to exactly one terminal outcome — `applied`, `failed`, `skipped`, or the report's new explicit `not-attempted` status for post-abort actions |
| Wrong-root manifest, exit 0 | The chain's `source_root` must equal the verified root; mismatch is a finding |
| Dangling intent ignored | Any `pending-intent` or `pending-restore` state from the reducer is a finding |

Plan-coverage semantics (F6):

- The action partition is a full invariant: every plan action appears exactly once across `applied | failed | skipped | not-attempted` (write runs) — duplicates and omissions are findings. `ReportTotals` gains `not_attempted` and the DR-003 reconciliation extends to it.
- **The ManifestChain lifecycle reduction is the mutation authority; report outcomes never override it.** The partition is built in two passes: first `reduce_lifecycle(chain)` fixes the state of every action with mutation evidence, then report outcomes fill in the actions the manifest intentionally never records (ordinary skips, `not-attempted`).
- `skipped/already-applied` is a **nonterminal reconciliation observation**, not a terminal outcome: a resume run emits it after confirming an earlier run's applied record against disk, so it confirms and retains the reducer's `applied` state — it never demotes it. A clean single or double resume therefore certifies as fully applied.
- Allowed cross-attempt report transitions, ordered by report-chain position: `not-attempted -> skipped | failed | applied` (a later attempt reached the action); `failed -> applied` (a successful retry — legal because terminal uniqueness is a per-ManifestSet rule, with the cross-set transition table governing the chain); `applied -> already-applied` (retained as `applied`); any later report that contradicts the chain's terminal mutation state — or claims a terminal `applied` with no chain record — is a finding.
- A dry-run report (`would_apply`) is not terminal evidence: `verify --plan` against only dry-run reports reports coverage as uncertified, a finding.
- A missing report where the manifest chain shows mutations — including a report whose publication was interrupted after corpus mutation — is a finding (`coverage unprovable`), not silence.

Verify optionally writes a durable result artifact (new `verify-report` schema, written through the destination guard) so rollout gates can consume recorded evidence rather than an exit code.

## Coupled Mediums Resolved Here

- Scan and plan runs containing `timeout` skips exit 1 (partial) instead of 0.
- The read/write entrypoint split with `WriteSafetyContext` gates the write-capable engines (F8).
- Randomized staging removes the fixed temp-name retry blocker.
- Restore selector misses exit 1.

Deferred to sub-projects 2–4: disk-headroom same-filesystem accounting, the parallel and scale contract, log permissions and redaction, artifact schema aggregate hardening, and documentation drift. The stale opt-in scale test is DMR-08 scope, but its manifest-shape assertions are updated mechanically here when manifest 2.0 lands, keeping it runnable.

## Error Taxonomy

No new exit codes; classifications follow ADR-0012's taxonomy (F7):

- Artifact destination guard refusal: **exit 3** (safety refusal).
- Malformed or lifecycle-invalid manifest input: **exit 2** (ERR-008 artifact-input error).
- Manifest containment violation (paths escaping `source_root`, backup outside the BackupStore): **exit 3** in restore/resume; a read-only **finding (exit 1)** in verify.
- Commit-time interference: per-action skip counting toward exit 1.
- New skip reasons: `collision-unpreserved`, `external-interference`. New report outcome status: `not-attempted`.
- Schema versions: manifest 2.0; the report schema bumps for `not-attempted`, the totals extension, and the attempt-lineage fields (`prior_attempt`, `manifest_sha256`); the plan and inventory schemas are unchanged; `verify-report` is a new schema.

## Testing

Each abstraction gets unit tests plus the review's reproductions as regressions:

- the DMR-01 collision plan (dirty `a.md` + `a.txt -> a.md`, overwrite policy) applying and then restoring byte-identically;
- the artifact-clobber matrix across scan, plan, apply dry-run, and refused writes, **plus** default-path acceptance (`scan .`, `plan .`, apply, restore, verify writing under `./.docmend/`) and explicit rejection of in-corpus source-file destinations and of `.docmend/` destinations when its exclusion has been removed (F1);
- adversarial manifest fixtures: mixed root and run, gapped or duplicate sequence, crafted out-of-root paths, crafted backup paths outside the BackupStore key space (F5), broken chain links, forked chains, intent/terminal immutable-field divergence, dangling intents, duplicate applied records, missing `undoes` references, 1.x rejection;
- crash-window fault injection for all mutation kinds and restore inverses, extending the existing `test_resume.py` injection pattern: **one deterministic kill-after-step test per adjudication-table row** (including every both-names intermediate state), plus the worked example's apply → interrupted resume → interrupted restore → convergent re-run chain, plus the F4 identity probes — kill after intent (pre-publish) **and** kill after publish before the terminal, replace the source, target, or published output with a **different inode carrying identical bytes**, and prove adjudication refuses with `external-interference` instead of adopting or unlinking it, for rewrite, rename_and_rewrite, and the restore replacement paths;
- commit-boundary races via the deterministic hooks listed above (source replacement, parent symlink, target replacement after backup, target creation before publish, unlink/publish windows) (F2/F3);
- a verify false-clean matrix asserting each table row yields a finding, plus `verify --plan` full-partition accounting across single-run, resume-chain, dry-run-only, and missing-report cases — including clean single-resume and double-resume chains proving `already-applied` retains the `applied` state, shuffled input order (chain links alone must determine attempt order), a first-action abort with no manifest, an all-skip report-only retry, a failed-manifest-then-successful-retry chain, a manifest-with-missing-report attempt followed by a successful resume, and a relocated prior report supplied via `--prior-report` (F6).

The standard gate holds: Ruff, BasedPyright strict, pytest at or above the current 97% branch coverage, allpairspy for the new gate and commit predicates, pip-audit.

## Change-Control Follow-Through

Before implementation starts, this design lands in the binding process:

- SPEC-VHHB revision updating the affected FR/DR/IR requirements (manifest format, verify semantics, backup layout, artifact IO, exit taxonomy) and section 18.4 rollout preconditions.
- **ADR dispositions (F7):**
  - `adr-0004` (apply safety gate and preservation): **amended** — action-time overwrite invariant, `WriteSafetyContext`, BackupStore keying.
  - `adr-0005` (durable artifact schema contract): **amended** — manifest 2.0, the report totals extension, `verify-report` as a fifth durable artifact, and the recorded clean-break compatibility decision.
  - `adr-0006` (resume and recovery model): **superseded** by a new ADR defining the manifest 2.0 envelope, chain links, journaled lifecycle, reducer, and adjudication tables — with reciprocal `supersedes`/`superseded_by` metadata and index updates.
  - `adr-0012` (verify semantics and exit-code taxonomy): **amended** — verify input binding and plan coverage, the findings list above, and the exit classifications in the error taxonomy section.
- New ADRs: the manifest 2.0 recovery model (superseding `adr-0006`); commit-boundary object identity; the artifact destination guard and canonical artifact-root carve-out.
- The implementation plan follows via the writing-plans process after the spec revision is approved.
