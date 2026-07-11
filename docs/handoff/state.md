# Handoff State

## Current focus

- Safety-core Plans A/B are implemented on `dev`. Plan C is in progress on `plan-c-commit-boundary`: Tasks 1-4 are committed (`571015c..cb32240`) and the full gate is green at 850 tests/97%. NEXT: Task 5 (`rename_and_rewrite` windows + checked rollback), then Tasks 6-12 in order; Plan D follows.
- Plan C settled rules: terminal `failed` requires proven pre-action state; never remove a possible last surviving copy; replacements stage first and re-authorize at commit; write authority comes only from sealed factories that own canonical lock/artifact namespaces and carry factory-read plan/config/effective options or a validated restore chain; resume evidence and artifact identities are factory-derived; immutability reaches nested leaves; restore's carve-out uses recorded `effective_excludes`. Preview and mutation engines are structurally separate.
- Landed on `dev` this session besides the plan: `8c2d5f4` fixes a live Plan B defect — the chain validator rejected the producer's own pre-mutation standalone `failed` records, making any run with an ordinary staging/backup failure unresumable/unrestorable (regressions in `tests/test_manifest_chain.py` + `tests/test_resume.py`; design lifecycle sentence disambiguated). Gate: 798 passed, 97% branch coverage.
- Plan B facts still current: manifest 2.0 is a CLEAN BREAK; shared wire types stay dependency-neutral; the adjudication table is shared by resume/restore. Plan C now captures apply source/overwrite identities through descriptors and checks rewrite/pure-rename commits; restore/adjudication migration remains in Tasks 5-7.
- The real-library write rollout stays paused behind the remediation (spec §18.4 precondition); `main` stays at v1.0.2 until the v2.0.0 release PR carries all four plans plus sub-projects 2-4.
- Keep post-v1 behavior change-controlled through the approved spec and ADR process; run the local gate before pushing `dev`. Plan docs must pass markdownlint + prettier (the reviewer checks); plan revisions are full self-contained rewrites, never references to superseded text.

## Active incidents

- None.
