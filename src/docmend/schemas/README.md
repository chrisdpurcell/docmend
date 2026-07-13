# JSON Schemas

The hand-authored JSON Schemas here are the **durable external contract** for docmend's run artifacts (spec DR-001..DR-004 and FR-014, IR-007; canonical decision: `docs/adr/adr-0005-durable-artifact-schema-contract.md`), product frontmatter (DR-005, `adr-0011`), and public scale-qualification records (NFR-001, OQ-038/OQ-041, `adr-0022`). The original four artifact contracts were pinned at MS-1, before any code froze their shapes; the verify-report contract was added by the approved Plan D redesign. The direction of authority is fixed: **code and internal pydantic models conform to these files, never the reverse.** The internal models' emitted JSON Schema is cross-checked against these in tests, but the checked-in files are the contract.

| Schema | Artifact | Representation | Producing command | Current version |
| --- | --- | --- | --- | --- |
| `inventory.schema.json` | DR-001 inventory | single JSON document | `scan` (MS-1) | 1.2 (MS-5: `timeout` scan-skip reason + `skipped_by_reason.timeout` counter, FR-019; MS-3: `encoding.detect` provenance, path-containment patterns) |
| `plan.schema.json` | DR-002 plan | single JSON document | `plan` (MS-2) | 2.0 (v2 removes the inert `parallel` config snapshot; plan 1.x requires regeneration, while its supported inventory may be reused; OQ-037, adr-0005) |
| `report.schema.json` | DR-003 apply report | single JSON document | `apply` (MS-3) | 2.0 (attempt lineage, explicit `not-attempted` outcomes, and manifest binding; adr-0019) |
| `verify-report.schema.json` | FR-014 verification report | single JSON document | `verify` (Plan D, optional `--out`) | 1.0 |
| `manifest.schema.json` | DR-004 manifest — schema covers **one NDJSON line** | JSON Lines, append-only | `apply` / `restore` (MS-3) | 2.0 (universal write-ahead intents, durable object identities, attempt lineage, and apply/restore kind; adr-0019) |
| `frontmatter.schema.json` | DR-005 product frontmatter — validates the parsed YAML block of a converted document | YAML frontmatter, validated **where present** (`adr-0011`) | none in v1 (emission is a deferred OQ-009 seam); consumed by `verify` (MS-5) | 1.0 |

## Scale qualification schemas

Scale qualification records use a separate schema registry and are deliberately absent from the product `ArtifactKind` registry. They are sanitized, aggregate-only repository evidence; operator artifacts, command lines, paths, host identities, and captured child output remain outside the public evidence tree.

| Schema | Contract | Purpose | Current version |
| --- | --- | --- | --- |
| `scale-evidence.schema.json` | DMR-08 qualification evidence | Binds candidate and wheel/build provenance, reference-environment identity, nullable resource preflight, an ordered attempted-stage prefix, measurement-vs-artifact state, phase-truthful totals, finite outcome reasons, threshold verdicts, and release-only workflow runtime. Exact stage artifact-size keys include structured/stdout/stderr logs without exposing their paths or content. Version 2.0 is the clean break for truthful partial and failed evidence (OQ-041). | 2.0 |
| `reference-environment.schema.json` | DMR-08 reference environment | Records the public-safe Linux CPU, memory, storage, filesystem, and value-free mount semantics used to classify a qualification environment. | 1.0 |
| `scale-thresholds.schema.json` | DMR-08 executable thresholds | Binds the exact 10,000- and 100,000-file evidence hashes, shared reference environment, fixed 1,000,000-file target, exact per-stage linear projection method, and frozen peak-RSS, slope, and 1/5 linearity limits. Version 2.0 replaces the obsolete largest-100k absolute ceiling before any baseline is accepted (OQ-041). | 2.0 |

Accepted evidence is passing-only and published without clobbering an existing baseline. Threshold evidence references are canonical safe relative names below the threshold file's directory and are verified against one no-follow snapshot of each referenced file. The loader freezes the four stage-aligned 10k/100k RSS pairs in one immutable context; evaluation does not reread mutable point paths. Publishing accepted scheduled/release evidence additionally reloads that validated baseline and requires both its exact digest and executable limits to match the evidence record.

The scale-evidence writer revalidates the complete model at publication and requires the six product artifact versions to equal their current code-owner constants. Generic readers instead accept the complete finite map of candidate-bound `MAJOR.MINOR` values so a later product-schema bump does not make historical qualification evidence unreadable. JSON Schema enforces every structural state and outcome-precedence rule expressible in Draft 2020-12; cross-field arithmetic such as corpus conservation and threshold/runtime verdict reconciliation is additionally enforced by the Pydantic model because standard JSON Schema cannot compare sibling numeric values.

Conventions (adr-0005):

- **Draft 2020-12**, validated with `jsonschema`'s `Draft202012Validator` + `FormatChecker` (`format` is asserted, not annotation-only — OQ-018).
- **Strict**: every record object declares `additionalProperties: false`; the two intentionally map-shaped qualification fields instead combine a finite `propertyNames` enum with a typed value schema. Unknown record fields and private map labels are rejected, never silently accepted.
- **Versioned**: every instance carries `schema` (artifact kind) and `schema_version` (`MAJOR.MINOR`). Compatibility is backward-only within a supported major unless an approved MAJOR clean break explicitly requires migration or regeneration. MINOR = additive (new optional fields, new enum values); MAJOR = removed/renamed fields or changed meaning. Bump the version and the instance `pattern` together, and record the change in the spec's revision history. Plan 2.0 is such a clean break: v2 rejects plan 1.x with regeneration guidance before schema validation, gate evaluation, or mutation.
- **Identity fields**: `run_id` on every artifact; `action_id` (`<run_id>/a<seq>`) on plan/report/manifest records; `docmend_id` (UUIDv7, adr-0008) on plan actions and manifest records.
- **Qualification separation**: scale evidence, reference environments, and executable thresholds are repository qualification records, not operator run artifacts. Their schemas and validators remain separate from `ARTIFACT_KINDS`.
- The manifest is NDJSON because a single JSON document cannot be appended crash-safely; one record is appended and fsynced per mutation, during the run, never only at the end (spec 12.3).

The schemas live **inside the package** (`src/docmend/schemas/`) rather than at the repo root so the installed wheel carries them — runtime artifact validation loads them via `importlib.resources`, which must work from any install, not just a repo checkout. (Spec DR-005's `schemas/frontmatter.schema.json` is an illustrative path; the schema landed here at MS-5 for exactly that wheel-carrying reason.)

Product artifacts are produced on the operator's machine and contain real library paths, so they are never committed (spec 13.4). Qualification evidence is the narrow exception: only schema-valid, aggregate-only, public-safe records may be reviewed into `docs/scale-evidence/`; private workspace logs and failed or incomplete diagnostic output remain external.
