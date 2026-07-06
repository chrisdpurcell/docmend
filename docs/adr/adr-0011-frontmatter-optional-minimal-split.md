---
schema_version: '1.1'
id: 'adr-0011-docmend-frontmatter-optional-minimal-split'
title: 'ADR 0011: Frontmatter — optional, minimal, mechanical/semantic split'
description: 'Product-output frontmatter is an opt-in feature, not core behavior; v1 emits only a minimal skeleton that validates against schemas/frontmatter.schema.json, structured as a mechanical/semantic split — Pandoc-recognized fields at the YAML root, docmend-owned data under namespaced objects — with required mechanical fields non-null, optional fields omitted rather than null, and the rich provenance-status wrapper deferred.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'frontmatter'
  - 'metadata'
  - 'output-contract'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0001-no-markdown-frontmatter-standard.md'
  - 'docs/adr/adr-0005-durable-artifact-schema-contract.md'
  - 'docs/adr/adr-0008-stable-document-identity.md'
  - 'docs/adr/adr-0010-pluggable-policy-seams.md'
  - 'docs/adr/adr-0013-v1-dependency-selection.md'
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

# Frontmatter — optional, minimal, mechanical/semantic split

## Context and Problem Statement

docmend's output is Pandoc-flavored Markdown: a boring, portable CommonMark body plus a strict YAML frontmatter block that Pandoc recognizes and can carry onward to HTML/EPUB/DOCX/PDF (D-001). Frontmatter is the durable heart of the output data model (§9). But the full metadata vision — inferred titles/authors/dates, controlled vocabularies, a known/inferred/unknown provenance wrapper — is semantic-enrichment work that v1 explicitly does not do (RQ-001). So: does v1 emit frontmatter at all, and if so, in what shape?

> **Scope note — not the same decision as ADR-0001.** ADR-0001 rejected adopting the project-standards **Markdown Frontmatter Standard for this repo's own documentation**. This ADR governs the **frontmatter docmend writes into converted product documents**. Same word, two different surfaces (conventions #7 draws exactly this line); the two decisions are independent and non-conflicting.

## Decision Drivers

- Frontmatter is an **optional feature**, not core functionality — the owner may run docmend without emitting any, and docmend must never impose it on all documents (RQ-008).
- v1 infers no semantic metadata (RQ-001); emitting placeholder-heavy or `null`-heavy blocks would pollute real files with low-value unknown metadata.
- Pandoc export compatibility (D-001) requires the standard Pandoc-recognized fields to sit at the YAML root, unnamespaced.
- Mechanical (regenerable) metadata must be distinguishable from semantic (hand-curated / inferred) metadata so low-confidence inference never masquerades as confirmed truth (D-007).
- The schema and validator must exist in v1 even though bulk emission does not, so `verify` can validate frontmatter where present (RQ-008, FR-016).

## Considered Options

- **Optional emission + minimal skeleton + mechanical/semantic split** (chosen).
- **Rich provenance model now**: the full `known`/`inferred`/`unknown` status wrapper and semantic fields in v1 — has no v1 consumer (RQ-001) and forces unresolved vocabulary/provenance decisions.
- **Flat schema**: all fields at one level — mixes regenerable mechanical data with hand-curated semantic data and breaks the D-007 trust boundary.

## Decision Outcome

Chosen option: **"optional, minimal, mechanical/semantic split."** Frontmatter emission is **opt-in per run** (a seam per ADR-0010); a run that emits none is legal and has nothing to validate. When emitted, v1 writes a **minimal skeleton** that validates against a checked-in `schemas/frontmatter.schema.json`, structured on the **mechanical/semantic split** (D-007): Pandoc-recognized fields at the YAML root, docmend-owned data under namespaced objects (`docmend`, `source`, `output`). The v1 schema follows five rules (RQ-014):

1. **Required mechanical fields, always present and non-null:** `docmend.id` (the UUIDv7 identity, ADR-0008), `docmend.schema_version`, `source.original_path`, `source.hash`, `output.hash`.
2. **`title` required but allowed a static placeholder** (`Untitled`) — v1 infers no titles.
3. **Optional fields are omitted, never `null`** — `null` cannot distinguish unknown / not-applicable / not-processed.
4. **`date` / `date-time` scalars are kept as strings** by overriding the YAML timestamp constructor, so JSON-Schema `format` assertions actually fire (the same override the YAML codec requires, ADR-0013 / RQ-021).
5. **The rich `known`/`inferred`/`unknown` provenance wrapper (`metadata_status`) is deferred** to when semantic enrichment (§2.3 WH-###) is scheduled.

Emission goes through the `FrontmatterCodec` (`ruamel.yaml`, ADR-0013) for duplicate-key rejection and controlled Pandoc-compatible output; validation uses the reused `Draft202012Validator` (ADR-0013). The §9 null-heavy worked example is rewritten to this convention when `schemas/frontmatter.schema.json` is authored (GAP-56).

### Consequences

- Good, because the output contract can be authored and validated now (skeleton + schema + `verify` support) without settling the deferred provenance, controlled-vocabulary, and required/null/omitted questions.
- Good, because the mechanical/semantic split keeps regenerable fields trustworthy and gives future semantic fields a home that never overwrites user-reviewed metadata with lower-confidence generated values (D-007).
- Good, because root-level Pandoc fields preserve onward export (D-001) while namespaced `docmend`/`source`/`output` objects keep tool-owned data out of Pandoc's way.
- Bad, because a `title: Untitled` placeholder is deliberately low-information until semantic enrichment lands — accepted, because v1 infers nothing and an honest placeholder beats a fabricated title.
- Bad, because deferring `metadata_status` means the schema will take a MINOR/MAJOR revision when the provenance wrapper is added (the ADR-0005 versioning policy absorbs this).

### Confirmation

Confirmed by: `schemas/frontmatter.schema.json` existing and rejecting a `null` in any required mechanical field, a missing `docmend.id`, and a duplicate key; a skeleton fixture round-tripping through the codec and validating; `verify` validating frontmatter where present and treating a no-frontmatter run as legal (RQ-008 FR-016/FR-014 conditionality, GAP-55); and `date`/`date-time` fixtures failing `format` assertions when malformed (proving the string-preservation override is active).

## More Information

- Spec: §7.1 FR-016, §9, DR-005, D-001, D-007.
- Research: `managing-pandoc-markdown-and-strict-yaml-frontmatter`, `safe-yaml-loading`.
- Decision owner: owner (RQ-008 scope + RQ-014 schema detail, both 2026-07-05). Sibling to ADR-0001 (repo-doc frontmatter standard, distinct surface); instance of ADR-0010 (emission is a seam); depends on ADR-0013 (codec + validator) and ADR-0008 (`docmend.id`); versioned under ADR-0005.
- Revisit when semantic enrichment (§2.3 WH-###) is scheduled — that unfreezes the deferred `metadata_status` wrapper, inferred fields, and controlled-vocabulary validation.
