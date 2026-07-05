# TODO

This is the human-facing work queue for docmend. The project builder owns the first section; agents maintain the second section from handoff docs and session work.

## User Tracked Tasks

Add personal tasks, reminders, or priorities here. Agents do not rewrite this section unless asked.

## Agent Tracked Tasks

Agents summarize outstanding work from `docs/handoff/state.md`, `docs/handoff/architecture.md`, `docs/handoff/specs-plans.md`, bug records, plans, and session notes here.

- [ ] Resolve blocking spec open questions before their milestones (see `docs/open-questions.md`, ranked in `docs/gap-analysis.md`): OQ-001, OQ-004, OQ-018 before MS-1; OQ-015 before MS-2; OQ-005 and OQ-012 before the MS-3 write path.
- [ ] Triage the non-blocking gap-analysis open questions (OQ-016 concurrency, OQ-017 logging, OQ-019 Hypothesis, OQ-020 generic-tool scope) plus the High/Medium doc-fixes and spec-changes catalogued in `docs/gap-analysis.md`.
- [ ] Send the 4 queued ChatGPT Deep-Research prompts in `docs/deep-research-queue.md` when the residual encoding-floor, free-threading-timeline, backup-throughput, and review-artifact-policy questions need deciding.
- [ ] Add a `[project.scripts]` console entry point when the CLI module lands.

## Maintenance Notes

- Keep open work here; move completed outcomes to `STATUS.md`.
- Preserve the separation between user-owned and agent-tracked tasks — do not complete a `## User Tracked Tasks` item unless asked.
- Do not store secrets, private hostnames, or credential values in this file.
