# Safety-Core Plan B — Manifest 2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the manifest 2.0 recovery model from the approved [safety-core design](../specs/2026-07-10-safety-core-remediation-design.md): header/chain/attempt lineage, journal-every-mutation with durable object identities, ManifestSet/chain validation, one lifecycle reducer with the dangling-intent adjudication table, and the resume/restore rewrite — closing DMR-03 and DMR-04.

**Architecture:** Clean-break rewrite of `writer/manifest.py` into a validated header+records wire model with chain links; a new `writer/adjudicate.py` holding the design's adjudication table; `writer/apply.py` journals intent→mutate→terminal for every mutation kind with identities captured via a new staged-write API in `writer/atomic.py`; `restore.py` becomes a chain consumer that journals its inverses; resume, restore (and later verify, Plan D) all consume one `reduce_lifecycle`. Report schema bumps to 2.0 for attempt lineage and `not-attempted`.

**Tech Stack:** Python 3.14, Pydantic v2 strict models, jsonschema Draft 2020-12, pytest (+ the `test_resume.py` deterministic fault-injection pattern), uv/Ruff/BasedPyright per the standard gate.

## Global Constraints

- Binding spec: SPEC-VHHB rev 0.27 with ADRs 0019–0021; adr-0006 is superseded by the manifest 2.0 recovery ADR (adr-0020).
- Clean break: no 1.x manifest read path. A 1.x manifest is rejected with: `this manifest was written by docmend 1.x; restore pre-2.0 runs with docmend 1.0.2` (exit 2, ERR-008).
- Schema versions: manifest header + record `2.0`; report `2.0`; plan and inventory unchanged.
- Exit taxonomy (adr-0012, unchanged codes): malformed/lifecycle-invalid manifest = exit 2; containment violation in restore/resume = exit 3; per-action interference = skip counting toward exit 1.
- Identity comparison is exact `(st_dev, st_ino)` equality; device mismatch refuses as `external-interference`, never substitutes.
- Every mutation kind (rewrite, rename, rename_and_rewrite, each restore inverse) appends a fsync'd `intent` before any corpus name is touched and a terminal after. Pre-mutation failures append `failed` with no intent.
- The staging write precedes the intent (it creates only a tool-owned `O_EXCL` temp, never a corpus name) so `expected_published_identity` is knowable pre-mutation.
- Gate: `uv run python scripts/check.py` must pass (Ruff format+lint, BasedPyright strict, pytest ≥97% branch coverage, pip-audit) before every commit.
- New skip reason `external-interference`; new report outcome status `not-attempted` (`collision-unpreserved` is Plan C).
- Never `git add .`; add files by name.

## File Structure

- `src/docmend/writer/manifest.py` — rewritten: `ObjectIdentity`, `PriorAttempt`, `ManifestHeader`, `ManifestRecord` 2.0, `ManifestWriter` (header-first), `ManifestSet`, `ManifestChain`, `read_manifest_set`, `read_manifest_chain`, `reduce_lifecycle`, `manifest_sha256`.
- `src/docmend/writer/adjudicate.py` — new: the dangling-intent adjudication table for apply kinds and restore inverses.
- `src/docmend/writer/atomic.py` — extended: `stage_bytes` / `publish_staged` staged-write API (existing `atomic_write_bytes` refactored on top; behavior unchanged).
- `src/docmend/writer/apply.py` — journal-every-mutation rewrite; resume consumes `reduce_lifecycle` + adjudication; abort emits `not-attempted`.
- `src/docmend/restore.py` — chain consumer; journaled inverses with `undoes_*`; adjudication-based convergence.
- `src/docmend/report.py` + `src/docmend/schemas/report.schema.json` — 2.0: `not-attempted`, `totals.not_attempted`, `prior_attempt`, `manifest_sha256`.
- `src/docmend/schemas/manifest.schema.json` (2.0 record) + new `src/docmend/schemas/manifest-header.schema.json`; `artifacts.ArtifactKind` gains `"manifest-header"`.
- `src/docmend/cli.py` — apply/restore wiring: chain reading, `plan_sha256`, `prior_attempt`, clean-break message, restore selector-miss exit 1, scan/plan timeout exit 1.
- `tests/test_scale.py` — mechanical manifest-shape assertion update.
- Tests: `tests/unit/writer/test_manifest.py` (rewrite), new `tests/unit/writer/test_adjudicate.py`, `tests/test_manifest_chain.py`, extensions to `tests/test_apply.py`, `tests/test_resume.py`, `tests/test_restore.py`, `tests/test_cli_apply.py`, `tests/test_cli_restore.py`, `tests/test_cli_scan.py`, `tests/test_cli_plan.py`.

---

### Task 1: Identity, lineage, and header models + header schema

**Files:**

- Modify: `src/docmend/writer/manifest.py` (add models above `ManifestRecord`)
- Create: `src/docmend/schemas/manifest-header.schema.json`
- Modify: `src/docmend/artifacts.py:45-53` (`ArtifactKind` + `ARTIFACT_KINDS` gain `"manifest-header"`)
- Test: `tests/unit/writer/test_manifest.py`, `tests/test_schemas.py`

**Interfaces:**

- Produces: `ObjectIdentity(dev: int, ino: int)`; `PriorAttempt(run_id: RunId, report_sha256: Sha256 | None, manifest_sha256: Sha256 | None)` (exactly one sha set); `ManifestHeader(schema_kind="docmend/manifest-header", schema_version="2.0", run_id, kind: Literal["apply","restore"], source_root: str, backup_root: str | None, plan_sha256: Sha256, prior_manifest_sha256: Sha256 | None, prior_attempt: PriorAttempt | None, created_at: str)`; constant `MANIFEST_SCHEMA_VERSION = "2.0"`.

- [ ] **Step 1: Write the failing tests**

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

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/unit/writer/test_manifest.py -q`; expected: ImportError/NameError on the new names.

- [ ] **Step 3: Implement the models**

```python
class ObjectIdentity(BaseModel):
    """Exact (st_dev, st_ino) pair — the adjudication predicates' currency
    (design F4 rounds 3-4). Device mismatch refuses, never substitutes."""
    model_config = ConfigDict(extra="forbid", strict=True)
    dev: Annotated[int, Field(ge=0)]
    ino: Annotated[int, Field(ge=0)]


class PriorAttempt(BaseModel):
    """Discriminated attempt-lineage edge (F6 round 4): the predecessor's
    run_id plus EITHER its report sha256 OR its closed-manifest sha256."""
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


class ManifestHeader(BaseModel):
    """Line 1 of every 2.0 manifest (design: Manifest 2.0 Wire Model)."""
    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
    )
    schema_kind: Literal["docmend/manifest-header"] = Field(
        default="docmend/manifest-header", alias="schema"
    )
    schema_version: Annotated[str, Field(pattern=r"^2\.\d+$")] = MANIFEST_SCHEMA_VERSION
    run_id: RunId
    kind: Literal["apply", "restore"]
    source_root: Annotated[str, Field(min_length=1)]
    backup_root: str | None
    plan_sha256: Sha256
    prior_manifest_sha256: Sha256 | None
    prior_attempt: PriorAttempt | None
    created_at: str
```

The header schema JSON mirrors the record schema's style: `additionalProperties: false`, all fields required, `schema` const `docmend/manifest-header`, `schema_version` pattern `^2\.[0-9]+$`, `prior_attempt` as `oneOf [null, object]` with the one-sha constraint expressed as two `oneOf` arms (`report_sha256` string + `manifest_sha256` null, and the mirror). Reuse the `run_id`/`sha256` `$defs` from `manifest.schema.json` inline.

- [ ] **Step 4: Run to verify pass** — same command; also `uv run pytest tests/test_schemas.py -q` (the schema-file conventions test must see the new file declare `schema`/`schema_version`).

- [ ] **Step 5: Commit** — `git add src/docmend/writer/manifest.py src/docmend/schemas/manifest-header.schema.json src/docmend/artifacts.py tests/unit/writer/test_manifest.py && git commit -m "feat(manifest): 2.0 header, identity, and attempt-lineage models (DMR-03/04)"`

### Task 2: ManifestRecord 2.0 + record schema 2.0

**Files:**

- Modify: `src/docmend/writer/manifest.py:37-76` (`ManifestRecord`)
- Modify: `src/docmend/schemas/manifest.schema.json` (version pattern `^2\.[0-9]+$`; drop `source_root`; add the new fields)
- Test: `tests/unit/writer/test_manifest.py`

**Interfaces:**

- Produces: `ManifestRecord` gains `undoes_action_id: ActionId | None = None`, `undoes_run_id: RunId | None = None`, `source_identity: ObjectIdentity | None = None`, `target_identity: ObjectIdentity | None = None`, `expected_published_identity: ObjectIdentity | None = None`; loses `source_root`; `schema_version` pattern becomes `^2\.\d+$`. `result` stays `Literal["applied", "failed", "intent"]` — 2.0 uses `intent` for every kind.

- [ ] **Step 1: Write the failing tests** — a 2.0 record with identities round-trips through `validate_artifact("manifest", …)`; a record carrying `source_root` is rejected (`extra="forbid"`); an apply record with `undoes_action_id` set but `undoes_run_id` null is rejected (paired-or-absent model validator).

```python
def test_record__undoes_fields_paired_or_absent(self) -> None:
    with pytest.raises(ValidationError):
        make_record(undoes_action_id=f"{RUN}/a1", undoes_run_id=None)
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** — field changes as above plus:

```python
    @model_validator(mode="after")
    def _undoes_paired(self) -> Self:
        if (self.undoes_action_id is None) != (self.undoes_run_id is None):
            msg = "undoes_action_id and undoes_run_id are set together or not at all"
            raise ValueError(msg)
        return self
```

Schema: `source_identity`/`target_identity`/`expected_published_identity` as `oneOf [null, {dev: integer≥0, ino: integer≥0, additionalProperties: false, required both}]`; `undoes_action_id` nullable action-id pattern; `undoes_run_id` nullable `$defs/run_id`. All five new fields are required members (2.0 is a clean break; writers always emit them, null where absent).

- [ ] **Step 4: Run to verify pass.** Expect collateral failures in old-model consumers (`apply.py`, `restore.py`, fixtures) — fix compile-level breakage only (constructor calls gain `…=None` defaults automatically; delete `source_root=` stampings in `ManifestWriter` temporarily by leaving Task 3 to own it). The full suite need not be green until Task 3; run only `tests/unit/writer/test_manifest.py` here.
- [ ] **Step 5: Commit** — `git commit -m "feat(manifest): record 2.0 — identities, undoes lineage, header-owned root"`

### Task 3: ManifestWriter 2.0 (header-first) + `manifest_sha256`

**Files:**

- Modify: `src/docmend/writer/manifest.py:78-139`
- Test: `tests/unit/writer/test_manifest.py`

**Interfaces:**

- Produces: `ManifestWriter(path, *, header: ManifestHeader, now=…)` — lazy-opens on first `append` and writes the fsync'd header line before the first record (all-skip runs still leave no file); `append(record) -> ManifestRecord` stamps `seq`/`recorded_at` only (no `source_root`); `close()`; `manifest_sha256(path: Path) -> str` returning `sha256:<hex>` of the closed file's bytes.
- Consumes: Task 1 `ManifestHeader`.

- [ ] **Step 1: Failing tests** — writer emits header as line 1 validating against `manifest-header`; `seq` starts at 1 on line 2; no file when nothing appended; `manifest_sha256` matches `hashlib.sha256(path.read_bytes())`.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** — replace `run_id`/`source_root` ctor params with `header`; in the lazy-open branch, after `fsync_dir`, serialize the header (`validate_artifact("manifest-header", …)`, write, flush, fsync) before the first record write. `_run_id` for stamping comes from `header.run_id`.
- [ ] **Step 4: Verify pass**, then update every `ManifestWriter(...)` construction site (`apply.py:640`, `restore.py:129`, test fixtures) to pass a header so the tree compiles; run `uv run pytest tests/unit/writer -q`.
- [ ] **Step 5: Commit** — `git commit -m "feat(manifest): header-first writer + manifest_sha256 chain hashing"`

### Task 4: `read_manifest_set` — per-set validation

**Files:**

- Modify: `src/docmend/writer/manifest.py:142-171` (replace `read_manifest`)
- Test: `tests/unit/writer/test_manifest.py`

**Interfaces:**

- Produces: `class ManifestSet(BaseModel): header: ManifestHeader; records: list[ManifestRecord]; path: Path; sha256: Sha256 | None` (`sha256` filled by chain reading, null for the open tip); `read_manifest_set(path: Path) -> ManifestSet` raising `ArtifactError` (exit-2 class) for malformed/lifecycle-invalid input and `ManifestContainmentError(ArtifactError)` (exit-3 class) for containment violations.
- Validation rules (design: ManifestSet and chain validation): header is line 1 and parses as `manifest-header` — a first line parsing as a 1.x record raises the clean-break message from Global Constraints; `schema_version` major must be 2 and minor ≤ `MANIFEST_SCHEMA_VERSION`'s; every record's `run_id` equals the header's; `seq` strictly contiguous from 1; torn-tail rule unchanged (physically unterminated final line drops with a warning); per-action lifecycle: at most one terminal, `applied` requires a preceding `intent` in this set OR the record is an adjudication terminal (its `seq` follows a dangling predecessor — cross-set legality is Task 5's), `failed` may stand alone, duplicate `applied` illegal, intent/terminal immutable-field agreement (`action_id, docmend_id, operation, original_path, target_path, before_sha256, after_sha256, backup_path, overwritten_backup_path, overwritten_sha256, source_identity, target_identity, expected_published_identity` — only `result, error, seq, recorded_at` may differ); restore-kind sets require `undoes_*` on every record, apply-kind sets require them null; containment: every `original_path`/`target_path` resolves inside `header.source_root`; every non-null backup path reconstructs exactly from `(backup_root, run_id, action_seq, role, relative_path)` — `source` role uses `original_path` relative to root, `overwritten` uses `target_path` — with role consistency (`overwritten_backup_path` requires `overwritten_sha256`).

- [ ] **Step 1: Failing tests** — one test per rule via an adversarial-fixture builder:

```python
def _set_lines(header: dict[str, object], *records: dict[str, object]) -> str:
    return "\n".join(json.dumps(d) for d in (header, *records)) + "\n"

@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda h, rs: rs[0].update(run_id=OTHER_RUN), "run_id"),
        (lambda h, rs: rs[1].update(seq=5), "contiguous"),
        (lambda h, rs: h.update(schema_version="2.9"), "unsupported"),
        (lambda h, rs: rs[0].update(original_path="/elsewhere/x.md"), "source root"),
        (lambda h, rs: rs[0].update(backup_path="/tmp/evil"), "BackupStore key"),
        (lambda h, rs: rs[1].update(before_sha256=SHA_B), "immutable"),
    ],
)
def test_read_manifest_set__rejects(self, tmp_path, mutation, match): ...

def test_read_manifest_set__1x_first_line_gets_clean_break_message(self, tmp_path):
    path = tmp_path / "m.jsonl"
    path.write_text(json.dumps(V1_RECORD) + "\n")
    with pytest.raises(ArtifactError, match=r"docmend 1\.0\.2"):
        read_manifest_set(path)
```

- [ ] **Step 2: Verify failure.** — `uv run pytest tests/unit/writer/test_manifest.py -q`
- [ ] **Step 3: Implement** — parse line 1: if its `schema` member is `docmend/manifest-record` (any version) raise the clean-break `ArtifactError`; else validate as header. Then per-line record validation (existing torn-tail logic retained), then the rule passes above as pure functions over `(header, records)` so Task 5 and verify (Plan D) reuse them. Delete `read_manifest`; update `cli.py` call sites to `read_manifest_set` mechanically (restore/`_read_resume_records` are properly rewired in Tasks 9/12 — here they may read `.records` to stay compiling).
- [ ] **Step 4: Verify pass** — unit file green; full suite may hold known-red CLI tests only if any fixture wrote 1.x manifests; update those fixtures to 2.0 via a shared `tests/helpers/manifest2.py` builder created here.
- [ ] **Step 5: Commit** — `git commit -m "feat(manifest): validated ManifestSet reader with clean-break 1.x rejection (DMR-03)"`

### Task 5: `read_manifest_chain` — cross-set validation

**Files:**

- Modify: `src/docmend/writer/manifest.py`
- Test: `tests/test_manifest_chain.py` (new)

**Interfaces:**

- Produces: `class ManifestChain(BaseModel): sets: list[ManifestSet]` ordered root→tip; `read_manifest_chain(paths: Sequence[Path]) -> ManifestChain`.
- Rules: each non-tip file's sha256 (via `manifest_sha256`) must be referenced by exactly one successor's `prior_manifest_sha256` — exactly one root (`prior_manifest_sha256 is None`), no forks, no gaps, input order irrelevant; identical `source_root` and `plan_sha256` across the chain; `restore` kind only at/after the tip of apply kinds — an apply-kind set after a restore-kind set is illegal; every restore record's `undoes_action_id` exists as an `applied` action in the chain's apply sets; cross-set lifecycle transition table: `failed → intent → applied` legal; contradictory apply-kind terminal after `applied` illegal; `prior_attempt` chain consistency — each set's `prior_attempt.run_id` must be the preceding set's `run_id` when a predecessor exists.

- [ ] **Step 1: Failing tests** — shuffled three-file chain orders deterministically; forked chain (two files naming the same prior) rejected; gap rejected; mixed `plan_sha256` rejected; apply-after-restore rejected; restore record undoing an unknown action rejected; `applied` in set 1 followed by `failed` for the same action in set 2 rejected.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** — hash every input file, build the `prior → set` map, walk from the root, then run the cross-set rule passes.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(manifest): chain reader — links, coherence, cross-set lifecycle (DMR-03)"`

### Task 6: `reduce_lifecycle`

**Files:**

- Modify: `src/docmend/writer/manifest.py`
- Test: `tests/test_manifest_chain.py`

**Interfaces:**

- Produces: `type LifecycleState = Literal["pending-intent", "applied", "failed", "pending-restore", "restored", "restore-failed"]`; `@dataclass(frozen=True) class ActionLifecycle: state: LifecycleState; record: ManifestRecord; set_index: int`; `reduce_lifecycle(chain: ManifestChain) -> dict[str, ActionLifecycle]` keyed by the ORIGINAL apply `action_id`.
- Fold rule (design): records in chain order then `seq` — never wall-clock. Apply-kind `intent` → `pending-intent`; apply terminal → `applied`/`failed`; restore-kind `intent` (via `undoes_action_id`) → `pending-restore`; restore terminal → `restored`/`restore-failed`. A later legal record supersedes the state; the transition table was already enforced by Tasks 4/5, so the reducer is a pure fold.

- [ ] **Step 1: Failing test** — the design's worked example: M1 (a1 intent+applied, a2 intent), M2 (a2 intent+applied, a3 intent+applied), M3 (restore: undoes-a3 intent+applied, undoes-a2 intent), M4 (undoes-a2 terminal, undoes-a1 intent+applied) reduces to `{a1: restored, a2: restored, a3: restored}`; truncate to `[M1]` → `{a1: applied, a2: pending-intent}`; `[M1, M2, M3]` → a2 `pending-restore`.
- [ ] **Step 2: Verify failure.** — `uv run pytest tests/test_manifest_chain.py -q`
- [ ] **Step 3: Implement the fold.**
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(manifest): one lifecycle reducer for resume/restore/verify (DMR-04)"`

### Task 7: Staged-write API in `writer/atomic.py`

**Files:**

- Modify: `src/docmend/writer/atomic.py`
- Test: `tests/unit/writer/test_atomic.py`

**Interfaces:**

- Produces: `@dataclass(frozen=True) class StagedWrite: tmp: Path; identity: ObjectIdentity` (import `ObjectIdentity` from `docmend.writer.manifest`); `stage_bytes(target: Path, data: bytes, *, mode: int | None = None) -> StagedWrite` — the existing randomized `O_EXCL` `_write_temp` plus `os.fstat` before close, returning the staged inode's identity; `publish_staged(staged: StagedWrite, target: Path, *, clobber: bool = True) -> None` — the existing replace/link publish + `fsync_dir`; `abort_staged(staged: StagedWrite) -> None` — unlink `missing_ok=True`. `atomic_write_bytes` is refactored to `publish_staged(stage_bytes(...), ...)` with identical behavior and signature.

- [ ] **Step 1: Failing tests** — `stage_bytes` leaves the target untouched and its returned identity equals `os.stat(staged.tmp)`'s `(st_dev, st_ino)`; after `publish_staged`, `os.stat(target)` has that same identity (the inode moved); `abort_staged` removes the temp; existing `atomic_write_bytes` tests stay green (behavioral refactor).
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Verify pass** — `uv run pytest tests/unit/writer/test_atomic.py -q`.
- [ ] **Step 5: Commit** — `git commit -m "feat(atomic): staged-write API exposing pre-publish object identity"`

### Task 8: Apply journals every mutation with identities

**Files:**

- Modify: `src/docmend/writer/apply.py` (`_execute_action`, `_record_intent`, `_record`, `execute_plan` manifest construction)
- Test: `tests/test_apply.py`, `tests/test_resume.py` (fault injection)

**Interfaces:**

- Consumes: Task 3 writer (header), Task 7 staged writes.
- Produces: for every executed action — `intent` record (with `source_identity` from `os.stat(source)` after the FR-003 read, `target_identity` from `os.stat(target)` when clobbering, `expected_published_identity` from the staged inode for rewrite/rename_and_rewrite or equal to `source_identity` for pure rename) appended and fsync'd BEFORE the first corpus-name mutation, then the mutation, then the terminal `applied`/`failed` record repeating the immutable fields. Pre-mutation failures (`unreadable`, backup errors, staging failure) append `failed` with identities null and no intent. `execute_plan` gains `plan_sha256: str`, `backup_root_resolved: str | None`, `prior_manifest_sha256: str | None`, `prior_attempt: PriorAttempt | None` parameters and builds the `ManifestHeader` (kind `apply`).
- Sequencing per kind (design adjudication table's step order):
  - `rewrite`: stage payload → intent(identities) → `publish_staged` → terminal.
  - `rename` no-clobber: intent (`expected_published_identity = source_identity`) → `rename_no_clobber` (link, unlink) → terminal.
  - `rename` overwrite: read+backup target → intent (with `target_identity`) → `rename_overwrite` → terminal.
  - `rename_and_rewrite`: stage payload → intent → `publish_staged(target)` → unlink source (existing rollback branch retained) → terminal.

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

# tests/test_resume.py — extend the existing kill-injection pattern
def test_kill_between_intent_and_rewrite_publish__leaves_dangling_intent(tmp_path):
    """Fault injection: monkeypatch publish_staged to raise KillSignal after
    the intent fsync; the manifest tail must be a dangling intent whose
    expected_published_identity matches the staged temp's inode."""
```

- [ ] **Step 2: Verify failure.** — `uv run pytest tests/test_apply.py -q`
- [ ] **Step 3: Implement** — restructure `_execute_action` per the sequencing above; `_record_intent` gains the three identity fields and is called for all kinds; `_record` repeats them on the terminal. Identity capture: `st = os.stat(path)` → `ObjectIdentity(dev=st.st_dev, ino=st.st_ino)` (descriptor-bound capture tightens in Plan C; the persisted evidence model is Plan B's contract).
- [ ] **Step 4: Verify pass**, then full gate.
- [ ] **Step 5: Commit** — `git commit -m "feat(apply): journal every mutation — intent with identities, then terminal (DMR-04)"`

### Task 9: Adjudication table + resume rewrite

**Files:**

- Create: `src/docmend/writer/adjudicate.py`
- Modify: `src/docmend/writer/apply.py` (`_reconcile_intent`/`_reconcile_completed`/`execute_plan` resume block), `src/docmend/cli.py:660-712` (`_read_resume_records` → `_read_resume_chain`)
- Test: `tests/unit/writer/test_adjudicate.py` (new), `tests/test_resume.py`

**Interfaces:**

- Produces:

```python
type AdjudicationVerdict = Literal[
    "never-happened", "completed", "finish-remaining", "external-interference"
]

@dataclass(frozen=True)
class Adjudication:
    verdict: AdjudicationVerdict
    detail: str

def adjudicate_dangling_intent(record: ManifestRecord) -> Adjudication
def finish_remaining(record: ManifestRecord) -> None  # completes the residual step(s); raises WriteError
```

- `adjudicate_dangling_intent` implements every design-table row for the record's operation (apply rows here; restore-inverse rows consumed by Task 12): match disk state via recorded hashes AND `lstat` identity predicates — both-names rows require both pathnames to `lstat` to the recorded pre-mutation inode; post-publish rows require the live output to `lstat` to `expected_published_identity`. Any state failing all predicates → `external-interference`. A same-bytes different-inode replacement fails the identity predicate and refuses.
- Resume in `execute_plan`: `resume_records: list[ManifestRecord]` parameter becomes `resume_chain: ManifestChain | None`; the `completed`/`dangling_intents` dicts and `(recorded_at, seq)` sorting are DELETED in favor of `reduce_lifecycle(chain)` — `applied` → `_reconcile_completed` (unchanged read-only check), `pending-intent` → adjudicate: `never-happened` → execute normally; `completed` → append the missing terminal (run_id of the resuming run) and report `applied`; `finish-remaining` → run `finish_remaining` then append terminal; `external-interference` → `_skip(action, "external-interference")`. `ApplySkipReason` in `report.py` gains `"external-interference"` (schema note in Task 10).
- CLI: `_read_resume_chain(resume_manifest, resume_run_id, source_root)` uses `read_manifest_chain`; root mismatch stays exit 2 (ERR-006 posture), containment violations exit 3.

- [ ] **Step 1: Failing tests** — `tests/unit/writer/test_adjudicate.py` parametrizes one test per apply-kind table row (each builds the exact disk state, e.g. both-names-one-inode via `os.link`, then asserts the verdict), plus the three identity probes: replace source/target/published-output with identical bytes under a new inode → `external-interference`. `tests/test_resume.py` gains one kill-after-step + resume test per row asserting convergence and a single terminal in the union chain.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** `adjudicate.py`, then rewire `execute_plan`, then the CLI reader.
- [ ] **Step 4: Verify pass; full gate.**
- [ ] **Step 5: Commit** — `git commit -m "feat(writer): adjudication table + reducer-driven resume (DMR-04)"`

### Task 10: Report 2.0 — lineage, `not-attempted`, totals

**Files:**

- Modify: `src/docmend/report.py`, `src/docmend/schemas/report.schema.json`, `src/docmend/artifacts.py` (`write_report` totals reconciliation extends to `not_attempted`)
- Modify: `src/docmend/writer/apply.py` (`execute_plan` abort accounting + report fields)
- Test: `tests/unit/test_report.py` (or the existing report test home), `tests/test_apply.py`

**Interfaces:**

- Produces: `REPORT_SCHEMA_VERSION = "2.0"`; `OutcomeStatus` gains `"not-attempted"`; `ApplySkipReason` gains `"external-interference"`; `ReportTotals` gains `not_attempted: int`; `Report` gains `prior_attempt: PriorAttempt | None` and `manifest_sha256: Sha256 | None` (null when the run mutated nothing). On the `fail`-policy abort, every remaining unexecuted plan action gets an `ApplyOutcome(status="not-attempted", before_sha256=action.source_sha256, after_sha256=None, skip_reason=None, error=None)` — the partition invariant: every plan action appears exactly once in the report.
- `manifest_sha256` is computed by the CLI after `ManifestWriter.close()` (Task 11) — `execute_plan` returns the report without it and `cli.apply` stamps it via `report.model_copy(update=…)` before `write_report`.

- [ ] **Step 1: Failing tests** — abort mid-plan (collision `fail` policy on action 2 of 3) yields outcomes `[applied, skipped, not-attempted]` and `totals.not_attempted == 1`; schema validates a 2.0 report and rejects totals that omit `not_attempted`.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** — in `execute_plan`, after the loop: `if abort: outcomes.extend(not_attempted_outcome(a) for a in plan.actions[len(outcomes):])`.
- [ ] **Step 4: Verify pass; full gate.**
- [ ] **Step 5: Commit** — `git commit -m "feat(report): 2.0 — attempt lineage, not-attempted partition, totals (DMR-04/05 accounting)"`

### Task 11: CLI apply wiring — plan hash, lineage, chain

**Files:**

- Modify: `src/docmend/cli.py` (apply command body, `_resume_manifest_paths` unchanged, `_read_resume_chain` from Task 9)
- Test: `tests/test_cli_apply.py`

**Interfaces:**

- Consumes: `manifest_sha256`, `PriorAttempt`, `read_manifest_chain`.
- Produces: apply computes `plan_sha256 = f"sha256:{hashlib.sha256(plan_path.read_bytes()).hexdigest()}"`; builds `prior_attempt` from the newest resume predecessor — its report sidecar's sha256 when that file exists, else its closed manifest's sha256; `prior_manifest_sha256` = the tip manifest's sha256; passes all three plus `backup_root` into `execute_plan`; after the run, stamps `manifest_sha256` onto the report (null when no manifest file was created) and writes it inside the lock as today.

- [ ] **Step 1: Failing tests** — a write apply produces a manifest whose header carries the plan file's sha256 and `prior_attempt: null`; a `--resume-run-id` apply's header carries `prior_manifest_sha256` = sha of the predecessor manifest and `prior_attempt.run_id` = predecessor run, and its report repeats the same `prior_attempt`; resuming from a 1.x manifest exits 2 with the clean-break message.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Verify pass; full gate.**
- [ ] **Step 5: Commit** — `git commit -m "feat(cli): apply carries plan hash and attempt lineage into manifest 2.0"`

### Task 12: Restore rewrite — chain consumer, journaled inverses, convergence

**Files:**

- Modify: `src/docmend/restore.py`, `src/docmend/cli.py:734-833` (+ `_restore_lock_root` deleted)
- Test: `tests/test_restore.py`, `tests/test_cli_restore.py`, `tests/test_restore_drill.py`

**Interfaces:**

- Consumes: `read_manifest_chain`, `reduce_lifecycle`, `adjudicate_dangling_intent`/`finish_remaining`, Task 3 writer.
- Produces: `run_restore(chain: ManifestChain, *, run_id, write, only_ids, manifest_out) -> list[RestoreOutcome]`:
  - Preflight: any `pending-restore` state adjudicates first (restore-inverse table rows) — convergence instead of the old collision trip; `pending-intent` states are reported as findings (`skipped`, detail naming the dangling apply intent) — adjudicating APPLY intents is resume's job.
  - Replays reducer state `applied` actions LIFO by chain position then `seq`; each inverse: verify inputs (existing `_verified_backup` / `_live_matches_after` logic retained) → append restore-kind `intent` (with `undoes_action_id`/`undoes_run_id`, identities: `source_identity` = live target's stat, `expected_published_identity` = staged original's inode where bytes are written, or the target identity for pure-rename relink) → mutate (existing loss-proof ordering retained) → append terminal.
  - Writer header: kind `restore`, `source_root`/`plan_sha256` copied from the chain, `prior_manifest_sha256` = tip sha, `backup_root` = chain's.
- CLI: lock root = `Path(chain.sets[0].header.source_root)` (validated identical across the chain — `_restore_lock_root` and the first-record fallback are deleted); `--manifest`/`--run-id` accept repeats to pass a full chain (single value = chain of one after link validation); `ManifestContainmentError` → exit 3; `--id` selecting zero applied records → `restore: no manifest record matches the requested id(s)` on stderr, exit 1.

- [ ] **Step 1: Failing tests** — inverse records carry `undoes_*` and the intent→terminal pair per restoration; an interrupted multi-step inverse (kill injected between relink and target rewrite) converges on re-run via the adjudication row instead of skipping on collision (this is the review's non-convergence reproduction); out-of-root record → exit 3 before any mutation; `--id nonexistent` → exit 1; the DMR-01 regression drill (`tests/test_restore_drill.py`) stays byte-identical end-to-end.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Verify pass; full gate.**
- [ ] **Step 5: Commit** — `git commit -m "feat(restore): chain-validated, journaled, convergent restore (DMR-03/04)"`

### Task 13: Timeout skips exit 1 on scan and plan

**Files:**

- Modify: `src/docmend/cli.py` (scan exit block ~`:228-236`, plan findings sum ~`:371-386`)
- Test: `tests/test_cli_scan.py`, `tests/test_cli_plan.py`

**Interfaces:** scan exits 1 when `totals.skipped_by_reason` contains `timeout` (alongside the existing `unreadable`); plan's findings count adds its timeout skips.

- [ ] **Step 1: Failing tests** — a scan over a tree whose reader watchdog is monkeypatched to time out on one file prints the partial summary and exits 1; same for plan.
- [ ] **Step 2: Verify failure.** → **Step 3: Implement** (add `reasons.get("timeout", 0)` to both sums). → **Step 4: Verify pass.** → **Step 5: Commit** — `git commit -m "fix(cli): timeout skips are partial results — scan/plan exit 1"`

### Task 14: Scale-test manifest-shape assertions (mechanical, DMR-08 escrow)

**Files:**

- Modify: `tests/test_scale.py:184-190`
- Test: the file itself (opt-in)

- [ ] **Step 1: Update the assertion** — manifest lines = 1 header + 2 × applied (intent + terminal per action):

```python
with manifest_path.open(encoding="utf-8") as fh:
    line_count = sum(1 for _ in fh)
assert line_count == 1 + 2 * report.totals.applied
```

- [ ] **Step 2: Run the suite's non-opt-in half** (`uv run pytest tests/test_scale.py -q` — skips cleanly) and, if the environment allows, a reduced `DOCMEND_SCALE=1` smoke with the file count lowered locally (do not commit a lowered count).
- [ ] **Step 3: Commit** — `git commit -m "test(scale): manifest 2.0 shape — header + intent/terminal pairs (DMR-08 escrow)"`

### Task 15: Changelog, docs, and traceability closure

**Files:**

- Modify: `CHANGELOG.md` (`[Unreleased]` gains the Plan B entries: manifest 2.0 clean break, journal-every-mutation, chain lineage, restore convergence, report 2.0, timeout exits, restore selector exit)
- Modify: `docs/handoff/*` per the session-end ritual; `docs/TODO.md` Plan B checkbox
- Verify: `uv run python scripts/check_traceability.py` and `project-standards spec validate` still pass (spec rev 0.26/0.27 already carries the requirement text; this plan implements it)

- [ ] **Step 1: Write the changelog entries.**
- [ ] **Step 2: Run the full gate + markdown lint + spec validation.**
- [ ] **Step 3: Commit** — `git commit -m "docs(changelog): safety-core plan B — manifest 2.0 (DMR-03/04 closures)"`

---

## Self-Review Notes

- **Spec coverage:** design sections Manifest 2.0 Wire Model (Tasks 1–6), Journal every mutation (Task 8), ManifestSet/chain validation (Tasks 4–5), reducer (Task 6), adjudication (Task 9), restore (Task 12), attempt lineage (Tasks 1, 10, 11), coupled mediums timeout/selector (Tasks 12–13), scale-test escrow (Task 14). CommitBoundary descriptor binding, `WriteSafetyContext`, `collision-unpreserved`, and verify consumption are Plans C/D by the approved decomposition and are deliberately absent.
- **Type consistency:** `ObjectIdentity`, `PriorAttempt`, `ManifestHeader`, `ManifestSet`, `ManifestChain`, `reduce_lifecycle`, `manifest_sha256`, `stage_bytes`/`publish_staged`, `Adjudication` names are used identically across Tasks 1–12.
- **Known intentional deviation to flag at review:** Task 8 captures identities via `os.stat` on pathnames; the design's descriptor-bound `O_NOFOLLOW` capture is Plan C's `CommitBoundary`. Plan B owns the _persisted evidence model_; Plan C tightens _how_ the values are captured. If review wants descriptor capture pulled into B, Task 8 absorbs it without wire-model changes.
