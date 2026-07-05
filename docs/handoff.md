# **Handoff** for llm-agent use

## 2026-07-05 (session 2 — spec migration)

### Spec migrated to a conformant project-spec — spec CI is on

Migrated `docs/specs/docmend-spec-draft.md` → **`docs/specs/docmend.md`** (`SPEC-VHHB`, **full** profile, `status: draft`), completing the project-spec adoption. Committed as `b30b922`.

- Scaffolded with `project-standards spec new --profile full` (never hand-author structure), then filled every canonical section from the draft. Full profile chosen per the standard's own tailoring rules (durable data; bulk automated decisions the owner must trust) and the user's request for the full template.
- **Nothing dropped:** every `<!-- Fill this in -->` placeholder in the old draft became an `OQ-` row in §21 (OQ-001–OQ-010; OQ-001/004/005 are blocking for MS-1/MS-3). Later-phase work became `WH-` rows in §2.3. Draft deleted; content lives in git history.
- Sections retained-with-reason rather than deleted: §5 Stakeholders (solo), §11 UI/API (headless CLI), C.1/C.2/C.5 (offline, no scheduler, no RDBMS). C.3 (dedup ladder) and C.4 (decision provenance) are filled — they map to WH-005 and the planning layer.
- **Gotcha for future spec editing:** the validator's ID extractor flags the literal token `ADR-0001` (`SV-ID-UNDECLARED`: prefix `ADR-` not in Appendix A). Reference ADRs as "ADR 0001" or by lowercase filename inside a spec.
- Wiring: exclude removed from `.project-standards.yml`; `.github/workflows/validate-specs.yml` added (`@v4` on both `uses:` and `standards-ref`, `strict-lint: false`). CI now enforces three workflows: Python gate, markdownlint, spec validation.
- `AGENTS.md` updated: spec path/ID references, CI-enforcement list, and the Project Specifications section rewritten from "deferred" to "adopted + working rules". `TODO.md`: standards-adoption task moved to Completed.

**Session-end verification:** `spec validate --config` ✅ · `spec lint --strict` ✅ · `npx prettier --check .` ✅ · `npx markdownlint-cli2 "**/*.md"` ✅ · full Python gate (`uv run python scripts/check.py`) ✅. Note: `scripts/check.py` refuses bare `python` — invoke via `uv run`.

### Open follow-ups (consolidated)

- **Uncommitted file from an earlier session:** `docs/research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md` (PDF→Markdown conversion, verified clean) sits **untracked** — it was never committed. Flagged to the user twice; awaiting their decision. Do not delete; commit only when asked.
- Resolve blocking open questions before their milestones: OQ-001 (v1 boundary/non-goals) and OQ-004 (artifact JSON Schemas) before MS-1; OQ-005 (exact apply safety-gate checks) before MS-3.
- Spec is `status: draft` — promote to `review`/`approved` (frontmatter + revision row) when the owner signs off.
- Add a `[project.scripts]` console entry point when the CLI module lands.

## 2026-07-05 (session 1 — standards adoption, pruned)

Adopted four [Project Standards](https://github.com/L3DigitalNet/project-standards) (v4.0.0): **Python Tooling SSOT**, **Markdown Tooling**, **Project Specification**, **ADR** — commit `707749e`; full detail in that commit and in `AGENTS.md` §Project Standards. Markdown Frontmatter deliberately **not** adopted — [`docs/decisions/adr-0001-no-markdown-frontmatter-standard.md`](decisions/adr-0001-no-markdown-frontmatter-standard.md). All gates verified green at adoption (Python gate incl. 100% coverage; prettier + markdownlint). Local-runner nuance that persists: `.markdownlint-cli2.jsonc` sets `gitignore:true` so `.venv` is skipped; **Prettier is local-only** (no CI workflow ships for it).
