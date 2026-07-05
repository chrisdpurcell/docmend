# Further Research Queue

This document tracks deep-research prompts for `docmend`. Use it when a spec decision needs current external evidence, tool comparison, legal/operational context, or a source-backed design recommendation before implementation.

## Status

**Last updated:** 2026-07-05

The 2026-07-05 gap analysis produced 22 evidence-backed research reports (see the table below) and queued **4 ChatGPT Deep-Research prompts** for the residual questions that need heavier empirical or owner-policy synthesis. Those four returned reports have been converted into Markdown under `docs/research/` and **reconciled** (2026-07-05) into the decision backlog: prompts 1–3 folded into existing open questions (OQ-015, OQ-016, OQ-008/OQ-010) as `Research update` agent notes, and prompt 4 opened a new question, **OQ-023** (deferred-review-artifact content-exposure policy). **Owner follow-up (2026-07-05):** the owner subsequently ruled on the first ten OQs, resolving OQ-008 → RQ-007 (preservation-agnostic) and OQ-010 → RQ-009 (numeric targets deferred), so those two prompt targets now live in [`resolved-questions.md`](resolved-questions.md) and the relevant spec prose (FR-005/FR-006, §18.6, NFR-001) was updated to match. OQ-015, OQ-016, and OQ-023 remain owner-undecided.

### docmend research reports

| Report | Topic | Feeds |
| --- | --- | --- |
| [`managing-pandoc-markdown-and-strict-yaml-frontmatter.md`](research/managing-pandoc-markdown-and-strict-yaml-frontmatter.md) | Pandoc Markdown, CommonMark body constraints, strict YAML frontmatter, schema validation | spec §9 / C-006 / FR-016 / DR-005; OQ-013 |
| [`self-hosted-corpus-storage-options.md`](research/self-hosted-corpus-storage-options.md) | Storage options for a large private document corpus | spec §18.6; OQ-008 |
| [`python-library-research.md`](research/python-library-research.md) | Whole-stack Python dependency posture (runtime + dev/test) — broad companion to the targeted per-library reports | OQ-015/017/018/019, OQ-021, OQ-022; §8.6 dependency policy |
| [`encoding-detection-benchmark.md`](research/encoding-detection-benchmark.md) | Encoding detection at corpus scale: detector choice, confidence semantics, threshold | OQ-001 (GAP-42, GAP-43, GAP-44) |
| [`charset-detection-floors-for-legacy-text-ingestion.md`](research/charset-detection-floors-for-legacy-text-ingestion.md) | Empirical non-ASCII-byte-count floor for legacy encoding detection | OQ-001 / OQ-015; spec FR-007, §18.2 |
| [`python-314-concurrency-model.md`](research/python-314-concurrency-model.md) | Concurrency model for a CPU-bound file pipeline on Python 3.14 | OQ-010 (GAP-22, GAP-54) |
| [`docmend-and-the-free-threaded-cpython-switch-decision.md`](research/docmend-and-the-free-threaded-cpython-switch-decision.md) | CPython free-threading re-open criteria and dependency readiness | OQ-010 / OQ-016; spec NFR-001, §14 |
| [`python-314-wheel-readiness.md`](research/python-314-wheel-readiness.md) | Python 3.14 wheel readiness for the approved dependency set | gap-analysis.md (GAP-60) |
| [`append-safe-manifest-format.md`](research/append-safe-manifest-format.md) | Crash-safe, append-safe on-disk manifest representation | OQ-004 (GAP-24, GAP-30) |
| [`atomic-write-filesystem-semantics.md`](research/atomic-write-filesystem-semantics.md) | Atomic-replace and directory-fsync guarantees across filesystems | gap-analysis.md (GAP-41) |
| [`path-containment-toctou.md`](research/path-containment-toctou.md) | Path-containment algorithm and TOCTOU symlink-race mitigation | OQ-004 (GAP-40) |
| [`stable-document-id-scheme.md`](research/stable-document-id-scheme.md) | Stable document ID scheme surviving renames and full rewrites | OQ-002 (GAP-26) |
| [`json-schema-versioning-migration.md`](research/json-schema-versioning-migration.md) | JSON Schema versioning and migration policy | OQ-004 (GAP-29) |
| [`json-schema-validator-library.md`](research/json-schema-validator-library.md) | JSON Schema validator library selection at scale | OQ-004 (GAP-58) |
| [`unicode-normalization-policy.md`](research/unicode-normalization-policy.md) | Unicode normalization-form policy for content and filenames | gap-analysis.md (GAP-45) |
| [`structured-logging-library.md`](research/structured-logging-library.md) | Structured logging library and format for a long-running batch CLI | gap-analysis.md (GAP-19) |
| [`batch-throughput-and-capacity.md`](research/batch-throughput-and-capacity.md) | Throughput, memory, disk-overhead, and progress-reporting budget for a 100k-file pass | OQ-010 (GAP-20, GAP-38, GAP-54) |
| [`docmend-backup-medium-durability-and-throughput-research.md`](research/docmend-backup-medium-durability-and-throughput-research.md) | Backup destination throughput, durability semantics, and staging recommendation | OQ-008 / OQ-010; spec §14, §18.6 |
| [`synthetic-corpus-generation.md`](research/synthetic-corpus-generation.md) | Synthetic corpus generation and public-safe anonymization of real anomalies | gap-analysis.md (GAP-49) |
| [`property-based-testing-hypothesis.md`](research/property-based-testing-hypothesis.md) | Property-based testing library for transform purity and edge cases | gap-analysis.md (GAP-50) |
| [`architecture-and-traceability-enforcement.md`](research/architecture-and-traceability-enforcement.md) | Mechanical enforcement of architecture invariants and requirement traceability | OQ-004 (GAP-52, GAP-53) |
| [`license-compliance-tooling.md`](research/license-compliance-tooling.md) | Dependency license-scanning tooling and policy for a uv/PEP 621 project | gap-analysis.md (GAP-59) |
| [`batch-curation-review-workflow.md`](research/batch-curation-review-workflow.md) | Report-driven review workflow for a headless batch curation tool | gap-analysis.md (GAP-61) |
| [`docmend-deferred-review-artifacts-for-confidential-corpora.md`](research/docmend-deferred-review-artifacts-for-confidential-corpora.md) | Content-exposure policy for headless deferred review artifacts | WH-002 / WH-005, NG-001; spec §11, §13.4/§13.5 |
| [`per-file-watchdog-timeout.md`](research/per-file-watchdog-timeout.md) | Per-file watchdog/timeout for pathological inputs in a batch pipeline | gap-analysis.md (GAP-63) |
| [`combinatorial-safety-gate-testing.md`](research/combinatorial-safety-gate-testing.md) | Combinatorial testing strategy for the multi-check safety gate | OQ-005 (GAP-39) |
| [`restore-from-manifest-design.md`](research/restore-from-manifest-design.md) | Restore-from-manifest tooling and drill design | OQ-005 (GAP-33) |
| [`safe-yaml-loading.md`](research/safe-yaml-loading.md) | Safe YAML loading and hardening for parsing legacy frontmatter | gap-analysis.md (GAP-65) |
| [`backup-integrity-verification.md`](research/backup-integrity-verification.md) | Backup integrity verification and preservation-strategy proof | OQ-005 (GAP-34, GAP-35) |

See [`research/index.md`](research/index.md) for the same list as a generated index.

## Queue

ChatGPT Deep-Research candidates. Each was flagged by the research pass as needing empirical validation or cross-domain owner-policy synthesis beyond a single-pass web lookup. The filled prompts follow in [Deep-research prompts](#deep-research-prompts).

| # | Topic | Status | Related question / spec section | Report |
| --: | --- | --- | --- | --- |
| 1 | Empirical non-ASCII-byte-count skip-floor for encoding detection on a legacy .txt/.html corpus | Reconciled → OQ-015 | OQ-001 (encoding v1 boundary), OQ-015 (encoding detector/thresholds); docs/research/encoding-detection-benchmark.md; spec FR-007, §18.2 | [`charset-detection-floors-for-legacy-text-ingestion.md`](research/charset-detection-floors-for-legacy-text-ingestion.md) |
| 2 | CPython free-threading (Phase III / default-build) timeline and re-open criteria for the concurrency choice | Reconciled → OQ-016 | OQ-010 (performance), OQ-016 (concurrency primitive); docs/research/python-314-concurrency-model.md; spec NFR-001, §14 | [`docmend-and-the-free-threaded-cpython-switch-decision.md`](research/docmend-and-the-free-threaded-cpython-switch-decision.md) |
| 3 | Real-hardware throughput and capacity validation on the actual OQ-008 backup medium | Reconciled → OQ-008 | OQ-008 (preservation posture), OQ-010 (performance targets), OQ-005 (preservation gate); docs/research/batch-throughput-and-capacity.md; spec NFR-001, §14, §18.6 | [`docmend-backup-medium-durability-and-throughput-research.md`](research/docmend-backup-medium-durability-and-throughput-research.md) |
| 4 | Document-content exposure policy for a headless batch tool's semantic-review artifacts | Reconciled → OQ-023 | OQ-023 (new); WH-002/WH-005, NG-001, §11, §13.4/§13.5; docs/research/batch-curation-review-workflow.md | [`docmend-deferred-review-artifacts-for-confidential-corpora.md`](research/docmend-deferred-review-artifacts-for-confidential-corpora.md) |

## Deep-research prompts

Paste a prompt into ChatGPT Deep-Research, then record the returned report under `docs/research/` and its reconciliation back into the spec / open questions.

### 1. Empirical non-ASCII-byte-count skip-floor for encoding detection on a legacy .txt/.html corpus

> **Status:** Reconciled → OQ-015 (2026-07-05)

**Related decision or spec section:** OQ-001 (encoding v1 boundary), OQ-015 (encoding detector/thresholds); docs/research/encoding-detection-benchmark.md; spec FR-007, §18.2

**Gap it fills:** The detector (charset-normalizer), confidence formula (1.0 - chaos), and 0.80 threshold are settled, but the exact non-ASCII-byte-count floor for the second, independent skip gate is not — the documented short-text tie failure (chaos=0.0 on a wrong answer) means a raw confidence threshold cannot bound false-accepts, and the right floor is encoding-family dependent and must reflect the real corpus's short-file distribution.

**Why deep research (qdev-level was insufficient):** qdev settled the detector, confidence formula, and 0.80 threshold from primary sources, but explicitly scoped the exact non-ASCII floor as needing empirical validation against a real short-file distribution — a synthesis across multiple detector-accuracy studies plus fixture design, deeper than a single-pass web lookup, though the final number still needs a project-internal run against docmend's own weird-document corpus.

```text
I'm building docmend, a Python CLI tool that normalizes, repairs, and converts a large legacy library of text and HTML documents into clean Pandoc-compatible Markdown. The repository is public, so examples and fixtures must be synthetic or public-domain only.

Research question:

charset-normalizer 3.x reports a chaos score (I use confidence = 1.0 - chaos) but is documented to return chaos=0.0 (maximum confidence) for a WRONG encoding on very short, mostly-ASCII text with a handful of non-ASCII bytes (e.g. a ~38-byte string misdetected as Big5). I want a second, independent skip gate based on the count of non-ASCII bytes in a file, below which I refuse to trust ANY detected legacy encoding regardless of confidence, and instead skip-and-report. Determine, with evidence: (1) the minimum non-ASCII byte counts at which single-byte (windows-1252/ISO-8859 family) versus multi-byte legacy CJK encodings (Shift_JIS, Big5, GB18030, EUC-*) become reliably distinguishable by statistical detectors; (2) how those thresholds interact with the presence/absence of a BOM and with UTF-8 validity as a pre-check; (3) whether the floor should be an absolute byte count, a ratio of non-ASCII to total bytes, or both; (4) recommended default values with a stated false-accept/false-skip tradeoff for a corpus dominated by short English-language .txt files with occasional Latin-1 or CJK content; and (5) a reproducible test-fixture design (synthetic/public-domain only) that would let me validate the chosen floor.

Deliver:

- A per-encoding-family table of minimum reliable non-ASCII byte counts with citations to detector-accuracy studies (e.g. chardetng/Sivonen, ICU, uchardet evaluations)
- A recommended default floor (absolute and/or ratio) with the tradeoff stated
- A synthetic fixture-generation recipe reproducing both the false-accept and false-skip boundary cases
- Version/date sensitivity notes for charset-normalizer 3.x and Python 3.14
```

**Deliverables:** Per-encoding-family reliability-threshold table with citations; a recommended default non-ASCII floor (absolute and ratio) with the false-accept/false-skip tradeoff stated; a synthetic/public-domain fixture recipe for validation; charset-normalizer/3.14 version sensitivity notes.

**Report:** [`research/charset-detection-floors-for-legacy-text-ingestion.md`](research/charset-detection-floors-for-legacy-text-ingestion.md)

**Reconciliation notes:** Folded into **OQ-015** as a `Research update (2026-07-05, charset-floor deep-research)` agent note. The report resolves the one item OQ-015 left to empirical validation — the exact non-ASCII floor for the second, independent skip gate — by narrowing OQ-015's provisional "8–20 range" to a concrete **20-byte universal hard floor** (from Sivonen/chardetng convergence: windows-1252/1251 settle ~20 non-ASCII bytes, legacy CJK ~10), with an **optional family-aware override** (Western single-byte ≥20, CJK multi-byte ≥12, Big5 ≥10). It also pins the **gate ordering** (BOM sniff → strict full-file UTF-8 validity → ASCII-only bypass → legacy floor only for non-BOM/non-UTF-8 files), makes the primary gate **count-based** with an optional ratio-hardening rule (`total_bytes ≥ 4096 && non_ascii_ratio < 0.005 → mark suspect`), and supplies a synthetic/public-domain fixture recipe that feeds §17.2. Version note captured in OQ-015: charset-normalizer 3.4.2 improved CJK reliability and 3.4.3 began damping confidence on small non-Unicode samples, so any floor work must run on ≥3.4.2 and use explicit binary-read + explicit-decode (not ambient `open()` defaults, given the 3.15 UTF-8-default transition). No spec text changed — OQ-015 remains owner-undecided; the numbers still need a final project-internal run against docmend's own weird-document corpus before FR-007/§18.2 are edited.

### 2. CPython free-threading (Phase III / default-build) timeline and re-open criteria for the concurrency choice

> **Status:** Reconciled → OQ-016 (2026-07-05)

**Related decision or spec section:** OQ-010 (performance), OQ-016 (concurrency primitive); docs/research/python-314-concurrency-model.md; spec NFR-001, §14

**Gap it fills:** The v1 primitive (ProcessPoolExecutor + forkserver) is settled, but the report explicitly parks free-threading re-evaluation on a future CPython Phase III (default free-threaded build) schedule. docmend needs a concrete, evidence-backed set of re-open triggers and a readiness snapshot of its dependency graph so a future maintainer knows exactly when and why to reconsider process-based parallelism.

**Why deep research (qdev-level was insufficient):** qdev answered the v1 primitive-selection question conclusively from PEPs and wheel listings, but the re-open decision depends on a fast-moving, multi-source CPython roadmap plus an evolving dependency-compatibility landscape that benefits from periodic heavier synthesis rather than a single in-the-loop lookup; the report itself flagged this as the one item warranting future re-analysis.

```text
I'm building docmend, a Python CLI tool that normalizes, repairs, and converts a large legacy library of text and HTML documents into clean Pandoc-compatible Markdown. The repository is public, so examples and fixtures must be synthetic or public-domain only.

Research question:

docmend is a CPU-bound file pipeline (charset-normalizer encoding detection + SHA-256 hashing + atomic writes) currently targeting Python 3.14 with concurrent.futures.ProcessPoolExecutor (forkserver). I want to know when free-threaded CPython would make in-process thread parallelism the better choice and retire the multiprocessing overhead. Determine, with citations to CPython PEPs, release notes, and the steering-council/core-dev record: (1) the current status and best-estimate timeline for PEP 703/779 Phase II (supported, non-default) to Phase III (default build) and any Phase IV (removal of the GIL build); (2) concrete, testable criteria docmend should adopt to trigger a re-evaluation (e.g. free-threaded build becomes the default in a stable release, or ships in the major distros/uv-managed interpreters docmend targets); (3) the free-threading readiness of docmend's dependency graph (charset-normalizer, rpds-py/jsonschema, rich, typer/click, pathspec) with per-package wheel/ABI evidence; (4) known correctness or performance caveats of free-threaded builds for hashlib and pure-Python hot loops as of the latest data; and (5) what benchmark docmend should run to make the switch decision.

Deliver:

- A PEP 703/779 phase-timeline summary with the latest primary-source status
- A concrete re-open trigger checklist for docmend
- A per-dependency free-threading readiness table with wheel/ABI citations
- A recommended micro-benchmark design to decide process vs free-threaded at switch time
- Version/date sensitivity notes
```

**Deliverables:** A free-threading phase-timeline summary with primary-source status; a concrete re-open trigger checklist; a per-dependency free-threading readiness table; a switch-decision benchmark design; version/date sensitivity notes.

**Report:** [`research/docmend-and-the-free-threaded-cpython-switch-decision.md`](research/docmend-and-the-free-threaded-cpython-switch-decision.md)

**Reconciliation notes:** Folded into **OQ-016** as a `Research update (2026-07-05, free-threading deep-research)` agent note. The report **confirms and does not disturb** OQ-016's decision — keep `ProcessPoolExecutor` + `forkserver`; do **not** retire multiprocessing — because free-threaded CPython is at PEP 779 **Phase II** (supported, non-default) with **no committed Phase III (default-build) date** (3.15 is still finishing the `abi3t` packaging transition; earliest plausible flip is 3.16–3.17+, an inference not a CPython commitment). Its net-new contribution is a durable **re-open trigger checklist** (default-build flips or SC begins Phase III; supported interpreter channels — `uv`, macOS installers — treat free-threading as first-class; full app import graph keeps `sys._is_gil_enabled()` False; per-dep `cp3xyt`/`abi3t` wheels present; a docmend switch-benchmark shows a thread pool beats the process-pool baseline with zero correctness drift) plus a **dependency-readiness snapshot** (`rpds-py` and `charset-normalizer` already ship `cp314t` wheels; `jsonschema`/`rich`/`typer`/`click`/`pathspec` are pure-Python `py3-none-any`, i.e. no ABI blocker ≠ proven thread-safe) and a caveat that `hashlib` already releases the GIL above 2047-byte buffers, so the free-threading upside is concentrated in the pure-Python detection/normalization hot loops, not hashing. Recorded as a **release-gated future re-check**, not a v1 change; NFR-001/§14 unchanged.

### 3. Real-hardware throughput and capacity validation on the actual OQ-008 backup medium

> **Status:** Reconciled → OQ-008 (2026-07-05)

**Related decision or spec section:** OQ-008 (preservation posture), OQ-010 (performance targets), OQ-005 (preservation gate); docs/research/batch-throughput-and-capacity.md; spec NFR-001, §14, §18.6

**Gap it fills:** The throughput/memory/disk-preflight budget was validated on a local SSD/btrfs spike, but the report explicitly leaves open real throughput on the owner's chosen OQ-008 backup destination (network share, external HDD, Borg/restic repo, or object storage), where the fsync-bound write/backup stage that dominates cost could behave very differently and invalidate the 8-hour wall-clock bound.

**Why deep research (qdev-level was insufficient):** qdev produced a first-party local-SSD profiling spike and corroborated formulas, but explicitly scoped real backup-medium behavior as a hardware-specific measurement pending the OQ-008 decision; synthesizing durability-semantics-plus-throughput across NFS/SMB/HDD/Borg/S3 is a multi-domain sweep beyond an in-the-loop lookup, and the answer directly gates whether the 8-hour NFR-001 bound holds in production.

```text
I'm building docmend, a Python CLI tool that normalizes, repairs, and converts a large legacy library of text and HTML documents into clean Pandoc-compatible Markdown. The repository is public, so examples and fixtures must be synthetic or public-domain only.

Research question:

docmend backs up each original file (shutil.copy2 + fsync) before an atomic in-place rewrite, and my profiling shows the fsync-bound backup+write stage dominates per-file cost (~14 ms/file interleaved, including a ~7.9 ms parent-directory fsync) on a local SSD. Before the first real 100k-file run I need to understand how this stage behaves on realistic backup destinations. Determine, with evidence: (1) how per-small-file fsync/copy throughput and the atomic-replace parent-dir fsync degrade on NFS, SMB/CIFS, an external USB HDD (spinning), a Borg/restic deduplicating repository, and S3-compatible object storage; (2) which of these can even honor the durability semantics docmend relies on (same-directory os.replace atomicity, directory fsync) and which silently weaken them; (3) recommended per-medium throughput expectations and whether a separate 'fast local backup then async replicate' staging design is warranted; (4) the right disk-space and inode preflight formulas per medium; and (5) how to instrument a real run to detect a medium that is an order of magnitude slower than the local-SSD baseline.

Deliver:

- A per-backup-medium throughput and durability-semantics comparison table with citations
- A recommendation on staging (local-fast-backup + replicate) vs direct-to-medium
- Per-medium disk-space/inode preflight formulas
- An instrumentation/heartbeat design to catch a pathologically slow medium mid-run
- Version/date and filesystem/kernel sensitivity notes
```

**Deliverables:** A per-backup-medium throughput and durability comparison table with citations; a staging-vs-direct recommendation; per-medium disk-space/inode preflight formulas; a mid-run slow-medium instrumentation design; filesystem/kernel version sensitivity notes.

**Report:** [`research/docmend-backup-medium-durability-and-throughput-research.md`](research/docmend-backup-medium-durability-and-throughput-research.md)

**Reconciliation notes:** Folded into **OQ-008** as a `Research update (2026-07-05, backup-medium deep-research)` agent note, with a cross-reference from **OQ-010** and a gate note for **OQ-005**. Three findings reshape the OQ-008 posture menu: (1) the recommended default architecture is **local-fast-backup + asynchronous replication**, not direct-to-medium — keep the synchronous per-file safety barrier (copy+`fsync` → temp-write+`fsync` → `os.replace` → parent-dir `fsync`) on a fast local filesystem and replicate to slower/weaker media afterward; (2) **Borg, restic, and S3-compatible object storage are not semantic substitutes** for docmend's inline copy-then-atomically-rewrite contract (their transactional/immutable-object formats provide no POSIX rename or directory-`fsync` primitive) — they are valid replication *targets* but must not be the inline barrier, which trims OQ-008's option set; only local filesystems and carefully-configured `sync`-export NFS / `cache=strict`+`strict sync` SMB can honor the durability contract. (3) A key structural insight: the measured parent-dir `fsync` cost is attached to the **source** filesystem, so if the library stays on local SSD and only the backup destination moves to a slow medium, wall-clock impact is bounded to the backup-copy term. The report also supplies per-medium disk-space/inode **preflight formulas** (feeding the RQ-005 per-mount preflight gate and §18.6), a **mid-run slow-medium abort rule** (>10× the ~14 ms/file baseline ≈ 140 ms/file → fall back to local staging), and a heartbeat + sentinel-microprobe instrumentation design (extends OQ-017's log schema). **Owner ruled 2026-07-05:** OQ-008 resolved → **RQ-007** (docmend is preservation-agnostic; Borg/restic/S3 are async replication targets, not inline barriers), and OQ-010 resolved → **RQ-009** (numeric targets deferred). §18.6 and FR-005/FR-006 were updated to match; the chosen concrete medium is now the user's choice, still requiring a restore drill before first real apply.

### 4. Document-content exposure policy for a headless batch tool's semantic-review artifacts

> **Status:** Reconciled → OQ-023 (2026-07-05)

**Related decision or spec section:** OQ-023 (new); WH-002/WH-005, NG-001, §11, §13.4/§13.5; docs/research/batch-curation-review-workflow.md

**Gap it fills:** The report found a genuine, previously undocumented conflict: docmend's artifacts are deliberately hash-and-path-only (§13.4/§13.5), but any WH-002 semantic-correction review artifact cannot be reviewed without showing actual document text, and NG-001 forbids a reading/browsing interface. This needs a defensible, precedent-backed policy on how much document content a headless curation tool may place in a decision artifact before it crosses into a forbidden UI, and how to keep confidential content (§13.4) safe in a public-repo project's design.

**Why deep research (qdev-level was insufficient):** qdev surfaced the tooling precedents and the automation-bias literature, but flagged the core question as an owner design/policy decision — how much document-body exposure is acceptable in a review artifact — that sits at the intersection of an architectural non-goal (NG-001), a confidentiality threat model (§13.4), and de-identification standards; resolving it needs a heavier cross-domain synthesis and an explicit owner-facing options analysis rather than a factual lookup.

```text
I'm building docmend, a Python CLI tool that normalizes, repairs, and converts a large legacy library of text and HTML documents into clean Pandoc-compatible Markdown. The repository is public, so examples and fixtures must be synthetic or public-domain only. docmend is strictly headless: it emits machine-readable JSON/NDJSON artifacts and has an explicit non-goal against any reading/browsing/search UI. Its artifacts today are deliberately hash-and-path-only and never contain document body text, because the content is confidential (personal letters, journals, financial records).

Research question:

I want to add an optional, deferred human-review step for two capabilities: (a) semantic text corrections (spelling/grammar), which unavoidably require showing the changed text to review, and (b) fuzzy duplicate clusters, which need only paths/sizes/similarity scores. Determine, with precedent from real headless/offline tools (patch/git apply .rej hunks, fclones/rdfind report-then-act files, the dedupe library's CSV verdict columns, Terraform plan, code-review diff formats) and from data-minimization/de-identification guidance (ISO/IEC 20889, NIST SP 800-188): (1) what content-exposure boundary keeps a decision-file design 'headless' rather than a de-facto reading UI; (2) design options for a semantic-correction review artifact that expose the minimum necessary text (diff hunks with bounded context, redaction, opt-in inline vs sidecar) and their tradeoffs; (3) how to keep such artifacts safe in a project whose source repo is public even though the artifacts themselves are generated on private data; (4) a recommended default posture (pessimistic-skip / exception-only review vs review-everything) given documented automation-bias/rubber-stamping failure modes at scale; and (5) whether the confidential-content concern justifies keeping WH-002 review entirely out of docmend and delegating to external diff tools.

Deliver:

- A survey table of headless report-then-act review patterns with their content-exposure level
- A recommended content-exposure boundary and its rationale against NG-001
- Concrete artifact-shape options for WH-002 (semantic) and WH-005 (dedup) with tradeoffs
- A default review-posture recommendation citing automation-bias evidence
- Data-minimization guidance mapped to the public-repo/confidential-content constraint
```

**Deliverables:** A survey of headless review patterns by content-exposure level; a recommended NG-001-compatible content boundary with rationale; artifact-shape options for semantic vs dedup review; a default review-posture recommendation with automation-bias citations; data-minimization guidance for the public-repo/confidential-content split.

**Report:** [`research/docmend-deferred-review-artifacts-for-confidential-corpora.md`](research/docmend-deferred-review-artifacts-for-confidential-corpora.md)

**Reconciliation notes:** Opened **OQ-023 — deferred-review-artifact content-exposure policy (WH-002/WH-005)** to carry this decision (the report surfaced a real, previously-undocumented conflict between NG-001's no-reading-UI boundary and the fact that a WH-002 semantic-correction review artifact cannot be judged without showing changed text — no existing OQ owned it). OQ-023 records the report's recommended default: a review artifact stays "headless" if it is **issue-bounded, decision-sufficient, non-navigable, and opt-in for text**; **WH-005** duplicate review defaults **metadata-only** (paths/aliases/sizes/hashes/similarity/cluster IDs — no body text); **WH-002** semantic review defaults to a **durable metadata ledger with no body text**, with any text confined to an **opt-in, local-only ephemeral sidecar or an external-diff handoff** (bounded hunks, tight char/line caps, path aliases not raw paths); default posture is **pessimistic-skip / exception-only** with no pre-filled "accept" and no bulk-approve (automation-bias evidence: Goddard et al., Cummings, Green); and the confidentiality/public-repo split means text-bearing artifacts are **private local artifacts, never repo or CI outputs and never version-controlled**. The load-bearing answer: docmend may *identify, package, and record* review decisions, but **text rendering stays outside docmend** — the cleanest NG-001 alignment. Because WH-002/WH-005 are deferred (§2.3), OQ-023 is non-blocking and future-facing; NG-001, §11, and §13.4/§13.5 are left unchanged until the owner rules and the WH work is scheduled.

## Candidate Topics

Backlog placeholders. Promote one into the [Queue](#queue) when the owner or implementation work needs research-backed detail. Several original candidates are now covered by the 2026-07-05 research pass and are marked accordingly.

| Candidate | Status | Covered by |
| --- | --- | --- |
| Artifact JSON Schema patterns | Covered | `research/json-schema-validator-library.md`, `research/json-schema-versioning-migration.md`, `research/append-safe-manifest-format.md` (OQ-004) |
| Apply preservation backends | Covered | `research/backup-integrity-verification.md`, `research/restore-from-manifest-design.md` (OQ-005); `research/self-hosted-corpus-storage-options.md` (OQ-008) |
| Encoding detection at corpus scale | Covered | `research/encoding-detection-benchmark.md` (OQ-015); residual empirical floor resolved by prompt 1 → `research/charset-detection-floors-for-legacy-text-ingestion.md` |
| HTML-to-Markdown conversion boundaries | Open | Deferred WH-004 survey; not yet researched |

## Prompt Template

Copy this section for each new queued prompt.

### N. Topic title

> **Status:** Not started

**Related decision or spec section:** _Link to OQ/RQ/spec section._

**Gap it fills:** _State the missing decision or evidence in one paragraph._

```text
I'm building docmend, a Python CLI tool that normalizes, repairs, and converts a
large legacy library of text and HTML documents into clean Pandoc-compatible
Markdown. The repository is public, so examples and fixtures must be synthetic
or public-domain only.

Research question:

[Write the exact research prompt here.]

Deliver:

- [Expected table/report shape]
- [Required citations or source types]
- [Any version/date sensitivity]
```

**Report:** _TBD_

**Reconciliation notes:** _Where the findings were folded back._
