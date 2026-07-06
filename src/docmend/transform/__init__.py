"""Transform layer — pure text transformations only (spec §8.2.3, NFR-005).

Architectural role: every function in this package is text in, text out — no
filesystem access, no imports of os/io/pathlib/shutil/tempfile, and never the
writer layer. This is not a convention but a mechanically enforced contract
(OQ-033): the `[tool.importlinter]` forbidden contract in pyproject.toml gates
imports in CI, and an autouse fixture in tests/unit/transform/ blocks
open/os.open/io.FileIO at runtime. Both were wired at MS-0, before any
transform code existed, so no transform has ever been written outside them.

Transforms land in MS-2 (encoding decode/encode, newline normalization,
whitespace transforms — FR-007..FR-009).
"""
