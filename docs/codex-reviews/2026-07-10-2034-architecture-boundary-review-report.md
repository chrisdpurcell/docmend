# Architecture And Boundary Review

## Review Metadata

- review_type: `architecture-boundary-review`
- reviewed_at: `2026-07-10`
- repo_path: `.`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- release_baseline: `v1.0.2` (`ffdcc47d6c3a5375f0454c4b3afa5b734260acc1`)
- baseline_comparison: `v1.0.2..HEAD` changes handoff/configuration documentation only; no runtime source files changed after the release tag.
- working_tree_state: `dirty` before this review (`AGENTS.md` modified; `docs/codex-reviews/` untracked). Those pre-existing changes were not edited.
- review_scope: full repository architecture, module boundaries, dependency direction, mutation/recovery coordination, artifact contracts, configuration boundaries, ADR alignment, and architecture enforcement.
- runtime: Python `>=3.14`, single-process Linux/POSIX batch CLI.
- frameworks_and_packaging: Typer, Rich, Pydantic v2, JSON Schema Draft 2020-12, structlog, charset-normalizer, ruamel.yaml, `uv_build`, uv lockfile.
- module_roots_reviewed: `src/docmend/`, `src/docmend/transform/`, `src/docmend/writer/`, `tests/`, `.github/workflows/`.
- entrypoints_reviewed: `docmend.cli:app`; `scan`, `plan`, `apply`, `restore`, and `verify` commands; `writer.apply.execute_plan`; `restore.run_restore`.
- design_inputs_reviewed: approved spec revision 0.25; ADRs 0002, 0004-0007, 0010, 0012, 0014, 0016, and 0018; `docs/handoff/architecture.md`; `docs/handoff/conventions.md`; restore/resume runbooks; artifact schema README.
- conventions_input: `docs/handoff/conventions.md` (repo equivalent of `docs/conventions.md`).
- ownership_signals: one named owner in ADRs; public repository; no need for formal multi-team ownership boundaries at current size.
- external_boundary: private sibling `doc-proc-scripts` is documented by ADR-0018 but was outside this repository review and was not independently verified.
- exclusions: generated caches, local `.docmend/` run artifacts, coverage output, Hypothesis cache, vendored/generated output, and byte-exact weird-document fixture contents.
- shared_research_used: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`.
- targeted_internet_follow_up: none; the current shared research covered the relevant Python, filesystem, schema, recovery, and fitness-function guidance.
- validation_run: `uv run pytest -q tests/test_import_contracts.py tests/test_restore.py tests/test_schemas.py tests/test_scale.py -m 'not slow'` -> `56 passed, 1 deselected`.
- slow_scale_test_run: no; prior checked-in evidence was reviewed instead.

## Architecture Area Matrix

| Architecture area | Relevance | Assessment | Findings |
| --- | --- | --- | --- |
| `system-decomposition-and-entrypoints` | high | Layered shape is clear, but write orchestration is split between Typer and callable engines. | ISSUE-001, ISSUE-002, ISSUE-008 |
| `layering-and-dependency-direction` | high | Transform purity is protected; writer-to-discovery and restore-outside-writer dependencies erode the intended direction. | ISSUE-003, ISSUE-007, ISSUE-009 |
| `module-boundaries-and-ownership` | high | Mutation ownership and operation-vocabulary ownership are not aligned with ADR-0002. | ISSUE-001, ISSUE-003, ISSUE-007 |
| `ownership-and-cognitive-load` | medium | Formal team boundaries are not needed for this repo; the 865-line CLI is the main cognitive-load hotspot. | ISSUE-008 |
| `domain-modeling-and-business-rules` | high | Core artifact models are strong; complete transform policy and operation vocabulary do not have one domain owner. | ISSUE-007 |
| `shared-kernel-and-utility-drift` | medium | No generic utility hub exists, but `sniff_bom` is owned by discovery while consumed by writer. | ISSUE-007 |
| `cross-cutting-concerns` | high | Locking, safety gating, reporting, and version checks are distributed across adapters and engines. | ISSUE-001, ISSUE-002, ISSUE-006 |
| `integration-boundaries-and-adapters` | low | No live remote/provider integrations; not needed for this repo. The sibling wrapper boundary is documented but externally unverified. | none |
| `state-and-side-effect-management` | critical | Apply has an intent journal, but public write engines can bypass coordination and restore is not interruption-convergent. | ISSUE-001, ISSUE-002, ISSUE-003 |
| `configuration-and-environment-boundaries` | high | Strict Pydantic validation is good; accepted parallel settings are runtime no-ops. | ISSUE-004 |
| `package-layout-and-discoverability` | medium | Most package names are legible; restore placement and CLI concentration hide mutation ownership. | ISSUE-003, ISSUE-008 |
| `change-amplification-and-coupling` | high | Byte transformation semantics are repeated in planning and apply. | ISSUE-007 |
| `abstraction-quality-and-complexity` | medium | Atomic primitives and schema registry are appropriate; application-service coordination is missing. | ISSUE-001, ISSUE-002 |
| `intended-architecture-vs-reality` | high | Writer isolation, process-pool support, and bounded-memory claims do not match implementation. | ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-010 |
| `documentation-and-adr-drift` | high | Several accepted or current records overstate implemented enforcement or current release posture. | ISSUE-004, ISSUE-005, ISSUE-010 |
| `architecture-fitness-functions-and-enforcement` | high | Transform purity is well enforced; broader layering and mutation invariants are not. | ISSUE-009 |
| `transitional-legacy-paths` | medium | Historical minor artifacts are supported implicitly, but future-minor rejection is inconsistent. | ISSUE-006 |
| `architecture-testability-and-enforcement` | high | Tests are extensive and deterministic, but some tests canonize unsafe boundary bypass or incomplete recovery. | ISSUE-001, ISSUE-003, ISSUE-009 |

## Severity Summary

| Severity | Count | Issue IDs                                             |
| -------- | ----: | ----------------------------------------------------- |
| critical |     0 | none                                                  |
| high     |     2 | ISSUE-001, ISSUE-003                                  |
| medium   |     5 | ISSUE-002, ISSUE-004, ISSUE-005, ISSUE-006, ISSUE-007 |
| low      |     3 | ISSUE-008, ISSUE-009, ISSUE-010                       |

## Findings

### ISSUE-001 — Destructive engines are callable outside the safety coordinator

- severity: `high`
- confidence: `high`
- first_pass: `1`
- architecture_area: `state-and-side-effect-management`
- issue_type: `architecture-enforcement-gap`
- verification: `direct repo evidence`
- evidence:
  - `src/docmend/cli.py:537-580` acquires the run lock and evaluates the safety gate before calling `execute_plan`; its comment explicitly says the engine does not self-enforce preservation.
  - `src/docmend/writer/apply.py:587-704` accepts `ApplyOptions(write=True)` and mutates without acquiring a lock or evaluating the gate.
  - `src/docmend/cli.py:740-756` similarly owns the restore lock outside `run_restore`, while `src/docmend/restore.py:106-143` accepts `write=True` directly.
  - `tests/test_apply.py:46-63` and numerous write tests call `execute_plan` directly; several use `write=True` without backup or declared preservation. Restore tests also call `run_restore` directly.
- risk: The mandatory FR-005 preservation check and AW-005 single-writer lock are properties of one Typer call path, not invariants of the mutation boundary. A future Python API, new subcommand, refactor, wrapper, or test helper can perform real writes while bypassing both controls.
- recommendation: Introduce one application service per destructive workflow that owns version validation, lock acquisition, gate evaluation, engine execution, and terminal artifact handling. Make the raw mutation loop private (for example, `_execute_plan_unchecked`) or require an unforgeable coordinator-owned capability. Route CLI and tests through the guarded service; keep low-level fault-injection tests explicitly scoped to private primitives.
- acceptance_evidence:
  - A direct call to the public apply service with a content rewrite and no preservation refuses without mutation.
  - Concurrent direct service calls contend on the same source-root lock.
  - No public write-capable path can reach the mutation loop without the coordinator.

### ISSUE-002 — Report finalization is outside gate preflight and lock scope

- severity: `medium`
- confidence: `high`
- first_pass: `2`
- architecture_area: `cross-cutting-concerns`
- issue_type: `state-side-effect-gap`
- verification: `direct repo evidence`
- evidence:
  - `src/docmend/writer/gate.py:184-232` preflights the manifest directory but has no input for the actual report path.
  - `src/docmend/cli.py:530-584` permits a custom report path, releases the run lock after mutation, and only then calls `artifacts.write_report`.
  - FR-018 and ADR-0002 treat the report/audit trail as mandatory, and the report is described as authoritative in spec section 18.5.
- risk: A write run can mutate the corpus and durably append its manifest, then fail to write an unwritable or failing custom report. The command loses its required DR-003 terminal record, and another run can start after lock release while the prior run is not fully finalized.
- recommendation: Preflight the actual report destination for write runs and finalize the report inside the application-service lifecycle. Preserve the manifest as the mutation authority, but define and test an explicit terminal state for report-write failure after mutations rather than allowing an uncategorized exception.
- acceptance_evidence:
  - An unwritable custom report path refuses before the first corpus mutation.
  - Fault injection during report publication yields a defined exit/result and leaves enough durable state to reconstruct the report.
  - The lock lifetime matches the documented definition of run completion.

### ISSUE-003 — Restore is outside the writer and cannot converge after a mid-record interruption

- severity: `high`
- confidence: `high`
- first_pass: `1`
- architecture_area: `state-and-side-effect-management`
- issue_type: `architecture-drift-gap`
- verification: `direct repo evidence plus focused passing test`
- evidence:
  - ADR-0002 (`docs/adr/adr-0002-layered-pipeline-isolated-writer.md:40-68`) says the isolated writer is the sole mutation component.
  - `src/docmend/restore.py:232-268` performs a multi-step inverse mutation in a top-level module and calls `target.unlink()` directly.
  - Unlike apply's manifest 1.3 intent protocol, restore writes its inverse record only after all mutation steps complete (`src/docmend/restore.py:268-281`).
  - `tests/test_restore.py:463-513` injects failure after the original is restored but before the target is removed; the next restore intentionally returns a collision skip instead of reconciling and completing the record.
- risk: An interruption or I/O failure in the disaster-recovery path leaves a safe but ambiguous superset of files, no durable intent describing the half-restore, and no automatic convergence path. The operator must manually interpret the collision. This also falsifies the standing writer-only mutation boundary and makes side-effect auditing incomplete.
- recommendation: Move restore mutation coordination into the writer/application boundary and give every multi-step inverse operation a write-ahead intent plus deterministic reconciliation, analogous to apply's manifest 1.3 protocol. Put unlink-plus-directory-fsync behind an atomic writer primitive. Extend the restore runbook with interruption states until the implementation converges automatically.
- acceptance_evidence:
  - Kill/fault injection at every restore mutation boundary can be rerun to completion or produces an explicit interference failure.
  - Every mutation and pending inverse operation has durable evidence before the mutation occurs.
  - An architecture fitness check confirms corpus mutation calls live only in the approved writer boundary.

### ISSUE-004 — Accepted parallel configuration is silently ignored

- severity: `medium`
- confidence: `high`
- first_pass: `3`
- architecture_area: `configuration-and-environment-boundaries`
- issue_type: `architecture-drift-gap`
- verification: `direct repo evidence`
- evidence:
  - ADR-0007 and spec section 18.2 state that `parallel.enabled=true` opts into `ProcessPoolExecutor` with a configured start method, workers, chunksize, and recycling policy.
  - `src/docmend/config.py:139-149` accepts that full configuration surface while its docstring says the switches are reserved for a profiled post-v1 pool.
  - Repository search finds no runtime read of `config.parallel`, no `ProcessPoolExecutor`, and no multiprocessing implementation; tests only validate parsing/defaults.
- risk: Valid configuration communicates behavior the runtime does not provide. Operators and wrappers can believe they enabled fault-isolated parallel processing while receiving the sequential engine, and the accepted ADR/spec/traceability claim cannot be trusted as deployment truth.
- recommendation: Resolve the approved-design conflict explicitly. Either implement ADR-0007 and test both modes, or revise the approved spec/ADR and reject `parallel.enabled=true` with a clear unsupported-feature error until the pool exists. Do not accept operational no-op settings.
- acceptance_evidence:
  - Every accepted parallel setting changes a measured/exercised runtime path, or unsupported combinations fail validation.
  - Process-mode tests assert worker isolation, parent-only manifest/report writing, configured start method, and identical output to sequential mode.

### ISSUE-005 — The completed bounded-memory requirement contradicts the in-memory pipeline

- severity: `medium`
- confidence: `high`
- first_pass: `3`
- architecture_area: `intended-architecture-vs-reality`
- issue_type: `architecture-drift-gap`
- verification: `direct repo evidence`
- evidence:
  - Approved NFR-001 (`docs/specs/docmend.md:353-355`) requires no whole-corpus in-memory structures and memory independent of corpus size.
  - `src/docmend/discovery.py:222-235` accumulates every file, symlink, skip, and hard-link group in memory; the returned inventory retains the full lists (`src/docmend/discovery.py:425-475`). Planning and apply likewise retain full action/outcome collections.
  - `tests/test_scale.py:114-119,194-205` deliberately asserts a count-proportional memory ceiling. Checked-in measurements report approximately 477 MiB at 100,000 files.
  - The spec traceability row marks NFR-001 complete even though its test proves O(file-count) memory, not independence from corpus size.
- risk: The architecture is adequate for the measured 100k case but does not satisfy the approved structural promise. Larger or metadata-heavy corpora have no constant/bounded-memory guarantee, and release traceability currently converts a contradictory test into evidence of completion.
- recommendation: Make an owner-level choice. If O(file-count) metadata is acceptable, revise NFR-001, its acceptance criterion, ADRs, and traceability to an explicit per-file budget. If independence is required, introduce streaming/spooled inventory and plan readers/writers and avoid retaining inventory, plan, report, and manifest projections simultaneously.
- acceptance_evidence:
  - Requirement text, architecture, and the scale test assert the same asymptotic bound.
  - Tests run at multiple corpus sizes and verify the chosen growth model, not one absolute 100k point.

### ISSUE-006 — Artifact readers do not consistently reject future schema minors

- severity: `medium`
- confidence: `high`
- first_pass: `2`
- architecture_area: `transitional-legacy-paths`
- issue_type: `transitional-legacy-gap`
- verification: `direct repo evidence plus current schema guidance from shared research`
- evidence:
  - `src/docmend/schemas/README.md:13-19` defines backward-only compatibility: newer tools read older artifacts.
  - Pydantic models and checked-in schemas accept any `1.x` version by pattern (`src/docmend/writer/manifest.py:37-48` and equivalent inventory/plan/report fields).
  - `src/docmend/artifacts.py:115-188` validates and constructs inventory, plan, and report models without a supported-minor check; `writer.manifest.read_manifest` does the same.
  - `src/docmend/cli.py:489-500` adds a future-minor rejection only for plans at apply time. Plan-from-inventory, restore-from-manifest, and verify/report paths have no equivalent guard.
- risk: An older executable can consume a future additive minor whose new optional field or enum changes safe interpretation. The highest-risk case is restore acting on a future manifest that still passes the old structural schema. Strict `additionalProperties` reduces but does not eliminate semantic forward-compatibility risk.
- recommendation: Centralize a per-artifact supported-version policy in the artifact readers. Parse kind/version first, reject unsupported majors and future minors, then validate the version-appropriate schema/model. Add golden historical fixtures for supported old minors and explicit rejection fixtures for future minors.
- acceptance_evidence:
  - Inventory, plan, report, manifest, and frontmatter readers share one tested compatibility matrix.
  - Every destructive consumer rejects future artifacts before path access or mutation.

### ISSUE-007 — Full transformation policy is duplicated across planning and apply

- severity: `medium`
- confidence: `high`
- first_pass: `2`
- architecture_area: `change-amplification-and-coupling`
- issue_type: `coupling-change-amplification-gap`
- verification: `direct repo evidence`
- evidence:
  - `src/docmend/planning.py:243-317` owns decode selection, file-class dispatch, config unpacking, transformation, invariant checks, re-encode operation, and rename decisions.
  - `src/docmend/writer/apply.py:101-131` reimplements most of the same byte-to-output policy to verify the plan.
  - Writer imports `sniff_bom` from the outward discovery layer (`src/docmend/writer/apply.py:28-46`).
  - `src/docmend/transform/dispatch.py:1-18` says planning never sequences transforms, but the same file says re-encode and rename occur outside it; its `Operation` type also owns non-transform values `rename` and `frontmatter_migrate` (`:31-40`).
- risk: Adding a file class, transform, provenance rule, or migration operation requires coordinated edits in discovery, planning, apply, transform dispatch, plan models, schemas, and tests. A missed edit becomes either a false plan, an apply-time divergence, or an inverted dependency from the danger layer to discovery.
- recommendation: Create one pure domain operation planner/executor that accepts source bytes, explicit provenance/config scalars, and path policy, then returns payload plus the canonical typed operation list and invariant result. Planning records that result; apply reruns the same pure function and compares it. Move BOM classification and operation vocabulary to a neutral domain/contracts module.
- acceptance_evidence:
  - Planning and apply use the same pure byte-transformation service.
  - Writer has no dependency on discovery.
  - Operation vocabulary has one neutral owner and schema drift tests still pass.

### ISSUE-008 — The CLI composition root has become a secondary application layer

- severity: `low`
- confidence: `high`
- first_pass: `4`
- architecture_area: `ownership-and-cognitive-load`
- issue_type: `ownership-cognitive-load-gap`
- verification: `direct repo evidence`
- evidence:
  - `src/docmend/cli.py` is 865 lines and imports nearly every application/domain boundary.
  - It owns configuration overrides, artifact naming/sidecar discovery, version policy, locking, preservation warnings, refusal-report creation, restore lock-root derivation, command exit taxonomy, and presentation for all five commands.
- risk: Typer-specific code is the only discoverable owner of several safety and lifecycle policies. Adding a command or non-CLI consumer increases the chance of copying an incomplete orchestration sequence and makes review impact harder to trace.
- recommendation: Keep `cli.py` as the composition root and thin adapter. Move each workflow into an application service with typed request/result objects; optionally split Typer command declarations by command once the service boundary exists. Do not split files first without resolving ISSUE-001.
- acceptance_evidence:
  - Command handlers only parse options, call one service, render a result, and map a typed outcome to an exit code.

### ISSUE-009 — Architecture fitness functions protect only transform purity

- severity: `low`
- confidence: `high`
- first_pass: `2`
- architecture_area: `architecture-fitness-functions-and-enforcement`
- issue_type: `fitness-function-gap`
- verification: `direct repo evidence`
- evidence:
  - The sole import-linter contract in `pyproject.toml:91-112` forbids filesystem/writer imports from `docmend.transform`.
  - `tests/test_import_contracts.py:1-28` runs only that contract.
  - No mechanical rule checks the full layer direction, writer-only corpus mutation, guarded public mutation entrypoints, or configuration-key consumption.
- risk: The existing green architecture gate can coexist with restore mutating outside writer, writer importing discovery, and public engines bypassing guards. ADR-0002's broader confirmation is therefore social rather than executable.
- recommendation: After the intended boundaries are corrected, add import-linter layered/forbidden contracts and small AST/contract tests for approved mutation modules, guarded service entrypoints, and accepted configuration consumption. Keep explicit exceptions for artifact, log, and lock writes so the check models corpus mutation rather than banning all I/O.
- acceptance_evidence:
  - A deliberate writer-to-discovery import, out-of-bound corpus unlink, or new public unchecked write function fails CI.

### ISSUE-010 — Architecture records overstate current conformance

- severity: `low`
- confidence: `high`
- first_pass: `3`
- architecture_area: `documentation-and-adr-drift`
- issue_type: `documentation-adr-gap`
- verification: `direct repo evidence`
- evidence:
  - `docs/handoff/architecture.md:5` and ADR-0002 state only writer mutates, contradicted by `restore.py`.
  - `docs/handoff/architecture.md:23` says v1.0.1 is released while `docs/STATUS.md:5` records v1.0.2.
  - ADR-0007 confirms sequential and process modes, but only sequential exists.
  - ADR-0005's confirmation mentions a regenerable latest-state index and a `check-jsonschema` pre-commit hook; neither is present in the tracked repository, while current schema tests provide different enforcement.
- risk: Future agents use these records as architecture truth and can close reviews or implementation claims against mechanisms that are absent or narrower than described.
- recommendation: Update accepted ADRs through their amendment process and keep `docs/handoff/architecture.md` as current structural truth rather than a release chronicle. Remove or explicitly defer confirmation mechanisms that do not exist.
- acceptance_evidence:
  - Every ADR confirmation maps to a current command/test/artifact.
  - The handoff architecture summary describes current release and actual mutation ownership.

## Boundary And Coupling Risks

- highest_risk_boundary: The CLI is currently the only safety coordinator, while the write engines remain directly callable. See ISSUE-001.
- recovery_boundary: Apply and restore do not share one interruption/reconciliation model. Apply has intent records; restore does not. See ISSUE-003.
- transaction_boundary: Corpus mutation, manifest durability, report publication, and lock lifetime do not have one documented application-service transaction. See ISSUE-002.
- transformation_boundary: Plan prediction and apply verification duplicate byte policy, with writer depending on discovery. See ISSUE-007.
- external_boundary: ADR-0018 clearly separates this product from `doc-proc-scripts`; conformance on the sibling side could not be verified from this repo.

## Decision Records And Intended Design

- ADR-0002: The layered pipeline and plan review point remain sound. Writer-only mutation and isolation are not currently true (ISSUE-003), and broader enforcement is missing (ISSUE-009).
- ADR-0004: Independent gate predicates are well tested, but the gate is owned by one CLI adapter rather than the destructive application boundary (ISSUE-001).
- ADR-0005: Hand-authored schemas, strict objects, packaged validation, and Pydantic cross-checks are strong. Reader-version policy is incomplete (ISSUE-006), and some confirmation prose is stale (ISSUE-010).
- ADR-0006: Apply intent reconciliation is a strong state-machine design. Restore needs a symmetric inverse-state protocol (ISSUE-003).
- ADR-0007: The selected process-pool design is not implemented even though its configuration and ADR are accepted (ISSUE-004).
- ADR-0010/0016: File-class dispatch is a useful seam, but the complete operation policy is still split across layers (ISSUE-007).
- ADR-0018: Repository responsibility is unusually explicit and valuable; surrounding organizational constraints remain external and unverified.

## Ownership And Discoverability Risks

- Formal CODEOWNERS or multi-team package ownership is `not needed for this repo` at its current single-owner scale.
- Mutation-policy ownership is unclear between `cli.py`, `writer/`, and top-level `restore.py` (ISSUE-001, ISSUE-003).
- Operation-vocabulary ownership in `transform.dispatch` is broader than the transform layer's stated role (ISSUE-007).
- The CLI's size and policy density make change impact harder to discover (ISSUE-008).

## Cross-Cutting And Integration Risks

- Locking, preservation gating, version compatibility, artifact paths, reporting, and exit mapping do not share one application-service owner.
- No network API, database, queue, webhook, AI, or hosted-service integration was found; those architecture categories are `not needed for this repo`.
- Filesystem containment/TOCTOU strength depends on an unresolved threat model and supported-filesystem matrix. This was not promoted to a finding because the approved runtime assumes a local POSIX workstation, but it remains residual risk.

## Architecture Drift And Documentation Gaps

- Writer-only mutation: intended, documented, and not true (ISSUE-003).
- Process-pool mode: intended, configurable, documented, and absent (ISSUE-004).
- Memory independence: approved and marked complete, while implementation/test evidence is linear in file count (ISSUE-005).
- Current handoff/ADR confirmation claims are stale or broader than their executable evidence (ISSUE-010).

## Fitness Functions And Enforcement

- present:
  - import-linter plus dynamic test fixture for transform purity.
  - strict Pydantic models plus hand-authored JSON Schemas and model/schema shape cross-checks.
  - requirement traceability checks.
  - extensive writer, resume, restore, containment, idempotency, and scale tests.
- missing:
  - full dependency-direction contract.
  - writer-only corpus mutation contract.
  - guarded-public-mutation-entrypoint contract.
  - accepted-config-key consumption contract.
  - consistent artifact version compatibility matrix.
  - convergent interruption tests for restore.
- assessment: Current fitness functions are high quality within their declared scope, but the scope is too narrow to enforce ADR-0002 as a whole.

## Transitional And Legacy Path Risks

- Historical same-major artifacts are intentionally accepted, but no single reader support matrix defines which inventory, plan, report, manifest, and frontmatter minors are supported.
- Future-minor rejection is implemented only for apply's plan input (ISSUE-006).
- No second old/new implementation path exists for the core pipeline; duplicate legacy engines are `not needed for this repo` and were not found.

## Enforcement And Testability Gaps

- Tests call unchecked write engines directly, so bypass is normal test architecture rather than an impossible state (ISSUE-001).
- Restore fault injection proves non-convergence but asserts collision as the expected result (ISSUE-003).
- The scale test proves one 100k-file point and a linear ceiling while traceability calls the independent-memory requirement complete (ISSUE-005).
- Parallel configuration tests prove parsing only, not behavior (ISSUE-004).
- Targeted review validation passed: `56 passed, 1 deselected`; passing tests therefore do not reduce the confidence of these boundary findings.

## Convention Recommendations

- Add a stable convention that all destructive workflows enter through a coordinator-owned application service; raw mutation primitives are private and never command/library entrypoints.
- Add a layer-direction map to `docs/handoff/conventions.md` only after the owner resolves the actual target shape: CLI -> application services -> domain/contracts -> writer adapters, with transform independent and writer not importing discovery.
- State that every accepted configuration key must either affect runtime behavior or fail validation as unsupported; no silent reserved/no-op operational settings.
- Define the artifact compatibility matrix and require every reader to enforce it before model construction or filesystem access.
- Define corpus mutation separately from tool-owned artifact/log/lock I/O so writer-isolation checks are precise.
- Existing Python tooling, Markdown tooling, public-fixture privacy, ADR, spec, and standard-owned-file conventions are sound and were followed by this review.

## Pass Log

| Pass | Lens | New issues | Result |
| --: | --- | --- | --- |
| 1 | System shape, entrypoints, layer boundaries, ADR intent, high-risk coupling | ISSUE-001, ISSUE-003 | Public mutation coordination and restore boundary drift identified. |
| 2 | Dependency direction, cross-cutting concerns, change amplification, fitness functions | ISSUE-002, ISSUE-006, ISSUE-007, ISSUE-009 | Artifact finalization/version gaps and transform duplication identified. |
| 3 | Domain modeling, configuration/integration boundaries, scaling, intended-vs-real documentation | ISSUE-004, ISSUE-005, ISSUE-010 | Parallelism, memory, and documentation drift identified. |
| 4 | Lower-severity maintainability, ergonomics, package organization, future-change hazards | ISSUE-008 | CLI cognitive-load hotspot identified; no category was skipped for early convergence. |
| 5 | Adaptive deepening: destructive callers, mutation call sites, schema-version consumers, fault tests | none | Existing inventory confirmed; no new issue. |
| 6 | Adaptive deepening: ADR confirmations, release baseline, config consumption, focused test validation | none | Second consecutive no-new-issue pass; review converged. |

## Claude Handoff

- highest_priority:
  1. Resolve ISSUE-001 before exposing any Python API, adding a new write command, or refactoring CLI orchestration.
  2. Resolve ISSUE-003 before strengthening restore/RPO claims or running unattended recovery workflows.
  3. Decide whether ADR-0007/NFR-001 are implementation requirements or approved-spec drift (ISSUE-004 and ISSUE-005) before further scale work.
- suggested_sequence:
  1. Record owner decisions/spec amendments for mutation coordination, restore convergence, parallelism, and the memory bound.
  2. Introduce guarded application services and move restore mutation into the writer boundary.
  3. Centralize transformation policy and artifact version enforcement.
  4. Add broader architecture fitness functions.
  5. Thin/split the CLI only after the service boundary is real.
- follow_on_reviews:
  - Product/business-logic review for restore interruption semantics and silent parallel settings.
  - Data-schema/migration review for artifact compatibility and duplicate-member handling.
  - Performance review for the chosen memory/concurrency target.
  - Comprehensive code review for filesystem TOCTOU and post-mutation error paths.
- change_control: The spec is approved and ADRs are accepted; architecture fixes that change behavior or accepted decisions must use the repository's spec/ADR process rather than silently editing implementation.

## Open Questions Or Assumptions

- Is `execute_plan`/`run_restore` intended as a supported Python API, or strictly internal? The risk remains because they are importable and are the normal engine-test surface.
- Does the owner accept O(file-count) metadata memory, or is NFR-001's size-independent memory requirement still binding?
- Should `parallel.enabled=true` work in v1.0.x, or should it be rejected until a post-v1 implementation exists?
- Must restore automatically resume after interruption, or is a safe superset plus manual collision resolution acceptable? Current runbook does not make that limitation explicit.
- Which historical artifact minors must each command support, and must older binaries always reject newer minors?
- The sibling `doc-proc-scripts` ADR and wrapper behavior were not available inside this repo and could not be verified.

## Residual Risk

- The review did not run the opt-in 100k scale test; it relied on checked-in code, assertions, and recorded measurements.
- The review did not inspect real library content or paths, consistent with the public-repository privacy boundary.
- The local trusted-user/POSIX threat model is assumed. If attacker-modifiable directories, multi-user hosts, network filesystems, removable media, or stronger power-loss durability are in scope, containment and mutation primitives need a dedicated security/filesystem review using the gaps already listed in shared research.
- External GitHub/PyPI settings and the private sibling repository are outside repo-verifiable evidence.
- No fixes were applied; all findings remain open pending owner triage.
