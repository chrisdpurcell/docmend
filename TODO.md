# TODO

This is the human-facing work queue for docmend. The project builder owns the first section; agents maintain the second section from handoff docs and session work.

## User Tracked Tasks

Add personal tasks, reminders, or priorities here. Agents do not rewrite this section unless asked.

## Agent Tracked Tasks

Agents summarize outstanding work from `docs/handoff/state.md`, `docs/handoff/architecture.md`, `docs/handoff/specs-plans.md`, bug records, plans, and session notes here.

- [ ] Resolve blocking spec open questions before their milestones: OQ-001 (v1 boundary) and OQ-004 (artifact JSON Schemas) before MS-1; OQ-005 (apply safety gate) before MS-3. See `docs/open-questions.md`.
- [ ] Add a `[project.scripts]` console entry point when the CLI module lands.

## Maintenance Notes

- Keep open work here; move completed outcomes to `STATUS.md`.
- Preserve the separation between user-owned and agent-tracked tasks — do not complete a `## User Tracked Tasks` item unless asked.
- Do not store secrets, private hostnames, or credential values in this file.
