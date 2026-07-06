"""docmend — normalize, repair, and convert legacy .txt/.html documents to Markdown.

MS-0 foundation surface: CLI entry point (docmend.cli), strict TOML configuration
(docmend.config), structured logging + run-ID conventions (docmend.observability),
and the empty transform/writer layer packages that anchor the NFR-005 purity
contract. The pipeline commands land per the spec's milestone ladder
(docs/specs/docmend.md §19).
"""

__version__ = "0.1.0"
