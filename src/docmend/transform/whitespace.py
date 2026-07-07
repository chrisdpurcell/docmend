"""Whitespace transforms (FR-009; tab semantics per adr-0016/OQ-031).

Pure (NFR-005): text in, text out, plain string methods only (§8.5 regex rule
satisfied by using none). Shared precondition: input is LF-normalized —
planning always runs normalize_newlines first, so lines are split on "\\n".

A "blank line" is empty or whitespace-only. Collapsing keeps the first `max`
lines of an over-long run VERBATIM: cleaning whitespace-only survivors is
trim_trailing's job, keeping each transform individually configurable (FR-009).
"""


def trim_trailing(text: str) -> str:
    return "\n".join(line.rstrip(" \t") for line in text.split("\n"))


def ensure_final_newline(text: str) -> str:
    return text.rstrip("\n") + "\n"


def collapse_blank_lines(text: str, max_consecutive: int) -> str:
    if not text:
        return text  # EC-009: no lines means nothing to collapse, never a spurious newline
    # The final "" element after a trailing newline is split() bookkeeping,
    # not a line; peel it off so a trailing blank run is measured correctly.
    lines = text.split("\n")
    trailing_newline = lines[-1] == ""
    if trailing_newline:
        lines = lines[:-1]
    kept: list[str] = []
    run = 0
    for line in lines:
        if line.strip(" \t") == "":
            run += 1
            if run > max_consecutive:
                continue
        else:
            run = 0
        kept.append(line)
    return "\n".join(kept) + ("\n" if trailing_newline else "")


def normalize_tabs(text: str, tab_width: int) -> str:
    converted: list[str] = []
    for line in text.split("\n"):
        prefix_len = len(line) - len(line.lstrip(" \t"))
        prefix = line[:prefix_len].replace("\t", " " * tab_width)
        converted.append(prefix + line[prefix_len:])
    return "\n".join(converted)
