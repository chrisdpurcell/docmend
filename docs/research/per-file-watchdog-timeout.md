# Per-File Watchdog/Timeout for Pathological Inputs in the docmend Batch Pipeline

**Date:** 2026-07-05

**Related:** GAP-63 (external gap reference supplied by the calling task; no `GAP-` identifier scheme exists anywhere in this repo as of 2026-07-05 — same disposition already noted for GAP-26, GAP-40, GAP-50, GAP-59, GAP-60 in prior research reports, see [Reconciliation notes](#reconciliation-notes)) · OQ-010 (performance targets and parallelism defaults — this report adds a hard constraint OQ-010's current text doesn't have) · `docs/specs/docmend.md` §7.2 NFR-001 (parallel/batch operation), §7.2 NFR-003 (observability), §8.1 (Discovery/Transform/Writer layer separation), §8.6 (Dependency Policy), §12.1 (Expected Failures, ERR-001–ERR-006), §14 (Capacity/Concurrency assumption), §15 (Risks), §10.4 (State Transitions), §18.2 (Configuration)

**Gap it fills:** The spec requires unattended batch operation at 100k+-file scale (G-003, NFR-001) and skip-and-report conservatism for risky input (FR-015, NFR-004), but nowhere bounds _how long_ a single file's processing may run before the batch is considered stuck, and OQ-010 defers all concurrency/parallelism decisions without noting that the timeout mechanism and the concurrency model are not independent choices — the mechanism that can actually enforce a hard per-file deadline constrains which concurrency model is viable, not the other way around. This report closes that gap: it establishes, with current (2026) evidence, that thread- and signal-based timeouts cannot reliably bound CPU-bound pathological input in CPython, that only OS-process-level supervision can, and it ties that conclusion to concrete stdlib code, a regex-safety rule for the FR-009 whitespace transforms that removes the risk at its source, and new ERR-/risk rows for the spec.

---

## 1. The question in docmend's own terms

GAP-63 names three pathological-input shapes a >100k-file legacy library will eventually contain:

1. **Catastrophic-backtracking regex** triggered by the FR-009 whitespace/blank-line transforms (or any regex added later, e.g. for WH-004 structural conversion) — CPU-bound, can run effectively forever on a crafted or merely unlucky byte sequence.
2. **A huge file that defeats encoding detection** — `charset-normalizer` (§8.6-approved, FR-007) runs statistical/heuristic passes over file content; degenerate or oversized input can make this slow enough to look identical to a hang from the orchestrator's point of view.
3. **Corrupted/adversarial input** more generally — anything in the discovery→transform path that loops, allocates unboundedly, or otherwise never returns.

All three share the same shape: they happen **after discovery accepts the file and before the writer touches disk** — i.e., inside the Transform layer (and the encoding-detection step that feeds it), which §8.1/NFR-005 already require to be pure, in-memory, and filesystem-free. That existing architectural boundary is exactly the right place to put a watchdog: **wrap discovery's encoding detection and the Transform layer's pure functions in a deadline; never wrap the Writer.** The writer's atomic-replace sequence (temp file + fsync + `os.replace`, NFR-002/D-004) is fast, already-validated, in-memory-to-disk work — killing it mid-flight would only reintroduce the partial-write risk NFR-002 exists to prevent, for no benefit, since the input that could hang is never inside the writer's scope.

§14's capacity table currently says concurrency is "optional parallel workers within one process," and OQ-010 defers concrete parallelism defaults to MS-5. This report's central finding is that **the timeout mechanism is not compatible with every concurrency model** — specifically, it rules out thread-based workers as the enforcement mechanism regardless of what OQ-010 eventually decides about worker _count_, for reasons detailed in §2.

## 2. Why cooperative (thread/signal) timeouts do not work here

**The GIL blocks the whole process during a backtracking match, not just one thread.** `re`'s C implementation (`_sre`) does not release the GIL while matching [community, benfrederickson.com — corroborated independently by the live 2026 CPython discussion in §2 below]. A single catastrophic-backtracking call on one thread therefore stalls every other thread in the process — health checks, a watchdog thread's own `time.sleep` wakeups, everything — because nothing else can acquire the GIL until the C loop returns control to the interpreter [community, benfrederickson.com/python-catastrophic-regular-expressions-and-the-gil]. A `threading`-based timeout (start a worker thread, wait on a separate watchdog thread, "cancel" on deadline) cannot make the offending computation stop; Python has no primitive to forcibly kill a thread, and even if it did, the GIL contention alone defeats the purpose. This is documented as a systemic limitation, not a docmend-specific concern: "Signals (e.g., SIGTERM, SIGKILL) are process-wide, not thread-specific... ThreadPoolExecutor does not [support forcibly stopping one task]" [community, py4u.org — corroborated by multiple Stack Overflow threads reaching the identical conclusion, e.g. stackoverflow.com/questions/75310731].

**`signal.alarm`/`SIGALRM` does not compose with a concurrent-worker model.** `signal.signal()` may only install a handler on the **main thread of the main interpreter**; `signal.alarm()` is POSIX-only. A live (2026) CPython core-development discussion proposing a native `re` timeout parameter states this plainly while surveying exactly docmend's problem space: _"signal.alarm is Unix-only, main-thread-only, and fragile... Running matches in a subprocess with a kill timer is the only reliable containment today"_ [official/community, discuss.python.org/t/add-an-opt-in-timeout-parameter-to-re-to-mitigate-catastrophic-backtracking/107766 — a 2026 Python core-dev thread, still open, proposal not accepted]. Even where `_sre`'s inner loop does periodically check for pending signals (the mechanism that lets Ctrl-C interrupt a hung regex on the main thread — confirmed by a core-dev linking the exact check in `Modules/_sre/sre_lib.h` in that same thread), that check is unusable as docmend's safety net for two independent reasons: (a) it only fires on the main thread, so it is unavailable to any worker other than a single sequential main-thread loop, which is precisely the "conservative single worker" case OQ-010 floats as a possible v1 default; and (b) it does not help with the other two GAP-63 failure modes at all — an oversized file inside `charset-normalizer`'s pure-Python heuristics, or a pathological loop anywhere else in discovery/transform, is not `re`-specific and gets no benefit from a `re`-internal signal check.

**`concurrent.futures` timeouts do not kill the work; they only stop waiting for it.** `Future.result(timeout=...)` raises `TimeoutError` in the _caller_ when the deadline passes, but the underlying call keeps running to completion in the worker — this is explicit stdlib behavior, not a bug, and it is confirmed independently across the CPython issue tracker and multiple Stack Overflow threads for both `ThreadPoolExecutor` and `ProcessPoolExecutor`: "the standard `multiprocessing.Pool` is not designed for dealing with worker timeouts" [community, stackoverflow.com/questions/38711840]; "Python standard `Pool` does not support worker termination on task timeout" [community, stackoverflow.com/questions/35669183]; a hung `ProcessPoolExecutor` future left `result(timeout=3)` looping "hang forever" until the caller manually tracked the worker PID and sent a signal [community, stackoverflow.com/questions/59034070]. **For a thread-based worker this is fatal** — there is no way to reach into a live thread and stop it. **For a process-based worker it is merely inconvenient** — the process is a real OS entity that can be signaled, which is the basis for §3's recommendation.

**Conclusion:** whatever OQ-010 ultimately decides about worker _count_ (1 or N), the _mechanism_ that enforces a per-file deadline for GAP-63's failure modes must operate at the OS-process level, not the thread level. A future free-threaded (no-GIL) Python build does not change this conclusion — Python still has no primitive to forcibly stop a running thread even without the GIL forcing serialization — and docmend's own runtime target (Python 3.14) still ships the standard GIL-enabled build by default; free-threading is officially supported as of Python 3.14 (PEP 779) but is an opt-in separate build, with "GIL off by default" not planned before roughly 2027–2028 [community, pydevtools.com/handbook/explanation/what-is-pep-703; gdevops.frama.io Python 3.14 free-threaded-mode-improvements].

## 3. Recommended mechanism: a process-level watchdog scoped to discovery + transform

**Architecture:** the apply orchestrator (main process) never runs discovery's encoding detection or the Transform layer's functions in-process on untrusted file content. Each file (or a small batch of files, to amortize process-start cost) is handed to a **worker process** the orchestrator supervises with a deadline:

```python
import multiprocessing as mp
from dataclasses import dataclass


@dataclass
class TransformResult:
    ok: bool
    text: str | None
    error: str | None


def _run_transform(path: str, config: dict, out_conn) -> None:
    """Runs in the worker process. Only discovery/encoding-detect/transform
    happen here — never the writer. Top-level function (picklable/importable),
    required for 'forkserver' and 'spawn' start methods."""
    try:
        text = detect_and_transform(path, config)  # pure, in-memory (NFR-005)
        out_conn.send(TransformResult(ok=True, text=text, error=None))
    except Exception as exc:  # noqa: BLE001 - report, never crash the orchestrator
        out_conn.send(TransformResult(ok=False, text=None, error=repr(exc)))


def transform_with_watchdog(
    path: str, config: dict, timeout_s: float, kill_grace_s: float = 2.0
) -> TransformResult:
    parent_conn, child_conn = mp.Pipe(duplex=False)
    proc = mp.Process(target=_run_transform, args=(path, config, child_conn))
    proc.start()
    proc.join(timeout_s)

    if proc.is_alive():
        proc.terminate()  # SIGTERM: request cooperative exit first
        proc.join(kill_grace_s)
        if proc.is_alive():
            proc.kill()  # SIGKILL (3.7+, POSIX): no more waiting
            proc.join()
        return TransformResult(ok=False, text=None, error="timeout")

    if parent_conn.poll():
        return parent_conn.recv()
    return TransformResult(ok=False, text=None, error=f"worker exit code {proc.exitcode}")
```

The orchestrator then writes (or skips) based on `TransformResult` exactly as it already does for any other Failed/Skipped outcome — the writer, manifest, and report machinery (FR-003–FR-006, DR-003/DR-004) do not need to know a timeout happened versus any other Failed classification.

**Why this specific stdlib shape, not `ProcessPoolExecutor`:** the standard pool executors have no supported API to identify and kill _one specific_ hung worker without a respawn — the only documented lever is `terminate()`/`shutdown()` on the whole pool, which kills every in-flight file, not just the offending one [community, corroborating Stack Overflow and CPython-issue evidence in §2]. A one-process-per-file (or per-small-batch) `multiprocessing.Process`, supervised individually as above, sidesteps that gap entirely using only the stdlib, with no new dependency — consistent with docmend's Dependency Policy (§8.6: new dependencies require an OQ- and owner approval).

**Two stdlib caveats the implementer must respect:**

- `Process.terminate()`'s official warning: _"If this method is used when the associated process is using a pipe or queue then the pipe or queue is liable to become corrupted and may become unusable by other process[es]. Similarly, if the process has acquired a lock or semaphore etc. then terminating it is liable to cause other processes to deadlock"_ [official, docs.python.org/3/library/multiprocessing.html]. The pattern above avoids this by giving each worker its own private `Pipe`, never a shared `Queue`/`Lock`, and by never reusing a worker process across files — a timed-out worker is simply discarded, not returned to a pool.
- **Start method matters, and Python 3.14 already changed it in docmend's favor.** As of Python 3.14, the default POSIX `multiprocessing` start method changed from `fork` to `forkserver` [community, corroborated independently by a Red Hat Bugzilla build-failure report and a Hacker News discussion of 3.14 breaking changes, both specifically citing this change]. `forkserver` (like `spawn`) starts each worker from a clean, freshly-imported interpreter rather than cloning the parent's live memory (locks, threads, open file descriptors) at an arbitrary point — the safer choice for exactly the kind of ad hoc, per-file worker process this pattern spawns. The practical implication for docmend: `_run_transform` must be a top-level, importable function (not a closure or lambda), because `forkserver`/`spawn` re-import the module rather than inheriting it by fork — the example above is written that way. Docmend should not need to call `multiprocessing.set_start_method()` explicitly; it should instead add a smoke test asserting the process-creation method is not the (Python-version-dependent) legacy `fork` default before relying on this behavior, since it is a recent (3.14) change and has already surprised several projects mid-upgrade.

**Diagnosing hangs, not just killing them:** in addition to the hard kill, enable `faulthandler.dump_traceback_later(timeout_s, exit=False)` inside the worker at the start of `_run_transform` (stdlib, zero dependency) so that if a file _does_ hang, the run's logs capture the actual Python-level stack the worker was stuck in — this is the stdlib's documented watchdog-style hang-diagnosis tool [official, docs.python.org/3/library/faulthandler.html; corroborated as the standard answer to "how can I tell where my Python script is hanging" — stackoverflow.com/questions/3443607]. This directly serves NFR-003 (observability): a timeout without a captured stack tells the owner _that_ a file was pathological but not _why_, which matters for growing the weird-document corpus (§17.2).

**Where this leaves the "pebble" library:** `pebble.ProcessPool` is a purpose-built, actively used third-party solution to exactly this problem — per-task timeout with transparent worker interruption and pool-slot respawn, used in production per independent reports [community, multiple Stack Overflow answers corroborating "Pebble is a quite stable library... We use Pebble in production on few systems and it works nicely"; official docs at pebble.readthedocs.io]. It removes the manual bookkeeping the pattern above requires once the worker count grows beyond a handful and a real pool (not one-process-per-file) becomes worth it. It is **not** in the §8.6 dependency table, so adopting it needs an OQ- and owner approval (§8.6); this report recommends starting with the zero-dependency stdlib pattern for v1 and revisiting `pebble` only if operational experience at 100k-file scale shows the manual respawn logic is a real maintenance burden — flagged as a candidate in [Reconciliation notes](#reconciliation-notes).

## 4. Regex-safety for the FR-009 whitespace/blank-line transforms

FR-009's transforms (trim trailing whitespace, ensure one final newline, collapse runs of blank lines beyond a configured maximum) do not need catastrophic-backtracking-prone patterns at all, and the strongest mitigation is to avoid the risk at the source rather than rely on a timeout to catch it after the fact:

1. **Prefer plain string operations over regex wherever they suffice.** Trailing-whitespace trim is `"\n".join(line.rstrip() for line in text.splitlines())` — O(n), no backtracking possible because there is no regex engine involved. Final-newline enforcement is a string-length check plus at most one append. Neither classic "evil regex" shape — nested quantifiers like `(a+)+`, or ambiguous alternation like `([a-z]|a)+` [official, owasp.org/www-community/attacks/Regular_expression_Denial_of_Service_-_ReDoS] — has any reason to appear in code this simple; the safest regex is the one that was never written.
2. **Where regex genuinely is the clearer tool** (e.g. `re.sub(r"\n{4,}", "\n" * (max_blank + 1), text)` for blank-line collapsing), the pattern has a single, bounded, non-nested quantifier over a single character class — not the nested-quantifier or overlapping-alternation shapes OWASP and Semgrep's cross-project ReDoS survey both identify as the actual root cause of catastrophic backtracking in real code, including in Python's own standard library (`urllib`'s CVE-2020-8492 was exactly a nested-quantifier pattern, `(?:.,)` next to a comma-repeat) [official, owasp.org/www-community/attacks/Regular_expression_Denial_of_Service_-_ReDoS; community, semgrep.dev/blog/2020/bento-check-catch-catastrophic-backtracking-redos-bugs]. A single top-level quantifier with no nested repetition inside it cannot exhibit exponential backtracking regardless of input, because there is no second quantifier layer to multiply against.
3. **If any future regex (WH-004 structural conversion, or a hand-authored pattern review misses) needs a repetition that _could_ nest, use Python's built-in atomic grouping and possessive quantifiers instead of an audit-and-hope process.** Python 3.11 added `(?>...)` (atomic groups) and possessive quantifiers `*+`, `++`, `?+`, `{m,n}+` to the stdlib `re` module [official, "What's New In Python 3.11": "Atomic grouping (`(?>...)`) and possessive quantifiers... are now supported in regular expressions," contributed via bpo-433030 — corroborated at learnbyexample.github.io/python-regex-possessive-quantifier and multiple Stack Overflow answers]. A possessive quantifier consumes greedily and **never backtracks into what it already matched**; wrapping any group that repeats a bounded character class (e.g. `[ \t]++` for a run of tabs/spaces) in this form makes catastrophic backtracking structurally impossible for that group, at zero dependency cost, because docmend already targets Python 3.14 — no separate `regex` package needed for this. This is the concrete, code-level regex-safety rule to apply during code review of any new pattern touching untrusted file content: **default new patterns to possessive quantifiers/atomic groups unless backtracking into that specific group is required for correctness**, and record the exception when it is.
4. **Defense in depth, only if OQ-010's eventual profiling shows it's needed:** the third-party `regex` module (PyPI, `mrab-regex`) supports a native, per-call `timeout` keyword on every matching method (`regex.sub(pattern, repl, string, timeout=2)` raises `TimeoutError` on expiry) [official, mrab-regex README (github.com/mrabarnett/mrab-regex)]. This is a real, working mitigation independently confirmed by the current (2026) CPython core-dev discussion as "the" existing answer teams reach for today [official/community, discuss.python.org/t/add-an-opt-in-timeout-parameter-to-re-to-mitigate-catastrophic-backtracking/107766]. It is not needed for v1 given rules 1–3 above cover FR-009's actual pattern set, and it is not in the §8.6 dependency table (would need an OQ-), but it is worth naming now so a future regex-heavy feature (WH-004 HTML/structural conversion) has a named, evidenced fallback instead of reinventing this research.
5. **File-size guard, independent of regex:** none of the above protects against GAP-63's second failure mode — an oversized file making `charset-normalizer`'s heuristic passes slow enough to look like a hang. `charset-normalizer` is materially faster than `chardet` on large payloads in current (2024–2026) published benchmarks, but both remain payload-size-sensitive, and the project's own numbers are stated "per file" with no documented upper bound guarantee [community, jawah/charset_normalizer README benchmarks; bytetunnels.com charset-detection comparison showing chardet scaling to seconds at 1 MB+ while charset-normalizer stays sub-100ms in the same tests]. Because docmend's actual corpus is legacy personal `.txt`/HTML documents — not expected to legitimately be hundreds of MB — the simplest, cheapest mitigation is a **plan-time file-size ceiling** (a new `limits.max_file_size_bytes` config item, proposed default in the tens of MiB) that skips-and-reports oversized files before encoding detection or transform ever runs, using the same FR-015 skip-and-report mechanism the spec already has for binary/NUL/low-confidence files. This is strictly complementary to the process-watchdog in §3, which remains the backstop for whatever slips past the size guard.

## 5. Proposed spec additions

### 5.1 New Expected Failure (§12.1)

| ID | Failure Mode | User/System Behavior | Logging / Observability | Recovery |
| --- | --- | --- | --- | --- |
| ERR-007 | Per-file discovery/encoding-detection/transform exceeds the configured watchdog timeout (catastrophic-backtracking regex, oversized/adversarial file, or any other pathological hang before the writer runs). | That file's worker process is terminated (SIGTERM, then SIGKILL after a grace period) and discarded, never respawned mid-file; the file is marked Failed with reason `timeout`; the batch continues; nothing is written for that file (the writer never started). | Timeout logged with path, elapsed time, configured limit, and worker exit status; `faulthandler.dump_traceback_later` output captured if available; counted in the report summary as a distinct `timed_out` outcome, not conflated with ERR-003 write failures. | Investigate offline (isolate the file, consider it a weird-document-corpus candidate per §17.2); adjust `limits.per_file_timeout_seconds` or `limits.max_file_size_bytes`, or exclude the file via `paths.exclude`; retry via a subsequent apply. |

### 5.2 New Risk (§15)

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
| --- | --- | --- | --- | --- | --- |
| R-007 | A pathological input (catastrophic-backtracking regex trigger, adversarially large/corrupted file, or an as-yet-unseen hang class) stalls a worker indefinitely during discovery/encoding-detection/transform, blocking unattended batch completion (G-003). | Low–Med | Med (wasted wall-clock and a stalled run; not a data-loss risk, because the writer never runs for a file that times out) | Process-level per-file watchdog scoped to discovery+transform only, never the writer (§3); regex-safety by construction for FR-009 via possessive quantifiers/atomic groups or plain string methods (§4); a plan-time file-size ceiling that skips oversized files before detection/transform starts (§4.5). | implementer |

### 5.3 New configuration items (§18.2)

| Setting | Required? | Default | Description |
| --- | --- | --- | --- |
| `limits.per_file_timeout_seconds` | No | e.g. `30` (concrete value pending OQ-010 profiling) | Watchdog deadline for discovery + encoding-detection + transform per file; on expiry the file is marked Failed (ERR-007), never the writer. |
| `limits.max_file_size_bytes` | No | e.g. `52428800` (50 MiB, concrete value pending OQ-010 profiling) | Plan-time ceiling; files above this are skipped-and-reported (FR-015-style) before encoding detection or transform runs. |

### 5.4 State-diagram note (§10.4)

The existing edge `Planned --> Failed : write error` should be broadened to `Planned --> Failed : write error or timeout`, since ERR-007 now produces a Failed outcome from a cause other than a writer error. No new top-level state is needed — a timeout is a Failed outcome with a distinct reason code, exactly like the existing ERR-003/ERR-004/ERR-005 failures already are.

## 6. Version/date sensitivity

- **`re`/`_sre` has no native timeout as of Python 3.14 (2026), and the live core-dev proposal to add one is unresolved** — re-check `docs.python.org/3/library/re.html` and the linked discuss.python.org thread if implementation happens well after this report; if a `timeout=` keyword lands in a future `re`, it would let docmend drop the process-watchdog requirement specifically for regex (not for the encoding-detection or general-hang cases, which are `re`-independent).
- **Atomic grouping/possessive quantifiers in `re`** — added in Python 3.11 (bpo-433030); stable and available on docmend's 3.14+ target with no dependency.
- **`multiprocessing`'s default POSIX start method changed from `fork` to `forkserver` in Python 3.14** — directly affects §3's recommendation (favorably) and requires worker target functions to be top-level/importable; this is recent enough (confirmed via a 2026 Red Hat build-failure report and community discussion of 3.14 breaking changes) that the implementer should add an explicit test/assertion rather than assume it silently.
- **Free-threaded (no-GIL) Python** is officially supported as of 3.14 (PEP 779) but is a separate opt-in build; GIL-off-by-default is not expected before ~2027–2028. §2's "thread cannot be force-killed" conclusion holds independent of GIL status and does not need revisiting even if docmend later runs on a free-threaded build.
- **`charset-normalizer` vs `chardet` performance figures cited in §4.5** are dated December 2024–March 2026 snapshots from the project's own benchmark suite; re-verify if the dependency version pinned in `pyproject.toml` diverges materially from `charset-normalizer` 3.4.x.
- **`pebble`** (noxdafox/pebble) is presented as an evidenced _option_, not a recommendation to adopt now; its own docs (pebble.readthedocs.io, version 5.2.0 as of this research) should be re-checked for currency if it is proposed via a future OQ.

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://discuss.python.org/t/add-an-opt-in-timeout-parameter-to-re-to-mitigate-catastrophic-backtracking/107766> | Add an opt-in timeout parameter to `re` to mitigate catastrophic backtracking | 2026 (open thread) | official (Python core-dev discussion) |
| <https://docs.python.org/3/library/multiprocessing.html> | `multiprocessing` — Process-based parallelism (Python 3.14 docs) | 2026 (current) | official |
| <https://docs.python.org/3/library/faulthandler.html> | `faulthandler` — Dump the Python traceback (Python 3.14 docs) | 2026 (current) | official |
| <https://docs.python.org/3/library/concurrent.futures.html> | `concurrent.futures` — Launching parallel tasks (Python 3.14 docs) | 2026 (current) | official |
| <https://learnbyexample.github.io/python-regex-possessive-quantifier> | Python 3.11: possessive quantifiers and atomic grouping added to `re` | current | community (quotes official "What's New in Python 3.11") |
| <https://github.com/mrabarnett/mrab-regex> | mrab-regex (the `regex` PyPI package) — timeout parameter, README | current | official (project README) |
| <https://owasp.org/www-community/attacks/Regular_expression_Denial_of_Service_-_ReDoS> | Regular expression Denial of Service — ReDoS | 2026 (current) | official (OWASP) |
| <https://semgrep.dev/blog/2020/bento-check-catch-catastrophic-backtracking-redos-bugs> | Bento check: Catch catastrophic backtracking ReDoS bugs (incl. Python stdlib CVE-2020-8492) | 2020 | community (vendor, technically substantive, cross-project survey) |
| <https://www.benfrederickson.com/python-catastrophic-regular-expressions-and-the-gil> | Python, Catastrophic Regular Expressions and the GIL | 2013 (mechanism unchanged; corroborated by 2026 core-dev thread) | community (widely cited, technically verified) |
| <https://www.py4u.org/blog/python-properly-kill-exit-futures-thread/> | How to Properly Exit/Kill Threads in Python's ThreadPoolExecutor | current | community |
| <https://stackoverflow.com/questions/38711840/python-multiprocessing-pool-timeout> | python multiprocessing pool timeout | ongoing | community (corroborating; multiple independent answers agree) |
| <https://stackoverflow.com/questions/35669183/hard-kill-hanging-sub-processes-in-pythons-multiprocessing> | Hard-kill hanging sub-processes in Python's multiprocessing | ongoing | community |
| <https://stackoverflow.com/questions/59034070/cancel-an-processpoolexecutor-future-that-has-hung> | Cancel an ProcessPoolExecutor future that has hung | ongoing | community |
| <https://pebble.readthedocs.io/> | Pebble 5.2.0 documentation — ProcessPool per-task timeout | current | official (project docs) |
| <https://stackoverflow.com/questions/38711840/python-multiprocessing-pool-timeout> | (Pebble production-use corroboration, same thread) | ongoing | community |
| <https://github.com/jawah/charset_normalizer> | jawah/charset_normalizer README — performance benchmarks | 2026 (README current) | official (project README) |
| <https://bytetunnels.com/posts/charset-detection-python-chardet-cchardet-charset-normalizer> | Charset Detection in Python: chardet, cchardet, and charset-normalizer | current | community (benchmark blog) |
| <https://bugzilla.redhat.com/show_bug.cgi?id=2357508> | ocrmypdf fails to build with Python 3.14: multiprocessing.Process now starts with forkserver method instead of fork | 2026 | official (Red Hat Bugzilla, confirms 3.14 default-start-method change) |
| <https://pydevtools.com/handbook/explanation/what-is-pep-703> | What is PEP 703? (free-threaded Python status/timeline) | current | community (technically substantive handbook) |
| <https://gdevops.frama.io/python/versions/3.14.0/free-threaded-mode-improvements/free-threaded-mode-improvements.html> | Python 3.14 PEP 703: Free-threaded mode improvements | current | community |

## Reconciliation notes

- **Fold into spec §12.1**: add ERR-007 as drafted in §5.1 above.
- **Fold into spec §15**: add R-007 as drafted in §5.2 above.
- **Fold into spec §18.2**: add `limits.per_file_timeout_seconds` and `limits.max_file_size_bytes` as drafted in §5.3; concrete numeric defaults should be set alongside OQ-010's profiling pass (MS-5), not guessed at now.
- **Fold into spec §10.4**: broaden the `Planned --> Failed` edge label per §5.4.
- **OQ-010** (performance targets / parallelism defaults): add a note that whatever worker _count_ is chosen, the enforcement mechanism for any per-file deadline must be process-based, not thread-based (§2) — this is a new constraint on OQ-010's scope, not something its current text states.
- **New OQ needed, but _not_ `OQ-015`**: this report should be attached to a new open question (e.g. "per-file watchdog/timeout mechanism and its interaction with the concurrency model") once §21 is next edited. **Do not mint `OQ-015` for it** — three _other_ pending research reports (`docs/research/property-based-testing-hypothesis.md` for GAP-50, `docs/research/python-314-wheel-readiness.md` for GAP-60, and `docs/research/stable-document-id-scheme.md` for GAP-26) have each already independently proposed `OQ-015` as their new number for unrelated topics. That collision is itself a second, distinct instance of the ID-drift pattern this task asked to check for — beyond the already-confirmed drift where `docs/open-questions.md` defines OQ-012–OQ-014 but the spec's own §21 table (`docs/specs/docmend.md`, stops at OQ-011) never lists them. **Recommend the owner do one consolidation pass** across all pending research reports' proposed new-OQ numbers before assigning any of them, rather than accepting `OQ-015` from whichever report is reconciled first.
- **Spec §21 table drift (re-confirmed during this research, orthogonal to the watchdog topic)**: `docs/open-questions.md` still defines OQ-012 (in-place mutation vs. separate output root), OQ-013 (frontmatter required/null/omitted/status), and OQ-014 (real-write CLI/config opt-in) with full Agent-notes content, while the spec's own §21 "Open Questions and Decisions" table ends at OQ-011 — confirming the drift the calling task flagged and that `docs/research/path-containment-toctou.md` and `docs/research/stable-document-id-scheme.md` had already independently spotted. No further OQ-numbered items beyond OQ-014 exist in `open-questions.md` as of this research pass, so the drift is still confined to exactly OQ-012–OQ-014 plus the `OQ-015` numbering collision noted above.
