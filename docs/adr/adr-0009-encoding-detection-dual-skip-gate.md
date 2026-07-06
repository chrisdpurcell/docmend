---
schema_version: '1.1'
id: 'adr-0009-docmend-encoding-detection-dual-skip-gate'
title: 'ADR 0009: Encoding detection and dual skip-gate'
description: "charset-normalizer is the sole detector; a file is skipped if it fails either of two independent gates — decode confidence (1.0 minus chaos) below 0.80, or too few non-ASCII bytes (default 20) to trust a legacy guess — because a single confidence scalar cannot catch short low-entropy false-accepts."
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'encoding'
  - 'safety'
  - 'detection'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0002-layered-pipeline-isolated-writer.md'
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

# Encoding detection and dual skip-gate

## Context and Problem Statement

The corpus is legacy `.txt`/`.html` in mixed, often-ambiguous encodings, where misdetection silently corrupts content at scale (R-001). docmend normalizes everything to UTF-8 without BOM and LF (D-002), so it must decide, per file, whether it can trust a decode — and skip-and-report when it cannot (G-005). What detector, what confidence signal, and what skip criteria?

## Decision Drivers

- Never silently "fix" a low-confidence file (G-005, FR-015); skip-and-report is the safe failure.
- The dominant risk for a `.txt`-heavy English corpus is a short, mostly-ASCII string mis-detected as a legacy multibyte encoding at **maximum** confidence.
- Use a detector that ships Python 3.14 wheels, exposes a usable confidence signal, and carries no licensing risk.
- Build-minimal (RQ-010): one fixed default now, family-aware refinement deferred behind the same seam.

## Considered Options

- **charset-normalizer + a confidence threshold AND an independent non-ASCII byte-count floor** (chosen).
- **charset-normalizer + a single confidence threshold.**
- **chardet / faust-cchardet / uchardet** (rejected: active licensing dispute; no 3.14 wheels / no confidence API).

## Decision Outcome

Chosen option: **"charset-normalizer + dual independent skip-gate."** `charset-normalizer` is the sole detector. Decode confidence is computed as **`1.0 − CharsetMatch.chaos`** (3.x exposes no `.confidence` attribute). A file is skipped if it fails **either** gate: (1) confidence below the configured threshold (default `0.80`), or (2) for a non-BOM, non-valid-UTF-8 file, fewer non-ASCII bytes than the configured floor (default `20`). **Gate ordering:** BOM sniff (authoritative) → strict full-file UTF-8 validity → ASCII-only content treated as ASCII/UTF-8 (never "detected" as legacy) → only a non-BOM, non-valid-UTF-8 file reaches the byte-count floor. The second gate exists because a single confidence scalar provably cannot catch a short low-entropy false-accept — e.g. a 38-byte mostly-ASCII string mis-detected as Big5 at `chaos = 0.0` (maximum confidence, wrong). v1 ships a **single fixed floor of 20**; family-aware overrides (Western single-byte ≥ 20, CJK ≥ 12, Big5 relaxable to 10) and a sparse-long-file ratio signal are deferred behind the same config key (RQ-010 seam). An **MS-2 calibration checkpoint** may tune the 20 within an ~8–20 band against docmend's own short-file distribution **without reopening** this decision.

### Consequences

- Good, because the two orthogonal gates measure different things — "how self-consistent is the decode?" (confidence) and "is there enough evidence to trust a legacy guess at all?" (floor) — and the floor catches the `chaos = 0.0` false-accept the confidence gate cannot.
- Good, because `charset-normalizer` is pure-Python, ships 3.14 wheels, and needs no license carve-out; the gate ordering means ASCII/UTF-8 files never touch legacy detection.
- Bad, because the 20-byte floor deliberately false-skips some genuine tiny Latin-1 and very short CJK files — accepted, because skip-and-report is the safe failure for this corpus.
- Bad, because the exact floor is corpus-sensitive, so the MS-2 calibration checkpoint is a required follow-up (a tuning step, not a reopen).

### Confirmation

Confirmed by: fixtures converting correctly in UTF-8, UTF-8-BOM, Windows-1252, and ISO-8859-1; a below-confidence fixture and a short below-floor fixture each skipped with reason; the §17.2 encoding-floor fixture recipe (total length × non-ASCII count × placement; explicit false-accept and false-skip boundary sets; family-equivalent decode outcomes such as cp932 vs Shift_JIS) in the weird-document corpus; and detection pinned to `charset-normalizer` ≥ 3.4.2.

## More Information

- Spec: §7.1 FR-007, §18.2 (`encoding.fail_below_confidence`, `encoding.non_ascii_floor`), A-003, D-002, G-005.
- Research: `encoding-detection-benchmark`, `charset-detection-floors-for-legacy-text-ingestion`.
- Decision owner: owner (RQ-022). Relates to ADR-0002 (encoding decode is a pure transform), RQ-010 (the family-aware seam), and RQ-009 (the calibration deferral).
- Revisit at the MS-2 calibration checkpoint, or if the family-aware floor / ratio signal is built out behind the config key.
