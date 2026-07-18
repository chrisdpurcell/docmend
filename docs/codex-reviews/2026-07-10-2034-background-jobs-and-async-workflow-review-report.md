# Background Jobs And Async Workflow Review

## Review Metadata

- review_type: `background-jobs-and-async-workflow-review`
- reviewed_at: `2026-07-10`
- repo_path: `.`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- release_baseline: `v1.0.2` (`9b0641bf3250bd3ba1b351609935612bdf8a3d40`)
- baseline_comparison: `v1.0.2..HEAD` contains handoff/configuration documentation changes only; no runtime source file changed after the release baseline.
- working_tree_state: `dirty` before this review (`AGENTS.md` modified; `docs/codex-reviews/` untracked). Pre-existing changes and orchestrator-owned artifacts were not edited.
- detected_frameworks_and_runtimes: Python `>=3.14` synchronous Linux/POSIX batch CLI; Typer/Rich command boundary; Pydantic/JSON Schema artifacts; structlog; no asyncio runtime, queue library, broker, workflow engine, scheduler, webhook receiver, HTTP service, or database.
- async_surfaces_reviewed: manual long-running `scan`, `plan`, `apply`, `restore`, and `verify` workflows; run-level `flock`; per-file SIGALRM watchdog; append/fsync manifest; resume reconciliation; inverse restore; artifact/report finalization; configured-but-absent process-pool mode.
- job_classes_and_workflow_families_reviewed: read-only discovery; content planning; destructive apply; interrupted-apply resume; manifest replay/restore; post-run verify; report/log/artifact publication.
- triggers_reviewed: manual CLI invocation only. Dependabot schedules are repository maintenance and not product job execution.
- delivery_guarantee_assumptions: no broker delivery. Work is enumerated from an immutable plan and attempted sequentially; manual rerun/resume gives application-level at-least-once attempts, while source/after hashes suppress many duplicate side effects.
- broker_guarantees_vs_application_guarantees: broker guarantees are `not needed for this repo`; all durability, deduplication, ordering, and replay guarantees are application/filesystem responsibilities.
- idempotency_and_deduplication_artifacts_reviewed: plan `action_id`, per-file source hash, manifest `after_sha256`, `docmend_id`, `seq`, write-ahead `intent`, `already-applied` reconciliation, collision policy, run lock.
- outbox_inbox_and_side_effect_coordination_reviewed: no network/database outbox or inbox is needed; the manifest is the filesystem write-ahead/audit seam. Its coverage is incomplete for single-step apply and restore transitions (ISSUE-002, ISSUE-003).
- workflow_versioning_compensation_and_saga_artifacts_reviewed: versioned inventory/plan/report/manifest schemas, plan snapshot, manifest inverse operations, resume manifests, restore runbooks. There is no general workflow engine or saga runtime.
- retry_dead_letter_replay_and_operator_tooling_reviewed: no automatic retry; classified skips/failures, manual re-plan/re-apply, repeatable resume-manifest flags, restore dry-run/write, ID-filtered replay, inverse manifest, verify reconciliation.
- observability_and_runbook_artifacts_reviewed: per-run JSONL logs, DR-003 apply report, manifest, Rich summary, exit taxonomy, `docs/runbooks/resume-after-interruption.md`, `docs/runbooks/restore-from-manifest.md`.
- important_external_async_surfaces_not_in_repo: the private sibling wrapper repository described by ADR-0018; user-selected Git/external backup systems; filesystem and storage behavior beyond local POSIX assumptions. None was independently verified.
- important_runtime_unknowns: real-library filesystem/mount behavior; hostile-versus-trusted artifact threat model; actual external wrapper call path; external backup completeness; power-loss behavior; long-running native/C detector behavior on pathological files.
- prior_baseline_or_release_artifacts_compared: `v1.0.2`, approved spec revision 0.25, ADRs 0002-0008 and 0018, resume/restore runbooks, current schema contracts, and checked-in scale evidence.
- conventions_input: `docs/handoff/conventions.md` (repo equivalent of `docs/conventions.md`). It is mature for tooling/spec/sensitive-data practices but has no durable runtime workflow/recovery conventions (ISSUE-013).
- exclusions: generated caches, coverage output, vendored/generated output, byte-exact fixture contents, and orchestrator execution/sweep/live-status artifacts.
- shared_research_used: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`.
- targeted_internet_follow_up: official Python 3.14 signal semantics only; Python handlers run later at a bytecode boundary and long-running C work can continue for an arbitrary duration despite a signal ([Python 3.14 `signal` documentation](https://docs.python.org/3.14/library/signal.html#execution-of-python-signal-handlers)).
- direct_validation:
  - `uv run pytest -q tests/test_resume.py tests/test_cli_resume.py tests/test_restore.py tests/test_restore_drill.py tests/test_watchdog.py tests/unit/writer/test_atomic.py tests/unit/writer/test_manifest.py tests/test_lock.py tests/test_config.py` -> `121 passed in 2.63s`.
  - isolated `/tmp` fault probe: an applied manifest record with `source_root` set to one directory successfully rewrote a path outside that root through `run_restore`.
  - isolated `/tmp` fault probe: a pure rewrite completed, then a simulated exception at the post-mutation `ManifestWriter.append` point left changed corpus bytes and no manifest file.
- evidence_legend: `verified` means direct repository evidence or an executed test/probe; `inferred` means a consequence derived from verified control flow; `unverified-external` means the critical surface is outside this repository.

## Async Workflow Area Matrix

| Async workflow area | Relevance | Assessment | Findings |
| --- | --- | --- | --- |
| `job-inventory-and-ownership` | high | Five manual batch workflows are identifiable, but raw write engines can bypass the coordinator that owns locks and preservation gates. | ISSUE-004 |
| `triggering-and-delivery-guarantees` | high | No broker exists; plan enumeration plus manual invocation is appropriate. Mutation-to-journal atomicity is incomplete. | ISSUE-002 |
| `payload-design-and-versioning` | high | Artifacts are explicitly versioned and strict, but destructive manifest consumers accept future minor versions and do not validate run-wide invariants. | ISSUE-011 |
| `idempotency-and-deduplication` | critical | Hash guards and applied-record reconciliation are strong; unjournaled completed mutations and residue states prevent complete convergence. | ISSUE-002, ISSUE-003, ISSUE-007 |
| `outbox-inbox-and-side-effect-coordination` | critical | No remote outbox/inbox is needed. The manifest is the local side-effect journal, but not every externally visible transition has durable prior intent. | ISSUE-002, ISSUE-003 |
| `retry-backoff-and-poison-message-handling` | medium | Automatic retry/backoff is intentionally absent; content poison is skipped and reported. Crash residue can turn transient interruption into a permanent retry failure. | ISSUE-007 |
| `timeouts-cancellation-and-heartbeats` | high | Per-file timeout exists, but it is cooperative Python signal handling rather than a hard worker-kill boundary. Resident-job heartbeat is not needed. | ISSUE-006 |
| `ordering-concurrency-and-reentrancy` | high | CLI apply/restore are serialized by root lock; standalone scan/verify are not; accepted process mode does not exist. | ISSUE-004, ISSUE-005, ISSUE-012 |
| `transaction-boundaries-and-exactly-once-assumptions` | critical | Atomic file visibility is strong, but it is incorrectly treated as atomic coordination with the manifest/report. | ISSUE-002, ISSUE-003, ISSUE-009 |
| `scheduling-cron-and-periodic-work` | none | `not needed for this repo`; product execution is manual and the spec explicitly excludes scheduled work. | none |
| `workflow-orchestration-and-state-progression` | high | Plan/apply/resume state is explicit, but logical attempt lineage is manual and restore lacks a convergent pending state. | ISSUE-003, ISSUE-008 |
| `workflow-versioning-and-compensation` | high | Plan snapshots, schema versions, and inverse restore exist; future-manifest rejection and complete compensation coverage are insufficient. | ISSUE-002, ISSUE-003, ISSUE-011 |
| `dlq-replay-and-recovery` | critical | Classified skips function as a local quarantine. Replay containment, lineage, crash evidence, and restore convergence have material gaps. | ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-007, ISSUE-008 |
| `throughput-backpressure-and-capacity` | high | Sequential processing provides natural work backpressure, but process-pool controls are no-ops and whole-run structures grow with file count. | ISSUE-005, ISSUE-010 |
| `observability-alerting-and-runbooks` | high | Logs, artifacts, reports, exit codes, and runbooks are substantial. A killed run has no durable terminal report and several runbook guarantees overstate implementation. | ISSUE-002, ISSUE-009 |
| `admin-tools-and-operator-safety` | critical | Restore is dry-run by default and hash-gated, but it trusts replay paths and requires manual attempt-chain assembly. | ISSUE-001, ISSUE-003, ISSUE-008, ISSUE-011 |
| `async-testing-and-fixtures` | high | Recovery tests are broad, but exception mocks are not equivalent to hard kills and some tests canonize non-convergence. | ISSUE-002, ISSUE-003, ISSUE-006, ISSUE-007, ISSUE-009 |

## Severity Summary

| Severity | Count | Issue IDs |
| --- | --: | --- |
| critical | 0 | none |
| high | 4 | ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-004 |
| medium | 7 | ISSUE-005, ISSUE-006, ISSUE-007, ISSUE-008, ISSUE-009, ISSUE-010, ISSUE-011 |
| low | 2 | ISSUE-012, ISSUE-013 |

## Findings

### ISSUE-001 — Restore can replay mutations outside the recorded source root

- severity: `high`
- confidence: `high`
- first_pass: `1`
- async_area: `admin-tools-and-operator-safety`
- issue_type: `admin-operator-safety-gap`
- verification: `verified repo behavior plus isolated /tmp probe`
- evidence:
  - `src/docmend/cli.py:379-394` derives the lock root from the first record's `source_root`, but does not validate that every record agrees or that its paths are contained.
  - `src/docmend/restore.py:48-104,146-268` reads `backup_path`, `original_path`, and `target_path` directly and mutates them without a source-root containment check.
  - `src/docmend/writer/manifest.py:44-75,138-166` validates each record structurally but does not enforce run-wide root/path invariants.
  - The shared research pack explicitly requires treating saved manifests as untrusted restore input and reapplying containment.
  - The isolated probe supplied a record stamped with one `source_root` and a rewrite target outside it; `run_restore(write=True)` returned `restored` and changed the outside file.
- risk: A stale, mixed, corrupt, or crafted manifest can direct the disaster-recovery command to read backups and rewrite or rename arbitrary operator-accessible paths while holding a lock for a different tree. Dry-run reduces accidental execution but does not make `--write` safe.
- recommendation: Before any path access, require one resolved non-null root for current manifests; validate every record's run ID, root, original, target, and relevant backup policy; enforce containment at the opened-object/mutation boundary; reject mixed-root manifests. Define a separately reviewed compatibility policy for legacy manifests without `source_root` rather than silently weakening current replay safety.
- acceptance_evidence:
  - Hostile-manifest tests for outside original, target, backup, overwritten backup, symlink swap, and mixed roots refuse before mutation.
  - The lock root and the actual replay root are derived from the same validated run-wide object.
  - Restore never reads or mutates a corpus path outside the validated root.
- follow_on_review: `security review` and `data-schema-migration-review`

### ISSUE-002 — Single-step apply mutations have a post-mutation journal gap

- severity: `high`
- confidence: `high`
- first_pass: `1`
- async_area: `transaction-boundaries-and-exactly-once-assumptions`
- issue_type: `transaction-boundary-gap`
- verification: `verified repo behavior plus isolated /tmp fault probe`
- evidence:
  - `src/docmend/writer/apply.py:483-503` writes an intent only for `rename_and_rewrite` and asserts that single-step operations have no unmanifested window.
  - `src/docmend/writer/apply.py:503-583` performs `rewrite` or `rename` first and calls `_record` afterward.
  - `src/docmend/writer/manifest.py:105-135` cannot make a post-side-effect append atomic with the earlier corpus mutation.
  - `tests/test_resume.py:233-264` and `docs/runbooks/resume-after-interruption.md:52-58` accept a lost trailing record as a stale-hash/unreadable skip and acknowledge that the backup pointer can be lost.
  - The isolated fault probe let a rewrite complete and then raised at `ManifestWriter.append`; the corpus changed and no manifest file existed.
- risk: A hard kill, process abort, disk-full condition, or manifest I/O failure after an atomic rewrite/rename but before its append can orphan a completed mutation from the manifest. Resume may avoid duplicating the write through path/hash symptoms, but restore, report accounting, and the claim that every mutation is reversible/auditable are false. Atomic file visibility is not an atomic commit with journal evidence.
- recommendation: Write and fsync a pre-mutation intent for every operation, including expected before/after state and overwrite metadata, then reconcile a dangling intent deterministically. Alternatively use a journal protocol with explicit prepare/commit records for every mutation. Treat manifest append failure after mutation as a first-class recovery state, not as an impossible window.
- acceptance_evidence:
  - Real subprocess kill tests at before-publish, after-publish, after-source-unlink, before-final-append, during-final-append, and after-final-fsync boundaries converge with complete restore evidence.
  - The union of attempt manifests contains an applied record or a safely reconcilable intent for every changed corpus object.
  - Restore after each injected interruption reproduces the pre-apply bytes.

### ISSUE-003 — Restore cannot converge after interruption inside a multi-step inverse

- severity: `high`
- confidence: `high`
- first_pass: `1`
- async_area: `dlq-replay-and-recovery`
- issue_type: `dlq-replay-recovery-gap`
- verification: `verified repo behavior and passing test that canonizes the gap`
- evidence:
  - `src/docmend/restore.py:232-268` reinstates the original before removing/replacing the applied target and has no pre-mutation intent.
  - The inverse manifest record is appended only after the entire mutation completes (`src/docmend/restore.py:268-281`).
  - A half-restore with both original and target present is rejected as a collision at `src/docmend/restore.py:178-185` rather than reconciled.
  - `tests/test_restore.py:459-513` injects exactly this failure, confirms a safe superset, reruns restore, and expects a collision skip.
- risk: The operation designed for disaster recovery can stop in an ambiguous state that the same command cannot finish. The operator must manually decide which file to remove while the replay has no durable pending record. This increases the chance of incomplete rollback or human deletion of the wrong copy during an incident.
- recommendation: Give restore its own durable prepare/commit protocol and state reconciliation for every multi-step inverse. On rerun, compare both paths and hashes to the recorded before/after state, complete only the missing step, or classify external interference. Keep safe-superset ordering, but make that state automatically convergent.
- acceptance_evidence:
  - Kill/fault injection at every restore mutation boundary reruns to `restored` or an explicit external-interference failure without manual file manipulation.
  - Every started inverse operation has durable evidence before its first mutation.
  - The restore runbook enumerates and tests every interruption state.

### ISSUE-004 — Public write engines can bypass the lock and preservation coordinator

- severity: `high`
- confidence: `high`
- first_pass: `1`
- async_area: `job-inventory-and-ownership`
- issue_type: `admin-operator-safety-gap`
- verification: `verified repo behavior`
- evidence:
  - `src/docmend/cli.py:537-580` acquires the run lock and evaluates the FR-005 gate before calling `execute_plan`; its comment states that the engine does not self-enforce preservation.
  - `src/docmend/writer/apply.py:587-704` is directly callable with `ApplyOptions(write=True)` and does not acquire a lock or evaluate the gate.
  - `src/docmend/cli.py:740-756` owns the restore lock outside `run_restore`, while `src/docmend/restore.py:106-143` directly accepts `write=True`.
  - The scale and unit tests regularly invoke raw write engines, demonstrating that these are practical callable boundaries, not unreachable internals.
- risk: A future background wrapper, Python API, refactor, or sibling integration can execute destructive work concurrently or without preservation while still using an apparently supported engine. The application guarantee depends on one Typer path rather than the mutation boundary.
- recommendation: Introduce guarded application services that own artifact-version checks, root validation, lock acquisition, preservation gate, mutation engine, and terminal artifacts. Make unchecked loops private and mark low-level fault tests explicitly. Route external wrappers through the guarded service or CLI only.
- acceptance_evidence:
  - Direct guarded-service calls without preservation refuse before mutation.
  - Concurrent guarded-service calls on one root contend.
  - Static enforcement or package visibility prevents production callers from reaching unchecked write loops.

### ISSUE-005 — Accepted parallel configuration is a silent runtime no-op

- severity: `medium`
- confidence: `high`
- first_pass: `2`
- async_area: `ordering-concurrency-and-reentrancy`
- issue_type: `convention-misalignment`
- verification: `verified repo behavior`
- evidence:
  - ADR-0007 and spec section 18.2 state that `parallel.enabled=true` selects `ProcessPoolExecutor` and controls workers, start method, chunksize, and recycling.
  - `src/docmend/config.py:139-163` accepts the full surface while saying it is reserved for a profiled post-v1 pool.
  - Repository search found no runtime read of `config.parallel`, no multiprocessing import, and no `ProcessPoolExecutor`; tests validate parsing only.
- risk: Operators and wrappers can believe they enabled fault-isolated parallel processing and hard worker timeouts while the sequential in-process engine continues silently. Capacity planning and the ADR/spec delivery guarantee become unreliable.
- recommendation: Either implement and verify ADR-0007 or reject `parallel.enabled=true`, non-default workers, and process-specific settings with a clear unsupported-feature error until the pool ships. Update the approved spec/ADR through the required change-control path; do not retain accepted no-op controls.
- acceptance_evidence:
  - Every accepted parallel setting changes an exercised runtime path, or validation rejects it.
  - Process-mode tests prove configured start method, parent-only artifact writes, worker termination, ordering independence, and output equivalence.

### ISSUE-006 — The per-file watchdog is not a hard timeout boundary

- severity: `medium`
- confidence: `high`
- first_pass: `2`
- async_area: `timeouts-cancellation-and-heartbeats`
- issue_type: `timeout-cancellation-heartbeat-gap`
- verification: `verified repo behavior plus official runtime semantics`
- evidence:
  - `src/docmend/watchdog.py:45-65` implements a SIGALRM handler that raises in the main thread and explicitly becomes a no-op in any other thread.
  - The approved DEV-002 acknowledges that the required process termination is deferred because no worker process exists.
  - Python documents that its signal handler runs later at a bytecode boundary and a long-running C calculation may continue for an arbitrary duration despite the signal ([Python 3.14 `signal` documentation](https://docs.python.org/3.14/library/signal.html#execution-of-python-signal-handlers)).
  - `tests/test_watchdog.py` proves interruptible Python work, nesting, and thread no-op behavior, not a stuck native detector or blocked filesystem call.
- risk: A pathological file in a long native/C operation can still stall an unattended 100k-file run beyond `limits.per_file_timeout`. Any future threaded caller silently loses the watchdog entirely. The config/help wording overpromises termination.
- recommendation: Until process workers exist, document the timer as best-effort and reject execution modes where it is disabled. For a hard limit, isolate per-file untrusted work in a killable subprocess, terminate and reap it after deadline, and bound IPC payload/memory. Preserve the writer exclusion.
- acceptance_evidence:
  - A deliberately non-cooperative child is terminated near the configured deadline and the batch continues.
  - No zombie workers or partial artifact writes remain.
  - Runtime documentation distinguishes cooperative alarm behavior from process termination.

### ISSUE-007 — Hard-kill temp residue can permanently block retry

- severity: `medium`
- confidence: `high`
- first_pass: `2`
- async_area: `retry-backoff-and-poison-message-handling`
- issue_type: `dlq-replay-recovery-gap`
- verification: `verified control flow; hard-kill path not covered by tests`
- evidence:
  - `src/docmend/writer/atomic.py:42-59` uses the deterministic name `.<target>.docmend-tmp` with `O_EXCL`.
  - Cleanup runs only through caught exceptions; SIGKILL/power loss bypasses it.
  - A later retry encounters the existing temp at staging and returns `WriteError` (`src/docmend/writer/atomic.py:62-67`) without proving whether the residue is stale, linked to the target, or from a live writer.
  - Tests cover injected exceptions and a post-link temp-unlink residue, but not a process killed after temp creation and a successful automatic retry.
- risk: One interrupted file can become a repeatable ERR-003 failure until the operator discovers and removes a hidden file. If the temp is a second hard link after no-clobber publish, residue also retains sensitive content and complicates reconciliation.
- recommendation: Use unique securely created same-directory temp names recorded in intent, or implement conservative stale-temp inspection/reclamation under the root lock. Reconciliation must compare inode/hash and never delete an unknown live writer's file. Document cleanup only after it is machine-safe.
- acceptance_evidence:
  - Kill after temp create/write/fsync/link, then resume without manual cleanup.
  - Residues from unrelated or live processes are never removed.
  - Successful completion leaves no stale temp aliases.

### ISSUE-008 — Resume attempts lack durable logical-workflow lineage and one-command compensation

- severity: `medium`
- confidence: `high`
- first_pass: `3`
- async_area: `workflow-orchestration-and-state-progression`
- issue_type: `workflow-state-progression-gap`
- verification: `verified repo behavior`
- evidence:
  - Every resume attempt receives a new run ID and writes a separate manifest; `src/docmend/cli.py:606-644` loads an operator-supplied list but does not persist a parent/attempt chain.
  - `src/docmend/writer/manifest.py:44-75` has run/action identity but no `workflow_id`, parent attempt, plan reference, or complete prior-manifest set.
  - `docmend restore` accepts exactly one manifest/run ID (`src/docmend/cli.py:665-756`).
  - Both runbooks require the operator to discover every attempt and restore/verify them manually newest-first.
- risk: Omitting one attempt or restoring in the wrong order leaves only part of a logical apply compensated. Sidecars can be relocated, and timestamps/run IDs do not prove parentage. Recovery correctness depends on incident-time manual bookkeeping.
- recommendation: Persist a logical workflow ID, plan digest, attempt number, parent manifest digest, and prior-attempt set in a run header or companion artifact. Add a command that discovers/verifies the complete chain and previews/applies compensation newest-first as one guarded workflow.
- acceptance_evidence:
  - A multiply interrupted apply is restored by one command from any attempt ID.
  - Missing, duplicate, forked, or reordered attempts refuse with an actionable chain error.
  - Verification proves the logical workflow's union of mutations exactly once.

### ISSUE-009 — Terminal report publication is outside the durable run transaction

- severity: `medium`
- confidence: `high`
- first_pass: `3`
- async_area: `observability-alerting-and-runbooks`
- issue_type: `observability-runbook-gap`
- verification: `verified repo behavior`
- evidence:
  - `src/docmend/writer/apply.py:625-704` retains outcomes in memory and returns the report only after the loop.
  - `src/docmend/cli.py:537-584` releases the root lock before `artifacts.write_report`.
  - The gate preflights the sidecar manifest directory, not an arbitrary custom report destination.
  - A kill mid-run leaves manifest/log evidence for some events but no DR-003 report with explicit `running`, `interrupted`, or terminal status.
- risk: The corpus can be mutated and the manifest durable while the authoritative report is absent or fails publication. Another run can begin after lock release while the previous command has not finalized. Skips/failures, which are not manifest mutations, are especially hard to reconstruct after interruption.
- recommendation: Preflight the actual report destination before writes; persist a small run header/status (`started`, progress checkpoint, terminal outcome); finalize the report inside the guarded run lifecycle; define recovery when final publication fails. Keep sensitive content out of status records.
- acceptance_evidence:
  - Unwritable custom report path refuses before mutation.
  - Kill/report-write fault leaves a machine-readable interrupted state and reconstructable totals.
  - Lock release occurs only after the documented terminal state is durable.

### ISSUE-010 — Whole-run state grows with file count and has no enforceable capacity envelope

- severity: `medium`
- confidence: `high`
- first_pass: `3`
- async_area: `throughput-backpressure-and-capacity`
- issue_type: `throughput-backpressure-gap`
- verification: `verified repo behavior and checked-in benchmark evidence`
- evidence:
  - Discovery accumulates all files/skips/symlinks; planning accumulates pending/actions/skips; apply accumulates all outcomes before report publication.
  - `tests/test_scale.py:39-51` explicitly states O(file-count) memory and reports about 477.4 MiB traced peak for 100,000 files.
  - `tests/test_scale.py:194-205` enforces a count-proportional ceiling rather than the spec's stated memory independence from corpus size.
  - The opt-in scale test is not part of the default CI run.
- risk: The measured target corpus fits, but larger or metadata-heavy runs can exhaust memory with no admission control, spill strategy, or multi-size regression curve. Parallelism, if later added, would multiply per-worker memory unless explicitly budgeted.
- recommendation: Align the approved requirement with actual O(n) metadata if that is acceptable, define a supported file-count/memory envelope, test several sizes, and fail before mutation when the plan/report cannot fit. If independence is required, stream/spool artifact records and aggregate counts incrementally. Budget future worker count against memory.
- acceptance_evidence:
  - Requirement, docs, and tests assert the same asymptotic model.
  - Multi-point benchmarks show expected slope and enforce an operator-visible capacity limit.
  - Process mode, if enabled, includes aggregate worker/parent memory assertions.

### ISSUE-011 — Destructive manifest consumers lack an explicit compatibility and run-invariant gate

- severity: `medium`
- confidence: `high`
- first_pass: `5`
- async_area: `payload-design-and-versioning`
- issue_type: `payload-versioning-gap`
- verification: `verified repo behavior`
- evidence:
  - `src/docmend/writer/manifest.py:44-75` accepts any `1.x` schema version.
  - `read_manifest` validates records independently but does not reject future minors or enforce one run ID, source root, monotonic sequence, unique action/terminal records, or valid intent closure (`src/docmend/writer/manifest.py:138-166`).
  - Apply explicitly rejects future plan minors, but restore/verify/resume do not apply an equivalent future-manifest policy.
  - Restore orders records solely by supplied `seq` (`src/docmend/restore.py:121-125`).
- risk: An older executable can destructively interpret a future or structurally mixed manifest whose individual rows pass the old schema. Corrupt ordering or duplicated terminal evidence can alter replay/reconciliation decisions.
- recommendation: Parse a run-level manifest envelope/header first; reject unsupported future minors before path access; enforce run/root/sequence/action/intent invariants; then validate records against the version-specific schema. Preserve explicit golden compatibility fixtures for supported historical minors.
- acceptance_evidence:
  - Future-minor restore/resume/verify inputs refuse before reading referenced files.
  - Mixed run IDs/roots, sequence gaps/duplicates, duplicate terminal records, and invalid intent closures have dedicated tests.
  - Historical 1.0-1.3 fixtures follow a documented compatibility matrix.

### ISSUE-012 — Standalone scan and verify can observe an active mutation run

- severity: `low`
- confidence: `high`
- first_pass: `4`
- async_area: `ordering-concurrency-and-reentrancy`
- issue_type: `ordering-concurrency-reentrancy-gap`
- verification: `verified repo behavior`
- evidence:
  - Plan shorthand, apply, and restore acquire the root lock; standalone `scan` and `verify` do not (`src/docmend/cli.py:135-204,768-865`).
  - Verify performs a whole-tree scan followed by manifest/report reconciliation, so a concurrent apply can change state between those phases.
- risk: Read-only commands can produce cross-time inventories or transient verify findings while a writer is active. Hash checks prevent later unsafe apply, so the primary impact is operator confusion and unreliable promotion/incident evidence rather than data loss.
- recommendation: Either acquire a shared/exclusive root lock for snapshot-sensitive scan/verify, refuse when a writer is active, or stamp artifacts as potentially concurrent and require a quiescent verify for authoritative results.
- acceptance_evidence:
  - A verify started during apply deterministically refuses/waits or is explicitly non-authoritative.
  - Authoritative inventory/verify artifacts are produced from a quiescent root.

### ISSUE-013 — Durable conventions do not cover the repository's recovery protocol

- severity: `low`
- confidence: `high`
- first_pass: `4`
- async_area: `cross-cutting`
- issue_type: `missing-conventions`
- verification: `verified documentation gap`
- evidence:
  - `docs/handoff/conventions.md` contains tooling, spec, ADR, sensitive-data, frontmatter, and standard-ownership rules, but no runtime rules for write-ahead transitions, replay validation, idempotent convergence, lock ownership, timeout semantics, or kill-boundary tests.
  - Those rules are spread across spec prose, ADRs, module comments, runbooks, and tests; several currently conflict with runtime behavior (ISSUE-002, ISSUE-003, ISSUE-005, ISSUE-006).
- risk: Future changes can preserve local tests while weakening cross-file recovery invariants because there is no concise convention identifying which transitions require prior durable evidence and which public layer owns mutation coordination.
- recommendation: After the owner resolves the behavioral findings, add a compact numbered repo-specific workflow/recovery convention. Do not use a convention to bless current contradictions; align spec/ADR/code/tests first.
- acceptance_evidence:
  - The convention names coordinator ownership, prepare/commit/reconcile rules, replay trust boundary, schema/version policy, and required hard-kill tests.
  - Cross-links from ADRs/runbooks point to one current invariant set.

## High-Risk Failure Paths

1. Operator supplies or selects a mixed/crafted manifest -> CLI locks the first recorded root -> restore trusts absolute paths -> file outside that root is rewritten or renamed (ISSUE-001).
2. Apply atomically rewrites/renames one file -> process dies before `_record` append -> corpus changed but manifest/report omit the mutation -> resume can only infer symptoms and restore lacks the backup pointer (ISSUE-002).
3. Restore reinstates an original path -> process dies before target removal/replacement -> both paths survive -> rerun returns collision -> incident recovery becomes manual (ISSUE-003).
4. External wrapper calls `execute_plan(write=True)` or `run_restore(write=True)` directly -> no CLI lock/gate -> concurrent or unpreserved mutation (ISSUE-004).
5. Per-file native detector stalls -> SIGALRM is pending but Python handler cannot run -> unattended batch exceeds configured timeout indefinitely (ISSUE-006).
6. Process dies after fixed temp creation -> retry hits `O_EXCL` -> same action fails until hidden residue is manually interpreted (ISSUE-007).
7. Apply is interrupted multiple times -> manifests form an implicit chain -> operator misses/reorders one during restore -> logical run is only partially compensated (ISSUE-008).

## Delivery Guarantees And Idempotency

- trigger model: manual invocation; no queue, broker, consumer acknowledgment, visibility timeout, lease, or scheduler is present or needed.
- work delivery: immutable plan actions are enumerated sequentially. Failed/skipped actions are not automatically retried; the operator reruns plan/apply.
- effective guarantee: manual at-least-once attempts with application-level deduplication, not exactly once.
- deduplication strengths:
  - source hashes prevent executing stale plan decisions;
  - manifest after-hashes confirm completed actions;
  - `already-applied` reconciliation avoids replaying recorded success;
  - run lock serializes guarded plan/apply/restore on one root;
  - collision and hard-link policies avoid unsafe aliasing.
- deduplication gaps:
  - completed-but-unrecorded single-step mutations cannot be proven from journal evidence (ISSUE-002);
  - restore cannot reconcile some partial inverse states (ISSUE-003);
  - raw engines can bypass locking/gating (ISSUE-004);
  - attempt lineage and manifest invariants are not durable (ISSUE-008, ISSUE-011).
- exactly_once_assumption: the spec/runbook language sometimes equates an atomic per-file mutation plus post-write append with exactly-once recorded mutation. That is not established across the corpus+journal boundary.

## Guarantee Boundaries And Side-Effect Coordination

- filesystem visibility boundary: `atomic_write_bytes` and rename primitives generally provide intact old-or-new file visibility.
- audit boundary: `ManifestWriter.append` flushes and fsyncs individual records and fsyncs the manifest parent on first creation.
- coordination gap: these two boundaries are separate transactions. Only `rename_and_rewrite` currently receives a pre-side-effect intent; rewrite, rename, and restore inverse transitions do not (ISSUE-002, ISSUE-003).
- report boundary: DR-003 is memory-resident until the loop ends and published after the root lock is released (ISSUE-009).
- lock boundary: CLI coordination is sound for its guarded paths, but not enforced by public write engines (ISSUE-004).
- outbox_inbox: `not needed for this repo`; no remote side effect or database transaction exists. The local equivalent should be a complete write-ahead journal protocol.
- compensation: verified tool backups plus hashes are strong when present; external-preservation runs are intentionally only partially restorable by docmend and are disclosed as such.

## Retry, Replay, And Recovery Risks

- retries: none automatic by design; this avoids retry storms and unsafe blind repetition.
- poison input: binary/ambiguous/timeout files are classified and skipped; this is an appropriate local quarantine instead of a DLQ.
- replay safety gaps: outside-root restore (ISSUE-001), missing single-step intent (ISSUE-002), non-convergent inverse (ISSUE-003), stale temp blocking (ISSUE-007), manual chain assembly (ISSUE-008), and weak manifest run/version invariants (ISSUE-011).
- backoff_and_jitter: `not needed for this repo`; no provider quotas, remote calls, or automatic retry loops exist.
- dead_letter_queue: `not needed for this repo`; reports/skips are the operator-visible equivalent.
- recovery strength: backup hashes are verified before restore; live outputs are after-hash gated; restore is dry-run by default; corrupt interior manifest lines hard-abort.

## Scheduling And Workflow State Risks

- scheduling_cron_periodic_work: `not needed for this repo`; spec appendix C.2 and runtime section 18.1 make product execution manual.
- time_zone_dst_clock: not relevant to product scheduling. Run IDs and timestamps are evidence labels, not scheduled trigger decisions.
- state source of truth: immutable plan plus per-attempt manifest is the intended source. Report/log are supporting evidence.
- state progression gaps:
  - no durable logical workflow/attempt graph (ISSUE-008);
  - no pending/commit state for several mutations (ISSUE-002, ISSUE-003);
  - no durable run terminal state on interruption (ISSUE-009);
  - future/mixed manifest semantics are not rejected consistently (ISSUE-011).
- compensation ordering: records within one manifest are LIFO by sequence; multi-attempt manifests rely on manual newest-first invocation.

## Throughput, Backpressure, And Capacity

- current execution: sequential, single-process, single-file-at-a-time content work; this naturally bounds active file bytes and prevents worker queues from growing.
- configured process pool: absent despite accepted settings (ISSUE-005).
- memory: whole inventory, plan, and report collections grow with file count; checked-in 100k evidence reports about 477 MiB traced peak (ISSUE-010).
- scale evidence: an opt-in seeded 100k pipeline test exists with timing/memory data; it is slow-marked and skipped from the normal gate.
- backpressure controls: no producer/consumer queue exists; `not needed for this repo` under sequential mode.
- future process-mode requirements: bound submitted tasks, keep parent-only manifest/report writes, terminate timed-out workers, budget aggregate memory, and prove unordered completion cannot change plan/output semantics.

## Operational Controls And Visibility

- strengths:
  - per-run IDs and JSONL logs;
  - stable exit taxonomy;
  - dry-run defaults for apply/restore;
  - root lock for guarded plan/apply/restore;
  - per-action manifest hashes and outcomes;
  - restore/resume runbooks;
  - verify reconciliation.
- gaps:
  - restore path/root validation (ISSUE-001);
  - guarded coordinator is bypassable (ISSUE-004);
  - no hard timeout for non-cooperative work (ISSUE-006);
  - no workflow-chain command (ISSUE-008);
  - no durable interrupted/terminal report state (ISSUE-009);
  - scan/verify can observe active mutation (ISSUE-012).
- alerts_metrics_health_endpoints: `not needed for this repo`; the equivalent is exit status plus artifact/log review. If an external scheduler runs docmend, that scheduler must alert on missing terminal artifacts as well as non-zero exit.

## Async Testing Gaps

- Add real subprocess SIGKILL/power-loss analog tests at every mutation/journal boundary for rewrite, rename, rename-and-rewrite, overwrite, restore, and report finalization (ISSUE-002, ISSUE-003, ISSUE-007, ISSUE-009).
- Add hostile/mixed manifest tests covering all replay paths and backup references (ISSUE-001, ISSUE-011).
- Replace the test expectation that a rerun remains a collision after partial restore with convergence or explicit interference semantics (ISSUE-003).
- Add a non-cooperative native/child timeout test; existing Python-loop tests do not prove hard cancellation (ISSUE-006).
- Add guarded-service integration tests so library/wrapper calls cannot bypass gate/lock (ISSUE-004).
- Add multi-attempt chain restore/verify tests with missing/forked/reordered attempts (ISSUE-008).
- Add report-destination and post-mutation report-publication fault tests (ISSUE-009).
- Add multi-size scale tests or a cheaper analytical capacity test to enforce the chosen memory slope; keep the full 100k drill periodic/release-gated (ISSUE-010).
- Add scan/verify-versus-apply concurrency tests for the selected authoritative snapshot policy (ISSUE-012).

## Convention Recommendations

### Shared Across Projects

1. Every externally visible side effect in a retryable workflow must have durable prior intent or an equivalent atomic coordination mechanism; success records written only afterward are not exactly-once evidence.
2. Every retry/replay path must converge from each interruption boundary or stop with an explicit external-interference classification; safe residue alone is not resumability.
3. Treat durable replay artifacts as untrusted inputs: validate supported version, run identity, ordering, root/tenant scope, path/resource authorization, and integrity before side effects.
4. Unsupported concurrency, queue, retry, or timeout modes must fail configuration; never accept operational no-op settings.
5. The public write boundary must own locks, gates, idempotency, and terminal artifacts; raw mutation loops stay private.
6. Use real process-kill tests for crash guarantees. Exception mocks are useful but do not exercise cleanup bypass, buffered I/O loss, or process-owned locks.

### Repo-Specific

1. Keep the synchronous manual CLI, no-broker, no-scheduler posture until profiling and a spec/ADR change justify process workers. Asyncio, DLQs, outbox/inbox, cron, and service heartbeats are `not needed for this repo` today.
2. Extend manifest 1.x only through the approved artifact/spec process, with a run-level envelope and prepare/commit/reconcile rules for apply and restore.
3. Define one guarded `apply` service and one guarded `restore` service as the only production mutation entrypoints, including the private sibling wrapper boundary from ADR-0018.
4. Define whether authoritative standalone scan/verify commands take a shared/exclusive root lock or explicitly refuse during writers.
5. Record the accepted file-count/memory envelope and process-worker reopen criteria in one current convention after owner approval.

## Pass Log

| Pass | Lens | New issues | Result |
| --: | --- | --- | --- |
| 1 | Surface inventory, ownership, topology, trigger paths, transaction seams, highest-risk failure paths | ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-004 | Confirmed synchronous manual workflows; found replay-containment, journal-atomicity, restore-convergence, and coordinator-boundary gaps. |
| 2 | Idempotency, deduplication, retry, poison input, timeout/cancellation, lease semantics, code-to-convention alignment | ISSUE-005, ISSUE-006, ISSUE-007 | Confirmed no broker/lease surface; found no-op process settings, cooperative watchdog limits, and hard-kill temp residue. |
| 3 | Concurrency, ordering, backpressure, recovery, workflow progression, compensation, capacity | ISSUE-008, ISSUE-009, ISSUE-010 | Found manual attempt lineage, non-durable terminal report, and O(file-count) capacity envelope. |
| 4 | Lower-severity tests, observability, runbooks, operator ergonomics, convention quality | ISSUE-012, ISSUE-013 | Found non-quiescent scan/verify evidence and missing durable recovery conventions. |
| 5 | Adaptive deepening: manifest compatibility and run-wide replay invariants | ISSUE-011 | Found destructive future-minor/run-invariant acceptance gap. |
| 6 | Adversarial verification of all findings against tests, spec, ADRs, runbooks, and release baseline | none | No new issue; confidence/severity calibrated and overlaps merged. |
| 7 | Final convergence pass across excluded/non-applicable categories and evidence gaps | none | Second consecutive no-new-issue pass; review converged. |

## Claude Handoff

- highest_priority_sequence:
  1. Fix ISSUE-001 before relying on restore against any artifact not generated and protected in the same trusted session.
  2. Design one prepare/commit/reconcile protocol covering ISSUE-002 and ISSUE-003; update spec/ADRs/runbooks/tests together because current documents explicitly promise stronger behavior.
  3. Close ISSUE-004 by making guarded application services the production mutation boundary.
  4. Reject or implement parallel mode (ISSUE-005) and correct watchdog wording/behavior (ISSUE-006).
  5. Add attempt lineage, terminal state, temp recovery, and version/run invariants (ISSUE-007 through ISSUE-011).
- suggested_change_shape: owner-approved spec/ADR correction first, then manifest/run-state schema design, then implementation and hard-kill tests. Do not patch only runbook wording for ISSUE-001 through ISSUE-004.
- follow_on_reviews:
  - `security review` for replay path authorization and symlink/TOCTOU behavior (ISSUE-001).
  - `data-schema-migration-review` for run envelope, future-version policy, and historical manifest migration (ISSUE-008, ISSUE-011).
  - `observability-review` and `incident-readiness-review` for durable run terminal state and external scheduler expectations (ISSUE-009).
  - `performance-review` for the supported capacity envelope and any process-pool reopen (ISSUE-005, ISSUE-010).
  - `test-suite-review` for real-kill coverage and current tests that encode non-convergence.
- convention_changes_after_behavior_is_settled: add a repo-specific workflow/recovery convention covering guarded entrypoints, prepare/commit/reconcile, artifact trust, hard-kill testing, and supported execution modes.
- preserve_current_strengths: dry-run defaults, per-file hashes, strict plans, parent/root lock, verified backups, torn-tail refusal policy, classified skips, parent-only artifact-write design intent, and no automatic retry storm.

## Open Questions Or Assumptions

1. Is the supported threat model strictly one trusted operator with protected manifests, or must restore remain safe when a manifest is copied, edited, recovered from backup, or supplied by external tooling? The shared research and public CLI posture support validating it as untrusted either way.
2. Must RPO zero and "every mutation reversible" include the low-risk no-backup opt-in, or is that accepted exception fully represented by WH-009? This does not remove ISSUE-002 for tool-backup runs because the manifest pointer itself can still be orphaned.
3. Is O(file-count) memory with the measured 100k envelope acceptable? The current requirement language and the scale test assert different models.
4. Should authoritative scan/verify block on an active writer, refuse immediately, or emit a non-authoritative marker?
5. Will the private sibling wrapper call only the CLI, or does it import raw engines? That external boundary was not verified.
6. What historical manifest minors must remain restorable, and is an explicit migration/inspection command acceptable for legacy records without `source_root`?
7. Are external Git/restic/Borg snapshots always taken before apply and retained through the needed restore window? This is unverified-external and affects only externally preserved runs.

## Residual Risk

- Even after protocol fixes, local POSIX atomic rename and fsync behavior varies by filesystem/mount; power-loss durability must be stated against the supported matrix and tested where practical.
- Hashes detect drift but do not authenticate a manifest or backup when an attacker can rewrite both. Add signatures/MACs only if the threat model requires tamper authenticity; containment/version/run validation is required regardless.
- External writers are not coordinated by docmend's `flock`; apply-time hashes reduce but cannot eliminate every pathname/identity race in a mutable tree.
- External preservation, private wrappers, and operator orchestration remain outside-repo guarantees until independently verified.
- No queue, broker, scheduler, webhook, remote API, database transaction, or resident service exists; risks specific to those categories are `not needed for this repo` at this baseline and must be reviewed if introduced later.
