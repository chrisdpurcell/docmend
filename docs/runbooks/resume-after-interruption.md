# Runbook: resume after an interruption

Complete an apply run that was killed mid-batch — crash, Ctrl-C, power loss — without redoing finished work and without touching anything that changed behind docmend's back (FR-013, `adr-0006`).

## What an interruption leaves behind

- **No partial files.** Writes are atomic (temp file + fsync + rename), so every document is either fully converted or untouched.
- **A manifest that is complete up to the kill.** One record is fsync'd per mutation as it happens. At worst the final line is torn (the crash hit mid-append); the reader drops exactly that torn tail and keeps everything before it.
- **A rename-and-rewrite killed mid-step leaves an `intent` line.** That action mutates in two steps (publish the converted target, remove the source), so apply records a write-ahead intent — the expected output hash — before the first step. If the manifest ends with an intent that has no final record, the kill landed inside that window; resume uses the intent to finish or adopt the action safely (see step 4).
- The plan file is untouched — it is the immutable statement of intent the resume reconciles against.

## 1. Find the interrupted run's ID

```bash
ls .docmend/docmend-*-manifest.jsonl
```

The interrupted attempt is the newest manifest for that tree (its run ID is also in the console output and the per-run log in `.docmend/`).

## 2. Preview the remainder (optional)

Resume works under the dry-run default too:

```bash
docmend apply plan.json --resume-run-id <run-id>
```

Completed work shows as `already-applied`; the remainder shows as `would-apply`.

## 3. Resume

Re-invoke apply with the same plan, the same preservation flags, and the prior run's manifest:

```bash
docmend apply plan.json --write --preserved-by git --resume-run-id <run-id>
```

If the run has been interrupted **more than once**, pass every prior attempt's manifest — the flags are repeatable and combinable:

```bash
docmend apply plan.json --write --preserved-by git \
  --resume-run-id <first-attempt-id> --resume-run-id <second-attempt-id>
# --resume-manifest /path/to/manifest.jsonl works too, from any directory
```

A manifest recorded against a different tree is refused (exit 2) — that is a wrong-manifest guard, not a failure of the resume itself.

## 4. Read the outcome

| Outcome | Meaning | Action |
| --- | --- | --- |
| `already-applied` skip | The prior manifest records this action as applied and the live output still matches its recorded hash. Not a finding — a fully resumed clean run exits 0. | None. |
| `applied` | Work the interrupted run never reached, now done. | None. |
| `stale-hash` or `unreadable` skip | Usually the **lost-trailing-record case**: the mutation completed but the crash tore its manifest line, so resume re-checked the file and found it already converted (or, for a rename, gone from its source path). Safe — nothing was mutated twice. | Inspect the file; it is normally fine. If tool backups were on, the pre-mutation copy still exists under `<backup_root>/<run-id>/<relative-path>` even though the manifest lost the pointer to it. |
| `applied` from a **dangling intent** | The kill landed inside a rename-and-rewrite's two-step window. Resume checked the intent's expected hash against the live target and either finished the step that was pending (removing the source) or adopted the already-finished mutation, recording the applied line the interrupted run never wrote. | None — the resume manifest now carries the action's restore record. |
| `failed` ERR-002 | The manifest says applied (or an intent was recorded), but the file state matches **neither the expected output nor the pre-action content** — something else changed or deleted it. Resume surfaces external interference rather than proceeding past it. | Investigate what touched the file; restore it from backup or re-plan just that file. |

The resume attempt writes **its own manifest** (new run ID). The attempts' manifests together cover each mutation exactly once — to undo the whole run, restore each manifest newest-first (see `restore-from-manifest.md`).

## 5. Verify

```bash
docmend verify <tree> --run-id <resume-run-id>
docmend verify <tree> --run-id <original-run-id>
```

Verify each attempt's manifest: content checks run over the tree, and each manifest's applied records are reconciled against the live files.
