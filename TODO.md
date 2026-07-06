# TODO

**Maintenance Instructions:** See [repo-hygiene.md](docs/repo-hygiene.md#todomd)

## User Tracked Tasks

- [ ] Add branch strategy, branch protections, release process, and CI/CD pipeline based on those used by the `hw-radar` project/repo.

## Agent Tracked Tasks

<instruction> Agents summarize outstanding work from `docs/handoff/state.md`, `docs/handoff/architecture.md`, `docs/handoff/specs-plans.md`, bug records, plans, and session notes here. The purpose is to provide convenience and transparency to the human user. </instruction>

- [ ] **MS-2 calibration checkpoint (carried from RQ-022, not a reopen):** during MS-2, run one project-internal validation of the 20-byte non-ASCII floor against docmend's own short-file distribution; may tune the number within the ~8–20 band without reopening OQ-015.
- [ ] Author `schemas/frontmatter.schema.json` and rewrite the §9 null-heavy example to the RQ-014 minimal shape when frontmatter schema work lands (GAP-56; gated by OQ-009/OQ-013).
- [ ] Add a `[project.scripts]` console entry point when the CLI module lands.

## Completed Tasks

<instruction> Agents should move completed tasks from both the user and agent sections to here. This space is not for agent tracking or handoff purposes; it is a user convenience and these will be deleted by the user once reviewed. </instruction>

- [x] **Traceability drift-check gate built (2026-07-06, GAP-53 automation half):** `scripts/check_traceability.py` (PEP 723, stdlib-only) cross-checks §7↔§17.3, §21 OQ↔RQ/open records, and §17.3 progress claims↔test mentions; 8 regression tests in `tests/test_check_traceability.py`; wired into CI as the additive `.github/workflows/traceability.yml` (check.yml is a standard-owned twin, left untouched per conventions #8).
- [x] **Gap-register outstanding-items strategy (2026-07-06):** triaged all 71 gaps against current state (~38 already resolved by RQ-015..024/ADRs). **Batch A** (spec rev 0.9): synced spec to settled ADR decisions + mechanical fixes (GAP-12/13/14/15/17/18/21/25/27/28/36/38/39/48/51/53-rows/66). **Batch B** (spec rev 0.10): owner settled the nine decision-bearing gaps as OQ-025..033 → RQ-025..033 (HTML mechanical-only include, UTF-16/32 BOM-before-NUL, parent single-writer + run lock, watchdog + size guard, config precedence, EC-005 invariant + ratio, leading-tab semantics, two-corpus + anonymization, import-linter purity); ADR-0007/0009 amendment notes; conventions #6 fixture review gate. GAP-70 was already fixed; GAP-62/64 accepted as-is; GAP-40/41/45/59/60/71 + GAP-20/54 remain milestone-gated with recorded triggers.

## Usage Notes

- This document is not a substitute for `STATUS.md`; the agent(s) should not use it to track ongoing work. This document is intended for human user convenience and transparency.
- Preserve the separation between user-owned and agent-tracked tasks — do not complete a `## User Tracked Tasks` item unless asked.
- Do not store secrets, private hostnames, or credential values in this file.
