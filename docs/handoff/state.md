# Handoff State

## Current focus

- Safety-core Plans A (DMR-01/02) and B (DMR-03/04) are implemented on `dev`. **Plan C is OWNER-APPROVED after 12 review rounds** (`docs/superpowers/plans/2026-07-11-safety-core-c-commit-boundary.md`): both final independent audits returned APPROVE, all findings are closed, and the CR-006 wire-model checkpoint is satisfied. NEXT: implement its 12 TDD tasks in order, beginning with Task 1; then Plan D (DMR-05), sub-projects 2-4, and the v2.0.0 release.
- Plan C settled rules: terminal `failed` requires proven pre-action state; never remove a possible last surviving copy; replacements stage first and re-authorize at commit; write authority comes only from sealed factories that own canonical lock/artifact namespaces and carry factory-read plan/config/effective options or a validated restore chain; resume evidence and artifact identities are factory-derived; immutability reaches nested leaves; restore's carve-out uses recorded `effective_excludes`. Preview and mutation engines are structurally separate.
- Landed on `dev` this session besides the plan: `8c2d5f4` fixes a live Plan B defect — the chain validator rejected the producer's own pre-mutation standalone `failed` records, making any run with an ordinary staging/backup failure unresumable/unrestorable (regressions in `tests/test_manifest_chain.py` + `tests/test_resume.py`; design lifecycle sentence disambiguated). Gate: 798 passed, 97% branch coverage.
- Plan B facts still current: manifest 2.0 is a CLEAN BREAK (no 1.x read path); shared wire types in dependency-neutral `docmend/lineage.py` (docstring is a binding import contract); the crash-state adjudication table lives in `writer/adjudicate.py`, consumed by resume and restore; identity capture stays `os.stat`-based until Plan C lands.
- The real-library write rollout stays paused behind the remediation (spec §18.4 precondition); `main` stays at v1.0.2 until the v2.0.0 release PR carries all four plans plus sub-projects 2-4.
- Keep post-v1 behavior change-controlled through the approved spec and ADR process; run the local gate before pushing `dev`. Plan docs must pass markdownlint + prettier (the reviewer checks); plan revisions are full self-contained rewrites, never references to superseded text.

## Active incidents

- None.
