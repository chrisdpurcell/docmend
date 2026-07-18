---
schema_version: '1.1'
id: 'adr-0022-docmend-sequential-million-file-scale-contract'
title: 'ADR 0022: Sequential million-file scale contract'
description: 'docmend v2.0.0 supports sequential execution from one through 1,000,000 files, removes the inert parallel configuration surface, adopts plan schema 2.0, and reopens concurrency only after accepted evidence shows the sequential workflow exceeds 12 hours.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-11'
updated: '2026-07-12'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'scale'
  - 'performance'
  - 'concurrency'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0005-durable-artifact-schema-contract.md'
  - 'docs/superpowers/specs/2026-07-11-million-file-scale-and-resource-design.md'
  - 'docs/superpowers/plans/2026-07-11-million-file-scale-and-resource-contract.md'
supersedes:
  - 'docs/adr/adr-0007-concurrency-primitive-process-pool.md'
superseded_by: null
source: []
confidence: 'high'
visibility: 'public'
license: null
project:
  decision_makers:
    - 'chrisdpurcell'
  consulted: []
  informed: []
---

# Sequential million-file scale contract

## Context and Problem Statement

NFR-001 historically required corpus-size-independent memory and supported parallel execution, while docmend's whole-run inventory, plan, report, and lifecycle evidence necessarily grow with file count. The shipped `parallel.*` configuration has no runtime consumer, the old 100,000-file test omits the installed-CLI and plan-aware verification paths, and plan schema 1.2 requires the inert parallel snapshot. What scale, memory, execution, and compatibility contract can v2.0.0 honestly qualify?

## Decision Drivers

- The release must prove the complete installed `scan -> plan -> apply --write -> verify --plan` workflow at the intended upper bound.
- Whole-run evidence must remain durable and reviewable without accumulating per-file body content.
- Configuration must not accept settings that the runtime ignores.
- Binding memory thresholds must come from unbiased external measurement on a public-safe reference environment.
- The single-file, no-config path remains a first-class product contract.
- A breaking plan-format change must fail before gate evaluation or mutation and provide an actionable migration path.

## Considered Options

- **Sequential execution through 1,000,000 files with bounded-linear metadata and pilot-derived resource thresholds.**
- **Implement the process-pool design recorded in the superseded ADR 0007 before scale qualification.**
- **Retain the inert `parallel.*` surface and the historical 100,000-file acceptance test.**

## Decision Outcome

Chosen option: **"Sequential million-file qualification with bounded-linear metadata."** docmend v2.0.0 supports sequential execution from one file through a binding 1,000,000-file qualification. The `parallel.*` configuration namespace is removed; a legacy table is an exit-2 migration error before scanning, while the default/no-config path remains valid. Whole-run artifact metadata may grow linearly, but per-file body content may not accumulate. Process concurrency may return only after the 1M workflow exceeds 12 hours on the accepted reference environment and a separately approved design proves equivalence, parent-only shared-artifact writes, worker isolation, and a hard watchdog boundary.

The complete installed-CLI qualification runs each stage in a separate uninstrumented subprocess. Binding peak RSS is observed externally; Python allocation tracing belongs to a separate diagnostic lane. A first 100,000-file pilot produces the evidence from which SPEC-VHHB revision two freezes the executable absolute peak, fitted incremental slope, and linearity thresholds with the approved headroom. The release then qualifies 1,000,000 files against those thresholds on the accepted Linux/POSIX, local disk-backed reference environment and must complete within 12 hours.

Plan schema 2.0 removes the required `parallel` configuration snapshot. v2 rejects every 1.x plan before gate evaluation or mutation and directs the operator to regenerate it; a supported inventory may be reused to produce the v2 plan.

### Consequences

- Good, because the specification matches the artifact architecture's real bounded-linear memory model instead of promising corpus-size-independent memory.
- Good, because unsupported configuration fails clearly rather than appearing to enable behavior that does not exist.
- Good, because release evidence binds the exact built wheel, candidate commit, complete workflow, reference environment, and public-safe measurement contract.
- Bad, because the million-file release qualification is long-running and requires a qualifying local Linux/POSIX machine with sufficient disk, inodes, and memory.
- Bad, because operators holding 1.x plans must regenerate them before v2 apply, even when the underlying inventory remains usable.

### Confirmation

Confirmed by: strict config tests for every legacy parallel-table shape; plan 2.0 schema/model and pre-gate 1.x rejection tests; the checked-out-source 1,000-file guard; accepted uninstrumented 100,000-file pilot evidence and the resulting versioned thresholds; the scheduled installed-wheel 100,000-file diagnostic; and accepted file-size plus 1,000,000-file qualification evidence whose artifact totals, plan coverage, expected findings, peak RSS, slope, linearity, environment identity, and elapsed time all satisfy the binding contracts.

## More Information

- Owner decision: OQ-037 / RQ-037, approved 2026-07-11.
- Approved design: `docs/superpowers/specs/2026-07-11-million-file-scale-and-resource-design.md`.
- Implementation plan: `docs/superpowers/plans/2026-07-11-million-file-scale-and-resource-contract.md`.
- Plan compatibility: `docs/adr/adr-0005-durable-artifact-schema-contract.md`.
- Supersedes `docs/adr/adr-0007-concurrency-primitive-process-pool.md`; concurrency reopens only through the evidence and approval conditions in this ADR.
