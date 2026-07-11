# Handoff State

## Current focus

- Safety-core Plans A-C are implemented on `dev`; Plan C was locally fast-forward merged at `ca59cdd` and its feature worktree/branch were removed. Full gate: 891 passed, one opt-in scale skip, 95% coverage. `dev` is ahead of `origin/dev`; NEXT: push when authorized, then implement Plan D (verify redesign, DMR-05).
- The real-library write rollout stays paused behind the remediation (spec §18.4 precondition); `main` stays at v1.0.2 until the v2.0.0 release PR carries all four plans plus sub-projects 2-4.
- Keep post-v1 behavior change-controlled through the approved spec and ADR process; run the local gate before pushing `dev`. Plan docs must pass markdownlint + prettier (the reviewer checks); plan revisions are full self-contained rewrites, never references to superseded text.

## Active incidents

- None.
