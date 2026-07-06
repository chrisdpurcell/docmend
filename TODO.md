# TODO

## User Tracked Tasks

- [ ] Assess ADR candidates
- [ ] Add branch strategy, branch protections, release process, and CI/CD pipeline based on the used by the `hw-radar` project/repo.

## Agent Tracked Tasks

Agents summarize outstanding work from `docs/handoff/state.md`, `docs/handoff/architecture.md`, `docs/handoff/specs-plans.md`, bug records, plans, and session notes here.

- [x] Settle the last two open questions (2026-07-05): **OQ-015 → RQ-022** (encoding detector + single fixed 20-byte non-ASCII floor; family-aware table + ratio signal deferred behind the RQ-010 seam) and **OQ-023 → RQ-023** (review-artifact exposure = public-repo/tool boundary not operator screen; metadata-only artifacts, external tools render text). Spec reconciled to v0.6 (FR-007/§18.2/A-003/FR-015/AW-003/R-001/§8.6/§17.2/§17.3 for RQ-022; §2.2/§11/§13.4/§13.5 for RQ-023); §21 both Resolved. **OQ backlog now fully settled (RQ-001..023); zero blocking OQs.**
- [ ] **MS-2 calibration checkpoint (carried from RQ-022, not a reopen):** during MS-2, run one project-internal validation of the 20-byte non-ASCII floor against docmend's own short-file distribution; may tune the number within the ~8–20 band without reopening OQ-015.
- [ ] Work the remaining High/Medium doc-fixes catalogued in `docs/gap-analysis.md`: reconcile the §8.2.2 "Converted library" diagram to in-place (GAP-70), rewrite the §9 null-heavy frontmatter example to the RQ-014 minimal shape and author `schemas/frontmatter.schema.json` (GAP-56), and specify config-vs-`--write` precedence (GAP-16).
- [ ] **ADR candidates** (per owner, feeds the user's "Assess ADR candidates" task): **RQ-004** (artifact JSON Schemas), **RQ-005** (apply safety gate), and now **RQ-013** (in-place mutation — the fundamental output model, flagged ⚑ in `resolved-questions.md`) are strong ADR material. The six library approvals (RQ-016..021) are recorded in spec §8.6 and are lighter-weight ADR candidates if the owner wants them formalized.
- [x] Follow up on the owner's OQ-007..022 comment batch (2026-07-05): 11 questions settled → RQ-011..021 in `docs/resolved-questions.md`; §21 statuses Resolved; spec §8.6 rewritten (Runtime vs Dev/Test); blocking OQs 3 → 1. Details in `STATUS.md`.
- [x] Reconcile the 4 Deep-Research reports and follow up on the owner's OQ-001..014 comments (2026-07-05): 10 questions settled → RQ-001..010 in `docs/resolved-questions.md`, OQ-007 reframed, binding spec prose reworded, §21 statuses set to Resolved. Details in `STATUS.md`.
- [ ] Add a `[project.scripts]` console entry point when the CLI module lands.

## Completed Tasks

<instruction> Agents should move completed tasks from both the user and agent sections to here. This space is not for agent tracking or handoff purposes; it is a user convenience and these will be deleted by the user once reviewed. </instruction>

- [x] **Spec/ADR consistency audit (2026-07-05, spec v0.7):** multi-agent workflow (dimensional finders → adversarial verify → classify) found 8 distinct stale-prose defects, all reconciled to already-settled decisions — **zero RQ downgrades, zero escalations.** Fixes: OQ-001 six-not-seven transforms; `--write` added to §10.1/IR-003 (RQ-015); IR-007 → JSON+NDJSON manifest (RQ-004); "output root" removed from §8.5/§13.2 for in-place (RQ-013); `docmend.id` example → UUIDv7 (RQ-002); §9 stale OQ-013 note (RQ-014); `parallel.*` §18.2 surface with sequential-until-profiled defaults + IR-006 (RQ-016). ADR-0001 internally consistent and consistent with the spec. Note: overlaps the GAP-56 doc-fix below (§9 frontmatter) — reconcile when working those.

## Maintenance Notes

- Keep open work here; move completed outcomes to `STATUS.md`.
- Preserve the separation between user-owned and agent-tracked tasks — do not complete a `## User Tracked Tasks` item unless asked.
- Do not store secrets, private hostnames, or credential values in this file.
