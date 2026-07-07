# State

**Last updated:** 2026-07-07

## Current

- **MS-3 User and admin experience complete — PR #9 open (`dev`→`main`; spec rev 0.16).** The writer layer is live: atomic primitives (temp+fsync+replace, link-based no-clobber renames, `rename_overwrite`; NFR-002 crash-injection tested), verify-then-mutate backups (FR-006/ERR-004), fsync-per-record NDJSON manifest with the AOF read rule (torn tail tolerated only when physically unterminated), and the adr-0004 pure-predicate safety gate (risk-scaled preservation per OQ-035; 16-case allpairspy sweep). `docmend apply` (IR-003): dry-run default, plan-snapshot-driven (no `--config`), per-file FR-003 hash guard, gate unconditional on write runs, refusal reports (§8.5). `docmend restore` (IR-008): LIFO preflight-then-mutate replay, loss-proof ordering, mode preservation, external-preservation records skipped whole. flock(2) run lock (OQ-027/OQ-036) wired into plan/apply/restore. Schemas 1.0→1.1 (inventory: detection provenance + path hardening; plan: optional `source_root`; manifest: overwrite-preservation fields). §18.6 restore drill automated: full plan→apply→restore byte-identity, incl. relative-backup-dir/cwd-change. Both MS-2 final-review Importants closed (cross-config binary-suspect misclassification; artifact path containment). 526 tests, 97% coverage. Execution: 13 tasks, each task-reviewed with fix rounds; final whole-branch review "with fixes" → fixes landed (`1f9cdf0`) and re-approved. Plan: `docs/superpowers/plans/2026-07-06-ms3-apply-writer.md` (pre-audited, 4 codex rounds in `docs/codex-reviews/`).
- **Next: merge PR #9, then MS-4 Unattended operation** — resume model (FR-013, adr-0006 reconciliation over the landed seq/fsync/AOF manifest), `verify` (FR-014), idempotency (FR-017), stale-plan tests. **Recorded MS-4 inputs:** restore lock-key gap (manifest 1.2 `source_root` field + restore lock rekey — OQ-036 notes/TODO row); deferred final-review minors (gate collision-stat race, manifest newer-minor message, restore `--id` unmatched-filter exit-0, inverse-record `action_id` seq divergence, refusal-report path not echoed, dry-run-restore artifact note).
- **Owner sign-off wanted (non-blocking):** OQ-034 (`.docmend/` artifact convention — apply/restore now follow it), OQ-035 (preservation flags + risk tiers), OQ-036 (flock lock + documented lock-key gap); DEV-001 (EC-011 plan-time hard-link skip) still pending from MS-2.
- **Workflow reminder:** all changes go `dev`→PR→`main`; no CI on direct `dev` pushes — run the local gate (README) before opening the PR. Milestone ladder §19 is binding (Appendix B).

## Active Blockers

- **None.** Open, non-blocking: OQ-034/OQ-035/OQ-036 (owner sign-off wanted by MS-4); DEV-001 pending owner review.

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, draft, v0.16)
- Decisions: `docs/resolved-questions.md` (RQ-001..033) · open: `docs/open-questions.md` (OQ-034..036) · ADRs: `docs/adr/` (0001–0017 + backlog)
- MS-3 plan + audits: `docs/superpowers/plans/2026-07-06-ms3-apply-writer.md` · `docs/codex-reviews/`
