# docmend

Python tool to normalize, fix, convert, manage, and maintain large libraries of text and markdown documents.

> **Status:** feature-complete for v1. The design is complete (see [`docs/specs/docmend.md`](docs/specs/docmend.md)) and the whole pipeline is live: `docmend scan` inventories a file or directory tree read-only, `docmend plan` turns that inventory into a reviewable plan, `docmend apply` executes a reviewed plan (dry-run by default, gated writes, atomic mutation, a reversible manifest) and survives interruption — `apply --resume-run-id`/`--resume-manifest` completes an interrupted run without redoing finished work — `docmend restore` undoes an apply run, and `docmend verify` checks converted output read-only. Re-runs are idempotent, and the pipeline is scale-tested against a 100,000-file synthetic corpus within a bounded memory ceiling.

## Commands

All commands work on a single file as well as a directory tree — the pipeline scales down without extra setup. Run artifacts (inventory, plan, report, manifest, log) default into `./.docmend/` in the invoking directory, keyed by run ID.

### `docmend scan PATH`

Inventory PATH read-only into a structured, schema-validated artifact: encoding facts (BOM, UTF-8 validity, legacy-encoding detection), newline census, hard-link and symlink records, and skip records for unreadable files. `--report FILE` relocates the artifact; `--include`/`--exclude` replace the configured glob lists. Exit codes: 0 clean, 1 findings (unreadable files were skipped), 2 input error.

### `docmend plan [PATH | --inventory FILE]`

Produce a reviewable plan from an inventory (`PATH` is shorthand that scans first). Each planned action carries the exact transforms (encoding, newline, whitespace, rename), the source hash it was decided on, and its decision provenance; risky files become skips with reasons instead of actions. `--out FILE` relocates the plan; `--fail-on-low-confidence-encoding` exits 1 when any file skipped on the encoding gates. Exit codes: 0 clean, 1 findings, 2 input error, 3 safety refusal (concurrent run lock).

### `docmend apply PLAN`

Execute a reviewed plan. **Dry-run by default** — nothing is written until you pass `--write` (FR-004/OQ-014). A writing run is gated (exit 3 on refusal): a content-changing rewrite needs a byte-preserving strategy — tool backups (`--backup-dir PATH` or `write.backup_dir`), a declared strategy (`--preserved-by git|external`), or, for a single-action plan only, the explicit `--allow-no-backup` low-risk opt-in. Every mutation is recorded in an append-only manifest (`.docmend/docmend-<run-id>-manifest.jsonl`); the report (`--report FILE` to relocate) records every outcome.

An interrupted run resumes with `--resume-run-id ID` or `--resume-manifest FILE` (both repeatable — pass every manifest of a multiply-interrupted run): actions the prior manifest records as applied are reconciled read-only and skip as `already-applied` (not a finding), outputs changed or missing since apply fail as ERR-002, and everything else executes normally. See the [resume runbook](docs/runbooks/resume-after-interruption.md). Exit codes: 0 clean, 1 findings (skips other than already-applied, failures), 2 input error, 3 safety refusal.

### `docmend restore [--manifest FILE | --run-id ID]`

Undo an apply run by replaying its manifest newest-first. Dry-run by default; `--write` performs the restore; `--id DOCMEND_ID` limits it to specific documents. A file modified since apply is skipped, never clobbered. See the [restore runbook](docs/runbooks/restore-from-manifest.md). Exit codes: 0 clean, 1 findings (skips/failures), 2 input error, 3 safety refusal.

### `docmend verify PATH [--manifest FILE | --run-id ID] [--report FILE]`

Check converted output read-only: UTF-8 decodability, LF-only line endings, and — where a `.md` file carries YAML frontmatter — validity against the pinned frontmatter schema (a document without frontmatter is legal; v1 emits none). With a manifest (flag or run-ID sidecar), each applied output's live hash is reconciled against the recorded after-hash; with a report too (`--run-id` picks up the report sidecar automatically), report↔manifest accounting is cross-checked. Verify mutates nothing and writes no manifest. Exit codes: 0 clean, 1 findings, 2 input error.

### Global flags

`--verbose/-v` (repeatable) raises console detail, `--quiet/-q` limits it to errors (mutually exclusive with `-v`), `--dry-run/-n` previews without writing (conflicts with `--write`), `--version/-V` prints the version.

## Configuration

Configuration is a TOML file. When `--config` is omitted, `./docmend.toml` is auto-discovered; absent that, built-in defaults apply. Precedence is **CLI flags > config file > built-in defaults**: scalar flags override their key, and list-valued flags (`--include`/`--exclude`) **replace** the config list entirely, never append. Configuration alone can never enable real writes — `apply --write` is the only opt-in. Unknown keys, wrong types, and out-of-range values are rejected with a clear error.

The full reference with rationale is [spec §18.2](docs/specs/docmend.md); the shipped defaults:

| Key | Default | Meaning |
| --- | --- | --- |
| `paths.include` | `["**/*.txt", "**/*.md", "**/*.html", "**/*.htm"]` | Files to process; markup files receive encoding/EOL normalization only. |
| `paths.exclude` | `.git/`, `.venv/`, `node_modules/`, `.docmend/`, binary/media patterns | Files never processed. |
| `rename.txt_to_md` | `true` | Enable the `.txt` → `.md` extension rename. |
| `rename.on_collision` | `"skip"` | Collision policy: `skip`, `fail`, or `overwrite`. |
| `encoding.target` | `"utf-8"` | Output encoding (written without BOM). |
| `encoding.detect` | `true` | Legacy source-encoding detection. |
| `encoding.fail_below_confidence` | `0.80` | Detection-confidence skip threshold. |
| `encoding.non_ascii_floor` | `20` | Minimum non-ASCII bytes before a legacy-encoding guess is trusted. |
| `newlines.target` | `"lf"` | Output newline style. |
| `whitespace.trim_trailing` | `true` | Trim trailing whitespace per line. |
| `whitespace.ensure_final_newline` | `true` | Ensure exactly one final newline. |
| `whitespace.collapse_blank_lines` | `3` | Maximum consecutive blank lines retained. |
| `whitespace.normalize_tabs` | `false` | Convert leading (indentation) tabs to spaces; interior tabs untouched. |
| `whitespace.tab_width` | `4` | Space width for `normalize_tabs`. |
| `write.dry_run_default` | `true` | Apply defaults to dry-run. |
| `write.backup_dir` | unset | Backup destination; enables the tool-backup preservation strategy. |
| `write.atomic` | `true` | Atomic replace writes. |
| `parallel.*` | `enabled = false` | v1 runs sequentially; the process-pool switches (`model`, `workers`, `start_method`, `chunksize`, `maxtasksperchild`) are pinned but off by default. |
| `limits.per_file_timeout` | `60` | Seconds per file across discovery/detection/transform. |
| `limits.max_file_size_mib` | `100` | Plan-time size guard; larger files are skipped with reason. |
| `safety.shrink_ratio` | `0.50` | Output/input floor for future content-touching transforms (v1's never-lose-non-whitespace invariant is separate and not configurable). |

## Safety model

The pipeline is built so that no invocation can silently destroy content:

- **Dry-run by default.** `apply` and `restore` preview until you pass `--write`; no config key can flip that.
- **Reviewed plans execute, not live decisions.** `apply` runs the plan's config snapshot and re-hashes every source first — a file changed since planning is skipped, never mutated (FR-003).
- **Safety gate.** A writing run refuses (exit 3, library untouched) unless preservation is satisfied: tool backups, a declared `--preserved-by git|external` strategy, or the single-action `--allow-no-backup` opt-in.
- **Atomic writes.** Temp file + fsync + rename in the same directory: a crash can never leave a partially written document.
- **Append-only manifest.** Every mutation is fsync'd to an NDJSON manifest as it happens — the durable record that powers `restore`, `verify`, and resume.
- **Run lock.** Concurrent plan/apply/restore runs over the same tree refuse rather than race.
- **Reversibility.** `restore` replays a manifest newest-first back to the original bytes; `verify` proves the converted output (and the artifacts) are still consistent.

Runbooks: [restore from a manifest](docs/runbooks/restore-from-manifest.md) · [resume after an interruption](docs/runbooks/resume-after-interruption.md).

## Contributing / workflow

**Branching.** `main` is protected and advances **only via a pull request from `dev`**. `dev` is the long-lived working branch — **commit and push to it directly** (no PR needed); use a short-lived `feature/*` branch only when you want isolation. To update `main`, open a PR from `dev` and **merge with a merge commit** (not squash — keeps `dev` in sync with `main` and preserves history); the PR must pass CI and carry signed commits.

`main` protection requires all five CI gates green (`check`, `validate-specs`, `lint-markdown`, `traceability`, `dependency-review`), signed commits, and resolved conversations; it is enforced for admins too. Note that direct pushes to `dev` do **not** run CI — the `dev → main` PR is the gate, so run the local verification gate before opening one:

```bash
uv sync --locked --all-groups
uv run ruff format --check . && uv run ruff check .
uv run basedpyright
uv run coverage run -m pytest && uv run coverage report
uv run pip-audit
```

The rationale for this model — and why it diverges from the sibling `hw-radar` repo it is ported from — is recorded in [`docs/adr/adr-0017-branch-and-ci-cd-workflow.md`](docs/adr/adr-0017-branch-and-ci-cd-workflow.md).

## Release process

Releases are cut from tags on `main` ([spec §19](docs/specs/docmend.md) MS-5, `adr-0017`):

1. Tag `vX.Y.Z` on `main` (annotated, signed).
2. The release workflow builds the distribution with `uv build` (sdist + wheel).
3. The artifacts are attached to a GitHub Release for that tag.

PyPI publishing is out of scope for v1. Install from a release artifact (`uv tool install docmend-<version>-py3-none-any.whl`), from source with `uv tool install .`, or run ad hoc with `uvx --from . docmend`.
