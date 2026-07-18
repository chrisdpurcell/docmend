# Incident Readiness Review

## Findings

### ISSUE-001: Mutation journals are not write-ahead for every apply and restore operation

- first_pass: `1`
- severity: `high`
- confidence: `high`
- incident_area: `stateful-recovery-and-data-safety`
- issue_type: `stateful-recovery-gap`
- evidence_status: `verified directly from repository code, tests, and runbooks`
- evidence:
  - `src/docmend/writer/apply.py:483-583` appends an `intent` before mutation only for `rename_and_rewrite`; ordinary `rewrite` and `rename` mutate first and append their final record afterward.
  - `tests/test_resume.py:233-263` explicitly accepts a completed rewrite whose trailing record was lost: resume returns `stale-hash`; the equivalent rename returns `unreadable`. Neither path reconstructs the missing applied record.
  - `src/docmend/restore.py:232-284` performs the inverse mutation before appending its inverse record. A restore has no write-ahead state.
  - `tests/test_restore.py:459-513` proves a failed mid-record restore leaves both original and applied target present; rerun stops at a collision rather than converging.
  - `docs/runbooks/resume-after-interruption.md:8-16` calls the manifest complete up to the kill, while `:54-56` acknowledges a completed mutation can have no record.
- impact: `A crash can leave a corpus mutation or half-restore without durable ledger evidence. Resume may avoid a second mutation, but automated restore, report reconciliation, and incident scoping cannot prove what happened. For external-preservation runs, the missing record can be the only repo-local evidence identifying the changed file.`
- recommendation: `Record a durable intent before every apply mutation and every restore mutation, including pure rename/rewrite and inverse operations. Define deterministic reconciliation for each pre/post state, and do not treat atomic visibility as journal completeness.`
- acceptance_evidence:
  - `SIGKILL/fault injection at every boundary between backup, intent, publish/unlink, applied record, and report leaves a state that resume or restore deterministically converges.`
  - `Every completed mutation is represented by a durable intent or applied record before a clean terminal status is possible.`

### ISSUE-002: Restore and verify do not enforce manifest-to-root containment

- first_pass: `1`
- severity: `high`
- confidence: `high`
- incident_area: `failure-containment-and-blast-radius`
- issue_type: `failure-containment-gap`
- evidence_status: `verified directly; external threat model remains an open assumption`
- evidence:
  - `src/docmend/schemas/manifest.schema.json:48-60,93-96` permits arbitrary absolute `original_path`, `target_path`, and backup paths; `source_root` is optional.
  - `src/docmend/cli.py:379-394,740-756` derives the restore lock from only the first record's `source_root` or a legacy common path.
  - `src/docmend/restore.py:106-258` reads and mutates every record path without checking that all records share one root or remain beneath it.
  - `src/docmend/verify.py:88-114` hashes manifest targets without proving they belong to the requested verify tree.
  - Apply-time intent reconciliation has explicit containment checks (`src/docmend/writer/apply.py:236-249`), demonstrating that the manifest is already treated as untrusted on one path but not restore/verify.
- impact: `A wrong, concatenated, corrupted, or crafted manifest can make restore mutate files outside the declared library. Verify can return clean while checking a different tree, expanding a recovery mistake beyond the intended blast radius.`
- recommendation: `Require one consistent resolved source_root for modern manifests; enforce every original and target path beneath it at read time and immediately before mutation; bind verify PATH to that root; and require an explicit trusted root or migration step for legacy manifests.`
- acceptance_evidence:
  - `Mixed-root, outside-root, wrong-tree verify, symlink-parent swap, and legacy-manifest tests all fail safely before path access or mutation.`

### ISSUE-003: Hash and containment preconditions are not held through commit

- first_pass: `2`
- severity: `high`
- confidence: `medium`
- incident_area: `failure-containment-and-blast-radius`
- issue_type: `failure-containment-gap`
- evidence_status: `direct code evidence; severity depends on whether editors, sync tools, or other writers may touch the tree during a run`
- evidence:
  - Apply reads and hashes a pathname (`src/docmend/writer/apply.py:351-386`), then performs backups and later pathname-based mutation (`:416-583`). The docmend run lock excludes other docmend runs, not external writers.
  - Restore hashes the live target (`src/docmend/restore.py:83-103`), later stats it (`:153-176`), then mutates through the pathname (`:232-258`).
  - The shared research pack identifies path identity and check-to-use drift as a filesystem trust boundary and recommends validating the opened object at mutation time.
- impact: `An editor, sync client, indexer, or other local process can replace content after validation. Apply or restore can then overwrite newer bytes while reporting hashes for the object checked earlier, violating the stated modified-since-apply and stale-plan containment guarantees.`
- recommendation: `Bind validation, backup, transform, and commit to the same opened file identity using descriptor-relative/no-follow operations where supported, or re-stat and re-hash the exact object immediately before publication and refuse on identity drift. Document quiescence if concurrent non-docmend writers are unsupported.`
- acceptance_evidence:
  - `Deterministic replacement-between-check-and-commit tests for rewrite, rename, rename-and-rewrite, overwrite, and restore preserve the external writer's bytes and emit a safety finding.`

### ISSUE-004: Verify can certify a run after its recovery bytes disappear

- first_pass: `2`
- severity: `high`
- confidence: `high`
- incident_area: `stateful-recovery-and-data-safety`
- issue_type: `stateful-recovery-gap`
- evidence_status: `verified directly from the verification contract and implementation`
- evidence:
  - `src/docmend/verify.py:88-114` checks only the live target against `after_sha256`.
  - It never reads `backup_path`, `before_sha256`, `overwritten_backup_path`, or `overwritten_sha256`.
  - `docs/specs/docmend.md` sections 18.5-18.6 present verify and backup recovery as the evidence for zero original-content loss.
  - The automated restore drill proves recovery immediately after apply, but there is no test that deletes or corrupts a recorded backup and expects verify to fail before an incident.
- impact: `A run can remain content-clean while its only tool-managed rollback bytes are missing or corrupt. The operator receives a clean verification verdict and discovers the loss only during restore, after the recovery decision has become urgent.`
- recommendation: `Add a recoverability verification mode that validates every tool backup and clobbered-target backup against its recorded before-hash, reports external-preservation records as externally unverifiable rather than clean, and emits a durable result.`
- acceptance_evidence:
  - `Missing, unreadable, corrupt, and wrong backup files are findings; a fully healthy tool-backup run proves both live after-state and recoverable before-state.`

### ISSUE-005: The restore runbook cannot prove the corpus returned to its pre-apply state

- first_pass: `1`
- severity: `high`
- confidence: `high`
- incident_area: `stateful-recovery-and-data-safety`
- issue_type: `stateful-recovery-gap`
- evidence_status: `verified directly from the runbook and CLI surface`
- evidence:
  - `docs/runbooks/restore-from-manifest.md:60-66` runs `docmend scan <tree>` and says the result “should match” the original inventory, but gives no comparison command or pass/fail invariant.
  - Inventory records do contain per-file hashes (`src/docmend/inventory.py:70-80`), but the product has no full pre-state reconciliation command.
  - Partial restore verification is explicitly a manual spot-check, which conflicts with the repository's scale premise and mechanical-safety convention.
  - `docmend verify --manifest` proves the post-apply after-state, not the restored before-state.
- impact: `A restore can exit 0 yet leave missing, unexpected, or wrong-but-valid UTF-8/LF files, especially across a multi-attempt resume chain. There is no executable evidence that the claimed zero-RPO recovery point was reached.`
- recommendation: `Add a full restore-verification workflow that preserves the pre-apply inventory/hash set, enumerates all manifests in required LIFO order, compares every expected path and before-hash, detects extras/missing files, and saves the result before backups are purged.`
- acceptance_evidence:
  - `The runbook ends in one automated command/artifact whose clean result proves exact path-and-byte equivalence to the selected recovery point.`

### ISSUE-006: Apply does not durably represent every plan action or terminal run state

- first_pass: `3`
- severity: `medium`
- confidence: `high`
- incident_area: `incident-detection-and-triage`
- issue_type: `detection-triage-gap`
- evidence_status: `verified directly from apply, report, and verify code`
- evidence:
  - A fail-policy collision stops the apply loop (`src/docmend/writer/apply.py:389-396,633-688`); actions after the abort are absent rather than recorded as `not_attempted` or `aborted`.
  - Report totals reconcile only with outcomes that exist (`src/docmend/report.py:53-86`); no rule binds all plan actions to terminal outcomes.
  - `reconcile_report` compares only applied report actions with applied manifest records (`src/docmend/verify.py:117-150`), so report+manifest can agree while later plan actions were never attempted.
  - `src/docmend/cli.py:537-584` releases the run lock before publishing the report, and the gate preflights only the manifest directory (`src/docmend/writer/gate.py:184-232`), not a custom report path.
  - Interrupted apply/restore paths have no explicit terminal log event; an apply report is written only after the engine returns.
- impact: `Incident triage cannot reliably distinguish completed, aborted, interrupted, and report-publication-failed runs. A clean cross-artifact check can hide pending plan actions, and another run can start while the prior run's terminal audit artifact is not finalized.`
- recommendation: `Model a durable run terminal state and require every plan action to have one terminal outcome, including not-attempted/aborted. Preflight and finalize the report inside the guarded run lifecycle; preserve enough state to reconstruct a report after publication failure.`
- acceptance_evidence:
  - `Abort, SIGINT, report-write failure, and collision-fail tests produce explicit terminal state and complete action coverage; verify fails on omitted actions.`

### ISSUE-007: Verify can exit clean after checking zero usable files

- first_pass: `2`
- severity: `high`
- confidence: `high`
- incident_area: `incident-detection-and-triage`
- issue_type: `detection-triage-gap`
- evidence_status: `verified directly; same-sweep isolated reproduction corroborates the code path`
- evidence:
  - Discovery records unreadable and timeout candidates as skips rather than `FileRecord` values (`src/docmend/inventory.py:89-92,111-123`).
  - Verify builds findings only from `inventory.files` plus optional artifact reconciliation (`src/docmend/cli.py:843-865`; `src/docmend/verify.py:36-81`).
  - It never turns unreadable or timeout scan skips into findings. The all-skipped state therefore prints `0 files checked, 0 findings` and exits 0.
- impact: `A pathological, unreadable, or permission-denied corpus can disappear from the verification population while the promotion/incident check reports success.`
- recommendation: `Treat unreadable and timeout scan skips as verification findings; display requested candidates, checked files, policy exclusions, and error skips separately; never emit a clean result when requested candidates could not be checked.`
- acceptance_evidence:
  - `Unreadable-only, timeout-only, mixed checked/skipped, and all-candidates-skipped tests return a non-clean verdict with durable counts.`

### ISSUE-008: Restore and verify lack complete machine-readable response artifacts

- first_pass: `3`
- severity: `medium`
- confidence: `high`
- incident_area: `incident-detection-and-triage`
- issue_type: `detection-triage-gap`
- evidence_status: `verified directly from CLI and logging behavior`
- evidence:
  - Verify prints findings and a count but writes no verify report (`src/docmend/cli.py:831-865`). Its log records a start and reused scan events, not each finding or a terminal verdict.
  - Restore writes an inverse manifest only for successful mutations; it emits no report for skips/failures (`src/docmend/cli.py:748-764`; `src/docmend/restore.py:106-143`).
  - Per-record restore details are logged at INFO (`src/docmend/restore.py:131-139`), while the default console threshold is WARNING (`src/docmend/observability.py:48-60`). The CLI prints only aggregate counts and does not print the log path.
  - `docs/runbooks/restore-from-manifest.md:37-40` says each skip/failure is listed with a reason, which is not true at default verbosity.
- impact: `Automation and an operator under pressure receive an exit code and counts without a stable per-file incident record. Evidence can be lost with terminal scrollback, and the runbook sends the operator looking for details that are hidden in an unadvertised log file.`
- recommendation: `Define versioned restore and verify report artifacts with input references, per-file outcomes, start/completion, terminal status, and counts. Print their paths; make default restore output list non-success details or point directly to the report.`
- acceptance_evidence:
  - `Clean, finding, refusal, and interrupted runs all leave parseable reports whose terminal state and counts match CLI exit status.`

### ISSUE-009: External preservation declarations are not bound to a recovery point

- first_pass: `1`
- severity: `medium`
- confidence: `high`
- incident_area: `manual-mitigation-and-maintenance-modes`
- issue_type: `manual-mitigation-gap`
- evidence_status: `verified directly; health of the owner's external backup regime is outside the repo`
- evidence:
  - `src/docmend/writer/gate.py:58-113` treats any `--preserved-by git|external` declaration as an active byte-preserving strategy without validating or recording a concrete recovery point.
  - `src/docmend/writer/manifest.py:37-75` has no preservation-kind, commit, snapshot, repository, or operator-reference field.
  - Restore explicitly says it cannot know which strategy covered the run (`src/docmend/cli.py:720-738`) and directs the operator to “whatever preservation” applies.
  - The approved product decision intentionally keeps docmend backend-agnostic, but backend agnosticism does not require losing an opaque operator-supplied recovery reference.
- impact: `During a bad apply, the operator may know that external recovery was claimed but not which Git commit/snapshot, where it lives, whether it covers the exact source root, or how to map changed files to it. Stabilization becomes manual and error-prone.`
- recommendation: `Require or strongly encourage an opaque recovery-point reference for external-preservation runs and persist it in the report/manifest. Add a preflight checklist proving the recovery point exists and covers the selected root without making docmend own the backup backend.`
- acceptance_evidence:
  - `External-preservation artifacts name the strategy and recovery reference; the restore runbook gives exact reference-driven recovery and verification steps.`

### ISSUE-010: Targeted restore silently succeeds when requested IDs do not match

- first_pass: `2`
- severity: `medium`
- confidence: `high`
- incident_area: `customer-support-and-manual-ops`
- issue_type: `manual-ops-support-gap`
- evidence_status: `verified directly from selection and exit-code logic`
- evidence:
  - `src/docmend/restore.py:121-143` filters records by `only_ids` and returns an empty outcome list when none match.
  - `src/docmend/cli.py:758-764` prints all-zero counts and exits 0 because only skipped or failed outcomes are non-clean.
  - Tests cover matching IDs but not no-match or partial-match requests (`tests/test_restore.py:749-772`).
- impact: `A typo, stale ID, or wrong manifest can be interpreted by an operator or wrapper as a successful targeted recovery even though nothing was restored.`
- recommendation: `Reconcile requested IDs against eligible applied records before replay, enumerate unmatched IDs, and return a non-clean finding or input-error status while still processing valid matches.`
- acceptance_evidence:
  - `No-match, partial-match, duplicate-ID, failed/intent-only ID, dry-run, and write tests all make unmatched requests explicit.`

### ISSUE-011: Destructive manifest consumers accept unsupported future minor versions

- first_pass: `2`
- severity: `medium`
- confidence: `high`
- incident_area: `deploy-and-change-safety`
- issue_type: `deploy-change-safety-gap`
- evidence_status: `verified directly from schema/model readers`
- evidence:
  - Manifest models and schema accept any `1.x` version (`src/docmend/writer/manifest.py:37-48`; `src/docmend/schemas/manifest.schema.json:26-27`).
  - `read_manifest` validates and constructs records without rejecting a future minor (`src/docmend/writer/manifest.py:142-170`).
  - Apply explicitly rejects a future plan minor (`src/docmend/cli.py:489-500`), but restore and verify have no equivalent compatibility gate.
- impact: `An older executable can act destructively on a future manifest whose semantic meaning changed while its old structural fields still validate. Recovery is the highest-risk place to guess forward compatibility.`
- recommendation: `Centralize an artifact compatibility matrix and reject unsupported majors and future minors before any path access. Preserve explicitly tested historical-minor support; require migration or a newer executable otherwise.`
- acceptance_evidence:
  - `Restore and verify accept golden supported historical manifests and reject future-minor manifests before locking, reading target paths, or mutating.`

### ISSUE-012: Release controls do not prevent or operationalize a bad-release incident

- first_pass: `3`
- severity: `medium`
- confidence: `high`
- incident_area: `deploy-and-change-safety`
- issue_type: `deploy-change-safety-gap`
- evidence_status: `repository workflow verified; external GitHub tag/release settings not verified`
- evidence:
  - `.github/workflows/release.yml:7-42` publishes on any `v*.*.*` tag with `contents: write`; it does not prove main ancestry, tag signature, tag/package-version equality, lock freshness, or that the full gate passed for the tagged commit.
  - `actions/checkout@v7` is tag-pinned rather than full-SHA-pinned in this privileged workflow (`:19`), while the shared guidance identifies full SHA as GitHub's immutable reference.
  - The release job smoke-tests only `docmend --version` from the wheel (`:31-33`) and rebuilds artifacts in the publish job.
  - `README.md:97-105` starts at tagging and has no failed-release cleanup, withdrawal, bad-version advisory, or corpus-recovery procedure.
  - Installing an older package does not undo documents already mutated by the bad version.
- impact: `A mistaken or compromised tag can distribute a destructive build, and the owner has no rehearsed procedure to stop distribution, identify affected versions/runs, communicate impact, or pair package rollback with corpus recovery.`
- recommendation: `Require main ancestry, signed tag verification, exact version/lock/changelog match, full gate and artifact tests, SHA-pinned actions, and build-once provenance. Add a bad-release runbook covering release withdrawal, replacement policy, affected-run identification, operator advisory, previous-version installation, and manifest/backup recovery.`
- acceptance_evidence:
  - `A non-main, unsigned, mismatched-version, stale-lock, or untested tag cannot publish.`
  - `A tabletop bad-release exercise produces an advisory and exact package-plus-corpus rollback steps.`

### ISSUE-013: Incident runbooks and conventions cover only two recovery cases

- first_pass: `3`
- severity: `medium`
- confidence: `high`
- incident_area: `runbooks-and-escalation`
- issue_type: `runbook-escalation-gap`
- evidence_status: `verified directly from docs/runbooks and the conventions index`
- evidence:
  - The repo has only `restore-from-manifest.md` and `resume-after-interruption.md` runbooks.
  - Neither runbook records an owner, reviewed date, version/schema window, prerequisites, stop/contain condition, evidence to preserve, escalation/decision point, communication step, or post-incident follow-up.
  - There is no runbook for wrong-root/containment breach, corrupt or mismatched manifest, restore failure, sensitive artifact/log disclosure, bad release/schema change, or dependency/release compromise.
  - `docs/handoff/conventions.md` has no incident/runbook/recovery-proof convention, so new operational docs are not required to carry these fields.
  - The shared research incident baseline recommends detection, containment, owner, evidence preservation, recovery, verification, communication, and follow-up for these repo-specific scenarios.
- impact: `The existing commands are discoverable, but an operator can destroy evidence, continue after an unsafe state, use the wrong recovery point, or improvise through a security/release incident.`
- recommendation: `Adopt a repo-specific runbook template and add scenario runbooks for the missing high-risk cases. Add a convention that distinguishes cross-project defaults from docmend-specific exceptions and requires executable recovery verification.`
- acceptance_evidence:
  - `Each high-risk scenario has a reviewed runbook with detection, stop/contain, evidence, owner, action, verification, communication, and learning fields.`

### ISSUE-014: Public incident intake, severity, and communication ownership are undefined

- first_pass: `3`
- severity: `low`
- confidence: `high`
- incident_area: `ownership-and-on-call-boundaries`
- issue_type: `ownership-on-call-gap`
- evidence_status: `verified directly; a formal pager/status page is not needed for this repo`
- evidence:
  - The spec identifies one owner/operator, so a multi-person incident command system and on-call rotation would be artificial.
  - The public repo has no `SECURITY.md`, issue template, vulnerability-reporting path, minimal severity taxonomy, or named release-incident communication channel.
  - GitHub Releases/issues are plausible communication surfaces, but their use is not documented as incident policy.
- impact: `External users do not know how to report a sensitive defect or what response to expect; the owner lacks a minimal rule for when to stop rollout, withdraw a release, or publish an advisory.`
- recommendation: `Document a lightweight solo-owner model: incident owner, severity triggers, stop-ship/stop-rollout criteria, private security intake, GitHub advisory/release-note usage, and handoff rules. Explicitly state that pager and status-page operations are not needed for the local CLI.`
- acceptance_evidence:
  - `A public security/reporting policy and a one-page severity/communication matrix exist and identify the owner and channels.`

### ISSUE-015: Exercise coverage has no recurring incident-drill cadence or recorded field evidence

- first_pass: `4`
- severity: `low`
- confidence: `medium`
- incident_area: `chaos-drill-and-exercise-readiness`
- issue_type: `drill-exercise-gap`
- evidence_status: `automated tests verified; actual owner drills and real-library evidence live outside the repo or have not occurred`
- evidence:
  - `tests/test_restore_drill.py:49-65` provides a strong happy-path synthetic apply/restore byte-equivalence drill.
  - Focused recovery/safety validation passed: `110 passed in 1.77s` for resume, restore, verify, lock, and gate tests.
  - Most interruption coverage is exception/fault injection inside one process, not an actual SIGKILL/power-loss matrix across every durability boundary.
  - The spec calls for a manual drill before the first real-library apply, while `docs/TODO.md` still lists the owner's staged real-library rollout as future work; no drill record/cadence is present.
- impact: `The code has strong regression coverage, but filesystem-specific durability, operator comprehension, external backup recovery, and bad-release/containment response remain unexercised in the real operating environment.`
- recommendation: `Before broad rollout, record a safe-copy drill covering interrupted apply, interrupted restore, missing/corrupt backup, wrong manifest/root, external recovery, and bad release. Repeat after recovery-schema or writer changes and retain privacy-safe results.`
- acceptance_evidence:
  - `A dated drill record identifies environment, scenarios, evidence, recovery point, observed timings, failures, and follow-up without exposing real corpus paths or content.`

## Review Metadata

- review_type: `incident-readiness-review`
- reviewed_at: `2026-07-10`
- repo_path: `.`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- release_baseline: `v1.0.2` at `9b0641bf3250bd3ba1b351609935612bdf8a3d40`
- baseline_comparison: `No src/ or tests/ changes between v1.0.2 and HEAD; incident posture findings apply to the released runtime.`
- working_tree_state: `dirty before review: AGENTS.md modified and docs/codex-reviews/ untracked; those pre-existing artifacts were not edited except this requested report path`
- review_mode: `read-only audit except for this requested report`
- detected_frameworks_and_runtimes: `Python >=3.14 local CLI; Typer/Rich; Pydantic v2; JSON Schema Draft 2020-12; structlog; ruamel.yaml; uv; pytest/Hypothesis; GitHub Actions`
- primary_incident_shape: `offline destructive filesystem batch processing over a potentially sensitive corpus`
- rollback_and_deploy_surfaces_reviewed: `apply preservation gate; atomic writer; manifest 1.3; restore; resume; verify; GitHub tag-to-release workflow; README release process; v1.0.0-v1.0.2 changelog`
- feature_flag_and_kill_switch_surfaces_reviewed: `dry-run/write opt-in; include/exclude rollout filters; preservation modes; collision policy; run lock; low-confidence fail mode; no remote feature-flag service`
- manual_mitigation_surfaces_reviewed: `Ctrl-C/interruption resume; restore dry-run/write; selective restore IDs; Git/external/tool-backup preservation; version rollback`
- runbooks_and_escalation_surfaces_reviewed: `restore and resume runbooks; spec error/recovery sections; README safety model; handoff conventions/status/tasks`
- incident_command_severity_handoff_surfaces_reviewed: `single-owner spec; run IDs; append-only manifest; JSONL logs; apply reports; handoff state/bug/session structure`
- observability_and_triage_surfaces_reviewed: `structured per-run logs; inventory/plan/report/manifest artifacts; exit codes; console summaries; verify findings`
- status_support_customer_communication_surfaces_reviewed: `README, CHANGELOG, GitHub Releases workflow; no SECURITY.md, status page, or documented support/incident channel`
- resilience_and_recovery_surfaces_reviewed: `atomic writes; backups; fsync behavior; intent reconciliation; stale hash checks; containment; restore preflight; verify; automated recovery tests`
- external_incident_surfaces_not_in_repo: `operator's private backup system and recovery points; real corpus and filesystem; editors/sync/indexers; GitHub tag protection/branch protection/release settings; installed user versions; any private vulnerability intake`
- important_incident_readiness_unknowns: `supported filesystem matrix; external-writer quiescence contract; external backup health/retention; first real-library drill outcome; regulatory or breach-notification duties; tag protection and immutable-release settings`
- prior_baseline_or_release_artifacts_compared: `v1.0.2 tag, v1.0.1 partial-undo fix, v1.0.0 initial release, CHANGELOG, current HEAD diff`
- conventions_input: `docs/handoff/conventions.md (repo equivalent of docs/conventions.md)`
- research_used: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md; no broad or targeted follow-up internet research was needed`
- focused_validation: `uv run pytest -q tests/test_resume.py tests/test_restore.py tests/test_verify.py tests/test_cli_verify.py tests/test_lock.py tests/test_gate.py -> 110 passed in 1.77s`
- exclusions: `generated/build output, caches, byte-exact fixture bodies, private real corpus, and orchestrator-owned execution/sweep/live-status artifacts`
- workflow_schema_note: `The consolidated workflow's relative incident report-schema link does not exist; the package's only report-schema.md is for planning reports. This report follows every required incident section and explicit per-finding field named by the consolidated workflow.`

## Incident Readiness Matrix

| Incident area | Relevance | Posture | Evidence / findings |
| --- | --- | --- | --- |
| `incident-detection-and-triage` | high | gap | Structured logs and exit codes exist, but false-clean and incomplete terminal/result states remain (ISSUE-006, ISSUE-007, ISSUE-008). |
| `incident-command-and-severity-model` | low | partial | Solo owner makes formal command unnecessary; minimal severity/stop criteria are absent (ISSUE-014). |
| `rollback-and-revert-readiness` | critical | gap | Restore exists and is tested, but journal windows and post-restore proof are incomplete (ISSUE-001, ISSUE-005). |
| `feature-flags-kill-switches-and-disablement` | high | adequate | Dry-run, explicit write, filters, lock, preservation gate, and collision defaults are strong; remote flags are not needed. |
| `manual-mitigation-and-maintenance-modes` | high | partial | Resume/restore/selective rollback exist; external recovery points are not bound to runs (ISSUE-009, ISSUE-010). |
| `runbooks-and-escalation` | high | gap | Two useful command runbooks exist; scenario, evidence, escalation, and verification coverage is incomplete (ISSUE-005, ISSUE-013). |
| `handoffs-and-decision-logging` | high | partial | Run IDs, logs, reports, manifests, ADRs, and handoff docs are strong; terminal and write-ahead gaps reduce certainty (ISSUE-001, ISSUE-006). |
| `failure-containment-and-blast-radius` | critical | gap | Run locks and apply containment exist; restore root binding and file-identity drift do not (ISSUE-002, ISSUE-003). |
| `dependency-degradation-and-fallbacks` | low | partial | No live remote dependencies; compromised dependency/release response is a runbook gap (ISSUE-012, ISSUE-013). |
| `deploy-and-change-safety` | high | gap | Protected-main process is documented; destructive artifact compatibility and release incident controls are incomplete (ISSUE-011, ISSUE-012). |
| `stateful-recovery-and-data-safety` | critical | gap | Verified backups and happy-path drill are strong; ledger, backup-health, and recovery-point proof gaps remain (ISSUE-001, ISSUE-004, ISSUE-005). |
| `status-page-and-customer-communications` | low | not needed / partial | A status page is not needed for a local CLI; public advisory/support policy is missing (ISSUE-014). |
| `ownership-and-on-call-boundaries` | low | partial | Owner is known; on-call is not needed; incident ownership/intake is not documented (ISSUE-014). |
| `chaos-drill-and-exercise-readiness` | medium | partial | Strong synthetic tests; no recurring real-environment/tabletop cadence (ISSUE-015). |
| `incident-testing-and-validation` | critical | partial | Broad recovery tests pass; several tests codify non-convergent or false-clean outcomes (ISSUE-001, ISSUE-007, ISSUE-010, ISSUE-015). |
| `customer-support-and-manual-ops` | medium | gap | CLI is clear for happy paths; selective restore and per-file failure evidence can mislead operators (ISSUE-008, ISSUE-010). |
| `post-incident-learning-hooks` | medium | partial | Changelog, issue references, ADRs, handoff sessions, and bug records provide durable learning; no explicit incident follow-up template/cadence exists (ISSUE-013, ISSUE-015). |

## Severity Summary

| Severity | Count | Issue IDs |
| --- | --: | --- |
| `critical` | 0 | none |
| `high` | 6 | ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-007 |
| `medium` | 7 | ISSUE-006, ISSUE-008, ISSUE-009, ISSUE-010, ISSUE-011, ISSUE-012, ISSUE-013 |
| `low` | 2 | ISSUE-014, ISSUE-015 |

## High-Risk Incident Scenarios

| Scenario | Detection today | Containment today | Recovery today | Readiness gap |
| --- | --- | --- | --- | --- |
| Kill after single-step publish, before final manifest append | Resume yields stale-hash/unreadable; no terminal report | Atomic file is intact; run lock dies with process | Manual inference; backup may exist without record | ISSUE-001, ISSUE-006 |
| Kill/failure midway through restore | Exit 1 and log detail | Ordering leaves a lossless superset | Rerun stops at collision; manual cleanup | ISSUE-001, ISSUE-008 |
| Wrong/crafted/mixed-root manifest | Structural schema may pass | Lock uses first root only | Restore can touch other paths; verify can check wrong tree | ISSUE-002 |
| External editor/sync changes file after hash check | Usually no signal before commit | docmend lock does not exclude external writers | Recover from backup if identifiable | ISSUE-003 |
| Tool backup deleted after apply | Verify can remain clean | None | Restore fails only when attempted | ISSUE-004 |
| Restore appears complete but wrong path/bytes remain | Scan may be clean format-wise | None | Manual inventory/spot comparison | ISSUE-005 |
| Verify cannot read or times out on every file | Prints zero checked / zero findings | None | Operator must notice the zero count | ISSUE-007 |
| Bad release mutates user corpus | User report/issue; no defined advisory flow | Manual release removal/install downgrade | Corpus restore is separate and undocumented | ISSUE-012, ISSUE-014 |
| Sensitive artifact/log disclosure | No repo-defined detection or intake | Stop sharing/manual deletion | External legal/notification duties unknown | ISSUE-013, ISSUE-014 |

## Rollback And Disablement Readiness

- verified_strengths:
  - `Apply and restore are dry-run by default; writes require an explicit flag.`
  - `Content rewrites require tool backup, declared Git/external preservation, or a restricted single-action opt-out.`
  - `Include/exclude filters provide a practical staged-rollout control.`
  - `Run locks refuse concurrent docmend plan/apply/restore operations on one root.`
  - `Tool backups are written, fsynced, reread, and hash-verified before mutation.`
  - `Restore rechecks live after-hashes and backup before-hashes per record.`
- gaps:
  - `The rollback ledger is not write-ahead for all operations (ISSUE-001).`
  - `Restore does not enforce one trusted root (ISSUE-002).`
  - `External recovery is declared but not identified (ISSUE-009).`
  - `Package downgrade is not corpus rollback (ISSUE-012).`
- not_needed_for_this_repo:
  - `Remote feature flags, service maintenance mode, traffic draining, and fleet kill switches; there is no resident or network service.`

## Incident Command, Handoffs, And Decision Logging

- current_posture:
  - `One owner is simultaneously operator and decision maker; a multi-role incident command hierarchy is not needed.`
  - `Run IDs correlate logs and artifacts; manifests are the mutation ledger; ADRs and handoff records preserve decisions.`
  - `Issue #15 and v1.0.1 demonstrate that post-release feedback can become a durable changelog/spec decision.`
- gaps:
  - `No minimal severity model, incident owner declaration, stop-rollout trigger, or public security intake (ISSUE-014).`
  - `Interrupted/aborted runs do not have a complete durable terminal state (ISSUE-006).`
  - `Runbooks do not specify evidence preservation or decision logging under pressure (ISSUE-013).`

## Runbooks, Escalation, And Ownership

- existing_runbooks: `restore from manifest; resume after interruption`
- adequate_content: `triggers, primary commands, dry-run posture, multi-attempt order, common failure notes`
- missing_content: `owner, review date, version/schema scope, prerequisites, stop/contain, evidence, escalation, communication, post-incident follow-up, full recovery proof`
- missing_scenarios: `wrong-root/containment breach; corrupt/mismatched manifest; failed/interrupted restore; missing/corrupt backup; sensitive artifact disclosure; bad release/schema change; compromised dependency/release workflow`
- related_findings: `ISSUE-005, ISSUE-008, ISSUE-012, ISSUE-013`

## Status Communication And Support Readiness

- status_page: `not needed for this repo; local batch CLI has no service availability status`
- current_channels: `GitHub Releases, CHANGELOG, and likely GitHub issues (inferred, not declared as incident policy)`
- gaps: `no SECURITY.md/private intake, issue template, advisory threshold, affected-version communication process, or support bundle redaction instructions`
- related_findings: `ISSUE-013, ISSUE-014`

## Failure Containment And Recovery Gaps

1. `Close ISSUE-002 before any broad restore use: destructive recovery must be root-bound.`
2. `Close ISSUE-001 before relying on zero-RPO journal claims: every mutation needs durable pre-state evidence.`
3. `Close ISSUE-003 or explicitly require and enforce corpus quiescence during apply/restore.`
4. `Make backup health and restored-before-state first-class verification targets (ISSUE-004, ISSUE-005).`
5. `Eliminate false-clean verification and selective-restore results (ISSUE-007, ISSUE-010).`

## Deploy And Change-Safety Risks

- current_strengths: `documented dev-to-protected-main workflow; signed-tag process; locked dependency file; release builds sdist+wheel; wheel version smoke test; changelog`
- risks:
  - `Future manifest minors can reach destructive consumers without compatibility refusal (ISSUE-011).`
  - `Release tags are not proven to be signed main commits with matching version/lock/gate evidence by the workflow itself (ISSUE-012).`
  - `Privileged release checkout is not full-SHA pinned (ISSUE-012).`
  - `No bad-release withdrawal/advisory plus corpus-recovery runbook exists (ISSUE-012).`
- external_unknowns: `GitHub tag protection, immutable releases, release-environment approvals, and actual branch-protection settings were not queried.`

## Incident Testing And Drill Gaps

- verified_test_strengths:
  - `110 focused recovery, verify, lock, and gate tests passed.`
  - `Happy-path full-corpus restore compares every byte.`
  - `Resume tests cover dangling rename-and-rewrite intent, tampering, repeated interruption, and wrong-tree prior manifests.`
  - `Restore tests cover corrupt/missing backups, overwrite recovery, modified-since-apply, and partial mutation residue.`
- gaps:
  - `No intent/reconciliation protocol for ordinary rewrite/rename or restore boundaries (ISSUE-001).`
  - `No restore/verify root-binding scenarios (ISSUE-002).`
  - `No external-writer identity-swap scenarios (ISSUE-003).`
  - `No verify-backup-health or automated restored-before-state command (ISSUE-004, ISSUE-005).`
  - `No all-skipped verify or unmatched restore-ID tests (ISSUE-007, ISSUE-010).`
  - `No dated real-environment/tabletop drill evidence (ISSUE-015).`

## Convention Recommendations

### Cross-project defaults

1. `Every destructive run has one durable lifecycle: preflight -> intent -> mutation -> terminal record -> verification; no mutation precedes its recoverable intent.`
2. `Runbooks carry owner, reviewed date, version/schema scope, detection, stop/contain, evidence preservation, recovery, verification, communication, and follow-up.`
3. `Recovery artifacts are treated as untrusted inputs: version-gated, root-bound, path-contained, and validated before access.`
4. `A clean verification result reports requested, checked, excluded, skipped/error, and recovered counts; zero checked is never implicitly clean.`
5. `Release rollback distinguishes executable rollback from state/data rollback and includes advisory/withdrawal steps.`

### Repo-specific exceptions

1. `No pager, on-call rotation, status page, service maintenance mode, remote feature-flag system, or network dependency fallback is needed while docmend remains a manually invoked offline single-owner CLI.`
2. `External preservation may remain backend-agnostic, but each run should retain an opaque recovery-point reference and a verified-root declaration.`
3. `Incident evidence stored in public repo docs must remain synthetic and path/content-free per convention #6.`
4. `Schema/recovery changes remain change-controlled through SPEC-VHHB and ADRs; conventions should point to, not duplicate, those contracts.`

## Pass Log

| Pass | Lens | New issues | Notes |
| --- | --- | --- | --- |
| 1 | Surface inventory, critical journeys, rollback/disablement, command/runbook coverage | ISSUE-001, ISSUE-002, ISSUE-005, ISSUE-009 | Established destructive CLI incident shape; service-only surfaces marked not needed. |
| 2 | Failure containment, preservation modes, dependency fallback, code-to-convention alignment | ISSUE-003, ISSUE-004, ISSUE-007, ISSUE-010, ISSUE-011 | Direct code review of apply/restore/verify/gate/artifact compatibility. |
| 3 | Ownership, severity, deploy/rollback safety, triage, communication, recovery workflow | ISSUE-006, ISSUE-008, ISSUE-012, ISSUE-013, ISSUE-014 | Release workflow and public-support negative search completed. |
| 4 | Lower-severity gaps, drills, decision logging, stale docs, post-incident hooks | ISSUE-015 | Required minimum pass reached; automated test behavior compared with runbook claims. |
| 5 | Adaptive verification of high-risk recovery paths | none | Focused suite: 110 passed; current behavior confirmed rather than dismissed as failing tests. |
| 6 | Baseline comparison, negative search, issue de-duplication | none | v1.0.2 runtime equals HEAD; second consecutive no-new-issue pass, convergence allowed. |

## Claude Handoff

- highest_priority:
  1. `ISSUE-002: root-bind restore and verify before broad rollout.`
  2. `ISSUE-001: make all apply/restore mutations write-ahead and interruption-convergent.`
  3. `ISSUE-004 + ISSUE-005: prove recovery bytes before incident and exact restored state afterward.`
  4. `ISSUE-007: remove zero-files-checked false-clean verification.`
- implementation_order_note: `These are post-approval behavior changes. Update the approved spec/ADR and traceability before implementation; do not silently patch runtime semantics.`
- validation_focus: `real process kill boundaries, mixed/wrong manifests, file-identity swaps, missing backups, full before-state reconciliation, terminal report states`
- do_not_overbuild: `Do not add service-oriented paging, status, feature-flag, or maintenance infrastructure to this local CLI.`
- related_review_artifacts: `The same sweep's documentation, product/business-logic, architecture, conventions, CI/CD, observability, schema, test, and release reviews should be reconciled before fixes to avoid duplicate or conflicting changes.`

## Open Questions Or Assumptions

1. `May editors, sync clients, indexers, or any non-docmend process modify the corpus during apply/restore, or is quiescence a supported-runtime precondition?`
2. `Must pre-1.2 manifests remain directly restorable, or may they require an explicit trusted root/migration?`
3. `What exact Git commit/snapshot/reference proves an external preservation declaration for the first real-library run?`
4. `What cadence and retention are required for tool-backup health verification?`
5. `Should unmatched restore IDs be exit 1 findings or exit 2 input errors?`
6. `Which filesystems/mount options are supported for claimed fsync/atomicity behavior?`
7. `What GitHub tag protection, immutable-release, and security-advisory settings are active outside the repo?`
8. `What privacy/regulatory or breach-notification duties apply to the owner's real corpus and artifacts? Repository evidence cannot determine this.`

## Residual Risk

- overall_posture: `not ready for broad unattended destructive rollout without owner-accepted recovery risk; appropriate for continued synthetic testing and read-only scan/plan`
- strongest_controls: `dry-run default, explicit write gate, tool-backup verification, atomic publication, run locking, per-run correlation, conservative skip behavior, broad automated tests`
- highest_residual_risks: `unjournaled committed mutations, uncontained restore manifests, stale file identity at commit, false-clean verification, and unproven recovery-point integrity`
- externally_unverified_risk: `real filesystem semantics, external backup recoverability, GitHub release controls, installed-user impact, and incident communication obligations`
- rollout_recommendation: `Before the owner's first filtered write, complete or explicitly accept ISSUE-001/002/004/005/007, perform a safe-copy incident drill, and retain privacy-safe drill evidence. Continue scan/plan rollout while write-path fixes are evaluated.`
