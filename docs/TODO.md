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

### Autonomous session log — 2026-07-14/17

- [x] Resumed from clean `dev` at `f75e02b`; confirmed `origin/dev` parity and a green baseline gate (1,684 tests, 90% coverage, Ruff/BasedPyright clean, no known dependency vulnerabilities).
- [x] Confirmed the binding host has 3.2 TiB available on Btrfs, 62 GiB RAM, zero active swap, and absent Task 11 workspaces/evidence outputs.
- [x] Resolved the reserved `file-size` evidence-tier gap as an additive schema/model extension that preserves existing scale-evidence 3.0 documents; case records are required only for the file-size tier.
- [x] Implemented the test-first file-size qualification lane as `48d148c`; its adversarial pre-commit review exposed and closed phase-truth, schema-order, watchdog, configured-maximum provenance, setup-fault, and direct-runtime coverage gaps. Final gate: 1,709 passed, 89% coverage.
- [x] Completed the final independent specification/code-quality approval after closing checkpoint, schema/model-parity, real-pipeline, and reference-equivalence findings; final reviews reported zero Critical, Important, or Minor findings.
- [x] Ran, validated, and accepted the file-size matrix for clean candidate `f050e0a`: 12/12 cases passed through 100 MiB with zero child swap and 1,894,080,512-byte maximum stage RSS; accepted evidence SHA-256 is `4db8276907201dc45366c29053e6da574443197defcc1f2969237fb4523d647e`.
- [ ] Run, validate, and accept the installed-wheel one-million-file release qualification from the next clean candidate commit.
- [ ] Synchronize NFR-001 evidence/documentation and complete Task 11 verification and handoff.

- [ ] Finish the remaining v2.0.0 release work identified by the [comprehensive review synthesis](codex-reviews/2026-07-10-2034-comprehensive-review-synthesis.md) and approved [safety-core design](superpowers/specs/2026-07-10-safety-core-remediation-design.md).
  - [ ] Complete DMR-08 scale qualification through Tasks 11–12 of the approved [million-file implementation plan](superpowers/plans/2026-07-11-million-file-scale-and-resource-contract.md).
    - [x] Add the scheduled/manual installed-wheel 100,000-file diagnostic workflow.
    - [ ] Qualify and accept the one-million-file candidate evidence, including the 12-hour practicality bound.
    - [ ] Close DMR-08 by reconciling review findings, evidence, status, deployment, and handoff documentation.
  - [ ] Complete sub-projects 3–4: DMR-09 release work, remaining observability/documentation, and the v2.0.0 `dev`-to-`main` release PR.

- [ ] Support the owner's first staged real-library rollout under spec section 18.4.

  Blocked on the remaining v2.0.0 release work above. After it closes, scan read-only, review the plan and skip pile, apply a filtered subset, then widen. Expand the weird-document corpus only through the adr-0015 re-synthesis procedure so no real library bytes or paths enter this public repository.
