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
  - The manifest matters because rename operations are otherwise painful to undo.
  - Preserve original data. For a large library, require at least one of these before apply mode:
    - library is in Git (my library is GBs of text documents; public git solutions like GitHub or GitLab are unsuitable for hosting, but I am considering self-hosted solutions like Gitea or Gogs)
    - external backups exist
    - tool writes backups
    - tool emits a reversible rename/write manifest
- **Performance and scalability:** The tool should be able to handle large libraries of documents efficiently, with support for parallel processing and batch operations.
- **Error handling and logging:** The tool should provide robust error handling and logging mechanisms to ensure that issues can be diagnosed and resolved quickly, including while in the middle of a batch operation.
- **Resume and continuation:** The tool should be able to resume processing from where it left off in case of interruptions or failures, and it should support continuation of batch operations without losing progress.
- **Logging and reporting:** The tool should provide detailed logging and reporting capabilities, including summaries of changes made, errors encountered, and statistics on the processing of documents.
- **Collision handling:** The tool should be able to handle file name collisions and other conflicts gracefully, with options for renaming or overwriting files as needed.
- **Encoding detection and handling:** The tool should be able to detect and handle different encoding formats and character sets, with options for converting to UTF-8 as needed.
  - Encoding detection is not perfect. UTF-8, UTF-8 with BOM, Windows-1252, ISO-8859-1, and random legacy encodings can be ambiguous. The tool should never silently “fix” low-confidence files.
  - `.txt` to `.md` is not always semantically correct. Renaming a file to Markdown does not make it Markdown. The tool should distinguish between _rename extension only_ and _convert document structure to Markdown_. Those are different problems.
- **Include/exclude filters:** The tool should support include/exclude filters for processing specific files or directories, based on file name patterns, extensions, or other criteria.
- **Idempotent operations:** The tool should be able to perform operations in an idempotent manner, meaning that running the same operation multiple times should produce the same result without introducing errors or inconsistencies.
- **Extensive testing against "weird" documents:** The tool should be tested against a wide variety of poorly formatted and corrupted documents to ensure that it can handle edge cases and unexpected input gracefully since the full range of possible document anomalies is unknown.
  - For risky files, prefer _skip and report_ over _guess and rewrite_. The tool should be conservative in its transformations, especially when dealing with potentially corrupted or ambiguous files.

## Architecture

### Discovery layer

Find candidate files, but do not modify anything.

Responsibilities:

- walk directories
- ignore binary files
- respect excludes such as .git/, node_modules/, archives, images, PDFs
- classify files by extension and apparent content
- collect metadata: path, size, current suffix, newline type, detected encoding, whether already UTF-8

This should produce a structured inventory.

### Planning layer

Given the inventory and config, decide what would happen.

Example planned actions:

```text
rename: notes/foo.txt -> notes/foo.md
rewrite_encoding: cp1252 -> utf-8
rewrite_newlines: CRLF -> LF
normalize_whitespace: trim trailing spaces, collapse excessive blank lines
skip: binary, unknown encoding, conflicting target path
```

This layer is where you catch dangerous cases before touching files.

Examples:

- foo.txt wants to become foo.md, but foo.md already exists.
- file appears binary despite .txt extension.
- encoding confidence is low.
- decoding only works with replacement characters.
- file contains NUL bytes.
- generated output would be empty or much smaller than input.

### Transform layer

Each transformation should be small and testable.

Good transform functions are boring:

```Python
def normalize_newlines(text: str) -> str: return text.replace("\r\n", "\n").replace("\r", "\n")
```

Keep transforms pure where possible: input text in, output text out. Filesystem writes should be handled elsewhere.

### Writer layer

This is the dangerous layer, so isolate it.

It should handle:

- atomic writes
- preserving permissions where reasonable
- optional backup files
- refusing to overwrite unless explicitly allowed
- writing UTF-8 only
- writing LF only
- recording before/after hashes
- producing a machine-readable report

For this kind of tool, prefer atomic replace over in-place mutation:

1. read original
2. transform in memory
3. write temp file in same directory
4. fsync temp file
5. os.replace(temp, target)
6. fsync parent directory where practical

Overkill for casual use, but correct for bulk destructive edits.

## CLI shape

Make the CLI intentionally conservative; example usage:

```bash
docmend scan PATH
docmend plan PATH --config cleaner.toml --out plan.json
docmend apply plan.json --dry-run
docmend apply plan.json --backup-dir .textlib-cleaner-backups
docmend verify PATH
```

### Flags

- `--help` `-h`: Show the help message and exit.
- `--dry-run` `-n`: Run the tool without making any changes to the files. This is useful for testing and previewing the changes that will be made.
- `--verbose` `-v`: Print detailed information about the processing steps and any issues encountered. This is useful for debugging and understanding the tool's behavior.
- `--quiet` `-q`: Suppress non-essential output, showing only errors and critical messages.

Other example flags:

```bash
--include "*.txt"
--include "*.md"
--exclude ".git/**"
--exclude "**/.venv/**"
--rename-txt-to-md
--encoding utf-8
--detect-encoding
--normalize-newlines lf
--trim-trailing-whitespace
--ensure-final-newline
--collapse-blank-lines 3
--dry-run
--fail-on-low-confidence-encoding
--backup-dir PATH
--report report.json
```

## Configuration

Use TOML. It fits Python projects and is easy for agents to edit.

Example:

```TOML
[paths]
include = ["**/*.txt", "**/*.md"]
exclude = [
  ".git/**",
  ".venv/**",
  "node_modules/**",
  "**/*.pdf",
  "**/*.png",
  "**/*.jpg",
  "**/*.zip",
]

[rename]
txt_to_md = true
on_collision = "skip" # skip | fail | overwrite

[encoding]
target = "utf-8"
detect = true
fail_below_confidence = 0.80

[newlines]
target = "lf"

[whitespace]
trim_trailing = true
ensure_final_newline = true
collapse_blank_lines = 3
normalize_tabs = false

[write]
dry_run_default = true
backup_dir = ".textlib-cleaner-backups"
atomic = true
```

## Tech Stack

- uv
- ruff
- basedpyright
- pytest

For runtime dependencies:

| Need                    | Recommendation                            |
| ----------------------- | ----------------------------------------- |
| CLI                     | ``typer`                                  |
| Encoding detection      | `charset-normalizer`                      |
| Glob-style ignore rules | `pathspec`                                |
| Rich reports            | plain json and `rich`                     |
| Config parsing          | Python 3.14+ `tomllib` for read-only TOML |

## Implementation Strategy

Do not start with advanced Markdown restructuring. Get the safe migration substrate right first.

Build the first version around these commands only:

```bash
docmend scan
docmend plan --config cleaner.toml --out plan.json
docmend apply plan.json --dry-run
docmend apply plan.json --backup-dir .textlib-cleaner-backups
docmend verify PATH
```

Initial supported transformations:

1. .txt → .md
2. decode as UTF-8 / UTF-8-BOM / detected legacy encoding
3. write as UTF-8 without BOM
4. convert all newlines to LF
5. trim trailing whitespace
6. ensure exactly one final newline
7. report skipped files and reasons

Do not start with advanced Markdown restructuring. Get the safe migration substrate right first.
