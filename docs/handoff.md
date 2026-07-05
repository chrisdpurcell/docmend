# **Handoff** for llm-agent use

## 2026-07-05

### Project Standards adoption

Adopted four [Project Standards](https://github.com/L3DigitalNet/project-standards) (v4.0.0): **Python Tooling SSOT**, **Markdown Tooling**, **Project Specification**, **ADR**. Deliberately did **not** adopt Markdown Frontmatter — recorded as [`docs/decisions/adr-0001-no-markdown-frontmatter-standard.md`](decisions/adr-0001-no-markdown-frontmatter-standard.md) (docmend's Pandoc-flavored product frontmatter + the Pandoc spec draft conflict with the canonical schema).

- CLI `project-standards adopt python-tooling markdown-tooling adr` wrote: `.python-version`, `.editorconfig`, `.markdownlint.json`, `.prettierrc.json`, `.vscode/{tasks,extensions}.json`, `.github/workflows/{check,lint-markdown}.yml`, `scripts/check.py`, `docs/decisions/adr.template.md`.
- Hand-authored: `pyproject.toml` (`[project]` + the reported tool sections), a minimal `src/docmend/` + `tests/test_smoke.py` scaffold (makes the gate provable, not empty), `.markdownlint-cli2.jsonc` (local runner: `gitignore:true` so `.venv` is skipped), `.project-standards.yml`.
- Merged (not clobbered): Python + Markdown + Spec + ADR agent blocks appended to `AGENTS.md` (demoted to `##`/`###` for single-H1 / MD025); Python + Markdown formatter blocks merged into `.vscode/settings.json` (kept existing `folder-color` key). `CLAUDE.md` unchanged — its `@AGENTS.md` thin pointer already resolves everything.
- Added a `## Project Standards` orientation section to `AGENTS.md`: a standard→config→run-it map, the convenience runners (`scripts/check.py`, VS Code tasks), what CI actually enforces (Python gate + markdownlint; **Prettier is local-only**), the standard-owned "don't hand-edit" rule, the ADR-0001 deviation, the product-vs-repo-doc frontmatter distinction, and ordered steps to turn spec CI on later. Internal anchor links validated by markdownlint MD051.
- **Verified green:** full Python gate (ruff format/check, basedpyright strict, pytest, coverage 100% ≥85, pip-audit) and both Markdown checks (prettier `--check`, markdownlint `0 errors`). `uv.lock` created.

**Open follow-up (deferred, by design):**

- **Migrate `docs/specs/docmend-spec-draft.md` to a conformant project-spec** (`project-standards spec new/upgrade`, choose a tier). It is currently excluded in `.project-standards.yml`; `spec validate` fails closed on the resulting empty corpus, so `.github/workflows/validate-specs.yml` was intentionally **not** added yet. Migrating the draft → drop the exclude → add the validate-specs workflow, in that order.
- Add a `[project.scripts]` console entry point when the CLI module lands.

### Also landed in this commit (earlier same-day work)

- `docs/research/`: consolidated the two storage reports into `self-hosted-corpus-storage-options.md` (Git forges + non-Git corpus storage); removed the superseded `self-hosted-git-options.md`.
- `docs/specs/docmend-spec-draft.md` frontmatter/metadata guidance was refreshed from official Pandoc + CommonMark docs in a prior commit (already on `main`).
