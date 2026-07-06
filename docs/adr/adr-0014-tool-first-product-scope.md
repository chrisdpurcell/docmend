---
schema_version: '1.1'
id: 'adr-0014-docmend-tool-first-product-scope'
title: 'ADR 0014: Tool-first product scope — scale-flexibility is a binding requirement'
description: 'The product is the scale-flexible tool, not the >100k-file migration pipeline: docmend must be fully functional from a single file to an entire library, bound by G-006 (scale-flexibility goal) and NFR-006 (small-scale floor). The v1 surface stays the scan→plan→apply→verify pipeline scaled down — ceremony scales, it is never waived — and a low-ceremony one-shot command is deferred as WH-008. Amends RQ-010/ADR-0010, which had kept genericity an architectural principle only.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-06'
updated: '2026-07-06'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'scope'
  - 'genericity'
  - 'usability'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0002-layered-pipeline-isolated-writer.md'
  - 'docs/adr/adr-0004-apply-safety-gate-and-preservation.md'
  - 'docs/adr/adr-0010-pluggable-policy-seams.md'
supersedes: []
superseded_by: null
source: []
confidence: 'high'
visibility: 'public'
license: null
project:
  decision_makers:
    - 'chrisdpurcell'
---

# Tool-first product scope — scale-flexibility is a binding requirement

## Context and Problem Statement

The spec's §1 originally framed docmend as "a pipeline so that the owner can convert a >100k-file library" — pipeline-as-product. The owner's 2026-07-06 rewrite of §1 clarified the actual framework: **the product is the tool**; the library migration is the impetus use case, made possible by the tool, not the tool's definition. The rewrite states requirement-strength expectations ("perfectly functional for small-scale and individual document manipulation tasks"; "users must not be effectively locked out … if they do not have substantial software and hardware resources") — but RQ-010/ADR-0010 had already resolved the genericity question the other way: an architectural principle governing shape, **not** a v1 requirement. Leaving both on the books would be a live contradiction; leaving the reframing as prose would make the basis of the entire document untestable.

## Decision Drivers

- §1 is the foundation the rest of the spec derives from; a foundation stated as aspiration reproduces exactly the spec-drift rot the consistency audits keep fixing.
- The substrate had already quietly anticipated small scale (FR-005's risk-scaled preservation gate, D-009's seams) — binding it mostly makes existing posture testable rather than adding scope.
- The plan file is the v1 safety-review artifact (ADR-0002/D-006); any flow that bypasses it needs its own safety-gate design and must not be improvised into v1.
- Amending a previously resolved question (RQ-010) requires a new decision record, never a silent upgrade (spec lifecycle rules, Appendix B).

## Considered Options

- **Binding requirements, pipeline-on-one-file** (chosen): add G-006 + NFR-006; the existing four-command pipeline must simply work over a single file; one-shot command deferred.
- **Principle only**: soften §1's wording to stay consistent with RQ-010; zero new requirements. Cheapest, but the reframing stays untestable prose and the §1/RQ-010 contradiction is resolved in the wrong direction (the owner's rewrite was the correction, not the drift).
- **Hybrid**: bind only an NFR resource floor, leave goals/success-evaluation library-framed. Splits the difference incoherently — a floor without a goal has no success signal.
- **One-shot command in v1** (sub-decision): add `docmend fix PATH` collapsing plan+apply now. Rejected for v1: it bypasses the reviewable plan artifact, so it needs its own safety-gate story — real scope, deferred with a trigger instead.

## Decision Outcome

Chosen option: **binding requirements, pipeline-on-one-file.**

- **G-006** (goal): docmend is fully functional from a single file to a >100k-file library, with no heavyweight setup for small jobs. Success signal: the complete scan → plan → apply → verify workflow succeeds on a single file, on modest hardware, with default configuration and only the FR-005 low-risk opt-in.
- **NFR-006** (Must): every `PATH`-accepting command accepts a single file as well as a directory tree; a single-file or small-batch run requires no configuration file, no parallelism, and no preservation infrastructure beyond the FR-005 low-risk opt-in. **The pipeline ceremony scales down; it is never waived.**
- **WH-008** (deferred, with trigger): a low-ceremony one-shot command waits until the NFR-006 single-file flow is proven in real use and demand for lower ceremony is demonstrated.
- §1's broader verb list (repairing, restructuring, classifying) remains product vision bounded by §2.3; "confirmed a total loss" maps to the existing skip-and-report posture (FR-015) — no new triage capability.
- **ADR-0010 stands unchanged**: this decision binds the pipeline's _floor_ (single-file, low-resource operation of the existing surface), not new policy machinery; design-for-pluggable / build-minimal is unaffected (amendment note recorded there).

### Consequences

- Good, because the tool-first framing is now enforceable: a single-file end-to-end test (§17.2/§17.3) gates every release, so small-scale support cannot silently rot while all attention is on the library run.
- Good, because it resolves the §1 ↔ RQ-010 contradiction through the front door — a recorded amendment (OQ-024) rather than divergent prose.
- Good, because deferring WH-008 keeps the plan-file safety model intact: v1 never grows an unreviewed write path.
- Bad, because a Must-level NFR adds v1 test surface (single-file E2E on a minimal environment) that a library-only tool would not need.
- Bad, because casual users get the full four-command ceremony even for one file until WH-008 lands — a deliberate safety-over-convenience trade.
- Bad, because "modest hardware" is only partially operationalized (no config/parallelism/preservation setup is testable; absolute resource numbers remain deferred with RQ-009).

### Confirmation

Confirmed by: the NFR-006 single-file end-to-end test (scan → plan → apply `--write` with the low-risk opt-in → verify) passing with default configuration and no additional setup; §17.3 carrying the NFR-006 row; every `PATH`-accepting command's CLI tests covering a single-file argument; and the §20 scale-flexibility success row evaluated after MS-5.

## More Information

- Spec: §1 (tool-first Purpose & Background, owner-rewritten 2026-07-06), §2.3 WH-008, §4 G-006, §7.2 NFR-006, §7.3 (single-file `PATH` semantics), §14 lower-bound row, §20; §21 OQ-024.
- Decision owner: owner, via the OQ-024 AskUserQuestion round (2026-07-06); recorded as RQ-024.
- **Amends RQ-010 / ADR-0010** (genericity was principle-only; now also a tested requirement — amendment note in ADR-0010's More Information).
- Revisit when WH-008's trigger fires (single-file flow proven in real use, demand for lower ceremony demonstrated) — the one-shot command's safety-gate design is the deferred half of this decision.
