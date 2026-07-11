# Handoff State

## Current focus

- Safety-core Plans A-D are implemented on `dev`; Plan D was locally fast-forward merged at `f906e9e`. Full gate: 983 passed, one opt-in scale skip, 95% branch coverage. `dev` is ahead of `origin/dev`; NEXT: push only when authorized, then begin sub-project 2 (scale/DMR-08).
- The real-library write rollout stays paused behind the remaining remediation (spec §18.4); `main` stays at v1.0.2 until sub-projects 2-4 and the v2.0.0 release PR complete.
- Keep post-v1 changes within approved spec/ADR change control and run the full local gate before integration or push.

## Active incidents

- None.
