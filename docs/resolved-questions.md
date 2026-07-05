# Resolved Questions — `docs/specs/docmend.md`

**Companion to [`open-questions.md`](open-questions.md)** — that file holds questions that still need decisions plus the shared [maintenance rules](open-questions.md#how-to-maintain-this-document). This file is the settled record for decisions that do not yet live in an ADR or in the spec itself.

**Terminology:** an **open question** (`OQ-###`) is a decision still to be made and lives in [`open-questions.md`](open-questions.md). A **resolved question** (`RQ-###`) is already settled and lives here until it is superseded by an ADR or folded back into the canonical spec.

## Table of Contents

- [Resolved Questions — `docs/specs/docmend.md`](#resolved-questions--docsspecsdocmendmd)
  - [Table of Contents](#table-of-contents)
  - [Resolved questions](#resolved-questions)
    - [RQ-001 — v1 boundary and explicit non-goals](#rq-001--v1-boundary-and-explicit-non-goals)
    - [RQ-002 — v1 naming policy and identity preservation](#rq-002--v1-naming-policy-and-identity-preservation)
    - [RQ-003 — resume model](#rq-003--resume-model)
    - [RQ-004 — artifact JSON Schemas](#rq-004--artifact-json-schemas)
    - [RQ-005 — apply safety gate and preservation semantics](#rq-005--apply-safety-gate-and-preservation-semantics)
    - [RQ-006 — verify semantics and exit codes](#rq-006--verify-semantics-and-exit-codes)
    - [RQ-007 — preservation posture: docmend is strategy-agnostic](#rq-007--preservation-posture-docmend-is-strategy-agnostic)
    - [RQ-008 — frontmatter emission scope: optional, minimal in v1](#rq-008--frontmatter-emission-scope-optional-minimal-in-v1)
    - [RQ-009 — performance targets deferred](#rq-009--performance-targets-deferred)
    - [RQ-010 — genericity: design-for-pluggable, build-minimal](#rq-010--genericity-design-for-pluggable-build-minimal)
  - [How to use this document](#how-to-use-this-document)

## Resolved questions

### RQ-001 — v1 boundary and explicit non-goals

**Resolved:** 2026-07-05
**Source question:** OQ-001
**Decision owner:** owner
**Canonical references:** spec §2.1/§2.2/§2.3, §6, §19; spec §21 OQ-001 (Status: Resolved)

v1 is the "safe migration substrate": read-only scan/inventory, reviewable plan artifacts, mechanical `.txt`→`.md` extension rename only, encoding normalization to UTF-8 without BOM, LF newline normalization, trailing-whitespace trim + final-newline enforcement + blank-line collapse, skip-and-report for risky files, and the safety machinery (dry-run default, preservation gate, backups/manifest, resume, verify). Frontmatter schema + validation machinery are in scope but bulk emission is not (see RQ-008). Explicitly **not** in v1: semantic cleanup, structural HTML→Markdown conversion, bulk frontmatter enrichment, search, publication export, and duplicate consolidation (NG-001–NG-003 stand; deferred work is §2.3 WH-###).

#### Rationale

- Proving the dangerous parts first (discovery, planning, reversible writes, idempotency, verification) gives later semantic/structural work a trusted substrate.
- Protects the project from scope drift: implementers can reject any request to infer meaning, restructure HTML, enrich metadata, publish, or merge duplicates as out of v1 scope.
- Consequence: unlocks MS-1.

#### My Comments

**I agree with the recommendation.** Lock it.

### RQ-002 — v1 naming policy and identity preservation

**Resolved:** 2026-07-05
**Source question:** OQ-002
**Decision owner:** owner
**Canonical references:** spec §7.1 FR-010/FR-011, §9 (`docmend.id`), `docs/research/stable-document-id-scheme.md`; spec §21 OQ-002 (Status: Resolved). **Pluggability of the naming policy is tracked under [RQ-010](#rq-010--genericity-design-for-pluggable-build-minimal).**

v1 changes filenames only for the mechanical extension rename; identity is never derived from the filename. `docmend.id` (UUIDv7 via `uuid.uuid7()`, RFC 9562) is the stable document identity, `source.original_path` is provenance, and the manifest is the path-history map. Collision policy stays `skip` (default) / `fail` / `overwrite` (FR-011). Identity recovery on re-scan uses the 3-tier algorithm from the research (trust schema-valid frontmatter `docmend.id`; else manifest match by path with hash confirmation, then content-hash; else mint a new UUIDv7 and flag "identity not recoverable"). Semantic renaming stays deferred to WH-001.

#### Rationale

- Keeps v1 simple while preserving future options; later semantic renaming reuses the same manifest + stable IDs without changing the identity model.
- The owner does not want to be locked into a single filename policy long-term — docmend should support different naming policies for different use cases. That flexibility is an **architectural seam** (RQ-010): v1 ships the single mechanical policy, but the substrate must not preclude alternative, config-driven policies later.
- Consequence: unblocks plan/report/manifest fields for `source_path`, `target_path`, `docmend.id`, collision status, and path-history records.

#### My Comments

**I largely agree.** Also, I don't want to be locked into a single filenaming policy for the long term. In addition to the specific job of this particular batch of document processing, I want the docmend tool to be generally useful, and that means it should be flexible enough to support different naming policies for different use cases.

### RQ-003 — resume model

**Resolved:** 2026-07-05
**Source question:** OQ-003
**Decision owner:** implementer
**Canonical references:** spec §7.1 FR-013, §12.2/§12.3, NFR-002/D-004, `docs/research/append-safe-manifest-format.md`; spec §21 OQ-003 (Status: Resolved)

Combined resume model: the plan is the immutable intent record (with source hashes + config snapshot); apply writes an append-only journal/report plus incremental manifest entries (NDJSON, one fsync'd record per mutation). On resume, docmend reconciles plan actions against completed manifest/report entries and current filesystem hashes before deciding to skip, continue, or fail each file. Atomic writes (NFR-002) mean a crash leaves only "completed", "not started", or "failed before mutation" — never a partial target. Manifest reconciliation follows a Redis-AOF-style rule (discard only a torn trailing line; hard-abort on a non-trailing parse failure).

#### Rationale

- Plan-only resume cannot know what actually completed after an interruption; a final-only manifest is unsafe because a crash loses the record. Incremental durable records give resume enough state to avoid redoing or guessing.
- Must be settled before OQ-004 schemas harden (needs stable run IDs, action IDs, status, hashes, timestamps, error classes).

#### My Comments

**I agree** Lock it.

### RQ-004 — artifact JSON Schemas

**Resolved:** 2026-07-05
**Source question:** OQ-004
**Decision owner:** implementer
**Canonical references:** spec §7.4 DR-001–DR-004, §9, IR-007; `docs/research/{append-safe-manifest-format,json-schema-versioning-migration,json-schema-validator-library}.md`; spec §21 OQ-004 (Status: Resolved). **⚑ ADR candidate** (architectural artifact contract — see the "Assess ADR candidates" task).

Four versioned JSON Schemas pinned in-repo before MS-1 code hardens them: `inventory.schema.json`, `plan.schema.json`, `report.schema.json`, `manifest.schema.json`. Draft 2020-12, strict (`additionalProperties: false`), explicit schema/version fields in every artifact. **Per-artifact representation:** single JSON document for inventory/plan/report; **JSON Lines (NDJSON)** for the manifest (a single JSON document cannot be appended crash-safely) — reword IR-007's blanket "as JSON" accordingly. Manifest is an append-only per-run ledger plus a small regenerable "latest state per path" index. Identity fields required: run-ID, per-action ID, UUIDv7 `docmend.id`. Symlink/hardlink record shapes defined (scan records them; plan/apply refuse symlink mutation by default). Schema versioning MAJOR.MINOR with a backward-only compatibility policy and a `frontmatter_migrate` planned-action for corpus migration. Pydantic may be used internally (RQ pending under OQ-021), but the checked-in JSON Schemas are the durable external contract.

#### Rationale

- Artifact schemas are the contract between every command; drift during implementation makes resume, verify, tests, and migrations brittle.
- P0 blocker for scan/plan/apply/verify — produce concrete schema files + fixture artifacts before broad behavior coding.

#### My Comments

**I agree** Lock it.

### RQ-005 — apply safety gate and preservation semantics

**Resolved:** 2026-07-05
**Source question:** OQ-005
**Decision owner:** owner
**Canonical references:** spec §7.1 FR-005/FR-006, §18.6, §8.5; `docs/research/{backup-integrity-verification,restore-from-manifest-design,combinatorial-safety-gate-testing}.md`; spec §21 OQ-005 (Status: Resolved). **⚑ ADR candidate.** Preservation *strategy* selection is governed by [RQ-007](#rq-007--preservation-posture-docmend-is-strategy-agnostic); pluggability by [RQ-010](#rq-010--genericity-design-for-pluggable-build-minimal).

The write safety gate is a set of pure independent predicates evaluated every run before any non-dry-run mutation: valid plan against current schema; compatible tool/schema version; plan source hashes still match; explicit write opt-in (OQ-014); output-path/containment passes; collision policy explicit and satisfied; risky files skipped or run configured to fail; **at least one active preservation strategy appropriate to the operation's risk level**; manifest writing enabled and writable; backup destination outside the mutation target and writable; per-mount disk-space preflight. FR-006 is **verify-then-mutate** (fsync backup, re-read, re-hash, compare to the plan's `source.hash` before mutating; record `backup_verified`; ERR-004 on mismatch). A manifest alone is **not** a preservation strategy for content-changing rewrites — it is mandatory rollback metadata, not original-byte storage. Add a first-class `docmend restore` command replaying manifest records per `docmend.id` in LIFO order; pin a per-record `preservation.kind`/`preservation.ref` field now.

**Flexibility (owner):** the required *strength* of preservation is **risk-scaled, not fixed**. A quick, low-risk, single-file operation may run under a lightweight posture (up to and including an explicit "no backup, no rollback" opt-in that the operator accepts), while critical/batch content rewrites must have an active byte-preserving strategy. This is the risk-tiered form of the gate, not a loophole in it — see RQ-007 for who owns the strategy and RQ-010 for the seam that keeps it pluggable.

#### Rationale

- The dangerous failure mode is a successful rewrite with no recoverable original; the gate must prove both "we can write safely" and "we can undo the write mechanically" — at a strength proportional to the operation's blast radius.
- Tested with pairwise (allpairspy) coverage over the independent predicates, t=3 for the preservation/manifest/backup trio.

#### My Comments

**I agree** Lock it. Just note that we need to also allow for flexibility. I might just want to process a single file quickly without having to set up a backup strategy. I don't want to be locked into a single preservation strategy for the long term. But it most definitely must be available for critical operations. In addition to the specific job of this particular batch of document processing, I want the docmend tool to be generally useful, and that means it should be flexible enough to support different preservation strategies for different use cases, including quick low-risk non-critical operations on a single file.

### RQ-006 — verify semantics and exit codes

**Resolved:** 2026-07-05
**Source question:** OQ-006
**Decision owner:** owner
**Canonical references:** spec §7.1 FR-014, §18.5, IR-004; `docs/research/restore-from-manifest-design.md`; spec §21 OQ-006 (Status: Resolved)

`verify` is a read-only command validating corpus state + artifacts, with a small stable exit-code taxonomy applied **tool-wide** to scan/plan/apply/verify/restore: `0` clean; `1` findings (bad encoding, CRLF, invalid frontmatter, missing output, hash mismatch, unreconciled counts); `2` invocation/config/artifact-input error; `3` safety refusal / path-containment violation. v1 verify checks: UTF-8 decodability without replacement; LF-only endings; frontmatter validity where present/expected; duplicate-key rejection before schema validation; `format` assertions active for date/date-time; manifest before/after hashes + backup refs reconcile; report/manifest counts reconcile with per-file outcomes; skipped/failed files accounted for. verify receives its inputs via explicit `--manifest`/`--report`/`--plan` flags or a run-ID-keyed sidecar-discovery convention.

#### Rationale

- The user cannot inspect 100k+ files manually; verify is the machine substitute for manual review and its exit codes must be script/agent-interpretable (success-with-skips vs partial failure vs invocation error vs safety refusal). restic's 0/1/2/3/10/11/12/130 taxonomy is the cited precedent.

#### My Comments

**I agree** Lock it.

### RQ-007 — preservation posture: docmend is strategy-agnostic

**Resolved:** 2026-07-05
**Source question:** OQ-008
**Decision owner:** owner
**Canonical references:** spec §18.6, FR-005/FR-006 (RQ-005); `docs/research/{self-hosted-corpus-storage-options,docmend-backup-medium-durability-and-throughput-research}.md`; spec §21 OQ-008 (Status: Resolved)

docmend is a document-**processing** tool, not a preservation/backup platform. It stays **agnostic** to the preservation strategy: the user owns the choice (self-hosted Git, external backups, filesystem snapshots, Borg/restic, tool-written backups, or — for quick low-risk single-file work — none), and docmend supports that choice without imposing a specific one. docmend's own responsibility ends at what is needed to make its processing operations safe and reversible: the RQ-005 gate (which requires *a* risk-appropriate strategy be active for content rewrites), the tool-written backup option, the manifest, and `restore`. No heavy corpus platform (lakeFS/MinIO/PostgreSQL/OpenSearch) is part of docmend. From the backup-medium research: keep the per-file safety barrier on a fast local filesystem and treat Borg/restic/S3 as async **replication targets**, not inline durability barriers (they provide no POSIX rename/directory-fsync primitive); first real-library apply still requires a named posture + a successful restore drill.

#### Rationale

- The tool's core safety contract must not depend on deploying a storage platform. The relevant question for a real run is "can original bytes be restored?", not "does the corpus have a search/publication architecture?".
- Reinforces RQ-005's risk-scaled flexibility and RQ-010's pluggability: the preservation backend is a seam, and v1 ships the simple tool-backup + manifest posture while remaining open to the user's own regime.

#### My Comments

docmend should remain agnostic to the preservation strategy which is the user's responsibility. However, docmend should be flexible enough to support different preservation strategies for different use cases, including quick low-risk non-critical operations on a single file.

docmend is a tool for document processing. It is not a tool for document preservation and backup beyond what is necessary to ensure that the document processing operations are safe and reversible. The user should be able to choose their own preservation strategy, and docmend should support that choice without imposing a specific strategy.

### RQ-008 — frontmatter emission scope: optional, minimal in v1

**Resolved:** 2026-07-05
**Source question:** OQ-009
**Decision owner:** owner
**Canonical references:** spec §7.1 FR-016, §9, DR-005; `docs/research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md`; spec §21 OQ-009 (Status: Resolved). Gates OQ-007 (vocabularies), OQ-011 (EPUB), OQ-013 (schema detail), OQ-022 (YAML codec).

Frontmatter is an **optional feature**, not core functionality — the user chooses whether a run emits it, and docmend never imposes frontmatter on all documents. v1 ships **very basic** support: a minimal skeleton frontmatter block that validates against the schema, providing the bare-minimum tracking of processed documents (the required mechanical fields — `docmend.id`, `docmend.schema_version`, `source.original_path`, `source.hash`, `output.hash`, plus a placeholder `title`). Richer frontmatter (semantic enrichment, inferred titles/authors/dates, controlled vocabularies, provenance depth) is deferred to later versions. v1 still defines `schemas/frontmatter.schema.json`, validates skeleton/fixture frontmatter, and lets `verify` validate frontmatter where present; it does **not** infer semantic metadata for the real library or emit placeholder-heavy blocks.

#### Rationale

- Making frontmatter opt-in and minimal keeps the output contract moving without forcing the unresolved required/null/omitted, controlled-vocabulary, and provenance decisions, and without polluting real files with low-value unknown metadata.
- Resolves the FR-016-vs-FR-014 conditionality gap (GAP-55): FR-016's "validate generated frontmatter" is conditioned on the emission being requested — a run that emits no frontmatter has nothing to validate, which is legal.

#### My Comments

The use of frontmatter is an optional feature of docmend. It is not a requirement for the core functionality of docmend. The user should be able to choose whether to use frontmatter or not, and docmend should support that choice without imposing frontmatter on all documents.

I would like very basic frontmatter support in v1, essentially just enough to have a skeleton frontmatter block that can be validated against a schema, and to provide the bare minimum of tracking of processed documents. Expansion to frontmatter features/depth/richness can be deferred to later versions.

### RQ-009 — performance targets deferred

**Resolved:** 2026-07-05
**Source question:** OQ-010
**Decision owner:** owner
**Canonical references:** spec §7.2 NFR-001, §14; `docs/research/{batch-throughput-and-capacity,docmend-backup-medium-durability-and-throughput-research}.md`; spec §21 OQ-010 (Status: Resolved)

Numeric performance targets (wall-clock, throughput, memory ceiling, parallelism defaults) are **deferred**. v1 keeps only the **structural** performance criteria already binding in NFR-001 (bounded memory, streaming per-file processing, no whole-corpus in-memory model, resumability, idempotency). Correctness and safety come first; concrete numeric targets are revisited **after** the tool is proven correct and safe on real data. The existing profiling data (2,636–4,036 files/min, ~49 MiB RSS on a 5k-file local-SSD spike) and the backup-medium findings are recorded as **informative context**, not binding acceptance targets — and the 8-hour figure is explicitly not a v1 gate.

**Revisit trigger:** the tool runs correctly and safely on the real library, and the owner chooses to set targets.

#### Rationale

- Early numeric targets are useful only as a sanity scale; premature optimization would compete with the correctness/safety work that matters more for an unattended, resumable workflow.
- Keeps NFR-001's structural guarantees binding while removing the numeric-target pressure from v1 milestones.

#### My Comments

It is too early to set performance targets. I would like to see the tool working correctly and safely first, and then we can look at performance targets later.

### RQ-010 — genericity: design-for-pluggable, build-minimal

**Resolved:** 2026-07-05
**Source question:** OQ-020
**Decision owner:** owner (decided in session, 2026-07-05, in response to the AskUserQuestion on genericity)
**Canonical references:** spec §1 (generally-useful ambition), §8 architecture/D-003, §9; relates to RQ-002 (naming), RQ-005/RQ-007 (preservation), OQ-007 (vocabularies), RQ-008 (frontmatter); spec §21 OQ-020 (Status: Resolved)

docmend's "remain generally useful" ambition (§1) is operationalized as an **architectural principle**, not as v1 feature work: **the v1 substrate must not *preclude* pluggable policies** — naming policy, preservation strategy, controlled vocabularies, and frontmatter emission are each isolated behind a seam/interface — but v1 **ships a single, minimal default policy for each** and does not build the configuration machinery to swap them. "Correctness and safety first" (RQ-009) governs the build order; genericity governs the shape so a later version can add config-driven policies without a breaking redesign. Concretely: the frontmatter schema/validator must be written to accept an **externally supplied** controlled-vocabulary set rather than hardcoding the §9 personal taxonomy (feeds OQ-007); the writer's preservation step is an interface (feeds RQ-005/RQ-007); the rename action is one implementation of a naming-policy seam (feeds RQ-002).

#### Rationale

- Chosen over "operationalize now" (would add config surface + machinery to v1 scope, conflicting with correctness-first) and over "aspirational only" (would leave a foundational schema-shape choice unbacked and risk a later breaking change).
- Design-for-pluggable is cheap when done up front (seams, interfaces, no hardcoded taxonomy) and expensive to retrofit; build-minimal keeps v1 focused.
- Consequence: the OQ-004 frontmatter schema and validator must be vocabulary-agnostic; §9's taxonomy becomes an example/default set, not a hardcoded contract.

#### My Comments

_Decided in session via the genericity AskUserQuestion (2026-07-05): "Design-for-pluggable, build-minimal." No in-file owner comment was recorded on OQ-020 before resolution._

## How to use this document

- Keep only settled docmend decisions here.
- Remove copied template content from other repositories before committing.
- Preserve owner comments from `open-questions.md` when moving a settled item.
- If a resolved question later gets an ADR, replace the body here with a short pointer to the ADR or remove the entry once the ADR is the canonical record.
- Do not use this file as a session log; use Git history and the repo handoff docs for routine maintenance history.
