# Data Schema And Migration Review Report

## Findings

### ISSUE-001 — Single-step mutations can become durable before their recovery record exists

- first_pass: 2
- severity: high
- confidence: high
- data_area: migration-safety-ordering
- issue_type: migration-safety-gap
- evidence_status: verified directly from repository code, tests, runbook, ADR, and shared research
- change_class: destructive file mutation and recovery-journal ordering
- affected_surfaces: `apply`, resume, manifest, tool backups, restore
- evidence:
  - `src/docmend/writer/apply.py:485-503` writes a durable intent before `rename_and_rewrite`, but explicitly excludes the single-step `rewrite` and `rename` paths.
  - `src/docmend/writer/apply.py:505-512` performs the single-step filesystem mutation; `src/docmend/writer/apply.py:562-583` appends the applied manifest record only afterward.
  - A kill or power loss between those blocks leaves converted or renamed corpus state without a durable record containing its backup path and before/after identity.
  - `tests/test_resume.py:233-263` models the resulting lost-record state and accepts a `stale-hash` or `unreadable` finding rather than recovering the missing record.
  - `docs/runbooks/resume-after-interruption.md:54` says the operator must inspect the file and manually locate the backup after a lost record.
  - This conflicts with `docs/specs/docmend.md:704-706`, `docs/adr/adr-0006-resume-and-recovery-model.md:59-64`, and `src/docmend/schemas/README.md:19`, which describe every completed mutation as incrementally and durably recorded.
  - The shared research pack requires a documented commit order and interruption result at every boundary and recommends write-ahead/checkpoint evidence before mutation.
- impact: A crash can leave a correctly converted file that resume will not adopt, a rename that resume sees only as a missing source, and a backup whose location is absent from the recovery ledger. The corpus is protected from a second blind mutation by source hashes, but rollback is no longer mechanical and the manifest/report cannot prove complete mutation coverage.
- recommendation: Extend the write-ahead lifecycle to every mutation kind. Persist an intent containing source/target paths, before hash, expected after hash, backup references, overwrite references, and source root before the first mutation; then append a terminal applied/failed record. On resume, reconcile a dangling intent against both source and target state and adopt, complete, or refuse deterministically. Add injected-kill tests immediately after each successful rewrite/rename and before its terminal append.

### ISSUE-002 — Restore does not enforce the manifest's recorded source-root boundary

- first_pass: 2
- severity: high
- confidence: high
- data_area: rollback-recovery
- issue_type: rollback-recovery-gap
- evidence_status: verified directly from repository code, contract text, and an executable schema probe
- change_class: destructive restore operation
- affected_surfaces: manifest import, `restore --write`, restore locking, backup reads
- evidence:
  - `src/docmend/schemas/manifest.schema.json:48-60` constrains original, target, and backup paths only as non-empty strings despite describing them as absolute.
  - `src/docmend/schemas/manifest.schema.json:93-95` accepts any string or null for `source_root` and does not relate record paths to it.
  - `src/docmend/writer/manifest.py:142-170` validates each record structurally without path containment or mixed-root checks.
  - `src/docmend/cli.py:379-394` chooses the restore lock from only the first record's root or a legacy common path.
  - `src/docmend/restore.py:48-103` and `src/docmend/restore.py:146-258` read and mutate manifest paths directly.
  - Spec sections 13.2 and 13.5 promise writes remain inside the configured source root and identify crafted path escape as a threat.
  - The review probe confirmed that an otherwise valid record with `/outside/...` original/target/backup paths and `/intended/root` as `source_root` passes both the checked-in schema and `ManifestRecord` validation.
- impact: A tampered, accidentally mixed, or externally produced manifest can make restore read or mutate user-writable files outside the apply run's corpus while holding a lock for another tree. The live after-hash and backup-hash checks reduce accidental matches but do not establish authorization or containment.
- recommendation: Before lock acquisition and again at the actual mutation boundary, require a coherent canonical absolute source root and require every original/target path to be an absolute descendant of it. Reject mixed-root manifests. Treat backup paths as a separate read-only trust boundary and validate their absolute/canonical form and expected identity. Add hostile-manifest tests proving zero outside-root reads, writes, links, replacements, or unlinks.

### ISSUE-003 — Manifest records and record sets omit recovery-critical semantic invariants

- first_pass: 3
- severity: high
- confidence: high
- data_area: constraints-indexes-integrity
- issue_type: constraints-integrity-gap
- evidence_status: verified directly and by executable probe
- change_class: durable recovery schema and state-machine integrity
- affected_surfaces: manifest, resume, restore, verify
- evidence:
  - `src/docmend/schemas/manifest.schema.json:38-41` requires only `seq >= 1`; monotonicity, uniqueness, contiguity, and writer order are descriptive rather than enforced.
  - `src/docmend/writer/manifest.py:150-170` validates lines independently and does not validate one run ID, schema version, source root, sequence, action identity, or lifecycle across the record set.
  - `src/docmend/schemas/manifest.schema.json:63-83` permits every result with either a null or non-null `after_sha256` and either a null or non-null error.
  - `src/docmend/restore.py:95` checks the live after-hash only when it is non-null. A schema-valid `result: applied` record with `after_sha256: null` therefore disables the modified-since-apply guard.
  - `src/docmend/restore.py:121-124` trusts `seq` for LIFO recovery ordering.
  - The probe accepted one record combining `result: applied`, `after_sha256: null`, a non-null error, out-of-root paths, `seq: 7`, and an `action_id` minted by a different run.
- impact: Structurally valid but semantically impossible records can bypass the live-content guard, reorder rollback, hide truncation, confuse dangling-intent resolution, or mix multiple runs and roots into one recovery operation.
- recommendation: Add a manifest-set validator used before resume, restore, and verify. Enforce one schema version family, coherent run/root identity, sequence rules, valid action/run provenance, and legal state transitions. At minimum require `applied => after_sha256 != null && error == null`, `failed => error != null`, and `intent => operation == rename_and_rewrite && after_sha256 != null && error == null`; define whether failed records may carry after hashes and whether duplicate terminal records are legal across attempts.

### ISSUE-004 — The report schema accepts values the internal consumer rejects

- first_pass: 4
- severity: medium
- confidence: high
- data_area: schema-model-alignment
- issue_type: schema-model-gap
- evidence_status: verified directly and by executable probe
- change_class: schema/model compatibility
- affected_surfaces: DR-003 report, `read_report`, `verify --report`
- evidence:
  - `src/docmend/schemas/report.schema.json:88-91` permits any string or null for `skip_reason`.
  - `src/docmend/report.py:20-34` narrows the field to a closed `ApplySkipReason` literal vocabulary.
  - `src/docmend/artifacts.py:175-188` first accepts the authoritative schema, then calls `Report.model_validate()` without mapping a Pydantic `ValidationError` to `ArtifactError`.
  - The probe confirmed that `future-reason` passes `validate_artifact("report", ...)` even though the model rejects it.
  - `tests/test_schemas.py:227-323` compares object property names and required sets, but it does not compare most nested types, patterns, or enums; only two plan enums have explicit guards.
- impact: A report valid under the published external contract can be rejected by docmend itself, and the failure can escape the CLI's documented artifact-error/exit-2 path. Additive provider evolution is unsafe until the authority direction is made consistent.
- recommendation: Decide whether `skip_reason` is an open or closed vocabulary and align both schema and model. Convert all post-schema model failures to `ArtifactError`. Extend schema/model drift tests to compare compatibility-sensitive types, patterns, enums, aliases, nullability, and defaults for all four modeled artifacts.

### ISSUE-005 — Version fields do not consistently dispatch supported schema semantics

- first_pass: 5
- severity: medium
- confidence: high
- data_area: schema-drift-and-history-reconciliation
- issue_type: schema-drift-history-gap
- evidence_status: verified directly; real historical operator artifacts were unavailable
- change_class: expand-contract compatibility and artifact migration
- affected_surfaces: all five schemas and every artifact reader
- evidence:
  - Every schema and model accepts any `1.x` label rather than selecting an exact supported shape.
  - `src/docmend/cli.py:494-500` explicitly rejects a newer plan minor only at apply time. Inventory consumption, report verification, manifest resume/restore/verify, and frontmatter verification have no equivalent future-minor gate.
  - Probes confirmed that current plan shape remains schema-valid when relabeled `1.999`.
  - `src/docmend/schemas/README.md:17` documents backward-only compatibility, but no centralized reader dispatch implements that policy per artifact kind.
  - Release baseline comparison found inventory 1.2, plan 1.2, report 1.0 across v1.0.0-v1.0.2; manifest moved from 1.2 to 1.3 in v1.0.2. No post-v1.0.2 data code differs at current `HEAD`.
  - Tests construct older version labels, but the repo has no immutable golden artifacts captured from every released producer and no matrix of accept/migrate/refuse expectations for each command.
- impact: Future-minor artifacts can be interpreted as current in destructive or recovery paths, while other schema-valid values fail later in models. The documented newer-reader/older-artifact guarantee is not proven against real release artifacts, and unsupported-newer behavior is inconsistent.
- recommendation: Centralize version parsing and supported-version dispatch per artifact kind before model construction. Accept explicitly supported older minors, migrate when necessary, and reject unsupported newer minors/majors before any mutation. Preserve synthetic golden artifacts for each released schema version and test the command-by-command compatibility matrix. Give future major schemas immutable identities rather than overwriting one semantic identity.

### ISSUE-006 — Aggregate invariants are not enforced when artifacts are consumed

- first_pass: 3
- severity: medium
- confidence: high
- data_area: constraints-indexes-integrity
- issue_type: constraints-integrity-gap
- evidence_status: verified directly and by executable probe
- change_class: artifact integrity validation
- affected_surfaces: inventory, plan, report, verify
- evidence:
  - `src/docmend/artifacts.py:157-172` reconciles report totals only in `write_report()`.
  - `src/docmend/artifacts.py:175-188` does not repeat the check in `read_report()`.
  - `src/docmend/verify.py:117-123` incorrectly assumes `read_report()` already enforces totals equality.
  - The probe changed `totals.would_apply` to 999 and `read_report()` accepted it.
  - Inventory and plan schemas describe totals as reconciling with record arrays, but `read_inventory`, `write_inventory`, `read_plan`, and `write_plan` contain no semantic reconciliation.
  - Existing tests prove producer-generated totals, not rejection of a consumed artifact with valid field types and false aggregates.
- impact: Operator-edited or corrupted artifacts can carry false summary counts while passing schema/model validation. Verify can report clean cross-artifact applied-set accounting even when the report's own authoritative totals are false.
- recommendation: Implement shared semantic validators for read and write paths: inventory array counts, skipped-by-reason sums, total bytes, hard-link groups; plan action/skip counts and action-ID uniqueness; report status counts and status-dependent field combinations. Add negative read-side tests.

### ISSUE-007 — JSON readers silently collapse duplicate member names

- first_pass: 4
- severity: medium
- confidence: high
- data_area: data-import-export
- issue_type: import-export-gap
- evidence_status: verified directly, by executable probe, and against shared research
- change_class: malformed artifact import
- affected_surfaces: inventory, plan, report, manifest, schema loading
- evidence:
  - `src/docmend/artifacts.py:70,123,149,183` and `src/docmend/writer/manifest.py:162` use default `json.loads()` behavior.
  - No artifact decoder rejects duplicate object member names.
  - The probe confirmed that duplicate `schema_version` members collapse to the last value before validation.
  - The shared research pack cites RFC 8259's warning that duplicate-name handling is unpredictable across implementations.
- impact: Different consumers can interpret the same artifact differently. Duplicate path, hash, result, version, or identity members are especially dangerous because validation sees only the locally retained value.
- recommendation: Centralize strict JSON decoding with an `object_pairs_hook` that rejects duplicate members and use it for JSON and NDJSON artifacts. Keep lock-file parsing separate unless its corruption policy is deliberately aligned. Add field-family duplicate tests.

### ISSUE-008 — Single-document artifact writes are not fully durable or collision-safe

- first_pass: 4
- severity: medium
- confidence: medium
- data_area: online-migration-operability
- issue_type: online-migration-operability-gap
- evidence_status: verified from code and shared filesystem guidance; concurrent same-destination behavior was not destructively exercised
- change_class: artifact publication and crash durability
- affected_surfaces: inventory, plan, report
- evidence:
  - `src/docmend/artifacts.py:93-102` fsyncs the temporary file and replaces the destination but does not fsync the containing directory.
  - The same function uses a predictable shared `<name>.tmp` rather than exclusive or unique temporary creation and has no cleanup block for a failed publication.
  - `src/docmend/writer/atomic.py:44-91` demonstrates the stronger repo-native pattern: exclusive temporary creation, cleanup, atomic publication, and parent-directory fsync.
  - `docs/research/append-safe-manifest-format.md:68` and the shared research pack both call for destination-file fsync followed by parent-directory fsync where supported.
- impact: After power loss, a replaced artifact name may not be durable even though the command returned. Concurrent writers targeting the same explicit output can share/truncate the same temporary inode, exposing partial or post-return mutation and leaving one writer to fail publication. Inventory and plan are regenerable, but a lost report weakens run accounting.
- recommendation: Reuse or generalize the exclusive-temp publication primitive for JSON artifacts, clean up on every failure, and fsync the parent directory after replacement. Add same-destination contention tests and fault-injection coverage around file fsync, replace, and directory fsync.

### ISSUE-009 — The primary conventions do not index artifact schema evolution

- first_pass: 4
- severity: low
- confidence: high
- data_area: schema-drift-and-history-reconciliation
- issue_type: convention-quality
- evidence_status: verified directly
- change_class: contributor and change-control convention
- affected_surfaces: schema/model/version maintenance
- evidence:
  - `docs/handoff/conventions.md` is the repo's primary long-lived pattern library but has no trigger for changing inventory, plan, report, manifest, frontmatter schemas, or their models.
  - `src/docmend/schemas/README.md:13-23` contains important compatibility rules, packaging location, authority direction, and version-bump discipline that are not indexed from the primary conventions quick reference.
  - Shared research treats durable artifacts and installed schema files as compatibility-sensitive data contracts requiring explicit upgrade/rejection behavior and historical fixtures.
- impact: A maintainer can follow the normal Python/JSON checks while omitting a schema-version decision, release-baseline fixture, compatibility gate, package-data validation, or spec revision entry.
- recommendation: Add a concise primary convention triggered by any durable artifact schema/model change. Link to ADR-0005 and the schema README; require authority-direction review, version and migration/rejection decision, historical fixtures, installed-package schema verification, and spec/ADR reconciliation without duplicating those documents.

## Review Metadata

- repo_path: `.`
- repo_name: `docmend`
- review_type: `data-schema-migration-review`
- review_mode: read-only review; only this report was created
- report_path: `docs/codex-reviews/2026-07-10-2034-data-schema-migration-review-report.md`
- review_date: `2026-07-10`
- current_branch: `dev`
- head_commit: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- working_tree_state_at_start: dirty; pre-existing `M AGENTS.md` and untracked `docs/codex-reviews/`
- detected_databases: none
- detected_storage_engines: local POSIX-style filesystem; JSON documents; NDJSON manifest/logs; YAML document frontmatter; backup directory tree
- detected_orms: Pydantic is used for strict internal data models, not as an ORM
- detected_migration_tools: no database migration tool; `scan -> plan -> apply -> restore -> verify` is the file-data evolution system
- schema_surfaces_reviewed: all five `src/docmend/schemas/*.schema.json`; inventory, plan, report, manifest models; frontmatter codec; artifact registry/readers/writers
- migration_or_backfill_artifacts_reviewed: apply journal, resume intents, restore inverse manifests, backups, restore/resume runbooks; reserved `frontmatter_migrate` operation; no live backfill job exists
- migration_command_surfaces_reviewed: `plan`, `apply`, `restore`, `verify`, resume flags, preservation flags, run lock
- schema_drift_or_history_artifacts_reviewed: schema README; ADR-0005; ADR-0006; spec data/recovery/security sections; v1.0.0-v1.0.2 tags; schema/model tests
- affected_data_stores_reviewed: source corpus, `./.docmend/` artifacts/logs, operator-selected backup root
- affected_tenants_or_partitions_reviewed: none; single-user local corpus, with run IDs and source roots acting as operational partitions
- prior_baseline_compared: v1.0.0, v1.0.1, v1.0.2; current data code has no diff from v1.0.2
- important_external_data_systems_not_in_repo: real private document library; operator Git/snapshot/external preservation; filesystem and mount configuration; any retained historical artifacts
- data_lifecycle_unknowns: real artifact authenticity/tamper exposure; exact filesystems used; owner purge schedule; external preservation verification; staged real-library rollout results
- conventions_input: `docs/handoff/conventions.md` plus schema-specific `src/docmend/schemas/README.md`
- shared_research_reused: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
- targeted_follow_up_web_research: not needed; shared research covered JSON Schema, duplicate JSON names, filesystem containment, atomicity, durability, and recovery ordering
- report_schema_resolution: the referenced common `report-schema.md` describes orchestrator planning reports rather than data child reports; this report follows the data workflow's required sections and issue fields
- validation:
  - focused schema/recovery suite: `97 passed in 1.69s`
  - command: `UV_CACHE_DIR=/tmp/docmend-uv-cache uv run --offline pytest -q tests/test_schemas.py tests/test_inventory_artifact.py tests/test_plan_artifact.py tests/test_report_artifact.py tests/test_restore.py tests/test_resume.py`
  - executable probes: impossible manifest lifecycle accepted; mismatched report totals accepted; open report skip reason accepted by schema; duplicate JSON member collapsed; future plan minor accepted by schema
  - environment_note: initial uv invocation failed because the injected child cache path was read-only; rerun succeeded with an isolated `/tmp` cache

## Data Area Matrix

| Data area | Applicability | Posture | Evidence or issues |
| --- | --- | --- | --- |
| `schema-model-alignment` | applicable | partial | Hand-authored schemas and strict models exist; ISSUE-004 and ISSUE-006. |
| `schema-drift-and-history-reconciliation` | applicable | partial | Version policy and git history exist; ISSUE-005 and ISSUE-009. |
| `migration-safety-ordering` | applicable | insufficient | File mutation is the migration; ISSUE-001. |
| `expand-contract-rollout` | applicable | partial | MAJOR.MINOR policy and additive history exist; reader dispatch and golden baselines do not, ISSUE-005. |
| `online-migration-operability` | applicable to live filesystem mutation; relational DDL not needed | partial | Dry-run, run lock, atomic writer, and per-file processing are strong; ISSUE-001 and ISSUE-008. |
| `backfill-repair-jobs` | not needed for this repo in v1 | sufficient | No database backfill; frontmatter migration remains reserved/deferred. |
| `rollback-recovery` | central | insufficient | Backups, manifests, resume, restore, and drills exist; ISSUE-001, ISSUE-002, ISSUE-003. |
| `constraints-indexes-integrity` | applicable; indexes not needed | partial | Strict schemas exist; semantic/set constraints missing, ISSUE-003 and ISSUE-006. |
| `idempotency-deduplication` | applicable | partial | Source hashes and resume reconciliation are strong; malformed manifest identity/state can undermine them, ISSUE-003. |
| `event-queue-persistence` | not needed for this repo | not needed for this repo | No queue, outbox, broker, or asynchronous event consumer. |
| `retention-deletion-archival` | applicable | documented/operator-owned | Tool never deletes backups; artifacts retained until user purge; no forced finding. |
| `multi-tenant-partitioning` | not needed for this repo | not needed for this repo | Local single-user CLI; no tenant datastore. |
| `data-import-export` | applicable | partial | Strict schemas and format checking exist; ISSUE-002, ISSUE-004, ISSUE-007. |
| `seed-bootstrap-reference-data` | not needed for production data | sufficient | Synthetic deterministic corpora only; no production seed/reference table. |
| `development-vs-production-migration-controls` | applicable as preview vs write | strong | Dry-run default, explicit `--write`, preservation gate, collision policy, and run lock. |
| `environment-drift-and-manual-changes` | applicable | partial | Stale hashes and modified-since-apply checks exist; ISSUE-002, ISSUE-003, ISSUE-005. |
| `observability-for-data-changes` | applicable | partial | Run IDs, reports, logs, and manifests exist; ISSUE-001 and ISSUE-006 weaken completeness. |
| `data-test-coverage` | applicable | partial | Broad happy-path and fault tests pass; negative semantic, compatibility, and journal-window gaps remain. |

## Severity Summary

| Severity | Count | Issue IDs                                             |
| -------- | ----: | ----------------------------------------------------- |
| critical |     0 | none                                                  |
| high     |     3 | ISSUE-001, ISSUE-002, ISSUE-003                       |
| medium   |     5 | ISSUE-004, ISSUE-005, ISSUE-006, ISSUE-007, ISSUE-008 |
| low      |     1 | ISSUE-009                                             |

## Migration And Rollout Risks

- highest_risk: ISSUE-001 leaves a post-mutation/pre-journal crash window for rewrite and rename.
- expand_contract_risk: ISSUE-005 means the version label does not reliably select supported semantics across consumers.
- destructive_change_controls_verified: explicit `--write`; dry-run default; preservation gate; per-file source hash; collision policy; run-level lock; backup-before-mutate; atomic file replacement.
- relational_schema_migration: not needed for this repo; no relational datastore or DDL exists.
- frontmatter_migration: reserved `frontmatter_migrate` operation exists in schema vocabulary, but v1 emits no frontmatter and no migration chain is live; no forced finding.
- rollout_unknown: the owner has not yet supplied evidence from the staged real-library rollout, so production anomaly coverage remains unverified.

## Schema Drift And History Reconciliation Risks

- ISSUE-004 demonstrates current authoritative-schema/model drift.
- ISSUE-005 covers incomplete supported-version dispatch and missing per-release golden artifact fixtures.
- ISSUE-009 covers the contributor-convention discoverability gap.
- verified_baseline: v1.0.0 and v1.0.1 used manifest 1.2; v1.0.2 uses manifest 1.3; inventory 1.2, plan 1.2, and report 1.0 remain stable across those tags.
- external_history_unknown: no real historical operator artifacts were available, so compatibility was evaluated from git snapshots and synthetic test objects only.

## Online Migration And Operational Safety

- applicable_interpretation: online safety means mutating a live local corpus while preserving readable, recoverable state; database online-DDL locking is not applicable.
- strengths: single writer; per-root lock; dry-run; per-file processing; backup verification; atomic content publication; parent fsync in the writer layer; resumable multi-step intent.
- risks: ISSUE-001 journal ordering and ISSUE-008 artifact publication.
- unverified_environment: network filesystems, unusual mount semantics, storage failures, and actual real-library scale behavior outside the synthetic corpus.

## Integrity And Constraint Risks

- ISSUE-003: manifest lifecycle, identity, sequence, and set constraints.
- ISSUE-004: report schema/model vocabulary mismatch.
- ISSUE-006: aggregate reconciliation absent on consumption.
- ISSUE-007: duplicate JSON members collapse before validation.
- positive_controls: Draft 2020-12 validation, format assertion, `additionalProperties: false`, strict Pydantic models, hashes, run/action/document IDs, enum drift tests for plan operations and skip reasons.

## Backfill And Recovery Risks

- backfills: not needed for this repo in v1; no side-channel repair script or deploy-coupled backfill exists.
- recovery_risks: ISSUE-001, ISSUE-002, ISSUE-003.
- positive_controls: tool backups are verified before mutation; restore checks backup and live hashes; restore is dry-run by default; restore drill reproduces original corpus bytes; resume has explicit dangling-intent handling for `rename_and_rewrite`.
- residual_recovery_gap: those controls assume a complete, coherent, contained manifest, which the current ordering and readers do not guarantee.

## Environment Drift And Operational Risks

- source drift: guarded by per-file SHA-256 at apply.
- post-apply drift: guarded only when a valid non-null manifest after hash exists; ISSUE-003.
- wrong-tree drift: resume checks a recorded root when present, but restore containment is missing; ISSUE-002.
- schema/tool drift: inconsistent future-version rejection; ISSUE-005.
- publication drift: JSON artifact directory durability and same-temp contention; ISSUE-008.
- manual changes: artifact edits remain an explicit trust boundary; strict parsing should reject ambiguity rather than normalize it, ISSUE-007.

## Retention And Lifecycle Risks

- source_documents: user-owned; retained outside tool policy.
- run_artifacts: confidential local data containing paths and hashes; retained until user purge.
- tool_backups: `src/docmend/writer/backup.py:3-5` explicitly states the tool never deletes its backups.
- external_preservation: Git/snapshot/external recovery is an operator assertion and cannot be verified from the manifest; documented warning is present.
- assessment: no forced retention finding. The local, user-owned posture is explicit, but the owner should confirm purge expectations before any automated cleanup feature is proposed.

## Data Testing Gaps

- no injected kill after a successful single-step rewrite/rename and before its terminal manifest append (ISSUE-001).
- no hostile restore test proving every mutation path remains inside the recorded root (ISSUE-002).
- no manifest-set validation tests for mixed roots/runs/versions, sequence gaps/duplicates/order, illegal lifecycle combinations, or applied-without-after-hash (ISSUE-003).
- no test proving every authoritative-schema-valid instance is accepted by its consumer model, or deliberately rejected as a schema error (ISSUE-004).
- no immutable golden artifact set from each released schema version with accept/migrate/refuse expectations per command (ISSUE-005).
- no negative read-side aggregate reconciliation tests for inventory, plan, and report (ISSUE-006).
- no duplicate JSON member rejection tests (ISSUE-007).
- no same-destination writer contention or JSON artifact directory-fsync fault tests (ISSUE-008).
- positive_coverage: schema validity/strictness; current round trips; format assertion; YAML duplicate-key rejection; path containment for inventory/plan and resume intents; backup verification; apply/resume/restore/verify journeys; torn-tail handling; restore drill; 100k synthetic scale path.

## Convention Recommendations

- Add the ISSUE-009 trigger-oriented artifact evolution convention to `docs/handoff/conventions.md`, linking rather than duplicating ADR-0005 and the schema README.
- Define one artifact-read pipeline: duplicate-safe decode, exact supported-version dispatch, authoritative schema validation, model validation mapped to `ArtifactError`, semantic document validation, then manifest-set/cross-artifact validation.
- State which schema descriptions are normative and test every normative semantic claim that JSON Schema cannot express alone.
- Require synthetic golden artifacts for every released schema minor and an explicit migration/rejection matrix before version bumps.
- Require crash-injection at every mutation/journal boundary and hostile containment tests for every command that consumes operator-editable paths.

## Pass Log

| Pass | Lens | New issues | Result |
| --: | --- | --- | --- |
| 1 | schema inventory, ownership, tools, stateful boundaries, applicability | none | Five file-backed schemas identified; database-only categories marked not needed. |
| 2 | mutation ordering, expand-contract posture, rollback, production/write boundary | ISSUE-001, ISSUE-002 | Single-step journal gap and restore containment gap found. |
| 3 | integrity constraints, partial failure, recovery, lifecycle, idempotency | ISSUE-003, ISSUE-006 | Manifest semantic/set invariants and consumed aggregate gaps found. |
| 4 | maintainability, schema/model drift, operator guardrails, convention quality | ISSUE-004, ISSUE-007, ISSUE-008, ISSUE-009 | Lower-severity compatibility, parsing, publication, and convention gaps found. |
| 5 | release-baseline comparison, version dispatch, executable probes | ISSUE-005 | Version-policy implementation and historical-fixture gap confirmed. |
| 6 | adaptive deepening: backups, restore inverses, config/write gate, retention, seed/queue/tenant applicability | none | First convergence pass; no new issue. |
| 7 | focused tests, repo-wide data keyword search, cross-check against shared research and existing review evidence | none | Second consecutive convergence pass; review stopped. |

## Claude Handoff

- priority_1: Fix ISSUE-001 by designing one write-ahead lifecycle for all mutation kinds before the real-library rollout.
- priority_2: Fix ISSUE-002 and ISSUE-003 together at a single manifest-read/restore trust boundary.
- priority_3: Centralize strict decoding, version dispatch, model/error mapping, and semantic validation for ISSUE-004 through ISSUE-007.
- priority_4: Harden single-document artifact publication (ISSUE-008) and index the evolution workflow (ISSUE-009).
- sequencing_note: Schema tightening should be treated as malformed-input rejection, but genuine v1.0.0-v1.0.2 artifacts must first be preserved as synthetic goldens and tested through explicit compatibility decisions.
- likely_files_for_fix: `src/docmend/writer/apply.py`; `src/docmend/writer/manifest.py`; `src/docmend/restore.py`; `src/docmend/artifacts.py`; artifact models and schemas; focused tests; ADR-0005/0006 and binding spec through their controlled workflows; `docs/handoff/conventions.md`.
- follow_on_reviews:
  - `security-review` for restore path authorization, symlink/TOCTOU, and hostile manifests.
  - `incident-readiness-review` for crash-window detection and manual backup recovery.
  - `api-contract-review` findings already corroborate several schema/import issues; reconcile IDs rather than implementing duplicate fixes independently.
- acceptance_evidence_for_fix:
  - crash injection after every successful mutation syscall but before terminal journal append, with complete resume/restore evidence;
  - hostile manifests cause zero outside-root filesystem access or mutation;
  - impossible manifest states and mixed sets reject before lock/mutation;
  - all released golden artifacts receive the documented accept/migrate/refuse result;
  - duplicate JSON keys and false aggregate counts reject consistently as artifact input errors.
- do_not_do: Do not edit orchestrator execution/sweep/live-status artifacts; do not hand-edit standard-owned files; do not use real library artifacts as compatibility fixtures.

## Open Questions Or Assumptions

- What exact crash recovery objective applies between a successful filesystem mutation and its final manifest record: automatic adoption, mechanical restore, or only no-double-mutation?
- Are manifests assumed authentic and tool-produced, or must restore defend against malicious local artifacts? Spec section 13.5 already requires crafted-path containment, so ISSUE-002 remains valid either way.
- Which exact artifact minors must v1.0.2 consume in plan, apply, resume, restore, verify, and frontmatter validation?
- Should `action_id` be correlated to the plan run while top-level manifest/report `run_id` identifies the apply attempt? Current behavior does that, but the durable schema prose is ambiguous.
- Which filesystems and mount types will the real rollout use, and are parent-directory fsync and local locking semantics available?
- What retention/purge schedule does the owner want for confidential artifacts, logs, manifests, and tool backups?
- Is external preservation merely an operator assertion, or should a future plan/apply preflight verify a snapshot/repository state reference?

## Residual Risk

- overall: high
- high: Until ISSUE-001 is fixed, a crash can leave a completed single-step mutation without its recovery record or backup pointer.
- high: Until ISSUE-002 and ISSUE-003 are fixed, restore safety depends on every manifest being contained, coherent, and producer-authentic despite the reader accepting weaker states.
- medium: Compatibility and internal-consistency behavior is inconsistent across artifact types, and real historical operator artifacts were not available.
- medium: Filesystem-specific power-loss, network-filesystem, and adversarial race behavior was not executed in this read-only review.
- medium: The focused suite passing demonstrates current happy-path stability, not absence of the negative-state gaps established by probes and code paths.
- research_limit: No broad internet research was performed because the supplied 2026-07-10 shared research artifact already contained current primary guidance for the detected stack and risks.
