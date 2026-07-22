"""Put the repository root on ``sys.path`` for the test session.

pytest inserts the directory of the first conftest it discovers (this one, at the
rootdir) at the front of ``sys.path`` under the default ``prepend`` import mode.
That makes the shared fixture builders importable as ``tests.helpers.*`` — the
role previously filled by ``[tool.pytest.ini_options].pythonpath = ["."]``, which
the V5 python-tooling standard renders as a canonical table that cannot carry a
``pythonpath`` entry (see upstream issue #14). basedpyright does not read this
file — it resolves ``tests.helpers`` on its own once the custom ``extraPaths`` is
dropped, because its default execution root is the directory holding pyproject.toml.
"""
