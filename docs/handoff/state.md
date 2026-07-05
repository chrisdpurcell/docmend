# State

**Last updated:** 2026-07-05

## Current

- **Decision backlog fully settled (2026-07-05):** all 23 spec open questions resolved (RQ-001..023); `docs/open-questions.md` is now empty of open items; zero blocking OQs. Latest: RQ-022 (encoding floor) + RQ-023 (review-artifact exposure); spec at v0.6.

- Pre-implementation: no conversion pipeline or CLI entry point yet — only a build/tooling scaffold (`pyproject.toml`, CI, `src/docmend/` + `tests/` skeleton) and a version smoke test.
- A multi-agent gap analysis (2026-07-05) added `docs/gap-analysis.md` (71 ranked gaps), OQ-015..020 + 8 research supplements in `docs/open-questions.md`, 22 initial `docs/research/` reports, and 4 ChatGPT Deep-Research prompts.
- The 4 returned Deep-Research reports were **reconciled** (2026-07-05): prompts 1–3 folded into OQ-015 (encoding non-ASCII floor: 20-byte default), OQ-016 (free-threading re-open checklist — keep ProcessPool), and OQ-008 (local-fast-backup + async-replicate; Borg/restic/S3 are replication targets, not inline barriers); prompt 4 opened **OQ-023** (deferred-review-artifact content-exposure policy for WH-002/WH-005).
- **Owner decisions (2026-07-05, batch 1):** reviewed comments on OQ-001..014 and settled ten questions → **RQ-001..010** in `docs/resolved-questions.md` (v1 boundary; v1 naming + identity; resume model; artifact JSON Schemas; risk-scaled safety gate + preservation; verify/exit codes; **preservation-agnostic** posture; **optional/minimal** frontmatter; **deferred** numeric perf targets; **design-for-pluggable/build-minimal** genericity). Binding spec prose reworded to match (FR-005/FR-006 risk-scaled preservation + verify-then-mutate; FR-016/§9 optional frontmatter + external vocab; §18.6 agnostic; new D-009 genericity seam). RQ-004 and RQ-005 flagged as ADR candidates.
- **Owner decisions (2026-07-05, batch 2):** settled 11 more → **RQ-011..021**. OQ-007 (external per-corpus vocab seam, mechanism deferred), OQ-011 (EPUB deferred), OQ-012 (**in-place mutation v1** — ADR candidate), OQ-013 (minimal v1 frontmatter shape, provenance deferred), OQ-014 (`--write` opt-in), OQ-016 (ProcessPool+forkserver), OQ-017 (structlog), OQ-018 (jsonschema≥4.26), OQ-019 (Hypothesis dev-only), OQ-021 (pydantic v2), OQ-022 (ruamel.yaml). §21 statuses set to Resolved; **§8.6 rewritten** into Runtime vs Dev/Test tables recording the six dependency approvals (spec v0.5).
- **Owner decisions (2026-07-05, batch 3):** settled the final two → **RQ-022/RQ-023**; **OQ backlog now fully cleared (RQ-001..023), zero blocking OQs.** OQ-015 → RQ-022 (`charset-normalizer` sole detector; confidence = `1.0 − chaos`, no `.confidence` API; keep 0.80; second independent non-ASCII byte-count skip floor, single fixed default **20** in v1 with family-aware table + ratio signal deferred behind the RQ-010 seam; gate order BOM→UTF-8→ASCII→floor; MS-2 calibration checkpoint, not a reopen). OQ-023 → RQ-023 (confidentiality line = public-repo/official-tool surface, **not** the operator's screen; durable review artifacts metadata-only, external tools render text; reaffirms RQ-011 + C-002). Spec reconciled to **v0.6** via a 3-agent drafting workflow (FR-007/§18.2/A-003/FR-015/AW-003/R-001/§8.6/§17.2/§17.3 for RQ-022; §2.2/§11/§13.4/§13.5 for RQ-023); both §21 rows Resolved.

## Active Blockers

- **None.** All spec open questions are settled (RQ-001..023); no blocking OQ remains. The RQ-022 20-byte floor carries a non-blocking **MS-2 calibration checkpoint** (validate against docmend's own short-file distribution; may tune within ~8–20 without reopening).

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, `status: draft`)
- Decision backlog: `docs/open-questions.md` / `docs/resolved-questions.md`
- Gap analysis + research: `docs/gap-analysis.md` / `docs/deep-research-queue.md` / `docs/research/`
