# TODO

**Maintenance Instructions:** See [repo-hygiene.md](docs/repo-hygiene.md#todomd)

## User Tracked Tasks

- [ ] Add branch strategy, branch protections, release process, and CI/CD pipeline based on those used by the `hw-radar` project/repo.

## Agent Tracked Tasks

<instruction> Agents summarize outstanding work from `docs/handoff/state.md`, `docs/handoff/architecture.md`, `docs/handoff/specs-plans.md`, bug records, plans, and session notes here. The purpose is to provide convenience and transparency to the human user. </instruction>

- [ ] **MS-2 calibration checkpoint (carried from RQ-022, not a reopen):** during MS-2, run one project-internal validation of the 20-byte non-ASCII floor against docmend's own short-file distribution; may tune the number within the ~8–20 band without reopening OQ-015.
- [ ] **Gap-register Batch B (owner decisions → OQ-025+):** settle the remaining decision-bearing gaps from `docs/gap-analysis.md` — GAP-07 (HTML missing from default `paths.include`), GAP-44 (UTF-16/32 BOM vs NUL-byte heuristic ordering), GAP-16 (config merge/precedence semantics beyond "flags override file"), GAP-46 (EC-005 shrink-ratio value + config knob), GAP-47 (`normalize_tabs` semantics), GAP-23 (who writes shared artifacts under parallelism — single-writer rule for ADR-0007), GAP-52 (import-linter purity enforcement, dev-dep approval), GAP-63 (per-file watchdog/timeout), GAP-49 (synthetic-corpus generation/anonymization strategy). Batch A mechanical sync landed 2026-07-06 (spec rev 0.9); GAP-70 already fixed in spec §8.2.2; GAP-62/GAP-64 accepted as-is (template category menu / metric granularity).
- [ ] Author `schemas/frontmatter.schema.json` and rewrite the §9 null-heavy example to the RQ-014 minimal shape when frontmatter schema work lands (GAP-56; gated by OQ-009/OQ-013).
- [ ] Add a `[project.scripts]` console entry point when the CLI module lands.

## Completed Tasks

<instruction> Agents should move completed tasks from both the user and agent sections to here. This space is not for agent tracking or handoff purposes; it is a user convenience and these will be deleted by the user once reviewed. </instruction>

## Usage Notes

- This document is not a substitute for `STATUS.md`; the agent(s) should not use it to track ongoing work. This document is intended for human user convenience and transparency.
- Preserve the separation between user-owned and agent-tracked tasks — do not complete a `## User Tracked Tasks` item unless asked.
- Do not store secrets, private hostnames, or credential values in this file.
