# State

**Last updated:** 2026-07-06

## Current

- **MS-1 Core workflow landed (PR #6; spec rev 0.14).** `docmend scan` is live: read-only discovery, FR-012 filters, single-pass classification, EC-008/EC-011 link records, ERR-007 skips, single-file PATH. The four OQ-004 artifact schemas are pinned in `src/docmend/schemas/` (adr-0005) — inventory live; plan/report/manifest are v1.0 contracts for MS-2/MS-3. Artifacts/log default to `./.docmend/` per the **OQ-034 assumption (open, non-blocking)**. 125 tests, 97% coverage. History: `STATUS.md` + `sessions/2026-07.md`; module map: `architecture.md`.
- **Next: MS-2 Domain logic** — planning layer (FR-002/FR-015/DR-002), pure transforms (FR-007..FR-009; adds `charset-normalizer`), weird-document corpus start (§17.2), RQ-022 floor calibration. Promote the corpus generator out of `tests/test_discovery.py` when fixtures need it.
- **Workflow reminder:** all changes go `dev`→PR→`main`; no CI on direct `dev` pushes — run the local gate (README) before opening the PR. Milestone ladder §19 is binding (Appendix B).

## Active Blockers

- **None.** Open, non-blocking: OQ-034 (artifact/log default location — owner decision wanted by MS-3); RQ-022 MS-2 encoding-floor calibration checkpoint.

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, draft, v0.14)
- Decisions: `docs/resolved-questions.md` (RQ-001..033) · open: `docs/open-questions.md` (OQ-034) · ADRs: `docs/adr/` (0001–0017 + backlog)
