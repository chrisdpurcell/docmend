# Safe YAML Loading and Hardening for Parsing Legacy Frontmatter

**Date:** 2026-07-05

**Related:** GAP-65 (external tracking reference supplied by the calling task; no `GAP-` identifier scheme exists anywhere in this repo as of 2026-07-05 — carried here verbatim, treat as an external tracker reference the owner can reconcile, not a docmend-native ID) · [`docs/open-questions.md`](../open-questions.md) OQ-004 (artifact JSON Schemas), OQ-009 (frontmatter emission scope), OQ-013 (frontmatter required/null/omitted/status details) · [`docs/specs/docmend.md`](../specs/docmend.md) §3.4 C-006, §7.1 FR-016, §7.4 DR-005, §8.6 (Dependency Policy), §9 Data Model, §13.6 (Hardening Checklist), §17.2 (weird-document corpus) · [`docs/research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md`](managing-pandoc-markdown-and-strict-yaml-frontmatter.md) · [`docs/research/json-schema-validator-library.md`](json-schema-validator-library.md)

**Gap it fills:** FR-016/DR-005 already commit docmend to rejecting duplicate frontmatter keys "at YAML-parse time (before schema validation runs)" and to asserting `format`-typed fields, and the prior Pandoc/frontmatter research (`managing-pandoc-markdown-and-strict-yaml-frontmatter.md`) already flagged _that_ this gap exists — but no research or OQ decision has picked _which YAML library and loader configuration_ actually satisfies that requirement, nor has anything examined the other well-documented YAML-loading hazards (arbitrary-object deserialization, resource-exhaustion DoS, implicit type coercion) that apply specifically to docmend's stated posture of parsing pre-existing, "admittedly-corrupted," decades-old frontmatter (§1, §17.2) rather than trusting it. Notably, `docs/specs/docmend.md` §8.6's Dependency Policy table lists no YAML library at all despite FR-016/DR-005 requiring one — the same class of unresolved-dependency gap the JSON Schema validator research (`json-schema-validator-library.md`) already closed for the schema layer. This report closes the YAML-loader half of that gap: a concrete safe-loading configuration, a duplicate-key/format-assertion mechanism that actually satisfies FR-016's acceptance criteria, and a proposed §13.6 hardening line item.

---

## Executive Summary

| Dimension | `PyYAML` 6.0.x (`SafeLoader`) | `ruamel.yaml` 0.18.x (`YAML(typ='safe')`) |
| --- | --- | --- |
| Arbitrary-object construction | Blocked by `SafeLoader`/`safe_load` — never `load()`, `full_load()`, or `unsafe_load()` [1] [2] | Blocked by `typ='safe'` — never `YAML(typ='unsafe')` or the legacy top-level `load()` [11] |
| Duplicate frontmatter keys (C-006/FR-016) | **Silently overwrites** — accepted behavior for 10+ years, tracked but unresolved in the library's own tracker [6] [7] | **Rejected by default** — `YAML()`'s "new API" raises `DuplicateKeyError` unless `allow_duplicate_keys=True` is explicitly set [8] [9] |
| YAML version / implicit-typing surface | YAML 1.1 resolver — retains the "Norway problem" (`yes`/`no`/`on`/`off` as implicit booleans, leading `0`-prefixed digit strings as octal) [10] | YAML 1.2 (2009) by default — drops the 1.1 boolean/octal implicit-typing footguns [10] |
| Implicit date/timestamp coercion | Unquoted ISO-like date scalars silently become `datetime.date`/`datetime.datetime` objects, not strings [21] | Same behavior — also resolves unquoted date-like scalars to `datetime` objects, independently corroborated as a live footgun [14] [15] |
| Resource-exhaustion DoS (alias/anchor "billion laughs") | Not mitigated by default; open issue since 2018 with no built-in cap on alias expansion [12] [13] | Shares PyYAML 3.11 lineage for the scanner/parser; no evidence of a built-in cap either — treat as inherited risk, not verified-safe |
| Deeply-nested-input `RecursionError` DoS | Confirmed, unbounded, uncaught by `yaml.YAMLError` — `safe_load` itself crashes with a raw `RecursionError` on deeply nested sequences (reported Oct 2025) [16] | Not independently verified for this exact case; same parser architecture makes it a reasonable inherited-risk assumption |
| Python 3.14 wheel readiness (2026-07-05) | `cp314`/`cp314t` wheels published (2025-09-25) [17] | `ruamel.yaml.clib` (the optional C accelerator) publishes `cp314` wheels (2025-11-16); pure-Python `ruamel.yaml` itself has no C-extension version gate [18] |
| Present in `docs/specs/docmend.md` §8.6 Dependency Policy | No — **gap**, same class as the JSON Schema validator's now-resolved "Conditional" row | No — same gap |

**Bottom line:** neither library is "safe" out of the box for docmend's stated requirements — `safe_load`/`typ='safe'` is necessary but not sufficient. **Recommend `ruamel.yaml` with `YAML(typ='safe')`** as the frontmatter loader, because it is the only one of the two that satisfies FR-016's duplicate-key acceptance criterion natively (no hand-rolled constructor to write, test, and maintain), and because its YAML 1.2 conformance removes an entire class of implicit-typing corruption that YAML 1.1 parsers (PyYAML) still carry. Both libraries still need docmend-side hardening for resource exhaustion and implicit date coercion — those are YAML-ecosystem-wide characteristics, not library bugs either tool has fixed.

---

## Findings by Angle

### 1. Loader/API selection — never `load()`, `full_load()`, or `unsafe_load()`

PyYAML's own documentation states plainly that "the ability to construct an arbitrary Python object may be dangerous if you receive a YAML document from an untrusted source" and that `safe_load` "recognizes only standard YAML tags and cannot construct an arbitrary Python object" [1]. The library's own wiki confirms `yaml.load()` "has been unsafe since the first release in May 2006" and documents `Loader=yaml.SafeLoader` as the fix for the now-deprecated bare `yaml.load(input)` call [2].

This is not a historical footnote. `CVE-2020-14343` documents that `full_load()`/`FullLoader` (versions before 5.4) are themselves exploitable for full remote code execution via the `python/object/new` constructor [3]. Two much more recent, independently reported incidents confirm the mistake is still being made in production code as of 2025–2026: `CVE-2025-50460` is an RCE in the `ms-swift` project from a test harness calling `yaml.load()` without a safe loader [4], and `CVE-2026-24009` is an RCE in the `docling` document-ingestion library from an unsafe PyYAML loader configuration reachable through normal document parsing — exactly docmend's own threat surface shape (a document-ingestion pipeline processing files that were not authored with the tool in mind) [5]. `ruamel.yaml`'s own maintainer likewise states, of `YAML(typ='safe')`/`typ='rt'`, that the _unsafe_ top-level `load()` "will terminate your program with an error message" in current releases specifically because it was being conflated with PyYAML's historical vulnerability [11] — i.e., the project has already hardened its own default against this exact mistake class.

**docmend implication:** even though the source library is the owner's own decades-old files rather than adversary-controlled network input, C-002/C-003's "cannot manually review 100k+ files" posture means docmend must treat every pre-existing frontmatter block as untrusted input by construction — a stray or externally-edited file with a crafted `!!python/object` tag is exactly the kind of "admittedly corrupted" input FR-015's skip-and-report doctrine already assumes will occur. `safe_load`/`typ='safe'` must be the _only_ code path that ever touches frontmatter, with no configuration flag, environment variable, or future refactor able to route it through `full_load`/`unsafe_load`.

### 2. Duplicate-key handling — the concrete mechanism FR-016 needs

The prior Pandoc/frontmatter research already identified duplicate-key rejection as necessary and cited YAML's own uniqueness requirement for mapping keys [managing-pandoc-markdown-and-strict-yaml-frontmatter.md]. This report supplies the missing _mechanism_.

PyYAML's `SafeLoader` **silently accepts duplicate keys and keeps the last value**, with no error and no warning. This is a long-standing, still-open defect in the library's own issue tracker: issue #41, "pyyaml should detect duplicate keys and report an error," has been open since a 2015 migration from the project's original Trac tracker with no resolution [6], and issue #165 independently reports the same silent-overwrite behavior in production use [7] — two independent reports of the identical gap, one of them the library's own repository. Getting duplicate-key rejection from PyYAML therefore requires **hand-writing and maintaining a custom `SafeLoader` subclass** that overrides `construct_mapping()` to check for repeated keys before returning the dict — extra code that is exactly the kind of bespoke security-relevant logic that is easy to get subtly wrong or to regress silently on a PyYAML upgrade.

`ruamel.yaml` solves this natively. Its own constructor source raises `DuplicateKeyError` from `check_mapping_key()` whenever a repeated key is found and `self.allow_duplicate_keys` is not `True` [8] — and a duplicate independent confirmation on Stack Overflow states the exact API-version distinction: "`ruamel.yaml` will give a `DuplicateKeyFutureWarning` if used with the legacy [top-level function] API, and raise a `DuplicateKeyError` with the new [`YAML()` class-based] API" [9]. Practically: `ruamel.yaml.YAML(typ='safe').load(text)` raises on the first duplicate key with **zero custom code**, which is a materially stronger, lower-maintenance answer to FR-016's literal acceptance criterion ("a fixture with duplicate frontmatter keys is rejected at parse time") than patching PyYAML.

(A third, more radical option surfaced during research — `StrictYAML`, which "will simply refuse to parse" any document with duplicate keys as a matter of core design, alongside disallowing several other YAML ambiguities [13, community] — is not recommended here: it restricts the accepted grammar aggressively enough that it risks rejecting legitimate frontmatter variations from a decades-old, heterogeneous library rather than just rejecting genuine hazards, and it does not appear in either `pyproject.toml` or `docs/specs/docmend.md` as a considered dependency. It is worth knowing about, not adopting for v1.)

### 3. Resource limits — the two DoS classes PyYAML/ruamel do not bound by default

The research question specifically asks about "resource limits," and this is the angle with the weakest defaults in _both_ candidate libraries:

- **Alias/anchor expansion ("billion laughs").** PyYAML's own issue tracker has an open, unresolved report (`#235`, filed 2018) asking whether anchors/aliases can be disabled or capped, noting that a `SafeLoader`-based mitigation had been prototyped elsewhere but never merged [12]. The generic mechanism — a handful of YAML anchors (`&`) referencing each other through aliases (`*`) in nested lists — is the same "exponential entity expansion" pattern documented for XML, and current community write-ups reconfirm PyYAML is still cited as vulnerable to it by default as of 2025–2026 discussion [13]. `ruamel.yaml` shares PyYAML 3.11's scanner/parser lineage [10] and no evidence surfaced during this research that it caps alias expansion either; treat it as an inherited, unverified risk rather than assume it is fixed.
- **Deeply-nested-input crash.** Independent of aliases, a plain deeply nested (but otherwise well-formed) YAML sequence can crash `yaml.safe_load` outright: issue `#895` in PyYAML's own tracker (filed October 2025 — recent enough to still be open as of this report) reproduces a raw, uncaught `RecursionError: maximum recursion depth exceeded` from inside the scanner, with a full traceback confirming the crash happens before any application code runs, i.e. a bare `except yaml.YAMLError` will **not** catch it because `RecursionError` is not a subclass of `yaml.YAMLError` [16]. This is not YAML-specific pathology alone — a corroborating example from the JS ecosystem (`CVE-2026-33532`, "yaml is vulnerable to Stack Overflow via deeply nested YAML collections") shows the same class of defect recurring across independent YAML parser implementations in 2026 [per the same research pass, GitLab advisory database], reinforcing that recursive-descent YAML parsers as a category do not bound nesting depth by default.

**docmend implication — concrete mitigations, since neither library provides them natively:**

1. **Bound the input before it reaches the parser.** Per C-004/§9, frontmatter is always the first `---`-delimited block in the file. docmend should extract that block with a hard byte-size ceiling (e.g. read at most the first 64 KiB of the file when searching for the closing `---`/`...` delimiter) before ever calling the YAML loader — a legitimate frontmatter block for this schema (§9) is at most a few KiB; a "block" that does not close within a generous ceiling is itself a `FR-015` skip-and-report case ("file appears binary despite a `.txt` extension"-style anomaly), not a YAML-parsing problem. This one guard defangs both the alias-expansion and recursion-depth hazards for the overwhelming majority of cases, because both require substantial input size/nesting to matter, and it costs nothing extra to implement since docmend already has to locate the frontmatter block's boundaries to feed the rest of the file to the Markdown body pipeline.
2. **Catch `RecursionError` explicitly, alongside the loader's own exception type**, around every frontmatter parse call, and treat it identically to a YAML syntax error: skip-and-report (FR-015), never propagate and crash the batch (`sys.setrecursionlimit()` should **not** be raised as a workaround — that trades a clean failure for a harder-to-diagnose C-stack overflow under `CSafeLoader`/`ruamel.yaml.clib`).
3. **Do not rely on `sys.setrecursionlimit()` reduction alone as the defense** — it is a blunt, global interpreter setting that would also constrain unrelated recursive code paths elsewhere in the same process (e.g. any tree-walking discovery/backup logic); a per-file byte-size ceiling plus explicit exception handling is the targeted, testable control that fits docmend's existing skip-and-report architecture.

### 4. Implicit typing — the "Norway problem" and silent date coercion

YAML 1.1 (PyYAML's default resolver) treats bare, unquoted `yes`, `no`, `on`, `off`, `y`, `n` as booleans and leading-zero digit strings as octal — the well-documented "Norway problem" (`NO`, the country code, silently becoming boolean `false`) [10, community]. YAML 1.2, which `ruamel.yaml` implements by default, **dropped** the `yes`/`no`/`on`/`off` boolean forms and the bare-octal form specifically to close this class of surprise [10, official ruamel.yaml docs]. For a decades-old, "poor spelling, grammar, and punctuation" library (§1) where a raw title, tag, or filename-derived string could plausibly be the literal word "No," "Off," or a leading-zero numeric-looking string, YAML 1.2 semantics are a strict, free correctness improvement over YAML 1.1 with no migration cost, since docmend has no existing frontmatter corpus to be backward-compatible with (OQ-009: bulk emission is deferred).

**Both** libraries, however, still resolve unquoted ISO-8601-shaped scalars (e.g. `2026-07-05`) to native `datetime.date`/`datetime.datetime` objects rather than leaving them as strings — this is YAML core-schema timestamp-tag behavior, not a PyYAML-specific bug, and it is independently confirmed for `ruamel.yaml` as well: a Stack Overflow report describes exactly this behavior causing a downstream `json.dumps()` failure because the loaded value is a Python `datetime` object, not a JSON-serializable string [14], and `ruamel.yaml`'s own issue tracker has an open ticket about timezone-naive timestamp parsing confirming the same code path exists and has known rough edges [15]. A parallel, independently filed complaint against PyYAML specifically requests "a way to disable or take control over PyYAML's magic parsing of dates" for the same reason [21].

**This directly undermines FR-016/DR-005's `format`-assertion acceptance criterion if not handled.** The prior JSON Schema research already flagged that `format` validation is annotation-only unless explicitly enabled in the validator [managing-pandoc-markdown-and-strict-yaml-frontmatter.md; json-schema-validator-library.md]. But there is a _prior_ trap this report surfaces: JSON Schema's `format` keyword is explicitly scoped to instances of the matching primitive type — the Draft 2020-12 validation spec states that format assertions apply only when the instance is of the correct type, and "instances of any other type MUST ignore" the format keyword. Because a Python `datetime.date` object is not a `str`, feeding it straight into `jsonschema.Draft202012Validator` against a `{"type": "string", "format": "date"}` schema fails on the `type` check (a reasonably loud, catchable failure) — but a looser schema that specifies `format: date` without also asserting `type: string` will simply **skip format validation entirely** for that field, silently, because the instance is the wrong Python type for the check to apply to at all. Either way, the frontmatter is no longer JSON-serializable data by the time it reaches schema validation, which conflicts with DR-005's own "JSON-serializable YAML subset" design intent from the prior frontmatter research.

**docmend implication:** the YAML loader must not be allowed to silently promote date-shaped scalars to native Python objects before schema validation runs. Two compliant options, in order of robustness:

- **Preferred:** override the loader's timestamp constructor (both PyYAML's `SafeConstructor.add_constructor('tag:yaml.org,2002:timestamp', ...)` and `ruamel.yaml`'s equivalent `SafeConstructor` registration support this) to return the raw string unchanged instead of a `datetime` object, so every scalar that survives YAML parsing is already JSON-primitive-compatible, and `format: date`/`date-time` assertion in `jsonschema` (already resolved to `jsonschema>=4.26` with `format-nongpl` per `json-schema-validator-library.md`) does the actual semantic date validation on a real string.
- **Acceptable fallback:** post-process the loaded mapping recursively, converting any `datetime.date`/`datetime.datetime` instance back to its ISO-8601 string form (`.isoformat()`) before handing the structure to the JSON Schema validator — functionally equivalent, but duplicates logic the loader override handles once, at the source.

Either way, this should be called out explicitly as its own hardening item — it is easy to satisfy DR-005's letter (format assertion is "enabled") while still failing its intent (a malformed date silently passes because it was never compared as a string in the first place).

### 5. Dependency-policy gap (a second instance of the pattern this task asked to look for)

While cross-referencing FR-016/DR-005 against `docs/specs/docmend.md` §8.6, this report confirms a gap in the same _shape_ as the already-known OQ-012–OQ-014 table drift the task brief asked to verify and extend: **§8.6's Dependency Policy table lists no YAML library at all**, despite FR-016 requiring frontmatter parsing and DR-005 requiring duplicate-key rejection "at the parser." The table lists `typer`, `charset-normalizer`, `pathspec`, `rich`, stdlib `tomllib` (for **config**, not frontmatter — D-005 is explicit that TOML is the config format, a separate concern from the YAML frontmatter contract in §9), and a "Conditional" JSON Schema validator row (now resolved by `json-schema-validator-library.md` to `jsonschema`). No row exists for the YAML parser that FR-016/DR-005 presuppose. This is not a table-numbering drift like OQ-012–014, but it is the identical failure pattern: a requirement (FR-016) depends on a concrete tool choice that was never actually added to the section whose entire job is to enumerate approved dependencies.

---

## Recommendation

1. **Adopt `ruamel.yaml>=0.18` as the frontmatter YAML loader**, resolving §8.6's missing YAML-library row. Use the class-based API exclusively:

   ```python
   from ruamel.yaml import YAML
   from ruamel.yaml.constructor import SafeConstructor

   # Keep date/date-time scalars as plain strings so downstream JSON Schema
   # format assertion (jsonschema Draft202012Validator, format-nongpl) sees
   # real strings, never a silently-substituted datetime.date/datetime object.
   SafeConstructor.add_constructor(
       "tag:yaml.org,2002:timestamp",
       SafeConstructor.construct_yaml_str,
   )

   frontmatter_loader = YAML(typ="safe")
   frontmatter_loader.allow_duplicate_keys = False  # explicit; this is also the default

   def load_frontmatter(block: str) -> dict:
       """block is the already-extracted, size-bounded '---'-delimited text."""
       return frontmatter_loader.load(block)
   ```

   `allow_duplicate_keys = False` is already the library default for the class-based API [8] [9], but setting it explicitly documents the safety-relevant decision at the call site rather than relying on an unstated default surviving future `ruamel.yaml` upgrades.

2. **Bound the input before parsing, not just the parser configuration.** Extract the frontmatter block under a hard byte-size ceiling (e.g. 64 KiB) as part of the existing "frontmatter must be the first `---`-delimited block" scan (C-004); a block that does not close within that ceiling is a `FR-015` skip-and-report case, never handed to the YAML loader at all. This is the single most effective, lowest-maintenance mitigation for both the alias-expansion and recursion-depth resource-exhaustion classes documented in Finding 3, and it requires no assumptions about internal loader behavior that might change on a future `ruamel.yaml`/PyYAML release.

3. **Wrap every frontmatter parse call to catch `RecursionError` alongside the loader's own exception class** (`ruamel.yaml.YAMLError` / `ruamel.yaml.constructor.DuplicateKeyError`), classifying all three identically as a risky-file skip (FR-015/ERR-family), never an unhandled crash that would abort a multi-hour batch run (NFR-001/FR-013).

4. **Never call `YAML(typ='unsafe')`, `YAML(typ='full')` for loading, or PyYAML's `load()`/`full_load()`/`unsafe_load()` anywhere in the codebase** — a lint rule or code-review checklist item enforcing "frontmatter is only ever loaded through the single hardened `load_frontmatter()` helper above" is cheap insurance against a future contributor reaching for the more familiar unsafe top-level function under time pressure, which is exactly the failure mode both `CVE-2025-50460` and `CVE-2026-24009` show still happens in current (2025–2026) real-world codebases [4] [5].

5. **If `ruamel.yaml`'s API surface proves too heavy for docmend's actual usage** (it is a large, round-trip-preservation-oriented library; docmend only ever needs one-way loading), the fallback is PyYAML `SafeLoader` plus a hand-written duplicate-key-checking `construct_mapping()` override and an equivalent timestamp-constructor override — functionally equivalent, but it is _docmend's own code_ carrying the security-relevant duplicate-key logic rather than an upstream-maintained default, which is a materially weaker position against future regression. Prefer option 1 unless a concrete, measured reason emerges to switch (e.g. `ruamel.yaml` throughput becoming a bottleneck at the >100k-file scale under OQ-010 profiling — the same escalation pattern the JSON Schema validator research used for `jsonschema-rs`).

## Proposed §13.6 Hardening Checklist Line Item

Add to `docs/specs/docmend.md` §13.6 (Hardening Checklist), in the same one-line checklist format as the existing rows:

> - [ ] **YAML input hardening** — frontmatter is parsed exclusively through a single hardened loader (`ruamel.yaml` `YAML(typ='safe')`, never `typ='unsafe'`/`typ='full'` or PyYAML's bare `load()`/`full_load()`/`unsafe_load()`); duplicate keys are rejected at parse time (`allow_duplicate_keys=False`, satisfying C-006/FR-016); the extracted frontmatter block is read under a hard byte-size ceiling before being handed to the loader; date/timestamp scalars are constructed as plain strings (not `datetime` objects) so JSON Schema `format` assertion runs against real strings; `RecursionError` is caught alongside the loader's own exception class and treated as a risky-file skip (FR-015), never an unhandled crash. See `docs/research/safe-yaml-loading.md`.

## Reconciliation notes

- **Fold into `docs/specs/docmend.md` §8.6:** add a `YAML frontmatter parser` row — `ruamel.yaml` — Yes — "Frontmatter parsing/duplicate-key rejection (FR-016, DR-005); see `docs/research/safe-yaml-loading.md`" — resolving the dependency-policy gap identified in Finding 5.
- **Fold into `docs/specs/docmend.md` §13.6:** add the line item proposed above.
- **Fold into `docs/specs/docmend.md` §9/DR-005:** append the timestamp-as-string constructor requirement to the existing bullet "Reject duplicate frontmatter keys at YAML parse time... (C-006)" so the two loader-hardening requirements (duplicate keys, timestamp coercion) are stated together where DR-005 already lives.
- **Fold into `docs/open-questions.md` OQ-004:** append this report's `ruamel.yaml` recommendation to OQ-004's Agent notes as the concrete answer to the still-open "exact JSON Schemas" question's implicit YAML-loader dependency.
- **Fold into `docs/open-questions.md` OQ-013:** the timestamp-as-string finding (Finding 4) is directly relevant to OQ-013's "required/null/omitted/status" schema-detail work — a `date` field's schema entry should assume it is validating a plain string, not a Python object, once this report's loader hardening lands.
- **New §8.6 drift, same shape as the OQ-012–014 table gap:** see Finding 5 — recommend the owner treat "a requirement names a dependency that never got a Dependency Policy row" as its own recurring drift class worth a lightweight cross-reference check (similar in spirit to the traceability-matrix tooling explored in `docs/research/architecture-and-traceability-enforcement.md`, if that report is in scope for this repo).

### Known drift re-confirmed during this research pass

Per the task brief's request to verify and look for more instances: `docs/open-questions.md` defines `OQ-012`, `OQ-013`, and `OQ-014` (each with full Agent-notes sections), but `docs/specs/docmend.md` §21's Open Questions table stops at `OQ-011` — confirmed again by direct inspection during this pass (three prior research reports in this directory have already independently confirmed the same count). No further instances of _that specific_ drift shape were found while reading §13.6/§8.6/§9 for this report. A related-but-distinct drift was found instead and is recorded above as Finding 5: §8.6's Dependency Policy table omits any row for the YAML library FR-016/DR-005 require.

---

## Sources

| # | URL | Title | Authority |
| --- | --- | --- | --- |
| 1 | <https://pyyaml.org/wiki/PyYAMLDocumentation> | PyYAML Documentation — `safe_load` vs `load`, arbitrary-object construction warning | [official] |
| 2 | <https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation> | PyYAML `yaml.load(input)` Deprecation wiki page | [official] |
| 3 | <https://www.sentinelone.com/vulnerability-database/cve-2020-14343> | CVE-2020-14343 — PyYAML `full_load`/`FullLoader` RCE via `python/object/new` | [community, security vendor writeup of an official CVE] |
| 4 | <https://nvd.nist.gov/vuln/detail/CVE-2025-50460> | CVE-2025-50460 — `yaml.load()` RCE in `ms-swift`, 2025 | [official, NVD] |
| 5 | <https://www.oligo.security/blog/docling-rce-a-shadow-vulnerability-introduced-via-pyyaml-cve-2026-24009> | CVE-2026-24009 — RCE in Docling via unsafe PyYAML deserialization, 2026 | [community, security vendor] |
| 6 | <https://github.com/yaml/pyyaml/issues/41> | `pyyaml should detect duplicate keys and report an error` — open since 2015 migration | [official, project's own issue tracker] |
| 7 | <https://github.com/yaml/pyyaml/issues/165> | `Duplicate keys are not handled properly` — corroborating report | [official, project's own issue tracker] |
| 8 | <https://qudi-core-testing.readthedocs.io/en/george/_modules/ruamel/yaml/constructor.html> | `ruamel.yaml.constructor` source — `check_mapping_key()`, `DuplicateKeyError`, `allow_duplicate_keys` | [official, library source code] |
| 9 | <https://stackoverflow.com/questions/44904290/getting-duplicate-keys-in-yaml-using-python> | Getting duplicate keys in YAML using Python — legacy vs. new API duplicate-key behavior | [community] |
| 10 | <https://yaml.dev/doc/ruamel.yaml/pyyaml> | `ruamel.yaml` official docs — "Differences with PyYAML," YAML 1.1 vs 1.2, dropped `Yes`/`No`/`On`/`Off` | [official] |
| 11 | <https://github.com/pycontribs/ruamel-yaml> | `ruamel.yaml` GitHub — maintainer statement on unsafe `load()`, safe/round-trip modes | [official] |
| 12 | <https://github.com/yaml/pyyaml/issues/235> | `Billion laughs attack` — open PyYAML issue, no built-in alias-expansion cap | [official, project's own issue tracker] |
| 13 | <https://en.wikipedia.org/wiki/Billion_laughs_attack> | Billion laughs attack — YAML anchor/alias mechanism, StrictYAML as a mitigating design | [community, reference] |
| 14 | <https://stackoverflow.com/questions/69516085/ruamel-yaml-weird-behavior-with-datetime-like-values> | `ruamel.yaml` weird behavior with datetime-like values — implicit `datetime` coercion breaks `json.dumps` | [community] |
| 15 | <https://sourceforge.net/p/ruamel-yaml/tickets/509> | `ruamel.yaml` issue tracker — naive vs. UTC `datetime` parsing of timestamps | [official, project's own issue tracker] |
| 16 | <https://github.com/yaml/pyyaml/issues/895> | `Deeply Nested YAML Triggers SafeLoader RecursionError DoS` — filed Oct 2025 | [official, project's own issue tracker] |
| 17 | <https://pypi.org/project/PyYAML/> | PyYAML · PyPI — `cp314`/`cp314t` wheel listing (uploaded 2025-09-25) | [official] |
| 18 | <https://pypi.org/project/ruamel.yaml.clib/> | `ruamel.yaml.clib` · PyPI — `cp314` wheel listing (uploaded 2025-11-16) | [official] |
| 19 | <https://python-jsonschema.readthedocs.io/en/v4.8.0/validate> | `jsonschema` docs — `FormatChecker` semantics, format checks scoped to matching instance type | [official] |
| 20 | <https://json-schema.org/draft/2020-12/json-schema-validation> | JSON Schema Draft 2020-12 validation spec — `format` applies only to instances of the correct type | [official, standard] |
| 21 | <https://github.com/equinor/webviz-config/issues/396> | "Disable or take control over PyYAML's magic parsing of dates" — corroborating community report of implicit date coercion | [community] |
| 22 | <https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html> | OWASP Deserialization Cheat Sheet — general safe-deserialization guidance corroborating "never deserialize untrusted data with an unsafe loader" | [official, OWASP] |
| — | `docs/specs/docmend.md` §3.4 C-006, §7.1 FR-016, §7.4 DR-005, §8.6, §9, §13.6 | docmend spec of record (internal) | [official, internal] |
| — | `docs/open-questions.md` OQ-004, OQ-009, OQ-013 | docmend open-questions backlog (internal) | [official, internal] |
| — | `docs/research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md` | Prior docmend research establishing the duplicate-key/format-assertion requirement | [official, internal] |
| — | `docs/research/json-schema-validator-library.md` | Prior docmend research resolving the JSON Schema validator choice (`jsonschema` + `format-nongpl`) that this report's loader hardening feeds | [official, internal] |

[1]: https://pyyaml.org/wiki/PyYAMLDocumentation
[2]: https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation
[3]: https://www.sentinelone.com/vulnerability-database/cve-2020-14343
[4]: https://nvd.nist.gov/vuln/detail/CVE-2025-50460
[5]: https://www.oligo.security/blog/docling-rce-a-shadow-vulnerability-introduced-via-pyyaml-cve-2026-24009
[6]: https://github.com/yaml/pyyaml/issues/41
[7]: https://github.com/yaml/pyyaml/issues/165
[8]: https://qudi-core-testing.readthedocs.io/en/george/_modules/ruamel/yaml/constructor.html
[9]: https://stackoverflow.com/questions/44904290/getting-duplicate-keys-in-yaml-using-python
[10]: https://yaml.dev/doc/ruamel.yaml/pyyaml
[11]: https://github.com/pycontribs/ruamel-yaml
[12]: https://github.com/yaml/pyyaml/issues/235
[13]: https://en.wikipedia.org/wiki/Billion_laughs_attack
[14]: https://stackoverflow.com/questions/69516085/ruamel-yaml-weird-behavior-with-datetime-like-values
[15]: https://sourceforge.net/p/ruamel-yaml/tickets/509
[16]: https://github.com/yaml/pyyaml/issues/895
[17]: https://pypi.org/project/PyYAML/
[18]: https://pypi.org/project/ruamel.yaml.clib/
[21]: https://github.com/equinor/webviz-config/issues/396
