---
schema_version: '1.1'
id: 'adr-0015-docmend-test-corpus-and-anonymization'
title: 'ADR 0015: Two-corpus test architecture and real-anomaly anonymization'
description: 'docmend tests against two corpora with opposite lifecycles produced by one pure seedable generator: a 100k-file scale corpus generated at test time from a recorded seed (never committed, slow-marked) and a small committed weird-document corpus of size-capped, provenance-decoupled fixtures. Real-library anomalies enter the committed corpus only through a re-synthesis anonymization procedure — reproduce the causal mechanism through unrelated synthetic filler, never mask or scrub original bytes — with an explicit reviewer gate.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-06'
updated: '2026-07-06'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'testing'
  - 'fixtures'
  - 'confidentiality'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/research/synthetic-corpus-generation.md'
  - 'docs/adr/adr-0002-layered-pipeline-isolated-writer.md'
  - 'docs/adr/adr-0013-v1-dependency-selection.md'
  - 'docs/handoff/conventions.md'
supersedes: []
superseded_by: null
source: []
confidence: 'high'
visibility: 'public'
license: null
project:
  decision_makers:
    - 'chrisdpurcell'
---

# Two-corpus test architecture and real-anomaly anonymization

## Context and Problem Statement

The spec demands three things that pull against each other: a 100k-file scale test (NFR-001), a continuously growing weird-document regression corpus that §17.2 calls a headline requirement, and an absolute ban on real library content in this public repository (C-002, conventions #6). Nothing defined how either corpus is produced, and the expedient path — copying an interesting broken file from the real library into `tests/fixtures/` — is exactly the confidentiality violation the repo's rules exist to prevent. How are the corpora generated, stored, and grown from real-world findings without ever leaking real content?

## Decision Drivers

- C-002: this repo is public and the library is personal; a reviewer must be able to confirm a fixture is not real content **by inspection**, without cross-referencing anything.
- The scale corpus and the regression corpus have opposite storage/provenance requirements; conflating them is the most likely design mistake.
- Test corpora should be coverage-optimized, not frequency-realistic (OSS-Fuzz seed-corpus philosophy) — a realistic 99%-clean corpus under-tests the skip-and-report paths that are docmend's safety-critical surface (G-005).
- Reproducibility: a failing 100k-file run must be exactly re-creatable without storing 100k files.
- Structure-preserving masking of real data is a weaker guarantee than true de-identification (ISO/IEC 20889, NIST SP 800-188) — masked bytes can carry re-identifying residue.

## Considered Options

- **Two corpora, one generator, re-synthesis anonymization** (chosen).
- **Commit everything, including the scale corpus**: reproducible by checkout but bloats a public repo by 100k files and multiplies the leak surface; rejected.
- **Hand-authored fixtures only, no generator**: cannot produce the scale corpus at all, and hand-written anomalies reproduce symptoms rather than causal mechanisms (a hand-typed "mojibake-looking" file may not exercise the real decode path); rejected.
- **Mask/scrub real files into fixtures**: preserves the original's length, rhythm, and byte statistics — re-identification residue in a public repo, and "sanitizing appearance" is a documented way real structure leaks back in; rejected on ISO 20889 / NIST 800-188 grounds.

## Decision Outcome

Chosen option: **two corpora, one generator, re-synthesis anonymization.**

| Corpus | Purpose | Lives | Committed? |
| --- | --- | --- | --- |
| Scale corpus (100k files, NFR-001/MS-5) | Bounded-memory/throughput proof | Generated at test time into a session temp directory from a **recorded seed**; gated behind a slow marker (small counts serve everyday CI) | **Never** |
| Weird-document corpus (§10.3, §17.2) | Every anomaly class pinned as a permanent regression fixture | `tests/fixtures/weird_documents/<class>/`, small size-capped files, one case = one behavior = one test, sidecar metadata (anomaly class, expected outcome, provenance line) | Yes — small, synthetic, content-free by construction |

- **One pure, seedable generator** (recipe → bytes; disk materialization isolated in a thin adapter) produces both — deliberately mirroring the NFR-005 transform/writer split so the generator is unit-testable the same way transforms are.
- **Anomalies reproduce mechanisms, not symptoms**: mojibake fixtures are synthetic filler pushed through the actual wrong-codec decode/re-encode chain; below-threshold encoding fixtures are verified against the real `charset-normalizer` at generation time so the corpus cannot drift from the detector it tests.
- **Filler text is Faker output** (dev dependency, ADR-0013 amendment) — deterministic, clearly synthetic, auditable as non-real by inspection; never LLM-generated realistic prose.
- **Anonymization procedure** (real anomaly → shareable fixture): capture facts only (byte offsets, the few bytes involved, detected encoding/confidence, structural description — never the file); classify the causal mechanism; re-synthesize that mechanism through unrelated filler; verify the synthetic fixture triggers the identical code path (same skip reason, same confidence bucket); name and store by mechanism, never provenance; pass the reviewer gate — an explicit confirmation that **zero bytes of the fixture are traceable to the original** (conventions #6).

### Consequences

- Good, because content-freeness is provable by construction: re-synthesized fixtures carry none of the original's structure, which no masking of real bytes can guarantee.
- Good, because a failing scale run reproduces from a seed instead of an artifact archive, and everyday CI stays fast (full 100k generation is opt-in, mirroring the repo's default-off posture for expensive work).
- Good, because the corpus can grow for the life of the project — §17.2's headline requirement — without the growth itself becoming a leak vector.
- Bad, because the generator is its own small software project (recipe format, per-class generator functions, materializer) that must exist before MS-1 tests want fixtures.
- Bad, because re-synthesis takes genuinely more effort per real-world anomaly than copying a file would; the procedure trades convenience for safety on every single fixture.
- Bad, because the reviewer gate is a process control, not a tooling one — secret scanners are documented to miss unstructured-content leaks, so discipline carries the invariant.

### Confirmation

Confirmed by: every committed fixture under the size cap with a sidecar whose provenance line is `synthetic` or `derived from a real-library anomaly; structurally reproduced, no original bytes retained`; the scale test generating from a recorded seed behind a slow marker with nothing materialized inside the repo tree; recipe self-checks validating claimed-below-threshold fixtures against the real detector; and the conventions #6 reviewer-gate line present in every fixture-adding change.

## More Information

- Spec: §17.2 (corpus strategy paragraph), §19 MS-5, C-002; §21 OQ-032. Research: `docs/research/synthetic-corpus-generation.md` (2026-07-05) — sources: OSS-Fuzz seed-corpus guidance, chardet/test-data provenance convention, Open Preservation Foundation format-corpus, ftfy mojibake taxonomy, ISO/IEC 20889, NIST SP 800-188, Hypothesis/Faker/pyfakefs official docs.
- Decision owner: owner, via the OQ-032 AskUserQuestion with individual research walkthrough (2026-07-06); recorded as RQ-032 ("adopt in full").
- Relates to ADR-0002 (the generator copies the purity split), ADR-0013 (Faker dev-dep amendment), ADR-0009 (encoding fixtures exercise its gates).
- Revisit if the weird-document corpus grows toward thousands of files — split it out of the primary Git history **before** that happens (see `self-hosted-corpus-storage-options.md` reasoning), not after.
