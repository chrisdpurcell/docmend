# Safety-Core Remediation Design

Approved design for remediating the rollout-blocking safety findings DMR-01 through DMR-07 from the [2026-07-10 comprehensive review synthesis](../../codex-reviews/2026-07-10-2034-comprehensive-review-synthesis.md). This document is the design-stage artifact; the binding change lands as a SPEC-VHHB revision plus new ADRs before implementation (see [Change-control follow-through](#change-control-follow-through)).

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

Engine entrypoints (`execute_plan`, `run_restore`) additionally stop being callable without coordination: both take a `SafetyContext` constructible only by acquiring the run lock and passing the gate, closing the engine-bypass medium.

## Output Ledger and Backup Store (DMR-01)

**OutputLedger.** `claimed_targets` generalizes to a ledger of every action's effective output path: `target_path` for renames, `path` itself for in-place rewrites. Processing stays in the existing deterministic sorted order.

- Emitting an action claims its output path. A later action whose output is already claimed is skipped at plan time with reason `collision` and a detail naming the claiming action.
- Because in-place rewrites claim their own path, a rename target that equals another action's source is caught by the same rule — the `a.md` rewrite versus `a.txt -> a.md` case.
- The rule is never policy-overridable: `overwrite` licenses clobbering pre-existing files, not another planned action's output (G-005).

**BackupStore.** The layout changes from `<backup_root>/<run_id>/<relative_path>` to `<backup_root>/<run_id>/<action_seq>/<role>/<relative_path>` with `role` one of `source` or `overwritten`.

- Keys are write-once: the destination opens `O_EXCL`, and an existing file at a key raises `BackupError` (ERR-004). A retry is a new run with a new `run_id`, never a rewrite of an existing key.
- The manifest records full backup paths, so restore needs no layout knowledge; ManifestSet validates recorded backup paths as outside the source root before restore follows them.
- Defense in depth: even a future planner regression cannot reproduce the DMR-01 data loss, because the colliding backups land under different `(action, role)` keys.

## Manifest 2.0, Lifecycle Reducer, Journaled Mutations (DMR-03/04)

**Format.** Append-only NDJSON with the existing torn-tail rule. Line 1 becomes a header record:

```json
{
	"schema": "docmend/manifest-header",
	"schema_version": "2.0",
	"run_id": "…",
	"kind": "apply",
	"source_root": "/resolved/root",
	"plan_sha256": "sha256:…",
	"created_at": "…"
}
```

Run-level facts (run, root, plan identity) live once in the header instead of being re-stamped per record. Mutation records keep their fields, drop `source_root`, and use `result` as the lifecycle field: `intent | applied | failed`.

**Journal every mutation.** Every mutation kind — rewrite, rename, rename_and_rewrite, and each restore inverse — appends a fsync'd `intent` record before the corpus is touched and a terminal record after. A kill at any instant leaves either no evidence and no mutation, or a dangling intent that resume adjudicates from disk state, generalizing the existing `_reconcile_intent` logic to all kinds. Cost: two fsync'd appends per mutation.

**ManifestSet.** `read_manifest_set` replaces raw record lists everywhere and validates, before any referenced path is touched:

- header present; version `2.x` with unsupported-future-minor rejection; any `1.x` file is rejected with the clean-break operator message;
- one `run_id` matching the header; `seq` strictly contiguous from 1;
- lifecycle legality per action: at most one terminal record; `applied` requires a preceding intent (a mutation happened, so it must have been journaled); `failed` is legal without an intent and then asserts no mutation occurred (pre-mutation failures such as a backup error); duplicate applied records are illegal;
- containment: every `original_path` and `target_path` resolves inside the header's `source_root`; every backup path resolves outside it. Violation is a hard ERR-008 (exit 2), never a per-record skip — a manifest that lies about paths is untrusted evidence, not partially usable.

**One reducer, three consumers.** `reduce_lifecycle` folds an ordered chain of ManifestSets, sorted by `(recorded_at, seq)`, into one terminal state per action (`applied`, `failed`, `pending-intent`, `restored`). Resume, restore, and verify all consume this reducer; the three divergent interpretations currently in `apply.py`, `restore.py`, and `verify.py` are deleted.

**Restore.** The run lock keys on the header's `source_root`, not the first record. `--only-ids` selecting zero records exits 1 instead of reporting success. Because restore journals its inverses, an interrupted restore converges on re-run: the reducer sees the dangling inverse intent and completes it instead of tripping the collision preflight.

## Commit Boundary and Artifact Guard (DMR-02/06/07)

**CommitBoundary.** Each mutation binds to one object identity instead of a pathname:

- Source bytes are read once through a file descriptor opened `O_RDONLY | O_NOFOLLOW`; `fstat` captures `(st_dev, st_ino)`; the hash check, transform recompute, and backup all use those bytes.
- Immediately before the atomic publish, the boundary re-stats the source by descriptor and re-resolves containment. Identity drift — changed dev/ino, a path resolving outside the root, or an interposed symlink — skips the action with the new reason `external-interference`, corpus untouched. The check-to-rename window shrinks from whole-action to microseconds; the residual window is a documented accepted limitation with an injectable test hook, per DMR-06's repeat-checks arm (portable POSIX rename cannot be fully TOCTOU-free).
- Overwrite preservation becomes an action-time invariant (DMR-07): if the target exists at commit — regardless of gate-time state — it must have a verified preservation outcome: an overwritten-role backup taken at commit into its own key, or a declared external strategy. Overwrite policy with no active strategy and a target present at commit skips with the new reason `collision-unpreserved`, never clobbers. The gate's plan-time check remains as early feedback but is no longer load-bearing.

**Artifact destination guard.** One preflight for every CLI artifact write (`scan --report`, `plan --out`, `apply --report`, verify output):

- Resolve the destination through symlinks; refuse if it lies inside the corpus root, aliases any input artifact of the same invocation, or is a non-regular file. Refusal is exit 2 before the pipeline runs.
- Staging uses `O_EXCL` randomized temp names in the destination directory, replacing the predictable `<name>.tmp` sibling; the same change lands in `writer/atomic.py`, closing both the truncate-a-victim vector and the stale-temp-blocks-retry medium.
- Apply report finalization moves inside the lock: the gate receives the report path, the guard runs before mutation starts, and the report is staged and published while the run lock is held. A refused or dry-run apply leaves prior corpus state and prior artifacts untouched.

## Verify Redesign (DMR-05)

Verify becomes a pure consumer of Plan, ManifestSet, and BackupStore. Every confirmed false-clean path becomes a finding:

| False-clean today | New check |
| --- | --- |
| Missing or corrupt backup, exit 0 | Every applied record's backups (both roles) must exist and hash to their recorded digests |
| Zero readable files, exit 0 | `checked == 0` while inputs exist is a finding; discovery `unreadable` and `timeout` skips surface as findings |
| Aborted plan's trailing actions invisible | New binding `verify --plan`: every plan action must map to exactly one terminal outcome — `applied`, `failed`, `skipped`, or the report's new explicit `not-attempted` status for post-abort actions |
| Wrong-root manifest, exit 0 | The ManifestSet root must equal the verified root; mismatch is a finding |
| Dangling intent ignored | Any `pending-intent` state from the reducer is a finding |

Verify optionally writes a durable result artifact (new `verify-report` schema, written through the destination guard) so rollout gates can consume recorded evidence rather than an exit code.

## Coupled Mediums Resolved Here

- Scan and plan runs containing `timeout` skips exit 1 (partial) instead of 0.
- `SafetyContext` gates the write-capable engine entrypoints.
- Randomized staging removes the fixed temp-name retry blocker.
- Restore selector misses exit 1.

Deferred to sub-projects 2–4: disk-headroom same-filesystem accounting, the parallel and scale contract, log permissions and redaction, artifact schema aggregate hardening, and documentation drift. The stale opt-in scale test is DMR-08 scope, but its manifest-shape assertions are updated mechanically here when manifest 2.0 lands, keeping it runnable.

## Error Taxonomy

No new exit codes. Containment or lifecycle-invalid manifests map to ERR-008 (exit 2); commit-time interference is a per-action skip counting toward exit 1; guard refusals are exit 2 before the pipeline runs. New skip reasons: `collision-unpreserved`, `external-interference`. New report outcome status: `not-attempted`. Schema versions: manifest 2.0; the report schema bumps for the `not-attempted` status; the plan and inventory schemas are unchanged.

## Testing

Each abstraction gets unit tests plus the review's reproductions as regressions:

- the DMR-01 collision plan (dirty `a.md` + `a.txt -> a.md`, overwrite policy) applying and then restoring byte-identically;
- the artifact-clobber matrix across scan, plan, apply dry-run, and refused writes;
- adversarial manifest fixtures: mixed root and run, gapped or duplicate sequence, crafted out-of-root paths, dangling intents, duplicate applied records, 1.x rejection;
- crash-window fault injection for all mutation kinds and restore inverses, extending the existing `test_resume.py` injection pattern, including restore convergence on re-run;
- commit-boundary races via injectable hooks (post-validation swap, target-appears-after-gate);
- a verify false-clean matrix asserting each table row above yields a finding, plus `verify --plan` full-coverage accounting.

The standard gate holds: Ruff, BasedPyright strict, pytest at or above the current 97% branch coverage, allpairspy for the new gate and commit predicates, pip-audit.

## Change-Control Follow-Through

Before implementation starts, this design lands in the binding process:

- SPEC-VHHB revision updating the affected FR/DR/IR requirements (manifest format, verify semantics, backup layout, artifact IO, exit taxonomy) and section 18.4 rollout preconditions.
- New ADRs: manifest 2.0 envelope and lifecycle journaling; backup store namespacing; commit-boundary identity and the action-time overwrite invariant; artifact destination guard; verify plan-coverage semantics and the durable verify result.
- The implementation plan follows via the writing-plans process after the spec revision is approved.
