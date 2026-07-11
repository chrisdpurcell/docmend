# Million-File Scale and Resource Contract Design

Approved design for closing DMR-08 from the [comprehensive review synthesis](../../codex-reviews/2026-07-10-2034-comprehensive-review-synthesis.md) before docmend v2.0.0. This document replaces the historical 100,000-file acceptance floor with a one-million-file release qualification and reconciles the binding specification with the implementation's actual whole-run artifact model.

Owner decisions recorded in the design conversation:

- v2.0.0 shall qualify the complete pipeline at 1,000,000 files, not merely 100,000 files.
- v2.0.0 shall use a bounded-linear metadata contract and supported sequential execution. Unsupported parallel settings shall be rejected, never accepted as inert configuration.
- Smaller tiers shall protect pull requests and scheduled development; the full one-million-file run is a release qualification and a regression gate after scale-sensitive changes.

This is the design-stage artifact. The binding change-control work is a new SPEC-VHHB revision, a settled OQ-037 recording the owner decision, and a concurrency ADR superseding `adr-0007-concurrency-primitive-process-pool` before implementation begins.

## Problem

The current NFR-001 contract and its evidence cannot both be true:

- NFR-001 requires corpus-size-independent memory, no whole-corpus in-memory structures, and working parallel execution.
- DR-001 through DR-003 define inventory, plan, and report as whole-run artifacts. The implementation materializes their records and the global indexes required for collision detection, lifecycle reduction, and exactly-once verification.
- The scale test acknowledges that memory grows with file count and allows `64 MiB + 10 KiB/file`.
- `parallel.*` configuration is parsed but has no runtime consumer.
- The existing scale test calls library APIs in one process, suppresses the normal logging path, spot-checks output, and stops before the binding `verify --plan` workflow.
- The 100 MiB per-file default has no demonstrated working-set envelope; file count and file size are independent resource dimensions.

The historical 100,000-file run remains useful evidence, but it is not a product ceiling and cannot close DMR-08 for v2.0.0.

## Contract

### Corpus count

The supported scale range is one file through 1,000,000 files on one local POSIX machine. The complete installed-CLI workflow shall qualify at the upper bound:

```text
scan -> plan -> apply --write -> verify --plan
```

The qualification corpus is deterministic, generated at run time, synthetic, and never committed. It includes actions, clean no-ops, classified skips, renames, rewrites, encoding conversion, collision-free nested paths, and the current Manifest/Report 2.0 evidence path.

### Memory model

Whole-run artifact metadata may grow linearly with file count. Per-file body content may not accumulate across records. The release contract is:

- peak resident memory at 1,000,000 files is at most 8 GiB on the reference 16 GiB Linux/POSIX qualification environment;
- the fitted incremental peak-memory slope from the measured 10,000, 100,000, and 1,000,000-file tiers is at most 6 KiB per file;
- the 1,000,000-file observation may not exceed the linear prediction from the smaller tiers by more than 20%; and
- each CLI stage runs in a separate process, so a prior stage's in-memory artifact model cannot inflate the next stage's measured peak.

Both peak RSS and Python allocation peak are recorded. RSS is the binding operator-facing ceiling; allocation data diagnoses Python-object regressions. The measured slope and peak become a versioned, sanitized baseline artifact, not an unrecorded console anecdote.

This contract deliberately does not claim memory independent of corpus size. Inventory, plan, report, and lifecycle records are durable per-file evidence; bounded linear growth is the honest contract for the v2 artifact architecture.

### Individual file size

Corpus cardinality and maximum individual file size are separate acceptance axes. A deterministic size matrix exercises planning, transformation, backup, apply, and verification with representative UTF-8 and legacy-encoding inputs, with and without tool backups.

The default `limits.max_file_size_mib` remains 100 MiB only if the measured peak RSS for one maximum-sized file stays within 2 GiB and the complete operation remains below the per-file watchdog budget on the qualification machine. Otherwise, the implementation derives the supported default from the largest measured size satisfying both bounds and synchronizes the config, specification, README, and tests in the same change. No benchmark result is silently converted into a larger limit.

### Execution model

v2.0.0 supports sequential execution. Configuration may retain the `parallel.*` namespace as a reserved compatibility surface, but only the sequential values are valid:

- `parallel.enabled = false`;
- `parallel.model = "sequential"`; and
- `parallel.workers = 1`.

Any request for process, thread, interpreter, or multiple-worker execution is an input error with a message that parallel execution is not implemented in this release. No setting may parse successfully and then be ignored.

`ProcessPoolExecutor` remains a documented future option, not a v2.0.0 feature. Reopening it requires profiling evidence that sequential execution misses the release's practicality target, a new approved design, equivalence tests, parent-only shared-artifact writes, worker-failure isolation, and a hard watchdog design. The accepted ADR 0007 is superseded because it claims a supported process mode that never shipped.

### Watchdog

The v2.0.0 sequential engine retains the current cooperative SIGALRM watchdog and documents its actual boundary: it interrupts Python-level discovery, detection, and transform work on the main thread but cannot guarantee termination of a stuck native call. FR-019, ERR-009, operator documentation, and DEV-002 shall use that exact language.

A hard per-file process boundary is coupled to future worker-process support. It is not simulated with a thread timeout or a fresh process per million-file record. Safety claims must describe what the shipped engine proves.

## Qualification Architecture

### Harness

The scale harness invokes the built wheel in isolated subprocesses. It does not import docmend from the checkout. Each stage writes and then rereads the real durable artifact used by the next stage. Apply uses a synthetic external preservation declaration for the cardinality lane and a separate smaller lane with tool backups; both are followed by plan-aware verification.

The harness captures, per stage:

- exact commit, package version, artifact schema versions, Python version, and dependency lock hash;
- file count and total corpus bytes;
- elapsed time, files per second, and bytes per second;
- peak RSS and Python allocation peak where available;
- inventory, plan, report, manifest, verify-report, and log sizes;
- action, skip, failure, not-attempted, and verified totals; and
- filesystem type plus cold/warm-cache classification, without hostnames, usernames, absolute corpus paths, or document content.

The output is a versioned JSON evidence document validated by a repository schema. A failed or incomplete run never overwrites the last accepted baseline.

### Test tiers

| Tier | Trigger | Corpus | Purpose |
| --- | --- | --: | --- |
| Pull request | Default Python gate | 1,000 files | Fast conservation, artifact, and gross memory-regression guard. |
| Scheduled/manual | Weekly and `workflow_dispatch` | 100,000 files | Full installed-CLI workflow, trend comparison, and intermediate slope point. |
| Release qualification | Exact v2.0.0 candidate and scale-sensitive changes | 1,000,000 files | Binding upper-bound acceptance and published release evidence. |
| File-size matrix | Manual and before limit changes | Derived size cases through the configured maximum | Per-file working-set, timeout, and backup envelope. |

The release workflow may publish only the candidate commit whose complete gate and one-million-file evidence both passed. Sub-project 3 (DMR-09) owns the exact workflow binding and provenance mechanism; this design owns the evidence format and qualification command.

### Correctness

Sampling is insufficient at the release tier. The qualification reconciles every record through artifact totals and `verify --plan` exactly-once coverage. It additionally selects deterministic boundary samples from every recipe class for byte/hash/encoding checks. The invariant is not merely that the command completed: every input is accounted for as exactly one action, clean no-op, or classified skip, and every plan action has exactly one certified terminal outcome.

## Resource Observability

Scale runs need content-free liveness signals. Every long-running stage emits:

- a start event naming the stage and input count when known;
- a heartbeat at least every 30 seconds containing processed count, elapsed time, rate, and aggregate error/skip counts;
- a terminal event containing final totals, elapsed time, artifact sizes, and peak RSS when supported; and
- an explicit incomplete terminal event on handled failure.

Heartbeat and terminal events never contain document bodies. Path-bearing per-file logs remain confidential runtime artifacts and receive the permission, redaction, placement, retention, and purge treatment owned by sub-project 4.

Disk preflight accounts per filesystem rather than independently double counting destinations on the same mount. It includes tool backups, the largest simultaneous staging requirement, manifest/report/verify-report growth, and the configured log budget. Qualification records actual artifact growth so the preflight coefficients are evidence-based.

## Error Handling

- Unsupported parallel configuration is exit 2 (input error), before scanning.
- A scale threshold miss fails the qualification and preserves its evidence; it never weakens the threshold automatically.
- Resource measurement unavailable on a platform is explicit. The release qualification must run where binding RSS measurement is supported.
- Corpus generation or disk-capacity failure is an incomplete qualification, not a product correctness failure; it still exits non-zero and records the environmental cause.
- Any conservation, artifact-validation, or `verify --plan` discrepancy is a correctness failure regardless of performance results.

## Testing

Implementation follows TDD and adds:

- configuration tests proving every unsupported parallel shape is rejected and sequential/default shapes are accepted;
- scale-harness unit tests for sanitized evidence, threshold evaluation, incomplete runs, and baseline non-overwrite;
- installed-wheel end-to-end tests for the 1,000-file PR tier;
- multi-point slope tests using deterministic synthetic measurements so the threshold math is testable without allocating a million files in unit tests;
- a real 100,000-file scheduled qualification;
- a real 1,000,000-file release qualification;
- file-size working-set tests covering planning, apply, tool backups, and verification;
- heartbeat/terminal-event tests using a fake clock and aggregate-only event assertions;
- disk-preflight tests for shared and distinct filesystems; and
- regressions proving manifest 2.0 line counts, report totals, plan coverage, and verify-report publication at scale.

The full local Python and documentation gates remain mandatory. The scale evidence supplements them; it never substitutes for correctness, typing, coverage, dependency, specification, or documentation validation.

## Change-Control Follow-Through

Before implementation:

1. Add and settle OQ-037 as the canonical owner decision for the one-million-file, bounded-linear, sequential v2.0.0 contract; preserve the older resolved questions as historical inputs rather than silently rewriting their decisions.
2. Revise SPEC-VHHB: NFR-001, G-006, §3.1, §7.3/IR-006, §8.1/§8.5, §12.1/ERR-009, §14, §17.2/§17.3, §18.2/§18.5, §19 MS-5, §20, and DEV-002, with cross-references from the superseded scale/concurrency assumptions to OQ-037.
3. Add a new accepted ADR superseding `adr-0007` with the sequential v2.0.0 contract, reserved/rejected parallel surface, and evidence-triggered reopen criteria. Update reciprocal metadata, the ADR index, and backlog.
4. Specify the scale-evidence artifact's identity, validation, retention, and public-safe fields in SPEC-VHHB; implement its JSON Schema as the first TDD slice after change control.
5. Regress NFR-001 to Partial until the one-million-file qualification passes; do not carry the historical 100,000-file result forward as v2 evidence.
6. Update `docs/TODO.md`, `docs/STATUS.md`, and handoff plan pointers so DMR-08 remains visibly release-blocking through qualification.

Sub-project 2 ends only when the exact candidate implementation passes the full correctness gate, the 100,000-file scheduled tier, the one-million-file release qualification, and the file-size envelope; the accepted evidence is recorded without private paths or corpus content.
