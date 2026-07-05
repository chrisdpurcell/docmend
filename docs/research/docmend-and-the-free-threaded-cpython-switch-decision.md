# docmend and the free-threaded CPython switch decision

Date: 2026-07-05

## Executive summary

CPython has reached **Phase II** of the PEP 703 rollout: free-threaded Python is now **officially supported, but still not the default build**. That status was formalized by PEP 779 for Python 3.14, after the Steering Council’s 2023 acceptance of PEP 703 laid out a three-stage rollout: experimental, supported-but-not-default, then default. The same Steering Council record also says that any move to a default free-threaded build is a separate decision, and that removing the GIL build would only be discussed **some time after** a default flip. [\[1\]](https://discuss.python.org/t/pep-703-making-the-global-interpreter-lock-optional-in-cpython-acceptance/37075)

As of 2026-07-05, the strongest primary-source reading is: **Phase III has no committed release target**. Python 3.15 beta documentation is still about making the packaging and ABI story workable for free-threaded extensions via `abi3t`, and explicitly says common build tools did **not** yet support `abi3t` at the time those docs were written. That makes a 3.15 default flip very unlikely. My best estimate is therefore: **not before 3.16**, with **3.16–3.17+** the earliest plausible window if ecosystem adoption and packaging support keep improving; but this is an inference, not a published CPython commitment. [\[2\]](https://docs.python.org/3.15/whatsnew/3.15.html)

For **docmend**, the practical conclusion is straightforward: **do not retire** `ProcessPoolExecutor` **yet**. Re-open the decision when the runtime and ecosystem conditions are measurably different: the free-threaded build is default or first-class in your supported interpreter channels, your full dependency import set leaves `sys._is_gil_enabled()` false, and a docmend-specific benchmark shows that a thread pool on a free-threaded build beats the process-pool baseline on throughput without unacceptable regressions in memory, correctness, or small-file latency. [\[3\]](https://docs.python.org/3/howto/free-threading-python.html)

The dependency picture is encouraging but not uniformly decisive. `rpds-py` is the strongest positive signal: it publishes version-specific `cp314t` and `cp315t` wheels. `charset-normalizer` is also unusually positive: it advertises the PyPI free-threading classifier and publishes `cp314t` wheels, while also shipping a universal wheel. `jsonschema`, `rich`, `pathspec`, `click`, and current `typer` are pure-Python `py3-none-any` distributions, which means they have **no ABI-wheel blocker**, but that is not the same thing as an explicit free-threading support statement. Also, PEP 803 is explicit that an extension being loadable on a free-threaded build does **not** prove it is thread-safe without the GIL. [\[4\]](https://pypi.org/project/rpds-py/)

## Bottom line and recommendation

Keep the current **process-based** default for docmend through the current Python 3.14 / 3.15 cycle. That is the conservative choice because free-threaded Python is still optional in official installers, the Steering Council has left the default-flip decision explicitly undecided, and the 3.15 cycle is still finishing the ABI and packaging transition needed for third-party native extensions to support both GIL and free-threaded builds cleanly. [\[5\]](https://docs.python.org/3/using/mac.html)

Re-open the design when at least one of these becomes true:

- a stable CPython release makes the free-threaded build the default, or the Steering Council publishes the future-PEP decision that Phase III is beginning; [\[6\]](https://discuss.python.org/t/pep-703-making-the-global-interpreter-lock-optional-in-cpython-acceptance/37075)
- the interpreter channels you actually support make free-threaded Python first-class enough that users will encounter it without special handling. Today, official macOS installers still make it a separate optional install, and `uv` still prefers the GIL build for installation even though it can discover and use free-threaded 3.14+ interpreters. [\[7\]](https://docs.python.org/3/using/mac.html)
- your lockfile’s import graph can be imported under a free-threaded build **without re-enabling the GIL**, as verified by `sys._is_gil_enabled()` after importing the full app. CPython’s docs explicitly warn that importing a C extension not marked as free-threading-compatible may automatically enable the GIL. [\[8\]](https://docs.python.org/3/howto/free-threading-python.html)
- your benchmark shows that a thread pool on a free-threaded build wins on the workload that matters to docmend: lots of independent documents, significant pure-Python compute in charset detection and transformation, and no correctness regressions. [\[9\]](https://docs.python.org/3/howto/free-threading-python.html)

If you want one crisp policy line for the project: **do not switch executor strategy because free-threading exists; switch because your supported interpreter channels, your dependency graph, and your benchmark all say the no-GIL path is actually better for docmend.** That recommendation follows directly from CPython’s staged rollout and from the current “supported, non-default” status. [\[6\]](https://discuss.python.org/t/pep-703-making-the-global-interpreter-lock-optional-in-cpython-acceptance/37075)

## Phase timeline and primary-source status

| Date | Milestone | Primary-source meaning |
| --- | --- | --- |
| 2023-10-24 | PEP 703 accepted by the Steering Council | The SC accepted free-threading with a **gradual rollout** and defined the three stages: Phase I experimental, Phase II supported-but-not-default, Phase III default. It also said the idea of removing the GIL build would come **after** the default flip and only once usage had declined. [\[10\]](https://peps.python.org/pep-0703/) |
| Python 3.13 | Phase I lands | CPython docs say free-threaded binaries are available starting in 3.13, but 3.13’s own documentation still described the mode as experimental and warned of substantial single-threaded overhead. [\[11\]](https://docs.python.org/3/howto/free-threading-python.html) |
| 2025-03-13 | PEP 779 accepted | PEP 779 established the criteria for moving to **Phase II** and explicitly said the default-flip decision for Phase III is different and “left for a future PEP.” [\[12\]](https://peps.python.org/pep-0779/?utm_source=chatgpt.com) |
| Python 3.14 beta 3 / beta 4 | “Free-threaded Python is officially supported” | The 3.14 beta announcements and docs state that PEP 779 is in 3.14 and that free-threaded Python is officially supported. That is the practical start of Phase II. [\[13\]](https://blog.python.org/2025/06/python-3140-beta-3-is-here/) |
| Python 3.14 docs | Supported, still optional | The free-threading HOWTO and macOS installer docs show that free-threaded Python is supported, but still a separate, optional install; official macOS installers do **not** install it by default. [\[14\]](https://docs.python.org/3/howto/free-threading-python.html) |
| 2026-03-29 | PEP 803 approved | The Steering Council approved `abi3t`, calling it an important step aligned with the PEP 779 expectation that stable ABI support for free-threading should be prepared for Python 3.15. [\[15\]](https://discuss.python.org/t/pep-803-stable-abi-for-free-threaded-builds-packaging-thread/104976?page=6) |
| Python 3.15 beta docs | Packaging still settling; still not default | Python 3.15 docs introduce `abi3t`, but also say that at the time of writing common build tools did **not** yet support it. No CPython primary source I found says Phase III has started. [\[16\]](https://docs.python.org/3.15/whatsnew/3.15.html) |

The most important status statement is still the one in the PEP 779 acceptance record: **“any decision to transition to Phase III … is still undecided”**. That is the current load-bearing answer to your “when does multiprocessing overhead get retired?” question: there is no official Phase III date to plan around yet. [\[17\]](https://discuss.python.org/t/pep-779-criteria-for-supported-status-for-free-threaded-python/84319?page=7&utm_source=chatgpt.com)

My best estimate, clearly marked as an inference, is this:

- **Phase II is current reality**: yes, now, in Python 3.14+. [\[18\]](https://peps.python.org/pep-0779/?utm_source=chatgpt.com)
- **Phase III is not 3.15 by any primary-source reading available here**: 3.15 beta docs are still working through `abi3t` and tool support, and the Steering Council has not published a “default now” decision. [\[19\]](https://docs.python.org/3.15/whatsnew/3.15.html)
- **Earliest plausible Phase III window**: **3.16**, but only as a best-effort forecast. **3.16–3.17+** is more realistic if adoption continues but packaging and toolchain work remain the pacing item. That forecast is based on the fact that 3.15 is still finishing ABI groundwork and build-tool adoption, not on a formal CPython roadmap. [\[20\]](https://docs.python.org/3.15/whatsnew/3.15.html)

## Re-open trigger checklist

For docmend, the right trigger is not “free-threading exists.” It is “the free-threaded path is mature enough in the exact environments docmend supports.” The following checklist is concrete and testable.

### Release-channel triggers

Treat any one of the first two as a **hard re-open**:

- A stable CPython release makes the free-threaded build the **default build**, or the Steering Council accepts the future PEP that begins Phase III. That is the clearest official signal that process overhead should be challenged by default. [\[6\]](https://discuss.python.org/t/pep-703-making-the-global-interpreter-lock-optional-in-cpython-acceptance/37075)
- Your supported interpreter management channels treat free-threaded Python as a normal first-class option rather than a niche opt-in. Today, `uv` can discover and install free-threaded 3.13+ and will use free-threaded 3.14+ interpreters found on `PATH`, but it still prefers the GIL build for installs; official macOS installers still package free-threading as a separate optional install and do not install it by default. [\[21\]](https://docs.astral.sh/uv/concepts/python-versions/)

### Runtime-capability triggers

All of these should pass before you even bother comparing thread vs process performance:

- The interpreter build reports `sysconfig.get_config_var("Py_GIL_DISABLED") == 1`. CPython explicitly recommends that variable for build-configuration decisions. [\[8\]](https://docs.python.org/3/howto/free-threading-python.html)
- After importing the **full docmend application and all plugins/extensions you load in real use**, `sys._is_gil_enabled()` remains `False`. CPython documents that importing an unsupported C extension may auto-enable the GIL. If that happens, you are not benchmarking the architecture you think you are. [\[8\]](https://docs.python.org/3/howto/free-threading-python.html)
- Your CI includes at least one free-threaded job for each platform you claim to support. The Steering Council’s original PEP 703 acceptance post explicitly expected CI checks for free-threaded builds on major platforms in order to reach supported status; the same logic applies to your project-level decision gate. [\[22\]](https://discuss.python.org/t/pep-703-making-the-global-interpreter-lock-optional-in-cpython-acceptance/37075)

### Dependency-graph triggers

Require these for any planned switch:

- Every non-pure-Python dependency in the lockfile either publishes version-specific `cp3xyt` wheels for your supported platforms, or publishes `abi3t` / `abi3.abi3t` artifacts once your targeted Python/tooling stack can consume them. PEP 803 is the primary source for what those tags mean. [\[23\]](https://peps.python.org/pep-0803/)
- Where the package is pure Python, you still run the test suite on a free-threaded build; “no ABI blocker” is not the same thing as “thread-safe in shared-state use.” PEP 779 and the free-threading HOWTO are both explicit that some code must be redesigned to avoid performance pitfalls or races. [\[24\]](https://peps.python.org/pep-0779/?utm_source=chatgpt.com)

### Performance trigger

Only switch the default executor if the dedicated benchmark says all of the following are true:

- thread-pool throughput on a free-threaded build beats your current process-pool baseline on the representative corpus;
- the win holds across at least the small-file and medium-file regimes that dominate your real library;
- peak RSS is acceptable for your support targets;
- output bytes, hashes, and failure accounting are identical across executor types. [\[25\]](https://docs.python.org/3/library/hashlib.html)

A simple maintainable policy is: **switch only when the free-threaded thread pool is both operationally clean and measurably better.**

## Dependency readiness

The table below is intentionally strict about what the evidence means. A `py3-none-any` wheel means “no free-threaded ABI blocker.” It does **not** by itself mean the package has made an explicit free-threading support claim. A `cp314t` / `cp315t` wheel is stronger packaging evidence, but PEP 803 explicitly says loadability is still not the same thing as being thread-safe without the GIL. [\[23\]](https://peps.python.org/pep-0803/)

| Package | Latest evidence found | Wheel / ABI signal | Assessment for docmend |
| --- | --- | --- | --- |
| `charset-normalizer` | PyPI shows the free-threading classifier `Python :: Free Threading :: 4 - Resilient`, a universal wheel `charset_normalizer-3.4.7-py3-none-any.whl`, and multiple `cp314-cp314t` wheels including Linux and Windows builds. [\[26\]](https://pypi.org/project/charset-normalizer/) | Strong positive packaging signal for 3.14t; plus universal fallback. | **Most encouraging dependency in your stack.** It looks actively FT-aware. I did not confirm a `cp315t` wheel from the current PyPI page snapshot, so for 3.15t you should verify what artifact the resolver actually installs. [\[27\]](https://pypi.org/project/charset-normalizer/) |
| `rpds-py` | PyPI shows `rpds-py 2026.6.3` with explicit `cp314-cp314t` and `cp315-cp315t` wheels. [\[28\]](https://pypi.org/project/rpds-py/) | Strong positive binary-compatibility signal on both 3.14t and 3.15t. | **Ready-looking from a packaging standpoint.** Still remember that a loadable FT wheel is not itself proof of thread-safety semantics under shared-state use. [\[23\]](https://peps.python.org/pep-0803/) |
| `jsonschema` | PyPI shows `jsonschema 4.26.0` as `py3-none-any`. [\[29\]](https://pypi.org/project/jsonschema/) | No ABI blocker. | **Probably low risk for the executor decision**, because the package itself is pure Python. The relevant native edge here is `rpds-py`, not `jsonschema`’s own wheel. [\[30\]](https://pypi.org/project/jsonschema/) |
| `rich` | PyPI shows `rich-15.0.0-py3-none-any.whl`. [\[31\]](https://pypi.org/project/rich/) | No ABI blocker. | **Low risk** for the worker-executor decision. Rich is unlikely to be on the hot path for file transforms, but still run import and smoke tests on FT builds. [\[32\]](https://pypi.org/project/rich/) |
| `typer` | PyPI shows `typer 0.26.8` as `py3-none-any`; Typer’s own project page says that since `0.26.0` it has **vendored Click** rather than depending on it separately. [\[33\]](https://pypi.org/project/typer/) | No ABI blocker; Click may not be a third-party dependency at all if you are on modern Typer. | **Low ABI risk.** The main project-management implication is dependency accounting: if docmend is on Typer `>=0.26.0`, treat Click as vendored app code, not a separate external blocker. [\[34\]](https://pypi.org/project/typer/) |
| `click` | PyPI shows `click-8.4.2-py3-none-any.whl`. [\[35\]](https://pypi.org/project/click/) | No ABI blocker. | **Only relevant if you pin Click directly or use older Typer.** Otherwise the current Typer line has already internalized it. [\[36\]](https://pypi.org/project/typer/) |
| `pathspec` | PyPI shows `pathspec-1.1.1-py3-none-any.whl`. [\[37\]](https://pypi.org/project/pathspec/) | No ABI blocker. | **Low ABI risk.** Still worth free-threaded test coverage if any shared mutable caches or global matchers exist in your usage, but the packaging story is clean. [\[38\]](https://pypi.org/project/pathspec/) |

The short dependency read is: **nothing in your named graph currently looks like a show-stopper for experimenting on 3.14t/3.15t**, and `charset-normalizer` plus `rpds-py` are notably ahead of the pack in packaging evidence. The remaining uncertainty is not mainly “will it install?” but rather “does the full import graph keep the GIL disabled, and does the end-to-end workload actually scale better with threads?” [\[39\]](https://docs.python.org/3/howto/free-threading-python.html)

## Caveats and benchmark design

### Correctness and performance caveats

For `hashlib`, there are two important caveats.

First, **on regular GIL builds,** `hashlib` **already releases the GIL** when hashing more than 2047 bytes in a single constructor or `.update()` call. That means your SHA-256 stage already has some thread-level parallel potential today if you feed it large enough buffers. So if hashing dominates the workload, a future no-GIL switch may deliver less incremental benefit than expected; the real differentiator will be the parts of docmend that remain pure Python, especially charset detection and any normalization/repair loops. [\[40\]](https://docs.python.org/3/library/hashlib.html)

Second, `hashlib` has needed free-threading fixes in CPython itself. CPython tracked work to make the hashlib-related modules thread-safe without the GIL, and later also fixed a free-threading race involving objects returned by `hashlib.sha256()`. That is good news in the sense that the core runtime is actively hardening the path you care about, but it is also evidence that this area has been maturing in real time rather than being “done” for years already. [\[41\]](https://github.com/python/cpython/issues/111916?utm_source=chatgpt.com)

For **pure-Python hot loops**, CPython’s own docs still warn about extra single-thread overhead in free-threaded builds. The current 3.14 free-threading HOWTO reports average `pyperformance` overhead ranging from about **1% on macOS aarch64 to 8% on x86-64 Linux**, and PEP 779 says the phase-II target was to stay within a **15%** slowdown and around **20%** higher memory use on `pyperformance`. The same HOWTO also documents higher memory use and remaining behavioral caveats around iterators, frame locals, and concurrent access patterns. [\[42\]](https://docs.python.org/3/howto/free-threading-python.html)

That matters directly for docmend: free-threading is attractive because your work looks embarrassingly parallel across files, but the benefit only materializes if each worker mostly operates on **its own local objects**. CPython’s docs explicitly recommend using real synchronization rather than relying on the implementation details of built-in type locking, and they note that sharing iterators across threads is generally unsafe. In other words: thread-per-file is a good fit; shared mutable work queues, shared iterators, and shared caches are where you invite avoidable pain. [\[43\]](https://docs.python.org/3/howto/free-threading-python.html)

One more packaging caveat is worth making explicit because it is easy to miss: **a free-threaded wheel tag is not a correctness certificate**. PEP 803 states this outright: the new ABI makes extensions loadable on free-threaded Python, but not necessarily thread-safe without a GIL. That warning is especially relevant when you start treating `cp3xyt` or `abi3t` uploads as if they automatically mean “safe to parallelize heavily.” They do not. [\[23\]](https://peps.python.org/pep-0803/)

### Recommended benchmark design

Use a **switch benchmark**, not a synthetic “threading benchmark.” The job is to decide whether docmend should change its executor default, so the harness should benchmark **the real pipeline stages** under the executor strategies you actually might ship.

Run this matrix:

| Axis | Recommended settings |
| --- | --- |
| Interpreters | Current shipping baseline on regular Python 3.14; free-threaded Python 3.14; free-threaded Python 3.15 once your supported installer channel can provide it cleanly. Verify `Py_GIL_DISABLED == 1` and `sys._is_gil_enabled() is False` after importing the full app. [\[44\]](https://docs.python.org/3/howto/free-threading-python.html) |
| Executors | serial baseline; `ThreadPoolExecutor`; `ProcessPoolExecutor` with your current `forkserver` settings. Keep the worker function identical across modes. [\[45\]](https://docs.python.org/3/library/multiprocessing.html?utm_source=chatgpt.com) |
| Worker counts | `1`, `2`, `4`, `min(8, ncpu)`, `ncpu`, and optionally `2*ncpu` for over-subscription tests. |
| Corpora | Synthetic/public-domain only. At minimum: tiny files, medium files, large files; mixed encodings; malformed inputs; HTML-heavy inputs; plain-text-heavy inputs. |
| Storage modes | One CPU-isolated mode where output goes to tmpfs/RAM-disk to expose compute scaling; one realistic SSD mode to capture write-path behavior and atomic rename costs. |
| Metrics | files/sec, MB/sec, wall-clock, peak RSS, CPU utilization, startup-to-first-result latency, per-file error counts, and output equivalence. |
| Correctness | Same emitted Markdown bytes, same SHA-256 outputs, same failure classification, same retry/repair outcomes across all executor modes. |

The corpora should be intentionally skewed to reveal the decision boundary:

- **tiny-file corpus**: many files below the `hashlib` 2048-byte threshold, because this is where GIL-era threads benefit least from hashing and where process overhead may dominate; [\[40\]](https://docs.python.org/3/library/hashlib.html)
- **medium-file corpus**: typical legacy docs where charset detection and text cleanup do meaningful CPU work;
- **large-file corpus**: enough data that hashing and writes become significant and may already overlap well due to GIL release around hashing and I/O. [\[46\]](https://docs.python.org/3/library/hashlib.html)

I would make the project’s switch rule conservative:

- switch the default only if free-threaded threads beat today’s process-pool baseline by a **clear margin** on the representative corpus, not just on one special case;
- require **zero correctness drift**;
- require that the full import graph does **not** turn the GIL back on;
- require that memory growth remains operationally acceptable on your support targets. [\[47\]](https://docs.python.org/3/howto/free-threading-python.html)

For docmend specifically, I would weight the result by **small and medium files** more heavily than by very large files. Large-file SHA-256 work is partly a solved problem already because `hashlib` releases the GIL on large buffers; the architectural upside of free-threading is strongest where pure-Python per-file work and process overhead are both significant. [\[40\]](https://docs.python.org/3/library/hashlib.html)

### Version and date sensitivity

This topic is unusually date-sensitive.

The status conclusions in this report are anchored to sources visible on **2026-07-05**. The most time-sensitive items are: whether the Steering Council has started Phase III; whether Python 3.15 final changes any of the `abi3t` / build-tool support caveats now visible in beta docs; whether `uv` changes its free-threaded selection defaults again; and whether your native dependencies add or remove `cp315t` / `abi3t` coverage in later releases. [\[48\]](https://discuss.python.org/t/pep-779-criteria-for-supported-status-for-free-threaded-python/84319?page=7&utm_source=chatgpt.com)

The safest project policy is therefore to treat the re-open decision as a **release-gated check**, not as a one-time strategic guess. Re-run the checklist whenever you move the supported Python floor, whenever your lockfile changes in ways that add C/Rust extensions, or whenever CPython announces a Phase III decision. [\[49\]](https://discuss.python.org/t/pep-703-making-the-global-interpreter-lock-optional-in-cpython-acceptance/37075)

## Sources

- PEP 703 and its acceptance record. [\[10\]](https://peps.python.org/pep-0703/)
- PEP 779 and its acceptance/status record. [\[50\]](https://peps.python.org/pep-0779/?utm_source=chatgpt.com)
- CPython free-threading HOWTO and thread-safety documentation. [\[51\]](https://docs.python.org/3/howto/free-threading-python.html)
- Python 3.13, 3.14, and 3.15 “What’s New” / release notes. [\[52\]](https://docs.python.org/3/whatsnew/3.13.html?utm_source=chatgpt.com)
- PEP 803 and the Steering Council approval record for `abi3t`. [\[53\]](https://peps.python.org/pep-0803/)
- Official/macOS installer docs and `uv` interpreter-selection docs. [\[7\]](https://docs.python.org/3/using/mac.html)
- `hashlib` documentation and CPython issue/changelog records for no-GIL thread-safety work. [\[54\]](https://docs.python.org/3/library/hashlib.html)
- PyPI package metadata for `charset-normalizer`, `rpds-py`, `jsonschema`, `rich`, `typer`, `click`, and `pathspec`. [\[55\]](https://pypi.org/project/charset-normalizer/)

---

[\[1\]](https://discuss.python.org/t/pep-703-making-the-global-interpreter-lock-optional-in-cpython-acceptance/37075) [\[6\]](https://discuss.python.org/t/pep-703-making-the-global-interpreter-lock-optional-in-cpython-acceptance/37075) [\[22\]](https://discuss.python.org/t/pep-703-making-the-global-interpreter-lock-optional-in-cpython-acceptance/37075) [\[49\]](https://discuss.python.org/t/pep-703-making-the-global-interpreter-lock-optional-in-cpython-acceptance/37075) PEP 703 (Making the Global Interpreter Lock Optional in CPython) acceptance - Core Development - Discussions on Python.org

<https://discuss.python.org/t/pep-703-making-the-global-interpreter-lock-optional-in-cpython-acceptance/37075>

[\[2\]](https://docs.python.org/3.15/whatsnew/3.15.html) [\[16\]](https://docs.python.org/3.15/whatsnew/3.15.html) [\[19\]](https://docs.python.org/3.15/whatsnew/3.15.html) [\[20\]](https://docs.python.org/3.15/whatsnew/3.15.html) What’s new in Python 3.15 — Python 3.15.0b3 documentation

<https://docs.python.org/3.15/whatsnew/3.15.html>

[\[3\]](https://docs.python.org/3/howto/free-threading-python.html) [\[8\]](https://docs.python.org/3/howto/free-threading-python.html) [\[9\]](https://docs.python.org/3/howto/free-threading-python.html) [\[11\]](https://docs.python.org/3/howto/free-threading-python.html) [\[14\]](https://docs.python.org/3/howto/free-threading-python.html) [\[39\]](https://docs.python.org/3/howto/free-threading-python.html) [\[42\]](https://docs.python.org/3/howto/free-threading-python.html) [\[43\]](https://docs.python.org/3/howto/free-threading-python.html) [\[44\]](https://docs.python.org/3/howto/free-threading-python.html) [\[47\]](https://docs.python.org/3/howto/free-threading-python.html) [\[51\]](https://docs.python.org/3/howto/free-threading-python.html) Python support for free threading — Python 3.14.6 documentation

<https://docs.python.org/3/howto/free-threading-python.html>

[\[4\]](https://pypi.org/project/rpds-py/) [\[28\]](https://pypi.org/project/rpds-py/) rpds-py · PyPI

<https://pypi.org/project/rpds-py/>

[\[5\]](https://docs.python.org/3/using/mac.html) [\[7\]](https://docs.python.org/3/using/mac.html) 5. Using Python on macOS — Python 3.14.6 documentation

<https://docs.python.org/3/using/mac.html>

[\[10\]](https://peps.python.org/pep-0703/) PEP 703 – Making the Global Interpreter Lock Optional in CPython \| peps.python.org

<https://peps.python.org/pep-0703/>

[\[12\]](https://peps.python.org/pep-0779/?utm_source=chatgpt.com) [\[18\]](https://peps.python.org/pep-0779/?utm_source=chatgpt.com) [\[24\]](https://peps.python.org/pep-0779/?utm_source=chatgpt.com) [\[50\]](https://peps.python.org/pep-0779/?utm_source=chatgpt.com) PEP 779 – Criteria for supported status for free-threaded Python

<https://peps.python.org/pep-0779/?utm_source=chatgpt.com>

[\[13\]](https://blog.python.org/2025/06/python-3140-beta-3-is-here/) Python 3.14.0 beta 3 is here! \| Python Insider

<https://blog.python.org/2025/06/python-3140-beta-3-is-here/>

[\[15\]](https://discuss.python.org/t/pep-803-stable-abi-for-free-threaded-builds-packaging-thread/104976?page=6) PEP 803: Stable ABI for Free-Threaded Builds (packaging thread) - Page 6 - Packaging - Discussions on Python.org

<https://discuss.python.org/t/pep-803-stable-abi-for-free-threaded-builds-packaging-thread/104976?page=6>

[\[17\]](https://discuss.python.org/t/pep-779-criteria-for-supported-status-for-free-threaded-python/84319?page=7&utm_source=chatgpt.com) [\[48\]](https://discuss.python.org/t/pep-779-criteria-for-supported-status-for-free-threaded-python/84319?page=7&utm_source=chatgpt.com) PEP 779: Criteria for supported status for free-threaded Python

<https://discuss.python.org/t/pep-779-criteria-for-supported-status-for-free-threaded-python/84319?page=7&utm_source=chatgpt.com>

[\[21\]](https://docs.astral.sh/uv/concepts/python-versions/) Python versions \| uv

<https://docs.astral.sh/uv/concepts/python-versions/>

[\[23\]](https://peps.python.org/pep-0803/) [\[53\]](https://peps.python.org/pep-0803/) PEP 803 – “abi3t”: Stable ABI for Free-Threaded Builds \| peps.python.org

<https://peps.python.org/pep-0803/>

[\[25\]](https://docs.python.org/3/library/hashlib.html) [\[40\]](https://docs.python.org/3/library/hashlib.html) [\[46\]](https://docs.python.org/3/library/hashlib.html) [\[54\]](https://docs.python.org/3/library/hashlib.html) hashlib — Secure hashes and message digests — Python 3.14.6 documentation

<https://docs.python.org/3/library/hashlib.html>

[\[26\]](https://pypi.org/project/charset-normalizer/) [\[27\]](https://pypi.org/project/charset-normalizer/) [\[55\]](https://pypi.org/project/charset-normalizer/) charset-normalizer · PyPI

<https://pypi.org/project/charset-normalizer/>

[\[29\]](https://pypi.org/project/jsonschema/) [\[30\]](https://pypi.org/project/jsonschema/) jsonschema · PyPI

<https://pypi.org/project/jsonschema/>

[\[31\]](https://pypi.org/project/rich/) [\[32\]](https://pypi.org/project/rich/) rich · PyPI

<https://pypi.org/project/rich/>

[\[33\]](https://pypi.org/project/typer/) [\[34\]](https://pypi.org/project/typer/) [\[36\]](https://pypi.org/project/typer/) typer · PyPI

<https://pypi.org/project/typer/>

[\[35\]](https://pypi.org/project/click/) click · PyPI

<https://pypi.org/project/click/>

[\[37\]](https://pypi.org/project/pathspec/) [\[38\]](https://pypi.org/project/pathspec/) pathspec · PyPI

<https://pypi.org/project/pathspec/>

[\[41\]](https://github.com/python/cpython/issues/111916?utm_source=chatgpt.com) Make hashlib related modules thread-safe without the GIL

<https://github.com/python/cpython/issues/111916?utm_source=chatgpt.com>

[\[45\]](https://docs.python.org/3/library/multiprocessing.html?utm_source=chatgpt.com) multiprocessing — Process-based parallelism

<https://docs.python.org/3/library/multiprocessing.html?utm_source=chatgpt.com>

[\[52\]](https://docs.python.org/3/whatsnew/3.13.html?utm_source=chatgpt.com) What's New In Python 3.13

<https://docs.python.org/3/whatsnew/3.13.html?utm_source=chatgpt.com>
