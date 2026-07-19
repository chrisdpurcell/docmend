"""docmend — normalize, repair, and convert legacy .txt/.html documents to Markdown.

v2 surface: the scan → plan → apply → verify pipeline plus restore and resume
(docs/specs/docmend.md §7.3) — CLI shell (docmend.cli), strict TOML configuration
(docmend.config), structured logging + run-ID conventions (docmend.observability),
pure transforms (docmend.transform, NFR-005), and the isolated writer layer
(docmend.writer) with its atomic-write/backup/manifest safety machinery.
"""

__version__ = "2.0.1"
