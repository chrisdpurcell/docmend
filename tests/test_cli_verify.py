"""`docmend verify` CLI tests (spec: FR-014, IR-004, adr-0012; §18.5 exit taxonomy).

adr-0012 exit taxonomy is the contract under test: 0 clean, 1 findings, 2
invocation/artifact-input error, 3 safety refusal. Checks cover corpus content,
discovery completeness, frontmatter where present, manifest lifecycle and
recovery evidence, and exactly-once plan coverage across resumed attempts.

verify reuses `discovery.scan`'s walk + facts, so it configures logging the same
way scan does; the isolate_logging fixture mirrors tests/test_cli_scan.py.
"""

import json
import logging
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
import structlog
from tests.helpers.manifest2 import (
    OTHER_RUN_ID,
    RUN_ID,
    SHA_A,
    header_doc,
    record_doc,
    write_set,
)
from typer.testing import CliRunner

from docmend import artifacts, cli, lock
from docmend import verify as verify_module
from docmend.cli import app
from docmend.plan import Plan
from docmend.verify_coverage import VerificationEvidence
from docmend.writer import manifest as manifest_io

runner = CliRunner()
LOCK_RUN_ID = "run_20260711T150000Z_000055"


@pytest.fixture(autouse=True)
def isolate_logging() -> Iterator[None]:
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    yield
    for handler in root.handlers:
        if handler not in saved:
            handler.close()
    root.handlers = saved
    root.setLevel(saved_level)
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


@pytest.fixture(autouse=True)
def isolate_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep scan/verify read-lock files out of the developer's real state dir."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))


def test_verify_clean_corpus__exit_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-014: verify passes (exit 0) on a correctly converted corpus."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.md").write_bytes(b"clean utf-8, lf only\n")
    (corpus / "b.md").write_bytes(b"# heading\n\nbody text\n")

    result = runner.invoke(app, ["verify", str(corpus)])

    assert result.exit_code == 0, result.output
    [log_path] = (tmp_path / ".docmend").glob("docmend-*.jsonl")
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    stage_events = [event for event in events if str(event["event"]).startswith("stage.")]
    assert [(event["stage"], event["event"]) for event in stage_events] == [
        ("scan", "stage.start"),
        ("scan", "stage.complete"),
        ("verify", "stage.start"),
        ("verify", "stage.complete"),
    ]


def test_verify_bad_encoding__exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-014/adr-0012: a file not UTF-8 decodable without replacement is a finding (exit 1)."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "ok.md").write_bytes(b"clean\n")
    (corpus / "bad.md").write_bytes(b"caf\xe9 not utf-8\n")  # lone \xe9 is invalid UTF-8

    result = runner.invoke(app, ["verify", str(corpus)])

    assert result.exit_code == 1, result.output
    assert "bad.md" in result.output


def test_verify_crlf__exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-014/adr-0012: non-LF (CRLF) line endings are a finding (exit 1)."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "ok.md").write_bytes(b"clean\n")
    (corpus / "crlf.md").write_bytes(b"line one\r\nline two\r\n")

    result = runner.invoke(app, ["verify", str(corpus)])

    assert result.exit_code == 1, result.output
    assert "crlf.md" in result.output


def _apply_corpus(corpus: Path, tmp_path: Path) -> Path:
    """plan + apply --write over corpus (rename-only, no preservation needed);
    return the single manifest path written under .docmend/."""
    plan_out = tmp_path / "plan.json"
    planned = runner.invoke(app, ["plan", str(corpus), "--out", str(plan_out)])
    assert planned.exit_code in (0, 1), planned.output
    applied = runner.invoke(app, ["apply", str(plan_out), "--write"])
    assert applied.exit_code == 0, applied.output
    manifests = list((tmp_path / ".docmend").glob("docmend-*-manifest.jsonl"))
    assert len(manifests) == 1, manifests
    return manifests[0]


def _report_for_manifest(manifest_path: Path) -> Path:
    run_id = manifest_path.name.removeprefix("docmend-").removesuffix("-manifest.jsonl")
    return manifest_path.with_name(f"docmend-{run_id}-report.json")


def _new_artifact(before: set[Path], artifact_dir: Path, pattern: str) -> Path:
    created = set(artifact_dir.glob(pattern)) - before
    assert len(created) == 1, created
    return created.pop()


def _run_write_with_backups(
    corpus: Path,
    tmp_path: Path,
    *,
    overwrite: bool = False,
) -> tuple[Path, Path, Path]:
    """Run a real plan/apply write and return its plan, manifest, and report."""
    plan_path = tmp_path / "backup-plan.json"
    args = ["plan", str(corpus), "--out", str(plan_path)]
    if overwrite:
        config_path = tmp_path / "overwrite.toml"
        config_path.write_text('[rename]\non_collision = "overwrite"\n', encoding="utf-8")
        args.extend(["--config", str(config_path)])
    planned = runner.invoke(app, args)
    assert planned.exit_code == 0, planned.output
    applied = runner.invoke(
        app,
        [
            "apply",
            str(plan_path),
            "--write",
            "--backup-dir",
            str(tmp_path / "backups"),
        ],
    )
    assert applied.exit_code == 0, applied.output
    [manifest_path] = (tmp_path / ".docmend").glob("docmend-*-manifest.jsonl")
    return plan_path, manifest_path, _report_for_manifest(manifest_path)


def test_verify_reconciles_clean_manifest__exit_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-014/adr-0012: verify passes when the live outputs match the manifest's
    recorded after-hashes."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"already clean\n")  # rename .txt -> .md, no rewrite
    manifest = _apply_corpus(corpus, tmp_path)

    result = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--manifest",
            str(manifest),
            "--report",
            str(_report_for_manifest(manifest)),
        ],
    )

    assert result.exit_code == 0, result.output


def test_verify_hash_mismatch__exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-014: a converted output that no longer matches its recorded after-hash
    is a finding (the 'hash mismatch' defect class), exit 1."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"already clean\n")
    manifest = _apply_corpus(corpus, tmp_path)
    (corpus / "doc.md").write_bytes(b"tampered after apply\n")  # diverge from recorded after-hash

    result = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--manifest",
            str(manifest),
            "--report",
            str(_report_for_manifest(manifest)),
        ],
    )

    assert result.exit_code == 1, result.output
    assert "doc.md" in result.output


def test_verify_missing_output__exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """adr-0012: an applied output that has since disappeared is a finding (exit 1)."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"already clean\n")
    manifest = _apply_corpus(corpus, tmp_path)
    (corpus / "doc.md").unlink()  # the applied output vanished

    result = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--manifest",
            str(manifest),
            "--report",
            str(_report_for_manifest(manifest)),
        ],
    )

    assert result.exit_code == 1, result.output
    assert "doc.md" in result.output


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_verify_source_backup_damage__backup_finding_exit_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"line one\r\nline two\r\n")
    plan_path, manifest_path, report_path = _run_write_with_backups(corpus, tmp_path)
    record = manifest_io.read_manifest_set(manifest_path).records[-1]
    assert record.backup_path is not None
    backup = Path(record.backup_path)
    if damage == "missing":
        backup.unlink()
    else:
        backup.write_bytes(b"corrupt backup")

    result = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--plan",
            str(plan_path),
            "--manifest",
            str(manifest_path),
            "--report",
            str(report_path),
        ],
    )

    assert result.exit_code == 1, result.output
    assert "[backup]" in result.output
    assert "source backup" in result.output


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_verify_overwritten_backup_damage__backup_finding_exit_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"new target\n")
    (corpus / "doc.md").write_bytes(b"old target\n")
    plan_path, manifest_path, report_path = _run_write_with_backups(
        corpus, tmp_path, overwrite=True
    )
    record = manifest_io.read_manifest_set(manifest_path).records[-1]
    assert record.overwritten_backup_path is not None
    backup = Path(record.overwritten_backup_path)
    if damage == "missing":
        backup.unlink()
    else:
        backup.write_bytes(b"corrupt overwritten backup")

    result = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--plan",
            str(plan_path),
            "--manifest",
            str(manifest_path),
            "--report",
            str(report_path),
        ],
    )

    assert result.exit_code == 1, result.output
    assert "[backup]" in result.output
    assert "overwritten backup" in result.output


def test_verify_all_candidates_unreadable_or_timed_out__discovery_and_zero_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from docmend.watchdog import PerFileTimeoutError

    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "denied.md").write_bytes(b"unreadable\n")
    (corpus / "slow.md").write_bytes(b"slow\n")

    def fail_classification(path: Path, *_args: object, **_kwargs: object) -> object:
        if path.name == "slow.md":
            raise PerFileTimeoutError(0.0)
        raise OSError("synthetic read refusal")

    monkeypatch.setattr(cli.discovery, "classify_file", fail_classification)
    result = runner.invoke(app, ["verify", str(corpus)])

    assert result.exit_code == 1, result.output
    assert "[discovery-unreadable]" in result.output
    assert "[discovery-timeout]" in result.output
    assert "[zero-checked]" in result.output


@pytest.mark.parametrize("all_excluded", [False, True])
def test_verify_empty_or_all_excluded__clean_without_zero_checked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    all_excluded: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    args = ["verify", str(corpus)]
    if all_excluded:
        (corpus / "excluded.md").write_bytes(b"clean\n")
        config_path = tmp_path / "exclude.toml"
        config_path.write_text('[paths]\nexclude = ["*.md"]\n', encoding="utf-8")
        args.extend(["--config", str(config_path)])

    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.output
    assert "zero-checked" not in result.output


def test_verify_is_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """IR-004/adr-0012: verify mutates no corpus file and writes no manifest."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"already clean\n")
    manifest = _apply_corpus(corpus, tmp_path)
    before = {p: p.read_bytes() for p in corpus.rglob("*") if p.is_file()}
    manifests_before = len(list((tmp_path / ".docmend").glob("*-manifest.jsonl")))

    result = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--manifest",
            str(manifest),
            "--report",
            str(_report_for_manifest(manifest)),
        ],
    )

    assert result.exit_code == 0, result.output
    assert {p: p.read_bytes() for p in corpus.rglob("*") if p.is_file()} == before
    assert len(list((tmp_path / ".docmend").glob("*-manifest.jsonl"))) == manifests_before


def test_verify_unreadable_manifest__exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """adr-0012: an unreadable/absent input artifact is an invocation error (exit 2)."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.md").write_bytes(b"clean\n")

    result = runner.invoke(
        app, ["verify", str(corpus), "--manifest", str(tmp_path / "absent.jsonl")]
    )

    assert result.exit_code == 2, result.output


def test_verify_wrong_root_manifest__manifest_root_finding_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_bytes(b"clean\n")
    manifest_path = write_set(
        tmp_path / "wrong-root.jsonl",
        header_doc(source_root=str(tmp_path / "different-corpus")),
    )

    result = runner.invoke(app, ["verify", str(corpus), "--manifest", str(manifest_path)])

    assert result.exit_code == 1, result.output
    assert "[manifest-root]" in result.output


def test_verify_dangling_apply_intent__lifecycle_finding_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    target = corpus / "doc.md"
    target.write_bytes(b"clean\n")
    manifest_path = write_set(
        tmp_path / "dangling-apply.jsonl",
        header_doc(source_root=str(corpus)),
        record_doc(
            1,
            result="intent",
            original_path=str(target),
            target_path=str(target),
        ),
    )

    result = runner.invoke(app, ["verify", str(corpus), "--manifest", str(manifest_path)])

    assert result.exit_code == 1, result.output
    assert "[lifecycle]" in result.output
    assert "pending-intent" in result.output


def test_verify_dangling_restore_intent__lifecycle_finding_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    target = corpus / "doc.md"
    target.write_bytes(b"clean\n")
    apply_manifest = write_set(
        tmp_path / "apply.jsonl",
        header_doc(source_root=str(corpus)),
        record_doc(
            1,
            result="intent",
            original_path=str(target),
            target_path=str(target),
        ),
        record_doc(
            1,
            seq=2,
            original_path=str(target),
            target_path=str(target),
        ),
    )
    apply_sha = manifest_io.manifest_sha256(apply_manifest)
    restore_manifest = write_set(
        tmp_path / "restore.jsonl",
        header_doc(
            run_id=OTHER_RUN_ID,
            kind="restore",
            source_root=str(corpus),
            prior_manifest_sha256=apply_sha,
            prior_attempt={
                "run_id": RUN_ID,
                "report_sha256": None,
                "manifest_sha256": apply_sha,
            },
        ),
        record_doc(
            1,
            result="intent",
            run_id=OTHER_RUN_ID,
            original_path=str(target),
            target_path=str(target),
            undoes_action_id=f"{RUN_ID}/a1",
            undoes_run_id=RUN_ID,
        ),
    )

    result = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--manifest",
            str(restore_manifest),
            "--manifest",
            str(apply_manifest),
        ],
    )

    assert result.exit_code == 1, result.output
    assert "[lifecycle]" in result.output
    assert "pending-restore" in result.output


def test_verify_containment_escape__finding_without_opening_escaped_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_bytes(b"clean\n")
    escaped = tmp_path / "outside.md"
    manifest_path = write_set(
        tmp_path / "escape.jsonl",
        header_doc(source_root=str(corpus)),
        record_doc(
            1,
            result="intent",
            original_path=str(escaped),
            target_path=str(escaped),
        ),
    )

    def refuse_open(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("escaped manifest path was opened")

    monkeypatch.setattr(verify_module, "bind_file", refuse_open)
    result = runner.invoke(app, ["verify", str(corpus), "--manifest", str(manifest_path)])

    assert result.exit_code == 1, result.output
    assert "[manifest-containment]" in result.output
    assert "[hash]" not in result.output


def test_verify_lifecycle_invalid_manifest__input_error_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    target = corpus / "doc.md"
    target.write_bytes(b"clean\n")
    manifest_path = write_set(
        tmp_path / "invalid-lifecycle.jsonl",
        header_doc(source_root=str(corpus)),
        record_doc(
            1,
            result="intent",
            original_path=str(target),
            target_path=str(target),
        ),
        record_doc(
            1,
            seq=2,
            after_sha256=SHA_A,
            original_path=str(target),
            target_path=str(target),
        ),
    )

    result = runner.invoke(app, ["verify", str(corpus), "--manifest", str(manifest_path)])

    assert result.exit_code == 2, result.output
    assert "immutable field" in result.output


def test_verify_missing_run_id_sidecars__exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A named run with neither default evidence sidecar is an input error."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.md").write_bytes(b"clean\n")

    result = runner.invoke(app, ["verify", str(corpus), "--run-id", "run_x"])

    assert result.exit_code == 2, result.output
    assert "neither default manifest nor report sidecar exists" in result.output


def test_verify_run_id_sidecar__resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """IR-004: --run-id resolves the .docmend/ sidecar manifest (OQ-034 convention)."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"already clean\n")
    manifest = _apply_corpus(corpus, tmp_path)
    run_id = manifest.name[len("docmend-") : -len("-manifest.jsonl")]

    result = runner.invoke(app, ["verify", str(corpus), "--run-id", run_id])

    assert result.exit_code == 0, result.output


VALID_FRONTMATTER = (
    "---\n"
    "title: 'Untitled'\n"
    "docmend:\n"
    "  id: '01980000-0000-7000-8000-000000000001'\n"
    "  schema_version: '1.0'\n"
    "source:\n"
    "  original_path: 'synthetic/example.txt'\n"
    "  hash: 'sha256:" + "a" * 64 + "'\n"
    "output:\n"
    "  hash: 'sha256:" + "b" * 64 + "'\n"
    "---\n"
    "body\n"
)


def test_verify_valid_frontmatter__exit_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-016/adr-0011: a present, schema-valid frontmatter block passes."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_text(VALID_FRONTMATTER, encoding="utf-8")

    result = runner.invoke(app, ["verify", str(corpus)])
    assert result.exit_code == 0, result.output


def test_verify_invalid_frontmatter__exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-014 seeded-defect class 'invalid frontmatter': a present block that
    fails the DR-005 schema is a finding, exit 1."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_text(
        "---\ntitle: 'Untitled'\ninvented_field: true\n---\nbody\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["verify", str(corpus)])
    assert result.exit_code == 1, result.output
    assert "[frontmatter]" in result.output


def test_verify_frontmatter_scoped_to_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `---` opener in a non-.md file is body text, never a metadata claim."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "notes.txt").write_bytes(b"---\nnot: frontmatter\n---\nbody\n")

    result = runner.invoke(app, ["verify", str(corpus)])
    assert result.exit_code == 0, result.output


def test_verify_report_without_manifest__exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--report is a cross-artifact check; alone it has nothing to reconcile."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_bytes(b"clean\n")

    result = runner.invoke(app, ["verify", str(corpus), "--report", "r.json"])
    assert result.exit_code == 2, result.output


def test_verify_run_id__reconciles_report_sidecar_exit_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OQ-034 sidecar: --run-id pulls in the run's report when present and the
    clean report↔manifest accounting passes."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"already clean\n")
    manifest = _apply_corpus(corpus, tmp_path)
    run_id = manifest.name.removeprefix("docmend-").removesuffix("-manifest.jsonl")
    assert (tmp_path / ".docmend" / f"docmend-{run_id}-report.json").is_file()

    result = runner.invoke(app, ["verify", str(corpus), "--run-id", run_id])
    assert result.exit_code == 0, result.output


def test_verify_report_manifest_accounting_drift__exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-014 'skipped-file accounting': a report whose applied outcomes do not
    match the manifest's applied records is a finding, exit 1."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"already clean\n")
    manifest = _apply_corpus(corpus, tmp_path)
    run_id = manifest.name.removeprefix("docmend-").removesuffix("-manifest.jsonl")
    report_path = tmp_path / ".docmend" / f"docmend-{run_id}-report.json"
    doctored = json.loads(report_path.read_text(encoding="utf-8"))
    # Drop the applied outcome and keep totals consistent with the outcome list,
    # so read_report's intra-report rule passes and only the CROSS-artifact
    # accounting can catch the drift.
    doctored["outcomes"] = []
    doctored["totals"]["applied"] = 0
    report_path.write_text(json.dumps(doctored), encoding="utf-8")

    result = runner.invoke(app, ["verify", str(corpus), "--run-id", run_id])
    assert result.exit_code == 1, result.output
    assert "[accounting]" in result.output


def _plan_for_verify(corpus: Path, tmp_path: Path) -> Path:
    plan_path = tmp_path / "verify-plan.json"
    result = runner.invoke(app, ["plan", str(corpus), "--out", str(plan_path)])
    assert result.exit_code in (0, 1), result.output
    return plan_path


def test_verify_plan_1_x__exit_2_before_lock_or_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    document_path = corpus / "doc.txt"
    document_path.write_bytes(b"clean\n")
    plan_path = _plan_for_verify(corpus, tmp_path)
    plan_document = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_document["schema_version"] = "1.2"
    plan_document["config"]["parallel"] = {
        "enabled": False,
        "model": "process",
        "workers": "auto",
        "start_method": "forkserver",
        "chunksize": "auto",
        "maxtasksperchild": None,
    }
    plan_path.write_text(json.dumps(plan_document), encoding="utf-8")

    def boundary_should_not_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("legacy plan reached the verify lock or scan")

    monkeypatch.setattr(cli, "_acquire_read_lock", boundary_should_not_run)
    monkeypatch.setattr(cli.discovery, "scan", boundary_should_not_run)

    result = runner.invoke(app, ["verify", str(corpus), "--plan", str(plan_path)])

    assert result.exit_code == 2, result.output
    assert "plan schema 1.2" in result.output
    assert "regenerate" in result.output
    assert document_path.read_bytes() == b"clean\n"


def test_verify_plan_snapshot_precedes_lock__evidence_load_stays_inside_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"clean\n")
    plan_path = _plan_for_verify(corpus, tmp_path)
    events: list[str] = []
    real_read_plan_snapshot = cli.artifacts.read_plan_snapshot
    real_acquire_read_lock = cli._acquire_read_lock  # pyright: ignore[reportPrivateUsage]
    real_load_verification_evidence = cli.load_verification_evidence

    def read_plan_snapshot(path: Path) -> tuple[Plan, str]:
        events.append("plan")
        return real_read_plan_snapshot(path)

    def acquire_read_lock(source_root: Path, *, run_id: str, command: str) -> lock.RunLock | None:
        events.append("lock")
        return real_acquire_read_lock(source_root, run_id=run_id, command=command)

    def load_evidence(
        plan_path: Path | None,
        manifest_paths: Sequence[Path],
        report_paths: Sequence[Path],
        *,
        plan_snapshot: tuple[Plan, str] | None = None,
    ) -> VerificationEvidence:
        events.append("evidence")
        return real_load_verification_evidence(
            plan_path,
            manifest_paths,
            report_paths,
            plan_snapshot=plan_snapshot,
        )

    monkeypatch.setattr(cli.artifacts, "read_plan_snapshot", read_plan_snapshot)
    monkeypatch.setattr(cli, "_acquire_read_lock", acquire_read_lock)
    monkeypatch.setattr(cli, "load_verification_evidence", load_evidence)

    result = runner.invoke(app, ["verify", str(corpus), "--plan", str(plan_path)])

    assert result.exit_code == 1, result.output
    assert events == ["plan", "lock", "evidence"]


def test_verify_plan_without_attempt_evidence__coverage_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"clean\n")
    plan_path = _plan_for_verify(corpus, tmp_path)

    result = runner.invoke(app, ["verify", str(corpus), "--plan", str(plan_path)])

    assert result.exit_code == 1, result.output
    assert "[coverage]" in result.output
    assert "plan action has no terminal outcome" in result.output


def test_verify_aborted_report_omitting_trailing_action__coverage_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.txt").write_bytes(b"first\n")
    (corpus / "b.txt").write_bytes(b"second\n")
    config_path = tmp_path / "fail-collision.toml"
    config_path.write_text('[rename]\non_collision = "fail"\n', encoding="utf-8")
    plan_path = tmp_path / "verify-plan.json"
    planned = runner.invoke(
        app,
        ["plan", str(corpus), "--config", str(config_path), "--out", str(plan_path)],
    )
    assert planned.exit_code == 0, planned.output
    (corpus / "a.md").write_bytes(b"late collision\n")
    applied = runner.invoke(app, ["apply", str(plan_path), "--write", "--preserved-by", "external"])
    assert applied.exit_code == 1, applied.output
    [report_path] = (tmp_path / ".docmend").glob("docmend-*-report.json")
    report_document = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_document["outcomes"][-1]["status"] == "not-attempted"
    report_document["outcomes"].pop()
    report_document["totals"]["not_attempted"] -= 1
    report_path.write_text(json.dumps(report_document), encoding="utf-8")

    result = runner.invoke(
        app,
        ["verify", str(corpus), "--plan", str(plan_path), "--report", str(report_path)],
    )

    assert result.exit_code == 1, result.output
    assert "[coverage]" in result.output
    assert "plan action has no terminal outcome" in result.output


def test_verify_dry_run_only_report__coverage_uncertified_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"line one\r\nline two\r\n")
    plan_path = _plan_for_verify(corpus, tmp_path)
    preview = runner.invoke(app, ["apply", str(plan_path)])
    assert preview.exit_code == 0, preview.output
    [report_path] = (tmp_path / ".docmend").glob("docmend-*-report.json")

    result = runner.invoke(
        app,
        ["verify", str(corpus), "--plan", str(plan_path), "--report", str(report_path)],
    )

    assert result.exit_code == 1, result.output
    assert "[coverage-uncertified]" in result.output


def test_verify_apply_manifest_missing_report__coverage_unprovable_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"clean\n")
    manifest_path = _apply_corpus(corpus, tmp_path)
    report_path = _report_for_manifest(manifest_path)
    report_path.unlink()

    result = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--plan",
            str(tmp_path / "plan.json"),
            "--manifest",
            str(manifest_path),
        ],
    )

    assert result.exit_code == 1, result.output
    assert "[coverage-unprovable]" in result.output


def test_verify_plan_aware_single_write__clean_exit_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"clean\n")
    manifest_path = _apply_corpus(corpus, tmp_path)

    result = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--plan",
            str(tmp_path / "plan.json"),
            "--manifest",
            str(manifest_path),
            "--report",
            str(_report_for_manifest(manifest_path)),
        ],
    )

    assert result.exit_code == 0, result.output


def test_verify_out__writes_schema_valid_report_and_no_default_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_bytes(b"clean\n")
    out = tmp_path / "verify.json"

    result = runner.invoke(app, ["verify", str(corpus), "--out", str(out)])

    assert result.exit_code == 0, result.output
    report = artifacts.read_verify_report(out)
    assert report.verified_path == str(corpus)
    assert report.source_root == str(corpus.resolve())
    assert report.inputs == []
    assert report.checked_files == 1
    assert report.findings == []
    assert report.clean is True
    assert not list((tmp_path / ".docmend").glob("*-verify.json"))


def test_verify_without_out__writes_no_result_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_bytes(b"clean\n")

    result = runner.invoke(app, ["verify", str(corpus)])

    assert result.exit_code == 0, result.output
    assert not list(tmp_path.rglob("*verify*.json"))


def test_verify_out__replaces_existing_ordinary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_bytes(b"clean\n")
    out = tmp_path / "verify.json"
    out.write_bytes(b"old bytes\n")

    result = runner.invoke(app, ["verify", str(corpus), "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert artifacts.read_verify_report(out).clean is True


def test_verify_out__input_alias_refused_before_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"clean\n")
    plan_path = _plan_for_verify(corpus, tmp_path)
    original = plan_path.read_bytes()

    def fail_scan(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("verify scanned before rejecting an output alias")

    monkeypatch.setattr(cli.discovery, "scan", fail_scan)
    result = runner.invoke(
        app,
        ["verify", str(corpus), "--plan", str(plan_path), "--out", str(plan_path)],
    )

    assert result.exit_code == 3, result.output
    assert plan_path.read_bytes() == original


def test_verify_out__inside_corpus_refused_before_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_bytes(b"clean\n")
    out = corpus / "verify.json"
    called = False

    def fail_scan(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True
        raise AssertionError("verify scanned before rejecting an in-corpus output")

    monkeypatch.setattr(cli.discovery, "scan", fail_scan)
    result = runner.invoke(app, ["verify", str(corpus), "--out", str(out)])

    assert result.exit_code == 3, result.output
    assert called is False
    assert not out.exists()


def test_verify_out__excluded_canonical_artifact_dir_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_bytes(b"clean\n")
    monkeypatch.chdir(corpus)
    out = Path(".docmend/verify.json")

    result = runner.invoke(app, ["verify", ".", "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert artifacts.read_verify_report(out).clean is True


def test_verify_repeatable_shuffled_evidence__report_only_predecessor_and_relocated_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"line one\r\nline two\r\n")
    plan_path = _plan_for_verify(corpus, tmp_path)

    refused = runner.invoke(app, ["apply", str(plan_path), "--write"])
    assert refused.exit_code == 3, refused.output
    [first_report] = (tmp_path / ".docmend").glob("docmend-*-report.json")
    first_id = first_report.name.removeprefix("docmend-").removesuffix("-report.json")

    applied = runner.invoke(
        app,
        [
            "apply",
            str(plan_path),
            "--write",
            "--preserved-by",
            "external",
            "--resume-run-id",
            first_id,
        ],
    )
    assert applied.exit_code == 0, applied.output
    [manifest_path] = (tmp_path / ".docmend").glob("docmend-*-manifest.jsonl")
    second_id = manifest_path.name.removeprefix("docmend-").removesuffix("-manifest.jsonl")
    second_report = tmp_path / ".docmend" / f"docmend-{second_id}-report.json"
    relocated = tmp_path / "archive" / "first-report.json"
    relocated.parent.mkdir()
    first_report.rename(relocated)

    explicit = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--plan",
            str(plan_path),
            "--report",
            str(second_report),
            "--manifest",
            str(manifest_path),
            "--report",
            str(relocated),
        ],
    )
    combined = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--plan",
            str(plan_path),
            "--run-id",
            second_id,
            "--report",
            str(relocated),
        ],
    )

    assert explicit.exit_code == 0, explicit.output
    assert combined.exit_code == 0, combined.output


def test_verify_double_resume_lineage__clean_exit_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"line one\r\nline two\r\n")
    plan_path = _plan_for_verify(corpus, tmp_path)
    artifact_dir = tmp_path / ".docmend"

    first = runner.invoke(app, ["apply", str(plan_path), "--write"])
    assert first.exit_code == 3, first.output
    [r1] = artifact_dir.glob("docmend-*-report.json")

    reports_before = set(artifact_dir.glob("docmend-*-report.json"))
    second = runner.invoke(
        app,
        [
            "apply",
            str(plan_path),
            "--write",
            "--preserved-by",
            "external",
            "--prior-report",
            str(r1),
        ],
    )
    assert second.exit_code == 0, second.output
    [m2] = artifact_dir.glob("docmend-*-manifest.jsonl")
    r2 = _new_artifact(reports_before, artifact_dir, "docmend-*-report.json")

    reports_before = set(artifact_dir.glob("docmend-*-report.json"))
    third = runner.invoke(
        app,
        [
            "apply",
            str(plan_path),
            "--write",
            "--preserved-by",
            "external",
            "--prior-report",
            str(r1),
            "--resume-manifest",
            str(m2),
            "--prior-report",
            str(r2),
        ],
    )
    assert third.exit_code == 0, third.output
    r3 = _new_artifact(reports_before, artifact_dir, "docmend-*-report.json")

    result = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--plan",
            str(plan_path),
            "--report",
            str(r3),
            "--manifest",
            str(m2),
            "--report",
            str(r1),
            "--report",
            str(r2),
        ],
    )

    assert result.exit_code == 0, result.output


def test_verify_composed_lineage_missing_middle_report__orders_then_finds_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.txt").write_bytes(b"first\n")
    (corpus / "b.txt").write_bytes(b"second\n")
    plan_path = _plan_for_verify(corpus, tmp_path)
    artifact_dir = tmp_path / ".docmend"

    preview = runner.invoke(app, ["apply", str(plan_path)])
    assert preview.exit_code == 0, preview.output
    [r1] = artifact_dir.glob("docmend-*-report.json")
    (corpus / "b.md").write_bytes(b"late collision\n")

    manifests_before = set(artifact_dir.glob("docmend-*-manifest.jsonl"))
    reports_before = set(artifact_dir.glob("docmend-*-report.json"))
    second = runner.invoke(
        app,
        [
            "apply",
            str(plan_path),
            "--write",
            "--preserved-by",
            "external",
            "--prior-report",
            str(r1),
        ],
    )
    assert second.exit_code == 1, second.output
    m2 = _new_artifact(manifests_before, artifact_dir, "docmend-*-manifest.jsonl")
    r2 = _new_artifact(reports_before, artifact_dir, "docmend-*-report.json")
    r2.unlink()
    (corpus / "b.md").unlink()

    manifests_before = set(artifact_dir.glob("docmend-*-manifest.jsonl"))
    reports_before = set(artifact_dir.glob("docmend-*-report.json"))
    third = runner.invoke(
        app,
        [
            "apply",
            str(plan_path),
            "--write",
            "--preserved-by",
            "external",
            "--prior-report",
            str(r1),
            "--resume-manifest",
            str(m2),
        ],
    )
    assert third.exit_code == 0, third.output
    m3 = _new_artifact(manifests_before, artifact_dir, "docmend-*-manifest.jsonl")
    r3 = _new_artifact(reports_before, artifact_dir, "docmend-*-report.json")

    result = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--plan",
            str(plan_path),
            "--manifest",
            str(m3),
            "--report",
            str(r1),
            "--manifest",
            str(m2),
            "--report",
            str(r3),
        ],
    )

    assert result.exit_code == 1, result.output
    assert "coverage-unprovable" in result.output
    assert "attempt lineage" not in result.output


class TestVerifyLock:
    def test_same_root_lock_contention__exit_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "doc.md").write_bytes(b"clean\n")
        held = lock.acquire(corpus.resolve(), run_id=LOCK_RUN_ID, command="apply")
        try:
            result = runner.invoke(app, ["verify", str(corpus)])
        finally:
            held.release()
        assert result.exit_code == 3, result.output
        assert "another docmend run holds the lock" in result.output

    def test_lock_creation_failure__warns_and_continues(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "doc.md").write_bytes(b"clean\n")

        def refuse_lock(*_args: object, **_kwargs: object) -> lock.RunLock:
            raise PermissionError("state directory is unwritable")

        monkeypatch.setattr(cli.lock, "acquire", refuse_lock)
        result = runner.invoke(app, ["verify", str(corpus)])
        assert result.exit_code == 0, result.output
        assert "run lock unavailable" in result.output

    def test_ancestor_lock_does_not_block_exact_keyed_subtree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        corpus = tmp_path / "corpus"
        child = corpus / "child"
        child.mkdir(parents=True)
        (child / "doc.md").write_bytes(b"clean\n")
        held = lock.acquire(corpus.resolve(), run_id=LOCK_RUN_ID, command="apply")
        try:
            result = runner.invoke(app, ["verify", str(child)])
        finally:
            held.release()
        assert result.exit_code == 0, result.output
