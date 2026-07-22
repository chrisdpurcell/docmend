"""Linux resource preflight for DMR-08 qualification (NFR-001, OQ-039).

Paths, device numbers, mount sources, and raw options are private harness data.
This module reduces them to the identifier-free capacity and reference verdicts
defined in :mod:`docmend.scale_evidence`; only those reduced records may enter
public qualification evidence.

The external grammars follow Linux ``proc_pid_mountinfo(5)``, ``statvfs(3)``,
``proc_pid_status(5)``, and ``proc_vmstat(5)``. Unknown mountinfo optional
fields are intentionally tolerated; unavailable binding measurements are not.
"""

import fcntl
import os
import platform
import re
import stat
import struct
import weakref
from collections.abc import Callable, Iterable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Literal, Protocol, cast
from uuid import UUID

from docmend.scale_evidence import (
    BINDING_CAPACITY_MARGIN,
    FilesystemCapacityEvidence,
    MountFlag,
    PreflightEvidence,
    ReferenceEnvironment,
    StorageClass,
)

if TYPE_CHECKING:
    from docmend.scale_corpus import ScaleCorpusSummary

ALLOWED_BINDING_FILESYSTEMS = frozenset({"ext4", "xfs", "btrfs"})
REJECTED_NETWORK_FILESYSTEMS = frozenset(
    {"9p", "ceph", "cifs", "fuse.sshfs", "glusterfs", "nfs", "nfs4", "smb3"}
)
MIN_BINDING_RAM_BYTES = 16 * 1024**3
# Linux MemTotal is usable RAM after kernel reservations, so it can vary by one
# base page without a machine-capacity change. Wider deltas remain mismatches.
_RAM_EQUIVALENCE_BYTES = os.sysconf("SC_PAGE_SIZE")
QUALIFICATION_BASE_BYTES = 256 * 1024 * 1024
INVENTORY_BYTES_PER_INPUT = 2_048
PLAN_BYTES_PER_INPUT = 4_096
REPORT_BYTES_PER_ACTION = 2_048
MANIFEST_BYTES_PER_ACTION = 8_192
VERIFY_BYTES_PER_INPUT = 1_024
STRUCTURED_LOG_BYTES_PER_INPUT_STAGE = 4_096
SUPERVISOR_PRIVATE_BYTES_PER_FILE = 2 * 1024 * 1024
SUPERVISOR_PRIVATE_FILES_PER_STAGE = 4
# A synthetic verify finding currently occupies 84 bytes. The next power-of-two
# coefficient keeps the capacity contract derived from the expected-finding
# count while leaving bounded room for public wording changes.
VERIFY_STDOUT_BYTES_PER_FINDING = 128
QUALIFICATION_NONCORPUS_INODES = 64
_QUALIFICATION_STAGE_COUNT = 4

PUBLIC_MOUNT_FLAGS: tuple[MountFlag, ...] = (
    "ro",
    "rw",
    "relatime",
    "noatime",
    "nodiratime",
    "lazytime",
    "sync",
    "dirsync",
)
_PUBLIC_MOUNT_FLAG_SET = frozenset(PUBLIC_MOUNT_FLAGS)
_BINDING_CAPACITY_MARGIN_FRACTION = Fraction(str(BINDING_CAPACITY_MARGIN))
_ALLOWED_CAPACITY_MARGINS = frozenset({Fraction(0), _BINDING_CAPACITY_MARGIN_FRACTION})

# Linux UAPI pads ``btrfs_ioctl_fs_info_args`` to exactly 1 KiB; the `_IOR`
# request encodes that size, so the request number and buffer must stay paired.
_BTRFS_FS_INFO_SIZE = 1_024
_BTRFS_IOC_FS_INFO = 0x8400941F

type ReferenceField = Literal[
    "operating_system",
    "cpu_architecture",
    "cpu_model",
    "logical_cpu_count",
    "ram_bytes",
    "storage_class",
    "filesystem",
    "mount_flags",
    "python_version",
    "kernel_version",
]
_REFERENCE_FIELDS: tuple[ReferenceField, ...] = (
    "operating_system",
    "cpu_architecture",
    "cpu_model",
    "logical_cpu_count",
    "ram_bytes",
    "storage_class",
    "filesystem",
    "mount_flags",
    "python_version",
    "kernel_version",
)

type StatPath = Callable[[Path], os.stat_result]
type StatVfs = Callable[[Path], os.statvfs_result]
type FstatVfs = Callable[[int], os.statvfs_result]
type FilesystemTypeProbe = Callable[[Path], str]


class ReferenceProbes(Protocol):
    """Supply the private Linux and platform observations used for reference capture."""

    def read_text(self, path: Path) -> str: ...

    def list_directory(self, path: Path) -> tuple[str, ...]: ...

    def resolve(self, path: Path) -> Path: ...

    def statvfs(self, path: Path) -> os.statvfs_result: ...

    def machine(self) -> str: ...

    def python_version(self) -> str: ...

    def kernel_version(self) -> str: ...

    def logical_cpu_count(self) -> int | None: ...

    def btrfs_filesystem_info(self, path: Path) -> tuple[bytes, int]: ...


@dataclass(frozen=True, slots=True)
class _DefaultReferenceProbes:
    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def list_directory(self, path: Path) -> tuple[str, ...]:
        with os.scandir(path) as entries:
            return tuple(sorted(entry.name for entry in entries))

    def resolve(self, path: Path) -> Path:
        return path.resolve(strict=True)

    def statvfs(self, path: Path) -> os.statvfs_result:
        return os.statvfs(path)

    def machine(self) -> str:
        return platform.machine()

    def python_version(self) -> str:
        return platform.python_version()

    def kernel_version(self) -> str:
        return platform.release()

    def logical_cpu_count(self) -> int | None:
        return os.cpu_count()

    def btrfs_filesystem_info(self, path: Path) -> tuple[bytes, int]:
        proc_fd_parent = Path("/proc/self/fd")
        if (
            path.parent == proc_fd_parent
            and path.name.isascii()
            and path.name.isdecimal()
            and path.name == str(int(path.name, 10))
        ):
            # Reference capture supplies a descriptor-held workspace through
            # procfs. Duplicate that descriptor: O_NOFOLLOW rejects the procfs
            # link, while reopening its resolved pathname would discard the hold.
            fd = os.dup(int(path.name, 10))
            try:
                if not stat.S_ISDIR(os.fstat(fd).st_mode):
                    raise NotADirectoryError(path)
            except BaseException:
                os.close(fd)
                raise
        else:
            fd = os.open(
                path,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            )
        try:
            payload = bytearray(_BTRFS_FS_INFO_SIZE)
            fcntl.ioctl(fd, _BTRFS_IOC_FS_INFO, payload, True)
        finally:
            os.close(fd)
        (_max_device_id, num_devices) = struct.unpack_from("=QQ", payload)
        return bytes(payload[16:32]), num_devices


_DEFAULT_REFERENCE_PROBES = _DefaultReferenceProbes()


class ResourcePreflightError(Exception):
    """Required Linux resource telemetry is missing, malformed, or ambiguous."""


class _Finalizer(Protocol):
    """Runtime-safe structural surface used from ``weakref.finalize``."""

    @property
    def alive(self) -> bool: ...

    def __call__(self) -> object | None: ...


@dataclass(frozen=True, slots=True)
class Requirement:
    """One private destination's pre-margin physical allocation estimate."""

    path: Path
    bytes: int
    inodes: int
    placement: CapacityPlacement | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.bytes) is not int or self.bytes < 0:
            raise ValueError("requirement bytes must be a non-negative integer")
        if type(self.inodes) is not int or self.inodes < 0:
            raise ValueError("requirement inodes must be a non-negative integer")
        if self.placement is not None and self.placement.path != self.path:
            raise ValueError("requirement path must match its held capacity placement")


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CapacityPlacement:
    """Hold one real probe-directory identity and its observed fragment size."""

    path: Path
    fragment_size: int
    _fstatvfs: InitVar[FstatVfs] = os.fstatvfs
    _directory_fd: int = field(init=False, repr=False, compare=False)
    _finalizer: _Finalizer = field(init=False, repr=False, compare=False)

    def __post_init__(self, _fstatvfs: FstatVfs) -> None:
        if type(self.fragment_size) is not int or self.fragment_size <= 0:
            raise ValueError("fragment_size must be a positive integer")
        if not self.path.is_absolute():
            raise ResourcePreflightError("capacity placement must be an absolute real directory")
        try:
            initial = os.lstat(self.path)
            resolved = self.path.resolve(strict=True)
            fd = os.open(
                self.path,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            )
        except OSError as exc:
            raise ResourcePreflightError(
                "capacity placement must be an existing real directory"
            ) from exc
        finalizer: _Finalizer | None = None
        adopted = False
        try:
            descriptor = os.fstat(fd)
            current = os.lstat(self.path)
            current_resolved = self.path.resolve(strict=True)
            capacity = _fstatvfs(fd)
            identities = {
                (initial.st_dev, initial.st_ino),
                (descriptor.st_dev, descriptor.st_ino),
                (current.st_dev, current.st_ino),
            }
            if (
                len(identities) != 1
                or not stat.S_ISDIR(descriptor.st_mode)
                or stat.S_ISLNK(initial.st_mode)
                or stat.S_ISLNK(current.st_mode)
                or resolved != self.path
                or current_resolved != self.path
            ):
                raise ResourcePreflightError(
                    "capacity placement must retain one real directory identity"
                )
            if capacity.f_frsize <= 0 or capacity.f_frsize != self.fragment_size:
                raise ResourcePreflightError(
                    "capacity placement fragment size must match held-directory statvfs"
                )
            finalizer = weakref.finalize(self, os.close, fd)
            object.__setattr__(self, "_directory_fd", fd)
            object.__setattr__(self, "_finalizer", finalizer)
            adopted = True
        except ResourcePreflightError:
            raise
        except Exception as exc:
            raise ResourcePreflightError("capacity placement validation failed") from exc
        finally:
            if not adopted:
                if finalizer is None:
                    os.close(fd)
                else:
                    finalizer()

    def __enter__(self) -> CapacityPlacement:
        self.require_current_identity()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Release the held directory identity; repeated closes are harmless."""
        self._finalizer()

    def require_current_identity(self) -> os.stat_result:
        """Return held identity only while the original pathname still names it."""
        if not self._finalizer.alive:
            raise ResourcePreflightError("capacity placement identity is closed")
        try:
            descriptor = os.fstat(self._directory_fd)
            current = os.lstat(self.path)
            resolved = self.path.resolve(strict=True)
        except OSError as exc:
            raise ResourcePreflightError(
                "capacity placement identity changed after validation"
            ) from exc
        if (
            (descriptor.st_dev, descriptor.st_ino) != (current.st_dev, current.st_ino)
            or not stat.S_ISDIR(descriptor.st_mode)
            or stat.S_ISLNK(current.st_mode)
            or resolved != self.path
        ):
            raise ResourcePreflightError("capacity placement identity changed after validation")
        return descriptor

    def capacity_stats(self) -> os.statvfs_result:
        """Read capacity through the held descriptor and recheck its fragment contract."""
        self.require_current_identity()
        try:
            capacity = os.fstatvfs(self._directory_fd)
        except OSError as exc:
            raise ResourcePreflightError("held capacity probe failed") from exc
        if capacity.f_frsize <= 0 or capacity.f_frsize != self.fragment_size:
            raise ResourcePreflightError("held capacity fragment size changed")
        return capacity


@dataclass(frozen=True, slots=True)
class CapacityCheck:
    """Identifier-free public capacity results after private device grouping."""

    ok: bool
    filesystems: tuple[FilesystemCapacityEvidence, ...]


@dataclass(frozen=True, slots=True)
class MountInfo:
    """One private ``/proc/self/mountinfo`` record."""

    mount_id: int
    parent_id: int
    device_major: int
    device_minor: int
    root: Path
    mount_point: Path
    mount_options: tuple[str, ...]
    optional_fields: tuple[str, ...]
    filesystem: str
    mount_source: str
    super_options: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MountFlagProjection:
    """The finite public flag subset plus whether any private option was omitted."""

    flags: tuple[MountFlag, ...]
    complete: bool


@dataclass(frozen=True, slots=True)
class ReferenceComparison:
    """Public-safe comparison: mismatch names are retained, observed values are not."""

    binding: bool
    exact_match: bool
    mismatched_fields: tuple[ReferenceField, ...]
    binding_filesystem: bool
    ram_requirement_met: bool


@dataclass(frozen=True, slots=True)
class ReferenceObservation:
    """Return only the public environment and reduced mount/capacity observations."""

    environment: ReferenceEnvironment
    mount_projection: MountFlagProjection
    fragment_size: int


@dataclass(frozen=True, slots=True)
class FilesystemRequirement:
    """One private followed-filesystem aggregate before capacity comparison."""

    device: int = field(repr=False, compare=False)
    probe: Path
    placement: CapacityPlacement | None
    required_bytes: int
    required_inodes: int


def allocated_bytes(size: int, fragment_size: int) -> int:
    """Round one logical file size to its physical fragment allocation."""
    if type(size) is not int or size < 0:
        raise ValueError("size must be a non-negative integer")
    if type(fragment_size) is not int or fragment_size <= 0:
        raise ValueError("fragment_size must be a positive integer")
    return ((size + fragment_size - 1) // fragment_size) * fragment_size


def available_capacity(stats: os.statvfs_result) -> tuple[int, int]:
    """Return bytes/inodes available to the unprivileged invoking user."""
    if stats.f_frsize <= 0 or stats.f_bavail < 0 or stats.f_favail < 0:
        raise ValueError("statvfs returned invalid unprivileged capacity")
    return stats.f_bavail * stats.f_frsize, stats.f_favail


def qualification_requirements(
    *,
    workspace: CapacityPlacement,
    corpus: CapacityPlacement,
    artifact: CapacityPlacement,
    supervisor: CapacityPlacement,
    summary: ScaleCorpusSummary,
) -> tuple[Requirement, ...]:
    """Return exact pre-margin qualification allocations for four destinations."""
    for placement in (workspace, corpus, artifact, supervisor):
        placement.require_current_identity()
    if corpus.fragment_size != summary.fragment_size:
        raise ValueError("corpus placement fragment size must match the corpus summary")

    action_count = summary.recipe_counts.actions
    inventory_size = INVENTORY_BYTES_PER_INPUT * summary.count
    plan_size = PLAN_BYTES_PER_INPUT * summary.count
    report_size = REPORT_BYTES_PER_ACTION * action_count
    manifest_size = MANIFEST_BYTES_PER_ACTION * action_count
    verify_size = VERIFY_BYTES_PER_INPUT * summary.count
    structured_log_size = STRUCTURED_LOG_BYTES_PER_INPUT_STAGE * summary.count
    atomic_staging_size = max(inventory_size, plan_size, report_size, verify_size)
    artifact_sizes = (
        inventory_size,
        plan_size,
        report_size,
        manifest_size,
        verify_size,
        *(structured_log_size for _ in range(_QUALIFICATION_STAGE_COUNT)),
        atomic_staging_size,
    )

    corpus_bytes = summary.allocated_bytes + allocated_bytes(
        summary.largest_file_bytes, corpus.fragment_size
    )
    artifact_bytes = sum(allocated_bytes(size, artifact.fragment_size) for size in artifact_sizes)
    supervisor_file_count = _QUALIFICATION_STAGE_COUNT * SUPERVISOR_PRIVATE_FILES_PER_STAGE
    verify_stdout_size = qualification_verify_stdout_allowance(
        expected_findings=summary.recipe_counts.skips
    )
    supervisor_sizes = (
        *(SUPERVISOR_PRIVATE_BYTES_PER_FILE for _ in range(supervisor_file_count - 1)),
        verify_stdout_size,
    )
    supervisor_bytes = sum(
        allocated_bytes(size, supervisor.fragment_size) for size in supervisor_sizes
    )
    workspace_bytes = allocated_bytes(QUALIFICATION_BASE_BYTES, workspace.fragment_size)

    return (
        Requirement(
            path=corpus.path,
            bytes=corpus_bytes,
            inodes=summary.required_inodes + 1,
            placement=corpus,
        ),
        Requirement(
            path=artifact.path,
            bytes=artifact_bytes,
            inodes=len(artifact_sizes),
            placement=artifact,
        ),
        Requirement(
            path=supervisor.path,
            bytes=supervisor_bytes,
            inodes=supervisor_file_count,
            placement=supervisor,
        ),
        Requirement(
            path=workspace.path,
            bytes=workspace_bytes,
            inodes=QUALIFICATION_NONCORPUS_INODES,
            placement=workspace,
        ),
    )


def qualification_verify_stdout_allowance(*, expected_findings: int) -> int:
    """Return the private verify-stdout ceiling for a deterministic corpus."""
    return max(
        SUPERVISOR_PRIVATE_BYTES_PER_FILE,
        expected_findings * VERIFY_STDOUT_BYTES_PER_FINDING,
    )


def _default_stat(path: Path) -> os.stat_result:
    return path.stat()


def _default_statvfs(path: Path) -> os.statvfs_result:
    return os.statvfs(path)


def _margin_fraction(value: int | float | Fraction) -> Fraction:
    if isinstance(value, bool):
        raise ValueError("capacity margin must be a non-negative finite number")
    try:
        fraction = value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("capacity margin must be a non-negative finite number") from exc
    if fraction < 0:
        raise ValueError("capacity margin must be a non-negative finite number")
    return fraction


def _ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def group_capacity_by_filesystem(
    requirements: Iterable[Requirement],
    *,
    stat_path: StatPath = _default_stat,
) -> tuple[FilesystemRequirement, ...]:
    """Sum destination requirements by followed ``st_dev`` without double counting."""
    values = tuple(requirements)
    if not values:
        raise ResourcePreflightError("at least one capacity requirement is required")
    groups: dict[int, FilesystemRequirement] = {}
    try:
        for requirement in values:
            placement = requirement.placement
            held_identity = placement.require_current_identity() if placement is not None else None
            device = (
                held_identity.st_dev
                if held_identity is not None and stat_path is _default_stat
                else stat_path(requirement.path).st_dev
            )
            current = groups.get(device)
            if current is None:
                groups[device] = FilesystemRequirement(
                    device=device,
                    probe=requirement.path,
                    placement=placement,
                    required_bytes=requirement.bytes,
                    required_inodes=requirement.inodes,
                )
            else:
                groups[device] = FilesystemRequirement(
                    device=device,
                    probe=current.probe,
                    placement=current.placement,
                    required_bytes=current.required_bytes + requirement.bytes,
                    required_inodes=current.required_inodes + requirement.inodes,
                )
    except (OSError, ValueError) as exc:
        raise ResourcePreflightError("capacity probe failed before device aggregation") from exc
    return tuple(groups[device] for device in sorted(groups))


def check_capacity(
    requirements: Iterable[Requirement],
    *,
    stat_path: StatPath = _default_stat,
    statvfs: StatVfs = _default_statvfs,
    filesystem_type: FilesystemTypeProbe | None = None,
    margin: int | float | Fraction = BINDING_CAPACITY_MARGIN,
) -> CapacityCheck:
    """Group requirements by followed ``st_dev`` and check each filesystem once."""
    margin_value = _margin_fraction(margin)
    if margin_value not in _ALLOWED_CAPACITY_MARGINS:
        raise ValueError("capacity margin must be zero or the exact binding margin")
    groups = group_capacity_by_filesystem(requirements, stat_path=stat_path)

    multiplier = 1 + margin_value
    public_results: list[FilesystemCapacityEvidence] = []
    mount_snapshot: tuple[MountInfo, ...] | None = None

    def classify_filesystem(path: Path) -> str:
        nonlocal mount_snapshot
        if filesystem_type is not None:
            return filesystem_type(path)
        if mount_snapshot is None:
            try:
                text = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
            except OSError as exc:
                raise ResourcePreflightError(
                    "inode capacity telemetry could not be classified"
                ) from exc
            mount_snapshot = parse_mountinfo(text)
        return select_mount(path, mount_snapshot).filesystem

    for group in groups:
        try:
            if group.placement is not None and statvfs is _default_statvfs:
                stats = group.placement.capacity_stats()
            else:
                stats = statvfs(group.probe)
            available_bytes, available_inodes = available_capacity(stats)
        except (OSError, ValueError) as exc:
            raise ResourcePreflightError(
                "capacity probe failed for an aggregated filesystem"
            ) from exc
        required_bytes = _ceil_fraction(Fraction(group.required_bytes) * multiplier)
        required_inodes = _ceil_fraction(Fraction(group.required_inodes) * multiplier)
        inode_triplet_unknown = stats.f_files == stats.f_ffree == stats.f_favail == 0
        if inode_triplet_unknown:
            if classify_filesystem(group.probe) != "btrfs":
                raise ResourcePreflightError(
                    "inode capacity telemetry is unavailable for a non-btrfs filesystem"
                )
            # Btrfs allocates inodes from metadata dynamically; null records that
            # no fixed statvfs inode pool exists, while bytes remain binding.
            inode_capacity_mode = "dynamic-metadata"
            public_available_inodes = None
            passed = required_bytes <= available_bytes
        else:
            inode_capacity_mode = "finite-statvfs"
            public_available_inodes = available_inodes
            passed = required_bytes <= available_bytes and required_inodes <= available_inodes
        public_results.append(
            FilesystemCapacityEvidence(
                required_bytes=required_bytes,
                available_bytes=available_bytes,
                required_inodes=required_inodes,
                inode_capacity_mode=inode_capacity_mode,
                available_inodes=public_available_inodes,
                margin_fraction=float(margin_value),
                passed=passed,
            )
        )

    # Sorting only public aggregates makes result order deterministic without
    # preserving the private device identifier used for grouping.
    public_results.sort(
        key=lambda item: (
            item.required_bytes,
            item.required_inodes,
            item.available_bytes,
            item.available_inodes is None,
            item.available_inodes if item.available_inodes is not None else 0,
        )
    )
    filesystems = tuple(public_results)
    return CapacityCheck(ok=all(item.passed for item in filesystems), filesystems=filesystems)


_MOUNT_ESCAPES = {"040": " ", "011": "\t", "012": "\n", "134": "\\"}


def _decode_mount_field(value: str) -> str:
    decoded: list[str] = []
    index = 0
    while index < len(value):
        if value[index] != "\\":
            decoded.append(value[index])
            index += 1
            continue
        code = value[index + 1 : index + 4]
        replacement = _MOUNT_ESCAPES.get(code)
        if len(code) != 3 or replacement is None:
            raise ResourcePreflightError("mountinfo contains an invalid escaped field")
        decoded.append(replacement)
        index += 4
    return "".join(decoded)


def _parse_options(value: str) -> tuple[str, ...]:
    options = tuple(value.split(","))
    if not options or any(not option for option in options):
        raise ResourcePreflightError("mountinfo contains malformed mount options")
    return options


def _parse_mount_line(line: str) -> MountInfo:
    fields = line.split()
    if fields.count("-") != 1:
        raise ResourcePreflightError("mountinfo record has no unique optional-field separator")
    separator = fields.index("-")
    before = fields[:separator]
    after = fields[separator + 1 :]
    if len(before) < 6 or len(after) != 3:
        raise ResourcePreflightError("mountinfo record has the wrong field count")
    try:
        mount_id = int(before[0], 10)
        parent_id = int(before[1], 10)
        major_text, minor_text = before[2].split(":", 1)
        device_major = int(major_text, 10)
        device_minor = int(minor_text, 10)
    except (ValueError, IndexError) as exc:
        raise ResourcePreflightError("mountinfo record has an invalid numeric identity") from exc
    if min(mount_id, parent_id, device_major, device_minor) < 0:
        raise ResourcePreflightError("mountinfo record has an invalid numeric identity")

    root = Path(_decode_mount_field(before[3]))
    mount_point = Path(_decode_mount_field(before[4]))
    if not root.is_absolute() or not mount_point.is_absolute():
        raise ResourcePreflightError("mountinfo root and mount point must be absolute")
    filesystem = after[0]
    if not filesystem:
        raise ResourcePreflightError("mountinfo filesystem type is missing")
    return MountInfo(
        mount_id=mount_id,
        parent_id=parent_id,
        device_major=device_major,
        device_minor=device_minor,
        root=root,
        mount_point=mount_point,
        mount_options=_parse_options(before[5]),
        optional_fields=tuple(before[6:]),
        filesystem=filesystem,
        mount_source=_decode_mount_field(after[1]),
        super_options=_parse_options(after[2]),
    )


def parse_mountinfo(text: str) -> tuple[MountInfo, ...]:
    """Parse Linux mountinfo while tolerating future optional fields as required."""
    lines = text.splitlines()
    if not lines or any(not line.strip() for line in lines):
        raise ResourcePreflightError("mountinfo is empty or contains an empty record")
    mounts = tuple(_parse_mount_line(line) for line in lines)
    if len({mount.mount_id for mount in mounts}) != len(mounts):
        raise ResourcePreflightError("mountinfo contains duplicate mount identities")
    return mounts


def _topmost_mount(records: tuple[MountInfo, ...]) -> MountInfo:
    parent_ids = {mount.parent_id for mount in records if mount.parent_id != mount.mount_id}
    topmost = tuple(mount for mount in records if mount.mount_id not in parent_ids)
    if len(topmost) != 1:
        raise ResourcePreflightError("containing mountinfo records are ambiguous")

    by_id = {mount.mount_id: mount for mount in records}
    visited: set[int] = set()
    current = topmost[0]
    while current.mount_id not in visited:
        visited.add(current.mount_id)
        if current.parent_id == current.mount_id or current.parent_id not in by_id:
            break
        current = by_id[current.parent_id]
    if current.mount_id in visited and len(visited) != len(records):
        raise ResourcePreflightError("containing mountinfo records are ambiguous")
    if visited != set(by_id):
        raise ResourcePreflightError("containing mountinfo records are ambiguous")
    return topmost[0]


def _visible_mount_at(parent: MountInfo, records: tuple[MountInfo, ...]) -> MountInfo:
    current = parent
    visited: set[int] = set()
    while True:
        children = tuple(
            mount
            for mount in records
            if mount.parent_id == current.mount_id and mount.mount_id not in visited
        )
        if not children:
            return current
        if len(children) != 1:
            raise ResourcePreflightError("containing mountinfo records are ambiguous")
        current = children[0]
        if current.mount_id in visited:
            raise ResourcePreflightError("containing mountinfo records are ambiguous")
        visited.add(current.mount_id)


def select_mount(path: Path, mounts: Iterable[MountInfo]) -> MountInfo:
    """Choose the visible containing mount after symlink and stack resolution."""
    if not path.is_absolute():
        raise ResourcePreflightError("mount selection requires an absolute path")
    try:
        resolved = Path(os.path.realpath(path, strict=os.path.ALLOW_MISSING))
    except (OSError, RuntimeError) as exc:
        raise ResourcePreflightError("mount selection could not resolve the target path") from exc

    groups: dict[Path, list[MountInfo]] = {}
    for mount in mounts:
        if resolved.is_relative_to(mount.mount_point):
            groups.setdefault(mount.mount_point, []).append(mount)
    root = groups.get(Path("/"))
    if root is None:
        raise ResourcePreflightError("mountinfo has no containing root mount")

    active = _topmost_mount(tuple(root))
    points = sorted(
        (point for point in groups if point != Path("/")),
        key=lambda point: len(point.parts),
    )
    for point in points:
        # A descendant whose parent is not the currently visible mount belongs
        # to a hidden lower stack and cannot classify the resolved target.
        active = _visible_mount_at(active, tuple(groups[point]))
    return active


def project_mount_flags(mount: MountInfo) -> MountFlagProjection:
    """Reduce raw field-6 options without ever publishing rejected option values."""
    seen: set[str] = set()
    complete = True
    for option in mount.mount_options:
        if option not in _PUBLIC_MOUNT_FLAG_SET or option in seen:
            complete = False
        seen.add(option)
    if ("ro" in seen) == ("rw" in seen):
        complete = False
    flags = cast(
        "tuple[MountFlag, ...]", tuple(flag for flag in PUBLIC_MOUNT_FLAGS if flag in seen)
    )
    return MountFlagProjection(flags=flags, complete=complete)


def _public_probe_label(value: str) -> str:
    normalized = " ".join(value.split())
    if (
        not normalized
        or len(normalized) > 256
        or any(character in "/\\=" or ord(character) < 32 for character in normalized)
    ):
        return "unknown"
    return normalized


def _cpu_model(cpuinfo: str) -> str:
    fields: dict[str, str] = {}
    for line in cpuinfo.splitlines():
        name, separator, value = line.partition(":")
        if separator:
            fields.setdefault(name.strip().lower(), value)
    for field_name in ("model name", "hardware", "processor"):
        if field_name in fields:
            return _public_probe_label(fields[field_name])
    raise ResourcePreflightError("CPU model telemetry unavailable")


_MEM_TOTAL_PATTERN = re.compile(r"^MemTotal:[ \t]+([0-9]+)[ \t]+kB$")


def _ram_bytes(meminfo: str) -> int:
    values = tuple(
        match
        for line in meminfo.splitlines()
        if (match := _MEM_TOTAL_PATTERN.fullmatch(line)) is not None
    )
    if len(values) != 1:
        raise ResourcePreflightError("RAM telemetry unavailable")
    value = int(values[0].group(1), 10) * 1024
    if value <= 0:
        raise ResourcePreflightError("RAM telemetry unavailable")
    return value


def _leaf_rotational_snapshot(
    node: Path,
    probes: ReferenceProbes,
    *,
    visiting: frozenset[Path] = frozenset(),
) -> tuple[tuple[Path, int], ...]:
    """Return resolved identity and rotational state for each proven leaf.

    Every branch must resolve: classifying a dm/LVM stack from only the
    readable leaves could publish an SSD/HDD assertion that the topology does
    not support.
    """
    resolved = probes.resolve(node)
    if resolved in visiting:
        raise ResourcePreflightError("block-device topology is cyclic")
    try:
        descendants = probes.list_directory(node / "slaves")
    except FileNotFoundError:
        descendants = ()
    if descendants:
        if any(not name or name in {".", ".."} or "/" in name for name in descendants):
            raise ResourcePreflightError("block-device topology is malformed")
        next_visiting = visiting | {resolved}
        return tuple(
            observation
            for name in descendants
            for observation in _leaf_rotational_snapshot(
                node / "slaves" / name,
                probes,
                visiting=next_visiting,
            )
        )
    try:
        value = probes.read_text(resolved / "queue" / "rotational").strip()
    except OSError:
        partition = probes.read_text(resolved / "partition").strip()
        if not partition.isdigit() or int(partition, 10) <= 0:
            raise ResourcePreflightError("partition topology is malformed") from None
        value = probes.read_text(resolved.parent / "queue" / "rotational").strip()
    if value not in {"0", "1"}:
        raise ResourcePreflightError("rotational telemetry is malformed")
    return ((resolved, int(value, 10)),)


def _normalized_leaf_rotational_snapshot(
    nodes: Iterable[Path], probes: ReferenceProbes
) -> tuple[tuple[Path, int], ...]:
    snapshot = tuple(
        observation for node in nodes for observation in _leaf_rotational_snapshot(node, probes)
    )
    identities = tuple(identity for identity, _rotational in snapshot)
    if len(set(identities)) != len(identities):
        raise ResourcePreflightError("block-device leaf topology is incomplete or malformed")
    return tuple(sorted(snapshot, key=lambda observation: observation[0].as_posix()))


@dataclass(frozen=True, slots=True)
class _BtrfsDeviceSnapshot:
    """One private, comparable btrfs identity and member-device snapshot."""

    fsid: bytes
    num_devices: int
    nodes: tuple[Path, ...]
    targets: tuple[Path, ...]


def _btrfs_device_snapshot(workspace: Path, probes: ReferenceProbes) -> _BtrfsDeviceSnapshot:
    """Bind an anonymous btrfs mount to its complete kernel-reported device set."""
    fsid_bytes, num_devices = probes.btrfs_filesystem_info(workspace)
    if type(fsid_bytes) is not bytes or len(fsid_bytes) != 16:
        raise ResourcePreflightError("btrfs filesystem identity is malformed")
    if type(num_devices) is not int or num_devices <= 0:
        raise ResourcePreflightError("btrfs device count is malformed")
    try:
        identity = UUID(bytes=fsid_bytes)
    except ValueError as exc:
        raise ResourcePreflightError("btrfs filesystem identity is malformed") from exc
    if identity.int == 0:
        raise ResourcePreflightError("btrfs filesystem identity is malformed")

    devices = Path("/sys/fs/btrfs") / str(identity) / "devices"
    # sysfs readdir order is not stable topology identity; normalize the
    # member set so a harmless order change cannot downgrade a binding host.
    names = tuple(sorted(probes.list_directory(devices)))
    if (
        len(names) != num_devices
        or len(set(names)) != len(names)
        or any(not name or name in {".", ".."} or "/" in name for name in names)
    ):
        raise ResourcePreflightError("btrfs device topology is incomplete or malformed")
    nodes = tuple(devices / name for name in names)
    targets = tuple(probes.resolve(node) for node in nodes)
    sysfs_devices = Path("/sys/devices")
    if len(set(targets)) != len(targets) or any(
        not target.is_absolute()
        or target == sysfs_devices
        or not target.is_relative_to(sysfs_devices)
        for target in targets
    ):
        raise ResourcePreflightError("btrfs member topology is incomplete or malformed")
    return _BtrfsDeviceSnapshot(
        fsid=fsid_bytes,
        num_devices=num_devices,
        nodes=nodes,
        targets=targets,
    )


def _storage_class(
    workspace: Path,
    mount: MountInfo,
    probes: ReferenceProbes,
) -> StorageClass:
    if mount.filesystem in {"tmpfs", "ramfs"}:
        return "memory"
    if mount.filesystem in REJECTED_NETWORK_FILESYSTEMS:
        return "network"
    if mount.filesystem not in ALLOWED_BINDING_FILESYSTEMS:
        return "unknown"
    try:
        btrfs_snapshot = (
            _btrfs_device_snapshot(workspace, probes) if mount.filesystem == "btrfs" else None
        )
        nodes = (
            btrfs_snapshot.nodes
            if btrfs_snapshot is not None
            else (Path(f"/sys/dev/block/{mount.device_major}:{mount.device_minor}"),)
        )
        leaf_snapshot = _normalized_leaf_rotational_snapshot(nodes, probes)
        if btrfs_snapshot is not None:
            final_snapshot = _btrfs_device_snapshot(workspace, probes)
            final_leaf_snapshot = _normalized_leaf_rotational_snapshot(final_snapshot.nodes, probes)
            if final_snapshot != btrfs_snapshot or final_leaf_snapshot != leaf_snapshot:
                raise ResourcePreflightError("btrfs device topology changed during observation")
        rotational = frozenset(value for _identity, value in leaf_snapshot)
    except OSError, RuntimeError, ResourcePreflightError:
        return "unknown"
    if rotational == frozenset({0}):
        return "local-ssd"
    if rotational == frozenset({1}):
        return "local-hdd"
    return "unknown"


def observe_reference_environment(
    workspace: Path,
    *,
    probes: ReferenceProbes = _DEFAULT_REFERENCE_PROBES,
) -> ReferenceObservation:
    """Observe one sanitized public environment from private Linux telemetry."""
    try:
        mountinfo = probes.read_text(Path("/proc/self/mountinfo"))
        cpuinfo = probes.read_text(Path("/proc/cpuinfo"))
        meminfo = probes.read_text(Path("/proc/meminfo"))
        capacity = probes.statvfs(workspace)
    except OSError as exc:
        raise ResourcePreflightError("reference environment telemetry unavailable") from exc
    if capacity.f_frsize <= 0:
        raise ResourcePreflightError("reference fragment size unavailable")
    logical_cpu_count = probes.logical_cpu_count()
    if type(logical_cpu_count) is not int or logical_cpu_count <= 0:
        raise ResourcePreflightError("logical CPU count unavailable")
    mount = select_mount(workspace, parse_mountinfo(mountinfo))
    projection = project_mount_flags(mount)
    filesystem = (
        mount.filesystem if re.fullmatch(r"[a-z0-9][a-z0-9._+-]*", mount.filesystem) else "unknown"
    )
    environment = ReferenceEnvironment(
        operating_system="linux",
        cpu_architecture=_public_probe_label(probes.machine()),
        cpu_model=_cpu_model(cpuinfo),
        logical_cpu_count=logical_cpu_count,
        ram_bytes=_ram_bytes(meminfo),
        storage_class=_storage_class(workspace, mount, probes),
        filesystem=filesystem,
        mount_flags=projection.flags,
        python_version=_public_probe_label(probes.python_version()),
        kernel_version=_public_probe_label(probes.kernel_version()),
    )
    return ReferenceObservation(
        environment=environment,
        mount_projection=projection,
        fragment_size=capacity.f_frsize,
    )


def _reference_value(environment: ReferenceEnvironment, field: ReferenceField) -> object:
    if field == "mount_flags":
        return frozenset(environment.mount_flags)
    return getattr(environment, field)


def _reference_field_matches(
    observed: ReferenceEnvironment,
    accepted: ReferenceEnvironment,
    field: ReferenceField,
) -> bool:
    if field == "ram_bytes":
        return abs(observed.ram_bytes - accepted.ram_bytes) <= _RAM_EQUIVALENCE_BYTES
    return _reference_value(observed, field) == _reference_value(accepted, field)


def compare_reference_environment(
    observed: ReferenceEnvironment,
    accepted: ReferenceEnvironment,
    *,
    mount_projection: MountFlagProjection,
) -> ReferenceComparison:
    """Compare public reference-class equivalence, then enforce binding eligibility.

    ``exact_match`` means no mismatch under the field-specific equivalence rules;
    it does not require byte-identical RAM telemetry.
    """
    mismatches = cast(
        "tuple[ReferenceField, ...]",
        tuple(
            field
            for field in _REFERENCE_FIELDS
            if not _reference_field_matches(observed, accepted, field)
        ),
    )
    exact_match = not mismatches
    binding_filesystem = (
        mount_projection.complete
        and frozenset(mount_projection.flags) == frozenset(observed.mount_flags)
        and observed.storage_class == "local-ssd"
        and observed.filesystem in ALLOWED_BINDING_FILESYSTEMS
    )
    ram_requirement_met = observed.ram_bytes >= MIN_BINDING_RAM_BYTES
    return ReferenceComparison(
        binding=exact_match and binding_filesystem and ram_requirement_met,
        exact_match=exact_match,
        mismatched_fields=mismatches,
        binding_filesystem=binding_filesystem,
        ram_requirement_met=ram_requirement_met,
    )


def build_preflight_evidence(
    capacity: CapacityCheck, comparison: ReferenceComparison
) -> PreflightEvidence:
    """Reduce private resource probes into the strict public preflight record."""
    capacity_margin_met = bool(capacity.filesystems) and all(
        item.margin_fraction == BINDING_CAPACITY_MARGIN for item in capacity.filesystems
    )
    passed = (
        capacity.ok
        and capacity_margin_met
        and comparison.exact_match
        and comparison.binding_filesystem
        and comparison.ram_requirement_met
    )
    return PreflightEvidence(
        filesystems=capacity.filesystems,
        capacity_margin_met=capacity_margin_met,
        reference_environment_match=comparison.exact_match,
        binding_filesystem=comparison.binding_filesystem,
        ram_requirement_met=comparison.ram_requirement_met,
        passed=passed,
    )


_VM_SWAP_PATTERN = re.compile(r"^VmSwap:[ \t]+([0-9]+)[ \t]+kB$")


def parse_vm_swap(status_text: str) -> int:
    """Parse one child's anonymous-private swap total from ``/proc/PID/status``."""
    fields = [line for line in status_text.splitlines() if line.startswith("VmSwap:")]
    if len(fields) != 1:
        raise ResourcePreflightError("child VmSwap unavailable")
    match = _VM_SWAP_PATTERN.fullmatch(fields[0])
    if match is None:
        raise ResourcePreflightError("child VmSwap unavailable")
    return int(match.group(1), 10) * 1024


def max_child_vm_swap(status_samples: Iterable[str]) -> int:
    """Return the largest child swap sample; absence is never treated as zero."""
    samples = tuple(status_samples)
    if not samples:
        raise ResourcePreflightError("at least one child VmSwap sample is required")
    return max(parse_vm_swap(sample) for sample in samples)
