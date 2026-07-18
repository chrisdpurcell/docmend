# ADR Index

Sequential index of docmend's Architecture Decision Records. See [README.md](README.md) for conventions and [adr-backlog.md](adr-backlog.md) for candidates not yet written up.

| ADR | Title | Status | Date | Sources |
| --- | --- | --- | --- | --- |
| [0001](adr-0001-no-markdown-frontmatter-standard.md) | Do not adopt the Markdown Frontmatter Standard | accepted | 2026-07-05 | D-008 |
| [0002](adr-0002-layered-pipeline-isolated-writer.md) | Layered pipeline with an isolated writer | accepted | 2026-07-05 | D-003, D-006 |
| [0003](adr-0003-in-place-mutation-output-model.md) | In-place mutation as the v1 output model | accepted | 2026-07-05 | RQ-013, D-004 |
| [0004](adr-0004-apply-safety-gate-and-preservation.md) | Apply safety gate and preservation posture | accepted | 2026-07-05 | RQ-005, RQ-007 |
| [0005](adr-0005-durable-artifact-schema-contract.md) | Durable artifact schema contract | accepted | 2026-07-05 | RQ-004 |
| [0006](adr-0006-resume-and-recovery-model.md) | Resume and recovery model | superseded by [0019](adr-0019-manifest-2-recovery-model.md) | 2026-07-05 | RQ-003 |
| [0007](adr-0007-concurrency-primitive-process-pool.md) | CPU-bound concurrency primitive | superseded by [0022](adr-0022-sequential-million-file-scale-contract.md) | 2026-07-05 | RQ-016 |
| [0008](adr-0008-stable-document-identity.md) | Stable document identity | accepted | 2026-07-05 | RQ-002 |
| [0009](adr-0009-encoding-detection-dual-skip-gate.md) | Encoding detection and dual skip-gate | accepted | 2026-07-05 | RQ-022, D-002 |
| [0010](adr-0010-pluggable-policy-seams.md) | Design-for-pluggable policy seams | accepted | 2026-07-05 | RQ-010, D-009 |
| [0011](adr-0011-frontmatter-optional-minimal-split.md) | Frontmatter — optional, minimal, mechanical/semantic split | accepted | 2026-07-05 | RQ-008, RQ-014, D-001, D-007 |
| [0012](adr-0012-verify-semantics-exit-code-taxonomy.md) | verify semantics and tool-wide exit-code taxonomy | accepted | 2026-07-05 | RQ-006 |
| [0013](adr-0013-v1-dependency-selection.md) | v1 runtime and dev dependency selection | accepted | 2026-07-05 | RQ-017–021 |
| [0014](adr-0014-tool-first-product-scope.md) | Tool-first product scope — scale-flexibility binding | accepted | 2026-07-06 | RQ-024 |
| [0015](adr-0015-test-corpus-and-anonymization.md) | Two-corpus test architecture and anonymization | accepted | 2026-07-06 | RQ-032 |
| [0016](adr-0016-mechanical-transform-boundary.md) | The mechanical-transform boundary | accepted | 2026-07-06 | RQ-025, RQ-030, RQ-031 |
| [0017](adr-0017-branch-and-ci-cd-workflow.md) | Branch strategy, protection, release, and CI/CD workflow | accepted | 2026-07-06 | hw-radar port |
| [0018](adr-0018-doc-processing-repository-boundary.md) | Doc Processing repository boundary | accepted | 2026-07-07 | cross-repo alignment review |
| [0019](adr-0019-manifest-2-recovery-model.md) | Manifest 2.0 recovery model | accepted | 2026-07-10 | 2026-07-10 review DMR-03/04; supersedes 0006 |
| [0020](adr-0020-commit-boundary-object-identity.md) | Commit-boundary object identity | accepted | 2026-07-10 | 2026-07-10 review DMR-06/07 |
| [0021](adr-0021-artifact-destination-guard.md) | Artifact destination guard | accepted | 2026-07-10 | 2026-07-10 review DMR-02 |
| [0022](adr-0022-sequential-million-file-scale-contract.md) | Sequential million-file scale contract | accepted | 2026-07-11 | RQ-037; DMR-08 |

## Candidates not yet written

Tracked with scoring and rationale in [adr-backlog.md](adr-backlog.md): all candidates from both review passes (2026-07-05 over D-001..009/RQ-001..023; 2026-07-06 over RQ-024..033) are now written up. ADR 0022 records the later DMR-08/OQ-037 scale decision and supersedes ADR 0007. The only remaining candidates are those **deliberately deferred until their downstream work is scheduled** — chiefly RQ-023's review-artifact exposure ADR (blocked on WH-002/WH-005) — plus the items in the backlog's "Deliberately not ADRs" table.
