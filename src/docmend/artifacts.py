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
import secrets
from collections import Counter
from collections.abc import Iterable, Iterator
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Literal, Protocol, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from docmend.inventory import Inventory
from docmend.plan import Plan
from docmend.report import Report

# "frontmatter" is the product-document schema (DR-005, adr-0011), not a run
# artifact — it rides the same registry so its validator is compiled once and
# works from an installed wheel like the other four.
type ArtifactKind = Literal["inventory", "plan", "report", "manifest", "frontmatter"]

ARTIFACT_KINDS: tuple[ArtifactKind, ...] = (
    "inventory",
    "plan",
    "report",
    "manifest",
    "frontmatter",
)


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


def guard_artifact_destination(
    destination: Path,
    *,
    corpus_root: Path | None,
    input_artifacts: Iterable[Path] = (),
    artifact_root: Path | None = None,
    exclude: PathSpec[GitIgnoreSpecPattern] | None = None,
) -> str | None:
    """One source-aware preflight for every CLI artifact write (rev 0.26
    IR-007, adr-0021, DMR-02): docmend's own artifacts must never be able to
    mutate the corpus they describe, and a refused write must precede the
    pipeline, not follow it. Returns the refusal message, or None when safe.

    Containment is judged on TWO candidates, because publication is
    tmp.replace(destination): the LEXICAL directory entry the replace swaps
    (resolved parent + final name, final component deliberately not followed)
    and the fully RESOLVED referent. An in-corpus name aliasing an external
    file mutates the corpus's directory entry; an external name aliasing an
    in-corpus file mutates corpus bytes — both must refuse.

    The .docmend/ carve-out (adr-0021) is licensed PER DESTINATION: a
    candidate inside the corpus is allowed only when it lies under
    `artifact_root` AND its own corpus-relative path matches `exclude` — a
    gitignore negation that re-includes one destination withdraws exactly
    that destination's license, and an operator-replaced exclude set
    withdraws the root wholesale.
    """
    lexical = destination.parent.resolve() / destination.name
    resolved = destination.resolve()
    if resolved.exists() and not resolved.is_file():
        return f"{destination}: artifact destination is not a regular file"
    for artifact in input_artifacts:
        if resolved == Path(artifact).resolve():
            return (
                f"{destination}: artifact destination aliases an input artifact "
                f"of this invocation ({artifact})"
            )
    if corpus_root is None:
        return None
    root = corpus_root.resolve()
    licensed_root = artifact_root.resolve() if artifact_root is not None else None
    for candidate in {lexical, resolved}:
        if not candidate.is_relative_to(root):
            continue
        licensed = (
            licensed_root is not None
            and candidate.is_relative_to(licensed_root)
            and exclude is not None
            and exclude.match_file(candidate.relative_to(root).as_posix())
        )
        if not licensed:
            return (
                f"{destination}: artifact destination resolves inside the corpus "
                f"root {root} (only excluded destinations under the canonical "
                f"artifact root are legal in-corpus writes; adr-0021)"
            )
    return None


def write_json_artifact(document: dict[str, object], path: Path) -> None:
    """Atomically write one JSON-document artifact (random O_EXCL temp + fsync +
    os.replace). Staging is randomized per attempt (rev 0.26, adr-0021): the
    old fixed '<name>.tmp' sibling was a predictable truncation target and a
    permanent retry blocker after a hard kill; EEXIST on a candidate is a name
    collision to retry, never an environmental failure. The temp is unlinked
    on EVERY unpublished exit — json.dump's TypeError/ValueError included, not
    only OSError. The 0o666 create mode is masked by the process umask AT
    os.open (kernel-side), so artifact modes stay exactly what plain open()
    produced before — permission POLICY is deliberately not decided here
    (deferred to the observability sub-project; plan-review F6/adr-0021
    amendment).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(8):
        tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError:
            continue
        break
    else:
        msg = f"{path}: could not allocate a staging name in 8 attempts"
        raise OSError(msg)
    published = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(document, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(path)
        published = True
    finally:
        if not published:
            tmp.unlink(missing_ok=True)


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
