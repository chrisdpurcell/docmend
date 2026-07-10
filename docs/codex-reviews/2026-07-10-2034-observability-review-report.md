# Observability Review

## Review Metadata

- review_type: `observability-review`
- report_path: `docs/codex-reviews/2026-07-10-2034-observability-review-report.md`
- reviewed_at: `2026-07-10`
- repo_path: `.`
- repo_name: `docmend`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- release_baseline: `v1.0.2` (`ffdcc47d6c3a5375f0454c4b3afa5b734260acc1`)
- baseline_comparison: `v1.0.2..HEAD` changes only agent-handoff/configuration documentation; no runtime observability source changed after the release tag.
- working_tree_state: `dirty before review` (`AGENTS.md` modified; `docs/codex-reviews/` untracked). Pre-existing changes and orchestrator-owned artifacts were not edited.
- review_mode: `read-only except for this requested report`
- review_scope: `full repository observability surface: logging, batch/job records, metrics applicability, tracing applicability, error visibility, exit-code alerting, runbooks, CI/release visibility, telemetry privacy, cost, and tests`
- runtime: `Python >=3.14 local batch CLI; sequential single process in the implemented v1 path`
- detected_frameworks_and_runtimes: `Typer, Rich, Pydantic v2, structlog through stdlib logging, JSON/JSONL artifacts, local POSIX filesystem`
- detected_observability_tooling_and_vendors: `structlog 26.x; stdlib FileHandler/StreamHandler; Rich ConsoleRenderer; no external vendor, collector, agent, gateway, or remote telemetry`
- telemetry_libraries_inspected: `structlog contextvars, ProcessorFormatter, JSONRenderer, dict_tracebacks, ConsoleRenderer; stdlib root logger and handlers`
- collector_agent_gateway_surfaces_inspected: `none present; not needed for the implemented local-only CLI`
- logging_surfaces_inspected: `src/docmend/observability.py; all logger call sites in cli.py, discovery.py, planning.py, restore.py, writer/apply.py, and writer/manifest.py; logging tests and CLI integration tests`
- metrics_surfaces_inspected: `artifact totals, console summaries, per-file elapsed fields on watchdog timeouts, scale-test measurements; no metrics exporter or service`
- tracing_surfaces_inspected: `run_id context binding and artifact reference chains; no distributed tracing SDK or network boundary`
- alerting_and_dashboard_surfaces_inspected: `exit-code taxonomy, CLI findings/refusals, GitHub Actions checks; no pager, dashboard, or resident service`
- ci_and_deployment_surfaces_inspected: `.github/workflows/check.yml, dependency-review.yml, lint-markdown.yml, release.yml, traceability.yml, validate-specs.yml; README release process`
- operational_docs_inspected: `README.md; restore and resume runbooks; spec sections 13.4-13.6, 17.3, 18.1-18.6, 20, and Appendix B; ADR-0013; docs/research/structured-logging-library.md`
- conventions_input: `docs/handoff/conventions.md` (repo equivalent of `docs/conventions.md`)
- important_external_observability_surfaces_not_in_repo: `GitHub Actions retention and repository settings; any shell scheduler or wrapper that captures stdout/stderr and exit codes; host filesystem permissions/umask; operator backup monitoring`
- known_operational_dependencies: `local filesystem capacity and durability; stderr/stdout capture when automated; user retention and review of .docmend artifacts`
- important_telemetry_unknowns: `whether target hosts are multi-user; whether logs are routinely shared; actual run-log size on the real corpus; external wrapper/scheduler behavior; desired retention/splitting threshold`
- prior_baseline_or_release_artifacts_compared: `v1.0.2 tag, current spec revision 0.25, NFR-003 traceability claim, OQ-017/RQ-017 decision, structured-logging research, current release workflow`
- exclusions: `generated caches, coverage output, private real-library content, byte-exact fixture contents, orchestrator execution/sweep/live-status artifacts, external GitHub settings`
- shared_research_used: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
- targeted_internet_follow_up: `none; the 2026-07-10 shared pack already covered current OpenTelemetry log-model, Prometheus batch-instrumentation, OWASP logging/privacy, Python 3.14 logging, and structlog guidance`
- validation_run: `UV_CACHE_DIR=/tmp/docmend-uv-cache XDG_STATE_HOME=/tmp/docmend-xdg-state uv run pytest -q tests/test_observability.py tests/test_cli_scan.py tests/test_cli_plan.py tests/test_cli_apply.py tests/test_cli_verify.py tests/test_restore.py` -> `102 passed in 1.96s`
- focused_failure_probe: `monkeypatched discovery.scan to raise RuntimeError through CliRunner` -> `exit 1; JSONL contained only scan starting; no failure/exception event`
- focused_permission_probe: `configure_logging under umask 022 in /tmp` -> `.docmend directory 0755; JSONL log 0644`

## Observability Area Matrix

| observability_area | relevance | assessment | findings |
| --- | --- | --- | --- |
| `structured-logging` | high | Strong JSONL/console foundation, but run lifecycle and event semantics are incomplete. | ISSUE-001, ISSUE-002, ISSUE-004 |
| `signal-schema-resource-identity` | high | `run_id`, command, level, and timestamp are consistent; event vocabulary, version identity, units, and workflow lineage are not. | ISSUE-004 |
| `metrics-instrumentation` | medium | No exporter is needed; artifact counts are useful, but durable duration/progress/rate signals are missing. | ISSUE-001, ISSUE-008 |
| `distributed-tracing` | not needed for this repo | No network, service, queue, or distributed request path exists. Artifact references plus run IDs are the appropriate local correlation substrate. | none |
| `error-monitoring` | high | Expected per-file errors are represented, but unexpected command failures have no structured terminal record or stack. | ISSUE-002 |
| `alerting-and-paging` | medium | Non-zero exits are an appropriate local alert equivalent; their detailed terminal evidence is not consistently durable. Paging is not needed. | ISSUE-001, ISSUE-002 |
| `alert-ownership-and-routing` | low | The local operator/owner is explicitly the alert owner; no multi-team routing is needed. | none |
| `dashboards-and-visualization` | not needed for this repo | Reports and command summaries fit the discrete local batch lifecycle better than a resident dashboard. | none |
| `sli-slo-error-budget` | medium | RPO/RTO and correctness targets exist, but batch completion time, terminal outcome, and progress are not emitted as reliable SLIs. A service-style error budget is not needed. | ISSUE-001, ISSUE-008 |
| `runbooks-and-operability` | high | Restore/resume procedures are detailed; log interpretation, incomplete-run diagnosis, and telemetry failure handling are not documented as stable practice. | ISSUE-009 |
| `correlation-context-propagation` | high | structlog contextvars consistently bind run ID and command; cross-stage lineage is available only indirectly through artifacts/action IDs. | ISSUE-004 |
| `telemetry-pipeline-resilience` | medium | Local FileHandler avoids a remote collector dependency, but sink failure, size growth, and terminal flushing/closure are not contract-tested. | ISSUE-002, ISSUE-007 |
| `background-jobs-workers` | not needed for this repo | No implemented worker pool or scheduler exists; the accepted parallel config is dormant and outside current telemetry topology. | none |
| `data-pipeline-batch-visibility` | critical | This is the primary operational surface; clean, finding, refused, interrupted, and failed terminal states are not uniformly distinguishable from logs alone. | ISSUE-001, ISSUE-002, ISSUE-008 |
| `client-ui-telemetry` | not needed for this repo | No GUI/web client exists; Typer/Rich console behavior is covered as CLI operability. | none |
| `deploy-release-observability` | medium | GitHub Actions exposes check/release logs externally; no resident deployment exists. External retention/settings could not be verified. | none |
| `audit-and-compliance-logging` | medium | Manifest/report artifacts, not diagnostic logs, are the mutation audit authority. No legal compliance regime is established. Verify/restore terminal evidence remains incomplete. | ISSUE-001 |
| `telemetry-data-hygiene-redaction` | high | No document bodies were found in current log calls, but permissions, absolute paths, raw errors, and foreign messages defeat the stated minimization boundary. | ISSUE-003, ISSUE-005 |
| `cost-cardinality-sampling` | medium | No vendor bill or label-cardinality risk exists; always-DEBUG per-file JSONL can consume unbounded local disk without a measured split policy. | ISSUE-007 |
| `observability-testing-validation` | high | Framework and apply happy-path tests pass, but command lifecycle, failure, privacy, permissions, and sink degradation are untested. | ISSUE-006 |

## Severity Summary

| severity | count | issue_ids                                             |
| -------- | ----: | ----------------------------------------------------- |
| critical |     0 | none                                                  |
| high     |     2 | ISSUE-001, ISSUE-002                                  |
| medium   |     5 | ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-006, ISSUE-008 |
| low      |     2 | ISSUE-007, ISSUE-009                                  |

## Findings

### ISSUE-001 — Command logs are not durable batch job records

- severity: `high`
- confidence: `high`
- first_pass: `1`
- observability_area: `data-pipeline-batch-visibility`
- issue_type: `data-pipeline-visibility-gap`
- verification: `verified directly from repo evidence and focused event inventory`
- evidence:
  - `docs/specs/docmend.md:941-949` says scan, plan, apply, and verify job records capture start/finish, per-file outcomes/reasons, summary counts, and terminal exit meaning.
  - `src/docmend/cli.py:176-203` and `src/docmend/discovery.py:448-454` give scan start and aggregate completion events, but no duration, exit outcome, or artifact-publication result.
  - `src/docmend/cli.py:263-344` logs plan start and prints its summary only to the console; no structured plan-completed event exists.
  - `src/docmend/writer/apply.py:625-703` logs per-action outcomes and builds a timestamped report, but the JSONL has no run-started, report-published, terminal status, exit code, duration, or aggregate-summary event.
  - `src/docmend/restore.py:120-143` logs per-record outcomes; `src/docmend/cli.py:758-764` prints the only aggregate/terminal result.
  - `src/docmend/cli.py:831-865` logs verify start and reuses scan events, but verify findings and its final finding count exist only on the console. Verify writes no result artifact.
- impact: `A log consumer cannot reliably distinguish clean completion from exit-1 findings, refusal, interruption, artifact-publication failure, or an incomplete process. Verify's actual defects can disappear when stdout is not retained, and the NFR-003 claim that a run is diagnosable without re-running is not true across commands.`
- recommendation: `Create one command-lifecycle boundary that emits a stable run.started event and exactly one terminal run.completed, run.findings, run.refused, run.interrupted, or run.failed event after final artifact publication. Include started_at, completed_at, duration_ms, exit_code, outcome, counts, bytes, dry_run/write mode, input/output artifact references, and safe parent/input run IDs. Give verify and restore a durable result record, either through an explicit report artifact or complete JSONL finding and summary events.`
- acceptance_evidence:
  - `Every command and every 0/1/2/3 terminal path produces exactly one parseable terminal event with matching exit_code and counts.`
  - `A killed run has a start event and no terminal event; a completed run always has both, making interruption mechanically detectable.`
  - `Verify findings and restore outcomes remain reconstructable after stdout/stderr are discarded.`
  - `Terminal success is emitted only after required artifacts are durably published.`

### ISSUE-002 — Unexpected failures leave no structured cause or terminal state

- severity: `high`
- confidence: `high`
- first_pass: `3`
- observability_area: `error-monitoring`
- issue_type: `error-monitoring-gap`
- verification: `verified directly from code and a focused runtime probe`
- evidence:
  - Repository search finds no `logger.exception`, `run.failed`, or command-level exception boundary after logging is configured.
  - Expected artifact/config errors are converted to console messages in individual branches, but unexpected exceptions from discovery, planning, writer, artifact publication, or logging setup propagate without a structured failure event.
  - The focused probe replaced `discovery.scan` with a function raising `RuntimeError`. CliRunner exited 1 and the JSONL contained only `scan starting`; it contained neither exception type nor stack nor terminal outcome.
  - `src/docmend/observability.py:101-105` configures structured exception rendering, but no production call site supplies `exc_info`, so that capability is effectively unused.
- impact: `The highest-value diagnostic path—an unforeseen batch abort—produces the least evidence. Operators cannot tell whether the run was killed, crashed, or failed after a partial stage, and may need to reproduce a failure against sensitive or already-mutated data.`
- recommendation: `Wrap each configured command lifecycle in a shared error boundary. Log expected input/refusal failures as stable safe codes; log unexpected Exception paths with run.failed, exception_type, phase, safe exception rendering, and terminal timing; record KeyboardInterrupt/SystemExit as interrupted or the already-selected terminal outcome. Flush and close owned handlers in a finally block without hiding the original failure.`
- acceptance_evidence:
  - `Fault injection at discovery, planning, mutation, manifest append, report publication, and verify reconciliation produces one run.failed event with a safe exception classification.`
  - `Ctrl-C produces run.interrupted and is distinguishable from an internal error.`
  - `The original exception/exit code remains authoritative if terminal logging itself fails.`

### ISSUE-003 — Confidential run logs default to world-readable metadata permissions

- severity: `medium`
- confidence: `high`
- first_pass: `4`
- observability_area: `telemetry-data-hygiene-redaction`
- issue_type: `telemetry-data-hygiene-gap`
- verification: `verified directly from code and a permission probe`
- evidence:
  - `docs/specs/docmend.md:730-740` classifies artifacts containing real paths and hashes as confidential and identifies shared logs/artifacts as a privacy threat.
  - `src/docmend/observability.py:85-99` creates the directory with ordinary `mkdir` defaults and the log with `logging.FileHandler`, without a restrictive mode or post-open permission check.
  - Under a normal `022` umask, the focused probe created the directory as `0755` and the JSONL file as `0644`.
  - The log may contain filenames, symlink targets, hashes, error details, and manifest-derived paths even though no document bodies were found in current call sites.
- impact: `On a multi-user host, other local accounts can read document/library metadata from every default run log. Filenames and paths alone may disclose personal, legal, medical, or financial context.`
- recommendation: `Create the private run-artifact directory with 0700 semantics and log files with 0600 semantics using a no-follow, ownership-checked open path or an equivalent safe handler. Refuse or warn clearly when an existing log destination is not private enough. Align inventory/plan/report permission handling in the follow-on security review.`
- acceptance_evidence:
  - `Permission tests under umasks 000, 022, and 077 prove new log files are 0600 and private directories are 0700 or stricter.`
  - `A pre-existing symlink/non-regular log target is refused rather than followed.`
  - `A test documents the policy for user-selected pre-existing directories.`

### ISSUE-004 — The event vocabulary and resource identity are not stable enough for reliable queries

- severity: `medium`
- confidence: `high`
- first_pass: `1`
- observability_area: `signal-schema-resource-identity`
- issue_type: `signal-schema-resource-identity-gap`
- verification: `verified directly from all production log call sites and the approved research contract`
- evidence:
  - `docs/research/structured-logging-library.md:42-80` recommends a small closed dotted event vocabulary, stable reason fields, units, and explicit run/command identity.
  - Production event strings are free prose such as `scan starting`, `planned skip`, `apply outcome`, `restore outcome`, and `torn trailing manifest line dropped` (`src/docmend/**/*.py`). `tests/test_observability.py:116-126` intentionally accepts arbitrary stdlib text as the event value.
  - Similar concepts use inconsistent fields: `err` versus `error`; `elapsed` without a unit suffix; `size` versus artifact `size_bytes`; `status`, `reason`, and `detail` without a common outcome/error envelope.
  - Log records omit docmend version, log schema version, phase/stage, terminal outcome, and direct input/parent run lineage. Artifact files contain some of this identity, but the JSONL does not.
- impact: `Queries and future support tooling must depend on prose and command-specific field guesses. Event renaming becomes a silent breaking change, cross-version diagnosis is ambiguous, and scan→plan→apply→verify correlation requires opening multiple artifacts instead of following explicit lineage fields.`
- recommendation: `Define a versioned internal log contract without adopting an external SDK: dotted event names, one outcome/error envelope, unit-suffixed numeric fields, docmend_version, log_schema_version, stage, and safe input/parent run IDs. Keep run_id and command context binding. Map foreign stdlib records into a distinct log.foreign event with logger identity instead of treating arbitrary prose as the primary event name.`
- acceptance_evidence:
  - `A table or typed registry owns every event and required/optional fields.`
  - `Schema-contract tests reject renamed/missing required fields and unit ambiguity.`
  - `One query can group failures and durations across all commands without parsing prose.`

### ISSUE-005 — Relative-path and redaction claims are not enforced at the sink

- severity: `medium`
- confidence: `high`
- first_pass: `2`
- observability_area: `telemetry-data-hygiene-redaction`
- issue_type: `telemetry-data-hygiene-gap`
- verification: `direct repo evidence; sensitive-content exposure through future/foreign messages is inferred`
- evidence:
  - `src/docmend/observability.py:16-18` states that callers provide relative paths and never document content, but there is no enforcing processor or allowlist.
  - `src/docmend/cli.py:187,280,288,842` logs caller-supplied PATH or inventory strings; absolute invocation paths remain absolute.
  - `src/docmend/discovery.py:244-255` logs raw exception strings and symlink targets; `src/docmend/restore.py:134-139` logs manifest-derived original paths and free-form details; `src/docmend/writer/apply.py:533-537` can log a resolved target path.
  - `src/docmend/observability.py:89-108` deliberately captures foreign stdlib messages into the same always-DEBUG JSONL sink. No redaction processor filters message, detail, error, target, or traceback data.
  - `tests/test_observability.py:75-126` asserts positive fields only; no test seeds secrets, absolute private paths, control characters, or document snippets and proves their absence.
- impact: `Current calls already expose more path detail than the documented relative-path contract. A future exception, dependency log, or debug addition can persist document content or credentials without crossing any tested boundary, while the spec marks log redaction complete.`
- recommendation: `Add a final sink-side sanitizer/redaction processor. Allowlist structured fields; convert file-scoped paths to source-root-relative safe identifiers; record error code/type separately from a sanitized message; bound free-form values; and scrub secrets, control characters, environment values, document snippets, and traceback locals. Keep detailed confidential evidence in governed artifacts when it is operationally required.`
- acceptance_evidence:
  - `Negative tests inject absolute paths, tokens, multiline/control-character values, and synthetic document text through native and stdlib loggers and prove the JSONL contains none of them.`
  - `Every file-scoped production event carries a relative path or a documented opaque ID.`
  - `Exception tests prove useful type/phase evidence survives redaction.`

### ISSUE-006 — Tests validate the logging transport, not the operational contract

- severity: `medium`
- confidence: `high`
- first_pass: `4`
- observability_area: `observability-testing-validation`
- issue_type: `observability-test-gap`
- verification: `verified directly from test inventory; all 102 focused tests passed`
- evidence:
  - `tests/test_observability.py:68-126` covers run-ID format, verbosity mapping, JSON parseability, context fields, handler replacement, and stdlib integration.
  - `tests/test_cli_apply.py:331-374` checks run-ID correlation and per-file apply outcomes, but not start/terminal lifecycle, totals, failure, refusal, duration, or artifact-publication ordering.
  - `tests/test_cli_scan.py:64-72` checks only that scan log lines share the run ID. No equivalent log-contract test exists for plan, restore, or verify.
  - No observability test covers unexpected exceptions, KeyboardInterrupt, logging disk/full-write failure, handler closure, restrictive permissions, path minimization, redaction, bounded log size, or terminal-event uniqueness.
  - The focused suite passed `102` tests, showing these are coverage gaps rather than currently failing assertions.
- impact: `The traceability row for NFR-003 reports completion, but regressions can remove terminal evidence, expose sensitive metadata, or break non-apply commands while the named tests remain green.`
- recommendation: `Build a command-by-terminal-state contract matrix. Assert lifecycle events and exit codes for scan/plan/apply/restore/verify across clean, findings, input error, refusal, interruption, and unexpected failure paths. Add privacy, permissions, sink-failure, and size-budget tests; keep lower-level processor tests as the fast unit layer.`
- acceptance_evidence:
  - `The test matrix covers every command and every applicable 0/1/2/3/internal-error terminal state.`
  - `Traceability cites end-to-end tests that inspect the complete JSONL, not only run ID and level presence.`
  - `Fault-injection tests prove logging degradation cannot hide or change the primary command result.`

### ISSUE-007 — Always-DEBUG per-file logging has no measured disk budget or split policy

- severity: `low`
- confidence: `medium`
- first_pass: `2`
- observability_area: `cost-cardinality-sampling`
- issue_type: `cost-cardinality-gap`
- verification: `direct implementation evidence; real-corpus size impact not measured`
- evidence:
  - `src/docmend/observability.py:98-100` fixes the file sink at DEBUG for every run.
  - Discovery emits a classified event per accepted file (`src/docmend/discovery.py:333-341`), and planning/apply add further per-file events.
  - `logging.FileHandler` has no size split, quota, or capacity preflight. The approved research explicitly leaves a per-run part-file safety valve threshold unresolved (`docs/research/structured-logging-library.md:86-93,134-136`).
  - The 100k-file scale test measures heap and elapsed time but does not measure log bytes or logging overhead.
- impact: `There is no vendor/cardinality cost, but a large or repeatedly resumed corpus can consume local disk, make jq/editor use impractical, and contribute to ENOSPC near manifests/reports. The current risk is plausible but unquantified.`
- recommendation: `Benchmark log bytes/event, total bytes/run, and logging overhead on the synthetic scale corpus. Set an owner-approved size budget and, if needed, split one run into ordered part files without deleting old parts or sampling away errors, skips, lifecycle events, or summaries. Document retention as user-controlled.`
- acceptance_evidence:
  - `Scale output reports total log bytes, bytes/file, and logging wall-time overhead.`
  - `A configured/tested safety valve preserves valid JSONL and run correlation across parts.`
  - `Errors, findings, and terminal records are never sampled.`

### ISSUE-008 — Long-running batches have no aggregate progress or heartbeat signal

- severity: `medium`
- confidence: `high`
- first_pass: `1`
- observability_area: `data-pipeline-batch-visibility`
- issue_type: `data-pipeline-visibility-gap`
- verification: `verified directly from event inventory, console thresholds, and scale evidence`
- evidence:
  - `src/docmend/observability.py:48-60` sets the default console threshold to WARNING, so INFO start/completion events are hidden during a normal run.
  - The file log has per-file DEBUG events, but no time-based heartbeat or aggregate progress event with processed files/bytes, rate, current stage, or time since last completion.
  - The checked-in scale evidence records roughly 358 seconds for 100k files (`docs/specs/docmend.md:64` and `tests/test_scale.py`), long enough for a silent default console to be operationally ambiguous.
  - Per-file watchdogs cover classification/transform only; a stalled directory walk, artifact write, backup, or writer operation has no heartbeat to distinguish slow progress from a hang.
- impact: `An operator or wrapper cannot cheaply tell whether a large run is healthy without tailing and interpreting high-volume per-file DEBUG JSONL. This weakens mid-batch diagnosis and makes filesystem stalls look like ordinary slowness.`
- recommendation: `Emit low-cardinality time-based progress events at stage boundaries and a bounded cadence, with processed/total when known, bytes, elapsed_ms, rate, skips/failures, and last-progress age. Keep per-file events in JSONL; show concise progress on an interactive console without flooding non-TTY automation.`
- acceptance_evidence:
  - `A synthetic slow run emits progress within the documented maximum silence interval.`
  - `Progress counts reconcile with the terminal artifact totals.`
  - `Non-TTY output remains stable and bounded; TTY behavior does not corrupt stderr logs or stdout machine output.`

### ISSUE-009 — Observability has no durable repo convention or troubleshooting runbook

- severity: `low`
- confidence: `high`
- first_pass: `3`
- observability_area: `runbooks-and-operability`
- issue_type: `missing-conventions`
- verification: `verified directly from conventions, README, and runbooks`
- evidence:
  - `docs/handoff/conventions.md` defines tooling, sensitive-data, spec, ADR, and frontmatter patterns but no logging/event/privacy/lifecycle convention.
  - `README.md:9,33-35` names the log location and verbosity flags but does not explain terminal-state detection, safe sharing, jq queries, or incomplete logs.
  - The restore/resume runbooks use logs only as a place to find the run ID; neither documents how to diagnose a failed/incomplete run or a broken telemetry sink.
  - Detailed decisions exist in the spec, ADR-0013, and research report, but they are not distilled into the repo's stable pattern library.
- impact: `Future changes can preserve structlog mechanically while drifting event names, privacy rules, terminal ordering, permissions, or tests. Operators lack a supported diagnostic procedure when the batch evidence is incomplete.`
- recommendation: `After the owner accepts the contract, add a compact observability convention and a troubleshooting section/runbook. Separate cross-project rules (stable lifecycle events, safe fields, private permissions, failure tests) from docmend-specific choices (per-run JSONL, DEBUG file floor, user-controlled retention, no service metrics/tracing, report/manifest authority).`
- acceptance_evidence:
  - `docs/handoff/conventions.md points to the authoritative event contract and its validation command.`
  - `A runbook explains how to identify clean/findings/refused/interrupted/failed runs and safely share sanitized evidence.`
  - `The convention states which facts belong in logs versus authoritative artifacts.`

## High-Risk Blind Spots

- `Unexpected internal failure`: verified blind; the log can end after a start event with no cause or terminal state (ISSUE-002).
- `Verify result durability`: verified blind; findings and final counts are console-only (ISSUE-001).
- `Restore terminal outcome`: verified blind; per-record events exist, but the aggregate result and exit meaning are console-only (ISSUE-001).
- `Local confidentiality`: verified under umask 022; metadata logs are 0644 inside a 0755 directory (ISSUE-003).
- `Telemetry sink failure`: unverified; no ENOSPC/write-error test or documented behavior exists (ISSUE-006, ISSUE-007).
- `External automation`: could not verify whether an operator wrapper retains stdout/stderr, monitors exit codes, or detects missing terminal records.

## Signal Schema And Resource Identity

- verified strengths:
  - `ts`, uppercase `level`, `run_id`, `command`, and `event` appear on structlog-native records.
  - `contextvars.merge_contextvars` and global binding provide reliable per-invocation correlation in the implemented sequential runtime.
  - Stdlib/third-party records enter the same JSONL and receive run/command context.
  - JSON rendering and `dict_tracebacks` are correctly placed on the file sink; console/file rendering is separated.
- gaps:
  - Event values are prose, not a closed semantic vocabulary.
  - No `docmend_version`, `log_schema_version`, terminal `outcome`, or consistent `stage` identity exists.
  - Numeric units are ambiguous (`elapsed`, `size`) and workflow lineage is indirect.
  - Foreign records are not distinguished by a stable event type/logger field.
- primary finding: `ISSUE-004`

## Signal Quality And Noise Risks

- Per-file DEBUG records provide useful forensic detail and are intentionally retained even under `--quiet`.
- The same design produces high-volume records without an aggregate progress layer or measured size budget.
- Free-form messages and details make grouping unstable; reason codes are strongest in apply/plan paths but not universal.
- Default console WARNING suppresses ordinary start/completion context; only warnings/errors and final `typer.echo` summaries remain.
- primary findings: `ISSUE-004, ISSUE-007, ISSUE-008`

## Alerting And Incident Response Gaps

- Service paging is `not needed for this repo`; non-zero process exit is the correct alert primitive for a manual/local CLI.
- Exit ownership is clear: the invoking operator/owner.
- The alert payload is not consistently durable: plan/apply/restore/verify terminal detail is split among console, artifacts, and incomplete logs.
- Unexpected exceptions and interruptions have no stable structured classification.
- Restore/resume runbooks are strong on recovery mechanics but weak on diagnosing telemetry state.
- primary findings: `ISSUE-001, ISSUE-002, ISSUE-009`

## SLO And Reliability Gaps

- Formal service SLOs/error budgets are `not needed for this repo`.
- Existing reliability targets include zero original-content loss, one-pass restore RTO, correctness, and practical full-library completion.
- Batch SLIs that would substantiate those targets—terminal outcome, total/per-stage duration, processed bytes/files, last progress, resume count, and failure classes—are incomplete in JSONL.
- Numeric performance targets were deliberately deferred by OQ-010; the review does not invent one.
- primary findings: `ISSUE-001, ISSUE-008`

## Telemetry Coverage Gaps

| command/surface | verified coverage | missing coverage |
| --- | --- | --- |
| `scan` | start, per-file classification/skips, aggregate scan count | terminal outcome/exit, duration, artifact publication, bytes in summary |
| `plan` | start, planned action/skip and timeout detail | terminal summary, no-op count, duration, artifact publication, exit outcome |
| `apply` | per-action outcome, gate refusal, partial-restore warning, report artifact | structured start, terminal summary/exit, duration, report/manifest publication result, unexpected failure |
| `restore` | per-record outcome and manifest events | structured start, aggregate terminal result, duration, durable report, unexpected failure |
| `verify` | start plus reused scan events | verify findings, reconciliation outcomes, terminal count/exit, duration, durable report |
| CI/release | GitHub job logs and check status | external retention/settings and alert routing not verifiable from repo |

## Telemetry Pipeline And Collector Risks

- No collector/exporter/gateway exists; this is appropriate for local/offline processing and avoids remote data exposure.
- `FileHandler` is single-process only. That is adequate for the implemented sequential runtime; the approved process-pool design must introduce QueueHandler/QueueListener before parallel logging is enabled.
- Sink errors, capacity exhaustion, close/flush ordering, and part-file behavior are not tested.
- Existing JSONL line flushing is provided by StreamHandler behavior, but crash/power-loss durability is not equivalent to the fsync-per-record manifest contract and should not be claimed as such.
- primary findings: `ISSUE-002, ISSUE-007`

## Deploy And Operational Visibility

- docmend has no resident deployment, health endpoint, migration service, or production cluster; those surfaces are `not needed for this repo`.
- GitHub Actions provides external check/release visibility. Repository-side workflow definitions were inspected; settings, log retention, notifications, and prior run artifacts were not externally verified.
- The current HEAD introduces no runtime change from v1.0.2, so the findings are release-baseline posture rather than a post-release observability regression.
- The owner-staged real-library rollout is the main production-like environment; no private rollout logs or corpus were inspected.

## Telemetry Data Hygiene And Redaction

- No current production log call was found emitting document body bytes/text.
- The stronger claim that paths are relative and sensitive values are redacted is not mechanically true: absolute/caller-supplied paths, symlink targets, raw exceptions, and foreign messages reach the JSONL.
- Default file/directory modes are not private under a common umask.
- Logs remain local with no exporter, which materially reduces but does not eliminate disclosure risk.
- primary findings: `ISSUE-003, ISSUE-005`

## Cost And Cardinality Risks

- Vendor cost, metric-label cardinality, and trace sampling are `not needed for this repo` because no remote backend exists.
- The relevant cost is local disk and parsing overhead from per-file DEBUG JSONL.
- No evidence establishes current real-corpus log size, so severity remains low and the review recommends measurement before choosing a split threshold.
- primary finding: `ISSUE-007`

## Observability Testing Gaps

- Focused existing suite result: `102 passed`.
- Existing tests strongly protect logger configuration and apply happy-path correlation.
- Missing contract tests cover command terminal states, exceptions/interruption, permissions, redaction, sink errors, part files/size, progress cadence, and cross-command schema stability.
- NFR-003 traceability should not remain `Complete` based only on field presence and apply outcomes once the binding job-record language is considered.
- primary finding: `ISSUE-006`

## Convention Recommendations

### Shared across projects

- Require one start event and exactly one terminal event for every observable command/job.
- Use a closed, versioned event vocabulary with unit-suffixed numeric fields and explicit resource/software identity.
- Enforce sink-side field allowlisting/redaction; do not rely only on caller discipline.
- Create confidential telemetry with private permissions and reject unsafe non-regular destinations.
- Test unexpected failure, interruption, sink degradation, privacy, and terminal ordering.

### Repo-specific conventions

- Keep one local JSONL stream per docmend run with `run_id` shared by artifacts; retain the DEBUG file floor independently of console verbosity.
- Keep manifest/report artifacts authoritative for mutation audit; use logs for lifecycle and diagnosis, not as a substitute ledger.
- Keep telemetry local/offline by default; metrics exporters, distributed tracing, dashboards, and paging remain unnecessary unless a future service/network boundary is approved.
- Preserve user-controlled retention. If scale measurement justifies splitting, use ordered part files for the same run and do not auto-delete evidence.
- Emit aggregate time-based progress suitable for a 100k+ file batch without putting per-file INFO noise on the default console.
- Add these rules to `docs/handoff/conventions.md` only after owner acceptance and spec/ADR change control where behavior changes.

## Pass Log

| pass | lens | new issues | result |
| --- | --- | --- | --- |
| 1 | telemetry inventory, command/job visibility, schema/resource identity, high-risk blind spots | ISSUE-001, ISSUE-004, ISSUE-008 | Found incomplete lifecycle coverage, unstable schema, and no aggregate progress. |
| 2 | signal quality, correlation, noise/cost, data minimization, convention alignment | ISSUE-005, ISSUE-007 | Found unenforced relative/redaction boundary and unmeasured DEBUG log growth. |
| 3 | incident response, runbooks, exit alerts, deploy/CI visibility, pipeline resilience | ISSUE-002, ISSUE-009 | Found missing unexpected-failure records and no durable observability convention/runbook. |
| 4 | privacy/permissions, lower-severity gaps, client/SLO applicability, validation coverage | ISSUE-003, ISSUE-006 | Confirmed permissive modes and tests that do not cover the operational contract. |
| 5 | adaptive deepening: all logger call sites, failure probe, permission probe, command test suite | none | Strengthened evidence; no new issue category. |
| 6 | adaptive convergence: release baseline, spec/ADR/research reconciliation, external-surface unknowns | none | Second consecutive pass with no new issues; review converged. |

## Claude Handoff

- highest_priority:
  1. `ISSUE-001`: define and implement the command lifecycle/terminal job-record contract, including verify and restore.
  2. `ISSUE-002`: add the safe unexpected-failure/interruption boundary and fault-injection coverage.
  3. `ISSUE-003` and `ISSUE-005`: make log storage private and enforce sanitization before the staged real-library rollout produces shareable evidence.
- likely_files_if_fixes_are_authorized: `src/docmend/observability.py`, `src/docmend/cli.py`, production log call sites, `tests/test_observability.py`, CLI tests, `docs/specs/docmend.md`, `docs/handoff/conventions.md`, README/runbooks`
- change_control_note: `The approved spec and ADR-0013 govern post-v1 logging behavior. Event schema, terminal artifact, retention, or CLI-output changes should be reconciled through the spec/ADR process rather than patched only in code.`
- suggested_follow_on_reviews: `security review for log/artifact permissions and path handling; incident-readiness review for terminal-state/runbook integration; performance review for measured log overhead and split threshold`
- preserve_strengths: `structlog+stdlib integration, contextvars run correlation, JSONL/console renderer split, quiet-independent file sink, local-only telemetry, append-safe authoritative manifest/report separation`
- fixes_applied: `none; review/report only`

## Open Questions Or Assumptions

- Are supported operator hosts guaranteed single-user, or must logs be confidential from other local accounts?
- Are `.docmend` logs routinely attached to issues or shared with agents/support? If so, what sanitization workflow is acceptable?
- Should verify and restore gain durable report artifacts, or is complete terminal/finding coverage in JSONL the preferred contract?
- What maximum silence interval should define a healthy progress heartbeat for local and network/removable filesystems?
- What measured bytes/run threshold should trigger part-file splitting, and should the threshold be configurable?
- Does any external wrapper/scheduler retain stdout/stderr, record exit codes, and alert on missing terminal records?
- Should scan→plan→apply→restore→verify share a separate workflow/campaign ID in addition to per-command run IDs?

## Residual Risk

- Repository evidence cannot verify GitHub settings, workflow-log retention, operator shell/scheduler capture, host ACLs, external backups, or real-library rollout monitoring.
- No private corpus or real run log was inspected; privacy conclusions use synthetic paths and direct call-site analysis.
- The review did not inject ENOSPC or power loss into a real destructive run. Telemetry-sink resilience remains an evidence gap until fault tests exist.
- Metrics, tracing, dashboards, paging, client telemetry, remote collectors, and worker telemetry remain not needed for the implemented local sequential CLI; reassess if a process pool, scheduler, service, or remote integration becomes live.
- The current tests pass and the logging foundation is technically sound, but high residual diagnosability risk remains until terminal lifecycle and unexpected-failure records are complete across all commands.
