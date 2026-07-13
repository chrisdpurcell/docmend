"""Apply safety gate — pure independent predicates (FR-005, OQ-005, adr-0004).

Evaluated before any non-dry-run mutation; each predicate is independent and
side-effect-light (writability probes create/remove one probe file) so the set
is combinatorially testable (allpairspy, §17.2). Empty result ⇒ proceed; any
refusal ⇒ exit 3 and the library is untouched.

Risk tiers (OQ-035 proposal): content rewrites need an active byte-preserving
strategy (tool backups or a declared git/external strategy) unless the plan is
a single action under the explicit --allow-no-backup opt-in; rename-only runs
are undoable from the manifest alone; a run that would actually overwrite an
existing target destroys that target's bytes and therefore needs a strategy
regardless (G-002).
"""

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from docmend.config import DocmendConfig
from docmend.plan import Plan, PlanAction
from docmend.scale_resources import (
    MANIFEST_BYTES_PER_ACTION,
    REPORT_BYTES_PER_ACTION,
    STRUCTURED_LOG_BYTES_PER_INPUT_STAGE,
    VERIFY_BYTES_PER_INPUT,
    Requirement,
    ResourcePreflightError,
    allocated_bytes,
    check_capacity,
)


@dataclass(frozen=True)
class ApplyOptions:
    write: bool
    backup_root: Path | None
    # str, not Literal["git","external"]: the CLI's PreservedBy enum .value is
    # typed str, and the gate only ever tests "is a strategy declared at all".
    preserved_by: str | None
    allow_no_backup: bool


@dataclass(frozen=True)
class GateRefusal:
    predicate: str
    message: str


def is_content_rewrite(action: PlanAction) -> bool:
    """OQ-035 risk tier: any operation beyond a pure path rename rewrites content."""
    return any(op != "rename" for op in action.operations)


def _dir_writable(path: Path) -> bool:
    probe = path / f".docmend-probe-{uuid.uuid4().hex}"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.touch()
        probe.unlink()
    except OSError:
        return False
    return True


def strategy_active(options: ApplyOptions) -> bool:
    return options.backup_root is not None or options.preserved_by is not None


def _containment(plan: Plan, source_root: Path) -> list[GateRefusal]:
    # Belt over the model validators: normpath-level re-check of every planned
    # path against the root (a crafted plan must fail here even if a reader
    # regression ever let it through). Runtime symlink escapes are the apply
    # loop's resolve() check (decision 12).
    refusals: list[GateRefusal] = []
    root = os.path.normpath(source_root)
    for action in plan.actions:
        for candidate in (action.path, action.target_path):
            if candidate is None:
                continue
            joined = os.path.normpath(Path(root) / candidate)
            if os.path.commonpath([root, joined]) != root:
                refusals.append(
                    GateRefusal(
                        predicate="containment",
                        message=f"{candidate}: planned path escapes {source_root} (§8.5/§13.5)",
                    )
                )
    return refusals


def _preservation(plan: Plan, options: ApplyOptions) -> list[GateRefusal]:
    content = [a for a in plan.actions if is_content_rewrite(a)]
    refusals: list[GateRefusal] = []
    if options.allow_no_backup and len(plan.actions) > 1:
        refusals.append(
            GateRefusal(
                predicate="preservation",
                message=(
                    "--allow-no-backup is the FR-005 low-risk opt-in and is limited to "
                    "single-action plans; this plan has "
                    f"{len(plan.actions)} actions"
                ),
            )
        )
    if content and not strategy_active(options):
        if options.allow_no_backup and len(plan.actions) == 1:
            return refusals
        refusals.append(
            GateRefusal(
                predicate="preservation",
                message=(
                    "content-changing rewrite with no byte-preserving strategy: enable "
                    "tool backups (--backup-dir / write.backup_dir), declare one "
                    "(--preserved-by git|external), or use --allow-no-backup for a "
                    "single-file low-risk run (FR-005; the manifest alone is rollback "
                    "metadata, not preservation)"
                ),
            )
        )
    return refusals


def _overwrite_preservation(
    plan: Plan, config: DocmendConfig, source_root: Path, options: ApplyOptions
) -> list[GateRefusal]:
    """Provide early feedback for overwrite targets visible before execution.

    The action-time invariant lives in the commit boundary: `_execute_action`
    re-checks `strategy_active` for every existing target it discovers. A target
    appearing after this gate without preservation is skipped rather than
    clobbered, so this predicate is no longer the load-bearing enforcement.
    """
    if config.rename.on_collision != "overwrite" or strategy_active(options):
        return []
    clobbers = [
        a.target_path
        for a in plan.actions
        if a.target_path is not None and (source_root / a.target_path).exists()
    ]
    if not clobbers:
        return []
    return [
        GateRefusal(
            predicate="overwrite-preservation",
            message=(
                f"overwrite collision policy would destroy {len(clobbers)} existing "
                "target file(s) with no byte-preserving strategy active (G-002, FR-011)"
            ),
        )
    ]


def _backup_destination(
    plan: Plan, config: DocmendConfig, source_root: Path, options: ApplyOptions
) -> list[GateRefusal]:
    if options.backup_root is None:
        return []
    resolved = options.backup_root.resolve()
    if resolved.is_relative_to(source_root.resolve()):
        # Short-circuit BEFORE any writability probe (codex CR-002): probing
        # mkdirs the destination, and this destination is inside the library —
        # a refusal must leave the target untouched (§8.5, adr-0004).
        return [
            GateRefusal(
                predicate="backup-outside-target",
                message=f"{options.backup_root}: backup destination lies inside the mutation target (OQ-005, §8.5)",
            )
        ]
    if not _dir_writable(options.backup_root):
        return [
            GateRefusal(
                predicate="backup-writable",
                message=f"{options.backup_root}: backup destination is not writable (OQ-005)",
            )
        ]
    return []


def _manifest_destination(manifest_dir: Path) -> list[GateRefusal]:
    if _dir_writable(manifest_dir):
        return []
    return [
        GateRefusal(
            predicate="manifest-writable",
            message=f"{manifest_dir}: manifest destination is not writable (adr-0004: manifest is mandatory rollback metadata)",
        )
    ]


def _capacity_probe(path: Path) -> tuple[Path, int]:
    """Return the hosting filesystem probe and missing directory count."""
    probe = path.resolve()
    missing_directories = 0
    while not probe.exists():
        parent = probe.parent
        if parent == probe:
            raise ResourcePreflightError("capacity destination has no existing ancestor")
        probe = parent
        missing_directories += 1
    return (probe if probe.is_dir() else probe.parent), missing_directories


def _existing_capacity_probe(path: Path) -> Path:
    return _capacity_probe(path)[0]


def _allocated_file_sizes(probe: Path, sizes: list[int]) -> int:
    try:
        fragment_size = os.statvfs(probe).f_frsize
        return sum(allocated_bytes(size, fragment_size) for size in sizes)
    except (OSError, ValueError) as exc:
        raise ResourcePreflightError("capacity fragment-size probe failed") from exc


def _capacity_requirements(
    plan: Plan,
    config: DocmendConfig,
    *,
    source_root: Path,
    options: ApplyOptions,
    manifest_dir: Path,
    report_path: Path | None,
    log_path: Path | None,
) -> tuple[Requirement, ...]:
    """Build per-file physical estimates before followed-filesystem aggregation."""
    source_probe = _existing_capacity_probe(source_root)
    artifact_probe = _existing_capacity_probe(manifest_dir)
    report_probe, report_missing_directories = (
        _capacity_probe(report_path.parent) if report_path is not None else (artifact_probe, 0)
    )
    log_probe = (
        _existing_capacity_probe(log_path.parent) if log_path is not None else artifact_probe
    )
    requirements: list[Requirement] = []

    if options.backup_root is not None:
        backup_probe = _existing_capacity_probe(options.backup_root)
        try:
            fragment_size = os.statvfs(backup_probe).f_frsize
            if fragment_size <= 0:
                raise ValueError("invalid backup fragment size")
        except (OSError, ValueError) as exc:
            raise ResourcePreflightError("backup capacity fragment-size probe failed") from exc
        backup_bytes = 0
        backup_inodes = 1 if plan.actions else 0  # one run directory
        for action in plan.actions:
            backup_bytes += allocated_bytes(action.source_size_bytes, fragment_size)
            # Unique action directory, source-role directory, relative parents,
            # and the source backup file itself.
            backup_inodes += 3 + sum(part != "." for part in Path(action.path).parent.parts)
            if config.rename.on_collision != "overwrite" or action.target_path is None:
                continue
            target = source_root / action.target_path
            try:
                target_size = target.stat().st_size
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise ResourcePreflightError("overwrite target capacity probe failed") from exc
            backup_bytes += allocated_bytes(target_size, fragment_size)
            # Overwritten-role directory, relative parents, and backup file;
            # the run/action directories were counted with the source role.
            backup_inodes += 2 + sum(part != "." for part in Path(action.target_path).parent.parts)
        requirements.append(
            Requirement(
                path=backup_probe,
                bytes=backup_bytes,
                inodes=backup_inodes,
            )
        )

    # Transformed output can be larger than input: UTF-8 re-encoding and tab
    # expansion are mutually exclusive maxima, so reserve their larger factor.
    if plan.actions:
        factor = max(3, config.whitespace.tab_width if config.whitespace.normalize_tabs else 1)
        largest_staging = max(action.source_size_bytes for action in plan.actions) * factor
        requirements.append(
            Requirement(
                path=source_probe,
                bytes=_allocated_file_sizes(source_probe, [largest_staging]),
                inodes=1,
            )
        )

    # Apply/report/plan-coverage growth follows represented plan records. Clean
    # no-ops produce no apply outcome or coverage finding; the separate scale
    # qualification preflight owns full-corpus scan/verify logs and artifacts.
    record_count = max(1, len(plan.actions) + len(plan.skips))
    report_size = REPORT_BYTES_PER_ACTION * record_count
    verify_size = VERIFY_BYTES_PER_INPUT * record_count
    staging_probe = report_probe if report_size >= verify_size else artifact_probe
    staging_size = max(report_size, verify_size)
    artifact_sizes = (
        (artifact_probe, MANIFEST_BYTES_PER_ACTION * record_count, 0),
        (report_probe, report_size, report_missing_directories),
        (artifact_probe, verify_size, 0),
        (log_probe, STRUCTURED_LOG_BYTES_PER_INPUT_STAGE * record_count, 0),
        (staging_probe, staging_size, 0),
    )
    for probe, size, directory_count in artifact_sizes:
        requirements.append(
            Requirement(
                path=probe,
                bytes=_allocated_file_sizes(probe, [size, *([1] * directory_count)]),
                inodes=1 + directory_count,
            )
        )
    return tuple(requirements)


def _capacity_preflight(
    plan: Plan,
    config: DocmendConfig,
    *,
    source_root: Path,
    options: ApplyOptions,
    manifest_dir: Path,
    report_path: Path | None,
    log_path: Path | None,
) -> list[GateRefusal]:
    try:
        result = check_capacity(
            _capacity_requirements(
                plan,
                config,
                source_root=source_root,
                options=options,
                manifest_dir=manifest_dir,
                report_path=report_path,
                log_path=log_path,
            )
        )
    except ResourcePreflightError as exc:
        return [
            GateRefusal(
                predicate="disk-preflight",
                message=f"filesystem-aware capacity preflight could not be completed ({exc})",
            )
        ]
    if result.ok:
        return []
    failed = sum(not filesystem.passed for filesystem in result.filesystems)
    return [
        GateRefusal(
            predicate="disk-preflight",
            message=(
                f"{max(1, failed)} filesystem(s) lack the grouped byte or inode capacity "
                "for backups, staging, manifest/report/verify, and structured logs"
            ),
        )
    ]


def evaluate_gate(
    plan: Plan,
    config: DocmendConfig,
    *,
    source_root: Path,
    options: ApplyOptions,
    manifest_dir: Path,
    report_path: Path | None = None,
    log_path: Path | None = None,
) -> list[GateRefusal]:
    backup_refusals = _backup_destination(plan, config, source_root, options)
    manifest_refusals = _manifest_destination(manifest_dir)
    capacity_refusals = _capacity_preflight(
        plan,
        config,
        source_root=source_root,
        options=options,
        manifest_dir=manifest_dir,
        report_path=report_path,
        log_path=log_path,
    )
    return [
        *_containment(plan, source_root),
        *_preservation(plan, options),
        *_overwrite_preservation(plan, config, source_root, options),
        *backup_refusals,
        *manifest_refusals,
        *capacity_refusals,
    ]
