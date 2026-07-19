# docmend — Comprehensive Project Review

- **Project:** docmend (v2.0.0)
- **Repo path:** `~/projects/docmend`
- **Reviewed commit:** `ed268c95779af8417305d5a8564e3cc31930b925` (branch `dev`, clean working tree)
- **Reviewer:** Claude Fable 5 (high effort); breadth via six parallel Opus subsystem reviewers; every finding re-checked by two fresh-context verifier agents
- **Review date:** 2026-07-19
- **Verification note:** 26 findings survived the verifier pass out of 32 candidate items — 2 pruned (one contradicted a pinning test and spec intent, one was empirically false), 1 downgraded Medium→Low (behavior is owner-approved DEV-001), 2 reclassified as Open Questions, 2 informational notes folded into the Coverage Ledger. Several line numbers and one fix were corrected during verification.
- **Remediation:** all 26 findings fixed 2026-07-19 and shipped in v2.0.1. F-013 resolved as no-change — Ruff's py314 formatter enforces the bare multi-exception `except` form, so the prescribed parenthesization is unimplementable; semantics-trap comments were added instead. F-014/F-015 additionally required patching `_reconcile_file_size_tier` and a `QualificationHarnessError` exit-1 path. OQ-1 and OQ-2 remain open for owner decision.

## Gate results (run during this review, at the reviewed commit)

| Check | Result |
| --- | --- |
| `uv run ruff format --check .` | 109 files already formatted |
| `uv run ruff check .` | All checks passed |
| `uv run basedpyright` | 0 errors, 0 warnings, 0 notes |
| `uv run coverage run -m pytest` | 1726 passed in 72.64s (0 failed; 0 skipped on this non-root runner) |
| `uv run coverage report` | TOTAL 89% branch coverage (gate `fail_under = 85`) |
| `uv run pip-audit` | No known vulnerabilities |

Notes: an IDE-side session snapshot claimed 18 failing tests; that was stale — the suite is fully green at this commit. The code tree contains **zero** TODO/HACK/XXX/FIXME markers (`git grep -niE '\b(todo|hack|fixme|xxx)\b' -- 'src/**' 'tests/**'` → 0 matches); marker counts reported by session tooling come from prose in `docs/`. `scripts/check.py` runs the full unweakened gate (its byte-identity with the project-standards twin is asserted by CI, not locally verifiable — the bundle is not vendored here).

## Executive Summary

docmend at v2.0.0 is in excellent health. Every mechanical gate passes at the reviewed commit, the spec's §18.2 config-defaults table has zero drift against `config.py`, the writer's safety core (manifest 2.0 chain validation, verify-then-mutate backups, atomic publication, adjudication tables) survived line-by-line adversarial review with no correctness defects, and the scale-qualification harness shows no false-accept, hash-bypass, or privacy-leak path. The review found **no Critical or High findings**. The two Medium items are: (1) a misclassified failure in the scale file-size lane — a wrong-sized tool backup produces no outcome reason, crashes evidence construction, and surfaces as exit 2 ("bad invocation") instead of published failed evidence; and (2) README drift — the `verify` documentation is a full version behind the shipped safety-relevant interface (`--plan`, `--out`, exit 3). The remaining 24 findings are localized robustness hardening (lock/fd leak windows, a TOCTOU hardening opportunity beyond the accepted DEV-001 posture, verify defense-in-depth), dead code, fixture-generator reproducibility, and documentation staleness.

| Severity | Architecture | Structure | Correctness | Security | Performance | Testing | Convention | Docs | **Total** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Critical | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| High | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| Medium | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | **2** |
| Low | 1 | 3 | 10 | 1 | 1 | 2 | 2 | 4 | **24** |
| **Total** | **1** | **3** | **11** | **1** | **1** | **2** | **2** | **5** | **26** |

## Coverage Ledger

| Subsystem / path | Depth | Notes |
| --- | --- | --- |
| `src/docmend/config.py`, `discovery.py`, `detection.py`, `inventory.py`, `planning.py`, `plan.py`, `frontmatter.py`, `watchdog.py` | Deep | Every line read. Newline census chunking, BOM sniff order, encoding gate ladder, DMR-01 collision/claimed-output tracking, shrink invariant, UTF-16-suspect split, watchdog scoping all verified correct. Hard-link plan-time skip confirmed as approved DEV-001. |
| `src/docmend/transform/` (all 5 files) | Deep | Clean. Dispatch order matches adr-0016; EC-005 metric Unicode-aware; CRLF-before-CR replacement order correct. |
| `src/docmend/writer/` (all 8 files) + `lock.py` | Deep | Every line read. `atomic.py`, `backup.py`, `gate.py`, `manifest.py`, `adjudicate.py` clean — manifest 2.0 chain validation, verify-then-mutate backups, and the adjudication identity predicates are internally consistent. Findings in `apply.py`, `commit.py`, `lock.py`. |
| `src/docmend/cli.py`, `restore.py`, `verify.py`, `verify_coverage.py`, `verify_report.py`, `artifacts.py`, `report.py`, `lineage.py`, `observability.py`, `__init__.py` | Deep | Every line read. Exit-taxonomy mapping, artifact destination guard (no bypass found), restore LIFO/convergence, verify plan-coverage exactly-once partition all traced. Findings in `verify.py`, `observability.py`, `cli.py`+`restore.py`. |
| `src/docmend/schemas/` (JSON schemas) | Deep (except one) | Product schemas cross-checked against Pydantic models; `scale-evidence.schema.json` (43 KB) scanned only — it belongs to the qualification subsystem reviewed separately. |
| `src/docmend/scale_qualification.py`, `scale_evidence.py`, `scale_resources.py` | Deep | Every line read. Verdict precedence, threshold context hash binding, upward-rounded linearity (no false pass), Btrfs fail-closed classification, single-mountinfo-snapshot rule verified. Findings: the file-size backup reason gap and dead helpers. |
| `src/docmend/scale_stage.py`, `scale_build.py`, `scale_reconcile.py`, `scale_corpus.py` | Deep | Every line read. Env allowlist fail-closed; O_TMPFILE+linkat exclusive publication; hash-locked installs (`--require-hashes --no-index --no-deps`); exact-multiset finding reconciliation (no false-accept found); deterministic corpus recipe with injective path mapping and exact inode math. One dead-code finding. |
| `scripts/` (all 6 scripts) | Deep | `check_traceability.py`, `fix_spec_toc.py`, and the two thin wrappers clean. Findings in `gen_weird_corpus.py`. `check.py` gate unweakened (see Gate results note). |
| `tests/` (62 files, ~20k lines) | Scanned (targeted deep reads) | conftest files, `tests/helpers/`, timing-sensitive tests (`test_watchdog.py`, `test_lock.py`) and subprocess-heavy scale tests deep-read — not racy; expensive ops faked. Fixtures spot-checked: synthetic only, no real personal content (public-repo policy holds). Only conditional skips are four root-guard `skipif`s; no xfail. Exhaustive line-by-line of every test module was not performed (the green suite and 89% branch coverage bound the risk). |
| `.github/` (8 workflows, dependabot, dependency-review) | Deep | Gate complete (ruff format+check, basedpyright, pytest, coverage `fail_under=85`, pip-audit, markdownlint, validate-specs, traceability). Actions SHA-pinned. `dependency-review` is PR-only with a documented compensating control. No weakening found. |
| Docs (`README.md`, `CHANGELOG.md`, `docs/STATUS.md`, `docs/TODO.md`, `docs/handoff/`, spec §18.2 defaults) | Deep | Spec §18.2 config-defaults table vs `config.py`: **zero drift** (all 21 defaults match — the §18.7 claim holds). CHANGELOG/version consistent. Drift findings against README and `docs/handoff/architecture.md`. |
| `docs/specs/docmend.md` (1,320 lines) | Deep (main sections), Scanned (appendices) | Requirements, architecture, data model, error handling, security, testing, and ops sections read in the main thread; §21 OQ register and appendices scanned. |
| `dist/`, `docs/scale-evidence/`, `docs/adr/` (25 ADRs), `docs/codex-reviews/`, `docs/research/`, `docs/runbooks/` | Skipped / consulted on demand | Build artifacts and historical records; ADRs and evidence documents consulted where findings referenced them, not independently audited. |

## Severity & Category Rubric

**Severity** — the bar used for every finding below:

- **Critical** — data loss, security breach, or crash on a normal path. (None found.)
- **High** — incorrect behavior on a realistic input, or a clear violation of a binding spec requirement with downstream impact. (None found.)
- **Medium** — a correctness or contract issue with a narrow trigger or workaround: a misclassified failure, a wrong outcome in an edge window, or user-facing documentation that misstates the current safety-relevant interface.
- **Low** — localized robustness gap, dead code, minor convention drift, or documentation staleness with no behavioral consequence on normal paths.

**Confidence** — High: verified empirically or by complete code trace during the verifier pass; Medium: traced but depends on an unexercised path or external behavior; Low: plausible reading that needs an owner/spec judgment.

**Categories:** Architecture, Structure, Correctness, Security, Performance, Testing, Convention, Docs. "Convention" covers violations of the repo's own documented rules (`docs/handoff/conventions.md`, adopted Project Standards).

## Findings

### Core read layers

#### F-001 — Decode the config file with `utf-8-sig` so a BOM'd `docmend.toml` loads

- Category: Correctness · Severity: Low · Confidence: High
- Location: `src/docmend/config.py:194` (`load_config`)
- Evidence (`config.py:194`): `raw = tomllib.loads(path.read_text(encoding="utf-8"))`
- Problem: a `docmend.toml` saved with a UTF-8 BOM (common from Windows/GUI editors) decodes to a leading `﻿`, which `tomllib` rejects with `TOMLDecodeError: Invalid statement (at line 1, column 1)` (reproduced empirically during review). The user sees a misleading "not valid TOML" error for a structurally valid file; IR-006 requires clear config errors.
- Fix: in `src/docmend/config.py:194`, change the encoding argument to `encoding="utf-8-sig"` (which accepts both BOM'd and BOM-less files). No other behavior change.
- Verification: add a test in `tests/test_config.py` that writes a config file whose bytes start with `\xef\xbb\xbf` and assert it loads to the same model as the BOM-less file; `uv run pytest tests/test_config.py`.
- Dependencies: none · Effort: S

#### F-002 — Split frontmatter text on `"\n"` instead of `str.splitlines()` so embedded Unicode separators cannot close the block

- Category: Correctness · Severity: Low · Confidence: High
- Location: `src/docmend/frontmatter.py:58-64` (`extract_frontmatter`)
- Evidence (`frontmatter.py:58`, `:62`): `lines = text.splitlines()` … `if line.strip() in _CLOSERS:`
- Problem: `str.splitlines()` splits on the full Unicode line-boundary set (U+000B, U+000C, U+001C–U+001E, U+0085, U+2028, U+2029), not just `\n`. A physical line containing e.g. `… ---` is split so that a segment strips to `---`, which the closer test accepts — terminating the frontmatter block before the real fence and mis-deriving block boundaries. The rest of the pipeline uses LF-only semantics.
- Fix: in `src/docmend/frontmatter.py:58`, replace `text.splitlines()` with `text.split("\n")`. This is safe: the only production caller (`verify.py:105`) reads files via `Path.read_text`, whose universal-newline translation converts CRLF/CR to `\n` before this function sees the text (verified during review), so no CRLF regression is possible.
- Verification: add a fixture-based test where the YAML block contains a U+2028 inside a value and assert `extract_frontmatter` returns the block bounded by the true `---` fence; `uv run pytest tests/test_frontmatter.py`.
- Dependencies: none · Effort: S

#### F-003 — Stop re-opening legacy-encoded files for detection at scan (or record the double read as a deliberate tradeoff)

- Category: Performance · Severity: Low · Confidence: Medium
- Location: `src/docmend/discovery.py:305` and `src/docmend/detection.py:41-46`
- Evidence (`discovery.py:305`): `detected = detection.detect_legacy(full)` — which calls `from_path(path).best()` (`detection.py:42`) after `classify_file` already streamed the whole file at `discovery.py:296`.
- Problem: every no-BOM, non-UTF-8, NUL-free file — i.e. exactly the legacy-encoded documents the tool exists to convert, potentially the majority of a real corpus — is opened and read twice during scan. On the 1M-file hot path this doubles open/read syscalls for the legacy subset; the bytes read by `classify_file` are discarded.
- Fix: have `classify_file` retain a bounded head buffer (e.g. first 64 KiB, keeping per-file memory bounded per NFR-001) and expose it on its result; add a `detect_legacy_bytes(head: bytes)` variant in `src/docmend/detection.py` using charset-normalizer's `from_bytes`, and call it from `_process_candidate` in `discovery.py` instead of `detect_legacy(path)`. If the owner prefers the accuracy of charset-normalizer's own full-file sampling, instead record the double read as a deliberate IO/accuracy tradeoff in a code comment at `discovery.py:305` and close this finding as accepted.
- Verification: `strace -c -e trace=openat uv run docmend scan <legacy-corpus>` before/after shows one fewer open per legacy file; `uv run pytest tests/test_detection.py tests/test_discovery.py` stays green.
- Dependencies: none · Effort: M

#### F-004 — Classify `detected is None` under an unknown scan-detection fact as low-confidence, not binary-suspect

- Category: Correctness · Severity: Low · Confidence: Medium
- Location: `src/docmend/planning.py:99-106` (`_fact_skip`)
- Evidence (`planning.py:99-106`): `if enc.detected is None:` / `if scan_detect is False:` … `return SkipDecision(path=path, reason="binary-suspect", detail="no encoding candidate")`
- Problem: `scan_config.encoding_detect` is `bool | None`, where `None` marks a pre-1.1 inventory in which the fact is unknown (`inventory.py:107`). Only `scan_detect is False` gets the "detection was not run at scan" path; `None` falls through to `binary-suspect` — telling the operator "we looked and it seems binary" when the truth is "we never looked". Only reachable when planning consumes a legacy persisted inventory.
- Fix: in `src/docmend/planning.py:100`, change the guard from `if scan_detect is False:` to `if scan_detect is not True:` so both `False` and `None` return the low-confidence "encoding detection was not run at scan" skip, reserving `binary-suspect` for `scan_detect is True` with no candidate.
- Verification: unit test `_fact_skip` with a no-BOM, non-utf8-valid `FileRecord` with `detected=None` under `scan_detect=None`; assert the skip reason is `low-confidence-encoding`; `uv run pytest tests/test_planning.py`.
- Dependencies: none · Effort: S

### Writer and lock

#### F-005 — Re-check `st_nlink` at apply time as hardening beyond the DEV-001 plan-time gate

- Category: Correctness · Severity: Low · Confidence: Medium
- Location: `src/docmend/writer/commit.py:114-130` (`bind_file`), consumed at `src/docmend/writer/apply.py:487-530` (`_execute_action`)
- Evidence (`commit.py:115-116`): `stat_result = os.fstat(fd)` / `if not stat.S_ISREG(stat_result.st_mode):` — only the file type is inspected; no `st_nlink` check exists anywhere on the apply path (the hard-link gates live at `discovery.py:232` and `planning.py:68`).
- Problem: DEV-001 (spec Deviations Log, owner-approved 2026-07-07) accepts plan-time-only hard-link skipping, so this is **not** a spec violation. But a file with `st_nlink == 1` at plan time that gains a second hard link before apply is mutated: staged-write + `os.replace` creates a fresh inode at the source name and the other alias silently keeps the old bytes. No data is lost (the alias and any backup preserve the original), but the EC-011 skip-and-report intent is bypassed in the plan→apply window. Since `bind_file` already has the `fstat` result in hand, closing the window is O(1).
- Fix: capture `st_nlink` on the `BoundFile` in `bind_file` (`src/docmend/writer/commit.py`), and in `_execute_action` (`src/docmend/writer/apply.py`, immediately after the `bind_file` call at line 492) skip the action with reason `hard-link-alias` (the reason planning already uses) when `st_nlink > 1`, before any mutation. Record the addition as an extension of DEV-001's rationale (plan-time skip remains the primary gate; this is a commit-boundary re-check consistent with the existing commit-boundary source-identity binding).
- Verification: add a test that creates a hard link to the source after plan and before apply, then asserts the action is skipped with reason `hard-link-alias` and the alias content is unchanged; `uv run pytest tests/test_apply.py -k nlink`.
- Dependencies: none · Effort: S

#### F-006 — Move `restore_write_context`'s attestation construction inside the lock's try/finally

- Category: Correctness · Severity: Low · Confidence: High
- Location: `src/docmend/writer/commit.py:638-665` (`restore_write_context`)
- Evidence (`commit.py:639`, `:643-660`, `:661-665`): `run_lock = lock.acquire(source_root, run_id=run_id, command="restore")` … `context = WriteSafetyContext(…)` … then `try: yield context` / `finally: … run_lock.release()`
- Problem: the `WriteSafetyContext`/`_Attestation` construction sits after `lock.acquire` but outside the `try/finally` that releases the lock, so any exception there leaves the flock held for the process lifetime. `apply_write_context` (`commit.py:596-619`) does this correctly. Today the construction cannot realistically raise (the `or manifest_sha256(tip.path)` fallback at line 652 is dead because `read_manifest_chain` always populates `tip.sha256`), so this is a fragility, not a live leak — but the asymmetry invites a future regression.
- Fix: in `src/docmend/writer/commit.py`, restructure `restore_write_context` so everything after `lock.acquire(...)` — including the attestation and context construction — is inside a `try:` whose `finally:` performs `context._active = False` (guarded for the not-yet-constructed case) and `run_lock.release()`, matching `apply_write_context`'s shape.
- Verification: add a test that monkeypatches `WriteSafetyContext.__init__` to raise, calls `restore_write_context`, and asserts a subsequent `lock.acquire` on the same root succeeds; `uv run pytest tests/unit/writer/test_commit.py`.
- Dependencies: none · Effort: S

#### F-007 — Close the lock fd (releasing the flock) when the holder-metadata write fails in `lock.acquire`

- Category: Correctness · Severity: Low · Confidence: High
- Location: `src/docmend/lock.py:80-94` (`acquire`)
- Evidence (`lock.py` post-flock sequence): `os.ftruncate(fd, 0)` / `os.write(fd, json.dumps({...}).encode("utf-8"))` / `os.fsync(fd)` / `return RunLock(path, fd)`
- Problem: after `flock` succeeds, the holder-JSON write has no error handling. An `OSError` (ENOSPC on the state filesystem, EIO) propagates with the fd never closed, so the flock stays held for the process lifetime. The pre-flock failure paths (lines 70 and 73) carefully `os.close(fd)` before raising; this path is the one inconsistency.
- Fix: in `src/docmend/lock.py`, wrap the ftruncate/write/fsync block (lines 81-93) in `try/except OSError:` that does `os.close(fd)` and re-raises, so a metadata-write failure releases the lock like every other failure path.
- Verification: test that monkeypatches `os.write` to raise `OSError` inside `acquire`, asserts the exception propagates, and asserts a second `acquire` on the same root succeeds; `uv run pytest tests/test_lock.py`.
- Dependencies: none · Effort: S

#### F-008 — Fsync the source parent directory after the source unlink in rename flows

- Category: Correctness · Severity: Low · Confidence: Medium
- Location: `src/docmend/writer/apply.py:719-720` (rename_and_rewrite inline path); `src/docmend/writer/commit.py:246-262` (`guarded_rename_no_clobber`, same gap)
- Evidence (`apply.py:720`): `source.unlink()` with no following `fsync_dir(source.parent)`; `guarded_rename_no_clobber` ends with `fsync_dir(target.parent)` (`commit.py:262`) — durability is guaranteed for the target entry's creation but not for the source entry's removal in either flow.
- Problem: the unlink of the source directory entry is never made durable. A crash immediately after unlink can resurrect the source name on remount. This is recoverable — adjudication classifies the state and re-executes the removal — so it is not a data-loss bug, but it is an inconsistent durability posture (targets are fsync'd, source removals are not) that produces avoidable post-crash reconciliation work.
- Fix: add `fsync_dir(source.parent)` after the successful `source.unlink()` at `src/docmend/writer/apply.py:720`, and after the source unlink inside `guarded_rename_no_clobber` in `src/docmend/writer/commit.py` (before its return). When source and target share a parent, the second fsync is a cheap no-op-equivalent; do not special-case it.
- Verification: `uv run pytest tests/test_apply.py -k rename` and `tests/unit/writer/test_commit.py` stay green; optionally extend a crash-injection test to assert the source entry removal is durable.
- Dependencies: none · Effort: S

#### F-009 — Contain the source path before `bind_file` reads it, closing the pre-containment read window

- Category: Security · Severity: Low · Confidence: Medium
- Location: `src/docmend/writer/apply.py:491-509`
- Evidence (`apply.py:492`, `:507-509`): `bound = bind_file(source)` reads the file's bytes; the containment gate `candidate.resolve().is_relative_to(root_resolved)` runs afterwards.
- Problem: `bind_file` applies `O_NOFOLLOW` only to the final path component (`commit.py:108`). A parent directory swapped for a symlink pointing outside the corpus root between plan and apply is followed by `os.open`, so an out-of-root file's bytes are read (and its path logged) before the containment check skips the action. Mutation remains contained — the gate at 507-509 and `check_bound`'s re-resolution both hold — so this is a read/info-exposure window only, in the same single-user threat model the spec accepts. Still, the write side is stricter than the read side for no reason.
- Fix: in `_execute_action` (`src/docmend/writer/apply.py`), perform the resolve-and-contain check on `source` (and `target`) before calling `bind_file`, skipping the action on containment failure without opening the file. (A dirfd-walk `O_NOFOLLOW` open is the stronger alternative but is not required for this threat model.)
- Verification: test that swaps a parent directory for an out-of-root symlink after plan and asserts the action skips on containment with no open of the out-of-root file (assert via an audit hook or by making the out-of-root file unreadable and asserting no error is logged); `uv run pytest tests/test_apply.py`.
- Dependencies: none · Effort: M

### CLI, verify, restore, observability

#### F-010 — Emit a verify finding for an `applied` manifest record whose `after_sha256` is null

- Category: Correctness · Severity: Low · Confidence: Medium
- Location: `src/docmend/verify.py:186-193` (`check_outputs`)
- Evidence (`verify.py:187-193`): `if (` / `lifecycle.state != "applied"` / `or action_id in unsafe_action_ids` / `or record.after_sha256 is None` / `):` / `continue`
- Problem: the manifest schema's `after_sha256` is `oneOf null|sha256` with no per-result conditional, and `manifest.py`'s lifecycle validation constrains the after-hash only for `failed` terminals — so an `applied` record with a null after-hash survives full chain validation (verified during review). `check_outputs` then treats it as nothing-to-verify and silently continues: the live output is never hashed. docmend's own writer never emits this shape, but verify's purpose (FR-014: manifest/hash consistency, "never silence") is to catch corrupt or crafted manifests; this shape currently produces a false-clean.
- Fix: in `src/docmend/verify.py`, split the guard: when `lifecycle.state == "applied" and action_id not in unsafe_action_ids and record.after_sha256 is None`, append `VerifyFinding(record.target_path, "hash", "applied record has no recorded after-hash to verify against")` instead of continuing.
- Verification: add a manifest fixture (via `tests/helpers/manifest2.py`) with an `applied` record carrying `after_sha256: null`; assert `docmend verify` exits 1 with a `hash` finding; `uv run pytest tests/test_verify.py tests/test_cli_verify.py`.
- Dependencies: none · Effort: S

#### F-011 — Close replaced logging handlers in `configure_logging`

- Category: Correctness · Severity: Low · Confidence: High
- Location: `src/docmend/observability.py:322-324` (`configure_logging`)
- Evidence (`observability.py:322-324`): `root = logging.getLogger()` / `root.setLevel(logging.DEBUG)` / `root.handlers = [file_handler, console_handler]`
- Problem: the handler list is replaced wholesale without closing the previously attached `FileHandler`. The docstring (lines 280-283) declares "idempotent per process … future in-process reuse" as a contract, and every reconfigure under that contract leaks the prior run's open `.jsonl` file descriptor until GC.
- Fix: in `src/docmend/observability.py`, before reassigning `root.handlers`, iterate the existing handlers and call `.close()` on each (then assign the new list).
- Verification: test that calls `configure_logging` several times and asserts the count of open descriptors on `.jsonl` files (via `/proc/self/fd`) does not grow; `uv run pytest tests/test_observability.py`.
- Dependencies: none · Effort: S

#### F-012 — Distinguish "id matched only non-restorable records" from "no match" in restore's error message

- Category: Correctness · Severity: Low · Confidence: High
- Location: `src/docmend/cli.py:1024-1031`; interacting code at `src/docmend/restore.py:239-247` (`preview_restore`) and `src/docmend/restore.py:306-315` (`run_restore`)
- Evidence (`cli.py:1024-1031`): `if only_id and not outcomes:` → `"restore: no manifest record matches the requested id(s)"` with `typer.Exit(1)`
- Problem: `outcomes` is empty both when `--id` matches nothing and when every matched record is in `failed` lifecycle state — both engine functions `continue` past failed records without appending an outcome (verified by trace: a matching `docmend_id` passes the id filter, `_non_action_outcome` returns `None` for failed, then `if state.state == "failed": continue`). The operator whose id matched only failed records is told nothing matched, misdirecting diagnosis toward a typo. Exit 1 is correct; only the message is wrong.
- Fix: have `preview_restore` and `run_restore` (in `src/docmend/restore.py`) also return (or expose via their result object) the count of records matched by the id selector; in `src/docmend/cli.py:1024-1031`, when the count is > 0 and `outcomes` is empty, emit "restore: the requested id(s) matched only non-restorable (failed) records" instead of the no-match message.
- Verification: test restoring `--id X` where X's records are all failed-state; assert the matched-but-non-restorable message and exit 1; `uv run pytest tests/test_restore.py tests/test_cli_apply.py -k restore`.
- Dependencies: none · Effort: S

#### F-013 — Parenthesize the nine unparenthesized multi-exception `except` clauses for house-style consistency

- Category: Convention · Severity: Low · Confidence: High
- Location: `src/docmend/verify.py:197`, `src/docmend/lock.py:105`, `src/docmend/writer/apply.py:331`, `src/docmend/scale_stage.py:723`, `src/docmend/scale_stage.py:1235`, `src/docmend/scale_qualification.py:429`, `src/docmend/scale_qualification.py:1988`, `src/docmend/scale_qualification.py:2435`, `src/docmend/scale_qualification.py:2673`
- Evidence (`verify.py:197`): `except OSError, InterferenceError:` — versus the parenthesized house style eight lines below (`verify.py:222`): `except (OSError, InterferenceError) as exc:`
- Problem: PEP 758's unparenthesized form is valid under `requires-python = ">=3.14"` (all nine sites compile and pass the gate — these are not bugs), but the codebase otherwise uses parentheses everywhere, and the bare-comma form is visually identical to the Python-2 `except E, name:` defect. Mixed style invites misreading and copy-paste errors.
- Fix: rewrite each of the nine listed sites to the parenthesized form `except (A, B):`. Purely mechanical; no behavior change.
- Verification: `grep -rnE 'except [A-Za-z_]+, [A-Za-z_]+:' src/` returns no matches; `uv run ruff check .` and `uv run pytest` stay green.
- Dependencies: none · Effort: S

### Scale qualification harness

#### F-014 — Record a failure reason for a wrong-sized tool backup in the file-size lane so it publishes failed evidence instead of crashing to exit 2

- Category: Correctness · Severity: Medium · Confidence: High
- Location: `src/docmend/scale_qualification.py:1367-1373` (`run_file_size_matrix` apply branch), `:998` (`_file_size_case_evidence`), `:1815-1824` (`execute_file_size_lane` re-derivation); `src/docmend/scale_evidence.py:643-644` (`_reconcile_file_size_tier`), `src/docmend/scale_qualification.py:2635-2636` (`qualify`)
- Evidence (`scale_qualification.py:1367-1373`): `if (applied_actions != 1 or report.totals.failed or report.totals.not_attempted): reasons.append("conservation-mismatch"); case_failed = True` — counts only, never backup size; while (`:998`) `backup_ok = recipe.preservation == "external" or backup_bytes == source_bytes` still drives `case.passed = False`.
- Problem: for a `preservation="tool"` case where apply completes cleanly but the product writes a wrong-sized backup, `case.passed` becomes False via `backup_ok` with **no** `OutcomeReason` ever appended. `select_evidence_outcome([])` therefore returns `passing`, `ScaleEvidence` construction reaches `_reconcile_file_size_tier`, which raises `ValueError` ("complete file-size evidence requires every case to pass", `scale_evidence.py:643-644`). That ValueError escapes `_publish_execution` (its outer block is try/finally with no except) and is caught by `qualify`'s `except (OSError, ValueError)` (`:2635-2636`), mapped to `QualificationInputError` → **exit 2 (bad invocation)**. A genuine product backup defect is thus reported as an invocation error with no evidence document published and no diagnosable reason. `backup_ok` is the only `case.passed` contributor lacking a reason path; the writer's own `_backup_object_findings` checks regular-file/no-symlink but never size, so the path is reachable. Verified end-to-end by the verifier pass; no existing test contradicts it.
- Fix: (1) in `run_file_size_matrix`'s apply branch (`src/docmend/scale_qualification.py`, after `backup_bytes` is computed near line 1373), add: when `recipe.preservation == "tool"` and `backup_bytes != recipe.size_mib * 1024**2`, append `"conservation-mismatch"` to `reasons` and set `case_failed = True`. (2) Add a `has_trustworthy_backup_failure()` method to `FileSizeCaseEvidence` (`src/docmend/scale_evidence.py`) returning True when the case is trustworthy and its backup check failed, and OR it into `execute_file_size_lane`'s conservation re-derivation (`scale_qualification.py:1819`) so an interrupted/rebuilt checkpoint classifies identically. The failure then routes to `status="failed"` with reason `conservation-mismatch`, exit 1, evidence published.
- Verification: add a test with a `FileSizeRuntime` double whose apply produces an undersized backup for a tool-preservation case; assert `qualify(...)` yields exit code 1, `evidence_published is True`, published `status == "failed"` and `outcome_reason == "conservation-mismatch"` — not a raised `QualificationInputError`; `uv run pytest tests/test_scale_file_size.py tests/test_scale_qualification.py`.
- Dependencies: none; F-015 builds on this · Effort: M

#### F-015 — Convert evidence-model construction failures to a published harness error instead of exit 2

- Category: Architecture · Severity: Low · Confidence: Medium
- Location: `src/docmend/scale_qualification.py:2437-2444` (`_evidence` call inside `_publish_execution`), `:2635-2636` (`qualify`)
- Evidence (`scale_qualification.py:2635-2636`): `except (OSError, ValueError) as exc:` / `raise QualificationInputError(str(exc))`
- Problem: `ScaleEvidence`'s after-validators raise `ValueError` whenever `select_evidence_outcome` and the model validators disagree — F-014 is one concrete trigger, but any future divergence takes the same path: a substantive verdict-construction failure is mislabeled "bad invocation" (exit 2) and nothing is published. The generic `except (OSError, ValueError)` in `qualify` conflates argument/OS input errors with execution-time model failures.
- Fix: in `src/docmend/scale_qualification.py`, wrap the `_evidence(...)` construction in `_publish_execution` (and its acceptance-path reuse) in a handler that converts a pydantic `ValidationError`/`ValueError` into a distinct harness-error outcome with exit code 1 and `evidence_published=False`, leaving `qualify`'s `except (OSError, ValueError)` to genuine input errors.
- Verification: force a selector/model disagreement (the F-014 fixture, with the F-014 fix temporarily reverted, or a synthetic monkeypatch of `select_evidence_outcome`) and assert the process returns 1, not 2; `uv run pytest tests/test_scale_qualification.py`.
- Dependencies: blocked by F-014 (land F-014 first; F-015 is the belt-and-braces layer) · Effort: S

#### F-016 — Delete the dead helpers `is_binding_filesystem`, `fit_peak_rss_slope`, and `MemoryPoint`

- Category: Structure · Severity: Low · Confidence: High
- Location: `src/docmend/scale_resources.py:840-844` (`is_binding_filesystem`); `src/docmend/scale_evidence.py:194-196` (`MemoryPoint`), `:1012-1032` (`fit_peak_rss_slope`)
- Evidence: `grep -rn "is_binding_filesystem\|fit_peak_rss_slope\|MemoryPoint" src/ scripts/` shows each symbol defined once with zero production callers (references exist only in `tests/test_scale_resources.py` and `tests/test_scale_evidence.py`). `compare_reference_environment` re-implements the binding-filesystem test inline (`scale_resources.py:1109-1114`); production threshold derivation uses `derive_thresholds` → `_project_stage_peak`/`_stage_growth`, not the least-squares fit.
- Problem: two parallel, unused implementations invite silent drift — and they have already diverged in both directions: `is_binding_filesystem` checks `REJECTED_NETWORK_FILESYSTEMS` which the inline copy does not, while the inline copy checks flag-set equality and `storage_class == "local-ssd"` which the helper does not. Dead code with green tests reads as load-bearing when it is not.
- Fix: delete `is_binding_filesystem` from `src/docmend/scale_resources.py`, and `fit_peak_rss_slope` plus `MemoryPoint` from `src/docmend/scale_evidence.py`, together with their tests in `tests/test_scale_resources.py` and `tests/test_scale_evidence.py`. Do **not** instead wire `is_binding_filesystem` into `compare_reference_environment` — the two checks differ in both directions, so substituting the helper would change behavior (verifier-confirmed).
- Verification: `grep -rn "is_binding_filesystem\|fit_peak_rss_slope\|MemoryPoint" src/ scripts/ tests/` returns nothing; full gate (`uv run coverage run -m pytest && uv run coverage report`) stays green and above 85%.
- Dependencies: none · Effort: S

#### F-017 — Remove the unconsumed diagnostic swap-counter API (`parse_vmstat_swap`, `swap_counter_delta`, `SwapCounters`)

- Category: Structure · Severity: Low · Confidence: Medium
- Location: `src/docmend/scale_resources.py:399-408` (`SwapCounters`/`parse_vmstat_swap` area, definitions at :400), `:1171-1193` (`swap_counter_delta`)
- Evidence: all three symbols have zero production references (tests-only, `tests/test_scale_resources.py`); the stage supervisor parses swap via its own `_parse_vm_swap` (`scale_stage.py:778`, consumed at `:908`), and nothing collects or surfaces a vmstat delta.
- Problem: the diagnostic swap-page evidence these helpers compute is never actually gathered, so they are either a wiring gap or dead code. Recommendation: they are dead — the binding swap contract is fully served by `_parse_vm_swap`, and no diagnostic evidence field expects pswpin/pswpout — so remove them. If the owner intended vmstat deltas in diagnostic evidence, that is a deliberate feature addition, not a review fix.
- Fix: delete `SwapCounters`, `parse_vmstat_swap`, and `swap_counter_delta` from `src/docmend/scale_resources.py` and their tests from `tests/test_scale_resources.py`.
- Verification: `grep -rn "parse_vmstat_swap\|swap_counter_delta\|SwapCounters" src/ scripts/ tests/` returns nothing; full gate stays green.
- Dependencies: none · Effort: S

#### F-018 — Remove the unreachable `st_mode` truthiness guard in `_real_repository`

- Category: Structure · Severity: Low · Confidence: High
- Location: `src/docmend/scale_build.py:534-535`
- Evidence (`scale_build.py:534-535`): `if not metadata.st_mode:` / `raise BuildContractError("candidate repository identity is unavailable")` — where `metadata = repository.lstat()` (line 528).
- Problem: `st_mode` for any existing lstat'd inode always includes file-type bits, so the branch is unreachable dead code. The intended failure modes are already handled: a failed lstat/resolve raises `OSError` (caught at 530-531) and the symlink/non-directory checks at 532 validate the type. The dead branch misleads readers into thinking `st_mode == 0` is a reachable state.
- Fix: delete lines 534-535 of `src/docmend/scale_build.py`.
- Verification: `uv run ruff check .` and `uv run pytest tests/test_scale_build.py` stay green; coverage no longer reports the dead branch.
- Dependencies: none · Effort: S

### Test fixtures and scripts

#### F-019 — Pin Faker to an exact version so the fixture generator's determinism claim holds across lock upgrades

- Category: Testing · Severity: Low · Confidence: Medium
- Location: `pyproject.toml:34` (dependency floor); claim at `scripts/gen_weird_corpus.py:15-16`
- Evidence (`pyproject.toml:34`): `"faker>=40.28.1",` — versus (`gen_weird_corpus.py:15-16`): "Re-run freely: every byte here is deterministic (fixed Faker seed, fixed / Random seed), so a re-run reproduces identical fixture bytes and sidecars."
- Problem: seeded Faker output changes across Faker releases; only `uv.lock` pins 40.28.1 today. A routine `uv lock --upgrade` would silently change every regenerated fixture's bytes while the generator's disposition-level self-verification still passes — the drift is invisible until committed fixtures diverge from a re-run. Reproducibility only; the corpus remains synthetic (C-002 holds).
- Fix: pin the dev dependency exactly — `uv remove --dev faker && uv add --dev 'faker==40.28.1'` (use uv per conventions #1; the `[dependency-groups]` block is the repo's own dependency list, and an exact dev-only pin is not a check-bypass of the standard-owned tool tables, but note the change in the commit message). Alternatively, if the owner prefers the floor, amend the `gen_weird_corpus.py` docstring to state reproduction is version-locked to `uv.lock`'s Faker pin. Prefer the exact pin so regeneration under an upgraded lock fails loudly rather than mutating bytes.
- Verification: `git diff --stat tests/fixtures/weird_documents/` is empty after `uv run python scripts/gen_weird_corpus.py`; `grep -n 'faker==' pyproject.toml` shows the pin.
- Dependencies: none · Effort: S

#### F-020 — Correct the `gen_weird_corpus.py` docstring: the two fixture subtrees are verified separately, not "the entire corpus at once"

- Category: Docs · Severity: Low · Confidence: High
- Location: `scripts/gen_weird_corpus.py:10-13` (claim); `main()` at `:739-744`, `_verify` at `:676-683`, `_floor_fixtures` at `:593-598`
- Evidence (`gen_weird_corpus.py:10-13`): "The verification scans the _entire_ candidate corpus at once, matching exactly / what tests/test_weird_corpus.py does against the committed directory — this is / what catches cross-fixture interactions …"
- Problem: `main()` verifies the top-level fixture list, and `_floor_fixtures()` verifies the encoding-floor matrix in its own separate `TemporaryDirectory` — two isolated scans, never combined. A cross-subtree interaction would not be caught at generation time (none exists today: floor rename targets stay inside `encoding_floor/`). Also, `tests/test_weird_corpus.py` enumerates top-level sidecars with a non-recursive glob while the floor matrix has its own test — so the "matching exactly" claim is wrong in both directions.
- Fix: reword `scripts/gen_weird_corpus.py:10-13` to state that top-level and floor fixtures are each verified within their own subtree, and that the distinct rename-target namespaces are what make separate verification sound. (Optionally add one combined `scan()` over the assembled set to make the stronger claim literally true — but the wording fix alone closes the finding.)
- Verification: re-read the docstring against `main()`; `uv run python scripts/gen_weird_corpus.py` still verifies cleanly.
- Dependencies: none · Effort: S

#### F-021 — Make fixture regeneration prune (or refuse on) orphaned fixtures and sidecars

- Category: Testing · Severity: Low · Confidence: Medium
- Location: `scripts/gen_weird_corpus.py:728-736` (`_write_fixtures`)
- Evidence (`gen_weird_corpus.py:731-734`): `target_dir.mkdir(parents=True, exist_ok=True)` / `(target_dir / fixture.name).write_bytes(fixture.data)` / `sidecar_path.write_text(...)` — the writer only creates/overwrites; nothing removes files the recipe no longer produces.
- Problem: renaming or removing a fixture in the generator leaves its previously committed data file and `.expect.json` sidecar on disk; `tests/test_weird_corpus.py` enumerates committed sidecars by glob, so the stale fixture keeps being asserted against with no generator able to reproduce it. The committed corpus can silently drift out of one-to-one correspondence with the recipe.
- Fix: in `_write_fixtures` (`scripts/gen_weird_corpus.py`), compute the expected set of relative paths (data files + sidecars, per subtree) and either delete any file under the two known fixture subtrees (`tests/fixtures/weird_documents/` top level and `encoding_floor/`) not in that set, or abort with a listing of extras. Restrict deletion strictly to those two subtrees.
- Verification: place a stray file under the corpus directory, run `uv run python scripts/gen_weird_corpus.py`, and confirm it is removed (or the run aborts naming it); `uv run pytest tests/test_weird_corpus.py tests/test_encoding_floor.py` stays green.
- Dependencies: none · Effort: S

### Documentation

#### F-022 — Update README's `verify` section to the v2.0.0 interface: `--plan`, `--out`, and exit 3

- Category: Docs · Severity: Medium · Confidence: High
- Location: `README.md:29-31`; actual interface at `src/docmend/cli.py:1074` (`--plan`), `:1078` (`--out`), `:1143` (read lock → `typer.Exit(3)` via `:505-507`)
- Evidence (`README.md:29`): the heading `docmend verify PATH [--manifest FILE | --run-id ID] [--report FILE]` and (`README.md:31`): "… Exit codes: 0 clean, 1 findings, 2 input error."
- Problem: the README documents the v1.0.x verify. It omits the two headline v2.0.0 plan-aware-verification features — `--plan` (exactly-once plan-coverage certification) and `--out` (guarded, schema-validated verify-report artifact) — and omits exit 3, which verify can now return when the read lock refuses a concurrent run. For the safety-review surface of a data-mutating tool, the human-facing doc misstates the current contract.
- Fix: in `README.md`, change the verify signature (line 29) to `docmend verify PATH [--plan FILE] [--manifest FILE | --run-id ID] [--report FILE] [--out FILE]`; add one or two sentences describing `--plan` coverage certification and `--out` verify-report publication; change the exit-code list (line 31) to "0 clean, 1 findings, 2 input error, 3 safety refusal (concurrent run lock)".
- Verification: `grep -nE '\-\-plan|\-\-out|3 safety refusal' README.md` hits the verify section; cross-check the option list against `grep 'typer.Option' src/docmend/cli.py` within the verify command; `npx prettier --check . && npx markdownlint-cli2 "**/*.md"` stay green (conventions #2).
- Dependencies: none · Effort: S

#### F-023 — Add exit 3 to the scan documentation (README and the command docstring)

- Category: Docs · Severity: Low · Confidence: High
- Location: `README.md:13`; `src/docmend/cli.py:256-257` (scan docstring); lock acquisition at `cli.py:279`
- Evidence (`README.md:13`): "Exit codes: 0 clean, 1 findings (unreadable files were skipped), 2 input error." — while `cli.py:279` acquires the read lock (`_acquire_read_lock(corpus_root, run_id=run_id, command="scan")`) whose `LockHeldError` handler raises `typer.Exit(3)` (`cli.py:505-507`).
- Problem: scan can exit 3 on a concurrent-run refusal, and the CHANGELOG documents that scan and verify share plan's read-lock posture — but neither the README scan section nor the scan docstring lists exit 3 (the README plan section at line 17 does, making this an internal inconsistency).
- Fix: append ", 3 safety refusal (concurrent run lock)" to the exit-code list in `README.md:13` and to the scan command docstring at `src/docmend/cli.py:256-257`.
- Verification: `grep -n '3 safety refusal' README.md src/docmend/cli.py` shows the scan section and docstring; Markdown check contract stays green.
- Dependencies: none · Effort: S

#### F-024 — Update `docs/handoff/architecture.md`'s stale trailer (v1.0.1 / ADRs 0001-0018 / DOCMEND_SCALE narration)

- Category: Docs · Severity: Low · Confidence: High
- Location: `docs/handoff/architecture.md:26-27` (Standing Backlog trailer); `:15` (historical `DOCMEND_SCALE=1` narration)
- Evidence (`architecture.md:26`): "…ADRs 0001–0018 are all accepted…" and (`:27`): "The MS-0..MS-5 ladder is complete and v1.0.1 is released." — versus `docs/STATUS.md:6` ("ADRs 0001-0022") and `pyproject.toml` version `2.0.0`.
- Problem: the file's "Current Shape" section is updated to v2.0.0/DMR-08, but the Standing Backlog trailer still asserts v1.0.1 and ADRs 0001-0018 as the ceiling, predating the entire safety-core and million-file work. The file contradicts itself about which release it describes. Line 15's `DOCMEND_SCALE=1` reference sits inside a dated historical block, so it may stay as history, but the trailer presents itself as current state.
- Fix: update `docs/handoff/architecture.md:26-27` to reference v2.0.0 and ADRs 0001-0022 (matching `docs/STATUS.md:6`), or move the stale text into a dated past-tense milestone block consistent with the rest of the file.
- Verification: `grep -n '0001–0022\|v2.0.0' docs/handoff/architecture.md` returns the updated trailer; no remaining "v1.0.1 is released" line presented as current state.
- Dependencies: none · Effort: S

#### F-025 — Remove the dead `slow` pytest marker whose description references the removed `DOCMEND_SCALE=1` gate

- Category: Convention · Severity: Low · Confidence: High
- Location: `pyproject.toml:88-90`
- Evidence (`pyproject.toml:88-90`): `markers = [` / `"slow: opt-in long-running tests (NFR-001 scale run; also gated on DOCMEND_SCALE=1)",` / `]`
- Problem: no test carries `@pytest.mark.slow` and `DOCMEND_SCALE` appears nowhere in `src/`, `tests/`, or `scripts/` (verified by grep). The in-gate scale test runs unconditionally at 1,000 files and the 100k tier lives in the scheduled workflow, so nothing is silently skipped — but the marker is dead configuration pointing at a removed mechanism. Note: `[tool.pytest.ini_options]` is a standard-owned tool table (conventions #8); removing a repo-specific dead marker entry is not a check-bypass, but record the reason in the commit message.
- Fix: delete the `slow` marker entry from `[tool.pytest.ini_options].markers` in `pyproject.toml` (leaving `markers = []` or removing the key if the standard's template allows).
- Verification: `git grep -n 'slow\|DOCMEND_SCALE' pyproject.toml tests/` shows no orphaned marker/reference; `uv run pytest --collect-only -q` collects cleanly under `--strict-markers`.
- Dependencies: none · Effort: S

#### F-026 — Soften `docs/STATUS.md`'s absolute "no skips" claim (it is conditional on a non-root runner)

- Category: Docs · Severity: Low · Confidence: Low
- Location: `docs/STATUS.md:7`
- Evidence (`STATUS.md:7`): "The current `dev` baseline is 1,726 passing tests with no skips, 89% branch coverage…" — while four tests skip under root: `@pytest.mark.skipif(os.geteuid() == 0, …)` at `tests/test_discovery.py:295`, `tests/test_cli_scan.py:193`, `tests/test_planning.py:408`, `tests/test_cli_plan.py:149`.
- Problem: "no skips" holds on any non-root runner (the normal CI and workstation case) but is conditionally inaccurate — a root container run skips four permission-bit tests. Minor wording precision only.
- Fix: reword `docs/STATUS.md:7` to "…with no skips on a non-root runner (four permission-bit tests skip only as root)…" or equivalent.
- Verification: `uv run pytest -ra -q | tail -3` as non-root shows no skips, matching the reworded claim.
- Dependencies: none · Effort: S

## Remediation Plan

Work the phases top to bottom; findings within a phase are independent unless noted.

1. **Phase 1 — the Medium code defect and its hardening layer:** F-014, then F-015 (F-015 is blocked by F-014).
2. **Phase 2 — user-facing safety-surface documentation:** F-022, F-023 (same files, do together).
3. **Phase 3 — writer/lock/verify robustness hardening:** F-007, F-006, F-008, F-005, F-009, F-010, F-011, F-012.
4. **Phase 4 — core read-layer corrections:** F-001, F-002, F-004.
5. **Phase 5 — dead code and convention sweep:** F-016, F-017, F-018, F-013, F-025.
6. **Phase 6 — fixture/tooling reproducibility:** F-019, F-021, F-020.
7. **Phase 7 — documentation staleness and the performance decision:** F-024, F-026, F-003 (F-003 may be closed as an accepted tradeoff instead of implemented — the finding states both paths).

After each phase, run the full gate (`uv run ruff format --check . && uv run ruff check . && uv run basedpyright && uv run coverage run -m pytest && uv run coverage report && uv run pip-audit`) plus the Markdown check contract for phases touching `.md` files (`npx prettier --check . && npx markdownlint-cli2 "**/*.md"`).

## Open Questions

### OQ-1 — What should verify do with a top-of-file `---` fence pair whose content is not a YAML mapping?

Today, a `.md` document that merely begins with a `---` thematic break and contains a later `---`/`...` line is treated by `extract_frontmatter` (`src/docmend/frontmatter.py:58-83`) as having a frontmatter block, and the non-mapping content is reported as a verify finding ("frontmatter is not a YAML mapping" — reproduced during review). Tradeoff: **lenient** (treat a non-mapping block as "no frontmatter", which adr-0011 says is legal) eliminates spurious findings on ordinary legacy body text that happens to start with a horizontal rule — but it would also silently pass a genuinely malformed emitted-frontmatter block that degraded into a non-mapping, weakening FR-016's backstop. **Strict** (current behavior) surfaces every candidate block but will flag legitimate documents in a corpus where `---` separators are common. The right choice depends on how prevalent leading thematic breaks are in the real library — an owner call, ideally recorded as an adr-0011 amendment plus a pinning fixture either way.

### OQ-2 — Should a reference-mismatched (non-binding-environment) scale run ever be classified `failed` by threshold evaluation?

`scale_qualification.py:2013-2014` marks a run `reference-mismatch` (→ diagnostic) when the environment does not match the reference, but `:2231-2248` still evaluates the frozen RSS thresholds for scheduled/release tiers, and a `threshold-exceeded` reason outranks `reference-mismatch` in `select_evidence_outcome` — flipping the run from `diagnostic` to `failed`. Tradeoff: **suppressing** threshold evaluation under reference mismatch keeps diagnostic runs diagnostic (RSS numbers from a non-reference environment are not meaningfully comparable to the frozen limits), but loses an early warning when a diagnostic run blows far past the budget; **current behavior** is fail-safe (never a false accept) but can brand a run "failed" on numbers the spec says are only binding on the reference environment. Needs a §17.2/OQ-040-level reading by the owner; either outcome should be pinned by a test.
