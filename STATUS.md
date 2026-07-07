# Project Status

This is the human-facing completion summary for docmend. Agents maintain it so the project builder can re-orient quickly.

## Completed

- Adopted four Project Standards (python-tooling, markdown-tooling, project-spec, adr) — CI gates green; Markdown Frontmatter Standard deliberately not adopted (ADR-0001).
- Spec `docs/specs/docmend.md` (SPEC-VHHB, `full` profile) is implementation-ready: entire decision backlog settled (RQ-001..033, zero blocking), ADR set 0001–0017 accepted, 71-gap register fully dispositioned, traceability drift-check CI gate live.
- Branch/CI/CD workflow live (ADR-0017): protected `main`, merge-commit PRs from long-lived `dev`, five required checks + dependency-review license gate.
- **MS-0 Foundation implemented** (2026-07-06, PR #5): `docmend` CLI entry point with the IR-005 global flags, strict §18.2 TOML config loading, structlog logging framework with the run-ID convention, NFR-005 purity enforcement wired before any transform exists, §16 license record.
- **MS-1 Core workflow implemented** (2026-07-06, PR #6): `docmend scan PATH` produces the schema-validated DR-001 inventory — provably read-only, include/exclude filters, single-pass classification (BOM/UTF-8 facts, newline census, hard-link and symlink records), single-file PATH first-class. The four OQ-004 artifact JSON Schemas are pinned in `src/docmend/schemas/` (adr-0005). 125 tests, 97% branch coverage.
- **MS-2 Domain logic implemented** (2026-07-06, PR #7): `docmend plan PATH` produces the schema-validated DR-002 plan — fact-gate ladder (filters, hard-link, oversize, encoding gates), content pass (decode checks, transform prediction, EC-005 shrink-invariant guard, collisions, C.4 decision provenance, per-action UUIDv7 identities). Pure transforms (FR-007–FR-009: encoding, newline, whitespace) live behind the adr-0016 file-class dispatch, enforced NFR-005-pure. `charset-normalizer` legacy detection rung populates DR-001 at scan. Initial weird-document corpus + regression harness, including the three-axis encoding-floor boundary matrix; RQ-022 MS-2 calibration checkpoint executed — floor stays 20. Post-merge housekeeping (same day) cleared every deferred review minor: enum drift guard, purity-fixture hardening, defensive decode catch, symlink filter labeling, stale-size fast-fail, plan-shorthand exit coherence, byte-exact-fixture guards (.prettierignore + markdownlint ignore). 345 tests, 98% coverage.

## Current State

- The tool can inventory and plan but not yet modify: `scan`/`plan` are live; `apply`/`verify`/`restore` land in MS-3/MS-4 per the binding §19 milestone ladder.
- Spec is `status: draft`, revision 0.15. One open question: OQ-034 (default artifact/log location — non-blocking, implementation proceeding on the `./.docmend/` assumption; owner sign-off wanted by MS-3).
- Next milestone: **MS-3 User and admin experience** — writer layer (atomic writes, backups, manifest, collision policy, safety gate; FR-003–FR-006/FR-011/NFR-002), `apply` with dry-run default and readable reports, and the restore-from-manifest drill.

## Recent Changes

- [2026-07-06] MS-2: plan command + planning layer + pure transforms + charset-normalizer legacy detection + weird-document corpus; RQ-022 calibration checkpoint (floor stays 20); spec rev 0.15.
- [2026-07-06] MS-1: scan command + discovery layer + pinned artifact schemas; new OQ-034; dependency-review purl exemption for rfc3987-syntax (false GPL detection, verified MIT).
- [2026-07-06] MS-0: CLI entry point, strict config, logging framework, purity enforcement; dependency licenses recorded.
- [2026-07-06] Branch/CI/CD workflow adopted (ADR-0017); third consistency audit brought all four spec gates green (spec v0.12).
- [2026-07-05..06] Spec authored to implementation-ready: decision backlog RQ-001..033, ADRs 0001–0016, gap register dispositioned (detail: `docs/handoff/sessions/2026-07.md`).

## Notes For The Builder

- Read `docs/specs/docmend.md` (Appendix B) before proposing any implementation — it is a binding Agent Implementation Contract, not just background.
- Milestone order (spec §19) is binding: do not build a later milestone on an unproven earlier one.
- Run `scripts/check_traceability.py` after any edit to the spec or the question files; CI enforces it.
- All changes go `dev` → PR → `main`; direct pushes to `dev` do not run CI — run the local gate first (see README).
