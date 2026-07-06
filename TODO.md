# TODO

**Maintenance Instructions:** See [repo-hygiene.md](docs/repo-hygiene.md#todomd)

## User Tracked Tasks

_None outstanding._

## Agent Tracked Tasks

<instruction> Agents summarize outstanding work from `docs/handoff/state.md`, `docs/handoff/architecture.md`, `docs/handoff/specs-plans.md`, bug records, plans, and session notes here. The purpose is to provide convenience and transparency to the human user. </instruction>

- [ ] **OQ-034 owner decision (raised at MS-1, non-blocking, wanted by MS-3):** default artifact/log location. Implementation proceeds on the recorded assumption — `./.docmend/` in the invoking directory, run-ID-keyed filenames, `--report` override, `.docmend/` in default excludes. Confirm or redirect in `docs/open-questions.md` § OQ-034.
- [ ] **MS-2 calibration checkpoint (carried from RQ-022, not a reopen):** during MS-2, run one project-internal validation of the 20-byte non-ASCII floor against docmend's own short-file distribution; may tune the number within the ~8–20 band without reopening OQ-015.
- [ ] Author `schemas/frontmatter.schema.json` and rewrite the §9 null-heavy example to the RQ-014 minimal shape when frontmatter schema work lands (GAP-56; gated by OQ-009/OQ-013).

## Completed Tasks

<instruction> Agents should move completed tasks from both the user and agent sections to here. This space is not for agent tracking or handoff purposes; it is a user convenience and these will be deleted by the user once reviewed. </instruction>

- [x] **MS-1 Core workflow implemented (2026-07-06, spec §19 items 1–4; spec rev 0.14):** `docmend scan PATH` end-to-end — read-only discovery layer (FR-001 proven via mtime+hash snapshot), FR-012 include/exclude filters (pathspec, OQ-029 replace semantics), single-pass chunked classification (BOM/strict-UTF-8 FR-007 rungs, newline census property-tested across chunk boundaries, NUL + non-ASCII floor facts, sha256), symlink records (EC-008), hard-link alias groups (EC-011), ERR-007 unreadable-skips, single-file PATH (NFR-006 scan leg). Four OQ-004 artifact JSON Schemas pinned in `src/docmend/schemas/` per adr-0005 (inventory live; plan/report/manifest v1.0 contracts with satisfiability + pydantic cross-check tests). New OQ-034 (open, non-blocking): `.docmend/` default artifact/log location. Deps added per §8.6: pathspec, jsonschema[format-nongpl]; dev hypothesis/pyfakefs/pytest-xdist — license record extended (all permissive; fqdn MPL-2.0 weak-copyleft cleared like pathspec). 125 tests, 97% coverage; §17.3 FR-001/IR-001 Complete, FR-012/IR-007/DR-001/NFR-006 Partial.
- [x] **MS-0 Foundation implemented (2026-07-06, spec §19):** `docmend` console entry point (`[project.scripts]`, closing the earlier agent task) with the IR-005 global flags (`--help/-h`, `--version/-V`, `--verbose/-v`, `--quiet/-q`, `--dry-run/-n`, verbose/quiet exclusivity → exit 2); §18.2 TOML config loading via strict pydantic models (unknown key/type/enum/range each rejected; `./docmend.toml` auto-discovery; reserved `parallel.model` values get a dedicated error); OQ-017 logging framework (structlog through stdlib handlers, per-run DEBUG-floored JSONL keyed on the `run_YYYYMMDDTHHMMSSZ_hex` run-ID, console level mapped from flags); NFR-005 purity enforcement wired before any transform exists (import-linter forbidden contract run inside pytest + autouse open/os.open/io.FileIO blocking fixture); §16 dependency-license check recorded in `docs/dependency-licenses.md`. 65 tests, 98% coverage, all five CI gates + spec gates green.
- [x] **Branch/CI/CD workflow adopted from hw-radar (2026-07-06, ADR-0017):** `dev`→`main` merge-commit PR model; `main` classic protection (5 strict required checks — `check`, `validate-specs / Specs`, `lint-markdown / Markdown`, `traceability`, `dependency-review` — required signatures, PR-required approvals=0, enforce-admins, conversation resolution, no force-push/deletion). Added `dependabot.yml` + PR-only `dependency-review.yml` (allowlist tightened vs hw-radar — no copyleft pre-approved since docmend distributes). Release deferred to MS-5 (README documents the tag→`uv build`→GitHub Release path). Standard-owned `check.yml`/`validate-specs.yml`/`lint-markdown.yml` left unedited (conventions #8) → no `dev` push-trigger; the PR is the gate. Landed via PR #1, which dogfooded the pipeline (all 5 checks green).
- [x] **Traceability drift-check gate built (2026-07-06, GAP-53 automation half):** `scripts/check_traceability.py` (PEP 723, stdlib-only) cross-checks §7↔§17.3, §21 OQ↔RQ/open records, and §17.3 progress claims↔test mentions; 8 regression tests in `tests/test_check_traceability.py`; wired into CI as the additive `.github/workflows/traceability.yml` (check.yml is a standard-owned twin, left untouched per conventions #8).
- [x] **Gap-register outstanding-items strategy (2026-07-06):** triaged all 71 gaps against current state (~38 already resolved by RQ-015..024/ADRs). **Batch A** (spec rev 0.9): synced spec to settled ADR decisions + mechanical fixes (GAP-12/13/14/15/17/18/21/25/27/28/36/38/39/48/51/53-rows/66). **Batch B** (spec rev 0.10): owner settled the nine decision-bearing gaps as OQ-025..033 → RQ-025..033 (HTML mechanical-only include, UTF-16/32 BOM-before-NUL, parent single-writer + run lock, watchdog + size guard, config precedence, EC-005 invariant + ratio, leading-tab semantics, two-corpus + anonymization, import-linter purity); ADR-0007/0009 amendment notes; conventions #6 fixture review gate. GAP-70 was already fixed; GAP-62/64 accepted as-is; GAP-40/41/45/59/60/71 + GAP-20/54 remain milestone-gated with recorded triggers.

## Usage Notes

- This document is not a substitute for `STATUS.md`; the agent(s) should not use it to track ongoing work. This document is intended for human user convenience and transparency.
- Preserve the separation between user-owned and agent-tracked tasks — do not complete a `## User Tracked Tasks` item unless asked.
- Do not store secrets, private hostnames, or credential values in this file.
