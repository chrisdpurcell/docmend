---
schema_version: '1.1'
id: 'adr-0019-docmend-manifest-2-recovery-model'
title: 'ADR 0019: Manifest 2.0 recovery model'
description: 'Manifest 2.0 replaces per-record trust with a validated set model: a header envelope anchoring run, root, plan, and backup-store facts; hash-linked manifest and attempt chains; intent-before-mutation journaling for every mutation kind including restore inverses; durable object identities in intent records; and one lifecycle reducer with a complete crash-state adjudication table shared by resume, restore, and verify.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-10'
updated: '2026-07-11'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'resume'
  - 'recovery'
  - 'safety'
  - 'manifest'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md'
  - 'docs/codex-reviews/2026-07-10-2034-comprehensive-review-synthesis.md'
  - 'docs/adr/adr-0004-apply-safety-gate-and-preservation.md'
  - 'docs/adr/adr-0005-durable-artifact-schema-contract.md'
  - 'docs/adr/adr-0020-commit-boundary-object-identity.md'
supersedes:
  - 'docs/adr/adr-0006-resume-and-recovery-model.md'
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

# Manifest 2.0 recovery model

## Context and Problem Statement

The 2026-07-10 comprehensive review confirmed that the ADR-0006 recovery model trusts manifest records line by line: no consumer checks run/root coherence, sequence integrity, lifecycle legality, or path containment before reading and mutating recorded paths (DMR-03); only one of three mutation kinds writes a pre-mutation intent record and restore writes none, so kills leave completed mutations with no durable evidence and interrupted restores that do not converge (DMR-04). Reproductions changed files outside the recorded source root, accepted mixed-root/mixed-run manifests, and suppressed planned work via crafted resume records. What durable record model makes resume, restore, and verify consume one validated, deterministic view of what actually happened?

## Decision Drivers

- A manifest is operator-supplied input to the disaster-recovery path; it must be validated as a whole before any referenced path is read or mutated.
- Every mutation — including each restore inverse — must leave durable evidence on both sides of its window (ADR-0006's per-kind gap is the confirmed defect).
- Post-kill adjudication must be deterministic and complete: every crash-after-step state of every primitive either converges or is refused by predicate failure, never guessed past (retains ADR-0006's no-guessing rule).
- The evidence adjudication consumes — object identities included — must itself survive the kill.
- Ordering must come from durable links, never wall-clock or caller order.
- No real-library runs exist yet, so a clean format break is cheap now and never again.

## Considered Options

- **Validated manifest-set model:** header envelope + hash-linked chains + journal-every-mutation + one lifecycle reducer.
- **Per-finding patches on manifest 1.3:** add validation calls at each consumer and intent records for the other kinds.
- **WAL-first two-phase apply:** journal all intents up front, then execute.

## Decision Outcome

Chosen option: **"Validated manifest-set model."** Manifest 2.0 keeps append-only NDJSON and the AOF torn-tail rule but line 1 becomes a **header record** owning run-level facts: `run_id`, `kind` (`apply` | `restore`), resolved `source_root`, resolved `backup_root` (null when no tool backups), `plan_sha256`, `prior_manifest_sha256` (mutation-ledger subchain link), and `prior_attempt` (unified attempt-lineage edge, persisted redundantly in the header and the apply report so the edge survives whichever artifact an interruption erases).

**Journal every mutation.** Every kind — rewrite, rename, rename_and_rewrite, and each restore inverse — appends a fsync'd `intent` before any corpus document is mutated and a terminal (`applied` | `failed`) after. Replacement outputs are **staged before the intent** so the intent carries `expected_published_identity` (the staged inode) alongside `source_identity` and `target_identity` — the identities post-kill adjudication needs, durable by construction. Restore records carry `undoes_action_id`/`undoes_run_id`; inverse relationships are never inferred.

**ManifestSet and chain validation** runs before any referenced path is touched: header presence and version (any 1.x rejected with a clean-break message pointing at docmend 1.0.2), single run with contiguous `seq`, lifecycle legality at two scopes (per-set terminal uniqueness; a cross-set transition table permitting `failed → intent → applied` retries and rejecting contradictions of `applied`), chain coherence (one root, no forks, one plan, restore only at the tip), containment (record paths inside `source_root`; backup references must reconstruct exactly from the header-anchored BackupStore key `(run, action, role, relative_path)` — never free-form paths).

**One reducer, three consumers.** `reduce_lifecycle(chain)` folds records in chain order then `seq` into one state per action; resume, restore, and verify all consume it. Dangling intents are adjudicated from disk state against the intent's persisted hashes and identities via a complete per-step crash-state table — including the lossless both-names intermediates of link-then-unlink primitives — with `external-interference` reserved for states failing every recorded predicate. Identity comparison is exact `(st_dev, st_ino)`; a device change refuses rather than substituting.

### Consequences

- Good, because resume, restore, and verify share one validated view — the three divergent interpretations that produced DMR-03/04 are structurally deleted.
- Good, because a crafted or incoherent manifest fails closed before any path access, and backup references are derivable evidence rather than trusted pointers.
- Good, because interrupted restores converge on re-run instead of colliding with their own residue.
- Bad, because every mutation now costs two fsync'd manifest appends plus staged-output identity capture.
- Bad, because pre-2.0 manifests are unreadable by v2 tooling — the recorded escape hatch is restoring with docmend 1.0.2.
- Bad, because the wire model (header, identities, lineage, adjudication table) is substantially more complex than 1.3 and demands the full fault-injection matrix.

### Confirmation

Confirmed by: adversarial manifest fixtures (mixed root/run, gapped or duplicate `seq`, crafted out-of-root paths, crafted backup paths outside the BackupStore key space, broken or forked chains, immutable-field divergence, missing `undoes` references, 1.x rejection); one deterministic kill-after-step fault-injection test per adjudication-table row plus same-bytes/different-inode substitution probes in both pre- and post-publish windows; the composed chain regression (report-only attempt → manifest-with-missing-report attempt → success, artifacts passed shuffled, one deterministic order); and a restore-convergence re-run drill.

## More Information

- The header additionally records the run's effective exclude patterns. Plan C review CR-006 requires restore's artifact-destination carve-out to be licensed against the excludes that governed apply, which per-invocation replacement flags make unreconstructable later. Revision note: added 2026-07-11.
- Supersedes `adr-0006-resume-and-recovery-model`: the plan/manifest/hash triangulation, incremental fsync-per-record NDJSON, and AOF torn-tail rule carry forward; the single-kind intent record, per-record trust, and wall-clock resume ordering do not.
- The full wire model, adjudication table, and worked apply → interrupted resume → interrupted restore → convergent re-run example live in the approved design: `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md` (reviewed through five adversarial rounds, F1–F8 closed).
- Spec: rev 0.26 — FR-013, FR-014, DR-003, DR-004, IR-008, §12.2/§12.3.
- Commit-time identity capture is ADR-0020's decision; schema ownership and the compatibility break are recorded against ADR-0005's amended contract.
- Targets v2.0.0. Revisit if a non-POSIX filesystem or a multi-writer manifest is ever supported.
