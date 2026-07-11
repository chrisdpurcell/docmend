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
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import structlog
from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from docmend import __version__
from docmend.artifacts import ArtifactError
from docmend.config import DocmendConfig
from docmend.discovery import sniff_bom
from docmend.lineage import ObjectIdentity, PriorAttempt
from docmend.observability import get_logger
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
    _observe_name,  # pyright: ignore[reportPrivateUsage] - shared rollback observation.
    bind_file,
    check_bound,
    check_destination,
    guarded_rename_no_clobber,
    guarded_replace,
)
from docmend.writer.gate import ApplyOptions, is_content_rewrite, strategy_active
from docmend.writer.manifest import (
    ManifestChain,
    ManifestHeader,
    ManifestOperation,
    ManifestRecord,
    ManifestWriter,
    reduce_lifecycle,
)


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


def _recompute(
    action: PlanAction, data: bytes, config: DocmendConfig
) -> tuple[bytes, list[Operation]] | str:
    """Re-derive the output bytes and operation list; a str return is an error message."""
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
    return encode_utf8(transformed), operations


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
    action: PlanAction,
    record: ManifestRecord,
    root_resolved: Path,
    options: ApplyOptions,
    manifest: ManifestWriter | None,
    run_id: str,
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
    source = Path(record.original_path)
    target = Path(record.target_path)
    for candidate in (source, target):
        if not candidate.resolve().is_relative_to(root_resolved):
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
    if not options.write:
        return ApplyOutcome(
            action_id=action.action_id,
            path=action.path,
            status="would_apply",
            before_sha256=action.source_sha256,
            after_sha256=None,
            skip_reason=None,
            error=None,
        )
    if verdict.verdict == "finish-remaining":
        try:
            finish_remaining(record)
        except WriteError as exc:
            return _failed(action, "ERR-003", str(exc))
    if manifest is not None:
        # The adjudication terminal (adr-0019): the intent's immutable fields
        # verbatim; seq/recorded_at re-stamped by the writer; run_id is the
        # resuming run's — it is the run asserting this evidence. Chain scope
        # proves it closes exactly this dangling intent (CR-NEW-002).
        manifest.append(record.model_copy(update={"result": "applied", "run_id": run_id}))
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
    action: PlanAction,
    source_root: Path,
    root_resolved: Path,
    config: DocmendConfig,
    options: ApplyOptions,
    include: PathSpec[GitIgnoreSpecPattern],
    exclude: PathSpec[GitIgnoreSpecPattern],
    manifest: ManifestWriter | None,
    run_id: str,
    log: structlog.stdlib.BoundLogger,
    hooks: CommitHooks,
) -> tuple[ApplyOutcome, bool]:
    source = source_root / action.path
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
    if _sha(data) != action.source_sha256:
        return _skip(action, "stale-hash"), False  # ERR-002, AW-004
    # FR-012: snapshot filters hold at apply exactly as at scan/plan.
    if not include.match_file(action.path) or exclude.match_file(action.path):
        return _skip(action, "excluded"), False
    # §13.5 runtime containment: a parent dir swapped for a symlink since plan
    # time must not carry the write outside the root.
    target = source_root / action.target_path if action.target_path is not None else None
    for candidate in (source, *((target,) if target is not None else ())):
        if not candidate.resolve().is_relative_to(root_resolved):
            return _skip(action, "containment"), False

    recomputed = _recompute(action, data, config)
    if recomputed == "shrink-invariant":
        return _skip(action, "shrink-invariant"), False  # EC-005 apply half
    if isinstance(recomputed, str):
        return _failed(action, "ERR-006", recomputed), False
    payload, _operations = recomputed
    kind = _operation_kind(action)

    clobber = False
    if target is not None and target.exists():
        policy = config.rename.on_collision
        if policy == "skip":
            return _skip(action, "collision"), False  # AW-002
        if policy == "fail":
            return _skip(action, "collision"), True  # non-zero abort (FR-011)
        # Overwrite preservation is an action-time invariant. The gate sees
        # only targets that exist during preflight; a later arrival is legal to
        # clobber only under the same byte-preserving strategy. Dry-run options
        # are synthesized without strategy flags, so preview retains the
        # collision behavior the corresponding configured write would take.
        if options.write and not strategy_active(options):
            return _skip(action, "collision-unpreserved"), False
        clobber = True  # policy == "overwrite"

    if not options.write:
        # Dry-run boundary (codex CR-001): collision state was INSPECTED above,
        # but nothing past this line may run — in particular no backup_file
        # call for a would-be-clobbered target. FR-004/NFR-004: a dry run
        # writes nothing but its report and log.
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


def execute_plan(
    plan: Plan,
    config: DocmendConfig,
    *,
    run_id: str,
    plan_ref: ArtifactRef,
    plan_sha256: str,
    options: ApplyOptions,
    manifest_path: Path,
    started_at: str,
    now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(),
    resume_chain: ManifestChain | None = None,
    prior_manifest_sha256: str | None = None,
    prior_attempt: PriorAttempt | None = None,
    hooks: CommitHooks = NO_HOOKS,
) -> Report:
    log = get_logger(__name__)
    assert plan.source_root is not None  # CLI refused earlier (ERR-006)
    source_root = Path(plan.source_root)
    root_resolved = source_root.resolve()
    include = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.include)
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude)

    # FR-013 (adr-0019): ONE lifecycle reducer drives resume — the same fold
    # restore and verify consume. Chain order then seq decides which record is
    # an action's newest evidence; the old per-consumer (recorded_at, seq)
    # interpretation is deleted. A `pending-intent` state is a kill inside
    # that action's mutation window, adjudicated from disk; restore-family
    # states cannot legally reach an apply resume (the chain rules reject the
    # shapes; re-application after restore requires a fresh plan).
    lifecycle = reduce_lifecycle(resume_chain) if resume_chain is not None else {}
    for state in lifecycle.values():
        if state.state in ("pending-restore", "restored", "restore-failed"):
            msg = (
                f"{state.record.action_id}: resume input contains restore-kind "
                f"evidence — re-application after a restore requires a fresh plan "
                f"(adr-0019)"
            )
            raise ArtifactError(msg)

    outcomes: list[ApplyOutcome] = []
    manifest: ManifestWriter | None = None
    if options.write and plan.actions:
        # 2.0: the run's envelope lives in the header (adr-0019) — restore keys
        # its lock on header.source_root, so it must match plan/apply's key:
        # the RESOLVED root. backup_root is the F5 trust anchor.
        manifest = ManifestWriter(
            manifest_path,
            header=ManifestHeader(
                run_id=run_id,
                kind="apply",
                source_root=str(root_resolved),
                backup_root=str(options.backup_root.resolve())
                if options.backup_root is not None
                else None,
                plan_sha256=plan_sha256,
                prior_manifest_sha256=prior_manifest_sha256,
                prior_attempt=prior_attempt,
                created_at=now(),
            ),
            now=now,
        )
    try:
        abort = False
        for action in plan.actions:
            if abort:
                break
            state = lifecycle.get(action.action_id)
            outcome = None
            if state is not None and state.state == "pending-intent":
                # A None verdict means the mutation never happened, so the
                # action executes normally below (FR-003 guard intact).
                outcome = _adjudicate_pending_intent(
                    action, state.record, root_resolved, options, manifest, run_id
                )
            elif state is not None and state.state == "applied":
                outcome = _reconcile_completed(action, state.record)
            # state "failed" (a recorded prior failure) retries normally —
            # the failed → intent → applied transition is chain-legal.
            if outcome is None:
                outcome, abort = _execute_action(
                    action,
                    source_root,
                    root_resolved,
                    config,
                    options,
                    include,
                    exclude,
                    manifest,
                    run_id,
                    log,
                    hooks,
                )
            outcomes.append(outcome)
            log.info(
                "apply outcome",
                path=action.path,
                status=outcome.status,
                reason=outcome.skip_reason,
                action=action.action_id,
            )
    finally:
        if manifest is not None:
            manifest.close()

    # Report 2.0 partition invariant (adr-0019, DMR-05 accounting): a
    # `fail`-policy abort left trailing actions unexecuted — each gets an
    # explicit `not-attempted` outcome so every plan action appears exactly
    # once and verify can prove full coverage.
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

    counts = Counter(outcome.status for outcome in outcomes)
    return Report(
        run_id=run_id,
        generated_by=f"docmend {__version__}",
        plan_ref=plan_ref,
        dry_run=not options.write,
        started_at=started_at,
        completed_at=now(),
        outcomes=outcomes,
        totals=ReportTotals(
            applied=counts.get("applied", 0),
            would_apply=counts.get("would_apply", 0),
            skipped=counts.get("skipped", 0),
            failed=counts.get("failed", 0),
            not_attempted=counts.get("not-attempted", 0),
        ),
        # Redundant attempt-lineage edge (design F6 round 5): identical to the
        # manifest header's. manifest_sha256 is stamped by the CLI after the
        # manifest CLOSES (null when the run mutated nothing).
        prior_attempt=prior_attempt,
        manifest_sha256=None,
    )
