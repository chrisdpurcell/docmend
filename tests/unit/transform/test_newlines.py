"""FR-008: all line endings (CRLF, CR, mixed) normalize to LF. Pure (NFR-005)."""

from hypothesis import given
from hypothesis import strategies as st

from docmend.transform.newlines import normalize_newlines


class TestNormalizeNewlines:
    def test_crlf__becomes_lf(self) -> None:
        assert normalize_newlines("a\r\nb\r\n") == "a\nb\n"

    def test_bare_cr__becomes_lf(self) -> None:
        assert normalize_newlines("a\rb\r") == "a\nb\n"

    def test_mixed__becomes_lf(self) -> None:
        # EC-006: mixed styles within one file all normalize.
        assert normalize_newlines("a\r\nb\rc\nd") == "a\nb\nc\nd"

    def test_lf_only__unchanged(self) -> None:
        assert normalize_newlines("a\nb\n") == "a\nb\n"

    def test_empty__unchanged(self) -> None:
        assert normalize_newlines("") == ""


class TestNormalizeNewlinesProperties:
    @given(st.text())
    def test_output_never_contains_cr(self, text: str) -> None:
        assert "\r" not in normalize_newlines(text)

    @given(st.text())
    def test_idempotent(self, text: str) -> None:
        once = normalize_newlines(text)
        assert normalize_newlines(once) == once

    @given(st.text())
    def test_non_whitespace_preserved(self, text: str) -> None:
        # The EC-005 invariant holds by construction for this transform.

        def strip(s: str) -> str:
            return "".join(s.split())

        assert strip(normalize_newlines(text)) == strip(text)

    @given(st.text(alphabet=st.characters(exclude_characters="\x85 \x0b\x0c")))
    def test_line_count_preserved(self, text: str) -> None:
        reference = text.replace("\r\n", "\n").replace("\r", "\n")
        assert normalize_newlines(text) == reference

    def test_unicode_line_separators__untouched(self) -> None:
        assert normalize_newlines("a b\x85c") == "a b\x85c"
