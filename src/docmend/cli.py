"""CLI shell — argument parsing, global flags, dispatch (spec §8.2.3 "CLI shell", IR-005).

Architectural role: this layer is deliberately thin — no domain logic lives here
(§8.2.3). The pipeline subcommands (scan/plan/apply/verify/restore, IR-001..IR-004,
IR-008) land milestone by milestone (MS-1+); at MS-0 the surface is the entry point
plus the IR-005 global flags.

Cross-file contracts:
- ``--verbose``/``--quiet`` are mutually exclusive by IR-005 (a hard usage error,
  exit 2 — not the "quiet wins" fallback the logging research floated; the spec is
  binding). Their level mapping lives in :mod:`docmend.observability`.
- ``--dry-run``/``-n`` is accepted globally per IR-005 and threaded through
  :class:`GlobalOptions`; it gains effect when write-capable commands land (MS-3).
  It can only ever make a run more conservative (NFR-004).
- Exit codes follow the §18.5 taxonomy; Click's usage-error exit code (2) already
  matches "input error", which is why BadParameter is used for flag conflicts.
"""

from dataclasses import dataclass
from typing import Annotated

import typer

from docmend import __version__

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
        # No subcommands exist yet (MS-1+); a bare invocation shows help, exit 0.
        typer.echo(ctx.get_help())
        raise typer.Exit(0)
