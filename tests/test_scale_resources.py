"""NFR-001 Linux resource-preflight contracts for scale qualification."""

import os
from fractions import Fraction
from inspect import signature
from pathlib import Path
from typing import cast, get_type_hints

import pytest

from docmend.scale_corpus import ScaleCorpusSummary, recipe_counts, summarize_scale_corpus
from docmend.scale_evidence import FilesystemCapacityEvidence, ReferenceEnvironment
from docmend.scale_resources import (
    ALLOWED_BINDING_FILESYSTEMS,
    INVENTORY_BYTES_PER_INPUT,
    MANIFEST_BYTES_PER_ACTION,
    PLAN_BYTES_PER_INPUT,
    QUALIFICATION_BASE_BYTES,
    QUALIFICATION_NONCORPUS_INODES,
    REJECTED_NETWORK_FILESYSTEMS,
    REPORT_BYTES_PER_ACTION,
    STRUCTURED_LOG_BYTES_PER_INPUT_STAGE,
    SUPERVISOR_PRIVATE_BYTES_PER_FILE,
    SUPERVISOR_PRIVATE_FILES_PER_STAGE,
    VERIFY_BYTES_PER_INPUT,
    CapacityPlacement,
    MountFlagProjection,
    MountInfo,
    ReferenceObservation,
    ReferenceProbes,
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
    observe_reference_environment,
    parse_mountinfo,
    parse_vm_swap,
    parse_vmstat_swap,
    project_mount_flags,
    qualification_requirements,
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


def _capacity_placement(path: Path, *, fragment_size: int) -> CapacityPlacement:
    """Build a real identity hold with synthetic capacity geometry for arithmetic tests."""
    return CapacityPlacement(
        path=path,
        fragment_size=fragment_size,
        _fstatvfs=lambda _fd: _statvfs_result(
            bytes_available=fragment_size,
            inodes_available=1,
            fragment_size=fragment_size,
        ),
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
    device_major: int = 8,
    device_minor: int = 1,
    mount_point: str = "/data",
    mount_options: str = "rw,relatime",
    filesystem: str = "ext4",
    mount_source: str = "/dev/synthetic",
    optional: str = "shared:1",
    super_options: str = "rw",
) -> str:
    optional_field = f" {optional}" if optional else ""
    return (
        f"{mount_id} {parent_id} {device_major}:{device_minor} / "
        f"{mount_point} {mount_options}{optional_field} - {filesystem} "
        f"{mount_source} {super_options}"
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


class _FakeReferenceProbes:
    def __init__(self, workspace: Path, *, filesystem: str = "ext4") -> None:
        self.machine_value = "x86_64"
        self.python_version_value = "3.14.6"
        self.kernel_version_value = "7.0.0-test"
        self.logical_cpu_count_value: int | None = 8
        self.device = Path("/sys/dev/block/8:1")
        self.resolved_device = Path("/sys/devices/pci/block/sda")
        self.text: dict[Path, str] = {
            Path("/proc/self/mountinfo"): "\n".join(
                (
                    _mount_line(mount_id=1, parent_id=1, mount_point="/"),
                    _mount_line(
                        mount_id=2,
                        parent_id=1,
                        mount_point=workspace.as_posix(),
                        filesystem=filesystem,
                    ),
                )
            ),
            Path("/proc/cpuinfo"): "processor: 0\nmodel name: Synthetic CPU 9000\n",
            Path("/proc/meminfo"): "MemTotal:       33554432 kB\n",
            self.resolved_device / "queue" / "rotational": "0\n",
        }
        self.text_sequences: dict[Path, list[str]] = {}
        self.directories: dict[Path, tuple[str, ...]] = {self.device / "slaves": ()}
        self.directory_sequences: dict[Path, list[tuple[str, ...]]] = {}
        self.resolved: dict[Path, Path] = {self.device: self.resolved_device}
        self.btrfs_fsid = bytes.fromhex("11111111222233334444555555555555")
        self.btrfs_num_devices = 1
        self.btrfs_error: OSError | None = None
        self.btrfs_info_sequence: list[tuple[bytes, int]] = []
        if filesystem == "btrfs":
            devices = Path("/sys/fs/btrfs/11111111-2222-3333-4444-555555555555/devices")
            member = devices / "synthetic"
            self.directories[devices] = ("synthetic",)
            self.directories[member / "slaves"] = ()
            self.resolved[member] = self.resolved_device

    def read_text(self, path: Path) -> str:
        if sequence := self.text_sequences.get(path):
            return sequence.pop(0)
        try:
            return self.text[path]
        except KeyError as exc:
            raise OSError("synthetic missing telemetry") from exc

    def list_directory(self, path: Path) -> tuple[str, ...]:
        if sequence := self.directory_sequences.get(path):
            return sequence.pop(0)
        try:
            return self.directories[path]
        except KeyError as exc:
            raise FileNotFoundError("synthetic missing directory") from exc

    def resolve(self, path: Path) -> Path:
        return self.resolved.get(path, path)

    def statvfs(self, _path: Path) -> os.statvfs_result:
        return _statvfs_result(
            bytes_available=10**12,
            inodes_available=10**9,
            fragment_size=4_096,
        )

    def machine(self) -> str:
        return self.machine_value

    def python_version(self) -> str:
        return self.python_version_value

    def kernel_version(self) -> str:
        return self.kernel_version_value

    def logical_cpu_count(self) -> int | None:
        return self.logical_cpu_count_value

    def btrfs_filesystem_info(self, _path: Path) -> tuple[bytes, int]:
        if self.btrfs_error is not None:
            raise self.btrfs_error
        if self.btrfs_info_sequence:
            return self.btrfs_info_sequence.pop(0)
        return self.btrfs_fsid, self.btrfs_num_devices


def _anonymous_btrfs_probes(
    workspace: Path,
    rotational: tuple[str, str] = ("0", "0"),
) -> tuple[_FakeReferenceProbes, Path]:
    probes = _FakeReferenceProbes(workspace, filesystem="btrfs")
    probes.text[Path("/proc/self/mountinfo")] = "\n".join(
        (
            _mount_line(mount_id=1, parent_id=1, mount_point="/"),
            _mount_line(
                mount_id=2,
                parent_id=1,
                device_major=0,
                device_minor=36,
                mount_point=workspace.as_posix(),
                filesystem="btrfs",
                mount_source="none",
            ),
        )
    )
    probes.directories.clear()
    probes.resolved.clear()
    probes.btrfs_num_devices = 2

    fsid = "11111111-2222-3333-4444-555555555555"
    devices = Path("/sys/fs/btrfs") / fsid / "devices"
    probes.directories[devices] = ("dm-0", "dm-1")
    for index, (device_name, rotational_value) in enumerate(
        zip(("dm-0", "dm-1"), rotational, strict=True)
    ):
        device = devices / device_name
        leaf_name = f"nvme{index}n1"
        leaf = device / "slaves" / leaf_name
        resolved_leaf = Path(f"/sys/devices/pci/block/{leaf_name}")
        probes.resolved[device] = Path(f"/sys/devices/virtual/block/{device_name}")
        probes.directories[device / "slaves"] = (leaf_name,)
        probes.resolved[leaf] = resolved_leaf
        probes.directories[leaf / "slaves"] = ()
        probes.text[resolved_leaf / "queue" / "rotational"] = f"{rotational_value}\n"
    return probes, devices


def _qualification_summary(count: int, *, fragment_size: int) -> ScaleCorpusSummary:
    return ScaleCorpusSummary(
        count=count,
        file_bytes=123,
        allocated_bytes=fragment_size * count,
        fragment_size=fragment_size,
        largest_file_bytes=123,
        file_inodes=count,
        directory_inodes=3,
        recipe_counts=recipe_counts(count),
    )


class TestCapacity:
    def test_capacity_placement__has_runtime_resolvable_annotations(self) -> None:
        assert "fragment_size" in signature(CapacityPlacement).parameters
        assert get_type_hints(CapacityPlacement)["fragment_size"] is int

    def test_capacity_placement__closes_descriptor_when_probe_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opened: list[int] = []
        closed: list[int] = []
        real_open = os.open
        real_close = os.close

        def tracking_open(*args: object, **kwargs: object) -> int:
            fd = real_open(*args, **kwargs)  # pyright: ignore[reportArgumentType]
            opened.append(fd)
            return fd

        def tracking_close(fd: int) -> None:
            closed.append(fd)
            real_close(fd)

        monkeypatch.setattr(os, "open", tracking_open)
        monkeypatch.setattr(os, "close", tracking_close)

        def fail_probe(_fd: int) -> os.statvfs_result:
            raise RuntimeError("synthetic probe failure")

        with pytest.raises(ResourcePreflightError, match="validation failed"):
            CapacityPlacement(
                path=tmp_path,
                fragment_size=os.statvfs(tmp_path).f_frsize,
                _fstatvfs=fail_probe,
            )

        assert opened
        assert opened[-1] in closed

        def interrupt_probe(_fd: int) -> os.statvfs_result:
            raise KeyboardInterrupt

        closed.clear()
        with pytest.raises(KeyboardInterrupt):
            CapacityPlacement(
                path=tmp_path,
                fragment_size=os.statvfs(tmp_path).f_frsize,
                _fstatvfs=interrupt_probe,
            )

        assert opened[-1] in closed

    def test_capacity_placement__rejects_forged_fragment_size(self, tmp_path: Path) -> None:
        observed = os.statvfs(tmp_path).f_frsize
        forged = observed + 1

        with pytest.raises(ResourcePreflightError, match="fragment size"):
            CapacityPlacement(path=tmp_path, fragment_size=forged)

    def test_capacity_placement__rejects_path_replacement_after_identity_hold(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "placement"
        path.mkdir()
        fragment_size = os.statvfs(path).f_frsize
        placement = CapacityPlacement(path=path, fragment_size=fragment_size)
        summary = _qualification_summary(1, fragment_size=fragment_size)
        moved = tmp_path / "moved"
        path.rename(moved)
        path.mkdir()

        with pytest.raises(ResourcePreflightError, match="identity changed"):
            qualification_requirements(
                workspace=placement,
                corpus=placement,
                artifact=placement,
                supervisor=placement,
                summary=summary,
            )

    def test_capacity_check__rejects_path_replacement_after_requirements(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "placement"
        path.mkdir()
        fragment_size = os.statvfs(path).f_frsize
        placement = CapacityPlacement(path=path, fragment_size=fragment_size)
        requirements = qualification_requirements(
            workspace=placement,
            corpus=placement,
            artifact=placement,
            supervisor=placement,
            summary=_qualification_summary(1, fragment_size=fragment_size),
        )
        path.rename(tmp_path / "moved")
        path.mkdir()

        with pytest.raises(ResourcePreflightError, match="identity changed"):
            check_capacity(requirements)

    def test_capacity_placement__context_closes_the_held_identity(self, tmp_path: Path) -> None:
        fragment_size = os.statvfs(tmp_path).f_frsize

        with CapacityPlacement(path=tmp_path, fragment_size=fragment_size) as placement:
            assert placement.path == tmp_path

        with pytest.raises(ResourcePreflightError, match="closed"):
            placement.require_current_identity()

    @pytest.mark.parametrize("fragment_size", [0, -1, True, cast("int", 1.5)])
    def test_capacity_placement__rejects_invalid_fragment_size(
        self, tmp_path: Path, fragment_size: int
    ) -> None:
        with pytest.raises(ValueError, match="fragment_size must be a positive integer"):
            CapacityPlacement(path=tmp_path, fragment_size=fragment_size)

    def test_capacity_placement__requires_existing_absolute_real_directory(
        self, tmp_path: Path
    ) -> None:
        destination = tmp_path / "destination"
        destination.mkdir()
        alias = tmp_path / "alias"
        alias.symlink_to(destination, target_is_directory=True)

        for path in (Path("relative"), tmp_path / "missing", alias):
            with pytest.raises(ResourcePreflightError, match="real directory"):
                CapacityPlacement(path=path, fragment_size=4_096)

    def test_qualification_requirements__rejects_corpus_fragment_mismatch(
        self, tmp_path: Path
    ) -> None:
        paths = tuple(tmp_path / name for name in ("workspace", "corpus", "artifact", "supervisor"))
        for path in paths:
            path.mkdir()
        placements = tuple(
            CapacityPlacement(path=path, fragment_size=os.statvfs(path).f_frsize) for path in paths
        )
        summary = summarize_scale_corpus(1, fragment_size=placements[1].fragment_size + 1)

        with pytest.raises(ValueError, match="fragment size must match"):
            qualification_requirements(
                workspace=placements[0],
                corpus=placements[1],
                artifact=placements[2],
                supervisor=placements[3],
                summary=summary,
            )

    def test_qualification_requirements__uses_exact_independently_rounded_budget(
        self, tmp_path: Path
    ) -> None:
        paths = tuple(tmp_path / name for name in ("workspace", "corpus", "artifact", "supervisor"))
        for path in paths:
            path.mkdir()
        workspace, corpus, artifact, supervisor = (
            _capacity_placement(path, fragment_size=fragment)
            for path, fragment in zip(paths, (4_096, 8_192, 6_000, 7_000), strict=True)
        )
        summary = summarize_scale_corpus(40, fragment_size=corpus.fragment_size)

        requirements = qualification_requirements(
            workspace=workspace,
            corpus=corpus,
            artifact=artifact,
            supervisor=supervisor,
            summary=summary,
        )

        by_path = {requirement.path: requirement for requirement in requirements}
        assert len(by_path) == 4
        assert by_path[corpus.path].bytes == summary.allocated_bytes + allocated_bytes(
            summary.largest_file_bytes, corpus.fragment_size
        )
        assert by_path[corpus.path].inodes == summary.required_inodes + 1

        action_count = summary.recipe_counts.actions
        artifact_sizes = (
            INVENTORY_BYTES_PER_INPUT * summary.count,
            PLAN_BYTES_PER_INPUT * summary.count,
            REPORT_BYTES_PER_ACTION * action_count,
            MANIFEST_BYTES_PER_ACTION * action_count,
            VERIFY_BYTES_PER_INPUT * summary.count,
            *(STRUCTURED_LOG_BYTES_PER_INPUT_STAGE * summary.count for _ in range(4)),
        )
        atomic_staging = max(
            artifact_sizes[0], artifact_sizes[1], artifact_sizes[2], artifact_sizes[4]
        )
        assert by_path[artifact.path].bytes == sum(
            allocated_bytes(size, artifact.fragment_size)
            for size in (*artifact_sizes, atomic_staging)
        )
        assert by_path[artifact.path].inodes == 10
        assert by_path[supervisor.path].bytes == (
            4
            * SUPERVISOR_PRIVATE_FILES_PER_STAGE
            * allocated_bytes(SUPERVISOR_PRIVATE_BYTES_PER_FILE, supervisor.fragment_size)
        )
        assert by_path[supervisor.path].inodes == 16
        assert by_path[workspace.path].bytes == allocated_bytes(
            QUALIFICATION_BASE_BYTES, workspace.fragment_size
        )
        assert by_path[workspace.path].inodes == QUALIFICATION_NONCORPUS_INODES

    @pytest.mark.parametrize("count", [1, 40, 100_000, 1_000_000])
    def test_qualification_requirements__derives_variable_counts_from_summary(
        self, tmp_path: Path, count: int
    ) -> None:
        paths = tuple(tmp_path / name for name in ("workspace", "corpus", "artifact", "supervisor"))
        for path in paths:
            path.mkdir()
        fragment_size = os.statvfs(paths[0]).f_frsize
        placements = tuple(
            CapacityPlacement(path=path, fragment_size=fragment_size) for path in paths
        )
        summary = _qualification_summary(count, fragment_size=fragment_size)

        artifact = qualification_requirements(
            workspace=placements[0],
            corpus=placements[1],
            artifact=placements[2],
            supervisor=placements[3],
            summary=summary,
        )[1]

        action_count = recipe_counts(count).actions
        raw_sizes = (
            INVENTORY_BYTES_PER_INPUT * count,
            PLAN_BYTES_PER_INPUT * count,
            REPORT_BYTES_PER_ACTION * action_count,
            MANIFEST_BYTES_PER_ACTION * action_count,
            VERIFY_BYTES_PER_INPUT * count,
        )
        expected = sum(allocated_bytes(size, fragment_size) for size in raw_sizes)
        expected += 4 * allocated_bytes(STRUCTURED_LOG_BYTES_PER_INPUT_STAGE * count, fragment_size)
        expected += allocated_bytes(
            max(raw_sizes[0], raw_sizes[1], raw_sizes[2], raw_sizes[4]), fragment_size
        )
        assert artifact.bytes == expected

    def test_qualification_requirements__shared_filesystem_gets_one_exact_margin(
        self, tmp_path: Path
    ) -> None:
        paths = tuple(tmp_path / name for name in ("workspace", "corpus", "artifact", "supervisor"))
        for path in paths:
            path.mkdir()
        placements = tuple(
            CapacityPlacement(path=path, fragment_size=os.statvfs(path).f_frsize) for path in paths
        )
        requirements = qualification_requirements(
            workspace=placements[0],
            corpus=placements[1],
            artifact=placements[2],
            supervisor=placements[3],
            summary=_qualification_summary(40, fragment_size=placements[1].fragment_size),
        )
        statvfs_calls: list[Path] = []

        def statvfs(path: Path) -> os.statvfs_result:
            statvfs_calls.append(path)
            return _statvfs_result(bytes_available=10**12, inodes_available=10**9)

        result = check_capacity(
            requirements,
            stat_path=lambda _path: _stat_result(7),
            statvfs=statvfs,
        )

        assert len(statvfs_calls) == 1
        assert len(result.filesystems) == 1
        assert (
            result.filesystems[0].required_bytes
            == (sum(item.bytes for item in requirements) * 5 + 3) // 4
        )
        assert (
            result.filesystems[0].required_inodes
            == (sum(item.inodes for item in requirements) * 5 + 3) // 4
        )

    def test_qualification_requirements__distinct_filesystems_margin_each_aggregate(
        self, tmp_path: Path
    ) -> None:
        paths = tuple(tmp_path / name for name in ("workspace", "corpus", "artifact", "supervisor"))
        for path in paths:
            path.mkdir()
        placements = tuple(
            _capacity_placement(path, fragment_size=fragment)
            for path, fragment in zip(paths, (4_096, 8_192, 6_000, 7_000), strict=True)
        )
        requirements = qualification_requirements(
            workspace=placements[0],
            corpus=placements[1],
            artifact=placements[2],
            supervisor=placements[3],
            summary=_qualification_summary(40, fragment_size=8_192),
        )
        devices = {path: index for index, path in enumerate(paths, start=1)}

        result = check_capacity(
            requirements,
            stat_path=lambda path: _stat_result(devices[path]),
            statvfs=lambda _path: _statvfs_result(bytes_available=10**12, inodes_available=10**9),
        )

        assert len(result.filesystems) == 4
        assert sorted(item.required_bytes for item in result.filesystems) == sorted(
            (requirement.bytes * 5 + 3) // 4 for requirement in requirements
        )
        assert sorted(item.required_inodes for item in result.filesystems) == sorted(
            (requirement.inodes * 5 + 3) // 4 for requirement in requirements
        )

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
    @pytest.mark.parametrize("filesystem", sorted(ALLOWED_BINDING_FILESYSTEMS))
    def test_reference_observation__derives_public_local_ssd_environment(
        self, tmp_path: Path, filesystem: str
    ) -> None:
        probes = _FakeReferenceProbes(tmp_path, filesystem=filesystem)

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert isinstance(observed, ReferenceObservation)
        assert observed.fragment_size == 4_096
        assert observed.mount_projection == MountFlagProjection(
            flags=("rw", "relatime"), complete=True
        )
        assert observed.environment == _reference_environment(
            cpu_model="Synthetic CPU 9000", filesystem=filesystem
        )
        assert {"path", "device", "mount_source", "sysfs"}.isdisjoint(
            observed.environment.model_dump()
        )

    @pytest.mark.parametrize(
        ("rotational", "expected"),
        [(("0", "0"), "local-ssd"), (("1", "1"), "local-hdd"), (("0", "1"), "unknown")],
    )
    def test_reference_observation__traverses_all_dm_slave_leaves(
        self, tmp_path: Path, rotational: tuple[str, str], expected: str
    ) -> None:
        probes = _FakeReferenceProbes(tmp_path)
        probes.resolved[probes.device] = Path("/sys/devices/virtual/block/dm-0")
        probes.directories[probes.device / "slaves"] = ("sda", "sdb")
        probes.text.pop(probes.resolved_device / "queue" / "rotational")
        for name, value in zip(("sda", "sdb"), rotational, strict=True):
            slave = probes.device / "slaves" / name
            resolved = Path(f"/sys/devices/pci/block/{name}")
            probes.directories[slave / "slaves"] = ()
            probes.resolved[slave] = resolved
            probes.text[resolved / "queue" / "rotational"] = f"{value}\n"

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == expected

    @pytest.mark.parametrize(
        ("rotational", "expected"),
        [
            (("0", "0"), "local-ssd"),
            (("1", "1"), "local-hdd"),
            (("0", "1"), "unknown"),
        ],
    )
    def test_reference_observation__resolves_anonymous_multidevice_btrfs_leaves(
        self,
        tmp_path: Path,
        rotational: tuple[str, str],
        expected: str,
    ) -> None:
        probes, _devices = _anonymous_btrfs_probes(tmp_path, rotational)

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == expected

    def test_reference_observation__incomplete_btrfs_device_set_is_unknown(
        self, tmp_path: Path
    ) -> None:
        probes, devices = _anonymous_btrfs_probes(tmp_path)
        probes.directories[devices] = ("dm-0",)

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "unknown"

    def test_reference_observation__nil_btrfs_fsid_is_unknown(self, tmp_path: Path) -> None:
        probes = _FakeReferenceProbes(tmp_path, filesystem="btrfs")
        probes.btrfs_fsid = bytes(16)
        nil_devices = Path("/sys/fs/btrfs/00000000-0000-0000-0000-000000000000/devices")
        member = nil_devices / "synthetic"
        probes.directories[nil_devices] = ("synthetic",)
        probes.directories[member / "slaves"] = ()
        probes.resolved[member] = probes.resolved_device

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "unknown"

    def test_reference_observation__duplicate_btrfs_member_targets_are_unknown(
        self, tmp_path: Path
    ) -> None:
        probes, devices = _anonymous_btrfs_probes(tmp_path)
        probes.resolved[devices / "dm-1"] = probes.resolved[devices / "dm-0"]

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "unknown"

    def test_reference_observation__btrfs_topology_churn_is_unknown(self, tmp_path: Path) -> None:
        probes, _devices = _anonymous_btrfs_probes(tmp_path)
        probes.btrfs_info_sequence = [
            (probes.btrfs_fsid, probes.btrfs_num_devices),
            (bytes.fromhex("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), 2),
        ]

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "unknown"

    def test_reference_observation__btrfs_member_order_is_not_topology_churn(
        self, tmp_path: Path
    ) -> None:
        probes, devices = _anonymous_btrfs_probes(tmp_path)
        probes.directory_sequences[devices] = [
            ("dm-0", "dm-1"),
            ("dm-1", "dm-0"),
        ]

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "local-ssd"

    def test_reference_observation__btrfs_member_churn_is_unknown(self, tmp_path: Path) -> None:
        probes, devices = _anonymous_btrfs_probes(tmp_path)
        replacement = devices / "dm-2"
        leaf_name = "nvme2n1"
        leaf = replacement / "slaves" / leaf_name
        resolved_leaf = Path(f"/sys/devices/pci/block/{leaf_name}")
        probes.resolved[replacement] = Path("/sys/devices/virtual/block/dm-2")
        probes.directories[replacement / "slaves"] = (leaf_name,)
        probes.resolved[leaf] = resolved_leaf
        probes.directories[leaf / "slaves"] = ()
        probes.text[resolved_leaf / "queue" / "rotational"] = "0\n"
        probes.directory_sequences[devices] = [
            ("dm-0", "dm-1"),
            ("dm-0", "dm-2"),
        ]

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "unknown"

    def test_reference_observation__btrfs_leaf_identity_churn_is_unknown(
        self, tmp_path: Path
    ) -> None:
        probes, devices = _anonymous_btrfs_probes(tmp_path)
        member = devices / "dm-0"
        replacement_name = "nvme9n1"
        replacement = member / "slaves" / replacement_name
        resolved_replacement = Path(f"/sys/devices/pci/block/{replacement_name}")
        probes.resolved[replacement] = resolved_replacement
        probes.directories[replacement / "slaves"] = ()
        probes.text[resolved_replacement / "queue" / "rotational"] = "0\n"
        probes.directory_sequences[member / "slaves"] = [
            ("nvme0n1",),
            (replacement_name,),
        ]

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "unknown"

    def test_reference_observation__btrfs_leaf_order_is_not_topology_churn(
        self, tmp_path: Path
    ) -> None:
        probes, devices = _anonymous_btrfs_probes(tmp_path)
        member = devices / "dm-0"
        additional_name = "nvme2n1"
        additional = member / "slaves" / additional_name
        resolved_additional = Path(f"/sys/devices/pci/block/{additional_name}")
        probes.resolved[additional] = resolved_additional
        probes.directories[additional / "slaves"] = ()
        probes.text[resolved_additional / "queue" / "rotational"] = "0\n"
        probes.directory_sequences[member / "slaves"] = [
            ("nvme0n1", additional_name),
            (additional_name, "nvme0n1"),
        ]

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "local-ssd"

    def test_reference_observation__btrfs_leaf_rotational_churn_is_unknown(
        self, tmp_path: Path
    ) -> None:
        probes, _devices = _anonymous_btrfs_probes(tmp_path)
        rotational = Path("/sys/devices/pci/block/nvme1n1/queue/rotational")
        probes.text_sequences[rotational] = ["0\n", "1\n"]

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "unknown"

    @pytest.mark.parametrize(
        "failure",
        ["missing-directory", "broken-member", "missing-rotation", "unsafe-name"],
    )
    def test_reference_observation__incomplete_btrfs_telemetry_is_unknown(
        self, tmp_path: Path, failure: str
    ) -> None:
        probes, devices = _anonymous_btrfs_probes(tmp_path)
        if failure == "missing-directory":
            probes.directories.pop(devices)
        elif failure == "broken-member":
            probes.resolved.pop(devices / "dm-1")
        elif failure == "missing-rotation":
            probes.text.pop(Path("/sys/devices/pci/block/nvme1n1/queue/rotational"))
        else:
            probes.directories[devices] = ("dm-0", "../escape")

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "unknown"

    @pytest.mark.parametrize("failure", ["identity", "count", "ioctl"])
    def test_reference_observation__unprovable_btrfs_identity_is_unknown(
        self, tmp_path: Path, failure: str
    ) -> None:
        probes, _devices = _anonymous_btrfs_probes(tmp_path)
        if failure == "identity":
            probes.btrfs_fsid = b"short"
        elif failure == "count":
            probes.btrfs_num_devices = 0
        else:
            probes.btrfs_error = OSError("synthetic ioctl failure")

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "unknown"

    def test_reference_observation__uses_partition_parent_rotational_state(
        self, tmp_path: Path
    ) -> None:
        probes = _FakeReferenceProbes(tmp_path)
        partition = Path("/sys/devices/pci/block/sda/sda1")
        probes.directories.pop(probes.device / "slaves")
        probes.resolved[probes.device] = partition
        probes.text.pop(probes.resolved_device / "queue" / "rotational")
        probes.text[partition / "partition"] = "1\n"
        probes.text[partition.parent / "queue" / "rotational"] = "1\n"

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.storage_class == "local-hdd"

    @pytest.mark.parametrize(
        ("filesystem", "storage_class"),
        [
            ("tmpfs", "memory"),
            ("ramfs", "memory"),
            *((filesystem, "network") for filesystem in sorted(REJECTED_NETWORK_FILESYSTEMS)),
            ("fuse.sshfs", "network"),
            ("ceph", "network"),
            ("glusterfs", "network"),
            ("9p", "network"),
        ],
    )
    def test_reference_observation__classifies_memory_and_network_without_sysfs(
        self, tmp_path: Path, filesystem: str, storage_class: str
    ) -> None:
        probes = _FakeReferenceProbes(tmp_path, filesystem=filesystem)
        probes.directories.clear()
        probes.resolved.clear()
        probes.text = {
            path: value
            for path, value in probes.text.items()
            if not path.is_relative_to(Path("/sys"))
        }

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.filesystem == filesystem
        assert observed.environment.storage_class == storage_class

    def test_reference_observation__supports_linux_arm_cpu_model_fields(
        self, tmp_path: Path
    ) -> None:
        probes = _FakeReferenceProbes(tmp_path)
        probes.text[Path("/proc/cpuinfo")] = "processor: 0\nHardware: Synthetic ARM CPU\n"

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.cpu_model == "Synthetic ARM CPU"

    def test_reference_observation__unavailable_or_cyclic_rotation_is_unknown(
        self, tmp_path: Path
    ) -> None:
        probes = _FakeReferenceProbes(tmp_path)
        probes.directories.clear()
        probes.text.pop(probes.resolved_device / "queue" / "rotational")
        missing = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))
        assert missing.environment.storage_class == "unknown"

        probes = _FakeReferenceProbes(tmp_path)
        probes.directories[probes.device / "slaves"] = ("loop",)
        slave = probes.device / "slaves" / "loop"
        probes.resolved[slave] = probes.device
        probes.directories[slave / "slaves"] = ("loop",)
        cyclic = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))
        assert cyclic.environment.storage_class == "unknown"

    def test_reference_observation__forbidden_probe_labels_degrade_to_unknown(
        self, tmp_path: Path
    ) -> None:
        probes = _FakeReferenceProbes(tmp_path)
        probes.text[Path("/proc/cpuinfo")] = "model name: /private/cpu\n"
        probes.machine_value = "private\\architecture"
        probes.python_version_value = "secret=version"
        probes.kernel_version_value = "/private/kernel"

        observed = observe_reference_environment(tmp_path, probes=cast("ReferenceProbes", probes))

        assert observed.environment.cpu_architecture == "unknown"
        assert observed.environment.cpu_model == "unknown"
        assert observed.environment.python_version == "unknown"
        assert observed.environment.kernel_version == "unknown"
        assert "private" not in repr(observed.environment)

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
