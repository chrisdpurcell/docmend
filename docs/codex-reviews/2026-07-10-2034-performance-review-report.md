# Performance Review

## Review Metadata

- review_type: `performance-review`
- reviewed_at: `2026-07-10`
- repo_path: `.`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- release_baseline: `v1.0.2` (`9b0641bf3250bd3ba1b351609935612bdf8a3d40`)
- baseline_comparison: `v1.0.2..HEAD` changes handoff and agent configuration only; no runtime source changed after the release tag.
- working_tree_state: `dirty` before review (`AGENTS.md` modified; `docs/codex-reviews/` untracked). Those pre-existing changes were not edited.
- detected_frameworks_and_runtimes: Python `>=3.14`; Typer/Rich CLI; Pydantic v2; JSON Schema Draft 2020-12; structlog; charset-normalizer; ruamel.yaml; local POSIX filesystem processing.
- request_or_interactive_surfaces_inspected: `scan`, `plan`, `apply`, `restore`, and `verify`; no HTTP/API request path exists.
- startup_cold_paths_inspected: CLI import/config loading, logging setup, schema loading and validator compilation, artifact parsing.
- background_or_batch_surfaces_inspected: the full scan -> plan -> apply -> verify/restore pipeline; no daemon, scheduler, queue, or long-running worker service exists.
- data_access_or_query_heavy_surfaces_inspected: directory walk/stat, document reads/hashes, JSON artifact read/write, manifest NDJSON read/write, backup verification, verify reconciliation.
- caching_or_memoization_surfaces_inspected: cached JSON Schema validators; no remote/data cache is needed for this repo.
- asset_bundle_or_render_surfaces_inspected: not needed for this repo; no frontend or delivered asset bundle exists.
- concurrency_or_parallelism_surfaces_inspected: sequential engines, run lock, SIGALRM watchdog, accepted `parallel.*` configuration, ADR-0007.
- performance_budget_or_regression_guardrail_artifacts_reviewed: spec NFR-001/FR-019, `tests/test_scale.py`, ADR-0007, `docs/research/batch-throughput-and-capacity.md`, CI workflows.
- benchmark_profiling_or_load_test_artifacts_reviewed: checked-in 100k scale result (358 s, 477.4 MiB traced peak), the opt-in scale harness, repository research spike, and focused measurements from this review.
- field_vs_lab_evidence_reviewed: lab-only synthetic results; no staged real-library rollout measurements exist yet.
- important_external_performance_artifacts_not_in_repo: actual corpus size/file-size/encoding distribution, storage and backup media, cold/warm filesystem cache behavior, production run logs, peak RSS, and real-run tail timings.
- important_workload_unknowns: file-size percentiles, legacy-detection frequency, frontmatter prevalence, collision/backup rates, storage topology, target memory ceiling, acceptable wall clock, and supported concurrency.
- shared_research_used: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`.
- targeted_internet_follow_up: none; shared research and current repo-local performance research covered the review-specific guidance.
- focused_measurements:
  - synthetic UTF-8/CRLF files of 8, 16, and 32 MiB through scan+plan peaked at 85.7, 168.5, and 336.8 MiB traced heap, respectively.
  - a 5,000-file inventory used 12.4 MiB peak while scanning; its 2.6 MiB JSON artifact peaked at 15.2 MiB while writing and 18.4 MiB while reading.
- validation_limitations: focused probes used `/tmp` and tracemalloc; they establish allocation shape, not field throughput or RSS on the owner's eventual storage.
- report_schema_resolution: the workflow's referenced common `report-schema.md` describes orchestrator plans, not performance child reports; this report follows the performance workflow's required sections and issue fields.

## Performance Area Matrix

| Performance area | Relevance | Assessment | Findings |
| --- | --- | --- | --- |
| `latency-and-tail-behavior` | high | Per-file tails and total batch time matter; no percentile evidence exists. | ISSUE-002, ISSUE-006, ISSUE-007 |
| `throughput-and-capacity` | high | A 100k synthetic run completed, but parallel controls are inert and the baseline omits material work. | ISSUE-003, ISSUE-004 |
| `algorithmic-complexity-and-scaling` | high | Whole-corpus metadata is O(file count), contrary to the binding constant-memory criterion. | ISSUE-001 |
| `startup-cold-paths-and-initialization` | low | CLI/schema initialization is bounded and not shown to dominate. | none |
| `database-query-and-storage-efficiency` | not applicable | No database exists; filesystem efficiency is covered under network/storage I/O. | none |
| `caching-and-reuse` | medium | Schema validators are cached; verify does not reuse scan hashes/facts sufficiently. | ISSUE-005 |
| `serialization-parsing-and-payload-size` | high | Whole JSON artifacts are materialized and validated in memory. | ISSUE-001, ISSUE-004 |
| `concurrency-batching-and-backpressure` | high | Accepted parallel configuration has no runtime consumer. | ISSUE-003 |
| `degraded-dependency-and-load-shedding` | medium | The in-process watchdog is not a hard process-level kill boundary. | ISSUE-007 |
| `background-jobs-and-queue-throughput` | not applicable | No queue or background worker system exists. | none |
| `frontend-rendering-and-interactivity` | not applicable | No frontend exists. | none |
| `asset-delivery-and-bundle-size` | not applicable | No browser-delivered assets exist. | none |
| `memory-allocation-and-lifecycle` | critical | Corpus metadata and permitted large files both create material heap risk. | ISSUE-001, ISSUE-002 |
| `network-io-and-external-calls` | medium | No network calls; repeated local filesystem reads are material at corpus scale. | ISSUE-005 |
| `runtime-configuration-and-resource-limits` | high | `parallel.*` is misleading and the 100 MiB input ceiling is not a working-set ceiling. | ISSUE-002, ISSUE-003 |
| `field-vs-lab-measurement-quality` | high | Evidence is synthetic, single-machine, and not representative of the actual CLI lifecycle. | ISSUE-004, ISSUE-006 |
| `performance-observability-and-profiling` | high | No durable stage timing, rates, peak memory, tails, or heartbeat exists. | ISSUE-006 |
| `performance-budgets-and-regression-guardrails` | high | The only scale test is manually gated and asserts the wrong asymptotic property. | ISSUE-001, ISSUE-004 |
| `benchmarks-load-testing-and-budgets` | high | One checked-in scale point exists; no matrix, scheduled run, or trend history exists. | ISSUE-004 |
| `cross-cutting` | medium | The conventions library does not tell contributors how to preserve performance evidence. | ISSUE-008 |

## Severity Summary

| Severity | Count | Issue IDs                                             |
| -------- | ----: | ----------------------------------------------------- |
| critical |     0 | none                                                  |
| high     |     2 | ISSUE-001, ISSUE-002                                  |
| medium   |     5 | ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-006, ISSUE-007 |
| low      |     1 | ISSUE-008                                             |
| total    |     8 | ISSUE-001 through ISSUE-008                           |

## Findings

### ISSUE-001 — The completed bounded-memory claim is contradicted by O(file-count) state

- first_pass: `1`
- severity: `high`
- confidence: `high`
- performance_area: `algorithmic-complexity-and-scaling`
- issue_type: `algorithmic-scaling-gap`
- verification: `direct repo evidence plus focused measurement`
- evidence:
  - `docs/specs/docmend.md:355` requires memory independent of corpus size and no whole-corpus in-memory structures.
  - `src/docmend/discovery.py:222-235,425-475` accumulates all file, symlink, skip, and hard-link records and sorts them in memory.
  - `src/docmend/planning.py:189-229,392-413` retains `pending`, `actions`, `skips`, `claimed_targets`, and `inventory_paths`; apply retains every outcome at `src/docmend/writer/apply.py:615-704`.
  - `src/docmend/artifacts.py:105-188` materializes whole model dumps, JSON strings/objects, validated documents, and Pydantic models at artifact boundaries.
  - `tests/test_scale.py:39-51,194-205` explicitly permits `64 MiB + 10 KiB/file`; the checked-in 100k result is 477.4 MiB, and the allowed ceiling is about 1,040.6 MiB.
  - This review's 5,000-file probe measured 12.4 MiB scan peak, 15.2 MiB write peak, and 18.4 MiB read peak for a 2.6 MiB inventory artifact.
- risk: The implementation may be acceptable at the one measured 100k shape, but it does not satisfy the binding structural guarantee and can exhaust memory as file count or artifact richness rises. Marking NFR-001 complete hides the scaling boundary from release decisions.
- recommendation: Make an owner-level contract decision. Either revise NFR-001 and traceability to a measured O(file-count) metadata budget with an explicit supported maximum, or stream/spool inventory, plan, report, and manifest processing so a stage does not retain the whole corpus. Test at multiple counts and assert the chosen growth model.
- acceptance_evidence:
  - Requirement, architecture, and scale-test language state the same asymptotic bound.
  - Measurements at multiple file counts enforce either near-constant working memory or a declared per-record budget and maximum supported count.
  - CLI artifact parsing/serialization is included in the memory assertion.

### ISSUE-002 — A permitted large file amplifies to roughly ten times its size in traced heap

- first_pass: `2`
- severity: `high`
- confidence: `high`
- performance_area: `memory-allocation-and-lifecycle`
- issue_type: `memory-lifecycle-gap`
- verification: `direct repo evidence plus focused measurement`
- evidence:
  - `src/docmend/config.py:163-167` permits files through 100 MiB by default.
  - Planning reads the full bytes, decodes a full string, produces successive full-string transforms, and counts non-whitespace over original and transformed text (`src/docmend/planning.py:141-168,235-299`; `src/docmend/transform/dispatch.py:50-82`; `src/docmend/transform/whitespace.py:13-52`).
  - Apply repeats that materialization and adds UTF-8 payload bytes (`src/docmend/writer/apply.py:101-131,363-386`); tool backup verification can hold a reread while the caller still holds source/transformed data (`src/docmend/writer/backup.py:24-45`).
  - Focused scan+plan measurements were: 8 MiB input -> 85.7 MiB peak, 16 MiB -> 168.5 MiB, 32 MiB -> 336.8 MiB. The near-linear slope is direct; a roughly 1 GiB peak at the 100 MiB default is an inference, not a measured result.
  - `tests/test_scale.py` uses small generated documents and therefore does not exercise this per-file working-set boundary.
- risk: One valid file can create hundreds of MiB of transient allocations and plausibly exhaust a modest machine well below the configured input-size limit. The file-count scale test cannot detect this failure mode.
- recommendation: Define a per-file working-set budget, profile representative large files through plan/apply/verify with and without backups, and either lower/derive the input limit from that budget or redesign transforms/frontmatter inspection to reduce whole-text copies. Keep safety checks while avoiding simultaneous source, intermediate, output, and verification copies where possible.
- acceptance_evidence:
  - A size matrix through real CLI stages records peak RSS and tracemalloc for representative encodings/transforms.
  - The documented maximum file size stays within the supported memory envelope on the minimum supported machine.
  - A regression test covers large-file plan, apply, backup, and verify paths.

### ISSUE-003 — Accepted parallel settings are silent runtime no-ops

- first_pass: `1`
- severity: `medium`
- confidence: `high`
- performance_area: `concurrency-batching-and-backpressure`
- issue_type: `throughput-capacity-gap`
- verification: `direct repo evidence`
- evidence:
  - `src/docmend/config.py:139-149` accepts `enabled`, `model`, `workers`, `start_method`, `chunksize`, and `maxtasksperchild`.
  - ADR-0007 and spec sections 14/18.2 describe `ProcessPoolExecutor` + `forkserver` when enabled and claim confirmation in sequential and process modes.
  - Repository search finds no runtime read of `config.parallel`, no `ProcessPoolExecutor`, and no multiprocessing execution path; tests only validate configuration parsing.
  - `src/docmend/watchdog.py:6-14` and DEV-002 explicitly confirm that v1 never spawns the pool.
- risk: Operators can believe they enabled parallel/fault-isolated processing while receiving the same sequential engine. Throughput/capacity behavior cannot be tuned as documented, and the accepted ADR's claimed confirmation evidence is not trustworthy.
- recommendation: Either implement and profile the approved process path or reject `parallel.enabled=true` and non-default parallel settings as unsupported until it exists. Do not accept operational no-op settings.
- acceptance_evidence:
  - Every accepted parallel setting affects a measured runtime path, or validation rejects it clearly.
  - Process-mode tests prove configured start method, worker count/batching, parent-only artifact writing, watchdog behavior, and result equivalence.

### ISSUE-004 — The scale baseline is manually gated and omits material production costs

- first_pass: `4`
- severity: `medium`
- confidence: `high`
- performance_area: `benchmarks-load-testing-and-budgets`
- issue_type: `performance-regression-guardrail-gap`
- verification: `direct repo evidence`
- evidence:
  - `tests/test_scale.py:9-11,109-113` requires both the slow marker and `DOCMEND_SCALE=1`; `.github/workflows/check.yml` never opts in, and no scheduled/manual scale workflow exists.
  - The harness invokes library APIs in one process and does not write/read inventory, plan, or report artifacts, does not run full verify, and declares external preservation rather than testing tool backups (`tests/test_scale.py:135-192`).
  - It suppresses the per-file log path because roughly 200k rendered lines would swamp the run (`tests/test_scale.py:81-88`), although real CLI runs always configure the DEBUG-floored file sink (`src/docmend/observability.py:71-140`).
  - It spot-verifies about 25 actions instead of exercising the full verify command (`tests/test_scale.py:91-106`).
  - The sole checked-in point used tmpfs and tracemalloc overhead and reports no repeat variance, cold/warm distinction, RSS, percentile/outlier distribution, or trend artifact.
- risk: Performance regressions can merge unnoticed, and the 358 s/477.4 MiB result is not a defensible estimate of the real CLI, durable artifact, logging, backup, or verification workload.
- recommendation: Keep a cheap multi-size guard in normal CI and run a representative full CLI scale matrix on a scheduled/manual workflow. Preserve machine/filesystem, cold/warm state, corpus recipe, stage timings, throughput, peak RSS, allocation peak, percentiles/outliers, artifact/log sizes, correctness, and variance as comparable artifacts.
- acceptance_evidence:
  - CI enforces a fast scaling invariant on every change.
  - A scheduled/manual job exercises actual CLI stage boundaries, artifacts, logs, and verify; backup media is separately profiled where relevant.
  - Results are retained and compared against an explicit regression threshold.

### ISSUE-005 — Verify rereads outputs and fully splits Markdown bodies after scan already hashed them

- first_pass: `2`
- severity: `medium`
- confidence: `high`
- performance_area: `network-io-and-external-calls`
- issue_type: `query-storage-efficiency-gap`
- verification: `direct repo evidence`
- evidence:
  - Verify first calls `discovery.scan`, which reads and hashes every file (`src/docmend/cli.py:843-844`; `src/docmend/discovery.py:149-209`).
  - `check_frontmatter` then `read_text()`s every UTF-8 `.md` in full, including documents with no frontmatter (`src/docmend/verify.py:57-81`).
  - `extract_frontmatter` calls `text.splitlines()` over the entire document before it knows whether the first line is `---` (`src/docmend/frontmatter.py:53-62`).
  - Manifest reconciliation then `read_bytes()`s each applied target and hashes it again (`src/docmend/verify.py:88-114`) rather than using the inventory hash already computed in the same command.
- risk: On a >100k-file, multi-GiB corpus, verify adds avoidable file opens, full reads, string/list allocation, and hashing. The cost is worst for the expected post-conversion `.md` corpus and is absent from the scale baseline.
- recommendation: Build a path->scan-fact/hash index once for reconciliation and inspect only the bounded frontmatter prefix/block instead of splitting every body. Preserve explicit handling for files that changed between scan and reconciliation.
- acceptance_evidence:
  - A verify I/O test proves ordinary no-frontmatter Markdown is read once or only receives a bounded prefix read beyond scan.
  - Manifest reconciliation reuses same-run scan hashes while detecting scan/reconcile drift safely.
  - A full-corpus verify benchmark records reads/bytes, time, and peak memory.

### ISSUE-006 — Field runs expose no stage rates, tails, peak memory, or heartbeat

- first_pass: `4`
- severity: `medium`
- confidence: `high`
- performance_area: `performance-observability-and-profiling`
- issue_type: `performance-observability-gap`
- verification: `direct repo evidence plus shared-research guidance`
- evidence:
  - Inventory and plan artifacts record generation time but no elapsed duration; reports record only apply start/completion and totals (`src/docmend/inventory.py:128-151`; `src/docmend/plan.py:89-110`; `src/docmend/report.py:70-86`).
  - Completion logs carry counts but no elapsed time, bytes, rate, peak memory, or size/tail buckets (`src/docmend/discovery.py:435-475`; `src/docmend/writer/apply.py:689-704`).
  - Default console level is WARNING, so multi-minute healthy runs have no liveness output; per-file file logs exist but no periodic aggregate heartbeat (`src/docmend/observability.py:48-60,98-140`).
  - The shared research recommends per-stage duration, work/bytes, terminal status, representative workload shape, peak memory, and tail/outlier evidence for this batch CLI.
- risk: The staged real-library rollout cannot establish a trustworthy field baseline or distinguish a slow large file, storage degradation, detector-heavy shard, logging overhead, or memory growth without ad hoc profiling. An unattended healthy run can appear hung.
- recommendation: Add low-overhead run/stage metrics and a TTY-independent periodic heartbeat: elapsed time, completed/remaining files and bytes, current/window rate, skips/errors/timeouts, size buckets, and terminal status. Capture peak RSS where portable; keep content-free identifiers and aggregate percentiles.
- acceptance_evidence:
  - Scan/plan/apply/verify emit stable start, heartbeat, stage-complete, and terminal events with durations/counts/bytes.
  - The real-library rollout produces comparable field records without document content.
  - Tests distinguish not-run, in-progress, succeeded, failed, and timed-out states.

### ISSUE-007 — The accepted SIGALRM deviation is not a hard per-file load-shedding boundary

- first_pass: `3`
- severity: `medium`
- confidence: `medium`
- performance_area: `degraded-dependency-and-load-shedding`
- issue_type: `degraded-dependency-load-shedding-gap`
- verification: `direct repo evidence plus repo-local research; C-extension behavior not reproduced`
- evidence:
  - FR-019 describes a process-level watchdog that terminates pathological work; DEV-002 approves an in-process SIGALRM substitute for the sequential release.
  - `src/docmend/watchdog.py:35-65` raises inside the current process and explicitly no-ops outside the main thread.
  - `docs/research/per-file-watchdog-timeout.md` concludes that only process supervision reliably bounds CPU-bound pathological work and recommends a process-level realization.
  - The current tests monkeypatch Python call sites to sleep/raise; they do not demonstrate termination of a stuck native parser/detector or uninterruptible filesystem operation.
- risk: A pathological call that does not promptly return to Python signal handling can exceed the configured timeout and stall the whole sequential run. The risk is accepted/documented but still matters to unattended capacity and tail guarantees.
- recommendation: Treat the timeout as best-effort in operator-facing performance claims until process isolation exists. Add a subprocess-level adversarial probe; when implementing concurrency, supervise and replace timed-out workers rather than relying on `Future` timeout alone.
- acceptance_evidence:
  - Documentation accurately distinguishes best-effort alarm behavior from a hard deadline.
  - A subprocess integration test proves the parent regains control and continues after a genuinely stuck task.

### ISSUE-008 — The conventions library has no performance-engineering entry

- first_pass: `4`
- severity: `low`
- confidence: `high`
- performance_area: `cross-cutting`
- issue_type: `missing-conventions`
- verification: `direct repo evidence`
- evidence:
  - `docs/handoff/conventions.md` contains tooling, spec, ADR, sensitive-data, frontmatter, and standard-ownership rules but no trigger for performance-sensitive pipeline/artifact changes.
  - The repo has binding scale requirements, a large-corpus product goal, and performance research whose critical guidance is not indexed for future contributors.
- risk: A contributor can change record retention, transform allocation, filesystem passes, logging, or artifact serialization without knowing which representative benchmark and evidence must be refreshed.
- recommendation: Add a repo-specific convention for changes affecting per-file work, corpus-wide collections, artifact I/O, logging, verification, backup/write durability, or concurrency. Require correctness-preserving profiling, representative size/count distributions, cold/warm and field/lab labels, peak memory, tails, and baseline comparison. Keep generic benchmark-before-optimize guidance as a cross-project default.
- acceptance_evidence:
  - The convention has a concise trigger, canonical command/workflow pointer, required metrics, privacy rule, and explicit exception process for safety-driven overhead.

## Critical Path And Hotspot Risks

- scan: checked-in 100k baseline `188.1 s`; directory walk, per-file open/hash/newline/UTF-8 classification, optional legacy detector, and per-file logging are the dominant known cold path.
- plan: checked-in baseline `18.3 s`; each pending file is reread, decoded, transformed, and checked while corpus-wide inventory/action structures remain live.
- apply: checked-in baseline `147.5 s`; each action is reread/rehashed/retransformed, optionally backed up and reread, atomically published, manifest-validated/fsync'd, logged, and retained in the report.
- verify: not included in the 100k baseline; scan is followed by Markdown rereads/frontmatter splitting and optional manifest rereads/hashes.
- artifact_boundaries: whole JSON document validation/model construction creates memory multipliers not covered by the in-process scale test.
- hotspot_confidence: stage rankings are lab-only because logging was suppressed, `/tmp` was used, and full CLI/backup/verify paths were omitted.

## Tail Latency And Workload Shape

- directly_verified: plan allocation and elapsed time scale near-linearly across 8/16/32 MiB focused inputs; the 32 MiB case took `4.830 s` and peaked at `336.8 MiB` traced heap.
- checked_in_lab_evidence: one 100k synthetic mix of mostly tiny files; aggregate stage times only.
- missing: p50/p95/p99/max per-file duration, file-size/encoding buckets, timeout count, legacy-detector hit rate, cold/warm runs, repeat variance, and real storage behavior.
- tail_risk: a single permitted large/pathological file can dominate memory and elapsed time; current timeout is best-effort rather than process-enforced.
- interactive_latency: not needed for this repo; the relevant user journey is time-to-first progress, liveness during the batch, and terminal completion.

## Data Access And Caching Risks

- database_queries: not needed for this repo.
- schema_validator_cache: directly verified and appropriate (`functools.cache` in `src/docmend/artifacts.py`).
- filesystem_reuse_gap: verify discards scan hash reuse and rereads Markdown/applied outputs (ISSUE-005).
- artifact_materialization_gap: readers/writers hold multiple whole-document representations (ISSUE-001).
- remote_cache_or_cdn: not needed for this repo.

## Concurrency And Queueing Risks

- runtime_model: sequential, single process, single writer, run-level inter-process lock.
- configured_parallelism: accepted but unused (ISSUE-003).
- queue_backpressure: no queue exists; not needed for this repo.
- worker_recycling_and_batching: configured fields exist but have no implementation or measurements.
- safety_constraint: any future concurrency must keep parent-only durable artifact writes and must profile storage contention rather than assume more workers improve fsync-bound throughput.

## Startup, Interaction, And Delivery Risks

- startup: schema validator compilation is cached per process; no material startup regression evidence was found.
- time_to_feedback: default console output provides no heartbeat during healthy work (ISSUE-006).
- CLI_delivery: no frontend render, hydration, bundle, or asset-delivery surface; not needed for this repo.
- cold_path_unknown: no cold interpreter/schema/filesystem timing is recorded separately from steady-state work.

## Degradation And Capacity Risks

- memory_capacity: file-count growth and per-file amplification are independent risk axes (ISSUE-001, ISSUE-002).
- storage_capacity: backup and durable fsync behavior depend on the owner's actual media and topology; not verified in field.
- timeout_degradation: a pathological task can outlive the best-effort alarm (ISSUE-007).
- load_shedding: oversize skip and timeout skip exist; there is no run-level memory/disk preflight or adaptive capacity limit.
- external_dependency_degradation: no remote dependencies exist; not needed for this repo.

## Frontend And Delivery Risks

- frontend_rendering: not needed for this repo.
- browser_interactivity: not needed for this repo.
- asset_bundle_size: not needed for this repo.
- CLI_distribution_size_or_import_cost: reviewed at a high level; no evidence of a material issue.

## Measurement And Benchmark Gaps

- no enforced multi-size memory-scaling test.
- no large-file working-set test across plan/apply/backup/verify.
- no actual full-CLI 100k benchmark including artifact serialization, logging, and verify.
- no scheduled/manual performance workflow or retained trend artifacts.
- no peak RSS, allocation breakdown/profile, per-stage percentiles, repeat variance, or cold/warm split.
- no field baseline from the staged real-library rollout.
- no supported hardware/filesystem/storage envelope or numeric target after OQ-010 deferred it.
- no benchmark proving the value/cost of parallelism before the configuration surface was accepted.

## Convention Recommendations

### Shared Across Projects

- Benchmark before optimizing and preserve correctness assertions in every benchmark.
- Label synthetic/lab, profiler, load, and field evidence separately; never present one synthetic average as a field capacity guarantee.
- Record representative workload distributions, cold/warm state, wall time, throughput, peak RSS, p50/p95/p99/max, errors/timeouts, platform, filesystem, and variance.
- Reject accepted configuration that has no runtime effect.
- Treat safety/durability overhead as an explicit measured tradeoff, not an optimization target to remove silently.

### Repo-Specific

- Decide whether NFR-001 promises streaming constant memory or an explicit O(file-count) budget and supported maximum.
- Tie `limits.max_file_size_mib` to a measured per-file working-set envelope.
- Require refresh of the full CLI scale baseline for changes to discovery, planning, transforms, artifact models/I/O, logging, writer durability, backup, verify, or concurrency.
- Require sensitive-data-safe aggregate performance events for the staged rollout.
- Preserve sequential correctness as the reference result for any future process mode.

## Pass Log

| Pass | Lens | New issues | Result |
| --: | --- | --- | --- |
| 1 | Critical paths, workload classes, startup, batch boundaries, scaling architecture | ISSUE-001, ISSUE-003 | Whole-corpus retention and inert parallel configuration identified. |
| 2 | Algorithmic complexity, serialization, memory lifecycle, storage reuse | ISSUE-002, ISSUE-005 | Large-file allocation and verify reread paths identified. |
| 3 | Concurrency, batching, backpressure, degraded behavior, runtime limits | ISSUE-007 | Best-effort watchdog residual identified; no queue/frontend issues applicable. |
| 4 | Lower-severity efficiency, field-vs-lab evidence, guardrails, convention quality | ISSUE-004, ISSUE-006, ISSUE-008 | Baseline, observability, and convention gaps identified. |
| 5 | Adaptive deepening: artifacts, logging, backup, restore, prior baseline | none | Existing issues refined; no new issue class. |
| 6 | Convergence: re-check area matrix, anti-pattern checklist, severity/confidence | none | Second consecutive no-new-issue pass; review converged. |

## Claude Handoff

- priority_order: `ISSUE-001 -> ISSUE-002 -> ISSUE-003 -> ISSUE-004 -> ISSUE-005 -> ISSUE-006 -> ISSUE-007 -> ISSUE-008`
- first_decision: owner must choose the actual NFR-001 memory contract before implementation; streaming and explicit O(file-count) budgeting are different architectures.
- first_measurement: add a representative multi-size, full-CLI benchmark before changing algorithms so remediation has a trustworthy baseline.
- cross_review_overlap:
  - architecture-boundary review also reports the no-op parallel configuration and bounded-memory contract drift.
  - observability/test-suite/CI reviews should sequence ISSUE-004 and ISSUE-006 rather than creating competing benchmark formats.
- safety_constraint: do not weaken atomic write, backup verification, manifest durability, or path safety to improve benchmark numbers.
- convention_change: route any durable performance convention through `docs/handoff/conventions.md` and the repo's normal review/ADR process.
- suggested_follow_on_reviews: observability review for event schema/heartbeat; test-suite and CI reviews for benchmark enforcement; architecture review for streaming/artifact boundaries.

## Open Questions Or Assumptions

- What is the minimum supported RAM and acceptable peak RSS for the owner's rollout machine?
- Is O(file-count) metadata acceptable if a supported maximum and explicit budget replace the current independence promise?
- What are the actual corpus p50/p95/p99/max file sizes and legacy-encoding frequency?
- Which filesystems and physical devices hold the library, artifacts, and tool backups?
- What full-run wall clock and unattended heartbeat cadence are acceptable?
- Should `parallel.*` be removed/rejected until implemented, or is process mode now a required post-v1 change?
- Can field performance records be retained safely using only aggregate counts, size buckets, and run-scoped identifiers?

## Residual Risk

- Direct repo evidence cannot predict the real-library rollout without its workload distribution and storage environment.
- Tracemalloc excludes some native allocations and is not peak RSS; large-file field memory may be higher or lower than the focused values.
- The 100 MiB extrapolation is intentionally labeled as inference; only 8/16/32 MiB inputs were measured.
- The prior 100k result is useful as a correctness/scale smoke point but remains a single synthetic, warm/tmpfs, logging-suppressed observation.
- Network filesystems, removable media, antivirus/indexing, and backup-device contention could materially change throughput and tail behavior.
- No database, web service, frontend, asset pipeline, remote API, queue, or daemon performance surface exists; findings were not forced for those categories.
