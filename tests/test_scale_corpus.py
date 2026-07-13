"""NFR-001 deterministic streamed-corpus contracts (OQ-037, OQ-040)."""

import ast
import os
import stat
import sys
from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from pathlib import Path, PurePosixPath
from typing import cast

import pytest

import docmend.scale_corpus as scale_corpus
from docmend.config import DocmendConfig
from docmend.discovery import scan
from docmend.plan import ArtifactRef
from docmend.planning import build_plan
from docmend.scale_corpus import (
    MAX_SCALE_FILE_COUNT,
    ScaleRecipe,
    ScaleRecipeClass,
    boundary_samples,
    corpus_inode_needs,
    expected_finding_keys,
    iter_recipes,
    materialize_scale_corpus,
    recipe_counts,
    render_recipe,
    summarize_scale_corpus,
)
from docmend.scale_resources import allocated_bytes

RUN_ID = "run_20260713T000000Z_000040"
PLAN_RUN_ID = "run_20260713T000000Z_000041"
GENERATED_AT = "2026-07-13T00:00:00+00:00"


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _set_attribute(instance: object, name: str, value: object) -> None:
    setattr(instance, name, value)


class TestRecipeStream:
    def test_iter_recipes__is_constant_size_iterator_with_canonical_first_path(self) -> None:
        small = iter_recipes(1)
        recipes = iter_recipes(MAX_SCALE_FILE_COUNT)

        assert isinstance(recipes, Iterator)
        assert sys.getsizeof(recipes) == sys.getsizeof(small)
        assert next(recipes).path.endswith("doc000000.txt")

    @pytest.mark.parametrize(
        "count",
        [
            0,
            -1,
            MAX_SCALE_FILE_COUNT + 1,
            True,
            False,
            cast("int", 1.0),
            cast("int", "40"),
        ],
    )
    def test_count__strict_integer_from_one_through_one_million(self, count: int) -> None:
        with pytest.raises(ValueError, match="count must be an integer from 1 to 1000000"):
            iter_recipes(count)

    def test_recipe__is_frozen_and_typed(self) -> None:
        recipe = next(iter_recipes(1))

        assert isinstance(recipe, ScaleRecipe)
        assert isinstance(recipe.recipe_class, ScaleRecipeClass)
        with pytest.raises(FrozenInstanceError):
            _set_attribute(recipe, "path", "changed.txt")

    def test_generated_paths__are_unique_canonical_safe_relatives(self) -> None:
        recipes = tuple(iter_recipes(2_174))
        paths = [recipe.path for recipe in recipes]

        assert len(paths) == len(set(paths))
        for path in paths:
            pure = PurePosixPath(path)
            assert path == pure.as_posix()
            assert not pure.is_absolute()
            assert all(part not in ("", ".", "..") for part in pure.parts)
            assert "\\" not in path


class TestDistribution:
    def test_full_cycle__preserves_35_actions_4_noops_1_skip(self) -> None:
        counts = recipe_counts(40)

        assert counts.rename_only == 24
        assert counts.rewrite_and_rename == 8
        assert counts.clean_markdown == 4
        assert counts.rewrite_markdown == 2
        assert counts.legacy_conversion == 1
        assert counts.below_floor_skip == 1
        assert counts.actions == 35
        assert counts.noops == 4
        assert counts.skips == 1
        assert counts.total == 40

    @pytest.mark.parametrize(
        ("count", "actions", "noops", "skips"),
        [
            (1, 1, 0, 0),
            (24, 24, 0, 0),
            (25, 25, 0, 0),
            (33, 32, 1, 0),
            (39, 35, 4, 0),
            (40, 35, 4, 1),
            (41, 36, 4, 1),
            (79, 70, 8, 1),
            (80, 70, 8, 2),
        ],
    )
    def test_partial_cycles__derive_counts_from_40q_plus_r(
        self, count: int, actions: int, noops: int, skips: int
    ) -> None:
        counts = recipe_counts(count)

        assert (counts.actions, counts.noops, counts.skips) == (actions, noops, skips)
        assert counts.total == count

    @pytest.mark.parametrize(
        ("count", "actions", "noops", "skips", "directory_inodes", "required_inodes"),
        [
            (1_000, 875, 100, 25, 1_055, 2_055),
            (10_000, 8_750, 1_000, 250, 2_228, 12_228),
            (100_000, 87_500, 10_000, 2_500, 2_228, 102_228),
            (1_000_000, 875_000, 100_000, 25_000, 2_228, 1_002_228),
        ],
    )
    def test_qualification_tiers__have_exact_conservation_totals(
        self,
        count: int,
        actions: int,
        noops: int,
        skips: int,
        directory_inodes: int,
        required_inodes: int,
    ) -> None:
        counts = recipe_counts(count)
        file_inodes, actual_directory_inodes = corpus_inode_needs(count)

        assert (counts.actions, counts.noops, counts.skips) == (actions, noops, skips)
        assert counts.total == count
        assert (file_inodes, actual_directory_inodes) == (count, directory_inodes)
        assert file_inodes + actual_directory_inodes == required_inodes

    def test_recipe_classes__match_the_normative_bucket_boundaries(self) -> None:
        classes = [recipe.recipe_class for recipe in iter_recipes(40)]

        assert classes[:24] == [ScaleRecipeClass.RENAME_ONLY] * 24
        assert classes[24:32] == [ScaleRecipeClass.REWRITE_AND_RENAME] * 8
        assert classes[32:36] == [ScaleRecipeClass.CLEAN_MARKDOWN] * 4
        assert classes[36:38] == [ScaleRecipeClass.REWRITE_MARKDOWN] * 2
        assert classes[38] is ScaleRecipeClass.LEGACY_CONVERSION
        assert classes[39] is ScaleRecipeClass.BELOW_FLOOR_SKIP


class TestSummary:
    @pytest.mark.parametrize("fragment_size", [1, 512, 4_096])
    def test_summary__uses_exact_rendered_bytes_and_per_file_allocation(
        self, fragment_size: int
    ) -> None:
        rendered = [render_recipe(recipe) for recipe in iter_recipes(43)]

        summary = summarize_scale_corpus(43, fragment_size=fragment_size)

        assert summary.file_bytes == sum(map(len, rendered))
        assert summary.allocated_bytes == sum(
            allocated_bytes(len(data), fragment_size) for data in rendered
        )
        assert summary.file_inodes == 43
        assert summary.required_inodes == summary.file_inodes + summary.directory_inodes
        assert summary.recipe_counts == recipe_counts(43)

    def test_inode_needs__include_complete_corpus_directory_tree(self) -> None:
        assert corpus_inode_needs(1) == (1, 4)
        assert corpus_inode_needs(53) == (53, 108)
        assert corpus_inode_needs(2_173) == (2_173, 2_228)
        assert corpus_inode_needs(MAX_SCALE_FILE_COUNT) == (1_000_000, 2_228)
        assert sum(corpus_inode_needs(MAX_SCALE_FILE_COUNT)) == 1_002_228

    @pytest.mark.parametrize("fragment_size", [0, -1, True, cast("int", 1.5), cast("int", "4096")])
    def test_summary__rejects_non_positive_or_non_integer_fragment_size(
        self, fragment_size: int
    ) -> None:
        with pytest.raises(ValueError, match="fragment_size must be a positive integer"):
            summarize_scale_corpus(1, fragment_size=fragment_size)

    def test_summary__never_touches_the_filesystem(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fail(*_args: object, **_kwargs: object) -> None:
            pytest.fail("summary attempted filesystem access")

        monkeypatch.setattr(Path, "mkdir", fail)
        monkeypatch.setattr(Path, "open", fail)
        monkeypatch.setattr(Path, "write_bytes", fail)

        summary = summarize_scale_corpus(40, fragment_size=4_096)

        assert summary.recipe_counts.actions == 35


class TestBoundarySamplesAndFindings:
    def test_boundary_samples__select_first_and_last_of_every_present_class(self) -> None:
        samples = boundary_samples(40)

        assert tuple(recipe.index for recipe in samples) == (0, 23, 24, 31, 32, 35, 36, 37, 38, 39)
        assert {recipe.recipe_class for recipe in samples} == set(ScaleRecipeClass)
        assert boundary_samples(40) == samples

    def test_boundary_samples__deduplicate_singletons_and_absent_classes(self) -> None:
        assert tuple(recipe.index for recipe in boundary_samples(1)) == (0,)
        assert tuple(recipe.index for recipe in boundary_samples(25)) == (0, 23, 24)

    def test_expected_findings__derive_only_intentional_below_floor_encoding_keys(self) -> None:
        assert expected_finding_keys(39) == ()

        skipped = tuple(
            recipe
            for recipe in iter_recipes(80)
            if recipe.recipe_class is ScaleRecipeClass.BELOW_FLOOR_SKIP
        )
        expected = tuple(sorted((recipe.path, "encoding") for recipe in skipped))
        first_skipped = next(
            recipe
            for recipe in iter_recipes(40)
            if recipe.recipe_class is ScaleRecipeClass.BELOW_FLOOR_SKIP
        )

        assert expected_finding_keys(80) == expected
        assert expected_finding_keys(40) == ((first_skipped.path, "encoding"),)


class TestMaterialization:
    def test_materialize__matches_fresh_summary_and_actual_bytes(self, tmp_path: Path) -> None:
        root = tmp_path / "corpus"
        predicted = summarize_scale_corpus(43, fragment_size=4_096)

        actual = materialize_scale_corpus(root, 43, fragment_size=4_096)
        files = _files(root)

        assert actual == predicted
        assert len(files) == 43
        assert sum(map(len, files.values())) == predicted.file_bytes
        assert sum(allocated_bytes(len(data), 4_096) for data in files.values()) == (
            predicted.allocated_bytes
        )

    def test_materialize__is_repeatable_across_fresh_roots(self, tmp_path: Path) -> None:
        first = tmp_path / "first"
        second = tmp_path / "second"

        first_summary = materialize_scale_corpus(first, 80, fragment_size=512)
        second_summary = materialize_scale_corpus(second, 80, fragment_size=512)

        assert first_summary == second_summary
        assert _files(first) == _files(second)

    def test_materialize__creates_owner_only_directories_and_files(self, tmp_path: Path) -> None:
        root = tmp_path / "corpus"

        materialize_scale_corpus(root, 1, fragment_size=4_096)

        directories = [root, *(path for path in root.rglob("*") if path.is_dir())]
        files = [path for path in root.rglob("*") if path.is_file()]
        assert files
        for directory in directories:
            mode = stat.S_IMODE(directory.stat().st_mode)
            assert mode & ~0o700 == 0
        for path in files:
            mode = stat.S_IMODE(path.stat().st_mode)
            assert mode & ~0o600 == 0

    def test_materialize__opens_every_file_exclusive_and_no_follow(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_open = os.open
        create_calls: list[tuple[int, int]] = []

        def recording_open(
            path: str | bytes,
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            if flags & os.O_CREAT:
                create_calls.append((flags, mode))
            return real_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(os, "open", recording_open)

        materialize_scale_corpus(tmp_path / "corpus", 3, fragment_size=4_096)

        assert len(create_calls) == 3
        for flags, mode in create_calls:
            assert flags & os.O_EXCL
            assert flags & os.O_NOFOLLOW
            assert mode == 0o600

    def test_materialize__requests_mode_0700_for_every_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_mkdir = os.mkdir
        requested_modes: list[int] = []

        def recording_mkdir(
            path: str | bytes,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> None:
            requested_modes.append(mode)
            real_mkdir(path, mode, dir_fd=dir_fd)

        monkeypatch.setattr(os, "mkdir", recording_mkdir)

        materialize_scale_corpus(tmp_path / "corpus", 3, fragment_size=4_096)

        assert requested_modes
        assert set(requested_modes) == {0o700}

    def test_materialize__derives_parent_fragment_size_when_omitted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_fstatvfs = os.fstatvfs
        fragment_size = os.statvfs(tmp_path).f_frsize
        probed: list[int] = []

        def recording_fstatvfs(fd: int) -> os.statvfs_result:
            probed.append(fd)
            return real_fstatvfs(fd)

        def fail_path_statvfs(_path: object) -> os.statvfs_result:
            pytest.fail("fragment derivation used a path instead of the held parent descriptor")

        monkeypatch.setattr(os, "fstatvfs", recording_fstatvfs)
        monkeypatch.setattr(os, "statvfs", fail_path_statvfs)

        actual = materialize_scale_corpus(tmp_path / "corpus", 3)

        assert actual == summarize_scale_corpus(3, fragment_size=fragment_size)
        assert len(probed) == 1

    @pytest.mark.parametrize("target", ["root", "child"])
    def test_materialize__rejects_target_inserted_at_no_replace_publication(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        target: str,
    ) -> None:
        root = tmp_path / "corpus"
        # Patch the private publication boundary so the injected target wins
        # immediately before the real no-replace operation.
        real_rename_noreplace = scale_corpus._rename_noreplace  # pyright: ignore[reportPrivateUsage]
        injected = False

        def racing_rename_noreplace(parent_fd: int, source: str, destination: str) -> None:
            nonlocal injected
            should_inject = (target == "root" and destination == root.name) or (
                target == "child" and destination == "lib"
            )
            if should_inject and not injected:
                injected = True
                os.mkdir(destination, 0o700, dir_fd=parent_fd)
                directory_fd = os.open(
                    destination,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=parent_fd,
                )
                try:
                    sentinel_fd = os.open(
                        "sentinel",
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=directory_fd,
                    )
                    os.close(sentinel_fd)
                finally:
                    os.close(directory_fd)
            real_rename_noreplace(parent_fd, source, destination)

        monkeypatch.setattr(scale_corpus, "_rename_noreplace", racing_rename_noreplace)

        message = (
            "corpus root must not already exist"
            if target == "root"
            else "unexpected corpus directory collision: lib"
        )
        with pytest.raises(FileExistsError, match=message):
            materialize_scale_corpus(root, 1, fragment_size=4_096)

        assert injected is True
        collision = root if target == "root" else root / "lib"
        assert (collision / "sentinel").is_file()
        assert not tuple(collision.rglob("*.txt"))
        private_parent = tmp_path if target == "root" else root
        private_entries = tuple(private_parent.glob(".docmend-corpus-*"))
        assert len(private_entries) == 1
        assert private_entries[0].is_dir()
        assert not tuple(private_entries[0].iterdir())

    @pytest.mark.parametrize("target", ["root", "child"])
    def test_materialize__rejects_nonempty_private_directory_substitution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
    ) -> None:
        root = tmp_path / "corpus"
        real_open = os.open
        real_mkdir = os.mkdir
        injected = False
        private_open_count = 0

        def racing_open(
            path: str | bytes,
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            nonlocal injected, private_open_count
            is_private = isinstance(path, str) and path.startswith(".docmend-corpus-")
            if is_private and dir_fd is not None:
                private_open_count += 1
            selected = (target == "root" and private_open_count == 1) or (
                target == "child" and private_open_count == 2
            )
            if is_private and selected and not injected and dir_fd is not None:
                injected = True
                os.rename(
                    path,
                    f"{path}-original",
                    src_dir_fd=dir_fd,
                    dst_dir_fd=dir_fd,
                )
                real_mkdir(path, 0o700, dir_fd=dir_fd)
                replacement_fd = real_open(
                    path,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=dir_fd,
                )
                try:
                    sentinel_fd = real_open(
                        "sentinel",
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=replacement_fd,
                    )
                    os.close(sentinel_fd)
                finally:
                    os.close(replacement_fd)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(os, "open", racing_open)

        label = r"\." if target == "root" else "lib"
        with pytest.raises(OSError, match=rf"private corpus directory is not empty: {label}"):
            materialize_scale_corpus(root, 1, fragment_size=4_096)

        assert injected is True
        if root.exists():
            assert not tuple(root.rglob("*.txt"))

    def test_materialize__rejects_known_directory_replaced_by_race(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "corpus"
        real_open = os.open
        real_mkdir = os.mkdir
        injected = False

        def racing_open(
            path: str | bytes,
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            nonlocal injected
            first_file = root / "lib" / "00" / "00" / "doc000000.txt"
            if path == "lib" and dir_fd is not None and first_file.exists() and not injected:
                injected = True
                os.rename(
                    "lib",
                    "lib-original",
                    src_dir_fd=dir_fd,
                    dst_dir_fd=dir_fd,
                )
                real_mkdir(path, 0o700, dir_fd=dir_fd)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(os, "open", racing_open)

        with pytest.raises(OSError, match="corpus directory identity changed: lib"):
            materialize_scale_corpus(root, 2, fragment_size=4_096)

        original = root / "lib-original" / "00" / "00" / "doc000000.txt"
        assert injected is True
        assert original.read_bytes() == render_recipe(next(iter_recipes(1)))
        assert (root / "lib").is_dir()
        assert not tuple((root / "lib").rglob("*.txt"))

    def test_materialize__final_root_name_must_retain_published_identity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "corpus"
        original = tmp_path / "corpus-original"
        # Inject after the file write so only the final root-name reconciliation
        # can detect the replacement.
        real_materialize_recipe = scale_corpus._materialize_recipe  # pyright: ignore[reportPrivateUsage]

        def replacing_materialize_recipe(
            root_fd: int,
            recipe: ScaleRecipe,
            data: bytes,
            directory_identities: dict[tuple[str, ...], tuple[int, int]],
        ) -> None:
            real_materialize_recipe(root_fd, recipe, data, directory_identities)
            root.rename(original)
            root.mkdir(mode=0o700)

        monkeypatch.setattr(
            scale_corpus,
            "_materialize_recipe",
            replacing_materialize_recipe,
        )

        with pytest.raises(OSError, match=r"corpus directory identity changed: \."):
            materialize_scale_corpus(root, 1, fragment_size=4_096)

        assert (original / "lib" / "00" / "00" / "doc000000.txt").is_file()
        assert not tuple(root.iterdir())

    def test_materialize__final_walk_rejects_replaced_child_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "corpus"
        original = root / "lib-original"
        real_materialize_recipe = scale_corpus._materialize_recipe  # pyright: ignore[reportPrivateUsage]

        def replacing_materialize_recipe(
            root_fd: int,
            recipe: ScaleRecipe,
            data: bytes,
            directory_identities: dict[tuple[str, ...], tuple[int, int]],
        ) -> None:
            real_materialize_recipe(root_fd, recipe, data, directory_identities)
            (root / "lib").rename(original)
            (root / "lib").mkdir(mode=0o700)
            (root / "lib" / "stale").write_bytes(b"unrelated")

        monkeypatch.setattr(
            scale_corpus,
            "_materialize_recipe",
            replacing_materialize_recipe,
        )

        with pytest.raises(OSError, match="corpus directory identity changed: lib"):
            materialize_scale_corpus(root, 1, fragment_size=4_096)

        assert (original / "00" / "00" / "doc000000.txt").is_file()
        assert (root / "lib" / "stale").read_bytes() == b"unrelated"

    def test_materialize__rejects_directory_with_non_owner_permissions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "corpus"
        real_open = os.open
        injected = False

        def permissive_private_open(
            path: str | bytes,
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            nonlocal injected
            fd = real_open(path, flags, mode, dir_fd=dir_fd)
            if isinstance(path, str) and path.startswith(".docmend-corpus-") and not injected:
                injected = True
                os.fchmod(fd, 0o750)
            return fd

        monkeypatch.setattr(os, "open", permissive_private_open)

        with pytest.raises(OSError, match="corpus directory is not owner-only: \\."):
            materialize_scale_corpus(root, 1, fragment_size=4_096)

        assert injected is True
        assert not root.exists()
        private_entries = tuple(tmp_path.glob(".docmend-corpus-*"))
        assert len(private_entries) == 1
        assert private_entries[0].is_dir()
        assert stat.S_IMODE(private_entries[0].stat().st_mode) == 0o750
        assert not tuple(private_entries[0].iterdir())

    def test_materialize__failure_never_rmdirs_a_substitutable_private_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "corpus"
        real_open = os.open
        real_mkdir = os.mkdir
        real_rmdir = os.rmdir
        invalid_mode_injected = False
        substitution_attempted = False
        foreign_replacement_deleted = False

        def permissive_private_open(
            path: str | bytes,
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            nonlocal invalid_mode_injected
            fd = real_open(path, flags, mode, dir_fd=dir_fd)
            if (
                isinstance(path, str)
                and path.startswith(".docmend-corpus-")
                and not invalid_mode_injected
            ):
                invalid_mode_injected = True
                os.fchmod(fd, 0o750)
            return fd

        def substituting_rmdir(path: str | bytes, *, dir_fd: int | None = None) -> None:
            nonlocal substitution_attempted, foreign_replacement_deleted
            assert isinstance(path, str)
            assert dir_fd is not None
            substitution_attempted = True
            os.rename(
                path,
                f"{path}-original",
                src_dir_fd=dir_fd,
                dst_dir_fd=dir_fd,
            )
            # An empty replacement can be removed after the preceding identity
            # check; a sentinel would hide the stat-to-rmdir race behind ENOTEMPTY.
            real_mkdir(path, 0o700, dir_fd=dir_fd)
            real_rmdir(path, dir_fd=dir_fd)
            foreign_replacement_deleted = True

        monkeypatch.setattr(os, "open", permissive_private_open)
        monkeypatch.setattr(os, "rmdir", substituting_rmdir)

        with pytest.raises(OSError, match="corpus directory is not owner-only"):
            materialize_scale_corpus(root, 1, fragment_size=4_096)

        assert invalid_mode_injected is True
        assert substitution_attempted is False
        assert foreign_replacement_deleted is False
        private_entries = tuple(tmp_path.glob(".docmend-corpus-*"))
        assert len(private_entries) == 1
        assert not private_entries[0].name.endswith("-original")

    @pytest.mark.parametrize("root_kind", ["directory", "file", "symlink"])
    def test_materialize__requires_absent_root_and_preserves_collision(
        self, tmp_path: Path, root_kind: str
    ) -> None:
        root = tmp_path / "corpus"
        sentinel = tmp_path / "sentinel"
        sentinel.write_bytes(b"keep")
        if root_kind == "directory":
            root.mkdir()
            (root / "keep").write_bytes(b"unchanged")
        elif root_kind == "file":
            root.write_bytes(b"unchanged")
        else:
            root.symlink_to(sentinel)

        with pytest.raises(FileExistsError, match="corpus root must not already exist"):
            materialize_scale_corpus(root, 1, fragment_size=4_096)

        assert sentinel.read_bytes() == b"keep"
        if root_kind == "directory":
            assert (root / "keep").read_bytes() == b"unchanged"
        elif root_kind == "file":
            assert root.read_bytes() == b"unchanged"
        else:
            assert root.is_symlink()

    @pytest.mark.parametrize("count", [0, True, MAX_SCALE_FILE_COUNT + 1])
    def test_materialize__validates_before_creating_root(self, tmp_path: Path, count: int) -> None:
        root = tmp_path / "corpus"

        with pytest.raises(ValueError):
            materialize_scale_corpus(root, count, fragment_size=4_096)

        assert not root.exists()


def test_real_classifier_and_planner__bucket_38_actions_bucket_39_skips(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    summary = materialize_scale_corpus(root, 40, fragment_size=4_096)
    config = DocmendConfig()
    inventory = scan(root, config, run_id=RUN_ID, generated_at=GENERATED_AT)
    inventory_ref = ArtifactRef(path="inventory.json", run_id=RUN_ID, sha256="sha256:" + "0" * 64)
    plan = build_plan(
        inventory,
        config,
        run_id=PLAN_RUN_ID,
        generated_at=GENERATED_AT,
        inventory_ref=inventory_ref,
    )
    recipes = tuple(iter_recipes(40))
    actions = {action.path: action for action in plan.actions}
    skips = {skip.path: skip for skip in plan.skips}
    records = {record.path: record for record in inventory.files}

    above = recipes[38]
    below = recipes[39]
    above_detection = records[above.path].encoding.detected
    below_detection = records[below.path].encoding.detected

    assert inventory.totals.files == 40
    assert plan.totals.actions == summary.recipe_counts.actions == 35
    assert plan.totals.skips == summary.recipe_counts.skips == 1
    assert (
        len(inventory.files) - plan.totals.actions - plan.totals.skips
        == summary.recipe_counts.noops
    )
    assert actions[above.path].operations == ["reencode", "normalize_newlines", "rename"]
    assert above_detection is not None
    assert above_detection.confidence >= config.encoding.fail_below_confidence
    assert records[above.path].non_ascii_bytes >= config.encoding.non_ascii_floor
    assert skips[below.path].reason == "below-non-ascii-floor"
    assert below_detection is not None
    assert below_detection.confidence >= config.encoding.fail_below_confidence
    assert records[below.path].non_ascii_bytes < config.encoding.non_ascii_floor
    assert expected_finding_keys(40) == ((below.path, "encoding"),)


def test_shipped_module__has_no_test_or_third_party_imports() -> None:
    source_path = Path(scale_corpus.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.partition(".")[0])

    assert roots <= {*sys.stdlib_module_names, "docmend"}
    assert "faker" not in roots
    assert "tests" not in roots
