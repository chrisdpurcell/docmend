# TODO

## User Tracked Tasks

- [ ] Assess ADR candidates
- [ ]

## Agent Tracked Tasks

Agents summarize outstanding work from `docs/handoff/state.md`, `docs/handoff/architecture.md`, `docs/handoff/specs-plans.md`, bug records, plans, and session notes here.

- [ ] Resolve the **one** remaining blocking spec open question: **OQ-015** (encoding detector / non-ASCII floor) before MS-2 — run one project-internal validation of the 20-byte default against docmend's own short-file distribution, then edit FR-007/§18.2. (OQ-018/OQ-012 resolved 2026-07-05 → RQ-018/RQ-013.)
- [ ] Triage the last non-blocking open question **OQ-023** (deferred review-artifact policy — WH-002/WH-005) and work the High/Medium doc-fixes catalogued in `docs/gap-analysis.md`. Newly actionable now that the OQ-012/013/014 decisions landed: reconcile the §8.2.2 "Converted library" diagram to in-place (GAP-70), rewrite the §9 null-heavy frontmatter example to the RQ-014 minimal shape and author `schemas/frontmatter.schema.json` (GAP-56), and specify config-vs-`--write` precedence (GAP-16). (OQ-007/011/016/017/019/021/022 resolved → RQ-011..021.)
- [ ] **ADR candidates** (per owner, feeds the user's "Assess ADR candidates" task): **RQ-004** (artifact JSON Schemas), **RQ-005** (apply safety gate), and now **RQ-013** (in-place mutation — the fundamental output model, flagged ⚑ in `resolved-questions.md`) are strong ADR material. The six library approvals (RQ-016..021) are recorded in spec §8.6 and are lighter-weight ADR candidates if the owner wants them formalized.
- [x] Follow up on the owner's OQ-007..022 comment batch (2026-07-05): 11 questions settled → RQ-011..021 in `docs/resolved-questions.md`; §21 statuses Resolved; spec §8.6 rewritten (Runtime vs Dev/Test); blocking OQs 3 → 1. Details in `STATUS.md`.
- [x] Reconcile the 4 Deep-Research reports and follow up on the owner's OQ-001..014 comments (2026-07-05): 10 questions settled → RQ-001..010 in `docs/resolved-questions.md`, OQ-007 reframed, binding spec prose reworded, §21 statuses set to Resolved. Details in `STATUS.md`.
- [ ] Add a `[project.scripts]` console entry point when the CLI module lands.

## Maintenance Notes

- Keep open work here; move completed outcomes to `STATUS.md`.
- Preserve the separation between user-owned and agent-tracked tasks — do not complete a `## User Tracked Tasks` item unless asked.
- Do not store secrets, private hostnames, or credential values in this file.
