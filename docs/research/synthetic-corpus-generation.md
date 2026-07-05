---
schema_version: '1.0'
id: synthetic-corpus-generation
title: Synthetic Corpus Generation and Public-Safe Anonymization of Real Anomalies
description: How docmend should generate a 100k-file synthetic test corpus and turn a real-library anomaly into a content-free, shareable fixture without leaking personal content.
doc_type: research
status: active
created: '2026-07-05'
updated: '2026-07-05'
reviewed: '2026-07-05'
owner: 'Chris Purcell'
consumer: mix
tags:
  - synthetic-data
  - test-fixtures
  - digital-preservation
  - anonymization
  - encoding-testing
  - docmend
aliases:
  - synthetic test corpus
  - weird-document corpus
  - fixture anonymization procedure
  - GAP-49
related:
  - 'docs/specs/docmend.md#172-test-strategy'
  - 'docs/specs/docmend.md#9-data-model'
  - 'docs/open-questions.md#oq-004--artifact-json-schemas'
  - 'docs/open-questions.md#oq-010--performance-targets'
  - 'docs/research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md'
  - 'docs/research/self-hosted-corpus-storage-options.md'
supersedes: []
superseded_by: null
depends_on: []
applies_to:
  - 'src/docmend'
  - 'tests'
source:
  - 'https://hypothesis.readthedocs.io/en/latest/data.html'
  - 'https://github.com/chardet/test-data'
  - 'https://github.com/openpreserve/format-corpus'
  - 'https://www.iso.org/obp/ui#iso:std:iso-iec:20889:ed-1:v1:en'
  - 'https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf'
confidence: medium
visibility: public
license: null
---

# Synthetic Corpus Generation and Public-Safe Anonymization of Real Anomalies

**Date:** 2026-07-05 **Related:** GAP-49 · `docs/specs/docmend.md` §17.2 (Test Strategy, "weird-document corpus"), §17.3, §9 (Data Model), §19 MS-5, NFR-001 · `docs/open-questions.md` OQ-004 (artifact schemas), OQ-010 (performance targets) · repo convention #6 (Sensitive Data, `AGENTS.md`) · prior research: `managing-pandoc-markdown-and-strict-yaml-frontmatter.md`, `self-hosted-corpus-storage-options.md`

## Gap it fills

The spec requires a 100,000-file synthetic corpus for the NFR-001 scale test and a continuously-growing "weird-document corpus" for regression coverage (§17.2), but nothing in the spec, `AGENTS.md`, or the two prior research reports says **how** that corpus is built, where it physically lives so a public repo never carries 100k generated files or their storage weight, or what procedure lets the owner turn a real anomaly discovered on the actual library (e.g., a corrupted-encoding byte sequence) into a fixture that reproduces the failure in CI without any byte of the original private document surviving. This report closes that gap with a concrete generator design, a fixture-authoring convention, and a step-by-step anonymization/minimization procedure, grounded in how existing digital-preservation and encoding-detector projects already solve this exact problem.

## Executive summary

Do not treat "100k synthetic files" and "the weird-document regression corpus" as the same artifact — they have opposite storage and provenance requirements, and conflating them is the most likely mistake:

| Artifact | Purpose | Size | Where it lives | Committed to git? |
| --- | --- | --- | --- | --- |
| **Scale corpus** (NFR-001, MS-5) | Prove bounded memory/throughput at 100k files | 100,000 files | Generated on demand into `tmp_path_factory` / a gitignored cache directory | **Never** |
| **Weird-document corpus** (§10.3, §17.2) | Pin every anomaly class as a permanent regression fixture | Tens to low hundreds of small files | `tests/fixtures/weird_documents/` in the repo | **Yes** — but only because each file is small, synthetic, and content-free by construction |

Both are produced by the **same generator module** (`tests/support/corpus_gen.py`, a pure, seedable function library — consistent with docmend's own NFR-005 "pure transform" design ethos), parameterized by a small YAML/JSON recipe describing anomaly classes and counts. The scale corpus calls the generator at test-collection time with a large count and writes to a temp directory that is deleted after the run; the weird-document corpus calls the same generator once, offline, to produce small hand-reviewed files that are then committed. Real anomalies enter the weird-document corpus only through the anonymization procedure in this report — never by copying bytes from the real library.

## Corpus-generator design

### 1. Generator architecture

Model the generator on the same layered discipline the spec already uses for the pipeline itself (§8.1): a pure **recipe → bytes** function per anomaly class, with no filesystem access, so the generator itself is unit-testable and the writer (whatever materializes files to disk for a given test) is a thin, separately-tested adapter. This mirrors NFR-005's transform/writer split and keeps the generator reviewable the same way a docmend plan is reviewable (D-006).

- **Recipe table** — a small, versioned, in-repo YAML/JSON file (e.g., `tests/fixtures/corpus_recipes.yaml`) listing anomaly classes, each with a generator function name, a weight/count, and parameters (target encoding, newline style, size range, confidence-threshold zone). Treat this recipe file the way the spec treats a plan: a reviewable, diffable artifact, not code.
- **Pure generator functions** — one function per class (`gen_windows1252_high_confidence(rng, size) -> bytes`, `gen_mixed_newlines(rng) -> bytes`, `gen_nul_byte_binary_disguised_as_txt(rng) -> bytes`, etc.), each taking a seeded `random.Random` (or a Hypothesis strategy — see below) and returning bytes only. No disk I/O in this layer, matching NFR-005's constraint that transforms are pure text/byte functions.
- **Materializer** — a thin adapter that takes `(recipe, output_dir)` and writes files, used only by the two corpus targets (scale corpus, weird-document corpus). This is the only layer touching disk, mirroring the spec's writer isolation principle (§8.1).

### 2. Property-based generation for the base text and the encoding/newline dimensions

Use [Hypothesis](https://hypothesis.readthedocs.io/en/latest/data.html) `[official]` as the base engine for varying content shape (line lengths, blank-line runs, whitespace patterns, Unicode text ranges) rather than hand-rolling random generators — it is already an implicit dependency-of-choice for a strict-BasedPyright/pytest Python 3.14 stack and integrates natively with pytest. Two Hypothesis features matter specifically for the weird-document corpus:

- **`@example(...)`** lets a property-based test pin a specific, previously-discovered failing input so it always runs, in addition to randomly generated ones — [official, Hypothesis "Replaying failed tests"](https://hypothesis.readthedocs.io/en/latest/tutorial/replaying-failures.html). This is the mechanism for promoting a reconstructed real-world anomaly (see the anonymization procedure below) into a permanent regression case without needing a separate fixture file at all, when the anomaly is small enough to express inline as bytes.
- **Third-party strategy libraries** such as [hypothesmith](https://github.com/Zac-HD/hypothesmith) (generates syntactically-valid Python, "something like CSmith") demonstrate the pattern of a domain-specific generator strategy layered on Hypothesis primitives `[community]` — docmend's own encoding/newline/whitespace generators should follow the same shape: composable strategies specific to the anomaly domain, not generic `st.text()`.
- Hypothesis's [Ghostwriter](https://hypothesis.readthedocs.io/en/latest/ghostwriter.html) (`hypothesis write`) `[official]` can bootstrap property tests for the pure transform functions (newline normalization, whitespace collapsing) directly from their type signatures — useful for MS-2's transform-layer tests, separate from corpus generation itself.

### 3. Encoding and byte-level anomaly generation

Hypothesis's generic `st.text()`/`st.binary()` strategies are the wrong tool for encoding-specific anomalies (mojibake has causal structure, not random byte noise). Generate encoding anomalies deterministically instead:

1. Start from a small set of **public-domain or Faker-generated plain-text paragraphs** (see below) that contain the specific character classes needed (e.g., a paragraph with curly quotes and an em dash to test Windows-1252/UTF-8 confusion).
2. Encode to the _target_ legacy encoding (`cp1252`, `latin-1`, etc.) via Python's `codecs` module — this is exactly how the real library's files came to exist, so it is a faithful reproduction of the mechanism, not just the symptom.
3. For mojibake-class anomalies (double-encoding), decode with the _wrong_ codec and re-encode to UTF-8, replicating the documented UTF-8 → Windows-1252 confusion chain described in [ftfy's mojibake-avoidance guide](https://ftfy.readthedocs.io/en/v6.0/avoid.html) `[official]` and explained mechanically in [brokkr.net's UTF-8 mojibake walkthrough](https://brokkr.net/2022/04/20/fun-with-character-encoding-errors-part-i) `[blog]`. `ftfy`'s own documentation is explicit that "most mojibake comes from decoding correct UTF-8 as if it were some other encoding" — generate anomalies by reproducing that exact chain, not by inserting arbitrary invalid bytes.
4. For low-confidence/ambiguous fixtures (FR-007's 0.80 threshold), generate short files (encoding detectors need statistical mass; short ASCII-heavy files are inherently ambiguous between encodings) and verify against `charset-normalizer` `[official, charset-normalizer docs]` directly in the recipe test, so the recipe is self-checking: a fixture claimed as "below-threshold" must actually score below threshold against the real detector docmend uses, not just be assumed to.

### 4. Size and variety distribution

Do not sample anomaly classes at their "natural" real-world frequency. Follow the seed-corpus philosophy documented by [OSS-Fuzz](https://google.github.io/oss-fuzz/advanced-topics/ideal-integration) `[official]`: a seed/test corpus is deliberately optimized for **coverage of code paths**, not realistic frequency — a corpus that mirrors real-world proportions (99% clean UTF-8 files) would under-test the skip-and-report paths that are docmend's actual safety-critical surface (G-005, FR-015). Recommended distribution for the two corpora:

| Corpus | Distribution rule |
| --- | --- |
| Scale corpus (100k, NFR-001) | ~90% "boring" well-formed UTF-8/ASCII text of varying sizes (this is what actually stresses memory-boundedness and throughput); ~10% drawn from the same weighted anomaly classes as the weird-document corpus, so the scale run also exercises planning/skip logic at volume, not just the happy path. |
| Weird-document corpus (§10.3) | Roughly even weight per §10.3 edge case (EC-001–EC-008) plus every anomaly class discovered from the real library via the anonymization procedure — coverage-complete, not frequency-realistic. Each class gets at least 2–3 size variants (near-empty, typical, and a size near any threshold like the blank-line-collapse maximum). |

### 5. Generated-at-test-time strategy (never commit the 100k corpus)

Use pytest's built-in [`tmp_path_factory`](https://docs.pytest.org/en/stable/how-to/tmp_path.html) `[official]` (session-scoped, unlike function-scoped `tmp_path`) as the materialization target for the scale corpus: a session-scoped fixture calls the generator with `count=100_000` and a fixed seed, writes to a `tmp_path_factory.mktemp("scale_corpus")` directory, and the NFR-001 test runs scan/plan/apply against it. Nothing under this path is ever added to git; it does not need to be gitignored either, because it never lives inside the repository tree. Record the seed in the test's failure output so a failing scale run is exactly reproducible without storing the corpus itself.

For fast, everyday CI runs, gate the full 100k-file generation behind an explicit marker/env var (e.g., `RUN_SCALE_TEST=1` or a pytest `@pytest.mark.slow`) and default CI to a much smaller count (e.g., 500–2,000 files) that still exercises every code path — this is the same "default-off, explicit opt-in for expensive work" posture the spec already applies to real writes (OQ-014, `--write`) and dry-run defaults (NFR-004), applied to test cost instead of corpus risk.

Where an in-memory fake filesystem would help: [pyfakefs](https://pytest-pyfakefs.readthedocs.io/en/latest/intro.html) `[official]` mocks Python's filesystem modules so tests run against an in-memory tree with no real disk I/O — useful for planning-layer unit tests that need "100k inventory records" without materializing 100k real files at all, cutting scale-test wall-clock time for pure logic. It is not a substitute for the writer-layer atomicity tests (NFR-002's kill-during-write, fsync/`os.replace` semantics): a fake filesystem cannot faithfully model real crash/fsync ordering, so those tests must still run against a real (if temporary) filesystem. `pyfakefs` maintainers already track Python 3.14 compatibility explicitly (`os.readinto`, `pathlib.glob` fixes) in their [changelog](https://github.com/pytest-dev/pyfakefs/blob/main/CHANGES.md) `[official]`, confirming current-version fitness for this stack.

### 6. Synthetic-but-realistic filler text

For the "boring 90%" and for filler prose inside anomaly-class fixtures, use [Faker](https://faker.readthedocs.io/) `[official]` (`faker.lorem`) rather than hand-written prose — it is explicitly designed for exactly this ("bootstrap your database... anonymize data taken from a production service," per Faker's own docs) and guarantees no accidental resemblance to real content since it is templated pseudo-Latin/locale text, not derived from any corpus of real writing. Do not use realistic-sounding LLM-generated prose as filler when the goal is provable content-freeness — Faker's deterministic, clearly-synthetic output is _auditable_ as non-real by inspection, which matters for a public repo where a reviewer must be able to confirm "this is not real library content" without cross-referencing anything.

## Fixture-authoring convention

1. **Location and size ceiling.** Committed anomaly fixtures live under `tests/fixtures/weird_documents/<class>/<case-id>.<ext>`, one file per case, capped at roughly 2 KB each. This mirrors the [Open Preservation Foundation's `format-corpus`](https://github.com/openpreserve/format-corpus) `[official]` pattern of "small example files... covering a wide range of formats," which exists precisely so a format/anomaly test corpus stays lightweight and reviewable in a public, general-purpose repository.
2. **Provenance metadata, never source content.** Each fixture ships a sidecar (`<case-id>.meta.json` or a leading comment for text formats) recording: anomaly class, expected docmend behavior (skip reason code / conversion outcome), and a provenance line that is _always_ one of `"synthetic"` or `"derived from a real-library anomaly; structurally reproduced, no original bytes retained"` — never a filename, date, or excerpt from the source. This directly follows the model of [`chardet`'s dedicated `test-data` repository](https://github.com/chardet/test-data) `[official]`, whose own `CLAUDE.md` states the convention explicitly: "The directory name is the ground truth encoding for the raw bytes," and its `CATALOG.md` records "every file's provenance and characteristics" `[official]` separately from the file content itself — provenance and payload are deliberately decoupled.
3. **Separate data-only concerns from code.** `chardet` keeps its ~2,178 encoding test files in a _separate_ repository from the detector's source code `[official, chardet/test-data]`, and `format-corpus` is likewise a repository of nothing but example files `[official]`. docmend is small enough (tens to low hundreds of fixtures) that a single `tests/fixtures/` directory in the main repo is fine, but the size ceiling in item 1 exists specifically to keep it that way — if the weird-document corpus ever grows into the thousands of files, revisit `self-hosted-corpus-storage-options.md`'s reasoning about splitting large corpora out of the primary Git history before it happens, not after.
4. **One case, one behavior, one test.** Each fixture is exercised by exactly one parametrized test case asserting the specific expected outcome (skip reason, converted output, or exception) — mirroring how the [CommonMark spec's `spec.json`](https://github.com/commonmark/commonmark-spec) `[official]` structures conformance tests as small, independent example/expected-output pairs rather than large composite documents. This keeps each fixture's purpose legible without needing to read the file's bytes to know why it exists.
5. **Never hand-edit an anomaly fixture to "look cleaner."** Corrupted-encoding and malformed-HTML fixtures should look exactly as corrupted as the generator/anonymization procedure produced them; sanitizing a fixture's _appearance_ is a common way real structure quietly leaks back in (see the anonymization procedure's step 3 on structural vs. content-preserving transforms).

## Anonymization/minimization procedure: real anomaly → shareable fixture

This procedure operationalizes `AGENTS.md` convention #6 ("never real library documents... paths, or personal content") and repo constraint C-002 for the one workflow where a real anomaly is the whole point of the fixture. It synthesizes documented minimal-reproducible-example practice, fuzzing testcase-minimization discipline, and structured-data de-identification principles — no single source states it end-to-end, so treat the step-by-step sequencing as a `[synthesis]`, while each individual technique it draws on is independently sourced below.

1. **Capture facts, not bytes.** When docmend hits an unexpected failure or a `verify` finding on a real file, record only: detected encoding + confidence score, byte offset(s) of the anomaly, the exact byte sequence(s) involved (a handful of bytes, not the file), file size class, newline style, and a structural description ("invalid 2-byte sequence embedded in an otherwise-ASCII paragraph, ~40 bytes before EOF"). Never paste the file itself into an issue, log, or fixture-authoring session — this is the direct analogue of [minimal-reproducible-example practice](https://en.wikipedia.org/wiki/Minimal_reproducible_example) `[community]` / [Stack Overflow's MRE guidance](https://stackoverflow.com/help/minimal-reproducible-example) `[official, platform docs]`: the goal is "just sufficient to demonstrate the problem," and here that bar is bytes and offsets, not prose.
2. **Classify the causal mechanism, not the content.** Identify _why_ the anomaly exists — e.g., a UTF-8 file whose bytes were mis-decoded as Windows-1252 and re-encoded (classic mojibake), a truncated multi-byte sequence at a chunk boundary, or a stray NUL byte from an old word processor. Use `ftfy`'s documented mojibake taxonomy `[official]` and general UTF-8 decode-chain mechanics `[blog, corroborating]` to name the mechanism precisely.
3. **Re-synthesize through the same mechanism — do not scrub the original.** Take unrelated Faker-generated or public-domain filler text and pass it through the _identical_ encode/decode/re-encode chain identified in step 2, so the fixture is a **structural reproduction**, not a **content-preserving mask** of the original. This distinction is not cosmetic: [ISO/IEC 20889](https://www.iso.org/obp/ui#iso:std:iso-iec:20889:ed-1:v1:en) `[official standard]` and [NIST SP 800-188](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) `[official standard]` both treat format/structure-preserving masking of real data as a weaker guarantee than true de-identification — masking that keeps the original's length, shape, or byte statistics can still carry re-identifying residue. Re-synthesis from unrelated filler through the same mechanism carries none of the original's structure by construction, which is a strictly stronger guarantee for a public repo than any masking of the real bytes could be.
4. **Verify the reproduction independently.** Confirm the synthetic fixture triggers the _same_ docmend code path as the original: same skip-reason code, same confidence bucket from `charset-normalizer`, same exception class/line if applicable. This mirrors fuzzing testcase-minimization discipline — a minimized or reconstructed input is only valid if it still reproduces the original failure, as emphasized in [The Fuzzing Book's `Reducer`/delta-debugging chapter](https://www.fuzzingbook.org/html/Reducer.html) `[official, academic]` and Google Project Zero's [`halfempty`](https://github.com/googleprojectzero/halfempty) minimization tool `[official]`, both of which treat "still reproduces the failure" as the acceptance test for any reduced/reconstructed case.
5. **Name and store by mechanism, not provenance.** File name and metadata carry the anomaly class and a case number only (`windows1252_reencode_mid_paragraph_01.txt`), matching the fixture-authoring convention above. Record the fixture's origin as "derived from a real-library anomaly; structurally reproduced, no original bytes retained" — never a filename, date, or path fragment from the real library (repo constraint C-002; `AGENTS.md` #6).
6. **Human/agent review gate, not automated scanning alone.** Because docmend has no automated secret/PII scanner in scope (§8.6, §13.6 checklist marks CI secret handling N/A for v1) and general secret scanners are documented to miss exactly this class of leak — [CybelAngel's 2026 analysis](https://cybelangel.com/blog/ai-assisted-development-public-repository-data-leaks/) `[blog, vendor]` notes GitHub-style secret scanning "does not detect sensitive business data in unstructured files, internal documents committed as test fixtures" — require an explicit reviewer checklist line before any anonymized fixture is committed: _"Confirm zero bytes of this fixture are traceable to the original file."_ This is a process control, not a tooling one, and should be added to conventions #6 and #1 (verification gate) rather than assumed to be covered by CI.

## Existing tools and prior art

| Tool / project | Role here | Maintenance signal | Fit |
| --- | --- | --- | --- |
| [Hypothesis](https://hypothesis.readthedocs.io/) | Property-based generation engine; `@example` for pinned regressions; Ghostwriter for transform-layer bootstrap | Actively maintained, widely used in the Python ecosystem | Strong — natural fit for a strict-typed pytest stack |
| [Faker](https://faker.readthedocs.io/) | Deterministically synthetic filler text/PII-shaped data | Actively maintained (releases through 2026) | Strong — purpose-built for "anonymize data... without handling sensitive information" |
| [chardet/test-data](https://github.com/chardet/test-data) | Reference model for a provenance-tracked, directory-encodes-ground-truth encoding fixture corpus | Active as of 2026 | Direct structural model for docmend's encoding fixture layout |
| [openpreserve/format-corpus](https://github.com/openpreserve/format-corpus) | Reference model for a small-file, openly-licensed, metadata-per-file example corpus | Maintained by the Open Preservation Foundation | Direct structural model for the weird-document corpus's size discipline |
| [Digital Corpora / govdocs1](https://digitalcorpora.org/corpora/file-corpora/files) | Precedent for a large (~1M file), openly available format corpus used across digital-forensics/preservation tooling | Long-running academic/forensics resource | Illustrates corpus-at-scale precedent; too large/heterogeneous to adopt directly, but validates the "separate large corpus from tool code" pattern |
| [The Fuzzing Book `Reducer`](https://www.fuzzingbook.org/html/Reducer.html) / [`halfempty`](https://github.com/googleprojectzero/halfempty) | Minimization/delta-debugging discipline for the anonymization procedure's verification step | Academic text / Google Project Zero, both actively referenced | Conceptual model, not a direct dependency |
| [pyfakefs](https://pytest-pyfakefs.readthedocs.io/) | In-memory filesystem for planning-layer unit tests at scale | Active, explicit Python 3.14 support tracked | Optional accelerant for non-writer-layer tests only |

## Security and compatibility

- No CVEs apply directly (this is a testing-methodology question, not a running service), but the relevant risk is **process, not code**: automated secret/PII scanners are documented to miss business-sensitive content embedded in test fixtures specifically, per [CybelAngel 2026](https://cybelangel.com/blog/ai-assisted-development-public-repository-data-leaks/) `[blog]` — reinforcing that the review-gate step in the anonymization procedure is load-bearing, not optional.
- [ISO/IEC 20889:2018](https://www.iso.org/obp/ui#iso:std:iso-iec:20889:ed-1:v1:en) and [NIST SP 800-188](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) `[official standards]` are written for structured/tabular datasets, not free-text documents — apply their _principle_ (structure-preserving masking is not equivalent to de-identification) rather than their specific techniques (k-anonymity, generalization, etc.), which do not map cleanly onto single text/HTML files.
- Version/date sensitivity: `chardet` underwent a disputed "AI-assisted" v7 rewrite in early 2026 with a licensing change (LGPL→MIT) noted in community sources; docmend already depends on `charset-normalizer` (§8.6), not `chardet`, so this is background context rather than a dependency risk — flagged here only because it surfaced during research and is worth knowing if `chardet` is ever reconsidered.

## Recent changes

- Python 3.14 shipped `pathlib.Path.copy`/`.move` and confirmed `tempfile`/`pathlib` stability relevant to fixture materialization; `pyfakefs` tracks 3.14-specific fixes (`os.readinto`, `pathlib.glob`) in its changelog as of 2026 `[official]` — current-version compatible for this stack.
- Hypothesis continues to expand pluggable backends (heuristic-random, solver-based, fuzzing-based) per its strategies documentation `[official]` — worth revisiting if docmend's corpus generation ever needs coverage-guided rather than purely random exploration of encoding edge cases.

## Open questions

| # | Question | Why unresolved |
| --- | --- | --- |
| 1 | What exact count/seed policy should the default (non-scale-marked) CI run use for the "boring 90%" corpus? | Depends on measured CI wall-clock budget, not yet profiled (ties to OQ-010). |
| 2 | Should the weird-document corpus's per-fixture metadata sidecar be JSON Schema-validated the same way frontmatter is (FR-016 precedent)? | Not yet decided; would need its own small schema and is a natural MS-2/MS-5 follow-up, not required to start. |
| 3 | Does the review-gate checklist item belong in `conventions.md` #6 or as a new numbered convention? | Editorial decision for the owner; functionally either works. |

## Reconciliation notes

Fold these findings back into:

- **`docs/specs/docmend.md` §17.2** (Test Strategy) — add the two-corpus distinction (scale vs. weird-document), the generated-at-test-time strategy for the 100k corpus, and the fixture-authoring convention's size ceiling.
- **`docs/specs/docmend.md` §19 MS-5** — the "weird-document corpus expanded from first real-library scan findings (read-only)" line should reference this report's anonymization procedure as _the_ mechanism for that expansion, not ad hoc practice.
- **`docs/open-questions.md` OQ-004** (artifact JSON Schemas) — Open Question 2 above (fixture metadata schema) is a natural sibling decision when OQ-004's schemas are pinned.
- **`AGENTS.md` / `docs/handoff/conventions.md` #6** — the review-gate checklist line ("confirm zero bytes are traceable to the original file") strengthens the existing sensitive-data convention with a concrete, actionable check.
- **Confirmed drift, out of this report's scope but worth flagging while it was found:** `docs/specs/docmend.md` §21's Open Questions table stops at OQ-011, while `docs/open-questions.md` defines OQ-012, OQ-013, and OQ-014 (all three reference spec sections — §8.5/§13.2/§18.2, §9, and §7.1/§7.3/§18.2 respectively — that do not currently link back to them). No other ID-range gaps were found in a full cross-check of every `OQ-###` reference in both files; this appears to be a single contiguous migration gap (all three added after the spec's last `§21` sync), not a broader pattern. Recommend a follow-up pass to add OQ-012–014 rows to §21 rather than folding it into this report.

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://hypothesis.readthedocs.io/en/latest/data.html> | Hypothesis — Strategies Reference | 2026 | official |
| <https://hypothesis.readthedocs.io/en/latest/tutorial/replaying-failures.html> | Hypothesis — Replaying failed tests (`@example`) | 2026 | official |
| <https://hypothesis.readthedocs.io/en/latest/ghostwriter.html> | Hypothesis — Ghostwriter / Integrations Reference | 2026 | official |
| <https://hypothesis.readthedocs.io/en/latest/extensions.html> | Hypothesis — Third-party extensions (hypothesmith etc.) | 2026 | official |
| <https://github.com/Zac-HD/hypothesmith> | hypothesmith — Python program generation strategies | 2026 | community |
| <https://docs.pytest.org/en/stable/how-to/tmp_path.html> | pytest — Temporary directories and files (`tmp_path`, `tmp_path_factory`) | 2026 | official |
| <https://pytest-pyfakefs.readthedocs.io/en/latest/intro.html> | pyfakefs — Introduction | 2026 | official |
| <https://github.com/pytest-dev/pyfakefs/blob/main/CHANGES.md> | pyfakefs — Changelog (Python 3.14 fixes) | 2026 | official |
| <https://digitalcorpora.org/corpora/file-corpora/files> | Digital Corpora — Govdocs1 | 2026 | community |
| <https://github.com/openpreserve/format-corpus> | Open Preservation Foundation — format-corpus | 2026 | official |
| <https://openpreservation.org/blogs/identification-tools-evaluation> | OPF — Identification tools, an evaluation | n/a | official |
| <https://ijdc.net/index.php/ijdc/article/download/211/270/887> | Towards the Development of a Test Corpus of Digital Objects | n/a | official (peer-reviewed) |
| <https://github.com/commonmark/commonmark-spec> | CommonMark spec (spec.json test format) | 2026 | official |
| <https://spec.commonmark.org/current> | CommonMark Spec 0.31.2 | 2026 | official |
| <https://github.com/chardet/test-data> | chardet — test-data repository | 2026 | official |
| <https://github.com/chardet/test-data/blob/main/CLAUDE.md> | chardet/test-data — repository conventions | 2026 | official |
| <https://github.com/chardet/chardet> | chardet — Python character encoding detector | 2026 | official |
| <https://charset-normalizer.readthedocs.io/> | charset_normalizer documentation | 2026 | official |
| <https://ftfy.readthedocs.io/en/v6.0/avoid.html> | ftfy — How can I avoid producing mojibake? | 2026 | official |
| <https://brokkr.net/2022/04/20/fun-with-character-encoding-errors-part-i> | UTF-8 mojibake — a practical guide | 2022 | blog |
| <https://faker.readthedocs.io/> | Faker documentation | 2026 | official |
| <https://github.com/joke2k/faker> | Faker — GitHub repository | 2026 | official |
| <https://www.fuzzingbook.org/html/Reducer.html> | The Fuzzing Book — Reducing Failure-Inducing Inputs | n/a | official (academic) |
| <https://github.com/googleprojectzero/halfempty> | halfempty — parallel test case minimization tool | 2026 | official |
| <https://google.github.io/oss-fuzz/advanced-topics/ideal-integration> | OSS-Fuzz — Ideal integration (seed corpus philosophy) | 2026 | official |
| <https://en.wikipedia.org/wiki/Minimal_reproducible_example> | Minimal reproducible example | 2026 | community |
| <https://stackoverflow.com/help/minimal-reproducible-example> | Stack Overflow — How to create a Minimal, Reproducible Example | n/a | official (platform docs) |
| <https://www.iso.org/obp/ui#iso:std:iso-iec:20889:ed-1:v1:en> | ISO/IEC 20889:2018 — Privacy enhancing data de-identification techniques | 2018 | official standard |
| <https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf> | NIST SP 800-188 — De-Identifying Government Datasets | 2023 | official standard |
| <https://nvlpubs.nist.gov/nistpubs/ir/2015/nist.ir.8053.pdf> | NIST IR 8053 — De-Identification of Personal Information | 2015 | official standard |
| <https://cybelangel.com/blog/ai-assisted-development-public-repository-data-leaks/> | AI Coding Tools and Public Repository Data Leaks: 2026 | 2026 | blog (vendor) |
| <https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github> | GitHub — Large files guidance | 2026 | official |
| <https://docs.python.org/3/library/tempfile.html> | Python `tempfile` documentation | 2026 | official |
