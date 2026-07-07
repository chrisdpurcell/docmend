"""Manifest writer/reader — the DR-004 append-only NDJSON record (adr-0005, adr-0006).

Cross-file contracts:
- One record is appended, flushed, and fsync'd immediately after each mutation
  (spec 12.3: incremental, never only at run end); a crash therefore loses at
  most the trailing record, which is exactly what the AOF read rule tolerates.
- Paths are ABSOLUTE (decision 7): `docmend restore` has no PATH argument
  (IR-008) and must locate files from the manifest alone.
- read_manifest is the MS-4 resume reader too — torn TRAILING line dropped
  with a warning; any interior parse/schema failure hard-aborts (ArtifactError
  → exit 2), because a corrupt interior record is a defect, not something to
  skip past (adr-0006).
"""

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Annotated, Literal, Self, TextIO

from pydantic import BaseModel, ConfigDict, Field

from docmend.artifacts import ArtifactError, validate_artifact
from docmend.inventory import RunId, Sha256
from docmend.observability import get_logger
from docmend.plan import ActionId, DocmendId
from docmend.report import ErrorInfo

MANIFEST_SCHEMA_VERSION = "1.1"

type ManifestOperation = Literal["rename", "rewrite", "rename_and_rewrite"]


# TODO(Task 6): replace with docmend.writer.atomic.fsync_dir when that module
# lands — that module owns the atomic-replace machinery this writer will also
# depend on; until then this minimal copy keeps Task 5 self-contained.
def fsync_dir(path: Path) -> None:
    """Fsync a directory's entry table (best-effort — see body for why)."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    except OSError:
        # Some filesystems/platforms reject fsync on a directory descriptor;
        # the durability of the FILE write already happened, this is best-effort
        # extra insurance for the directory entry, not a correctness dependency.
        pass
    finally:
        os.close(fd)


class ManifestRecord(BaseModel):
    """One mutation record (DR-004) — one NDJSON line, restorable in isolation."""

    model_config = ConfigDict(
        extra="forbid", strict=True, populate_by_name=True, serialize_by_alias=True
    )

    schema_kind: Literal["docmend/manifest-record"] = Field(
        default="docmend/manifest-record", alias="schema"
    )
    schema_version: Annotated[str, Field(pattern=r"^1\.\d+$")] = MANIFEST_SCHEMA_VERSION
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
    result: Literal["applied", "failed"]
    error: ErrorInfo | None
    overwritten_sha256: Sha256 | None = None
    overwritten_backup_path: str | None = None


class ManifestWriter:
    """Append-only, per-record-durable NDJSON writer (single-writer, OQ-027)."""

    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(),
    ) -> None:
        self._path = path
        self._run_id = run_id
        self._now = now
        self._seq = 0
        # Lazy-open on first append: a write run in which every action skips
        # must not leave an empty manifest file implying mutations happened
        # (codex round-1 "empty manifest" question — the answer is: no file).
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


def read_manifest(path: Path) -> list[ManifestRecord]:
    """Read every record, applying the adr-0006 AOF torn-tail rule."""
    log = get_logger(__name__)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"{path}: cannot read manifest ({exc.strerror or exc})"
        raise ArtifactError(msg) from exc
    lines = raw.splitlines()
    # AOF tolerance applies ONLY to a physically unterminated tail (a crash
    # mid-append). A newline-terminated final line was a COMPLETE record; if
    # it no longer parses, that is corruption, not a torn write, and it must
    # hard-abort like an interior record (codex CR-NEW-006; adr-0006).
    unterminated_tail = bool(raw) and not raw.endswith("\n")
    records: list[ManifestRecord] = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        trailing = index == len(lines) - 1
        try:
            document: object = json.loads(line)
        except json.JSONDecodeError as exc:
            if trailing and unterminated_tail:
                log.warning("torn trailing manifest line dropped", path=str(path), line=index + 1)
                break
            msg = f"{path}:{index + 1}: corrupt manifest record — {exc}"
            raise ArtifactError(msg) from exc
        validate_artifact("manifest", document)
        records.append(ManifestRecord.model_validate(document))
    return records
