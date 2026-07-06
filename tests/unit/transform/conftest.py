"""Runtime half of the NFR-005 purity enforcement (spec OQ-033).

Every test under tests/unit/transform/ runs with file-opening primitives blocked,
so a transform that sneaks in filesystem access fails its own unit tests even if
it evades the import-linter contract (e.g. via a late/local import). Wired at
MS-0, before any transform code existed.
"""

import builtins
import io
import os
from typing import NoReturn

import pytest


@pytest.fixture(autouse=True)
def block_filesystem_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: NFR-005 — transform unit tests must never touch the filesystem."""

    def blocked(*_args: object, **_kwargs: object) -> NoReturn:
        msg = "filesystem access is forbidden in transform unit tests (NFR-005/OQ-033)"
        raise RuntimeError(msg)

    monkeypatch.setattr(builtins, "open", blocked)
    monkeypatch.setattr(os, "open", blocked)
    monkeypatch.setattr(io, "FileIO", blocked)
