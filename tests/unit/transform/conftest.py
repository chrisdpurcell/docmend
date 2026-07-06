"""Runtime half of the NFR-005 purity enforcement (spec OQ-033).

Every test under tests/unit/transform/ runs with file-opening primitives blocked,
so a transform that sneaks in filesystem access fails its own unit tests even if
it evades the import-linter contract (e.g. via a late/local import). Wired at
MS-0, before any transform code existed.
"""

import builtins
import io
import os
from builtins import open as builtin_open
from typing import Any, NoReturn

import pytest


@pytest.fixture(autouse=True)
def block_filesystem_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: NFR-005 — transform unit tests must never touch the filesystem.

    Note: allows reading of .pyc bytecode cache files to support Hypothesis
    property-based testing, which dynamically loads modules. Only the transform
    code is forbidden from accessing the filesystem; infrastructure (pytest,
    Hypothesis, Python import machinery) may read pre-compiled .pyc files.
    """

    def selective_blocker(*args: Any, **kwargs: Any) -> Any:
        # Allow accessing .pyc files and their temp files (bytecode cache, not code)
        if args:
            path_str = str(args[0])  # Handle both str and Path objects
            # Allow .pyc files themselves and pytest's temporary .pyc.NNNNN files
            if path_str.endswith(".pyc") or ".pyc." in path_str:
                # All modes allowed for .pyc files (read, write, append)
                return builtin_open(*args, **kwargs)  # type: ignore[no-any-return]  # noqa: PTH123

        msg = "filesystem access is forbidden in transform unit tests (NFR-005/OQ-033)"
        raise RuntimeError(msg)

    def os_blocker(*_args: Any, **_kwargs: Any) -> NoReturn:
        msg = "filesystem access is forbidden in transform unit tests (NFR-005/OQ-033)"
        raise RuntimeError(msg)

    def fileio_blocker(*_args: Any, **_kwargs: Any) -> NoReturn:
        msg = "filesystem access is forbidden in transform unit tests (NFR-005/OQ-033)"
        raise RuntimeError(msg)

    monkeypatch.setattr(builtins, "open", selective_blocker)
    monkeypatch.setattr(os, "open", os_blocker)
    monkeypatch.setattr(io, "FileIO", fileio_blocker)
