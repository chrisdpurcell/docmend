# docmend

`docmend` is a Python CLI tool for managing and maintaining large libraries of text-based documents. It is designed to help users clean up, modernize, and convert poorly formatted text and HTML documents into well-structured markdown files.

## Problem

I have a large library (>100k) of poorly formatted text (`.txt`), html (`.html`, `.htm`, etc.) documents that need to be modernized and converted into markdown (`.md`).

Notable issues include:

- Poor and broken formatting (e.g., inconsistent headings, spacing, and indentation) from years of handling and editing. Many documents date back the 1990s and even earlier.
- Mix of encoding formats (e.g., UTF-8, ISO-8859-1, Windows-1252, etc.) and character sets (e.g., ASCII, Latin-1, etc.) and end-of-line formats (e.g., LF, CRLF, CR) that need to be normalized to UTF-8 and LF.
- There is no file naming convention or structure, and many files have non-descriptive names (e.g., `doc1.txt`, `file2.html`, etc.) that need to be renamed to something more meaningful.
- There is a wide variety of line and paragraph breaking, inconsistent use of whitespace, extra whitespace and in many cases missing whitespace (words run together and paragraphs no longer separate properly), tab/indenting inconsistencies, and other formatting issues that need to be cleaned up.
- Poor spelling, grammar, and punctuation that need to be corrected.
- Many appear corrupted or broken, and need to be repaired or reconstructed.
- Many are full of garbled and garbage text, html tags, and other "ASCII pollution" that needs to be cleaned up and removed.

## Desired Final Output

The tooling is not necessarily intended to be limited to strictly producing the desired final output described below, but it should be able to produce it. The tools should also be generally useful for cleaning up and modernizing text and HTML documents in a variety of ways, including but not limited to:

- **Markdown:** Pandoc Markdown for the file format, CommonMark-ish body rules, strict YAML frontmatter for metadata. Make the body boring and portable; make the frontmatter rich and machine-validated.
  - _Reasoning:_ CommonMark is the stable baseline for readable Markdown syntax, while Pandoc explicitly supports YAML metadata blocks and has strong conversion paths for EPUB, HTML, DOCX, or PDF.
  - [commonmark.org](https://commonmark.org/?utm_source=openai)
  - [pandoc.org](https://pandoc.org/demo/example33/8.10-metadata-blocks.html?utm_source=openai)
- **YAML Frontmatter:** Strict YAML frontmatter for metadata, including title, author, date, tags, and other relevant information.
  - _Stable IDs:_ never depend on filename alone.
  - _Source provenance:_ original path, source hash, import batch, conversion version.
  - _Controlled vocabularies:_ genres, ratings, status, language, story type. Freeform tags are useful, but they get messy fast.
  - _Generated fields:_ word count, chapter count, checksum, detected language. Regenerate them rather than hand- editing.
  - _Schema validation:_ JSON Schema or similar, so bad metadata does not quietly poison the index.
  - _Search separation:_ frontmatter feeds faceted search; the Markdown body feeds full-text search.
- **Encoding:** UTF-8
- **Line Endings:** LF (UNIX-style)

## Requirements

- **Backup and version control:** Absolutely critical since the volume of files precludes complete manual review. The tool should be able to create backups of the original files before making any changes, and it should support version control systems (e.g., Git) for tracking changes and reverting if necessary.
- **Performance and scalability:** The tool should be able to handle large libraries of documents efficiently, with support for parallel processing and batch operations.
- **Error handling and logging:** The tool should provide robust error handling and logging mechanisms to ensure that issues can be diagnosed and resolved quickly, including while in the middle of a batch operation.
- **Resume and continuation:** The tool should be able to resume processing from where it left off in case of interruptions or failures, and it should support continuation of batch operations without losing progress.
- **Logging and reporting:** The tool should provide detailed logging and reporting capabilities, including summaries of changes made, errors encountered, and statistics on the processing of documents.

## Flags

- `--help` `-h`: Show the help message and exit.
- `--dry-run` `-n`: Run the tool without making any changes to the files. This is useful for testing and previewing the changes that will be made.
- `--verbose` `-v`: Print detailed information about the processing steps and any issues encountered. This is useful for debugging and understanding the tool's behavior.
- `--quiet` `-q`: Suppress non-essential output, showing only errors and critical messages.
