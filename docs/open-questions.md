# Open Questions — `docs/specs/docmend.md`

## Important Notes

- **Document Handling Rules and Guidelines:** [How to maintain this document](#how-to-maintain-this-document)
- **Terminology:**
  - _open question_ (`OQ-###`) is a decision still to be made — the primary unit of this document.
  - _resolved question_ (`RQ-###`, already settled) lives in the companion file [`resolved-questions.md`](resolved-questions.md).

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
