# State

**Last updated:** 2026-07-07

## Current

- **v1.0.1 released; alignment hardening landed on `dev`** (6 commits pushed, not yet PR'd to `main`): cross-repo review with `doc-proc-scripts` fixed both P0s — same-run rename-collision escape under `overwrite` (FR-011) and the `rename_and_rewrite` kill window (manifest 1.2→**1.3** write-ahead intent records + resume reconciliation, adr-0006 amended) — plus excluded-dir pruning at scan, release-workflow SHA pin, v1.0.1 doc drift. Spec rev **0.24**; CHANGELOG has an Unreleased section.
- **Pending owner:** review rev 0.24 (FR-011/DR-004 amendments) and accept **adr-0018** (repository boundary, proposed); sibling `doc-proc-scripts` mirrors it, then both root `ALIGNMENT_HANDOFF.md` files get deleted. Also still the owner's: §18.4 staged real-library rollout (TODO.md).
- 617 tests + opt-in 100k scale test (`DOCMEND_SCALE=1`), 97% coverage; full gate + spec validate + traceability + markdownlint green.
- **Workflow:** `dev`→PR→`main` (merge needs `--admin` + resolved Copilot threads; if the PR shows BEHIND, merge main into dev first); no CI on direct `dev` pushes — run the local gate (README) first. Release = signed `vX.Y.Z` tag on main → `release.yml`.

## Active Blockers

- **None.**

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, **approved**, rev 0.24 — change-controlled)
- Alignment: `ALIGNMENT_HANDOFF.md` (temporary) · ADRs: `docs/adr/` (0001–0018; 0018 proposed) · session detail: `sessions/2026-07.md`
