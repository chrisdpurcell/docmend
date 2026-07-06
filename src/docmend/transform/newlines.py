"""Newline normalization (FR-008) — the spec's "two-replace one-liner" (§8.1).

Pure (NFR-005): text in, text out. Order matters: CRLF must collapse before
bare CR, or every CRLF would double-convert to two LFs. Unicode line
separators (NEL, LS, PS) are document content, not newline styles — untouched.
"""


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")
