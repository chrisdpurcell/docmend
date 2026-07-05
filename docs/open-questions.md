# Open Questions — `docs/specs/docmend.md`

## Important Notes

- **Document Handling Rules and Guidelines:** [How to maintain this document](#how-to-maintain-this-document)
- **Terminology:**
  - _open question_ (`OQ-###`) is a decision still to be made — the primary unit of this document.
  - _resolved question_ (`RQ-###`, already settled) lives in the companion file [`resolved-questions.md`](resolved-questions.md).
- **Priority scale:** legacy OQ-001..014 use `P0 blocker` / `P1 near-blocker` / `P2 decision`. OQ-015+ (added by the 2026-07-05 gap analysis) carry both that label and a High / Medium / Low gap-analysis priority; the full ranked register with downstream-impact analysis lives in [`gap-analysis.md`](gap-analysis.md).

## Table of Contents

- [Open Questions — `docs/specs/docmend.md`](#open-questions--docsspecsdocmendmd)
  - [Important Notes](#important-notes)
  - [Table of Contents](#table-of-contents)
  - [Open questions](#open-questions)
    - [OQ-007 — controlled vocabularies](#oq-007--controlled-vocabularies)
      - [Agent notes](#agent-notes)
      - [My Comments](#my-comments)
    - [OQ-011 — EPUB export metadata](#oq-011--epub-export-metadata)
      - [Agent notes](#agent-notes-1)
      - [My Comments](#my-comments-1)
    - [OQ-012 — in-place mutation vs separate output root](#oq-012--in-place-mutation-vs-separate-output-root)
      - [Agent notes](#agent-notes-2)
      - [My Comments](#my-comments-2)
    - [OQ-013 — frontmatter required/null/omitted/status details](#oq-013--frontmatter-requirednullomittedstatus-details)
      - [Agent notes](#agent-notes-3)
      - [My Comments](#my-comments-3)
    - [OQ-014 — real-write CLI/config opt-in](#oq-014--real-write-cliconfig-opt-in)
      - [Agent notes](#agent-notes-4)
      - [My Comments](#my-comments-4)
    - [OQ-015 — encoding detector, confidence signal, and dual skip thresholds](#oq-015--encoding-detector-confidence-signal-and-dual-skip-thresholds)
      - [Agent notes](#agent-notes-5)
      - [My Comments](#my-comments-5)
    - [OQ-016 — CPU-bound concurrency primitive for the Python 3.14 target](#oq-016--cpu-bound-concurrency-primitive-for-the-python-314-target)
      - [Agent notes](#agent-notes-6)
      - [My Comments](#my-comments-6)
    - [OQ-017 — structured logging library, format, and verbosity mapping](#oq-017--structured-logging-library-format-and-verbosity-mapping)
      - [Agent notes](#agent-notes-7)
      - [My Comments](#my-comments-7)
    - [OQ-018 — JSON Schema validator library selection](#oq-018--json-schema-validator-library-selection)
      - [Agent notes](#agent-notes-8)
      - [My Comments](#my-comments-8)
    - [OQ-019 — property-based testing dependency (Hypothesis) approval](#oq-019--property-based-testing-dependency-hypothesis-approval)
      - [Agent notes](#agent-notes-9)
      - [My Comments](#my-comments-9)
    - [OQ-021 — internal data-model library (pydantic v2)](#oq-021--internal-data-model-library-pydantic-v2)
      - [Agent notes](#agent-notes-10)
      - [My Comments](#my-comments-10)
    - [OQ-022 — frontmatter YAML codec (ruamel.yaml vs PyYAML)](#oq-022--frontmatter-yaml-codec-ruamelyaml-vs-pyyaml)
      - [Agent notes](#agent-notes-11)
      - [My Comments](#my-comments-11)
    - [OQ-023 — deferred-review-artifact content-exposure policy (WH-002/WH-005)](#oq-023--deferred-review-artifact-content-exposure-policy-wh-002wh-005)
      - [Agent notes](#agent-notes-12)
      - [My Comments](#my-comments-12)
  - [How to maintain this document](#how-to-maintain-this-document)

## Open questions

### OQ-007 — controlled vocabularies

**Priority:** P2 decision **Owner:** owner **Needed by:** frontmatter emission scope; gated by RQ-008 **Spec references:** `docs/specs/docmend.md` §9, §21 OQ-007 · Related: RQ-010 (genericity), RQ-008 (frontmatter scope)

**Reframed by the owner (2026-07-05):** the decision is no longer "what fixed values should `genre`/`status`/`story_type`/`rating`/`lang` take." The owner's content is **sensitive**, and a controlled-vocabulary set describing it would itself leak clues about the documents. So docmend must support controlled vocabularies that are **user-definable, stored securely _outside_ the public repo, and per-document-set** (different corpora carry different vocabularies; a single global hardcoded taxonomy is unacceptable). The open decision is now the **mechanism** for that, and which generic default set (if any) ships in the public repo.

#### Agent notes

**Recommendation (revised for the reframing):** Treat controlled vocabularies as **externally-supplied, per-corpus configuration**, consistent with RQ-010's design-for-pluggable principle. Concretely:

- The frontmatter schema/validator is **vocabulary-agnostic**: it validates a facet value against an `enum` (or equivalent) **loaded from the run's vocabulary configuration**, not against a taxonomy hardcoded in the repo. This is the RQ-010 seam applied to §9.
- Real vocabularies live in a **user-owned vocabulary file referenced by config** (path or profile), kept outside the public repo and outside committed artifacts — the same confidential-content posture as §13.4 and OQ-023. docmend never writes the user's vocabulary set into the public repo, fixtures, or docs.
- The repo ships **only a small, generic, non-revealing example/default set** (e.g. `unknown`/`other`-style neutral values) for tests and for users who want a starting point — never the owner's real taxonomy.
- `lang` stays BCP 47 (RFC 5646); `tags` stays freeform and separate from the controlled facets.

**Open sub-decisions for the owner:** (1) the config surface for pointing at a vocabulary file/profile (single file vs named per-corpus profiles); (2) whether v1 ships any default set at all or leaves the facets unconstrained until a vocabulary is supplied; (3) the on-disk vocabulary format (reuse the TOML config codec vs a dedicated JSON/YAML vocab file). Per RQ-010 the seam must exist in v1 even if the swap machinery is minimal; per RQ-008 emission (and therefore vocabulary use) is optional and minimal in v1, so this can be shaped now and enriched later.

**Supporting information:** JSON Schema `enum` restricts a value to a fixed set but the set can be injected at validator-construction time rather than baked into the schema file. RFC 5646 / BCP 47 defines the `lang` model. The confidentiality constraint mirrors OQ-023 and §13.4 (vocabulary is a quasi-identifier for the corpus).

**Decision impact:** Shapes the OQ-004 frontmatter schema and validator wiring (they must accept an external vocabulary set) and adds a §18.2 config surface for the vocabulary source; gated behind RQ-008 for timing but the vocabulary-agnostic seam must be present when the schema is authored.

#### My Comments

I have some restrictions which may complicate this. The document set that I am working with is sensitive and a vocabulary set describing it would give clues as to the contents of the documents. I would like to be able to define my own controlled vocabulary set for my own use that is stored securely and separable from the docmend project overall. I would also like to be able to define my own controlled vocabulary set for each document set that I am working with, and not have to use a single set for all document sets. Different types of document sets will have different vocabularies.

### OQ-011 — EPUB export metadata

**Priority:** P2 decision **Owner:** owner **Needed by:** WH-004 or any v1 frontmatter emission expansion **Spec references:** `docs/specs/docmend.md` §9, §21 OQ-011

Decide whether root frontmatter should later include optional EPUB-export metadata fields such as `identifier`, `rights`, `creator`, and `cover-image`, and how they relate to `docmend.id`.

#### Agent notes

**Recommendation:** Defer EPUB-specific root metadata until frontmatter emission or export preparation is in scope. When added, keep it optional and distinct from docmend identity.

Use this split:

- `docmend.id`: immutable internal corpus identifier; required.
- `identifier`: optional EPUB/publication identifier; never a substitute for `docmend.id`.
- `creator`, `rights`, `publisher`, `cover-image`: optional export metadata only when the document is intentionally export-ready.
- Rich contributor data, if needed later, belongs in a namespaced internal object and is mapped to EPUB fields during export.

**Supporting information:** Pandoc documents EPUB metadata through YAML metadata blocks or `--metadata-file`, and recognizes fields such as `identifier`, `creator`, and `rights`. The variables docs show `title`, `author`, `date`, `lang`, `keywords`, `subject`, `description`, and related fields flowing into output metadata; EPUB has additional specialized needs.

**Reasoning:** Most legacy library files are not publication-ready works. Adding EPUB fields too early creates empty or misleading metadata, while `docmend.id` already solves internal traceability.

**Decision impact:** This can remain P2 unless RQ-008's optional/minimal frontmatter scope changes and bulk frontmatter emission moves into v1.

#### My Comments

### OQ-012 — in-place mutation vs separate output root

**Priority:** P0 blocker **Owner:** owner **Needed by:** before write-path implementation **Spec references:** `docs/specs/docmend.md` §8.5, §13.2, §18.2

Decide whether v1 mutates files in place or writes converted output to a separate output root. Align path containment, configuration, manifest paths, backup behavior, collision handling, and rollback semantics with that decision.

#### Agent notes

**Recommendation:** For v1, choose in-place mutation with atomic replace, backups, manifest, and path-containment checks. Do not add a separate output-root workflow until a later export/structural-conversion phase needs it.

Clarify the terminology:

- `source_root`: the library root scanned and planned.
- `target_path`: the planned path for each file after extension rename.
- `output_root`: not a v1 configuration setting unless you decide to support copy-out conversion.
- `backup_dir`: separate preservation location, not the output root.

If you prefer a separate output root, then v1 must add explicit config, path mapping, collision policy across two trees, verify semantics for source-vs-output, and restore rules. That is a larger workflow than the current spec describes.

**Supporting information:** The current architecture describes "Converted library" but the config table lacks `write.output_root`. Python `os.replace()` is atomic only when the replace succeeds on the same filesystem, which aligns naturally with in-place same-directory temp-file writes.

**Reasoning:** In-place mutation is riskier in intent but simpler and better specified by the current safety model. The safety comes from dry-run, preservation gate, backups, manifest, and atomic writes, not from copy-out alone.

**Decision impact:** This should be settled before writer implementation. If in-place wins, remove or clarify stray output-root language in the spec. If output-root wins, add a full config and artifact model for it.

#### My Comments

### OQ-013 — frontmatter required/null/omitted/status details

**Priority:** P1 near-blocker **Owner:** owner **Needed by:** frontmatter schema work; gated by RQ-008 **Spec references:** `docs/specs/docmend.md` §9

Tighten frontmatter schema details for required versus optional fields, when unknown values are represented as `null` versus omitted, and how `known`/`inferred`/`unknown` status metadata is represented.

#### Agent notes

**Recommendation:** Use this rule set for the schema:

- Required mechanical fields must always be present and non-null: `docmend.id`, `docmend.schema_version`, `source.original_path`, `source.hash`, `output.hash`.
- `title` remains required, but allow a deterministic placeholder plus status metadata until title inference is trustworthy.
- Optional unknown semantic fields are omitted by default, not emitted as `null`.
- Empty arrays are allowed only when the field is known to be intentionally empty, not merely unknown.
- Status/provenance for semantic fields should use a consistent wrapper or sidecar map rather than ad hoc `null`s.

One practical shape is:

```yaml
title: Untitled
metadata_status:
  title:
    state: unknown
    source: placeholder
    confidence: 0
```

**Supporting information:** JSON Schema `required` only checks property presence; type rules decide whether `null` is legal. The local frontmatter research recommends a strict JSON-serializable YAML subset and explicit known/inferred/unknown status so validation does not masquerade as provenance truth.

**Reasoning:** `null` in many optional fields makes frontmatter noisy and ambiguous: it does not tell readers whether the value is unknown, not applicable, intentionally blank, or not processed yet. A clear status model is more verbose only where uncertainty matters.

**Decision impact:** This should be resolved before frontmatter schema files are written. The current example in the spec should then be updated to match the chosen convention.

**Research update (2026-07-05 gap analysis):** Research adds a concrete parser-level constraint to the schema-detail decision (docs/research/safe-yaml-loading.md): both PyYAML and ruamel.yaml silently coerce unquoted ISO-date-like scalars into native datetime.date/datetime objects at parse time, which breaks JSON Schema 'format' assertions (they apply only to string instances). The frontmatter loader's timestamp constructor must be overridden to keep date/date-time scalars as strings so FR-016's 'malformed date is rejected' criterion actually fires. This reinforces the omit-by-default (not null) recommendation and the required-mechanical-fields set, and it should be captured alongside the frontmatter schema file under RQ-008's optional/minimal emission scope.

#### My Comments

### OQ-014 — real-write CLI/config opt-in

**Priority:** P1 near-blocker **Owner:** owner **Needed by:** MS-3 **Spec references:** `docs/specs/docmend.md` §7.1 FR-004, §7.3 IR-003, §18.2

Name the exact CLI flag and configuration behavior that opts into real writes when `apply` defaults to dry-run.

#### Agent notes

**Recommendation:** Use `docmend apply plan.json --write` as the positive opt-in for real writes. Keep `--dry-run` available and defaulted, but make `--write` and `--dry-run` mutually exclusive.

Suggested behavior:

- `docmend apply plan.json` performs a dry run.
- `docmend apply plan.json --dry-run` performs a dry run explicitly.
- `docmend apply plan.json --write` may mutate only if the RQ-005 safety gate passes.
- Config may keep `write.dry_run_default = true`, but config alone should not enable writes; the CLI invocation must include `--write`.

**Supporting information:** The spec requires destructive capabilities to be opt-in and says out-of-the-box `apply` cannot mutate anything. Keeping the opt-in at the command line prevents a stale config file from silently turning a preview into a write.

**Reasoning:** `--write` is blunt and hard to misunderstand. Names like `--no-dry-run` are technically precise but easier to miss in shell history and logs.

**Decision impact:** This unblocks CLI tests, docs, safety-gate tests, and the command examples in §10.1/§18.2.

#### My Comments

### OQ-015 — encoding detector, confidence signal, and dual skip thresholds

**Priority:** P0 blocker · Gap-analysis priority: High **Owner:** owner **Needed by:** MS-2 **Blocking:** Yes **Spec references:** `docs/specs/docmend.md` FR-007, §18.2 encoding.fail_below_confidence, A-003, G-005, §8.6 · Related: RQ-001 (v1 boundary)

Confirm charset-normalizer as FR-007's sole detector, define the decode-confidence score as 1.0 - CharsetMatch.chaos, keep the 0.80 fail_below_confidence default, and set a second independent skip gate keyed on non-ASCII byte count (default in the 8-20 range, encoding-family dependent).

#### Agent notes

**Recommendation:** Keep charset-normalizer only (do not add chardet — active licensing dispute, or faust-cchardet/uchardet — no 3.14 wheels/no confidence API). Adopt confidence = 1.0 - CharsetMatch.chaos, the library's own shipping chardet-compat formula (with the -0.2 penalty below 32 bytes), recording chaos/coherence/language separately as provenance. Keep the 0.80 threshold (always exceeds the worst-case penalized 0.70). Add a non-ASCII-byte-count floor as a second, independent skip gate, with the exact default validated against the weird-document corpus.

**Supporting information:** Report docs/research/encoding-detection-benchmark.md (20 citations): charset-normalizer 3.x CharsetMatch has no .confidence, only chaos/coherence; legacy detect() shim computes 1.0-chaos; documented GitHub issue #391 shows a 38-byte ASCII+1-byte string misdetected as Big5 at chaos=0.0 (max confidence, wrong) that no confidence threshold catches; Sivonen/chardetng convergence study shows windows-1252 needs ~20 and CJK ~10 non-ASCII bytes for reliable detection — so byte length is the wrong unit and a non-ASCII count floor is the right second gate.

**Reasoning:** The threshold governs false-skip/false-accept rates for the core safety premise; a single confidence scalar provably cannot catch the short-low-entropy failure mode that this .txt-heavy library is full of, so a second independent gate is required, not optional.

**Decision impact:** Unblocks MS-2 transform hardening with an evidence-backed decode/skip contract; without it FR-007 references a confidence API that does not exist as specified.

**Downstream impact:** Adds a non-ASCII-floor config key to §18.2, adds chaos/coherence/language provenance fields to the inventory schema (feeds RQ-004), reworks FR-007/FR-016 wording, and adds the report's fixture set to §17.2; also fixes GAP-43 (confidence-API mismatch) in the same change.

**Research update (2026-07-05, owner ChatGPT report):** `docs/research/python-library-research.md` independently confirms `charset-normalizer` as the FR-007 detector, but its proposed `DetectedEncoding` interface carries a `confidence: float` field — note that charset-normalizer 3.x exposes no `.confidence` (only `chaos`/`coherence`); use the `1.0 - chaos` formula from `docs/research/encoding-detection-benchmark.md` (this OQ's primary basis), not a `.confidence` attribute. The report also endorses recording the detector version and confidence in the plan (C.4 provenance).

**Research update (2026-07-05, charset-floor deep-research):** `docs/research/charset-detection-floors-for-legacy-text-ingestion.md` resolves the one sub-question this OQ left to empirical validation — the exact non-ASCII floor for the second, independent skip gate — and **narrows the provisional "8–20 range" to concrete defaults**:

- **Primary hard gate (default): `non_ascii_bytes >= 20`** before trusting any legacy (non-Unicode) guess. Basis: Sivonen/chardetng "document-length-equivalent" convergence — windows-1252/windows-1251 settle at ~20 non-ASCII bytes, legacy CJK at ~10, with almost everything converged by 50–90.
- **Optional family-aware override:** Western single-byte ≥ 20; CJK multi-byte ≥ 12; **Big5 relaxable to 10** (structurally distinctive on short input, per Sivonen), while GBK/GB18030 stays ≥ 12 ("bad with fewer than 6 hanzi").
- **The floor is count-based, not ratio-based.** The published evidence is in absolute non-ASCII counts. A ratio rule is only a secondary hardening signal for sparse long files: `total_bytes >= 4096 && non_ascii_ratio < 0.005 → mark the accepted legacy result "suspect" and prefer skip-and-report` (an engineering choice, not a literature constant).
- **Gate ordering (the floor applies last):** BOM sniff (authoritative, bypass legacy) → strict **full-file** UTF-8 validity (accept UTF-8, bypass legacy) → ASCII-only ⇒ treat as ASCII/UTF-8, never "detect" as legacy → only non-BOM, non-valid-UTF-8 files reach the byte-count floor.
- **Tradeoff (stated):** the 20-byte default deliberately false-skips some genuine tiny Latin-1 and very short CJK files in exchange for sharply cutting the `chaos=0.0`-but-wrong false-accept on short mostly-ASCII English — the dominant risk for this `.txt`-heavy corpus, where skip-and-report is the safe failure.
- **Version sensitivity (feeds §8.6 pin + FR-007 wording):** charset-normalizer **3.4.2** improved CJK reliability and **3.4.3** began damping confidence on small non-Unicode samples, so floor validation must run on ≥ 3.4.2 (3.4.7 ships 3.14 wheels); keep all ingest on explicit binary reads + explicit decode, not ambient `open()` defaults (3.15 moves to a UTF-8 default).
- **Fixtures:** the report's algorithmic synthetic/public-domain recipe (three axes — total length × non-ASCII count × placement; explicit false-accept and false-skip boundary sets; family-equivalent decode outcomes such as cp932≈Shift_JIS and GBK≈GB18030) should be added to the §17.2 weird-document corpus. **The final chosen number still needs one project-internal run against docmend's own short-file distribution before FR-007/§18.2 are edited.**

#### My Comments

### OQ-016 — CPU-bound concurrency primitive for the Python 3.14 target

**Priority:** P1 near-blocker · Gap-analysis priority: High **Owner:** implementer **Needed by:** MS-3 **Blocking:** No **Spec references:** `docs/specs/docmend.md` NFR-001, §14, §18.2 · Related: RQ-009 (performance targets, deferred)

Choose docmend's v1 concurrency primitive for the CPU-bound scan/plan/apply pipeline: process-based (ProcessPoolExecutor), free-threaded 3.14t, asyncio, or sequential-only, and the default worker count.

#### Agent notes

**Recommendation:** Adopt concurrent.futures.ProcessPoolExecutor with multiprocessing.get_context('forkserver') pinned explicitly (not the 3.14t free-threaded build, not asyncio — the workload is CPU-bound so async cannot help and GIL threading won't parallelize encoding detection). Default parallel.workers='auto' (os.process_cpu_count()) with a sequential mode (workers=1) as the default-until-profiled path used by all NFR-005 purity tests. Add a §18.2 parallel.\* surface (enabled, model, workers, start_method, chunksize, maxtasksperchild) with 'process'/'sequential' as the only v1 models and 'thread'/'interpreter' reserved. Fold numeric throughput targets into the deferred performance-target work (RQ-009).

**Supporting information:** Report docs/research/python-314-concurrency-model.md (19 citations): 3.14 free-threading is a separate non-default build (PEP 779); charset-normalizer is pure-Python and GIL-bound today; both named C-ext deps (charset-normalizer, rpds-py) already ship free-threading wheels so nothing blocks a future move; 3.14 changed the default Linux start method fork->forkserver (fork unsafe with threads); ProcessPoolExecutor gives fault isolation matching the writer-isolation architecture (D-003).

**Reasoning:** The choice determines whether the Must-priority NFR-001 parallel capability is implementable and sets worker defaults; process-based works on the standard interpreter every user has with zero new C-extension risk, while free-threading remains a moving target.

**Decision impact:** MS-5's 'parallelism if needed' currently silently demotes a Must NFR; a decided primitive lets the writer, worker-locking (GAP-23), and per-file watchdog (GAP-63) be designed coherently.

**Downstream impact:** Introduces the §18.2 parallel.\* config, a forkserver top-level-importable-target constraint on worker functions, the shared-artifact locking requirement (GAP-23), and the CI scale-test placement (GAP-54); folds into the deferred performance-target work (RQ-009) and §14.

**Research update (2026-07-05, free-threading deep-research):** `docs/research/docmend-and-the-free-threaded-cpython-switch-decision.md` **confirms this OQ's decision and adds the re-open criteria** it deferred to "a future CPython Phase III schedule." It does **not** change the v1 primitive — keep `ProcessPoolExecutor` + `forkserver`; do not retire multiprocessing.

- **Timeline / status:** free-threaded CPython is at PEP 779 **Phase II** (officially supported, non-default) in 3.14. **Phase III (default build) has no committed release target** — 3.15 is still completing the `abi3t` packaging/ABI transition (PEP 803), so a 3.15 flip is very unlikely; earliest plausible window is **3.16–3.17+**, flagged explicitly as a forecast, not a CPython commitment. The Steering Council record still reads "any decision to transition to Phase III … is still undecided."
- **Re-open trigger checklist (adopt as a release-gated re-check, not a one-time guess):** re-open when **any** release-channel trigger fires — a stable release makes the free-threaded build default, or the SC accepts the Phase III PEP, or `uv`/OS installers treat free-threading as first-class rather than opt-in; **and** all runtime/dep gates pass — `sysconfig Py_GIL_DISABLED == 1`, `sys._is_gil_enabled()` stays `False` after importing the **full** app (CPython auto-re-enables the GIL on an unmarked C extension), every native dep publishes `cp3xyt`/`abi3t` wheels, and pure-Python deps still pass their suites on a free-threaded build; **and** a docmend switch-benchmark shows the thread pool beats the process-pool baseline with zero correctness drift.
- **Dependency readiness snapshot:** `rpds-py` (jsonschema's Rust dep) and `charset-normalizer` already ship `cp314t` wheels and are the furthest ahead; `jsonschema`, `rich`, `typer`, `click`, `pathspec` are pure-Python `py3-none-any` (no ABI blocker, but PEP 803 warns loadable ≠ thread-safe).
- **`hashlib` caveat for the benchmark:** on GIL builds `hashlib` **already releases the GIL above 2047-byte buffers**, so SHA-256 has parallel headroom today; the free-threading upside is concentrated in the pure-Python detection/normalization hot loops. Weight the switch-benchmark corpus toward small/medium files, require zero output/hash/failure-accounting drift across executors, and verify the import graph keeps the GIL disabled.

Net: no v1 change; NFR-001/§14 unchanged. Re-run this checklist whenever the supported Python floor moves, the lockfile adds a C/Rust extension, or CPython announces Phase III.

#### My Comments

### OQ-017 — structured logging library, format, and verbosity mapping

**Priority:** P1 near-blocker · Gap-analysis priority: High **Owner:** owner **Needed by:** MS-0 **Blocking:** No **Spec references:** `docs/specs/docmend.md` §19 MS-0, NFR-003, §18.5, IR-005, §8.6

Choose the logging library, wire format, destination, field schema, and how --verbose/--quiet map to levels for a long-running batch CLI, and approve the new dependency under §8.6.

#### Agent notes

**Recommendation:** Adopt structlog wired through stdlib logging handlers (not loguru — last release predates 3.14 GA with an open unanswered compat issue), emitting JSON Lines to a per-run file named by run-ID plus Rich-rendered console text via ConsoleRenderer. Decouple --verbose/--quiet (console level only) from the file sink (always floored at DEBUG) so NFR-003's diagnose-without-re-running guarantee holds on quiet runs. Extend the never-auto-delete retention rule (§7.4/§18.6) to logs. Use QueueHandler+QueueListener with explicit per-worker init if NFR-001 parallelism lands (given the fork->forkserver default change).

**Supporting information:** Report docs/research/structured-logging-library.md (27 citations): structlog ~2x faster than stdlib+json/loguru on 3.14, actively released post-3.14, composes with stdlib handlers and the already-approved Rich; loguru 0.7.3 shipped 2024-12 with no 3.14 statement; no existing OQ covers logging and §8.6 requires owner approval for the new dependency.

**Reasoning:** At 100k+ files, log volume/format/destination determines whether NFR-003 mid-batch post-mortem debugging is feasible; this MS-0 decision has no current owner.

**Decision impact:** Unblocks MS-0 observability scaffolding and defines the log-schema keyed on run-ID that every command emits.

**Downstream impact:** Adds a §8.6 dependency row, a per-run JSONL log-schema cross-referenced to the run-ID (GAP-27), the console-flag semantics (GAP-17), and the heartbeat/progress line (GAP-20).

**Research update (2026-07-05, owner ChatGPT report):** `docs/research/python-library-research.md` reaches the OPPOSITE conclusion to this OQ's recommendation — it advises AVOIDING `structlog` in v1 and starting with stdlib `logging` plus structured JSON artifacts, on dependency-minimization grounds. This OQ's recommendation (from `docs/research/structured-logging-library.md`) favors `structlog` for throughput and per-run JSON Lines. Both are defensible; the owner should decide with both arguments in view. If stdlib `logging` is chosen, the per-run JSONL schema and run-ID correlation (NFR-003) can still be met with a stdlib JSON formatter, avoiding the new runtime dependency.

#### My Comments

### OQ-018 — JSON Schema validator library selection

**Priority:** P1 near-blocker · Gap-analysis priority: Medium **Owner:** owner **Needed by:** MS-1 **Blocking:** Yes **Spec references:** `docs/specs/docmend.md` §8.6, FR-016, DR-005, RQ-004 · Related: RQ-004 (artifact schemas)

Resolve §8.6's Conditional JSON Schema validator row to a specific library, given Draft 2020-12 and format-assertion requirements at hundreds of thousands of validations per run.

#### Agent notes

**Recommendation:** Adopt jsonschema>=4.26 with the format-nongpl extra and an explicit Draft202012Validator + FormatChecker, reusing one compiled validator instance per schema across a run (~10x faster than per-call validate()). Do not adopt fastjsonschema (only drafts 04/06/07, disqualified) or check-jsonschema as a runtime dep (a jsonschema-wrapping CLI with a requests dependency unfit for an offline tool) — use check-jsonschema only as a pre-commit hook linting schemas/\*.schema.json. Record jsonschema-rs as the pre-vetted escalation path if profiling later shows a bottleneck (its own §8.6 OQ).

**Supporting information:** Report docs/research/json-schema-validator-library.md (18 citations): jsonschema 4.26 has full Draft 2020-12 support and a 3.14 classifier; its sole Rust dep rpds-py ships cp314/cp314t wheels; format assertion is off by default and needs the extra + explicit FormatChecker; validator-reuse caps added CPU cost at tens of seconds against a multi-hour I/O-bound run.

**Reasoning:** Per Appendix B.2 the dependency cannot land without an approved OQ, and it is only conditionally pre-approved pending that OQ; the validator is required for FR-016/DR-005 schema enforcement at MS-1.

**Decision impact:** Unblocks the OQ-004 schema-authoring and MS-1 validation work with a concrete, 3.14-ready, format-asserting validator.

**Downstream impact:** Adds a §8.6 runtime dependency row, a validator-reuse discipline note, and the format-nongpl license consideration; couples to the license-scan policy (GAP-59) and the versioning policy (GAP-29).

**Research update (2026-07-05, owner ChatGPT report):** `docs/research/python-library-research.md` independently confirms this OQ — use `jsonschema` (not a homegrown validator) with an explicit `FormatChecker` (format is annotation-only by default) and Draft 2020-12; it further advises parsing critical `date`/`date-time` fields explicitly rather than trusting `format` alone (reinforcing `docs/research/safe-yaml-loading.md`).

#### My Comments

### OQ-019 — property-based testing dependency (Hypothesis) approval

**Priority:** P2 decision · Gap-analysis priority: Medium **Owner:** owner **Needed by:** MS-1 **Blocking:** No **Spec references:** `docs/specs/docmend.md` §17.2, §8.6, NFR-005, Appendix B.2

Approve Hypothesis as a dev-only test dependency to satisfy §17.2's 'property-based tests where cheap', which §8.6 currently does not authorize.

#### Agent notes

**Recommendation:** Adopt Hypothesis as a dev-only dependency in [dependency-groups].dev (never [project.dependencies]) with a CI settings profile (register_profile/load_profile) loosening or disabling deadline to avoid CI timing flakiness, and keep Transform-layer tests fixture-free per NFR-005. Split §8.6 into Runtime vs Dev/Test subsections since pytest/ruff/basedpyright/coverage/pip-audit already sit outside it by omission.

**Supporting information:** Report docs/research/property-based-testing-hypothesis.md (15 citations): Hypothesis 6.156 ships cp310-cp314 wheels including 3.14t; only always-installed transitive dep is sortedcontainers (MIT); MPL-2.0 but dev-only so never distributed in the MIT package; two documented CI footguns (deadline flakiness, function_scoped_fixture) both have simple mitigations.

**Reasoning:** There is a direct process contradiction: §17.2 requires property tests while §8.6's footer forbids an unlisted dependency without an OQ; an implementer cannot honor the requirement without filing this OQ.

**Decision impact:** Enables NFR-005 transform-purity and edge-case property tests at MS-1 without violating the dependency gate.

**Downstream impact:** Adds a §8.6 Dev/Test row and a CI settings profile; the §8.6 Runtime-vs-Dev split it prompts also regularizes the already-ungated pytest/ruff/etc. tooling.

**Research update (2026-07-05, owner ChatGPT report):** `docs/research/python-library-research.md` confirms `hypothesis` for transform/idempotency/risk-classifier property tests and adds two dev-test companions: `pyfakefs` for fast scan/plan/filter tests (explicitly NOT for atomic-write/fsync/crash/permission/symlink tests, which need real-filesystem integration) and `pytest-xdist` for parallelizing the growing weird-document corpus. Both belong in the §8.6 Dev/Test split this OQ proposes.

#### My Comments

### OQ-021 — internal data-model library (pydantic v2)

**Priority:** P2 decision · Gap-analysis priority: Medium **Owner:** owner **Needed by:** MS-1 **Blocking:** No **Spec references:** `docs/specs/docmend.md` §7.4 DR-001-DR-004, §9, §8.6 · Related: RQ-004 (artifact schemas), OQ-018

Decide whether v1 adopts `pydantic` v2 as the internal model layer for config, inventory, plan, report, manifest, and per-action/skip records, or uses stdlib dataclasses / typed dicts with manual validation. Adding the dependency requires this OQ and a §8.6 row (Appendix B.2).

#### Agent notes

**Recommendation:** Adopt `pydantic` v2 (>= 2.12, which introduced Python 3.14 support; v1 is not 3.14-compatible) as the internal artifact/config model layer, using strict models with `extra='forbid'`. Keep the hand-authored, checked-in JSON Schemas (OQ-004) as the durable EXTERNAL artifact contract rather than deriving them solely from models; use pydantic's JSON Schema emission only to cross-check the hand-authored schemas in tests.

**Supporting information:** `docs/research/python-library-research.md` (owner ChatGPT Deep-Research): the four JSON artifacts plus config snapshots and action records are structured enough that plain dicts become a defect source; pydantic v2.12 added initial 3.14 support and can emit Draft 2020-12 JSON Schema. This complements OQ-018 — `jsonschema` validates the external artifact contract, pydantic guards internal construction.

**Reasoning:** At 100k-file scale, unvalidated dicts let shape errors reach disk and downstream commands before anything catches them; a strict model layer fails fast at construction. Keeping hand-authored schemas as the external contract preserves the OQ-004 durability guarantee independent of the model library.

**Decision impact:** Adds a §8.6 runtime dependency row; sets the internal representation for the OQ-004 schema work at MS-1; establishes the model-vs-hand-authored-schema division of labor with OQ-018.

**Downstream impact:** OQ-004 artifact schemas would be authored as (or cross-checked against) pydantic models; introduces a models module under `src/docmend/`; couples to OQ-018 (external validator) and the schema-versioning policy. If rejected, artifacts use dataclasses/TypedDicts plus manual validation.

#### My Comments

### OQ-022 — frontmatter YAML codec (ruamel.yaml vs PyYAML)

**Priority:** P2 decision · Gap-analysis priority: Medium **Owner:** owner **Needed by:** Frontmatter validation work (gated by RQ-008) **Blocking:** No **Spec references:** `docs/specs/docmend.md` §9, FR-016, DR-005, §8.6 · Related: RQ-008 (frontmatter scope), OQ-013

Choose the YAML library for parsing and (later) emitting product frontmatter: `ruamel.yaml` (round-trip, key-order/comment preservation) or `PyYAML` (mainstream, but needs a custom duplicate-key-rejecting loader). Add the corresponding §8.6 row.

#### Agent notes

**Recommendation:** Use `ruamel.yaml` behind a `FrontmatterCodec` abstraction (duplicate-key rejection, controlled quoting/block scalars, Pandoc-compatible emission), with `PyYAML` plus a custom duplicate-key-rejecting loader as the documented fallback if ruamel.yaml's Beta / single-maintainer risk becomes unacceptable. Regardless of choice, override the timestamp/date constructor so `date` and `date-time` scalars stay strings — otherwise JSON Schema `format` assertions never fire (`docs/research/safe-yaml-loading.md`, OQ-013). Gate runtime-vs-fixture-only timing on RQ-008.

**Supporting information:** `docs/research/python-library-research.md` (ruamel.yaml round-trip fidelity + 3.14 compat; Beta/single-maintainer caveat; PyYAML mainstream but insufficient for duplicate-key safety without a custom loader) and `docs/research/safe-yaml-loading.md` (both PyYAML and ruamel silently coerce ISO-date scalars to `datetime`, breaking string-only `format` assertions — the loader must override the timestamp constructor). Pandoc requires quoting/block-scalar discipline for colons, backslashes, and blank lines (C-006).

**Reasoning:** Frontmatter needs stricter guarantees than 'parse some YAML' — duplicate-key rejection (C-006/FR-016), controlled emission, and string-preserved dates. The codec choice decides whether those safety properties are built in (ruamel) or must be hand-rolled (PyYAML).

**Decision impact:** Adds a §8.6 row; sets the `FrontmatterCodec` implementation for FR-016 validation and any OQ-009 emission; binds the date-string-preservation requirement into the loader.

**Downstream impact:** If ruamel.yaml: a heavier but round-trip-safe codec. If PyYAML: a custom loader with duplicate-key + timestamp overrides. Timing (MS-5/fixtures vs. core runtime) follows RQ-008's optional/minimal emission scope; couples to OQ-013 (schema detail) and the missing `schemas/frontmatter.schema.json`.

#### My Comments

### OQ-023 — deferred-review-artifact content-exposure policy (WH-002/WH-005)

**Priority:** P2 decision · Gap-analysis priority: Low **Owner:** owner **Needed by:** WH-002 / WH-005 design (deferred — §2.3) **Blocking:** No **Spec references:** `docs/specs/docmend.md` §2.2 NG-001, §2.3 WH-002/WH-005, §11, §13.4, §13.5 · Related: RQ-001 (v1 boundary), RQ-010 (genericity)

Decide how much document content a headless deferred-review artifact may carry before it crosses NG-001's "no reading/browsing interface" boundary, and the default review posture — for the deferred semantic-correction (WH-002) and fuzzy-duplicate (WH-005) capabilities. Raised by prompt 4 of the deep-research queue, which surfaced a genuine, previously-undocumented conflict: docmend's artifacts are deliberately hash-and-path-only and its content is confidential (§13.4), yet a WH-002 correction cannot be reviewed without showing the changed text, and NG-001 forbids a reading UI. No existing OQ owned this decision.

#### Agent notes

**Recommendation:** Adopt the content-exposure boundary **"issue-bounded, decision-sufficient, non-navigable, and opt-in for text."** A review artifact stays headless (NG-001-compatible) when it is keyed to a finite set of flagged issues/clusters, carries only the minimum information needed for a yes/no/edit verdict, and offers no search, browse, whole-file expansion, or progressive-context surface inside docmend. Concretely:

- **WH-005 (fuzzy duplicates): metadata-only by default** — `cluster_id`, path aliases, sizes, hashes, similarity scores, recommended canonical, blank `decision` field. Body text is unnecessary. Matches `rdfind`/`fclones` report-then-act precedent.
- **WH-002 (semantic corrections): durable metadata ledger with no body text by default.** Any text lives in an **opt-in, local-only ephemeral sidecar** keyed by `issue_id` (the "durable-manifest / ephemeral-sidecar" split, by analogy to Terraform `sensitive` vs `ephemeral`), or is handed off to an **external diff tool** — never embedded in the durable artifact by default. When text is exposed, use **bounded unified-diff-style hunks with tight operator-configurable char/line caps**, **path aliases not raw paths** (paths are quasi-identifiers), and optional PII redaction as a secondary (not default) mode.
- **Default posture: pessimistic-skip / exception-only**, capped batches, `decision` left null (no pre-filled "accept"), no bulk-approve for text-bearing changes. The automation-bias literature (Goddard et al. 2012; Cummings; Green) shows large repetitive review queues degrade into rubber-stamping — so "review everything" is the wrong default twice: it leaks more text than necessary and manufactures the conditions for rubber-stamping.
- **Public-repo / confidential split:** text-bearing review artifacts are **private local artifacts**, never ordinary build outputs, never repo/CI artifacts, and never version-controlled; do not retain long-lived snippet archives (NIST SP 800-188 repeated-release risk). Fixtures/tests/docs stay synthetic or public-domain (C-002) regardless.
- **Load-bearing answer to "keep WH-002 review out of docmend entirely?":** docmend may **identify, package, and record** review decisions; **external tools render text**. Keeping rendering out of docmend is the cleanest NG-001 alignment and lowest-maintenance path — but it does not require forbidding docmend from generating a minimal machine-readable handoff bundle.

**Supporting information:** `docs/research/docmend-deferred-review-artifacts-for-confidential-corpora.md` (headless report-then-act survey — `patch`/`git apply --reject`, unified diff, `rdfind`/`fclones`, `dedupe`'s engine/UI split, Terraform plan; ISO/IEC 20889 and NIST SP 800-188 de-identification/output-governance guidance; automation-bias evidence). The report states plainly that no cited source gives a formal industry definition of "headless" for confidential-document remediation — the boundary is a well-supported architectural inference, not a standard.

**Reasoning:** The decision sits at the intersection of an architectural non-goal (NG-001), a confidentiality threat model (§13.4/§13.5), and de-identification standards, so it is an owner policy call rather than a factual lookup. Settling it now — while the research is fresh — prevents WH-002/WH-005 design from either silently building a de-facto reading UI or blocking on an unmade policy decision.

**Decision impact:** Sets the artifact shape and default posture for the future WH-002/WH-005 review workflows; would add a note to §11 (how a decision artifact stays distinct from NG-001's forbidden UI) and to §13.4/§13.5 (text-bearing review artifacts as a distinct, private, non-versioned sensitive-data class with its own leakage mitigation). Non-blocking because WH-002/WH-005 are deferred (§2.3); revisit when either is scheduled.

**Downstream impact:** If adopted, the future WH-002 artifact is a two-layer (durable metadata ledger + opt-in ephemeral text sidecar / external-diff handoff) design and WH-005 is a metadata-only cluster report; both feed the OQ-004 artifact-schema family when that work reaches the deferred capabilities. If the owner instead delegates WH-002 review wholly to external diff tools, docmend stops at detection + decision-recording and emits no text at all.

#### My Comments

## How to maintain this document

These rules govern **both** files: this one (open) and its companion [`resolved-questions.md`](resolved-questions.md) (settled).

- Read **[Open questions](#open-questions)** for anything that still needs a call. Everything settled lives in [`resolved-questions.md`](resolved-questions.md) — you should not have to read it to know what's outstanding.
- When a question is settled, move it to [`resolved-questions.md`](resolved-questions.md). If a question is partially settled, move the decided half there and leave a focused open question here covering _only_ the remaining fork.
- Once an ADR is written for a settled question, the resolved decision can be safely condensed to an ADR pointer or removed from `resolved-questions.md` to control its size. The ADR is the canonical record of the decision.

**Rules:**

1. **Open questions first, distilled.** Each open question states _only_ the unresolved decision — not the history behind it. The history lives in `resolved-questions.md` and in the research reports.
2. **When a question is settled, move it to `resolved-questions.md`.** Relocate its substance there (record the decision + any ADR) and remove it from this file. Never leave a settled item in Open questions.
3. **Split partially-settled items.** If a gap is half-decided, move the decided half to `resolved-questions.md` and leave a focused open question here covering _only_ the remaining fork.
4. **Two comment layers per open question, kept separate:**
   - `#### Agent notes` — research/reconciliation context, maintained by the assistant.
   - `#### My Comments` — the owner's notes and decisions; **the assistant does not edit this block.** (When an OQ is relocated to `resolved-questions.md`, its owner comments are preserved verbatim.)
5. **Cross-reference by stable ID.** `OQ-###` = open question and `RQ-###` = resolved question. ADRs, the spec, and TODO link here by those IDs — keep them stable. Heading anchors derive from heading _text_, so moving an item between files changes file-qualified links such as `open-questions.md#oq-001--...`; update every referring ADR/TODO/spec/research link in the same change. If you must renumber, update the referencing docs in the same change.
6. **Not a log:** Do not append a log of routine maintenance or administrative changes. This is a _decision record_, not a change log. Use the Git history for that and `docs/handoff.md` and/or `TODO.md` where appropriate.
