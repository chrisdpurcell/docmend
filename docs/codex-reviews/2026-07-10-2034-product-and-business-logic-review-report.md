# Product And Business Logic Review

## Review Metadata

- review_type: `product-and-business-logic-review`
- repo_root: `.`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- worktree_state: `dirty before review`; pre-existing `AGENTS.md` modification and orchestrator-owned `docs/codex-reviews/` artifacts were preserved
- report_path: `docs/codex-reviews/2026-07-10-2034-product-and-business-logic-review-report.md`
- review_mode: `read-only product review; report write only`
- detected_runtime: `Python >=3.14`
- detected_frameworks: `Typer`, `Rich`, `Pydantic v2`, `jsonschema Draft 2020-12`, `structlog`, `charset-normalizer`, `pathspec`, `ruamel.yaml`
- core_domain_entities_reviewed: `Inventory`, `FileRecord`, `Plan`, `PlanAction`, `SkipDecision`, `Report`, `ApplyOutcome`, `ManifestRecord`, `DocmendConfig`, backup files, source/target documents
- core_workflows_reviewed: `scan -> plan -> apply`, dry-run, preservation gate, collision handling, resume, restore, verify, frontmatter validation
- product_policy_sources_reviewed: `docs/specs/docmend.md` (approved SPEC-VHHB), ADRs 0001-0018, `README.md`, restore/resume runbooks, resolved decisions, repository conventions
- conventions_input: `docs/handoff/conventions.md`
- decision_tables_and_scenarios_reviewed: safety-gate predicates, collision policies, encoding gates, weird-document fixtures, requirement-to-test traceability, resume intent states, restore outcomes
- surfaces_reviewed: `CLI`, Python domain modules, JSON/NDJSON artifacts, filesystem mutations, tests, docs; UI/API/background-job surfaces are absent
- config_driven_behavior_reviewed: include/exclude filters, encoding thresholds, transform toggles, collision policy, preservation options, limits, advertised parallel/write settings
- pricing_quota_entitlement_surfaces: `not needed for this repo`
- historical_migration_surfaces: artifact schema versions 1.x, resume manifests, restore manifests, report/manifest reconciliation, pre-1.2 source-root fallback
- business_event_artifacts_reviewed: inventory, plan, apply report, manifest, JSONL logs, verify console findings, restore inverse manifest
- prior_baseline_compared: `v1.0.2`; no source/test changes exist between tag `v1.0.2` and reviewed HEAD; no prior product-logic report was present
- shared_research_used: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
- targeted_follow_up_web_research: `none`; the shared pack covered filesystem identity, containment, recovery, artifact, and batch-audit guidance
- validation_run: `619 passed, 1 skipped` via `uv run pytest -q`; skipped test is the opt-in 100k-file scale test
- isolated_synthetic_reproductions: `confirmed` for ISSUE-002, ISSUE-003, ISSUE-004, and ISSUE-005
- important_external_unknowns: supported concurrent-editor/process threat model, supported filesystem matrix, real-library anomaly distribution, external preservation reliability/retention

## Product Logic Area Matrix

| product_logic_area | relevance | posture | evidence_or_reason |
| --- | --- | --- | --- |
| `core-domain-invariants` | high | insufficient | stale-input and source-root invariants can be bypassed (ISSUE-001, ISSUE-002) |
| `workflow-state-transitions` | high | insufficient | collision aborts can leave plan actions without report outcomes (ISSUE-004) |
| `entitlements-pricing-quotas-and-limits` | none | not needed for this repo | local offline CLI; no commercial entitlement model |
| `defaults-fallbacks-and-implicit-behavior` | medium | insufficient | accepted config values can be operationally inert (ISSUE-007) |
| `edge-cases-and-exception-paths` | high | insufficient | verification timeouts/skips and unmatched restore IDs can falsely succeed (ISSUE-005, ISSUE-008) |
| `temporal-and-calendar-semantics` | medium | insufficient | check-to-mutation races affect plan/apply and restore; calendar rules are otherwise not needed (ISSUE-001) |
| `approval-escalation-and-human-override-paths` | medium | adequate with gap | write/preservation overrides are explicit; targeted restore selection lacks unmatched-ID feedback (ISSUE-008) |
| `feature-flags-and-config-driven-rules` | medium | insufficient | parallel and write controls are accepted without implementing their advertised behavior (ISSUE-007) |
| `feature-flag-lifecycle-and-retirement` | low | insufficient | future/reserved settings are shipped as active-looking values instead of rejected lifecycle states (ISSUE-007) |
| `decision-table-and-scenario-coverage` | high | insufficient | existing suite omits the confirmed false-clean and containment scenarios |
| `cross-surface-consistency-ui-api-jobs` | medium | insufficient | UI/API/jobs are not needed; CLI/spec/artifact consistency has verification gaps (ISSUE-002 through ISSUE-006) |
| `historical-data-backfill-semantic-consistency` | medium | insufficient | legacy/mixed manifest handling lacks one enforced root identity (ISSUE-002) |
| `data-model-and-domain-meaning-alignment` | high | insufficient | `source_root` is recorded but not enforced by restore/verify (ISSUE-002) |
| `business-event-auditability` | high | insufficient | recovery evidence, full plan outcomes, and verify results are incomplete (ISSUE-003, ISSUE-004, ISSUE-006) |
| `docs-adrs-and-product-rationale` | high | insufficient | reversibility claims conflict with the documented no-tool-backup mode (ISSUE-009) |
| `business-logic-testing` | high | insufficient | 619 tests pass, but all high findings represent missing invariant/scenario tests |

## Severity Summary

| severity | count | issue_ids                                                       |
| -------- | ----: | --------------------------------------------------------------- |
| high     |     5 | `ISSUE-001`, `ISSUE-002`, `ISSUE-003`, `ISSUE-004`, `ISSUE-005` |
| medium   |     3 | `ISSUE-006`, `ISSUE-007`, `ISSUE-008`                           |
| low      |     1 | `ISSUE-009`                                                     |

## Findings

### ISSUE-001: Hash and containment preconditions are not held through mutation

- first_pass: `1`
- severity: `high`
- confidence: `medium`
- product_logic_area: `core-domain-invariants`
- issue_type: `domain-invariant-gap`
- verified_repo_evidence:
  - `src/docmend/writer/apply.py:363-380` reads and hashes a source pathname, then later mutates via a fresh pathname operation at `src/docmend/writer/apply.py:503-517`.
  - `src/docmend/restore.py:83-103` hashes the live target, then `src/docmend/restore.py:153-169` stats it and `src/docmend/restore.py:239-258` mutates it through later pathname operations.
  - Tests cover changes before apply/restore, collision races, and docmend run-lock contention, but not external replacement between validation and mutation.
  - Shared research lines 41-46 requires checking identity/digest at the actual mutation point and treating mutable pathnames as a TOCTOU boundary.
- inferred_business_impact: an editor, sync process, or other local process can replace or change a file after docmend's hash check; apply can overwrite newer bytes, and restore can clobber work that its public contract says is skipped when modified since apply.
- not_verified: whether the supported operating contract explicitly forbids all non-docmend writers during apply/restore.
- failure_path: `hash matches -> external path replacement -> mutation uses replacement path -> manifest/report records the earlier bytes as if they were mutated`.
- recommendation: bind validation, backup, transform, and mutation to one opened file identity; use descriptor-relative/no-follow operations or re-stat and re-hash the exact object immediately before commit, and fail safely on identity drift. Apply the same rule to restore.
- required_tests: deterministic source replacement between hash and publish for rewrite, rename, rename-and-rewrite, and restore; assert no newer bytes are lost and the outcome is a safety finding.

### ISSUE-002: Restore and verify do not enforce manifest-to-source-root binding

- first_pass: `1`
- severity: `high`
- confidence: `high`
- product_logic_area: `data-model-and-domain-meaning-alignment`
- issue_type: `historical-semantic-consistency-gap`
- verified_repo_evidence:
  - Manifest schema records `source_root` but permits arbitrary absolute `original_path` and `target_path` values (`src/docmend/schemas/manifest.schema.json:48-60,93-96`).
  - Restore selects a lock root from only the first record (`src/docmend/cli.py:379-394`) and `run_restore` performs no per-record containment check (`src/docmend/restore.py:106-143,146-258`).
  - Verify hashes every manifest target without checking it belongs to `verify PATH` or to a consistent manifest root (`src/docmend/verify.py:88-114`; `src/docmend/cli.py:843-860`).
  - Isolated reproduction: a schema-valid record declaring one root restored an outside path with status `restored`; `verify tree-b --manifest tree-a-manifest` exited `0`.
- inferred_business_impact: a wrong, concatenated, corrupted, or crafted manifest can mutate outside the declared library during restore; verify can produce a clean result while checking content from a different tree.
- not_verified: policy for pre-1.2 manifests that have no source root and whether destructive legacy restore is required without an explicit operator-supplied root.
- failure_path: `manifest validates structurally -> first record determines lock -> later/arbitrary absolute path accepted -> restore mutates it or verify treats another tree as evidence`.
- recommendation: treat manifests as untrusted domain input. Require one consistent resolved `source_root` for modern records; enforce every original/target path beneath it at read and mutation time; require verify's PATH to match that root; require an explicit trusted root or migration step for legacy manifests.
- required_tests: mixed-root manifest, outside-root original, outside-root target, wrong-tree verify, symlinked parent swap, and legacy-manifest explicit-root behavior.
- follow_on_review: `architecture-boundary-review`, `data-schema-migration-review`, and `comprehensive-code-review` should reuse this finding.

### ISSUE-003: Verify does not verify backup references or recoverable before-state

- first_pass: `2`
- severity: `high`
- confidence: `high`
- product_logic_area: `business-event-auditability`
- issue_type: `business-event-auditability-gap`
- verified_repo_evidence:
  - Accepted ADR-0012 requires manifest before/after hashes and backup references to reconcile (`docs/adr/adr-0012-verify-semantics-exit-code-taxonomy.md:68`).
  - `reconcile_manifest` checks only applied target `after_sha256` (`src/docmend/verify.py:88-114`); it never reads `backup_path`, `before_sha256`, `overwritten_backup_path`, or `overwritten_sha256`.
  - Isolated reproduction: after a successful tool-backup apply, deleting the recorded backup still left `verify --manifest` at exit `0`.
- inferred_business_impact: verify can certify a run whose original bytes are no longer recoverable, defeating the zero-loss/recovery posture exactly when a later restore is needed.
- not_verified: whether external backup systems are expected to be checked by docmend; this finding is limited to tool-written backup paths already recorded in the manifest.
- failure_path: `apply verifies backup once -> backup disappears/corrupts -> live converted output remains healthy -> verify exits clean -> restore later fails ERR-004`.
- recommendation: verify every non-null backup reference for existence, regular-file type, containment in the expected backup domain where knowable, and hash equality; do the same for overwritten-target backups. Report null backup references as declared external-recovery dependencies, not as verified recoverability.
- required_tests: missing/corrupt source backup, missing/corrupt overwritten-target backup, null-backup external-preservation status, and clean backup verification.

### ISSUE-004: Apply/report/verify accounting is plan-unaware and can hide unattempted actions

- first_pass: `2`
- severity: `high`
- confidence: `high`
- product_logic_area: `business-event-auditability`
- issue_type: `cross-surface-consistency-gap`
- verified_repo_evidence:
  - Collision policy `fail` breaks the apply loop after the colliding action, leaving later plan actions without outcomes (`src/docmend/writer/apply.py:634-677`; behavior is explicitly asserted at `tests/test_apply.py:271-285`).
  - The report schema has no run terminal status or `not_attempted` outcome (`src/docmend/schemas/report.schema.json:35-53,62-111`).
  - `reconcile_report` compares only applied action-ID sets and duplicate applied records (`src/docmend/verify.py:117-151`).
  - The CLI has no accepted ADR-0012 `--plan` input (`src/docmend/cli.py:767-860`), so it cannot prove every planned action has one terminal outcome.
  - Isolated reproduction: a three-action plan applied the first, collided on the second, omitted the third from the report, left the third source untouched, and later `verify --manifest --report` exited `0`.
- inferred_business_impact: at library scale, verify can certify an incomplete run and reports cannot distinguish "never attempted" from "not in the plan," weakening unattended promotion decisions.
- not_verified: whether product policy wants collision `fail` to mark all remaining actions skipped, aborted, or not-attempted; the current contract does not encode any of them.
- failure_path: `plan has N actions -> fail collision at k -> report contains only 1..k -> manifest applied set matches report applied set -> verify exits clean while k+1..N remain pending`.
- recommendation: add plan-aware verification and a terminal run state. Require each plan action to map exactly once to `applied`, `would_apply`, `skipped`, `failed`, or an explicit `not_attempted/aborted`; verify plan hash/run identity, report coverage, and manifest coverage together.
- required_tests: collision-fail with trailing actions, injected fatal abort after one mutation, missing skipped outcome, missing failed outcome, wrong plan/report pairing, and complete clean accounting.

### ISSUE-005: Verify ignores scan-time skips and can exit clean after checking zero files

- first_pass: `2`
- severity: `high`
- confidence: `high`
- product_logic_area: `edge-cases-and-exception-paths`
- issue_type: `edge-case-exception-gap`
- verified_repo_evidence:
  - Discovery records `unreadable` and `timeout` skips in the inventory (`src/docmend/discovery.py:313-331,435-446`).
  - Verify builds findings only from `inventory.files`, frontmatter, and optional artifacts (`src/docmend/cli.py:843-864`); it never converts `inventory.skipped` into findings.
  - Isolated reproduction forced the only candidate to exceed `limits.per_file_timeout`; verify printed `0 files checked, 0 findings` and exited `0`.
  - ADR-0012 says exit `1` covers skipped-with-errors and requires skipped/failed files to be accounted for.
- inferred_business_impact: unreadable or pathological files can disappear from the verification population while the command reports a clean library, including the degenerate all-files-skipped case.
- not_verified: whether excluded-by-policy paths should appear as findings; unreadable and timeout outcomes are unambiguously error-class skips.
- failure_path: `candidate times out/unreadable -> scan stores skip, no FileRecord -> content/frontmatter loops see nothing -> verify exits 0`.
- recommendation: convert unreadable and timeout scan skips into verify findings; display candidate, checked, excluded, and error-skip counts separately; refuse a clean result when requested candidates could not be checked.
- required_tests: one unreadable file, one timeout, mixed checked/skipped set, and all-candidates-skipped.

### ISSUE-006: Verify results are not preserved as a complete machine-readable business event

- first_pass: `3`
- severity: `medium`
- confidence: `high`
- product_logic_area: `business-event-auditability`
- issue_type: `business-event-auditability-gap`
- verified_repo_evidence:
  - Spec section 18.5 requires every verify run to emit a machine-readable artifact with per-file outcomes and summary counts.
  - Verify prints findings and its total to the console (`src/docmend/cli.py:861-864`) but writes no verification report.
  - Its JSONL log records `verify starting` and reused scan events, but the code does not log each verify finding or a verify terminal summary.
- inferred_business_impact: unattended operators cannot retain, compare, or independently audit the exact verification verdict; console capture becomes an undocumented data contract.
- not_verified: whether the per-run JSONL log was intended to be the verify artifact; it currently lacks the required verdict fields either way.
- failure_path: `verify finds problems -> console only -> process output not retained -> no durable run result for promotion/incident review`.
- recommendation: define a versioned verify-report artifact (or a complete stable JSONL event contract) carrying input refs, checked/skipped totals, findings, start/completion timestamps, and terminal status.
- required_tests: artifact schema round-trip, clean/finding terminal status, per-file finding preservation, and report-path behavior.

### ISSUE-007: Advertised parallel and write settings are accepted but operationally inert

- first_pass: `3`
- severity: `medium`
- confidence: `high`
- product_logic_area: `feature-flags-and-config-driven-rules`
- issue_type: `feature-flag-config-rule-gap`
- verified_repo_evidence:
  - `parallel.enabled`, model/workers/start-method/chunksize/maxtasksperchild, `write.atomic`, and `write.dry_run_default` are accepted by strict config and serialized into plans (`src/docmend/config.py:122-149,181-192`; plan schema lines 259-293).
  - Repository-wide source search found no consumer of `config.parallel`, `config.write.atomic`, or `config.write.dry_run_default` outside config declaration; apply always uses explicit `--write` and atomic writer functions.
  - Spec/ADR-0007 says enabling parallel mode opts into a process pool, while README describes switches as pinned and off by default.
- inferred_business_impact: operators can believe a large rollout is parallel when it is sequential, or believe atomic/dry-run policy changed when the values are silently ignored; plan provenance records a configuration that did not govern execution.
- not_verified: intended post-v1 lifecycle for these keys and whether `false` write values should be rejected as invalid safety downgrades.
- failure_path: `config validates -> plan snapshots setting -> execution ignores setting -> report gives no warning`.
- recommendation: reject unsupported/non-operative values with a clear release-specific error, or implement them. Constrain safety invariants such as atomic writes and dry-run default to constant values rather than accepting `false`.
- required_tests: behavioral test for every accepted config key, plus rejection tests for reserved/inert values.

### ISSUE-008: Targeted restore silently succeeds when requested IDs do not match

- first_pass: `3`
- severity: `medium`
- confidence: `high`
- product_logic_area: `approval-escalation-and-human-override-paths`
- issue_type: `edge-case-exception-gap`
- verified_repo_evidence:
  - `run_restore` filters records by `only_ids` and returns an empty outcome list when no ID matches (`src/docmend/restore.py:106-143`).
  - The CLI reports all zero counts and exits `0` because only skipped/failed outcomes trigger exit `1` (`src/docmend/cli.py:748-764`).
  - Tests cover matching `--id` values but not missing or partially missing requested IDs (`tests/test_restore.py:749-772`).
- inferred_business_impact: an operator typo or stale document ID can be interpreted by automation as a successful targeted recovery even though nothing was restored.
- not_verified: desired taxonomy: unmatched IDs could be input error `2` or finding `1`; partial matches need an explicit product decision.
- failure_path: `operator requests wrong ID -> replay list empty -> zero outcomes -> exit 0`.
- recommendation: reconcile requested IDs against eligible applied records before replay; enumerate unmatched IDs and return a non-clean exit, while preserving matched-ID results.
- required_tests: no IDs match, some IDs match, duplicate IDs, IDs present only in failed/intent records, and dry-run/write parity.

### ISSUE-009: Reversibility rationale remains internally contradictory

- first_pass: `4`
- severity: `low`
- confidence: `high`
- product_logic_area: `docs-adrs-and-product-rationale`
- issue_type: `convention-quality`
- verified_repo_evidence:
  - README correctly explains that only tool backups make content rewrites restorable (`README.md:21,27`) but later states restore replays a manifest back to original bytes without qualification (`README.md:77`).
  - Accepted ADR-0004 says every mutation is mechanically undoable (`docs/adr/adr-0004-apply-safety-gate-and-preservation.md:41,47,59,63`) despite the accepted `--preserved-by` and `--allow-no-backup` modes.
  - Manifest schema description says records carry everything needed to restore, while `backup_path` is explicitly nullable (`src/docmend/schemas/manifest.schema.json:5,58-60`).
- inferred_business_impact: future contributors can reintroduce the partial-undo trap or build automation on the stronger, false interpretation of "reversible manifest."
- not_verified: none; the contradiction is directly documented.
- failure_path: `maintainer reads durable ADR/schema rationale -> assumes manifest is self-sufficient -> weakens warnings/tests or downstream recovery logic`.
- recommendation: amend the ADR and schema descriptions to distinguish `manifest-replayable`, `tool-backup-restorable`, and `externally recoverable`; qualify the README safety summary consistently.
- required_tests: documentation contract check is optional; behavior tests should retain the three restore-capability classes.

## High-Risk Business Failure Paths

| path_id | sequence | consequence | mitigated_today |
| --- | --- | --- | --- |
| `HFP-001` | plan hash passes -> external edit/path swap -> apply publishes | newer content overwritten while report records old precondition | no; ISSUE-001 |
| `HFP-002` | crafted/wrong manifest -> restore write | file outside declared library mutated | no; confirmed ISSUE-002 |
| `HFP-003` | tool backup deleted -> verify exits 0 -> restore needed | original bytes unavailable when rollback is attempted | no; confirmed ISSUE-003 |
| `HFP-004` | collision fail aborts batch -> trailing actions omitted -> verify exits 0 | incomplete rollout promoted as verified | no; confirmed ISSUE-004 |
| `HFP-005` | every candidate times out/unreadable -> verify checks zero -> exits 0 | unverified corpus accepted | no; confirmed ISSUE-005 |

## Domain Invariants And Workflow Semantics

- verified_strong_controls: dry-run default; explicit write opt-in; plan config snapshot; source hash checks; collision policies; same-run target claims; hard-link/symlink skips; incremental intent/applied manifest records; resume reconciliation; tool run lock; restore live-after-hash check.
- invariant_gaps: exact opened-file identity is not held to commit (ISSUE-001); manifest root/path identity is not enforced by restore/verify (ISSUE-002); abort state is not represented for every plan action (ISSUE-004).
- workflow_states_missing: `aborted` or `not_attempted` report state; durable verify terminal state.

## Entitlements, Defaults, And Edge Cases

- entitlements_pricing_quotas: `not needed for this repo`.
- safe_defaults_verified: dry-run, skip collision, confidence floor, conservative risky-file skips, optional no-backup restricted to one action.
- edge_case_gaps: scan-time verification skips (ISSUE-005), unmatched restore IDs (ISSUE-008), inert configuration states (ISSUE-007).

## Flags, Scenarios, And Historical Semantics

- live_flags_reviewed: `--write`, `--dry-run`, `--backup-dir`, `--preserved-by`, `--allow-no-backup`, collision config, filters, encoding thresholds, resume manifest/run IDs, restore document IDs.
- unsupported_state_risk: accepted parallel/write settings do not change execution (ISSUE-007).
- historical_artifact_risk: pre-1.2 manifests have no trustworthy root; modern manifests do not enforce one root across records (ISSUE-002).
- scenario_coverage_gap: cross-root, lost-backup, abort-tail, verification-skip, concurrent replacement, and unmatched-ID scenarios are absent.

## Temporal, Override, And Exception Risks

- temporal_risk: check-to-use gaps can invalidate stale-input and modified-since-apply rules (ISSUE-001).
- override_posture: preservation overrides are explicit and warnings exist; documentation overstates the resulting restore capability (ISSUE-009).
- exception_risk: collision-fail has an implicit batch abort without explicit tail outcomes (ISSUE-004).

## Cross-Surface Consistency Risks

- spec_to_cli: accepted `verify --plan` and full accounting contract are not implemented (ISSUE-004).
- artifact_to_filesystem: manifest `source_root` does not constrain restore/verify paths (ISSUE-002).
- config_to_execution: parallel/write settings are recorded but ignored (ISSUE-007).
- docs_to_behavior: qualified restore behavior and unqualified reversibility claims coexist (ISSUE-009).
- ui_api_jobs: `not needed for this repo`; no live UI, HTTP API, queue, or background-job surface was found.

## Business Event Auditability

- adequate: plan decisions carry hashes/provenance; apply outcomes and mutation records carry run/action IDs; intent records cover multi-step kill windows; logs correlate run IDs.
- inadequate: verify omits backup health (ISSUE-003), report/verify omit unattempted plan actions (ISSUE-004), and verify has no complete machine-readable result event (ISSUE-006).

## Docs, ADR, And Product-Rationale Gaps

- accepted spec/ADR baseline is unusually detailed and directly test-linked.
- ADR-0012 is stronger than shipped verify behavior for backup refs, plan input, and skipped/failed accounting (ISSUE-003 through ISSUE-006).
- ADR-0004 and schema/README reversibility language needs capability-qualified terminology (ISSUE-009).

## Business Logic Testing Gaps

| issue_id | missing_executable_scenario |
| --- | --- |
| `ISSUE-001` | mutate/replace source after hash validation but before commit; same for restore |
| `ISSUE-002` | restore outside recorded root; mixed roots; verify wrong tree |
| `ISSUE-003` | missing/corrupt recorded source and overwritten-target backups |
| `ISSUE-004` | plan/report/manifest total coverage after mid-batch abort |
| `ISSUE-005` | verify unreadable, timeout, and zero-checked populations |
| `ISSUE-006` | durable verify result artifact/event contract |
| `ISSUE-007` | observable behavior or rejection for every accepted config key |
| `ISSUE-008` | unmatched and partially matched restore IDs |
| `ISSUE-009` | capability terminology consistency |

## Convention Recommendations

### Shared Across Projects

- destructive artifact consumers must bind every path to one explicit authority root and re-check containment/file identity at mutation time.
- a verification command must never report clean when requested work was not checked; checked, excluded, error-skipped, and not-attempted are distinct states.
- durable batch reports should carry terminal status and complete source-work-item accounting.
- recovery verification should validate recovery evidence, not only live output.
- every accepted configuration value must either affect execution or be rejected as unsupported.

### Repo-Specific

- add a convention tying SPEC-VHHB's plan/report/manifest identities together: one plan action -> exactly one terminal report outcome -> zero/one valid applied manifest completion, with intent records non-terminal.
- define manifest source-root rules for 1.2+ and a deliberate legacy restore policy for older records.
- define restore capability vocabulary: `rename-replayable`, `tool-backup-restorable`, `external-recovery-required`.
- define verify's durable report schema and whether `--plan` is mandatory, optional, or sidecar-discovered.

## Pass Log

| pass | lens | new_issues | result |
| --: | --- | --- | --- |
| 1 | domain inventory, destructive invariants, workflow states, failure cost | `ISSUE-001`, `ISSUE-002` | manifest/path and stale-input invariants insufficient |
| 2 | defaults, edge cases, scenarios, cross-surface behavior | `ISSUE-003`, `ISSUE-004`, `ISSUE-005` | four isolated reproductions confirmed false-clean/unsafe paths |
| 3 | temporal rules, exceptions, overrides, historical artifacts, config | `ISSUE-006`, `ISSUE-007`, `ISSUE-008` | audit-event, inert-config, targeted-restore gaps found |
| 4 | maintainability, terminology, test coverage, convention quality | `ISSUE-009` | reversibility rationale drift found |
| 5 | adaptive deepening on recovery, accounting, config, and scenario tests | none | no new issues; evidence/confidence refined |
| 6 | release-baseline comparison and negative search for absent product surfaces | none | second consecutive no-new-issue pass; convergence allowed |

## Claude Handoff

- fix_order:
  1. `ISSUE-002` manifest root/path enforcement before any further restore rollout.
  2. `ISSUE-001` mutation-time identity/precondition enforcement.
  3. `ISSUE-003`, `ISSUE-004`, and `ISSUE-005` so verify cannot falsely certify recovery or completeness.
  4. `ISSUE-006` durable verification event, then `ISSUE-007`/`ISSUE-008` contract cleanup.
  5. `ISSUE-009` ADR/schema/README terminology after behavior is settled.
- preserve_existing_strengths: do not weaken dry-run, preservation gate, atomic write, intent-record, resume, or collision safeguards while fixing these gaps.
- spec_change_control: the approved spec is binding; behavior or schema changes require the repo's spec/ADR workflow and traceability updates.
- suggested_follow_on_reviews: architecture boundary for ISSUE-001/002; data schema migration for manifest compatibility; test-suite review for scenario design; observability review for ISSUE-006.
- verification_expectation: add synthetic tests only; never use real library bytes or paths.

## Open Questions Or Assumptions

- Does the supported runtime contract permit editors, sync tools, indexers, or other processes to modify the tree during apply/restore? If not, document and enforce quiescence; otherwise ISSUE-001 requires descriptor/identity-level controls.
- Must pre-1.2 manifests remain directly restorable, or may restore require an explicit trusted source root/migration?
- Should verify require `--plan`, auto-discover it from `report.plan_ref`, or support both?
- Should unmatched restore IDs be exit `1` findings or exit `2` input errors?
- Are parallel settings intentionally deferred? If yes, should every non-default value be rejected until implementation lands?
- What retention/health-check cadence is promised for tool backups between apply and restore?

## Residual Risk

- The normal suite is green, but it does not exercise the confirmed high-risk combinations above.
- The opt-in 100k scale test was not run during this review; scale performance was not needed to confirm the logic findings.
- Real-library anomaly prevalence and external-backup reliability remain unverified owner/environment facts.
- POSIX local-filesystem assumptions reduce but do not remove path identity, concurrent modification, mount, and durability risks.
- No entitlement, pricing, UI, HTTP API, async-job, webhook, AI inference, or database business logic exists in the reviewed runtime; those categories are not needed for this repo.
