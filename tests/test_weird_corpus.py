"""Weird-document corpus regression harness (§17.2, FR-015, adr-0015).

Every fixture under tests/fixtures/weird_documents/ carries a sidecar
`<name>.expect.json` pinning its planned disposition. The corpus grows for the
life of the project; this harness never enumerates fixtures by name — drop a
file + sidecar in, and it is tested. Committed fixtures are byte-exact
(.gitattributes -text) and 100% synthetic (C-002, adr-0015).
"""

import json
from pathlib import Path
from typing import cast

import pytest

from docmend.config import DocmendConfig
from docmend.discovery import scan
from docmend.plan import ArtifactRef, Plan
from docmend.planning import build_plan

CORPUS_DIR = Path(__file__).parent / "fixtures" / "weird_documents"
RUN_ID = "run_20260706T000000Z_abc123"


def corpus_cases() -> list[tuple[str, dict[str, object]]]:
    sidecars = sorted(CORPUS_DIR.glob("*.expect.json"))
    assert sidecars, "weird-document corpus must never be empty (§17.2)"
    return [(s.name.removesuffix(".expect.json"), json.loads(s.read_text())) for s in sidecars]


@pytest.fixture(scope="module")
def corpus_plan() -> Plan:
    config = DocmendConfig()
    inventory = scan(CORPUS_DIR, config, run_id=RUN_ID, generated_at="2026-07-06T00:00:00+00:00")
    ref = ArtifactRef(path="unused.json", run_id=RUN_ID, sha256="sha256:" + "0" * 64)
    return build_plan(
        inventory,
        config,
        run_id=RUN_ID,
        generated_at="2026-07-06T00:00:00+00:00",
        inventory_ref=ref,
    )


@pytest.mark.parametrize(("name", "case"), corpus_cases())
def test_weird_document__planned_as_expected(
    name: str, case: dict[str, object], corpus_plan: Plan
) -> None:
    """FR-015: each risky-file class in the weird-document corpus is classified, never modified."""
    expect_raw = case["expect"]
    assert isinstance(expect_raw, dict)
    expect = cast(dict[str, object], expect_raw)
    actions = {a.path: a for a in corpus_plan.actions}
    skips = {s.path: s for s in corpus_plan.skips}
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
        case "noop":
            assert name not in actions and name not in skips
        case other:
            pytest.fail(f"unknown disposition {other!r} in {name}.expect.json")


def test_sidecars_never_become_candidates(corpus_plan: Plan) -> None:
    planned = {a.path for a in corpus_plan.actions} | {s.path for s in corpus_plan.skips}
    assert not any(p.endswith(".expect.json") for p in planned)
