# State

**Last updated:** 2026-07-06

## Current

- **MS-2 Domain logic landed (dev, pending PR; spec rev 0.15).** `docmend plan` is live: fact-gate ladder (filters, hard-link, oversize, encoding gates), content pass (decode checks, EC-005 shrink-invariant guard, FR-011 collisions, C.4 provenance, UUIDv7 action IDs). Pure transforms (FR-007-FR-009) behind the adr-0016 file-class dispatch, NFR-005-pure. `charset-normalizer` legacy rung populates DR-001 at scan (adr-0009). Weird-document corpus + regression harness started (§17.2), incl. the 37-fixture encoding-floor boundary matrix. RQ-022 MS-2 calibration checkpoint resolved: floor stays 20 (full tabulation: `sessions/2026-07.md`; R-001 Western-misdetection residual pinned as a risk-marker fixture). Plan schema pre-implementation v1.0 amendment (`changed-since-scan`). 334 tests, 97% coverage. History: `STATUS.md` + `sessions/2026-07.md`; module map: `architecture.md`.
- **Next: MS-3 User and admin experience** — writer layer (atomic writes, backups, manifest, collision policy, safety gate; FR-003-FR-006/FR-011/NFR-002), `apply` with dry-run default and readable reports (FR-004/FR-018/IR-005), restore-from-manifest drill (§18.6). **OQ-034 still open** (artifact/log default location — non-blocking, owner sign-off wanted by MS-3).
- **Workflow reminder:** all changes go `dev`→PR→`main`; no CI on direct `dev` pushes — run the local gate (README) before opening the PR. Milestone ladder §19 is binding (Appendix B).

## Active Blockers

- **None.** Open, non-blocking: OQ-034 (artifact/log default location — owner decision wanted by MS-3).

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, draft, v0.15)
- Decisions: `docs/resolved-questions.md` (RQ-001..033) · open: `docs/open-questions.md` (OQ-034) · ADRs: `docs/adr/` (0001–0017 + backlog)
