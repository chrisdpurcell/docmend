---
schema_version: '1.1'
id: 'adr-0003-docmend-in-place-mutation-output-model'
title: 'ADR 0003: In-place mutation as the v1 output model'
description: "v1 mutates files at their source location via atomic same-directory replace, backups, manifest, and path containment — not a separate output-root/copy-out tree. Clarifies that 'in-place' means same-location output via atomic replace, not naive mid-write byte overwrite."
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'writer'
  - 'safety'
  - 'output-model'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0002-layered-pipeline-isolated-writer.md'
  - 'docs/adr/adr-0004-apply-safety-gate-and-preservation.md'
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

# In-place mutation as the v1 output model

## Context and Problem Statement

The writer (ADR-0002) must put converted output _somewhere_. Two shapes are possible: mutate each file at its existing location, or write all output into a separate output-root tree while leaving the source untouched. This choice is the fundamental output model — it dictates path-containment rules, config surface, manifest paths, collision policy, and rollback semantics — so the owner flagged it (OQ-012 → RQ-013) as ADR-worthy once settled.

**Terminology note (resolves a naming collision).** "In-place" is used in two distinct senses in the spec. Design decision D-004 _rejects_ "in-place mutation (corruptible mid-write)" — meaning naively overwriting a file's bytes, which a crash can tear. This ADR's "in-place" means the _opposite implementation_: writing a temp file in the **same directory** and atomically swapping it in, so the output lands at the source **location** without any corruptible partial-write window. Same-location, not same-bytes-overwritten.

## Decision Drivers

- Simplicity and completeness of the safety model: the RQ-005 safety gate (ADR-0004) already fully specifies safe, reversible writes for the same-location case.
- Crash-safety: no partial-write state may ever exist (NFR-002).
- Reversibility should come from backups + manifest + `restore`, not from copy-out tree isolation.
- Avoid unspecified complexity: a second output tree needs path mapping, cross-tree collision policy, source-vs-output verify semantics, and distinct restore rules the spec does not describe.

## Considered Options

- **In-place mutation via atomic same-directory replace** (`os.replace()` on a same-dir temp file), with backups, manifest, and path containment (RQ-013 + D-004 mechanism).
- **Separate output-root / copy-out tree**, leaving sources untouched.
- **Naive in-place byte overwrite** (truncate-and-rewrite) — the corruptible option D-004 rejects.

## Decision Outcome

Chosen option: **"In-place mutation via atomic same-directory replace."** v1 mutates each file at its location using a same-directory temp file and `os.replace()` (atomic on POSIX), guarded by backups, the manifest, and path-containment checks. `output_root` is **not** a v1 config key; the terminology is `source_root` (scanned/planned), `target_path` (post-rename path), and `backup_dir` (a separate preservation location, _not_ an output root). A separate output-root/copy-out workflow is deferred to a later export or structural-conversion phase. The naive byte-overwrite option is rejected outright (D-004).

### Consequences

- Good, because the output model is simpler and already fully specified by the safety model (ADR-0004): dry-run default, preservation, backups, manifest, atomic writes, containment.
- Good, because atomic replace guarantees a crash leaves only "completed", "not started", or "failed before mutation" — never a partial target (NFR-002), which is what makes resume (ADR-0006 candidate) tractable.
- Bad, because adding a separate output root later is a breaking config redesign (a full second-tree config, path mapping, cross-tree collision/verify/restore) — accepted and deferred, not precluded.
- Bad, because safety rests entirely on the gate + atomic writes rather than on physical source/output tree isolation; this raises the stakes on ADR-0004 being correct.

### Confirmation

Confirmed by: atomic-write / fsync / crash / permission / symlink tests run against a **real** filesystem (not `pyfakefs`, which cannot model these); the absence of an `output_root` key in the §18.2 configuration table; and containment tests proving written paths stay inside `source_root` (§8.5/§13.2/§13.5).

## More Information

- Spec: §8.5, §13.2, §18.2, §21 OQ-012 (Resolved RQ-013); D-004 (atomic replace).
- Resolved question: RQ-013 (owner: "Agree. Defer [output-root] to later"). Preservation strength that guards the write is governed by ADR-0004 (RQ-005/RQ-007); pluggability of the writer's preservation step by the seams principle (ADR-0010 candidate, RQ-010).
- Reconciles the §8.2.2 "Converted library" diagram's copy-out implication to in-place (GAP-70) when the writer is specified.
- Revisit when an export or structural-conversion phase (WH-004) needs a copy-out tree; the seam design keeps that a non-breaking addition.
