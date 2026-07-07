"""FR-009 whitespace transforms (OQ-031 tab semantics, EC-009 final newline). Pure (NFR-005)."""

from hypothesis import given
from hypothesis import strategies as st

from docmend.transform.whitespace import (
    collapse_blank_lines,
    ensure_final_newline,
    normalize_tabs,
    trim_trailing,
)

# LF-normalized text (the documented precondition).
lf_text = st.text(alphabet=st.characters(exclude_characters="\r")).map(
    lambda s: s.replace("\r", "")
)


def non_ws(s: str) -> str:
    return "".join(s.split())


class TestTrimTrailing:
    def test_spaces_and_tabs__trimmed(self) -> None:
        assert trim_trailing("a  \nb\t\nc") == "a\nb\nc"

    def test_leading_whitespace__untouched(self) -> None:
        assert trim_trailing("  a\n\tb\n") == "  a\n\tb\n"

    def test_whitespace_only_line__becomes_empty(self) -> None:
        assert trim_trailing("a\n   \nb") == "a\n\nb"

    @given(lf_text)
    def test_trim__idempotent(self, text: str) -> None:
        once = trim_trailing(text)
        assert trim_trailing(once) == once

    @given(lf_text)
    def test_trim__non_whitespace_preserved(self, text: str) -> None:
        assert non_ws(trim_trailing(text)) == non_ws(text)

    @given(lf_text)
    def test_trim__no_line_ends_with_space_or_tab(self, text: str) -> None:
        assert all(not line.endswith((" ", "\t")) for line in trim_trailing(text).split("\n"))


class TestEnsureFinalNewline:
    def test_missing_final_newline__added(self) -> None:
        assert ensure_final_newline("a") == "a\n"

    def test_multiple_final_newlines__reduced_to_one(self) -> None:
        assert ensure_final_newline("a\n\n\n") == "a\n"

    def test_exactly_one__unchanged(self) -> None:
        assert ensure_final_newline("a\n") == "a\n"

    def test_empty__gains_newline(self) -> None:
        # EC-009: a zero-byte file receives final-newline enforcement mechanically.
        assert ensure_final_newline("") == "\n"

    @given(lf_text)
    def test_final_newline__always_exactly_one(self, text: str) -> None:
        result = ensure_final_newline(text)
        assert result.endswith("\n") and not result.endswith("\n\n")

    @given(lf_text)
    def test_final_newline__idempotent(self, text: str) -> None:
        once = ensure_final_newline(text)
        assert ensure_final_newline(once) == once


class TestCollapseBlankLines:
    def test_run_beyond_max__collapsed(self) -> None:
        assert collapse_blank_lines("a\n\n\n\n\nb", 2) == "a\n\n\nb"
        # 5 newlines = 4 blank lines between a and b -> keep 2.

    def test_run_at_max__unchanged(self) -> None:
        assert collapse_blank_lines("a\n\n\nb", 2) == "a\n\n\nb"

    def test_whitespace_only_lines__count_as_blank(self) -> None:
        # First `max` lines of the run survive VERBATIM (whitespace kept);
        # trim_trailing owns cleaning them, not this transform.
        assert collapse_blank_lines("a\n \n\t\n \nb", 1) == "a\n \nb"

    def test_zero_max__removes_all_blank_lines(self) -> None:
        assert collapse_blank_lines("a\n\n\nb", 0) == "a\nb"

    def test_empty_text__unchanged(self) -> None:
        # EC-009 guard: split("\n") on "" yields [""], which the trailing-newline
        # peel would otherwise turn into a spurious "\n".
        assert collapse_blank_lines("", 3) == ""

    def test_all_blank_with_trailing_newline__zero_max_empties(self) -> None:
        # Regression (Hypothesis counterexample, 2026-07-07): an all-blank input
        # with a trailing newline under max 0 must collapse to "", not a phantom
        # "\n". The trailing-newline peel/reattach must not resurrect a dropped run.
        assert collapse_blank_lines("\n", 0) == ""
        assert collapse_blank_lines("\n\n", 0) == ""
        assert collapse_blank_lines("\t\n", 0) == ""

    def test_leading_and_trailing_runs__collapsed(self) -> None:
        assert collapse_blank_lines("\n\n\na\n\n\n", 1) == "\na\n\n"
        # leading: 3 blank lines -> 1; trailing: text ends with newline, so the
        # trailing run is 2 blank lines -> 1 (final line "" is not a line).

    @given(lf_text, st.integers(min_value=0, max_value=5))
    def test_collapse__idempotent(self, text: str, max_blank: int) -> None:
        once = collapse_blank_lines(text, max_blank)
        assert collapse_blank_lines(once, max_blank) == once

    @given(lf_text, st.integers(min_value=0, max_value=5))
    def test_collapse__non_whitespace_preserved(self, text: str, max_blank: int) -> None:
        assert non_ws(collapse_blank_lines(text, max_blank)) == non_ws(text)

    @given(lf_text, st.integers(min_value=0, max_value=5))
    def test_collapse__no_run_exceeds_max(self, text: str, max_blank: int) -> None:
        lines = collapse_blank_lines(text, max_blank).split("\n")
        run = 0
        for line in lines[:-1] if lines and lines[-1] == "" else lines:
            run = run + 1 if line.strip(" \t") == "" else 0
            assert run <= max_blank


class TestNormalizeTabs:
    def test_leading_tabs__converted(self) -> None:
        assert normalize_tabs("\tx\n\t\ty", 4) == "    x\n        y"

    def test_interior_tabs__untouched(self) -> None:
        # adr-0016: column-aligned tables/ASCII art are content.
        assert normalize_tabs("a\tb\tc", 4) == "a\tb\tc"

    def test_tabs_in_mixed_leading_whitespace__converted(self) -> None:
        assert normalize_tabs(" \t x", 2) == "    x"
        # leading prefix " \t " -> space + 2 spaces + space.

    def test_tab_width__respected(self) -> None:
        assert normalize_tabs("\tx", 8) == "        x"

    @given(lf_text, st.integers(min_value=1, max_value=8))
    def test_tabs__idempotent(self, text: str, width: int) -> None:
        once = normalize_tabs(text, width)
        assert normalize_tabs(once, width) == once

    @given(lf_text, st.integers(min_value=1, max_value=8))
    def test_tabs__non_whitespace_preserved(self, text: str, width: int) -> None:
        assert non_ws(normalize_tabs(text, width)) == non_ws(text)

    @given(lf_text, st.integers(min_value=1, max_value=8))
    def test_tabs__no_leading_tabs_remain(self, text: str, width: int) -> None:
        for line in normalize_tabs(text, width).split("\n"):
            prefix_end = len(line) - len(line.lstrip(" \t"))
            assert "\t" not in line[:prefix_end]
