# Open Questions — `docs/specs/docmend.md`

## Important Notes

- **Document Handling Rules and Guidelines:** [How to maintain this document](#how-to-maintain-this-document)
- **Terminology:**
  - _open question_ (`OQ-###`) is a decision still to be made — the primary unit of this document.
  - _resolved question_ (`RQ-###`, already settled) lives in the companion file [`resolved-questions.md`](resolved-questions.md).
- **Priority scale:** open questions carry a `P0 blocker` / `P1 near-blocker` / `P2 decision` label; the gap-analysis-sourced ones also carry a High / Medium / Low gap-analysis priority. The full ranked register with downstream-impact analysis lives in [`gap-analysis.md`](gap-analysis.md).
- **Status:** OQ-001..037 are settled — see [`resolved-questions.md`](resolved-questions.md), RQ-001..037. **One open question:** OQ-038 (non-blocking; implementation proceeds on its recorded assumption per the spec's Appendix B rules).

## Table of Contents

- [Open Questions — `docs/specs/docmend.md`](#open-questions--docsspecsdocmendmd)
  - [Important Notes](#important-notes)
  - [Table of Contents](#table-of-contents)
  - [Open questions](#open-questions)
  - [How to maintain this document](#how-to-maintain-this-document)

## Open questions

<!-- OQ-001..037 are settled — see resolved-questions.md (RQ-001..037). New decisions get added here as OQ-### per the rules below. -->

### OQ-038 — qualification evidence nested contract (`P2 decision`, non-blocking)

**Raised:** 2026-07-13 (DMR-08 Task 3 implementation) **Owner:** owner **Needed by:** DMR-08 pilot and threshold revision **Spec:** §21 OQ-038; touches NFR-001, §9, §14, and OQ-037

**The unresolved decision:** what exact public nested records, finite artifact-key vocabularies, evidence-reference hashing rule, and threshold rounding semantics complete the approved scale-evidence outline without allowing private labels or freezing ambiguous math into the durable schemas?

**Current assumption (implementation proceeds on this per Appendix B):** public records remain strict, frozen, aggregate-only, and use finite artifact-name vocabularies. Preflight records only identifier-free per-filesystem byte/inode budgets and aggregate environment verdicts; totals record conservation and finding counts; threshold verdicts record the loaded limits, observed values, and individual/aggregate pass results. A required memory-method discriminator and mutually exclusive nullable stage fields distinguish external RSS from diagnostic Python-allocation peaks; allocation evidence is diagnostic-only and cannot carry binding thresholds. Threshold point identities are safe POSIX-relative evidence names beneath the threshold file's directory and bind the referenced file's exact bytes with SHA-256. Peak-RSS fitting uses exact rational least squares with an intercept over distinct positive counts; the 25% headroom applies to both the largest peak and non-negative fitted slope with upward integer rounding, while the provisional 20% linearity tolerance remains an explicit generated limit until pilot revision two freezes the executable baseline. Passing installed-wheel pilot/scheduled/release evidence requires an exact wheel hash and completed scan, plan, apply, and verify stages; incomplete evidence may contain the completed stage prefix once build provenance exists. The reference model may represent non-binding diagnostic environments, while a separate comparison determines binding eligibility.

#### Agent notes

- The approved design and implementation plan name `PreflightEvidence`, `QualificationTotals`, `ThresholdVerdict`, `ThresholdPointIdentity`, and `ThresholdSet` but do not define their fields. The plan also proposes unconstrained string-keyed maps even though the public-repository privacy contract and strict-schema convention require closed public vocabularies.
- Task 9 is the approval boundary: its reviewed pilot evidence and specification revision two may adopt or amend this assumption before any numeric threshold becomes binding.

#### My Comments

(none yet — owner block, agent does not edit)

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
6. **Not a log:** Do not append a log of routine maintenance or administrative changes. This is a _decision record_, not a change log. Use the Git history for that and `docs/handoff/` and/or `TODO.md` where appropriate.
