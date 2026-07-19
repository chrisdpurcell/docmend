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

import hashlib
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from docmend import __version__
from docmend.config import DocmendConfig
from docmend.inventory import FileRecord, Inventory
from docmend.observability import ProgressHeartbeat, get_logger
from docmend.plan import (
    PLAN_SCHEMA_VERSION,
    ActionProvenance,
    ArtifactRef,
    Plan,
    PlanAction,
    PlanTotals,
    SkipDecision,
)
from docmend.transform.dispatch import (
    Operation,
    apply_text_transforms,
    classify_suffix,
    non_whitespace_count,
)
from docmend.transform.encoding import decode_source
from docmend.watchdog import PerFileTimeoutError, per_file_watchdog


def _fact_skip(
    record: FileRecord,
    hard_linked: dict[str, str],
    config: DocmendConfig,
    include: PathSpec[GitIgnoreSpecPattern],
    exclude: PathSpec[GitIgnoreSpecPattern],
    scan_detect: bool | None,
) -> SkipDecision | None:
    path = record.path
    if not include.match_file(path):
        return SkipDecision(
            path=path, reason="excluded", detail="not matched by plan-time include patterns"
        )
    if exclude.match_file(path):
        return SkipDecision(
            path=path, reason="excluded", detail="matched a plan-time exclude pattern"
        )
    if path in hard_linked:
        return SkipDecision(path=path, reason="hard-link-alias", detail=hard_linked[path])
    limit_bytes = config.limits.max_file_size_mib * 1024 * 1024
    if record.size_bytes > limit_bytes:
        return SkipDecision(
            path=path,
            reason="oversize",
            detail=(
                f"{record.size_bytes} bytes > {config.limits.max_file_size_mib} MiB limit "
                f"({limit_bytes} bytes)"
            ),
        )
    # NUL bytes are legal UTF-8 (tests/corpus.py's "binaryish" recipe proves
    # it), so this ladder deliberately never runs at all for a NUL-bearing
    # file (the `not record.nul_bytes` guard below). That makes the ladder
    # itself indifferent to `detected`'s value for NUL-bearing files — but
    # for the record: discovery's legacy-detection gate (adr-0009) skips
    # charset-normalizer specifically for NUL-bearing files, so `detected` is
    # None only for the no-BOM, non-UTF-8 NUL files that would otherwise
    # reach this branch. A BOM'd NUL file, or one that is still strictly
    # UTF-8-valid (NUL is a legal code point), gets `detected` set from the
    # deterministic rungs regardless of the NUL bytes. Every NUL-bearing file
    # instead falls through here into `pending`, where the content pass does
    # the byte-accurate nul-bytes vs utf16-suspect split (EC-004/EC-010) and,
    # for BOM'd files, decodes normally since a BOM authoritatively claims the
    # encoding.
    enc = record.encoding
    if not record.nul_bytes and enc.bom is None and not enc.utf8_valid:
        if not config.encoding.detect:
            return SkipDecision(
                path=path, reason="low-confidence-encoding", detail="encoding detection disabled"
            )
        if enc.detected is None:
            # scan_detect is None for a pre-1.1 inventory where the fact is
            # unknown (inventory.py ScanConfigRecord); only scan_detect is True
            # means "detection ran and found no candidate" -> binary-suspect.
            # Both False (disabled at scan) and None (fact absent) mean we never
            # looked here, so report the low-confidence skip instead.
            if scan_detect is not True:
                return SkipDecision(
                    path=path,
                    reason="low-confidence-encoding",
                    detail="encoding detection was not run at scan",
                )
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


def _utf16_suspect(data: bytes) -> bool:
    """BOM-less interleaved-NUL pattern (EC-010, OQ-026).

    UTF-16 text over an ASCII-heavy corpus puts ~50% NULs on one byte parity;
    thresholds (>=25% NUL density, >=90% single-parity concentration) are
    internal heuristics, deliberately not configurable — the outcome either
    way is a skip, only the recorded reason differs.
    """
    if len(data) < 4:
        return False
    nuls = data.count(0)
    if not nuls or nuls / len(data) < 0.25:
        return False
    even = data[::2].count(0)
    return max(even, nuls - even) / nuls >= 0.90


def _read_verified(full: Path, record: FileRecord) -> bytes | SkipDecision:
    try:
        current_size = full.stat().st_size
    except OSError as exc:
        return SkipDecision(path=record.path, reason="unreadable", detail=str(exc))
    if current_size != record.size_bytes:
        # NFR-001: fail fast on a size mismatch before reading — a file that
        # grew after scan (e.g. still being written to) must never have its
        # full, now-larger contents pulled into memory just to compute a hash
        # that was always going to mismatch. Equal-size changes (same length,
        # different bytes) still fall through to the read + hash check below.
        return SkipDecision(
            path=record.path,
            reason="changed-since-scan",
            detail=f"inventory size {record.size_bytes} bytes, now {current_size} bytes",
        )
    try:
        data = full.read_bytes()
    except OSError as exc:
        return SkipDecision(path=record.path, reason="unreadable", detail=str(exc))
    digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
    if digest != record.sha256:
        return SkipDecision(
            path=record.path,
            reason="changed-since-scan",
            detail=f"inventory {record.sha256}, now {digest}",
        )
    return data


def build_plan(
    inventory: Inventory,
    config: DocmendConfig,
    *,
    run_id: str,
    generated_at: str,
    inventory_ref: ArtifactRef,
    mint_id: Callable[[], uuid.UUID] = uuid.uuid7,
    heartbeat: ProgressHeartbeat | None = None,
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
    skips: list[SkipDecision] = []
    processed = 0

    def advance() -> None:
        nonlocal processed
        processed += 1
        if heartbeat is not None:
            heartbeat.advance(processed=processed, skipped=len(skips), failed=0)

    for link in inventory.symlinks:
        # A plan-time exclude added after the scan can cover a symlink the
        # inventory already recorded; the more specific "excluded" reason
        # (matching the fact-gate ladder's own exclude branch above) wins
        # over the generic "symlink" reason so the two skip paths agree on
        # why a filtered symlink is never planned for mutation.
        if exclude.match_file(link.path):
            skips.append(
                SkipDecision(
                    path=link.path, reason="excluded", detail="matched a plan-time exclude pattern"
                )
            )
        else:
            skips.append(SkipDecision(path=link.path, reason="symlink", detail=f"-> {link.target}"))
        advance()
    pending: list[FileRecord] = []
    for record in inventory.files:
        decision = _fact_skip(
            record, hard_linked, config, include, exclude, inventory.scan_config.encoding_detect
        )
        if decision is not None:
            skips.append(decision)
            log.debug("planned skip", path=record.path, reason=decision.reason)
            advance()
        else:
            pending.append(record)
            if heartbeat is not None:
                heartbeat.advance(processed=processed, skipped=len(skips), failed=0)

    # Part 2: turn `pending` into actions, content-derived skips, or no-ops
    # (FR-017's third state — a file that needs nothing is in neither list).
    # Output ledger (rev 0.26, DMR-01): EVERY emitted action claims its
    # effective output path — target_path for renames, the file's own path for
    # in-place rewrites — so no two actions in one plan can share an output
    # (and therefore no two backups can share a key). The old set tracked only
    # rename targets, which let an in-place rewrite of a.md and a.txt -> a.md
    # both claim a.md's bytes. `pending` is processed in the globally sorted
    # order set by discovery.py, so the lexicographically first claimant wins
    # deterministically; never policy-overridable — `overwrite` licenses
    # clobbering a pre-existing target (AW-002), not another planned action's
    # output (G-005). Values are the claiming source path, for skip details.
    claimed_outputs: dict[str, str] = {}
    inventory_paths = {f.path for f in inventory.files}
    source_root = Path(inventory.source_root)
    seq = 0
    pending_started = 0
    for record in pending:
        if pending_started:
            advance()
        pending_started += 1
        # FR-019: the content pass — verified read + decode + transform
        # prediction — is this layer's unbounded per-file work; catastrophic
        # regex backtracking in an FR-009 transform (R-007) surfaces here. The
        # watchdog re-arms per file and never spans the writer (the writer is a
        # different layer entirely; see docmend.watchdog's scope contract).
        start = time.monotonic()
        try:
            with per_file_watchdog(config.limits.per_file_timeout):
                result = _read_verified(source_root / record.path, record)
                if isinstance(result, SkipDecision):
                    skips.append(result)
                    log.debug("planned skip", path=record.path, reason=result.reason)
                    continue
                data = result
                enc = record.encoding
                if record.nul_bytes and enc.bom is None:
                    reason = "utf16-suspect" if _utf16_suspect(data) else "nul-bytes"
                    detail = (
                        "BOM-less interleaved-NUL pattern"
                        if reason == "utf16-suspect"
                        else "NUL bytes present"
                    )
                    skips.append(SkipDecision(path=record.path, reason=reason, detail=detail))
                    log.debug("planned skip", path=record.path, reason=reason)
                    continue
                decode_encoding = enc.detected.name if enc.detected else "utf-8"
                try:
                    text = decode_source(data, bom=enc.bom, encoding_name=decode_encoding)
                except UnicodeDecodeError as exc:
                    skips.append(
                        SkipDecision(
                            path=record.path,
                            reason="decode-replacement",
                            detail=f"{decode_encoding}: undecodable byte at offset {exc.start}",
                        )
                    )
                    log.debug("planned skip", path=record.path, reason="decode-replacement")
                    continue
                except LookupError:
                    # Theoretical: a detector could in principle name a codec
                    # Python's registry doesn't have (charset-normalizer's
                    # candidate names are not currently validated against
                    # `codecs`). Treated the same as an undecodable file rather
                    # than propagating — an unrecognized codec name is not this
                    # file's fault to abort the whole run over.
                    skips.append(
                        SkipDecision(
                            path=record.path,
                            reason="decode-replacement",
                            detail=f"unknown codec {decode_encoding!r}",
                        )
                    )
                    log.debug("planned skip", path=record.path, reason="decode-replacement")
                    continue
                file_class = classify_suffix(record.suffix)
                ws = config.whitespace
                transformed, operations = apply_text_transforms(
                    text,
                    file_class,
                    trim_trailing_ws=ws.trim_trailing,
                    final_newline=ws.ensure_final_newline,
                    collapse_max=ws.collapse_blank_lines,
                    tab_width=ws.tab_width if ws.normalize_tabs else None,
                )
                ops: list[Operation] = []
                if enc.bom is not None or decode_encoding != "utf-8":
                    ops.append("reencode")
                ops.extend(operations)
                if non_whitespace_count(transformed) < non_whitespace_count(text):
                    # Unreachable with correct transforms (adr-0016's dispatch
                    # never removes non-whitespace content); a hit here means a
                    # transform bug, logged at error level besides the skip.
                    log.error("shrink invariant tripped", path=record.path)
                    skips.append(
                        SkipDecision(
                            path=record.path,
                            reason="shrink-invariant",
                            detail="non-whitespace count would decrease",
                        )
                    )
                    continue
                target: str | None = None
                if (
                    file_class == "text"
                    and record.suffix.lower() == ".txt"
                    and config.rename.txt_to_md
                ):
                    candidate = record.path[: -len(record.suffix)] + ".md"
                    if candidate in claimed_outputs:
                        skips.append(
                            SkipDecision(
                                path=record.path,
                                reason="collision",
                                detail=(
                                    f"target {candidate} already claimed by an "
                                    f"earlier action this run ({claimed_outputs[candidate]})"
                                ),
                            )
                        )
                        log.debug("planned skip", path=record.path, reason="collision")
                        continue
                    collides = candidate in inventory_paths or (source_root / candidate).exists()
                    if collides and config.rename.on_collision != "overwrite":
                        skips.append(
                            SkipDecision(
                                path=record.path,
                                reason="collision",
                                detail=(
                                    f"target {candidate} exists "
                                    f"(policy {config.rename.on_collision})"
                                ),
                            )
                        )
                        log.debug("planned skip", path=record.path, reason="collision")
                        continue
                    target = candidate
                    ops.append("rename")
                if not ops:
                    continue  # no-op: neither action nor skip (FR-017 plan half)
                effective_output = target if target is not None else record.path
                if effective_output in claimed_outputs:
                    # In-place rewrite whose own path an earlier rename claimed
                    # (the rename is about to replace these bytes; executing
                    # both is the DMR-01 double-claim).
                    skips.append(
                        SkipDecision(
                            path=record.path,
                            reason="collision",
                            detail=(
                                f"output path {effective_output} already claimed by an "
                                f"earlier action this run ({claimed_outputs[effective_output]})"
                            ),
                        )
                    )
                    log.debug("planned skip", path=record.path, reason="collision")
                    continue
                claimed_outputs[effective_output] = record.path
                seq += 1
                actions.append(
                    PlanAction(
                        action_id=f"{run_id}/a{seq}",
                        docmend_id=str(mint_id()),
                        path=record.path,
                        source_sha256=record.sha256,
                        source_size_bytes=record.size_bytes,
                        operations=ops,
                        target_path=target,
                        provenance=ActionProvenance(
                            detected_encoding=enc.detected, newline_style=record.newline_style
                        ),
                    )
                )
                log.debug("planned action", path=record.path, operations=ops, target=target)
        except PerFileTimeoutError:
            # FR-019/ERR-009: bound the per-file content work; record the
            # timeout with path + elapsed and let the batch continue.
            elapsed = time.monotonic() - start
            skips.append(
                SkipDecision(
                    path=record.path,
                    reason="timeout",
                    detail=f"exceeded {config.limits.per_file_timeout}s (elapsed {elapsed:.2f}s)",
                )
            )
            log.warning(
                "content pass timed out",
                path=record.path,
                elapsed=round(elapsed, 3),
                err="ERR-009",
            )
            continue

    if pending_started:
        advance()

    skips.sort(key=lambda s: s.path)
    if config.write.backup_dir is not None and not config.write.backup_dir.is_absolute():
        # The reviewed snapshot, not apply's cwd, decides the backup home
        # (codex CR-NEW-002): re-resolving a relative path against the
        # *apply* cwd would silently move backups, or make the gate refuse.
        config = config.model_copy(
            update={
                "write": config.write.model_copy(
                    update={"backup_dir": config.write.backup_dir.resolve()}
                )
            }
        )
    return Plan(
        run_id=run_id,
        generated_at=generated_at,
        generated_by=f"docmend {__version__}",
        inventory_ref=inventory_ref,
        source_root=inventory.source_root,
        config=config.model_dump(mode="json"),
        actions=actions,
        skips=skips,
        totals=PlanTotals(actions=len(actions), skips=len(skips)),
        schema_version=PLAN_SCHEMA_VERSION,
    )
