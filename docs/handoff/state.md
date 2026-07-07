# State

**Last updated:** 2026-07-07

## Current

- **MS-3 complete — PR #9 open (`dev`→`main`, all 5 CI gates green; spec rev 0.16).** Writer layer live: atomic primitives, verify-then-mutate backups, fsync-per-record NDJSON manifest (AOF read rule), adr-0004 safety gate (risk-scaled preservation, OQ-035). `docmend apply` (dry-run default, snapshot-driven, FR-003 hash guard, gate unconditional on writes) + `docmend restore` (LIFO preflight-then-mutate, loss-proof ordering, mode-preserving). flock(2) run lock (OQ-036) on plan/apply/restore. Schemas 1.0→1.1. §18.6 restore drill: full plan→apply→restore byte-identity. Both MS-2 review Importants closed. 527 tests, 97% coverage. Housekeeping (2026-07-07): fixed a `collapse_blank_lines` phantom-blank-line bug (all-blank input + trailing newline under `max=0` returned `"\n"` not `""`) surfaced by the Hypothesis property suite; pinned a deterministic regression. Detail: `sessions/2026-07.md`; plan `docs/superpowers/plans/2026-07-06-ms3-apply-writer.md` (+ codex audits in `docs/codex-reviews/`).
- **PR #9 unblock (2026-07-07):** the only merge blocker was two Copilot review threads flagging `except A, B:` in `lock.py`/`apply.py` as Python-2 syntax — both false positives (PEP 758 makes unparenthesized multi-type `except` valid on 3.14; sites now carry a preempting comment). Resolve the threads (`main` requires conversation resolution) to merge.
- **Next: merge PR #9, then MS-4 Unattended operation** — resume (FR-013 over the landed seq/fsync/AOF manifest), `verify` (FR-014), idempotency (FR-017). MS-4 inputs recorded in TODO/OQ-036: restore lock-key gap (manifest 1.2 `source_root` + lock rekey) + deferred final-review minors (list: `sessions/2026-07.md`).
- **Owner sign-off wanted (non-blocking):** OQ-034 (`.docmend/` convention), OQ-035 (preservation flags/risk tiers), OQ-036 (flock lock + known gap); DEV-001 (MS-2) still pending.
- **Workflow:** `dev`→PR→`main`; no CI on direct `dev` pushes — run the local gate (README) first. Milestone ladder §19 binding (Appendix B).

## Active Blockers

- **None.** Open, non-blocking: OQ-034..036; DEV-001 pending owner review.

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, draft, v0.16)
- Decisions: `docs/resolved-questions.md` (RQ-001..033) · open: `docs/open-questions.md` (OQ-034..036) · ADRs: `docs/adr/` (0001–0017 + backlog)
