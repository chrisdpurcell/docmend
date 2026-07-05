# Open Questions — `docs/specs/docmend.md`

## Important Notes

- **Document Handling Rules and Guidelines:** [How to maintain this document](#how-to-maintain-this-document)
- **Terminology:**
  - _open question_ (`OQ-###`) is a decision still to be made — the primary unit of this document.
  - _resolved question_ (`RQ-###`, already settled) lives in the companion file [`resolved-questions.md`](resolved-questions.md).
- **Priority scale:** open questions carry a `P0 blocker` / `P1 near-blocker` / `P2 decision` label; the gap-analysis-sourced ones also carry a High / Medium / Low gap-analysis priority. The full ranked register with downstream-impact analysis lives in [`gap-analysis.md`](gap-analysis.md).
- **Status:** all legacy OQ-001..014 and the gap-analysis OQ-016..022 are now settled (see [`resolved-questions.md`](resolved-questions.md), RQ-001..021). Only **OQ-015** and **OQ-023** remain open.

## Table of Contents

- [Open Questions — `docs/specs/docmend.md`](#open-questions--docsspecsdocmendmd)
  - [Important Notes](#important-notes)
  - [Table of Contents](#table-of-contents)
  - [Open questions](#open-questions)
    - [OQ-015 — encoding detector, confidence signal, and dual skip thresholds](#oq-015--encoding-detector-confidence-signal-and-dual-skip-thresholds)
      - [Agent notes](#agent-notes)
      - [My Comments](#my-comments)
    - [OQ-023 — deferred-review-artifact content-exposure policy (WH-002/WH-005)](#oq-023--deferred-review-artifact-content-exposure-policy-wh-002wh-005)
      - [Agent notes](#agent-notes-1)
      - [My Comments](#my-comments-1)
  - [How to maintain this document](#how-to-maintain-this-document)

## Open questions

<!-- Settled questions live in resolved-questions.md (RQ-001..021). Only OQ-015 and OQ-023 remain open. -->

### OQ-015 — encoding detector, confidence signal, and dual skip thresholds

**Priority:** P0 blocker · Gap-analysis priority: High **Owner:** owner **Needed by:** MS-2 **Blocking:** Yes **Spec references:** `docs/specs/docmend.md` FR-007, §18.2 encoding.fail_below_confidence, A-003, G-005, §8.6 · Related: RQ-001 (v1 boundary)

Confirm charset-normalizer as FR-007's sole detector, define the decode-confidence score as 1.0 - CharsetMatch.chaos, keep the 0.80 fail_below_confidence default, and set a second independent skip gate keyed on non-ASCII byte count (default in the 8-20 range, encoding-family dependent).

#### Agent notes

**Recommendation:** Keep charset-normalizer only (do not add chardet — active licensing dispute, or faust-cchardet/uchardet — no 3.14 wheels/no confidence API). Adopt confidence = 1.0 - CharsetMatch.chaos, the library's own shipping chardet-compat formula (with the -0.2 penalty below 32 bytes), recording chaos/coherence/language separately as provenance. Keep the 0.80 threshold (always exceeds the worst-case penalized 0.70). Add a non-ASCII-byte-count floor as a second, independent skip gate, with the exact default validated against the weird-document corpus.

**Supporting information:** Report docs/research/encoding-detection-benchmark.md (20 citations): charset-normalizer 3.x CharsetMatch has no .confidence, only chaos/coherence; legacy detect() shim computes 1.0-chaos; documented GitHub issue #391 shows a 38-byte ASCII+1-byte string misdetected as Big5 at chaos=0.0 (max confidence, wrong) that no confidence threshold catches; Sivonen/chardetng convergence study shows windows-1252 needs ~20 and CJK ~10 non-ASCII bytes for reliable detection — so byte length is the wrong unit and a non-ASCII count floor is the right second gate.

**Reasoning:** The threshold governs false-skip/false-accept rates for the core safety premise; a single confidence scalar provably cannot catch the short-low-entropy failure mode that this .txt-heavy library is full of, so a second independent gate is required, not optional.

**Decision impact:** Unblocks MS-2 transform hardening with an evidence-backed decode/skip contract; without it FR-007 references a confidence API that does not exist as specified.

**Downstream impact:** Adds a non-ASCII-floor config key to §18.2, adds chaos/coherence/language provenance fields to the inventory schema (feeds RQ-004), reworks FR-007/FR-016 wording, and adds the report's fixture set to §17.2; also fixes GAP-43 (confidence-API mismatch) in the same change.

**Research update (2026-07-05, owner ChatGPT report):** `docs/research/python-library-research.md` independently confirms `charset-normalizer` as the FR-007 detector, but its proposed `DetectedEncoding` interface carries a `confidence: float` field — note that charset-normalizer 3.x exposes no `.confidence` (only `chaos`/`coherence`); use the `1.0 - chaos` formula from `docs/research/encoding-detection-benchmark.md` (this OQ's primary basis), not a `.confidence` attribute. The report also endorses recording the detector version and confidence in the plan (C.4 provenance).

**Research update (2026-07-05, charset-floor deep-research):** `docs/research/charset-detection-floors-for-legacy-text-ingestion.md` resolves the one sub-question this OQ left to empirical validation — the exact non-ASCII floor for the second, independent skip gate — and **narrows the provisional "8–20 range" to concrete defaults**:

- **Primary hard gate (default): `non_ascii_bytes >= 20`** before trusting any legacy (non-Unicode) guess. Basis: Sivonen/chardetng "document-length-equivalent" convergence — windows-1252/windows-1251 settle at ~20 non-ASCII bytes, legacy CJK at ~10, with almost everything converged by 50–90.
- **Optional family-aware override:** Western single-byte ≥ 20; CJK multi-byte ≥ 12; **Big5 relaxable to 10** (structurally distinctive on short input, per Sivonen), while GBK/GB18030 stays ≥ 12 ("bad with fewer than 6 hanzi").
- **The floor is count-based, not ratio-based.** The published evidence is in absolute non-ASCII counts. A ratio rule is only a secondary hardening signal for sparse long files: `total_bytes >= 4096 && non_ascii_ratio < 0.005 → mark the accepted legacy result "suspect" and prefer skip-and-report` (an engineering choice, not a literature constant).
- **Gate ordering (the floor applies last):** BOM sniff (authoritative, bypass legacy) → strict **full-file** UTF-8 validity (accept UTF-8, bypass legacy) → ASCII-only ⇒ treat as ASCII/UTF-8, never "detect" as legacy → only non-BOM, non-valid-UTF-8 files reach the byte-count floor.
- **Tradeoff (stated):** the 20-byte default deliberately false-skips some genuine tiny Latin-1 and very short CJK files in exchange for sharply cutting the `chaos=0.0`-but-wrong false-accept on short mostly-ASCII English — the dominant risk for this `.txt`-heavy corpus, where skip-and-report is the safe failure.
- **Version sensitivity (feeds §8.6 pin + FR-007 wording):** charset-normalizer **3.4.2** improved CJK reliability and **3.4.3** began damping confidence on small non-Unicode samples, so floor validation must run on ≥ 3.4.2 (3.4.7 ships 3.14 wheels); keep all ingest on explicit binary reads + explicit decode, not ambient `open()` defaults (3.15 moves to a UTF-8 default).
- **Fixtures:** the report's algorithmic synthetic/public-domain recipe (three axes — total length × non-ASCII count × placement; explicit false-accept and false-skip boundary sets; family-equivalent decode outcomes such as cp932≈Shift_JIS and GBK≈GB18030) should be added to the §17.2 weird-document corpus. **The final chosen number still needs one project-internal run against docmend's own short-file distribution before FR-007/§18.2 are edited.**

#### My Comments

### OQ-023 — deferred-review-artifact content-exposure policy (WH-002/WH-005)

**Priority:** P2 decision · Gap-analysis priority: Low **Owner:** owner **Needed by:** WH-002 / WH-005 design (deferred — §2.3) **Blocking:** No **Spec references:** `docs/specs/docmend.md` §2.2 NG-001, §2.3 WH-002/WH-005, §11, §13.4, §13.5 · Related: RQ-001 (v1 boundary), RQ-010 (genericity)

Decide how much document content a headless deferred-review artifact may carry before it crosses NG-001's "no reading/browsing interface" boundary, and the default review posture — for the deferred semantic-correction (WH-002) and fuzzy-duplicate (WH-005) capabilities. Raised by prompt 4 of the deep-research queue, which surfaced a genuine, previously-undocumented conflict: docmend's artifacts are deliberately hash-and-path-only and its content is confidential (§13.4), yet a WH-002 correction cannot be reviewed without showing the changed text, and NG-001 forbids a reading UI. No existing OQ owned this decision.

#### Agent notes

**Recommendation:** Adopt the content-exposure boundary **"issue-bounded, decision-sufficient, non-navigable, and opt-in for text."** A review artifact stays headless (NG-001-compatible) when it is keyed to a finite set of flagged issues/clusters, carries only the minimum information needed for a yes/no/edit verdict, and offers no search, browse, whole-file expansion, or progressive-context surface inside docmend. Concretely:

- **WH-005 (fuzzy duplicates): metadata-only by default** — `cluster_id`, path aliases, sizes, hashes, similarity scores, recommended canonical, blank `decision` field. Body text is unnecessary. Matches `rdfind`/`fclones` report-then-act precedent.
- **WH-002 (semantic corrections): durable metadata ledger with no body text by default.** Any text lives in an **opt-in, local-only ephemeral sidecar** keyed by `issue_id` (the "durable-manifest / ephemeral-sidecar" split, by analogy to Terraform `sensitive` vs `ephemeral`), or is handed off to an **external diff tool** — never embedded in the durable artifact by default. When text is exposed, use **bounded unified-diff-style hunks with tight operator-configurable char/line caps**, **path aliases not raw paths** (paths are quasi-identifiers), and optional PII redaction as a secondary (not default) mode.
- **Default posture: pessimistic-skip / exception-only**, capped batches, `decision` left null (no pre-filled "accept"), no bulk-approve for text-bearing changes. The automation-bias literature (Goddard et al. 2012; Cummings; Green) shows large repetitive review queues degrade into rubber-stamping — so "review everything" is the wrong default twice: it leaks more text than necessary and manufactures the conditions for rubber-stamping.
- **Public-repo / confidential split:** text-bearing review artifacts are **private local artifacts**, never ordinary build outputs, never repo/CI artifacts, and never version-controlled; do not retain long-lived snippet archives (NIST SP 800-188 repeated-release risk). Fixtures/tests/docs stay synthetic or public-domain (C-002) regardless.
- **Load-bearing answer to "keep WH-002 review out of docmend entirely?":** docmend may **identify, package, and record** review decisions; **external tools render text**. Keeping rendering out of docmend is the cleanest NG-001 alignment and lowest-maintenance path — but it does not require forbidding docmend from generating a minimal machine-readable handoff bundle.

**Supporting information:** `docs/research/docmend-deferred-review-artifacts-for-confidential-corpora.md` (headless report-then-act survey — `patch`/`git apply --reject`, unified diff, `rdfind`/`fclones`, `dedupe`'s engine/UI split, Terraform plan; ISO/IEC 20889 and NIST SP 800-188 de-identification/output-governance guidance; automation-bias evidence). The report states plainly that no cited source gives a formal industry definition of "headless" for confidential-document remediation — the boundary is a well-supported architectural inference, not a standard.

**Reasoning:** The decision sits at the intersection of an architectural non-goal (NG-001), a confidentiality threat model (§13.4/§13.5), and de-identification standards, so it is an owner policy call rather than a factual lookup. Settling it now — while the research is fresh — prevents WH-002/WH-005 design from either silently building a de-facto reading UI or blocking on an unmade policy decision.

**Decision impact:** Sets the artifact shape and default posture for the future WH-002/WH-005 review workflows; would add a note to §11 (how a decision artifact stays distinct from NG-001's forbidden UI) and to §13.4/§13.5 (text-bearing review artifacts as a distinct, private, non-versioned sensitive-data class with its own leakage mitigation). Non-blocking because WH-002/WH-005 are deferred (§2.3); revisit when either is scheduled.

**Downstream impact:** If adopted, the future WH-002 artifact is a two-layer (durable metadata ledger + opt-in ephemeral text sidecar / external-diff handoff) design and WH-005 is a metadata-only cluster report; both feed the OQ-004 artifact-schema family when that work reaches the deferred capabilities. If the owner instead delegates WH-002 review wholly to external diff tools, docmend stops at detection + decision-recording and emits no text at all.

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
