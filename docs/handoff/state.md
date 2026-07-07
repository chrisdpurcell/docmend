# State

**Last updated:** 2026-07-07

## Current

- **v1.0.1 released; alignment hardening merged to `main`** (PR #18, `784b3e2`): cross-repo review with `doc-proc-scripts` fixed both P0s — same-run rename-collision escape under `overwrite` (FR-011) and the `rename_and_rewrite` kill window (manifest 1.2→**1.3** write-ahead intent records + resume reconciliation with §13.5 record-path containment, adr-0006 amended) — plus excluded-dir pruning at scan, release-workflow SHA pin, v1.0.1 doc drift. Spec rev **0.24**; **adr-0018 accepted** (owner, 2026-07-07; sibling ADR confirmed); `ALIGNMENT_HANDOFF.md` deleted. CHANGELOG has an Unreleased section — a signed v1.0.2 tag on `main` would ship it (owner's call).
- **Next work is the owner's:** §18.4 staged real-library rollout + weird-corpus expansion (TODO.md).
- 617 tests + opt-in 100k scale test (`DOCMEND_SCALE=1`), 97% coverage; full gate + spec validate + traceability + markdownlint green.
- **Workflow:** `dev`→PR→`main` (merge needs `--admin` + resolved Copilot threads; if the PR shows BEHIND, merge main into dev first); no CI on direct `dev` pushes — run the local gate (README) first. Release = signed `vX.Y.Z` tag on main → `release.yml`.

## Active Blockers

- **None.**

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, **approved**, rev 0.24 — change-controlled)
- Decisions: `docs/resolved-questions.md` (all settled) · ADRs: `docs/adr/` (0001–0018, all accepted) · session detail: `sessions/2026-07.md`
