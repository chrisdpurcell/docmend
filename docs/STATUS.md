# Project Status

## Current snapshot

- docmend v1.0.2 is released with the complete scan, plan, apply, restore, resume, and verify pipeline.
- The approved SPEC-VHHB revision 0.27 and ADRs 0001-0021 govern post-v1 changes (adr-0006 superseded by adr-0019); the decision backlog is empty.
- The current baseline is 651 tests plus an opt-in 100k-file scale test, with 97% coverage.
- The repository workflow is `dev` to pull request to protected `main`; releases are signed `vX.Y.Z` tags with sdist and wheel artifacts. `main` stays at v1.0.2 until the v2.0.0 safety-core release ships all four remediation plans.
- The 2026-07-10 comprehensive review confirmed rollout-blocking defects (DMR-01..09); the safety core is recontracted in spec rev 0.26/0.27 with ADRs 0019-0021 from a six-round-reviewed design, targeting v2.0.0 with a clean manifest/backup format break.
- Safety-core Plan A (DMR-01/02: output ledger, write-once run/action/role backup keys, artifact destination guard with the `.docmend/` carve-out, randomized `O_EXCL` staging, in-lock report finalization) is implemented on `dev` — final whole-branch review "ready to merge", full gate green.
- The sweep findings were independently re-verified post-Plan-A against HEAD ([verification](codex-reviews/2026-07-10-2251-all-findings-verification.md)): DMR-01/02 confirmed closed, DMR-03..09 confirmed still open with unchanged scope, no Plan A regressions, Plans B–D decomposition unchanged.
- Plans B (manifest 2.0 + lifecycle reducer), C (commit-boundary identity + WriteSafetyContext), and D (verify redesign) remain; the opt-in scale test stays stale until manifest 2.0 lands (DMR-08 scope).
- The owner's staged real-library write rollout stays paused behind the remediation (spec section 18.4 precondition).
- Agent Handoff v1 provides one shared repo-local SessionStart runtime for the dual Claude/Codex profile.
