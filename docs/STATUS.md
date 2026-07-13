# Project Status

## Current snapshot

- docmend v1.0.2 is released with the complete scan, plan, apply, restore, resume, and verify pipeline.
- The approved SPEC-VHHB revision 0.31 and ADRs 0001-0022 govern landed post-v1 changes (adr-0006 superseded by adr-0019; adr-0007 superseded by adr-0022). Non-blocking OQ-038 records the Task 3 aggregate evidence-model assumption through the pilot revision-two approval boundary. DMR-08 change control binds the sequential million-file, bounded-linear resource contract and plan schema 2.0 migration.
- The current `dev` baseline is 1,043 passing tests plus one opt-in historical 100k-file scale skip, with 94% branch coverage.
- The repository workflow is `dev` to pull request to protected `main`; releases are signed `vX.Y.Z` tags with sdist and wheel artifacts. `main` stays at v1.0.2 until the v2.0.0 safety-core release ships all four remediation plans.
- Safety-core Plans A-D are implemented: output/backup ownership and artifact guards (DMR-01/02); manifest/report 2.0 lineage, journaled recovery, and shared lifecycle adjudication (DMR-03/04); descriptor-bound commit authority and action-time overwrite preservation (DMR-06/07); and plan-aware verification with complete false-clean findings, guarded verify reports, and same-root read locking (DMR-05).
- Plan D was implemented as eight green commits (`39784b0..f906e9e`) after three audit rounds approved the [plan](superpowers/plans/2026-07-11-safety-core-d-verify-redesign.md), then fast-forward merged into `dev` and pushed to `origin/dev`. `verify --plan` now certifies repeatable attempt lineage and exactly-once outcomes; restore evidence is lifecycle-only and never requires an apply report.
- DMR-08 has an owner-approved [million-file scale design](superpowers/specs/2026-07-11-million-file-scale-and-resource-design.md) and an adversarially reviewed [12-task implementation plan](superpowers/plans/2026-07-11-million-file-scale-and-resource-contract.md). Tasks 1-3 are complete: change control binds the sequential contract; `parallel.*` and plan 1.x fail before work; and strict public-safe evidence, reference-environment, and executable-threshold contracts now bind exact wheel/candidate/reference provenance, external RSS, conservation, and pilot-derived limits without publishing operator identifiers. Task 4 resource preflight is next.
- DMR-08 (scale), DMR-09 (release), and observability/documentation remain in post-A-D sub-projects 2-4 before the v2.0.0 release PR.
- The owner's staged real-library write rollout stays paused behind the remediation (spec section 18.4 precondition).
- Agent Handoff v3 provides the shared repo-local session-state and durable-fact layout for the dual Claude/Codex profile.
