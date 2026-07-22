# Agents

<!-- markdownlint-disable-file MD037 MD049 -->
<!-- The project-standards managed instruction blocks appended below contain literal
     glob patterns (e.g. the markdown/structured-config scopes) that this repo's strict
     MD049=underscore / MD037 rules flag as emphasis. Those blocks disable only MD025 and
     are control-plane-owned (reconcile reverts edits), so the two emphasis rules are
     disabled file-wide here. Reported upstream to project-standards. -->

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
- Four Project Standards are adopted (python-tooling, markdown-tooling, project-spec, adr), managed via the V5 control plane (`.standards/`) — conventions #1-#5 and #8 are their operational how-to. The Markdown Frontmatter Standard is deliberately **not** adopted (ADR-0001) — see conventions #7 for the product-vs-repo-doc frontmatter distinction this creates.
- Never hand-edit a standard-owned file to bypass a check (conventions #8).

## Review Orchestrator Note

- Full `review-orchestrator` sweeps now run selected child reviews with bounded parallelism by default, currently up to `8` in parallel after planning, preflight, and shared research complete.
- The shared-research phase can legitimately take around `10` minutes on larger or research-heavy repos before child reviews start, so treat that as normal unless heartbeats stop or no artifact activity appears beyond that window.
- Expect the sweep index, child review reports, and `*-execution.json` manifests under `docs/codex-reviews/` while the sweep is running.
- Do not describe sweep child reviews as running “one at a time” unless the sweep was explicitly configured down to serial execution.

<!-- prettier-ignore-start -->

<!-- BEGIN project-standards:agent-handoff -->
<!-- markdownlint-disable MD025 -->
# Agent Handoff

Use the repo-local `agent-handoff` skill at session startup and closeout. Do not reread state already injected by SessionStart. Keep project knowledge inside this repository and store credential references only, never values.
<!-- markdownlint-enable MD025 -->
<!-- END project-standards:agent-handoff -->

<!-- prettier-ignore-end -->

<!-- prettier-ignore-start -->

<!-- BEGIN project-standards:markdown-tooling -->
<!-- markdownlint-disable MD025 -->
# Markdown and structured-text tooling

Prettier owns physical formatting and markdownlint owns Markdown structure. Do not add overlapping tools.

Enabled checks: format, lint.
Markdown scope: **/*.md.
Structured-config scope: **/*.json, **/*.jsonc, **/*.yml, **/*.yaml.

Run the enabled checks before claiming completion.
<!-- markdownlint-enable MD025 -->
<!-- END project-standards:markdown-tooling -->

<!-- prettier-ignore-end -->

<!-- prettier-ignore-start -->

<!-- BEGIN project-standards:python-tooling -->
<!-- markdownlint-disable MD025 -->
# Python tooling

Use uv for environments and dependency changes. Ruff owns formatting, linting, and imports.
Use basedpyright in strict mode for type checking. Do not add a competing Python gate.

Run before claiming completion:

```bash
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run coverage run -m pytest
uv run coverage report
uv run pip-audit
```

When the gate reports formatting or lint findings, run:

```bash
uv run ruff format .
uv run ruff check . --fix
```
<!-- markdownlint-enable MD025 -->
<!-- END project-standards:python-tooling -->

<!-- prettier-ignore-end -->
