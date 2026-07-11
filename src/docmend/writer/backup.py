"""Tool-written backups — verify-then-mutate (FR-006, ERR-004, adr-0004 amended, adr-0019).

Layout: {backup_root}/{run_id}/{action_seq}/{role}/{relative_path} — keyed by
run, action, and role so no two backups in one run can ever share a key
(DMR-01: an in-place rewrite's source copy and a rename's overwritten-target
copy may share a relative path; the old run/relative-path layout let the
second silently replace the first). Keys are WRITE-ONCE: the publish is
no-clobber, and an existing file at a key raises BackupError — a retry is a
new run with a new run_id, never a rewrite of an existing key. §7.4 retention
unchanged (the tool never deletes its own backups).

Sequence per FR-006: write the copy, fsync it, RE-READ it from disk, re-hash,
compare to the plan's recorded source hash — only then may the caller touch
the original. Any failure raises BackupError (ERR-004) with the original
still untouched.
"""

import hashlib
from pathlib import Path
from typing import Literal

from docmend.writer.atomic import WriteError, atomic_write_bytes

type BackupRole = Literal["source", "overwritten"]


class BackupError(Exception):
    """Backup copy or verification failed (ERR-004); the original is untouched."""


def backup_file(
    data: bytes,
    *,
    backup_root: Path,
    run_id: str,
    action_seq: str,
    role: BackupRole,
    relative_path: str,
    expected_sha256: str,
) -> Path:
    dest = backup_root / run_id / action_seq / role / relative_path
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # clobber=False publishes via hardlink: atomic AND EEXIST-safe, which
        # is what makes the write-once contract race-proof rather than a
        # check-then-write.
        atomic_write_bytes(dest, data, clobber=False)
    except FileExistsError as exc:
        msg = (
            f"{dest}: backup key already occupied — backup keys are write-once "
            f"(a second write to one (run, action, role, path) key is a defect, "
            f"never a legitimate retry; ERR-004)"
        )
        raise BackupError(msg) from exc
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
