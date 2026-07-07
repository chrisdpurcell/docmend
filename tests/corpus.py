"""Shared synthetic-corpus generator (adr-0015: pure recipe -> bytes; disk adapter isolated).

Promoted out of tests/test_discovery.py at MS-2 (the promotion its docstring
promised) so planning tests and the weird-document fixture generator share one
provably synthetic (faker-seeded, C-002) source. `render` is the pure half;
`materialize` is the only place generator output touches the filesystem.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from faker import Faker

from docmend.inventory import NewlineStyle

RUN_ID = "run_20260706T000000Z_abc123"
GENERATED_AT = datetime(2026, 7, 6, tzinfo=UTC).isoformat()

type RecipeEncoding = Literal["utf-8", "utf-8-sig", "windows-1252", "utf-16-le-bom", "binaryish"]


@dataclass(frozen=True)
class FileRecipe:
    """Pure description of one synthetic corpus file (adr-0015: recipe -> bytes)."""

    path: str
    encoding: RecipeEncoding
    newline: NewlineStyle
    sentences: int = 3

    @property
    def expected_bom(self) -> str | None:
        return {"utf-8-sig": "utf-8", "utf-16-le-bom": "utf-16-le"}.get(self.encoding)

    @property
    def expected_utf8_valid(self) -> bool:
        # NUL bytes are perfectly valid UTF-8 — that is exactly why FR-015 keys
        # binary suspicion on the nul_bytes fact, not on decode failure.
        return self.encoding in ("utf-8", "utf-8-sig", "binaryish")


_EOL: dict[NewlineStyle, str] = {"lf": "\n", "crlf": "\r\n", "cr": "\r", "none": "", "mixed": ""}


def render(recipe: FileRecipe, faker: Faker) -> bytes:
    """Pure recipe -> bytes. Faker filler is provably synthetic (adr-0015, C-002)."""
    lines = [faker.sentence() for _ in range(recipe.sentences)]
    if recipe.encoding == "windows-1252":
        lines = [f"café naïve — {line}" for line in lines]
    if recipe.newline == "mixed":
        text = "".join(line + ("\n" if i % 2 else "\r\n") for i, line in enumerate(lines))
    elif recipe.newline == "none":
        text = " ".join(lines)
    else:
        eol = _EOL[recipe.newline]
        text = eol.join(lines) + eol
    match recipe.encoding:
        case "utf-8" | "utf-8-sig":
            return text.encode(recipe.encoding)
        case "windows-1252":
            return text.replace("—", "-").encode("cp1252")
        case "utf-16-le-bom":
            return b"\xff\xfe" + text.encode("utf-16-le")
        case "binaryish":
            return b"\x00\x01" + text.encode("utf-8") + b"\x00"


def materialize(root: Path, recipes: list[FileRecipe], faker: Faker) -> None:
    """Thin disk adapter — the only place generator output touches the filesystem."""
    for recipe in recipes:
        target = root / recipe.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(render(recipe, faker))


def seeded_faker() -> Faker:
    faker = Faker()
    faker.seed_instance(20260706)
    return faker


CORPUS_RECIPES = [
    FileRecipe("plain.txt", "utf-8", "lf"),
    FileRecipe("dos.txt", "utf-8", "crlf"),
    FileRecipe("mac.txt", "utf-8", "cr"),
    FileRecipe("mixed.txt", "utf-8", "mixed"),
    FileRecipe("one-line.txt", "utf-8", "none"),
    FileRecipe("bom.txt", "utf-8-sig", "lf"),
    FileRecipe("legacy.txt", "windows-1252", "crlf"),
    FileRecipe("utf16.txt", "utf-16-le-bom", "lf"),
    FileRecipe("sub/nested.txt", "utf-8", "lf"),
    FileRecipe("notes.md", "utf-8", "lf"),
    FileRecipe("page.html", "utf-8", "crlf"),
    FileRecipe("nulls.txt", "binaryish", "lf"),
]
