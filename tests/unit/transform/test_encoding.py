"""FR-007 codec half: strict decode (BOM-aware, EC-007/EC-010) and UTF-8-no-BOM encode (D-002).

Pure (NFR-005): bytes/str in memory only.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from docmend.transform.encoding import decode_source, encode_utf8


class TestDecodeSource:
    def test_plain_utf8__decodes(self) -> None:
        assert decode_source("héllo".encode(), bom=None, encoding_name="utf-8") == "héllo"

    def test_utf8_bom__stripped(self) -> None:
        # EC-007: BOM decoded correctly and never reaches the text.
        data = b"\xef\xbb\xbfabc"
        assert decode_source(data, bom="utf-8", encoding_name="utf-8") == "abc"

    def test_utf16_le_bom__decodes(self) -> None:
        # EC-010: BOM'd UTF-16 decodes per its BOM (OQ-026).
        data = b"\xff\xfe" + "ab".encode("utf-16-le")
        assert decode_source(data, bom="utf-16-le", encoding_name="utf-16-le") == "ab"

    def test_utf32_be_bom__decodes(self) -> None:
        data = b"\x00\x00\xfe\xff" + "a".encode("utf-32-be")
        assert decode_source(data, bom="utf-32-be", encoding_name="utf-32-be") == "a"

    def test_windows_1252__decodes(self) -> None:
        assert decode_source(b"caf\xe9", bom=None, encoding_name="cp1252") == "café"

    def test_undecodable_byte__raises(self) -> None:
        # EC-003: strict decode, never replacement characters. 0x81 is undefined in cp1252.
        with pytest.raises(UnicodeDecodeError):
            decode_source(b"ok\x81", bom=None, encoding_name="cp1252")

    def test_empty_after_bom__returns_empty_string(self) -> None:
        assert decode_source(b"\xef\xbb\xbf", bom="utf-8", encoding_name="utf-8") == ""


class TestEncodeUtf8:
    def test_encode__never_emits_bom(self) -> None:
        assert not encode_utf8("abc").startswith(b"\xef\xbb\xbf")

    @given(st.text())
    def test_encode_decode__round_trips(self, text: str) -> None:
        assert decode_source(encode_utf8(text), bom=None, encoding_name="utf-8") == text
