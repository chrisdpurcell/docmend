"""Artifact schema registry, validation, and atomic IO (adr-0005, IR-007, OQ-018).

Cross-file contracts:
- The hand-authored schemas in ``docmend/schemas/*.schema.json`` are the durable
  external contract; they are loaded via ``importlib.resources`` so validation
  works from an installed wheel, not only a repo checkout.
- One compiled ``Draft202012Validator`` per schema, cached for the process
  lifetime (OQ-018: reusing the validator caps validation CPU); ``format`` is
  asserted, not annotation-only, via the draft's FORMAT_CHECKER — the reason the
  ``format-nongpl`` extra is installed.
- Artifacts are written atomically (temp file + fsync + ``os.replace`` in the
  same directory): scan/plan have no resume machinery precisely because their
  artifact appears complete or not at all (OQ-003). This writes docmend's OWN
  artifacts; it is not the library-mutating writer layer (§8.2.3), which lands
  at MS-3 with the full FR-005/FR-006 safety machinery.
- :class:`ArtifactError` covers both directions: an unreadable/invalid input
  artifact (ERR-008 family — the CLI maps it to exit 2) and the should-never-
  happen case of docmend producing a document its own schema rejects.
"""

import hashlib
import json
import os
from collections import Counter
from collections.abc import Iterator
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Literal, Protocol, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError

from docmend.inventory import Inventory
from docmend.plan import Plan
from docmend.report import Report

type ArtifactKind = Literal["inventory", "plan", "report", "manifest"]

ARTIFACT_KINDS: tuple[ArtifactKind, ...] = ("inventory", "plan", "report", "manifest")


class ArtifactError(Exception):
    """An artifact could not be read, parsed, or validated (exit 2, §18.5)."""


class _CompiledValidator(Protocol):
    """The slice of jsonschema's validator API docmend uses.

    jsonschema's own annotations are partially unknown under basedpyright
    strict; this Protocol is the typed seam (instances are cast to it once,
    at compile time in :func:`validator_for`).
    """

    def iter_errors(self, instance: object) -> Iterator[SchemaValidationError]: ...


def load_schema(kind: ArtifactKind) -> dict[str, object]:
    """Return the checked-in JSON Schema for one artifact kind."""
    text = (resources.files("docmend.schemas") / f"{kind}.schema.json").read_text("utf-8")
    schema: dict[str, object] = json.loads(text)
    return schema


@cache
def validator_for(kind: ArtifactKind) -> _CompiledValidator:
    schema = load_schema(kind)
    Draft202012Validator.check_schema(schema)  # pyright: ignore[reportUnknownMemberType]
    return cast(
        "_CompiledValidator",
        Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER),
    )


def validate_artifact(kind: ArtifactKind, document: object) -> None:
    """Validate one artifact document (or one manifest record) against its schema."""
    errors = sorted(validator_for(kind).iter_errors(document), key=lambda e: e.json_path)
    if errors:
        findings = "; ".join(f"{e.json_path}: {e.message}" for e in errors)
        msg = f"{kind} artifact failed schema validation — {findings}"
        raise ArtifactError(msg)


def write_json_artifact(document: dict[str, object], path: Path) -> None:
    """Atomically write one JSON-document artifact (temp + fsync + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(document, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


def write_inventory(inventory: Inventory, path: Path) -> None:
    """Validate a produced inventory against the external contract, then persist it."""
    document: dict[str, object] = inventory.model_dump(mode="json")
    # Self-check before touching disk: if docmend emits a document its own
    # checked-in schema rejects, that is a defect to fail loudly on, not an
    # artifact to write.
    validate_artifact("inventory", document)
    write_json_artifact(document, path)


def read_inventory(path: Path) -> Inventory:
    """Load and validate an inventory artifact (ERR-008 semantics on failure)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"{path}: cannot read inventory artifact ({exc.strerror or exc})"
        raise ArtifactError(msg) from exc
    try:
        document: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"{path}: not valid JSON — {exc}"
        raise ArtifactError(msg) from exc
    validate_artifact("inventory", document)
    return Inventory.model_validate(document)


def write_plan(plan: Plan, path: Path) -> None:
    """Validate a produced plan against the external contract, then persist it."""
    document: dict[str, object] = plan.model_dump(mode="json")
    # Self-check before touching disk: if docmend emits a document its own
    # checked-in schema rejects, that is a defect to fail loudly on, not an
    # artifact to write.
    validate_artifact("plan", document)
    write_json_artifact(document, path)


def read_plan(path: Path) -> Plan:
    """Load and validate a plan artifact (ERR-008 semantics on failure)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"{path}: cannot read plan artifact ({exc.strerror or exc})"
        raise ArtifactError(msg) from exc
    try:
        document: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"{path}: not valid JSON — {exc}"
        raise ArtifactError(msg) from exc
    validate_artifact("plan", document)
    return Plan.model_validate(document)


def write_report(report: Report, path: Path) -> None:
    """Validate a produced report, enforce DR-003 count reconciliation, persist."""
    counts = Counter(outcome.status for outcome in report.outcomes)
    expected = {
        "applied": report.totals.applied,
        "would_apply": report.totals.would_apply,
        "skipped": report.totals.skipped,
        "failed": report.totals.failed,
    }
    actual = {key: counts.get(key, 0) for key in expected}
    if expected != actual:
        msg = f"report totals {expected} do not reconcile with outcomes {actual} (DR-003)"
        raise ArtifactError(msg)
    document: dict[str, object] = report.model_dump(mode="json")
    validate_artifact("report", document)
    write_json_artifact(document, path)


def read_report(path: Path) -> Report:
    """Load and validate a report artifact (ERR-008 semantics on failure)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"{path}: cannot read report artifact ({exc.strerror or exc})"
        raise ArtifactError(msg) from exc
    try:
        document: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"{path}: not valid JSON — {exc}"
        raise ArtifactError(msg) from exc
    validate_artifact("report", document)
    return Report.model_validate(document)


def sha256_of_file(path: Path) -> str:
    """Hash an artifact file for cross-artifact references (adr-0005 identity fields)."""
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"
