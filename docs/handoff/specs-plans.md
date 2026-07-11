# Specs and Plans

The project specification follows the adopted Project Specification Standard; safety-core implementation plans use the repository's `docs/superpowers/` planning tree.

| Type | Location | Notes |
| --- | --- | --- |
| Spec | `docs/specs/docmend.md` (SPEC-VHHB, `full` profile) | Project Specification Standard location (project-standards), `status: approved` (2026-07-07, change-controlled). CI-validated (`.github/workflows/validate-specs.yml`). |
| Decision backlog | `docs/open-questions.md` / `docs/resolved-questions.md` | Companion OQ-/RQ- tracking for the spec's §21 open questions — a spec-standard concept, not part of the handoff system. |
| ADRs | `docs/adr/` | ADR Standard (project-standards), authored from `docs/adr/adr.template.md`. |
| Plans | `docs/superpowers/plans/` | Safety-core Plans A-D are implemented: A (foundations), B (manifest 2.0), C (commit boundary), and D (plan-aware verify redesign, eight green slices after three audit rounds at `2026-07-11-safety-core-d-verify-redesign.md`). The MS-2/MS-3 plans were pruned after v1.0.0 shipped; the safety-core plans stay until the v2.0.0 release PR lands. |
