# Code Simplification Review

## Header

- Run status: `completed`
- **Repository:** `docmend` at `/home/chris/projects/docmend`
- **Anchored SHA:** `834f07515a5308edd2d6c97f1cf940233c2e6b01`
- **UTC review date:** 2026-07-22
- **Actual report path:** `/home/chris/projects/docmend/docs/reviews/2026-07-21-code-simplification.md`
- **Git:** 2.55.0; non-bare repository root; branch `chore/project-standards-v5-migration`
- **Environment:** CPython 3.14.6; uv 0.11.6; Pydantic 2.13.4 / pydantic-core 2.46.4; existing project `.venv`; no environment creation, sync, install, source build, or dependency change
- **Baseline tools:** BasedPyright 1.39.9 / Pyright 1.1.411 in strict mode; Ruff 0.15.20; pytest 9.1.1; Coverage.py 7.15.0; pip-audit 2.10.1
- **Scanner tools:** jscpd 5.0.12; Pylint 4.0.6 / astroid 4.0.4; Vulture 2.16; targeted Ruff 0.15.20
- **Audit tools:** run-local `report_lint.py` SHA-256 `291061a85753bc72db8485926af677da573d5371546fbb0a1b4df7415c6d4771`; bundled technical-writer `docctl.py` SHA-256 `373a6ab4c13dad9ef677d0ed996bb1658e336f8c5c32581934400f6f06d5eea1` (no semantic version exposed); fresh GPT-5.6 Sol Ultra report auditor
- **Baseline summary:** BasedPyright 0 diagnostics across 102 files; Ruff 0 diagnostics and 110 files formatted; pytest 1,728 passed with no non-pass identities; 89% branch coverage; pip-audit found no known vulnerabilities and skipped only the local unpublished `docmend` distribution
- **Requested include:** `src/`
- **User exclusions:** none
- **Automatic exclusions:** `.git/`, `.scratch/code-simplify/`, the actual report, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.tox/`, `.nox/`, `.venv/`, `venv/`, `site-packages/`, `.eggs/`, `*.egg-info`, `build/`, `dist/`, submodules, nested repositories, generated/vendor trees not explicitly included, and unsafe or unmaterialized tracked content. None removed an otherwise eligible file under `src/`.
- **Governing convention sources:** injected `AGENTS.md`; `CLAUDE.md`; `README.md`; `pyproject.toml`; `docs/handoff/conventions.md`; `docs/handoff/architecture.md`; ADR index and relevant ADRs; `docs/specs/docmend.md`, including Appendix B
- **Workstreams:** 29 registered; 24 completed and 5 failed, interrupted, or superseded by a fresh safe lane. All six semantic assignments and all successful verifiers were read-only outside their unique scratch directories.
- **Method:** Git-object-derived inventory, complete semantic reading of all 40 included Python files, repository-wide evidence searches, configured baseline fingerprints, four deterministic scanners, anchored history, independent two-phase verification of every surviving non-trivial candidate, coordinator adjudication under the prompt's strict behavior envelope, and a fresh final report audit.
- **Integrity override disclosure:** two predecessor attempts stopped after cache-metadata writes outside their then-current guards. On the user's explicit authority, this continuation preserved those incidents, established a fresh post-incident 65,753-entry guard, treated `.venv/` as a no-write zone, reran the incomplete verifier lanes in read-only sandboxes, and did not use the unsafe paired-snapshot lane for promotion. The override did not authorize any source, test, configuration, lockfile, handoff, or existing documentation edit.

## Baseline exception ledger

The authoritative baseline has no pre-existing type diagnostic, lint diagnostic, pytest failure, pytest error, skip, xfail, xpass, or collection-error identity.

| Surface | Exact baseline identity state | Evidence |
| --- | --- | --- |
| Type | BasedPyright strict; 102 files; `0 errors, 0 warnings, 0 notes` | `.scratch/code-simplify/20260722T004716Z-834f07515a53/baseline/normalized/basedpyright.json`; raw SHA-256 `53c502e23a13fadf87bda94b2c60b1341572b6047ced3b07ac82536506d92b8d` |
| Lint | Ruff: empty normalized diagnostic identity set; format check: 110 files already formatted | `.scratch/code-simplify/20260722T004716Z-834f07515a53/baseline/normalized/ruff.json`; raw SHA-256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| Tests | 1,728 passed; no failure/error/skip/xfail/xpass/collection identities | `.scratch/code-simplify/20260722T004716Z-834f07515a53/baseline/normalized/pytest.json`; JUnit SHA-256 `7dc875b11722619007057e9fd4ffc1eae4389e71064e8bbaf5fb0605b6bf13c7` |
| Coverage | 89% branch coverage | `.scratch/code-simplify/20260722T004716Z-834f07515a53/baseline/raw/coverage-report.txt`; data SHA-256 `74e10aff6907cfe44f3e6af562c72359d391efc5217143bdcd1c755ea4fc95dd` |
| Dependency audit | No known vulnerabilities; local `docmend` skipped because it is not a PyPI project | `.scratch/code-simplify/20260722T004716Z-834f07515a53/baseline/raw/pip-audit.txt` |

An initial diagnostic-only pytest sandbox made `.docmend` read-only and produced three false failures: `tests.test_cli_apply.TestApplyInputErrors::test_apply_invalid_plan__exit_2`, `tests.test_cli_plan.TestPlanCommand::test_corrupt_inventory__err_008_exit_2`, and `tests.test_cli_plan.TestPlanCommand::test_path_not_exists__exit_2`. The cause was the artificial artifact-write restriction, not the anchored code. A corrected sandbox produced the authoritative 1,728-pass identity set above. These three outcomes are not baseline exceptions and must not be accepted by an executor.

Post-change comparison is identity-based, not count-based: type/lint may add no normalized `(path, remapped line or enclosing symbol/context, rule, message)` identity; tests may add, remove, or change no failure, error, unexpected-pass, skip, or xfail identity/reason unless an unchanged-tree rerun first demonstrates that exact fluctuation.

## Coverage ledger

The authoritative candidate-origin inventory came from the anchored Git tree and was cross-checked against the clean materialized worktree. Every included file is tracked at the SHA, regular, one-link, byte-identical to its blob, PEP 263 decodable, non-LFS, non-sparse, and fully read.

| Candidate-origin scope       | Eligible Python files | Reviewed | Gap      |
| ---------------------------- | --------------------: | -------: | -------- |
| `src/docmend/*.py`           |                    26 |       26 | None     |
| `src/docmend/schemas/*.py`   |                     1 |        1 | None     |
| `src/docmend/transform/*.py` |                     5 |        5 | None     |
| `src/docmend/writer/*.py`    |                     8 |        8 | None     |
| **Total**                    |                **40** |   **40** | **None** |

The six disjoint semantic assignments reconciled exactly: core 17, runtime 5, verification 3, writer 8, scale-build 4, and scale-evidence 3. Candidate generation excluded nothing else under `src/`.

Evidence-only tracked content read or opened as needed included `AGENTS.md`, `CLAUDE.md`, `README.md`, `pyproject.toml`, `uv.lock` metadata, `.gitattributes`, `docs/specs/docmend.md`, applicable ADRs, handoff conventions/architecture, historical implementation plans, all match-bearing tests and JSON schemas for each candidate, package exports, console entry-point metadata, workflow files, and focused Git history ending at the anchor. Exact per-workstream opened-file ledgers are indexed in the tool table below. Ignored/untracked content supplied no finding anchor.

Repository boundaries: 408 tracked entries; no gitlinks/submodules, tracked symlinks, nested repositories, sparse paths, assume-unchanged/skip-worktree entries, candidate hardlinks, special tracked materializations, or unresolved LFS pointers. The root `.gitattributes` matched its anchored blob and selected only `-text` for designated weird-document fixtures; no executable filter, textconv, external diff, or fsmonitor surface was used.

## Tool and evidence ledger

All evidence paths are repository-relative. `result.md`, `phase1.md`, and `final.md` files contain the exact command ledger, opened-file ledger, limitations, failures, and sanitized raw-output map for their row.

| Workstream/tool | Version/model; command or scope | Status and evidence | Files opened / useful negative result / limitation |
| --- | --- | --- | --- |
| Override preflight | Coordinator GPT-5.6 Sol Ultra; Git-object inventory and fresh filesystem guard | Complete; current run `preflight.json`, `inventory.json`, `prewrite-filesystem-guard.jsonl` | Repository/attributes/config identities; 40 eligible files; no unsafe boundary. Ambient names `GIT_ASKPASS` and `SSH_ASKPASS` were unset only in review subprocesses under prior user authority. |
| Baseline type | BasedPyright 1.39.9, strict configured mode | Complete/adopted; first-run `baseline/raw/` and `baseline/normalized/` | Effective `pyproject.toml`; 102 files; zero diagnostics. No baseline file modified. |
| Baseline lint | Ruff 0.15.20; configured check and format check | Complete/adopted; first-run `baseline/raw/` and normalized Ruff JSON | 110 configured files; zero lint findings; no fixer or formatter write mode. |
| Baseline tests/coverage | pytest 9.1.1, Coverage 7.15.0 | Complete/adopted; authoritative corrected sandbox | All collected tests; 1,728 pass, zero non-pass; 89% branch. Initial read-only-artifact false failures are disclosed above. |
| Baseline audit | pip-audit 2.10.1 | Complete/adopted | Lock/environment metadata only; no vulnerabilities; local project skip disclosed. |
| jscpd | 5.0.12; Python, 5 lines/50 tokens, JSON and console | Complete; first-run `ultra/deterministic/` | All 40 included files; 14 clone pairs, 201 lines/1.02%; leads only. |
| Pylint duplicate-code | Pylint 4.0.6 / astroid 4.0.4; R0801 | Complete; first-run `ultra/deterministic/` | All included source; 8 leads, none accepted without semantic proof. |
| Vulture | 2.16, `--min-confidence 80` | Complete; first-run `ultra/deterministic/` | All included source; five signature-related false positives, no verified dead symbol. |
| Targeted Ruff | 0.15.20; `SIM,C4,C901,F401,F811,ERA` | Complete; first-run `ultra/deterministic/` | 37 C901 leads; no SIM/C4/F401/F811/ERA diagnostic. Complexity was never treated as a finding by itself. |
| Semantic core | GPT-5.6 Sol Ultra; 17 core/schema/transform modules | Complete; first-run `ultra/semantic-core/result.md` | All 17 assigned files plus matching tests/spec/schemas/history. Eleven unsafe or low-value abstractions rejected. |
| Semantic runtime | GPT-5.6 Sol Ultra; CLI/lineage/lock/observability/watchdog | Complete; first-run `ultra/semantic-runtime/result.md` | Five assigned files plus CLI/observability tests and contracts. Read/write lock and heartbeat lifecycle boundaries retained. |
| Semantic verification | GPT-5.6 Sol Ultra; restore/verify/coverage | Complete; first-run `ultra/semantic-verification/result.md` | Three assigned files plus restore/verify tests, plans, and history. Verification ordering/state reductions retained. |
| Semantic writer | GPT-5.6 Sol Ultra; eight `writer/` modules | Complete; first-run `ultra/semantic-writer/result.md` | All eight modules plus match-bearing tests/plans/history. Journal, mutation, and rollback ceremonies were not merged. |
| Semantic scale-build | GPT-5.6 Sol Ultra; build/corpus/resources/stage | Complete; first-run `ultra/semantic-scale-build/result.md` | Four modules plus scale tests/design/history. Stateful and threat-boundary clone leads rejected. |
| Semantic scale-evidence | GPT-5.6 Sol Ultra; evidence/qualification/reconcile | Complete; first-run `ultra/semantic-scale-evidence/result.md` | Three modules plus schemas/tests/spec. Only the five-site incomplete-stage construction survived. |
| BOM verifier | GPT-5.6 Sol Ultra; `discovery.py` and all references | Confirmed with qualification; first-run `ultra/verifier-bom/final.md` | Definition, all five values, caller/export/schema/tests/history. Private mapping reflection is unsupported and disclosed. |
| Model-config verifier | GPT-5.6 Sol Ultra; four artifact roots | Confirmed with qualification; first-run `ultra/verifier-model-config/final.md` | Four models/bases, artifact/schema tests, Pydantic runtime. Exact proof is scoped to Pydantic 2.13.4/core 2.46.4. |
| Frontmatter-closer verifier | GPT-5.6 Sol Ultra; one constant relation | Verifier confirmed with qualification; coordinator retained it; first-run `ultra/verifier-frontmatter-closer/final.md` | Module/tests/history and 66,430 inputs. Import-time name lookup/allocation, code object, and cross-execution tuple identity diverge under the review's stricter envelope. |
| File-size verifier | GPT-5.6 Sol Ultra; five incomplete constructors | Confirmed with qualification; first-run `ultra/verifier-file-size/final.md` | Qualification/evidence models, all seven constructors, tests/history. Two completed-stage constructors explicitly excluded. |
| Recompute verifier | GPT-5.6 Sol Ultra; private return/consumers | Confirmed with qualification; first-run `ultra/verifier-recompute/final.md` | Definition, two callers, transforms/tests/history. Removed tuple allocation/private metadata disclosed. |
| Build-report verifier | GPT-5.6 Sol Ultra; unused private parameter | Confirmed with qualification; first-run `ultra/verifier-build-report/final.md` | Definition/two calls, report tests/schema/history. Seven retained keyword expressions remain ordered. |
| Backup-destination verifier | GPT-5.6 Sol Ultra; unused private parameters | Confirmed with qualification; first-run `ultra/verifier-backup-destination/final.md` | Definition/sole call, gate tests/history. Containment check remains before the potentially mutating writability probe. |
| Verified-backup verifier | GPT-5.6 Sol Ultra; duplicate digest call | Verifier confirmed with qualification; coordinator retained it; first-run `ultra/verifier-verified-backup/final.md` | Definition/sole call/restore tests/history. Mismatch-path `_sha` evaluation count changes from two to one, which the requested envelope forbids. |
| Corpus-root verifier | GPT-5.6 Sol Ultra; three CLI expressions | Confirmed with qualification; second-run `ultra/verifier-corpus-root-resumed/final.md` | CLI, downstream guards/locks, 32 focused tests, related helpers/history. Private helper frame/reflection disclosed. |
| Bare snapshot verifier | GPT-5.6 family; six-field predicate | Rejected; second-run `ultra/verifier-regular-snapshot-resumed/final.md` | Dataclass/helper/callers/tests/history. Bare equality adds path, exact-class, and `__eq__` behavior. |
| Fresh frontmatter-guard verifier | Configured GPT-5.6 Sol Ultra; two-phase exact adjudication | Rejected; current-run `ultra/verifier-frontmatter-guard-fresh/{phase1,final}.md` | Public function/callers/tests/spec/history; a valid `str` subclass changes `None` to uncaught `IndexError`. |
| Fresh CPU-model verifier | Configured GPT-5.6 Sol Ultra; two-phase exact adjudication | Confirmed with qualification; current-run `ultra/verifier-cpu-model-fresh/{phase1,final}.md` | Helper/caller/model/schema/tests/history; 2,007 differential cases, strict typing, public JSON/comparison, and five caller tests passed. Extra selected-key lookup, subtype behavior, locals/lifetimes, and allocation boundaries disclosed. |
| Fresh paired-snapshot verifier | Configured GPT-5.6 Sol Ultra; two-phase exact adjudication | Rejected; current-run `ultra/verifier-regular-snapshot-paired-fresh/{phase1,final}.md` | Snapshot dataclass/helper/callers/tests/contracts/history; equality/hash/reflection/operator/subclass drift. Unsafe predecessor evidence excluded. |
| Dependency health | None | Not applicable | No third-party replacement or new dependency survived candidate reconciliation. |
| Report schema linter | Run-local deterministic Python script; SHA-256 `291061a85753bc72db8485926af677da573d5371546fbb0a1b4df7415c6d4771` | Pass before fresh audit | Exact 12 headings; complete S/D/J/B fields; contiguous IDs; sequence and count reconciliation. |
| Markdown structure validator | Bundled technical-writer `docctl.py`; SHA-256 `373a6ab4c13dad9ef677d0ed996bb1658e336f8c5c32581934400f6f06d5eea1` | Pass before fresh audit | Draft only: 0 errors, 0 warnings, 0 informational findings; tool exposes no semantic version. |
| Fresh final auditor | Configured GPT-5.6 Sol Ultra; complete draft, evidence, anchor, schemas, counts, order | PASS; current-run `ultra/final-audit/audit.md` | No disposition changed. The auditor required only publication bookkeeping, then re-audit of the exact resolved draft. |

Known limitations: no external/downstream consumer search can prove absence of unsupported imports of underscore-private names; history was local and ending at the anchor, with no network fetch; network/package-health work was unnecessary; scanner and baseline output are candidate evidence rather than implementation proof. No raw evidence was withheld for secret risk, and no credential value was persisted.

## Shared-module manifest

No new module or public API is proposed.

| Existing private destination | Findings | Boundary |
| --- | --- | --- |
| `src/docmend/cli.py::_resolve_corpus_root` | S-001 | Same-module private helper for the three CLI guard/lock roots only; discovery, lock, artifact, and gate ownership remain separate. |
| `src/docmend/scale_qualification.py::_incomplete_file_size_stage` | S-004 | Same-module private factory for exactly five incomplete evidence constructors; completed-stage constructors remain explicit. |

## Findings

### S-001 — Name the repeated CLI corpus-root resolution policy — extract-shared

**ID / title / category:** `S-001`; Name the repeated CLI corpus-root resolution policy; `extract-shared`.

**Anchors:** `src/docmend/cli.py:277` (`docmend.cli.scan`), `src/docmend/cli.py:388` (`docmend.cli.plan`, `PATH` branch), and `src/docmend/cli.py:1124` (`docmend.cli.verify`). Insert the definition after `src/docmend/cli.py:192-217` (`_guard_artifact_paths`) and before the first command decorator. Evidence-only analogous owners inspected: `src/docmend/discovery.py:396-414`, `src/docmend/lock.py:53-55`, `src/docmend/artifacts.py:137-166`, and `src/docmend/writer/gate.py:192-202`; they are not call sites and must not change.

**Current state:** Each CLI command repeats the same expression:

```python
corpus_root = (path if path.is_dir() else path.parent).resolve()
```

The `plan` copy names the result `scan_root`; each value is then passed to artifact containment and exact-root locking, with verify also comparing/serializing it.

**Public/dynamic contract check:** Complete tracked search found only the three expressions and no helper-name reference. `docmend.cli` has no `__all__`; `src/docmend/__init__.py` exports only `__version__`; the console entry point remains `docmend.cli:app`. Typer command order, command signatures/help, callback, artifacts, lock keys, schemas, and `Inventory.source_root` ownership remain unchanged. No test monkeypatches `Path.is_dir`, `Path.resolve`, or the proposed private helper. The new underscore name is reflectable and rebindable, and failures gain a helper frame; no repository contract observes that private surface.

**Intent and convention evidence:** Commits `2acdc4a8` (plan lock root), `ba986a2` (scan artifact guard), and `e6decca4` (verify orchestration) introduced the copies independently with the same policy; blame shows no divergence. NFR-006, IR-007, OQ-036, and FR-014 require single-file support, pre-pipeline artifact guards, resolved-root lock identity, and manifest-root agreement. The repository favors narrow typed private helpers when they name one policy and does not require docstrings that restate a one-line body.

**Comprehension benefit:** The three large commands will state “resolve the corpus root” instead of making each maintainer re-derive the file-versus-directory rule at safety boundaries. Three same-domain callers justify one local name; keeping it in `cli.py` avoids cross-layer coupling.

**Proposed change:** Add exactly:

```python
def _resolve_corpus_root(path: Path) -> Path:
    return (path if path.is_dir() else path.parent).resolve()
```

Then edit only:

- `scan`: `(path if path.is_dir() else path.parent).resolve()` → `_resolve_corpus_root(path)` while retaining `corpus_root`.
- `plan`: the same expression → `_resolve_corpus_root(path)` while retaining `scan_root`.
- `verify`: the same expression → `_resolve_corpus_root(path)` while retaining `corpus_root`.

Do not globally replace after inserting the helper, which would recurse. Do not add a docstring or move discovery/lock/artifact/gate logic.

**Replacement target:** Not applicable; no dependency or standard-library substitution.

**Automation plan:** Not applicable. One file, three call sites, about ten changed lines; below the codemod threshold. Use a targeted structural or exact patch and confirm one definition/three calls/one original expression in the helper.

**Consolidation basis:** The three expressions encode the same CLI safety fact and have identical evaluation order and return contract. No conditional fan-out is introduced. Discovery's independently owned scan semantics, lock's defensive resolution, artifact containment, and gate's ancestor probing remain separate; no public path or useful test seam is removed.

**Dependency health:** Not applicable.

**Typing:** Exact signature `def _resolve_corpus_root(path: Path) -> Path`. Both conditional arms and `resolve()` are `Path`; no `Any`, widening, cast, suppression, import, or public annotation changes.

**Behavior and error preservation:** Directory branch still calls `path.is_dir()` once then `path.resolve()` once. Non-directory branch still calls `path.is_dir()` once, obtains `path.parent` once, then resolves that parent once. Receiver choice, non-strict resolution, TOCTOU shape, filesystem observation order, results for file/directory/symlink/broken/missing/lexical-`..` paths, and propagated exception type/message/cause/context are unchanged. A private Python call/return, traceback frame, trace/profile event, source-line shift, and negligible timing shift are the disclosed qualifications; no supported caller introspection or exact scheduling contract exists.

**Independent verification:** `verifier-corpus-root-resumed`; independently enumerated the three sites and downstream consumers, then confirmed the exact phase-two proposal with qualifications. Exact overlay passed Ruff format/lint, strict BasedPyright, and 32 focused tests twice; candidate SHA-256 `4c75e30ece17665befb9cd026d67f180781c57ef08a706b813893cd683661e3c`.

**Verification for executor:** Before editing, require a clean isolated worktree at the anchor and matching global baseline identities. After the exact edit, verify occurrence counts and run:

```bash
uv run --frozen --no-sync ruff format --check src/docmend/cli.py
uv run --frozen --no-sync ruff check src/docmend/cli.py
uv run --frozen --no-sync basedpyright src/docmend/cli.py
uv run --frozen --no-sync pytest tests/test_cli.py tests/test_cli_scan.py tests/test_cli_plan.py \
  tests/test_cli_verify.py tests/test_discovery.py tests/test_restore_drill.py tests/test_verify.py
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync basedpyright
uv run --frozen --no-sync coverage run -m pytest
uv run --frozen --no-sync coverage report
uv run --frozen --no-sync pip-audit
```

Redirect all caches/temp/bytecode as in the executor preflight. Compare normalized identities, inspect the one-file diff, and revert only this finding if any behavioral oracle, command, or identity differs. No existing test edit is permitted or needed.

**Benefit × confidence:** Benefit medium: removes three repeated mental models at safety-sensitive call sites. Safety confidence high: all occurrences/consumers/contracts were enumerated and the exact overlay passed type/lint and focused behavior checks.

**Blast radius:** One private definition, three call sites, one source file, about ten changed lines. No dependency, public path, schema, test-reference edit, or automation threshold. Independent of every other finding.

### S-002 — Remove the redundant BOM identity mapping — simplify-construct

**ID / title / category:** `S-002`; Remove the redundant BOM identity mapping; `simplify-construct`.

**Anchors:** `src/docmend/discovery.py:74-82` (`_BOMS`), `src/docmend/discovery.py:84-93` (`_BOM_ENCODING_NAME`), `src/docmend/discovery.py:96-102` (`sniff_bom`), and `src/docmend/discovery.py:230-232` (`classify_file`). `BomKind` is defined at `src/docmend/inventory.py:25`. The other repository call/reference site for unchanged public `sniff_bom` is `src/docmend/writer/apply.py:33,200` (`docmend.writer.apply._recompute`).

**Current state:** `_BOMS` already pairs each byte prefix with the authoritative five-value `BomKind`, but `_BOM_ENCODING_NAME` repeats an identity mapping for the same five strings and its sole lookup supplies `DetectedEncoding.name`.

```python
_BOM_ENCODING_NAME: dict[BomKind, str] = {
    "utf-8": "utf-8",
    "utf-16-le": "utf-16-le",
    "utf-16-be": "utf-16-be",
    "utf-32-le": "utf-32-le",
    "utf-32-be": "utf-32-be",
}
```

**Public/dynamic contract check:** `sniff_bom` remains public with identical name/signature/return values; `classify_file` changes only the equal constructor value. Repository-wide exact, quoted, export, registry, callback, reflection, `setattr`, and monkeypatch searches found no mapping consumer. Package exports, inventory/plan schemas, and serializer paths remain unchanged. Removing the underscore mapping changes `discovery.__dict__`, module annotations, and unsupported direct private import/mutation behavior; no tracked contract observes it.

**Intent and convention evidence:** `_BOMS` and the identity map originated together in `cae24372`; no later history established a distinct translation. FR-007/OQ-026 make the BOM authoritative for encoding, while EC-007 requires the BOM fact to remain separately recorded for stripping. The code-comment canon requires preserving that invariant rather than deleting its rationale with the table.

**Comprehension benefit:** One closed source of truth makes it immediately clear that `BomKind` itself is the detected encoding name. A maintainer no longer has to compare two five-entry structures to prove they cannot drift.

**Proposed change:** Preserve `_BOMS` order and type. Move/reword the existing rationale immediately above `_BOMS` to:

```python
# Each BomKind literal is also the authoritative detected encoding name
# (FR-007/OQ-026); the BOM fact remains separate so plan/apply can strip it
# (EC-007).
```

Delete `_BOM_ENCODING_NAME` entirely and change only:

```python
DetectedEncoding(name=_BOM_ENCODING_NAME[bom], confidence=1.0, method="bom")
```

to:

```python
DetectedEncoding(name=bom, confidence=1.0, method="bom")
```

**Replacement target:** Not applicable.

**Automation plan:** Not applicable; one definition deletion and one expression substitution in one file.

**Consolidation basis:** This is not a cross-domain merge: both structures encode the exact same closed five-literal fact. No branches or parameters are added, and the useful distinction between content encoding and separately recorded BOM presence remains explicit in the retained invariant comment.

**Dependency health:** Not applicable.

**Typing:** In the `bom is not None` branch, BasedPyright narrows `BomKind | None` to the five-value `BomKind` literal union, which is assignable to `DetectedEncoding.name: str`. No cast, suppression, widening, or import change.

**Behavior and error preservation:** `_BOMS`, longest-first matching, `startswith`, four-byte read, decode selection, BOM recording, evaluation order, and serialized string values remain identical for all five values. The anchored lookup is total. Only behavior dependent on mutating or reflecting on the private identity dict disappears, along with a private annotation and impossible lookup/mutation failure modes; no repository consumer relies on them. No function frame, warning, log, I/O, cleanup, random state, or performance characteristic changes materially.

**Independent verification:** `verifier-bom`; confirmed with qualification after all five mappings, complete references, schemas, tests, typing, and anchored history were checked. No public/dynamic consumer was found.

**Verification for executor:** Characterize all five `_BOMS` entries before and after, preserving exact order and emitted `DetectedEncoding` values. Then run:

```bash
uv run --frozen --no-sync ruff format --check src/docmend/discovery.py
uv run --frozen --no-sync ruff check src/docmend/discovery.py
uv run --frozen --no-sync basedpyright src/docmend/discovery.py
uv run --frozen --no-sync pytest tests/test_discovery.py
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync basedpyright
uv run --frozen --no-sync coverage run -m pytest
uv run --frozen --no-sync coverage report
uv run --frozen --no-sync pip-audit
```

Require no remaining `_BOM_ENCODING_NAME` reference, inspect the one-file diff, compare baseline identities, and revert this finding if any existing behavioral oracle would need alteration.

**Benefit × confidence:** Benefit low: local clarity and one drift source removed. Safety confidence high: closed finite mapping exhaustively compared; complete references and serialization contracts checked.

**Blast radius:** One source file; one private seven-line mapping removed, one constructor expression changed, one invariant comment relocated/reworded. No call-site, dependency, public path, schema, test edit, or automation requirement.

### S-003 — Let artifact roots inherit unchanged strict-model policy — simplify-construct

**ID / title / category:** `S-003`; Let artifact roots inherit unchanged strict-model policy; `simplify-construct`.

**Anchors:** `src/docmend/inventory.py:51-54` and `:128-137` (`_StrictModel`, `Inventory`); `src/docmend/plan.py:50-53` and `:89-98` (`_StrictModel`, `Plan`); `src/docmend/report.py:49-50` and `:87-92` (`_StrictModel`, `Report`); `src/docmend/verify_report.py:16-17` and `:33-40` (`_StrictModel`, `VerifyReport`).

**Current state:** Each public root subclasses its module-local `_StrictModel` but repeats inherited `extra="forbid"`, `strict=True`, and, for `VerifyReport`, `frozen=True`, alongside the actual root delta `populate_by_name=True, serialize_by_alias=True`.

**Public/dynamic contract check:** All four class identities, bases, MROs, module/qualified names, signatures, fields, aliases, validators, serializers, frozen/hash behavior, model/core config mappings, validation errors, and three JSON-schema modes were compared in the installed runtime. Each own-class `model_config` remains a fully merged mapping and distinct from the base mapping. No export, entry point, registry, reflection, serialization, schema, or artifact path changes. Do not include `report.ErrorInfo`; rebasing it would change public MRO/isinstance behavior.

**Intent and convention evidence:** The roots arrived independently in `cae24372`, `c236f653`, `13dd1bbb`, and `39784b04`; history contains no rationale for restating inherited keys. ADR-0005 requires the effective strict durable schema, which remains identical. Neighboring nested records already rely on the same local-base inheritance.

**Comprehension benefit:** Each public root will declare only what differs from its named strict base. A maintainer can see the common policy once and the alias policy once, without wondering whether repeated values intentionally diverge.

**Proposed change:** At exactly four sites replace the full declaration with:

```python
model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
```

Retain every local `_StrictModel`, class base, comment, field, import, serializer, validator, test, and schema. Do not centralize bases or modernize `populate_by_name` in this finding.

**Replacement target:** Not applicable.

**Automation plan:** Not applicable; four mechanical declarations, four files, well below threshold.

**Consolidation basis:** The repeated keys are the same inherited policy within each module, and Pydantic already copies/merges the local base config. The edit adds no shared module, fan-out, or coupling. Root-specific alias policy remains explicit and every class/import path/test seam remains.

**Dependency health:** No new dependency. The exact proof is scoped to locked Pydantic 2.13.4 / pydantic-core 2.46.4. The declared open range `pydantic>=2.12` means any dependency refresh must rerun the equivalence characterization; this finding does not claim future-major compatibility or authorize a constraint change.

**Typing:** `ConfigDict` is a `TypedDict(total=False)`; deleting optional inherited entries leaves a valid precise declaration. No field/parameter/return annotation, `Any`, suppression, overload, import, or checker mode changes.

**Behavior and error preservation:** Exact transformed-module probes found equal final config item order, validation/serialization schemas, field metadata, alias dumps, missing/extra/strict errors, Plan serializer behavior, and VerifyReport assignment errors/hashability. Executor post-edit schema hashes must remain: Inventory `138b4a7a2503809efc152b725fcfdd0b06a5c5284ab6cb9c526f8ad1bd2d1f60`; Plan `c2c275d88b0ddb69b40422dce8aa57b62c58cb933dc4c0ea62a417d604216fd3`; Report `231c082ab3a12dffdde9687d51c8d69f5f653e4fcc581d2cbcf4c98fb6d9dc96`; VerifyReport `4b3d3954404cff3bae71f6e02f657bba8349a805b19f7d2c063f05fecbc08e41`.

**Independent verification:** `verifier-model-config`; confirmed with qualification using exact in-memory transformed modules, Pydantic metaclass/runtime inspection, full schema/config/error/serialization matrices, and anchored history. Qualification: only the locked installed Pydantic versions were assessed.

**Verification for executor:** Recreate the recorded environment first. After the four replacements, assert the exact merged configs and four schema hashes above, then run:

```bash
uv run --frozen --no-sync ruff format --check src/docmend/inventory.py src/docmend/plan.py \
  src/docmend/report.py src/docmend/verify_report.py
uv run --frozen --no-sync ruff check src/docmend/inventory.py src/docmend/plan.py \
  src/docmend/report.py src/docmend/verify_report.py
uv run --frozen --no-sync basedpyright src/docmend/inventory.py src/docmend/plan.py \
  src/docmend/report.py src/docmend/verify_report.py
uv run --frozen --no-sync pytest tests/test_inventory_artifact.py tests/test_plan_artifact.py \
  tests/test_report_artifact.py tests/test_verify_report_artifact.py tests/test_schemas.py
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync basedpyright
uv run --frozen --no-sync coverage run -m pytest
uv run --frozen --no-sync coverage report
uv run --frozen --no-sync pip-audit
```

If Pydantic versions, effective mappings, hashes, errors, serialization, or baseline identities differ, stop and rerun this analysis rather than modifying tests or schemas.

**Benefit × confidence:** Benefit medium: removes cross-module policy restatement and drift risk. Safety confidence medium: exact installed-version proof is strong, but the declared open dependency range requires recharacterization on upgrade.

**Blast radius:** Four public model source files, four declarations, about twelve lines removed; no callable, field, schema, artifact, import, dependency, or test-reference change. No codemod threshold or prerequisite; keep independent from other findings.

### S-004 — Centralize the exact incomplete file-size stage record — extract-shared

**ID / title / category:** `S-004`; Centralize the exact incomplete file-size stage record; `extract-shared`.

**Anchors:** Insert after `src/docmend/scale_qualification.py:963-972` (`_file_size_stage_request`) and before `_file_size_case_evidence`. Replace constructors in `docmend.scale_qualification.DefaultCandidateRuntime.run_file_size_matrix` at `:1220-1230`, `:1238-1248`, `:1255-1265`, `:1286-1296`, and `:1309-1319`. Retain completed-stage constructors at `:1408-1420` and `:1440-1450`. Model definitions are `src/docmend/scale_evidence.py` (`StageName`, `FileSizeStageEvidence`, `FileSizeCaseEvidence`).

**Current state:** Five failure/incomplete branches repeat a strict nine-field `FileSizeStageEvidence` construction. Three use `elapsed_seconds=0.0`; two preserve a branch-derived elapsed value. The two completed paths resemble the shape but carry trustworthy measurements and must remain separate.

**Public/dynamic contract check:** The evidence model class, import path, identity, MRO, validators, fields, required set, strict config, schema, serialization, and public runtime signatures remain unchanged. Complete search found no reflection, registry, dynamic import, or monkeypatch of the proposed helper. `FileSizeStageEvidence` remains looked up from module globals on every helper call, preserving existing model monkeypatch behavior. The new underscore helper is visible in the private module dictionary and adds a frame only if model construction fails; no tracked contract observes it.

**Intent and convention evidence:** The five incomplete records all encode the same absence-of-trust fact; completed children deliberately carry measurements and artifact/watchdog outcomes. History and the scale qualification contract preserve branch order, interruption routing, and completed-versus-incomplete distinctions. Repository convention supports a narrow typed factory when it removes a repeated durable-record invariant without swallowing control flow.

**Comprehension benefit:** Each failure branch will state only which stage failed and any elapsed time. The single factory makes the nine-field incomplete invariant auditable in one place and prevents a future branch from silently drifting.

**Proposed change:** Add exactly:

```python
def _incomplete_file_size_stage(
    stage: StageName, *, elapsed_seconds: float = 0.0
) -> FileSizeStageEvidence:
    return FileSizeStageEvidence(
        stage=stage,
        elapsed_seconds=elapsed_seconds,
        peak_rss_bytes=None,
        vm_swap_peak_bytes=None,
        exit_code=None,
        completed=False,
        artifact_validated=False,
        timeout_outcome="not-measured",
        backup_bytes=0,
    )
```

Replace the first three listed constructors with `_incomplete_file_size_stage(stage)`. Replace `:1286` with:

```python
_incomplete_file_size_stage(
    stage,
    elapsed_seconds=(result.elapsed_seconds if result is not None else 0.0),
)
```

Replace `:1309` with `_incomplete_file_size_stage(stage, elapsed_seconds=result.elapsed_seconds)`. Do not alter reasons, flags, assignments, `break`, interruption calls, or the two completed constructors.

**Replacement target:** Not applicable.

**Automation plan:** Not applicable; one file, five call sites, fewer than 50 calls/500 lines. Exact occurrence check should show one helper definition, five helper calls, one direct constructor inside it, and two completed direct constructors.

**Consolidation basis:** All five sites express the same immutable incomplete-stage domain record; variation is limited to the record's legitimate `stage` and elapsed values rather than conditional fan-out. Fresh construction preserves independent state. Completed paths represent different knowledge and are explicitly excluded. No public path or useful seam is lost.

**Dependency health:** Not applicable.

**Typing:** Exact signature uses existing `StageName` and `FileSizeStageEvidence`; `elapsed_seconds` remains `float`. No import, `Any`, cast, suppression, widening, protocol, model default, or schema change.

**Behavior and error preservation:** Every call returns a fresh normally validated Pydantic object with identical nine values and JSON bytes. Python still evaluates `stage` before the unchanged keyword expression. The conditional still checks `result is not None` once and reads elapsed at most once; the mismatch branch still reads it once. Expression failures occur before helper entry. Construction errors preserve Pydantic class, error entries, message, cause/context, and routing but gain the private helper frame. Three literal `0.0` argument loads disappear in favor of keyword default binding; no supported side effect or value changes. No caching, `model_copy`, or `model_construct` is allowed.

**Independent verification:** `verifier-file-size`; confirmed with qualification. Exact in-memory transform compiled with five helper calls and three total direct constructors. Eight valid stage/elapsed comparisons, fresh identity, serialization equality, 10 focused tests, Ruff, and strict BasedPyright passed.

**Verification for executor:** First run a characterization loop over four stages and elapsed values `0.0`/`0.25`, comparing equality, `model_dump_json()`, and distinct identity against direct construction. After editing:

```bash
rg -n 'FileSizeStageEvidence\(|_incomplete_file_size_stage\(' src/docmend/scale_qualification.py
uv run --frozen --no-sync ruff format --check src/docmend/scale_qualification.py
uv run --frozen --no-sync ruff check src/docmend/scale_qualification.py
uv run --frozen --no-sync basedpyright src/docmend/scale_qualification.py src/docmend/scale_evidence.py
uv run --frozen --no-sync pytest tests/test_scale_file_size.py \
  tests/test_schemas.py::TestPydanticCrossCheck::test_qualification_model__matches_hand_authored_schema
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync basedpyright
uv run --frozen --no-sync coverage run -m pytest
uv run --frozen --no-sync coverage report
uv run --frozen --no-sync pip-audit
```

Compare all baseline identities and inspect only this file's diff. No behavioral oracle or existing test reference may change; revert this finding alone on failure.

**Benefit × confidence:** Benefit medium: five failure branches share one durable-record invariant instead of nine repeated fields. Safety confidence high: exact sites/exclusions, construction/evaluation/error behavior, schema, typing, and focused tests were independently verified.

**Blast radius:** One private helper and five private call sites in one file; roughly 45 repeated lines replaced by about 20 explicit helper/call lines. No dependency, public API, schema, test edit, or automation threshold. Independent of all other findings.

### S-005 — Store only the first CPU field value that can be observed — simplify-construct

**ID / title / category:** `S-005`; Store only the first CPU field value that can be observed; `simplify-construct`.

**Anchors:** `src/docmend/scale_resources.py:828-836` (`_public_probe_label`), `:839-848` (`docmend.scale_resources._cpu_model`), and sole production call at `:1012-1051`, specifically `observe_reference_environment:1038`. Public value/serialization contracts: `src/docmend/scale_evidence.py:175-191`, `:899-927`, `:1193-1195`, and `:1293-1308`; schema `src/docmend/schemas/reference-environment.schema.json:8-27,54-60`.

**Current state:** The private parser builds `dict[str, list[str]]`, eagerly allocates an empty-list default and appends every duplicate CPU-info value, then observes only `values[0]` in fixed priority order. Empty first values are deliberately present and normalize to `unknown`; later duplicates and lower-priority fields do not replace them.

**Public/dynamic contract check:** `_cpu_model` has one internal caller, is underscore-private, is not re-exported, registered, string-addressed, reflected, or monkeypatched, and receives ordinary `str` from the `/proc/cpuinfo` probe. `ReferenceEnvironment.cpu_model` remains the same required strict `PublicLabel`, exact comparison input, JSON field, and digest input. No public callable/model/signature changes. An unsupported method-overriding `str` subtype directly passed to the private helper can observe the new selected-key lookup pattern; this qualification is explicit below.

**Intent and convention evidence:** Commit `1115308e` introduced parser, caller, model, and tests together; no later history uses retained duplicates for diagnostics. The scale contract requires a sanitized public CPU label and exact reference matching, not duplicate telemetry retention. The local style favors a direct loop over a clever reverse comprehension when order and first-wins behavior matter.

**Comprehension benefit:** A scalar map states the actual contract—first value per normalized field—without suggesting that later duplicates are consumed. It removes list plumbing and makes empty-value presence explicit through membership.

**Proposed change:** Replace only `_cpu_model`'s body with:

```python
def _cpu_model(cpuinfo: str) -> str:
    fields: dict[str, str] = {}
    for line in cpuinfo.splitlines():
        name, separator, value = line.partition(":")
        if separator:
            fields.setdefault(name.strip().lower(), value)
    for field_name in ("model name", "hardware", "processor"):
        if field_name in fields:
            return _public_probe_label(fields[field_name])
    raise ResourcePreflightError("CPU model telemetry unavailable")
```

Do not use a reverse comprehension, a truthiness/walrus selection, an early-return parser, or remove/change imports, callers, models, schemas, tests, or error text.

**Replacement target:** Not applicable.

**Automation plan:** Not applicable; one ten-line private function, no call-site edit.

**Consolidation basis:** Not a merge/extraction. The scalar representation removes unused list state while retaining the explicit parse-then-priority boundary and first-wins rule.

**Dependency health:** Not applicable.

**Typing:** Exact existing signature remains `def _cpu_model(cpuinfo: str) -> str`. The local changes from `dict[str, list[str]]` to `dict[str, str]`; built-in `splitlines`, `partition`, `strip`, and `lower` produce strings. Strict BasedPyright reported zero diagnostics; no `Any`, cast, suppression, import, or public annotation changes.

**Behavior and error preservation:** For ordinary `str`, `splitlines` remains once; every line is parsed forward; first-colon partition, key strip/lower order, complete-parse-before-selection, priority, first duplicate, empty-value selection, sanitization, extra-colon handling, and missing-telemetry exception class/message/args/cause/context are identical. A 2,007-case differential oracle found no ordinary-string outcome difference; public JSON and exact comparison matched. The proposal removes per-line list allocation/append and duplicate retention, reducing the synthetic peak allocation about 45.6% and time about 11%, neither relied on as a performance promise. Qualification: selected fields use membership then subscription (two dictionary lookups versus current one `get`), so a method-overriding `str` subtype that yields an equality-effectful key can differ; trace-visible locals, duplicate destructor timing, and low-memory allocation failures also change. The only supported repository caller supplies exact ordinary `str`, and no private dynamic seam was found.

**Independent verification:** `verifier-cpu-model-fresh`; conclusion-blind phase 1 rejected comprehension alternatives, then phase 2 confirmed this exact forward scalar loop with qualification. Evidence: 2,007 differential inputs, strict typing, public JSON/comparison probes, five focused caller tests, allocation/lifetime and adversarial-subtype characterization, full references/history, and clean integrity.

**Verification for executor:** Before editing, add/run a scratch characterization (not a repository test edit) covering duplicate first-wins, empty high-priority value, ARM fallback, missing fields, extra colons, forbidden labels, and ordinary strings. After the exact edit run:

```bash
uv run --frozen --no-sync ruff format --check src/docmend/scale_resources.py
uv run --frozen --no-sync ruff check src/docmend/scale_resources.py
uv run --frozen --no-sync basedpyright src/docmend/scale_resources.py
uv run --frozen --no-sync pytest tests/test_scale_resources.py -k \
  'local_ssd or arm_cpu_model_fallback or forbidden_probe_label'
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync basedpyright
uv run --frozen --no-sync coverage run -m pytest
uv run --frozen --no-sync coverage report
uv run --frozen --no-sync pip-audit
```

Require the same environment and normalized identities. Do not add a contract for the private local representation or alter public expected values. Revert this finding alone on any public/caller/error/serialization difference.

**Benefit × confidence:** Benefit medium: removes a misleading list-valued model and duplicate allocation from a repeated system-information record. Safety confidence medium: complete repository/public behavior is characterized, but unsupported adversarial `str` subtype and introspection differences remain explicit.

**Blast radius:** One private function in one file; no call-site, public path, schema, dependency, test edit, or codemod. Approximately six expression/type changes inside the existing ten-line body. Independent of other findings.

### S-006 — Return only the recomputed payload that callers use — collapse-indirection

**ID / title / category:** `S-006`; Return only the recomputed payload that callers use; `collapse-indirection`.

**Anchors:** `src/docmend/writer/apply.py:196-226` (`docmend.writer.apply._recompute`), mutation caller `:536-541` (`_execute_action`), and preview caller `:924-928` (`_preview_action`). Downstream payload consumers include hashing at `:634` and staging at `:646`.

**Current state:** `_recompute` calculates transformed bytes and an ordered `list[Operation]`, compares the list with `action.operations`, then returns `(bytes, operations)`. `_execute_action` immediately unpacks and discards `_operations`; `_preview_action` ignores the entire successful return. The operation list is valuable for validation but is not a caller result.

**Public/dynamic contract check:** Complete tracked search found exactly one definition and two calls, with no string lookup, direct test, export, registry, serializer, reflection, or monkeypatch of `_recompute`. Public `execute_plan`/`preview_plan`, CLI, report/manifest artifacts, `PlanAction.operations`, and transform dependencies retain their paths and metadata. Tests monkeypatch `apply_text_transforms`, not `_recompute`. The private return annotation and behavior for unsupported direct callers/malformed monkeypatches intentionally narrow.

**Intent and convention evidence:** Commit `4f08d658` introduced the tuple and immediate discard together; commit `928717f3` added preview without consuming successful data. No history assigned meaning to the returned list. The local convention keeps the ordered operation comparison in `_recompute`, where it names the plan-vs-runtime contract.

**Comprehension benefit:** The return type will match what downstream code actually needs. A maintainer no longer has to trace `_operations` to discover that the list is computed only to validate the plan and is then discarded.

**Proposed change:** Make exactly three edits:

```python
def _recompute(
    action: PlanAction, data: bytes, config: DocmendConfig
) -> bytes | str:
```

At the successful return, change `return encode_utf8(transformed), operations` to `return encode_utf8(transformed)`. At `_execute_action`, change `payload, _operations = recomputed` to `payload = recomputed`. Keep `operations: list[Operation]`, its exact construction/order, comparison, divergence message, both string discriminator branches, imports, and preview flow.

**Replacement target:** Not applicable.

**Automation plan:** Not applicable; three expressions in one file.

**Consolidation basis:** This collapses a false private result channel without combining concepts. Operation derivation remains an explicit named local and safety check; bytes remain the sole success output. No test seam, useful name, module boundary, or public import path is removed.

**Dependency health:** Not applicable.

**Typing:** Exact return is `bytes | str`. After the existing equality/string guards, strict BasedPyright narrows `recomputed` to `bytes`; no cast, `Any`, suppression, import, or public annotation changes. `Operation` remains imported and precisely typed.

**Behavior and error preservation:** BOM sniffing, decoding/translation, transform arguments, shrink counts, ordered operation construction/comparison, exact ERR-006 detail, UTF-8 encoding, payload object, hashes, staging, outcomes, reports, and manifests retain their evaluation order and values. All pre-return exceptions retain handler/chaining/frame boundaries. The unnecessary tuple allocation and its theoretical `MemoryError` point disappear. Private direct callers/untyped monkeypatches expecting the tuple and private signature/annotations observe the deliberate narrowing; repository-wide checks found none.

**Independent verification:** `verifier-recompute`; confirmed with qualification. Exact in-memory replacement matched once per edit, compiled, retained six `operations` uses, and produced the intended assignment/annotation. Focused five-test selection, Ruff, and strict BasedPyright passed at the anchor.

**Verification for executor:** Inspect the exact three-line semantic diff and require `operations` still feeds the ordered comparison. Run:

```bash
uv run --frozen --no-sync ruff format --check src/docmend/writer/apply.py
uv run --frozen --no-sync ruff check src/docmend/writer/apply.py tests/test_apply.py
uv run --frozen --no-sync basedpyright src/docmend/writer/apply.py tests/test_apply.py
uv run --frozen --no-sync pytest tests/test_apply.py -k \
  'dry_run_default or write_rewrite_in_place or write_rename_only or shrink_invariant_recheck or operations_divergence'
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync basedpyright
uv run --frozen --no-sync coverage run -m pytest
uv run --frozen --no-sync coverage report
uv run --frozen --no-sync pip-audit
```

Compare baseline identities and public report/manifest values. Do not add a private return-shape test or modify an oracle; revert this finding alone on any difference.

**Benefit × confidence:** Benefit low: removes one misleading private result component within one symbol. Safety confidence high: all consumers and dynamic surfaces were checked, equivalence is direct, and exact transformed shape/type checks passed.

**Blast radius:** One file, one private definition, two callers, three edited expressions, fewer than ten changed lines. No dependency, public path, schema, test edit, prerequisite, conflict, or codemod threshold.

### S-007 — Remove the unused plan dependency from report assembly — collapse-indirection

**ID / title / category:** `S-007`; Remove the unused plan dependency from report assembly; `collapse-indirection`.

**Anchors:** `src/docmend/writer/apply.py:967-977` (`docmend.writer.apply._build_report`), preview call `:1052-1061`, and write call `:1153-1162`. Plan-dependent completion remains at `_complete_outcomes`, `:948-964`, and immediately precedes both calls.

**Current state:** `_build_report` declares a positional `plan: Plan` parameter but never loads it. Both callers pass `plan` after using it in `_complete_outcomes`; report assembly depends only on seven keyword-only inputs.

**Public/dynamic contract check:** Exact repository search found only the definition and two calls. The private helper is not exported, registered, wrapped, reflected, string-addressed, tested directly, or monkeypatched. Public report models, CLI/public apply functions, artifacts, and schema paths remain unchanged. `Plan` import remains for other annotations and logic. The private signature, annotations, frame locals, arity errors, and malformed direct/private monkeypatch calls change; no tracked contract observes them.

**Intent and convention evidence:** Commit `928717f3` extracted `_complete_outcomes` and `_build_report` from a monolithic flow, putting plan-dependent completion in the former while carrying `plan` into both. No later history, test, comment, spec, or schema gave the latter a purpose. Local convention favors signatures that expose real dependencies.

**Comprehension benefit:** Report assembly's boundary becomes truthful: it receives the plan reference artifact and completed outcomes, not the full plan object. Readers need not inspect the body to determine whether hidden plan data affects totals or serialization.

**Proposed change:** Delete only the `plan: Plan,` positional parameter and the first positional `plan,` line from each of the two calls. Retain all seven keyword-only parameters and their order:

```python
def _build_report(
    *,
    run_id: str,
    plan_ref: ArtifactRef,
    started_at: str,
    completed_at: str,
    outcomes: list[ApplyOutcome],
    dry_run: bool,
    prior_attempt: PriorAttempt | None,
) -> Report:
```

Do not alter `_complete_outcomes`, timestamps, `Counter`, totals, fields, keyword expressions/order, imports, tests, schemas, or docs.

**Replacement target:** Not applicable.

**Automation plan:** Not applicable; exactly three deleted lines in one file.

**Consolidation basis:** The edit removes false indirection/dependency rather than merging boundaries. Plan-dependent completion remains a named separate concern and report construction remains its own testable concept.

**Dependency health:** Not applicable.

**Typing:** Seven keyword-only parameters retain exact annotations and `-> Report`. The private `plan` annotation alone disappears; `Plan` remains imported/used. No precision loss, `Any`, suppression, cast, or public signature change.

**Behavior and error preservation:** The deleted caller expression is only `LOAD_FAST plan`, with no dispatch or exception path; `plan` remains alive in each owner frame. Every retained keyword AST and evaluation order is identical, including `completed_at=now()`. Counter/model construction receives identical values; valid dumps and invalid-run-id `ValidationError` class/message matched. Source lines/frame-local content/private callable metadata change as disclosed, but product traceback frames, report fields, serialization, logging, and cleanup do not.

**Independent verification:** `verifier-build-report`; confirmed with qualification. Exact in-memory transform compiled with unchanged helper-body AST and keyword ASTs, zero positional parameters, seven keyword-only parameters, equal report/dump and validation error, and clean Ruff stdin checks.

**Verification for executor:** Require exactly one definition/two calls and no positional argument at either call. Run:

```bash
uv run --frozen --no-sync ruff format --check src/docmend/writer/apply.py
uv run --frozen --no-sync ruff check src/docmend/writer/apply.py
uv run --frozen --no-sync ruff check --no-cache --select ARG001 src/docmend/writer/apply.py
uv run --frozen --no-sync basedpyright src/docmend/writer/apply.py
uv run --frozen --no-sync pytest tests/test_apply.py tests/test_resume.py tests/test_report_artifact.py \
  tests/test_cli_apply.py tests/test_cli_resume.py
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync basedpyright
uv run --frozen --no-sync coverage run -m pytest
uv run --frozen --no-sync coverage report
uv run --frozen --no-sync pip-audit
```

No private-signature test or existing oracle edit is permitted. Compare baseline identities and revert only this finding if any report/error/diagnostic identity changes.

**Benefit × confidence:** Benefit low: one helper exposes one fewer false dependency. Safety confidence high: complete reference inventory, unchanged body/keywords, direct result/error equivalence, and focused contract coverage.

**Blast radius:** One private function and two calls in one file; three deleted lines. No public path, dependency, schema, test edit, prerequisite, conflict, or automation threshold. It may follow S-006 because both touch `writer/apply.py`, and its diff must be reviewed separately.

### S-008 — Remove unused inputs from backup-destination checking — collapse-indirection

**ID / title / category:** `S-008`; Remove unused inputs from backup-destination checking; `collapse-indirection`.

**Anchors:** `src/docmend/writer/gate.py:155-178` (`docmend.writer.gate._backup_destination`) and sole call at `src/docmend/writer/gate.py:366` (`evaluate_gate`). Behavioral tests: `tests/test_gate.py:224-248` and `:277-297`.

**Current state:** The private helper accepts `(plan: Plan, config: DocmendConfig, source_root: Path, options: ApplyOptions)` but never reads `plan` or `config`. It checks only whether a configured backup root lies outside the mutation root and is writable.

**Public/dynamic contract check:** Full repository search found one definition and one call; a similarly worded test name is only lexical. No export, registry, dynamic lookup, string reference, reflection, monkeypatch, serialization, or direct test targets the helper. Public `evaluate_gate`, `ApplyOptions`, `GateRefusal`, and all refusal order/messages remain. `Plan` and `DocmendConfig` imports remain used elsewhere. Private signature/annotations/code arity and wrong-arity errors narrow, with no tracked observer.

**Intent and convention evidence:** The helper dates to initial safety gate commit `11ea97b3`; both inputs were unused from introduction. Later commit `fba1d3e` moved plan/config-dependent capacity work into `_capacity_preflight`, leaving this stale private channel. The adjacent comment makes containment-before-probe ordering a deliberate no-write refusal contract.

**Comprehension benefit:** The helper signature will state its actual safety inputs, making it clear that destination containment/writability does not depend on plan contents or transform configuration.

**Proposed change:** Change exactly:

```python
def _backup_destination(
    source_root: Path, options: ApplyOptions
) -> list[GateRefusal]:
```

and update the sole call to `_backup_destination(source_root, options)`. Retain every body statement and, critically, the `is_relative_to` short-circuit before `_dir_writable` because the latter may create the destination. Do not remove imports or alter any other gate computation/refusal ordering.

**Replacement target:** Not applicable.

**Automation plan:** Not applicable; one definition and one call in one file.

**Consolidation basis:** This removes stale private dependencies without combining predicates or changing the gate boundary. The named helper, its refusal taxonomy, and safety-order test seam remain intact.

**Dependency health:** Not applicable.

**Typing:** Exact signature is `(source_root: Path, options: ApplyOptions) -> list[GateRefusal]`. No public annotation, import, `Any`, cast, suppression, or precision change.

**Behavior and error preservation:** Caller evaluation removes two `LOAD_FAST` operations only; retained `source_root` then `options` order is unchanged. The null backup check, backup/source resolution, containment refusal and exact message, no-write short-circuit, writability probe, exception behavior, refusal-list ordering, and downstream capacity/manifest checks are byte-for-value identical. Private direct caller/reflection and wrong-arity behavior change as disclosed; no tracked contract observes it.

**Independent verification:** `verifier-backup-destination`; confirmed with qualification. One definition/one call, eight normal/error path traces, anchored and exact in-memory focused suites both 42 passed, Ruff passed, strict BasedPyright returned zero diagnostics, and Ruff ARG001 identified exactly the two removed inputs.

**Verification for executor:** Inspect the two-hunk diff and require containment remains before `_dir_writable`. Run:

```bash
uv run --frozen --no-sync ruff format --check src/docmend/writer/gate.py
uv run --frozen --no-sync ruff check src/docmend/writer/gate.py
uv run --frozen --no-sync ruff check --no-cache --select ARG001 src/docmend/writer/gate.py
uv run --frozen --no-sync basedpyright src/docmend/writer/gate.py
uv run --frozen --no-sync pytest tests/test_gate.py
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync basedpyright
uv run --frozen --no-sync coverage run -m pytest
uv run --frozen --no-sync coverage report
uv run --frozen --no-sync pip-audit
```

No test or oracle edit is permitted. Compare normalized baseline identities; revert only this finding if call ordering, filesystem effects, message, refusal order, or any identity changes.

**Benefit × confidence:** Benefit low: local signature truthfulness at one safety predicate. Safety confidence high: unused inputs and all references were proved, exact paths characterized, and focused overlay/type/lint checks passed.

**Blast radius:** One source file, one private definition, one call, about four changed lines. No public path, dependency, schema, test edit, prerequisite, conflict, or automation threshold.

## Implementation sequence

Global executor preflight, before any characterization or source edit:

1. Use a fresh or equivalently isolated worktree. Require `HEAD` to equal `834f07515a5308edd2d6c97f1cf940233c2e6b01`, an empty index/tracked/untracked status except that this report may be the sole explicit untracked exemption, and no merge/rebase/cherry-pick/revert/bisect/sequencer operation or Git lock. Do not relocate anchors to a newer commit.
2. Recreate the recorded CPython 3.14.6 / uv 0.11.6 / locked project environment without installing or syncing. Confirm Ruff 0.15.20, BasedPyright 1.39.9 / Pyright 1.1.411 strict, pytest 9.1.1, Coverage 7.15.0, and pip-audit 2.10.1. Stop if the effective checker mode, supported platform, dependency versions, or material environment fingerprint differs.
3. Redirect `TMPDIR`, `TMP`, `TEMP`, `UV_CACHE_DIR`, `XDG_CACHE_HOME`, `PYTHONPYCACHEPREFIX`, `RUFF_CACHE_DIR`, `COVERAGE_FILE`, `HYPOTHESIS_STORAGE_DIRECTORY`, and pytest cache/basetemp to an executor-owned scratch directory. Require that the existing environment is present; every command below must use `uv run --frozen --no-sync` or the corresponding already-recorded environment executable.
4. Rerun the unchanged baseline:

   ```bash
   uv run --frozen --no-sync ruff format --check .
   uv run --frozen --no-sync ruff check .
   uv run --frozen --no-sync basedpyright
   uv run --frozen --no-sync coverage run -m pytest
   uv run --frozen --no-sync coverage report
   uv run --frozen --no-sync pip-audit
   ```

   Require the exact normalized state: type and lint identity sets empty; 1,728 tests passed with no non-pass identity; 89% branch coverage; no known vulnerability, with only the same local-project audit skip. Any mismatch other than an exact unchanged-tree fluctuation demonstrated and recorded now is a stop-and-rerun-analysis signal.

5. For each item below, capture a scoped reverse patch before editing; establish any listed scratch characterization; apply only that item; run its targeted checks and the broad baseline; compare identity sets; inspect `git diff --check` and the scoped diff; then continue. If any check fails, reverse only that item's source and characterization/reference edits. Never change an existing assertion, expected value/message/type, golden output, ordering, timeout, retry, or other behavioral oracle to make a finding pass.

Apply in this acyclic order:

1. `S-001` — one-file CLI helper and three calls; no prerequisite.
2. `S-002` — one-file BOM identity-map removal; no prerequisite.
3. `S-003` — four model-config declarations; require the recorded Pydantic versions and schema hashes.
4. `S-004` — one-file incomplete-stage factory; no prerequisite.
5. `S-005` — one-file CPU first-value map; preserve the exact forward-loop/membership form and recorded private-domain qualifications.
6. `S-006` — first `writer/apply.py` change; verify separately before the next item.
7. `S-007` — second `writer/apply.py` change; apply only after the preceding diff and full gate pass so the overlapping file remains attributable.
8. `S-008` — one-file gate signature cleanup; no prerequisite.

No codemod is required. The items are jointly applicable; none changes an input, output, import path, or private symbol consumed by another item.

## Divergences and retained abstractions (do-not-apply)

### D-001 — Retain the literal frontmatter closer tuple

**ID / title:** `D-001`; Retain the literal frontmatter closer tuple.

**Anchors:** `src/docmend/frontmatter.py:32-35` (`_OPEN`, `_CLOSERS`) and `src/docmend/frontmatter.py:55-69` (`extract_frontmatter`, consumption at `:64-67`).

**Current state:** `_OPEN = "---"` and `_CLOSERS = ("---", "...")` look like same-knowledge duplication; `_CLOSERS = (_OPEN, "...")` would make the relation explicit.

**Why left separate/retained:** The proposed name load changes module-initialization bytecode from a constant tuple to `LOAD_NAME` plus allocation. Re-executing one compiled module code object currently reuses the tuple constant; the proposal creates a new tuple. A line tracer deleting `_OPEN` between assignments currently leaves import successful but would raise `NameError`. Module code object/cache identity and import-time evaluation therefore differ. No product test relies on those hostile/private observations, but the benefit is extremely small and the review's explicit import-time/object-identity envelope makes the literal safer to retain.

**Intent/convention evidence:** Both constants and the comment arrived in `fa61d404` and remain unchanged. The comment already documents that `---` opens and closes while `...` is an accepted alternate. The verifier exercised 66,430 input documents and 21 focused tests with equal product results but confirmed the metadata/import-time differences.

**Benefit × confidence:** Future benefit low; confidence high that retention avoids real, if unusual, observable drift for a one-line cosmetic gain.

### D-002 — Retain the defensive frontmatter split-result guard

**ID / title:** `D-002`; Retain the defensive frontmatter split-result guard.

**Anchors:** `src/docmend/frontmatter.py:55-69` (`extract_frontmatter`, especially `:63-64`), `src/docmend/frontmatter.py:91-106` (`validate_frontmatter`), `src/docmend/verify.py:88-114`, and `src/docmend/cli.py:1162-1166`.

**Current state:** After `lines = text.split("\n")`, the guard is `if not lines or lines[0].strip() != _OPEN:`. For exact built-in `str`, the empty-list arm is unreachable.

**Why left separate/retained:** `text: str` admits subclasses and calls `split` virtually. A valid subtype override returning `[]` makes current code return `None`; deleting `not lines or` raises uncaught `IndexError("list index out of range")` before `validate_frontmatter`'s parser/schema handler. Instrumented falsy/truthy split-result sequences also prove changed truth-test, indexing, side-effect, and exception order. Narrowing to exact `str` would be a separate API/behavior change, not simplification.

**Intent/convention evidence:** The guard dates to `fa61d404`; `8245e9e8` changed `splitlines()` to `split("\n")` for Unicode-separator correctness and deliberately retained the guard. FR-016 and ADR-0011 make absent frontmatter legal. Fresh two-phase verifier `verifier-frontmatter-guard-fresh` rejected the exact deletion after 21 focused tests and constructive subtype proof.

**Benefit × confidence:** Future benefit low; confidence high that the apparent dead branch is part of the callable's valid runtime envelope.

### D-003 — Retain the two mismatch-path backup digest evaluations

**ID / title:** `D-003`; Retain the two mismatch-path backup digest evaluations.

**Anchors:** `src/docmend/restore.py:152-184` (`docmend.restore._verified_backup`, digest evaluations at `:176` and `:182`) and sole caller `src/docmend/restore.py:495` (`_prepare_restore`).

**Current state:** On digest mismatch, `_sha(data)` is evaluated once for the comparison and again when formatting the exact ERR-004 detail. Caching a local would visibly tie the reported value to the checked value and avoid a second full hash.

**Why left separate/retained:** The proposal changes mismatch-path evaluation count from two calls to one. A stateful/private monkeypatch can produce a different detail or make the second call raise; the proposal removes that call and failure point. The task explicitly requires preserving evaluation count and failure behavior, so deterministic behavior of the anchored pure helper is insufficient to claim exact equivalence. This is not a performance hotspot demonstrated by evidence.

**Intent/convention evidence:** Both calls originate in restore commit `02e6ad42`; later safety work retained them. Corrupted-backup tests at `tests/test_restore.py:503-529` and `:1619-1638` cover refusal-before-mutation but do not establish a call-count change as contract-safe. Independent verifier confirmed ordinary output equivalence but qualified precisely this private call-count surface.

**Benefit × confidence:** Future benefit low; confidence high that retention honors the prompt's stricter evaluation rule.

### D-004 — Do not alter snapshot equality to enable whole-record comparison

**ID / title:** `D-004`; Do not alter snapshot equality to enable whole-record comparison.

**Anchors:** `src/docmend/scale_build.py:282-290` (`_RegularFileSnapshot.path`) and `:860-888` (`_require_unchanged_file`).

**Current state:** A paired alternative marks `path: Path = field(compare=False)` and then uses `if current != snapshot:` so production comparison covers the same six data/stat fields.

**Why left separate/retained:** Production helper-created exact instances with `Path`/`bytes`/`int` are equivalent, but class-wide semantics are not. Path-only snapshots become equal; generated hash/set/dict behavior drops path; `dataclasses.fields(...)[0].compare` changes; exact-class/subclass behavior changes; generated equality invokes `__eq__` instead of the predicate's `__ne__`; identity/non-reflexive values differ. The paired predicate was also 1.75×–3.06× slower in local microbenchmarks. This broadens a local readability edit into a private data-model contract change.

**Intent/convention evidence:** The dataclass, snapshot helper, and explicit predicate entered together in `67baeecc`; OQ-041 and the build/install contracts treat path as the reread locator while bytes/stat facts determine unchanged content/identity. Fresh conclusion-blind verifier plus exact phase-two adjudication rejected the paired proposal under the strict envelope after 37 repository tests and four property-oracle tests passed for the narrower production domain.

**Benefit × confidence:** Future benefit low; confidence high that retaining the explicit projection avoids equality/hash/reflection drift.

### D-005 — Do not use bare dataclass inequality for regular snapshots

**ID / title:** `D-005`; Do not use bare dataclass inequality for regular snapshots.

**Anchors:** `src/docmend/scale_build.py:282-290` (`_RegularFileSnapshot`), `:823-857` (`_snapshot_regular_file`), and `:860-888` (`_require_unchanged_file`, predicate `:877-884`).

**Current state:** Six explicit `!=` comparisons omit the `path` locator. Replacing the block with `if current != snapshot:` looks shorter because the dataclass already generates equality.

**Why left separate/retained:** Existing dataclass equality includes `path`, uses `__eq__` rather than each field's `__ne__`, has an identity fast path, and requires exact runtime class. The bare change therefore adds a `Path.__eq__` call/exception, rejects structurally matching subclasses, changes custom operator behavior, and automatically includes future fields. The explicit block defines a selective six-fact change detector, not whole-record identity.

**Intent/convention evidence:** Class, snapshot helper, and explicit predicate entered together in `67baeecc`; later history did not drift them. The exact verifier demonstrated the custom-path exception difference despite 113 ordinary focused tests passing. OQ-041 and build/install contracts treat path as the reread locator, while bytes/stat facts determine unchanged content/identity.

**Benefit × confidence:** Future benefit low; confidence high that explicit comparison better communicates and preserves the security boundary.

### D-006 — Retain explicit ExitStack close semantics in the stage runner

**ID / title:** `D-006`; Retain explicit ExitStack close semantics in the stage runner.

**Anchors:** `src/docmend/scale_stage.py:840-1009` (`docmend.scale_stage._run_stage_at`), especially `ExitStack()`/`try`/`finally` at `:870-1004`, descriptor transfers at `:872-875`, and outer descriptor fallback at `:1005-1009`.

**Current state:** `output_files = ExitStack()` is closed explicitly in `finally`; the conventional `with ExitStack() as output_files:` spelling would remove the manual pair.

**Why left separate/retained:** `ExitStack.close()` invokes exits without an active exception; `with` forwards the active exception and can honor a nonstandard injected context manager's suppression result. Real binary file objects do not suppress, but a monkeypatched replacement can change propagation. The edit also reindents roughly 130 safety-critical state-machine lines, creating review noise disproportionate to one paired close removal.

**Intent/convention evidence:** The cleanup frame came from `21d617e9`; later telemetry fixes changed nested lifecycle semantics but not ownership. `tests/test_scale_stage_runner.py:1585-1607` proves cleanup when the second `os.fdopen` fails. Explicit descriptor ownership/fallback is a useful safety boundary.

**Benefit × confidence:** Future benefit low; confidence high that the current explicit ceremony is easier to audit than a wide reindent with a real suppression difference.

### D-007 — Retain the caller-owned path count in manifest finalization

**ID / title:** `D-007`; Retain the caller-owned path count in manifest finalization.

**Anchors:** `src/docmend/writer/manifest.py:676-711` (`_order_chain`), `:855-863` (`_finish_chain_validation`), and callers `:866-879` / `:882-887`.

**Current state:** `_order_chain(paths, sets)` uses `paths` only for `len(paths)` in the one-root error; each caller builds one `sets` item per input path, so using `len(sets)` and removing the channel appears redundant.

**Why left separate/retained:** The annotated inputs are sequences, not frozen tuples. Removing `paths` changes when/how many times a custom or concurrently mutable sequence is observed and can change `__len__` side effects, exception type/message timing, and the exact count rendered in a public reader error. The gain is a private parameter removal across two helpers and two callers, while the current value directly names the external path input whose count is reported.

**Intent/convention evidence:** `_order_chain` came from `2708b9a1`; finalization extraction came from `7bb75b82`. Tests cover deterministic order, empty/fork/gap/bad-link and the two-root error. No history proves the sequence inputs are immutable/exact-list contracts, so strict equivalence is not established.

**Benefit × confidence:** Future benefit low; confidence medium that retention avoids an uncharacterized mutable/custom-sequence observation change.

## Judgment-call observations (manual review only)

### J-001 — Consider naming the heartbeat's exact non-negative-integer predicate

**ID / title:** `J-001`; Consider naming the heartbeat's exact non-negative-integer predicate.

**Anchors:** `src/docmend/observability.py:75-76` (`ProgressHeartbeat.start`), `:123-124` (`finish`), and `:192-195` (`_validate_counts`); public class callers across CLI, discovery, planning, verify, coverage, and writer are enumerated in `ultra/semantic-runtime/result.md`.

**Observed comprehension cost:** Three sites repeat `type(value) is int and value >= 0`; exact type matters because `bool` is an `int` subclass. A name such as `_is_non_negative_int(value: object) -> bool` could expose that intent.

**Why judgment is required:** The public heartbeat state machine has distinct `None` allowances, messages, monotonicity, lifecycle, and clock-consumption order. Existing tests cover successful lifecycle but not invalid/negative/bool boundaries or validation-versus-clock order. Whether a small predicate name helps more than a cross-site jump is a readability decision after objective characterization; it is not ready for automatic extraction.

**Convention/history context:** `fba1d3e1` introduced lifecycle/caller choreography as one feature. ProgressHeartbeat is public and directly imported; only a new underscore predicate is contemplated. Local convention preserves explicit validation at state boundaries.

**Suggested direction:** If a maintainer prefers the name, first add table-driven characterization for `total`, all counts, `not_attempted`, booleans, exact errors, clock calls, and lifecycle order; then extract only the pure predicate and preserve each site's surrounding order.

**Benefit × confidence:** Benefit low; confidence medium that the bounded direction is safe after characterization, with subjective readability remaining.

### J-002 — Consider sharing only pending-restore interference outcome formatting

**ID / title:** `J-002`; Consider sharing only pending-restore interference outcome formatting.

**Anchors:** `src/docmend/restore.py:233-247` (`_preview_pending_restore`, constructor `:239-246`) and `src/docmend/restore.py:374-409` (`_converge_pending_restore`, constructor `:387-394`).

**Observed comprehension cost:** Two branches build the same failed `RestoreOutcome` with action/path/status and `ERR-002: {detail}` text.

**Why judgment is required:** Both explicit blocks are locally short and obvious; a helper adds a navigation jump. Existing tests do not pair-pin the exact preview and convergence detail shapes. Choosing central text ownership versus local explicitness is a decomposition judgment, not missing objective safety evidence for the narrow value construction.

**Convention/history context:** Restore design intentionally separates read-only preview from write convergence and uses sealed `_RestoreRun` capability state. Any helper must be pure outcome formatting only and must not accept runtime state, manifest writer, hooks, root, chain, or a write flag.

**Suggested direction:** If central text ownership is preferred, first characterize both public outcome dumps/errors, then introduce one private fully typed helper accepting only `action_id`, intent/path data, and detail. Do not merge traversal, adjudication, or mutation flows.

**Benefit × confidence:** Benefit low; confidence medium that the narrow helper is behaviorally viable, but likely not clearer at only two sites.

### J-003 — Revisit carried write-authority attestation fields only as a design decision

**ID / title:** `J-003`; Revisit carried write-authority attestation fields only as a design decision.

**Anchors:** `src/docmend/writer/commit.py:321-338` (`_Attestation`), `source_root` declaration `:326` and constructions `:607,658`, `subject_sha256` declaration `:331` and constructions `:612,663`.

**Observed comprehension cost:** Repository-wide search found no read of `_attest.source_root` or `.subject_sha256`, so the private frozen dataclass appears to carry dead state.

**Why judgment is required:** The class explicitly represents immutable write authority. Removing fields changes dataclass equality/repr and removes evaluation of the restore fallback `tip.sha256 or manifest_sha256(tip.path)`. Safety design may intentionally carry authority even before every confirmation method consumes it. Deciding whether those facts are anticipatory capability evidence or obsolete state is a domain/security boundary decision, not dead-code cleanup.

**Convention/history context:** `_Attestation` and both fields originated in `e8ebef44`; the safety-core plan explicitly specifies them. `8245e9e8` later repaired restore lock-release structure without removing them. A prior review called one fallback dead, but did not authorize capability redesign.

**Suggested direction:** Review the write-capability model and future confirmation obligations explicitly. Remove a field only if the owner decides it is not part of authority, then characterize construction evaluation, repr/equality, restore fallback, and every commit/restore path as a separate design change.

**Benefit × confidence:** Potential benefit medium; confidence low on domain intent, so no executor action.

## Blocked candidates

None.

## Final audit

- **Fresh auditor:** `final-auditor`; verdict PASS, followed by re-audit of the exact publication candidate.
- **Coordinator resolutions:** Fresh final audit passed. Expected publication placeholders were resolved, the final-audit manifest row was completed, the deterministic D-ordering rule was enforced without changing either retained disposition, and no self-referential report hash was embedded.
- **Heading/schema reconciliation:** exactly 12 required headings in the required order; every finding block contains its complete status schema.
- **ID/count reconciliation:** S=8, D=7, J=3, B=0. Actionable IDs are contiguous and occur exactly once in the implementation sequence; every disposition is mutually exclusive.
- **Baseline comparison rule:** normalized diagnostic and non-pass identity sets, with touched-line remapping by enclosing symbol/stable context; count equality alone is insufficient. Existing behavioral oracles are immutable stop signals.
- **Source/worktree integrity:** anchored SHA `834f07515a5308edd2d6c97f1cf940233c2e6b01`; 40/40 included files remained byte-identical and tracked; current guard SHA-256 `f51408b4c24300419f9e7d87af0d750e5e69d380a142d308bac239e688cf42e7`; the exact integrity checker passed immediately before and after exclusive publication.
- **Final Git status:** protected porcelain contains only `?? docs/reviews/2026-07-21-code-simplification.md`; no tracked path changed.
- **Actual report path:** `/home/chris/projects/docmend/docs/reviews/2026-07-21-code-simplification.md`; the final report SHA-256 is intentionally not self-embedded. The run-local exclusive-publication receipt records the final byte count and SHA-256, and publication verifies byte-for-byte identity with the audited draft.
- **Local exclude:** before the overall review, 541 bytes / SHA-256 `321dffcb77a68a6c079d35da12944866b895b4cc9fb3b1fae72fe9468c7eafeb`; after one exact appended `/.scratch/code-simplify/` rule, 566 bytes / SHA-256 `8ffe9f8c9568d546748ad9c2678e07a9a78c398ff00efdc5e24246cbd74e899b`. The override continuation made no further exclude edit.
- **Secret hygiene:** no credential/token/private-key/connection-string value persisted; no evidence was withheld for secret risk; credential-pattern scans of verifier artifacts were negative.
- **Evidence completeness:** every report claim maps to the indexed anchored source/history, a listed opened-file ledger, sanitized command output, test/probe result, or an explicit limitation. No network source or unassessed dependency claim is used.
- **Incident accounting:** predecessor cache-metadata incidents are preserved and disclosed; the fresh override guard treated them as immutable pre-existing state. No source/config/test/doc/handoff path was modified during analysis; unsafe predecessor paired-snapshot evidence was excluded from promotion.
