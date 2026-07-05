"""Strip the dead H1 self-link from the editor-generated ToC in docs/specs/docmend.md.

The editor's "generate Table of Contents" feature always emits an unindented root
entry linking to the document's own H1 title. The project-standards spec validator's
SV-ANCHOR check only indexes ##-#### headings (never H1), so that one line is always
a dead anchor. Run this after the editor regenerates the ToC on save, before
`spec validate`. Idempotent: a no-op if the entry is already gone.
"""

import re
import sys
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parent.parent / "docs" / "specs" / "docmend.md"

# Matches the unindented ToC root entry, e.g.:
#   - [`docmend` — Specification (Full)](#docmend--specification-full)
# immediately followed by the first indented child entry, e.g.:
#     - [Revision History](#revision-history)
ROOT_ENTRY = re.compile(r"^- \[[^\]]+\]\(#[^)]+\)\n(?=  - \[)", re.MULTILINE)


def main() -> int:
    text = SPEC_PATH.read_text(encoding="utf-8")
    fixed, count = ROOT_ENTRY.subn("", text)
    if count == 0:
        print("No dead H1 ToC entry found; nothing to fix.")
        return 0
    if count > 1:
        print(
            f"Expected exactly one match, found {count}; aborting without writing.", file=sys.stderr
        )
        return 1
    SPEC_PATH.write_text(fixed, encoding="utf-8")
    print(f"Removed the H1 self-link ToC entry from {SPEC_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
