"""Smoke test: proves the package imports and the verification gate has something to run.

Replace/expand once real modules land — this exists so the Python Tooling SSOT gate
(pytest + coverage) is green on a pre-implementation repo rather than failing on an
empty test corpus. See docs/decisions/ for adoption context.
"""

from importlib.metadata import version

from docmend import __version__


def test_version__is_importable__matches_pyproject() -> None:
    # Derived from installed metadata, not hardcoded — a release version bump
    # must not be able to fail this test while leaving the two in sync.
    assert __version__ == version("docmend")
