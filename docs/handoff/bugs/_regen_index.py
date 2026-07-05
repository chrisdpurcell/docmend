#!/usr/bin/env python3
"""Regenerate docs/handoff/bugs/INDEX.md from bug-file frontmatter.

Run directly (`python3 docs/handoff/bugs/_regen_index.py`) after adding,
removing, or renaming a bug file. build_index() is kept pure (no file writes)
so it can be unit-tested and diffed against the committed INDEX.md; only the
__main__ path writes.
"""

import re
from pathlib import Path

BUGS = Path(__file__).parent


def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract key-value fields from a YAML front-matter block (--- ... ---).

    Returns an empty dict when no front-matter fence is found. Values have
    leading/trailing whitespace and quote characters stripped; Prettier rewrites
    managed-doc YAML to single quotes, so a double-quote-only strip would leak
    `'001'` into INDEX table cells.
    """
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("\"'")
    return fields


def build_index(bugs_dir: Path) -> str:
    """Render the full INDEX.md text from the NNN-*.md bug records in bugs_dir.

    Pure (no side effects) so it can be unit-tested directly and diffed against the
    committed INDEX.md. The __main__ path is the only writer.
    """
    rows: list[tuple[str, str, str, str, str]] = []
    for path in sorted(bugs_dir.glob("[0-9][0-9][0-9]-*.md")):
        fields = parse_frontmatter(path.read_text(encoding="utf-8"))
        rows.append(
            (
                fields.get("bug_id", "?"),
                fields.get("date", "?"),
                fields.get("title", "?"),
                fields.get("services", "[]").strip("[]"),
                fields.get("status", "?"),
            )
        )

    lines = [
        "# Bug Index",
        "",
        "Generated from frontmatter. Regenerate with `python3 docs/handoff/bugs/_regen_index.py`.",
        "",
    ]
    if not rows:
        lines.append("_No bugs recorded._")
    else:
        lines.extend(
            [
                "| # | Date | Title | Services | Status |",
                "|---|---|---|---|---|",
            ]
        )
        for row in rows:
            lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines) + "\n"


def main() -> None:
    """Write the regenerated INDEX.md to the bugs directory."""
    (BUGS / "INDEX.md").write_text(build_index(BUGS), encoding="utf-8")


if __name__ == "__main__":
    main()
