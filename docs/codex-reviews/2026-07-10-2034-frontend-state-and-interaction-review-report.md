# Frontend State And Interaction Review

## Findings

### ISSUE-001

- first_pass: `3`
- severity: `high`
- confidence: `high`
- frontend_state_area: `race-conditions-and-concurrency`
- issue_type: `race-condition-concurrency-gap`
- verification_status: `direct repo evidence plus isolated runtime reproduction`
- evidence:
  - `src/docmend/writer/apply.py:172-234` makes a durable `intent` record the source of truth when a hard kill lands inside `rename_and_rewrite`.
  - `src/docmend/writer/apply.py:606-645` explicitly distinguishes closed and dangling intents during resume.
  - `src/docmend/verify.py:88-114` ignores every non-`applied` record without checking whether a later terminal record closes an intent.
  - `src/docmend/restore.py:121-125` likewise filters replay to `applied` records without surfacing dangling intents.
  - `tests/test_verify.py:108-119` proves a closed intent is ignored, but there is no verify/restore test for an intent with no later terminal record.
- failure: A manifest containing only a dangling intent can represent a target already published while the original source still exists, or a fully completed mutation whose terminal record was never appended. Both `verify` and `restore` return exit `0`; restore reports zero work, and verify can report zero findings.
- reproduced: An isolated schema-valid intent with both source and target present produced `verify: 2 files checked, 0 findings` and `restored: 0 ... skipped: 0 failed: 0`; both commands exited `0`.
- user_impact: The only durable evidence of an interrupted multi-step mutation is rendered invisible on the two commands users reasonably invoke to assess or undo state. Automation can accept a partially transitioned corpus as clean.
- recommendation: Centralize manifest lifecycle reduction into one function that classifies each action as `unstarted`, `dangling-intent`, `applied`, or `failed`. Resume, verify, restore, and report reconciliation should consume that reducer. `verify` and `restore` should emit a finding and nonzero exit for each dangling intent, with an explicit instruction to resume against the original plan before restoring.
- test_direction: Add CLI tests for kill-after-publish and kill-before-final-record manifests passed to both `verify` and `restore`; require nonzero status, the affected action ID/path, and a resume-oriented message. Preserve the existing clean result for an intent closed by a later applied/failed record.
- convention_impact: Add a repo-specific convention that every persisted nonterminal state must be visible to every status, verify, and recovery interaction.

### ISSUE-002

- first_pass: `2`
- severity: `high`
- confidence: `high`
- frontend_state_area: `loading-empty-error-and-retry-states`
- issue_type: `loading-empty-error-state-gap`
- verification_status: `direct repo evidence plus isolated runtime reproduction`
- evidence:
  - `src/docmend/discovery.py:313-330` records timeout and unreadable candidates as inventory skips rather than file records.
  - `src/docmend/verify.py:36-81` checks only `inventory.files`.
  - `src/docmend/cli.py:843-865` builds findings solely from content/frontmatter/artifact reconciliation and prints only the checked-file count; it never promotes `inventory.skipped` into findings.
  - `src/docmend/cli.py:193-203` and `src/docmend/cli.py:326-341` already treat unreadable scan/plan inputs as exit-`1` findings, so verify diverges from the established state model.
  - `tests/test_cli_verify.py` covers an unreadable manifest but not unreadable or timed-out corpus entries.
- failure: Verification can skip an unreadable or timed-out output, omit it from both the checked count and finding count, and exit `0`.
- reproduced: With one readable Markdown file and one permission-denied Markdown file, verify logged `ERR-007`, printed `verify: 1 files checked, 0 findings`, and exited `0`.
- user_impact: The command's clean state means “all records that happened to be readable passed,” not “the requested scope was verified.” This is unsafe for unattended rollout gates and contradicts the CLI's `0 clean / 1 findings` interaction contract.
- recommendation: Convert every non-excluded discovery skip during verify (`unreadable`, `timeout`, and future incomplete classifications) into a `VerifyFinding`. Include checked, skipped, and total candidate counts in the summary. Decide explicitly whether an explicit single-file path filtered out by configuration is an input error or a finding; do not report it as clean without saying it was unverified.
- test_direction: Add permission-denied and injected-watchdog CLI tests asserting exit `1`, path/reason output, and a summary whose counts reconcile with requested candidates.
- convention_impact: Add a cross-project convention that “clean” requires complete coverage of the requested scope; skipped or indeterminate work must remain visible and non-successful unless the user explicitly excluded it.

### ISSUE-003

- first_pass: `3`
- severity: `high`
- confidence: `high`
- frontend_state_area: `pending-transitions-and-intent-preservation`
- issue_type: `pending-transition-intent-gap`
- verification_status: `direct repo evidence plus isolated runtime reproduction`
- evidence:
  - `src/docmend/cli.py:530-582` executes all mutations and releases the run lock before terminal report persistence.
  - `src/docmend/cli.py:584-603` writes the report before echoing either report or manifest locations and does not handle write failures.
  - `src/docmend/artifacts.py:93-102` can raise `OSError` while creating or replacing the report.
  - `src/docmend/writer/gate.py:184-232` preflights the default manifest directory and backup destination, but the caller does not pass the independently configurable `report_path` into the gate.
  - No CLI test injects a report-publication failure after a successful mutation.
- failure: A write apply can mutate the corpus and durably append its manifest, then fail to persist a custom report. The process exits through an unhandled exception after the lock is released and before it tells the user where the manifest is.
- reproduced: An apply using a non-writable custom `--report` path exited `1` with a Rich traceback and `PermissionError`; the renamed target and manifest existed, while the report did not.
- user_impact: The visible terminal state says “command failed” even though destructive work succeeded. A user or wrapper can retry under the wrong assumption, while the required authoritative report is absent and the recovery artifact path was never printed.
- recommendation: Treat terminal artifact publication as part of the apply state machine. Preflight the selected report destination before mutation, keep the run lock until report publication and terminal messaging finish, and catch late publication failures with a concise error that states whether mutations occurred and prints the manifest path. Consider a provisional/final report protocol if the contract must survive disk-full or post-mutation failures.
- test_direction: Inject create, fsync, and replace failures for the report after at least one mutation. Assert corpus/manifest state, stable nonzero exit semantics, no traceback, explicit “mutations occurred” messaging, and a discoverable recovery path.
- convention_impact: Add a repo-specific convention that a destructive command does not enter its terminal success/failure state until durable mutation evidence and user-visible recovery coordinates are published.

### ISSUE-004

- first_pass: `2`
- severity: `medium`
- confidence: `high`
- frontend_state_area: `form-input-and-validation-state`
- issue_type: `form-input-state-gap`
- verification_status: `direct repo evidence plus isolated runtime reproduction`
- evidence:
  - `src/docmend/cli.py:678-680` accepts repeatable `--id` selectors.
  - `src/docmend/restore.py:121-125` silently filters out records whose IDs do not match.
  - `src/docmend/cli.py:748-764` derives success only from returned outcomes, so a zero-match selection prints all zeros and exits `0`.
  - `tests/test_restore.py:749-772` covers a matching selector but no unknown, partially matching, or duplicate selector.
- failure: A typo or stale `docmend.id` produces a successful no-op rather than preserving the user's stated restore intent as an error/finding.
- reproduced: `restore --write --id <unknown-valid-UUID>` printed `restored: 0 ... failed: 0`, exited `0`, and left the applied target in place.
- user_impact: Scripts and operators can believe a targeted recovery succeeded when no requested document was found.
- recommendation: Validate selectors before replay. Report unknown IDs individually and exit nonzero; for mixed selections, restore known IDs while returning a finding for every unmatched ID. Include matched/requested counts in the summary.
- test_direction: Cover zero matches, partial matches, repeated IDs, and dry-run/write parity.
- convention_impact: Add a cross-project convention that explicit selectors are assertions of user intent; zero or partial matches cannot be silently successful.

### ISSUE-005

- first_pass: `4`
- severity: `low`
- confidence: `high`
- frontend_state_area: `loading-empty-error-and-retry-states`
- issue_type: `convention-misalignment`
- verification_status: `direct repo evidence plus isolated runtime reproduction`
- evidence:
  - `src/docmend/cli.py:88-95` promises that `--quiet` limits console output to errors and critical messages.
  - `src/docmend/observability.py:48-60` correctly applies that policy to the structured console log sink.
  - Direct `typer.echo` summaries at `src/docmend/cli.py:195-200`, `316-324`, `586-597`, `733-738`, `759-762`, and `861-863` bypass the quiet state.
  - `tests/test_cli_apply.py:312-328` asserts only that per-file log lines disappear; it does not assert stdout/stderr emptiness or the documented errors-only contract. Typer supports separate stdout/stderr assertions in its official testing guidance: <https://typer.tiangolo.com/tutorial/testing/>.
- failure: Successful `-q` commands still emit artifact paths and summaries.
- reproduced: `docmend -q verify <clean-file>` printed `verify: 1 files checked, 0 findings` and exited `0`.
- user_impact: The flag cannot provide the stable silent-success behavior expected by wrappers, cron-like execution, or shell composition.
- recommendation: Decide one contract and make it explicit. Either gate all non-error direct output on `opts.quiet`, or rename/document the flag as “suppress informational logs but keep command summaries.” The current help, conventions, implementation, and tests should agree.
- test_direction: For every command, assert stdout and stderr separately under default, `-v`, `-vv`, and `-q`, including success, findings, input error, and safety refusal. Click's official exception model supports stable user-facing errors and exit codes without raw tracebacks: <https://click.palletsprojects.com/en/stable/exceptions/>.
- convention_impact: Clarify the existing CLI output convention; this is primarily a convention-alignment defect, not a new product capability.

## Severity Summary

| severity | count | issue_ids                             |
| -------- | ----: | ------------------------------------- |
| critical |     0 | —                                     |
| high     |     3 | `ISSUE-001`, `ISSUE-002`, `ISSUE-003` |
| medium   |     1 | `ISSUE-004`                           |
| low      |     1 | `ISSUE-005`                           |

## Review Metadata

- repo_path: `.`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- worktree_state: `dirty before review: modified AGENTS.md plus orchestrator-owned/untracked docs/codex-reviews artifacts; review added only this requested report`
- review_mode: `read-only implementation review; exact requested report path is the only repository write`
- review_date: `2026-07-10`
- detected_frontend_frameworks_and_runtimes: `no browser/web frontend; Python 3.14.6; Typer 0.26.8; Click 8.4.2; Rich 15.0.0`
- state_containers_and_data_fetching_libraries_reviewed: `none; state is Python models plus JSON/NDJSON filesystem artifacts`
- navigation_routing_and_url_state_surfaces_reviewed: `Typer command dispatch; CWD-relative .docmend sidecar lookup; --run-id and explicit artifact paths`
- form_and_input_state_surfaces_reviewed: `CLI flags/options, repeatable --id and resume selectors, config precedence, write/dry-run conflicts`
- pending_transition_and_interruption_surfaces_reviewed: `scan/plan atomic publication; apply write-ahead intent; resume; restore; verify; report finalization; run locks`
- optimistic_update_and_realtime_surfaces_reviewed: `not needed for this repo`
- cache_invalidation_and_synchronization_surfaces_reviewed: `no client cache; plan/inventory/report/manifest reconciliation is the equivalent durable synchronization surface`
- persisted_offline_or_multi_tab_surfaces_reviewed: `offline JSON/NDJSON artifacts and filesystem state; multi-tab browser state not needed; concurrent CLI processes covered by flock`
- browser_and_interaction_test_artifacts_reviewed: `Typer CliRunner suites and engine tests; no browser tests because no browser surface exists`
- important_external_browser_or_runtime_surfaces_not_in_repo: `real terminal/TTY behavior, shell wrappers, permission/disk-full behavior, and owner real-library rollout`
- important_interaction_unknowns: `whether quiet should suppress summaries; expected recovery command when restore sees dangling intents; whether zero verified candidates is a finding or input error`
- conventions_input: `docs/handoff/conventions.md`
- conventions_maturity: `strong repository/tooling conventions; no dedicated durable CLI state/interaction convention`
- prior_baseline_compared: `v1.0.2 tag 9b0641b; no src/tests/pyproject/README changes between v1.0.2 and reviewed HEAD`
- shared_research_reused: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
- targeted_follow_up_research: `official Typer CLI testing and Click exception/exit-code documentation only; no broad web research`
- validation_run: `uv run pytest -q -> 619 passed, 1 scale test skipped`

## Frontend State Area Matrix

| frontend_state_area | applicability | posture | evidence_or_reason |
| --- | --- | --- | --- |
| state-ownership-and-source-of-truth | needed | partial | Plan, manifest, report, and live filesystem roles are documented; nonterminal manifest state is not shared consistently across commands (`ISSUE-001`). |
| derived-versus-duplicated-state | needed | mostly protected | Report totals and manifest/report accounting are derived and tested; CLI summaries still derive incomplete “clean” state (`ISSUE-002`). |
| async-request-lifecycle-and-cancellation | needed as CLI interruption lifecycle | gap | No network requests; interruption/resume is core. Dangling intent visibility and late report publication are unsafe (`ISSUE-001`, `ISSUE-003`). |
| pending-transitions-and-intent-preservation | needed | gap | Write-ahead intent preserves data, but verify/restore and terminal report publication do not preserve user-visible transition state. |
| optimistic-updates-and-rollback | not needed for this repo | not applicable | No optimistic UI; apply is explicit and restore is the rollback path. |
| cache-invalidation-and-freshness | not needed for this repo | not applicable | No browser/client cache. Stale-plan hash guards are reviewed as durable synchronization and are well covered. |
| form-input-and-validation-state | needed as CLI option state | gap | Flag conflicts are guarded, but explicit restore selectors can silently match nothing (`ISSUE-004`). |
| navigation-url-and-session-state | needed as CLI run/session state | mostly protected | Run IDs and sidecar paths are clear; no router or URL state exists. |
| offline-persistence-and-multi-tab-state | needed for offline persistence; browser multi-tab not needed | partial | Artifact schemas, atomic JSON, fsynced NDJSON, and flock are strong; terminal-state publication remains incomplete (`ISSUE-003`). |
| race-conditions-and-concurrency | needed | gap | Run lock and intent reconciliation are substantial protections; status/recovery consumers miss dangling state (`ISSUE-001`). |
| server-client-hydration-boundaries | not needed for this repo | not applicable | No server rendering or browser hydration boundary. |
| loading-empty-error-and-retry-states | needed as CLI progress/error/exit semantics | gap | Unverified skips can be clean, quiet state diverges, and late artifact errors expose tracebacks (`ISSUE-002`, `ISSUE-003`, `ISSUE-005`). |
| realtime-subscriptions-and-live-sync | not needed for this repo | not applicable | No subscriptions, sockets, polling, or live server synchronization. |
| interaction-testing-and-debuggability | needed | partial | Broad CLI/engine tests and structured logs exist; concrete missing failure-path tests are listed in all findings. |

## High-Risk User State Failure Paths

1. `apply rename_and_rewrite` → process killed after intent append → target may be published and source may remain → `verify`/`restore` ignore intent → exit `0` → partial state accepted as clean.
2. `verify PATH` → discovery cannot read or times out on a candidate → candidate enters `inventory.skipped` → verify checks only `inventory.files` → exit `0` → rollout gate accepts incomplete coverage.
3. `apply --write --report <bad-destination>` → mutation and manifest succeed → report publication fails → raw traceback/nonzero exit before artifact coordinates print → user retries without an accurate terminal-state model.
4. `restore --id <typo>` → selector matches zero applied records → zero outcomes → exit `0` → requested document remains applied.

## State Ownership And Synchronization Risks

- authoritative_live_state: `filesystem under plan.source_root`
- authoritative_pre_action_decision_state: `plan artifact plus source hashes`
- authoritative_mutation_progress_state: `manifest records reduced by action_id and record order`
- authoritative_terminal_outcome_state: `report artifact, currently vulnerable to post-mutation publication failure`
- synchronization_gap: `manifest lifecycle reduction exists privately inside execute_plan instead of as a shared reducer for resume/verify/restore`
- synchronization_gap: `verify's rendered clean state excludes inventory skips`
- synchronization_gap: `explicit restore selector state is discarded during filtering rather than reconciled against requested IDs`

## Async Lifecycle, Cache, And Rollback Risks

- async_network_requests: `not needed for this repo`
- cancellation_equivalent: `process interruption during batch apply`
- rollback_surface: `restore from applied manifest records and backups`
- primary_risks: `ISSUE-001`, `ISSUE-003`
- cache_state: `not needed; no client cache`
- verified_strengths: `source-hash stale guards, fsynced append-only manifest, torn-tail rule, resume reconciliation, dry-run defaults, and restore hash checks`

## Navigation, Form, And Session State Risks

- navigation: `not needed as browser routing; Typer command routing is explicit`
- session_identity: `run-ID is consistently carried through logs and artifacts`
- input_validation_strengths: `mutually exclusive write/dry-run, verbose/quiet, PATH/inventory, and manifest/run-ID forms are tested`
- input_validation_gap: `ISSUE-004`
- interaction_output_gap: `ISSUE-005`

## Persistence, Multi-Tab, And Browser Lifecycle Risks

- browser_persistence: `not needed for this repo`
- multi_tab_state: `not needed for this repo`
- multi_process_equivalent: `flock keyed by resolved source root; reviewed and covered by tests`
- persistence_risks: `terminal report publication is outside the locked mutation transition; dangling intent is persisted but hidden from recovery/status consumers`
- external_unknowns: `power-loss/disk-full behavior on the owner's filesystem and behavior through shell wrappers were not available in repo evidence`

## Hydration, Realtime, And Concurrency Risks

- hydration: `not needed for this repo`
- realtime: `not needed for this repo`
- concurrency_model: `single local process per run; cross-process exclusion via flock; sequential v1 engine`
- concurrency_risk: `ISSUE-001`
- race_review_note: `No new race issue was added for resume-manifest reads before lock acquisition because write runs refuse an active competing lock and source hashes retain a safe fallback; residual operational ambiguity remains low.`

## Interaction Testing And Debuggability Gaps

- missing_test: `dangling intent passed to verify and restore`
- missing_test: `verify corpus unreadable and watchdog-timeout skips`
- missing_test: `post-mutation report create/fsync/replace failure`
- missing_test: `restore zero-match and partial-match --id selectors`
- missing_test: `full stdout/stderr matrix for -q/-v/-vv across every command and terminal state`
- existing_strengths: `619 passing tests; extensive CliRunner coverage; resume kill-window tests; restore drill; idempotency; run locks; structured per-run JSONL logs`
- test_tool_guidance: `Typer documents asserting exit code and stdout/stderr separately; Click documents handled ClickException/UsageError paths and stable exit semantics`

## Convention Recommendations

### Shared Across Projects

1. `clean-means-complete`: A success status requires every requested item to be either verified or explicitly excluded; skipped/indeterminate items are findings.
2. `selectors-preserve-intent`: Explicit selectors are assertions. Zero and partial matches must be surfaced, not silently filtered away.
3. `nonterminal-state-is-visible`: Persisted pending/interrupted states must appear in status, verification, and recovery interactions until a terminal record closes them.
4. `terminal-artifact-before-success`: A destructive command must publish durable outcome/recovery coordinates before presenting a terminal state.
5. `verbosity-is-end-to-end`: Quiet/verbose semantics govern direct command output and logging consistently, with stdout/stderr behavior tested separately.

### Repo-Specific Exceptions Or Additions

1. Reduce manifest history through one shared action-state reducer; do not let resume, verify, restore, and accounting each invent a different subset rule.
2. Treat `intent` as nonterminal until a later `applied` or `failed` record with the same action ID closes it.
3. Hold the source-root run lock through report publication and final recovery-coordinate output, or document and test an equivalent durable finalization protocol.
4. Keep browser-specific cache, routing, hydration, realtime, optimistic-update, and multi-tab conventions out of this repo until an actual browser boundary is introduced.

### Convention Quality Assessment

- current_alignment: `Strong for tooling, artifact schemas, safety defaults, sensitive data, and spec traceability.`
- missing_hotspot: `CLI state-machine and interaction-output conventions are not durable in docs/handoff/conventions.md.`
- proposed_owner: `docs/handoff/conventions.md after owner/Claude accepts the behavior decisions; do not change the approved spec silently.`

## Pass Log

| pass | lens | new_issues | result |
| --: | --- | --- | --- |
| 1 | Repo/stack inventory, source-of-truth map, CLI commands, artifact flow, routing/form/pending surfaces | none | Confirmed no web frontend; scoped review to CLI and durable interaction state. |
| 2 | Derived state, input validation, loading/error semantics, code-to-convention alignment | `ISSUE-002`, `ISSUE-004` | Found false-clean verify skips and silent zero-match restore selectors. |
| 3 | Interruption, races, cancellation equivalent, persistence, lock boundaries, rollback | `ISSUE-001`, `ISSUE-003` | Found invisible dangling intents and post-mutation terminal report failure. |
| 4 | Lower-severity maintainability, output semantics, test gaps, convention quality | `ISSUE-005` | Found quiet-mode contract drift and completed test-gap inventory. |
| 5 | Adaptive deepening: adversarial artifact lifecycle and baseline comparison | none | No new issue; v1.0.2 implementation baseline matches reviewed source. |
| 6 | Convergence: isolated runtime reproductions, anti-pattern re-scan, severity/confidence calibration | none | Second consecutive no-new-issue pass; review converged. |

## Claude Handoff

- fix_first: `ISSUE-001 and ISSUE-002; both let verification/recovery return false success over incomplete state.`
- fix_second: `ISSUE-003; bind mutation completion, report durability, lock lifetime, and user-visible recovery coordinates into one terminal transition.`
- then: `ISSUE-004 and ISSUE-005 with their CLI interaction matrices.`
- change_control: `The approved spec explicitly says verify/restore reconcile applied records; changing dangling-intent behavior should be recorded through the approved spec/ADR process rather than patched silently.`
- suggested_implementation_shape: `manifest action-state reducer -> verify/restore integration -> CLI exit/output tests -> report-finalization protocol -> selector/verbosity cleanup`
- follow_on_reviews: `Coordinate ISSUE-003 with comprehensive code, incident-readiness, observability, and API/artifact-contract reviews; coordinate ISSUE-001 with background-jobs/async-workflow and data-schema reviews.`
- browser_follow_on: `none unless a real UI is added`
- acceptance_signal: `All four reproduced false/misleading terminal paths produce deterministic nonzero statuses, concise recovery guidance, and tests; quiet semantics match help.`

## Open Questions Or Assumptions

1. Should a dangling intent make `restore` refuse and direct the operator to resume, or should restore itself reconcile/undo the interrupted state? The current runbook favors resume, but the CLI does not surface that requirement.
2. Should `verify` treat an explicit PATH that yields zero candidate files as exit `1` finding or exit `2` input error?
3. Is `--quiet` intended to mean errors-only, as help states, or “hide structured informational logs but retain summaries”?
4. Must the report be durable after every mutating run even when the selected report destination fails after the preflight? The approved DR-003/FR-018 contract says yes; the exact provisional/final publication protocol is not specified.
5. Real terminal signal handling, disk-full timing, and owner shell-wrapper behavior were not verified beyond isolated local reproductions.

## Residual Risk

- overall: `high until ISSUE-001 through ISSUE-003 are resolved or explicitly accepted`
- directly_verified: `source code, tests, approved spec, conventions, shared research, v1.0.2 baseline, full non-scale test suite, and four isolated CLI reproductions`
- inferred: `automation and rollout-gate impact based on documented exit-code semantics and the project's unattended-operation goals`
- not_verified: `owner real-library corpus, long-running scale test, filesystem power-loss behavior, external backup systems, shell wrappers, and any browser surface outside this repo`
- excluded_as_not_needed: `optimistic UI, client cache invalidation, URL/router state, SSR/hydration, realtime subscriptions, service workers, browser storage, and multi-tab synchronization`
- research_basis: `Shared pack filesystem/recovery guidance plus official Typer testing and Click exception/exit-code documentation; no additional broad research was needed.`
