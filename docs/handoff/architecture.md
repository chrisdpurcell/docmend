# Architecture

## Component Graph

docmend is a single-process, layered pipeline (spec §8.1): Discovery -> Planning -> Transform -> Writer -> Verification, each stage living under `src/docmend/` once built. Only the Writer layer touches the filesystem for mutation; Transform is pure functions (text in, text out). Full diagrams: spec §8.2.

## Current Shape

Pre-implementation: `pyproject.toml`, CI (`.github/workflows/check.yml`), a `src/docmend/` + `tests/` skeleton, and a version smoke test only. No scan/plan/apply/verify commands exist yet — don't assume a runnable `docmend` CLI is present.

## Standing Backlog

- Milestone order is binding (spec §19, Appendix B.1): MS-0 Foundation -> MS-1 Core workflow -> MS-2 Domain logic -> MS-3 CLI experience -> MS-4 Unattended operation -> MS-5 Production readiness. Do not build a later milestone on an unproven earlier one.
- Blocking open questions gate milestone starts: OQ-001 + OQ-004 before MS-1; OQ-005 before MS-3 (`docs/open-questions.md`).
- Deferred capabilities (spec §2.3, WH-001-WH-007): semantic renaming, spelling/grammar repair, document reconstruction, HTML structural conversion, deduplication, frontmatter enrichment, search integration — none are v1 scope.
