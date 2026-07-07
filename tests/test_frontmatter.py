"""FrontmatterCodec + frontmatter schema tests (FR-016, DR-005, adr-0011, C-006).

adr-0011 confirmation set: the schema rejects a null required mechanical field,
a missing `docmend.id`, and a duplicate key; a minimal skeleton validates;
malformed `date-time` scalars fail `format` assertions (proving the timestamp
string-preservation override is active); a no-frontmatter document is legal.
"""

import pytest

from docmend.frontmatter import (
    FrontmatterError,
    extract_frontmatter,
    parse_frontmatter,
    validate_frontmatter,
)

SHA = "sha256:" + "a" * 64

MINIMAL_SKELETON = f"""\
title: 'Untitled'
docmend:
  id: '01890000-0000-7000-8000-000000000000'
  schema_version: '1.0'
source:
  original_path: 'synthetic/example.txt'
  hash: '{SHA}'
output:
  hash: '{SHA}'
"""


def _doc(block: str) -> str:
    return f"---\n{block}---\nbody text\n"


class TestExtract:
    def test_no_frontmatter__none(self) -> None:
        assert extract_frontmatter("plain body\n") is None

    def test_block_extracted(self) -> None:
        assert extract_frontmatter(_doc("title: 'X'\n")) == "title: 'X'"

    def test_unterminated_block__none(self) -> None:
        """A lone leading --- with no closer is body text, not frontmatter."""
        assert extract_frontmatter("---\ntitle: 'X'\nno closer\n") is None

    def test_dots_closer_accepted(self) -> None:
        assert extract_frontmatter("---\ntitle: 'X'\n...\nbody\n") == "title: 'X'"


class TestParse:
    def test_duplicate_key__rejected_at_parse(self) -> None:
        """C-006: duplicates must fail BEFORE schema validation — a permissive
        parser would silently collapse them and the schema never sees it."""
        with pytest.raises(FrontmatterError, match="duplicate"):
            parse_frontmatter("title: 'A'\ntitle: 'B'\n")

    def test_non_mapping__rejected(self) -> None:
        with pytest.raises(FrontmatterError, match="mapping"):
            parse_frontmatter("- just\n- a list\n")

    def test_timestamp_scalars_stay_strings(self) -> None:
        """adr-0011 rule 4: the YAML timestamp constructor is overridden so
        date scalars reach the JSON-Schema validator as strings."""
        document = parse_frontmatter("date: 2003-01-01\n")
        assert document["date"] == "2003-01-01"
        assert isinstance(document["date"], str)


class TestValidate:
    def test_no_frontmatter__legal(self) -> None:
        assert validate_frontmatter("plain body\n") is None

    def test_minimal_skeleton__valid(self) -> None:
        assert validate_frontmatter(_doc(MINIMAL_SKELETON)) is None

    def test_missing_docmend_id__invalid(self) -> None:
        block = MINIMAL_SKELETON.replace("  id: '01890000-0000-7000-8000-000000000000'\n", "")
        detail = validate_frontmatter(_doc(block))
        assert detail is not None and "id" in detail

    def test_null_required_mechanical_field__invalid(self) -> None:
        """RQ-014 rule 1: required mechanical fields are non-null, always."""
        block = MINIMAL_SKELETON.replace(f"  hash: '{SHA}'", "  hash: null", 1)
        detail = validate_frontmatter(_doc(block))
        assert detail is not None and "hash" in detail

    def test_null_optional_field__invalid_omit_instead(self) -> None:
        """RQ-014 rule 3: optional fields are omitted, never null."""
        detail = validate_frontmatter(_doc(MINIMAL_SKELETON + "subject: null\n"))
        assert detail is not None and "subject" in detail

    def test_malformed_generated_at__format_assertion_fires(self) -> None:
        """adr-0011 rule 4 confirmation: a malformed date-time FAILS, which is
        only possible because the scalar reached the validator as a string."""
        block = MINIMAL_SKELETON.replace(
            "  schema_version: '1.0'\n",
            "  schema_version: '1.0'\n  generated_at: 'not-a-timestamp'\n",
        )
        detail = validate_frontmatter(_doc(block))
        assert detail is not None and "generated_at" in detail

    def test_wellformed_generated_at__valid(self) -> None:
        block = MINIMAL_SKELETON.replace(
            "  schema_version: '1.0'\n",
            "  schema_version: '1.0'\n  generated_at: '2026-07-07T00:00:00+00:00'\n",
        )
        assert validate_frontmatter(_doc(block)) is None

    def test_unknown_field__rejected(self) -> None:
        """adr-0005 strictness: additionalProperties:false everywhere."""
        detail = validate_frontmatter(_doc(MINIMAL_SKELETON + "invented: 'x'\n"))
        assert detail is not None

    def test_duplicate_key__reported_as_detail(self) -> None:
        detail = validate_frontmatter(_doc("title: 'A'\ntitle: 'B'\n" + MINIMAL_SKELETON))
        assert detail is not None and "duplicate" in detail

    def test_optional_fields_present__valid(self) -> None:
        block = MINIMAL_SKELETON + (
            "author:\n  - 'A. Writer'\ndate: '2003'\nlang: 'en'\ntags:\n  - 'archive'\n"
            "genre: 'memoir'\nrating: 'unrated'\n"
        )
        assert validate_frontmatter(_doc(block)) is None
