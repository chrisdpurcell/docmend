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

_READ_ONLY_MODES = frozenset({"r", "rb", "rt"})


def _blocked(*_args: Any, **_kwargs: Any) -> NoReturn:
    msg = "filesystem access is forbidden in transform unit tests (NFR-005/OQ-033)"
    raise RuntimeError(msg)


@pytest.fixture(autouse=True)
def block_filesystem_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: NFR-005 — transform unit tests must never touch the filesystem.

    Note: allows read-only access to .pyc bytecode cache files. The mechanism
    is pytest's assertion-rewrite import hook, which registers Hypothesis's
    lazily-imported internal modules for rewriting and then reads (or, on a
    fully cold cache, writes) their compiled bytecode the first time each is
    imported — not "Hypothesis dynamically loading modules" mid-test, as a
    prior version of this note claimed. Verified empirically: a full-suite run
    against a deleted __pycache__ (both this repo's and the installed
    hypothesis package's) shows every such import completing during test
    *collection*, before this fixture activates, so no write is ever observed
    during test execution. The allowance is therefore narrowed to read modes
    only — a write reaching this guard is unexpected and blocked like any
    other filesystem access, rather than silently permitted.
    """

    def selective_blocker(*args: Any, **kwargs: Any) -> Any:
        # `open()` accepts the path positionally or as `file=`; both must be
        # checked or a kwarg-style call slips past the __pycache__ allowance
        # undetected (indistinguishable from a real leak) and, in the other
        # direction, a legitimate .pyc read passed as `file=` would wrongly
        # raise. Only .pyc paths under __pycache__/, opened read-only, are
        # allowed; application code must never access the filesystem at all
        # (spec NFR-005).
        path_arg = args[0] if args else kwargs.get("file")
        mode = args[1] if len(args) > 1 else kwargs.get("mode", "r")
        if path_arg is not None:
            path_str = str(path_arg)  # Handle both str and Path objects
            if (
                "__pycache__" in path_str
                and (path_str.endswith(".pyc") or ".pyc." in path_str)
                and mode in _READ_ONLY_MODES
            ):
                return builtin_open(*args, **kwargs)  # type: ignore[no-any-return]  # noqa: PTH123
        _blocked()

    monkeypatch.setattr(builtins, "open", selective_blocker)
    monkeypatch.setattr(os, "open", _blocked)
    monkeypatch.setattr(io, "FileIO", _blocked)
