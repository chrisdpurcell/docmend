# Changelog

All notable changes to docmend are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 2026-07-19

Remediation of the 2026-07-19 comprehensive project review (`docs/fable-review/2026-07-19-docmend-review.md`): 26 findings fixed, none Critical or High.

### Fixed

- File-size qualification: a wrong-sized tool backup now publishes failed evidence with reason `conservation-mismatch` and exit 1 instead of aborting as an exit-2 invocation error, and an evidence-model construction failure is a distinct harness error at exit 1, no longer conflated with input errors.
- `verify` flags an `applied` manifest record carrying no recorded after-hash as a `hash` finding instead of silently skipping it.
- Apply re-checks `st_nlink` at the commit boundary and skips `hard-link-alias` when a source gained a hard link between plan and apply (hardening on top of the DEV-001 plan-time gate), and containment-checks source/target paths before opening them, closing an out-of-root read window through a swapped parent symlink.
- Run-lock acquisition and the restore write context release the lock when holder-metadata write or context construction fails; source parent directories are fsync'd after rename unlinks; replaced logging handlers are closed on reconfigure.
- `restore --id` reports "matched only non-restorable (failed) records" instead of "no match" when the selector hit only failed-lifecycle records.
- Configuration files saved with a UTF-8 BOM now load (`utf-8-sig`); frontmatter fence scanning is LF-only, so embedded Unicode line separators can no longer close a block early; planning a pre-1.1 inventory with an unknown detection fact skips as `low-confidence-encoding`, not `binary-suspect`.

### Changed

- Scan reuses a 64 KiB head buffer for encoding detection on files that fit it entirely, halving reads for small legacy files; larger files keep the full-file detection path.
- The weird-corpus generator pins `faker==40.28.1` exactly, documents its per-subtree verification accurately, and prunes orphaned fixtures/sidecars on regeneration.
- README documents the v2 `verify` interface (`--plan`, `--out`) and the exit-3 concurrent-run refusal for `scan` and `verify`.

### Removed

- Dead scale-harness helpers (`is_binding_filesystem`, `fit_peak_rss_slope`, `MemoryPoint`, `MemoryFit`, `SwapCounters`, `parse_vmstat_swap`, `swap_counter_delta`), an unreachable repository-identity guard in `scale_build`, and the unused `slow` pytest marker.

## [2.0.0] - 2026-07-18

Safety-core remediation, plans A–D (spec revs 0.26–0.29; 2026-07-10 comprehensive review findings DMR-01..07; ADRs 0019–0021).

### Changed — bounded-linear scale contract (DMR-08)

- Removed the unimplemented `parallel.*` configuration surface and advanced plan artifacts to schema 2.0, rejecting legacy configuration and plans before operational side effects.
- Added the always-on 1,000-file source-tree guard, installed-wheel qualification and strict public evidence contracts, aggregate stage liveness, filesystem-aware capacity preflight, and the weekly/manual 100,000-file diagnostic workflow.
- Accepted the 100,000-file pilot, the 12-case file-size matrix through 100 MiB, and the clean-HEAD one-million-file release qualification. The final release run completed in 25,629.225 seconds with zero child swap, exact corpus/finding conservation, a 20,825,497,600-byte maximum stage RSS, and passing absolute, slope, linearity, reference, and 12-hour runtime verdicts.

### Fixed — scale telemetry

- Stage supervision now samples a recoverable post-sample `/proc/<pid>/status` gap before polling the child, preserving terminal zombie `VmSwap` evidence that `Popen.poll()` could otherwise reap. Invalid or unreadable post-sample telemetry coinciding with exit fails closed instead of retaining an earlier peak as complete evidence.

### Changed — plan-aware verification (plan D)

- `verify --plan` now certifies exactly-once plan coverage across repeatable `--manifest`, `--report`, and `--run-id` evidence, ordering report-only, manifest-only, resumed, and restore attempts from durable lineage instead of argument order.
- Verification closes the confirmed false-clean set: unreadable/timeout discovery evidence and zero-checked runs, wrong manifest roots, incomplete or restored lifecycle states, missing or corrupt source/overwrite backups, output-hash drift, missing apply reports after mutation evidence, and uncovered or uncertified plan actions are findings (exit 1). Structural artifact contradictions remain input errors (exit 2); restore runs do not require apply reports.
- `verify --out FILE` optionally publishes a guarded, schema-validated verify-report. Omitting it preserves the no-result-artifact behavior; an ordinary existing output is replaced, while corpus, input-alias, and non-regular destinations are refused before scanning.
- Standalone `scan` and `verify` now share `plan`'s read-only run-lock posture: a concurrent docmend run using the same resolved corpus-root key is refused (exit 3), while lock-creation failure warns and continues per OQ-036. Lock keys are exact resolved roots, so a subtree key does not contend with an ancestor apply key.

### Changed — manifest 2.0 (plan B, BREAKING)

- **Manifest format 2.0 (adr-0019, clean break):** line 1 is now a header envelope carrying the run's identity, kind (`apply`/`restore`), resolved source root, tool-backup root, plan hash, and attempt lineage; records drop the per-line `source_root` and gain restore lineage (`undoes_action_id`/`undoes_run_id`) plus the durable object identities post-kill adjudication verifies against. Any 1.x manifest is rejected with a message directing pre-2.0 restores to docmend 1.0.2. There is deliberately no 1.x read path.
- **Every mutation is journaled (DMR-04):** every kind — rewrite, rename, rename_and_rewrite, and every restore inverse — appends a fsync'd `intent` record (with exact `(st_dev, st_ino)` identities, captured via a new staged-write publish) before any corpus name is touched, and a terminal after. Replacement outputs are staged before the intent so the published inode's identity is knowable pre-mutation and survives a kill.
- **Manifest consumers validate before trusting (DMR-03):** one validated set/chain model — header presence and version, single run with contiguous seq, lifecycle legality (provisional standalone terminals proven by chain-scope closure), source-root containment, and the complete BackupStore trust boundary (derivable keys, regular files, no symlinked components) — runs before resume, restore, or verify touches any recorded path. Containment violations are safety refusals (exit 3); malformed input is exit 2.
- **One lifecycle reducer, shared adjudication:** resume and restore (and verify, in plan D) consume the same `reduce_lifecycle` fold — chain order then seq, never wall-clock — and the same crash-state adjudication table, with identity predicates that refuse a same-bytes replacement under a different inode. An interrupted restore now CONVERGES on re-run instead of tripping its own collision preflight; a resume can adopt a completed-but-unrecorded mutation for every kind.
- **Attempt lineage (report 2.0):** manifests and reports both carry a discriminated `prior_attempt` edge and reports carry their closed manifest's hash, so interrupted-attempt chains stay connected whichever artifact a crash erased. Apply resume builds one deterministic attempt graph over all supplied evidence (`--resume-run-id` resolves both sidecars; new repeatable `--prior-report` names relocated or report-only predecessor reports) with a no-gap rule; a report recording a closed manifest whose file is missing is refused as missing mutation evidence, never mistaken for a mutation-free attempt.
- Reports partition every plan action exactly once: a `fail`-policy abort's unreached actions get an explicit `not-attempted` outcome and totals entry (report schema 2.0).
- `restore --manifest`/`--run-id` are now repeatable and combinable (a multiply-resumed run restores as one chain); `restore --id` values matching nothing exit 1 with a finding instead of reporting an all-zero success.
- `scan` and `plan` runs containing watchdog-timeout skips now exit 1 (partial result), matching the unreadable-skip posture.

### Changed — commit boundary (plan C, BREAKING for library callers)

- **Every mutation commits against the object it validated (adr-0020, DMR-06):** apply and restore read each file's bytes exactly once through an `O_NOFOLLOW` descriptor whose `(st_dev, st_ino)` identity is captured and journaled. Immediately before every publish and unlink, the pathname is `lstat`-compared against that identity and containment is re-resolved, including staged temporary files, absent destinations' parent chains, and the survivor required before a destructive second step. Pre-mutation interference skips as `external-interference`; an unprovable post-mutation intermediate retains every possibly-last copy and leaves its intent for adjudication. The `lstat`-to-rename interval remains the stated POSIX residual.
- **Overwrite preservation is an action-time invariant (DMR-07):** a target discovered at action time is clobbered only under an active byte-preserving strategy and is backed up through its own descriptor with an identity check immediately before replacement. A target appearing later publishes no-clobber and skips as `collision-unpreserved`, never silently overwriting. The gate's plan-time overwrite check remains early feedback.
- **Failed terminals are proofs (spec §10.4):** a `failed` manifest terminal is appended only when the pre-action state is proven. Rollbacks are identity-checked, replacement writes stage first, no rollback removes the last surviving name of a validated object, and an unprovable intermediate keeps its journal intent for resume or restore adjudication.
- **Post-crash adjudication uses the same boundary:** `finish-remaining` steps re-resolve containment at the mutation instant, distinguish unobservable names from absence, use stage-first replacement writes, and preserve the mode captured with identity and bytes through one descriptor.
- **Read/write entrypoint split (F8):** `preview_plan` and `preview_restore` are structurally read-only. `execute_plan` and `run_restore` now require a sealed `WriteSafetyContext` whose factories acquire the canonical run lock, evaluate the apply gate or validate the restore chain, guard artifact destinations, and attest the exact run and destinations. Apply authority comes from one factory-read plan snapshot and its embedded config; retained plan/config payloads are immutable serializations reconstructed as fresh private models. Restore consumes a factory-validated chain frozen to its leaves. Library callers can no longer substitute a config, plan, chain, effective options, artifact identity, root, or destination after the ceremony. The CLI surface is unchanged.
- **Dry-run and refusal artifacts preserve prior files:** dry-run reports publish no-clobber, and a gate-refused apply publishes its refusal report inside the run lock without replacing a pre-existing artifact.
- **The manifest header records effective excludes:** restore licenses the `.docmend/` artifact carve-out against the patterns that governed the apply run, because per-invocation replacement flags make that set unreconstructable later.
- New skip reasons: `external-interference` and `collision-unpreserved`. No new exit codes were added; the unreleased manifest 2.0 header gained its required `effective_excludes` field without another schema-version bump.

### Fixed

- A manifest containing an ordinary pre-mutation failure (a staging, stat, or backup error that aborted an action before any corpus name was touched) is no longer rejected wholesale by the chain reader, which made such runs unresumable and unrestorable. The closure rule had read "standalone terminal" as covering `failed` records, but the design's own clause — a `failed` with no intent anywhere asserts no mutation occurred — makes them the legal pre-mutation shape; only adoption (`applied`) terminals must close a dangling intent. (Found verifying plan C review round 2, CR-NEW-002.)
- One plan can no longer overwrite its own recovery backups (DMR-01): planning reserves every action's effective output path — in-place and rename alike — so colliding actions skip at plan time, and backups are stored under write-once keys namespaced by run, action, and role, so even a crafted plan cannot make two byte streams share a key.
- docmend's own artifacts can no longer destroy corpus inputs (DMR-02): every `scan --report`, `plan --out`, and `apply --report` destination passes a source-aware guard before the pipeline runs — both the directory entry publication replaces and its resolved referent must be outside the corpus, in-corpus destinations are refused (exit 3) except destinations under the canonical `.docmend/` root that the effective excludes still cover, and destinations aliasing an invocation's input artifacts are refused outright.
- Staging names are randomized (`O_EXCL`, collision-retried) for both corpus writes and JSON artifacts: kill residue no longer blocks retries, the predictable `<name>.tmp` truncation target is gone, artifact staging cleans up on every failure class including serialization errors, and artifact file modes are unchanged (umask-derived, as before).
- The apply report now finalizes while the run lock is held, so a run's artifacts and corpus effects commit under one coordination boundary.

## [1.0.2] - 2026-07-07

Safety hardening from the 2026-07-07 cross-repo alignment review, ahead of broad real-library mutation. The repository boundary with the workstation-side tooling is recorded in `docs/adr/adr-0018-doc-processing-repository-boundary.md` (accepted 2026-07-07).

### Fixed

- Planning no longer lets `rename.on_collision = "overwrite"` merge two same-run actions onto one target (e.g. `a.TXT` + `a.txt` both planning `a.md`): a plan-internal claim conflict now always skips the later action with a collision reason, under every policy. Overwrite continues to apply only to pre-existing targets.
- A hard kill inside a `rename_and_rewrite`'s window (target published, source not yet unlinked, or mutation done but unrecorded) no longer leaves the corpus mutated without manifest evidence. Apply appends a write-ahead `intent` record (manifest schema 1.2 → 1.3) before the first step; resume reconciles a dangling intent from disk state — completing the unlink, adopting the finished mutation into the resuming run's manifest, re-executing when the publish never happened, or failing ERR-002 on external interference. Restore and verify are unaffected (they act on `applied` records only).

### Changed

- Scan prunes excluded directories (`.git/`, `.venv/`, `node_modules/`, `.docmend/`, and any configured directory pattern) from the walk instead of descending and recording a per-file `excluded` skip for everything inside. Selection is unchanged; inventories are quieter and large-tree scans faster. Per-file skip records remain for file-pattern excludes.
- The release workflow's `setup-uv` action is SHA-pinned like the check workflow's (it publishes artifacts with `contents: write`).
- Documentation drift sweep: the restore runbook now states that a restore's own inverse manifest is re-reversible for renames only (inverse records carry no backup bytes); schema contract table, ADR backlog, and spec current-state brought up to date.

## [1.0.1] - 2026-07-07

Fixes the partial-undo trap reported in [#15](https://github.com/chrisdpurcell/docmend/issues/15): when an apply run satisfies the write gate with a declared external preservation (no `--backup-dir`), its manifest records content mutations as hashes only, so `docmend restore` can undo renames but not rewrites — and users discovered that only at restore time.

### Changed

- `apply --write` now warns at run time when a run with content rewrites takes no tool backups: restore for that run will be renames-only, and content recovery relies on the declared preservation.
- `restore` states the run's capability up front (`restore capability: renames-only — N content mutation(s) ...`) instead of leaving it to per-row skips; wrapper scripts can derive the same fact from the manifest (an applied non-rename record with a null `backup_path`).
- The `no-backup` skip detail now names the declared preservation as the recovery path.
- README and the restore runbook document how restore capability follows from the apply-time preservation choice.

Journaled originals (issue suggestion 3 — storing pre-mutation bytes even under external preservation) is deferred as capability WH-009 in the spec.

## [1.0.0] - 2026-07-07

First release. docmend normalizes, repairs, and converts legacy `.txt`/`.html` document collections into clean UTF-8, LF-only text with mechanical Markdown renames, from a single file up to libraries of 100,000+ files.

### Added

- `docmend scan PATH`: read-only discovery. Walks a file or tree, classifies encoding (BOM, strict UTF-8, ASCII, charset detection for legacy encodings), takes a newline census, records hard-link groups and symlinks, and writes a schema-validated inventory artifact.
- `docmend plan`: turns an inventory into a reviewable plan of per-file transforms (encoding conversion, newline normalization, whitespace cleanup, `.txt` to `.md` renames) with risk-classified skips and full decision provenance. Accepts a `PATH` shorthand that scans first.
- `docmend apply PLAN`: executes a reviewed plan. Dry-run by default; real writes require `--write` and pass a safety gate that demands a byte-preserving strategy (tool backups via `--backup-dir`, a declared `--preserved-by git|external`, or the single-file `--allow-no-backup` opt-in). Every mutation is an atomic replace recorded in an append-only, per-record-fsynced manifest.
- `docmend restore`: replays a manifest newest-first to undo an apply run, byte-identical, with `--id` for selective restore.
- `docmend verify PATH`: read-only output checks. UTF-8 decodability, LF-only endings, frontmatter schema validity where present, manifest hash reconciliation, and report/manifest accounting.
- Resume: `docmend apply --resume-run-id ID` (or `--resume-manifest FILE`, both repeatable) continues an interrupted run. Completed files are verified against the manifest and skipped; files changed outside docmend fail loudly rather than being rewritten.
- Idempotent re-runs: applying the same plan twice changes nothing, and re-planning over converted output produces an empty plan.
- Concurrency guard: a run lock keyed on the source tree makes a second concurrent plan, apply, or restore refuse instead of racing.
- Five pinned JSON Schemas (inventory, plan, report, manifest, frontmatter) ship inside the package as the durable artifact contract.
- Scale-tested: the seeded 100,000-file synthetic-corpus test completes in about six minutes with peak memory under 500 MiB.

[2.0.0]: https://github.com/chrisdpurcell/docmend/releases/tag/v2.0.0
[1.0.2]: https://github.com/chrisdpurcell/docmend/releases/tag/v1.0.2
[1.0.1]: https://github.com/chrisdpurcell/docmend/releases/tag/v1.0.1
[1.0.0]: https://github.com/chrisdpurcell/docmend/releases/tag/v1.0.0
