# Test Suite Review

## Review Metadata

- review_type: `test-suite-review`
- repo_root: `.`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- working_tree_state_at_start: `dirty`; pre-existing `AGENTS.md` modification and orchestrator-owned `docs/codex-reviews/` artifacts were preserved
- report_path: `docs/codex-reviews/2026-07-10-2034-test-suite-review-report.md`
- review_mode: `read-only test review; report write only`
- runtime: `Python 3.14`
- detected_test_frameworks: `pytest 9`, `Hypothesis`, `coverage.py`, `Typer CliRunner`, `allpairspy`, `pytest-xdist`
- local_test_entrypoints_inspected: `uv run coverage run -m pytest`; `uv run coverage report`; `scripts/check.py`; targeted pytest invocations
- ci_test_entrypoints_inspected: `.github/workflows/check.yml`, `.github/workflows/traceability.yml`, `.github/workflows/release.yml`
- conventions_input: `docs/handoff/conventions.md`
- binding_test_contract: `docs/specs/docmend.md` sections 7, 13.5, 14, and 17
- shared_research_used: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
- targeted_follow_up_web_research: `none`; the shared pack covered pytest, Hypothesis stateful testing, packaging, filesystem safety, artifact compatibility, and CI guidance
- default_exclusions: generated corpus output, lockfile, bulky byte-exact fixtures, review execution manifests, coverage output, caches
- browser_facing_surfaces_reviewed: `none`; this is a local Typer CLI/library
- charlotte_availability: `not available`
- charlotte_assisted_inspection: `not used; not applicable without a browser-facing surface`
- default_suite_result: `619 passed, 1 skipped in 6.44s`
- default_suite_coverage: `97% total branch-aware coverage; 65 statements and 15 partial branches uncovered; threshold 85%`
- xdist_result: `619 passed, 1 skipped with -n 2 in 5.33s`
- opt_in_scale_probe: `failed at DOCMEND_SCALE_COUNT=1000: 1050 manifest records != 850 applied outcomes`
- isolated_behavior_probes:
  - `verify` with its only candidate forced to a scan timeout exited `0` and printed `0 files checked, 0 findings`
  - a schema-conforming applied manifest record with `source_root` under one tree restored a target outside that tree; outcome was `restored`
- collection_summary: `620 collected cases across 39 test modules; the sole skipped case is the scale test`

## Test Layer Matrix

| test_area | classification | evidence_or_issue_ids |
| --- | --- | --- |
| `unit` | present and healthy | pure transforms, schemas, atomic writer, gate, watchdog; property coverage and 97% total coverage |
| `integration` | present but weak | strong filesystem adapters and restore drills, but mutation identity and recovery containment remain unprotected; ISSUE-001, ISSUE-006 |
| `end-to-end` | present but weak | CLI journeys exist, but verification can falsely certify skipped or unattempted work; ISSUE-002, ISSUE-003 |
| `api-contract` | present but weak | JSON/NDJSON schemas and round trips exist; historical/version and whole-artifact invariants are incomplete; ISSUE-009 |
| `security` | present but weak | inventory/plan containment and symlink discovery are tested; restore/verify containment and TOCTOU are not; ISSUE-001, ISSUE-006 |
| `ui` | not needed for this repo | no browser or graphical UI |
| `ux` | present and healthy | CLI help, flag conflicts, exit codes, summaries, and dry-run behavior are exercised |
| `accessibility` | not needed for this repo | no browser or graphical UI |
| `visual-regression` | not needed for this repo | no rendered visual surface |
| `performance-load` | present but weak | the only scale test is skipped by CI, currently fails when enabled, and asserts the wrong memory invariant; ISSUE-004, ISSUE-005 |
| `reliability-flake` | present and healthy | no retries or rerun plugins; timeout sleeps are watchdog/subprocess fixtures; default and two-worker runs passed |
| `concurrency` | present but weak | real-process lock contention is tested; external path/object replacement during destructive operations is not; ISSUE-006 |
| `persistence-migration` | present but weak | manifests, resume, and restore are heavily tested, but manifest-set and historical artifact compatibility are incomplete; ISSUE-001, ISSUE-009 |
| `packaging-deploy-smoke` | present but weak | tag workflow builds artifacts but only runs `docmend --version`; ISSUE-008 |
| `observability-diagnostics` | present but weak | framework and apply events are tested; verify has no durable terminal/finding event contract; ISSUE-011 |
| `property-fuzz` | present but weak | Hypothesis covers transforms and newline census only; stateful recovery/artifact sequences are absent; ISSUE-010 |
| `mutation` | missing but likely needed | high line coverage coexists with several false-clean semantic gaps; ISSUE-012 |
| `compatibility-upgrade` | present but weak | one synthesized pre-1.2 manifest case exists; no genuine released artifact corpus or future-version rejection matrix; ISSUE-009 |

## Severity Summary

| severity | count | issue_ids |
| --- | --: | --- |
| critical | 0 | none |
| high | 6 | `ISSUE-001`, `ISSUE-002`, `ISSUE-003`, `ISSUE-004`, `ISSUE-005`, `ISSUE-006` |
| medium | 5 | `ISSUE-007`, `ISSUE-008`, `ISSUE-009`, `ISSUE-010`, `ISSUE-011` |
| low | 1 | `ISSUE-012` |

## Findings

### ISSUE-001: Containment tests stop before the destructive restore and verify consumers

- first_pass: `4`
- severity: `high`
- confidence: `high`
- test_area: `security`
- issue_type: `security-gap`
- evidence:
  - `tests/test_artifact_containment.py:39-139` rejects escaping relative paths for inventory and plan records only.
  - Resume intent containment is covered, but no restore or verify test supplies mixed roots, an outside-root applied record, or a manifest belonging to a different verification tree.
  - `src/docmend/restore.py:83-103,121-157` reads and mutates absolute manifest paths without checking each record against `source_root`.
  - `src/docmend/verify.py:88-114` hashes manifest targets without binding them to verify's requested path.
  - Isolated probe: a record declaring one source root moved an outside target into that root and returned `restored`.
- risk: a crafted, concatenated, corrupt, or wrong-tree manifest can mutate outside the intended corpus during restore or let verify certify a different tree.
- recommendation: add end-to-end adversarial manifest tests before changing implementation. Require one coherent source root, per-record original/target containment, verify-path/root agreement, and safe legacy-root handling.
- required_tests: `outside original`, `outside target`, `mixed source_root`, `wrong-tree verify`, `symlinked parent swap`, `legacy manifest with explicit trusted root`.

### ISSUE-002: Verification tests omit scan skips, allowing a clean result after checking nothing

- first_pass: `3`
- severity: `high`
- confidence: `high`
- test_area: `end-to-end`
- issue_type: `e2e-gap`
- evidence:
  - `src/docmend/cli.py:843-865` builds findings from `inventory.files` and optional artifacts but never converts `inventory.skipped` into findings.
  - Discovery separately tests unreadable and timeout skip recording, while `tests/test_cli_verify.py` has no unreadable, timeout, mixed checked/skipped, or all-skipped case.
  - Isolated probe forced the only candidate through the timeout branch: verify exited `0` and printed `verify: 0 files checked, 0 findings`.
  - The binding spec treats verify as the machine substitute for manual review and requires error-class skips to be accounted for.
- risk: unreadable or pathological documents can disappear from the checked population while automation receives a clean exit code.
- recommendation: make verify tests assert candidate, checked, policy-excluded, unreadable, and timeout counts separately; unreadable/timeout must prevent exit `0`.
- required_tests: `one unreadable`, `one timeout`, `mixed checked plus skipped`, `all candidates skipped`, `policy exclusion remains non-error`.

### ISSUE-003: End-to-end accounting never proves that every planned action reached a terminal outcome

- first_pass: `3`
- severity: `high`
- confidence: `high`
- test_area: `end-to-end`
- issue_type: `e2e-gap`
- evidence:
  - `tests/test_apply.py:271-285` explicitly accepts that collision policy `fail` records the collision and omits later actions from the report.
  - `src/docmend/writer/apply.py:634-677` breaks the loop after the aborting action; the report has no `not_attempted` or terminal run status.
  - `src/docmend/verify.py:117-151` compares only applied report IDs with applied manifest IDs.
  - `docmend verify` has no plan input, so the suite cannot prove coverage of every planned action.
- risk: a partial batch can pass report/manifest reconciliation even though later plan actions were never attempted, which is unsafe for unattended 100k-file promotion.
- recommendation: add plan-aware terminal accounting before treating report/manifest reconciliation as complete. Every action should map exactly once to applied, would-apply, skipped, failed, or explicitly aborted/not-attempted.
- required_tests: `collision fail with trailing actions`, `fatal interruption after one action`, `missing skipped outcome`, `missing failed outcome`, `wrong plan/report pair`, `complete clean pair`.

### ISSUE-004: The opt-in scale test is stale and fails when enabled

- first_pass: `5`
- severity: `high`
- confidence: `high`
- test_area: `performance-load`
- issue_type: `ci-gap`
- evidence:
  - `tests/test_scale.py:9-11,109-113` requires `DOCMEND_SCALE=1`; `.github/workflows/check.yml:41-45` does not set it, so the only scale case is always skipped in the default gate.
  - `tests/test_scale.py:185-186` assumes manifest line count equals applied action count.
  - Manifest 1.3 writes an intent plus a final record for `rename_and_rewrite`, so record count is intentionally greater than action count.
  - Targeted run with `DOCMEND_SCALE=1 DOCMEND_SCALE_COUNT=1000` failed: `1050 != 850` at line 186.
- risk: the repository marks NFR-001 complete while its only acceptance test is both outside CI and no longer compatible with the live manifest protocol.
- recommendation: update the assertion to validate lifecycle records per action, then run a bounded scale lane in pull requests and a full 100k lane on a scheduled/manual runner with retained metrics.
- required_tests: `small CI scale with intent/final reconciliation`, `full 100k scheduled run`, `failure when an intent lacks a legal terminal state`.

### ISSUE-005: The scale assertion encodes the opposite of the binding memory requirement

- first_pass: `4`
- severity: `high`
- confidence: `high`
- test_area: `performance-load`
- issue_type: `convention-misalignment`
- evidence:
  - Spec NFR-001 at `docs/specs/docmend.md:355` requires no whole-corpus in-memory structures and memory usage independent of corpus size; section 14 repeats the no-whole-corpus model at line 765.
  - `tests/test_scale.py:39-51` states that inventory, plan, and report are held in memory by design and budgets 10 KiB per file.
  - `tests/test_scale.py:194-205` accepts a ceiling that grows linearly with file count, approximately 1.0 GiB at 100k files.
  - The traceability matrix nevertheless marks NFR-001 complete at `docs/specs/docmend.md:850` based on this count-proportional test.
- risk: the acceptance test can stay green while the implementation violates the release-blocking scalability contract and exhausts memory on larger corpora.
- recommendation: resolve the spec/architecture conflict through the approved spec/ADR process. Then test the chosen invariant at multiple corpus counts and assert either a fixed memory envelope or an explicitly approved bounded-growth model.
- required_tests: `at least three corpus counts`, `peak-memory slope assertion`, `per-stage measurement in separate processes`, `large-record metadata stress`.

### ISSUE-006: Destructive precondition tests do not cover object replacement between validation and mutation

- first_pass: `2`
- severity: `high`
- confidence: `medium`
- test_area: `concurrency`
- issue_type: `concurrency-gap`
- evidence:
  - Apply reads/hashes a path at `src/docmend/writer/apply.py:363-380` and later stats/mutates through fresh path operations at lines 503-517.
  - Restore hashes a target at `src/docmend/restore.py:83-103` and later stats/mutates it at lines 153-258.
  - Existing tests cover edits before apply/restore, parent-symlink replacement before apply, run locks, and injected mutation failures; repository-wide test search found no deterministic replacement between the final check and publish/unlink.
  - Shared research treats file identity at the actual mutation point as the relevant safety invariant.
- risk: an editor, sync client, or external process can replace a pathname after validation, allowing newer bytes or an outside object to be mutated despite a passing stale-hash/containment check.
- recommendation: create deterministic seam tests around the last precondition-to-commit boundary for apply and restore. The implementation should bind validation and mutation to one object identity or revalidate immediately before commit.
- required_tests: `rewrite replacement`, `rename replacement`, `rename-and-rewrite source replacement`, `restore target replacement`, `parent symlink swap at commit`, `hard-link identity policy`.

### ISSUE-007: The traceability gate proves token presence, not executable requirement coverage

- first_pass: `5`
- severity: `medium`
- confidence: `high`
- test_area: `cross-cutting`
- issue_type: `convention-quality`
- evidence:
  - `scripts/check_traceability.py:103-112` concatenates test source and considers a requirement covered when its ID appears anywhere.
  - `tests/test_check_traceability.py:113-122` explicitly proves that a comment-only `# spec: FR-001` satisfies the gate.
  - The gate does not validate the test node named in the traceability matrix, ensure that node is collected, ensure it runs in a required CI lane, or ensure it passes.
  - ISSUE-004 demonstrates the consequence: NFR-001 is marked Complete while its named test is skipped by default and fails when enabled.
- risk: `Complete` becomes a documentation claim disconnected from executable evidence, overstating release confidence.
- recommendation: keep the ID drift check, but add a generated requirement-to-node manifest or pytest markers and verify collection, lane assignment, and latest passing evidence for release-blocking requirements.
- required_tests: `missing named node`, `renamed node`, `permanently skipped node`, `xfail node`, `required slow lane absent`, `comment-only mention rejected as completion evidence`.

### ISSUE-008: Packaging smoke tests do not exercise the installed product contract

- first_pass: `1`
- severity: `medium`
- confidence: `high`
- test_area: `packaging-deploy-smoke`
- issue_type: `packaging-deploy-gap`
- evidence:
  - `tests/test_smoke.py:1-12` is still a pre-implementation placeholder that imports only `__version__` from the editable project.
  - `.github/workflows/check.yml` does not build or install distribution artifacts.
  - `.github/workflows/release.yml:28-33` builds sdist and wheel only after a tag, then invokes only `docmend --version` from the wheel.
  - Core commands load packaged JSON schemas; a missing data-file or sdist-build regression would not be caught by `--version`.
- risk: the tag workflow can publish artifacts that import but fail on scan/plan/apply/verify or cannot reproduce a wheel from the sdist.
- recommendation: before tag publication, build sdist and wheel, build a wheel from the sdist, inspect both, install in clean environments, and run a synthetic single-file CLI journey that loads every packaged schema.
- required_tests: `wheel full journey`, `sdist-to-wheel`, `schema/resource presence`, `console entry point`, `--help`, `scan-plan-apply-verify`, `restore smoke`.

### ISSUE-009: Artifact compatibility tests do not preserve released producers or reject unsupported futures

- first_pass: `4`
- severity: `medium`
- confidence: `high`
- test_area: `compatibility-upgrade`
- issue_type: `compatibility-gap`
- evidence:
  - Tags `v1.0.0`, `v1.0.1`, and `v1.0.2` exist, but no committed golden inventory/plan/report/manifest corpus captures their real emitted bytes.
  - `tests/unit/writer/test_manifest.py:156-165` simulates pre-1.2 compatibility by deleting one field from a current record.
  - Artifact schemas and models accept any `1.x` version; tests do not assert rejection or migration for a future `1.999` producer.
  - No manifest-set tests enforce coherent run/root identity, legal sequence/lifecycle transitions, or strict duplicate JSON member rejection.
- risk: current readers can silently reinterpret future or malformed artifacts, while compatibility regressions against real released output remain invisible.
- recommendation: commit conspicuously synthetic golden artifacts emitted by each supported release, then test exact-version dispatch, migration/rejection, whole-manifest invariants, and malformed adversarial inputs.
- required_tests: `v1.0.0/v1.0.1/v1.0.2 producer fixtures`, `future minor rejection`, `mixed-version manifest`, `sequence gap/order`, `result-dependent fields`, `duplicate JSON members`.

### ISSUE-010: Property-based testing stops at pure transforms instead of the recovery state machine

- first_pass: `2`
- severity: `medium`
- confidence: `high`
- test_area: `property-fuzz`
- issue_type: `property-fuzz-gap`
- evidence:
  - Hypothesis is used in discovery newline census and pure transform tests only.
  - Apply/resume/restore has multiple durable states (`intent`, `applied`, `failed`), repeated resume manifests, collisions, partial restore, and ordering rules, but no Hypothesis rule-based state machine or generated artifact sequence test.
  - Hand-authored interruption tests are strong but enumerate selected windows and use injected exceptions rather than exploring long action/retry sequences.
- risk: unanticipated combinations of interruption point, duplicate evidence, order, collision, and retry can violate idempotency or recovery even though all named examples pass.
- recommendation: add a model-based state machine over a small synthetic corpus and an independent reference model of legal disk/artifact states.
- required_tests: `random interrupt/retry sequences`, `multiple resume manifests`, `intent-final ordering`, `restore-retry sequences`, `collision policy changes`, `corrupt/torn tail generation`.

### ISSUE-011: Observability tests do not require a durable verify verdict

- first_pass: `4`
- severity: `medium`
- confidence: `high`
- test_area: `observability-diagnostics`
- issue_type: `observability-gap`
- evidence:
  - `tests/test_observability.py` verifies framework fields and handlers; the integration assertion named by NFR-003 covers apply outcomes.
  - `src/docmend/cli.py:842-865` logs `verify starting` but sends findings and the terminal count only to console.
  - Repository-wide event search found no verify completion or per-finding structured event, and no test asserts one.
- risk: unattended verification has no retained machine-readable terminal verdict; console loss prevents later audit of what was checked or skipped.
- recommendation: define a versioned verify report or stable JSONL finding/completion events, then assert clean, findings, skipped-error, and input-error terminal states.
- required_tests: `verify.completed`, `per-finding event`, `checked/skipped totals`, `exit/status agreement`, `log write failure`, `privacy-safe path/error fields`.

### ISSUE-012: No targeted mutation baseline checks assertion strength in the safety core

- first_pass: `5`
- severity: `low`
- confidence: `medium`
- test_area: `mutation`
- issue_type: `mutation-gap`
- evidence:
  - No mutation tool or mutation CI lane is configured.
  - The suite reports 97% coverage while ISSUE-002 and ISSUE-003 show that covered verification code can still encode incomplete semantics.
- risk: high coverage may continue to conceal weak or over-narrow assertions in gate, verify, artifact, and recovery logic.
- recommendation: introduce a small, time-bounded mutation baseline for pure gate predicates, verify reconciliation, artifact validators, and recovery decision functions; do not start with the whole filesystem suite.
- required_tests: `mutation score baseline`, `survivor review`, `changed-lines mutation lane for safety modules`.

## Missing Test Types

- missing_and_required_now:
  - restore/verify manifest containment and wrong-root tests
  - verify unreadable/timeout accounting
  - plan-aware terminal accounting tests
  - a working scale acceptance lane
  - installed wheel/sdist journey tests
- missing_and_likely_needed:
  - recovery state-machine/property tests
  - historical artifact golden fixtures
  - targeted mutation tests
  - apply/restore object-identity race tests
- not_needed_for_this_repo:
  - browser UI, accessibility, visual regression, HTTP API, database migration, and load-generator request testing

## High-Risk Untested Behaviors

- Restoring a schema-valid manifest whose paths or roots do not belong to one corpus.
- Verifying a corpus where every candidate timed out or was unreadable.
- Verifying a run that aborted before all plan actions received outcomes.
- Replacing a source/target object between its final hash/containment check and mutation.
- Processing 100k files under the binding memory contract with the current manifest protocol.
- Installing released artifacts and running commands that load packaged schemas.
- Reading real artifacts produced by all supported released versions.

## Security Testing Gaps

- high: restore and verify do not have end-to-end root-containment tests (ISSUE-001).
- high: apply and restore lack deterministic TOCTOU/object-identity tests (ISSUE-006).
- medium: manifest-set trust checks do not cover mixed roots/runs/versions or duplicate JSON members (ISSUE-009).
- adequate: discovery does not follow symlinks; inventory/plan reject lexical escapes; apply tests a pre-run parent-symlink swap; run-lock contention uses real subprocesses.

## API Contract Testing Gaps

- The relevant API is the CLI plus JSON/NDJSON/YAML artifacts; no network API exists.
- Plan, report, and manifest are not verified as one complete terminal transaction (ISSUE-003).
- Historical producers, future-version rejection, and whole-manifest invariants are incomplete (ISSUE-009).
- Installed-package tests do not prove schema artifacts are present and usable (ISSUE-008).

## CI And Execution Coverage

- pull_request_and_main_gate: Ubuntu, Python from `.python-version` (`3.14`), locked full dependency group, format, lint, strict type check, default pytest under coverage, 85% threshold, dependency audit.
- actual_default_result: `619 passed, 1 skipped`; branch-aware coverage `97%`.
- parallel_diagnostic_result: `619 passed, 1 skipped` under `pytest -n 2`; no immediate order/global-state failure observed.
- unexecuted_in_ci: the sole scale test, because no workflow sets `DOCMEND_SCALE`.
- hidden_failure: the scale test fails when enabled at 1,000 files (ISSUE-004).
- release_only_evidence: sdist/wheel build and wheel `--version` smoke occur only after a tag, immediately before publishing.
- missing_execution_evidence: full installed CLI journey, sdist-to-wheel reproducibility, historical artifact compatibility, supported POSIX platform/filesystem matrix, full 100k metrics.

## Charlotte-Assisted Opportunities

- availability: `not available`
- current_opportunities: `none`; no browser-facing surface exists.
- future_opportunities: if a browser UI is added, use Charlotte for keyboard navigation, focus order, accessible names, error recovery, and real end-to-end flows before classifying UI/UX/accessibility layers.

## Test Strategy Recommendations

1. Fix and execute the scale lane; do not retain NFR-001 `Complete` evidence until the test passes and the memory contract is reconciled.
2. Add the three false-safety end-to-end families first: restore/verify containment, verify skipped candidates, and plan-aware terminal accounting.
3. Add deterministic object-replacement seams around destructive commits.
4. Promote release smoke to an installed sdist/wheel single-file journey that loads all package resources.
5. Build a synthetic historical artifact corpus and model-based recovery state machine.
6. Add targeted mutation testing only after the higher-value missing scenarios are protected.

## Convention Recommendations

- Preserve conventions #1 and #6: the locked gate and synthetic-only fixture policy are sound and well followed.
- Amend the test convention so every release-blocking traceability row records a concrete pytest node and execution lane, not only a requirement token.
- Resolve the NFR-001 test/spec contradiction through the spec/ADR workflow; do not silently redefine bounded memory in test comments.
- Require every slow/opt-in acceptance test to have an owned CI/manual lane and freshness evidence.
- Replace the stale pre-implementation smoke-test prose with the installed-package contract once the packaging test is added.

## Pass Log

| pass | lens | new_issue_ids | result |
| --- | --- | --- | --- |
| 1 | inventory, test layout, frameworks, CI, coverage, layer matrix | `ISSUE-008` | packaging smoke is release-only and version-only |
| 2 | unit/integration quality, fixtures, mocks, determinism, recovery seams | `ISSUE-006`, `ISSUE-010` | strong examples; object-identity and stateful exploration absent |
| 3 | end-to-end, CLI UX, browser/UI applicability, convention-rationale alignment | `ISSUE-002`, `ISSUE-003` | two false-clean verification paths identified |
| 4 | security, artifact contracts, persistence, performance, CI reality, observability | `ISSUE-001`, `ISSUE-005`, `ISSUE-009`, `ISSUE-011` | containment, memory-contract, compatibility, and verdict gaps identified |
| 5 | adaptive probes: scale execution, traceability enforcement, mutation posture | `ISSUE-004`, `ISSUE-007`, `ISSUE-012` | scale failure reproduced; traceability limitation confirmed |
| 6 | anti-pattern and flake pass; two-worker execution | none | no retries/snapshot sprawl/brittle selectors; xdist run passed |
| 7 | merged-inventory deduplication and residual-layer rescan | none | second consecutive no-new-issue pass; convergence allowed |

## Claude Handoff

- highest_priority: `ISSUE-001`, `ISSUE-002`, `ISSUE-003`, `ISSUE-004`, `ISSUE-005`, `ISSUE-006`
- first_implementation_batch: containment plus false-clean verification tests; these protect destructive/release decisions and can be written before fixes
- spec_decision_required: `ISSUE-005`; choose independent-of-corpus memory or approve a different bounded-growth contract before changing the test
- workflow_decision_required: choose an owned runner/cadence for the 100k scale lane and artifact compatibility fixtures
- safe_fixture_rule: all added corpus and artifact fixtures must remain conspicuously synthetic; never use real library bytes or paths
- suggested_review_order_after_fixes: focused tests -> full default gate -> opt-in small scale -> full 100k lane -> installed artifact journey
- likely_cross_review_links: API-contract, product/business-logic, security, performance, CI/CD, release-readiness, and observability reports should reuse the matching findings rather than duplicate incompatible fixes

## Open Questions Or Assumptions

- supported_posix_matrix: only Linux CI is established; macOS/BSD/network/removable filesystem support is not defined.
- threat_model: external editors/sync processes during apply/restore are plausible but not explicitly accepted or excluded; ISSUE-006 confidence remains medium for that reason.
- scale_contract: the spec says memory independent of corpus size, while implementation/test commentary assumes count-proportional whole-run artifacts.
- slow_lane_owner: no workflow or documented operator currently owns periodic `DOCMEND_SCALE=1` execution.
- artifact_compatibility_window: readers accept the `1.x` family, but supported exact producer versions and migration/rejection rules are not defined per artifact.

## Residual Risk And Coverage Gaps

- Repository-only review cannot establish behavior on the owner's real library, alternate filesystems, power loss, disk faults, or external concurrent writers.
- The 100k test was not rerun at full size during this review because the 1,000-file supported probe already failed before its memory assertion.
- Coverage percentage remains strong evidence of exercised code, but not of complete destructive-workflow semantics.
- No browser, network API, database, queue, or UI exists; those layers were marked not needed rather than treated as missing.
