# Research Index

Generated index of `docmend` research reports. Last rebuilt 2026-07-05 from the gap-analysis workflow output. The queue view with reconciliation status lives in [`../deep-research-queue.md`](../deep-research-queue.md).

| Report | Topic | Feeds |
| --- | --- | --- |
| [`managing-pandoc-markdown-and-strict-yaml-frontmatter.md`](managing-pandoc-markdown-and-strict-yaml-frontmatter.md) | Pandoc Markdown, CommonMark body constraints, strict YAML frontmatter, schema validation | spec §9 / C-006 / FR-016 / DR-005; OQ-013 |
| [`self-hosted-corpus-storage-options.md`](self-hosted-corpus-storage-options.md) | Storage options for a large private document corpus | spec §18.6; OQ-008 |
| [`python-library-research.md`](python-library-research.md) | Whole-stack Python dependency posture (runtime + dev/test) — broad companion to the targeted per-library reports | OQ-017, OQ-018, OQ-019; §8.6 |
| [`encoding-detection-benchmark.md`](encoding-detection-benchmark.md) | Encoding detection at corpus scale: detector choice, confidence semantics, threshold | OQ-001 (GAP-42, GAP-43, GAP-44) |
| [`python-314-concurrency-model.md`](python-314-concurrency-model.md) | Concurrency model for a CPU-bound file pipeline on Python 3.14 | OQ-010 (GAP-22, GAP-54) |
| [`python-314-wheel-readiness.md`](python-314-wheel-readiness.md) | Python 3.14 wheel readiness for the approved dependency set | gap-analysis.md (GAP-60) |
| [`append-safe-manifest-format.md`](append-safe-manifest-format.md) | Crash-safe, append-safe on-disk manifest representation | OQ-004 (GAP-24, GAP-30) |
| [`atomic-write-filesystem-semantics.md`](atomic-write-filesystem-semantics.md) | Atomic-replace and directory-fsync guarantees across filesystems | gap-analysis.md (GAP-41) |
| [`path-containment-toctou.md`](path-containment-toctou.md) | Path-containment algorithm and TOCTOU symlink-race mitigation | OQ-004 (GAP-40) |
| [`stable-document-id-scheme.md`](stable-document-id-scheme.md) | Stable document ID scheme surviving renames and full rewrites | OQ-002 (GAP-26) |
| [`json-schema-versioning-migration.md`](json-schema-versioning-migration.md) | JSON Schema versioning and migration policy | OQ-004 (GAP-29) |
| [`json-schema-validator-library.md`](json-schema-validator-library.md) | JSON Schema validator library selection at scale | OQ-004 (GAP-58) |
| [`unicode-normalization-policy.md`](unicode-normalization-policy.md) | Unicode normalization-form policy for content and filenames | gap-analysis.md (GAP-45) |
| [`structured-logging-library.md`](structured-logging-library.md) | Structured logging library and format for a long-running batch CLI | gap-analysis.md (GAP-19) |
| [`batch-throughput-and-capacity.md`](batch-throughput-and-capacity.md) | Throughput, memory, disk-overhead, and progress-reporting budget for a 100k-file pass | OQ-010 (GAP-20, GAP-38, GAP-54) |
| [`synthetic-corpus-generation.md`](synthetic-corpus-generation.md) | Synthetic corpus generation and public-safe anonymization of real anomalies | gap-analysis.md (GAP-49) |
| [`property-based-testing-hypothesis.md`](property-based-testing-hypothesis.md) | Property-based testing library for transform purity and edge cases | gap-analysis.md (GAP-50) |
| [`architecture-and-traceability-enforcement.md`](architecture-and-traceability-enforcement.md) | Mechanical enforcement of architecture invariants and requirement traceability | OQ-004 (GAP-52, GAP-53) |
| [`license-compliance-tooling.md`](license-compliance-tooling.md) | Dependency license-scanning tooling and policy for a uv/PEP 621 project | gap-analysis.md (GAP-59) |
| [`batch-curation-review-workflow.md`](batch-curation-review-workflow.md) | Report-driven review workflow for a headless batch curation tool | gap-analysis.md (GAP-61) |
| [`per-file-watchdog-timeout.md`](per-file-watchdog-timeout.md) | Per-file watchdog/timeout for pathological inputs in a batch pipeline | gap-analysis.md (GAP-63) |
| [`combinatorial-safety-gate-testing.md`](combinatorial-safety-gate-testing.md) | Combinatorial testing strategy for the multi-check safety gate | OQ-005 (GAP-39) |
| [`restore-from-manifest-design.md`](restore-from-manifest-design.md) | Restore-from-manifest tooling and drill design | OQ-005 (GAP-33) |
| [`safe-yaml-loading.md`](safe-yaml-loading.md) | Safe YAML loading and hardening for parsing legacy frontmatter | gap-analysis.md (GAP-65) |
| [`backup-integrity-verification.md`](backup-integrity-verification.md) | Backup integrity verification and preservation-strategy proof | OQ-005 (GAP-34, GAP-35) |
