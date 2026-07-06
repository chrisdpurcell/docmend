# TODO

**Maintenance Instructions:** See [repo-hygiene.md](docs/repo-hygiene.md#todomd)

## User Tracked Tasks

- [ ] Add branch strategy, branch protections, release process, and CI/CD pipeline based on those used by the `hw-radar` project/repo.

## Agent Tracked Tasks

<instruction> Agents summarize outstanding work from `docs/handoff/state.md`, `docs/handoff/architecture.md`, `docs/handoff/specs-plans.md`, bug records, plans, and session notes here. The purpose is to provide convenience and transparency to the human user. </instruction>

- [ ] **MS-2 calibration checkpoint (carried from RQ-022, not a reopen):** during MS-2, run one project-internal validation of the 20-byte non-ASCII floor against docmend's own short-file distribution; may tune the number within the ~8–20 band without reopening OQ-015.
- [ ] Work the remaining High/Medium doc-fixes catalogued in `docs/gap-analysis.md`: reconcile the §8.2.2 "Converted library" diagram to in-place (GAP-70), rewrite the §9 null-heavy frontmatter example to the RQ-014 minimal shape and author `schemas/frontmatter.schema.json` (GAP-56), and specify config-vs-`--write` precedence (GAP-16).
- [ ] Add a `[project.scripts]` console entry point when the CLI module lands.

## Completed Tasks

<instruction> Agents should move completed tasks from both the user and agent sections to here. This space is not for agent tracking or handoff purposes; it is a user convenience and these will be deleted by the user once reviewed. </instruction>

## Usage Notes

- This document is not a substitute for `STATUS.md`; the agent(s) should not use it to track ongoing work. This document is intended for human user convenience and transparency.
- Preserve the separation between user-owned and agent-tracked tasks — do not complete a `## User Tracked Tasks` item unless asked.
- Do not store secrets, private hostnames, or credential values in this file.
