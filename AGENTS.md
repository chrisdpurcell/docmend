# Agents

## Project

`docmend` is a Python CLI tool (pre-implementation — no source code yet) for normalizing, repairing, and converting a large library (>100k files) of legacy `.txt`/`.html` documents into clean, well-structured Markdown.

The full problem statement, design rationale, and requirements live in [`docs/specs/docmend-spec-draft.md`](docs/specs/docmend-spec-draft.md) — read it before proposing any implementation. Key decisions already locked in there:

- **Output format:** Pandoc-flavored Markdown, CommonMark-ish body, strict YAML frontmatter (title, author, date, tags, source provenance, generated fields like word/chapter count and checksum) validated against a schema.
- **Encoding / line endings:** normalize everything to UTF-8 / LF regardless of source encoding (Latin-1, Windows-1252, mixed ASCII/CR/CRLF/LF).
- **Non-negotiable requirements:** back up or version-control originals before mutating them, support `--dry-run`, make batch processing resumable, and log in detail — the file volume makes manual review of results impossible, so these aren't optional nice-to-haves.

## Status & workflow

- No source code, tests, or build tooling exist yet — don't assume a `pyproject.toml`, test runner, or CLI entry point is present without checking first.
- When implementation starts, use the `uv-strict-python` conventions (uv for envs/deps, Ruff, BasedPyright strict, pytest + coverage, pip-audit) rather than inventing tooling ad hoc.
- Task-tracking conventions are defined in [`TODO.md`](TODO.md) — read it before adding or completing tasks. Agent-added and user-added tasks live in separate sections with different completion rules; don't complete a user-added task unless asked.
- `docs/handoff.doc` is currently just a placeholder header for session handoff notes.

## Handling sensitive data (this repository is public)

`docmend`'s entire purpose is operating on a large personal document library that may contain private or identifying content (old letters, journals, financial records, etc.). Because this repo is public:

- Never commit real documents from the user's actual library, real local file paths from that library, or any sample corpus containing real personal/identifying content. Test fixtures must be synthetic or public-domain text written for the purpose.
- If an external service integration is added later (LLM APIs, OCR, cloud storage), read credentials from environment variables only — never hardcode keys or tokens. Document required variables in a `.env.example`, not a real `.env` (already gitignored).
- Don't reference the user's private infrastructure (internal hostnames, credential-store paths, network addresses) in code, comments, or docs — none of it is relevant to this tool.
