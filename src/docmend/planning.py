"""Planning layer — per-file decisions, risk classification, plan assembly (FR-002, FR-015, DR-002).

Architectural role (§8.2.3): consumes the DR-001 inventory + effective config,
emits the DR-002 plan. ALL danger detection happens here, before any write
(§8.1). Planning reads library files READ-ONLY (part 2's content pass) and
writes nothing itself — artifact IO lives in docmend.artifacts, invoked by the
CLI.

Decision record (spec C.4): every skip carries a classified reason + detail;
every action carries the facts it was decided on (source hash, detection,
newline style) so the plan is reviewable without re-running anything.

Gate order is fixed (adr-0009 + FR-015): filters -> hard-link -> oversize ->
encoding gates -> content checks (part 2). First hit wins; a file gets exactly
one skip decision or one action or (no-op) neither — FR-017's plan half.
"""

import uuid
from collections.abc import Callable

from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from docmend import __version__
from docmend.config import DocmendConfig
from docmend.inventory import FileRecord, Inventory
from docmend.observability import get_logger
from docmend.plan import (
    PLAN_SCHEMA_VERSION,
    ArtifactRef,
    Plan,
    PlanAction,
    PlanTotals,
    SkipDecision,
)


def _fact_skip(
    record: FileRecord,
    hard_linked: dict[str, str],
    config: DocmendConfig,
    include: PathSpec[GitIgnoreSpecPattern],
    exclude: PathSpec[GitIgnoreSpecPattern],
) -> SkipDecision | None:
    path = record.path
    if not include.match_file(path):
        return SkipDecision(
            path=path, reason="excluded", detail="not matched by plan-time include patterns"
        )
    if exclude.match_file(path):
        return SkipDecision(path=path, reason="excluded", detail=None)
    if path in hard_linked:
        return SkipDecision(path=path, reason="hard-link-alias", detail=hard_linked[path])
    if record.size_bytes > config.limits.max_file_size_mib * 1024 * 1024:
        return SkipDecision(
            path=path,
            reason="oversize",
            detail=f"{record.size_bytes} bytes > limits.max_file_size_mib {config.limits.max_file_size_mib}",
        )
    # NUL bytes are legal UTF-8 (tests/corpus.py's "binaryish" recipe proves
    # it), so this check cannot be folded into the utf8_valid ladder below: a
    # NUL-bearing file is risky (FR-015/EC-004) whether or not it happens to
    # decode as valid UTF-8. A BOM authoritatively claims the encoding (e.g. a
    # BOM'd UTF-16 file legitimately has NULs), so bom is None guards against
    # skipping those. Part 2 (content pass) refines this into the
    # utf16-suspect split from bytes and will relocate this decision there.
    if record.nul_bytes and record.encoding.bom is None:
        return SkipDecision(path=path, reason="nul-bytes", detail="NUL bytes present")
    enc = record.encoding
    if enc.bom is None and not enc.utf8_valid:
        if not config.encoding.detect:
            return SkipDecision(
                path=path, reason="low-confidence-encoding", detail="encoding detection disabled"
            )
        if enc.detected is None:
            return SkipDecision(path=path, reason="binary-suspect", detail="no encoding candidate")
        threshold = config.encoding.fail_below_confidence
        if enc.detected.confidence < threshold:
            return SkipDecision(
                path=path,
                reason="low-confidence-encoding",
                detail=f"confidence {enc.detected.confidence:.2f} < {threshold}",
            )
        floor = config.encoding.non_ascii_floor
        if record.non_ascii_bytes < floor:
            return SkipDecision(
                path=path,
                reason="below-non-ascii-floor",
                detail=f"{record.non_ascii_bytes} non-ASCII bytes < floor {floor}",
            )
    return None


def build_plan(
    inventory: Inventory,
    config: DocmendConfig,
    *,
    run_id: str,
    generated_at: str,
    inventory_ref: ArtifactRef,
    mint_id: Callable[[], uuid.UUID] = uuid.uuid7,
) -> Plan:
    log = get_logger(__name__)
    include = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.include)
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude)
    hard_linked = {
        path: f"inode {group.inode}: {', '.join(group.paths)}"
        for group in inventory.hard_link_groups
        for path in group.paths
    }

    actions: list[PlanAction] = []
    skips: list[SkipDecision] = [
        SkipDecision(path=link.path, reason="symlink", detail=f"-> {link.target}")
        for link in inventory.symlinks
    ]
    pending: list[FileRecord] = []
    for record in inventory.files:
        decision = _fact_skip(record, hard_linked, config, include, exclude)
        if decision is not None:
            skips.append(decision)
            log.debug("planned skip", path=record.path, reason=decision.reason)
        else:
            pending.append(record)

    # Part 2 (content pass) turns `pending` into actions/no-ops; until then a
    # pending file is deliberately absent from both lists (FR-017 plan half).
    del pending  # replaced by the content pass in the next task

    skips.sort(key=lambda s: s.path)
    return Plan(
        run_id=run_id,
        generated_at=generated_at,
        generated_by=f"docmend {__version__}",
        inventory_ref=inventory_ref,
        config=config.model_dump(mode="json"),
        actions=actions,
        skips=skips,
        totals=PlanTotals(actions=len(actions), skips=len(skips)),
        schema_version=PLAN_SCHEMA_VERSION,
    )
