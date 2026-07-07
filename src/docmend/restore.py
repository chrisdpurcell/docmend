"""Restore engine — LIFO manifest replay (IR-008, adr-0004, §12.3, §18.6).

Conservatism contract (decision 10): only result=='applied' records replay;
the live file must still hash to the record's after_sha256 (a file edited
since apply is skipped, never clobbered); the backup must hash to
before_sha256 (ERR-004 on mismatch); records with no backup reference are
skipped — the operator's own preservation strategy (git/external) is the
recovery path there, by design (FR-005). Restore is itself mutation: it
dry-runs by default and appends inverse records to its own run manifest.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from docmend.observability import get_logger
from docmend.writer.atomic import (
    WriteError,
    atomic_write_bytes,
    link_no_clobber,
    rename_no_clobber,
)
from docmend.writer.manifest import ManifestRecord, ManifestWriter

type RestoreStatus = Literal["restored", "would_restore", "skipped", "failed"]


@dataclass(frozen=True)
class RestoreOutcome:
    action_id: str
    docmend_id: str
    path: str
    status: RestoreStatus
    detail: str | None


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _verified_backup(record: ManifestRecord) -> bytes | RestoreOutcome:
    if record.backup_path is None:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "skipped", "no-backup"
        )
    try:
        data = Path(record.backup_path).read_bytes()
    except OSError as exc:
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "failed",
            f"ERR-004: backup unreadable ({exc})",
        )
    if _sha(data) != record.before_sha256:
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "failed",
            f"ERR-004: backup hash {_sha(data)} != recorded before hash {record.before_sha256}",
        )
    return data


def _live_matches_after(record: ManifestRecord) -> RestoreOutcome | None:
    live = Path(record.target_path)
    try:
        current = live.read_bytes()
    except OSError:
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "skipped",
            "unreadable: applied file missing or unreadable",
        )
    if record.after_sha256 is not None and _sha(current) != record.after_sha256:
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "skipped",
            "modified-since-apply",
        )
    return None


def run_restore(
    records: list[ManifestRecord],
    *,
    run_id: str,
    write: bool,
    only_ids: frozenset[str] | None,
    manifest_out: Path,
) -> list[RestoreOutcome]:
    """Replay `records` LIFO by seq, restoring only `result == "applied"` entries.

    IR-008, adr-0004: dry-run (the default) previews with no mutation; a write
    run appends one inverse manifest record per successful restoration to its
    own run manifest (via `ManifestWriter`, lazily opened like apply's).
    """
    log = get_logger(__name__)
    replay = [
        r
        for r in sorted(records, key=lambda r: r.seq, reverse=True)  # LIFO (IR-008)
        if r.result == "applied" and (only_ids is None or r.docmend_id in only_ids)
    ]
    outcomes: list[RestoreOutcome] = []
    manifest: ManifestWriter | None = None
    if write and replay:
        manifest = ManifestWriter(manifest_out, run_id=run_id)
    try:
        for record in replay:
            outcome = _restore_one(record, write=write, run_id=run_id, manifest=manifest)
            outcomes.append(outcome)
            log.info(
                "restore outcome",
                path=record.original_path,
                status=outcome.status,
                detail=outcome.detail,
            )
    finally:
        if manifest is not None:
            manifest.close()
    return outcomes


def _restore_one(
    record: ManifestRecord, *, write: bool, run_id: str, manifest: ManifestWriter | None
) -> RestoreOutcome:
    # ---- Preflight: verify EVERY recovery input before ANY mutation (codex
    # CR-003). A restore that mutates and then discovers a bad input has
    # destroyed state inside the disaster-recovery path itself — every early
    # return in this section leaves both live files byte-identical.
    mismatch = _live_matches_after(record)
    if mismatch is not None:
        return mismatch
    original = Path(record.original_path)
    target = Path(record.target_path)

    if record.operation != "rewrite" and original.exists():
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "skipped",
            "collision: original path is occupied",
        )
    backup: bytes | None = None
    if record.operation in ("rewrite", "rename_and_rewrite"):
        verdict = _verified_backup(record)
        if isinstance(verdict, RestoreOutcome):
            return verdict
        backup = verdict
    clobbered: bytes | None = None
    if record.overwritten_sha256 is not None and record.operation != "rewrite":
        # The overwrite policy destroyed a pre-existing target (OQ-035/G-002).
        if record.overwritten_backup_path is None:
            # Declared external preservation: docmend holds no bytes to
            # reinstate the clobbered file. Restoring only our own mutation
            # would report success while that file stays missing (codex
            # CR-NEW-003) — the operator's external strategy recovers the
            # WHOLE record, so skip it, mutating nothing.
            return RestoreOutcome(
                record.action_id,
                record.docmend_id,
                record.original_path,
                "skipped",
                "no-backup: overwritten target restorable only from external preservation",
            )
        # Its backup must read and verify BEFORE we undo our own mutation.
        try:
            clobbered = Path(record.overwritten_backup_path).read_bytes()
        except OSError as exc:
            return RestoreOutcome(
                record.action_id,
                record.docmend_id,
                record.original_path,
                "failed",
                f"ERR-004: overwritten-target backup unreadable ({exc})",
            )
        if _sha(clobbered) != record.overwritten_sha256:
            return RestoreOutcome(
                record.action_id,
                record.docmend_id,
                record.original_path,
                "failed",
                "ERR-004: overwritten-target backup hash mismatch",
            )
    if not write:
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "would_restore", None
        )

    # ---- Mutate: all inputs proven above. Ordering is loss-proof (codex
    # CR-003 residual): the original is reinstated FIRST and the applied
    # target is removed/replaced LAST, so an environmental failure at any
    # step leaves a SUPERSET of the wanted files on disk — never a missing
    # one. A half-restored record is deliberately re-runnable: its preflight
    # collision check surfaces the leftover state instead of guessing.
    try:
        if record.operation == "rewrite":
            assert backup is not None
            atomic_write_bytes(original, backup)
        elif record.operation == "rename":
            if clobbered is not None:
                # Keep the target name occupied throughout: link the applied
                # file back to its original name, then atomically replace the
                # target with the clobbered content — no window where either
                # name is missing.
                link_no_clobber(target, original)
                atomic_write_bytes(target, clobbered)
            else:
                rename_no_clobber(target, original)
        else:  # rename_and_rewrite
            assert backup is not None
            atomic_write_bytes(original, backup, clobber=False)
            if clobbered is not None:
                atomic_write_bytes(target, clobbered)
            else:
                target.unlink()
    except (WriteError, OSError, FileExistsError) as exc:
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "failed",
            f"ERR-003: {exc}",
        )

    if manifest is not None:
        manifest.append(
            record.model_copy(
                update={
                    "run_id": run_id,
                    "action_id": f"{run_id}/a{record.seq}",
                    "original_path": record.target_path,
                    "target_path": record.original_path,
                    "backup_path": None,
                    "before_sha256": record.after_sha256 or record.before_sha256,
                    "after_sha256": record.before_sha256,
                    "overwritten_sha256": None,
                    "overwritten_backup_path": None,
                    "error": None,
                }
            )
        )
    return RestoreOutcome(
        record.action_id, record.docmend_id, record.original_path, "restored", None
    )
