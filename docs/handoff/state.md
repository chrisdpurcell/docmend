# Handoff State

## Current focus

- Safety-core remediation per the approved design (`docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md`, spec rev 0.26/0.27, ADRs 0019-0021): Plans A (DMR-01/02) and B (manifest 2.0, DMR-03/04) are implemented and pushed on `dev`. NEXT: write Plan C (commit boundary — adr-0020 descriptor identity, action-time overwrite invariant, WriteSafetyContext + preview/write split, DMR-06/07) via superpowers:writing-plans, then the owner's Codex plan-review loop (Plan B took 3 rounds; commit before each round), then implement. Plan D (verify redesign, DMR-05) follows, consuming Plan B's reducer/chain/`not-attempted` partition.
- Plan B facts a successor needs: manifest 2.0 is a CLEAN BREAK (no 1.x read path; `CLEAN_BREAK_MESSAGE` in `writer/manifest.py`); shared wire types live in dependency-neutral `docmend/lineage.py` (its docstring is a binding import contract — review CR-001); per-set lifecycle is PROVISIONAL with strict chain-scope closure (design amended for CR-NEW-002); identity capture is `os.stat`-based by design until Plan C's CommitBoundary; the crash-state adjudication table lives in `writer/adjudicate.py` and is consumed by both resume and restore.
- The 2026-07-10 review-findings verification is complete (`docs/codex-reviews/2026-07-10-2251-all-findings-verification.md`, all 189 raw findings classified); the user task is closed in `docs/TODO.md`.
- The real-library write rollout stays paused behind the remediation (spec §18.4 precondition); `main` stays at v1.0.2 until the v2.0.0 release PR carries all four plans plus sub-projects 2-4.
- Keep post-v1 behavior change-controlled through the approved spec and ADR process; run the local gate before pushing `dev`.

## Active incidents

- None.
