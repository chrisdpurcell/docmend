"""FR-007 non-ASCII floor boundary sets (adr-0009; RQ-022 calibration evidence).

The committed matrix under fixtures/weird_documents/encoding_floor/ pins the
floor's behavior at its boundaries: counts 19/20/21 across three lengths and
three placements, plus a clear-skip (8) and clear-accept (40) per length, the
two family-equivalence pairs (cp932/Shift_JIS, GBK/GB18030), and the Western
family-inequivalence residual. Files at count >= 20 with a confident detection
are planned; files below skip `below-non-ascii-floor` (unless an earlier gate
fires first — each sidecar records the observed reason). Family-equivalent
fixtures must DECODE identically whichever family member the detector names.

Harness split (Task 12 decision): tests/test_weird_corpus.py globs
`weird_documents/*.expect.json` NON-recursively, so it does NOT reach this
subdirectory — its `scan()` recurses and plans these files, but its parametrized
assertions never see them. This module therefore owns BOTH the disposition
assertions for the floor subtree (its own scoped plan, below) and the
detector-level assertions the Task 11 harness cannot express.
"""

import json
from pathlib import Path
from typing import cast

import pytest

from docmend.config import DocmendConfig
from docmend.detection import detect_legacy
from docmend.discovery import scan
from docmend.plan import ArtifactRef, Plan
from docmend.planning import build_plan
from docmend.transform.encoding import decode_source

FLOOR_DIR = Path(__file__).parent / "fixtures" / "weird_documents" / "encoding_floor"
RUN_ID = "run_20260706T000000Z_abc123"
GENERATED_AT = "2026-07-06T00:00:00+00:00"


def floor_cases() -> list[tuple[str, dict[str, object]]]:
    sidecars = sorted(FLOOR_DIR.glob("*.expect.json"))
    assert sidecars, "floor matrix must exist (§17.2, RQ-022)"
    return [(s.name.removesuffix(".expect.json"), json.loads(s.read_text())) for s in sidecars]


@pytest.fixture(scope="module")
def floor_plan() -> Plan:
    config = DocmendConfig()
    inventory = scan(FLOOR_DIR, config, run_id=RUN_ID, generated_at=GENERATED_AT)
    ref = ArtifactRef(path="unused.json", run_id=RUN_ID, sha256="sha256:" + "0" * 64)
    return build_plan(
        inventory, config, run_id=RUN_ID, generated_at=GENERATED_AT, inventory_ref=ref
    )


@pytest.mark.parametrize(("name", "case"), floor_cases())
def test_floor_document__planned_as_expected(
    name: str, case: dict[str, object], floor_plan: Plan
) -> None:
    """FR-015/FR-007: the floor's plan disposition holds at every committed cell.

    The load-bearing invariant is that every count < 20 cell skips: the floor
    never lets a sub-floor legacy guess through (the false-skip side), while
    count >= 20 cells with a confident, strict-decodable verdict are planned
    (the false-accept side the family-aware seam still owns — adr-0009).
    """
    expect = cast(dict[str, object], case["expect"])
    actions = {a.path: a for a in floor_plan.actions}
    skips = {s.path: s for s in floor_plan.skips}
    match expect["disposition"]:
        case "skip":
            assert name in skips, (
                f"{name}: expected skip, got {'action' if name in actions else 'noop'}"
            )
            assert skips[name].reason == expect["reason"]
        case "action":
            assert name in actions, (
                f"{name}: expected action, got "
                f"{'skip: ' + skips[name].reason if name in skips else 'noop'}"
            )
            assert actions[name].operations == expect["operations"]
            assert actions[name].target_path == expect.get("target_path")
        case other:
            pytest.fail(f"unknown disposition {other!r} in {name}.expect.json")


@pytest.mark.parametrize(("name", "case"), [c for c in floor_cases() if "family" in c[1]])
def test_family_equivalents__decode_identically(name: str, case: dict[str, object]) -> None:
    """§17.2 family-equivalent decode outcomes: whichever member the detector
    names, and every listed member, decode to the same text (the Task 6 pattern)."""
    data = (FLOOR_DIR / name).read_bytes()
    family = cast(dict[str, object], case["family"])
    expected_text = family["expected_text"]
    detected = detect_legacy(FLOOR_DIR / name)
    assert detected is not None, f"{name}: family fixture must be detectable"
    decoded = decode_source(data, bom=None, encoding_name=detected.name)
    assert decoded == expected_text
    for member in cast(list[str], family["members"]):
        assert decode_source(data, bom=None, encoding_name=member) == expected_text


@pytest.mark.parametrize(("name", "case"), [c for c in floor_cases() if "detection" in c[1]])
def test_boundary_detection_facts__pinned(name: str, case: dict[str, object]) -> None:
    """Pin the observed detector verdict (candidate / confident) at each cell —
    the bimodal signal (confident match or no candidate) that makes the FLOOR,
    not the confidence threshold, the operative gate for short files (adr-0009)."""
    detected = detect_legacy(FLOOR_DIR / name)
    expected = cast(dict[str, object], case["detection"])
    if expected["candidate"]:
        assert detected is not None
        assert (detected.confidence >= 0.80) == expected["confident"]
    else:
        assert detected is None


def test_western_residual__decode_diverges() -> None:
    """R-001 residual (empirical, Task 6/9): cp1252 French/Spanish diacritics get
    a CONFIDENT verdict whose decode differs from the source — a false-accept the
    floor cannot catch, deferred behind the OQ-020 family-aware seam. Pinned as an
    observed risk marker, not a correctness claim."""
    name = "western-cp1252-inequivalent.txt"
    data = (FLOOR_DIR / name).read_bytes()
    detected = detect_legacy(FLOOR_DIR / name)
    assert detected is not None and detected.confidence >= 0.80
    assert decode_source(data, bom=None, encoding_name=detected.name) != data.decode("cp1252")
