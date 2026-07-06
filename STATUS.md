# Project Status

This is the human-facing completion summary for docmend. Agents maintain it so the project builder can re-orient quickly.

## Completed

- Adopted four Project Standards (python-tooling, markdown-tooling, project-spec, adr) — CI gates green; Markdown Frontmatter Standard deliberately not adopted (ADR-0001).
- Spec `docs/specs/docmend.md` (SPEC-VHHB, `full` profile) is implementation-ready: entire decision backlog settled (RQ-001..033, zero blocking), ADR set 0001–0017 accepted, 71-gap register fully dispositioned, traceability drift-check CI gate live.
- Branch/CI/CD workflow live (ADR-0017): protected `main`, merge-commit PRs from long-lived `dev`, five required checks + dependency-review license gate.
- **MS-0 Foundation implemented** (2026-07-06, PR #5): `docmend` CLI entry point with the IR-005 global flags, strict §18.2 TOML config loading, structlog logging framework with the run-ID convention, NFR-005 purity enforcement wired before any transform exists, §16 license record.
- **MS-1 Core workflow implemented** (2026-07-06, PR #6): `docmend scan PATH` produces the schema-validated DR-001 inventory — provably read-only, include/exclude filters, single-pass classification (BOM/UTF-8 facts, newline census, hard-link and symlink records), single-file PATH first-class. The four OQ-004 artifact JSON Schemas are pinned in `src/docmend/schemas/` (adr-0005). 125 tests, 97% branch coverage.

## Current State

- The tool can inventory but not modify: `scan` is live; `plan`/`apply`/`verify`/`restore` land in MS-2..MS-4 per the binding §19 milestone ladder.
- Spec is `status: draft`, revision 0.14. One open question: OQ-034 (default artifact/log location — non-blocking, implementation proceeding on the `./.docmend/` assumption; owner sign-off wanted by MS-3).
- Next milestone: **MS-2 Domain logic** — planning layer (FR-002/FR-015/DR-002), pure transforms (FR-007..FR-009, adds `charset-normalizer`), the weird-document corpus, and the RQ-022 encoding-floor calibration checkpoint.

## Recent Changes

- [2026-07-06] MS-1: scan command + discovery layer + pinned artifact schemas; new OQ-034; dependency-review purl exemption for rfc3987-syntax (false GPL detection, verified MIT).
- [2026-07-06] MS-0: CLI entry point, strict config, logging framework, purity enforcement; dependency licenses recorded.
- [2026-07-06] Branch/CI/CD workflow adopted (ADR-0017); third consistency audit brought all four spec gates green (spec v0.12).
- [2026-07-05..06] Spec authored to implementation-ready: decision backlog RQ-001..033, ADRs 0001–0016, gap register dispositioned (detail: `docs/handoff/sessions/2026-07.md`).

## Notes For The Builder

- Read `docs/specs/docmend.md` (Appendix B) before proposing any implementation — it is a binding Agent Implementation Contract, not just background.
- Milestone order (spec §19) is binding: do not build a later milestone on an unproven earlier one.
- Run `scripts/check_traceability.py` after any edit to the spec or the question files; CI enforces it.
- All changes go `dev` → PR → `main`; direct pushes to `dev` do not run CI — run the local gate first (see README).
