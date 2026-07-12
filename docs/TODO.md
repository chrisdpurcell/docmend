# Project Tasks

<!--
Purpose:
- This document is the user-visible task list and agent-visible project queue.

Instructions for AI agents:
- Do not add tasks to the `## User tasks` section.
- Do add tasks to the `## Agent tasks` section. Include all open work from agent-managed handoff documents.
- Use `- [ ]` to indicate open work and `- [x]` for work completed during the current session.
- Remove completed standalone agent tasks after recording their outcomes in `docs/STATUS.md`.
-->

## User tasks

- [x] **URGENT:** See `docs/codex-reviews/2026-07-10-2034-all-review-findings.md`. Verify using `/superpowers:receiving-code-review`. Some were corrected and some major dev work has been implemented since this review, so take extra care concerning blast radius, regression review, and determining potential effects on the work that has been completed since the review. — Verified against HEAD: see [2026-07-10-2251 verification](codex-reviews/2026-07-10-2251-all-findings-verification.md), including a per-finding appendix covering all 189 raw findings. DMR-01/02 confirmed closed by Plan A; 4 raw findings fixed, 6 partially fixed, 179 still open with scope unchanged; no Plan A regressions; Plans B–D need no re-planning.

## Agent tasks

- [ ] Remediate the confirmed rollout blockers in the [2026-07-10 comprehensive review synthesis](codex-reviews/2026-07-10-2034-comprehensive-review-synthesis.md) per the approved [safety-core design](superpowers/specs/2026-07-10-safety-core-remediation-design.md) (spec rev 0.26/0.27, ADRs 0019-0021).

  - [x] Plan A — foundations (DMR-01/02): output ledger, write-once backup keys, artifact destination guard, randomized staging, in-lock report finalization. Implemented, final-reviewed, pushed (`b9d5195..6ae7547`).
  - [x] Plan B — manifest 2.0: header/chain/attempt lineage, journal-every-mutation with durable identities, ManifestSet validation, one lifecycle reducer + adjudication, resume/restore rewrite (DMR-03/04). Plan three-round reviewed ([plan](superpowers/plans/2026-07-10-safety-core-b-manifest-2.md), [review](codex-reviews/2026-07-10-safety-core-b-manifest-2-plan-review.md)); implemented and pushed (`dca9fcf..`), all 13 tasks, full gate green at 97% per commit; the stale scale-test manifest-shape assertion updated (DMR-08 escrow). Plan C subsequently replaced its provisional `os.stat` identity capture with the descriptor-bound CommitBoundary (adr-0020).
  - [x] Plan C — commit boundary: descriptor identity binding, action-time overwrite invariant, attested WriteSafetyContext + preview/write split (DMR-06/07). All 12 tasks in the owner-approved [plan](superpowers/plans/2026-07-11-safety-core-c-commit-boundary.md) are locally merged into `dev` (`571015c..ca59cdd`); full gate green at 891 passed, one opt-in scale skip, 95% coverage. Spec rev 0.28 synchronizes §17.3 evidence for landed Plans A-C.
  - [x] Plan D — verify redesign: false-clean closure, exactly-once `verify --plan`, optional guarded verify-report, repeatable attempt lineage, and same-root scan/verify locking (DMR-05). The three-round-approved [plan](superpowers/plans/2026-07-11-safety-core-d-verify-redesign.md) landed as eight green slices (`39784b0..f906e9e`), was fast-forward merged into `dev`, and was pushed to `origin/dev`; final gate: 983 passed, one opt-in scale skip, 95% branch coverage; spec rev 0.29 synchronizes FR-014/IR-004/IR-007 evidence.
  - [ ] Sub-project 2 — scale/DMR-08: execute the owner-approved [million-file design](superpowers/specs/2026-07-11-million-file-scale-and-resource-design.md) through the reviewed [implementation plan](superpowers/plans/2026-07-11-million-file-scale-and-resource-contract.md).
    - [x] Change control: settle OQ/RQ-037, revise SPEC-VHHB to 0.30, accept ADR-0022, supersede ADR-0007, and amend ADR-0005 for plan 2.0.
    - [ ] Config and artifact compatibility: remove `parallel.*`, reject legacy tables, adopt plan schema 2.0, and reject plan 1.x before gate evaluation or mutation.
    - [ ] Evidence and resource harness: add strict public-safe evidence/reference/threshold contracts, external RSS stage supervision, capacity preflight, and deterministic corpus recipes.
    - [ ] Default guard: replace the stale scale test with the 1,000-file source-tree PR tier.
    - [ ] Liveness and capacity: add aggregate heartbeat/terminal events and evidence-based per-filesystem resource accounting.
    - [ ] Pilot and threshold revision: run the 10,000/100,000-file uninstrumented pilot, publish supporting evidence, and freeze numeric thresholds in SPEC revision two.
    - [ ] Scheduled diagnostic: add the installed-wheel 100,000-file scheduled/manual workflow.
    - [ ] Release qualification: accept the file-size envelope and one-million-file candidate evidence, including the 12-hour practicality bound.
    - [ ] Closeout: reconcile DMR-08 findings, evidence, status, and handoff while keeping the real-library write rollout blocked behind remaining release work.
  - [ ] Sub-projects 3-4 — release/DMR-09 plus remaining observability/documentation, then the v2.0.0 `dev` to `main` release PR.

- [ ] Support the owner's first staged real-library rollout under spec section 18.4.

  Blocked on the comprehensive-review remediation above. After it closes, scan read-only, review the plan and skip pile, apply a filtered subset, then widen. Expand the weird-document corpus only through the adr-0015 re-synthesis procedure so no real library bytes or paths enter this public repository.
