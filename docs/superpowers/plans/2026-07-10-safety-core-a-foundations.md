# Safety-Core Plan A: Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close DMR-01 (same-plan backup overwrite) and DMR-02 (artifact destinations clobbering corpus inputs) — the plan-time output ledger, the write-once role-namespaced BackupStore, the artifact destination guard, randomized `O_EXCL` staging, and in-lock apply-report finalization.

**Architecture:** This is Plan A of four (A foundations → B manifest 2.0 → C commit boundary → D verify) implementing SPEC-VHHB rev 0.26 (`docs/specs/docmend.md`) per the approved design `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md` and ADRs `adr-0019`/`adr-0020`/`adr-0021` (+ amended `adr-0004`/`adr-0005`/`adr-0012`). Plan A has no dependency on B–D and changes no schema: manifest records already store backup paths as opaque strings, so the new key layout is value-only.

**Tech Stack:** Python 3.14 (`uv`-managed), Typer CLI, pydantic v2 strict models, pathspec, pytest.

Revision note: revised per `docs/codex-reviews/2026-07-10-safety-core-a-foundations-plan-review.md` round 1 — F1 (every pasted test now uses valid `run_[0-9a-f]{6}` IDs, the live modules' module-level `runner`/`make_corpus`/`_make_plan` conventions, typed signatures, and deterministic spy setup), F2 (the carve-out is licensed per actual destination against the effective excludes — the probe is gone), F3 (the guard checks both the lexical directory entry and the resolved referent, with mirror symlink tests), F4 (JSON staging cleans up on every failure class via `finally`, no umask mutation), F5 (writer staging retries `EEXIST` as a name collision with a deterministic collision test). Revised again per round 2 — F6 (owner decision recorded): the lexical+resolved containment rule is now stated in the approved contract (`adr-0021` amendment + SPEC-VHHB rev 0.27, IR-007), and the mode-0600 policy is dropped — artifact modes stay umask-derived via a kernel-masked `0o666` create mode (no `os.umask()` calls), with permission policy deferred to sub-project 4.

## Global Constraints

- Full local gate (run before claiming any task complete that says "run the gate"): `uv run scripts/check.py` — ruff format → ruff check → basedpyright → coverage run -m pytest → coverage report → pip-audit. All must pass.
- Quick loop while developing: `uv run pytest <file>::<test> -v`.
- Branch coverage must stay ≥ 97% (the gate's `coverage report` enforces the configured floor).
- **Never `git add .` or `git add -A`** — stage files by explicit name only.
- This repo is **public**: test fixtures are synthetic only — never real library documents, paths, or personal content.
- Comments target the next AI session: intent, invariants, cross-file contracts, rejected alternatives. No syntax narration.
- The package version stays `1.0.2`; v2.0.0 releases only after Plans A–D all land. New behavior goes under an `## [Unreleased]` CHANGELOG section (Task 10).
- Run IDs must match `run_\d{8}T\d{6}Z_[0-9a-f]{6}` (`src/docmend/inventory.py:32`) — the six-char suffix is strictly hex.
- Requirement IDs cited in code comments/tests must match rev 0.26 of `docs/specs/docmend.md` (FR-006, FR-011, IR-007, DMR-01, DMR-02 are the ones this plan touches).
- Python 3.14 note: `except WriteError, OSError:` (unparenthesized, PEP 758) appears in `apply.py` — it is valid 3.14 syntax, not a bug. Do not "fix" it.
- CLI test conventions (all three `tests/test_cli_*.py` modules): module-level `runner = CliRunner()` (no fixture), `monkeypatch.chdir(tmp_path)` per test, autouse `isolate_logging` (and, in the apply module, `isolate_state_dir`) fixtures already present — new tests get them for free.

---

### Task 1: Write-once, role-namespaced BackupStore keys

**Files:**

- Modify: `src/docmend/writer/backup.py` (whole file, 48 lines)
- Test: `tests/unit/writer/test_backup.py`

**Interfaces:**

- Consumes: `docmend.writer.atomic.atomic_write_bytes(target, data, *, clobber: bool)` — with `clobber=False` it publishes via hardlink and raises `FileExistsError` if the target already exists (existing behavior, unchanged).
- Produces: `backup_file(data: bytes, *, backup_root: Path, run_id: str, action_seq: str, role: BackupRole, relative_path: str, expected_sha256: str) -> Path` and `type BackupRole = Literal["source", "overwritten"]`. Task 2 calls this from `apply.py`. Key layout: `{backup_root}/{run_id}/{action_seq}/{role}/{relative_path}`.

- [ ] **Step 1: Update the existing layout test and add the write-once + role tests (failing)**

Replace the first test in `tests/unit/writer/test_backup.py` and append two new ones (explicit keyword calls throughout — no kwargs-dict spreading; the module's strict typing gate rejects `dict[str, object]` unpacking into typed keywords):

```python
def test_backup__written_verified_and_returned(tmp_path: Path) -> None:
    data = b"payload bytes\n"
    dest = backup.backup_file(
        data,
        backup_root=tmp_path / "backups",
        run_id=RUN_ID,
        action_seq="a1",
        role="source",
        relative_path="sub/a.txt",
        expected_sha256=_sha(data),
    )
    assert dest == (tmp_path / "backups" / RUN_ID / "a1" / "source" / "sub" / "a.txt").resolve()
    assert dest.is_absolute()  # CR-005: manifest backup paths must survive cwd changes
    assert dest.read_bytes() == data


def test_backup_key_write_once__second_write_raises(tmp_path: Path) -> None:
    """DMR-01 defense in depth: a backup key is write-once — a second write to
    the same (run, action, role, path) key is a defect, never a retry (ERR-004)."""
    data = b"payload"
    backup.backup_file(
        data,
        backup_root=tmp_path / "backups",
        run_id=RUN_ID,
        action_seq="a1",
        role="source",
        relative_path="a.txt",
        expected_sha256=_sha(data),
    )
    with pytest.raises(backup.BackupError, match="write-once"):
        backup.backup_file(
            data,
            backup_root=tmp_path / "backups",
            run_id=RUN_ID,
            action_seq="a1",
            role="source",
            relative_path="a.txt",
            expected_sha256=_sha(data),
        )


def test_backup_roles__same_relative_path_distinct_keys(tmp_path: Path) -> None:
    """The DMR-01 shape: one action's source bytes and another action's
    overwritten-target bytes may share a relative path; roles + action_seq
    keep the keys distinct so neither copy can clobber the other."""
    source = b"original a.md\n"
    clobbered = b"pre-existing a.md target\n"
    dest_source = backup.backup_file(
        source,
        backup_root=tmp_path / "backups",
        run_id=RUN_ID,
        action_seq="a1",
        role="source",
        relative_path="a.md",
        expected_sha256=_sha(source),
    )
    dest_overwritten = backup.backup_file(
        clobbered,
        backup_root=tmp_path / "backups",
        run_id=RUN_ID,
        action_seq="a2",
        role="overwritten",
        relative_path="a.md",
        expected_sha256=_sha(clobbered),
    )
    assert dest_source != dest_overwritten
    assert dest_source.read_bytes() == source
    assert dest_overwritten.read_bytes() == clobbered
```

Also update the three remaining existing tests (`test_backup_hash_mismatch__raises_before_mutation`, `test_backup_reread_corruption__raises`, `test_backup_destination_unwritable__raises`) to pass `action_seq="a1", role="source",` alongside their existing keyword arguments — no other change to them.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/writer/test_backup.py -v` Expected: FAIL — `TypeError: backup_file() got an unexpected keyword argument 'action_seq'`

- [ ] **Step 3: Rewrite `backup.py`**

Replace the whole of `src/docmend/writer/backup.py`:

```python
"""Tool-written backups — verify-then-mutate (FR-006, ERR-004, adr-0004 amended, adr-0019).

Layout: {backup_root}/{run_id}/{action_seq}/{role}/{relative_path} — keyed by
run, action, and role so no two backups in one run can ever share a key
(DMR-01: an in-place rewrite's source copy and a rename's overwritten-target
copy may share a relative path; the old run/relative-path layout let the
second silently replace the first). Keys are WRITE-ONCE: the publish is
no-clobber, and an existing file at a key raises BackupError — a retry is a
new run with a new run_id, never a rewrite of an existing key. §7.4 retention
unchanged (the tool never deletes its own backups).

Sequence per FR-006: write the copy, fsync it, RE-READ it from disk, re-hash,
compare to the plan's recorded source hash — only then may the caller touch
the original. Any failure raises BackupError (ERR-004) with the original
still untouched.
"""

import hashlib
from pathlib import Path
from typing import Literal

from docmend.writer.atomic import WriteError, atomic_write_bytes

type BackupRole = Literal["source", "overwritten"]


class BackupError(Exception):
    """Backup copy or verification failed (ERR-004); the original is untouched."""


def backup_file(
    data: bytes,
    *,
    backup_root: Path,
    run_id: str,
    action_seq: str,
    role: BackupRole,
    relative_path: str,
    expected_sha256: str,
) -> Path:
    dest = backup_root / run_id / action_seq / role / relative_path
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # clobber=False publishes via hardlink: atomic AND EEXIST-safe, which
        # is what makes the write-once contract race-proof rather than a
        # check-then-write.
        atomic_write_bytes(dest, data, clobber=False)
    except FileExistsError as exc:
        msg = (
            f"{dest}: backup key already occupied — backup keys are write-once "
            f"(a second write to one (run, action, role, path) key is a defect, "
            f"never a legitimate retry; ERR-004)"
        )
        raise BackupError(msg) from exc
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

- [ ] **Step 4: Run the unit tests — they pass; the apply suite fails until Task 2**

Run: `uv run pytest tests/unit/writer/test_backup.py -v` Expected: PASS (all 6).

Run: `uv run pytest tests/test_apply.py -x -q 2>&1 | head -5` Expected: FAIL with `TypeError: backup_file() got an unexpected keyword argument` — that is Task 2's job. Commit Task 1 and Task 2 back-to-back before pushing so CI never sees the intermediate state.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/writer/backup.py tests/unit/writer/test_backup.py
git commit -m "feat(backup): write-once BackupStore keys namespaced by run/action/role (DMR-01)"
```

---

### Task 2: Apply wires action/role backup keys + DMR-01 regression

**Files:**

- Modify: `src/docmend/writer/apply.py:416-481` (the two `backup_file` call sites in `_execute_action`)
- Test: `tests/test_apply.py` (append one regression test)

**Interfaces:**

- Consumes: Task 1's `backup_file(..., action_seq=..., role=...)`.
- Produces: nothing new — manifest records keep carrying the returned absolute paths as opaque strings, so `restore.py` needs no change.

- [ ] **Step 1: Write the failing DMR-01 regression test**

Append to `tests/test_apply.py` (module-level imports it already has cover most of this; add the missing ones to the module's import block: `Operation` from `docmend.transform.dispatch`, `ActionProvenance`/`PlanTotals` from `docmend.plan`, `run_restore` from `docmend.restore`, `read_manifest` from `docmend.writer.manifest` — check which are already imported first):

```python
def _sha256(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _dmr01_action(
    run_id: str,
    seq: int,
    path: str,
    ops: list[Operation],
    target: str | None,
    data: bytes,
) -> PlanAction:
    return PlanAction(
        action_id=f"{run_id}/a{seq}",
        docmend_id=f"00000000-0000-7000-8000-00000000000{seq}",
        path=path,
        source_sha256=_sha256(data),
        source_size_bytes=len(data),
        operations=ops,
        target_path=target,
        provenance=ActionProvenance(
            detected_encoding=None,
            newline_style="crlf" if b"\r" in data else "lf",
        ),
    )


def test_dmr01_colliding_backup_keys__both_preserved_and_restorable(tmp_path: Path) -> None:
    """DMR-01 defense in depth: a crafted plan with an in-place rewrite of a.md
    AND a rename a.txt -> a.md (overwrite policy) must preserve every byte
    stream under distinct backup keys, and restore must reproduce both
    originals. The Task 5 output ledger stops the planner emitting this plan,
    but execute_plan accepts crafted plans — the backup layer must not rely on
    the planner being correct."""
    root = tmp_path / "corpus"
    root.mkdir()
    md_original = b"alpha\r\n"  # dirty: CRLF forces a rewrite action
    txt_original = b"bravo\n"  # clean content: rename-only action
    (root / "a.md").write_bytes(md_original)
    (root / "a.txt").write_bytes(txt_original)

    config = DocmendConfig()
    config = config.model_copy(
        update={"rename": config.rename.model_copy(update={"on_collision": "overwrite"})}
    )
    run_id = "run_20260710T000000Z_00d0a1"

    plan = Plan(
        run_id=run_id,
        generated_at="2026-07-10T00:00:00+00:00",
        generated_by="docmend test",
        inventory_ref=ArtifactRef(path="unused", run_id=run_id, sha256=_sha256(b"")),
        source_root=str(root),
        config=config.model_dump(mode="json"),
        actions=[
            _dmr01_action(run_id, 1, "a.md", ["normalize_newlines"], None, md_original),
            _dmr01_action(run_id, 2, "a.txt", ["rename"], "a.md", txt_original),
        ],
        skips=[],
        totals=PlanTotals(actions=2, skips=0),
    )

    backup_root = tmp_path / "backups"
    manifest_path = tmp_path / "manifest.jsonl"
    report = execute_plan(
        plan,
        config,
        run_id=run_id,
        plan_ref=ArtifactRef(path="unused", run_id=run_id, sha256=_sha256(b"")),
        options=ApplyOptions(
            write=True, backup_root=backup_root, preserved_by=None, allow_no_backup=False
        ),
        manifest_path=manifest_path,
        started_at="2026-07-10T00:00:00+00:00",
    )
    assert report.totals.applied == 2, [o.status for o in report.outcomes]

    records = read_manifest(manifest_path)
    backup_paths = {r.backup_path for r in records if r.backup_path is not None} | {
        r.overwritten_backup_path for r in records if r.overwritten_backup_path is not None
    }
    # a1's source copy of a.md, a2's source copy of a.txt, and a2's
    # overwritten-role copy of the (already rewritten) a.md — three distinct
    # keys, none clobbered.
    assert len(backup_paths) == 3
    stored = {Path(p).read_bytes() for p in backup_paths}
    assert stored == {md_original, txt_original, b"alpha\n"}

    outcomes = run_restore(
        records,
        run_id="run_20260710T000001Z_00d0a2",
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )
    assert all(o.status == "restored" for o in outcomes), [
        (o.path, o.status, o.detail) for o in outcomes
    ]
    assert (root / "a.md").read_bytes() == md_original
    assert (root / "a.txt").read_bytes() == txt_original
```

The subtlety the byte assertions encode: a2 runs after a1, so the target `a.md` it overwrites holds a1's **rewritten** bytes (`b"alpha\n"`) — that is what a2's overwritten-role backup preserves. LIFO restore unwinds a2 first (reinstating `a.txt` and the rewritten `a.md`), then a1 (reinstating the CRLF `a.md`) — ending byte-identical to the start. That is exactly the recovery DMR-01 destroyed.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_apply.py::test_dmr01_colliding_backup_keys__both_preserved_and_restorable -v` Expected: FAIL — `TypeError: backup_file() got an unexpected keyword argument 'action_seq'` (the call sites still use the old signature).

- [ ] **Step 3: Update the two call sites in `_execute_action`**

In `src/docmend/writer/apply.py`, add a helper above `_execute_action` (near `_operation_kind`):

```python
def _action_seq(action: PlanAction) -> str:
    """The `aN` tail of `action_id` (`{run_id}/aN`) — the BackupStore's
    per-action key segment (adr-0019/adr-0004 amendment)."""
    return action.action_id.rsplit("/", 1)[-1]
```

Overwritten-target call site (currently `apply.py:432-438`) becomes:

```python
                overwritten_backup = backup_file(
                    target_bytes,
                    backup_root=options.backup_root,
                    run_id=run_id,
                    action_seq=_action_seq(action),
                    role="overwritten",
                    relative_path=str(action.target_path),
                    expected_sha256=overwritten_sha,
                )
```

Source call site (currently `apply.py:459-465`) becomes:

```python
            backup_path = backup_file(
                data,
                backup_root=options.backup_root,
                run_id=run_id,
                action_seq=_action_seq(action),
                role="source",
                relative_path=action.path,
                expected_sha256=action.source_sha256,
            )
```

- [ ] **Step 4: Run the regression + the whole apply/restore test set**

Run: `uv run pytest tests/test_apply.py tests/test_restore.py tests/test_restore_drill.py tests/unit/writer/ -q` Expected: PASS. If any pre-existing test asserts the old backup path layout (search: `rg -l 'backups' tests/ | xargs rg -l 'run_'`), update its expected path to insert the `aN/{role}/` segments — the layout is the contract change, the behavior assertions stay.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/writer/apply.py tests/test_apply.py
git commit -m "feat(apply): route backups through run/action/role keys + DMR-01 regression"
```

---

### Task 3: Randomized staging names in the writer's atomic primitives

**Files:**

- Modify: `src/docmend/writer/atomic.py:44-57` (`_write_temp`) and the stale residue comment at `atomic.py:81-90`
- Test: `tests/unit/writer/test_atomic.py` (append two tests)

**Interfaces:**

- Consumes: nothing new.
- Produces: unchanged public API; staging names become `.{name}.{8-hex}.docmend-tmp`, and an `EEXIST` on a candidate name is retried as a name collision (never surfaced as a write failure). Every writer mutation and Task 1's backups inherit retry-after-crash for free.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/writer/test_atomic.py` (add `import pytest` to the module imports if absent):

```python
def test_stale_staging_residue__does_not_block_retry(tmp_path: Path) -> None:
    """A hard kill can leave a staging file behind; with the old FIXED temp
    name (.{name}.docmend-tmp) the next attempt's O_EXCL open failed forever.
    Randomized names make residue inert (rev 0.26 / adr-0021 staging rule)."""
    target = tmp_path / "a.md"
    (tmp_path / ".a.md.docmend-tmp").write_bytes(b"legacy stale residue")
    atomic.atomic_write_bytes(target, b"fresh\n")
    assert target.read_bytes() == b"fresh\n"
    assert (tmp_path / ".a.md.docmend-tmp").read_bytes() == b"legacy stale residue"


def test_staging_name_collision__retried_not_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EEXIST on a generated candidate is a NAME COLLISION, not an
    environmental write failure: the writer must retry a fresh name, leave the
    colliding residue untouched, and still publish (plan-review F5)."""
    target = tmp_path / "a.md"
    residue = tmp_path / ".a.md.deadbeef.docmend-tmp"
    residue.write_bytes(b"stale residue from a killed run")
    tokens = iter(["deadbeef", "cafe0000"])
    monkeypatch.setattr(atomic.secrets, "token_hex", lambda _n: next(tokens))
    atomic.atomic_write_bytes(target, b"fresh\n")
    assert target.read_bytes() == b"fresh\n"
    assert residue.read_bytes() == b"stale residue from a killed run"
    assert not (tmp_path / ".a.md.cafe0000.docmend-tmp").exists()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/writer/test_atomic.py -k "residue or collision" -v` Expected: FAIL — the first with `WriteError: ... cannot stage write (File exists)`? No: the first plants only the _legacy_ fixed name, which the old code collides with — `WriteError` — while the second fails with `AttributeError: module ... has no attribute 'secrets'` (the module does not import `secrets` yet). Both red states are the intended missing behavior.

- [ ] **Step 3: Randomize the staging name with EEXIST retry**

In `src/docmend/writer/atomic.py`, add `import secrets` to the imports, then replace `_write_temp`:

```python
def _write_temp(target: Path, data: bytes, mode: int | None) -> Path:
    # Randomized per attempt (rev 0.26): a fixed staging name meant a hard
    # kill's residue blocked every later attempt at the same target with a
    # spurious O_EXCL failure, and made the staging path predictable to an
    # interfering process. Residue from a killed attempt is inert; EEXIST on
    # a candidate is a name collision to retry with a fresh name (bounded so
    # a pathological directory cannot loop forever), never an environmental
    # write failure — those propagate as OSError.
    for _ in range(8):
        tmp = target.with_name(f".{target.name}.{secrets.token_hex(4)}.docmend-tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        break
    else:
        msg = f"{target}: could not allocate a staging name in 8 attempts"
        raise OSError(msg)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            tmp.chmod(mode & 0o7777)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return tmp
```

Then update the stale comment inside `atomic_write_bytes`'s `if not clobber:` block — replace the sentence "a later write attempt will surface it as an O_EXCL collision on the temp-file stage." so the block reads:

```python
        # The link above already succeeded, so target now holds the new bytes
        # — the publish happened. The stray staging name is just a second name
        # for that same inode (lossless residue); staging names are randomized
        # per attempt and EEXIST-retried, so residue never blocks a retry.
        # Reporting WriteError here would tell the caller the mutation failed
        # when it didn't — worse than the residue, so we swallow this one
        # deliberately.
```

- [ ] **Step 4: Run the writer unit tests**

Run: `uv run pytest tests/unit/writer/test_atomic.py -v` Expected: PASS (including the pre-existing crash-during-replace test).

- [ ] **Step 5: Commit**

```bash
git add src/docmend/writer/atomic.py tests/unit/writer/test_atomic.py
git commit -m "fix(atomic): randomized EEXIST-retried staging so kill residue never blocks retry"
```

---

### Task 4: Randomized exclusive staging for JSON artifacts

**Files:**

- Modify: `src/docmend/artifacts.py:93-102` (`write_json_artifact`)
- Test: `tests/test_inventory_artifact.py` (append two tests)

**Interfaces:**

- Consumes: nothing new.
- Produces: unchanged `write_json_artifact(document, path)` signature; staging becomes randomized `O_EXCL` in the destination directory (closing DMR-02's predictable-truncation vector), cleanup covers **every** failure class including serialization errors, and artifact modes stay **umask-derived exactly as today** — the temp is created with mode `0o666` which the kernel masks at `os.open`, so no `os.umask()` call and no policy change (permission policy is deferred to sub-project 4; plan-review F6).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_inventory_artifact.py`:

```python
def test_artifact_staging__randomized_and_retry_safe(tmp_path: Path) -> None:
    """DMR-02: the old fixed '<name>.tmp' sibling was a predictable truncation
    target and blocked nothing on collision. Staging must be O_EXCL-random:
    pre-existing residue at the legacy name must be left untouched and must
    not block the write."""
    dest = tmp_path / "out.json"
    legacy_residue = tmp_path / "out.json.tmp"
    legacy_residue.write_bytes(b"victim bytes that must survive")
    artifacts.write_json_artifact({"k": "v"}, dest)
    assert json.loads(dest.read_text()) == {"k": "v"}
    assert legacy_residue.read_bytes() == b"victim bytes that must survive"
    leftovers = sorted(p.name for p in tmp_path.iterdir())
    assert leftovers == ["out.json", "out.json.tmp"]  # staging temp cleaned up
    # F6: modes stay umask-derived — no artifact-mode policy is decided here.
    umask = os.umask(0)
    os.umask(umask)
    assert (dest.stat().st_mode & 0o777) == (0o666 & ~umask)


def test_artifact_staging__serialization_failure_leaves_no_residue(tmp_path: Path) -> None:
    """plan-review F4: json.dump can raise TypeError on a non-serializable
    document; cleanup must cover that class too, not only OSError."""
    dest = tmp_path / "out.json"
    with pytest.raises(TypeError):
        artifacts.write_json_artifact({"k": object()}, dest)
    assert not dest.exists()
    assert list(tmp_path.iterdir()) == []
```

(Add `import json`, `import os`, `import pytest`, and `from docmend import artifacts` to the module's imports if not already present.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_inventory_artifact.py -k "staging" -v` Expected: FAIL — the first at the `legacy_residue` assertion (the current code truncates `out.json.tmp`); the second at the residue assertion (the temp survives a `TypeError`).

- [ ] **Step 3: Rewrite `write_json_artifact`**

In `src/docmend/artifacts.py`, add `import secrets` to the imports and replace the function:

```python
def write_json_artifact(document: dict[str, object], path: Path) -> None:
    """Atomically write one JSON-document artifact (random O_EXCL temp + fsync +
    os.replace). Staging is randomized per attempt (rev 0.26, adr-0021): the
    old fixed '<name>.tmp' sibling was a predictable truncation target and a
    permanent retry blocker after a hard kill; EEXIST on a candidate is a name
    collision to retry, never an environmental failure. The temp is unlinked
    on EVERY unpublished exit — json.dump's TypeError/ValueError included, not
    only OSError. The 0o666 create mode is masked by the process umask AT
    os.open (kernel-side), so artifact modes stay exactly what plain open()
    produced before — permission POLICY is deliberately not decided here
    (deferred to the observability sub-project; plan-review F6/adr-0021
    amendment).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(8):
        tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError:
            continue
        break
    else:
        msg = f"{path}: could not allocate a staging name in 8 attempts"
        raise OSError(msg)
    published = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(document, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(path)
        published = True
    finally:
        if not published:
            tmp.unlink(missing_ok=True)
```

- [ ] **Step 4: Run the artifact test files**

Run: `uv run pytest tests/test_inventory_artifact.py tests/test_plan_artifact.py tests/test_report_artifact.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/artifacts.py tests/test_inventory_artifact.py
git commit -m "fix(artifacts): randomized O_EXCL staging, full-failure-class cleanup (DMR-02)"
```

---

### Task 5: Plan-time output ledger

**Files:**

- Modify: `src/docmend/planning.py:218-357` (the `claimed_targets` machinery in `build_plan`)
- Test: `tests/test_planning.py` (append two tests to `TestCollisions`)

**Interfaces:**

- Consumes: nothing new.
- Produces: `build_plan` behavior change only — every emitted action claims its **effective output path** (`target_path` for renames, `path` for in-place rewrites); a later action whose output is claimed skips with reason `collision`. No signature change.

- [ ] **Step 1: Write the failing tests**

Append inside `class TestCollisions` in `tests/test_planning.py`. First check how its neighboring tests (`test_case_variant_sources__*`) build an overwrite-policy config + inventory and call `planning.build_plan`; reuse that exact helper if one exists. If none is shared, add this helper method and the two tests:

```python
    def _plan_with_overwrite(self, tmp_path: Path) -> Plan:
        config = DocmendConfig()
        config = config.model_copy(
            update={"rename": config.rename.model_copy(update={"on_collision": "overwrite"})}
        )
        run_id = "run_20260710T000000Z_0a1ed9"
        generated_at = "2026-07-10T00:00:00+00:00"
        inventory = discovery.scan(tmp_path, config, run_id=run_id, generated_at=generated_at)
        return planning.build_plan(
            inventory,
            config,
            run_id=run_id,
            generated_at=generated_at,
            inventory_ref=ArtifactRef(path="unused", run_id=run_id, sha256="sha256:" + "0" * 64),
        )

    def test_rewrite_claims_own_path__later_rename_skips(self, tmp_path: Path) -> None:
        """DMR-01, rev 0.26 output ledger: an in-place rewrite of a.md claims
        'a.md' as an output, so a.txt -> a.md must skip even under overwrite —
        'overwrite' licenses clobbering pre-existing files, never another
        planned action's output (G-005). Sorted order: a.md < a.txt, so the
        rewrite claims first."""
        (tmp_path / "a.md").write_bytes(b"alpha\r\n")  # CRLF: rewrite action
        (tmp_path / "a.txt").write_bytes(b"bravo\n")  # clean: rename-only
        plan = self._plan_with_overwrite(tmp_path)
        assert [a.path for a in plan.actions] == ["a.md"]
        [skip] = [s for s in plan.skips if s.path == "a.txt"]
        assert skip.reason == "collision"
        assert "already claimed" in skip.detail

    def test_rename_claims_target__later_rewrite_skips(self, tmp_path: Path) -> None:
        """Mirror ordering: 'a.TXT' sorts before 'a.md', so the rename claims
        the a.md output first and the in-place rewrite of a.md skips — the
        rename is about to replace those bytes anyway; executing both would
        be the DMR-01 double-claim."""
        (tmp_path / "a.TXT").write_bytes(b"bravo\n")
        (tmp_path / "a.md").write_bytes(b"alpha\r\n")
        plan = self._plan_with_overwrite(tmp_path)
        assert [a.path for a in plan.actions] == ["a.TXT"]
        [skip] = [s for s in plan.skips if s.path == "a.md"]
        assert skip.reason == "collision"
        assert "already claimed" in skip.detail
```

(`Plan`, `ArtifactRef`, `DocmendConfig`, `discovery`, and `planning` are already imported by the module — verify and add any that are missing to its import block, not inline.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest "tests/test_planning.py::TestCollisions::test_rewrite_claims_own_path__later_rename_skips" "tests/test_planning.py::TestCollisions::test_rename_claims_target__later_rewrite_skips" -v` Expected: FAIL — both plans currently contain 2 actions (no ledger).

- [ ] **Step 3: Generalize `claimed_targets` into the output ledger**

In `src/docmend/planning.py`:

1. Replace the declaration and its comment (currently `planning.py:218-225`):

```python
    # Output ledger (rev 0.26, DMR-01): EVERY emitted action claims its
    # effective output path — target_path for renames, the file's own path for
    # in-place rewrites — so no two actions in one plan can share an output
    # (and therefore no two backups can share a key). The old set tracked only
    # rename targets, which let an in-place rewrite of a.md and a.txt -> a.md
    # both claim a.md's bytes. `pending` is processed in the globally sorted
    # order set by discovery.py, so the lexicographically first claimant wins
    # deterministically; never policy-overridable — `overwrite` licenses
    # clobbering a pre-existing target (AW-002), not another planned action's
    # output (G-005). Values are the claiming source path, for skip details.
    claimed_outputs: dict[str, str] = {}
```

2. Update the rename-candidate early check (currently `planning.py:318-336`) — the condition and detail become:

```python
                    if candidate in claimed_outputs:
                        skips.append(
                            SkipDecision(
                                path=record.path,
                                reason="collision",
                                detail=(
                                    f"target {candidate} already claimed by an "
                                    f"earlier action this run ({claimed_outputs[candidate]})"
                                ),
                            )
                        )
                        log.debug("planned skip", path=record.path, reason="collision")
                        continue
```

3. Replace the claim site (currently `planning.py:355-356`, the `if target is not None: claimed_targets.add(target)` just before `seq += 1`) with the unified claim covering in-place outputs too:

```python
                effective_output = target if target is not None else record.path
                if effective_output in claimed_outputs:
                    # In-place rewrite whose own path an earlier rename claimed
                    # (the rename is about to replace these bytes; executing
                    # both is the DMR-01 double-claim).
                    skips.append(
                        SkipDecision(
                            path=record.path,
                            reason="collision",
                            detail=(
                                f"output path {effective_output} already claimed by an "
                                f"earlier action this run ({claimed_outputs[effective_output]})"
                            ),
                        )
                    )
                    log.debug("planned skip", path=record.path, reason="collision")
                    continue
                claimed_outputs[effective_output] = record.path
```

- [ ] **Step 4: Run the planning suite**

Run: `uv run pytest tests/test_planning.py tests/test_weird_corpus.py -q` Expected: PASS — the two new tests plus every existing `TestCollisions` case (the rename-target early check behaves identically for the pure-rename claims it already covered).

- [ ] **Step 5: Commit**

```bash
git add src/docmend/planning.py tests/test_planning.py
git commit -m "feat(planning): output ledger reserves every action's effective output (DMR-01)"
```

---

### Task 6: `guard_artifact_destination` in artifacts.py

**Files:**

- Modify: `src/docmend/artifacts.py` (new function after `validate_artifact`; new imports)
- Test: Create `tests/test_artifact_guard.py`

**Interfaces:**

- Consumes: `pathspec.PathSpec` (already a runtime dependency).
- Produces: `guard_artifact_destination(destination: Path, *, corpus_root: Path | None, input_artifacts: Iterable[Path] = (), artifact_root: Path | None = None, exclude: PathSpec[GitIgnoreSpecPattern] | None = None) -> str | None` — returns a refusal message, or `None` when safe. The carve-out is **destination-specific** (plan-review F2): an in-corpus candidate is licensed only when it lies under `artifact_root` AND its own corpus-relative path matches `exclude`. Containment is checked for **both** the lexical directory entry (resolved parent + final name, final component not followed) and the fully resolved referent (plan-review F3). Tasks 7–9 call it via `_guard_artifact_paths` in `cli.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_artifact_guard.py`:

```python
"""Artifact destination guard (rev 0.26 IR-007, adr-0021, DMR-02).

Pure-function tests; the CLI wiring (refusal exit 3 before the pipeline runs)
is covered in the per-command CLI test files. The guard checks BOTH the
lexical directory entry publication replaces AND the resolved referent
(plan-review F3), and licenses the .docmend/ carve-out per actual destination
against the effective excludes (plan-review F2).
"""

from pathlib import Path

from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from docmend.artifacts import guard_artifact_destination

DEFAULT_EXCLUDES = ["**/.docmend/**"]


def _spec(lines: list[str]) -> PathSpec[GitIgnoreSpecPattern]:
    return PathSpec.from_lines(GitIgnoreSpecPattern, lines)


def _corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "victim.txt").write_bytes(b"corpus document\n")
    return root


def test_destination_inside_corpus__refused(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    refusal = guard_artifact_destination(root / "victim.txt", corpus_root=root)
    assert refusal is not None
    assert "inside" in refusal


def test_destination_outside_corpus__allowed(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    assert guard_artifact_destination(tmp_path / "report.json", corpus_root=root) is None


def test_symlink_outside_name_inside_referent__refused(tmp_path: Path) -> None:
    """An out-of-corpus NAME aliasing an in-corpus file: the resolved referent
    is inside, so publication would rewrite corpus bytes."""
    root = _corpus(tmp_path)
    link = tmp_path / "innocent.json"
    link.symlink_to(root / "victim.txt")
    refusal = guard_artifact_destination(link, corpus_root=root)
    assert refusal is not None
    assert (root / "victim.txt").read_bytes() == b"corpus document\n"


def test_symlink_inside_name_outside_referent__refused(tmp_path: Path) -> None:
    """The F3 mirror: an in-corpus NAME resolving outside. os.replace swaps
    the directory ENTRY, so the corpus-owned symlink entry would be replaced
    even though the referent is external — lexical containment must refuse."""
    root = _corpus(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"external file\n")
    link = root / "looks-internal.json"
    link.symlink_to(outside)
    refusal = guard_artifact_destination(link, corpus_root=root)
    assert refusal is not None
    assert link.is_symlink()  # refusal is non-mutating: the entry survives
    assert outside.read_bytes() == b"external file\n"


def test_carveout_allows_excluded_docmend_destination(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    artifact_root = root / ".docmend"
    dest = artifact_root / "docmend-run-inventory.json"
    assert (
        guard_artifact_destination(
            dest,
            corpus_root=root,
            artifact_root=artifact_root,
            exclude=_spec(DEFAULT_EXCLUDES),
        )
        is None
    )


def test_carveout_negated_destination__refused(tmp_path: Path) -> None:
    """plan-review F2: gitignore negation can re-include ONE destination while
    the rest of .docmend/ stays excluded — the license is per destination,
    so the re-included path is refused."""
    root = _corpus(tmp_path)
    artifact_root = root / ".docmend"
    dest = artifact_root / "docmend-run-report.json"
    spec = _spec(["**/.docmend/**", "!.docmend/docmend-run-report.json"])
    refusal = guard_artifact_destination(
        dest, corpus_root=root, artifact_root=artifact_root, exclude=spec
    )
    assert refusal is not None


def test_carveout_withdrawn__docmend_destination_refused(tmp_path: Path) -> None:
    """No exclude covering the destination (operator replaced the exclude set)
    means the canonical root is scannable corpus space: license withdrawn."""
    root = _corpus(tmp_path)
    artifact_root = root / ".docmend"
    dest = artifact_root / "docmend-run-inventory.json"
    refusal = guard_artifact_destination(
        dest, corpus_root=root, artifact_root=artifact_root, exclude=_spec(["*.bin"])
    )
    assert refusal is not None


def test_excluded_but_outside_artifact_root__refused(tmp_path: Path) -> None:
    """Exclusion alone is not a license: only the canonical artifact root is
    the authorized in-corpus namespace (adr-0021)."""
    root = _corpus(tmp_path)
    (root / "notes").mkdir()
    dest = root / "notes" / "report.json"
    refusal = guard_artifact_destination(
        dest,
        corpus_root=root,
        artifact_root=root / ".docmend",
        exclude=_spec(["**/.docmend/**", "notes/"]),
    )
    assert refusal is not None


def test_alias_of_invocation_input__refused(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    inventory = tmp_path / "inventory.json"
    inventory.write_bytes(b"{}")
    refusal = guard_artifact_destination(
        inventory, corpus_root=root, input_artifacts=[inventory]
    )
    assert refusal is not None
    assert "input" in refusal


def test_non_regular_destination__refused(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    directory = tmp_path / "adir"
    directory.mkdir()
    refusal = guard_artifact_destination(directory, corpus_root=root)
    assert refusal is not None


def test_no_corpus_root__only_alias_and_type_rules_apply(tmp_path: Path) -> None:
    assert guard_artifact_destination(tmp_path / "x.json", corpus_root=None) is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_artifact_guard.py -v` Expected: FAIL at collection — `ImportError: cannot import name 'guard_artifact_destination'`.

- [ ] **Step 3: Implement the guard**

In `src/docmend/artifacts.py`, extend the `collections.abc` import to include `Iterable`, add `from pathspec import PathSpec` and `from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern` to the imports, and add after `validate_artifact`:

```python
def guard_artifact_destination(
    destination: Path,
    *,
    corpus_root: Path | None,
    input_artifacts: Iterable[Path] = (),
    artifact_root: Path | None = None,
    exclude: PathSpec[GitIgnoreSpecPattern] | None = None,
) -> str | None:
    """One source-aware preflight for every CLI artifact write (rev 0.26
    IR-007, adr-0021, DMR-02): docmend's own artifacts must never be able to
    mutate the corpus they describe, and a refused write must precede the
    pipeline, not follow it. Returns the refusal message, or None when safe.

    Containment is judged on TWO candidates, because publication is
    tmp.replace(destination): the LEXICAL directory entry the replace swaps
    (resolved parent + final name, final component deliberately not followed)
    and the fully RESOLVED referent. An in-corpus name aliasing an external
    file mutates the corpus's directory entry; an external name aliasing an
    in-corpus file mutates corpus bytes — both must refuse.

    The .docmend/ carve-out (adr-0021) is licensed PER DESTINATION: a
    candidate inside the corpus is allowed only when it lies under
    `artifact_root` AND its own corpus-relative path matches `exclude` — a
    gitignore negation that re-includes one destination withdraws exactly
    that destination's license, and an operator-replaced exclude set
    withdraws the root wholesale.
    """
    lexical = destination.parent.resolve() / destination.name
    resolved = destination.resolve()
    if resolved.exists() and not resolved.is_file():
        return f"{destination}: artifact destination is not a regular file"
    for artifact in input_artifacts:
        if resolved == Path(artifact).resolve():
            return (
                f"{destination}: artifact destination aliases an input artifact "
                f"of this invocation ({artifact})"
            )
    if corpus_root is None:
        return None
    root = corpus_root.resolve()
    licensed_root = artifact_root.resolve() if artifact_root is not None else None
    for candidate in {lexical, resolved}:
        if not candidate.is_relative_to(root):
            continue
        licensed = (
            licensed_root is not None
            and candidate.is_relative_to(licensed_root)
            and exclude is not None
            and exclude.match_file(candidate.relative_to(root).as_posix())
        )
        if not licensed:
            return (
                f"{destination}: artifact destination resolves inside the corpus "
                f"root {root} (only excluded destinations under the canonical "
                f"artifact root are legal in-corpus writes; adr-0021)"
            )
    return None
```

- [ ] **Step 4: Run the guard tests**

Run: `uv run pytest tests/test_artifact_guard.py -v` Expected: PASS (all 11).

- [ ] **Step 5: Commit**

```bash
git add src/docmend/artifacts.py tests/test_artifact_guard.py
git commit -m "feat(artifacts): destination guard - lexical+resolved containment, per-destination carve-out (DMR-02)"
```

---

### Task 7: Guard wiring — `scan`

**Files:**

- Modify: `src/docmend/cli.py` (new `_guard_artifact_paths` helper + `scan` body at `cli.py:173-203`)
- Test: `tests/test_cli_scan.py` (append one test class)

**Interfaces:**

- Consumes: Task 6's `guard_artifact_destination`.
- Produces: `_guard_artifact_paths(destinations: list[Path], *, corpus_root: Path | None, input_artifacts: list[Path], config: DocmendConfig) -> None` in `cli.py` — builds the exclude spec from the effective config, passes the canonical artifact root, echoes `refused [artifact-destination]: …` and raises `typer.Exit(3)` on refusal. Tasks 8–9 reuse it.

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/test_cli_scan.py` (module-level `runner` and the existing autouse fixtures apply; note the module's `corpus` fixture already chdirs into `tmp_path`):

```python
class TestScanArtifactGuard:
    """rev 0.26 IR-007 / adr-0021 / DMR-02: unsafe --report destinations are
    refused at exit 3 BEFORE the walk; the OQ-034 default keeps working."""

    def test_report_inside_corpus__refused_exit_3_source_intact(self, corpus: Path) -> None:
        victim = corpus / "a.txt"
        before = victim.read_bytes()
        result = runner.invoke(app, ["scan", str(corpus), "--report", str(victim)])
        assert result.exit_code == 3
        assert "artifact-destination" in result.output
        assert victim.read_bytes() == before

    def test_default_docmend_root__still_works(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OQ-034/NFR-006: the zero-setup default (`scan .` writing under
        ./.docmend/) is binding behavior — the carve-out must keep it."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "doc.txt").write_text("clean\n")
        result = runner.invoke(app, ["scan", "."])
        assert result.exit_code == 0, result.output
        assert list(Path(".docmend").glob("docmend-run_*-inventory.json"))

    def test_docmend_exclusion_removed__default_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The carve-out is licensed by the exclusion (adr-0021): --exclude
        REPLACES the exclude set (OQ-029), so a set without .docmend/
        withdraws the license and the default in-corpus destination refuses."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "doc.txt").write_text("clean\n")
        result = runner.invoke(app, ["scan", ".", "--exclude", "*.bin"])
        assert result.exit_code == 3
        assert "artifact-destination" in result.output
        assert not list(Path(".docmend").glob("docmend-run_*-inventory.json"))

    def test_negated_default_destination__refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """plan-review F2: a negation re-including the exact inventory
        destination withdraws that one destination's license even though the
        rest of .docmend/ stays excluded."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "doc.txt").write_text("clean\n")
        result = runner.invoke(
            app,
            [
                "scan",
                ".",
                "--exclude",
                "**/.docmend/**",
                "--exclude",
                "!.docmend/docmend-*-inventory.json",
            ],
        )
        assert result.exit_code == 3
        assert "artifact-destination" in result.output
        assert not list(Path(".docmend").glob("docmend-run_*-inventory.json"))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_cli_scan.py::TestScanArtifactGuard -v` Expected: `test_default_docmend_root__still_works` PASSES already (carve-out regression baseline); the other three FAIL — exit 0/1 instead of 3, and the first replaces `a.txt` with inventory JSON.

- [ ] **Step 3: Add the helper and wire `scan`**

In `src/docmend/cli.py`, add imports `from pathspec import PathSpec` and `from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern` (top of file, with the other imports), then add near `_load_effective_config`:

```python
def _guard_artifact_paths(
    destinations: list[Path],
    *,
    corpus_root: Path | None,
    input_artifacts: list[Path],
    config: DocmendConfig,
) -> None:
    """Refuse unsafe artifact destinations BEFORE the pipeline runs (rev 0.26
    IR-007, adr-0021): a refused write must not follow a completed scan. The
    .docmend/ carve-out is licensed per destination against the effective
    exclude patterns — if the operator's excludes no longer cover a
    destination, that destination is scannable corpus space and loses its
    license (guard_artifact_destination owns the decision)."""
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude)
    artifact_root = Path(ARTIFACT_DIR_NAME).resolve()
    for destination in destinations:
        refusal = artifacts.guard_artifact_destination(
            destination,
            corpus_root=corpus_root,
            input_artifacts=input_artifacts,
            artifact_root=artifact_root,
            exclude=exclude,
        )
        if refusal is not None:
            typer.echo(f"refused [artifact-destination]: {refusal}", err=True)
            raise typer.Exit(3)
```

In `scan`, compute the output path before the walk and guard it — insert after `log.info("scan starting", ...)`:

```python
    out_path = report if report is not None else artifact_dir / f"docmend-{run_id}-inventory.json"
    corpus_root = (path if path.is_dir() else path.parent).resolve()
    _guard_artifact_paths([out_path], corpus_root=corpus_root, input_artifacts=[], config=config)

    inventory = discovery.scan(path, config, run_id=run_id, generated_at=now.isoformat())
    artifacts.write_inventory(inventory, out_path)
```

(and delete the old `out_path = …` line that followed the scan).

- [ ] **Step 4: Run the scan CLI suite**

Run: `uv run pytest tests/test_cli_scan.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/cli.py tests/test_cli_scan.py
git commit -m "feat(cli): artifact destination guard on scan (DMR-02)"
```

---

### Task 8: Guard wiring — `plan`

**Files:**

- Modify: `src/docmend/cli.py:271-313` (both branches of `plan`)
- Test: `tests/test_cli_plan.py` (append two tests)

**Interfaces:**

- Consumes: Task 7's `_guard_artifact_paths`.
- Produces: nothing new.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_plan.py` (module-level `runner`; check the module's existing corpus conventions — tests chdir via `monkeypatch.chdir(tmp_path)` and build small corpora inline):

```python
class TestPlanArtifactGuard:
    """rev 0.26 IR-007 / adr-0021 / DMR-02 wiring for both plan branches."""

    def test_out_inside_corpus__refused_exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        victim = corpus / "victim.txt"
        victim.write_bytes(b"corpus document\n")
        result = runner.invoke(app, ["plan", str(corpus), "--out", str(victim)])
        assert result.exit_code == 3
        assert "artifact-destination" in result.output
        assert victim.read_bytes() == b"corpus document\n"

    def test_out_aliasing_inventory_input__refused_exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A destination outside the corpus can still corrupt the pipeline by
        aliasing this invocation's own input (adr-0021)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "doc.txt").write_text("clean\n")
        inventory_path = tmp_path / "inventory.json"
        scan_result = runner.invoke(
            app, ["scan", str(corpus), "--report", str(inventory_path)]
        )
        assert scan_result.exit_code == 0, scan_result.output
        result = runner.invoke(
            app,
            ["plan", "--inventory", str(inventory_path), "--out", str(inventory_path)],
        )
        assert result.exit_code == 3
        assert "artifact-destination" in result.output
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_cli_plan.py::TestPlanArtifactGuard -v` Expected: FAIL — current exit codes are 0/1 and the destination files are replaced.

- [ ] **Step 3: Wire both branches**

In `plan` (`cli.py`), compute `out_path` once, before the branches (immediately after `log = get_logger(__name__)`):

```python
    out_path = out if out is not None else artifact_dir / f"docmend-{run_id}-plan.json"
```

(and delete the later duplicate assignment at the current `cli.py:312`.) In the PATH-shorthand branch, insert the guard right after `scan_root` is computed and **before** `_acquire_run_lock`:

```python
        inventory_artifact = (artifact_dir / f"docmend-{run_id}-inventory.json").resolve()
        _guard_artifact_paths(
            [out_path, inventory_artifact],
            corpus_root=scan_root,
            input_artifacts=[],
            config=config,
        )
```

(and delete the later duplicate `inventory_artifact = …` assignment at the current `cli.py:284`.) In the `--inventory` branch, insert after `inventory` is read and before `_acquire_run_lock`:

```python
        _guard_artifact_paths(
            [out_path],
            corpus_root=Path(inventory.source_root),
            input_artifacts=[inventory_path],
            config=config,
        )
```

- [ ] **Step 4: Run the plan CLI suite**

Run: `uv run pytest tests/test_cli_plan.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/cli.py tests/test_cli_plan.py
git commit -m "feat(cli): artifact destination guard on plan (DMR-02)"
```

---

### Task 9: Guard wiring — `apply` + in-lock report finalization

**Files:**

- Modify: `src/docmend/cli.py:530-584` (`apply` body)
- Test: `tests/test_cli_apply.py` (append one test class)

**Interfaces:**

- Consumes: Task 7's `_guard_artifact_paths`; the module's existing `make_corpus(root)` and `_make_plan(corpus, *, out=...)` helpers.
- Produces: nothing new. Behavior: report/manifest destinations are guarded before the lock and gate; `artifacts.write_report` moves **inside** the lock (`try:` block), so a run's artifacts finalize under the same coordination as its mutations (rev 0.26; the refusal-report write at `cli.py:550` is already in-lock and becomes safe because its path was guarded first).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_apply.py`:

```python
class TestApplyArtifactGuard:
    """rev 0.26 IR-007 / adr-0021 / DMR-02: apply's report path is guarded
    before the gate, and the report finalizes while the run lock is held."""

    def test_report_inside_corpus__refused_exit_3_before_gate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`apply --report <corpus file>` used to clobber the file even on a
        dry run and even when the write was later refused (DMR-02 repro)."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)
        victim = corpus / "b.md"
        before = victim.read_bytes()
        result = runner.invoke(app, ["apply", str(plan_path), "--report", str(victim)])
        assert result.exit_code == 3
        assert "artifact-destination" in result.output
        assert victim.read_bytes() == before

    def test_write__report_published_inside_run_lock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """rev 0.26: report finalization happens while the run lock is held,
        so a run's artifacts and corpus effects commit under one coordination
        boundary. Spies are installed AFTER plan creation (plan takes its own
        lock) and the event list starts empty for the apply invocation."""
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        make_corpus(corpus)
        plan_path = _make_plan(corpus)

        events: list[str] = []
        real_release = lock.RunLock.release
        real_write_report = cli_module.artifacts.write_report

        def spy_release(self: lock.RunLock) -> None:
            events.append("lock-released")
            real_release(self)

        def spy_write_report(report: Report, path: Path) -> None:
            events.append("report-written")
            real_write_report(report, path)

        monkeypatch.setattr(lock.RunLock, "release", spy_release)
        monkeypatch.setattr(cli_module.artifacts, "write_report", spy_write_report)

        result = runner.invoke(
            app,
            ["apply", str(plan_path), "--write", "--backup-dir", str(tmp_path / "bk")],
        )
        assert result.exit_code == 0, result.output
        assert "report-written" in events and "lock-released" in events
        assert events.index("report-written") < events.index("lock-released")
```

Add to the module's import block (top of file): `import docmend.cli as cli_module` and `from docmend.report import Report` (the module already imports `lock` and `app`).

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_cli_apply.py::TestApplyArtifactGuard -v` Expected: FAIL — the guard test sees exit 0 and `b.md` replaced with report JSON; the ordering test sees `lock-released` at index 0.

- [ ] **Step 3: Wire the guard and move the report write**

In `apply` (`cli.py`), insert the guard immediately after `report_path` is computed (current `cli.py:531`) and **before** `_acquire_run_lock_strict`:

```python
    _guard_artifact_paths(
        [report_path, manifest_path],
        corpus_root=source_root,
        input_artifacts=[plan_path, *(resume_manifest or [])],
        config=config,
    )
```

Then move the report write inside the lock — change the current

```python
        result = execute_plan(
            ...
        )
    finally:
        run_lock.release()

    artifacts.write_report(result, report_path)
```

to

```python
        result = execute_plan(
            plan,
            config,
            run_id=run_id,
            plan_ref=plan_ref,
            options=options,
            manifest_path=manifest_path,
            started_at=started_at,
            resume_records=resume_records,
        )
        # rev 0.26: the report finalizes under the same run lock as the
        # mutations it records — a run's artifacts and corpus effects commit
        # or refuse under one coordination boundary (adr-0004 amendment).
        artifacts.write_report(result, report_path)
    finally:
        run_lock.release()
```

- [ ] **Step 4: Run the apply CLI suite**

Run: `uv run pytest tests/test_cli_apply.py tests/test_cli_resume.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/cli.py tests/test_cli_apply.py
git commit -m "feat(cli): guard apply artifact paths; finalize report inside the run lock"
```

---

### Task 10: Full gate, CHANGELOG, and push

**Files:**

- Modify: `CHANGELOG.md` (new `## [Unreleased]` section at the top, above `## [1.0.2]`)

**Interfaces:** none.

- [ ] **Step 1: Run the full local gate**

Run: `uv run scripts/check.py` Expected: every stage passes — ruff format, ruff check, basedpyright, pytest (all tests incl. the ~20 new ones), coverage ≥ 97%, pip-audit clean. Fix anything it flags before proceeding (a coverage dip means a new branch lacks a test — add the test, don't lower the bar).

- [ ] **Step 2: Add the CHANGELOG entry**

Insert directly under the intro paragraph of `CHANGELOG.md`:

```markdown
## [Unreleased]

Safety-core remediation, plan A of four (spec rev 0.26; 2026-07-10 comprehensive review findings DMR-01/DMR-02; ADRs 0019–0021). Targets the eventual v2.0.0.

### Fixed

- One plan can no longer overwrite its own recovery backups (DMR-01): planning reserves every action's effective output path — in-place and rename alike — so colliding actions skip at plan time, and backups are stored under write-once keys namespaced by run, action, and role, so even a crafted plan cannot make two byte streams share a key.
- docmend's own artifacts can no longer destroy corpus inputs (DMR-02): every `scan --report`, `plan --out`, and `apply --report` destination passes a source-aware guard before the pipeline runs — both the directory entry publication replaces and its resolved referent must be outside the corpus, in-corpus destinations are refused (exit 3) except destinations under the canonical `.docmend/` root that the effective excludes still cover, and destinations aliasing an invocation's input artifacts are refused outright.
- Staging names are randomized (`O_EXCL`, collision-retried) for both corpus writes and JSON artifacts: kill residue no longer blocks retries, the predictable `<name>.tmp` truncation target is gone, artifact staging cleans up on every failure class including serialization errors, and artifact file modes are unchanged (umask-derived, as before).
- The apply report now finalizes while the run lock is held, so a run's artifacts and corpus effects commit under one coordination boundary.
```

- [ ] **Step 3: Verify markdown gates**

Run: `npx prettier --check CHANGELOG.md && npx markdownlint-cli2 CHANGELOG.md` Expected: both clean (run `npx prettier --write CHANGELOG.md` first if needed).

- [ ] **Step 4: Commit and push**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): unreleased safety-core plan A (DMR-01/02 closures)"
git push origin dev
```

---

## Self-Review Notes (updated after plan-review round 1)

- **Spec coverage (Plan A scope):** FR-006 backup keys + ledger → Tasks 1/2/5; IR-007 guard + staging → Tasks 3/4/6/7/8/9; §18.5 exit-3 classification → Tasks 7–9. FR-011's action-time invariant is Plan C; DR-003/DR-004 field changes are Plan B; the scan/plan `timeout`-skip exit-1 medium is Plan D scope.
- **Type consistency:** `BackupRole` defined Task 1, consumed Task 2; `guard_artifact_destination` signature defined Task 6 (with `artifact_root`/`exclude` — no probe, no `allowed_root`), consumed via `_guard_artifact_paths` (Task 7) by Tasks 8–9; `_action_seq` defined and consumed within Task 2; `Operation` imported in Task 2's test from `docmend.transform.dispatch`.
- **Plan-review round 1 dispositions:** F1 closed (hex run IDs `00d0a1`/`00d0a2`/`0a1ed9`; live `runner`/`make_corpus`/`_make_plan` conventions; typed spies installed after plan creation; explicit keyword calls, no kwargs spreading); F2 closed (per-destination exclude match; negation tests at guard and CLI levels); F3 closed (lexical + resolved candidates; mirror symlink tests, non-mutating refusal asserted); F4 closed (`finally`-based cleanup, serialization-failure test, umask-derived modes preserved via kernel-masked `0o666`, no umask mutation); F5 closed (bounded EEXIST retry, deterministic two-token collision test); F6 closed (lexical+resolved containment recorded in `adr-0021` + spec rev 0.27 with owner approval; 0600 policy removed, permissions deferred to sub-project 4 as the approved design already stated).
