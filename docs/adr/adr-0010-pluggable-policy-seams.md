---
schema_version: '1.1'
id: 'adr-0010-docmend-pluggable-policy-seams'
title: 'ADR 0010: Design-for-pluggable policy seams'
description: 'docmend keeps its "generally useful" ambition as an architectural principle, not v1 feature work: naming policy, preservation strategy, controlled-vocabulary source, and frontmatter emission are each isolated behind a seam so a later version can add config-driven policies without a breaking redesign, while v1 ships exactly one minimal default per seam and no swap-config machinery.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'extensibility'
  - 'genericity'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0002-layered-pipeline-isolated-writer.md'
  - 'docs/adr/adr-0004-apply-safety-gate-and-preservation.md'
  - 'docs/adr/adr-0008-stable-document-identity.md'
  - 'docs/adr/adr-0011-frontmatter-optional-minimal-split.md'
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

# Design-for-pluggable policy seams

## Context and Problem Statement

docmend's stated ambition is to stay generally useful beyond this one legacy-library migration (§1), yet its v1 job is narrow and its governing constraint is "correctness and safety first" (RQ-009). Four decisions carry a live desire for future flexibility — the naming policy (RQ-002), the preservation strategy (RQ-005 / RQ-007), the controlled-vocabulary source (RQ-011), and whether a run emits frontmatter at all (RQ-008). How much of that flexibility does v1 build, and how much does it merely leave room for?

## Decision Drivers

- The "generally useful" ambition (§1) must survive v1 without becoming v1 scope.
- Correctness and safety first (RQ-009) governs **build order**: no configuration machinery competing with the dangerous-path work.
- Retrofitting extensibility onto hardcoded policy is a breaking redesign; designing the seam up front is cheap.
- Do not build a config surface that has **no v1 consumer** (build-minimal).
- The owner explicitly does not want to be locked into a single naming policy or a single preservation strategy long-term (RQ-002, RQ-005).

## Considered Options

- **Design-for-pluggable, build-minimal** (chosen): isolate each policy behind a seam, ship one minimal default per seam, build no swap machinery.
- **Hardcode each policy**: cheapest in v1; every future policy is a breaking change to generalize.
- **Build full pluggable config in v1**: honors §1 immediately but adds config surface and machinery that conflict with correctness-first.

## Decision Outcome

Chosen option: **"design-for-pluggable, build-minimal."** §1's genericity becomes an **architectural principle governing shape, not a v1 requirement adding features** (D-009). The v1 substrate must not _preclude_ pluggable policies: naming, preservation, controlled vocabulary, and frontmatter emission are each isolated behind a seam/interface, and v1 ships exactly **one minimal default per seam** with no config machinery to swap them. Concretely, the four seams and their v1 defaults are:

- **Naming policy** — the mechanical `.txt`→`.md` extension rename is _one implementation_ of a naming-policy seam; identity is never derived from the filename (ADR-0008 / RQ-002).
- **Preservation strategy** — the writer's preservation step is an interface; docmend stays strategy-agnostic and ships the tool-backup + manifest posture as its default (ADR-0004 / RQ-005 / RQ-007).
- **Controlled vocabulary** — the frontmatter schema/validator is **vocabulary-agnostic**: it validates a facet value against a set **injected from the run's configuration**, never a taxonomy hardcoded in this public repo. This absorbs RQ-011 as a direct instance of this ADR — the repo ships only a small, generic, non-revealing example set for tests; real vocabularies are external and per-corpus.
- **Frontmatter emission** — emitting frontmatter is an opt-in toggle, not core behavior (ADR-0011 / RQ-008).

The mechanism decisions each seam defers (config file vs named profiles, on-disk vocab format, alternative naming/preservation policies) are **deferred to when a consumer for them is actually built**, post-v1.

### Consequences

- Good, because a later version can add config-driven policies as a **non-breaking addition** rather than a redesign — the schema-shape and interface choices that are expensive to change later are made now, for free.
- Good, because it keeps §1's ambition honest without letting it inflate v1 scope; build-minimal keeps the dangerous-path work first.
- Good, because forbidding a hardcoded §9 taxonomy in the public repo aligns the genericity seam with the confidentiality posture (ADR-0011 note, RQ-011, §13.4) at zero extra cost.
- Bad, because a seam with a single implementation looks like over-abstraction until the second implementation arrives — the justification is the reversal cost, not present-day use.
- Bad, because "the substrate must not preclude X" is a fuzzier fitness test than a concrete requirement; it relies on review discipline rather than an automated check.

### Confirmation

Confirmed by: the frontmatter validator accepting an externally-supplied vocabulary set rather than importing a repo-committed taxonomy (test with an injected generic set); the preservation step and naming action each sitting behind an interface with the single v1 default as one implementation; and the public repo containing **no** committed controlled-vocabulary dictionary or §9 personal taxonomy (reaffirmed by ADR-0011 and the C-002 synthetic-fixtures rule).

## More Information

- Spec: §1 (generally-useful ambition), §8 architecture, §9, D-009.
- Decision owner: owner, decided in session via the genericity AskUserQuestion (RQ-010, 2026-07-05).
- This is a **philosophy ADR**: it governs the shape of several other decisions rather than a single mechanism. Instances live in ADR-0002 (layered pipeline), ADR-0004 (preservation interface), ADR-0008 (naming-policy seam), and ADR-0011 (frontmatter emission). RQ-011 (external per-corpus vocabularies) is recorded here as an instance rather than as its own ADR.
- Revisit when a second policy implementation (an alternative naming or preservation policy, or controlled-vocab emission) is actually scheduled — that is when the deferred config-surface decisions become live.
