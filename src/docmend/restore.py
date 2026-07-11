"""Restore engine — LIFO chain replay (IR-008, adr-0004, adr-0019, §12.3, §18.6).

Conservatism contract (decision 10): only reducer-state `applied` actions
replay; the live file must still hash to the record's after_sha256 (a file
edited since apply is skipped, never clobbered); the backup must hash to
before_sha256 (ERR-004 on mismatch); records with no backup reference are
skipped — the operator's own preservation strategy (git/external) is the
recovery path there, by design (FR-005).

2.0 (adr-0019): restore is a CHAIN consumer driven by the same
`reduce_lifecycle` resume and verify use, and restore is itself journaled
mutation — every inverse appends a fsync'd intent (with the durable object
identities) before touching a corpus name and a terminal after, so an
interrupted restore CONVERGES on re-run through the shared adjudication
table instead of tripping its own collision preflight (the DMR-04 restore
half the 2026-07-10 review reproduced).

Permission preservation (IR-008, §8.1): apply carries the source file's mode
onto the applied target, so every reinstatement write below stats the live
target immediately before mutating and passes that mode through — otherwise
restored files come back at the temp-file default (0o600) instead of their
original permissions.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from docmend.lineage import ObjectIdentity, PriorAttempt
from docmend.observability import get_logger
from docmend.report import ErrorInfo
from docmend.writer.adjudicate import adjudicate_dangling_intent, finish_remaining
from docmend.writer.atomic import (
    StagedWrite,
    WriteError,
    abort_staged,
    link_no_clobber,
    publish_staged,
    stage_bytes,
)
from docmend.writer.commit import (
    NO_HOOKS,
    CommitHooks,
    InterferenceError,
    bind_file,
    check_bound,
    check_destination,
    guarded_rename_no_clobber,
    guarded_replace,
)
from docmend.writer.manifest import (
    ManifestChain,
    ManifestHeader,
    ManifestRecord,
    ManifestWriter,
    manifest_sha256,
    reduce_lifecycle,
)

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
        # Issue #15 (suggestion 4): name where recovery actually lives, so the
        # operator discovering this at restore time knows the next step.
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "skipped",
            "no-backup: the apply run took no tool backup for this content mutation "
            "(the FR-005 gate was satisfied without --backup-dir) — recover these "
            "bytes from whatever preservation covered that run (e.g. git, an "
            "external snapshot, or other backups)",
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


def run_restore(
    chain: ManifestChain,
    *,
    run_id: str,
    write: bool,
    only_ids: frozenset[str] | None,
    manifest_out: Path,
    hooks: CommitHooks = NO_HOOKS,
) -> list[RestoreOutcome]:
    """Undo a validated apply CHAIN (adr-0019): the lifecycle reducer decides
    each action's state; `applied` states replay LIFO (chain position then
    seq); `pending-restore` states (an interrupted earlier restore) converge
    through the adjudication table instead of tripping a collision; dangling
    APPLY intents surface as findings (adjudicating those is resume's job).

    IR-008, adr-0004: dry-run (the default) previews with no mutation. 2.0:
    every inverse journals intent-then-terminal into a restore-kind manifest
    whose header copies the chain's source_root/plan_sha256, links the chain
    tip as its prior, and carries `backup_root: null` (a restore run takes no
    tool backups; its inverse records hold no backup references — review
    CR-NEW-003).
    """
    log = get_logger(__name__)
    lifecycle = reduce_lifecycle(chain)
    apply_terminals = {
        r.action_id: r
        for s in chain.sets
        if s.header.kind == "apply"
        for r in s.records
        if r.result == "applied"
    }
    tip = chain.sets[-1]
    root_header = chain.sets[0].header
    root_resolved = Path(root_header.source_root).resolve()
    tip_sha = tip.sha256 or manifest_sha256(tip.path)
    manifest: ManifestWriter | None = None
    if write:
        manifest = ManifestWriter(
            manifest_out,
            header=ManifestHeader(
                run_id=run_id,
                kind="restore",
                source_root=root_header.source_root,
                backup_root=None,
                plan_sha256=root_header.plan_sha256,
                prior_manifest_sha256=tip_sha,
                prior_attempt=PriorAttempt(
                    run_id=tip.header.run_id, report_sha256=None, manifest_sha256=tip_sha
                ),
                created_at=datetime.now(UTC).isoformat(),
            ),
        )

    outcomes: list[RestoreOutcome] = []
    # LIFO over ORIGINAL apply actions: latest mutation undone first.
    ordered = sorted(
        lifecycle.items(),
        key=lambda item: (item[1].set_index, item[1].record.seq),
        reverse=True,
    )
    try:
        for action_id, state in ordered:
            record = state.record
            docmend_id = record.docmend_id
            if only_ids is not None and docmend_id not in only_ids:
                continue
            if state.state == "pending-intent":
                outcomes.append(
                    RestoreOutcome(
                        action_id,
                        docmend_id,
                        record.original_path,
                        "skipped",
                        f"dangling apply intent from {record.run_id}: resume the apply "
                        f"run before restoring (adr-0019 adjudication is resume's job)",
                    )
                )
                continue
            if state.state == "failed":
                continue  # the apply never happened; nothing to undo
            if state.state == "restored":
                outcomes.append(
                    RestoreOutcome(
                        action_id,
                        docmend_id,
                        record.undoes_action_id or action_id,
                        "skipped",
                        "already-restored",
                    )
                )
                continue
            if state.state == "pending-restore":
                outcome = _converge_pending_restore(
                    action_id,
                    state.record,
                    apply_terminals.get(action_id),
                    write=write,
                    run_id=run_id,
                    manifest=manifest,
                    root_resolved=root_resolved,
                    hooks=hooks,
                )
                if outcome is not None:
                    outcomes.append(outcome)
                    _log_outcome(log, outcome)
                    continue
                # never-happened: fall through and re-execute the inverse.
            if state.state == "restore-failed":
                # A failed inverse terminal proves no mutation landed, so a
                # retry is a fresh inverse; failed -> intent -> applied is legal.
                pass
            undone = apply_terminals.get(action_id)
            if undone is None:
                continue  # unreachable: chain rules require the apply record
            outcome = _restore_one(
                undone,
                write=write,
                run_id=run_id,
                manifest=manifest,
                root_resolved=root_resolved,
                hooks=hooks,
            )
            outcomes.append(outcome)
            _log_outcome(log, outcome)
    finally:
        if manifest is not None:
            manifest.close()
    return outcomes


def _log_outcome(log: object, outcome: RestoreOutcome) -> None:
    get_logger(__name__).info(
        "restore outcome", path=outcome.path, status=outcome.status, detail=outcome.detail
    )


def _converge_pending_restore(
    action_id: str,
    intent: ManifestRecord,
    undone: ManifestRecord | None,
    *,
    write: bool,
    run_id: str,
    manifest: ManifestWriter | None,
    root_resolved: Path,
    hooks: CommitHooks,
) -> RestoreOutcome | None:
    """An interrupted earlier restore left a dangling INVERSE intent: the
    shared adjudication table classifies the crash-after state and this run
    completes or adopts it — convergence instead of a collision trip (the
    DMR-04 restore half). Returns None for never-happened (re-execute)."""
    verdict = adjudicate_dangling_intent(intent, undone=undone)
    if verdict.verdict == "never-happened":
        return None
    if verdict.verdict == "external-interference":
        return RestoreOutcome(
            action_id,
            intent.docmend_id,
            intent.original_path,
            "failed",
            f"ERR-002: {verdict.detail}",
        )
    if not write:
        return RestoreOutcome(
            action_id, intent.docmend_id, intent.original_path, "would_restore", None
        )
    if verdict.verdict == "finish-remaining":
        try:
            finish_remaining(
                intent,
                undone=undone,
                root_resolved=root_resolved,
                hooks=hooks,
            )
        except WriteError as exc:
            return RestoreOutcome(
                action_id, intent.docmend_id, intent.original_path, "failed", f"ERR-003: {exc}"
            )
    if manifest is not None:
        # The adjudication terminal: the dangling inverse intent's immutable
        # fields verbatim; run_id is this run's (chain closure, CR-NEW-002).
        manifest.append(intent.model_copy(update={"result": "applied", "run_id": run_id}))
    return RestoreOutcome(action_id, intent.docmend_id, intent.original_path, "restored", None)


def _inverse_record(
    record: ManifestRecord,
    *,
    run_id: str,
    result: str,
    identities: tuple[ObjectIdentity | None, ObjectIdentity | None],
) -> ManifestRecord:
    """The inverse of an applied record: paths and hashes swapped, undoes
    lineage set, backup references cleared (the apply sets keep the backup
    anchors; a restore run takes none — CR-NEW-003)."""
    source_identity, expected_identity = identities
    return record.model_copy(
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
            "result": result,
            "undoes_action_id": record.action_id,
            "undoes_run_id": record.run_id,
            "source_identity": source_identity,
            "target_identity": None,
            "expected_published_identity": expected_identity,
        }
    )


def _restore_one(
    record: ManifestRecord,
    *,
    write: bool,
    run_id: str,
    manifest: ManifestWriter | None,
    root_resolved: Path,
    hooks: CommitHooks,
) -> RestoreOutcome:
    # ---- Preflight: verify EVERY recovery input before ANY mutation (codex
    # CR-003). A restore that mutates and then discovers a bad input has
    # destroyed state inside the disaster-recovery path itself — every early
    # return in this section leaves both live files byte-identical.
    original = Path(record.original_path)
    target = Path(record.target_path)
    try:
        # Hash, mode, and identity describe one descriptor-bound applied file.
        live = bind_file(target)
    except InterferenceError as exc:
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "failed",
            f"ERR-002 external-interference: {exc}",
        )
    except OSError:
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "skipped",
            "unreadable: applied file missing or unreadable",
        )
    if record.after_sha256 is not None and _sha(live.data) != record.after_sha256:
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "skipped",
            "modified-since-apply",
        )
    mode = live.mode

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

    # ---- Journal-every-mutation (adr-0019): stage any replacement output
    # FIRST (a tool-owned temp is not corpus mutation), capture the inverse's
    # identities, append the fsync'd intent, mutate, append the terminal.
    source_identity = live.identity
    staged: StagedWrite | None = None
    try:
        if backup is not None:
            staged = stage_bytes(original, backup, mode=mode)
    except WriteError as exc:
        if manifest is not None:
            manifest.append(
                _inverse_record(
                    record, run_id=run_id, result="failed", identities=(None, None)
                ).model_copy(update={"after_sha256": None, "error": _staging_error(exc)})
            )
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "failed", f"ERR-003: {exc}"
        )
    expected_identity = staged.identity if staged is not None else source_identity
    intent = None
    if manifest is not None:
        intent = manifest.append(
            _inverse_record(
                record,
                run_id=run_id,
                result="intent",
                identities=(source_identity, expected_identity),
            )
        )

    # ---- Mutate: all inputs proven above. Ordering is loss-proof (codex
    # CR-003 residual): the original is reinstated FIRST and the applied
    # target is removed/replaced LAST, so an environmental failure at any
    # step leaves a SUPERSET of the wanted files on disk — never a missing
    # one. An interrupted inverse converges on re-run via the adjudication
    # table (adr-0019), never a guessing collision trip.
    mutated = False
    try:
        if record.operation == "rewrite":
            assert staged is not None
            hooks.before_step("publish", original)
            check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)
            check_bound(target, live.identity, root_resolved=root_resolved)
            publish_staged(staged, original)
        elif record.operation == "rename":
            if clobbered is not None:
                hooks.before_step("publish", original)
                check_bound(target, live.identity, root_resolved=root_resolved)
                check_destination(original, root_resolved=root_resolved)
                link_no_clobber(target, original)
                mutated = True
                guarded_replace(
                    target,
                    clobbered,
                    expected=live.identity,
                    mode=mode,
                    root_resolved=root_resolved,
                    hooks=hooks,
                    survivor=(original, live.identity),
                )
            else:
                guarded_rename_no_clobber(
                    target,
                    original,
                    live.identity,
                    root_resolved=root_resolved,
                    hooks=hooks,
                )
        else:  # rename_and_rewrite
            assert staged is not None
            hooks.before_step("publish", original)
            check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)
            check_destination(original, root_resolved=root_resolved)
            reinstated_identity = staged.identity
            publish_staged(staged, original, clobber=False)
            mutated = True
            hooks.before_step("unlink", target)
            if clobbered is not None:
                guarded_replace(
                    target,
                    clobbered,
                    expected=live.identity,
                    mode=mode,
                    root_resolved=root_resolved,
                    hooks=hooks,
                    survivor=(original, reinstated_identity),
                )
            else:
                check_bound(original, reinstated_identity, root_resolved=root_resolved)
                check_bound(target, live.identity, root_resolved=root_resolved)
                target.unlink()
    except InterferenceError as exc:
        if staged is not None:
            abort_staged(staged, root_resolved=root_resolved)
        if mutated or exc.intermediate:
            return RestoreOutcome(
                record.action_id,
                record.docmend_id,
                record.original_path,
                "failed",
                f"ERR-002 external-interference: {exc} "
                "(intermediate preserved; re-run adjudicates)",
            )
        if manifest is not None and intent is not None:
            manifest.append(
                intent.model_copy(
                    update={
                        "result": "failed",
                        "after_sha256": None,
                        "run_id": run_id,
                        "error": ErrorInfo(error_class="ERR-002", message=str(exc)),
                    }
                )
            )
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "failed",
            f"ERR-002 external-interference: {exc}",
        )
    except (WriteError, OSError, FileExistsError) as exc:
        if staged is not None:
            abort_staged(staged, root_resolved=root_resolved)
        if mutated:
            return RestoreOutcome(
                record.action_id,
                record.docmend_id,
                record.original_path,
                "failed",
                f"ERR-003: {exc} (intermediate preserved; re-run adjudicates)",
            )
        if manifest is not None and intent is not None:
            manifest.append(
                intent.model_copy(
                    update={
                        "result": "failed",
                        "after_sha256": None,
                        "run_id": run_id,
                        "error": _staging_error(exc),
                    }
                )
            )
        return RestoreOutcome(
            record.action_id,
            record.docmend_id,
            record.original_path,
            "failed",
            f"ERR-003: {exc}",
        )

    if manifest is not None and intent is not None:
        manifest.append(intent.model_copy(update={"result": "applied"}))
    return RestoreOutcome(
        record.action_id, record.docmend_id, record.original_path, "restored", None
    )


def _staging_error(exc: BaseException) -> ErrorInfo:
    return ErrorInfo(error_class="ERR-003", message=str(exc))
