# Handoff State

## Current focus

- Safety-core Plans A-D and DMR-08 Tasks 1-2 are implemented on `dev`. Task 2 removed `parallel.*`, rejects legacy tables before scanning, emits plan schema 2.0 without the legacy snapshot, and rejects plan 1.x before validation, gates, locks, or mutation. NEXT: continue inline with Task 3 — add the strict public-safe scale-evidence and reference-environment contracts.
- Current gate: 991 passed, one expected opt-in scale skip, 95% branch coverage, and no known dependency vulnerabilities.
- The real-library write rollout stays paused behind the remaining remediation (spec §18.4); `main` stays at v1.0.2 until sub-projects 2-4 and the v2.0.0 release PR complete.
- Keep post-v1 changes within approved spec/ADR change control and run the full local gate before integration or push.

## Active incidents

- None.
