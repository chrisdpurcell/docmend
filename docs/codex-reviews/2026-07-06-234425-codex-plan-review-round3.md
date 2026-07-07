# Codex plan audit — MS-3 apply/writer (2026-07-06-234425)

## Executive summary

Claude Code’s latest revisions resolve the overwrite-rename writer bypass and the relative `write.backup_dir` snapshot issue. The restore mutation-phase fix is safer than round 2 because it preserves payloads instead of deleting one before attempting the next step, but it still intentionally leaves a half-restored corpus on some ERR-003 paths.

Significant findings remain. A new blocking restore defect appears for overwrite-renames executed with declared external preservation rather than tool backups: `restore` can report success while failing to reinstate the clobbered target file.

No new internet research was required in this pass; the remaining findings are falsified by repository/spec evidence and the revised plan text, not by stale external API behavior.

## Verdict

Needs major correction before execution

## Audit loop status

- Audit type: Follow-up audit
- Plan path: /home/chris/projects/docmend/docs/superpowers/plans/2026-07-06-ms3-apply-writer.md
- Prior audit issue count: 8
- Resolved issue count: 7
- Still open issue count: 0
- Partially resolved issue count: 1
- New issue count: 2
- Regression count: 0
- Significant findings remaining: Yes

## Adversarial review performed

I re-read the current plan, compared it against the prior audit ledger, inspected the changed restore/apply/writer/gate sections, and checked the relevant live repository contracts in `docs/specs/docmend.md`, ADR-0003/0004/0006, `src/docmend/config.py`, `src/docmend/plan.py`, and current planning code.

I retested the prior open assumptions around restore mutation failure atomicity, overwrite rename routing through writer primitives, and deterministic relative config backup paths. I also attacked new failure modes introduced or exposed by the corrections: restore behavior for overwrite records without tool backup paths, partial apply failure after publishing a rename-and-rewrite target, and validation false positives where the proposed tests exercise tool-backup paths but not external-preservation paths.

I did not run pytest or project gates because this audit is read-only and those commands may create caches/artifacts.

## Prior findings status

### CR-001: Dry-run overwrite collisions can still write backups

- Previous severity: High
- Current status: Resolved
- Evidence: `_execute_action` now returns `would_apply` before any `backup_file` call when `options.write` is false, and both engine/CLI dry-run overwrite tests are listed. See plan lines 2338-2355, 2090, and 2512.
- Remaining action for Claude Code: Keep both dry-run overwrite tests.

### CR-002: The safety gate can create directories inside the target before refusing them

- Previous severity: High
- Current status: Resolved
- Evidence: `_backup_destination` checks `resolved.is_relative_to(source_root.resolve())` before `_dir_writable`, and the no-side-effect test remains required. See plan lines 1848-1864 and 1665.
- Remaining action for Claude Code: Keep the recursive source-tree unchanged assertion.

### CR-003: Restore can partially mutate before validating overwritten-target backup integrity

- Previous severity: Critical
- Current status: Partially resolved
- Evidence: The corrupted-input half is resolved: restore now verifies live `after_sha256`, source backup, overwritten backup, and original-path collision before mutation. See plan lines 2865-2905. The mutation phase no longer deletes the target before restoring the clobbered target; it restores the original first and leaves a superset on failure. See lines 2907-2938 and the new failure test at 2738. That removes the prior file-loss case but still accepts a half-restored corpus after ERR-003 rather than rolling back or completing recovery.
- Remaining action for Claude Code: Decide whether the “superset, then collision on retry” state is an explicit supported recovery mode. If yes, document the operator recovery path and assert it in tests. If no, add rollback/staging so ERR-003 leaves the corpus byte-for-byte unchanged.

### CR-004: Stale-lock stealing can unlink a newly acquired live lock

- Previous severity: High
- Current status: Resolved
- Evidence: The plan uses `fcntl.flock`, closes the descriptor on release, leaves the lock file as metadata debris, and handles `EAGAIN`/`EWOULDBLOCK`/`EACCES`. See plan lines 31, 495-502, 526-530, and 552-578.
- Remaining action for Claude Code: Keep the cross-process lock tests.

### CR-005: Manifest backup paths are not guaranteed absolute

- Previous severity: High
- Current status: Resolved
- Evidence: Apply resolves `backup_root` once before building `ApplyOptions`, `backup_file` returns absolute paths, and the restore drill covers relative CLI `--backup-dir` from another cwd. See plan lines 36, 1614, 2613-2620, and 3162-3177.
- Remaining action for Claude Code: None beyond implementing the listed tests.

### CR-006: Disk preflight underestimates write and backup space in overwrite/growing-output cases

- Previous severity: Medium
- Current status: Resolved
- Evidence: The gate includes live overwrite target sizes and transformed-output growth bounds, with a dedicated test. See plan lines 1668-1669, 1871-1880, and 1904-1924.
- Remaining action for Claude Code: Keep the disk-space oracle independent of gate internals.

### CR-NEW-001: Overwrite rename bypasses the atomic/fsync writer primitive

- Previous severity: High
- Current status: Resolved
- Evidence: The plan adds `rename_overwrite(source, target)` with `os.replace`, `WriteError` wrapping, and parent fsync, then routes overwrite rename through it. See plan lines 1184, 1275-1300, 1433-1446, and 2401-2403.
- Remaining action for Claude Code: Keep the overwrite-rename primitive tests.

### CR-NEW-002: Relative `write.backup_dir` from the plan snapshot is still apply-cwd dependent

- Previous severity: Medium
- Current status: Resolved
- Evidence: The plan now resolves relative `config.write.backup_dir` at plan creation before serializing `plan.config`, and adds a planning assertion for the absolute snapshot. See plan lines 1995-2009. Apply then resolves the already-snapshotted path once at options normalization, lines 2608-2620.
- Remaining action for Claude Code: Add the apply-from-different-cwd coverage if practical, but the plan-level correction addresses the core issue.

## New blocking issues

### CR-NEW-003: Restore falsely succeeds for overwrite-renames without tool backups

- Severity: High
- Status: Confirmed
- Adversarial angle: Does `docmend restore` behave safely when overwrite preservation is declared as `git`/`external` rather than implemented by tool-written backups?
- Plan reference: Design decision 1, line 30; gate test line 1670; apply overwrite backup recording lines 2356-2386; restore preflight/mutation lines 2791-2808 and 2886-2933.
- Finding: The gate permits overwrite collisions when `preserved_by="external"` is declared. In that case apply records `overwritten_sha256` but no `overwritten_backup_path`. For a pure overwrite rename, restore does not call `_verified_backup`, sees `clobbered is None`, runs `rename_no_clobber(target, original)`, and reports `restored`. That recreates the source path but does not reinstate the clobbered target, so the pre-apply corpus is not restored even though the outcome says success.
- Repository evidence: FR-005 allows declared external preservation but says manifest alone is not preservation for destructive content cases, `docs/specs/docmend.md` line 320. FR-006 requires restoring from manifest+backups to reproduce the original corpus when backups are enabled, line 321. IR-008 requires restore to return mutated files to pre-apply state, line 362. The plan itself says records with no backup path under external/no-backup preservation are skipped `no-backup`, line 39, but the restore code only applies that skip to `rewrite` and `rename_and_rewrite`, lines 2880-2885.
- External research evidence: Not applicable.
- Why it matters: This is a false-success recovery path. A user relying on external preservation may run `docmend restore`, receive a successful restore result, and still have the overwrite-clobbered target missing from the local corpus.
- Recommended action for Claude Code: Treat any overwrite record with `overwritten_sha256` but no `overwritten_backup_path` as `skipped: no-backup` unless the plan deliberately adds an operator-provided restore source for external preservation. For pure non-overwrite renames, manifest-only restore can still proceed.
- Suggested validation: Add a test for pure rename overwrite with `--preserved-by external` and no `--backup-dir`; restore should not report `restored`, should not mutate the corpus, and should return a `no-backup`/external-preservation skip.

## New non-blocking issues

### CR-NEW-004: Apply can record a failed rename-and-rewrite after publishing the target

- Severity: Medium
- Status: Confirmed
- Adversarial angle: Can apply validation pass while the manifest/report understate a partial mutation?
- Plan reference: Task 9 `_execute_action`, lines 2405-2415.
- Finding: For `rename_and_rewrite`, apply writes the new target with `atomic_write_bytes(target, payload, ...)` and then unlinks the source. If `source.unlink()` raises, the catch block records a failed outcome with `after=None`, but the target file has already been published. Restore ignores failed manifest records, and the report/manifest no longer accurately describe the live corpus.
- Repository evidence: DR-003 requires apply reports to include accurate per-file outcomes and counts, `docs/specs/docmend.md` line 374. DR-004 requires a reversible operation record per mutation, line 375. ADR-0006 says resume relies on completed manifest entries plus hashes and assumes atomic writes avoid partial states, `docs/adr/adr-0006-resume-and-recovery-model.md` lines 57-66.
- External research evidence: Not applicable.
- Why it matters: A rare environmental failure after target publish can leave a changed corpus with artifacts that say the action failed. That weakens resume/restore and can hide the need for manual cleanup.
- Recommended action for Claude Code: Either make this operation rollback the published target before returning failed, or record the partial/applied state explicitly enough for resume/restore to reconcile it. At minimum, the plan should state the supported failure state and add a test that forces `source.unlink()` to fail.
- Suggested validation: Add a targeted test monkeypatching `Path.unlink` after target publish for `rename_and_rewrite`; assert the corpus state, report status, and manifest record are mutually consistent and recoverable.

## Regressions

None found.

## Internet research performed

No new internet research was performed. The round-3 corrections did not introduce new external API/version assumptions beyond the Python `fcntl`/`pathlib` assumptions already researched in round 2; the remaining findings are local restore/apply logic issues verified against repository evidence.

## Read-only validation performed

- `git status --short && git branch --show-current && git log --oneline -n 10`: confirmed branch `dev`, modified plan file, and untracked `docs/codex-reviews/`.
- `rg --files`: confirmed current repository inventory and that apply/restore/writer modules are still proposed plan work, not completed implementation.
- `rg` over the plan for restore, overwrite, backup, fsync, lock, and relative backup terms: located the changed assumptions and validation claims.
- `nl -ba` / `sed -n` on the plan: inspected current design decisions, atomic writer, gate, apply, CLI, restore, and drill sections.
- `git diff -- docs/superpowers/plans/2026-07-06-ms3-apply-writer.md`: confirmed the current edits address the prior open issues and exposed the restore/apply sequencing changes.
- Inspected `docs/codex-reviews/2026-07-06-233748-codex-plan-review-round2.md`: verified prior issue IDs and expected follow-up focus.
- Inspected `src/docmend/config.py`, `src/docmend/plan.py`, and `src/docmend/planning.py`: checked current config snapshot and plan model behavior.
- Inspected `docs/specs/docmend.md` and ADR-0003/0004/0006: checked binding writer, preservation, restore, manifest, and recovery contracts.

## Recommended implementation validation

- Run only after implementation: targeted restore test for pure overwrite rename with `--preserved-by external` and no tool backup, asserting restore skips without mutation.
- Run only after implementation: targeted apply test forcing `source.unlink()` failure after `rename_and_rewrite` target publish, asserting report/manifest/corpus consistency.
- Run only after implementation: targeted tests for CR-003 mutation-phase restore failure state and operator recovery behavior.
- Run only after implementation: `uv run pytest tests/test_cli_apply.py tests/test_apply.py tests/test_gate.py tests/test_restore.py tests/test_restore_drill.py -q`
- Run only after implementation: `uv run ruff format --check . && uv run ruff check . && uv run basedpyright`
- Run only after implementation: `uv run coverage run -m pytest && uv run coverage report`
- Run only after docs closeout: `uv run python scripts/check_traceability.py`

## Final recommendation

Claude Code should revise the plan using the findings above

## Review ledger for next loop

- Plan path: /home/chris/projects/docmend/docs/superpowers/plans/2026-07-06-ms3-apply-writer.md
- Audit round: 3
- Open issue IDs: CR-003, CR-NEW-003, CR-NEW-004
- Resolved issue IDs: CR-001, CR-002, CR-004, CR-005, CR-006, CR-NEW-001, CR-NEW-002
- Superseded issue IDs:
- Significant findings remaining: Yes
- Next audit should focus on: restore behavior for overwrite records without tool backup paths, apply rename-and-rewrite late-failure artifact consistency, and whether the CR-003 half-restored superset state is an explicit supported recovery mode
