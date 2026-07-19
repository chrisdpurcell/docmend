"""Generates the weird-document corpus (§17.2, FR-015, adr-0015/0016).

Each fixture's bytes are synthesized here (Faker-seeded prose or byte literals,
never real library content — C-002), then VERIFIED against its expectation by
scanning + planning the whole assembled corpus in a scratch directory before a
single byte is written to tests/fixtures/weird_documents/. A generated fixture
can therefore never disagree with its own sidecar at birth: a mismatch aborts
the run with nothing written (or overwritten).

Verification runs one scan per fixture subtree: the top-level corpus is
scanned as a whole (catching cross-fixture interactions like the
collision-src.txt/.md pair that per-file isolation would miss), and the
encoding_floor/ matrix self-verifies in its own scratch directory. Separate
scans are sound because the subtrees have disjoint rename-target namespaces —
floor rename targets never leave encoding_floor/.

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
from docmend.detection import detect_legacy
from docmend.discovery import scan
from docmend.plan import ArtifactRef, Plan
from docmend.planning import build_plan

CORPUS_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "weird_documents"
FLOOR_DIR = CORPUS_DIR / "encoding_floor"
RUN_ID = "run_20260706T000000Z_abc123"
GENERATED_AT = "2026-07-06T00:00:00+00:00"
SEED = 20260706

# Encoding-floor matrix (§17.2, adr-0009, RQ-022). Byte-identical across
# cp1250/cp1252/cp1257 (verified), so every codec charset-normalizer might name
# for these decodes equivalently — this isolates the non-ASCII byte COUNT as the
# single variable the floor gates on. French/Spanish diacritics deliberately do
# NOT round-trip this way; that decode-inequivalence is its own committed fixture
# (the R-001 residual of the sole-detector design).
_FLOOR_DIACRITICS = "äöüßÄÖÜé"
_FLOOR_LENGTHS = (30, 200, 2048)
_FLOOR_PLACEMENTS = ("start", "spread", "end")
_FLOOR_DEFAULT = 20  # the adr-0009 default the committed boundaries pin behavior around

type Disposition = Literal["skip", "action", "noop"]


@dataclass(frozen=True)
class Fixture:
    """One corpus file: its bytes, its sidecar's traceability fields, and the
    disposition the sidecar pins (adr-0015 recipe -> bytes, applied to plan
    outcomes rather than raw bytes).

    `subdir` places the fixture in a nested corpus directory (the encoding-floor
    matrix lives under `encoding_floor/`); `detection`/`family` are the optional
    extra sidecar keys the floor fixtures carry for the detector-level assertions
    in tests/test_encoding_floor.py (Task 12 contract) — top-level corpus
    fixtures leave them None and their sidecars stay the plain Task 11 shape.
    """

    name: str
    data: bytes
    anomaly: str
    spec_refs: list[str]
    expect: dict[str, object]
    subdir: str = ""
    detection: dict[str, object] | None = None
    family: dict[str, object] | None = None


def _sidecar(fixture: Fixture) -> dict[str, object]:
    sidecar: dict[str, object] = {
        "anomaly": fixture.anomaly,
        "spec_refs": fixture.spec_refs,
        "expect": fixture.expect,
    }
    if fixture.detection is not None:
        sidecar["detection"] = fixture.detection
    if fixture.family is not None:
        sidecar["family"] = fixture.family
    return sidecar


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


@dataclass(frozen=True)
class _FloorCell:
    """A pre-observation floor-matrix cell: synthetic bytes plus the ground-truth
    cp1252 text they were built from (needed to check decode-equivalence) and the
    role that decides which invariant the observation must satisfy."""

    name: str
    data: bytes
    truth: str
    anomaly: str
    spec_refs: list[str]
    role: Literal["boundary", "clear-skip", "clear-accept", "family", "western"]
    count: int
    family_members: tuple[str, ...] = ()


def _floor_prose(faker: Faker, total: int) -> list[str]:
    """ASCII faker prose padded to at least `total` chars with a guaranteed-dense
    run of letters, so even a 30-byte cell can host up to ~21 injected non-ASCII
    bytes (the top boundary count) at real alpha positions."""
    text = ""
    while sum(c.isalpha() for c in text) < total:
        text += faker.sentence() + " "
    return list(text[:total])


def _inject_non_ascii(faker: Faker, total: int, count: int, placement: str) -> tuple[bytes, str]:
    """Place exactly `count` byte-stable diacritics into ASCII prose of `total`
    chars, clustered at start/end or spread evenly. cp1252 encodes each diacritic
    as one high byte, so the file's non-ASCII byte count equals `count` exactly."""
    chars = _floor_prose(faker, total)
    alpha = [i for i, c in enumerate(chars) if c.isalpha() and c.isascii()]
    if len(alpha) < count:
        msg = f"floor cell total={total} count={count}: only {len(alpha)} alpha slots"
        raise AssertionError(msg)
    if placement == "start":
        positions = alpha[:count]
    elif placement == "end":
        positions = alpha[-count:]
    else:
        step = max(1, len(alpha) // count)
        positions = alpha[::step][:count]
    for k, i in enumerate(positions):
        chars[i] = _FLOOR_DIACRITICS[k % len(_FLOOR_DIACRITICS)]
    truth = "".join(chars)
    data = truth.encode("cp1252")
    non_ascii = sum(1 for b in data if b >= 0x80)
    if non_ascii != count:
        msg = f"floor cell total={total} count={count}: produced {non_ascii} non-ASCII bytes"
        raise AssertionError(msg)
    return data, truth


def _synth_floor_cells() -> list[_FloorCell]:
    """The committed boundary sets: every (length, placement) at counts 19/20/21,
    a clear-skip (8) and clear-accept (40) per length that can host them, the two
    family-equivalence pairs, and the Western family-inequivalence risk marker."""
    faker = Faker()
    faker.seed_instance(SEED)
    cells: list[_FloorCell] = []

    # Three-axis boundary sets (§17.2): length x placement x {19,20,21}. 19 sits
    # just below the floor (false-skip boundary), 20 at it, 21 just above
    # (false-accept boundary) — the exact window MS-2 calibrated (RQ-022).
    for total in _FLOOR_LENGTHS:
        for placement in _FLOOR_PLACEMENTS:
            for count in (19, 20, 21):
                data, truth = _inject_non_ascii(faker, total, count, placement)
                cells.append(
                    _FloorCell(
                        name=f"floor-len{total}-n{count}-{placement}.txt",
                        data=data,
                        truth=truth,
                        anomaly="encoding-floor-boundary",
                        spec_refs=["FR-007", "adr-0009", "OQ-015"],
                        role="boundary",
                        count=count,
                    )
                )

    # Clear-skip (8 non-ASCII) per length: unambiguously below the floor.
    for total in _FLOOR_LENGTHS:
        data, truth = _inject_non_ascii(faker, total, 8, "spread")
        cells.append(
            _FloorCell(
                name=f"floor-len{total}-n8-spread.txt",
                data=data,
                truth=truth,
                anomaly="encoding-floor-clear-skip",
                spec_refs=["FR-007", "adr-0009", "OQ-015"],
                role="clear-skip",
                count=8,
            )
        )

    # Clear-accept (40 non-ASCII) per length that can hold it (a 30-byte file
    # cannot host 40 non-ASCII bytes; its above-floor behavior is pinned by its
    # own n20/n21 cells). Spread placement keeps the detection decode-equivalent.
    for total in _FLOOR_LENGTHS:
        if total < 40:
            continue
        data, truth = _inject_non_ascii(faker, total, 40, "spread")
        cells.append(
            _FloorCell(
                name=f"floor-len{total}-n40-spread.txt",
                data=data,
                truth=truth,
                anomaly="encoding-floor-clear-accept",
                spec_refs=["FR-007", "adr-0009", "OQ-015"],
                role="clear-accept",
                count=40,
            )
        )

    # Family-equivalence pairs (§17.2): cp932/Shift_JIS share bytes for common
    # kana/kanji, GBK/GB18030 for common hanzi — whichever member the detector
    # names, the decode is identical. Synthetic CJK prose via faker locales (C-002).
    faker_ja = Faker("ja_JP")
    faker_ja.seed_instance(SEED)
    ja_truth = "".join(faker_ja.text() for _ in range(2))[:60]
    for member in ("cp932", "shift_jis"):
        data = ja_truth.encode(member)
        cells.append(
            _FloorCell(
                name=f"family-ja-{member.replace('_', '')}.txt",
                data=data,
                truth=ja_truth,
                anomaly="family-equivalent-decode",
                spec_refs=["FR-007", "adr-0009"],
                role="family",
                count=sum(1 for b in data if b >= 0x80),
                family_members=("cp932", "shift_jis"),
            )
        )
    faker_zh = Faker("zh_CN")
    faker_zh.seed_instance(SEED)
    zh_truth = "".join(faker_zh.text() for _ in range(2))[:60]
    for member in ("gbk", "gb18030"):
        data = zh_truth.encode(member)
        cells.append(
            _FloorCell(
                name=f"family-zh-{member}.txt",
                data=data,
                truth=zh_truth,
                anomaly="family-equivalent-decode",
                spec_refs=["FR-007", "adr-0009"],
                role="family",
                count=sum(1 for b in data if b >= 0x80),
                family_members=("gbk", "gb18030"),
            )
        )

    # Western family-inequivalence (R-001 residual): cp1252 French/Spanish
    # diacritics get a CONFIDENT verdict whose decode differs from cp1252 (a real
    # false-accept the floor cannot catch — the sole-detector design's known
    # residual, deferred behind the OQ-020 family-aware seam). Pinned as an
    # observed risk marker, not a correctness pass.
    faker_fr = Faker("fr_FR")
    faker_fr.seed_instance(SEED)
    fr_body = "".join(faker_fr.text() for _ in range(3))
    fr_truth = (
        "Café à la crème: naïve garçon, être où ne pas être. "
        + fr_body.replace("a", "à").replace("e", "ê")
    )[:250]
    cells.append(
        _FloorCell(
            name="western-cp1252-inequivalent.txt",
            data=fr_truth.encode("cp1252"),
            truth=fr_truth,
            anomaly="western-family-inequivalence",
            spec_refs=["FR-007", "adr-0009", "R-001", "OQ-020"],
            role="western",
            count=sum(1 for b in fr_truth.encode("cp1252") if b >= 0x80),
        )
    )
    return cells


def _plan_scratch(root: Path) -> Plan:
    config = DocmendConfig()
    inventory = scan(root, config, run_id=RUN_ID, generated_at=GENERATED_AT)
    ref = ArtifactRef(path="unused.json", run_id=RUN_ID, sha256="sha256:" + "0" * 64)
    return build_plan(
        inventory, config, run_id=RUN_ID, generated_at=GENERATED_AT, inventory_ref=ref
    )


def _floor_fixtures() -> list[Fixture]:
    """Synthesize the floor matrix, then OBSERVE each cell's real plan disposition
    and detector verdict in a scratch dir before writing. Unlike the top-level
    corpus (recipe -> intended disposition, verified), the floor sidecars record
    observed values — but the observation still enforces the invariants that make
    the matrix meaningful, aborting the run if the floor logic ever regressed:
      * every sub-floor cell (count < 20) skips — the floor's lower-bound guarantee;
      * every clear-accept and family cell plans as an action;
      * family cells decode identically under every listed member and the detected
        name; the Western cell is a confident verdict whose decode differs.
    """
    cells = _synth_floor_cells()
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        for cell in cells:
            (root / cell.name).write_bytes(cell.data)
        plan = _plan_scratch(root)
        actions = {a.path: a for a in plan.actions}
        skips = {s.path: s for s in plan.skips}

        fixtures: list[Fixture] = []
        for cell in cells:
            detected = detect_legacy(root / cell.name)
            candidate = detected is not None
            confident = candidate and detected.confidence >= 0.80

            if cell.count < _FLOOR_DEFAULT:
                assert cell.name in skips, (
                    f"{cell.name}: sub-floor cell (count {cell.count}) must skip, "
                    f"got {'action' if cell.name in actions else 'noop'}"
                )
            if cell.role in ("clear-accept", "family"):
                assert cell.name in actions, (
                    f"{cell.name}: {cell.role} cell must plan an action, got "
                    f"{'skip: ' + skips[cell.name].reason if cell.name in skips else 'noop'}"
                )

            if cell.name in skips:
                expect: dict[str, object] = {
                    "disposition": "skip",
                    "reason": skips[cell.name].reason,
                }
            elif cell.name in actions:
                action = actions[cell.name]
                expect = {
                    "disposition": "action",
                    "operations": list(action.operations),
                    "target_path": action.target_path,
                }
            else:
                expect = {"disposition": "noop"}

            detection: dict[str, object] | None = None
            family: dict[str, object] | None = None
            if cell.role == "family":
                assert detected is not None
                for member in cell.family_members:
                    assert cell.data.decode(member) == cell.truth, (
                        f"{cell.name}: {member} decode diverges from source text"
                    )
                assert cell.data.decode(detected.name) == cell.truth, (
                    f"{cell.name}: detected {detected.name} decode diverges from source text"
                )
                family = {"expected_text": cell.truth, "members": list(cell.family_members)}
            elif cell.role == "western":
                assert detected is not None and confident, (
                    f"{cell.name}: Western residual must be a confident verdict"
                )
                assert cell.data.decode(detected.name) != cell.truth, (
                    f"{cell.name}: expected decode-inequivalence, but decode matched source"
                )
                detection = {
                    "candidate": True,
                    "confident": True,
                    "decode_matches_source": False,
                }
            else:
                detection = {"candidate": candidate, "confident": confident}

            fixtures.append(
                Fixture(
                    name=cell.name,
                    data=cell.data,
                    anomaly=cell.anomaly,
                    spec_refs=cell.spec_refs,
                    expect=expect,
                    subdir="encoding_floor",
                    detection=detection,
                    family=family,
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


def _write_fixtures(fixtures: list[Fixture]) -> None:
    for fixture in fixtures:
        target_dir = CORPUS_DIR / fixture.subdir if fixture.subdir else CORPUS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / fixture.name).write_bytes(fixture.data)
        sidecar_path = target_dir / f"{fixture.name}.expect.json"
        sidecar_path.write_text(json.dumps(_sidecar(fixture), indent=2) + "\n", encoding="utf-8")
        label = f"{fixture.subdir}/{fixture.name}" if fixture.subdir else fixture.name
        print(f"wrote {label} ({len(fixture.data)} bytes) + sidecar")


def _prune_orphans(fixtures: list[Fixture]) -> None:
    # The committed corpus must stay one-to-one with the recipe:
    # tests/test_weird_corpus.py enumerates committed sidecars, so a fixture
    # renamed or removed here would otherwise keep being asserted against with
    # no generator able to reproduce it. Deletion is confined to the fixture
    # subtrees this generator owns.
    expected: dict[Path, set[str]] = {CORPUS_DIR: set(), FLOOR_DIR: set()}
    for fixture in fixtures:
        target_dir = CORPUS_DIR / fixture.subdir if fixture.subdir else CORPUS_DIR
        expected.setdefault(target_dir, set()).update({fixture.name, f"{fixture.name}.expect.json"})
    for directory, names in expected.items():
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            if entry.is_dir() or entry.name in names:
                continue
            entry.unlink()
            print(f"pruned orphan {entry.relative_to(CORPUS_DIR)}")


def main() -> None:
    fixtures = build_fixtures()
    _verify(fixtures)
    floor_fixtures = _floor_fixtures()  # observes + self-verifies the floor matrix
    _write_fixtures(fixtures)
    _write_fixtures(floor_fixtures)
    _prune_orphans(fixtures + floor_fixtures)


if __name__ == "__main__":
    main()
