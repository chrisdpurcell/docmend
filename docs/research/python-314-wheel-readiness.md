# Python 3.14 Wheel Readiness for the Approved Dependency Set

**Date:** 2026-07-05 **Related:** GAP-60 (dependency/CI pre-flight gap, tracked by the calling workflow — no in-repo anchor yet; see Reconciliation notes); `docs/specs/docmend.md` §8.6 Dependency Policy, §18.3 Deployment Flow (CI checks); `pyproject.toml` (`requires-python = ">=3.14"`, `dev` group); `.github/workflows/check.yml`; `docs/open-questions.md` OQ-004 (JSON Schema choice feeds the "Conditional" validator row in §8.6) **Status:** informational research — feeds a new CI/pre-flight recommendation, does not itself resolve an existing OQ

**Gap it fills:** docmend pins `requires-python = ">=3.14"` and already had to bump `ruff>=0.14` in `pyproject.toml` because earlier Ruff releases rejected `target-version = "py314"` — proof the project has already been bitten once by 3.14 tooling lag. Section 8.6 of the spec approves `typer`, `charset-normalizer`, `pathspec`, `rich`, and a JSON Schema validator (with `jsonschema` given as the example) but never checks whether any of them, or their compiled transitive dependencies, actually ship installable Python 3.14 wheels — a live risk for a project whose CI (`.github/workflows/check.yml`) runs `uv sync --locked --all-groups` against `.python-version = 3.14` with no fallback path if a `uv lock` resolution suddenly demands a source build. This report closes that verification gap (GAP-60) with per-package wheel evidence pulled directly from PyPI, corroborated against the community-run Python 3.14 readiness tracker, and turns the finding into a concrete, low-cost CI check plus a fallback playbook.

## Bottom line

Every dependency on the approved list — including the compiled ones — already ships Python 3.14 wheels as of this writing, so **there is no source-build risk for docmend today.** The one genuine transitive compiled dependency, `rpds-py` (pulled in by `jsonschema` via `referencing`), already publishes `cp314`, `cp314t` (free-threaded), and even pre-release `cp315`/`cp315t` wheels — evidence the maintainer tracks CPython pre-releases proactively. `charset-normalizer`, the other compiled dependency on the approved list itself, is in the same position. The only actionable risk is **regression**, not current unavailability: `uv lock --upgrade` could one day pick up a release that drops a wheel before a new CPython ABI is supported. That risk is best handled with a scheduled CI job, not a one-time check — see Recommendation.

## Method note — two independent measurements, and why they disagree cosmetically

This report used two independently-sourced signals per package, as required for corroboration:

1. **PyPI JSON API** (`https://pypi.org/pypi/<project>/json`), queried directly for the exact wheel filenames, platform tags, and `requires_python` metadata of each package's latest release. This is the ground truth for "can `uv`/`pip` install a wheel on CPython 3.14 today" — [official, pypi.org].
2. **pyreadiness.org / py3readiness.org** (community-maintained; explicitly the spiritual successor to `py3readiness.org` / `pythonwheels.com`), which tracks whether the **most recent release** of a package **explicitly declares** 3.14 support (via `python_requires` upper-bound removal or an added `Programming Language :: Python :: 3.14` trove classifier) [community, pyreadiness.org].

These two sources disagree on a few packages (`click`, `shellingham`, `jsonschema-specifications`, `fastjsonschema` show ✗ on pyreadiness.org) but **that disagreement is not a wheel-availability problem** — it is a metadata-declaration lag. All four ship pure-Python `py3-none-any` (or `py2.py3-none-any`) wheels with no upper Python-version bound, so they install and run on 3.14 unconditionally; the ✗ only means their maintainers have not yet bumped a classifier or `requires-python` ceiling. This distinction matters for docmend's pre-flight design: a check that only reads pyreadiness-style "declared support" would produce false-positive alarms for every pure-Python dependency in the approved set.

## Per-package wheel-availability table

| Package | Role | Latest version (as queried) | `requires_python` | Wheel type | 3.14 wheel? | pyreadiness.org | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `typer` | CLI framework | 0.26.8 (2026-06-26) | `>=3.10` | `py3-none-any` (pure Python) | Yes — universal wheel, no compiled code | ✓ | [pypi.org/project/typer](https://pypi.org/project/typer) [official]; [pyreadiness.org/3.14](http://pyreadiness.org/3.14/) [community] |
| `charset-normalizer` | Encoding detection (FR-007) | 3.4.7 (2026-04-02) | `>=3.7` | Compiled accelerator (per-platform `cp3xx` wheels) **and** a pure-Python fallback path built in | Yes — `cp314-cp314`, `cp314-cp314t` wheels for Linux/macOS/Windows | ✓ | [pypi.org/project/charset-normalizer](https://pypi.org/project/charset-normalizer) [official]; free-threading tracker lists it as already ported [py-free-threading.github.io/tracking](https://py-free-threading.github.io/tracking) [community] |
| `pathspec` | Glob include/exclude (FR-012) | 1.1.1 (2026-04-27) | `>=3.9` | `py3-none-any` (pure Python, zero deps) | Yes — universal wheel | ✓ | [pypi.org/project/pathspec](https://pypi.org/project/pathspec) [official] |
| `rich` | Console reporting | 15.0.0 (2026-04-12) | `>=3.9.0` | `py3-none-any` (pure Python) | Yes — universal wheel | ✓ | [pypi.org/project/rich](https://pypi.org/project/rich) [official] |
| `jsonschema` | JSON Schema validator (DR-005/FR-016, conditional) | 4.26.0 (2026-01-07) | `>=3.10` | `py3-none-any` (pure Python) | Yes — universal wheel | ✓ | [pypi.org/project/jsonschema](https://pypi.org/project/jsonschema) [official] |
| `referencing` | `jsonschema` dependency ($ref resolution) | 0.37.0 (2025-10-13) | `>=3.10` | `py3-none-any` (pure Python) | Yes — universal wheel | ✓ | [pypi.org/project/referencing](https://pypi.org/project/referencing) [official] |
| `jsonschema-specifications` | `jsonschema` dependency (metaschema data) | 2025.9.1 (2025-09-08) | `>=3.9` | `py3-none-any` (pure Python) | Yes — universal wheel (metadata not yet bumped) | ✗ (metadata-lag, not a real gap) | [pypi.org/project/jsonschema-specifications](https://pypi.org/project/jsonschema-specifications) [official] |
| `rpds-py` | `referencing`/`jsonschema` dependency (Rust, immutable data structures) | 2026.6.3 (2026-06-30) | `>=3.11` | Compiled, per-platform (PyO3/Rust) | Yes — `cp314`, `cp314t` (free-threaded), plus pre-release `cp315`/`cp315t` already published | ✓ | [pypi.org/project/rpds-py](https://pypi.org/project/rpds-py) [official]; PyO3 free-threading support confirmed at [pyo3.rs/v0.29.0/free-threading](https://pyo3.rs/v0.29.0/free-threading) [official/upstream] |
| `attrs` | `jsonschema`/`referencing` dependency | 26.1.0 (2026-03-19) | `>=3.9` | `py3-none-any` (pure Python) | Yes — universal wheel | ✓ | [pypi.org/project/attrs](https://pypi.org/project/attrs) [official] |
| `click` | `typer` dependency | 8.4.2 (2026-06-24) | `>=3.10` | `py3-none-any` (pure Python) | Yes — universal wheel (metadata not yet bumped) | ✗ (metadata-lag, not a real gap) | [pypi.org/project/click](https://pypi.org/project/click) [official] |
| `shellingham` | `typer` dependency (shell detection) | 1.5.4 (2023-10-24, stale) | `>=3.7` | `py2.py3-none-any` (pure Python) | Yes — universal wheel; **note:** no release since 2023, worth a maintenance-liveness watch independent of 3.14 | ✗ (metadata-lag) | [pypi.org/project/shellingham](https://pypi.org/project/shellingham) [official] |
| `annotated-doc` | `typer` dependency (PEP 727 doc annotations) | 0.0.4 (2025-11-10) | `>=3.8` | `py3-none-any` (pure Python) | Yes — universal wheel | ✓ | [pypi.org/project/annotated-doc](https://pypi.org/project/annotated-doc) [official] |
| `markdown-it-py`, `pygments`, `typing-extensions` | `rich`/`referencing` transitive deps | 4.2.0 / 2.20.0 / 4.16.0 | `>=3.10` / `>=3.9` / `>=3.9` | `py3-none-any` (pure Python) | Yes — universal wheels | ✓ / ✗ / ✓ (mixed metadata-lag) | [pypi.org](https://pypi.org) [official] |

**Fallback alternative already vetted:** `jsonschema-rs` (Rust-backed, faster, `Draft2020Support`) also already ships `cp314`/`cp314t` wheels (confirmed uploads dated 2026-06-30) — a drop-in escape hatch if the pure-Python `jsonschema` stack ever became a bottleneck, though not a wheel-_availability_ fallback since `jsonschema` itself has no compiled-wheel exposure at all [pypi.org/project/jsonschema-rs] [official].

## Compiled-dependency deep dive

Only two packages in the whole dependency+transitive graph ship platform-specific compiled wheels: **`charset-normalizer`** (approved directly) and **`rpds-py`** (transitive, via `referencing` → `jsonschema`). Both matter more than the pure-Python packages because a missing wheel forces a source build, which requires a Rust or C toolchain on every machine that runs `uv sync` — a real problem for an "offline, safety-first" tool per docmend's design constraints.

- **`charset-normalizer`** ships `cp314-cp314` and `cp314-cp314t` (free-threaded) wheels for `manylinux2014`/`manylinux_2_28`, `musllinux_1_2`, `macosx`, and `win32/win_amd64/win_arm64` — full coverage. It has also been explicitly ported for free-threaded Python per the community free-threading compatibility tracker [py-free-threading.github.io/tracking] [community]. It further ships a pure-Python fallback module, so even in the pathological case where no wheel matched a given platform, `pip`/`uv` would fall back to a functional (if slower) sdist build rather than failing outright — the project's `requires_python >=3.7` sdist has no compiled-toolchain hard requirement documented on PyPI.
- **`rpds-py`** is a PyO3 (Rust) extension. PyO3 declared official free-threaded-build support as of 0.23, and `rpds-py`'s current release already exposes `cp314`, `cp314t`, and pre-release `cp315`/`cp315t` tags — i.e., the maintainer is already building against CPython release candidates ahead of the stable 3.15 release, which is a strong signal of an actively-maintained release pipeline rather than a one-off catch-up [pyo3.rs/v0.29.0/free-threading] [official]; [pypi.org/project/rpds-py] [official]. A missing `rpds-py` wheel is the single most plausible failure mode that could break `uv sync` on a CPython version bump, because unlike `charset-normalizer` it has no documented pure-Python fallback path — `referencing`/`jsonschema` both hard-depend on `rpds-py>=0.25.0`/`>=0.7.0` with no optional-extra escape hatch.

Python 3.14 itself reached final release on **2025-10-07** per PEP 745, with the free-threaded build promoted to officially supported (Phase II) status in the same release; 3.14.6 was the latest bugfix tag confirmed by `docs.python.org` at query time, and 3.15 has already entered its alpha cycle — consistent with `rpds-py` shipping `cp315` wheels ahead of docmend's own timeline [peps.python.org/pep-0745] [official]; [docs.python.org/3/whatsnew/3.14.html] [official].

## Recommendation

1. **Record this as a tracked pre-flight check, not just a one-time finding.** Wheel availability is a point-in-time fact that can regress on any `uv lock --upgrade`. Add a dedicated CI job (or a step in the existing `check.yml` gate) that fails loudly if a `uv sync --locked` resolution would require building any package from source:

   ```yaml
   # .github/workflows/check.yml — additional step, illustrative only
   - name: Verify no source builds are required for the locked env
     run: |
       uv sync --locked --all-groups
       # `uv pip list -v` / `uv export` don't currently flag build origin directly;
       # the reliable signal is a non-zero exit / stderr from a wheel-only resolve:
       uv sync --locked --all-groups --no-build-isolation --refresh --python 3.14 \
         || { echo "::error::dependency resolution required a source build — check for a dropped 3.14 wheel"; exit 1; }
   ```

   The concrete mechanism matters less than the intent: **fail CI, not `pip install` at install time on a contributor's machine**, if any approved dependency (or its transitive graph) loses 3.14 wheel coverage. `uv`'s `--no-build-isolation` combined with a clean cache surfaces missing wheels as a hard resolution error rather than silently falling back to compiling from source (which would only be discovered later, and only on a machine that happens to lack the Rust/C toolchain).

2. **Pin a floor on `rpds-py` implicitly via `jsonschema`/`referencing`, and let `uv.lock` be the enforcement mechanism** — do not hand-pin `rpds-py` directly in `pyproject.toml` (it is not a direct dependency and pinning it separately risks drifting from what `referencing` actually supports). The existing `uv sync --locked` step in `check.yml` already prevents silent upgrades; the addition in item 1 only adds the "did the resolution need to compile" signal that `--locked` alone doesn't surface.

3. **Add one line to `docs/specs/docmend.md` §8.6** noting that the JSON Schema validator choice (currently "Conditional... confirm choice via OQ- process") should record wheel-availability as a selection criterion alongside correctness/API fit, since the field already has a viable pure-Python option (`jsonschema`) with zero compiled surface of its own and only one transitive compiled hop (`rpds-py`, currently fully covered).

4. **Fallback playbook if any package ever drops 3.14 support** (ordered by likelihood of being needed):
   - **`rpds-py` drops a CPython tag first** (most likely single point of failure): `referencing`/`jsonschema` would need a compatible `rpds-py` release before docmend's lock file could update; in the interim, pin the last-known-good `rpds-py`/`referencing`/`jsonschema` trio in `uv.lock` and open an upstream issue. `jsonschema-rs` (already confirmed 3.14/3.14t-ready) is a viable substitute validator if `jsonschema` itself stalls on a `rpds-py` incompatibility for an extended period — but this is a heavier API-surface change (see OQ-004/DR-005 for schema-validation wiring) and should not be treated as a casual swap.
   - **`charset-normalizer` drops a wheel**: lower risk given its documented pure-Python fallback; a source build here has no hard native-toolchain prerequisite documented upstream, so degraded-but-functional install is the expected worst case, not a hard failure.
   - **A pure-Python package (`typer`, `rich`, `click`, `pathspec`, `jsonschema`, `attrs`, etc.) is "unsupported"**: per the pyreadiness.org caveat above, this is virtually always a metadata-declaration lag, not an installability problem — confirm via the PyPI JSON API method in this report before treating it as an incident.
   - **`shellingham` (last released 2023-10-24)**: not a wheel-readiness risk today (pure-Python, works fine on 3.14), but its release cadence is worth a periodic liveness check independent of this report — if `typer` ever needs a shell-detection fix that only lands in a newer `shellingham`, and none arrives, that is a maintenance risk distinct from wheel availability.

## Open questions / drift note (secondary finding)

While reading `docs/open-questions.md` against `docs/specs/docmend.md` §21 for context, a spec/backlog drift was confirmed and appears larger than previously noted: **`docs/open-questions.md` fully defines OQ-012 (in-place mutation vs. separate output root), OQ-013 (frontmatter required/null/omitted/status details), and OQ-014 (real-write CLI/config opt-in)** — each with populated "Agent notes" and priority/owner/spec-reference metadata — **but the spec's own §21 "Open Questions and Decisions" table (lines ~890–906) stops at OQ-011**, and the Revision History (v0.2) changelog entry only records "OQ-011 added," with no entry for OQ-012–014. This means three fully-specified, P0/P1-priority open questions (one of them, OQ-012, marked a **P0 blocker** for the write path) are currently invisible to anyone reading the spec of record in isolation. No further drift of this shape (an OQ/GAP/FR/DR id defined in one doc but absent from its cross-referenced table) was found in the sections reviewed for this report (§8.5–§9, §18, §21), but the review here was scoped to the sections this research topic touched, not an exhaustive line-by-line audit of the whole spec.

## Reconciliation notes

- **Primary fold-back:** `docs/specs/docmend.md` §8.6 (Dependency Policy) — append a short note that all approved dependencies and their compiled transitive graph (`rpds-py`, `charset-normalizer`) are confirmed 3.14-wheel-ready as of 2026-07-05, with a pointer to this report.
- **CI fold-back:** `docs/specs/docmend.md` §18.3 (Deployment Flow / CI checks) and `.github/workflows/check.yml` — add the pre-flight wheel-availability job described in Recommendation item 1.
- **GAP-60:** this report is the closing artifact for GAP-60 as scoped by the calling workflow; since GAP-60 has no existing anchor inside this repo (not present in `docs/open-questions.md`, `docs/resolved-questions.md`, or the spec), recommend either (a) filing a new `OQ-015 — dependency wheel-readiness CI pre-flight` in `docs/open-questions.md` so it gets the same owner/priority/spec-reference tracking as OQ-001–014, or (b) if the owner considers this already "resolved" by this report, adding a corresponding entry directly to `docs/resolved-questions.md` (currently empty) rather than leaving GAP-60 unanchored.
- **Drift fold-back:** the OQ-012/013/014-missing-from-§21 finding above should be reconciled directly in `docs/specs/docmend.md` §21 (add three table rows) and in the Revision History (new v0.3 row), independent of the wheel-readiness topic — flagging it here only because it was surfaced while cross-referencing files for this report, per the task's request to look for more drift like it.

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://pypi.org/pypi/typer/json> | typer PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/charset-normalizer/json> | charset-normalizer PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/pathspec/json> | pathspec PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/rich/json> | rich PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/jsonschema/json> | jsonschema PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/referencing/json> | referencing PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/rpds-py/json> | rpds-py PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/jsonschema-specifications/json> | jsonschema-specifications PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/jsonschema-rs/json> | jsonschema-rs PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/attrs/json> | attrs PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/click/json> | click PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/shellingham/json> | shellingham PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/annotated-doc/json> | annotated-doc PyPI JSON API | queried 2026-07-05 | official |
| <https://pypi.org/pypi/ruff/json> | ruff PyPI JSON API (dev-tool cross-check; py3-none-\<platform\> binaries, ABI-independent) | queried 2026-07-05 | official |
| <https://pypi.org/pypi/coverage/json> | coverage PyPI JSON API (dev-tool cross-check; confirms cp314/cp314t precedent) | queried 2026-07-05 | official |
| <http://pyreadiness.org/3.14/> | Python 3.14 Readiness tracker | fetched 2026-07-05 | community |
| <https://py-free-threading.github.io/tracking> | Python Free-Threading Guide — Compatibility Status Tracking | fetched 2026-07-05 | community |
| <https://pyo3.rs/v0.29.0/free-threading> | PyO3 user guide — Supporting Free-Threaded Python | fetched 2026-07-05 | official (upstream project docs) |
| <https://peps.python.org/pep-0745/> | PEP 745 — Python 3.14 Release Schedule | fetched 2026-07-05 | official |
| <https://docs.python.org/3/whatsnew/3.14.html> | What's new in Python 3.14 | fetched 2026-07-05 | official |
| <https://docs.python.org/3/howto/free-threading-python.html> | Python support for free threading | fetched 2026-07-05 | official |
