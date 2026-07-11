# Project Status

## Current snapshot

- docmend v1.0.2 is released with the complete scan, plan, apply, restore, resume, and verify pipeline.
- The approved SPEC-VHHB revision 0.27 and ADRs 0001-0021 govern post-v1 changes (adr-0006 superseded by adr-0019); the decision backlog is empty.
- The current baseline is 651 tests plus an opt-in 100k-file scale test, with 97% coverage.
- The repository workflow is `dev` to pull request to protected `main`; releases are signed `vX.Y.Z` tags with sdist and wheel artifacts. `main` stays at v1.0.2 until the v2.0.0 safety-core release ships all four remediation plans.
- The 2026-07-10 comprehensive review confirmed rollout-blocking defects (DMR-01..09); the safety core is recontracted in spec rev 0.26/0.27 with ADRs 0019-0021 from a six-round-reviewed design, targeting v2.0.0 with a clean manifest/backup format break.
- Safety-core Plan A (DMR-01/02: output ledger, write-once run/action/role backup keys, artifact destination guard with the `.docmend/` carve-out, randomized `O_EXCL` staging, in-lock report finalization) is implemented on `dev` — final whole-branch review "ready to merge", full gate green.
- Safety-core Plan B (DMR-03/04: manifest 2.0 clean break — header/chain/attempt lineage, journal-every-mutation with durable object identities, validated ManifestSet/chain with the full F5 backup trust boundary, one lifecycle reducer + crash-state adjudication shared by resume and restore, report 2.0 partition/lineage, convergent journaled restore, timeout exits) is implemented on `dev` — plan three-round Codex-reviewed before implementation; all 13 tasks landed as green slices, full gate at 97% branch coverage per commit; the opt-in scale test's manifest-shape assertion is updated (DMR-08 escrow — the scale contract itself remains sub-project 2).
- The sweep findings were independently re-verified post-Plan-A against HEAD ([verification](codex-reviews/2026-07-10-2251-all-findings-verification.md)): DMR-01/02 confirmed closed, DMR-03..09 confirmed still open with unchanged scope, no Plan A regressions, Plans B–D decomposition unchanged. DMR-03/04 have since closed with Plan B.
- Plans C (commit-boundary descriptor identity + WriteSafetyContext, adr-0020 — Plan B persists identities via `os.stat`; C binds capture to `O_NOFOLLOW` descriptors and re-checks at each mutation step) and D (verify redesign consuming the Plan B reducer/chain) remain, then sub-projects 2-4.
- The owner's staged real-library write rollout stays paused behind the remediation (spec section 18.4 precondition).
- Agent Handoff v1 provides one shared repo-local SessionStart runtime for the dual Claude/Codex profile.
