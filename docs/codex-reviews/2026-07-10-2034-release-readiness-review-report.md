# Release Readiness Review

## Review Metadata

- repo_path: `.`
- repo_name: `docmend`
- review_date: `2026-07-10`
- review_type: `release-readiness-review`
- ship_decision: `not-ready-for-a-new-release-from-current-head`
- current_released_baseline: `v1.0.2`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- working_tree_state: `dirty-before-review`
- preexisting_worktree_changes: `AGENTS.md modified; docs/codex-reviews/ untracked`
- report_write_scope: `only this requested report was created or overwritten`
- detected_runtimes: `Python 3.14.6; uv 0.11.6 locally`
- detected_frameworks: `Typer, Rich, Pydantic, jsonschema, structlog`
- packaging_surfaces_reviewed: `pyproject.toml, uv.lock, uv_build backend, wheel, sdist, console entry point, packaged JSON Schemas, py.typed`
- release_surfaces_reviewed: `.github/workflows/release.yml, README release process, CHANGELOG.md, adr-0017, v1.0.2 tag baseline`
- artifact_provenance_surfaces_reviewed: `GitHub Release assets, action/tool pins, asset attestations, SBOM/checksum posture`
- ci_surfaces_reviewed: `check, dependency-review, lint-markdown, traceability, validate-specs workflows`
- deploy_and_rollout_surfaces_reviewed: `local CLI install/upgrade, staged library rollout, dry-run, plan promotion, restore/resume`
- environment_protection_surfaces_reviewed: `repository workflow only; GitHub rulesets/environments could not be verified`
- migration_surfaces_reviewed: `versioned inventory/plan/report/manifest/frontmatter artifacts; no database`
- observability_surfaces_reviewed: `structured run logs, reports, exit codes, release workflow logs`
- support_surfaces_reviewed: `restore and resume runbooks; release rollback and post-publish guidance`
- post_release_verification_surfaces_reviewed: `release workflow wheel version smoke; no post-publish asset verification workflow`
- shared_research_reused: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
- targeted_follow_up_research: `GitHub CLI release tag verification and GitHub artifact attestations only`
- prior_baselines_compared: `v1.0.2 tag, CHANGELOG 1.0.2 entry, docs/handoff/deployed.md, 2026-07-10 hygiene session evidence`
- important_external_surfaces_not_in_repo: `branch protection, tag rulesets, signed-tag enforcement, protected environments/reviewers, release immutability, Actions run status, GitHub Release attestations`
- important_unknowns: `intended next version/tag; external GitHub controls; candidate CI status; current online vulnerability result`
- default_exclusions_applied: `generated caches, build output outside /tmp review directory, bulky fixtures except contract inventory, coverage artifacts`

## Release Readiness Matrix

| Release area | Status | Direct evidence | Finding or disposition |
| --- | --- | --- | --- |
| `build-and-package-integrity` | `partial` | `uv lock --check` and `uv build --no-sources` passed; wheel/sdist were valid; wheel contained schemas and `py.typed` | ISSUE-003, ISSUE-004 |
| `artifact-provenance-and-sbom` | `not-ready` | No attestation, SBOM, or checksum generation in `release.yml` | ISSUE-003, ISSUE-005 |
| `versioning-and-change-notes` | `blocked` | HEAD is three commits past `v1.0.2` but builds `1.0.2`; changelog has no unreleased candidate | ISSUE-001, ISSUE-007 |
| `ci-gates-and-release-automation` | `blocked` | Main PR gates exist; tag workflow does not bind tag, commit, version, or gate result | ISSUE-002, ISSUE-003, ISSUE-004 |
| `deployment-and-rollout-readiness` | `ready-with-release-caveats` | Local CLI installation and staged library exposure are documented | ISSUE-006 |
| `progressive-rollout-and-canary` | `ready` | Include-filtered scan/plan/apply widening is the repo-specific canary model | Service canaries are `not needed for this repo` |
| `environment-protection-and-approval-gates` | `not-ready` | No `environment:` or in-workflow approval/identity gate; external settings unknown | ISSUE-002 |
| `rollback-and-recovery-readiness` | `partial` | Product restore/resume is strong and tested; package-release rollback is only one sentence | ISSUE-006 |
| `migration-and-state-change-readiness` | `ready` | No database; durable file artifacts are versioned and legacy manifest shapes are tested | Database migration tooling is `not needed for this repo` |
| `contract-and-compatibility-confidence` | `ready` | Five packaged schemas, schema/model cross-checks, legacy manifest behavior, CLI contract tests | Residual risk: no real-library rollout evidence yet |
| `test-and-quality-signal-confidence` | `ready-with-artifact-gap` | 619 tests passed, one opt-in scale test skipped, 97% coverage | ISSUE-004 |
| `observability-and-support-readiness` | `ready-with-release-caveats` | Per-run structured logs/reports and exit taxonomy are implemented | ISSUE-006 |
| `post-release-verification-and-monitoring-window` | `not-ready` | No download/verify/install journey or defined observation window after publication | ISSUE-006 |
| `configuration-and-environment-readiness` | `ready` | Linux/POSIX and Python 3.14+ scope is explicit; strict TOML defaults are tested | Multi-environment service config is `not needed for this repo` |
| `security-and-compliance-ship-blockers` | `partial` | Dependency/license gates exist; privileged release chain is not fully immutable | ISSUE-003, ISSUE-005 |
| `approval-and-governance` | `not-ready` | README states signed tags on main, but automation does not prove those predicates | ISSUE-002 |
| `release-documentation-and-operator-guidance` | `partial` | Install and product recovery docs exist; bad-release response is incomplete | ISSUE-006, ISSUE-007 |
| `release-validation-and-smoke-checks` | `partial` | Published wheel receives only `docmend --version` before release | ISSUE-004 |

## Severity Summary

| Severity | Count | IDs                             |
| -------- | ----: | ------------------------------- |
| Critical |     0 | None                            |
| High     |     3 | ISSUE-001, ISSUE-002, ISSUE-003 |
| Medium   |     3 | ISSUE-004, ISSUE-005, ISSUE-006 |
| Low      |     1 | ISSUE-007                       |

- critical_ship_blocker_count: `0`
- high_ship_blocker_count: `3`
- release_recommendation: `Do not create a new tag from current HEAD until ISSUE-001 through ISSUE-003 are resolved.`

## Findings

### ISSUE-001: Current HEAD is not a coherent new release candidate

- first_pass: `1`
- severity: `high`
- confidence: `high`
- release_area: `versioning-and-change-notes`
- issue_type: `versioning-change-note-gap`
- evidence_basis: `verified-directly`
- locations: `pyproject.toml:3`, `src/docmend/__init__.py:10`, `CHANGELOG.md:5`, Git history
- impact: `A new tag from HEAD would publish a wheel and sdist named/versioned 1.0.2 even though 1.0.2 is already released. Consumers and operators could not distinguish the new artifact from the existing release by package version.`
- evidence:
  - `git rev-list --count v1.0.2..HEAD` returned `3`.
  - `pyproject.toml` and `docmend.__version__` remain `1.0.2`.
  - The built artifacts were `docmend-1.0.2-py3-none-any.whl` and `docmend-1.0.2.tar.gz`.
  - `CHANGELOG.md` begins with the already-released `1.0.2` entry and has no `Unreleased` or next-version section.
- remediation:
  1. Declare the intended next version and release scope.
  2. Update every authoritative version surface and `uv.lock` together.
  3. Add the matching changelog entry.
  4. Require the tag text, package metadata version, runtime `--version`, and changelog heading to agree before publication.
- verification: `Build from the candidate tag and assert the tag-derived version equals wheel METADATA, sdist PKG-INFO, pyproject version, runtime version, and changelog heading.`

### ISSUE-002: Any matching tag can publish without proving it is the signed mainline candidate

- first_pass: `1`
- severity: `high`
- confidence: `medium`
- release_area: `approval-and-governance`
- issue_type: `approval-governance-gap`
- evidence_basis: `verified-repo-behavior-plus-external-settings-unknown`
- locations: `.github/workflows/release.yml:7-12`, `.github/workflows/release.yml:35-42`, `README.md` release process, `docs/specs/docmend.md:926-931`
- impact: `A pushed v*.*.* tag on a non-main commit, a lightweight or unsigned tag, or a tag whose version disagrees with the package can trigger publication. This bypasses the repo's stated signed-tag-on-main approval contract.`
- evidence:
  - The workflow trigger accepts every `v*.*.*` tag and performs no main-ancestry, tag-signature, annotated-tag, or package-version check.
  - No protected `environment:` is named in the publish job.
  - `gh release create --verify-tag` only aborts when the remote tag does not exist; it does not verify a cryptographic tag signature or main ancestry, per the [GitHub CLI manual](https://cli.github.com/manual/gh_release_create).
  - GitHub tag rulesets or environment protections may reduce this risk, but they live outside the repository and were not verifiable in this review.
- remediation:
  1. Fetch `origin/main` and verify the tagged commit is the intended mainline commit.
  2. Verify an annotated signed tag against the project's trusted signer policy.
  3. Enforce tag/package/changelog equality and fail if the release already exists.
  4. Put publication behind a protected `release` environment with required reviewers, or document equivalent tag-ruleset enforcement.
- verification: `Exercise negative workflow tests for unsigned, lightweight, off-main, reused-version, mismatched-version, and already-published tags; each must stop before contents-write publication.`

### ISSUE-003: The privileged release build is not immutable or least-privileged

- first_pass: `3`
- severity: `high`
- confidence: `high`
- release_area: `ci-gates-and-release-automation`
- issue_type: `security-compliance-ship-blocker`
- evidence_basis: `verified-directly-plus-current-official-guidance`
- locations: `.github/workflows/release.yml:11-29`
- impact: `A mutable Action reference or drifting uv executable can change the bytes built under the same repository commit, and every build/smoke step runs with contents:write available to the job token.`
- evidence:
  - `actions/checkout@v7` is a mutable tag inside the contents-write release job.
  - `astral-sh/setup-uv` is SHA-pinned, but unlike `check.yml`, the release workflow does not set `with.version: 0.11.6`; the uv executable therefore is not bound by repo configuration.
  - Build and smoke steps share the same job-level `contents: write` permission needed only for final publication.
  - Shared research records GitHub's full-SHA and least-privilege guidance for non-local Actions.
- remediation:
  1. Pin every non-local Action and reusable workflow to a full commit SHA, including first-party Actions.
  2. Pin the uv executable version in the release workflow to the same reviewed version as CI.
  3. Split build/test and publish into separate jobs: build with `contents: read`, transfer an immutable workflow artifact, then grant `contents: write` only to the protected publish job.
  4. Record the runner, Python, uv, lockfile, source commit, and artifact digests in release evidence.
- verification: `Review the workflow permissions graph and confirm the publish job consumes exactly the artifact produced by the read-only build job; rebuild twice from the same commit and compare digests.`

### ISSUE-004: The release gate barely tests the artifact users install

- first_pass: `2`
- severity: `medium`
- confidence: `high`
- release_area: `release-validation-and-smoke-checks`
- issue_type: `release-validation-gap`
- evidence_basis: `verified-directly`
- locations: `.github/workflows/release.yml:28-33`, `.github/workflows/check.yml:29-48`
- impact: `Source-checkout tests can pass while the wheel is missing package data, has a broken command beyond version output, or cannot complete the destructive workflow users rely on.`
- evidence:
  - The release job builds both formats and `uv_build` builds the wheel from the sdist, which is good.
  - The only wheel command run by automation is `docmend --version`.
  - The full test suite runs against the repository environment before artifact creation, not against the installed wheel/sdist product.
  - Manual review confirmed the current wheel includes all five JSON Schemas, `py.typed`, and a working console entry point; the missing control is a durable release gate, not a defect in the current artifact.
- remediation:
  1. Inspect wheel and sdist contents and archive integrity in CI.
  2. Install the wheel into a clean isolated environment and run help, schema-resource loading, and a synthetic scan/plan/apply/restore/verify journey.
  3. Build a wheel from the produced sdist and compare its expected content contract.
  4. Publish only the already-tested artifacts; never rebuild in the publish job.
- verification: `Delete the source checkout from the smoke test's import path and prove the clean installed wheel completes the release contract suite.`

### ISSUE-005: Published assets have no repository-defined provenance, SBOM, or digest bundle

- first_pass: `3`
- severity: `medium`
- confidence: `high`
- release_area: `artifact-provenance-and-sbom`
- issue_type: `artifact-provenance-sbom-gap`
- evidence_basis: `verified-directly-plus-current-official-guidance`
- locations: `.github/workflows/release.yml:28-42`
- impact: `A consumer cannot cryptographically bind a downloaded wheel/sdist to this repository, workflow, commit, and dependency inventory using release evidence defined by the repo.`
- evidence:
  - The workflow uploads only `dist/*`; it generates no checksums, provenance attestation, or SBOM.
  - GitHub documents that artifact attestations bind artifacts to the repository, workflow, commit, and triggering event and can include an SBOM ([GitHub artifact attestation guidance](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts)).
  - Whether GitHub immutable releases or release-level attestations are enabled externally is unknown.
- remediation:
  1. Generate SHA-256 digests and build provenance for the exact wheel and sdist.
  2. Generate and attest an SBOM for the resolved runtime closure, or document why the chosen inventory is equivalent.
  3. Publish verification instructions and expected repository/workflow identity.
  4. Enable immutable releases if compatible with the release process.
- verification: `Download each asset after release and verify its digest and attestation against the expected repository, workflow, tag commit, and signer identity.`

### ISSUE-006: Bad-release rollback and post-release verification are underspecified

- first_pass: `4`
- severity: `medium`
- confidence: `high`
- release_area: `post-release-verification-and-monitoring-window`
- issue_type: `post-release-verification-gap`
- evidence_basis: `verified-directly`
- locations: `docs/specs/docmend.md:922-962`, `README.md` release process, `docs/runbooks/restore-from-manifest.md`, `docs/runbooks/resume-after-interruption.md`
- impact: `The project can recover a document run, but lacks a repeatable response for a bad GitHub Release, compromised asset, or artifact that fails only after publication. Installing an older executable does not undo documents already changed by the bad release.`
- evidence:
  - The spec's package rollback guidance is only `install the previous release tag`.
  - Product-level restore/resume runbooks and drills are strong and correctly separate document recovery from package rollback.
  - No release runbook defines asset download verification, clean install, post-publish CLI journey, observation window, release withdrawal/yank/delete decision, user notification, or preservation of incident evidence.
- remediation:
  1. Add a release checklist/runbook with pre-tag approval, publish, download, digest/attestation verification, and clean-install contract smoke.
  2. Define a monitoring window and owner for inspecting workflow/release evidence and first field use.
  3. Define bad-release actions: mark affected versions, stop further rollout, preserve artifacts/logs, publish corrected guidance, install a prior version, and use manifest+backup restore for already-mutated libraries.
  4. Keep package rollback and data recovery as separate explicit procedures.
- verification: `Run a tabletop drill for a bad wheel after one synthetic apply and prove both executable rollback and byte-identical document recovery.`

### ISSUE-007: Duplicate/no-change releases and changelog drift are not rejected

- first_pass: `4`
- severity: `low`
- confidence: `high`
- release_area: `versioning-and-change-notes`
- issue_type: `versioning-change-note-gap`
- evidence_basis: `verified-directly`
- locations: `.github/workflows/release.yml:35-42`, `CHANGELOG.md:1-5`
- impact: `The automation can create a release with no new commits and generated notes that are not mechanically tied to the curated changelog.`
- evidence:
  - `gh release create` uses `--generate-notes` but not `--fail-on-no-commits`.
  - The [GitHub CLI manual](https://cli.github.com/manual/gh_release_create) states that release creation permits no-new-commit releases by default.
  - No check requires the tag version to have a changelog section or reconciles generated notes with it.
- remediation: `Add no-new-commit rejection, changelog/version validation, and an explicit policy for whether curated changelog text or generated GitHub notes is authoritative.`
- verification: `Attempt a no-change tag and a tag missing its changelog heading; both must fail before release creation.`

## Critical Ship Blockers

- critical_findings: `none`
- high_findings_treated_as_ship_blockers: `ISSUE-001, ISSUE-002, ISSUE-003`
- decision_basis: `The current application baseline is healthy, but a new artifact cannot be safely identified, authorized, or reproduced by the present release automation.`

## Rollout, Rollback, And Recovery Readiness

- directly_verified:
  - `Dry-run, reviewed plan, write gate, atomic mutation, append-only manifest, resume, restore, and verify paths are implemented and heavily tested.`
  - `The spec defines an include-filtered subset rollout before widening exposure to the real library.`
  - `Restore and resume runbooks exist.`
- inferred:
  - `The owner can use the existing staged library rollout as a canary model after a release artifact passes post-publish verification.`
- not_verified:
  - `The owner's real-library preservation backend and manual restore drill.`
  - `A package-release rollback/tabletop drill.`
- gap: `ISSUE-006`

## Artifact Provenance, Inventory, And Package Integrity

- verified_package_evidence:
  - `uv lock --check`: passed.
  - `uv build --no-sources`: built sdist and wheel successfully.
  - `unzip -t`: wheel archive passed.
  - `wheel contents`: all five JSON Schemas, `py.typed`, console entry point, code modules, METADATA, and RECORD present.
  - `sdist contents`: pyproject, README, and full src package present.
  - `wheel METADATA`: name `docmend`, version `1.0.2`, Python `>=3.14`, MIT expression, declared runtime dependencies.
  - `unpacked-wheel console smoke`: `docmend 1.0.2` and help output succeeded against the locked environment.
- inconclusive_package_evidence:
  - `A fully isolated wheel install attempted to resolve dependencies from PyPI and was blocked by sandbox DNS; this was not a package failure.`
- gaps: `ISSUE-003, ISSUE-004, ISSUE-005`

## Migration, Contract, And Compatibility Risks

- database_migrations: `not needed for this repo`
- durable_contracts: `inventory 1.2, plan 1.2, report 1.0, manifest 1.3, frontmatter 1.0`
- directly_verified:
  - `Schemas use Draft 2020-12 and ship in the wheel.`
  - `Schema/model cross-check tests pass.`
  - `Tests cover a schema-1.0 manifest record and pre-1.2 missing-source_root behavior.`
  - `Apply explicitly rejects an unusable pre-1.1 plan and instructs regeneration.`
- residual_risk: `Compatibility evidence uses synthetic historical shapes rather than downloaded prior-release artifacts, but no concrete release blocker was found.`

## Quality Signal And Observability Confidence

- direct_results:
  - `ruff format --check`: passed for Python files.
  - `ruff check`: passed.
  - `coverage run -m pytest`: 619 passed, 1 opt-in scale test skipped.
  - `coverage report`: 97%, above the 85% gate.
  - `scripts/check_traceability.py`: passed.
- environment_limited_results:
  - `basedpyright` could not resolve installed third-party packages in this child sandbox despite successful Python imports; the repo's 2026-07-10 session record reports a direct 0-error/0-warning pass on the same HEAD. Treat current direct type-check verification as inconclusive, not failed.`
  - `pip-audit` could not reach PyPI because sandbox DNS is disabled; the 2026-07-10 session record reports a clean audit on the same HEAD. A candidate release still needs a fresh online result.`
  - `project-standards spec validation via uvx could not fetch its pinned Git source; the local global CLI is a different command generation. The 2026-07-10 session record reports the spec gate green.`
- observability_assessment: `Application run observability is ready; release observability and post-publish monitoring are incomplete under ISSUE-006.`

## Release Automation And Governance Gaps

- blocking: `ISSUE-002, ISSUE-003`
- non_blocking_after_blockers: `ISSUE-007`
- external_controls_to_verify:
  - `main branch required checks and admin enforcement`
  - `signed commits and signed/annotated tag policy`
  - `tag rulesets preventing delete/move and constraining creators`
  - `protected release environment and required reviewers`
  - `immutable GitHub Releases`
  - `Actions default token permissions and allowed-Actions policy`

## Post-Release Verification And Monitoring Window

- current_state: `not-defined`
- required_minimum:
  1. `Download the published wheel and sdist by tag.`
  2. `Verify digest and provenance identity.`
  3. `Install the wheel into a clean Python 3.14 environment.`
  4. `Run version/help/schema-resource checks and a synthetic scan-plan-apply-restore-verify journey.`
  5. `Compare GitHub Release tag commit, generated notes/changelog, and artifact version.`
  6. `Observe the workflow/release and first staged field run for a named window before widening library exposure.`
- owner_needed: `Define the observation window and who may declare the release promoted or withdrawn.`
- gap: `ISSUE-006`

## Release Validation And Smoke-Test Gaps

- present: `lock freshness, source quality gate on PR/main, sdist+wheel build, isolated wheel --version smoke`
- missing:
  - `candidate identity checks`
  - `clean installed-wheel contract journey`
  - `packaged schema/resource assertion in automation`
  - `artifact digest/provenance/SBOM generation and verification`
  - `post-publish download and verification`
  - `no-change and changelog-version rejection`
- findings: `ISSUE-001, ISSUE-002, ISSUE-004, ISSUE-005, ISSUE-007`

## Convention Recommendations

### Cross-Project Defaults

1. `A release tag must be annotated/signed, authorized, on the intended protected branch, and equal to package/runtime/changelog versions.`
2. `Build/test runs read-only; a separate protected publish job receives only the already-tested artifact and narrowly scoped write permission.`
3. `All non-local Actions and reusable workflows use full commit SHAs; build tools use explicit versions.`
4. `Every distributed executable artifact receives a clean-install contract smoke, digest, provenance attestation, and dependency inventory.`
5. `Every release has a pre-tag checklist, post-publish verification, monitoring window, withdrawal procedure, and separate data-recovery procedure.`

### Repo-Specific Exceptions

- `PyPI publishing is not needed for v1; GitHub Release wheel/sdist delivery is the approved scope.`
- `Service deployment, database migrations, health endpoints, blue/green deployment, and service canaries are not needed for this repo.`
- `The canary is an include-filtered library subset promoted via the reviewed plan artifact.`
- `Linux/POSIX and Python 3.14+ are the declared runtime contract; a cross-platform matrix should not be forced without a scope change.`
- `The 100k scale test may remain opt-in, but release policy should require rerunning it for performance, memory, discovery, planning, or writer changes.`

### Existing Convention Quality

- `docs/handoff/conventions.md` is strong for Python, Markdown, specification, public-data, and standard-owned-file discipline.
- `adr-0017` and README describe the release topology but do not define enforceable candidate identity, artifact provenance, post-publish verification, or bad-release response.
- `Add release conventions through the approved ADR/spec/standard process; do not hand-edit standard-owned workflows to bypass checks.`

## Pass Log

| Pass | Lens | New issues | Outcome |
| --: | --- | --- | --- |
| 1 | Release inventory, candidate identity, packaging, deploy path, rollback posture | ISSUE-001, ISSUE-002 | Current HEAD is not a versioned candidate; tag publication predicates are not enforced |
| 2 | Tests, contracts, configuration, exact-artifact confidence, observability | ISSUE-004 | Source confidence is high; installed-artifact release testing is too shallow |
| 3 | Governance, environment protection, privileged automation, provenance, supply chain | ISSUE-003, ISSUE-005 | Privileged build chain and asset provenance are not release-grade |
| 4 | Lower-severity friction, documentation drift, release notes, post-release window | ISSUE-006, ISSUE-007 | Bad-release response and no-change/changelog controls are incomplete |
| 5 | Adaptive deepening: historical artifact compatibility, recovery semantics, package contents | None | No new issue; existing compatibility and recovery evidence is adequate |
| 6 | Convergence: recheck issue boundaries, false positives, not-applicable categories, baseline comparison | None | Second consecutive no-new-issue pass; review converged |

## Claude Handoff

- ship_decision: `not-ready-for-a-new-release-from-current-head`
- first_fix_batch: `ISSUE-001 and ISSUE-002: establish candidate version/tag/main/signature/changelog identity`
- second_fix_batch: `ISSUE-003: immutable pins, explicit uv version, read-only build job, protected write publish job`
- third_fix_batch: `ISSUE-004 and ISSUE-005: exact-artifact contract smoke, digests, provenance, SBOM`
- fourth_fix_batch: `ISSUE-006 and ISSUE-007: release checklist, verification window, rollback/withdrawal, no-change/changelog checks`
- retain_as_is:
  - `product dry-run and safety gate`
  - `manifest/backup restore model`
  - `resume and verify contracts`
  - `versioned packaged schemas`
  - `staged include-filtered library rollout`
- do_not_assume:
  - `that --verify-tag verifies a signature`
  - `that branch protection also protects tags`
  - `that source-checkout tests prove the shipped wheel`
  - `that reinstalling an old package restores already-mutated documents`
  - `that external GitHub settings match README claims without verification`

## Open Questions Or Assumptions

1. `Is a new release intended now? If yes, what is the target version and scope?`
2. `Are GitHub tag rulesets configured to require authorized, signed, immutable version tags?`
3. `Is a protected release environment with required reviewers configured externally?`
4. `Is immutable GitHub Releases enabled, and do existing releases have verifiable release or asset attestations?`
5. `Did all required checks pass on the exact intended candidate commit?`
6. `Who owns post-release verification, what is the monitoring window, and what event triggers withdrawal?`
7. `Can a fresh online vulnerability and license audit be captured immediately before tagging?`
8. `Has the manual restore drill required before the first real-library apply been performed on the owner's actual preservation setup?`

## Residual Risk

- overall: `medium-after-high-blockers-are-fixed; high-while-current-release-automation-remains-unchanged`
- strongest_controls: `application safety gates, atomic writer, backup/manifest recovery, resume, verification, schema contracts, broad automated tests`
- dominant_residuals: `external GitHub governance unknowns, release artifact identity/provenance, post-publish verification, first real-library evidence`
- not_applicable: `service deployment, database migrations, remote API rollout, container/image release, orchestration, canary traffic, health checks`
- release_condition: `Resolve ISSUE-001 through ISSUE-003, rerun the complete online gate on the exact candidate, and record external GitHub protections before tagging.`
