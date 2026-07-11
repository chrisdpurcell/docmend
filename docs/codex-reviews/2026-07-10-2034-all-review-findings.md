# Complete Review Sweep Findings

This report is the single index of every finding produced by the 2026-07-10-2034 exhaustive review sweep. It preserves all lens-local findings and the deduplicated synthesis outcomes.

## Scope And Counting

- Sweep result: 18 completed reviews, 0 failed, and 0 skipped.
- Raw catalog: 189 findings across 18 child-review reports.
- Consolidated synthesis: 9 confirmed rollout blockers.
- Raw ISSUE identifiers are local to each review lens. Repeated root causes remain listed because each entry records a distinct review perspective.
- Severity and confidence values reproduce the source reports. This document does not silently reclassify findings.
- Full evidence, impact, recommendations, pass logs, and residual-risk notes remain in the linked source reports.

## Consolidated Rollout Blockers

These are the deduplicated high-priority findings from the [comprehensive synthesis](2026-07-10-2034-comprehensive-review-synthesis.md).

| ID | Severity | Finding |
| --- | --- | --- |
| DMR-01 | High | One plan can overwrite its own recovery backup |
| DMR-02 | High | Artifact destinations can overwrite corpus inputs |
| DMR-03 | High | Manifest consumers trust paths and invalid ledger states |
| DMR-04 | High | Apply and restore have unjournaled commit windows |
| DMR-05 | High | Verify has multiple false-clean outcomes |
| DMR-06 | High | Path identity is not held through mutation |
| DMR-07 | High | A target created after the gate can be overwritten without preservation |
| DMR-08 | High contract failure | The scale contract and acceptance gate are not validly closed |
| DMR-09 | High future-release risk | Future releases are not bound to the documented release candidate |

## Consolidated Medium Themes

- Stable document identity is not implemented. Planning always mints a new UUID, despite ADR-0008's three-tier recovery contract.
- Artifact readers do not reject duplicate JSON keys, enforce aggregate totals, consistently reject unsupported future versions, or fully align schemas with Pydantic models.
- Public write-capable engine functions can bypass CLI lock and preservation coordination. Fixed writer staging names can block retry after a hard kill.
- Disk preflight checks backup space and source temporary space independently, even when both consume the same filesystem.
- Scan and plan treat timeouts as successful; targeted restore succeeds when no requested ID matches; resume chains lack durable lineage.
- Logs lack a stable terminal event contract, default to metadata-readable permissions under a typical `022` umask, and do not enforce path minimization or redaction at the sink.
- Recovery, privacy, prerequisites, and release documentation overstate some guarantees or omit executable operator procedures.

## Corrected Or Non-Applicable Raw Findings

- GitHub's live dependency graph does ingest the lock: its SBOM reported 82 packages and 122 relationships, including the key runtime dependencies.
- `uv build` builds the wheel from the generated sdist. The remaining release test gap is the shallow installed-product smoke, not absence of an sdist build.
- GitHub's current default workflow permission is read-only, with pull-request approval disabled. Explicit workflow permissions remain useful hardening.
- The current `dev` head is not a declared release candidate, so its distance from v1.0.2 is not a release defect.
- Scanner matches for FastAPI, SQLAlchemy, Svelte, webhooks, containers, databases, background workers, and runtime AI came from prose and research. These product surfaces do not exist in docmend v1.

## Complete Raw Finding Catalog

The catalog below lists every ISSUE record from every completed child review. Consult the linked report for the full evidence and recommendation.

### AI And Prompt Workflow Review

Source: [2026-07-10-2034-ai-and-prompt-workflow-review-report.md](2026-07-10-2034-ai-and-prompt-workflow-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Consistency prompt can reverse owner decisions without an approval boundary |
| ISSUE-002 | medium | medium | Web research is not isolated from write-capable canonical-document work |
| ISSUE-003 | low | medium | Static prompts have a stale and undeclared execution contract |
| ISSUE-004 | low | medium | Prompt and generated-research provenance is insufficient for replay |
| ISSUE-005 | low | high | Absolute-success wording has no incomplete or uncertainty outcome |
| ISSUE-006 | low | high | Agent fan-out has no cost, latency, or convergence bound |
| ISSUE-007 | low | medium | Future semantic-enrichment ownership conflicts across binding documents |
| ISSUE-008 | low | high | Frontmatter convention overstates automated emission |

### API Contract Review Report

Source: [2026-07-10-2034-api-contract-review-report.md](2026-07-10-2034-api-contract-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Restore accepts manifest paths without enforcing the recorded root boundary |
| ISSUE-002 | high | high | Manifest validation omits the semantic and run-level invariants recovery relies on |
| ISSUE-003 | medium | high | The authoritative report schema and the internal consumer model disagree |
| ISSUE-004 | medium | high | Aggregate and cross-field invariants are enforced only on selected write paths |
| ISSUE-005 | medium | high | JSON artifacts silently collapse duplicate member names |
| ISSUE-006 | medium | high | Schema versions identify a family but do not select or enforce supported semantics |
| ISSUE-007 | medium | high | The binding spec and shipped CLI disagree on verify/report interfaces |
| ISSUE-008 | low | high | `run_id` and `action_id` ownership is ambiguous across plan, report, and manifest |
| ISSUE-009 | low | high | The UUIDv7 identity contract is not validated |
| ISSUE-010 | low | medium | CLI and TOML compatibility/deprecation policy is not defined at contract granularity |

### Architecture And Boundary Review

Source: [2026-07-10-2034-architecture-boundary-review-report.md](2026-07-10-2034-architecture-boundary-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Destructive engines are callable outside the safety coordinator |
| ISSUE-002 | medium | high | Report finalization is outside gate preflight and lock scope |
| ISSUE-003 | high | high | Restore is outside the writer and cannot converge after a mid-record interruption |
| ISSUE-004 | medium | high | Accepted parallel configuration is silently ignored |
| ISSUE-005 | medium | high | The completed bounded-memory requirement contradicts the in-memory pipeline |
| ISSUE-006 | medium | high | Artifact readers do not consistently reject future schema minors |
| ISSUE-007 | medium | high | Full transformation policy is duplicated across planning and apply |
| ISSUE-008 | low | high | The CLI composition root has become a secondary application layer |
| ISSUE-009 | low | high | Architecture fitness functions protect only transform purity |
| ISSUE-010 | low | high | Architecture records overstate current conformance |

### Background Jobs And Async Workflow Review

Source: [2026-07-10-2034-background-jobs-and-async-workflow-review-report.md](2026-07-10-2034-background-jobs-and-async-workflow-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Restore can replay mutations outside the recorded source root |
| ISSUE-002 | high | high | Single-step apply mutations have a post-mutation journal gap |
| ISSUE-003 | high | high | Restore cannot converge after interruption inside a multi-step inverse |
| ISSUE-004 | high | high | Public write engines can bypass the lock and preservation coordinator |
| ISSUE-005 | medium | high | Accepted parallel configuration is a silent runtime no-op |
| ISSUE-006 | medium | high | The per-file watchdog is not a hard timeout boundary |
| ISSUE-007 | medium | high | Hard-kill temp residue can permanently block retry |
| ISSUE-008 | medium | high | Resume attempts lack durable logical-workflow lineage and one-command compensation |
| ISSUE-009 | medium | high | Terminal report publication is outside the durable run transaction |
| ISSUE-010 | medium | high | Whole-run state grows with file count and has no enforceable capacity envelope |
| ISSUE-011 | medium | high | Destructive manifest consumers lack an explicit compatibility and run-invariant gate |
| ISSUE-012 | low | high | Standalone scan and verify can observe an active mutation run |
| ISSUE-013 | low | high | Durable conventions do not cover the repository's recovery protocol |

### CI/CD Review Report

Source: [2026-07-10-2034-ci-cd-review-report.md](2026-07-10-2034-ci-cd-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Tag releases are not bound to protected `main`, the package version, or the full gate |
| ISSUE-002 | high | high | Most Actions and reusable workflows use mutable tags |
| ISSUE-003 | medium | high | Published distributions are not tested as the complete installable release contract |
| ISSUE-004 | medium | high | Release build tooling is not reproducibly pinned |
| ISSUE-005 | medium | medium | The Python dependency-review license gate depends on unverified `uv.lock` ingestion |
| ISSUE-006 | medium | medium | Reusable workflow callers inherit unverified default token permissions |
| ISSUE-007 | medium | high | Resolved-environment vulnerability auditing has no periodic trigger |
| ISSUE-008 | medium | medium | Release assets lack repository-defined provenance, attestations, or checksums |
| ISSUE-009 | low | high | Superseded pull-request runs are not cancelled |
| ISSUE-010 | low | high | The documented local gate does not cover all repo-verifiable required checks |

### Comprehensive Code Review

Source: [2026-07-10-2034-comprehensive-code-review-report.md](2026-07-10-2034-comprehensive-code-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Mutation and recovery journals do not cover every commit boundary |
| ISSUE-002 | high | high | Restore and verify trust manifest paths outside the recorded source root |
| ISSUE-003 | high | medium | Hash and containment preconditions are not held through mutation |
| ISSUE-004 | high | high | A late overwrite collision bypasses the preservation gate |
| ISSUE-005 | high | high | Verify ignores unreadable and timed-out scan candidates |
| ISSUE-006 | high | high | Apply/report/verify accounting can hide unattempted plan actions |
| ISSUE-007 | high | high | Verify does not validate recorded recovery backups |
| ISSUE-008 | high | high | Whole-run structures violate the binding bounded-memory contract |
| ISSUE-009 | medium | high | Terminal report publication is outside preflight, lock scope, and full durability |
| ISSUE-010 | medium | high | Manifest readers validate records but not ledger semantics or compatibility |
| ISSUE-011 | medium | high | JSON artifact readers accept ambiguous members and false aggregates |
| ISSUE-012 | medium | high | Accepted configuration values are operationally inert |
| ISSUE-013 | medium | medium | The default maximum file size permits an excessive transient working set |
| ISSUE-014 | medium | high | Confidential logs are permissive and violate their own path-minimization claim |
| ISSUE-015 | medium | high | Verify has no complete machine-readable terminal artifact |
| ISSUE-016 | medium | high | Standalone verify does not coordinate with active mutation runs |
| ISSUE-017 | medium | high | Targeted restore silently succeeds when requested IDs do not match |
| ISSUE-018 | low | high | A hard-kill temp residue can permanently block retries |
| ISSUE-019 | medium | high | Destructive engines can be called without the safety coordinator |

### Conventions Review Report

Source: [2026-07-10-2034-conventions-review-report.md](2026-07-10-2034-conventions-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | medium | high | Product-frontmatter convention states behavior v1 does not implement |
| ISSUE-002 | medium | high | Standard-ownership convention was not updated for Agent Handoff v1 |
| ISSUE-003 | medium | high | Durable artifact schema evolution is not indexed as a contributor convention |
| ISSUE-004 | medium | medium | Sensitive-data convention does not cover runtime diagnostics and artifacts |
| ISSUE-005 | low | high | Spec workflow's canonical scaffold uses the wrong profile for this repo |
| ISSUE-006 | medium | high | Markdown formatter commands resolve unpinned tools |
| ISSUE-007 | low | high | Local Python verification example does not explicitly prove lock freshness |
| ISSUE-008 | low | high | Body order and missing canonical examples violate the child workflow's house schema |
| ISSUE-009 | low | high | Branch, integration, and release workflow is durable but absent from the LLM conventions index |

### Data Schema And Migration Review Report

Source: [2026-07-10-2034-data-schema-migration-review-report.md](2026-07-10-2034-data-schema-migration-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Single-step mutations can become durable before their recovery record exists |
| ISSUE-002 | high | high | Restore does not enforce the manifest's recorded source-root boundary |
| ISSUE-003 | high | high | Manifest records and record sets omit recovery-critical semantic invariants |
| ISSUE-004 | medium | high | The report schema accepts values the internal consumer rejects |
| ISSUE-005 | medium | high | Version fields do not consistently dispatch supported schema semantics |
| ISSUE-006 | medium | high | Aggregate invariants are not enforced when artifacts are consumed |
| ISSUE-007 | medium | high | JSON readers silently collapse duplicate member names |
| ISSUE-008 | medium | medium | Single-document artifact writes are not fully durable or collision-safe |
| ISSUE-009 | low | high | The primary conventions do not index artifact schema evolution |

### Dependency And Supply-Chain Review

Source: [2026-07-10-2034-dependency-supply-chain-review-report.md](2026-07-10-2034-dependency-supply-chain-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | medium | The release tag boundary does not enforce the documented release provenance |
| ISSUE-002 | high | high | The artifact-producing release toolchain is resolved dynamically |
| ISSUE-003 | high | medium | The required dependency-review gate has no proven `uv.lock` inventory path |
| ISSUE-004 | medium | high | Multiple executable Actions and reusable workflows use mutable tags |
| ISSUE-005 | medium | medium | Release artifacts have no repository-defined SBOM or verifiable provenance |
| ISSUE-006 | medium | high | The release validates only a wheel version smoke path, not the complete distribution chain |
| ISSUE-007 | medium | medium | Advisory detection is event-driven and can go stale in a quiet repository |
| ISSUE-008 | medium | high | Repository conventions execute unpinned ambient Node and Git tooling |
| ISSUE-009 | medium | high | License enforcement permits unknown licenses and lacks a complete lock-derived record |

### Documentation And Runbook Review

Source: [2026-07-10-2034-documentation-and-runbook-review-report.md](2026-07-10-2034-documentation-and-runbook-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Recovery documentation promises complete journals and universal reversibility that the documented failure model does not provide |
| ISSUE-002 | high | high | The approved specification advertises CLI and configuration behavior that is not implemented |
| ISSUE-003 | high | high | The restore runbook's verification step does not prove that the corpus returned to its pre-apply state |
| ISSUE-004 | high | high | Confidential artifact and log handling is documented only as a buried classification, not an operator procedure |
| ISSUE-005 | medium | high | User onboarding omits the actual Linux/POSIX, Python 3.14, and uv prerequisites |
| ISSUE-006 | medium | high | Recovery runbooks lack the minimum fields needed for safe triage under pressure |
| ISSUE-007 | medium | high | The release procedure starts at tagging and omits preparation, contract checks, and failure recovery |
| ISSUE-008 | medium | high | The spec claims every command emits an authoritative machine-readable job record, but plan and verify do not satisfy that description |
| ISSUE-009 | medium | medium | The compliance section makes an unverified “none apply” legal conclusion |
| ISSUE-010 | medium | high | Docs-as-code validates style and spec shape but not links or executable documentation |
| ISSUE-011 | low | high | The handoff architecture's standing backlog is stale after v1.0.2 |
| ISSUE-012 | low | high | The large documentation corpus has no audience-oriented landing page |
| ISSUE-013 | low | high | `docmend plan --help` omits a real exit code and the README blurs global versus command-local write flags |
| ISSUE-014 | low | high | The specification revision history is not ordered by revision |

### Frontend State And Interaction Review

Source: [2026-07-10-2034-frontend-state-and-interaction-review-report.md](2026-07-10-2034-frontend-state-and-interaction-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | A manifest containing only a dangling intent can represent a target already published while the original source still exists, or a fully completed mutation whose terminal record was never appended. Both `verify` and `restore` return exit `0`; restore reports zero work, and verify can report zero findings. |
| ISSUE-002 | high | high | Verification can skip an unreadable or timed-out output, omit it from both the checked count and finding count, and exit `0`. |
| ISSUE-003 | high | high | A write apply can mutate the corpus and durably append its manifest, then fail to persist a custom report. The process exits through an unhandled exception after the lock is released and before it tells the user where the manifest is. |
| ISSUE-004 | medium | high | A typo or stale `docmend.id` produces a successful no-op rather than preserving the user's stated restore intent as an error/finding. |
| ISSUE-005 | low | high | Successful `-q` commands still emit artifact paths and summaries. |

### Incident Readiness Review

Source: [2026-07-10-2034-incident-readiness-review-report.md](2026-07-10-2034-incident-readiness-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Mutation journals are not write-ahead for every apply and restore operation |
| ISSUE-002 | high | high | Restore and verify do not enforce manifest-to-root containment |
| ISSUE-003 | high | medium | Hash and containment preconditions are not held through commit |
| ISSUE-004 | high | high | Verify can certify a run after its recovery bytes disappear |
| ISSUE-005 | high | high | The restore runbook cannot prove the corpus returned to its pre-apply state |
| ISSUE-006 | medium | high | Apply does not durably represent every plan action or terminal run state |
| ISSUE-007 | high | high | Verify can exit clean after checking zero usable files |
| ISSUE-008 | medium | high | Restore and verify lack complete machine-readable response artifacts |
| ISSUE-009 | medium | high | External preservation declarations are not bound to a recovery point |
| ISSUE-010 | medium | high | Targeted restore silently succeeds when requested IDs do not match |
| ISSUE-011 | medium | high | Destructive manifest consumers accept unsupported future minor versions |
| ISSUE-012 | medium | high | Release controls do not prevent or operationalize a bad-release incident |
| ISSUE-013 | medium | high | Incident runbooks and conventions cover only two recovery cases |
| ISSUE-014 | low | high | Public incident intake, severity, and communication ownership are undefined |
| ISSUE-015 | low | medium | Exercise coverage has no recurring incident-drill cadence or recorded field evidence |

### Integration And Third-Party Boundary Review

Source: [2026-07-10-2034-integration-and-third-party-boundary-review-report.md](2026-07-10-2034-integration-and-third-party-boundary-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Restore can mutate paths outside the manifest's recorded source root |
| ISSUE-002 | high | high | Pure rewrite/rename and restore mutations can complete before durable manifest evidence exists |
| ISSUE-003 | high | high | Duplicate JSON members are silently collapsed before durable-artifact validation |
| ISSUE-004 | high | high | Verify can report clean without checking whether recovery backups still exist or match their recorded hashes |
| ISSUE-005 | high | high | Release publication executes mutable Action tags with a write-capable token |
| ISSUE-008 | high | high | Manifest readers validate records individually but not the ledger's run, root, version, identity, or sequence invariants |
| ISSUE-006 | medium | high | The binding verify contract advertises plan input and reconciliation that the CLI does not implement |
| ISSUE-007 | medium | high | Artifact-version policy is not enforced consistently and lacks genuine historical compatibility fixtures |
| ISSUE-009 | medium | high | Released wheels permit untested future dependency majors at behavior-critical boundaries |
| ISSUE-010 | medium | high | Package metadata does not disclose the runtime's POSIX-only boundary |
| ISSUE-011 | medium | high | GitHub release creation is not a pinned, identity-checked, retry-safe transaction |
| ISSUE-012 | medium | medium | The dependency-review license gate assumes uv.lock ingestion that is not proven in the repo |
| ISSUE-013 | low | high | Some documented provider/test controls are installed or claimed but not active |

### Observability Review

Source: [2026-07-10-2034-observability-review-report.md](2026-07-10-2034-observability-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Command logs are not durable batch job records |
| ISSUE-002 | high | high | Unexpected failures leave no structured cause or terminal state |
| ISSUE-003 | medium | high | Confidential run logs default to world-readable metadata permissions |
| ISSUE-004 | medium | high | The event vocabulary and resource identity are not stable enough for reliable queries |
| ISSUE-005 | medium | high | Relative-path and redaction claims are not enforced at the sink |
| ISSUE-006 | medium | high | Tests validate the logging transport, not the operational contract |
| ISSUE-007 | low | medium | Always-DEBUG per-file logging has no measured disk budget or split policy |
| ISSUE-008 | medium | high | Long-running batches have no aggregate progress or heartbeat signal |
| ISSUE-009 | low | high | Observability has no durable repo convention or troubleshooting runbook |

### Performance Review

Source: [2026-07-10-2034-performance-review-report.md](2026-07-10-2034-performance-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | The completed bounded-memory claim is contradicted by O(file-count) state |
| ISSUE-002 | high | high | A permitted large file amplifies to roughly ten times its size in traced heap |
| ISSUE-003 | medium | high | Accepted parallel settings are silent runtime no-ops |
| ISSUE-004 | medium | high | The scale baseline is manually gated and omits material production costs |
| ISSUE-005 | medium | high | Verify rereads outputs and fully splits Markdown bodies after scan already hashed them |
| ISSUE-006 | medium | high | Field runs expose no stage rates, tails, peak memory, or heartbeat |
| ISSUE-007 | medium | medium | The accepted SIGALRM deviation is not a hard per-file load-shedding boundary |
| ISSUE-008 | low | high | The conventions library has no performance-engineering entry |

### Product And Business Logic Review

Source: [2026-07-10-2034-product-and-business-logic-review-report.md](2026-07-10-2034-product-and-business-logic-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | medium | Hash and containment preconditions are not held through mutation |
| ISSUE-002 | high | high | Restore and verify do not enforce manifest-to-source-root binding |
| ISSUE-003 | high | high | Verify does not verify backup references or recoverable before-state |
| ISSUE-004 | high | high | Apply/report/verify accounting is plan-unaware and can hide unattempted actions |
| ISSUE-005 | high | high | Verify ignores scan-time skips and can exit clean after checking zero files |
| ISSUE-006 | medium | high | Verify results are not preserved as a complete machine-readable business event |
| ISSUE-007 | medium | high | Advertised parallel and write settings are accepted but operationally inert |
| ISSUE-008 | medium | high | Targeted restore silently succeeds when requested IDs do not match |
| ISSUE-009 | low | high | Reversibility rationale remains internally contradictory |

### Release Readiness Review

Source: [2026-07-10-2034-release-readiness-review-report.md](2026-07-10-2034-release-readiness-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Current HEAD is not a coherent new release candidate |
| ISSUE-002 | high | medium | Any matching tag can publish without proving it is the signed mainline candidate |
| ISSUE-003 | high | high | The privileged release build is not immutable or least-privileged |
| ISSUE-004 | medium | high | The release gate barely tests the artifact users install |
| ISSUE-005 | medium | high | Published assets have no repository-defined provenance, SBOM, or digest bundle |
| ISSUE-006 | medium | high | Bad-release rollback and post-release verification are underspecified |
| ISSUE-007 | low | high | Duplicate/no-change releases and changelog drift are not rejected |

### Test Suite Review

Source: [2026-07-10-2034-test-suite-review-report.md](2026-07-10-2034-test-suite-review-report.md)

| ID | Severity | Confidence | Finding |
| --- | --- | --- | --- |
| ISSUE-001 | high | high | Containment tests stop before the destructive restore and verify consumers |
| ISSUE-002 | high | high | Verification tests omit scan skips, allowing a clean result after checking nothing |
| ISSUE-003 | high | high | End-to-end accounting never proves that every planned action reached a terminal outcome |
| ISSUE-004 | high | high | The opt-in scale test is stale and fails when enabled |
| ISSUE-005 | high | high | The scale assertion encodes the opposite of the binding memory requirement |
| ISSUE-006 | high | medium | Destructive precondition tests do not cover object replacement between validation and mutation |
| ISSUE-007 | medium | high | The traceability gate proves token presence, not executable requirement coverage |
| ISSUE-008 | medium | high | Packaging smoke tests do not exercise the installed product contract |
| ISSUE-009 | medium | high | Artifact compatibility tests do not preserve released producers or reject unsupported futures |
| ISSUE-010 | medium | high | Property-based testing stops at pure transforms instead of the recovery state machine |
| ISSUE-011 | medium | high | Observability tests do not require a durable verify verdict |
| ISSUE-012 | low | medium | No targeted mutation baseline checks assertion strength in the safety core |

## Source Artifacts

- [Comprehensive synthesis](2026-07-10-2034-comprehensive-review-synthesis.md)
- [Sweep summary](2026-07-10-2034-codex-review-sweep.md)
- [Sweep manifest](2026-07-10-2034-codex-review-sweep.json)
- [Shared research](2026-07-10-2034-codex-review-shared-research.md)
