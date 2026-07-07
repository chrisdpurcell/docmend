"""`docmend verify` CLI tests (spec: FR-014, IR-004, adr-0012; §18.5 exit taxonomy).

adr-0012 exit taxonomy is the contract under test: 0 clean, 1 findings, 2
invocation/artifact-input error, 3 safety refusal. v1 checks (RQ-006 / this
session's scope decision): UTF-8 decodability without replacement, LF-only line
endings, manifest/report reconciliation, frontmatter validity where present
(FR-016, adr-0011 — a no-frontmatter document is legal; the v1 pipeline emits
none), and report<->manifest accounting.

verify reuses `discovery.scan`'s walk + facts, so it configures logging the same
way scan does; the isolate_logging fixture mirrors tests/test_cli_scan.py.
"""

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

from docmend.cli import app

runner = CliRunner()


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


def test_verify_clean_corpus__exit_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-014: verify passes (exit 0) on a correctly converted corpus."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.md").write_bytes(b"clean utf-8, lf only\n")
    (corpus / "b.md").write_bytes(b"# heading\n\nbody text\n")

    result = runner.invoke(app, ["verify", str(corpus)])

    assert result.exit_code == 0, result.output


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

    result = runner.invoke(app, ["verify", str(corpus), "--manifest", str(manifest)])

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

    result = runner.invoke(app, ["verify", str(corpus), "--manifest", str(manifest)])

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

    result = runner.invoke(app, ["verify", str(corpus), "--manifest", str(manifest)])

    assert result.exit_code == 1, result.output
    assert "doc.md" in result.output


def test_verify_is_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """IR-004/adr-0012: verify mutates no corpus file and writes no manifest."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.txt").write_bytes(b"already clean\n")
    manifest = _apply_corpus(corpus, tmp_path)
    before = {p: p.read_bytes() for p in corpus.rglob("*") if p.is_file()}
    manifests_before = len(list((tmp_path / ".docmend").glob("*-manifest.jsonl")))

    result = runner.invoke(app, ["verify", str(corpus), "--manifest", str(manifest)])

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


def test_verify_manifest_and_run_id__mutually_exclusive_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IR-004: --manifest and --run-id name the same input two ways; refuse both (exit 2)."""
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.md").write_bytes(b"clean\n")

    result = runner.invoke(
        app, ["verify", str(corpus), "--manifest", "m.jsonl", "--run-id", "run_x"]
    )

    assert result.exit_code == 2, result.output


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
