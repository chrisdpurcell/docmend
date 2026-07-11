# Changelog

All notable changes to docmend are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Safety-core remediation, plans A and B of four (spec rev 0.26/0.27; 2026-07-10 comprehensive review findings DMR-01..DMR-04; ADRs 0019–0021). Targets the eventual v2.0.0.

### Changed — manifest 2.0 (plan B, BREAKING)

- **Manifest format 2.0 (adr-0019, clean break):** line 1 is now a header envelope carrying the run's identity, kind (`apply`/`restore`), resolved source root, tool-backup root, plan hash, and attempt lineage; records drop the per-line `source_root` and gain restore lineage (`undoes_action_id`/`undoes_run_id`) plus the durable object identities post-kill adjudication verifies against. Any 1.x manifest is rejected with a message directing pre-2.0 restores to docmend 1.0.2. There is deliberately no 1.x read path.
- **Every mutation is journaled (DMR-04):** every kind — rewrite, rename, rename_and_rewrite, and every restore inverse — appends a fsync'd `intent` record (with exact `(st_dev, st_ino)` identities, captured via a new staged-write publish) before any corpus name is touched, and a terminal after. Replacement outputs are staged before the intent so the published inode's identity is knowable pre-mutation and survives a kill.
- **Manifest consumers validate before trusting (DMR-03):** one validated set/chain model — header presence and version, single run with contiguous seq, lifecycle legality (provisional standalone terminals proven by chain-scope closure), source-root containment, and the complete BackupStore trust boundary (derivable keys, regular files, no symlinked components) — runs before resume, restore, or verify touches any recorded path. Containment violations are safety refusals (exit 3); malformed input is exit 2.
- **One lifecycle reducer, shared adjudication:** resume and restore (and verify, in plan D) consume the same `reduce_lifecycle` fold — chain order then seq, never wall-clock — and the same crash-state adjudication table, with identity predicates that refuse a same-bytes replacement under a different inode. An interrupted restore now CONVERGES on re-run instead of tripping its own collision preflight; a resume can adopt a completed-but-unrecorded mutation for every kind.
- **Attempt lineage (report 2.0):** manifests and reports both carry a discriminated `prior_attempt` edge and reports carry their closed manifest's hash, so interrupted-attempt chains stay connected whichever artifact a crash erased. Apply resume builds one deterministic attempt graph over all supplied evidence (`--resume-run-id` resolves both sidecars; new repeatable `--prior-report` names relocated or report-only predecessor reports) with a no-gap rule; a report recording a closed manifest whose file is missing is refused as missing mutation evidence, never mistaken for a mutation-free attempt.
- Reports partition every plan action exactly once: a `fail`-policy abort's unreached actions get an explicit `not-attempted` outcome and totals entry (report schema 2.0).
- `restore --manifest`/`--run-id` are now repeatable and combinable (a multiply-resumed run restores as one chain); `restore --id` values matching nothing exit 1 with a finding instead of reporting an all-zero success.
- `scan` and `plan` runs containing watchdog-timeout skips now exit 1 (partial result), matching the unreadable-skip posture.

### Fixed

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

[1.0.2]: https://github.com/chrisdpurcell/docmend/releases/tag/v1.0.2
[1.0.1]: https://github.com/chrisdpurcell/docmend/releases/tag/v1.0.1
[1.0.0]: https://github.com/chrisdpurcell/docmend/releases/tag/v1.0.0
