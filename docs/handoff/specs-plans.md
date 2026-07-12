# Specs and Plans

The project specification follows the adopted Project Specification Standard; safety-core implementation plans use the repository's `docs/superpowers/` planning tree.

| Type | Location | Notes |
| --- | --- | --- |
| Spec | `docs/specs/docmend.md` (SPEC-VHHB, `full` profile) | Project Specification Standard location (project-standards), `status: approved` (2026-07-07, change-controlled). CI-validated (`.github/workflows/validate-specs.yml`). |
| Decision backlog | `docs/open-questions.md` / `docs/resolved-questions.md` | Companion OQ-/RQ- tracking for the spec's §21 open questions — a spec-standard concept, not part of the handoff system. |
| ADRs | `docs/adr/` | ADR Standard (project-standards), authored from `docs/adr/adr.template.md`. |
| Designs | `docs/superpowers/specs/` | The owner-approved `2026-07-11-million-file-scale-and-resource-design.md` governs DMR-08 planning; its binding SPEC/ADR change control is implementation Task 1 and has not landed yet. |
| Plans | `docs/superpowers/plans/` | Safety-core Plans A-D are implemented. The active DMR-08 plan is `2026-07-11-million-file-scale-and-resource-contract.md`: 12 reviewed tasks, paused before Task 1 change control. The safety-core plans stay until the v2.0.0 release PR lands. |
