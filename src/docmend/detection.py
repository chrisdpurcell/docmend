"""Legacy-encoding detection — the charset-normalizer rung of FR-007 (adr-0009).

Architectural role: §8.2.3 requires the encoding-detection dependency to be
replaceable behind an interface; this module IS that interface. Everything
else in docmend sees only `detect_legacy` and the DetectedEncoding fact model.

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


from_path = cast(_FromPath, _from_path)


def detect_legacy(path: Path) -> DetectedEncoding | None:
    best = from_path(path).best()
    if best is None:
        return None
    confidence = min(1.0, max(0.0, 1.0 - best.chaos))
    return DetectedEncoding(name=best.encoding, confidence=confidence, method="charset-normalizer")
