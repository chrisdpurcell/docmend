"""FrontmatterCodec — safe YAML parsing + schema validation for product
frontmatter (FR-016, DR-005, adr-0011, adr-0013, C-006).

Architectural role: the ONLY code path that parses frontmatter out of product
documents. v1 emits no frontmatter (emission is a deferred adr-0010 seam), but
`verify` validates it WHERE PRESENT (adr-0011: a no-frontmatter document is
legal and has nothing to validate), so the parse direction lands first.

Cross-file contracts:
- Duplicate keys are rejected at YAML parse time, BEFORE schema validation — a
  permissive parser silently collapses duplicates and the schema would only
  ever see the collapsed result (C-006).
- Timestamp-looking scalars are preserved as STRINGS (the constructor
  override below), so the schema's `format: date-time` assertion actually
  fires on malformed values instead of ruamel pre-parsing them into datetime
  objects the JSON validator cannot check (adr-0011 rule 4, RQ-021).
- The schema itself is `docmend/schemas/frontmatter.schema.json`, loaded and
  cached through :mod:`docmend.artifacts` like the four run artifacts.
"""

from io import StringIO

from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError, SafeConstructor
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import ScalarNode

from docmend.artifacts import ArtifactError, validate_artifact

FRONTMATTER_SCHEMA_VERSION = "1.0"

#: Frontmatter block delimiters (§9/C-004): the block must be the FIRST content
#: in the file, opened by `---` and closed by `---` (Pandoc also accepts `...`).
_OPEN = "---"
_CLOSERS = ("---", "...")


class FrontmatterError(Exception):
    """Frontmatter that is present but unparseable or schema-invalid."""


class _StringPreservingConstructor(SafeConstructor):
    """SafeConstructor with the timestamp constructor overridden to strings."""


def _construct_str(constructor: SafeConstructor, node: ScalarNode) -> str:
    return constructor.construct_scalar(node)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportReturnType]


_StringPreservingConstructor.add_constructor(  # pyright: ignore[reportUnknownMemberType]
    "tag:yaml.org,2002:timestamp", _construct_str
)


def extract_frontmatter(text: str) -> str | None:
    """The raw YAML block when `text` opens with one, else None (no-frontmatter
    documents are legal, adr-0011 — None is 'nothing to validate', not an error)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _OPEN:
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() in _CLOSERS:
            return "\n".join(lines[1:index])
    return None  # unterminated block: not frontmatter, just body text starting with ---


def parse_frontmatter(block: str) -> dict[str, object]:
    """Parse one YAML frontmatter block safely (duplicate keys rejected, C-006)."""
    yaml = YAML(typ="safe", pure=True)
    yaml.Constructor = _StringPreservingConstructor
    yaml.allow_duplicate_keys = False
    try:
        document: object = yaml.load(StringIO(block))  # pyright: ignore[reportUnknownMemberType]
    except DuplicateKeyError as exc:
        msg = f"duplicate frontmatter key ({exc.problem})"  # pyright: ignore[reportUnknownMemberType]
        raise FrontmatterError(msg) from exc
    except YAMLError as exc:
        msg = f"frontmatter is not valid YAML ({exc})"
        raise FrontmatterError(msg) from exc
    if not isinstance(document, dict):
        msg = "frontmatter is not a YAML mapping"
        raise FrontmatterError(msg)
    return document  # pyright: ignore[reportUnknownVariableType]


def validate_frontmatter(text: str) -> str | None:
    """Validate a document's frontmatter where present (FR-016, adr-0011).

    Returns None when the document has no frontmatter (legal) or the block
    validates; returns the failure detail string otherwise — the shape
    `verify` folds directly into a finding.
    """
    block = extract_frontmatter(text)
    if block is None:
        return None
    try:
        document = parse_frontmatter(block)
        validate_artifact("frontmatter", document)
    except (FrontmatterError, ArtifactError) as exc:
        return str(exc)
    return None
