# Project Status

This is the human-facing completion summary for docmend. Agents maintain it so the project builder can re-orient quickly.

## Completed

- Adopted four Project Standards (python-tooling, markdown-tooling, project-spec, adr) — both CI gates green; Markdown Frontmatter Standard deliberately not adopted (ADR-0001).
- Migrated the spec to a conformant `full`-profile project-spec at `docs/specs/docmend.md` (SPEC-VHHB); spec CI (`spec validate` + `spec lint --strict`) is on.
- Adopted the agent-handoff-v3 session-state layout: `docs/handoff/*`, root `STATUS.md`/`TODO.md`, Claude + Codex SessionStart hooks.

## Current State

- Pre-implementation: only a build/tooling scaffold (`pyproject.toml`, CI, `src/docmend/` + `tests/` skeleton) and a version smoke test exist. No conversion pipeline or CLI entry point yet.
- Spec is `status: draft`, `full` profile, with three blocking open questions (OQ-001, OQ-004, OQ-005) ahead of MS-1/MS-3.

## Recent Changes

- [2026-07-05] Reviewed `docs/research/` (Pandoc/frontmatter validation, self-hosted corpus storage) against the spec and strengthened several sections (C-006, FR-016/DR-005, OQ-008, OQ-011).
- [2026-07-05] Populated `docs/open-questions.md`/`docs/resolved-questions.md` as the spec's decision backlog.
- [2026-07-05] Adopted the agent-handoff-v3 session-state layout: `docs/handoff.md` retired, `AGENTS.md` slimmed 12,254 -> 1,639 bytes with detail moved to `docs/handoff/conventions.md`, and Claude + Codex SessionStart hooks installed.

## Notes For The Builder

- Read `docs/specs/docmend.md` (Appendix B) before proposing any implementation — it is a binding Agent Implementation Contract, not just background.
- Milestone order (spec §19) is binding: do not build a later milestone on an unproven earlier one.
