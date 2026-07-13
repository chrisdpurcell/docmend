"""CLI shell — argument parsing, global flags, dispatch (spec §8.2.3 "CLI shell", IR-005).

Architectural role: this layer is deliberately thin — no domain logic lives here
(§8.2.3). All five pipeline subcommands are live as of v1.0.0: ``scan`` (IR-001),
``plan`` (IR-002), ``apply`` (IR-003, incl. FR-013 resume), ``verify`` (IR-004),
and ``restore`` (IR-008).

Cross-file contracts:
- ``--verbose``/``--quiet`` are mutually exclusive by IR-005 (a hard usage error,
  exit 2 — not the "quiet wins" fallback the logging research floated; the spec is
  binding). Their level mapping lives in :mod:`docmend.observability`.
- ``--dry-run``/``-n`` is accepted globally per IR-005 and threaded through
  :class:`GlobalOptions`; the write-capable commands (``apply``/``restore``) honor
  it. It can only ever make a run more conservative (NFR-004). ``scan`` is read-only
  by construction (FR-001), so the flag is a no-op there.
- Exit codes follow the §18.5 taxonomy: 0 clean, 1 findings (a scan with
  unreadable-file skips, ERR-007), 2 input error (Click usage errors already exit
  2, which is why BadParameter is used for flag conflicts), 3 safety refusal.
- Run artifacts and the per-run log default into ``./.docmend/`` in the invoking
  directory, keyed by run-ID (proposed OQ-034 convention; ``--report`` overrides
  the artifact path). The default excludes make ``.docmend/`` invisible to scans.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern
from pydantic import ValidationError

from docmend import __version__, artifacts, discovery, lock, planning
from docmend.artifacts import ARTIFACT_DIR_NAME
from docmend.config import ConfigError, DocmendConfig, PathsConfig, load_config
from docmend.lineage import PriorAttempt
from docmend.observability import configure_logging, get_logger, new_run_id
from docmend.plan import PLAN_SCHEMA_VERSION, ArtifactRef
from docmend.report import Report, ReportTotals
from docmend.restore import preview_restore, run_restore
from docmend.verify import (
    VerifyFinding,
    check_backups,
    check_content,
    check_discovery,
    check_frontmatter,
    check_lifecycle,
    check_manifest_root,
    check_outputs,
    manifest_inspection_findings,
)
from docmend.verify_coverage import check_plan_coverage, load_verification_evidence
from docmend.verify_report import VerifyFindingRecord, VerifyReport
from docmend.writer import commit, manifest
from docmend.writer.apply import execute_plan, preview_plan
from docmend.writer.commit import _load_apply_predecessors  # pyright: ignore[reportPrivateUsage]
from docmend.writer.gate import is_content_rewrite

app = typer.Typer(
    name="docmend",
    help=(
        "Normalize, repair, and convert text/HTML documents into clean, "
        "well-structured Markdown — from a single file to an entire library."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=False,  # bare invocation is handled in main() so it exits 0
)


@dataclass(frozen=True)
class GlobalOptions:
    """IR-005 global flag state, threaded to subcommands via the Typer context."""

    verbose: int
    quiet: bool
    dry_run: bool


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", "-V", help="Print the package version and exit."),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help="Raise console detail (-v per-file outcomes, -vv debug). File log unaffected.",
        ),
    ] = 0,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Limit console output to errors and critical messages."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Preview without writing (apply's default posture)."),
    ] = False,
) -> None:
    """docmend — safe, resumable, auditable document normalization."""
    if version:
        typer.echo(f"docmend {__version__}")
        raise typer.Exit(0)
    if verbose and quiet:
        # IR-005: mutually exclusive; BadParameter -> Click usage error -> exit 2.
        raise typer.BadParameter("--verbose and --quiet are mutually exclusive")
    ctx.obj = GlobalOptions(verbose=verbose, quiet=quiet, dry_run=dry_run)
    if ctx.invoked_subcommand is None:
        # Bare invocation shows help and exits 0 (a request for usage, not an error).
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


def _global_options(ctx: typer.Context) -> GlobalOptions:
    obj: object = ctx.obj
    return obj if isinstance(obj, GlobalOptions) else GlobalOptions(0, False, False)


def _load_effective_config(
    config_path: Path | None, include: list[str] | None, exclude: list[str] | None
) -> DocmendConfig:
    """Config per OQ-029 precedence: flags > file > defaults; list flags REPLACE."""
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    if include is not None or exclude is not None:
        paths = PathsConfig(
            include=include if include is not None else config.paths.include,
            exclude=exclude if exclude is not None else config.paths.exclude,
        )
        config = config.model_copy(update={"paths": paths})
    return config


def _guard_artifact_paths(
    destinations: list[Path],
    *,
    corpus_root: Path | None,
    input_artifacts: list[Path],
    config: DocmendConfig,
) -> None:
    """Refuse unsafe artifact destinations BEFORE the pipeline runs (rev 0.26
    IR-007, adr-0021): a refused write must not follow a completed scan. The
    .docmend/ carve-out is licensed per destination against the effective
    exclude patterns — if the operator's excludes no longer cover a
    destination, that destination is scannable corpus space and loses its
    license (guard_artifact_destination owns the decision)."""
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude)
    artifact_root = Path(ARTIFACT_DIR_NAME).resolve()
    for destination in destinations:
        refusal = artifacts.guard_artifact_destination(
            destination,
            corpus_root=corpus_root,
            input_artifacts=input_artifacts,
            artifact_root=artifact_root,
            exclude=exclude,
        )
        if refusal is not None:
            typer.echo(f"refused [artifact-destination]: {refusal}", err=True)
            raise typer.Exit(3)


@app.command()
def scan(
    ctx: typer.Context,
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            help="File or directory tree to inventory; a single file is first-class (NFR-006).",
        ),
    ],
    report: Annotated[
        Path | None,
        typer.Option(
            "--report",
            help="Write the inventory to FILE (default: .docmend/docmend-<run-id>-inventory.json).",
        ),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="TOML config file (default: ./docmend.toml when present)."),
    ] = None,
    include: Annotated[
        list[str] | None,
        typer.Option(
            "--include", help="Replace paths.include (repeatable; replaces, never appends)."
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude", help="Replace paths.exclude (repeatable; replaces, never appends)."
        ),
    ] = None,
) -> None:
    """Scan PATH read-only into a structured inventory artifact (FR-001, IR-001).

    Exit codes (§18.5): 0 clean; 1 when any file or directory was skipped as
    unreadable (ERR-007 findings); 2 on input errors (bad PATH, invalid config).
    """
    opts = _global_options(ctx)
    config = _load_effective_config(config_path, include, exclude)

    now = datetime.now(UTC)
    run_id = new_run_id(now)
    artifact_dir = Path(ARTIFACT_DIR_NAME)
    configure_logging(
        run_id=run_id,
        command="scan",
        log_dir=artifact_dir,
        verbose=opts.verbose,
        quiet=opts.quiet,
    )
    log = get_logger(__name__)
    log.info("scan starting", path=str(path))

    out_path = report if report is not None else artifact_dir / f"docmend-{run_id}-inventory.json"
    corpus_root = (path if path.is_dir() else path.parent).resolve()
    _guard_artifact_paths([out_path], corpus_root=corpus_root, input_artifacts=[], config=config)

    run_lock = _acquire_read_lock(corpus_root, run_id=run_id, command="scan")
    try:
        inventory = discovery.scan(path, config, run_id=run_id, generated_at=now.isoformat())
        artifacts.write_inventory(inventory, out_path)
    finally:
        if run_lock is not None:
            run_lock.release()

    totals = inventory.totals
    reasons = totals.skipped_by_reason
    typer.echo(f"inventory: {out_path}")
    typer.echo(
        f"files: {totals.files}  symlinks: {totals.symlinks}  "
        f"skipped: {totals.skipped} (excluded {reasons.excluded}, "
        f"unreadable {reasons.unreadable}, timeout {reasons.timeout})  "
        f"hard-link groups: {totals.hard_link_groups}"
    )
    if reasons.unreadable or reasons.timeout:
        # Findings, not failure: the scan completed but not everything was
        # covered — a watchdog timeout is a PARTIAL result exactly like an
        # unreadable file, never a silent success (2026-07-10 review).
        raise typer.Exit(1)


@app.command()
def plan(
    ctx: typer.Context,
    path: Annotated[
        Path | None,
        typer.Argument(
            help="File or directory to plan over (shorthand: scans first, IR-002).",
        ),
    ] = None,
    inventory_path: Annotated[
        Path | None,
        typer.Option("--inventory", help="Existing inventory artifact to consume (IR-002)."),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option(
            "--out", help="Write the plan to FILE (default: .docmend/docmend-<run-id>-plan.json)."
        ),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="TOML config file (default: ./docmend.toml when present)."),
    ] = None,
    include: Annotated[
        list[str] | None,
        typer.Option(
            "--include", help="Replace paths.include (repeatable; replaces, never appends)."
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude", help="Replace paths.exclude (repeatable; replaces, never appends)."
        ),
    ] = None,
    fail_on_low_confidence: Annotated[
        bool,
        typer.Option(
            "--fail-on-low-confidence-encoding",
            help="Exit 1 when any file skips on the FR-007 encoding gates (AW-003).",
        ),
    ] = False,
) -> None:
    """Produce a reviewable DR-002 plan from an inventory (FR-002, IR-002).

    Exit codes (§18.5): 0 clean; 1 findings (unreadable/changed-since-scan plan
    skips, collision under the fail policy, or encoding-gate skips under
    --fail-on-low-confidence-encoding — plus, for the PATH shorthand, any
    unreadable files its own scan step skipped, matching `scan`'s exit
    behavior over the same tree); 2 input errors (bad config, ERR-008).
    """
    opts = _global_options(ctx)
    if (path is None) == (inventory_path is None):
        # IR-002: exactly one of the two source forms — neither or both is a usage error.
        raise typer.BadParameter("provide exactly one of PATH or --inventory")
    config = _load_effective_config(config_path, include, exclude)

    now = datetime.now(UTC)
    run_id = new_run_id(now)
    artifact_dir = Path(ARTIFACT_DIR_NAME)
    configure_logging(
        run_id=run_id, command="plan", log_dir=artifact_dir, verbose=opts.verbose, quiet=opts.quiet
    )
    log = get_logger(__name__)
    out_path = out if out is not None else artifact_dir / f"docmend-{run_id}-plan.json"

    if path is not None:
        if not path.exists():
            typer.echo(f"error: {path}: no such file or directory", err=True)
            raise typer.Exit(2)
        # The root is known before scanning: acquire here (not after) so the
        # scan+plan pair is covered as one run (OQ-027) instead of leaving the
        # scan step racy against a concurrent invocation over the same tree.
        scan_root = (path if path.is_dir() else path.parent).resolve()
        # Resolved to absolute: inventory_ref.path must stay valid outside this
        # invocation's CWD, unlike out_path (echoed, never round-tripped) below.
        inventory_artifact = (artifact_dir / f"docmend-{run_id}-inventory.json").resolve()
        _guard_artifact_paths(
            [out_path, inventory_artifact],
            corpus_root=scan_root,
            input_artifacts=[],
            config=config,
        )
        run_lock = _acquire_read_lock(scan_root, run_id=run_id, command="plan")
        log.info("plan starting (scan shorthand)", path=str(path))
        inventory = discovery.scan(path, config, run_id=run_id, generated_at=now.isoformat())
        artifacts.write_inventory(inventory, inventory_artifact)
    else:
        assert inventory_path is not None
        log.info("plan starting", inventory=str(inventory_path))
        try:
            inventory = artifacts.read_inventory(inventory_path)
        except artifacts.ArtifactError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(2) from exc
        inventory_artifact = inventory_path.resolve()
        _guard_artifact_paths(
            [out_path],
            corpus_root=Path(inventory.source_root),
            input_artifacts=[inventory_path],
            config=config,
        )
        # The root is only known once the inventory is read, so the lock is
        # acquired here rather than up front (OQ-027).
        run_lock = _acquire_read_lock(Path(inventory.source_root), run_id=run_id, command="plan")

    try:
        inventory_ref = ArtifactRef(
            path=str(inventory_artifact),
            run_id=inventory.run_id,
            sha256=artifacts.sha256_of_file(inventory_artifact),
        )
        result = planning.build_plan(
            inventory,
            config,
            run_id=run_id,
            generated_at=now.isoformat(),
            inventory_ref=inventory_ref,
        )
        artifacts.write_plan(result, out_path)

        reasons = Counter(skip.reason for skip in result.skips)
        typer.echo(f"plan: {out_path}")
        typer.echo(
            f"actions: {result.totals.actions}  skips: {result.totals.skips}"
            + (
                f"  ({', '.join(f'{r} {n}' for r, n in sorted(reasons.items()))})"
                if reasons
                else ""
            )
        )

        # Timeouts are partial results, same finding class as unreadable
        # (2026-07-10 review): a plan that silently skipped work must exit 1.
        findings = (
            reasons.get("unreadable", 0)
            + reasons.get("changed-since-scan", 0)
            + reasons.get("timeout", 0)
        )
        if path is not None:
            # IR-002: the PATH shorthand's own scan step can skip unreadable files
            # (ERR-007) that never reach the plan at all — they live in the
            # inventory, not result.skips — so `plan PATH` must still count them
            # here, or it would silently exit 0 over a tree `scan PATH` would
            # have exited 1 on.
            findings += (
                inventory.totals.skipped_by_reason.unreadable
                + inventory.totals.skipped_by_reason.timeout
            )
        if config.rename.on_collision == "fail":
            findings += reasons.get("collision", 0)
        if fail_on_low_confidence:
            findings += reasons.get("low-confidence-encoding", 0) + reasons.get(
                "below-non-ascii-floor", 0
            )
        if findings:
            raise typer.Exit(1)
    finally:
        if run_lock is not None:
            run_lock.release()


def _acquire_read_lock(source_root: Path, *, run_id: str, command: str) -> lock.RunLock | None:
    """Acquire a read-only command's run lock, mapping contention to exit 3.

    A lock the tool cannot create must not block scan, plan, or verify; that
    OSError degrades to a warning and an unlocked run per OQ-036.
    """
    try:
        return lock.acquire(source_root, run_id=run_id, command=command)
    except lock.LockHeldError as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(3) from exc
    except OSError as exc:
        get_logger(__name__).warning("run lock unavailable", error=str(exc))
        return None


def _acquire_run_lock_strict(source_root: Path, *, run_id: str, command: str) -> lock.RunLock:
    """Acquire the OQ-027 run lock for a write-capable command (e.g. `apply`).

    Unlike `_acquire_read_lock`, a write-capable command must REFUSE
    (exit 3) when the lock cannot even be created — an unwritable state dir is
    not a reason to proceed unlocked into a run that can mutate the library
    (AW-005; contrast the OQ-036 read-only posture that lets `plan` degrade).
    """
    try:
        return lock.acquire(source_root, run_id=run_id, command=command)
    except (lock.LockHeldError, OSError) as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(3) from exc


class PreservedBy(StrEnum):
    """FR-005 declared byte-preserving strategies external to docmend's own backups."""

    git = "git"
    external = "external"


@app.command()
def apply(
    ctx: typer.Context,
    plan_path: Annotated[
        Path,
        typer.Argument(exists=True, metavar="PLAN", help="Plan artifact to execute (IR-003)."),
    ],
    write: Annotated[
        bool,
        typer.Option("--write", help="Opt into real mutation (OQ-014); default is dry-run."),
    ] = False,
    dry_run_flag: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview outcomes without writing (the default)."),
    ] = False,
    backup_dir: Annotated[
        Path | None,
        typer.Option(
            "--backup-dir",
            help="Tool-written backup destination (FR-006); overrides write.backup_dir.",
        ),
    ] = None,
    preserved_by: Annotated[
        PreservedBy | None,
        typer.Option(
            "--preserved-by",
            help="Declare an external byte-preserving strategy (FR-005): git or external.",
        ),
    ] = None,
    allow_no_backup: Annotated[
        bool,
        typer.Option(
            "--allow-no-backup",
            help="FR-005 low-risk opt-in: single-action plans only, no rollback copy.",
        ),
    ] = False,
    report: Annotated[
        Path | None,
        typer.Option(
            "--report",
            help="Write the report to FILE (default: .docmend/docmend-<run-id>-report.json).",
        ),
    ] = None,
    resume_manifest: Annotated[
        list[Path] | None,
        typer.Option(
            "--resume-manifest",
            help="Resume (FR-013): reconcile against this prior apply manifest "
            "(repeatable — pass every manifest of a multiply-interrupted run).",
        ),
    ] = None,
    resume_run_id: Annotated[
        list[str] | None,
        typer.Option(
            "--resume-run-id",
            help="Resume (FR-013): reconcile against BOTH .docmend sidecars of run <ID> "
            "(manifest and report; OQ-034 convention; repeatable, combinable with "
            "--resume-manifest/--prior-report).",
        ),
    ] = None,
    prior_report: Annotated[
        list[Path] | None,
        typer.Option(
            "--prior-report",
            help="A relocated or report-only predecessor attempt's report (adr-0019 "
            "attempt lineage; repeatable).",
        ),
    ] = None,
) -> None:
    """Execute a reviewed plan; dry-run by default (FR-004, IR-003).

    Resume (FR-013, adr-0006): --resume-manifest/--resume-run-id reconcile the
    plan against a prior run's manifest first — recorded-applied actions whose
    live output still matches skip as `already-applied` (not a finding),
    changed/missing outputs fail ERR-002, unrecorded actions execute normally.

    Exit codes (§18.5): 0 clean; 1 findings (skips other than already-applied,
    failures); 2 input error (ERR-006 invalid plan, flag conflicts, unreadable
    resume manifest); 3 safety refusal (gate or lock).
    """
    opts = _global_options(ctx)
    if write and (dry_run_flag or opts.dry_run):
        # IR-003: --write conflicts with --dry-run and with the global -n
        # (IR-005 gains its write-capable effect right here).
        raise typer.BadParameter("--write and --dry-run are mutually exclusive")

    now = datetime.now(UTC)
    run_id = new_run_id(now)
    artifact_dir = Path(ARTIFACT_DIR_NAME)
    configure_logging(
        run_id=run_id, command="apply", log_dir=artifact_dir, verbose=opts.verbose, quiet=opts.quiet
    )
    log = get_logger(__name__)

    try:
        plan, plan_sha256 = artifacts.read_plan_snapshot(plan_path)
    except artifacts.ArtifactError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    if int(plan.schema_version.split(".")[1]) > int(PLAN_SCHEMA_VERSION.split(".")[1]):
        typer.echo(
            f"error: {plan_path}: plan schema {plan.schema_version} is newer than this "
            f"docmend supports ({PLAN_SCHEMA_VERSION}) — regenerate the plan (ERR-006)",
            err=True,
        )
        raise typer.Exit(2)
    if plan.source_root is None:
        typer.echo(
            f"error: {plan_path}: plan lacks source_root (pre-1.1 artifact) — regenerate the plan (ERR-006)",
            err=True,
        )
        raise typer.Exit(2)
    source_root = Path(plan.source_root)
    if not source_root.is_dir():
        typer.echo(f"error: {source_root}: plan source root is not a directory", err=True)
        raise typer.Exit(2)
    try:
        config = DocmendConfig.model_validate(plan.config)
    except ValidationError as exc:
        typer.echo(f"error: {plan_path}: config snapshot invalid — {exc}", err=True)
        raise typer.Exit(2) from exc

    try:
        manifest_inputs, report_inputs = _resolve_evidence_paths(
            resume_manifest,
            resume_run_id,
            prior_report,
            option_name="--resume-run-id",
        )
    except artifacts.ArtifactError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    manifest_path = artifact_dir / f"docmend-{run_id}-manifest.jsonl"
    report_path = report if report is not None else artifact_dir / f"docmend-{run_id}-report.json"
    plan_ref = ArtifactRef(path=str(plan_path), run_id=plan.run_id, sha256=plan_sha256)
    started_at = now.isoformat()

    _guard_artifact_paths(
        [report_path, manifest_path],
        corpus_root=source_root,
        # Predecessor REPORTS are inputs too (adr-0019 lineage): --report must
        # not be able to clobber the evidence this run reconciles against.
        input_artifacts=[
            plan_path,
            *manifest_inputs,
            *report_inputs,
        ],
        config=config,
    )
    if write:

        def on_refusal(
            refusals: list[commit.GateRefusal],
            factory_plan_ref: ArtifactRef,
            factory_prior_attempt: PriorAttempt | None,
        ) -> None:
            for refusal in refusals:
                typer.echo(f"refused [{refusal.predicate}]: {refusal.message}", err=True)
                log.error("gate refusal", predicate=refusal.predicate, detail=refusal.message)
            _write_refusal_report(
                factory_plan_ref,
                run_id,
                started_at,
                report_path,
                prior_attempt=factory_prior_attempt,
            )

        try:
            with commit.apply_write_context(
                plan_path,
                run_id=run_id,
                manifest_path=manifest_path,
                report_path=report_path,
                backup_root_override=backup_dir.resolve() if backup_dir is not None else None,
                preserved_by=preserved_by.value if preserved_by is not None else None,
                allow_no_backup=allow_no_backup,
                resume_manifest_paths=manifest_inputs,
                prior_report_paths=report_inputs,
                input_artifacts=[plan_path, *manifest_inputs, *report_inputs],
                on_refusal=on_refusal,
            ) as safety:
                gated_plan, _, _, effective_options, _, _ = safety._consume_apply_state()  # pyright: ignore[reportPrivateUsage]
                content_rewrites = sum(
                    1 for action in gated_plan.actions if is_content_rewrite(action)
                )
                if effective_options.backup_root is None and content_rewrites:
                    typer.echo(
                        f"warning: no tool backups for this run — `docmend restore` will be "
                        f"able to undo only its pure renames; its {content_rewrites} action(s) "
                        "with content rewrites rely on external preservation",
                        err=True,
                    )
                result = execute_plan(
                    run_id=run_id,
                    manifest_path=manifest_path,
                    started_at=started_at,
                    safety=safety,
                )
                if manifest_path.exists():
                    result = result.model_copy(
                        update={"manifest_sha256": manifest.manifest_sha256(manifest_path)}
                    )
                safety.confirm_report(report_path)
                artifacts.write_report(result, report_path)
        except manifest.ManifestContainmentError as exc:
            typer.echo(f"refused [manifest-containment]: {exc}", err=True)
            raise typer.Exit(3) from exc
        except artifacts.ArtifactError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(2) from exc
        except commit.WriteRefusedError as exc:
            raise typer.Exit(3) from exc
        except commit.SafetyRefusedError as exc:
            typer.echo(f"refused: {exc}", err=True)
            raise typer.Exit(3) from exc
    else:
        try:
            resume_chain, prior_attempt = _load_apply_predecessors(
                manifest_inputs,
                report_inputs,
                source_root=source_root,
                plan_sha256=plan_sha256,
            )
        except manifest.ManifestContainmentError as exc:
            typer.echo(f"refused [manifest-containment]: {exc}", err=True)
            raise typer.Exit(3) from exc
        except artifacts.ArtifactError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(2) from exc
        run_lock = _acquire_run_lock_strict(source_root, run_id=run_id, command="apply")
        try:
            result = preview_plan(
                plan,
                config,
                run_id=run_id,
                plan_ref=plan_ref,
                started_at=started_at,
                resume_chain=resume_chain,
                prior_attempt=prior_attempt,
            )
            try:
                artifacts.write_report(result, report_path, clobber=False)
            except FileExistsError as exc:
                typer.echo(
                    f"error: report not written: {report_path} already exists "
                    "(dry runs leave prior artifacts untouched; adr-0021)",
                    err=True,
                )
                raise typer.Exit(2) from exc
        finally:
            run_lock.release()

    totals = result.totals
    typer.echo(f"report: {report_path}")
    # exists() and not just the counts: resume reconciliation can fail actions
    # read-only (ERR-002) without a single mutation, and the lazy-opening
    # ManifestWriter then never created the file (PR #10 review).
    if write and (totals.applied or totals.failed) and manifest_path.exists():
        typer.echo(f"manifest: {manifest_path}")
    reasons = Counter(o.skip_reason for o in result.outcomes if o.skip_reason is not None)
    detail = f" ({', '.join(f'{r} {n}' for r, n in sorted(reasons.items()))})" if reasons else ""
    typer.echo(
        f"applied: {totals.applied}  would-apply: {totals.would_apply}  "
        f"skipped: {totals.skipped}{detail}  failed: {totals.failed}"
    )
    # FR-013: `already-applied` is reconciliation confirming completed work, not
    # a reviewable finding — counting it would make a clean resume exit 1 and an
    # unattended re-invoke loop never converge on success.
    finding_skips = totals.skipped - reasons.get("already-applied", 0)
    if finding_skips or totals.failed:
        raise typer.Exit(1)


def _resolve_evidence_paths(
    manifests: list[Path] | None,
    run_ids: list[str] | None,
    reports: list[Path] | None,
    *,
    option_name: str,
) -> tuple[list[Path], list[Path]]:
    """Resolve explicit and sidecar predecessor evidence without inventing paths."""
    manifest_paths = list(manifests or [])
    report_paths = list(reports or [])
    for run_id in run_ids or []:
        sidecar_manifest = Path(ARTIFACT_DIR_NAME) / f"docmend-{run_id}-manifest.jsonl"
        sidecar_report = Path(ARTIFACT_DIR_NAME) / f"docmend-{run_id}-report.json"
        found = False
        if sidecar_manifest.exists():
            manifest_paths.append(sidecar_manifest)
            found = True
        if sidecar_report.exists():
            report_paths.append(sidecar_report)
            found = True
        if not found:
            raise artifacts.ArtifactError(
                f"{option_name} {run_id}: neither default manifest nor report sidecar exists "
                "(the named predecessor left no evidence; ERR-006)"
            )
    return list(dict.fromkeys(manifest_paths)), list(dict.fromkeys(report_paths))


def _write_refusal_report(
    plan_ref: ArtifactRef,
    run_id: str,
    started_at: str,
    report_path: Path,
    *,
    prior_attempt: PriorAttempt | None,
) -> None:
    # §8.5: even a refused run leaves an artifact; zero outcomes, library untouched.
    # 2.0: null manifest_sha256 + zero applied totals = a genuine report-only
    # attempt (nothing mutated) — resumable with an empty chain (CR-NEW-001).
    try:
        artifacts.write_report(
            Report(
                run_id=run_id,
                generated_by=f"docmend {__version__}",
                plan_ref=plan_ref,
                dry_run=False,
                started_at=started_at,
                completed_at=datetime.now(UTC).isoformat(),
                outcomes=[],
                totals=ReportTotals(applied=0, would_apply=0, skipped=0, failed=0, not_attempted=0),
                prior_attempt=prior_attempt,
                manifest_sha256=None,
            ),
            report_path,
            clobber=False,
        )
    except FileExistsError:
        typer.echo(
            f"refusal report not written: {report_path} already exists "
            "(pre-existing artifact preserved; §8.5)",
            err=True,
        )


@app.command()
def restore(
    ctx: typer.Context,
    manifest_path: Annotated[
        list[Path] | None,
        typer.Option(
            "--manifest",
            help="Manifest(s) to undo (DR-004 NDJSON; repeatable — pass the whole "
            "attempt chain of a multiply-resumed run).",
        ),
    ] = None,
    run_id_arg: Annotated[
        list[str] | None,
        typer.Option(
            "--run-id",
            help="Resolve .docmend/docmend-<ID>-manifest.jsonl (OQ-034 sidecar "
            "convention; repeatable, combinable with --manifest).",
        ),
    ] = None,
    only_id: Annotated[
        list[str] | None,
        typer.Option("--id", help="Restore only these docmend.id values (repeatable)."),
    ] = None,
    write: Annotated[
        bool, typer.Option("--write", help="Perform the restore; default previews (mirrors apply).")
    ] = False,
    dry_run_flag: Annotated[bool, typer.Option("--dry-run", help="Preview (the default).")] = False,
) -> None:
    """Undo an apply chain LIFO (IR-008, adr-0019, §18.6).

    Exit codes (§18.5): 0 clean; 1 findings (skips/failures, or --id matching
    nothing); 2 input error (bad manifest); 3 safety refusal (lock or
    containment).
    """
    opts = _global_options(ctx)
    if write and (dry_run_flag or opts.dry_run):
        raise typer.BadParameter("--write and --dry-run are mutually exclusive")
    if not manifest_path and not run_id_arg:
        raise typer.BadParameter("provide at least one of --manifest or --run-id")
    manifest_paths = list(manifest_path or [])
    manifest_paths.extend(
        Path(ARTIFACT_DIR_NAME) / f"docmend-{rid}-manifest.jsonl" for rid in run_id_arg or []
    )

    now = datetime.now(UTC)
    run_id = new_run_id(now)
    artifact_dir = Path(ARTIFACT_DIR_NAME)
    configure_logging(
        run_id=run_id,
        command="restore",
        log_dir=artifact_dir,
        verbose=opts.verbose,
        quiet=opts.quiet,
    )

    try:
        chain = manifest.read_manifest_chain(manifest_paths)
    except manifest.ManifestContainmentError as exc:
        # adr-0012: paths escaping the recorded roots are a safety refusal,
        # not a mere input error — nothing is read or mutated past this point.
        typer.echo(f"refused [manifest-containment]: {exc}", err=True)
        raise typer.Exit(3) from exc
    except artifacts.ArtifactError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    records = [r for s in chain.sets for r in s.records]
    if not records:
        typer.echo("nothing to restore: manifest holds no records")
        return

    # Issue #15 (suggestion 2, artifact-derived): state the run's restore
    # capability UP FRONT — derivable from the manifest alone (an applied
    # non-rename record with no backup_path has no recoverable bytes), so the
    # operator and wrapper scripts learn it before any per-row skip appears.
    unrestorable = sum(
        1
        for r in records
        if r.result == "applied" and r.operation != "rename" and r.backup_path is None
    )
    if unrestorable:
        # Wording states only what the manifest proves: a null backup_path. It
        # cannot know WHICH FR-005 strategy satisfied the gate (--preserved-by
        # git|external and --allow-no-backup all record the same shape).
        typer.echo(
            f"restore capability: renames-only — {unrestorable} content mutation(s) in this "
            "manifest have no tool backup and cannot be undone from it; recover that "
            "content from whatever preservation covered the apply run (FR-005: a "
            "git/external declaration or the low-risk opt-in)"
        )

    manifest_out = artifact_dir / f"docmend-{run_id}-manifest.jsonl"
    selector = frozenset(only_id) if only_id else None
    if write:
        try:
            with commit.restore_write_context(
                manifest_paths, run_id=run_id, manifest_out=manifest_out
            ) as safety:
                outcomes = run_restore(
                    run_id=run_id,
                    only_ids=selector,
                    manifest_out=manifest_out,
                    safety=safety,
                )
        except commit.SafetyRefusedError as exc:
            typer.echo(f"refused: {exc}", err=True)
            raise typer.Exit(3) from exc
        except manifest.ManifestContainmentError as exc:
            typer.echo(f"refused [manifest-containment]: {exc}", err=True)
            raise typer.Exit(3) from exc
        except artifacts.ArtifactError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(2) from exc
    else:
        # Preview preserves the command's historical lock semantics while its
        # engine remains structurally incapable of mutation.
        run_lock = _acquire_run_lock_strict(
            Path(chain.sets[0].header.source_root), run_id=run_id, command="restore"
        )
        try:
            outcomes = preview_restore(chain, run_id=run_id, only_ids=selector)
        finally:
            run_lock.release()

    if only_id and not outcomes:
        # A typo'd/stale --id must preserve the operator's stated intent as a
        # finding, never a silent success (2026-07-10 review medium theme).
        typer.echo(
            "restore: no manifest record matches the requested id(s)",
            err=True,
        )
        raise typer.Exit(1)
    counts = Counter(outcome.status for outcome in outcomes)
    typer.echo(
        f"restored: {counts.get('restored', 0)}  would-restore: {counts.get('would_restore', 0)}  "
        f"skipped: {counts.get('skipped', 0)}  failed: {counts.get('failed', 0)}"
    )
    if counts.get("skipped", 0) or counts.get("failed", 0):
        raise typer.Exit(1)


@app.command()
def verify(
    ctx: typer.Context,
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            help="Converted file or directory tree to verify; a single file is first-class (NFR-006).",
        ),
    ],
    manifest_paths_arg: Annotated[
        list[Path] | None,
        typer.Option(
            "--manifest",
            help="Manifest evidence to consume (repeatable; DR-004 NDJSON).",
        ),
    ] = None,
    run_ids_arg: Annotated[
        list[str] | None,
        typer.Option(
            "--run-id",
            help="Resolve default manifest/report sidecars for ID (repeatable and combinable).",
        ),
    ] = None,
    report_paths_arg: Annotated[
        list[Path] | None,
        typer.Option(
            "--report",
            help="Apply-report evidence to consume (repeatable; DR-003).",
        ),
    ] = None,
    plan_path: Annotated[
        Path | None,
        typer.Option("--plan", help="Plan artifact whose complete coverage must be certified."),
    ] = None,
    out_path: Annotated[
        Path | None,
        typer.Option("--out", help="Write an optional durable verify-report artifact to FILE."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="TOML config file (default: ./docmend.toml when present)."),
    ] = None,
) -> None:
    """Verify converted output read-only against the FR-014 checks (IR-004, adr-0012).

    Content checks always run. Optional plan/report/manifest evidence activates
    lifecycle, recovery, and exactly-once plan certification. Exit codes:
    0 clean; 1 findings; 2 invocation/structural input error; 3 safety refusal.
    """
    opts = _global_options(ctx)
    config = _load_effective_config(config_path, None, None)
    now = datetime.now(UTC)
    run_id = new_run_id(now)
    artifact_dir = Path(ARTIFACT_DIR_NAME)
    configure_logging(
        run_id=run_id,
        command="verify",
        log_dir=artifact_dir,
        verbose=opts.verbose,
        quiet=opts.quiet,
    )
    log = get_logger(__name__)
    log.info("verify starting", path=str(path))

    try:
        manifest_paths, report_paths = _resolve_evidence_paths(
            manifest_paths_arg,
            run_ids_arg,
            report_paths_arg,
            option_name="--run-id",
        )
    except artifacts.ArtifactError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    if report_paths and not manifest_paths and plan_path is None:
        raise typer.BadParameter("--report without --plan requires at least one manifest")

    corpus_root = (path if path.is_dir() else path.parent).resolve()
    input_artifacts = [*manifest_paths, *report_paths]
    if plan_path is not None:
        input_artifacts.append(plan_path)
    if out_path is not None:
        _guard_artifact_paths(
            [out_path],
            corpus_root=corpus_root,
            input_artifacts=input_artifacts,
            config=config,
        )

    plan_snapshot = None
    if plan_path is not None:
        # Plan 1.x must fail before a million-file scan or lock attempt, while
        # manifest/report snapshots must remain inside the corpus lock. Reuse
        # this exact snapshot below so plan validation has no TOCTOU reread.
        try:
            plan_snapshot = artifacts.read_plan_snapshot(plan_path)
        except artifacts.ArtifactError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(2) from exc

    started_at = now.isoformat()
    run_lock = _acquire_read_lock(corpus_root, run_id=run_id, command="verify")
    try:
        inventory = discovery.scan(path, config, run_id=run_id, generated_at=started_at)
        findings = (
            check_content(inventory) + check_frontmatter(inventory) + check_discovery(inventory)
        )
        evidence = None
        if manifest_paths or report_paths or plan_path is not None:
            try:
                evidence = load_verification_evidence(
                    plan_path,
                    manifest_paths,
                    report_paths,
                    plan_snapshot=plan_snapshot,
                )
            except manifest.ManifestContainmentError as exc:
                # Inspection owns containment; this is a defense-in-depth
                # fallback if a future refactor lets one escape as an error.
                findings.append(VerifyFinding(str(path), "manifest-containment", str(exc)))
            except artifacts.ArtifactError as exc:
                typer.echo(f"error: {exc}", err=True)
                raise typer.Exit(2) from exc
            if evidence is not None:
                inspection = evidence.manifest_inspection
                findings.extend(evidence.findings)
                findings.extend(manifest_inspection_findings(inspection))
                root_findings = check_manifest_root(inspection.chain, corpus_root)
                findings.extend(root_findings)
                findings.extend(check_lifecycle(inspection.chain))
                if not root_findings:
                    unsafe = frozenset(item.action_id for item in inspection.findings)
                    findings.extend(check_outputs(inspection.chain, unsafe_action_ids=unsafe))
                    findings.extend(check_backups(inspection.chain, unsafe_action_ids=unsafe))
        if plan_path is not None and evidence is not None:
            findings.extend(check_plan_coverage(evidence).findings)
        if out_path is not None:
            result_report = VerifyReport(
                run_id=run_id,
                generated_by=f"docmend {__version__}",
                verified_path=str(path),
                source_root=str(corpus_root),
                started_at=started_at,
                completed_at=datetime.now(UTC).isoformat(),
                inputs=list(evidence.inputs) if evidence is not None else [],
                checked_files=inventory.totals.files,
                findings=[
                    VerifyFindingRecord(
                        path=item.path,
                        check=item.check,
                        detail=item.detail,
                    )
                    for item in findings
                ],
                clean=not findings,
            )
            try:
                artifacts.write_verify_report(result_report, out_path)
            except artifacts.ArtifactError as exc:
                typer.echo(f"error: {exc}", err=True)
                raise typer.Exit(2) from exc
    finally:
        if run_lock is not None:
            run_lock.release()

    for finding in findings:
        typer.echo(f"finding [{finding.check}] {finding.path}: {finding.detail}")
    typer.echo(f"verify: {inventory.totals.files} files checked, {len(findings)} findings")
    if findings:
        raise typer.Exit(1)
