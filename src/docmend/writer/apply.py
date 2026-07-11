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
from datetime import UTC, datetime
from pathlib import Path

import structlog
from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from docmend import __version__
from docmend.config import DocmendConfig
from docmend.discovery import sniff_bom
from docmend.lineage import PriorAttempt
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
from docmend.writer.atomic import (
    WriteError,
    atomic_write_bytes,
    rename_no_clobber,
    rename_overwrite,
)
from docmend.writer.backup import BackupError, backup_file
from docmend.writer.gate import ApplyOptions, is_content_rewrite
from docmend.writer.manifest import (
    ManifestHeader,
    ManifestOperation,
    ManifestRecord,
    ManifestWriter,
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
        )
    )


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
) -> None:
    """The 1.3 write-ahead record for a multi-step mutation: appended (and
    fsync'd) BEFORE the target publish so a hard kill anywhere in the
    publish→unlink→record window leaves reconcilable evidence. after_sha256
    carries the EXPECTED output hash — that is what lets resume decide from
    disk state alone whether the publish happened."""
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
        )
    )


def _reconcile_intent(
    action: PlanAction,
    record: ManifestRecord,
    root_resolved: Path,
    options: ApplyOptions,
    manifest: ManifestWriter | None,
    run_id: str,
) -> ApplyOutcome | None:
    """Resume decision for a DANGLING intent record (1.3): a prior run was
    killed inside a multi-step mutation's window and left evidence but no
    final record. Disk state decides:

    - live target matches the intent's expected after-hash → the publish
      happened; complete the action (unlink a still-present source) or adopt
      the finished-but-unrecorded mutation, appending the applied record the
      interrupted run never wrote — the union of manifests stays the complete
      restore evidence.
    - target missing, or still holding the recorded to-be-overwritten bytes →
      the publish never happened; return None so the action executes normally
      (still behind the FR-003 hash guard).
    - anything else → ERR-002 external interference; mutate nothing.
    """
    target = Path(record.target_path)
    source = Path(record.original_path)
    # §13.5 containment, symmetric with _execute_action: the record's ABSOLUTE
    # paths come from an operator-supplied manifest, and the completion arm
    # below unlinks `source` — a crafted/wrong record must never read or
    # mutate outside the plan's source root (PR #18 review).
    for candidate in (source, target):
        if not candidate.resolve().is_relative_to(root_resolved):
            return _failed(
                action,
                "ERR-002",
                f"{candidate}: intent record path resolves outside the plan's "
                f"source root; refusing reconciliation",
            )
    try:
        target_data = target.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        return _failed(
            action,
            "ERR-002",
            f"{target}: unreadable while reconciling the intent recorded in "
            f"{record.run_id} ({exc.strerror or exc})",
        )
    if _sha(target_data) == record.after_sha256:
        source_data: bytes | None
        try:
            source_data = source.read_bytes()
        except FileNotFoundError:
            source_data = None
        except OSError as exc:
            return _failed(
                action,
                "ERR-002",
                f"{source}: unreadable while reconciling the intent recorded in "
                f"{record.run_id} ({exc.strerror or exc})",
            )
        if source_data is not None and _sha(source_data) != record.before_sha256:
            return _failed(
                action,
                "ERR-002",
                f"{source}: changed since the intent recorded in {record.run_id}; "
                f"resume must not remove it",
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
        if source_data is not None:
            try:
                source.unlink()
            except OSError as exc:
                return _failed(
                    action,
                    "ERR-003",
                    f"{source}: target already published but source not removed "
                    f"on resume ({exc.strerror or exc})",
                )
        if manifest is not None:
            # seq/recorded_at/source_root re-stamped by the writer; run_id is
            # the resuming run's — it is the run asserting this evidence.
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
    if record.overwritten_sha256 is not None and _sha(target_data) == record.overwritten_sha256:
        return None
    return _failed(
        action,
        "ERR-002",
        f"{target}: neither the expected output nor the recorded pre-overwrite "
        f"content (intent recorded in {record.run_id}; changed externally)",
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
) -> tuple[ApplyOutcome, bool]:
    source = source_root / action.path
    # FR-003: the plan's decision only executes against the exact bytes it saw.
    try:
        data = source.read_bytes()
    except OSError:
        return _skip(action, "unreadable"), False  # ERR-005
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
    target_bytes: bytes | None = None  # clobbered content, kept for CR-NEW-004 rollback
    if clobber:
        assert target is not None
        try:
            target_bytes = target.read_bytes()
        except OSError as exc:
            outcome = _failed(
                action, "ERR-003", f"{target}: unreadable for overwrite backup ({exc})"
            )
            _record(manifest, action, kind, source, target, None, None, None, None, run_id, outcome)
            return outcome, False
        overwritten_sha = _sha(target_bytes)
        if options.backup_root is not None:
            try:
                overwritten_backup = backup_file(
                    target_bytes,
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
    if kind == "rename_and_rewrite":
        # The only multi-step mutation (publish target, unlink source): its
        # write-ahead intent record must be durable before the first step.
        # Single-step kinds stay one-record — atomic_write_bytes/rename leave
        # no window in which the corpus is mutated but unmanifested.
        assert target is not None
        _record_intent(
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
        )
    try:
        mode = source.stat().st_mode
        if kind == "rewrite":
            atomic_write_bytes(source, payload, mode=mode)
        elif kind == "rename":
            assert target is not None
            if clobber:
                rename_overwrite(source, target)  # codex CR-NEW-001: fsync'd, WriteError-wrapped
            else:
                rename_no_clobber(source, target)
        else:  # rename_and_rewrite
            assert target is not None
            atomic_write_bytes(target, payload, mode=mode, clobber=clobber)
            try:
                source.unlink()
            except OSError as unlink_exc:
                # codex CR-NEW-004: the target is already published; recording
                # "failed" while the corpus changed would make the report and
                # manifest lie. Roll the publish back to the exact pre-action
                # state (rewrite the clobbered bytes, or remove the published
                # target), then fail honestly with the original untouched.
                try:
                    if target_bytes is not None:
                        atomic_write_bytes(target, target_bytes)
                    else:
                        target.unlink()
                # PEP 758 (Python 3.14): unparenthesized multi-type except reads as
                # `except (WriteError, OSError)`. Kept unparenthesized deliberately;
                # pre-3.14 reviewers misread it as the Python 2 bind form.
                except WriteError, OSError:
                    log.error(
                        "apply residue: target published, source not removed, rollback failed",
                        path=action.path,
                        target=str(target),
                    )
                msg = (
                    f"{source}: target published but source not removed; publish "
                    f"rolled back ({unlink_exc.strerror or unlink_exc})"
                )
                raise WriteError(msg) from unlink_exc
    except FileExistsError:
        return _skip(action, "collision"), False  # no-clobber race lost (FR-011)
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
    resume_records: list[ManifestRecord] | None = None,
    prior_manifest_sha256: str | None = None,
    prior_attempt: PriorAttempt | None = None,
) -> Report:
    log = get_logger(__name__)
    assert plan.source_root is not None  # CLI refused earlier (ERR-006)
    source_root = Path(plan.source_root)
    root_resolved = source_root.resolve()
    include = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.include)
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude)

    # FR-013 (adr-0006): actions a prior run's manifest records as applied are
    # reconciled read-only instead of executed; the LATEST applied record per
    # action wins (an apply→restore→apply chain can record one action twice).
    # Sorted by (recorded_at, seq) rather than caller order so a multi-resume
    # chain passed out of flag order cannot let a stale record win and raise a
    # spurious ERR-002 (PR #10 review). A 1.3 intent record with no LATER
    # final record for its action is DANGLING — the kill landed inside that
    # action's mutation window — and, being the newest evidence, it takes
    # precedence over any earlier applied record for the same action.
    completed: dict[str, ManifestRecord] = {}
    dangling_intents: dict[str, ManifestRecord] = {}
    for record in sorted(resume_records or [], key=lambda r: (r.recorded_at, r.seq)):
        if record.result == "intent":
            dangling_intents[record.action_id] = record
        else:
            dangling_intents.pop(record.action_id, None)
            if record.result == "applied":
                completed[record.action_id] = record

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
            prior = completed.get(action.action_id)
            intent = dangling_intents.get(action.action_id)
            if intent is not None:
                # Newest evidence wins: a None verdict means the publish never
                # happened, so the action executes normally below — never via
                # _reconcile_completed against an older, superseded record.
                reconciled = _reconcile_intent(
                    action, intent, root_resolved, options, manifest, run_id
                )
                if reconciled is not None:
                    outcome = reconciled
                else:
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
                    )
            elif prior is not None:
                outcome = _reconcile_completed(action, prior)
            else:
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
        ),
    )
