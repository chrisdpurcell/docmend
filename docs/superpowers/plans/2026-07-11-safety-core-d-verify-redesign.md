# Safety-Core Plan D — Verify Redesign (DMR-05) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `docmend verify` an honest, plan-aware certification step that detects every confirmed false-clean state, orders apply attempts from durable lineage, validates backup and lifecycle evidence, emits an optional guarded verify-report artifact, and never observes a corpus while another docmend run is mutating it.

**Architecture:** Keep `verify.py` as the read-only check engine, add `verify_coverage.py` for attempt-graph and exactly-once plan coverage reduction, and add `verify_report.py` plus a pinned JSON Schema for durable results. Manifest parsing remains structurally strict; a new read-only inspection path returns containment defects as findings without dereferencing unsafe paths. The CLI resolves repeatable sidecar/explicit inputs, acquires the corpus lock for both standalone scan and verify, runs the pure checks, and optionally publishes the result through the existing artifact destination guard.

**Tech Stack:** Python 3.14, pydantic v2 strict models, JSON Schema Draft 2020-12, Typer, pytest, Ruff, BasedPyright strict, coverage, pip-audit.

**Design sources (binding):** `docs/specs/docmend.md` rev 0.28 (FR-014, IR-004, IR-007, DR-003/004, §17.3, Appendix B); `docs/adr/adr-0012-verify-semantics-exit-code-taxonomy.md`; `docs/adr/adr-0005-durable-artifact-schema-contract.md`; `docs/adr/adr-0019-manifest-2-recovery-model.md`; `docs/adr/adr-0021-artifact-destination-guard.md`; `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md` §“Verify Redesign (DMR-05)”; `docs/codex-reviews/2026-07-10-2251-all-findings-verification.md` (standalone scan/verify lock medium accepted into Plan D scope).

---

## Global Constraints

- Use TDD for every behavior slice: failing focused test, confirm the expected failure, minimal implementation, focused pass, then the full local gate before commit.
- Run `uv run python scripts/check.py` before every task commit. The current merged baseline is 891 tests and 95% branch coverage; no task may lower the measured percentage.
- Never use `git add .` or `git add -A`; stage only the files named by that task.
- The repository is public. All paths, files, manifests, reports, backups, and plan fixtures must be synthetic; never copy real library bytes or paths.
- Verify remains corpus-read-only. The optional verify-report and the existing log are tool artifacts, not corpus mutations; no verify path may write a manifest, backup, plan, report, or document.
- Exit taxonomy is fixed: `0` clean, `1` findings, `2` invocation/config/structural artifact-input error, `3` safety refusal. Manifest path/BackupStore containment violations are findings in verify, even though restore/resume refuse them with `3`.
- Individual JSON/schema parse failures, unsupported versions, lifecycle-invalid chains, duplicate reports for one run, forked/gapped lineage, and unresolved predecessor edges remain input errors (`2`). Missing report publication after mutation is a finding (`1`), not a structural error.
- The validated ManifestChain is mutation authority. Reports can fill ordinary `skipped` and `not-attempted` outcomes and can confirm `already-applied`; they never override a lifecycle state derived from the manifest.
- Attempt ordering comes only from `prior_attempt` edges. Caller order, filename order, timestamps, and filesystem mtimes are never ordering evidence.
- `verify --plan` computes one final partition over plan actions. Multiple attempt outcomes are transition evidence, not duplicate final partition entries.
- A dry-run-only lineage cannot certify plan coverage. `would_apply` is preview evidence and produces an `uncertified` finding when no write attempt supplies terminal evidence.
- `scan` and `verify` acquire the canonical exclusive corpus lock so neither can observe a mid-apply or mid-restore filesystem. Lock contention is a safety refusal (`3`).
- No dependency additions are needed or permitted by this plan.

## File Structure

| File | Role in this plan |
| --- | --- |
| `src/docmend/verify_report.py` (create) | Strict internal model for the new `docmend/verify-report` 1.0 durable artifact. |
| `src/docmend/schemas/verify-report.schema.json` (create) | External contract for verification inputs, checked-file count, findings, and clean verdict. |
| `src/docmend/artifacts.py` (modify) | Register, validate, read, and write verify reports. |
| `src/docmend/schemas/README.md` (modify) | Add the fifth durable artifact and correct the already-landed report/manifest 2.0 rows. |
| `src/docmend/writer/manifest.py` (modify) | Add a non-mutating manifest inspection path that preserves structural validation while returning containment defects for verify. |
| `src/docmend/verify_coverage.py` (create) | Load and order report/manifest attempts, validate cross-artifact bindings, and reduce exactly-once plan coverage. |
| `src/docmend/verify.py` (modify) | Close content/discovery, root, lifecycle, output-hash, and backup-integrity false-clean paths; orchestrate findings. |
| `src/docmend/cli.py` (modify) | Repeatable verify inputs and sidecar discovery, `--plan`, optional `--out`, strict scan/verify locking, destination guard, exit mapping. |
| `tests/test_verify_report_artifact.py` (create) | Schema/model/IO contract tests for verify-report 1.0. |
| `tests/unit/writer/test_manifest.py` (modify) | Structural-error versus read-only-containment-finding behavior. |
| `tests/test_verify_coverage.py` (create) | Attempt ordering and plan-partition unit matrix. |
| `tests/test_verify.py` (modify) | Pure false-clean checks for discovery, roots, lifecycle, outputs, and backups. |
| `tests/test_cli_verify.py` (modify) | CLI input, exit taxonomy, output guard, lock, and end-to-end false-clean matrix. |
| `tests/test_cli_scan.py` (modify) | Standalone scan lock contention regression. |
| `CHANGELOG.md` (modify) | Plan D safety behavior under `[Unreleased]`. |
| `docs/specs/docmend.md` (modify, final task only) | Rev 0.29 evidence-only traceability sync for FR-014/IR-004/IR-007. |
| `docs/STATUS.md`, `docs/TODO.md`, `docs/handoff/state.md`, `docs/handoff/specs-plans.md` (modify, closeout only) | Current result, completed task, next work, and plan index. |

---

### Task 1: Pin the verify-report 1.0 artifact

**Files:**

- Create: `src/docmend/verify_report.py`
- Create: `src/docmend/schemas/verify-report.schema.json`
- Create: `tests/test_verify_report_artifact.py`
- Modify: `src/docmend/artifacts.py`
- Modify: `src/docmend/schemas/README.md`
- Test: `tests/test_schemas.py`

**Wire contract:**

- `schema = "docmend/verify-report"`, `schema_version = "1.0"`.
- `run_id` identifies the verify invocation, not an apply attempt.
- `verified_path` records the operator argument; `source_root` records its canonical corpus root.
- `inputs` contains immutable `(kind, path, run_id, sha256)` references for each consumed plan, report, or manifest.
- `checked_files` equals the inventory's readable file count.
- `findings` contains the exact emitted `(path, check, detail)` records.
- `clean` is true if and only if `findings` is empty. `write_verify_report` enforces this reconciliation before disk.

- [ ] **Step 1: Write failing model, schema-registry, reconciliation, and round-trip tests**

Create `tests/test_verify_report_artifact.py` with this core fixture and assertions:

```python
from pathlib import Path

import pytest

from docmend import artifacts
from docmend.verify_report import (
    VerificationInput,
    VerifyFindingRecord,
    VerifyReport,
)

RUN_ID = "run_20260711T120000Z_0000aa"
SHA = "sha256:" + "a" * 64


def _report(*, clean: bool = False) -> VerifyReport:
    findings = [] if clean else [
        VerifyFindingRecord(path="synthetic/doc.md", check="hash", detail="mismatch")
    ]
    return VerifyReport(
        run_id=RUN_ID,
        generated_by="docmend test",
        verified_path="synthetic",
        source_root="/synthetic",
        started_at="2026-07-11T12:00:00+00:00",
        completed_at="2026-07-11T12:00:01+00:00",
        inputs=[
            VerificationInput(kind="plan", path="plan.json", run_id=RUN_ID, sha256=SHA)
        ],
        checked_files=1,
        findings=findings,
        clean=clean,
    )


def test_verify_report_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "verify.json"
    report = _report()
    artifacts.write_verify_report(report, path)
    assert artifacts.read_verify_report(path) == report


def test_verify_report_clean_must_reconcile(tmp_path: Path) -> None:
    with pytest.raises(artifacts.ArtifactError, match="clean verdict"):
        artifacts.write_verify_report(_report().model_copy(update={"clean": True}), tmp_path / "x")
```

Extend `tests/test_schemas.py` so `ARTIFACT_KINDS` includes `verify-report`, its schema passes `Draft202012Validator.check_schema`, and the pydantic fixture validates against the hand-authored schema.

- [ ] **Step 2: Run the tests and confirm the missing-contract failures**

Run:

```bash
uv run pytest tests/test_verify_report_artifact.py tests/test_schemas.py -q
```

Expected: collection/import failure because `docmend.verify_report` and the `verify-report` registry entry do not exist.

- [ ] **Step 3: Add the strict model and external schema**

Create `src/docmend/verify_report.py`:

```python
"""Durable verification evidence (FR-014, adr-0005).

The checked-in verify-report schema is the external contract. These strict
models conform to it; artifacts.py validates and reconciles every write.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from docmend.inventory import RunId, Sha256

VERIFY_REPORT_SCHEMA_VERSION = "1.0"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class VerificationInput(_StrictModel):
    kind: Literal["plan", "report", "manifest"]
    path: Annotated[str, Field(min_length=1)]
    run_id: RunId
    sha256: Sha256


class VerifyFindingRecord(_StrictModel):
    path: Annotated[str, Field(min_length=1)]
    check: Annotated[str, Field(min_length=1)]
    detail: Annotated[str, Field(min_length=1)]


class VerifyReport(_StrictModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, populate_by_name=True, serialize_by_alias=True
    )

    schema_kind: Literal["docmend/verify-report"] = Field(
        default="docmend/verify-report", alias="schema"
    )
    schema_version: Literal["1.0"] = VERIFY_REPORT_SCHEMA_VERSION
    run_id: RunId
    generated_by: Annotated[str, Field(min_length=1)]
    verified_path: Annotated[str, Field(min_length=1)]
    source_root: Annotated[str, Field(min_length=1)]
    started_at: str
    completed_at: str
    inputs: list[VerificationInput]
    checked_files: Annotated[int, Field(ge=0)]
    findings: list[VerifyFindingRecord]
    clean: bool
```

Create `src/docmend/schemas/verify-report.schema.json` as a strict Draft 2020-12 object matching those fields. Require every field, use the repository's existing `run_id` and `sha256` regexes, assert `date-time` for both timestamps, set `additionalProperties: false` at every object, and use the literal artifact/schema versions above.

- [ ] **Step 4: Register verify-report IO and enforce the clean verdict**

In `src/docmend/artifacts.py`, add `verify-report` to `ArtifactKind`/`ARTIFACT_KINDS`, import `VerifyReport`, and add:

```python
def write_verify_report(report: VerifyReport, path: Path) -> None:
    """Validate and persist one internally reconciled verify result."""
    if report.clean != (not report.findings):
        raise ArtifactError("verify-report clean verdict does not reconcile with findings")
    document: dict[str, object] = report.model_dump(mode="json")
    validate_artifact("verify-report", document)
    write_json_artifact(document, path)


def read_verify_report(path: Path) -> VerifyReport:
    """Load one validated verify-report artifact."""
    try:
        document: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"{path}: cannot read verify-report artifact ({exc})") from exc
    validate_artifact("verify-report", document)
    report = VerifyReport.model_validate(document)
    if report.clean != (not report.findings):
        raise ArtifactError(f"{path}: clean verdict does not reconcile with findings")
    return report
```

Update `src/docmend/schemas/README.md` to list verify-report 1.0 and correct the report and manifest rows to their landed 2.0 contracts.

- [ ] **Step 5: Run focused tests and the full gate**

Run:

```bash
uv run pytest tests/test_verify_report_artifact.py tests/test_schemas.py -q
uv run python scripts/check.py
```

Expected: focused tests pass; full gate passes at or above 95% branch coverage.

- [ ] **Step 6: Commit Task 1**

```bash
git add src/docmend/verify_report.py src/docmend/artifacts.py \
  src/docmend/schemas/verify-report.schema.json src/docmend/schemas/README.md \
  tests/test_verify_report_artifact.py tests/test_schemas.py
git commit -m "feat(verify): add durable verify report"
```

---

### Task 2: Preserve structural manifest validation while surfacing containment as findings

**Files:**

- Modify: `src/docmend/writer/manifest.py`
- Modify: `tests/unit/writer/test_manifest.py`

**Interface:**

```python
@dataclass(frozen=True)
class ManifestInspectionFinding:
    path: str
    action_id: str
    check: Literal["manifest-containment", "backup-containment"]
    detail: str


@dataclass(frozen=True)
class ManifestInspection:
    chain: ManifestChain
    findings: tuple[ManifestInspectionFinding, ...]


def inspect_manifest_chain(paths: Sequence[Path]) -> ManifestInspection:
    """Validate structure without touching referenced objects; return containment defects."""
```

`read_manifest_chain` remains unchanged for mutating consumers. Both paths call shared collectors so verify cannot drift from restore/resume containment rules.

- [ ] **Step 1: Write failing inspection-policy tests**

Add tests proving:

```python
def test_inspect_chain__path_escape_is_finding_not_error(tmp_path: Path) -> None:
    manifest_path = write_manifest_with_original_path(tmp_path, "/outside/doc.txt")
    inspected = inspect_manifest_chain([manifest_path])
    assert inspected.chain.sets
    assert [(f.action_id, f.check) for f in inspected.findings] == [
        (f"{RUN_ID}/a1", "manifest-containment")
    ]


def test_inspect_chain__lifecycle_error_stays_input_error(tmp_path: Path) -> None:
    manifest_path = write_manifest_with_duplicate_applied(tmp_path)
    with pytest.raises(ArtifactError, match="terminal"):
        inspect_manifest_chain([manifest_path])
```

Add equivalent off-key BackupStore and symlink-component cases. Assert the inspection path never opens the escaped corpus path or untrusted backup leaf by monkeypatching `Path.read_bytes`/`Path.open` for those exact paths to fail the test if called.

- [ ] **Step 2: Run and confirm the missing API failure**

```bash
uv run pytest tests/unit/writer/test_manifest.py -q
```

Expected: import/attribute failure for `inspect_manifest_chain`.

- [ ] **Step 3: Refactor containment checks into shared collectors**

Replace raise-only containment helpers with collectors that return immutable findings. Keep current `read_manifest_set` behavior by raising `ManifestContainmentError` on the first collected defect. Add an internal structural reader that skips only the shared containment collectors; it must still enforce header/version, run/sequence, per-set and cross-set lifecycle, kind, hash-chain coherence, attempt lineage, and `undoes` references.

The inspection path must:

```python
def inspect_manifest_chain(paths: Sequence[Path]) -> ManifestInspection:
    sets = [_read_manifest_set_structural(path) for path in paths]
    chain = _finish_chain_validation(paths, sets)
    findings = tuple(
        finding
        for manifest_set in chain.sets
        for finding in _containment_findings(manifest_set)
    )
    return ManifestInspection(chain=chain, findings=findings)
```

Do not catch `ArtifactError` broadly: structural defects must remain exit-2 inputs at the CLI.

- [ ] **Step 4: Run focused tests and the full gate**

```bash
uv run pytest tests/unit/writer/test_manifest.py tests/test_manifest_chain.py tests/test_restore.py tests/test_resume.py -q
uv run python scripts/check.py
```

Expected: focused and full gates pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/docmend/writer/manifest.py tests/unit/writer/test_manifest.py
git commit -m "feat(verify): inspect manifest containment read only"
```

---

### Task 3: Close discovery, root, lifecycle, output-hash, and backup false-clean paths

**Files:**

- Modify: `src/docmend/verify.py`
- Modify: `tests/test_verify.py`

**Interfaces:**

```python
def check_discovery(inventory: Inventory) -> list[VerifyFinding]
def check_manifest_root(chain: ManifestChain, verified_root: Path) -> list[VerifyFinding]
def manifest_inspection_findings(inspection: ManifestInspection) -> list[VerifyFinding]
def check_lifecycle(chain: ManifestChain) -> list[VerifyFinding]
def check_outputs(
    chain: ManifestChain, *, unsafe_action_ids: AbstractSet[str] = frozenset()
) -> list[VerifyFinding]
def check_backups(
    chain: ManifestChain, *, unsafe_action_ids: AbstractSet[str] = frozenset()
) -> list[VerifyFinding]
```

- `check_discovery` emits one finding per `unreadable`/`timeout` skip and a `zero-checked` finding when no readable files exist but scan observed candidate evidence (`skipped`, symlink, or hard-link records). A genuinely empty directory stays clean.
- `check_manifest_root` compares the canonical verified root with the chain root.
- `manifest_inspection_findings` converts Task 2's typed containment defects into the public `VerifyFinding` shape without reading the referenced paths.
- `check_lifecycle` consumes `reduce_lifecycle`; `pending-intent` and `pending-restore` are findings. `restored`/`restore-failed` are findings for plan certification because the applied result is no longer fully present.
- `check_outputs` hashes the final reducer-selected applied records, not raw record lines. It skips action IDs whose manifest containment failed.
- `check_backups` checks each final applied record's non-null source/overwritten backup once. It rejects missing, symlinked, non-regular, unreadable, or digest-mismatched bytes. It skips action IDs whose containment inspection failed.
- The CLI does not call either filesystem check when `check_manifest_root` reports that the chain belongs to another corpus.

- [ ] **Step 1: Replace v1 record-list tests with failing ManifestChain tests**

Use `tests.helpers.manifest2.chain_of` and add tests for every row:

```python
def test_discovery_unreadable_and_timeout__findings() -> None:
    inventory = inventory_with_skips("unreadable", "timeout")
    assert {finding.check for finding in check_discovery(inventory)} == {
        "discovery-unreadable",
        "discovery-timeout",
        "zero-checked",
    }


def test_dangling_intent__lifecycle_finding(tmp_path: Path) -> None:
    chain = chain_of([intent_record(tmp_path)])
    assert [(f.check, f.path) for f in check_lifecycle(chain)] == [
        ("lifecycle", f"{RUN_ID}/a1")
    ]


def test_corrupt_source_backup__integrity_finding(tmp_path: Path) -> None:
    chain = applied_chain_with_backup(tmp_path, backup_bytes=b"corrupt")
    assert [(f.check, f.detail) for f in check_backups(chain)] == [
        ("backup", "source backup hash does not match recorded before-hash")
    ]
```

Add missing source backup, missing overwritten backup, corrupt overwritten backup, wrong root, missing output, changed output, restored, restore-failed, and genuinely empty directory cases.

- [ ] **Step 2: Run and confirm failures against the v1 verify API**

```bash
uv run pytest tests/test_verify.py -q
```

Expected: failures because the new chain-aware functions do not exist and `reconcile_manifest` still consumes raw records.

- [ ] **Step 3: Implement the pure checks and delete the divergent raw-record reducer**

Import `ManifestChain` and `reduce_lifecycle`. Replace `reconcile_manifest` with the functions above. Keep `check_content` and `check_frontmatter` behavior unchanged. Use Plan C's descriptor-bound reader so backup identity and bytes come from one regular, no-follow descriptor:

```python
def _check_backup(path: Path, expected_sha256: str, *, action_id: str, role: str) -> VerifyFinding | None:
    try:
        bound = bind_file(path)
    except (OSError, InterferenceError) as exc:
        return VerifyFinding(action_id, "backup", f"{role} backup missing or unreadable ({exc})")
    if _sha(bound.data) != expected_sha256:
        return VerifyFinding(action_id, "backup", f"{role} backup hash mismatch")
    return None
```

Call it only after Task 2 inspection has established the backup key is trusted. Deduplicate intent/terminal references by reducing lifecycle first.

- [ ] **Step 4: Run focused tests and the full gate**

```bash
uv run pytest tests/test_verify.py tests/unit/writer/test_manifest.py -q
uv run python scripts/check.py
```

Expected: all pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/docmend/verify.py tests/test_verify.py
git commit -m "feat(verify): close corpus and recovery false clean paths"
```

---

### Task 4: Load and order the complete attempt-evidence graph

**Files:**

- Create: `src/docmend/verify_coverage.py`
- Create: `tests/test_verify_coverage.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class AttemptEvidence:
    run_id: str
    prior_attempt: PriorAttempt | None
    manifest_set: ManifestSet | None
    report: Report | None
    report_sha256: str | None


@dataclass(frozen=True)
class VerificationEvidence:
    plan: Plan | None
    plan_sha256: str | None
    manifest_inspection: ManifestInspection
    attempts: tuple[AttemptEvidence, ...]
    inputs: tuple[VerificationInput, ...]
    findings: tuple[VerifyFinding, ...]


def load_verification_evidence(
    plan_path: Path | None,
    manifest_paths: Sequence[Path],
    report_paths: Sequence[Path],
) -> VerificationEvidence:
```

The loader validates individual artifacts structurally, hashes one immutable snapshot of each, enforces at most one report and manifest per run, requires report/header agreement when both survive, and orders the unified graph root-to-tip through `prior_attempt`. A missing report for a manifest attempt containing `intent` or `applied` mutation evidence is recorded as `coverage-unprovable`; an unresolved predecessor edge remains `ArtifactError` because no deterministic order exists. `plan_path=None` preserves the existing report↔manifest accounting surface without activating full plan coverage: report and manifest plan hashes must still agree, applied report claims must still have reducer-backed applied evidence, and manifest-applied actions must still appear in their run's report when that report is present.

- [ ] **Step 1: Write the failing attempt-graph matrix**

Add tests for:

- shuffled report and manifest input order;
- report-only first attempt followed by a normal write attempt;
- manifest-with-missing-report followed by a normal retry;
- composed R1 report-only → R2 manifest-with-missing-report → R3 success, all inputs shuffled;
- duplicate report for one run;
- report/header `prior_attempt` disagreement;
- report `manifest_sha256` disagreement;
- plan/report/header hash mismatch;
- unresolved predecessor report hash;
- two roots/tips.

The central ordering assertion is:

```python
evidence = load_verification_evidence(plan_path, [m3, m2], [r3, r1])
assert [attempt.run_id for attempt in evidence.attempts] == [RUN_1, RUN_2, RUN_3]
assert any(
    finding.check == "coverage-unprovable" and finding.path == RUN_2
    for finding in evidence.findings
)
```

- [ ] **Step 2: Run and confirm the missing-module failure**

```bash
uv run pytest tests/test_verify_coverage.py -q
```

Expected: collection failure because `docmend.verify_coverage` does not exist.

- [ ] **Step 3: Implement immutable snapshot loading and graph ordering**

When a plan is supplied, reuse `artifacts.read_plan_snapshot`; always use `artifacts.read_report_snapshot`, `manifest.inspect_manifest_chain`, and each `ManifestSet.sha256`. Build a `run_id -> AttemptEvidence` map, merge report/header evidence only after agreement checks, then order by predecessor references:

```python
roots = [run_id for run_id, attempt in attempts.items() if attempt.prior_attempt is None]
if len(roots) != 1:
    raise ArtifactError(f"attempt evidence must have exactly one root; found {len(roots)}")

successors: dict[str, str] = {}
for run_id, attempt in attempts.items():
    edge = attempt.prior_attempt
    if edge is None:
        continue
    predecessor = _resolve_predecessor(edge, attempts)
    if predecessor in successors:
        raise ArtifactError(f"attempt lineage forks after run {predecessor}")
    successors[predecessor] = run_id
```

Walk from the root, reject leftovers/gaps, and derive `VerificationInput` records from the exact snapshots consumed. Cross-artifact binding mismatches are findings when the graph remains orderable; contradictory duplicate/cardinality/edge identities are input errors.

- [ ] **Step 4: Run focused tests and the full gate**

```bash
uv run pytest tests/test_verify_coverage.py tests/test_manifest_chain.py -q
uv run python scripts/check.py
```

Expected: all pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/docmend/verify_coverage.py tests/test_verify_coverage.py
git commit -m "feat(verify): order durable attempt evidence"
```

---

### Task 5: Reduce exactly-once plan coverage across attempts

**Files:**

- Modify: `src/docmend/verify_coverage.py`
- Modify: `tests/test_verify_coverage.py`

**Interface:**

```python
type CertifiedOutcome = Literal["applied", "failed", "skipped", "not-attempted"]


@dataclass(frozen=True)
class CoverageResult:
    outcomes: Mapping[str, CertifiedOutcome]
    findings: tuple[VerifyFinding, ...]


def check_plan_coverage(evidence: VerificationEvidence) -> CoverageResult:
```

`check_plan_coverage` requires `evidence.plan` and `evidence.plan_sha256` to be non-null; the CLI calls it only when `--plan` was supplied. The loader itself remains usable for legacy report↔manifest accounting without a plan.

Two passes are mandatory. Pass 1 seeds mutation-authoritative states from `reduce_lifecycle`. Pass 2 processes ordered report observations for actions the manifest intentionally does not record and validates cross-attempt transitions. The final `outcomes` mapping has at most one entry per plan action.

- [ ] **Step 1: Add the failing full-partition matrix**

Cover all required cases:

- clean single write;
- clean single resume and double resume where `already-applied` retains `applied`;
- first-action abort with `failed` + trailing `not-attempted` and no manifest;
- all-skip report-only attempt;
- failed-manifest then successful retry;
- dry-run-only `would_apply` lineage (`uncertified` finding);
- missing report after mutation (`coverage-unprovable` finding);
- omitted, duplicate, and foreign plan actions;
- illegal transitions (`applied -> failed`, `skipped/already-applied` without manifest-applied authority, report `applied` without manifest evidence);
- pending intent/restore and fully restored plan states.

Use final assertions such as:

```python
result = check_plan_coverage(double_resume_evidence())
assert result.outcomes == {ACTION_1: "applied", ACTION_2: "applied"}
assert result.findings == ()
```

- [ ] **Step 2: Run and confirm the missing-reducer failure**

```bash
uv run pytest tests/test_verify_coverage.py -q
```

Expected: failure because `check_plan_coverage` is absent.

- [ ] **Step 3: Implement mutation-first coverage reduction**

Use a small explicit transition table, not scattered conditionals:

```python
_ALLOWED_REPORT_TRANSITIONS = frozenset(
    {
        ("not-attempted", "skipped"),
        ("not-attempted", "failed"),
        ("not-attempted", "applied"),
        ("failed", "applied"),
        ("applied", "already-applied"),
    }
)
```

Within each report, duplicate action IDs are findings. Across reports, validate transitions in `evidence.attempts` order. `already-applied` is represented by `status == "skipped" and skip_reason == "already-applied"`. After both passes:

```python
for action_id in plan_actions:
    if action_id not in outcomes:
        findings.append(VerifyFinding(action_id, "coverage", "plan action has no terminal outcome"))
for action_id in outcomes.keys() - plan_actions:
    findings.append(VerifyFinding(action_id, "coverage", "artifact evidence names no plan action"))
```

Do not let a report overwrite a reducer-derived applied/failed/pending/restored state. A report claim may confirm it or produce a contradiction finding only.

- [ ] **Step 4: Run focused tests and the full gate**

```bash
uv run pytest tests/test_verify_coverage.py tests/test_verify.py -q
uv run python scripts/check.py
```

Expected: all pass.

- [ ] **Step 5: Commit Task 5**

```bash
git add src/docmend/verify_coverage.py tests/test_verify_coverage.py
git commit -m "feat(verify): certify full plan coverage"
```

---

### Task 6: Rebuild the verify CLI around repeatable evidence and guarded output

**Files:**

- Modify: `src/docmend/cli.py`
- Modify: `tests/test_cli_verify.py`
- Modify: `tests/test_cli_scan.py`

**CLI contract:**

- `--manifest FILE` repeatable.
- `--report FILE` repeatable.
- `--run-id ID` repeatable and combinable with explicit paths; each ID resolves whichever default report/manifest sidecars exist and errors when neither exists.
- `--plan FILE` activates binding plan coverage. Reports without a plan remain legal only for legacy report↔manifest accounting; report-only attempt coverage requires `--plan`.
- `--out FILE` optionally writes verify-report 1.0. Without `--out`, verify preserves the current no-result-artifact behavior.
- Every explicit and sidecar-resolved plan/report/manifest is an invocation input for the destination-alias guard.
- Guard the output before scan; acquire the strict corpus lock before any corpus read; hold it through verify-report publication.

- [ ] **Step 1: Write failing CLI input, guard, and lock tests**

Add tests for repeatable shuffled chains, relocated prior reports, report-only predecessors, missing sidecars, `--plan` coverage, `--out` schema contents, output alias refusal, in-corpus output refusal, excluded `.docmend/` output acceptance, and no-output default.

Add a lock test for each command:

```python
held = lock.acquire(corpus.resolve(), run_id=RUN_ID, command="apply")
try:
    result = runner.invoke(app, ["verify", str(corpus)])
finally:
    held.release()
assert result.exit_code == 3
assert "another docmend run holds the lock" in result.output
```

- [ ] **Step 2: Run and confirm the old scalar-option/lock failures**

```bash
uv run pytest tests/test_cli_verify.py tests/test_cli_scan.py -q
```

Expected: new repeatable/output tests fail; standalone scan and verify currently ignore a held lock.

- [ ] **Step 3: Add one resolver for explicit and sidecar evidence**

In `src/docmend/cli.py` add:

```python
def _resolve_verify_evidence_paths(
    manifests: list[Path] | None,
    reports: list[Path] | None,
    run_ids: list[str] | None,
) -> tuple[list[Path], list[Path]]:
    manifest_paths = list(manifests or [])
    report_paths = list(reports or [])
    for run_id in run_ids or []:
        sidecar_manifest = Path(ARTIFACT_DIR_NAME) / f"docmend-{run_id}-manifest.jsonl"
        sidecar_report = Path(ARTIFACT_DIR_NAME) / f"docmend-{run_id}-report.json"
        found = False
        if sidecar_manifest.is_file():
            manifest_paths.append(sidecar_manifest)
            found = True
        if sidecar_report.is_file():
            report_paths.append(sidecar_report)
            found = True
        if not found:
            raise artifacts.ArtifactError(
                f"--run-id {run_id}: neither default manifest nor report sidecar exists"
            )
    return list(dict.fromkeys(manifest_paths)), list(dict.fromkeys(report_paths))
```

Path deduplication is exact path spelling only; snapshot loaders and run/cardinality checks remain authoritative for aliases.

- [ ] **Step 4: Rewire verify orchestration and exit mapping**

Compute `corpus_root = (path if path.is_dir() else path.parent).resolve()`. If `--out` is present, guard it before acquiring the lock and before `discovery.scan`. Then:

```python
run_lock = _acquire_run_lock_strict(corpus_root, run_id=run_id, command="verify")
try:
    inventory = discovery.scan(path, config, run_id=run_id, generated_at=started_at)
    findings = check_content(inventory) + check_frontmatter(inventory) + check_discovery(inventory)
    evidence = None
    if manifest_paths or report_paths or plan_path is not None:
        evidence = load_verification_evidence(plan_path, manifest_paths, report_paths)
        inspection = evidence.manifest_inspection
        findings.extend(evidence.findings)
        findings.extend(manifest_inspection_findings(inspection))
        root_findings = check_manifest_root(inspection.chain, corpus_root)
        findings.extend(root_findings)
        findings.extend(check_lifecycle(inspection.chain))
        if not root_findings:
            unsafe = frozenset(item.action_id for item in inspection.findings)
            findings.extend(check_outputs(inspection.chain, unsafe_action_ids=unsafe))
            findings.extend(check_backups(inspection.chain, unsafe_action_ids=unsafe))
    if plan_path is not None and evidence is not None:
        findings.extend(check_plan_coverage(evidence).findings)
    if out_path is not None:
        result_report = VerifyReport(
            run_id=run_id,
            generated_by=f"docmend {__version__}",
            verified_path=str(path),
            source_root=str(corpus_root),
            started_at=started_at,
            completed_at=datetime.now(UTC).isoformat(),
            inputs=list(evidence.inputs) if evidence is not None else [],
            checked_files=inventory.totals.files,
            findings=[
                VerifyFindingRecord(path=item.path, check=item.check, detail=item.detail)
                for item in findings
            ],
            clean=not findings,
        )
        artifacts.write_verify_report(result_report, out_path)
finally:
    run_lock.release()
```

Use the explicit construction above; do not pass an ambient locals dict into a report builder.

Catch `ManifestContainmentError` only if an invariant regression escapes the inspection API and map it to a finding; catch other `ArtifactError` as exit `2`. Artifact guard and lock refusals remain exit `3` through existing helpers.

- [ ] **Step 5: Acquire the same strict lock in standalone scan**

After the scan artifact guard and before `discovery.scan`, acquire `_acquire_run_lock_strict(corpus_root, run_id=run_id, command="scan")`; hold it through `write_inventory`, and release in `finally`. The plan shorthand already holds the same lock around its scan+plan pair and needs no behavior change.

- [ ] **Step 6: Run focused tests and the full gate**

```bash
uv run pytest tests/test_cli_verify.py tests/test_cli_scan.py tests/test_cli_plan.py -q
uv run python scripts/check.py
```

Expected: all pass; scan/verify contention exits `3`; verify findings exit `1`; malformed inputs exit `2`; guarded output refusal exits `3` before scanning.

- [ ] **Step 7: Commit Task 6**

```bash
git add src/docmend/cli.py tests/test_cli_verify.py tests/test_cli_scan.py
git commit -m "feat(cli): expose plan aware verification"
```

---

### Task 7: Add the end-to-end false-clean and lineage regression matrix

**Files:**

- Modify: `tests/test_cli_verify.py`
- Modify: `tests/test_verify_coverage.py`
- Modify: `tests/test_restore_drill.py`

- [ ] **Step 1: Add one CLI regression for every DMR-05 false-clean class**

Each test must invoke the real CLI over synthetic temporary artifacts and assert both exit code and finding family:

| Case | Expected finding / exit |
| --- | --- |
| Missing source backup | `[backup]`, `1` |
| Corrupt source backup | `[backup]`, `1` |
| Missing/corrupt overwritten backup | `[backup]`, `1` |
| Every candidate unreadable/timed out | `[discovery-*]` + `[zero-checked]`, `1` |
| Wrong-root manifest | `[manifest-root]`, `1` |
| Dangling apply intent | `[lifecycle]`, `1` |
| Dangling restore intent | `[lifecycle]`, `1` |
| Aborted plan trailing action omitted | `[coverage]`, `1` |
| Dry-run-only report | `[coverage-uncertified]`, `1` |
| Manifest attempt missing report | `[coverage-unprovable]`, `1` |
| Crafted containment escape | `[manifest-containment]`, `1`; escaped path never opened |
| Lifecycle-invalid manifest | input error, `2` |

- [ ] **Step 2: Add clean single-, double-resume, and composed-lineage CLI proofs**

Build artifacts through the real `plan`/`apply`/resume commands where practical. For the crash-after-manifest-close window, use the existing manifest helpers to remove only the report after a completed synthetic attempt; never hand-author a structurally impossible chain.

The composed proof must pass inputs shuffled:

```python
result = runner.invoke(
    app,
    [
        "verify", str(corpus), "--plan", str(plan),
        "--manifest", str(m3), "--report", str(r1),
        "--manifest", str(m2), "--report", str(r3),
    ],
)
assert result.exit_code == 1
assert "coverage-unprovable" in result.output
assert "attempt lineage" not in result.output
```

The missing R2 report is a finding; it must not break deterministic R1→R2→R3 ordering.

- [ ] **Step 3: Run the matrix and fix only implementation defects it exposes**

```bash
uv run pytest tests/test_cli_verify.py tests/test_verify_coverage.py tests/test_restore_drill.py -q
```

Expected: all matrix cases pass. If a test exposes an underspecified semantic conflict, stop and record an `OQ-` rather than weakening the assertion.

- [ ] **Step 4: Run the full gate**

```bash
uv run python scripts/check.py
```

Expected: full gate passes at or above 95% branch coverage.

- [ ] **Step 5: Commit Task 7**

```bash
git add tests/test_cli_verify.py tests/test_verify_coverage.py tests/test_restore_drill.py
git commit -m "test(verify): cover false clean and resume lineage matrix"
```

---

### Task 8: Changelog, spec traceability, and handoff closeout

**Files:**

- Modify: `CHANGELOG.md`
- Modify: `docs/specs/docmend.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/TODO.md`
- Modify: `docs/handoff/state.md`
- Modify: `docs/handoff/specs-plans.md`
- Modify: `docs/handoff/sessions/2026-07.md` only if the result adds durable history not already captured by status/spec/changelog

- [ ] **Step 1: Record the user-visible Plan D behavior**

Under `[Unreleased]`, add a concise Plan D entry covering plan-aware verify, complete false-clean findings, optional durable verify report, repeatable lineage inputs, and scan/verify lock consistency. Do not document sub-project 2–4 work as complete.

- [ ] **Step 2: Update spec rev 0.29 as evidence-only completion**

Add a revision-history row stating that only §17.3 evidence/status changed. Update:

- FR-014 to Complete with named tests from `tests/test_verify.py`, `tests/test_verify_coverage.py`, and `tests/test_cli_verify.py`;
- IR-004 to Complete with repeatable inputs, sidecar discovery, read-only/lock, and exit taxonomy tests;
- IR-007 to include the verify-report schema/round-trip and destination-guard tests.

Do not modify requirement text, ADR decisions, open questions, or deviations unless implementation actually diverged.

- [ ] **Step 3: Reconcile current project and handoff state**

- Mark Plan D complete in the agent queue while preserving the user task section exactly.
- Move the current status to “Plans A–D complete”; keep sub-projects 2–4 and the v2.0.0 release PR open.
- Update `docs/handoff/specs-plans.md` so Plans A–D and their implementation state are accurate.
- Keep `docs/handoff/state.md` below its cap and focused on the next session: push only when authorized, then sub-project 2 (scale/DMR-08).

- [ ] **Step 4: Run complete code, spec, Markdown, and handoff validation**

Run:

```bash
uv sync --locked --all-groups
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run coverage run -m pytest
uv run coverage report
uv run pip-audit
uv run python scripts/check_traceability.py
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec validate --config .project-standards.yml
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec lint --config .project-standards.yml --strict
npx --yes prettier@3.6.2 --check CHANGELOG.md docs/specs/docmend.md docs/STATUS.md docs/TODO.md docs/handoff/state.md docs/handoff/specs-plans.md
npx --yes markdownlint-cli2@0.18.1 CHANGELOG.md docs/specs/docmend.md docs/STATUS.md docs/TODO.md docs/handoff/state.md docs/handoff/specs-plans.md
project-standards agent-handoff validate --repo .
project-standards agent-handoff drift-check --repo .
```

Expected: all commands pass; pytest count is greater than 891; branch coverage is at least 95%; the opt-in scale test may remain the one expected skip.

- [ ] **Step 5: Review the complete branch diff**

```bash
git status --short
git diff --check
git diff --stat dev...HEAD
git log --oneline --decorate dev..HEAD
```

Confirm every changed file belongs to Plan D, every plan task has a commit, no real paths/content appear, and no unrelated user work is staged.

- [ ] **Step 6: Commit closeout**

```bash
git add CHANGELOG.md docs/specs/docmend.md docs/STATUS.md docs/TODO.md \
  docs/handoff/state.md docs/handoff/specs-plans.md
git commit -m "docs(handoff): close out Plan D implementation"
```

If `docs/handoff/sessions/2026-07.md` changed, add it explicitly to the command. Do not push without owner authorization.

---

## Self-Review Notes

- **Spec coverage:** Task 3 closes backup, zero-checked, discovery-skip, wrong-root, and dangling-lifecycle findings. Tasks 4–5 implement the required lineage and exactly-once `verify --plan` contract. Task 6 exposes repeatable inputs, optional guarded output, exit taxonomy, and scan/verify lock consistency. Task 7 proves every false-clean row plus the required resume/report-only/missing-report shapes. Task 8 completes FR-014/IR-004/IR-007 traceability.
- **Current versus intended state:** Existing content/frontmatter checks, report 2.0, manifest 2.0, reducer, attempt edges, timeout exits, restore selector exit, and artifact guard are current on `dev`. The verify-report, inspection policy, coverage reducer, repeatable verify CLI, and scan/verify locks are intended Plan D work.
- **No dependency or behavior expansion:** The plan adds no external dependency, no mutation path, no exit code, and no deferred DMR-08/09 or observability hardening.
- **Intentional interface choice:** verify-report publication is explicit through `--out`; omitting it preserves the current no-result-artifact behavior while still satisfying the approved “optional durable result” contract.
- **Ambiguity resolved in favor of safety:** Empty directories remain clean, but a zero-readable-file scan with observed candidates is a finding. Structural artifact contradictions remain exit `2`; containment violations and missing post-mutation reports are exit `1` findings.
