# Codex Review Orchestrator Plan

## Review Orchestrator Metadata

- repo_root: .
- repo_name: docmend
- mode: exhaustive
- budget: deep
- scope: .
- current_branch: dev
- head_commit: ad8a899f5e718a1530f387093badfdf2eae3e2da
- working_tree_state: dirty
- execution_profile_used: review-sweep
- search_enabled: True
- codex_cli_mode: exec
- orchestrator_version: stage2

## Repo Scan Summary

- primary_repo_pattern: document-centric-sensitive-data
- secondary_repo_patterns: sensitive-fastapi-internal-tool, library-cli-tooling, retrieval-knowledge-base
- language_signals: python
- framework_signals: ai-workflow, alembic, async-jobs, observability, pytest, sqlalchemy, svelte
- behavior_signals: admin-surface, authentication, authorization, cli-tooling, webhooks
- artifact_signals: adrs, conventions-doc, github-actions, tests
- sensitivity_signals: financial-data, legal-estate-data, medical-data, personal-data
- deployment_signals: docker, github-actions, systemd
- packaging_signals: desktop-installer
- nested_repo_signals: none
- existing_review_artifacts: codex-reviews
- unknowns_that_reduce_confidence: none

## Repo Pattern Classification

- primary_repo_pattern: document-centric-sensitive-data
- secondary_repo_patterns: sensitive-fastapi-internal-tool, library-cli-tooling, retrieval-knowledge-base

## Framework And Artifact Signals

- framework_evidence: `{"ai-workflow": ["docs/research/unicode-normalization-policy.md", ".agents/agent-handoff/manifest.json"], "alembic": ["docs/research/restore-from-manifest-design.md"], "async-jobs": ["AGENTS.md", "docs/resolved-questions.md", "docs/open-questions.md", "docs/deep-research-queue.md", "docs/specs/docmend.md", "docs/research/backup-integrity-verification.md", "docs/handoff/conventions.md", "docs/handoff/specs-plans.md"], "observability": ["uv.lock", "pyproject.toml", "docs/gap-analysis.md", "docs/resolved-questions.md", "docs/dependency-licenses.md", "docs/specs/docmend.md", "docs/research/python-library-research.md", "docs/research/structured-logging-library.md"], "pytest": ["uv.lock", "pyproject.toml", "README.md", "docs/gap-analysis.md", "docs/dependency-licenses.md", "docs/repo-hygiene.md", "docs/specs/docmend.md", "docs/research/license-compliance-tooling.md"], "sqlalchemy": ["docs/research/restore-from-manifest-design.md"], "svelte": ["docs/gap-analysis.md", "docs/adr/adr-0016-mechanical-transform-boundary.md"]}`
- behavior_evidence: `{"admin-surface": ["docs/specs/docmend.md", "docs/research/self-hosted-corpus-storage-options.md", "docs/research/atomic-write-filesystem-semantics.md", "docs/research/docmend-backup-medium-durability-and-throughput-research.md", "docs/adr/adr-0017-branch-and-ci-cd-workflow.md", ".superpowers/sdd/task-13-brief.md"], "authentication": ["AGENTS.md", "docs/gap-analysis.md", "docs/resolved-questions.md", "docs/repo-hygiene.md", "docs/TODO.md", "docs/specs/docmend.md", "docs/research/synthetic-corpus-generation.md", "docs/research/atomic-write-filesystem-semantics.md"], "authorization": ["docs/gap-analysis.md", "docs/specs/docmend.md", "docs/research/self-hosted-corpus-storage-options.md", "docs/research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md", "docs/research/path-containment-toctou.md", "docs/research/python-314-wheel-readiness.md", "docs/research/synthetic-corpus-generation.md", "docs/research/python-library-research.md"], "cli-tooling": [".markdownlint.json", "uv.lock", "pyproject.toml", "docs/gap-analysis.md", "docs/dependency-licenses.md", "docs/deep-research-queue.md", "docs/specs/docmend.md", "docs/research/python-314-wheel-readiness.md"], "webhooks": ["docs/specs/docmend.md", "docs/research/combinatorial-safety-gate-testing.md"]}`
- artifact_evidence: `{"adrs": ["docs/adr/adr-0001-no-markdown-frontmatter-standard.md", "docs/adr/adr.template.md", "docs/adr/README.md", "docs/adr/adr-0011-frontmatter-optional-minimal-split.md", "docs/adr/adr-0012-verify-semantics-exit-code-taxonomy.md", "docs/adr/adr-0008-stable-document-identity.md", "docs/adr/adr-0010-pluggable-policy-seams.md", "docs/adr/adr-0014-tool-first-product-scope.md"], "conventions-doc": ["docs/handoff/conventions.md"], "github-actions": [".github/workflows/lint-markdown.yml", ".github/workflows/validate-specs.yml", ".github/workflows/check.yml", ".github/workflows/traceability.yml", ".github/workflows/dependency-review.yml", ".github/workflows/release.yml"], "tests": ["tests/test_smoke.py", "tests/test_check_traceability.py", "tests/test_cli.py", "tests/test_observability.py", "tests/test_import_contracts.py", "tests/conftest.py", "tests/corpus.py", "tests/test_detection.py"]}`

## Conventions Inputs

- conventions_inputs_found: docs/handoff/conventions.md
- conventions_maturity: present
- likely_convention_heavy_reviews: conventions-review, architecture-boundary-review, api-contract-review, observability-review, test-suite-review, ci-cd-review
- missing_conventions_hotspots: none

## Available And Missing Review Skills

- available_review_skills: ai-and-prompt-workflow-review, api-contract-review, architecture-boundary-review, background-jobs-and-async-workflow-review, ci-cd-review, comprehensive-code-review, conventions-review, data-schema-migration-review, dependency-supply-chain-review, desktop-packaging-review, documentation-and-runbook-review, frontend-state-and-interaction-review, incident-readiness-review, integration-and-third-party-boundary-review, mcp-and-agent-tool-boundary-review, observability-review, performance-review, product-and-business-logic-review, release-readiness-review, retrieval-and-knowledge-base-review, shell-and-automation-script-review, test-suite-review
- missing_review_skills: none

## Run Now

### ci-cd-review

- canonical_prompt: `perform a CI review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `delivery-and-runtime`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: CI workflow artifacts
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### observability-review

- canonical_prompt: `perform an observability review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `delivery-and-runtime`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: telemetry or logging signals
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### data-schema-migration-review

- canonical_prompt: `perform a data review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `state-data-and-workflow`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: schema or migration evidence
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### release-readiness-review

- canonical_prompt: `perform a release readiness review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `delivery-and-runtime`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: delivery or packaging surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### product-and-business-logic-review

- canonical_prompt: `perform a product logic review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `repo-shape-and-intent`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: domain or workflow logic surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### background-jobs-and-async-workflow-review

- canonical_prompt: `perform an async workflow review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `state-data-and-workflow`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: background jobs or schedulers detected
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### test-suite-review

- canonical_prompt: `perform a test review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `broad-integrative`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: test files and tooling detected
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### incident-readiness-review

- canonical_prompt: `perform an incident readiness review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `delivery-and-runtime`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: runtime operations surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### ai-and-prompt-workflow-review

- canonical_prompt: `perform an AI workflow review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `contract-and-integration`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: AI or prompt workflow surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### documentation-and-runbook-review

- canonical_prompt: `perform a documentation review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `repo-shape-and-intent`
- why_selected_or_skipped: document-centric sensitive-data repo-pattern boost
- key_signals: documentation surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### dependency-supply-chain-review

- canonical_prompt: `perform a dependency review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `boundary-and-trust`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: dependency manifest surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### integration-and-third-party-boundary-review

- canonical_prompt: `perform an integration review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `contract-and-integration`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: external integration surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### conventions-review

- canonical_prompt: `perform a conventions review`
- applicable: `yes`
- expected_value: `critical`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `repo-shape-and-intent`
- why_selected_or_skipped: repo has enough implementation and docs surface to justify conventions-fit review even without a current conventions file
- key_signals: conventions input detected
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### performance-review

- canonical_prompt: `perform a performance review`
- applicable: `yes`
- expected_value: `high`
- confidence: `high`
- run_recommendation: `run_now`
- default_execution_group: `delivery-and-runtime`
- why_selected_or_skipped: Selected from weighted repo evidence.
- key_signals: runtime or UI performance surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### api-contract-review

- canonical_prompt: `perform an API contract review`
- applicable: `yes`
- expected_value: `medium`
- confidence: `medium`
- run_recommendation: `run_now`
- default_execution_group: `contract-and-integration`
- why_selected_or_skipped: Selected from weighted repo evidence. Deep budget promoted this review.
- key_signals: contract artifacts or endpoint surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### frontend-state-and-interaction-review

- canonical_prompt: `perform a frontend state review`
- applicable: `yes`
- expected_value: `medium`
- confidence: `medium`
- run_recommendation: `run_now`
- default_execution_group: `state-data-and-workflow`
- why_selected_or_skipped: Selected from weighted repo evidence. Deep budget promoted this review.
- key_signals: interactive UI surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### architecture-boundary-review

- canonical_prompt: `perform an architecture review`
- applicable: `maybe`
- expected_value: `low`
- confidence: `low`
- run_recommendation: `run_now`
- default_execution_group: `repo-shape-and-intent`
- why_selected_or_skipped: Selected from weighted repo evidence. Deep budget promoted this review.
- key_signals: meaningful implementation surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### comprehensive-code-review

- canonical_prompt: `perform a code review`
- applicable: `maybe`
- expected_value: `low`
- confidence: `low`
- run_recommendation: `run_now`
- default_execution_group: `broad-integrative`
- why_selected_or_skipped: Selected from weighted repo evidence. Deep budget promoted this review.
- key_signals: meaningful implementation surface
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

## Consider Next

## Not Applicable

### mcp-and-agent-tool-boundary-review

- canonical_prompt: `perform an MCP review`
- applicable: `no`
- expected_value: `low`
- confidence: `high`
- run_recommendation: `skip_now`
- default_execution_group: `contract-and-integration`
- why_selected_or_skipped: No MCP or tool-boundary surface was detected.
- key_signals: none recorded
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### retrieval-and-knowledge-base-review

- canonical_prompt: `perform a retrieval review`
- applicable: `no`
- expected_value: `low`
- confidence: `high`
- run_recommendation: `skip_now`
- default_execution_group: `contract-and-integration`
- why_selected_or_skipped: No retrieval or knowledge-base surface was detected.
- key_signals: none recorded
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### desktop-packaging-review

- canonical_prompt: `perform a desktop packaging review`
- applicable: `no`
- expected_value: `low`
- confidence: `high`
- run_recommendation: `skip_now`
- default_execution_group: `delivery-and-runtime`
- why_selected_or_skipped: No desktop packaging surface was detected.
- key_signals: none recorded
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

### shell-and-automation-script-review

- canonical_prompt: `perform a shell automation review`
- applicable: `no`
- expected_value: `low`
- confidence: `high`
- run_recommendation: `skip_now`
- default_execution_group: `delivery-and-runtime`
- why_selected_or_skipped: No meaningful shell automation surface was detected.
- key_signals: none recorded
- blocking_unknowns: none
- latest_existing_report: docs/codex-reviews/2026-07-10-2034-codex-review-live-status.md

## Execution Order

- 1. `conventions-review`: repo-shape-and-intent / critical
- 2. `documentation-and-runbook-review`: repo-shape-and-intent / critical
- 3. `product-and-business-logic-review`: repo-shape-and-intent / critical
- 4. `architecture-boundary-review`: repo-shape-and-intent / low
- 5. `dependency-supply-chain-review`: boundary-and-trust / critical
- 6. `ai-and-prompt-workflow-review`: contract-and-integration / critical
- 7. `integration-and-third-party-boundary-review`: contract-and-integration / critical
- 8. `api-contract-review`: contract-and-integration / medium
- 9. `background-jobs-and-async-workflow-review`: state-data-and-workflow / critical
- 10. `data-schema-migration-review`: state-data-and-workflow / critical
- 11. `frontend-state-and-interaction-review`: state-data-and-workflow / medium
- 12. `ci-cd-review`: delivery-and-runtime / critical
- 13. `incident-readiness-review`: delivery-and-runtime / critical
- 14. `observability-review`: delivery-and-runtime / critical
- 15. `release-readiness-review`: delivery-and-runtime / critical
- 16. `performance-review`: delivery-and-runtime / high
- 17. `test-suite-review`: broad-integrative / critical
- 18. `comprehensive-code-review`: broad-integrative / low

## Planning Risks And Unknowns

- missing_evidence_that_could_change_prioritization: Sweep execution relies on non-interactive child Codex runs and will save a durable JSON manifest.
- environment_limitations: none recorded
- search_or_profile_limitations: execution profile `review-sweep` with search_enabled=True

## Claude Handoff

- highest_value_reviews_to_run_first: conventions-review, documentation-and-runbook-review, product-and-business-logic-review
- reviews_likely_to_change_conventions: conventions-review, architecture-boundary-review, api-contract-review, observability-review, test-suite-review, ci-cd-review
- reviews_to_revisit_after_major_changes: none
- follow_up_questions_for_human_if_needed: none
