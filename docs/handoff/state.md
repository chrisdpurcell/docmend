# Handoff State

## Current focus

- FIRST: the URGENT user task in `docs/TODO.md` — verify `docs/codex-reviews/2026-07-10-2034-all-review-findings.md` via receiving-code-review; much has been remediated since that snapshot, so judge blast radius against the landed work.
- Safety-core remediation underway per the approved design (`docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md`, spec rev 0.26/0.27, ADRs 0019-0021): Plan A (DMR-01/02) implemented and pushed; Plan B (manifest 2.0, DMR-03/04) is next, then C (commit boundary) and D (verify).
- The real-library write rollout stays paused behind the remediation (spec §18.4 precondition); `main` stays at v1.0.2 until the v2.0.0 release PR carries all four plans.
- Keep post-v1 behavior change-controlled through the approved spec and ADR process; run the local gate before pushing `dev`.

## Active incidents

- None.
