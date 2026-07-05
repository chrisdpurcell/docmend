# Python Library Research

**Date:** 2026-07-05

## Executive summary

For `docmend`, the right dependency posture is **small runtime surface, strong validation, heavy tests**. Your v1 spec is not primarily a Markdown-conversion project yet; it is a safe, resumable, auditable filesystem mutation pipeline for >100k legacy text/HTML files, with JSON artifacts, strict frontmatter validation, dry-run/default safety gates, atomic writes, and skip-on-risk behavior.

**Recommended v1 runtime stack:**

| Need | Recommended library |
| --- | --- |
| CLI | `typer`, or `click` directly if you want maximum conservatism |
| Encoding detection | `charset-normalizer` |
| Include/exclude rules | `pathspec` |
| Human console output | `rich` |
| Internal artifact/config models | `pydantic` v2 |
| Frontmatter YAML codec | `ruamel.yaml` preferred; `PyYAML` acceptable with custom duplicate-key rejection |
| JSON Schema validation | `jsonschema[format-nongpl]` |
| TOML, JSON, walking, atomic writes | stdlib: `tomllib`, `json`, `pathlib`, `os.replace`, `tempfile`, `hashlib`, `shutil`, `logging` |

**Recommended dev/test stack:**

| Need                    | Recommended library       |
| ----------------------- | ------------------------- |
| Tests                   | `pytest`                  |
| Coverage                | `coverage` + `pytest-cov` |
| Property tests          | `hypothesis`              |
| Fake filesystem tests   | `pyfakefs`                |
| Parallel test execution | `pytest-xdist`            |
| Packaging/env           | `uv`                      |
| Lint/format             | `ruff`                    |
| Type checking           | `basedpyright`            |
| Vulnerability audit     | `pip-audit`               |

**Defer unless profiling or future milestones justify them:** `orjson`, `ijson`, `msgspec`, `puremagic`, `beautifulsoup4`, `lxml`, `markdownify`, `html-to-markdown`, `pypandoc`.

## Bottom line / Recommendation

Use this dependency policy:

```toml
# Core runtime
typer
charset-normalizer
pathspec
rich
pydantic
ruamel.yaml
jsonschema[format-nongpl]

# Dev / test
pytest
pytest-cov
coverage
hypothesis
pyfakefs
pytest-xdist
ruff
basedpyright
pip-audit
```

Keep Pandoc/HTML-conversion libraries out of v1 unless you explicitly move structural HTML-to-Markdown conversion into v1. Your spec currently treats structural conversion quality as deferred, and that is the right boundary. Adding conversion libraries early will make the project look more capable than it safely is.

---

## Analysis

## 1. Python 3.14 posture

Python 3.14 is now a real stable baseline, not a speculative target; the Python docs identify 3.14 as the latest stable release and note its October 2025 release. The same docs also show that 3.14 has already had post-release behavioral adjustments, including GC changes in 3.14.5+, so the implementation should test on the exact supported 3.14 patch level rather than merely assuming “3.14” is one thing. ([Python documentation][1])

The PyPI ecosystem is not uniformly 3.14-ready by explicit classifier. Pyreadiness tracks the top 360 PyPI packages and, as of its current page, shows **226 / 360** with explicit Python 3.14 support and **134 / 360** without it. That is good enough to proceed, but it argues for conservative dependencies and CI against Python 3.14. ([PyReadiness][2])

## 2. Recommended v1 runtime libraries

### CLI: `typer`

`typer` fits the spec well because your CLI surface is typed, subcommand-heavy, and should remain thin: `scan`, `plan`, `apply`, `verify`. Current PyPI metadata shows `typer` supports Python 3.10 through 3.14 and is actively released as of June 2026. ([PyPI][3])

The caveat: Typer is still classified as **Beta**. That does not make it inappropriate, but for a reliability-first CLI you should keep all domain logic outside Typer callbacks. If Typer becomes annoying, switching to `click` directly is realistic because Typer is built on the Click ecosystem, and Click itself is the conservative, composable CLI foundation. ([Click Documentation][4])

**Recommendation:** keep `typer`; isolate it in `src/docmend/cli.py`.

---

### Encoding detection: `charset-normalizer`

This is the right default for FR-007. It is current, Python 3.14-compatible, and positioned as an actively maintained alternative to `chardet`. Its current release metadata shows Python 3.14 support and production/stable status. ([PyPI][5])

Do not treat it as an oracle. Your spec is correct to require confidence thresholds, skip-and-report, and no replacement-character decoding. Encoding detection will always have ambiguity around Windows-1252, ISO-8859-1, UTF-8-ish files, and small files.

**Recommendation:** use `charset-normalizer` behind a small interface that returns:

```python
DetectedEncoding(
    name: str,
    confidence: float,
    bom: bool,
    decoded_without_replacement: bool,
)
```

Record the detector version and confidence in the plan.

---

### Include/exclude rules: `pathspec`

`pathspec` is directly relevant to FR-012. It implements Gitignore-style matching, has explicit Python 3.14 support, and is currently maintained. ([PyPI][6])

License note: it is MPL-2.0. That is usually fine for an application/CLI, but it is worth recording in your MS-0 dependency license review.

**Recommendation:** use one `PathSpec` selection layer shared by scan, plan, and apply. Do not reimplement glob semantics separately in each stage.

---

### Console reporting: `rich`

`rich` is appropriate for human-readable progress, tables, summaries, and readable errors. It has current releases, Python 3.14 classifiers, and broad community adoption. ([PyPI][7])

The important boundary: `rich` output must never be the canonical artifact. The canonical outputs are JSON inventory, plan, report, and manifest.

**Recommendation:** use `rich` only at the presentation layer. In `--quiet`, non-TTY, and CI modes, degrade cleanly.

---

### Internal data models: `pydantic` v2

Your JSON artifacts are structured enough that plain dictionaries will become a defect source. `pydantic` v2 is a good fit for inventory, plan, report, manifest, config snapshots, skip reasons, and action records. It is current, production/stable, Python 3.14-compatible, and Pydantic explicitly notes that v2.12 introduced initial Python 3.14 support while Pydantic v1 is not compatible with Python 3.14+. ([PyPI][8])

Pydantic can also emit JSON Schema from models, which is useful for artifact schemas, though I would still keep hand-reviewed schema files for durable external contracts. ([Pydantic Docs][9])

**Recommendation:** add `pydantic` v2 and use strict models with forbidden extras. Do not support Pydantic v1.

---

### Frontmatter YAML: `ruamel.yaml` vs `PyYAML`

Your frontmatter requirements are stricter than “parse some YAML.” You need duplicate-key rejection, stable emission, quoted scalars when needed, block scalars for multiline values, predictable ordering, and Pandoc-compatible output. Pandoc’s own docs confirm that YAML metadata blocks are top-of-file YAML objects and that YAML escaping/quoting matters for colons, backslashes, blank lines, and block formatting. ([Pandoc][10])

`ruamel.yaml` is the better technical fit because it supports round-trip preservation of comments, flow style, and key order, and current metadata shows Python 3.14 compatibility. ([PyPI][11])

The maintenance caveat is real: `ruamel.yaml` is classified Beta and appears more single-maintainer-sensitive than PyYAML. `PyYAML` is more mainstream, production/stable, and has Python 3.14 wheels, but by default it is not enough for your duplicate-key safety requirement without custom loader logic. ([PyPI][12])

**Recommendation:** use `ruamel.yaml` behind a `FrontmatterCodec` abstraction. Add explicit duplicate-key tests. If you later decide the maintenance risk is unacceptable, swap to `PyYAML` with a custom duplicate-key rejecting loader.

---

### JSON Schema validation: `jsonschema[format-nongpl]`

Use `jsonschema`, not a homegrown validator. Current metadata shows Python 3.14 support and Draft 2020-12 support. ([PyPI][13])

Your spec correctly calls out a common trap: JSON Schema `format` is not automatically asserted. The `jsonschema` docs show that format validation must be enabled with a `FormatChecker`, and that without one, format is informational. ([jsonschema][14])

**Recommendation:** use:

```python
from jsonschema import Draft202012Validator

validator = Draft202012Validator(
    schema,
    format_checker=Draft202012Validator.FORMAT_CHECKER,
)
```

Also add explicit tests for invalid `date` and `date-time` fields. For critical fields, I would not rely only on `format`; parse dates explicitly too.

---

### Stdlib filesystem and artifact primitives

Several v1 requirements should stay stdlib:

| Need               | Use                  |
| ------------------ | -------------------- |
| Config parsing     | `tomllib`            |
| Artifact JSON      | `json`               |
| Tree walking       | `pathlib.Path.walk`  |
| Atomic replacement | `os.replace`         |
| Temp files         | `tempfile`           |
| Hashing            | `hashlib`            |
| Backup copy        | `shutil`             |
| Logging            | `logging`            |
| Parallelism        | `concurrent.futures` |

`tomllib` is built into Python 3.11+ and parses TOML 1.0, but does not write TOML. That is fine for your spec because config is read-only. ([Python documentation][15])

`os.replace` is the right primitive for the atomic writer layer; Python documents that successful renaming is atomic on POSIX when source and destination are on the same filesystem. ([Python documentation][16])

`pathlib.Path.walk` is now available and gives a good stdlib basis for discovery, with explicit control over symlink traversal behavior. ([Python documentation][17])

The stdlib `json` module is fine for artifacts, with one warning: JSON is not a framed protocol, so repeated `dump()` calls into the same file produce invalid JSON. For append-style progress journals, use NDJSON deliberately or write a separate journal format. ([Python documentation][18])

**Recommendation:** do not add `atomicwrites`, `tomlkit`, `structlog`, or a file-walking dependency in v1 unless a specific requirement appears.

---

## 3. Recommended dev/test libraries

| Library | Why relevant | Recommendation |
| --- | --- | --- |
| `pytest` | Core test runner; current and mainstream. ([PyPI][19]) | Required |
| `coverage` | Coverage engine with current Python support. ([PyPI][20]) | Required |
| `pytest-cov` | Pytest integration for coverage, including subprocess/xdist support. ([PyPI][21]) | Required |
| `hypothesis` | Property-based tests for whitespace normalization, newline normalization, idempotency, and weird text cases; current, production/stable, Python 3.14-compatible. ([PyPI][22]) | Strongly recommended |
| `pyfakefs` | Useful for scan/plan/filter tests without touching the real filesystem; tested on Python 3.10–3.14. ([PyPI][23]) | Strongly recommended |
| `pytest-xdist` | Parallelizes the test suite; useful once the weird-document corpus grows. ([PyPI][24]) | Optional but useful |

Important boundary: do not use `pyfakefs` for atomic-write, fsync, crash/interruption, permission, or symlink tests. Those need real filesystem integration tests.

---

## 4. Existing tooling stack

Your existing tooling choices are still good.

| Tool | Assessment |
| --- | --- |
| `uv` | Current, widely adopted, and appropriate as the project/package manager. ([PyPI][25]) |
| `ruff` | Current, fast, broad lint/format coverage, and Python 3.14-compatible. ([PyPI][26]) |
| `basedpyright` | Fits your strict typing preference and has Python 3.14 classifier support. The tradeoff is bus-factor/community size versus Microsoft Pyright. ([PyPI][27]) |
| `pip-audit` | Appropriate supply-chain check, but it only catches known vulnerabilities in Python packages; it does not prove packages are safe or detect every transitive native/shared-library issue. ([PyPI][28]) |

Supply-chain note: dependency minimization is not theoretical. Research on PyPI package releases has found license incompatibilities and transitive-dependency issues at meaningful rates, which supports your spec’s “justify every dependency” posture. ([arXiv][29])

---

## 5. Optional / future libraries

### HTML-to-Markdown and Pandoc-related work

Do not make this v1 runtime unless you explicitly expand v1 scope. Your spec currently distinguishes extension rename from structural Markdown conversion and defers structural conversion quality. That is the right call.

For future WH-004:

| Candidate | Assessment |
| --- | --- |
| Pandoc CLI via `subprocess` | Best canonical converter for Pandoc-flavored Markdown. Prefer explicit binary discovery/version capture over hiding it behind a Python wrapper. Pandoc officially supports conversion among many formats including Markdown and HTML. ([Pandoc][30]) |
| `pypandoc` | Useful wrapper, current enough, Python 3.14-compatible, but it still depends on Pandoc being present or bundled. ([PyPI][31]) |
| `beautifulsoup4` | Good for HTML cleanup/sniffing/preprocessing, but not a Markdown converter by itself. Popular and stable, though current metadata does not explicitly advertise Python 3.14 support. ([PyPI][32]) |
| `lxml` | Fast, mature HTML/XML parser with Python 3.14 wheels; adds native dependency complexity. ([PyPI][33]) |
| `markdownify` | Simple HTML-to-Markdown converter; current release, but less obviously 3.14-signaled. Useful as a comparison candidate, not canonical. ([PyPI][34]) |
| `html-to-markdown` | Very current and Python 3.14-compatible, but I would require fixture-based comparison before trusting it. ([PyPI][35]) |

**Recommendation:** when structural conversion starts, create a conversion shootout fixture set and compare Pandoc CLI, `markdownify`, and `html-to-markdown`. Pick based on output fidelity, not package marketing.

---

### Binary/file-type sniffing

For v1, internal heuristics are probably enough: suffix allowlist, NUL-byte check, byte-ratio checks, decode status, and charset confidence.

| Library | Assessment |
| --- | --- |
| `puremagic` | Best optional candidate if you need more file-type sniffing. Current, pure Python, Python 3.14-compatible, no runtime dependencies. ([PyPI][36]) |
| `python-magic` | Powerful via libmagic, but stale-looking PyPI metadata, no 3.14 classifier, and external native dependency complexity. ([PyPI][37]) |
| `filetype` | Dependency-free but stale-looking and not 3.14-signaled. ([PyPI][38]) |

**Recommendation:** defer all three. Add `puremagic` only if the weird-document corpus shows internal sniffing is insufficient.

---

### JSON scale/performance

Start with stdlib JSON. Your artifact sizes may be large, but not necessarily enough to justify faster serializers before profiling.

| Library | Assessment |
| --- | --- |
| `orjson` | Very current, fast, Python 3.14/3.15-compatible. Good optional performance dependency, but returns bytes and does not solve streaming/journaling design. ([PyPI][39]) |
| `ijson` | Good if `verify` must stream huge JSON artifacts with bounded memory. Current and Python 3.14-compatible. ([PyPI][40]) |
| `msgspec` | Fast validation/serialization option with Python 3.14 support, but less aligned with your explicit JSON Schema/frontmatter validation needs. ([PyPI][41]) |

**Recommendation:** keep these out of core v1. Add `ijson` first if artifact size becomes a memory issue. Add `orjson` only after profiling shows serialization is a bottleneck.

---

## 6. Libraries I would avoid or defer

| Library/category | Why |
| --- | --- |
| `python-magic` | Native `libmagic` dependency and stale-looking 3.14 posture. |
| `filetype` | Stale-looking metadata and weak 3.14 signal. |
| `atomicwrites` | Your atomic-write design is better implemented directly with stdlib temp file + fsync + `os.replace`. |
| `tomlkit` / `tomli-w` | Not needed unless docmend writes or edits TOML config. `tomllib` is enough for read-only config. |
| `structlog` | Nice, but not necessary. Start with stdlib logging plus structured JSON artifacts. |
| `pypandoc_binary` | Heavy and premature for v1; structural conversion is deferred. |
| `orjson` / `msgspec` in core | Premature optimization. Keep JSON contracts boring until profiling proves otherwise. |
| Spellcheck/grammar libraries | Explicitly out of v1. They pull the project toward semantic mutation before the safety substrate is proven. |

---

## 7. Proposed spec amendment: dependency policy

I would update §8.6 to this:

| Dependency | Status | Reason |
| --- | --- | --- |
| `typer` | Allowed | CLI shell only; no domain logic in callbacks. |
| `charset-normalizer` | Required | Encoding detection with confidence threshold and skip-on-risk behavior. |
| `pathspec` | Required | Shared include/exclude engine for scan, plan, apply. |
| `rich` | Allowed | Human-readable console output only; JSON artifacts remain canonical. |
| `pydantic` v2 | Required | Strict internal models for config, inventory, plan, report, manifest. |
| `ruamel.yaml` | Conditional / preferred | Frontmatter parse/emit with duplicate-key rejection and emission control. |
| `PyYAML` | Conditional fallback | Acceptable only with custom duplicate-key rejecting loader. |
| `jsonschema[format-nongpl]` | Required when FR-016 lands | Draft 2020-12 validation with explicit format checking. |
| `hypothesis` | Dev required | Property tests for transforms/idempotency/risk classifier. |
| `pyfakefs` | Dev allowed | Fast filesystem-behavior tests, excluding atomic/crash tests. |
| `puremagic` | Deferred | Add only if weird-document corpus proves byte heuristics insufficient. |
| Pandoc CLI | Deferred | Future structural conversion, invoked explicitly and version-recorded. |

## Recommendations

1. **Adopt the minimal runtime stack now:** `typer`, `charset-normalizer`, `pathspec`, `rich`, `pydantic`, `ruamel.yaml`, `jsonschema[format-nongpl]`.
2. **Keep v1 conversion conservative:** no Pandoc wrapper, no HTML-to-Markdown converter, no spellcheck/grammar, no dedupe library.
3. **Make validation first-class:** `pydantic` for internal models, `jsonschema` for canonical schema validation, `ruamel.yaml` for frontmatter codec safety.
4. **Test the dangerous parts harder than the happy path:** add `hypothesis`, `pyfakefs`, real-filesystem atomic-write tests, and a growing weird-document corpus.
5. **Gate every dependency through Python 3.14 CI:** classifier support is useful but not enough.

## Uncertainties

The main unresolved decision is frontmatter emission timing. If v1 truly only validates fixture frontmatter and does not emit frontmatter at scale, `ruamel.yaml` and `jsonschema` can land at MS-5 instead of MS-0. If frontmatter is emitted during v1 conversion, they become core runtime dependencies immediately.

The second uncertainty is artifact size. For >100k files, stdlib JSON may still be fine. If manifests/reports become too large to load comfortably, add `ijson` before considering faster encoders.

## Sources

- docmend specification.
- Python 3.14 documentation. ([Python documentation][1])
- Python stdlib docs for `os.replace`, `tomllib`, `json`, and `pathlib.Path.walk`. ([Python documentation][16])
- Pyreadiness Python 3.14 package support tracker. ([PyReadiness][2])
- PyPI/package documentation for Typer, charset-normalizer, pathspec, Rich, Pydantic, jsonschema, ruamel.yaml, PyYAML, pytest, coverage, Hypothesis, pyfakefs, uv, Ruff, BasedPyright, and pip-audit. ([PyPI][3])
- Pandoc documentation for conversion and YAML metadata blocks. ([Pandoc][30])

[1]: https://docs.python.org/3/whatsnew/3.14.html 'What’s new in Python 3.14 — Python 3.14.6 documentation'
[2]: https://pyreadiness.org/3.14/ 'Python 3.14 Readiness - Python 3.14 support table for most popular Python packages'
[3]: https://pypi.org/project/typer/ 'typer · PyPI'
[4]: https://click.palletsprojects.com/?utm_source=chatgpt.com 'Welcome to Click — Click Documentation (8.4.x)'
[5]: https://pypi.org/project/charset-normalizer/ 'charset-normalizer · PyPI'
[6]: https://pypi.org/project/pathspec/ 'pathspec · PyPI'
[7]: https://pypi.org/project/rich/ 'rich · PyPI'
[8]: https://pypi.org/project/pydantic/ 'pydantic · PyPI'
[9]: https://docs.pydantic.dev/latest/concepts/json_schema/ 'JSON Schema | Pydantic Docs'
[10]: https://pandoc.org/demo/example33/8.10-metadata-blocks.html 'Metadata blocks'
[11]: https://pypi.org/project/ruamel.yaml/ 'ruamel.yaml · PyPI'
[12]: https://pypi.org/project/PyYAML/ 'PyYAML · PyPI'
[13]: https://pypi.org/project/jsonschema/ 'jsonschema · PyPI'
[14]: https://python-jsonschema.readthedocs.io/en/stable/validate/ 'Schema Validation - jsonschema 4.26.0 documentation'
[15]: https://docs.python.org/3/library/tomllib.html 'tomllib — Parse TOML files — Python 3.14.6 documentation'
[16]: https://docs.python.org/3/library/os.html 'os — Miscellaneous operating system interfaces — Python 3.14.6 documentation'
[17]: https://docs.python.org/3/library/pathlib.html 'pathlib — Object-oriented filesystem paths — Python 3.14.6 documentation'
[18]: https://docs.python.org/3/library/json.html 'json — JSON encoder and decoder — Python 3.14.6 documentation'
[19]: https://pypi.org/project/pytest/ 'pytest · PyPI'
[20]: https://pypi.org/project/coverage/ 'coverage · PyPI'
[21]: https://pypi.org/project/pytest-cov/ 'pytest-cov · PyPI'
[22]: https://pypi.org/project/hypothesis/ 'hypothesis · PyPI'
[23]: https://pypi.org/project/pyfakefs/ 'pyfakefs · PyPI'
[24]: https://pypi.org/project/pytest-xdist/ 'pytest-xdist · PyPI'
[25]: https://pypi.org/project/uv/ 'uv · PyPI'
[26]: https://pypi.org/project/ruff/ 'ruff · PyPI'
[27]: https://pypi.org/project/basedpyright/ 'basedpyright · PyPI'
[28]: https://pypi.org/project/pip-audit/ 'pip-audit · PyPI'
[29]: https://arxiv.org/abs/2308.05942?utm_source=chatgpt.com 'Understanding and Remediating Open-Source License Incompatibilities in the PyPI Ecosystem'
[30]: https://pandoc.org/MANUAL.html 'Pandoc - Pandoc User’s Guide'
[31]: https://pypi.org/project/pypandoc/ 'pypandoc · PyPI'
[32]: https://pypi.org/project/beautifulsoup4/ 'beautifulsoup4 · PyPI'
[33]: https://pypi.org/project/lxml/ 'lxml · PyPI'
[34]: https://pypi.org/project/markdownify/ 'markdownify · PyPI'
[35]: https://pypi.org/project/html-to-markdown/ 'html-to-markdown · PyPI'
[36]: https://pypi.org/project/puremagic/ 'puremagic · PyPI'
[37]: https://pypi.org/project/python-magic/ 'python-magic · PyPI'
[38]: https://pypi.org/project/filetype/ 'filetype · PyPI'
[39]: https://pypi.org/project/orjson/ 'orjson · PyPI'
[40]: https://pypi.org/project/ijson/ 'ijson · PyPI'
[41]: https://pypi.org/project/msgspec/ 'msgspec · PyPI'
