# Project Status

This is the human-facing completion summary for docmend. Agents maintain it so the project builder can re-orient quickly.

## Completed

- Adopted four Project Standards (python-tooling, markdown-tooling, project-spec, adr) — CI gates green; Markdown Frontmatter Standard deliberately not adopted (ADR-0001).
- Migrated the spec to a conformant `full`-profile project-spec at `docs/specs/docmend.md` (SPEC-VHHB); spec CI is on.
- Adopted the agent-handoff-v3 session-state layout: `docs/handoff/*`, root `STATUS.md`/`TODO.md`, Claude + Codex SessionStart hooks.
- **Settled the entire spec decision backlog** — 33 open questions resolved (RQ-001..033 in `docs/resolved-questions.md`), zero blocking; includes the 2026-07-06 tool-first reframing (the product is the scale-flexible tool; the >100k-file library pipeline is the impetus use case).
- **Wrote the full ADR set 0001–0016** (`docs/adr/`, all accepted) with a scored candidate backlog and recorded skips; only the deferred RQ-023 review-artifact ADR remains (blocked on WH-002/WH-005).
- **Fully dispositioned the 71-gap register** (`docs/gap-analysis.md`): ~38 already resolved by prior decisions, the rest closed via a mechanical spec sync plus nine owner decisions (OQ-025..033); residuals are milestone-gated with recorded triggers.
- **Built the traceability drift-check CI gate** (`scripts/check_traceability.py` + `traceability.yml`): mechanically prevents spec-registry drift (§7↔§17.3, §21↔question records).

## Current State

- Pre-implementation: only a build/tooling scaffold (`pyproject.toml`, CI, `src/docmend/` + `tests/` skeleton), a version smoke test, and the traceability-gate tests exist. No conversion pipeline or CLI entry point yet.
- Spec is `status: draft`, `full` profile, revision 0.11 — **implementation-ready**: zero open questions, all decisions ADR- or spec-canonical. The only decision checkpoint ahead is the non-blocking MS-2 encoding-floor calibration (RQ-022).
- Next milestone: MS-0 Foundation (spec §19) — includes adding the approved dev deps (`allpairspy`, `import-linter`, `faker`) and wiring the NFR-005 purity enforcement (OQ-033).

## Recent Changes

- [2026-07-06] Second ADR review pass: authored ADR-0014 (tool-first scope), ADR-0015 (test-corpus + anonymization), ADR-0016 (mechanical-transform boundary); amended ADRs 0002/0007/0013; recorded skips in the backlog.
- [2026-07-06] Built the traceability drift-check gate (script + 8 tests + additive CI workflow).
- [2026-07-06] Gap-register strategy executed: Batch A synced spec prose to settled ADRs (spec v0.9); Batch B settled the nine decision-bearing gaps as OQ-025..033 (spec v0.10).
- [2026-07-06] Owner reframed spec §1 tool-first; scale-flexibility bound as G-006/NFR-006 via OQ-024 (amending OQ-020/ADR-0010); one-shot command deferred as WH-008 (spec v0.8).
- [2026-07-06] Added `repo-hygiene.md` as a periodic maintenance checklist and linked it from `AGENTS.md`.
- [2026-07-05] Spec migrated to the project-spec standard; decision backlog created and fully settled (RQ-001..023); ADRs 0001–0013 written; spec↔ADR↔RQ consistency enforced (detail: `docs/handoff/sessions/2026-07.md`).

## Notes For The Builder

- Read `docs/specs/docmend.md` (Appendix B) before proposing any implementation — it is a binding Agent Implementation Contract, not just background.
- Milestone order (spec §19) is binding: do not build a later milestone on an unproven earlier one.
- Run `scripts/check_traceability.py` after any edit to the spec or the question files; CI enforces it.
