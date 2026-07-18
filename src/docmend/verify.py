"""verify — read-only corpus + artifact validation (FR-014, IR-004, adr-0012).

Read-only (adr-0012, G-005 posture): reuses `discovery.scan`'s walk + facts and
reconciles the manifest/report against them; it mutates nothing and writes no
manifest. It yields findings; the CLI maps their presence to the adr-0012 exit
taxonomy (0 clean / 1 findings). Frontmatter is validated WHERE PRESENT
(FR-016, adr-0011): documents without frontmatter are legal — the v1 pipeline
emits none (RQ-008) — but a present block must parse safely and validate
against `schemas/frontmatter.schema.json`.
"""

import hashlib
from collections.abc import Iterable, Iterator
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from docmend.frontmatter import validate_frontmatter
from docmend.inventory import Inventory
from docmend.observability import ProgressHeartbeat
from docmend.writer.commit import InterferenceError, bind_file
from docmend.writer.manifest import (
    ManifestChain,
    ManifestInspection,
    reduce_lifecycle,
)

# LF-only per adr-0012. "none" (a file with no line endings) trivially has no CR
# and is compliant; every other census result ("crlf"/"cr"/"mixed") carries a CR.
_LF_ONLY = frozenset({"lf", "none"})


@dataclass(frozen=True)
class VerifyFinding:
    """One failed check on one file (adr-0012). `check` names the check family."""

    path: str
    check: str
    detail: str


def _record_boundaries[T](
    records: Iterable[T],
    *,
    heartbeat: ProgressHeartbeat | None,
    findings: list[VerifyFinding],
) -> Iterator[T]:
    """Advance cumulative verify progress after each yielded record returns."""
    if heartbeat is None:
        yield from records
        return
    processed, skipped, failed_before = heartbeat.counts
    findings_before = len(findings)
    for record in records:
        yield record
        processed += 1
        heartbeat.advance(
            processed=processed,
            skipped=skipped,
            failed=failed_before + len(findings) - findings_before,
        )


def check_content(
    inventory: Inventory, *, heartbeat: ProgressHeartbeat | None = None
) -> list[VerifyFinding]:
    """Content-check findings over a scanned corpus (adr-0012 v1 content checks).

    Reuses scan's own encoding/newline facts, so "verify passes" means exactly
    "scan sees clean output" — one detection code path, never a second opinion.
    """
    findings: list[VerifyFinding] = []
    for record in _record_boundaries(inventory.files, heartbeat=heartbeat, findings=findings):
        if not record.encoding.utf8_valid:
            findings.append(
                VerifyFinding(record.path, "encoding", "not UTF-8 decodable without replacement")
            )
        if record.newline_style not in _LF_ONLY:
            findings.append(
                VerifyFinding(
                    record.path, "newlines", f"line endings are {record.newline_style}, not LF-only"
                )
            )
    return findings


def check_frontmatter(
    inventory: Inventory, *, heartbeat: ProgressHeartbeat | None = None
) -> list[VerifyFinding]:
    """Frontmatter-validity findings where frontmatter is present (FR-016).

    Scoped to `.md` files — docmend's output format, the only place the DR-005
    contract applies; a `---` opener in a legacy `.txt` is body text, not a
    metadata claim. Files scan already flagged non-UTF-8 are skipped here: they
    cannot be decoded to look for a block, and the encoding finding from
    check_content already covers them (one defect, one finding).
    """
    findings: list[VerifyFinding] = []
    root = Path(inventory.source_root)
    for record in _record_boundaries(inventory.files, heartbeat=heartbeat, findings=findings):
        if not record.path.endswith(".md") or not record.encoding.utf8_valid:
            continue
        try:
            text = (root / record.path).read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(
                VerifyFinding(record.path, "frontmatter", f"unreadable ({exc.strerror or exc})")
            )
            continue
        detail = validate_frontmatter(text)
        if detail is not None:
            findings.append(VerifyFinding(record.path, "frontmatter", detail))
    return findings


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def check_discovery(inventory: Inventory) -> list[VerifyFinding]:
    """Report candidate evidence discovery could not certify as readable."""
    findings = [
        VerifyFinding(skip.path, f"discovery-{skip.reason}", skip.detail or skip.reason)
        for skip in inventory.skipped
        if skip.reason in ("unreadable", "timeout")
    ]
    candidate_evidence = bool(findings or inventory.symlinks)
    if not inventory.files and candidate_evidence:
        findings.append(
            VerifyFinding(
                inventory.requested_path,
                "zero-checked",
                "candidate evidence exists but no readable files were checked",
            )
        )
    return findings


def check_manifest_root(chain: ManifestChain, verified_root: Path) -> list[VerifyFinding]:
    """Require manifest evidence to describe the corpus being verified."""
    if not chain.sets:
        return []
    recorded = chain.sets[0].header.source_root
    if Path(recorded).resolve() == verified_root.resolve():
        return []
    return [
        VerifyFinding(
            recorded,
            "manifest-root",
            f"manifest source root does not match verified root {verified_root.resolve()}",
        )
    ]


def manifest_inspection_findings(inspection: ManifestInspection) -> list[VerifyFinding]:
    """Expose typed containment defects without reading their referenced paths."""
    return [
        VerifyFinding(path=finding.path, check=finding.check, detail=finding.detail)
        for finding in inspection.findings
    ]


def check_lifecycle(
    chain: ManifestChain, *, heartbeat: ProgressHeartbeat | None = None
) -> list[VerifyFinding]:
    """Report final mutation states that cannot certify an applied plan."""
    uncertified = frozenset({"pending-intent", "pending-restore", "restored", "restore-failed"})
    findings: list[VerifyFinding] = []
    records = sorted(reduce_lifecycle(chain).items())
    for action_id, lifecycle in _record_boundaries(records, heartbeat=heartbeat, findings=findings):
        if lifecycle.state in uncertified:
            findings.append(VerifyFinding(action_id, "lifecycle", lifecycle.state))
    return findings


def check_outputs(
    chain: ManifestChain,
    *,
    unsafe_action_ids: AbstractSet[str] = frozenset(),
    heartbeat: ProgressHeartbeat | None = None,
) -> list[VerifyFinding]:
    """Hash each final applied output once, skipping untrusted manifest paths."""
    findings: list[VerifyFinding] = []
    records = sorted(reduce_lifecycle(chain).items())
    for action_id, lifecycle in _record_boundaries(records, heartbeat=heartbeat, findings=findings):
        record = lifecycle.record
        if (
            lifecycle.state != "applied"
            or action_id in unsafe_action_ids
            or record.after_sha256 is None
        ):
            continue
        target = Path(record.target_path)
        try:
            live = bind_file(target).data
        except OSError, InterferenceError:
            findings.append(
                VerifyFinding(record.target_path, "hash", "applied output missing or unreadable")
            )
            continue
        if _sha(live) != record.after_sha256:
            findings.append(
                VerifyFinding(
                    record.target_path,
                    "hash",
                    "live hash does not match recorded after-hash",
                )
            )
    return findings


def _check_backup(
    path: Path,
    expected_sha256: str,
    *,
    action_id: str,
    role: Literal["source", "overwritten"],
) -> VerifyFinding | None:
    try:
        bound = bind_file(path)
    except (OSError, InterferenceError) as exc:
        return VerifyFinding(
            action_id,
            "backup",
            f"{role} backup missing or unreadable ({exc})",
        )
    if _sha(bound.data) == expected_sha256:
        return None
    recorded_hash = "before-hash" if role == "source" else "overwritten-hash"
    return VerifyFinding(
        action_id,
        "backup",
        f"{role} backup hash does not match recorded {recorded_hash}",
    )


def check_backups(
    chain: ManifestChain,
    *,
    unsafe_action_ids: AbstractSet[str] = frozenset(),
    heartbeat: ProgressHeartbeat | None = None,
) -> list[VerifyFinding]:
    """Verify each final applied action's trusted backup references once."""
    findings: list[VerifyFinding] = []
    records = sorted(reduce_lifecycle(chain).items())
    for action_id, lifecycle in _record_boundaries(records, heartbeat=heartbeat, findings=findings):
        if lifecycle.state != "applied" or action_id in unsafe_action_ids:
            continue
        record = lifecycle.record
        references: tuple[tuple[str | None, str | None, Literal["source", "overwritten"]], ...] = (
            (record.backup_path, record.before_sha256, "source"),
            (record.overwritten_backup_path, record.overwritten_sha256, "overwritten"),
        )
        for recorded_path, expected_sha256, role in references:
            if recorded_path is None or expected_sha256 is None:
                continue
            finding = _check_backup(
                Path(recorded_path),
                expected_sha256,
                action_id=action_id,
                role=role,
            )
            if finding is not None:
                findings.append(finding)
    return findings
