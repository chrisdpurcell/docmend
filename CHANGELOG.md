# Changelog

All notable changes to docmend are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.1]: https://github.com/chrisdpurcell/docmend/releases/tag/v1.0.1
[1.0.0]: https://github.com/chrisdpurcell/docmend/releases/tag/v1.0.0
