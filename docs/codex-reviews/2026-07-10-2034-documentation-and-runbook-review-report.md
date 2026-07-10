# Documentation And Runbook Review

## Findings

### ISSUE-001: Recovery documentation promises complete journals and universal reversibility that the documented failure model does not provide

- first_pass: 2
- severity: high
- confidence: high
- documentation_area: incident-and-rollback-guidance
- issue_type: incident-rollback-doc-gap
- evidence_status: verified directly from repository documentation and implementation order
- evidence:
  - `README.md:21` correctly says content rewrites are restorable by docmend only when tool backups exist, but `README.md:75-77` later says every mutation is in the manifest and that restore returns files to original bytes without repeating that condition.
  - `docs/runbooks/restore-from-manifest.md:3` says every mutation is recorded, while `docs/runbooks/resume-after-interruption.md:54` explicitly recognizes a mutation-completed/lost-trailing-record case.
  - `docs/runbooks/resume-after-interruption.md:8` calls the manifest complete up to the kill, then `:54` says a completed mutation can lack its record.
  - `docs/specs/docmend.md:706`, `:939`, and `:955` promise that crashes cannot orphan completed mutations, every applied change is restorable, and RPO is zero after any operation. The same spec permits an explicit no-backup run and limits write-ahead `intent` records to `rename_and_rewrite`.
  - `src/docmend/writer/apply.py` performs ordinary rename/rewrite mutations before appending their final manifest record; only `rename_and_rewrite` gets `_record_intent` before mutation.
- impact: An operator can treat the manifest as complete recovery evidence, delete or neglect the real preservation copy, and discover after a kill or no-backup run that a rewrite or pure rename has no mechanically replayable record. The CLI warning reduces the no-backup surprise but does not cure the cross-document promise.
- recommendation: Define recovery guarantees by operation and preservation mode. State that atomicity protects file visibility, not journal completeness or universal rollback; describe the ordinary rename/rewrite post-mutation/pre-record kill window; require preserving tool backups or the declared external recovery point until a verified post-run checkpoint; and either extend write-ahead evidence to every mutation or remove the stronger zero-RPO/complete-manifest claims.

### ISSUE-002: The approved specification advertises CLI and configuration behavior that is not implemented

- first_pass: 2
- severity: high
- confidence: high
- documentation_area: docs-to-code-alignment
- issue_type: docs-code-alignment-gap
- evidence_status: verified directly against current CLI help and source references
- evidence:
  - `docs/specs/docmend.md:910-915` says `parallel.enabled = true` activates a `ProcessPoolExecutor` and describes live worker/chunksize behavior. `src/docmend/config.py:139-163` only parses those values; repository-wide source search found no runtime consumer of `config.parallel`, and `README.md:62` more accurately says v1 is sequential.
  - `docs/specs/docmend.md:371` lists `docmend verify ... --plan FILE`; current `docmend verify --help` has no `--plan` option.
  - `docs/specs/docmend.md:377` says flags such as `--rename-txt-to-md`, `--detect-encoding`, `--normalize-newlines`, `--trim-trailing-whitespace`, `--ensure-final-newline`, and `--collapse-blank-lines` mirror the configuration surface. Current command help exposes none of those flags.
  - `write.atomic` and `write.dry_run_default` are accepted configuration fields (`docs/specs/docmend.md:907-909`, `src/docmend/config.py:121-136`) but source search found no behavior switch for either; writes remain atomic and dry-run remains the default.
- impact: The approved, change-controlled contract tells operators and integrators that knobs and flags work when they are absent or inert. `parallel.enabled = true` is especially misleading for capacity planning because a large run remains sequential without an error.
- recommendation: Decide contract-first whether each surface is required now. Implement and test the documented behavior or mark the fields reserved/rejected and remove nonexistent flags from the approved spec. Add a generated or tested CLI/config compatibility inventory so approval cannot coexist with inert settings.

### ISSUE-003: The restore runbook's verification step does not prove that the corpus returned to its pre-apply state

- first_pass: 3
- severity: high
- confidence: high
- documentation_area: incident-and-rollback-guidance
- issue_type: incident-rollback-doc-gap
- evidence_status: verified directly from the runbook and CLI surface
- evidence:
  - `docs/runbooks/restore-from-manifest.md:60-66` runs only `docmend scan <tree>` and says the result “should match” the original inventory, but gives no comparison command or invariant.
  - A newly generated inventory contains new run metadata and is not directly established as a byte-for-byte pre-state comparator.
  - The only concrete hash instruction is a spot-check for partial restore; the procedure has no complete-corpus hash or saved recovery-point verification step.
- impact: Exit 0 from restore plus a clean scan can still leave wrong-but-valid UTF-8/LF bytes, missing files, extra files, or an incomplete multi-attempt rollback. The operator lacks evidence that recovery actually met the stated RPO.
- recommendation: Add an executable full-restore verification procedure: preserve a pre-apply inventory/hash set, enumerate the exact manifests in restore order, compare every expected path and `before_sha256`, detect missing and unexpected paths, save the verification result, and stop before deleting backups. Keep the current scan as a content-health check, not as proof of restoration.

### ISSUE-004: Confidential artifact and log handling is documented only as a buried classification, not an operator procedure

- first_pass: 3
- severity: high
- confidence: high
- documentation_area: runbooks-and-operations
- issue_type: runbook-gap
- evidence_status: verified directly; regulatory consequences remain external unknowns
- evidence:
  - `README.md:9` tells users that inventories, plans, reports, manifests, and logs are written to `./.docmend/` but does not warn that they contain sensitive paths, hashes, outcomes, and diagnostics.
  - `docs/specs/docmend.md:731` correctly classifies artifacts as confidential and retained until purge, and `src/docmend/schemas/README.md` notes real library paths, but neither runbook gives permission, placement, backup, sharing, retention, or purge instructions.
  - Manifest paths are absolute (`src/docmend/writer/manifest.py` contract; `docs/runbooks/restore-from-manifest.md:29-30`), increasing disclosure impact.
  - The default `.gitignore` protects only repositories that contain this project's ignore rule; it does not protect arbitrary invocation directories or cloud-synced folders.
- impact: A user can copy a manifest into an issue, place `.docmend/` in a synced/public directory, retain sensitive run history indefinitely, or expose absolute personal paths even though document bodies never leave the machine.
- recommendation: Put a prominent warning next to the default artifact location and in both runbooks. Document restrictive placement/permissions, safe support bundles, fields that must be redacted, backup/encryption expectations, retention and logical deletion, and an explicit warning that ordinary deletion is not portable secure erasure.

### ISSUE-005: User onboarding omits the actual Linux/POSIX, Python 3.14, and uv prerequisites

- first_pass: 1
- severity: medium
- confidence: high
- documentation_area: setup-and-onboarding
- issue_type: setup-onboarding-gap
- evidence_status: verified directly
- evidence:
  - `README.md` starts with command semantics and places install forms at `:105`, but has no prerequisites, install verification, or supported-platform section.
  - `docs/specs/docmend.md:872-880` limits the runtime to a Linux workstation with local POSIX filesystem semantics and Python 3.14+.
  - Runtime code uses `fcntl.flock` (`src/docmend/lock.py`) and `SIGALRM`/`setitimer` (`src/docmend/watchdog.py`), so the platform limitation is functional, not merely a tested-on note.
- impact: Users can attempt installation on Windows, network/object storage, or an older Python and encounter import/runtime failures or unsupported durability semantics only after setup or during a long run.
- recommendation: Add a concise Quick Start with supported OS/filesystem, Python and uv prerequisites, artifact install/source install commands, `docmend --version`, a synthetic dry-run, and an explicit unsupported/untested platform list. Replace “environment matrix not applicable” with a one-row supported execution matrix.

### ISSUE-006: Recovery runbooks lack the minimum fields needed for safe triage under pressure

- first_pass: 3
- severity: medium
- confidence: high
- documentation_area: runbook-structure-and-minimum-fields
- issue_type: runbook-structure-gap
- evidence_status: verified directly against both runbooks and shared runbook guidance
- evidence:
  - Both runbooks have useful triggers and commands, but neither identifies owner, last review, applicable versions/schema window, prerequisites, evidence to preserve, explicit stop/contain conditions, escalation/decision points, or post-incident follow-up.
  - The restore runbook does not tell the operator to work from a safe copy, retain manifests/logs/backups before retry, or stop when backup/manifest integrity is uncertain.
  - The resume runbook's example uses `--preserved-by git` (`:32-44`) without a precondition that the claimed Git recovery point exists and is byte-preserving.
- impact: The commands are discoverable, but an operator can destroy evidence, resume with a different preservation posture, or improvise through ambiguous state during the exact incidents the documents are meant to control.
- recommendation: Adopt a repo-specific runbook template with owner, reviewed date, scope/version, detection, prerequisites, stop/contain, evidence, preview, action, verification, rollback-of-recovery, escalation, and follow-up. For this single-user CLI, escalation can simply be “stop and obtain owner review,” but it should be explicit.

### ISSUE-007: The release procedure starts at tagging and omits preparation, contract checks, and failure recovery

- first_pass: 4
- severity: medium
- confidence: high
- documentation_area: deployment-and-release-docs
- issue_type: deployment-release-doc-gap
- evidence_status: verified directly against README, workflow, history, and shared packaging guidance
- evidence:
  - `README.md:97-105` says to tag `main`, then lets the workflow build and attach artifacts. It does not require a version bump, changelog update, `uv lock`, clean/green commit, tag/package-version equality, local artifact inspection, or failed-release cleanup.
  - Commit `64eb307` exists solely to regenerate `uv.lock` after the v1.0.2 version bump; the durable session record says the omission failed `uv sync --locked`.
  - `.github/workflows/release.yml` smoke-tests the wheel but does not bind the tag to `pyproject.toml`/`docmend.__version__`, build the wheel from the sdist, or document rollback of an incorrect GitHub Release/tag.
- impact: A maintainer can create a signed release tag for a stale lock or mismatched package version, then need ad hoc tag/release repair. Package rollback also does not undo data already mutated by that version.
- recommendation: Create a release runbook covering version/changelog/lock updates, the full local gate, tag/version assertions, sdist-to-wheel and clean-install smoke tests, artifact contents, signing, publish verification, failed-tag/release cleanup, and the distinction between package rollback and corpus recovery.

### ISSUE-008: The spec claims every command emits an authoritative machine-readable job record, but plan and verify do not satisfy that description

- first_pass: 2
- severity: medium
- confidence: high
- documentation_area: docs-to-code-alignment
- issue_type: docs-code-alignment-gap
- evidence_status: verified directly
- evidence:
  - `docs/specs/docmend.md:946-949` says every scan, plan, apply, and verify run emits a machine-readable artifact with start/finish, per-file outcomes, reasons, and counts, and that a report is authoritative.
  - `FR-018` at `docs/specs/docmend.md:346` names reports for plan and apply, while `DR-003` defines only an apply report.
  - `docmend plan` writes an inventory/plan, not a DR-003 job report; `docmend verify` prints findings and writes no verification artifact. Current `docmend verify --help` has inputs only.
- impact: Wrapper authors can wait for a documented job record that never appears, and unattended audit/history claims are stronger than the observable interface.
- recommendation: Define command-specific artifacts precisely. Either add plan/verify result artifacts with a stable schema or say which existing artifact/log/exit code is authoritative for each command. Add CLI tests that assert the documented artifact set per command.

### ISSUE-009: The compliance section makes an unverified “none apply” legal conclusion

- first_pass: 3
- severity: medium
- confidence: medium
- documentation_area: external-dependency-and-support-docs
- issue_type: external-dependency-support-doc-gap
- evidence_status: repository claim verified; actual legal applicability could not be verified from repository evidence
- evidence:
  - `docs/specs/docmend.md:790-795` marks PII/regulatory regimes as identified and says none apply because personal data is processed locally by its owner.
  - The shared research pack explicitly records jurisdiction, roles, retention, deletion, and breach obligations as unknown and cautions that sensitivity labels do not establish or exclude HIPAA, GLBA, GDPR, or other regimes.
  - No jurisdictional analysis, user-role limitation, legal review, or deployment restriction in the repo supports the categorical conclusion.
- impact: The approved spec can be read as legal clearance for uses beyond the owner's current personal workflow.
- recommendation: Replace the legal conclusion with a scoped engineering statement: v1 is local/offline and makes no regulatory determination; applicability depends on user, data, jurisdiction, and organizational role. Record owner responsibilities and route any non-personal/organizational deployment to qualified review.

### ISSUE-010: Docs-as-code validates style and spec shape but not links or executable documentation

- first_pass: 4
- severity: medium
- confidence: high
- documentation_area: docs-as-code-validation-and-executability
- issue_type: docs-as-code-validation-gap
- evidence_status: verified directly with local checks
- evidence:
  - CI runs markdownlint, spec validation, and traceability, but no local-link checker or CLI-help/documentation contract check is configured.
  - A tracked-file local-link scan found 11 broken relative links: six in `docs/prompts/prompt-consistency-workflow.md:40-45` and five in `docs/prompts/prompt-gap-analysis-workflow.md:19-23`; the latter also points to nonexistent `docs/decisions` instead of `docs/adr`.
  - The substantive CLI/config drift in ISSUE-002 and artifact drift in ISSUE-008 passed the existing validators.
  - Current tracked product docs pass Prettier; traceability passes. Markdownlint errors observed in the dirty tree were confined to orchestrator-generated review artifacts, which this review was forbidden to edit and excluded from product-doc findings.
- impact: Green documentation CI can coexist with broken navigation and commands/options that do not exist.
- recommendation: Add repository-confined link validation, generated CLI help or option inventories, config-default/schema comparisons, and smoke execution of Quick Start/runbook commands on a synthetic corpus. Keep generated review artifacts either lint-conformant or explicitly excluded by an owned convention.

### ISSUE-011: The handoff architecture's standing backlog is stale after v1.0.2

- first_pass: 4
- severity: low
- confidence: high
- documentation_area: freshness-ownership-and-review-cadence
- issue_type: freshness-review-cadence-gap
- evidence_status: verified directly
- evidence:
  - `docs/handoff/architecture.md:23` says v1.0.1 is released.
  - `README.md:5`, `docs/STATUS.md:5`, Git tags, and `docs/handoff/deployed.md` identify v1.0.2 as current.
- impact: Future agents using the durable architecture owner can anchor on an obsolete release even though the eager status is correct.
- recommendation: Keep historical “Through MS-\*” paragraphs clearly labeled as history, but make the standing structural backlog release-neutral or update it through the normal handoff closeout path.

### ISSUE-012: The large documentation corpus has no audience-oriented landing page

- first_pass: 4
- severity: low
- confidence: high
- documentation_area: audience-and-information-architecture
- issue_type: audience-information-architecture-gap
- evidence_status: verified directly
- evidence:
  - `docs/` contains the approved spec, 18 ADRs, two runbooks, status/tasks, research, schemas, prompts, and handoff records.
  - There is an ADR index and research index, but no `docs/README.md` or equivalent explaining which documents are for users, contributors, operators, and agents.
  - The root README links important individual documents but does not expose status/tasks, research, artifact schemas, or documentation ownership boundaries.
- impact: Readers can enter stale research or LLM-only handoff history without knowing whether it is normative, operational, historical, or human-facing.
- recommendation: Add a small docs landing page that maps audiences to the README, runbooks, spec, ADR index, schema contract, status/tasks, and historical research, explicitly labeling canonical versus contextual documents.

### ISSUE-013: `docmend plan --help` omits a real exit code and the README blurs global versus command-local write flags

- first_pass: 2
- severity: low
- confidence: high
- documentation_area: docs-to-code-alignment
- issue_type: docs-code-alignment-gap
- evidence_status: verified by executing current CLI help and reading tests
- evidence:
  - `README.md:17` correctly lists exit 3 for a held plan lock, and `tests/test_cli_plan.py::TestPlanLock` verifies it.
  - Current `docmend plan --help` documents only exits 0, 1, and 2.
  - `README.md:33-35` labels `--dry-run/-n` global and says it conflicts with `--write`, but `--write` exists only on `apply` and `restore`, not as a global option.
- impact: Shell integrations generated from `--help` can mishandle lock refusal, and users can place `--write` in the wrong command position.
- recommendation: Generate exit-code/help text from one command contract and describe the conflict as “global `--dry-run` conflicts with the selected command's `--write`.”

### ISSUE-014: The specification revision history is not ordered by revision

- first_pass: 4
- severity: low
- confidence: high
- documentation_area: maintenance-and-update-paths
- issue_type: maintenance-update-gap
- evidence_status: verified directly
- evidence:
  - `docs/specs/docmend.md:48-70` orders revision rows as 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 0.6, 0.8, 0.9, 0.10, 0.11, 0.14, 0.13, 0.12, and later 0.20, 0.21, 0.22, 0.23, 0.24, 0.25, 0.19.
  - The spec is approved and change-controlled, so this history is the primary change narrative.
- impact: Reviewers cannot reliably scan the evolution or determine what a later revision superseded without manually sorting versions.
- recommendation: Put revision rows in ascending numeric order and add a validator for monotonic, unique revision identifiers without changing their content.

## Review Metadata

- repo_path: `.`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- worktree_state: dirty before review; pre-existing `AGENTS.md` modification and untracked `docs/codex-reviews/` sweep artifacts
- review_mode: read-only repository audit except for this requested report
- runtime_and_stack: Python 3.14 library/CLI; Typer/Rich; Pydantic; JSON Schema Draft 2020-12; ruamel.yaml; structlog; uv; pytest/Hypothesis; GitHub Actions
- primary_audiences_reviewed: CLI user/operator, contributor/release maintainer, coding agent, artifact consumer
- documentation_surfaces_reviewed: root README, changelog, approved spec, ADR README/index/backlog and representative ADRs, status/tasks, handoff architecture/deployed/specs-plans/conventions, runbooks, research index and selected recovery research, schema README, prompt workflows, repo-hygiene checklist, CI/workflows, package/config/CLI/writer supporting code, relevant tests
- audience_entrypoints_reviewed: `README.md`, `AGENTS.md`, `CLAUDE.md`, ADR index, research index, status/tasks
- runbooks_reviewed: `docs/runbooks/restore-from-manifest.md`, `docs/runbooks/resume-after-interruption.md`
- setup_and_onboarding_reviewed: install forms, prerequisites, config reference, global and per-command help, contributor gate
- ci_deployment_troubleshooting_reviewed: all GitHub workflows, Dependabot, release flow, runbook failure notes, CLI exit help
- docs_validation_reviewed: Prettier, markdownlint, project-spec validation configuration, traceability script/workflow, local tracked-link scan
- freshness_ownership_reviewed: README release status, spec `last_reviewed` and revision history, ADR owners/status, handoff current facts, runbook metadata
- expected_but_missing: supported-environment Quick Start, confidential-artifact operations guidance, complete release runbook, full restore-verification procedure, docs landing page, runbook template/minimum fields
- external_surfaces_not_in_repo: GitHub branch-protection/security settings and release UI; operator's private backup regime; real-library rollout records; jurisdictional/legal analysis
- important_unknowns: exact filesystem/threat model, external backup integrity and retention, legal scope, whether inert config fields are reserved or intended functionality
- prior_baseline_compared: tag `v1.0.2`; current HEAD differs in documentation primarily through Agent Handoff adoption/status routing, not product CLI behavior
- research_used: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`; no broad or targeted follow-up internet research was needed
- exclusions: `.venv`, generated/build output, byte-exact fixture bodies, and orchestrator-owned execution/sweep/live-status artifacts
- workflow_schema_note: the child workflow's relative `references/report-schema.md` link is broken; the located canonical file is a planning-report schema, so this report follows the child workflow's explicit required sections and finding fields rather than the unrelated planning layout

## Documentation Area Matrix

| Documentation area | Posture | Evidence / findings |
| --- | --- | --- |
| repo-entrypoint-and-readme | partial | Strong command overview; conditional recovery language later becomes unconditional (ISSUE-001). |
| audience-and-information-architecture | partial | Root/ADR/research entrypoints exist; no audience map (ISSUE-012). |
| setup-and-onboarding | gap | Install forms exist; prerequisites and supported platform are missing (ISSUE-005). |
| development-workflow-docs | adequate | Branch model and local gate are explicit and align with workflows. |
| architecture-and-design-docs | partial | Comprehensive approved spec/ADRs; live-contract drift and stale handoff remain (ISSUE-002, ISSUE-011, ISSUE-014). |
| runbooks-and-operations | gap | Resume/restore commands are useful; confidentiality and triage controls are missing (ISSUE-004, ISSUE-006). |
| runbook-structure-and-minimum-fields | gap | No owner/review/version/prerequisite/evidence/stop/escalation fields (ISSUE-006). |
| incident-and-rollback-guidance | high-risk gap | Recovery guarantees and verification procedure are unsafe/insufficient (ISSUE-001, ISSUE-003). |
| deployment-and-release-docs | partial | Workflow is live; preparation and rollback runbook is incomplete (ISSUE-007). |
| configuration-and-environment-docs | gap | Full table exists; unsupported/inert settings and platform prerequisites are unclear (ISSUE-002, ISSUE-005). |
| troubleshooting-and-debugging | partial | Outcome/failure tables exist; decision and evidence paths are incomplete (ISSUE-003, ISSUE-006). |
| ownership-and-escalation | gap | Spec/ADRs have owners; runbooks do not (ISSUE-006). |
| freshness-ownership-and-review-cadence | partial | Status is current; no runbook cadence and one stale durable fact remain (ISSUE-006, ISSUE-011). |
| docs-to-code-alignment | high-risk gap | CLI/config/artifact claims diverge from executable surface (ISSUE-002, ISSUE-008, ISSUE-013). |
| adr-and-decision-history | adequate | 18 indexed accepted ADRs with rationale; ADR history is intentionally immutable. |
| docs-as-code-validation-and-executability | partial | Style/spec/traceability gates exist; links and commands are not validated (ISSUE-010). |
| external-dependency-and-support-docs | partial | Runtime dependencies and licenses are documented; legal/support boundary is overclaimed (ISSUE-009). |
| maintenance-and-update-paths | partial | Strong conventions and hygiene checklist; revision ordering/link drift remain (ISSUE-010, ISSUE-014). |
| documentation-testing-and-validation | partial | Traceability and restore tests exist; operator docs and artifact promises lack executable checks (ISSUE-003, ISSUE-008, ISSUE-010). |

## Severity Summary

| Severity | Count | IDs                                                              |
| -------- | ----: | ---------------------------------------------------------------- |
| critical |     0 | —                                                                |
| high     |     4 | ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-004                       |
| medium   |     6 | ISSUE-005, ISSUE-006, ISSUE-007, ISSUE-008, ISSUE-009, ISSUE-010 |
| low      |     4 | ISSUE-011, ISSUE-012, ISSUE-013, ISSUE-014                       |
| total    |    14 | ISSUE-001–ISSUE-014                                              |

## High-Risk Missing Or Misleading Guidance

- ISSUE-001: manifest completeness, reversibility, and zero-RPO claims exceed the documented implementation and no-backup posture.
- ISSUE-002: the approved spec exposes inert parallel/write configuration and nonexistent CLI flags.
- ISSUE-003: the restore runbook does not produce evidence of complete byte/path restoration.
- ISSUE-004: operators are not warned how to protect or purge confidential artifacts and logs.

## Setup And Onboarding Gaps

- ISSUE-005 is the primary gap: Linux/local-POSIX, Python 3.14+, and uv are not surfaced before installation.
- There is no copyable first-run sequence over synthetic data that demonstrates scan, plan, dry-run apply, preserved write, verify, and restore.
- Developer setup is largely inferable from the local gate, but clone/sync/test and generated-artifact expectations are not presented as onboarding.

## Runbook And Operational Gaps

- The two existing runbooks cover the highest-value product actions and contain useful outcome tables.
- They do not cover wrong-root/containment suspicion, corrupt or mismatched artifacts, sensitive-artifact disclosure, bad release/schema compatibility, or compromised release/dependency workflows.
- For this repo, service-health, pager, web/API, database, and distributed-system runbooks are `not needed for this repo`; it is a manual local CLI with no service or datastore.

## Runbook Structure And Triage Quality

| Minimum field | Restore | Resume | Assessment |
| --- | --- | --- | --- |
| trigger / detection | present | present | Good. |
| owner / decision authority | missing | missing | Add owner and explicit stop-for-review point. |
| applicable versions / schemas | missing | missing | Important for historical manifests. |
| prerequisites | partial | partial | Preservation and integrity preconditions are underspecified. |
| stop / contain | partial | partial | Lock/interference outcomes exist; broad stop conditions do not. |
| evidence to preserve | missing | missing | Add manifests, reports, logs, backup identity, and corpus snapshot. |
| preview | present | present | Good dry-run posture. |
| recovery action | present | present | Commands are concrete. |
| verification | weak | partial | Restore proof is inadequate; resume verifies each manifest only. |
| rollback of recovery | partial | not addressed | Inverse-manifest limitations are noted, but safe recovery rollback is not planned. |
| escalation / communication | missing | missing | External communications are `not needed for this repo`; owner review is still needed. |
| follow-up / retention | missing | missing | Add backup-retention and anomaly/bug capture guidance. |

## Freshness, Ownership, And Review Cadence

- README, changelog, status, deployed truth, tags, and package version agree on v1.0.2.
- `docs/handoff/architecture.md:23` is stale at v1.0.1 (ISSUE-011).
- Runbooks have no owner, reviewed date, or review trigger (ISSUE-006).
- ADRs have owners/status and are historical records; null `reviewed` values are not treated as a defect by themselves because the repo convention declares ADRs immutable and superseded by new ADRs.
- Recommended review triggers: any manifest/schema change; recovery behavior change; new filesystem/platform support; release workflow change; and each restore drill or real-library incident.

## Docs To Code Drift

- ISSUE-001: recovery promises versus mutation/manifest order.
- ISSUE-002: parallel/config/flag/verify contract drift.
- ISSUE-008: machine-readable job-record promises versus actual command artifacts.
- ISSUE-013: plan exit-code help and global/local flag terminology.
- The root README's command descriptions and most shipped defaults otherwise align with current `--help`, `config.py`, and v1.0.2 behavior.

## ADR And Decision History Gaps

- No missing ADR category was identified for the current v1 architecture.
- ADR index and files 0001–0018 are present and accepted.
- The release ADR intentionally records the pre-MS-5 decision point; current operational truth correctly lives in `README.md` and `docs/handoff/deployed.md`.
- The approved spec revision table should be ordered for reviewability (ISSUE-014).

## Executable Documentation And Drift Checks

- Executed current CLI version and all command help successfully with `UV_CACHE_DIR` redirected to `/tmp` because the review sandbox's default uv cache path was read-only.
- Executed `scripts/check_traceability.py`: pass.
- Checked tracked product Markdown/JSON/YAML with Prettier: pass.
- Markdownlint's dirty-tree failures were only in orchestrator-generated review files; tracked product docs had no reported lint violations in the same run.
- Local tracked-link scan: 11 broken links, all in the two prompt workflow documents (ISSUE-010).
- Compared tag `v1.0.2` with current HEAD and reviewed current product-doc changes.
- Did not execute the 100k scale test or mutate a corpus; neither was necessary for a documentation-only review.

## Documentation Testing Gaps

- No automated CLI-help/README option parity test.
- No test that documented configuration fields affect behavior or are rejected as reserved.
- No test of the artifact set promised for each command.
- No repository-confined Markdown link checker.
- No executable Quick Start or runbook test over a synthetic corpus.
- Restore tests prove implementation behavior on fixtures, but the operator's documented verification command does not prove full recovery.
- Release tests do not bind tag, package version, lock freshness, changelog, and built artifact into one documented gate.

## Convention Recommendations

### Cross-project defaults

- Runbooks should carry owner, reviewed date, scope/version, prerequisites, stop conditions, evidence, action, verification, rollback, escalation, and follow-up fields.
- User-facing CLI docs should be generated from or tested against command/config contracts.
- Documentation CI should validate repository-confined links and executable examples in addition to style.
- Recovery claims should separate atomic visibility, durability, journal completeness, backup integrity, and full restore evidence.
- Compliance docs should distinguish verified engineering properties from external legal determinations.

### Repo-specific exceptions and additions

- Keep repo-doc frontmatter unvalidated per ADR-0001; a runbook template can use ordinary Markdown fields rather than introducing a conflicting frontmatter standard.
- Preserve the repo's synthetic-only public fixture rule in every executable-doc test.
- Treat `.docmend/` artifacts/logs as confidential operator data and keep them out of public fixtures, issues, and review reports.
- Make Linux/local-POSIX support explicit until `flock`, `SIGALRM`, filesystem, and filename behavior are ported and tested elsewhere.
- Keep standard-owned workflow files unchanged; implement new semantic documentation checks through repo-owned additive tests/workflows unless the standard is deliberately revised.

## Pass Log

| Pass | Lens | New issues | Result |
| --: | --- | --- | --- |
| 1 | inventory, entrypoints, setup, architecture, runbooks, missing-doc hotspots | ISSUE-005 | Substantial docs surface; onboarding prerequisites missing. |
| 2 | docs-to-code, CLI help, config, recovery ordering, artifacts | ISSUE-001, ISSUE-002, ISSUE-008, ISSUE-013 | Approved spec and recovery claims diverge materially. |
| 3 | operator guidance, rollback, triage, sensitive data, ownership | ISSUE-003, ISSUE-004, ISSUE-006, ISSUE-009 | Recovery proof and confidential-artifact operations are weak. |
| 4 | release, links, freshness, information architecture, maintenance clarity | ISSUE-007, ISSUE-010, ISSUE-011, ISSUE-012, ISSUE-014 | Lower-severity drift and validation gaps recorded. |
| 5 | v1.0.2 baseline comparison, issue deduplication, severity challenge | none | Existing evidence strengthened; no new issue. |
| 6 | final area-matrix sweep and unresolved-unknown review | none | Second consecutive no-new-issue pass; convergence allowed. |

## Claude Handoff

- highest_priority_order:
  1. Reconcile recovery guarantees and runbooks (ISSUE-001, ISSUE-003) before the first real-library write.
  2. Reconcile approved spec with live CLI/config/artifact behavior (ISSUE-002, ISSUE-008).
  3. Add confidential-artifact handling guidance (ISSUE-004).
  4. Add platform prerequisites and runbook minimum fields (ISSUE-005, ISSUE-006).
- likely_change_control: ISSUE-001, ISSUE-002, ISSUE-008, and ISSUE-009 touch the approved spec and require a new revision row; behavior changes may also require ADR/OQ handling under repository conventions.
- implementation_boundary: This review did not authorize fixes. Preserve orchestrator artifacts and the existing dirty `AGENTS.md` change.
- suggested_verification_after_fixes: CLI help snapshot/parity tests; config behavior tests; synthetic end-to-end runbook exercise; full restore hash/path proof; link check; Prettier/markdownlint; spec validation; traceability; agent-handoff validation if handoff facts change.

## Open Questions Or Assumptions

- Is the intended threat model a trusted single user on a private local tree, or can artifacts/directories be attacker-modifiable or shared with other users/processes?
- Which Linux filesystems and storage media are supported for corpus and backup roots, and what durability is promised on removable/network/case-insensitive/Unicode-normalizing filesystems?
- Are `parallel.*`, `write.atomic`, and `write.dry_run_default` intended post-v1 reserved fields or incomplete v1 functionality?
- Should verify/plan gain result artifacts, or should the approved artifact/report requirements be narrowed?
- What external preservation regime will the owner use for the staged real-library rollout, and what evidence proves its recovery point before apply?
- What jurisdiction, data roles, and retention/deletion duties apply to actual use? Repository evidence is insufficient for a legal conclusion.
- GitHub branch protection, release settings, vulnerability alerts, and published release assets were not independently verified through the external UI in this review.

## Residual Risk

- High residual risk remains until recovery language and verification are corrected: current docs can induce overconfidence even though the CLI has conservative defaults and warnings.
- High-confidence repo evidence supports ISSUE-001 through ISSUE-008 and ISSUE-010 through ISSUE-014.
- ISSUE-009 is medium-confidence because the documentation defect is the unsupported certainty; actual legal applicability is intentionally unresolved.
- External GitHub settings, private backup integrity, and the real-library environment remain unverified outside-repo surfaces.
- No finding assumes FastAPI, SQLAlchemy/Alembic, Svelte, AI inference, queues, webhooks, Docker, systemd, desktop packaging, or a network API; executable scope confirms those are `not needed for this repo` in v1.
