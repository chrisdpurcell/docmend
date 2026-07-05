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
    - [RQ-011 — controlled vocabularies: external and per-corpus](#rq-011--controlled-vocabularies-external-and-per-corpus)
    - [RQ-012 — EPUB export metadata deferred](#rq-012--epub-export-metadata-deferred)
    - [RQ-013 — in-place mutation for v1](#rq-013--in-place-mutation-for-v1)
    - [RQ-014 — frontmatter schema detail for v1](#rq-014--frontmatter-schema-detail-for-v1)
    - [RQ-015 — real-write opt-in](#rq-015--real-write-opt-in)
    - [RQ-016 — CPU-bound concurrency primitive](#rq-016--cpu-bound-concurrency-primitive)
    - [RQ-017 — structured logging via structlog](#rq-017--structured-logging-via-structlog)
    - [RQ-018 — JSON Schema validator library](#rq-018--json-schema-validator-library)
    - [RQ-019 — property-based testing dependency](#rq-019--property-based-testing-dependency)
    - [RQ-020 — internal data-model library](#rq-020--internal-data-model-library)
    - [RQ-021 — frontmatter YAML codec](#rq-021--frontmatter-yaml-codec)
    - [RQ-022 — encoding detector and non-ASCII skip floor](#rq-022--encoding-detector-and-non-ascii-skip-floor)
    - [RQ-023 — deferred-review-artifact content-exposure policy (WH-002/WH-005)](#rq-023--deferred-review-artifact-content-exposure-policy-wh-002wh-005)
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

### RQ-011 — controlled vocabularies: external and per-corpus

**Resolved:** 2026-07-05
**Source question:** OQ-007
**Decision owner:** owner
**Canonical references:** spec §9, §21 OQ-007 (Status: Resolved); relates to [RQ-008](#rq-008--frontmatter-emission-scope-optional-minimal-in-v1) (frontmatter scope), [RQ-010](#rq-010--genericity-design-for-pluggable-build-minimal) (genericity seam), OQ-023 / §13.4 (confidential-content posture)

Controlled vocabularies are **externally-supplied, per-corpus configuration**, not a taxonomy hardcoded in this public repo. The frontmatter schema/validator is **vocabulary-agnostic** — it validates a facet value against an `enum` (or equivalent) **loaded from the run's vocabulary configuration** (the RQ-010 seam applied to §9). The owner's real vocabularies live in a **user-owned file stored securely outside the public repo and outside committed artifacts** (same confidentiality posture as §13.4 / OQ-023 — a vocabulary set leaks clues about confidential content), and are **per-document-set** (different corpora carry different vocabularies; no single global taxonomy). The repo ships **only a small, generic, non-revealing example set** for tests. `lang` stays BCP 47; `tags` stays freeform and separate from the controlled facets. **v1 scope:** because v1 emits no controlled-vocab-validated fields (RQ-008 skeleton only), only the *seam* must exist in v1 — the concrete config surface (single file vs named per-corpus profiles), whether any default set ships, and the on-disk vocab format are **deferred** to when controlled-vocab emission is actually built (post-v1, gated by RQ-008).

#### Rationale

- Honors the owner's constraints (user-defined, secure, per-corpus, separable from docmend) at zero v1 build cost: the RQ-010 seam already guarantees the validator accepts an injected set.
- Defers mechanism decisions that have no v1 consumer, avoiding premature config machinery (RQ-009 correctness-first, RQ-010 build-minimal).

#### My Comments

I have some restrictions which may complicate this. The document set that I am working with is sensitive and a vocabulary set describing it would give clues as to the contents of the documents. I would like to be able to define my own controlled vocabulary set for my own use that is stored securely and separable from the docmend project overall. I would also like to be able to define my own controlled vocabulary set for each document set that I am working with, and not have to use a single set for all document sets. Different types of document sets will have different vocabularies.

_Resolution confirmed in session via the OQ-007 AskUserQuestion (2026-07-05): "seam now, mechanism later."_

### RQ-012 — EPUB export metadata deferred

**Resolved:** 2026-07-05
**Source question:** OQ-011
**Decision owner:** owner
**Canonical references:** spec §9, §21 OQ-011 (Status: Resolved); `docs/research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md`

Optional EPUB-export root metadata (`identifier`, `rights`, `creator`, `cover-image`) is **out of scope** — a far-future "maybe." Not needed for v1 (frontmatter is optional/minimal per RQ-008). Whenever it lands, `docmend.id` remains the sole stable internal identifier; Pandoc's `identifier` is an EPUB-facing publication field, never a substitute for it. If added later, EPUB fields stay optional and distinct from docmend identity, emitted only for intentionally export-ready documents.

#### Rationale

- The owner has no use for EPUB export; most legacy library files are not publication-ready, so early EPUB fields would create empty or misleading metadata while `docmend.id` already solves internal traceability.

#### My Comments

**Defer EPUB support.** This is fairly niche and I have no use for it. It's a far future "maybe" feature.

### RQ-013 — in-place mutation for v1

**Resolved:** 2026-07-05
**Source question:** OQ-012
**Decision owner:** owner
**Canonical references:** spec §8.5, §13.2, §18.2, §21 OQ-012 (Status: Resolved); relates to [RQ-005](#rq-005--apply-safety-gate-and-preservation-semantics) (safety gate). **⚑ ADR candidate** — the owner flagged OQ-012 (fundamental output model) for ADR consideration once settled.

v1 **mutates files in place** with atomic replace (`os.replace()` on a same-directory temp file), backups, manifest, and path-containment checks. A separate **output-root / copy-out** workflow is **not** a v1 configuration and is deferred to a later export/structural-conversion phase. Terminology: `source_root` (scanned/planned), `target_path` (post-rename path), `backup_dir` (separate preservation location, *not* an output root); `output_root` is not a v1 config key. Safety comes from the RQ-005 gate (dry-run default, preservation, backups, manifest, atomic writes, containment), not from copy-out isolation.

#### Rationale

- In-place is simpler and better-specified by the current safety model; a separate output root would require a full second-tree config, path mapping, cross-tree collision policy, source-vs-output verify semantics, and restore rules the spec does not yet describe.
- Consequence: unblocks the MS-3 write path. The §8.2.2 diagram's "Converted library" node and any stray output-root language should be reconciled to in-place (GAP-70) when the writer is specified.

#### My Comments

**Agree.** Defer to later.

_Reading confirmed in session via the OQ-012 AskUserQuestion (2026-07-05): in-place for v1; separate output root deferred._

### RQ-014 — frontmatter schema detail for v1

**Resolved:** 2026-07-05
**Source question:** OQ-013
**Decision owner:** owner
**Canonical references:** spec §9, FR-016, DR-005, §21 OQ-013 (Status: Resolved); `docs/research/safe-yaml-loading.md`; gated by [RQ-008](#rq-008--frontmatter-emission-scope-optional-minimal-in-v1); relates to [RQ-021](#rq-021--frontmatter-yaml-codec) (YAML codec)

At the RQ-008 minimal-skeleton scope, the v1 frontmatter schema follows five rules: **(a)** required mechanical fields always present and non-null — `docmend.id`, `docmend.schema_version`, `source.original_path`, `source.hash`, `output.hash`; **(b)** `title` required but allowed a static placeholder (`Untitled`), since v1 infers no titles; **(c)** optional fields **omitted, never `null`** (null cannot distinguish unknown / not-applicable / not-processed); **(d)** `date` / `date-time` scalars kept as **strings** in the loader (override the YAML timestamp constructor) so JSON-Schema `format` assertions fire — the same override RQ-021 requires; **(e)** the rich `known` / `inferred` / `unknown` provenance wrapper (`metadata_status`) is **deferred** to when semantic enrichment (§2.3 WH-###) is scheduled. The §9 null-heavy worked example is rewritten to this convention when `schemas/frontmatter.schema.json` is authored (GAP-56).

#### Rationale

- RQ-008 already scoped v1 to a validatable skeleton, so the elaborate provenance model has no v1 consumer; the reduced rule set is enough to author the schema and keep `format` assertions working.

#### My Comments

I need to discuss this further with Claude for guidance to help answer this.

_Decided in session via the OQ-013 AskUserQuestion (2026-07-05): adopt the minimal v1 shape above; defer the provenance/status model._

### RQ-015 — real-write opt-in

**Resolved:** 2026-07-05
**Source question:** OQ-014
**Decision owner:** owner
**Canonical references:** spec §7.1 FR-004, §7.3 IR-003, §18.2, §21 OQ-014 (Status: Resolved); relates to [RQ-005](#rq-005--apply-safety-gate-and-preservation-semantics) (safety gate)

Real writes are opt-in via `docmend apply plan.json --write`. `apply` **dry-runs by default**; `--write` and `--dry-run` are **mutually exclusive**; `--write` may mutate only if the RQ-005 safety gate passes. Config may keep `write.dry_run_default = true`, but **config alone never enables writes** — the CLI invocation must include `--write`, so a stale config cannot silently turn a preview into a mutation.

#### Rationale

- `--write` is blunt and hard to misread in shell history and logs; keeping the opt-in at the command line (not in config) preserves the "out-of-the-box `apply` cannot mutate" guarantee (FR-004).

#### My Comments

_Decided in session via the OQ-014 AskUserQuestion (2026-07-05): lock `--write`. No in-file owner comment was recorded on OQ-014 before resolution._

### RQ-016 — CPU-bound concurrency primitive

**Resolved:** 2026-07-05
**Source question:** OQ-016
**Decision owner:** owner (implementer-proposed)
**Canonical references:** spec NFR-001, §14, §18.2, §21 OQ-016 (Status: Resolved); `docs/research/{python-314-concurrency-model,docmend-and-the-free-threaded-cpython-switch-decision}.md`; relates to [RQ-009](#rq-009--performance-targets-deferred) (perf targets deferred)

v1 uses `concurrent.futures.ProcessPoolExecutor` with `multiprocessing.get_context('forkserver')` pinned explicitly — **not** the 3.14t free-threaded build, **not** asyncio (the workload is CPU-bound). Default `parallel.workers='auto'` (`os.process_cpu_count()`), with sequential mode (`workers=1`) as the default-until-profiled path used by all NFR-005 purity tests. A §18.2 `parallel.*` surface (`enabled`, `model`, `workers`, `start_method`, `chunksize`, `maxtasksperchild`) ships with `'process'` / `'sequential'` as the only v1 models; `'thread'` / `'interpreter'` reserved. Worker functions must be top-level-importable (forkserver constraint). **Re-open to free-threading only when the release-gated checklist fires:** a stable build defaults free-threaded **or** the SC accepts the Phase III PEP **or** `uv` / OS installers treat it as first-class; **and** `Py_GIL_DISABLED == 1`, `sys._is_gil_enabled()` stays `False` after importing the *full* app, every native dep ships `cp3xyt` / `abi3t` wheels; **and** a docmend switch-benchmark beats the process-pool baseline with zero correctness drift. Numeric throughput targets fold into RQ-009.

#### Rationale

- Process-based works on the standard interpreter every user has, with fault isolation matching the writer-isolation architecture (D-003) and zero new C-extension risk; free-threading remains a moving target (PEP 779 Phase II, no committed Phase III date).

#### My Comments

**Agreed.** Lock it.

### RQ-017 — structured logging via structlog

**Resolved:** 2026-07-05
**Source question:** OQ-017
**Decision owner:** owner
**Canonical references:** spec §19 MS-0, NFR-003, §18.5, IR-005, §8.6, §21 OQ-017 (Status: Resolved); `docs/research/structured-logging-library.md`

Adopt `structlog` wired through stdlib `logging` handlers, emitting **JSON Lines to a per-run file named by run-ID** plus Rich-rendered console text via `ConsoleRenderer`. Decouple `--verbose` / `--quiet` (console level only) from the file sink (always floored at DEBUG) so NFR-003's "diagnose without re-running" holds on quiet runs. Extend the never-auto-delete retention rule (§7.4 / §18.6) to logs. Use `QueueHandler` + `QueueListener` with explicit per-worker init once NFR-001 parallelism (RQ-016) lands. Adds a §8.6 Runtime dependency row. (The owner's `python-library-research.md` argued the opposite — stdlib `logging` + JSON artifacts, on dependency-minimization grounds; the owner chose structlog for throughput and per-run JSONL.)

#### Rationale

- At 100k+ files, log volume/format/destination decides whether mid-batch post-mortem debugging (NFR-003) is feasible; structlog is ~2× faster than stdlib+json/loguru on 3.14, actively released post-3.14 GA, and composes with the already-approved Rich.

#### My Comments

**Agreed.** structlog wired through stdlib logging handlers. Lock it.

### RQ-018 — JSON Schema validator library

**Resolved:** 2026-07-05
**Source question:** OQ-018
**Decision owner:** owner
**Canonical references:** spec §8.6, FR-016, DR-005, §21 OQ-018 (Status: Resolved); relates to [RQ-004](#rq-004--artifact-json-schemas) (artifact schemas); `docs/research/json-schema-validator-library.md`

Adopt `jsonschema>=4.26` with the `format-nongpl` extra and an explicit `Draft202012Validator` + `FormatChecker`, **reusing one compiled validator instance per schema** across a run (~10× faster than per-call `validate()`). **Not** `fastjsonschema` (only drafts 04/06/07) and **not** `check-jsonschema` as a runtime dep (a `requests`-dependent CLI unfit for an offline tool) — `check-jsonschema` is used only as a pre-commit hook linting `schemas/*.schema.json`. `jsonschema-rs` recorded as the pre-vetted escalation path if profiling later shows a bottleneck (its own §8.6 OQ). Adds a §8.6 Runtime row; couples to license-scan (GAP-59) and versioning (GAP-29). Parse critical `date` / `date-time` fields explicitly rather than trusting `format` alone (reinforces RQ-014 + safe-yaml).

#### Rationale

- Per Appendix B.2 the dependency needs an approved OQ; jsonschema 4.26 has full Draft 2020-12 support, a 3.14 classifier, and its sole Rust dep (`rpds-py`) ships cp314/cp314t wheels. Validator-reuse caps added CPU at tens of seconds against a multi-hour I/O-bound run.

#### My Comments

**Agreed.** Lock it.

### RQ-019 — property-based testing dependency

**Resolved:** 2026-07-05
**Source question:** OQ-019
**Decision owner:** owner
**Canonical references:** spec §17.2, §8.6, NFR-005, Appendix B.2, §21 OQ-019 (Status: Resolved); `docs/research/property-based-testing-hypothesis.md`

Adopt `Hypothesis` as a **dev-only** dependency in `[dependency-groups].dev` (never `[project.dependencies]`) with a CI settings profile (`register_profile` / `load_profile`) loosening or disabling `deadline` to avoid timing flakiness; keep Transform-layer tests fixture-free (NFR-005). MPL-2.0 but dev-only, never distributed in the MIT package; the only always-installed transitive dep is `sortedcontainers` (MIT). Companions from `python-library-research.md`: `pyfakefs` for fast scan/plan/filter tests (**not** for atomic-write / fsync / crash / permission / symlink tests — those need a real filesystem) and `pytest-xdist` for parallelizing the weird-document corpus. **Split §8.6 into Runtime vs Dev/Test** (pytest / ruff / basedpyright / coverage / pip-audit already sit outside it by omission).

#### Rationale

- Direct process contradiction resolved: §17.2 requires property tests while §8.6's footer forbids an unlisted dependency without an OQ, so an implementer could not honor the requirement without this approval.

#### My Comments

**Agreed.** Lock it.

### RQ-020 — internal data-model library

**Resolved:** 2026-07-05
**Source question:** OQ-021
**Decision owner:** owner
**Canonical references:** spec §7.4 DR-001–DR-004, §9, §8.6, §21 OQ-021 (Status: Resolved); relates to [RQ-004](#rq-004--artifact-json-schemas) (artifact schemas), [RQ-018](#rq-018--json-schema-validator-library) (external validator); `docs/research/python-library-research.md`

Adopt `pydantic` v2 (>= 2.12, the first 3.14-compatible line; v1 is not) as the internal model layer for config / inventory / plan / report / manifest / action / skip records, using **strict models with `extra='forbid'`**. Keep the hand-authored, checked-in JSON Schemas (RQ-004) as the durable **external** artifact contract — use pydantic's JSON-Schema emission only to **cross-check** the hand-authored schemas in tests, not to generate them. Division of labor: `jsonschema` (RQ-018) validates the external contract; pydantic guards internal construction. Adds a §8.6 Runtime row; introduces a models module under `src/docmend/`.

#### Rationale

- At 100k-file scale, unvalidated dicts let shape errors reach disk before anything catches them; a strict model layer fails fast at construction while the hand-authored schemas preserve the RQ-004 durability guarantee independent of the model library.

#### My Comments

**Agreed.** Lock it.

### RQ-021 — frontmatter YAML codec

**Resolved:** 2026-07-05
**Source question:** OQ-022
**Decision owner:** owner
**Canonical references:** spec §9, FR-016, DR-005, §8.6, §21 OQ-022 (Status: Resolved); relates to [RQ-008](#rq-008--frontmatter-emission-scope-optional-minimal-in-v1) (frontmatter scope), [RQ-014](#rq-014--frontmatter-schema-detail-for-v1) (schema detail); `docs/research/{python-library-research,safe-yaml-loading}.md`

Use `ruamel.yaml` behind a `FrontmatterCodec` abstraction (duplicate-key rejection, controlled quoting / block scalars, Pandoc-compatible emission), with `PyYAML` + a custom duplicate-key-rejecting loader as the **documented fallback** if ruamel's Beta / single-maintainer risk becomes unacceptable. **Regardless of choice, override the timestamp / date constructor so `date` and `date-time` scalars stay strings** — otherwise JSON-Schema `format` assertions never fire (RQ-014, safe-yaml). Adds a §8.6 Runtime row. Runtime-vs-fixture-only timing gated by RQ-008.

#### Rationale

- Frontmatter needs stricter guarantees than "parse some YAML": duplicate-key rejection (C-006 / FR-016), controlled emission, and string-preserved dates. ruamel builds those in; PyYAML would require hand-rolling them.

#### My Comments

**Agreed.** Lock it.

### RQ-022 — encoding detector and non-ASCII skip floor

**Resolved:** 2026-07-05
**Source question:** OQ-015
**Decision owner:** owner
**Canonical references:** spec §7.1 FR-007, §18.2 (`encoding.fail_below_confidence` + a new non-ASCII byte-count floor key), A-003, G-005, §8.6; §17.2 (weird-document corpus); `docs/research/{encoding-detection-benchmark,charset-detection-floors-for-legacy-text-ingestion,python-library-research}.md`; spec §21 OQ-015 (Status: Resolved). Relates to [RQ-004](#rq-004--artifact-json-schemas) (inventory provenance fields), [RQ-010](#rq-010--genericity-design-for-pluggable-build-minimal) (build-minimal seam), [RQ-009](#rq-009--performance-targets-deferred) (validation-run deferral). Fixes GAP-43.

`charset-normalizer` is FR-007's **sole** detector — no `chardet` (active licensing dispute), no `faust-cchardet`/`uchardet` (no 3.14 wheels / no confidence API). Decode confidence is **`1.0 − CharsetMatch.chaos`** (3.x exposes **no** `.confidence`; this is the library's own chardet-compat formula, including its −0.2 penalty below 32 bytes), recording `chaos`/`coherence`/`language` separately as inventory provenance (feeds RQ-004). Keep **`fail_below_confidence = 0.80`**. Add a **second, independent skip gate — a non-ASCII byte-count floor, default `20`** — because a single confidence scalar provably cannot catch the documented short-low-entropy false-accept (a 38-byte mostly-ASCII string misdetected as Big5 at `chaos=0.0`, i.e. maximum confidence, wrong). **Gate ordering (floor applies last):** BOM sniff (authoritative → bypass legacy) → strict **full-file** UTF-8 validity (accept → bypass legacy) → ASCII-only ⇒ treat as ASCII/UTF-8 (never "detect" as legacy) → only non-BOM, non-valid-UTF-8 files reach the byte-count floor. **v1 ships a single fixed count-based floor of `20` for every legacy guess;** the family-aware overrides (Western single-byte ≥ 20; CJK multi-byte ≥ 12; Big5 relaxable to 10) and the sparse-long-file ratio signal (`total_bytes ≥ 4096 && non_ascii_ratio < 0.005 → mark "suspect", prefer skip`) are **documented future overrides behind the same config key (the RQ-010 seam), not built in v1**. All ingest uses explicit binary reads + explicit decode, never ambient `open()` defaults; floor work targets charset-normalizer ≥ 3.4.2 (3.4.7 ships 3.14 wheels). The report's synthetic/public-domain fixture recipe (length × non-ASCII count × placement; explicit false-accept/false-skip boundary sets) is added to the §17.2 corpus.

**Calibration checkpoint (not a reopen):** the `20`-byte default is literature-backed (Sivonen/chardetng convergence — windows-1252/1251 settle at ~20 non-ASCII bytes, legacy CJK at ~10). One project-internal run against docmend's own short-file distribution during MS-2 may tune the number within the ~8–20 band **without reopening OQ-015**; the decision — detector, confidence formula, second-gate existence, gate ordering, and the `20` default — is closed.

#### Rationale

- The threshold governs the core safety premise's false-skip/false-accept rates; the second independent gate is **required, not optional**, because this `.txt`-heavy English corpus is full of the short-mostly-ASCII case a confidence scalar cannot catch, and skip-and-report is the safe failure.
- Closing now (rather than holding a P0 open for the MS-2 run) unblocks the FR-007/§18.2 edits and MS-2 without loss — the number moves within a documented band, the decode/skip contract does not.

#### My Comments

_Decided in session via the OQ-015 AskUserQuestion (2026-07-05): close now on the literature-backed 20-byte default with an MS-2 calibration checkpoint; ship a single fixed floor, defer the family-aware table and ratio signal behind the RQ-010 seam. No in-file owner comment was recorded on OQ-015 before resolution._

### RQ-023 — deferred-review-artifact content-exposure policy (WH-002/WH-005)

**Resolved:** 2026-07-05
**Source question:** OQ-023
**Decision owner:** owner
**Canonical references:** spec §2.2 NG-001, §2.3 WH-002/WH-005, §11, §13.4, §13.5; spec §21 OQ-023 (Status: Resolved). Relates to [RQ-001](#rq-001--v1-boundary-and-explicit-non-goals) (v1 boundary), [RQ-010](#rq-010--genericity-design-for-pluggable-build-minimal) (genericity), [RQ-011](#rq-011--controlled-vocabularies-external-and-per-corpus) (external per-corpus vocabularies), C-002 (synthetic fixtures). **Non-blocking** — WH-002/WH-005 are deferred (§2.3).

The confidentiality line is drawn at the **public-repo / official-tool boundary, not at the operator's screen.**

1. **Operator display is fine.** Showing document contents to the operator as part of docmend's own output and process flow is acceptable. NG-001's "no reading/browsing interface" non-goal means docmend is not a reading/search/browsing product and does not persist confidential content into public or committed surfaces — it does **not** mean the operator may never see their own document text during a run. (This refines NG-001's intent; §11/§13.4 wording to be reconciled accordingly.)
2. **The hard invariant:** nothing that *hints* at document contents may be baked into the official tool or the public repo — no committed controlled-vocabulary dictionaries / frontmatter taxonomies that reveal the corpus (reaffirms RQ-011: vocabularies are external, per-corpus, stored outside the repo), no version-controlled text-bearing artifacts; fixtures/tests/docs stay synthetic or public-domain (C-002).
3. **Durable review artifacts stay metadata-only; external tools render text.** WH-005 (fuzzy duplicates) is a metadata-only cluster report (`cluster_id`, path aliases, sizes, hashes, similarity scores, recommended canonical, blank `decision`). WH-002 (semantic corrections) is a durable machine-readable metadata ledger with **no embedded body text** — docmend identifies, packages, and records review decisions, and **external diff tools render any changed text**. Default review posture stays exception-oriented (no pre-filled "accept", capped batches) to avoid the automation-bias rubber-stamping failure. When scheduled, both feed the RQ-004 schema family as metadata-only shapes.

#### Rationale

- Reframes the earlier "minimize text even to the operator / opt-in text sidecar" research recommendation to the owner's actual threat model: the leakage risk is **public/committed exposure, not transient operator display**.
- Keeping durable artifacts metadata-only and delegating text rendering to external tools is the cleanest NG-001 alignment and the lowest-maintenance path, and keeps docmend's committed surface free of confidential content by construction.

#### My Comments

_Owner decision, verbatim (from the OQ-023 AskUserQuestion, 2026-07-05):_

> It's perfectly acceptable to show contents of the documents to the user as part of the tool's output and process flow. It is not acceptable to bake-in information to the official tool itself and repository (like certain frontmatter dictionaries) which are publicly accessible and may hint at the contents of potentially sensitive documents.

_Text-rendering fork: **external tools render text** — docmend stops at detection + decision-recording and emits only a machine-readable handoff bundle._

## How to use this document

- Keep only settled docmend decisions here.
- Remove copied template content from other repositories before committing.
- Preserve owner comments from `open-questions.md` when moving a settled item.
- If a resolved question later gets an ADR, replace the body here with a short pointer to the ADR or remove the entry once the ADR is the canonical record.
- Do not use this file as a session log; use Git history and the repo handoff docs for routine maintenance history.
