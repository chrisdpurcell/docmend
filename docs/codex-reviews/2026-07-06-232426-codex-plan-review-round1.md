# Codex plan audit — MS-3 apply/writer (2026-07-06-232426)

## Executive summary

The implementation plan needs major correction before Claude Code executes it. The plan is strong on scope, repo alignment, and test-first sequencing, but several writer/restore safety paths contradict the plan’s own dry-run, gate-refusal, lock, and standalone-restore guarantees.

Internet research was required for current Python/Pydantic behavior. No stale external assumption appears to invalidate the overall stack choice; the major findings come from repository evidence and plan-code falsification.

## Verdict

Needs major correction before execution

## Audit loop status

- Audit type: First audit
- Plan path: /home/chris/projects/docmend/docs/superpowers/plans/2026-07-06-ms3-apply-writer.md
- Significant findings remaining: Yes
- Blocking issue count: 5
- Non-blocking issue count: 1

## What the plan gets right

The plan correctly targets the MS-3 surfaces named by the live spec: writer layer, `apply`, `restore`, FR-003–FR-006, FR-011, FR-018, NFR-002/NFR-004, and AW-005. It also correctly recognizes the existing repo state: `scan`/`plan` are live, current inventory/plan schemas are still 1.0, `RelativePath` is currently only `min_length=1`, and `apply`/`restore` do not exist yet. The Pydantic lookahead concern is valid: Pydantic defaults to Rust regex for pattern validation, and the documented `AfterValidator` workaround is appropriate.

## Adversarial review performed

I inventoried the plan’s claims across writer atomicity, backup verification, manifest semantics, apply/restore flow, CLI exit taxonomy, run-lock behavior, schema versioning, path containment, and validation gates. I then checked those claims against the current source models, schemas, CLI, tests, spec §7/§8/§10/§18/§21, ADR-0004/0005/0006/0007, TODO/README/handoff state, and current dependencies.

Strongest assumptions attacked: dry-run cannot write, gate refusal leaves the library untouched, restore verifies before touching, manifest paths are standalone, and the run lock actually serializes concurrent invocations. I did not run pytest or validation gates because they would write caches/artifacts and this audit is read-only.

## Blocking issues

### CR-001: Dry-run overwrite collisions can still write backups

- Severity: High
- Status: Confirmed
- Adversarial angle: Can `docmend apply PLAN` write anything non-report/log before `--write`?
- Plan reference: Task 9 `_execute_action`, lines 2210-2234; global constraints lines 16-18.
- Finding: The apply sketch backs up an overwritten target before checking `if not options.write`. In an overwrite-collision dry-run with `write.backup_dir` configured or `backup_root` supplied to the engine, `backup_file(...)` writes to disk even though `options.write` is false.
- Repository evidence: The current config explicitly says config alone can never enable real mutation and `write.backup_dir` exists as a config field, [src/docmend/config.py](/home/chris/projects/docmend/src/docmend/config.py:99). The spec requires apply default dry-run and unchanged corpus hashes, [docs/specs/docmend.md](/home/chris/projects/docmend/docs/specs/docmend.md:318).
- External research evidence: Not applicable.
- Why it matters: This violates FR-004/NFR-004 and the plan’s “config alone can never enable writes” rule. It also creates a validation false positive because the planned dry-run tests do not cover overwrite collisions with a configured backup directory.
- Recommended action for Claude Code: Move all backup writes, including overwritten-target backups, behind the `options.write` branch. Dry-run may inspect target existence and report would-apply/collision behavior, but must not call `backup_file`.
- Suggested validation: Add a dry-run test with `rename.on_collision="overwrite"` and `write.backup_dir` set; assert no backup directory/file is created and only report/log artifacts appear.

### CR-002: The safety gate can create directories inside the target before refusing them

- Severity: High
- Status: Confirmed
- Adversarial angle: Does a safety refusal really leave the library untouched?
- Plan reference: Design decision 8 line 37; Task 8 `_dir_writable` and `_backup_destination`, lines 1673-1680 and 1771-1786.
- Finding: `_backup_destination` records `backup-outside-target` when `backup_root` resolves inside `source_root`, but it still calls `_dir_writable(options.backup_root)`. `_dir_writable` runs `mkdir(parents=True)` and creates/removes a probe file. If the forbidden backup path is `source_root / "backups"` and does not exist, the gate refusal creates a new directory inside the library.
- Repository evidence: The spec requires backup destination outside the mutation target and gate refusal as safety refusal, [docs/specs/docmend.md](/home/chris/projects/docmend/docs/specs/docmend.md:472), [docs/specs/docmend.md](/home/chris/projects/docmend/docs/specs/docmend.md:949). ADR-0004 says gate refusal is prove-before-mutate and must refuse every failed predicate, [docs/adr/adr-0004-apply-safety-gate-and-preservation.md](/home/chris/projects/docmend/docs/adr/adr-0004-apply-safety-gate-and-preservation.md:59).
- External research evidence: Not applicable.
- Why it matters: The refusal path itself pollutes the source tree, directly contradicting “library untouched” and creating a hidden side effect in exactly the safety-failure scenario.
- Recommended action for Claude Code: Short-circuit backup destination checks: if `backup_root` is inside `source_root`, return that refusal without writability probing or mkdir. Add no-side-effect assertions for all gate refusals.
- Suggested validation: For `backup_root=source_root/"backups"` where the path is absent, call `evaluate_gate(...)` and assert the refusal is present and `source_root/"backups"` still does not exist.

### CR-003: Restore can partially mutate before validating overwritten-target backup integrity

- Severity: Critical
- Status: Confirmed
- Adversarial angle: Does restore verify every needed recovery input before touching live files?
- Plan reference: Design decision 10 line 39; Task 11 restore sketch, lines 2746-2764.
- Finding: For `rename_and_rewrite`, restore writes the original file and unlinks the target before reading and hash-checking `overwritten_backup_path`. If that overwritten-target backup is missing or hash-mismatched, restore returns failed after already changing the corpus.
- Repository evidence: FR-006 acceptance requires restoring from manifest+backups reproduces the original corpus, [docs/specs/docmend.md](/home/chris/projects/docmend/docs/specs/docmend.md:321). ADR-0004 requires mechanical undoability and verify-then-mutate, [docs/adr/adr-0004-apply-safety-gate-and-preservation.md](/home/chris/projects/docmend/docs/adr/adr-0004-apply-safety-gate-and-preservation.md:59).
- External research evidence: Not applicable.
- Why it matters: A failed restore can destroy the applied target state and still fail to reinstate the clobbered target. This is a data-integrity failure in the disaster-recovery path.
- Recommended action for Claude Code: Preflight all restore prerequisites before any write/unlink: live after-hash, source backup, overwritten-target backup, destination collision state, and all needed hashes. Only mutate after preflight succeeds.
- Suggested validation: Add a test corrupting `overwritten_backup_path` for an overwrite `rename_and_rewrite` record; assert restore returns failed and both live files remain byte-for-byte unchanged.

### CR-004: Stale-lock stealing can unlink a newly acquired live lock

- Severity: High
- Status: Confirmed
- Adversarial angle: Does the O_EXCL lock algorithm actually preserve AW-005 under races?
- Plan reference: Task 3 `lock.acquire`, lines 551-573; `RunLock.release`, lines 505-513.
- Finding: On stale/corrupt lock detection, the plan unlinks the lock path by name and retries. If another process acquires a fresh lock between this process reading the stale holder and calling `unlink`, the stale-stealer can remove the new live lock. `RunLock.release()` also unlinks by path without proving it still owns that path.
- Repository evidence: AW-005 requires a second concurrent plan/apply to refuse and no shared artifact to be written by two live runs, [docs/specs/docmend.md](/home/chris/projects/docmend/docs/specs/docmend.md:630). ADR-0007’s amendment records the lock as the concurrency protection, [docs/adr/adr-0007-concurrency-primitive-process-pool.md](/home/chris/projects/docmend/docs/adr/adr-0007-concurrency-primitive-process-pool.md:73).
- External research evidence: Not applicable.
- Why it matters: The lock can fail open under exactly the stale-lock race it tries to handle, allowing two live runs against one target.
- Recommended action for Claude Code: Make stale removal owner-aware: write a unique token in the holder, compare device/inode or token immediately before unlink, and make release unlink only if the on-disk holder still matches this process’s token. Add a race test.
- Suggested validation: Simulate stale-read/new-acquire/unlink interleaving and assert the new holder is not removed and the stale-stealer retries/refuses.

### CR-005: Manifest backup paths are not guaranteed absolute

- Severity: High
- Status: Confirmed
- Adversarial angle: Can `restore` locate backups from the manifest alone after cwd changes?
- Plan reference: Design decision 7 line 36; Task 7 `backup_file`, lines 1514-1533; Task 9 `_record`, lines 2330-2338.
- Finding: The plan says manifest records carry absolute paths, but `_record` resolves only `original_path` and `target_path`. It serializes `backup_path` and `overwritten_backup_path` with `str(path)`. If the operator supplies a relative `--backup-dir`, restore will later depend on cwd.
- Repository evidence: The manifest schema currently carries backup paths as strings intended for restore, [src/docmend/schemas/manifest.schema.json](/home/chris/projects/docmend/src/docmend/schemas/manifest.schema.json:55). The plan’s own decision says restore has no PATH argument and must locate files standalone.
- External research evidence: Not applicable.
- Why it matters: Restore can fail or read the wrong backup when invoked from a different directory, breaking IR-008 and the manifest’s standalone recovery role.
- Recommended action for Claude Code: Resolve `backup_root` once at CLI/options normalization or have `backup_file` return `dest.resolve()`. Manifest serialization should use resolved absolute backup paths for both normal and overwritten-target backups.
- Suggested validation: Run apply with a relative `--backup-dir`, change cwd, then restore by absolute manifest path and assert it finds the backups.

## Non-blocking issues

### CR-006: Disk preflight underestimates write and backup space in overwrite/growing-output cases

- Severity: Medium
- Status: Confirmed
- Adversarial angle: Can the gate pass while the write path still predictably runs out of space?
- Plan reference: Task 8 `_backup_destination` and `_source_headroom`, lines 1787-1798 and 1812-1826.
- Finding: Backup space is estimated as `sum(a.source_size_bytes)`, but overwrite mode can also back up clobbered targets. Source headroom uses the largest original source size, but transformed output can be larger than the input.
- Repository evidence: The config supports overwrite collisions, [src/docmend/config.py](/home/chris/projects/docmend/src/docmend/config.py:54). FR-011 requires overwrite behavior to be explicit and manifest-recorded, [docs/specs/docmend.md](/home/chris/projects/docmend/docs/specs/docmend.md:326).
- External research evidence: Not applicable.
- Why it matters: The disk preflight can falsely pass and defer predictable ENOSPC failures to the dangerous mutation phase.
- Recommended action for Claude Code: Include existing target sizes for live overwrite collisions and either compute planned payload sizes during apply preflight or use a conservative upper bound before write.
- Suggested validation: Add gate tests with overwrite targets larger than sources and transform output larger than source; monkeypatch `disk_usage` to prove refusal happens before mutation.

## Missing considerations

- Blocking: Dry-run validation must attack config-driven and overwrite-driven writes, not only default dry-run over a simple rewrite.
- Blocking: Gate refusal tests must assert filesystem no-side-effects, especially for invalid backup destinations inside `source_root`.
- Blocking: Restore tests must cover failure atomicity, not just successful restore and modified-since-apply skips.
- Blocking: Run-lock tests need race/interleaving coverage for stale lock stealing and owner-safe release.
- Blocking: Manifest path tests need relative `--backup-dir` plus restore from a different cwd.
- Non-blocking: Disk preflight should cover overwritten-target backups and payload growth.
- Non-blocking: The plan should state whether empty write-mode manifests are printed/reported when all actions skip.

## Internet research performed

- Source name: Python 3.14 `os` module documentation
- URL: <https://docs.python.org/3.14/library/os.html>
- Access date: 2026-07-07
- What it was used to verify: `os.link` hard-link behavior and current Python filesystem API availability.
- Relevant conclusion: The plan’s link-based no-clobber rename is plausible on the Python/POSIX target, but the lock races are design-level issues not solved by `O_EXCL` alone.

- Source name: Pydantic `ConfigDict.regex_engine` documentation
- URL: <https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict.regex_engine>
- Access date: 2026-07-07
- What it was used to verify: Pydantic v2 default regex engine behavior.
- Relevant conclusion: Pydantic defaults to `rust-regex`, which does not support all regex features; the plan’s model-side `AfterValidator` for lookahead-based path rules is appropriate.

## Items Claude Code should verify before correcting the plan

- Verify whether `apply` should ever write empty manifests for all-skipped write runs, and whether CLI should print their path.
- Verify desired restore semantics for overwrite records before implementation: all prerequisites should be validated before any mutation.
- Verify whether plan locking may warn-and-proceed on uncreatable state dir, because current spec text says second concurrent plan/apply refuses exit 3.
- Verify schema README and spec wording after resolving whether pattern tightening is acceptable as 1.1 rather than a major bump.

## Suggested corrections for Claude Code's plan

- Move overwritten-target backup writes behind `options.write`.
- Short-circuit backup-inside-target gate failures before any mkdir/probe.
- Redesign restore as preflight-then-mutate for every record, including overwritten-target backup verification.
- Make lock acquisition/release owner-token safe under stale-lock races.
- Resolve backup paths to absolute paths before manifest serialization.
- Expand tests to include the false-positive validation cases above.
- Adjust disk preflight to account for overwrite backup size and output growth.

## Read-only validation performed

- `git status --short && git branch --show-current && git log --oneline -n 10`: confirmed branch `dev`, plan commit at HEAD, and no displayed dirty status.
- `sed -n` / `nl -ba` on the plan path: inventoried all task claims and captured exact line references.
- `rg --files`: confirmed current repo file inventory and that `apply`, `restore`, and writer modules are not implemented yet.
- Inspected `docs/handoff/state.md` and `docs/handoff/conventions.md`: confirmed MS-2 current state and repo conventions.
- Inspected `src/docmend/{inventory.py,plan.py,planning.py,discovery.py,config.py,artifacts.py,cli.py}` and schemas: checked current models, schema versions, config surface, CLI commands, and artifact IO.
- Inspected `docs/specs/docmend.md`, `docs/open-questions.md`, `docs/resolved-questions.md`, and ADR-0003/0004/0005/0006/0007/0012: checked binding requirements and decisions.
- Inspected existing CLI/artifact tests: checked current test style and gaps relevant to the proposed additions.

## Recommended implementation validation

- Run only after implementation: `uv run pytest tests/test_cli_apply.py tests/test_apply.py tests/test_gate.py tests/test_restore.py -q`
- Run only after implementation: targeted new tests for CR-001 through CR-005.
- Run only after implementation: `uv run ruff format --check . && uv run ruff check . && uv run basedpyright`
- Run only after implementation: `uv run coverage run -m pytest && uv run coverage report`
- Run only after docs closeout: `uv run python scripts/check_traceability.py`
- Run only after docs closeout: project-standards spec validate/lint and markdown checks from the plan.

## Final recommendation

Claude Code should revise the plan using the findings above

## Review ledger for next loop

- Plan path: /home/chris/projects/docmend/docs/superpowers/plans/2026-07-06-ms3-apply-writer.md
- Audit round: 1
- Open issue IDs: CR-001, CR-002, CR-003, CR-004, CR-005, CR-006
- Resolved issue IDs:
- Superseded issue IDs:
- Significant findings remaining: Yes
- Next audit should focus on: dry-run no-write guarantees, safety-refusal no-side-effects, restore preflight ordering, lock ownership/race safety, absolute manifest backup paths, and expanded validation for those fixes
