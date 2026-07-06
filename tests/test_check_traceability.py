"""Regression tests for scripts/check_traceability.py (GAP-53 drift gate).

The script is exercised as a subprocess against synthetic fixture trees --
it is a repo-layout tool, not part of the docmend package, so it is not
imported (and stays outside the coverage gate's `source = ["src"]` scope).
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_traceability.py"

CLEAN_SPEC = """\
## 7. Requirements

| ID | Requirement |
| --- | --- |
| FR-001 | The system shall frob. |
| NFR-001 | Frobbing shall be fast. |

## 8. Architecture and Design

### 17.3 Requirement-to-Test Traceability

| Requirement ID | Test / Verification Method | Status |
| --- | --- | --- |
| FR-001 | Frob test. | Not Started |
| NFR-001 | Frob benchmark. | Not Started |

## 18. Deployment and Operations

## 21. Open Questions and Decisions

| ID | Question | Assumption | Blocking? | Owner | Needed By | Status |
| --- | --- | --- | --- | --- | --- | --- |
| OQ-001 | Settled thing? | Yes. | No | owner | MS-1 | Resolved |
| OQ-002 | Open thing? | Maybe. | No | owner | MS-2 | Open |

## Deviations Log
"""

RESOLVED = "### RQ-001 — settled thing\n"
OPEN = "### OQ-002 — open thing\n"


def make_tree(
    tmp_path: Path,
    spec: str = CLEAN_SPEC,
    resolved: str = RESOLVED,
    open_qs: str = OPEN,
    test_source: str = "",
) -> Path:
    (tmp_path / "docs" / "specs").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs" / "specs" / "docmend.md").write_text(spec, encoding="utf-8")
    (tmp_path / "docs" / "resolved-questions.md").write_text(resolved, encoding="utf-8")
    (tmp_path / "docs" / "open-questions.md").write_text(open_qs, encoding="utf-8")
    (tmp_path / "tests" / "test_stub.py").write_text(test_source, encoding="utf-8")
    return tmp_path


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_clean_tree_passes(tmp_path: Path) -> None:
    result = run(make_tree(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no traceability drift" in result.stdout


def test_requirement_missing_from_trace_matrix(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace("| NFR-001 | Frob benchmark. | Not Started |\n", "")
    result = run(make_tree(tmp_path, spec=spec))
    assert result.returncode == 1
    assert "missing from §17.3" in result.stdout
    assert "NFR-001" in result.stdout


def test_trace_row_for_undefined_requirement(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        "| NFR-001 | Frob benchmark. | Not Started |",
        "| NFR-001 | Frob benchmark. | Not Started |\n| FR-099 | Ghost test. | Not Started |",
    )
    result = run(make_tree(tmp_path, spec=spec))
    assert result.returncode == 1
    assert "not defined in §7" in result.stdout
    assert "FR-099" in result.stdout


def test_oq_row_without_record(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        "## Deviations Log",
        "| OQ-003 | Phantom? | — | No | owner | MS-1 | Resolved |\n\n## Deviations Log",
    )
    result = run(make_tree(tmp_path, spec=spec))
    assert result.returncode == 1
    assert "OQ-003" in result.stdout


def test_record_without_oq_row(tmp_path: Path) -> None:
    result = run(make_tree(tmp_path, resolved=RESOLVED + "### RQ-004 — orphan record\n"))
    assert result.returncode == 1
    assert "no spec §21 row" in result.stdout


def test_progress_claim_requires_test_mention(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        "| FR-001 | Frob test. | Not Started |", "| FR-001 | Frob test. | Done |"
    )
    untested = run(make_tree(tmp_path / "untested", spec=spec))
    assert untested.returncode == 1
    assert "claim progress" in untested.stdout

    tested = run(make_tree(tmp_path / "tested", spec=spec, test_source="# spec: FR-001\n"))
    assert tested.returncode == 0


def test_changed_layout_exits_two(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace("## 21. Open Questions and Decisions", "## 21. Renamed Heading")
    result = run(make_tree(tmp_path, spec=spec))
    assert result.returncode == 2
    assert "layout" in result.stderr
