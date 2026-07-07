"""verify — read-only corpus + artifact validation (FR-014, IR-004, adr-0012).

Read-only (adr-0012, G-005 posture): reuses `discovery.scan`'s walk + facts and
reconciles the manifest/report against them; it mutates nothing and writes no
manifest. It yields findings; the CLI maps their presence to the adr-0012 exit
taxonomy (0 clean / 1 findings). Frontmatter validation (FR-016) is deferred with
the frontmatter feature — the v1 pipeline emits none (RQ-008).
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from docmend.inventory import Inventory
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


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def reconcile_manifest(records: list[ManifestRecord]) -> list[VerifyFinding]:
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
