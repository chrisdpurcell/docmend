"""Encoding decode/encode (FR-007 codec half; D-002 UTF-8-no-BOM output).

Pure (NFR-005): bytes in, str out. Decoding is STRICT by contract — a byte the
declared encoding cannot represent raises UnicodeDecodeError, and the planning
layer maps that to the `decode-replacement` skip (EC-003); replacement
characters are silent corruption and never an output of this module.

The caller supplies the BOM kind the discovery layer sniffed (inventory
`encoding.bom`); the BOM bytes are stripped here so they can never leak into
text (EC-007), and `encode_utf8` never writes one (D-002).
"""

_BOM_LENGTH = {"utf-8": 3, "utf-16-le": 2, "utf-16-be": 2, "utf-32-le": 4, "utf-32-be": 4}


def decode_source(data: bytes, *, bom: str | None, encoding_name: str) -> str:
    if bom is not None:
        data = data[_BOM_LENGTH[bom] :]
    return data.decode(encoding_name, errors="strict")


def encode_utf8(text: str) -> bytes:
    return text.encode("utf-8")
