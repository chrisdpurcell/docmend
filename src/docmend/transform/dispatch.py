"""Per-file-class transform dispatch (adr-0016) and the EC-005 invariant metric.

Architectural role: the "dispatch is a seam in the transform layer, not
scattered conditionals" decision (adr-0016) lives here — planning asks this
module what a file's bytes would become and which operations that took;
it never sequences transforms itself.

Cross-file contracts:
- `Operation` mirrors the plan schema's operation enum verbatim; docmend.plan
  imports it from here so schema, models, and dispatch share one vocabulary.
  (plan -> transform is the allowed import direction; transform imports no
  internal module, keeping the NFR-005 import-linter contract trivially green.)
- Scalars in, scalars out: config booleans/ints are unpacked by the caller
  because docmend.config imports pathlib, which this package is forbidden.
- Canonical execution order (= the recorded operations order): reencode
  happens outside this module (bytes-level), then normalize_newlines,
  trim_trailing_whitespace, normalize_tabs, collapse_blank_lines,
  ensure_final_newline; rename is a path operation appended by planning.
"""

from typing import Literal

from docmend.transform.newlines import normalize_newlines
from docmend.transform.whitespace import (
    collapse_blank_lines,
    ensure_final_newline,
    normalize_tabs,
    trim_trailing,
)

type Operation = Literal[
    "rename",
    "reencode",
    "normalize_newlines",
    "trim_trailing_whitespace",
    "ensure_final_newline",
    "collapse_blank_lines",
    "normalize_tabs",
    "frontmatter_migrate",
]
type FileClass = Literal["text", "markup"]

_TEXT_SUFFIXES = frozenset({".txt", ".md"})


def classify_suffix(suffix: str) -> FileClass:
    return "text" if suffix.lower() in _TEXT_SUFFIXES else "markup"


def non_whitespace_count(text: str) -> int:
    """EC-005 metric: decoded non-whitespace characters (Unicode-aware via str.split)."""
    return sum(len(part) for part in text.split())


def apply_text_transforms(
    text: str,
    file_class: FileClass,
    *,
    trim_trailing_ws: bool,
    final_newline: bool,
    collapse_max: int | None,
    tab_width: int | None,
) -> tuple[str, list[Operation]]:
    operations: list[Operation] = []

    def step(op: Operation, result: str, current: str) -> str:
        if result != current:
            operations.append(op)
        return result

    out = step("normalize_newlines", normalize_newlines(text), text)
    if file_class == "markup":
        # adr-0016: markup receives encoding + EOL normalization only.
        return out, operations
    if trim_trailing_ws:
        out = step("trim_trailing_whitespace", trim_trailing(out), out)
    if tab_width is not None:
        out = step("normalize_tabs", normalize_tabs(out, tab_width), out)
    if collapse_max is not None:
        out = step("collapse_blank_lines", collapse_blank_lines(out, collapse_max), out)
    if final_newline:
        out = step("ensure_final_newline", ensure_final_newline(out), out)
    return out, operations
