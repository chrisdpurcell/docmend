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


def test_builtin_open__blocks_pycache_write_mode() -> None:
    # A write to a .pyc path is never legitimate application behavior (bytecode
    # caching is collection-time, not execution-time, per the fixture's note),
    # so the read-only allowance must not extend to "wb".
    with pytest.raises(RuntimeError, match=BLOCKED):
        open("/tmp/__pycache__/test.cpython-314.pyc", "wb")  # noqa: PTH123, SIM115


def test_builtin_open__allows_pycache_file_via_file_kwarg() -> None:
    # The path can arrive as the `file=` keyword instead of positionally; the
    # allowance must recognize it there too, not just in args[0].
    with pytest.raises(FileNotFoundError):
        open(file="/tmp/__pycache__/test.cpython-314.pyc", mode="rb")  # noqa: PTH123, SIM115


def test_builtin_open__blocks_non_pycache_via_file_kwarg() -> None:
    # A non-.pyc path passed as `file=` must still hit the guard, not slip
    # through simply because it bypassed the positional-arg check.
    with pytest.raises(RuntimeError, match=BLOCKED):
        open(file="leak.txt")  # noqa: PTH123, SIM115
