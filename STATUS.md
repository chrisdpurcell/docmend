# Project Status

This is the human-facing completion summary for docmend. Agents maintain it so the project builder can re-orient quickly.

## Completed

- Adopted four Project Standards (python-tooling, markdown-tooling, project-spec, adr) — both CI gates green; Markdown Frontmatter Standard deliberately not adopted (ADR-0001).
- Migrated the spec to a conformant `full`-profile project-spec at `docs/specs/docmend.md` (SPEC-VHHB); spec CI (`spec validate` + `spec lint --strict`) is on.
- Adopted the agent-handoff-v3 session-state layout: `docs/handoff/*`, root `STATUS.md`/`TODO.md`, Claude + Codex SessionStart hooks.

## Current State

- Pre-implementation: only a build/tooling scaffold (`pyproject.toml`, CI, `src/docmend/` + `tests/` skeleton) and a version smoke test exist. No conversion pipeline or CLI entry point yet.
- Spec is `status: draft`, `full` profile. After the 2026-07-05 owner decisions, **one** blocking open question remains (**OQ-015** → MS-2); OQ-023 (deferred) is the only other open item. Twenty-one questions are settled in `docs/resolved-questions.md` (RQ-001..021). The full ranked gap landscape is in `docs/gap-analysis.md`.

## Recent Changes

- [2026-07-06] Added `repo-hygiene.md` as a periodic maintenance checklist and linked it from `AGENTS.md`.
- [2026-07-05] Followed up on the owner's second comment batch (OQ-007..022): settled 11 questions into `docs/resolved-questions.md` as **RQ-011..021** — OQ-007 (external per-corpus vocabulary seam, mechanism deferred), OQ-011 (EPUB deferred), OQ-012 (in-place mutation for v1, **ADR candidate**), OQ-013 (minimal v1 frontmatter shape, provenance deferred), OQ-014 (`--write` real-write opt-in), OQ-016 (ProcessPoolExecutor + forkserver), OQ-017 (structlog), OQ-018 (jsonschema ≥ 4.26), OQ-019 (Hypothesis dev-only), OQ-021 (pydantic v2), OQ-022 (ruamel.yaml). Removed those sections from `docs/open-questions.md` (only OQ-015 and OQ-023 remain open), set §21 statuses Resolved, and **rewrote spec §8.6** into Runtime vs Dev/Test dependency tables recording the six library approvals (spec v0.5). Four inferable decisions (OQ-012/013/014/007) were confirmed via an in-session AskUserQuestion. Blocking OQs dropped 3 → 1.
- [2026-07-05] Followed up on the owner's OQ-001..014 comments: settled ten questions into `docs/resolved-questions.md` as **RQ-001..010** (v1 boundary; v1 naming + identity; resume; artifact JSON Schemas; risk-scaled apply safety gate + preservation; verify/exit codes; preservation-agnostic posture; optional/minimal frontmatter; deferred numeric perf targets; design-for-pluggable/build-minimal genericity). Removed those sections from `docs/open-questions.md` (rebuilt its ToC) and **re-scoped OQ-007** to user-defined, secure, per-corpus vocabularies. Reworded binding spec prose to match — FR-005/FR-006 (risk-scaled preservation + verify-then-mutate), FR-016/§9 (optional frontmatter + externally-supplied vocab), §18.6 (preservation-agnostic), NFR-001 (targets deferred), new **D-009** (genericity policy seams) — and set §21 statuses to Resolved. RQ-004 and RQ-005 flagged as ADR candidates.
- [2026-07-05] Reconciled the 4 returned ChatGPT Deep-Research reports into the decision backlog: prompt 1 (charset floors) → OQ-015 (20-byte non-ASCII default + family-aware overrides, count-based gate, BOM/UTF-8 ordering); prompt 2 (free-threading) → OQ-016 (keep ProcessPool + forkserver; release-gated re-open checklist + dep-readiness); prompt 3 (backup medium) → OQ-008 (local-fast-backup + async replicate; Borg/restic/S3 are replication targets, not inline durability barriers; per-medium preflight/abort/heartbeat) with cross-refs in OQ-010/OQ-005; prompt 4 (deferred review artifacts) → new **OQ-023** (WH-002/WH-005 content-exposure policy). Updated `docs/deep-research-queue.md` (per-prompt reconciliation notes), `docs/research/index.md`, and the spec §21 register. No normative spec text changed — the four target OQs stay owner-undecided.
- [2026-07-05] Converted the 4 queued ChatGPT Deep-Research `.docx` reports into `docs/research/` Markdown, preserving their citation/reference links, and updated `docs/research/index.md` plus `docs/deep-research-queue.md` to mark them converted.
- [2026-07-05] Ran a multi-agent gap analysis: `docs/gap-analysis.md` (71 ranked gaps with downstream impacts), OQ-015..020 + 8 research supplements, 22 `docs/research/` reports, and 4 queued ChatGPT Deep-Research prompts; reconciled spec §21 with the OQ backlog and fixed ADR-0001's removed-draft links.
- [2026-07-05] Reviewed `docs/research/` (Pandoc/frontmatter validation, self-hosted corpus storage) against the spec and strengthened several sections (C-006, FR-016/DR-005, OQ-008, OQ-011).
- [2026-07-05] Populated `docs/open-questions.md`/`docs/resolved-questions.md` as the spec's decision backlog.
- [2026-07-05] Adopted the agent-handoff-v3 session-state layout: `docs/handoff.md` retired, `AGENTS.md` slimmed 12,254 -> 1,639 bytes with detail moved to `docs/handoff/conventions.md`, and Claude + Codex SessionStart hooks installed.

## Notes For The Builder

- Read `docs/specs/docmend.md` (Appendix B) before proposing any implementation — it is a binding Agent Implementation Contract, not just background.
- Milestone order (spec §19) is binding: do not build a later milestone on an unproven earlier one.
