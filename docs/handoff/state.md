# Handoff State

## Current focus

- Safety-core Plans A/B are implemented on `dev`; Plan C is complete on `plan-c-commit-boundary` (`571015c..2b7ed0d`). Full gate: 891 passed, one opt-in scale skip, 95% coverage. NEXT: integrate Plan C through the repo's `dev`→PR workflow, then implement Plan D (verify redesign, DMR-05).
- The real-library write rollout stays paused behind the remediation (spec §18.4 precondition); `main` stays at v1.0.2 until the v2.0.0 release PR carries all four plans plus sub-projects 2-4.
- Keep post-v1 behavior change-controlled through the approved spec and ADR process; run the local gate before pushing `dev`. Plan docs must pass markdownlint + prettier (the reviewer checks); plan revisions are full self-contained rewrites, never references to superseded text.

## Active incidents

- None.
