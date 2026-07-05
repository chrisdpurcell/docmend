# Dependency License-Scanning Tooling and Policy for a uv/PEP 621 Project

**Date:** 2026-07-05

**Related:** `docs/specs/docmend.md` §8.6 (Dependency Policy), §16 (Compliance, Licensing, and Data Rights); `docs/open-questions.md` (no OQ- currently owns this decision — see [Reconciliation notes](#reconciliation-notes)); GAP-59 (external gap reference; not present in this repo's own tracker as of this research — see note below).

**Gap it fills:** §16 has an unchecked box — "OSS license compatibility of dependencies checked — do at MS-0 when dependencies are added (§8.6)" — but neither §16 nor §8.6 names a tool, a CI step, or a license-compatibility policy to check _against_. `pyproject.toml`'s `dev` dependency group already has `pip-audit` for vulnerability scanning but nothing for license scanning, and `.github/workflows/check.yml` has no license-check step. This report closes that gap: it compares the candidate tools named in the research question (`pip-licenses`, `licensecheck`, `deptry`, uv-native options) plus one more found during research (`liccheck`) against docmend's actual constraints (uv/PEP 621, Python 3.14, offline, public repo, MIT-licensed, currently near-zero runtime dependencies), and proposes a concrete tool, CI step, and license-compatibility policy statement ready to drop into §8.6/§16.

> Note on GAP-59: no `GAP-` identifier scheme exists anywhere in this repo (`docs/open-questions.md`, `docs/resolved-questions.md`, `docs/decisions/`, `docs/handoff/`, `TODO.md`) as of 2026-07-05. It is carried here verbatim as supplied by the calling task; treat it as an external tracker reference the owner can reconcile, not a docmend-native ID.

---

## Executive Summary

- **Recommended tool: `pip-licenses`** (PyPI: `pip-licenses`, GitHub: `raimon49/pip-licenses`, BSD-licensed). It is the only one of the four named candidates that actually does license _listing and policy gating_; it explicitly declares Python 3.13/3.14 support, needs no network access (it reads installed-package metadata locally, matching docmend's fully-offline v1 posture), works identically regardless of resolver (uv, pip, Poetry) because it only ever inspects the active virtual environment, and ships a CI-ready `--allow-only`/`--fail-on` gate with a documented non-zero exit code. [1](https://github.com/raimon49/pip-licenses) [2](https://pypi.org/project/pip-licenses/)
- **`deptry` does not do license scanning.** It is an unused/missing/transitive-dependency linter (`DEP001`–`DEP004` codes). This was independently confirmed across three sources (PyPI, `deptry.com` docs, and the GitHub repo) and needs to be corrected in how the research question framed it — it belongs in docmend's tooling as a _different_ check (dead-dependency hygiene), not as a §16 license gate. [3](https://pypi.org/project/deptry/) [4](https://deptry.com/) [5](https://github.com/osprey-oss/deptry)
- **uv has no native license-policy checker.** `uv export --format cyclonedx-json` emits a CycloneDX SBOM (including per-component license fields when available) from `uv.lock`, which is useful as an audit artifact but is not itself a pass/fail gate — a consuming tool or script would still need to enforce policy against that SBOM. [6](https://docs.astral.sh/uv/concepts/projects/export/) [7](https://github.com/astral-sh/uv/pull/16523)
- **`licensecheck` (FHPythonUtils) is a viable secondary/backstop option**, not the primary pick: it uniquely checks compatibility of a dependency's license _against the project's own declared license_ (not just a static allow-list), but it is a single-maintainer project (113 GitHub stars, 11 open issues) with a Python ≥3.12 floor (compatible with 3.14 but not as explicitly declared/tested as `pip-licenses`). [8](https://pypi.org/project/licensecheck/)
- **Policy recommendation: permissive-allow-list, copyleft-excluded-by-default, case-by-case exception via the existing OQ- process.** docmend's `pyproject.toml` declares `license = "MIT"`; combining an MIT-licensed public distribution with a GPL-family dependency forces the combined _distributed_ work under GPL terms per the FSF's own compatibility guidance — that is a real legal constraint, not just a style preference, and corroborated across the FSF-derived Wikipedia summary, a dedicated license-compatibility tool (FOSSA), and an Open Source Stack Exchange analysis. [9](https://en.wikipedia.org/wiki/GNU_General_Public_License) [10](https://fossa.com/resources/devops-tools/license-compatibility-checker/gpl-3-0-vs-mit) [11](https://opensource.stackexchange.com/questions/10365/source-only-distribution-of-mit-licensed-project-which-depends-on-gpl-library)

---

## Tool Comparison

| Tool | What it actually does | uv/PEP 621 fit | Python 3.14 | Offline? | CI gate primitive | Maintenance signal | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **`pip-licenses`** | Lists installed packages' declared licenses (Trove classifiers + Core Metadata) and can fail CI against an allow/deny list. | Resolver-agnostic — reads `importlib.metadata` from whatever venv is active, so `uv run pip-licenses` just works with a uv-managed venv; as of 5.5.0 it also reads config from `pyproject.toml`. | Explicitly declared: PyPI changelog states "Declare support for Python 3.13 and 3.14." [2](https://pypi.org/project/pip-licenses/) | Yes — pure local metadata introspection, no network call. | `--allow-only="..."` and `--fail-on="..."`, both exit code 1 on violation; `--partial-match` for substring policies. [1](https://github.com/raimon49/pip-licenses) | Active: BSD-licensed, changelog shows releases into 2026 (5.5.1–5.5.5, including a `pre-commit`/`prek` integration and a `black 26.1.0` bump), original StackOverflow recommendation dates to 2018 and the project is still the canonical answer in newer threads. [1](https://github.com/raimon49/pip-licenses) | **Recommended primary.** |
| **`licensecheck`** (FHPythonUtils) | Lists dependency licenses _and_ checks compatibility against the project's own SPDX license expression — a genuine compatibility check, not just an allow-list match. | Reads `pyproject.toml` project metadata for the "our license" side of the comparison; works with any resolver since it also inspects installed metadata. | `Requires-Python: >=3.12` — no upper bound, so 3.14 is not excluded, but (unlike `pip-licenses`) there is no explicit "we tested 3.14" changelog claim found. [8](https://pypi.org/project/licensecheck/) | Yes — local metadata only. | Exit-code based pass/fail; less battle-tested CI examples in the wild than `pip-licenses`. | Calendar-versioned (`2026.0.8`, released Jun 2026 — actively cut), but small (113 stars, 39 forks, 11 open issues, single primary maintainer) — a real bus-factor risk for a tool guarding public-repo legal exposure. [8](https://pypi.org/project/licensecheck/) | Reasonable **secondary/backstop**, not primary, given the maintenance gap versus `pip-licenses`. |
| **`liccheck` / `python-license-check` (dhatim)** | INI- or `pyproject.toml`-based "strategy file" that authorizes/forbids licenses per package, including transitive deps, with a documented forbidden-package report. | Supports `pyproject.toml`-based strategy per community reports; less first-party documentation found on uv-specific usage. | Not independently verified for 3.14 in this pass (single-source finding only — see Open Questions). | Presumed yes (same local-metadata model as the others) but not independently confirmed to the same depth. | `liccheck -s strategy.ini -r requirements.txt`, non-zero exit on forbidden packages found. | Corroborated only via one StackOverflow answer plus the project's own GitHub page in this pass — **below the report's 2-source corroboration bar for a footgun-level claim**, so treated as unverified-depth here. `[unverified-depth]` | Worth a follow-up look if `pip-licenses`' allow/deny semantics ever prove too coarse, but not adopted now. |
| **`deptry`** | Detects unused, missing, and transitive dependencies (`DEP001`–`DEP004`); explicitly supports Poetry, pip, PDM, uv, and any PEP 621 project. **Does not check licenses at all.** | Excellent fit for docmend's uv/PEP 621 setup for its _actual_ purpose. | Actively maintained, dropped Python 3.8/3.9 support as they reached EOL — a signal of an actively curated support matrix. [12](https://deptry.com/CHANGELOG/) | Yes — static import analysis. | N/A for licensing. | Active (0.25.1, uploaded via `uv publish` in its own release metadata). [13](https://pypi.org/project/deptry/) | **Not a license tool — do not route the §16 gate through it.** Independently confirmed via PyPI, `deptry.com`, and the GitHub README, all three describing it purely as a dependency-hygiene linter. [3](https://pypi.org/project/deptry/) [4](https://deptry.com/) [5](https://github.com/osprey-oss/deptry) Consider it separately for a _different_ future CI check (dead/misplaced dependency hygiene), out of scope for this report. |
| **uv-native (`uv export --format cyclonedx-json`)** | Exports `uv.lock` as a CycloneDX v1.5 SBOM, which includes license fields per component when the underlying package metadata has them. | First-party, zero extra dependency — it is a `uv` subcommand. | N/A (uv itself, not a Python-version-gated tool). | Yes — reads the local lockfile. | None built in — the SBOM is data, not a policy gate; something else (a script, or a CycloneDX-aware tool) has to walk the SBOM and enforce an allow-list. [6](https://docs.astral.sh/uv/concepts/projects/export/) | uv is Astral's flagship tool, extremely active; SBOM export landed via a reviewed, merged PR. [7](https://github.com/astral-sh/uv/pull/16523) | **Good as an audit trail / provenance artifact, not as the enforcement tool.** Third-party CycloneDX tooling (`cyclonedx-python`, community `uv-sbom`) exists to consume it, but none of them are license-policy gates either — they generate the same SBOM by a different path. [14](https://github.com/CycloneDX/cyclonedx-python) [15](https://github.com/Taketo-Yoda/uv-sbom) |
| **`pip-audit`** (already a docmend dev dependency) | Scans for known _vulnerabilities_ (CVEs) via the PyPI Advisory Database. | Already wired into `.github/workflows/check.yml`. | N/A — unrelated axis. | No — needs the PyPI Advisory Database, i.e., network access at CI time (this is a pre-existing property of the already-adopted tool, not a new offline regression). | N/A for licensing — confirmed it has no license-check feature of its own. [16](https://appsecsanta.com/sca-tools/sca-tools-for-python) | Actively maintained by PyPA/Trail of Bits. [17](https://pypi.org/project/pip-audit) | **Keep for its existing job (CVEs); do not conflate with license scanning.** It is, however, the natural CI-step neighbor for a new license-check step — same job, same `uv run` pattern. |

---

## Recommendation

Add `pip-licenses` to the existing `dev` dependency group and wire it as a new step in `.github/workflows/check.yml`, immediately after the existing `pip-audit` step, mirroring that step's `uv run` pattern exactly (`check.yml` line 47-48 today):

```toml
# pyproject.toml — [dependency-groups] dev, alongside the existing pip-audit entry
dev = [
    "basedpyright",
    "coverage[toml]",
    "pip-audit",
    "pip-licenses",
    "pytest>=9.0",
    "ruff>=0.14",
]
```

```yaml
# .github/workflows/check.yml — new step after "Dependency audit"
- name: Dependency license check
  run: >
    uv run pip-licenses --allow-only="MIT License;MIT;BSD License;BSD-2-Clause;BSD-3-Clause;Apache Software License;Apache-2.0;Apache License 2.0;ISC License (ISCL);Python Software Foundation License;The Unlicense (Unlicense)"
```

Rationale for `--allow-only` over `--fail-on`: `--allow-only` fails closed on _any_ license not on the list, including a license nobody has seen yet — which mirrors §8.6's existing philosophy ("introducing a dependency not listed here requires an OQ- entry and owner approval"). `--fail-on` only fails closed on licenses explicitly named as forbidden, which would silently allow an unrecognized copyleft variant through. Given docmend is a public repo distributing installable code under MIT, fail-closed is the safer default. [1](https://github.com/raimon49/pip-licenses)

`licensecheck` is worth keeping in reserve (not adopted now) if the allow-list ever needs true SPDX-expression compatibility checking (e.g., dual-licensed or compound-expression dependencies) rather than string matching against classifier text — `pip-licenses`' `--from=all` mode also matches against the PEP 639 SPDX `license` metadata field when classifiers are absent, which narrows this gap somewhat but is not a full compatibility engine. [1](https://github.com/raimon49/pip-licenses)

Do not route this check through `deptry` (wrong tool, no license feature) or through `uv export --format cyclonedx-json` alone (produces data, not a gate) — though the SBOM export is worth generating once per release as a provenance artifact for §16/§18.7 documentation deliverables, since it costs nothing extra and gives a permanent point-in-time record of exactly what shipped.

---

## Proposed Policy Statement (for §16 / §8.6)

Add to **§8.6 Dependency Policy** (after the existing table):

> **License policy:** All runtime and dev-group dependencies must carry a license on the permissive allow-list below, verified in CI by `pip-licenses --allow-only=...` on every PR and push to `main`. A dependency whose license is not on the list may not be added without an OQ- entry and owner approval (same gate already required in this section for any new dependency), which must record the SPDX identifier, the rationale for the exception, and whether the exception is runtime-only or dev-only (dev-only dependencies carry materially lower distribution risk since they are never shipped to end users of the built package).
>
> **Allow-list (permissive, OSI-approved):** MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, Python Software Foundation License (PSF), Unlicense/CC0.
>
> **Excluded by default (copyleft family):** GPL-2.0, GPL-3.0, AGPL-3.0, LGPL-2.1, LGPL-3.0, MPL-2.0, EPL-2.0, and any license not on the allow-list. Rationale: docmend's own `pyproject.toml` declares `license = "MIT"` and the project is publicly distributed; combining an MIT-licensed public distribution with a GPL-family dependency obliges the _combined distributed work_ to be released under GPL terms, per the FSF's own compatibility position — that is a licensing-model change, not a style choice, and is out of scope for a personal-library CLI tool. [9](https://en.wikipedia.org/wiki/GNU_General_Public_License) [10](https://fossa.com/resources/devops-tools/license-compatibility-checker/gpl-3-0-vs-mit) LGPL/MPL are weak-copyleft and _may_ be viable case-by-case (e.g., unmodified import-only use), but Python's import model makes the "linking" analysis genuinely ambiguous compared to C-style dynamic linking, so treat them as case-by-case, not auto-allow. [11](https://opensource.stackexchange.com/questions/10365/source-only-distribution-of-mit-licensed-project-which-depends-on-gpl-library)
>
> **Case-by-case path:** Any exception (including LGPL/MPL) goes through the existing OQ- process already required for out-of-list dependencies; the owner is the sole approver, matching current §8.6 wording.

Update **§16 Compliance, Licensing, and Data Rights**, replacing the unchecked box:

> - [ ] OSS license compatibility of dependencies checked — do at MS-0 when dependencies are added (§8.6).

with:

> - [ ] OSS license compatibility of dependencies checked via `pip-licenses --allow-only=...` in CI (§8.6); policy is permissive-allow-list with copyleft excluded by default and case-by-case owner exception via the OQ- process.

---

## Security and Compatibility

- `pip-licenses` itself is BSD-licensed and has no known open CVEs surfaced in this research pass; it performs no network I/O, which keeps it aligned with docmend's "no external services in v1" constraint (§8.6, §18.1). [1](https://github.com/raimon49/pip-licenses)
- `pip-audit` (already adopted) _does_ require network access to query the PyPI Advisory Database — this is a pre-existing property unrelated to this research question, noted here only because it is the CI-step neighbor being proposed; it does not change with this recommendation. [16](https://appsecsanta.com/sca-tools/sca-tools-for-python) [17](https://pypi.org/project/pip-audit)
- Neither `pip-licenses` nor `licensecheck` performs transitive-dependency _vulnerability_ scanning — that remains `pip-audit`'s job; the two checks are complementary, not overlapping.

## Recent Changes

- `pip-licenses` 5.5.0 added `pyproject.toml`-driven configuration and a `License-Expression`/`--from=expression` mode that reads the PEP 639 SPDX `license` field directly, reducing reliance on (sometimes absent) Trove classifiers. [1](https://github.com/raimon49/pip-licenses)
- `uv`'s CycloneDX SBOM export (`uv export --format cyclonedx-json`) is a comparatively new first-party feature (merged via PR #16523); it is the closest thing to a "uv-native option" the research question asked about, but it is an export, not a policy gate. [7](https://github.com/astral-sh/uv/pull/16523)
- PEP 639's `license`/`license-files` SPDX-expression format (already used correctly in docmend's own `pyproject.toml`: `license = "MIT"`) is now supported by `uv_build` (≥0.7.19) and all major build backends, which is what makes SPDX-expression-aware tools like `pip-licenses --from=expression` and `licensecheck` viable going forward instead of relying on legacy Trove classifiers. [18](https://packaging.python.org/en/latest/guides/writing-pyproject-toml)

## Open Questions

| # | Question | Why unresolved |
| --- | --- | --- |
| 1 | Does `liccheck`/`python-license-check` (dhatim) support Python 3.14 and offer meaningfully different CI ergonomics from `pip-licenses`? | Only corroborated by one StackOverflow answer and the project's own GitHub page in this pass — below this report's 2-source bar for a firm recommendation. |
| 2 | Should the license-check step also run against dev-group-only dependencies, or runtime-only? | The proposed policy statement above defaults to "both, but records exception type," but the owner may prefer a runtime-only gate since dev tools are never distributed to end users of the built package. |
| 3 | What is the correct disposition of `GAP-59`? | No `GAP-` tracker exists anywhere in this repo; the identifier could not be cross-referenced locally (see note under Gap it fills). |

---

## Reconciliation notes

This report answers a decision that currently has **no owning OQ-** in `docs/open-questions.md` — §16's unchecked "OSS license compatibility... checked" box and §8.6's dependency-policy table are the only spec anchors. Recommend the owner either (a) fold the proposed policy statement directly into §8.6/§16 as drafted above and check the §16 box once the CI step lands, or (b) open a new `OQ-015 — dependency license-scanning tool and policy` if a decision round is wanted first (this report's Recommendation section would serve as that OQ's "Agent notes"). Either way, this is also the moment to fix the separately-discovered drift: `docs/open-questions.md` already defines `OQ-012`, `OQ-013`, and `OQ-014`, but the spec's own §21 table (`docs/specs/docmend.md` lines ~896-906) stops at `OQ-011` — those three open questions are currently invisible to the spec of record and should be added to the §21 table in the same pass that reconciles this report's findings, regardless of whether a new `OQ-015` is opened.

---

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://github.com/raimon49/pip-licenses> | pip-licenses (GitHub) | accessed 2026-07-05 | [official] |
| <https://pypi.org/project/pip-licenses/> | pip-licenses (PyPI) | accessed 2026-07-05 | [official] |
| <https://pypi.org/project/deptry/> | deptry (PyPI) | accessed 2026-07-05 | [official] |
| <https://deptry.com/> | deptry docs | accessed 2026-07-05 | [official] |
| <https://github.com/osprey-oss/deptry> | deptry (GitHub) | accessed 2026-07-05 | [official] |
| <https://docs.astral.sh/uv/concepts/projects/export/> | Exporting a lockfile — uv docs | accessed 2026-07-05 | [official] |
| <https://github.com/astral-sh/uv/pull/16523> | uv PR #16523: Add SBOM export support | accessed 2026-07-05 | [official] |
| <https://pypi.org/project/licensecheck/> | licensecheck (PyPI) | accessed 2026-07-05 | [official] |
| <https://en.wikipedia.org/wiki/GNU_General_Public_License> | GNU General Public License — Wikipedia (FSF-sourced compatibility claims) | accessed 2026-07-05 | [community] |
| <https://fossa.com/resources/devops-tools/license-compatibility-checker/gpl-3-0-vs-mit> | Is GPL 3.0 compatible with MIT? — FOSSA | accessed 2026-07-05 | [community] |
| <https://opensource.stackexchange.com/questions/10365/source-only-distribution-of-mit-licensed-project-which-depends-on-gpl-library> | Source-only distribution of MIT project depending on GPL library — Open Source Stack Exchange | accessed 2026-07-05 | [community] |
| <https://github.com/dhatim/python-license-check> | liccheck / python-license-check (GitHub) | accessed 2026-07-05 | [unverified] |
| <https://stackoverflow.com/questions/19086030/can-pip-or-setuptools-distribute-etc-list-the-license-used-by-each-install> | StackOverflow: listing installed-package licenses | accessed 2026-07-05 | [community] |
| <https://deptry.com/CHANGELOG/> | deptry CHANGELOG | accessed 2026-07-05 | [official] |
| <https://appsecsanta.com/sca-tools/sca-tools-for-python> | Best SCA Tools for Python (2026) | accessed 2026-07-05 | [blog] |
| <https://pypi.org/project/pip-audit> | pip-audit (PyPI) | accessed 2026-07-05 | [official] |
| <https://github.com/CycloneDX/cyclonedx-python> | cyclonedx-python (GitHub) | accessed 2026-07-05 | [official] |
| <https://github.com/Taketo-Yoda/uv-sbom> | uv-sbom (community, GitHub) | accessed 2026-07-05 | [community] |
| <https://packaging.python.org/en/latest/guides/writing-pyproject-toml> | Writing your pyproject.toml — Python Packaging User Guide (PEP 639) | accessed 2026-07-05 | [official] |
