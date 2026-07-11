---
schema_version: '1.1'
id: 'adr-0004-docmend-apply-safety-gate-and-preservation'
title: 'ADR 0004: Apply safety gate and preservation posture'
description: "Before any non-dry-run mutation, docmend evaluates a set of pure independent predicates that prove both that a write is safe and that it can be mechanically undone, at a strength scaled to the operation's risk; docmend stays agnostic to the preservation backend the user chooses."
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-10'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'safety'
  - 'preservation'
  - 'apply'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0003-in-place-mutation-output-model.md'
  - 'docs/adr/adr-0005-durable-artifact-schema-contract.md'
  - 'docs/adr/adr-0019-manifest-2-recovery-model.md'
  - 'docs/adr/adr-0020-commit-boundary-object-identity.md'
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

# Apply safety gate and preservation posture

## Context and Problem Statement

The dangerous failure mode for docmend is a _successful_ rewrite that leaves no recoverable original. Because `apply` mutates in place (ADR-0003), the tool must, before every non-dry-run mutation, prove two things: that it _can write safely_, and that it _can undo the write mechanically_. It must do so at a strength proportional to the operation's blast radius — a single low-risk file should not demand the same ceremony as a critical batch rewrite — while never depending on docmend being a backup platform.

## Decision Drivers

- Prove-before-mutate: no write proceeds unless a set of checkable conditions all hold.
- Risk-scaled strength: lightweight posture for quick low-risk single-file work (up to an explicit "no backup" opt-in the operator accepts); byte-preserving strategy mandatory for critical/batch content rewrites.
- Mechanical reversibility: a manifest of every mutation, and a first-class way to replay it back.
- Preservation-agnostic: the user owns the backup strategy (Git, external backups, snapshots, Borg/restic, tool-written backups, or none for throwaway work); docmend supports the choice without imposing one.
- Testability: the gate must be decomposable into independent predicates that can be combinatorially tested.

## Considered Options

- **A set of pure independent predicates evaluated every run, with risk-scaled preservation and verify-then-mutate** (RQ-005 + RQ-007).
- **A single fixed preservation requirement** for all operations (always-backup, no scaling).
- **No gate** — trust configuration and the operator.

## Decision Outcome

Chosen option: **"Pure independent predicates, risk-scaled, verify-then-mutate."** Before any non-dry-run mutation the gate evaluates: valid plan against current schema; compatible tool/schema version; plan source hashes still match; explicit `--write` opt-in (ADR/RQ-015); output-path containment; collision policy explicit and satisfied; risky files skipped or run configured to fail; **at least one preservation strategy appropriate to the operation's risk level active**; manifest writable; backup destination outside the mutation target and writable; per-mount disk-space preflight. FR-006 is **verify-then-mutate**: fsync the backup, re-read and re-hash it, compare to the plan's `source.hash`, record `backup_verified`, and raise ERR-004 on mismatch _before_ touching the original. A manifest is **not** a preservation strategy for content-changing rewrites — it is mandatory rollback metadata, not original-byte storage. A first-class `docmend restore` replays manifest records per `docmend.id` in LIFO order. docmend stays **agnostic** to the preservation backend (RQ-007): its responsibility ends at what makes its own operations safe and reversible; no heavy corpus-storage platform is part of the tool.

### Consequences

- Good, because every mutation is provably both safe-to-write and mechanically-undoable, at a strength matched to blast radius.
- Good, because risk-scaling keeps quick single-file work ergonomic (an explicit no-backup opt-in is allowed) while forcing byte-preservation on critical batches — flexibility without a loophole.
- Good, because staying backend-agnostic means the core safety contract never depends on deploying a storage platform.
- Bad, because a many-predicate gate plus `restore` is more to build and test; mitigated by pairwise (allpairspy) coverage over the independent predicates, at t=3 for the preservation/manifest/backup trio.
- Bad, because a real first-library run still requires a named preservation posture and a successful restore drill before it can proceed — deliberate friction.

### Confirmation

Confirmed by: pairwise combinatorial tests over the predicate set (t=3 for the preservation/manifest/backup interaction); an automated backup-and-restore drill from the manifest (§18.6); ERR-004 raised on any backup re-hash mismatch; and the gate refusing every run in which any predicate fails (exit code 3, safety refusal).

## More Information

- **Amendment (2026-07-10, comprehensive review / safety-core design):** three of this gate's assumptions are recontracted for v2 (spec rev 0.26). (1) **Overwrite preservation becomes an action-time invariant**: the gate's plan-time overwrite check is early feedback only — any target present at the commit instant must have a verified preservation outcome (an overwritten-role backup taken at commit, or a declared external strategy), and overwrite policy with no active strategy skips `collision-unpreserved` rather than clobbering (DMR-07; identity mechanics in `adr-0020-commit-boundary-object-identity`). (2) **Backups become a write-once BackupStore** keyed `<backup_root>/<run_id>/<action_seq>/<role>/<relative_path>` (`role` ∈ `source`/`overwritten`, `O_EXCL`, second write to a key is ERR-004) — closing the DMR-01 same-plan key collision — and manifest backup references must reconstruct from the header-anchored key, never free-form paths (`adr-0019`). (3) **Write-capable engine entrypoints are sealed behind a `WriteSafetyContext`** constructible only by acquiring the run lock and passing this gate (restore: the ManifestSet preflight), held through manifest close and report publication; read-only previews stay ceremony-free (FR-004/IR-008).
- Spec: §7.1 FR-005/FR-006, §8.5, §18.6, §21 OQ-005 (Resolved RQ-005) and OQ-008 (Resolved RQ-007).
- Research: `backup-integrity-verification`, `restore-from-manifest-design`, `combinatorial-safety-gate-testing`.
- The preservation _strategy_ selection is RQ-007 (agnostic); its pluggability is the seams principle (ADR-0010, RQ-010); the `--write` opt-in that this gate requires is RQ-015; the output model it guards is ADR-0003; the manifest it writes obeys ADR-0005.
- Revisit if a new preservation class (e.g. content-addressed store) needs first-class gate support, or if risk-tier definitions need to be made configurable.
