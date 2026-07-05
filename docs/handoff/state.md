# State

**Last updated:** 2026-07-05

## Current

- Pre-implementation: no conversion pipeline or CLI entry point yet — only a build/tooling scaffold (`pyproject.toml`, CI, `src/docmend/` + `tests/` skeleton) and a version smoke test.
- A multi-agent gap analysis (2026-07-05) added `docs/gap-analysis.md` (71 ranked gaps), OQ-015..020 + 8 research supplements in `docs/open-questions.md`, 22 initial `docs/research/` reports, and 4 ChatGPT Deep-Research prompts.
- The 4 returned Deep-Research reports were **reconciled** (2026-07-05): prompts 1–3 folded into OQ-015 (encoding non-ASCII floor: 20-byte default), OQ-016 (free-threading re-open checklist — keep ProcessPool), and OQ-008 (local-fast-backup + async-replicate; Borg/restic/S3 are replication targets, not inline barriers); prompt 4 opened **OQ-023** (deferred-review-artifact content-exposure policy for WH-002/WH-005).
- **Owner decisions (2026-07-05, batch 1):** reviewed comments on OQ-001..014 and settled ten questions → **RQ-001..010** in `docs/resolved-questions.md` (v1 boundary; v1 naming + identity; resume model; artifact JSON Schemas; risk-scaled safety gate + preservation; verify/exit codes; **preservation-agnostic** posture; **optional/minimal** frontmatter; **deferred** numeric perf targets; **design-for-pluggable/build-minimal** genericity). Binding spec prose reworded to match (FR-005/FR-006 risk-scaled preservation + verify-then-mutate; FR-016/§9 optional frontmatter + external vocab; §18.6 agnostic; new D-009 genericity seam). RQ-004 and RQ-005 flagged as ADR candidates.
- **Owner decisions (2026-07-05, batch 2):** settled 11 more → **RQ-011..021**. OQ-007 (external per-corpus vocab seam, mechanism deferred), OQ-011 (EPUB deferred), OQ-012 (**in-place mutation v1** — ADR candidate), OQ-013 (minimal v1 frontmatter shape, provenance deferred), OQ-014 (`--write` opt-in), OQ-016 (ProcessPool+forkserver), OQ-017 (structlog), OQ-018 (jsonschema≥4.26), OQ-019 (Hypothesis dev-only), OQ-021 (pydantic v2), OQ-022 (ruamel.yaml). §21 statuses set to Resolved; **§8.6 rewritten** into Runtime vs Dev/Test tables recording the six dependency approvals (spec v0.5).

## Active Blockers

- **One** blocking spec open question remains: **OQ-015** (encoding detector / non-ASCII floor) blocks MS-2 — its 20-byte default still needs one project-internal validation run before FR-007/§18.2 are edited. OQ-018 (was blocking MS-1) and OQ-012 (was blocking MS-3 write path) resolved 2026-07-05 → RQ-018/RQ-013. Non-blocking OQ-023 (review-artifact policy, deferred) also stays open.

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, `status: draft`)
- Decision backlog: `docs/open-questions.md` / `docs/resolved-questions.md`
- Gap analysis + research: `docs/gap-analysis.md` / `docs/deep-research-queue.md` / `docs/research/`
