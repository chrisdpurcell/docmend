"""Self-test of the purity fixture (spec NFR-005, OQ-033).

Proves the autouse guard in conftest.py actually blocks each named primitive —
otherwise the enforcement could silently rot while every transform test passes.
"""

import io
import os

import pytest

BLOCKED = "filesystem access is forbidden"


def test_builtin_open__blocked() -> None:
    with pytest.raises(RuntimeError, match=BLOCKED):
        open("anything")  # noqa: PTH123, SIM115 — the call must raise, nothing to manage


def test_os_open__blocked() -> None:
    with pytest.raises(RuntimeError, match=BLOCKED):
        os.open("anything", os.O_RDONLY)


def test_io_fileio__blocked() -> None:
    with pytest.raises(RuntimeError, match=BLOCKED):
        io.FileIO("anything")
