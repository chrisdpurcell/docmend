"""Generates the weird-document corpus (§17.2, FR-015, adr-0015/0016).

Each fixture's bytes are synthesized here (Faker-seeded prose or byte literals,
never real library content — C-002), then VERIFIED against its expectation by
scanning + planning the whole assembled corpus in a scratch directory before a
single byte is written to tests/fixtures/weird_documents/. A generated fixture
can therefore never disagree with its own sidecar at birth: a mismatch aborts
the run with nothing written (or overwritten).

The verification scans the *entire* candidate corpus at once, matching exactly
what tests/test_weird_corpus.py does against the committed directory — this is
what catches cross-fixture interactions (e.g. the collision-src.txt/.md pair)
that per-file isolation would miss.

Re-run freely: every byte here is deterministic (fixed Faker seed, fixed
Random seed), so a re-run reproduces identical fixture bytes and sidecars.
"""

import json
import random
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from faker import Faker

from docmend.config import DocmendConfig
from docmend.discovery import scan
from docmend.plan import ArtifactRef
from docmend.planning import build_plan

CORPUS_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "weird_documents"
RUN_ID = "run_20260706T000000Z_abc123"
GENERATED_AT = "2026-07-06T00:00:00+00:00"
SEED = 20260706

type Disposition = Literal["skip", "action", "noop"]


@dataclass(frozen=True)
class Fixture:
    """One corpus file: its bytes, its sidecar's traceability fields, and the
    disposition the sidecar pins (adr-0015 recipe -> bytes, applied to plan
    outcomes rather than raw bytes)."""

    name: str
    data: bytes
    anomaly: str
    spec_refs: list[str]
    expect: dict[str, object]


def _sidecar(fixture: Fixture) -> dict[str, object]:
    return {"anomaly": fixture.anomaly, "spec_refs": fixture.spec_refs, "expect": fixture.expect}


def build_fixtures() -> list[Fixture]:
    faker = Faker()
    faker.seed_instance(SEED)
    rng = random.Random(SEED)
    fixtures: list[Fixture] = []

    # scattered-nuls.txt: prose with 3 isolated NULs, otherwise valid UTF-8
    # (EC-004) — the corpus "binaryish" pattern proves NUL-bearing UTF-8 still
    # skips via the content pass's byte-accurate nul-bytes check.
    prose = bytearray(" ".join(faker.sentence() for _ in range(4)).encode("utf-8"))
    for pos in sorted([5, len(prose) // 2, len(prose) - 3], reverse=True):
        prose.insert(pos, 0)
    fixtures.append(
        Fixture(
            name="scattered-nuls.txt",
            data=bytes(prose),
            anomaly="nul-bytes",
            spec_refs=["EC-004", "FR-015"],
            expect={"disposition": "skip", "reason": "nul-bytes"},
        )
    )

    # utf16-bomless.txt: ASCII prose encoded utf-16-le with no BOM — the
    # ~50%-NUL, single-parity byte pattern EC-010's heuristic is tuned to.
    prose_text = " ".join(faker.sentence() for _ in range(4))
    fixtures.append(
        Fixture(
            name="utf16-bomless.txt",
            data=prose_text.encode("utf-16-le"),
            anomaly="utf16-suspect-bomless",
            spec_refs=["EC-010", "FR-015"],
            expect={"disposition": "skip", "reason": "utf16-suspect"},
        )
    )

    # utf16-le-bom.txt: BOM'd utf-16-le, CRLF — a BOM authoritatively claims
    # the encoding (OQ-026), so this decodes and plans as a normal action.
    lines = [faker.sentence() for _ in range(3)]
    text = "\r\n".join(lines) + "\r\n"
    fixtures.append(
        Fixture(
            name="utf16-le-bom.txt",
            data=b"\xff\xfe" + text.encode("utf-16-le"),
            anomaly="utf16-bom-crlf",
            spec_refs=["EC-010", "OQ-026"],
            expect={
                "disposition": "action",
                "operations": ["reencode", "normalize_newlines", "rename"],
                "target_path": "utf16-le-bom.md",
            },
        )
    )

    # utf8-bom.txt: UTF-8 BOM + already-clean LF prose (EC-007) — the BOM
    # alone forces reencode (to strip it); newlines need no touch.
    lines = [faker.sentence() for _ in range(3)]
    text = "\n".join(lines) + "\n"
    fixtures.append(
        Fixture(
            name="utf8-bom.txt",
            data=text.encode("utf-8-sig"),
            anomaly="utf8-bom",
            spec_refs=["EC-007"],
            expect={
                "disposition": "action",
                "operations": ["reencode", "rename"],
                "target_path": "utf8-bom.md",
            },
        )
    )

    # binary-suspect.txt: dense 0x80-0xFF soup, no NULs — verified below that
    # charset-normalizer returns no candidate at all (EC-002).
    fixtures.append(
        Fixture(
            name="binary-suspect.txt",
            data=bytes(rng.choice(range(0x80, 0x100)) for _ in range(400)),
            anomaly="binary-suspect",
            spec_refs=["EC-002", "FR-015"],
            expect={"disposition": "skip", "reason": "binary-suspect"},
        )
    )

    # below-floor.txt: only 2 non-ASCII bytes in short ASCII prose — below the
    # default 20-byte floor (FR-007/adr-0009) regardless of detector verdict.
    fixtures.append(
        Fixture(
            name="below-floor.txt",
            data=b"mostly ascii text here.... \xe9\xe8",
            anomaly="below-non-ascii-floor",
            spec_refs=["FR-007", "adr-0009"],
            expect={"disposition": "skip", "reason": "below-non-ascii-floor"},
        )
    )

    # decode-replacement.txt: BOM-truncation construction (Task 9 finding —
    # decode-replacement is otherwise unreachable via legacy detection, since
    # charset-normalizer only returns candidates that strictly decode the
    # whole file). A BOM claims utf-16-le, but the trailing odd byte makes the
    # strict BOM-codec decode fail (EC-003).
    fixtures.append(
        Fixture(
            name="decode-replacement.txt",
            data=b"\xff\xfe" + "twenty utf-16-le chars".encode("utf-16-le") + b"\x41",
            anomaly="bom-codec-decode-failure",
            spec_refs=["EC-003"],
            expect={"disposition": "skip", "reason": "decode-replacement"},
        )
    )

    # legacy-cp1252.txt: German umlaut/eszett prose, CRLF, trailing spaces.
    # Task 9/10 finding: cp1252 diacritic prose gets confidently misdetected
    # as a decode-equivalent codec (observed: cp1250) rather than cp1252
    # itself — the expectation is pinned on the PLAN outcome (the operations
    # list), never on the detected codec name, which is incidental.
    german_words = [
        "Straße",
        "Mädchen",
        "Übermütig",
        "schön",
        "Größe",
        "Fußball",
        "Käse",
        "Blüte",
        "Rätsel",
        "Öl",
    ]
    lines = [
        f"Das ist ein {german_words[i % len(german_words)]} Test mit ä ö ü ß Zeichen.   "
        for i in range(6)
    ]
    text = "\r\n".join(lines) + "\r\n"
    fixtures.append(
        Fixture(
            name="legacy-cp1252.txt",
            data=text.encode("cp1252"),
            anomaly="legacy-encoding-decode-equivalent",
            spec_refs=["FR-007", "FR-015"],
            expect={
                "disposition": "action",
                "operations": [
                    "reencode",
                    "normalize_newlines",
                    "trim_trailing_whitespace",
                    "rename",
                ],
                "target_path": "legacy-cp1252.md",
            },
        )
    )

    # mixed-endings.txt: UTF-8, LF + CRLF + CR interleaved (EC-006).
    lines = [faker.sentence() for _ in range(6)]
    text = (
        lines[0]
        + "\n"
        + lines[1]
        + "\r\n"
        + lines[2]
        + "\r"
        + lines[3]
        + "\n"
        + lines[4]
        + "\r\n"
        + lines[5]
        + "\n"
    )
    fixtures.append(
        Fixture(
            name="mixed-endings.txt",
            data=text.encode("utf-8"),
            anomaly="mixed-newlines",
            spec_refs=["EC-006"],
            expect={
                "disposition": "action",
                "operations": ["normalize_newlines", "rename"],
                "target_path": "mixed-endings.md",
            },
        )
    )

    # padded-legacy.txt: UTF-8, 200 blank lines between two words — proves
    # collapse_blank_lines fires without tripping the EC-005 shrink-invariant
    # guard (adr-0016: whitespace-only removal never counts as shrinkage).
    fixtures.append(
        Fixture(
            name="padded-legacy.txt",
            data=("alpha" + "\n" * 201 + "beta\n").encode("utf-8"),
            anomaly="excess-blank-lines",
            spec_refs=["FR-009", "adr-0016"],
            expect={
                "disposition": "action",
                "operations": ["collapse_blank_lines", "rename"],
                "target_path": "padded-legacy.md",
            },
        )
    )

    # zero-byte.txt: empty file (EC-009) — vacuously UTF-8-valid; needs only a
    # final newline plus the standard .txt -> .md rename.
    fixtures.append(
        Fixture(
            name="zero-byte.txt",
            data=b"",
            anomaly="empty-file",
            spec_refs=["EC-009"],
            expect={
                "disposition": "action",
                "operations": ["ensure_final_newline", "rename"],
                "target_path": "zero-byte.md",
            },
        )
    )

    # clean-noop.md: already-normalized — proves the plan's third state (FR-017):
    # a file needing nothing appears in neither actions nor skips. Markdown,
    # not .txt, because .txt always renames (see tabs-leading.md below).
    lines = [faker.sentence() for _ in range(3)]
    text = "\n".join(lines) + "\n"
    fixtures.append(
        Fixture(
            name="clean-noop.md",
            data=text.encode("utf-8"),
            anomaly="already-clean",
            spec_refs=["FR-017"],
            expect={"disposition": "noop"},
        )
    )

    # markup-crlf.html: CRLF + trailing whitespace + blank-line runs — markup
    # files receive encoding/EOL normalization only (adr-0016), never rename
    # (OQ-025), and never the whitespace quartet.
    html_lines = [
        "<html>",
        "<body>",
        faker.sentence() + "   ",
        "",
        "",
        "",
        faker.sentence(),
        "</body>",
        "</html>",
    ]
    text = "\r\n".join(html_lines) + "\r\n"
    fixtures.append(
        Fixture(
            name="markup-crlf.html",
            data=text.encode("utf-8"),
            anomaly="markup-crlf-and-blank-runs",
            spec_refs=["OQ-025", "adr-0016"],
            expect={
                "disposition": "action",
                "operations": ["normalize_newlines"],
                "target_path": None,
            },
        )
    )

    # collision-src.txt + collision-src.md: the .txt's rename target already
    # exists as a real file (EC-001) — skipped under the default "skip"
    # collision policy; the pre-existing .md is untouched (noop).
    lines = [faker.sentence() for _ in range(2)]
    fixtures.append(
        Fixture(
            name="collision-src.txt",
            data=("\n".join(lines) + "\n").encode("utf-8"),
            anomaly="rename-target-collision",
            spec_refs=["EC-001"],
            expect={"disposition": "skip", "reason": "collision"},
        )
    )
    lines = [faker.sentence() for _ in range(2)]
    fixtures.append(
        Fixture(
            name="collision-src.md",
            data=("\n".join(lines) + "\n").encode("utf-8"),
            anomaly="rename-target-collision",
            spec_refs=["EC-001"],
            expect={"disposition": "noop"},
        )
    )

    # tabs-leading.md: leading + interior tabs, otherwise clean, LF (OQ-031).
    # Named .md rather than .txt: FR-010's rename fires unconditionally for
    # any .txt file with rename.txt_to_md enabled (the default), regardless
    # of whether content changed — so a .txt file can never be a true no-op
    # under default config (see clean-noop.md above for the same reason).
    # .md isolates the fixture's actual point: with normalize_tabs off (the
    # default), tabs are left untouched and the file is a genuine no-op;
    # enabling normalize_tabs is additive (verified manually, not pinned here
    # since the harness always plans under DocmendConfig() defaults).
    tab_lines = ["\tFirst item", "\tSecond\titem here", faker.sentence()]
    fixtures.append(
        Fixture(
            name="tabs-leading.md",
            data=("\n".join(tab_lines) + "\n").encode("utf-8"),
            anomaly="leading-interior-tabs",
            spec_refs=["OQ-031"],
            expect={"disposition": "noop"},
        )
    )

    return fixtures


def _verify(fixtures: list[Fixture]) -> None:
    """Scan + plan the whole assembled corpus in a scratch dir and assert
    every fixture's sidecar expectation holds — before any real file is
    written (so a committed fixture can never disagree with its sidecar)."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        for fixture in fixtures:
            (root / fixture.name).write_bytes(fixture.data)
        config = DocmendConfig()
        inventory = scan(root, config, run_id=RUN_ID, generated_at=GENERATED_AT)
        ref = ArtifactRef(path="unused.json", run_id=RUN_ID, sha256="sha256:" + "0" * 64)
        plan = build_plan(
            inventory, config, run_id=RUN_ID, generated_at=GENERATED_AT, inventory_ref=ref
        )
        actions = {a.path: a for a in plan.actions}
        skips = {s.path: s for s in plan.skips}
        for fixture in fixtures:
            expect = fixture.expect
            disposition = expect["disposition"]
            if disposition == "skip":
                observed = skips.get(fixture.name)
                assert observed is not None, (
                    f"{fixture.name}: expected skip, got "
                    f"{'action' if fixture.name in actions else 'noop'}"
                )
                assert observed.reason == expect["reason"], (
                    f"{fixture.name}: expected reason {expect['reason']!r}, got {observed.reason!r}"
                )
            elif disposition == "action":
                observed_action = actions.get(fixture.name)
                assert observed_action is not None, (
                    f"{fixture.name}: expected action, got "
                    f"{'skip: ' + skips[fixture.name].reason if fixture.name in skips else 'noop'}"
                )
                assert observed_action.operations == expect["operations"], (
                    f"{fixture.name}: expected operations {expect['operations']!r}, "
                    f"got {observed_action.operations!r}"
                )
                assert observed_action.target_path == expect.get("target_path"), (
                    f"{fixture.name}: expected target_path {expect.get('target_path')!r}, "
                    f"got {observed_action.target_path!r}"
                )
            elif disposition == "noop":
                assert fixture.name not in actions and fixture.name not in skips, (
                    f"{fixture.name}: expected noop, got "
                    f"{'action' if fixture.name in actions else 'skip: ' + skips[fixture.name].reason}"
                )
            else:
                msg = f"{fixture.name}: unknown disposition {disposition!r}"
                raise AssertionError(msg)


def main() -> None:
    fixtures = build_fixtures()
    _verify(fixtures)
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for fixture in fixtures:
        (CORPUS_DIR / fixture.name).write_bytes(fixture.data)
        sidecar_path = CORPUS_DIR / f"{fixture.name}.expect.json"
        sidecar_path.write_text(json.dumps(_sidecar(fixture), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {fixture.name} ({len(fixture.data)} bytes) + sidecar")


if __name__ == "__main__":
    main()
