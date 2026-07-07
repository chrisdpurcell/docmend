# State

**Last updated:** 2026-07-07

## Current

- **Released and idle: v1.0.2** (tag + GitHub Release with sdist/wheel; PRs #18/#19). Ships the cross-repo alignment hardening: same-run rename-collision escape under `overwrite` fixed (FR-011), the `rename_and_rewrite` kill window closed (manifest 1.2→**1.3** write-ahead intent records + §13.5-contained resume reconciliation, adr-0006 amended), excluded-dir pruning at scan, release-workflow SHA pin — plus a two-agent pre-release drift sweep (spec rev **0.25**). **adr-0018 accepted** (owner; sibling `doc-proc-scripts` ADR confirmed); `ALIGNMENT_HANDOFF.md` deleted; decision backlog empty.
- **Next work is the owner's:** §18.4 staged real-library rollout + weird-corpus expansion (TODO.md). Post-v1 agent work: bug fixes / deferred capabilities (WH-001..009) as prioritized — change-controlled (revision row; ADR when architectural).
- 619 tests + opt-in 100k scale test (`DOCMEND_SCALE=1`), 97% coverage; full gate + spec validate + traceability + markdownlint green. Gotcha: a version bump needs `uv lock` after it, or CI's `uv sync --locked` fails.
- **Workflow:** `dev`→PR→`main` (merge needs `--admin` + resolved Copilot threads; if the PR shows BEHIND, merge main into dev first); no CI on direct `dev` pushes — run the local gate (README) first. Release = signed `vX.Y.Z` tag on main → `release.yml`.

## Active Blockers

- **None.**

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, **approved**, rev 0.25 — change-controlled)
- Decisions: `docs/resolved-questions.md` (all settled) · ADRs: `docs/adr/` (0001–0018, all accepted) · session detail: `sessions/2026-07.md`
