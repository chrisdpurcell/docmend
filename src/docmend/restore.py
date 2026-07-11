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
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal

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
    BoundFile,
    CommitHooks,
    InterferenceError,
    WriteSafetyContext,
    bind_file,
    check_bound,
    check_destination,
    guarded_rename_no_clobber,
    guarded_replace,
)
from docmend.writer.manifest import (
    ActionLifecycle,
    ManifestChain,
    ManifestHeader,
    ManifestRecord,
    ManifestWriter,
    manifest_sha256,
    reduce_lifecycle,
)

type RestoreStatus = Literal["restored", "would_restore", "skipped", "failed"]

_RESTORE_ENGINE_TOKEN: Final[object] = object()


@dataclass(frozen=True)
class RestoreOutcome:
    action_id: str
    docmend_id: str
    path: str
    status: RestoreStatus
    detail: str | None


@dataclass(frozen=True, init=False)
class _RestoreRun:
    """Engine-sealed restore state derived from a live capability."""

    safety: WriteSafetyContext
    chain: ManifestChain
    lifecycle: Mapping[str, ActionLifecycle]
    apply_terminals: Mapping[str, ManifestRecord]
    run_id: str
    manifest: ManifestWriter
    root_resolved: Path
    hooks: CommitHooks

    def __init__(
        self,
        *,
        _token: object | None = None,
        safety: WriteSafetyContext | None = None,
        chain: ManifestChain | None = None,
        lifecycle: Mapping[str, ActionLifecycle] | None = None,
        apply_terminals: Mapping[str, ManifestRecord] | None = None,
        run_id: str | None = None,
        manifest: ManifestWriter | None = None,
        root_resolved: Path | None = None,
        hooks: CommitHooks = NO_HOOKS,
    ) -> None:
        if _token is not _RESTORE_ENGINE_TOKEN:
            raise TypeError("_RestoreRun is engine-sealed")
        assert safety is not None
        safety._confirm_active("restore")  # pyright: ignore[reportPrivateUsage]
        if (
            chain is None
            or lifecycle is None
            or apply_terminals is None
            or run_id is None
            or manifest is None
            or root_resolved is None
        ):
            raise TypeError("_RestoreRun requires complete capability-derived state")
        object.__setattr__(self, "safety", safety)
        object.__setattr__(self, "chain", chain)
        object.__setattr__(self, "lifecycle", MappingProxyType(dict(lifecycle)))
        object.__setattr__(self, "apply_terminals", MappingProxyType(dict(apply_terminals)))
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "manifest", manifest)
        object.__setattr__(self, "root_resolved", root_resolved)
        object.__setattr__(self, "hooks", hooks)


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


def _restore_inputs(
    chain: ManifestChain,
) -> tuple[dict[str, ActionLifecycle], dict[str, ManifestRecord]]:
    lifecycle = reduce_lifecycle(chain)
    apply_terminals = {
        r.action_id: r
        for s in chain.sets
        if s.header.kind == "apply"
        for r in s.records
        if r.result == "applied"
    }
    return lifecycle, apply_terminals


def _ordered_lifecycle(
    lifecycle: Mapping[str, ActionLifecycle],
) -> list[tuple[str, ActionLifecycle]]:
    """Return inverse work in deterministic LIFO mutation order."""
    return sorted(
        lifecycle.items(),
        key=lambda item: (item[1].set_index, item[1].record.seq),
        reverse=True,
    )


def _non_action_outcome(action_id: str, state: ActionLifecycle) -> RestoreOutcome | None:
    record = state.record
    if state.state == "pending-intent":
        return RestoreOutcome(
            action_id,
            record.docmend_id,
            record.original_path,
            "skipped",
            f"dangling apply intent from {record.run_id}: resume the apply run before restoring",
        )
    if state.state == "restored":
        return RestoreOutcome(
            action_id,
            record.docmend_id,
            record.undoes_action_id or action_id,
            "skipped",
            "already-restored",
        )
    return None


def _preview_pending_restore(
    action_id: str, intent: ManifestRecord, undone: ManifestRecord | None
) -> RestoreOutcome | None:
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
    return RestoreOutcome(action_id, intent.docmend_id, intent.original_path, "would_restore", None)


def preview_restore(
    chain: ManifestChain, *, run_id: str, only_ids: frozenset[str] | None
) -> list[RestoreOutcome]:
    """Preview restore through a structurally read-only traversal."""
    del run_id  # Preview outcome identities come from the validated chain.
    lifecycle, apply_terminals = _restore_inputs(chain)
    outcomes: list[RestoreOutcome] = []
    for action_id, state in _ordered_lifecycle(lifecycle):
        if only_ids is not None and state.record.docmend_id not in only_ids:
            continue
        non_action = _non_action_outcome(action_id, state)
        if non_action is not None:
            outcomes.append(non_action)
            continue
        if state.state == "failed":
            continue
        if state.state == "pending-restore":
            pending = _preview_pending_restore(
                action_id, state.record, apply_terminals.get(action_id)
            )
            if pending is not None:
                outcomes.append(pending)
                continue
        record = apply_terminals.get(action_id)
        if record is not None:
            outcomes.append(_preview_restore_one(record))
    return outcomes


def run_restore(
    *,
    run_id: str,
    only_ids: frozenset[str] | None,
    manifest_out: Path,
    safety: WriteSafetyContext,
    hooks: CommitHooks = NO_HOOKS,
) -> list[RestoreOutcome]:
    """Restore only the immutable chain authorized by a live capability."""
    safety.confirm_restore(run_id=run_id, manifest_out=manifest_out)
    chain = safety.chain
    lifecycle, apply_terminals = _restore_inputs(chain)
    tip = chain.sets[-1]
    root_header = chain.sets[0].header
    root_resolved = Path(root_header.source_root).resolve()
    tip_sha = tip.sha256 or manifest_sha256(tip.path)
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
            effective_excludes=root_header.effective_excludes,
            created_at=datetime.now(UTC).isoformat(),
        ),
    )
    run = _RestoreRun(
        _token=_RESTORE_ENGINE_TOKEN,
        safety=safety,
        chain=chain,
        lifecycle=lifecycle,
        apply_terminals=apply_terminals,
        run_id=run_id,
        manifest=manifest,
        root_resolved=root_resolved,
        hooks=hooks,
    )
    outcomes: list[RestoreOutcome] = []
    try:
        for action_id, state in _ordered_lifecycle(lifecycle):
            record = state.record
            if only_ids is not None and record.docmend_id not in only_ids:
                continue
            non_action = _non_action_outcome(action_id, state)
            if non_action is not None:
                outcomes.append(non_action)
                continue
            if state.state == "failed":
                continue
            if state.state == "pending-restore":
                outcome = _converge_pending_restore(run, action_id)
                if outcome is not None:
                    outcomes.append(outcome)
                    _log_outcome(outcome)
                    continue
            if action_id in apply_terminals:
                outcome = _restore_one(run, action_id)
                outcomes.append(outcome)
                _log_outcome(outcome)
    finally:
        manifest.close()
    return outcomes


def _restore_one(run: _RestoreRun, action_id: str) -> RestoreOutcome:
    """Execute one inverse from sealed state; raw records are not accepted."""
    try:
        record = run.apply_terminals[action_id]
    except KeyError as exc:
        raise KeyError(f"{action_id}: not in validated chain") from exc
    return _restore_record(
        record,
        run_id=run.run_id,
        manifest=run.manifest,
        root_resolved=run.root_resolved,
        hooks=run.hooks,
    )


def _log_outcome(outcome: RestoreOutcome) -> None:
    get_logger(__name__).info(
        "restore outcome", path=outcome.path, status=outcome.status, detail=outcome.detail
    )


def _converge_pending_restore(run: _RestoreRun, action_id: str) -> RestoreOutcome | None:
    """An interrupted earlier restore left a dangling INVERSE intent: the
    shared adjudication table classifies the crash-after state and this run
    completes or adopts it — convergence instead of a collision trip (the
    DMR-04 restore half). Returns None for never-happened (re-execute)."""
    try:
        intent = run.lifecycle[action_id].record
    except KeyError as exc:
        raise KeyError(f"{action_id}: not in validated chain") from exc
    undone = run.apply_terminals.get(action_id)
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
    if verdict.verdict == "finish-remaining":
        try:
            finish_remaining(
                intent,
                undone=undone,
                root_resolved=run.root_resolved,
                hooks=run.hooks,
            )
        except WriteError as exc:
            return RestoreOutcome(
                action_id, intent.docmend_id, intent.original_path, "failed", f"ERR-003: {exc}"
            )
    # This run asserts the closure terminal for the factory-validated intent.
    run.manifest.append(intent.model_copy(update={"result": "applied", "run_id": run.run_id}))
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


@dataclass(frozen=True)
class _PreparedRestore:
    record: ManifestRecord
    original: Path
    target: Path
    live: BoundFile
    backup: bytes | None
    clobbered: bytes | None


def _prepare_restore(record: ManifestRecord) -> _PreparedRestore | RestoreOutcome:
    """Validate every recovery input without exposing a mutation branch."""
    original = Path(record.original_path)
    target = Path(record.target_path)
    try:
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
        if record.overwritten_backup_path is None:
            return RestoreOutcome(
                record.action_id,
                record.docmend_id,
                record.original_path,
                "skipped",
                "no-backup: overwritten target restorable only from external preservation",
            )
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
    return _PreparedRestore(record, original, target, live, backup, clobbered)


def _preview_restore_one(record: ManifestRecord) -> RestoreOutcome:
    prepared = _prepare_restore(record)
    if isinstance(prepared, RestoreOutcome):
        return prepared
    return RestoreOutcome(
        record.action_id, record.docmend_id, record.original_path, "would_restore", None
    )


def _restore_record(
    record: ManifestRecord,
    *,
    run_id: str,
    manifest: ManifestWriter,
    root_resolved: Path,
    hooks: CommitHooks,
) -> RestoreOutcome:
    prepared = _prepare_restore(record)
    if isinstance(prepared, RestoreOutcome):
        return prepared
    original = prepared.original
    target = prepared.target
    live = prepared.live
    mode = live.mode
    backup = prepared.backup
    clobbered = prepared.clobbered

    # ---- Journal-every-mutation (adr-0019): stage any replacement output
    # FIRST (a tool-owned temp is not corpus mutation), capture the inverse's
    # identities, append the fsync'd intent, mutate, append the terminal.
    source_identity = live.identity
    staged: StagedWrite | None = None
    try:
        if backup is not None:
            staged = stage_bytes(original, backup, mode=mode)
    except WriteError as exc:
        manifest.append(
            _inverse_record(
                record, run_id=run_id, result="failed", identities=(None, None)
            ).model_copy(update={"after_sha256": None, "error": _staging_error(exc)})
        )
        return RestoreOutcome(
            record.action_id, record.docmend_id, record.original_path, "failed", f"ERR-003: {exc}"
        )
    expected_identity = staged.identity if staged is not None else source_identity
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

    manifest.append(intent.model_copy(update={"result": "applied"}))
    return RestoreOutcome(
        record.action_id, record.docmend_id, record.original_path, "restored", None
    )


def _staging_error(exc: BaseException) -> ErrorInfo:
    return ErrorInfo(error_class="ERR-003", message=str(exc))
