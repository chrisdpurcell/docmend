# Codex plan audit — MS-3 apply/writer (2026-07-06-233748)

## Executive summary

Claude Code’s revisions resolve most round-1 findings, especially dry-run backup writes, gate-refusal side effects, stale-lock unlink races, absolute manifest backup paths, and disk-space estimation. Significant findings remain: restore now verifies corrupted overwrite backups before mutation, but its mutation phase can still leave a partially changed corpus on an environmental write/unlink failure; additionally, the overwrite rename path bypasses the planned atomic/fsync writer primitive.

New internet research was required for the revised `flock(2)` assumption. Official Python docs support the approach on the repo’s Linux/POSIX target, with a portability caveat around non-blocking failure errno handling.

## Verdict

Needs major correction before execution

## Audit loop status

- Audit type: Follow-up audit
- Plan path: /home/chris/projects/docmend/docs/superpowers/plans/2026-07-06-ms3-apply-writer.md
- Prior audit issue count: 6
- Resolved issue count: 5
- Still open issue count: 0
- Partially resolved issue count: 1
- New issue count: 2
- Regression count: 0
- Significant findings remaining: Yes

## Adversarial review performed

I re-read the revised plan, diffed it against the committed plan, and retested the prior findings against the current plan text and repository evidence. I focused on dry-run write boundaries, gate refusal side effects, restore preflight ordering, run-lock race semantics, manifest path stand-alone behavior, and disk preflight false positives.

I also attacked new assumptions introduced by the fixes: `flock` behavior, overwrite mutation durability, restore failure atomicity after successful preflight, relative backup path semantics from config snapshots, and whether validation tests prove the intended safety properties. I did not run pytest or project gates because this audit is read-only and those commands may write caches/artifacts.

## Prior findings status

### CR-001: Dry-run overwrite collisions can still write backups

- Previous severity: High
- Current status: Resolved
- Evidence: The revised `_execute_action` returns `would_apply` before any backup code when `options.write` is false, and the plan adds `test_apply_dry_run_overwrite_with_configured_backup_dir__no_backup_written` plus an engine-level dry-run overwrite test. See plan lines 2261-2277, 2436-2438, and 2018.
- Remaining action for Claude Code: Keep the dry-run tests scoped to both CLI/config and engine-level `backup_root` cases.

### CR-002: The safety gate can create directories inside the target before refusing them

- Previous severity: High
- Current status: Resolved
- Evidence: `_backup_destination` now resolves `backup_root`, checks `is_relative_to(source_root.resolve())`, and returns `backup-outside-target` before `_dir_writable` can mkdir/probe. The test explicitly snapshots the source tree and asserts the inside-target backup directory is not created. See plan lines 1610 and 1793-1808.
- Remaining action for Claude Code: Keep the no-side-effect assertion in the gate tests.

### CR-003: Restore can partially mutate before validating overwritten-target backup integrity

- Previous severity: Critical
- Current status: Partially resolved
- Evidence: The revised restore preflight now checks live `after_sha256`, source backup hash, overwritten backup readability/hash, and original-path collision before write/unlink, resolving the specific corrupted-overwritten-backup case. See plan lines 2788-2824 and tests at 2660-2662. However, after preflight succeeds, `rename_and_rewrite` restore writes the original, unlinks the target, and only then writes the clobbered target; if `target.unlink()` succeeds but `atomic_write_bytes(target, clobbered, clobber=False)` fails, the function returns `failed` after changing the live corpus. See lines 2828-2843.
- Remaining action for Claude Code: Redesign overwrite restore mutation sequencing or add rollback/staging so ERR-003 during the mutation phase cannot leave the corpus partially restored. Add a test that forces failure after `target.unlink()` and asserts live files remain byte-for-byte unchanged or the operation rolls back deterministically.

### CR-004: Stale-lock stealing can unlink a newly acquired live lock

- Previous severity: High
- Current status: Resolved
- Evidence: The plan replaced O_EXCL/unlink stale stealing with `fcntl.flock`, keeps the holder file as metadata debris, and releases by closing the descriptor rather than unlinking. See plan lines 31, 495-502, 524-530, and 547-578.
- Remaining action for Claude Code: Handle non-blocking lock failures by errno (`EACCES`/`EAGAIN`) or verify Linux-only behavior in tests; this is not a blocker for the documented Linux target.

### CR-005: Manifest backup paths are not guaranteed absolute

- Previous severity: High
- Current status: Resolved
- Evidence: The revised plan resolves `backup_root` at CLI/options normalization, `backup_file` returns `dest.resolve()`, `_record` serializes that path, and the drill includes relative `--backup-dir` plus restore from a different cwd. See plan lines 36, 1452-1453, 1558-1560, 2538-2546, and 3067-3083.
- Remaining action for Claude Code: Also address CR-NEW-002 for config-snapshot relative `write.backup_dir` semantics.

### CR-006: Disk preflight underestimates write and backup space in overwrite/growing-output cases

- Previous severity: Medium
- Current status: Resolved
- Evidence: The revised gate adds live overwrite target sizes to backup-space needs and bounds source temp headroom by transformed output growth. It also adds a specific preflight test for overwrite targets and output growth. See plan lines 1613-1615 and 1816-1869.
- Remaining action for Claude Code: Keep the monkeypatched disk tests independent of gate internals.

## New blocking issues

### CR-NEW-001: Overwrite rename bypasses the atomic/fsync writer primitive

- Severity: High
- Status: Confirmed
- Adversarial angle: Does every mutation path actually satisfy D-004/NFR-002?
- Plan reference: Task 9 `_execute_action`, lines 2324-2327.
- Finding: For pure rename under `overwrite`, the apply sketch directly calls `os.replace(source, target)` instead of going through a writer primitive that fsyncs the parent directory and wraps environmental failures. This contradicts the plan’s own isolated-writer/atomicity contract and leaves overwrite-renames with weaker crash-durability than no-clobber renames and content writes.
- Repository evidence: NFR-002 requires atomic writes with temp/fsync/replace semantics and no partial-written state, `docs/specs/docmend.md` lines 342-343. D-004 requires fsync and parent-dir fsync where practical for all writes, lines 446 and 391. The plan’s atomic module provides `fsync_dir` and `rename_no_clobber`, but no overwrite-rename primitive, lines 1317-1391.
- External research evidence: Not applicable.
- Why it matters: FR-011 overwrite is the riskiest collision policy. If this path skips the same durability barrier as the rest of the writer, validation can pass while crash/interruption behavior is weaker than the spec promises.
- Recommended action for Claude Code: Add a dedicated `rename_overwrite(source, target)` writer primitive that uses `os.replace`, wraps `OSError` as `WriteError`, and fsyncs the parent directory. Route overwrite rename through it instead of inline `os.replace`.
- Suggested validation: Add a test for overwrite rename that monkeypatches the primitive’s `fsync_dir`/`os.replace` failure paths and asserts errors are classified ERR-003, source/target state is as documented, and the parent fsync path is exercised.

## New non-blocking issues

### CR-NEW-002: Relative `write.backup_dir` from the plan snapshot is still apply-cwd dependent

- Severity: Medium
- Status: Confirmed
- Adversarial angle: Is backup location semantics stable when apply runs from a different cwd than plan?
- Plan reference: Design decisions 1 and 7, lines 30 and 36; Task 10 options normalization, lines 2538-2546.
- Finding: The plan fixes relative CLI `--backup-dir`, but a relative `write.backup_dir` captured in `plan.config` is revalidated at apply and resolved relative to the apply process cwd. That means the reviewed plan snapshot does not fully determine where tool backups go unless the config path was absolute or the operator passes `--backup-dir`.
- Repository evidence: `WriteConfig.backup_dir` is a `Path | None` with no base normalization, `src/docmend/config.py` lines 122-127. The existing `Plan.config` is an unnormalized snapshot dict, `src/docmend/plan.py` lines 103-104. The revised validation only covers relative CLI backup dir, plan lines 3067-3083.
- External research evidence: Not applicable.
- Why it matters: A plan produced in one cwd and applied in another can place backups somewhere different from what was reviewed, or gate-refuse because the relative path now resolves inside the source root. Restore would still get absolute manifest paths after apply, but the apply-time preservation strategy remains cwd-sensitive.
- Recommended action for Claude Code: Define and implement one base rule for relative config backup paths. Prefer resolving `write.backup_dir` during plan creation into the plan snapshot, or storing enough config-origin metadata to resolve it deterministically at apply.
- Suggested validation: Add a test where plan creation uses relative `write.backup_dir`, apply runs from a different cwd without `--backup-dir`, and the backup destination is asserted to match the reviewed/resolved plan semantics.

## Regressions

None found.

## Internet research performed

- Source name: Python 3.14 `fcntl` module documentation
- URL: <https://docs.python.org/3/library/fcntl.html>
- Access date: 2026-07-07
- What it was used to verify: Current `fcntl.flock` availability and non-blocking lock failure behavior.
- Relevant conclusion: `flock` is available on Unix and supports `LOCK_EX | LOCK_NB`; failure raises `OSError`, with non-blocking lock contention using `EACCES` or `EAGAIN` depending on OS. The plan’s Linux/POSIX target makes `flock` plausible, but robust code should not rely only on `BlockingIOError` if portability matters.

- Source name: Python 3.14 `pathlib` documentation
- URL: <https://docs.python.org/3/library/pathlib.html>
- Access date: 2026-07-07
- What it was used to verify: Current path API assumptions around resolved paths and relative path checks.
- Relevant conclusion: The plan’s use of modern `pathlib` containment APIs is compatible with the Python 3.14 target.

## Read-only validation performed

- `git status --short && git branch --show-current && git log --oneline -n 10`: confirmed branch `dev`, the plan file is modified, and `docs/codex-reviews/` is untracked.
- `nl -ba` / `sed -n` on the plan: re-read current round-2 plan text and captured line references for changed lock, gate, apply, restore, and validation sections.
- `rg --files`: confirmed current repo inventory and that apply/restore/writer modules are still proposed, not implemented.
- `git diff -- docs/superpowers/plans/2026-07-06-ms3-apply-writer.md`: confirmed the round-2 edits specifically target the prior findings.
- Inspected `src/docmend/config.py`, `src/docmend/plan.py`, `src/docmend/inventory.py`, `src/docmend/artifacts.py`, `src/docmend/cli.py`, and schemas: checked current config/model/schema realities.
- Inspected `docs/specs/docmend.md`, ADR-0003/0004/0006/0007, `docs/open-questions.md`, and `docs/resolved-questions.md`: checked binding writer, lock, restore, and OQ/RQ constraints.
- Used official Python docs for `fcntl` and `pathlib`: verified revised external API assumptions.

## Recommended implementation validation

- Run only after implementation: targeted tests for CR-003 mutation-phase restore failure atomicity.
- Run only after implementation: targeted tests for CR-NEW-001 overwrite rename via the atomic writer primitive.
- Run only after implementation: targeted tests for CR-NEW-002 relative `write.backup_dir` from config snapshot across cwd changes.
- Run only after implementation: `uv run pytest tests/test_cli_apply.py tests/test_apply.py tests/test_gate.py tests/test_restore.py tests/test_restore_drill.py -q`
- Run only after implementation: `uv run ruff format --check . && uv run ruff check . && uv run basedpyright`
- Run only after implementation: `uv run coverage run -m pytest && uv run coverage report`
- Run only after docs closeout: `uv run python scripts/check_traceability.py`

## Final recommendation

Claude Code should revise the plan using the findings above

## Review ledger for next loop

- Plan path: /home/chris/projects/docmend/docs/superpowers/plans/2026-07-06-ms3-apply-writer.md
- Audit round: 2
- Open issue IDs: CR-003, CR-NEW-001, CR-NEW-002
- Resolved issue IDs: CR-001, CR-002, CR-004, CR-005, CR-006
- Superseded issue IDs:
- Significant findings remaining: Yes
- Next audit should focus on: restore mutation-phase failure atomicity, overwrite-rename routing through a fsyncing writer primitive, and deterministic relative `write.backup_dir` semantics from plan snapshots
