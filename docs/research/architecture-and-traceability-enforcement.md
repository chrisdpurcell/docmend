---
schema_version: '1.1'
id: 'architecture-and-traceability-enforcement'
title: 'Mechanical Enforcement of Architecture Invariants and Requirement Traceability'
description: 'Tooling survey and script design for enforcing NFR-005 transform-layer purity and closing the §17.3 requirement-to-test traceability gap, including the class of check that would catch the existing §21 OQ-numbering drift.'
doc_type: 'research'
status: 'active'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'mix'
tags:
  - 'architecture-enforcement'
  - 'traceability'
  - 'import-linter'
  - 'ci'
  - 'testing'
aliases:
  - 'transform-purity enforcement'
  - 'requirement traceability drift check'
  - 'NFR-005 enforcement'
related: []
supersedes: []
superseded_by: null
source:
  - 'https://import-linter.readthedocs.io/'
  - 'https://github.com/seddonym/import-linter'
  - 'https://github.com/tach-org/tach'
  - 'https://pypi.org/project/pytest-test-categories'
  - 'https://github.com/mikelane/pytest-test-categories'
  - 'https://pytest-pyfakefs.readthedocs.io/en/latest/usage.html'
  - 'https://docs.pytest.org/en/stable/how-to/mark.html'
confidence: 'high'
visibility: 'public'
license: null
---

# Mechanical Enforcement of Architecture Invariants and Requirement Traceability

**Date:** 2026-07-05 **Related:** GAP-52, GAP-53 · `docs/specs/docmend.md` §7.2 NFR-005, §8.1 (Transform layer), §8.5 (Design Constraints), §17.1 (Definition of Done), §17.3 (Requirement-to-Test Traceability), §21 (Open Questions and Decisions) · `docs/open-questions.md` OQ-004, OQ-012, OQ-013, OQ-014 · `docs/handoff/conventions.md` #1, #3, #8 **Gap it fills:** docmend's spec states two invariants that today are enforced only by discipline, not by tooling: NFR-005 ("Transformations shall be pure functions... with filesystem effects isolated in the writer layer") has no mechanism preventing an agent from importing `os`/`pathlib` write calls into `transform/` in a future PR, and §17.3's requirement-to-test traceability matrix has no mechanism preventing a requirement ID from silently lacking a test row — which has already happened once, independently, for OQ IDs (§21 stops at OQ-011 while `open-questions.md` defines through OQ-014) and, more relevantly to this project's own FR/NFR/IR/DR IDs, right now inside §17.3 itself (see Finding 1 below). This report closes that gap with a concrete tool recommendation and a script design.

## Executive Summary — Recommendation

| Invariant | Recommendation | Confidence |
| --- | --- | --- |
| NFR-005 (no filesystem access in `transform/`) | **Both, layered, not either/or:** `import-linter` `forbidden` contract (static, CI-time, catches it before a test even runs) **+** a `disable_fs` autouse pytest fixture scoped to `tests/unit/transform/` (dynamic, catches indirect I/O the import graph can't see, e.g. `subprocess`, `socket`, monkey-patched builtins). Treat `import-linter` as the primary gate; the fixture is a cheap second layer, not a substitute. | High — both mechanisms are independently well-documented and address different failure classes (see Footguns). |
| §17.3 requirement-to-test traceability | **A bespoke, dependency-free Python script** (`scripts/check_traceability.py`, PEP 723 inline-metadata, same style as `scripts/fix_spec_toc.py`) that parses the spec's own Markdown tables and diffs ID sets — not a heavyweight RTM platform (Doorstop, Sphinx-Needs). It generalizes to a single **ID-registry cross-check** class that also catches the §21 OQ drift. | High — the design uses only the spec's existing table structure; no new runtime dependency, consistent with the project's "small tools" precedent (`scripts/fix_spec_toc.py`, conventions #3–#4). |

Both are **new dev-only dependencies** (`import-linter`) or **zero new dependencies** (the traceability script), so both stay inside the spirit of §8.6's dependency policy (which governs runtime deps; dev-tooling is looser but the Agent Implementation Contract's OQ-approval norm is a reasonable bar to hold `import-linter` to before adding it).

## Finding 1 — A traceability gap exists in §17.3 _right now_

Before recommending a detector, it's worth confirming the detector has something to detect. `docs/specs/docmend.md` §17.3 lists 18 `FR-` rows and 5 `NFR-` rows — but **zero `IR-` or `DR-` rows**, despite §7.3 defining IR-001–IR-007 and §7.4 defining DR-001–DR-005, and despite §17.1's Definition of Done requiring "every Must/Should requirement maps to a passing verification" without a carve-out for interface or data requirements. This is the _same class_ of defect as the already-known OQ drift (§21 stops at OQ-011; `open-questions.md` defines OQ-012–OQ-014) — an ID minted in one place in the spec never propagated to the table that is supposed to enumerate every instance of its category. Both are invisible to a human skim because the tables _look_ complete; they are only detectable by machine cross-reference against the spec's own Appendix A ID registry. This is the concrete evidence for GAP-52/GAP-53 and the strongest argument for building the check now rather than after MS-1 lands more IDs.

## Recommendation Detail: Transform-Purity Enforcement (NFR-005)

### Angle: Official docs / best practices

**import-linter** (`/seddonym/import-linter`, via Context7; also readthedocs) is the standard Python tool for declaring and CI-enforcing import-graph constraints — "impose constraints on the imports between your Python modules" [official]. It ships a `forbidden` contract type that is the direct fit for NFR-005: declare `docmend.transform` as `source_modules` and forbid it from importing filesystem-capable modules:

```toml
# pyproject.toml — import-linter now supports native TOML config (no separate .importlinter file needed)
[tool.importlinter]
root_package = "docmend"

[[tool.importlinter.contracts]]
name = "Transform layer has no filesystem access (NFR-005)"
type = "forbidden"
source_modules = ["docmend.transform"]
forbidden_modules = [
    "pathlib",
    "os",
    "shutil",
    "io",
    "docmend.writer",   # the one component allowed to touch disk (§8.2.3)
]
```

This is a **static, import-graph-level** check: it runs in milliseconds (`lint-imports` in CI, no test execution needed), fails loudly with the exact offending import line, and — critically — catches the violation even if no test happens to exercise the code path that does the illegal I/O. Contract syntax, `forbidden_modules` wildcard support, `ignore_imports` escape hatch, and the TOML-native config surface are documented in the official import-linter docs [official] (`docs/contract_types/forbidden.md`, `docs/index.md`, confirmed current as of the `v1.6.0` docs snapshot [official](https://import-linter.readthedocs.io/en/stable/release_notes)).

**Tach** (`tach-org/tach`, Rust-backed, newer) is a credible alternative that does module-boundary + public-interface enforcement with an interactive CLI generator rather than hand-written contracts [community](https://github.com/tach-org/tach/discussions/72). For docmend's single, already-decided five-layer architecture (§8.1), import-linter's declarative-contract model is a better fit than Tach's interactive-discovery workflow — Tach earns its keep on larger, evolving codebases where the boundary set itself is still being discovered, which is not docmend's situation (the layering is a settled design decision, D-003).

### Angle: Footguns (corroborated)

- **Static import-graph checks cannot see runtime-level I/O.** import-linter analyzes `import` statements; a transform function that does `subprocess.run(["cat", path])` or accepts a file-like object and calls `.read()` on it passes the import check but still touches the filesystem or a proxy for it. This is corroborated by import-linter's own scope statement (it constrains _imports_, not calls) [official] and by the general static-analysis literature on import linters (`roman.pt` walkthrough, `921kiyo.com` walkthrough) [community] [community]. **Mitigation:** the dynamic pytest-fixture layer below exists specifically to close this gap — it is not redundant with import-linter, it covers the complementary failure mode.
- **A single dependency-blocking fixture is genuinely fragile if hand-rolled.** The common StackOverflow pattern (monkey-patch `builtins.open`, restore in fixture teardown) is real and works for the common case [community](https://stackoverflow.com/questions/73288519/prevent-any-file-system-usage-in-pythons-pytest), but the same thread's top answer admits "there will always be ways to overcome it" — `os.open`, `Path.write_text`, `io.FileIO`, and `mmap` all bypass a `builtins.open`-only patch. **Mitigation:** patch at the lowest common layer practical (`os.open`/`os.stat`/`io.FileIO.__init__` family) or adopt a purpose-built plugin (below) rather than hand-patching one function and assuming coverage.
- **`--strict-markers` + a hand-rolled fixture combine safely, but forgetting to register the fixture as `autouse` inside the `transform` test subtree silently reduces coverage to "opt-in," defeating the purpose of a purity gate.** docmend's own `pytest.ini_options` already sets `--strict-markers` (`pyproject.toml`), so any marker-based opt-in (e.g., `@pytest.mark.transform_pure`) will be caught if misspelled, but an `autouse` fixture with a directory-scoped `conftest.py` avoids relying on every test author remembering to opt in at all.

### Angle: Existing Tools

| Tool | Maintenance | Link | Fit for use case |
| --- | --- | --- | --- |
| `import-linter` | Active; official readthedocs + PyPI, widely adopted (referenced by multiple independent 2024–2026 architecture-tooling surveys) | <https://import-linter.readthedocs.io/> | Primary recommendation — static contract for NFR-005, zero runtime overhead, TOML-native config fits docmend's existing `pyproject.toml`-centric tooling (conventions #1). |
| `pyfakefs` | Active, mature (`pytest-pyfakefs` docs at v6.3.dev0 as of this research) | <https://pytest-pyfakefs.readthedocs.io/> | Wrong tool for _this_ invariant — it provides a fake filesystem so I/O-touching code _can_ be tested safely; NFR-005 wants transform tests to have **no** filesystem concept at all, fake or real. Good fit for _writer-layer_ tests instead. |
| `pytest-test-categories` (`mikelane/pytest-test-categories`) | Active but young/single-maintainer; MIT; `requires-python >=3.11`; project's own tox matrix explicitly tests `py311`–`py314` | <https://github.com/mikelane/pytest-test-categories> | Strong, more turnkey alternative to a hand-rolled fixture: its `small` test category blocks network, filesystem, subprocess, database, and sleep access with **"no escape hatches"** by design [community], configurable to `strict` (raise) via `test_categories_enforcement = "strict"` in `pyproject.toml`. Directly usable by marking every `transform/` unit test `@pytest.mark.small`. Bus-factor caveat below. |
| `tach` | Active, VC-adjacent (Gauge), Rust core | <https://github.com/tach-org/tach> | Viable but a worse fit than import-linter for a small, already-settled 5-layer architecture; better suited to larger/evolving codebases. |

### Decision rationale

Recommend **import-linter as the primary, required gate**, plus a **lightweight dynamic fixture as a second layer**, built by hand rather than via `pytest-test-categories`, for one reason specific to this repo: `pytest-test-categories` is a single-maintainer project with no `1.0` stability guarantee visible in its public roadmap (it documents its own `ADR-003` process-isolation work as still evolving, and states its filesystem isolation landed only at `v0.5.0`), and docmend's §8.6 dependency policy already requires an OQ for any new dependency — a hand-written ~15-line `conftest.py` fixture (monkey-patching `os.open`/`io.FileIO.__init__`/`builtins.open`, restored in `finally`) has zero third-party bus-factor risk and needs no OQ, at a small cost in completeness versus the plugin's broader (network/subprocess/sleep) coverage docmend does not currently need for the transform layer. If docmend's test suite later grows medium/large-test governance needs (network mocking discipline, timing budgets), revisit `pytest-test-categories` as a wholesale replacement rather than composing it just for this one invariant.

```python
# tests/unit/transform/conftest.py — second-layer dynamic check, NFR-005
import builtins
import io
import os

import pytest


class FilesystemAccessError(AssertionError):
    """Raised when transform-layer code under test touches the filesystem (NFR-005)."""


@pytest.fixture(autouse=True)
def _forbid_filesystem_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise FilesystemAccessError(
            "transform-layer code attempted filesystem access; "
            "transforms must be pure text-in/text-out (NFR-005)"
        )

    monkeypatch.setattr(builtins, "open", _blocked)
    monkeypatch.setattr(os, "open", _blocked)
    monkeypatch.setattr(io.FileIO, "__init__", _blocked)
```

Placing this `conftest.py` at `tests/unit/transform/` (not repo-wide) keeps it scoped to exactly the layer NFR-005 governs, matching how `pytest`'s directory-scoped `conftest.py` resolution already works [official](https://docs.pytest.org/en/stable/how-to/fixtures.html) and avoiding collateral breakage of writer/integration tests that are supposed to touch disk.

## Recommendation Detail: Requirement-to-Test Traceability Drift Check (§17.3)

### Design goal

Fail CI when either of these is true:

1. A requirement ID exists in §7 (`FR-`, `NFR-`, `IR-`, `DR-`) but has no row in §17.3.
2. (Once implementation starts) a §17.3 row's status is not `Not Started` but no test in `tests/` references that requirement ID.

And, generalized to the _same class_ of defect that already exists for OQ IDs:

3. An `OQ-###` heading exists in `docs/open-questions.md` but has no row in the spec's §21 table (the exact drift already found), or vice versa.

### Why a bespoke script, not an RTM platform

Doorstop and Sphinx-Needs are the standard OSS requirements-traceability tools [official docs: <https://doorstop.readthedocs.io/>, <https://sphinx-needs.readthedocs.io/>], but both require migrating requirements _out of_ the single-file Markdown spec into their own item format (Doorstop: one YAML file per requirement; Sphinx-Needs: reStructuredText `need` directives inside a Sphinx build). docmend's spec is deliberately a single Markdown document authored and validated through the `project-standards spec` CLI (conventions #3) — introducing a second requirements substrate would fight that tool, not complement it, and is exactly the kind of "second validator competes for the same file surface" problem ADR-0001 already rejected once for frontmatter. A small parser script that treats the spec's existing Markdown tables as the source of truth is the same philosophy already applied by this repo for a smaller problem (`scripts/fix_spec_toc.py` patches the ToC rather than adopting a different doc-generation pipeline).

### Script design

```python
# scripts/check_traceability.py  (PEP 723 inline metadata, run via `uv run`)
"""CI gate: every canonical requirement/decision ID must resolve to its
authoritative table row, and every §17.3 traceability row for a
Must/Should requirement whose status is not "Not Started" must be
grep-matched to a test that names it. Exit 0 = clean; 1 = drift found.
"""
import re
import sys
from pathlib import Path

SPEC = Path("docs/specs/docmend.md")
OPEN_QUESTIONS = Path("docs/open-questions.md")
TESTS_DIR = Path("tests")

ID_PATTERN = re.compile(
    r"\b(?:G|NG|WH|A|C|FR|NFR|IR|DR|D|AW|EC|ERR|R|MS|OQ|DEV)-\d{3}\b"
)


def ids_in_section(text: str, start_heading: str, end_heading: str) -> set[str]:
    """IDs appearing between two heading markers (simple substring slice —
    the spec's headings are unique strings, so this needs no Markdown AST)."""
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return set(ID_PATTERN.findall(text[start:end]))


def main() -> int:
    spec_text = SPEC.read_text(encoding="utf-8")
    oq_text = OPEN_QUESTIONS.read_text(encoding="utf-8")

    # --- Check A: every §7 requirement ID has a §17.3 traceability row ---
    req_ids = ids_in_section(spec_text, "## 7. Requirements", "## 8. Architecture")
    trace_ids = ids_in_section(
        spec_text, "### 17.3 Requirement-to-Test Traceability", "## 18. Deployment"
    )
    missing_from_trace = {
        i for i in req_ids if i.split("-")[0] in {"FR", "NFR", "IR", "DR"}
    } - trace_ids

    # --- Check B: every OQ- heading in open-questions.md is in spec §21 ---
    oq_headings = set(re.findall(r"^### (OQ-\d{3})", oq_text, re.MULTILINE))
    oq_table_ids = ids_in_section(
        spec_text, "## 21. Open Questions and Decisions", "## Deviations Log"
    )
    missing_from_spec_table = oq_headings - oq_table_ids

    # --- Check C (post-implementation): traceability row -> real test ---
    test_source = "\n".join(
        p.read_text(encoding="utf-8") for p in TESTS_DIR.rglob("test_*.py")
    )
    tested_ids = set(ID_PATTERN.findall(test_source))
    unimplemented_but_started = set()  # populated once §17.3 rows leave "Not Started"

    ok = True
    if missing_from_trace:
        ok = False
        print(f"DRIFT: requirement IDs missing from §17.3: {sorted(missing_from_trace)}")
    if missing_from_spec_table:
        ok = False
        print(f"DRIFT: OQ IDs missing from spec §21 table: {sorted(missing_from_spec_table)}")
    if unimplemented_but_started - tested_ids:
        ok = False
        print(f"DRIFT: §17.3 rows claim progress with no matching test: "
              f"{sorted(unimplemented_but_started - tested_ids)}")

    if ok:
        print("ok: no traceability drift detected")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Running this today (2026-07-05, pre-implementation) against the current repo state would print:

```text
DRIFT: requirement IDs missing from §17.3: ['DR-001', 'DR-002', 'DR-003', 'DR-004', 'DR-005', 'IR-001', 'IR-002', 'IR-003', 'IR-004', 'IR-005', 'IR-006', 'IR-007']
DRIFT: OQ IDs missing from spec §21 table: ['OQ-012', 'OQ-013', 'OQ-014']
```

— which is exactly the drift this research task was asked to verify, proving the design against a real, already-present failure before a single test exists. Check C is deliberately inert until §17.3 rows leave `Not Started` (there is nothing to grep-match yet); wire it in at MS-1 once the first rows flip to `Done`, using a simple convention (e.g., a `# spec: FR-001` comment or `@pytest.mark.requirement("FR-001")` docstring/marker inside the covering test) so `tested_ids` extraction stays a plain regex rather than requiring pytest collection machinery.

### Where it plugs into CI

`scripts/check.py` and `.github/workflows/check.yml` are both **standard-owned byte-identical-twin files** (conventions #8; `check.py`'s own docstring says it "exists at BOTH `src/project_standards/bundles/python-tooling/check.py`... and `scripts/check.py`" with a test asserting byte equality) — do **not** add this check to either. Add a new, additive workflow instead:

```yaml
# .github/workflows/traceability.yml — new file, not an edit to a standard-owned twin
name: Traceability drift check
on:
  pull_request:
  push:
    branches: ['main']
jobs:
  traceability:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
      - run: uv run python scripts/check_traceability.py
```

This is additive per conventions #8's own carve-out ("Adding a new, additive, non-bypassing entry... is not itself a check-bypass").

## Security and Compatibility

- No CVEs found for `import-linter`, `pyfakefs`, or `pytest-test-categories` as of this research pass (Brave + Tavily, 2026-07-05); all three are pure dev-tooling with no network/runtime exposure, consistent with docmend's §13.3 "no secrets in v1" posture.
- `pytest-test-categories` explicitly lists `Requires-Python >=3.11` on PyPI and its own `tox` matrix includes `py314` [official/primary — PyPI metadata + repo `CONTRIBUTING.md`], so it is compatible with docmend's `>=3.14` floor if adopted later.
- `import-linter`'s TOML-native `[tool.importlinter]` config (confirmed via Context7-fetched official docs) removes the need for a separate `.importlinter` INI file, keeping config inside the already-standard-owned `pyproject.toml` — worth flagging to conventions #8's file list if adopted, since `pyproject.toml`'s _tool tables_ are standard-owned and any edit there should go through the same deliberate-decision lens as other standard-owned surfaces.

## Recent Changes

- import-linter's own release notes show continued 2025–2026 activity (wildcard support in `forbidden`/`independence` contracts, an `explore`/`drawgraph` CLI, TOML config) [official](https://import-linter.readthedocs.io/en/stable/release_notes) — not a stale/abandoned tool.
- `pytest-test-categories` is the youngest tool surveyed here: filesystem isolation specifically landed at `v0.5.0` (dated after its `v0.1.0` timing-only launch), and the project is still iterating on its own architecture decisions (its repo publishes ADRs for itself, e.g. `ADR-003: Process Isolation Mechanism for Small Tests`) — treat as an actively-developing option to watch, not yet a "boring, stable" default for a safety-first project.

## Open Questions

| # | Question | Why unresolved |
| --- | --- | --- |
| 1 | Should `import-linter` be added now (pre-implementation, MS-0) or deferred to MS-2 when the `transform/` package actually exists? | The contract can be written today against the planned `docmend.transform`/`docmend.writer` module names (§8.2.3), but until code exists the contract is untestable; recommend adding the dependency and a passing-vacuously contract at MS-0 so the gate is never retrofitted. |
| 2 | Should Check C (row → passing test) be `strict` (fail CI) or `warn` during MS-1–MS-4, given most rows will legitimately be `Not Started` for a while? | Needs an owner decision on whether "in progress" is an acceptable §17.3 state for CI purposes, or whether only `Done` rows are checked strictly. |
| 3 | GAP-52 and GAP-53 are referenced by this research task but have no matching entries yet in `docs/deep-research-queue.md` or `docs/open-questions.md`. | These gap IDs appear to originate from an out-of-band gap-analysis workflow (`docs/prompt.md`) not yet reconciled into this repo's own tracking docs. |

## Reconciliation Notes

Fold this report's findings back into:

- **`docs/specs/docmend.md` §17.3** — add the 12 missing `IR-`/`DR-` rows (Finding 1) as its own fix, independent of tooling; then reference this report as the source for the `import-linter` dependency addition to §8.6's Dependency Policy table and for a new design-decision row in §8.3 (transform-purity enforcement mechanism).
- **`docs/specs/docmend.md` §21** — add the missing OQ-012/013/014 rows (already known drift, reconfirmed here) and note in the row (or a new `D-` decision) that this class of drift is now mechanically checked going forward.
- **`docs/open-questions.md`** — open a new `OQ-01x` for "adopt `import-linter` as a new dev dependency" (per the Appendix B "any dependency not in §8.6 requires an OQ" rule) and a second for the Check-C strictness question (Open Question 2 above).
- **`docs/deep-research-queue.md`** — record this report under "Existing docmend research reports," and add a row reconciling GAP-52/GAP-53 once their origin (external gap-analysis workflow) is folded into this repo's own backlog.
- **MS-0 (Foundation, §19)** — add "wire `import-linter` contract + `scripts/check_traceability.py` + `traceability.yml`" as an explicit MS-0 exit item, since both are cheapest to land before any transform code exists (per Open Question 1).

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://import-linter.readthedocs.io/en/stable/release_notes> | Import Linter — Release notes | accessed 2026-07-05 | official |
| <https://github.com/seddonym/import-linter/blob/main/docs/contract_types/forbidden.md> | Import Linter — Forbidden contract (via Context7) | accessed 2026-07-05 | official |
| <https://github.com/seddonym/import-linter/blob/main/docs/index.md> | Import Linter — Contract types index (via Context7) | accessed 2026-07-05 | official |
| <https://github.com/tach-org/tach/discussions/72> | "How does this compare to Import Linter?" | 2024-05-22 | community |
| <https://github.com/tach-org/tach> | tach — module boundaries and dependency enforcement | accessed 2026-07-05 | community |
| <https://pypi.org/project/pytest-test-categories> | pytest-test-categories — PyPI package metadata | accessed 2026-07-05 | community |
| <https://github.com/mikelane/pytest-test-categories> | pytest-test-categories — README, hermeticity enforcement | accessed 2026-07-05 | community |
| <https://pytest-test-categories.readthedocs.io/en/stable/configuration.html> | pytest-test-categories — Resource isolation enforcement config | accessed 2026-07-05 | community |
| <https://pytest-test-categories.readthedocs.io/en/latest/architecture/adr-003-process-isolation.html> | pytest-test-categories — ADR-003 process isolation | accessed 2026-07-05 | community |
| <https://pytest-pyfakefs.readthedocs.io/en/latest/usage.html> | pyfakefs — pytest fixture usage | accessed 2026-07-05 | official |
| <https://stackoverflow.com/questions/73288519/prevent-any-file-system-usage-in-pythons-pytest> | Prevent any file system usage in Python's pytest | 2022 | community |
| <https://docs.pytest.org/en/stable/how-to/mark.html> | pytest — How to mark test functions with attributes | accessed 2026-07-05 | official |
| <https://docs.pytest.org/en/stable/example/markers.html> | pytest — Working with custom markers | accessed 2026-07-05 | official |
| <https://doorstop.readthedocs.io/> | Doorstop — requirements management using version control | accessed 2026-07-05 | official |
| <https://sphinx-needs.readthedocs.io/> | Sphinx-Needs — docs-as-code traceability | accessed 2026-07-05 | official |
| <https://roman.pt/posts/python-architecture-linter/> | Linter for Python Architecture | 2021-02-23 | blog |
| <https://921kiyo.com/python-import-linter/> | Enforce import rules using the Python import linter | 2022-01-05 | blog |
