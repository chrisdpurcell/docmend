# Structured Logging Library and Format for a Long-Running Batch CLI

**Date:** 2026-07-05 **Related:** GAP-19 · `docs/specs/docmend.md` §7.2 NFR-003 (Observability), §7.3 IR-005 (`--verbose`/`--quiet`), §18.5 (Observability), §19 MS-0 item 3 ("Logging framework and run-ID/artifact conventions"), §8.6 (Dependency Policy) · no existing `OQ-` row covers this decision today — see Reconciliation notes.

**Gap it fills:** The spec requires "structured per-file logs with a per-run correlation" and per-file/per-run detail "sufficient to diagnose issues mid-batch without re-running" (NFR-003, §18.5), and it already names the `--verbose`/`--quiet` flags in IR-005, but nowhere does it pick a logging library, a wire format, a concrete field schema, a file/console destination policy, a rotation/retention rule, or a verbosity-to-level mapping. MS-0 item 3 ("Logging framework and run-ID/artifact conventions") is currently a one-line placeholder. This report closes that gap with an evidence-backed recommendation sized to docmend's actual shape: an offline, single-user, Python 3.14 batch CLI over 100k+ files, not a networked service.

## Executive Summary and Recommendation

**Recommend: `structlog`, wired through the standard library's logging handlers, emitting JSON Lines (JSONL) to a per-run file and human-readable text to the console.** Do not add `loguru`. Do not build the JSONL formatter from scratch on bare stdlib `logging` either, though bare stdlib remains an acceptable fallback if the project later decides against adding any structured-logging dependency.

Three findings drove this over the alternative (stdlib-only, or loguru):

1. **Performance favors structlog at this file count.** Independent benchmarks on Python 3.14 show structlog roughly 2x faster than both stdlib+`json` and loguru for a simple structured message, and it stays fastest as context fields are added ([Dash0, 2026](https://www.dash0.com/guides/python-logging-libraries); corroborating numbers from an independent benchmark suite: [hangukquant.com](https://www.research.hangukquant.com/p/designing-state-of-the-art-logging)). At 100k+ files with multiple log lines per file (NFR-001), per-call logging overhead is not negligible.
2. **Loguru shows a real maintenance-freshness gap relative to Python 3.14.** Its last release (`0.7.3`) shipped 2024-12-06 — before Python 3.14's 2025-10-07 release ([PyPI](https://pypi.org/project/loguru/); [python.org](https://www.python.org/downloads/release/python-3140/)) — and as of this research date the maintainer has an open, unanswered issue asking about the next release ([GitHub issue #1375](https://github.com/Delgan/loguru/issues/1375)). Loguru is not necessarily _broken_ on 3.14 (it is pure Python plus small platform shims), but there is no maintainer-confirmed compatibility statement, which matters for a project whose C-001 constraint pins Python 3.14+. structlog, by contrast, ships active releases (latest `25.5.0`, changelog entries dated within the last release cycle) from a maintainer (Hynek Schlawack) with a strong track record on packaging/typing correctness ([structlog CHANGELOG](https://github.com/hynek/structlog/blob/main/CHANGELOG.md)).
3. **structlog composes with stdlib handlers instead of replacing them**, which matters directly for two of docmend's own requirements: NFR-001's "parallel and batch operation" (stdlib's `QueueHandler`/`QueueListener` is the documented-safe pattern for multi-process-safe log writes — [Python Logging Cookbook](https://docs.python.org/3/howto/logging-cookbook.html)) and the already-approved `rich` dependency (§8.6) for console rendering. structlog's `ProcessorFormatter` lets the same event dictionary be rendered as JSON for a file handler and as colored text for a console handler from one call site ([structlog: Standard Library Logging](https://www.structlog.org/en/stable/standard-library.html)).

If the project's dependency-minimalism preference outweighs the performance/ergonomics gain, bare stdlib `logging` configured to emit one JSON object per line (via a small custom `Formatter`, optionally accelerated with `orjson`) is a legitimate fallback — the Dash0 benchmark shows swapping stdlib's JSON encoder for `orjson` closes most of the gap with structlog (139k -> 185k ops/s at 10 context fields). This is not a false economy either way; it is a real trade-off worth an explicit `OQ-` decision (see Reconciliation notes).

## Comparison: stdlib logging vs. structlog vs. loguru

| Dimension | stdlib `logging` | `structlog` | `loguru` |
| --- | --- | --- | --- |
| Structured/JSON output | Manual: needs a custom `Formatter`/filter to emit JSON; no built-in event-dict model. | Native: processor pipeline builds a dict; `JSONRenderer` renders it; integrates with stdlib via `ProcessorFormatter` ([docs](https://www.structlog.org/en/stable/standard-library.html)). | Native: `logger.add(sink, serialize=True)` emits JSON per record; custom sink functions can hand-pick fields ([docs](https://loguru.readthedocs.io/)). |
| Performance (10 context fields, Python 3.14, null sink) | ~7.0 µs / 139k ops/s with stdlib `json`; ~5.4 µs / 185k ops/s with `orjson` swapped in. | ~4.05 µs / 242k ops/s — fastest of the three. | ~6.76 µs / 147k ops/s. |
| Source of benchmark | — [Dash0, 2026](https://www.dash0.com/guides/python-logging-libraries) (Python 3.14, pytest-benchmark); corroborated in relative ordering by [hangukquant.com](https://www.research.hangukquant.com/p/designing-state-of-the-art-logging). | Same. | Same. |
| Rich console integration | Via `rich.logging.RichHandler` attached as a normal handler ([Rich docs](https://rich.readthedocs.io/en/stable/logging.html)). | Native: `structlog.dev.ConsoleRenderer()` auto-detects and uses `rich` for pretty tracebacks when installed and stderr is a TTY; falls back cleanly otherwise ([structlog logging-best-practices](https://github.com/hynek/structlog/blob/main/docs/logging-best-practices.md)). | Supported by adding a `RichHandler` as a sink (`logger.add(RichHandler())`), but community reports show rough edges with duplicate/garbled exception output in that combination ([GitHub issue #1172](https://github.com/Delgan/loguru/issues/1172)). |
| Run-ID / correlation binding | Manual: thread through `extra=` on every call, or a custom `Filter`. | `structlog.contextvars` — bind once per run/file, every subsequent log call in that context carries it automatically, including across `async`/thread boundaries via `contextvars` ([structlog contextvars docs](https://github.com/hynek/structlog/blob/main/docs/contextvars.md)). | `logger.bind(request_id=...)` returns a new bound logger; workable but re-binds must be threaded through call sites explicitly (no automatic context propagation without stdlib `contextvars` glue). |
| Rotation/retention | `logging.handlers.RotatingFileHandler` (size) / `TimedRotatingFileHandler` (time) — mature, well-documented, but designed for continuously-running services, not discrete batch runs ([Python docs](https://docs.python.org/3/library/logging.handlers.html)). | Rides on the same stdlib handlers (structlog is a processing/formatting layer, not a handler/sink layer). | Native and very convenient: `rotation=`, `retention=`, `compression=` on `logger.add()` in one call ([loguru docs](https://loguru.readthedocs.io/)). This is loguru's strongest feature — see below for why it is still not decisive here. |
| Multiprocess-safety | `QueueHandler` + `QueueListener` is the documented-correct pattern; stdlib's plain `FileHandler` family does **not** coordinate across processes ([Logging Cookbook](https://docs.python.org/3/howto/logging-cookbook.html)). | Same underlying mechanism (structlog sits above stdlib handlers). | `logger.add(sink, enqueue=True)` — a built-in, one-line equivalent, documented specifically for Linux multiprocessing ([loguru recipes](https://github.com/delgan/loguru/blob/master/docs/resources/recipes.md)). |
| Python 3.14 support signal | Part of the stdlib; ships with 3.14 by definition. | Actively released; latest `25.5.0` postdates 3.14's GA and targets current CPython behavior (e.g., new `CallsiteParameter.QUAL_MODULE`) ([release notes](https://github.com/hynek/structlog/releases)). | Last release `0.7.3` predates 3.14 GA by ~10 months; no confirmed-compatible release since, and an open unanswered "when's the next release" issue ([issue #1375](https://github.com/Delgan/loguru/issues/1375)). |
| Dependency footprint | None (stdlib). | One pure-Python package, no transitive deps beyond typing-extensions on old Pythons. | One package; historically pulled `colorama`/`win32-setctime` on Windows only, none on Linux. |
| Community sentiment (2026) | "Powerful but not friendly out of the box" — near-universal complaint about stdlib's `dictConfig` boilerplate. | Praised for correctness/composability, criticized for a steeper initial learning curve (bound loggers, processor chains) ([Dash0 guide](https://www.dash0.com/guides/python-logging-libraries)). | Praised for one-line ergonomics; multiple 2026 sources explicitly still recommend it for quick/hobby use but suggest migrating to structlog for anything production/scale-sensitive ([Reddit r/Python thread](https://www.reddit.com/r/Python/comments/1o4uyrv/advice_on_logging_libraries_logfire_loguru_or/)). |

**Why loguru's built-in rotation is not decisive despite being genuinely nice:** loguru's `rotation=`/`retention=` API is real usability leverage, but it targets the wrong lifecycle model for docmend. docmend does not run as a resident service that needs to prune an ever-growing log directory on a schedule — each invocation of `scan`/`plan`/`apply`/`verify` is already a discrete, artifact-producing run (DR-001–DR-004), and §7.4 already states the project's retention philosophy: "artifacts and backups are retained until the user explicitly purges them; the tool never deletes its own manifests or backups." A generic time/size rotation-and-delete policy (loguru's `retention="10 days"`, or stdlib's `TimedRotatingFileHandler` `backupCount`) would silently violate that policy for logs specifically, creating an inconsistency between how docmend treats its JSON artifacts and how it treats its logs. See the destination/rotation policy below for the batch-shaped alternative this points to.

## Recommended Wire Format: JSON Lines (JSONL)

One JSON object per line, UTF-8, no pretty-printing, to the file destination; a separate human-readable renderer (`ConsoleRenderer`, optionally through `RichHandler`) to the console destination. This is the converged recommendation across every structured-logging guide surveyed: consistent field names, ISO 8601 UTC timestamps, and one-object-per-line for streamability are the repeated baseline requirements ([Better Stack: JSON Logging](https://betterstack.com/community/guides/logging/json-logging/); [Uptrace: Structured Logging](https://uptrace.dev/glossary/structured-logging); [SigNoz: What Is Structured Logging](https://signoz.io/blog/structured-logs/); [Dash0: JSON Logging](https://www.dash0.com/guides/json-logging)). JSONL specifically (rather than a single JSON array) is what lets an interrupted run (crash mid-batch, per FR-013/AW-001) leave a valid, line-truncatable, `grep`/`jq`-able log rather than a single malformed JSON document — directly relevant to docmend's resumability requirements.

Plain text remains reasonable for the console (humans reading a live run benefit from color and alignment, not raw JSON), which is exactly the split structlog's `ConsoleRenderer`/`JSONRenderer` pair is designed for ([structlog logging-best-practices.md](https://github.com/hynek/structlog/blob/main/docs/logging-best-practices.md)).

## Recommended JSONL Field Schema

Field names are deliberately short (line-count matters at 100k+ files) but follow the same mechanical/semantic-field discipline the spec already uses for frontmatter (§9) and the same reason-code discipline used for `ERR-`/`EC-` IDs (§12.1, §10.3):

```json
{
	"ts": "2026-07-05T14:22:03.512381+00:00",
	"level": "INFO",
	"run_id": "run_20260705T142150Z_8f3a1c",
	"command": "apply",
	"event": "file.skipped",
	"path": "fixtures/synthetic/example.txt",
	"action": "skip",
	"reason": "low_confidence_encoding",
	"detail": { "confidence": 0.62, "encoding": "windows-1252" },
	"duration_ms": 1.8,
	"pid": 48213,
	"worker": "w2",
	"exc_info": null
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `ts` | Yes | ISO 8601, UTC, microsecond precision. Matches the "ISO 8601 timestamp in UTC" baseline recommended across every structured-logging source surveyed ([Uptrace](https://uptrace.dev/glossary/structured-logging)). |
| `level` | Yes | One of `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` — stdlib's names, since structlog's `add_log_level` processor reuses them. |
| `run_id` | Yes | **Must be the same identifier already recorded in DR-001–DR-004 artifacts** (§18.5 already requires "per-run correlation (run ID recorded in artifacts)"). This is the single field that makes a log line and an artifact record cross-referenceable — the concrete mechanism behind NFR-003. |
| `command` | Yes | `scan`/`plan`/`apply`/`verify` — mirrors IR-001–IR-004. |
| `event` | Yes | A small, closed, dotted vocabulary (`file.scanned`, `file.planned`, `file.skipped`, `file.applied`, `file.failed`, `run.started`, `run.completed`), not free prose — mirrors the project's existing discipline of stable `ERR-`/`EC-`/`AW-` IDs (§12.1, §10.3, §10.2) so log lines are machine-groupable, not just human-readable. |
| `path` | When file-scoped | **Relative to the source root only, never absolute.** Absolute paths risk leaking the owner's real directory structure into a log that could be pasted into an issue or shared for debugging — this is the same threat already named in §13.5 ("Private content leakage via artifacts or logs shared/committed publicly") and the same posture as §13.6's existing note that "logs carry paths and hashes, not document content, at default verbosity." |
| `action` | Optional | `rename`/`rewrite`/`skip`/`overwrite`/`error` — reuses the plan/report action taxonomy (FR-010, FR-011) instead of inventing a parallel one. |
| `reason` | When skipped/failed | A stable machine reason code, not a sentence — reuses/extends the `ERR-`/`EC-` vocabulary (e.g. `low_confidence_encoding`, `nul_bytes`, `hash_mismatch`) so a downstream `jq` query can bucket a run's skip pile the same way the report's summary counts do (DR-003). |
| `detail` | Optional | Free-form structured context (confidence scores, hash prefixes, byte offsets). **Never document body content** — same constraint as `path`. |
| `duration_ms` | Optional | Per-file or per-phase timing; useful for the OQ-010 performance-target work later without adding a separate profiling system. |
| `pid` / `worker` | Optional | Only meaningful once NFR-001's "parallel... operation" lands; include the fields now so the schema does not need a breaking change later. |
| `exc_info` | On exceptions | structlog's `format_exc_info`/`dict_tracebacks` processor renders this as structured data rather than an embedded string blob, keeping the line valid JSON and `jq`-queryable ([structlog standard-library.md](https://github.com/hynek/structlog/blob/main/docs/standard-library.md)). |

This does not need a checked-in JSON Schema the way DR-001–DR-004 do (OQ-004) — logs are diagnostic, not a durable contract other tools parse against a version — but the field list above should be pinned in the same implementation pass as the logging framework itself (MS-0 item 3) so it does not drift silently across the pipeline layers.

## Destination and Rotation/Retention Policy

Tailored to docmend's actual lifecycle (discrete batch runs, not a resident service), not a generic microservice template:

- **Console:** human-readable, colorized when `sys.stderr.isatty()`, via structlog's `ConsoleRenderer()` (auto-uses `rich` for tracebacks if installed — no extra wiring needed given `rich` is already an approved dependency, §8.6). Written to **stderr**, not stdout, so machine-readable output (report/manifest JSON on stdout, if the CLI ever pipes it) is never interleaved with human log noise — this is the same separation stdlib's own docs assume implicitly and that every CLI-logging guide surveyed recommends ([xahteiwi.eu](https://xahteiwi.eu/resources/hints-and-kinks/python-cli-logging-options/)).
- **File:** JSONL, **one file per run**, named with the run ID that already appears in the artifacts (e.g. `logs/docmend-{run_id}.jsonl`), not a continuously-appended rotated file. This is the key departure from generic advice: `RotatingFileHandler`/`TimedRotatingFileHandler`/loguru's `rotation=` all solve "one long-lived log file needs to be kept from growing forever," which is the resident-service problem. docmend's problem is the opposite — each run is already bounded and already produces bounded, purge-on-request artifacts (§7.4, §18.6). One file per run:
  - Makes the log a first-class sibling of `inventory.json`/`plan.json`/`report.json`/`manifest.json` rather than an orphaned, differently-governed artifact.
  - Never needs `backupCount`/`retention=` semantics that would contradict §7.4's "the tool never deletes its own manifests or backups" — the same rule should extend to logs, and the deep-research note here recommends the spec say so explicitly (see Reconciliation notes).
  - Sidesteps the multi-process file-rotation-coordination problem entirely for the common case (single log destination, workers write via a queue — see below) since there is no rotation boundary to race on.
- **Size safety valve (not retention):** for a 100k+-file run, a single JSONL file can still grow to multiple GiB. Recommend an optional, off-by-default, purely mechanical split at a large size threshold (e.g. 512 MiB) that continues the **same run** into `docmend-{run_id}.part002.jsonl`, etc. — a size cap for practical file handling (so `less`/editors/`jq` do not choke on one giant file), explicitly _not_ a retention/deletion mechanism. This reuses the _mechanism_ of `RotatingFileHandler` (size-triggered rollover) without adopting its _policy_ (`backupCount`-driven deletion of old parts).
- **Retention/purge:** identical to every other docmend artifact — retained until the user explicitly purges it (§7.4, §18.6). docmend should not auto-delete old run logs any more than it auto-deletes old manifests.

## `--verbose`/`--quiet` to Level Mapping

The established CLI convention — corroborated across independent sources (a Python core-adjacent discussion, a widely cited CLI-logging how-to, and the `click-log` package's own documented pattern) — is: a sane default that is not silent, `-v`/`--verbose` (repeatable) raises verbosity, `-q`/`--quiet` caps it down to errors only ([discuss.python.org](https://discuss.python.org/t/setting-log-level-based-on-quiet-debug-flags/55570); [xahteiwi.eu](https://xahteiwi.eu/resources/hints-and-kinks/python-cli-logging-options/); [click-log docs](https://click-log.readthedocs.io/)). IR-005 already commits docmend to exactly this shape ("`--quiet` limits output to errors and critical messages").

The recommendation tailored to docmend adds one deliberate asymmetry: **`--verbose`/`--quiet` govern the console renderer only — the JSONL file sink always logs at a fixed floor (default `DEBUG`) regardless of the flags.** Rationale: NFR-003's whole purpose is to make a run "diagnosable... without re-running." If `--quiet` also silenced the file record, a quiet production run's failure would be undiagnosable after the fact — exactly the failure mode NFR-003 exists to prevent. Decoupling console verbosity from file verbosity is a small, explicit design choice worth recording as its own line item, not an accident of implementation.

| Flag | Console level | File (JSONL) level | Notes |
| --- | --- | --- | --- |
| `--quiet` / `-q` | `ERROR` (errors and critical only) | `DEBUG` (unchanged) | Matches IR-005's literal text. If both `-q` and `-v` are given, `--quiet` wins and a one-line warning is emitted noting the conflict (fail loud, not silently pick one). |
| _(default, no flag)_ | `WARNING`, plus explicit `run.started`/`run.completed` and per-run summary lines forced through at `INFO` regardless | `DEBUG` | At 100k+ files, per-file `INFO` noise on every default run would defeat the console's purpose; the summary line is what tells the operator the run is alive and what happened, matching §18.5's "job records" framing. |
| `-v` | `INFO` (per-file outcomes: converted/renamed/skipped, with `reason`) | `DEBUG` | Matches the staged-rollout workflow (§18.4): run a filtered subset with `-v` to review outcomes interactively before widening. |
| `-vv` | `DEBUG` (per-transform decisions, timing, low-level detail) | `DEBUG` | For troubleshooting a specific file or file class; not intended for a full 100k-file run. |

Implementation note for Typer (already the chosen CLI framework, §8.6): a repeatable counting option (`typer.Option(0, "--verbose", "-v", count=True)`) plus a boolean `--quiet`/`-q` flag map directly onto the table above; Typer/Click's own ecosystem already documents this exact pattern (`click-loglevel`, `click-log`) even though neither package itself needs to become a dependency — the mapping is simple enough to implement directly in the CLI shell layer (§8.2.3) with no additional dependency.

## Multiprocessing Caveat Specific to Python 3.14

NFR-001 allows "parallel and batch operation." Two independent facts compound into a real footgun worth flagging now, before MS-0 wiring hardens:

1. Stdlib's plain `FileHandler`/`RotatingFileHandler` family **does not coordinate writes across processes** — concurrent processes writing the same file can interleave or corrupt lines. The documented-correct fix is `QueueHandler` (in each worker) feeding a single `QueueListener` (in one process) that owns the actual file handler ([Python Logging Cookbook](https://docs.python.org/3/howto/logging-cookbook.html); corroborated independently by [Stack Overflow #641420](https://stackoverflow.com/questions/641420/how-should-i-log-while-using-multiprocessing-in-python) and [Stack Overflow #47968861](https://stackoverflow.com/questions/47968861/does-python-logging-support-multiprocessing)).
2. **Python 3.14 changed the default `multiprocessing` start method on Linux and BSD from `fork` to `forkserver`** ([What's New in Python 3.14](https://docs.python.org/3/whatsnew/3.14.html); corroborated by [versionlog.com's 3.14 summary](https://versionlog.com/python/3.14/), which specifically calls out that code relying on "child processes inheriting module-level state or open file descriptors from a fork" will now behave differently and must "make initialization explicit"). docmend's own A-001 constraint assumes a POSIX filesystem and, implicitly, Linux — so this default-start-method change applies directly. Any logging setup that implicitly relies on fork-inherited file handles or a pre-configured module-level logger existing in a worker (a common shortcut in fork-based code, including several of loguru's own historical multiprocessing recipes) needs explicit, per-worker initialization under 3.14's new default — the `QueueHandler`-per-worker pattern already satisfies this because it does not depend on inherited state, but a "just fork and let the child reuse the parent's open file handle" shortcut would not.

**Recommendation:** if/when NFR-001's parallelism lands, use `QueueHandler` per worker + one `QueueListener` owning the JSONL file handle, explicitly initialized in each worker's entry point rather than assumed inherited — this is correct under both `fork` and `forkserver` and removes the 3.14 start-method change as a variable entirely.

## Rich Integration

docmend already lists `rich` as an approved dependency for "human-readable console reporting alongside plain JSON artifacts" (§8.6). Two integration paths exist and either satisfies the spec:

- **structlog-native (recommended):** `structlog.dev.ConsoleRenderer()` automatically produces `rich`-rendered tracebacks when `rich` is importable and stderr is a TTY, with zero extra wiring beyond having `rich` installed ([structlog logging-best-practices.md](https://github.com/hynek/structlog/blob/main/docs/logging-best-practices.md)).
- **Explicit `RichHandler` bridge:** attach `rich.logging.RichHandler` as a stdlib handler that structlog's `ProcessorFormatter` feeds into, giving full control over Rich's column layout (time/level/path columns) ([Rich logging docs](https://rich.readthedocs.io/en/stable/logging.html)). This is the better choice only if docmend later wants Rich progress bars/spinners driven from the same console session as log output, since it keeps everything on one `rich.console.Console` instance.

Either path is compatible with the recommendation; the first requires less code and is the default suggestion.

## Dependency Policy Consequence

§8.6's dependency table does not currently list a logging library — `structlog` would be a new entry, and per that section's own rule ("introducing a dependency not listed here requires an OQ- entry and owner approval"), this recommendation should not be treated as self-executing. It is written as _evidence for_ an `OQ-` decision, not a substitute for one (see Reconciliation notes below).

## Open Questions Surfaced by This Research

| # | Question | Why unresolved |
| --- | --- | --- |
| 1 | Should the JSONL field list above be pinned as a checked-in schema (like DR-001–DR-004) or treated as an implementation detail with no versioning contract? | Logs are diagnostic rather than a cross-tool artifact contract today, but if a future log-aggregation/search integration is ever added (WH-007-adjacent), an unpinned schema would need retrofitting. |
| 2 | Exact size threshold and part-file naming for the "size safety valve" split described above. | No numeric target exists yet; should likely be set alongside OQ-010's performance-target work rather than guessed here. |

## Reconciliation Notes

Fold this research back into:

- **`docs/specs/docmend.md` §8.6 (Dependency Policy):** add a row for the chosen logging library once the owner approves it, per that section's own approval rule.
- **`docs/specs/docmend.md` §18.5 (Observability):** replace the current one-line "structured per-file logs with a per-run correlation" with a pointer to this report's JSONL schema and destination/rotation policy, or inline the schema table directly.
- **`docs/specs/docmend.md` §7.3 IR-005:** add the concrete `--verbose`/`--quiet`-to-level table above so MS-3's CLI-experience milestone has a testable mapping instead of prose.
- **`docs/specs/docmend.md` §7.4 / §18.6:** add one sentence extending the existing "artifacts and backups are retained until the user explicitly purges them" retention rule to logs explicitly, since this report's rotation recommendation depends on that extension being spec text, not just research-report advice.
- **`docs/open-questions.md`:** this topic currently has no `OQ-` row. Recommend adding an `OQ-015` ("logging library, JSONL schema, and destination/rotation policy") that cites this report the way OQ-008/OQ-011 cite their respective research reports, with Agent notes summarizing the Executive Summary above. This also happens to be a second, independent example of the drift pattern already flagged elsewhere in this session (open questions existing without a corresponding spec §21 row) — worth fixing in the same pass as the other OQ/spec-table reconciliation.
- **`docs/deep-research-queue.md`:** move this from an implicit ad hoc request into the tracked table (topic: "Structured logging library and format," report: this file, reconciled into: the spec references above) so the queue's own bookkeeping stays accurate.

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://www.dash0.com/guides/python-logging-libraries> | Choosing a Python Logging Library in 2026 | 2026 | [blog] |
| <https://www.research.hangukquant.com/p/designing-state-of-the-art-logging> | Designing State-of-the-Art Logging in Python | 2026 | [blog] |
| <https://betterstack.com/community/guides/logging/best-python-logging-libraries> | Logging in Python: A Comparison of the Top 6 Libraries | 2026-01-19 | [blog] |
| <https://www.structlog.org/en/stable/standard-library.html> | Standard Library Logging — structlog docs | current | [official] |
| <https://github.com/hynek/structlog/blob/main/docs/logging-best-practices.md> | structlog logging best practices | current | [official] |
| <https://github.com/hynek/structlog/blob/main/docs/contextvars.md> | structlog contextvars docs | current | [official] |
| <https://github.com/hynek/structlog/blob/main/CHANGELOG.md> | structlog CHANGELOG | current | [official] |
| <https://github.com/hynek/structlog/releases> | structlog releases | current | [official] |
| <https://pypi.org/project/loguru/> | loguru on PyPI (0.7.3, released 2024-12-06) | 2024-12-06 | [official] |
| <https://github.com/Delgan/loguru/issues/1375> | "Is there a plan for the next release version?" | open | [official] |
| <https://github.com/delgan/loguru/blob/master/docs/resources/recipes.md> | loguru recipes (multiprocessing, JSON sinks) | current | [official] |
| <https://github.com/Delgan/loguru/issues/1172> | Loguru + Rich handler duplicate exception output | open | [community] |
| <https://docs.python.org/3/howto/logging-cookbook.html> | Python Logging Cookbook (multiprocessing, QueueHandler) | Python 3.14 docs | [official] |
| <https://docs.python.org/3/library/logging.handlers.html> | logging.handlers — rotation handlers | Python 3.14 docs | [official] |
| <https://docs.python.org/3/whatsnew/3.14.html> | What's New in Python 3.14 | 2025-10-07 | [official] |
| <https://versionlog.com/python/3.14/> | Python 3.14 — What's New, Support Lifecycle & EOL | 2026 | [community] |
| <https://www.python.org/downloads/release/python-3140/> | Python Release 3.14.0 | 2025-10-07 | [official] |
| <https://rich.readthedocs.io/en/stable/logging.html> | Rich — Logging Handler | current | [official] |
| <https://uptrace.dev/glossary/structured-logging> | Structured Logging: Best Practices & JSON Examples | 2025-01-08 (updated) | [blog] |
| <https://www.dash0.com/guides/json-logging> | JSON Logging: A Quick Guide for Engineers | 2026 | [blog] |
| <https://betterstack.com/community/guides/logging/json-logging/> | A Beginner's Guide to JSON Logging | current | [blog] |
| <https://signoz.io/blog/structured-logs/> | What Is Structured Logging? | 2026-05-13 (example dated) | [blog] |
| <https://discuss.python.org/t/setting-log-level-based-on-quiet-debug-flags/55570> | Setting log level based on --quiet, --debug flags | current | [community] |
| <https://xahteiwi.eu/resources/hints-and-kinks/python-cli-logging-options/> | Configuring CLI output verbosity with logging and argparse | current | [blog] |
| <https://click-log.readthedocs.io/> | click-log documentation | current | [official] |
| <https://stackoverflow.com/questions/641420/how-should-i-log-while-using-multiprocessing-in-python> | How should I log while using multiprocessing in Python? | current | [community] |
| <https://stackoverflow.com/questions/47968861/does-python-logging-support-multiprocessing> | Does python logging support multiprocessing? | current | [community] |
