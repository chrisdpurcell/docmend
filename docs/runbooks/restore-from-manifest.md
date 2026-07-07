# Runbook: restore from a manifest

Undo an apply run by replaying its manifest — every mutation docmend performed is recorded there with before/after hashes and any backup path, so recovery is mechanical (spec §18.6, IR-008).

## When to use this

- An apply run changed files it shouldn't have, or the results are wrong on review.
- `docmend verify` reported hash mismatches you want to roll back rather than investigate forward.
- You are running the periodic restore drill against a copy of real output.

## 1. Locate the manifest

Every writing `apply` run prints its manifest path and stores it by the sidecar convention:

```text
.docmend/docmend-<run-id>-manifest.jsonl
```

in the directory `apply` was invoked from. If you know the run ID (it is in the console output, the report filename, and the per-run log), you can pass `--run-id` instead of a path. To list candidate runs:

```bash
ls .docmend/docmend-*-manifest.jsonl
```

## 2. Preview (dry-run is the default)

```bash
docmend restore --run-id <run-id>
# or, from anywhere (manifest paths are absolute inside the file):
docmend restore --manifest /path/to/.docmend/docmend-<run-id>-manifest.jsonl
```

The preview reports what would be restored, skipped, or failed without touching anything. A file **modified since apply** is reported as a skip — restore never clobbers newer content.

## 3. Restore

```bash
docmend restore --run-id <run-id> --write
```

Records replay newest-first (LIFO), so a rename-then-rewrite chain unwinds in the right order. Exit 0 means every record restored; exit 1 means some skipped or failed — each is listed with a reason. Exit 3 means another docmend run holds the lock on this tree; let it finish first.

To restore only specific documents, pass their stable IDs (from the manifest records' `docmend_id`):

```bash
docmend restore --run-id <run-id> --write --id <docmend-id> --id <another-id>
```

## 4. Restoring a resumed run

A run that was interrupted and resumed has **one manifest per attempt** (each attempt got its own run ID). Together they cover each mutation exactly once. Restore them **newest first**:

```bash
docmend restore --run-id <resume-run-id> --write
docmend restore --run-id <original-run-id> --write
```

The resume runbook (`resume-after-interruption.md`) explains how the attempts relate.

## 5. Verify the result

```bash
docmend scan <tree>
```

A scan after a full restore should match the pre-apply state (the original inventory is still in `.docmend/` if you planned from one). For a partial restore, spot-check the restored files' hashes against the manifest's `before_sha256` values.

## Failure notes

- **"restore capability: renames-only" (printed up front)** — the apply run satisfied the write gate with a declared external preservation (`--preserved-by` / `--allow-no-backup`) and took no tool backups, so this manifest can undo only pure renames; an action that rewrote content (even one that also renamed) is skipped whole. Recover content from whatever preservation covered the apply run (git checkout, snapshot, backup). Wrapper scripts can derive the same fact from the manifest: an applied non-rename record with a null `backup_path` has no recoverable bytes.
- **Skip: "modified since apply"** — the live file no longer matches the manifest's after-hash. Decide manually: keep the newer content, or move it aside and re-run restore for that ID.
- **Skip: "no-backup"** — that record's content mutation was never backed up by the tool (external preservation run); the skip detail names the recovery path.
- **Failed: backup missing** — a content rewrite recorded a backup path that no longer exists. The original bytes are only in your external preservation (git/backup regime) at that point.
- Restore writes its own inverse manifest under `.docmend/`, so a restore is itself undoable **for its renames**: inverse records carry no backup bytes (`backup_path` is null), so a restore that reversed a content rewrite cannot itself be re-reversed from the inverse manifest — the same renames-only rule above applies to it.
