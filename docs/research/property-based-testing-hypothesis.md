# Property-Based Testing Library for Transform Purity and Edge Cases

**Date:** July 5, 2026 **Related:** GAP-50 · proposed OQ-015 (new) · `docs/specs/docmend.md` §7.2 NFR-005, §8.6, §17.2, §17.3 (FR-007–FR-009, NFR-005), §21 · `docs/open-questions.md` (drift check: OQ-012–OQ-014)

**Gap it fills:** docmend's own spec requires "property-based tests where cheap" for the pure Transform layer (§17.2) and makes transform purity a first-class non-functional requirement (NFR-005), but no property-based testing library has ever been evaluated or approved — §8.6's dependency table is silent on test tooling entirely, and Appendix B.2 requires an `OQ-` for any dependency introduced "outside §8.6." That rule is already being violated by omission: `pytest`, `ruff`, `basedpyright`, `coverage[toml]`, and `pip-audit` sit in `pyproject.toml`'s `dev` group today with no §8.6 row and no approving `OQ-`. This report (a) evaluates Hypothesis as the property-based testing candidate, (b) quantifies what adopting it actually costs (dependency footprint, CI behavior, Python 3.14 support), and (c) proposes a concrete §8.6 addition plus an `OQ-` entry that resolves both the tooling decision and the standing process contradiction in the same move — while also documenting a second instance of the same contradiction found during this research (see "Known drift" below).

---

## Recommendation

**Adopt `hypothesis` as a dev-only test dependency**, scoped to the pure Transform layer (§8.1 step 3: encoding, newline, and whitespace normalization — FR-007–FR-009) and to planning/risk-classification decision tests (§17.2 "Unit / domain" row). No serious alternative exists for Python in 2026: Hypothesis is the dominant, actively maintained property-based testing library, ships native wheels for CPython 3.14 as of its most recent release (four days before this report), has a near-zero always-installed dependency footprint, and its integration model (pytest-native `@given` decorator, automatic shrinking to a minimal failing example, an on-disk failure database) maps directly onto docmend's own stated testing philosophy: cheap, pure, deterministic transform tests that build a growing weird-document regression corpus (§17.2 Regression row, R-006).

Treat this as a **dev/test-only** dependency: it must never appear in `[project.dependencies]` or ship in the built wheel/sdist, only in `[dependency-groups].dev`.

---

## Why Hypothesis (justification)

- **Purpose-built for exactly docmend's Transform-layer contract.** NFR-005 requires transforms to be pure functions (text in, text out) tested with no filesystem access. That is Hypothesis's ideal use case: `@given(st.text())`-style generation over pure string transforms, with no I/O, no mocking, and fast execution. The spec's own §17.2 table already names "property-based tests" for this layer — this report closes the "which library" gap left open by that line. [official](https://hypothesis.readthedocs.io/en/latest/quickstart.html)
- **Maturity and adoption.** The peer-reviewed JOSS paper on Hypothesis documents production use (100,000+ weekly downloads at time of publication, adoption across numpy and astropy, and 4%+ of Python users in a PSF survey reporting use) — independent, citable evidence this is not a niche tool. [official/academic](https://joss.theoj.org/papers/10.21105/joss.01891.pdf)
- **Shrinking is a direct fit for the weird-document corpus workflow.** §17.2's Regression row and R-006 both call for a continuously grown "weird-document corpus" of anomaly classes. Hypothesis's defining feature — reducing a failing random example down to the simplest reproducing case — turns every property-test failure into a ready-made minimal fixture candidate for that corpus, rather than requiring an engineer to hand-craft one. [official](https://hypothesis.readthedocs.io/)
- **Pytest-native, not a separate framework.** A Hypothesis test is a normal `pytest` test function; the project's locked toolchain (`pytest` + `coverage`, per `docs/handoff/conventions.md`) needs zero changes to run Hypothesis tests, and Hypothesis ships its own pytest plugin (enabled by default) for statistics, seed replay, and profile selection. [official](https://hypothesis.readthedocs.io/en/latest/details.html)

## Alternatives considered

| Alternative | Verdict | Why |
| --- | --- | --- |
| Hand-rolled fuzz loops (stdlib `random` + `for _ in range(N)`) | Rejected | No shrinking (failures report the raw random input, not a minimal case), no failure-replay database, no pytest integration, no seed-based CI reproducibility — more code to maintain for a strictly worse result. |
| `pytest-quickcheck` | Rejected | No evidence of active maintenance or Python 3.14 support found during this research; effectively superseded by Hypothesis years ago in the Python ecosystem. |
| Schemathesis | Not applicable | Built on top of Hypothesis for OpenAPI/HTTP-schema-driven fuzzing; docmend has no HTTP API or UI surface (§11 states this explicitly) — there is no schema for it to fuzz against. [blog](https://qaskills.sh/blog/hypothesis-property-based-testing-python-guide) |
| CrossHair | Deferred, not a v1 need | A symbolic-execution-based alternative/complement; Hypothesis itself ships a `hypothesis[crosshair]` extra to use it as an alternate backend rather than requiring a separate framework choice. [official](https://pypi.org/project/hypothesis/) |

**Conclusion:** this is not a close call between competing libraries — it is "Hypothesis, or hand-roll something strictly weaker." The decision that actually needs an `OQ-` is _whether to adopt property-based testing at all as a dependency_, not _which one_.

---

## Cost of Adoption

### Dependency footprint

- **License:** `hypothesis` is MPL-2.0 (Mozilla Public License 2.0, a weak/file-level copyleft license), per its own PyPI metadata. [official](https://pypi.org/project/hypothesis/) MPL-2.0's copyleft obligations attach to modifications of MPL-covered files themselves, not to separate works that merely depend on the library, and as a dev-only test dependency it is never bundled into docmend's own MIT-licensed distributed artifact. This is a case the existing but currently unchecked §16 checklist item ("OSS license compatibility of dependencies checked — do at MS-0") should formally confirm rather than this report asserting a legal conclusion.
- **Transitive runtime dependencies are minimal and mostly Python-version-gated.** Current release metadata lists `sortedcontainers` (MIT-licensed, sorted-collections library) as an always-installed dependency, with `exceptiongroup` and `tzdata` as version/platform-conditional backports. [community](https://pypistats.org/packages/hypothesis) Since docmend requires Python 3.14+ (`requires-python = ">=3.14"` in `pyproject.toml`), the `exceptiongroup` backport (needed only pre-3.11) is irrelevant, and `tzdata` only matters if tests use timezone-aware generation strategies on a platform lacking a system IANA database (chiefly Windows) — docmend's stated runtime is a Linux workstation (§18.1), so this is a non-issue in practice.
- **Package size is trivial.** Independent distro-packaging data records roughly a 1 MB download / ~6 MB installed footprint — negligible next to a CI image or `.venv`. [community](https://packages.cachyos.org/package/extra/any/python-hypothesis)
- **Type-checking compatibility (BasedPyright strict).** Hypothesis added static type annotations to its public API years ago and documents this as an explicit compatibility target; it satisfies the PEP 561 "typed library" bar that BasedPyright's strict mode expects from third-party dependencies. [official](https://github.com/HypothesisWorks/hypothesis/issues/200) · [official](https://docs.basedpyright.com/latest/usage/typed-libraries)

### Python 3.14 support

- Hypothesis 6.156.0, released 2026-07-01 — four days before this report — publishes native wheels for **Python 3.10, 3.11, 3.12, 3.13, 3.14, 3.14t (free-threaded), and PyPy 3.11** across Linux (manylinux/musllinux) x86_64/aarch64, macOS x86_64/arm64, and Windows x64. [official](https://hypothesis.readthedocs.io/en/latest/changelog.html) This directly matches docmend's runtime floor (`requires-python = ">=3.14"`) with current, first-class support rather than a lagging-adopter risk.
- **Build-from-source caveat, flagged for completeness:** the same release begins migrating internal Hypothesis engine code to Rust and now requires a Rust toolchain to build from source when no matching prebuilt wheel is available (e.g., PyPy 3.11 wheels are explicitly published "except on musllinux" per the changelog). For docmend's stated Linux workstation environment this is a non-issue today because prebuilt wheels exist for the target platform, but it is worth recording as a watch item if docmend's CI ever runs on an unsupported wheel platform. [official](https://hypothesis.readthedocs.io/en/latest/changelog.html)

### CI time and behavioral cost

- **Default example count is bounded, not unbounded.** `@given`-decorated tests run 100 examples by default; for docmend's pure, microsecond-scale string transforms (newline/whitespace/encoding normalization) this is expected to be cheap, but the cost is configurable both directions via `settings.register_profile` / `settings.load_profile`, including loading a profile name from an environment variable — the documented pattern is a small "fast" profile for local iteration and a separate profile (more or fewer examples) for CI. [official](https://hypothesis.readthedocs.io/en/latest/settings.html)
- **`deadline`-driven flakiness on shared/noisy CI runners is a real, corroborated footgun.** Hypothesis enforces a per-example wall-clock `deadline` by default; the library's own engineering writeup documents that CI test-run times are not perfectly repeatable, which can make a test intermittently report `DeadlineExceeded` purely from runner timing noise, not a real regression. [official](https://hypothesis.works/articles/threshold-problem/) A second, independent account from an early production adopter describes the same class of CI-timing flakiness in practice and how seed-based replay was used to diagnose it. [official](https://hypothesis.works/articles/smarkets/) Mitigation is documented and simple: loosen or disable `deadline` in the CI settings profile.
- **`HealthCheck.function_scoped_fixture` is a correctness footgun, not just a performance one.** Hypothesis's own settings/health-check documentation warns that a pytest function-scoped fixture used inside a `@given` test resets once per _test_, not once per _generated example_ — a subtle trap for anyone assuming fixture isolation per Hypothesis-generated case. [official](https://hypothesis.readthedocs.io/en/latest/settings.html) This is directly relevant to docmend's Transform-layer tests, which should generally avoid fixtures entirely given NFR-005's "no filesystem access" pure-function framing — the footgun mostly disappears if transform tests stay fixture-free as designed.
- **A local, stateful example database is written by default.** Failing (and previously-explored) examples are persisted to `.hypothesis/examples/` via `DirectoryBasedExampleDatabase` in the current working directory unless configured otherwise. [official](https://hypothesis.readthedocs.io/en/latest/settings.html) This needs an explicit project decision (gitignore vs. commit for reproducibility across CI runs) — recommend gitignoring it for docmend, since CI failures are already reproducible via the printed `--hypothesis-seed`, and a committed database risks becoming a source of stale, environment-specific noise in a public repo.
- **Reproducibility fits docmend's "no manual review" operating model.** On a CI failure, Hypothesis prints the failing example and a seed that can reproduce it locally with `--hypothesis-seed`; this is a good match for NFR-003 (diagnosable from reports/logs alone) and G-005 (nothing silently guessed). [official](https://hypothesis.readthedocs.io/en/latest/details.html) · [official](https://hypothesis.works/articles/smarkets/)
- **Parallel test execution is explicitly supported and self-tested by the library.** `pytest -n auto` style parallelism is documented as regularly exercised in Hypothesis's own CI, relevant if docmend's test suite grows large enough (100k-file synthetic corpus tests, §14/NFR-001) to need parallel runners. [official](https://hypothesis.readthedocs.io/en/latest/details.html)

**Net CI-cost assessment:** low. The transforms docmend needs to property-test (FR-007–FR-009) are pure, in-memory, sub-millisecond operations, so the realistic added wall-clock cost is small and tunable via settings profiles; the actual risk is process (an unmanaged `deadline` default causing occasional flaky CI on noisy runners), not raw runtime, and that risk has a documented, one-line mitigation.

---

## Fit against docmend's specific test surface

- **Directly serves §17.2's "Unit / domain" row** for pure transforms (encoding, newlines, whitespace) and planning/risk-classification decisions — the row that already names "property-based tests where cheap" without naming a library.
- **Concrete candidate properties for MS-2** (FR-007–FR-009):
  - Newline normalization: idempotence (`normalize(normalize(x)) == normalize(x)`); no CR/CRLF byte sequence survives in output.
  - Whitespace transforms: trailing-whitespace trim never touches non-trailing whitespace; blank-line collapse never increases a blank-run's length; final-newline enforcement is idempotent.
  - Encoding normalization: output is always valid UTF-8 without BOM for any input accepted above the confidence threshold (EC-007).
- **Not a fit for the Writer layer.** Atomic-write, backup, and manifest tests are inherently filesystem-touching (§8.3 Writer component) and belong in the integration/adapter tier, not the pure-property tier — Hypothesis's `stateful testing` (`RuleBasedStateMachine`) could in principle model the per-file state machine in §10.4 later, but that is a larger adoption step beyond this OQ's scope and is flagged here only as a possible future extension, not a v1 requirement.

---

## Existing Tools

| Tool | Maintenance | Fit for docmend | License |
| --- | --- | --- | --- |
| Hypothesis | Active; frequent releases, day-of Python 3.14 wheel support | Strong — pytest-native, matches §17.2/NFR-005 directly | MPL-2.0 |
| pytest-quickcheck | No evidence of current maintenance found | Poor — stale, no confirmed Python 3.14 support | Unverified |
| Schemathesis | Active; built on Hypothesis | Not applicable — API/schema fuzzer; docmend has no HTTP API (§11) | MIT |
| CrossHair | Active, smaller community | Complementary optional Hypothesis backend (`hypothesis[crosshair]`), not a v1 need | Apache-2.0-family (verify at adoption time if ever used) |

---

## Security and Compatibility

- MPL-2.0 dependency, dev-only, never distributed with docmend's MIT-licensed package — confirm formally via the existing but unchecked §16 license-compatibility checklist item at MS-0. [official](https://pypi.org/project/hypothesis/)
- No known CVEs surfaced in this research pass; `pip-audit` (already a locked dev dependency, §8.6-adjacent tooling) will cover ongoing vulnerability scanning once `hypothesis` is added, consistent with existing project practice.
- Native-wheel platform coverage (Linux x86_64/aarch64, macOS, Windows) matches docmend's stated single-Linux-workstation runtime with margin to spare. [official](https://hypothesis.readthedocs.io/en/latest/changelog.html)

## Recent Changes

- **6.156.0 (2026-07-01):** start of an internal Python→Rust migration for engine internals; now requires a Rust toolchain to build from source absent a matching wheel; publishes native wheels including Python 3.14 and 3.14t. [official](https://hypothesis.readthedocs.io/en/latest/changelog.html)
- **"The Hypothesis Corpus" (2026-04-14):** the maintainers published a dataset of ~29,000 real-world Hypothesis tests across 1,529 repositories, described as reflecting Hypothesis's status as the most widely used property-based testing library for Python — useful corroborating evidence of ecosystem maturity, though self-published by the project. [official](https://hypothesis.works)

---

## Proposed §8.6 addition

Add a dev/test-only dependency to the existing Dependency Policy table (§8.6), and note the scope of that table explicitly for future entries:

| Dependency | Allowed? | Reason |
| --- | --- | --- |
| `hypothesis` (dev/test only) | Conditional — pending OQ-015 | Property-based testing for pure Transform-layer functions (NFR-005) and edge-case generation (§17.2); a dev-dependency only, never shipped in the built wheel/sdist. |

Recommend §8.6 also gain an explicit "Runtime (shipped) vs. Dev/Test (not shipped)" split, since the table currently reads as runtime-only in practice (`typer`, `charset-normalizer`, `pathspec`, `rich`, `tomllib`, conditional `jsonschema`) while Appendix B.2's "no dependency outside §8.6" rule is written to cover _all_ dependencies — a scope mismatch this OQ should close for good, not just for `hypothesis`.

## Proposed OQ-015 entry

For `docs/open-questions.md` (and, per the reconciliation notes below, a corresponding row restored in spec §21):

> ### OQ-015 — property-based testing dependency for transform tests
>
> **Priority:** P2 decision **Owner:** owner **Needed by:** MS-2 (pure-transform tests) **Spec references:** `docs/specs/docmend.md` §7.2 NFR-005, §8.6, §17.2, §17.3 FR-007–FR-009/NFR-005, §21
>
> Approve `hypothesis` as a dev-only test dependency for property-based tests over the pure Transform layer (§8.1 step 3), and record it in §8.6 to close the standing process gap in which `pytest`/`ruff`/`basedpyright`/`coverage[toml]`/`pip-audit` already sit in `pyproject.toml`'s `dev` group without an §8.6 row or an approving OQ-.
>
> #### Agent notes
>
> **Recommendation:** Approve `hypothesis` as a dev-only dependency; add it to `[dependency-groups].dev` in `pyproject.toml` once approved, and add the §8.6 row proposed above. In the same edit, resolve the broader process gap: split §8.6 into explicit "Runtime (shipped)" and "Dev/Test (not shipped)" sections, and grandfather the five pre-existing dev tools into the Dev/Test list so Appendix B.2's rule is actually satisfied by the current `pyproject.toml`, not merely by new additions going forward.
>
> **Supporting information:** `docs/research/property-based-testing-hypothesis.md` — Hypothesis ships native wheels for Python 3.10–3.14 (+3.14t) as of 6.156.0 (2026-07-01); its only always-installed runtime dependency is `sortedcontainers` (MIT); it is MPL-2.0 licensed but dev-only (never distributed in docmend's own package); it is the dominant, actively maintained property-based testing library for Python with native pytest integration and a documented settings-profile mechanism for tuning CI cost.
>
> **Reasoning:** This is a genuinely new, unlisted dependency per §8.6's own rule, so Appendix B.2's process requires an `OQ-` regardless of how uncontroversial the library choice is. Resolving it in the same pass also fixes a live, pre-existing process contradiction (dev dependencies already present without OQs) rather than letting the gap recur on every future dev-tool addition.
>
> **Decision impact:** Unblocks writing property-based tests for FR-007–FR-009 transforms in MS-2, matching that milestone's own exit criteria ("transforms pass unit/property tests," §19 Milestone Summary); establishes a reusable Runtime-vs-Dev/Test §8.6 pattern for future dependency OQs (see the `jsonschema` gap noted below).
>
> #### My Comments
>
> _(owner fills in)_

---

## Known drift (verified) + one more spotted

- **Confirmed, as flagged by the task:** `docs/open-questions.md` fully defines **OQ-012** (in-place mutation vs. separate output root, P0 blocker), **OQ-013** (frontmatter required/null/omitted/status details, P1), and **OQ-014** (real-write CLI/config opt-in, P1) — complete headings, priorities, and "Agent notes" sections all present (lines 371–456 of that file) — but `docs/specs/docmend.md` §21's own tracking table (lines 894–906) enumerates only **OQ-001 through OQ-011**. OQ-012–OQ-014 are therefore invisible to anyone reading the spec of record's own open-questions summary, despite carrying priorities up to P0 blocker.
- **A second instance of the same category of gap, spotted while researching this OQ:** §8.6's dependency table already flags one dependency as pending an `OQ-` that has never actually been opened — the "JSON Schema validator (e.g. `jsonschema`)" row says "Conditional... confirm choice via OQ- process," but no `OQ-` row (numbered or otherwise) exists for that decision in either `open-questions.md` or spec §21. This is structurally the same problem this report was commissioned to fix for `hypothesis`: an §8.6-flagged dependency decision with no corresponding `OQ-` artifact. Recommend closing it in the same maintenance pass as OQ-015, either as a new `OQ-016` or folded into the DR-005/FR-016 frontmatter-validation implementation planning once that work starts.

---

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://hypothesis.readthedocs.io/en/latest/changelog.html> | Changelog — Hypothesis 6.156.0 | 2026-07-01 | official |
| <https://hypothesis.works> | Hypothesis (project homepage, "The Hypothesis Corpus") | 2026-04-14 | official |
| <https://joss.theoj.org/papers/10.21105/joss.01891.pdf> | Hypothesis: A new approach to property-based testing (JOSS) | 2019 (accessed 2026-07-05) | official/academic |
| <https://pypi.org/project/hypothesis/> | hypothesis · PyPI | accessed 2026-07-05 | official |
| <https://pypistats.org/packages/hypothesis> | hypothesis · pypistats (dependency list) | accessed 2026-07-05 | community |
| <https://packages.cachyos.org/package/extra/any/python-hypothesis> | python-hypothesis package metadata | accessed 2026-07-05 | community |
| <https://hypothesis.readthedocs.io/en/latest/settings.html> | API Reference — Settings (deadline, health checks, database) | accessed 2026-07-05 | official |
| <https://hypothesis.readthedocs.io/en/latest/details.html> | Details and advanced features (parallel runs, seed replay) | accessed 2026-07-05 | official |
| <https://hypothesis.readthedocs.io/en/latest/quickstart.html> | Quickstart | accessed 2026-07-05 | official |
| <https://hypothesis.works/articles/threshold-problem/> | The Threshold Problem (deadline flakiness) | undated, pre-2026 | official |
| <https://hypothesis.works/articles/smarkets/> | Smarkets's funding of Hypothesis (CI seed-replay account) | undated, pre-2026 | official |
| <https://github.com/HypothesisWorks/hypothesis/issues/200> | Add static typing to Hypothesis API | historical | official |
| <https://docs.basedpyright.com/latest/usage/typed-libraries> | Typed libraries — basedpyright | accessed 2026-07-05 | official |
| <https://qaskills.sh/blog/hypothesis-property-based-testing-python-guide> | Hypothesis: Property-Based Testing in Python (2026) | 2026 | blog |
| <https://dev.to/ayinedjimi-consultants/pytest-vs-unittest-vs-hypothesis-python-testing-frameworks-in-2026-bc2> | Pytest vs unittest vs hypothesis: Python testing frameworks in 2026 | 2026 | blog |

**Queries:** 8 · **Results parsed:** ~35 · **Deep reads:** 5 (Hypothesis changelog, settings docs, details docs, JOSS paper abstract/content, PyPI page) · **Follow-up pass:** no (all six research angles reached 2+ distinct sources on the first pass)

---

## Reconciliation notes

Fold this report's findings back into:

- **`docs/specs/docmend.md` §8.6** — add the `hypothesis` (dev/test-only) row above; consider splitting the table into Runtime vs. Dev/Test sections in the same edit.
- **`docs/specs/docmend.md` §21** — add the new **OQ-015** row, and, per the confirmed drift above, restore the missing **OQ-012, OQ-013, OQ-014** rows that already exist in `docs/open-questions.md` but are absent from this table (same maintenance pass; do not treat as two separate edits).
- **`docs/open-questions.md`** — add the full **OQ-015** entry per the template above; optionally add **OQ-016** for the still-ungated `jsonschema` validator dependency noted under "Known drift."
- **`docs/deep-research-queue.md`** — add this report to the "Existing docmend research reports" table with "Reconciled into" pointing at §8.6 and §21/open-questions.md once the above edits land.
- **`pyproject.toml`** — add `hypothesis` to `[dependency-groups].dev` only after OQ-015 is approved by the owner; this research report does not modify project source or dependencies itself.
