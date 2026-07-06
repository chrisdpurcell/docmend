"""Architectural purity gate — spec NFR-005, OQ-033 (import-linter forbidden contract).

Running lint-imports inside pytest means the standard-owned check workflow enforces
the contract in CI without being edited (conventions #8): wherever the pytest gate
runs, this contract runs.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_transform_purity_contract__lint_imports_passes() -> None:
    """spec: NFR-005 — docmend.transform must never import filesystem modules
    (os/io/pathlib/shutil/tempfile) or docmend.writer; contract in pyproject.toml."""
    lint_imports = Path(sys.executable).parent / "lint-imports"
    assert lint_imports.is_file(), "import-linter missing from the dev environment"
    result = subprocess.run(  # fixed argv, no shell; --no-cache keeps the repo litter-free
        [str(lint_imports), "--no-cache"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, f"NFR-005 contract broken:\n{result.stdout}{result.stderr}"
