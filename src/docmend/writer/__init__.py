"""Writer layer — the isolated dangerous layer (spec §8.2.3, D-003, NFR-002).

Architectural role: the ONLY component that mutates the library. Landed at
MS-3 across five modules: `atomic` (same-directory temp-file + fsync +
`os.replace`, crash-safe rewrite/rename primitives), `backup` (verify-then-mutate
tool backups under `--backup-dir`, including clobbered-target preservation),
`gate` (the pure-predicate FR-005 safety gate — preservation strategy,
collision policy, hash-staleness, and containment checks, all evaluated before
any mutation), `manifest` (fsync-per-record NDJSON manifest recording, with an
append-only-file read rule for restore replay), and `apply` (the `docmend
apply` orchestration: dry-run by default, snapshot-driven, per-file FR-003
hash guard). Everything else in docmend is read-only or in-memory by contract;
the import-linter contract (OQ-033) additionally forbids the transform layer
from ever importing this package.
"""
