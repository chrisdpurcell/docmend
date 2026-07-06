# Artifact JSON Schemas

The four hand-authored JSON Schemas here are the **durable external contract** for docmend's run artifacts (spec DR-001..DR-004, IR-007; canonical decision: `docs/adr/adr-0005-durable-artifact-schema-contract.md`). They were pinned at MS-1, before any code froze their shapes, and the direction of authority is fixed: **code and internal pydantic models conform to these files, never the reverse.** The internal models' emitted JSON Schema is cross-checked against these in tests, but the checked-in files are the contract.

| Schema | Artifact | Representation | Producing command |
| --- | --- | --- | --- |
| `inventory.schema.json` | DR-001 inventory | single JSON document | `scan` (MS-1) |
| `plan.schema.json` | DR-002 plan | single JSON document | `plan` (MS-2) |
| `report.schema.json` | DR-003 apply report | single JSON document | `apply` (MS-3) |
| `manifest.schema.json` | DR-004 manifest — schema covers **one NDJSON line** | JSON Lines, append-only | `apply` (MS-3) |

Conventions (adr-0005):

- **Draft 2020-12**, validated with `jsonschema`'s `Draft202012Validator` + `FormatChecker` (`format` is asserted, not annotation-only — OQ-018).
- **Strict**: every object declares `additionalProperties: false`; drift is rejected, never silently accepted.
- **Versioned**: every instance carries `schema` (artifact kind) and `schema_version` (`MAJOR.MINOR`). Compatibility policy is **backward-only**: a newer tool must read (or migrate) older artifacts. MINOR = additive (new optional fields, new enum values); MAJOR = removed/renamed fields or changed meaning. Bump the version and the instance `pattern` together, and record the change in the spec's revision history.
- **Identity fields**: `run_id` on every artifact; `action_id` (`<run_id>/a<seq>`) on plan/report/manifest records; `docmend_id` (UUIDv7, adr-0008) on plan actions and manifest records.
- The manifest is NDJSON because a single JSON document cannot be appended crash-safely; one record is appended and fsynced per mutation, during the run, never only at the end (spec 12.3).

The schemas live **inside the package** (`src/docmend/schemas/`) rather than at the repo root so the installed wheel carries them — runtime artifact validation loads them via `importlib.resources`, which must work from any install, not just a repo checkout. (Spec DR-005's `schemas/frontmatter.schema.json` is an illustrative path, and that schema will live here too when it lands at MS-5.)

These artifacts are produced on the operator's machine and contain real library paths — they are never committed (spec 13.4); only the schemas live in this public repo.
