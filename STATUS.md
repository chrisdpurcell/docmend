# Project Status

This is the human-facing completion summary for docmend. Agents maintain it so the project builder can re-orient quickly.

## Completed

- **v1.0.0 released** (2026-07-07): signed tag `v1.0.0`, GitHub Release with sdist + wheel, published by the tag-triggered release workflow. The full milestone ladder MS-0..MS-5 (spec §19) shipped across PRs #5–#11; per-milestone detail lives in `docs/handoff/sessions/2026-07.md` and the spec's revision history.
- The complete v1 pipeline is live: `scan` (read-only inventory), `plan` (reviewable transform plan), `apply` (dry-run default, gated writes, atomic mutation, reversible manifest, `--resume-*` continuation), `restore` (byte-identical undo), `verify` (content + frontmatter + manifest/report reconciliation). Idempotent re-runs; 100k-file scale-tested (477 MiB peak); per-file watchdog.
- Governance: four Project Standards adopted (`@v4`), spec SPEC-VHHB **approved** (rev 0.24) with a fully Complete §17.3 traceability matrix, ADRs 0001–0018, protected `main` with five required CI checks + dependency-review, Dependabot version updates + vulnerability alerts + automated security fixes enabled.

## Current State

- **Post-release maintenance mode.** `dev` → PR → `main` continues for bug fixes and post-v1 features; the release path is tag-triggered (`release.yml`).
- **v1.0.2 released (2026-07-07)**: ships the cross-repo alignment hardening — both P0 safety findings fixed (same-run rename collisions could merge under `overwrite`; a hard kill inside `rename_and_rewrite`'s window left unmanifested mutations, now covered by manifest 1.3 write-ahead intent records + resume reconciliation) — plus scan-time excluded-dir pruning, release-workflow pinning, and a pre-release two-agent doc-drift sweep (spec rev 0.25). **adr-0018** (repository boundary) accepted with the sibling ADR confirmed; the temporary `ALIGNMENT_HANDOFF.md` is deleted.
- **The next substantive step is the owner's**: the §18.4 staged real-library rollout (scan → plan review → filtered apply → widen) and weird-corpus expansion from real scan findings (adr-0015 anonymization procedure). Tracked in `TODO.md`.
- Spec is **`status: approved`** (owner, 2026-07-07; rev 0.25) — change-controlled: edits need a revision row; scope changes need owner re-approval. The decision backlog is empty.
- 619 tests + an opt-in 100k scale test (`DOCMEND_SCALE=1`), 97% coverage.

## Recent Changes

- [2026-07-07] **Cross-repo alignment hardening** (PR #18): same-run collision fix, manifest 1.3 intent records, excluded-dir pruning, setup-uv SHA pin, v1.0.1 doc drift, spec rev 0.24; adr-0018 boundary ADR accepted (sibling confirmed) and the temporary coordination file retired.
- [2026-07-07] Post-release housekeeping: milestone plans pruned, STATUS/architecture refreshed, Dependabot alerts + automated security fixes enabled, release-workflow input warning fixed (PR #12).
- [2026-07-07] **v1.0.0 + v1.0.1 released** (PRs #11/#16 + tags): MS-5 complete; issue #15 partial-undo trap surfaced at apply/restore time.
- [2026-07-07] MS-4 complete (PR #10): verify, resume (FR-013), idempotency (FR-017), frontmatter contract (DR-005).

## Notes For The Builder

- Read `docs/specs/docmend.md` (Appendix B) before proposing any implementation — it is a binding Agent Implementation Contract, not just background.
- Post-v1 changes still trace to the spec: new behavior means a spec revision (and an ADR when architectural), not just code.
- Run `scripts/check_traceability.py` after any edit to the spec or the question files; CI enforces it.
- All changes go `dev` → PR → `main`; direct pushes to `dev` do not run CI — run the local gate first (see README).
