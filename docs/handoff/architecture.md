# Architecture

## Component Graph

docmend is a single-process, layered pipeline (spec §8.1): Discovery -> Planning -> Transform -> Writer -> Verification, each stage living under `src/docmend/` once built. Only the Writer layer touches the filesystem for mutation; Transform is pure functions (text in, text out). Full diagrams: spec §8.2.

## Current Shape

Through MS-1 (2026-07-06). `src/docmend/`: `cli.py` (typer shell: IR-005 global flags + the `scan` command; artifacts/log default into `./.docmend/`, OQ-034 assumption), `config.py` (§18.2 strict pydantic models), `observability.py` (structlog via stdlib handlers; run-ID convention), `discovery.py` (read-only walk + single-pass chunked classifier; pathspec `GitIgnoreSpecPattern` filters), `inventory.py` (DR-001 internal models), `artifacts.py` (schema registry + cached Draft 2020-12 validators with format assertion + atomic artifact IO), `schemas/` (the four hand-authored artifact JSON Schemas — the adr-0005 durable contract, shipped inside the wheel), and empty `transform/` + `writer/` packages anchoring the NFR-005 purity contracts. Commands `plan`/`apply`/`verify`/`restore` do not exist yet.

## Standing Backlog

- Milestone order is binding (spec §19, Appendix B.1): MS-0 Foundation -> MS-1 Core workflow -> MS-2 Domain logic -> MS-3 CLI experience -> MS-4 Unattended operation -> MS-5 Production readiness. Do not build a later milestone on an unproven earlier one.
- Open decisions: OQ-034 (default artifact/log location — non-blocking, proceeding on the `.docmend/` assumption; owner sign-off wanted by MS-3) and the non-blocking MS-2 encoding-floor calibration (RQ-022). Everything else is settled (OQ-001..033; `docs/resolved-questions.md`, ADRs 0001–0017).
- MS-2 note: the seeded recipe→bytes corpus generator currently lives inside `tests/test_discovery.py`; promote it to a shared module when the weird-document fixture work needs it (adr-0015 expects the generator to be a lasting component).
- Deferred capabilities (spec §2.3, WH-001-WH-008): semantic renaming, spelling/grammar repair, document reconstruction, HTML structural conversion, deduplication, frontmatter enrichment, search integration, and the low-ceremony one-shot command — none are v1 scope.
