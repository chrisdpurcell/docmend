"""Planning-layer decisions (FR-002, FR-015, DR-002; EC-008/EC-011; adr-0009 gates).

Fact-level tests build inventories via discovery.scan over recipe corpora
(tests/corpus.py) so planning is exercised against real scan output.
"""

import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from corpus import GENERATED_AT, RUN_ID, FileRecipe, materialize, seeded_faker
from docmend.config import DocmendConfig, EncodingConfig, LimitsConfig, PathsConfig, WriteConfig
from docmend.discovery import scan
from docmend.inventory import DetectedEncoding
from docmend.plan import ArtifactRef, Plan
from docmend.planning import build_plan
from docmend.transform.dispatch import FileClass, Operation, apply_text_transforms

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

    def test_symlink_matching_plan_time_exclude__excluded_not_symlink(self, tmp_path: Path) -> None:
        """A plan-time exclude covering a symlink relabels its skip reason.

        Without this, every inventory symlink gets the generic "symlink"
        reason even when it also matches an exclude added between scan and
        plan — leaving the two skip paths (fact-gate ladder vs. symlink list)
        disagreeing about why the same kind of filtered path is skipped.
        """
        (tmp_path / "real.txt").write_text("x\n")
        (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")
        inventory = scan(tmp_path, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)
        narrowed = DocmendConfig(paths=PathsConfig(exclude=["link.txt"]))
        plan = build_plan(
            inventory,
            narrowed,
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
            inventory_ref=INV_REF,
            mint_id=fixed_ids(),
        )
        skip = {s.path: s for s in plan.skips}["link.txt"]
        assert skip.reason == "excluded"
        assert skip.detail == "matched a plan-time exclude pattern"

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

    def test_exclude_pattern__skipped_with_reason(self, tmp_path: Path) -> None:
        """FR-012: the exclude ladder's second branch (matched, not merely unincluded).

        Scanned permissively, then re-planned with a narrower exclude — the
        file is present in the inventory (unlike the include-mismatch case in
        test_plan_time_filters__consistent_with_scan) so it reaches the
        `exclude.match_file` branch specifically.
        """
        (tmp_path / "excluded.txt").write_bytes(b"x\n")
        inventory = scan(
            tmp_path,
            DocmendConfig(paths=PathsConfig(exclude=[])),
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
        )
        narrowed = DocmendConfig(paths=PathsConfig(exclude=["excluded.txt"]))
        plan = build_plan(
            inventory,
            narrowed,
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
            inventory_ref=INV_REF,
            mint_id=fixed_ids(),
        )
        skip = {s.path: s for s in plan.skips}["excluded.txt"]
        assert skip.reason == "excluded"
        assert skip.detail == "matched a plan-time exclude pattern"

    def test_binary_suspect__skipped(self, tmp_path: Path) -> None:
        """FR-007 gate 0: no encoding candidate at all -> binary-suspect, not a silent pass."""
        (tmp_path / "opaque.bin").write_bytes(bytes(range(0x80, 0xFF)) * 2)
        config = DocmendConfig(paths=PathsConfig(include=["**/*.bin"]))
        plan = plan_over(tmp_path, config)
        assert {s.path: s.reason for s in plan.skips}["opaque.bin"] == "binary-suspect"

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

    def test_source_root__matches_inventory(self, tmp_path: Path) -> None:
        """1.1/decision 3: apply resolves files from the plan alone (FR-012)."""
        materialize(tmp_path, [FileRecipe("a.txt", "utf-8", "crlf")], seeded_faker())
        inventory = scan(tmp_path, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)
        plan = build_plan(
            inventory,
            DocmendConfig(),
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
            inventory_ref=INV_REF,
            mint_id=fixed_ids(),
        )
        assert plan.source_root == inventory.source_root

    def test_relative_backup_dir__pinned_to_planning_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """codex CR-NEW-002: the reviewed snapshot, not apply's cwd, decides the backup home."""
        materialize(tmp_path, [FileRecipe("a.txt", "utf-8", "crlf")], seeded_faker())
        monkeypatch.chdir(tmp_path)
        config = DocmendConfig(write=WriteConfig(backup_dir=Path("backups")))
        plan = plan_over(tmp_path, config)
        write_snapshot = cast("dict[str, object]", plan.config["write"])
        assert write_snapshot["backup_dir"] == str((tmp_path / "backups").resolve())


class TestContentPass:
    def test_crlf_legacy_txt__full_action_with_provenance(self, tmp_path: Path) -> None:
        """FR-002/C.4: action carries operations, hashes, and decision provenance."""
        # sentences=15 (vs. the corpus default of 3): the recipe's accented
        # characters are 2 non-ASCII bytes/line, so the default 3-sentence
        # recipe (6 bytes) never clears the 20-byte non_ascii_floor gate.
        materialize(
            tmp_path,
            [FileRecipe("legacy.txt", "windows-1252", "crlf", sentences=15)],
            seeded_faker(),
        )
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["legacy.txt"]
        assert action.operations[0] == "reencode"
        assert "normalize_newlines" in action.operations
        assert action.operations[-1] == "rename"
        assert action.target_path == "legacy.md"
        assert action.source_sha256.startswith("sha256:")
        assert action.provenance.newline_style == "crlf"
        assert action.provenance.detected_encoding is not None
        assert action.provenance.detected_encoding.method == "charset-normalizer"

    def test_utf8_bom__reencode_planned(self, tmp_path: Path) -> None:
        """EC-007: BOM strip is a byte rewrite -> reencode even if text is clean."""
        (tmp_path / "bom.txt").write_bytes(b"\xef\xbb\xbfclean\n")
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["bom.txt"]
        assert "reencode" in action.operations

    def test_already_clean_file__neither_action_nor_skip(self, tmp_path: Path) -> None:
        """FR-017 plan half: no-op files appear in neither list."""
        (tmp_path / "clean.md").write_bytes(b"already clean\n")
        plan = plan_over(tmp_path)
        assert all(a.path != "clean.md" for a in plan.actions)
        assert all(s.path != "clean.md" for s in plan.skips)

    def test_rename_only__still_an_action(self, tmp_path: Path) -> None:
        """FR-010: rename is a typed operation distinct from content transforms."""
        (tmp_path / "clean.txt").write_bytes(b"already clean\n")
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["clean.txt"]
        assert action.operations == ["rename"]
        assert action.target_path == "clean.md"

    def test_markup_file__never_renamed_never_whitespace(self, tmp_path: Path) -> None:
        """adr-0016: HTML gets encoding/EOL only."""
        (tmp_path / "page.html").write_bytes(b"<p>x  </p>\r\n\r\n\r\n\r\n\r\n<p>y</p>")
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["page.html"]
        assert action.operations == ["normalize_newlines"]
        assert action.target_path is None

    def test_decode_replacement__skipped(self, tmp_path: Path) -> None:
        """EC-003: strict decode failure is skipped, not silently replacement-decoded.

        A charset-normalizer-detected legacy encoding turned out to be
        unreliable for this (empirically observed to never survive
        charset-normalizer's own candidate filtering, which excludes any
        codec that fails to strictly decode the full byte sequence — see the
        report). A BOM-declared codec sidesteps the detector entirely: the
        BOM authoritatively names utf-16-le (Task 6's deterministic rung),
        and an odd trailing byte after a clean run of code units is a
        truncated code unit under strict utf-16-le decoding.
        """
        data = b"\xff\xfe" + "clean text".encode("utf-16-le") + b"\x41"
        (tmp_path / "broken.txt").write_bytes(data)
        plan = plan_over(tmp_path)
        skip = {s.path: s for s in plan.skips}.get("broken.txt")
        assert skip is not None
        assert skip.reason == "decode-replacement"

    def test_utf16_suspect__bomless_interleaved_nul(self, tmp_path: Path) -> None:
        """EC-010: BOM-less UTF-16 pattern gets the specific reason, never generic binary."""
        (tmp_path / "suspect.txt").write_bytes("plain ascii text here".encode("utf-16-le"))
        plan = plan_over(tmp_path)
        assert {s.path: s.reason for s in plan.skips}["suspect.txt"] == "utf16-suspect"

    def test_tiny_nul_file__too_short_for_utf16_heuristic(self, tmp_path: Path) -> None:
        """EC-004: below the 4-byte floor, _utf16_suspect can't compute parity; plain nul-bytes."""
        (tmp_path / "tiny.txt").write_bytes(b"\x00a")
        plan = plan_over(tmp_path)
        assert {s.path: s.reason for s in plan.skips}["tiny.txt"] == "nul-bytes"

    def test_scattered_nuls__plain_nul_bytes_reason(self, tmp_path: Path) -> None:
        """EC-004: scattered NULs are nul-bytes, not utf16-suspect."""
        (tmp_path / "nully.txt").write_bytes(b"abc\x00defghijklmnop\x00qrs")
        plan = plan_over(tmp_path)
        assert {s.path: s.reason for s in plan.skips}["nully.txt"] == "nul-bytes"

    def test_changed_since_scan__skipped(self, tmp_path: Path) -> None:
        """AW-004 analog at plan time: stale facts are never decided on."""
        (tmp_path / "moving.txt").write_bytes(b"version one\r\n")
        inventory = scan(tmp_path, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)
        (tmp_path / "moving.txt").write_bytes(b"version two\r\n")
        plan = build_plan(
            inventory,
            DocmendConfig(),
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
            inventory_ref=INV_REF,
            mint_id=fixed_ids(),
        )
        assert {s.path: s.reason for s in plan.skips}["moving.txt"] == "changed-since-scan"

    def test_grown_file__changed_since_scan(self, tmp_path: Path) -> None:
        """NFR-001: a size mismatch is caught before any read, on a file that grew after scan."""
        (tmp_path / "growing.txt").write_bytes(b"short\r\n")
        inventory = scan(tmp_path, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)
        (tmp_path / "growing.txt").write_bytes(b"much longer content now\r\n" * 100)
        plan = build_plan(
            inventory,
            DocmendConfig(),
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
            inventory_ref=INV_REF,
            mint_id=fixed_ids(),
        )
        skip = {s.path: s for s in plan.skips}["growing.txt"]
        assert skip.reason == "changed-since-scan"
        assert "size" in (skip.detail or "")

    def test_unknown_codec__decode_replacement_skip(self, tmp_path: Path) -> None:
        """Theoretical LookupError guard: an unrecognized codec name is skipped like
        any undecodable file, rather than propagating out of build_plan.

        The doctored inventory record simulates a detector naming a codec
        Python's registry doesn't have (never observed from charset-normalizer
        in practice, hence exercising it here rather than via a real corpus
        recipe).
        """
        (tmp_path / "plain.txt").write_bytes(b"plain ascii text here\n")
        inventory = scan(tmp_path, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)
        record = inventory.files[0]
        doctored_encoding = record.encoding.model_copy(
            update={
                "detected": DetectedEncoding(
                    name="bogus-codec", confidence=1.0, method="utf8-strict"
                )
            }
        )
        doctored_record = record.model_copy(update={"encoding": doctored_encoding})
        doctored_inventory = inventory.model_copy(update={"files": [doctored_record]})
        plan = build_plan(
            doctored_inventory,
            DocmendConfig(),
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
            inventory_ref=INV_REF,
            mint_id=fixed_ids(),
        )
        skip = {s.path: s for s in plan.skips}["plain.txt"]
        assert skip.reason == "decode-replacement"
        assert "bogus-codec" in (skip.detail or "")

    def test_vanished_file__unreadable_skip(self, tmp_path: Path) -> None:
        """ERR-005 analog: deleted between scan and plan -> skip, batch continues."""
        (tmp_path / "gone.txt").write_bytes(b"here now\r\n")
        (tmp_path / "stays.txt").write_bytes(b"stays\r\n")
        inventory = scan(tmp_path, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)
        (tmp_path / "gone.txt").unlink()
        plan = build_plan(
            inventory,
            DocmendConfig(),
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
            inventory_ref=INV_REF,
            mint_id=fixed_ids(),
        )
        assert {s.path: s.reason for s in plan.skips}["gone.txt"] == "unreadable"
        assert any(a.path == "stays.txt" for a in plan.actions)

    @pytest.mark.skipif(os.geteuid() == 0, reason="permission bits do not bind root")
    def test_permission_revoked_after_scan__unreadable_skip(self, tmp_path: Path) -> None:
        """ERR-005 analog, same-size case.

        The stale-size fast-fail only catches size changes, so a file that
        still matches its recorded size but lost read permission must still
        be caught by the read_bytes() OSError branch, not silently mistaken
        for a size-stable, readable file.
        """
        target = tmp_path / "locked.txt"
        target.write_bytes(b"here now\r\n")
        inventory = scan(tmp_path, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)
        target.chmod(0)
        try:
            plan = build_plan(
                inventory,
                DocmendConfig(),
                run_id=RUN_ID,
                generated_at=GENERATED_AT,
                inventory_ref=INV_REF,
                mint_id=fixed_ids(),
            )
        finally:
            target.chmod(0o644)
        assert {s.path: s.reason for s in plan.skips}["locked.txt"] == "unreadable"

    def test_zero_byte__handled_mechanically(self, tmp_path: Path) -> None:
        """EC-009: rename + final-newline enforcement; never the shrink heuristic."""
        (tmp_path / "empty.txt").write_bytes(b"")
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["empty.txt"]
        assert action.operations == ["ensure_final_newline", "rename"]

    def test_padded_legacy_file__shrinks_without_tripping_invariant(self, tmp_path: Path) -> None:
        """adr-0016 confirmation: whitespace-only shrinkage is legitimate."""
        (tmp_path / "padded.txt").write_bytes(b"a\n" + b"\n" * 500 + b"b\n")
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["padded.txt"]
        assert "collapse_blank_lines" in action.operations
        assert all(s.path != "padded.txt" for s in plan.skips)


class TestCollisions:
    def _corpus(self, tmp_path: Path) -> None:
        (tmp_path / "foo.txt").write_bytes(b"txt body\r\n")
        (tmp_path / "foo.md").write_bytes(b"md body\n")

    def test_policy_skip__collision_skip_recorded(self, tmp_path: Path) -> None:
        """FR-011/EC-001 default: skip-with-reason."""
        self._corpus(tmp_path)
        plan = plan_over(tmp_path)
        skip = {s.path: s for s in plan.skips}["foo.txt"]
        assert skip.reason == "collision"
        assert "foo.md" in (skip.detail or "")

    def test_policy_overwrite__action_planned(self, tmp_path: Path) -> None:
        self._corpus(tmp_path)
        from docmend.config import RenameConfig

        plan = plan_over(tmp_path, DocmendConfig(rename=RenameConfig(on_collision="overwrite")))
        action = {a.path: a for a in plan.actions}["foo.txt"]
        assert action.target_path == "foo.md"

    def test_case_variant_sources__second_claims_collision(self, tmp_path: Path) -> None:
        """Two sources differing only in suffix case both target a.md; the second collides.

        The default `paths.include` glob ("**/*.txt") is case-sensitive
        (pathspec/gitignore semantics), so a bare ".TXT" file never reaches
        discovery under default config. The include list is widened here to
        admit both, which is what exposes the claimed_targets in-run branch.
        """
        (tmp_path / "a.TXT").write_bytes(b"one\r\n")
        (tmp_path / "a.txt").write_bytes(b"two\r\n")
        config = DocmendConfig(paths=PathsConfig(include=["**/*.txt", "**/*.TXT"]))
        plan = plan_over(tmp_path, config)
        actions = {a.path: a for a in plan.actions}
        skips = {s.path: s for s in plan.skips}
        assert len(actions) == 1 and len(skips) == 1
        # sorted() ranks "a.TXT" before "a.txt" (ASCII 'T' < 't'), so a.TXT is
        # processed first and claims a.md; a.txt is the later collider.
        assert actions["a.TXT"].target_path == "a.md"
        assert skips["a.txt"].reason == "collision"

    def test_case_variant_sources__overwrite_policy_never_merges_same_run_targets(
        self, tmp_path: Path
    ) -> None:
        """A claimed_targets hit is a plan-internal conflict, not an FR-011 collision.

        `on_collision = "overwrite"` licenses clobbering a *pre-existing* target
        (AW-002). It must not license two actions in the same run planning the
        same target — that would make the second apply silently destroy the
        first apply's output, violating G-005.
        """
        (tmp_path / "a.TXT").write_bytes(b"one\r\n")
        (tmp_path / "a.txt").write_bytes(b"two\r\n")
        from docmend.config import RenameConfig

        config = DocmendConfig(
            paths=PathsConfig(include=["**/*.txt", "**/*.TXT"]),
            rename=RenameConfig(on_collision="overwrite"),
        )
        plan = plan_over(tmp_path, config)
        actions = {a.path: a for a in plan.actions}
        skips = {s.path: s for s in plan.skips}
        assert len(actions) == 1 and len(skips) == 1
        assert actions["a.TXT"].target_path == "a.md"
        assert skips["a.txt"].reason == "collision"
        assert "this run" in (skips["a.txt"].detail or "")

    def test_case_variant_sources__fail_policy_second_claims_collision(
        self, tmp_path: Path
    ) -> None:
        """Under `fail` the same-run collider is a plan skip (the CLI turns the
        collision count into exit 1); the plan artifact itself matches skip."""
        (tmp_path / "a.TXT").write_bytes(b"one\r\n")
        (tmp_path / "a.txt").write_bytes(b"two\r\n")
        from docmend.config import RenameConfig

        config = DocmendConfig(
            paths=PathsConfig(include=["**/*.txt", "**/*.TXT"]),
            rename=RenameConfig(on_collision="fail"),
        )
        plan = plan_over(tmp_path, config)
        assert len(plan.actions) == 1
        assert {s.path: s.reason for s in plan.skips} == {"a.txt": "collision"}

    def test_action_ids__sequential_and_run_scoped(self, tmp_path: Path) -> None:
        """DR-002: per-action ID correlated with the run-ID."""
        (tmp_path / "a.txt").write_bytes(b"x\r\n")
        (tmp_path / "b.txt").write_bytes(b"y\r\n")
        plan = plan_over(tmp_path)
        assert [a.action_id for a in plan.actions] == [f"{RUN_ID}/a1", f"{RUN_ID}/a2"]

    def test_docmend_ids__unique(self, tmp_path: Path) -> None:
        """adr-0008: every planned document gets a distinct UUIDv7 identity."""
        (tmp_path / "a.txt").write_bytes(b"x\r\n")
        (tmp_path / "b.txt").write_bytes(b"y\r\n")
        plan = plan_over(tmp_path)
        ids = [a.docmend_id for a in plan.actions]
        assert len(set(ids)) == len(ids)


class TestWatchdog:
    """FR-019/OQ-028/ERR-009: the content-pass per-file watchdog (DEV-002)."""

    def test_content_pass__slow_transform_recorded_as_timeout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A file whose transform prediction exceeds limits.per_file_timeout is
        skipped with reason 'timeout' (ERR-009) while the rest of the batch
        plans normally — the R-007 pathological-transform case."""
        # Trailing whitespace + .txt makes each file a real action candidate
        # (trim + txt_to_md rename), so the fast file proves the batch proceeds.
        (tmp_path / "slow.txt").write_bytes(b"SLOWMARKER body \n")
        (tmp_path / "fast.txt").write_bytes(b"fast body \n")

        def slow_transforms(
            text: str,
            file_class: FileClass,
            *,
            trim_trailing_ws: bool,
            final_newline: bool,
            collapse_max: int | None,
            tab_width: int | None,
        ) -> tuple[str, list[Operation]]:
            if "SLOWMARKER" in text:
                time.sleep(5)  # far beyond the 0.05s budget; the alarm fires first
            # `apply_text_transforms` here is the test-module import (the real
            # function), not the monkeypatched planning.apply_text_transforms.
            return apply_text_transforms(
                text,
                file_class,
                trim_trailing_ws=trim_trailing_ws,
                final_newline=final_newline,
                collapse_max=collapse_max,
                tab_width=tab_width,
            )

        monkeypatch.setattr("docmend.planning.apply_text_transforms", slow_transforms)
        config = DocmendConfig(limits=LimitsConfig(per_file_timeout=0.05))
        plan = plan_over(tmp_path, config)

        reasons = {skip.path: skip.reason for skip in plan.skips}
        assert reasons.get("slow.txt") == "timeout"
        # The fast file was unaffected: it produced a normal action, and its
        # path is never among the skips.
        assert "fast.txt" not in reasons
        assert "fast.txt" in {action.path for action in plan.actions}
        assert "slow.txt" not in {action.path for action in plan.actions}
