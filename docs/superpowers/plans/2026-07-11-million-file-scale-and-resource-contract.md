# Million-File Scale and Resource Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close DMR-08 for docmend v2.0.0 with an honest bounded-linear resource contract, sequential-only configuration, plan schema 2.0, tiered scale qualification, pilot-derived RSS thresholds, and accepted one-million-file evidence.

**Architecture:** Preserve the existing whole-run inventory/plan/report model while measuring each installed-CLI stage in a separate uninstrumented subprocess. A repo-only qualification orchestrator produces strict, sanitized evidence; a fresh single-child supervisor owns each stage's external RSS measurement; source-tree pytest covers the 1,000-file PR guard, while built-wheel qualification owns the 100,000- and 1,000,000-file tiers. Change control lands before code, and a second spec revision freezes numeric thresholds only after the real 100,000-file pilot.

**Tech Stack:** Python 3.14, uv, Pydantic v2, JSON Schema Draft 2020-12, Typer, pytest, Ruff, BasedPyright strict, GitHub Actions, POSIX `/proc` and `resource` APIs.

---

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
| `src/docmend/schemas/scale-evidence.schema.json`, `reference-environment.schema.json`, `scale-thresholds.schema.json` | Public qualification contracts, separate from product `ArtifactKind`. |
| `src/docmend/scale_corpus.py` | Streaming deterministic million-file recipe source, expected findings, and exact budget summary. |
| `scripts/measure_scale_stage.py` | One-child supervisor for external RSS and private output capture. |
| `scripts/qualify_scale.py` | Repo-only four-stage qualification orchestrator. |
| `tests/test_scale*.py`, `tests/test_config.py`, `tests/test_plan_artifact.py`, `tests/test_cli_*.py`, `tests/unit/writer/test_commit.py` | TDD coverage for every new contract. |
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

### Task 6: Build the four-stage qualification orchestrator

**Files:**

- Create: `scripts/qualify_scale.py`
- Create: `src/docmend/scale_qualification.py`
- Create: `tests/test_scale_qualification.py`
- Create: `docs/scale-evidence/README.md`

- [ ] **Step 1: Write failing orchestration tests**

Use fake builders/executables/readers to cover fixed binding counts, dirty-tree refusal, exact-HEAD wheel build and hash capture, reference mismatch, required threshold-baseline loading for scheduled/release, four-stage command order, implicit manifest derivation from report run ID, stage-specific exit semantics, downstream stop on failure, incomplete evidence retention, explicit diagnostic output, acceptance as explicit no-clobber action, and artifact/totals reconciliation.

```python
def test_binding_count__cannot_be_overridden() -> None:
    with pytest.raises(QualificationInputError, match="binding tier count is fixed"):
        parse_args(["--tier", "release", "--count", "999"])


def test_stage_failure__stops_pipeline(fake_runner: FakeRunner) -> None:
    fake_runner.fail_on("plan")
    evidence = qualify(fake_request(), runner=fake_runner)
    assert [stage.stage for stage in evidence.stages] == ["scan", "plan"]
    assert evidence.status == "incomplete"
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
uv run pytest tests/test_scale_qualification.py -q
```

- [ ] **Step 3: Implement exact CLI and stage commands**

Implement orchestration and argument parsing in `src/docmend/scale_qualification.py`; keep `scripts/qualify_scale.py` as the same three-line `main` wrapper pattern used by the stage supervisor. Support:

```text
--tier pilot|scheduled|release
--diagnostic
--count N                 # diagnostic only
--workspace PATH          # must be disk-backed and preflighted
--reference-environment PATH
--thresholds PATH         # required for scheduled/release
--evidence-out PATH       # required no-clobber result for every qualification run
--accept-to PATH          # passing binding evidence only, explicit no-clobber
--capture-reference       # write a sanitized candidate environment and exit
--output PATH             # required with --capture-reference
```

Require a clean worktree, capture `HEAD`, build the wheel into a new workspace subdirectory, require exactly one wheel, hash it, and install it into an isolated workspace venv. Never accept an externally supplied wheel whose provenance cannot be tied to the captured commit. Execute:

```text
docmend scan CORPUS --report INVENTORY
docmend plan --inventory INVENTORY --out PLAN
docmend apply PLAN --write --preserved-by external --report REPORT
docmend verify CORPUS --plan PLAN --manifest MANIFEST --report REPORT --out VERIFY_REPORT
```

Derive `MANIFEST` from the validated report run ID under the stage working directory's `.docmend/`. Bind clean worktree, `HEAD`, wheel hash/version, lock hash, schema versions, and reference class. The PR tier is not routed through this installed-wheel path. `--evidence-out` is required and no-clobber for every run so passing, diagnostic, failed, and incomplete evidence has a deterministic operator/workflow path; `--accept-to` additionally publishes a passing binding document under the accepted naming contract.

- [ ] **Step 4: Reconcile all artifacts, not samples**

Require inventory conservation, plan action/skip/no-op conservation, report coverage, manifest line count/lifecycle validity, exact recipe-derived verification findings with no unexpected findings, complete plan coverage, exact candidate identity, and all thresholds appropriate to the tier. Scan, plan, and apply require exit 0. Verify exit 0 is accepted only with no expected findings; verify exit 1 is a completed passing stage only after its published finding multiset equals the recipe-derived expectation exactly. Any other exit or finding mismatch is failed/incomplete as appropriate. Keep private stage output/logs under workspace only.

- [ ] **Step 5: Document evidence acceptance and validate**

Document `docs/scale-evidence/accepted/`, diagnostic storage, sanitization, non-overwrite, review, and validation. Run:

```bash
uv run pytest tests/test_scale_qualification.py -q
uv run python scripts/check.py
python /home/chris/.agents/skills/technical-writer/scripts/docctl.py validate docs/scale-evidence/README.md
```

- [ ] **Step 6: Commit**

```bash
git add src/docmend/scale_qualification.py scripts/qualify_scale.py \
  tests/test_scale_qualification.py docs/scale-evidence/README.md
git commit -m "feat(scale): orchestrate installed-wheel qualification"
```

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
uv run python scripts/qualify_scale.py --tier pilot \
  --workspace /var/tmp/docmend-scale-100k \
  --reference-environment docs/scale-evidence/reference-environment.json \
  --evidence-out /var/tmp/docmend-scale-100k-evidence.json \
  --accept-to docs/scale-evidence/accepted/
```

Expected: exact artifact conservation, complete `verify --plan` coverage, the exact recipe-derived finding multiset with no unexpected findings, zero child swap, reference match, and a new no-clobber accepted pilot document.

- [ ] **Step 4: Derive and freeze thresholds in SPEC revision two**

Validate and copy the sanitized 10k diagnostic into `docs/scale-evidence/supporting/`; it is supporting fit evidence, not an accepted baseline. Use `derive_thresholds` on that committed 10k point and the accepted 100k point. Write `docs/scale-evidence/thresholds.json` with both relative evidence identities and SHA-256 hashes, the shared reference-environment hash, exact fitting method, largest peak plus 25% headroom, fitted slope threshold, and linearity tolerance. Load the new baseline through the production validator and reproduce the verdict before revising SPEC. Record the same values, evidence links, and swap rule in revision two. Keep NFR-001 Partial.

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

Reuse the repository's current checkout/setup-uv conventions, pin uv to the check workflow's reviewed version, validate `docs/scale-evidence/thresholds.json`, run the self-building 100k scheduled tier in `$RUNNER_TEMP` with explicit threshold and evidence paths, and upload that diagnostic evidence plus private logs with limited retention. Accepted evidence remains a reviewed commit.

- [ ] **Step 2: Validate workflow and run locally equivalent command**

```bash
npx --yes prettier@3.6.2 --check .github/workflows/scale-qualification.yml
uv run python scripts/qualify_scale.py --tier scheduled \
  --workspace /var/tmp/docmend-scale-scheduled \
  --reference-environment docs/scale-evidence/reference-environment.json \
  --thresholds docs/scale-evidence/thresholds.json \
  --evidence-out /var/tmp/docmend-scale-scheduled-evidence.json
```

Expected: local command passes; hosted mismatches remain diagnostic rather than replacing binding evidence.

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
