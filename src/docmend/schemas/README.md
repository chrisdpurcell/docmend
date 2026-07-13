# Artifact JSON Schemas

The hand-authored JSON Schemas here are the **durable external contract** for docmend's run artifacts (spec DR-001..DR-004 and FR-014, IR-007; canonical decision: `docs/adr/adr-0005-durable-artifact-schema-contract.md`) plus the product-frontmatter contract (DR-005, `adr-0011`). The original four artifact contracts were pinned at MS-1, before any code froze their shapes; the verify-report contract was added by the approved Plan D redesign. The direction of authority is fixed: **code and internal pydantic models conform to these files, never the reverse.** The internal models' emitted JSON Schema is cross-checked against these in tests, but the checked-in files are the contract.

| Schema | Artifact | Representation | Producing command | Current version |
| --- | --- | --- | --- | --- |
| `inventory.schema.json` | DR-001 inventory | single JSON document | `scan` (MS-1) | 1.2 (MS-5: `timeout` scan-skip reason + `skipped_by_reason.timeout` counter, FR-019; MS-3: `encoding.detect` provenance, path-containment patterns) |
| `plan.schema.json` | DR-002 plan | single JSON document | `plan` (MS-2) | 2.0 (v2 removes the inert `parallel` config snapshot; plan 1.x requires regeneration, while its supported inventory may be reused; OQ-037, adr-0005) |
| `report.schema.json` | DR-003 apply report | single JSON document | `apply` (MS-3) | 2.0 (attempt lineage, explicit `not-attempted` outcomes, and manifest binding; adr-0019) |
| `verify-report.schema.json` | FR-014 verification report | single JSON document | `verify` (Plan D, optional `--out`) | 1.0 |
| `manifest.schema.json` | DR-004 manifest — schema covers **one NDJSON line** | JSON Lines, append-only | `apply` / `restore` (MS-3) | 2.0 (universal write-ahead intents, durable object identities, attempt lineage, and apply/restore kind; adr-0019) |
| `frontmatter.schema.json` | DR-005 product frontmatter — validates the parsed YAML block of a converted document | YAML frontmatter, validated **where present** (`adr-0011`) | none in v1 (emission is a deferred OQ-009 seam); consumed by `verify` (MS-5) | 1.0 |

Conventions (adr-0005):

- **Draft 2020-12**, validated with `jsonschema`'s `Draft202012Validator` + `FormatChecker` (`format` is asserted, not annotation-only — OQ-018).
- **Strict**: every object declares `additionalProperties: false`; drift is rejected, never silently accepted.
- **Versioned**: every instance carries `schema` (artifact kind) and `schema_version` (`MAJOR.MINOR`). Compatibility is backward-only within a supported major unless an approved MAJOR clean break explicitly requires migration or regeneration. MINOR = additive (new optional fields, new enum values); MAJOR = removed/renamed fields or changed meaning. Bump the version and the instance `pattern` together, and record the change in the spec's revision history. Plan 2.0 is such a clean break: v2 rejects plan 1.x with regeneration guidance before schema validation, gate evaluation, or mutation.
- **Identity fields**: `run_id` on every artifact; `action_id` (`<run_id>/a<seq>`) on plan/report/manifest records; `docmend_id` (UUIDv7, adr-0008) on plan actions and manifest records.
- The manifest is NDJSON because a single JSON document cannot be appended crash-safely; one record is appended and fsynced per mutation, during the run, never only at the end (spec 12.3).

The schemas live **inside the package** (`src/docmend/schemas/`) rather than at the repo root so the installed wheel carries them — runtime artifact validation loads them via `importlib.resources`, which must work from any install, not just a repo checkout. (Spec DR-005's `schemas/frontmatter.schema.json` is an illustrative path; the schema landed here at MS-5 for exactly that wheel-carrying reason.)

These artifacts are produced on the operator's machine and contain real library paths — they are never committed (spec 13.4); only the schemas live in this public repo.
