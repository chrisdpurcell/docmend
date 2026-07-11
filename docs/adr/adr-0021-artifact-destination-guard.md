---
schema_version: '1.1'
id: 'adr-0021-docmend-artifact-destination-guard'
title: 'ADR 0021: Artifact destination guard'
description: 'Every CLI artifact write passes one source-aware preflight: a destination is refused as a safety refusal (exit 3) when either the lexical directory entry publication replaces or its fully resolved referent lies inside the corpus root, except destinations under the canonical .docmend/ artifact root that the effective excludes still cover per destination; aliases of invocation inputs are refused outright, staging is O_EXCL-randomized everywhere, and the apply report finalizes inside the run lock.'
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

Chosen option: **"Source-aware guard with a canonical-root carve-out."** One preflight runs for every CLI artifact write (`scan --report`, `plan --out`, `apply --report`, verify output) **before the pipeline runs**. Containment is judged on **two candidates**, because publication is an `os.replace` that swaps a directory entry: the **lexical entry** the replace would swap (resolved parent plus final name, final component deliberately not followed) and the **fully resolved referent**. A destination is refused — safety refusal, exit 3 — when either candidate lies inside the corpus root, when it aliases any input artifact of the same invocation, or when it is a non-regular file; checking only the resolved referent would let an in-corpus symlink pointing outward have its corpus-owned entry silently replaced. The carve-out is the canonical tool artifact root `.docmend/` in the invoking directory, licensed **per destination**: an in-corpus candidate is legal only when it lies under that root **and** its own corpus-relative path is still matched by the effective exclude patterns (the default `**/.docmend/**` exclude keeps its contents out of discovery) — a gitignore negation that re-includes one destination withdraws exactly that destination's license, and an operator-replaced exclude set withdraws the root wholesale. Staging everywhere — artifact writer and the corpus writer's atomic primitives alike — uses `O_EXCL` randomized temp names in the destination directory, and apply report finalization moves inside the run lock (the gate receives the report path; the guard runs before mutation starts).

### Consequences

- Good, because the reproduced corpus-clobber matrix fails closed at invocation time, and the default zero-setup workflows keep working unchanged.
- Good, because randomized exclusive staging closes both the truncate-a-victim vector and the stale-temp-blocks-retry defect in one move.
- Bad, because the guard needs the effective exclude set and the invocation's input list, coupling artifact IO to configuration state it previously ignored.
- Bad, because a legitimate operator choice — deliberately writing a report into the corpus tree — now requires either the `.docmend/` root or an out-of-corpus destination.

### Confirmation

Confirmed by: the artifact-clobber regression matrix across scan, plan, apply dry-run, and refused writes; default-path acceptance tests (`scan .`, `plan .`, apply, restore, verify writing under `./.docmend/`); explicit rejection tests for in-corpus source-file destinations, input aliases, `.docmend/` with its exclusion removed, a negation re-including one exact destination, and **mirror symlink cases in both directions** (outside name → inside referent; inside name → outside referent) with the refusal proven non-mutating; and a kill-then-retry test over the randomized staging names.

## More Information

- **Amendment (2026-07-10, Plan A implementation-plan review F3/F6, owner-approved):** containment made explicitly two-candidate (lexical entry + resolved referent) and the carve-out license made per-destination against the effective excludes rather than root-wide. Both were latent requirements of this ADR's own invariant — `os.replace` swaps directory entries, and gitignore negation can re-include a single path — surfaced by the plan review's counterexamples; spec IR-007 wording aligned in rev 0.27. JSON-artifact file modes remain umask-derived and undecided: permission policy is deferred to the observability/documentation sub-project, deliberately not decided here.
- Guard rules and carve-out reasoning: `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md` (Artifact Destination Guard section; review finding F1 closed).
- Spec: rev 0.26 — IR-007, §18.5; OQ-034's default-location decision is preserved, now with the exclusion made load-bearing.
- Exit-code classification (guard refusal = 3, never 2) is recorded against the amended `adr-0012-verify-semantics-exit-code-taxonomy`.
- Revisit if the default artifact root ever moves outside the corpus (the rejected second option becomes attractive if `.docmend/` gains non-artifact content).
