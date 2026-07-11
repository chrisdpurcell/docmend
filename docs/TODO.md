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
  - [x] Plan B — manifest 2.0: header/chain/attempt lineage, journal-every-mutation with durable identities, ManifestSet validation, one lifecycle reducer + adjudication, resume/restore rewrite (DMR-03/04). Plan three-round reviewed ([plan](superpowers/plans/2026-07-10-safety-core-b-manifest-2.md), [review](codex-reviews/2026-07-10-safety-core-b-manifest-2-plan-review.md)); implemented and pushed (`dca9fcf..`), all 13 tasks, full gate green at 97% per commit; the stale scale-test manifest-shape assertion updated (DMR-08 escrow). Identity capture is `os.stat`-based pending Plan C's descriptor-bound CommitBoundary (adr-0020), as planned.
  - [ ] Plan C — commit boundary: descriptor identity binding, action-time overwrite invariant, attested WriteSafetyContext + preview/write split (DMR-06/07). Plan authored and four Codex review rounds converged ([plan](superpowers/plans/2026-07-11-safety-core-c-commit-boundary.md), at `6c30f45`; all 17 findings resolved; CR-006 `effective_excludes` header addition owner-approved 2026-07-11). Next: review round 5, then implement the 12 tasks. Side product: Plan B chain-validator fix `8c2d5f4` (pre-mutation standalone `failed` records are chain-legal again).
  - [ ] Plan D — verify redesign: false-clean closure set, `verify --plan`, verify-report artifact, coupled-medium exits (DMR-05).
  - [ ] After A-D: sub-projects 2-4 (scale/DMR-08, release/DMR-09, observability + docs), then the v2.0.0 `dev` to `main` release PR.

- [ ] Support the owner's first staged real-library rollout under spec section 18.4.

  Blocked on the comprehensive-review remediation above. After it closes, scan read-only, review the plan and skip pile, apply a filtered subset, then widen. Expand the weird-document corpus only through the adr-0015 re-synthesis procedure so no real library bytes or paths enter this public repository.
