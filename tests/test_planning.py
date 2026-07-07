"""Planning-layer decisions (FR-002, FR-015, DR-002; EC-008/EC-011; adr-0009 gates).

Fact-level tests build inventories via discovery.scan over recipe corpora
(tests/corpus.py) so planning is exercised against real scan output.
"""

import uuid
from collections.abc import Callable
from pathlib import Path

from corpus import GENERATED_AT, RUN_ID, FileRecipe, materialize, seeded_faker
from docmend.config import DocmendConfig, EncodingConfig, LimitsConfig, PathsConfig
from docmend.discovery import scan
from docmend.plan import ArtifactRef, Plan
from docmend.planning import build_plan

INV_REF = ArtifactRef(path="inventory.json", run_id=RUN_ID, sha256="sha256:" + "0" * 64)


def fixed_ids() -> Callable[[], uuid.UUID]:
    # Deterministic stand-in for uuid.uuid7 (no version= param: the UUID
    # constructor's version check predates RFC 9562 versions on some releases,
    # and nothing asserts version bits — only uniqueness and shape).
    counter = iter(range(1, 10_000))
    return lambda: uuid.UUID(int=(0x0198_0000 << 96) | next(counter))


def plan_over(root: Path, config: DocmendConfig | None = None) -> Plan:
    config = config or DocmendConfig()
    inventory = scan(root, config, run_id=RUN_ID, generated_at=GENERATED_AT)
    return build_plan(
        inventory,
        config,
        run_id=RUN_ID,
        generated_at=GENERATED_AT,
        inventory_ref=INV_REF,
        mint_id=fixed_ids(),
    )


class TestFactGates:
    def test_oversize_file__skipped_with_reason(self, tmp_path: Path) -> None:
        """FR-019 plan-time size guard: oversize skipped at plan with reason."""
        (tmp_path / "big.txt").write_bytes(b"a" * (2 * 1024 * 1024))
        config = DocmendConfig(limits=LimitsConfig(max_file_size_mib=1))
        plan = plan_over(tmp_path, config)
        assert [s.reason for s in plan.skips if s.path == "big.txt"] == ["oversize"]

    def test_hard_link_group__every_member_skipped(self, tmp_path: Path) -> None:
        """EC-011: shared-inode alias groups are never planned for mutation."""
        original = tmp_path / "a.txt"
        original.write_text("x\n")
        (tmp_path / "b.txt").hardlink_to(original)
        plan = plan_over(tmp_path)
        reasons = {s.path: s.reason for s in plan.skips}
        assert reasons["a.txt"] == "hard-link-alias"
        assert reasons["b.txt"] == "hard-link-alias"

    def test_symlink__skipped_with_reason(self, tmp_path: Path) -> None:
        """EC-008: symlinks recorded, never planned for mutation."""
        (tmp_path / "real.txt").write_text("x\n")
        (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")
        plan = plan_over(tmp_path)
        assert {s.path: s.reason for s in plan.skips}["link.txt"] == "symlink"

    def test_nul_bytes__skipped(self, tmp_path: Path) -> None:
        """EC-004 / FR-015: NUL-bearing files are risky, skipped with reason."""
        materialize(tmp_path, [FileRecipe("nulls.txt", "binaryish", "lf")], seeded_faker())
        plan = plan_over(tmp_path)
        assert {s.path: s.reason for s in plan.skips}["nulls.txt"] in ("nul-bytes", "utf16-suspect")

    def test_detection_disabled__legacy_file_skipped(self, tmp_path: Path) -> None:
        materialize(tmp_path, [FileRecipe("legacy.txt", "windows-1252", "lf")], seeded_faker())
        config = DocmendConfig(encoding=EncodingConfig(detect=False))
        plan = plan_over(tmp_path, config)
        skip = {s.path: s for s in plan.skips}["legacy.txt"]
        assert skip.reason == "low-confidence-encoding"
        assert skip.detail == "encoding detection disabled"

    def test_low_confidence__skipped_with_thresholds_in_detail(self, tmp_path: Path) -> None:
        """FR-007 gate 1: confidence below threshold -> skip (provenance C.4).

        The synthetic "windows-1252" corpus recipe is clean single-encoding
        prose, and charset-normalizer reports chaos=0 (confidence 1.0) for it
        regardless of length, so it cannot exercise this gate. C1-range bytes
        (undefined in windows-1252) interspersed with ASCII prose still let
        the detector settle on a candidate, but with confidence measurably
        below 1.0 — that is what this gate needs to fire on.
        """
        body = (
            bytes([0x80, 0x81, 0x8D, 0x8F, 0x90, 0x9D]) * 3
            + b"some ascii text here to pad it out nicely for detect"
            + bytes([0x80, 0x9D])
            + b"ion purposes yes indeed and even more padding words to be safe here"
        )
        (tmp_path / "legacy.txt").write_bytes(body)
        config = DocmendConfig(encoding=EncodingConfig(fail_below_confidence=0.98))
        plan = plan_over(tmp_path, config)
        assert {s.path: s.reason for s in plan.skips}["legacy.txt"] == "low-confidence-encoding"

    def test_below_floor__skipped(self, tmp_path: Path) -> None:
        """FR-007 gate 2 (adr-0009): too few non-ASCII bytes to trust a legacy guess."""
        (tmp_path / "short.txt").write_bytes(b"mostly ascii text here.... \xe9\xe8")
        plan = plan_over(tmp_path)  # floor default 20; file has 2 non-ASCII bytes
        assert {s.path: s.reason for s in plan.skips}["short.txt"] == "below-non-ascii-floor"
        # If the detector returns NO candidate for these bytes (binary-suspect
        # fires first in the ladder), adjust the ASCII prose until it detects
        # confidently — mirror Task 11's 3-consecutive-runs stability rule.

    def test_plan_time_filters__consistent_with_scan(self, tmp_path: Path) -> None:
        """FR-012: plan applies effective include/exclude over inventory records."""
        materialize(
            tmp_path,
            [FileRecipe("keep.txt", "utf-8", "lf"), FileRecipe("drop.txt", "utf-8", "lf")],
            seeded_faker(),
        )
        inventory = scan(tmp_path, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)
        narrowed = DocmendConfig(paths=PathsConfig(include=["keep.txt"], exclude=[]))
        plan = build_plan(
            inventory,
            narrowed,
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
            inventory_ref=INV_REF,
            mint_id=fixed_ids(),
        )
        assert {s.path: s.reason for s in plan.skips}["drop.txt"] == "excluded"
        assert all(a.path != "drop.txt" for a in plan.actions)


class TestPlanShape:
    def test_totals__reconcile_with_action_and_skip_lists(self, tmp_path: Path) -> None:
        """DR-002: totals equal the record-list lengths."""
        materialize(tmp_path, [FileRecipe("a.txt", "utf-8", "crlf")], seeded_faker())
        plan = plan_over(tmp_path)
        assert plan.totals.actions == len(plan.actions)
        assert plan.totals.skips == len(plan.skips)

    def test_plan__validates_against_schema(self, tmp_path: Path) -> None:
        from docmend.artifacts import validate_artifact

        materialize(tmp_path, [FileRecipe("a.txt", "utf-8", "crlf")], seeded_faker())
        validate_artifact("plan", plan_over(tmp_path).model_dump(mode="json"))
