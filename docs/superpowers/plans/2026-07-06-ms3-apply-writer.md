# MS-3 Apply / Writer Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land spec §19 MS-3 — the writer layer (atomic writes, backups, manifest, collision policy, safety gate; FR-003–FR-006, FR-011, NFR-002), `docmend apply` with dry-run default and readable report summaries (FR-004, FR-018, IR-005), `docmend restore` with the automated restore-from-manifest drill (IR-008, §18.6), the OQ-027 run-level lock (AW-005), and the two MS-3 inputs filed from the final MS-2 review (inventory detection provenance; artifact path-containment hardening).

**Architecture:** Apply consumes the DR-002 plan (its config snapshot is authoritative for transforms — never the live config), re-verifies each action's source hash (FR-003), recomputes the transform output exactly as planning did, and hands mutation to the isolated writer layer: verify-then-mutate backups (FR-006/ERR-004), atomic same-directory replace (NFR-002, adr-0003), no-clobber renames via `os.link`+`os.unlink`, and one fsync'd NDJSON manifest record per mutation (adr-0005/adr-0006). A pure-predicate safety gate (adr-0004) refuses any writing run whose preservation, containment, backup, manifest, or disk preconditions fail (exit 3). `restore` replays manifest records LIFO per IR-008. A run-level lock (OQ-027) serializes plan/apply/restore against one target tree.

**Tech Stack:** Python 3.14 (uv, Ruff, BasedPyright strict), pydantic v2 strict models, jsonschema Draft 2020-12, typer CLI, structlog, allpairspy (gate pairwise tests). **No new dependencies.**

## Global Constraints

- Spec: `docs/specs/docmend.md` (SPEC-VHHB rev 0.15), Appendix B binding. Re-read §7, §21, Deviations Log each session.
- `docmend.transform` stays pure (import-linter contract unchanged); the writer package may import `os`/`pathlib`/`shutil` freely — it is the one dangerous layer (§8.2.3). `pyfakefs` is **never** used for writer tests — atomic-write/fsync/permission behavior needs the real filesystem (`tmp_path`) per OQ-019/adr-0003.
- Exit-code taxonomy (§18.5, adr-0012): 0 clean, 1 findings, 2 input error (ERR-006/ERR-008, bad flags), 3 safety refusal (gate, lock).
- Dry-run is the default posture; `--write` is the only opt-in; config alone can never enable writes (FR-004, OQ-014, NFR-004).
- The writer refuses to overwrite unless explicitly allowed and writes UTF-8/LF only (§8.5). Written paths stay inside `source_root` (§13.5). Backups live outside the mutation target (OQ-005).
- Artifacts for every run (§8.5): report always; manifest for writing runs; per-run JSONL log always. Defaults per OQ-034: `.docmend/docmend-<run-id>-report.json`, `-manifest.jsonl`.
- Public repo (C-002): all fixtures synthetic — never real library content or paths.
- Verification gate before claiming any task done: `uv run ruff format --check . && uv run ruff check . && uv run basedpyright && uv run coverage run -m pytest && uv run coverage report` (fail_under = 85).
- Workflow: all commits on `dev`; single PR to `main` at the end (adr-0017 — no CI on direct `dev` pushes, so the local gate is mandatory). No `git add .`/`-A` — add files by name.
- Test naming: `test_<subject>__<expectation>`; docstrings cite requirement IDs (the `traceability` CI gate greps IDs under `tests/`).
- Timestamps/run-IDs/clocks are injected parameters — tests pin them.
- Never hand-edit `uv.lock` or standard-owned files (conventions #1/#8).

## Design decisions locked by this plan

These interpret the spec where it left the operational definition to the implementer. Each cites its basis. Decisions 1–2 are genuinely new surface, so they are ALSO filed as OQ-035/OQ-036 rows (spec §21 + `docs/open-questions.md`) per Appendix B — proposed assumptions, non-blocking, owner sign-off wanted by MS-4. If any decision turns out wrong during execution, stop and record an OQ-/DEV- row instead of guessing.

1. **Preservation flags and risk tiers (→ OQ-035).** FR-005 names three byte-preserving strategies but no CLI surface for two of them. Locked: `--backup-dir PATH` (or snapshot `write.backup_dir`) activates tool-written backups; `--preserved-by {git,external}` _declares_ an external byte-preserving strategy (an operator assertion — docmend stays preservation-agnostic per adr-0004); `--allow-no-backup` is the FR-005 low-risk opt-in, valid **only when the plan contains exactly one action** (the spec's "low-risk single-file operation"). Risk tiers: an action is a _content rewrite_ iff any operation ≠ `rename`; a rename-only run under `skip`/`fail` collision policy needs no byte-preserving strategy (the manifest mechanically undoes a pure path move — nothing's bytes change); content rewrites require an active strategy or the single-action opt-in. Under the `overwrite` policy, clobbering an existing target destroys _that file's_ bytes (G-002), so any run that would actually overwrite requires an active byte-preserving strategy, and when tool backups are enabled the writer backs up the clobbered target too (manifest 1.1 fields `overwritten_sha256`/`overwritten_backup_path`).
2. **Run-lock location and mechanism (→ OQ-036).** OQ-027 mandates the lock but not its home. Locked: `flock(2)` on `$XDG_STATE_HOME/docmend/locks/<sha256-of-resolved-source-root>.lock` (default `~/.local/state/...`) — keyed to the _target_, so two invocations from different CWDs contend correctly, and the library tree itself stays untouched (plan remains write-free over the library, §3.1). flock, not `O_EXCL`-create-plus-unlink (codex CR-004): the kernel owns the lock, it vanishes with the holding process (crash included), so there is no stale-PID detection to get wrong and no unlink-by-name step that could remove a competitor's freshly acquired lock. Holder JSON (`run_id`, `pid`, `command`, `started_at`) is written into the file purely for the refusal message; a live holder refuses with exit 3 (AW-005). `plan`, `apply`, and `restore` all acquire it (restore mutates the same tree; commonpath of its manifest's original paths is the key). Single-machine semantics by design (A-001; flock over NFS out of scope).
3. **The plan snapshot is apply's config.** Apply takes **no** `--config`: transforms, filters, collision policy, and encoding facts come from `plan.config` (that is the point of the snapshot, DR-002/C.4); only `write.*` concerns may be overridden by apply-time flags (`--backup-dir`). Plan schema 1.1 adds **optional** `source_root` (MINOR-clean: optional field) recorded from the inventory; apply refuses a plan without it (ERR-006, exit 2, "regenerate the plan") — required-field promotion is deferred to a future MAJOR.
4. **Apply recomputes and cross-checks.** For each action apply re-reads bytes, re-verifies `source_sha256` (mismatch → skipped `stale-hash`, ERR-002, exit 1 at completion, batch continues — AW-004), re-runs decode + `apply_text_transforms` from the snapshot, and requires the recomputed operation list to equal the plan's recorded one (divergence → failed ERR-006 — defensive; hash equality makes it unreachable). The EC-005 shrink invariant is re-checked at apply ("Planning flags it; apply skips it").
5. **FR-012 at apply = snapshot-filter enforcement.** Apply re-checks each action's path against the snapshot's include/exclude and skips non-matching actions as `excluded` — identical selection behavior across scan/plan/apply without new flags (only a hand-edited plan can trip it).
6. **Mutation mechanics.** Rewrite-in-place: temp file in the same directory + fsync + `os.replace` + parent-dir fsync, source mode preserved (D-004). Rename (no clobber): `os.link(src, dst)` then `os.unlink(src)` — atomic, `EEXIST` on collision race (a crash between link and unlink leaves both names and loses nothing). Rename+rewrite: temp beside the _target_, publish (link for no-clobber, `os.replace` under overwrite), then unlink the source — the original survives until the new file is durable. v1 renames change suffix only, so source and target always share a directory/device.
7. **Manifest semantics.** Records carry **absolute** paths — including `backup_path`/`overwritten_backup_path`: the CLI resolves `backup_root` once at options-normalization time, so a relative `--backup-dir` can never produce cwd-dependent manifest entries (codex CR-005; restore has no PATH argument, IR-008 — the manifest must locate files standalone; artifacts are confidential-local, §13.4). One fsync'd record per mutation, written immediately **after** the mutation (adr-0006: a crash loses at most the last record; resume reconciles by hash at MS-4). `seq` starts at 1 per run. Reader applies the AOF rule: tolerate only a torn **trailing** line; hard-abort (ERR-008/exit 2) on any interior parse or schema failure. `operation` mapping: rename-only → `rename`; content-only → `rewrite`; both → `rename_and_rewrite`.
8. **Gate refusal still leaves an audit trail.** On exit 3 the run writes a schema-valid report with empty outcomes plus the refusal reasons in the log/stderr (§8.5: no audit-trail-free runs); the library is untouched.
9. **Report skip vocabulary** (report schema's `skip_reason` is a free string; keep it closed internally): `stale-hash` (ERR-002), `unreadable` (ERR-005), `collision` (AW-002), `shrink-invariant` (EC-005), `excluded` (decision 5), `containment` (a resolved path escaping `source_root` at execution time — symlinked-parent defense, §13.5). `failed` outcomes carry `error.class` ∈ {ERR-003 write, ERR-004 backup, ERR-006 plan-inconsistency}.
10. **Restore conservatism (IR-008): preflight-then-mutate.** Only `result == "applied"` records replay, LIFO by `seq`. **Every** prerequisite is verified before **any** mutation of a record — live file still hashes to `after_sha256` (changed since apply → skipped `modified-since-apply`, exit 1 — never clobber newer edits), source backup hashes to `before_sha256`, the overwritten-target backup (when recorded) reads and hashes to `overwritten_sha256`, and the destination is collision-free (codex CR-003: a restore that mutates and then discovers a bad recovery input has destroyed state in the disaster-recovery path itself — failed ERR-004 must leave both live files byte-identical). A record with `backup_path: null` (git/external/opt-in runs) is skipped `no-backup` — the user's own preservation strategy is the recovery path — and an overwrite record whose `overwritten_backup_path` is null (declared external preservation) is skipped whole for the same reason: restoring only docmend's half would report success while the clobbered file stays missing (codex CR-NEW-003). **Failure mode is superset-by-design:** a restore that fails mid-mutation (ERR-003) never deletes anything — the reinstated original and the applied target can coexist; re-running restore reports the leftover as a `collision` skip and the operator clears it using the logged paths. This is the explicit supported recovery mode, asserted by test. Restore is itself mutation: it takes the lock, dry-runs by default, honors `--write`, and appends its own manifest records (inverse operations) to its run's manifest.
11. **Detection provenance fallback (MS-2 review Important #1).** Inventory schema 1.1 records `scan_config.encoding_detect` (bool) and `scan_config.detector` (`"charset-normalizer <version>"` or null). When a plan runs over an inventory whose scan had detection **off**, a no-BOM/non-UTF-8/`detected: null` file skips as `low-confidence-encoding` with detail "encoding detection was not run at scan" — not `binary-suspect` — so `--fail-on-low-confidence-encoding` counts it. Absent fields (a 1.0 inventory) keep today's behavior.
12. **Path containment hardening (MS-2 review Important #2).** `relative_path` in the inventory and plan schemas gains the pattern `^(?!/)(?!(?:.*/)?\.\.(?:/|$)).+$` (no leading `/`, no `..` segment — Python `re` handles the lookaheads; pydantic's rust-regex does not, so the model side is an `AfterValidator`). `read_inventory`/`read_plan` therefore reject crafted artifacts at exit 2. Apply adds the runtime belt: each source/target resolves (`Path.resolve()`) inside the resolved `source_root` or the action is skipped `containment`.
13. **Schema version bumps** (adr-0005 MINOR policy — optional fields/enum values only): inventory 1.0→1.1 (two optional scan_config fields + pattern tightening), plan 1.0→1.1 (optional `source_root` + pattern tightening), manifest 1.0→1.1 (two optional overwrite fields + absolute-path descriptions), report stays 1.0. Pattern tightening is nominally a constraint change, but no artifact with an absolute/`..` path was ever legitimately producible — recorded here rather than as a MAJOR.
14. **Sequential only.** No process pool in MS-3 (OQ-016 sequential-until-profiled; MS-5 revisits). The single-writer/lock design (OQ-027) is satisfied trivially. The FR-019 watchdog stays MS-5; FR-013 resume and FR-014 verify stay MS-4 — the manifest built here (seq, per-record fsync, AOF reader) is what MS-4 consumes.

---

### Task 1: Artifact path-containment hardening (schemas 1.1 + model validators)

MS-2 review Important #2. Reject absolute and `..`-bearing paths at every artifact read.

**Files:**

- Modify: `src/docmend/schemas/inventory.schema.json` (relative_path pattern; schema_version note)
- Modify: `src/docmend/schemas/plan.schema.json` (relative_path pattern)
- Modify: `src/docmend/inventory.py` (`RelativePath` validator, `INVENTORY_SCHEMA_VERSION`)
- Modify: `src/docmend/plan.py` (`PLAN_SCHEMA_VERSION`)
- Test: `tests/test_artifact_containment.py`

**Interfaces:**

- Consumes: existing `read_inventory`/`read_plan` (unchanged signatures).
- Produces: `docmend.inventory.RelativePath` now rejects `/abs`, `../x`, `a/../b`, `a/..`; `INVENTORY_SCHEMA_VERSION = "1.1"`, `PLAN_SCHEMA_VERSION = "1.1"`. Every later task relies on `RelativePath` being containment-safe.

- [ ] **Step 1: Write the failing tests** — `tests/test_artifact_containment.py`:

```python
"""Artifact path-containment hardening (spec §8.5/§13.5; MS-2 final-review Important #2).

A crafted or hand-edited inventory/plan with absolute or '..' paths must be
rejected at read time (ERR-008 semantics, exit 2) — the §8.5 apply-time
containment check remains the runtime gate; this is the artifact-layer belt.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from docmend import artifacts
from docmend.inventory import FileRecord

BAD_PATHS = ["/etc/passwd", "../escape.txt", "a/../b.txt", "a/..", ".."]
GOOD_PATHS = ["a.txt", "sub/b.txt", "odd..name.txt", "sub/..hidden", "d../e.txt"]


def _file_record(path: str) -> dict[str, object]:
    return {
        "path": path,
        "size_bytes": 1,
        "suffix": ".txt",
        "mtime_ns": 0,
        "nlink": 1,
        "sha256": "sha256:" + "0" * 64,
        "newline_style": "lf",
        "nul_bytes": False,
        "non_ascii_bytes": 0,
        "encoding": {"bom": None, "utf8_valid": True, "ascii_only": True, "detected": None},
    }


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_file_record_model__rejects_escaping_path(bad: str) -> None:
    with pytest.raises(ValidationError):
        FileRecord.model_validate(_file_record(bad))


@pytest.mark.parametrize("good", GOOD_PATHS)
def test_file_record_model__accepts_contained_path(good: str) -> None:
    assert FileRecord.model_validate(_file_record(good)).path == good


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_inventory_schema__rejects_escaping_path(bad: str) -> None:
    with pytest.raises(artifacts.ArtifactError):
        artifacts.validate_artifact("inventory", _minimal_inventory(bad))


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_read_inventory__rejects_crafted_artifact(tmp_path: Path, bad: str) -> None:
    doc = _minimal_inventory(bad)
    target = tmp_path / "inventory.json"
    target.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(artifacts.ArtifactError):
        artifacts.read_inventory(target)


def _minimal_inventory(path: str) -> dict[str, object]:
    record = _file_record(path)
    return {
        "schema": "docmend/inventory",
        "schema_version": "1.1",
        "run_id": "run_20260706T000000Z_000000",
        "generated_at": "2026-07-06T00:00:00+00:00",
        "generated_by": "docmend 0.1.0",
        "requested_path": "corpus",
        "source_root": "/corpus",
        "scan_config": {"include": ["**/*.txt"], "exclude": []},
        "files": [record],
        "symlinks": [],
        "skipped": [],
        "hard_link_groups": [],
        "totals": {
            "files": 1,
            "symlinks": 0,
            "skipped": 0,
            "skipped_by_reason": {"excluded": 0, "unreadable": 0},
            "hard_link_groups": 0,
            "total_size_bytes": 1,
        },
    }
```

Add the plan-side mirror (same `BAD_PATHS` over a minimal plan document with one action whose `path`/`target_path` carries the bad value, asserting `artifacts.validate_artifact("plan", ...)` and a `read_plan` round-trip both raise). Build the minimal plan document with `schema_version: "1.1"`, a valid `inventory_ref`, and `config` = `DocmendConfig().model_dump(mode="json")`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_artifact_containment.py -x -q` Expected: FAIL — bad paths are currently accepted (`min_length=1` only).

- [ ] **Step 3: Implement.** In `src/docmend/inventory.py`:

```python
from pydantic import AfterValidator  # add to existing import

INVENTORY_SCHEMA_VERSION = "1.1"


def _contained_relative_path(value: str) -> str:
    # Containment belt (spec §8.5/§13.5): artifacts are operator-editable JSON,
    # so a crafted absolute or '..' path must die at read time, not at apply.
    if value.startswith("/"):
        msg = "path must be relative to source_root, not absolute"
        raise ValueError(msg)
    if ".." in value.split("/"):
        msg = "path must not contain '..' segments"
        raise ValueError(msg)
    return value


type RelativePath = Annotated[str, Field(min_length=1), AfterValidator(_contained_relative_path)]
```

In `src/docmend/plan.py`: `PLAN_SCHEMA_VERSION = "1.1"` (RelativePath is imported from inventory — nothing else changes here yet).

In both schema files, replace the `relative_path` def:

```json
"relative_path": {
    "description": "POSIX-style path relative to source_root; never absolute, never containing '..' — enforced by pattern since 1.1 (MS-2 final-review hardening).",
    "type": "string",
    "minLength": 1,
    "pattern": "^(?!/)(?!(?:.*/)?\\.\\.(?:/|$)).+$"
}
```

(The plan schema's bare `"relative_path": { "type": "string", "minLength": 1 }` gains the same description + pattern.)

- [ ] **Step 4: Run the new tests, then the full suite** — existing tests pin `schema_version` `"1.0"` in fixtures/assertions (`tests/test_inventory_artifact.py`, `tests/test_plan_artifact.py`, `tests/test_schemas.py`, corpus constants); update those expectations to `"1.1"`. The schema `pattern "^1\\.[0-9]+$"` still accepts both.

Run: `uv run coverage run -m pytest -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/schemas/inventory.schema.json src/docmend/schemas/plan.schema.json \
        src/docmend/inventory.py src/docmend/plan.py tests/test_artifact_containment.py \
        tests/test_inventory_artifact.py tests/test_plan_artifact.py tests/test_schemas.py
git commit -m "harden: reject absolute/'..' artifact paths at read time (schemas 1.1)"
```

---

### Task 2: Inventory detection provenance + planning fallback

MS-2 review Important #1: cross-config `plan --inventory` runs misclassify undetected legacy files.

**Files:**

- Modify: `src/docmend/schemas/inventory.schema.json` (scan_config optional fields)
- Modify: `src/docmend/inventory.py` (`ScanConfigRecord`)
- Modify: `src/docmend/discovery.py` (populate the new fields)
- Modify: `src/docmend/planning.py` (fallback skip reason)
- Test: `tests/test_detection_provenance.py`

**Interfaces:**

- Consumes: `discovery.scan(...)` (internal change only), `planning.build_plan(...)` (unchanged signature).
- Produces: `ScanConfigRecord.encoding_detect: bool | None = None`, `ScanConfigRecord.detector: str | None = None`. Planning treats `encoding_detect is False` + `detected is None` as `low-confidence-encoding`.

- [ ] **Step 1: Write the failing tests** — `tests/test_detection_provenance.py`:

```python
"""Scan-config detection provenance (DR-001; MS-2 final-review Important #1).

The inventory must record whether encoding detection ran at scan (and which
detector), so a later plan run with a different config cannot misread
'detected: null' as binary-suspect when detection simply never ran (FR-007,
FR-015 — the skip must be low-confidence-encoding, which
--fail-on-low-confidence-encoding counts).
"""

from importlib.metadata import version
from pathlib import Path

from docmend import discovery, planning
from docmend.config import DocmendConfig, EncodingConfig
from docmend.plan import ArtifactRef

RUN_ID = "run_20260706T000000Z_00003a"
GENERATED_AT = "2026-07-06T00:00:00+00:00"


def _scan(root: Path, config: DocmendConfig):
    return discovery.scan(root, config, run_id=RUN_ID, generated_at=GENERATED_AT)


def _ref() -> ArtifactRef:
    return ArtifactRef(path="inv.json", run_id=RUN_ID, sha256="sha256:" + "0" * 64)


def _legacy_corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    # windows-1252 bytes, invalid as UTF-8, no BOM, no NUL — the legacy rung's case.
    (root / "legacy.txt").write_bytes(("café " * 30).encode("windows-1252"))
    return root


def test_scan_records_detection_provenance__enabled(tmp_path: Path) -> None:
    inventory = _scan(_legacy_corpus(tmp_path), DocmendConfig())
    assert inventory.scan_config.encoding_detect is True
    assert inventory.scan_config.detector == f"charset-normalizer {version('charset-normalizer')}"


def test_scan_records_detection_provenance__disabled(tmp_path: Path) -> None:
    config = DocmendConfig(encoding=EncodingConfig(detect=False))
    inventory = _scan(_legacy_corpus(tmp_path), config)
    assert inventory.scan_config.encoding_detect is False
    assert inventory.scan_config.detector is None


def test_plan_over_detect_off_inventory__skips_low_confidence_not_binary(tmp_path: Path) -> None:
    """FR-007/FR-015: detection-not-run is a low-confidence skip, never binary-suspect."""
    scan_config = DocmendConfig(encoding=EncodingConfig(detect=False))
    inventory = _scan(_legacy_corpus(tmp_path), scan_config)
    # Plan with detection ENABLED — the cross-config case the review flagged.
    plan = planning.build_plan(
        inventory, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT, inventory_ref=_ref()
    )
    (skip,) = plan.skips
    assert skip.reason == "low-confidence-encoding"
    assert skip.detail == "encoding detection was not run at scan"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_detection_provenance.py -x -q` Expected: FAIL — `ScanConfigRecord` has no `encoding_detect`; the plan skip is `binary-suspect`.

- [ ] **Step 3: Implement.**

`src/docmend/inventory.py` — extend `ScanConfigRecord`:

```python
class ScanConfigRecord(_StrictModel):
    include: list[Annotated[str, Field(min_length=1)]]
    exclude: list[Annotated[str, Field(min_length=1)]]
    # 1.1 (MS-2 final-review Important #1): scan-output provenance beyond filters.
    # None = a pre-1.1 artifact where the fact is unknown; new scans always record.
    encoding_detect: bool | None = None
    detector: Annotated[str, Field(min_length=1)] | None = None
```

`src/docmend/discovery.py` — where the `Inventory` is assembled (`scan_config=ScanConfigRecord(...)` around line 414):

```python
        scan_config=ScanConfigRecord(
            include=list(config.paths.include),
            exclude=list(config.paths.exclude),
            encoding_detect=config.encoding.detect,
            detector=(
                f"charset-normalizer {metadata_version('charset-normalizer')}"
                if config.encoding.detect
                else None
            ),
        ),
```

with `from importlib.metadata import version as metadata_version` added to the imports.

`src/docmend/schemas/inventory.schema.json` — inside `scan_config.properties` (NOT added to `required` — 1.1 optional fields):

```json
"encoding_detect": {
    "description": "Whether encoding detection ran during this scan (1.1) — planning must not read 'detected: null' as binary-suspect when detection never ran. Null only in pre-1.1 artifacts.",
    "type": ["boolean", "null"]
},
"detector": {
    "description": "Detector name and version when detection ran (e.g. 'charset-normalizer 3.4.4'); null when detection was off or in pre-1.1 artifacts.",
    "type": ["string", "null"]
}
```

`src/docmend/planning.py` — thread the fact through `_fact_skip`. Add a parameter `scan_detect: bool | None` (passed as `inventory.scan_config.encoding_detect` from `build_plan`), and change the `detected is None` branch:

```python
        if enc.detected is None:
            if scan_detect is False:
                return SkipDecision(
                    path=path,
                    reason="low-confidence-encoding",
                    detail="encoding detection was not run at scan",
                )
            return SkipDecision(path=path, reason="binary-suspect", detail="no encoding candidate")
```

- [ ] **Step 4: Run the new tests, then the full suite**

Run: `uv run coverage run -m pytest -q` Expected: PASS (the schema cross-check test in `tests/test_schemas.py` compares model fields to schema properties — the new optional fields appear on both sides).

- [ ] **Step 5: Commit**

```bash
git add src/docmend/schemas/inventory.schema.json src/docmend/inventory.py \
        src/docmend/discovery.py src/docmend/planning.py tests/test_detection_provenance.py
git commit -m "feat: record scan-time detection provenance; fix cross-config binary-suspect misclassification"
```

---

### Task 3: Run-level lock (OQ-027 / AW-005)

**Files:**

- Create: `src/docmend/lock.py`
- Modify: `src/docmend/cli.py` (`plan` acquires/releases the lock)
- Test: `tests/test_lock.py`

**Interfaces:**

- Consumes: nothing new.
- Produces: `lock.acquire(source_root: Path, *, run_id: str, command: str, state_dir: Path | None = None) -> RunLock` raising `LockHeldError` (CLI maps to exit 3); `RunLock.release() -> None` (idempotent); `lock.LockHeldError`. Tasks 10–11 wire the same calls into `apply`/`restore`.

- [ ] **Step 1: Write the failing tests** — `tests/test_lock.py`:

```python
"""Run-level lock (OQ-036 proposal; spec OQ-027, AW-005, §8.5).

One live plan/apply/restore per target tree; a second invocation refuses with
exit 3. flock(2) on a file under $XDG_STATE_HOME/docmend/locks keyed by the
hashed resolved source root: the library tree is never touched, different CWDs
still contend, and — because the kernel drops the lock with the holding
process — a crashed run can never leave a stale lock, and no unlink-based
steal race exists (codex CR-004 class, closed by construction).
"""

import subprocess
import sys
from pathlib import Path

import pytest

from docmend import lock

RUN_ID = "run_20260706T000000Z_00004b"


def test_acquire_then_second_acquire__refuses(tmp_path: Path) -> None:
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()
    held = lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state)
    try:
        with pytest.raises(lock.LockHeldError) as excinfo:
            lock.acquire(root, run_id="run_20260706T000001Z_00004c", command="plan", state_dir=state)
        assert RUN_ID in str(excinfo.value)  # holder identified in the refusal message
    finally:
        held.release()


def test_release__allows_reacquire(tmp_path: Path) -> None:
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()
    lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state).release()
    lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state).release()


def test_dead_holder__lock_auto_released(tmp_path: Path) -> None:
    """A holder that exited (or crashed) leaves no stale lock: flock dies with
    the process, so re-acquisition needs no stale detection at all (CR-004)."""
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()
    script = (
        "import sys; from pathlib import Path; from docmend import lock; "
        "lock.acquire(Path(sys.argv[1]), run_id='run_20260101T000000Z_dead00', "
        "command='apply', state_dir=Path(sys.argv[2]))"
    )
    subprocess.run([sys.executable, "-c", script, str(root), str(state)], check=True)
    lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state).release()


def test_live_holder_in_other_process__refuses(tmp_path: Path) -> None:
    """AW-005 across real processes: a subprocess holds the lock while this
    process tries to acquire."""
    state = tmp_path / "state"
    root = tmp_path / "corpus"
    root.mkdir()
    script = (
        "import sys, time; from pathlib import Path; from docmend import lock; "
        "lock.acquire(Path(sys.argv[1]), run_id='run_20260101T000000Z_11ee00', "
        "command='apply', state_dir=Path(sys.argv[2])); print('held', flush=True); "
        "time.sleep(30)"
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", script, str(root), str(state)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "held"
        with pytest.raises(lock.LockHeldError):
            lock.acquire(root, run_id=RUN_ID, command="apply", state_dir=state)
    finally:
        holder.kill()
        holder.wait()


def test_different_roots__do_not_contend(tmp_path: Path) -> None:
    state = tmp_path / "state"
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    held = lock.acquire(a, run_id=RUN_ID, command="apply", state_dir=state)
    try:
        lock.acquire(b, run_id=RUN_ID, command="apply", state_dir=state).release()
    finally:
        held.release()
```

Plus a CLI-level test in `tests/test_cli_plan.py`: pre-create the lock for the corpus root (via `lock.acquire` with `XDG_STATE_HOME` monkeypatched into `tmp_path`), run `docmend plan <corpus>`, assert exit code 3 and a stderr message naming the holder (AW-005).

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_lock.py -x -q` Expected: FAIL — `docmend.lock` does not exist.

- [ ] **Step 3: Implement** `src/docmend/lock.py`:

```python
"""Run-level lock — one live plan/apply/restore per target tree (OQ-027, AW-005).

Location (OQ-036 proposal): $XDG_STATE_HOME/docmend/locks/<sha256(root)>.json,
NOT inside the library tree — plan stays write-free over the library (§3.1) and
a read-only tree stays plannable. Keyed on the RESOLVED source root so
invocations from different CWDs contend correctly.

Mechanism: flock(2), not O_EXCL-create-plus-unlink (codex CR-004). The kernel
owns the lock: it vanishes with the holding process (crash included), so no
stale-PID detection exists to get wrong, and no unlink-by-name step exists
that could remove a competitor's freshly acquired lock (the classic steal
race). Release closes the descriptor and leaves the file behind — an empty
file in the state dir is metadata debris, never a stale lock. Holder JSON is
written into the file purely for the refusal message. Single-machine
semantics by design (A-001: local POSIX filesystem; flock over NFS is out of
scope).
"""

import errno
import fcntl
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


class LockHeldError(Exception):
    """Another live run holds this target's lock (exit 3, AW-005)."""


class RunLock:
    def __init__(self, path: Path, fd: int) -> None:
        self.path = path
        self._fd = fd
        self._released = False

    def release(self) -> None:
        # Closing the descriptor drops the flock; the file deliberately stays
        # (unlinking it would reopen the CR-004 steal race for a competitor
        # blocked on the same inode).
        if not self._released:
            os.close(self._fd)
            self._released = True


def _default_state_dir() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "docmend" / "locks"


def lock_path(source_root: Path, *, state_dir: Path | None = None) -> Path:
    digest = hashlib.sha256(str(source_root.resolve()).encode()).hexdigest()
    return (state_dir if state_dir is not None else _default_state_dir()) / f"{digest}.lock"


def acquire(
    source_root: Path, *, run_id: str, command: str, state_dir: Path | None = None
) -> RunLock:
    path = lock_path(source_root, state_dir=state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        # Contention is EWOULDBLOCK/EAGAIN on Linux (BlockingIOError) but
        # EACCES on some Unixes — treat both as "held", re-raise the rest.
        if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES):
            os.close(fd)
            raise
        holder = _read_holder(fd)
        os.close(fd)
        msg = (
            f"{source_root}: another docmend run holds the lock{holder} — "
            f"AW-005 refuses a second concurrent run against the same target"
        )
        raise LockHeldError(msg) from exc
    # Best-effort holder metadata for the competitor's refusal message; the
    # flock itself, not this JSON, is the mutual exclusion.
    os.ftruncate(fd, 0)
    os.write(
        fd,
        json.dumps(
            {
                "run_id": run_id,
                "pid": os.getpid(),
                "command": command,
                "started_at": datetime.now(UTC).isoformat(),
            }
        ).encode("utf-8"),
    )
    os.fsync(fd)
    return RunLock(path, fd)


def _read_holder(fd: int) -> str:
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        existing: dict[str, object] = json.loads(os.read(fd, 4096).decode("utf-8"))
    except (OSError, ValueError):
        return ""
    return (
        f" (run_id {existing.get('run_id')}, pid {existing.get('pid')}, "
        f"command {existing.get('command')})"
    )
```

- [ ] **Step 4: Wire `plan` in `src/docmend/cli.py`.** After the inventory is obtained (both branches — the scanned root for the PATH shorthand, `Path(inventory.source_root)` for `--inventory`), wrap the planning work:

```python
    try:
        run_lock = lock.acquire(Path(inventory.source_root), run_id=run_id, command="plan")
    except lock.LockHeldError as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(3) from exc
    except OSError as exc:
        # The state dir being uncreatable must not block a read-only plan.
        get_logger(__name__).warning("run lock unavailable", error=str(exc))
        run_lock = None
    try:
        ...  # existing inventory_ref/build_plan/write_plan/echo block, unchanged
    finally:
        if run_lock is not None:
            run_lock.release()
```

Note: for the PATH shorthand, acquire the lock **before** `discovery.scan` (the root is known: `path if path.is_dir() else path.parent`, resolved) so the scan+plan pair is covered as one run; the `--inventory` branch acquires after `read_inventory` (the root is only known then). Add `from docmend import lock` to the imports.

- [ ] **Step 5: Run the full suite**

Run: `uv run coverage run -m pytest -q` Expected: PASS (existing CLI plan tests run with a real `$HOME`; monkeypatch `XDG_STATE_HOME` to `tmp_path` in the `corpus` fixtures of `tests/test_cli_plan.py` so tests never touch the real state dir — do the same in `tests/test_cli_scan.py`'s shared fixture if it is reused).

- [ ] **Step 6: Commit**

```bash
git add src/docmend/lock.py src/docmend/cli.py tests/test_lock.py tests/test_cli_plan.py
git commit -m "feat: run-level lock (OQ-027/AW-005) - plan wired, exit 3 on live holder"
```

---

### Task 4: Report data model + artifact IO (DR-003)

**Files:**

- Create: `src/docmend/report.py`
- Modify: `src/docmend/artifacts.py` (`write_report`, `read_report`)
- Test: `tests/test_report_artifact.py`

**Interfaces:**

- Consumes: `ArtifactRef` from `docmend.plan`; `ActionId` from `docmend.plan`.
- Produces (used by Tasks 5/9/10):
  - `ErrorInfo(error_class: str, message: str)` — serializes as `{"class": ..., "message": ...}`.
  - `ApplyOutcome(action_id, path, status, before_sha256, after_sha256, skip_reason, error)`.
  - `ReportTotals(applied, would_apply, skipped, failed)`.
  - `Report(run_id, generated_by, plan_ref, dry_run, started_at, completed_at, outcomes, totals)` with `schema_kind="docmend/report"`, `REPORT_SCHEMA_VERSION = "1.0"`.
  - `artifacts.write_report(report: Report, path: Path) -> None`, `artifacts.read_report(path: Path) -> Report`.

- [ ] **Step 1: Write the failing tests** — `tests/test_report_artifact.py`:

```python
"""Report artifact round-trip and schema conformance (DR-003, FR-018, IR-007)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from docmend import artifacts
from docmend.plan import ArtifactRef
from docmend.report import ApplyOutcome, ErrorInfo, Report, ReportTotals

RUN_ID = "run_20260706T000000Z_00005c"
SHA = "sha256:" + "a" * 64


def _report() -> Report:
    return Report(
        run_id=RUN_ID,
        generated_by="docmend 0.1.0",
        plan_ref=ArtifactRef(path="plan.json", run_id=RUN_ID, sha256=SHA),
        dry_run=True,
        started_at="2026-07-06T00:00:00+00:00",
        completed_at="2026-07-06T00:00:01+00:00",
        outcomes=[
            ApplyOutcome(
                action_id=f"{RUN_ID}/a1",
                path="a.txt",
                status="would_apply",
                before_sha256=SHA,
                after_sha256=None,
                skip_reason=None,
                error=None,
            ),
            ApplyOutcome(
                action_id=f"{RUN_ID}/a2",
                path="b.txt",
                status="failed",
                before_sha256=SHA,
                after_sha256=None,
                skip_reason=None,
                error=ErrorInfo(error_class="ERR-003", message="disk full"),
            ),
        ],
        totals=ReportTotals(applied=0, would_apply=1, skipped=0, failed=1),
    )


def test_report_round_trip__write_read_identical(tmp_path: Path) -> None:
    """IR-007: write -> read -> identical model (DR-003)."""
    out = tmp_path / "report.json"
    artifacts.write_report(_report(), out)
    assert artifacts.read_report(out) == _report()


def test_report_serializes_wire_names__schema_and_class(tmp_path: Path) -> None:
    document = _report().model_dump(mode="json")
    assert document["schema"] == "docmend/report"
    assert document["outcomes"][1]["error"]["class"] == "ERR-003"
    artifacts.validate_artifact("report", document)


def test_error_class_pattern__rejected_when_malformed() -> None:
    with pytest.raises(ValidationError):
        ErrorInfo(error_class="oops", message="x")


def test_report_totals_mismatch__rejected_by_writer(tmp_path: Path) -> None:
    """DR-003: summary counts must equal per-outcome totals — enforced at write."""
    bad = _report().model_copy(update={"totals": ReportTotals(applied=9, would_apply=0, skipped=0, failed=0)})
    with pytest.raises(artifacts.ArtifactError):
        artifacts.write_report(bad, tmp_path / "report.json")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_report_artifact.py -x -q` Expected: FAIL — `docmend.report` does not exist.

- [ ] **Step 3: Implement** `src/docmend/report.py`:

```python
"""Apply-report data model — the DR-003 artifact as strict internal models (OQ-021).

Cross-file contract (adr-0005): src/docmend/schemas/report.schema.json is the
durable external contract; these models CONFORM to it. Identity/hash aliases
are shared with docmend.inventory/docmend.plan; serialization goes through
docmend.artifacts, which validates before disk and enforces the DR-003
totals-equal-outcomes reconciliation rule.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from docmend.inventory import Sha256
from docmend.plan import ActionId, ArtifactRef, RunId

REPORT_SCHEMA_VERSION = "1.0"

type OutcomeStatus = Literal["applied", "would_apply", "skipped", "failed"]
#: Closed internal vocabulary for the schema's free-string skip_reason
#: (decision 9): stale hash ERR-002/AW-004, apply-time unreadable ERR-005,
#: collision AW-002, EC-005 re-check, snapshot-filter enforcement (FR-012),
#: and the runtime containment belt (§13.5).
type ApplySkipReason = Literal[
    "stale-hash", "unreadable", "collision", "shrink-invariant", "excluded", "containment"
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ErrorInfo(BaseModel):
    """Classified failure ({'class': 'ERR-NNN', 'message': ...}); 'class' is a
    Python keyword, hence the alias."""

    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
    )

    error_class: Annotated[str, Field(pattern=r"^ERR-\d{3}$", alias="class")]
    message: str


class ApplyOutcome(_StrictModel):
    action_id: ActionId
    path: Annotated[str, Field(min_length=1)]
    status: OutcomeStatus
    before_sha256: Sha256 | None
    after_sha256: Sha256 | None
    skip_reason: ApplySkipReason | None
    error: ErrorInfo | None


class ReportTotals(_StrictModel):
    applied: Annotated[int, Field(ge=0)]
    would_apply: Annotated[int, Field(ge=0)]
    skipped: Annotated[int, Field(ge=0)]
    failed: Annotated[int, Field(ge=0)]


class Report(_StrictModel):
    """One `docmend apply` result (DR-003) — serialize via docmend.artifacts only."""

    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
    )

    schema_kind: Literal["docmend/report"] = Field(default="docmend/report", alias="schema")
    schema_version: Annotated[str, Field(pattern=r"^1\.\d+$")] = REPORT_SCHEMA_VERSION
    run_id: RunId
    generated_by: Annotated[str, Field(min_length=1)]
    plan_ref: ArtifactRef
    dry_run: bool
    started_at: str
    completed_at: str
    outcomes: list[ApplyOutcome]
    totals: ReportTotals
```

Note: `RunId` is re-exported from `docmend.plan` via its `from docmend.inventory import ... RunId` line already — import it from `docmend.plan` alongside `ActionId`/`ArtifactRef` (or directly from `docmend.inventory`; pick one and let Ruff's import sort settle it).

In `src/docmend/artifacts.py` add (mirroring `write_plan`/`read_plan`):

```python
from collections import Counter  # top of file

from docmend.report import Report  # with the existing model imports


def write_report(report: Report, path: Path) -> None:
    """Validate a produced report, enforce DR-003 count reconciliation, persist."""
    counts = Counter(outcome.status for outcome in report.outcomes)
    expected = {
        "applied": report.totals.applied,
        "would_apply": report.totals.would_apply,
        "skipped": report.totals.skipped,
        "failed": report.totals.failed,
    }
    actual = {key: counts.get(key, 0) for key in expected}
    if expected != actual:
        msg = f"report totals {expected} do not reconcile with outcomes {actual} (DR-003)"
        raise ArtifactError(msg)
    document: dict[str, object] = report.model_dump(mode="json")
    validate_artifact("report", document)
    write_json_artifact(document, path)


def read_report(path: Path) -> Report:
    """Load and validate a report artifact (ERR-008 semantics on failure)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"{path}: cannot read report artifact ({exc.strerror or exc})"
        raise ArtifactError(msg) from exc
    try:
        document: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"{path}: not valid JSON — {exc}"
        raise ArtifactError(msg) from exc
    validate_artifact("report", document)
    return Report.model_validate(document)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_report_artifact.py tests/test_schemas.py -q` Expected: PASS. If `tests/test_schemas.py` cross-checks every model↔schema pair from a registry, register `Report` there.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/report.py src/docmend/artifacts.py tests/test_report_artifact.py tests/test_schemas.py
git commit -m "feat: DR-003 report model + validated artifact IO with count reconciliation"
```

---

### Task 5: Manifest model, writer, and AOF reader (DR-004)

**Files:**

- Modify: `src/docmend/schemas/manifest.schema.json` (1.1: overwrite fields, absolute-path descriptions)
- Create: `src/docmend/writer/manifest.py`
- Test: `tests/unit/writer/__init__.py` (empty), `tests/unit/writer/test_manifest.py`

**Interfaces:**

- Consumes: `ErrorInfo` from `docmend.report`; `ActionId`, `DocmendId` from `docmend.plan`; `Sha256`, `RunId` from `docmend.inventory`; `artifacts.validate_artifact`.
- Produces (used by Tasks 9/11 and MS-4 resume):
  - `MANIFEST_SCHEMA_VERSION = "1.1"`, `type ManifestOperation = Literal["rename", "rewrite", "rename_and_rewrite"]`.
  - `ManifestRecord(...)` — full record model; `overwritten_sha256`/`overwritten_backup_path` default `None`.
  - `ManifestWriter(path, run_id, now=...)` context manager: `.append(record_without_seq_and_stamp) -> ManifestRecord` assigns `seq`, stamps `recorded_at`, schema-validates, writes one NDJSON line, flushes, fsyncs.
  - `read_manifest(path: Path) -> list[ManifestRecord]` — AOF torn-trailing-line rule; raises `artifacts.ArtifactError` on interior corruption.

- [ ] **Step 1: Write the failing tests** — `tests/unit/writer/test_manifest.py`:

```python
"""Manifest writer/reader (DR-004, IR-007 NDJSON half, adr-0005/adr-0006).

Real filesystem on purpose (OQ-019): the per-record append+fsync durability
behavior is the thing under test. The AOF rule (adr-0006): tolerate only a
torn TRAILING line; hard-abort on any interior corruption.
"""

import json
from pathlib import Path

import pytest

from docmend.artifacts import ArtifactError
from docmend.writer.manifest import ManifestRecord, ManifestWriter, read_manifest

RUN_ID = "run_20260706T000000Z_00006d"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
UUID7 = "01980000-0000-7000-8000-000000000001"


def _record(seq_free_suffix: int) -> ManifestRecord:
    return ManifestRecord(
        run_id=RUN_ID,
        action_id=f"{RUN_ID}/a{seq_free_suffix}",
        docmend_id=UUID7,
        seq=1,  # placeholder; ManifestWriter.append re-stamps
        recorded_at="2026-07-06T00:00:00+00:00",
        operation="rewrite",
        original_path="/corpus/a.txt",
        target_path="/corpus/a.txt",
        backup_path=None,
        before_sha256=SHA_A,
        after_sha256=SHA_B,
        result="applied",
        error=None,
    )


def test_append_read_round_trip__per_record(tmp_path: Path) -> None:
    """IR-007: each NDJSON line parses back to an identical record model (DR-004)."""
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        first = writer.append(_record(1))
        second = writer.append(_record(2))
    assert (first.seq, second.seq) == (1, 2)
    assert read_manifest(path) == [first, second]


def test_torn_trailing_line__tolerated(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        kept = writer.append(_record(1))
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"schema": "docmend/manifest-record", "torn')  # no newline: crash mid-append
    assert read_manifest(path) == [kept]


def test_corrupt_newline_terminated_final_record__hard_aborts(tmp_path: Path) -> None:
    """codex CR-NEW-006: a final line ending in '\\n' was a COMPLETE record —
    if it no longer parses, that is corruption, never a tolerable torn tail."""
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        writer.append(_record(1))
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{corrupt}\n")
    with pytest.raises(ArtifactError):
        read_manifest(path)


def test_first_append_fsyncs_manifest_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """codex CR-NEW-005: creating the manifest file must fsync its directory —
    file fsync alone does not persist a new directory entry."""
    from docmend.writer import manifest as manifest_module

    calls: list[Path] = []
    monkeypatch.setattr(manifest_module, "fsync_dir", calls.append)
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        writer.append(_record(1))
        writer.append(_record(2))
    assert calls == [tmp_path]  # exactly once, on first create


def test_corrupt_interior_line__hard_aborts(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        record = writer.append(_record(1))
    lines = path.read_text(encoding="utf-8")
    path.write_text("{corrupt}\n" + lines, encoding="utf-8")
    with pytest.raises(ArtifactError):
        read_manifest(path)
    del record


def test_schema_invalid_interior_record__hard_aborts(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        writer.append(_record(1))
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["result"] = "not-a-result"
    path.write_text(json.dumps(doc) + "\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ArtifactError):
        read_manifest(path)


def test_zero_appends__no_manifest_file_created(tmp_path: Path) -> None:
    """A write run in which every action skipped leaves NO manifest file —
    an empty manifest would imply mutations happened (lazy-open contract)."""
    path = tmp_path / "manifest.jsonl"
    with ManifestWriter(path, run_id=RUN_ID):
        pass
    assert not path.exists()


def test_overwrite_fields__round_trip(tmp_path: Path) -> None:
    """Manifest 1.1 (OQ-035): clobbered-target preservation fields."""
    path = tmp_path / "manifest.jsonl"
    record = _record(1).model_copy(
        update={"overwritten_sha256": SHA_B, "overwritten_backup_path": "/backups/run/x.md"}
    )
    with ManifestWriter(path, run_id=RUN_ID) as writer:
        written = writer.append(record)
    assert read_manifest(path)[0] == written
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/writer/test_manifest.py -x -q` Expected: FAIL — module missing.

- [ ] **Step 3: Amend the schema** — `src/docmend/schemas/manifest.schema.json`, inside `properties` (NOT `required`):

```json
"overwritten_sha256": {
    "description": "1.1 (OQ-035): hash of the pre-existing target this mutation clobbered under the overwrite collision policy; null otherwise.",
    "oneOf": [{ "type": "null" }, { "$ref": "#/$defs/sha256" }]
},
"overwritten_backup_path": {
    "description": "1.1 (OQ-035): verified backup of the clobbered target when tool backups were enabled; null otherwise.",
    "type": ["string", "null"]
}
```

and extend the `original_path`/`target_path`/`backup_path` descriptions with: "Absolute path — restore locates files from the manifest alone (IR-008)."

- [ ] **Step 4: Implement** `src/docmend/writer/manifest.py`:

```python
"""Manifest writer/reader — the DR-004 append-only NDJSON record (adr-0005, adr-0006).

Cross-file contracts:
- One record is appended, flushed, and fsync'd immediately after each mutation
  (spec 12.3: incremental, never only at run end); a crash therefore loses at
  most the trailing record, which is exactly what the AOF read rule tolerates.
- Paths are ABSOLUTE (decision 7): `docmend restore` has no PATH argument
  (IR-008) and must locate files from the manifest alone.
- read_manifest is the MS-4 resume reader too — torn TRAILING line dropped
  with a warning; any interior parse/schema failure hard-aborts (ArtifactError
  → exit 2), because a corrupt interior record is a defect, not something to
  skip past (adr-0006).
"""

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Annotated, Literal, Self, TextIO

from pydantic import BaseModel, ConfigDict, Field

from docmend.artifacts import ArtifactError, validate_artifact
from docmend.inventory import RunId, Sha256
from docmend.observability import get_logger
from docmend.plan import ActionId, DocmendId
from docmend.report import ErrorInfo
from docmend.writer.atomic import fsync_dir

MANIFEST_SCHEMA_VERSION = "1.1"

type ManifestOperation = Literal["rename", "rewrite", "rename_and_rewrite"]


class ManifestRecord(BaseModel):
    """One mutation record (DR-004) — one NDJSON line, restorable in isolation."""

    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
    )

    schema_kind: Literal["docmend/manifest-record"] = Field(
        default="docmend/manifest-record", alias="schema"
    )
    schema_version: Annotated[str, Field(pattern=r"^1\.\d+$")] = MANIFEST_SCHEMA_VERSION
    run_id: RunId
    action_id: ActionId
    docmend_id: DocmendId
    seq: Annotated[int, Field(ge=1)]
    recorded_at: str
    operation: ManifestOperation
    original_path: Annotated[str, Field(min_length=1)]
    target_path: Annotated[str, Field(min_length=1)]
    backup_path: str | None
    before_sha256: Sha256
    after_sha256: Sha256 | None
    result: Literal["applied", "failed"]
    error: ErrorInfo | None
    overwritten_sha256: Sha256 | None = None
    overwritten_backup_path: str | None = None


class ManifestWriter:
    """Append-only, per-record-durable NDJSON writer (single-writer, OQ-027)."""

    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(),
    ) -> None:
        self._path = path
        self._run_id = run_id
        self._now = now
        self._seq = 0
        # Lazy-open on first append: a write run in which every action skips
        # must not leave an empty manifest file implying mutations happened
        # (codex round-1 "empty manifest" question — the answer is: no file).
        self._fh: TextIO | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def append(self, record: ManifestRecord) -> ManifestRecord:
        if self._fh is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self._path.open("a", encoding="utf-8")
            # The durability claim covers the file NAME too: fsync(2) on the
            # file alone does not persist a newly created directory entry
            # (codex CR-NEW-005), so the first append also fsyncs the parent.
            fsync_dir(self._path.parent)
        self._seq += 1
        stamped = record.model_copy(update={"seq": self._seq, "recorded_at": self._now()})
        document = stamped.model_dump(mode="json")
        # Self-check before disk, mirroring write_inventory/write_plan.
        validate_artifact("manifest", document)
        self._fh.write(json.dumps(document, ensure_ascii=False) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        return stamped

    def close(self) -> None:
        if self._fh is not None and not self._fh.closed:
            self._fh.close()

    @property
    def path(self) -> Path:
        return self._path


def read_manifest(path: Path) -> list[ManifestRecord]:
    """Read every record, applying the adr-0006 AOF torn-tail rule."""
    log = get_logger(__name__)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"{path}: cannot read manifest ({exc.strerror or exc})"
        raise ArtifactError(msg) from exc
    lines = raw.splitlines()
    # AOF tolerance applies ONLY to a physically unterminated tail (a crash
    # mid-append). A newline-terminated final line was a COMPLETE record; if
    # it no longer parses, that is corruption, not a torn write, and it must
    # hard-abort like an interior record (codex CR-NEW-006; adr-0006).
    unterminated_tail = bool(raw) and not raw.endswith("\n")
    records: list[ManifestRecord] = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        trailing = index == len(lines) - 1
        try:
            document: object = json.loads(line)
        except json.JSONDecodeError as exc:
            if trailing and unterminated_tail:
                log.warning("torn trailing manifest line dropped", path=str(path), line=index + 1)
                break
            msg = f"{path}:{index + 1}: corrupt manifest record — {exc}"
            raise ArtifactError(msg) from exc
        validate_artifact("manifest", document)
        records.append(ManifestRecord.model_validate(document))
    return records
```

Create the empty `tests/unit/writer/__init__.py` only if the existing `tests/unit/transform/` layout has one — mirror whatever convention `tests/unit/transform/` uses (it has no `__init__.py`; then skip this file).

- [ ] **Step 5: Run the tests, then the full suite**

Run: `uv run coverage run -m pytest -q` Expected: PASS. Watch basedpyright: `existing["pid"]` is `object`; the `int(...)` + `# type: ignore` pattern in lock.py and any analogous casts here must be strict-clean (prefer `isinstance` narrowing over ignores if the checker complains).

- [ ] **Step 6: Commit**

```bash
git add src/docmend/schemas/manifest.schema.json src/docmend/writer/manifest.py \
        tests/unit/writer/test_manifest.py
git commit -m "feat: DR-004 manifest model, fsync-per-record writer, AOF reader (schema 1.1)"
```

---

### Task 6: Atomic write primitives (NFR-002, D-004)

**Files:**

- Create: `src/docmend/writer/atomic.py`
- Test: `tests/unit/writer/test_atomic.py`

**Interfaces:**

- Consumes: nothing internal.
- Produces (used by Tasks 7/9/11):
  - `WriteError(Exception)` — ERR-003 family; original guaranteed intact when raised.
  - `atomic_write_bytes(target: Path, data: bytes, *, mode: int | None = None, clobber: bool = True) -> None` — temp-in-same-dir + fsync + publish (`os.replace` when `clobber`, else `os.link`+unlink; `FileExistsError` propagates on a no-clobber race) + parent fsync.
  - `link_no_clobber(source: Path, target: Path) -> None` — the lossless half of a rename (both names exist afterwards); `FileExistsError` propagates.
  - `rename_no_clobber(source: Path, target: Path) -> None` — `link_no_clobber` + `os.unlink`; `FileExistsError` propagates.
  - `rename_overwrite(source: Path, target: Path) -> None` — `os.replace` + parent fsync + `WriteError` wrapping, for the FR-011 overwrite policy only (codex CR-NEW-001: the clobbering rename gets the same durability contract as every other mutation).
  - `fsync_dir(path: Path) -> None` — best-effort ("where practical", D-004).

- [ ] **Step 1: Write the failing tests** — `tests/unit/writer/test_atomic.py`:

```python
"""Atomic write primitives (NFR-002, D-004, adr-0003).

Real filesystem, never pyfakefs (OQ-019/adr-0003): fsync/os.replace/os.link
semantics are the subject. Crash-injection: fail each step and assert the
target is either the intact original or the complete output — never a
fragment, never a stray temp file.
"""

import os
from pathlib import Path

import pytest

from docmend.writer import atomic


def test_atomic_write__replaces_content(tmp_path: Path) -> None:
    """NFR-002: the write lands complete."""
    target = tmp_path / "a.txt"
    target.write_bytes(b"old")
    atomic.atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"new"
    assert list(tmp_path.iterdir()) == [target]  # no temp residue


def test_atomic_write__preserves_mode(tmp_path: Path) -> None:
    """Spec §8.1: permission preservation where reasonable."""
    target = tmp_path / "a.txt"
    target.write_bytes(b"old")
    target.chmod(0o640)
    atomic.atomic_write_bytes(target, b"new", mode=target.stat().st_mode)
    assert (target.stat().st_mode & 0o777) == 0o640


def test_crash_during_replace__original_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR-002 kill-during-write analog: fail at os.replace; file is the intact
    original, and the temp file is cleaned up."""
    target = tmp_path / "a.txt"
    target.write_bytes(b"old")

    def boom(src: object, dst: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(atomic.os, "replace", boom)
    with pytest.raises(atomic.WriteError):
        atomic.atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [target]


def test_no_clobber_publish__raises_when_target_exists(tmp_path: Path) -> None:
    """FR-011/§8.5: the writer refuses to overwrite unless explicitly allowed."""
    target = tmp_path / "a.md"
    target.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        atomic.atomic_write_bytes(target, b"new", clobber=False)
    assert target.read_bytes() == b"existing"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.md"]


def test_no_clobber_publish__creates_when_free(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    atomic.atomic_write_bytes(target, b"new", clobber=False)
    assert target.read_bytes() == b"new"


def test_rename_no_clobber__moves_and_refuses(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_bytes(b"payload")
    atomic.rename_no_clobber(src, tmp_path / "a.md")
    assert not src.exists()
    assert (tmp_path / "a.md").read_bytes() == b"payload"

    other = tmp_path / "b.txt"
    other.write_bytes(b"other")
    blocker = tmp_path / "b.md"
    blocker.write_bytes(b"blocker")
    with pytest.raises(FileExistsError):
        atomic.rename_no_clobber(other, blocker)
    assert other.read_bytes() == b"other"
    assert blocker.read_bytes() == b"blocker"


def test_rename_overwrite__replaces_and_wraps_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """codex CR-NEW-001: the overwrite rename goes through the same
    WriteError/fsync contract as every other mutation (FR-011, NFR-002)."""
    src = tmp_path / "a.txt"
    src.write_bytes(b"new")
    dst = tmp_path / "a.md"
    dst.write_bytes(b"old")
    atomic.rename_overwrite(src, dst)
    assert not src.exists()
    assert dst.read_bytes() == b"new"

    other = tmp_path / "b.txt"
    other.write_bytes(b"payload")
    blocker = tmp_path / "b.md"
    blocker.write_bytes(b"blocker")

    def boom(src_: object, dst_: object) -> None:
        raise OSError(5, "I/O error")

    monkeypatch.setattr(atomic.os, "replace", boom)
    with pytest.raises(atomic.WriteError):
        atomic.rename_overwrite(other, blocker)
    assert other.read_bytes() == b"payload"
    assert blocker.read_bytes() == b"blocker"


def test_write_failure_wraps_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ERR-003: environmental write errors surface as WriteError with the cause."""
    target = tmp_path / "a.txt"

    real_fsync = os.fsync

    def boom(fd: int) -> None:
        raise OSError(5, "I/O error")

    monkeypatch.setattr(atomic.os, "fsync", boom)
    with pytest.raises(atomic.WriteError):
        atomic.atomic_write_bytes(target, b"new")
    monkeypatch.setattr(atomic.os, "fsync", real_fsync)
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/writer/test_atomic.py -x -q` Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `src/docmend/writer/atomic.py`:

```python
"""Atomic filesystem primitives — the NFR-002 mechanism (D-004, adr-0003).

Every mutation path in the writer goes through these two functions; nothing
else in docmend calls os.replace/os.link on library files. Invariants:

- On ANY failure the target is untouched and the temp file is removed
  (ERR-003: "temp file cleaned up; original untouched").
- clobber=False publishes via os.link + unlink-temp: atomic on POSIX and
  EEXIST-safe against a target appearing between the collision check and the
  publish (the TOCTOU window os.replace cannot close). FileExistsError is
  deliberately NOT wrapped — the caller maps it to the collision policy.
- Parent-directory fsync is best-effort ("where practical", D-004): some
  filesystems refuse O_RDONLY dir fsync; durability of the rename itself is
  then the mount's problem, not a docmend error.
"""

import os
from pathlib import Path


class WriteError(Exception):
    """A mutation failed environmentally (ERR-003); the original is intact."""


def fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _write_temp(target: Path, data: bytes, mode: int | None) -> Path:
    tmp = target.with_name(f".{target.name}.docmend-tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, mode & 0o7777)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return tmp


def atomic_write_bytes(
    target: Path, data: bytes, *, mode: int | None = None, clobber: bool = True
) -> None:
    """Write `data` to `target` with no partial-write window (NFR-002)."""
    try:
        tmp = _write_temp(target, data, mode)
    except OSError as exc:
        msg = f"{target}: cannot stage write ({exc.strerror or exc})"
        raise WriteError(msg) from exc
    try:
        if clobber:
            os.replace(tmp, target)
        else:
            os.link(tmp, target)  # FileExistsError on a collision race — caller's policy
            tmp.unlink()
    except FileExistsError:
        tmp.unlink(missing_ok=True)
        raise
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        msg = f"{target}: cannot publish write ({exc.strerror or exc})"
        raise WriteError(msg) from exc
    fsync_dir(target.parent)


def link_no_clobber(source: Path, target: Path) -> None:
    """Give `source`'s inode a second name at `target`, refusing an existing
    target. The lossless half of a rename: after it, BOTH names exist."""
    try:
        os.link(source, target)
    except FileExistsError:
        raise
    except OSError as exc:
        msg = f"{target}: cannot link rename target ({exc.strerror or exc})"
        raise WriteError(msg) from exc


def rename_no_clobber(source: Path, target: Path) -> None:
    """Move `source` to `target`, refusing an existing target (FR-011).

    link + unlink instead of check-then-os.replace: link is atomic and
    EEXIST-safe; a crash between the two calls leaves BOTH names pointing at
    one intact inode — recoverable, never lossy. v1 renames change only the
    suffix, so source and target always share a directory (same device).
    """
    link_no_clobber(source, target)
    try:
        source.unlink()
    except OSError as exc:
        # Roll the link back so a failed rename leaves the exact pre-action
        # state (codex CR-NEW-004 class); if even that fails, both names
        # remain on one intact inode — superset, lossless, and said so.
        residue = ""
        try:
            target.unlink()
        except OSError:
            residue = f"; rollback failed, {target} remains as a second name"
        msg = f"{source}: rename linked but source not removed ({exc.strerror or exc}){residue}"
        raise WriteError(msg) from exc
    fsync_dir(target.parent)


def rename_overwrite(source: Path, target: Path) -> None:
    """Move `source` onto an existing `target` (FR-011 overwrite policy only).

    The one deliberate clobber in the writer (codex CR-NEW-001): the same
    os.replace + parent-fsync + WriteError contract as every other mutation —
    an overwrite rename must not have weaker crash-durability than a
    no-clobber one. Callers have already backed up the clobbered target.
    """
    try:
        os.replace(source, target)
    except OSError as exc:
        msg = f"{target}: cannot replace with {source} ({exc.strerror or exc})"
        raise WriteError(msg) from exc
    fsync_dir(target.parent)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/writer/test_atomic.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/writer/atomic.py tests/unit/writer/test_atomic.py
git commit -m "feat: atomic write/rename primitives - temp+fsync+replace, link-based no-clobber (NFR-002)"
```

---

### Task 7: Backup module — verify-then-mutate (FR-006, ERR-004)

**Files:**

- Create: `src/docmend/writer/backup.py`
- Test: `tests/unit/writer/test_backup.py`

**Interfaces:**

- Consumes: `atomic.atomic_write_bytes`, `fsync_dir`.
- Produces (used by Task 9): `BackupError(Exception)` (ERR-004); `backup_file(data: bytes, *, backup_root: Path, run_id: str, relative_path: str, expected_sha256: str) -> Path` — writes `backup_root/run_id/relative_path`, fsyncs, **re-reads from disk**, re-hashes, compares to the plan's recorded hash, returns the absolute backup path; raises `BackupError` on any failure **before the original is ever touched**.

- [ ] **Step 1: Write the failing tests** — `tests/unit/writer/test_backup.py`:

```python
"""Backup verify-then-mutate (FR-006, ERR-004, adr-0004).

The re-read/re-hash step is the point: a silently corrupted or short backup
must abort the mutation BEFORE the original is touched, or there is no
recoverable copy at all. Real filesystem (OQ-019).
"""

import hashlib
from pathlib import Path

import pytest

from docmend.writer import backup

RUN_ID = "run_20260706T000000Z_00007e"


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def test_backup__written_verified_and_returned(tmp_path: Path) -> None:
    data = b"payload bytes\n"
    dest = backup.backup_file(
        data,
        backup_root=tmp_path / "backups",
        run_id=RUN_ID,
        relative_path="sub/a.txt",
        expected_sha256=_sha(data),
    )
    assert dest == (tmp_path / "backups" / RUN_ID / "sub" / "a.txt").resolve()
    assert dest.is_absolute()  # CR-005: manifest backup paths must survive cwd changes
    assert dest.read_bytes() == data


def test_backup_hash_mismatch__raises_before_mutation(tmp_path: Path) -> None:
    """ERR-004: a backup whose re-hash does not match the plan's source hash aborts."""
    data = b"payload"
    with pytest.raises(backup.BackupError):
        backup.backup_file(
            data,
            backup_root=tmp_path / "backups",
            run_id=RUN_ID,
            relative_path="a.txt",
            expected_sha256=_sha(b"different"),
        )


def test_backup_reread_corruption__raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A backup that reads back different bytes (bad disk, races) is ERR-004."""
    data = b"payload"
    real_read_bytes = Path.read_bytes

    def corrupt(self: Path) -> bytes:
        return b"corrupt" if self.name == "a.txt" else real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", corrupt)
    with pytest.raises(backup.BackupError):
        backup.backup_file(
            data,
            backup_root=tmp_path / "backups",
            run_id=RUN_ID,
            relative_path="a.txt",
            expected_sha256=_sha(data),
        )


def test_backup_destination_unwritable__raises(tmp_path: Path) -> None:
    root = tmp_path / "backups"
    root.mkdir()
    root.chmod(0o500)
    try:
        with pytest.raises(backup.BackupError):
            backup.backup_file(
                b"x",
                backup_root=root,
                run_id=RUN_ID,
                relative_path="a.txt",
                expected_sha256=_sha(b"x"),
            )
    finally:
        root.chmod(0o700)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/writer/test_backup.py -x -q` Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `src/docmend/writer/backup.py`:

```python
"""Tool-written backups — verify-then-mutate (FR-006, ERR-004, adr-0004).

Layout: <backup_root>/<run_id>/<relative_path> — run-keyed so repeated runs
never clobber each other's copies, mirroring §7.4 retention (the tool never
deletes its own backups). The gate (Task 8) has already proven backup_root
lies OUTSIDE the mutation target and is writable (OQ-005).

Sequence per FR-006: write the copy, fsync it, RE-READ it from disk, re-hash,
compare to the plan's recorded source hash — only then may the caller touch
the original. Any failure raises BackupError (ERR-004) with the original
still untouched.
"""

import hashlib
from pathlib import Path

from docmend.writer.atomic import WriteError, atomic_write_bytes


class BackupError(Exception):
    """Backup copy or verification failed (ERR-004); the original is untouched."""


def backup_file(
    data: bytes, *, backup_root: Path, run_id: str, relative_path: str, expected_sha256: str
) -> Path:
    dest = backup_root / run_id / relative_path
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(dest, data)
    except (OSError, WriteError) as exc:
        msg = f"{dest}: backup copy failed ({exc})"
        raise BackupError(msg) from exc
    try:
        reread = dest.read_bytes()
    except OSError as exc:
        msg = f"{dest}: backup unreadable after write ({exc.strerror or exc})"
        raise BackupError(msg) from exc
    digest = f"sha256:{hashlib.sha256(reread).hexdigest()}"
    if digest != expected_sha256:
        msg = (
            f"{dest}: backup verification failed — re-hash {digest} does not match "
            f"the plan's recorded source hash {expected_sha256} (ERR-004)"
        )
        raise BackupError(msg)
    # Absolute by contract (codex CR-005): this path lands in the manifest,
    # which restore must be able to follow from any cwd (IR-008).
    return dest.resolve()
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/writer/test_backup.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/writer/backup.py tests/unit/writer/test_backup.py
git commit -m "feat: verify-then-mutate tool backups (FR-006/ERR-004)"
```

---

### Task 8: Safety gate — pure predicates + pairwise tests (FR-005, adr-0004)

**Files:**

- Create: `src/docmend/writer/gate.py`
- Test: `tests/test_gate.py`

**Interfaces:**

- Consumes: `Plan`, `PlanAction` from `docmend.plan`; `DocmendConfig`.
- Produces (used by Task 10):
  - `ApplyOptions(write: bool, backup_root: Path | None, preserved_by: str | None, allow_no_backup: bool)` (frozen dataclass; `preserved_by` carries the CLI enum's value, "git"/"external").
  - `GateRefusal(predicate: str, message: str)` (frozen dataclass).
  - `is_content_rewrite(action: PlanAction) -> bool`.
  - `evaluate_gate(plan: Plan, config: DocmendConfig, *, source_root: Path, options: ApplyOptions, manifest_dir: Path) -> list[GateRefusal]` — pure predicate sweep; empty list ⇒ the write may proceed. Every refusal is exit 3.

- [ ] **Step 1: Write the failing tests** — `tests/test_gate.py`. Build plans with a tiny helper (mirror `tests/test_plan_artifact.py`'s construction style) producing (a) a single rename-only action, (b) a single content-rewrite action, (c) three content-rewrite actions. Core cases:

```python
"""Apply safety gate (FR-005, OQ-005/adr-0004, OQ-035 risk tiers).

Pure independent predicates; every failing predicate refuses with exit 3
(mapped by the CLI). Pairwise coverage over the predicate space per §17.2
Operations row (allpairspy, t=3 for the preservation/manifest/backup trio).
"""
```

- `test_content_rewrite_without_strategy__refused` — plan (b), no backup_root, no preserved_by, no opt-in → one refusal with `predicate == "preservation"` (FR-005 acceptance: exits non-zero, writes nothing).
- `test_content_rewrite_with_backup_dir__passes` — plan (b), `backup_root=tmp_path / "backups"` (outside root) → `[]`.
- `test_content_rewrite_with_declared_preservation__passes` — plan (b), `preserved_by="git"` → `[]`.
- `test_single_action_opt_in__passes` — plan (b), `allow_no_backup=True` → `[]` (FR-005 low-risk opt-in; NFR-006/G-006).
- `test_multi_action_opt_in__refused` — plan (c), `allow_no_backup=True` → refusal `preservation` ("limited to single-action plans").
- `test_rename_only_plan__needs_no_strategy` — plan (a), nothing active → `[]` (OQ-035 risk tier: manifest suffices for pure path moves).
- `test_manifest_only_configuration__does_not_satisfy_preservation` — plan (c) with no strategy → refused (FR-005 acceptance criterion, verbatim case).
- `test_backup_dir_inside_target__refused_and_nothing_created` — `backup_root=source_root / "backups"` (path does **not** exist) → refusal `backup-outside-target` AND `source_root / "backups"` still does not exist afterwards (codex CR-002: a refusal must not mkdir inside the library). Also snapshot `source_root`'s full recursive listing before/after `evaluate_gate` and assert equality.
- `test_backup_dir_unwritable__refused` — chmod 0o500 dir → refusal `backup-writable`.
- `test_manifest_dir_unwritable__refused` — chmod 0o500 manifest_dir → refusal `manifest-writable`.
- `test_disk_preflight__refused_when_backup_mount_too_small` — monkeypatch `gate.shutil.disk_usage` to return `free=1` → refusal `disk-preflight` (OQ-005).
- `test_disk_preflight__counts_overwrite_targets_and_output_growth` (codex CR-006) — overwrite policy with a live-colliding target larger than every source: monkeypatch `disk_usage` so free space covers `sum(sources)` but not `sum(sources) + target_size` → refusal; and a single-action plan where free space covers the source size but not `source × 3` → refusal (the re-encode growth bound).
- `test_overwrite_policy_with_live_collision__requires_strategy` — plan (b variant with `target_path` whose file exists on disk), snapshot `rename.on_collision="overwrite"`, no strategy → refusal `overwrite-preservation` (G-002); with `preserved_by="external"` → `[]`.
- `test_containment_belt__escaping_target_refused` — hand-build a `PlanAction` via `model_construct(...)` (bypassing validators, simulating a crafted artifact that slipped a symlink-free `..`) with `target_path="../escape.md"` → refusal `containment`.
- `test_gate_pairwise__every_failing_predicate_refuses` — allpairspy sweep:

```python
from allpairspy import AllPairs

PRESERVATION = ["none", "backup_dir", "preserved_by", "opt_in"]
PLAN_SHAPE = ["single_rewrite", "multi_rewrite", "single_rename_only"]
MANIFEST_DIR = ["writable", "unwritable"]
BACKUP_DEST = ["outside", "inside_target", "unwritable"]


@pytest.mark.parametrize(
    "preservation,plan_shape,manifest_dir,backup_dest",
    list(AllPairs([PRESERVATION, PLAN_SHAPE, MANIFEST_DIR, BACKUP_DEST], n=3)),
)
def test_gate_pairwise__every_failing_predicate_refuses(
    tmp_path: Path, preservation: str, plan_shape: str, manifest_dir: str, backup_dest: str
) -> None:
    """§17.2 Operations row: t=3 pairwise over the preservation/manifest/backup trio."""
    # Arrange per the combo, call evaluate_gate, then assert refusals == the
    # independently derived expectation:
    #   expect "preservation" iff plan has content rewrites and preservation
    #     in {"none"} or (== "opt_in" and plan is multi-action);
    #   expect "backup-outside-target"/"backup-writable" iff preservation == "backup_dir"
    #     and backup_dest is "inside_target"/"unwritable";
    #   expect "manifest-writable" iff manifest_dir == "unwritable".
    # The oracle is spelled out inline — no re-derivation from gate internals.
```

(backup_dest is only wired when `preservation == "backup_dir"`; otherwise pass `backup_root=None` and expect no backup refusals.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_gate.py -x -q` Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `src/docmend/writer/gate.py`:

```python
"""Apply safety gate — pure independent predicates (FR-005, OQ-005, adr-0004).

Evaluated before any non-dry-run mutation; each predicate is independent and
side-effect-light (writability probes create/remove one probe file) so the set
is combinatorially testable (allpairspy, §17.2). Empty result ⇒ proceed; any
refusal ⇒ exit 3 and the library is untouched.

Risk tiers (OQ-035 proposal): content rewrites need an active byte-preserving
strategy (tool backups or a declared git/external strategy) unless the plan is
a single action under the explicit --allow-no-backup opt-in; rename-only runs
are undoable from the manifest alone; a run that would actually overwrite an
existing target destroys that target's bytes and therefore needs a strategy
regardless (G-002).
"""

import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from docmend.config import DocmendConfig
from docmend.plan import Plan, PlanAction


@dataclass(frozen=True)
class ApplyOptions:
    write: bool
    backup_root: Path | None
    # str, not Literal["git","external"]: the CLI's PreservedBy enum .value is
    # typed str, and the gate only ever tests "is a strategy declared at all".
    preserved_by: str | None
    allow_no_backup: bool


@dataclass(frozen=True)
class GateRefusal:
    predicate: str
    message: str


def is_content_rewrite(action: PlanAction) -> bool:
    """OQ-035 risk tier: any operation beyond a pure path rename rewrites content."""
    return any(op != "rename" for op in action.operations)


def _dir_writable(path: Path) -> bool:
    probe = path / f".docmend-probe-{uuid.uuid4().hex}"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.touch()
        probe.unlink()
    except OSError:
        return False
    return True


def _strategy_active(options: ApplyOptions) -> bool:
    return options.backup_root is not None or options.preserved_by is not None


def _containment(plan: Plan, source_root: Path) -> list[GateRefusal]:
    # Belt over the model validators: normpath-level re-check of every planned
    # path against the root (a crafted plan must fail here even if a reader
    # regression ever let it through). Runtime symlink escapes are the apply
    # loop's resolve() check (decision 12).
    refusals: list[GateRefusal] = []
    root = os.path.normpath(source_root)
    for action in plan.actions:
        for candidate in (action.path, action.target_path):
            if candidate is None:
                continue
            joined = os.path.normpath(os.path.join(root, candidate))
            if os.path.commonpath([root, joined]) != root:
                refusals.append(
                    GateRefusal(
                        predicate="containment",
                        message=f"{candidate}: planned path escapes {source_root} (§8.5/§13.5)",
                    )
                )
    return refusals


def _preservation(plan: Plan, options: ApplyOptions) -> list[GateRefusal]:
    content = [a for a in plan.actions if is_content_rewrite(a)]
    refusals: list[GateRefusal] = []
    if options.allow_no_backup and len(plan.actions) > 1:
        refusals.append(
            GateRefusal(
                predicate="preservation",
                message=(
                    "--allow-no-backup is the FR-005 low-risk opt-in and is limited to "
                    "single-action plans; this plan has "
                    f"{len(plan.actions)} actions"
                ),
            )
        )
    if content and not _strategy_active(options):
        if options.allow_no_backup and len(plan.actions) == 1:
            return refusals
        refusals.append(
            GateRefusal(
                predicate="preservation",
                message=(
                    "content-changing rewrite with no byte-preserving strategy: enable "
                    "tool backups (--backup-dir / write.backup_dir), declare one "
                    "(--preserved-by git|external), or use --allow-no-backup for a "
                    "single-file low-risk run (FR-005; the manifest alone is rollback "
                    "metadata, not preservation)"
                ),
            )
        )
    return refusals


def _overwrite_preservation(
    plan: Plan, config: DocmendConfig, source_root: Path, options: ApplyOptions
) -> list[GateRefusal]:
    if config.rename.on_collision != "overwrite" or _strategy_active(options):
        return []
    clobbers = [
        a.target_path
        for a in plan.actions
        if a.target_path is not None and (source_root / a.target_path).exists()
    ]
    if not clobbers:
        return []
    return [
        GateRefusal(
            predicate="overwrite-preservation",
            message=(
                f"overwrite collision policy would destroy {len(clobbers)} existing "
                "target file(s) with no byte-preserving strategy active (G-002, FR-011)"
            ),
        )
    ]


def _backup_destination(
    plan: Plan, config: DocmendConfig, source_root: Path, options: ApplyOptions
) -> list[GateRefusal]:
    if options.backup_root is None:
        return []
    resolved = options.backup_root.resolve()
    if resolved.is_relative_to(source_root.resolve()):
        # Short-circuit BEFORE any writability probe (codex CR-002): probing
        # mkdirs the destination, and this destination is inside the library —
        # a refusal must leave the target untouched (§8.5, adr-0004).
        return [
            GateRefusal(
                predicate="backup-outside-target",
                message=f"{options.backup_root}: backup destination lies inside the mutation target (OQ-005, §8.5)",
            )
        ]
    if not _dir_writable(options.backup_root):
        return [
            GateRefusal(
                predicate="backup-writable",
                message=f"{options.backup_root}: backup destination is not writable (OQ-005)",
            )
        ]
    needed = sum(a.source_size_bytes for a in plan.actions)
    if config.rename.on_collision == "overwrite":
        # codex CR-006: overwrite mode also backs up each live-colliding
        # target, so its bytes count against the same mount.
        needed += sum(
            (source_root / a.target_path).stat().st_size
            for a in plan.actions
            if a.target_path is not None and (source_root / a.target_path).exists()
        )
    if shutil.disk_usage(options.backup_root).free < needed:
        return [
            GateRefusal(
                predicate="disk-preflight",
                message=(
                    f"{options.backup_root}: {needed} bytes of backups planned but less "
                    "free space on the destination mount (OQ-005 per-mount preflight)"
                ),
            )
        ]
    return []


def _manifest_destination(manifest_dir: Path) -> list[GateRefusal]:
    if _dir_writable(manifest_dir):
        return []
    return [
        GateRefusal(
            predicate="manifest-writable",
            message=f"{manifest_dir}: manifest destination is not writable (adr-0004: manifest is mandatory rollback metadata)",
        )
    ]


def _source_headroom(plan: Plan, config: DocmendConfig, source_root: Path) -> list[GateRefusal]:
    if not plan.actions:
        return []
    # codex CR-006: transformed output can be LARGER than the input. Bound the
    # mechanical growth instead of assuming size parity: a legacy single-byte
    # encoding re-encodes to at most 3 UTF-8 bytes per byte, and leading-tab
    # expansion multiplies by tab_width; the two maxima cannot compound (tabs
    # are ASCII and re-encode 1:1), so the factor is their max, not product.
    factor = max(3, config.whitespace.tab_width if config.whitespace.normalize_tabs else 1)
    largest = max(a.source_size_bytes for a in plan.actions) * factor
    if shutil.disk_usage(source_root).free >= largest:
        return []
    return [
        GateRefusal(
            predicate="disk-preflight",
            message=(
                f"{source_root}: the largest planned temp file (bounded at {largest} bytes) "
                "exceeds free space on the target mount (OQ-005 per-mount preflight)"
            ),
        )
    ]


def evaluate_gate(
    plan: Plan,
    config: DocmendConfig,
    *,
    source_root: Path,
    options: ApplyOptions,
    manifest_dir: Path,
) -> list[GateRefusal]:
    return [
        *_containment(plan, source_root),
        *_preservation(plan, options),
        *_overwrite_preservation(plan, config, source_root, options),
        *_backup_destination(plan, config, source_root, options),
        *_manifest_destination(manifest_dir),
        *_source_headroom(plan, config, source_root),
    ]
```

- [ ] **Step 4: Run the tests, then the full suite**

Run: `uv run coverage run -m pytest -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/writer/gate.py tests/test_gate.py
git commit -m "feat: apply safety gate - pure predicates, risk-scaled preservation, pairwise-tested (FR-005/adr-0004)"
```

---

### Task 9: Apply engine (FR-003, FR-004, FR-006, FR-011, FR-012, FR-018)

First: the plan artifact must carry `source_root` (decision 3).

**Files:**

- Modify: `src/docmend/schemas/plan.schema.json` (optional `source_root`)
- Modify: `src/docmend/plan.py` (`source_root` field)
- Modify: `src/docmend/planning.py` (populate it)
- Modify: `src/docmend/discovery.py` (export `sniff_bom` — rename `_sniff_bom`, update call sites)
- Create: `src/docmend/writer/apply.py`
- Test: `tests/test_apply.py`

**Interfaces:**

- Consumes: everything from Tasks 4–8; `sniff_bom(header: bytes) -> BomKind | None` from `docmend.discovery`; `decode_source`/`encode_utf8`, `apply_text_transforms`/`classify_suffix`/`non_whitespace_count` from the transform layer.
- Produces (used by Tasks 10–12): `execute_plan(plan: Plan, config: DocmendConfig, *, run_id: str, plan_ref: ArtifactRef, options: ApplyOptions, manifest_path: Path, started_at: str, now: Callable[[], str] = ...) -> Report`. Opens a `ManifestWriter` at `manifest_path` only when `options.write`; the returned `Report` reconciles by construction.

- [ ] **Step 1: Plan carries `source_root`.** In `src/docmend/schemas/plan.schema.json` add to `properties` (NOT `required`):

```json
"source_root": {
    "description": "1.1: absolute source root the action paths are relative to, copied from the consumed inventory — apply resolves files from the plan alone. Optional for schema-compat with 1.0 plans, which apply refuses with ERR-006 (regenerate).",
    "type": "string",
    "minLength": 1
}
```

In `src/docmend/plan.py`, add to `Plan` (after `inventory_ref`):

```python
    source_root: Annotated[str, Field(min_length=1)] | None = None
```

In `src/docmend/planning.py` `build_plan`, two changes:

1. `return Plan(...)` gains `source_root=inventory.source_root,`.
2. The config snapshot pins a relative `write.backup_dir` to the **planning** cwd before serialization (codex CR-NEW-002: the reviewed plan must fully determine where backups go — re-resolving a relative path against the _apply_ cwd would silently move them, or gate-refuse). Immediately before `config.model_dump(mode="json")`:

```python
    if config.write.backup_dir is not None and not config.write.backup_dir.is_absolute():
        # The reviewed snapshot, not apply's cwd, decides the backup home.
        config = config.model_copy(
            update={
                "write": config.write.model_copy(
                    update={"backup_dir": config.write.backup_dir.resolve()}
                )
            }
        )
```

Add assertions to `tests/test_planning.py`: the built plan's `source_root` equals the inventory's, and a config with `write.backup_dir=Path("backups")` snapshots as an absolute path under the planning cwd (`tmp_path` via `monkeypatch.chdir`).

In `src/docmend/discovery.py`, rename `_sniff_bom` → `sniff_bom` (public: apply re-sniffs the BOM from bytes whose hash already matched the scan, so the sniff is provenance-equivalent) and update its internal call site.

- [ ] **Step 2: Write the failing engine tests** — `tests/test_apply.py`. Shared harness:

```python
"""Apply engine (FR-003/FR-004/FR-006/FR-011/FR-012/FR-017-report-half/FR-018,
NFR-002/NFR-004, EC-005, AW-002/AW-004, ERR-002/ERR-003/ERR-004/ERR-005).

End-to-end over real files: scan -> plan -> execute_plan, asserting per-file
outcomes, manifest records, and corpus state. Real filesystem (OQ-019).
"""

import hashlib
from pathlib import Path

import pytest

from docmend import discovery, planning
from docmend.artifacts import sha256_of_file
from docmend.config import DocmendConfig, RenameConfig
from docmend.plan import ArtifactRef, Plan
from docmend.writer.apply import execute_plan
from docmend.writer.gate import ApplyOptions
from docmend.writer.manifest import read_manifest

RUN_ID = "run_20260706T000000Z_00008f"
PLAN_RUN_ID = "run_20260706T000000Z_00008e"
GENERATED_AT = "2026-07-06T00:00:00+00:00"
NOW = "2026-07-06T00:00:01+00:00"


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _plan_for(root: Path, config: DocmendConfig) -> Plan:
    inventory = discovery.scan(root, config, run_id=PLAN_RUN_ID, generated_at=GENERATED_AT)
    ref = ArtifactRef(path="inv.json", run_id=PLAN_RUN_ID, sha256="sha256:" + "0" * 64)
    return planning.build_plan(
        inventory, config, run_id=PLAN_RUN_ID, generated_at=GENERATED_AT, inventory_ref=ref
    )


def _execute(plan: Plan, config: DocmendConfig, tmp_path: Path, **kwargs: object):
    options = ApplyOptions(
        write=bool(kwargs.pop("write", False)),
        backup_root=kwargs.pop("backup_root", None),  # type: ignore[arg-type]
        preserved_by=kwargs.pop("preserved_by", None),  # type: ignore[arg-type]
        allow_no_backup=bool(kwargs.pop("allow_no_backup", False)),
    )
    assert not kwargs
    return execute_plan(
        plan,
        config,
        run_id=RUN_ID,
        plan_ref=ArtifactRef(path="plan.json", run_id=PLAN_RUN_ID, sha256="sha256:" + "1" * 64),
        options=options,
        manifest_path=tmp_path / "manifest.jsonl",
        started_at=GENERATED_AT,
        now=lambda: NOW,
    )
```

Cases (each its own test function, docstrings citing the IDs shown):

1. `test_dry_run_default__writes_nothing_reports_would_apply` (FR-004, NFR-004): corpus of one CRLF `.txt`; hash-snapshot every file; execute with `write=False`; assert all hashes unchanged, no manifest file exists, single outcome `would_apply` with `after_sha256 is None`, `report.dry_run is True`, totals reconcile.
2. `test_write_rewrite_in_place__utf8_lf_and_manifest` (FR-006, FR-008, NFR-002, DR-004): a CRLF windows-1252 `.md` file (no rename — `.md` keeps its path); execute with `write=True, backup_root=...`; assert file bytes are the UTF-8/LF transform result, outcome `applied` with correct before/after hashes, manifest has one `rewrite` record whose `backup_path` exists and whose backup bytes hash to `before_sha256`, and `after_sha256 == sha256_of_file(the file)`.
3. `test_write_rename_only__link_semantics` (FR-010, FR-011): an already-clean LF `.txt` (rename is the only op); write with no strategy (rename-only tier); assert old path gone, new `.md` path has identical bytes/hash, manifest record `operation == "rename"`, `after_sha256 == before_sha256`.
4. `test_write_rename_and_rewrite__source_survives_failure` (NFR-002): CRLF `.txt` → rename+rewrite; monkeypatch `docmend.writer.apply.atomic_write_bytes` to raise `WriteError`; outcome `failed` with `error.error_class == "ERR-003"`, source file untouched, manifest records `result == "failed"`, `after_sha256 is None`.
5. `test_stale_hash__skipped_batch_continues` (FR-003, ERR-002, AW-004): two-action plan; mutate file A after planning; execute write; A → `skipped`/`stale-hash`, B → `applied`; A's bytes untouched.
6. `test_unreadable_at_apply__skipped` (ERR-005): delete file A after planning; outcome `skipped`/`unreadable`.
7. `test_collision_policies__skip_fail_overwrite` (FR-011, AW-002, EC-001): plan a `.txt`→`.md` rename, then create the target `.md` after planning. `skip` → outcome `skipped`/`collision`, target untouched; `fail` → outcome `skipped`/`collision` and NO later actions executed (assert a second action never ran); `overwrite` with `backup_root` → outcome `applied`, manifest record carries `overwritten_sha256` = clobbered target's hash and an existing `overwritten_backup_path` whose bytes match.
8. `test_backup_failure__aborts_before_original_touched` (FR-006, ERR-004): monkeypatch `docmend.writer.apply.backup_file` to raise `BackupError`; outcome `failed`/`ERR-004`; source bytes unchanged.
9. `test_snapshot_filter_enforced__foreign_action_excluded` (FR-012): take a valid plan, `model_copy` its action with `path` untouched but tighten the snapshot config's include to `["**/*.rst"]` via a rebuilt plan config dict; outcome `skipped`/`excluded`.
10. `test_shrink_invariant_recheck__skips` (EC-005): monkeypatch `docmend.writer.apply.apply_text_transforms` to return a shrunk string; outcome `skipped`/`shrink-invariant`, file untouched.
11. `test_operations_divergence__failed_err006` (decision 4): monkeypatch the transform to return different text (same length class) so recomputed operations ≠ plan's; outcome `failed`/`ERR-006`.
12. `test_containment_resolve_escape__skipped` (§13.5): after planning, replace the file's parent directory with a symlink to a directory outside the root; outcome `skipped`/`containment`; nothing outside the root written.
13. `test_report_counts_reconcile__and_manifest_seq_monotonic` (FR-018, DR-003, DR-004): mixed corpus; assert `totals` equals a `Counter` over outcomes and manifest `seq` is 1..N in order.
14. `test_empty_plan__clean_report` : plan over an already-clean corpus (zero actions); write mode with no strategy; report has zero outcomes, and **no manifest file exists** (lazy-open contract).
15. `test_dry_run_overwrite_collision_with_backup_dir__writes_nothing` (codex CR-001; FR-004, NFR-004): config snapshot with `rename.on_collision="overwrite"` **and** `write.backup_dir` set; create the colliding target after planning; execute with `write=False` and `backup_root` populated from the snapshot. Assert: outcome `would_apply`, the backup directory was never created, and a full recursive hash snapshot of `tmp_path` (corpus + would-be backup location) is unchanged except for report/log artifacts.
16. `test_all_actions_skip_in_write_mode__no_manifest_file`: two-action plan, both files mutated after planning (stale-hash); write mode with backups; assert no manifest file is created and exit-relevant totals show 2 skips.
17. `test_rename_and_rewrite_unlink_failure__publish_rolled_back` (codex CR-NEW-004): monkeypatch `Path.unlink` to raise `OSError` for the source path only; write mode with backups over a rename+rewrite action → outcome `failed`/`ERR-003`, manifest record `result == "failed"`, AND the corpus is byte-for-byte unchanged (the published target was rolled back; report/manifest/corpus agree). Repeat under `overwrite` policy with a live collision: the clobbered target's original bytes are back in place after the rollback.

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_apply.py -x -q` Expected: FAIL — `docmend.writer.apply` missing.

- [ ] **Step 4: Implement** `src/docmend/writer/apply.py`:

```python
"""Apply engine — executes a reviewed plan through the writer layer.

Architectural role (§8.2.3): the ONLY orchestration that mutates the library,
and only via the atomic/backup primitives in this package. The plan's config
snapshot is authoritative (decision 3): transforms, filters, and collision
policy come from the plan, never the live config — that is what makes the
reviewed plan the thing that actually executes (D-006, C.4).

Per-action contract (decisions 4-9): re-read -> re-hash (FR-003) -> snapshot
filters (FR-012) -> resolve-containment (§13.5) -> recompute transforms and
cross-check operations -> EC-005 re-check -> collision policy (FR-011) ->
[dry-run stops here] -> verify-then-mutate backup (FR-006) -> atomic mutation
(NFR-002) -> fsync'd manifest record (DR-004) -> outcome (DR-003). Failures
never abort the batch except the 'fail' collision policy (AW-002); every
failure class maps to §12.1.
"""

import hashlib
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from docmend import __version__
from docmend.config import DocmendConfig
from docmend.discovery import sniff_bom
from docmend.observability import get_logger
from docmend.plan import ArtifactRef, Plan, PlanAction
from docmend.report import (
    ApplyOutcome,
    ApplySkipReason,
    ErrorInfo,
    Report,
    ReportTotals,
)
from docmend.transform.dispatch import (
    Operation,
    apply_text_transforms,
    classify_suffix,
    non_whitespace_count,
)
from docmend.transform.encoding import decode_source, encode_utf8
from docmend.writer.atomic import (
    WriteError,
    atomic_write_bytes,
    rename_no_clobber,
    rename_overwrite,
)
from docmend.writer.backup import BackupError, backup_file
from docmend.writer.gate import ApplyOptions, is_content_rewrite
from docmend.writer.manifest import ManifestOperation, ManifestRecord, ManifestWriter


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _skip(action: PlanAction, reason: ApplySkipReason) -> ApplyOutcome:
    return ApplyOutcome(
        action_id=action.action_id,
        path=action.path,
        status="skipped",
        before_sha256=action.source_sha256,
        after_sha256=None,
        skip_reason=reason,
        error=None,
    )


def _failed(action: PlanAction, error_class: str, message: str) -> ApplyOutcome:
    return ApplyOutcome(
        action_id=action.action_id,
        path=action.path,
        status="failed",
        before_sha256=action.source_sha256,
        after_sha256=None,
        skip_reason=None,
        error=ErrorInfo(error_class=error_class, message=message),
    )


def _operation_kind(action: PlanAction) -> ManifestOperation:
    renames = "rename" in action.operations
    if renames and is_content_rewrite(action):
        return "rename_and_rewrite"
    return "rename" if renames else "rewrite"


def _recompute(
    action: PlanAction, data: bytes, config: DocmendConfig
) -> tuple[bytes, list[Operation]] | str:
    """Re-derive the output bytes and operation list; a str return is an error message."""
    bom = sniff_bom(data[:4])
    detected = action.provenance.detected_encoding
    encoding_name = detected.name if detected is not None else "utf-8"
    try:
        text = decode_source(data, bom=bom, encoding_name=encoding_name)
    except (UnicodeDecodeError, LookupError) as exc:
        return f"decode diverged from plan ({exc})"  # unreachable: hash matched (decision 4)
    ws = config.whitespace
    transformed, text_ops = apply_text_transforms(
        text,
        classify_suffix(action.path[action.path.rfind(".") :] if "." in action.path.rsplit("/", 1)[-1] else ""),
        trim_trailing_ws=ws.trim_trailing,
        final_newline=ws.ensure_final_newline,
        collapse_max=ws.collapse_blank_lines,
        tab_width=ws.tab_width if ws.normalize_tabs else None,
    )
    if non_whitespace_count(transformed) < non_whitespace_count(text):
        return "shrink-invariant"
    operations: list[Operation] = []
    if bom is not None or encoding_name != "utf-8":
        operations.append("reencode")
    operations.extend(text_ops)
    if action.target_path is not None:
        operations.append("rename")
    if operations != action.operations:
        return f"recomputed operations {operations} != planned {action.operations}"
    return encode_utf8(transformed), operations
```

(The suffix expression above is awkward inline — implement it as a small helper `_suffix(path: str) -> str` returning the final `.ext` of the basename or `""`, matching `FileRecord.suffix` semantics from discovery. Keep `classify_suffix(_suffix(action.path))`.)

```python
def execute_plan(
    plan: Plan,
    config: DocmendConfig,
    *,
    run_id: str,
    plan_ref: ArtifactRef,
    options: ApplyOptions,
    manifest_path: Path,
    started_at: str,
    now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(),
) -> Report:
    log = get_logger(__name__)
    assert plan.source_root is not None  # CLI refused earlier (ERR-006)
    source_root = Path(plan.source_root)
    root_resolved = source_root.resolve()
    include = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.include)
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude)

    outcomes: list[ApplyOutcome] = []
    manifest: ManifestWriter | None = None
    if options.write and plan.actions:
        manifest = ManifestWriter(manifest_path, run_id=run_id, now=now)
    try:
        abort = False
        for action in plan.actions:
            if abort:
                break
            outcome, abort = _execute_action(
                action, source_root, root_resolved, config, options,
                include, exclude, manifest, run_id, log,
            )
            outcomes.append(outcome)
            log.info(
                "apply outcome",
                path=action.path,
                status=outcome.status,
                reason=outcome.skip_reason,
                action=action.action_id,
            )
    finally:
        if manifest is not None:
            manifest.close()

    counts = Counter(outcome.status for outcome in outcomes)
    return Report(
        run_id=run_id,
        generated_by=f"docmend {__version__}",
        plan_ref=plan_ref,
        dry_run=not options.write,
        started_at=started_at,
        completed_at=now(),
        outcomes=outcomes,
        totals=ReportTotals(
            applied=counts.get("applied", 0),
            would_apply=counts.get("would_apply", 0),
            skipped=counts.get("skipped", 0),
            failed=counts.get("failed", 0),
        ),
    )
```

`_execute_action` (returns `(outcome, abort)`):

```python
def _execute_action(
    action: PlanAction,
    source_root: Path,
    root_resolved: Path,
    config: DocmendConfig,
    options: ApplyOptions,
    include: PathSpec[GitIgnoreSpecPattern],
    exclude: PathSpec[GitIgnoreSpecPattern],
    manifest: ManifestWriter | None,
    run_id: str,
    log: object,
) -> tuple[ApplyOutcome, bool]:
    source = source_root / action.path
    # FR-003: the plan's decision only executes against the exact bytes it saw.
    try:
        data = source.read_bytes()
    except OSError:
        return _skip(action, "unreadable"), False  # ERR-005
    if _sha(data) != action.source_sha256:
        return _skip(action, "stale-hash"), False  # ERR-002, AW-004
    # FR-012: snapshot filters hold at apply exactly as at scan/plan.
    if not include.match_file(action.path) or exclude.match_file(action.path):
        return _skip(action, "excluded"), False
    # §13.5 runtime containment: a parent dir swapped for a symlink since plan
    # time must not carry the write outside the root.
    target = source_root / action.target_path if action.target_path is not None else None
    for candidate in (source, *((target,) if target is not None else ())):
        if not candidate.resolve().is_relative_to(root_resolved):
            return _skip(action, "containment"), False

    recomputed = _recompute(action, data, config)
    if recomputed == "shrink-invariant":
        return _skip(action, "shrink-invariant"), False  # EC-005 apply half
    if isinstance(recomputed, str):
        return _failed(action, "ERR-006", recomputed), False
    payload, _operations = recomputed
    kind = _operation_kind(action)

    clobber = False
    if target is not None and target.exists():
        policy = config.rename.on_collision
        if policy == "skip":
            return _skip(action, "collision"), False  # AW-002
        if policy == "fail":
            return _skip(action, "collision"), True  # non-zero abort (FR-011)
        clobber = True  # policy == "overwrite"

    if not options.write:
        # Dry-run boundary (codex CR-001): collision state was INSPECTED above,
        # but nothing past this line may run — in particular no backup_file
        # call for a would-be-clobbered target. FR-004/NFR-004: a dry run
        # writes nothing but its report and log.
        return (
            ApplyOutcome(
                action_id=action.action_id,
                path=action.path,
                status="would_apply",
                before_sha256=action.source_sha256,
                after_sha256=None,
                skip_reason=None,
                error=None,
            ),
            False,
        )

    overwritten_sha: str | None = None
    overwritten_backup: Path | None = None
    target_bytes: bytes | None = None  # clobbered content, kept for CR-NEW-004 rollback
    if clobber:
        assert target is not None
        try:
            target_bytes = target.read_bytes()
        except OSError as exc:
            return _failed(action, "ERR-003", f"{target}: unreadable for overwrite backup ({exc})"), False
        overwritten_sha = _sha(target_bytes)
        if options.backup_root is not None:
            try:
                overwritten_backup = backup_file(
                    target_bytes,
                    backup_root=options.backup_root,
                    run_id=run_id,
                    relative_path=str(action.target_path),
                    expected_sha256=overwritten_sha,
                )
            except BackupError as exc:
                return _failed(action, "ERR-004", str(exc)), False

    backup_path: Path | None = None
    if options.backup_root is not None:
        try:
            backup_path = backup_file(
                data,
                backup_root=options.backup_root,
                run_id=run_id,
                relative_path=action.path,
                expected_sha256=action.source_sha256,
            )
        except BackupError as exc:
            outcome = _failed(action, "ERR-004", str(exc))  # backup abort, original untouched
            _record(manifest, action, kind, source, target, backup_path, None,
                    overwritten_sha, overwritten_backup, run_id, outcome)
            return outcome, False

    content = is_content_rewrite(action)
    after = _sha(payload) if content else action.source_sha256
    try:
        mode = source.stat().st_mode
        if kind == "rewrite":
            atomic_write_bytes(source, payload, mode=mode)
        elif kind == "rename":
            assert target is not None
            if clobber:
                rename_overwrite(source, target)  # codex CR-NEW-001: fsync'd, WriteError-wrapped
            else:
                rename_no_clobber(source, target)
        else:  # rename_and_rewrite
            assert target is not None
            atomic_write_bytes(target, payload, mode=mode, clobber=clobber)
            try:
                source.unlink()
            except OSError as unlink_exc:
                # codex CR-NEW-004: the target is already published; recording
                # "failed" while the corpus changed would make the report and
                # manifest lie. Roll the publish back to the exact pre-action
                # state (rewrite the clobbered bytes, or remove the published
                # target), then fail honestly with the original untouched.
                try:
                    if target_bytes is not None:
                        atomic_write_bytes(target, target_bytes)
                    else:
                        target.unlink()
                except (WriteError, OSError):
                    log.error(
                        "apply residue: target published, source not removed, rollback failed",
                        path=action.path,
                        target=str(target),
                    )
                msg = (
                    f"{source}: target published but source not removed; publish "
                    f"rolled back ({unlink_exc.strerror or unlink_exc})"
                )
                raise WriteError(msg) from unlink_exc
    except FileExistsError:
        return _skip(action, "collision"), False  # no-clobber race lost (FR-011)
    except (WriteError, OSError) as exc:
        outcome = _failed(action, "ERR-003", str(exc))
        _record(manifest, action, kind, source, target, backup_path, None,
                overwritten_sha, overwritten_backup, run_id, outcome)
        return outcome, False

    outcome = ApplyOutcome(
        action_id=action.action_id,
        path=action.path,
        status="applied",
        before_sha256=action.source_sha256,
        after_sha256=after,
        skip_reason=None,
        error=None,
    )
    _record(manifest, action, kind, source, target, backup_path, after,
            overwritten_sha, overwritten_backup, run_id, outcome)
    return outcome, False
```

and the shared record helper:

```python
def _record(
    manifest: ManifestWriter | None,
    action: PlanAction,
    kind: ManifestOperation,
    source: Path,
    target: Path | None,
    backup_path: Path | None,
    after: str | None,
    overwritten_sha: str | None,
    overwritten_backup: Path | None,
    run_id: str,
    outcome: ApplyOutcome,
) -> None:
    if manifest is None:
        return
    manifest.append(
        ManifestRecord(
            run_id=run_id,
            action_id=action.action_id,
            docmend_id=action.docmend_id,
            seq=1,  # stamped by the writer
            recorded_at="",  # stamped by the writer
            operation=kind,
            original_path=str(source.resolve()),
            target_path=str((target if target is not None else source).resolve()),
            backup_path=str(backup_path) if backup_path is not None else None,
            before_sha256=action.source_sha256,
            after_sha256=after,
            result="applied" if outcome.status == "applied" else "failed",
            error=outcome.error,
            overwritten_sha256=overwritten_sha,
            overwritten_backup_path=str(overwritten_backup) if overwritten_backup is not None else None,
        )
    )
```

Notes for the implementer: (a) every mutation goes through a `docmend.writer.atomic` primitive — no inline `os.replace`/`os.link` calls in the engine (codex CR-NEW-001); (b) `recorded_at=""` fails the model's own validation — give `ManifestRecord.recorded_at` a `str` type with no format constraint (it already is) and pass `recorded_at="1970-01-01T00:00:00+00:00"` as the placeholder the writer overwrites, or make `ManifestWriter.append` accept the fields as kwargs instead of a pre-built record — pick ONE and keep Task 5's tests consistent (the pre-built-record + `model_copy` stamp approach from Task 5 is the contract; use a valid placeholder timestamp); (c) `resolve()` on `original_path`/`target_path` happens **before** mutation for the target (it may not exist yet — `Path.resolve()` handles non-existent tails without error, which is exactly what we want); (d) the `fail`-policy abort must come **after** the outcome is recorded so the report shows the collision; unprocessed actions simply have no outcome (DR-003 reconciliation still holds).

- [ ] **Step 5: Run the tests, then the full suite**

Run: `uv run coverage run -m pytest -q` Expected: PASS. `basedpyright` strict will police the `log: object` parameter — type it `structlog.stdlib.BoundLogger`.

- [ ] **Step 6: Commit**

```bash
git add src/docmend/schemas/plan.schema.json src/docmend/plan.py src/docmend/planning.py \
        src/docmend/discovery.py src/docmend/writer/apply.py tests/test_apply.py tests/test_planning.py
git commit -m "feat: apply engine - hash-guarded, snapshot-driven, atomic, manifest-recorded (FR-003..FR-006, FR-011)"
```

---

### Task 10: `docmend apply` CLI (IR-003, IR-005, FR-004, FR-018, NFR-004)

**Files:**

- Modify: `src/docmend/cli.py`
- Test: `tests/test_cli_apply.py`

**Interfaces:**

- Consumes: `execute_plan`, `evaluate_gate`, `ApplyOptions`, `lock`, `artifacts.read_plan`/`write_report`/`sha256_of_file`.
- Produces: the `apply` command per IR-003: `docmend apply PLAN [--write | --dry-run] [--backup-dir PATH] [--preserved-by git|external] [--allow-no-backup] [--report FILE]`.

- [ ] **Step 1: Write the failing CLI tests** — `tests/test_cli_apply.py` (CliRunner + the `isolate_logging`/`corpus` fixture pattern from `tests/test_cli_scan.py`, with `XDG_STATE_HOME` monkeypatched into `tmp_path`):

```python
"""`docmend apply` CLI tests (IR-003, IR-005, FR-004, FR-005, FR-018, NFR-004,
AW-005; §18.5 exit taxonomy).

IR-003 acceptance: behaviors per FR-003-FR-006; exits non-zero when the safety
gate refuses. NFR-004 acceptance: out-of-the-box invocation cannot mutate.
"""
```

Cases (helper `_make_plan(corpus) -> Path` shells `plan <corpus> --out plan.json` via CliRunner first):

- `test_apply_default__dry_run_writes_nothing` (FR-004, NFR-004): `docmend apply plan.json` over a dirty corpus → exit 0, every corpus hash unchanged, no `-manifest.jsonl` anywhere, report artifact exists in `.docmend/` with `dry_run: true`, stdout summary shows `would-apply` count. **This is the NFR-004 config-default audit test — cite NFR-004 in the docstring.**
- `test_apply_dry_run_overwrite_with_configured_backup_dir__no_backup_written` (codex CR-001): plan built with a `docmend.toml` setting `rename.on_collision = "overwrite"` and `write.backup_dir`; create the colliding target; run `docmend apply plan.json` (no `--write`) → exit 0 and the configured backup directory does not exist afterwards ("config alone can never enable writes", OQ-014).
- `test_apply_write_and_dry_run__mutually_exclusive` (IR-003): `apply plan.json --write --dry-run` → exit 2. Also `docmend -n apply plan.json --write` → exit 2 (the global `-n` IS `--dry-run`; IR-005 gains its write-capable effect here).
- `test_apply_write_without_strategy__gate_refuses_exit_3` (FR-005): content-rewrite plan, `--write` only → exit 3, stderr explains the missing preservation strategy, corpus unchanged, report written with zero outcomes (decision 8).
- `test_apply_write_with_backup_dir__mutates_and_reports` (FR-005, FR-006, FR-018): `--write --backup-dir <outside>` → exit 0, corpus converted, report totals reconcile, manifest exists, console summary line contains `applied`.
- `test_apply_single_file_opt_in__no_backup_needed` (NFR-006, G-006): one-file corpus, default config, `apply plan.json --write --allow-no-backup` → exit 0, file converted.
- `test_apply_findings__exit_1` (FR-003): mutate a planned file before apply; `--write --backup-dir` → exit 1 (stale-hash finding), other file converted.
- `test_apply_invalid_plan__exit_2` (ERR-006): a JSON file that fails the plan schema → exit 2.
- `test_apply_plan_without_source_root__exit_2` (decision 3): strip `source_root` from a valid plan document, rewrite the file → exit 2, message says regenerate.
- `test_apply_locked_target__exit_3` (AW-005): pre-acquire the lock for the corpus root → exit 3.
- `test_apply_report_override__honored` (IR-001-style `--report`): `--report custom.json` → report lands there.
- `test_apply_verbose__per_file_lines` (IR-005/OQ-017): `docmend -v apply plan.json` → stderr contains a per-file `apply outcome` line; `-q` shows none.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli_apply.py -x -q` Expected: FAIL — no `apply` command.

- [ ] **Step 3: Implement** in `src/docmend/cli.py` (imports: `from enum import Enum`; `from docmend import lock`; `from docmend.config import ...` already present; `from docmend.report import Report` not needed; `from docmend.writer.apply import execute_plan`; `from docmend.writer.gate import ApplyOptions, evaluate_gate`; `from pydantic import ValidationError`):

```python
class PreservedBy(str, Enum):
    git = "git"
    external = "external"


@app.command()
def apply(
    ctx: typer.Context,
    plan_path: Annotated[
        Path,
        typer.Argument(exists=True, metavar="PLAN", help="Plan artifact to execute (IR-003)."),
    ],
    write: Annotated[
        bool,
        typer.Option("--write", help="Opt into real mutation (OQ-014); default is dry-run."),
    ] = False,
    dry_run_flag: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview outcomes without writing (the default)."),
    ] = False,
    backup_dir: Annotated[
        Path | None,
        typer.Option("--backup-dir", help="Tool-written backup destination (FR-006); overrides write.backup_dir."),
    ] = None,
    preserved_by: Annotated[
        PreservedBy | None,
        typer.Option("--preserved-by", help="Declare an external byte-preserving strategy (FR-005): git or external."),
    ] = None,
    allow_no_backup: Annotated[
        bool,
        typer.Option("--allow-no-backup", help="FR-005 low-risk opt-in: single-action plans only, no rollback copy."),
    ] = False,
    report: Annotated[
        Path | None,
        typer.Option("--report", help="Write the report to FILE (default: .docmend/docmend-<run-id>-report.json)."),
    ] = None,
) -> None:
    """Execute a reviewed plan; dry-run by default (FR-004, IR-003).

    Exit codes (§18.5): 0 clean; 1 findings (skips/failures); 2 input error
    (ERR-006 invalid plan, flag conflicts); 3 safety refusal (gate or lock).
    """
    opts = _global_options(ctx)
    if write and (dry_run_flag or opts.dry_run):
        raise typer.BadParameter("--write and --dry-run are mutually exclusive")

    now = datetime.now(UTC)
    run_id = new_run_id(now)
    artifact_dir = Path(ARTIFACT_DIR_NAME)
    configure_logging(
        run_id=run_id, command="apply", log_dir=artifact_dir, verbose=opts.verbose, quiet=opts.quiet
    )
    log = get_logger(__name__)

    try:
        plan = artifacts.read_plan(plan_path)
    except artifacts.ArtifactError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    if int(plan.schema_version.split(".")[1]) > int(PLAN_SCHEMA_VERSION.split(".")[1]):
        typer.echo(
            f"error: {plan_path}: plan schema {plan.schema_version} is newer than this "
            f"docmend supports ({PLAN_SCHEMA_VERSION}) — regenerate the plan (ERR-006)",
            err=True,
        )
        raise typer.Exit(2)
    if plan.source_root is None:
        typer.echo(
            f"error: {plan_path}: plan lacks source_root (pre-1.1 artifact) — regenerate the plan (ERR-006)",
            err=True,
        )
        raise typer.Exit(2)
    source_root = Path(plan.source_root)
    if not source_root.is_dir():
        typer.echo(f"error: {source_root}: plan source root is not a directory", err=True)
        raise typer.Exit(2)
    try:
        config = DocmendConfig.model_validate(plan.config)
    except ValidationError as exc:
        typer.echo(f"error: {plan_path}: config snapshot invalid — {exc}", err=True)
        raise typer.Exit(2) from exc

    backup_root = backup_dir if backup_dir is not None else config.write.backup_dir
    options = ApplyOptions(
        write=write,
        # Resolved ONCE here (codex CR-005): every backup path derived from
        # this root lands in the manifest, which restore must be able to
        # follow from any cwd (IR-008) — a relative --backup-dir must never
        # produce cwd-dependent manifest entries.
        backup_root=backup_root.resolve() if backup_root is not None else None,
        preserved_by=preserved_by.value if preserved_by is not None else None,
        allow_no_backup=allow_no_backup,
    )
    manifest_path = artifact_dir / f"docmend-{run_id}-manifest.jsonl"
    report_path = report if report is not None else artifact_dir / f"docmend-{run_id}-report.json"
    plan_ref = ArtifactRef(
        path=str(plan_path), run_id=plan.run_id, sha256=artifacts.sha256_of_file(plan_path)
    )
    started_at = now.isoformat()

    try:
        run_lock = lock.acquire(source_root, run_id=run_id, command="apply")
    except (lock.LockHeldError, OSError) as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(3) from exc
    try:
        if write:
            refusals = evaluate_gate(
                plan, config, source_root=source_root, options=options, manifest_dir=artifact_dir
            )
            if refusals:
                for refusal in refusals:
                    typer.echo(f"refused [{refusal.predicate}]: {refusal.message}", err=True)
                    log.error("gate refusal", predicate=refusal.predicate, detail=refusal.message)
                _write_refusal_report(plan_ref, run_id, started_at, report_path)
                raise typer.Exit(3)
        result = execute_plan(
            plan,
            config,
            run_id=run_id,
            plan_ref=plan_ref,
            options=options,
            manifest_path=manifest_path,
            started_at=started_at,
        )
    finally:
        run_lock.release()

    artifacts.write_report(result, report_path)
    totals = result.totals
    typer.echo(f"report: {report_path}")
    if write and (totals.applied or totals.failed):
        typer.echo(f"manifest: {manifest_path}")
    reasons = Counter(o.skip_reason for o in result.outcomes if o.skip_reason is not None)
    detail = f" ({', '.join(f'{r} {n}' for r, n in sorted(reasons.items()))})" if reasons else ""
    typer.echo(
        f"applied: {totals.applied}  would-apply: {totals.would_apply}  "
        f"skipped: {totals.skipped}{detail}  failed: {totals.failed}"
    )
    if totals.skipped or totals.failed:
        raise typer.Exit(1)
```

with the refusal-report helper (decision 8) and imports of `PLAN_SCHEMA_VERSION` from `docmend.plan` and `Report`/`ReportTotals` from `docmend.report`:

```python
def _write_refusal_report(
    plan_ref: ArtifactRef, run_id: str, started_at: str, report_path: Path
) -> None:
    # §8.5: even a refused run leaves an artifact; zero outcomes, library untouched.
    artifacts.write_report(
        Report(
            run_id=run_id,
            generated_by=f"docmend {__version__}",
            plan_ref=plan_ref,
            dry_run=False,
            started_at=started_at,
            completed_at=datetime.now(UTC).isoformat(),
            outcomes=[],
            totals=ReportTotals(applied=0, would_apply=0, skipped=0, failed=0),
        ),
        report_path,
    )
```

- [ ] **Step 4: Run the tests, then the full suite**

Run: `uv run coverage run -m pytest -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/cli.py tests/test_cli_apply.py
git commit -m "feat: docmend apply - dry-run default, gate wiring, readable summary (IR-003/FR-004/FR-018)"
```

---

### Task 11: Restore engine + `docmend restore` CLI (IR-008)

**Files:**

- Create: `src/docmend/restore.py`
- Modify: `src/docmend/cli.py`
- Test: `tests/test_restore.py`

**Interfaces:**

- Consumes: `read_manifest`/`ManifestWriter`/`ManifestRecord`, `atomic_write_bytes`/`rename_no_clobber`, `lock`.
- Produces:
  - `RestoreOutcome(action_id, docmend_id, path, status: Literal["restored","would_restore","skipped","failed"], detail: str | None)` (frozen dataclass).
  - `run_restore(records: list[ManifestRecord], *, run_id: str, write: bool, only_ids: frozenset[str] | None, manifest_out: Path) -> list[RestoreOutcome]`.
  - CLI: `docmend restore [--manifest FILE | --run-id ID] [--id DOCMEND_ID ...] [--write | --dry-run]`.

- [ ] **Step 1: Write the failing tests** — `tests/test_restore.py`. Harness: run a real write-mode apply first (reuse `tests/test_apply.py`'s `_plan_for`/`_execute` helpers by importing them, or duplicate the ~20 lines — prefer a tiny shared `tests/apply_harness.py` if the import is awkward), capture the pre-apply hash snapshot, then exercise `run_restore` over `read_manifest(manifest_path)`:

- `test_restore_dry_run__previews_and_touches_nothing` (IR-008): statuses all `would_restore`; post-apply corpus unchanged.
- `test_restore_rewrite__bytes_match_before_hash` (IR-008 acceptance): after restore `--write`, the file's bytes hash to the manifest's `before_sha256`.
- `test_restore_rename__file_moved_back`: `.md` gone, `.txt` back with identical bytes.
- `test_restore_rename_and_rewrite__original_reproduced`: original path holds the pre-apply bytes; target gone.
- `test_restore_lifo__later_mutations_undone_first` (adr-0004): records replay in reverse `seq`; assert by restoring a two-record manifest touching the same path lineage (apply then a crafted second record) and checking final state equals the FIRST record's `before` state.
- `test_restore_modified_since_apply__skipped_never_clobbers` (decision 10): edit a converted file after apply; restore skips it (`detail == "modified-since-apply"`), edited bytes intact, other records restored; findings exit handled at CLI level.
- `test_restore_no_backup_record__skipped`: apply via `--allow-no-backup`; restore of the rewrite record → skipped `no-backup`.
- `test_restore_backup_hash_mismatch__failed_err004`: corrupt the backup file bytes; restore → `failed`, file untouched.
- `test_restore_overwrite_record__clobbered_target_reinstated`: apply under `overwrite` with backups; restore puts the ORIGINAL clobbered `.md` content back at the target path and the `.txt` source back.
- `test_restore_overwrite_backup_corrupt__nothing_mutated` (codex CR-003): apply under `overwrite` with backups, then corrupt the `overwritten_backup_path` file's bytes; restore `--write` → that record `failed` with an ERR-004 detail AND both live files (the applied target and everything else) are byte-for-byte unchanged — preflight must catch the bad input before any write/unlink.
- `test_restore_source_backup_corrupt__nothing_mutated` (codex CR-003 sibling): corrupt the `backup_path` file of a `rename_and_rewrite` record; restore `--write` → `failed`, applied target still present and unchanged, original path still absent.
- `test_restore_mutation_phase_failure__no_file_lost` (codex CR-003 residual): for a `rename_and_rewrite` record, monkeypatch `docmend.restore.atomic_write_bytes` to succeed on the first call (original reinstated) and raise `WriteError` on the second — or monkeypatch `Path.unlink` for the no-clobbered variant; restore `--write` → record `failed` with ERR-003, AND every payload survives on disk: the reinstated original holds the pre-apply bytes and the applied target file still exists (superset, nothing lost). Re-running restore then reports the leftover as a `collision` skip, not silent damage.
- `test_restore_external_preservation_overwrite__skipped_untouched` (codex CR-NEW-003): apply a pure `.txt`→`.md` overwrite rename under `--preserved-by external` (no `--backup-dir`); restore `--write` → that record is `skipped` with the external-preservation `no-backup` detail, exit 1, and the corpus is byte-for-byte unmutated — restore must never report success while the clobbered target stays missing.
- `test_restore_records_its_own_manifest`: after a write restore, `manifest_out` contains one record per restoration with swapped before/after hashes.
- CLI tests (in the same file): `--manifest`/`--run-id` exclusivity → exit 2; `--run-id` resolves `.docmend/docmend-<id>-manifest.jsonl`; corrupt-interior manifest → exit 2; findings → exit 1; clean write restore → exit 0; locked root → exit 3; `--id` filters to one document.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_restore.py -x -q` Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `src/docmend/restore.py`:

```python
"""Restore engine — LIFO manifest replay (IR-008, adr-0004, §12.3, §18.6).

Conservatism contract (decision 10): only result=='applied' records replay;
the live file must still hash to the record's after_sha256 (a file edited
since apply is skipped, never clobbered); the backup must hash to
before_sha256 (ERR-004 on mismatch); records with no backup reference are
skipped — the operator's own preservation strategy (git/external) is the
recovery path there, by design (FR-005). Restore is itself mutation: it
dry-runs by default and appends inverse records to its own run manifest.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from docmend.observability import get_logger
from docmend.report import ErrorInfo
from docmend.writer.atomic import (
    WriteError,
    atomic_write_bytes,
    link_no_clobber,
    rename_no_clobber,
)
from docmend.writer.manifest import ManifestRecord, ManifestWriter

type RestoreStatus = Literal["restored", "would_restore", "skipped", "failed"]


@dataclass(frozen=True)
class RestoreOutcome:
    action_id: str
    docmend_id: str
    path: str
    status: RestoreStatus
    detail: str | None


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _verified_backup(record: ManifestRecord) -> bytes | RestoreOutcome:
    if record.backup_path is None:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "skipped", "no-backup"
        )
    try:
        data = Path(record.backup_path).read_bytes()
    except OSError as exc:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "failed",
            f"ERR-004: backup unreadable ({exc})",
        )
    if _sha(data) != record.before_sha256:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "failed",
            f"ERR-004: backup hash {_sha(data)} != recorded before hash {record.before_sha256}",
        )
    return data


def _live_matches_after(record: ManifestRecord) -> RestoreOutcome | None:
    live = Path(record.target_path)
    try:
        current = live.read_bytes()
    except OSError:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "skipped",
            "unreadable: applied file missing or unreadable",
        )
    if record.after_sha256 is not None and _sha(current) != record.after_sha256:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "skipped",
            "modified-since-apply",
        )
    return None


def run_restore(
    records: list[ManifestRecord],
    *,
    run_id: str,
    write: bool,
    only_ids: frozenset[str] | None,
    manifest_out: Path,
) -> list[RestoreOutcome]:
    log = get_logger(__name__)
    replay = [
        r
        for r in sorted(records, key=lambda r: r.seq, reverse=True)  # LIFO (IR-008)
        if r.result == "applied" and (only_ids is None or r.docmend_id in only_ids)
    ]
    outcomes: list[RestoreOutcome] = []
    manifest: ManifestWriter | None = None
    if write and replay:
        manifest = ManifestWriter(manifest_out, run_id=run_id)
    try:
        for record in replay:
            outcome = _restore_one(record, write=write, run_id=run_id, manifest=manifest)
            outcomes.append(outcome)
            log.info(
                "restore outcome",
                path=record.original_path,
                status=outcome.status,
                detail=outcome.detail,
            )
    finally:
        if manifest is not None:
            manifest.close()
    return outcomes


def _restore_one(
    record: ManifestRecord, *, write: bool, run_id: str, manifest: ManifestWriter | None
) -> RestoreOutcome:
    # ---- Preflight: verify EVERY recovery input before ANY mutation (codex
    # CR-003). A restore that mutates and then discovers a bad input has
    # destroyed state inside the disaster-recovery path itself — every early
    # return in this section leaves both live files byte-identical.
    mismatch = _live_matches_after(record)
    if mismatch is not None:
        return mismatch
    original = Path(record.original_path)
    target = Path(record.target_path)

    if record.operation != "rewrite" and original.exists():
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "skipped",
            "collision: original path is occupied",
        )
    backup: bytes | None = None
    if record.operation in ("rewrite", "rename_and_rewrite"):
        verdict = _verified_backup(record)
        if isinstance(verdict, RestoreOutcome):
            return verdict
        backup = verdict
    clobbered: bytes | None = None
    if record.overwritten_sha256 is not None and record.operation != "rewrite":
        # The overwrite policy destroyed a pre-existing target (OQ-035/G-002).
        if record.overwritten_backup_path is None:
            # Declared external preservation: docmend holds no bytes to
            # reinstate the clobbered file. Restoring only our own mutation
            # would report success while that file stays missing (codex
            # CR-NEW-003) — the operator's external strategy recovers the
            # WHOLE record, so skip it, mutating nothing.
            return RestoreOutcome(
                record.action_id, record.docmend_id, record.original_path, "skipped",
                "no-backup: overwritten target restorable only from external preservation",
            )
        # Its backup must read and verify BEFORE we undo our own mutation.
        try:
            clobbered = Path(record.overwritten_backup_path).read_bytes()
        except OSError as exc:
            return RestoreOutcome(
                record.action_id, record.docmend_id, record.original_path, "failed",
                f"ERR-004: overwritten-target backup unreadable ({exc})",
            )
        if _sha(clobbered) != record.overwritten_sha256:
            return RestoreOutcome(
                record.action_id, record.docmend_id, record.original_path, "failed",
                "ERR-004: overwritten-target backup hash mismatch",
            )
    if not write:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "would_restore", None
        )

    # ---- Mutate: all inputs proven above. Ordering is loss-proof (codex
    # CR-003 residual): the original is reinstated FIRST and the applied
    # target is removed/replaced LAST, so an environmental failure at any
    # step leaves a SUPERSET of the wanted files on disk — never a missing
    # one. A half-restored record is deliberately re-runnable: its preflight
    # collision check surfaces the leftover state instead of guessing.
    try:
        if record.operation == "rewrite":
            assert backup is not None
            atomic_write_bytes(original, backup)
        elif record.operation == "rename":
            if clobbered is not None:
                # Keep the target name occupied throughout: link the applied
                # file back to its original name, then atomically replace the
                # target with the clobbered content — no window where either
                # name is missing.
                link_no_clobber(target, original)
                atomic_write_bytes(target, clobbered)
            else:
                rename_no_clobber(target, original)
        else:  # rename_and_rewrite
            assert backup is not None
            atomic_write_bytes(original, backup, clobber=False)
            if clobbered is not None:
                atomic_write_bytes(target, clobbered)
            else:
                target.unlink()
    except (WriteError, OSError, FileExistsError) as exc:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "failed",
            f"ERR-003: {exc}",
        )

    if manifest is not None:
        manifest.append(
            record.model_copy(
                update={
                    "run_id": run_id,
                    "action_id": f"{run_id}/a{record.seq}",
                    "original_path": record.target_path,
                    "target_path": record.original_path,
                    "backup_path": None,
                    "before_sha256": record.after_sha256 or record.before_sha256,
                    "after_sha256": record.before_sha256,
                    "overwritten_sha256": None,
                    "overwritten_backup_path": None,
                    "error": None,
                }
            )
        )
    return RestoreOutcome(
        record.action_id, record.docmend_id, record.original_path, "restored", None
    )
```

(`ErrorInfo` import is unused in this sketch — drop it unless the implementer routes failures through it; Ruff will catch either way.)

CLI command in `src/docmend/cli.py`:

```python
@app.command()
def restore(
    ctx: typer.Context,
    manifest_path: Annotated[
        Path | None,
        typer.Option("--manifest", help="Manifest to replay (DR-004 NDJSON)."),
    ] = None,
    run_id_arg: Annotated[
        str | None,
        typer.Option("--run-id", help="Resolve .docmend/docmend-<ID>-manifest.jsonl (OQ-034 sidecar convention)."),
    ] = None,
    only_id: Annotated[
        list[str] | None,
        typer.Option("--id", help="Restore only these docmend.id values (repeatable)."),
    ] = None,
    write: Annotated[
        bool, typer.Option("--write", help="Perform the restore; default previews (mirrors apply).")
    ] = False,
    dry_run_flag: Annotated[bool, typer.Option("--dry-run", help="Preview (the default).")] = False,
) -> None:
    """Replay manifest records LIFO to undo an apply run (IR-008, §18.6).

    Exit codes (§18.5): 0 clean; 1 findings (skips/failures); 2 input error
    (bad manifest); 3 safety refusal (lock).
    """
    opts = _global_options(ctx)
    if write and (dry_run_flag or opts.dry_run):
        raise typer.BadParameter("--write and --dry-run are mutually exclusive")
    if (manifest_path is None) == (run_id_arg is None):
        raise typer.BadParameter("provide exactly one of --manifest or --run-id")
    if manifest_path is None:
        manifest_path = Path(ARTIFACT_DIR_NAME) / f"docmend-{run_id_arg}-manifest.jsonl"

    now = datetime.now(UTC)
    run_id = new_run_id(now)
    artifact_dir = Path(ARTIFACT_DIR_NAME)
    configure_logging(
        run_id=run_id, command="restore", log_dir=artifact_dir,
        verbose=opts.verbose, quiet=opts.quiet,
    )

    try:
        records = manifest.read_manifest(manifest_path)
    except artifacts.ArtifactError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    if not records:
        typer.echo("nothing to restore: manifest holds no records")
        return

    root = Path(os.path.commonpath([r.original_path for r in records]))
    try:
        run_lock = lock.acquire(root if root.is_dir() else root.parent, run_id=run_id, command="restore")
    except (lock.LockHeldError, OSError) as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(3) from exc
    try:
        outcomes = run_restore(
            records,
            run_id=run_id,
            write=write,
            only_ids=frozenset(only_id) if only_id else None,
            manifest_out=artifact_dir / f"docmend-{run_id}-manifest.jsonl",
        )
    finally:
        run_lock.release()

    counts = Counter(outcome.status for outcome in outcomes)
    typer.echo(
        f"restored: {counts.get('restored', 0)}  would-restore: {counts.get('would_restore', 0)}  "
        f"skipped: {counts.get('skipped', 0)}  failed: {counts.get('failed', 0)}"
    )
    if counts.get("skipped", 0) or counts.get("failed", 0):
        raise typer.Exit(1)
```

(new cli imports: `import os`, `from docmend.restore import run_restore`, `from docmend.writer import manifest`.)

- [ ] **Step 4: Run the tests, then the full suite**

Run: `uv run coverage run -m pytest -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/restore.py src/docmend/cli.py tests/test_restore.py
git commit -m "feat: docmend restore - LIFO manifest replay, hash-guarded, dry-run default (IR-008)"
```

---

### Task 12: Restore drill + single-file pipeline journey (§18.6, FR-006, NFR-006)

The §18.6/§17.2 Operations-row acceptance: an automated backup-and-restore drill from the manifest, end-to-end through the CLI; plus the NFR-006 single-file leg through apply.

**Files:**

- Test: `tests/test_restore_drill.py`

**Interfaces:**

- Consumes: the full CLI surface (`scan` implicit via `plan PATH`, `apply`, `restore`) through `CliRunner`.
- Produces: nothing new — pure verification.

- [ ] **Step 1: Write the drill test** — `tests/test_restore_drill.py`:

```python
"""Automated restore drill (spec §18.6, FR-006 acceptance, IR-008) and the
NFR-006 single-file pipeline leg (scan -> plan -> apply --write).

FR-006: "restoring from manifest+backups reproduces the original corpus."
The drill runs the REAL command surface end-to-end: plan PATH -> apply --write
--backup-dir -> restore --manifest --write, then compares every byte.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from docmend.cli import app

runner = CliRunner()


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.fixture
def drill_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "corpus"
    (root / "sub").mkdir(parents=True)
    (root / "crlf.txt").write_bytes(b"alpha\r\nbeta\r\n")
    (root / "legacy.txt").write_bytes(("café " * 30).encode("windows-1252"))
    (root / "sub" / "trailing.txt").write_bytes(b"gamma  \ndelta\n")
    (root / "clean.md").write_bytes(b"# already clean\n")
    return root


def _artifact(pattern: str, out: str) -> Path:
    match = re.search(pattern, out)
    assert match is not None, out
    return Path(match.group(1))


def test_restore_drill__manifest_replay_reproduces_original_corpus(drill_corpus: Path) -> None:
    """§18.6 + FR-006 + IR-008: the full plan -> apply --write -> restore --write drill."""
    before = _snapshot(drill_corpus)

    planned = runner.invoke(app, ["plan", str(drill_corpus), "--out", "plan.json"])
    assert planned.exit_code == 0, planned.output

    applied = runner.invoke(
        app, ["apply", "plan.json", "--write", "--backup-dir", str(drill_corpus.parent / "backups")]
    )
    assert applied.exit_code == 0, applied.output
    assert _snapshot(drill_corpus) != before  # the corpus really changed
    manifest = _artifact(r"manifest: (\S+)", applied.output)

    restored = runner.invoke(app, ["restore", "--manifest", str(manifest), "--write"])
    assert restored.exit_code == 0, restored.output
    assert _snapshot(drill_corpus) == before  # IR-008: bytes match pre-apply hashes


def test_single_file_journey__scan_plan_apply_with_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR-006/G-006: one file, default configuration, only the FR-005 low-risk
    opt-in — no config file, no backup infrastructure (apply leg; verify closes
    the journey at MS-4)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    single = tmp_path / "letter.txt"
    single.write_bytes(b"hello\r\nworld")

    planned = runner.invoke(app, ["plan", str(single), "--out", "plan.json"])
    assert planned.exit_code == 0, planned.output
    applied = runner.invoke(app, ["apply", "plan.json", "--write", "--allow-no-backup"])
    assert applied.exit_code == 0, applied.output

    converted = tmp_path / "letter.md"
    assert converted.read_bytes() == b"hello\nworld\n"
    assert not single.exists()


def test_drill_relative_backup_dir__restore_from_other_cwd(
    drill_corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """codex CR-005: a RELATIVE --backup-dir must still yield a manifest that
    restores from a different working directory (IR-008 standalone manifest)."""
    before = _snapshot(drill_corpus)
    runner.invoke(app, ["plan", str(drill_corpus), "--out", "plan.json"])
    applied = runner.invoke(app, ["apply", "plan.json", "--write", "--backup-dir", "backups"])
    assert applied.exit_code == 0, applied.output
    manifest = _artifact(r"manifest: (\S+)", applied.output).resolve()

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    restored = runner.invoke(app, ["restore", "--manifest", str(manifest), "--write"])
    assert restored.exit_code == 0, restored.output
    assert _snapshot(drill_corpus) == before


def test_drill_report_and_manifest_agree(drill_corpus: Path) -> None:
    """DR-003/DR-004 consistency: applied count in the report equals the number
    of applied manifest records (§17.2 Operations row)."""
    runner.invoke(app, ["plan", str(drill_corpus), "--out", "plan.json"])
    applied = runner.invoke(
        app, ["apply", "plan.json", "--write", "--backup-dir", str(drill_corpus.parent / "backups")]
    )
    report_path = _artifact(r"report: (\S+)", applied.output)
    manifest_path = _artifact(r"manifest: (\S+)", applied.output)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert report["totals"]["applied"] == sum(1 for r in records if r["result"] == "applied")
```

- [ ] **Step 2: Run — these should pass already** (they are acceptance, not TDD-first: every piece landed in Tasks 3–11). Any failure here is a real integration defect — fix it in the task that owns the failing layer before proceeding.

Run: `uv run pytest tests/test_restore_drill.py -q` Expected: PASS.

- [ ] **Step 3: Full verification gate**

Run: `uv run ruff format --check . && uv run ruff check . && uv run basedpyright && uv run coverage run -m pytest && uv run coverage report` Expected: all green, coverage ≥ 85%.

- [ ] **Step 4: Commit**

```bash
git add tests/test_restore_drill.py
git commit -m "test: automated restore drill + single-file apply journey (18.6/FR-006/NFR-006)"
```

---

### Task 13: Spec, decision-backlog, and doc sync (Appendix B closeout)

**Files:**

- Modify: `docs/specs/docmend.md` (revision row 0.16, §3.1, §17.3 rows, §21 OQ-035/OQ-036 rows)
- Modify: `docs/open-questions.md` (OQ-035, OQ-036 entries)
- Modify: `TODO.md` (move the two MS-3 inputs to Completed; note OQ-035/036 for the owner)
- Modify: `README.md` (apply/restore usage)
- Modify: `src/docmend/writer/__init__.py` (docstring: modules now exist)
- Modify: `src/docmend/schemas/README.md` (1.1 version notes, if it lists versions)

**Steps:**

- [ ] **Step 1: §21 rows.** Append to the spec's §21 table (content-edit within existing structure — no CLI needed, conventions #3):

```markdown
| OQ-035 | FR-005's CLI surface and risk tiers: how are the git/external preservation strategies declared, what exactly is a "low-risk single-file operation", and how is an overwrite-clobbered target preserved (G-002)? | Proceeding on: `--backup-dir` activates tool backups; `--preserved-by git\|external` declares an external byte-preserving strategy (operator assertion); `--allow-no-backup` is the low-risk opt-in, valid only for single-action plans; an action is a content rewrite iff any operation ≠ rename; rename-only runs under skip/fail collision policy need no strategy (manifest suffices); a run that would overwrite an existing target requires an active strategy, and tool backups also copy the clobbered target (manifest 1.1 `overwritten_*` fields). | No | owner | MS-4 (before verify/resume harden the surface) | Open | | OQ-036 | Run-level lock (OQ-027) location and mechanism — the spec mandates the lock but not its home. | Proceeding on: `flock(2)` on `$XDG_STATE_HOME/docmend/locks/<sha256-of-resolved-source-root>.lock` (default `~/.local/state/…`) — kernel-owned, so a crashed holder can never leave a stale lock and no stale-detection/unlink races exist; holder JSON (run_id/pid/command/started_at) written only for the refusal message; a live holder refuses with exit 3 (AW-005); plan warns-and-proceeds if the state dir is uncreatable (stays read-only-safe), apply/restore refuse. Single-machine semantics (A-003-adjacent: local POSIX filesystem per A-001). | No | owner | MS-4 | Open |
```

Mirror both into `docs/open-questions.md` following that file's existing entry format (read it first; keep the same headings/fields it uses for OQ-034).

- [ ] **Step 2: Revision history row** (top of the table, version 0.16):

```markdown
| 0.16 | `2026-07-06` | `coding-agent` | **MS-3 User and admin experience implemented** (§19 items 1–3). Spec-side changes: §17.3 rows FR-003/FR-004/FR-005/FR-006/FR-011/FR-018/NFR-002/NFR-004/IR-003/IR-008/DR-003/DR-004 Complete, FR-007/FR-010/FR-012/NFR-006/IR-005/IR-007 advanced, each with named tests; §3.1 refreshed (apply/restore live; verify lands MS-4); §21 gains OQ-035 (FR-005 CLI surface + risk tiers) and OQ-036 (run-lock location) — both Open, non-blocking, proceeding on recorded assumptions. Code side (for context): the writer layer (atomic same-dir replace + parent fsync, link-based no-clobber renames, verify-then-mutate backups, fsync-per-record NDJSON manifest with AOF read rule), the adr-0004 pure-predicate safety gate (pairwise-tested), `docmend apply` (dry-run default, snapshot-driven, per-file FR-003 hash guard, console summary mirroring the DR-003 counts per §18.5), `docmend restore` (LIFO replay, IR-008) with the automated §18.6 drill, the OQ-027 run lock, and the two MS-2 final-review inputs: inventory 1.1 detection provenance (cross-config binary-suspect fix) and artifact path-containment hardening (inventory/plan 1.1 patterns + model validators). Manifest schema 1.1 adds the overwrite-preservation fields; plan schema 1.1 adds optional `source_root`. |
```

- [ ] **Step 3: §17.3 traceability updates.** Set each row's Test/Status cell (named tests are the ones this plan created; keep existing citations and append):

| Row | New status | Named tests to cite |
| --- | --- | --- |
| FR-003 | Complete (MS-3) | `tests/test_apply.py::test_stale_hash__skipped_batch_continues`, `tests/test_cli_apply.py::test_apply_findings__exit_1` |
| FR-004 | Complete (MS-3) | `tests/test_cli_apply.py::test_apply_default__dry_run_writes_nothing`, `tests/test_apply.py::test_dry_run_default__writes_nothing_reports_would_apply` |
| FR-005 | Complete (MS-3) | `tests/test_gate.py` (refusal-per-missing-strategy set), `tests/test_cli_apply.py::test_apply_write_without_strategy__gate_refuses_exit_3` |
| FR-006 | Complete (MS-3) | `tests/unit/writer/test_backup.py`, `tests/test_apply.py::test_write_rewrite_in_place__utf8_lf_and_manifest`, `tests/test_restore_drill.py::test_restore_drill__manifest_replay_reproduces_original_corpus` |
| FR-007 | Complete (MS-3: conversion-through-apply) | append `tests/test_apply.py`, `tests/test_restore_drill.py` |
| FR-010 | Complete (MS-3: report side) | append `tests/test_apply.py::test_write_rename_only__link_semantics` |
| FR-011 | Complete (MS-3: apply half incl. overwrite manifest) | append `tests/test_apply.py::test_collision_policies__skip_fail_overwrite` |
| FR-012 | Partial → note apply leg done | append `tests/test_apply.py::test_snapshot_filter_enforced__foreign_action_excluded` |
| FR-018 | Complete (MS-3) | `tests/test_report_artifact.py`, `tests/test_apply.py::test_report_counts_reconcile__and_manifest_seq_monotonic` |
| FR-019 | unchanged (watchdog MS-5) | — |
| NFR-002 | Complete (MS-3: injected-crash atomicity; kill-and-resume e2e reaffirms at MS-4) | `tests/unit/writer/test_atomic.py::test_crash_during_replace__original_intact` |
| NFR-004 | Complete (MS-3) | `tests/test_cli_apply.py::test_apply_default__dry_run_writes_nothing` |
| NFR-006 | Partial (MS-3 apply leg; verify closes at MS-4) | append `tests/test_restore_drill.py::test_single_file_journey__scan_plan_apply_with_defaults` |
| IR-003 | Complete (MS-3) | `tests/test_cli_apply.py` |
| IR-005 | Complete (MS-3: --dry-run now has effect) | append `tests/test_cli_apply.py::test_apply_write_and_dry_run__mutually_exclusive` |
| IR-007 | Complete (MS-3: report + manifest halves) | append `tests/test_report_artifact.py`, `tests/unit/writer/test_manifest.py` |
| IR-008 | Complete (MS-3) | `tests/test_restore.py`, `tests/test_restore_drill.py` |
| DR-003 | Complete (MS-3) | `tests/test_report_artifact.py` (schema + reconciliation) |
| DR-004 | Complete (MS-3) | `tests/unit/writer/test_manifest.py`, `tests/test_restore_drill.py` (mechanical restorability) |

Run `uv run python scripts/check_traceability.py` (or the exact invocation `.github/workflows/traceability.yml` uses) to confirm every cited ID appears under `tests/`.

- [ ] **Step 4: §3.1 refresh.** Rewrite the final clause of §3.1's paragraph: scan, plan, **apply, and restore** are live (the writer layer with the FR-005 gate, backups, manifest, atomic writes); `verify` lands per §19 (MS-4).

- [ ] **Step 5: README.** Add to the command documentation (matching the existing scan/plan entries' style):

```markdown
### `docmend apply PLAN`

Execute a reviewed plan. **Dry-run by default** — nothing is written until you pass `--write` (FR-004/OQ-014). A writing run is gated (exit 3 on refusal): a content-changing rewrite needs a byte-preserving strategy — tool backups (`--backup-dir PATH` or `write.backup_dir`), a declared strategy (`--preserved-by git|external`), or, for a single-action plan only, the explicit `--allow-no-backup` low-risk opt-in. Every mutation is recorded in an append-only manifest (`.docmend/docmend-<run-id>-manifest.jsonl`); the report (`--report FILE` to relocate) records every outcome. Exit codes: 0 clean, 1 findings (skips/failures), 2 input error, 3 safety refusal.

### `docmend restore [--manifest FILE | --run-id ID]`

Undo an apply run by replaying its manifest newest-first. Dry-run by default; `--write` performs the restore; `--id DOCMEND_ID` limits it to specific documents. A file modified since apply is skipped, never clobbered.
```

- [ ] **Step 6: TODO.md.** Move the two "MS-3 input" items to Completed Tasks with a one-line resolution note each; add one Agent Tracked line: "OQ-035/OQ-036 owner sign-off (raised at MS-3, non-blocking, wanted by MS-4): preservation CLI surface + risk tiers; run-lock location."

- [ ] **Step 7: Markdown/format pass + spec validation**

Run:

```bash
npx prettier --write . && npx markdownlint-cli2 --fix "**/*.md"
uv run python scripts/fix_spec_toc.py
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec validate --config .project-standards.yml
uvx --from 'git+https://github.com/L3DigitalNet/project-standards@v4' project-standards spec lint --strict --config .project-standards.yml
npx prettier --check . && npx markdownlint-cli2 "**/*.md"
```

Expected: all pass (watch conventions #9: no bare `RQ-`/`ADR-NNNN`/`GAP-NN` tokens in spec prose).

- [ ] **Step 8: Full verification gate, then commit**

```bash
uv run ruff format --check . && uv run ruff check . && uv run basedpyright && \
  uv run coverage run -m pytest && uv run coverage report && uv run pip-audit
git add docs/specs/docmend.md docs/open-questions.md TODO.md README.md \
        src/docmend/writer/__init__.py src/docmend/schemas/README.md
git commit -m "docs: MS-3 closeout - spec rev 0.16, 17.3 rows, OQ-035/036, README apply+restore"
```

---

## Completion checklist (Appendix B.3)

Before opening the `dev → main` PR:

1. **Requirements → tests:** every §17.3 row this milestone claims maps to a named, passing test (Task 13 Step 3 table).
2. **Deviations:** none expected; if execution forced one, it is in the spec's Deviations Log, not silently adapted. DEV-001 remains pending owner review (unchanged).
3. **Open questions:** OQ-034 unchanged (apply followed its assumption); OQ-035/OQ-036 filed with recorded assumptions.
4. **Docs:** README, spec, TODO, open-questions synced (Task 13); handoff docs (`docs/handoff/state.md`, `STATUS.md`, `sessions/2026-07.md`, `specs-plans.md` plan pointer) updated at session end per the handoff ritual.
5. **Gate:** local verification gate green (it is the only gate before the PR — no CI on `dev`).
6. PR title: "MS-3: writer layer, apply, restore — full safety machinery"; body summarizes gate/backup/manifest/collision/dry-run coverage and the restore drill per the §19 MS-3 exit criteria.
