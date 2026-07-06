---
schema_version: '1.1'
id: 'adr-0016-docmend-mechanical-transform-boundary'
title: 'ADR 0016: The mechanical-transform boundary — file-type dispatch, content-preservation invariant, tab semantics'
description: 'Consolidated record of what "mechanical" means at its edges: HTML/markup files are in default scope for encoding + EOL normalization only (no whitespace transforms, no renames); v1 mechanical transforms carry a hard content-preservation invariant (non-whitespace character count never decreases — the exact, threshold-free form of EC-005) with a forward-looking shrink-ratio knob; and tab normalization means leading-indentation tabs to spaces only, interior tabs untouched. Bundles RQ-025/RQ-030/RQ-031, which share one reversal surface: the transform dispatch layer.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-06'
updated: '2026-07-06'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'transforms'
  - 'scope'
  - 'safety'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0002-layered-pipeline-isolated-writer.md'
  - 'docs/adr/adr-0009-encoding-detection-dual-skip-gate.md'
  - 'docs/adr/adr-0014-tool-first-product-scope.md'
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

# The mechanical-transform boundary — file-type dispatch, content-preservation invariant, tab semantics

## Context and Problem Statement

"Mechanical, conservative transformations" is the v1 promise (§1, RQ-001), but three of its edges were undefined, and each is a place where an implementer would otherwise guess: **which file types** get which transforms (the default include globs silently excluded `.html`/`.htm` — roughly half the corpus); **what proves no content was lost** (EC-005's "empty or drastically smaller output" had no number, and a naive size ratio false-positives on padded legacy files that legitimately shrink under blank-line collapse); and **what tab normalization does** (`whitespace.normalize_tabs` existed in config with no defined transformation over a corruption class §1 explicitly names). These three decisions share one reversal surface — the transform layer's per-file-class dispatch — so they are recorded together (the ADR-0013 bundling pattern), not as three thin ADRs.

## Decision Drivers

- A default first run must honor the tool's stated purpose (ADR-0014's tool-first framing sharpens this): silently ignoring half the corpus is a trust failure, but whitespace-transforming markup would corrupt `<pre>`/`<script>`/`<style>` content.
- G-005: transforms are trusted unreviewed at scale, so the "no content lost" check must be exact, not tunable — a threshold someone can mis-set is a threshold that silently eats content.
- v1's mechanical transforms touch only whitespace and encoding **by definition** — which makes an exact invariant available for free.
- Column-aligned ASCII tables and art are real content in a 1990s-era corpus; a uniform tabs-to-spaces pass would destroy their alignment.
- Structural HTML→Markdown conversion is deferred (WH-004) and must not leak into v1 through the back door of "cleanup."

## Considered Options

- **File-type dispatch — HTML mechanical-only** (chosen) vs. scan-only inclusion (inventory but never mutate: leaves mixed encodings/EOLs in half the corpus) vs. documented exclusion (honest but contradicts §1's framing).
- **Content check — invariant + forward knob** (chosen) vs. ratio-only (default 0.50: simple but false-positive-prone on padded files and false-negative-prone on partial loss above the threshold) vs. invariant-only (leaves EC-005's "drastically smaller" wording with no configurable meaning for future content-touching transforms).
- **Tab semantics — leading-only conversion** (chosen) vs. all-tabs conversion (fully normalizing but corrupts aligned tables/art) vs. dropping the config key until WH-003 (leaves a §1-named corruption class with no v1 answer at all).

## Decision Outcome

The mechanical-transform contract, complete:

1. **Dispatch by file class (RQ-025).** `.txt`/`.md`: the full mechanical set — extension rename, encoding → UTF-8, EOL → LF, trailing-whitespace trim, final-newline enforcement, blank-line collapse, plus the optional tab conversion. `.html`/`.htm` (now in the default include globs): **encoding and EOL normalization only** — no whitespace transforms, no renames; structural conversion remains WH-004's problem. The dispatch is a seam in the transform layer, not scattered conditionals.
2. **Content-preservation invariant (RQ-030).** Under v1's mechanical transforms, any reduction in **non-whitespace character count** (compared post-decode, so encoding conversion cannot skew it) flags the file as risky — exact, threshold-free, and immune to the padded-file false positive because whitespace-only shrinkage never trips it. `safety.shrink_ratio` (default 0.50 of decoded characters) is a forward-looking bound for future content-touching transforms only; it is not the v1 check.
3. **Tab semantics (RQ-031).** `normalize_tabs = true` converts **leading (indentation) tabs only** to spaces at `whitespace.tab_width` (default 4); interior tabs are untouched. Off by default; explicitly additional to the RQ-001 six default transforms, so enabling it never changes what a default run does.

### Consequences

- Good, because "mechanical" now has a testable definition at every edge an implementer previously had to interpret — the transform layer can be built without minting new OQs for these questions.
- Good, because the invariant makes the safety claim exact: for v1, _any_ non-whitespace loss is a defect, full stop — no tuning, no judgment calls, no per-corpus calibration.
- Good, because HTML owners get real value (one canonical encoding/EOL across the whole corpus) without v1 pretending markup cleanup is mechanical.
- Bad, because HTML users may be surprised that "processing" leaves markup's whitespace untouched — the plan/report must make the per-class action set legible.
- Bad, because per-file-class dispatch adds a branch point the transform layer must keep pure and the §17.2 fixtures must cover per class.
- Bad, because leading-only tab conversion deliberately leaves interior-tab mess (aligned-table drift, mid-line tab runs) for the WH-003 reconstruction era.

### Confirmation

Confirmed by: fixture tests per file class asserting HTML receives exactly encoding/EOL changes and nothing else in an end-to-end run; an EC-005 test seeding non-whitespace loss and asserting the risky flag with no tunable involved; a padded-legacy-file fixture shrinking heavily under blank-line collapse **without** tripping the invariant; and tab fixtures asserting leading conversion at the configured width with interior tabs byte-identical.

## More Information

- Spec: §2.1 (markup scope sentence), §18.2 (`paths.include`, `whitespace.normalize_tabs`, `whitespace.tab_width`, `safety.shrink_ratio`), FR-009, EC-005; §21 OQ-025/OQ-030/OQ-031.
- Decision owner: owner, via the OQ-025..033 AskUserQuestion rounds (2026-07-06); recorded as RQ-025/RQ-030/RQ-031.
- Relates to ADR-0002 (dispatch lives in the pure transform layer), ADR-0009 (encoding is the one transform HTML does receive), ADR-0014 (default-run honesty driver).
- Revisit when WH-004 (structural HTML conversion) is scheduled — the dispatch table gains a conversion action — or if MS-2's weird-document corpus surfaces a file class the two-class dispatch cannot express.
