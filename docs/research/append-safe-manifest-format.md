---
schema_version: '1.0'
id: append-safe-manifest-format
title: 'Crash-Safe, Append-Safe On-Disk Manifest Representation'
description: 'NDJSON vs WAL vs single-JSON+atomic-rewrite for the DR-004 reversible mutation manifest, reconciled with IR-007 and per-run/cumulative granularity.'
doc_type: research
status: active
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'Chris Purcell'
tags:
  - manifest
  - crash-safety
  - ndjson
  - write-ahead-log
  - durability
  - json
aliases:
  - manifest format research
  - append-safe manifest
  - GAP-24
  - GAP-30
related: []
source:
  - 'https://jsonlines.org'
  - 'https://datatracker.ietf.org/doc/html/rfc7464'
  - 'https://sqlite.org/wal.html'
  - 'https://docs.python.org/3/library/os.html#os.replace'
confidence: high
visibility: public
license: null
---

# Crash-Safe, Append-Safe On-Disk Manifest Representation

**Date:** 2026-07-05

**Related:** SPEC-VHHB §7.3 IR-007, §7.4 DR-004, §7.2 NFR-002, §12.2, §12.3, §18.6; `docs/open-questions.md` OQ-003 (resume model), OQ-004 (artifact JSON Schemas), OQ-005 (safety-gate/preservation semantics); GAP-24, GAP-30.

**Gap it fills:** The spec already commits to an incremental, never-only-at-the-end manifest (§12.3) and to JSON as the artifact format (IR-007), but it never reconciles those two commitments: a classic single-JSON-document artifact cannot be safely appended to record-by-record without either an unbounded per-mutation rewrite cost or a durability gap between rewrites, and neither OQ-003 nor OQ-004 currently name a concrete on-disk representation, a torn-write recovery rule, or a per-run-vs-cumulative granularity model for DR-004. This report closes that gap with an evidence-backed format choice, a concrete IR-007 reconciliation, and a granularity recommendation for multi-run restore.

## Executive Summary

**Recommendation: NDJSON (JSON Lines), one file per apply run, one record per completed mutation, fsync'd after every append; IR-007 reworded to scope "JSON" per-artifact rather than as a single-document requirement; a small, regenerable cumulative index derived from the per-run files for fast multi-run lookups.**

- **NDJSON wins on append-safety and crash-recovery** because each record becomes durable (or is cleanly discardable) independently of every other record — there is no rewrite window in which a completed mutation can vanish from the manifest, and a truncated tail is mechanically distinguishable from a corrupted body (§"Comparison"). [official](https://jsonlines.org)
- **A single JSON document with periodic atomic rewrites is unsafe as the _primary_ manifest mechanism** for this project: between rewrites, mutations that already completed on disk have no manifest record at all, which directly violates FR-006 ("shall always record a reversible manifest entry... for every mutation") and the RPO stated in §18.6 ("zero for original content"). It remains the right mechanism for DR-001–DR-003 (inventory/plan/report), which are computed once and written once per run.
- **A dedicated WAL engine (SQLite WAL, a custom binary log) is unnecessary and works against §9's "docmend has no database" framing and IR-007's JSON contract.** NDJSON _is_ the write-ahead log here — it is the simplest member of the append-only-log family that still satisfies "JSON," and 100k mutation records at a few hundred bytes each is tens of megabytes, far below the scale where a real WAL engine's concurrency/checkpoint machinery earns its complexity. [official](https://sqlite.org/wal.html)
- **IR-007 needs a one-line reconciliation, not a redesign:** JSON Lines is explicitly _not_ a single valid JSON document (you cannot wrap a `.jsonl` file in `[` `]` and parse it) — this is stated on the format's own reference pages, not an implementation detail. [official](https://ndjson.com/definition) IR-007 should be reworded from "as JSON" to "as JSON per the shape defined for each artifact in §9 (DR-001–DR-003: one JSON document; DR-004: JSON Lines, one JSON-Schema-valid object per line)," which is a documentation fix, not a scope change.
- **Granularity: per-run files for the ledger, a cumulative derived index for lookup.** One manifest file per apply run keeps each file's torn-tail-recovery blast radius to that run only and mirrors the run-scoped identity model already in §9 ("run (timestamp + source root)"). A small, regenerable "latest state per path" index — rebuildable at any time from the immutable per-run files — gives cheap answers to "what happened to this file across every run" without re-scanning history or, worse, appending forever to one ever-growing file. This mirrors how SQLite splits WAL (source of truth for recent changes) from the checkpointed main database (a rebuildable summary), and how PostgreSQL's incremental `backup_manifest` chains point back to prior generations rather than storing one flat ledger. [official](https://sqlite.org/wal.html) [official](https://sqlbak.com/blog/incremental-postgresql-backup-step-by-step-guide/)

## Comparison: NDJSON vs Single-JSON+Atomic-Rewrite vs WAL

| Property | NDJSON / JSONL (append) | Single JSON doc + periodic atomic rewrite | Dedicated WAL engine (e.g. SQLite WAL) |
| --- | --- | --- | --- |
| Append cost | O(1) per record — write the new line, no read-back | O(n) per rewrite (read + serialize + write the whole document) — the manifest is exactly the workload this footgun is documented against | O(1) per record (that's the point of a WAL) |
| Durability gap | None: each record is fsync'd as it lands | Real gap: everything mutated since the last periodic rewrite has zero manifest record if the process dies before the next rewrite | None, by design |
| Crash symptom | At most one incomplete trailing line; everything before it is intact and independently parseable | Either the old complete document (safe, but stale/missing recent entries) or, if the atomic-rewrite discipline is skipped even once, a torn document | WAL replay on next open; well-understood but adds recovery-on-open logic and extra files (`-wal`, `-shm`) |
| "Is it JSON" per IR-007 | Not a single JSON document (explicitly, per spec) — needs IR-007 wording fix | Yes, unmodified | No — a `.db` file is not JSON in any sense; conflicts with IR-007 outright |
| Tooling / stdlib fit | Trivial with stdlib `json` + line iteration; one third-party convenience library exists (`jsonlines`) | Trivial with stdlib `json` | Needs `sqlite3` (stdlib) but adds a real embedded database as a durable artifact, which conflicts with §9 ("no database") |
| Fits docmend's existing pattern | Yes — it's the natural extension of the "manifest is written incrementally, never only at the end" line already in §12.3 | No — contradicts that line unless rewrites happen after _every_ mutation, which degenerates into the pathological O(n²) case | Overkill for a single-writer, single-machine, ≤100k-line ledger |

**Sources:** JSON Lines is "not a single valid JSON document" and has no wrapping array or commas between records — this is the format's own defining constraint, not an implementation detail. [official](https://jsonlines.org) [official](https://ndjson.com/definition) Appending to a JSON array "requires reading the entire file, parsing it, adding the new element, and rewriting the complete file," which is the documented O(n) cost that periodic full-document rewrite inherits; JSONL append is documented as O(1) by contrast. [community](https://jsonl.co/guide/json-vs-jsonl) [community](https://scrapfly.io/blog/posts/jsonl-vs-json) SQLite's WAL mode is the canonical "append-only log, checkpoint into a compacted store later" pattern and is explicitly a roll-forward journal of committed-but-not-yet-applied changes. [official](https://sqlite.org/wal.html)

## Recommendation, Reconciled with IR-007

1. **Keep DR-001 (inventory), DR-002 (plan), DR-003 (report) as single JSON documents**, written via the existing atomic-replace discipline (temp file in the same directory, `fsync`, `os.replace`, `fsync` parent directory where practical) that §8.1/D-004/NFR-002 already mandate for converted files. These artifacts are computed once and written once (or, for the report, accumulated in memory during a run and flushed at the end) — they have no per-mutation append requirement, so the single-document-plus-atomic-rewrite pattern is exactly right for them and needs no change. `os.replace()` is documented as atomic when it succeeds on the same filesystem; `python-atomicwrites`-style temp-then-rename-then-fsync is the standard implementation of that guarantee. [official](https://docs.python.org/3/library/os.html#os.replace) [community](https://python-atomicwrites.readthedocs.io/en/latest)
2. **Make DR-004 (the manifest) NDJSON, one JSON object per line, one file per apply run.** Each record is written with a single `write()` call whose payload never contains an embedded newline (JSON Lines forbids literal newlines inside the JSON value; escape them as `\n` inside string fields), followed immediately by `flush()` **and** `os.fsync(fd)` before the mutation is considered "recorded" for FR-006/§12.3 purposes. `flush()` alone only empties the Python-level buffer into the OS page cache; it does not survive an OS crash or power loss, only a process crash — matching the §18.6 RPO of "zero loss of original content" requires the `fsync`, not just the `flush`. [community](https://zetcode.com/python/os-fsync/)
3. **Reword IR-007** from "The system shall read and write its durable artifacts (inventory, plan, report, manifest) as JSON" to something like: _"...as JSON: inventory, plan, and report are single JSON documents; the manifest is JSON Lines (NDJSON) — one independently JSON-Schema-valid object per line, newline-delimited, no enclosing array."_ This is the minimal wording change that keeps IR-007 honest without touching FR-006, NFR-002, or the manifest's actual field shapes; fold it into OQ-004's manifest-schema work, since OQ-004 already owns "exact JSON Schemas... for... manifest."
4. **Treat OQ-004's `manifest.schema.json` as a per-record schema**, validated against each line independently (Draft 2020-12, `additionalProperties: false`, as OQ-004's agent notes already propose) — not as a schema for "the manifest file as a whole," which is the subtle reframing IR-007's fix requires downstream in the schema work.
5. **Torn-tail recovery rule for `verify` and resume (OQ-003/OQ-006):** on open, parse the manifest file line-by-line. If every line parses and schema-validates, the manifest is clean. If exactly the **last** line fails to parse (JSON syntax error or schema violation) and every earlier line is valid, treat that line as a partial write from an interrupted run: discard it, treat the mutation it would have recorded as **not completed** for resume purposes (the underlying file write is already known-atomic per NFR-002, so "manifest record missing" cannot mean "file half-written" — it can only mean "was this specific mutation attempted at all," which resume re-derives from current filesystem state and the plan's source hashes). If a **non-trailing** line fails to parse, that is not a crash artifact — it is a corruption or bug, and should abort with a hard error rather than be silently discarded, matching the project's "skip-and-report, never guess" posture (FR-015's spirit applied to its own audit trail). This mirrors the exact distinction Redis draws in AOF recovery between truncation ("safe to fix," discard the trailing partial command) and corruption ("unsafe," requires manual intervention). [official](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence) [community](https://oneuptime.com/blog/post/2026-03-31-redis-how-to-troubleshoot-redis-aof-file-corruption/view)
6. **Defensive duplicate-key rejection on manifest read**, mirroring the discipline C-006/FR-016 already mandate for YAML frontmatter: JSON itself only says object names "SHOULD" be unique and explicitly calls the behavior of duplicate names "unpredictable" when parsers disagree (RFC 8259 §4; the stricter I-JSON profile in RFC 7493 forbids them outright). Because the manifest is machine-generated and never hand-edited, this is a lower-probability risk than the frontmatter case, but it is a near-zero-cost guard: Python's `json.loads(line, object_pairs_hook=...)` sees the raw list of (key, value) pairs before they collapse into a `dict`, so a duplicate can be detected and rejected at parse time rather than silently keeping "last value wins." Recommend applying this in `verify`, not necessarily on every read during a hot apply loop. [official](https://datatracker.ietf.org/doc/html/rfc8259) [community](https://alexwlchan.net/2025/duplicate-names-in-json)
7. **Single-writer discipline for the manifest file**, independent of any parallelism NFR-001 eventually adds. POSIX `O_APPEND` does make concurrent small writes from multiple processes/threads land without interleaving on local (non-NFS) filesystems, but relying on multi-writer `O_APPEND` for a durability-critical, schema-validated ledger is fragile in practice: fsync ordering across independent writers is not itself synchronized, and Python's buffered file objects add a layer that must be explicitly flushed before the OS-level append semantics even apply. Route every manifest append through one owning component (the existing "Writer layer," §8.1 point 4) even if transform work is parallelized elsewhere — this also keeps the manifest a strict record of "what the writer actually did," which is the property that makes it trustworthy. This becomes more important, not less, under Python 3.14's officially supported free-threaded build: without the GIL's incidental serialization, naive concurrent appends from multiple threads lose a safety net that used to exist by accident. [community](https://nullprogram.com/blog/2016/08/03/) [community](https://unix.stackexchange.com/questions/12942915/understanding-concurrent-file-writes-from-multiple-processes)

## Per-Run-File vs Cumulative-Ledger Granularity

Two independent design axes were conflated in the research question and are worth separating explicitly:

- **Axis 1 — how often does a _new_ manifest file start?** Recommend **one NDJSON file per apply run** (e.g., `manifest-<run_id>.jsonl`, where `run_id` matches the timestamp+source-root natural key §9 already defines). This bounds the "how far back must torn-tail recovery look" question to the most recent run, keeps each file's size proportional to that run's own mutation count rather than the corpus's entire history, and matches FR-018/DR-003's existing per-run reporting model — the manifest becoming per-run too is the consistent choice, not a new precedent.
- **Axis 2 — how does a restore spanning _multiple_ runs find "what happened to this file, most recently"?** Do **not** answer this by making the append-only ledger itself span multiple runs (that reintroduces an ever-growing single file with no natural checkpoint boundary and makes "resume run N" ambiguous about which tail belongs to which run). Instead, maintain a small **derived, regenerable index** — one entry per still-relevant source path, pointing at `(run_id, manifest file, line/offset)` of its most recent manifest record — refreshed as a normal single-JSON-document atomic rewrite at the _end_ of each run (safe, because it is not the durability-critical record; it is a cache that can always be rebuilt by replaying every per-run `.jsonl` file oldest-to-newest, since 100k files across a handful of runs is still small data to scan). This is the same shape used by:
  - **SQLite**: the WAL file is the durable source of truth for recent changes; the main `.db` file is a checkpointed, rebuildable-from-WAL summary used for fast reads. [official](https://sqlite.org/wal.html)
  - **PostgreSQL incremental backups**: each incremental backup carries a `backup_manifest` that chains back to the prior backup's manifest rather than one flat cumulative ledger, and restoring correctly requires walking that chain in order. [official](https://sqlbak.com/blog/incremental-postgresql-backup-step-by-step-guide/)
  - **Redis**: the RDB snapshot ("preamble") plus the AOF tail is exactly "periodic compacted summary + append-only log since the summary," the same two-tier shape recommended here. [official](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence)

  Per §18.6, none of the underlying per-run `.jsonl` files are ever deleted (manifests and backups are retained until user purge) — the derived index is purely an optimization layer on top of that permanent record, never a replacement for it.

## Existing Tools

| Tool | Maintenance | Link | Fit for docmend |
| --- | --- | --- | --- |
| `jsonlines` (wbolster) | High download volume (~6.6M/month) but no new PyPI release in the last 12 months per third-party health signals — "sustainable but slow" rather than actively developed | [PyPI](https://pypi.org/project/jsonlines/) / [docs](https://jsonlines.readthedocs.io/) | Thin convenience wrapper (`Reader`/`Writer`) over stdlib `json` + line iteration. Adding it requires an OQ- per §8.6's dependency policy for a win of roughly ten lines of code; recommend hand-rolling the writer instead so the fsync-per-record discipline stays visible and under docmend's own control rather than hidden inside a third-party `.write()` call. |
| `python-atomicwrites` | Long-stable, small, POSIX temp-file+`link`/`unlink`+`fsync` implementation of the exact pattern NFR-002/D-004 already specify | [docs](https://python-atomicwrites.readthedocs.io/en/latest) | Useful reference implementation for DR-001–DR-003's single-document atomic rewrite; not needed as a dependency since the Writer layer must implement this primitive natively for converted-file writes anyway (NFR-002), so the same code can serve both. |
| SQLite (`sqlite3`, stdlib) in WAL mode | Extremely mature; native to Python's stdlib | [official docs](https://sqlite.org/wal.html) | Rejected for v1: excellent append-safety and crash-recovery machinery, but a `.db` file is not JSON (conflicts with IR-007 outright) and introduces "docmend has a database" which §9 explicitly disclaims. Worth remembering as the escape hatch if the manifest ever needs true concurrent multi-writer semantics beyond a single local process. |
| Redis AOF / `redis-check-aof` | N/A — not a dependency candidate (docmend is offline, no external services, C-002/§13.1) | [official docs](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence) | Not used directly; its truncation-vs-corruption repair distinction is the direct behavioral model this report recommends docmend's own `verify`/resume implement for the manifest tail. |

## Security and Compatibility

- **RFC 8259 leaves duplicate JSON object keys "unspecified"** — different parsers may keep the first, the last, or error; RFC 7493 (I-JSON) tightens this to forbidding duplicates outright, but ordinary JSON per RFC 8259 does not. Because the manifest is generated exclusively by docmend and never hand-edited, the practical risk is lower than the YAML-frontmatter case already flagged in C-006/FR-016, but the same "reject at parse time, don't let ambiguity reach validation" discipline is a near-free guard worth adding to `verify`. [official](https://datatracker.ietf.org/doc/html/rfc8259)
- **JSON Lines / NDJSON is a community convention (jsonlines.org, ndjson.org), not an IETF or ISO standard**, unlike JSON itself (RFC 8259) or the lesser-known **RFC 7464 "JSON Text Sequences"** (`application/json-seq`), which is a formal IETF standard using an ASCII Record Separator (0x1E) prefix plus LF suffix per record instead of bare newlines. RFC 7464 is the more "official" citation if the owner wants IR-007 to point at a numbered standard, but it has materially weaker ecosystem support in the Python/data-tooling world than the LF-delimited NDJSON convention this report recommends — no stdlib support, few libraries, essentially no tooling in the JSON-Lines-heavy corners of the ecosystem docmend would otherwise interoperate with (log shippers, `jq`, ClickHouse's `JSONEachRow`, ML dataset tooling). Recommend NDJSON for practical tooling fit, while citing this trade-off explicitly in case the owner weighs "citable standard" more heavily than "ecosystem fit." [official](https://datatracker.ietf.org/doc/html/rfc7464)
- **ext4's delayed-allocation "zero-length file" hazard** (Ted Ts'o's original writeup, corroborated independently by a Stack Exchange analysis and a filesystem comparison article) is the reason `fsync` before `rename`/before "the append is committed" is not optional on ext4's default `data=ordered` mount: without it, a crash can leave a renamed-into-place file with its _old_ (possibly empty) content, because ext4 only forces data blocks to disk before a rename/truncate commit when the kernel detects that specific pattern, not for arbitrary appends. Docmend's stated Writer algorithm (temp + fsync + `os.replace` + fsync parent dir, D-004/NFR-002) already gets this right for converted files; this report's per-record `fsync` requirement for manifest appends applies exactly the same discipline to DR-004 rather than leaving it as an unstated assumption. [official](https://lwn.net/Articles/323169) [community](https://unix.stackexchange.com/questions/297632/is-it-broken-to-replace-an-existing-file-without-fsync) [community](https://www.pointsoftware.ch/2014/02/05/linux-filesystems-part-4-ext4-vs-ext3-and-why-delayed-allocation-is-bad)
- No CVEs or security advisories were found against JSON Lines as a format or against the `jsonlines` PyPI package as of this research date.

## Recent Changes

- No changes to the JSON (RFC 8259), JSON Lines, or JSON Text Sequences (RFC 7464) specifications were found in the review window; all three are stable.
- **Python 3.14** ships free-threading as an officially supported (opt-in) build mode. This does not change any file-I/O API directly relevant to the manifest, but it raises the stakes of the single-writer-discipline recommendation above (§"Recommendation," point 7): once NFR-001's parallel/batch operation is implemented on a free-threaded interpreter, the GIL's incidental serialization of interleaved `write()` calls from multiple threads can no longer be assumed even accidentally. [official](https://docs.python.org/3/whatsnew/3.14.html)

## Open Questions

| # | Question | Why unresolved |
| --- | --- | --- |
| 1 | Exact fsync cadence for manifest appends — per-record (this report's default recommendation, matching the "zero loss" RPO) vs. batched every N records or T seconds for higher throughput on very large runs. | A throughput/durability trade-off that needs measurement against the real corpus (same category as OQ-010's performance targets), not further literature review. |
| 2 | Whether IR-007's wording fix (§"Recommendation," point 3) should be a spec text edit now or deferred until OQ-004 hardens the manifest schema. | Editorial sequencing decision for the owner, not a research question. |

## Reconciliation Notes

Fold this report's findings back into:

- **`docs/specs/docmend.md` §7.3 IR-007** — reword to scope "JSON" per-artifact (single document for DR-001–DR-003, JSON Lines for DR-004) per the "Recommendation" section above.
- **`docs/specs/docmend.md` §7.2 NFR-002 / §7.4 DR-004** — add the explicit "`fsync` after every manifest append, not just `flush`" requirement, and note the manifest's on-disk shape is JSON Lines, one file per apply run.
- **`docs/open-questions.md` OQ-003 (resume model)** — add the torn-tail discard rule (last-line-only, discard-and-treat-as-not-completed) and the single-writer/serialization guidance for manifest appends under NFR-001 parallelism.
- **`docs/open-questions.md` OQ-004 (artifact JSON Schemas)** — reframe `manifest.schema.json` as a per-record (per-line) schema rather than a whole-file schema, and record the NDJSON file-per-run convention plus the derived cumulative-index design for multi-run restore.
- **`docs/open-questions.md` OQ-005 (safety gate)** — no change required; this report does not alter what counts as a preservation strategy, only how DR-004 itself is stored.

**Housekeeping aside (not part of this research topic, but observed while reading the source files for it):** `docs/specs/docmend.md` §21's Open Questions table stops at OQ-011, while `docs/open-questions.md` defines OQ-012, OQ-013, and OQ-014 (in-place-mutation-vs-output-root, frontmatter null/omitted details, and the `--write` CLI opt-in) — these three are real open questions but are invisible to anyone reading only the spec's own §21 table. No further ID-numbering or cross-reference drift of this kind was found elsewhere in `docs/open-questions.md`, `docs/resolved-questions.md` (currently empty, as expected), or `docs/deep-research-queue.md` during this pass.

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://jsonlines.org> | JSON Lines | undated (stable) | official |
| <https://ndjson.com/definition> | JSONL Definition & Specification | 2026 | community |
| <https://datatracker.ietf.org/doc/html/rfc7464> | RFC 7464 — JSON Text Sequences | 2015 | official |
| <https://datatracker.ietf.org/doc/html/rfc8259> | RFC 8259 — The JavaScript Object Notation (JSON) Data Interchange Format | 2017 | official |
| <https://sqlite.org/wal.html> | SQLite Write-Ahead Logging | undated (stable) | official |
| <https://sqlite.org/walformat.html> | SQLite WAL-mode File Format | undated (stable) | official |
| <https://docs.python.org/3/library/os.html#os.replace> | Python `os.replace` documentation | 2026 | official |
| <https://docs.python.org/3/whatsnew/3.14.html> | What's New in Python 3.14 | 2026 | official |
| <https://redis.io/docs/latest/operate/oss_and_stack/management/persistence> | Redis persistence (RDB/AOF) | 2026 | official |
| <https://oneuptime.com/blog/post/2026-03-31-redis-how-to-troubleshoot-redis-aof-file-corruption/view> | How to Troubleshoot Redis AOF File Corruption | 2026-03-31 | blog |
| <https://sqlbak.com/blog/incremental-postgresql-backup-step-by-step-guide/> | Incremental PostgreSQL backup: step-by-step guide | 2026 | blog |
| <https://lwn.net/Articles/323169> | Ts'o: Delayed allocation and the zero-length file problem | 2009-03-13 | official (LKML-sourced) |
| <https://unix.stackexchange.com/questions/297632/is-it-broken-to-replace-an-existing-file-without-fsync> | Is it "broken" to replace an existing file without fsync()? | undated | community |
| <https://www.pointsoftware.ch/2014/02/05/linux-filesystems-part-4-ext4-vs-ext3-and-why-delayed-allocation-is-bad> | Linux Filesystems Part 4 — ext4 vs ext3 and delayed allocation | 2014-02-05 | blog |
| <https://nullprogram.com/blog/2016/08/03/> | Appending to a File from Multiple Processes | 2016-08-03 | blog |
| <https://unix.stackexchange.com/questions/12942915/understanding-concurrent-file-writes-from-multiple-processes> | Understanding concurrent file writes from multiple processes | undated | community |
| <https://alexwlchan.net/2025/duplicate-names-in-json> | Handling JSON objects with duplicate names in Python | 2025 | blog |
| <https://jsonl.co/guide/json-vs-jsonl> | JSON vs JSONL | undated | community |
| <https://scrapfly.io/blog/posts/jsonl-vs-json> | JSONL vs JSON | undated | blog |
| <https://pypi.org/project/jsonlines/> | jsonlines · PyPI | 2026 | official (project page) |
| <https://snyk.io/advisor/python/jsonlines> | jsonlines - Python Package Health Analysis | 2026 | community |
| <https://python-atomicwrites.readthedocs.io/en/latest> | python-atomicwrites documentation | undated | community |
| <https://aiopsschool.com/blog/jsonl> | What is jsonl? (failure modes table) | 2026 | blog |
