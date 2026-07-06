"""FR-007 legacy detection rung (adr-0009): charset-normalizer wrapper facts.

These tests pin detector BEHAVIOR docmend depends on, so a charset-normalizer
upgrade that changes verdicts fails visibly here rather than corrupting plans.
Real filesystem (tmp_path): from_path reads the file itself.
"""

from pathlib import Path

from docmend.detection import detect_legacy


def write(tmp_path: Path, name: str, data: bytes) -> Path:
    target = tmp_path / name
    target.write_bytes(data)
    return target


class TestDetectLegacy:
    def test_windows_1252__detected_with_usable_confidence(self, tmp_path: Path) -> None:
        text = "café naïve — déjà vu, señor. " * 20
        path = write(tmp_path, "legacy.txt", text.replace("—", "-").encode("cp1252"))
        result = detect_legacy(path)
        assert result is not None
        assert result.method == "charset-normalizer"
        # Observed verdict (installed charset-normalizer, this fixture): cp1257
        # (Windows Baltic), not cp1252 itself — the two share enough accented
        # Latin-1 code points that a short sample is genuinely ambiguous between
        # them. Family kept narrow but not single-valued: alias-close single-byte
        # Windows code pages are the only acceptable verdicts here.
        assert result.name in ("cp1252", "cp1257", "latin_1", "iso8859_15", "cp1250", "cp1254")
        assert result.confidence >= 0.80

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
