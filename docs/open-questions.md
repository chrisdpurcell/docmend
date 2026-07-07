# Open Questions — `docs/specs/docmend.md`

## Important Notes

- **Document Handling Rules and Guidelines:** [How to maintain this document](#how-to-maintain-this-document)
- **Terminology:**
  - _open question_ (`OQ-###`) is a decision still to be made — the primary unit of this document.
  - _resolved question_ (`RQ-###`, already settled) lives in the companion file [`resolved-questions.md`](resolved-questions.md).
- **Priority scale:** open questions carry a `P0 blocker` / `P1 near-blocker` / `P2 decision` label; the gap-analysis-sourced ones also carry a High / Medium / Low gap-analysis priority. The full ranked register with downstream-impact analysis lives in [`gap-analysis.md`](gap-analysis.md).
- **Status:** OQ-001..033 are settled — see [`resolved-questions.md`](resolved-questions.md), RQ-001..033. **Three open questions:** OQ-034, OQ-035, OQ-036 (all non-blocking; implementation proceeding on their recorded assumptions per the spec's Appendix B rules).

## Table of Contents

- [Open Questions — `docs/specs/docmend.md`](#open-questions--docsspecsdocmendmd)
  - [Important Notes](#important-notes)
  - [Table of Contents](#table-of-contents)
  - [Open questions](#open-questions)
  - [How to maintain this document](#how-to-maintain-this-document)

## Open questions

<!-- OQ-001..033 are settled — see resolved-questions.md (RQ-001..033). New decisions get added here as OQ-### per the rules below. -->

### OQ-034 — default artifact/log output location (`P2 decision`, non-blocking)

**Raised:** 2026-07-06 (MS-1 implementation) **Owner:** owner **Needed by:** MS-3 (before apply multiplies the artifact set) **Spec:** §21 OQ-034; touches IR-001, §18.2 (`paths.exclude` default), §18.5, OQ-006 (sidecar discovery)

**The unresolved decision:** where do run artifacts and the per-run log go when the operator passes no flags? IR-001's `--report` is optional, §18.5 requires an artifact for every run, and no spec section names a default path.

**Current assumption (implementation proceeds on this per Appendix B):** a `.docmend/` directory created in the **invoking directory** (not inside the scanned tree, unless the operator runs from there) holds the per-run log (`docmend-{run-id}.jsonl` — the MS-0 convention unchanged) and run artifacts (`docmend-{run-id}-inventory.json`; later `-plan.json`, `-report.json`, `-manifest.ndjson`). Explicit flags (`--report`, and the future `--out`-family) override per artifact. `.docmend/` is added to the §18.2 default excludes so the tool's own output can never become a scan candidate. The run-ID-keyed sibling naming is deliberately the input `verify`'s OQ-006 sidecar-discovery convention will consume at MS-4.

#### Agent notes

- Alternatives considered: bare files in the CWD (clutters, and a second run doubles it); alongside the scanned root (pollutes the library being processed — worst option given FR-001's read-only posture, though only the _tool's_ directory, never library files, would be written); XDG state dir (`~/.local/state/docmend/` — survives anywhere but hides the artifacts the operator is supposed to review; the plan file is a review surface, D-006).
- A future `artifacts.dir` config key could make this configurable; deliberately **not** added now — §18.2 is spec-governed and the flag override suffices for v1.

#### My Comments

(none yet — owner block, agent does not edit)

### OQ-035 — FR-005 CLI surface and risk tiers (`P2 decision`, non-blocking)

**Raised:** 2026-07-06 (MS-3 implementation) **Owner:** owner **Needed by:** MS-4 (before verify/resume harden the surface) **Spec:** §21 OQ-035; touches FR-005, G-002

**The unresolved decision:** how are the git/external preservation strategies declared on the CLI, what exactly qualifies as a "low-risk single-file operation," and how is an overwrite-clobbered target preserved (G-002)?

**Current assumption (implementation proceeds on this per Appendix B):** `--backup-dir` activates tool backups; `--preserved-by git|external` declares an external byte-preserving strategy (an operator assertion, not verified); `--allow-no-backup` is the low-risk opt-in, valid only for single-action plans. An action counts as a content rewrite iff any of its operations is not a rename; rename-only runs under the skip/fail collision policy need no preservation strategy (the manifest alone suffices). A run that would overwrite an existing target requires an active strategy, and tool backups additionally copy the clobbered target (manifest schema 1.1 `overwritten_*` fields).

#### Agent notes

- Landed via the adversarial plan audit that produced the MS-3 implementation plan; the gate (`tests/test_gate.py`) enforces the refusal set mechanically.

#### My Comments

(none yet — owner block, agent does not edit)

### OQ-036 — run-level lock location and mechanism (`P2 decision`, non-blocking)

**Raised:** 2026-07-06 (MS-3 implementation) **Owner:** owner **Needed by:** MS-4 **Spec:** §21 OQ-036; touches OQ-027, AW-005

**The unresolved decision:** the spec mandates the run-level lock this heading resolves for but not its home or mechanism (the lock requirement itself was settled as OQ-027).

**Current assumption (implementation proceeds on this per Appendix B):** `flock(2)` on a lock file under `$XDG_STATE_HOME/docmend/locks/` (default `~/.local/state/…`), named by the sha256 hash of the resolved source root, `.lock` suffixed — kernel-owned, so a crashed holder can never leave a stale lock and no stale-detection/unlink races exist. Holder JSON (`run_id`/`pid`/`command`/`started_at`) is written only to populate the refusal message; a live holder refuses with exit 3 (AW-005). `plan` warns and proceeds if the state directory is uncreatable (stays read-only-safe); `apply`/`restore` refuse. Single-machine semantics (A-003-adjacent: local POSIX filesystem per A-001).

#### Agent notes

- Landed via the adversarial plan audit that produced the MS-3 implementation plan.

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
