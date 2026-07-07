# ADR Candidate Backlog

**Purpose:** LLM-facing tracking record for docmend's Architecture Decision Records. Derived from a comprehensive review of [`docs/specs/docmend.md`](../specs/docmend.md) (design decisions D-001–D-009) and [`docs/resolved-questions.md`](../resolved-questions.md) (RQ-001–RQ-023), 2026-07-05; **second review pass 2026-07-06** over the tool-first reframing and gap-register Batch B decisions (RQ-024–RQ-033) added ADRs 0014–0016 and the amendment/skip dispositions below. Not itself an ADR.

**How this list was built.** ADR candidates come from two converging sources — the spec's own `D-###` design decisions (which already carry considered-alternatives) and the settled-question backlog (`RQ-###`). Candidates are **bundled by decision cohesion and shared reversal cost** (things revisited _together_ share one ADR), not one-ADR-per-RQ. Each was scored on five ADR-worthiness axes: **Rev** (cost to reverse), **Blast** (cross-cutting reach), **Trade** (richness of rejected alternatives), **Contract** (durable external contract), **Revisit** (has live re-open criteria).

## Status

| ADR | Title | Tier | Sources | Status |
| --- | --- | --- | --- | --- |
| 0001 | Do not adopt the Markdown Frontmatter Standard | — | D-008 | ✅ accepted |
| 0002 | Layered pipeline with an isolated writer | 🔴 1 | D-003, D-006 | ✅ accepted |
| 0003 | In-place mutation + atomic-replace output model | 🔴 1 | RQ-013 ⚑, D-004 | ✅ accepted |
| 0004 | Apply safety gate + preservation posture | 🔴 1 | RQ-005 ⚑, RQ-007 | ✅ accepted |
| 0005 | Durable artifact schema contract (JSON + NDJSON) | 🔴 1 | RQ-004 ⚑, DR-001–004 | ✅ accepted |
| 0006 | Resume & recovery model | 🟡 2 | RQ-003 | ✅ accepted |
| 0007 | Concurrency primitive: ProcessPool + forkserver | 🟡 2 | RQ-016 | ✅ accepted |
| 0008 | Stable document identity (UUIDv7 + manifest) | 🟡 2 | RQ-002 | ✅ accepted |
| 0009 | Encoding detection & dual skip-gate | 🟡 2 | RQ-022, D-002 | ✅ accepted |
| 0010 | Design-for-pluggable policy seams | 🟢 3 | RQ-010, D-009 | ✅ accepted |
| 0011 | Frontmatter: optional, minimal, mechanical/semantic split | 🟢 3 | RQ-008/014, D-001/007 | ✅ accepted |
| 0012 | verify semantics + tool-wide exit-code taxonomy | 🟢 3 | RQ-006 | ✅ accepted |
| 0013 | v1 runtime & dev dependency selection (consolidated) | 🟢 3 | RQ-017/018/019/020/021 | ✅ accepted |
| 0014 | Tool-first product scope — scale-flexibility binding | 🟢 3 | RQ-024, G-006, NFR-006 | ✅ accepted |
| 0015 | Two-corpus test architecture & anonymization | 🟡 2 | RQ-032 | ✅ accepted |
| 0016 | The mechanical-transform boundary (consolidated) | 🟢 3 | RQ-025/030/031 | ✅ accepted |
| 0017 | Branch strategy, protection, release process, CI/CD | 🟡 2 | workflow adoption (no RQ; authored 2026-07-06 before MS-0) | ✅ accepted |
| 0018 | Doc Processing repository boundary | 🟡 2 | 2026-07-07 cross-repo alignment review (no RQ; outside the two original review passes) | ✅ accepted |

## Tier 1 — write now (foundational; hard to reverse)

- **ADR-0002 — Layered pipeline with an isolated writer** (D-003, D-006). Rev H · Blast H · Trade M · Contract M · Revisit L. The structural backbone: pure transforms + discovery/planning/transform/writer/verify separation, with `plan` emitting a reviewable, hash-validated artifact `apply` executes. Rejected monolithic convert-in-place. _Added beyond the owner's flags — arguably more foundational than any single RQ._
- **ADR-0003 — In-place mutation + atomic-replace output model** (RQ-013 ⚑, D-004). Rev H · Blast H · Trade H · Contract M · Revisit M. The fundamental output model; the separate-output-root alternative is explicitly rejected and later reversal is a breaking redesign. Clarifies the "in-place" terminology collision with D-004.
- **ADR-0004 — Apply safety gate + preservation posture** (RQ-005 ⚑, RQ-007, FR-005/006). Rev M · Blast H · Trade H · Contract M · Revisit M. Risk-scaled predicate gate + verify-then-mutate + preservation-agnostic stance + `restore`.
- **ADR-0005 — Durable artifact schema contract** (RQ-004 ⚑, DR-001–004, IR-007). Rev H · Blast H · Trade M · Contract H · Revisit M. Four checked-in versioned schemas; JSON-doc-vs-NDJSON-manifest split; MAJOR.MINOR versioning.

## Tier 2 — strong (significant, clear alternatives)

- **ADR-0006 — Resume & recovery model** (RQ-003, §12). Rev M · Blast H · Trade H · Contract M · Revisit L. Plan + append-only journal/manifest reconciliation (Redis-AOF-style torn-line rule); foundational to unattended batch; hard to retrofit.
- **ADR-0007 — Concurrency primitive: ProcessPool + forkserver, not free-threading** (RQ-016). Rev M · Blast M · Trade H · Contract L · Revisit **H**. Textbook ADR: chose X over free-threading/asyncio with an explicit, dated re-open checklist that wants a durable home.
- **ADR-0008 — Stable document identity (UUIDv7 + manifest path-history)** (RQ-002, §9). Rev **H** · Blast M · Trade M · Contract H · Revisit M. Identity decoupled from filename; 3-tier re-scan recovery; a naming-policy seam. Effectively irreversible once IDs are minted into real files.
- **ADR-0009 — Encoding detection & dual skip-gate** (RQ-022, D-002, FR-007). Rev M · Blast M · Trade H · Contract M · Revisit M. Safety-critical confidence + non-ASCII-floor two-gate design; single-scalar approach explicitly rejected; carries the MS-2 calibration revisit.
- **ADR-0015 — Two-corpus test architecture & anonymization** (RQ-032). Rev M · Blast H · Trade H · Contract H · Revisit M. Generated-never-committed seeded scale corpus vs small committed weird-document corpus, one pure generator; re-synthesis-not-masking anonymization with reviewer gate — the confidentiality contract most likely to be violated expediently. **Drafted 2026-07-06**, status accepted.

## Tier 3 — worth recording (lighter, or bundle)

- **ADR-0010 — Design-for-pluggable policy seams** (RQ-010, D-009). A philosophy ADR governing many decisions (build-minimal, seam-not-machinery). Absorbs RQ-011 (external vocab) as an instance. **Drafted 2026-07-05**, status accepted; RQ-011 recorded inside 0010 rather than as its own ADR (as planned).
- **ADR-0011 — Frontmatter: optional, minimal, mechanical/semantic split** (RQ-008, RQ-014, D-001, D-007). Output-metadata contract + Pandoc target; sibling to ADR-0001. **Drafted 2026-07-05**, status accepted; carries an explicit scope note that it governs _product-output_ frontmatter, distinct from ADR-0001's _repo-doc_ frontmatter-standard non-adoption (conventions #7).
- **ADR-0012 — verify semantics + tool-wide exit-code taxonomy** (RQ-006). Exit codes 0/1/2/3 are a machine/agent API worth pinning. **Drafted 2026-07-05**, status accepted. _Resolution of the "may fold into ADR-0005" question: kept **separate** — exit codes are a CLI-surface contract spanning commands that emit no artifact, so they are not subsumed by ADR-0005's artifact-schema contract._
- **ADR-0013 — v1 runtime & dev dependency selection** (RQ-017/018/019/020/021). One consolidated ADR for structlog/jsonschema/Hypothesis/pydantic/ruamel.yaml + rejected alternatives — not five thin ones. Satisfies §8.6's "every dependency needs a recorded decision." **Drafted 2026-07-05**, status accepted. **Amended 2026-07-06** with the three Batch-B dev deps (`allpairspy`, `import-linter`, `faker`).
- **ADR-0014 — Tool-first product scope** (RQ-024, G-006, NFR-006, WH-008). Rev M-H · Blast H · Trade M · Contract M · Revisit M. The product is the scale-flexible tool, not the pipeline; amends RQ-010/ADR-0010's principle-only resolution, so a second reversal would be doubly expensive; carries WH-008's revisit trigger. **Drafted 2026-07-06**, status accepted.
- **ADR-0016 — The mechanical-transform boundary** (RQ-025/030/031). Rev M · Blast M · Trade M · Contract M · Revisit M as a bundle (individually thin; bundled by the shared reversal surface — the transform dispatch layer — per the 0013 consolidation pattern). File-type dispatch, the non-whitespace content-preservation invariant, and leading-only tab semantics. **Drafted 2026-07-06**, status accepted.

## Deliberately not ADRs (recording _why not_ is part of the backlog)

| Item | Why skip |
| --- | --- |
| RQ-001 (v1 boundary) | Scope — authoritatively in §2; an ADR would duplicate. |
| RQ-009 (perf targets deferred) | A deferral, not a structural choice; revisit trigger lives in the RQ. |
| RQ-011 (external vocab) | An instance of ADR-0010 (seams) — note it there. |
| RQ-012 (EPUB deferred) | Trivial far-future "maybe." |
| RQ-015 (`--write` opt-in) | Small safety-UX detail; fold a paragraph into ADR-0004. |
| RQ-023 (review-artifact exposure) | Governs deferred WH-002/WH-005 — write the ADR when that work is scheduled. |
| D-005 (TOML config) | Conventional, low-tradeoff. |
| RQ-026 (UTF-16/32 BOM-before-NUL) | Refinement inside ADR-0009's gate ordering — recorded there as an amendment (2026-07-06). |
| RQ-027 (single-writer + run lock) | Completes ADR-0007's concurrency story — recorded there as an amendment (2026-07-06). |
| RQ-028 (per-file watchdog/limits) | Hardening mechanism; canonical in FR-019/ERR-009/R-007 + `per-file-watchdog-timeout` research; the process-vs-thread constraint noted in ADR-0007's amendment. |
| RQ-029 (config precedence/merge) | Conventional, low-tradeoff — same class as the D-005 skip; canonical in §18.2's intro. |
| RQ-033 (purity enforcement) as its own ADR | Enforcement detail _of_ ADR-0002's layering — recorded there as an amendment; dependency record in ADR-0013's amendment. |

## Notes

- Numbering: ADR-0001 exists; new ADRs claim 0002+ in this backlog's order. Keep the `id` frontmatter globally unique (`adr-NNNN-docmend-<title>`); the filename omits the repo name.
- These ADRs record decisions already **settled** as RQs (owner-approved), so drafts are authored at `status: accepted`. When an ADR becomes the canonical record, its `RQ-###` entry in `resolved-questions.md` may be condensed to an ADR pointer (per the open/resolved-questions maintenance rules).
