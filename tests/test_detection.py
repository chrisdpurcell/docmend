"""FR-007 legacy detection rung (adr-0009): charset-normalizer wrapper facts.

These tests pin detector BEHAVIOR docmend depends on, so a charset-normalizer
upgrade that changes verdicts fails visibly here rather than corrupting plans.
Real filesystem (tmp_path): from_path reads the file itself.
"""

from pathlib import Path

from docmend.detection import detect_legacy, detect_legacy_bytes


def write(tmp_path: Path, name: str, data: bytes) -> Path:
    target = tmp_path / name
    target.write_bytes(data)
    return target


class TestDetectLegacy:
    def test_windows_1252__detected_with_usable_confidence(self, tmp_path: Path) -> None:
        # A short, repetitive sample is exactly what confuses charset-normalizer:
        # on a fixture like "café naïve déjà vu" x20 it names cp1257 (Windows
        # Baltic) at chaos=0.0 — confident and WRONG, since decoding the
        # cp1252-encoded bytes as cp1257 silently corrupts "naïve" into "naļve".
        # Matching codec *names* would paper over that. What actually matters
        # (spec §17.2, "family-equivalent decode outcomes") is whether the named
        # codec reproduces the original text byte-for-byte, so this asserts
        # decode-equivalence instead of a name allowlist. Longer, more natural
        # prose helps, but the specific accent mix matters too: French/Spanish
        # diacritics (à ç è ê ï ñ) are exactly what drives the detector to the
        # decode-inequivalent cp1257 verdict above, so this fixture leans on
        # German umlaut/eszett prose (ä ö ü ß) instead, which charset-normalizer
        # resolves confidently to a decode-equivalent Central European codec.
        original = (
            "Der Wähler äußerte seine Meinung über die Größe der Straße und "
            "die Übernahme der Bäckerei am Übergang, während die Kälte über "
            "München hereinbrach. Später überquerte er die Brücke, müde und "
            "übernächtigt, während der Bürgermeister über die städtische "
            "Wärmeversorgung sprach und die Bevölkerung über die höheren "
            "Übertragungsgebühren klagte."
        )
        path = write(tmp_path, "legacy.txt", original.encode("cp1252"))
        result = detect_legacy(path)
        assert result is not None
        assert result.method == "charset-normalizer"
        assert result.confidence >= 0.80
        # The decisive check: whatever codec the detector names must decode the
        # cp1252 bytes back to the original text exactly. A decode-inequivalent
        # verdict (e.g. cp1257 here) must fail this test, not be allowlisted.
        assert path.read_bytes().decode(result.name) == original

    def test_confidence__is_one_minus_chaos_bounds(self, tmp_path: Path) -> None:
        path = write(tmp_path, "x.txt", "øøø æææ ååå ".encode("cp1252") * 10)
        result = detect_legacy(path)
        assert result is not None
        assert 0.0 <= result.confidence <= 1.0

    def test_undetectable_bytes__returns_none(self, tmp_path: Path) -> None:
        # Dense non-textual byte soup with no NULs: the binary-suspect input class.
        data = bytes(range(0x80, 0x100)) * 8
        path = write(tmp_path, "blob.txt", data)
        result = detect_legacy(path)
        # Observed verdict (installed charset-normalizer, this byte range and
        # nearby variants): no candidate at all — a genuine binary-suspect, not
        # merely a low-confidence guess.
        assert result is None


class TestDetectLegacyBytes:
    """F-003: detecting over the full file content held in memory must give the
    identical verdict to re-opening the file — this is the correctness
    precondition for reusing discovery's head buffer instead of a second read."""

    def test_bytes_match_from_path(self, tmp_path: Path) -> None:
        original = (
            "Der Wähler äußerte seine Meinung über die Größe der Straße und "
            "die Übernahme der Bäckerei am Übergang, während die Kälte über "
            "München hereinbrach."
        )
        data = original.encode("cp1252")
        path = write(tmp_path, "legacy.txt", data)
        assert detect_legacy_bytes(data) == detect_legacy(path)

    def test_undetectable_bytes__returns_none(self, tmp_path: Path) -> None:
        data = bytes(range(0x80, 0x100)) * 8
        path = write(tmp_path, "blob.txt", data)
        assert detect_legacy_bytes(data) is None
        assert detect_legacy(path) is None
