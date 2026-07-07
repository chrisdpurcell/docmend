# Codex plan audit — MS-3 apply/writer (2026-07-06-235057)

## Executive summary

Claude Code’s latest revisions substantively resolve the three remaining round-3 findings: the restore superset state is now an explicit supported recovery mode with tests, overwrite records without tool backups are skipped instead of falsely restored, and rename-and-rewrite late failure now attempts rollback and has targeted validation.

Significant findings still remain, but they are new and narrower than the prior blockers. New internet research was required for the filesystem durability assumption behind the writer/manifest plan; the Linux `fsync(2)` documentation confirms that file fsync alone does not necessarily persist the containing directory entry.

## Verdict

Needs minor correction before execution

## Audit loop status

- Audit type: Follow-up audit
- Plan path: /home/chris/projects/docmend/docs/superpowers/plans/2026-07-06-ms3-apply-writer.md
- Prior audit issue count: 10
- Resolved issue count: 10
- Still open issue count: 0
- Partially resolved issue count: 0
- New issue count: 2
- Regression count: 0
- Significant findings remaining: Yes

## Adversarial review performed

I re-read the revised plan and retested the round-3 open areas: restore mutation-phase failure handling, overwrite/external-preservation restore behavior, and rename-and-rewrite late apply failures. I inspected the current repository contracts in `docs/specs/docmend.md`, ADR-0003/0004/0006, `docs/research/atomic-write-filesystem-semantics.md`, `src/docmend/config.py`, `src/docmend/plan.py`, `src/docmend/planning.py`, and the current plan diff.

I also attacked new assumptions exposed by the corrections: whether “fsync’d manifest” and “parent fsync” actually prove crash durability, whether final corrupt manifest records can be silently ignored, and whether tests can pass while durability semantics remain weaker than the plan claims.

I did not run pytest or implementation commands because this is a read-only audit and those checks may create caches/artifacts.

## Prior findings status

### CR-001: Dry-run overwrite collisions can still write backups

- Previous severity: High
- Current status: Resolved
- Evidence: The plan still returns `would_apply` before any backup call in dry-run mode, and keeps dry-run overwrite tests. See plan lines 2347-2363 and 2098.
- Remaining action for Claude Code: None beyond implementing the listed tests.

### CR-002: The safety gate can create directories inside the target before refusing them

- Previous severity: High
- Current status: Resolved
- Evidence: `_backup_destination` checks `resolved.is_relative_to(source_root.resolve())` before `_dir_writable`, preserving the no-side-effect refusal. See plan lines 1856-1872 and test line 1673.
- Remaining action for Claude Code: None beyond keeping the recursive unchanged assertion.

### CR-003: Restore can partially mutate before validating overwritten-target backup integrity

- Previous severity: Critical
- Current status: Resolved
- Evidence: Restore now verifies live target, source backup, overwritten-target backup, and original-path collision before mutation, and explicitly documents the ERR-003 superset recovery mode. The test suite asserts no payload loss and retry-as-collision behavior. See plan lines 39 and 2769-2771, plus implementation sketch lines 2899-2982.
- Remaining action for Claude Code: None; implement the documented superset-mode tests exactly.

### CR-004: Stale-lock stealing can unlink a newly acquired live lock

- Previous severity: High
- Current status: Resolved
- Evidence: The plan uses `fcntl.flock` and leaves the lock file behind as metadata, eliminating unlink-by-name stealing. See plan lines 31 and 492-578.
- Remaining action for Claude Code: None beyond keeping cross-process lock tests.

### CR-005: Manifest backup paths are not guaranteed absolute

- Previous severity: High
- Current status: Resolved
- Evidence: The plan resolves relative config `write.backup_dir` at planning time and resolves CLI backup roots during apply options normalization. See plan lines 2002-2017 and 2648-2654.
- Remaining action for Claude Code: None.

### CR-006: Disk preflight underestimates write and backup space in overwrite/growing-output cases

- Previous severity: Medium
- Current status: Resolved
- Evidence: The gate now counts live overwrite target sizes and transformed-output growth headroom, with tests listed. See plan lines 1677 and 1879-1929.
- Remaining action for Claude Code: None.

### CR-NEW-001: Overwrite rename bypasses the atomic/fsync writer primitive

- Previous severity: High
- Current status: Resolved
- Evidence: `rename_overwrite` wraps `os.replace` with `WriteError` and parent fsync, and apply routes overwrite renames through it. See plan lines 1275-1300, 1441-1454, and 2411-2413.
- Remaining action for Claude Code: None.

### CR-NEW-002: Relative `write.backup_dir` from the plan snapshot is still apply-cwd dependent

- Previous severity: Medium
- Current status: Resolved
- Evidence: The plan snapshots relative `write.backup_dir` as an absolute path during planning and tests that behavior. See plan lines 2002-2017.
- Remaining action for Claude Code: None.

### CR-NEW-003: Restore falsely succeeds for overwrite-renames without tool backups

- Previous severity: High
- Current status: Resolved
- Evidence: Restore now skips overwrite records with `overwritten_sha256` but no `overwritten_backup_path`, mutating nothing and reporting `no-backup`. See plan lines 39, 2772, and 2921-2932.
- Remaining action for Claude Code: None.

### CR-NEW-004: Apply can record a failed rename-and-rewrite after publishing the target

- Previous severity: Medium
- Current status: Resolved
- Evidence: Apply now rolls back the published target on `source.unlink()` failure and adds a targeted test requiring corpus/report/manifest consistency, including overwrite collision rollback. See plan lines 2100 and 2417-2448.
- Remaining action for Claude Code: None beyond implementing the test.

## New blocking issues

None found.

## New non-blocking issues

### CR-NEW-005: Manifest creation is not directory-fsynced, weakening “fsync’d record” durability

- Severity: Medium
- Status: Confirmed
- Adversarial angle: Can the plan claim a crash-durable manifest record after fsyncing only the newly created manifest file?
- Plan reference: Design decision 7, line 36; manifest writer lines 1103-1115; spec/ADR claim that the manifest is incremental crash-recovery state.
- Finding: `ManifestWriter.append` opens the manifest lazily, writes a line, flushes, and fsyncs the file descriptor, but it never fsyncs the manifest directory when the manifest file is first created. That means the first mutation’s “fsync’d” record may still lose the directory entry after a crash on filesystems that require directory fsync for new names.
- Repository evidence: The spec says every mutation must have a reversible manifest record and that the manifest is written incrementally so a crash cannot orphan completed mutations (`docs/specs/docmend.md` lines 321, 375, 708). The repository’s own atomic-write research says D-004 uses parent-directory fsync where practical and explicitly discusses directory fsync outcome handling (`docs/research/atomic-write-filesystem-semantics.md` lines 53-56).
- External research evidence: Linux `fsync(2)` states that fsyncing a file does not necessarily persist the containing directory entry and that an explicit fsync on the directory file descriptor is needed. Source: <https://man7.org/linux/man-pages/man2/fsync.2.html>, accessed 2026-07-07.
- Why it matters: A crash after the first mutation could leave the library changed but the manifest absent, undermining the recovery model and making validation falsely pass on ordinary write/read tests that do not simulate metadata-loss crashes.
- Recommended action for Claude Code: Amend `ManifestWriter` to fsync the parent directory after the file is first created, or explicitly document why manifest-directory fsync is out of scope and downgrade the durability claim. The safer correction is to reuse the writer’s directory-fsync primitive and test that it is called on first append.
- Suggested validation: Add a unit test monkeypatching the manifest module’s directory-fsync helper to assert it runs exactly once when the manifest file is first created, plus existing per-record fsync tests.

### CR-NEW-006: The AOF reader can silently drop a corrupt complete final record

- Severity: Medium
- Status: Confirmed
- Adversarial angle: Can manifest validation pass while the last completed record is corrupt rather than merely torn?
- Plan reference: Design decision 7, line 36; manifest reader lines 1126-1150; tests lines 937-965.
- Finding: `read_manifest` uses `raw.splitlines()` and treats any JSON decode error on the final returned line as a tolerable torn trailing line. Because `splitlines()` discards newline information, the reader cannot distinguish a true unterminated torn tail from a newline-terminated corrupt final record. The current tests cover a no-newline torn tail and corrupt interior records, but not a corrupt final line that ends with `\n`.
- Repository evidence: ADR-0006 allows discarding only a torn trailing line and requires fail-safe behavior on corrupted records (`docs/adr/adr-0006-resume-and-recovery-model.md` lines 57-70). The plan’s reader sketch drops any final JSONDecodeError regardless of newline termination, at lines 1134-1147.
- External research evidence: Not applicable.
- Why it matters: A damaged final complete record could be silently ignored, causing restore/resume to operate on an incomplete manifest and potentially report success without accounting for the latest mutation.
- Recommended action for Claude Code: Preserve line endings while reading, and only tolerate a final parse error when the physical final line is unterminated. A newline-terminated corrupt final line should raise `ArtifactError`, just like corrupt interior records.
- Suggested validation: Add `test_corrupt_newline_terminated_final_record__hard_aborts` with a valid first record followed by `{corrupt}\n`; assert `read_manifest` raises `ArtifactError`.

## Regressions

None found.

## Internet research performed

- Source name: Linux man-pages `fsync(2)`
- URL: <https://man7.org/linux/man-pages/man2/fsync.2.html>
- Access date: 2026-07-07
- What it was used to verify: Whether fsyncing a file descriptor necessarily persists the containing directory entry.
- Relevant conclusion: It does not; directory entry durability requires an explicit fsync on the directory descriptor.

- Source name: Python 3.14 `os` documentation
- URL: <https://docs.python.org/3/library/os.html#os.fsync>
- Access date: 2026-07-07
- What it was used to verify: Current Python `os` filesystem API context for fsync usage.
- Relevant conclusion: Python exposes `os.fsync`, but the decisive directory-entry durability behavior is specified by the underlying OS documentation.

## Read-only validation performed

- `git status --short && git branch --show-current && git log --oneline -n 10`: confirmed branch `dev`, modified plan file, and untracked `docs/codex-reviews/`.
- `rg --files`: confirmed repository inventory and that apply/restore/writer modules remain proposed plan work, not completed implementation.
- `nl -ba` / `sed -n` on the plan: inspected revised design decisions, atomic writer, manifest writer/reader, gate, apply, restore, CLI, and restore drill sections.
- `rg` over the plan for restore, overwrite, backup, fsync, manifest, external preservation, and rollback terms: located the revised assumptions and validation claims.
- `git diff -- docs/superpowers/plans/2026-07-06-ms3-apply-writer.md`: verified the current edits against the prior audit’s open findings.
- Inspected `src/docmend/config.py`, `src/docmend/plan.py`, `src/docmend/planning.py`, `src/docmend/artifacts.py`, `src/docmend/observability.py`, and `src/docmend/cli.py`: checked current repo contracts and implementation surface.
- Inspected `docs/specs/docmend.md`, ADR-0003, ADR-0004, ADR-0006, and `docs/research/atomic-write-filesystem-semantics.md`: checked binding writer, preservation, manifest, restore, and durability contracts.
- Internet research via official Linux/Python documentation: verified the directory fsync assumption.

## Recommended implementation validation

- Run only after implementation: targeted manifest writer test asserting parent directory fsync on first manifest creation.
- Run only after implementation: `test_corrupt_newline_terminated_final_record__hard_aborts` for the manifest AOF reader.
- Run only after implementation: existing targeted restore tests for CR-003 and CR-NEW-003.
- Run only after implementation: existing targeted apply rollback test for CR-NEW-004.
- Run only after implementation: `uv run pytest tests/unit/writer/test_manifest.py tests/unit/writer/test_atomic.py tests/test_restore.py tests/test_apply.py tests/test_restore_drill.py -q`
- Run only after implementation: `uv run ruff format --check . && uv run ruff check . && uv run basedpyright`
- Run only after implementation: `uv run coverage run -m pytest && uv run coverage report`
- Run only after docs closeout: `uv run python scripts/check_traceability.py`

## Final recommendation

Claude Code should revise the plan using the findings above

## Review ledger for next loop

- Plan path: /home/chris/projects/docmend/docs/superpowers/plans/2026-07-06-ms3-apply-writer.md
- Audit round: 4
- Open issue IDs: CR-NEW-005, CR-NEW-006
- Resolved issue IDs: CR-001, CR-002, CR-003, CR-004, CR-005, CR-006, CR-NEW-001, CR-NEW-002, CR-NEW-003, CR-NEW-004
- Superseded issue IDs:
- Significant findings remaining: Yes
- Next audit should focus on: manifest creation directory-fsync durability and AOF reader handling of newline-terminated corrupt final records
