# MS-2 Domain Logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land spec §19 MS-2 — the planning layer (`docmend plan`, FR-002/FR-015/DR-002), the pure transforms (FR-007–FR-009), the initial weird-document corpus (§17.2/§10.3), and the RQ-022 encoding-floor calibration checkpoint.

**Architecture:** Planning consumes the DR-001 inventory plus effective config, re-reads each surviving candidate's bytes once (read-only) to catch decode-replacement, predict transform outcomes, and enforce the EC-005 invariant, then emits the DR-002 plan artifact with per-action IDs, UUIDv7 `docmend_id`s, and C.4 provenance. Transforms are pure `str`/`bytes` functions in `docmend.transform` (import-linter forbids `os`/`io`/`pathlib`/`shutil`/`tempfile`/`docmend.writer` there — pass scalars, never config models or paths). The charset-normalizer legacy detection rung populates the inventory at scan time (DR-001 traceability note), behind its own module so the detector stays replaceable (§8.2.3 guidance).

**Tech Stack:** Python 3.14 (uv, Ruff, BasedPyright strict), pydantic v2 strict models, jsonschema Draft 2020-12, charset-normalizer ≥ 3.4.2 (new runtime dep), hypothesis, faker, pyfakefs (never for atomicity tests).

## Global Constraints

- Spec: `docs/specs/docmend.md` (SPEC-VHHB rev 0.14), Appendix B binding. Re-read §7, §21, Deviations Log each session.
- `docmend.transform` must import none of: `docmend.writer`, `os`, `io`, `pathlib`, `shutil`, `tempfile` (pyproject `[tool.importlinter]`; transitive through internal modules counts — so transform must NOT import `docmend.config`, which imports `pathlib`). The autouse fixture in `tests/unit/transform/conftest.py` blocks `open`/`os.open`/`io.FileIO` at test runtime.
- Transforms prefer plain string methods; any regex must be backtracking-safe by construction (§8.5). None are needed in this plan.
- v1 hard invariant (adr-0016, EC-005): mechanical transforms never reduce **non-whitespace character count** — exact, not configurable.
- File-class dispatch (adr-0016): `.txt`/`.md` get the full mechanical set; every other suffix (including `.html`/`.htm`) gets encoding + EOL normalization only, never whitespace transforms, never rename. Rename applies to `.txt` only.
- Encoding gate order (adr-0009, FR-007): BOM (authoritative, before NUL check) → strict full-file UTF-8 → ASCII → charset-normalizer legacy rung with dual skip gate (confidence `1.0 − chaos` < 0.80, or non-ASCII bytes < floor 20). Never decode with replacement characters (EC-003).
- Public repo (C-002): all fixtures synthetic (faker) or constructed byte patterns — never real library content or paths.
- Exit-code taxonomy (§18.5): 0 clean, 1 findings, 2 input error (ConfigError/ArtifactError), 3 safety refusal.
- Dependencies: only `charset-normalizer>=3.4.2` may be added (already approved in §8.6). Use `uv add`, never hand-edit `uv.lock`. Update `docs/dependency-licenses.md` in the same commit.
- Verification gate before claiming any task done: `uv run ruff format --check . && uv run ruff check . && uv run basedpyright && uv run coverage run -m pytest && uv run coverage report` (coverage `fail_under = 85`).
- Workflow: all commits on `dev`; single PR to `main` at the end. No `git add .`/`-A` — add files by name.
- Test naming follows the repo pattern `test_<subject>__<expectation>`; docstrings cite requirement IDs (the `traceability` CI gate greps requirement IDs under `tests/`).
- Timestamps/run-IDs are injected parameters (`run_id=`, `generated_at=`) — tests pin them; UUIDv7 minting is injected the same way (`mint_id=` defaulting to `uuid.uuid7`).

## Design decisions locked by this plan

These interpret the spec where it left the operational definition to the implementer. None contradicts a requirement; each cites its basis. If any turns out wrong during execution, stop and record an OQ-/DEV- row instead of guessing (Appendix B).

1. **Planning reads file bytes (read-only).** §8.1 requires planning to catch decode-only-with-replacement and would-be-shrink output — both need content. Planning hashes what it reads; a mismatch with the inventory's recorded hash yields skip reason `changed-since-scan` (the plan-time analog of AW-004; apply-time FR-003 remains the real guard).
2. **Plan schema amendment (pre-implementation, stays v1.0):** add `changed-since-scan` to the skip-reason enum. The schema's own description authorizes MS-2 extension via MINOR bumps, but no plan artifact has ever been produced, so amending 1.0 in place with a commit note is cleaner than minting 1.1 at birth.
3. **Operational risky-class definitions (FR-015):** `nul-bytes` = NUL present, no BOM, not matching the UTF-16 pattern; `utf16-suspect` = no BOM, ≥25% NUL bytes with ≥90% concentrated at one byte parity; `binary-suspect` = non-UTF-8, no BOM, no NUL, and charset-normalizer returns **no** candidate at all. Detection disabled (`encoding.detect=false`) skips non-UTF-8 files as `low-confidence-encoding` with detail `"encoding detection disabled"` (no schema change needed).
4. **No-op files produce neither action nor skip** — they simply appear in the inventory only. This is the plan half of FR-017 idempotency.
5. **Collision policy at plan time (FR-011 plan half):** `skip` → skip decision, exit 0; `fail` → skip decision recorded + run exits 1 (artifact still written — §8.5 forbids audit-trail-free runs); `overwrite` → action planned normally (apply's manifest records the overwrite at MS-3). Collision = rename target exists on disk under `source_root`, OR is an inventory file path, OR is already claimed by an earlier planned action.
6. **`--fail-on-low-confidence-encoding` (AW-003):** plan completes and writes its artifact; if any skip has reason `low-confidence-encoding` or `below-non-ascii-floor`, exit 1.
7. **Symlinks and hard-link-group members get explicit plan skip decisions** (`symlink`, `hard-link-alias`) so the plan is the complete apply worklist (EC-008/EC-011; the plan schema enumerates both reasons).
8. **Legacy detection runs at scan** (populates `encoding.detected`, method `charset-normalizer`) only when: no BOM, not strict-UTF-8-valid, no NUL bytes, and `encoding.detect` is true. NUL-bearing files never reach the detector — planning skips them before encoding matters.
9. **Transform execution order** (= the `operations` array order): `reencode`, `normalize_newlines`, `trim_trailing_whitespace`, `normalize_tabs`, `collapse_blank_lines`, `ensure_final_newline`, `rename` last. An operation is listed only if it would actually change the file (`reencode` iff source encoding ≠ UTF-8 or a BOM must be stripped; text ops iff output ≠ input at that step).
10. **Whitespace semantics:** a *blank line* is empty or whitespace-only; collapsing a run keeps its first `max` lines verbatim. `normalize_tabs` replaces each tab in a line's leading `[ \t]*` prefix with `tab_width` spaces; interior tabs untouched (adr-0016). Text ops require LF-normalized input (they run after `normalize_newlines` by construction).

---

### Task 1: Promote the corpus generator to a shared module

The seeded recipe→bytes generator lives inside `tests/test_discovery.py` with an explicit promotion note ("when MS-2's weird-document fixtures need it too, promote it to a shared location"). MS-2 needs it for planning tests and fixture generation.

**Files:**
- Create: `tests/corpus.py`
- Modify: `tests/test_discovery.py` (delete the moved block, import instead)
- Create: `.gitattributes` (repo root)

**Interfaces:**
- Consumes: nothing new.
- Produces: `tests/corpus.py` exporting `FileRecipe`, `RecipeEncoding`, `render(recipe, faker) -> bytes`, `materialize(root, recipes, faker) -> None`, `seeded_faker() -> Faker`, `CORPUS_RECIPES`, `RUN_ID`, `GENERATED_AT` — exactly the objects currently defined in `tests/test_discovery.py` lines ~27–108, unchanged.

- [ ] **Step 1: Create `tests/corpus.py`** by moving (verbatim, cut-and-paste) from `tests/test_discovery.py`: the `RUN_ID`/`GENERATED_AT` constants, `RecipeEncoding` type alias, `FileRecipe` dataclass, `_EOL`, `render`, `materialize`, `seeded_faker`, `CORPUS_RECIPES`, plus the imports they need (`hashlib` stays in test_discovery; corpus.py needs `dataclass`, `datetime`/`UTC`, `Path`, `Literal`, `Faker`, `NewlineStyle`). Module docstring:

```python
"""Shared synthetic-corpus generator (adr-0015: pure recipe -> bytes; disk adapter isolated).

Promoted out of tests/test_discovery.py at MS-2 (the promotion its docstring
promised) so planning tests and the weird-document fixture generator share one
provably synthetic (faker-seeded, C-002) source. `render` is the pure half;
`materialize` is the only place generator output touches the filesystem.
"""
```

- [ ] **Step 2: Update `tests/test_discovery.py`** — delete the moved definitions, add `from tests.corpus import CORPUS_RECIPES, GENERATED_AT, RUN_ID, FileRecipe, materialize, seeded_faker` (keep whatever names that file still uses; drop unused imports). Note: pytest rootdir has no `tests/__init__.py` — check; if imports fail, use `from corpus import ...` (pytest inserts rootdir/tests in sys.path via conftest) or add `tests/__init__.py` consistent with how `tests/unit/` is packaged today. Match the existing arrangement; do not restructure test packaging.

- [ ] **Step 3: Create `.gitattributes`** protecting byte-exact fixtures (CR/CRLF/legacy-encoding fixtures would be corrupted by EOL translation on checkout):

```gitattributes
# Weird-document corpus fixtures are byte-exact test inputs (spec §17.2):
# never EOL-translated, never diffed as text by tooling that would touch bytes.
tests/fixtures/weird_documents/** -text
```

- [ ] **Step 4: Run the full test suite**

Run: `uv run coverage run -m pytest && uv run coverage report`
Expected: all 125 existing tests PASS (pure refactor, zero behavior change).

- [ ] **Step 5: Commit**

```bash
git add tests/corpus.py tests/test_discovery.py .gitattributes
git commit -m "tests: promote seeded corpus generator to tests/corpus.py for MS-2 consumers"
```

---

### Task 2: Pure transform — newline normalization (FR-008)

**Files:**
- Create: `src/docmend/transform/newlines.py`
- Test: `tests/unit/transform/test_newlines.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `normalize_newlines(text: str) -> str` — CRLF, CR, and mixed all become LF. Pure; no imports beyond stdlib-typing-free string ops.

- [ ] **Step 1: Write the failing tests**

```python
"""FR-008: all line endings (CRLF, CR, mixed) normalize to LF. Pure (NFR-005)."""

from hypothesis import given
from hypothesis import strategies as st

from docmend.transform.newlines import normalize_newlines


class TestNormalizeNewlines:
    def test_crlf__becomes_lf(self) -> None:
        assert normalize_newlines("a\r\nb\r\n") == "a\nb\n"

    def test_bare_cr__becomes_lf(self) -> None:
        assert normalize_newlines("a\rb\r") == "a\nb\n"

    def test_mixed__becomes_lf(self) -> None:
        # EC-006: mixed styles within one file all normalize.
        assert normalize_newlines("a\r\nb\rc\nd") == "a\nb\nc\nd"

    def test_lf_only__unchanged(self) -> None:
        assert normalize_newlines("a\nb\n") == "a\nb\n"

    def test_empty__unchanged(self) -> None:
        assert normalize_newlines("") == ""


class TestNormalizeNewlinesProperties:
    @given(st.text())
    def test_output_never_contains_cr(self, text: str) -> None:
        assert "\r" not in normalize_newlines(text)

    @given(st.text())
    def test_idempotent(self, text: str) -> None:
        once = normalize_newlines(text)
        assert normalize_newlines(once) == once

    @given(st.text())
    def test_non_whitespace_preserved(self, text: str) -> None:
        # The EC-005 invariant holds by construction for this transform.
        strip = lambda s: "".join(s.split())  # noqa: E731
        assert strip(normalize_newlines(text)) == strip(text)

    @given(st.text())
    def test_line_structure_matches_universal_newlines(self, text: str) -> None:
        assert normalize_newlines(text).split("\n") == text.splitlines() or text == ""
```

Note on the last property: `splitlines()` splits on more separators than CR/CRLF/LF (e.g. `\x85`, ` `), so it will fail as written for those inputs — replace it with a reference comparison limited to the three styles:

```python
    @given(st.text(alphabet=st.characters(exclude_characters="\x85  \x0b\x0c")))
    def test_line_count_preserved(self, text: str) -> None:
        reference = text.replace("\r\n", "\n").replace("\r", "\n")
        assert normalize_newlines(text) == reference
```

Use this corrected version (drop `test_line_structure_matches_universal_newlines`). FR-008 covers CR/CRLF/LF only; Unicode line separators are content, not newlines, and must pass through untouched — assert that too:

```python
    def test_unicode_line_separators__untouched(self) -> None:
        assert normalize_newlines("a b\x85c") == "a b\x85c"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/transform/test_newlines.py -v`
Expected: FAIL — `ModuleNotFoundError: docmend.transform.newlines`

- [ ] **Step 3: Implement**

```python
"""Newline normalization (FR-008) — the spec's "two-replace one-liner" (§8.1).

Pure (NFR-005): text in, text out. Order matters: CRLF must collapse before
bare CR, or every CRLF would double-convert to two LFs. Unicode line
separators (NEL, LS, PS) are document content, not newline styles — untouched.
"""


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/transform/test_newlines.py -v`
Expected: PASS (all). The autouse purity fixture proves no filesystem access.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/transform/newlines.py tests/unit/transform/test_newlines.py
git commit -m "transform: newline normalization to LF (FR-008, EC-006)"
```

---

### Task 3: Pure transforms — whitespace quartet (FR-009)

**Files:**
- Create: `src/docmend/transform/whitespace.py`
- Test: `tests/unit/transform/test_whitespace.py`

**Interfaces:**
- Consumes: nothing (plain scalars only — the import-linter contract bars config models).
- Produces:
  - `trim_trailing(text: str) -> str`
  - `ensure_final_newline(text: str) -> str`
  - `collapse_blank_lines(text: str, max_consecutive: int) -> str`
  - `normalize_tabs(text: str, tab_width: int) -> str`
  - All assume LF-normalized input (documented precondition; planning runs `normalize_newlines` first).

- [ ] **Step 1: Write the failing tests**

```python
"""FR-009 whitespace transforms (OQ-031 tab semantics, EC-009 final newline). Pure (NFR-005)."""

from hypothesis import given
from hypothesis import strategies as st

from docmend.transform.whitespace import (
    collapse_blank_lines,
    ensure_final_newline,
    normalize_tabs,
    trim_trailing,
)

# LF-normalized text (the documented precondition).
lf_text = st.text(alphabet=st.characters(exclude_characters="\r")).map(
    lambda s: s.replace("\r", "")
)


def non_ws(s: str) -> str:
    return "".join(s.split())


class TestTrimTrailing:
    def test_spaces_and_tabs_trimmed(self) -> None:
        assert trim_trailing("a  \nb\t\nc") == "a\nb\nc"

    def test_leading_whitespace_untouched(self) -> None:
        assert trim_trailing("  a\n\tb\n") == "  a\n\tb\n"

    def test_whitespace_only_line_becomes_empty(self) -> None:
        assert trim_trailing("a\n   \nb") == "a\n\nb"

    @given(lf_text)
    def test_idempotent(self, text: str) -> None:
        once = trim_trailing(text)
        assert trim_trailing(once) == once

    @given(lf_text)
    def test_non_whitespace_preserved(self, text: str) -> None:
        assert non_ws(trim_trailing(text)) == non_ws(text)

    @given(lf_text)
    def test_no_line_ends_with_space_or_tab(self, text: str) -> None:
        assert all(not line.endswith((" ", "\t")) for line in trim_trailing(text).split("\n"))


class TestEnsureFinalNewline:
    def test_missing_final_newline_added(self) -> None:
        assert ensure_final_newline("a") == "a\n"

    def test_multiple_final_newlines_reduced_to_one(self) -> None:
        assert ensure_final_newline("a\n\n\n") == "a\n"

    def test_exactly_one_unchanged(self) -> None:
        assert ensure_final_newline("a\n") == "a\n"

    def test_empty_gains_newline(self) -> None:
        # EC-009: a zero-byte file receives final-newline enforcement mechanically.
        assert ensure_final_newline("") == "\n"

    @given(lf_text)
    def test_always_exactly_one_final_newline(self, text: str) -> None:
        result = ensure_final_newline(text)
        assert result.endswith("\n") and not result.endswith("\n\n")

    @given(lf_text)
    def test_idempotent(self, text: str) -> None:
        once = ensure_final_newline(text)
        assert ensure_final_newline(once) == once


class TestCollapseBlankLines:
    def test_run_beyond_max_collapsed(self) -> None:
        assert collapse_blank_lines("a\n\n\n\n\nb", 2) == "a\n\n\nb"
        # 5 newlines = 4 blank lines between a and b -> keep 2.

    def test_run_at_max_unchanged(self) -> None:
        assert collapse_blank_lines("a\n\n\nb", 2) == "a\n\n\nb"

    def test_whitespace_only_lines_count_as_blank(self) -> None:
        # First `max` lines of the run survive VERBATIM (whitespace kept);
        # trim_trailing owns cleaning them, not this transform.
        assert collapse_blank_lines("a\n \n\t\n \nb", 1) == "a\n \nb"

    def test_zero_max_removes_all_blank_lines(self) -> None:
        assert collapse_blank_lines("a\n\n\nb", 0) == "a\nb"

    def test_empty_text_unchanged(self) -> None:
        # EC-009 guard: split("\n") on "" yields [""], which the trailing-newline
        # peel would otherwise turn into a spurious "\n".
        assert collapse_blank_lines("", 3) == ""

    def test_leading_and_trailing_runs_collapsed(self) -> None:
        assert collapse_blank_lines("\n\n\na\n\n\n", 1) == "\na\n\n"
        # leading: 3 blank lines -> 1; trailing: text ends with newline, so the
        # trailing run is 2 blank lines -> 1 (final line "" is not a line).

    @given(lf_text, st.integers(min_value=0, max_value=5))
    def test_idempotent(self, text: str, max_blank: int) -> None:
        once = collapse_blank_lines(text, max_blank)
        assert collapse_blank_lines(once, max_blank) == once

    @given(lf_text, st.integers(min_value=0, max_value=5))
    def test_non_whitespace_preserved(self, text: str, max_blank: int) -> None:
        assert non_ws(collapse_blank_lines(text, max_blank)) == non_ws(text)

    @given(lf_text, st.integers(min_value=0, max_value=5))
    def test_no_run_exceeds_max(self, text: str, max_blank: int) -> None:
        lines = collapse_blank_lines(text, max_blank).split("\n")
        run = 0
        for line in lines[:-1] if lines and lines[-1] == "" else lines:
            run = run + 1 if line.strip(" \t") == "" else 0
            assert run <= max_blank


class TestNormalizeTabs:
    def test_leading_tabs_converted(self) -> None:
        assert normalize_tabs("\tx\n\t\ty", 4) == "    x\n        y"

    def test_interior_tabs_untouched(self) -> None:
        # adr-0016: column-aligned tables/ASCII art are content.
        assert normalize_tabs("a\tb\tc", 4) == "a\tb\tc"

    def test_tabs_in_mixed_leading_whitespace_converted(self) -> None:
        assert normalize_tabs(" \t x", 2) == "    x"
        # leading prefix " \t " -> space + 2 spaces + space.

    def test_tab_width_respected(self) -> None:
        assert normalize_tabs("\tx", 8) == "        x"

    @given(lf_text, st.integers(min_value=1, max_value=8))
    def test_idempotent(self, text: str, width: int) -> None:
        once = normalize_tabs(text, width)
        assert normalize_tabs(once, width) == once

    @given(lf_text, st.integers(min_value=1, max_value=8))
    def test_non_whitespace_preserved(self, text: str, width: int) -> None:
        assert non_ws(normalize_tabs(text, width)) == non_ws(text)

    @given(lf_text, st.integers(min_value=1, max_value=8))
    def test_no_leading_tabs_remain(self, text: str, width: int) -> None:
        for line in normalize_tabs(text, width).split("\n"):
            prefix_end = len(line) - len(line.lstrip(" \t"))
            assert "\t" not in line[:prefix_end]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/transform/test_whitespace.py -v`
Expected: FAIL — `ModuleNotFoundError: docmend.transform.whitespace`

- [ ] **Step 3: Implement**

```python
"""Whitespace transforms (FR-009; tab semantics per adr-0016/OQ-031).

Pure (NFR-005): text in, text out, plain string methods only (§8.5 regex rule
satisfied by using none). Shared precondition: input is LF-normalized —
planning always runs normalize_newlines first, so lines are split on "\\n".

A "blank line" is empty or whitespace-only. Collapsing keeps the first `max`
lines of an over-long run VERBATIM: cleaning whitespace-only survivors is
trim_trailing's job, keeping each transform individually configurable (FR-009).
"""


def trim_trailing(text: str) -> str:
    return "\n".join(line.rstrip(" \t") for line in text.split("\n"))


def ensure_final_newline(text: str) -> str:
    return text.rstrip("\n") + "\n"


def collapse_blank_lines(text: str, max_consecutive: int) -> str:
    if not text:
        return text  # EC-009: no lines means nothing to collapse, never a spurious newline
    # The final "" element after a trailing newline is split() bookkeeping,
    # not a line; peel it off so a trailing blank run is measured correctly.
    lines = text.split("\n")
    trailing_newline = lines[-1] == ""
    if trailing_newline:
        lines = lines[:-1]
    kept: list[str] = []
    run = 0
    for line in lines:
        if line.strip(" \t") == "":
            run += 1
            if run > max_consecutive:
                continue
        else:
            run = 0
        kept.append(line)
    return "\n".join(kept) + ("\n" if trailing_newline else "")


def normalize_tabs(text: str, tab_width: int) -> str:
    converted: list[str] = []
    for line in text.split("\n"):
        prefix_len = len(line) - len(line.lstrip(" \t"))
        prefix = line[:prefix_len].replace("\t", " " * tab_width)
        converted.append(prefix + line[prefix_len:])
    return "\n".join(converted)
```

Watch one property-test edge: `ensure_final_newline` on text containing only newlines (`"\n\n"` → `"\n"`) and `collapse_blank_lines` leading-run counting — if the `test_leading_and_trailing_runs_collapsed` expectation disagrees with the implementation by one line, recompute the expectation by hand against the "final empty element is bookkeeping" rule and fix the **test** only if the implementation matches the documented semantics (first `max` lines of each run survive).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/transform/test_whitespace.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/transform/whitespace.py tests/unit/transform/test_whitespace.py
git commit -m "transform: whitespace quartet - trim, final newline, blank-line collapse, leading tabs (FR-009)"
```

---

### Task 4: Pure transform — encoding decode/encode (FR-007 codec half)

**Files:**
- Create: `src/docmend/transform/encoding.py`
- Test: `tests/unit/transform/test_encoding.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `decode_source(data: bytes, *, bom: str | None, encoding_name: str) -> str` — strict decode; strips the BOM bytes first when `bom` is one of `"utf-8" | "utf-16-le" | "utf-16-be" | "utf-32-le" | "utf-32-be"` (the inventory's `BomKind` values, passed as plain strings — no model import); raises `UnicodeDecodeError` on any undecodable byte (EC-003 is caught by the caller, never smoothed with replacement characters).
  - `encode_utf8(text: str) -> bytes` — UTF-8, never a BOM (D-002).

- [ ] **Step 1: Write the failing tests**

```python
"""FR-007 codec half: strict decode (BOM-aware, EC-007/EC-010) and UTF-8-no-BOM encode (D-002).

Pure (NFR-005): bytes/str in memory only.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from docmend.transform.encoding import decode_source, encode_utf8


class TestDecodeSource:
    def test_plain_utf8(self) -> None:
        assert decode_source("héllo".encode(), bom=None, encoding_name="utf-8") == "héllo"

    def test_utf8_bom_stripped(self) -> None:
        # EC-007: BOM decoded correctly and never reaches the text.
        data = b"\xef\xbb\xbfabc"
        assert decode_source(data, bom="utf-8", encoding_name="utf-8") == "abc"

    def test_utf16_le_bom(self) -> None:
        # EC-010: BOM'd UTF-16 decodes per its BOM (OQ-026).
        data = b"\xff\xfe" + "ab".encode("utf-16-le")
        assert decode_source(data, bom="utf-16-le", encoding_name="utf-16-le") == "ab"

    def test_utf32_be_bom(self) -> None:
        data = b"\x00\x00\xfe\xff" + "a".encode("utf-32-be")
        assert decode_source(data, bom="utf-32-be", encoding_name="utf-32-be") == "a"

    def test_windows_1252(self) -> None:
        assert decode_source(b"caf\xe9", bom=None, encoding_name="cp1252") == "café"

    def test_undecodable_byte_raises(self) -> None:
        # EC-003: strict decode, never replacement characters. 0x81 is undefined in cp1252.
        with pytest.raises(UnicodeDecodeError):
            decode_source(b"ok\x81", bom=None, encoding_name="cp1252")

    def test_empty_after_bom(self) -> None:
        assert decode_source(b"\xef\xbb\xbf", bom="utf-8", encoding_name="utf-8") == ""


class TestEncodeUtf8:
    def test_never_emits_bom(self) -> None:
        assert not encode_utf8("abc").startswith(b"\xef\xbb\xbf")

    @given(st.text())
    def test_round_trip(self, text: str) -> None:
        assert decode_source(encode_utf8(text), bom=None, encoding_name="utf-8") == text
```

Note: hypothesis `st.text()` can generate surrogates? It does not by default (valid text only) — the round-trip property is safe as written.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/transform/test_encoding.py -v`
Expected: FAIL — `ModuleNotFoundError: docmend.transform.encoding`

- [ ] **Step 3: Implement**

```python
"""Encoding decode/encode (FR-007 codec half; D-002 UTF-8-no-BOM output).

Pure (NFR-005): bytes in, str out. Decoding is STRICT by contract — a byte the
declared encoding cannot represent raises UnicodeDecodeError, and the planning
layer maps that to the `decode-replacement` skip (EC-003); replacement
characters are silent corruption and never an output of this module.

The caller supplies the BOM kind the discovery layer sniffed (inventory
`encoding.bom`); the BOM bytes are stripped here so they can never leak into
text (EC-007), and `encode_utf8` never writes one (D-002).
"""

_BOM_LENGTH = {"utf-8": 3, "utf-16-le": 2, "utf-16-be": 2, "utf-32-le": 4, "utf-32-be": 4}


def decode_source(data: bytes, *, bom: str | None, encoding_name: str) -> str:
    if bom is not None:
        data = data[_BOM_LENGTH[bom] :]
    return data.decode(encoding_name, errors="strict")


def encode_utf8(text: str) -> bytes:
    return text.encode("utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/transform/test_encoding.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/transform/encoding.py tests/unit/transform/test_encoding.py
git commit -m "transform: strict BOM-aware decode and UTF-8-no-BOM encode (FR-007, EC-003/EC-007)"
```

---

### Task 5: Transform dispatch — file classes, pipeline, operations, EC-005 counter

**Files:**
- Create: `src/docmend/transform/dispatch.py`
- Test: `tests/unit/transform/test_dispatch.py`

**Interfaces:**
- Consumes: Task 2–3 functions (`normalize_newlines`, `trim_trailing`, `ensure_final_newline`, `collapse_blank_lines`, `normalize_tabs`).
- Produces (planning imports all of these from here):
  - `type Operation = Literal["rename", "reencode", "normalize_newlines", "trim_trailing_whitespace", "ensure_final_newline", "collapse_blank_lines", "normalize_tabs", "frontmatter_migrate"]` — mirrors the plan schema's operation enum; the plan models (Task 7) import it from here so the vocabulary is single-sourced.
  - `type FileClass = Literal["text", "markup"]`
  - `classify_suffix(suffix: str) -> FileClass` — `.txt`/`.md` (case-insensitive) → `"text"`, everything else → `"markup"` (adr-0016 two-class dispatch; unknown suffixes get the conservative minimal set).
  - `apply_text_transforms(text: str, file_class: FileClass, *, trim_trailing_ws: bool, final_newline: bool, collapse_max: int | None, tab_width: int | None) -> tuple[str, list[Operation]]` — runs the pipeline in canonical order, returns the transformed text and the operations that actually changed it. `collapse_max=None` / `tab_width=None` mean "transform disabled" (planning maps config booleans to these scalars — dispatch must not import `docmend.config`). For `"markup"`, only `normalize_newlines` ever runs regardless of the flags.
  - `non_whitespace_count(text: str) -> int` — the EC-005 invariant metric (`sum(len(part) for part in text.split())`, Unicode-whitespace-aware and C-speed).

- [ ] **Step 1: Write the failing tests**

```python
"""adr-0016 dispatch: per-file-class transform sets, canonical order, EC-005 metric. Pure."""

from hypothesis import given
from hypothesis import strategies as st

from docmend.transform.dispatch import (
    apply_text_transforms,
    classify_suffix,
    non_whitespace_count,
)


class TestClassifySuffix:
    def test_txt_and_md_are_text(self) -> None:
        assert classify_suffix(".txt") == "text"
        assert classify_suffix(".md") == "text"
        assert classify_suffix(".TXT") == "text"

    def test_html_and_everything_else_is_markup(self) -> None:
        # adr-0016: markup gets encoding+EOL only; unknown suffixes take the
        # same conservative minimal set.
        for suffix in (".html", ".htm", ".rst", "", ".log"):
            assert classify_suffix(suffix) == "markup"


class TestTextClassPipeline:
    def test_all_transforms_run_in_canonical_order(self) -> None:
        text = "a  \r\n\tb\n\n\n\n\nc"
        result, ops = apply_text_transforms(
            text, "text", trim_trailing_ws=True, final_newline=True, collapse_max=2, tab_width=4
        )
        assert result == "a\n    b\n\n\nc\n"
        assert ops == [
            "normalize_newlines",
            "trim_trailing_whitespace",
            "normalize_tabs",
            "collapse_blank_lines",
            "ensure_final_newline",
        ]

    def test_noop_input_yields_no_operations(self) -> None:
        # FR-017's plan half: an already-clean file produces zero operations.
        result, ops = apply_text_transforms(
            "a\nb\n", "text", trim_trailing_ws=True, final_newline=True, collapse_max=3, tab_width=None
        )
        assert result == "a\nb\n"
        assert ops == []

    def test_disabled_transforms_do_not_run(self) -> None:
        result, ops = apply_text_transforms(
            "a  \n", "text", trim_trailing_ws=False, final_newline=False, collapse_max=None, tab_width=None
        )
        assert result == "a  \n"
        assert ops == []


class TestMarkupClassPipeline:
    def test_markup_gets_only_newline_normalization(self) -> None:
        # adr-0016 confirmation: HTML receives exactly encoding/EOL changes.
        text = "<pre>a  \r\n\n\n\n\nb\t</pre>"
        result, ops = apply_text_transforms(
            text, "markup", trim_trailing_ws=True, final_newline=True, collapse_max=1, tab_width=4
        )
        assert result == "<pre>a  \n\n\n\n\nb\t</pre>"
        assert ops == ["normalize_newlines"]


class TestInvariantMetric:
    def test_counts_non_whitespace_only(self) -> None:
        assert non_whitespace_count(" a\tb\nc ") == 3

    def test_unicode_whitespace_ignored(self) -> None:
        assert non_whitespace_count("a b") == 2

    @given(
        st.text(alphabet=st.characters(exclude_characters="\r")),
        st.booleans(),
        st.booleans(),
        st.one_of(st.none(), st.integers(min_value=0, max_value=4)),
        st.one_of(st.none(), st.integers(min_value=1, max_value=8)),
        st.sampled_from(["text", "markup"]),
    )
    def test_pipeline_never_reduces_non_whitespace(
        self,
        text: str,
        trim: bool,
        final: bool,
        collapse: int | None,
        tabs: int | None,
        cls: str,
    ) -> None:
        # The EC-005 hard invariant holds for every configuration by construction.
        result, _ = apply_text_transforms(
            text, cls, trim_trailing_ws=trim, final_newline=final, collapse_max=collapse, tab_width=tabs
        )
        assert non_whitespace_count(result) == non_whitespace_count(text)
```

(` ` is NBSP; `str.split()` treats it as whitespace, which is exactly the Unicode-aware behavior EC-005 wants — decoded characters, not bytes.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/transform/test_dispatch.py -v`
Expected: FAIL — `ModuleNotFoundError: docmend.transform.dispatch`

- [ ] **Step 3: Implement**

```python
"""Per-file-class transform dispatch (adr-0016) and the EC-005 invariant metric.

Architectural role: the "dispatch is a seam in the transform layer, not
scattered conditionals" decision (adr-0016) lives here — planning asks this
module what a file's bytes would become and which operations that took;
it never sequences transforms itself.

Cross-file contracts:
- `Operation` mirrors the plan schema's operation enum verbatim; docmend.plan
  imports it from here so schema, models, and dispatch share one vocabulary.
  (plan -> transform is the allowed import direction; transform imports no
  internal module, keeping the NFR-005 import-linter contract trivially green.)
- Scalars in, scalars out: config booleans/ints are unpacked by the caller
  because docmend.config imports pathlib, which this package is forbidden.
- Canonical execution order (= the recorded operations order): reencode
  happens outside this module (bytes-level), then normalize_newlines,
  trim_trailing_whitespace, normalize_tabs, collapse_blank_lines,
  ensure_final_newline; rename is a path operation appended by planning.
"""

from typing import Literal

from docmend.transform.newlines import normalize_newlines
from docmend.transform.whitespace import (
    collapse_blank_lines,
    ensure_final_newline,
    normalize_tabs,
    trim_trailing,
)

type Operation = Literal[
    "rename",
    "reencode",
    "normalize_newlines",
    "trim_trailing_whitespace",
    "ensure_final_newline",
    "collapse_blank_lines",
    "normalize_tabs",
    "frontmatter_migrate",
]
type FileClass = Literal["text", "markup"]

_TEXT_SUFFIXES = frozenset({".txt", ".md"})


def classify_suffix(suffix: str) -> FileClass:
    return "text" if suffix.lower() in _TEXT_SUFFIXES else "markup"


def non_whitespace_count(text: str) -> int:
    """EC-005 metric: decoded non-whitespace characters (Unicode-aware via str.split)."""
    return sum(len(part) for part in text.split())


def apply_text_transforms(
    text: str,
    file_class: FileClass,
    *,
    trim_trailing_ws: bool,
    final_newline: bool,
    collapse_max: int | None,
    tab_width: int | None,
) -> tuple[str, list[Operation]]:
    operations: list[Operation] = []

    def step(op: Operation, result: str, current: str) -> str:
        if result != current:
            operations.append(op)
        return result

    out = step("normalize_newlines", normalize_newlines(text), text)
    if file_class == "markup":
        # adr-0016: markup receives encoding + EOL normalization only.
        return out, operations
    if trim_trailing_ws:
        out = step("trim_trailing_whitespace", trim_trailing(out), out)
    if tab_width is not None:
        out = step("normalize_tabs", normalize_tabs(out, tab_width), out)
    if collapse_max is not None:
        out = step("collapse_blank_lines", collapse_blank_lines(out, collapse_max), out)
    if final_newline:
        out = step("ensure_final_newline", ensure_final_newline(out), out)
    return out, operations
```

- [ ] **Step 4: Run tests, then the purity gates**

Run: `uv run pytest tests/unit/transform/ tests/test_import_contracts.py -v`
Expected: PASS — including the import-linter contract test now covering four real transform modules.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/transform/dispatch.py tests/unit/transform/test_dispatch.py
git commit -m "transform: file-class dispatch, canonical pipeline, EC-005 metric (adr-0016)"
```

---

### Task 6: Legacy encoding detection — charset-normalizer rung (FR-007, DR-001)

**Files:**
- Modify: `pyproject.toml` via `uv add "charset-normalizer>=3.4.2"`
- Create: `src/docmend/detection.py`
- Modify: `src/docmend/discovery.py` (`_process_candidate` + `scan` signature threading)
- Modify: `docs/dependency-licenses.md` (add charset-normalizer row — MIT)
- Test: `tests/test_detection.py`; extend `tests/test_discovery.py`

**Interfaces:**
- Consumes: `DetectedEncoding` model from `docmend.inventory`.
- Produces: `detect_legacy(path: Path) -> DetectedEncoding | None` — runs charset-normalizer over the file; returns `None` when the detector has **no** candidate (planning maps that to `binary-suspect`); otherwise `DetectedEncoding(name=<python codec name>, confidence=1.0 - chaos, method="charset-normalizer")`. Discovery calls it only when: no BOM, not strict-UTF-8-valid, no NUL bytes, and detection enabled.

- [ ] **Step 1: Add the dependency and license record**

Run: `uv add "charset-normalizer>=3.4.2"`
Then add a row to the runtime table in `docs/dependency-licenses.md` following its existing format: charset-normalizer, MIT, permissive — cleared. (Read the file first and match its exact column layout.)

- [ ] **Step 2: Verify the charset-normalizer 3.x API against current docs**

Before writing code, confirm via Context7 (`/jawah/charset_normalizer` or equivalent) or the installed package's docstrings: `from_path(path)` returns `CharsetMatches`; `.best()` returns `CharsetMatch | None`; `CharsetMatch.encoding` is the Python codec name (e.g. `cp1252`); `CharsetMatch.chaos` is a float in `[0, 1]` (the "mess" ratio — spec FR-007 defines confidence as `1.0 − chaos`; 3.x has **no** `.confidence`). If any of this differs, stop and re-check the spec's OQ-015 research note before proceeding.

- [ ] **Step 3: Write the failing tests**

```python
"""FR-007 legacy detection rung (adr-0009): charset-normalizer wrapper facts.

These tests pin detector BEHAVIOR docmend depends on, so a charset-normalizer
upgrade that changes verdicts fails visibly here rather than corrupting plans.
Real filesystem (tmp_path): from_path reads the file itself.
"""

from pathlib import Path

from docmend.detection import detect_legacy


def write(tmp_path: Path, name: str, data: bytes) -> Path:
    target = tmp_path / name
    target.write_bytes(data)
    return target


class TestDetectLegacy:
    def test_windows_1252__detected_with_usable_confidence(self, tmp_path: Path) -> None:
        text = "café naïve — déjà vu, señor. " * 20
        path = write(tmp_path, "legacy.txt", text.replace("—", "-").encode("cp1252"))
        result = detect_legacy(path)
        assert result is not None
        assert result.method == "charset-normalizer"
        # cp1252/latin-1 are alias-close; accept the family, not one exact name.
        assert result.name in ("cp1252", "latin_1", "iso8859_15", "cp1250", "cp1254")
        assert result.confidence >= 0.80

    def test_confidence_is_one_minus_chaos_bounds(self, tmp_path: Path) -> None:
        path = write(tmp_path, "x.txt", "øøø æææ ååå ".encode("cp1252") * 10)
        result = detect_legacy(path)
        assert result is not None
        assert 0.0 <= result.confidence <= 1.0

    def test_undetectable_bytes__returns_none(self, tmp_path: Path) -> None:
        # Dense non-textual byte soup with no NULs: the binary-suspect input class.
        data = bytes(range(0x80, 0x100)) * 8
        path = write(tmp_path, "blob.txt", data)
        result = detect_legacy(path)
        # Pin whichever verdict the installed detector gives; if it DOES return a
        # match here, its chaos must be high enough that the 0.80 gate skips it.
        assert result is None or result.confidence < 0.80
```

The third test is deliberately tolerant: `binary-suspect` (no candidate) and `low-confidence-encoding` are both safe skip outcomes for that input. During implementation, print the actual verdict once and tighten the assertion to the observed branch, leaving the tolerant form only if the detector is genuinely unstable across the corpus of similar inputs.

Extend `tests/test_discovery.py` (class `TestClassification`):

```python
    def test_legacy_detection__populates_inventory_at_scan(self, corpus: Path) -> None:
        """DR-001 legacy rung (MS-2): charset-normalizer fills encoding.detected."""
        inventory = run_scan(corpus)
        legacy = {f.path: f for f in inventory.files}["legacy.txt"]
        assert legacy.encoding.detected is not None
        assert legacy.encoding.detected.method == "charset-normalizer"

    def test_legacy_detection__skipped_for_bom_utf8_and_nul_files(self, corpus: Path) -> None:
        inventory = run_scan(corpus)
        by_path = {f.path: f for f in inventory.files}
        assert by_path["bom.txt"].encoding.detected is not None
        assert by_path["bom.txt"].encoding.detected.method == "bom"
        assert by_path["plain.txt"].encoding.detected is not None
        assert by_path["plain.txt"].encoding.detected.method == "utf8-strict"
        # NUL-bearing files never reach the legacy detector (design decision 8).
        assert by_path["nulls.txt"].encoding.detected is None

    def test_legacy_detection__disabled_by_config(self, corpus: Path) -> None:
        config = DocmendConfig().model_copy(deep=True)
        config.encoding.detect = False  # if strict models forbid mutation, build via model_copy(update=...)
        inventory = run_scan(corpus, config)
        legacy = {f.path: f for f in inventory.files}["legacy.txt"]
        assert legacy.encoding.detected is None
```

(Strict pydantic models may reject attribute assignment; construct the config with `DocmendConfig(encoding=EncodingConfig(detect=False))` instead — use whichever pattern `tests/test_config.py` already uses.)

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_detection.py tests/test_discovery.py -v`
Expected: new tests FAIL (`ModuleNotFoundError: docmend.detection` / `detected is None` assertions).

- [ ] **Step 5: Implement `src/docmend/detection.py`**

```python
"""Legacy-encoding detection — the charset-normalizer rung of FR-007 (adr-0009).

Architectural role: §8.2.3 requires the encoding-detection dependency to be
replaceable behind an interface; this module IS that interface. Everything
else in docmend sees only `detect_legacy` and the DetectedEncoding fact model.

Contract facts (OQ-015, adr-0009):
- charset-normalizer is the SOLE detector; 3.x exposes no `.confidence`, so
  confidence is computed as 1.0 - CharsetMatch.chaos.
- `None` means the detector produced no candidate at all — the planning layer
  maps that to the `binary-suspect` skip; it is NOT an error.
- Callers gate invocation (discovery only calls for no-BOM, non-UTF-8,
  NUL-free files with detection enabled); this module never decides policy.
"""

from pathlib import Path

from charset_normalizer import from_path

from docmend.inventory import DetectedEncoding


def detect_legacy(path: Path) -> DetectedEncoding | None:
    best = from_path(path).best()
    if best is None:
        return None
    confidence = min(1.0, max(0.0, 1.0 - best.chaos))
    return DetectedEncoding(name=best.encoding, confidence=confidence, method="charset-normalizer")
```

(If BasedPyright strict flags charset-normalizer's annotations as partially unknown, follow the `artifacts.py` precedent: a minimal `Protocol` + one `cast`, not a blanket ignore.)

- [ ] **Step 6: Integrate into discovery**

In `src/docmend/discovery.py`:
1. `scan(...)` already receives `config: DocmendConfig` — thread `config.encoding.detect` into `_process_candidate` as a keyword `detect: bool`.
2. In `_process_candidate`, after `record = classify_file(full, rel, stat)` succeeds:

```python
    if (
        detect
        and record.encoding.bom is None
        and not record.encoding.utf8_valid
        and not record.nul_bytes
    ):
        # FR-007 legacy rung (adr-0009 gate order): only a no-BOM, non-UTF-8,
        # NUL-free file ever reaches charset-normalizer; a detection failure
        # here is an ERR-007-style unreadable skip, same as classification.
        try:
            detected = detection.detect_legacy(full)
        except OSError as exc:
            state.skipped.append(SkipRecord(path=rel, reason="unreadable", detail=str(exc)))
            log.warning("file unreadable", path=rel, error=str(exc), err="ERR-007")
            return
        if detected is not None:
            record = record.model_copy(
                update={"encoding": record.encoding.model_copy(update={"detected": detected})}
            )
            log.debug("legacy encoding detected", path=rel, name=detected.name)
```

3. Import `from docmend import detection` at the top. Update both `_process_candidate` call sites (directory walk and single-file) to pass `detect=config.encoding.detect`.

- [ ] **Step 7: Run the full suite**

Run: `uv run coverage run -m pytest && uv run coverage report`
Expected: PASS; the pre-existing `legacy.txt` classification expectations in `test_discovery.py` may need their `detected is None` assumption updated — that assumption was the MS-1 placeholder this task removes; update those assertions, nothing else.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock src/docmend/detection.py src/docmend/discovery.py tests/test_detection.py tests/test_discovery.py docs/dependency-licenses.md
git commit -m "detection: charset-normalizer legacy rung populates inventory at scan (FR-007, DR-001, adr-0009)"
```

---

### Task 7: Plan artifact — schema amendment, pydantic models, artifact IO (DR-002, IR-007)

**Files:**
- Modify: `src/docmend/schemas/plan.schema.json` (add `changed-since-scan` to the skip-reason enum; extend the reason `description` with "plan-time change detection (AW-004 analog)")
- Create: `src/docmend/plan.py`
- Modify: `src/docmend/artifacts.py` (add `write_plan`, `read_plan`, `sha256_of_file`)
- Test: `tests/test_plan_artifact.py`; extend `tests/test_schemas.py` satisfiability fixtures if they enumerate skip reasons

**Interfaces:**
- Consumes: `Operation` from `docmend.transform.dispatch`; `RunId`/`Sha256`/`RelativePath`/`DetectedEncoding`/`NewlineStyle` patterns from `docmend.inventory` (reuse the type aliases; do not redefine).
- Produces (planning and CLI rely on these exact names):
  - `PLAN_SCHEMA_VERSION = "1.0"`
  - `type PlanSkipReason = Literal["binary-suspect", "nul-bytes", "utf16-suspect", "decode-replacement", "low-confidence-encoding", "below-non-ascii-floor", "collision", "hard-link-alias", "symlink", "oversize", "shrink-invariant", "excluded", "unreadable", "changed-since-scan"]`
  - Models: `ArtifactRef(path, run_id, sha256)`, `ActionProvenance(detected_encoding: DetectedEncoding | None, newline_style: NewlineStyle)`, `PlanAction(action_id, docmend_id, path, source_sha256, source_size_bytes, operations, target_path, provenance)`, `SkipDecision(path, reason, detail)`, `PlanTotals(actions, skips)`, `Plan(schema_kind alias "schema" = "docmend/plan", schema_version, run_id, generated_at, generated_by, inventory_ref, config, actions, skips, totals)`.
  - `Plan.config` is `dict[str, object]` (the §18.2 snapshot) validated structurally by the JSON Schema's `config_snapshot`, not re-modeled — the strict `DocmendConfig` already owns that shape; planning produces it via `config.model_dump(mode="json")`.
  - `artifacts.write_plan(plan: Plan, path: Path) -> None` and `artifacts.read_plan(path: Path) -> Plan` — mirror the inventory pair exactly (validate-against-schema before write; ERR-008-style `ArtifactError` on read).
  - `artifacts.sha256_of_file(path: Path) -> str` — `"sha256:<hex>"` of a file's bytes (chunked read), used for `inventory_ref.sha256` and planning's change check.

- [ ] **Step 1: Amend the schema.** In `plan.schema.json` `$defs.skip_decision.properties.reason.enum`, append `"changed-since-scan"`; extend the description's reason list with `, and plan-time change detection — the file's bytes no longer match the inventory record (AW-004 analog; FR-003 remains the apply-time guard)`. Commit note must record this as a pre-implementation amendment to the never-yet-produced v1.0 contract.

- [ ] **Step 2: Write the failing tests**

```python
"""DR-002 plan artifact: model<->schema conformance, round-trip, IDs (adr-0005, IR-007)."""

from pathlib import Path

import pytest

from docmend import artifacts
from docmend.plan import (
    PLAN_SCHEMA_VERSION,
    ActionProvenance,
    ArtifactRef,
    Plan,
    PlanAction,
    PlanTotals,
    SkipDecision,
)

RUN = "run_20260706T000000Z_abc123"


def sample_plan() -> Plan:
    return Plan(
        run_id=RUN,
        generated_at="2026-07-06T00:00:00+00:00",
        generated_by="docmend 0.1.0",
        inventory_ref=ArtifactRef(
            path=".docmend/docmend-run_20260706T000000Z_abc123-inventory.json",
            run_id=RUN,
            sha256="sha256:" + "0" * 64,
        ),
        config=__import__("docmend.config", fromlist=["DocmendConfig"]).DocmendConfig().model_dump(mode="json"),
        actions=[
            PlanAction(
                action_id=f"{RUN}/a1",
                docmend_id="019807c0-0000-7000-8000-000000000000",
                path="legacy.txt",
                source_sha256="sha256:" + "1" * 64,
                source_size_bytes=120,
                operations=["reencode", "normalize_newlines", "rename"],
                target_path="legacy.md",
                provenance=ActionProvenance(detected_encoding=None, newline_style="crlf"),
            )
        ],
        skips=[SkipDecision(path="blob.txt", reason="binary-suspect", detail=None)],
        totals=PlanTotals(actions=1, skips=1),
    )


class TestPlanModel:
    def test_dump_validates_against_checked_in_schema(self) -> None:
        artifacts.validate_artifact("plan", sample_plan().model_dump(mode="json"))

    def test_schema_key_serialized_by_alias(self) -> None:
        assert sample_plan().model_dump(mode="json")["schema"] == "docmend/plan"

    def test_action_id_pattern_enforced(self) -> None:
        with pytest.raises(Exception):
            PlanAction(
                action_id="not-an-action-id",
                docmend_id="019807c0-0000-7000-8000-000000000000",
                path="x.txt",
                source_sha256="sha256:" + "1" * 64,
                source_size_bytes=1,
                operations=["rename"],
                target_path="x.md",
                provenance=ActionProvenance(detected_encoding=None, newline_style="lf"),
            )

    def test_changed_since_scan_reason_accepted(self) -> None:
        decision = SkipDecision(path="x.txt", reason="changed-since-scan", detail="sha mismatch")
        plan = sample_plan().model_copy(update={"skips": [decision], "totals": PlanTotals(actions=1, skips=1)})
        artifacts.validate_artifact("plan", plan.model_dump(mode="json"))


class TestPlanArtifactIO:
    def test_round_trip_identical(self, tmp_path: Path) -> None:
        # IR-007: write -> read -> identical model.
        target = tmp_path / "plan.json"
        plan = sample_plan()
        artifacts.write_plan(plan, target)
        assert artifacts.read_plan(target) == plan

    def test_read_invalid_json_raises_artifact_error(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.json"
        target.write_text("{not json")
        with pytest.raises(artifacts.ArtifactError):
            artifacts.read_plan(target)

    def test_read_schema_violating_document_raises(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.json"
        target.write_text('{"schema": "docmend/plan"}')
        with pytest.raises(artifacts.ArtifactError):
            artifacts.read_plan(target)


class TestSha256OfFile:
    def test_matches_hashlib(self, tmp_path: Path) -> None:
        import hashlib

        target = tmp_path / "f.bin"
        target.write_bytes(b"abc")
        assert artifacts.sha256_of_file(target) == "sha256:" + hashlib.sha256(b"abc").hexdigest()
```

(Clean up the ugly `__import__` in `sample_plan` — use a normal top-level `from docmend.config import DocmendConfig` import; it is written inline above only to keep the snippet self-contained.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_plan_artifact.py -v`
Expected: FAIL — `ModuleNotFoundError: docmend.plan`

- [ ] **Step 4: Implement `src/docmend/plan.py`** — follow `inventory.py`'s structure and docstring conventions exactly (strict `_StrictModel` base, `schema_kind` alias trick, patterns as `Annotated` aliases). Key extract:

```python
"""Plan data model — the DR-002 artifact as strict internal models (OQ-021).

Cross-file contract (adr-0005): src/docmend/schemas/plan.schema.json is the
durable external contract; these models CONFORM to it. The Operation
vocabulary is imported from docmend.transform.dispatch (single-sourced), and
identity/hash type aliases are shared with docmend.inventory. Serialization
goes through docmend.artifacts, which validates before disk.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from docmend.inventory import DetectedEncoding, NewlineStyle, RelativePath, RunId, Sha256
from docmend.transform.dispatch import Operation

PLAN_SCHEMA_VERSION = "1.0"

type ActionId = Annotated[str, Field(pattern=r"^run_\d{8}T\d{6}Z_[0-9a-f]{6}/a\d+$")]
type DocmendId = Annotated[
    str,
    Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
]
type PlanSkipReason = Literal[
    "binary-suspect",
    "nul-bytes",
    "utf16-suspect",
    "decode-replacement",
    "low-confidence-encoding",
    "below-non-ascii-floor",
    "collision",
    "hard-link-alias",
    "symlink",
    "oversize",
    "shrink-invariant",
    "excluded",
    "unreadable",
    "changed-since-scan",
]
```

then `_StrictModel`, `ArtifactRef`, `ActionProvenance`, `PlanAction` (`operations: Annotated[list[Operation], Field(min_length=1)]`, `target_path: RelativePath | None`), `SkipDecision`, `PlanTotals`, and `Plan` with `config: dict[str, object]` and the same `model_config`/alias arrangement as `Inventory`.

- [ ] **Step 5: Extend `src/docmend/artifacts.py`** — `write_plan`/`read_plan` are line-for-line parallels of `write_inventory`/`read_inventory` (import `Plan`, validate kind `"plan"`); add:

```python
def sha256_of_file(path: Path) -> str:
    """Hash an artifact file for cross-artifact references (adr-0005 identity fields)."""
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"
```

(`import hashlib` at top.) If the duplication between the inventory and plan read/write pairs itches, a shared private helper parameterized on `(kind, model_type)` is acceptable — but only if it keeps BasedPyright strict clean without casts; otherwise keep the explicit pair.

- [ ] **Step 6: Check `tests/test_schemas.py`** — if its satisfiability/cross-check fixtures enumerate the plan skip-reason enum, add `changed-since-scan`; the pydantic↔schema cross-check for plan models now becomes ACTIVE (the plan model exists) — wire `Plan` into whatever cross-check pattern `Inventory` uses there.

- [ ] **Step 7: Run the full suite**

Run: `uv run coverage run -m pytest && uv run coverage report`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/docmend/schemas/plan.schema.json src/docmend/plan.py src/docmend/artifacts.py tests/test_plan_artifact.py tests/test_schemas.py
git commit -m "plan: DR-002 models + artifact IO; add changed-since-scan skip reason (pre-implementation v1.0 amendment)"
```

---

### Task 8: Planning engine, part 1 — fact-level decisions (FR-002, FR-015 gates)

The engine is split in two tasks along a clean seam: part 1 decides everything derivable from the inventory + config alone (no file reads); part 2 adds the content pass. Part 1 ships a working `build_plan` that actions nothing yet — every candidate either skips on facts or lands in a `pending` list that part 2 consumes.

**Files:**
- Create: `src/docmend/planning.py`
- Test: `tests/test_planning.py`

**Interfaces:**
- Consumes: `Inventory`/`FileRecord` (Task 6-populated detection), `DocmendConfig`, plan models (Task 7), `pathspec` (same `GitIgnoreSpecPattern` usage as discovery).
- Produces:
  - `build_plan(inventory: Inventory, config: DocmendConfig, *, run_id: str, generated_at: str, inventory_ref: ArtifactRef, mint_id: Callable[[], uuid.UUID] = uuid.uuid7) -> Plan`
  - `class PlanningAbort(Exception)` — raised for `rename.on_collision == "fail"` semantics? **No** — collisions are recorded as skips and the CLI derives the exit code from the plan (design decision 5); no abort exception exists. The CLI needs only `build_plan`.
  - Internal but tested: `_fact_skip(record, groups, config) -> SkipDecision | None` implementing the gate ladder below.

**Gate ladder (fixed order, first hit wins) — part 1:**
1. Plan-time include/exclude (FR-012 consistency): not matching effective `paths.include` → skip `excluded` (detail `"not matched by plan-time include patterns"`); matching `paths.exclude` → skip `excluded`.
2. Hard-link group member (`path` in any `inventory.hard_link_groups[*].paths`) → skip `hard-link-alias`, detail `f"inode {group.inode}: {', '.join(group.paths)}"` (EC-011).
3. Oversize: `size_bytes > config.limits.max_file_size_mib * 1024 * 1024` → skip `oversize` (FR-019 plan-time half).
4. Encoding resolution (adr-0009 order) for files with `bom is None and not utf8_valid`:
   - `nul_bytes` → part 2 decides `utf16-suspect` vs `nul-bytes` (needs bytes) — record as pending-with-nul marker; **part 1 skips them as `nul-bytes`** with detail `"NUL bytes present"` and a code comment that part 2 refines the utf16-suspect split.
   - `not config.encoding.detect` → skip `low-confidence-encoding`, detail `"encoding detection disabled"`.
   - `encoding.detected is None` → skip `binary-suspect`, detail `"no encoding candidate"`.
   - `encoding.detected.confidence < config.encoding.fail_below_confidence` → skip `low-confidence-encoding`, detail `f"confidence {c:.2f} < {threshold}"`.
   - `non_ascii_bytes < config.encoding.non_ascii_floor` → skip `below-non-ascii-floor`, detail `f"{n} non-ASCII bytes < floor {floor}"`.
5. Survivors → pending (part 2).

Also: every `inventory.symlinks` record → skip `symlink` (EC-008); part 1 leaves pending files with **no action** (empty `actions`) and correct totals.

- [ ] **Step 1: Write the failing tests** (representative core; keep all in one class-per-concern layout):

```python
"""Planning-layer decisions (FR-002, FR-015, DR-002; EC-008/EC-011; adr-0009 gates).

Fact-level tests build inventories via discovery.scan over recipe corpora
(tests/corpus.py) so planning is exercised against real scan output.
"""

import uuid
from pathlib import Path

from docmend.artifacts import sha256_of_file
from docmend.config import DocmendConfig, EncodingConfig, LimitsConfig
from docmend.discovery import scan
from docmend.plan import ArtifactRef, Plan
from docmend.planning import build_plan
from tests.corpus import GENERATED_AT, RUN_ID, FileRecipe, materialize, seeded_faker

INV_REF = ArtifactRef(path="inventory.json", run_id=RUN_ID, sha256="sha256:" + "0" * 64)


def fixed_ids() -> "Callable[[], uuid.UUID]":
    # Deterministic stand-in for uuid.uuid7 (no version= param: the UUID
    # constructor's version check predates RFC 9562 versions on some releases,
    # and nothing asserts version bits — only uniqueness and shape).
    counter = iter(range(1, 10_000))
    return lambda: uuid.UUID(int=(0x0198_0000 << 96) | next(counter))


def plan_over(root: Path, config: DocmendConfig | None = None) -> Plan:
    config = config or DocmendConfig()
    inventory = scan(root, config, run_id=RUN_ID, generated_at=GENERATED_AT)
    return build_plan(
        inventory, config, run_id=RUN_ID, generated_at=GENERATED_AT,
        inventory_ref=INV_REF, mint_id=fixed_ids(),
    )


class TestFactGates:
    def test_oversize_file__skipped_with_reason(self, tmp_path: Path) -> None:
        """FR-019 plan-time size guard: oversize skipped at plan with reason."""
        (tmp_path / "big.txt").write_bytes(b"a" * (2 * 1024 * 1024))
        config = DocmendConfig(limits=LimitsConfig(max_file_size_mib=1))
        plan = plan_over(tmp_path, config)
        assert [s.reason for s in plan.skips if s.path == "big.txt"] == ["oversize"]

    def test_hard_link_group__every_member_skipped(self, tmp_path: Path) -> None:
        """EC-011: shared-inode alias groups are never planned for mutation."""
        original = tmp_path / "a.txt"
        original.write_text("x\n")
        (tmp_path / "b.txt").hardlink_to(original)
        plan = plan_over(tmp_path)
        reasons = {s.path: s.reason for s in plan.skips}
        assert reasons["a.txt"] == "hard-link-alias"
        assert reasons["b.txt"] == "hard-link-alias"

    def test_symlink__skipped_with_reason(self, tmp_path: Path) -> None:
        """EC-008: symlinks recorded, never planned for mutation."""
        (tmp_path / "real.txt").write_text("x\n")
        (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")
        plan = plan_over(tmp_path)
        assert {s.path: s.reason for s in plan.skips}["link.txt"] == "symlink"

    def test_nul_bytes__skipped(self, tmp_path: Path) -> None:
        """EC-004 / FR-015: NUL-bearing files are risky, skipped with reason."""
        materialize(tmp_path, [FileRecipe("nulls.txt", "binaryish", "lf")], seeded_faker())
        plan = plan_over(tmp_path)
        assert {s.path: s.reason for s in plan.skips}["nulls.txt"] in ("nul-bytes", "utf16-suspect")

    def test_detection_disabled__legacy_file_skipped(self, tmp_path: Path) -> None:
        materialize(tmp_path, [FileRecipe("legacy.txt", "windows-1252", "lf")], seeded_faker())
        config = DocmendConfig(encoding=EncodingConfig(detect=False))
        plan = plan_over(tmp_path, config)
        skip = {s.path: s for s in plan.skips}["legacy.txt"]
        assert skip.reason == "low-confidence-encoding"
        assert skip.detail == "encoding detection disabled"

    def test_low_confidence__skipped_with_thresholds_in_detail(self, tmp_path: Path) -> None:
        """FR-007 gate 1: confidence below threshold -> skip (provenance C.4)."""
        materialize(tmp_path, [FileRecipe("legacy.txt", "windows-1252", "lf")], seeded_faker())
        config = DocmendConfig(encoding=EncodingConfig(fail_below_confidence=1.0))
        plan = plan_over(tmp_path, config)
        assert {s.path: s.reason for s in plan.skips}["legacy.txt"] == "low-confidence-encoding"

    def test_below_floor__skipped(self, tmp_path: Path) -> None:
        """FR-007 gate 2 (adr-0009): too few non-ASCII bytes to trust a legacy guess."""
        (tmp_path / "short.txt").write_bytes(b"mostly ascii text here.... \xe9\xe8")
        plan = plan_over(tmp_path)  # floor default 20; file has 2 non-ASCII bytes
        assert {s.path: s.reason for s in plan.skips}["short.txt"] == "below-non-ascii-floor"
        # If the detector returns NO candidate for these bytes (binary-suspect
        # fires first in the ladder), adjust the ASCII prose until it detects
        # confidently — mirror Task 11's 3-consecutive-runs stability rule.

    def test_plan_time_filters__consistent_with_scan(self, tmp_path: Path) -> None:
        """FR-012: plan applies effective include/exclude over inventory records."""
        materialize(tmp_path, [FileRecipe("keep.txt", "utf-8", "lf"), FileRecipe("drop.txt", "utf-8", "lf")], seeded_faker())
        inventory = scan(tmp_path, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)
        narrowed = DocmendConfig().model_copy(deep=True)
        from docmend.config import PathsConfig
        narrowed = DocmendConfig(paths=PathsConfig(include=["keep.txt"], exclude=[]))
        plan = build_plan(inventory, narrowed, run_id=RUN_ID, generated_at=GENERATED_AT, inventory_ref=INV_REF, mint_id=fixed_ids())
        assert {s.path: s.reason for s in plan.skips}["drop.txt"] == "excluded"
        assert all(a.path != "drop.txt" for a in plan.actions)


class TestPlanShape:
    def test_totals_reconcile(self, tmp_path: Path) -> None:
        """DR-002: totals equal the record-list lengths."""
        materialize(tmp_path, [FileRecipe("a.txt", "utf-8", "crlf")], seeded_faker())
        plan = plan_over(tmp_path)
        assert plan.totals.actions == len(plan.actions)
        assert plan.totals.skips == len(plan.skips)

    def test_plan_validates_against_schema(self, tmp_path: Path) -> None:
        from docmend.artifacts import validate_artifact

        materialize(tmp_path, [FileRecipe("a.txt", "utf-8", "crlf")], seeded_faker())
        validate_artifact("plan", plan_over(tmp_path).model_dump(mode="json"))
```

(Fix the duplicate `narrowed` assignment when transcribing — keep only the `DocmendConfig(paths=PathsConfig(...))` construction, imported at top.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_planning.py -v`
Expected: FAIL — `ModuleNotFoundError: docmend.planning`

- [ ] **Step 3: Implement part 1 of `src/docmend/planning.py`**

```python
"""Planning layer — per-file decisions, risk classification, plan assembly (FR-002, FR-015, DR-002).

Architectural role (§8.2.3): consumes the DR-001 inventory + effective config,
emits the DR-002 plan. ALL danger detection happens here, before any write
(§8.1). Planning reads library files READ-ONLY (part 2's content pass) and
writes nothing itself — artifact IO lives in docmend.artifacts, invoked by the
CLI.

Decision record (spec C.4): every skip carries a classified reason + detail;
every action carries the facts it was decided on (source hash, detection,
newline style) so the plan is reviewable without re-running anything.

Gate order is fixed (adr-0009 + FR-015): filters -> hard-link -> oversize ->
encoding gates -> content checks (part 2). First hit wins; a file gets exactly
one skip decision or one action or (no-op) neither — FR-017's plan half.
"""

import uuid
from collections.abc import Callable
from pathlib import Path

from pathspec import PathSpec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from docmend import __version__
from docmend.config import DocmendConfig
from docmend.inventory import FileRecord, Inventory
from docmend.observability import get_logger
from docmend.plan import (
    PLAN_SCHEMA_VERSION,
    ActionProvenance,
    ArtifactRef,
    Plan,
    PlanAction,
    PlanTotals,
    SkipDecision,
)


def _fact_skip(
    record: FileRecord,
    hard_linked: dict[str, str],
    config: DocmendConfig,
    include: PathSpec[GitIgnoreSpecPattern],
    exclude: PathSpec[GitIgnoreSpecPattern],
) -> SkipDecision | None:
    path = record.path
    if not include.match_file(path):
        return SkipDecision(path=path, reason="excluded", detail="not matched by plan-time include patterns")
    if exclude.match_file(path):
        return SkipDecision(path=path, reason="excluded", detail=None)
    if path in hard_linked:
        return SkipDecision(path=path, reason="hard-link-alias", detail=hard_linked[path])
    if record.size_bytes > config.limits.max_file_size_mib * 1024 * 1024:
        return SkipDecision(
            path=path,
            reason="oversize",
            detail=f"{record.size_bytes} bytes > limits.max_file_size_mib {config.limits.max_file_size_mib}",
        )
    enc = record.encoding
    if enc.bom is None and not enc.utf8_valid:
        if record.nul_bytes:
            # Part 2 refines this into the utf16-suspect split from bytes;
            # facts alone cannot distinguish interleaved-NUL from scattered.
            return SkipDecision(path=path, reason="nul-bytes", detail="NUL bytes present")
        if not config.encoding.detect:
            return SkipDecision(path=path, reason="low-confidence-encoding", detail="encoding detection disabled")
        if enc.detected is None:
            return SkipDecision(path=path, reason="binary-suspect", detail="no encoding candidate")
        threshold = config.encoding.fail_below_confidence
        if enc.detected.confidence < threshold:
            return SkipDecision(
                path=path,
                reason="low-confidence-encoding",
                detail=f"confidence {enc.detected.confidence:.2f} < {threshold}",
            )
        floor = config.encoding.non_ascii_floor
        if record.non_ascii_bytes < floor:
            return SkipDecision(
                path=path,
                reason="below-non-ascii-floor",
                detail=f"{record.non_ascii_bytes} non-ASCII bytes < floor {floor}",
            )
    return None


def build_plan(
    inventory: Inventory,
    config: DocmendConfig,
    *,
    run_id: str,
    generated_at: str,
    inventory_ref: ArtifactRef,
    mint_id: Callable[[], uuid.UUID] = uuid.uuid7,
) -> Plan:
    log = get_logger(__name__)
    include = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.include)
    exclude = PathSpec.from_lines(GitIgnoreSpecPattern, config.paths.exclude)
    hard_linked = {
        path: f"inode {group.inode}: {', '.join(group.paths)}"
        for group in inventory.hard_link_groups
        for path in group.paths
    }

    actions: list[PlanAction] = []
    skips: list[SkipDecision] = [
        SkipDecision(path=link.path, reason="symlink", detail=f"-> {link.target}")
        for link in inventory.symlinks
    ]
    pending: list[FileRecord] = []
    for record in inventory.files:
        decision = _fact_skip(record, hard_linked, config, include, exclude)
        if decision is not None:
            skips.append(decision)
            log.debug("planned skip", path=record.path, reason=decision.reason)
        else:
            pending.append(record)

    # Part 2 (content pass) turns `pending` into actions/no-ops; until then a
    # pending file is deliberately absent from both lists (FR-017 plan half).
    del pending  # replaced by the content pass in the next task

    skips.sort(key=lambda s: s.path)
    return Plan(
        run_id=run_id,
        generated_at=generated_at,
        generated_by=f"docmend {__version__}",
        inventory_ref=inventory_ref,
        config=config.model_dump(mode="json"),
        actions=actions,
        skips=skips,
        totals=PlanTotals(actions=len(actions), skips=len(skips)),
        schema_version=PLAN_SCHEMA_VERSION,
    )
```

- [ ] **Step 4: Run tests** — the fact-gate and shape tests PASS; any test asserting actions exist (there are none yet in this task) stays for part 2.

Run: `uv run pytest tests/test_planning.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/planning.py tests/test_planning.py
git commit -m "planning: fact-level gate ladder - filters, hard links, oversize, encoding gates (FR-002/FR-015 part 1)"
```

---

### Task 9: Planning engine, part 2 — content pass: decode, transform prediction, collisions, actions

**Files:**
- Modify: `src/docmend/planning.py`
- Test: extend `tests/test_planning.py`

**Interfaces:**
- Consumes: Task 4/5 transform functions; `sha256_of_file` pattern (hash-while-reading inline here); Task 8's `pending` seam.
- Produces: the completed `build_plan` — `pending` files become actions, no-ops, or content-derived skips. New internal function `_content_decision(record, source_root, config, claimed_targets) -> PlanAction-parts | SkipDecision | None` (exact shape below). `build_plan` gains a `source_root: Path` derived from `inventory.source_root`.

**Content pass per pending file (fixed order):**
1. Read all bytes (one read; files here are ≤ `max_file_size_mib`, bounded per-file memory per NFR-001), hashing as read. `OSError` → skip `unreadable` (ERR-005 analog). Hash ≠ `record.sha256` → skip `changed-since-scan` (detail: both hashes).
2. NUL refinement: if `record.nul_bytes` and no BOM — `_utf16_suspect(data)` → skip `utf16-suspect` (EC-010, detail `"BOM-less interleaved-NUL pattern"`), else skip `nul-bytes`. (Part 1 currently skips these before content; MOVE that branch here so the split is byte-accurate — part 1's `nul-bytes` fact-skip is replaced by routing NUL files into pending.)
3. Determine decode parameters: BOM → BOM codec; `utf8_valid` → `utf-8`; else `record.encoding.detected.name`. Strict `decode_source`; `UnicodeDecodeError` → skip `decode-replacement` (EC-003, detail names the encoding and error offset).
4. `apply_text_transforms(text, classify_suffix(record.suffix), trim_trailing_ws=config.whitespace.trim_trailing, final_newline=config.whitespace.ensure_final_newline, collapse_max=config.whitespace.collapse_blank_lines, tab_width=config.whitespace.tab_width if config.whitespace.normalize_tabs else None)`.
5. `reencode` operation prepended iff `record.encoding.bom is not None or decode_encoding != "utf-8"` (BOM strip or legacy decode — both rewrite bytes even when text ops are no-ops).
6. EC-005 invariant (belt-and-braces over the dispatch property): `non_whitespace_count(transformed) < non_whitespace_count(text)` → skip `shrink-invariant`. (Unreachable with correct transforms; a hit means a transform bug — log at error level too.)
7. Rename: `file_class == "text"` and suffix lowercase `.txt` and `config.rename.txt_to_md` → `target_path = path with .md suffix`; collision iff target exists on disk under `source_root`, or is an inventory file path, or already claimed by an earlier action this run. On collision: policy `skip`/`fail` → skip `collision` (detail records the existing target and policy; the CLI maps `fail` to exit 1), policy `overwrite` → keep the rename. No rename and no operations → **no entry** (idempotent no-op). Rename appends `"rename"` as the final operation.
8. Assemble `PlanAction`: `action_id = f"{run_id}/a{next_seq}"` (sequence over emitted actions, starting 1, in path order), `docmend_id = str(mint_id())`, `source_sha256 = record.sha256`, provenance from the inventory facts.

- [ ] **Step 1: Write the failing tests** (extend `tests/test_planning.py`):

```python
class TestContentPass:
    def test_crlf_legacy_txt__full_action_with_provenance(self, tmp_path: Path) -> None:
        """FR-002/C.4: action carries operations, hashes, and decision provenance."""
        materialize(tmp_path, [FileRecipe("legacy.txt", "windows-1252", "crlf")], seeded_faker())
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["legacy.txt"]
        assert action.operations[0] == "reencode"
        assert "normalize_newlines" in action.operations
        assert action.operations[-1] == "rename"
        assert action.target_path == "legacy.md"
        assert action.source_sha256.startswith("sha256:")
        assert action.provenance.newline_style == "crlf"
        assert action.provenance.detected_encoding is not None
        assert action.provenance.detected_encoding.method == "charset-normalizer"

    def test_utf8_bom__reencode_planned(self, tmp_path: Path) -> None:
        """EC-007: BOM strip is a byte rewrite -> reencode even if text is clean."""
        (tmp_path / "bom.txt").write_bytes(b"\xef\xbb\xbfclean\n")
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["bom.txt"]
        assert "reencode" in action.operations

    def test_already_clean_file__neither_action_nor_skip(self, tmp_path: Path) -> None:
        """FR-017 plan half: no-op files appear in neither list."""
        (tmp_path / "clean.md").write_bytes(b"already clean\n")
        plan = plan_over(tmp_path)
        assert all(a.path != "clean.md" for a in plan.actions)
        assert all(s.path != "clean.md" for s in plan.skips)

    def test_rename_only__still_an_action(self, tmp_path: Path) -> None:
        """FR-010: rename is a typed operation distinct from content transforms."""
        (tmp_path / "clean.txt").write_bytes(b"already clean\n")
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["clean.txt"]
        assert action.operations == ["rename"]
        assert action.target_path == "clean.md"

    def test_markup_file__never_renamed_never_whitespace(self, tmp_path: Path) -> None:
        """adr-0016: HTML gets encoding/EOL only."""
        (tmp_path / "page.html").write_bytes(b"<p>x  </p>\r\n\r\n\r\n\r\n\r\n<p>y</p>")
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["page.html"]
        assert action.operations == ["normalize_newlines"]
        assert action.target_path is None

    def test_decode_replacement__skipped(self, tmp_path: Path) -> None:
        """EC-003: a file that only decodes with replacement chars is skipped."""
        # Needs >=20 non-ASCII bytes to pass the floor, detected as cp1252-family,
        # but containing 0x81 (undefined in cp1252) so strict decode fails.
        data = ("caf\xe9 na\xefve d\xe9j\xe0 vu se\xf1or " * 3).encode("latin-1") + b"\x81"
        (tmp_path / "broken.txt").write_bytes(data)
        plan = plan_over(tmp_path)
        skip = {s.path: s for s in plan.skips}.get("broken.txt")
        action = {a.path: a for a in plan.actions}.get("broken.txt")
        # Detector may name an encoding that CAN decode 0x81 (latin-1 decodes
        # everything); accept either a decode-replacement skip or a clean plan,
        # then pin the observed branch (see note below).
        assert skip is not None or action is not None

    def test_utf16_suspect__bomless_interleaved_nul(self, tmp_path: Path) -> None:
        """EC-010: BOM-less UTF-16 pattern gets the specific reason, never generic binary."""
        (tmp_path / "suspect.txt").write_bytes("plain ascii text here".encode("utf-16-le"))
        plan = plan_over(tmp_path)
        assert {s.path: s.reason for s in plan.skips}["suspect.txt"] == "utf16-suspect"

    def test_scattered_nuls__plain_nul_bytes_reason(self, tmp_path: Path) -> None:
        """EC-004: scattered NULs are nul-bytes, not utf16-suspect."""
        (tmp_path / "nully.txt").write_bytes(b"abc\x00defghijklmnop\x00qrs")
        plan = plan_over(tmp_path)
        assert {s.path: s.reason for s in plan.skips}["nully.txt"] == "nul-bytes"

    def test_changed_since_scan__skipped(self, tmp_path: Path) -> None:
        """AW-004 analog at plan time: stale facts are never decided on."""
        (tmp_path / "moving.txt").write_bytes(b"version one\r\n")
        inventory = scan(tmp_path, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)
        (tmp_path / "moving.txt").write_bytes(b"version two\r\n")
        plan = build_plan(inventory, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT, inventory_ref=INV_REF, mint_id=fixed_ids())
        assert {s.path: s.reason for s in plan.skips}["moving.txt"] == "changed-since-scan"

    def test_vanished_file__unreadable_skip(self, tmp_path: Path) -> None:
        """ERR-005 analog: deleted between scan and plan -> skip, batch continues."""
        (tmp_path / "gone.txt").write_bytes(b"here now\r\n")
        (tmp_path / "stays.txt").write_bytes(b"stays\r\n")
        inventory = scan(tmp_path, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT)
        (tmp_path / "gone.txt").unlink()
        plan = build_plan(inventory, DocmendConfig(), run_id=RUN_ID, generated_at=GENERATED_AT, inventory_ref=INV_REF, mint_id=fixed_ids())
        assert {s.path: s.reason for s in plan.skips}["gone.txt"] == "unreadable"
        assert any(a.path == "stays.txt" for a in plan.actions)

    def test_zero_byte__handled_mechanically(self, tmp_path: Path) -> None:
        """EC-009: rename + final-newline enforcement; never the shrink heuristic."""
        (tmp_path / "empty.txt").write_bytes(b"")
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["empty.txt"]
        assert action.operations == ["ensure_final_newline", "rename"]

    def test_padded_legacy_file__shrinks_without_tripping_invariant(self, tmp_path: Path) -> None:
        """adr-0016 confirmation: whitespace-only shrinkage is legitimate."""
        (tmp_path / "padded.txt").write_bytes(b"a\n" + b"\n" * 500 + b"b\n")
        plan = plan_over(tmp_path)
        action = {a.path: a for a in plan.actions}["padded.txt"]
        assert "collapse_blank_lines" in action.operations
        assert all(s.path != "padded.txt" for s in plan.skips)


class TestCollisions:
    def _corpus(self, tmp_path: Path) -> None:
        (tmp_path / "foo.txt").write_bytes(b"txt body\r\n")
        (tmp_path / "foo.md").write_bytes(b"md body\n")

    def test_policy_skip__collision_skip_recorded(self, tmp_path: Path) -> None:
        """FR-011/EC-001 default: skip-with-reason."""
        self._corpus(tmp_path)
        plan = plan_over(tmp_path)
        skip = {s.path: s for s in plan.skips}["foo.txt"]
        assert skip.reason == "collision"
        assert "foo.md" in (skip.detail or "")

    def test_policy_overwrite__action_planned(self, tmp_path: Path) -> None:
        self._corpus(tmp_path)
        from docmend.config import RenameConfig

        plan = plan_over(tmp_path, DocmendConfig(rename=RenameConfig(on_collision="overwrite")))
        action = {a.path: a for a in plan.actions}["foo.txt"]
        assert action.target_path == "foo.md"

    def test_two_sources_one_target__second_collides(self, tmp_path: Path) -> None:
        # Case-variant sources can share a target on case-insensitive mappings;
        # simulate via claimed-target bookkeeping: plan order is path-sorted.
        (tmp_path / "bar.txt").write_bytes(b"one\r\n")
        sub = tmp_path / "sub"
        # Same-directory duplicate targets are impossible for pure extension
        # rename; assert the disk-existence branch instead when this proves
        # unconstructible — see implementation note.

    def test_action_ids_sequential_and_run_scoped(self, tmp_path: Path) -> None:
        """DR-002: per-action ID correlated with the run-ID."""
        (tmp_path / "a.txt").write_bytes(b"x\r\n")
        (tmp_path / "b.txt").write_bytes(b"y\r\n")
        plan = plan_over(tmp_path)
        assert [a.action_id for a in plan.actions] == [f"{RUN_ID}/a1", f"{RUN_ID}/a2"]

    def test_docmend_ids_unique(self, tmp_path: Path) -> None:
        """adr-0008: every planned document gets a distinct UUIDv7 identity."""
        (tmp_path / "a.txt").write_bytes(b"x\r\n")
        (tmp_path / "b.txt").write_bytes(b"y\r\n")
        plan = plan_over(tmp_path)
        ids = [a.docmend_id for a in plan.actions]
        assert len(set(ids)) == len(ids)
```

Notes for the implementer:
- `test_decode_replacement__skipped` is honest about detector variance: after first run, **pin the observed branch** (if charset-normalizer names a decode-everything codec like latin-1 for that input, redesign the fixture: detected multibyte encodings such as cp932 raise on truncated sequences — e.g. detected-as-cp932 bytes ending in a lone lead byte `\x81`). The committed weird-corpus fixture (Task 10) must be a **deterministic** decode-replacement case; iterate there and mirror the final bytes here.
- Delete the unfinished `test_two_sources_one_target__second_collides` stub if the claimed-targets branch proves unconstructible with pure extension renames — the disk- and inventory-existence branches are the reachable ones; keep the claimed-target set in code as cheap defense-in-depth with a comment saying why no test constructs it.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `uv run pytest tests/test_planning.py -v`
Expected: new tests FAIL (no actions produced yet); Task 8 tests still PASS (except `test_nul_bytes__skipped` semantics now refined — see step 3 change moving NUL handling to content pass; keep it green since both reasons were accepted).

- [ ] **Step 3: Implement the content pass** in `src/docmend/planning.py`:

```python
from docmend.transform.dispatch import (
    Operation,
    apply_text_transforms,
    classify_suffix,
    non_whitespace_count,
)
from docmend.transform.encoding import decode_source

import hashlib


def _utf16_suspect(data: bytes) -> bool:
    """BOM-less interleaved-NUL pattern (EC-010, OQ-026).

    UTF-16 text over an ASCII-heavy corpus puts ~50% NULs on one byte parity;
    thresholds (>=25% NUL density, >=90% single-parity concentration) are
    internal heuristics, deliberately not configurable — the outcome either
    way is a skip, only the recorded reason differs.
    """
    if len(data) < 4:
        return False
    nuls = data.count(0)
    if not nuls or nuls / len(data) < 0.25:
        return False
    even = data[::2].count(0)
    return max(even, nuls - even) / nuls >= 0.90


def _read_verified(full: Path, record: FileRecord) -> bytes | SkipDecision:
    try:
        data = full.read_bytes()
    except OSError as exc:
        return SkipDecision(path=record.path, reason="unreadable", detail=str(exc))
    digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
    if digest != record.sha256:
        return SkipDecision(
            path=record.path,
            reason="changed-since-scan",
            detail=f"inventory {record.sha256}, now {digest}",
        )
    return data
```

Then the per-file decision (replaces part 1's `del pending`; part 1's `nul-bytes` fact-skip branch is **removed** — NUL files flow into pending, minus the detection gates, which NUL files must bypass):

```python
    claimed_targets: set[str] = set()
    inventory_paths = {f.path for f in inventory.files}
    source_root = Path(inventory.source_root)
    seq = 0
    for record in pending:
        result = _read_verified(source_root / record.path, record)
        if isinstance(result, SkipDecision):
            skips.append(result)
            continue
        data = result
        enc = record.encoding
        if record.nul_bytes and enc.bom is None:
            reason = "utf16-suspect" if _utf16_suspect(data) else "nul-bytes"
            detail = "BOM-less interleaved-NUL pattern" if reason == "utf16-suspect" else "NUL bytes present"
            skips.append(SkipDecision(path=record.path, reason=reason, detail=detail))
            continue
        decode_encoding = enc.detected.name if enc.detected else "utf-8"
        try:
            text = decode_source(data, bom=enc.bom, encoding_name=decode_encoding)
        except UnicodeDecodeError as exc:
            skips.append(
                SkipDecision(
                    path=record.path,
                    reason="decode-replacement",
                    detail=f"{decode_encoding}: undecodable byte at offset {exc.start}",
                )
            )
            continue
        file_class = classify_suffix(record.suffix)
        ws = config.whitespace
        transformed, operations = apply_text_transforms(
            text,
            file_class,
            trim_trailing_ws=ws.trim_trailing,
            final_newline=ws.ensure_final_newline,
            collapse_max=ws.collapse_blank_lines,
            tab_width=ws.tab_width if ws.normalize_tabs else None,
        )
        ops: list[Operation] = []
        if enc.bom is not None or decode_encoding != "utf-8":
            ops.append("reencode")
        ops.extend(operations)
        if non_whitespace_count(transformed) < non_whitespace_count(text):
            log.error("shrink invariant tripped", path=record.path)
            skips.append(
                SkipDecision(path=record.path, reason="shrink-invariant", detail="non-whitespace count would decrease")
            )
            continue
        target: str | None = None
        if file_class == "text" and record.suffix.lower() == ".txt" and config.rename.txt_to_md:
            candidate = record.path[: -len(record.suffix)] + ".md"
            collides = (
                candidate in claimed_targets
                or candidate in inventory_paths
                or (source_root / candidate).exists()
            )
            if collides and config.rename.on_collision != "overwrite":
                skips.append(
                    SkipDecision(
                        path=record.path,
                        reason="collision",
                        detail=f"target {candidate} exists (policy {config.rename.on_collision})",
                    )
                )
                continue
            target = candidate
            ops.append("rename")
        if not ops:
            continue  # no-op: neither action nor skip (FR-017 plan half)
        if target is not None:
            claimed_targets.add(target)
        seq += 1
        actions.append(
            PlanAction(
                action_id=f"{run_id}/a{seq}",
                docmend_id=str(mint_id()),
                path=record.path,
                source_sha256=record.sha256,
                source_size_bytes=record.size_bytes,
                operations=ops,
                target_path=target,
                provenance=ActionProvenance(
                    detected_encoding=enc.detected, newline_style=record.newline_style
                ),
            )
        )
        log.debug("planned action", path=record.path, operations=ops, target=target)
```

Detail to respect: in `_fact_skip`, the encoding-gate block must now be entered only when `not record.nul_bytes` (NUL files bypass detection gates and reach the content pass). Update the Task 8 test `test_nul_bytes__skipped` accordingly — it already accepts both reasons.

- [ ] **Step 4: Run the full suite**

Run: `uv run coverage run -m pytest && uv run coverage report`
Expected: PASS, coverage ≥ 85%.

- [ ] **Step 5: Commit**

```bash
git add src/docmend/planning.py tests/test_planning.py
git commit -m "planning: content pass - decode checks, transform prediction, EC-005, collisions, actions (FR-002/FR-015 part 2)"
```

---

### Task 10: CLI `plan` command (IR-002, FR-018 plan half)

**Files:**
- Modify: `src/docmend/cli.py`
- Test: `tests/test_cli_plan.py`

**Interfaces:**
- Consumes: `build_plan`, `artifacts.write_plan`/`read_inventory`/`write_inventory`/`sha256_of_file`, `discovery.scan`, `_load_effective_config`, `new_run_id`, `configure_logging` — all existing.
- Produces: `docmend plan [PATH] [--inventory FILE] [--out FILE] [--config FILE] [--include ...] [--exclude ...] [--fail-on-low-confidence-encoding]`.

**Contract (IR-002 + §18.5 + design decisions 5/6):**
- Exactly one of `PATH` / `--inventory` — both or neither is a usage error (`BadParameter`, exit 2).
- `PATH` shorthand: scan first under the **same run-ID**, write the inventory artifact (default `.docmend/docmend-<run-id>-inventory.json`), then plan referencing it (`inventory_ref.path` = as written, `sha256` via `sha256_of_file`).
- `--inventory FILE`: `read_inventory` — `ArtifactError` → message + exit 2 (ERR-008).
- Config errors → exit 2 (existing `_load_effective_config`).
- Plan artifact default `.docmend/docmend-<run-id>-plan.json`; `--out` overrides.
- Console summary mirrors totals (§18.5): actions, skips-by-reason counts.
- Exit code: 2 input errors; 1 if any skip reason is `unreadable` or `changed-since-scan` (findings, mirroring scan's posture), or `collision` under policy `fail`, or — with `--fail-on-low-confidence-encoding` — any `low-confidence-encoding`/`below-non-ascii-floor` skip; else 0.

- [ ] **Step 1: Write the failing tests**

```python
"""IR-002 `plan` CLI: inventory consumption, PATH shorthand, exits, artifact defaults."""

import json
from pathlib import Path

from typer.testing import CliRunner

from docmend.cli import app

runner = CliRunner()


def make_corpus(root: Path) -> None:
    (root / "a.txt").write_bytes(b"body\r\n")
    (root / "b.md").write_bytes(b"clean\n")


class TestPlanCommand:
    def test_path_shorthand__scans_then_plans_with_inventory_ref(self, tmp_path: Path, monkeypatch) -> None:
        """IR-002: raw PATH performs the scan first and records the inventory reference."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        make_corpus(corpus)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["plan", str(corpus)])
        assert result.exit_code == 0, result.output
        artifact_dir = tmp_path / ".docmend"
        plans = list(artifact_dir.glob("docmend-*-plan.json"))
        inventories = list(artifact_dir.glob("docmend-*-inventory.json"))
        assert len(plans) == 1 and len(inventories) == 1
        document = json.loads(plans[0].read_text())
        assert document["inventory_ref"]["path"] == str(inventories[0])
        assert document["inventory_ref"]["run_id"] == document["run_id"]

    def test_inventory_flag__consumes_existing_artifact(self, tmp_path: Path, monkeypatch) -> None:
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        make_corpus(corpus)
        monkeypatch.chdir(tmp_path)
        scan_result = runner.invoke(app, ["scan", str(corpus)])
        assert scan_result.exit_code == 0
        inventory_path = next((tmp_path / ".docmend").glob("docmend-*-inventory.json"))
        result = runner.invoke(app, ["plan", "--inventory", str(inventory_path), "--out", str(tmp_path / "plan.json")])
        assert result.exit_code == 0, result.output
        document = json.loads((tmp_path / "plan.json").read_text())
        assert document["inventory_ref"]["path"] == str(inventory_path)

    def test_path_and_inventory_together__usage_error(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["plan", str(tmp_path), "--inventory", "x.json"])
        assert result.exit_code == 2

    def test_neither_path_nor_inventory__usage_error(self) -> None:
        result = runner.invoke(app, ["plan"])
        assert result.exit_code == 2

    def test_corrupt_inventory__err_008_exit_2(self, tmp_path: Path) -> None:
        """ERR-008: invalid inventory refuses plan with exit 2."""
        bad = tmp_path / "inv.json"
        bad.write_text("{not json")
        result = runner.invoke(app, ["plan", "--inventory", str(bad)])
        assert result.exit_code == 2

    def test_config_error__exit_2(self, tmp_path: Path) -> None:
        """IR-002: exits non-zero on config errors."""
        (tmp_path / "bad.toml").write_text("[unknown]\nkey = 1\n")
        result = runner.invoke(app, ["plan", str(tmp_path), "--config", str(tmp_path / "bad.toml")])
        assert result.exit_code == 2

    def test_collision_policy_fail__exit_1(self, tmp_path: Path, monkeypatch) -> None:
        """FR-011: fail policy -> non-zero abort, artifact still written (§8.5)."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "foo.txt").write_bytes(b"t\r\n")
        (corpus / "foo.md").write_bytes(b"m\n")
        (tmp_path / "docmend.toml").write_text('[rename]\non_collision = "fail"\n')
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["plan", str(corpus)])
        assert result.exit_code == 1
        assert list((tmp_path / ".docmend").glob("docmend-*-plan.json"))

    def test_fail_on_low_confidence__exit_1(self, tmp_path: Path, monkeypatch) -> None:
        """AW-003: hardened run aborts non-zero on encoding-gate skips."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "short.txt").write_bytes(b"mostly ascii \xe9\xe8")
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["plan", str(corpus), "--fail-on-low-confidence-encoding"])
        assert result.exit_code == 1

    def test_filter_flags__replace_config_lists(self, tmp_path: Path, monkeypatch) -> None:
        """FR-012/OQ-029: --include replaces, never appends, at plan too."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        make_corpus(corpus)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["plan", str(corpus), "--include", "*.md", "--out", str(tmp_path / "p.json")])
        assert result.exit_code == 0
        document = json.loads((tmp_path / "p.json").read_text())
        assert all(a["path"].endswith(".md") for a in document["actions"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_plan.py -v`
Expected: FAIL — `plan` is not a registered command (Typer usage error, exit 2 on every invocation including the happy paths).

- [ ] **Step 3: Implement the command** in `src/docmend/cli.py` (mirror `scan`'s structure — flags, config loading, run-ID, logging, artifact dir):

```python
@app.command()
def plan(
    ctx: typer.Context,
    path: Annotated[
        Path | None,
        typer.Argument(
            help="File or directory to plan over (shorthand: scans first, IR-002).",
        ),
    ] = None,
    inventory_path: Annotated[
        Path | None,
        typer.Option("--inventory", help="Existing inventory artifact to consume (IR-002)."),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write the plan to FILE (default: .docmend/docmend-<run-id>-plan.json)."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="TOML config file (default: ./docmend.toml when present)."),
    ] = None,
    include: Annotated[
        list[str] | None,
        typer.Option("--include", help="Replace paths.include (repeatable; replaces, never appends)."),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Replace paths.exclude (repeatable; replaces, never appends)."),
    ] = None,
    fail_on_low_confidence: Annotated[
        bool,
        typer.Option(
            "--fail-on-low-confidence-encoding",
            help="Exit 1 when any file skips on the FR-007 encoding gates (AW-003).",
        ),
    ] = False,
) -> None:
    """Produce a reviewable DR-002 plan from an inventory (FR-002, IR-002).

    Exit codes (§18.5): 0 clean; 1 findings (unreadable/changed-since-scan
    skips, collision under the fail policy, or encoding-gate skips under
    --fail-on-low-confidence-encoding); 2 input errors (bad config, ERR-008).
    """
    opts = _global_options(ctx)
    if (path is None) == (inventory_path is None):
        raise typer.BadParameter("provide exactly one of PATH or --inventory")
    config = _load_effective_config(config_path, include, exclude)

    now = datetime.now(UTC)
    run_id = new_run_id(now)
    artifact_dir = Path(ARTIFACT_DIR_NAME)
    configure_logging(
        run_id=run_id, command="plan", log_dir=artifact_dir, verbose=opts.verbose, quiet=opts.quiet
    )
    log = get_logger(__name__)

    if path is not None:
        if not path.exists():
            typer.echo(f"error: {path}: no such file or directory", err=True)
            raise typer.Exit(2)
        log.info("plan starting (scan shorthand)", path=str(path))
        inventory = discovery.scan(path, config, run_id=run_id, generated_at=now.isoformat())
        inventory_artifact = artifact_dir / f"docmend-{run_id}-inventory.json"
        artifacts.write_inventory(inventory, inventory_artifact)
    else:
        assert inventory_path is not None
        log.info("plan starting", inventory=str(inventory_path))
        try:
            inventory = artifacts.read_inventory(inventory_path)
        except artifacts.ArtifactError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(2) from exc
        inventory_artifact = inventory_path

    inventory_ref = planning.ArtifactRef(
        path=str(inventory_artifact),
        run_id=inventory.run_id,
        sha256=artifacts.sha256_of_file(inventory_artifact),
    )
    result = planning.build_plan(
        inventory, config, run_id=run_id, generated_at=now.isoformat(), inventory_ref=inventory_ref
    )
    out_path = out if out is not None else artifact_dir / f"docmend-{run_id}-plan.json"
    artifacts.write_plan(result, out_path)

    reasons = Counter(skip.reason for skip in result.skips)
    typer.echo(f"plan: {out_path}")
    typer.echo(
        f"actions: {result.totals.actions}  skips: {result.totals.skips}"
        + (f"  ({', '.join(f'{r} {n}' for r, n in sorted(reasons.items()))})" if reasons else "")
    )

    findings = reasons.get("unreadable", 0) + reasons.get("changed-since-scan", 0)
    if config.rename.on_collision == "fail":
        findings += reasons.get("collision", 0)
    if fail_on_low_confidence:
        findings += reasons.get("low-confidence-encoding", 0) + reasons.get("below-non-ascii-floor", 0)
    if findings:
        raise typer.Exit(1)
```

Imports to add: `from collections import Counter`, `from docmend import planning` (and re-export `ArtifactRef` from planning or import from `docmend.plan` — import `ArtifactRef` from `docmend.plan` directly; adjust the snippet). `PATH` existence is checked manually (not `exists=True`) because the argument is optional.

- [ ] **Step 4: Run the full suite**

Run: `uv run coverage run -m pytest && uv run coverage report`
Expected: PASS.

- [ ] **Step 5: End-to-end smoke by hand** (the `verify`-skill equivalent for this milestone):

```bash
cd "$(mktemp -d)" && mkdir corpus && printf 'caf\xe9 body\r\n' > corpus/demo.txt \
  && printf 'clean\n' > corpus/done.md \
  && uv --project /home/chris/projects/docmend run docmend plan corpus \
  && cat .docmend/docmend-*-plan.json
```

Expected: exit 0; plan JSON shows one action for `demo.txt` (reencode? — the file is below the 20-byte floor, so expect a `below-non-ascii-floor` skip instead: **read the actual output against the gate ladder and confirm it matches**; that reading is the point of the smoke test), no entry for `done.md`.

- [ ] **Step 6: Commit**

```bash
git add src/docmend/cli.py tests/test_cli_plan.py
git commit -m "cli: docmend plan - inventory consumption, PATH shorthand, findings exits (IR-002, AW-003)"
```

---

### Task 11: Initial weird-document corpus (§17.2, FR-015, adr-0015)

**Files:**
- Create: `scripts/gen_weird_corpus.py` (committed generator; run once, fixtures committed)
- Create: `tests/fixtures/weird_documents/*` (fixture bytes + `<name>.expect.json` sidecars)
- Test: `tests/test_weird_corpus.py` (the growing regression harness)

**Interfaces:**
- Consumes: `tests/corpus.py` recipes where useful; `discovery.scan` + `planning.build_plan`.
- Produces: the corpus contract — every fixture file `F` has sidecar `F.expect.json`:

```json
{
  "anomaly": "utf16-suspect-bomless",
  "spec_refs": ["EC-010", "FR-015"],
  "expect": { "disposition": "skip", "reason": "utf16-suspect" }
}
```

or `{"expect": {"disposition": "action", "operations": ["reencode", "normalize_newlines", "rename"], "target_path": "..."}}` or `{"expect": {"disposition": "noop"}}`. Sidecars are excluded from candidacy automatically (`.json` matches no include glob) — assert that in the harness.

- [ ] **Step 1: Write the harness first** (it fails on an empty corpus via an explicit guard):

```python
"""Weird-document corpus regression harness (§17.2, FR-015, adr-0015).

Every fixture under tests/fixtures/weird_documents/ carries a sidecar
`<name>.expect.json` pinning its planned disposition. The corpus grows for the
life of the project; this harness never enumerates fixtures by name — drop a
file + sidecar in, and it is tested. Committed fixtures are byte-exact
(.gitattributes -text) and 100% synthetic (C-002, adr-0015).
"""

import json
from pathlib import Path

import pytest

from docmend.config import DocmendConfig
from docmend.discovery import scan
from docmend.plan import ArtifactRef, Plan
from docmend.planning import build_plan

CORPUS_DIR = Path(__file__).parent / "fixtures" / "weird_documents"
RUN_ID = "run_20260706T000000Z_abc123"


def corpus_cases() -> list[tuple[str, dict]]:
    sidecars = sorted(CORPUS_DIR.glob("*.expect.json"))
    assert sidecars, "weird-document corpus must never be empty (§17.2)"
    return [(s.name.removesuffix(".expect.json"), json.loads(s.read_text())) for s in sidecars]


@pytest.fixture(scope="module")
def corpus_plan() -> Plan:
    config = DocmendConfig()
    inventory = scan(CORPUS_DIR, config, run_id=RUN_ID, generated_at="2026-07-06T00:00:00+00:00")
    ref = ArtifactRef(path="unused.json", run_id=RUN_ID, sha256="sha256:" + "0" * 64)
    return build_plan(inventory, config, run_id=RUN_ID, generated_at="2026-07-06T00:00:00+00:00", inventory_ref=ref)


@pytest.mark.parametrize(("name", "case"), corpus_cases())
def test_weird_document__planned_as_expected(name: str, case: dict, corpus_plan: Plan) -> None:
    """FR-015: each risky-file class in the weird-document corpus is classified, never modified."""
    expect = case["expect"]
    actions = {a.path: a for a in corpus_plan.actions}
    skips = {s.path: s for s in corpus_plan.skips}
    match expect["disposition"]:
        case "skip":
            assert name in skips, f"{name}: expected skip, got {'action' if name in actions else 'noop'}"
            assert skips[name].reason == expect["reason"]
        case "action":
            assert name in actions, f"{name}: expected action, got {'skip: ' + skips[name].reason if name in skips else 'noop'}"
            assert actions[name].operations == expect["operations"]
            assert actions[name].target_path == expect.get("target_path")
        case "noop":
            assert name not in actions and name not in skips
        case other:
            pytest.fail(f"unknown disposition {other!r} in {name}.expect.json")


def test_sidecars_never_become_candidates(corpus_plan: Plan) -> None:
    planned = {a.path for a in corpus_plan.actions} | {s.path for s in corpus_plan.skips}
    assert not any(p.endswith(".expect.json") for p in planned)
```

Note `scan(CORPUS_DIR, ...)` is read-only (FR-001) — scanning committed fixtures in place is safe by the tested guarantee.

- [ ] **Step 2: Write the generator script** `scripts/gen_weird_corpus.py` — synthesizes each fixture deterministically (seeded faker where prose is needed, byte literals elsewhere), writes file + sidecar, and **verifies** each fixture by scanning+planning it and asserting the sidecar expectation holds before writing (so a committed fixture can never disagree with its sidecar at birth). Initial fixture set (one file each; keep every file under ~4 KiB):

| Fixture | Bytes | Expected |
| --- | --- | --- |
| `scattered-nuls.txt` | prose with 3 isolated NULs | skip `nul-bytes` (EC-004) |
| `utf16-bomless.txt` | ASCII prose encoded utf-16-le, no BOM | skip `utf16-suspect` (EC-010) |
| `utf16-le-bom.txt` | BOM + utf-16-le prose, CRLF | action `["reencode", "normalize_newlines", "rename"]` (EC-010/OQ-026) |
| `utf8-bom.txt` | UTF-8 BOM + clean LF prose ending in newline | action `["reencode", "rename"]` (EC-007) |
| `binary-suspect.txt` | dense 0x80–0xFF soup, no NULs (verified: detector returns no candidate) | skip `binary-suspect` (EC-002) |
| `low-confidence.txt` | ≥20 non-ASCII bytes of cross-encoding gibberish (verified: confidence < 0.80) | skip `low-confidence-encoding` (FR-007) |
| `below-floor.txt` | 2 non-ASCII cp1252 bytes in short ASCII prose | skip `below-non-ascii-floor` (FR-007/adr-0009) |
| `decode-replacement.txt` | verified: detected encoding cannot strictly decode all bytes (iterate per Task 9 note) | skip `decode-replacement` (EC-003) |
| `legacy-cp1252.txt` | accented cp1252 prose (≥20 non-ASCII), CRLF, trailing spaces | action `["reencode", "normalize_newlines", "trim_trailing_whitespace", "rename"]` |
| `mixed-endings.txt` | UTF-8, LF+CRLF+CR mixed | action `["normalize_newlines", "rename"]` (EC-006) |
| `padded-legacy.txt` | UTF-8, 200 blank lines between two words | action includes `collapse_blank_lines`, no `shrink-invariant` skip (adr-0016) |
| `zero-byte.txt` | empty | action `["ensure_final_newline", "rename"]` (EC-009) |
| `clean-noop.md` | already-normalized | noop (FR-017 plan half) |
| `markup-crlf.html` | CRLF + trailing whitespace + blank-line runs | action `["normalize_newlines"]`, `target_path` null (adr-0016/OQ-025) |
| `collision-src.txt` + `collision-src.md` | pair | `collision-src.txt` skip `collision` (EC-001); `collision-src.md` noop |
| `tabs-leading.txt` | leading + interior tabs, otherwise clean, LF | noop under defaults (`normalize_tabs` off — the harness proves enabling it is additive, OQ-031) |

If any "verified" fixture cannot be constructed to behave deterministically (detector variance), record what was observed in the sidecar's `anomaly` notes, choose different bytes, and only commit once stable across 3 consecutive generator runs.

- [ ] **Step 3: Generate, inspect, run**

Run: `uv run python scripts/gen_weird_corpus.py && uv run pytest tests/test_weird_corpus.py -v`
Expected: PASS, one parametrized case per fixture. Inspect `git status` — only intended fixture files added; confirm every fixture is small (`du -sh tests/fixtures/weird_documents`).

- [ ] **Step 4: Full suite + commit**

```bash
uv run coverage run -m pytest && uv run coverage report
git add scripts/gen_weird_corpus.py tests/fixtures/weird_documents tests/test_weird_corpus.py
git commit -m "tests: initial weird-document corpus + regression harness (§17.2, FR-015, adr-0015/0016)"
```

---

### Task 12: Encoding-floor boundary fixtures + RQ-022 calibration checkpoint

**Files:**
- Modify: `scripts/gen_weird_corpus.py` (add the floor-matrix generation under `tests/fixtures/weird_documents/encoding_floor/`)
- Create: `tests/fixtures/weird_documents/encoding_floor/*` (+ sidecars, same contract)
- Create: `tests/test_encoding_floor.py`
- Modify: `docs/adr/adr-0009-encoding-detection-dual-skip-gate.md` (calibration outcome note in More Information)
- Modify: `docs/handoff/sessions/2026-07.md` (calibration record — done in Task 13's handoff pass if preferred)

**Interfaces:**
- Consumes: `detect_legacy`, `build_plan`, corpus recipes.
- Produces: the §17.2 three-axis fixture matrix and a recorded calibration verdict (keep 20, or tune within 8–20 — never outside; never reopen OQ-015).

- [ ] **Step 1: Build the matrix generator.** Axes per §17.2/adr-0009: **total length** (~30 B, ~200 B, ~2 KiB) × **non-ASCII count** (8, 12, 19, 20, 21, 40) × **placement** (clustered at start, spread evenly, clustered at end), in cp1252; plus family-equivalence pairs: identical Japanese text bytes as cp932 vs Shift_JIS-labelled recipe and Chinese text as GBK vs GB18030 (assert the *decode outcome* is identical whichever family member the detector names — the §17.2 "family-equivalent decode outcomes" requirement). Not every cell needs committing: commit the **boundary sets** — every (length, placement) at counts 19/20/21 (false-skip and false-accept boundaries), plus one clear-accept (40) and one clear-skip (8) per length, plus the two family pairs. Roughly 35 small files.

- [ ] **Step 2: Write `tests/test_encoding_floor.py`**

```python
"""FR-007 non-ASCII floor boundary sets (adr-0009; RQ-022 calibration evidence).

The committed matrix pins the floor's behavior at its boundaries: counts 19/20/21
across lengths and placements. Files at count >= 20 with a confident detection
must be planned; files below must skip below-non-ascii-floor (unless an earlier
gate fires first — each sidecar records the expected reason). Family-equivalent
fixtures (cp932/Shift_JIS, GBK/GB18030) must DECODE identically whichever family
member the detector names.
"""

import json
from pathlib import Path

import pytest

from docmend.detection import detect_legacy
from docmend.transform.encoding import decode_source

FLOOR_DIR = Path(__file__).parent / "fixtures" / "weird_documents" / "encoding_floor"


def floor_cases() -> list[tuple[str, dict]]:
    sidecars = sorted(FLOOR_DIR.glob("*.expect.json"))
    assert sidecars, "floor matrix must exist (§17.2, RQ-022)"
    return [(s.name.removesuffix(".expect.json"), json.loads(s.read_text())) for s in sidecars]


# Disposition assertions ride the Task 11 harness (the floor dir sits inside
# weird_documents/, so test_weird_corpus.py already covers them); this module
# adds the detector-level assertions the harness cannot express.


@pytest.mark.parametrize(("name", "case"), [c for c in floor_cases() if "family" in c[1]])
def test_family_equivalents__decode_identically(name: str, case: dict) -> None:
    data = (FLOOR_DIR / name).read_bytes()
    detected = detect_legacy(FLOOR_DIR / name)
    assert detected is not None, f"{name}: family fixture must be detectable"
    decoded = decode_source(data, bom=None, encoding_name=detected.name)
    assert decoded == case["family"]["expected_text"]


@pytest.mark.parametrize(("name", "case"), [c for c in floor_cases() if "detection" in c[1]])
def test_boundary_detection_facts__pinned(name: str, case: dict) -> None:
    detected = detect_legacy(FLOOR_DIR / name)
    expected = case["detection"]
    if expected["candidate"]:
        assert detected is not None
        assert (detected.confidence >= 0.80) == expected["confident"]
    else:
        assert detected is None
```

(Sidecars for floor fixtures carry the extra optional keys `detection` / `family` alongside the Task 11 `expect` contract.)

- [ ] **Step 3: Run the calibration.** Generate the FULL matrix (all cells, not just committed ones) into a temp dir; for each file record: detector verdict, confidence, floor pass/fail at floors {8, 12, 16, 20}; tabulate false-accepts (file below the true-trust boundary that would be converted) and false-skips per floor. The decision rule from adr-0009: the floor may move within 8–20 only if the tabulation shows the 20 default false-skipping a materially useful class while a lower value admits no new false-accepts. Expected outcome (per the research the default came from): **keep 20**.

- [ ] **Step 4: Record the outcome.** Append to adr-0009 "More Information":

```markdown
- **MS-2 calibration checkpoint (2026-07-06, RQ-022):** executed against the §17.2 three-axis boundary matrix (committed under `tests/fixtures/weird_documents/encoding_floor/`; full-matrix tabulation in the session log). Outcome: <keep 20 | tuned to N> — <one-sentence tabulation summary>. The checkpoint is closed; the family-aware table and ratio signal remain deferred behind the OQ-020 seam.
```

Fill the placeholders from the actual tabulation; if tuned, also change `encoding.non_ascii_floor` default in `src/docmend/config.py`, §18.2's default cell, and the plan/inventory schema prose — all in this same commit.

- [ ] **Step 5: Full suite + commit**

```bash
uv run coverage run -m pytest && uv run coverage report
git add scripts/gen_weird_corpus.py tests/fixtures/weird_documents/encoding_floor tests/test_encoding_floor.py docs/adr/adr-0009-encoding-detection-dual-skip-gate.md
git commit -m "tests: encoding-floor boundary matrix; RQ-022 MS-2 calibration checkpoint executed (adr-0009)"
```

---

### Task 13: Spec traceability, docs sync, verification gate, PR

**Files:**
- Modify: `docs/specs/docmend.md` (revision row 0.15; §3.1 current-state; §17.3 rows; §21 nothing new unless a DEV/OQ arose)
- Modify: `TODO.md` (move MS-2 + RQ-022 items to Completed)
- Modify: `docs/handoff/state.md`, `STATUS.md`, `docs/handoff/sessions/2026-07.md`, `docs/handoff/architecture.md` (new modules)
- Modify: `README.md` only if it documents the command surface (check; `plan` joins `scan`)

**Interfaces:** none — documentation and gate.

- [ ] **Step 1: Update §17.3** — the completion evidence (Appendix B.3). New statuses with named tests:

| Row | New status |
| --- | --- |
| FR-002 | Complete (MS-2) — `tests/test_planning.py`, `tests/test_weird_corpus.py` |
| FR-007 | Partial (MS-2 gates + codec; conversion-through-apply lands MS-3) — `tests/test_detection.py`, `tests/unit/transform/test_encoding.py`, `tests/test_encoding_floor.py`, `tests/test_planning.py` |
| FR-008 | Complete (MS-2) — `tests/unit/transform/test_newlines.py` (apply-side fixture matrix reaffirmed at MS-3) |
| FR-009 | Complete (MS-2) — `tests/unit/transform/test_whitespace.py`, `test_dispatch.py` |
| FR-010 | Partial (MS-2 plan typing; report side MS-3) — `tests/test_planning.py::TestContentPass::test_rename_only__still_an_action` |
| FR-011 | Partial (MS-2 plan half; overwrite manifest at MS-3) — `tests/test_planning.py::TestCollisions`, `tests/test_cli_plan.py` |
| FR-012 | Partial (MS-1 scan + MS-2 plan; apply at MS-3) — add `tests/test_planning.py`, `tests/test_cli_plan.py` |
| FR-015 | Complete (MS-2) — `tests/test_weird_corpus.py`, `tests/test_planning.py` |
| FR-017 | Partial (MS-2 plan-level no-op; double-apply at MS-4) — `tests/test_planning.py::TestContentPass::test_already_clean_file__neither_action_nor_skip` |
| FR-019 | Partial (MS-2 oversize plan-time guard; watchdog at MS-5) — `tests/test_planning.py::TestFactGates::test_oversize_file__skipped_with_reason` |
| NFR-005 | Complete (MS-2: transforms exist and pass both enforcement layers) — existing rows + `tests/unit/transform/` |
| NFR-006 | Partial (MS-1 scan + MS-2 plan legs) — add `tests/test_cli_plan.py` |
| IR-002 | Complete (MS-2) — `tests/test_cli_plan.py` |
| IR-007 | Partial (inventory + plan; report/manifest with their producers) — add `tests/test_plan_artifact.py` |
| DR-001 | Complete (MS-2: legacy rung populates) — add `tests/test_detection.py`, `tests/test_discovery.py` legacy tests |
| DR-002 | Complete (MS-2) — `tests/test_plan_artifact.py`, `tests/test_planning.py` |

Run `uv run python scripts/check_traceability.py` (or however the `traceability` gate is invoked — check `.github/workflows` for the exact command) to confirm every claimed ID appears under `tests/`.

- [ ] **Step 2: Add revision row 0.15** (match the 0.14 row's voice): MS-2 Domain logic implemented (§19 items 1–4) — planning layer + `docmend plan` (FR-002/FR-015/DR-002/IR-002), pure transforms (FR-007..FR-009, adr-0016 dispatch), charset-normalizer legacy rung populating DR-001, weird-document corpus started (§17.2), RQ-022 floor calibration executed (outcome), plan schema `changed-since-scan` amendment, §17.3 rows updated. Refresh §3.1's current-state sentence (scan **and plan** live; apply/verify land per §19).

- [ ] **Step 3: Deviations audit.** Re-read the "Design decisions locked by this plan" list against what was actually built; anything that drifted from spec text gets a `DEV-` row (or `OQ-` if it needs an owner call). Expected: none, but the audit is the deliverable.

- [ ] **Step 4: Markdown + spec gates**

Run: `npx prettier --write . && npx markdownlint-cli2 --fix "**/*.md" && npx prettier --check . && npx markdownlint-cli2 "**/*.md"` plus the spec validators used by CI (`validate-specs` / `spec lint` — check `.github/workflows/` for exact invocations and run them locally).
Expected: all green. Beware conventions #4 (ToC dead-anchor gotcha) if §17.3 edits touched headings.

- [ ] **Step 5: Full verification gate**

```bash
uv run ruff format --check . && uv run ruff check . && uv run basedpyright \
  && uv run coverage run -m pytest && uv run coverage report && uv run pip-audit
```

Expected: every gate green, coverage ≥ 85%.

- [ ] **Step 6: Handoff ritual** — invoke the `handoff-system-v3` skill and follow it: STATUS.md refresh, session-log rows, `state.md` re-capped (Current → MS-2 landed, Next → MS-3 writer layer/apply; OQ-034 still open, wanted by MS-3), TODO.md moves.

- [ ] **Step 7: Commit docs, push, open the PR**

```bash
git add docs/specs/docmend.md TODO.md STATUS.md docs/handoff/state.md docs/handoff/sessions/2026-07.md docs/handoff/architecture.md
git commit -m "handoff: MS-2 closeout - spec 0.15 traceability, state refresh, session log"
git push origin dev
gh pr create --base main --title "MS-2 Domain logic: planning layer, pure transforms, weird-document corpus" --body "$(cat <<'EOF'
## Summary
- Planning layer + `docmend plan` (FR-002, FR-015, DR-002, IR-002): fact-gate ladder, content pass, collisions, C.4 provenance, per-action IDs + UUIDv7 identities
- Pure transforms (FR-007..FR-009) with adr-0016 file-class dispatch and the EC-005 invariant
- charset-normalizer legacy detection rung populates the inventory (DR-001, adr-0009)
- Initial weird-document corpus + regression harness; encoding-floor boundary matrix; RQ-022 calibration checkpoint executed
- Plan schema: pre-implementation v1.0 amendment adding `changed-since-scan`

## Completion report (Appendix B.3)
See spec §17.3 (rev 0.15) for the requirement-to-test matrix updated in this PR.

## Test plan
- [ ] Five CI gates green (check, validate-specs, lint-markdown, traceability, dependency-review)
EOF
)"
```

Wait for the five required checks; merge per the ADR-0017 workflow (merge commit) once green.

---

## Self-Review Record

Checked against spec §19 MS-2 and the milestone summary ("Correct decisions over the edge-case corpus; transforms pass unit/property tests"):

1. **Spec coverage.** §19 MS-2 item 1 (planning layer, FR-002/FR-015/DR-002) → Tasks 7–10; item 2 (pure transforms FR-007–FR-009) → Tasks 2–6; item 3 (edge-case/threshold tests over the initial weird-document corpus, §10.3) → Tasks 11–12 (every EC-001..EC-011 case has a named test or fixture; EC-008/EC-011 in Task 8); item 4 (decision provenance, C.4) → provenance blocks + config snapshot in Tasks 7/9. RQ-022 checkpoint → Task 12. Out of MS-2 scope by design: FR-003–FR-006, FR-013/FR-014, FR-016 (frontmatter emission optional, MS-5), FR-018 report artifact (MS-3 — the plan artifact itself is FR-002's), watchdog half of FR-019 (MS-5).
2. **Placeholder scan.** No TBDs. Three deliberate empirical-iteration points are flagged as such with concrete procedures (detector-variance fixtures in Tasks 6/9/11, the calibration tabulation in Task 12) — the honest form for behavior pinned to a third-party detector, per the two-corpus strategy.
3. **Type consistency.** `Operation`/`FileClass` single-sourced in `transform/dispatch.py`; plan models re-use `inventory.py` aliases; `build_plan(inventory, config, *, run_id, generated_at, inventory_ref, mint_id)` is identical in Tasks 8, 9, 10 and both test helpers; `apply_text_transforms` keyword names match between Task 5 definition and Task 9 call site; `sha256_of_file` defined Task 7, used Task 10.






