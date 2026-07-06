# Conventions

Long-lived pattern library for docmend — "how we do things here." Check this before adding a persistent pattern; it must not conflict with any standard adopted from [project-standards](https://github.com/L3DigitalNet/project-standards). Numbered entries are the durable record; `AGENTS.md` only indexes them.

## Quick Reference

| # | Applies when | Rule |
| --- | --- | --- |
| 1 | Touching Python code | Fix pass, then the full verification gate, before claiming done |
| 2 | Touching Markdown/JSON/JSONC/YAML | Fix pass, then the check contract |
| 3 | Authoring/extending the spec | Use the `project-standards spec` CLI; never hand-edit structure |
| 4 | Editor regenerates the spec's ToC | Run `scripts/fix_spec_toc.py` before `spec validate` |
| 5 | Recording an architectural/deviation decision | Author an ADR from the template |
| 6 | Adding any file, fixture, comment, or doc | Never real library documents, paths, or personal content |
| 7 | Touching frontmatter anywhere | Product frontmatter vs. repo-doc frontmatter are different systems — never conflate |
| 8 | Considering an edit to a standard-owned file | Don't, without a documented ADR exception |
| 9 | Citing a settled decision in the spec | Use `OQ-`/`D-`/ADR stems only — never `RQ-` |

## 1. Python Tooling SSOT

**Applies when:** changing any Python code under `src/`, `tests/`, or `scripts/`.

**Rule:** `uv` owns dependency resolution/lockfile/venv/execution; Ruff owns formatting, linting, and import sort; BasedPyright (strict) is the type authority; pytest + coverage cover tests; pip-audit covers dependency vulnerabilities. Do not introduce Black, isort, Flake8, or Pylint. Use `uv add` / `uv add --dev` / `uv remove` for dependency changes; never hand-edit `uv.lock`.

**Code:**

```bash
# fix pass (run first)
uv run ruff format .
uv run ruff check . --fix

# verification gate (must all pass before claiming done)
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run coverage run -m pytest
uv run coverage report
uv run pip-audit
```

**Why:** one locked, agent-designated tool per concern (format/lint/type/test/audit) keeps the gate deterministic and avoids competing formatters producing conflicting diffs.

**Sources:** `pyproject.toml` tool tables; Python Tooling SSOT Standard (project-standards).

**Related:** #2, #7.

## 2. Markdown Tooling Standard

**Applies when:** changing Markdown, JSON, JSONC, or YAML.

**Rule:** Prettier owns physical formatting for every file type it supports here; markdownlint owns Markdown structure only. Don't hand-format against Prettier's output; don't disable a markdownlint rule to silence a warning — fix the Markdown instead.

**Code:**

```bash
# fix pass
npx prettier --write .
npx markdownlint-cli2 --fix "**/*.md"

# check contract (must both pass before claiming done)
npx prettier --check .
npx markdownlint-cli2 "**/*.md"
```

**Why:** CI enforces markdownlint (`lint-markdown.yml`) but _not_ Prettier — Prettier is a local/pre-commit nicety. A Prettier miss won't fail CI; a markdownlint miss will. Keep both clean anyway.

**Sources:** `.markdownlint.json`, `.markdownlint-cli2.jsonc`, `.prettierrc.json`; Markdown Tooling Standard (project-standards).

**Related:** #1.

## 3. Project Specification Workflow

**Applies when:** authoring or extending `docs/specs/docmend.md` (SPEC-VHHB).

**Rule:** Author and extend the spec with the CLI, never by hand-editing structure (section numbering, omission notes, frontmatter keys, table shapes). Editing prose/table _content_ within the existing structure is normal authoring. The spec's Appendix B (Agent Implementation Contract) binds implementation: Must requirements are mandatory, deviations go in the Deviations Log, and completion claims require the §17.3 traceability matrix filled in.

**Code:**

```bash
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' \
  project-standards spec new docs/specs/<name>.md --profile standard --title '<Title>'
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' \
  project-standards spec validate --config .project-standards.yml
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' \
  project-standards spec lint --strict --config .project-standards.yml
```

**Why:** hand-edited structure drifts from what the CLI's own validators expect; the CLI is the single source of truth for spec shape.

**Sources:** `.project-standards.yml` `spec:` block; `.github/workflows/validate-specs.yml`.

**Related:** #4, #6.

## 4. Spec ToC / `spec validate` Dead-Anchor Gotcha

**Applies when:** an editor auto-generates or refreshes a Table of Contents inside `docs/specs/docmend.md`.

**Rule:** The ToC's root entry — a link to the document's own H1 title — always fails `spec validate`'s `SV-ANCHOR` check, because the validator's anchor scanner only indexes `##`-`####` headings and never H1. Run `uv run python scripts/fix_spec_toc.py` (idempotent) after the editor regenerates the ToC, before validating.

**Code:**

```bash
uv run python scripts/fix_spec_toc.py
```

**Why:** confirmed by reading the validator's source (`_anchor_slugs()` in `project_standards/specs/document.py` matches `^(#{2,4})\s+`) — a structural property of the validator, not a slug-format mismatch (both single- and double-hyphen GitHub slugs for the H1 were tested and both failed identically).

**Sources:** `scripts/fix_spec_toc.py`; `.vscode/tasks.json` task `fix-spec-toc`.

**Related:** #3.

## 5. Architecture Decision Records

**Applies when:** recording a significant/architectural decision, or any deviation from an adopted standard.

**Rule:** Author from `docs/adr/adr.template.md` (MADR shape) under `docs/adr/`. Filenames are `adr-NNNN-short-title.md`; frontmatter `id` embeds the repo name (`adr-NNNN-docmend-short-title`). ADR frontmatter is not CI-validated here (see #8) — keep it consistent by convention.

**Why:** a documented decision record prevents relitigating a rejected alternative and gives future sessions the _why_, not just the _what_.

**Sources:** `docs/adr/`.

**Related:** #8.

## 6. Sensitive Data (Public Repository)

**Applies when:** adding any file, fixture, comment, or doc to this repo.

**Rule:** Never commit real documents from the user's actual library, real local file paths from that library, or any sample corpus containing real personal/identifying content — test fixtures must be synthetic or public-domain. Don't reference the user's private infrastructure (hostnames, credential-store paths, network addresses) anywhere in the repo. External service credentials (if integrated later) come from environment variables only, documented in `.env.example`, never hardcoded.

**Fixture review gate (RQ-032):** a fixture derived from a real-library anomaly may only enter the repo via the anonymization procedure (spec §17.2: capture facts, re-synthesize the causal mechanism through unrelated synthetic filler, verify the identical code path fires) — and the committing reviewer must explicitly confirm: _"zero bytes of this fixture are traceable to the original file."_ Never scrub/mask real bytes; always re-synthesize.

**Why:** this repo is public and its entire purpose is operating on a large _personal_ document library.

**Sources:** repo sensitive-data policy; spec OQ-032 / `docs/research/synthetic-corpus-generation.md`.

**Related:** none.

## 9. Decision References in the Spec

**Applies when:** writing or editing `docs/specs/docmend.md` text that cites a settled decision.

**Rule:** the spec cites decisions by `OQ-###` (its own §21 register), `D-###`, or ADR stem (`adr-00NN-…`) — never `RQ-###`. More generally, `validate-specs@v4` reads **any** uppercase `PREFIX-<digits>` token in the spec body as a spec-ID reference and fails it (`SV-ID-UNDECLARED`, plus `SV-ID-FMT` on a non-3-digit width) unless the prefix is declared in Appendix A. So three classes must stay out of the spec body: `RQ-###` (use its shared-number `OQ-###`); a bare uppercase `ADR-0010` (use the lowercase `adr-00NN-…` stem, which is not tokenised); and a `GAP-07` cross-reference to `gap-analysis.md` (lowercase it to `gap-07`, or reword). `RQ-###` lives only in `docs/resolved-questions.md` and the ADRs; `OQ-N` and `RQ-N` share the number `N` by convention.

**Why:** the 2026-07-05 consistency audit had to remap 76 `RQ-` references after `validate-specs` failed on them; the 2026-07-06 audit additionally found bare `ADR-NNNN` and `GAP-NN` tokens tripping the same `SV-ID-*` checks (and the recurring `SV-ANCHOR` ToC-root dead anchor, fixed by [`scripts/fix_spec_toc.py`](../../scripts/fix_spec_toc.py) — see #4). `scripts/check_traceability.py` (CI, `traceability.yml`) cross-checks the §21 OQ register against the RQ/open-question records, so the OQ/RQ pairing is machine-enforced; `validate-specs.yml` gates the ID-token rules. Run `project-standards spec validate` locally after editing the spec — the lowercase-`adr-`/`gap-` forms are the only cross-doc-reference styles it accepts.

**Sources:** `validate-specs@v4`; 2026-07-05 and 2026-07-06 consistency-audit sessions; `scripts/check_traceability.py`; `scripts/fix_spec_toc.py`.

**Related:** #3, #5.

## 7. Product Frontmatter vs. Repo-Doc Frontmatter

**Applies when:** touching any YAML frontmatter, anywhere in this repo.

**Rule:** These are two unrelated systems — never conflate them.

- **Product frontmatter** — the Pandoc-flavored YAML docmend _emits into every converted document_ (title, author, provenance, generated fields). Governed by its own schema in `docs/specs/docmend.md` (§9 Data Model / DR-005) — never validated or reformatted by this repo's markdownlint/Prettier config.
- **Repo-doc frontmatter** — YAML on `docs/**` and ADRs. Deliberately unvalidated (see #8 / ADR-0001) — keep it consistent by convention.

**Why:** the repo's Markdown Frontmatter Standard was deliberately not adopted (ADR-0001) because its schema conflicts with docmend's Pandoc-oriented output contract; conflating the two would either break product output or misapply repo-doc rules to it.

**Sources:** `docs/adr/adr-0001-no-markdown-frontmatter-standard.md`; spec §9 / DR-005.

**Related:** #8.

## 8. Standard-Owned Files

**Applies when:** considering an edit to `pyproject.toml` (tool tables), `.python-version`, `.github/workflows/*.yml`, `.vscode/`, `scripts/check.py`, `.markdownlint.json`, `.markdownlint-cli2.jsonc`, `.prettierrc.json`, `.editorconfig`, or `.project-standards.yml` structure.

**Rule:** Don't hand-edit these to bypass a check, except with a documented ADR exception. `.project-standards.yml`'s `spec:` `include`/`exclude` globs are the one adoption-config surface edited normally. Adding a new, additive, non-bypassing entry (e.g. a new VS Code task) is not itself a check-bypass, but is still worth a deliberate decision rather than a silent edit.

**Dependabot action-version bumps are an accepted exception (adr-0017).** Dependabot's `github-actions` ecosystem scans _every_ workflow file — including standard-owned ones like `check.yml` — and cannot exclude a single file. A version bump it authors (e.g. `actions/checkout@v6→v7`) is not a hand-edit and not a check-bypass; it keeps action pins current, which is the posture the standards endorse. Merge such PRs normally. The only side effect is possible churn if a future `project-standards` sync resets the pin — accepted as low-cost. This exception is scoped to **action-version bumps**; any _other_ change to a standard-owned workflow still needs an ADR exception.

**Why:** these files are the mechanism CI enforcement depends on; unreviewed edits here can silently weaken the gate.

**Sources:** four adopted Project Standards (python-tooling, markdown-tooling, project-spec, adr), pinned to `@v4`; adr-0017 (Dependabot exception).

**Related:** #1, #2, #3, #5.
