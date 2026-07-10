# Agents

**Session state:** Agent Handoff SessionStart injects `docs/handoff/state.md`; do not reread it when injected. Then use this file and `docs/handoff/conventions.md`.

**Full conventions reference:** [`docs/handoff/conventions.md`](docs/handoff/conventions.md) - LLM-targeted pattern library. Check it before adding persistent patterns.

**Detailed review workflows:** not configured for this repo.

## Project

`docmend` is a Python CLI tool (v1.0.2 released 2026-07-07 — the full scan/plan/apply/restore/verify pipeline is live) for normalizing, repairing, and converting a large library (>100k files) of legacy `.txt`/`.html` documents into clean, well-structured Markdown.

Read [`docs/specs/docmend.md`](docs/specs/docmend.md) (SPEC-VHHB, `full` profile, binding Agent Implementation Contract in Appendix B) before proposing any implementation.

## Task Tracking

- [`docs/TODO.md`](docs/TODO.md) — user tasks above agent tasks; don't complete a user task unless asked.
- [`docs/repo-hygiene.md`](docs/repo-hygiene.md) — periodic repository hygiene checklist for cleanup and maintenance passes.
- [`docs/open-questions.md`](docs/open-questions.md) / [`docs/resolved-questions.md`](docs/resolved-questions.md) — the spec's `OQ-`/`RQ-` decision backlog.

## Non-Negotiables

- This repo is public — see conventions #6 before adding any file, fixture, or doc: never real library documents, paths, or personal content.
- Four Project Standards are adopted (python-tooling, markdown-tooling, project-spec, adr), pinned `@v4` — conventions #1-#5 and #8 are their operational how-to. The Markdown Frontmatter Standard is deliberately **not** adopted (ADR-0001) — see conventions #7 for the product-vs-repo-doc frontmatter distinction this creates.
- Never hand-edit a standard-owned file to bypass a check (conventions #8).

<!-- BEGIN agent-handoff managed instructions -->
Use the repo-local `$agent-handoff` skill at startup and closeout.
Do not reread `docs/handoff/state.md` when SessionStart already injected it.
Keep current status and tasks in `docs/STATUS.md` and `docs/TODO.md`; route durable facts through `docs/handoff/`.
At closeout, update only changed facts, preserve user-authored work, store credential references only, and run relevant validation.
<!-- END agent-handoff managed instructions -->
