"""Manifest 2.0 writer/reader — the DR-004 append-only NDJSON ledger (adr-0005, adr-0019).

Cross-file contracts:
- Line 1 is the fsync'd header envelope (run, root, plan, backup-store,
  attempt lineage); every later line is one mutation record, appended and
  fsync'd immediately after its mutation step (spec 12.3). A crash loses at
  most the trailing line — exactly what the AOF torn-tail rule tolerates.
- Paths are ABSOLUTE (decision 7): `docmend restore` has no PATH argument
  (IR-008) and must locate files from the manifest alone; containment against
  the header's source_root is validated BEFORE any consumer touches them.
- `read_manifest_set` validates one file; `read_manifest_chain` (Plan B
  Task 3) proves the hash links across files; `reduce_lifecycle` (Task 4) is
  the single lifecycle authority for resume, restore, and verify.
- Any 1.x manifest is rejected with the clean-break operator message —
  there is deliberately no 1.x read path (adr-0019; no real-library runs
  exist, so compatibility would only preserve the DMR-03 trust hole).
"""

import hashlib
import json
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Annotated, Literal, Self, TextIO, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from docmend.artifacts import ArtifactError, validate_artifact
from docmend.inventory import RunId, Sha256
from docmend.lineage import ObjectIdentity, PriorAttempt
from docmend.observability import get_logger
from docmend.plan import ActionId, DocmendId
from docmend.report import ErrorInfo
from docmend.writer.atomic import fsync_dir

MANIFEST_SCHEMA_VERSION = "2.0"
MANIFEST_HEADER_SCHEMA_VERSION = "2.0"

#: The clean-break operator message (adr-0019): 2.0 carries no 1.x read path.
CLEAN_BREAK_MESSAGE = (
    "this manifest was written by docmend 1.x; restore pre-2.0 runs with docmend 1.0.2"
)


class ManifestContainmentError(ArtifactError):
    """A manifest references paths outside its recorded roots (source_root
    containment or the F5 BackupStore trust boundary). Safety refusal — the
    CLI maps it to exit 3 in restore/resume (adr-0012), unlike its parent's
    exit-2 artifact-input class."""


type ManifestOperation = Literal["rename", "rewrite", "rename_and_rewrite"]
type ManifestKind = Literal["apply", "restore"]


class ManifestHeader(BaseModel):
    """Line 1 of every 2.0 manifest (adr-0019: the header envelope anchoring
    run, root, plan, backup-store, and attempt-lineage facts that records were
    previously trusted to repeat per line).

    - `backup_root` is THIS run's resolved tool-backup root, null when the run
      took no tool backups — restore runs always carry null (their inverse
      records hold no backup references; Plan B review CR-NEW-003).
    - `prior_manifest_sha256` is the mutation-ledger subchain link; null only
      on the root manifest of a chain.
    - `prior_attempt` is the redundant attempt-lineage edge (also stamped on
      the run's report); a ROOT manifest may carry a report-flavored edge —
      its predecessor attempts were report-only and produced no manifest.
    """

    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
    )

    schema_kind: Literal["docmend/manifest-header"] = Field(
        default="docmend/manifest-header", alias="schema"
    )
    schema_version: Annotated[str, Field(pattern=r"^2\.\d+$")] = MANIFEST_HEADER_SCHEMA_VERSION
    run_id: RunId
    kind: ManifestKind
    source_root: Annotated[str, Field(min_length=1)]
    backup_root: str | None
    plan_sha256: Sha256
    prior_manifest_sha256: Sha256 | None
    prior_attempt: PriorAttempt | None
    created_at: str


class ManifestRecord(BaseModel):
    """One mutation record (DR-004) — one NDJSON line, restorable in isolation."""

    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
    )

    schema_kind: Literal["docmend/manifest-record"] = Field(
        default="docmend/manifest-record", alias="schema"
    )
    schema_version: Annotated[str, Field(pattern=r"^2\.\d+$")] = MANIFEST_SCHEMA_VERSION
    run_id: RunId
    action_id: ActionId
    docmend_id: DocmendId
    seq: Annotated[int, Field(ge=1)]
    recorded_at: str
    operation: ManifestOperation
    original_path: Annotated[str, Field(min_length=1)]
    target_path: Annotated[str, Field(min_length=1)]
    backup_path: str | None
    before_sha256: Sha256
    after_sha256: Sha256 | None
    # 2.0 (adr-0019): EVERY mutation kind journals `intent` before any corpus
    # name is touched and a terminal after. after_sha256 on an intent holds the
    # EXPECTED output hash. A dangling intent (no terminal after it in the
    # chain) is the evidence a kill landed inside that mutation's window; the
    # adjudication table decides from disk state + the identities below.
    result: Literal["applied", "failed", "intent"]
    error: ErrorInfo | None
    overwritten_sha256: Sha256 | None = None
    overwritten_backup_path: str | None = None
    # 2.0 restore lineage: an inverse record names the exact apply action it
    # undoes — the reducer never infers the relationship from paths or clocks.
    # Set together or not at all; non-null exactly in restore-kind sets.
    undoes_action_id: ActionId | None = None
    undoes_run_id: RunId | None = None
    # 2.0 durable object identities (design F4 rounds 3-4), persisted in the
    # INTENT before mutation: the validated source object, the overwrite
    # target when one existed, and the identity the published output will
    # have (the staged inode for replacement publishes; the source inode for
    # pure renames). The terminal CONFIRMS the same values — divergence is a
    # lifecycle violation. Null on pre-mutation `failed` records.
    source_identity: ObjectIdentity | None = None
    target_identity: ObjectIdentity | None = None
    expected_published_identity: ObjectIdentity | None = None

    @model_validator(mode="after")
    def _undoes_paired(self) -> Self:
        if (self.undoes_action_id is None) != (self.undoes_run_id is None):
            msg = "undoes_action_id and undoes_run_id are set together or not at all"
            raise ValueError(msg)
        return self


class ManifestWriter:
    """Append-only, per-record-durable NDJSON writer (single-writer, OQ-027).

    2.0: the fsync'd header is written at lazy open, BEFORE the first record —
    so a manifest file, once it exists, always carries its run/root/plan/
    lineage envelope. A write run in which every action skips still leaves NO
    file (the lazy-open contract): a header-only file therefore means a run
    was killed between its header and its first record — a valid, empty set.
    """

    def __init__(
        self,
        path: Path,
        *,
        header: ManifestHeader,
        now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(),
    ) -> None:
        self._path = path
        self._header = header
        self._now = now
        self._seq = 0
        self._fh: TextIO | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def append(self, record: ManifestRecord) -> ManifestRecord:
        if self._fh is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self._path.open("a", encoding="utf-8")
            # The durability claim covers the file NAME too: fsync(2) on the
            # file alone does not persist a newly created directory entry
            # (codex CR-NEW-005), so the first append also fsyncs the parent.
            fsync_dir(self._path.parent)
            header_doc = self._header.model_dump(mode="json")
            validate_artifact("manifest-header", header_doc)
            self._fh.write(json.dumps(header_doc, ensure_ascii=False) + "\n")
            self._fh.flush()
            os.fsync(self._fh.fileno())
        self._seq += 1
        stamped = record.model_copy(update={"seq": self._seq, "recorded_at": self._now()})
        document = stamped.model_dump(mode="json")
        # Self-check before disk, mirroring write_inventory/write_plan.
        validate_artifact("manifest", document)
        self._fh.write(json.dumps(document, ensure_ascii=False) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        return stamped

    def close(self) -> None:
        if self._fh is not None and not self._fh.closed:
            self._fh.close()

    @property
    def path(self) -> Path:
        return self._path


def manifest_sha256(path: Path) -> str:
    """`sha256:<hex>` of a CLOSED manifest file's bytes — the chain-link and
    attempt-lineage currency (adr-0019). Manifests are closed before any
    successor hashes them, so the value is stable (a torn tail stays torn)."""
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


@dataclass(frozen=True)
class ManifestSet:
    """One validated manifest file: header envelope plus its records.

    `sha256` is filled by chain reading (`read_manifest_chain` hashes every
    non-tip file to prove the links); a set read in isolation carries None.
    """

    header: ManifestHeader
    records: list[ManifestRecord]
    path: Path
    sha256: str | None = None


#: Fields an action's intent and terminal record must agree on (adr-0019
#: immutable-field rule) — only result/error/seq/recorded_at (and the
#: set-scope run_id, for adjudication terminals appended by a later run)
#: may differ.
_IMMUTABLE_FIELDS = (
    "action_id",
    "docmend_id",
    "operation",
    "original_path",
    "target_path",
    "before_sha256",
    "after_sha256",
    "backup_path",
    "overwritten_backup_path",
    "overwritten_sha256",
    "source_identity",
    "target_identity",
    "expected_published_identity",
)


def _parse_lines(path: Path) -> list[object]:
    """NDJSON parse with the adr-0006 AOF torn-tail rule (unchanged in 2.0):
    tolerate only a physically unterminated trailing line; any interior or
    newline-terminated corruption hard-aborts."""
    log = get_logger(__name__)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"{path}: cannot read manifest ({exc.strerror or exc})"
        raise ArtifactError(msg) from exc
    lines = raw.splitlines()
    unterminated_tail = bool(raw) and not raw.endswith("\n")
    documents: list[object] = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        trailing = index == len(lines) - 1
        try:
            documents.append(json.loads(line))
        except json.JSONDecodeError as exc:
            if trailing and unterminated_tail:
                log.warning("torn trailing manifest line dropped", path=str(path), line=index + 1)
                break
            msg = f"{path}:{index + 1}: corrupt manifest record — {exc}"
            raise ArtifactError(msg) from exc
    return documents


def _read_header(path: Path, first: object) -> ManifestHeader:
    raw: object = first  # keep the un-narrowed alias for validate_artifact
    if isinstance(first, dict):
        document = cast("dict[str, object]", first)
        if document.get("schema") == "docmend/manifest-record":
            raise ArtifactError(f"{path}: {CLEAN_BREAK_MESSAGE}")
    validate_artifact("manifest-header", raw)
    header = ManifestHeader.model_validate(raw)
    _check_supported_minor(path, header.schema_version, MANIFEST_HEADER_SCHEMA_VERSION)
    return header


def _check_supported_minor(path: Path, version: str, current: str) -> None:
    if int(version.split(".")[1]) > int(current.split(".")[1]):
        msg = f"{path}: unsupported future manifest schema version {version} (this docmend reads up to {current})"
        raise ArtifactError(msg)


def _lexically_inside(candidate: str, root: str) -> bool:
    return Path(os.path.normpath(candidate)).is_relative_to(os.path.normpath(root))


def _validate_lifecycle(path: Path, records: list[ManifestRecord]) -> None:
    """Per-set lifecycle legality — PROVISIONAL by design (adr-0019; Plan B
    review CR-NEW-002): a terminal with no same-set intent parses here and is
    proven (or rejected) at chain scope, where it must close exactly one
    earlier set's dangling intent. That is what makes both adjudication
    terminals and pre-journaling producers representable at set scope."""
    by_action: dict[str, list[ManifestRecord]] = {}
    for record in records:
        by_action.setdefault(record.action_id, []).append(record)
    for action_id, group in by_action.items():
        intents = [r for r in group if r.result == "intent"]
        terminals = [r for r in group if r.result != "intent"]
        if len(intents) > 1:
            msg = f"{path}: {action_id}: more than one intent record in one set"
            raise ArtifactError(msg)
        if len(terminals) > 1:
            msg = f"{path}: {action_id}: more than one terminal record in one set"
            raise ArtifactError(msg)
        if intents and terminals:
            intent, terminal = intents[0], terminals[0]
            if intent.seq > terminal.seq:
                msg = f"{path}: {action_id}: intent recorded after its terminal"
                raise ArtifactError(msg)
            for field in _IMMUTABLE_FIELDS:
                if field == "after_sha256" and terminal.result == "failed":
                    # The intent records the EXPECTED output hash; a failed
                    # terminal asserts the mutation did not complete, so its
                    # after is null (the original is intact) — the one field
                    # a failure legitimately "changes" (spec 10.4).
                    if terminal.after_sha256 is not None:
                        msg = f"{path}: {action_id}: failed terminal carries an after hash"
                        raise ArtifactError(msg)
                    continue
                if getattr(intent, field) != getattr(terminal, field):
                    msg = (
                        f"{path}: {action_id}: immutable field {field!r} diverges "
                        f"between intent and terminal"
                    )
                    raise ArtifactError(msg)


def _validate_kind(path: Path, header: ManifestHeader, records: list[ManifestRecord]) -> None:
    for record in records:
        has_undoes = record.undoes_action_id is not None
        if header.kind == "restore" and not has_undoes:
            msg = f"{path}: {record.action_id}: restore-kind record missing undoes lineage"
            raise ArtifactError(msg)
        if header.kind == "apply" and has_undoes:
            msg = f"{path}: {record.action_id}: apply-kind record carries undoes lineage"
            raise ArtifactError(msg)


def _validate_containment(
    path: Path, header: ManifestHeader, records: list[ManifestRecord], *, resolve: bool
) -> None:
    root = header.source_root
    for record in records:
        for candidate in (record.original_path, record.target_path):
            inside = _lexically_inside(candidate, root)
            if inside and resolve:
                inside = Path(candidate).resolve().is_relative_to(Path(root).resolve())
            if not inside:
                msg = (
                    f"{path}: {record.action_id}: recorded path {candidate} escapes "
                    f"the manifest's source root {root}"
                )
                raise ManifestContainmentError(msg)


def _validate_backup_trust(
    path: Path, header: ManifestHeader, records: list[ManifestRecord], *, check_objects: bool
) -> None:
    """The complete F5 BackupStore trust boundary (Plan B review CR-002): a
    backup reference is DERIVABLE evidence, never a free-form path. The key's
    run segment is the PERFORMING run's run_id — which equals this set's
    header run (run coherence already forced record.run_id == header.run_id).
    A STANDALONE terminal (no same-set intent) is exempt at set scope: it is
    either an adoption terminal whose backup was written under the CLOSING
    INTENT's run (chain scope validates it against that intent, whose own set
    already reconstructed the key) or a pre-journaling producer's record —
    the same provisional-set/strict-chain split as the lifecycle rule.
    NOTE: action_id's run prefix is the PLAN run, never the key's run segment.
    """
    intent_actions = {r.action_id for r in records if r.result == "intent"}
    for record in records:
        references = (
            (record.backup_path, "source", record.original_path),
            (record.overwritten_backup_path, "overwritten", record.target_path),
        )
        if record.overwritten_backup_path is not None and record.overwritten_sha256 is None:
            msg = f"{path}: {record.action_id}: overwritten backup without overwritten_sha256"
            raise ManifestContainmentError(msg)
        for recorded, role, base in references:
            if recorded is None:
                continue
            if record.result != "intent" and record.action_id not in intent_actions:
                continue  # standalone terminal: key proven at chain scope (see docstring)
            if header.backup_root is None:
                msg = (
                    f"{path}: {record.action_id}: backup reference with no backup_root "
                    f"in the header (BackupStore trust boundary)"
                )
                raise ManifestContainmentError(msg)
            _, _, action_part = record.action_id.partition("/")
            try:
                rel = Path(os.path.normpath(base)).relative_to(os.path.normpath(header.source_root))
            except ValueError as exc:
                msg = f"{path}: {record.action_id}: backup base path outside source root"
                raise ManifestContainmentError(msg) from exc
            expected = Path(header.backup_root) / header.run_id / action_part / role / rel
            if os.path.normpath(recorded) != os.path.normpath(str(expected)):
                msg = (
                    f"{path}: {record.action_id}: backup path {recorded} does not "
                    f"reconstruct from its BackupStore key (expected {expected})"
                )
                raise ManifestContainmentError(msg)
            # F5's "at most one path per role per action" holds without a
            # dedicated check at set scope: the immutable-field rule already
            # forces an action's intent and terminal to agree on both backup
            # fields, and a second record pair for the action is illegal.
            # Cross-SET agreement (adoption terminals) is chain scope (Task 3).
            if check_objects:
                _validate_backup_object(
                    path,
                    record.action_id,
                    Path(header.backup_root),
                    (header.run_id, action_part, role, *rel.parts),
                )


def _validate_backup_object(
    path: Path, action_id: str, backup_root: Path, components: tuple[str, ...]
) -> None:
    """Filesystem half of F5, run BEFORE any backup is opened: the leaf must
    be a regular file and no component below backup_root may be a symlink.
    `components` is the full derivable key below the root — the same
    (run, action, role, relative-path) tuple reconstruction proved."""
    current = backup_root
    for index, part in enumerate(components):
        current = current / part
        try:
            st = os.lstat(current)
        except OSError as exc:
            msg = f"{path}: {action_id}: backup component {current} missing/unreadable ({exc})"
            raise ManifestContainmentError(msg) from exc
        leaf = index == len(components) - 1
        if stat.S_ISLNK(st.st_mode):
            msg = f"{path}: {action_id}: symlink component {current} below the backup root"
            raise ManifestContainmentError(msg)
        if leaf and not stat.S_ISREG(st.st_mode):
            msg = f"{path}: {action_id}: backup object {current} is not a regular file"
            raise ManifestContainmentError(msg)
        if not leaf and not stat.S_ISDIR(st.st_mode):
            msg = f"{path}: {action_id}: backup path component {current} is not a directory"
            raise ManifestContainmentError(msg)


def read_manifest_set(path: Path, *, check_backup_objects: bool = True) -> ManifestSet:
    """Read and validate ONE manifest file (adr-0019: header presence and
    version, single run, contiguous seq, provisional per-set lifecycle, kind
    lineage, source-root containment, and the full F5 BackupStore trust
    boundary) — before any referenced path is touched by a consumer.

    `check_backup_objects=False` skips the live-filesystem half of F5 (regular
    file, no symlink components); mutating consumers use the default so every
    check runs before `_verified_backup` opens anything, while read-only
    verify (Plan D) re-runs those checks as findings.
    """
    documents = _parse_lines(path)
    if not documents:
        raise ArtifactError(f"{path}: manifest has no header")
    header = _read_header(path, documents[0])
    records: list[ManifestRecord] = []
    for document in documents[1:]:
        validate_artifact("manifest", document)
        record = ManifestRecord.model_validate(document)
        _check_supported_minor(path, record.schema_version, MANIFEST_SCHEMA_VERSION)
        records.append(record)
    for index, record in enumerate(records, start=1):
        if record.run_id != header.run_id:
            msg = f"{path}: seq {record.seq}: record run_id {record.run_id} != header run_id"
            raise ArtifactError(msg)
        if record.seq != index:
            msg = f"{path}: record seq {record.seq} at position {index} — seq must be contiguous from 1"
            raise ArtifactError(msg)
    _validate_lifecycle(path, records)
    _validate_kind(path, header, records)
    _validate_containment(path, header, records, resolve=check_backup_objects)
    _validate_backup_trust(path, header, records, check_objects=check_backup_objects)
    return ManifestSet(header=header, records=records, path=path)
