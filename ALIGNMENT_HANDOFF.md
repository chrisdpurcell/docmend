# Repository Alignment Handoff

- Repository: docmend
- Sibling repository: doc-proc-scripts
- Created: 2026-07-07
- Status: temporary coordination artifact — delete after durable records exist (see Completion checklist)

## Purpose

Coordinate boundary alignment, safety hardening, and ADR preparation between the two Doc Processing repositories, per the 2026-07-07 cross-repo review feedback. `docmend` participates as a standalone shippable product; `doc-proc-scripts` is one downstream consumer whose needs inform compatibility and documentation but do not narrow the general-purpose batch-normalization contract.

## Local responsibilities

- Batch normalization engine: scan → plan → apply → restore → verify.
- Artifact schemas (inventory/plan/report/manifest/frontmatter) and validation.
- Strict config semantics, `apply --write` safety-gate semantics.
- Manifest, resume, restore, verify behavior; atomic writer primitives.
- Pure mechanical transforms (encoding, newline, whitespace, `.txt`→`.md` rename).
- Synthetic scale + weird-document fixtures (adr-0015 anonymization procedure).
- Own product direction, release quality, and public interface (adr-0014).

Explicitly not owned here:

- Kate-specific workflow design, human editor bindings, interactive selection filters.
- Real-corpus inspection by agents; corpus-profile privacy abstraction.
- Workstation orchestration / Bash wrapper conventions.
- HTML→Markdown article extraction beyond the adr-0016 mechanical boundary.
- Metadata/frontmatter enrichment beyond current verify/frontmatter schema behavior.

## Sibling responsibilities assumed here

- `doc-proc-scripts` owns workstation orchestration, Kate-facing tools, corpus privacy rules, and wrapper behavior around `docmend` (including independent snapshots for `--preserved-by external` campaigns).
- It does not duplicate scan/plan/apply/restore semantics; its wrappers explain and defer to `docmend` restore limitations.
- Sibling fixes in flight (its own handoff file tracks them): `doc-batch-normalize` preflight mkdir-before-containment-check, path-with-spaces in report summarization, `docproc fix-text --in-place` atomic-write hardening.

## Active coordination items

| ID | Topic | Local owner | Sibling owner | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| ALIGN-001 | P0: same-run rename target collision escapes skip under `on_collision="overwrite"` (`planning.py`) | docmend | — | **Done** (2026-07-07) | Collision classes split: a claimed-target hit always skips (never policy-overridable); inventory/live-target hits obey policy. Tests under all three policies (`tests/test_planning.py::TestCollisions`). Spec FR-011 amended (rev 0.24). |
| ALIGN-002 | P0: `rename_and_rewrite` hard-kill window between target publish, source unlink, and manifest append leaves unmanifested residue | docmend | — | **Done** (2026-07-07) | Chose the intent-record design: manifest schema 1.2→1.3 adds `result: "intent"`, appended fsync'd before the first mutation step; resume reconciles a dangling intent from disk state (complete / adopt / re-execute / ERR-002). Restore + verify inert (applied-only filters). Kill-window tests in `tests/test_resume.py`; adr-0006 amended; spec DR-004 + rev 0.24. |
| ALIGN-003 | P1: discovery walks excluded directories (`.git`, `.venv`, `node_modules`, `.docmend`) instead of pruning `dirnames` | docmend | — | **Done** (2026-07-07) | Pruned via `exclude.match_file(rel + "/")` (pathspec dir-probe). Selection unchanged (dir-prefix semantics already excluded contents); per-file `excluded` skip records now exist only for file-pattern excludes — matches gitignore's parent-dir-exclusion rule, incl. the negation corner. Tests in `tests/test_discovery.py`/`tests/test_cli_scan.py`. |
| ALIGN-004 | P1: `release.yml` uses movable `setup-uv@v8.2.0` tag with `contents: write`; `check.yml` is SHA-pinned | docmend | — | **Done** (2026-07-07) | Pinned to the same SHA as `check.yml` (`fac544c` = v8.2.0); first-party `actions/*` stay on tags, matching the check job's convention. |
| ALIGN-005 | P1: README/AGENTS still describe status as "v1.0.0 released"; current release is v1.0.1 | docmend | — | **Done** (2026-07-07) | README status line + AGENTS project line now v1.0.1; history stays in CHANGELOG. |
| ALIGN-006 | Formal cross-repo boundary ADR | docmend | doc-proc-scripts | **Drafted — owner acceptance pending** | `docs/adr/adr-0018-doc-processing-repository-boundary.md` (status: proposed). Sibling repo should cross-reference or mirror it; owner flips to accepted, then both handoff files can be deleted. |

## Decisions to migrate into ADR

| Decision | Target ADR location | Status |
| --- | --- | --- |
| Repository boundary: docmend = standalone batch engine with many possible downstreams; doc-proc-scripts = workstation/interactive/privacy layer and wrapper | `docs/adr/adr-0018-doc-processing-repository-boundary.md` | Draft |
| Restore expectations: `docmend restore` is complete only when tool backups exist for content rewrites; under `--preserved-by external` the wrapper's independent snapshot is the authoritative full restore path | same ADR | Draft |
| Same-run plan-internal collisions are a safety invariant, not a policy choice (ALIGN-001 outcome) | same ADR (safety contract section) + spec §21 revision row | Draft |

## Safety notes

- No real corpus content, private paths, secrets, or hostnames in this file — synthetic fixtures or content-free metadata only (repo is public).
- Mutating commands stay dry-run/report-first; the `apply --write` safety gate is not weakened by any alignment fix.
- Transforms stay pure; the scan → plan → apply review model is preserved.

## Completion checklist

- [ ] Boundary responsibilities agreed by both agents (docmend side proposed in adr-0018; awaiting sibling + owner).
- [x] Safety-critical fixes completed or explicitly deferred (ALIGN-001, ALIGN-002 — both fixed 2026-07-07).
- [x] Tests added for all implemented safety changes (617 tests, 97% coverage; kill-window, collision, pruning suites).
- [x] Durable docs updated (spec rev 0.24, adr-0006 amendment, CHANGELOG Unreleased, README, resume runbook, AGENTS).
- [ ] Formal ADR or cross-referenced ADRs accepted by the owner (adr-0018 is `proposed`).
- [ ] This temporary file deleted after durable records exist.
