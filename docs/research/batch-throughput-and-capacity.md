---
schema_version: '1.1'
id: 'batch-throughput-and-capacity'
title: 'Batch throughput, memory, disk-space, and progress-reporting budget for a 100k-file pass'
description: "Profiling-spike measurements and cited benchmarks validating OQ-010's throughput/memory/wall-clock targets, a disk-space preflight formula, and a Rich-based progress/heartbeat design for docmend's single-worker apply pipeline."
doc_type: 'research'
status: 'active'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'performance'
  - 'throughput'
  - 'capacity-planning'
  - 'disk-space'
  - 'ci-testing'
aliases:
  - 'OQ-010'
  - 'scale test'
  - 'disk preflight'
  - 'progress bar cadence'
  - '100k file benchmark'
related:
  - 'docs/specs/docmend.md'
  - 'docs/open-questions.md'
  - 'docs/research/python-314-concurrency-model.md'
  - 'docs/research/atomic-write-filesystem-semantics.md'
  - 'docs/research/encoding-detection-benchmark.md'
  - 'docs/research/structured-logging-library.md'
  - 'docs/research/synthetic-corpus-generation.md'
supersedes: []
superseded_by: null
depends_on:
  - 'atomic-write-filesystem-semantics'
  - 'python-314-concurrency-model'
  - 'encoding-detection-benchmark'
applies_to:
  - 'OQ-010'
  - 'GAP-20'
  - 'GAP-38'
  - 'GAP-54'
  - 'NFR-001'
  - 'NFR-002'
  - 'NFR-003'
source:
  - 'https://docs.python.org/3/library/hashlib.html'
  - 'https://docs.python.org/3/library/shutil.html'
  - 'https://docs.python.org/3/library/os.html#os.replace'
  - 'https://rich.readthedocs.io/en/stable/progress.html'
  - 'https://rich.readthedocs.io/en/stable/reference/progress.html'
  - 'https://chardet.readthedocs.io/en/latest/performance.html'
  - 'https://pypi.org/project/charset-normalizer/'
  - 'https://danluu.com/deconstruct-files/'
  - 'https://docs.github.com/en/actions/reference/runners/larger-runners'
  - 'https://github.com/actions/runner-images/discussions/9329'
confidence: 'medium'
visibility: 'public'
license: null
project:
  decision_makers:
    - 'chrisdpurcell'
  consulted: []
  informed: []
---

# Batch throughput, memory, disk-space, and progress-reporting budget for a 100k-file pass

**Date:** 2026-07-05

**Related:** `docs/specs/docmend.md` NFR-001, NFR-002, NFR-003, §14 (Capacity and Scale Assumptions), §17.2 (Test Strategy), §17.3 (NFR-001 traceability row), §18.5 (Observability), §19 (MS-5 scale test) · `docs/open-questions.md` OQ-010 (performance targets) · GAP-20, GAP-38, GAP-54 (external gap-tracker IDs supplied with this research request — not present in any tracked docmend document as of this writing; `docs/open-questions.md`, `docs/resolved-questions.md`, `docs/deep-research-queue.md`, `docs/decisions/`, and `docs/handoff/*` were all checked). GAP-54 is also cited by `docs/research/python-314-concurrency-model.md` (`applies_to`); that report answers "which concurrency primitive," this one answers "what throughput/memory/disk numbers, and what does OQ-010 mean by 'first'."

**Gap it fills:** OQ-010 currently carries only structural targets ("bounded memory... under 512 MiB," "at least 500/1,000 files/minute," "under 8 hours") with an explicit note that concrete numbers were deferred to post-MS-1 profiling on the synthetic corpus (§21 OQ-010 row; `docs/open-questions.md` OQ-010 Agent notes). Nothing in the spec or open-questions record has yet run that profiling pass, computed a disk-space preflight formula for the FR-005/OQ-008 backup-copy obligation, or designed the progress/heartbeat surface implied by NFR-003's "diagnose issues mid-batch without re-running" and a multi-hour unattended run (§14 "Request rate: manually invoked batch runs"). This report closes that gap with an actual profiling spike (synthetic corpus, local SSD, Python 3.14.6), a component-level cost breakdown, a validated/adjusted set of OQ-010 numbers, a concrete disk-space preflight formula, a Rich-based progress/heartbeat design that builds on the already-approved `rich` dependency (§8.6) and the sibling structured-logging research, and a recommendation on where the 100k-file scale test should live in CI.

**Spec drift also confirmed while reading source material for this report:** `docs/open-questions.md` defines OQ-012, OQ-013, and OQ-014, but `docs/specs/docmend.md` §21's own Open Questions and Decisions table stops at OQ-011 (lines 890–906) — those three open questions are currently invisible to the spec of record. This is independently confirmed by `docs/research/atomic-write-filesystem-semantics.md` and `docs/research/encoding-detection-benchmark.md`, both of which flagged the same drift while researching unrelated topics on the same day. Whoever closes it should do so once, in one change, rather than have a fourth report re-discover it.

## Bottom Line and Recommendation

OQ-010's targets are **conservative, not infeasible** — on a local NVMe-backed btrfs SSD, a single-worker, fully-durable (temp file + `fsync` + `os.replace` + parent-directory `fsync`) pipeline over synthetic small text files measured **2,636–4,036 files/minute** and **~49 MiB peak RSS**, both comfortably inside OQ-010's floor (500–1,000 files/min) and ceiling (512 MiB). Recommendation:

1. **Keep 500–1,000 files/min and <512 MiB as regression-alarm floors/ceilings**, not as aspirational targets — real single-worker throughput on comparable hardware should be several times higher; treat "below 500 files/min" or "above 512 MiB" in the scale test as a signal that something regressed (slow storage, disk contention, a memory-buffering bug), not as "we hit the wall."
2. **Lower the "8 hours" wall-clock framing to two numbers**: a "typical" expectation of well under two hours on comparable local SSD hardware, and an outer safety bound of 8 hours reserved for genuinely slower media (spinning HDD backup targets, network-mounted backup destinations, very large individual files) — see §3.
3. **Add a disk-space preflight gate** requiring, per distinct mount point (library root, `write.backup_dir`, and any artifacts location if separate): the backup destination needs headroom for a full duplicate of every file the run will touch (≈1× the bytes being processed) plus a 10–15% margin for filesystem block-size rounding and manifest/report growth; the library mount needs only a small, worker-count-bounded transient margin, since in-place mechanical normalization does not grow files. See §5 for the exact formula.
4. **Use a Rich `Progress` display on the same `Console` as the already-recommended structlog/Rich logging setup** (`docs/research/structured-logging-library.md`), refreshed at a low rate (2–4 Hz, not the library default of 10 Hz) with a longer speed-averaging window (60–120 s) to keep the ETA stable over a multi-hour run, **plus** a separate, TTY-independent heartbeat log line every N files or T seconds (whichever comes first) so an unattended run redirected to a log file (`nohup`, `systemd`, CI) still shows liveness. See §6.
5. **Keep the full 100k-file scale test out of the default `check.yml` PR/push gate.** Wire it as a separate, `workflow_dispatch` + weekly-`schedule`-triggered workflow (MS-5 framing already implies this — §19 lists it under "Hardening and production readiness," not every-commit CI). Keep a cheap, fast **memory-independent-of-corpus-size** assertion (e.g., compare peak RSS at 5k vs. 20k synthetic files) in the default gate, since that check is fast, deterministic, and catches the most dangerous regression class (an accidental whole-corpus in-memory structure) on every PR. See §7.

## 1. Profiling Spike: Method, Environment, and Caveats

No profiling run existed anywhere in the repo or its research history for this specific question, so this report includes an actual spike rather than only citing external benchmarks. **Method:** a synthetic corpus of 5,000 small text files (public-domain-style Lorem-ipsum-shaped prose, 3–12 paragraphs each, ~1–4 KiB/file) with a realistic mix of legacy-file mess — mixed newline styles (`\n`/`\r\n`/`\r`), UTF-8, UTF-8-with-BOM, and Latin-1 encodings, trailing whitespace, and irregular blank-line runs — was generated with a fixed random seed. A single-worker pipeline then ran, per file: read bytes → `charset-normalizer` `from_bytes().best()` detect+decode → newline-normalize to LF → re-encode UTF-8 → `hashlib.sha256` on source and output bytes → `shutil.copy2` to a backup directory → atomic write (temp file in the target directory, `os.fsync(fd)`, `os.replace()`), run once without a per-file parent-directory `fsync` and once with one, to isolate the durability-hardening cost described in `docs/research/atomic-write-filesystem-semantics.md`.

**Environment:** Python 3.14.6 (matches the spec's `requires-python = ">=3.14"`), `charset-normalizer` 3.4.7, on a local workstation SSD, `btrfs` filesystem, `compress=zstd:1`, single trial per configuration.

**Caveats — read before trusting the absolute numbers:**

- **Single machine, single trial, synthetic corpus.** No repeated runs for variance, no real legacy-library files (none exist in this pre-implementation repo, and none may exist in this public repo per the project's non-negotiables). Treat the numbers as an order-of-magnitude sanity check, not a certified benchmark — the spec's own MS-5 scale test against the eventual weird-document corpus (§17.2) is the authoritative measurement.
- **btrfs with `compress=zstd:1` is not the only filesystem docmend will run on.** ext4 and XFS both require the same pre-rename `fsync()` for crash-durability that this spike measured, per `docs/research/atomic-write-filesystem-semantics.md`, so the _shape_ of the cost (write + fsync + replace dominates) should generalize, but absolute per-`fsync()` latency varies by filesystem and by whether the backup/library targets share a physical device.
- **The workstation's `/tmp` is `tmpfs` (RAM-backed)**, so this spike deliberately ran on `/var/tmp` (confirmed `btrfs` on real block storage) instead — a `tmpfs`-backed spike would have produced meaningless zero-cost `fsync()` numbers, and `docs/research/atomic-write-filesystem-semantics.md` independently concludes tmpfs must be refused as a write target for exactly this reason (no durability across a reboot regardless of `fsync()` outcome).
- **GitHub Actions runners will very likely be slower and noisier than this local NVMe/SSD spike** — see §7.

## 2. Per-File Pipeline Cost Breakdown

A component-level pass (each stage run across the whole 5,000-file corpus in isolation, then compared to the full interleaved single-file pipeline) attributes the per-file cost:

| Stage | Measured cost (this spike) | Cited benchmark (independent corroboration) |
| --- | --- | --- |
| Read bytes | ~0.005 ms/file | — (page-cache-dominated; negligible at this file size) |
| `charset-normalizer` detect + decode | ~1.24 ms/file | `charset-normalizer` 3.4.6 (mypyc wheel): mean 2.65 ms/file, 376 files/s, on a mixed 2,517-file corpus (chardet.readthedocs.io benchmark, current as of March 2026) [official] — this spike's files are simpler (ASCII/Latin-1-heavy, less "mess" to evaluate), so a lower measured cost than that mixed-corpus average is expected and consistent, not contradictory. |
| SHA-256 hash (source + output) | ~0.002 ms/file | `hashlib`'s OpenSSL backend releases the GIL above ~2 KiB per the CPython source (`HASHLIB_GIL_MINSIZE`) and is uniformly cited as the cheapest stage in this pipeline (Python docs [official]; corroborated in `docs/research/python-314-concurrency-model.md` §5). |
| `shutil.copy2` backup | ~0.06 ms/file | Python `shutil` docs [official] document `copy2()` as `copy()` plus metadata preservation; no published per-call benchmark found, consistent with this being dominated by the same underlying `write()`/`fsync()`-free copy path. |
| Atomic write (temp write + `fsync(file)` + `os.replace()`, **no** directory `fsync`) | ~5.6 ms/file | Single-digit-millisecond `fsync()` latency on SSD is the generally cited range; exact latency is filesystem- and journal-mode-dependent (`docs/research/atomic-write-filesystem-semantics.md` §"Filesystem-by-Filesystem Table" — ext4/XFS require this pre-rename `fsync()` for crash-durability; it is "load-bearing," not belt-and-suspenders). |
| Parent-directory `fsync` (interleaved with real replaces, full run) | **+7.9 ms/file** (measured as the delta between the two full pipeline runs, §3) | Directly corroborates the durability requirement documented independently in Dan Luu, "Files are fraught with peril" [blog, exceptionally-cited primary reference backed by academic citations within it — Bornholt et al. ASPLOS'16, Mohan et al. OSDI'18] and a Stack Overflow answer on UBIFS reaching the same conclusion for a different filesystem [community] — `fsync()` on the file alone does not guarantee the _directory entry_ pointing at it survives a crash; the parent directory must also be `fsync()`'d. `docs/research/atomic-write-filesystem-semantics.md` already recommends this exact behavior (D-004's "fsync parent directory where practical"); this spike supplies the first measured cost number for that recommendation on real hardware. |
| **Sum, no directory fsync** | **~6.9 ms/file** (staged) / **~14.9 ms/file** (interleaved, single-file-pipeline loop) | — |
| **Sum, with directory fsync** | **~22.8 ms/file** (interleaved) | — |

The roughly 2× gap between the staged-by-component sum (6.9 ms) and the realistic interleaved single-file loop (14.9 ms) is itself a finding: processing one file end-to-end (read → detect → hash → backup → write, each against a different directory) has worse filesystem-cache/metadata locality than doing the same work batched by stage across many files. This is consistent with the general small-file-I/O-locality effect documented independently (e.g., a 42.85× I/O speedup measured when reading 1,351 sequential files instead of 104,000 randomly-ordered ones, attributed to metadata-lookup and seek locality rather than raw syscall count) [community, `modulovalue.com`]. **Implication for docmend:** a real single-worker `apply` loop (which must process one file fully, including its manifest write, before moving on, to preserve OQ-003's incremental-manifest-durability contract) should expect costs closer to the interleaved number than the staged number — this report's throughput extrapolation in §3 uses the interleaved (realistic) figures.

## 3. Throughput Extrapolation to 100k Files

Using the interleaved, single-file-pipeline measurements (the realistic shape for a real `apply` loop that must write its manifest entry immediately per file, per OQ-003's Agent notes):

| Mode | Measured rate | 100k-file wall clock |
| --- | --- | --- |
| No parent-directory `fsync` (relies on ext4/XFS's own delayed-allocation flush behavior at the next journal commit — a "best effort," not a guarantee, per `docs/research/atomic-write-filesystem-semantics.md`) | 4,036 files/min (67.3 files/s) | ~25 minutes |
| **Full durability (parent-directory `fsync` after every replace)** — the safer, spec-aligned mode | 2,636 files/min (43.9 files/s) | ~38 minutes |

Both modes clear OQ-010's floor (500–1,000 files/min) by a **4–8×** margin, and clear the 8-hour wall-clock target by more than an order of magnitude, on this spike's hardware. This validates OQ-010's Agent notes framing directly: the numbers were deliberately set as a conservative sanity floor pending real profiling (`docs/open-questions.md` OQ-010: "Treat these as acceptance targets for MS-5, not MS-1/MS-2 blockers"), and this spike is the first evidence that the floor has real headroom rather than being an optimistic guess.

**What would actually threaten the 8-hour/500-files-per-minute floor:** not the CPU-bound detection/hashing stages (sub-millisecond each), but the I/O/fsync-bound atomic-write stage on slower media — a spinning HDD (`fsync()` commonly cited in the 10–15 ms range due to rotational latency, versus this spike's SSD numbers), a network-mounted backup destination (NFS/CIFS add round-trip and cache-coherence overhead on top of whatever the server-side filesystem provides — `docs/research/atomic-write-filesystem-semantics.md` §"NFS"/"CIFS/SMB" rows), or per-file sizes far larger than this spike's 1–4 KiB corpus. **OQ-008's backup-posture decision therefore has a direct throughput consequence that OQ-010 should name explicitly**: if the chosen backup destination is a slower/network-mounted device, the throughput floor should be re-validated against _that_ device, not assumed to transfer from a local-SSD spike.

## 4. Memory Budget

Peak RSS for the full 5,000-file single-worker run was **~49 MiB** (`resource.getrusage(RUSAGE_SELF).ru_maxrss`), with the Python-heap-only `tracemalloc` peak at **~9 MiB** — both are corpus-size-independent measurements consistent with NFR-001's "streaming per-file processing, no whole-corpus in-memory structures" requirement, and far inside the 512 MiB ceiling. **The measured pipeline itself is not the memory risk.** The real risk NFR-001 is actually guarding against, and that this spike does not exercise, is an implementation that accumulates 100k manifest/report _records_ in a single in-memory list/dict before writing the artifact once at the end — even at a generous ~1 KiB/record (source path, target path, both hashes, timestamps, status), 100k records is only ~100 MiB, which would still pass the 512 MiB ceiling in isolation but is exactly the anti-pattern NFR-001 and OQ-003 already argue against (manifest entries "written immediately after each successful mutation," per `docs/open-questions.md` OQ-003). `docs/research/append-safe-manifest-format.md` (already in this research set, per the index) independently recommends an NDJSON/append-only manifest format for the same crash-safety reason; that recommendation also happens to be the memory-safe one. **Recommendation:** keep the 512 MiB ceiling as a regression guard, but make the _binding_ acceptance criterion for NFR-001's memory row an explicit two-point comparison (e.g., peak RSS at 5k files vs. peak RSS at 50k files should differ by less than a small fixed delta, not scale linearly) — this is the check that actually catches an accidental whole-corpus buffer, whereas a single absolute number at one corpus size would not.

## 5. Disk-Space Preflight Formula

**The core arithmetic, given OQ-012's in-place-mutation decision:** after a complete apply run, the library mount holds ~1× the (now-converted) corpus, and the backup destination holds ~1× the pre-conversion originals — so **total steady-state disk consumption is ~2× the original corpus size**, which validates the "~2× source" heuristic given in this research request. The refinement this spike adds is _where_ that 2× is needed and how much headroom on top of it a preflight check should require:

- **Backup destination (`write.backup_dir`, per OQ-005/OQ-008 — must be outside the mutation target path):** needs headroom for a full duplicate of every file the run will touch. This is the dominant, corpus-size-scaling term.
- **Library mount (in-place mutation target):** needs only a small, transient margin — the atomic-write pattern (temp file + `fsync` + `os.replace`) means only _one_ file (per worker) has both its old and new bytes on disk simultaneously at any instant; mechanical newline/BOM/whitespace normalization also does not grow files in the general case (it typically holds size steady or shrinks it slightly). Budget `max_source_file_size_bytes × worker_count` here, not a corpus-scaling term.
- **Artifacts location (manifest/report/plan/logs), if on a separate volume:** small in absolute terms (well under 1 GiB even at 100k files with a verbose NDJSON manifest), but still needs a nonzero floor check — a full artifacts disk mid-run is exactly the kind of failure OQ-003's incremental-manifest durability contract is meant to survive gracefully, and a preflight check is cheaper than discovering it 90% through an unattended run.
- **Filesystem block-size rounding is a real, corroborated tax at 100k-file scale**, independent of file content size: on a 4 KiB block-size filesystem, 100k small files can round up to 100k × 4 KiB ≈ 400 MiB of allocated space even for near-empty files, and the backup copy doubles the file _count_ (though not necessarily the block waste, since content is duplicated at the same average size). A flat **10–15% margin** on top of the raw byte-sum comfortably covers this for a small-text-file corpus without needing per-file block-size arithmetic.

**Concrete formula** (evaluate per distinct resolved mount point — see the footgun below):

```text
required_free(backup_mount)   ≈ Σ(source_bytes_in_scope) × 1.15
required_free(library_mount)  ≈ max(source_file_size_bytes) × worker_count × 1.10
required_free(artifacts_mount)≈ max(500 MiB, file_count × ~1 KiB × 2)   # floor, not corpus-scaling
```

If two or more of these resolve to the same physical filesystem (e.g., backup and artifacts on the same disk, or — against OQ-005's recommendation — backup sharing the library's own mount), **sum the requirements for that mount** rather than checking them independently; a preflight that checks each in isolation would under-count when they compete for the same free-space pool.

**A corroborated footgun this preflight design must account for:** `shutil.disk_usage()` (and the underlying `statvfs(2)`) reports free space for the **whole filesystem/mount** a path resides on — it is the Python equivalent of `df`, not `du` — a fact independently confirmed by a Python core-devs discussion thread and a Stack Overflow answer reaching the same conclusion after debugging a "seeming discrepancy" [both community; corroborated, 2 independent sources]. A preflight check that calls `shutil.disk_usage()` once on the library root and assumes it also covers the backup destination will silently pass even when the backup destination (explicitly required to be a _different_ path than the mutation target, per OQ-005) is a different, nearly-full mount. **The preflight must resolve each of `source_root`, `write.backup_dir`, and any distinct artifacts path to its own mount** (the same longest-mount-point-prefix technique against `/proc/mounts` that `docs/research/atomic-write-filesystem-semantics.md` already recommends for filesystem-durability classification — one mechanism, two consumers) and run the check independently per distinct mount.

## 6. Progress, ETA, and Heartbeat Design

`rich` is already an approved dependency (§8.6) and `docs/research/structured-logging-library.md` already recommends attaching an explicit `rich.logging.RichHandler` (rather than relying only on structlog's auto-detection) specifically "if docmend later wants Rich progress bars/spinners driven from the same console session as log output, since it keeps everything on one `rich.console.Console` instance" — this report is exactly that later use, so the recommendation below assumes and extends that shared-`Console` design rather than introducing a second one.

**`rich.progress.Progress` defaults, and why they need tuning for a multi-hour unattended batch** [official, `rich.readthedocs.io`]:

- `refresh_per_second` defaults to **10** — appropriate for an interactive, short-lived CLI operation being watched in real time, but wasteful and log-noisy (if the console is also capturing structlog output at the same time) over a 30–60 minute run where nothing visually interesting happens between file-count ticks. **Recommend 2–4 Hz** for docmend's `apply` progress display — still visually smooth, an order of magnitude less redraw work over a multi-hour run.
- `speed_estimate_period` defaults to **30.0 seconds** — the window Rich uses to compute the "speed"/ETA columns. A 30-second window is fine for a short task but will make the ETA visibly jump around over a multi-hour run if per-file cost varies (larger files later in the corpus, an OS-level disk-cache warm-up/cool-down cycle, a backup destination that briefly contends with something else on the same disk). **Recommend widening `speed_estimate_period` to 60–120 seconds** for the `apply` progress bar specifically, trading a few seconds of ETA responsiveness for a much more stable read-out over a run the owner may only glance at occasionally.
- Rich's advance/update calls (`progress.update()`) are decoupled from the actual terminal redraw — the redraw is what `refresh_per_second` throttles, not the per-file bookkeeping call — so it is safe and cheap to call `progress.advance(task, 1)` after every single file without waiting for a batch, keeping the progress state precisely in sync with the incremental-manifest-write model OQ-003 already requires.

**TTY-vs-non-TTY split (the actual heartbeat requirement):** a live-updating Rich progress bar is meaningless once stdout/stderr is not a terminal — redirected to a log file (`docmend apply plan.json --write > run.log 2>&1`), piped, or running under `systemd`/`nohup`/CI. `Console.is_terminal` is the existing, already-idiomatic way to detect this (and is exactly what structlog's own `ConsoleRenderer()` already uses internally per the sibling logging report). **Recommend:**

- When `console.is_terminal` is true: render the live `Progress` bar as designed above (2–4 Hz refresh, 60–120 s speed window), with columns for description, bar, percentage, files-completed/total, elapsed time, and estimated remaining time (`rich.progress.TimeElapsedColumn`/`TimeRemainingColumn`, both stdlib-Rich, no extra dependency).
- When `console.is_terminal` is false (or `--quiet`/non-interactive mode is set): **suppress the live bar entirely** and instead emit a plain structured **heartbeat log line** at a fixed cadence — recommend **every 1,000 files processed or every 30 seconds of wall-clock time, whichever comes first** — through the same structlog pipeline NFR-003 already requires for per-file/per-run detail. This satisfies NFR-003's "diagnose issues mid-batch without re-running" for the actually-common unattended-run case (a log file being tailed or reviewed after the fact) without inventing a second output surface. A heartbeat line should carry at minimum: files completed, files remaining, elapsed time, current rate (files/min over the same 60–120 s window used for the interactive ETA, for consistency), and the count of skips/errors so far — everything the operator needs to judge "is this run healthy" from a single log line without re-deriving it from per-file records.
- The 1,000-files-or-30-seconds dual trigger avoids two failure modes: a heartbeat that goes silent for many minutes on a slow file (30-second wall-clock trigger), and log spam once throughput is fast enough that 1,000 files would otherwise pass in under a second (the 30-second floor also caps heartbeat _frequency_, not just its minimum cadence — implement as "at most once per 30 seconds, and at least once per 1,000 files or 30 seconds").

## 7. Scale Test: Default CI Gate or Separate Job?

**Recommendation: separate job, not the default `check.yml` gate.** Three independent, corroborating reasons:

1. **General CI/CD practice is unambiguous and multiply-corroborated**: keep per-PR/per-push gates fast (smoke-level, typically minutes), and push longer/heavier performance or scale validation to a scheduled (nightly/weekly) or manually-triggered job — a pattern described consistently across several independent sources on CI/CD performance-testing practice [community, multiple independent sources: Ranger, Gatling, DevOps.com, Augment Code, Elio Navarrete — "avoid running tests longer than 15 minutes in the main deployment pipeline," "schedule heavier load or soak tests nightly or per release," "reserve heavier load profiles for staging merges or scheduled runs"]. Even at this spike's favorable local numbers (25–40 minutes for the full 100k-file pass), a scale test of that length has no place gating every commit in a single-developer repo where `check.yml` currently completes in well under that time.
2. **GitHub-hosted `ubuntu-latest` runners are a documented, independently-corroborated I/O bottleneck relative to local NVMe/SSD hardware** — multiple sources describe virtualized/shared-storage disk I/O as a known source of CI slowness and variance (a dedicated benchmarking site publishes ongoing GitHub Actions disk-I/O comparisons; a widely-discussed Hacker News/blog post on "disk I/O bottlenecks in GitHub Actions" documents specific mitigations vendors apply for exactly this reason) [community]. A numeric throughput assertion calibrated against this spike's local-SSD numbers would be at real risk of flaking on shared CI infrastructure, which is a second, independent reason not to gate every commit on it even if the _duration_ were otherwise acceptable.
3. **`ubuntu-latest` free disk space is a moving, shrinking target**: GitHub's own docs currently state standard hosted runners have 2 CPU cores, 7 GB RAM, and 14 GB SSD (with the "larger runners" tier offering 4 CPU/16 GB RAM/150 GB disk) [official, `docs.github.com`], and a tracked community discussion documents a further reduction in _free_ space on the standard runner image (from "31 GB+" to "roughly 17 GB+") following a routine image update [community, `github.com/actions/runner-images` discussion]. A 100k-file synthetic corpus of small text files (this spike's files averaged a few KiB) plus its backup copy is well within that budget in isolation (likely under 1 GiB total, even accounting for the block-size-rounding effect described in §5), but it is one more consumer of an already-tightening shared budget on the same runner that also has to check out the repo, build a `uv` environment, and run the rest of the gate — an avoidable source of contention for a check that does not need to run on every commit.

**Concrete recommendation:**

- **Keep in the default `check.yml` gate**: a fast, deterministic memory-independent-of-corpus-size assertion (compare peak RSS across two corpus sizes, e.g. 5k vs. 20k synthetic files — small enough to run in seconds, and the exact check this report's §4 identifies as the one that actually catches the dangerous regression class).
- **Move to a separate workflow** (e.g. `scale-test.yml`), triggered by `workflow_dispatch` and a weekly `schedule`, and optionally as a non-blocking post-merge job on pushes to `main`: the full 100k-file synthetic-corpus wall-clock/throughput/memory-ceiling test that exercises NFR-001's traceability row (§17.3) end-to-end. This matches the spec's own milestone framing — §19 already places "100k-file synthetic corpus; bounded-memory assertion (NFR-001); parallelism if needed" under MS-5 ("Hardening and production readiness"), not under the continuous per-commit gate that exists today for MS-0-era code.

## Revised OQ-010 Targets

| Dimension | Current OQ-010 draft | This report's evidence-backed revision |
| --- | --- | --- |
| Memory | "under 512 MiB... excluding OS cache" | Keep 512 MiB as an outer regression ceiling; make the _binding_ check a corpus-size-independence comparison (§4), since the spike shows real usage (~50 MiB RSS at 5k files) is nowhere near the ceiling and a single absolute number at one corpus size would not catch a whole-corpus-buffer regression. |
| Throughput | "scan/plan at least 1,000/min; apply at least 500/min" | Keep as regression-alarm floors (validated as achievable with 4–8× headroom on comparable local-SSD hardware, §3); explicitly document that the floor should be re-validated against the actual chosen OQ-008 backup-destination medium if it is not local SSD, since the atomic-write/backup-copy stage — not encoding detection or hashing — is what a slower device would degrade. |
| Wall clock | "under 8 hours" for a full 100k-file pass | Keep 8 hours as the outer safety bound (covers slow/degraded storage); add a "typical" expectation of well under 2 hours on comparable local hardware (§3), so a run that is "technically under 8 hours" but 5–10× slower than typical is still visible as a finding, not silently passing. |
| Parallelism | "default to conservative single-process or low worker count" | Confirmed and reinforced with a mechanism, not just a policy: the dominant per-file cost is I/O/`fsync`-bound (§2), not CPU-bound, so naive multi-worker fan-out mostly contends for the same disk's journal-commit path rather than scaling linearly — complements, does not reopen, `docs/research/python-314-concurrency-model.md`'s process-pool primitive recommendation. |
| Disk space | _(not previously covered by OQ-010)_ | New: preflight formula in §5, evaluated per distinct mount point, required before this report's targets can be treated as complete acceptance criteria for a real-library apply run. |
| Progress/heartbeat | _(not previously covered by OQ-010)_ | New: Rich-based interactive progress (2–4 Hz refresh, 60–120 s speed window) plus a TTY-independent heartbeat log line (every 1,000 files or 30 s) per §6. |
| CI placement | _(not previously covered by OQ-010)_ | New: memory-independence check stays in the default gate; full 100k-file scale test moves to a separate scheduled/`workflow_dispatch` job (§7). |

## Open Questions Surfaced

| # | Question | Why unresolved |
| --- | --- | --- |
| 1 | Should the disk-space preflight formula (§5) be a new FR/NFR, or folded into OQ-005's existing safety-gate checklist as an additional gate item? | Both are defensible; §5's per-mount check is a natural sibling to OQ-005's "backup destination... outside the mutation target path... writable" gate item, but it introduces new config surface (which paths to check) that OQ-005's draft doesn't currently name. |
| 2 | What is the real per-`fsync()` latency and per-file throughput on the owner's actual intended backup-destination hardware (per OQ-008), as opposed to this spike's local NVMe/btrfs workstation? | This spike deliberately used local SSD storage; OQ-008's backup-posture decision (Git/external backup/tool-written backup, and the physical device behind it) is still open, and §3 shows the backup-copy stage is the one most sensitive to that choice. |
| 3 | Should the memory-independence CI check (§4/§7) be written now, ahead of any real scan/plan/apply implementation, as a property the pipeline must satisfy from day one? | This report recommends it as the binding default-gate check for NFR-001, but no implementation exists yet to write the check against; flag for whoever implements MS-1/MS-2. |

## Reconciliation Notes

Fold these findings into:

- **`docs/open-questions.md` OQ-010** — replace the placeholder "numbers set after MS-1 profiling" language with this report's validated floor/ceiling values and the "typical vs. outer-bound" wall-clock framing (Revised OQ-010 Targets table above); this report is that profiling evidence, gathered ahead of MS-1 rather than after it, and should be revisited once a real implementation exists to re-measure against (this spike used a hand-rolled pipeline that approximates, but is not, docmend's actual code).
- **`docs/specs/docmend.md` §7.2 NFR-001 / §17.3 traceability row** — add the corpus-size-independence comparison (§4) as the concrete "memory usage independent of corpus size" acceptance test, alongside (not instead of) the absolute 512 MiB ceiling.
- **`docs/specs/docmend.md` §7.1 (a new or extended FR) / §21 OQ-005** — add the disk-space preflight formula (§5) as an explicit safety-gate checklist item, referencing OQ-005's existing "backup destination... writable" line as the natural attachment point.
- **`docs/specs/docmend.md` §18.5 (Observability)** — add the progress/heartbeat design (§6) as the concrete shape of "structured per-file logs with a per-run correlation," extending rather than replacing NFR-003's existing language.
- **`docs/specs/docmend.md` §17.2 (Test Strategy) / §19 (MS-5)** — record the CI-placement recommendation (§7): memory-independence check in the default gate now; full 100k-file scale test as a separate scheduled/`workflow_dispatch` workflow at MS-5.
- **The pre-existing §21 OQ table drift** (OQ-012–014 present in `docs/open-questions.md` but absent from the spec's own §21 table) — noted here for the third time across this research batch (also flagged independently by `docs/research/atomic-write-filesystem-semantics.md` and `docs/research/encoding-detection-benchmark.md`); whoever closes it should do so once, in one change that also reconciles any new OQ- entries these three reports propose, so the table does not immediately fall behind again.

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://chardet.readthedocs.io/en/latest/performance.html> | chardet performance page (detector speed table, incl. `charset-normalizer` 3.4.6) | accessed 2026-07-05, "updated as of March 2026" | [official] (self-reported, see `docs/research/encoding-detection-benchmark.md` for the disputed-accuracy caveat; speed numbers used here only for order-of-magnitude corroboration) |
| <https://pypi.org/project/charset-normalizer/> | charset-normalizer PyPI page — performance table, license | accessed 2026-07-05 | [official] |
| <https://docs.python.org/3/library/hashlib.html> | `hashlib` — Secure hashes and message digests | Python 3.14.6 docs, accessed 2026-07-05 | [official] |
| <https://docs.python.org/3/library/shutil.html> | `shutil` — High-level file operations (`copy2`, `disk_usage`) | Python 3.14 docs, accessed 2026-07-05 | [official] |
| <https://docs.python.org/3/library/os.html#os.replace> | `os.replace()` documentation | Python 3.14 docs, accessed 2026-07-05 | [official] |
| <https://rich.readthedocs.io/en/stable/progress.html> | Rich — Progress Display (auto-refresh, `refresh_per_second`) | Rich 14.1.0 docs, accessed 2026-07-05 | [official] |
| <https://rich.readthedocs.io/en/stable/reference/progress.html> | Rich — `rich.progress` API reference (`Progress`, `speed_estimate_period`, columns) | Rich 14.1.0 docs, accessed 2026-07-05 | [official] |
| <https://danluu.com/deconstruct-files/> | "Files are fraught with peril" — `fsync` on file vs. parent directory | accessed 2026-07-05; long-standing, exceptionally widely cited | [blog] (primary reference for this footgun; cites Bornholt et al. ASPLOS'16 and Mohan et al. OSDI'18 within it) |
| <https://stackoverflow.com/questions/53702698/do-we-need-to-fsync-the-parent-directory-in-ubifs-for-atomic-and-durable-file> | Do we need to fsync the parent directory for atomic and durable file updates? | accessed 2026-07-05 | [community] (second, independent source for the same footgun) |
| <https://discuss.python.org/t/disk-space-used-by-a-file/45205> | `shutil.disk_usage()` reports filesystem-wide (df-like), not directory-scoped (du-like), usage | accessed 2026-07-05 | [community] |
| <https://stackoverflow.com/questions/19236690/seeming-discrepancy-in-shutil-disk-usage> | "Seeming discrepancy in shutil.disk_usage()" — same conclusion, independent thread | accessed 2026-07-05 | [community] (second, independent source) |
| <https://modulovalue.com/blog/syscall-overhead-tar-gz-io-performance/> | Small-file I/O locality effect (42.85× speedup from sequential vs. random small-file access) | accessed 2026-07-05 | [blog] |
| <https://docs.github.com/en/actions/reference/runners/larger-runners> | GitHub Actions — Larger runners reference (standard runner specs: 2 CPU/7 GB/14 GB) | accessed 2026-07-05 | [official] |
| <https://github.com/actions/runner-images/discussions/9329> | ubuntu-latest runner disk space reduced (community-tracked regression) | accessed 2026-07-05 | [community] |
| <https://www.ranger.net/post/automated-performance-testing-cicd-guide> | Automated Performance Testing for CI/CD — keep long tests out of the main pipeline, schedule separately | accessed 2026-07-05 | [community] |
| <https://gatling.io/blog/performance-testing-ci-cd> | Add load testing to your CI/CD pipeline — smoke tests per merge, full-scale tests nightly | accessed 2026-07-05 | [community] |
| <https://docs.python.org/3/whatsnew/3.14.html> | What's New in Python 3.14 (used to confirm Python 3.14.6 spike environment matches spec's `requires-python`) | accessed 2026-07-05 | [official] |

`docs/research/atomic-write-filesystem-semantics.md`, `docs/research/python-314-concurrency-model.md`, `docs/research/encoding-detection-benchmark.md`, and `docs/research/structured-logging-library.md` (same-day sibling reports in this repo) are cited throughout by relative path rather than duplicated in this table; see each report's own Sources table for their full citation lists.
