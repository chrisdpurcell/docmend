# Project Status

## Current snapshot

- docmend v1.0.2 is released with the complete scan, plan, apply, restore, resume, and verify pipeline.
- The approved SPEC-VHHB revision 0.25 and ADRs 0001-0018 govern post-v1 changes; the decision backlog is empty.
- The current baseline is 619 tests plus an opt-in 100k-file scale test, with 97% coverage.
- The repository workflow is `dev` to pull request to protected `main`; releases are signed `vX.Y.Z` tags with sdist and wheel artifacts.
- The next substantive work is the owner's staged real-library rollout and synthetic weird-corpus expansion from observed anomalies.
- Agent Handoff v1 provides one shared repo-local SessionStart runtime for the dual Claude/Codex profile.
