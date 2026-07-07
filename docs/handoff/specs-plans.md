# Specs and Plans

This repo does not use the default `docs/superpowers/{specs,plans}/` locations — recording the actual locations here per the handoff spec's documented exception clause.

| Type | Location | Notes |
| --- | --- | --- |
| Spec | `docs/specs/docmend.md` (SPEC-VHHB, `full` profile) | Project Specification Standard location (project-standards), `status: approved` (2026-07-07, change-controlled). CI-validated (`.github/workflows/validate-specs.yml`). |
| Decision backlog | `docs/open-questions.md` / `docs/resolved-questions.md` | Companion OQ-/RQ- tracking for the spec's §21 open questions — a spec-standard concept, not part of the handoff system. |
| ADRs | `docs/adr/` | ADR Standard (project-standards), authored from `docs/adr/adr.template.md`. |
| Plans | `docs/superpowers/plans/` (currently absent) | Empty since the post-v1.0.0 hygiene pass: the MS-2 and MS-3 implementation plans were pruned once the MS-0..5 ladder completed (per `docs/repo-hygiene.md` — completed plans are deletable when the overall project ships). New feature/bugfix plans go back here. |
