"""Manifest 2.0 fixture builder shared by every manifest-consuming test.

Builds raw NDJSON documents (dicts), not models, so tests can express
adversarial mutations — wrong roots, gapped seqs, diverging immutable
fields — that the strict models would refuse to construct.
"""

import json
from pathlib import Path

from docmend.writer.manifest import (
    ManifestChain,
    ManifestHeader,
    ManifestRecord,
    ManifestSet,
    read_manifest_set,
)

RUN_ID = "run_20260706T000000Z_00006d"


def read_records(path: Path) -> list[ManifestRecord]:
    """The records of one validated manifest 2.0 file — the mechanical
    replacement for the deleted 1.x `read_manifest` in tests that only
    inspect mutation records."""
    return read_manifest_set(path).records


def chain_of(records: list[ManifestRecord], *, source_root: str = "/corpus") -> ManifestChain:
    """A synthetic single-set chain over arbitrary (possibly gappy) record
    subsets — for ENGINE tests that feed resume evidence directly, bypassing
    file-level validation the way a validated CLI read would have passed it.
    The reducer only folds records; header facts are inert here."""
    header = ManifestHeader.model_validate(header_doc(source_root=source_root))
    return ManifestChain(
        sets=[
            ManifestSet(
                header=header,
                records=records,
                path=Path("/synthetic-manifest.jsonl"),
                sha256=SHA_C,
            )
        ]
    )


OTHER_RUN_ID = "run_20260707T000000Z_00007e"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
UUID7 = "01980000-0000-7000-8000-000000000001"


def header_doc(**overrides: object) -> dict[str, object]:
    doc: dict[str, object] = {
        "schema": "docmend/manifest-header",
        "schema_version": "2.0",
        "run_id": RUN_ID,
        "kind": "apply",
        "source_root": "/corpus",
        "backup_root": None,
        "plan_sha256": SHA_C,
        "prior_manifest_sha256": None,
        "prior_attempt": None,
        "created_at": "2026-07-10T00:00:00+00:00",
    }
    doc.update(overrides)
    return doc


def record_doc(
    action_seq: int, *, result: str = "applied", **overrides: object
) -> dict[str, object]:
    """One raw mutation-record document. `action_seq` names the action
    (`{run}/aN`) and defaults the record's own seq; override `seq=` for a
    second record of the same action (e.g. its terminal)."""
    doc: dict[str, object] = {
        "schema": "docmend/manifest-record",
        "schema_version": "2.0",
        "run_id": RUN_ID,
        "action_id": f"{RUN_ID}/a{action_seq}",
        "docmend_id": UUID7,
        "seq": action_seq,
        "recorded_at": "2026-07-10T00:00:00+00:00",
        "operation": "rewrite",
        "original_path": f"/corpus/f{action_seq}.md",
        "target_path": f"/corpus/f{action_seq}.md",
        "backup_path": None,
        "before_sha256": SHA_A,
        "after_sha256": SHA_B,
        "result": result,
        "error": None,
        "overwritten_sha256": None,
        "overwritten_backup_path": None,
        "undoes_action_id": None,
        "undoes_run_id": None,
        "source_identity": None,
        "target_identity": None,
        "expected_published_identity": None,
    }
    doc.update(overrides)
    return doc


def write_set(path: Path, header: dict[str, object], *records: dict[str, object]) -> Path:
    lines = [json.dumps(doc, ensure_ascii=False) for doc in (header, *records)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
