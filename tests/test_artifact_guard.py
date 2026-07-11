"""Artifact destination guard (rev 0.26 IR-007, adr-0021, DMR-02).

Pure-function tests; the CLI wiring (refusal exit 3 before the pipeline runs)
is covered in the per-command CLI test files. The guard checks BOTH the
lexical directory entry publication replaces AND the resolved referent
(plan-review F3), and licenses the .docmend/ carve-out per actual destination
against the effective excludes (plan-review F2).
"""

from pathlib import Path

from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from docmend.artifacts import guard_artifact_destination

DEFAULT_EXCLUDES = ["**/.docmend/**"]


def _spec(lines: list[str]) -> PathSpec[GitIgnoreSpecPattern]:
    return PathSpec.from_lines(GitIgnoreSpecPattern, lines)


def _corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "victim.txt").write_bytes(b"corpus document\n")
    return root


def test_destination_inside_corpus__refused(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    refusal = guard_artifact_destination(root / "victim.txt", corpus_root=root)
    assert refusal is not None
    assert "inside" in refusal


def test_destination_outside_corpus__allowed(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    assert guard_artifact_destination(tmp_path / "report.json", corpus_root=root) is None


def test_symlink_outside_name_inside_referent__refused(tmp_path: Path) -> None:
    """An out-of-corpus NAME aliasing an in-corpus file: the resolved referent
    is inside, so publication would rewrite corpus bytes."""
    root = _corpus(tmp_path)
    link = tmp_path / "innocent.json"
    link.symlink_to(root / "victim.txt")
    refusal = guard_artifact_destination(link, corpus_root=root)
    assert refusal is not None
    assert (root / "victim.txt").read_bytes() == b"corpus document\n"


def test_symlink_inside_name_outside_referent__refused(tmp_path: Path) -> None:
    """The F3 mirror: an in-corpus NAME resolving outside. os.replace swaps
    the directory ENTRY, so the corpus-owned symlink entry would be replaced
    even though the referent is external — lexical containment must refuse."""
    root = _corpus(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"external file\n")
    link = root / "looks-internal.json"
    link.symlink_to(outside)
    refusal = guard_artifact_destination(link, corpus_root=root)
    assert refusal is not None
    assert link.is_symlink()  # refusal is non-mutating: the entry survives
    assert outside.read_bytes() == b"external file\n"


def test_carveout_allows_excluded_docmend_destination(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    artifact_root = root / ".docmend"
    dest = artifact_root / "docmend-run-inventory.json"
    assert (
        guard_artifact_destination(
            dest,
            corpus_root=root,
            artifact_root=artifact_root,
            exclude=_spec(DEFAULT_EXCLUDES),
        )
        is None
    )


def test_carveout_negated_destination__refused(tmp_path: Path) -> None:
    """plan-review F2: gitignore negation can re-include ONE destination while
    the rest of .docmend/ stays excluded — the license is per destination,
    so the re-included path is refused."""
    root = _corpus(tmp_path)
    artifact_root = root / ".docmend"
    dest = artifact_root / "docmend-run-report.json"
    spec = _spec(["**/.docmend/**", "!.docmend/docmend-run-report.json"])
    refusal = guard_artifact_destination(
        dest, corpus_root=root, artifact_root=artifact_root, exclude=spec
    )
    assert refusal is not None


def test_carveout_withdrawn__docmend_destination_refused(tmp_path: Path) -> None:
    """No exclude covering the destination (operator replaced the exclude set)
    means the canonical root is scannable corpus space: license withdrawn."""
    root = _corpus(tmp_path)
    artifact_root = root / ".docmend"
    dest = artifact_root / "docmend-run-inventory.json"
    refusal = guard_artifact_destination(
        dest, corpus_root=root, artifact_root=artifact_root, exclude=_spec(["*.bin"])
    )
    assert refusal is not None


def test_excluded_but_outside_artifact_root__refused(tmp_path: Path) -> None:
    """Exclusion alone is not a license: only the canonical artifact root is
    the authorized in-corpus namespace (adr-0021)."""
    root = _corpus(tmp_path)
    (root / "notes").mkdir()
    dest = root / "notes" / "report.json"
    refusal = guard_artifact_destination(
        dest,
        corpus_root=root,
        artifact_root=root / ".docmend",
        exclude=_spec(["**/.docmend/**", "notes/"]),
    )
    assert refusal is not None


def test_alias_of_invocation_input__refused(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    inventory = tmp_path / "inventory.json"
    inventory.write_bytes(b"{}")
    refusal = guard_artifact_destination(inventory, corpus_root=root, input_artifacts=[inventory])
    assert refusal is not None
    assert "input" in refusal


def test_non_regular_destination__refused(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    directory = tmp_path / "adir"
    directory.mkdir()
    refusal = guard_artifact_destination(directory, corpus_root=root)
    assert refusal is not None


def test_no_corpus_root__only_alias_and_type_rules_apply(tmp_path: Path) -> None:
    assert guard_artifact_destination(tmp_path / "x.json", corpus_root=None) is None
