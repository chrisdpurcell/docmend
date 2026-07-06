# docmend Gap Analysis

**Generated:** 2026-07-05 · **Method:** 12-lens multi-agent workflow (Sonnet reviewers + Opus consolidation/synthesis), 36 agents, 22 evidence-backed research reports under [`research/`](research/).

This is the comprehensive gap register for `docmend`. It complements the two decision docs, which hold the actionable subset: genuine undecided decisions live as open questions in [`open-questions.md`](open-questions.md) (OQ-015..020 were added from this analysis); research prompts live in [`deep-research-queue.md`](deep-research-queue.md). This file is the full ranked landscape with downstream-impact analysis; it is a point-in-time analysis, not a living decision record.

## How to read this

**Disposition** — where a gap is routed:

- `new-open-question` — a genuine undecided decision; became OQ-015..020 in `open-questions.md`.
- `update-existing-oq` — research that strengthens an existing OQ; folded in as a research-update supplement.
- `spec-change` — a concrete edit the spec of record needs (author via the `project-standards spec` CLI, not by hand).
- `doc-fix` — documentation drift/consistency; see the [doc-fix checklist](#documentation-and-drift-fix-checklist).
- `research-only` — needs external evidence but is not itself an owner decision; a report was produced.

**Priority** — High / Medium / Low by project impact × urgency relative to the MS-0..MS-5 milestone order.

## Executive summary

The 71-gap landscape splits into five clusters, and the single highest-leverage action is fixing a systemic documentation-drift rot pattern before it misleads any implementation work.

(1) Documentation drift (GAP-01/02/03/04/66/67/70, plus 68/69/71) — the confirmed anchor is that spec §21's OQ table stops at OQ-011 while open-questions.md defines OQ-012/013/014, one of them (OQ-012, in-place vs separate output root) a P0 write-path blocker. This omission propagated into state.md/architecture.md/STATUS.md/TODO.md ('three blocking OQs' should be four), and the same rot class shows up as undefined P0/P1/P2 taxonomy, stale post-migration docs/handoff.md pointers, a broken ADR-0001 link, and an architecture diagram contradicting the in-place recommendation. These are near-free to fix, block nothing technically, but corrupt the Appendix B.1 authoritative per-session re-read, so they are top priority. GAP-53's traceability drift-check (a bespoke ID-registry script) mechanically prevents recurrence and also found a NEW live drift: §17.3 is missing all IR-/DR- rows.

(2) MS-1 schema-freeze blockers (GAP-24/26/27/28/29/30/58, feeding OQ-004) — before artifact JSON Schemas can freeze, docmend must settle identity (UUIDv7 docmend.id + a 3-tier identity-recovery algorithm; a run-ID scheme that is referenced everywhere but defined nowhere; a per-action ID), the manifest on-disk representation (NDJSON, not a single JSON document, to be crash-safe/append-safe — a real IR-007 wording conflict), schema versioning/migration, and the JSON Schema validator library (jsonschema>=4.26, needing a §8.6 OQ). These are High and urgent because OQ-004 is a P0 at MS-1 yet structurally depends on feeders scheduled later (GAP-04).

(3) MS-3 writer/safety-gate depth (GAP-23/33/34/35/36/38/39, feeding OQ-005) — the restore command literally does not exist yet the restore-drill is an MS-3 exit criterion; backup integrity is copy-then-trust rather than verify-then-mutate; preservation-strategy proofs are self-declared booleans (with a concrete GitPython untracked_files=False footgun); the ~10-check gate has no combinatorial test strategy or deterministic blocking-reason contract; and there is no worker-locking for shared artifacts or disk-space preflight. All High.

(4) MS-2 transform correctness (GAP-07/42/43/44/45/46/47/63) — the encoding detector/confidence/threshold has no evidence base and charset-normalizer exposes no confidence matching FR-007 as written; UTF-16 BOM files are permanently unprocessable because they collide with the NUL-byte risky heuristic; HTML (half the corpus) is silently excluded from the default include globs; and there is no Unicode normalization policy or per-file watchdog. The encoding cluster is High and must be evidence-backed before MS-2 hardens transform code.

(5) MS-0 tooling and the dependency-approval gate (GAP-19/22/50/52/59/60) — logging library, concurrency primitive, property-testing (Hypothesis), import-linter, and license-scanning each require a §8.6 OQ that does not exist; §8.6 should be split into Runtime vs Dev/Test since several tools already sit outside it by omission.

Six gaps become new open questions (proposed OQ-015..020: encoding thresholds, concurrency primitive, logging library, validator library, Hypothesis, generic-tool scope). Research (22 reports written this pass) resolved almost every technical question conclusively from primary sources — qdev marked all deep_research_warranted=false — but four topics (encoding non-ASCII floor, free-threading Phase III timeline, real backup-medium throughput, and review-artifact content-exposure policy) carry residual empirical or owner-policy questions and are queued as ChatGPT Deep-Research prompts. A cross-cutting caveat from the research pass: at least seven reports independently proposed minting 'OQ-015' for different topics, so the orchestrator must do one coordinated OQ-numbering pass when folding these in.

Top three priorities, in order: (a) fix the §21/handoff drift and land the traceability drift-check in one pass; (b) settle the identity + manifest-format + output-model cluster (OQ-012 plus new run-ID/ID-scheme/NDJSON decisions) before OQ-004 freezes schemas at MS-1; (c) specify the restore command, backup-integrity verify-then-mutate, and preservation-proof substantiation before MS-3 writer work begins.

## Gap register (summary)

71 canonical gaps (consolidated from 104 raw findings across 12 lenses).

| ID | Title | Priority | Disposition | Related OQ | Report |
| --- | --- | --- | --- | --- | --- |
| GAP-01 | Spec §21 OQ table and spec body omit OQ-012/013/014 | High | doc-fix | OQ-012 | — |
| GAP-02 | Handoff/status/TODO docs undercount blocking OQs (three vs four) | High | doc-fix | OQ-012 | — |
| GAP-03 | Blocking-flag drift (OQ-003/006/009) plus undefined P0/P1/P2 taxonomy | High | doc-fix | OQ-003 | — |
| GAP-04 | OQ backlog sequencing contradictions around OQ-004 | High | doc-fix | OQ-004 | — |
| GAP-05 | OQ hygiene: split OQ-005 and OQ-002, flag OQ-004 Pydantic | Medium | doc-fix | OQ-005 | — |
| GAP-06 | resolved-questions.md empty; no owner decision cadence | Low | doc-fix | — | — |
| GAP-07 | HTML excluded from v1 default paths.include; mechanical HTML handling undefined | High | update-existing-oq | OQ-001 | — |
| GAP-08 | 'Generally useful tool' ambition unbacked vs personal-library taxonomy | Medium | new-open-question | OQ-001 | — |
| GAP-09 | NG-003 vs WH-002 contradict on spelling correction | Medium | doc-fix | OQ-001 | — |
| GAP-10 | WH deferred-capability table inconsistencies | Low | doc-fix | OQ-009 | — |
| GAP-11 | No CLI exit-code taxonomy for scan/plan/apply | High | update-existing-oq | OQ-006 | — |
| GAP-12 | verify has no flag to locate manifest/report/plan artifacts | Medium | update-existing-oq | OQ-006 | — |
| GAP-13 | plan input ambiguously a raw PATH vs an inventory artifact | Medium | spec-change | OQ-004 | — |
| GAP-14 | --version flag missing from IR-005 despite exposed `__version__` | Medium | spec-change | — | — |
| GAP-15 | Config validation covers only unknown keys, not type/enum/range | Medium | spec-change | — | — |
| GAP-16 | Config precedence and merge semantics underspecified | Medium | spec-change | OQ-014 | — |
| GAP-17 | IR-005 flag behaviors undefined / criterion not testable | Low | spec-change | — | — |
| GAP-18 | No ERR- rows for scan-time or plan-time failures | Medium | spec-change | — | — |
| GAP-19 | Logging framework, format, destination, rotation unspecified | High | new-open-question | — | [`structured-logging-library.md`](research/structured-logging-library.md) |
| GAP-20 | No progress/ETA reporting or liveness heartbeat | Medium | spec-change | OQ-010 | [`batch-throughput-and-capacity.md`](research/batch-throughput-and-capacity.md) |
| GAP-21 | Console/human-readable summary format undefined | Low | spec-change | OQ-004 | — |
| GAP-22 | Concurrency primitive undecided for Python 3.14 target | High | new-open-question | OQ-010 | [`python-314-concurrency-model.md`](research/python-314-concurrency-model.md) |
| GAP-23 | No worker-locking/mutual-exclusion for shared manifest/report/backup | High | spec-change | OQ-004 | [`python-314-concurrency-model.md`](research/python-314-concurrency-model.md) |
| GAP-24 | Incremental-manifest 'JSON' framing conflicts with crash-safe append | High | spec-change | OQ-004 | [`append-safe-manifest-format.md`](research/append-safe-manifest-format.md) |
| GAP-25 | No resume/checkpoint story for interrupted scan or plan | Medium | update-existing-oq | OQ-003 | — |
| GAP-26 | No algorithm for generating docmend.id or recovering identity on re-scan | High | update-existing-oq | OQ-002 | [`stable-document-id-scheme.md`](research/stable-document-id-scheme.md) |
| GAP-27 | Run-ID scheme referenced but never defined | High | update-existing-oq | OQ-004 | — |
| GAP-28 | DR-002 plan requirement lacks a per-action ID assumed by resume | Medium | spec-change | OQ-004 | — |
| GAP-29 | No schema-versioning/migration policy for artifacts and frontmatter | Medium | research-only | OQ-004 | [`json-schema-versioning-migration.md`](research/json-schema-versioning-migration.md) |
| GAP-30 | Manifest granularity (per-run vs cumulative ledger) undecided | Medium | update-existing-oq | OQ-004 | [`append-safe-manifest-format.md`](research/append-safe-manifest-format.md) |
| GAP-31 | Symlink handling underspecified beyond 'don't follow for mutation' | Medium | update-existing-oq | OQ-004 | — |
| GAP-32 | Hardlinks entirely unaddressed unlike symlinks | Medium | update-existing-oq | OQ-004 | — |
| GAP-33 | No docmend restore command; restore-drill automation undefined | High | spec-change | OQ-005 | [`restore-from-manifest-design.md`](research/restore-from-manifest-design.md) |
| GAP-34 | Preservation-strategy safety-gate checks are self-declared, not verified | High | update-existing-oq | OQ-005 | [`backup-integrity-verification.md`](research/backup-integrity-verification.md) |
| GAP-35 | No post-copy backup-integrity verification before mutating original | High | spec-change | OQ-005 | [`backup-integrity-verification.md`](research/backup-integrity-verification.md) |
| GAP-36 | Backup-directory-inside-target-root hazard not codified | High | update-existing-oq | OQ-005 | — |
| GAP-37 | Tool-written backup file/dir permissions unaddressed for confidential data | Low | spec-change | — | — |
| GAP-38 | No disk-space/backup-storage preflight or §14 storage-overhead dimension | Medium | spec-change | OQ-010 | [`batch-throughput-and-capacity.md`](research/batch-throughput-and-capacity.md) |
| GAP-39 | Safety-gate check combinatorics have no defined test strategy | High | spec-change | OQ-005 | [`combinatorial-safety-gate-testing.md`](research/combinatorial-safety-gate-testing.md) |
| GAP-40 | Path-containment mechanism asserted but not specified (realpath/TOCTOU) | Medium | research-only | OQ-004 | [`path-containment-toctou.md`](research/path-containment-toctou.md) |
| GAP-41 | fsync/atomic-replace guarantees unbounded across filesystems | Low | research-only | — | [`atomic-write-filesystem-semantics.md`](research/atomic-write-filesystem-semantics.md) |
| GAP-42 | Encoding-detector choice and 0.80 confidence threshold have no evidence base or owning OQ | High | new-open-question | OQ-001 | [`encoding-detection-benchmark.md`](research/encoding-detection-benchmark.md) |
| GAP-43 | charset-normalizer exposes no single 0-1 confidence matching FR-007 | High | spec-change | — | [`encoding-detection-benchmark.md`](research/encoding-detection-benchmark.md) |
| GAP-44 | UTF-16/UTF-32 BOM handling unaddressed; conflicts with NUL-byte heuristic | High | spec-change | — | — |
| GAP-45 | No Unicode normalization form (NFC/NFD) policy for content or filenames | Medium | research-only | — | [`unicode-normalization-policy.md`](research/unicode-normalization-policy.md) |
| GAP-46 | EC-005 'empty or drastically smaller output' has no numeric ratio or knob | Medium | spec-change | — | — |
| GAP-47 | whitespace.normalize_tabs has no defined transformation semantics | Medium | spec-change | — | — |
| GAP-48 | Missing edge case for already-empty (zero-byte) source files | Low | spec-change | — | — |
| GAP-49 | No generation strategy for the 100k synthetic corpus or weird-document fixtures, no public-safe anonymization path | High | spec-change | — | [`synthetic-corpus-generation.md`](research/synthetic-corpus-generation.md) |
| GAP-50 | Property-based testing required but Hypothesis not in §8.6 dependency policy | Medium | new-open-question | — | [`property-based-testing-hypothesis.md`](research/property-based-testing-hypothesis.md) |
| GAP-51 | No coverage-threshold reconciliation or per-component floor in the DoD | Medium | spec-change | — | — |
| GAP-52 | NFR-005 transform-purity has no mechanical enforcement | Medium | spec-change | — | [`architecture-and-traceability-enforcement.md`](research/architecture-and-traceability-enforcement.md) |
| GAP-53 | §17.3 traceability matrix omits IR/DR rows and has no drift-check automation | Medium | spec-change | OQ-004 | [`architecture-and-traceability-enforcement.md`](research/architecture-and-traceability-enforcement.md) |
| GAP-54 | 100k-file scale test has no defined CI placement or execution budget | Low | spec-change | OQ-010 | [`batch-throughput-and-capacity.md`](research/batch-throughput-and-capacity.md) |
| GAP-55 | FR-016 vs FR-014 frontmatter-validation conditionality contradicts OQ-009 | High | update-existing-oq | OQ-009 | — |
| GAP-56 | No frontmatter JSON Schema authored; §9 null-heavy example contradicts OQ-013 | Medium | doc-fix | OQ-013 | — |
| GAP-57 | Controlled vocabularies (OQ-007) have no extensibility mechanism once frozen | Low | update-existing-oq | OQ-007 | — |
| GAP-58 | JSON Schema validator library choice has no OQ despite §8.6 requiring one | Medium | new-open-question | OQ-004 | [`json-schema-validator-library.md`](research/json-schema-validator-library.md) |
| GAP-59 | No dependency license policy or license-check tool for §16 and MS-0 | Medium | research-only | — | [`license-compliance-tooling.md`](research/license-compliance-tooling.md) |
| GAP-60 | §8.6 runtime deps not in pyproject; no tracked MS-0 task; 3.14 wheel readiness unrecorded | Low | doc-fix | — | [`python-314-wheel-readiness.md`](research/python-314-wheel-readiness.md) |
| GAP-61 | Review-workflow presupposed by WH-002/C.3 is undesigned and may conflict with headless-CLI/NG-001 | Medium | research-only | — | [`batch-curation-review-workflow.md`](research/batch-curation-review-workflow.md) |
| GAP-62 | §7.2 preamble names usability/maintainability NFR categories but no NFR covers them | Medium | spec-change | — | — |
| GAP-63 | No per-file processing timeout/watchdog requirement or risk row | Medium | spec-change | — | [`per-file-watchdog-timeout.md`](research/per-file-watchdog-timeout.md) |
| GAP-64 | §20 'Operational usability' success metric is not independently measurable | Low | spec-change | — | — |
| GAP-65 | No requirement that frontmatter/config YAML parsing use a safe loader | Medium | spec-change | — | [`safe-yaml-loading.md`](research/safe-yaml-loading.md) |
| GAP-66 | Stale docs/handoff.md pointers survive migration to docs/handoff/ | Medium | doc-fix | — | — |
| GAP-67 | ADR-0001 links a removed spec file twice and never links the canonical spec | Medium | doc-fix | — | — |
| GAP-68 | docs/prompt.md points research output at a nonexistent docs/research-reports/ | Low | doc-fix | — | — |
| GAP-69 | README.md is a 3-line stub | Low | doc-fix | — | — |
| GAP-70 | Architecture diagram's 'Converted library' node contradicts in-place recommendation | Medium | doc-fix | OQ-012 | — |
| GAP-71 | No console entry point wired; MS-0 overstates it as 'largely present' | Low | doc-fix | — | — |

## High-priority gaps (22)

### GAP-01 — Spec §21 OQ table and spec body omit OQ-012/013/014

**Priority:** High · **Disposition:** doc-fix · **Related OQ:** OQ-012 · **Report:** —

**Recommendation:** Add OQ-012/013/014 rows to §21 and inline cross-references (OQ-012 at §8.1/§8.2.2/§13.5/§18.2, OQ-013 at §9, OQ-014 at FR-004/IR-003); update the §21 'nothing silently dropped' claim and Revision History in the same commit.

**Downstream impact:** Restores the Appendix B.1 per-session re-read as an authoritative OQ list so MS-3 writer work sees the P0 output-model blocker (OQ-012); no code impact but unblocks correct milestone sequencing.

### GAP-02 — Handoff/status/TODO docs undercount blocking OQs (three vs four)

**Priority:** High · **Disposition:** doc-fix · **Related OQ:** OQ-012 · **Report:** —

**Recommendation:** Correct 'three blocking OQs' to four across state.md, architecture.md, STATUS.md, TODO.md, adding OQ-012 as the fourth P0 gating MS-3.

**Downstream impact:** Owner's blocker list becomes correct; MS-3 writer work is not started against an unresolved output model. Documentation-only.

### GAP-03 — Blocking-flag drift (OQ-003/006/009) plus undefined P0/P1/P2 taxonomy

**Priority:** High · **Disposition:** doc-fix · **Related OQ:** OQ-003 · **Report:** —

**Recommendation:** Reconcile §21 Blocking=No against open-questions.md's P1 near-blocker labels for OQ-003/006/009, and add a legend in open-questions.md Important Notes defining P0/P1/P2 and their mapping to §21's binary Blocking column; reference from Appendix A.

**Downstream impact:** Makes urgency mechanically checkable and closes the same rot class that produced the OQ-012 omission; feeds the traceability drift-check (GAP-53). Documentation-only.

### GAP-04 — OQ backlog sequencing contradictions around OQ-004

**Priority:** High · **Disposition:** doc-fix · **Related OQ:** OQ-004 · **Report:** —

**Recommendation:** Document that OQ-004 (MS-1) structurally depends on OQ-002/003/012 (scheduled at/after its deadline) and either pull those feeders earlier or annotate OQ-004 that its schemas freeze only the fields those decisions do not touch; capture the dependency order explicitly in each OQ's Needed-by.

**Downstream impact:** Prevents freezing artifact schemas at MS-1 before identity/resume/output-root inputs exist, avoiding breaking schema revisions later; reshapes OQ-004 Agent notes and MS-1 exit criteria.

### GAP-07 — HTML excluded from v1 default paths.include; mechanical HTML handling undefined

**Priority:** High · **Disposition:** update-existing-oq · **Related OQ:** OQ-001 · **Report:** —

**Recommendation:** In OQ-001, make the include-glob/HTML-visibility decision explicit: either add **/\*.html|**/\*.htm to §18.2 default paths.include with a defined mechanical posture (scan-and-classify only, never whitespace-transform markup, guard `<pre>`/`<script>`/`<style>`), or explicitly exclude HTML in v1 and say so in §1/§2.1 so a default first run does not silently ignore half the corpus.

**Downstream impact:** Determines whether the tool's stated purpose is honored on a default run; touches §18.2 config defaults, FR-007..010 scope, WH-004 boundary, and the transform layer's file-type dispatch.

### GAP-11 — No CLI exit-code taxonomy for scan/plan/apply

**Priority:** High · **Disposition:** update-existing-oq · **Related OQ:** OQ-006 · **Report:** —

**Recommendation:** Extend OQ-006's 0/1/2/3 proposal from verify-only to a single tool-wide taxonomy covering success-with-skips, partial failure, invocation/config error, and safety refusal, applied uniformly to scan/plan/apply/verify/restore; make 'exits non-zero' acceptance criteria cite specific codes.

**Downstream impact:** Turns un-automatable 'exits non-zero' criteria into testable ones and lets driver scripts/agents distinguish partial success from abort; touches IR-001..004, FR-003/005, ERR-002, the §17.3 matrix, and every CLI test.

### GAP-19 — Logging framework, format, destination, rotation unspecified

**Priority:** High · **Disposition:** new-open-question · **Related OQ:** — · **Report:** [`structured-logging-library.md`](research/structured-logging-library.md) · **New OQ**

**Recommendation:** Open an OQ (and §8.6 dependency row) adopting structlog wired through stdlib logging handlers, emitting JSON Lines to a per-run file named by run-ID plus Rich-rendered console text, with --verbose/--quiet governing console level only and the file sink floored at DEBUG; extend the never-auto-delete retention rule to logs; use QueueHandler+QueueListener for NFR-001 parallelism.

**Downstream impact:** Determines whether NFR-003 mid-batch post-mortem debugging at 100k+ files is feasible; adds a dependency (owner approval), a §8.6 row, log-schema fields cross-referenced to run-ID (GAP-27), and console-flag semantics (GAP-17). MS-0 decision.

### GAP-22 — Concurrency primitive undecided for Python 3.14 target

**Priority:** High · **Disposition:** new-open-question · **Related OQ:** OQ-010 · **Report:** [`python-314-concurrency-model.md`](research/python-314-concurrency-model.md) · **New OQ**

**Recommendation:** Open an OQ adopting concurrent.futures.ProcessPoolExecutor with multiprocessing.get_context('forkserver') pinned explicitly as the v1 CPU-bound primitive (not free-threaded 3.14t, not asyncio), default parallel.workers='auto' (os.process_cpu_count()) with a sequential mode as the default-until-profiled path used by NFR-005 purity tests; add a §18.2 parallel.\* config surface; fold into OQ-010.

**Downstream impact:** Decides whether the Must-priority NFR-001 parallel capability is implementable and sets worker-count defaults (OQ-010); introduces the parallel.\* config, the forkserver top-level-target constraint, and the worker-locking requirement (GAP-23). Architecture decision affecting MS-3/MS-5.

### GAP-23 — No worker-locking/mutual-exclusion for shared manifest/report/backup

**Priority:** High · **Disposition:** spec-change · **Related OQ:** OQ-004 · **Report:** [`python-314-concurrency-model.md`](research/python-314-concurrency-model.md)

**Recommendation:** Specify a single-writer actor (or per-worker shard+merge) for incremental manifest/report appends and a run-level lock preventing two apply/plan invocations racing on the same manifest/report/backup path; NFR-002's atomic guarantee is per-document, not per shared artifact.

**Downstream impact:** Prevents JSON-artifact corruption/lost entries and accidental double-launch clobbering; couples tightly to the concurrency primitive (GAP-22) and the append-safe manifest format (GAP-24), and adds a lock-acquisition step to the writer layer.

### GAP-24 — Incremental-manifest 'JSON' framing conflicts with crash-safe append

**Priority:** High · **Disposition:** spec-change · **Related OQ:** OQ-004 · **Report:** [`append-safe-manifest-format.md`](research/append-safe-manifest-format.md)

**Recommendation:** Adopt NDJSON (JSON Lines) for the DR-004 manifest — one schema-valid object per line, one file per apply run (manifest-<run_id>.jsonl), each record fsync'd immediately — and reword IR-007's 'as JSON' to be per-artifact (single document for inventory/plan/report; JSON Lines for the manifest); implement a Redis-AOF-style last-line-only torn-tail discard rule in resume/verify.

**Downstream impact:** A foundational OQ-004 schema decision: makes FR-006/§12.3 incremental writes crash-safe at O(1) append cost, changes IR-007 wording, and defines the on-disk shape the resume/reconciliation logic (OQ-003) reads after a crash. Blocks MS-1 schema freeze.

### GAP-26 — No algorithm for generating docmend.id or recovering identity on re-scan

**Priority:** High · **Disposition:** update-existing-oq · **Related OQ:** OQ-002 · **Report:** [`stable-document-id-scheme.md`](research/stable-document-id-scheme.md)

**Recommendation:** In OQ-002, adopt UUIDv7 via Python 3.14 stdlib uuid.uuid7() for docmend.id (zero-dependency, standards-based) plus a 3-tier identity-recovery algorithm on re-scan: trust valid frontmatter docmend.id, else manifest path-match with hash confirmation, else manifest content-hash match, else mint a new UUIDv7 with an explicit 'identity not recoverable' report flag.

**Downstream impact:** Because the ID must survive full rewrites it cannot be content-derived, so the recovery path is the only source of truth; this unblocks OQ-002/OQ-004 identity fields and adds an identity-recovery step to scan/plan.

### GAP-27 — Run-ID scheme referenced but never defined

**Priority:** High · **Disposition:** update-existing-oq · **Related OQ:** OQ-004 · **Report:** —

**Recommendation:** Define a run-ID format (e.g. UTC timestamp + short random suffix, or UUIDv7), its uniqueness/collision guarantee, generation point, and cross-command linkage rule: whether apply inherits plan's run-ID or mints its own linked via a plan reference, and how a resumed apply reconciles IDs.

**Downstream impact:** Every artifact and structured log needs a stable run identity to cross-reference (DR-001..004) and resume; directly blocks writing the OQ-004 JSON Schemas and the log-schema (GAP-19). MS-1 blocker.

### GAP-33 — No docmend restore command; restore-drill automation undefined

**Priority:** High · **Disposition:** spec-change · **Related OQ:** OQ-005 · **Report:** [`restore-from-manifest-design.md`](research/restore-from-manifest-design.md)

**Recommendation:** Add a first-class `docmend restore [PATH...] [--dry-run|--write] [--to original|run:<id>] [--verify] [--run RUN_ID]` command in MS-3, symmetric to apply (same atomic-replace writer, path-containment, dry-run-default/--write opt-in); replay manifest records per docmend.id in strict reverse-chronological (LIFO) order; scope v1's automated path to preservation.kind=tool_backup and print a manual-restore report for git/external_backup so restore is decoupled from OQ-008; implement the 8-assertion CI restore drill from the report.

**Downstream impact:** Makes FR-006 reversibility real and lets the MS-3 restore-drill exit criterion be written; adds a CLI verb (IR-008), a restore report schema, a per-manifest-record preservation.kind/preservation.ref field (blocks OQ-005), and 8 drill assertions to §17.2. MS-3 blocker.

### GAP-34 — Preservation-strategy safety-gate checks are self-declared, not verified

**Priority:** High · **Disposition:** update-existing-oq · **Related OQ:** OQ-005 · **Report:** [`backup-integrity-verification.md`](research/backup-integrity-verification.md)

**Recommendation:** In OQ-005, replace the boolean-config gate with per-strategy machine checks: for Git, non-bare working tree + all covered files tracked + is_dirty(path=covered_paths, untracked_files=True) is False (explicitly overriding GitPython's untracked_files=False default) with HEAD hexsha recorded as restore anchor; for tool backups, reuse FR-006's verified result; for Borg/restic, require a machine-readable snapshot receipt with recency window + sampled coverage; raise 'external backups declared' from a bare boolean to a recency-checked attestation; re-check at a bounded interval during long runs.

**Downstream impact:** Prevents satisfying the gate with a flag and no real preservation (defeating §18.6 zero-loss RPO); rewrites FR-005 acceptance criteria, adds per-strategy proof checks and a preservation.kind manifest field, and adds TOCTOU-style re-check to the writer.

### GAP-35 — No post-copy backup-integrity verification before mutating original

**Priority:** High · **Disposition:** spec-change · **Related OQ:** OQ-005 · **Report:** [`backup-integrity-verification.md`](research/backup-integrity-verification.md)

**Recommendation:** Make FR-006 verify-then-mutate: fsync the backup, re-read it, recompute its hash, and compare against the plan's confirmed source.hash before the writer mutates the original; record a backup_verified manifest field; route a mismatch (silent truncation/corruption, full/failing medium) through ERR-004.

**Downstream impact:** Closes the cheap check that catches the zero-irreversible-loss failure class (G-002); adds a backup_verified field to the manifest schema (OQ-004) and a verify step to the writer layer. MS-3.

### GAP-36 — Backup-directory-inside-target-root hazard not codified

**Priority:** High · **Disposition:** update-existing-oq · **Related OQ:** OQ-005 · **Report:** —

**Recommendation:** Promote OQ-005's backup-destination-outside-target recommendation into FR-005/006 criteria and §18.2 validation: reject a backup_dir inside source_root (or auto-exclude it from discovery) so prior backups are not re-ingested or re-backed-up.

**Downstream impact:** An implementer reading only the spec of record would otherwise miss this; adds a config-validation check and a default paths.exclude entry. MS-3.

### GAP-39 — Safety-gate check combinatorics have no defined test strategy

**Priority:** High · **Disposition:** spec-change · **Related OQ:** OQ-005 · **Report:** [`combinatorial-safety-gate-testing.md`](research/combinatorial-safety-gate-testing.md)

**Recommendation:** Adopt allpairspy (pure-Python, dev-only, behind a §8.6 OQ) for pairwise (t=2) coverage of the ~10 gate checks, escalating to t=3 for the preservation-strategy/manifest-writable/backup-destination trio (NIST staged-strength); implement the gate as pure independent predicates evaluated every run with a fixed priority-ordered deterministic blocking_reason plus a complete all_failures list.

**Downstream impact:** Bounds the >1000-state space and makes the gate's determinism (which reason blocks) a tested safety-critical contract; adds a dev dependency (§8.6 OQ), an FR-005 test-strategy row, and a blocking-order contract to OQ-005. MS-3.

### GAP-42 — Encoding-detector choice and 0.80 confidence threshold have no evidence base or owning OQ

**Priority:** High · **Disposition:** new-open-question · **Related OQ:** OQ-001 · **Report:** [`encoding-detection-benchmark.md`](research/encoding-detection-benchmark.md) · **New OQ**

**Recommendation:** Open an OQ keeping charset-normalizer as FR-007's sole detector (do not add chardet/faust-cchardet/uchardet), defining source.detected_encoding.confidence as 1.0 - CharsetMatch.chaos (matching charset-normalizer's own chardet-compat formula), keeping the 0.80 fail_below_confidence default, and adding a second independent skip gate on non-ASCII byte count (8-20, encoding-family dependent, validated against the weird-document corpus) because the documented short-text tie failure produces chaos=0.0 on a wrong answer no confidence threshold can catch.

**Downstream impact:** Governs false-skip/false-accept rates for the core safety premise (A-003/G-005) and must be evidence-backed before MS-2 hardens transform code; adds a non-ASCII-floor config key, provenance fields (chaos/coherence/language) to the inventory schema, and fixtures to §17.2. MS-2 decision.

### GAP-43 — charset-normalizer exposes no single 0-1 confidence matching FR-007

**Priority:** High · **Disposition:** spec-change · **Related OQ:** — · **Report:** [`encoding-detection-benchmark.md`](research/encoding-detection-benchmark.md)

**Recommendation:** Reword FR-007 and encoding.fail_below_confidence to define the confidence score as 1.0 - CharsetMatch.chaos (the shipping chardet-compat formula, with the -0.2 sub-32-byte penalty), recording chaos/coherence/language separately as Appendix-C.4 provenance rather than blending them into the scalar.

**Downstream impact:** FR-007 currently assumes a ready-made confidence API that does not exist as specified; this pins the exact API surface and feeds the non-ASCII-floor decision (GAP-42). Part of the encoding OQ.

### GAP-44 — UTF-16/UTF-32 BOM handling unaddressed; conflicts with NUL-byte heuristic

**Priority:** High · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Extend EC-007 beyond UTF-8-BOM: detect UTF-16/32 BOMs (and the interleaved-0x00 pattern of legacy Windows Notepad UTF-16LE) BEFORE the FR-015/EC-004 NUL-byte risky check, and state whether UTF-16/32 is in scope (recommended: yes, decode via BOM) so legitimate UTF-16 files are not permanently skipped as risky.

**Downstream impact:** Rescues a whole class of real legacy files from being silently unconvertible; reorders the transform-layer detection pipeline (BOM sniff before NUL check) and adds an EC row.

### GAP-49 — No generation strategy for the 100k synthetic corpus or weird-document fixtures, no public-safe anonymization path

**Priority:** High · **Disposition:** spec-change · **Related OQ:** — · **Report:** [`synthetic-corpus-generation.md`](research/synthetic-corpus-generation.md)

**Recommendation:** Adopt a two-corpus architecture: a session-scoped seeded pytest tmp_path_factory 100k-file scale corpus (never committed, behind a slow/scale marker) and a small size-capped git-committed weird-document corpus under tests/fixtures/weird_documents/ (chardet/test-data provenance-decoupled convention), both from one pure seedable generator; and a documented anonymization procedure (capture byte offsets + causal mechanism, re-synthesize the same mechanism through unrelated filler, verify identical code path, reviewer checklist) so real anomalies become content-free fixtures.

**Downstream impact:** MS-1/MS-2 tests and the MS-5 scale test currently have no starting point and the corpus can't grow without leaking real content (C-002); adds §17.2/§19 MS-5 content, a generator module, a fixture-metadata schema (alongside OQ-004), and a conventions #6 review-gate line. High (MS-1..MS-5).

### GAP-55 — FR-016 vs FR-014 frontmatter-validation conditionality contradicts OQ-009

**Priority:** High · **Disposition:** update-existing-oq · **Related OQ:** OQ-009 · **Report:** —

**Recommendation:** In OQ-009, reconcile FR-016 (Must, unconditional 'validate generated frontmatter') with FR-014's conditional 'where present' and with OQ-009's recommendation that v1 emits no bulk frontmatter: add explicit frontmatter-absent behavior so FR-016 is not written as unconditional live behavior that OQ-009's likely resolution turns into a no-op.

**Downstream impact:** Prevents a Must requirement becoming a silent no-op on every real run; rewrites FR-016 acceptance criteria conditioned on the OQ-009 emission-scope decision. MS-4/MS-5.

## Medium-priority gaps (35)

### GAP-05 — OQ hygiene: split OQ-005 and OQ-002, flag OQ-004 Pydantic

**Priority:** Medium · **Disposition:** doc-fix · **Related OQ:** OQ-005 · **Report:** —

**Recommendation:** Apply maintenance rule 3: split OQ-005's preservation-semantics fork into a pre-MS-1 item, move OQ-002's settled sub-questions (WH-001 extension rename, FR-010/011 collision policy) to resolved-questions.md, and add a note that OQ-004's Pydantic suggestion needs its own §8.6 dependency-approval OQ.

**Downstream impact:** Re-prioritizes MS-1 work correctly and closes the Appendix B.2 dependency-gate leak; edits confined to open-questions.md/resolved-questions.md.

### GAP-08 — 'Generally useful tool' ambition unbacked vs personal-library taxonomy

**Priority:** Medium · **Disposition:** new-open-question · **Related OQ:** OQ-001 · **Report:** — · **New OQ**

**Recommendation:** Open an OQ deciding whether docmend's domain-specific parts (§9 genre/status/story_type/rating vocabularies) are config-driven/pluggable or purpose-built; scope the §1 genericity claim to a concrete requirement or drop it.

**Downstream impact:** Materially shapes the frontmatter schema (OQ-004/007/013) — a pluggable vocabulary changes the schema shape and validator wiring; a purpose-built choice lets §9 stay hardcoded.

### GAP-09 — NG-003 vs WH-002 contradict on spelling correction

**Priority:** Medium · **Disposition:** doc-fix · **Related OQ:** OQ-001 · **Report:** —

**Recommendation:** Resolve within OQ-001: remove spelling from NG-003's 'safe form-level repairs' list (spelling is semantic, per WH-002) so the non-goals list is internally consistent before approval.

**Downstream impact:** Finalizes the explicit non-goals list; prevents an implementer from building unapproved spelling correction into v1 transforms.

### GAP-12 — verify has no flag to locate manifest/report/plan artifacts

**Priority:** Medium · **Disposition:** update-existing-oq · **Related OQ:** OQ-006 · **Report:** —

**Recommendation:** In OQ-006, add explicit --manifest/--report/--plan inputs to IR-004's verify signature (or specify a documented sidecar-discovery convention keyed on run-ID), symmetric with scan --report and plan --out.

**Downstream impact:** Makes FR-014 implementable as written; adds fields to the verify CLI contract and its tests, and ties to the run-ID scheme (GAP-27).

### GAP-13 — plan input ambiguously a raw PATH vs an inventory artifact

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** OQ-004 · **Report:** —

**Recommendation:** Reconcile IR-002 with FR-002/DR-002/Glossary: give plan an explicit --inventory input (consuming scan's inventory.json) or state that plan re-scans and how it guards against divergence from a reviewed inventory; pick one to wire the scan->plan handoff.

**Downstream impact:** Determines whether the reviewable scan->plan workflow (§10.1) is actually connected; affects IR-002, plan's CLI contract, and the inventory/plan schema linkage in OQ-004.

### GAP-14 — --version flag missing from IR-005 despite exposed `__version__`

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Add --version to IR-005's global-flag list; it exposes the `__version__`/conversion_version that ERR-006 and §18.3 rollback compatibility checks already depend on.

**Downstream impact:** Adds a standard testable CLI surface; small IR-005 and cli.py change plus a smoke test, aligned with test_smoke's existing `__version__` assertion.

### GAP-15 — Config validation covers only unknown keys, not type/enum/range

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Extend IR-006/FR-016 to validate known-key values: wrong TOML type, out-of-enum (e.g. on_collision=delete), and out-of-range (negative collapse_blank_lines, confidence outside [0,1]); add acceptance criteria and seeded-defect fixtures.

**Downstream impact:** Closes a stated review-focus class; touches the config loader, IR-006 criteria, and the §17.3 matrix.

### GAP-16 — Config precedence and merge semantics underspecified

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** OQ-014 · **Report:** —

**Recommendation:** Specify list-valued merge (--include replace vs append), whether a default config search path exists or --config is mandatory, behavior when --config is omitted for plan/apply, and the interaction between write.dry_run_default and OQ-014's --write flag.

**Downstream impact:** Prevents silent misconfiguration in a safety-critical default posture (NFR-004); touches §18.2, the config loader, and OQ-014's opt-in design.

### GAP-18 — No ERR- rows for scan-time or plan-time failures

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Add ERR- rows for scan failures (nonexistent PATH, permission-denied root, symlink loop) and plan failures (malformed TOML, stale inventory schema, unwritable --out), symmetric with the apply-scoped ERR-001..006.

**Downstream impact:** Gives FR-001/002 and IR-001/002 traceable failure behavior in §17.3; adds error classes and their exit-code mapping (couples to GAP-11).

### GAP-20 — No progress/ETA reporting or liveness heartbeat

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** OQ-010 · **Report:** [`batch-throughput-and-capacity.md`](research/batch-throughput-and-capacity.md)

**Recommendation:** Add an NFR/FR tying a Rich progress bar (2-4 Hz refresh, 60-120s speed window) plus a TTY-independent heartbeat log line (every 1,000 files or 30s) to §18.5 Observability, for OQ-010's 8-hour unattended pass.

**Downstream impact:** Gives an operator a specified way to tell a multi-hour run is alive/hung/progressing (§20 no-babysitting goal); couples to the logging decision (GAP-19) and OQ-010.

### GAP-25 — No resume/checkpoint story for interrupted scan or plan

**Priority:** Medium · **Disposition:** update-existing-oq · **Related OQ:** OQ-003 · **Report:** —

**Recommendation:** In OQ-003, state explicitly whether scan (classification) and plan (encoding detection + risk classification) restart from scratch (acceptable but costly, and must be documented) or checkpoint, since FR-013/AW-001 define resume only for apply.

**Downstream impact:** Restart-from-scratch cost is non-trivial against OQ-010's 8-hour pressure; the resume-model IDs (run/action/status) shape every artifact schema (OQ-004).

### GAP-28 — DR-002 plan requirement lacks a per-action ID assumed by resume

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** OQ-004 · **Report:** —

**Recommendation:** Promote the 'action ID' concept from OQ-003/OQ-004 non-binding notes into DR-002's binding text so a planned action (a file may have more than one) correlates with its manifest/report outcome.

**Downstream impact:** Resume (FR-013) needs per-action correlation; adds an action_id field to the plan and manifest schemas before MS-1/MS-2.

### GAP-29 — No schema-versioning/migration policy for artifacts and frontmatter

**Priority:** Medium · **Disposition:** research-only · **Related OQ:** OQ-004 · **Report:** [`json-schema-versioning-migration.md`](research/json-schema-versioning-migration.md)

**Recommendation:** Adopt MAJOR.MINOR version strings per schema (Terraform format_version precedent), keep schemas strict (additionalProperties:false) and document honestly that MINOR guarantees only backward compatibility (refuse newer-minor artifacts, matching FR-015 skip-and-report); model already-converted-corpus frontmatter migration as a new first-class planned action (frontmatter_migrate) flowing through plan/dry-run/apply/manifest/verify.

**Downstream impact:** Defines verify/apply behavior across schema_version mismatch (six-row decision table feeds OQ-005 gate and OQ-006 exit codes) and gives converted files a migration path; extends DR-005 and adds a planned-action type.

### GAP-30 — Manifest granularity (per-run vs cumulative ledger) undecided

**Priority:** Medium · **Disposition:** update-existing-oq · **Related OQ:** OQ-004 · **Report:** [`append-safe-manifest-format.md`](research/append-safe-manifest-format.md)

**Recommendation:** In OQ-004, decide: keep append-only per-run NDJSON ledgers as the permanent source of truth (per GAP-24) plus a small regenerable 'latest state per path' index rewritten atomically at end-of-run for fast multi-run restore lookups.

**Downstream impact:** Multi-run corpora mutate the same file over months; restore-to-pre-apply-state needs to know which manifest entries belong to which historical state per id/path — gates the restore tooling (GAP-33).

### GAP-31 — Symlink handling underspecified beyond 'don't follow for mutation'

**Priority:** Medium · **Disposition:** update-existing-oq · **Related OQ:** OQ-004 · **Report:** —

**Recommendation:** In OQ-004, specify the inventory record shape for a symlink (distinct type, stored/resolved target), that directory walking uses os.walk(followlinks=False) to avoid loops/duplicates, how a target outside source_root is handled (ties to §13.5 containment), and how source/output hashes are computed or omitted.

**Downstream impact:** A 20+-year library plausibly contains symlinks; undefined walking risks infinite loops or duplicate processing; adds symlink fields to the inventory schema and a containment check reuse (GAP-40).

### GAP-32 — Hardlinks entirely unaddressed unlike symlinks

**Priority:** Medium · **Disposition:** update-existing-oq · **Related OQ:** OQ-004 · **Report:** —

**Recommendation:** In OQ-004, define hardlink handling: detect shared inodes (st_nlink>1) at scan, decide whether to process once and record the alias set, and document that os.replace() on one path breaks the hardlink so the other becomes stale — treat as a skip-and-report case rather than silent divergence.

**Downstream impact:** Prevents a silent undocumented divergence contradicting FR-015/NFR-004; adds inode/alias fields to the inventory schema.

**Resolved (2026-07-06):** owner adopted this policy. Now specified in spec §10.3 EC-011, DR-001 (shared-inode alias group), §21 OQ-004, and `docs/adr/adr-0005-durable-artifact-schema-contract.md` (amendment): skip-and-report hard-linked files at apply.

### GAP-38 — No disk-space/backup-storage preflight or §14 storage-overhead dimension

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** OQ-010 · **Report:** [`batch-throughput-and-capacity.md`](research/batch-throughput-and-capacity.md)

**Recommendation:** Add a per-mount disk-space preflight (required_free(backup_mount) ~= source_bytes x 1.15; required_free(library_mount) ~= max_file_size x workers x 1.10, each evaluated per distinct mount via shutil.disk_usage) as an OQ-005 gate check, and size the ~2x backup footprint plus transient atomic-temp space in §14.

**Downstream impact:** Prevents a multi-hour run hard-stopping on backup-destination exhaustion; adds a preflight gate check and a §14 capacity dimension.

### GAP-40 — Path-containment mechanism asserted but not specified (realpath/TOCTOU)

**Priority:** Medium · **Disposition:** research-only · **Related OQ:** OQ-004 · **Report:** [`path-containment-toctou.md`](research/path-containment-toctou.md)

**Recommendation:** Specify a two-stage canonical containment check (Path.resolve(strict=False) + is_relative_to(), never lexical-only) run at plan time AND re-run immediately before each write; harden the writer with dir_fd-scoped os.stat/os.open/os.replace + O_NOFOLLOW (leaf) + O_EXCL (temp), probing os.supports_dir_fd; explicitly do NOT build full per-component openat treewalk/chroot given the single-trusted-user threat model.

**Downstream impact:** Removes the containment black box so an implementer neither under- nor over-engineers it; names concrete primitives in §8.5/§13.5, reuses them for backup-dir containment (GAP-36) and symlink handling (GAP-31), and reconciles §13.5's adversarial framing with the trusted-user model elsewhere.

### GAP-45 — No Unicode normalization form (NFC/NFD) policy for content or filenames

**Priority:** Medium · **Disposition:** research-only · **Related OQ:** — · **Report:** [`unicode-normalization-policy.md`](research/unicode-normalization-policy.md)

**Recommendation:** Adopt NFC (never NFD/NFKC/NFKD, which would violate NG-003) as a new mechanical transform: normalize content in the Transform layer after decode and before FR-008/FR-009, normalize filename stems in the Planning layer at target_path computation (keeping source.original_path byte-exact); compute source.hash over raw pre-decode bytes and output.hash over final post-normalization bytes; add an EC row for normalization-induced rename collisions; treat as its own OQ/FR, not a silent fold-in.

**Downstream impact:** Fixes byte-level-only definitions of idempotent (FR-017), staleness (FR-003), and duplicate (WH-005/C.3) so hash mechanisms don't miss NFC/NFD-equivalent text; adds a transform stage, an EC row, and gives dedup rung-2 a free correctness win. MS-2.

### GAP-46 — EC-005 'empty or drastically smaller output' has no numeric ratio or knob

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Give EC-005 a concrete configurable ratio (a §18.2 row, e.g. shrink_ratio_skip_threshold) and disambiguate it from legitimate aggressive blank-line/trailing-whitespace shrinkage of padded legacy files to avoid false-positive skips.

**Downstream impact:** Makes the heuristic deterministically implementable and testable; adds a config key and refines the transform-validation check.

### GAP-47 — whitespace.normalize_tabs has no defined transformation semantics

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Define what normalize_tabs=true does (tabs-to-spaces vs tab-stop realignment, tab width, leading-only vs all, interaction with column-aligned ASCII tables/art) and add it to FR-009's enumerated whitespace transforms.

**Downstream impact:** Closes a config setting that refers to an unspecified requirement over a corruption class §1 explicitly names; adds an FR-009 sub-transform and tests.

### GAP-50 — Property-based testing required but Hypothesis not in §8.6 dependency policy

**Priority:** Medium · **Disposition:** new-open-question · **Related OQ:** — · **Report:** [`property-based-testing-hypothesis.md`](research/property-based-testing-hypothesis.md) · **New OQ**

**Recommendation:** Open an OQ adopting Hypothesis as a dev-only test dependency (in [dependency-groups].dev, never [project.dependencies]) with a CI settings profile loosening/disabling deadline; add the §8.6 row and split §8.6 into Runtime vs Dev/Test subsections since pytest/ruff/basedpyright already sit outside it.

**Downstream impact:** Resolves the direct contradiction between §17.2's property-test requirement and the Appendix B.2 dependency gate; adds a dev dependency and enables NFR-005 transform-purity property tests. MS-1 (tests).

### GAP-51 — No coverage-threshold reconciliation or per-component floor in the DoD

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Reconcile pyproject's blanket 85% branch gate with the §17.1 DoD and §17.3 matrix, and set a stricter floor on the writer/safety-gate layer §8.1 calls 'dangerous' so a build can't pass 85% while FR-005/FR-006 are thinly covered.

**Downstream impact:** Ensures safety-critical paths are actually covered; adds a per-module coverage floor to pyproject/check config and a §17.1 statement.

### GAP-52 — NFR-005 transform-purity has no mechanical enforcement

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** — · **Report:** [`architecture-and-traceability-enforcement.md`](research/architecture-and-traceability-enforcement.md)

**Recommendation:** Adopt import-linter (dev dependency) with a forbidden contract barring docmend.transform from importing os/pathlib/shutil/io/docmend.writer, layered with an autouse pytest fixture in tests/unit/transform/conftest.py blocking builtins.open/os.open/io.FileIO at runtime; land both at MS-0 before transform code exists.

**Downstream impact:** Turns an assertion satisfiable-today-and-silently-violated-later into a CI-enforced invariant; adds a dev dependency (§8.6 OQ), a contract config, and a test fixture.

### GAP-53 — §17.3 traceability matrix omits IR/DR rows and has no drift-check automation

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** OQ-004 · **Report:** [`architecture-and-traceability-enforcement.md`](research/architecture-and-traceability-enforcement.md)

**Recommendation:** Add IR-001..007 and DR-001..005 rows to the §17.3 matrix (confirmed missing) and build scripts/check_traceability.py (dependency-free, PEP 723, mirroring scripts/fix_spec_toc.py) as a generalized ID-registry cross-check wired into a new additive .github/workflows/traceability.yml — do not touch the standard-owned check.py/check.yml twins; the same check also catches the §21 OQ drift.

**Downstream impact:** Makes the completed matrix (Appendix B.3 sole accepted evidence) actually cover the CLI/artifact surface and mechanically prevents the §21-style rot; adds a script, a workflow, and matrix rows.

### GAP-56 — No frontmatter JSON Schema authored; §9 null-heavy example contradicts OQ-013

**Priority:** Medium · **Disposition:** doc-fix · **Related OQ:** OQ-013 · **Report:** —

**Recommendation:** Flag §9's null-heavy worked example (author/date/description: null) as gated on OQ-013's omit-by-default recommendation and note that schemas/frontmatter.schema.json (DR-005, confirmed missing) plus the rewritten example must be produced once OQ-013 resolves.

**Downstream impact:** Removes an unflagged internal inconsistency; the schema file and example are produced together after OQ-013. Documentation-only until then.

### GAP-58 — JSON Schema validator library choice has no OQ despite §8.6 requiring one

**Priority:** Medium · **Disposition:** new-open-question · **Related OQ:** OQ-004 · **Report:** [`json-schema-validator-library.md`](research/json-schema-validator-library.md) · **New OQ**

**Recommendation:** Open an OQ resolving §8.6's Conditional validator row to jsonschema>=4.26 (with the format-nongpl extra and an explicit Draft202012Validator + FormatChecker), reusing one compiled validator instance per schema across a run; record jsonschema-rs as the pre-vetted escalation path if profiling shows a bottleneck (its own §8.6 OQ) and adopt check-jsonschema only as a pre-commit dev hook, not a runtime dep.

**Downstream impact:** Per Appendix B.2 the dependency can't land without an approved OQ; this pins the validator that FR-016/DR-005 need and confirms Draft 2020-12 + 3.14 wheel readiness. MS-1.

### GAP-59 — No dependency license policy or license-check tool for §16 and MS-0

**Priority:** Medium · **Disposition:** research-only · **Related OQ:** — · **Report:** [`license-compliance-tooling.md`](research/license-compliance-tooling.md)

**Recommendation:** Adopt pip-licenses (dev dependency) with a --allow-only permissive allow-list step in check.yml after the pip-audit step, plus a copyleft-excluded-by-default policy in §8.6 (GPL/AGPL/LGPL/MPL/EPL and anything unlisted requires an OQ + owner approval); do not route through deptry (no license feature) or rely on uv export cyclonedx alone (audit artifact, not a gate).

**Downstream impact:** Makes §16's 'OSS license compatibility checked' verifiable and certifies MS-0; adds a CI step, a dev dependency, and a §8.6 policy paragraph. Legally grounded for a public MIT repo bundling deps.

### GAP-61 — Review-workflow presupposed by WH-002/C.3 is undesigned and may conflict with headless-CLI/NG-001

**Priority:** Medium · **Disposition:** research-only · **Related OQ:** — · **Report:** [`batch-curation-review-workflow.md`](research/batch-curation-review-workflow.md)

**Recommendation:** Seed a future OQ for WH-002/WH-005: (1) extend FR-015 skip-and-report to segregate 'needs semantic/dedup judgment' skips (beets quiet-mode); (2) for WH-005 build a decision-file/verdict-column side-car artifact (dedupe CSV pattern, no document text, stays inside §13.4/§13.5); (3) for WH-002 treat it as blocked on an explicit owner decision to amend or scope-carve §13.4/§13.5's 'no document content in artifacts' rule, since reviewing a text correction requires showing text; keep review headless (structured files consumed by generic external tools + an apply-corrections/apply-dedup subcommand), default to pessimistic-skip/exception-only to avoid rubber-stamping.

**Downstream impact:** Two deferred capabilities depend on an unaddressed architectural question that may contradict NG-001; the WH-002 branch specifically needs an owner policy decision on document-body exposure in artifacts before design. Deferred (post-v1) but the §13.4/§13.5 policy question can be surfaced now.

### GAP-62 — §7.2 preamble names usability/maintainability NFR categories but no NFR covers them

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Add a usability NFR (progress/ETA, actionable error content, NO_COLOR/non-TTY fallback for Rich, --quiet/--verbose legibility) and a maintainability NFR (forward-compatible/extensible plan/manifest schemas for the seven deferred WH capabilities), the two categories the §7.2 preamble names but leaves uncovered.

**Downstream impact:** Requirement-izes the primary UX risk (hours-long unattended run) and the schema forward-compatibility every deferred capability needs; couples to GAP-20/GAP-29 and adds NFR-006/007.

### GAP-63 — No per-file processing timeout/watchdog requirement or risk row

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** — · **Report:** [`per-file-watchdog-timeout.md`](research/per-file-watchdog-timeout.md)

**Recommendation:** Add a process-level per-file watchdog (multiprocessing.Process + join(timeout) + terminate()/kill(), zero new dependency, scoped to discovery+encoding-detection+transform, never the writer) plus regex-safety-by-construction (plain string methods first, Python 3.11+ possessive quantifiers/atomic groups for FR-009) and a plan-time max-file-size guard; record as a new ERR-007/R-007 pair with limits.\* config keys.

**Downstream impact:** Mitigates a plausible unattended-run failure (catastrophic-backtracking regex, adversarial file); the constraint is architectural (process vs thread) so it composes with whatever OQ-010 worker count wins; adds config keys, an ERR row, and a §15 risk row.

### GAP-65 — No requirement that frontmatter/config YAML parsing use a safe loader

**Priority:** Medium · **Disposition:** spec-change · **Related OQ:** — · **Report:** [`safe-yaml-loading.md`](research/safe-yaml-loading.md)

**Recommendation:** Adopt ruamel.yaml>=0.18 (YAML(typ='safe')) as the sole frontmatter loader with allow_duplicate_keys=False (satisfies C-006/FR-016 natively), a timestamp-constructor override keeping date/date-time scalars as strings (so jsonschema format assertions validate strings not datetime objects), a 64 KiB byte cap on the extracted frontmatter block before parsing, and RecursionError caught alongside the loader exception as an FR-015 skip; never call yaml.load/full_load/unsafe_load; add a §13.6 input-parsing checklist line and a §8.6 YAML dependency row.

**Downstream impact:** Hardens parsing of a decades-old corrupted/adversarial corpus (FR-015 risky category) and resolves the missing §8.6 YAML dependency row; feeds OQ-013's timestamp-as-string schema detail and adds a §13.6 item.

### GAP-66 — Stale docs/handoff.md pointers survive migration to docs/handoff/

**Priority:** Medium · **Disposition:** doc-fix · **Related OQ:** — · **Report:** —

**Recommendation:** Update the spec's §18.7 checklist and Appendix B.4 session-handoff clause and open-questions.md maintenance rule 6 to reference the docs/handoff/ directory layout instead of the retired single-file docs/handoff.md.

**Downstream impact:** Fixes three binding/authoritative dead links that contradict the repo's own changelog; documentation-only.

### GAP-67 — ADR-0001 links a removed spec file twice and never links the canonical spec

**Priority:** Medium · **Disposition:** doc-fix · **Related OQ:** — · **Report:** —

**Recommendation:** Update adr-0001's frontmatter related: list (line 21) and body link (line 45) from the removed docs/specs/docmend-spec-draft.md to the canonical docs/specs/docmend.md.

**Downstream impact:** Repairs a broken cross-reference in an accepted decision record; documentation-only.

**Resolved (2026-07-06):** already fixed in an earlier commit — `adr-0001` links `docs/specs/docmend.md` at both the frontmatter `related:` list and the body link; the removed `docmend-spec-draft.md` reference is gone. No action outstanding.

### GAP-70 — Architecture diagram's 'Converted library' node contradicts in-place recommendation

**Priority:** Medium · **Disposition:** doc-fix · **Related OQ:** OQ-012 · **Report:** —

**Recommendation:** Reconcile §8.2.2's Mermaid diagram (distinct 'Converted library' output node) with OQ-012's in-place recommendation and the absent write.output_root in §18.2, resolving the normative text-vs-diagram inconsistency as part of the OQ-012 decision.

**Downstream impact:** Removes a normative contradiction about the fundamental output model; resolved together with OQ-012, so it also gates MS-3 framing.

## Low-priority gaps (14)

### GAP-06 — resolved-questions.md empty; no owner decision cadence

**Priority:** Low · **Disposition:** doc-fix · **Related OQ:** — · **Report:** —

**Recommendation:** Add a tracked owner-review cadence (in TODO.md or handoff) so P0/P1 OQs get closed into resolved-questions.md rather than sitting in a one-way agent-proposes pipe.

**Downstream impact:** Unblocks the several P0/P1 decisions that gate MS-1/MS-3; process-only.

### GAP-10 — WH deferred-capability table inconsistencies

**Priority:** Low · **Disposition:** doc-fix · **Related OQ:** OQ-009 · **Report:** —

**Recommendation:** Replace subjective revisit triggers (WH-001 'proven', WH-003 'mature', WH-007 'substantially complete') with checkable conditions and add the hidden dependencies (WH-005 on frontmatter emission via OQ-009/WH-004; WH-006 on the §8.6/C.1 external-service approval gate) to the Revisit-When column.

**Downstream impact:** Makes §2.3 revisit triggers mechanically checkable so a deferred capability cannot be judged ready without its prerequisites; documentation-only.

### GAP-17 — IR-005 flag behaviors undefined / criterion not testable

**Priority:** Low · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Define --quiet (suppress console noise only, never the machine-readable report), --verbose (log level plus per-file lines), and their combination; align with the logging decision (GAP-19) so the file sink stays at DEBUG regardless of console flags.

**Downstream impact:** Makes IR-005's 'flag behavior covered by CLI tests' judgeable; couples to the logging library OQ and CLI tests.

### GAP-21 — Console/human-readable summary format undefined

**Priority:** Low · **Disposition:** spec-change · **Related OQ:** OQ-004 · **Report:** —

**Recommendation:** Define the Rich console summary (aggregate counts, colorized skip/error breakdown, optional per-file table) and how it varies by --verbose/default/--quiet; DR-003 covers only the JSON shape.

**Downstream impact:** Specifies the primary triage surface for a solo owner (§20); couples to GAP-17/GAP-19 and MS-3 readable-summary promise.

### GAP-37 — Tool-written backup file/dir permissions unaddressed for confidential data

**Priority:** Low · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Mandate restrictive permissions (e.g. 0600 files / 0700 dir) on tool-written backups and the backup dir rather than inheriting ambient umask; §8.1 currently covers permission preservation only for the replacement output.

**Downstream impact:** Prevents world-readable confidential backups (§13.4 letters/journals/financial) on multi-user POSIX hosts; small writer-layer change.

### GAP-41 — fsync/atomic-replace guarantees unbounded across filesystems

**Priority:** Low · **Disposition:** research-only · **Related OQ:** — · **Report:** [`atomic-write-filesystem-semantics.md`](research/atomic-write-filesystem-semantics.md)

**Recommendation:** Keep D-004/NFR-002 pre-rename fsync exactly as specified (load-bearing on ext4/XFS, not overkill) and make the rationale explicit in §8.3; add /proc/mounts-based filesystem-type detection with a durability classification (strong/weak_network/volatile/union/unknown) threaded into artifacts, hard-refuse tmpfs/ramfs targets, add a case-sensitivity probe feeding FR-011 collision detection, and validate NFR-002's kill-during-write test on ext4+tmpfs (Must) with loopback btrfs/XFS/overlayfs (Should).

**Downstream impact:** Makes the atomicity/idempotency guarantees testable against concrete filesystems and prevents plan/apply divergence on case-insensitive destinations; adds a scan-layer detector, durability artifact fields (OQ-004), a gate refusal, and a CI matrix.

### GAP-48 — Missing edge case for already-empty (zero-byte) source files

**Priority:** Low · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Add an EC row defining behavior for a zero-byte source at scan time (recommended: trivial successful extension rename, no content transform), distinct from EC-005 output shrinkage.

**Downstream impact:** Defines a plausible real occurrence in a 100k+ library; adds an EC row and a classification branch.

### GAP-54 — 100k-file scale test has no defined CI placement or execution budget

**Priority:** Low · **Disposition:** spec-change · **Related OQ:** OQ-010 · **Report:** [`batch-throughput-and-capacity.md`](research/batch-throughput-and-capacity.md)

**Recommendation:** Keep a cheap memory-independence assertion in the default check.yml gate but move the full 100k-file scale run to a separate workflow_dispatch + scheduled job, and register a slow/scale pytest marker (none exist despite --strict-markers) so an opt-out exists.

**Downstream impact:** Prevents the scale test from making ordinary CI impractical or being silently omitted; adds a marker registration and a second workflow. MS-5.

### GAP-57 — Controlled vocabularies (OQ-007) have no extensibility mechanism once frozen

**Priority:** Low · **Disposition:** update-existing-oq · **Related OQ:** OQ-007 · **Report:** —

**Recommendation:** In OQ-007, define whether 'other' is a permanent safety valve or a signal to revise the schema, and add an extension policy (additive enum value = MINOR schema bump per the versioning policy GAP-29) so a new value doesn't force a breaking migration.

**Downstream impact:** A decades-heterogeneous corpus will overflow first-guess enums; ties OQ-007 to the schema-versioning policy (GAP-29) and shapes the frontmatter schema.

### GAP-60 — §8.6 runtime deps not in pyproject; no tracked MS-0 task; 3.14 wheel readiness unrecorded

**Priority:** Low · **Disposition:** doc-fix · **Related OQ:** — · **Report:** [`python-314-wheel-readiness.md`](research/python-314-wheel-readiness.md)

**Recommendation:** Add an explicit TODO/MS-0 task to `uv add` the §8.6 runtime deps (typer, charset-normalizer, pathspec, rich, jsonschema), record that all ship Python 3.14 wheels today (verified via PyPI JSON API), add a CI pre-flight failing the build if any approved-set resolution would need a source build (rpds-py/charset-normalizer), and document lockfile discipline (pin vs range, license/CVE review on new deps) in conventions.md.

**Downstream impact:** Closes the 'allowed vs pinned' gap with a checklist owner and a recorded 3.14 baseline; adds a TODO task, a CI pre-flight step, and a conventions entry.

### GAP-64 — §20 'Operational usability' success metric is not independently measurable

**Priority:** Low · **Disposition:** spec-change · **Related OQ:** — · **Report:** —

**Recommendation:** Replace the subjective self-referential 'owner triages the skip pile using reports only' with a numeric bound (e.g. % of skip reasons resolvable without opening a file), like every other §20 row.

**Downstream impact:** Makes the success criterion objectively evaluable under ISO/IEC/IEEE 29148; documentation-only.

### GAP-68 — docs/prompt.md points research output at a nonexistent docs/research-reports/

**Priority:** Low · **Disposition:** doc-fix · **Related OQ:** — · **Report:** —

**Recommendation:** Change prompt.md (lines 12, 22) from docs/research-reports/ to the actual docs/research/ directory to match existing reports and deep-research-queue references.

**Downstream impact:** Prevents fragmenting research output into a second inconsistent location for exactly this class of workflow; documentation-only.

### GAP-69 — README.md is a 3-line stub

**Priority:** Low · **Disposition:** doc-fix · **Related OQ:** — · **Report:** —

**Recommendation:** Expand README with project status (pre-implementation), links to docs/specs/docmend.md and the open-questions backlog, and a brief safety-model note (dry-run default, backups) per the §18.7 DoD.

**Downstream impact:** Gives a public-repo visitor basic orientation and project-status signal; documentation-only.

### GAP-71 — No console entry point wired; MS-0 overstates it as 'largely present'

**Priority:** Low · **Disposition:** doc-fix · **Related OQ:** — · **Report:** —

**Recommendation:** Reword §19 MS-0 item 1 to reflect that the CLI entry point is outstanding (no [project.scripts], no cli.py; only `__init__`.py and py.typed exist), as TODO.md already correctly tracks.

**Downstream impact:** Corrects a misleading milestone claim; documentation-only (the actual entry-point wiring is a separate MS-0 implementation task).

## Documentation and drift fix checklist

Actionable documentation/consistency fixes that need no external research. Several touch the CLI-managed spec (`docs/specs/docmend.md`) — author those via the `project-standards spec` CLI (conventions #3), not by hand.

| Priority | Fix | Files |
| --- | --- | --- |
| High | Add OQ-012/013/014 rows to spec §21 and cross-reference them in the spec body | docs/specs/docmend.md (§21, §9, §8.1/§8.2.2, §13.5, §18.2, Appendix A ID index, Revision History) |
| High | Correct 'three blocking OQs' to four across handoff/status/TODO and add OQ-012 | docs/handoff/state.md, docs/handoff/architecture.md, STATUS.md, TODO.md |
| High | Reconcile blocking flags (OQ-003/006/009) and define the P0/P1/P2 priority legend | docs/open-questions.md (Important Notes, OQ-003/006/009), docs/specs/docmend.md (§21, Appendix A) |
| Medium | Resolve OQ backlog sequencing and apply maintenance-rule-3 splits | docs/open-questions.md (OQ-002, OQ-004, OQ-005), docs/resolved-questions.md |
| Medium | Fix stale docs/handoff.md pointers post-migration | docs/specs/docmend.md (§18.7 ~line 805, Appendix B.4 ~line 1016), docs/open-questions.md (rule 6, ~line 475) |
| Medium | Fix ADR-0001 broken links to the removed spec draft | docs/decisions/adr-0001-no-markdown-frontmatter-standard.md |
| Medium | Flag §9 frontmatter example as gated on OQ-013 and note the missing schema file | docs/specs/docmend.md (§9), docs/open-questions.md (OQ-013) |
| Medium | Resolve architecture diagram vs in-place output contradiction | docs/specs/docmend.md (§8.2.2, §18.2) |
| Low | Fix WH deferred-capability table inconsistencies | docs/specs/docmend.md (§2.3 WH-001/003/005/006/007, Appendix C) |
| Low | Correct MS-0 'CLI entry point largely present' overstatement | docs/specs/docmend.md (§19 MS-0) |
| Low | Record dependency-addition tracking and lockfile discipline for MS-0 | TODO.md, docs/handoff/conventions.md |
| Low | Correct docs/prompt.md research-output path | docs/prompt.md |
| Low | Expand README.md from a 3-line stub | README.md |
| Low | Establish an owner decision cadence for open questions | TODO.md, docs/resolved-questions.md |

- **[High] Add OQ-012/013/014 rows to spec §21 and cross-reference them in the spec body** — Extend the §21 Open Questions table (stops at OQ-011) with OQ-012 (in-place vs separate output root, P0), OQ-013 (frontmatter null/omitted/status), and OQ-014 (real-write opt-in), and add inline pointers where they apply (OQ-012 at §8.1/§8.2.2/§13.5/§18.2, OQ-013 at §9, OQ-014 at FR-004/IR-003). Update the Revision History, the Appendix A ID index, and the §21 'nothing silently dropped' claim. Highest-priority fix: a P0 write-path blocker is currently invisible to the Appendix B.1 per-session re-read.
- **[High] Correct 'three blocking OQs' to four across handoff/status/TODO and add OQ-012** — state.md, architecture.md, STATUS.md, and TODO.md all say three OQs (OQ-001/004/005) block milestones; add OQ-012 as a fourth P0 blocker gating MS-3 write-path work.
- **[High] Reconcile blocking flags (OQ-003/006/009) and define the P0/P1/P2 priority legend** — Spec §21 marks OQ-003/006/009 Blocking=No while open-questions.md calls them P1 near-blockers. Align the §21 column with the backlog (or document why they differ) and add a legend defining P0/P1/P2 and their mapping to §21's binary Blocking column in open-questions.md Important Notes, referenced from spec Appendix A.
- **[Medium] Resolve OQ backlog sequencing and apply maintenance-rule-3 splits** — Document/fix that OQ-004 (MS-1) depends on OQ-002/003/012 scheduled at or after its own deadline; split OQ-005's preservation-semantics fork out as a pre-MS-1 item; move OQ-002's settled sub-questions (WH-001 extension rename, FR-010/011 collision policy) to resolved-questions.md; add a note that OQ-004's Pydantic suggestion requires its own §8.6 approval OQ.
- **[Medium] Fix stale docs/handoff.md pointers post-migration** — Update the spec's §18.7 checklist and Appendix B.4 session-handoff clause, plus open-questions.md maintenance rule 6, to reference the docs/handoff/ directory layout instead of the retired single-file docs/handoff.md.
- **[Medium] Fix ADR-0001 broken links to the removed spec draft** — docs/specs/docmend-spec-draft.md no longer exists; update adr-0001's frontmatter related: list (line 21) and body link (line 45) to point at the canonical docs/specs/docmend.md.
- **[Medium] Flag §9 frontmatter example as gated on OQ-013 and note the missing schema file** — §9's worked example uses a null-heavy convention (author/date/description: null) that contradicts OQ-013's omit-by-default recommendation; add a note that the example and schemas/frontmatter.schema.json (DR-005, confirmed missing) must be produced/rewritten once OQ-009 emission scope and OQ-013 resolve.
- **[Medium] Resolve architecture diagram vs in-place output contradiction** — §8.2.2's Mermaid diagram shows a distinct 'Converted library' output node contradicting OQ-012's in-place recommendation and the absent write.output_root in §18.2; reconcile the normative diagram and text as part of the OQ-012 decision.
- **[Low] Fix WH deferred-capability table inconsistencies** — Replace subjective revisit triggers (WH-001 'proven', WH-003 'mature', WH-007 'substantially complete') with checkable conditions; add WH-005's hidden dependency on frontmatter emission (C.3 rung 6, gated by OQ-009/WH-004) and WH-006's dependency on the §8.6/C.1 external-service approval gate to their Revisit-When columns.
- **[Low] Correct MS-0 'CLI entry point largely present' overstatement** — §19 MS-0 item 1 describes the docmend CLI entry point as '(largely present)', but no [project.scripts] and no cli.py exist (only `__init__`.py and py.typed); reword to reflect that the entry point is still outstanding, as TODO.md already tracks.
- **[Low] Record dependency-addition tracking and lockfile discipline for MS-0** — Add an explicit tracked task to `uv add` the §8.6 runtime deps (typer, charset-normalizer, pathspec, rich, jsonschema) and document lockfile discipline (pin vs range, license/CVE review on new deps) for when runtime deps land; note that a scratch resolve succeeds under CPython 3.14.6 and all ship 3.14 wheels.
- **[Low] Correct docs/prompt.md research-output path** — prompt.md (lines 12, 22) points research output at the nonexistent docs/research-reports/; change to the actual docs/research/ directory to match existing reports and deep-research-queue references.
- **[Low] Expand README.md from a 3-line stub** — Add project status (pre-implementation), links to docs/specs/docmend.md and the open-questions backlog, and a brief safety-model note (dry-run default, backups) per the §18.7 DoD.
- **[Low] Establish an owner decision cadence for open questions** — resolved-questions.md is empty while 14 OQs carry agent recommendations with empty owner blocks; add a tracked owner-review task/cadence (in TODO.md or handoff) so P0/P1 blockers get closed rather than sitting in a one-way agent-proposes pipe.

## Deep-research candidates

Four residual questions warranted a heavier ChatGPT Deep-Research pass. The filled prompts live in [`deep-research-queue.md`](deep-research-queue.md).

1. **Empirical non-ASCII-byte-count skip-floor for encoding detection on a legacy .txt/.html corpus** — OQ-001 (encoding v1 boundary) and proposed OQ-015 (encoding detector/thresholds); docs/research/encoding-detection-benchmark.md; spec FR-007, §18.2
2. **CPython free-threading (Phase III / default-build) timeline and re-open criteria for the concurrency choice** — OQ-010 (performance) and proposed OQ-016 (concurrency primitive); docs/research/python-314-concurrency-model.md; spec NFR-001, §14
3. **Real-hardware throughput and capacity validation on the actual OQ-008 backup medium** — OQ-010 (performance targets), OQ-008 (preservation posture); docs/research/batch-throughput-and-capacity.md; spec NFR-001, §14, §18.6
4. **Document-content exposure policy for a headless batch tool's semantic-review artifacts** — WH-002/WH-005, NG-001, §11, §13.4/§13.5; proposed future review-workflow OQ; docs/research/batch-curation-review-workflow.md

## Research reports produced

22 reports written to [`research/`](research/) this pass:

| Report | Topic |
| --- | --- |
| [`encoding-detection-benchmark.md`](research/encoding-detection-benchmark.md) | Encoding detection at corpus scale: detector choice, confidence semantics, threshold |
| [`python-314-concurrency-model.md`](research/python-314-concurrency-model.md) | Concurrency model for a CPU-bound file pipeline on Python 3.14 |
| [`python-314-wheel-readiness.md`](research/python-314-wheel-readiness.md) | Python 3.14 wheel readiness for the approved dependency set |
| [`append-safe-manifest-format.md`](research/append-safe-manifest-format.md) | Crash-safe, append-safe on-disk manifest representation |
| [`atomic-write-filesystem-semantics.md`](research/atomic-write-filesystem-semantics.md) | Atomic-replace and directory-fsync guarantees across filesystems |
| [`path-containment-toctou.md`](research/path-containment-toctou.md) | Path-containment algorithm and TOCTOU symlink-race mitigation |
| [`stable-document-id-scheme.md`](research/stable-document-id-scheme.md) | Stable document ID scheme surviving renames and full rewrites |
| [`json-schema-versioning-migration.md`](research/json-schema-versioning-migration.md) | JSON Schema versioning and migration policy |
| [`json-schema-validator-library.md`](research/json-schema-validator-library.md) | JSON Schema validator library selection at scale |
| [`unicode-normalization-policy.md`](research/unicode-normalization-policy.md) | Unicode normalization-form policy for content and filenames |
| [`structured-logging-library.md`](research/structured-logging-library.md) | Structured logging library and format for a long-running batch CLI |
| [`batch-throughput-and-capacity.md`](research/batch-throughput-and-capacity.md) | Throughput, memory, disk-overhead, and progress-reporting budget for a 100k-file pass |
| [`synthetic-corpus-generation.md`](research/synthetic-corpus-generation.md) | Synthetic corpus generation and public-safe anonymization of real anomalies |
| [`property-based-testing-hypothesis.md`](research/property-based-testing-hypothesis.md) | Property-based testing library for transform purity and edge cases |
| [`architecture-and-traceability-enforcement.md`](research/architecture-and-traceability-enforcement.md) | Mechanical enforcement of architecture invariants and requirement traceability |
| [`license-compliance-tooling.md`](research/license-compliance-tooling.md) | Dependency license-scanning tooling and policy for a uv/PEP 621 project |
| [`batch-curation-review-workflow.md`](research/batch-curation-review-workflow.md) | Report-driven review workflow for a headless batch curation tool |
| [`per-file-watchdog-timeout.md`](research/per-file-watchdog-timeout.md) | Per-file watchdog/timeout for pathological inputs in a batch pipeline |
| [`combinatorial-safety-gate-testing.md`](research/combinatorial-safety-gate-testing.md) | Combinatorial testing strategy for the multi-check safety gate |
| [`restore-from-manifest-design.md`](research/restore-from-manifest-design.md) | Restore-from-manifest tooling and drill design |
| [`safe-yaml-loading.md`](research/safe-yaml-loading.md) | Safe YAML loading and hardening for parsing legacy frontmatter |
| [`backup-integrity-verification.md`](research/backup-integrity-verification.md) | Backup integrity verification and preservation-strategy proof |

## New open questions raised

Six gaps were genuine undecided decisions and became open questions (full agent notes in [`open-questions.md`](open-questions.md)):

- **OQ-015** — encoding detector, confidence signal, and dual skip thresholds (High, blocking, needed by MS-2)
- **OQ-016** — CPU-bound concurrency primitive for the Python 3.14 target (High, non-blocking, needed by MS-3)
- **OQ-017** — structured logging library, format, and verbosity mapping (High, non-blocking, needed by MS-0)
- **OQ-018** — JSON Schema validator library selection (Medium, blocking, needed by MS-1)
- **OQ-019** — property-based testing dependency (Hypothesis) approval (Medium, non-blocking, needed by MS-1)
- **OQ-020** — generic-tool genericity vs purpose-built personal taxonomy (Medium, non-blocking, needed by MS-1)

## Methodology and provenance

- **Discovery:** 12 parallel Sonnet reviewers, one lens each (functional surface, architecture/resume, data-model/artifacts, safety/preservation, encoding, testing, documentation-drift, ops/scale/perf, tooling/packaging, existing-OQ review, scope/vision, requirements-quality).
- **Consolidation:** one Opus pass deduplicated 104 raw findings into 71 canonical gaps and derived 22 research topics.
- **Research:** 22 Sonnet `qdev-researcher` agents (live web + Context7), one report each.
- **Synthesis:** one Opus pass produced the recommendations, downstream-impact analysis, priorities, and deep-research prompts.

**Consolidation caveat (verbatim):** Consolidated 104 raw findings into 71 canonical gaps. Verified the headline drift directly: `grep` confirms docs/specs/docmend.md references only OQ-001..011 while docs/open-questions.md defines OQ-001..014; resolved-questions.md has no decisions; README is 3 lines; docs/specs/docmend-spec-draft.md is missing (ADR-0001 links it twice); no schemas/ directory; handoff.md pointers are stale in spec §18.7/Appendix B.4 and OQ maintenance rule 6; §18.2 default paths.include excludes HTML; no [project.scripts]; prompt.md points at nonexistent docs/research-reports/. Major dedup clusters: (1) The OQ-012/013/014 §21-omission finding recurred in 9 lenses — merged into GAP-01 (plus GAP-02 propagation, GAP-70 diagram facet). (2) HTML-excluded-by-default recurred in 3 lenses -> GAP-07. (3) restore-command/restore-drill recurred in ~4 findings -> GAP-33. (4) run-ID-undefined and concurrency/manifest-safety each spanned multiple lenses -> GAP-27 and GAP-22/23/24. (5) disk-space and progress/liveness each merged from 2 findings -> GAP-38, GAP-20. Disposition rationale: pure §21/handoff/ADR/prompt/README drift is doc-fix; genuinely undecided decisions with no owning OQ (logging library, concurrency primitive, encoding detector/threshold, JSON Schema validator lib, Hypothesis adoption, generic-tool scope) are new-open-question; findings that strengthen an existing OQ (OQ-001 HTML, OQ-002 id, OQ-004 run-id/granularity/symlink, OQ-005 preservation checks, OQ-006 exit codes/verify inputs, OQ-007 vocab, OQ-009 FR-016 conflict) are update-existing-oq; concrete missing FR/IR/ERR/edge-case/NFR text is spec-change; evidence-needed-but-not-owner-decision items (fsync/FS, path-containment, schema-versioning, unicode-norm, license tooling, review-workflow) are research-only. Research plan: 22 topics (at the hard cap). Coverage note — to stay within 22 I merged progress-reporting + disk-space + scale-test-CI into RT-12 (batch-throughput-and-capacity), merged transform-purity + traceability enforcement into RT-15, and merged backup-integrity + preservation-strategy-proof into RT-22; encoding detector choice, the charset-normalizer confidence-API defect, and UTF-16/NUL conflict are all folded into RT-01. Deep-research candidates flagged: RT-01 (encoding), RT-02 (3.14 concurrency), RT-12 (throughput/capacity spike), RT-17 (review-workflow precedent). None of the 22 re-runs the two existing reports (Pandoc/frontmatter; self-hosted corpus storage). Several gaps (GAP-08 generic-tool scope, GAP-11 exit codes, GAP-44 UTF-16, GAP-55 FR-016 conflict, GAP-62 usability NFRs) are decision/spec work needing no external research and carry research_topic_id 'none'. Caveat: I did not re-open every cited spec line; line-number citations are carried from the raw findings, which were internally consistent across independent lenses for the claims I spot-checked. Priorities are preliminary and inherited from the raw findings, adjusted only where dedup changed scope.

## Addendum — `python-library-research.md` reconciliation (2026-07-05)

A separate owner-authored ChatGPT Deep-Research report, [`research/python-library-research.md`](research/python-library-research.md), gives a whole-stack Python dependency posture. It is a companion to the targeted per-library reports and mostly ratifies the existing open questions. Reconciliation:

- **New decisions raised:** OQ-021 (`pydantic` v2 for internal artifact/config models) and OQ-022 (frontmatter YAML codec — `ruamel.yaml` vs `PyYAML`), both added to `open-questions.md` and spec §21. Appendix B.2 requires an OQ before either dependency lands.
- **Conflict flagged:** the report recommends stdlib `logging` over `structlog`, opposite to OQ-017's recommendation; recorded as a research-update on OQ-017 for the owner to decide.
- **Confirmations:** OQ-015 (`charset-normalizer` — but its `DetectedEncoding.confidence` assumes an API 3.x lacks; use `1.0 - chaos`), OQ-018 (`jsonschema` + explicit `FormatChecker`), OQ-019 (`hypothesis`, plus `pyfakefs`/`pytest-xdist`), OQ-003/004 (NDJSON journals), OQ-016 (`concurrent.futures`), and the OQ-001 v1 boundary (keep Pandoc/HTML/perf libraries out of v1).
- **Gated spec-change:** rewrite spec §8.6 using the report's section-7 dependency table (adds `pydantic`, `ruamel.yaml`/`PyYAML`, `hypothesis`, `pyfakefs`, deferred `puremagic`; splits Runtime vs. Dev/Test) — apply only once OQ-017/018/019/021/022 are decided.
