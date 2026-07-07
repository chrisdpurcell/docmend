"""Discovery layer — read-only walk and classification (FR-001, FR-012, DR-001).

Architectural role (§8.2.3): the first pipeline layer. It walks a directory tree
(or accepts a single file, NFR-006), applies the FR-012 include/exclude filters,
and collects per-file facts into the DR-001 inventory. It must be provably
read-only (FR-001): every filesystem call here is a stat, readlink, or read —
never a write — and the FR-001 test asserts corpus mtimes/hashes are unchanged
after a scan.

Classification collects FACTS; it makes no skip decisions beyond the two scan
outcomes (excluded by filter, unreadable per ERR-007). Danger detection —
binary/NUL/utf16-suspect/low-confidence risk classification (FR-015) — is the
planning layer's job (MS-2), consuming the facts recorded here.

Encoding facts implement the deterministic rungs of FR-007's fixed order: BOM
sniff (UTF-32 patterns checked before UTF-16 — the UTF-32-LE BOM begins with the
UTF-16-LE BOM bytes), then strict full-file UTF-8 validity, then ASCII-only.
``classify_file`` itself only ever produces those deterministic rungs; the
charset-normalizer legacy rung (``docmend.detection``, adr-0009) is applied
afterward, once per candidate, by ``_process_candidate`` — gated to files that
are no-BOM, non-UTF-8, and NUL-free (a decode failure or NUL byte would make
the detector's guess meaningless). ``detected`` stays ``None`` only when that
gate excludes the file, detection is disabled, or the detector itself found no
candidate.

Everything is single-pass and chunked: hash, NUL presence, non-ASCII byte count
(the FR-007 floor gate's input, OQ-015), newline census, and incremental strict
UTF-8 validation all stream over the same read, so memory stays bounded per
file, never per corpus (NFR-001).
"""

import codecs
import hashlib
import os
import stat as stat_module
import time
from collections import Counter
from importlib.metadata import version as metadata_version
from pathlib import Path

from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from docmend import __version__, detection
from docmend.config import DocmendConfig
from docmend.inventory import (
    INVENTORY_SCHEMA_VERSION,
    BomKind,
    DetectedEncoding,
    EncodingFacts,
    FileRecord,
    HardLinkGroup,
    Inventory,
    InventoryTotals,
    NewlineStyle,
    ScanConfigRecord,
    SkippedByReason,
    SkipRecord,
    SymlinkRecord,
)
from docmend.observability import get_logger
from docmend.watchdog import PerFileTimeoutError, per_file_watchdog

_CHUNK_SIZE = 1 << 20  # 1 MiB per read: bounded memory regardless of file size
_ASCII_BYTES = bytes(range(0x80))

# Longest BOM first: UTF-32-LE (ff fe 00 00) must be tested before UTF-16-LE
# (ff fe), and UTF-32-BE (00 00 fe ff) before anything that could shadow it.
_BOMS: tuple[tuple[bytes, BomKind], ...] = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)

# The encoding a BOM authoritatively announces (FR-007: BOM'd files decode per
# their BOM, OQ-026). For the UTF-8 BOM the content encoding is utf-8; the BOM
# itself is recorded separately so plan/apply know to strip it (EC-007).
_BOM_ENCODING_NAME: dict[BomKind, str] = {
    "utf-8": "utf-8",
    "utf-16-le": "utf-16-le",
    "utf-16-be": "utf-16-be",
    "utf-32-le": "utf-32-le",
    "utf-32-be": "utf-32-be",
}


def sniff_bom(header: bytes) -> BomKind | None:
    """Public: the apply engine (Task 9) re-sniffs the BOM from bytes whose
    hash already matched the scan, so the sniff is provenance-equivalent."""
    for bom, kind in _BOMS:
        if header.startswith(bom):
            return kind
    return None


class NewlineCensus:
    """Streaming CRLF/LF/CR counter that survives a CRLF split across chunks."""

    def __init__(self) -> None:
        self.crlf = 0
        self.bare_lf = 0
        self.bare_cr = 0
        self._pending_cr = False

    def update(self, chunk: bytes) -> None:
        if not chunk:
            return
        if self._pending_cr:
            # The previous chunk ended in \r; only now do we know whether it
            # was a bare CR or the first half of a CRLF.
            if chunk[0] == 0x0A:
                self.crlf += 1
                chunk = chunk[1:]
            else:
                self.bare_cr += 1
            self._pending_cr = False
            if not chunk:
                return
        pairs = chunk.count(b"\r\n")
        bare_lf = chunk.count(b"\n") - pairs
        bare_cr = chunk.count(b"\r") - pairs
        if chunk.endswith(b"\r"):
            bare_cr -= 1
            self._pending_cr = True
        self.crlf += pairs
        self.bare_lf += bare_lf
        self.bare_cr += bare_cr

    def finish(self) -> None:
        if self._pending_cr:
            self.bare_cr += 1
            self._pending_cr = False

    def style(self) -> NewlineStyle:
        present: list[NewlineStyle] = []
        if self.bare_lf:
            present.append("lf")
        if self.crlf:
            present.append("crlf")
        if self.bare_cr:
            present.append("cr")
        if not present:
            return "none"
        return present[0] if len(present) == 1 else "mixed"


def classify_file(
    full: Path, rel: str, stat: os.stat_result, *, chunk_size: int = _CHUNK_SIZE
) -> FileRecord:
    """Build one DR-001 per-file record from a single streaming read.

    ``chunk_size`` is parameterized so tests can prove classification is
    independent of chunk boundaries (the CRLF-split and BOM-header cases).
    """
    hasher = hashlib.sha256()
    census = NewlineCensus()
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    utf8_valid = True
    nul_bytes = False
    non_ascii = 0
    bom: BomKind | None = None

    def consume(chunk: bytes) -> None:
        nonlocal utf8_valid, nul_bytes, non_ascii
        hasher.update(chunk)
        if not nul_bytes and b"\x00" in chunk:
            nul_bytes = True
        non_ascii += len(chunk.translate(None, _ASCII_BYTES))
        census.update(chunk)
        if utf8_valid:
            try:
                decoder.decode(chunk)
            except UnicodeDecodeError:
                utf8_valid = False

    with full.open("rb") as fh:
        # Read the 4-byte BOM window first so sniffing never spans a chunk
        # boundary, whatever chunk_size is.
        header = fh.read(4)
        bom = sniff_bom(header)
        consume(header)
        while chunk := fh.read(chunk_size):
            consume(chunk)
    if utf8_valid:
        try:
            decoder.decode(b"", True)
        except UnicodeDecodeError:
            utf8_valid = False
    census.finish()

    # FR-007 deterministic rungs, in the spec's fixed order. A pure-ASCII file
    # is always strict-UTF-8-valid, so the ASCII rung can never be reached here;
    # it exists in FR-007 (and the schema's method enum) to guarantee ASCII
    # content is never handed to the MS-2 legacy detector.
    detected: DetectedEncoding | None = None
    if bom is not None:
        detected = DetectedEncoding(name=_BOM_ENCODING_NAME[bom], confidence=1.0, method="bom")
    elif utf8_valid:
        detected = DetectedEncoding(name="utf-8", confidence=1.0, method="utf8-strict")

    return FileRecord(
        path=rel,
        size_bytes=stat.st_size,
        suffix=full.suffix,
        mtime_ns=stat.st_mtime_ns,
        nlink=stat.st_nlink,
        sha256=f"sha256:{hasher.hexdigest()}",
        newline_style=census.style(),
        nul_bytes=nul_bytes,
        non_ascii_bytes=non_ascii,
        encoding=EncodingFacts(
            bom=bom,
            utf8_valid=utf8_valid,
            ascii_only=non_ascii == 0,
            detected=detected,
        ),
    )


class _ScanState:
    """Accumulators for one scan pass; keeps the walk loop readable."""

    def __init__(self) -> None:
        self.files: list[FileRecord] = []
        self.symlinks: list[SymlinkRecord] = []
        self.skipped: list[SkipRecord] = []
        self.link_groups: dict[tuple[int, int], tuple[int, list[str]]] = {}

    def record_hard_link(self, stat: os.stat_result, rel: str) -> None:
        if stat.st_nlink > 1:
            key = (stat.st_dev, stat.st_ino)
            _, paths = self.link_groups.setdefault(key, (stat.st_nlink, []))
            paths.append(rel)


def _record_symlink(state: _ScanState, full: Path, rel: str) -> None:
    log = get_logger(__name__)
    try:
        target = str(full.readlink())
    except OSError as exc:
        state.skipped.append(SkipRecord(path=rel, reason="unreadable", detail=str(exc)))
        log.warning("symlink unreadable", path=rel, error=str(exc))
        return
    if full.is_file():
        kind = "file"
    elif full.is_dir():
        kind = "directory"
    elif full.exists():
        kind = "other"
    else:
        kind = "broken"
    state.symlinks.append(SymlinkRecord(path=rel, target=target, kind=kind))
    log.debug("symlink recorded", path=rel, target=target, kind=kind)


def _process_candidate(
    state: _ScanState,
    full: Path,
    rel: str,
    include: PathSpec[GitIgnoreSpecPattern],
    exclude: PathSpec[GitIgnoreSpecPattern],
    *,
    detect: bool,
    timeout: float,
) -> None:
    """Filter and classify one directory entry (file or symlink, never a dir)."""
    log = get_logger(__name__)
    try:
        stat = full.lstat()
    except OSError as exc:
        state.skipped.append(SkipRecord(path=rel, reason="unreadable", detail=str(exc)))
        log.warning("entry unreadable", path=rel, error=str(exc), err="ERR-007")
        return

    if stat_module.S_ISLNK(stat.st_mode):
        if not exclude.match_file(rel):
            _record_symlink(state, full, rel)
        return

    if not include.match_file(rel):
        return  # not a candidate document; deliberately not recorded (DR-001)
    if exclude.match_file(rel):
        state.skipped.append(SkipRecord(path=rel, reason="excluded", detail=None))
        log.debug("excluded by filter", path=rel)
        return

    # FR-019: the watchdog spans classification AND the legacy-detection rung —
    # together they are the unbounded per-file work in this layer (streaming
    # read + strict-UTF-8 decode + charset-normalizer). The writer is elsewhere
    # and is never wrapped (see docmend.watchdog scope contract).
    start = time.monotonic()
    try:
        with per_file_watchdog(timeout):
            record = classify_file(full, rel, stat)
            if (
                detect
                and record.encoding.bom is None
                and not record.encoding.utf8_valid
                and not record.nul_bytes
            ):
                # FR-007 legacy rung (adr-0009 gate order): only a no-BOM,
                # non-UTF-8, NUL-free file ever reaches charset-normalizer.
                detected = detection.detect_legacy(full)
                if detected is not None:
                    record = record.model_copy(
                        update={
                            "encoding": record.encoding.model_copy(update={"detected": detected})
                        }
                    )
                    log.debug("legacy encoding detected", path=rel, name=detected.name)
    except PerFileTimeoutError:
        # FR-019/ERR-009: a pathological file must not hang an unattended run;
        # record the timeout with path + elapsed and let the batch continue.
        elapsed = time.monotonic() - start
        state.skipped.append(
            SkipRecord(
                path=rel, reason="timeout", detail=f"exceeded {timeout}s (elapsed {elapsed:.2f}s)"
            )
        )
        log.warning(
            "file classification timed out", path=rel, elapsed=round(elapsed, 3), err="ERR-009"
        )
        return
    except OSError as exc:
        # ERR-007: unreadable during scan (classification or detection) is
        # recorded, never fatal.
        state.skipped.append(SkipRecord(path=rel, reason="unreadable", detail=str(exc)))
        log.warning("file unreadable", path=rel, error=str(exc), err="ERR-007")
        return

    state.files.append(record)
    state.record_hard_link(stat, rel)
    log.debug(
        "classified",
        path=rel,
        size=record.size_bytes,
        newline_style=record.newline_style,
        utf8_valid=record.encoding.utf8_valid,
    )


def scan(
    requested: Path,
    config: DocmendConfig,
    *,
    run_id: str,
    generated_at: str,
) -> Inventory:
    """Scan PATH (file or directory, NFR-006) into a DR-001 inventory. Read-only."""
    log = get_logger(__name__)
    root = requested if requested.is_dir() else requested.parent
    root = root.resolve()

    include = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.include)
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude)
    state = _ScanState()

    if requested.is_dir():

        def on_walk_error(error: OSError) -> None:
            failed = Path(error.filename) if error.filename else root
            try:
                rel = failed.resolve().relative_to(root).as_posix()
            except ValueError:
                rel = str(failed)
            state.skipped.append(SkipRecord(path=rel, reason="unreadable", detail=str(error)))
            log.warning("directory unreadable", path=rel, error=str(error), err="ERR-007")

        for dirpath, dirnames, filenames in os.walk(
            root, topdown=True, onerror=on_walk_error, followlinks=False
        ):
            dirnames.sort()
            base = Path(dirpath)
            # Symlinked directories are listed but never descended into
            # (followlinks=False); record them like any other symlink (EC-008).
            for dirname in list(dirnames):
                sub = base / dirname
                rel = sub.relative_to(root).as_posix()
                # Excluded directories are pruned at the walk (the trailing "/"
                # marks a directory for pathspec, so "**/.git/**" matches
                # ".git/" itself). Selection is unchanged — gitignore
                # dir-prefix semantics already excluded every file beneath at
                # the per-file check — but the descent cost and the per-file
                # "excluded" skip records for the subtree disappear. Matches
                # git's own rule that a negation pattern cannot re-include a
                # file whose parent directory is excluded.
                if exclude.match_file(rel + "/"):
                    dirnames.remove(dirname)
                    continue
                if sub.is_symlink():
                    dirnames.remove(dirname)
                    if not exclude.match_file(rel):
                        _record_symlink(state, sub, rel)
            for filename in sorted(filenames):
                full = base / filename
                rel = full.relative_to(root).as_posix()
                _process_candidate(
                    state,
                    full,
                    rel,
                    include,
                    exclude,
                    detect=config.encoding.detect,
                    timeout=config.limits.per_file_timeout,
                )
    else:
        rel = requested.name
        _process_candidate(
            state,
            root / rel,
            rel,
            include,
            exclude,
            detect=config.encoding.detect,
            timeout=config.limits.per_file_timeout,
        )
        if not state.files and not state.symlinks and not state.skipped:
            log.warning(
                "single-file PATH matched no include pattern; inventory is empty",
                path=str(requested),
            )

    # Globally sorted record arrays: os.walk yields parent-directory files
    # before subdirectory files, which is deterministic but not diff-friendly;
    # path order makes inventories from different runs directly comparable.
    state.files.sort(key=lambda record: record.path)
    state.symlinks.sort(key=lambda record: record.path)
    state.skipped.sort(key=lambda record: record.path)
    hard_link_groups = [
        HardLinkGroup(device=dev, inode=ino, nlink=nlink, paths=sorted(paths))
        for (dev, ino), (nlink, paths) in sorted(state.link_groups.items())
    ]
    reasons = Counter(record.reason for record in state.skipped)
    totals = InventoryTotals(
        files=len(state.files),
        symlinks=len(state.symlinks),
        skipped=len(state.skipped),
        skipped_by_reason=SkippedByReason(
            excluded=reasons.get("excluded", 0),
            unreadable=reasons.get("unreadable", 0),
            timeout=reasons.get("timeout", 0),
        ),
        hard_link_groups=len(hard_link_groups),
        total_size_bytes=sum(record.size_bytes for record in state.files),
    )
    log.info(
        "scan complete",
        files=totals.files,
        symlinks=totals.symlinks,
        skipped=totals.skipped,
        hard_link_groups=totals.hard_link_groups,
    )
    return Inventory(
        run_id=run_id,
        generated_at=generated_at,
        generated_by=f"docmend {__version__}",
        requested_path=str(requested),
        source_root=str(root),
        scan_config=ScanConfigRecord(
            include=list(config.paths.include),
            exclude=list(config.paths.exclude),
            encoding_detect=config.encoding.detect,
            detector=(
                f"charset-normalizer {metadata_version('charset-normalizer')}"
                if config.encoding.detect
                else None
            ),
        ),
        files=state.files,
        symlinks=state.symlinks,
        skipped=state.skipped,
        hard_link_groups=hard_link_groups,
        totals=totals,
        schema_version=INVENTORY_SCHEMA_VERSION,
    )
