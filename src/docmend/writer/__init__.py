"""Writer layer — the isolated dangerous layer (spec §8.2.3, D-003, NFR-002).

Architectural role: the ONLY component that mutates the library. Atomic replace
(temp file + fsync + os.replace in the same directory), backups, manifest
recording, overwrite refusal, UTF-8/LF-only output. Everything else in docmend
is read-only or in-memory by contract; the import-linter contract (OQ-033)
additionally forbids the transform layer from ever importing this package.

Implementation lands in MS-3 (FR-003..FR-006, FR-011, NFR-002).
"""
