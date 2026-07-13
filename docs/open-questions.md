# Open Questions — `docs/specs/docmend.md`

## Important Notes

- **Document Handling Rules and Guidelines:** [How to maintain this document](#how-to-maintain-this-document)
- **Terminology:**
  - _open question_ (`OQ-###`) is a decision still to be made — the primary unit of this document.
  - _resolved question_ (`RQ-###`, already settled) lives in the companion file [`resolved-questions.md`](resolved-questions.md).
- **Priority scale:** open questions carry a `P0 blocker` / `P1 near-blocker` / `P2 decision` label; the gap-analysis-sourced ones also carry a High / Medium / Low gap-analysis priority. The full ranked register with downstream-impact analysis lives in [`gap-analysis.md`](gap-analysis.md).
- **Status:** OQ-001..037 are settled — see [`resolved-questions.md`](resolved-questions.md), RQ-001..037. **Four open questions:** OQ-038, OQ-039, OQ-040, and OQ-041 (all non-blocking; implementation proceeds on their recorded assumptions per the spec's Appendix B rules).

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

**Current assumption (implementation proceeds on this per Appendix B):** public records remain strict, frozen, aggregate-only, and use finite artifact-name vocabularies. Preflight records only identifier-free per-filesystem byte/inode budgets and aggregate environment verdicts; totals record conservation and finding counts; threshold verdicts record the loaded limits, observed values, and individual/aggregate pass results. A required memory-method discriminator and mutually exclusive nullable stage fields distinguish external RSS from diagnostic Python-allocation peaks; allocation evidence is diagnostic-only and cannot carry binding thresholds. Threshold point identities are safe POSIX-relative evidence names beneath the threshold file's directory and bind the referenced file's exact bytes with SHA-256. Threshold schema 2.0 preserves stage identity across the immutable 10,000/100,000-file snapshots: each stage gets a non-negative exact two-point slope and 1,000,000-file prediction; the absolute limit is 25% above the largest stage prediction, the slope limit is 25% above the largest stage slope, both rounded upward, and the linearity tolerance is exactly 20%. Scheduled evaluation compares the current 100,000-file stage peaks with the 10,000-file anchors; release evaluation uses exact per-stage least-squares slopes over all three counts and maximum relative deviation from the pilot projection. Public observed slope and linearity round only upward. Passing installed-wheel pilot/scheduled/release evidence requires an exact wheel hash and completed scan, plan, apply, and verify stages; incomplete evidence may contain the completed stage prefix once build provenance exists. The reference model may represent non-binding diagnostic environments, while a separate comparison determines binding eligibility.

#### Agent notes

- The approved design and implementation plan name `PreflightEvidence`, `QualificationTotals`, `ThresholdVerdict`, `ThresholdPointIdentity`, and `ThresholdSet` but do not define their fields. The plan also proposes unconstrained string-keyed maps even though the public-repository privacy contract and strict-schema convention require closed public vocabularies.
- Task 9 is the approval boundary: its reviewed pilot evidence and specification revision two may adopt or amend this assumption before any numeric threshold becomes binding.
- Task 6 review found that the original largest-100k-peak helper could not provide the required 1M absolute ceiling. Schema 2.0 corrects that meaning before any threshold baseline is accepted; OQ-041 carries the orchestration and partial-evidence boundary.

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

### OQ-041 — qualification orchestration completion contract (`P2 decision`, non-blocking)

**Raised:** 2026-07-13 (DMR-08 Task 6 pre-implementation review) **Owner:** owner **Needed by:** DMR-08 qualification orchestrator and pilot **Spec:** §21 OQ-041; touches NFR-001, §9, §14, §17.2, OQ-038, OQ-039, and OQ-040

**The unresolved decision:** what exact partial-evidence, threshold-evaluation, exact-HEAD build, workspace, reference-observation, provisional-capacity, runtime, acceptance, and process-exit contract completes the approved Task 6 orchestrator without publishing false evidence or resolving mutable/unpinned inputs during a binding run?

**Current assumption (implementation proceeds on this per Appendix B):** scale-evidence advances to 2.0 and uses a finite `outcome_reason`, nullable preflight, phase-derived totals, and an ordered attempted stage prefix. Public stage `completed` means a trustworthy reaped child measurement; separate `artifact_validated` means the required durable artifacts passed their own schema/identity boundary. The state rules are biconditional: incomplete measurement forces null exit/RSS, completed measurement requires exit plus exactly one memory value, non-validated artifact forces null run ID, and validated artifact requires the exact stage key set including `structured-log`. Passing and otherwise-correct complete diagnostic evidence enforce full conservation; failed evidence preserves observed discrepancies; incomplete evidence uses zeros for phases not proven by validated artifacts. Missing/unreadable/schema-invalid artifacts are incomplete, while safely loaded artifacts whose facts disagree are failed. Status precedence is incomplete for harness/environment inability, failed for trustworthy product/threshold/runtime failure, diagnostic for explicit or reference-nonbinding complete correctness, and passing only for the binding four-stage/zero-swap/exact-reconciliation contract. The six product schema versions come only from owner constants, including a new frontmatter constant.

The clean 40-hex `HEAD` is archived and safely extracted into a new held mode-0700 workspace outside the checkout. Qualification fixes `uv 0.11.6` and `uv_build==0.11.6`, forces the declared PEP 517 backend, installs the hash-locked runtime closure plus the one hashed wheel into a fresh venv, verifies wheel metadata/import origins, records both build versions, and rechecks `HEAD` plus tracked/untracked cleanliness through acceptance. Every stage uses a new isolated candidate-venv supervisor and absolute candidate `docmend`, with private home/state/config/temp roots and Task 5's tracing exclusions. Workspace reuse/symlink substitution is refused; failure residue is preserved.

Reference capture reads one immutable public snapshot and derives local storage conservatively from the eligible mount's complete sysfs leaf set: all non-rotational leaves are `local-ssd`, all rotational leaves `local-hdd`, and mixed/unavailable proof is `unknown` and non-binding. The freshly written corpus is `warm`. Build/install precede capacity preflight so their allocation is already reflected. Pre-pilot allowances are fixed at 256 MiB base; 2,048 bytes/input inventory; 4,096 bytes/input plan; 2,048 bytes/action report; 8,192 bytes/action manifest; 1,024 bytes/input verify report; 4,096 bytes/input/stage structured logs; four separately rounded 2 MiB private supervisor files per stage; the largest estimated atomic artifact; the largest rendered writer staging file; and 64 additional non-corpus inodes. Placement is explicit before filesystem grouping: each workspace/corpus-parent/artifact/supervisor destination is an identity-held existing no-follow probe directory with its own observed fragment size; the corpus summary records and matches its placement fragment. Named files are rounded with their destination fragment, grouped by followed filesystem, and receive one exact 25% margin. Exceeding an allowance makes the run incomplete; pilot revision two may raise but never silently lower coefficients.

Only release evidence may carry workflow runtime: it is null before scan dispatch, required once dispatch begins, and for a complete run is at least the sum of published stage elapsed values. Timing is monotonic scan-dispatch through the last validated attempted result, including inter-stage validation but excluding setup/materialization/publication; 43,200 seconds passes and any greater value fails without claiming a hard-kill guarantee. Invalid invocation, dirty/unfixed provenance, and occupied/inside-checkout ordinary evidence output refuse exit 2 before evidence. Post-provenance passing and explicitly requested successful diagnostics exit 0; failed/incomplete evidence exits 1; an otherwise-correct reference-mismatched binding request publishes diagnostic evidence but exits 1. Multiple conditions choose one reason deterministically: trustworthy stage/conservation/finding/threshold/runtime failures first in that order, then the first execution-order lifecycle blocker, then reference mismatch, then explicit diagnostic. `--evidence-out` publishes first outside the checkout and never overwrites. `--accept-to` is an existing directory; only passing binding evidence may publish identical canonical bytes as `{full-commit}-{tier}-{count}.json` (or `{full-commit}-file-size.json`), also no-clobber.

#### Agent notes

- Independent contract, provenance, and adversarial-plan reviews all found the literal four-file Task 6 unsafe. The split into Task 6A contract completion and Task 6B orchestration preserves the approved Tasks 7-12 order and does not pull heartbeat, workflow, pilot, file-size, or release evidence forward.
- Task 6A now implements the reusable evidence/threshold 2.0, transport, schema-provenance, reference-observation, and capacity contracts on this assumption. Task 6B orchestration and the Task 9 pilot/revision-two owner approval boundary remain pending.
- Scale-evidence 2.0 and thresholds 2.0 are major bumps because non-passing evidence and the absolute threshold change meaning. No accepted scale evidence or threshold baseline exists, so there is no accepted artifact to migrate.
- The Task 9 pilot/revision-two review remains the owner approval boundary for OQ-038 through OQ-041 and all numeric thresholds/coefficient evidence.

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
