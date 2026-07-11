# Safety-Core Plan B — Manifest 2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Revision note: revised per [plan review round 1](../../codex-reviews/2026-07-10-safety-core-b-manifest-2-plan-review.md) — CR-001 (shared wire types move to a dependency-neutral `docmend/lineage.py`), CR-002 (the complete F5 BackupStore trust boundary lands in `read_manifest_set` with adversarial fixtures), CR-003 (tasks recut into green vertical slices; the full gate runs before every commit), CR-004 (predecessor-attempt discovery is a separate input from mutation-manifest loading; report-only and relocated-report predecessors are first-class), CR-005 (one deterministic kill-after-step test per restore adjudication row plus restore identity-substitution probes), CR-006 (attempt-chain/subchain consistency invariants stated per kind, with the report-flavored deferrals named), CR-007 (the superseding recovery ADR is adr-0019). Revised again per review round 2: CR-003 (Task 2 now names every live `read_manifest` consumer — including the verify CLI path and three previously omitted test files — and the per-set lifecycle rule is provisional so pre-Task-6 producers stay readable), CR-004/CR-NEW-001 (a root manifest may carry a report-flavored attempt edge; report-only acceptance requires `manifest_sha256: null` and zero applied outcomes — a report whose non-null manifest hash has no matching manifest input is MISSING MUTATION EVIDENCE, exit 2), CR-006 (one deterministic attempt graph over all supplied reports/manifests/run-ids replaces caller order; every report field checkable at apply-resume is validated there), CR-NEW-002 (standalone adjudication terminals are provisionally legal per set and must close exactly one prior dangling intent at chain scope), CR-NEW-003 (restore headers carry `backup_root: null` — inverse records hold no backup references), CR-NEW-004 (this plan's review artifact is tracked in the same commit).

**Goal:** Implement the manifest 2.0 recovery model from the approved [safety-core design](../specs/2026-07-10-safety-core-remediation-design.md): header/chain/attempt lineage, journal-every-mutation with durable object identities, ManifestSet/chain validation, one lifecycle reducer with the dangling-intent adjudication table, and the resume/restore rewrite — closing DMR-03 and DMR-04.

**Architecture:** Clean-break rewrite of `writer/manifest.py` into a validated header+records wire model with chain links; shared wire primitives (`ObjectIdentity`, `PriorAttempt`) live in a new dependency-neutral `docmend/lineage.py` so `atomic.py`, `report.py`, and `manifest.py` can all import them without cycles; a new `writer/adjudicate.py` holds the design's adjudication table; `writer/apply.py` journals intent→mutate→terminal for every mutation kind with identities captured via a new staged-write API in `writer/atomic.py`; `restore.py` becomes a chain consumer that journals its inverses; resume, restore (and later verify, Plan D) all consume one `reduce_lifecycle`. Report schema bumps to 2.0 for attempt lineage and `not-attempted`.

**Tech Stack:** Python 3.14, Pydantic v2 strict models, jsonschema Draft 2020-12, pytest (+ the `test_resume.py` deterministic fault-injection pattern), uv/Ruff/BasedPyright per the standard gate.

## Global Constraints

- Binding spec: SPEC-VHHB rev 0.27 with ADRs 0019–0021; adr-0006 is superseded by **adr-0019** (manifest 2.0 recovery model). adr-0020 (commit-boundary object identity) governs Plan C; Plan B persists the identity _evidence_, Plan C tightens its _capture_.
- Clean break: no 1.x manifest read path. A 1.x manifest is rejected with: `this manifest was written by docmend 1.x; restore pre-2.0 runs with docmend 1.0.2` (exit 2, ERR-008).
- Schema versions: manifest header + record `2.0`; report `2.0`; plan and inventory unchanged.
- Exit taxonomy (adr-0012, unchanged codes): malformed/lifecycle-invalid manifest = exit 2; containment violation (paths escaping `source_root`, backup outside the BackupStore trust boundary) = exit 3 in restore/resume; per-action interference = skip counting toward exit 1.
- Identity comparison is exact `(st_dev, st_ino)` equality; device mismatch refuses as `external-interference`, never substitutes.
- Every mutation kind (rewrite, rename, rename_and_rewrite, each restore inverse) appends a fsync'd `intent` before any corpus name is touched and a terminal after. Pre-mutation failures append `failed` with no intent.
- The staging write precedes the intent (it creates only a tool-owned `O_EXCL` temp, never a corpus name) so `expected_published_identity` is knowable pre-mutation.
- **Green-slice commit rule (CR-003):** every task ends in a state where the FULL gate — `uv run python scripts/check.py` (Ruff format+lint, BasedPyright strict, complete pytest with ≥97% branch coverage, pip-audit) — passes. Run it immediately before every commit; no commit is retained with a failing or partially-run gate. Tasks are cut so this is achievable: additive tasks first, the one unavoidable format-break slice (Task 2) updates all consumers and fixtures in the same commit.
- New skip reason `external-interference`; new report outcome status `not-attempted` (`collision-unpreserved` is Plan C).
- Never `git add .`; add files by name.

## File Structure

- `src/docmend/lineage.py` — NEW, dependency-neutral (imports only stdlib, pydantic, and `docmend.inventory` aliases): `ObjectIdentity`, `PriorAttempt`. Imported by `writer/atomic.py`, `writer/manifest.py`, and `report.py` — this placement is what breaks both CR-001 cycles (`manifest → atomic` and `manifest → artifacts → report` already exist in the graph).
- `src/docmend/writer/manifest.py` — rewritten: `ManifestHeader`, `ManifestRecord` 2.0, `ManifestWriter` (header-first), `ManifestSet`, `ManifestChain`, `read_manifest_set`, `read_manifest_chain`, `reduce_lifecycle`, `manifest_sha256`, `ManifestContainmentError`.
- `src/docmend/writer/adjudicate.py` — new: the dangling-intent adjudication table for apply kinds and restore inverses.
- `src/docmend/writer/atomic.py` — extended: `stage_bytes` / `publish_staged` / `abort_staged` staged-write API (existing `atomic_write_bytes` refactored on top; behavior unchanged).
- `src/docmend/writer/apply.py` — journal-every-mutation rewrite; resume consumes `reduce_lifecycle` + adjudication; abort emits `not-attempted`.
- `src/docmend/restore.py` — chain consumer; journaled inverses with `undoes_*`; adjudication-based convergence.
- `src/docmend/report.py` + `src/docmend/schemas/report.schema.json` — 2.0: `not-attempted`, `totals.not_attempted`, `prior_attempt`, `manifest_sha256`.
- `src/docmend/schemas/manifest.schema.json` (2.0 record) + new `src/docmend/schemas/manifest-header.schema.json`; `artifacts.ArtifactKind` gains `"manifest-header"`.
- `src/docmend/cli.py` — apply/restore wiring: predecessor-attempt discovery (separate from mutation-manifest loading), chain reading, `plan_sha256`, `prior_attempt`, `--prior-report`, clean-break message, restore selector-miss exit 1, scan/plan timeout exit 1.
- `tests/test_scale.py` — mechanical manifest-shape assertion update.
- Tests: `tests/test_lineage_imports.py` (new import smoke), `tests/unit/writer/test_manifest.py` (rewrite), `tests/helpers/manifest2.py` (new fixture builder), new `tests/unit/writer/test_adjudicate.py`, `tests/test_manifest_chain.py`, extensions to `tests/test_apply.py`, `tests/test_resume.py`, `tests/test_restore.py`, `tests/test_cli_apply.py`, `tests/test_cli_restore.py`, `tests/test_cli_scan.py`, `tests/test_cli_plan.py`.

---

### Task 1: `lineage.py` wire primitives + header model + header schema (additive, green)

**Files:**

- Create: `src/docmend/lineage.py`
- Create: `src/docmend/schemas/manifest-header.schema.json`
- Create: `tests/test_lineage_imports.py`
- Modify: `src/docmend/writer/manifest.py` (add `ManifestHeader`; nothing else changes yet)
- Modify: `src/docmend/artifacts.py:45-53` (`ArtifactKind` + `ARTIFACT_KINDS` gain `"manifest-header"`)
- Test: `tests/unit/writer/test_manifest.py`, `tests/test_schemas.py`

**Interfaces:**

- Produces (in `docmend.lineage`): `ObjectIdentity(dev: int, ino: int)`; `PriorAttempt(run_id: RunId, report_sha256: Sha256 | None, manifest_sha256: Sha256 | None)` with exactly one sha set.
- Produces (in `docmend.writer.manifest`): `ManifestHeader(schema_kind="docmend/manifest-header", schema_version="2.0", run_id, kind: Literal["apply","restore"], source_root: str, backup_root: str | None, plan_sha256: Sha256, prior_manifest_sha256: Sha256 | None, prior_attempt: PriorAttempt | None, created_at: str)`. `MANIFEST_SCHEMA_VERSION` stays `"1.3"` until Task 2 flips it — this task is purely additive so the gate stays green.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lineage_imports.py
"""CR-001 regression: the shared wire types must be importable from every
consumer module in a clean process — the review found two would-be cycles
(manifest→atomic and manifest→artifacts→report)."""

import subprocess
import sys


def test_wire_type_consumers__import_in_clean_process() -> None:
    code = (
        "import docmend.lineage, docmend.report, docmend.artifacts, "
        "docmend.writer.atomic, docmend.writer.manifest"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
```

```python
# tests/unit/writer/test_manifest.py
class TestManifestHeader:
    def test_header__validates_and_serializes_by_alias(self) -> None:
        header = ManifestHeader(
            run_id=RUN, kind="apply", source_root="/lib", backup_root="/bak",
            plan_sha256=SHA_A, prior_manifest_sha256=None, prior_attempt=None,
            created_at="2026-07-10T00:00:00+00:00",
        )
        doc = header.model_dump(mode="json")
        assert doc["schema"] == "docmend/manifest-header"
        assert doc["schema_version"] == "2.0"
        validate_artifact("manifest-header", doc)

    def test_prior_attempt__requires_exactly_one_sha(self) -> None:
        with pytest.raises(ValidationError):
            PriorAttempt(run_id=RUN, report_sha256=None, manifest_sha256=None)
        with pytest.raises(ValidationError):
            PriorAttempt(run_id=RUN, report_sha256=SHA_A, manifest_sha256=SHA_B)
        PriorAttempt(run_id=RUN, report_sha256=SHA_A, manifest_sha256=None)  # legal
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_lineage_imports.py tests/unit/writer/test_manifest.py -q`; expected: ModuleNotFoundError/ImportError on the new names.

- [ ] **Step 3: Implement**

```python
# src/docmend/lineage.py
"""Shared recovery-lineage wire primitives (adr-0019).

Dependency-neutral BY CONTRACT (plan-review CR-001): this module may import
only stdlib, pydantic, and docmend.inventory's aliases — writer/atomic.py,
writer/manifest.py, and report.py all consume it, and any heavier import
here re-creates the cycles the review found.
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from docmend.inventory import RunId, Sha256


class ObjectIdentity(BaseModel):
    """Exact (st_dev, st_ino) pair — the adjudication predicates' currency
    (design F4 rounds 3-4). Device mismatch refuses, never substitutes."""

    model_config = ConfigDict(extra="forbid", strict=True)
    dev: Annotated[int, Field(ge=0)]
    ino: Annotated[int, Field(ge=0)]


class PriorAttempt(BaseModel):
    """Discriminated attempt-lineage edge (design F6 rounds 4-5): the
    predecessor's run_id plus EITHER its report sha256 OR — when that report
    was never published — its closed-manifest sha256."""

    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: RunId
    report_sha256: Sha256 | None
    manifest_sha256: Sha256 | None

    @model_validator(mode="after")
    def _exactly_one_sha(self) -> Self:
        if (self.report_sha256 is None) == (self.manifest_sha256 is None):
            msg = "prior_attempt carries exactly one of report_sha256 or manifest_sha256"
            raise ValueError(msg)
        return self
```

`ManifestHeader` lands in `writer/manifest.py` importing `PriorAttempt` from `docmend.lineage` (model body as in the Interfaces block; `extra="forbid"`, `strict=True`, `populate_by_name=True`, `serialize_by_alias=True`, `schema` alias). The header schema JSON mirrors the record schema's style: `additionalProperties: false`, all fields required, `schema` const `docmend/manifest-header`, `schema_version` pattern `^2\.[0-9]+$`, `prior_attempt` as `oneOf [null, object]` with the one-sha constraint as two `oneOf` arms; `run_id`/`sha256` `$defs` copied inline.

- [ ] **Step 4: Run the FULL gate** — `uv run python scripts/check.py`; expected: pass (everything is additive).
- [ ] **Step 5: Commit** — `git add src/docmend/lineage.py src/docmend/writer/manifest.py src/docmend/schemas/manifest-header.schema.json src/docmend/artifacts.py tests/test_lineage_imports.py tests/unit/writer/test_manifest.py && git commit -m "feat(lineage): neutral wire primitives + manifest 2.0 header model (DMR-03/04)"`

### Task 2: The format-break slice — record 2.0, header-first writer, validated set reader, all consumers (green)

This is the one unavoidable large slice (CR-003): flipping the record schema to 2.0 breaks every producer, reader, and fixture at once, so they change in one commit that ends green.

**Files:**

- Modify: `src/docmend/writer/manifest.py` (record 2.0, `ManifestWriter(header=…)`, `manifest_sha256`, `read_manifest_set` + `ManifestSet` + `ManifestContainmentError`; DELETE `read_manifest`)
- Modify: `src/docmend/schemas/manifest.schema.json` (2.0)
- Modify: `src/docmend/writer/apply.py` (`_record`/`_record_intent` constructor fields; `execute_plan` builds the header — lineage params arrive in Task 6, here it uses `plan_sha256="sha256:" + "0"*64` placeholders NOWHERE: the CLI already knows the plan path, so thread `plan_sha256: str` and `backup_root_resolved: str | None` through `execute_plan` in THIS slice, with `prior_manifest_sha256=None, prior_attempt=None` until Task 7)
- Modify: `src/docmend/restore.py` (inverse-record `model_copy` drops `source_root`, gains nulls; `run_restore` builds a restore-kind header from the records' set — full rewrite is Task 10, this is the mechanical compile-and-pass update)
- Modify: `src/docmend/cli.py` (ALL THREE `read_manifest` call sites — `_read_resume_records` ~`:698`, restore ~`:781`, and the VERIFY command ~`:916` — switch to `read_manifest_set` (verify passes `check_backup_objects=False`); clean-break message surfaces as exit 2)
- Create: `tests/helpers/manifest2.py` (header/record/set fixture builder used by every manifest test)
- Test: `tests/unit/writer/test_manifest.py`, plus mechanical fixture updates across EVERY current `read_manifest`/manifest-shape consumer (round-2 CR-003 inventory): `tests/test_restore.py`, `tests/test_resume.py`, `tests/test_apply.py`, `tests/test_cli_resume.py`, `tests/test_idempotency.py`, `tests/test_schemas.py`, `tests/test_cli_apply.py`, `tests/test_cli_restore.py`, `tests/test_cli_verify.py`, `tests/test_restore_drill.py`

**Interfaces:**

- `ManifestRecord` 2.0: loses `source_root`; gains `undoes_action_id: ActionId | None = None`, `undoes_run_id: RunId | None = None` (paired-or-absent validator), `source_identity: ObjectIdentity | None = None`, `target_identity: ObjectIdentity | None = None`, `expected_published_identity: ObjectIdentity | None = None`; `schema_version` pattern `^2\.\d+$`; `MANIFEST_SCHEMA_VERSION = "2.0"`. All five new fields are required members of the JSON schema (writers always emit them, null where absent).
- `ManifestWriter(path, *, header: ManifestHeader, now=…)` — lazy-opens on first `append`, writes the fsync'd header line before the first record (all-skip runs still leave no file); `append` stamps `seq`/`recorded_at` only.
- `manifest_sha256(path: Path) -> str` — `sha256:<hex>` of the closed file's bytes.
- `read_manifest_set(path: Path) -> ManifestSet` where `ManifestSet` carries `header`, `records`, `path`, `sha256: Sha256 | None` (filled by chain reading). Raises `ArtifactError` (exit-2 class) for malformed/lifecycle-invalid input, `ManifestContainmentError(ArtifactError)` (exit-3 class) for containment/trust violations.
- **Per-set validation rules** (design: ManifestSet and chain validation, incl. the complete F5 trust boundary — CR-002):
  1. Line 1 parses as `manifest-header`; a first line whose `schema` is `docmend/manifest-record` (any version) raises the clean-break `ArtifactError` from Global Constraints.
  2. `schema_version` major = 2, minor ≤ current; future minors rejected.
  3. Every record's `run_id` equals the header's; `seq` strictly contiguous from 1; torn-tail rule unchanged (physically unterminated final line drops with a warning).
  4. Lifecycle per action within the set — PROVISIONAL by design (round-2 CR-003/CR-NEW-002): at most one terminal per action; duplicate `applied` illegal; `failed` may stand alone; when an `intent` and a terminal for the same action both appear in this set, immutable-field agreement is required (`action_id, docmend_id, operation, original_path, target_path, before_sha256, after_sha256, backup_path, overwritten_backup_path, overwritten_sha256, source_identity, target_identity, expected_published_identity` — only `result, error, seq, recorded_at` differ). A terminal with NO same-set intent is provisionally legal at set scope: it is either an adjudication terminal closing an earlier set's dangling intent (proven at chain scope, Task 3) or a pre-Task-6 producer's single-record mutation — which is exactly why the format-break slice stays green before journal-every-mutation lands. STRICT intent-before-terminal is a CHAIN rule, not a set rule.
  5. Restore-kind sets require `undoes_*` on every record; apply-kind sets require them null.
  6. Path containment: every `original_path`/`target_path` resolves inside `header.source_root`.
  7. **F5 BackupStore trust boundary (all of it — CR-002):** for every non-null backup reference: (a) it resolves beneath `header.backup_root` (null root with a non-null reference is a violation); (b) it reconstructs EXACTLY from the record's own `(run_id, action_seq, role, relative_path)` key — `source` role from `original_path` relative to `source_root`, `overwritten` role from `target_path`; (c) the referenced object is a REGULAR file; (d) NO component below `backup_root` is a symlink (walk each intermediate with `lstat`); (e) role consistency — `overwritten_backup_path` requires `overwritten_sha256`; (f) at most one path per role per action across the set. (c) and (d) inspect the live filesystem: `read_manifest_set` takes `check_backup_objects: bool = True`; restore/resume call it with the default so every check runs BEFORE `_verified_backup` opens anything; verify (Plan D) passes `False` and re-runs (c)/(d) as findings.

- [ ] **Step 1: Write the failing tests** — the fixture builder plus one test per rule:

```python
# tests/helpers/manifest2.py
"""Manifest 2.0 fixture builder shared by every manifest-consuming test."""

def header_doc(**overrides: object) -> dict[str, object]: ...
def record_doc(seq: int, *, result: str = "applied", **overrides: object) -> dict[str, object]: ...
def write_set(path: Path, header: dict[str, object], *records: dict[str, object]) -> Path: ...
```

```python
@pytest.mark.parametrize(
    ("mutate", "error", "match"),
    [
        (lambda h, rs: rs[0].update(run_id=OTHER_RUN), ArtifactError, "run_id"),
        (lambda h, rs: rs[1].update(seq=5), ArtifactError, "contiguous"),
        (lambda h, rs: h.update(schema_version="2.9"), ArtifactError, "unsupported"),
        (lambda h, rs: rs[1].update(before_sha256=SHA_B), ArtifactError, "immutable"),
        (lambda h, rs: rs[0].update(original_path="/elsewhere/x.md"),
         ManifestContainmentError, "source root"),
        (lambda h, rs: rs[0].update(backup_path="/tmp/evil"),
         ManifestContainmentError, "BackupStore"),
    ],
)
def test_read_manifest_set__rejects(tmp_path, mutate, error, match): ...

# CR-002 adversarial filesystem fixtures — each builds a real backup tree:
def test_backup_trust__symlinked_intermediate_directory_refused(tmp_path): ...
def test_backup_trust__symlink_leaf_refused(tmp_path): ...
def test_backup_trust__fifo_leaf_refused(tmp_path): ...      # os.mkfifo
def test_backup_trust__directory_leaf_refused(tmp_path): ...
def test_backup_trust__duplicate_role_reference_refused(tmp_path): ...
def test_backup_trust__valid_regular_backup_accepted(tmp_path): ...

def test_read_manifest_set__1x_first_line_gets_clean_break_message(tmp_path):
    path = tmp_path / "m.jsonl"
    path.write_text(json.dumps(V1_RECORD) + "\n")
    with pytest.raises(ArtifactError, match=r"docmend 1\.0\.2"):
        read_manifest_set(path)
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/unit/writer/test_manifest.py -q`.
- [ ] **Step 3: Implement** — model/schema/writer changes, then `read_manifest_set` as pure rule passes over `(header, records)` (reused by Task 3 and Plan D) plus the filesystem trust pass; then update every consumer and fixture in the same slice: `apply.py` record constructors gain the identity/undoes nulls and drop nothing else; `execute_plan` gains `plan_sha256`/`backup_root_resolved` params and builds the apply header; `restore.py`'s inverse `model_copy` update drops `source_root` and adds `undoes_action_id=record.action_id, undoes_run_id=record.run_id` (already correct for Task 10); CLI reads via `read_manifest_set` at all three call sites (resume, restore, verify — verify with `check_backup_objects=False`), catches `ManifestContainmentError` → exit 3 before other `ArtifactError` → exit 2; `_restore_lock_root` reads `sets' header.source_root`. The slice ends green precisely because rule 4 is provisional: apply still emits single-terminal records for rewrite/rename until Task 6, and the set reader accepts them.
- [ ] **Step 4: Run the FULL gate** — `uv run python scripts/check.py`; expected: pass with every fixture updated.
- [ ] **Step 5: Commit** — `git add src/docmend/writer/manifest.py src/docmend/schemas/manifest.schema.json src/docmend/writer/apply.py src/docmend/restore.py src/docmend/cli.py tests/helpers/manifest2.py tests/unit/writer/test_manifest.py tests/test_restore.py tests/test_resume.py tests/test_apply.py tests/test_cli_resume.py tests/test_idempotency.py tests/test_schemas.py tests/test_cli_apply.py tests/test_cli_restore.py tests/test_cli_verify.py tests/test_restore_drill.py && git commit -m "feat(manifest)!: 2.0 format break — header-first writer, validated set reader, F5 trust boundary (DMR-03)"`

### Task 3: `read_manifest_chain` — cross-set and attempt-lineage validation (additive, green)

**Files:**

- Modify: `src/docmend/writer/manifest.py`
- Test: `tests/test_manifest_chain.py` (new)

**Interfaces:**

- `class ManifestChain(BaseModel): sets: list[ManifestSet]` ordered root→tip; `read_manifest_chain(paths: Sequence[Path]) -> ManifestChain`. An EMPTY path list returns an empty chain (legal: a report-only predecessor produced no manifest — CR-004).
- Structural rules: hash every file via `manifest_sha256`; exactly one root (`prior_manifest_sha256 is None`); every non-root's `prior_manifest_sha256` equals the ACTUAL hash of exactly one other input file (no forks, no gaps, no self-reference); input order irrelevant; identical `source_root` and `plan_sha256` across the chain; no duplicate `run_id`s; `restore`-kind sets only after all apply-kind sets (apply-after-restore illegal); every restore record's `undoes_action_id` exists as an `applied` action in the chain's apply sets; cross-set lifecycle transition table (`failed → intent → applied` legal; contradictory apply-kind terminal after `applied` illegal; restore transitions only through `undoes` records).
- **Attempt-lineage consistency (CR-006), validated where locally provable:** the ROOT set is the one with `prior_manifest_sha256: null`; its `prior_attempt` is null (a true first attempt) OR report-flavored (its predecessor attempts were report-only and produced no manifest — round-2 CR-004: this shape is LEGAL and is exactly the R1-report-only → R2-first-manifest sequence). A manifest-flavored `prior_attempt` REQUIRES a non-null `prior_manifest_sha256` equal to it (the predecessor's newest manifest is the attempt evidence) with the named `run_id` being that predecessor set's; a report-flavored `prior_attempt` on a non-root set requires `prior_manifest_sha256` to still name the newest earlier manifest (a report-only attempt interleaves without breaking the subchain) — the subchain and attempt chain cannot disagree. Report-hash verification itself (does `report_sha256` match a real report file?) is DEFERRED: apply-resume validates it at edge-build time (Task 9) because it holds the report input; verify (Plan D) validates it chain-wide with report inputs. This deferral is deliberate and stated here so Plan D picks it up.
- **Cross-set terminal closure (round-2 CR-NEW-002):** a terminal record with no same-set intent must close EXACTLY ONE dangling intent for the same `action_id` from an earlier set, with full immutable-field agreement against that intent; a standalone terminal that closes nothing is illegal at chain scope. A chain consisting only of such a set (nothing to close) is rejected. This is the wire rule that makes Task 7's adjudication terminals and Task 4's M4 worked-example records readable: provisionally legal per set, proven at chain scope.

- [ ] **Step 1: Failing tests** — shuffled three-file chain orders deterministically; forked chain rejected; gap rejected; wrong `prior_manifest_sha256` hash rejected; mixed `plan_sha256` rejected; apply-after-restore rejected; restore record undoing an unknown action rejected; `applied` then contradictory `failed` in a later apply set rejected; root with a REPORT-flavored `prior_attempt` and null `prior_manifest_sha256` ACCEPTED (the report-only-predecessor shape); manifest-flavored `prior_attempt` on a root rejected; `prior_attempt.manifest_sha256` disagreeing with `prior_manifest_sha256` rejected; self-run reference rejected; duplicate `run_id` rejected; a standalone terminal that closes an earlier set's dangling intent ACCEPTED; a standalone terminal closing nothing rejected; a single-set chain containing only a standalone terminal rejected; the same closure pair for a restore inverse terminal; empty input → empty chain.
- [ ] **Step 2: Verify failure** — `uv run pytest tests/test_manifest_chain.py -q`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the FULL gate.**
- [ ] **Step 5: Commit** — `git commit -m "feat(manifest): chain reader — links, coherence, attempt-lineage invariants (DMR-03)"`

### Task 4: `reduce_lifecycle` (additive, green)

**Files:**

- Modify: `src/docmend/writer/manifest.py`
- Test: `tests/test_manifest_chain.py`

**Interfaces:**

- `type LifecycleState = Literal["pending-intent", "applied", "failed", "pending-restore", "restored", "restore-failed"]`; `@dataclass(frozen=True) class ActionLifecycle: state: LifecycleState; record: ManifestRecord; set_index: int`; `reduce_lifecycle(chain: ManifestChain) -> dict[str, ActionLifecycle]` keyed by the ORIGINAL apply `action_id`. Pure fold in chain order then `seq` — never wall-clock; legality was already enforced by Tasks 2/3.

- [ ] **Step 1: Failing test** — the design's worked example: M1 (a1 intent+applied, a2 intent), M2 (a2 intent+applied, a3 intent+applied), M3 (restore: undoes-a3 intent+applied, undoes-a2 intent), M4 (undoes-a2 terminal, undoes-a1 intent+applied) reduces to all-`restored`; `[M1]` → `{a1: applied, a2: pending-intent}`; `[M1, M2, M3]` → a2 `pending-restore`.
- [ ] **Step 2: Verify failure.** → **Step 3: Implement the fold.** → **Step 4: FULL gate.** → **Step 5: Commit** — `git commit -m "feat(manifest): one lifecycle reducer for resume/restore/verify (DMR-04)"`

### Task 5: Staged-write API in `writer/atomic.py` (additive, green)

**Files:**

- Modify: `src/docmend/writer/atomic.py`
- Test: `tests/unit/writer/test_atomic.py`

**Interfaces:**

- `@dataclass(frozen=True) class StagedWrite: tmp: Path; identity: ObjectIdentity` — `ObjectIdentity` imported from `docmend.lineage` (NOT from `writer.manifest` — CR-001); `stage_bytes(target: Path, data: bytes, *, mode: int | None = None) -> StagedWrite` (the existing randomized `O_EXCL` `_write_temp` plus `os.fstat` before close); `publish_staged(staged: StagedWrite, target: Path, *, clobber: bool = True) -> None` (the existing replace/link publish + `fsync_dir`); `abort_staged(staged: StagedWrite) -> None` (unlink `missing_ok=True`). `atomic_write_bytes` refactored to `publish_staged(stage_bytes(...), ...)` with identical behavior and signature.

- [ ] **Step 1: Failing tests** — `stage_bytes` leaves the target untouched and its identity equals `os.stat(staged.tmp)`'s `(st_dev, st_ino)`; after `publish_staged`, `os.stat(target)` has that identity (the inode moved); `abort_staged` removes the temp; all existing `atomic_write_bytes` tests stay green.
- [ ] **Step 2: Verify failure.** → **Step 3: Implement.** → **Step 4: FULL gate.** → **Step 5: Commit** — `git commit -m "feat(atomic): staged-write API exposing pre-publish object identity"`

### Task 6: Apply journals every mutation with identities (green)

**Files:**

- Modify: `src/docmend/writer/apply.py` (`_execute_action`, `_record_intent`, `_record`)
- Test: `tests/test_apply.py`, `tests/test_resume.py`

**Interfaces:**

- For every executed action: `intent` record — `source_identity` from `os.stat(source)` after the FR-003 read, `target_identity` from `os.stat(target)` when clobbering, `expected_published_identity` from the staged inode (rewrite/rename_and_rewrite) or equal to `source_identity` (pure rename) — appended and fsync'd BEFORE the first corpus-name mutation; then the mutation; then the terminal repeating the immutable fields. Pre-mutation failures (`unreadable`, backup errors, staging failure) append `failed` with identities null and no intent.
- Sequencing per kind (the adjudication table's step order): `rewrite`: stage payload → intent → `publish_staged` → terminal. `rename` no-clobber: intent (`expected = source_identity`) → `rename_no_clobber` → terminal. `rename` overwrite: read+backup target → intent (with `target_identity`) → `rename_overwrite` → terminal. `rename_and_rewrite`: stage payload → intent → `publish_staged(target)` → unlink source (existing rollback branch retained) → terminal.
- Identity capture is `os.stat` on pathnames in Plan B; descriptor-bound `O_NOFOLLOW` capture is Plan C's adr-0020 `CommitBoundary`. Plan B owns the persisted evidence model.

- [ ] **Step 1: Failing tests**

```python
# tests/test_apply.py
def test_every_mutation_kind__journals_intent_then_terminal(tmp_path):
    """DMR-04: 2.0 journals EVERY kind, not only rename_and_rewrite."""
    report, manifest_path = apply_over(tmp_path, files={
        "rw.md": b"body\r\n",            # rewrite
        "mv.txt": b"clean\n",            # pure rename
        "both.txt": b"dirty\r\n",        # rename_and_rewrite
    })
    lines = [json.loads(l) for l in manifest_path.read_text().splitlines()]
    assert lines[0]["schema"] == "docmend/manifest-header"
    per_action = group_by_action(lines[1:])
    for records in per_action.values():
        assert [r["result"] for r in records] == ["intent", "applied"]
        intent, terminal = records
        assert intent["source_identity"] is not None
        assert intent["expected_published_identity"] is not None
        for field in IMMUTABLE_FIELDS:
            assert intent[field] == terminal[field]

def test_pre_mutation_failure__failed_record_without_intent(tmp_path): ...

# tests/test_resume.py — kill injection per kind
def test_kill_between_intent_and_rewrite_publish__leaves_dangling_intent(tmp_path): ...
```

- [ ] **Step 2: Verify failure.** → **Step 3: Implement.** → **Step 4: FULL gate.** → **Step 5: Commit** — `git commit -m "feat(apply): journal every mutation — intent with identities, then terminal (DMR-04)"`

### Task 7: Adjudication table + reducer-driven resume (green)

**Files:**

- Create: `src/docmend/writer/adjudicate.py`
- Modify: `src/docmend/writer/apply.py` (`execute_plan` resume block; DELETE `_reconcile_intent` and the `completed`/`dangling_intents` maps), `src/docmend/report.py` (`ApplySkipReason` gains `"external-interference"` — model-only; the schema's skip_reason is free-string)
- Test: `tests/unit/writer/test_adjudicate.py` (new), `tests/test_resume.py`

**Interfaces:**

```python
type AdjudicationVerdict = Literal[
    "never-happened", "completed", "finish-remaining", "external-interference"
]

@dataclass(frozen=True)
class Adjudication:
    verdict: AdjudicationVerdict
    detail: str

def adjudicate_dangling_intent(record: ManifestRecord) -> Adjudication
def finish_remaining(record: ManifestRecord) -> None  # completes residual step(s); raises WriteError
```

- Implements every design-table row for the record's operation — apply rows AND restore-inverse rows (rows dispatch on whether `undoes_action_id` is set). Predicates use recorded hashes AND `lstat` identities: both-names rows require both pathnames to `lstat` to the recorded pre-mutation inode; post-publish rows require the live output to `lstat` to `expected_published_identity`. Any state failing all predicates → `external-interference`; a same-bytes different-inode replacement fails the identity predicate and refuses.
- `execute_plan` signature: `resume_records` becomes `resume_chain: ManifestChain | None`; `reduce_lifecycle(chain)` drives: `applied` → `_reconcile_completed` (unchanged); `pending-intent` → adjudicate: `never-happened` → execute normally; `completed` → append the missing terminal (resuming run's `run_id`) and report `applied`; `finish-remaining` → `finish_remaining` then terminal; `external-interference` → `_skip(action, "external-interference")`. `pending-restore`/`restored`/`restore-failed` states in a resume input are exit-2 input errors (re-application after restore requires a fresh plan — the chain rules already reject the shapes; the reducer states guard the residual). The appended standalone terminals are legal by Task 2's provisional set rule and proven by Task 3's chain-closure rule (CR-NEW-002): they carry the intent's immutable fields verbatim, differing only in `result`/`seq`/`recorded_at` (and the set-scope `run_id`).

- [ ] **Step 1: Failing tests** — `tests/unit/writer/test_adjudicate.py` parametrizes ONE test per apply-kind table row from a named table (`operation, crash_after_step, disk_state_builder, expected_verdict`), each building the exact disk state (both-names-one-inode via `os.link`; overwritten bytes via the fixture backup tree), plus the three apply identity probes (replace source / target / published output with identical bytes under a new inode → `external-interference`). Restore-inverse rows are exercised in Task 10 against the real restore flow; the adjudicator unit rows for them land HERE (the function must already know them — CR-005). `tests/test_resume.py` gains one kill-after-step + resume convergence test per apply row.
- [ ] **Step 2: Verify failure.** → **Step 3: Implement `adjudicate.py`, rewire `execute_plan`.** → **Step 4: FULL gate.** → **Step 5: Commit** — `git commit -m "feat(writer): adjudication table + reducer-driven resume (DMR-04)"`

### Task 8: Report 2.0 — lineage, `not-attempted`, totals (green)

**Files:**

- Modify: `src/docmend/report.py`, `src/docmend/schemas/report.schema.json`, `src/docmend/artifacts.py` (`write_report` totals reconciliation extends to `not_attempted`)
- Modify: `src/docmend/writer/apply.py` (abort accounting)
- Test: `tests/test_apply.py`, the report/schema test homes

**Interfaces:**

- `REPORT_SCHEMA_VERSION = "2.0"`; `OutcomeStatus` gains `"not-attempted"`; `ReportTotals` gains `not_attempted: int`; `Report` gains `prior_attempt: PriorAttempt | None` (imported from `docmend.lineage` — CR-001: report.py must NOT import `writer.manifest`) and `manifest_sha256: Sha256 | None` (null when the run mutated nothing).
- On the `fail`-policy abort, every remaining unexecuted plan action gets `ApplyOutcome(status="not-attempted", before_sha256=action.source_sha256, after_sha256=None, skip_reason=None, error=None)` — the partition invariant: every plan action appears exactly once in the report.
- `manifest_sha256` is stamped by the CLI after `ManifestWriter.close()` (Task 9) via `report.model_copy(update=…)` before `write_report`.

- [ ] **Step 1: Failing tests** — abort mid-plan (collision `fail` on action 2 of 3) yields outcomes `[applied, skipped, not-attempted]` and `totals.not_attempted == 1`; the 2.0 schema validates it and rejects totals omitting `not_attempted`.
- [ ] **Step 2: Verify failure.** → **Step 3: Implement** (`if abort: outcomes.extend(...)` over `plan.actions[len(outcomes):]`). → **Step 4: FULL gate.** → **Step 5: Commit** — `git commit -m "feat(report): 2.0 — attempt lineage, not-attempted partition, totals"`

### Task 9: CLI apply wiring — predecessor-attempt discovery, plan hash, lineage (green)

**Files:**

- Modify: `src/docmend/cli.py` (apply command body; NEW `_load_predecessor_attempt`; `_read_resume_chain`)
- Test: `tests/test_cli_apply.py`

**Interfaces (CR-004/CR-006/CR-NEW-001 — one deterministic attempt graph over ALL predecessor evidence):**

- `--resume-run-id RID` resolves BOTH default sidecars: `.docmend/docmend-RID-manifest.jsonl` AND `.docmend/docmend-RID-report.json`. The manifest feeds the mutation chain; the report feeds the lineage edge. New repeatable `--prior-report PATH` names a relocated or report-only predecessor report. Existing repeatable `--resume-manifest PATH` inputs participate identically (round-2 CR-004: explicit manifests are graph nodes, not a separate world).
- `_load_predecessor_attempt(resume_manifests, resume_run_ids, prior_reports, *, plan_sha256) -> tuple[PriorAttempt | None, str | None]` builds the ATTEMPT GRAPH and returns the tip's lineage edge plus `prior_manifest_sha256`:
  - **Nodes:** one per predecessor run — from each supplied/derived manifest (its header) and each supplied/derived report. When both artifacts of one run are present, their `prior_attempt` and `run_id` must be IDENTICAL (design F6 round 5).
  - **Edges:** every node's `prior_attempt` reference. **Tip selection is graph-derived, never caller-order:** the tip is the unique node no other node references as its predecessor; zero or multiple tips → exit 2 with the ambiguity named.
  - **Report validation at edge-build time (CR-006):** each report must parse as a valid 2.0 report; its `plan_ref.sha256` must equal the current `plan_sha256` (resume executes the same plan); its own `prior_attempt` enters the graph and must be consistent; and — **CR-NEW-001** — its `manifest_sha256` disposition decides its class: `null` AND `totals.applied == 0` → a genuine report-only attempt (no mutation evidence expected); non-null → the matching manifest MUST be among the inputs and hash-match, else exit 2 (`missing mutation evidence: report for run <RID> records a closed manifest that was not supplied`) — a lost manifest is never mistaken for a mutation-free attempt.
  - **Outputs:** `prior_attempt` = the tip's edge (report sha when the tip has a report, else its closed-manifest sha); `prior_manifest_sha256` = the hash of the newest manifest walking the graph back from the tip (None when no predecessor manifest exists). A named predecessor with NEITHER sidecar → exit 2.
- Apply computes `plan_sha256 = f"sha256:{hashlib.sha256(plan_path.read_bytes()).hexdigest()}"`, passes it + `prior_manifest_sha256` + `prior_attempt` + `backup_root` into `execute_plan`; after the run, stamps `manifest_sha256` (null when no manifest was created) and the same `prior_attempt` onto the report — both artifacts carry the identical edge — then writes it inside the lock as today.

- [ ] **Step 1: Failing tests** — a fresh write apply's header carries the plan file's sha256, `prior_attempt: null`; a `--resume-run-id` apply's header carries `prior_manifest_sha256` = predecessor manifest hash and `prior_attempt.report_sha256` = predecessor report hash, with the report repeating the identical edge; a GENUINE report-only predecessor (first-action abort: report has `manifest_sha256: null`, `totals.applied == 0`, no manifest ever existed) → resume succeeds with an empty chain, the new header carrying null `prior_manifest_sha256` + the report-flavored edge (legal root per Task 3); a MISSING-manifest predecessor (report's `manifest_sha256` non-null, manifest deleted) → exit 2 with the missing-mutation-evidence message — these two cases are separate tests (CR-NEW-001); a relocated report via `--prior-report` works; explicit `--resume-manifest` inputs join the same graph; shuffled evidence order yields the same tip (determinism); ambiguous tips (two unreferenced nodes) exit 2; a report whose `plan_ref.sha256` mismatches the current plan exits 2; a predecessor with NEITHER sidecar exits 2; resuming from a 1.x manifest exits 2 with the clean-break message; the composed three-attempt lineage — R1 genuine-report-only → R2 manifest-with-missing-report → R3 success — connects: R3's `prior_attempt` names R2 by manifest hash, R2's header names R1 by report hash (the design's principal interruption shape).
- [ ] **Step 2: Verify failure.** → **Step 3: Implement.** → **Step 4: FULL gate.** → **Step 5: Commit** — `git commit -m "feat(cli): predecessor-attempt discovery — report-only lineage, plan hash (DMR-04)"`

### Task 10: Restore rewrite — chain consumer, journaled inverses, full crash matrix (green)

**Files:**

- Modify: `src/docmend/restore.py`, `src/docmend/cli.py:734-833`
- Test: `tests/test_restore.py`, `tests/test_cli_restore.py`, `tests/test_restore_drill.py`

**Interfaces:**

- `run_restore(chain: ManifestChain, *, run_id, write, only_ids, manifest_out) -> list[RestoreOutcome]`:
  - Preflight: any `pending-restore` state adjudicates first (restore-inverse table rows via Task 7's `adjudicate_dangling_intent`/`finish_remaining`) — convergence instead of the old collision trip; `pending-intent` (apply) states are findings (`skipped`, detail naming the dangling apply intent — adjudicating APPLY intents is resume's job).
  - Replays reducer-state-`applied` actions LIFO by chain position then `seq`; each inverse: verify inputs (existing `_verified_backup`/`_live_matches_after` retained) → append restore-kind `intent` with `undoes_action_id`/`undoes_run_id` and identities (`source_identity` = live target's stat; `expected_published_identity` = the staged original's inode where replacement bytes are written, or the target's identity for the pure-rename relink) → mutate (existing loss-proof ordering retained) → append terminal.
  - Writer header: kind `restore`, `source_root`/`plan_sha256` copied from the chain, **`backup_root: null`** (round-2 CR-NEW-003: the header field means THIS run's tool-backup root, and a restore run takes no backups — its inverse records carry null backup references; the apply sets already anchor every backup restore reads), `prior_manifest_sha256` = tip manifest's hash, `prior_attempt` = the tip attempt's edge (its run_id + manifest hash). A direct header assertion test covers `backup_root: null`.
- CLI: `--manifest`/`--run-id` accept repeats (a full chain; single value = chain of one); lock root = the chain's validated `source_root`; `_restore_lock_root` deleted; `ManifestContainmentError` → exit 3; `--id` selecting zero applied records → `restore: no manifest record matches the requested id(s)` on stderr, exit 1.

- [ ] **Step 1: Failing tests — the complete matrix (CR-005).** One deterministic kill-after-step test per restore adjudication row, parametrized from a named table mirroring the design's rows:

```python
RESTORE_CRASH_MATRIX = [
    # (operation, crash_after, disk_state, expected_verdict, converges_to)
    ("rewrite",            "nothing",       "original-has-after-bytes",              "never-happened",   "restored"),
    ("rewrite",            "inverse-write", "original-has-before-bytes",             "completed",        "restored"),
    ("rename",             "nothing",       "target-only-after-bytes",               "never-happened",   "restored"),
    ("rename",             "relink",        "both-names-one-inode",                  "finish-remaining", "restored"),
    ("rename",             "unlink",        "original-only-after-bytes",             "completed",        "restored"),
    ("rename+clobbered",   "nothing",       "target-applied-original-absent",        "never-happened",   "restored"),
    ("rename+clobbered",   "relink",        "original-relinked-target-applied",      "finish-remaining", "restored"),
    ("rename+clobbered",   "target-write",  "original-applied-target-clobbered",     "completed",        "restored"),
    ("rename_and_rewrite", "nothing",       "original-absent-target-applied",        "never-happened",   "restored"),
    ("rename_and_rewrite", "reinstate",     "original-before-target-applied",        "finish-remaining", "restored"),
    ("rename_and_rewrite", "cleanup",       "original-before-target-clobbered-or-absent", "completed",   "restored"),
]

@pytest.mark.parametrize(("op", "crash", "state", "verdict", "converges"), RESTORE_CRASH_MATRIX)
def test_interrupted_restore__adjudicates_and_converges(tmp_path, op, crash, state, verdict, converges):
    """Design adjudication table, restore-inverse rows: kill exactly after
    `crash`, assert the dangling inverse intent adjudicates to `verdict`, and
    a re-run converges to `converges` with exactly one inverse terminal in
    the union chain."""
```

Plus the restore identity-substitution probes (CR-005): after the kill, replace the restored original / the target with identical bytes under a NEW inode → re-run refuses that action as `external-interference`, corpus untouched. Plus: inverse records carry `undoes_*` and intent→terminal pairs; out-of-root record → exit 3 before any mutation; `--id nonexistent` → exit 1 with the stderr message; the DMR-01 regression drill stays byte-identical end-to-end.

- [ ] **Step 2: Verify failure.** → **Step 3: Implement.** → **Step 4: FULL gate.** → **Step 5: Commit** — `git commit -m "feat(restore): chain-validated, journaled, convergent restore (DMR-03/04)"`

### Task 11: Timeout skips exit 1 on scan and plan (green)

**Files:**

- Modify: `src/docmend/cli.py` (scan exit block ~`:228-236`, plan findings sum ~`:371-386`)
- Test: `tests/test_cli_scan.py`, `tests/test_cli_plan.py`

- [ ] **Step 1: Failing tests** — a scan/plan over a tree with one watchdog-timeout file (monkeypatched) prints the partial summary and exits 1.
- [ ] **Step 2: Verify failure.** → **Step 3: Implement** (add `reasons.get("timeout", 0)` to both sums). → **Step 4: FULL gate.** → **Step 5: Commit** — `git commit -m "fix(cli): timeout skips are partial results — scan/plan exit 1"`

### Task 12: Scale-test manifest-shape assertions (mechanical, DMR-08 escrow)

**Files:**

- Modify: `tests/test_scale.py:184-190`

- [ ] **Step 1: Update the assertion** — manifest lines = 1 header + 2 × applied (intent + terminal per action):

```python
with manifest_path.open(encoding="utf-8") as fh:
    line_count = sum(1 for _ in fh)
assert line_count == 1 + 2 * report.totals.applied
```

- [ ] **Step 2: FULL gate** (the opt-in test skips; the shape change is exercised by the Task 6 tests). If the environment allows, a reduced `DOCMEND_SCALE=1` smoke with a locally lowered file count (never committed).
- [ ] **Step 3: Commit** — `git commit -m "test(scale): manifest 2.0 shape — header + intent/terminal pairs (DMR-08 escrow)"`

### Task 13: Changelog, docs, and traceability closure

**Files:**

- Modify: `CHANGELOG.md` (`[Unreleased]`: manifest 2.0 clean break, journal-every-mutation, chain/attempt lineage, restore convergence, report 2.0, timeout exits, restore selector exit)
- Modify: `docs/handoff/*` per the session-end ritual; `docs/TODO.md` Plan B checkbox

- [ ] **Step 1: Write the changelog entries.**
- [ ] **Step 2: FULL gate + `npx prettier --check .` + `npx markdownlint-cli2 "**/\*.md"`+`uv run python scripts/check_traceability.py` + the pinned Project Standards spec validation.\*\*
- [ ] **Step 3: Commit** — `git commit -m "docs(changelog): safety-core plan B — manifest 2.0 (DMR-03/04 closures)"`

---

## Self-Review Notes

- **Review closure mapping (rounds 1–2):** CR-001 → `lineage.py` + `tests/test_lineage_imports.py` (Tasks 1, 5, 8 import from it); CR-002 → Task 2 rule 7 with the six adversarial filesystem fixtures; CR-003 → the green-slice constraint, the complete consumer inventory in Task 2 (verify path + the three test files round 2 found missing), and the PROVISIONAL set rule that keeps pre-Task-6 producers readable; CR-004 → Task 3's report-flavored-root legality + Task 9's attempt graph over manifests/run-ids/reports with graph-derived tip selection; CR-005 → Task 10's `RESTORE_CRASH_MATRIX` + restore identity probes, adjudicator restore rows unit-tested in Task 7; CR-006 → Task 3's lineage invariants + Task 9's edge-build report validation (`plan_ref` binding, `manifest_sha256` reconciliation, report `prior_attempt` graph consistency), with only genuine Plan-D checks deferred; CR-007 → adr-0019 in Global Constraints; CR-NEW-001 → Task 9's report-only vs missing-manifest distinction (`manifest_sha256: null` + zero applied required for an empty chain); CR-NEW-002 → Task 2 provisional terminals + Task 3 chain-closure rule with isolated-set rejection tests; CR-NEW-003 → Task 10 restore header `backup_root: null` + direct assertion; CR-NEW-004 → the review artifact is tracked in this correction commit.
- **Spec coverage:** wire model (Tasks 1–2), set/chain validation (2–3), reducer (4), staged identity (5), journal-every-mutation (6), adjudication + resume (7), report lineage + partition (8), CLI lineage discovery (9), restore (10), coupled mediums (10–11), scale escrow (12). CommitBoundary descriptor binding, `WriteSafetyContext`, `collision-unpreserved`, and verify consumption remain Plans C/D by the approved decomposition.
- **Type consistency check:** `ObjectIdentity`/`PriorAttempt` always from `docmend.lineage`; `ManifestHeader`/`ManifestSet`/`ManifestChain`/`read_manifest_set`/`read_manifest_chain`/`reduce_lifecycle`/`manifest_sha256`/`ManifestContainmentError` from `docmend.writer.manifest`; `stage_bytes`/`publish_staged`/`abort_staged`/`StagedWrite` from `docmend.writer.atomic`; `Adjudication`/`adjudicate_dangling_intent`/`finish_remaining` from `docmend.writer.adjudicate` — used identically across tasks.
- **Restore header `backup_root`:** `null` (round-2 CR-NEW-003). The round-1 rationale ("the root the set's backup references resolve under") was wrong on its own terms: restore inverse records carry NULL backup references, so a restore set's F5 pass never consults the field — the design's per-run meaning (this run's tool-backup root, null when the run took none) is the only consistent reading.
