---
schema_version: '1.1'
id: 'adr-0007-docmend-concurrency-primitive-process-pool'
title: 'ADR 0007: CPU-bound concurrency primitive'
description: "v1 parallelizes CPU-bound work with concurrent.futures.ProcessPoolExecutor pinned to the forkserver start method — not the 3.14t free-threaded build, not asyncio — and runs sequentially by default until MS-5 profiling; free-threading is gated behind an explicit release checklist."
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'concurrency'
  - 'performance'
  - 'python-314'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0002-layered-pipeline-isolated-writer.md'
supersedes: []
superseded_by: null
source: []
confidence: 'high'
visibility: 'public'
license: null
project:
  decision_makers:
    - 'chrisdpurcell'
  consulted: []
  informed: []
---

# CPU-bound concurrency primitive

## Context and Problem Statement

docmend's CPU-bound work — encoding detection and hashing over 100,000+ files (NFR-001) — can be parallelized. Python 3.14 offers three primitives: multiprocessing, the free-threaded (no-GIL) build, and `asyncio`. Which does v1 use as its concurrency primitive, and is parallelism enabled by default?

## Decision Drivers

- Must run on the interpreter users actually install (standard CPython from PyPI), not an opt-in build.
- Fault isolation matching the writer-isolation architecture (ADR-0002): a crashing worker must not take the run down.
- Zero new C-extension risk.
- Correctness and safety first (RQ-009): parallelism is an optimization, not a v1 acceptance gate.
- Reproducibility across dev, CI, and the field.

## Considered Options

- **`concurrent.futures.ProcessPoolExecutor` pinned to the `forkserver` start method.**
- **The 3.14t free-threaded (no-GIL) build** with `threading`.
- **`asyncio`.**

## Decision Outcome

Chosen option: **"ProcessPoolExecutor + forkserver."** v1 uses `concurrent.futures.ProcessPoolExecutor` with `multiprocessing.get_context('forkserver')` pinned explicitly — **not** the 3.14t free-threaded build (a separate, non-default interpreter, `python3.14t`, most PyPI users will not have), and **not** `asyncio` (it does not address a CPU-bound bottleneck). **Sequential is the v1 default until MS-5 profiling** (`parallel.enabled = false`; the sequential path is what all NFR-005 purity tests use); when enabled, `parallel.workers = "auto"` resolves to `os.process_cpu_count()`. A §18.2 `parallel.*` surface (`enabled`, `model`, `workers`, `start_method`, `chunksize`, `maxtasksperchild`) ships with `"process"` and `"sequential"` as the only v1 models; `"thread"` (free-threaded) and `"interpreter"` (PEP 734) are reserved and rejected until a future re-open. Worker functions must be top-level-importable (a `forkserver` constraint). **Re-open to free-threading only when a release-gated checklist fires:** (a) a stable build defaults free-threaded **or** the Steering Council accepts the Phase III PEP **or** `uv`/OS installers treat it as first-class; **and** (b) `Py_GIL_DISABLED == 1`, `sys._is_gil_enabled()` stays `False` after importing the **full** app, and every native dependency ships `cp3xyt`/`abi3t` wheels; **and** (c) a docmend switch-benchmark beats the process-pool baseline with zero correctness drift.

### Consequences

- Good, because it works on every user's interpreter; fault isolation (each worker is a separate process) matches D-003 / ADR-0002; and each worker keeps its own GIL-enabled interpreter, so `charset-normalizer` and `jsonschema`'s `rpds-py` carry zero new free-threading risk.
- Good, because sequential-by-default keeps v1 correctness-first and gives every purity test a deterministic path.
- Bad, because a process pool has pickling/IPC cost (mitigated by `chunksize` batching) and imposes a top-level-importability constraint on worker functions.
- Bad, because free-threading is the more elegant long-term answer (no IPC or `pickle` constraint) but is disqualified as a v1 default by its non-default-build status alone.

### Confirmation

Confirmed by: the transform-purity suite (NFR-005) passing in both `sequential` and `process` modes; the `forkserver` start method asserted rather than left to the platform default; the free-threading re-open criteria encoded as an explicit checklist (this ADR) rather than folklore; and numeric throughput targets deferred to RQ-009.

## More Information

- Spec: NFR-001, §14, §18.2 (`parallel.*`).
- Research: `python-314-concurrency-model`, `docmend-and-the-free-threaded-cpython-switch-decision`.
- Decision owner: owner, implementer-proposed (RQ-016). Relates to ADR-0002 (process workers mirror writer fault-isolation) and RQ-009 (numeric perf targets deferred).
- Revisit strictly per the release-gated checklist above; there is no committed CPython version for the free-threaded default build as of 2026-07.
