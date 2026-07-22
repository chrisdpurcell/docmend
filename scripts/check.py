"""Run the selected Python verification gate and stop at the first failure."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

COMMANDS: tuple[tuple[str, ...], ...] = (
    ("uv", "run", "ruff", "format", "--check", "."),
    ("uv", "run", "ruff", "check", "."),
    ("uv", "run", "basedpyright"),
    ("uv", "run", "coverage", "run", "-m", "pytest"),
    ("uv", "run", "coverage", "report"),
    ("uv", "run", "pip-audit"),
)


def run_command(command: Sequence[str]) -> int:
    """Run one gate command and preserve its exit code."""
    print(f"\n$ {' '.join(command)}", flush=True)
    return subprocess.run(command, check=False).returncode


def main() -> int:
    """Run the gate in order and stop at the first failure."""
    for command in COMMANDS:
        if return_code := run_command(command):
            return return_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
