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
from pathlib import Path
from typing import Annotated

import typer

from docmend import __version__, artifacts, discovery, planning
from docmend.config import ConfigError, DocmendConfig, PathsConfig, load_config
from docmend.observability import configure_logging, get_logger, new_run_id
from docmend.plan import ArtifactRef

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

    Exit codes (§18.5): 0 clean; 1 findings (unreadable/changed-since-scan
    skips, collision under the fail policy, or encoding-gate skips under
    --fail-on-low-confidence-encoding); 2 input errors (bad config, ERR-008).
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

    inventory_ref = ArtifactRef(
        path=str(inventory_artifact),
        run_id=inventory.run_id,
        sha256=artifacts.sha256_of_file(inventory_artifact),
    )
    result = planning.build_plan(
        inventory, config, run_id=run_id, generated_at=now.isoformat(), inventory_ref=inventory_ref
    )
    out_path = out if out is not None else artifact_dir / f"docmend-{run_id}-plan.json"
    artifacts.write_plan(result, out_path)

    reasons = Counter(skip.reason for skip in result.skips)
    typer.echo(f"plan: {out_path}")
    typer.echo(
        f"actions: {result.totals.actions}  skips: {result.totals.skips}"
        + (f"  ({', '.join(f'{r} {n}' for r, n in sorted(reasons.items()))})" if reasons else "")
    )

    findings = reasons.get("unreadable", 0) + reasons.get("changed-since-scan", 0)
    if config.rename.on_collision == "fail":
        findings += reasons.get("collision", 0)
    if fail_on_low_confidence:
        findings += reasons.get("low-confidence-encoding", 0) + reasons.get(
            "below-non-ascii-floor", 0
        )
    if findings:
        raise typer.Exit(1)
