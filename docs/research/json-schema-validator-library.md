# JSON Schema Validator Library Selection at Scale

**Date:** 2026-07-05

**Related:** GAP-58 · [`docs/open-questions.md`](../open-questions.md) OQ-004 (artifact JSON Schemas), OQ-010 (performance targets) · [`docs/specs/docmend.md`](../specs/docmend.md) §7.1 FR-016, §7.4 DR-005, §8.6 Dependency Policy, §9 Data Model, §21 OQ-004/OQ-010

**Gap it fills:** §8.6's Dependency Policy table lists "JSON Schema validator (e.g. `jsonschema`)" as **Conditional — confirm choice via OQ- process**, and FR-016/DR-005 require Draft 2020-12 validation with duplicate-key rejection and asserted (not merely annotated) `format` checks, run at `plan`, `apply`, and `verify` across a >100k-file library (§14, NFR-001). No prior research or OQ decision has actually compared candidate validator libraries against docmend's specific constraints: Draft 2020-12 conformance, Python 3.14 wheel availability, offline/no-network operation (§8.6, §13.3), and per-file validation cost at library scale. This report closes that gap so OQ-004's "confirm choice via OQ- process" instruction has a concrete, evidence-backed answer to adopt or reject.

---

## Executive Summary

| Candidate | Draft 2020-12 | Python 3.14 wheel/classifier (2026-07-05) | Per-validation cost (order of magnitude) | Runtime deps added | Verdict |
| --- | --- | --- | --- | --- | --- |
| **`jsonschema`** 4.26.0 | Yes — full support incl. 2020-12, 2019-09, 7, 6, 4, 3 [1] [2] | Yes — `Programming Language :: Python :: 3.14` classifier present [10] | ~0.1 ms/record with a reused compiled validator instance; ~1.3 ms/record if you naively re-validate the "easy way" each call [8] [9] | `attrs`, `jsonschema-specifications`, `referencing`, `rpds-py` (Rust, wheels ship for cp314/cp314t already) [10] [15] | **Recommended default** |
| **`fastjsonschema`** 2.21.2 | **No** — drafts 04/06/07 only; 2020-12 requested in a still-unresolved issue open since Dec 2019 [3] [4] [5] | No `3.14` classifier as of 2026-07-05 [10] [14] | ~0.017 ms/record compiled — fastest of the three, but disqualified on draft support | None (pure Python, zero required deps) | **Disqualified** — cannot satisfy FR-016/DR-005's Draft 2020-12 requirement |
| **`check-jsonschema`** 0.37.4 | Yes, but only because it _depends on_ `jsonschema>=4.18` — it is not an independent validation engine [6] [7] | No `3.14` classifier as of 2026-07-05 [10] | Not designed for in-process bulk calls — it is a CLI/pre-commit tool, one process invocation per run, with `requests`-based remote-schema fetching [6] [11] | `jsonschema`, `click`, `ruamel.yaml`, `requests`, `regress`, (`tomli` on <3.11) [10] | **Not a runtime dependency** — adopt only as a `pre-commit` dev-tool for schema-file hygiene (see Recommendation) |
| **`jsonschema-rs`** 0.46.9 _(not in the original three-way ask, surfaced during research)_ | Yes — 2020-12, 2019-09, 7, 6, 4 [12] [13] | Yes — cp310–cp314 **and** cp314t (free-threaded) wheels already published (2026-06-30/07-02) [10] [14] | Vendor-benchmarked 43–240x faster than pure-Python `jsonschema` [13] [14] | None (Rust binary wheel, no required Python deps) [10] | **Pre-vetted escalation path**, not the v1 default |

**Bottom line:** adopt **`jsonschema` 4.26+ with `Draft202012Validator` instances reused across a run and the `format` (or `format-nongpl`) extra enabled**, as the runtime dependency that resolves §8.6's "Conditional" row. `fastjsonschema` is disqualified outright by draft support, independent of its speed advantage. `check-jsonschema` is not a competing validation engine for this decision — recommend it separately, as a `pre-commit` hook that lints the checked-in schema files themselves, not as a `pyproject.toml` runtime dependency. `jsonschema-rs` is the answer if OQ-010's profiling work later shows schema validation is an actual bottleneck; it needs its own OQ approval per §8.6 before being added.

---

## Comparison Table (full)

| Dimension | `jsonschema` 4.26.0 | `fastjsonschema` 2.21.2 | `check-jsonschema` 0.37.4 | `jsonschema-rs` 0.46.9 |
| --- | --- | --- | --- | --- |
| Draft 2020-12 support | Full [1] [2] | Not supported (04/06/07 only) [3] [4] | Inherits `jsonschema`'s support (it is a wrapper) [6] [10] | Full [12] [13] |
| Validation model | Pure-Python validator classes (`Draft202012Validator`), instance-reusable, `iter_errors`/`validate` [9] | Generates Python source code once via `compile()`, then calls the generated function [3] | CLI/pre-commit invocation around `jsonschema`; not a bulk in-process API [6] | Rust core with Python bindings; `validator_for()` returns a reusable compiled validator [13] |
| `format` assertion | Optional; needs `jsonschema[format]` or `jsonschema[format-nongpl]` extra + explicit `FormatChecker` wiring — off by default per Draft 2020-12 semantics (source 7 in the prior report) [2] | Same annotation-only default behavior for whichever drafts it supports | Delegated to underlying `jsonschema` | Built-in format validators, with a documented API for custom formats [13] |
| Benchmarked throughput (per-record, order of magnitude) | ~0.1 ms (validator reused) vs. ~1.3 ms (schema recompiled every call) [8] [9] | ~0.017 ms (compiled) [3] [4] | N/A — file/process-granularity tool, not a per-record API | 43–240x faster than pure-Python `jsonschema` per vendor benchmark suite [13] [14] |
| Python 3.14 readiness | `3.14` classifier present on PyPI [10]; core Rust dependency `rpds-py` already ships cp314/cp314t wheels [15] | No `3.14` classifier as of 2026-07-05 [10] [14] | No `3.14` classifier as of 2026-07-05 [10] | `3.14` classifier present; cp314 **and** cp314t (free-threaded) wheels already on PyPI, uploaded 2026-06-30/07-02 [10] [14] |
| Required runtime deps | `attrs`, `jsonschema-specifications`, `referencing`, `rpds-py` [10] | None (pure Python) [10] | `jsonschema`, `click`, `ruamel.yaml`, `requests`, `regress`, conditionally `tomli` [10] | None (self-contained Rust wheel) [10] |
| Network/offline fit | Fully offline; no network calls in the library itself | Fully offline | Ships with a `requests`-based remote-schema-fetch feature (used when `$ref`/`--schemafile` points at an HTTP(S) URL) [6] — undesirable surface for an offline tool even if unused by default | Fully offline |
| License | MIT | MIT | Apache-2.0 | MIT [13] |
| Maturity / maintenance signal | Reference implementation for Python; used transitively by `check-jsonschema` and much of the ecosystem [6] [10] | Active but scope-limited maintenance; the 2020-12 gap has been open ~6+ years without resolution [4] | Actively maintained by the same org as `jsonschema`; frequent releases (0.37.x as of query date) [10] | ~4.7M PyPI downloads/month, 736 GitHub stars, MIT, no known vulnerabilities per Snyk, releases as recent as 2026-07-02 [14] |
| Compliance testing | Contributes to the cross-language "Bowtie" JSON Schema compliance report | N/A (limited draft scope) | N/A (wrapper) | Contributes to Bowtie; API design explicitly modeled on Python `jsonschema` for low migration friction [13] |

---

## Findings by Angle

### Draft 2020-12 support

`jsonschema`'s own PyPI listing states "Full support for Draft 2020-12, Draft 2019-09, Draft 7, Draft 6, Draft 4 and Draft 3" [1] [2]. `fastjsonschema`'s documentation is explicit that "the library implements JSON schema drafts 04, 06, and 07" [3], and a GitHub issue requesting 2019-09/2020-12 support has been open since December 2019 with no resolution [4] — two independent, corroborating sources for the same gap, one of them the maintainer's own docs. Because docmend's spec already commits to Draft 2020-12 for DR-005/FR-016 (and the prior `docs/research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md` report explicitly recommends Draft 2020-12 for the same reasons), `fastjsonschema` is disqualified regardless of its speed advantage — downgrading the schema draft to gain raw throughput is not a trade docmend needs to make at this file scale (see Throughput analysis below).

### Validation performance at library scale

Independent benchmarks agree on the relative ordering, even though absolute numbers vary by hardware and schema complexity:

- A well-known Python benchmark write-up found that reusing a `jsonschema` validator instance across calls is roughly **10x faster** than the "obvious" `jsonschema.validate()` call-per-record pattern (naive: ~1.25 ms/record; reused instance: ~0.125 ms/record for ~1 KB records), and that `fastjsonschema`'s compiled validator is roughly **100x faster** than the naive pattern (~0.017 ms/record) [8]. `jsonschema`'s own documentation demonstrates and recommends the reuse pattern (instantiate `Draft202012Validator(schema)` once, then call `.validate()`/`.iter_errors()` repeatedly rather than re-deriving the validator class per call) [9].
- `jsonschema-rs` publishes its own benchmark claim of 43–240x over pure-Python `jsonschema` for complex schemas and large instances [13], and its PyPI download volume (~4.7M/month) and lack of known vulnerabilities [14] indicate it is a production-grade, actively used alternative rather than an experimental toy.

Applied to docmend: FR-016 requires frontmatter validation at `plan`, `apply`, and `verify`, and the four JSON artifacts (inventory, plan, report, manifest — DR-001–DR-004) also need schema validation. At a >100k-file library (§14), that puts the number of individual validation calls per full run somewhere on the order of several hundred thousand once per-stage frontmatter checks and per-record artifact entries are counted — the exact figure depends on schema shape decisions still pending under OQ-004 and the concrete throughput targets still open under OQ-010. Using the reused-validator-instance pattern, `jsonschema` alone adds on the order of tens of seconds of CPU time even at 300k+ calls (300,000 x ~0.1 ms ≈ 30 s) — negligible next to the multi-hour, I/O- and encoding-detection-bound cost of a >100k-file conversion run that R-005 already flags as the dominant scale risk. This is the central reason `jsonschema` (not the fastest option) is still the right default: the naive-vs-reused-instance discipline matters far more than the choice of engine at this file count, and `jsonschema` is fast enough by 1–2 orders of magnitude of headroom once that discipline is followed.

### Compiled-validator caching

- `jsonschema`: caching means holding onto a `Draft202012Validator(schema)` (or the result of `jsonschema.validators.validator_for(schema)`) instance and reusing it for every file in a run, rather than calling the top-level `validate()` convenience function per file (which re-derives the validator class each time) [9]. This is the officially documented pattern, not a workaround.
- `fastjsonschema`: `compile()` generates Python source once and returns a callable; the library explicitly recommends compiling once and calling the result many times, "similarly like regular expressions" [3]. Fastest of the three, but moot given the draft-support disqualification.
- `check-jsonschema`: no bulk/compiled API surface is exposed for embedding — it is invoked as a CLI process or pre-commit hook per file-set, not as a library that compiles a validator once and validates hundreds of thousands of in-memory records [6] [11].
- `jsonschema-rs`: exposes `validator_for()` to build a reusable compiled validator, explicitly modeled on the Python `jsonschema` API for familiarity [13].

### Python 3.14 wheel availability

Direct PyPI JSON API queries (2026-07-05) show:

- `jsonschema` 4.26.0 carries a `Programming Language :: Python :: 3.14` classifier [10]. Its one Rust-backed transitive dependency, `rpds-py`, already ships `cp314` and `cp314t` (free-threaded) wheels for `manylinux_2_17_x86_64` as of 2026-05-28 [15] — so the full dependency chain is 3.14-ready, not just the pure-Python top-level package.
- `fastjsonschema` 2.21.2 and `check-jsonschema` 0.37.4 carry **no** `3.14` classifier as of this query, and the community-maintained Python 3.14 readiness tracker independently confirms `fastjsonschema` as not-yet-ready (✗) [14].
- `jsonschema-rs` 0.46.9 carries a `3.14` classifier and — notably — already publishes `cp314t` (free-threaded CPython 3.14) wheels for Linux, macOS x86_64, and macOS arm64, uploaded 2026-06-30/07-02 [10] [14]. That is unusually fast free-threading coverage for a Rust-extension package this early in the 3.14 lifecycle, and a positive maturity signal if it is ever adopted.

### Transitive dependency footprint and offline fit

`jsonschema`'s required deps (`attrs`, `jsonschema-specifications`, `referencing`, `rpds-py`) are all pure schema/reference-resolution plumbing with no network code [10]. Enabling FR-016's `format` assertion (needed for `date`/`date-time` checks per DR-005) pulls in the `format` or `format-nongpl` extra, which is a further half-dozen small format-checking packages (`rfc3339-validator`, `webcolors`, etc., or their non-GPL equivalents for `format-nongpl`) [7 of prior report]. None of these perform network I/O.

`check-jsonschema`, by contrast, depends on `requests` for its remote-schema-fetch feature (`$ref`s or `--schemafile` pointing at an HTTP(S) URL are downloaded and cached) [6]. Even if docmend never exercises that code path, shipping `requests` as a transitive runtime dependency of a "fully offline" tool (§8.6: "None in v1 — the tool is fully offline"; §13.3 credential policy predicated on no external services) is an unnecessary dependency-surface increase for a public, security-conscious repo. This is the strongest architectural reason to keep `check-jsonschema` out of `pyproject.toml` entirely and use it only as an external `pre-commit` tool (which manages its own isolated environment, outside docmend's shipped dependency tree).

`jsonschema-rs` has zero required Python-level dependencies — it is a self-contained Rust binary wheel — which is attractive from a footprint standpoint, but it does add a second JSON Schema _engine_ to the codebase's dependency graph if adopted alongside `jsonschema` for any reason, and swapping it in as the _sole_ engine is itself a §8.6-governed dependency change requiring its own OQ approval.

---

## Recommendation

1. **Resolve §8.6's "Conditional" row to: `jsonschema>=4.26` with the `format-nongpl` extra** (avoids the GPL-licensed `rfc3987` dependency pulled in by the plain `format` extra, consistent with keeping the dependency tree license-clean for a public repo). This directly answers the part of OQ-004 that defers to "confirm choice via OQ- process," and satisfies FR-016/DR-005's Draft 2020-12 requirement without qualification.
2. **Implementation discipline, not just library choice, is what delivers acceptable throughput:** build one `Draft202012Validator` (or the `validator_for()`-selected class) per schema at process start, reuse it for every file/record in the run, and enable `Draft202012Validator.FORMAT_CHECKER` explicitly rather than relying on any default — this is the single biggest performance and correctness lever, and it is free (no new dependency).
3. **Do not adopt `fastjsonschema`.** Its speed is real but irrelevant once it cannot express the schema draft docmend has already committed to; treating this as a live trade-off would effectively re-open OQ-004 and the settled Draft 2020-12 decision.
4. **Do not add `check-jsonschema` to `pyproject.toml`.** Instead, adopt it as a **`pre-commit`** dev-tool (outside the shipped dependency tree) running its `check-metaschema` hook against `schemas/*.schema.json` (DR-005) to catch malformed or non-2020-12-conformant schema files before they are committed, and optionally a `check-jsonschema` hook validating small, synthetic fixture artifacts in CI. This is a repo-hygiene use, not a runtime dependency decision, and it should be recorded separately (e.g., in a future CI/tooling OQ or the implementation plan), not in §8.6's runtime dependency table.
5. **Record `jsonschema-rs` as the pre-vetted escalation path for OQ-010.** If the NFR-001 100k-file synthetic-corpus profiling required by OQ-010 shows schema validation is a measurable fraction of full-run wall-clock time (unlikely given the ~30-second-order estimate above, but this is exactly what profiling is for), `jsonschema-rs` is a drop-in-shaped, Draft-2020-12-conformant, Python-3.14-ready (including free-threaded wheels) option that avoids re-litigating the draft-support question. Adding it would still require its own OQ under §8.6 at that time.

---

## Reconciliation notes

- **Fold into `docs/specs/docmend.md` §8.6:** change the `JSON Schema validator` row from "Conditional ... confirm choice via OQ- process" to `jsonschema` (pinned, with `format-nongpl` extra), citing this report.
- **Fold into `docs/open-questions.md` OQ-004:** append this report's recommendation and the reuse-pattern implementation note to OQ-004's "Agent notes," and consider moving OQ-004's validator-choice sub-question to `docs/resolved-questions.md` once the owner confirms.
- **Fold into `docs/open-questions.md` OQ-010:** add `jsonschema-rs` as the named escalation candidate if profiling surfaces schema validation as a bottleneck, so OQ-010's eventual resolution doesn't have to re-research this from scratch.
- **New/adjacent tooling note (not an existing OQ):** consider a short addendum recording `check-jsonschema` as a recommended `pre-commit` hook for `schemas/*.schema.json` hygiene — this doesn't fit cleanly under any existing OQ and may warrant its own entry when CI/pre-commit tooling is scoped.

### Drift noted while cross-referencing (out of scope for this research question, flagged for the owner)

While reading `docs/specs/docmend.md` §21 against `docs/open-questions.md` to locate OQ-004/OQ-010, confirmed the drift flagged in this task's brief: `docs/open-questions.md` defines **OQ-012** (in-place mutation vs. separate output root), **OQ-013** (frontmatter required/null/omitted/status details), and **OQ-014** (real-write CLI/config opt-in) — each with full "Agent notes" and spec-reference citations back into `docmend.md` (§8.5/§13.2/§18.2 for OQ-012; §9 for OQ-013; §7.1 FR-004/§7.3 IR-003/§18.2 for OQ-014). None of the three appear in the spec's own §21 table (which stops at OQ-011), nor anywhere else in `docmend.md` (confirmed via full-text search — zero matches for "OQ-012", "OQ-013", or "OQ-014" in the spec). All three questions are therefore invisible to anyone reading the spec of record in isolation. No further drifts of this shape (open-questions.md entries absent from §21) were found beyond these three — OQ-001 through OQ-011 all have matching §21 rows.

---

## Sources

| # | URL | Title | Authority |
| --- | --- | --- | --- |
| 1 | <https://pypi.org/project/jsonschema/> | `jsonschema` · PyPI (draft support statement) | [official] |
| 2 | <https://json-schema.org/draft/2020-12> | JSON Schema Draft 2020-12 (standard) | [official] |
| 3 | <https://horejsek.github.io/python-fastjsonschema/> | Fast JSON schema for Python — official docs (drafts 04/06/07 only) | [official] |
| 4 | <https://github.com/horejsek/python-fastjsonschema/issues/81> | `2019-09 (aka Draft 08) support` — open issue since Dec 2019 | [community] |
| 5 | <https://blog.horejsek.com/fastjsonschema> | Fast JSON Schema for Python — maintainer's own benchmark writeup | [blog] |
| 6 | <https://github.com/python-jsonschema/check-jsonschema> | `check-jsonschema` GitHub (CLI/pre-commit tool, deps, remote-schema fetch) | [official] |
| 7 | <https://check-jsonschema.readthedocs.io/en/latest/precommit_usage.html> | `check-jsonschema` pre-commit usage docs | [official] |
| 8 | <https://www.peterbe.com/plog/jsonschema-validate-10x-faster-in-python> | Benchmark: naive vs. reused-instance `jsonschema` vs. `fastjsonschema` | [blog] |
| 9 | <https://github.com/python-jsonschema/jsonschema/blob/main/docs/validate.rst> | `jsonschema` official docs — validator reuse, `FormatChecker`, `Draft202012Validator` | [official] |
| 10 | <https://pypi.org/pypi/{jsonschema,fastjsonschema,check-jsonschema,jsonschema-rs}/json> | PyPI JSON API — `requires_dist` and classifier data pulled directly, 2026-07-05 | [official] |
| 11 | <https://pypi.org/project/check-jsonschema/> | `check-jsonschema` · PyPI | [official] |
| 12 | <https://github.com/Stranger6667/jsonschema-rs> | `jsonschema` (Rust) GitHub — supported drafts, Bowtie compliance | [community, high reputation] |
| 13 | <https://pypi.org/project/jsonschema-rs/> | `jsonschema-rs` · PyPI — Python bindings, benchmark claim, `validator_for()` API | [community] |
| 14 | <https://pyreadiness.org/3.14/> ; <https://snyk.io/advisor/python/jsonschema-rs> ; <https://pypistats.org/packages/jsonschema-rs> | Python 3.14 readiness tracker; Snyk health/vuln scan; PyPI download stats | [community/tooling aggregators] |
| 15 | <https://pypi.org/project/rpds-py/> | `rpds-py` · PyPI — cp314/cp314t wheel availability (transitive dep of `jsonschema`) | [official] |
| — | `docs/specs/docmend.md` §7.1 FR-016, §7.4 DR-005, §8.6, §9, §21 | docmend spec of record (internal) | [official, internal] |
| — | `docs/open-questions.md` OQ-004, OQ-010, OQ-012, OQ-013, OQ-014 | docmend open-questions backlog (internal) | [official, internal] |
| — | `docs/research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md` | Prior docmend research establishing the Draft 2020-12 commitment | [official, internal] |

[1]: https://pypi.org/project/jsonschema/
[2]: https://json-schema.org/draft/2020-12
[3]: https://horejsek.github.io/python-fastjsonschema/
[4]: https://github.com/horejsek/python-fastjsonschema/issues/81
[5]: https://blog.horejsek.com/fastjsonschema
[6]: https://github.com/python-jsonschema/check-jsonschema
[7]: https://check-jsonschema.readthedocs.io/en/latest/precommit_usage.html
[8]: https://www.peterbe.com/plog/jsonschema-validate-10x-faster-in-python
[9]: https://github.com/python-jsonschema/jsonschema/blob/main/docs/validate.rst
[10]: https://pypi.org/pypi/{jsonschema,fastjsonschema,check-jsonschema,jsonschema-rs}/json
[11]: https://pypi.org/project/check-jsonschema/
[12]: https://github.com/Stranger6667/jsonschema-rs
[13]: https://pypi.org/project/jsonschema-rs/
[14]: https://pyreadiness.org/3.14/
[15]: https://pypi.org/project/rpds-py/
