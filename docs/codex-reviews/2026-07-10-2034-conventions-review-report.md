# Conventions Review Report

## Review Metadata

- review_type: `conventions-review`
- review_date: `2026-07-10`
- repo_path: `.`
- repo_name: `docmend`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- working_tree_state: `dirty before review: modified AGENTS.md; untracked docs/codex-reviews/ orchestrator artifacts`
- review_mode: `read-only except this report`
- primary_conventions_input: `docs/handoff/conventions.md`
- equivalent_conventions_location_status: `valid repo-specific equivalent to docs/conventions.md; binding linkage is in AGENTS.md and the Agent Handoff fact-routing table`
- additional_conventions_inputs: `AGENTS.md; .project-standards.yml; .agents/skills/agent-handoff/SKILL.md; .agents/agent-handoff/manifest.json; README.md; docs/handoff/{architecture,deployed,specs-plans}.md; docs/adr/; docs/specs/docmend.md`
- detected_runtime: `Python >=3.14`
- detected_frameworks_and_libraries: `Typer; Rich; Pydantic; jsonschema Draft 2020-12; structlog; ruamel.yaml; charset-normalizer; pathspec`
- detected_package_and_build_tools: `uv; uv_build; uv.lock`
- detected_test_and_quality_tools: `pytest; Hypothesis; coverage.py; BasedPyright strict; Ruff; import-linter; pip-audit; markdownlint-cli2; Prettier`
- deployment_clues: `local single-user CLI; GitHub Actions CI; signed GitHub Release tags; sdist and wheel; no service deployment; no PyPI publication in v1`
- major_implementation_surfaces_sampled: `src/docmend/{cli,artifacts,observability,planning,discovery}.py; src/docmend/schemas/; src/docmend/writer/; tests for schemas, observability, transforms, apply, restore, resume, and scale`
- docs_ci_and_operational_surfaces_sampled: `README.md; docs/STATUS.md; docs/TODO.md; docs/handoff/; accepted ADRs 0002, 0005, 0011, 0015, 0016, 0017; .github/workflows/; .github/dependabot.yml; formatter/linter configs`
- shared_research_reused: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
- targeted_follow_up_research: `official Prettier installation guidance and official npm npx behavior only; no broad follow-up search`
- important_external_guidance_reviewed: `uv lock/sync guidance; PyPA packaging flow; pytest practices; pip-audit security model; JSON Schema 2020-12; filesystem safety references; OWASP logging; GitHub Actions secure-use guidance; Prettier installation guidance; npm npx guidance`
- prior_conventions_baseline: `no earlier conventions-review report found; latest conventions commit 377f1ab (2026-07-06), compared with Agent Handoff adoption commit 1657e2e (2026-07-10)`
- directly_verified: `repo files and history; conventions field/section shape; live source boundaries; CI commands; absence of package.json/package-lock.json; uv lock freshness; traceability script result`
- inferred: `likely maintenance impact of missing conventions; likelihood that agents consult the LLM-targeted conventions before deeper source comments`
- not_verifiable_from_repo: `external branch-protection state; GitHub Release settings; supported OS/filesystem matrix; actual corpus threat model; legal/regulatory scope; whether all contributors have globally cached npm tools`
- validation_results: `UV_CACHE_DIR=/tmp/docmend-review-uv-cache uv lock --check passed; UV_CACHE_DIR=/tmp/docmend-review-uv-cache uv run --locked python scripts/check_traceability.py passed; agent-handoff validate/drift-check could not run because the installed project-standards CLI lacks that subcommand`
- report_schema_resolution: `the referenced common report-schema.md describes review plans, not conventions child reports; this report follows the conventions-review workflow's required sections and issue fields`

## Convention Area Matrix

| Convention area | Relevance | Status | Evidence / issue IDs |
| --- | --- | --- | --- |
| `conventions-file-presence-and-location` | high | adequate | `docs/handoff/conventions.md` is the repo's declared stable-pattern owner. |
| `house-schema-and-agents-linkage` | high | partial | Correct AGENTS linkage; field/order defects and ownership drift: ISSUE-002, ISSUE-008. |
| `llm-consumability-and-scannability` | high | partial | Strong quick reference and labels; non-sequential body and missing examples: ISSUE-008. |
| `file-structure-and-schema-quality` | high | partial | Purpose/quick reference present; five entries omit canonical examples: ISSUE-008. |
| `stack-framework-alignment` | high | partial | Python stack is accurately represented; frontmatter and spec-profile guidance drift: ISSUE-001, ISSUE-005. |
| `language-tooling-alignment` | high | partial | Python tools match pyproject/CI; local lock check and Markdown tool pinning gaps: ISSUE-006, ISSUE-007. |
| `environment-and-deployment-fit` | medium | adequate | Local CLI/no service deployment is documented elsewhere; service/container conventions are not needed for this repo. |
| `developer-workflow-alignment` | high | partial | Code/Markdown gates are present; branch/release workflow is not indexed: ISSUE-009. |
| `testing-and-validation-conventions` | high | partial | Full Python gate and synthetic fixture rule exist; artifact compatibility validation is not indexed: ISSUE-003. |
| `security-and-secrets-conventions` | high | partial | Public-repo/fixture controls are strong; runtime diagnostic-data handling is omitted: ISSUE-004. |
| `observability-and-operations-conventions` | high | partial | Stable logging contract exists only in source/spec, not the conventions library: ISSUE-004. |
| `docs-and-handoff-conventions` | high | partial | Fact routing is strong; Agent Handoff ownership is stale in convention #8: ISSUE-002. |
| `cross-project-vs-repo-specific-balance` | high | adequate | Generic tooling defaults and repo-specific gotchas are distinguishable; recommended changes are classified below. |
| `coverage-and-gap-analysis` | high | partial | Missing schema, diagnostic privacy, and release workflow indexes: ISSUE-003, ISSUE-004, ISSUE-009. |
| `enforceability-and-drift-resistance` | high | partial | CI and test enforcement are substantial; local tool/version and ownership gaps remain: ISSUE-002, ISSUE-006, ISSUE-007. |
| `community-standards-alignment` | medium | partial | uv/pytest/packaging posture is mostly current; unpinned Prettier conflicts with official guidance: ISSUE-006. |
| `exceptions-and-rationale-quality` | high | adequate | Rules consistently include rationale and sources; Dependabot's standard-owned-workflow exception is scoped and explained. |

## Severity Summary

| Severity | Count | Issue IDs                                             |
| -------- | ----: | ----------------------------------------------------- |
| critical |     0 | none                                                  |
| high     |     0 | none                                                  |
| medium   |     5 | ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-004, ISSUE-006 |
| low      |     4 | ISSUE-005, ISSUE-007, ISSUE-008, ISSUE-009            |
| total    |     9 | ISSUE-001 through ISSUE-009                           |

## Findings

### ISSUE-001 — Product-frontmatter convention states behavior v1 does not implement

- first_pass: `2`
- severity: `medium`
- confidence: `high`
- convention_area: `stack-framework-alignment`
- issue_type: `stale-or-conflicting-guidance`
- evidence_class: `directly verified`
- remediation_class: `repo-specific exception`
- evidence:
  - `docs/handoff/conventions.md:156` says product frontmatter is emitted "into every converted document."
  - `.project-standards.yml:4-7` repeats the same unconditional-emission claim.
  - `src/docmend/cli.py:804-844` implements frontmatter validation only where present.
  - `docs/specs/docmend.md:844-846` says emission is a deferred seam and v1 validates existing frontmatter where present.
  - `src/docmend/schemas/README.md:11` says no command produces frontmatter in v1.
- impact: `An agent following the LLM-targeted convention can infer that every conversion must add metadata, a material behavior change for a destructive document tool. The binding spec corrects the error, but only after the convention has already supplied the wrong default.`
- recommendation: `Rewrite convention #7 to state that product and repo-doc frontmatter are separate systems, v1 emits none, and verify validates product frontmatter where present. Reconcile the stale .project-standards.yml comment and ADR-0011 language through their owner-approved workflows; do not hand-edit managed or standard-owned structure.`

### ISSUE-002 — Standard-ownership convention was not updated for Agent Handoff v1

- first_pass: `1`
- severity: `medium`
- confidence: `high`
- convention_area: `docs-and-handoff-conventions`
- issue_type: `stale-or-conflicting-guidance`
- evidence_class: `directly verified`
- remediation_class: `repo-specific exception and LLM-consumability rewrite`
- evidence:
  - `docs/handoff/conventions.md:165-175` lists standard-owned surfaces but omits `.agents/skills/agent-handoff/**`, `.agents/hooks/agent-handoff/session_start.py`, `.agents/agent-handoff/manifest.json`, and the exact managed blocks recorded in the manifest.
  - `.agents/skills/agent-handoff/SKILL.md:40-51` defines those ownership boundaries and says knowledge files under `docs/` are consumer-owned after creation.
  - `.agents/agent-handoff/manifest.json:9-17` identifies the exact installed files and managed blocks.
  - `.prettierignore:10-16` inaccurately says Agent Handoff owns `docs/STATUS.md` and `docs/TODO.md` and ignores whole AGENTS/CLAUDE files even though the standard owns only marked blocks there.
  - Git history shows Agent Handoff adoption on 2026-07-10, after the conventions file's last update on 2026-07-06.
- impact: `The incomplete ownership map can cause direct edits to managed artifacts or excessive avoidance of consumer-owned status/task content. Whole-file formatter exclusions also weaken the stated Markdown formatting contract outside the exact managed blocks.`
- recommendation: `Extend convention #8 with an explicit ownership table: exact standard-owned files, exact managed blocks, and consumer-owned docs/content. Correct formatter comments/exclusions only through the appropriate standard/adoption workflow, preserving managed byte contracts.`

### ISSUE-003 — Durable artifact schema evolution is not indexed as a contributor convention

- first_pass: `2`
- severity: `medium`
- confidence: `high`
- convention_area: `coverage-and-gap-analysis`
- issue_type: `missing-conventions`
- evidence_class: `directly verified`
- remediation_class: `repo-specific exception`
- evidence:
  - `src/docmend/schemas/README.md:1-23` defines hand-authored schemas as the durable external authority, backward-only compatibility, MAJOR.MINOR rules, version-bump steps, packaged-resource placement, and the prohibition on committing real run artifacts.
  - `docs/adr/adr-0005-durable-artifact-schema-contract.md` records the same compatibility-sensitive decision.
  - `docs/handoff/conventions.md` has no `Applies when` entry for changing inventory, plan, report, manifest, or frontmatter schemas/models.
  - Shared research recommends treating CLI artifacts and installed package data as versioned compatibility contracts with explicit upgrade/rejection behavior.
- impact: `A schema/model edit can pass ordinary lint and unit tests while still omitting a version bump, historical compatibility fixture, package-content check, or spec revision. These artifacts drive apply, resume, restore, and verify, so their evolution is a high-risk maintenance seam.`
- recommendation: `Add a concise convention triggered by any artifact/model/schema change. Point to ADR-0005 and the schema README; require authority direction, version/compatibility decision, historical fixtures, schema-model cross-checks, packaged-resource validation, and spec revision-history updates.`

### ISSUE-004 — Sensitive-data convention does not cover runtime diagnostics and artifacts

- first_pass: `3`
- severity: `medium`
- confidence: `medium`
- convention_area: `security-and-secrets-conventions`
- issue_type: `coverage-gap`
- evidence_class: `direct repo evidence plus unresolved threat-model assumptions`
- remediation_class: `durable cross-project default plus repo-specific exception`
- evidence:
  - `docs/handoff/conventions.md:124-136` protects committed files, fixtures, comments, docs, and future credentials, but does not apply when adding log events, exception fields, reports, manifests, backup metadata, or console output.
  - `src/docmend/observability.py:1-18` contains a caller-enforced contract: relative paths/hashes, no document body content, stable fields, stderr separation, and one run ID.
  - Source call sites emit `str(exc)` into `error` or `detail` fields; the repo convention gives no allowlist/redaction rule for exception text.
  - Shared research notes that paths, titles, snippets, low-entropy hashes, and raw exception text may identify a document or person and recommends allowlisted, sanitized diagnostic fields.
- impact: `The strongest runtime privacy contract is hidden in a module docstring rather than the LLM-targeted pattern library. A new event or error path can retain document content or private paths without violating convention #6 as written.`
- recommendation: `Add an observability/privacy convention triggered by any log, report, manifest, exception, or console-output change. Require stable event names and run IDs; relative/safe identifiers; no document bytes/snippets or raw secret/environment values; reviewed exception-field handling; control-character sanitization where output crosses line-oriented sinks; and focused tests. Do not claim a legal regime without owner confirmation.`

### ISSUE-005 — Spec workflow's canonical scaffold uses the wrong profile for this repo

- first_pass: `2`
- severity: `low`
- confidence: `high`
- convention_area: `stack-framework-alignment`
- issue_type: `convention-misalignment`
- evidence_class: `directly verified`
- remediation_class: `repo-specific exception`
- evidence:
  - `docs/handoff/conventions.md:73-85` applies to `docs/specs/docmend.md` but demonstrates `project-standards spec new ... --profile standard`.
  - `docs/specs/docmend.md:1-5` declares `profile: full`.
  - `AGENTS.md:13` and `.project-standards.yml:16-19` identify the binding spec as the full profile.
- impact: `The example is unlikely to affect routine prose edits, but it is not a canonical way to recreate or replace this repo's binding spec and could scaffold the wrong structure.`
- recommendation: `Use --profile full for a docmend scaffold example, or remove the unrelated spec new command from an edit/validate convention and label new-spec scaffolding separately.`

### ISSUE-006 — Markdown formatter commands resolve unpinned tools

- first_pass: `3`
- severity: `medium`
- confidence: `high`
- convention_area: `language-tooling-alignment`
- issue_type: `tooling-alignment-gap`
- evidence_class: `direct repo evidence plus current official guidance`
- remediation_class: `durable cross-project default`
- evidence:
  - `docs/handoff/conventions.md:53-63` runs bare `npx prettier` and `npx markdownlint-cli2`.
  - The repository has no `package.json` or npm lockfile, so those commands do not resolve repo-pinned local versions.
  - [Prettier's installation guide](https://prettier.io/docs/install.html) says to install an exact local version and warns that otherwise npx downloads the latest version, whose formatting may change between releases.
  - [npm's npx documentation](https://docs.npmjs.com/cli/commands/npx/) confirms missing local packages are installed into the npm cache for execution.
- impact: `Two agents can run the same convention at different times and receive different formatting behavior. This is especially risky for a repo with byte-exact fixtures, standard-owned files, and a local-only Prettier gate.`
- recommendation: `Fix the adopted Markdown Tooling Standard upstream or record an ADR-scoped repo exception that pins exact Prettier and markdownlint-cli2 versions through a committed tool manifest/lock. Do not silently hand-edit standard-owned configs to work around the standard.`

### ISSUE-007 — Local Python verification example does not explicitly prove lock freshness

- first_pass: `3`
- severity: `low`
- confidence: `high`
- convention_area: `enforceability-and-drift-resistance`
- issue_type: `tooling-alignment-gap`
- evidence_class: `directly verified`
- remediation_class: `durable cross-project default`
- evidence:
  - `docs/handoff/conventions.md:25-39` calls its six `uv run` commands the verification gate but does not use `--locked` or run `uv lock --check`/`uv sync --locked`.
  - `.github/workflows/check.yml:29-30` explicitly runs `uv sync --locked --all-groups` before checks.
  - `README.md:81-94` also puts `uv sync --locked --all-groups` at the start of the local gate.
  - Shared uv guidance distinguishes locked verification from commands that may refresh project state.
- impact: `The convention's local command block and the actual CI/local workflow are not identical. Dependency metadata drift can remain undiscovered until the PR gate, and the phrase "full verification gate" is ambiguous.`
- recommendation: `Prepend uv sync --locked --all-groups or use a supported locked/check equivalent, and say whether scripts/check.py mirrors only the Python CI job or the complete five-check repository gate.`

### ISSUE-008 — Body order and missing canonical examples violate the child workflow's house schema

- first_pass: `1`
- severity: `low`
- confidence: `high`
- convention_area: `llm-consumability-and-scannability`
- issue_type: `schema-structure-gap`
- evidence_class: `directly verified`
- remediation_class: `LLM-consumability rewrite`
- evidence:
  - The Quick Reference is sequential 1 through 9, but body section 9 appears before sections 7 and 8 at `docs/handoff/conventions.md:138-165`.
  - Sections 5, 6, 7, 8, and 9 omit the required `Code`/minimal canonical example field; an automated field inventory confirmed all other required labels are present.
  - The top-of-file purpose, complete Quick Reference, `Applies when`, `Rule`, `Why`, `Sources`, and `Related` coverage are otherwise strong.
- impact: `The file remains usable, but deterministic section lookup and automated extraction are weaker than the declared LLM-oriented contract.`
- recommendation: `Reorder sections physically to 1-9. Add a minimal canonical example or explicit Example: not applicable with the preferred command, file skeleton, or do/don't pair for every convention.`

### ISSUE-009 — Branch, integration, and release workflow is durable but absent from the LLM conventions index

- first_pass: `4`
- severity: `low`
- confidence: `high`
- convention_area: `developer-workflow-alignment`
- issue_type: `missing-conventions`
- evidence_class: `directly verified`
- remediation_class: `repo-specific exception`
- evidence:
  - `README.md:81-105`, `docs/handoff/deployed.md:5-20`, and ADR-0017 define the long-lived `dev` to merge-commit PR to protected `main` workflow, five required checks, signed tags, and GitHub Release path.
  - `docs/handoff/conventions.md` has no entry triggered by preparing a merge or release.
  - Current `docs/handoff/state.md` repeats the branch instruction, but eager session state is not the durable pattern owner.
- impact: `The workflow is discoverable to humans and through deployment handoff docs, but an LLM told to consult conventions before persistent actions does not get the stable integration/release pattern there.`
- recommendation: `Add a short convention that points to ADR-0017 and deployed.md, states dev-to-main merge-commit integration and the change-aware local gate, and treats signed release tags/workflow changes as deliberate release operations. Keep external branch-protection truth in deployed.md.`

## Conventions File Structure And LLM Fit

- overall_fit: `good foundation, targeted rewrite needed`
- top_of_file_purpose_and_usage_preamble: `present and concise`
- quick_reference_coverage: `complete for all nine current conventions`
- sequential_numbering: `IDs are unique and complete, but body order is 1,2,3,4,5,6,9,7,8`
- per_convention_field_fit: `all entries have Applies when, Rule, Why, Sources, and Related; entries 5-9 lack the required minimal canonical example field`
- scanability: `strong labels and compact quick-reference table; convention #9 is disproportionately long and should be reduced to a canonical rule plus focused examples`
- machine_extractability: `moderate; consistent bold labels help, but absent Example fields and non-sequential body order reduce deterministic parsing`
- rewrite_required: `yes, localized rather than full-file replacement`
- rewrite_scope: `reorder sections; add examples; shorten #9; update stale facts; add a small number of high-risk pattern entries`

## House Schema And Repo Contract Fit

- conventions_location_contract: `pass; docs/handoff/conventions.md is explicitly declared by AGENTS.md and Agent Handoff`
- agents_linkage: `pass; AGENTS.md:3-5 points directly to the conventions file and calls it LLM-targeted`
- adopted_standard_linkage: `pass with drift; conventions #1-#5 and #8 map to adopted standards, but #8 predates Agent Handoff v1 ownership`
- binding_spec_linkage: `pass; AGENTS.md and convention #3 require the approved spec`
- schema_field_contract: `partial; see ISSUE-008`
- managed_artifact_ownership_contract: `partial; see ISSUE-002`
- standard_owned_edit_constraint: `sound principle; remediation must use standard upgrade/adoption or ADR exception paths`

## Stack And Ecosystem Alignment

- python_and_uv: `well aligned with pyproject and CI; explicit locked local verification is missing (ISSUE-007)`
- lint_format_type_test: `Ruff, BasedPyright strict, pytest, and coverage match repo configuration`
- dependency_audit: `pip-audit convention matches CI; shared research correctly limits it to known advisory coverage, so it should not be described as the entire supply-chain posture`
- markdown_tooling: `tool roles match config, but execution versions are not reproducible (ISSUE-006)`
- typer_rich_cli: `no separate convention needed; binding CLI behavior lives in the spec and tests`
- pydantic_json_schema: `runtime use is aligned; schema evolution needs a contributor convention (ISSUE-003)`
- structlog: `implementation has a stable contract; convention coverage is missing (ISSUE-004)`
- frontmatter: `convention conflicts with implemented v1 behavior (ISSUE-001)`
- non_applicable_stack: `FastAPI, SQLAlchemy/Alembic, Svelte, databases, webhooks, background queues, hosted AI, Docker, systemd, and desktop installers are not live implementation surfaces; conventions for them are not needed for this repo`

## Environment And Workflow Fit

- runtime_environment: `local CLI; no dev/staging/prod service matrix, so service deployment conventions are not needed`
- filesystem_environment: `binding safety rules exist in spec/ADRs/tests; supported OS/filesystem/threat matrix remains unverified and should not be invented in conventions`
- branch_workflow: `documented outside conventions; see ISSUE-009`
- ci_workflow: `five repository checks are documented in deployed.md; convention #1 covers only the Python job and convention #2 the Markdown tools`
- release_workflow: `GitHub Release from signed tags; no PyPI in v1; absent from conventions index`
- fork_protection: `provided by higher-level agent instructions; no repo-specific fork exception was inferred`

## Coverage Gaps And Missing Conventions

- priority_1: `Artifact/schema evolution — ISSUE-003.`
- priority_2: `Runtime diagnostic privacy and event contract — ISSUE-004.`
- priority_3: `Agent Handoff ownership boundary — ISSUE-002.`
- priority_4: `Branch/integration/release pointer — ISSUE-009.`
- testing_note: `Do not duplicate the entire spec or ADR suite. New conventions should identify the trigger, invariant, authoritative source, canonical validation, and exception path.`
- not_needed_for_this_repo:
  - `web/API/auth conventions`
  - `database migration conventions`
  - `frontend state/UI conventions`
  - `queue/background-worker conventions`
  - `container/system-service deployment conventions`
  - `hosted AI/prompt execution conventions`

## Enforceability And Drift Risks

- strongly_enforced:
  - `Python format/lint/type/test/coverage/audit through CI`
  - `Markdown structure through reusable CI`
  - `spec validation and traceability`
  - `transform-layer purity through import-linter plus runtime test fixture`
  - `synthetic weird-corpus behavior through generator/tests and byte-exact exclusions`
- partially_enforced:
  - `Prettier is local-only and unpinned`
  - `fixture privacy includes an intentional human reviewer assertion`
  - `ADR frontmatter consistency is conventional, not CI-validated`
  - `Agent Handoff ownership relies on managed hashes/validation but the local convention is stale`
- drift_hotspots:
  - `frontmatter behavior prose across convention, .project-standards.yml comment, ADR-0011, spec, and implementation`
  - `schema/model/version/package-data edits`
  - `whole-file formatter exclusions around exact managed blocks`
  - `local gate versus CI lock verification`
- baseline_comparison: `The conventions file has not changed since 2026-07-06, while Agent Handoff v1 was adopted on 2026-07-10; ISSUE-002 is adoption-shaped drift.`

## Rewrite Recommendations

1. `Make a targeted rewrite, not a replacement: preserve the strong preamble, Quick Reference, numbered IDs, rationales, and sources.`
2. `Reorder the body to 1-9 and add an Example field to every entry.`
3. `Shorten convention #9 into one rule, a small invalid-to-valid mapping table, and its validation command.`
4. `Correct convention #7 to the implemented v1 frontmatter posture and route related ADR/comment reconciliation through controlled owners.`
5. `Expand convention #8 into an ownership table covering Project Standards files, Agent Handoff files, exact managed blocks, consumer-owned docs, and allowed additive repo-owned changes.`
6. `Add narrowly scoped entries for artifact compatibility and diagnostic privacy; link to existing ADR/spec/source contracts instead of copying them.`
7. `Add one branch/release pointer convention and one complete change-aware validation matrix rather than repeating partial gates in multiple entries.`
8. `Use repository-relative source links wherever possible so Claude can jump directly to the authority.`

## Convention Recommendations

### Durable Cross-Project Defaults

- `Pin exact local Markdown formatter/linter versions; bare npx without local dependencies is not reproducible.`
- `Require an explicit lock-freshness check in any gate described as equivalent to CI.`
- `For sensitive local-processing tools, make diagnostics/logs/artifacts part of the data-handling convention, not only committed fixtures.`
- `Keep every LLM convention in a stable labeled schema with a minimal canonical example.`

### Repo-Specific Exceptions

- `Product frontmatter: v1 validates where present and does not emit it; repo-doc frontmatter remains a separate, deliberately unvalidated system.`
- `Artifact contracts: hand-authored schemas are authoritative, backward-only, packaged resources; schema/model changes require compatibility work.`
- `Agent Handoff: exact installed files and exact managed blocks are standard-owned; STATUS/TODO and other knowledge content remain consumer-owned.`
- `Integration: dev advances main by merge-commit PR; releases are signed tags to GitHub Releases; PyPI is out of scope for v1.`

### LLM-Consumability Rewrites

- `Restore physical section order.`
- `Add Example fields to conventions 5-9.`
- `Replace long prose in #9 and #8 with small decision tables.`
- `Add trigger-oriented Quick Reference rows for schema changes, diagnostics, and release preparation.`

## Pass Log

| Pass | Lens | New issues | Result |
| --: | --- | --- | --- |
| 1 | Presence, discoverability, house schema, LLM fit, high-risk hotspots | ISSUE-002, ISSUE-008 | Equivalent file and linkage valid; ownership and shape defects found. |
| 2 | Stack/tool alignment, code-to-convention alignment, stale/conflicting guidance | ISSUE-001, ISSUE-003, ISSUE-005 | Frontmatter drift, missing schema-change convention, wrong spec profile example. |
| 3 | Workflow coverage, enforceability, rationale consistency, current ecosystem guidance | ISSUE-004, ISSUE-006, ISSUE-007 | Diagnostic privacy, unpinned Markdown tools, lock-check mismatch. |
| 4 | Lower-severity gaps, duplication, repo tailoring, rewrite quality | ISSUE-009 | Durable branch/release workflow absent from LLM conventions. |
| 5 | Adaptive deepening: history baseline, references, field inventory, non-applicable stack | none | No new issues; existing findings strengthened. |
| 6 | Convergence: adversarial re-check of findings and area matrix | none | Second consecutive pass with no new issues; review converged. |

## Claude Handoff

- recommended_order:
  1. `Resolve ISSUE-001 first because it is a product-behavior contradiction; reconcile convention, standard comment, ADR, and spec intentionally.`
  2. `Resolve ISSUE-002 through Agent Handoff-aware ownership changes, not direct edits to managed artifacts.`
  3. `Add ISSUE-003 and ISSUE-004 as concise high-risk conventions with links to existing authorities and tests.`
  4. `Route ISSUE-006 and ISSUE-007 to the adopted standards upstream or document an ADR exception before changing standard-owned tooling.`
  5. `Apply the low-risk structural rewrite and workflow pointer after substantive rules settle.`
- likely_files_for_owner_approved_fix: `docs/handoff/conventions.md; .project-standards.yml comment through its allowed workflow; docs/adr/adr-0011-frontmatter-optional-minimal-split.md; possibly .prettierignore through standards/adoption reconciliation; upstream Project Standards Markdown/Python tooling bundles`
- follow_on_reviews:
  - `documentation-and-runbook-review for the cross-document frontmatter contradiction and branch/release discoverability`
  - `observability-review for exception payloads, redaction, control characters, and retention`
  - `api-contract or data-schema-migration review for historical artifact compatibility`
  - `ci-cd review for tool pinning, full-SHA action posture, and exact release-artifact validation`
- do_not_do: `Do not hand-edit standard-owned files or orchestrator execution artifacts; do not duplicate the binding spec into conventions; do not infer a legal compliance regime.`
- acceptance_checks_for_a_fix:
  - `Quick Reference and body IDs match and are sequential.`
  - `Every convention has Applies when, Rule, Example, Why, Sources, and Related.`
  - `Frontmatter statements match source and spec.`
  - `Agent Handoff validate/drift-check pass with a CLI version that supports the adopted standard.`
  - `Markdown and spec/traceability validation pass.`
  - `Git diff confirms only intended consumer content or managed updates produced by the owning tool changed.`

## Open Questions Or Assumptions

- `Does the owner want artifact/schema and diagnostic/privacy rules in the central conventions file, or only indexed there with details remaining in schema README/spec/source? This review recommends the latter.`
- `Should Prettier/markdownlint pinning be fixed in project-standards v4 upstream or accepted as a repo-local ADR exception? The standard-owned-file rule makes upstream the default.`
- `ADR-0011 says optional v1 emission exists, while the approved spec traceability and implementation say emission is deferred. Which document should be amended or superseded is an owner/change-control decision.`
- `The repo does not establish whether corpus directories are trusted single-user trees or attacker-modifiable/shared trees; conventions should not strengthen or weaken filesystem guarantees until that threat model is settled.`
- `External branch protection and release settings were not queried; repo documentation was treated as declared truth, not independently verified external state.`
- `Agent Handoff validation was not executable with the installed project-standards CLI in this environment; the checked-in skill and manifest were reviewed directly.`

## Residual Risk

- overall: `moderate conventions risk; low evidence of immediate runtime failure`
- after_report_only: `All nine issues remain open because this task authorized review/reporting, not fixes.`
- highest_residual: `An agent can still receive incorrect frontmatter behavior and incomplete managed-file ownership from the primary LLM conventions file.`
- external_unknowns: `Threat model, filesystem support, legal scope, branch-protection settings, and historical artifact compatibility corpus remain unverified.`
- false_positive_control: `No web, database, frontend, queue, remote API, hosted AI, container, systemd, or service-deployment conventions were recommended because those are not live repo surfaces.`
