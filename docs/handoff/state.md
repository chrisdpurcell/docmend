# State

**Last updated:** 2026-07-07

## Current

- **MS-4 Unattended operation — in progress (spec rev 0.17).** `dev` is 3 commits ahead of `main`, not yet in a PR. 545 tests, 97% coverage, full gate + spec validators + traceability green.
  - ✅ **OQ-036 lock-key gap closed:** manifest 1.1→1.2 adds writer-stamped `source_root`; `docmend restore` keys its lock on it via `cli._restore_lock_root` (falls back to `commonpath` for pre-1.2 manifests), so restore contends with a concurrent apply even when mutated files nest below the root (AW-005).
  - ✅ **`docmend verify` landed** (FR-014, IR-004, adr-0012): read-only UTF-8 + LF content checks (reusing scan's facts, `verify.py`) + manifest after-hash reconciliation; `--manifest`/`--run-id` sidecar; 0/1/2 exit taxonomy; no lock. §17.3 IR-004 Complete, FR-014 Partial.
  - **Remaining:** resume (FR-013 over the AOF manifest, adr-0006), idempotency (FR-017), single-file verify journey (NFR-006), verify report/count reconciliation; then the deferred MS-3 final-review minors (`sessions/2026-07.md`).
- **MS-3 merged** (PR #9 → `main` `468dd9f`, 2026-07-07; a housekeeping pass fixed a `collapse_blank_lines` phantom-blank-line bug en route). Detail: `sessions/2026-07.md`.
- **Owner sign-off wanted (non-blocking):** OQ-034 (`.docmend/`), OQ-035 (preservation flags/tiers), OQ-036 (lock location/mechanism — key gap now fixed); DEV-001 (MS-2) pending.
- **Workflow:** `dev`→PR→`main`; no CI on direct `dev` pushes — run the local gate (README) first. Milestone ladder §19 binding.

## Active Blockers

- **None.** Open, non-blocking: OQ-034..036; DEV-001 pending owner review.

## Pointers

- Spec: `docs/specs/docmend.md` (SPEC-VHHB, draft, v0.17)
- Decisions: `docs/resolved-questions.md` (RQ-001..033) · open: `docs/open-questions.md` (OQ-034..036) · ADRs: `docs/adr/` (0001–0017 + backlog)
