---
schema_version: '1.1'
id: 'adr-0020-docmend-commit-boundary-object-identity'
title: 'ADR 0020: Commit-boundary object identity'
description: 'Every corpus mutation binds to one filesystem object, not a pathname: bytes are read once through an O_NOFOLLOW descriptor whose (st_dev, st_ino) identity is captured and persisted, and immediately before every publish and unlink step the pathname is lstat-compared against that identity, with parent-path containment re-resolved at the same instant; targets appearing after the absent-target check are published no-clobber, never overwritten.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-10'
updated: '2026-07-10'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'safety'
  - 'writer'
  - 'toctou'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md'
  - 'docs/codex-reviews/2026-07-10-2034-comprehensive-review-synthesis.md'
  - 'docs/adr/adr-0003-in-place-mutation-output-model.md'
  - 'docs/adr/adr-0004-apply-safety-gate-and-preservation.md'
  - 'docs/adr/adr-0019-manifest-2-recovery-model.md'
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

# Commit-boundary object identity

## Context and Problem Statement

Apply and restore validate a pathname, then later stat and mutate whatever object that pathname names. The 2026-07-10 review reproduced both halves of the resulting gap: a controlled replacement after the hash check was silently overwritten and reported as applied (DMR-06), and a target created after the preservation gate was replaced without a backup or external-preservation declaration (DMR-07). The run lock excludes other docmend runs, not editors, sync clients, or other local processes. How does every mutation guarantee it commits against the same filesystem object it validated and preserved?

## Decision Drivers

- DMR-06's confirmed defect is _different object_, not different bytes — hash equality cannot close it.
- `fstat` on an open descriptor describes the originally opened inode even after the name is repointed; only a pathname-to-descriptor identity comparison detects replacement.
- `O_NOFOLLOW` guards only the final path component; parent directories can be swapped for symlinks independently.
- Overwrite preservation evaluated at gate time is stale by commit time; the invariant must hold at the mutation instant.
- The captured identities must also serve post-kill adjudication, so they cannot remain process-local (ADR-0019).
- Portable POSIX rename cannot be made fully TOCTOU-free; the residual must be minimized, stated, and testable.

## Considered Options

- **Descriptor-bound identity with lstat-at-commit comparison** on both source and target, plus no-clobber publication for late-appearing targets.
- **Re-hash immediately before rename** (bytes-only recheck, no identity binding).
- **Linux-only `renameat2`/`RENAME_EXCHANGE` hardening** with directory descriptors.

## Decision Outcome

Chosen option: **"Descriptor-bound identity with lstat-at-commit comparison."** The source opens once with `O_RDONLY | O_NOFOLLOW`; `fstat` captures `(st_dev, st_ino)`; the hash check, transform recompute, and backup all use bytes read from that descriptor, and the identity is persisted into the action's intent record (with `expected_published_identity` captured by `fstat` of the staged output before the intent append — ADR-0019). Immediately before **every** pathname mutation step — each publish and each unlink — the boundary `lstat`s the pathname (never following symlinks) and compares `(st_dev, st_ino)` against the captured identity; a missing name, a symlink, or a mismatch skips the action as `external-interference` with the corpus untouched. The full path is re-resolved and containment re-checked against the source root at the same instant, so a parent-symlink swap fails even when the leaf identity matches.

An existing overwrite target gets the same binding: opened `O_NOFOLLOW`, identity captured, bytes read and backed up **through that descriptor**, and the pathname `lstat`-compared immediately before `os.replace`. When the earlier check found **no** target, publication uses a no-clobber primitive and maps `EEXIST` to the skip `collision-unpreserved` — a target that appears after the gate is never silently overwritten, making overwrite preservation an action-time invariant regardless of gate-time state (the gate's plan-time check remains early feedback only).

### Consequences

- Good, because validation, preservation, and commit are bound to one object on both the source and target sides, closing both reproduced races.
- Good, because the same captured identities double as the durable adjudication evidence ADR-0019 requires.
- Bad, because the `lstat`-to-`rename` interval remains a residual window — shrunk from whole-action seconds to microseconds, accepted and documented as a stated limitation rather than engineered away with Linux-only primitives.
- Bad, because every mutation step adds an `lstat` + resolve + compare, and the commit path needs injectable hooks to be testable at all.

### Confirmation

Confirmed by deterministic hook-driven race tests: regular-file replacement after validation, parent-symlink interposition, target replacement after backup, target creation immediately before publish, and the unlink/publish windows — each refusing with `external-interference` or `collision-unpreserved` and mutating nothing; plus the ADR-0019 same-bytes/different-inode adjudication probes proving the persisted identities catch what hashes cannot.

## More Information

- Mechanism detail and residual-window statement: `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md` (Commit Boundary section; review findings F2/F3 closed).
- Spec: rev 0.26 — FR-003, FR-005, FR-011, §13.5.
- The action-time overwrite invariant and `WriteSafetyContext` engine gating are recorded as the 2026-07-10 amendment to `adr-0004-apply-safety-gate-and-preservation`; this ADR owns the identity mechanics they rely on.
- Revisit if a Linux-only deployment ever justifies `renameat2`-based elimination of the residual window, or if a filesystem without stable `(st_dev, st_ino)` semantics must be supported.
