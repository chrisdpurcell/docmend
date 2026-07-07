---
schema_version: '1.1'
id: 'adr-0006-docmend-resume-and-recovery-model'
title: 'ADR 0006: Resume and recovery model'
description: 'docmend resumes an interrupted run by reconciling the immutable plan against an append-only NDJSON manifest/journal and current filesystem hashes; atomic writes guarantee no partial-target state to reconcile, and manifest recovery follows a Redis-AOF-style torn-trailing-line rule.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-07'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'resume'
  - 'recovery'
  - 'safety'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0002-layered-pipeline-isolated-writer.md'
  - 'docs/adr/adr-0003-in-place-mutation-output-model.md'
  - 'docs/adr/adr-0005-durable-artifact-schema-contract.md'
supersedes: []
superseded_by: null
source: []
confidence: 'high'
visibility: 'public'
license: null
project:
  decision_makers:
    - 'chrisdpurcell'
  consulted: []
  informed: []
---

# Resume and recovery model

## Context and Problem Statement

docmend runs unattended over 100,000+ files (G-003) and must survive interruption — crash, kill, power loss — then resume without redoing completed work or corrupting it (FR-013). What durable state does resume rely on, and how does it decide, per file, whether to skip, continue, or fail?

## Decision Drivers

- Resume must know what **actually completed**, not merely what was planned.
- The record of completed work must survive a crash — written **incrementally and durably**, never only at the end.
- There must be no partial-write state to reconcile (depends on atomic writes, ADR-0003 / NFR-002).
- Reconciliation must be deterministic and **fail safe** on a corrupted record rather than guessing past it.

## Considered Options

- **Combined model:** immutable plan + append-only journal/manifest, reconciled against current filesystem hashes.
- **Plan-file-only resume:** re-derive progress from the plan alone.
- **Final-only manifest:** write the completion record at the end of the run.

## Decision Outcome

Chosen option: **"Combined model."** The plan is the immutable intent record (per-file source hashes + config snapshot, ADR-0002). `apply` writes an append-only journal/report plus incremental manifest entries — NDJSON, one `fsync`'d record per mutation (ADR-0005). On resume, docmend reconciles plan actions against completed manifest/report entries **and** current filesystem hashes, then decides per file: **skip** (already done, hashes match), **continue** (not started), or **fail** (hash mismatch, ERR-002). Because writes are atomic (ADR-0003), a crash leaves only "completed", "not started", or "failed before mutation" — never a partial target. Manifest reconciliation follows a **Redis-AOF-style rule**: discard only a torn **trailing** line; **hard-abort** on any non-trailing parse failure (a corrupt interior record is a defect, not something to skip past).

### Consequences

- Good, because resume has enough durable state to avoid both redoing work and guessing; the plan/manifest/hash triangulation also catches drift (source changed since the plan was made).
- Good, because one-`fsync`'d-record-per-mutation NDJSON means a crash loses at most the last unflushed record, and that torn trailing line is recoverable.
- Bad, because the reconciliation logic and AOF-style torn-line handling are nontrivial and must be tested against injected-crash fixtures.
- Bad, because resume correctness depends on ADR-0003 (atomic writes) and ADR-0005 (durable NDJSON manifest) holding — it is not self-contained.

### Confirmation

Confirmed by: kill-and-resume tests that crash at each pipeline stage and prove no file is redone or corrupted; a fixture with a torn trailing manifest line that resumes cleanly; a fixture with a corrupt **interior** manifest line that hard-aborts; and a changed-source fixture that surfaces ERR-002 on resume rather than silently proceeding.

## More Information

- **Amendment (2026-07-07, cross-repo alignment review):** the "never a partial target" invariant holds per WRITE, but `rename_and_rewrite` is a multi-step action (publish target, unlink source, record) — a hard kill inside that window used to leave a mutated corpus with no manifest evidence, degrading resume to indirect signals (stale-hash/unreadable skips). Manifest schema 1.3 closes this with a **write-ahead intent record** (`result: "intent"`, carrying the expected after-hash and, under overwrite, the clobbered target's hash) appended and fsync'd before the first mutation step. On resume, a **dangling** intent (no later applied/failed record for its action) is reconciled from disk state: target matches the expected after-hash → complete the unlink if pending and append the applied record the interrupted run never wrote (the union of manifests stays the complete restore evidence); target missing or still holding the recorded pre-overwrite bytes → the publish never happened, execute normally; anything else → ERR-002. Restore replays and verify reconciles only `result == "applied"` records, so intents are inert to both. Single-step actions stay one-record.
- Spec: §7.1 FR-013, §12.2/§12.3, NFR-002; D-004 (atomic replace).
- Research: `append-safe-manifest-format`.
- Decision owner: implementer (RQ-003). Relates to ADR-0002 (plan as immutable intent record), ADR-0003 (atomic writes make partial state impossible), ADR-0005 (the NDJSON manifest resume reads).
- Revisit if a non-atomic write path or a non-POSIX filesystem is ever supported (either would break the "no partial target" invariant this model rests on).
