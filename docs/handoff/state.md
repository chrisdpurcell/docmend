# State

**Last updated:** 2026-07-07

## Current

- **MS-3 complete — PR #9 open (`dev`→`main`, all 5 CI gates green; spec rev 0.16).** Writer layer live: atomic primitives, verify-then-mutate backups, fsync-per-record NDJSON manifest (AOF read rule), adr-0004 safety gate (risk-scaled preservation, OQ-035). `docmend apply` (dry-run default, snapshot-driven, FR-003 hash guard, gate unconditional on writes) + `docmend restore` (LIFO preflight-then-mutate, loss-proof ordering, mode-preserving). flock(2) run lock (OQ-036) on plan/apply/restore. Schemas 1.0→1.1. §18.6 restore drill: full plan→apply→restore byte-identity. Both MS-2 review Importants closed. 527 tests, 97% coverage. Housekeeping (2026-07-07): fixed a `collapse_blank_lines` phantom-blank-line bug (all-blank input + trailing newline under `max=0` returned `"\n"` not `""`) surfaced by the Hypothesis property suite; pinned a deterministic regression. Detail: `sessions/2026-07.md`; plan `docs/superpowers/plans/2026-07-06-ms3-apply-writer.md` (+ codex audits in `docs/codex-reviews/`).
- **MS-3 merged (2026-07-07, PR #9 → `main` `468dd9f`; `dev` synced).** The merge blocker was two Copilot review threads flagging `except A, B:` in `lock.py`/`apply.py` as Python-2 syntax — both false positives (PEP 758 makes unparenthesized multi-type `except` valid on 3.14; sites now carry a preempting comment); resolved, CI green on `808ab49`, merged.
- **MS-4 Unattended operation — in progress (spec rev 0.17).** ✅ **OQ-036 lock-key gap closed** (2026-07-07): manifest schema 1.1→1.2 adds writer-stamped `source_root`; `docmend restore` keys its lock on it via `cli._restore_lock_root` (falls back to `commonpath` for pre-1.2 manifests), so restore now contends with a concurrent apply even when mutated files nest below the root (AW-005). ✅ **`docmend verify` landed** (FR-014, IR-004, adr-0012): read-only UTF-8-decodability + LF-only content checks (reusing scan's facts, `verify.py::check_content`) plus manifest after-hash reconciliation (`reconcile_manifest`); input via `--manifest`/`--run-id` sidecar; 0/1/2 exit taxonomy; proven read-only; no lock. §17.3 IR-004 Complete, FR-014 Partial. TDD throughout, 545 tests, 97% coverage, full gate green. **Remaining MS-4:** resume (FR-013 over the seq/fsync/AOF manifest), idempotency (FR-017), stale-plan tests, single-file verify journey (NFR-006), verify report/count reconciliation; then the deferred MS-3 final-review minors (`sessions/2026-07.md`). Not yet in a PR — MS-4 work sits on `dev` ahead of `main`.
- **Owner sign-off wanted (non-blocking):** OQ-034 (`.docmend/` convention), OQ-035 (preservation flags/risk tiers), OQ-036 (flock lock + known gap); DEV-001 (MS-2) still pending.
- **Workflow:** `dev`→PR→`main`; no CI on direct `dev` pushes — run the local gate (README) first. Milestone ladder §19 binding (Appendix B).

## Active Blockers

- **None.** Open, non-blocking: OQ-034..036; DEV-001 pending owner review.

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, draft, v0.17)
- Decisions: `docs/resolved-questions.md` (RQ-001..033) · open: `docs/open-questions.md` (OQ-034..036) · ADRs: `docs/adr/` (0001–0017 + backlog)
