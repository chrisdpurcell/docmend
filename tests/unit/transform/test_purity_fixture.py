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


def test_builtin_open__allows_pycache_files() -> None:
    # Verify that .pyc files under __pycache__/ are allowed through the guard.
    # Attempting to read a non-existent .pyc file should raise FileNotFoundError
    # (file doesn't exist), not RuntimeError (guard blocked it).
    with pytest.raises(FileNotFoundError):
        open("/tmp/__pycache__/test.cpython-314.pyc", "rb")  # noqa: PTH123, SIM115 — the call must raise, nothing to manage


def test_builtin_open__blocks_pyc_without_pycache() -> None:
    # Verify that .pyc files NOT under __pycache__/ are properly blocked.
    # A path like "leak.pyc" should raise RuntimeError from the guard.
    with pytest.raises(RuntimeError, match=BLOCKED):
        open("leak.pyc", "rb")  # noqa: PTH123, SIM115 — the call must raise, nothing to manage
