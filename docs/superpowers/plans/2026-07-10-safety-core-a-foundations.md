# Safety-Core Plan A: Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close DMR-01 (same-plan backup overwrite) and DMR-02 (artifact destinations clobbering corpus inputs) — the plan-time output ledger, the write-once role-namespaced BackupStore, the artifact destination guard, randomized `O_EXCL` staging, and in-lock apply-report finalization.

**Architecture:** This is Plan A of four (A foundations → B manifest 2.0 → C commit boundary → D verify) implementing SPEC-VHHB rev 0.26 (`docs/specs/docmend.md`) per the approved design `docs/superpowers/specs/2026-07-10-safety-core-remediation-design.md` and ADRs `adr-0019`/`adr-0020`/`adr-0021` (+ amended `adr-0004`/`adr-0005`/`adr-0012`). Plan A has no dependency on B–D and changes no schema: manifest records already store backup paths as opaque strings, so the new key layout is value-only.

**Tech Stack:** Python 3.14 (`uv`-managed), Typer CLI, pydantic v2 strict models, pathspec, pytest.

## Global Constraints

- Full local gate (run before claiming any task complete that says "run the gate"): `uv run scripts/check.py` — ruff format → ruff check → basedpyright → coverage run -m pytest → coverage report → pip-audit. All must pass.
- Quick loop while developing: `uv run pytest <file>::<test> -v`.
- Branch coverage must stay ≥ 97% (the gate's `coverage report` enforces the configured floor).
- **Never `git add .` or `git add -A`** — stage files by explicit name only.
- This repo is **public**: test fixtures are synthetic only — never real library documents, paths, or personal content.
- Comments target the next AI session: intent, invariants, cross-file contracts, rejected alternatives. No syntax narration.
- The package version stays `1.0.2`; v2.0.0 releases only after Plans A–D all land. New behavior goes under an `## [Unreleased]` CHANGELOG section (Task 10).
- Requirement IDs cited in code comments/tests must match rev 0.26 of `docs/specs/docmend.md` (FR-006, FR-011, IR-007, DMR-01, DMR-02 are the ones this plan touches).
- Python 3.14 note: `except WriteError, OSError:` (unparenthesized, PEP 758) appears in `apply.py` — it is valid 3.14 syntax, not a bug. Do not "fix" it.

---

### Task 1: Write-once, role-namespaced BackupStore keys

**Files:**

- Modify: `src/docmend/writer/backup.py` (whole file, 48 lines)
- Test: `tests/unit/writer/test_backup.py`

**Interfaces:**

- Consumes: `docmend.writer.atomic.atomic_write_bytes(target, data, *, clobber: bool)` — with `clobber=False` it publishes via hardlink and raises `FileExistsError` if the target already exists (existing behavior, unchanged).
- Produces: `backup_file(data: bytes, *, backup_root: Path, run_id: str, action_seq: str, role: BackupRole, relative_path: str, expected_sha256: str) -> Path` and `type BackupRole = Literal["source", "overwritten"]`. Task 2 calls this from `apply.py`. Key layout: `{backup_root}/{run_id}/{action_seq}/{role}/{relative_path}`.

- [ ] **Step 1: Update the existing layout test and add the write-once + role tests (failing)**

Replace the first test in `tests/unit/writer/test_backup.py` and append two new ones:

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
    kwargs = {
        "backup_root": tmp_path / "backups",
        "run_id": RUN_ID,
        "action_seq": "a1",
        "role": "source",
        "relative_path": "a.txt",
        "expected_sha256": _sha(data),
    }
    backup.backup_file(data, **kwargs)
    with pytest.raises(backup.BackupError, match="write-once"):
        backup.backup_file(data, **kwargs)


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

Also update the three remaining existing tests (`test_backup_hash_mismatch__raises_before_mutation`, `test_backup_reread_corruption__raises`, `test_backup_destination_unwritable__raises`) to pass `action_seq="a1", role="source",` alongside their existing kwargs — no other change to them.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/writer/test_backup.py -v` Expected: FAIL — `TypeError: backup_file() got an unexpected keyword argument 'action_seq'`

- [ ] **Step 3: Rewrite `backup_file`**

Replace the body of `src/docmend/writer/backup.py` from the `def backup_file` line down (keep the module docstring's first paragraph but update the layout line, keep `BackupError`):

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

- [ ] **Step 4: Run the unit tests — they pass; run the full suite — `apply.py` call sites fail**

Run: `uv run pytest tests/unit/writer/test_backup.py -v` Expected: PASS (all 6).

Run: `uv run pytest tests/test_apply.py -x -q 2>&1 | head -20` Expected: FAIL with `TypeError: backup_file() got an unexpected keyword argument` — that is Task 2's job. Do NOT fix it here; commit the module + unit tests only (the two tasks land as one push to keep CI green, or commit Task 1 and Task 2 back-to-back before pushing).

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

Append to `tests/test_apply.py` (match the module's existing imports; add any of these that are missing):

```python
def test_dmr01_colliding_backup_keys__both_preserved_and_restorable(tmp_path: Path) -> None:
    """DMR-01 defense in depth: a crafted plan with an in-place rewrite of a.md
    AND a rename a.txt -> a.md (overwrite policy) must preserve BOTH byte
    streams under distinct backup keys, and restore must reproduce both
    originals. The Task 5 output ledger stops the planner emitting this plan,
    but execute_plan accepts crafted plans — the backup layer must not rely on
    the planner being correct."""
    from docmend.config import DocmendConfig
    from docmend.plan import ActionProvenance, ArtifactRef, Plan, PlanAction, PlanTotals
    from docmend.restore import run_restore
    from docmend.writer.apply import execute_plan
    from docmend.writer.gate import ApplyOptions
    from docmend.writer.manifest import read_manifest

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
    run_id = "run_20260710T000000Z_00dmr1"

    def sha(data: bytes) -> str:
        import hashlib

        return f"sha256:{hashlib.sha256(data).hexdigest()}"

    def action(seq: int, path: str, ops: list[str], target: str | None, data: bytes) -> PlanAction:
        return PlanAction(
            action_id=f"{run_id}/a{seq}",
            docmend_id=f"00000000-0000-7000-8000-00000000000{seq}",
            path=path,
            source_sha256=sha(data),
            source_size_bytes=len(data),
            operations=ops,  # type: ignore[arg-type]
            target_path=target,
            provenance=ActionProvenance(detected_encoding=None, newline_style="crlf" if b"\r" in data else "lf"),
        )

    plan = Plan(
        run_id=run_id,
        generated_at="2026-07-10T00:00:00+00:00",
        generated_by="docmend test",
        inventory_ref=ArtifactRef(path="unused", run_id=run_id, sha256=sha(b"")),
        source_root=str(root),
        config=config.model_dump(mode="json"),
        actions=[
            action(1, "a.md", ["normalize_newlines"], None, md_original),
            action(2, "a.txt", ["rename"], "a.md", txt_original),
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
        plan_ref=ArtifactRef(path="unused", run_id=run_id, sha256=sha(b"")),
        options=ApplyOptions(
            write=True, backup_root=backup_root, preserved_by=None, allow_no_backup=False
        ),
        manifest_path=manifest_path,
        started_at="2026-07-10T00:00:00+00:00",
    )
    assert report.totals.applied == 2, [o.model_dump() for o in report.outcomes]

    records = read_manifest(manifest_path)
    backup_paths = {r.backup_path for r in records if r.backup_path is not None} | {
        r.overwritten_backup_path for r in records if r.overwritten_backup_path is not None
    }
    # a1's source copy of a.md, a2's source copy of a.txt, a2's overwritten copy
    # of (rewritten) a.md — three distinct keys, none clobbered.
    assert len(backup_paths) == 3
    stored = {Path(p).read_bytes() for p in backup_paths}
    assert md_original in {b.replace(b"\r\n", b"\r\n") for b in stored} or md_original in stored

    outcomes = run_restore(
        records,
        run_id="run_20260710T000001Z_00dmr2",
        write=True,
        only_ids=None,
        manifest_out=tmp_path / "restore-manifest.jsonl",
    )
    assert all(o.status == "restored" for o in outcomes), [o for o in outcomes]
    assert (root / "a.md").read_bytes() == md_original
    assert (root / "a.txt").read_bytes() == txt_original
```

Note the one subtlety: action a2 runs after a1, so the target `a.md` it overwrites holds a1's **rewritten** bytes (`b"alpha\n"`), and a2's overwritten-role backup preserves those. The LIFO restore then unwinds a2 first (reinstating `a.txt` and the rewritten `a.md`), then a1 (reinstating the CRLF `a.md`) — ending byte-identical to the start. That is exactly the recovery DMR-01 destroyed.

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

Run: `uv run pytest tests/test_apply.py tests/test_restore.py tests/test_restore_drill.py tests/unit/writer/ -q` Expected: PASS. If any pre-existing test asserts the old backup path layout (search: `rg -l 'backups.*run_' tests/`), update its expected path to insert the `aN/source/` segments — the layout is the contract change, the behavior assertions stay.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/writer/apply.py tests/test_apply.py
git commit -m "feat(apply): route backups through run/action/role keys + DMR-01 regression"
```

---

### Task 3: Randomized staging names in the writer's atomic primitives

**Files:**

- Modify: `src/docmend/writer/atomic.py:44-57` (`_write_temp`) and the stale residue comment at `atomic.py:81-90`
- Test: `tests/unit/writer/test_atomic.py` (append one test)

**Interfaces:**

- Consumes: nothing new.
- Produces: unchanged public API; staging names become `.{name}.{8-hex}.docmend-tmp`. Every writer mutation and Task 1's backups inherit retry-after-crash for free.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/writer/test_atomic.py`:

```python
def test_stale_staging_residue__does_not_block_retry(tmp_path: Path) -> None:
    """A hard kill can leave a staging file behind; with the old FIXED temp
    name (.{name}.docmend-tmp) the next attempt's O_EXCL open failed forever.
    Randomized names make residue inert (rev 0.26 / adr-0021 staging rule)."""
    target = tmp_path / "a.md"
    (tmp_path / ".a.md.deadbeef.docmend-tmp").write_bytes(b"stale residue")
    (tmp_path / ".a.md.docmend-tmp").write_bytes(b"legacy stale residue")
    atomic.atomic_write_bytes(target, b"fresh\n")
    assert target.read_bytes() == b"fresh\n"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/unit/writer/test_atomic.py::test_stale_staging_residue__does_not_block_retry -v` Expected: FAIL — `WriteError: ... cannot stage write (File exists)` (the legacy fixed name collides).

- [ ] **Step 3: Randomize the staging name**

In `src/docmend/writer/atomic.py`, add `import secrets` to the imports, then change the first line of `_write_temp`:

```python
def _write_temp(target: Path, data: bytes, mode: int | None) -> Path:
    # Randomized per attempt (rev 0.26): a fixed staging name meant a hard
    # kill's residue blocked every later attempt at the same target with a
    # spurious O_EXCL failure, and made the staging path predictable to an
    # interfering process. Residue from a killed attempt is inert.
    tmp = target.with_name(f".{target.name}.{secrets.token_hex(4)}.docmend-tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
```

(The rest of `_write_temp` is unchanged.) Then update the stale comment inside `atomic_write_bytes`'s `if not clobber:` block — replace the sentence "a later write attempt will surface it as an O_EXCL collision on the temp-file stage." with:

```python
        # The link above already succeeded, so target now holds the new bytes
        # — the publish happened. The stray staging name is just a second name
        # for that same inode (lossless residue); staging names are randomized
        # per attempt, so residue never blocks a retry. Reporting WriteError
        # here would tell the caller the mutation failed when it didn't —
        # worse than the residue, so we swallow this one deliberately.
```

- [ ] **Step 4: Run the writer unit tests**

Run: `uv run pytest tests/unit/writer/test_atomic.py -v` Expected: PASS (including the pre-existing crash-during-replace test).

- [ ] **Step 5: Commit**

```bash
git add src/docmend/writer/atomic.py tests/unit/writer/test_atomic.py
git commit -m "fix(atomic): randomize staging names so kill residue never blocks retry"
```

---

### Task 4: Randomized exclusive staging for JSON artifacts

**Files:**

- Modify: `src/docmend/artifacts.py:93-102` (`write_json_artifact`)
- Test: `tests/test_inventory_artifact.py` (append one test)

**Interfaces:**

- Consumes: nothing new.
- Produces: unchanged `write_json_artifact(document, path)` signature; staging becomes `mkstemp`-random in the destination directory (closing DMR-02's predictable-truncation vector: the old `<name>.tmp` sibling was truncated on every write, so pointing `--report` near a victim file destroyed it even when the final `os.replace` was refused later).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_inventory_artifact.py` (reuse the module's existing fixture helpers for building a valid inventory; if it has a helper like `_inventory(...)`, use it — the assertion only needs any successful write):

```python
def test_artifact_staging__randomized_and_retry_safe(tmp_path: Path, monkeypatch) -> None:
    """DMR-02: the old fixed '<name>.tmp' sibling was a predictable truncation
    target and blocked nothing on collision. Staging must be O_EXCL-random:
    pre-existing residue at the legacy name must be left untouched and must
    not block the write."""
    import json

    from docmend import artifacts

    dest = tmp_path / "out.json"
    legacy_residue = tmp_path / "out.json.tmp"
    legacy_residue.write_bytes(b"victim bytes that must survive")
    artifacts.write_json_artifact({"k": "v"}, dest)
    assert json.loads(dest.read_text()) == {"k": "v"}
    assert legacy_residue.read_bytes() == b"victim bytes that must survive"
    leftovers = [p for p in tmp_path.iterdir() if p not in (dest, legacy_residue)]
    assert leftovers == []  # staging temp cleaned up after publish
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_inventory_artifact.py::test_artifact_staging__randomized_and_retry_safe -v` Expected: FAIL — `legacy_residue.read_bytes()` assertion fails (the current code truncates `out.json.tmp`).

- [ ] **Step 3: Rewrite `write_json_artifact`**

In `src/docmend/artifacts.py`, add `import tempfile` to the imports and replace the function:

```python
def write_json_artifact(document: dict[str, object], path: Path) -> None:
    """Atomically write one JSON-document artifact (random O_EXCL temp + fsync +
    os.replace). Staging is randomized per attempt (rev 0.26, adr-0021): the
    old fixed '<name>.tmp' sibling was a predictable truncation target and a
    permanent retry blocker after a hard kill."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        # mkstemp creates 0o600; artifacts are shared run records, so restore
        # the ordinary umask-derived mode a plain open() would have given.
        umask = os.umask(0)
        os.umask(umask)
        os.fchmod(fd, 0o666 & ~umask)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(document, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
```

- [ ] **Step 4: Run the artifact test files**

Run: `uv run pytest tests/test_inventory_artifact.py tests/test_plan_artifact.py tests/test_report_artifact.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/artifacts.py tests/test_inventory_artifact.py
git commit -m "fix(artifacts): randomized O_EXCL staging for JSON artifacts (DMR-02)"
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

Append inside `class TestCollisions` in `tests/test_planning.py` (match the class's existing helper style for building an inventory — it scans a `tmp_path` corpus via `discovery.scan`; reuse the same helper the neighboring `test_case_variant_sources__*` tests use for config-with-overwrite):

```python
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

If `TestCollisions` has no shared `_plan_with_overwrite` helper, add one following the pattern its existing tests use to build config + inventory + call `planning.build_plan`; the two tests above are its only callers:

```python
    def _plan_with_overwrite(self, tmp_path: Path):
        from datetime import UTC, datetime

        from docmend import discovery, planning
        from docmend.config import DocmendConfig
        from docmend.plan import ArtifactRef

        config = DocmendConfig()
        config = config.model_copy(
            update={"rename": config.rename.model_copy(update={"on_collision": "overwrite"})}
        )
        now = datetime.now(UTC).isoformat()
        run_id = "run_20260710T000000Z_0ledgr"
        inventory = discovery.scan(tmp_path, config, run_id=run_id, generated_at=now)
        return planning.build_plan(
            inventory,
            config,
            run_id=run_id,
            generated_at=now,
            inventory_ref=ArtifactRef(path="unused", run_id=run_id, sha256="sha256:" + "0" * 64),
        )
```

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

- Modify: `src/docmend/artifacts.py` (new function after `validate_artifact`)
- Test: Create `tests/test_artifact_guard.py`

**Interfaces:**

- Consumes: nothing new.
- Produces: `guard_artifact_destination(destination: Path, *, corpus_root: Path | None, input_artifacts: Iterable[Path] = (), allowed_root: Path | None = None) -> str | None` — returns a refusal message, or `None` when the destination is safe. Tasks 7–9 call it from the CLI; `allowed_root` is the resolved `.docmend/` carve-out root or `None` when the operator removed its exclusion.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_artifact_guard.py`:

```python
"""Artifact destination guard (rev 0.26 IR-007, adr-0021, DMR-02).

Pure-function tests; the CLI wiring (refusal exit 3 before the pipeline runs)
is covered in the per-command CLI test files.
"""

from pathlib import Path

from docmend.artifacts import guard_artifact_destination


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


def test_symlink_into_corpus__refused(tmp_path: Path) -> None:
    """Resolution happens through symlinks: an out-of-corpus name aliasing an
    in-corpus file is the same clobber."""
    root = _corpus(tmp_path)
    link = tmp_path / "innocent.json"
    link.symlink_to(root / "victim.txt")
    refusal = guard_artifact_destination(link, corpus_root=root)
    assert refusal is not None


def test_carveout_allows_docmend_root_inside_corpus(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    allowed = root / ".docmend"
    dest = allowed / "docmend-run-inventory.json"
    assert (
        guard_artifact_destination(dest, corpus_root=root, allowed_root=allowed) is None
    )


def test_carveout_withdrawn__docmend_root_refused(tmp_path: Path) -> None:
    """allowed_root=None models the operator having removed the .docmend/
    exclusion: the canonical root loses its license (adr-0021)."""
    root = _corpus(tmp_path)
    dest = root / ".docmend" / "docmend-run-inventory.json"
    refusal = guard_artifact_destination(dest, corpus_root=root, allowed_root=None)
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

Run: `uv run pytest tests/test_artifact_guard.py -v` Expected: FAIL — `ImportError: cannot import name 'guard_artifact_destination'`.

- [ ] **Step 3: Implement the guard**

In `src/docmend/artifacts.py`, extend the `collections.abc` import to include `Iterable` and add after `validate_artifact`:

```python
def guard_artifact_destination(
    destination: Path,
    *,
    corpus_root: Path | None,
    input_artifacts: Iterable[Path] = (),
    allowed_root: Path | None = None,
) -> str | None:
    """One source-aware preflight for every CLI artifact write (rev 0.26
    IR-007, adr-0021, DMR-02): docmend's own artifacts must never be able to
    destroy the corpus they describe, and a refused write must precede the
    pipeline, not follow it. Returns the refusal message, or None when safe.

    `allowed_root` is the canonical tool artifact root (.docmend/) resolved by
    the CLI — passed only while the effective exclude patterns still cover it,
    so its contents can never become scan candidates; None means the operator
    removed that exclusion and the carve-out is withdrawn.
    """
    resolved = destination.resolve()
    if resolved.exists() and not resolved.is_file():
        return f"{destination}: artifact destination is not a regular file"
    for artifact in input_artifacts:
        if resolved == Path(artifact).resolve():
            return (
                f"{destination}: artifact destination aliases an input artifact "
                f"of this invocation ({artifact})"
            )
    if corpus_root is not None:
        root = corpus_root.resolve()
        if resolved.is_relative_to(root):
            if allowed_root is not None and resolved.is_relative_to(allowed_root.resolve()):
                return None
            return (
                f"{destination}: artifact destination resolves inside the corpus "
                f"root {root} (only the excluded canonical artifact root is a "
                f"legal in-corpus destination; adr-0021)"
            )
    return None
```

- [ ] **Step 4: Run the guard tests**

Run: `uv run pytest tests/test_artifact_guard.py -v` Expected: PASS (all 8).

- [ ] **Step 5: Commit**

```bash
git add src/docmend/artifacts.py tests/test_artifact_guard.py
git commit -m "feat(artifacts): source-aware destination guard with .docmend carve-out (DMR-02)"
```

---

### Task 7: Guard wiring — `scan`

**Files:**

- Modify: `src/docmend/cli.py` (new `_guard_artifact_paths` helper + `scan` body at `cli.py:173-203`)
- Test: `tests/test_cli_scan.py` (append three tests)

**Interfaces:**

- Consumes: Task 6's `guard_artifact_destination`.
- Produces: `_guard_artifact_paths(destinations: list[Path], *, corpus_root: Path | None, input_artifacts: list[Path], config: DocmendConfig) -> None` in `cli.py` — computes the carve-out from the effective excludes, echoes `refused [artifact-destination]: …` and raises `typer.Exit(3)` on refusal. Tasks 8–9 reuse it.

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/test_cli_scan.py` (match the module's existing `CliRunner` fixture/helper names — it invokes `app` with `runner.invoke(app, [...])` and typically `chdir`s into `tmp_path` via a fixture or `runner.isolated_filesystem`; follow its established pattern):

```python
def test_scan_report_inside_corpus__refused_exit_3_source_intact(tmp_path, runner) -> None:
    """DMR-02 reproduction: `scan --report <corpus file>` used to replace the
    source with inventory JSON and exit 0. Now: exit 3, nothing written, and
    the refusal precedes the walk."""
    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"corpus document\n")
    result = runner.invoke(app, ["scan", str(tmp_path), "--report", str(victim)])
    assert result.exit_code == 3
    assert "artifact-destination" in result.output
    assert victim.read_bytes() == b"corpus document\n"


def test_scan_default_docmend_root__still_works(tmp_path, runner, monkeypatch) -> None:
    """OQ-034/NFR-006: the zero-setup default (`scan .` writing under
    ./.docmend/) is binding behavior — the guard's carve-out must keep it."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "doc.txt").write_bytes(b"clean\n")
    result = runner.invoke(app, ["scan", "."])
    assert result.exit_code == 0
    assert list((tmp_path / ".docmend").glob("docmend-*-inventory.json"))


def test_scan_docmend_exclusion_removed__default_refused(tmp_path, runner, monkeypatch) -> None:
    """The carve-out is licensed by the exclusion (adr-0021): --exclude REPLACES
    the exclude set (OQ-029), so an exclude list without .docmend/ withdraws
    the license and the default in-corpus destination is refused."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "doc.txt").write_bytes(b"clean\n")
    result = runner.invoke(app, ["scan", ".", "--exclude", "*.bin"])
    assert result.exit_code == 3
    assert "artifact-destination" in result.output
    assert not (tmp_path / ".docmend").exists() or not list(
        (tmp_path / ".docmend").glob("docmend-*-inventory.json")
    )
```

Adjust the two-argument `(tmp_path, runner)` signatures to the module's actual fixture names before running.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_cli_scan.py -k "refused or docmend_root or exclusion_removed" -v` Expected: the first and third FAIL (exit 0/1 instead of 3; victim replaced); the second may already pass — keep it as the carve-out regression.

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
    .docmend/ carve-out is licensed by the effective exclude patterns — if the
    operator removed that exclusion, the canonical root is scannable corpus
    space and loses its license."""
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude)
    artifact_dir_excluded = exclude.match_file(f"{ARTIFACT_DIR_NAME}/probe")
    allowed = Path(ARTIFACT_DIR_NAME).resolve() if artifact_dir_excluded else None
    for destination in destinations:
        refusal = artifacts.guard_artifact_destination(
            destination,
            corpus_root=corpus_root,
            input_artifacts=input_artifacts,
            allowed_root=allowed,
        )
        if refusal is not None:
            typer.echo(f"refused [artifact-destination]: {refusal}", err=True)
            raise typer.Exit(3)
```

In `scan`, compute the output path before the walk and guard it — replace the current post-scan `out_path` line (`cli.py:190`) by inserting after `log.info("scan starting", ...)`:

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

Append to `tests/test_cli_plan.py` (match its fixture/runner conventions):

```python
def test_plan_out_inside_corpus__refused_exit_3(tmp_path, runner) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"corpus document\n")
    result = runner.invoke(app, ["plan", str(tmp_path), "--out", str(victim)])
    assert result.exit_code == 3
    assert "artifact-destination" in result.output
    assert victim.read_bytes() == b"corpus document\n"


def test_plan_out_aliasing_inventory_input__refused_exit_3(tmp_path, runner, monkeypatch) -> None:
    """A destination outside the corpus can still corrupt the pipeline by
    aliasing this invocation's own input (adr-0021)."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"clean\n")
    scan_result = runner.invoke(
        app, ["scan", str(corpus), "--report", str(tmp_path / "inventory.json")]
    )
    assert scan_result.exit_code == 0
    result = runner.invoke(
        app,
        [
            "plan",
            "--inventory",
            str(tmp_path / "inventory.json"),
            "--out",
            str(tmp_path / "inventory.json"),
        ],
    )
    assert result.exit_code == 3
    assert "artifact-destination" in result.output
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_cli_plan.py -k "refused" -v` Expected: FAIL — current exit codes are 0/1 and the files are replaced.

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
- Test: `tests/test_cli_apply.py` (append two tests)

**Interfaces:**

- Consumes: Task 7's `_guard_artifact_paths`.
- Produces: nothing new. Behavior: report/manifest destinations are guarded before the lock and gate; `artifacts.write_report` moves **inside** the lock (`try:` block), so a run's artifacts finalize under the same coordination as its mutations (rev 0.26; the refusal-report write at `cli.py:550` is already in-lock and becomes safe because its path was guarded first).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_apply.py` (match its fixture conventions; the module already has helpers that scan+plan a corpus and return a plan path — reuse them):

```python
def test_apply_report_inside_corpus__refused_exit_3_before_gate(tmp_path, runner) -> None:
    """DMR-02: `apply --report <corpus file>` clobbered the file even on a
    dry run and even when the write was later refused. The guard must refuse
    at exit 3 BEFORE gate evaluation and before any pipeline output."""
    corpus, plan_path = _scan_and_plan(tmp_path, runner)  # module helper; adapt name
    victim = corpus / "victim.txt"
    victim.write_bytes(b"corpus document\n")
    result = runner.invoke(app, ["apply", str(plan_path), "--report", str(victim)])
    assert result.exit_code == 3
    assert "artifact-destination" in result.output
    assert victim.read_bytes() == b"corpus document\n"


def test_apply_write__report_published_inside_run_lock(tmp_path, runner, monkeypatch) -> None:
    """rev 0.26: report finalization happens while the run lock is held, so a
    refused or interrupted run cannot leave mutations published but the
    report's fate decided outside coordination."""
    import docmend.cli as cli_module
    from docmend import lock as lock_module

    events: list[str] = []
    real_release = lock_module.RunLock.release
    real_write_report = cli_module.artifacts.write_report

    def spy_release(self):  # noqa: ANN001
        events.append("lock-released")
        return real_release(self)

    def spy_write_report(report, path):  # noqa: ANN001
        events.append("report-written")
        return real_write_report(report, path)

    monkeypatch.setattr(lock_module.RunLock, "release", spy_release)
    monkeypatch.setattr(cli_module.artifacts, "write_report", spy_write_report)

    corpus, plan_path = _scan_and_plan_with_dirty_file(tmp_path, runner)  # module helper; adapt
    result = runner.invoke(
        app, ["apply", str(plan_path), "--write", "--backup-dir", str(tmp_path / "bk")]
    )
    assert result.exit_code == 0, result.output
    assert events.index("report-written") < events.index("lock-released")
```

Adapt the two `_scan_and_plan*` helper names to whatever the module actually provides (search for existing tests that invoke `apply` end-to-end and reuse their setup verbatim); if no helper exists, inline the same scan→plan CLI invocations those tests use.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_cli_apply.py -k "refused_exit_3_before_gate or inside_run_lock" -v` Expected: FAIL — the guard test sees the victim replaced with report JSON; the ordering test sees `lock-released` before `report-written`.

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

Run: `uv run scripts/check.py` Expected: every stage passes — ruff format, ruff check, basedpyright, pytest (all tests incl. the ~15 new ones), coverage ≥ 97%, pip-audit clean. Fix anything it flags before proceeding (a coverage dip means a new branch lacks a test — add the test, don't lower the bar).

- [ ] **Step 2: Add the CHANGELOG entry**

Insert directly under the intro paragraph of `CHANGELOG.md`:

```markdown
## [Unreleased]

Safety-core remediation, plan A of four (spec rev 0.26; 2026-07-10 comprehensive review findings DMR-01/DMR-02; ADRs 0019–0021). Targets the eventual v2.0.0.

### Fixed

- One plan can no longer overwrite its own recovery backups (DMR-01): planning reserves every action's effective output path — in-place and rename alike — so colliding actions skip at plan time, and backups are stored under write-once keys namespaced by run, action, and role, so even a crafted plan cannot make two byte streams share a key.
- docmend's own artifacts can no longer destroy corpus inputs (DMR-02): every `scan --report`, `plan --out`, and `apply --report` destination passes a source-aware guard before the pipeline runs — in-corpus destinations are refused (exit 3) except the still-excluded canonical `.docmend/` root, and destinations aliasing an invocation's input artifacts are refused outright.
- Staging names are randomized (`O_EXCL`) for both corpus writes and JSON artifacts: kill residue no longer blocks retries, and the predictable `<name>.tmp` truncation target is gone.
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

## Self-Review Notes (completed at authoring)

- **Spec coverage (Plan A scope):** FR-006 backup keys + ledger → Tasks 1/2/5; FR-011's plan-half is untouched (its action-time invariant is Plan C); IR-007 guard + staging → Tasks 3/4/6/7/8/9; DR-003/DR-004 field changes are Plans B; §18.5 exit-3 classification → Tasks 7–9. The scan/plan `timeout`-skip exit-1 medium is Plan D scope (verify/exit sweep), deliberately not here.
- **Type consistency:** `BackupRole` defined Task 1, consumed Task 2; `guard_artifact_destination` signature defined Task 6, consumed via `_guard_artifact_paths` (Task 7) by Tasks 8–9; `_action_seq` defined and consumed within Task 2.
- **Known adaptation points (deliberate, not placeholders):** fixture/helper names in `tests/test_cli_*.py` (`runner`, `_scan_and_plan*`) must be matched to the modules' existing conventions — the tests' assertions are complete as written.
