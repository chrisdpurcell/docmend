# Repo Hygiene

Use this checklist for periodic cleanup passes and before declaring a broad repo-maintenance task complete. Keep the work evidence-based: inspect the live files and commands first, then update the checked items that actually changed.

## Public Repository Safety

- [ ] Confirm new docs, fixtures, comments, and examples contain no real library documents, real personal paths, private hostnames, credential values, or identifying content.
- [ ] Keep credential documentation to secret-source references, environment variable names, and lookup locations only.
- [ ] Prefer synthetic or public-domain fixture content for future tests and examples.

## Standards And Tooling

- [ ] Run the Markdown fix pass after Markdown, JSON, JSONC, or YAML edits: `npx prettier --write .` and `npx markdownlint-cli2 --fix "**/*.md"`.
- [ ] Run the Markdown check contract before claiming Markdown/doc work complete: `npx prettier --check .` and `npx markdownlint-cli2 "**/*.md"`.
- [ ] Run the Python verification gate after Python edits: `uv run ruff format --check .`, `uv run ruff check .`, `uv run basedpyright`, `uv run coverage run -m pytest`, `uv run coverage report`, and `uv run pip-audit`.
- [ ] Validate the project spec after spec edits: `uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec validate --config .project-standards.yml`.
- [ ] Run `uv run python scripts/fix_spec_toc.py` before spec validation if an editor regenerated the spec table of contents.

## Documentation State

- [ ] Keep `AGENTS.md` a slim index and move durable patterns to `docs/handoff/conventions.md`.
- [ ] Keep `TODO.md` split between user-tracked tasks, agent-tracked tasks, and completed user-visible work.
- [ ] Keep `STATUS.md` current rather than historical; prune lines that are superseded by later session notes.
- [ ] Confirm `docs/open-questions.md`, `docs/resolved-questions.md`, and the spec's question register agree after any decision-backlog change.
- [ ] Record architectural decisions or adopted-standard deviations as ADRs under `docs/adr/`.

## Repository Shape

- [ ] Confirm obsolete scaffold paths are removed after migrations, especially renamed docs directories and moved ADR files.
- [ ] Confirm CI workflow names and local commands match the adopted Project Standards.
- [ ] Keep generated build, cache, virtualenv, and coverage artifacts out of the tracked tree.
- [ ] Confirm newly added docs are linked from the nearest appropriate index or agent instruction surface.

## Release And Collaboration Readiness

- [ ] Document branch strategy, branch protections, release process, and CI/CD expectations once the project adopts them.
- [ ] Confirm package metadata, console entry points, and version smoke tests still match the implementation stage.
- [ ] Check `git status --short` before and after maintenance so unrelated local work stays untouched.

## Document Pruning

The following may be deleted:

- [ ] Completed plans from `docs/plans/` and `docs/superpowers/plans/`. Plans for sub-phases of a larger project should be retained until the overall project is complete.
- [ ] Fully addressed reviews from `docs/codex-reviews/`.

## Document Specific Maintenance

### `TODO.md`

- Move completed tasks from the user-tracked and agent-tracked sections to the completed section.

### `deep-research/` and `docs/deep-research/`
