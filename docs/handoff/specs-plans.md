# Specs and Plans

The project specification follows the adopted Project Specification Standard; safety-core implementation plans use the repository's `docs/superpowers/` planning tree.

| Type | Location | Notes |
| --- | --- | --- |
| Spec | `docs/specs/docmend.md` (SPEC-VHHB, `full` profile) | Project Specification Standard location (project-standards), `status: approved` (2026-07-07, change-controlled). CI-validated (`.github/workflows/validate-specs.yml`). |
| Decision backlog | `docs/open-questions.md` / `docs/resolved-questions.md` | Companion OQ-/RQ- tracking for the spec's §21 open questions — a spec-standard concept, not part of the handoff system. |
| ADRs | `docs/adr/` | ADR Standard (project-standards), authored from `docs/adr/adr.template.md`. |
| Designs | `docs/superpowers/specs/` | The owner-approved `2026-07-11-million-file-scale-and-resource-design.md` governs DMR-08; its first binding change-control revision is SPEC-VHHB 0.30 plus `adr-0022-sequential-million-file-scale-contract`. |
| Plans | `docs/superpowers/plans/` | Safety-core Plans A-D and all 12 tasks in `2026-07-11-million-file-scale-and-resource-contract.md` are complete. DMR-08 is closed with accepted 100,000-file pilot, file-size, and one-million-file evidence. The plans stay until the v2.0.0 release PR lands; DMR-09 is next. |
