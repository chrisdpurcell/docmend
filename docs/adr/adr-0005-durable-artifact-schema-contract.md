---
schema_version: '1.1'
id: 'adr-0005-docmend-durable-artifact-schema-contract'
title: 'ADR 0005: Durable artifact schema contract'
description: "docmend's inventory, plan, report, and manifest are governed by four hand-authored, versioned JSON Schemas checked into the repo — the durable external contract between every command; the manifest is JSON Lines (NDJSON) because a single JSON document cannot be appended crash-safely."
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-10'
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

Chosen option: **"Four hand-authored, versioned JSON Schemas, NDJSON manifest."** `inventory.schema.json`, `plan.schema.json`, `report.schema.json`, and `manifest.schema.json` are pinned in-repo (Draft 2020-12, strict `additionalProperties: false`, explicit schema/version fields) before MS-1 code freezes them. Representation is a **single JSON document** for inventory/plan/report and **JSON Lines (NDJSON)** for the append-only manifest, because a single JSON document cannot be appended crash-safely — plus a small regenerable "latest state per path" index. Required identity fields: run-ID, per-action ID, and UUIDv7 `docmend.id`. Symlink and hard-link record shapes are both defined: scan records a symlink (recorded, not followed for mutation by default, EC-008) and, where `st_nlink > 1`, the shared-inode hard-link alias group (EC-011); plan/apply refuse symlink mutation by default and process a hard-linked file once, skipping-and-reporting the alias set rather than mutating it — `os.replace()` on one path would break the link and leave the other names pointing at the stale original (FR-015). Versioning is MAJOR.MINOR with a backward-only compatibility policy and a `frontmatter_migrate` planned-action for corpus migration. `pydantic` (ADR-0013 / RQ-020) guards _internal_ construction and its JSON-Schema emission **cross-checks** the hand-authored schemas in tests — but the checked-in schemas are the durable contract; they are not generated.

### Consequences

- Good, because the contract is stable and library-independent: resume, verify, tests, and migrations all bind to durable files, not to a model class that can change.
- Good, because NDJSON gives the manifest crash-safe, one-fsync'd-record-per-mutation appends (the basis for safe resume, ADR-0006) — which IR-007's original blanket "as JSON" could not.
- Good, because reusing one compiled validator per schema caps validation CPU at tens of seconds against a multi-hour I/O-bound run.
- Bad, because two representations (JSON doc + NDJSON) and a schema-vs-pydantic cross-check must both be maintained, and MAJOR.MINOR versioning is ongoing discipline.

### Confirmation

Confirmed by: fixture artifacts that round-trip (inventory/plan/report write→read→identical model; manifest per-line record round-trip); a `jsonschema` `Draft202012Validator` + `FormatChecker` validating against the checked-in schemas; a test asserting pydantic's emitted JSON Schema stays compatible with the hand-authored ones; and a `check-jsonschema` pre-commit hook linting `schemas/*.schema.json`.

## More Information

- **Amendment (2026-07-10, comprehensive review / safety-core design):** the first MAJOR schema bump and the fifth artifact arrive together (spec rev 0.26, targets v2.0.0). **Manifest 2.0** (`adr-0019-manifest-2-recovery-model`) adds a line-1 header record (run, kind, roots, plan hash, chain links), intent/terminal lifecycle records for every mutation kind, durable object-identity fields, and restore `undoes` references. **Compatibility is a recorded clean break**: no real-library runs exist, so v2 tooling rejects every 1.x manifest with an operator message naming docmend 1.0.2 as the restore path for pre-2.0 runs — the MAJOR-bump discipline this ADR anticipated, exercised deliberately. The **report schema** gains the `not-attempted` outcome status, its totals extension, and the attempt-lineage fields (`prior_attempt`, `manifest_sha256`). A **fifth durable artifact** joins the registry: the optional `verify-report` (durable verification evidence, written through the `adr-0021` destination guard). Plan and inventory schemas are unchanged.
- **Amendment (2026-07-06, OQ-004 / gap-32):** the hard-link record shape is now genuinely specified, not merely asserted. Owner adopted the gap-32 policy — detect `st_nlink > 1` at scan, record the shared-inode alias group in the inventory, and skip-and-report at apply rather than mutate (because `os.replace()` on one path breaks the link). Spec: §10.3 EC-011, DR-001, §21 OQ-004. Prior to this the Decision Outcome claimed hard-link shapes were defined while no artifact defined them (consistency-audit finding).
- Spec: §7.4 DR-001–DR-004, §9, §10.3 EC-008/EC-011, IR-007, §21 OQ-004 (Resolved RQ-004).
- Research: `append-safe-manifest-format`, `json-schema-versioning-migration`, `json-schema-validator-library`.
- The validator library is ADR-0013 (RQ-018); the internal model library is ADR-0013 (RQ-020); the resume model that consumes the manifest is ADR-0006 (RQ-003); the identity field shape is ADR-0008 (RQ-002). verify's checks over these artifacts + the exit-code taxonomy are ADR-0012 (RQ-006).
- Revisit on the first MAJOR schema bump, or if a fifth durable artifact is introduced.
