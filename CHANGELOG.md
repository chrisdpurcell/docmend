# Changelog

All notable changes to docmend are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
