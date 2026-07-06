# Dependency License Compatibility Record

Spec §16 requires an OSS-license compatibility check "at MS-0 when dependencies are added." This is that record: docmend is **MIT-licensed and distributed** (wheel/sdist at MS-5, spec §18.3), so runtime dependencies must be permissive; dev-group dependencies are never distributed and only need to be usable. Checked 2026-07-06 from installed package metadata (`License-Expression` / classifiers); extended 2026-07-06 with the MS-1 additions (pathspec, jsonschema + `format-nongpl` closure; dev hypothesis/pyfakefs/pytest-xdist). CI keeps this current mechanically: the `dependency-review` gate (adr-0017) rejects new dependencies whose license is outside the repo allowlist.

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

## Runtime closure additions (installed at MS-1)

| Package | License | Compatible with MIT distribution |
| --- | --- | --- |
| pathspec | MPL-2.0 | ✅ File-level weak copyleft: using it unmodified as a dependency imposes no obligation on docmend's MIT code; MPL-2.0 is in the CI allowlist. Modifying vendored pathspec files (not planned) would require releasing those files' changes under MPL. |
| jsonschema | MIT | ✅ (`format-nongpl` extra — exists precisely to keep GPL format validators out of the closure; keep using it) |
| attrs / jsonschema-specifications / referencing / rpds-py (via jsonschema) | MIT | ✅ |
| lark / rfc3339-validator / rfc3986-validator / uri-template / six (format-nongpl extras) | MIT | ✅ |
| rfc3987-syntax (format-nongpl extra) | MIT | ✅ The MIT replacement for the GPL `rfc3987`. GitHub's dependency graph mis-reports it as "Apache-2.0 AND GPL-1.0-or-later AND MIT" — verified 2026-07-06 against the installed distribution: LICENSE is MIT, `License-Expression: MIT`, no GPL text in any shipped file (a stale "Apache Software License" classifier + repo-level scanning cause the false expression). Exempted by purl in `dependency-review.yml` with this rationale. |
| isoduration (format-nongpl extra) | ISC | ✅ |
| jsonpointer / webcolors (format-nongpl extras) | BSD-3-Clause | ✅ |
| arrow / tzdata (format-nongpl extras) | Apache-2.0 | ✅ |
| python-dateutil (via arrow) | BSD-3-Clause OR Apache-2.0 (dual) | ✅ |
| fqdn (format-nongpl extra) | MPL-2.0 | ✅ Same file-level weak-copyleft analysis as pathspec: unmodified dependency, no obligation on MIT code; in the CI allowlist. |

## Runtime closure additions (installed at MS-2)

| Package | License | Compatible with MIT distribution |
| --- | --- | --- |
| charset-normalizer | MIT | ✅ FR-007 legacy encoding detection rung (adr-0009); no transitive dependencies. |

## Approved-but-not-yet-added runtime deps (§8.6; pre-cleared for their milestone)

| Package            | License | Note                             |
| ------------------ | ------- | -------------------------------- |
| ruamel.yaml        | MIT     | Frontmatter work (OQ-009/OQ-022) |

## Dev group (never distributed — §8.6 dev table)

pytest (MIT), coverage (Apache-2.0), ruff (MIT), basedpyright (MIT), pip-audit (Apache-2.0), import-linter (BSD-2-Clause), grimp (BSD-2-Clause, via import-linter), allpairspy (MIT), faker (MIT). Added at MS-1 per OQ-019: hypothesis (MPL-2.0 — dev-only, never in the distributed package), pyfakefs (Apache-2.0), pytest-xdist (MIT), execnet (MIT, via pytest-xdist), sortedcontainers (Apache-2.0, via hypothesis).

## Verdict

No copyleft in the runtime closure; every license present or pre-approved is on the CI `dependency-review` allowlist. The §16 checklist item is satisfied for MS-0. Re-run this check whenever a new §8.6 dependency is actually added (the CI gate enforces it on every PR regardless).
