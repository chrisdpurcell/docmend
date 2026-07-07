# State

**Last updated:** 2026-07-07

## Current

- **MS-4 Unattended operation — COMPLETE (spec rev 0.18), heading into MS-5.** 559 tests, 97% coverage, full gate + spec validator + traceability green.
  - ✅ **Resume (FR-013, adr-0006):** `docmend apply --resume-run-id ID | --resume-manifest FILE` (both repeatable for multiply-interrupted runs) reconciles the plan against prior manifest records before execution — recorded-applied + live hash matches → `already-applied` skip (new internal skip reason, free-string schema, no bump; **not** an exit-1 finding so unattended re-invocation converges); changed/missing output → failed ERR-002; unrecorded → normal execution behind the FR-003 guard. Wrong-tree manifest refuses exit 2 via the 1.2 `source_root` cross-check. Kill-and-resume e2e: corpus + union-of-manifests identical to an uninterrupted control run.
  - ✅ **Idempotency (FR-017):** all three duplicate shapes tested (`tests/test_idempotency.py`) — blind double-apply (zero mutations, stale-hash skips, exit 1 by design), double-apply under `--resume-run-id` (exit 0), re-plan over converted output (zero actions).
  - ✅ **NFR-006 journey closed:** scan → plan → apply `--write` (low-risk opt-in) → verify over one file, default config (`test_restore_drill.py::test_single_file_journey…`).
  - The MS-3 final-review inputs are all cleared (mode-reset fix + lock rekey landed earlier); verify's report/count reconciliation stays deferred with the frontmatter feature (FR-016, MS-5).
- **MS-5 underway (§19):** ✅ frontmatter contract landed (spec rev 0.19): `schemas/frontmatter.schema.json` 1.0 (adr-0011/RQ-014 shape), `frontmatter.py` ruamel.yaml codec (duplicate-key rejection, timestamp-string preservation), verify validates frontmatter where present + report↔manifest accounting (`--report`/run-ID sidecar) — FR-014 Complete, FR-016 Complete for v1 scope, DR-005 Complete, gap-56 closed. Remaining: 100k seeded scale test + NFR-001 memory bound (subagent worktree in flight); §18.7 docs (README, runbooks); release wiring per adr-0017 (tag → `uv build` → GitHub Release) and v1.0.0. The "first real-library run" (§18.4 staged rollout) and weird-corpus expansion from real scans are **owner actions** post-release.
- **MS-3 merged** (PR #9 → `main` `468dd9f`, 2026-07-07). Detail: `sessions/2026-07.md`.
- **Owner sign-off wanted (non-blocking):** OQ-034 (`.docmend/`), OQ-035 (preservation flags/tiers), OQ-036 (lock location/mechanism — key gap fixed); DEV-001 (MS-2) pending.
- **Workflow:** `dev`→PR→`main`; no CI on direct `dev` pushes — run the local gate (README) first. Milestone ladder §19 binding.

## Active Blockers

- **None.** Open, non-blocking: OQ-034..036; DEV-001 pending owner review.

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, draft, v0.19)
- Decisions: `docs/resolved-questions.md` (RQ-001..033) · open: `docs/open-questions.md` (OQ-034..036) · ADRs: `docs/adr/` (0001–0017 + backlog)
