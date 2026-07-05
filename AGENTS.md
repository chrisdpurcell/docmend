# Agents

## Project

`docmend` is a Python CLI tool (pre-implementation — only a tooling scaffold and a version smoke test exist; the conversion pipeline and CLI entry point are not built yet) for normalizing, repairing, and converting a large library (>100k files) of legacy `.txt`/`.html` documents into clean, well-structured Markdown.

The full problem statement, design rationale, and requirements live in [`docs/specs/docmend.md`](docs/specs/docmend.md) (SPEC-VHHB, a Full-profile project-spec with stable requirement IDs and a binding Agent Implementation Contract in its Appendix B) — read it before proposing any implementation. Key decisions already locked in there:

- **Output format:** Pandoc-flavored Markdown, CommonMark-ish body, strict YAML frontmatter (title, author, date, tags, source provenance, generated fields like word/chapter count and checksum) validated against a schema.
- **Encoding / line endings:** normalize everything to UTF-8 / LF regardless of source encoding (Latin-1, Windows-1252, mixed ASCII/CR/CRLF/LF).
- **Non-negotiable requirements:** back up or version-control originals before mutating them, support `--dry-run`, make batch processing resumable, and log in detail — the file volume makes manual review of results impossible, so these aren't optional nice-to-haves.

## Status & workflow

- Build tooling now exists: `pyproject.toml`, `.python-version` (3.14), CI (`.github/workflows/check.yml`), and a `src/docmend/` + `tests/` skeleton. No conversion logic or CLI entry point yet — don't assume a runnable `docmend` command is present.
- This repo has adopted four [Project Standards](https://github.com/L3DigitalNet/project-standards) — see the **[Project Standards](#project-standards)** section below for the map, the run-it commands, the one deliberate deviation, and the rules for changing standard-owned files. Follow those contracts; don't invent alternative tooling.
- Task-tracking conventions are defined in [`TODO.md`](TODO.md) — read it before adding or completing tasks. Agent-added and user-added tasks live in separate sections with different completion rules; don't complete a user-added task unless asked.
- Spec decision tracking lives in [`docs/open-questions.md`](docs/open-questions.md) and [`docs/resolved-questions.md`](docs/resolved-questions.md). `open-questions.md` is the formal queue of unresolved `OQ-###` decisions and blockers; `resolved-questions.md` is the companion record for settled `RQ-###` decisions that have not been folded into the spec or an ADR yet.
- `docs/handoff.md` is for session handoff notes, it should be updated at checkpoints during sessions and fully updated at the end of each session. During the end-of-session handoff, the agent should prune old handoff comments to keep the file concise and relevant.

## Handling sensitive data (this repository is public)

`docmend`'s entire purpose is operating on a large personal document library that may contain private or identifying content (old letters, journals, financial records, etc.). Because this repo is public:

- Never commit real documents from the user's actual library, real local file paths from that library, or any sample corpus containing real personal/identifying content. Test fixtures must be synthetic or public-domain text written for the purpose.
- If an external service integration is added later (LLM APIs, OCR, cloud storage), read credentials from environment variables only — never hardcode keys or tokens. Document required variables in a `.env.example`, not a real `.env` (already gitignored).
- Don't reference the user's private infrastructure (internal hostnames, credential-store paths, network addresses) in code, comments, or docs — none of it is relevant to this tool.

---

## Project Standards

This repo is governed by four [Project Standards](https://github.com/L3DigitalNet/project-standards), pinned to the `@v4` major. Each section below is the operational how-to; this is the map.

| Standard | Governs | Config / artifacts (do not hand-edit to bypass a check) | How to run it |
| --- | --- | --- | --- |
| Python Tooling SSOT | Python stack, `src/` layout, CI gate | `pyproject.toml` (tool tables), `.python-version`, `.github/workflows/check.yml`, `.vscode/`, `scripts/check.py` | `python scripts/check.py`, or the [verification gate](#python-verification-gate) |
| Markdown Tooling | Markdown/JSON/YAML lint + format | `.markdownlint.json`, `.markdownlint-cli2.jsonc`, `.prettierrc.json`, `.editorconfig` | the [check contract](#markdown-check-contract) |
| Project Specification | Tiered specs, stable IDs | `.project-standards.yml` (`spec:` block), `.github/workflows/validate-specs.yml` | `project-standards spec …` (see [below](#project-specifications)) |
| ADR | Decision records | `docs/decisions/`, `adr.template.md` | author from the template (see [below](#architecture-decision-records)) |

**Convenience runners (prefer these):** `python scripts/check.py` runs the entire Python gate (format → lint → type → test → coverage → audit) and stops at the first failure. In VS Code, the tasks `check` / `fix` / `test` / `typecheck` / `audit` map to the same commands — they are the standard's designated agent interface, so use them rather than reinventing invocations.

**What CI actually enforces (i.e. what blocks a merge):** the Python gate (`check.yml`), **markdownlint** (`lint-markdown.yml`), and **spec validation** (`validate-specs.yml`). **Prettier is _not_ run in CI** — the formatter half ships no workflow, so `prettier --check` is a local/pre-commit nicety. Keep it clean anyway (it is part of the check contract), but know that a Prettier miss won't fail CI while a markdownlint or Python-gate miss will.

**Changing a standard-owned file** (the middle column above, plus the three CI workflows): don't, except to bypass a check with a **documented [ADR](#architecture-decision-records)**. `.project-standards.yml` is the one adoption-config surface you edit normally (e.g. to adjust the spec `include`/`exclude` globs — see [Project Specifications](#project-specifications)).

**Deliberate deviation — Markdown Frontmatter Standard is NOT adopted** ([ADR-0001](docs/decisions/adr-0001-no-markdown-frontmatter-standard.md)). Do not try to re-adopt it or "fix" the missing frontmatter validator. Consequence: repo-doc and ADR frontmatter are not CI-validated — keep them consistent by convention.

**Two unrelated "frontmatter" concerns — never conflate them:**

- **Product frontmatter** — the Pandoc-flavored YAML docmend _emits into every converted document_ (title, author, provenance, generated fields). This is the tool's core output contract, governed by its own schema in [`docs/specs/docmend.md`](docs/specs/docmend.md) (§9 Data Model / DR-005) — **not** by any repo tooling. Never validate or reformat it with the repo's markdownlint/Prettier config.
- **Repo-doc frontmatter** — YAML on `docs/**` and ADRs. Deliberately unvalidated here (ADR-0001).

## Python Project Agent Instructions

This repository follows the Python Tooling SSOT Standard. Use the existing project structure and tools. Do not replace the tooling stack unless explicitly instructed.

### Python fix pass

When changing Python code, run the fix pass first:

```bash
uv run ruff format .
uv run ruff check . --fix
```

### Python verification gate

Before considering work complete, run the non-mutating verification gate:

```bash
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run coverage run -m pytest
uv run coverage report
uv run pip-audit
```

Do not claim completion if any verification command fails.

### Dependency rules

- Use `uv add <package>` for runtime deps, `uv add --dev <package>` for dev deps.
- Do not manually edit `uv.lock`. Explain any new dependency.

### Typing rules

- All new `src/` code must pass strict BasedPyright. No untyped public functions, no implicit `Any`.
- Avoid `# type: ignore`; if unavoidable, include the exact rule and reason.

### Testing rules

- New behavior requires tests; bug fixes require regression tests. Assert behavior, not implementation.

### Python style rules

- Ruff owns formatting, linting, and import sorting. Do not introduce Black, isort, Flake8, or Pylint.

## Markdown & Structured-Text Tooling

This repository follows the Markdown Tooling Standard. Prettier formats every file type it supports (`md`/`json`/`jsonc`/`yaml` here); markdownlint lints Markdown structure only. Do not introduce a competing formatter or linter.

### Markdown fix pass

When changing Markdown, JSON, JSONC, or YAML, run the fix pass first:

```bash
npx prettier --write .
npx markdownlint-cli2 --fix "**/*.md"
```

### Markdown check contract

Before considering work complete, run the non-mutating check:

```bash
npx prettier --check .
npx markdownlint-cli2 "**/*.md"
```

Do not claim completion if either command fails.

### Markdown rules

- Prettier owns physical formatting. Do not fight its output or hand-format.
- markdownlint owns Markdown structure. Do not disable a rule to silence a warning — fix the Markdown.
- Do not edit `.prettierrc.json` or `.markdownlint.json` to bypass a check without a documented ADR exception.

## Project Specifications

This repository has wired the [Project Specification Standard](https://github.com/L3DigitalNet/project-standards/tree/main/standards/project-spec) (`spec:` block in `.project-standards.yml`). Author and extend specs with the CLI, not by hand-editing structure:

```bash
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' \
  project-standards spec new docs/specs/<name>.md --profile standard --title '<Title>'
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' \
  project-standards spec validate --config .project-standards.yml
```

The standard is **fully adopted**: [`docs/specs/docmend.md`](docs/specs/docmend.md) (SPEC-VHHB, `full` profile) is a conformant project-spec — migrated 2026-07-05 from the pre-standard `docmend-spec-draft.md` (see git history) — and `.github/workflows/validate-specs.yml` runs `spec validate` in CI on every push/PR. `spec lint --strict` also passes; keep it that way even though CI runs lint non-strict.

Rules for working with the spec:

- Never hand-edit spec **structure** (section numbering, omission notes, frontmatter keys, table shapes) — use the CLI (`spec new`, `spec upgrade`, `spec next` for the next free ID). Editing prose and table _content_ within the existing structure is normal authoring.
- If your editor auto-generates/refreshes a Table of Contents in `docs/specs/docmend.md`, its root entry (linking to the document's own H1 title) will always fail `spec validate`'s `SV-ANCHOR` check — the validator's anchor scan only indexes `##`–`####` headings, never H1. After the editor regenerates the ToC, run `uv run python scripts/fix_spec_toc.py` (idempotent — safe to run even if there's nothing to fix) before validating.
- The spec's `<!-- fill in -->` gaps from the old draft were carried forward as `OQ-` rows in §21 — resolve them there (some are blocking for specific milestones), don't reinvent them.
- Use [`docs/open-questions.md`](docs/open-questions.md) as the working decision backlog for open spec questions. When a question is settled, move its substance to [`docs/resolved-questions.md`](docs/resolved-questions.md) or the relevant ADR/spec section, and update any `OQ-###`/`RQ-###` references in the same change.
- Implementation work is bound by the spec's Appendix B (Agent Implementation Contract): Must requirements are mandatory, deviations go in the Deviations Log, and completion claims require the §17.3 traceability matrix.

## Architecture Decision Records

Significant/architectural decisions and any deviation from an adopted standard are recorded as ADRs under `docs/decisions/`, authored from `docs/decisions/adr.template.md` (MADR shape). Filenames are `adr-NNNN-short-title.md`; the frontmatter `id` embeds the repo name (`adr-NNNN-docmend-short-title`). ADR frontmatter is **not** CI-validated here (the Markdown Frontmatter Standard is deliberately not adopted — see ADR-0001), so keep ADR frontmatter consistent by convention.
