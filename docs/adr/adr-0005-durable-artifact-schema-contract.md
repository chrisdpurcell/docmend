---
schema_version: '1.1'
id: 'adr-0005-docmend-durable-artifact-schema-contract'
title: 'ADR 0005: Durable artifact schema contract'
description: "docmend's inventory, plan, report, and manifest are governed by four hand-authored, versioned JSON Schemas checked into the repo — the durable external contract between every command; the manifest is JSON Lines (NDJSON) because a single JSON document cannot be appended crash-safely."
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'artifacts'
  - 'schema'
  - 'contract'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0002-layered-pipeline-isolated-writer.md'
  - 'docs/adr/adr-0004-apply-safety-gate-and-preservation.md'
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

# Durable artifact schema contract

## Context and Problem Statement

The inventory, plan, apply report, and manifest are the contract between every docmend command: `plan` reads the inventory, `apply` reads the plan and writes the report + manifest, `verify` and `restore` read all of them. If these shapes drift during implementation, resume, verify, tests, and cross-version migration all become brittle. What is the durable, machine-checkable form of these artifacts, and how is it versioned?

## Decision Drivers

- A durable _external_ contract that does not depend on any internal model library or its version.
- Crash-safe appendability for the manifest (mutations are recorded incrementally, never only at the end).
- Explicit, checkable versioning so a newer tool can read or migrate older artifacts.
- Strict validation that rejects unknown fields rather than silently accepting drift.
- Stable identity fields so resume and restore can key on them.

## Considered Options

- **Four hand-authored, versioned JSON Schemas checked into the repo**, with the manifest as JSON Lines (NDJSON) (RQ-004).
- **A single "as JSON" shape per §9**, without checked-in schemas (the pre-resolution IR-007 wording).
- **Generate the schemas from the internal pydantic models** at build time.

## Decision Outcome

Chosen option: **"Four hand-authored, versioned JSON Schemas, NDJSON manifest."** `inventory.schema.json`, `plan.schema.json`, `report.schema.json`, and `manifest.schema.json` are pinned in-repo (Draft 2020-12, strict `additionalProperties: false`, explicit schema/version fields) before MS-1 code freezes them. Representation is a **single JSON document** for inventory/plan/report and **JSON Lines (NDJSON)** for the append-only manifest, because a single JSON document cannot be appended crash-safely — plus a small regenerable "latest state per path" index. Required identity fields: run-ID, per-action ID, and UUIDv7 `docmend.id`. Symlink/hardlink record shapes are defined (scan records them; plan/apply refuse symlink mutation by default, EC-008). Versioning is MAJOR.MINOR with a backward-only compatibility policy and a `frontmatter_migrate` planned-action for corpus migration. `pydantic` (ADR-0013 candidate / RQ-020) guards _internal_ construction and its JSON-Schema emission **cross-checks** the hand-authored schemas in tests — but the checked-in schemas are the durable contract; they are not generated.

### Consequences

- Good, because the contract is stable and library-independent: resume, verify, tests, and migrations all bind to durable files, not to a model class that can change.
- Good, because NDJSON gives the manifest crash-safe, one-fsync'd-record-per-mutation appends (the basis for safe resume, ADR-0006 candidate) — which IR-007's original blanket "as JSON" could not.
- Good, because reusing one compiled validator per schema caps validation CPU at tens of seconds against a multi-hour I/O-bound run.
- Bad, because two representations (JSON doc + NDJSON) and a schema-vs-pydantic cross-check must both be maintained, and MAJOR.MINOR versioning is ongoing discipline.

### Confirmation

Confirmed by: fixture artifacts that round-trip (inventory/plan/report write→read→identical model; manifest per-line record round-trip); a `jsonschema` `Draft202012Validator` + `FormatChecker` validating against the checked-in schemas; a test asserting pydantic's emitted JSON Schema stays compatible with the hand-authored ones; and a `check-jsonschema` pre-commit hook linting `schemas/*.schema.json`.

## More Information

- Spec: §7.4 DR-001–DR-004, §9, IR-007, §21 OQ-004 (Resolved RQ-004).
- Research: `append-safe-manifest-format`, `json-schema-versioning-migration`, `json-schema-validator-library`.
- The validator library is RQ-018 (ADR-0013 candidate); the internal model library is RQ-020; the resume model that consumes the manifest is ADR-0006 (candidate, RQ-003); the identity field shape is ADR-0008 (candidate, RQ-002). verify's checks over these artifacts + the exit-code taxonomy are RQ-006 (ADR-0012 candidate).
- Revisit on the first MAJOR schema bump, or if a fifth durable artifact is introduced.
