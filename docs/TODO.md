# Project Tasks

<!--
Purpose:
- This document is the user-visible task list and agent-visible project queue.

Instructions for AI agents:
- Do not add tasks to the `## User tasks` section.
- Do add tasks to the `## Agent tasks` section. Include all open work from agent-managed handoff documents.
- Use `- [ ]` to indicate open work and `- [x]` for work completed during the current session.
- Remove completed standalone agent tasks after recording their outcomes in `docs/STATUS.md`.
-->

## User tasks

None.

## Agent tasks

- [ ] Finish the remaining v2.0.0 release work identified by the [comprehensive review synthesis](codex-reviews/2026-07-10-2034-comprehensive-review-synthesis.md) and approved [safety-core design](superpowers/specs/2026-07-10-safety-core-remediation-design.md).
  - [ ] Complete DMR-08 scale qualification through Tasks 10–12 of the approved [million-file implementation plan](superpowers/plans/2026-07-11-million-file-scale-and-resource-contract.md).
    - [ ] Add the scheduled/manual installed-wheel 100,000-file diagnostic workflow.
    - [ ] Qualify and accept the file-size envelope and one-million-file candidate evidence, including the 12-hour practicality bound.
    - [ ] Close DMR-08 by reconciling review findings, evidence, status, deployment, and handoff documentation.
  - [ ] Complete sub-projects 3–4: DMR-09 release work, remaining observability/documentation, and the v2.0.0 `dev`-to-`main` release PR.

- [ ] Support the owner's first staged real-library rollout under spec section 18.4.

  Blocked on the remaining v2.0.0 release work above. After it closes, scan read-only, review the plan and skip pile, apply a filtered subset, then widen. Expand the weird-document corpus only through the adr-0015 re-synthesis procedure so no real library bytes or paths enter this public repository.
