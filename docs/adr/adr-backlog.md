# ADR Candidate Backlog

**Purpose:** LLM-facing tracking record for docmend's Architecture Decision Records. Derived from a comprehensive review of [`docs/specs/docmend.md`](../specs/docmend.md) (design decisions D-001–D-009) and [`docs/resolved-questions.md`](../resolved-questions.md) (RQ-001–RQ-023), 2026-07-05. Not itself an ADR.

**How this list was built.** ADR candidates come from two converging sources — the spec's own `D-###` design decisions (which already carry considered-alternatives) and the settled-question backlog (`RQ-###`). Candidates are **bundled by decision cohesion and shared reversal cost** (things revisited _together_ share one ADR), not one-ADR-per-RQ. Each was scored on five ADR-worthiness axes: **Rev** (cost to reverse), **Blast** (cross-cutting reach), **Trade** (richness of rejected alternatives), **Contract** (durable external contract), **Revisit** (has live re-open criteria).

## Status

| ADR | Title | Tier | Sources | Status |
| --- | --- | --- | --- | --- |
| 0001 | Do not adopt the Markdown Frontmatter Standard | — | D-008 | ✅ accepted |
| 0002 | Layered pipeline with an isolated writer | 🔴 1 | D-003, D-006 | ✍️ drafted 2026-07-05 |
| 0003 | In-place mutation + atomic-replace output model | 🔴 1 | RQ-013 ⚑, D-004 | ✍️ drafted 2026-07-05 |
| 0004 | Apply safety gate + preservation posture | 🔴 1 | RQ-005 ⚑, RQ-007 | ✍️ drafted 2026-07-05 |
| 0005 | Durable artifact schema contract (JSON + NDJSON) | 🔴 1 | RQ-004 ⚑, DR-001–004 | ✍️ drafted 2026-07-05 |
| 0006 | Resume & recovery model | 🟡 2 | RQ-003 | ✍️ drafted 2026-07-05 |
| 0007 | Concurrency primitive: ProcessPool + forkserver | 🟡 2 | RQ-016 | ✍️ drafted 2026-07-05 |
| 0008 | Stable document identity (UUIDv7 + manifest) | 🟡 2 | RQ-002 | ✍️ drafted 2026-07-05 |
| 0009 | Encoding detection & dual skip-gate | 🟡 2 | RQ-022, D-002 | ✍️ drafted 2026-07-05 |
| 0010 | Design-for-pluggable policy seams | 🟢 3 | RQ-010, D-009 | ✍️ drafted 2026-07-05 |
| 0011 | Frontmatter: optional, minimal, mechanical/semantic split | 🟢 3 | RQ-008/014, D-001/007 | ✍️ drafted 2026-07-05 |
| 0012 | verify semantics + tool-wide exit-code taxonomy | 🟢 3 | RQ-006 | ✍️ drafted 2026-07-05 |
| 0013 | v1 runtime & dev dependency selection (consolidated) | 🟢 3 | RQ-017/018/019/020/021 | ✍️ drafted 2026-07-05 |

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

## Tier 3 — worth recording (lighter, or bundle)

- **ADR-0010 — Design-for-pluggable policy seams** (RQ-010, D-009). A philosophy ADR governing many decisions (build-minimal, seam-not-machinery). Absorbs RQ-011 (external vocab) as an instance. **Drafted 2026-07-05**, status accepted; RQ-011 recorded inside 0010 rather than as its own ADR (as planned).
- **ADR-0011 — Frontmatter: optional, minimal, mechanical/semantic split** (RQ-008, RQ-014, D-001, D-007). Output-metadata contract + Pandoc target; sibling to ADR-0001. **Drafted 2026-07-05**, status accepted; carries an explicit scope note that it governs _product-output_ frontmatter, distinct from ADR-0001's _repo-doc_ frontmatter-standard non-adoption (conventions #7).
- **ADR-0012 — verify semantics + tool-wide exit-code taxonomy** (RQ-006). Exit codes 0/1/2/3 are a machine/agent API worth pinning. **Drafted 2026-07-05**, status accepted. _Resolution of the "may fold into ADR-0005" question: kept **separate** — exit codes are a CLI-surface contract spanning commands that emit no artifact, so they are not subsumed by ADR-0005's artifact-schema contract._
- **ADR-0013 — v1 runtime & dev dependency selection** (RQ-017/018/019/020/021). One consolidated ADR for structlog/jsonschema/Hypothesis/pydantic/ruamel.yaml + rejected alternatives — not five thin ones. Satisfies §8.6's "every dependency needs a recorded decision." **Drafted 2026-07-05**, status accepted.

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

## Notes

- Numbering: ADR-0001 exists; new ADRs claim 0002+ in this backlog's order. Keep the `id` frontmatter globally unique (`adr-NNNN-docmend-<title>`); the filename omits the repo name.
- These ADRs record decisions already **settled** as RQs (owner-approved), so drafts are authored at `status: accepted`. When an ADR becomes the canonical record, its `RQ-###` entry in `resolved-questions.md` may be condensed to an ADR pointer (per the open/resolved-questions maintenance rules).
