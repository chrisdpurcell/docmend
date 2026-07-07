"""adr-0016 dispatch: per-file-class transform sets, canonical order, EC-005 metric. Pure."""

from typing import cast

from hypothesis import given
from hypothesis import strategies as st

from docmend.transform.dispatch import (
    FileClass,
    apply_text_transforms,
    classify_suffix,
    non_whitespace_count,
)


class TestClassifySuffix:
    def test_txt_and_md__are_text(self) -> None:
        assert classify_suffix(".txt") == "text"
        assert classify_suffix(".md") == "text"
        assert classify_suffix(".TXT") == "text"

    def test_html_and_everything_else__is_markup(self) -> None:
        # adr-0016: markup gets encoding+EOL only; unknown suffixes take the
        # same conservative minimal set.
        for suffix in (".html", ".htm", ".rst", "", ".log"):
            assert classify_suffix(suffix) == "markup"


class TestTextClassPipeline:
    def test_all_transforms__run_in_canonical_order(self) -> None:
        text = "a  \r\n\tb\n\n\n\n\nc"
        result, ops = apply_text_transforms(
            text, "text", trim_trailing_ws=True, final_newline=True, collapse_max=2, tab_width=4
        )
        assert result == "a\n    b\n\n\nc\n"
        assert ops == [
            "normalize_newlines",
            "trim_trailing_whitespace",
            "normalize_tabs",
            "collapse_blank_lines",
            "ensure_final_newline",
        ]

    def test_noop_input__yields_no_operations(self) -> None:
        # FR-017's plan half: an already-clean file produces zero operations.
        result, ops = apply_text_transforms(
            "a\nb\n",
            "text",
            trim_trailing_ws=True,
            final_newline=True,
            collapse_max=3,
            tab_width=None,
        )
        assert result == "a\nb\n"
        assert ops == []

    def test_disabled_transforms__do_not_run(self) -> None:
        result, ops = apply_text_transforms(
            "a  \n",
            "text",
            trim_trailing_ws=False,
            final_newline=False,
            collapse_max=None,
            tab_width=None,
        )
        assert result == "a  \n"
        assert ops == []


class TestMarkupClassPipeline:
    def test_markup__gets_only_newline_normalization(self) -> None:
        # adr-0016 confirmation: HTML receives exactly encoding/EOL changes.
        text = "<pre>a  \r\n\n\n\n\nb\t</pre>"
        result, ops = apply_text_transforms(
            text, "markup", trim_trailing_ws=True, final_newline=True, collapse_max=1, tab_width=4
        )
        assert result == "<pre>a  \n\n\n\n\nb\t</pre>"
        assert ops == ["normalize_newlines"]


class TestInvariantMetric:
    def test_counts__non_whitespace_only(self) -> None:
        assert non_whitespace_count(" a\tb\nc ") == 3

    def test_unicode_whitespace__ignored(self) -> None:
        assert non_whitespace_count("a\xa0b") == 2

    @given(
        st.text(alphabet=st.characters(exclude_characters="\r")),
        st.booleans(),
        st.booleans(),
        st.one_of(st.none(), st.integers(min_value=0, max_value=4)),
        st.one_of(st.none(), st.integers(min_value=1, max_value=8)),
        st.sampled_from(["text", "markup"]),
    )
    def test_pipeline__never_reduces_non_whitespace(
        self,
        text: str,
        trim: bool,
        final: bool,
        collapse: int | None,
        tabs: int | None,
        cls: str,
    ) -> None:
        # The EC-005 hard invariant holds for every configuration by construction.
        result, _ = apply_text_transforms(
            text,
            cast(FileClass, cls),
            trim_trailing_ws=trim,
            final_newline=final,
            collapse_max=collapse,
            tab_width=tabs,
        )
        assert non_whitespace_count(result) == non_whitespace_count(text)
