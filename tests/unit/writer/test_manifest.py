"""Manifest 2.0 writer/reader (DR-004, IR-007 NDJSON half, adr-0005/adr-0019).

Real filesystem on purpose (OQ-019): the per-record append+fsync durability
behavior is the thing under test. The AOF rule (unchanged in 2.0): tolerate
only a torn TRAILING line; hard-abort on any interior corruption. New in 2.0:
the header envelope, the clean-break 1.x rejection, and read_manifest_set's
rule passes — run coherence, seq contiguity, provisional lifecycle, kind
lineage, source-root containment, and the complete F5 BackupStore trust
boundary (Plan B review CR-002).
"""

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError
from tests.helpers.manifest2 import (
    OTHER_RUN_ID,
    RUN_ID,
    SHA_A,
    SHA_B,
    SHA_C,
    UUID7,
    header_doc,
    record_doc,
    write_set,
)

from docmend.artifacts import ArtifactError, validate_artifact
from docmend.lineage import ObjectIdentity, PriorAttempt
from docmend.report import ErrorInfo
from docmend.writer.manifest import (
    ManifestContainmentError,
    ManifestHeader,
    ManifestRecord,
    ManifestWriter,
    manifest_sha256,
    read_manifest_set,
)


def _header(**overrides: object) -> ManifestHeader:
    return ManifestHeader.model_validate(header_doc(**overrides))


def _record(action_seq: int) -> ManifestRecord:
    return ManifestRecord.model_validate(record_doc(action_seq))


def _writer(path: Path, **header_overrides: object) -> ManifestWriter:
    return ManifestWriter(path, header=_header(**header_overrides))


class TestManifestHeader:
    """Manifest 2.0 header + lineage wire primitives (adr-0019, Plan B Task 1)."""

    def test_header__validates_and_serializes_by_alias(self) -> None:
        header = _header(backup_root="/bak")
        doc = header.model_dump(mode="json")
        assert doc["schema"] == "docmend/manifest-header"
        assert doc["schema_version"] == "2.0"
        validate_artifact("manifest-header", doc)

    def test_prior_attempt__requires_exactly_one_sha(self) -> None:
        with pytest.raises(ValidationError):
            PriorAttempt(run_id=RUN_ID, report_sha256=None, manifest_sha256=None)
        with pytest.raises(ValidationError):
            PriorAttempt(run_id=RUN_ID, report_sha256=SHA_A, manifest_sha256=SHA_B)
        edge = PriorAttempt(run_id=RUN_ID, report_sha256=SHA_A, manifest_sha256=None)
        assert edge.report_sha256 == SHA_A

    def test_header_and_nested_lineage__deep_frozen(self) -> None:
        edge = PriorAttempt(run_id=RUN_ID, report_sha256=SHA_A, manifest_sha256=None)
        header = _header(prior_attempt=edge)
        assert isinstance(header.effective_excludes, tuple)
        with pytest.raises(ValidationError):
            header.source_root = "/elsewhere"  # type: ignore[misc]
        with pytest.raises(ValidationError):
            edge.run_id = OTHER_RUN_ID  # type: ignore[misc]
        identity = ObjectIdentity(dev=1, ino=2)
        error = ErrorInfo(error_class="ERR-003", message="synthetic")
        with pytest.raises(ValidationError):
            identity.dev = 3  # type: ignore[misc]
        with pytest.raises(ValidationError):
            error.message = "changed"  # type: ignore[misc]

    def test_header_schema__rejects_future_major_and_extra_members(self) -> None:
        base = header_doc(
            kind="restore",
            prior_manifest_sha256=SHA_B,
            prior_attempt={"run_id": RUN_ID, "report_sha256": None, "manifest_sha256": SHA_B},
        )
        validate_artifact("manifest-header", base)
        with pytest.raises(ArtifactError):
            validate_artifact("manifest-header", {**base, "schema_version": "3.0"})
        with pytest.raises(ArtifactError):
            validate_artifact("manifest-header", {**base, "surprise": True})

    def test_record__undoes_fields_paired_or_absent(self) -> None:
        with pytest.raises(ValidationError):
            ManifestRecord.model_validate(
                record_doc(1, undoes_action_id=f"{RUN_ID}/a1", undoes_run_id=None)
            )


class TestWriterDurability:
    """Header-first append semantics; the AOF behaviors carry over from 1.x."""

    def test_append_read_round_trip__header_then_records(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.jsonl"
        with _writer(path) as writer:
            first = writer.append(_record(1))
            second = writer.append(_record(2))
        assert (first.seq, second.seq) == (1, 2)
        lines = path.read_text(encoding="utf-8").splitlines()
        assert json.loads(lines[0])["schema"] == "docmend/manifest-header"
        loaded = read_manifest_set(path)
        assert loaded.header == _header()
        assert loaded.records == (first, second)
        assert loaded.sha256 is None  # filled by chain reading only

    def test_torn_trailing_line__tolerated(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.jsonl"
        with _writer(path) as writer:
            kept = writer.append(_record(1))
        with path.open("a", encoding="utf-8") as fh:
            fh.write('{"schema": "docmend/manifest-record", "torn')  # crash mid-append
        assert read_manifest_set(path).records == (kept,)

    def test_corrupt_newline_terminated_final_record__hard_aborts(self, tmp_path: Path) -> None:
        """codex CR-NEW-006: a final line ending in '\\n' was a COMPLETE record —
        if it no longer parses, that is corruption, never a tolerable torn tail."""
        path = tmp_path / "manifest.jsonl"
        with _writer(path) as writer:
            writer.append(_record(1))
        with path.open("a", encoding="utf-8") as fh:
            fh.write("{corrupt}\n")
        with pytest.raises(ArtifactError):
            read_manifest_set(path)

    def test_first_append_fsyncs_manifest_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """codex CR-NEW-005: creating the manifest file must fsync its directory —
        file fsync alone does not persist a new directory entry."""
        from docmend.writer import manifest as manifest_module

        calls: list[Path] = []
        monkeypatch.setattr(manifest_module, "fsync_dir", calls.append)
        path = tmp_path / "manifest.jsonl"
        with _writer(path) as writer:
            writer.append(_record(1))
            writer.append(_record(2))
        assert calls == [tmp_path]  # exactly once, on first create

    def test_corrupt_interior_line__hard_aborts(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.jsonl"
        with _writer(path) as writer:
            writer.append(_record(1))
        header_line, record_line = path.read_text(encoding="utf-8").splitlines()
        path.write_text(f"{header_line}\n{{corrupt}}\n{record_line}\n", encoding="utf-8")
        with pytest.raises(ArtifactError):
            read_manifest_set(path)

    def test_zero_appends__no_manifest_file_created(self, tmp_path: Path) -> None:
        """A write run in which every action skipped leaves NO manifest file —
        an empty manifest would imply mutations happened (lazy-open contract);
        the header is written together with the first append."""
        path = tmp_path / "manifest.jsonl"
        with _writer(path):
            pass
        assert not path.exists()

    def test_header_only_file__valid_empty_set(self, tmp_path: Path) -> None:
        """A kill between the header fsync and the first record leaves a
        header-only file: a valid, EMPTY set (nothing was durably recorded)."""
        path = write_set(tmp_path / "manifest.jsonl", header_doc())
        loaded = read_manifest_set(path)
        assert loaded.records == ()

    def test_missing_file__raises_cannot_read(self, tmp_path: Path) -> None:
        with pytest.raises(ArtifactError, match="cannot read"):
            read_manifest_set(tmp_path / "absent.jsonl")

    def test_manifest_sha256__hashes_file_bytes(self, tmp_path: Path) -> None:
        import hashlib

        path = write_set(tmp_path / "manifest.jsonl", header_doc(), record_doc(1))
        assert manifest_sha256(path) == f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


type _Mutator = Callable[[dict[str, object], list[dict[str, object]]], object]


def _mutate_all(**overrides: object) -> _Mutator:
    def apply(_h: dict[str, object], rs: list[dict[str, object]]) -> None:
        for r in rs:
            r.update(overrides)

    return apply


def _mutate_header(**overrides: object) -> _Mutator:
    def apply(h: dict[str, object], _rs: list[dict[str, object]]) -> None:
        h.update(overrides)

    return apply


def _mutate_record(index: int, **overrides: object) -> _Mutator:
    def apply(_h: dict[str, object], rs: list[dict[str, object]]) -> None:
        rs[index].update(overrides)

    return apply


_REJECT_CASES: list[tuple[_Mutator, type[Exception], str]] = [
    (
        _mutate_record(0, run_id=OTHER_RUN_ID, action_id=f"{OTHER_RUN_ID}/a1"),
        ArtifactError,
        "run_id",
    ),
    (_mutate_record(1, seq=5), ArtifactError, "contiguous"),
    (_mutate_header(schema_version="2.9"), ArtifactError, "unsupported"),
    (_mutate_record(1, before_sha256=SHA_C), ArtifactError, "immutable"),
    (
        _mutate_all(original_path="/elsewhere/x.md"),
        ManifestContainmentError,
        "source root",
    ),
    (
        _mutate_all(
            original_path="/corpus/../elsewhere/x.md",
            target_path="/corpus/../elsewhere/x.md",
        ),
        ManifestContainmentError,
        "source root",
    ),
    (_mutate_all(backup_path="/tmp/evil"), ManifestContainmentError, "backup"),
]


class TestSetValidation:
    """read_manifest_set's rule passes (adr-0019; DMR-03)."""

    def test_1x_first_line__clean_break_message(self, tmp_path: Path) -> None:
        path = tmp_path / "m.jsonl"
        v1_record = {k: v for k, v in record_doc(1).items() if not k.startswith("undoes")}
        v1_record["schema_version"] = "1.3"
        path.write_text(json.dumps(v1_record) + "\n", encoding="utf-8")
        with pytest.raises(ArtifactError, match=r"docmend 1\.0\.2"):
            read_manifest_set(path)

    def test_empty_file__no_header_error(self, tmp_path: Path) -> None:
        path = tmp_path / "m.jsonl"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ArtifactError, match="no header"):
            read_manifest_set(path)

    @pytest.mark.parametrize(
        ("mutate", "error", "match"),
        _REJECT_CASES,
    )
    def test_read_manifest_set__rejects(
        self,
        tmp_path: Path,
        mutate: Callable[[dict[str, object], list[dict[str, object]]], object],
        error: type[Exception],
        match: str,
    ) -> None:
        header = header_doc()
        records = [
            record_doc(1, result="intent"),
            record_doc(1, seq=2),
        ]
        records[1]["action_id"] = records[0]["action_id"]
        mutate(header, records)
        path = write_set(tmp_path / "m.jsonl", header, *records)
        with pytest.raises(error, match=match):
            read_manifest_set(path)

    def test_provisional_lifecycle__standalone_terminal_parses(self, tmp_path: Path) -> None:
        """Plan B review CR-NEW-002: a terminal with no same-set intent is
        provisionally legal at SET scope (adjudication terminals and
        pre-journaling producers); chain scope proves or rejects it."""
        path = write_set(tmp_path / "m.jsonl", header_doc(), record_doc(1))
        assert read_manifest_set(path).records[0].result == "applied"

    def test_duplicate_terminals__rejected(self, tmp_path: Path) -> None:
        first = record_doc(1)
        second = record_doc(1, seq=2)
        second["action_id"] = first["action_id"]
        path = write_set(tmp_path / "m.jsonl", header_doc(), first, second)
        with pytest.raises(ArtifactError, match="more than one terminal"):
            read_manifest_set(path)

    def test_intent_after_terminal__rejected(self, tmp_path: Path) -> None:
        terminal = record_doc(1)
        intent = record_doc(1, seq=2, result="intent")
        intent["action_id"] = terminal["action_id"]
        path = write_set(tmp_path / "m.jsonl", header_doc(), terminal, intent)
        with pytest.raises(ArtifactError, match="intent recorded after"):
            read_manifest_set(path)

    def test_restore_kind__requires_undoes_on_every_record(self, tmp_path: Path) -> None:
        path = write_set(
            tmp_path / "m.jsonl",
            header_doc(kind="restore", prior_manifest_sha256=SHA_C),
            record_doc(1),
        )
        with pytest.raises(ArtifactError, match="undoes"):
            read_manifest_set(path)

    def test_apply_kind__rejects_undoes(self, tmp_path: Path) -> None:
        path = write_set(
            tmp_path / "m.jsonl",
            header_doc(),
            record_doc(1, undoes_action_id=f"{OTHER_RUN_ID}/a1", undoes_run_id=OTHER_RUN_ID),
        )
        with pytest.raises(ArtifactError, match="undoes"):
            read_manifest_set(path)

    def test_future_minor_record__rejected(self, tmp_path: Path) -> None:
        path = write_set(tmp_path / "m.jsonl", header_doc(), record_doc(1, schema_version="2.7"))
        with pytest.raises(ArtifactError, match="unsupported"):
            read_manifest_set(path)


def _backup_tree(
    tmp_path: Path, *, rel: str = "f1.md", role: str = "source"
) -> tuple[Path, dict[str, object], dict[str, object], dict[str, object]]:
    """A REAL BackupStore tree matching one action's derivable key, plus the
    action's intent+terminal pair — F5 reconstruction applies to intents and
    intent-paired terminals (standalone terminals defer to chain scope)."""
    backup_root = tmp_path / "backups"
    key_path = backup_root / RUN_ID / "a1" / role / rel
    key_path.parent.mkdir(parents=True)
    key_path.write_bytes(b"backed up bytes")
    header = header_doc(source_root=str(tmp_path / "corpus"), backup_root=str(backup_root))
    fields: dict[str, str] = {
        "original_path": str(tmp_path / "corpus" / rel),
        "target_path": str(tmp_path / "corpus" / rel),
        "backup_path": str(key_path),
    }
    intent = record_doc(1, result="intent", **fields)
    terminal = record_doc(1, seq=2, **fields)
    (tmp_path / "corpus").mkdir(exist_ok=True)
    return backup_root, header, intent, terminal


class TestBackupTrustBoundary:
    """The complete F5 checks (Plan B review CR-002) — a backup reference is
    derivable evidence, never a free-form path, and the object itself must be
    a plain regular file below an unsymlinked tree."""

    def test_valid_regular_backup__accepted(self, tmp_path: Path) -> None:
        _, header, intent, terminal = _backup_tree(tmp_path)
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        assert read_manifest_set(path).records[0].backup_path is not None

    def test_non_derivable_backup_path__refused(self, tmp_path: Path) -> None:
        backup_root, header, intent, terminal = _backup_tree(tmp_path)
        stray = backup_root / "stray.md"
        stray.write_bytes(b"x")
        for r in (intent, terminal):
            r["backup_path"] = str(stray)
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        with pytest.raises(ManifestContainmentError, match="reconstruct"):
            read_manifest_set(path)

    def test_backup_reference_with_null_root__refused(self, tmp_path: Path) -> None:
        _, header, intent, terminal = _backup_tree(tmp_path)
        header["backup_root"] = None
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        with pytest.raises(ManifestContainmentError, match="backup_root"):
            read_manifest_set(path)

    def test_symlinked_intermediate_directory__refused(self, tmp_path: Path) -> None:
        backup_root, header, intent, terminal = _backup_tree(tmp_path)
        real_role_dir = backup_root / RUN_ID / "a1" / "source"
        moved = tmp_path / "moved-role-dir"
        real_role_dir.rename(moved)
        real_role_dir.symlink_to(moved)
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        with pytest.raises(ManifestContainmentError, match="symlink"):
            read_manifest_set(path)

    def test_symlink_leaf__refused(self, tmp_path: Path) -> None:
        backup_root, header, intent, terminal = _backup_tree(tmp_path)
        leaf = backup_root / RUN_ID / "a1" / "source" / "f1.md"
        real = tmp_path / "real-bytes"
        leaf.rename(real)
        leaf.symlink_to(real)
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        with pytest.raises(ManifestContainmentError, match="symlink"):
            read_manifest_set(path)

    def test_fifo_leaf__refused(self, tmp_path: Path) -> None:
        backup_root, header, intent, terminal = _backup_tree(tmp_path)
        leaf = backup_root / RUN_ID / "a1" / "source" / "f1.md"
        leaf.unlink()
        os.mkfifo(leaf)
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        with pytest.raises(ManifestContainmentError, match="regular file"):
            read_manifest_set(path)

    def test_directory_leaf__refused(self, tmp_path: Path) -> None:
        backup_root, header, intent, terminal = _backup_tree(tmp_path)
        leaf = backup_root / RUN_ID / "a1" / "source" / "f1.md"
        leaf.unlink()
        leaf.mkdir()
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        with pytest.raises(ManifestContainmentError, match="regular file"):
            read_manifest_set(path)

    def test_overwritten_backup_without_sha__refused(self, tmp_path: Path) -> None:
        _, header, intent, terminal = _backup_tree(tmp_path, role="overwritten")
        overwritten = str(
            Path(str(header["backup_root"])) / RUN_ID / "a1" / "overwritten" / "f1.md"
        )
        for r in (intent, terminal):
            r["backup_path"] = None
            r["overwritten_backup_path"] = overwritten
            r["overwritten_sha256"] = None
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        with pytest.raises(ManifestContainmentError, match="overwritten_sha256"):
            read_manifest_set(path)

    def test_check_backup_objects_false__skips_filesystem_half(self, tmp_path: Path) -> None:
        """Verify (Plan D) reads with check_backup_objects=False: the derivable-
        key rules still run, the live-filesystem checks do not — a MISSING
        backup object parses (it becomes a verify finding, not an abort)."""
        backup_root, header, intent, terminal = _backup_tree(tmp_path)
        (backup_root / RUN_ID / "a1" / "source" / "f1.md").unlink()
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        loaded = read_manifest_set(path, check_backup_objects=False)
        assert loaded.records[0].backup_path is not None

    def test_uuid7_docmend_id__still_validated(self, tmp_path: Path) -> None:
        path = write_set(tmp_path / "m.jsonl", header_doc(), record_doc(1, docmend_id=UUID7))
        assert read_manifest_set(path).records[0].docmend_id == UUID7

    def test_missing_backup_component__refused(self, tmp_path: Path) -> None:
        backup_root, header, intent, terminal = _backup_tree(tmp_path)
        (backup_root / RUN_ID / "a1" / "source" / "f1.md").unlink()
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        with pytest.raises(ManifestContainmentError, match="missing"):
            read_manifest_set(path)

    def test_regular_file_as_intermediate_component__refused(self, tmp_path: Path) -> None:
        backup_root, header, intent, terminal = _backup_tree(tmp_path)
        role_dir = backup_root / RUN_ID / "a1" / "source"
        (role_dir / "f1.md").unlink()
        role_dir.rmdir()
        role_dir.write_bytes(b"a file where a directory belongs")
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        with pytest.raises(ManifestContainmentError, match="not a directory"):
            read_manifest_set(path)

    def test_diverging_role_path_between_intent_and_terminal__refused(self, tmp_path: Path) -> None:
        """F5's at-most-one-path-per-role rule at set scope IS the immutable
        rule: an intent and terminal disagreeing on backup_path are refused
        before trust validation even runs."""
        backup_root, header, intent, terminal = _backup_tree(tmp_path)
        second_key = backup_root / RUN_ID / "a1" / "source" / "other.md"
        second_key.write_bytes(b"different bytes")
        terminal["backup_path"] = str(second_key)
        path = write_set(tmp_path / "m.jsonl", header, intent, terminal)
        with pytest.raises(ArtifactError, match="immutable"):
            read_manifest_set(path)


class TestLifecycleEdges:
    def test_duplicate_intents__rejected(self, tmp_path: Path) -> None:
        first = record_doc(1, result="intent")
        second = record_doc(1, seq=2, result="intent")
        second["action_id"] = first["action_id"]
        path = write_set(tmp_path / "m.jsonl", header_doc(), first, second)
        with pytest.raises(ArtifactError, match="more than one intent"):
            read_manifest_set(path)

    def test_failed_terminal_with_after_hash__rejected(self, tmp_path: Path) -> None:
        intent = record_doc(1, result="intent")
        terminal = record_doc(1, seq=2, result="failed")
        terminal["action_id"] = intent["action_id"]
        terminal["error"] = {"class": "ERR-003", "message": "boom"}
        path = write_set(tmp_path / "m.jsonl", header_doc(), intent, terminal)
        with pytest.raises(ArtifactError, match="after hash"):
            read_manifest_set(path)

    def test_failed_terminal_with_null_after__accepted(self, tmp_path: Path) -> None:
        """The failed-after exemption's happy half: intent carries the EXPECTED
        hash, the failed terminal nulls it — legal, not an immutable violation."""
        intent = record_doc(1, result="intent")
        terminal = record_doc(1, seq=2, result="failed", after_sha256=None)
        terminal["action_id"] = intent["action_id"]
        terminal["error"] = {"class": "ERR-003", "message": "boom"}
        path = write_set(tmp_path / "m.jsonl", header_doc(), intent, terminal)
        assert read_manifest_set(path).records[1].result == "failed"

    def test_blank_lines__skipped(self, tmp_path: Path) -> None:
        path = write_set(tmp_path / "m.jsonl", header_doc(), record_doc(1))
        path.write_text(path.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
        assert len(read_manifest_set(path).records) == 1

    def test_writer_path_property(self, tmp_path: Path) -> None:
        writer = _writer(tmp_path / "m.jsonl")
        assert writer.path == tmp_path / "m.jsonl"
