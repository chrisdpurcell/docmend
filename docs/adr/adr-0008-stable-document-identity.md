---
schema_version: '1.1'
id: 'adr-0008-docmend-stable-document-identity'
title: 'ADR 0008: Stable document identity'
description: "Document identity is a UUIDv7 (docmend.id) minted per document, never derived from the filename; the manifest is the path-history map, and a 3-tier algorithm recovers identity on re-scan across renames and rewrites."
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'identity'
  - 'data-model'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0003-in-place-mutation-output-model.md'
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

# Stable document identity

## Context and Problem Statement

Filenames change (a mechanical extension rename now, semantic renaming later via WH-001) and content is rewritten. docmend must track a document's identity across both so the manifest, resume (ADR-0006), and future dedup/enrichment can reliably refer to "the same document." What is that identity, and how is it recovered when an already-processed corpus is re-scanned?

## Decision Drivers

- Identity must survive **both** filename changes and content rewrites.
- Never derive identity from the filename — a rename would break it.
- Identity must be **recoverable** on a fresh scan of already-processed files.
- Do not lock in a single naming policy long-term (the RQ-010 seam).

## Considered Options

- **UUIDv7 in frontmatter + manifest path-history** (chosen).
- **Filename / path as identity.**
- **Content hash as identity.**

## Decision Outcome

Chosen option: **"UUIDv7 + manifest path-history."** `docmend.id` — a UUIDv7 (`uuid.uuid7()`, RFC 9562) minted per document — is the stable internal identity. `source.original_path` is provenance only; the manifest is the path-history map. v1 changes filenames only for the mechanical extension rename; identity is never derived from the filename. Target-path collision policy stays `skip` (default) / `fail` / `overwrite` (FR-011). **Identity recovery on re-scan uses a 3-tier algorithm:** (1) trust a schema-valid frontmatter `docmend.id`; (2) else match the manifest by path with hash confirmation, then by content-hash; (3) else mint a new UUIDv7 and flag **"identity not recoverable."** Semantic renaming is deferred (WH-001) and reuses the same manifest + IDs without changing the identity model. The naming policy itself is a pluggable seam (ADR-0010 candidate / RQ-010): v1 ships the single mechanical policy without precluding config-driven policies later.

### Consequences

- Good, because identity is stable across rename and rewrite; a time-ordered UUIDv7 keeps IDs sortable and index-friendly; content-hash and path serve as recovery fallbacks, not as the identity.
- Good, because the 3-tier recovery degrades gracefully and never silently reuses a wrong identity — it flags the unrecoverable case instead.
- Bad, because once IDs are minted into real files the scheme is effectively irreversible; a v1 mistake here is expensive, which is precisely why it is pinned as an ADR now.
- Bad, because identity recovery depends on the manifest (ADR-0005) being intact; a lost manifest drops recovery to the content-hash/mint tiers.

### Confirmation

Confirmed by: round-trip tests (mint → rename → rewrite → re-scan recovers the same `docmend.id` through each tier); a corrupted-frontmatter fixture that falls to manifest match; a no-manifest + changed-content fixture that mints a new id and flags it "not recoverable"; and a UUIDv7-format assertion matching the §9 frontmatter example.

## More Information

- Spec: §7.1 FR-010/FR-011, §9 (`docmend.id`).
- Research: `stable-document-id-scheme`.
- Decision owner: owner (RQ-002). Relates to ADR-0005 (run-ID / action-ID / `docmend.id` are the artifacts' required identity fields), ADR-0003 (rewrites preserve identity), and RQ-010 (naming-policy seam).
- Revisit only if the identity scheme itself must change (a MAJOR schema event, ADR-0005) or when a config-driven naming policy is built.
