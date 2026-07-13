# Million-File Scale and Resource Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close DMR-08 for docmend v2.0.0 with an honest bounded-linear resource contract, sequential-only configuration, plan schema 2.0, tiered scale qualification, pilot-derived RSS thresholds, and accepted one-million-file evidence.

**Architecture:** Preserve the existing whole-run inventory/plan/report model while measuring each installed-CLI stage in a separate uninstrumented subprocess. A repo-only qualification orchestrator produces strict, sanitized evidence; a fresh single-child supervisor owns each stage's external RSS measurement; source-tree pytest covers the 1,000-file PR guard, while built-wheel qualification owns the 100,000- and 1,000,000-file tiers. Change control lands before code, and a second spec revision freezes numeric thresholds only after the real 100,000-file pilot.

**Tech Stack:** Python 3.14, uv, Pydantic v2, JSON Schema Draft 2020-12, Typer, pytest, Ruff, BasedPyright strict, GitHub Actions, POSIX `/proc` and `resource` APIs.

---

## Task 6 Contract Amendment (2026-07-13)

Three independent pre-implementation reviews found that the original four-file Task 6 could not satisfy its own evidence/provenance requirements: scale-evidence 1.1 rejects truthful pre-scan/partial totals, public stage exits cannot represent the private supervisor's spawn/reap result, the threshold helper derives an absolute ceiling from the largest 100k observation instead of the required 1M projection, and the build backend is range-resolved outside `uv.lock`. SPEC-VHHB revision 0.34 and OQ-041 authorize the bounded assumptions in the approved design's Task 6 amendment.

Task 6 is split into 6A contract completion and 6B orchestration. Tasks 7-12 retain their approved order and scope. This amendment does not pull heartbeat integration, the pilot, workflow, file-size matrix, or accepted release evidence forward.

## File Map

| File | Responsibility |
| --- | --- |
| `docs/specs/docmend.md` | OQ-037, revision-one contract, revision-two measured thresholds, traceability. |
| `docs/resolved-questions.md`, `docs/open-questions.md` | Settled OQ/RQ-037 and registry synchronization. |
| `docs/adr/adr-0022-sequential-million-file-scale-contract.md` | Current scale/concurrency decision, superseding ADR-0007. |
| `docs/adr/adr-0005-durable-artifact-schema-contract.md` | Plan schema 2.0 clean break. |
| `docs/adr/adr-0007-concurrency-primitive-process-pool.md`, `docs/adr/index.md`, `docs/adr/adr-backlog.md` | Reciprocal supersession and navigation. |
| `src/docmend/config.py` | Remove `parallel.*`; reject legacy tables with a migration message. |
| `src/docmend/plan.py`, `src/docmend/schemas/plan.schema.json` | Plan 2.0 and supported-version contract. |
| `src/docmend/artifacts.py`, `src/docmend/cli.py`, `src/docmend/writer/commit.py` | Reject plan 1.x before gate/mutation with regeneration guidance. |
| `src/docmend/scale_evidence.py` | Strict evidence/reference models, validation, fitting, sanitization, no-clobber acceptance. |
| `src/docmend/scale_resources.py` | Mount classification, capacity/inode preflight, reference matching, swap evidence. |
| `src/docmend/scale_stage.py` | Typed one-child external-RSS supervisor implementation. |
| `src/docmend/scale_qualification.py` | Typed four-stage qualification orchestration and CLI parser. |
| `src/docmend/scale_build.py` | Exact clean-HEAD archive, fixed-backend wheel build, locked venv installation, and import-origin proof. |
| `src/docmend/scale_reconcile.py` | Complete inventory/plan/report/manifest/verify and boundary-output reconciliation. |
| `src/docmend/schemas/scale-evidence.schema.json`, `reference-environment.schema.json`, `scale-thresholds.schema.json` | Public qualification contracts, separate from product `ArtifactKind`. |
| `src/docmend/scale_corpus.py` | Streaming deterministic million-file recipe source, expected findings, and exact budget summary. |
| `src/docmend/frontmatter.py` | Code-owned current frontmatter schema version for qualification provenance. |
| `scripts/measure_scale_stage.py` | One-child supervisor for external RSS and private output capture. |
| `scripts/qualify_scale.py` | Repo-only four-stage qualification orchestrator. |
| `tests/test_scale*.py`, `tests/test_config.py`, `tests/test_plan_artifact.py`, `tests/test_cli_*.py`, `tests/unit/writer/test_commit.py` | TDD coverage for every new contract, including exact build and complete reconciliation. |
| `docs/scale-evidence/README.md`, `reference-environment.json`, `thresholds.json`, `supporting/*.json`, `accepted/*.json` | Sanitized, reviewed evidence, executable thresholds, and environment identity. |
| `.github/workflows/scale-qualification.yml` | Repo-owned scheduled/manual diagnostic 100k lane. |
| `src/docmend/observability.py`, stage loops, `src/docmend/writer/gate.py` | Best-effort aggregate liveness and evidence-based capacity accounting. |
| `README.md`, `docs/STATUS.md`, `docs/TODO.md`, `docs/handoff/*` | Operator contract and durable project state. |

### Task 1: Land OQ-037, SPEC revision one, and ADR change control

**Files:**

- Create: `docs/adr/adr-0022-sequential-million-file-scale-contract.md`
- Modify: `docs/specs/docmend.md`
- Modify: `docs/resolved-questions.md`
- Modify: `docs/open-questions.md`
- Modify: `docs/adr/adr-0005-durable-artifact-schema-contract.md`
- Modify: `docs/adr/adr-0007-concurrency-primitive-process-pool.md`
- Modify: `docs/adr/index.md`
- Modify: `docs/adr/adr-backlog.md`
- Modify: `docs/TODO.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/handoff/specs-plans.md`

- [ ] **Step 1: Add settled OQ/RQ-037**

Add this §21 row to `docs/specs/docmend.md`:

```markdown
| OQ-037 | What scale and execution contract replaces the invalid 100k/parallel NFR-001 evidence for v2.0.0? | One through 1,000,000 files; whole-run metadata may grow linearly while per-file bodies never accumulate; v2.0.0 is sequential-only and removes `parallel.*`; plan schema 2.0 removes the legacy snapshot field; 1M must complete within 12 hours; numeric RSS limits are frozen only after the uninstrumented 100k pilot defined by the approved design. | Yes | owner | Before DMR-08 implementation | Resolved; canonical ADR `adr-0022-sequential-million-file-scale-contract` |
```

Add `RQ-037` to `docs/resolved-questions.md` with the same decision, owner approval dated 2026-07-11, and canonical links to the design, SPEC sections, ADR-0022, and amended ADR-0005. Change the settled range and placeholder comment in `docs/open-questions.md` from 036 to 037. Preserve older RQ text; add supersession pointers instead of rewriting history.

- [ ] **Step 2: Author ADR-0022 and reciprocal supersession**

Create ADR-0022 from the repository template with this decision outcome:

```markdown
## Decision Outcome

docmend v2.0.0 supports sequential execution from one file through a binding 1,000,000-file qualification. The `parallel.*` configuration namespace is removed; a legacy table is an exit-2 migration error before scanning, while the default/no-config path remains valid. Whole-run artifact metadata may grow linearly, but per-file body content may not accumulate. Process concurrency may return only after the 1M workflow exceeds 12 hours on the accepted reference environment and a separately approved design proves equivalence, parent-only shared-artifact writes, worker isolation, and a hard watchdog boundary.
```

Set ADR-0007 to `status: superseded` with `superseded_by` pointing at ADR-0022. Amend ADR-0005 to define plan 2.0, removal of the required `parallel` snapshot, 1.x rejection, and inventory reuse. Update ADR index/backlog reciprocally.

- [ ] **Step 3: Revise SPEC-VHHB to revision 0.30**

Apply the approved design to G-006, NFR-001, IR-006, DR-002, FR-019, ERR-006/009, §§3.1, 8.1, 8.5, 9, 14, 17.2, 17.3, 18.2, 18.5, 19, 20, §21, and DEV-002. Requirements must state:

```markdown
NFR-001: docmend shall qualify the installed scan -> plan -> apply --write -> verify --plan workflow at 1,000,000 files on one accepted Linux/POSIX reference environment. Whole-run artifact metadata may grow linearly with file count; per-file body content shall not accumulate. v2.0.0 executes sequentially. The numeric RSS ceiling and slope remain provisional until the specified external, uninstrumented 100,000-file pilot is accepted in revision two.
```

Regress NFR-001 to Partial. Register the scale-evidence and reference-environment contracts, accepted location, non-overwrite rule, external RSS lane, separate allocation diagnostic lane, disk-backed environment, swap deltas, PR/100k/1M tiers, 12-hour trigger, best-effort heartbeat, and plan 2.0 regeneration error.

- [ ] **Step 4: Update the durable queue and plan pointer**

Expand the existing DMR-08 TODO item into change control, config/plan 2.0, evidence/harness, 100k pilot, revision two, scheduled 100k, 1M qualification, file-size envelope, and closeout subitems. Keep the real-library rollout blocked. Point `docs/handoff/specs-plans.md` at this design and plan; keep `docs/STATUS.md` concise.

- [ ] **Step 5: Run change-control validation**

Run:

```bash
uv run python scripts/fix_spec_toc.py
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec validate --config .project-standards.yml
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec lint --strict --config .project-standards.yml
uv run python scripts/check_traceability.py
npx --yes prettier@3.6.2 --check docs/specs/docmend.md docs/resolved-questions.md docs/open-questions.md docs/adr docs/TODO.md docs/STATUS.md docs/handoff/specs-plans.md
npx --yes markdownlint-cli2@0.18.1 docs/specs/docmend.md docs/resolved-questions.md docs/open-questions.md docs/adr docs/TODO.md docs/STATUS.md docs/handoff/specs-plans.md
git diff --check
```

Expected: all commands exit 0; OQ-037 has exactly one §21 row and one RQ record; ADR-0007/0022 supersession is reciprocal.

- [ ] **Step 6: Commit the atomic change-control set**

```bash
git add docs/specs/docmend.md docs/resolved-questions.md docs/open-questions.md \
  docs/adr docs/TODO.md docs/STATUS.md docs/handoff/specs-plans.md
git commit -m "docs(spec): bind million-file scale contract"
```

### Task 2: Remove inert parallel configuration and bump plan schema to 2.0

**Files:**

- Modify: `src/docmend/config.py`
- Modify: `src/docmend/plan.py`
- Modify: `src/docmend/artifacts.py`
- Modify: `src/docmend/cli.py`
- Modify: `src/docmend/watchdog.py`
- Modify: `src/docmend/writer/commit.py`
- Modify: `src/docmend/schemas/plan.schema.json`
- Modify: `src/docmend/schemas/README.md`
- Modify: `README.md`
- Test: `tests/test_config.py`
- Test: `tests/test_cli_scan.py`
- Test: `tests/test_plan_artifact.py`
- Test: `tests/test_schemas.py`
- Test: `tests/test_cli_apply.py`
- Test: `tests/unit/writer/test_commit.py`

- [ ] **Step 1: Write failing config-migration tests**

Add:

```python
@pytest.mark.parametrize(
    "body",
    [
        "[parallel]\n",
        "[parallel]\nenabled = false\n",
        "[parallel]\nmodel = 'process'\n",
        "[parallel]\nworkers = 'auto'\n",
        "[parallel]\nstart_method = 'forkserver'\n",
        "[parallel]\nchunksize = 'auto'\n",
        "[parallel]\nmaxtasksperchild = 100\n",
    ],
)
def test_legacy_parallel_table__migration_error(tmp_path: Path, body: str) -> None:
    path = tmp_path / "docmend.toml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ConfigError, match=r"parallel execution never shipped.*remove.*parallel"):
        load_config(path)


def test_empty_toml__yields_defaults(tmp_path: Path) -> None:
    path = tmp_path / "docmend.toml"
    path.write_text("", encoding="utf-8")
    assert load_config(path) == DocmendConfig()
    assert "parallel" not in DocmendConfig.model_fields
```

Add a CLI test that monkeypatches `docmend.cli.discovery.scan`, invokes `scan --config`, expects exit 2 and no call/artifact.

- [ ] **Step 2: Write failing plan 2.0 compatibility tests**

Update plan fixtures to expect `2.0`, remove `parallel` from config snapshots, and add:

```python
def test_read_plan_1_x__regenerate_error(tmp_path: Path) -> None:
    path = tmp_path / "old-plan.json"
    document = minimal_plan_document()
    document["schema_version"] = "1.2"
    document["config"]["parallel"] = {
        "enabled": False,
        "model": "process",
        "workers": "auto",
        "start_method": "forkserver",
        "chunksize": "auto",
        "maxtasksperchild": None,
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ArtifactError, match=r"plan schema 1\.2.*regenerate.*v2"):
        read_plan_snapshot(path)
```

Pin the same message through CLI dry-run and `apply_write_context`; assert no gate, lock, report, or mutation occurs.

- [ ] **Step 3: Run the focused tests and confirm RED**

```bash
uv run pytest tests/test_config.py tests/test_cli_scan.py tests/test_plan_artifact.py \
  tests/test_schemas.py tests/test_cli_apply.py tests/unit/writer/test_commit.py -q
```

Expected: failures show the current `ParallelConfig`, plan 1.2 schema, and generic validation behavior.

- [ ] **Step 4: Remove the config surface and add the migration boundary**

Delete `PositiveIntOrAuto`, `ParallelConfig`, and `DocmendConfig.parallel`. In `load_config`, immediately after TOML parsing add:

```python
if "parallel" in raw:
    msg = (
        f"{path}: invalid configuration — parallel execution never shipped; "
        "docmend v2 is sequential, so remove the entire [parallel] section"
    )
    raise ConfigError(msg)
```

Do not alias `workers="auto"`; do not leave dead fields in the model.

- [ ] **Step 5: Implement plan schema 2.0 and explicit legacy rejection**

Set `PLAN_SCHEMA_VERSION = "2.0"`, change the model/schema pattern to `^2\.[0-9]+$`, and remove `parallel` from the schema's config required list and properties. In `artifacts.py`, after JSON parsing and before schema validation:

```python
def _reject_legacy_plan(document: object, path: Path) -> None:
    if not isinstance(document, dict) or document.get("schema") != "docmend/plan":
        return
    version = document.get("schema_version")
    if isinstance(version, str) and version.startswith("1."):
        raise ArtifactError(
            f"{path}: plan schema {version} is not executable by docmend v2; "
            "regenerate the plan with docmend v2 (the inventory may be reused)"
        )
```

Call it from `read_plan_snapshot`. Keep future 2.x-minor checks in CLI/commit; update them to compare against the 2.0 constant. Synchronize schema README.

Update the watchdog's architectural comment so it describes the sequential cooperative boundary without promising a future process pool. Remove the `parallel.*` configuration table from README and add the v2 migration error; do not claim million-file qualification before accepted evidence exists.

- [ ] **Step 6: Run focused tests and confirm GREEN**

Run the Step 3 command.

Expected: all selected tests pass; default/no-config remains valid; every legacy parallel table and plan 1.x path fails before work.

- [ ] **Step 7: Run the Python gate and commit**

```bash
uv run ruff format .
uv run ruff check . --fix
uv run python scripts/check.py
git diff --check
git add src/docmend/config.py src/docmend/plan.py src/docmend/artifacts.py \
  src/docmend/cli.py src/docmend/watchdog.py src/docmend/writer/commit.py \
  src/docmend/schemas README.md \
  tests/test_config.py tests/test_cli_scan.py tests/test_plan_artifact.py \
  tests/test_schemas.py tests/test_cli_apply.py tests/unit/writer/test_commit.py
git commit -m "feat(config): remove inert parallel surface"
```

### Task 3: Add strict scale-evidence and reference-environment contracts

**Files:**

- Create: `src/docmend/scale_evidence.py`
- Create: `src/docmend/schemas/scale-evidence.schema.json`
- Create: `src/docmend/schemas/reference-environment.schema.json`
- Create: `src/docmend/schemas/scale-thresholds.schema.json`
- Create: `tests/test_scale_evidence.py`
- Modify: `tests/test_schemas.py`
- Modify: `src/docmend/schemas/README.md`

- [ ] **Step 1: Write failing evidence model/schema tests**

Test strict Draft 2020-12 schemas, Pydantic/schema agreement, rejection of unknown/private fields, no-clobber acceptance, threshold-baseline provenance/loading, and threshold math:

```python
def test_binding_evidence__forbids_private_fields() -> None:
    forbidden = {"hostname", "username", "argv", "stdout", "stderr", "workspace", "corpus_path"}
    assert forbidden.isdisjoint(ScaleEvidence.model_fields)


def test_accepted_evidence__never_overwrites(tmp_path: Path) -> None:
    evidence = passing_evidence()
    path = tmp_path / "accepted.json"
    write_scale_evidence(evidence, path, accepted=True)
    with pytest.raises(FileExistsError):
        write_scale_evidence(evidence, path, accepted=True)


def test_thresholds__use_pilot_plus_headroom() -> None:
    fit = fit_peak_rss_slope([MemoryPoint(files=10_000, peak_rss_bytes=100_000_000), MemoryPoint(files=100_000, peak_rss_bytes=550_000_000)])
    thresholds = derive_thresholds(fit, largest_peak_bytes=550_000_000, headroom=0.25)
    assert thresholds.absolute_peak_rss_bytes == 687_500_000
    assert thresholds.slope_bytes_per_file >= fit.slope_bytes_per_file
```

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
uv run pytest tests/test_scale_evidence.py tests/test_schemas.py -q
```

Expected: import/schema failures because the evidence contracts do not exist.

- [ ] **Step 3: Implement strict models and pure threshold functions**

Create frozen strict models with these required shapes:

```python
type EvidenceStatus = Literal["passing", "failed", "incomplete", "diagnostic"]
type QualificationTier = Literal["pr", "pilot", "scheduled", "release", "file-size"]

class MemoryPoint(_StrictModel):
    files: Annotated[int, Field(gt=0)]
    peak_rss_bytes: Annotated[int, Field(gt=0)]

class StageEvidence(_StrictModel):
    stage: Literal["scan", "plan", "apply", "verify"]
    run_id: RunId | None
    elapsed_seconds: Annotated[float, Field(ge=0)]
    files_per_second: Annotated[float, Field(ge=0)]
    bytes_per_second: Annotated[float, Field(ge=0)]
    peak_rss_bytes: Annotated[int, Field(ge=0)]
    vm_swap_peak_bytes: Annotated[int, Field(ge=0)]
    exit_code: int
    completed: bool
    artifact_bytes: dict[str, Annotated[int, Field(ge=0)]]

class ScaleEvidence(_StrictModel):
    schema_kind: Literal["docmend/scale-evidence"] = Field(alias="schema")
    schema_version: Literal["1.0"] = "1.0"
    status: EvidenceStatus
    tier: QualificationTier
    candidate_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    package_version: str
    wheel_sha256: Sha256 | None
    lock_sha256: Sha256
    reference_environment_sha256: Sha256
    artifact_schema_versions: dict[str, str]
    python_version: str
    cache_classification: Literal["cold", "warm", "mixed"]
    started_at: AwareDatetime
    completed_at: AwareDatetime
    preflight: PreflightEvidence
    file_count: Annotated[int, Field(gt=0)]
    corpus_bytes: Annotated[int, Field(ge=0)]
    stages: list[StageEvidence]
    totals: QualificationTotals
    thresholds: ThresholdVerdict | None

class ThresholdBaseline(_StrictModel):
    schema_kind: Literal["docmend/scale-thresholds"] = Field(alias="schema")
    schema_version: Literal["1.0"] = "1.0"
    reference_environment_sha256: Sha256
    measurement_points: tuple[ThresholdPointIdentity, ThresholdPointIdentity]
    fitting_method: Literal["exact-linear-least-squares"]
    limits: ThresholdSet
```

Use exact integer least-squares math or `fractions.Fraction`; do not add NumPy. Accepted evidence requires `status="passing"` and publishes through `write_json_artifact(..., clobber=False)`. An incomplete stage may have `run_id=None` when the child failed before publishing an artifact; model/schema conditionals require a run ID for every completed stage. Evidence also records the sanitized reference fingerprint, artifact-schema map, cache class, timestamps, aggregate throughput, and byte/inode preflight verdict explicitly rather than leaving them in private logs.

- [ ] **Step 4: Add separate schemas and validators**

Keep qualification schemas out of `ARTIFACT_KINDS`. Load them through `importlib.resources`, validate with cached `Draft202012Validator`, and add dedicated strict/satisfiability tests. Define `ReferenceEnvironment` with public-safe CPU architecture/model, CPU count, RAM, storage class, filesystem, an allowlist of value-free flags such as `ro`, `rw`, `relatime`, `noatime`, `nodiratime`, `lazytime`, `sync`, and `dirsync`, Python/kernel versions, and explicit forbidden identity fields. Reject every option containing `=` and every unknown flag from public models so subvolume paths, user data, credentials, and device identifiers cannot leak.

`ThresholdBaseline` validates exactly the 10k and 100k evidence identities/hashes, their shared reference hash, fitting method, and frozen limits. Add a loader that rejects an unsupported version, missing point, hash/reference mismatch, or non-passing 100k point. Scheduled and release requests require this validated baseline; tests prove the evaluated values come from it rather than duplicated constants or specification prose.

- [ ] **Step 5: Run tests, full gate, and commit**

```bash
uv run pytest tests/test_scale_evidence.py tests/test_schemas.py -q
uv run python scripts/check.py
git add src/docmend/scale_evidence.py src/docmend/schemas tests/test_scale_evidence.py tests/test_schemas.py
git commit -m "feat(scale): define qualification evidence"
```

### Task 4: Implement mount, capacity, reference, and swap preflight

**Files:**

- Create: `src/docmend/scale_resources.py`
- Create: `tests/test_scale_resources.py`

- [ ] **Step 1: Write failing resource tests**

Cover mountinfo escaping/longest-prefix selection, ext4/XFS/btrfs acceptance, tmpfs/overlay/network rejection, public mount-flag allowlisting and value rejection, shared-device aggregation, block rounding, inode shortage, byte shortage, reference mismatch, and child swap:

```python
def test_capacity__shared_filesystem_sums_once() -> None:
    result = check_capacity(
        requirements=[Requirement(path=Path("/corpus"), bytes=100, inodes=10), Requirement(path=Path("/artifacts"), bytes=50, inodes=5)],
        stat_path=lambda _path: SimpleNamespace(st_dev=7),
        statvfs=lambda _path: fake_statvfs(bytes_available=149, inodes_available=15),
    )
    assert result.ok is False
    assert result.filesystems[0].required_bytes == 150


def test_binding_environment__rejects_tmpfs() -> None:
    observed = reference_environment(filesystem="tmpfs", storage_class="memory")
    assert compare_reference_environment(observed, accepted_reference()).binding is False
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
uv run pytest tests/test_scale_resources.py -q
```

- [ ] **Step 3: Implement resource primitives**

Implement:

```python
ALLOWED_BINDING_FILESYSTEMS = frozenset({"ext4", "xfs", "btrfs"})
REJECTED_NETWORK_FILESYSTEMS = frozenset({"nfs", "nfs4", "cifs", "smb3"})

def allocated_bytes(size: int, fragment_size: int) -> int:
    return ((size + fragment_size - 1) // fragment_size) * fragment_size

def available_capacity(stats: os.statvfs_result) -> tuple[int, int]:
    return stats.f_bavail * stats.f_frsize, stats.f_favail
```

Parse `/proc/self/mountinfo` with octal escape decoding, choose the longest containing mount, and aggregate requirements by `st_dev`. Treat global `/proc/vmstat` swap deltas as diagnostic; make child `VmSwap == 0` the binding rule.

- [ ] **Step 4: Run tests/gate and commit**

```bash
uv run pytest tests/test_scale_resources.py -q
uv run python scripts/check.py
git add src/docmend/scale_resources.py tests/test_scale_resources.py
git commit -m "feat(scale): add qualification resource preflight"
```

### Task 5: Add streaming corpus recipes and one-child RSS supervisor

**Files:**

- Create: `src/docmend/scale_corpus.py`
- Create: `src/docmend/scale_stage.py`
- Create: `scripts/measure_scale_stage.py`
- Create: `tests/test_scale_corpus.py`
- Create: `tests/test_scale_stage_runner.py`

- [ ] **Step 1: Write failing streaming and supervisor tests**

```python
def test_iter_recipes__does_not_materialize_count() -> None:
    recipes = iter_recipes(1_000_000)
    assert isinstance(recipes, Iterator)
    assert next(recipes).path.endswith("doc000000.txt")


def test_binding_child__strips_tracing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PYTHONTRACEMALLOC", "25")
    result = run_stage([sys.executable, "-c", "print('ok')"], cwd=tmp_path)
    assert result.completed is True
    assert result.tracing_enabled is False
    assert result.stdout_path.is_relative_to(tmp_path)
```

Also test fixed argv with `shell=False`, nonzero exit evidence, Linux KiB-to-bytes conversion, private stdout/stderr files, and exactly one waited child per supervisor.

- [ ] **Step 2: Run tests and confirm RED**

```bash
uv run pytest tests/test_scale_corpus.py tests/test_scale_stage_runner.py -q
```

- [ ] **Step 3: Stream corpus generation**

Reimplement the existing 40-bucket behavior in `src/docmend/scale_corpus.py` as a stdlib-only deterministic `ScaleRecipe` stream; do not import the dev-only Faker package or any `tests` module from shipped source. The same module owns rendering, streaming materialization, budget summarization, boundary samples, and `expected_finding_keys(count)` so pytest and the qualification orchestrator derive intentional skip findings from one source of truth. Use a fresh `random.Random` with the fixed seed for the no-write budget pass and reset it before materialization so predicted and actual bytes match. Preserve the existing recipe-class distribution and semantics, not Faker's incidental prose bytes.

- [ ] **Step 4: Implement the fresh supervisor**

Implement the typed logic in `src/docmend/scale_stage.py`. `scripts/measure_scale_stage.py` is only:

```python
from docmend.scale_stage import main

raise SystemExit(main())
```

The supervisor accepts one JSON request file and writes one private result file. Use `subprocess.Popen(argv, shell=False)`, redirect output to workspace files, poll `/proc/<pid>/status` for `VmSwap`, wait once, and read `resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss` in the fresh supervisor. Strip `PYTHONTRACEMALLOC`; reject `-X tracemalloc` in argv. Never store argv/output/paths in public evidence.

- [ ] **Step 5: Run tests/gate and commit**

```bash
uv run pytest tests/test_scale_corpus.py tests/test_scale_stage_runner.py -q
uv run python scripts/check.py
git add src/docmend/scale_corpus.py src/docmend/scale_stage.py \
  scripts/measure_scale_stage.py tests/test_scale_corpus.py tests/test_scale_stage_runner.py
git commit -m "feat(scale): add streamed corpus and RSS supervisor"
```

### Task 6A: Complete the qualification contracts

**Files:**

- Modify: `src/docmend/scale_evidence.py`
- Modify: `src/docmend/schemas/scale-evidence.schema.json`
- Modify: `src/docmend/schemas/scale-thresholds.schema.json`
- Modify: `src/docmend/schemas/README.md`
- Modify: `src/docmend/scale_stage.py`
- Modify: `src/docmend/scale_resources.py`
- Modify: `src/docmend/scale_corpus.py`
- Modify: `src/docmend/frontmatter.py`
- Modify: `tests/test_scale_evidence.py`
- Modify: `tests/test_schemas.py`
- Modify: `tests/test_scale_stage_runner.py`
- Modify: `tests/test_scale_resources.py`
- Modify: `tests/test_scale_corpus.py`

- [ ] **Step 1: Write failing scale-evidence 2.0 partial-truth tests**

Add tests for preflight-null build failure, pre-scan zero totals, scan-only and plan-only prefixes, measured-but-artifact-invalid stages, spawn/reap null exits, conservation-failed evidence, exact artifact-validated stage keys, structured-log accounting, finite outcome reasons, build-version provenance, runtime reconciliation, stage order/uniqueness, and passing/diagnostic full invariants. Pin the intended public shape:

```python
def test_pre_scan_incomplete__records_only_proven_zero_phases() -> None:
    evidence = incomplete_evidence(
        preflight=None,
        outcome_reason="build-failed",
        stages=[],
        totals=zero_totals(expected_findings=25),
    )
    assert evidence.status == "incomplete"
    assert evidence.totals.scanned == 0


def test_measured_invalid_artifact__retains_measurement_without_run_identity() -> None:
    stage = StageEvidence(
        stage="scan",
        run_id=None,
        elapsed_seconds=1.0,
        files_per_second=0.0,
        bytes_per_second=0.0,
        peak_rss_bytes=1024,
        python_allocation_peak_bytes=None,
        vm_swap_peak_bytes=0,
        exit_code=0,
        completed=True,
        artifact_validated=False,
        artifact_bytes={"stdout-log": 0, "stderr-log": 0},
    )
    assert stage.completed is True
    assert stage.artifact_validated is False
```

Add inverse-invariant tests proving `completed=false` rejects any exit/RSS/allocation value, `completed=true` requires an exit plus exactly one memory value, `artifact_validated=false` rejects a public run ID, and `artifact_validated=true` requires the exact stage key set. Add schema/model parity tests proving 1.1 is rejected and the six product versions are derived from code-owner constants rather than repeated literals.

- [ ] **Step 2: Run the evidence tests and confirm RED**

```bash
uv run pytest tests/test_scale_evidence.py tests/test_schemas.py -q
```

Expected: failures for schema 1.1, mandatory preflight/exit, unconditional full-corpus conservation, absent build/runtime/artifact state, and the missing frontmatter constant.

- [ ] **Step 3: Implement scale-evidence 2.0 and current schema provenance**

Use these finite contracts:

```python
SCALE_EVIDENCE_SCHEMA_VERSION = "2.0"
SCALE_THRESHOLDS_SCHEMA_VERSION = "2.0"

type OutcomeReason = Literal[
    "explicit-diagnostic",
    "reference-mismatch",
    "reference-observation-unavailable",
    "provenance-changed",
    "build-failed",
    "install-failed",
    "capacity-insufficient",
    "capacity-estimate-exceeded",
    "corpus-materialization-failed",
    "supervisor-failed",
    "telemetry-unavailable",
    "stage-exit",
    "artifact-invalid",
    "conservation-mismatch",
    "finding-mismatch",
    "threshold-exceeded",
    "runtime-limit-exceeded",
    "harness-error",
]

class WorkflowRuntimeVerdict(_StrictModel):
    elapsed_seconds: Annotated[float, Field(ge=0)]
    limit_seconds: Annotated[int, Field(gt=0)]
    passed: bool

class StageEvidence(_StrictModel):
    stage: StageName
    run_id: RunId | None
    elapsed_seconds: Annotated[float, Field(ge=0)]
    files_per_second: Annotated[float, Field(ge=0)]
    bytes_per_second: Annotated[float, Field(ge=0)]
    peak_rss_bytes: Annotated[int, Field(ge=0)] | None
    python_allocation_peak_bytes: Annotated[int, Field(ge=0)] | None
    vm_swap_peak_bytes: Annotated[int, Field(ge=0)] | None
    exit_code: int | None
    completed: bool
    artifact_validated: bool
    artifact_bytes: dict[ArtifactSizeName, ArtifactSize]
```

Add `structured-log` to `ArtifactSizeName`; add `build_frontend_version` and `build_backend_version` public labels; make `preflight` nullable; add `outcome_reason` and `workflow_runtime: WorkflowRuntimeVerdict | None`. Enforce the state biconditionals: `completed=false` forces null exit/RSS/allocation; `completed=true` requires known exit and exactly one memory measurement; `artifact_validated=false` forces null run ID; `artifact_validated=true` additionally requires completed, trusted run ID, and the exact stage-specific durable/log key set. Stages are an ordered unique prefix. Passing requires all four artifact-validated stages; non-passing evidence obeys phase-zero rules but may preserve a validated artifact's discrepant totals. Passing has no outcome reason; every other status has one.

Only release evidence may carry workflow runtime. A release failure before scan dispatch has null runtime; once dispatch begins it is required even when a later stage stops. Passing/otherwise-complete release evidence requires it, uses a 43,200-second limit, and reconciles `passed == (elapsed <= limit)`. For a complete release, set public elapsed to `max(observed_outer_elapsed, sum(public_stage_elapsed))` and require it to be at least that stage sum, so float serialization cannot understate the workflow.

When multiple conditions coexist, choose status/reason deterministically: any trustworthy stage/conservation/finding/threshold/runtime failure outranks incomplete/diagnostic classification, with primary reason order `stage-exit`, `conservation-mismatch`, `finding-mismatch`, `threshold-exceeded`, `runtime-limit-exceeded`; otherwise use the first lifecycle blocker in execution order, then `reference-mismatch`, then `explicit-diagnostic`. Add pairwise tests for threshold+runtime, reference+threshold, stage-exit+missing-artifact, and multiple lifecycle blockers.

Add `FRONTMATTER_SCHEMA_VERSION = "1.0"` and `current_artifact_schema_versions()` using only `INVENTORY_SCHEMA_VERSION`, `PLAN_SCHEMA_VERSION`, `REPORT_SCHEMA_VERSION`, `MANIFEST_SCHEMA_VERSION`, `VERIFY_REPORT_SCHEMA_VERSION`, and the new frontmatter constant. Update both JSON Schemas and the schema README in the same edit.

- [ ] **Step 4: Run the evidence tests and confirm GREEN**

```bash
uv run pytest tests/test_scale_evidence.py tests/test_schemas.py -q
```

- [ ] **Step 5: Write failing immutable threshold-context and 1M-projection tests**

Cover stage-order mismatch, mutation after context load, mutation before acceptance, 10k diagnostic quality, 100k passing requirement, provenance mismatch, negative stage slope, projected peak dominated by a non-maximum pilot stage, exact boundary/one-unit-over verdicts, scheduled 100k evaluation, release three-point evaluation, upward serialization, and the old 100k-ceiling regression.

```python
def test_threshold_absolute_limit__projects_each_stage_to_one_million() -> None:
    series = (
        StageMemorySeries("scan", rss_10k=100_000_000, rss_100k=550_000_000),
        StageMemorySeries("plan", rss_10k=300_000_000, rss_100k=350_000_000),
        StageMemorySeries("apply", rss_10k=200_000_000, rss_100k=300_000_000),
        StageMemorySeries("verify", rss_10k=150_000_000, rss_100k=250_000_000),
    )
    limits = derive_thresholds(series)
    assert limits.target_file_count == 1_000_000
    assert limits.absolute_peak_rss_bytes == 6_312_500_000
```

The expected value is `ceil(1.25 * (100,000,000 + 5,000 * 990,000))`; it deliberately proves the limit is not `1.25 * 550,000,000`.

- [ ] **Step 6: Implement the frozen threshold context and pure evaluator**

Add:

```python
@dataclass(frozen=True, slots=True)
class StageMemorySeries:
    stage: StageName
    rss_10k: int
    rss_100k: int

@dataclass(frozen=True, slots=True)
class ThresholdContext:
    baseline: ThresholdBaseline
    baseline_sha256: Sha256
    stage_memory: tuple[StageMemorySeries, ...]
```

Add exact APIs `load_threshold_context(path: Path, *, reference_environment_sha256: Sha256) -> ThresholdContext` and `evaluate_thresholds(context: ThresholdContext, *, file_count: Literal[100_000, 1_000_000], stage_peak_rss: Mapping[StageName, int]) -> ThresholdVerdict`. `ThresholdBaseline` requires `target_file_count=1_000_000` and `fitting_method="exact-per-stage-linear-projection"`. The context loader performs the only point reads and derives four stage-aligned pairs from those immutable bytes. For each pair use the OQ-041 `g[s]`/`p[s,n]` formulas with `Fraction`. Derive limits from the largest projected 1M stage and largest non-negative stage slope with 25% upward-rounded headroom. Scheduled observed slope is `max_s max(0, (current100[s] - m10[s]) / 90_000)`; release observed slope is `max_s max(0, ols_s)` over the exact per-stage least-squares slopes for 10k/100k/1M. Maximum relative deviation is rounded upward to 12 decimals only for publication. Preserve compatibility wrappers only when they delegate to the context and cannot discard/re-read point state.

- [ ] **Step 7: Run threshold tests and confirm GREEN**

```bash
uv run pytest tests/test_scale_evidence.py -q
```

- [ ] **Step 8: Write failing transport, observation, budget, and corpus-summary tests**

Add request-writer/result-loader tests for collision, symlink/FIFO, wrong mode, duplicate key, non-finite number, truncated JSON, recursive JSON, and request/result stage/output-name mismatch. Add injected reference-observation tests for ext4/XFS/btrfs SSD, rotational HDD, dm/LVM leaf traversal, partition parent, mixed leaves, missing sysfs, tmpfs/network, RAM/CPU parsing, and public-label sanitization. Add exact shared/distinct-filesystem budget tests at 1, 40, 100,000, and 1,000,000 files, coefficient-overrun behavior, and largest rendered recipe agreement.

```python
def test_stage_result_loader__rejects_duplicate_key(tmp_path: Path) -> None:
    path = private_file(tmp_path, '{"schema":"docmend/scale-stage-result","schema":"x"}')
    with pytest.raises(StageContractError, match="duplicate"):
        load_stage_result(path)


def test_reference_observation__unprovable_rotation_is_unknown(fake_linux: FakeLinux) -> None:
    fake_linux.remove_rotational_file()
    observed = observe_reference_environment(Path("/workspace"), probes=fake_linux.probes)
    assert observed.environment.storage_class == "unknown"
```

- [ ] **Step 9: Implement strict transport and immutable reference snapshots**

Add `write_stage_request(request, path)` and `load_stage_result(path)` in `scale_stage.py`. The writer requires the held real mode-0700 parent and safe basename, writes canonical strict JSON plus newline as a mode-0600 regular file, fsyncs, and publishes no-clobber without pathname cleanup. The loader takes one no-follow regular mode-0600 descriptor snapshot, rejects duplicate keys/non-finite values/invalid Unicode/recursion, and calls `StageResult.from_document`. Keep private wire schema 1.0 because its shape is unchanged.

Add `read_reference_environment_snapshot(path) -> tuple[ReferenceEnvironment, Sha256]`. Add injected `observe_reference_environment(workspace: Path, *, probes: ReferenceProbes) -> ReferenceObservation`, returning the sanitized model, selected mount projection, and fragment size. Follow every sysfs `slaves` edge to leaves; eligible local filesystems are SSD only when every leaf proves rotational `0`, HDD only when every leaf proves `1`, otherwise unknown. Never expose device/sysfs/mount paths.

- [ ] **Step 10: Implement provisional capacity coefficients and independent boundary oracle**

Add `fragment_size` and `largest_file_bytes` to `ScaleCorpusSummary` and compute both in the existing single streaming pass. The fragment field binds its physical-allocation total to the observed corpus destination. Add constants and `qualification_requirements()` in `scale_resources.py`:

```python
QUALIFICATION_BASE_BYTES = 256 * 1024 * 1024
INVENTORY_BYTES_PER_INPUT = 2_048
PLAN_BYTES_PER_INPUT = 4_096
REPORT_BYTES_PER_ACTION = 2_048
MANIFEST_BYTES_PER_ACTION = 8_192
VERIFY_BYTES_PER_INPUT = 1_024
STRUCTURED_LOG_BYTES_PER_INPUT_STAGE = 4_096
SUPERVISOR_PRIVATE_BYTES_PER_FILE = 2 * 1024 * 1024
SUPERVISOR_PRIVATE_FILES_PER_STAGE = 4
QUALIFICATION_NONCORPUS_INODES = 64
```

Add frozen `CapacityPlacement(path: Path, fragment_size: int)`, requiring a positive fragment size and an existing identity-held no-follow probe directory. The absent corpus root uses its held existing parent. Implement `qualification_requirements(*, workspace: CapacityPlacement, corpus: CapacityPlacement, artifact: CapacityPlacement, supervisor: CapacityPlacement, summary: ScaleCorpusSummary) -> tuple[Requirement, ...]`; reject a corpus placement whose fragment differs from `summary.fragment_size`. It emits four placement-aware requirements before grouping:

- corpus: exact corpus allocation/inodes plus the largest writer staging file rounded with `corpus.fragment_size` and one staging inode;
- artifact: inventory, plan, report, manifest, verify-report, four structured logs, and the largest atomic staging artifact, each rounded with `artifact.fragment_size`, plus ten named-file inodes;
- supervisor: request/result/stdout/stderr as four 2 MiB files for each of four stages, each rounded with `supervisor.fragment_size`, plus sixteen inodes; and
- workspace: the 256 MiB base rounded with `workspace.fragment_size` plus 64 additional non-corpus inodes.

Group those existing probe paths by followed `st_dev`, then delegate the single 25% margin to `check_capacity`. Build/venv bytes are not estimated because setup precedes this check. Add exact same-filesystem and four-distinct-filesystem arithmetic tests with different fragment sizes, including per-file rounding when a destination fragment does not divide 2 MiB. Add `expected_boundary_output(recipe)` to the corpus source: derive target path, bytes, hash, and encoding directly from the synthetic recipe/render contract, without calling planning or transform production code.

- [ ] **Step 11: Run focused and full gates**

```bash
uv run pytest tests/test_scale_evidence.py tests/test_schemas.py \
  tests/test_scale_stage_runner.py tests/test_scale_resources.py \
  tests/test_scale_corpus.py -q
uv run python scripts/check.py
git diff --check
```

- [ ] **Step 12: Commit the contract-completion slice**

```bash
git add src/docmend/scale_evidence.py src/docmend/scale_stage.py \
  src/docmend/scale_resources.py src/docmend/scale_corpus.py \
  src/docmend/frontmatter.py src/docmend/schemas \
  tests/test_scale_evidence.py tests/test_schemas.py \
  tests/test_scale_stage_runner.py tests/test_scale_resources.py \
  tests/test_scale_corpus.py
git commit -m "feat(scale): complete qualification contracts"
```

### Task 6B: Build the four-stage installed-wheel orchestrator

**Files:**

- Modify: `pyproject.toml` (`[build-system]` requirement only; no tool-table change)
- Create: `src/docmend/scale_build.py`
- Create: `src/docmend/scale_reconcile.py`
- Create: `src/docmend/scale_qualification.py`
- Create: `scripts/qualify_scale.py`
- Create: `tests/test_scale_build.py`
- Create: `tests/test_scale_reconcile.py`
- Create: `tests/test_scale_qualification.py`
- Create: `docs/scale-evidence/README.md`

- [ ] **Step 1: Write failing parser, workspace, and exact-build tests**

Cover fixed binding counts (pilot/scheduled 100,000; release 1,000,000), diagnostic-only count override, capture-reference exclusivity, threshold requirement, acceptance refusal for diagnostics, unsafe/preexisting/in-checkout workspaces, inside-checkout ordinary evidence output, dirty/unborn/moving HEAD, wrong uv version, archive source identity, multiple/symlink wheels, wheel metadata mismatch, lock export/hash-required install, `pip check`, import-origin escape, and cleanliness rechecks.

```python
def test_binding_count__cannot_be_overridden() -> None:
    with pytest.raises(QualificationInputError, match="binding tier count is fixed"):
        parse_args(["--tier", "release", "--count", "999"])


def test_prepare_candidate__builds_archived_head_not_worktree(
    fake_commands: FakeCommands, request: BuildRequest, source: SourceProvenance
) -> None:
    candidate = prepare_candidate(request, source=source, commands=fake_commands)
    assert candidate.commit == "a" * 40
    assert fake_commands.build_source == candidate.source_snapshot
    assert candidate.source_snapshot != request.repository
```

- [ ] **Step 2: Run build/parser tests and confirm RED**

```bash
uv run pytest tests/test_scale_build.py tests/test_scale_qualification.py -q
```

- [ ] **Step 3: Implement absent workspace and exact fixed-backend candidate build**

Change only:

```toml
[build-system]
requires = ["uv_build==0.11.6"]
build-backend = "uv_build"
```

In `scale_build.py` define `QUALIFICATION_UV_VERSION = "0.11.6"`, frozen `SourceProvenance`/`BuildRequest`/`CandidateBuild` models, `inspect_candidate_source()`, and `prepare_candidate()`. `inspect_candidate_source()` is read-only: require the exact uv version, capture `HEAD^{commit}` plus porcelain-v2 tracked/untracked cleanliness, read committed `pyproject.toml`/`uv.lock` through Git object access, and return commit, package/backend versions, and exact hashes. This is the pre-run provenance boundary. `prepare_candidate()` then requires an absent workspace outside the repository, creates it mode 0700 with retained/reconciled identity, archives exactly the inspected commit, safely extracts with the stdlib data filter, and verifies archived `pyproject.toml`/`uv.lock` against the inspected Git-object bytes. Run, without shell or discovered config:

```text
uv --no-config build --wheel --no-sources --force-pep517 --out-dir WHEEL_DIR SOURCE
uv --no-config venv --no-project --python EXACT_PYTHON --no-python-downloads VENV
uv --no-config export --project SOURCE --locked --no-dev --no-emit-project --no-sources --format requirements.txt --output-file RUNTIME
uv --no-config pip install --python VENV_PYTHON --require-hashes --no-deps --only-binary :all: -r RUNTIME
uv --no-config pip install --python VENV_PYTHON --no-index --no-deps WHEEL
uv --no-config pip check --python VENV_PYTHON
```

Require one regular non-symlink wheel in a new directory; hash exact bytes; validate wheel `METADATA` name/version; and run `VENV_PYTHON -I` from outside the repo/snapshot to prove `docmend` and all scale modules resolve beneath the venv. Record exact frontend/backend versions. Recheck commit and cleanliness after archive, build, install, qualification, and before acceptance. Preserve workspace residue; never clear or reuse it.

- [ ] **Step 4: Run build/parser tests and confirm GREEN**

```bash
uv run pytest tests/test_scale_build.py tests/test_scale_qualification.py -q
```

- [ ] **Step 5: Write failing complete-reconciliation tests**

Create strict valid artifacts from a small synthetic corpus, then mutate one invariant at a time: inventory count/path/size/hash/encoding/newline, plan inventory hash and disposition partition, duplicate path/action ID, report plan binding/outcome set/totals, manifest header/run/plan/report binding and exact `1 + 2 * actions` intent→applied lifecycle, verify checked count/coverage/finding multiset, and every boundary recipe's final target/bytes/hash/encoding. Prove findings use `Counter[(path, check)]`, not a set.

```python
def test_verify_findings__duplicate_is_not_collapsed(valid_pipeline: PipelinePaths) -> None:
    add_duplicate_expected_finding(valid_pipeline.verify_report)
    with pytest.raises(QualificationFailure, match="finding multiset"):
        reconcile_pipeline(valid_pipeline, count=40)
```

- [ ] **Step 6: Implement `scale_reconcile.py`**

Use the existing strict readers and lifecycle/coverage reducers: `read_inventory`, `read_plan_snapshot`, `read_report_snapshot`, `read_verify_report`, `read_manifest_chain`, `reduce_lifecycle`, `load_verification_evidence`, and `check_plan_coverage`. Derive the manifest only after strict report loading as `PIPELINE/.docmend/docmend-{validated_run_id}-manifest.jsonl`; derive each stage's structured log only from that stage's trusted artifact run ID as `PIPELINE/.docmend/docmend-{validated_run_id}.jsonl`; never glob or parse stdout. Reconcile every recipe/artifact record and the independent boundary oracle. Return one frozen `PipelineReconciliation` containing phase totals, per-stage trusted run IDs, exact artifact sizes, expected/observed finding Counters, and the manifest path. Distinguish an unreadable/missing artifact (`QualificationIncomplete`) from a valid artifact whose facts disagree (`QualificationFailure`).

- [ ] **Step 7: Run reconciliation tests and confirm GREEN**

```bash
uv run pytest tests/test_scale_reconcile.py -q
```

- [ ] **Step 8: Write failing fresh-supervisor orchestration/status tests**

Cover four exact commands, one fresh supervisor process per stage, absolute candidate executable, isolated candidate Python wrapper, private environment roots, strict request/result round-trip, wrapper/result mismatch, stage-specific expected exits, immediate downstream stop, partial evidence at build/materialization/supervisor/artifact failures, reference mismatch continuation, unavailable/nonzero swap, coefficient overrun, threshold/runtime failures, and exact status precedence.

```python
def test_stage_failure__stops_pipeline(fake_services: FakeServices) -> None:
    fake_services.fail_artifact_on("plan")
    outcome = qualify(fake_request(), services=fake_services)
    assert [stage.stage for stage in outcome.evidence.stages] == ["scan", "plan"]
    assert outcome.evidence.status == "incomplete"
    assert outcome.evidence.outcome_reason == "artifact-invalid"


def test_reference_mismatch_binding_request__diagnostic_but_nonzero(
    fake_services: FakeServices,
) -> None:
    fake_services.reference_matches = False
    outcome = qualify(fake_request(diagnostic=False), services=fake_services)
    assert outcome.evidence.status == "diagnostic"
    assert outcome.exit_code == 1
```

- [ ] **Step 9: Implement the four-stage orchestrator**

Keep `scripts/qualify_scale.py` as:

```python
from docmend.scale_qualification import main

raise SystemExit(main())
```

Support the approved flags exactly. `--workspace` names one absent external root. `--thresholds` is required for scheduled/release. `--count` is legal only with `--diagnostic`. `--evidence-out` is required, no-clobber, and outside the checkout for qualification. `--accept-to` is an existing directory and is illegal for diagnostics. `--capture-reference` requires `--workspace` and `--output` and is exclusive of qualification arguments.

First perform every no-evidence refusal: parse/validate flags and destinations, require an outside-checkout absent workspace/evidence path, call `inspect_candidate_source()`, load the immutable reference and applicable threshold context, and precheck the deterministic acceptance target. Once commit/package/build/lock/reference provenance is fixed, start the evidence lifecycle and call `prepare_candidate()`; archive/build/install failures from this point publish incomplete evidence with a null wheel hash where necessary. After candidate setup, run capacity preflight before materialization and require materialization to equal its summary. Classify the newly written corpus `warm`. For each stage, write a strict request and launch a new process:

```text
VENV_PYTHON -I SOURCE/scripts/measure_scale_stage.py REQUEST RESULT
```

The request uses `cwd=PIPELINE`, absolute venv `docmend`, private `HOME`/`XDG_STATE_HOME`/`XDG_CONFIG_HOME`/`TMPDIR`, `LANG=C.UTF-8`, `LC_ALL=C.UTF-8`, `TZ=UTC`, and the Task 5 fixed environment. Commands are exactly:

```text
docmend scan CORPUS --report INVENTORY
docmend plan --inventory INVENTORY --out PLAN
docmend apply PLAN --write --preserved-by external --report REPORT
docmend verify CORPUS --plan PLAN --manifest MANIFEST --report REPORT --out VERIFY_REPORT
```

Require wrapper exit 0 before trusting the strict result; reconcile result stage/stdout/stderr to its request. Scan/plan/apply require child exit 0. Verify requires 0 when no expected findings and 1 only when the exact nonempty expected multiset is published. For release only, start monotonic workflow timing immediately before scan supervisor dispatch and stop after the last validated attempted result; publish `max(observed_outer_elapsed, sum(public_stage_elapsed))`. Scheduled/release load one immutable threshold context; release adds the exact 43,200-second verdict. Stop downstream immediately at the first failed boundary and construct the phase-truthful evidence prefix using the fixed status/reason precedence from Task 6A.

- [ ] **Step 10: Write failing publication, acceptance, and CLI-exit tests**

Test every pre-run exit-2 refusal with no evidence, post-provenance incomplete/failed exit 1 with evidence, passing/explicit diagnostic exit 0, reference-mismatched binding exit 1 diagnostic, evidence destination collision, acceptance directory/file confusion, deterministic full-commit name for every tier, accepted byte identity, prior acceptance preservation, publication race, and capture-reference no-clobber output.

- [ ] **Step 11: Implement evidence-first no-clobber publication**

Publish canonical validated bytes to `--evidence-out` first. Only `passing` binding evidence may then publish identical bytes to:

```text
{candidate_commit}-pilot-100000.json
{candidate_commit}-scheduled-100000.json
{candidate_commit}-release-1000000.json
{candidate_commit}-file-size.json
```

Never overwrite either path. A race at acceptance preserves ordinary evidence and returns 1. Input/provenance/output refusal before candidate/reference/lock identity returns 2 without evidence. Passing, reference capture, and an otherwise-correct explicit diagnostic return 0. Failed/incomplete evidence returns 1; an otherwise-correct reference-mismatched binding request is diagnostic evidence but returns 1.

- [ ] **Step 12: Document the evidence boundary and run focused validation**

Document workspace privacy/retention, evidence statuses/reasons, thresholds, reference capture, diagnostic vs binding behavior, exact accepted directories/names, sanitization, review, no-overwrite, and validation in `docs/scale-evidence/README.md`. Run:

```bash
uv run pytest tests/test_scale_build.py tests/test_scale_reconcile.py \
  tests/test_scale_qualification.py -q
python /home/chris/.agents/skills/technical-writer/scripts/docctl.py validate \
  docs/scale-evidence/README.md
npx --yes prettier@3.6.2 --check docs/scale-evidence/README.md
npx --yes markdownlint-cli2@0.18.1 docs/scale-evidence/README.md
```

- [ ] **Step 13: Run the full gate and commit the orchestrator**

```bash
uv run python scripts/check.py
git diff --check
git add pyproject.toml src/docmend/scale_build.py src/docmend/scale_reconcile.py \
  src/docmend/scale_qualification.py scripts/qualify_scale.py \
  tests/test_scale_build.py tests/test_scale_reconcile.py \
  tests/test_scale_qualification.py docs/scale-evidence/README.md
git commit -m "feat(scale): orchestrate installed-wheel qualification"
```

- [ ] **Step 14: Run a real clean-HEAD installed-wheel diagnostic**

After the commit makes the tree clean, use one temporary parent and two absent workspace children:

```bash
tmp="$(mktemp -d)"
uv run python scripts/qualify_scale.py --capture-reference \
  --workspace "$tmp/reference-workspace" --output "$tmp/reference.json"
uv run python scripts/qualify_scale.py --tier pilot --diagnostic --count 40 \
  --workspace "$tmp/qualification-workspace" \
  --reference-environment "$tmp/reference.json" \
  --evidence-out "$tmp/diagnostic.json"
```

Expected: both commands exit 0; the second builds/installs the committed wheel, runs four fresh supervisors, publishes status `diagnostic`, and passes exact correctness without accepting evidence. If this exposes a defect, add the smallest failing regression first, fix it, rerun the focused/full gates and diagnostic, and commit the follow-up before Task 7.

### Task 7: Replace the old scale test with the 1,000-file PR guard

**Files:**

- Modify: `tests/test_scale.py`
- Modify: `pyproject.toml` only through the adopted-standard workflow if marker removal is required
- Test: `tests/test_scale.py`

- [ ] **Step 1: Rewrite the test as a failing full-pipeline contract**

Remove `DOCMEND_SCALE`, `DOCMEND_SCALE_COUNT`, `@pytest.mark.slow`, tracemalloc, and `_spot_verify`. Fix the count at 1,000 and use the streaming helper. Run the source-tree CLI through `CliRunner`:

```python
def test_pr_scale__full_pipeline_and_exact_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    materialize_scale_corpus(corpus, 1_000)
    inventory = tmp_path / "inventory.json"
    plan = tmp_path / "plan.json"
    report = tmp_path / "report.json"
    verify_report = tmp_path / "verify-report.json"

    assert runner.invoke(app, ["scan", str(corpus), "--report", str(inventory)]).exit_code == 0
    assert runner.invoke(app, ["plan", "--inventory", str(inventory), "--out", str(plan)]).exit_code == 0
    applied = runner.invoke(app, ["apply", str(plan), "--write", "--preserved-by", "external", "--report", str(report)])
    assert applied.exit_code == 0
    report_model = read_report(report)
    manifest = tmp_path / ".docmend" / f"docmend-{report_model.run_id}-manifest.jsonl"
    verified = runner.invoke(app, ["verify", str(corpus), "--plan", str(plan), "--manifest", str(manifest), "--report", str(report), "--out", str(verify_report)])
    assert verified.exit_code == 1
    verify_model = read_verify_report(verify_report)
    assert verify_model.clean is False
    assert verification_finding_keys(verify_model) == expected_finding_keys(1_000)
```

Add exact conservation and deterministic per-recipe-class boundary assertions. `expected_finding_keys` derives the full finding multiset from the corpus recipe source of truth; for the retained 40-bucket mix, the only findings are the encoding findings for intentionally unmodified below-floor skips. Do not hardcode a finding count separately from that recipe.

- [ ] **Step 2: Run the test and make path/run-ID handling GREEN**

```bash
uv run pytest tests/test_scale.py -vv -s
```

Expected: one passing test without environment flags, under a practical PR budget.

- [ ] **Step 3: Run full gate and commit**

If the `slow` marker becomes unused, update its standard-owned pyproject source through the project-standards workflow; do not hand-edit a governed table merely to silence a warning.

```bash
uv run python scripts/check.py
git add tests/test_scale.py
git commit -m "test(scale): gate the full 1k pipeline"
```

### Task 8: Add aggregate heartbeat and filesystem-aware write preflight

**Files:**

- Modify: `src/docmend/observability.py`
- Modify: `src/docmend/discovery.py`
- Modify: `src/docmend/planning.py`
- Modify: `src/docmend/writer/apply.py`
- Modify: `src/docmend/verify.py`
- Modify: `src/docmend/verify_coverage.py`
- Modify: `src/docmend/cli.py`
- Modify: `src/docmend/writer/gate.py`
- Test: `tests/test_observability.py`
- Test: `tests/test_gate.py`
- Test: relevant CLI tests

- [ ] **Step 1: Write failing heartbeat tests with a fake clock**

Define `ProgressHeartbeat` with `start`, `advance`, `finish`, and `incomplete`. Test aggregate-only fields, 30-second target, between-record behavior, and no hard guarantee during a native stall.

```python
def test_heartbeat__emits_after_target_interval(fake_clock: FakeClock) -> None:
    emitted: list[dict[str, object]] = []
    heartbeat = ProgressHeartbeat(stage="scan", emit=emitted.append, clock=fake_clock)
    heartbeat.start(total=100)
    fake_clock.advance(31)
    heartbeat.advance(processed=5, skipped=1, failed=0)
    assert emitted[-1]["event"] == "stage.heartbeat"
    assert "path" not in emitted[-1]
```

- [ ] **Step 2: Write failing shared-filesystem preflight tests**

Replace independent backup/source checks with a requirement list grouped by `st_dev`; include backup bytes, largest staging file, manifest/report/verify/log allowance, and shared-mount summation. Keep existing refusal ordering stable.

- [ ] **Step 3: Run focused tests and confirm RED**

```bash
uv run pytest tests/test_observability.py tests/test_gate.py tests/test_cli_scan.py tests/test_cli_plan.py tests/test_cli_apply.py tests/test_cli_verify.py -q
```

- [ ] **Step 4: Implement heartbeat and stage integration**

Use injected monotonic clock and logger callbacks; emit `stage.start`, best-effort `stage.heartbeat`, `stage.complete`, and `stage.incomplete`. Call `advance` only at deterministic per-record boundaries in discovery, planning, apply, `verify.py` content/lifecycle checks, and `verify_coverage.py` plan reduction. Never emit document content; retain the documented silence interpretation.

- [ ] **Step 5: Implement filesystem-aware preflight**

Factor gate requirements into `scale_resources.group_capacity_by_filesystem`; use actual `st_dev`, available blocks/inodes, and conservative compiled coefficients before the pilot. After revision two, update those coefficients in code and tests from the accepted pilot in the same commit; installed docmend never reads repository evidence files dynamically. Do not double count destinations on one mount.

- [ ] **Step 6: Run focused/full gates and commit**

```bash
uv run pytest tests/test_observability.py tests/test_gate.py tests/test_cli_scan.py tests/test_cli_plan.py tests/test_cli_apply.py tests/test_cli_verify.py -q
uv run python scripts/check.py
git add src/docmend/observability.py src/docmend/discovery.py src/docmend/planning.py \
  src/docmend/writer/apply.py src/docmend/verify.py src/docmend/verify_coverage.py \
  src/docmend/cli.py src/docmend/writer/gate.py \
  tests/test_observability.py tests/test_gate.py tests/test_cli_*.py
git commit -m "feat(scale): report liveness and shared capacity"
```

### Task 9: Capture the reference environment and run the 10k/100k pilot

**Files:**

- Create: `docs/scale-evidence/reference-environment.json`
- Create: `docs/scale-evidence/supporting/<candidate>-pilot-10000.json`
- Create: `docs/scale-evidence/accepted/<candidate>-pilot-100000.json`
- Create: `docs/scale-evidence/thresholds.json`
- Modify: `docs/scale-evidence/README.md`
- Modify: `docs/specs/docmend.md` (revision two)
- Modify: `docs/STATUS.md`, `docs/TODO.md`

- [ ] **Step 1: Capture and commit a sanitized reference candidate**

```bash
uv run python scripts/qualify_scale.py --capture-reference \
  --workspace /var/tmp/docmend-scale-reference \
  --output /var/tmp/docmend-reference-environment.json
```

Review the JSON for forbidden identity/path fields, validate it, then copy it to `docs/scale-evidence/reference-environment.json` with `apply_patch`. Validate and commit this public-safe reference before any clean-tree binding run:

```bash
git add docs/scale-evidence/reference-environment.json
git commit -m "docs(scale): record reference environment"
```

- [ ] **Step 2: Run the uninstrumented 10k diagnostic**

```bash
uv run python scripts/qualify_scale.py --tier pilot --diagnostic --count 10000 \
  --workspace /var/tmp/docmend-scale-10k \
  --reference-environment docs/scale-evidence/reference-environment.json \
  --evidence-out /var/tmp/docmend-scale-10k-evidence.json
```

Expected: all four stages complete; binding children have no allocation tracing; evidence is diagnostic and stays outside the accepted directory.

- [ ] **Step 3: Run and explicitly accept the 100k pilot**

```bash
mkdir -p docs/scale-evidence/accepted
uv run python scripts/qualify_scale.py --tier pilot \
  --workspace /var/tmp/docmend-scale-100k \
  --reference-environment docs/scale-evidence/reference-environment.json \
  --evidence-out /var/tmp/docmend-scale-100k-evidence.json \
  --accept-to docs/scale-evidence/accepted/
```

Expected: exact artifact conservation, complete `verify --plan` coverage, the exact recipe-derived finding multiset with no unexpected findings, zero child swap, reference match, and a new no-clobber accepted pilot document.

- [ ] **Step 4: Derive and freeze thresholds in SPEC revision two**

Validate and copy the sanitized 10k diagnostic into `docs/scale-evidence/supporting/`; it is supporting fit evidence, not an accepted baseline. Use `derive_thresholds` on the immutable per-stage context from that committed 10k point and the accepted 100k point. Write `docs/scale-evidence/thresholds.json` with both relative evidence identities and SHA-256 hashes, the shared reference-environment hash, target count 1,000,000, exact per-stage projection method, 25%-headroom projected-peak and maximum-slope limits, and linearity tolerance. Load the new baseline through the production validator and reproduce the verdict before revising SPEC. Record the same values, evidence links, and swap rule in revision two. Keep NFR-001 Partial.

- [ ] **Step 5: Validate and commit evidence plus revision two**

```bash
uv run python scripts/fix_spec_toc.py
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec validate --config .project-standards.yml
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec lint --strict --config .project-standards.yml
uv run python scripts/check_traceability.py
npx --yes prettier@3.6.2 --check docs/specs/docmend.md docs/scale-evidence
npx --yes markdownlint-cli2@0.18.1 docs/specs/docmend.md docs/scale-evidence/README.md
git diff --check
git add docs/specs/docmend.md docs/scale-evidence docs/STATUS.md docs/TODO.md
git commit -m "docs(scale): freeze pilot-derived resource thresholds"
```

### Task 10: Add the scheduled/manual 100k diagnostic workflow

**Files:**

- Create: `.github/workflows/scale-qualification.yml`
- Modify: `docs/handoff/deployed.md`
- Test: workflow text assertions in a new focused test if repository convention requires them

- [ ] **Step 1: Add a least-privilege repo-owned workflow**

Create a weekly plus manual workflow using `ubuntu-latest` as a **diagnostic** environment unless it matches the accepted reference file. Do not let it overwrite accepted baselines or edit standard-owned workflows.

```yaml
name: Scale qualification

on:
  workflow_dispatch:
  schedule:
    - cron: '0 6 * * 1'

permissions:
  contents: read

concurrency:
  group: scale-qualification
  cancel-in-progress: false
```

Reuse the repository's current checkout/setup-uv conventions, pin uv to the check workflow's reviewed version, validate `docs/scale-evidence/thresholds.json`, run the self-building scheduled tier explicitly as `--diagnostic --count 100000` in `$RUNNER_TEMP` with threshold and evidence paths, and upload that diagnostic evidence plus private logs with limited retention. Accepted evidence remains a reviewed commit.

- [ ] **Step 2: Validate workflow and run locally equivalent command**

```bash
npx --yes prettier@3.6.2 --check .github/workflows/scale-qualification.yml
uv run python scripts/qualify_scale.py --tier scheduled --diagnostic --count 100000 \
  --workspace /var/tmp/docmend-scale-scheduled \
  --reference-environment docs/scale-evidence/reference-environment.json \
  --thresholds docs/scale-evidence/thresholds.json \
  --evidence-out /var/tmp/docmend-scale-scheduled-evidence.json
```

Expected: the local and hosted commands complete as status `diagnostic`, evaluate the threshold context, and never replace binding evidence.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/scale-qualification.yml docs/handoff/deployed.md
git commit -m "ci(scale): schedule 100k qualification"
```

### Task 11: Qualify the file-size envelope and the full one-million-file candidate

**Files:**

- Modify: `src/docmend/scale_evidence.py`
- Modify: `src/docmend/scale_qualification.py`
- Create: `tests/test_scale_file_size.py`
- Create: `docs/scale-evidence/accepted/<candidate>-file-size.json`
- Create: `docs/scale-evidence/accepted/<candidate>-release-1000000.json`
- Modify: `docs/specs/docmend.md`
- Modify: `README.md`
- Modify: `docs/STATUS.md`, `docs/TODO.md`

- [ ] **Step 1: Write failing file-size matrix tests**

Define the cases from the configured maximum rather than duplicating `100`: small control, 25%, 50%, 75%, and 100% of `limits.max_file_size_mib`, for UTF-8 and the supported legacy encoding. Cover external preservation and a bounded tool-backup subset. Every case runs planning, apply, and verification in fresh measured children and records per-stage RSS, elapsed time, timeout outcome, backup bytes, and finding/coverage reconciliation.

```python
def test_file_size_matrix__derives_boundaries_from_config() -> None:
    cases = file_size_cases(DocmendConfig().limits.max_file_size_mib)
    assert max(case.size_mib for case in cases) == DocmendConfig().limits.max_file_size_mib
    assert {case.encoding for case in cases} == {"utf-8", "windows-1252"}


def test_file_size_tier__requires_exact_head_build(fake_builder: FakeBuilder) -> None:
    evidence = qualify_file_sizes(fake_request(), builder=fake_builder)
    assert fake_builder.built_commit == evidence.candidate_commit
    assert all(case.peak_rss_bytes < 2 * 1024**3 for case in evidence.file_size_cases)
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
uv run pytest tests/test_scale_file_size.py -q
```

- [ ] **Step 3: Implement and commit the file-size lane**

Add `--tier file-size` to the self-building orchestrator, strict `FileSizeCaseEvidence` schema/model coverage, matrix generation, fresh-child stage measurement, tool-backup accounting, the 2 GiB per-case RSS verdict, and watchdog-result capture. Require an accepted reference match and `--accept-to` for binding publication; use `--evidence-out` for diagnostics. Keep file bodies and paths out of public evidence.

```bash
uv run pytest tests/test_scale_file_size.py tests/test_scale_evidence.py tests/test_scale_qualification.py -q
uv run python scripts/check.py
git add src/docmend/scale_evidence.py src/docmend/scale_qualification.py \
  tests/test_scale_file_size.py
git commit -m "feat(scale): qualify the file-size envelope"
```

- [ ] **Step 4: Run the file-size matrix**

```bash
uv run python scripts/qualify_scale.py --tier file-size \
  --workspace /var/tmp/docmend-scale-file-size \
  --reference-environment docs/scale-evidence/reference-environment.json \
  --evidence-out /var/tmp/docmend-scale-file-size-evidence.json \
  --accept-to docs/scale-evidence/accepted/
```

Expected: representative UTF-8/legacy files through 100 MiB remain below the 2 GiB per-file RSS and watchdog envelope. If not, use the largest measured passing size as the derived default and update config/spec/README/tests through a separate TDD commit; never raise the limit from this evidence.

- [ ] **Step 5: Validate and commit the file-size settlement**

If Step 4 fails the envelope, implement the derived lower default with focused tests and a separate config/spec/README commit, then rerun Step 4 from that clean `HEAD`; failed evidence remains only at `--evidence-out`. Once the lane passes, run the evidence/schema/spec/full gates and commit the accepted file-size evidence plus its synchronized documentation. The next binding run must start from this clean committed state.

- [ ] **Step 6: Build from clean HEAD and run the full 1M qualification**

```bash
uv run python scripts/qualify_scale.py --tier release \
  --workspace /var/tmp/docmend-scale-1000000 \
  --reference-environment docs/scale-evidence/reference-environment.json \
  --thresholds docs/scale-evidence/thresholds.json \
  --evidence-out /var/tmp/docmend-scale-1000000-evidence.json \
  --accept-to docs/scale-evidence/accepted/
```

Expected: completion within 12 hours, exact conservation, complete plan-aware coverage, the exact recipe-derived finding multiset with no unexpected findings, zero child swap, measured RSS/slope/linearity within revision-two thresholds, and no-clobber accepted evidence bound to the tested commit and wheel.

- [ ] **Step 7: Promote NFR-001 only from evidence**

Set NFR-001 Complete in §17.3 only after both accepted evidence documents validate and bind their tested clean commits and self-built wheel hashes. Add the exact commands and evidence links; synchronize README's supported scale and sequential migration guidance. Do not claim that the later evidence-only commit has the same hash as the tested commit; DMR-09 owns release-publication binding to the qualified code and artifact.

- [ ] **Step 8: Run the full gates and commit qualification evidence**

```bash
uv run python scripts/check.py
uv run python scripts/fix_spec_toc.py
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec validate --config .project-standards.yml
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec lint --strict --config .project-standards.yml
uv run python scripts/check_traceability.py
npx --yes prettier@3.6.2 --check .
npx --yes markdownlint-cli2@0.18.1 "**/*.md"
git diff --check
git add docs/scale-evidence docs/specs/docmend.md README.md docs/STATUS.md docs/TODO.md
git commit -m "test(scale): qualify million-file release contract"
```

### Task 12: Close DMR-08 and synchronize durable documentation

**Files:**

- Modify: `docs/codex-reviews/2026-07-10-2251-all-findings-verification.md` or add a post-Plan-D/DMR-08 disposition artifact
- Modify: `docs/handoff/architecture.md`
- Modify: `docs/handoff/deployed.md`
- Modify: `docs/handoff/specs-plans.md`
- Modify: `docs/handoff/state.md`
- Modify: `docs/handoff/sessions/2026-07.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/TODO.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Record evidence-backed closure**

Mark only DMR-08 and its verified child findings closed. Record the accepted 100k pilot, file-size, and 1M evidence paths, plan 2.0/config migration, heartbeat/capacity changes, and remaining DMR-09/sub-project-4 work. Do not repeat the obsolete “179 open after Plan A” tally as current truth.

- [ ] **Step 2: Route current and durable facts**

Keep STATUS current, TODO future-facing, state limited to the immediate DMR-09 next step, architecture structural, deployed workflow-focused, and the session log historical. Preserve the user task section.

- [ ] **Step 3: Run final verification**

```bash
uv run python scripts/check.py
uv run python scripts/fix_spec_toc.py
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec validate --config .project-standards.yml
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec lint --strict --config .project-standards.yml
uv run python scripts/check_traceability.py
npx --yes prettier@3.6.2 --check .
npx --yes markdownlint-cli2@0.18.1 "**/*.md"
python /home/chris/.agents/skills/technical-writer/scripts/docctl.py validate README.md CHANGELOG.md docs/STATUS.md docs/TODO.md docs/handoff docs/scale-evidence
git diff --check
git status --short
```

Expected: all gates pass, DMR-08 is closed with accepted evidence, DMR-09 remains the next release blocker, and no private paths/content appear in committed evidence.

- [ ] **Step 4: Commit closeout**

```bash
git add CHANGELOG.md README.md docs/STATUS.md docs/TODO.md \
  docs/codex-reviews docs/handoff docs/specs/docmend.md docs/scale-evidence
git commit -m "docs(handoff): close million-file scale remediation"
```

## Plan Self-Review Checklist

- [ ] Every DMR-08 finding maps to a task: contract/config, plan artifact, cardinality, file-size, qualification ownership, watchdog honesty, liveness, and capacity.
- [ ] The default/no-config path is tested before `parallel.*` removal ships.
- [ ] Plan 1.x is rejected before gate/lock/mutation; plan 2.0 contains no inert config.
- [ ] Binding RSS never shares a run with tracemalloc.
- [ ] The harness builds exactly one wheel from verified-clean `HEAD`; evidence binds both commit and wheel hash.
- [ ] PR is source-tree; 100k/1M are installed-wheel subprocess qualifications.
- [ ] The 100k pilot precedes numeric threshold freeze; 1M validates rather than defines thresholds.
- [ ] Accepted evidence is sanitized, explicit, and no-clobber.
- [ ] The 1M corpus recipe stream never materializes one million Python objects.
- [ ] Verify exit 1 is accepted only for the exact recipe-derived finding multiset; all other stage exits and finding mismatches fail.
- [ ] Standard-owned files are not hand-edited; additive workflow ownership is explicit.
- [ ] NFR-001 is not marked Complete before accepted 1M and file-size evidence exists.
