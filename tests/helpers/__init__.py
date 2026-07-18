"""Shared test fixture builders (not a pytest plugin — plain importable helpers)."""

from pathlib import Path


def replace_with_new_inode(path: Path, data: bytes) -> None:
    """Replace path while its original inode remains allocated during staging."""
    replacement = path.with_name(f".{path.name}.replacement")
    replacement.write_bytes(data)
    replacement.replace(path)
