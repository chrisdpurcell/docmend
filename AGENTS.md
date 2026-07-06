# Agents

**Session state:** read `docs/handoff/state.md`, then this file, then `docs/handoff/conventions.md`.

**Full conventions reference:** [`docs/handoff/conventions.md`](docs/handoff/conventions.md) - LLM-targeted pattern library. Check it before adding persistent patterns.

**Detailed review workflows:** not configured for this repo.

## Project

`docmend` is a Python CLI tool (pre-implementation — only a build/tooling scaffold and a version smoke test exist) for normalizing, repairing, and converting a large library (>100k files) of legacy `.txt`/`.html` documents into clean, well-structured Markdown.

Read [`docs/specs/docmend.md`](docs/specs/docmend.md) (SPEC-VHHB, `full` profile, binding Agent Implementation Contract in Appendix B) before proposing any implementation.

## Task Tracking

- [`TODO.md`](TODO.md) — user tasks above agent tasks; don't complete a user task unless asked.
- [`repo-hygiene.md`](repo-hygiene.md) — periodic repository hygiene checklist for cleanup and maintenance passes.
- [`docs/open-questions.md`](docs/open-questions.md) / [`docs/resolved-questions.md`](docs/resolved-questions.md) — the spec's `OQ-`/`RQ-` decision backlog.

## Non-Negotiables

- This repo is public — see conventions #6 before adding any file, fixture, or doc: never real library documents, paths, or personal content.
- Four Project Standards are adopted (python-tooling, markdown-tooling, project-spec, adr), pinned `@v4` — conventions #1-#5 and #8 are their operational how-to. The Markdown Frontmatter Standard is deliberately **not** adopted (ADR-0001) — see conventions #7 for the product-vs-repo-doc frontmatter distinction this creates.
- Never hand-edit a standard-owned file to bypass a check (conventions #8).
