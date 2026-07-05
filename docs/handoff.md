# **Handoff** for llm-agent use

## 2026-07-05 (later session)

### Spec migrated to a conformant project-spec — spec CI is on

Migrated `docs/specs/docmend-spec-draft.md` → **`docs/specs/docmend.md`** (`SPEC-VHHB`, **full** profile, `status: draft`), completing the project-spec adoption:

- Scaffolded with `project-standards spec new --profile full` (never hand-author structure), then filled every canonical section from the draft. Full profile chosen per the standard's own tailoring rules (durable data; bulk automated decisions the owner must trust) and the user's request for the full template.
- **Nothing dropped:** every `<!-- Fill this in -->` placeholder in the old draft became an `OQ-` row in §21 (OQ-001–OQ-010; OQ-001/004/005 are blocking for MS-1/MS-3). Later-phase work became `WH-` rows in §2.3. Draft deleted; content lives in git history.
- Sections retained-with-reason rather than deleted: §5 Stakeholders (solo), §11 UI/API (headless CLI), C.1/C.2/C.5 (offline, no scheduler, no RDBMS). C.3 (dedup ladder) and C.4 (decision provenance) are filled — they map to WH-005 and the planning layer.
- **Gotcha for future editing:** the validator's ID extractor flags the literal token `ADR-0001` (`SV-ID-UNDECLARED`: prefix `ADR-` not in Appendix A). Reference ADRs as "ADR 0001" or by lowercase filename inside a spec.
- Wiring: exclude removed from `.project-standards.yml`; `.github/workflows/validate-specs.yml` added (`@v4` on both `uses:` and `standards-ref`, `strict-lint: false`). `spec validate --config` and `spec lint --strict` both pass locally.
- `AGENTS.md` updated: spec path/ID references, CI-enforcement list (now three workflows), and the Project Specifications section rewritten from "deferred" to "adopted + working rules". `TODO.md`: standards-adoption task moved to Completed.

**Open follow-ups:** resolve blocking OQ-001/OQ-004/OQ-005 before their milestones; spec is `status: draft` — promote to `review`/`approved` when the owner signs off; add a `[project.scripts]` console entry point when the CLI module lands (carried over).

## 2026-07-05

### Project Standards adoption

Adopted four [Project Standards](https://github.com/L3DigitalNet/project-standards) (v4.0.0): **Python Tooling SSOT**, **Markdown Tooling**, **Project Specification**, **ADR**. Deliberately did **not** adopt Markdown Frontmatter — recorded as [`docs/decisions/adr-0001-no-markdown-frontmatter-standard.md`](decisions/adr-0001-no-markdown-frontmatter-standard.md) (docmend's Pandoc-flavored product frontmatter + the Pandoc spec draft conflict with the canonical schema).

- CLI `project-standards adopt python-tooling markdown-tooling adr` wrote: `.python-version`, `.editorconfig`, `.markdownlint.json`, `.prettierrc.json`, `.vscode/{tasks,extensions}.json`, `.github/workflows/{check,lint-markdown}.yml`, `scripts/check.py`, `docs/decisions/adr.template.md`.
- Hand-authored: `pyproject.toml` (`[project]` + the reported tool sections), a minimal `src/docmend/` + `tests/test_smoke.py` scaffold (makes the gate provable, not empty), `.markdownlint-cli2.jsonc` (local runner: `gitignore:true` so `.venv` is skipped), `.project-standards.yml`.
- Merged (not clobbered): Python + Markdown + Spec + ADR agent blocks appended to `AGENTS.md` (demoted to `##`/`###` for single-H1 / MD025); Python + Markdown formatter blocks merged into `.vscode/settings.json` (kept existing `folder-color` key). `CLAUDE.md` unchanged — its `@AGENTS.md` thin pointer already resolves everything.
- Added a `## Project Standards` orientation section to `AGENTS.md`: a standard→config→run-it map, the convenience runners (`scripts/check.py`, VS Code tasks), what CI actually enforces (Python gate + markdownlint; **Prettier is local-only**), the standard-owned "don't hand-edit" rule, the ADR-0001 deviation, the product-vs-repo-doc frontmatter distinction, and ordered steps to turn spec CI on later. Internal anchor links validated by markdownlint MD051.
- **Verified green:** full Python gate (ruff format/check, basedpyright strict, pytest, coverage 100% ≥85, pip-audit) and both Markdown checks (prettier `--check`, markdownlint `0 errors`). `uv.lock` created.

**Open follow-up (deferred, by design):**

- ~~Migrate `docs/specs/docmend-spec-draft.md` to a conformant project-spec~~ — **done in the later 2026-07-05 session** (see above).
- Add a `[project.scripts]` console entry point when the CLI module lands.

### Also landed in this commit (earlier same-day work)

- `docs/research/`: consolidated the two storage reports into `self-hosted-corpus-storage-options.md` (Git forges + non-Git corpus storage); removed the superseded `self-hosted-git-options.md`.
- `docs/specs/docmend-spec-draft.md` frontmatter/metadata guidance was refreshed from official Pandoc + CommonMark docs in a prior commit (already on `main`).

### Research conversion session

- Converted `/home/chris/Downloads/managing-pandoc-markdown-and-strict-yaml-frontmatter.pdf` into `docs/research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md`. The Markdown version is ASCII/LF normalized, restores headings/tables, removes PDF page artifacts, and preserves all 45 citation instances as Markdown links plus a citation-instance map.
- Verified the new research file with a citation-number presence check, `markdownlint-cli2 --no-globs`, `npx prettier --check`, and `git diff --check`.
