---
schema_version: '1.1'
id: 'adr-0012-docmend-verify-semantics-exit-code-taxonomy'
title: 'ADR 0012: verify semantics and tool-wide exit-code taxonomy'
description: 'verify is a read-only command that validates corpus state and artifacts; a small stable exit-code taxonomy — 0 clean, 1 findings, 2 invocation/config/artifact-input error, 3 safety refusal — is applied tool-wide across scan/plan/apply/verify/restore so scripts and agents can distinguish success-with-skips from partial failure from bad invocation from a deliberate safety refusal.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'cli'
  - 'contract'
  - 'verification'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0004-apply-safety-gate-and-preservation.md'
  - 'docs/adr/adr-0005-durable-artifact-schema-contract.md'
  - 'docs/adr/adr-0006-resume-and-recovery-model.md'
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

# verify semantics and tool-wide exit-code taxonomy

## Context and Problem Statement

The corpus is 100,000+ files (NFR-001); the user cannot inspect the result of a run by hand, so `verify` is the machine substitute for manual review. Because docmend is meant to be driven unattended and by agents, the **exit code of every command is a machine-readable API**, not a cosmetic detail — a caller must be able to tell "clean" from "found problems" from "you invoked me wrong" from "I refused for safety" without parsing prose. What does `verify` check, and what exit-code taxonomy do the commands share?

## Decision Drivers

- Outcomes must be script- and agent-interpretable: success-with-skips, partial failure, invocation error, and safety refusal are **four different things** a caller acts on differently.
- `verify` is read-only — it validates, it never mutates (NFR / G-005 posture).
- One taxonomy across all commands beats per-command conventions a caller has to memorize.
- A cited precedent exists (restic's `0/1/2/3/10/11/12/130` scheme) — adopt a small, stable subset rather than invent one.

## Considered Options

- **A small stable `0/1/2/3` taxonomy applied tool-wide, plus an enumerated read-only `verify` check set** (chosen).
- **Fold exit codes into ADR-0005 as "the CLI contract"**: ADR-0005 owns the durable _artifact schema_ contract; exit codes are a _CLI-surface_ contract spanning commands that emit no artifact (a bare `scan` path check, a `restore`), so co-locating them there would overload that ADR.
- **Boolean pass/fail (`0`/non-zero)**: simplest, but collapses the four distinct outcomes a caller must distinguish — a safety refusal would be indistinguishable from a hash-mismatch finding.

## Decision Outcome

Chosen option: **"small stable taxonomy, tool-wide."** The exit-code taxonomy is applied uniformly across **scan / plan / apply / verify / restore**:

| Code | Meaning |
| --- | --- |
| `0` | Clean — all checks passed / operation succeeded with nothing to report. |
| `1` | Findings — the command ran correctly and found reportable problems (bad encoding, CRLF, invalid frontmatter, missing output, hash mismatch, unreconciled counts, skipped-with-errors). |
| `2` | Invocation / config / artifact-input error — bad flags, unreadable or schema-invalid input artifact, malformed config. |
| `3` | Safety refusal / path-containment violation — the safety gate (ADR-0004) declined to proceed. |

`verify PATH` is **read-only** and its v1 checks are: UTF-8 decodability without replacement; LF-only line endings; frontmatter validity where present or expected (duplicate-key rejection **before** schema validation; `format` assertions active for `date`/`date-time`); manifest before/after hashes and backup refs reconcile; report/manifest counts reconcile with per-file outcomes; and skipped/failed files are accounted for. `verify` receives its inputs via explicit `--manifest` / `--report` / `--plan` flags **or** a run-ID-keyed sidecar-discovery convention.

### Consequences

- Good, because a caller (script or agent) can branch on the exit code alone: `1` means "look at the findings," `2` means "I made a mistake invoking it," `3` means "docmend deliberately protected the corpus" — three very different follow-ups.
- Good, because one taxonomy across five commands is a single contract to learn and to test, and it pins `3` as a **distinct** signal so a safety refusal never hides inside a generic non-zero.
- Good, because `verify`'s read-only guarantee makes it safe to run repeatedly in CI or between apply phases.
- Bad, because collapsing every "finding" into a single `1` means the caller must read the report to learn _which_ finding fired — accepted, because the report/manifest already carry per-file detail and multiplying exit codes would make the contract fragile.
- Bad, because a tool-wide taxonomy constrains future commands to fit these four buckets; a genuinely new outcome class would need a new code and a taxonomy revision.

### Confirmation

Confirmed by: exit-code assertions in the CLI test suite for each of scan/plan/apply/verify/restore across clean, findings, bad-invocation, and safety-refusal fixtures; `verify` proven read-only (no mutation, no manifest write) by test; duplicate-key rejection asserted to fire before schema validation; and a below-threshold encoding fixture, a CRLF fixture, and a hash-mismatch fixture each yielding exit `1` with the finding enumerated in the report.

## More Information

- Spec: §7.1 FR-014, §18.5, IR-004.
- Research: `restore-from-manifest-design` (restic exit-code precedent).
- Decision owner: owner (RQ-006, 2026-07-05). The taxonomy's `3` bucket is the observable signal of the ADR-0004 safety gate; `verify`'s reconciliation checks consume the ADR-0005 artifact schemas and the ADR-0006 manifest/report.
- Deliberately kept a **separate** ADR from ADR-0005: exit codes are a CLI-surface contract spanning commands that emit no artifact, so they are not subsumed by the artifact-schema contract.
- Revisit only if a new command introduces an outcome class that none of `0/1/2/3` can honestly represent.
