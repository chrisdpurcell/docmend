# Open Questions — `docs/specs/docmend.md`

## Important Notes

- **Document Handling Rules and Guidelines:** [How to maintain this document](#how-to-maintain-this-document)
- **Terminology:**
  - _open question_ (`OQ-###`) is a decision still to be made — the primary unit of this document.
  - _resolved question_ (`RQ-###`, already settled) lives in the companion file [`resolved-questions.md`](resolved-questions.md).
- **Priority scale:** open questions carry a `P0 blocker` / `P1 near-blocker` / `P2 decision` label; the gap-analysis-sourced ones also carry a High / Medium / Low gap-analysis priority. The full ranked register with downstream-impact analysis lives in [`gap-analysis.md`](gap-analysis.md).
- **Status:** OQ-001..037 are settled — see [`resolved-questions.md`](resolved-questions.md), RQ-001..037. **Two open questions:** OQ-038 and OQ-039 (both non-blocking; implementation proceeds on their recorded assumptions per the spec's Appendix B rules).

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

### OQ-039 — qualification resource-preflight semantics (`P2 decision`, non-blocking)

**Raised:** 2026-07-13 (DMR-08 Task 4 implementation) **Owner:** owner **Needed by:** DMR-08 pilot **Spec:** §21 OQ-039; touches NFR-001, §14, §17.2, and OQ-037

**The unresolved decision:** what exact capacity-margin arithmetic, reference-class equivalence, mount-option projection, and unavailable swap behavior govern binding DMR-08 resource preflight?

**Current assumption (implementation proceeds on this per Appendix B):** requirement byte values are pre-margin physical-allocation estimates whose per-file logical sizes have already been rounded to the filesystem fragment size. Requirements are grouped by followed `st_dev`; then one exact 25% margin, rounded upward, is applied per filesystem to both aggregate bytes and aggregate inodes. Tests of grouping alone pass an explicit zero margin. Reference matching is exact across all public fields except that mount-flag order is immaterial; binding eligibility additionally requires Linux, at least 16 GiB RAM, `local-ssd`, ext4/XFS/btrfs, passing capacity, and zero child swap. Only the existing finite value-free allowlist from mountinfo field 6 (per-mount options) enters public records; an unknown or value-bearing field-6 option remains private and makes the observed mount non-binding rather than being published. Mountinfo field 11 (superblock options) always remains private and does not affect the public reference class. A missing, duplicate, malformed, unreadable, or unknown-unit child `VmSwap` sample makes binding qualification incomplete; global `pswpin`/`pswpout` deltas are diagnostic-only and never override the child-zero rule.

#### Agent notes

- The approved design requires a deterministic 25% byte/inode margin, while the Task 4 grouping example expects the un-margined sum of 150 bytes. Making the grouping test's zero margin explicit preserves both requirements.
- The approved reference-class prose does not say whether recorded RAM/CPU/runtime fields are exact class identity or minimum/compatible comparisons, and “no material swap activity” does not define how unavailable child telemetry behaves. The conservative assumption prevents a missing measurement from becoming a false zero.
- Mountinfo exposes per-mount and superblock option fields separately. Keeping field 11 private avoids publishing value-bearing filesystem details or misclassifying an otherwise eligible btrfs mount solely because those private details exist.
- Task 9 is the owner approval boundary: pilot review and specification revision two may adopt or amend this assumption before evidence becomes binding.

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
