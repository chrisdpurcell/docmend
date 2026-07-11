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
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from docmend.config import DocmendConfig
from docmend.plan import Plan, PlanAction


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
    needed = sum(a.source_size_bytes for a in plan.actions)
    if config.rename.on_collision == "overwrite":
        # codex CR-006: overwrite mode also backs up each live-colliding
        # target, so its bytes count against the same mount.
        needed += sum(
            (source_root / a.target_path).stat().st_size
            for a in plan.actions
            if a.target_path is not None and (source_root / a.target_path).exists()
        )
    if shutil.disk_usage(options.backup_root).free < needed:
        return [
            GateRefusal(
                predicate="disk-preflight",
                message=(
                    f"{options.backup_root}: {needed} bytes of backups planned but less "
                    "free space on the destination mount (OQ-005 per-mount preflight)"
                ),
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


def _source_headroom(plan: Plan, config: DocmendConfig, source_root: Path) -> list[GateRefusal]:
    if not plan.actions:
        return []
    # codex CR-006: transformed output can be LARGER than the input. Bound the
    # mechanical growth instead of assuming size parity: a legacy single-byte
    # encoding re-encodes to at most 3 UTF-8 bytes per byte, and leading-tab
    # expansion multiplies by tab_width; the two maxima cannot compound (tabs
    # are ASCII and re-encode 1:1), so the factor is their max, not product.
    factor = max(3, config.whitespace.tab_width if config.whitespace.normalize_tabs else 1)
    largest = max(a.source_size_bytes for a in plan.actions) * factor
    if shutil.disk_usage(source_root).free >= largest:
        return []
    return [
        GateRefusal(
            predicate="disk-preflight",
            message=(
                f"{source_root}: the largest planned temp file (bounded at {largest} bytes) "
                "exceeds free space on the target mount (OQ-005 per-mount preflight)"
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
) -> list[GateRefusal]:
    return [
        *_containment(plan, source_root),
        *_preservation(plan, options),
        *_overwrite_preservation(plan, config, source_root, options),
        *_backup_destination(plan, config, source_root, options),
        *_manifest_destination(manifest_dir),
        *_source_headroom(plan, config, source_root),
    ]
