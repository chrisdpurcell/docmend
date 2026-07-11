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
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from docmend.frontmatter import validate_frontmatter
from docmend.inventory import Inventory
from docmend.report import Report
from docmend.writer.manifest import ManifestRecord

# LF-only per adr-0012. "none" (a file with no line endings) trivially has no CR
# and is compliant; every other census result ("crlf"/"cr"/"mixed") carries a CR.
_LF_ONLY = frozenset({"lf", "none"})


@dataclass(frozen=True)
class VerifyFinding:
    """One failed check on one file (adr-0012). `check` names the check family."""

    path: str
    check: str
    detail: str


def check_content(inventory: Inventory) -> list[VerifyFinding]:
    """Content-check findings over a scanned corpus (adr-0012 v1 content checks).

    Reuses scan's own encoding/newline facts, so "verify passes" means exactly
    "scan sees clean output" — one detection code path, never a second opinion.
    """
    findings: list[VerifyFinding] = []
    for record in inventory.files:
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


def check_frontmatter(inventory: Inventory) -> list[VerifyFinding]:
    """Frontmatter-validity findings where frontmatter is present (FR-016).

    Scoped to `.md` files — docmend's output format, the only place the DR-005
    contract applies; a `---` opener in a legacy `.txt` is body text, not a
    metadata claim. Files scan already flagged non-UTF-8 are skipped here: they
    cannot be decoded to look for a block, and the encoding finding from
    check_content already covers them (one defect, one finding).
    """
    findings: list[VerifyFinding] = []
    root = Path(inventory.source_root)
    for record in inventory.files:
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


def reconcile_manifest(records: Sequence[ManifestRecord]) -> list[VerifyFinding]:
    """Reconcile applied outputs against the manifest (adr-0012, FR-014).

    The FR-014 'hash mismatch' defect class: each applied record's live target
    must still hash to the after_sha256 the manifest recorded at apply time.
    Only result=='applied' records with a recorded after-hash are reconcilable;
    'failed' records left the original untouched (nothing to compare against).
    """
    findings: list[VerifyFinding] = []
    for record in records:
        if record.result != "applied" or record.after_sha256 is None:
            continue
        target = Path(record.target_path)
        try:
            live = target.read_bytes()
        except OSError:
            findings.append(
                VerifyFinding(record.target_path, "hash", "applied output missing or unreadable")
            )
            continue
        if _sha(live) != record.after_sha256:
            findings.append(
                VerifyFinding(
                    record.target_path, "hash", "live hash does not match recorded after-hash"
                )
            )
    return findings


def reconcile_report(report: Report, records: Sequence[ManifestRecord]) -> list[VerifyFinding]:
    """Cross-artifact accounting (FR-014 'skipped-file accounting / artifact
    internal consistency', OQ-006): every applied report outcome must have an
    applied manifest record and vice versa. The intra-report totals rule
    (totals == outcome counts) is already enforced by `artifacts.read_report`;
    this is the BETWEEN-artifacts half it cannot see.
    """
    findings: list[VerifyFinding] = []
    applied_outcomes = {o.action_id for o in report.outcomes if o.status == "applied"}
    applied_records = {r.action_id for r in records if r.result == "applied"}
    for action_id in sorted(applied_outcomes - applied_records):
        findings.append(
            VerifyFinding(
                action_id, "accounting", "report records applied but manifest has no applied record"
            )
        )
    for action_id in sorted(applied_records - applied_outcomes):
        findings.append(
            VerifyFinding(
                action_id,
                "accounting",
                "manifest records applied but report has no applied outcome",
            )
        )
    # A duplicate applied record for one action would slip past the set logic.
    duplicates = [
        a
        for a, n in Counter(r.action_id for r in records if r.result == "applied").items()
        if n > 1
    ]
    for action_id in sorted(duplicates):
        findings.append(
            VerifyFinding(action_id, "accounting", "manifest holds duplicate applied records")
        )
    return findings
