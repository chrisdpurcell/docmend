# State

**Last updated:** 2026-07-07

## Current

- **Released and idle: v1.0.1** (tag + GitHub Release with sdist/wheel; v1.0.0 same day). All milestones MS-0..MS-5 shipped; spec **approved** (rev 0.23, change-controlled); decision backlog **empty** (OQ-034..036 resolved, DEV-001/DEV-002 approved); GitHub issues clear (#15 partial-undo trap fixed in v1.0.1, closed).
- **Next work is the owner's:** §18.4 staged real-library rollout + weird-corpus expansion (TODO.md). Post-v1 agent work: bug fixes / deferred capabilities (WH-001..009) as prioritized — new behavior needs a spec revision row (change-controlled) and an ADR when architectural.
- 604 tests + opt-in 100k scale test (`DOCMEND_SCALE=1`), 97% coverage; full gate + spec validate + traceability green.
- **Workflow:** `dev`→PR→`main` (merge needs `--admin` + resolved Copilot threads; if the PR shows BEHIND, merge main into dev first); no CI on direct `dev` pushes — run the local gate (README) first. Release = signed `vX.Y.Z` tag on main → `release.yml`.

## Active Blockers

- **None.**

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, **approved**, v0.23 — change-controlled)
- Decisions: `docs/resolved-questions.md` (all settled) · ADRs: `docs/adr/` (0001–0017) · session detail: `sessions/2026-07.md`
