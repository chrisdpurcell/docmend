"""NFR-001 Linux resource-preflight contracts for scale qualification."""

import os
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from docmend.scale_evidence import FilesystemCapacityEvidence, ReferenceEnvironment
from docmend.scale_resources import (
    ALLOWED_BINDING_FILESYSTEMS,
    REJECTED_NETWORK_FILESYSTEMS,
    MountFlagProjection,
    MountInfo,
    Requirement,
    ResourcePreflightError,
    SwapCounters,
    allocated_bytes,
    available_capacity,
    build_preflight_evidence,
    check_capacity,
    compare_reference_environment,
    is_binding_filesystem,
    max_child_vm_swap,
    parse_mountinfo,
    parse_vm_swap,
    parse_vmstat_swap,
    project_mount_flags,
    select_mount,
    swap_counter_delta,
)


def _stat_result(device: int) -> os.stat_result:
    return os.stat_result((0, 0, device, 0, 0, 0, 0, 0, 0, 0))


def _statvfs_result(
    *,
    bytes_available: int,
    inodes_available: int,
    fragment_size: int = 1,
    bytes_free: int | None = None,
    inodes_free: int | None = None,
) -> os.statvfs_result:
    if bytes_available % fragment_size:
        raise ValueError("test capacity must be divisible by fragment size")
    blocks_available = bytes_available // fragment_size
    return os.statvfs_result(
        (
            fragment_size,
            fragment_size,
            10_000,
            blocks_available if bytes_free is None else bytes_free // fragment_size,
            blocks_available,
            10_000,
            inodes_available if inodes_free is None else inodes_free,
            inodes_available,
            0,
            255,
        )
    )


def _reference_environment(**updates: object) -> ReferenceEnvironment:
    values: dict[str, object] = {
        "operating_system": "linux",
        "cpu_architecture": "x86_64",
        "cpu_model": "Synthetic Qualification CPU",
        "logical_cpu_count": 8,
        "ram_bytes": 32 * 1024**3,
        "storage_class": "local-ssd",
        "filesystem": "ext4",
        "mount_flags": ("rw", "relatime"),
        "python_version": "3.14.6",
        "kernel_version": "7.0.0-test",
    }
    values.update(updates)
    return ReferenceEnvironment.model_validate(values)


def _mount_line(
    *,
    mount_id: int = 36,
    parent_id: int = 25,
    mount_point: str = "/data",
    mount_options: str = "rw,relatime",
    filesystem: str = "ext4",
    optional: str = "shared:1",
    super_options: str = "rw",
) -> str:
    optional_field = f" {optional}" if optional else ""
    return (
        f"{mount_id} {parent_id} 8:1 / {mount_point} {mount_options}"
        f"{optional_field} - {filesystem} /dev/synthetic {super_options}"
    )


def _mount(
    *,
    mount_id: int = 36,
    parent_id: int = 25,
    mount_point: str = "/data",
    mount_options: str = "rw,relatime",
    filesystem: str = "ext4",
    optional: str = "shared:1",
    super_options: str = "rw",
) -> MountInfo:
    return parse_mountinfo(
        _mount_line(
            mount_id=mount_id,
            parent_id=parent_id,
            mount_point=mount_point,
            mount_options=mount_options,
            filesystem=filesystem,
            optional=optional,
            super_options=super_options,
        )
    )[0]


def _binding_projection(*, options: str = "rw,relatime") -> MountFlagProjection:
    return project_mount_flags(_mount(mount_options=options))


class TestCapacity:
    @pytest.mark.parametrize(
        ("size", "fragment_size", "expected"),
        [(0, 4_096, 0), (1, 4_096, 4_096), (4_096, 4_096, 4_096), (4_097, 4_096, 8_192)],
    )
    def test_allocated_bytes__rounds_to_fragment_boundary(
        self, size: int, fragment_size: int, expected: int
    ) -> None:
        assert allocated_bytes(size, fragment_size) == expected

    @pytest.mark.parametrize(
        ("size", "fragment_size"),
        [
            (-1, 4_096),
            (1, 0),
            (1, -1),
            (cast("int", 1.5), 4_096),
            (1, cast("int", 4_096.5)),
        ],
    )
    def test_allocated_bytes__rejects_invalid_inputs(self, size: int, fragment_size: int) -> None:
        with pytest.raises(ValueError):
            allocated_bytes(size, fragment_size)

    @pytest.mark.parametrize(("bytes_", "inodes"), [(1.5, 1), (1, 1.5)])
    def test_requirement__rejects_fractional_runtime_values(
        self, bytes_: float, inodes: float
    ) -> None:
        with pytest.raises(ValueError):
            Requirement(
                path=Path("/synthetic"),
                bytes=cast("int", bytes_),
                inodes=cast("int", inodes),
            )

    def test_available_capacity__uses_unprivileged_fragment_and_inode_values(self) -> None:
        stats = _statvfs_result(
            bytes_available=20_480,
            inodes_available=7,
            fragment_size=4_096,
            bytes_free=40_960,
            inodes_free=70,
        )
        assert available_capacity(stats) == (20_480, 7)

    def test_capacity__shared_filesystem_sums_once_without_grouping_margin(self) -> None:
        statvfs_calls: list[Path] = []

        def statvfs(path: Path) -> os.statvfs_result:
            statvfs_calls.append(path)
            return _statvfs_result(bytes_available=149, inodes_available=15)

        result = check_capacity(
            requirements=[
                Requirement(path=Path("/corpus"), bytes=100, inodes=10),
                Requirement(path=Path("/artifacts"), bytes=50, inodes=5),
            ],
            stat_path=lambda _path: _stat_result(7),
            statvfs=statvfs,
            margin=0,
        )

        assert result.ok is False
        assert len(result.filesystems) == 1
        assert result.filesystems[0].required_bytes == 150
        assert result.filesystems[0].required_inodes == 15
        assert len(statvfs_calls) == 1

    def test_capacity__applies_one_exact_upward_rounded_margin_per_filesystem(self) -> None:
        result = check_capacity(
            requirements=[Requirement(path=Path("/corpus"), bytes=1, inodes=1)],
            stat_path=lambda _path: _stat_result(7),
            statvfs=lambda _path: _statvfs_result(bytes_available=2, inodes_available=2),
        )

        assert result.ok is True
        assert result.filesystems[0].required_bytes == 2
        assert result.filesystems[0].required_inodes == 2
        assert result.filesystems[0].margin_fraction == 0.25

    def test_capacity__rounded_public_margin_cannot_mask_an_under_reserve(self) -> None:
        base_bytes = 10**21
        under_margin = Fraction(1, 4) - Fraction(1, 10**20)
        with pytest.raises(ValueError, match="zero or the exact binding margin"):
            check_capacity(
                requirements=[Requirement(path=Path("/corpus"), bytes=base_bytes, inodes=0)],
                stat_path=lambda _path: _stat_result(7),
                statvfs=lambda _path: _statvfs_result(
                    bytes_available=1_250_000_000_000_000_000_000 - 10,
                    inodes_available=0,
                ),
                margin=under_margin,
            )

    def test_capacity__distinct_filesystems_are_checked_once_and_sorted_publicly(self) -> None:
        calls: list[Path] = []

        def stat_path(path: Path) -> os.stat_result:
            return _stat_result(2 if path.name == "small" else 1)

        def statvfs(path: Path) -> os.statvfs_result:
            calls.append(path)
            return _statvfs_result(bytes_available=1_000, inodes_available=1_000)

        result = check_capacity(
            requirements=[
                Requirement(path=Path("/synthetic/small"), bytes=10, inodes=1),
                Requirement(path=Path("/synthetic/large"), bytes=100, inodes=2),
            ],
            stat_path=stat_path,
            statvfs=statvfs,
            margin=0,
        )

        assert result.ok is True
        assert len(calls) == 2
        assert [item.required_bytes for item in result.filesystems] == [10, 100]

    @pytest.mark.parametrize(
        ("available_bytes", "available_inodes", "passed"),
        [(125, 13, True), (124, 13, False), (125, 12, False)],
    )
    def test_capacity__exact_equality_and_one_unit_shortages(
        self, available_bytes: int, available_inodes: int, passed: bool
    ) -> None:
        result = check_capacity(
            requirements=[Requirement(path=Path("/corpus"), bytes=100, inodes=10)],
            stat_path=lambda _path: _stat_result(7),
            statvfs=lambda _path: _statvfs_result(
                bytes_available=available_bytes,
                inodes_available=available_inodes,
            ),
        )
        assert result.ok is passed
        assert result.filesystems[0].passed is passed

    def test_capacity__rejects_empty_or_invalid_probes_without_path_disclosure(self) -> None:
        with pytest.raises(ResourcePreflightError, match="at least one"):
            check_capacity(requirements=[])

        def failing_stat(_path: Path) -> os.stat_result:
            raise OSError("/private/operator/path")

        with pytest.raises(ResourcePreflightError, match="capacity probe failed") as caught:
            check_capacity(
                requirements=[Requirement(path=Path("/synthetic"), bytes=1, inodes=1)],
                stat_path=failing_stat,
            )
        assert "/private" not in str(caught.value)


class TestMountInfo:
    def test_mountinfo__decodes_kernel_escapes_and_ignores_unknown_optional_fields(self) -> None:
        line = _mount_line(
            mount_point=r"/data\040set\011tab\134slash",
            optional="shared:1 future:synthetic",
        )
        mount = parse_mountinfo(line)[0]
        assert mount.mount_point == Path("/data set\ttab\\slash")
        assert mount.optional_fields == ("shared:1", "future:synthetic")

    @pytest.mark.parametrize(
        "line",
        [
            "",
            "36 25 8:1 / /data rw ext4 /dev/synthetic rw",
            "bad 25 8:1 / /data rw - ext4 /dev/synthetic rw",
            "36 25 8:1 / relative rw - ext4 /dev/synthetic rw",
            r"36 25 8:1 / /bad\999path rw - ext4 /dev/synthetic rw",
            r"36 25 8:1 / /bad\04path rw - ext4 /dev/synthetic rw",
        ],
    )
    def test_mountinfo__rejects_malformed_records(self, line: str) -> None:
        with pytest.raises(ResourcePreflightError, match="mountinfo"):
            parse_mountinfo(line)

    def test_mount_selection__uses_component_aware_longest_containing_mount(self) -> None:
        mounts = parse_mountinfo(
            "\n".join(
                [
                    _mount_line(mount_id=1, parent_id=1, mount_point="/"),
                    _mount_line(mount_id=2, parent_id=1, mount_point="/data"),
                    _mount_line(mount_id=3, parent_id=1, mount_point="/database"),
                    _mount_line(mount_id=4, parent_id=2, mount_point="/data/nested"),
                ]
            )
        )
        assert select_mount(Path("/data/nested/file"), mounts).mount_id == 4
        assert select_mount(Path("/database/file"), mounts).mount_id == 3
        assert select_mount(Path("/data-other/file"), mounts).mount_id == 1
        assert select_mount(Path("/data/../database/file"), mounts).mount_id == 3

    def test_mount_selection__chooses_topmost_stacked_mount_or_refuses_ambiguity(self) -> None:
        stacked = parse_mountinfo(
            "\n".join(
                [
                    _mount_line(mount_id=1, parent_id=1, mount_point="/"),
                    _mount_line(mount_id=10, parent_id=1, mount_point="/data"),
                    _mount_line(mount_id=11, parent_id=10, mount_point="/data"),
                ]
            )
        )
        assert select_mount(Path("/data/file"), stacked).mount_id == 11

        ambiguous = parse_mountinfo(
            "\n".join(
                [
                    _mount_line(mount_id=1, parent_id=1, mount_point="/"),
                    _mount_line(mount_id=10, parent_id=1, mount_point="/data"),
                    _mount_line(mount_id=11, parent_id=1, mount_point="/data"),
                ]
            )
        )
        with pytest.raises(ResourcePreflightError, match="ambiguous"):
            select_mount(Path("/data/file"), ambiguous)

    def test_mount_selection__resolves_existing_symlink_parents(self, tmp_path: Path) -> None:
        destination = tmp_path / "destination"
        destination.mkdir()
        alias = tmp_path / "alias"
        alias.symlink_to(destination, target_is_directory=True)
        mounts = parse_mountinfo(
            "\n".join(
                [
                    _mount_line(mount_id=1, parent_id=1, mount_point="/"),
                    _mount_line(
                        mount_id=2,
                        parent_id=1,
                        mount_point=destination.as_posix(),
                    ),
                ]
            )
        )
        assert select_mount(alias / "future-file", mounts).mount_id == 2

    def test_mount_selection__ignores_descendants_hidden_by_ancestor_overmount(self) -> None:
        mounts = parse_mountinfo(
            "\n".join(
                [
                    _mount_line(mount_id=1, parent_id=1, mount_point="/"),
                    _mount_line(mount_id=10, parent_id=1, mount_point="/data"),
                    _mount_line(
                        mount_id=12,
                        parent_id=10,
                        mount_point="/data/nested",
                        filesystem="btrfs",
                    ),
                    _mount_line(
                        mount_id=11,
                        parent_id=10,
                        mount_point="/data",
                        filesystem="nfs",
                    ),
                ]
            )
        )
        selected = select_mount(Path("/data/nested/file"), mounts)
        assert selected.mount_id == 11
        assert selected.filesystem == "nfs"

    def test_mount_selection__requires_complete_root_visibility(self) -> None:
        with pytest.raises(ResourcePreflightError, match="root mount"):
            select_mount(Path("/data/file"), [_mount(mount_id=10, mount_point="/data")])

    def test_mount_selection__refuses_unresolvable_symlink_loop(self, tmp_path: Path) -> None:
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.symlink_to(second)
        second.symlink_to(first)
        with pytest.raises(ResourcePreflightError, match="resolve the target path"):
            select_mount(first / "future-file", [_mount(mount_id=1, mount_point="/")])

    def test_public_mount_projection__keeps_only_complete_value_free_allowlist(self) -> None:
        complete = project_mount_flags(
            _mount(mount_options="rw,noatime,relatime,nodiratime,lazytime,sync,dirsync")
        )
        assert complete.complete is True
        assert complete.flags == (
            "rw",
            "relatime",
            "noatime",
            "nodiratime",
            "lazytime",
            "sync",
            "dirsync",
        )

        for options in (
            "relatime",
            "rw,nosuid",
            "rw,subvol=/private",
            "ro,rw",
            "rw,rw",
        ):
            projection = project_mount_flags(_mount(mount_options=options))
            assert projection.complete is False
            assert projection.flags in (("rw",), ("ro", "rw"), ("relatime",))
            assert "private" not in repr(projection)

    def test_public_mount_projection__keeps_superblock_options_private(self) -> None:
        mount = _mount(super_options="rw,subvol=/private")
        projection = project_mount_flags(mount)
        assert projection == MountFlagProjection(flags=("rw", "relatime"), complete=True)
        assert is_binding_filesystem(mount, projection) is True
        assert "private" not in repr(projection)

    @pytest.mark.parametrize("filesystem", sorted(ALLOWED_BINDING_FILESYSTEMS))
    def test_binding_filesystem__accepts_local_disk_types(self, filesystem: str) -> None:
        mount = _mount(filesystem=filesystem)
        assert is_binding_filesystem(mount, project_mount_flags(mount)) is True

    @pytest.mark.parametrize(
        "filesystem",
        ["tmpfs", "ramfs", "overlay", "fuse.sshfs", *sorted(REJECTED_NETWORK_FILESYSTEMS)],
    )
    def test_binding_filesystem__rejects_memory_overlay_network_and_unknown(
        self, filesystem: str
    ) -> None:
        mount = _mount(filesystem=filesystem)
        assert is_binding_filesystem(mount, project_mount_flags(mount)) is False


class TestReferenceEnvironment:
    def test_reference_comparison__is_exact_with_order_independent_mount_flags(self) -> None:
        accepted = _reference_environment()
        observed = _reference_environment(mount_flags=("relatime", "rw"))
        comparison = compare_reference_environment(
            observed, accepted, mount_projection=_binding_projection()
        )
        assert comparison.binding is True
        assert comparison.exact_match is True
        assert comparison.mismatched_fields == ()

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("cpu_architecture", "aarch64"),
            ("cpu_model", "Other Synthetic CPU"),
            ("logical_cpu_count", 16),
            ("ram_bytes", 64 * 1024**3),
            ("storage_class", "local-hdd"),
            ("filesystem", "xfs"),
            ("python_version", "3.14.7"),
            ("kernel_version", "7.0.1-test"),
        ],
    )
    def test_reference_comparison__reports_field_names_without_values(
        self, field: str, value: object
    ) -> None:
        comparison = compare_reference_environment(
            _reference_environment(**{field: value}),
            _reference_environment(),
            mount_projection=_binding_projection(),
        )
        assert comparison.binding is False
        assert comparison.mismatched_fields == (field,)
        assert str(value) not in repr(comparison.mismatched_fields)

    def test_binding_environment__rejects_tmpfs_but_keeps_it_diagnostic(self) -> None:
        observed = _reference_environment(filesystem="tmpfs", storage_class="memory")
        comparison = compare_reference_environment(
            observed,
            _reference_environment(),
            mount_projection=_binding_projection(),
        )
        assert observed.filesystem == "tmpfs"
        assert comparison.binding is False
        assert comparison.binding_filesystem is False

    def test_binding_environment__requires_16_gib_even_for_exact_reference(self) -> None:
        eight_gib = _reference_environment(ram_bytes=8 * 1024**3)
        comparison = compare_reference_environment(
            eight_gib, eight_gib, mount_projection=_binding_projection()
        )
        assert comparison.exact_match is True
        assert comparison.ram_requirement_met is False
        assert comparison.binding is False

    def test_binding_environment__rejects_incomplete_public_mount_projection(self) -> None:
        accepted = _reference_environment()
        comparison = compare_reference_environment(
            accepted,
            accepted,
            mount_projection=project_mount_flags(_mount(mount_options="rw,subvol=/private")),
        )
        assert comparison.exact_match is True
        assert comparison.binding_filesystem is False
        assert comparison.binding is False

    def test_binding_environment__rejects_projection_that_differs_from_public_record(self) -> None:
        observed = _reference_environment(mount_flags=("rw", "noatime"))
        comparison = compare_reference_environment(
            observed,
            observed,
            mount_projection=_binding_projection(),
        )
        assert comparison.exact_match is True
        assert comparison.binding_filesystem is False
        assert comparison.binding is False

    def test_reference_comparison__reports_mount_flag_mismatch_order_independently(self) -> None:
        observed = _reference_environment(mount_flags=("noatime", "rw"))
        comparison = compare_reference_environment(
            observed,
            _reference_environment(),
            mount_projection=_binding_projection(options="rw,noatime"),
        )
        assert comparison.mismatched_fields == ("mount_flags",)
        assert comparison.binding is False

    def test_preflight_evidence__combines_identifier_free_capacity_and_reference_results(
        self,
    ) -> None:
        capacity = check_capacity(
            requirements=[Requirement(path=Path("/corpus"), bytes=100, inodes=10)],
            stat_path=lambda _path: _stat_result(7),
            statvfs=lambda _path: _statvfs_result(bytes_available=125, inodes_available=13),
        )
        comparison = compare_reference_environment(
            _reference_environment(),
            _reference_environment(),
            mount_projection=_binding_projection(),
        )
        preflight = build_preflight_evidence(capacity, comparison)
        assert preflight.passed is True
        assert preflight.capacity_margin_met is True
        assert set(FilesystemCapacityEvidence.model_fields) == {
            "required_bytes",
            "available_bytes",
            "required_inodes",
            "available_inodes",
            "margin_fraction",
            "passed",
        }

    def test_preflight_evidence__zero_margin_capacity_cannot_be_binding(self) -> None:
        capacity = check_capacity(
            requirements=[Requirement(path=Path("/corpus"), bytes=100, inodes=10)],
            stat_path=lambda _path: _stat_result(7),
            statvfs=lambda _path: _statvfs_result(bytes_available=100, inodes_available=10),
            margin=0,
        )
        comparison = compare_reference_environment(
            _reference_environment(),
            _reference_environment(),
            mount_projection=_binding_projection(),
        )
        preflight = build_preflight_evidence(capacity, comparison)
        assert capacity.ok is True
        assert preflight.capacity_margin_met is False
        assert preflight.passed is False


class TestSwap:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [("Name:\tchild\nVmSwap:\t0 kB\n", 0), ("VmSwap: 123 kB\n", 123 * 1024)],
    )
    def test_vm_swap__parses_exact_kibibyte_field(self, status: str, expected: int) -> None:
        assert parse_vm_swap(status) == expected

    @pytest.mark.parametrize(
        "status",
        [
            "Name: child\n",
            "VmSwap: 0 kB\nVmSwap: 0 kB\n",
            "VmSwap: -1 kB\n",
            "VmSwap: unknown kB\n",
            "VmSwap: 1 MB\n",
            "VmSwap: 1 kB extra\n",
        ],
    )
    def test_vm_swap__missing_duplicate_or_malformed_is_unavailable(self, status: str) -> None:
        with pytest.raises(ResourcePreflightError, match="VmSwap unavailable"):
            parse_vm_swap(status)

    def test_child_swap__tracks_peak_and_never_converts_unavailable_to_zero(self) -> None:
        assert max_child_vm_swap(["VmSwap: 0 kB\n", "VmSwap: 2 kB\n"]) == 2 * 1024
        with pytest.raises(ResourcePreflightError, match="sample"):
            max_child_vm_swap([])
        with pytest.raises(ResourcePreflightError, match="VmSwap unavailable"):
            max_child_vm_swap(["Name: child\n"])

    def test_vmstat__parses_swap_counters_and_ignores_unrelated_fields(self) -> None:
        counters = parse_vmstat_swap("nr_free_pages 10\npswpin 11\npswpout 12\n")
        assert counters == SwapCounters(pswpin=11, pswpout=12)

    @pytest.mark.parametrize(
        "vmstat",
        [
            "pswpin 1\n",
            "pswpin 1\npswpin 2\npswpout 0\n",
            "pswpin bad\npswpout 0\n",
            "pswpin -1\npswpout 0\n",
            "pswpin 1 extra\npswpout 0\n",
        ],
    )
    def test_vmstat__missing_duplicate_or_malformed_is_unavailable(self, vmstat: str) -> None:
        with pytest.raises(ResourcePreflightError, match="vmstat swap counters unavailable"):
            parse_vmstat_swap(vmstat)

    def test_swap_counter_delta__is_diagnostic_and_never_clamps_regression(self) -> None:
        assert swap_counter_delta(
            SwapCounters(pswpin=10, pswpout=20), SwapCounters(pswpin=13, pswpout=25)
        ) == SwapCounters(pswpin=3, pswpout=5)
        assert swap_counter_delta(
            SwapCounters(pswpin=10, pswpout=20), SwapCounters(pswpin=10, pswpout=20)
        ) == SwapCounters(pswpin=0, pswpout=0)
        with pytest.raises(ResourcePreflightError, match="delta unavailable"):
            swap_counter_delta(
                SwapCounters(pswpin=10, pswpout=20), SwapCounters(pswpin=9, pswpout=20)
            )

    def test_public_results__contain_no_path_device_or_mount_source_fields(self) -> None:
        capacity = check_capacity(
            requirements=[Requirement(path=Path("/synthetic"), bytes=1, inodes=1)],
            stat_path=lambda _path: _stat_result(99),
            statvfs=lambda _path: _statvfs_result(bytes_available=2, inodes_available=2),
        )
        public = capacity.filesystems[0].model_dump()
        assert {"path", "device", "st_dev", "mount_source"}.isdisjoint(public)
        assert cast("int", public["required_bytes"]) == 2
