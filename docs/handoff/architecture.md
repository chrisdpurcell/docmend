# Architecture

## Component Graph

docmend is a single-process, layered pipeline (spec §8.1): Discovery -> Planning -> Transform -> Writer -> Verification, each stage living under `src/docmend/` once built. Only the Writer layer touches the filesystem for mutation; Transform is pure functions (text in, text out). Full diagrams: spec §8.2.

## Current Shape

Pre-implementation: `pyproject.toml`, CI (`.github/workflows/check.yml` + the additive `traceability.yml` drift gate), a `src/docmend/` + `tests/` skeleton, a version smoke test, and `scripts/check_traceability.py` with its regression tests. No scan/plan/apply/verify commands exist yet — don't assume a runnable `docmend` CLI is present.

## Standing Backlog

- Milestone order is binding (spec §19, Appendix B.1): MS-0 Foundation -> MS-1 Core workflow -> MS-2 Domain logic -> MS-3 CLI experience -> MS-4 Unattended operation -> MS-5 Production readiness. Do not build a later milestone on an unproven earlier one.
- All spec open questions are settled (OQ-001..033, zero blocking; `docs/resolved-questions.md`, ADRs 0001–0016). The only decision checkpoint ahead is the non-blocking MS-2 encoding-floor calibration (RQ-022).
- Deferred capabilities (spec §2.3, WH-001-WH-008): semantic renaming, spelling/grammar repair, document reconstruction, HTML structural conversion, deduplication, frontmatter enrichment, search integration, and the low-ceremony one-shot command — none are v1 scope.
