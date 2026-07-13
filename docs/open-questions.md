# Open Questions — `docs/specs/docmend.md`

## Important Notes

- **Document Handling Rules and Guidelines:** [How to maintain this document](#how-to-maintain-this-document)
- **Terminology:**
  - _open question_ (`OQ-###`) is a decision still to be made — the primary unit of this document.
  - _resolved question_ (`RQ-###`, already settled) lives in the companion file [`resolved-questions.md`](resolved-questions.md).
- **Priority scale:** open questions carry a `P0 blocker` / `P1 near-blocker` / `P2 decision` label; the gap-analysis-sourced ones also carry a High / Medium / Low gap-analysis priority. The full ranked register with downstream-impact analysis lives in [`gap-analysis.md`](gap-analysis.md).
- **Status:** OQ-001..037 are settled — see [`resolved-questions.md`](resolved-questions.md), RQ-001..037. **Three open questions:** OQ-038, OQ-039, and OQ-040 (all non-blocking; implementation proceeds on their recorded assumptions per the spec's Appendix B rules).

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

### OQ-040 — streamed scale corpus and private stage-supervisor contract (`P2 decision`, non-blocking)

**Raised:** 2026-07-13 (DMR-08 Task 5 implementation) **Owner:** owner **Needed by:** DMR-08 pilot **Spec:** §21 OQ-040; touches NFR-001, §14, §17.2, and OQ-037

**The unresolved decision:** what exact deterministic corpus summary/materialization semantics and private request/result/process/file contract complete Task 5 without making conservation, resource budgeting, or RSS/swap evidence platform- or race-dependent?

**Current assumption (implementation proceeds on this per Appendix B):** `iter_recipes(count)` accepts a strict non-boolean integer from 1 through 1,000,000 and streams unique frozen recipes in index order without retaining prior recipes. The 40-bucket mix is normative: 24 UTF-8/LF `.txt` renames, 8 UTF-8/CRLF `.txt` rewrites plus renames, 4 clean UTF-8/LF Markdown no-ops, 2 UTF-8/CRLF Markdown rewrites, 1 confidently detectable legacy conversion above the non-ASCII floor, and 1 below-floor legacy skip that yields exactly one encoding finding. Every full traversal starts a fresh fixed-seed `random.Random` and consumes one render per recipe, so the no-write summary and materialization byte counts match. Summary allocated bytes round each regular file before aggregation; directory metadata, artifacts, logs, and staging allowances remain separate. Directory/inode accounting includes the corpus root, `lib`, every used first-level shard, and every used second-level shard. Materialization requires an absent root; publishes owner-only directories from held, empty private descriptors with Linux `renameat2(RENAME_NOREPLACE)`; creates every regular file exclusively with no-follow; and reconciles the final published name of every bounded shard identity before returning. It never merges, resets, deletes, or follows stale entries.

The supervisor transport is strict versioned private JSON. A request identifies one stage, a non-empty NUL-free scalar-Unicode argv, an existing absolute cwd, a validated finite environment overlay, and safe workspace-relative stdout/stderr names; the result records that stage, completion, nullable exit/RSS on spawn/reap failure, nullable child-swap peak, elapsed time, tracing-disabled state, private output names, and a finite generic error code. The request is opened no-follow; one real mode-0700 workspace identity is held across request loading, output capture, and publication; and all private outputs publish exclusively as owner-only regular files. The result is hard-linked no-clobber from its held staged descriptor and reconciled by no-follow identity, type, and mode rather than trusted through a mutable temporary name. The final child environment starts from only a fixed safe inherited allowlist plus the request overlay, never an arbitrary parent-environment copy; it rejects NULs and explicit tracing/instrumentation overrides, removes `PYTHONTRACEMALLOC`, `PYTHONPATH`, and `PYTHONHOME`, and forces `PYTHONNOUSERSITE=1`. Every spaced or combined direct-Python `-X tracemalloc[=N]` argv form is refused, and environment-launcher wrappers are refused rather than allowed to bypass that proof. One fresh supervisor creates exactly one `Popen(..., shell=False)` child, samples child `VmSwap` immediately and every 50 ms, makes one explicit `Popen.wait()` finalization call even after telemetry failure, then reads `RUSAGE_CHILDREN.ru_maxrss` once and converts Linux KiB to bytes. Elapsed time spans immediately before spawn through immediately after that wait. Any unavailable/malformed swap sample yields `null`, never a false zero; a nonzero child exit is still a completed measurement. The wrapper returns `0` whenever it exclusively publishes a trustworthy private result, including nonzero-child and incomplete spawn/reap results; invalid invocation/request contracts return `2`, failures before trustworthy publication return `1`, and no wrapper status mirrors the child exit.

#### Agent notes

- The historical Faker-backed bucket 38 produced only 16 non-ASCII bytes and therefore joined bucket 39 as a skip (34 actions / 4 no-ops / 2 skips per 40). Task 5 intentionally corrects the normative mix to 35 / 4 / 1 and pins it through the real detector/planner rather than preserving incidental bytes.
- For `n = 40q + r`, bucket `b` occurs `q + int(b < r)` times. At one million files this yields 875,000 actions, 100,000 no-ops, 25,000 plan skips/findings, 2,228 directories, and 1,002,228 required inodes.
- Private request/result/output data may contain operational paths and argv but never enters public `StageEvidence`; unavailable swap telemetry makes evidence incomplete under OQ-039.
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
