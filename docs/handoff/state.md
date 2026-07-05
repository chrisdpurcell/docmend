# State

**Last updated:** 2026-07-05

## Current

- Pre-implementation: no conversion pipeline or CLI entry point yet — only a build/tooling scaffold (`pyproject.toml`, CI, `src/docmend/` + `tests/` skeleton) and a version smoke test.
- A multi-agent gap analysis (2026-07-05) added `docs/gap-analysis.md` (71 ranked gaps), OQ-015..020 + 8 research supplements in `docs/open-questions.md`, 22 initial `docs/research/` reports, and 4 ChatGPT Deep-Research prompts.
- The 4 returned Deep-Research reports were **reconciled** (2026-07-05): prompts 1–3 folded into OQ-015 (encoding non-ASCII floor: 20-byte default), OQ-016 (free-threading re-open checklist — keep ProcessPool), and OQ-008 (local-fast-backup + async-replicate; Borg/restic/S3 are replication targets, not inline barriers); prompt 4 opened **OQ-023** (deferred-review-artifact content-exposure policy for WH-002/WH-005).
- **Owner decisions (2026-07-05):** reviewed comments on OQ-001..014 and settled ten questions → **RQ-001..010** in `docs/resolved-questions.md` (v1 boundary; v1 naming + identity; resume model; artifact JSON Schemas; risk-scaled safety gate + preservation; verify/exit codes; **preservation-agnostic** posture; **optional/minimal** frontmatter; **deferred** numeric perf targets; **design-for-pluggable/build-minimal** genericity). OQ-007 reframed (user-defined, secure, per-corpus vocabularies — still open). Binding spec prose reworded to match (FR-005/FR-006 risk-scaled preservation + verify-then-mutate; FR-016/§9 optional frontmatter + external vocab; §18.6 agnostic; new D-009 genericity seam); §21 statuses set to Resolved. RQ-004 and RQ-005 flagged as ADR candidates.

## Active Blockers

- Three blocking spec open questions remain (recommendations in `docs/open-questions.md`, ranked in `docs/gap-analysis.md`): **OQ-018** blocks MS-1; **OQ-015** blocks MS-2; **OQ-012** blocks the MS-3 write path. (OQ-001/OQ-004/OQ-005 resolved 2026-07-05 → RQ-001/RQ-004/RQ-005.)

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, `status: draft`)
- Decision backlog: `docs/open-questions.md` / `docs/resolved-questions.md`
- Gap analysis + research: `docs/gap-analysis.md` / `docs/deep-research-queue.md` / `docs/research/`
