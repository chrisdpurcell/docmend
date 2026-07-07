# State

**Last updated:** 2026-07-07

## Current

- **MS-4 Unattended operation — COMPLETE (spec rev 0.18, merged in PR #10).**
  - ✅ **Resume (FR-013, adr-0006):** `docmend apply --resume-run-id ID | --resume-manifest FILE` (both repeatable for multiply-interrupted runs) reconciles the plan against prior manifest records before execution — recorded-applied + live hash matches → `already-applied` skip (new internal skip reason, free-string schema, no bump; **not** an exit-1 finding so unattended re-invocation converges); changed/missing output → failed ERR-002; unrecorded → normal execution behind the FR-003 guard. Wrong-tree manifest refuses exit 2 via the 1.2 `source_root` cross-check. Kill-and-resume e2e: corpus + union-of-manifests identical to an uninterrupted control run.
  - ✅ **Idempotency (FR-017):** all three duplicate shapes tested (`tests/test_idempotency.py`) — blind double-apply (zero mutations, stale-hash skips, exit 1 by design), double-apply under `--resume-run-id` (exit 0), re-plan over converted output (zero actions).
  - ✅ **NFR-006 journey closed:** scan → plan → apply `--write` (low-risk opt-in) → verify over one file, default config (`test_restore_drill.py::test_single_file_journey…`).
  - The MS-3 final-review inputs are all cleared (mode-reset fix + lock rekey landed earlier); verify's report/count reconciliation stays deferred with the frontmatter feature (FR-016, MS-5).
- **v1.0.0 RELEASED** — PR #11 merged, signed tag `v1.0.0`, GitHub Release published with sdist + wheel (release workflow verified live; its one warning fixed in PR #12). All of §19 that is achievable without the real library is done: 100k scale test (NFR-001, 477 MiB peak, opt-in `DOCMEND_SCALE=1`), FR-019 SIGALRM watchdog (`timeout` skip reasons; inventory/plan schemas 1.2; DEV-002 records the in-process realization), NFR-003 log-content test, frontmatter contract (rev 0.19), §18.7 docs (README + two runbooks), release workflow (`release.yml`: tag → `uv build` → smoke → GitHub Release). §17.3 matrix fully Complete; 598 tests + scale test, 97% coverage. **Owner actions with the released tool:** §18.4 staged real-library rollout; weird-corpus expansion from real scan findings; DEV-001/DEV-002 sign-off (tracked in TODO.md).
- **v1.0.1 RELEASED (issue #15 partial-undo trap; PR #16, tag `v1.0.1`, Release published with sdist+wheel):** apply warns when a write run has content rewrites and no tool backups; restore states renames-only capability up front (manifest-derived — only pure renames replay without backups; a rename_and_rewrite record skips whole); no-backup skips name the recovery path; `--journal-originals` deferred as WH-009. Issue #15 closed with a suggestion-by-suggestion summary. Spec revs 0.21 (sign-off) / 0.22 (fix).
- **Owner sign-off received (2026-07-07):** OQ-034..036 resolved as implemented (RQ-034..036); DEV-001/DEV-002 approved; spec DoD (§17.1) + hardening (§13.6) checklists ticked. **The decision backlog is empty.**
- **Workflow:** `dev`→PR→`main`; no CI on direct `dev` pushes — run the local gate (README) first. Milestone ladder §19 binding.

## Active Blockers

- **None.** Open, non-blocking: OQ-034..036; DEV-001 pending owner review.

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, draft, v0.20)
- Decisions: `docs/resolved-questions.md` (RQ-001..033) · open: `docs/open-questions.md` (OQ-034..036) · ADRs: `docs/adr/` (0001–0017 + backlog)
