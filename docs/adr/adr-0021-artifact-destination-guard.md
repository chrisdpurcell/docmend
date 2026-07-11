---
schema_version: '1.1'
id: 'adr-0021-docmend-artifact-destination-guard'
title: 'ADR 0021: Artifact destination guard'
description: 'Every CLI artifact write passes one source-aware preflight: destinations resolving inside the corpus root are refused as a safety refusal (exit 3) except the canonical .docmend/ artifact root, which stays legal only while its default exclusion still covers it and it aliases no input of the invocation; staging is O_EXCL-randomized everywhere, and the apply report finalizes inside the run lock.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-10'
updated: '2026-07-10'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'safety'
  - 'artifacts'
  - 'cli'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md'
  - 'docs/codex-reviews/2026-07-10-2034-comprehensive-review-synthesis.md'
  - 'docs/adr/adr-0005-durable-artifact-schema-contract.md'
  - 'docs/adr/adr-0012-verify-semantics-exit-code-taxonomy.md'
supersedes: []
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

# Artifact destination guard

## Context and Problem Statement

`scan --report`, `plan --out`, and `apply --report` accept unchecked destination paths, the artifact writer stages at a predictable `<name>.tmp` sibling it truncates, and the apply gate never sees the report path. The 2026-07-10 review reproduced corpus source files being replaced by inventory, plan, and report JSON during scan, plan, apply dry-run, and even a refused write — each returning its normal status (DMR-02). The tool's own artifacts must never be able to destroy the corpus they describe. What is the destination trust boundary, given that the accepted default artifact root `./.docmend/` (OQ-034, §18.2) legitimately lies **inside** the corpus for the common `PATH=.` invocation?

## Decision Drivers

- A refused artifact write must not follow a completed pipeline stage — refusal has to precede the work.
- The default workflows (`scan .`, `plan .`, the single-file journey) are binding behavior (NFR-006, OQ-034) and must keep working without setup.
- Predictable staging names are themselves a truncation vector and block retry after a hard kill.
- An artifact destination that aliases an input of the same invocation (e.g. `plan --out` onto its inventory) corrupts the pipeline even outside the corpus.
- A dry-run or refused apply must leave prior corpus state **and** prior artifacts untouched.

## Considered Options

- **Source-aware guard with a canonical-root carve-out:** refuse in-corpus destinations except a proven-excluded `.docmend/`.
- **Move the default artifact root outside the corpus:** revise OQ-034, §18.2, discovery, docs, and tests.
- **Blanket in-root refusal:** simplest rule; breaks the default workflows.

## Decision Outcome

Chosen option: **"Source-aware guard with a canonical-root carve-out."** One preflight runs for every CLI artifact write (`scan --report`, `plan --out`, `apply --report`, verify output) **before the pipeline runs**. A destination is refused — safety refusal, exit 3 — when it resolves (through symlinks) inside the corpus root, aliases any input artifact of the same invocation, or is a non-regular file. The single carve-out is the canonical tool artifact root `.docmend/` in the invoking directory: it remains legal inside the corpus **only while** the effective exclude patterns still cover it (the default `**/.docmend/**` exclude, which keeps its contents out of discovery) and the destination aliases no input; if the operator removed that exclusion, the guard refuses rather than write into scannable corpus space. Staging everywhere — artifact writer and the corpus writer's atomic primitives alike — uses `O_EXCL` randomized temp names in the destination directory, and apply report finalization moves inside the run lock (the gate receives the report path; the guard runs before mutation starts).

### Consequences

- Good, because the reproduced corpus-clobber matrix fails closed at invocation time, and the default zero-setup workflows keep working unchanged.
- Good, because randomized exclusive staging closes both the truncate-a-victim vector and the stale-temp-blocks-retry defect in one move.
- Bad, because the guard needs the effective exclude set and the invocation's input list, coupling artifact IO to configuration state it previously ignored.
- Bad, because a legitimate operator choice — deliberately writing a report into the corpus tree — now requires either the `.docmend/` root or an out-of-corpus destination.

### Confirmation

Confirmed by: the artifact-clobber regression matrix across scan, plan, apply dry-run, and refused writes; default-path acceptance tests (`scan .`, `plan .`, apply, restore, verify writing under `./.docmend/`); explicit rejection tests for in-corpus source-file destinations, input aliases, and `.docmend/` with its exclusion removed; and a kill-then-retry test over the randomized staging names.

## More Information

- Guard rules and carve-out reasoning: `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md` (Artifact Destination Guard section; review finding F1 closed).
- Spec: rev 0.26 — IR-007, §18.5; OQ-034's default-location decision is preserved, now with the exclusion made load-bearing.
- Exit-code classification (guard refusal = 3, never 2) is recorded against the amended `adr-0012-verify-semantics-exit-code-taxonomy`.
- Revisit if the default artifact root ever moves outside the corpus (the rejected second option becomes attractive if `.docmend/` gains non-artifact content).
