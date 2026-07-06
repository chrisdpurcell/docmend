---
schema_version: '1.1'
id: 'adr-0013-docmend-v1-dependency-selection'
title: 'ADR 0013: v1 runtime and dev dependency selection'
description: "One consolidated record for the five dependency choices resolved as RQ-017 through RQ-021 — structlog, jsonschema, pydantic v2, ruamel.yaml, and Hypothesis — each with its rejected alternatives, Python 3.14 wheel status, and license note, satisfying §8.6's rule that every dependency carries a recorded decision without spawning five thin ADRs."
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'architecture'
  - 'dependencies'
  - 'python-314'
  - 'tooling'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/resolved-questions.md'
  - 'docs/adr/adr-0005-durable-artifact-schema-contract.md'
  - 'docs/adr/adr-0007-concurrency-primitive-process-pool.md'
  - 'docs/adr/adr-0009-encoding-detection-dual-skip-gate.md'
  - 'docs/adr/adr-0011-frontmatter-optional-minimal-split.md'
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

# v1 runtime and dev dependency selection

## Context and Problem Statement

§8.6 allows only listed dependencies, and Appendix B.2 prohibits an implementer from introducing an unlisted one without an owner-approved OQ/RQ. Five libraries needed that approval before code could rely on them — a structured-logging library, a JSON-Schema validator, an internal data-model library, a frontmatter YAML codec, and a property-based-testing framework. Each was resolved as its own resolved question (RQ-017–RQ-021). Do these become five thin ADRs, or one consolidated dependency record?

## Decision Drivers

- Dependency minimization: every runtime dependency is attack surface, build risk, and a Python 3.14 wheel-availability bet.
- License compatibility: the distributed package is MIT; a copyleft or license-disputed dependency in `[project.dependencies]` is disqualifying (dev-only tools are held to a looser bar).
- Offline operation: a runtime dependency that pulls network stacks (e.g. `requests`) is unfit for a batch tool that must run air-gapped.
- Python 3.14 readiness: each library must ship 3.14 wheels (including any native transitive dep) and be actively released post-3.14 GA.
- Decision cohesion: these five are revisited **together** as "the v1 dependency set," so they share one reversal context (the backlog's bundling rule).

## Considered Options

- **One consolidated dependency ADR** (chosen): a single record with a row per library and its rejected alternatives.
- **Five per-library ADRs**: one each for structlog/jsonschema/pydantic/ruamel/Hypothesis — accurate but thin, and they fragment a set that is reasoned about as a whole.
- **No ADR (leave them in the RQs/§8.6 table)**: satisfies traceability minimally, but §8.6's "every dependency needs a recorded decision" and the ADR backlog both want a durable architectural home for the rejected alternatives.

## Decision Outcome

Chosen option: **"one consolidated dependency ADR."** The five approved choices, each with what it was chosen **over**:

| Dependency | Layer | Chosen | Rejected alternatives |
| --- | --- | --- | --- |
| `structlog` (wired through stdlib `logging`) | Runtime | Per-run JSON Lines keyed on run-ID + Rich `ConsoleRenderer`; console verbosity decoupled from a DEBUG-floored file sink (RQ-017). | Stdlib `logging` + hand-rolled JSON artifacts (the owner's own earlier dependency-minimization pick — overruled for throughput and per-run JSONL); `loguru` (slower on 3.14). |
| `jsonschema` (≥ 4.26, `format-nongpl` extra) | Runtime | Explicit `Draft202012Validator` + `FormatChecker`, one reused compiled validator per schema (~10× faster than per-call `validate()`) (RQ-018). | `fastjsonschema` (only drafts 04/06/07); `check-jsonschema` as a runtime dep (`requests`-dependent CLI, unfit offline) — retained as a **pre-commit hook only**. `jsonschema-rs` recorded as the pre-vetted escalation path if profiling shows a bottleneck. |
| `pydantic` (v2, ≥ 2.12) | Runtime | Strict internal model layer (`extra='forbid'`) for config/inventory/plan/report/manifest/action records; guards internal construction while the hand-authored JSON Schemas stay the external contract (RQ-020). | Stdlib dataclasses / `TypedDict` (no fail-fast validation at construction — shape errors would reach disk at 100k-file scale). Pydantic v1 (not 3.14-compatible). |
| `ruamel.yaml` (behind a `FrontmatterCodec`) | Runtime | Duplicate-key rejection, controlled quoting/block scalars, Pandoc-compatible emission, and a date/date-time constructor override that keeps those scalars strings (RQ-021). | `PyYAML` + a custom duplicate-key-rejecting loader — kept as the **documented fallback** if ruamel's Beta / single-maintainer risk becomes unacceptable. |
| `hypothesis` | Dev/Test only | Property-based tests for the fixture-free Transform layer (NFR-005), with a CI settings profile loosening `deadline` (RQ-019). | No property testing (leaves §17.2's requirement unmet). MPL-2.0 is acceptable **only** because it is dev-only and never distributed in the MIT package; its sole always-installed transitive dep is `sortedcontainers` (MIT). |

Two rules bind the whole set: every runtime library must ship **Python 3.14 wheels** (including native transitive deps — `jsonschema`'s `rpds-py` ships `cp314`/`cp314t`; `pydantic-core` ships 3.14 wheels), and license compatibility is checked per layer (MIT distributed package; MPL-2.0 tolerated dev-only). Dependencies decided **elsewhere** are out of scope here and cross-referenced instead: `charset-normalizer` (ADR-0009), the `ProcessPoolExecutor` primitive (ADR-0007), and the conventional/low-tradeoff picks `typer` / `rich` / `pathspec` / `tomllib` (stdlib, D-005). `puremagic` remains **deferred**, not adopted.

### Consequences

- Good, because one record captures the whole v1 dependency set and its rejected alternatives, satisfying §8.6 / Appendix B.2 without five near-duplicate ADRs, and gives a future auditor a single place to see why each library won.
- Good, because the division of labor is explicit — `jsonschema` validates the **external** artifact contract, `pydantic` guards **internal** construction (ADR-0005 / RQ-004) — so the two model libraries are not redundant.
- Good, because each choice carries a **named fallback or escalation path** (`PyYAML` for ruamel, `jsonschema-rs` for jsonschema), so a later reversal is pre-vetted rather than open-ended.
- Bad, because a consolidated ADR must be revised when **any** single dependency is replaced, so its `updated` date will churn more than a per-library ADR would — accepted, because the set is small and reasoned about together.
- Bad, because pinning specific libraries couples v1 to their 3.14 wheel cadence and maintenance health (ruamel's single-maintainer/Beta risk is the sharpest example) — mitigated by the documented fallbacks.

### Confirmation

Confirmed by: `pyproject.toml` listing exactly these runtime deps in `[project.dependencies]` and the dev tools in `[dependency-groups].dev` (Hypothesis never in the former); `pip-audit` clean; a license scan confirming the distributed closure is MIT-compatible and MPL-2.0 appears only dev-side (GAP-59); an installed-wheel check confirming 3.14 wheels for every runtime dep and native transitive; and the validator-reuse and duplicate-key behaviors exercised by test.

## More Information

- Spec: §8.6 (runtime and dev/test dependency tables), Appendix B.2 (unlisted-dependency prohibition), NFR-003, DR-005, §17.2.
- Research: `structured-logging-library`, `json-schema-validator-library`, `property-based-testing-hypothesis`, `python-library-research`, `safe-yaml-loading`.
- Decision owner: owner (RQ-017–RQ-021, all 2026-07-05). Consumers: ADR-0005 (jsonschema/pydantic realize the schema contract), ADR-0011 (ruamel realizes the frontmatter codec, jsonschema validates it).
- Revisit per-row: when a fallback/escalation trigger fires (ruamel risk → `PyYAML`; validation bottleneck → `jsonschema-rs`), when a dependency drops 3.14 support, or when a new dependency needs an OQ/RQ and owner approval before it is added to §8.6.
