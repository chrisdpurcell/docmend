# State

**Last updated:** 2026-07-06

## Current

- **Spec at v0.11; decision backlog fully settled (OQ-001..033); ADR set 0001–0016 complete** (2026-07-06; commits `30325fe`..`04f4450`). Tool-first reframing (OQ-024 → ADR-0014: G-006 scale-flexibility, NFR-006 single-file floor, WH-008 one-shot deferral). Gap register (`docs/gap-analysis.md`, 71 gaps) fully dispositioned: ~38 already resolved; Batch A mechanical sync (spec v0.9); Batch B owner decisions OQ-025..033 (v0.10: HTML mechanical-only, UTF-16/32 BOM-before-NUL, parent single-writer + run lock, FR-019 watchdog, config precedence, EC-005 non-whitespace invariant, leading-tab semantics, two-corpus + anonymization → ADR-0015, purity enforcement). ADR-0016 bundles OQ-025/030/031; amendments on ADRs 0002/0007/0009/0010/0013. Deferred: RQ-023 review-artifact ADR (blocked on WH-002/WH-005).
- **Traceability drift gate live** (`62e536a`): `scripts/check_traceability.py` + 8 tests + `.github/workflows/traceability.yml` cross-check §7↔§17.3, §21 OQ↔RQ records, and progress-claims↔tests. Run it after touching the spec or question files.
- Pre-implementation: no conversion pipeline or CLI yet — scaffold + smoke test only. Next: MS-0 (spec §19); at MS-0 add dev deps `allpairspy`/`import-linter`/`faker` and the purity contract + fixture (OQ-033).

## Active Blockers

- **None.** Zero open OQs. Non-blocking MS-2 calibration checkpoint on the 20-byte encoding floor (RQ-022).

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, draft, v0.11)
- Decisions: `docs/resolved-questions.md` (RQ-001..033) · ADRs: `docs/adr/` (0001–0016 + backlog)
