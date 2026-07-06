---
schema_version: '1.1'
id: 'adr-0002-docmend-layered-pipeline-isolated-writer'
title: 'ADR 0002: Layered pipeline with an isolated writer'
description: "docmend is structured as a layered pipeline — discovery, planning, pure transforms, an isolated writer, and verification — with an explicit reviewable plan artifact between planning and execution, rather than a monolithic convert-in-place script."
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'pipeline'
  - 'safety'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/adr/adr-0003-in-place-mutation-output-model.md'
  - 'docs/adr/adr-0004-apply-safety-gate-and-preservation.md'
  - 'docs/adr/adr-0005-durable-artifact-schema-contract.md'
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

# Layered pipeline with an isolated writer

## Context and Problem Statement

docmend rewrites a library of >100,000 legacy documents in bulk. A single mistake in that path can silently corrupt or destroy irreplaceable personal content at scale, and the transformations must be tested, audited, and interrupted-then-resumed safely. How should the tool be structured so that the _dangerous_ part (mutating files) is isolated, testable, and preceded by a review point — rather than entangled with the _safe_ parts (reading, deciding, reporting)?

## Decision Drivers

- The filesystem-mutating layer must be the only place danger lives, and must be small and auditable.
- Transformations must be pure functions so they can be exhaustively unit- and property-tested (NFR-005) without touching a real filesystem.
- Danger must be caught during planning, before any write — including stale-input detection (source changed since the plan was made, FR-003).
- There must be a human/agent review surface between "decide" and "execute" at 100k-file scale, where manual inspection of every file is impossible.

## Considered Options

- **Layered pipeline (discovery → planning → transform → writer → verification) with an explicit plan-file workflow** (spec D-003 + D-006).
- **Monolithic convert-in-place script** that scans and mutates in one pass.
- **Scan-and-apply with no intermediate plan artifact** (layered internally, but no review/stale-input point).

## Decision Outcome

Chosen option: **"Layered pipeline with an explicit plan-file workflow."** Discovery produces an inventory; planning produces a reviewable plan artifact carrying per-file source hashes and a config snapshot; pure transforms compute new content; an isolated writer is the sole component that mutates the filesystem; verification checks the result. `apply` re-validates the plan against current source hashes before executing, so a stale plan cannot silently act on changed inputs (FR-003).

### Consequences

- Good, because the writer is the only fault-prone surface, matching the fault-isolation the concurrency model also relies on (process workers, ADR-0007 candidate).
- Good, because transforms are pure and testable in isolation, satisfying NFR-005 and enabling property-based tests over the weird-document corpus.
- Good, because the plan artifact is both the review surface (nothing mutates without a reviewable intent record) and the stale-input guard (FR-003), and it is the anchor for resume (ADR-0006 candidate) and the safety gate (ADR-0004).
- Bad, because there are more moving parts and durable artifacts to manage, and the workflow is two-step (`plan` then `apply`) rather than one command — an accepted cost, since the review point and stale-input guard are the whole point.

### Confirmation

Confirmed by: NFR-005 purity tests proving transforms perform no filesystem mutation; the writer being the only component with mutation capability; every run emitting artifacts (a run that leaves no audit trail is a defect, §8.5); and `apply` refusing to execute a plan whose source hashes no longer match (FR-003, part of the safety gate).

## More Information

- Spec: §8.1–§8.3 (D-003 layered pipeline, D-006 plan-file workflow), §8.5 design constraints.
- This decision is the backbone the other Tier-1 ADRs hang on: the writer's output model (ADR-0003), the gate that guards it (ADR-0004), and the artifact contract the plan/report/manifest obey (ADR-0005).
- Revisit only if the pipeline model itself is challenged (e.g. a streaming single-pass mode is ever needed); the plan-file review point is a hard requirement, not an optimization.
