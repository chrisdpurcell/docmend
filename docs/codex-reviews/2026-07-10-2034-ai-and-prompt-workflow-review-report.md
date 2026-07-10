# AI And Prompt Workflow Review

## Findings

### ISSUE-001 — Consistency prompt can reverse owner decisions without an approval boundary

- first_pass: 1
- severity: high
- confidence: high
- ai_workflow_area: tool-use-and-boundaries
- issue_type: tool-boundary-gap
- evidence_basis: verified directly from repository evidence
- affected_surfaces:
  - `docs/prompts/prompt-consistency-workflow.md:5-14`
  - `docs/prompts/prompt-consistency-workflow.md:20-24`
  - `docs/specs/docmend.md:67-72`
  - `docs/specs/docmend.md:1168-1196`
  - `docs/open-questions.md:24-40`
- evidence:
  - The reusable prompt directs an agent to downgrade resolved questions and relocate them when the agent finds an inconsistency.
  - Resolved questions are settled decisions, owner comments are protected from agent edits, and the approved specification is change-controlled.
  - The prompt does not require owner confirmation before reopening a decision, does not distinguish a mechanical drift repair from a decision change, and omits the specification revision, validation, traceability, and deviation gates.
- impact: Running the prompt as written can turn an AI interpretation of ambiguity into a write to binding requirements or settled owner intent. Git and interactive tool permissions reduce blast radius but do not make the workflow fail closed.
- recommendation:
  - Make the workflow analysis-only until the owner approves each decision-bearing change.
  - Require contradictions to be reported with evidence and classified as mechanical drift, underspecification, or genuine decision conflict.
  - Permit agents to propose a new `OQ-` entry, but never move or rewrite an `RQ-` or scope-affecting spec text without explicit owner approval.
  - Bind every approved edit to the spec revision row, applicable `DEV-`/`OQ-`, traceability update, and repository validation commands.
- verification:
  - Dry-run the revised prompt against a synthetic settled-decision conflict and verify that it emits a proposal without editing the spec, ADRs, or question registers.

### ISSUE-002 — Web research is not isolated from write-capable canonical-document work

- first_pass: 3
- severity: medium
- confidence: medium
- ai_workflow_area: prompt-injection-and-untrusted-input
- issue_type: prompt-injection-gap
- evidence_basis: direct repository evidence plus current provider guidance; actual external `/qdev:research` and permission configuration could not be verified
- affected_surfaces:
  - `docs/prompts/prompt-gap-analysis-workflow.md:9-14`
  - `docs/prompts/prompt-consistency-workflow.md:20-30`
  - `.claude/settings.json:1-17`
- evidence:
  - Both workflows combine internet research or research subagents with writes to canonical repository documents.
  - Neither prompt labels retrieved content as untrusted, restricts researcher tools to read-only access, requires source-claim verification before edits, or inserts a human approval handoff between research and mutation.
  - Claude subagents inherit the main conversation's tools by default unless restricted; current guidance supports explicit tool allowlists and warns against feeding untrusted content directly into a write-capable workflow.
- impact: A malicious or merely misleading source can influence the same agent context that edits specifications, ADRs, and decision records. Provider defenses and permission prompts are compensating controls, not repository-enforced workflow boundaries.
- recommendation:
  - Run web research in read-only subagents with explicit tool allowlists and no edit, write, or privileged MCP tools.
  - Treat fetched pages as quoted evidence, never instructions; prefer primary sources and independently verify claims that can change binding behavior.
  - Require the main thread to synthesize a cited proposal and stop for approval before any decision-bearing write.
  - Keep network and write permissions separate for non-interactive executions.
- verification:
  - Inject a synthetic hostile instruction into a local research fixture and confirm it is reported as untrusted content, cannot invoke tools, and cannot alter repository files.
- current_guidance:
  - [Claude Code security](https://code.claude.com/docs/en/security)
  - [Claude Code subagents and tool restrictions](https://code.claude.com/docs/en/sub-agents)
  - [OWASP LLM01: Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)

### ISSUE-003 — Static prompts have a stale and undeclared execution contract

- first_pass: 1
- severity: low
- confidence: medium
- ai_workflow_area: model-and-prompt-drift-management
- issue_type: model-prompt-drift-gap
- evidence_basis: repository paths and missing definitions verified directly; user-level plugins and provider settings were not available in the repository
- affected_surfaces:
  - `docs/prompts/prompt-gap-analysis-workflow.md:9-23`
  - `docs/prompts/prompt-consistency-workflow.md:20-45`
  - `docs/gap-analysis.md:669-675`
- evidence:
  - Relative links beginning with `docs/` resolve under `docs/prompts/docs/` and are broken from both prompt files.
  - The gap-analysis prompt names nonexistent `docs/research-reports/` and `docs/decisions/`; the canonical locations are `docs/research/` and `docs/adr/`.
  - `/qdev:research` has no repo-local definition or declared plugin prerequisite.
  - The prompts route work by mutable `Sonnet`/`Opus` aliases and name `Fable` without recording provider, model resolution, minimum Claude Code version, capability assumptions, or fallback behavior.
  - The bad research-output path was already recorded as GAP-68 but remains in the live prompt.
- impact: A new operator cannot reproduce the workflow from the repository alone; a run can fail, write to the wrong location, or change behavior as aliases and user plugins drift.
- recommendation:
  - Either mark the prompts historical/retired or add a small execution header with status, supported harness, required plugin/skill, tested CLI version, model policy, fallback, and repository-root path semantics.
  - Fix all links and destinations, and prefer capability/effort routing over provider marketing names where exact model identity is not a requirement.
  - If aliases remain intentional, record that they float and capture their resolved model IDs in each run artifact.
- verification:
  - Run a repository link check from each prompt's directory and a clean-profile dry run with no user-level plugins.
- current_guidance:
  - [Claude Code model configuration](https://code.claude.com/docs/en/model-config)

### ISSUE-004 — Prompt and generated-research provenance is insufficient for replay

- first_pass: 5
- severity: low
- confidence: medium
- ai_workflow_area: prompt-artifact-governance
- issue_type: convention-quality
- evidence_basis: direct repository evidence; original ChatGPT execution metadata and human verification records were not available
- affected_surfaces:
  - `docs/prompts/prompt-gap-analysis-workflow.md`
  - `docs/prompts/prompt-consistency-workflow.md`
  - `docs/deep-research-queue.md:47-60`
  - `docs/research/charset-detection-floors-for-legacy-text-ingestion.md:1-11`
  - `docs/research/docmend-and-the-free-threaded-cpython-switch-decision.md:1-13`
  - `docs/handoff/conventions.md`
- evidence:
  - Git preserves prompt history, and the deep-research queue commendably preserves the exact prompts, status, output links, and reconciliation notes.
  - The reusable workflow prompts do not declare owner, lifecycle state, version, last-tested date, expected inputs/outputs, or acceptance checks.
  - Imported ChatGPT reports record a date and sources but not provider/model ID, execution settings, source snapshot, review status, or claim-level verification.
  - The conventions library has no durable rule for development-time AI prompts or AI-generated research artifacts.
- impact: Later agents cannot tell whether a prompt is current, reproduce model-sensitive output, or distinguish model-generated claims from independently verified conclusions.
- recommendation:
  - Add lightweight metadata to reusable prompts and imported AI research: owner, status, prompt version/hash, provider/model, execution date, tool/search mode, source cutoff, reviewer, verification state, and canonical reconciliation target.
  - Add a convention requiring primary-source verification before AI research changes a binding decision.
- verification:
  - Select one historical prompt/output pair and confirm a reviewer can identify the exact prompt, resolved model, source set, review decision, and downstream changes.

### ISSUE-005 — Absolute-success wording has no incomplete or uncertainty outcome

- first_pass: 2
- severity: low
- confidence: high
- ai_workflow_area: hallucination-containment-and-fail-safe-behavior
- issue_type: hallucination-fail-safe-gap
- evidence_basis: verified directly from repository evidence
- affected_surfaces:
  - `docs/prompts/prompt-consistency-workflow.md:8-14`
  - `docs/prompts/prompt-gap-analysis-workflow.md:5-15`
- evidence:
  - The prompts demand comprehensive coverage, 100% consistency, zero contradictions, and recommendations for each gap.
  - They do not define `unknown`, `not verified`, `blocked`, or `no safe change` outcomes; they also lack evidence-quality and confidence fields.
- impact: The workflow rewards a false completeness claim or speculative edit when evidence is unavailable, contradictory, or outside the repository.
- recommendation:
  - Require explicit verified, inferred, unknown, and blocked states.
  - Define completion as inspected scope plus residual unknowns, not 100% certainty.
  - Require evidence and confidence for each proposed contradiction or gap.
- verification:
  - Dry-run against an intentionally missing external dependency and confirm the result is `blocked/unverified`, with no fabricated conclusion or edit.

### ISSUE-006 — Agent fan-out has no cost, latency, or convergence bound

- first_pass: 4
- severity: low
- confidence: high
- ai_workflow_area: cost-latency-and-rate-limit-strategy
- issue_type: cost-latency-rate-limit-gap
- evidence_basis: verified directly from repository evidence
- affected_surfaces:
  - `docs/prompts/prompt-consistency-workflow.md:18-24`
  - `docs/prompts/prompt-gap-analysis-workflow.md:9-13`
  - `docs/handoff/sessions/2026-07.md:8-11`
- evidence:
  - One prompt says to use as many subagents as needed; neither defines a maximum, concurrency bound, research budget, timeout, early-stop rule, or convergence test.
  - The historical gap-analysis run used 36 agents and then four separate ChatGPT Deep-Research jobs.
- impact: Re-running a broad prompt can consume unpredictable time and model spend and may duplicate research without improving decision quality.
- recommendation:
  - Add a bounded planning phase, worker cap, evidence reuse requirement, per-topic budget, and two-no-new-issues convergence rule.
  - Require an operator checkpoint before paid or external deep research.
- verification:
  - Confirm the workflow stops at its declared cap and reports deferred topics rather than silently expanding the run.

### ISSUE-007 — Future semantic-enrichment ownership conflicts across binding documents

- first_pass: 3
- severity: low
- confidence: medium
- ai_workflow_area: documentation-and-operator-ergonomics
- issue_type: operator-docs-gap
- evidence_basis: direct text conflict; intended supersession relationship is inferred
- affected_surfaces:
  - `docs/specs/docmend.md:220-233`
  - `docs/specs/docmend.md:535-548`
  - `docs/adr/adr-0018-doc-processing-repository-boundary.md:62-92`
- evidence:
  - The approved spec lists WH-006 semantic enrichment as a deferred docmend capability, including inference/external assistance.
  - ADR-0018 says docmend does not own metadata/frontmatter enrichment beyond current behavior, while the sibling repository also does not own automatic enrichment without an accepted design.
- impact: No current runtime is affected, but a future AI/enrichment proposal has no unambiguous component owner and can be routed into either repository inconsistently.
- recommendation:
  - Reconcile WH-006 and ADR-0018 before any enrichment design begins. State whether the ADR supersedes the deferred capability, or define the approval event that transfers ownership back into docmend.
- verification:
  - A future implementer should be able to answer component ownership from one canonical pointer without interpreting conflicting documents.

### ISSUE-008 — Frontmatter convention overstates automated emission

- first_pass: 2
- severity: low
- confidence: high
- ai_workflow_area: documentation-and-operator-ergonomics
- issue_type: convention-misalignment
- evidence_basis: verified directly from repository evidence
- affected_surfaces:
  - `docs/handoff/conventions.md:150-161`
  - `docs/specs/docmend.md:527-548`
  - `README.md:29-31`
- evidence:
  - Convention 7 says docmend emits product frontmatter into every converted document.
  - The approved spec says emission is optional, and the README says v1 emits none.
- impact: An agent designing future inference or enrichment can assume a universal metadata write path that the product contract explicitly does not have.
- recommendation:
  - Change the convention to say product frontmatter is the schema docmend validates and may emit when enabled; v1 emits none and a document without frontmatter is legal.
- verification:
  - Cross-check the revised wording against the spec, README, and ADR-0011.

## Review Metadata

- repo_path: `.`
- repo_name: `docmend`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- worktree_state: dirty before review; pre-existing `AGENTS.md` modification and untracked `docs/codex-reviews/` sweep artifacts
- report_path: `docs/codex-reviews/2026-07-10-2034-ai-and-prompt-workflow-review-report.md`
- review_mode: read-only review plus requested report write
- detected_product_model_providers: none
- detected_product_orchestration_frameworks: none
- detected_development_ai_surfaces:
  - Claude Code static workflow prompts
  - ChatGPT Deep-Research prompt queue and imported reports
  - shared Claude/Codex SessionStart context hook
- model_versions_and_provider_assumptions:
  - static prompts name mutable Sonnet/Opus aliases
  - actual historical resolved model IDs are not recorded
  - `/qdev:research` is assumed to be an external/user-level asset, not verified
- prompt_tool_and_routing_surfaces_inspected:
  - `docs/prompts/`
  - `docs/deep-research-queue.md`
  - `.claude/settings.json`
  - `.codex/config.toml`
  - `.agents/hooks/agent-handoff/session_start.py`
  - `.agents/skills/agent-handoff/`
- prompt_artifact_and_versioning_surfaces_inspected:
  - Git history for both reusable prompts
  - four reconciled ChatGPT Deep-Research prompts and reports
  - `docs/gap-analysis.md`
  - `docs/handoff/sessions/2026-07.md`
- structured_output_and_validation_surfaces_inspected:
  - product Pydantic/JSON Schema artifacts were verified as deterministic, non-AI output
  - development AI outputs are prose Markdown and are not machine-consumed
- external_assets_not_in_repo:
  - `/qdev:research` implementation and configuration
  - user/organization Claude permission policy and model alias resolution at run time
  - ChatGPT Deep-Research model IDs, settings, and original execution traces
- runtime_or_production_usage_unknowns:
  - whether the two static prompts are still active or historical
  - whether prompt executions always received human diff review
- prior_baseline_compared:
  - tag `v1.0.2` at `ffdcc47d6c3a5375f0454c4b3afa5b734260acc1`
  - current `main` at `390fd9a8f3dbcf25cf4cc1ea257f50cc3eb3bb12`
  - prompt/deep-research artifacts are unchanged from `v1.0.2`
- research_reused:
  - `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
  - NIST AI RMF Generative AI Profile and OWASP LLM01/LLM02 links from that artifact
- targeted_follow_up_research:
  - current official Claude Code subagent tool inheritance/restriction behavior
  - current official Claude Code model-alias and prompt-injection guidance
- default_exclusions:
  - generated review artifacts except the required shared-research input and baseline metadata
  - vendored dependencies, build output, coverage output, and bulky fixtures

## AI Workflow Area Matrix

| ai_workflow_area | applicability | result | issues | evidence summary |
| --- | --- | --- | --- | --- |
| prompt-artifact-governance | development only | gaps found | ISSUE-004 | Git and queue tracking exist; lifecycle and replay metadata do not |
| prompt-and-instruction-design | development only | gaps found | ISSUE-001, ISSUE-005 | Write authority and uncertainty outcomes are unsafe or underspecified |
| model-routing-and-fallback | development only | gaps found | ISSUE-003 | Mutable aliases and undeclared external command; no fallback contract |
| tool-use-and-boundaries | development only | gaps found | ISSUE-001, ISSUE-002 | Research, decision mutation, and approval are not separated |
| structured-output-and-validation | not needed for this repo's current AI surface | not applicable | none | Development outputs are human-reviewed prose; product schemas are not AI output |
| refusals-and-incomplete-output-handling | development only | gap found | ISSUE-005 | No blocked, unknown, or partial outcome |
| context-selection-and-data-minimization | development only | protected | none | Prompts use public project context; synthetic-only rule; hook context is bounded |
| untrusted-input-isolation | development only | gap found | ISSUE-002 | Web evidence is not isolated from write-capable work |
| prompt-injection-and-untrusted-input | development only | gap found | ISSUE-002 | No workflow-level untrusted-source boundary |
| hallucination-containment-and-fail-safe-behavior | development only | gaps found | ISSUE-001, ISSUE-005 | Decision changes and completeness claims do not fail closed |
| evals-and-regression-testing | development only | gap found | ISSUE-004 | No prompt acceptance fixture or replayable execution metadata |
| model-and-prompt-drift-management | development only | gaps found | ISSUE-003, ISSUE-004 | Prompts float across models/plugins without recorded resolution |
| cost-latency-and-rate-limit-strategy | development only | gap found | ISSUE-006 | No worker, time, or spend bounds |
| logging-redaction-and-traceability | product AI not present | not needed for this repo | none | No inference traces; product logs exclude document bodies |
| operator-controls-and-debuggability | development only | gaps found | ISSUE-001, ISSUE-003 | Approval and prerequisite diagnostics are missing |
| documentation-and-operator-ergonomics | development/future AI | gaps found | ISSUE-003, ISSUE-007, ISSUE-008 | Stale prompt contract and conflicting future ownership/convention text |

## Severity Summary

| severity | count | issue_ids                                                        |
| -------- | ----: | ---------------------------------------------------------------- |
| critical |     0 | none                                                             |
| high     |     1 | ISSUE-001                                                        |
| medium   |     1 | ISSUE-002                                                        |
| low      |     6 | ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-006, ISSUE-007, ISSUE-008 |
| total    |     8 | ISSUE-001 through ISSUE-008                                      |

## Prompt Governance And Versioning

- verified:
  - Reusable prompts are tracked in Git.
  - The deep-research queue preserves exact prompt text, status, output links, and reconciliation notes.
  - The public/synthetic-only boundary is explicit in research prompts.
- gaps:
  - ISSUE-004: no prompt lifecycle metadata or replayable output provenance.
  - ISSUE-003: prompt prerequisites and model resolution are undeclared.
- inferred:
  - Historical reports received owner review because they were reconciled into settled questions, but no claim-level review record was found.
- unverified:
  - Exact ChatGPT and Claude model IDs, settings, and external plugin versions.

## Prompt And Routing Risks

- ISSUE-003: mutable model aliases and `/qdev:research` make routing non-reproducible.
- ISSUE-005: absolute-success language pressures the model to overclaim completeness.
- ISSUE-006: worker fan-out lacks cost and convergence bounds.
- product_runtime_model_routing: not needed for this repo; no inference path exists.

## Tool Use And Boundary Risks

- ISSUE-001: decision-bearing edits are authorized without an owner approval checkpoint.
- ISSUE-002: research and mutation occur in one trust domain.
- verified_positive_control: the SessionStart hook labels injected repository state as data, neutralizes context tags, caps content, uses fixed Git arguments, and avoids exposing full local paths on failure.

## Structured Output And Validation Risks

- status: not needed for this repo's current AI surface
- rationale: AI-assisted development outputs are Markdown for human review and are not parsed into executable product actions. Product JSON/Pydantic artifacts are deterministic application outputs, not model outputs.
- future_trigger: If WH-006 or another model integration lands, require a versioned schema, strict parsing, refusal/incomplete-state handling, and deterministic validation before any output influences a plan or write.

## Refusals And Incomplete Output Risks

- ISSUE-005 is the current development-workflow gap.
- product_runtime_refusals: not needed for this repo; no model request exists.
- future_trigger: Model-assisted semantic work must preserve `unknown`, `inferred`, `rejected`, and `needs-review` states and must never silently fall back to a weaker guarantee.

## Untrusted Input And Privileged Tool Risks

- ISSUE-002: untrusted web material can influence a write-capable research workflow.
- verified_positive_control: Current product corpus bytes never enter a model; product processing is local and deterministic.
- verified_positive_control: Repository policy forbids real corpus bytes in public fixtures and forbids agents from reading real corpus content without specific authorization.

## Prompt Injection And Safety Risks

- ISSUE-002 is the only confirmed prompt-injection-shaped path.
- no_product_path: Corpus documents are not prompt input in v1.
- future_requirement: Any later LLM integration must treat document text/markup as hostile indirect-prompt input, keep authorization and path policy outside the model, constrain tools and egress, and require deterministic validation plus human approval before destructive actions.
- references:
  - [NIST AI RMF Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)
  - [OWASP LLM01: Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
  - [OWASP LLM02: Sensitive Information Disclosure](https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/)

## Model Drift And Baseline Risks

- ISSUE-003 and ISSUE-004 remain present in both current HEAD and the `v1.0.2` baseline.
- No current prompt regression was introduced after `v1.0.2`; the risk is longstanding.
- GAP-68 already documented one broken destination, so the unresolved stale prompt is known backlog drift rather than a newly introduced defect.
- Product model drift is not needed for this repo because no product model exists.

## Eval, Regression, And Monitoring Gaps

- ISSUE-004: there is no lightweight prompt acceptance or replay fixture.
- Recommended minimum regression set:
  - broken-link and canonical-destination check;
  - synthetic owner-decision conflict that must stop for approval;
  - missing-provider/plugin case that must report blocked;
  - hostile-source fixture that must remain data-only and read-only;
  - run manifest recording prompt hash, resolved model, tool policy, source set, issue inventory, and validation results.
- Product AI evals and inference monitoring are not needed for this repo today.

## Operator And Documentation Gaps

- ISSUE-003: clean-clone prerequisites and paths are not usable as written.
- ISSUE-007: future AI/enrichment ownership is ambiguous.
- ISSUE-008: the convention misstates the current frontmatter contract.
- Actual production behavior is documented consistently as offline and deterministic.

## Convention Recommendations

- Add one development-AI convention covering reusable prompt lifecycle metadata, untrusted-source isolation, least-privilege research workers, owner approval for decision changes, and replayable execution records.
- State that AI research is advisory until primary-source claims and repository evidence are verified by the main reviewer.
- Require capability-based routing with bounded worker/time/spend budgets and explicit incomplete outcomes.
- Reconcile future semantic-enrichment ownership before defining provider or prompt standards for WH-006.
- Correct convention 7 so frontmatter is optional and absent from v1-generated documents.
- Preserve existing strong conventions: offline processing, synthetic/public fixtures, environment-only future credentials, spec/OQ approval, and no real-corpus agent access.

## Pass Log

| pass | lens | new_issue_ids | result |
| --: | --- | --- | --- |
| 1 | Inventory, prompt governance, routing, tool boundaries, highest-risk paths | ISSUE-001, ISSUE-003 | Confirmed no product AI runtime; isolated development prompts |
| 2 | Structured output, refusals, validation, context minimization, conventions alignment | ISSUE-005, ISSUE-008 | Product structured-output categories marked not applicable |
| 3 | Prompt injection, tool safety, evals, logging, drift, documentation consistency | ISSUE-002, ISSUE-007 | Targeted current Claude guidance required for tool inheritance |
| 4 | Lower severity, cost/latency, operator ergonomics, convention quality | ISSUE-006 | Mandatory minimum passes complete; not converged |
| 5 | `v1.0.2`/`main` baseline and imported-research provenance | ISSUE-004 | Baseline unchanged; provenance gap added |
| 6 | Adaptive deepening over source, tests, dependencies, prompts, and hook boundary | none | First consecutive no-new-issue pass |
| 7 | Adversarial inventory reconciliation and applicability recheck | none | Second consecutive no-new-issue pass; converged |

## Claude Handoff

- priority_1: Fix ISSUE-001 before reusing the consistency workflow. Convert it to an analysis/proposal flow with explicit owner approval for decision-bearing edits.
- priority_2: Fix ISSUE-002 by separating read-only research from write-capable synthesis and by adding an untrusted-source contract.
- priority_3: Decide whether `docs/prompts/` is active or historical. If active, repair ISSUE-003 through ISSUE-006; if retired, label/archive the prompts so agents do not run them as current instructions.
- priority_4: Reconcile ISSUE-007 and ISSUE-008 before any future semantic-enrichment work.
- suggested_follow_on_reviews:
  - `mcp-and-agent-tool-boundary-review` if `/qdev:research` or other privileged MCP/plugin tools are made repo-local or used non-interactively
  - `retrieval-and-knowledge-base-review` only if WH-007 or a live RAG/index boundary is implemented
- change_scope: no fixes were requested or applied by this review.

## Open Questions Or Assumptions

- Are the two files under `docs/prompts/` active workflows or historical artifacts?
- What repo-external plugin or command provides `/qdev:research`, and what tools and permissions does it grant?
- Which exact Claude and ChatGPT model IDs produced prior workflow and Deep-Research outputs?
- Were imported research claims independently checked against primary sources before owner reconciliation, and is that evidence stored elsewhere?
- Does ADR-0018 intentionally supersede WH-006 ownership, or only describe the current v1 boundary?
- User-level and organization-level Claude/Codex permission policies were outside the repository and could not be verified.

## Residual Risk

- current_product_ai_risk: none identified; product model inference, retrieval, prompt construction, agent loops, and tool calling are absent in v1
- current_development_ai_risk: high until ISSUE-001 is corrected if the consistency prompt remains active; medium for research-source isolation; low for the remaining governance and documentation gaps
- future_ai_risk: high if confidential corpus content is ever sent to a hosted model or model output can affect destructive actions without a separately approved data-flow, deterministic policy enforcement, constrained tools/egress, evals, and human approval
- unverifiable_residuals: external plugin behavior, actual historical model settings, provider-side retention/configuration, and human review traces
