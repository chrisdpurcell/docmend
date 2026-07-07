"""Tool-written backups — verify-then-mutate (FR-006, ERR-004, adr-0004).

Layout: <backup_root>/<run_id>/<relative_path> — run-keyed so repeated runs
never clobber each other's copies, mirroring §7.4 retention (the tool never
deletes its own backups). The gate (Task 8) has already proven backup_root
lies OUTSIDE the mutation target and is writable (OQ-005).

Sequence per FR-006: write the copy, fsync it, RE-READ it from disk, re-hash,
compare to the plan's recorded source hash — only then may the caller touch
the original. Any failure raises BackupError (ERR-004) with the original
still untouched.
"""

import hashlib
from pathlib import Path

from docmend.writer.atomic import WriteError, atomic_write_bytes


class BackupError(Exception):
    """Backup copy or verification failed (ERR-004); the original is untouched."""


def backup_file(
    data: bytes, *, backup_root: Path, run_id: str, relative_path: str, expected_sha256: str
) -> Path:
    dest = backup_root / run_id / relative_path
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(dest, data)
    except (OSError, WriteError) as exc:
        msg = f"{dest}: backup copy failed ({exc})"
        raise BackupError(msg) from exc
    try:
        reread = dest.read_bytes()
    except OSError as exc:
        msg = f"{dest}: backup unreadable after write ({exc.strerror or exc})"
        raise BackupError(msg) from exc
    digest = f"sha256:{hashlib.sha256(reread).hexdigest()}"
    if digest != expected_sha256:
        msg = (
            f"{dest}: backup verification failed — re-hash {digest} does not match "
            f"the plan's recorded source hash {expected_sha256} (ERR-004)"
        )
        raise BackupError(msg)
    # Absolute by contract (codex CR-005): this path lands in the manifest,
    # which restore must be able to follow from any cwd (IR-008).
    return dest.resolve()
