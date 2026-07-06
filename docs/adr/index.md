# ADR Index

Sequential index of docmend's Architecture Decision Records. See [README.md](README.md) for conventions and [adr-backlog.md](adr-backlog.md) for candidates not yet written up.

| ADR | Title | Status | Date | Sources |
| --- | --- | --- | --- | --- |
| [0001](adr-0001-no-markdown-frontmatter-standard.md) | Do not adopt the Markdown Frontmatter Standard | accepted | 2026-07-05 | D-008 |
| [0002](adr-0002-layered-pipeline-isolated-writer.md) | Layered pipeline with an isolated writer | accepted | 2026-07-05 | D-003, D-006 |
| [0003](adr-0003-in-place-mutation-output-model.md) | In-place mutation as the v1 output model | accepted | 2026-07-05 | RQ-013, D-004 |
| [0004](adr-0004-apply-safety-gate-and-preservation.md) | Apply safety gate and preservation posture | accepted | 2026-07-05 | RQ-005, RQ-007 |
| [0005](adr-0005-durable-artifact-schema-contract.md) | Durable artifact schema contract | accepted | 2026-07-05 | RQ-004 |

## Candidates not yet written

Tracked with scoring and rationale in [adr-backlog.md](adr-backlog.md):

- **Tier 2:** 0006 resume & recovery model · 0007 concurrency primitive · 0008 stable document identity · 0009 encoding dual-gate.
- **Tier 3:** 0010 pluggable policy seams · 0011 frontmatter scope/split · 0012 verify + exit-code taxonomy · 0013 dependency selection.
