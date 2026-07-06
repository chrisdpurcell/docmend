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

**Canonical record — now formalized in [ADR-0008](adr/adr-0008-stable-document-identity.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**I largely agree.** Also, I don't want to be locked into a single filenaming policy for the long term. In addition to the specific job of this particular batch of document processing, I want the docmend tool to be generally useful, and that means it should be flexible enough to support different naming policies for different use cases.

### RQ-003 — resume model

**Resolved:** 2026-07-05
**Source question:** OQ-003
**Decision owner:** implementer
**Canonical references:** spec §7.1 FR-013, §12.2/§12.3, NFR-002/D-004, `docs/research/append-safe-manifest-format.md`; spec §21 OQ-003 (Status: Resolved)

**Canonical record — now formalized in [ADR-0006](adr/adr-0006-resume-and-recovery-model.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**I agree** Lock it.

### RQ-004 — artifact JSON Schemas

**Resolved:** 2026-07-05
**Source question:** OQ-004
**Decision owner:** implementer
**Canonical references:** spec §7.4 DR-001–DR-004, §9, IR-007; `docs/research/{append-safe-manifest-format,json-schema-versioning-migration,json-schema-validator-library}.md`; spec §21 OQ-004 (Status: Resolved). **⚑ ADR candidate** (architectural artifact contract) — now formalized in [ADR-0005](adr/adr-0005-durable-artifact-schema-contract.md).

**Canonical record — now formalized in [ADR-0005](adr/adr-0005-durable-artifact-schema-contract.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**I agree** Lock it.

### RQ-005 — apply safety gate and preservation semantics

**Resolved:** 2026-07-05
**Source question:** OQ-005
**Decision owner:** owner
**Canonical references:** spec §7.1 FR-005/FR-006, §18.6, §8.5; `docs/research/{backup-integrity-verification,restore-from-manifest-design,combinatorial-safety-gate-testing}.md`; spec §21 OQ-005 (Status: Resolved). **⚑ ADR candidate** — now formalized in [ADR-0004](adr/adr-0004-apply-safety-gate-and-preservation.md). Preservation _strategy_ selection is governed by [RQ-007](#rq-007--preservation-posture-docmend-is-strategy-agnostic); pluggability by [RQ-010](#rq-010--genericity-design-for-pluggable-build-minimal).

**Canonical record — now formalized in [ADR-0004](adr/adr-0004-apply-safety-gate-and-preservation.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**I agree** Lock it. Just note that we need to also allow for flexibility. I might just want to process a single file quickly without having to set up a backup strategy. I don't want to be locked into a single preservation strategy for the long term. But it most definitely must be available for critical operations. In addition to the specific job of this particular batch of document processing, I want the docmend tool to be generally useful, and that means it should be flexible enough to support different preservation strategies for different use cases, including quick low-risk non-critical operations on a single file.

### RQ-006 — verify semantics and exit codes

**Resolved:** 2026-07-05
**Source question:** OQ-006
**Decision owner:** owner
**Canonical references:** spec §7.1 FR-014, §18.5, IR-004; `docs/research/restore-from-manifest-design.md`; spec §21 OQ-006 (Status: Resolved)

**Canonical record — now formalized in [ADR-0012](adr/adr-0012-verify-semantics-exit-code-taxonomy.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**I agree** Lock it.

### RQ-007 — preservation posture: docmend is strategy-agnostic

**Resolved:** 2026-07-05
**Source question:** OQ-008
**Decision owner:** owner
**Canonical references:** spec §18.6, FR-005/FR-006 (RQ-005); `docs/research/{self-hosted-corpus-storage-options,docmend-backup-medium-durability-and-throughput-research}.md`; spec §21 OQ-008 (Status: Resolved)

**Canonical record — now formalized in [ADR-0004](adr/adr-0004-apply-safety-gate-and-preservation.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

docmend should remain agnostic to the preservation strategy which is the user's responsibility. However, docmend should be flexible enough to support different preservation strategies for different use cases, including quick low-risk non-critical operations on a single file.

docmend is a tool for document processing. It is not a tool for document preservation and backup beyond what is necessary to ensure that the document processing operations are safe and reversible. The user should be able to choose their own preservation strategy, and docmend should support that choice without imposing a specific strategy.

### RQ-008 — frontmatter emission scope: optional, minimal in v1

**Resolved:** 2026-07-05
**Source question:** OQ-009
**Decision owner:** owner
**Canonical references:** spec §7.1 FR-016, §9, DR-005; `docs/research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md`; spec §21 OQ-009 (Status: Resolved). Gates OQ-007 (vocabularies), OQ-011 (EPUB), OQ-013 (schema detail), OQ-022 (YAML codec).

**Canonical record — now formalized in [ADR-0011](adr/adr-0011-frontmatter-optional-minimal-split.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

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

**Canonical record — now formalized in [ADR-0010](adr/adr-0010-pluggable-policy-seams.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

_Decided in session via the genericity AskUserQuestion (2026-07-05): "Design-for-pluggable, build-minimal." No in-file owner comment was recorded on OQ-020 before resolution._

### RQ-011 — controlled vocabularies: external and per-corpus

**Resolved:** 2026-07-05
**Source question:** OQ-007
**Decision owner:** owner
**Canonical references:** spec §9, §21 OQ-007 (Status: Resolved); relates to [RQ-008](#rq-008--frontmatter-emission-scope-optional-minimal-in-v1) (frontmatter scope), [RQ-010](#rq-010--genericity-design-for-pluggable-build-minimal) (genericity seam), OQ-023 / §13.4 (confidential-content posture)

**Canonical record — recorded as an instance in [ADR-0010](adr/adr-0010-pluggable-policy-seams.md).** See the ADR for the full decision.

#### My Comments

I have some restrictions which may complicate this. The document set that I am working with is sensitive and a vocabulary set describing it would give clues as to the contents of the documents. I would like to be able to define my own controlled vocabulary set for my own use that is stored securely and separable from the docmend project overall. I would also like to be able to define my own controlled vocabulary set for each document set that I am working with, and not have to use a single set for all document sets. Different types of document sets will have different vocabularies.

Resolution note — confirmed in session via the OQ-007 AskUserQuestion (2026-07-05): _"seam now, mechanism later."_

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
**Canonical references:** spec §8.5, §13.2, §18.2, §21 OQ-012 (Status: Resolved); relates to [RQ-005](#rq-005--apply-safety-gate-and-preservation-semantics) (safety gate). **⚑ ADR candidate** — the owner flagged OQ-012 (fundamental output model) for ADR consideration once settled; now formalized in [ADR-0003](adr/adr-0003-in-place-mutation-output-model.md).

**Canonical record — now formalized in [ADR-0003](adr/adr-0003-in-place-mutation-output-model.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**Agree.** Defer to later.

_Reading confirmed in session via the OQ-012 AskUserQuestion (2026-07-05): in-place for v1; separate output root deferred._

### RQ-014 — frontmatter schema detail for v1

**Resolved:** 2026-07-05
**Source question:** OQ-013
**Decision owner:** owner
**Canonical references:** spec §9, FR-016, DR-005, §21 OQ-013 (Status: Resolved); `docs/research/safe-yaml-loading.md`; gated by [RQ-008](#rq-008--frontmatter-emission-scope-optional-minimal-in-v1); relates to [RQ-021](#rq-021--frontmatter-yaml-codec) (YAML codec)

**Canonical record — now formalized in [ADR-0011](adr/adr-0011-frontmatter-optional-minimal-split.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

I need to discuss this further with Claude for guidance to help answer this.

_Decided in session via the OQ-013 AskUserQuestion (2026-07-05): adopt the minimal v1 shape above; defer the provenance/status model._

### RQ-015 — real-write opt-in

**Resolved:** 2026-07-05
**Source question:** OQ-014
**Decision owner:** owner
**Canonical references:** spec §7.1 FR-004, §7.3 IR-003, §18.2, §21 OQ-014 (Status: Resolved); relates to [RQ-005](#rq-005--apply-safety-gate-and-preservation-semantics) (safety gate)

**Canonical record — now formalized in [ADR-0004](adr/adr-0004-apply-safety-gate-and-preservation.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

_Decided in session via the OQ-014 AskUserQuestion (2026-07-05): lock `--write`. No in-file owner comment was recorded on OQ-014 before resolution._

### RQ-016 — CPU-bound concurrency primitive

**Resolved:** 2026-07-05
**Source question:** OQ-016
**Decision owner:** owner (implementer-proposed)
**Canonical references:** spec NFR-001, §14, §18.2, §21 OQ-016 (Status: Resolved); `docs/research/{python-314-concurrency-model,docmend-and-the-free-threaded-cpython-switch-decision}.md`; relates to [RQ-009](#rq-009--performance-targets-deferred) (perf targets deferred)

**Canonical record — now formalized in [ADR-0007](adr/adr-0007-concurrency-primitive-process-pool.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**Agreed.** Lock it.

### RQ-017 — structured logging via structlog

**Resolved:** 2026-07-05
**Source question:** OQ-017
**Decision owner:** owner
**Canonical references:** spec §19 MS-0, NFR-003, §18.5, IR-005, §8.6, §21 OQ-017 (Status: Resolved); `docs/research/structured-logging-library.md`

**Canonical record — now formalized in [ADR-0013](adr/adr-0013-v1-dependency-selection.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**Agreed.** structlog wired through stdlib logging handlers. Lock it.

### RQ-018 — JSON Schema validator library

**Resolved:** 2026-07-05
**Source question:** OQ-018
**Decision owner:** owner
**Canonical references:** spec §8.6, FR-016, DR-005, §21 OQ-018 (Status: Resolved); relates to [RQ-004](#rq-004--artifact-json-schemas) (artifact schemas); `docs/research/json-schema-validator-library.md`

**Canonical record — now formalized in [ADR-0013](adr/adr-0013-v1-dependency-selection.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**Agreed.** Lock it.

### RQ-019 — property-based testing dependency

**Resolved:** 2026-07-05
**Source question:** OQ-019
**Decision owner:** owner
**Canonical references:** spec §17.2, §8.6, NFR-005, Appendix B.2, §21 OQ-019 (Status: Resolved); `docs/research/property-based-testing-hypothesis.md`

**Canonical record — now formalized in [ADR-0013](adr/adr-0013-v1-dependency-selection.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**Agreed.** Lock it.

### RQ-020 — internal data-model library

**Resolved:** 2026-07-05
**Source question:** OQ-021
**Decision owner:** owner
**Canonical references:** spec §7.4 DR-001–DR-004, §9, §8.6, §21 OQ-021 (Status: Resolved); relates to [RQ-004](#rq-004--artifact-json-schemas) (artifact schemas), [RQ-018](#rq-018--json-schema-validator-library) (external validator); `docs/research/python-library-research.md`

**Canonical record — now formalized in [ADR-0013](adr/adr-0013-v1-dependency-selection.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**Agreed.** Lock it.

### RQ-021 — frontmatter YAML codec

**Resolved:** 2026-07-05
**Source question:** OQ-022
**Decision owner:** owner
**Canonical references:** spec §9, FR-016, DR-005, §8.6, §21 OQ-022 (Status: Resolved); relates to [RQ-008](#rq-008--frontmatter-emission-scope-optional-minimal-in-v1) (frontmatter scope), [RQ-014](#rq-014--frontmatter-schema-detail-for-v1) (schema detail); `docs/research/{python-library-research,safe-yaml-loading}.md`

**Canonical record — now formalized in [ADR-0013](adr/adr-0013-v1-dependency-selection.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

**Agreed.** Lock it.

### RQ-022 — encoding detector and non-ASCII skip floor

**Resolved:** 2026-07-05
**Source question:** OQ-015
**Decision owner:** owner
**Canonical references:** spec §7.1 FR-007, §18.2 (`encoding.fail_below_confidence` + a new non-ASCII byte-count floor key), A-003, G-005, §8.6; §17.2 (weird-document corpus); `docs/research/{encoding-detection-benchmark,charset-detection-floors-for-legacy-text-ingestion,python-library-research}.md`; spec §21 OQ-015 (Status: Resolved). Relates to [RQ-004](#rq-004--artifact-json-schemas) (inventory provenance fields), [RQ-010](#rq-010--genericity-design-for-pluggable-build-minimal) (build-minimal seam), [RQ-009](#rq-009--performance-targets-deferred) (validation-run deferral). Fixes GAP-43.

**Canonical record — now formalized in [ADR-0009](adr/adr-0009-encoding-detection-dual-skip-gate.md).** See the ADR for the full decision, drivers, considered alternatives, and consequences.

#### My Comments

_Decided in session via the OQ-015 AskUserQuestion (2026-07-05): close now on the literature-backed 20-byte default with an MS-2 calibration checkpoint; ship a single fixed floor, defer the family-aware table and ratio signal behind the RQ-010 seam. No in-file owner comment was recorded on OQ-015 before resolution._

### RQ-023 — deferred-review-artifact content-exposure policy (WH-002/WH-005)

**Resolved:** 2026-07-05
**Source question:** OQ-023
**Decision owner:** owner
**Canonical references:** spec §2.2 NG-001, §2.3 WH-002/WH-005, §11, §13.4, §13.5; spec §21 OQ-023 (Status: Resolved). Relates to [RQ-001](#rq-001--v1-boundary-and-explicit-non-goals) (v1 boundary), [RQ-010](#rq-010--genericity-design-for-pluggable-build-minimal) (genericity), [RQ-011](#rq-011--controlled-vocabularies-external-and-per-corpus) (external per-corpus vocabularies), C-002 (synthetic fixtures). **Non-blocking** — WH-002/WH-005 are deferred (§2.3).

The confidentiality line is drawn at the **public-repo / official-tool boundary, not at the operator's screen.**

1. **Operator display is fine.** Showing document contents to the operator as part of docmend's own output and process flow is acceptable. NG-001's "no reading/browsing interface" non-goal means docmend is not a reading/search/browsing product and does not persist confidential content into public or committed surfaces — it does **not** mean the operator may never see their own document text during a run. (This refines NG-001's intent; §11/§13.4 wording to be reconciled accordingly.)
2. **The hard invariant:** nothing that _hints_ at document contents may be baked into the official tool or the public repo — no committed controlled-vocabulary dictionaries / frontmatter taxonomies that reveal the corpus (reaffirms RQ-011: vocabularies are external, per-corpus, stored outside the repo), no version-controlled text-bearing artifacts; fixtures/tests/docs stay synthetic or public-domain (C-002).
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
