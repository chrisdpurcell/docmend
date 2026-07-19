# Handoff State

## Current focus

- v2.0.1 is released: the 2026-07-19 comprehensive-review remediation (26 findings fixed, none Critical/High; report at `docs/fable-review/2026-07-19-docmend-review.md`) on top of the complete v2.0.0 pipeline. NEXT: support the owner's staged real-library rollout under spec §18.4.
- Current gate: 1,728 passed with no skips on a non-root runner, 89% branch coverage, and no known dependency vulnerabilities.
- Two review Open Questions await owner decisions: OQ-1 (frontmatter semantics for non-mapping `---` fence blocks) and OQ-2 (whether reference-mismatched scale runs may be failed by binding thresholds) — tradeoffs recorded in the review report.
- The real-library write rollout remains owner-controlled under the safeguards in spec §18.4.
- Keep post-v1 changes within approved spec/ADR change control and run the full local gate before integration or push.

## Active incidents

- None.
