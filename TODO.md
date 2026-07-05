# TODO

## User Tracked Tasks

- [ ] Assess ADR candidates
- [ ]

## Agent Tracked Tasks

Agents summarize outstanding work from `docs/handoff/state.md`, `docs/handoff/architecture.md`, `docs/handoff/specs-plans.md`, bug records, plans, and session notes here.

- [ ] Resolve the remaining blocking spec open questions before their milestones (see `docs/open-questions.md`, ranked in `docs/gap-analysis.md`): OQ-018 before MS-1; OQ-015 before MS-2; OQ-012 before the MS-3 write path. (OQ-001/OQ-004/OQ-005 resolved 2026-07-05 → RQ-001/RQ-004/RQ-005.)
- [ ] Triage the non-blocking open questions (OQ-016 concurrency, OQ-017 logging, OQ-019 Hypothesis, OQ-023 review-artifact policy) plus the **reframed OQ-007** (user-defined, secure, per-corpus vocabularies — owner added new requirements) and the High/Medium doc-fixes catalogued in `docs/gap-analysis.md`. (OQ-020 resolved → RQ-010.)
- [ ] **ADR candidates** (per owner, feeds the user's "Assess ADR candidates" task): **RQ-004** (artifact JSON Schemas) and **RQ-005** (apply safety gate) are strong ADR material; route **OQ-012** (in-place mutation) for ADR consideration when it settles.
- [x] Reconcile the 4 Deep-Research reports and follow up on the owner's OQ-001..014 comments (2026-07-05): 10 questions settled → RQ-001..010 in `docs/resolved-questions.md`, OQ-007 reframed, binding spec prose reworded, §21 statuses set to Resolved. Details in `STATUS.md`.
- [ ] Add a `[project.scripts]` console entry point when the CLI module lands.

## Maintenance Notes

- Keep open work here; move completed outcomes to `STATUS.md`.
- Preserve the separation between user-owned and agent-tracked tasks — do not complete a `## User Tracked Tasks` item unless asked.
- Do not store secrets, private hostnames, or credential values in this file.
