# Dependency License Compatibility Record

Spec §16 requires an OSS-license compatibility check "at MS-0 when dependencies are added." This is that record: docmend is **MIT-licensed and distributed** (wheel/sdist at MS-5, spec §18.3), so runtime dependencies must be permissive; dev-group dependencies are never distributed and only need to be usable. Checked 2026-07-06 from installed package metadata (`License-Expression` / classifiers). CI keeps this current mechanically: the `dependency-review` gate (adr-0017) rejects new dependencies whose license is outside the repo allowlist.

## Runtime closure (installed at MS-0)

| Package | License | Compatible with MIT distribution |
| --- | --- | --- |
| typer | MIT | ✅ |
| click (via typer) | BSD-3-Clause | ✅ |
| shellingham (via typer) | ISC | ✅ |
| annotated-doc (via typer) | MIT | ✅ |
| pydantic / pydantic-core | MIT | ✅ |
| annotated-types (via pydantic) | MIT | ✅ |
| typing-extensions | PSF-2.0 | ✅ |
| typing-inspection (via pydantic) | MIT | ✅ |
| structlog | MIT OR Apache-2.0 | ✅ (dual; MIT elected) |
| rich | MIT | ✅ |
| markdown-it-py / mdurl (via rich) | MIT | ✅ |
| pygments (via rich) | BSD-2-Clause | ✅ |
| colorama (typer marker dep, Windows-only) | BSD-3-Clause | ✅ (not installed on Linux) |

## Approved-but-not-yet-added runtime deps (§8.6; pre-cleared for their milestone)

| Package | License | Note |
| --- | --- | --- |
| charset-normalizer | MIT | MS-2 (FR-007) |
| pathspec | MPL-2.0 | MS-1 (FR-012). File-level weak copyleft: using it unmodified as a dependency imposes no obligation on docmend's MIT code; MPL-2.0 is in the CI allowlist. Modifying vendored pathspec files (not planned) would require releasing those files' changes under MPL. |
| jsonschema (`format-nongpl` extra) | MIT | MS-1 (OQ-018). The `format-nongpl` extra exists precisely to keep GPL format validators out of the closure — keep using it. |
| ruamel.yaml | MIT | Frontmatter work (OQ-009/OQ-022) |

## Dev group (never distributed — §8.6 dev table)

pytest (MIT), coverage (Apache-2.0), ruff (MIT), basedpyright (MIT), pip-audit (Apache-2.0), import-linter (BSD-2-Clause), grimp (BSD-2-Clause, via import-linter), allpairspy (MIT), faker (MIT). Pre-cleared for MS-1: hypothesis (MPL-2.0 — dev-only per OQ-019, never in the distributed package), pyfakefs (Apache-2.0), pytest-xdist (MIT).

## Verdict

No copyleft in the runtime closure; every license present or pre-approved is on the CI `dependency-review` allowlist. The §16 checklist item is satisfied for MS-0. Re-run this check whenever a new §8.6 dependency is actually added (the CI gate enforces it on every PR regardless).
