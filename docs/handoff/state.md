# State

**Last updated:** 2026-07-06

## Current

- **Spec at v0.11; decision backlog fully settled (OQ-001..033); ADR set 0001–0016 complete** (2026-07-06; commits `30325fe`..`04f4450`). Tool-first reframing (OQ-024 → ADR-0014: G-006 scale-flexibility, NFR-006 single-file floor, WH-008 one-shot deferral). Gap register (`docs/gap-analysis.md`, 71 gaps) fully dispositioned: ~38 already resolved; Batch A mechanical sync (spec v0.9); Batch B owner decisions OQ-025..033 (v0.10: HTML mechanical-only, UTF-16/32 BOM-before-NUL, parent single-writer + run lock, FR-019 watchdog, config precedence, EC-005 non-whitespace invariant, leading-tab semantics, two-corpus + anonymization → ADR-0015, purity enforcement). ADR-0016 bundles OQ-025/030/031; amendments on ADRs 0002/0007/0009/0010/0013. Deferred: RQ-023 review-artifact ADR (blocked on WH-002/WH-005).
- **Traceability drift gate live** (`62e536a`): `scripts/check_traceability.py` + 8 tests + `.github/workflows/traceability.yml` cross-check §7↔§17.3, §21 OQ↔RQ records, and progress-claims↔tests. Run it after touching the spec or question files.
- **Third consistency/drift audit complete (2026-07-06, spec rev 0.12).** Multi-agent detect→adversarial-verify→classify (2 workflow passes, ~67 agents) + `validate-specs` ground-truthing. 11 stage-1a + 4 stage-1b findings resolved; **all four spec gates now green** (`validate-specs`, `spec lint`, markdownlint CI contract, `check_traceability`) — the spec was previously `validate-specs`-RED (bare `ADR-NNNN`/`GAP-NN`/`RQ-` ID tokens + `SV-ANCHOR`). Two owner decisions: G-002/§20 qualified for the FR-005 low-risk no-backup opt-in (reconciling ADR-0014); gap-32 hard-link policy adopted (EC-011, DR-001 alias group, OQ-004, adr-0005 amendment). Zero RQ downgrades — resolved-questions all agreed with spec/ADRs. New conventions #9 clause: only Appendix-A prefixes may appear as uppercase `PREFIX-NNN` in the spec body; use lowercase `adr-`/`gap-` for cross-refs. Committed and pushed to `origin/main` (2026-07-06). Pre-existing prettier warning on `resolved-questions.md` left as-is (not CI-gated, predates this pass).
- Pre-implementation: no conversion pipeline or CLI yet — scaffold + smoke test only. Next: MS-0 (spec §19); at MS-0 add dev deps `allpairspy`/`import-linter`/`faker` and the purity contract + fixture (OQ-033).

## Active Blockers

- **None.** Zero open OQs. Non-blocking MS-2 calibration checkpoint on the 20-byte encoding floor (RQ-022).

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, draft, v0.11)
- Decisions: `docs/resolved-questions.md` (RQ-001..033) · ADRs: `docs/adr/` (0001–0016 + backlog)
