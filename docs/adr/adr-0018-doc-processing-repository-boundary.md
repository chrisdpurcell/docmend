---
schema_version: '1.1'
id: 'adr-0018-docmend-doc-processing-repository-boundary'
title: 'ADR 0018: Doc Processing repository boundary'
description: 'docmend is the standalone batch-normalization product; doc-proc-scripts is the workstation/orchestration/privacy layer that consumes it as one downstream — the boundary, non-goals, safety contract, and wrapper expectations are recorded here and mirrored by a sibling ADR in doc-proc-scripts.'
doc_type: 'adr'
status: 'proposed'
created: '2026-07-07'
updated: '2026-07-07'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'scope'
  - 'boundary'
  - 'safety'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/adr/adr-0004-apply-safety-gate-and-preservation.md'
  - 'docs/adr/adr-0006-resume-and-recovery-model.md'
  - 'docs/adr/adr-0014-tool-first-product-scope.md'
  - 'docs/adr/adr-0015-test-corpus-and-anonymization.md'
  - 'docs/adr/adr-0016-mechanical-transform-boundary.md'
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

# Doc Processing repository boundary

## Context and Problem Statement

The Doc Processing project spans two repositories: `docmend` (this repo) and the private workstation repo `doc-proc-scripts`. Both mutate or orchestrate work over the same real document library, and a 2026-07-07 cross-repo alignment review found the boundary between them implicit — safe today, but rediscovered from context by every new agent session, and at risk of drifting into duplicate batch semantics or downstream-specific narrowing of `docmend`. Which responsibilities belong to which repository, and what contract do wrappers get to rely on?

## Decision Drivers

- `docmend` is a standalone, shippable, general-purpose product (adr-0014); it may serve many downstreams and must not be distorted into an implementation detail of one workstation setup.
- The real library is private; `docmend` is public. Agents working here must never need — or receive — real corpus content (adr-0015).
- Batch mutation safety guarantees (gate, manifest, resume, restore) live in exactly one place, or they erode.
- Wrapper behavior in `doc-proc-scripts` depends on documented, stable `docmend` semantics — especially restore limitations.

## Considered Options

- **Explicit boundary, two ADRs:** each repo records the same boundary from its own side and cross-references the sibling.
- **Single-owner boundary:** record the boundary only in `docmend` and have `doc-proc-scripts` link to it.
- **Status quo:** leave the boundary implicit in each repo's scope docs.

## Decision Outcome

Chosen option: **"Explicit boundary, two ADRs"** — each repository's agents read their own ADR set first, so the decision must be native to both; cross-referencing keeps the two records honest.

### `docmend` owns

- Its own product direction, release quality, public interface, and general-purpose mission (adr-0014).
- Batch normalization: large-tree scan → plan → apply → restore → verify.
- Artifact schemas (inventory/plan/report/manifest/frontmatter) and their validation (adr-0005).
- Strict configuration semantics and the `apply --write` safety-gate semantics (adr-0004).
- Manifest, resume, restore, and verify behavior (adr-0006, adr-0012).
- Pure mechanical transforms for text/Markdown normalization (adr-0016).
- Synthetic scale and weird-document fixtures validating batch behavior (adr-0015).

### `docmend` does not own

- Downstream-specific workflow policy that would narrow the standalone product.
- Kate-specific workflow design, human editor bindings, interactive selection filters.
- Real-corpus inspection by agents; corpus-profile privacy abstraction (unless formally moved into scope by a future revision).
- HTML→Markdown article extraction beyond the adr-0016 mechanical boundary.
- Metadata/frontmatter enrichment beyond current verify/frontmatter schema behavior.

### `doc-proc-scripts` owns

- Workstation orchestration and OS glue; Bash safety-wrapper conventions.
- Kate-facing tools and config templates; human-in-the-loop text repair and HTML conversion workflows.
- Format triage gaps (suffix/content mismatch, PDF structural checks).
- Batch campaign wrapper behavior around `docmend`, including independent snapshots.
- Corpus privacy rules and agent behavior around real corpus content; content-free corpus-profile design.

### `doc-proc-scripts` does not own

- A second batch normalization engine, or duplicate scan/plan/apply/restore semantics.
- Manifest restore semantics beyond wrapping and explaining `docmend` behavior.
- Automatic encoding-conversion policy, deduplication, reassembly, or metadata enrichment without an accepted design.

### Shared safety contract

- Mutating tools are dry-run/report-first; `docmend`'s `apply --write` gate is never weakened or bypassed by a wrapper.
- **Restore expectations:** `docmend restore` is complete only when tool backups exist for content rewrites. Under `--preserved-by external`, the wrapper's independent snapshot is the authoritative full restore path — `docmend`'s manifest then undoes only pure renames, and wrappers must present it that way.
- **Privacy contract:** agents do not read real corpus contents unless specifically authorized for a specific file; reports and logs carry metadata only; public-repo fixtures are synthetic (adr-0015 anonymization for weird-corpus expansion).
- Safety-affecting behavior changes on either side get regression tests and a cross-reference in the sibling repo when the wrapper contract is touched.

### Consequences

- Good, because future agents inherit the boundary instead of re-deriving it, and "should this feature live here?" has a recorded answer.
- Good, because `docmend`'s general-purpose contract is protected from downstream-specific drift while still serving `doc-proc-scripts` deliberately.
- Bad, because two records can diverge; the cross-reference and the sibling's "mirrors the accepted boundary" statement are the mitigation, and boundary changes must touch both.

### Confirmation

The temporary root `ALIGNMENT_HANDOFF.md` files in both repositories are deleted only after this ADR (and its sibling) are accepted; thereafter, scope questions in review cite this ADR, and any boundary change requires updating both ADRs in the same effort.

## More Information

- Sibling record: `doc-proc-scripts` `docs/adr/` boundary ADR (same title scheme), which either cross-references this ADR or states that it mirrors the accepted boundary decision.
- Origin: 2026-07-07 cross-repo alignment review (temporary coordination doc; findings triaged in this repo as the same-run collision split, intent-record interruption evidence, discovery pruning, release-workflow pinning, and version-drift fixes).
- Decision owner: `chrisdpurcell` (accepts by flipping `status` to `accepted`).
- Revisit if corpus-profile privacy abstraction is delegated into `docmend`, if HTML article extraction is brought into mechanical scope (adr-0016 revision), or if a second downstream consumer appears with conflicting wrapper needs.
