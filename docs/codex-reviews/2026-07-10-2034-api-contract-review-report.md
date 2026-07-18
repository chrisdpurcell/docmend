# API Contract Review Report

## Findings

### ISSUE-001 — Restore accepts manifest paths without enforcing the recorded root boundary

- first_pass: 2
- severity: high
- confidence: high
- contract_area: file-format-import-export
- issue_type: file-format-contract-gap
- evidence_status: verified directly from repository code and contract text
- affected_contracts: DR-004 manifest, `restore --write`, source-root lock scope, path-containment promise
- evidence:
  - `src/docmend/schemas/manifest.schema.json:48-60` describes `original_path`, `target_path`, and `backup_path` as absolute but constrains them only as non-empty strings.
  - `src/docmend/schemas/manifest.schema.json:93-96` accepts any string or null for `source_root`; it does not require an absolute canonical path or relate record paths to it.
  - `src/docmend/writer/manifest.py:142-170` validates each record structurally and returns it without a containment check.
  - `src/docmend/cli.py:379-394` derives the restore lock from only the first record's `source_root` (or a path common prefix for legacy records).
  - `src/docmend/restore.py:83-103` and `src/docmend/restore.py:146-258` open and mutate `target_path`/`original_path` directly.
  - Spec §13.2 denies writes outside the source root; §13.5 explicitly treats crafted paths as a threat.
  - An executable probe confirmed that a record with `original_path: relative.txt`, `target_path: ../outside.txt`, `source_root: /expected/root`, and otherwise valid fields passes the checked-in manifest schema.
- consumer_impact: A tampered, accidentally mixed, or externally produced manifest can make `restore --write` read or mutate a user-writable file outside the apply run's source tree while holding a lock for a different tree. Relative paths also make the same manifest mean different files under different working directories, contradicting the documented "restore from anywhere" contract.
- compatibility_direction: unsafe acceptance; tightening this requires an explicit malformed-artifact policy but should not reject genuine docmend manifests because the writer already emits resolved absolute paths.
- recommendation: At the restore boundary, require one canonical absolute `source_root`, require every original/target path to be an absolute descendant of that root, re-check containment and object identity immediately before mutation, and reject mixed-root records. Keep backup paths separately scoped because they are intentionally outside the mutation root. Add adversarial restore tests. Request a follow-on `security-review` because this overlaps filesystem authorization and trust-boundary enforcement.

### ISSUE-002 — Manifest validation omits the semantic and run-level invariants recovery relies on

- first_pass: 2
- severity: high
- confidence: high
- contract_area: file-format-import-export
- issue_type: file-format-contract-gap
- evidence_status: verified directly and by executable probes
- affected_contracts: DR-004 manifest, resume, restore, verify, append-only truncation detection
- evidence:
  - `src/docmend/schemas/manifest.schema.json:38-41` requires only `seq >= 1`; monotonicity, uniqueness, and contiguity exist only in the description.
  - `src/docmend/writer/manifest.py:150-170` validates lines independently and never checks manifest-wide run ID, schema version, source root, sequence, action lifecycle, or duplicate-final-record invariants.
  - `src/docmend/schemas/manifest.schema.json:63-83` permits every `result` value with either null or non-null `after_sha256` and either null or non-null `error`.
  - `src/docmend/restore.py:95` checks the live after-hash only when `after_sha256` is non-null. Therefore a schema-valid `result: applied` record with `after_sha256: null` bypasses the documented modified-since-apply guard.
  - `src/docmend/restore.py:121-124` trusts `seq` as the LIFO order.
  - Probes confirmed that `read_manifest()` accepts sequence `[2, 1]` and that the schema accepts an applied record with no after-hash, relative/out-of-root paths, and no error.
- consumer_impact: Corrupt or mixed manifests can reorder recovery, hide truncation, bypass the live-content guard, confuse dangling-intent reconciliation, or place records from multiple runs/roots under one recovery operation. These are safety properties, not cosmetic schema quality.
- compatibility_direction: reader hardening; existing writer output should remain valid.
- recommendation: Add a manifest-set validator before resume/restore/verify. Enforce one schema version family, coherent run/source-root identity, writer-order sequence rules, unique lifecycle transitions, and result-dependent fields. At minimum: `applied => after_sha256 != null && error == null`; `failed => error != null`; `intent => operation == rename_and_rewrite && after_sha256 != null && error == null`. Reject ambiguous duplicate terminal records unless a documented cross-attempt reconciliation rule explicitly owns them.

### ISSUE-003 — The authoritative report schema and the internal consumer model disagree

- first_pass: 2
- severity: medium
- confidence: high
- contract_area: consumer-provider-alignment
- issue_type: consumer-provider-gap
- evidence_status: verified directly and by executable probe
- affected_contracts: DR-003 report, `verify --report`, external schema consumers
- evidence:
  - `src/docmend/schemas/report.schema.json:88-91` defines `skip_reason` as any string or null.
  - `src/docmend/report.py:20-34` narrows it to the closed `ApplySkipReason` literal set.
  - `src/docmend/artifacts.py:175-188` first accepts the document against the authoritative schema, then calls `Report.model_validate()` without converting a Pydantic failure to `ArtifactError`.
  - A probe passed `future-conforming-reason` through `validate_artifact("report", ...)` and then received a Pydantic validation failure at `outcomes[0].skip_reason`.
  - `src/docmend/schemas/README.md:3` states that the checked-in schema is authoritative and models conform to it, never the reverse.
- consumer_impact: A report valid under the published contract can be rejected by docmend itself. In the CLI path the error also escapes the documented artifact-error handling and exit-2 semantics. Any additive reason introduced at the schema/provider boundary is especially likely to break the strict model consumer.
- compatibility_direction: current provider/consumer mismatch; future additive evolution is unsafe.
- recommendation: Choose one contract. Either enumerate the exact closed vocabulary in the authoritative schema and guard it against the Python literal, or accept arbitrary contract-valid reason strings in the model. Wrap every post-schema model validation error as `ArtifactError` so malformed inputs retain the documented error taxonomy.

### ISSUE-004 — Aggregate and cross-field invariants are enforced only on selected write paths

- first_pass: 2
- severity: medium
- confidence: high
- contract_area: serialization-and-validation
- issue_type: serialization-validation-gap
- evidence_status: verified directly and by executable probe
- affected_contracts: DR-001 inventory totals, DR-002 plan totals, DR-003 report totals, verify artifact consistency
- evidence:
  - `src/docmend/artifacts.py:157-172` reconciles report totals only in `write_report()`.
  - `src/docmend/artifacts.py:175-188` does not repeat that check in `read_report()`.
  - `src/docmend/verify.py:117-123` incorrectly states that `read_report()` already enforces totals equality.
  - A probe changed `totals.would_apply` from 1 to 999; `read_report()` accepted it.
  - `src/docmend/schemas/inventory.schema.json:234-265` says aggregate counts must reconcile with record arrays, but JSON Schema only constrains individual non-negative integers.
  - `src/docmend/plan.py:84-108` and `src/docmend/artifacts.py:131-154` similarly provide no actions/skips-to-totals reconciliation on read or write.
- consumer_impact: Operator-edited or corrupted artifacts can validate and be displayed or verified with false counts. `verify` can report clean cross-artifact accounting while a report's authoritative summary is internally wrong. Inventory and plan summaries can likewise drift from the record arrays.
- compatibility_direction: validation tightening; valid producer output is unaffected.
- recommendation: Put aggregate and status-dependent checks in shared model/reader validators that run for both produced and consumed artifacts. Add read-side tests for each mismatch and make `verify` surface or reject them consistently.

### ISSUE-005 — JSON artifacts silently collapse duplicate member names

- first_pass: 4
- severity: medium
- confidence: high
- contract_area: serialization-and-validation
- issue_type: serialization-validation-gap
- evidence_status: verified directly, by executable probe, and against shared research
- affected_contracts: inventory, plan, report, manifest, schema loader
- evidence:
  - `src/docmend/artifacts.py:70,123,149,183` and `src/docmend/writer/manifest.py:162` use default `json.loads()` behavior.
  - No parser supplies an `object_pairs_hook` that rejects duplicate keys.
  - A probe supplied two `schema_version` members; the parser retained only the last value (`1.99`) and validation saw no ambiguity.
  - The shared research pack cites RFC 8259's interoperability warning that duplicate-name handling is unpredictable across implementations.
- consumer_impact: Two conforming consumers may interpret the same artifact differently. Duplicated path, hash, result, or version fields are especially dangerous because validation observes only the locally retained value.
- compatibility_direction: malformed-input rejection; docmend-produced JSON already emits unique keys.
- recommendation: Centralize strict JSON decoding with duplicate-member rejection and use it for all JSON and NDJSON reads. Add tests that duplicate each compatibility-sensitive field family.

### ISSUE-006 — Schema versions identify a family but do not select or enforce supported semantics

- first_pass: 4
- severity: medium
- confidence: high
- contract_area: versioning-and-deprecation
- issue_type: versioning-deprecation-gap
- evidence_status: verified directly; external consumer behavior remains unverified
- affected_contracts: all five schemas, backward-only policy, released artifact compatibility
- evidence:
  - Every `schema_version` constraint accepts any `1.x` value (`src/docmend/schemas/*.schema.json`); the Python models use the same broad pattern.
  - `src/docmend/cli.py:494-500` rejects a newer plan minor only in `apply`. Inventory, report, manifest, frontmatter, and other reader contexts have no equivalent supported-version dispatch.
  - Probes confirmed that current plan, report, and manifest shapes remain schema-valid when labeled `1.999`.
  - `src/docmend/schemas/README.md:17` promises backward-only compatibility and says to bump the instance pattern, but the patterns are family-wide and unchanged across minor versions.
  - Schema `$id` values are unversioned; four point at mutable `main`, while frontmatter uses a different non-raw repository URL.
  - Tests cover current shapes and one simulated pre-1.2 manifest field omission, but there is no golden corpus of genuine historical artifacts from v1.0.0/v1.0.1/v1.0.2 or explicit migration/rejection tests per artifact kind.
- consumer_impact: A version label does not determine the applicable field/enum semantics. Future-minor artifacts can be accepted and interpreted as current in some paths, rejected after schema acceptance in others, and cannot be reliably resolved to a versioned published schema by external consumers.
- compatibility_direction: ambiguous in both directions; the documented newer-reader/older-artifact guarantee lacks full release-baseline evidence.
- recommendation: Define supported versions per artifact kind, dispatch validation/migration by exact version, and reject unsupported future minors before model construction. Publish immutable versioned schema identities or document how release-tag/package schemas are resolved. Preserve golden historical artifacts and test every supported upgrade/rejection path.

### ISSUE-007 — The binding spec and shipped CLI disagree on verify/report interfaces

- first_pass: 3
- severity: medium
- confidence: high
- contract_area: documentation-and-examples
- issue_type: documentation-drift-gap
- evidence_status: verified directly from spec, CLI code, generated help, and README
- affected_contracts: IR-004, FR-018, spec §18.5, CLI automation
- evidence:
  - Spec IR-004 documents `docmend verify PATH [--manifest FILE] [--report FILE] [--plan FILE]` and requires findings in output/report.
  - `src/docmend/cli.py:767-865` and generated `docmend verify --help` have no `--plan` option and do not produce a verification-result artifact.
  - Spec FR-018 requires a DR-003 machine-readable report for every plan and apply run; `plan` produces only the DR-002 plan artifact.
  - Spec §18.5 says every scan, plan, apply, and verify run emits a machine-readable artifact with start/finish, per-file outcomes/reasons, and summary counts; verify emits console output and a log but no result artifact.
  - `README.md:29-31` matches the implementation, so the binding specification—not the user guide—is the drifting source.
  - Repo convention #3 states that the spec is binding and mismatches require an explicit OQ/DEV path.
- consumer_impact: A wrapper implemented against the binding interface cannot supply `--plan` or collect the promised verification artifact. The project also cannot make one consistent claim about which commands emit DR-003 reports/job records.
- compatibility_direction: documentation/implementation ambiguity; either resolution can be breaking for a consumer following the other source.
- recommendation: Decide the intended interface, then reconcile the spec, README/help, implementation, tests, and traceability matrix through the spec/ADR process. Do not silently declare one source non-authoritative.

### ISSUE-008 — `run_id` and `action_id` ownership is ambiguous across plan, report, and manifest

- first_pass: 3
- severity: low
- confidence: high
- contract_area: consumer-provider-alignment
- issue_type: consumer-provider-gap
- evidence_status: verified directly; external joins not inspected
- affected_contracts: cross-artifact correlation, resume, third-party artifact consumers
- evidence:
  - `src/docmend/schemas/README.md:18` says `action_id` is `<run_id>/a<seq>` on plan/report/manifest records without distinguishing which run ID.
  - `src/docmend/writer/apply.py:149-168` writes a manifest record whose top-level `run_id` is the apply attempt while `action_id` comes from the plan action.
  - `src/docmend/cli.py:481-498,532-534` creates a new apply run ID but preserves the plan run in `plan_ref.run_id`.
  - Report outcomes follow the same plan-action/apply-run split; manifests have no explicit `plan_ref`.
- consumer_impact: A consumer can incorrectly assume `action_id.startswith(manifest.run_id)` or `action_id.startswith(report.run_id)`. The report's `plan_ref` permits a correct join, but the manifest makes the intended provenance implicit.
- compatibility_direction: documentation ambiguity in the current format.
- recommendation: Document the two identities explicitly (`plan_run_id`/minting run versus apply-attempt `run_id`), state the required joins, and add semantic tests. Consider adding an optional plan reference to a future manifest minor rather than changing existing IDs.

### ISSUE-009 — The UUIDv7 identity contract is not validated

- first_pass: 5
- severity: low
- confidence: high
- contract_area: serialization-and-validation
- issue_type: serialization-validation-gap
- evidence_status: verified directly and by executable probe
- affected_contracts: `docmend_id` in plan, manifest, and frontmatter
- evidence:
  - Plan and manifest schema descriptions require UUIDv7, but use only JSON Schema `format: uuid` (`plan.schema.json:55-58`, `manifest.schema.json:33-37`).
  - `src/docmend/plan.py:25-28` checks only the generic textual UUID shape.
  - A valid UUIDv4 (`123e4567-e89b-42d3-a456-426614174000`) passed the plan schema under the UUIDv7 contract.
- consumer_impact: Externally produced or edited artifacts can claim a stable identity that violates the specified generation/version rule. This is unlikely to break current restore logic, but it weakens a durable identity promise used across renames and manifests.
- compatibility_direction: validation tightening; current docmend-generated UUIDv7 values remain valid.
- recommendation: Add a UUIDv7-specific semantic validator to plan, manifest, and frontmatter validation, plus positive/negative fixtures.

### ISSUE-010 — CLI and TOML compatibility/deprecation policy is not defined at contract granularity

- first_pass: 4
- severity: low
- confidence: medium
- contract_area: versioning-and-deprecation
- issue_type: versioning-deprecation-gap
- evidence_status: inferred from repository-wide documentation search
- affected_contracts: Typer command/options, exit codes, `docmend.toml`, Python import surface
- evidence:
  - `CHANGELOG.md` states package Semantic Versioning, but no document maps SemVer to CLI flag removal/rename, output text, exit-code changes, config-key changes, or import stability.
  - `DocmendConfig` is strict (`extra="forbid"`) and unversioned; no config migration/deprecation mechanism or compatibility window is documented.
  - The package ships `py.typed` and many importable modules, but `src/docmend/__init__.py` exports only `__version__` and does not declare whether any Python API beyond that is supported.
- consumer_impact: Shell wrappers, persisted TOML, and Python callers cannot tell which changes are breaking or how long deprecated surfaces remain supported.
- compatibility_direction: future-risk ambiguity rather than a demonstrated current regression.
- recommendation: Define the supported public surfaces and SemVer rules. Include CLI option names/placement, exit codes, machine-readable artifacts, config keys/defaults, and any supported Python imports; state a deprecation window and migration behavior.

## Review Metadata

- repo_path: `.`
- repo_name: `docmend`
- review_type: `api-contract-review`
- review_mode: read-only review; only this report is written
- report_path: `docs/codex-reviews/2026-07-10-2034-api-contract-review-report.md`
- review_date: `2026-07-10`
- current_branch: `dev`
- head_commit: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- working_tree_state_at_start: dirty; pre-existing `M AGENTS.md` and untracked `docs/codex-reviews/`
- detected_api_styles_and_protocols: Typer CLI; TOML config; JSON documents; NDJSON manifest/logs; YAML frontmatter; typed Python package modules
- schemas_or_contract_artifacts_inspected: all five `src/docmend/schemas/*.schema.json`; schema README; CLI/help; config; inventory/plan/report/manifest models and readers; restore/resume/verify consumers; binding spec; ADRs 0005/0006/0011; README/runbooks; contract tests
- generated_clients_or_sdks_inspected: none exist
- prior_baseline_or_release_artifacts_compared: git tags `v1.0.0`, `v1.0.1`, `v1.0.2`; schema/code diffs; no committed historical golden artifact corpus exists
- important_external_contract_artifacts_not_in_repo: real operator artifacts; any wrapper repository/runtime; GitHub release wheels/settings; external consumer code
- research_reused: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
- targeted_follow_up_web_research: not needed; shared research already covered JSON Schema 2020-12, RFC 8259 duplicate-member behavior, packaging contracts, and filesystem trust boundaries
- validation:
  - focused contract suite: `90 passed` with `XDG_STATE_HOME=/tmp/docmend-state UV_CACHE_DIR=/tmp/docmend-uv-cache uv run pytest -q tests/test_schemas.py tests/test_inventory_artifact.py tests/test_plan_artifact.py tests/test_report_artifact.py tests/unit/writer/test_manifest.py tests/test_cli.py tests/test_cli_verify.py`
  - initial focused run: `83 passed, 7 failed` solely because the review sandbox's default XDG state path was read-only; rerun above isolated state and passed
  - executable probes: confirmed ISSUE-002, ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-006, and ISSUE-009 acceptance/rejection behavior without modifying repository files
  - report formatting: Prettier and targeted markdownlint passed after consolidation cleanup

## Contract Area Matrix

| contract_area | applicability | status | evidence_or_issue_ids |
| --- | --- | --- | --- |
| rest-http | not needed for this repo | not applicable | no server/routes/HTTP runtime |
| graphql | not needed for this repo | not applicable | no GraphQL schema/runtime |
| grpc-protobuf | not needed for this repo | not applicable | no protobuf or gRPC surface |
| rpc-or-internal-service | limited | ambiguity | typed Python modules exist, but supported public imports are undefined; ISSUE-010 |
| events-webhooks | not needed for this repo | not applicable | no events/webhooks/network boundary |
| streaming-realtime | not needed for this repo | not applicable | no resident or streaming service |
| file-format-import-export | primary | high risk | ISSUE-001, ISSUE-002 |
| serialization-and-validation | primary | gaps | ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-009 |
| error-semantics | relevant | gap | ISSUE-003 can escape the documented `ArtifactError`/exit-2 path |
| versioning-and-deprecation | primary | gaps | ISSUE-006, ISSUE-010 |
| generated-clients-sdks | not needed for this repo | not applicable | none exist |
| consumer-provider-alignment | relevant | gaps | ISSUE-003, ISSUE-008 |
| backward-compatibility | relevant | insufficiently protected | ISSUE-006; only narrow simulated historical coverage |
| documentation-and-examples | relevant | drift | ISSUE-007, ISSUE-008 |
| contract-testing | primary | gaps | ISSUE-001 through ISSUE-006 and ISSUE-009 lack negative/historical cases |

## Severity Summary

| severity | count | issue_ids                                             |
| -------- | ----: | ----------------------------------------------------- |
| critical |     0 | none                                                  |
| high     |     2 | ISSUE-001, ISSUE-002                                  |
| medium   |     5 | ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-006, ISSUE-007 |
| low      |     3 | ISSUE-008, ISSUE-009, ISSUE-010                       |

## Compatibility Break Risks

- immediate_break_risks:
  - ISSUE-003: a schema-valid report can fail the internal model and documented error path.
  - ISSUE-007: spec-driven wrappers can request unsupported verify/report behavior.
- future_break_risks:
  - ISSUE-006: broad version patterns and no version dispatch make additive evolution unpredictable.
  - ISSUE-008: consumers may join action IDs to the wrong run identity.
  - ISSUE-010: CLI/config/Python compatibility rules and deprecation windows are unspecified.
- strict_consumer_risk: `additionalProperties: false` is intentional, but additive optional fields and enum values are still breaking to older strict consumers; the current policy acknowledges this only partially.
- ordering_guarantees: manifest order is described through `seq` but not validated (ISSUE-002).
- timestamp_and_timezone_behavior: JSON Schema format assertions are enabled; no new issue found. Manifest-wide chronological coherence is not asserted and is part of ISSUE-002.
- pagination_partial_update_idempotency: not needed for this repo; no paginated or partial-update network API. Apply/resume idempotency has substantial direct test coverage.

## Ambiguity And Drift Risks

- schema_vs_model: ISSUE-003.
- schema_description_vs_enforcement: ISSUE-001, ISSUE-002, ISSUE-004, ISSUE-009.
- version_label_vs_semantics: ISSUE-006.
- binding_spec_vs_shipped_cli: ISSUE-007.
- run_identity_ownership: ISSUE-008.
- public_surface_definition: ISSUE-010.
- verified_no_drift:
  - CLI README command descriptions match generated help for the current implementation.
  - Config defaults have direct tests and no review-specific mismatch was found.
  - Frontmatter YAML duplicate-key rejection and JSON Schema `format` assertion are implemented and tested.

## Consumer Inventory And Visibility

- verified_in_repo_consumers:
  - Typer CLI users and shell automation.
  - `plan` consuming inventory.
  - `apply` consuming plan and optional resume manifests.
  - `restore` consuming manifests.
  - `verify` consuming corpus state, manifests, reports, and frontmatter.
  - Python tests/importers using internal models and functions.
- inferred_consumers:
  - User-maintained wrappers around exit codes and `.docmend/` sidecar names.
  - The separately referenced `doc-proc-scripts` boundary; its code was outside this repo and was not inspected.
  - Users installing GitHub release wheels and retaining artifacts indefinitely.
- externally_visible_artifacts:
  - CLI command/options/help and exit codes.
  - `docmend.toml`.
  - Inventory, plan, report, manifest, frontmatter, log, and sidecar naming conventions.
  - Packaged JSON Schemas and `py.typed` marker.
- visibility_limitations:
  - No real-library artifacts were inspected.
  - No external consumer repository or automation was inspected.
  - No GitHub release assets, wheel contents, or remote schema URLs were fetched in this child review.

## Schema And Validation Gaps

- ISSUE-001: manifest root/path containment.
- ISSUE-002: manifest result/lifecycle/sequence/run invariants.
- ISSUE-003: report schema/model vocabulary drift.
- ISSUE-004: aggregate reconciliation on reads.
- ISSUE-005: duplicate JSON member rejection.
- ISSUE-006: exact version dispatch and versioned schema identity.
- ISSUE-009: UUIDv7 semantics.
- nullability_and_optional_fields:
  - Inventory/plan compatibility fields intentionally distinguish absent and null in several places.
  - Manifest result-dependent nullability is not enforced (ISSUE-002).
- defaults_and_server_side_fills:
  - Pydantic defaults support some older optional artifact fields.
  - No migration layer establishes which defaults are safe for each historical schema version (ISSUE-006).
- enum_expansion:
  - Manifest 1.3 added `intent` consistently for the current writer/reader.
  - Report `skip_reason` exposes a free-string schema but a closed model (ISSUE-003).
- bounds:
  - Numeric bounds are generally explicit.
  - No review finding was raised solely for unbounded strings/arrays because the CLI's local trusted-user model and file-size guard reduce immediate impact; residual resource-exhaustion risk remains for externally supplied artifact files.

## Auth And Permission Semantics Risks

- authentication: not needed for this repo; local single-user CLI, no service or network identity.
- authorization: the invoking user's OS identity is the authority.
- primary_risk: ISSUE-001 violates the product-level promise that writes are scoped to the recorded source root.
- follow_on: Run a `security-review` focused on restore manifests, symlink/TOCTOU behavior, object identity at mutation time, and attacker-modifiable artifact/corpus assumptions.

## Versioning And Deprecation Risks

- ISSUE-006: artifact version labels do not select exact semantics or migration behavior.
- ISSUE-010: CLI/config/import compatibility and deprecation rules are unspecified.
- release_baseline_observation: v1.0.2 adds manifest schema 1.3 over the v1.0.0/1.0.1 era; current-reader compatibility is covered behaviorally for current code, but not by immutable historical artifact fixtures.
- schema_publication_observation: unversioned mutable `$id` URLs weaken independent consumer reproducibility.

## Generated Client And Consumer Risks

- generated_clients_sdks: not needed for this repo; none exist.
- client_generation_drift: not applicable.
- consumer_alignment_risks: ISSUE-003 and ISSUE-008.
- Python consumer note: the package is typed but does not identify a supported library API (ISSUE-010).

## Contract Testing Gaps

- no negative restore tests proving a crafted manifest cannot escape its recorded root (ISSUE-001).
- no manifest-set validation tests for sequence, mixed roots/runs/versions, illegal lifecycle transitions, or applied-without-after-hash (ISSUE-002).
- no test that every schema-valid report is model-valid; nested vocabulary alignment is incomplete (ISSUE-003).
- no read-side totals mismatch tests for report/inventory/plan (ISSUE-004).
- no duplicate JSON member tests (ISSUE-005).
- no per-release golden artifact corpus and version migration/rejection matrix (ISSUE-006).
- no contract test reconciling generated CLI help, README, and binding spec (ISSUE-007).
- no UUID-version negative fixtures (ISSUE-009).
- strong_existing_evidence:
  - current schema validity/strictness and minimal satisfiability.
  - current artifact round trips.
  - torn-unterminated-tail versus newline-terminated-corruption manifest behavior.
  - frontmatter duplicate YAML keys and date-time format assertion.
  - apply/resume/restore/verify happy paths and many interruption cases.

## Convention Recommendations

- convention_alignment:
  - Conventions #1/#2 are followed by the current test/tooling setup.
  - Convention #3 is violated by the unresolved binding-spec/interface drift in ISSUE-007.
  - Convention #6 was followed during this review; no real paths or private corpus content were added.
  - Convention #7 correctly separates product frontmatter from repo-document frontmatter.
- recommended_contract_conventions:
  - Define one strict artifact-read pipeline: duplicate-safe decode, exact-version dispatch, authoritative-schema validation, model validation mapped to `ArtifactError`, then semantic/set invariants.
  - State whether every schema description is normative; if so, test semantic claims such as absolute paths, UUIDv7, and count reconciliation.
  - Preserve immutable golden artifacts from every released schema version.
  - Define CLI/config/import SemVer and deprecation rules.
  - Reconcile spec/help/README contract surfaces in one change and gate future drift mechanically.

## Pass Log

| pass | lens | new_issue_ids | result |
| --: | --- | --- | --- |
| 1 | inventory: CLI, config, schemas, artifacts, consumers, external surfaces, applicability | none | meaningful surface isolated; network categories marked not needed |
| 2 | request/response equivalents: serialization, validation, error semantics, path/permission semantics | ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-004 | direct high/medium contract gaps found |
| 3 | consumer/provider alignment, docs, conventions, published artifact meaning | ISSUE-007, ISSUE-008 | binding-spec and identity ambiguity found |
| 4 | backward compatibility, versioning, malformed JSON, historical tags, test coverage | ISSUE-005, ISSUE-006, ISSUE-010 | version and parser gaps found |
| 5 | adaptive probes for semantic schema claims and strict identity | ISSUE-009 | UUIDv7 enforcement gap confirmed |
| 6 | exhaustive parser/validator call-site sweep, remaining public/import surface | none | first convergence pass |
| 7 | baseline diff review, generated CLI help, focused contract tests, schema ID inventory | none | second consecutive convergence pass; review stopped |

## Claude Handoff

- highest_priority:
  1. Fix ISSUE-001 before trusting restore against operator-editable or externally stored manifests.
  2. Fix ISSUE-002 in the same manifest-read/restore design because containment alone does not restore the after-hash and sequence safety invariants.
  3. Run a focused `security-review` over the resulting restore boundary.
- next_priority:
  1. Align the authoritative schema and model (ISSUE-003).
  2. Centralize read-side semantic validation and duplicate rejection (ISSUE-004, ISSUE-005).
  3. Define exact artifact version dispatch and add historical fixtures (ISSUE-006).
- change_control:
  - Resolve ISSUE-007 through the binding spec/OQ/DEV/ADR workflow before implementation.
  - Treat schema tightening as malformed-input rejection and verify genuine v1.0.0-v1.0.2 artifacts remain accepted or receive an explicit migration/refusal message.
- suggested_validation_after_fixes:
  - Full local gate from conventions #1/#2.
  - New hostile-manifest restore tests with zero outside-root mutation.
  - Historical artifact matrix across every supported schema version.
  - Installed-wheel contract tests to prove packaged schemas and CLI behavior match the source checkout.

## Open Questions Or Assumptions

- Is an artifact attacker-modifiable, or only accidentally corrupt/operator-edited? The binding spec already treats crafted paths as a threat, so ISSUE-001 does not depend on the answer; it changes defense depth and severity rationale only.
- Should `verify` produce a dedicated durable result artifact, should DR-003 expand beyond apply, or should the binding spec be narrowed to the shipped behavior?
- Is `--plan` intentionally deferred/removed from verify, or omitted accidentally?
- What exact artifact versions must v1.0.2 read, migrate, apply, restore, and verify?
- Are schema `$id` values intended as retrievable publication URLs or identifiers only?
- Which Python imports, if any, are supported for external callers beyond `docmend.__version__`?
- Are console text and sidecar filenames stable automation contracts, or are only exit codes and structured artifacts stable?

## Residual Risk

- high: Until ISSUE-001 and ISSUE-002 are fixed, restore safety depends on every manifest being authentic, internally coherent, and produced by the current writer despite the schema and CLI presenting manifests as durable external inputs.
- medium: External wrappers and historical artifacts were not available, so actual compatibility breakage may be broader than the in-repo evidence.
- medium: This review did not execute destructive hostile-manifest tests; it established the reachable code path and schema acceptance without mutating a target.
- low: No network/auth/generated-client surfaces exist, so those categories add no hidden protocol risk in the current repository.
- research_limit: No broad internet research was performed because the provided 2026-07-10 shared research artifact already supplied current primary guidance for JSON Schema, JSON parsing, compatibility, packaging, and filesystem boundaries.
