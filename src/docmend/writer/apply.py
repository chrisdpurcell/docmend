"""Apply engine — executes a reviewed plan through the writer layer.

Architectural role (§8.2.3): the ONLY orchestration that mutates the library,
and only via the atomic/backup primitives in this package. The plan's config
snapshot is authoritative (decision 3): transforms, filters, and collision
policy come from the plan, never the live config — that is what makes the
reviewed plan the thing that actually executes (D-006, C.4).

Per-action contract (decisions 4-9): re-read -> re-hash (FR-003) -> snapshot
filters (FR-012) -> resolve-containment (§13.5) -> recompute transforms and
cross-check operations -> EC-005 re-check -> collision policy (FR-011) ->
[dry-run stops here] -> verify-then-mutate backup (FR-006) -> atomic mutation
(NFR-002) -> fsync'd manifest record (DR-004) -> outcome (DR-003). Failures
never abort the batch except the 'fail' collision policy (AW-002); every
failure class maps to §12.1.
"""

import hashlib
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Final

from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from docmend import __version__
from docmend.artifacts import ArtifactError
from docmend.config import DocmendConfig
from docmend.discovery import sniff_bom
from docmend.lineage import ObjectIdentity, PriorAttempt
from docmend.observability import ProgressHeartbeat, get_logger
from docmend.plan import ArtifactRef, Plan, PlanAction
from docmend.report import (
    ApplyOutcome,
    ApplySkipReason,
    ErrorInfo,
    Report,
    ReportTotals,
)
from docmend.transform.dispatch import (
    Operation,
    apply_text_transforms,
    classify_suffix,
    non_whitespace_count,
)
from docmend.transform.encoding import decode_source, encode_utf8
from docmend.writer.adjudicate import adjudicate_dangling_intent, finish_remaining
from docmend.writer.atomic import (
    StagedWrite,
    WriteError,
    abort_staged,
    fsync_dir,
    publish_staged,
    rename_overwrite,
    stage_bytes,
)
from docmend.writer.backup import BackupError, backup_file
from docmend.writer.commit import (
    NO_HOOKS,
    BoundFile,
    CommitHooks,
    InterferenceError,
    WriteSafetyContext,
    _observe_name,  # pyright: ignore[reportPrivateUsage] - shared rollback observation.
    bind_file,
    check_bound,
    check_destination,
    guarded_rename_no_clobber,
    guarded_replace,
)
from docmend.writer.gate import ApplyOptions, is_content_rewrite, strategy_active
from docmend.writer.manifest import (
    ActionLifecycle,
    ManifestChain,
    ManifestHeader,
    ManifestOperation,
    ManifestRecord,
    ManifestWriter,
    reduce_lifecycle,
)

_ENGINE_TOKEN: Final[object] = object()


@dataclass(frozen=True, init=False)
class _ApplyRun:
    """Engine-sealed authority assembled only from a live write capability."""

    safety: WriteSafetyContext
    plan: Plan
    config: DocmendConfig
    source_root: Path
    root_resolved: Path
    options: ApplyOptions
    run_id: str
    manifest: ManifestWriter
    hooks: CommitHooks
    include: PathSpec[GitIgnoreSpecPattern]
    exclude: PathSpec[GitIgnoreSpecPattern]
    actions: Mapping[str, PlanAction]
    lifecycle: Mapping[str, ActionLifecycle]

    def __init__(
        self,
        *,
        _token: object | None = None,
        safety: WriteSafetyContext | None = None,
        plan: Plan | None = None,
        config: DocmendConfig | None = None,
        source_root: Path | None = None,
        root_resolved: Path | None = None,
        options: ApplyOptions | None = None,
        run_id: str | None = None,
        manifest: ManifestWriter | None = None,
        hooks: CommitHooks = NO_HOOKS,
        include: PathSpec[GitIgnoreSpecPattern] | None = None,
        exclude: PathSpec[GitIgnoreSpecPattern] | None = None,
        actions: Mapping[str, PlanAction] | None = None,
        lifecycle: Mapping[str, ActionLifecycle] | None = None,
    ) -> None:
        if _token is not _ENGINE_TOKEN:
            raise TypeError("_ApplyRun is engine-sealed")
        assert safety is not None
        safety._confirm_active("apply")  # pyright: ignore[reportPrivateUsage]
        required = (plan, config, source_root, root_resolved, options, run_id, manifest)
        if any(value is None for value in required) or include is None or exclude is None:
            raise TypeError("_ApplyRun requires complete factory-derived state")
        object.__setattr__(self, "safety", safety)
        object.__setattr__(self, "plan", plan)
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "source_root", source_root)
        object.__setattr__(self, "root_resolved", root_resolved)
        object.__setattr__(self, "options", options)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "manifest", manifest)
        object.__setattr__(self, "hooks", hooks)
        object.__setattr__(self, "include", include)
        object.__setattr__(self, "exclude", exclude)
        object.__setattr__(self, "actions", MappingProxyType(dict(actions or {})))
        object.__setattr__(self, "lifecycle", MappingProxyType(dict(lifecycle or {})))


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _suffix(path: str) -> str:
    """The final `.ext` of the basename, or "" — matches `FileRecord.suffix`
    (discovery.classify_file derives it from `Path.suffix` on the full path,
    which is equivalent to the basename since suffix only looks at the final
    path component)."""
    return Path(path).suffix


def _skip(action: PlanAction, reason: ApplySkipReason) -> ApplyOutcome:
    return ApplyOutcome(
        action_id=action.action_id,
        path=action.path,
        status="skipped",
        before_sha256=action.source_sha256,
        after_sha256=None,
        skip_reason=reason,
        error=None,
    )


def _failed(action: PlanAction, error_class: str, message: str) -> ApplyOutcome:
    return ApplyOutcome(
        action_id=action.action_id,
        path=action.path,
        status="failed",
        before_sha256=action.source_sha256,
        after_sha256=None,
        skip_reason=None,
        error=ErrorInfo(error_class=error_class, message=message),
    )


def _action_seq(action: PlanAction) -> str:
    """The `aN` tail of `action_id` (`{run_id}/aN`) — the BackupStore's
    per-action key segment (adr-0019/adr-0004 amendment)."""
    return action.action_id.rsplit("/", 1)[-1]


def _operation_kind(action: PlanAction) -> ManifestOperation:
    renames = "rename" in action.operations
    if renames and is_content_rewrite(action):
        return "rename_and_rewrite"
    return "rename" if renames else "rewrite"


def _recompute(action: PlanAction, data: bytes, config: DocmendConfig) -> bytes | str:
    """Re-derive the output bytes; a str return is an error message."""
    bom = sniff_bom(data[:4])
    detected = action.provenance.detected_encoding
    encoding_name = detected.name if detected is not None else "utf-8"
    try:
        text = decode_source(data, bom=bom, encoding_name=encoding_name)
    except (UnicodeDecodeError, LookupError) as exc:
        return f"decode diverged from plan ({exc})"  # unreachable: hash matched (decision 4)
    ws = config.whitespace
    transformed, text_ops = apply_text_transforms(
        text,
        classify_suffix(_suffix(action.path)),
        trim_trailing_ws=ws.trim_trailing,
        final_newline=ws.ensure_final_newline,
        collapse_max=ws.collapse_blank_lines,
        tab_width=ws.tab_width if ws.normalize_tabs else None,
    )
    if non_whitespace_count(transformed) < non_whitespace_count(text):
        return "shrink-invariant"
    operations: list[Operation] = []
    if bom is not None or encoding_name != "utf-8":
        operations.append("reencode")
    operations.extend(text_ops)
    if action.target_path is not None:
        operations.append("rename")
    if operations != action.operations:
        return f"recomputed operations {operations} != planned {action.operations}"
    return encode_utf8(transformed)


def _record(
    manifest: ManifestWriter | None,
    action: PlanAction,
    kind: ManifestOperation,
    source: Path,
    target: Path | None,
    backup_path: Path | None,
    after: str | None,
    overwritten_sha: str | None,
    overwritten_backup: Path | None,
    run_id: str,
    outcome: ApplyOutcome,
    identities: _Identities | None = None,
) -> None:
    if manifest is None:
        return
    manifest.append(
        ManifestRecord(
            run_id=run_id,
            action_id=action.action_id,
            docmend_id=action.docmend_id,
            seq=1,  # stamped by the writer
            recorded_at="1970-01-01T00:00:00+00:00",  # stamped by the writer
            operation=kind,
            original_path=str(source.resolve()),
            target_path=str((target if target is not None else source).resolve()),
            backup_path=str(backup_path) if backup_path is not None else None,
            before_sha256=action.source_sha256,
            after_sha256=after,
            result="applied" if outcome.status == "applied" else "failed",
            error=outcome.error,
            overwritten_sha256=overwritten_sha,
            overwritten_backup_path=str(overwritten_backup)
            if overwritten_backup is not None
            else None,
            source_identity=identities.source if identities is not None else None,
            target_identity=identities.target if identities is not None else None,
            expected_published_identity=identities.expected if identities is not None else None,
        )
    )


@dataclass(frozen=True)
class _Identities:
    """The three durable object identities an intent persists (adr-0019 F4):
    what the terminal must repeat verbatim and what post-kill adjudication
    lstat-compares against."""

    source: ObjectIdentity
    target: ObjectIdentity | None
    expected: ObjectIdentity


def _undo_publish(
    target: Path,
    expected_identity: ObjectIdentity,
    target_bound: BoundFile | None,
    *,
    survivor: tuple[Path, ObjectIdentity],
    root_resolved: Path,
    hooks: CommitHooks,
) -> bool:
    """Undo a two-step publish only when the pre-action state is provable.

    A no-clobber rollback removes the published name only after containment,
    target identity, and the surviving source are re-authorized. A clobber
    rollback restores the descriptor-bound target bytes and mode through the
    stage-first replacement primitive; inode resurrection is impossible, so
    the durable overwritten backup remains the recovery contract.
    """
    if target_bound is None:
        survivor_path, survivor_identity = survivor
        hooks.before_step("rollback", target)
        if not (target.parent.resolve() / target.name).is_relative_to(root_resolved):
            return False
        observed = _observe_name(target)
        if observed == "unobservable":
            return False
        hooks.before_step("rollback-survivor", survivor_path)
        try:
            # The survivor is the final proof before deletion. Losing it here
            # makes the published output a possible last useful copy.
            check_bound(survivor_path, survivor_identity, root_resolved=root_resolved)
        except InterferenceError:
            return False
        if observed != expected_identity:
            return True
        try:
            target.unlink()
        except OSError:
            return False
        return True
    try:
        guarded_replace(
            target,
            target_bound.data,
            expected=expected_identity,
            mode=target_bound.mode,
            root_resolved=root_resolved,
            hooks=hooks,
            survivor=survivor,
            step="rollback",
        )
    # PEP 758 (py314): reads as `except (InterferenceError, WriteError)`, NOT the
    # Python-2 `except InterferenceError as WriteError`. Ruff's py314 formatter
    # strips the parentheses from a bare (no-`as`) except, so this form is
    # formatter-mandated, not a Python-2 defect.
    except InterferenceError, WriteError:
        return False
    return True


def _record_intent(
    manifest: ManifestWriter | None,
    action: PlanAction,
    kind: ManifestOperation,
    source: Path,
    target: Path,
    backup_path: Path | None,
    after: str,
    overwritten_sha: str | None,
    overwritten_backup: Path | None,
    run_id: str,
    identities: _Identities,
) -> None:
    """The 2.0 write-ahead record, appended (and fsync'd) BEFORE any corpus
    name is touched — for EVERY mutation kind (adr-0019, DMR-04), not only
    the multi-step one. after_sha256 carries the EXPECTED output hash and the
    identity fields carry the exact objects the mutation is about to touch —
    that is what lets adjudication decide from disk state alone whether (and
    how far) the mutation happened."""
    if manifest is None:
        return
    manifest.append(
        ManifestRecord(
            run_id=run_id,
            action_id=action.action_id,
            docmend_id=action.docmend_id,
            seq=1,  # stamped by the writer
            recorded_at="1970-01-01T00:00:00+00:00",  # stamped by the writer
            operation=kind,
            original_path=str(source.resolve()),
            target_path=str(target.resolve()),
            backup_path=str(backup_path) if backup_path is not None else None,
            before_sha256=action.source_sha256,
            after_sha256=after,
            result="intent",
            error=None,
            overwritten_sha256=overwritten_sha,
            overwritten_backup_path=str(overwritten_backup)
            if overwritten_backup is not None
            else None,
            source_identity=identities.source,
            target_identity=identities.target,
            expected_published_identity=identities.expected,
        )
    )


def _adjudicate_pending_intent(
    run: _ApplyRun,
    action_id: str,
) -> ApplyOutcome | None:
    """Resume decision for a DANGLING intent (2.0, adr-0019): the shared
    adjudication table classifies the crash-after disk state against the
    intent's persisted hashes and identities. `None` means the mutation never
    happened — the action executes normally, still behind the FR-003 guard.

    §13.5 containment runs first, symmetric with `_execute_action`: the
    record's ABSOLUTE paths come from an operator-supplied manifest, and the
    finish arm below can unlink a name — a crafted/wrong record must never
    read or mutate outside the plan's source root. (read_manifest_set already
    proved containment for CLI inputs; this engine-level belt keeps direct
    library callers honest until Plan C's WriteSafetyContext.)
    """
    try:
        action = run.actions[action_id]
        state = run.lifecycle[action_id]
    except KeyError as exc:
        raise KeyError(f"{action_id}: not in gated plan/resume state") from exc
    record = state.record
    source = Path(record.original_path)
    target = Path(record.target_path)
    for candidate in (source, target):
        if not candidate.resolve().is_relative_to(run.root_resolved):
            return _failed(
                action,
                "ERR-002",
                f"{candidate}: intent record path resolves outside the plan's "
                f"source root; refusing reconciliation",
            )
    verdict = adjudicate_dangling_intent(record)
    if verdict.verdict == "never-happened":
        return None
    if verdict.verdict == "external-interference":
        return _failed(
            action,
            "ERR-002",
            f"{target}: {verdict.detail} — changed since the intent recorded in {record.run_id}",
        )
    if verdict.verdict == "finish-remaining":
        try:
            finish_remaining(record, root_resolved=run.root_resolved, hooks=run.hooks)
        except WriteError as exc:
            return _failed(action, "ERR-003", str(exc))
    # The resuming run stamps the terminal that closes the prior intent.
    run.manifest.append(record.model_copy(update={"result": "applied", "run_id": run.run_id}))
    return ApplyOutcome(
        action_id=action.action_id,
        path=action.path,
        status="applied",
        before_sha256=action.source_sha256,
        after_sha256=record.after_sha256,
        skip_reason=None,
        error=None,
    )


def _reconcile_completed(action: PlanAction, record: ManifestRecord) -> ApplyOutcome:
    """The adr-0006 resume decision for an action a prior manifest records as
    applied: skip `already-applied` when the live output still matches the
    recorded after-hash; otherwise fail ERR-002 — the file changed (or
    vanished) since docmend applied it, and resume must surface external
    interference, never silently proceed past it. Read-only by construction,
    so it is safe in dry-run resume too (NFR-004)."""
    final_path = Path(record.target_path)
    try:
        data = final_path.read_bytes()
    except OSError as exc:
        return _failed(
            action,
            "ERR-002",
            f"{final_path}: recorded applied in {record.run_id} but output is "
            f"missing/unreadable on resume ({exc.strerror or exc})",
        )
    if record.after_sha256 is None or _sha(data) != record.after_sha256:
        return _failed(
            action,
            "ERR-002",
            f"{final_path}: output no longer matches the after-hash recorded in "
            f"{record.run_id} (changed since apply; resume reconciliation)",
        )
    return _skip(action, "already-applied")


def _execute_action(
    run: _ApplyRun,
    action_id: str,
) -> tuple[ApplyOutcome, bool]:
    try:
        action = run.actions[action_id]
    except KeyError as exc:
        raise KeyError(f"{action_id}: not in gated plan") from exc
    source_root = run.source_root
    root_resolved = run.root_resolved
    config = run.config
    options = run.options
    include = run.include
    exclude = run.exclude
    manifest = run.manifest
    run_id = run.run_id
    hooks = run.hooks
    log = get_logger(__name__)
    source = source_root / action.path
    target = source_root / action.target_path if action.target_path is not None else None
    # §13.5 containment BEFORE the descriptor opens: a parent dir swapped for a
    # symlink since plan time is followed by bind_file's O_NOFOLLOW (which only
    # guards the final component), so an out-of-root file's bytes would be read
    # and its path logged before mutation is refused. Resolve-and-contain first,
    # matching the stricter write side (check_bound re-resolves), and skip
    # without opening the file. The post-bind check below remains the mutation
    # gate; this pre-check is additive.
    for candidate in (source, *((target,) if target is not None else ())):
        if not candidate.resolve().is_relative_to(root_resolved):
            return _skip(action, "containment"), False
    # FR-003 + adr-0020: one non-following descriptor supplies the bytes for
    # hashing, recomputation, and backup plus the identity later commit steps
    # re-check. A pathname read could silently follow an interposed symlink.
    try:
        bound = bind_file(source)
    except InterferenceError as exc:
        log.info("commit boundary refusal at bind", path=action.path, detail=str(exc))
        return _skip(action, "external-interference"), False
    except OSError:
        return _skip(action, "unreadable"), False  # ERR-005
    data = bound.data
    # DEV-001 commit-boundary re-check: plan-time hard-link skipping
    # (planning.py:68) is the primary gate. A file with st_nlink==1 at plan time
    # that gains a second link before apply would otherwise be mutated — replace
    # forges a fresh inode at the source name and the alias silently keeps the
    # old bytes, bypassing the EC-011 skip-and-report intent. bind_file already
    # captured st_nlink, so closing the plan->apply window is O(1); the reason
    # literal matches planning's `hard-link-alias`.
    if bound.nlink > 1:
        return _skip(action, "hard-link-alias"), False
    if _sha(data) != action.source_sha256:
        return _skip(action, "stale-hash"), False  # ERR-002, AW-004
    # FR-012: snapshot filters hold at apply exactly as at scan/plan.
    if not include.match_file(action.path) or exclude.match_file(action.path):
        return _skip(action, "excluded"), False
    # §13.5 runtime containment: a parent dir swapped for a symlink since plan
    # time must not carry the write outside the root (re-checked post-bind
    # against the same objects bound above).
    for candidate in (source, *((target,) if target is not None else ())):
        if not candidate.resolve().is_relative_to(root_resolved):
            return _skip(action, "containment"), False

    recomputed = _recompute(action, data, config)
    if recomputed == "shrink-invariant":
        return _skip(action, "shrink-invariant"), False  # EC-005 apply half
    if isinstance(recomputed, str):
        return _failed(action, "ERR-006", recomputed), False
    payload = recomputed
    kind = _operation_kind(action)

    clobber = False
    if target is not None and target.exists():
        policy = config.rename.on_collision
        if policy == "skip":
            return _skip(action, "collision"), False  # AW-002
        if policy == "fail":
            return _skip(action, "collision"), True  # non-zero abort (FR-011)
        # The gate sees only targets present during preflight; a later arrival
        # still requires the same byte-preserving strategy at action time.
        if not strategy_active(options):
            return _skip(action, "collision-unpreserved"), False
        clobber = True  # policy == "overwrite"

    overwritten_sha: str | None = None
    overwritten_backup: Path | None = None
    target_bound: BoundFile | None = None
    if clobber:
        assert target is not None
        try:
            # Backup and the later pre-replace check refer to the same object:
            # one descriptor supplies its bytes, identity, and mode.
            target_bound = bind_file(target)
        except InterferenceError as exc:
            log.info("commit boundary refusal at target bind", path=action.path, detail=str(exc))
            return _skip(action, "external-interference"), False
        except OSError as exc:
            outcome = _failed(
                action, "ERR-003", f"{target}: unreadable for overwrite backup ({exc})"
            )
            _record(manifest, action, kind, source, target, None, None, None, None, run_id, outcome)
            return outcome, False
        overwritten_sha = _sha(target_bound.data)
        if options.backup_root is not None:
            try:
                overwritten_backup = backup_file(
                    target_bound.data,
                    backup_root=options.backup_root,
                    run_id=run_id,
                    action_seq=_action_seq(action),
                    role="overwritten",
                    relative_path=str(action.target_path),
                    expected_sha256=overwritten_sha,
                )
            except BackupError as exc:
                outcome = _failed(action, "ERR-004", str(exc))
                _record(
                    manifest,
                    action,
                    kind,
                    source,
                    target,
                    None,
                    None,
                    overwritten_sha,
                    None,
                    run_id,
                    outcome,
                )
                return outcome, False

    backup_path: Path | None = None
    if options.backup_root is not None:
        try:
            backup_path = backup_file(
                data,
                backup_root=options.backup_root,
                run_id=run_id,
                action_seq=_action_seq(action),
                role="source",
                relative_path=action.path,
                expected_sha256=action.source_sha256,
            )
        except BackupError as exc:
            outcome = _failed(action, "ERR-004", str(exc))  # backup abort, original untouched
            _record(
                manifest,
                action,
                kind,
                source,
                target,
                backup_path,
                None,
                overwritten_sha,
                overwritten_backup,
                run_id,
                outcome,
            )
            return outcome, False

    content = is_content_rewrite(action)
    after = _sha(payload) if content else action.source_sha256

    # ---- Journal-every-mutation (adr-0019, DMR-04): capture the identities,
    # stage any replacement output FIRST (a tool-owned O_EXCL temp is not
    # corpus mutation), append the fsync'd intent, mutate, append the
    # terminal. A staging or stat failure is PRE-mutation: it records
    # `failed` with no intent, asserting no corpus name was touched.
    staged: StagedWrite | None = None
    try:
        if kind in ("rewrite", "rename_and_rewrite"):
            staged = stage_bytes(
                target if kind == "rename_and_rewrite" else source,  # type: ignore[arg-type]
                payload,
                mode=bound.mode,
            )
    except (WriteError, OSError) as exc:
        outcome = _failed(action, "ERR-003", str(exc))
        _record(
            manifest,
            action,
            kind,
            source,
            target,
            backup_path,
            None,
            overwritten_sha,
            overwritten_backup,
            run_id,
            outcome,
        )
        return outcome, False

    identities = _Identities(
        source=bound.identity,
        target=target_bound.identity if target_bound is not None else None,
        # Replacement publishes move the STAGED inode onto the target name;
        # pure renames move the source inode. Either way the identity is
        # knowable before any corpus name changes.
        expected=staged.identity if staged is not None else bound.identity,
    )
    _record_intent(
        manifest,
        action,
        kind,
        source,
        target if target is not None else source,
        backup_path,
        after,
        overwritten_sha,
        overwritten_backup,
        run_id,
        identities,
    )
    try:
        if kind == "rewrite":
            assert staged is not None
            hooks.before_step("publish", source)
            check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)
            check_bound(source, bound.identity, root_resolved=root_resolved)
            publish_staged(staged, source)
        elif kind == "rename":
            assert target is not None
            if clobber:
                assert target_bound is not None
                hooks.before_step("replace-target", target)
                check_bound(source, bound.identity, root_resolved=root_resolved)
                check_bound(target, target_bound.identity, root_resolved=root_resolved)
                rename_overwrite(source, target)
            else:
                guarded_rename_no_clobber(
                    source,
                    target,
                    bound.identity,
                    root_resolved=root_resolved,
                    hooks=hooks,
                )
        else:  # rename_and_rewrite
            assert target is not None
            assert staged is not None
            hooks.before_step("publish", target)
            check_bound(staged.tmp, staged.identity, root_resolved=root_resolved)
            check_bound(source, bound.identity, root_resolved=root_resolved)
            if clobber:
                assert target_bound is not None
                check_bound(target, target_bound.identity, root_resolved=root_resolved)
            else:
                check_destination(target, root_resolved=root_resolved)
            publish_staged(staged, target, clobber=clobber)
            hooks.before_step("unlink", source)
            try:
                check_bound(source, bound.identity, root_resolved=root_resolved)
            except InterferenceError as source_exc:
                rolled_back = _undo_publish(
                    target,
                    staged.identity,
                    target_bound,
                    survivor=(source, bound.identity),
                    root_resolved=root_resolved,
                    hooks=hooks,
                )
                state = "publish rolled back" if rolled_back else "published output retained"
                msg = f"{source_exc}; {state}, original's pre-action state unprovable"
                raise InterferenceError(msg, intermediate=True) from source_exc
            try:
                check_bound(target, staged.identity, root_resolved=root_resolved)
            except InterferenceError as survivor_exc:
                if clobber:
                    msg = f"{survivor_exc}; clobbered target unrecovered at a foreign name"
                    raise InterferenceError(msg, intermediate=True) from survivor_exc
                raise
            try:
                source.unlink()
            except OSError as unlink_exc:
                if not _undo_publish(
                    target,
                    staged.identity,
                    target_bound,
                    survivor=(source, bound.identity),
                    root_resolved=root_resolved,
                    hooks=hooks,
                ):
                    msg = (
                        f"{source}: target published but source not removed "
                        f"({unlink_exc.strerror or unlink_exc}); publish rollback unproven"
                    )
                    raise InterferenceError(msg, intermediate=True) from unlink_exc
                msg = (
                    f"{source}: target published but source not removed; publish "
                    f"rolled back ({unlink_exc.strerror or unlink_exc})"
                )
                raise WriteError(msg) from unlink_exc
            # Durability symmetry with the staged publish above: make the source
            # entry's removal survive a crash so a remount cannot resurrect it.
            fsync_dir(source.parent)
    except InterferenceError as exc:
        if staged is not None:
            abort_staged(staged, root_resolved=root_resolved)
        if exc.intermediate:
            log.error(
                "commit interference with unproven rollback; intent left for adjudication",
                path=action.path,
                detail=str(exc),
            )
            return _failed(action, "ERR-002", f"{exc} (resume adjudicates)"), False
        interference = _failed(action, "ERR-002", f"{exc} (adr-0020 commit boundary)")
        _record(
            manifest,
            action,
            kind,
            source,
            target,
            backup_path,
            None,
            overwritten_sha,
            overwritten_backup,
            run_id,
            interference,
            identities,
        )
        return _skip(action, "external-interference"), False
    except FileExistsError:
        # No-clobber race lost (FR-011): a target appeared inside the
        # check-to-publish window — external interference with the corpus
        # (ERR-002). Nothing mutated; the intent must not dangle for a live
        # run, so it closes with a failed terminal while the REPORT keeps the
        # collision skip (the reviewable outcome).
        race_outcome = _failed(
            action,
            "ERR-002",
            f"{target}: no-clobber publish lost a collision race (DMR-07); no mutation occurred",
        )
        _record(
            manifest,
            action,
            kind,
            source,
            target,
            backup_path,
            None,
            overwritten_sha,
            overwritten_backup,
            run_id,
            race_outcome,
            identities,
        )
        return _skip(action, "collision-unpreserved"), False
    except (WriteError, OSError) as exc:
        outcome = _failed(action, "ERR-003", str(exc))
        _record(
            manifest,
            action,
            kind,
            source,
            target,
            backup_path,
            None,
            overwritten_sha,
            overwritten_backup,
            run_id,
            outcome,
            identities,
        )
        return outcome, False

    outcome = ApplyOutcome(
        action_id=action.action_id,
        path=action.path,
        status="applied",
        before_sha256=action.source_sha256,
        after_sha256=after,
        skip_reason=None,
        error=None,
    )
    _record(
        manifest,
        action,
        kind,
        source,
        target,
        backup_path,
        after,
        overwritten_sha,
        overwritten_backup,
        run_id,
        outcome,
        identities,
    )
    return outcome, False


def _validate_resume_lifecycle(
    resume_chain: ManifestChain | None,
) -> dict[str, ActionLifecycle]:
    lifecycle = reduce_lifecycle(resume_chain) if resume_chain is not None else {}
    for state in lifecycle.values():
        if state.state in ("pending-restore", "restored", "restore-failed"):
            msg = (
                f"{state.record.action_id}: resume input contains restore-kind evidence; "
                "re-application after restore requires a fresh plan"
            )
            raise ArtifactError(msg)
    return lifecycle


def _preview_pending_intent(
    action: PlanAction, record: ManifestRecord, root_resolved: Path
) -> ApplyOutcome | None:
    for candidate in (Path(record.original_path), Path(record.target_path)):
        if not candidate.resolve().is_relative_to(root_resolved):
            return _failed(action, "ERR-002", f"{candidate}: intent escapes the plan root")
    verdict = adjudicate_dangling_intent(record)
    if verdict.verdict == "never-happened":
        return None
    if verdict.verdict == "external-interference":
        return _failed(action, "ERR-002", verdict.detail)
    return ApplyOutcome(
        action_id=action.action_id,
        path=action.path,
        status="would_apply",
        before_sha256=action.source_sha256,
        after_sha256=None,
        skip_reason=None,
        error=None,
    )


def _preview_action(
    action: PlanAction,
    source_root: Path,
    root_resolved: Path,
    config: DocmendConfig,
    include: PathSpec[GitIgnoreSpecPattern],
    exclude: PathSpec[GitIgnoreSpecPattern],
) -> tuple[ApplyOutcome, bool]:
    """Classify one action without any mutation-capable dependency."""
    source = source_root / action.path
    try:
        data = bind_file(source).data
    except InterferenceError:
        return _skip(action, "external-interference"), False
    except OSError:
        return _skip(action, "unreadable"), False
    if _sha(data) != action.source_sha256:
        return _skip(action, "stale-hash"), False
    if not include.match_file(action.path) or exclude.match_file(action.path):
        return _skip(action, "excluded"), False
    target = source_root / action.target_path if action.target_path is not None else None
    for candidate in (source, *((target,) if target is not None else ())):
        if not candidate.resolve().is_relative_to(root_resolved):
            return _skip(action, "containment"), False
    recomputed = _recompute(action, data, config)
    if recomputed == "shrink-invariant":
        return _skip(action, "shrink-invariant"), False
    if isinstance(recomputed, str):
        return _failed(action, "ERR-006", recomputed), False
    if target is not None and target.exists():
        if config.rename.on_collision == "skip":
            return _skip(action, "collision"), False
        if config.rename.on_collision == "fail":
            return _skip(action, "collision"), True
    return (
        ApplyOutcome(
            action_id=action.action_id,
            path=action.path,
            status="would_apply",
            before_sha256=action.source_sha256,
            after_sha256=None,
            skip_reason=None,
            error=None,
        ),
        False,
    )


def _complete_outcomes(
    plan: Plan, outcomes: list[ApplyOutcome], *, abort: bool
) -> list[ApplyOutcome]:
    if abort:
        outcomes.extend(
            ApplyOutcome(
                action_id=action.action_id,
                path=action.path,
                status="not-attempted",
                before_sha256=action.source_sha256,
                after_sha256=None,
                skip_reason=None,
                error=None,
            )
            for action in plan.actions[len(outcomes) :]
        )
    return outcomes


def _build_report(
    *,
    run_id: str,
    plan_ref: ArtifactRef,
    started_at: str,
    completed_at: str,
    outcomes: list[ApplyOutcome],
    dry_run: bool,
    prior_attempt: PriorAttempt | None,
) -> Report:
    counts = Counter(outcome.status for outcome in outcomes)
    return Report(
        run_id=run_id,
        generated_by=f"docmend {__version__}",
        plan_ref=plan_ref,
        dry_run=dry_run,
        started_at=started_at,
        completed_at=completed_at,
        outcomes=outcomes,
        totals=ReportTotals(
            applied=counts.get("applied", 0),
            would_apply=counts.get("would_apply", 0),
            skipped=counts.get("skipped", 0),
            failed=counts.get("failed", 0),
            not_attempted=counts.get("not-attempted", 0),
        ),
        prior_attempt=prior_attempt,
        manifest_sha256=None,
    )


def preview_plan(
    plan: Plan,
    config: DocmendConfig,
    *,
    run_id: str,
    plan_ref: ArtifactRef,
    started_at: str,
    now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(),
    resume_chain: ManifestChain | None = None,
    prior_attempt: PriorAttempt | None = None,
    heartbeat: ProgressHeartbeat | None = None,
) -> Report:
    """Preview a plan through a structurally read-only engine."""
    assert plan.source_root is not None
    source_root = Path(plan.source_root)
    root_resolved = source_root.resolve()
    include = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.include)
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude)
    lifecycle = _validate_resume_lifecycle(resume_chain)
    outcomes: list[ApplyOutcome] = []
    abort = False
    skipped_count = failed_count = 0
    log = get_logger(__name__)
    for processed, action in enumerate(plan.actions, start=1):
        if abort:
            break
        state = lifecycle.get(action.action_id)
        outcome = None
        if state is not None and state.state == "pending-intent":
            outcome = _preview_pending_intent(action, state.record, root_resolved)
        elif state is not None and state.state == "applied":
            outcome = _reconcile_completed(action, state.record)
        if outcome is None:
            outcome, abort = _preview_action(
                action, source_root, root_resolved, config, include, exclude
            )
        outcomes.append(outcome)
        skipped_count += outcome.status == "skipped"
        failed_count += outcome.status == "failed"
        log.info(
            "apply outcome",
            path=action.path,
            status=outcome.status,
            reason=outcome.skip_reason,
            action=action.action_id,
        )
        if heartbeat is not None:
            heartbeat.advance(
                processed=processed,
                skipped=skipped_count,
                failed=failed_count,
            )
    _complete_outcomes(plan, outcomes, abort=abort)
    return _build_report(
        run_id=run_id,
        plan_ref=plan_ref,
        started_at=started_at,
        completed_at=now(),
        outcomes=outcomes,
        dry_run=True,
        prior_attempt=prior_attempt,
    )


def execute_plan(
    *,
    run_id: str,
    manifest_path: Path,
    started_at: str,
    safety: WriteSafetyContext,
    now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(),
    hooks: CommitHooks = NO_HOOKS,
    heartbeat: ProgressHeartbeat | None = None,
) -> Report:
    """Execute only the immutable plan/options licensed by a live capability."""
    safety.confirm_apply(run_id=run_id, manifest_path=manifest_path)
    plan, config, plan_ref, options, resume_chain, prior_attempt = safety._consume_apply_state()  # pyright: ignore[reportPrivateUsage]
    if not options.write:
        raise RuntimeError("write capability carried non-write options")
    assert plan.source_root is not None
    source_root = Path(plan.source_root)
    root_resolved = source_root.resolve()
    lifecycle = _validate_resume_lifecycle(resume_chain)
    prior_manifest_sha256 = resume_chain.sets[-1].sha256 if resume_chain.sets else None
    outcomes: list[ApplyOutcome] = []
    abort = False
    skipped_count = failed_count = 0
    if plan.actions:
        manifest = ManifestWriter(
            manifest_path,
            header=ManifestHeader(
                run_id=run_id,
                kind="apply",
                source_root=str(root_resolved),
                backup_root=str(options.backup_root.resolve())
                if options.backup_root is not None
                else None,
                plan_sha256=plan_ref.sha256,
                prior_manifest_sha256=prior_manifest_sha256,
                prior_attempt=prior_attempt,
                effective_excludes=tuple(config.paths.exclude),
                created_at=now(),
            ),
            now=now,
        )
        run = _ApplyRun(
            _token=_ENGINE_TOKEN,
            safety=safety,
            plan=plan,
            config=config,
            source_root=source_root,
            root_resolved=root_resolved,
            options=options,
            run_id=run_id,
            manifest=manifest,
            hooks=hooks,
            include=PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.include),
            exclude=PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude),
            actions={action.action_id: action for action in plan.actions},
            lifecycle=lifecycle,
        )
        log = get_logger(__name__)
        try:
            for processed, action in enumerate(plan.actions, start=1):
                if abort:
                    break
                state = lifecycle.get(action.action_id)
                outcome = None
                if state is not None and state.state == "pending-intent":
                    outcome = _adjudicate_pending_intent(run, action.action_id)
                elif state is not None and state.state == "applied":
                    outcome = _reconcile_completed(action, state.record)
                if outcome is None:
                    outcome, abort = _execute_action(run, action.action_id)
                outcomes.append(outcome)
                skipped_count += outcome.status == "skipped"
                failed_count += outcome.status == "failed"
                log.info(
                    "apply outcome",
                    path=action.path,
                    status=outcome.status,
                    reason=outcome.skip_reason,
                    action=action.action_id,
                )
                if heartbeat is not None:
                    heartbeat.advance(
                        processed=processed,
                        skipped=skipped_count,
                        failed=failed_count,
                    )
        finally:
            manifest.close()
    _complete_outcomes(plan, outcomes, abort=abort)
    return _build_report(
        run_id=run_id,
        plan_ref=plan_ref,
        started_at=started_at,
        completed_at=now(),
        outcomes=outcomes,
        dry_run=False,
        prior_attempt=prior_attempt,
    )
