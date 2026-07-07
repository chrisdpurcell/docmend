"""Discovery-layer tests (spec: FR-001, FR-012, DR-001, NFR-006; ERR-007, EC-006/008/009/011).

Covers the MS-1 exit criteria: a valid inventory from a synthetic corpus,
provably read-only scanning, and working include/exclude filters.
"""

import hashlib
import os
import time
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from corpus import CORPUS_RECIPES, GENERATED_AT, RUN_ID, materialize, seeded_faker
from docmend.config import DocmendConfig, EncodingConfig, LimitsConfig, PathsConfig
from docmend.discovery import NewlineCensus, classify_file, scan
from docmend.inventory import FileRecord, Inventory


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    materialize(root, CORPUS_RECIPES, seeded_faker())
    return root


def run_scan(root: Path, config: DocmendConfig | None = None) -> Inventory:
    return scan(root, config or DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)


def snapshot(root: Path) -> dict[str, tuple[int, str]]:
    """(mtime_ns, sha256) per file — the FR-001 'nothing changed' witness."""
    result: dict[str, tuple[int, str]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            stat = path.stat()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result[str(path.relative_to(root))] = (stat.st_mtime_ns, digest)
    return result


class TestScanReadOnly:
    def test_scan__modifies_no_file_and_creates_none(self, corpus: Path) -> None:
        """spec: FR-001 — scan is provably read-only: mtimes, hashes, and the
        file set are identical before and after."""
        before = snapshot(corpus)
        run_scan(corpus)
        assert snapshot(corpus) == before


class TestClassification:
    def test_newline_styles__match_recipes(self, corpus: Path) -> None:
        """spec: DR-001 / EC-006 — per-file newline census, 'mixed' recorded as such."""
        inventory = run_scan(corpus)
        styles = {record.path: record.newline_style for record in inventory.files}
        for recipe in CORPUS_RECIPES:
            if recipe.encoding == "utf-16-le-bom":
                continue  # newline bytes are interleaved with NULs; census is byte-level
            assert styles[recipe.path] == recipe.newline, recipe.path

    def test_encoding_facts__match_recipes(self, corpus: Path) -> None:
        """spec: DR-001 / FR-007 deterministic rungs — BOM and strict-UTF-8 facts."""
        records = {record.path: record for record in run_scan(corpus).files}
        for recipe in CORPUS_RECIPES:
            facts = records[recipe.path].encoding
            assert facts.bom == recipe.expected_bom, recipe.path
            assert facts.utf8_valid is recipe.expected_utf8_valid, recipe.path
            if recipe.expected_bom:
                assert facts.detected is not None and facts.detected.method == "bom"
            elif recipe.encoding == "windows-1252":
                # Legacy detection is the MS-2 charset-normalizer rung (this
                # task): the deterministic rungs hand off, and the rung fills
                # in the verdict at scan time.
                assert facts.detected is not None
                assert facts.detected.method == "charset-normalizer"
                assert records[recipe.path].non_ascii_bytes > 0

    def test_nul_bytes_flagged(self, corpus: Path) -> None:
        records = {record.path: record for record in run_scan(corpus).files}
        assert records["nulls.txt"].nul_bytes is True
        assert records["plain.txt"].nul_bytes is False

    def test_sha256_and_size__match_disk(self, corpus: Path) -> None:
        records = {record.path: record for record in run_scan(corpus).files}
        raw = (corpus / "plain.txt").read_bytes()
        assert records["plain.txt"].sha256 == f"sha256:{hashlib.sha256(raw).hexdigest()}"
        assert records["plain.txt"].size_bytes == len(raw)

    def test_zero_byte_file__recorded_normally(self, tmp_path: Path) -> None:
        """spec: DR-001 / EC-009 — the zero-byte file is a normal record."""
        (tmp_path / "empty.txt").touch()
        record = run_scan(tmp_path).files[0]
        assert record.size_bytes == 0
        assert record.newline_style == "none"
        assert record.encoding.utf8_valid is True
        assert record.encoding.ascii_only is True

    def test_suffix_recorded_verbatim(self, tmp_path: Path) -> None:
        (tmp_path / "SHOUT.TXT").write_text("x\n")
        inventory = run_scan(
            tmp_path,
            DocmendConfig(paths=PathsConfig(include=["**/*.TXT"])),
        )
        assert inventory.files[0].suffix == ".TXT"

    def test_legacy_detection__populates_inventory_at_scan(self, corpus: Path) -> None:
        """DR-001 legacy rung (MS-2): charset-normalizer fills encoding.detected."""
        inventory = run_scan(corpus)
        legacy = {f.path: f for f in inventory.files}["legacy.txt"]
        assert legacy.encoding.detected is not None
        assert legacy.encoding.detected.method == "charset-normalizer"

    def test_legacy_detection__skipped_for_bom_utf8_and_nul_files(self, corpus: Path) -> None:
        inventory = run_scan(corpus)
        by_path = {f.path: f for f in inventory.files}
        assert by_path["bom.txt"].encoding.detected is not None
        assert by_path["bom.txt"].encoding.detected.method == "bom"
        assert by_path["plain.txt"].encoding.detected is not None
        assert by_path["plain.txt"].encoding.detected.method == "utf8-strict"
        # nulls.txt (corpus "binaryish") never reaches the legacy detector
        # either: NUL and 0x01 are valid single-byte UTF-8 code points (EC-006),
        # so it is already utf8-strict-valid before the charset-normalizer gate
        # (which additionally excludes it on nul_bytes) is even checked.
        assert by_path["nulls.txt"].encoding.detected is not None
        assert by_path["nulls.txt"].encoding.detected.method == "utf8-strict"

    def test_legacy_detection__no_candidate_leaves_detected_none(self, tmp_path: Path) -> None:
        """A file that reaches the gate but the detector can't call at all
        (binary-suspect, not merely a failure) leaves encoding.detected unset."""
        (tmp_path / "blob.txt").write_bytes(bytes(range(0x80, 0x100)) * 8)
        inventory = run_scan(tmp_path)
        assert inventory.files[0].encoding.detected is None

    def test_legacy_detection__disabled_by_config(self, corpus: Path) -> None:
        config = DocmendConfig(encoding=EncodingConfig(detect=False))
        inventory = run_scan(corpus, config)
        legacy = {f.path: f for f in inventory.files}["legacy.txt"]
        assert legacy.encoding.detected is None

    def test_legacy_detection__nul_bearing_file_skips_charset_normalizer(
        self, tmp_path: Path
    ) -> None:
        """The `not record.nul_bytes` gate clause (adr-0009 gate order) has no
        other test where it is the deciding reason detection is skipped:
        nulls.txt in the corpus never reaches the gate at all, because NUL is
        already a valid UTF-8 code point (EC-006) and utf8_valid short-circuits
        first. This fixture is BOM-less, non-UTF-8-valid (0xE9 followed by a
        non-continuation byte), and NUL-bearing, so it clears the BOM and
        utf8_valid clauses and is stopped by the NUL clause specifically."""
        (tmp_path / "nul.txt").write_bytes(b"caf\xe9 text\x00more \xe9\xe8 here")
        record = run_scan(tmp_path).files[0]
        assert record.nul_bytes is True
        assert record.encoding.utf8_valid is False
        assert record.encoding.bom is None
        assert record.encoding.detected is None

    def test_legacy_detection__detector_failure_is_an_unreadable_skip(
        self, corpus: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ERR-007: a detect_legacy OSError is skipped the same way as an
        unreadable file during classification, not raised through the scan."""

        def _boom(path: Path) -> None:
            raise OSError("simulated detector failure")

        monkeypatch.setattr("docmend.detection.detect_legacy", _boom)
        inventory = run_scan(corpus)
        skipped = {record.path: record for record in inventory.skipped}
        assert skipped["legacy.txt"].reason == "unreadable"
        assert "simulated detector failure" in (skipped["legacy.txt"].detail or "")
        assert "legacy.txt" not in {f.path for f in inventory.files}


class TestFilters:
    def test_include_selects_only_matching_files(self, corpus: Path) -> None:
        """spec: FR-012 — include globs select candidates; misses are not candidates."""
        inventory = run_scan(corpus, DocmendConfig(paths=PathsConfig(include=["**/*.md"])))
        assert [record.path for record in inventory.files] == ["notes.md"]
        assert inventory.totals.skipped == 0

    def test_exclude_records_skip_with_reason(self, corpus: Path) -> None:
        """spec: FR-012 / DR-001 — an include match excluded by a *file-level*
        pattern is a recorded skip (directory-pattern excludes prune instead)."""
        config = DocmendConfig(
            paths=PathsConfig(include=["**/*.txt"], exclude=["**/nested.txt"]),
        )
        inventory = run_scan(corpus, config)
        skipped = {record.path: record.reason for record in inventory.skipped}
        assert skipped == {"sub/nested.txt": "excluded"}
        assert all(record.path != "sub/nested.txt" for record in inventory.files)

    def test_excluded_directory__pruned_without_per_file_records(self, corpus: Path) -> None:
        """A directory-pattern exclude prunes the subtree at the walk: nothing
        beneath is selected *or* recorded as a per-file skip. Selection is
        unchanged (pathspec dir-prefix semantics already excluded the files);
        only the skip noise and the descent cost go away."""
        config = DocmendConfig(
            paths=PathsConfig(include=["**/*.txt"], exclude=["**/sub/**"]),
        )
        inventory = run_scan(corpus, config)
        assert all(not record.path.startswith("sub/") for record in inventory.files)
        assert all(not record.path.startswith("sub/") for record in inventory.skipped)

    def test_default_excludes__hide_tool_and_vcs_dirs(self, corpus: Path) -> None:
        (corpus / ".git").mkdir()
        (corpus / ".git" / "notes.txt").write_text("x\n")
        (corpus / ".git" / "objects").mkdir()
        (corpus / ".git" / "objects" / "deep.txt").write_text("x\n")
        (corpus / ".venv").mkdir()
        (corpus / ".venv" / "cfg.txt").write_text("x\n")
        (corpus / "node_modules").mkdir()
        (corpus / "node_modules" / "pkg").mkdir()
        (corpus / "node_modules" / "pkg" / "readme.txt").write_text("x\n")
        (corpus / ".docmend").mkdir()
        (corpus / ".docmend" / "old-inventory.json").write_text("{}\n")
        inventory = run_scan(corpus)
        hidden = (".git/", ".venv/", "node_modules/", ".docmend/")
        assert all(not record.path.startswith(hidden) for record in inventory.files)
        assert all(not record.path.startswith(hidden) for record in inventory.skipped)

    def test_excluded_directory__unreadable_child_never_visited(self, corpus: Path) -> None:
        """Pruning means the walk never enters an excluded directory, so an
        unreadable subdirectory inside it cannot surface as ERR-007 noise."""
        sealed = corpus / ".git" / "sealed"
        sealed.mkdir(parents=True)
        sealed.chmod(0o000)
        try:
            inventory = run_scan(corpus)
        finally:
            sealed.chmod(0o755)
        assert all(record.reason != "unreadable" for record in inventory.skipped)

    def test_filters_apply_to_single_file_path(self, corpus: Path) -> None:
        """spec: FR-012 / NFR-006 — the same filters govern a single-file PATH."""
        included = run_scan(corpus / "plain.txt")
        assert [record.path for record in included.files] == ["plain.txt"]
        excluded = run_scan(
            corpus / "plain.txt",
            DocmendConfig(paths=PathsConfig(include=["**/*.txt"], exclude=["plain.txt"])),
        )
        assert excluded.totals.files == 0
        assert [record.reason for record in excluded.skipped] == ["excluded"]


class TestSingleFile:
    def test_single_file_scan__first_class(self, corpus: Path) -> None:
        """spec: NFR-006 / FR-001 — a single-file PATH yields a one-record inventory
        with default configuration and no extra setup."""
        inventory = run_scan(corpus / "dos.txt")
        assert inventory.requested_path.endswith("dos.txt")
        assert inventory.source_root == str(corpus)
        assert [record.path for record in inventory.files] == ["dos.txt"]
        assert inventory.files[0].newline_style == "crlf"

    def test_single_file_not_matching_include__empty_inventory(self, tmp_path: Path) -> None:
        (tmp_path / "data.bin").write_bytes(b"x")
        inventory = run_scan(tmp_path / "data.bin")
        assert inventory.totals.files == 0
        assert inventory.totals.skipped == 0


class TestLinks:
    def test_symlinks__recorded_never_classified(self, corpus: Path) -> None:
        """spec: DR-001 / EC-008 — symlinks are recorded (file, dir, broken), not followed."""
        (corpus / "alias-link.txt").symlink_to("plain.txt")
        (corpus / "dir-link").symlink_to("sub")
        (corpus / "dangling.txt").symlink_to("gone.txt")
        inventory = run_scan(corpus)
        kinds = {record.path: record.kind for record in inventory.symlinks}
        assert kinds == {
            "alias-link.txt": "file",
            "dir-link": "directory",
            "dangling.txt": "broken",
        }
        assert all(not record.path.endswith("-link.txt") for record in inventory.files)
        # The symlinked directory's contents appear once (via sub/), not twice.
        nested = [record.path for record in inventory.files if "nested" in record.path]
        assert nested == ["sub/nested.txt"]

    def test_hard_links__grouped_by_inode(self, corpus: Path) -> None:
        """spec: DR-001 / EC-011 — st_nlink > 1 files form a shared-inode alias group."""
        os.link(corpus / "plain.txt", corpus / "alias.txt")
        inventory = run_scan(corpus)
        assert len(inventory.hard_link_groups) == 1
        group = inventory.hard_link_groups[0]
        assert group.paths == ["alias.txt", "plain.txt"]
        assert group.nlink == 2
        by_path = {record.path: record.nlink for record in inventory.files}
        assert by_path["plain.txt"] == 2


@pytest.mark.skipif(os.geteuid() == 0, reason="permission bits do not bind root")
class TestUnreadable:
    def test_unreadable_file__skipped_with_reason_scan_completes(self, corpus: Path) -> None:
        """spec: DR-001 (ERR-007) — unreadable file is recorded, scan completes."""
        target = corpus / "locked.txt"
        target.write_text("secret\n")
        target.chmod(0)
        try:
            inventory = run_scan(corpus)
        finally:
            target.chmod(0o644)
        skipped = {record.path: record for record in inventory.skipped}
        assert skipped["locked.txt"].reason == "unreadable"
        assert skipped["locked.txt"].detail
        assert inventory.totals.skipped_by_reason.unreadable == 1

    def test_unreadable_directory__skipped_scan_completes(self, corpus: Path) -> None:
        blocked = corpus / "vault"
        blocked.mkdir()
        (blocked / "inside.txt").write_text("x\n")
        blocked.chmod(0)
        try:
            inventory = run_scan(corpus)
        finally:
            blocked.chmod(0o755)
        assert any(
            record.path == "vault" and record.reason == "unreadable" for record in inventory.skipped
        )
        assert inventory.totals.files == len(CORPUS_RECIPES)


class TestDeterminism:
    def test_two_scans__identical_but_for_nothing(self, corpus: Path) -> None:
        """Sorted walk => byte-identical inventories for identical inputs."""
        first = run_scan(corpus)
        second = run_scan(corpus)
        assert first == second
        paths = [record.path for record in first.files]
        assert paths == sorted(paths)


def _census_reference(data: bytes) -> tuple[int, int, int]:
    pairs = data.count(b"\r\n")
    return (pairs, data.count(b"\n") - pairs, data.count(b"\r") - pairs)


newline_soup = st.binary(max_size=64).flatmap(
    lambda filler: st.lists(
        st.sampled_from([b"\n", b"\r", b"\r\n", filler or b"a"]), max_size=32
    ).map(b"".join)
)


class TestNewlineCensusProperties:
    @given(data=newline_soup, cut_points=st.lists(st.integers(0, 96), max_size=8))
    def test_census__independent_of_chunk_boundaries(
        self, data: bytes, cut_points: list[int]
    ) -> None:
        """The CRLF-split-across-chunks case (spec FR-008's future input facts):
        any chunking of the same bytes yields the same census."""
        whole = NewlineCensus()
        whole.update(data)
        whole.finish()

        chunked = NewlineCensus()
        previous = 0
        for cut in sorted(point for point in cut_points if point <= len(data)):
            chunked.update(data[previous:cut])
            previous = cut
        chunked.update(data[previous:])
        chunked.finish()

        assert (whole.crlf, whole.bare_lf, whole.bare_cr) == (
            chunked.crlf,
            chunked.bare_lf,
            chunked.bare_cr,
        )

    @given(data=newline_soup)
    def test_census__matches_whole_buffer_reference(self, data: bytes) -> None:
        census = NewlineCensus()
        census.update(data)
        census.finish()
        assert (census.crlf, census.bare_lf, census.bare_cr) == _census_reference(data)


class TestClassifierChunking:
    @pytest.mark.parametrize("chunk_size", [1, 2, 3, 7, 1 << 20])
    def test_classifier__independent_of_chunk_size(self, tmp_path: Path, chunk_size: int) -> None:
        """BOM window and CRLF handling must not depend on read granularity."""
        target = tmp_path / "boundary.txt"
        target.write_bytes(b"\xef\xbb\xbfline one\r\nline two\rrest\ncaf\xc3\xa9\r\n")
        stat = target.lstat()
        record = classify_file(target, "boundary.txt", stat, chunk_size=chunk_size)
        assert record.encoding.bom == "utf-8"
        assert record.newline_style == "mixed"
        assert record.encoding.utf8_valid is True
        assert record.non_ascii_bytes == 5  # 3 BOM bytes + 2-byte é


class TestWatchdog:
    """FR-019/OQ-028/ERR-009: the scan-side per-file watchdog (DEV-002)."""

    def test_scan__slow_classification_recorded_as_timeout_batch_continues(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A file whose classification exceeds limits.per_file_timeout is
        recorded as a 'timeout' skip (ERR-009) while the rest of the scan
        classifies normally — one pathological file cannot hang the run."""
        (tmp_path / "slow.txt").write_text("slow body\n")
        (tmp_path / "fast.txt").write_text("fast body\n")

        def slow_classify(
            full: Path, rel: str, stat: os.stat_result, *, chunk_size: int = 1 << 20
        ) -> FileRecord:
            if rel == "slow.txt":
                time.sleep(5)  # far beyond the 0.05s budget; the alarm fires first
            # `classify_file` here is the test-module import (the real function),
            # not the monkeypatched discovery.classify_file — so no recursion.
            return classify_file(full, rel, stat, chunk_size=chunk_size)

        monkeypatch.setattr("docmend.discovery.classify_file", slow_classify)
        config = DocmendConfig(limits=LimitsConfig(per_file_timeout=0.05))
        inventory = run_scan(tmp_path, config)

        skips = {record.path: record.reason for record in inventory.skipped}
        assert skips.get("slow.txt") == "timeout"
        assert "fast.txt" in {record.path for record in inventory.files}
        assert "slow.txt" not in {record.path for record in inventory.files}
        assert inventory.totals.skipped_by_reason.timeout == 1
        # totals still reconcile with the per-reason breakdown after the new reason.
        assert inventory.totals.skipped == (
            inventory.totals.skipped_by_reason.excluded
            + inventory.totals.skipped_by_reason.unreadable
            + inventory.totals.skipped_by_reason.timeout
        )
