"""Legacy-encoding detection — the charset-normalizer rung of FR-007 (adr-0009).

Architectural role: §8.2.3 requires the encoding-detection dependency to be
replaceable behind an interface; this module IS that interface. Everything
else in docmend sees only `detect_legacy`/`detect_legacy_bytes` and the
DetectedEncoding fact model.

Contract facts (OQ-015, adr-0009):
- charset-normalizer is the SOLE detector; 3.x exposes no `.confidence`, so
  confidence is computed as 1.0 - CharsetMatch.chaos.
- `None` means the detector produced no candidate at all — the planning layer
  maps that to the `binary-suspect` skip; it is NOT an error.
- Callers gate invocation (discovery only calls for no-BOM, non-UTF-8,
  NUL-free files with detection enabled); this module never decides policy.
"""

from pathlib import Path
from typing import Protocol, cast

from charset_normalizer import CharsetMatches
from charset_normalizer import (
    from_bytes as _from_bytes,  # pyright: ignore[reportUnknownVariableType]
)
from charset_normalizer import from_path as _from_path  # pyright: ignore[reportUnknownVariableType]

from docmend.inventory import DetectedEncoding


class _FromPath(Protocol):
    """The slice of charset-normalizer's `from_path` signature docmend uses.

    charset-normalizer types its `path` parameter as a bare (unparameterized)
    `PathLike`, which basedpyright strict flags as partially unknown; this
    Protocol is the typed seam (cast once, at import time) — the artifacts.py
    `_CompiledValidator` precedent applied to a function instead of an
    instance.
    """

    def __call__(self, path: Path) -> CharsetMatches: ...


class _FromBytes(Protocol):
    """The slice of charset-normalizer's `from_bytes` signature docmend uses.

    Same typed-seam rationale as `_FromPath`. `detect_legacy_bytes` feeds the
    scan-side head buffer here: when a candidate file fits entirely within
    discovery's head buffer, running the detector over those already-read bytes
    is verdict-equivalent to reopening the file (`from_path` reads and delegates
    to `from_bytes` over the same content), so it eliminates the second read
    without changing detection. A TRUNCATED head is deliberately never passed —
    a partial sample can yield a different verdict than the full file.
    """

    def __call__(self, sequences: bytes) -> CharsetMatches: ...


from_path = cast(_FromPath, _from_path)
from_bytes = cast(_FromBytes, _from_bytes)


def _to_detected(matches: CharsetMatches) -> DetectedEncoding | None:
    best = matches.best()
    if best is None:
        return None
    confidence = min(1.0, max(0.0, 1.0 - best.chaos))
    return DetectedEncoding(name=best.encoding, confidence=confidence, method="charset-normalizer")


def detect_legacy(path: Path) -> DetectedEncoding | None:
    return _to_detected(from_path(path))


def detect_legacy_bytes(head: bytes) -> DetectedEncoding | None:
    """Detect over an in-memory head buffer that holds the file's full content.

    The caller (discovery) must only pass a COMPLETE file (head buffer not
    truncated); see `_FromBytes` for why a partial head is never fed here."""
    return _to_detected(from_bytes(head))
