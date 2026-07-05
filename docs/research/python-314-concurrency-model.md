---
schema_version: '1.1'
id: 'python-314-concurrency-model'
title: 'Concurrency model for a CPU-bound file pipeline on Python 3.14'
description: "Decision matrix (multiprocessing vs free-threaded vs async) for docmend's encoding-detection and hashing pipeline over 100k+ files, with C-extension compatibility notes and a proposed §18.2 parallel.* config surface backing OQ-010."
doc_type: 'research'
status: 'active'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'python-314'
  - 'concurrency'
  - 'multiprocessing'
  - 'free-threading'
  - 'performance'
aliases:
  - 'free-threading vs multiprocessing'
  - 'no-gil python 3.14'
  - 'PEP 703'
  - 'PEP 779'
related:
  - 'docs/specs/docmend.md'
  - 'docs/open-questions.md'
supersedes: []
superseded_by: null
depends_on: []
applies_to:
  - 'OQ-010'
  - 'GAP-22'
  - 'GAP-54'
  - 'NFR-001'
source:
  - 'https://docs.python.org/3/howto/free-threading-python.html'
  - 'https://peps.python.org/pep-0703/'
  - 'https://peps.python.org/pep-0779/'
  - 'https://docs.python.org/3/whatsnew/3.14.html'
  - 'https://docs.python.org/3/library/multiprocessing.html'
confidence: 'high'
visibility: 'public'
license: null
project:
  decision_makers:
    - 'chrisdpurcell'
  consulted: []
  informed: []
---

# Concurrency model for a CPU-bound file pipeline on Python 3.14

**Date:** 2026-07-05 **Related:** OQ-010 (performance targets), GAP-22, GAP-54, spec §7.2 NFR-001 (scalability/parallel), §8.6 (Dependency Policy — `charset-normalizer`, conditional `jsonschema`), §14 (Capacity and Scale Assumptions — "optional parallel workers within one process"), §18.2 (Configuration — proposed `parallel.*` extension)

**Gap it fills:** The spec already assumes optional in-process parallelism (§14) and defers concrete parallelism defaults to OQ-010, but nothing in the spec or open-questions record picks a _primitive_ — multiprocessing, the Python 3.14 free-threaded (no-GIL) build, or `asyncio` — for the actually CPU-bound part of the pipeline (encoding detection + hashing over 100k+ files), nor does it check whether docmend's two encoding/schema dependencies (`charset-normalizer`, and `jsonschema`'s transitive `rpds-py` dependency) are even compatible with the free-threaded build if that were chosen. This report closes that gap with a primitive recommendation, a maturity read on the 3.14 free-threaded build as of 2026-07, per-dependency compatibility notes, and a concrete `§18.2 parallel.*` config surface OQ-010 can adopt directly.

---

## Executive summary and recommendation

**Recommendation: process-based parallelism via `concurrent.futures.ProcessPoolExecutor`, explicitly pinned to the `forkserver` start method, with a `sequential` fallback used by default until MS-5 profiling — not the free-threaded build, not `asyncio`, as the primary CPU-bound concurrency primitive for v1.**

- docmend's per-file hot path (read bytes → sniff binary/NUL → detect encoding via `charset-normalizer` → compute `source.hash`/`output.hash` via `hashlib`) is CPU-bound, not I/O-bound in the sense that matters for concurrency choice: the dominant costs are pure-Python mess-ratio scoring in `charset-normalizer` and (to a lesser extent) hash digest computation, not waiting on the disk. `asyncio` parallelizes waiting, not computing, so it cannot speed up this workload on its own — see §2 and §4.
- Python 3.14's free-threaded build is real and, as of 2026-07, officially **supported** rather than experimental (PEP 779, accepted June 2025) — but it is a **separate, non-default build** (`python3.14t`, ABI tag `cp314t`) that most users installing docmend from PyPI will not have. Shipping a Must-have performance path that only works on an opt-in interpreter build a public tool's users are unlikely to have installed is a deployability risk this project does not need to take in v1. See §1.
- Both C-extension dependencies docmend actually uses check out for free-threading _if_ that path is ever adopted later — `charset-normalizer` is pure Python by design with only an optional, already free-threading-aware `mypyc` speedup extension, and the Rust `rpds-py` package that `jsonschema`/`referencing` pulls in ships native `cp314t` wheels — but "compatible" is not the same as "the right default for a project whose distribution target is standard CPython." See §3.
- Process isolation also fits docmend's own architecture better than threads-without-a-GIL: the writer/planning split already isolates the dangerous layer (D-003); process-per-worker isolation extends that same principle to the CPU-bound scan/plan phase — a worker crash or runaway memory use on one poisoned file cannot corrupt shared interpreter state the way a thread-safety bug in an unaudited C extension could under free-threading.
- CPython 3.14 itself changed the _default_ multiprocessing start method on Linux from `fork` to `forkserver` (the `fork` method is documented as unsafe with threads present) — docmend should pin this explicitly rather than rely on the platform/version default, for reproducibility across dev, CI, and the field. See §1 and §5.

---

## 1. Current maturity of the Python 3.14 free-threaded build

Free-threading is being rolled out under a Steering-Council-approved three-phase plan first described in the PEP 703 acceptance and formalized by PEP 779:

| Phase | Status | Python version | Meaning |
| --- | --- | --- | --- |
| I | Complete | 3.13 | Free-threaded build shipped, explicitly **experimental**. |
| II | **Current, as of 3.14** | 3.14 | Free-threaded build is **officially supported**, but still an **optional, non-default** build (`python3.14t`). |
| III | Not yet scheduled | 3.15+ (no committed version) | Free-threading becomes the default build; timeline undecided. |

Sources: PEP 703 [official](https://peps.python.org/pep-0703/); PEP 779 (accepted for 3.14) [official](https://peps.python.org/pep-0779/); the CPython free-threading HOWTO, which states plainly that "Starting with the 3.13 release, CPython has support for a build of Python called free threading where the global interpreter lock (GIL) is disabled" [official](https://docs.python.org/3/howto/free-threading-python.html); Astral's 3.14 release writeup, which is explicit that phase II "entails full, official support, but still maintains the optional status of the build" [community](https://astral.sh/blog/python-3.14) — corroborated by the community-maintained tracking project itself: "the free-threaded interpreter is no longer considered experimental starting in Python 3.14, although it is not yet the default interpreter build" [community](https://py-free-threading.github.io/).

Concrete implications for a project targeting `requires-python = ">=3.14"` on a standard PyPI install (docmend's actual `pyproject.toml` constraint):

- The free-threaded build is a **separate binary and a separate wheel ABI**, not a runtime flag on the standard interpreter. PEP 803's compatibility table is unambiguous: a `cp314-cp314` wheel does not run on a free-threaded (`cp314t`) interpreter and vice versa; only `abi3.abi3t`-tagged wheels (not yet common) or per-ABI matching wheels work across both [official](https://peps.python.org/pep-0803/). A user running plain `pip install docmend` on the standard `python3.14` will never see free-threading benefits regardless of what docmend's own code does.
- Any C extension not yet updated for free threading is **not broken by default** — importing it silently re-enables the GIL process-wide with a `RuntimeWarning`, per the official HOWTO's "Thread safety" section [official](https://docs.python.org/3/howto/free-threading-python.html) — but that also means "free-threaded" is not a guarantee that _any given dependency graph_ actually gets the parallelism win; it is a per-package property that must be verified (see §3), and a currently-safe dependency can regress if a transitive dependency adds or updates a non-audited extension.
- Independent community benchmarks (two unrelated sources, both post-3.14 release) put single-threaded overhead of the free-threaded build at roughly 5-10% versus the standard build on 3.14 — down from a much larger (~40%) penalty on 3.13's free-threaded build before the specializing adaptive interpreter was re-enabled for 3.14t [blog, corroborated by two independent sources](https://www.javacodegeeks.com/2026/06/python-3-13s-free-threaded-mode-what-no-gil-actually-means-for-your-code.html) / [blog](https://medium.com/@aftab001x/pythons-liberation-the-gil-is-finally-optional-and-why-this-changes-everything-5579b43e969c). Treat these specific percentages as order-of-magnitude community numbers, not vendor-verified benchmarks — but the direction (real but shrinking single-thread tax) is consistent across both.
- CPython 3.14 shipped a second, related but distinct concurrency primitive in the same release: **subinterpreters** in the stdlib (`concurrent.interpreters`, PEP 734) plus a matching `concurrent.futures.InterpreterPoolExecutor` [official](https://docs.python.org/3/whatsnew/3.14.html). These give process-like memory isolation with lower startup overhead than `multiprocessing`, but C-extension isolation support for subinterpreters is its own, separately-immature compatibility axis (many extensions do not yet support the multi-phase initialization subinterpreters require), so this is a "watch, don't adopt yet" item for docmend, tracked as a possible post-v1 optimization rather than folded into this recommendation.

**Bottom line for docmend:** free-threading is a legitimate, officially-supported _option_ as of 3.14, but "supported and optional" is exactly the state that makes it the wrong default for a Must-have (NFR-001) performance path in a public tool whose users install standard CPython. Revisit only when Phase III (default build) lands — no committed CPython version exists for that as of 2026-07; do not gate v1 design on an undated milestone.

---

## 2. Decision matrix: multiprocessing vs free-threaded vs async

Workload characterization first, since the right primitive is workload-dependent: docmend's scan/plan phase over 100k+ files is **CPU-bound with light, local (non-network) I/O** — read a file's bytes, run `charset-normalizer`'s pure-Python mess-ratio scoring to pick an encoding, and hash the content. There is no network I/O and no long idle-wait-for-external-service pattern anywhere in this loop.

| Dimension | Multiprocessing (`ProcessPoolExecutor`) | Free-threaded build (`python3.14t` + `threading`) | `asyncio` |
| --- | --- | --- | --- |
| Speeds up _this_ workload (CPU-bound mess-ratio scoring + hashing) | **Yes** — full core parallelism regardless of GIL status, works on the standard interpreter every docmend user actually has installed. | Yes, _if_ the interpreter in use is the free-threaded build and every extension on the import path has opted in (see §3) — no benefit at all on the standard `python3.14` build most installs use. | **No** — `asyncio` concurrency helps overlap _waiting_, not _computing_; a single-threaded event loop still executes the mess-ratio/hash CPU work serially on one core unless combined with a thread/process pool anyway. |
| Works on the interpreter docmend actually ships against (`requires-python = ">=3.14"`, standard PyPI wheel) | **Yes**, no special build required. | No — requires the user to separately obtain `python3.14t` (distro package, `python.org` installer variant, `deadsnakes` PPA, or building from source) [community](https://blog.adarshd.dev/posts/exploring-free-threaded-python-314/). | Yes, but doesn't solve the problem (see above). |
| C-extension dependency risk | **None** — each worker process has its own normal GIL-enabled interpreter; `charset-normalizer` and `jsonschema`'s `rpds-py` behave exactly as they always have. | Real, though currently low for docmend's two named dependencies (§3) — a future dependency without free-threading support silently re-enables the GIL and the parallelism win for that import graph, and this needs monitoring/CI to catch. | None — same as above, extensions run as normal under the standard interpreter. |
| Fault isolation | **Strong** — a worker crash (segfault in a native dependency, OOM on one pathological file) kills one worker process; the pool and the rest of the batch continue. Matches docmend's own "isolate the dangerous layer" architecture (D-003). | Weak — a thread-safety bug in an unaudited extension, or an uncaught fatal error, can take down the whole process, including in-flight work for every other file. | N/A (single process; a hard crash still takes the whole run down either way). |
| Resumability / NFR-001 (bounded memory, streaming) fit | Good — one file (or a small chunk) in memory per worker at a time; `Pool`/`ProcessPoolExecutor`'s `maxtasksperchild` gives a built-in hedge against per-worker memory growth over a 100k-file run [official](https://docs.python.org/3/library/multiprocessing.html). | Good in principle (threads share memory, no extra IPC serialization cost) — but only realizes any advantage over multiprocessing if free-threading is actually active, which it will not be for most installs (see above). | Naturally streaming for I/O, irrelevant to the CPU-bound part. |
| Implementation cost for a coding-agent-built v1 | Low — `ProcessPoolExecutor.map`/`imap_unordered` over a pure worker function (`path -> outcome dict`) is a direct fit for docmend's existing pure-transform architecture (NFR-005): the worker function is itself a pure, testable function; only argument/return values need to be picklable. | Higher — requires shipping/documenting a second supported interpreter build, a `python3.14t`-specific CI lane, and ongoing dependency-compatibility monitoring the project has no current tooling for. | Low to write, but solves the wrong problem here, so any "low cost" is wasted effort against NFR-001/OQ-010. |
| Startup/IPC overhead per task | Real but bounded — Python 3.14 changed the default start method on Linux to `forkserver` specifically to avoid the "fork with threads present" hazard, at some added per-task pickling/IPC cost versus raw `fork` [official](https://docs.python.org/3/whatsnew/3.14.html). Mitigated with `chunksize` batching (see §5/§6). | Zero extra IPC — same process, shared memory. | N/A. |
| Where the standard-library docs point today | `concurrent.futures.ProcessPoolExecutor`, `multiprocessing.Pool` — both explicitly documented, stable, and now default to `os.process_cpu_count()` for worker count when unset (since 3.13) [official](https://docs.python.org/3/library/multiprocessing.html). | `threading` module + free-threaded build; HOWTO explicitly frames this as a supported-but-optional path, not a universal default [official](https://docs.python.org/3/howto/free-threading-python.html). | `asyncio`, positioned by the stdlib docs for I/O-bound/high-level-structured-concurrency workloads, not CPU-bound batch transforms. |

**Verdict:** multiprocessing wins on every axis that matters for docmend specifically (works on the interpreter users actually have, zero new C-extension risk, better fault isolation matching the existing architecture, low implementation cost against the pure-function design already mandated by NFR-005). Free-threading is the more elegant long-term answer _in the abstract_ — no serialization/IPC cost, no `pickle`-ability constraint on worker arguments — but is disqualified for a v1 default by its non-default-build status alone, independent of the (currently favorable) per-dependency compatibility picture in §3. `asyncio` is disqualified because it does not address the bottleneck at all.

---

## 3. C-extension compatibility notes

### 3.1 `charset-normalizer` (FR-007 encoding detection)

`charset-normalizer` is **pure Python by design** — the project's own documentation states "charset-normalizer will always remain pure Python, meaning that an environment without any build-capabilities will run this program without any additional requirements" [official, project docs](https://charset-normalizer.readthedocs.io/en/latest/community/speedup.html). It ships an _optional_ `mypyc`-compiled speedup extension for its `md.py` mess-ratio module, built only when `CHARSET_NORMALIZER_USE_MYPYC=1` is set at build time; most published wheels use it, but the pure-Python fallback always exists and is what runs when no compatible compiled wheel is available [official](https://charset-normalizer.readthedocs.io/en/latest/community/speedup.html).

Practically, this cuts both ways for docmend's concurrency choice:

- Because the hot path is (mostly) pure Python, it is **fully GIL-bound today** under the standard interpreter — this is precisely the part of docmend's workload that free-threading, if adopted, would actually speed up on multiple threads. It is also precisely why `asyncio` cannot help it: an `await`-based event loop does not make pure-Python CPU work run on more than one core.
- `charset-normalizer` is also already free-threading-ready: the community-maintained free-threading compatibility tracker lists version **3.4.6** as the first release with free-threading support [community, corroborated by the project's pure-Python architecture above](https://py-free-threading.github.io/tracking/). This removes one plausible objection to a _future_ free-threading adoption, but does not change the v1 recommendation in §2, since the blocking issue is the non-default build, not this dependency.

### 3.2 `jsonschema` / `rpds-py` (FR-016/DR-005 frontmatter schema validation, conditional per §8.6)

`jsonschema` is pure Python itself, but since release 4.18 it depends (via the `referencing` package) on **`rpds-py`**, a Rust extension (built with PyO3/`maturin`) providing the immutable data structures `referencing`'s schema registry uses — a dependency addition the `jsonschema` project's own issue tracker documents as introducing a Rust build requirement where none existed before [community, project issue tracker](https://github.com/python-jsonschema/jsonschema/issues/1117).

`rpds-py` is a genuine native (Rust) extension, so it is the one dependency in this pair where free-threading compatibility is a real, non-trivial question rather than a formality — and it checks out:

- The community free-threading compatibility tracker lists `rpds-py` version **0.22.3** as the first release with free-threading support [community](https://py-free-threading.github.io/tracking/).
- Current `rpds-py` releases publish native `cp314-cp314t` wheels directly on PyPI (confirmed by inspecting the published file list for a current release, which includes `manylinux`, macOS, and other `cp314-cp314t`-tagged wheel files) [official, package index](https://pypi.org/project/rpds-py/#files) — i.e., this is not merely "expected to work," it is shipped and built specifically for the free-threaded ABI today.
- `rpds-py`'s Rust bindings use PyO3, which since version 0.23 defaults new extension modules to declaring themselves free-threading-safe (`gil_used = false`), pushing authors to explicitly and deliberately opt back into GIL-serialized behavior only where `unsafe` code demands it [official, PyO3 user guide](https://pyo3.rs/v0.29.0/free-threading). This is a favorable ecosystem signal, not proof of correctness for every internal data path, but it means `rpds-py`'s free-threading support is not an incidental afterthought.

**Net assessment:** if docmend (or a future version of it) ever needs the free-threaded build for a different bottleneck, neither of the two dependencies named in this research question would block that move today. That finding is good news for the _option's_ future viability, but it is orthogonal to — and does not overturn — the v1 primitive recommendation in §2, which turns on build availability and deployability, not on dependency readiness.

---

## 4. Why not free-threading or async as the v1 default (summary of disqualifying factors)

1. **Non-default build.** PEP 779 explicitly keeps the free-threaded build optional in Phase II (3.14); Phase III (default) has no committed CPython version as of 2026-07 [official](https://peps.python.org/pep-0779/). Building a Must-have (NFR-001) performance path around an opt-in interpreter build most `pip install docmend` users will not have contradicts docmend's own goal of remaining "generally useful" (§1) beyond the owner's machine.
2. **No project CI or packaging story for a second ABI.** Adopting free-threading properly would mean testing docmend and its dependency set on both `cp314` and `cp314t`, tracking a `cp314t`-specific compatibility matrix, and documenting a second install path — infrastructure this repository does not have and that is out of scope for a v1 whose milestone ladder (§19) is explicitly ordered "safe migration substrate first."
3. **Wrong tool for the actual bottleneck (`asyncio`).** The workload is CPU-bound pure-Python scoring plus hashing, not waiting on slow I/O; `asyncio` does not parallelize CPU-bound work across cores by itself and would need a `ThreadPoolExecutor`/`ProcessPoolExecutor` underneath anyway to get any speedup — at which point it has added an event loop for no benefit over calling the process pool directly.
4. **Process isolation is a better safety fit anyway.** Given docmend's core safety posture (skip-and-report, never guess; isolate the dangerous layer, D-003), a crashing or misbehaving worker _process_ on one corrupted/hostile file is a contained, recoverable event; a thread-safety bug surfacing under free-threading in an un-audited extension is a whole-process failure mode with a much larger blast radius, at 100k-file scale a real practical concern for R-006 ("unknown variety of document anomalies").

---

## 5. Recommended primitive (detail)

Use `concurrent.futures.ProcessPoolExecutor` (or the lower-level `multiprocessing.Pool`, equivalent for this purpose) for the scan/plan CPU-bound phase, with these specific choices:

- **Start method: pin `forkserver` explicitly** via `multiprocessing.get_context("forkserver")`, rather than relying on the platform/version default. As of Python 3.14, `forkserver` is already the new default on Unix platforms other than macOS (replacing `fork`, which the docs describe as unsafe when threads are present); macOS and Windows already default to `spawn` [official](https://docs.python.org/3/whatsnew/3.14.html). Pinning it explicitly protects docmend from silently changing behavior across Python patch versions or platforms, and keeps worker startup semantics identical in dev, CI, and the field — a reproducibility property this spec already values (D-005's "read-only stdlib parsing" and NFR-005's purity requirements are in the same spirit).
- **Worker function is a pure function of `(path, config-snapshot)`, returning a small picklable result** (a dict or dataclass with hash, detected encoding + confidence, newline style, classification/skip-reason) — this is a direct extension of the pure-transform requirement already mandated by NFR-005, just applied one layer earlier (discovery/planning), and keeps per-task IPC payloads small regardless of the underlying file's size (never pickle full file contents across the process boundary; read and hash inside the worker).
- **Default worker count: mirror the stdlib's own default**, `os.process_cpu_count()` (the same call `multiprocessing.Pool`/`ProcessPoolExecutor` now use internally as of Python 3.13 when `processes`/`max_workers` is left unset) [official](https://docs.python.org/3/library/multiprocessing.html), exposed as `parallel.workers = "auto"` in config rather than hand-rolled logic. Note one known gap worth flagging rather than silently trusting: `os.process_cpu_count()` (unlike the older `os.cpu_count()`) does respect the process's CPU affinity mask, but an open CPython issue notes it does **not** yet account for cgroup CPU quota limits on Linux [community, CPython issue tracker](https://github.com/python/cpython/issues/149452) — not a concern for docmend's stated single-workstation target (A-004), but worth a one-line note in the config reference if this tool is ever run inside a constrained container.
- **`maxtasksperchild` as a memory-growth hedge** for full 100k+-file runs, per the `multiprocessing.Pool` documentation's own recommendation for long-running worker pools [official](https://docs.python.org/3/library/multiprocessing.html) — recycle workers periodically rather than assuming zero leaks across a multi-hour unattended batch (NFR-001's bounded-memory requirement, at pool-lifetime scale rather than per-file scale).
- **A `sequential` (single-process, `workers=1`) mode is not just a fallback but the mode used by default until profiled**, and the mode all unit/property tests run under (keeps the NFR-005 purity tests deterministic and keeps CI simple) — this matches, rather than contradicts, OQ-010's existing "default to conservative single-process or low worker count" assumption; this research fixes _which primitive_ backs the eventual non-default mode, it does not force flipping the default before MS-5 profiling.
- **Hashing already partially escapes the GIL today, independent of this decision.** `hashlib`'s OpenSSL-backed algorithms (including SHA-256, used for `source.hash`/`output.hash`) release the GIL for buffer updates at or above a compile-time threshold (`HASHLIB_GIL_MINSIZE`, historically 2048 bytes) — documented behavior dating to Python 3.1 and still present in current CPython source [official, CPython source](https://github.com/python/cpython/blob/master/Modules/hashlib.h) / [official, stdlib docs](https://docs.python.org/3/library/hashlib.html). This is a secondary, minor point (most legacy text files are well above that threshold, so hashing already gets some real OS-thread concurrency even on the standard interpreter), but it means the _encoding-detection_ half of the workload — not hashing — is the part that actually justifies the process-based design; if `charset-normalizer` is ever swapped for a compiled/GIL-releasing detector, this recommendation should be revisited (see Reconciliation notes).

---

## 6. Proposed §18.2 `parallel.*` configuration surface

Extends the existing §18.2 configuration table with a new settings group. Shape mirrors the existing table's style (setting / required? / default / description):

| Setting | Required? | Default | Description |
| --- | --- | --- | --- |
| `parallel.enabled` | No | `true` | Enables process-pool parallelism for scan/plan's per-file CPU work; `false` forces the sequential path (also the automatic behavior when `parallel.workers` resolves to `1`). |
| `parallel.model` | No | `"process"` | Concurrency primitive. Only `"process"` (`ProcessPoolExecutor`) and `"sequential"` are supported in v1; reserved values `"thread"` (free-threaded build) and `"interpreter"` (`concurrent.interpreters`/PEP 734) are recognized as forward-compatible placeholders but rejected with a clear "not supported in this release" error until a future OQ- revisits §1/§4 — chosen so the config schema does not need a breaking change if either primitive becomes viable later (e.g., Phase III default-build free-threading). |
| `parallel.workers` | No | `"auto"` | `"auto"` resolves to `os.process_cpu_count()` at run time (mirrors the stdlib's own default resolution); an explicit positive integer overrides it. `1` is equivalent to `parallel.enabled = false`. |
| `parallel.start_method` | No | `"forkserver"` | Explicit `multiprocessing` start method (`"forkserver"`, `"spawn"`; `"fork"` is not offered as a config value — see §5 rationale). Pinned rather than left to the platform default so behavior is stable across OS/Python-patch combinations. |
| `parallel.chunksize` | No | `"auto"` | Passed through to the pool's `map`/`imap_unordered` call to batch small per-file tasks and amortize `forkserver` IPC overhead; `"auto"` uses a size derived from inventory count and worker count, an explicit integer overrides it. |
| `parallel.maxtasksperchild` | No | unset (no recycling) | Optional worker-recycling threshold (files processed before a worker is replaced), a hedge against per-worker memory growth on full-library runs; unset preserves current stdlib default behavior (workers live for the pool's lifetime). |

Implementation note for whoever resolves OQ-010: this table answers "which primitive and what shape," not "what number is the default `workers` value's practical floor/ceiling for the real library" — that second, purely empirical question is still correctly deferred to post-MS-1 profiling on the 100k-file synthetic corpus, exactly as OQ-010's existing agent notes already propose.

---

## 7. Answer to the research question, directly

> For a batch that runs CPU-bound encoding detection + hashing over 100k+ files, what concurrency primitive should docmend use on Python 3.14 — multiprocessing, the free-threaded (no-GIL, PEP 703) interpreter, or async I/O — given C-extension dependency compatibility, and what default worker count/model should OQ-010 assume?

**Multiprocessing** (`concurrent.futures.ProcessPoolExecutor`, `forkserver`-pinned), **not** the free-threaded build and **not** `asyncio`. C-extension compatibility is favorable for a _future_ free-threading move (both `charset-normalizer` and `rpds-py` already support it), but that finding is not what decides v1 — build non-defaultness and the lack of any project tooling for a second ABI are. OQ-010 should assume a `process`/`sequential` model exposed via the §6 config surface, with `workers` defaulting to `os.process_cpu_count()` ("auto") once parallelism is enabled by default at MS-5, and `sequential` remaining the mode used through MS-1/MS-2 correctness work and in all NFR-005 purity tests.

---

## Reconciliation notes

Findings from this report should fold back into:

- **`docs/specs/docmend.md` §18.2 (Configuration):** add the `parallel.*` table from §6 above (verbatim or lightly edited) as a new settings group, following the existing table's style.
- **`docs/specs/docmend.md` §14 (Capacity and Scale Assumptions) / §8.6 (Dependency Policy):** the "Concurrency" row in §14 currently says only "optional parallel workers within one process" — update it to name the primitive (process pool, not threads) now that this research has settled it; no new dependency-policy row is needed since `multiprocessing`/`concurrent.futures` are stdlib.
- **`docs/open-questions.md` OQ-010:** fold this report's primitive recommendation into OQ-010's "Agent notes" (parallelism defaults bullet), citing this report; OQ-010 can then move to `docs/resolved-questions.md` once the owner confirms the primitive choice, while the concrete numeric throughput/worker-count targets remain open pending the post-MS-1 100k-file profiling run, exactly as OQ-010 already anticipates.
- **GAP-22 / GAP-54** (external gap-tracker IDs supplied with this research request, not yet present in-repo): whoever owns that tracker should mark both closed against this report once §18.2/OQ-010 are updated.
- If `charset-normalizer` is ever replaced or gains a mandatory compiled fast path (§5's closing note), re-open this analysis specifically for §2's "speeds up this workload" row — the process-based recommendation is contingent on the current pure-Python-dominated hot path, not an unconditional preference for processes over threads.

---

## Sources

| URL | Title | Date accessed | Authority |
| --- | --- | --- | --- |
| <https://peps.python.org/pep-0703/> | PEP 703 — Making the Global Interpreter Lock Optional in CPython | 2026-07-05 | official |
| <https://peps.python.org/pep-0779/> | PEP 779 — Criteria for supported status for free-threaded Python | 2026-07-05 | official |
| <https://peps.python.org/pep-0803/> | PEP 803 — "abi3t": Stable ABI for Free-Threaded Builds | 2026-07-05 | official |
| <https://docs.python.org/3/howto/free-threading-python.html> | Python support for free threading (HOWTO) | 2026-07-05 | official |
| <https://docs.python.org/3/whatsnew/3.14.html> | What's New in Python 3.14 | 2026-07-05 | official |
| <https://docs.python.org/3/library/multiprocessing.html> | `multiprocessing` — Process-based parallelism | 2026-07-05 | official |
| <https://docs.python.org/3/library/concurrent.futures.html> | `concurrent.futures` — Launching parallel tasks | 2026-07-05 | official |
| <https://docs.python.org/3/library/hashlib.html> | `hashlib` — Secure hashes and message digests | 2026-07-05 | official |
| <https://github.com/python/cpython/blob/master/Modules/hashlib.h> | CPython source: `HASHLIB_GIL_MINSIZE` | 2026-07-05 | official |
| <https://github.com/python/cpython/issues/149452> | `os.process_cpu_count()` cgroup-quota gap (open issue) | 2026-07-05 | community |
| <https://charset-normalizer.readthedocs.io/en/latest/community/speedup.html> | charset-normalizer: optional speedup extension | 2026-07-05 | official |
| <https://pypi.org/project/rpds-py/#files> | rpds-py PyPI file listing (cp314-cp314t wheels) | 2026-07-05 | official |
| <https://github.com/python-jsonschema/jsonschema/issues/1117> | jsonschema 4.18 introduces `rpds-py`/Rust dependency | 2026-07-05 | community |
| <https://pyo3.rs/v0.29.0/free-threading> | PyO3 user guide: Supporting Free-Threaded Python | 2026-07-05 | official |
| <https://py-free-threading.github.io/> | Python Free-Threading Guide (community-maintained, CPython-affiliated) | 2026-07-05 | community |
| <https://py-free-threading.github.io/tracking/> | Compatibility Status Tracking (charset-normalizer 3.4.6, rpds-py 0.22.3) | 2026-07-05 | community |
| <https://astral.sh/blog/python-3.14> | Python 3.14 (Astral release notes) | 2026-07-05 | community |
| <https://www.javacodegeeks.com/2026/06/python-3-13s-free-threaded-mode-what-no-gil-actually-means-for-your-code.html> | Python 3.13's Free-Threaded Mode — single-thread overhead benchmarks | 2026-07-05 | blog |
| <https://medium.com/@aftab001x/pythons-liberation-the-gil-is-finally-optional-and-why-this-changes-everything-5579b43e969c> | Python's Liberation: The GIL is Finally Optional — corroborating benchmark table | 2026-07-05 | blog |
