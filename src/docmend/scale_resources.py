"""Linux resource preflight for DMR-08 qualification (NFR-001, OQ-039).

Paths, device numbers, mount sources, and raw options are private harness data.
This module reduces them to the identifier-free capacity and reference verdicts
defined in :mod:`docmend.scale_evidence`; only those reduced records may enter
public qualification evidence.

The external grammars follow Linux ``proc_pid_mountinfo(5)``, ``statvfs(3)``,
``proc_pid_status(5)``, and ``proc_vmstat(5)``. Unknown mountinfo optional
fields are intentionally tolerated; unavailable binding measurements are not.
"""

import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Literal, cast

from docmend.scale_evidence import (
    BINDING_CAPACITY_MARGIN,
    FilesystemCapacityEvidence,
    MountFlag,
    PreflightEvidence,
    ReferenceEnvironment,
)

ALLOWED_BINDING_FILESYSTEMS = frozenset({"ext4", "xfs", "btrfs"})
REJECTED_NETWORK_FILESYSTEMS = frozenset({"nfs", "nfs4", "cifs", "smb3"})
MIN_BINDING_RAM_BYTES = 16 * 1024**3

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


class ResourcePreflightError(Exception):
    """Required Linux resource telemetry is missing, malformed, or ambiguous."""


@dataclass(frozen=True, slots=True)
class Requirement:
    """One private destination's pre-margin physical allocation estimate."""

    path: Path
    bytes: int
    inodes: int

    def __post_init__(self) -> None:
        if type(self.bytes) is not int or self.bytes < 0:
            raise ValueError("requirement bytes must be a non-negative integer")
        if type(self.inodes) is not int or self.inodes < 0:
            raise ValueError("requirement inodes must be a non-negative integer")


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
class SwapCounters:
    """Diagnostic cumulative ``/proc/vmstat`` swap-page counters or their delta."""

    pswpin: int
    pswpout: int

    def __post_init__(self) -> None:
        if self.pswpin < 0 or self.pswpout < 0:
            raise ValueError("swap counters must be non-negative")


@dataclass(slots=True)
class _CapacityGroup:
    probe: Path
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


def check_capacity(
    requirements: Iterable[Requirement],
    *,
    stat_path: StatPath = _default_stat,
    statvfs: StatVfs = _default_statvfs,
    margin: int | float | Fraction = BINDING_CAPACITY_MARGIN,
) -> CapacityCheck:
    """Group requirements by followed ``st_dev`` and check each filesystem once."""
    values = tuple(requirements)
    if not values:
        raise ResourcePreflightError("at least one capacity requirement is required")
    margin_value = _margin_fraction(margin)
    if margin_value not in _ALLOWED_CAPACITY_MARGINS:
        raise ValueError("capacity margin must be zero or the exact binding margin")
    groups: dict[int, _CapacityGroup] = {}
    try:
        for requirement in values:
            device = stat_path(requirement.path).st_dev
            current = groups.get(device)
            if current is None:
                groups[device] = _CapacityGroup(
                    probe=requirement.path,
                    required_bytes=requirement.bytes,
                    required_inodes=requirement.inodes,
                )
            else:
                current.required_bytes += requirement.bytes
                current.required_inodes += requirement.inodes
    except (OSError, ValueError) as exc:
        raise ResourcePreflightError("capacity probe failed before device aggregation") from exc

    multiplier = 1 + margin_value
    public_results: list[FilesystemCapacityEvidence] = []
    for group in groups.values():
        try:
            available_bytes, available_inodes = available_capacity(statvfs(group.probe))
        except (OSError, ValueError) as exc:
            raise ResourcePreflightError(
                "capacity probe failed for an aggregated filesystem"
            ) from exc
        required_bytes = _ceil_fraction(Fraction(group.required_bytes) * multiplier)
        required_inodes = _ceil_fraction(Fraction(group.required_inodes) * multiplier)
        passed = required_bytes <= available_bytes and required_inodes <= available_inodes
        public_results.append(
            FilesystemCapacityEvidence(
                required_bytes=required_bytes,
                available_bytes=available_bytes,
                required_inodes=required_inodes,
                available_inodes=available_inodes,
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
            item.available_inodes,
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


def is_binding_filesystem(mount: MountInfo, projection: MountFlagProjection) -> bool:
    """Return whether the mount is a complete public local-disk filesystem class."""
    if mount.filesystem in REJECTED_NETWORK_FILESYSTEMS:
        return False
    return mount.filesystem in ALLOWED_BINDING_FILESYSTEMS and projection.complete


def _reference_value(environment: ReferenceEnvironment, field: ReferenceField) -> object:
    if field == "mount_flags":
        return frozenset(environment.mount_flags)
    return getattr(environment, field)


def compare_reference_environment(
    observed: ReferenceEnvironment,
    accepted: ReferenceEnvironment,
    *,
    mount_projection: MountFlagProjection,
) -> ReferenceComparison:
    """Compare exact public class identity, then enforce fixed binding eligibility."""
    mismatches = cast(
        "tuple[ReferenceField, ...]",
        tuple(
            field
            for field in _REFERENCE_FIELDS
            if _reference_value(observed, field) != _reference_value(accepted, field)
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


def parse_vmstat_swap(vmstat_text: str) -> SwapCounters:
    """Parse diagnostic cumulative ``pswpin``/``pswpout`` counters."""
    values: dict[str, int] = {}
    for line in vmstat_text.splitlines():
        fields = line.split()
        if not fields or fields[0] not in {"pswpin", "pswpout"}:
            continue
        name = fields[0]
        if len(fields) != 2 or name in values or not fields[1].isdigit():
            raise ResourcePreflightError("vmstat swap counters unavailable")
        values[name] = int(fields[1], 10)
    if set(values) != {"pswpin", "pswpout"}:
        raise ResourcePreflightError("vmstat swap counters unavailable")
    return SwapCounters(pswpin=values["pswpin"], pswpout=values["pswpout"])


def swap_counter_delta(before: SwapCounters, after: SwapCounters) -> SwapCounters:
    """Return diagnostic counter deltas, refusing reset/wrap instead of clamping."""
    pswpin = after.pswpin - before.pswpin
    pswpout = after.pswpout - before.pswpout
    if pswpin < 0 or pswpout < 0:
        raise ResourcePreflightError("vmstat swap counter delta unavailable")
    return SwapCounters(pswpin=pswpin, pswpout=pswpout)
