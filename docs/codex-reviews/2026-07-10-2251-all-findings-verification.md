# Review Findings Verification — Post-Plan-A

Verification of the [2026-07-10-2034 complete sweep findings](2026-07-10-2034-all-review-findings.md) against `dev` HEAD `24b57bb`, per the urgent task in `docs/TODO.md`. The sweep snapshot predates the entire safety-core Plan A implementation (`66b0140..24b57bb`, landed 21:00–22:40 the same evening), so every verdict below was re-established against current code, not the sweep's line references.

Method: direct inspection of the full Plan A diff (`b9d5195..6ae7547`), two independent targeted code-verification passes over the DMR evidence paths, and a full test-suite run at HEAD (651 passed, 1 skipped — the opt-in scale test).

## Rollout-blocker verdicts

| ID | Sweep status | Verified status at HEAD | Owner |
| --- | --- | --- | --- |
| DMR-01 | High | **Closed by Plan A** | done |
| DMR-02 | High | **Closed by Plan A** (CLI surface) | done |
| DMR-03 | High | Still open | Plan B |
| DMR-04 | High | Still open | Plan B/C |
| DMR-05 | High | Still open | Plan D |
| DMR-06 | High | Still open | Plan C |
| DMR-07 | High | Still open, marginally mitigated | Plan C |
| DMR-08 | High contract failure | Still open | Sub-project 2 |
| DMR-09 | High future-release risk | Still open | Sub-project 3 |

### DMR-01 — closed

`build_plan` now keeps an output ledger (`claimed_outputs`) that reserves every action's effective output path — rename targets AND in-place rewrite paths — so no two actions in one plan can share an output; the second claimant becomes a `collision` skip naming the claimer (`src/docmend/planning.py`). Independently, backup keys are namespaced `{run_id}/{action_seq}/{role}/{relative_path}` and write-once: publication is a no-clobber hardlink, and an occupied key raises `BackupError` (`src/docmend/writer/backup.py`). The sweep's exact reproduction (in-place `a.md` rewrite + `a.txt → a.md` rename sharing one backup key) is impossible at both layers; both claim orderings have regression tests (`tests/test_planning.py::TestCollisions`).

### DMR-02 — closed at the CLI surface

`guard_artifact_destination` (`src/docmend/artifacts.py`) refuses destinations whose lexical entry or resolved referent lands in the corpus (with the per-destination `.docmend/` carve-out), non-regular-file destinations, and aliases of the invocation's input artifacts. It runs before the pipeline on `scan --report`, both `plan` branches (including the shorthand's inventory artifact), and `apply` report+manifest paths; manifests reachable via `--resume-run-id` count as input aliases. Report finalization moved inside the run lock. Staging is randomized `O_EXCL` with cleanup on every unpublished exit, in both the artifact writer and `writer/atomic.py`.

Residual (known, scoped): the guard-to-write window is a TOCTOU — a destination parent swapped to a corpus symlink after preflight is not re-checked at write time. That is DMR-06's class and is Plan C scope, not a Plan A gap.

### DMR-03 — still open

`read_manifest` (`src/docmend/writer/manifest.py:142-171`) still validates line-by-line with no run-level pass for single root, single run, version ceiling (schema pattern `^1\.\d+$` accepts any future minor), sequence integrity, or lifecycle. `_restore_one` (`src/docmend/restore.py:146-287`) reads and mutates recorded paths verbatim with no containment against the recorded `source_root`; the restore lock root comes from `records[0]` alone (`src/docmend/cli.py:424-439`). The containment guard added for apply resume (`apply.py:248-255`) was never extended to restore/verify.

### DMR-04 — still open

Only `rename_and_rewrite` writes a pre-mutation intent (`apply.py:495-512`); pure rewrite and pure rename mutate first and append their only record after (`apply.py:515-522` then `581-593`). Restore mutates before appending inverse evidence (`restore.py:238-266` then `268-284`). Verify and restore both filter to `result == "applied"` and ignore dangling intents (`verify.py:98`, `restore.py:124`).

### DMR-05 — still open

All four false-clean outcomes reproduce in current code: `reconcile_manifest` never reads or hashes backup bytes (`verify.py:88-114`); verify iterates only readable inventory files and exits 0 on zero checked files (`verify.py:43,68`; `cli.py:933-934`); a `fail`-policy mid-plan abort leaves trailing actions in neither outcome nor record set, invisible to `reconcile_report` (`verify.py:117-151`); no root-match check between manifest and PATH argument; no `verify --plan` interface.

### DMR-06 — still open

Apply hashes and containment-checks a pathname (`apply.py:372-385`), then later mutates whatever that name resolves to (`apply.py:514-525`) with no fd pinning, `O_NOFOLLOW`, or commit-time re-hash. Restore is symmetric (`restore.py:84-102` vs `238-258`).

### DMR-07 — still open, marginally mitigated

The collision policy and overwritten-target backup are evaluated at apply time from a fresh `target.exists()` (`apply.py:396-446`), and Plan A's write-once keys removed the backup-collision failure mode — so with tool backups configured, a late-appearing target IS now preserved. The open remainder: the gate's preservation contract is never re-asserted at commit, and when `backup_root is None` (external/git preservation declared) a late target is clobbered with only `overwritten_sha` recorded and no recoverable bytes. The action-time preservation invariant remains Plan C scope.

### DMR-08 — still open

Corpus-wide collections persist (`discovery.py:222-229`, `planning.py:189-190`); `ParallelConfig` has zero runtime consumers; the scale test still budgets 10 KiB/file (`tests/test_scale.py:51`) and still asserts one manifest record per applied action (`test_scale.py:186`), which manifest 1.3's intent+terminal records violate — the staleness is unchanged and, as already planned, gets mechanically fixed with Plan B's manifest 2.0.

### DMR-09 — still open

`release.yml` still publishes on any `v*.*.*` tag with no main-ancestry, signature, or package-version-equality proof; `actions/checkout@v7` remains a mutable tag inside the write-capable job (first-party `actions/*` on tags is a documented deliberate choice — the finding stands as accepted-risk-vs-hardening for sub-project 3).

## Medium-theme verdicts

| Theme | Verified status at HEAD |
| --- | --- |
| Planning mints a new UUID per document (no stable identity) | Still open (`planning.py:178,374`) |
| JSON readers: duplicate keys, unenforced aggregates, future minors accepted | Still open (bare `json.loads` everywhere; only apply's plan read guards minors) |
| Public write engines callable outside CLI lock/gate coordination | Still open (`execute_plan`, `run_restore` are plain exports) |
| Fixed staging names block retry after hard kill | **Fixed by Plan A** (randomized EEXIST-retried staging, `atomic.py:45-73`, `artifacts.py:169-178`) |
| Disk preflight double-counts shared filesystems | Still open (`gate.py:162-215`, two independent `shutil.disk_usage` checks) |
| Timeouts treated as success; targeted restore silent no-op on unmatched IDs | Still open (both: `discovery.py:313-323`/`planning.py:386-403` skip-and-continue; `restore.py:121-125` + `cli.py:827-833` exit 0) |
| Logs: no terminal event contract, 0644 under 022 umask, no sink-level redaction | Still open (`observability.py:98`, caller-obligation comment only) |

The sweep's "Corrected Or Non-Applicable" section needed no re-verification — none of its five entries concern code that changed.

## Plan A regression review

- **Full suite green at HEAD**: 651 passed, 1 skipped. The two failures visible in stale session tooling (`test_schemas.py` frontmatter schema, `test_cli_scan.py` exclude-flag skips) do not reproduce — pre-Plan-A cache, not regressions.
- **Behavior change from the output ledger is intended and tested**: plans over corpora where a rename target coincides with an in-place rewrite path now emit one action plus one `collision` skip (deterministic lexicographic first-claimant) instead of two actions. This counts toward `fail`-policy exit accounting, matching G-005.
- **One false alarm refuted during verification**: `apply.py:542`'s unparenthesized `except WriteError, OSError:` was flagged as a `SyntaxError` — it is deliberate PEP 758 syntax, valid on the project's Python 3.14 floor, carries an in-code comment anticipating the misread, and the green suite proves the module parses.
- **No interaction found** between Plan A's changes (planning ledger, backup keys, artifact guard, staging) and the DMR-03/04/05 code paths — the restore/verify/manifest-read surfaces are byte-untouched by Plan A, so the remaining verdicts carry no hidden coupling to the landed work.

## Conclusion

The sweep's consolidated findings remain accurate at HEAD with exactly the closures the changelog claims: DMR-01 and DMR-02 closed (plus the staging-residue medium theme), everything else still open with scope unchanged. No finding invalidates or is invalidated by the landed Plan A work, and no re-planning of Plans B, C, or D is needed — the approved design's decomposition still matches the verified defect set.
