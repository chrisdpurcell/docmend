"""Smoke test: proves the package imports and the verification gate has something to run.

Replace/expand once real modules land — this exists so the Python Tooling SSOT gate
(pytest + coverage) is green on a pre-implementation repo rather than failing on an
empty test corpus. See docs/decisions/ for adoption context.
"""

from docmend import __version__


def test_version__is_importable__matches_pyproject() -> None:
    assert __version__ == "2.0.0"
