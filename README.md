# docmend

Python tool to normalize, fix, convert, manage, and maintain large libraries of text and markdown documents.

> **Status:** writer layer (MS-3) implemented. The design is complete (see [`docs/specs/docmend.md`](docs/specs/docmend.md)); `docmend scan PATH` produces a structured, schema-validated inventory of a file or directory tree — read-only, with include/exclude filters — and the four run-artifact JSON Schemas are pinned in `src/docmend/schemas/`. `docmend plan` turns that inventory into a reviewable plan of encoding/newline/whitespace transforms, renames, and risk-classified skips — still read-only, no writes. `docmend apply` now executes a reviewed plan (dry-run by default, gated writes, atomic mutation, a reversible manifest) and `docmend restore` undoes an apply run. `verify` lands in a later milestone.

## Commands

### `docmend apply PLAN`

Execute a reviewed plan. **Dry-run by default** — nothing is written until you pass `--write` (FR-004/OQ-014). A writing run is gated (exit 3 on refusal): a content-changing rewrite needs a byte-preserving strategy — tool backups (`--backup-dir PATH` or `write.backup_dir`), a declared strategy (`--preserved-by git|external`), or, for a single-action plan only, the explicit `--allow-no-backup` low-risk opt-in. Every mutation is recorded in an append-only manifest (`.docmend/docmend-<run-id>-manifest.jsonl`); the report (`--report FILE` to relocate) records every outcome. Exit codes: 0 clean, 1 findings (skips/failures), 2 input error, 3 safety refusal.

### `docmend restore [--manifest FILE | --run-id ID]`

Undo an apply run by replaying its manifest newest-first. Dry-run by default; `--write` performs the restore; `--id DOCMEND_ID` limits it to specific documents. A file modified since apply is skipped, never clobbered.

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

Releases are **deferred** until the CLI exists (milestone MS-5, [spec §19](docs/specs/docmend.md)). The intended path, to be wired as a workflow at that point:

1. Tag `vX.Y.Z` on `main` (annotated, signed).
2. Build the distribution with `uv build` (sdist + wheel).
3. Attach the artifacts to a GitHub Release.

PyPI publishing is out of scope for v1. Until the release workflow lands, install from source with `uv tool install .` or run ad hoc with `uvx --from . docmend`.
