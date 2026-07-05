# Open Questions — `docs/specs/docmend.md`

## Important Notes

- **Document Handling Rules and Guidelines:** [How to maintain this document](#how-to-maintain-this-document)
- **Terminology:**
  - _open question_ (`OQ-###`) is a decision still to be made — the primary unit of this document.
  - _resolved question_ (`RQ-###`, already settled) lives in the companion file [`resolved-questions.md`](resolved-questions.md).
- **Priority scale:** legacy OQ-001..014 use `P0 blocker` / `P1 near-blocker` / `P2 decision`. OQ-015+ (added by the 2026-07-05 gap analysis) carry both that label and a High / Medium / Low gap-analysis priority; the full ranked register with downstream-impact analysis lives in [`gap-analysis.md`](gap-analysis.md).

## Table of Contents

- [Open Questions — `docs/specs/docmend.md`](#open-questions--docsspecsdocmendmd)
  - [Important Notes](#important-notes)
  - [Table of Contents](#table-of-contents)
  - [Open questions](#open-questions)
    - [OQ-001 — v1 boundary and explicit non-goals](#oq-001--v1-boundary-and-explicit-non-goals)
    - [OQ-002 — naming policy and identity preservation](#oq-002--naming-policy-and-identity-preservation)
    - [OQ-003 — resume model](#oq-003--resume-model)
    - [OQ-004 — artifact JSON Schemas](#oq-004--artifact-json-schemas)
    - [OQ-005 — apply safety gate and preservation semantics](#oq-005--apply-safety-gate-and-preservation-semantics)
    - [OQ-006 — verify semantics and exit codes](#oq-006--verify-semantics-and-exit-codes)
    - [OQ-007 — controlled vocabularies](#oq-007--controlled-vocabularies)
    - [OQ-008 — library version control and backup posture](#oq-008--library-version-control-and-backup-posture)
    - [OQ-009 — frontmatter emission scope](#oq-009--frontmatter-emission-scope)
    - [OQ-010 — performance targets](#oq-010--performance-targets)
    - [OQ-011 — EPUB export metadata](#oq-011--epub-export-metadata)
    - [OQ-012 — in-place mutation vs separate output root](#oq-012--in-place-mutation-vs-separate-output-root)
    - [OQ-013 — frontmatter required/null/omitted/status details](#oq-013--frontmatter-requirednullomittedstatus-details)
    - [OQ-014 — real-write CLI/config opt-in](#oq-014--real-write-cliconfig-opt-in)
    - [OQ-015 — encoding detector, confidence signal, and dual skip thresholds](#oq-015--encoding-detector-confidence-signal-and-dual-skip-thresholds)
    - [OQ-016 — CPU-bound concurrency primitive for the Python 3.14 target](#oq-016--cpu-bound-concurrency-primitive-for-the-python-314-target)
    - [OQ-017 — structured logging library, format, and verbosity mapping](#oq-017--structured-logging-library-format-and-verbosity-mapping)
    - [OQ-018 — JSON Schema validator library selection](#oq-018--json-schema-validator-library-selection)
    - [OQ-019 — property-based testing dependency (Hypothesis) approval](#oq-019--property-based-testing-dependency-hypothesis-approval)
    - [OQ-020 — generic-tool genericity vs purpose-built personal taxonomy](#oq-020--generic-tool-genericity-vs-purpose-built-personal-taxonomy)
    - [OQ-021 — internal data-model library (pydantic v2)](#oq-021--internal-data-model-library-pydantic-v2)
    - [OQ-022 — frontmatter YAML codec (ruamel.yaml vs PyYAML)](#oq-022--frontmatter-yaml-codec-ruamelyaml-vs-pyyaml)
  - [How to maintain this document](#how-to-maintain-this-document)

## Open questions

### OQ-001 — v1 boundary and explicit non-goals

**Priority:** P0 blocker  
**Owner:** owner  
**Needed by:** MS-1  
**Spec references:** `docs/specs/docmend.md` §2.1, §2.2, §2.3, §21 OQ-001

Finalize the exact v1 boundary and the complete explicit non-goals list. The decision should clarify which document classes and transformations are in v1, which are deferred, and which are never goals.

#### Agent notes

**Recommendation:** Approve the current "safe migration substrate" as the v1 boundary, and make it explicit that v1 does not do semantic cleanup, structural HTML-to-Markdown conversion, bulk frontmatter emission, search, publication export, or duplicate consolidation.

The v1 included set should be:

- Read-only scan and inventory.
- Reviewable plan artifacts.
- Mechanical `.txt` to `.md` extension rename only.
- Encoding normalization to UTF-8 without BOM.
- LF newline normalization.
- Trailing-whitespace trim, final-newline enforcement, and blank-line collapse.
- Skip-and-report for risky files.
- Dry-run default, preservation gate, backups/manifest, resume, and verify.
- Frontmatter schema and validation machinery, but not bulk emission unless OQ-009 is resolved differently.

**Supporting information:** The spec already defines this split in §2.1, §2.3, §6, and §19. CommonMark is valuable here because it is a strongly defined Markdown baseline, while Pandoc adds the export and YAML metadata layer. Pandoc itself warns that conversions from more expressive formats into Markdown can be lossy, which argues against putting structural HTML conversion in the first safe migration release.

**Reasoning:** This decision protects the rest of the project from scope drift. The early implementation can prove the dangerous parts first: discovery, planning, reversible writes, idempotency, and verification. Once those are trusted on real data, later semantic or structural work has a safer substrate to build on.

**Decision impact:** This unlocks MS-1 and lets implementers reject any request to infer meaning, restructure HTML, enrich metadata, publish EPUB/DOCX/PDF, or merge duplicates as out of v1 scope.

#### My Comments

### OQ-002 — naming policy and identity preservation

**Priority:** P2 decision  
**Owner:** owner  
**Needed by:** MS-2  
**Spec references:** `docs/specs/docmend.md` §7.1 FR-010, §7.1 FR-011, §21 OQ-002

Close or explicitly defer the naming policy. Decide when filenames change mechanically versus meaningfully, how collisions are resolved, and how stable IDs plus old-to-new mappings survive renames.

#### Agent notes

**Recommendation:** Resolve v1 naming narrowly: filenames change only for mechanical extension rename, and identity is never derived from filename. Use `docmend.id` as the stable document identity, `source.original_path` as provenance, and the manifest as the path-history map. Keep semantic renaming deferred to WH-001.

For v1 collision behavior, keep the existing policy set:

- `skip` is the default and leaves both files untouched.
- `fail` aborts the run with a non-zero exit.
- `overwrite` requires explicit configuration and records both the overwritten target and changed source in the manifest.

**Supporting information:** The spec already separates extension rename from structural conversion in FR-010 and requires collision policy in FR-011. Pandoc has an `identifier` field for EPUB/publication metadata, but that is a publication identifier, not an internal corpus identity. Git-like path history and manifests are a better fit for rename provenance than treating paths as durable IDs.

**Reasoning:** This keeps v1 implementation simple while preserving future options. Later semantic renaming can use the same manifest and stable IDs without changing the identity model or corrupting downstream indexes.

**Decision impact:** This unblocks plan/report/manifest schema fields for `source_path`, `target_path`, `docmend.id`, collision status, and path-history records.

**Research update (2026-07-05 gap analysis):** Research (docs/research/stable-document-id-scheme.md, 18 citations) resolves the two open sub-questions this OQ leaves implicit. (1) Generation scheme: adopt UUIDv7 via Python 3.14's stdlib uuid.uuid7() (RFC 9562 §5.7) — zero-dependency, standards-based, time-ordered, and already matched to requires-python>=3.14. Content-derived (UUIDv3/v5, hash), path-derived, and monotonic-counter schemes are disqualified by construction because the ID must survive full rewrites and OQ-002 already forbids filename-derived identity. (2) Identity recovery on re-scan (currently unspecified and the actual source of truth): use a 3-tier algorithm — trust a schema-valid frontmatter docmend.id if present; else match the manifest by original_path/target_path with hash confirmation, then by content-hash (git-rename-detection style) when frontmatter is stripped and the file was also moved; else mint a new UUIDv7 and set an explicit 'identity not recoverable' report flag (extending skip-and-report to identity). Calibre (UUID in an OPF sidecar) and beets (MusicBrainz ID + AcoustID fallback) corroborate the stored-ID-first, content-lookup-fallback shape.

#### My Comments

### OQ-003 — resume model

**Priority:** P1 near-blocker  
**Owner:** implementer  
**Needed by:** before artifact schemas harden; no later than MS-4  
**Spec references:** `docs/specs/docmend.md` §7.1 FR-013, §12.2, §21 OQ-003

Settle the resume model: plan-file-based resume, apply journal, per-file result records, manifest-driven resume, or a combination.

#### Agent notes

**Recommendation:** Use a combined resume model: the plan remains the immutable intent record, while apply writes an append-only journal/report plus incremental manifest entries. On resume, docmend should reconcile plan actions against completed manifest/report entries and current filesystem hashes before deciding whether to skip, continue, or fail a file.

The minimum resume contract should be:

- Plans are immutable after creation and include source hashes plus config snapshot.
- Manifest entries are written immediately after each successful mutation.
- Apply report/journal records started, completed, skipped, failed, and dry-run outcomes.
- Atomic writes mean a crash cannot leave a partial target; resume only has to handle "completed", "not started", or "failed before mutation".
- Failed environmental writes are retried by rerunning apply after the cause is fixed; stale or changed sources require re-plan.

**Supporting information:** Python documents `os.replace()` as atomic when successful on the same filesystem, and the spec already requires temp-file plus fsync plus `os.replace` in NFR-002/D-004. The spec also says the manifest is written incrementally, never only at the end.

**Reasoning:** A plan-only resume cannot know what actually completed after an interruption. A final-only manifest is unsafe because a crash can lose the record. Incremental manifest/report records give docmend enough durable state to resume without redoing completed work or guessing.

**Decision impact:** This should be settled before OQ-004, because inventory/plan/report/manifest schemas need stable run IDs, action IDs, operation status, source hashes, output hashes, timestamps, and error classifications.

**Research update (2026-07-05 gap analysis):** Two research inputs sharpen the resume contract. (1) docs/research/append-safe-manifest-format.md: the manifest must be NDJSON (one schema-valid object per line, one file per apply run), each record fsync'd immediately, so resume/reconciliation reads a durable per-record log; implement a Redis-AOF-style rule that discards only a torn trailing line and hard-aborts on a non-trailing parse failure rather than silently dropping it. (2) The resume model should also state whether scan and plan checkpoint or restart-from-scratch (GAP-25) — currently only apply resume is defined (FR-013/AW-001), yet plan's encoding detection over 100k+ files is expensive to redo against OQ-010's 8-hour pressure. The action-ID assumed here should be promoted into DR-002's binding plan schema (GAP-28).

#### My Comments

### OQ-004 — artifact JSON Schemas

**Priority:** P0 blocker  
**Owner:** implementer  
**Needed by:** MS-1  
**Spec references:** `docs/specs/docmend.md` §7.4 DR-001-DR-004, §9, §21 OQ-004

Pin exact JSON Schemas for inventory, plan, apply report, and manifest, including symlink behavior and path identity.

#### Agent notes

**Recommendation:** Define four versioned JSON Schemas in-repo before MS-1 hardens code:

- `inventory.schema.json`: run metadata, source root identity, config snapshot, file records, skipped records, aggregate counts, and symlink records.
- `plan.schema.json`: inventory reference, tool/schema version, config snapshot, planned actions, skip decisions, risk/conflict decisions, source hashes, target paths, and action IDs.
- `report.schema.json`: command/run metadata, dry-run flag, per-file outcomes, errors, skips, summary counts, and artifact references.
- `manifest.schema.json`: one appendable mutation record per completed mutation, with original path, target path, backup path or external preservation reference, before/after hashes, operation type, and restore instructions.

Use JSON Schema Draft 2020-12, keep schemas strict with `additionalProperties: false` for stable contracts, and include explicit schema/version fields in every artifact. Use Pydantic models internally if helpful, but treat the checked-in JSON Schemas as the external artifact contract.

For symlinks, recommend:

- Scan records symlinks explicitly.
- Plan does not follow symlinks for mutation by default.
- Apply refuses symlink mutation unless a future policy explicitly allows it.

**Supporting information:** JSON Schema supports required object properties and controlled enumerations, while Pydantic can generate Draft 2020-12-compatible schemas. The spec requires artifacts to round-trip identically and counts to reconcile with per-file records.

**Reasoning:** Artifact schemas are the contract between every command. If they drift during implementation, resume, verify, tests, and future migrations all become brittle.

**Decision impact:** This is a P0 blocker for scan/plan/apply/verify implementation and should produce concrete schema files plus fixture artifacts before broad behavior coding.

**Research update (2026-07-05 gap analysis):** Multiple research reports feed the schema freeze and should be reconciled together before MS-1. Manifest representation: use NDJSON per apply run, not a single JSON document — reword IR-007's blanket 'as JSON' to be per-artifact (single document for inventory/plan/report; JSON Lines for the manifest) — because a single JSON doc cannot be appended crash-safely (docs/research/append-safe-manifest-format.md). Manifest granularity: append-only per-run ledgers are the permanent source of truth plus a small regenerable end-of-run 'latest state per path' index for fast multi-run restore lookups (GAP-30). Identity fields needed: run-ID (GAP-27, undefined), per-action ID (GAP-28), UUIDv7 docmend.id (GAP-26). Symlink (GAP-31) and hardlink (GAP-32) record shapes are unspecified. Schema versioning: MAJOR.MINOR per schema, strict additionalProperties:false, with an honest backward-only compatibility policy and a frontmatter_migrate planned-action for corpus migration (docs/research/json-schema-versioning-migration.md). Path-containment and filesystem-durability classification fields (docs/research/path-containment-toctou.md, docs/research/atomic-write-filesystem-semantics.md) should be threaded into the plan/apply/report/manifest artifacts. Note the §17.3 traceability matrix is missing all IR-/DR- rows (GAP-53).

#### My Comments

### OQ-005 — apply safety gate and preservation semantics

**Priority:** P0 blocker  
**Owner:** owner  
**Needed by:** MS-3, with preservation semantics preferably settled before MS-1  
**Spec references:** `docs/specs/docmend.md` §7.1 FR-005, §7.1 FR-006, §18.6, §21 OQ-005

Define the exact apply safety-gate checklist and what satisfies the preservation strategy requirement. Decide whether a manifest alone can ever satisfy FR-005, or whether original bytes must be preserved through Git, external backups, tool-written backups, or another concrete mechanism.

#### Agent notes

**Recommendation:** Define the write safety gate as a checklist that must pass before any non-dry-run mutation:

- Plan is valid against the current schema.
- Plan tool/schema version is compatible.
- Plan source hashes still match current files.
- Explicit write opt-in was provided (see OQ-014).
- Output root/path containment passes.
- Collision policy is explicit and satisfied.
- Low-confidence/risky files are skipped or the run is configured to fail before writing.
- At least one byte-preserving strategy is active: library under Git/snapshot backup, external backup declared, or tool-written backups enabled.
- Manifest writing is enabled and writable.
- Backup destination, if used, is outside the mutation target path and writable.

Do **not** count a manifest by itself as a preservation strategy for content-changing writes. Count the manifest as mandatory rollback metadata, not as original-byte storage. A manifest alone can reverse a rename only if the original bytes remain in place; it cannot restore bytes after rewrite.

**Supporting information:** The spec's RPO is zero loss of original content. Python `shutil.copy2()` attempts to preserve file metadata when copying backups, while `os.replace()` provides the atomic replacement primitive for the writer. Backup tools such as Borg/restic and filesystem snapshots provide independent original-byte preservation outside docmend's manifest.

**Reasoning:** The dangerous failure mode is a successful rewrite with no recoverable original. The safety gate must prove both "we can write safely" and "we can undo the write mechanically."

**Decision impact:** This should update FR-005 language eventually: "reversible manifest" is required for docmend operations, but only a byte-preserving backend satisfies preservation for content rewrites.

**Research update (2026-07-05 gap analysis):** Research converts several self-declared gate checks into verified ones. Backup integrity (docs/research/backup-integrity-verification.md): make FR-006 verify-then-mutate (fsync backup, re-read, re-hash, compare to plan's source.hash before mutating; record backup_verified; ERR-004 on mismatch), and substantiate preservation per-file not per-run — for Git require a non-bare tree, all covered files tracked, and is_dirty(path=covered_paths, untracked_files=True) is False (explicitly overriding GitPython's untracked_files=False default) with HEAD hexsha as restore anchor; raise 'external backups declared' from a bare boolean to a recency-checked attestation; re-check at a bounded interval during long runs. Restore (docs/research/restore-from-manifest-design.md): add a first-class docmend restore command symmetric to apply, replaying manifest records per docmend.id in reverse-chronological (LIFO) order, and pin a per-manifest-record preservation.kind/preservation.ref field now (this is the only hard blocker to starting restore); scope v1 automated restore to tool_backup so it is decoupled from OQ-008. Gate test strategy (docs/research/combinatorial-safety-gate-testing.md): treat the ~10 checks as pure independent predicates evaluated every run with a fixed priority-ordered deterministic blocking_reason plus an all_failures list, tested with allpairspy pairwise coverage (t=3 for the preservation/manifest/backup trio). Add a per-mount disk-space preflight (GAP-38) and the backup-dir-inside-source-root refusal (GAP-36) as gate checks. The schema-version-mismatch decision table (docs/research/json-schema-versioning-migration.md) belongs in this gate too.

#### My Comments

### OQ-006 — verify semantics and exit codes

**Priority:** P1 near-blocker  
**Owner:** owner  
**Needed by:** MS-4  
**Spec references:** `docs/specs/docmend.md` §7.1 FR-014, §18.5, §21 OQ-006

Pin exact `verify` semantics, including artifact inputs, checks performed, failure classes, report contents, and exit-code taxonomy.

#### Agent notes

**Recommendation:** Make `verify` a read-only command that validates corpus state plus artifacts and returns a small, stable exit-code taxonomy:

- `0`: verified clean; no defects found.
- `1`: verification findings exist, such as bad encoding, CRLF, invalid frontmatter, missing output, hash mismatch, or unreconciled counts.
- `2`: invocation/config/artifact input error, such as missing files, invalid JSON, or unknown schema version.
- `3`: safety refusal or path-containment violation detected before verification work can proceed.

For v1, verify should check:

- UTF-8 decodability without replacement.
- LF-only endings.
- Frontmatter validity where frontmatter exists or is expected by the plan/schema.
- Duplicate frontmatter key rejection before schema validation.
- JSON Schema format assertions are active for date/date-time fields.
- Manifest before/after hashes and backup references reconcile.
- Report and manifest counts reconcile with per-file outcomes.
- Skipped/failed files are accounted for and classified.

**Supporting information:** FR-014 already defines the core checks, and §18.5 says exit codes must distinguish success, findings, and refusals. JSON Schema and `jsonschema` both document that `format` validation is not automatically enforced unless explicitly enabled/configured.

**Reasoning:** The user cannot inspect 100k+ files manually. `verify` needs to be strict enough to be the machine substitute for manual review, and its exit codes need to be simple enough for scripts and agents to interpret reliably.

**Decision impact:** This guides CLI tests, seeded-defect fixtures, report schema fields, and release/rollout gates.

**Research update (2026-07-05 gap analysis):** Extend the recommended 0/1/2/3 taxonomy from verify-only to a single tool-wide contract applied uniformly to scan/plan/apply/verify/restore (GAP-11), so every 'exits non-zero' acceptance criterion cites a specific code and driver scripts/agents can distinguish success-with-skips from partial failure from invocation error from safety refusal. Also resolve that verify has no documented way to receive its manifest/report/plan inputs (GAP-12): add explicit --manifest/--report/--plan flags to IR-004 or a run-ID-keyed sidecar-discovery convention. restic's small stable exit-code taxonomy (0/1/2/3/10/11/12/130) is cited precedent (docs/research/restore-from-manifest-design.md).

#### My Comments

### OQ-007 — controlled vocabularies

**Priority:** P2 decision  
**Owner:** owner  
**Needed by:** frontmatter emission scope; gated by OQ-009  
**Spec references:** `docs/specs/docmend.md` §9, §21 OQ-007

Define controlled vocabulary values for `genre`, `status`, `story_type`, `rating`, and `lang`, or confirm placeholder values remain sufficient until frontmatter emission starts.

#### Agent notes

**Recommendation:** Keep placeholders valid for v1, then define controlled vocabularies when frontmatter emission becomes real. Use JSON Schema `enum` for project-owned facets and BCP 47 language tags for `lang`.

Suggested starting point:

- `genre`: `unknown`, `fiction`, `nonfiction`, `poetry`, `essay`, `letter`, `journal`, `notes`, `reference`, `other`.
- `status`: `unknown`, `draft`, `complete`, `fragment`, `corrupt`, `needs_review`.
- `story_type`: `unknown`, `short_story`, `novella`, `novel`, `serial`, `poem`, `essay`, `letter`, `journal_entry`, `notes`, `other`.
- `rating`: `unrated`, `general`, `teen`, `mature`, `explicit`, `sensitive`.
- `lang`: BCP 47 tag when known, with `und` available for undetermined language if the field is required.

Keep `tags` freeform and separate from these controlled fields.

**Supporting information:** JSON Schema `enum` restricts a value to a fixed set, which is exactly what controlled vocabulary fields need. RFC 5646 / BCP 47 defines the structure and validation model for language tags and distinguishes well-formed from valid tags.

**Reasoning:** Controlled values are useful for indexing only if they stay small and predictable. Freeform tags should remain a browsing layer, not a dumping ground for schema-controlled concepts.

**Decision impact:** This can wait behind OQ-009, but schema authors need to know whether placeholders such as `unknown`, `unrated`, and `und` are legal defaults.

#### My Comments

### OQ-008 — library version control and backup posture

**Priority:** P2 decision  
**Owner:** owner  
**Needed by:** first real-library apply  
**Spec references:** `docs/specs/docmend.md` §18.6, §21 OQ-008

Choose the real-library preservation posture: self-hosted Git, external backups, tool-written backups, filesystem snapshots, a heavier object-storage stack, or a documented combination.

#### Agent notes

**Recommendation:** For v1, do not make a heavy corpus platform part of docmend. Use one of these simpler preservation postures before the first real-library write:

- Preferred simple posture: tool-written backups plus manifest, with the library also covered by the user's normal backup/snapshot regime.
- Stronger local posture: filesystem snapshot or Borg/restic backup immediately before mutating runs, plus tool-written manifest.
- Git posture: self-hosted/private Git is acceptable for multiple-GiB text if performance is tested, but avoid public Git hosting and avoid assuming Git alone handles every restore workflow.

Keep lakeFS/MinIO/PostgreSQL/OpenSearch as a later architecture option only if corpus size, search, multi-generation publication, or metadata workflow grows beyond the current single-user filesystem model.

**Supporting information:** The local storage research explicitly says its lakeFS/MinIO recommendation was sized for 1M+ documents / 50+ GB, while the current spec targets >100k files and multiple GiB. GitHub recommends repositories stay under 1 GB and strongly under 5 GB; GitLab documents special handling for large repositories. Borg's deduplicating backup model is well matched to repeated backup runs where only changes should consume new storage.

**Reasoning:** The tool's core safety contract should not depend on deploying a storage platform. For the first real-library run, the relevant question is whether original bytes can be restored, not whether the corpus already has a future search/publication architecture.

**Decision impact:** OQ-005 should remain backend-agnostic, but first real apply should require a named preservation posture and a successful restore drill.

#### My Comments

### OQ-009 — frontmatter emission scope

**Priority:** P1 near-blocker  
**Owner:** owner  
**Needed by:** MS-5, earlier if schema work assumes emitted output  
**Spec references:** `docs/specs/docmend.md` §7.1 FR-016, §9, §21 OQ-009

Decide whether v1 emits frontmatter into converted documents, or only pins the schema and validation machinery for fixtures and later structural conversion.

#### Agent notes

**Recommendation:** Keep v1 to schema plus validation machinery and fixture-level generated frontmatter. Defer bulk frontmatter emission into real converted files until structural conversion or a dedicated frontmatter-emission milestone.

In v1, implementers may:

- Define `schemas/frontmatter.schema.json`.
- Parse and validate existing/generated fixture frontmatter.
- Validate generated frontmatter in tests.
- Ensure `verify` can validate frontmatter where present.

In v1, implementers should not:

- Infer titles, authors, dates, genre, status, or story type for the real library.
- Emit placeholder-heavy frontmatter into every file just to satisfy the target-state vision.
- Treat extension rename as structural Markdown conversion.

**Supporting information:** Pandoc supports YAML metadata blocks and requires them at the beginning for CommonMark-family readers; when writing standalone Markdown it emits one metadata block at the start. The local Pandoc/frontmatter research also warns that metadata scalars are parsed as Markdown by Pandoc, so frontmatter should be emitted only when the schema and emission rules are disciplined.

**Reasoning:** Bulk frontmatter emission forces unresolved decisions about required/null/omitted fields, controlled vocabularies, provenance, and semantic status. Schema-first keeps the output contract moving without polluting real files with low-value unknown metadata.

**Decision impact:** This reduces v1 scope and gates OQ-007, OQ-011, and OQ-013 behind schema/validation work rather than immediate library mutation.

**Research update (2026-07-05 gap analysis):** Reconcile the FR-016-vs-FR-014 conditionality contradiction (GAP-55) as part of this decision: FR-016 (Must) is written as unconditional 'validate generated frontmatter' with no 'where present' qualifier, but this OQ's recommendation that v1 emits no bulk frontmatter would make FR-016 a no-op on every real run. Add explicit frontmatter-absent behavior so the Must requirement is conditioned on the emission-scope decision. Also note §9's null-heavy worked example and the missing schemas/frontmatter.schema.json (DR-005, confirmed absent) must be produced/rewritten together once emission scope and OQ-013 resolve (GAP-56).

#### My Comments

### OQ-010 — performance targets

**Priority:** P2 decision  
**Owner:** owner  
**Needed by:** MS-5  
**Spec references:** `docs/specs/docmend.md` §7.2 NFR-001, §14, §21 OQ-010

Define concrete performance targets before production readiness, including acceptable full-library wall-clock time, throughput, memory ceiling, and parallelism defaults.

#### Agent notes

**Recommendation:** Set provisional performance targets now, then revise after the first 100k synthetic-corpus run:

- Memory: bounded with corpus size; target under 512 MiB for scan/plan/apply on 100k small text files, excluding OS cache.
- Throughput: scan/plan at least 1,000 files/minute on the workstation; apply at least 500 files/minute for small text files when backups are local.
- Wall clock: a full 100k-file mechanical pass should complete in one unattended session, target under 8 hours.
- Parallelism: default to conservative single-process or low worker count; add configurable workers only after single-worker correctness and artifacts are stable.

Treat these as acceptance targets for MS-5, not MS-1/MS-2 blockers.

**Supporting information:** The spec's scale assumption is >100k files and multiple GiB, with occasional manually invoked batch runs. It already prioritizes bounded memory, resumability, idempotency, and no whole-corpus in-memory model.

**Reasoning:** Early numeric targets are useful only as a sanity scale. Correctness, resume, and restore matter more than raw throughput because the workflow can run unattended across sessions.

**Decision impact:** MS-5 gets measurable pass/fail criteria without forcing premature optimization into the core workflow.

**Research update (2026-07-05 gap analysis):** A profiling spike (docs/research/batch-throughput-and-capacity.md, 5,000 synthetic files, Python 3.14.6, local SSD) measured 2,636-4,036 files/min and ~49 MiB peak RSS — clearing this OQ's 500-1,000 files/min floor by 4-8x and its 512 MiB ceiling with wide margin, so the provisional targets are conservative, not infeasible; adopt them as regression floors/ceilings and consider adding a <2h 'typical' expectation while keeping 8h as an outer bound. The I/O/fsync write stage dominates (parent-dir fsync adds ~7.9 ms/file), not CPU-bound detection/hashing. Concurrency primitive (docs/research/python-314-concurrency-model.md): adopt ProcessPoolExecutor with forkserver, default workers='auto' (os.process_cpu_count()). Add a per-mount disk-space preflight (~1.15x source on the backup mount), a Rich progress design (2-4 Hz, 60-120s speed window) plus a TTY-independent heartbeat line, and keep the full 100k scale test out of the default CI gate in favor of a scheduled/workflow_dispatch job (GAP-54).

#### My Comments

### OQ-011 — EPUB export metadata

**Priority:** P2 decision  
**Owner:** owner  
**Needed by:** WH-004 or any v1 frontmatter emission expansion  
**Spec references:** `docs/specs/docmend.md` §9, §21 OQ-011

Decide whether root frontmatter should later include optional EPUB-export metadata fields such as `identifier`, `rights`, `creator`, and `cover-image`, and how they relate to `docmend.id`.

#### Agent notes

**Recommendation:** Defer EPUB-specific root metadata until frontmatter emission or export preparation is in scope. When added, keep it optional and distinct from docmend identity.

Use this split:

- `docmend.id`: immutable internal corpus identifier; required.
- `identifier`: optional EPUB/publication identifier; never a substitute for `docmend.id`.
- `creator`, `rights`, `publisher`, `cover-image`: optional export metadata only when the document is intentionally export-ready.
- Rich contributor data, if needed later, belongs in a namespaced internal object and is mapped to EPUB fields during export.

**Supporting information:** Pandoc documents EPUB metadata through YAML metadata blocks or `--metadata-file`, and recognizes fields such as `identifier`, `creator`, and `rights`. The variables docs show `title`, `author`, `date`, `lang`, `keywords`, `subject`, `description`, and related fields flowing into output metadata; EPUB has additional specialized needs.

**Reasoning:** Most legacy library files are not publication-ready works. Adding EPUB fields too early creates empty or misleading metadata, while `docmend.id` already solves internal traceability.

**Decision impact:** This can remain P2 unless OQ-009 changes and bulk frontmatter emission moves into v1.

#### My Comments

### OQ-012 — in-place mutation vs separate output root

**Priority:** P0 blocker  
**Owner:** owner  
**Needed by:** before write-path implementation  
**Spec references:** `docs/specs/docmend.md` §8.5, §13.2, §18.2

Decide whether v1 mutates files in place or writes converted output to a separate output root. Align path containment, configuration, manifest paths, backup behavior, collision handling, and rollback semantics with that decision.

#### Agent notes

**Recommendation:** For v1, choose in-place mutation with atomic replace, backups, manifest, and path-containment checks. Do not add a separate output-root workflow until a later export/structural-conversion phase needs it.

Clarify the terminology:

- `source_root`: the library root scanned and planned.
- `target_path`: the planned path for each file after extension rename.
- `output_root`: not a v1 configuration setting unless you decide to support copy-out conversion.
- `backup_dir`: separate preservation location, not the output root.

If you prefer a separate output root, then v1 must add explicit config, path mapping, collision policy across two trees, verify semantics for source-vs-output, and restore rules. That is a larger workflow than the current spec describes.

**Supporting information:** The current architecture describes "Converted library" but the config table lacks `write.output_root`. Python `os.replace()` is atomic only when the replace succeeds on the same filesystem, which aligns naturally with in-place same-directory temp-file writes.

**Reasoning:** In-place mutation is riskier in intent but simpler and better specified by the current safety model. The safety comes from dry-run, preservation gate, backups, manifest, and atomic writes, not from copy-out alone.

**Decision impact:** This should be settled before writer implementation. If in-place wins, remove or clarify stray output-root language in the spec. If output-root wins, add a full config and artifact model for it.

#### My Comments

### OQ-013 — frontmatter required/null/omitted/status details

**Priority:** P1 near-blocker  
**Owner:** owner  
**Needed by:** frontmatter schema work; gated by OQ-009  
**Spec references:** `docs/specs/docmend.md` §9

Tighten frontmatter schema details for required versus optional fields, when unknown values are represented as `null` versus omitted, and how `known`/`inferred`/`unknown` status metadata is represented.

#### Agent notes

**Recommendation:** Use this rule set for the schema:

- Required mechanical fields must always be present and non-null: `docmend.id`, `docmend.schema_version`, `source.original_path`, `source.hash`, `output.hash`.
- `title` remains required, but allow a deterministic placeholder plus status metadata until title inference is trustworthy.
- Optional unknown semantic fields are omitted by default, not emitted as `null`.
- Empty arrays are allowed only when the field is known to be intentionally empty, not merely unknown.
- Status/provenance for semantic fields should use a consistent wrapper or sidecar map rather than ad hoc `null`s.

One practical shape is:

```yaml
title: Untitled
metadata_status:
  title:
    state: unknown
    source: placeholder
    confidence: 0
```

**Supporting information:** JSON Schema `required` only checks property presence; type rules decide whether `null` is legal. The local frontmatter research recommends a strict JSON-serializable YAML subset and explicit known/inferred/unknown status so validation does not masquerade as provenance truth.

**Reasoning:** `null` in many optional fields makes frontmatter noisy and ambiguous: it does not tell readers whether the value is unknown, not applicable, intentionally blank, or not processed yet. A clear status model is more verbose only where uncertainty matters.

**Decision impact:** This should be resolved before frontmatter schema files are written. The current example in the spec should then be updated to match the chosen convention.

**Research update (2026-07-05 gap analysis):** Research adds a concrete parser-level constraint to the schema-detail decision (docs/research/safe-yaml-loading.md): both PyYAML and ruamel.yaml silently coerce unquoted ISO-date-like scalars into native datetime.date/datetime objects at parse time, which breaks JSON Schema 'format' assertions (they apply only to string instances). The frontmatter loader's timestamp constructor must be overridden to keep date/date-time scalars as strings so FR-016's 'malformed date is rejected' criterion actually fires. This reinforces the omit-by-default (not null) recommendation and the required-mechanical-fields set, and it should be captured alongside the frontmatter schema file when OQ-009 resolves emission scope.

#### My Comments

### OQ-014 — real-write CLI/config opt-in

**Priority:** P1 near-blocker  
**Owner:** owner  
**Needed by:** MS-3  
**Spec references:** `docs/specs/docmend.md` §7.1 FR-004, §7.3 IR-003, §18.2

Name the exact CLI flag and configuration behavior that opts into real writes when `apply` defaults to dry-run.

#### Agent notes

**Recommendation:** Use `docmend apply plan.json --write` as the positive opt-in for real writes. Keep `--dry-run` available and defaulted, but make `--write` and `--dry-run` mutually exclusive.

Suggested behavior:

- `docmend apply plan.json` performs a dry run.
- `docmend apply plan.json --dry-run` performs a dry run explicitly.
- `docmend apply plan.json --write` may mutate only if the OQ-005 safety gate passes.
- Config may keep `write.dry_run_default = true`, but config alone should not enable writes; the CLI invocation must include `--write`.

**Supporting information:** The spec requires destructive capabilities to be opt-in and says out-of-the-box `apply` cannot mutate anything. Keeping the opt-in at the command line prevents a stale config file from silently turning a preview into a write.

**Reasoning:** `--write` is blunt and hard to misunderstand. Names like `--no-dry-run` are technically precise but easier to miss in shell history and logs.

**Decision impact:** This unblocks CLI tests, docs, safety-gate tests, and the command examples in §10.1/§18.2.

#### My Comments

### OQ-015 — encoding detector, confidence signal, and dual skip thresholds

**Priority:** P0 blocker · Gap-analysis priority: High  
**Owner:** owner  
**Needed by:** MS-2  
**Blocking:** Yes  
**Spec references:** `docs/specs/docmend.md` FR-007, §18.2 encoding.fail_below_confidence, A-003, G-005, §8.6 · Related: OQ-001

Confirm charset-normalizer as FR-007's sole detector, define the decode-confidence score as 1.0 - CharsetMatch.chaos, keep the 0.80 fail_below_confidence default, and set a second independent skip gate keyed on non-ASCII byte count (default in the 8-20 range, encoding-family dependent).

#### Agent notes

**Recommendation:** Keep charset-normalizer only (do not add chardet — active licensing dispute, or faust-cchardet/uchardet — no 3.14 wheels/no confidence API). Adopt confidence = 1.0 - CharsetMatch.chaos, the library's own shipping chardet-compat formula (with the -0.2 penalty below 32 bytes), recording chaos/coherence/language separately as provenance. Keep the 0.80 threshold (always exceeds the worst-case penalized 0.70). Add a non-ASCII-byte-count floor as a second, independent skip gate, with the exact default validated against the weird-document corpus.

**Supporting information:** Report docs/research/encoding-detection-benchmark.md (20 citations): charset-normalizer 3.x CharsetMatch has no .confidence, only chaos/coherence; legacy detect() shim computes 1.0-chaos; documented GitHub issue #391 shows a 38-byte ASCII+1-byte string misdetected as Big5 at chaos=0.0 (max confidence, wrong) that no confidence threshold catches; Sivonen/chardetng convergence study shows windows-1252 needs ~20 and CJK ~10 non-ASCII bytes for reliable detection — so byte length is the wrong unit and a non-ASCII count floor is the right second gate.

**Reasoning:** The threshold governs false-skip/false-accept rates for the core safety premise; a single confidence scalar provably cannot catch the short-low-entropy failure mode that this .txt-heavy library is full of, so a second independent gate is required, not optional.

**Decision impact:** Unblocks MS-2 transform hardening with an evidence-backed decode/skip contract; without it FR-007 references a confidence API that does not exist as specified.

**Downstream impact:** Adds a non-ASCII-floor config key to §18.2, adds chaos/coherence/language provenance fields to the inventory schema (feeds OQ-004), reworks FR-007/FR-016 wording, and adds the report's fixture set to §17.2; also fixes GAP-43 (confidence-API mismatch) in the same change.

**Research update (2026-07-05, owner ChatGPT report):** `docs/research/python-library-research.md` independently confirms `charset-normalizer` as the FR-007 detector, but its proposed `DetectedEncoding` interface carries a `confidence: float` field — note that charset-normalizer 3.x exposes no `.confidence` (only `chaos`/`coherence`); use the `1.0 - chaos` formula from `docs/research/encoding-detection-benchmark.md` (this OQ's primary basis), not a `.confidence` attribute. The report also endorses recording the detector version and confidence in the plan (C.4 provenance).

#### My Comments

### OQ-016 — CPU-bound concurrency primitive for the Python 3.14 target

**Priority:** P1 near-blocker · Gap-analysis priority: High  
**Owner:** implementer  
**Needed by:** MS-3  
**Blocking:** No  
**Spec references:** `docs/specs/docmend.md` NFR-001, §14, §18.2, OQ-010 · Related: OQ-010

Choose docmend's v1 concurrency primitive for the CPU-bound scan/plan/apply pipeline: process-based (ProcessPoolExecutor), free-threaded 3.14t, asyncio, or sequential-only, and the default worker count.

#### Agent notes

**Recommendation:** Adopt concurrent.futures.ProcessPoolExecutor with multiprocessing.get_context('forkserver') pinned explicitly (not the 3.14t free-threaded build, not asyncio — the workload is CPU-bound so async cannot help and GIL threading won't parallelize encoding detection). Default parallel.workers='auto' (os.process_cpu_count()) with a sequential mode (workers=1) as the default-until-profiled path used by all NFR-005 purity tests. Add a §18.2 parallel.\* surface (enabled, model, workers, start_method, chunksize, maxtasksperchild) with 'process'/'sequential' as the only v1 models and 'thread'/'interpreter' reserved. Fold numeric throughput targets into OQ-010's post-MS-1 profiling.

**Supporting information:** Report docs/research/python-314-concurrency-model.md (19 citations): 3.14 free-threading is a separate non-default build (PEP 779); charset-normalizer is pure-Python and GIL-bound today; both named C-ext deps (charset-normalizer, rpds-py) already ship free-threading wheels so nothing blocks a future move; 3.14 changed the default Linux start method fork->forkserver (fork unsafe with threads); ProcessPoolExecutor gives fault isolation matching the writer-isolation architecture (D-003).

**Reasoning:** The choice determines whether the Must-priority NFR-001 parallel capability is implementable and sets worker defaults; process-based works on the standard interpreter every user has with zero new C-extension risk, while free-threading remains a moving target.

**Decision impact:** MS-5's 'parallelism if needed' currently silently demotes a Must NFR; a decided primitive lets the writer, worker-locking (GAP-23), and per-file watchdog (GAP-63) be designed coherently.

**Downstream impact:** Introduces the §18.2 parallel.\* config, a forkserver top-level-importable-target constraint on worker functions, the shared-artifact locking requirement (GAP-23), and the CI scale-test placement (GAP-54); folds into OQ-010's agent notes and §14.

#### My Comments

### OQ-017 — structured logging library, format, and verbosity mapping

**Priority:** P1 near-blocker · Gap-analysis priority: High  
**Owner:** owner  
**Needed by:** MS-0  
**Blocking:** No  
**Spec references:** `docs/specs/docmend.md` §19 MS-0, NFR-003, §18.5, IR-005, §8.6

Choose the logging library, wire format, destination, field schema, and how --verbose/--quiet map to levels for a long-running batch CLI, and approve the new dependency under §8.6.

#### Agent notes

**Recommendation:** Adopt structlog wired through stdlib logging handlers (not loguru — last release predates 3.14 GA with an open unanswered compat issue), emitting JSON Lines to a per-run file named by run-ID plus Rich-rendered console text via ConsoleRenderer. Decouple --verbose/--quiet (console level only) from the file sink (always floored at DEBUG) so NFR-003's diagnose-without-re-running guarantee holds on quiet runs. Extend the never-auto-delete retention rule (§7.4/§18.6) to logs. Use QueueHandler+QueueListener with explicit per-worker init if NFR-001 parallelism lands (given the fork->forkserver default change).

**Supporting information:** Report docs/research/structured-logging-library.md (27 citations): structlog ~2x faster than stdlib+json/loguru on 3.14, actively released post-3.14, composes with stdlib handlers and the already-approved Rich; loguru 0.7.3 shipped 2024-12 with no 3.14 statement; no existing OQ covers logging and §8.6 requires owner approval for the new dependency.

**Reasoning:** At 100k+ files, log volume/format/destination determines whether NFR-003 mid-batch post-mortem debugging is feasible; this MS-0 decision has no current owner.

**Decision impact:** Unblocks MS-0 observability scaffolding and defines the log-schema keyed on run-ID that every command emits.

**Downstream impact:** Adds a §8.6 dependency row, a per-run JSONL log-schema cross-referenced to the run-ID (GAP-27), the console-flag semantics (GAP-17), and the heartbeat/progress line (GAP-20).

**Research update (2026-07-05, owner ChatGPT report):** `docs/research/python-library-research.md` reaches the OPPOSITE conclusion to this OQ's recommendation — it advises AVOIDING `structlog` in v1 and starting with stdlib `logging` plus structured JSON artifacts, on dependency-minimization grounds. This OQ's recommendation (from `docs/research/structured-logging-library.md`) favors `structlog` for throughput and per-run JSON Lines. Both are defensible; the owner should decide with both arguments in view. If stdlib `logging` is chosen, the per-run JSONL schema and run-ID correlation (NFR-003) can still be met with a stdlib JSON formatter, avoiding the new runtime dependency.

#### My Comments

### OQ-018 — JSON Schema validator library selection

**Priority:** P1 near-blocker · Gap-analysis priority: Medium  
**Owner:** owner  
**Needed by:** MS-1  
**Blocking:** Yes  
**Spec references:** `docs/specs/docmend.md` §8.6, FR-016, DR-005, OQ-004 · Related: OQ-004

Resolve §8.6's Conditional JSON Schema validator row to a specific library, given Draft 2020-12 and format-assertion requirements at hundreds of thousands of validations per run.

#### Agent notes

**Recommendation:** Adopt jsonschema>=4.26 with the format-nongpl extra and an explicit Draft202012Validator + FormatChecker, reusing one compiled validator instance per schema across a run (~10x faster than per-call validate()). Do not adopt fastjsonschema (only drafts 04/06/07, disqualified) or check-jsonschema as a runtime dep (a jsonschema-wrapping CLI with a requests dependency unfit for an offline tool) — use check-jsonschema only as a pre-commit hook linting schemas/\*.schema.json. Record jsonschema-rs as the pre-vetted escalation path if profiling later shows a bottleneck (its own §8.6 OQ).

**Supporting information:** Report docs/research/json-schema-validator-library.md (18 citations): jsonschema 4.26 has full Draft 2020-12 support and a 3.14 classifier; its sole Rust dep rpds-py ships cp314/cp314t wheels; format assertion is off by default and needs the extra + explicit FormatChecker; validator-reuse caps added CPU cost at tens of seconds against a multi-hour I/O-bound run.

**Reasoning:** Per Appendix B.2 the dependency cannot land without an approved OQ, and it is only conditionally pre-approved pending that OQ; the validator is required for FR-016/DR-005 schema enforcement at MS-1.

**Decision impact:** Unblocks the OQ-004 schema-authoring and MS-1 validation work with a concrete, 3.14-ready, format-asserting validator.

**Downstream impact:** Adds a §8.6 runtime dependency row, a validator-reuse discipline note, and the format-nongpl license consideration; couples to the license-scan policy (GAP-59) and the versioning policy (GAP-29).

**Research update (2026-07-05, owner ChatGPT report):** `docs/research/python-library-research.md` independently confirms this OQ — use `jsonschema` (not a homegrown validator) with an explicit `FormatChecker` (format is annotation-only by default) and Draft 2020-12; it further advises parsing critical `date`/`date-time` fields explicitly rather than trusting `format` alone (reinforcing `docs/research/safe-yaml-loading.md`).

#### My Comments

### OQ-019 — property-based testing dependency (Hypothesis) approval

**Priority:** P2 decision · Gap-analysis priority: Medium  
**Owner:** owner  
**Needed by:** MS-1  
**Blocking:** No  
**Spec references:** `docs/specs/docmend.md` §17.2, §8.6, NFR-005, Appendix B.2

Approve Hypothesis as a dev-only test dependency to satisfy §17.2's 'property-based tests where cheap', which §8.6 currently does not authorize.

#### Agent notes

**Recommendation:** Adopt Hypothesis as a dev-only dependency in [dependency-groups].dev (never [project.dependencies]) with a CI settings profile (register_profile/load_profile) loosening or disabling deadline to avoid CI timing flakiness, and keep Transform-layer tests fixture-free per NFR-005. Split §8.6 into Runtime vs Dev/Test subsections since pytest/ruff/basedpyright/coverage/pip-audit already sit outside it by omission.

**Supporting information:** Report docs/research/property-based-testing-hypothesis.md (15 citations): Hypothesis 6.156 ships cp310-cp314 wheels including 3.14t; only always-installed transitive dep is sortedcontainers (MIT); MPL-2.0 but dev-only so never distributed in the MIT package; two documented CI footguns (deadline flakiness, function_scoped_fixture) both have simple mitigations.

**Reasoning:** There is a direct process contradiction: §17.2 requires property tests while §8.6's footer forbids an unlisted dependency without an OQ; an implementer cannot honor the requirement without filing this OQ.

**Decision impact:** Enables NFR-005 transform-purity and edge-case property tests at MS-1 without violating the dependency gate.

**Downstream impact:** Adds a §8.6 Dev/Test row and a CI settings profile; the §8.6 Runtime-vs-Dev split it prompts also regularizes the already-ungated pytest/ruff/etc. tooling.

**Research update (2026-07-05, owner ChatGPT report):** `docs/research/python-library-research.md` confirms `hypothesis` for transform/idempotency/risk-classifier property tests and adds two dev-test companions: `pyfakefs` for fast scan/plan/filter tests (explicitly NOT for atomic-write/fsync/crash/permission/symlink tests, which need real-filesystem integration) and `pytest-xdist` for parallelizing the growing weird-document corpus. Both belong in the §8.6 Dev/Test split this OQ proposes.

#### My Comments

### OQ-020 — generic-tool genericity vs purpose-built personal taxonomy

**Priority:** P2 decision · Gap-analysis priority: Medium  
**Owner:** owner  
**Needed by:** MS-1  
**Blocking:** No  
**Spec references:** `docs/specs/docmend.md` §1, §9, G-/FR-/NFR-/NG-/WH- rows, OQ-004, OQ-007, OQ-013 · Related: OQ-001

Decide whether docmend's domain-specific parts (the §9 genre/status/story_type/rating vocabularies and semantic fields) are config-driven/pluggable or purpose-built for the owner's library, and whether §1's 'remain generally useful' ambition is operationalized as a requirement or dropped.

#### Agent notes

**Recommendation:** Either add a concrete requirement operationalizing genericity (e.g. config-driven controlled vocabularies with the mechanical substrate agnostic to them) or explicitly scope §1's ambition down and mark the §9 taxonomy purpose-built; do not leave the ambition unbacked.

**Supporting information:** No G-/FR-/NFR-/NG-/WH- row operationalizes genericity, and §9's semantic fields are a hardcoded personal taxonomy; whether they are configurable materially changes the frontmatter schema shape and validator wiring.

**Reasoning:** An unscoped ambition is silently dropped by OQ-001's narrow v1 framing yet drives a foundational schema-shape choice; leaving it undecided risks either over-building a plugin system or hardcoding a taxonomy that later needs a breaking change.

**Decision impact:** Shapes the OQ-004 frontmatter schema and the OQ-007 controlled-vocabulary extensibility (GAP-57) before schemas freeze at MS-1.

**Downstream impact:** If pluggable, the frontmatter schema and validator must be vocabulary-agnostic and OQ-007 becomes a config concern; if purpose-built, §9 stays hardcoded and the §1 genericity claim is narrowed.

#### My Comments

### OQ-021 — internal data-model library (pydantic v2)

**Priority:** P2 decision · Gap-analysis priority: Medium  
**Owner:** owner  
**Needed by:** MS-1  
**Blocking:** No  
**Spec references:** `docs/specs/docmend.md` §7.4 DR-001-DR-004, §9, §8.6 · Related: OQ-004, OQ-018

Decide whether v1 adopts `pydantic` v2 as the internal model layer for config, inventory, plan, report, manifest, and per-action/skip records, or uses stdlib dataclasses / typed dicts with manual validation. Adding the dependency requires this OQ and a §8.6 row (Appendix B.2).

#### Agent notes

**Recommendation:** Adopt `pydantic` v2 (>= 2.12, which introduced Python 3.14 support; v1 is not 3.14-compatible) as the internal artifact/config model layer, using strict models with `extra='forbid'`. Keep the hand-authored, checked-in JSON Schemas (OQ-004) as the durable EXTERNAL artifact contract rather than deriving them solely from models; use pydantic's JSON Schema emission only to cross-check the hand-authored schemas in tests.

**Supporting information:** `docs/research/python-library-research.md` (owner ChatGPT Deep-Research): the four JSON artifacts plus config snapshots and action records are structured enough that plain dicts become a defect source; pydantic v2.12 added initial 3.14 support and can emit Draft 2020-12 JSON Schema. This complements OQ-018 — `jsonschema` validates the external artifact contract, pydantic guards internal construction.

**Reasoning:** At 100k-file scale, unvalidated dicts let shape errors reach disk and downstream commands before anything catches them; a strict model layer fails fast at construction. Keeping hand-authored schemas as the external contract preserves the OQ-004 durability guarantee independent of the model library.

**Decision impact:** Adds a §8.6 runtime dependency row; sets the internal representation for the OQ-004 schema work at MS-1; establishes the model-vs-hand-authored-schema division of labor with OQ-018.

**Downstream impact:** OQ-004 artifact schemas would be authored as (or cross-checked against) pydantic models; introduces a models module under `src/docmend/`; couples to OQ-018 (external validator) and the schema-versioning policy. If rejected, artifacts use dataclasses/TypedDicts plus manual validation.

#### My Comments

### OQ-022 — frontmatter YAML codec (ruamel.yaml vs PyYAML)

**Priority:** P2 decision · Gap-analysis priority: Medium  
**Owner:** owner  
**Needed by:** Frontmatter validation work (gated by OQ-009)  
**Blocking:** No  
**Spec references:** `docs/specs/docmend.md` §9, FR-016, DR-005, §8.6 · Related: OQ-009, OQ-013

Choose the YAML library for parsing and (later) emitting product frontmatter: `ruamel.yaml` (round-trip, key-order/comment preservation) or `PyYAML` (mainstream, but needs a custom duplicate-key-rejecting loader). Add the corresponding §8.6 row.

#### Agent notes

**Recommendation:** Use `ruamel.yaml` behind a `FrontmatterCodec` abstraction (duplicate-key rejection, controlled quoting/block scalars, Pandoc-compatible emission), with `PyYAML` plus a custom duplicate-key-rejecting loader as the documented fallback if ruamel.yaml's Beta / single-maintainer risk becomes unacceptable. Regardless of choice, override the timestamp/date constructor so `date` and `date-time` scalars stay strings — otherwise JSON Schema `format` assertions never fire (`docs/research/safe-yaml-loading.md`, OQ-013). Gate runtime-vs-fixture-only timing on OQ-009.

**Supporting information:** `docs/research/python-library-research.md` (ruamel.yaml round-trip fidelity + 3.14 compat; Beta/single-maintainer caveat; PyYAML mainstream but insufficient for duplicate-key safety without a custom loader) and `docs/research/safe-yaml-loading.md` (both PyYAML and ruamel silently coerce ISO-date scalars to `datetime`, breaking string-only `format` assertions — the loader must override the timestamp constructor). Pandoc requires quoting/block-scalar discipline for colons, backslashes, and blank lines (C-006).

**Reasoning:** Frontmatter needs stricter guarantees than 'parse some YAML' — duplicate-key rejection (C-006/FR-016), controlled emission, and string-preserved dates. The codec choice decides whether those safety properties are built in (ruamel) or must be hand-rolled (PyYAML).

**Decision impact:** Adds a §8.6 row; sets the `FrontmatterCodec` implementation for FR-016 validation and any OQ-009 emission; binds the date-string-preservation requirement into the loader.

**Downstream impact:** If ruamel.yaml: a heavier but round-trip-safe codec. If PyYAML: a custom loader with duplicate-key + timestamp overrides. Timing (MS-5/fixtures vs. core runtime) follows the OQ-009 emission-scope decision; couples to OQ-013 (schema detail) and the missing `schemas/frontmatter.schema.json`.

#### My Comments

## How to maintain this document

These rules govern **both** files: this one (open) and its companion [`resolved-questions.md`](resolved-questions.md) (settled).

- Read **[Open questions](#open-questions)** for anything that still needs a call. Everything settled lives in [`resolved-questions.md`](resolved-questions.md) — you should not have to read it to know what's outstanding.
- When a question is settled, move it to [`resolved-questions.md`](resolved-questions.md). If a question is partially settled, move the decided half there and leave a focused open question here covering _only_ the remaining fork.
- Once an ADR is written for a settled question, the resolved decision can be safely condensed to an ADR pointer or removed from `resolved-questions.md` to control its size. The ADR is the canonical record of the decision.

**Rules:**

1. **Open questions first, distilled.** Each open question states _only_ the unresolved decision — not the history behind it. The history lives in `resolved-questions.md` and in the research reports.
2. **When a question is settled, move it to `resolved-questions.md`.** Relocate its substance there (record the decision + any ADR) and remove it from this file. Never leave a settled item in Open questions.
3. **Split partially-settled items.** If a gap is half-decided, move the decided half to `resolved-questions.md` and leave a focused open question here covering _only_ the remaining fork.
4. **Two comment layers per open question, kept separate:**
   - `#### Agent notes` — research/reconciliation context, maintained by the assistant.
   - `#### My Comments` — the owner's notes and decisions; **the assistant does not edit this block.** (When an OQ is relocated to `resolved-questions.md`, its owner comments are preserved verbatim.)
5. **Cross-reference by stable ID.** `OQ-###` = open question and `RQ-###` = resolved question. ADRs, the spec, and TODO link here by those IDs — keep them stable. Heading anchors derive from heading _text_, so moving an item between files changes file-qualified links such as `open-questions.md#oq-001--...`; update every referring ADR/TODO/spec/research link in the same change. If you must renumber, update the referencing docs in the same change.
6. **Not a log:** Do not append a log of routine maintenance or administrative changes. This is a _decision record_, not a change log. Use the Git history for that and `docs/handoff.md` and/or `TODO.md` where appropriate.
