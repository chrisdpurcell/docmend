"""CLI shell — argument parsing, global flags, dispatch (spec §8.2.3 "CLI shell", IR-005).

Architectural role: this layer is deliberately thin — no domain logic lives here
(§8.2.3). The pipeline subcommands land milestone by milestone: ``scan`` (IR-001)
arrived at MS-1; plan/apply/verify/restore (IR-002..IR-004, IR-008) follow per §19.

Cross-file contracts:
- ``--verbose``/``--quiet`` are mutually exclusive by IR-005 (a hard usage error,
  exit 2 — not the "quiet wins" fallback the logging research floated; the spec is
  binding). Their level mapping lives in :mod:`docmend.observability`.
- ``--dry-run``/``-n`` is accepted globally per IR-005 and threaded through
  :class:`GlobalOptions`; it gains effect when write-capable commands land (MS-3).
  It can only ever make a run more conservative (NFR-004). ``scan`` is read-only
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
from pydantic import ValidationError

from docmend import __version__, artifacts, discovery, lock, planning
from docmend.config import ConfigError, DocmendConfig, PathsConfig, load_config
from docmend.observability import configure_logging, get_logger, new_run_id
from docmend.plan import PLAN_SCHEMA_VERSION, ArtifactRef
from docmend.report import Report, ReportTotals
from docmend.writer.apply import execute_plan
from docmend.writer.gate import ApplyOptions, evaluate_gate

#: Default per-run artifact/log directory, created in the invoking directory
#: (proposed OQ-034; the run-ID-keyed names inside it are the OQ-006 sidecar
#: discovery convention's future input).
ARTIFACT_DIR_NAME = ".docmend"

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

    inventory = discovery.scan(path, config, run_id=run_id, generated_at=now.isoformat())
    out_path = report if report is not None else artifact_dir / f"docmend-{run_id}-inventory.json"
    artifacts.write_inventory(inventory, out_path)

    totals = inventory.totals
    reasons = totals.skipped_by_reason
    typer.echo(f"inventory: {out_path}")
    typer.echo(
        f"files: {totals.files}  symlinks: {totals.symlinks}  "
        f"skipped: {totals.skipped} (excluded {reasons.excluded}, unreadable {reasons.unreadable})  "
        f"hard-link groups: {totals.hard_link_groups}"
    )
    if reasons.unreadable:
        # Findings, not failure: the scan completed but not everything was readable.
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

    if path is not None:
        if not path.exists():
            typer.echo(f"error: {path}: no such file or directory", err=True)
            raise typer.Exit(2)
        # The root is known before scanning: acquire here (not after) so the
        # scan+plan pair is covered as one run (OQ-027) instead of leaving the
        # scan step racy against a concurrent invocation over the same tree.
        scan_root = (path if path.is_dir() else path.parent).resolve()
        run_lock = _acquire_run_lock(scan_root, run_id=run_id)
        log.info("plan starting (scan shorthand)", path=str(path))
        inventory = discovery.scan(path, config, run_id=run_id, generated_at=now.isoformat())
        # Resolved to absolute: inventory_ref.path must stay valid outside this
        # invocation's CWD, unlike out_path (echoed, never round-tripped) below.
        inventory_artifact = (artifact_dir / f"docmend-{run_id}-inventory.json").resolve()
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
        # The root is only known once the inventory is read, so the lock is
        # acquired here rather than up front (OQ-027).
        run_lock = _acquire_run_lock(Path(inventory.source_root), run_id=run_id)

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
        out_path = out if out is not None else artifact_dir / f"docmend-{run_id}-plan.json"
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

        findings = reasons.get("unreadable", 0) + reasons.get("changed-since-scan", 0)
        if path is not None:
            # IR-002: the PATH shorthand's own scan step can skip unreadable files
            # (ERR-007) that never reach the plan at all — they live in the
            # inventory, not result.skips — so `plan PATH` must still count them
            # here, or it would silently exit 0 over a tree `scan PATH` would
            # have exited 1 on.
            findings += inventory.totals.skipped_by_reason.unreadable
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


def _acquire_run_lock(source_root: Path, *, run_id: str) -> lock.RunLock | None:
    """Acquire the OQ-027 run lock for `plan`, mapping contention to exit 3.

    `plan` is read-only (§3.1), so a lock the tool cannot even create (e.g. an
    unwritable state dir) must not block it — that OSError degrades to a
    warning and an unlocked run, per the OQ-036 posture.
    """
    try:
        return lock.acquire(source_root, run_id=run_id, command="plan")
    except lock.LockHeldError as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(3) from exc
    except OSError as exc:
        get_logger(__name__).warning("run lock unavailable", error=str(exc))
        return None


def _acquire_run_lock_strict(source_root: Path, *, run_id: str, command: str) -> lock.RunLock:
    """Acquire the OQ-027 run lock for a write-capable command (e.g. `apply`).

    Unlike `plan`'s `_acquire_run_lock`, a write-capable command must REFUSE
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
) -> None:
    """Execute a reviewed plan; dry-run by default (FR-004, IR-003).

    Exit codes (§18.5): 0 clean; 1 findings (skips/failures); 2 input error
    (ERR-006 invalid plan, flag conflicts); 3 safety refusal (gate or lock).
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
        plan = artifacts.read_plan(plan_path)
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

    backup_root = backup_dir if backup_dir is not None else config.write.backup_dir
    options = ApplyOptions(
        write=write,
        # Resolved ONCE here (codex CR-005): every backup path derived from
        # this root lands in the manifest, which restore must be able to
        # follow from any cwd (IR-008) — a relative --backup-dir must never
        # produce cwd-dependent manifest entries.
        backup_root=backup_root.resolve() if backup_root is not None else None,
        preserved_by=preserved_by.value if preserved_by is not None else None,
        allow_no_backup=allow_no_backup,
    )
    manifest_path = artifact_dir / f"docmend-{run_id}-manifest.jsonl"
    report_path = report if report is not None else artifact_dir / f"docmend-{run_id}-report.json"
    plan_ref = ArtifactRef(
        path=str(plan_path), run_id=plan.run_id, sha256=artifacts.sha256_of_file(plan_path)
    )
    started_at = now.isoformat()

    run_lock = _acquire_run_lock_strict(source_root, run_id=run_id, command="apply")
    try:
        if write:
            # CRITICAL (Task 9 carry-forward): the gate is invoked
            # unconditionally before execute_plan on every write run — the
            # engine itself does not self-enforce preservation.
            refusals = evaluate_gate(
                plan, config, source_root=source_root, options=options, manifest_dir=artifact_dir
            )
            if refusals:
                for refusal in refusals:
                    typer.echo(f"refused [{refusal.predicate}]: {refusal.message}", err=True)
                    log.error("gate refusal", predicate=refusal.predicate, detail=refusal.message)
                _write_refusal_report(plan_ref, run_id, started_at, report_path)
                raise typer.Exit(3)
        result = execute_plan(
            plan,
            config,
            run_id=run_id,
            plan_ref=plan_ref,
            options=options,
            manifest_path=manifest_path,
            started_at=started_at,
        )
    finally:
        run_lock.release()

    artifacts.write_report(result, report_path)
    totals = result.totals
    typer.echo(f"report: {report_path}")
    if write and (totals.applied or totals.failed):
        typer.echo(f"manifest: {manifest_path}")
    reasons = Counter(o.skip_reason for o in result.outcomes if o.skip_reason is not None)
    detail = f" ({', '.join(f'{r} {n}' for r, n in sorted(reasons.items()))})" if reasons else ""
    typer.echo(
        f"applied: {totals.applied}  would-apply: {totals.would_apply}  "
        f"skipped: {totals.skipped}{detail}  failed: {totals.failed}"
    )
    if totals.skipped or totals.failed:
        raise typer.Exit(1)


def _write_refusal_report(
    plan_ref: ArtifactRef, run_id: str, started_at: str, report_path: Path
) -> None:
    # §8.5: even a refused run leaves an artifact; zero outcomes, library untouched.
    artifacts.write_report(
        Report(
            run_id=run_id,
            generated_by=f"docmend {__version__}",
            plan_ref=plan_ref,
            dry_run=False,
            started_at=started_at,
            completed_at=datetime.now(UTC).isoformat(),
            outcomes=[],
            totals=ReportTotals(applied=0, would_apply=0, skipped=0, failed=0),
        ),
        report_path,
    )
