# CI/CD Review Report

## Findings

### ISSUE-001 — Tag releases are not bound to protected `main`, the package version, or the full gate

- first_pass: 1
- severity: high
- confidence: high
- ci_cd_area: release-versioning-and-publishing
- issue_type: release-publishing-gap
- evidence_status: verified-repo
- evidence:
  - `.github/workflows/release.yml:7-42` runs for every tag matching `v*.*.*`, immediately builds and publishes it.
  - The workflow does not verify that `GITHUB_SHA` is reachable from `origin/main`, that the tag is annotated and signed, or that the tag version equals `pyproject.toml` / `docmend.__version__`.
  - `gh release create --verify-tag` only requires the remote tag to exist; it does not establish main ancestry, signature validity, version equality, or prior check success.
  - The release job does not run or depend on `check`, Markdown lint, spec validation, traceability, or dependency review.
  - `README.md:97-103`, `docs/specs/docmend.md:924-930`, and `docs/adr/adr-0017-branch-and-ci-cd-workflow.md` require releases to be signed tags on `main` after the verification gate.
- impact: A matching tag on an unreviewed commit can produce an official GitHub Release; a mistyped tag can also label artifacts whose embedded version differs from the release name. Repository branch protection does not protect tags or prove ancestry by itself.
- recommendation: Add a release preflight that fetches full history, requires the tagged commit to be an ancestor of current `origin/main`, verifies the annotated tag signature, compares `vX.Y.Z` with all package version sources, and runs or cryptographically reuses the complete gate for that exact SHA before publication. Treat external tag rules as defense in depth, not the only binding.
- external_basis: [GitHub push tag/branch filter semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushbranchestagsbranches-ignoretags-ignore)

### ISSUE-002 — Most Actions and reusable workflows use mutable tags

- first_pass: 2
- severity: high
- confidence: high
- ci_cd_area: supply-chain-and-third-party-automation
- issue_type: automation-supply-chain-gap
- evidence_status: verified-repo
- evidence:
  - Mutable references include `actions/checkout@v7`, `actions/setup-python@v6`, `actions/dependency-review-action@v5`, and both `L3DigitalNet/project-standards/...@v4` reusable workflows.
  - `.github/workflows/release.yml:19` executes mutable `actions/checkout@v7` in the job holding `contents: write`.
  - `.github/workflows/validate-specs.yml:14` also passes mutable `standards-ref: "v4"` to remotely controlled validation logic.
  - Only `astral-sh/setup-uv` is pinned to a full commit SHA.
- impact: Moving or compromised upstream tags can change executable CI code without a repository commit. In the release job this can affect a write-capable token and the bytes published as official artifacts; in required-check workflows it can forge or disable merge evidence.
- recommendation: Pin every non-local Action and reusable workflow to a full commit SHA with a trailing release comment, including `actions/*` and both Project Standards references. Keep Dependabot updating SHA pins. Because several callers are standard-owned under convention 8, fix their source bundle/upstream standard or record an explicit ADR exception rather than silently hand-editing around ownership.
- external_basis: [GitHub secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use)

### ISSUE-003 — Published distributions are not tested as the complete installable release contract

- first_pass: 2
- severity: medium
- confidence: high
- ci_cd_area: artifact-build-and-integrity
- issue_type: artifact-integrity-gap
- evidence_status: verified-repo
- evidence:
  - `.github/workflows/check.yml:29-48` tests the source checkout after `uv sync`, not an installed release artifact.
  - `.github/workflows/release.yml:28-33` builds an sdist and wheel but smoke-tests only the wheel with `docmend --version`.
  - No pipeline builds a wheel from the generated sdist, inspects both archives, verifies packaged JSON Schemas / `py.typed`, or runs CLI and schema contract tests from a clean installation.
  - The sdist is published despite receiving no release-job test.
- impact: Packaging omissions, broken sdist builds, missing schema data, or entry-point/runtime failures beyond `--version` can pass source tests and be attached to a release.
- recommendation: Build once, inspect both archives, build a wheel from the sdist, install the resulting wheel into a clean isolated environment, and run representative CLI plus packaged-schema contract tests against those exact bytes. Publish only the already-tested artifacts.
- external_basis: [PyPA packaging flow](https://packaging.python.org/en/latest/flow/), [uv package builds](https://docs.astral.sh/uv/guides/package/)

### ISSUE-004 — Release build tooling is not reproducibly pinned

- first_pass: 2
- severity: medium
- confidence: high
- ci_cd_area: build-reproducibility-and-determinism
- issue_type: build-determinism-gap
- evidence_status: verified-repo
- evidence:
  - `.github/workflows/check.yml:24-27` pins the uv executable to `0.11.6`; `.github/workflows/release.yml:26` omits the `version` input.
  - `pyproject.toml:45` allows any `uv_build>=0.11,<0.12`.
  - `uv.lock` contains no `uv_build` package, so the isolated build backend is not part of the checked development resolution.
  - `.github/workflows/release.yml:29` runs plain `uv build` without a build constraint or equivalent backend lock.
- impact: Re-running the same tag later can select different uv frontend or build-backend code and produce behavior or bytes that were not used by CI.
- recommendation: Pin the uv executable in release, constrain the isolated build backend through an auditable locked/constraint input, and record the toolchain versions in release evidence. Retain `uv sync --locked --all-groups` for the source gate.
- external_basis: [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/), [uv in GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/)

### ISSUE-005 — The Python dependency-review license gate depends on unverified `uv.lock` ingestion

- first_pass: 2
- severity: medium
- confidence: medium
- ci_cd_area: supply-chain-and-third-party-automation
- issue_type: pipeline-coverage-gap
- evidence_status: verified-repo-plus-external-unknown
- evidence:
  - `.github/workflows/dependency-review.yml:3-6` states that GitHub's dependency graph resolves `uv.lock` natively, including license metadata.
  - Current GitHub dependency-graph documentation does not list `uv.lock` as a supported or recommended pip manifest/lock file; its pip row names `requirements.txt` and `pipfile.lock`, while Poetry is separate.
  - The repository has no dependency-submission workflow or deterministic local license gate over the locked environment.
  - The authenticated dependency-graph SBOM could not be queried in this review, so actual repository ingestion remains unverified.
- impact: A PR can receive a green required `dependency-review` check while Python dependency/license deltas are absent or incomplete in the graph. The allowlist then protects less than the ADR and workflow comments claim.
- recommendation: Verify the live dependency graph/SBOM for a known `uv.lock` delta. If coverage is incomplete, submit the resolved uv graph through GitHub's dependency-submission API or run a deterministic license-compliance tool against the locked environment in CI. Change the comments and ADR confirmation language to match demonstrated coverage.
- external_basis: [GitHub dependency-graph ecosystem support](https://docs.github.com/en/code-security/reference/supply-chain-security/dependency-graph-supported-package-ecosystems), [dependency submission for unsupported inputs](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/enable-dependency-graph)

### ISSUE-006 — Reusable workflow callers inherit unverified default token permissions

- first_pass: 3
- severity: medium
- confidence: medium
- ci_cd_area: secret-handling-and-identity
- issue_type: secret-identity-gap
- evidence_status: verified-repo-plus-external-unknown
- evidence:
  - `.github/workflows/lint-markdown.yml` and `.github/workflows/validate-specs.yml` define no workflow- or job-level `permissions`.
  - GitHub gives a called reusable workflow the caller repository's default `GITHUB_TOKEN` permissions when the calling job does not specify them.
  - The repository's default workflow permission setting could not be queried because GitHub CLI authentication is unavailable in this environment.
- impact: If the external repository default is write-capable, remote reusable workflows receive broader repository authority than lint/spec validation needs.
- recommendation: Set explicit `contents: read` permissions on both callers and confirm repository default workflow permissions are read-only with PR approval disabled. Route standard-owned caller changes through Project Standards or a documented exception.
- external_basis: [GitHub reusable-workflow permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations), [least-privilege `GITHUB_TOKEN`](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token)

### ISSUE-007 — Resolved-environment vulnerability auditing has no periodic trigger

- first_pass: 4
- severity: medium
- confidence: high
- ci_cd_area: supply-chain-and-third-party-automation
- issue_type: pipeline-coverage-gap
- evidence_status: verified-repo
- evidence:
  - `pip-audit` runs only in `.github/workflows/check.yml`, whose triggers are pull requests and pushes to `main`.
  - No workflow has a `schedule` trigger for auditing the current locked dependency closure after publication.
  - Dependabot is scheduled weekly, but dependency-graph coverage for `uv.lock` is not established by repo evidence (ISSUE-005), and version-update automation is not the same evidence as auditing the exact locked environment.
- impact: A newly disclosed vulnerability can remain undetected in an otherwise inactive repository and released CLI until another PR or main push occurs.
- recommendation: Add a scheduled locked-environment audit using the convention-owned `pip-audit` gate, preserve its output without sensitive data, and define how failures are surfaced and triaged. Keep PR dependency review as a separate delta gate.

### ISSUE-008 — Release assets lack repository-defined provenance, attestations, or checksums

- first_pass: 4
- severity: medium
- confidence: medium
- ci_cd_area: provenance-attestations-and-immutability
- issue_type: provenance-immutability-gap
- evidence_status: verified-repo-plus-external-unknown
- evidence:
  - `.github/workflows/release.yml` uploads `dist/*` directly with no checksum manifest, artifact attestation, or provenance generation/verification.
  - Historical release tags are annotated and contain signatures; this authenticates the tag but does not bind the hosted build environment and generated artifact bytes to a provenance statement.
  - GitHub immutable-release settings and any platform-generated release attestations could not be verified without authenticated repository settings/run access.
- impact: Consumers cannot use repository-defined evidence to verify that a downloaded wheel/sdist was produced from the expected commit by the expected workflow, and mutable-release protections remain an external assumption.
- recommendation: Generate checksums and GitHub artifact/build-provenance attestations for the tested artifacts, verify them before publication, and enable/confirm immutable GitHub Releases. Use narrowly scoped job permissions and pin any attestation Actions by full SHA.
- external_basis: [GitHub immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases), [SLSA build provenance](https://slsa.dev/spec/v1.2/build-track-basics)

### ISSUE-009 — Superseded pull-request runs are not cancelled

- first_pass: 5
- severity: low
- confidence: high
- ci_cd_area: cost-concurrency-and-runner-efficiency
- issue_type: cost-concurrency-gap
- evidence_status: verified-repo
- evidence:
  - None of the five PR workflows defines `concurrency`.
  - A force-push or new commit to the `dev -> main` PR can leave obsolete check, lint, spec, traceability, and dependency-review runs consuming runners concurrently.
- impact: This increases runner cost and failure noise. It does not bypass required checks because GitHub associates required results with the current head SHA.
- recommendation: Add workflow/ref- or workflow/PR-keyed concurrency with `cancel-in-progress: true` for non-release workflows. Do not cancel an in-progress release merely because a different tag appears.

### ISSUE-010 — The documented local gate does not cover all repo-verifiable required checks

- first_pass: 5
- severity: low
- confidence: high
- ci_cd_area: documentation-and-operator-ergonomics
- issue_type: operator-ergonomics-gap
- evidence_status: verified-repo
- evidence:
  - `README.md:83-93` says direct `dev` pushes do not run CI and instructs contributors to run the local verification gate.
  - That command list and `scripts/check.py` include only format, lint, type, pytest/coverage, and `pip-audit`.
  - The required PR graph also includes Markdown lint, spec validation, traceability, and dependency review; the first three are locally runnable but absent from the aggregate instruction/script.
- impact: In the intentionally CI-free `dev` workflow, repository-document failures are discovered only after opening the promotion PR, creating avoidable late feedback and weakening the claimed local/CI mirror.
- recommendation: Provide a repo-owned aggregate pre-PR command that runs the Python gate plus Prettier/markdownlint, spec validation, and traceability. Clearly label dependency review as GitHub/external unless a local equivalent is added. Do not repurpose the standard-owned Python-only twin in `scripts/check.py`.

## Review Metadata

- repo_root: `.`
- repo_name: `docmend`
- review_type: `ci-cd-review`
- reviewed_at: `2026-07-10`
- current_branch: `dev`
- head_commit: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- working_tree_state_at_start: `dirty; M AGENTS.md; ?? docs/codex-reviews/`
- working_tree_ownership_note: `AGENTS.md and existing docs/codex-reviews artifacts were pre-existing and not modified by this review`
- detected_ci_or_automation_platforms: `GitHub Actions; Dependabot; GitHub Releases`
- workflow_pipeline_release_surfaces_inspected: `.github/workflows/check.yml; dependency-review.yml; lint-markdown.yml; release.yml; traceability.yml; validate-specs.yml; .github/dependabot.yml; pyproject.toml; uv.lock; scripts/check.py; scripts/check_traceability.py`
- conventions_inputs_inspected: `docs/handoff/conventions.md; docs/adr/adr-0017-branch-and-ci-cd-workflow.md; README.md; docs/specs/docmend.md`
- branch_protection_required_check_surfaces_inspected: `ADR/README declarations and workflow job names; live settings unavailable without GitHub authentication`
- self_hosted_or_runner_isolation_surfaces_inspected: `all repository jobs use GitHub-hosted ubuntu-latest; no self-hosted runner configuration found`
- deployment_or_publish_surfaces_inspected: `tag-triggered GitHub Release; PyPI and service deployment are explicitly out of scope`
- package_or_artifact_outputs_reviewed: `sdist; pure-Python wheel; five packaged JSON Schemas; py.typed; GitHub Release assets`
- provenance_attestation_or_release_immutability_surfaces_reviewed: `signed tag history; release workflow; no repo-defined attestations/checksums; live immutable-release setting unavailable`
- artifact_or_log_retention_surfaces_reviewed: `GitHub Release assets; no CI artifact uploads; live Actions log retention unavailable`
- cache_or_dependency_bootstrap_surfaces_reviewed: `setup-uv cache in check; uv sync --locked --all-groups; uncached/unpinned release uv; Dependabot; pip-audit`
- environment_or_approval_surfaces_reviewed: `no GitHub environment referenced; live environments/reviewers unavailable`
- important_external_ci_cd_surfaces_not_in_repo: `branch protection; tag rules; Actions allowlist; default token permissions; environments; immutable releases; dependency graph/SBOM; workflow run history; log retention`
- prior_baseline_or_release_artifacts_compared: `v1.0.2 tag and origin/main; no CI/release workflow diff from v1.0.2 to HEAD; findings are baseline posture, not a post-release regression`
- research_reused: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
- targeted_follow_up_research: `official GitHub token/reusable-workflow semantics, tag trigger semantics, and dependency-graph supported files only`
- default_exclusions_applied: `dist output, caches, generated artifacts, bulky fixtures, and coverage output excluded except where packaging/CI evidence required inspection`

## CI/CD Area Matrix

| ci_cd_area | applicability | posture | issue_ids | evidence_scope |
| --- | --- | --- | --- | --- |
| pipeline-coverage-and-required-checks | applicable | gaps | ISSUE-001, ISSUE-005, ISSUE-007 | repo verified; live required checks unverified |
| build-reproducibility-and-determinism | applicable | gap | ISSUE-004 | repo verified |
| test-gating-and-failure-propagation | applicable | partial | ISSUE-001, ISSUE-003 | source gate strong; release binding weak |
| cache-and-dependency-bootstrap | applicable | adequate-with-unknowns | ISSUE-004 | check cache/locked sync sound; release differs |
| artifact-build-and-integrity | applicable | gap | ISSUE-003 | repo verified |
| provenance-attestations-and-immutability | applicable | gap/unverified-external | ISSUE-008 | repo verified; platform settings unknown |
| release-versioning-and-publishing | applicable | gap | ISSUE-001 | repo verified |
| deploy-governance-and-approvals | GitHub Release only | partial | ISSUE-001 | no service deploy; tag governance external |
| environment-separation-and-promotion | not needed for this repo | not needed for this repo | none | local CLI; no dev/stage/prod runtime |
| secret-handling-and-identity | applicable | partial | ISSUE-006 | no long-lived secret refs; token defaults unknown |
| runner-trust-and-isolation | applicable | adequate | none | GitHub-hosted only; no untrusted privileged trigger |
| branch-protection-and-change-controls | applicable | unverified-external | ISSUE-001, ISSUE-005 | ADR declares strong protection; live settings unavailable |
| rollback-and-recovery | applicable | adequate | none | install previous release; product data recovery separately documented |
| pipeline-observability-and-debuggability | applicable | partial/unverified | ISSUE-007 | Actions logs external; retention/alerts unknown |
| cost-concurrency-and-runner-efficiency | applicable | gap | ISSUE-009 | repo verified |
| documentation-and-operator-ergonomics | applicable | gap | ISSUE-010 | repo verified |
| workflow-governance-and-reuse | applicable | partial | ISSUE-002, ISSUE-006 | reusable standards workflows, but mutable/default-authority risks |
| supply-chain-and-third-party-automation | applicable | gaps | ISSUE-002, ISSUE-005, ISSUE-007 | repo verified plus dependency graph unknown |

## Severity Summary

| severity | count | issue_ids                                                        |
| -------- | ----: | ---------------------------------------------------------------- |
| critical |     0 | none                                                             |
| high     |     2 | ISSUE-001, ISSUE-002                                             |
| medium   |     6 | ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-006, ISSUE-007, ISSUE-008 |
| low      |     2 | ISSUE-009, ISSUE-010                                             |
| total    |    10 | ISSUE-001 through ISSUE-010                                      |

## Pipeline Graph And Trigger Risks

| trigger | workflows/jobs | gate/publish role | principal risk |
| --- | --- | --- | --- |
| `pull_request` | check; dependency-review; lint-markdown; validate-specs; traceability | intended five-check promotion gate | mutable automation; dependency graph coverage unknown; no stale-run cancellation |
| `push` to `main` | check; lint-markdown; validate-specs; traceability | post-push verification | dependency-review absent by design; live direct-push protection unverified |
| `push` to `dev` | none | accepted ADR deviation; local gate expected | late feedback because local aggregate omits document/spec gates |
| `push` tag `v*.*.*` | release only | build and publish GitHub Release | not bound to main/version/full gate; write-capable mutable checkout |

- path_filter_risk: `none found; protective workflows use no path filters or conditional no-op guards`
- required_check_name_risk: `ADR names five contexts; exact live context configuration could not be authenticated`
- high_risk_boundary: `tag event -> checkout/build -> GitHub Release under contents:write`

## Build, Artifact, And Retention Integrity

- build_frontend: `uv; pinned in check, unpinned in release`
- build_backend: `uv_build>=0.11,<0.12; not present in uv.lock`
- source_gate: `uv sync --locked --all-groups; Ruff; BasedPyright strict; pytest/coverage; pip-audit`
- artifact_gate: `wheel --version smoke only`
- sdist_tested: `no`
- wheel_built_from_sdist: `no`
- installed_package_contract_tested: `partial; version only`
- package_data_integrity_tested_in_release: `no`
- artifact_promotion: `single build is uploaded directly, which avoids rebuild drift but does not compensate for incomplete artifact tests`
- artifact_retention: `GitHub Release assets; live immutability/retention settings unverified`
- ci_artifact_retention: `not needed for this repo; workflows upload no transient build/test artifacts`

## Provenance And Supply Chain Integrity

- action_pinning: `one Action SHA-pinned; all other actions/reusable workflows mutable`
- dependency_locking: `runtime/dev closure locked; isolated build backend not locked`
- dependency_delta_review: `configured, but uv.lock ingestion unverified`
- vulnerability_scan: `pip-audit on PR/main activity only`
- release_provenance: `signed tags documented/historical; no repo-defined artifact attestation or checksums`
- release_immutability: `external GitHub setting unknown`
- pypi_trusted_publishing: `not needed for this repo; PyPI explicitly out of scope`

## Release And Deploy Governance

- release_target: `GitHub Releases only`
- release_actor: `GITHUB_TOKEN with contents:write`
- protected_environment: `none referenced; not necessarily required for a single-owner GitHub Release, but live approval settings are unknown`
- version_binding: `missing`
- main_ancestry_binding: `missing`
- signed_tag_enforcement_in_workflow: `missing`
- full_gate_binding: `missing`
- service_deployment: `not needed for this repo`
- database_migration: `not needed for this repo`

## Runner Trust And Isolation

- runner_type: `GitHub-hosted ubuntu-latest`
- self_hosted_runners: `not found; not needed for this repo`
- untrusted_privileged_triggers: `no pull_request_target or privileged workflow_run found`
- fork_secret_exposure: `no repository secret references found`
- runner_image_determinism: `ubuntu-latest is mutable, but artifacts are pure Python; secondary to unpinned build tooling`
- assessment: `adequate after fixing automation pinning and release-token scope`

## Secret And Identity Risks

- long_lived_secrets: `none referenced`
- oidc: `not needed for current GitHub-only publishing`
- default_token_posture: `explicit contents:read in check, traceability, dependency-review; omitted in reusable-workflow callers; contents:write in release`
- token_exposure_note: `GitHub documents that Actions can access github.token even when not explicitly passed; the release job therefore gives every Action in that job the effective write-capable token context`
- external_unknowns: `repository default token permission; Actions allowlist; environment reviewers`

## Environment Promotion And Recovery

- runtime_environment_promotion: `not needed for this repo; local CLI`
- release_promotion_unit: `wheel/sdist attached directly to tagged GitHub Release`
- package_rollback: `install prior release artifact/tag; documented`
- corpus_recovery: `product manifests/backups/restore runbooks; outside package-delivery mechanics but reviewed as supporting evidence`
- rollback_gap: `a package rollback cannot undo files already mutated; existing product recovery model addresses that separately`

## Pipeline Reliability And Cost

- cache: `setup-uv cache enabled in check with lock-aware project inputs; no release cache, reasonable for infrequent releases`
- failure_propagation: `shell steps use default fail-fast; no continue-on-error found`
- no_op_risk: `dependency-review can be green on incomplete dependency graph evidence`
- concurrency: `no cancellation groups; low-severity duplicate-run cost/noise`
- scheduled_health: `no periodic locked vulnerability audit`
- local_validation_observed:
  - `workflow/dependabot YAML parse: pass`
  - `uv lock --check: pass with temporary sandbox cache`
  - `Ruff format check: pass`
  - `Ruff lint: pass`
  - `pytest/coverage with temporary XDG state: 619 passed, 1 opt-in scale skip, 97%`
  - `traceability: pass`
  - `BasedPyright: inconclusive in child-review sandbox; it omitted the active venv site-packages and produced cascading unresolved-import errors; same HEAD is documented as 0/0/0 earlier on 2026-07-10`
  - `pip-audit: inconclusive; sandbox DNS cannot resolve pypi.org`

## Operator Ergonomics And Drift

- source_vs_ci_commands: `Python commands align between scripts/check.py and check.yml`
- complete_local_vs_pr_gate: `does not align; Markdown/spec/traceability omitted locally`
- workflow_comments: `generally strong, but dependency-review's uv.lock support claim is not backed by current GitHub documentation`
- baseline_drift: `no .github/pyproject/uv.lock/release diff from v1.0.2 to HEAD`
- external_drift_detection: `Dependabot covers pip and github-actions weekly; immutable SHA policy is not consistently applied`

## Convention Recommendations

### Shared Across Projects

- Pin every external Action and reusable workflow to a full commit SHA; keep automated SHA updates.
- Give every workflow/calling job explicit least-privilege token permissions and keep repository defaults read-only.
- Bind releases to source SHA, version, completed gates, exact tested artifacts, checksums, and provenance.
- Run a periodic audit of the resolved dependency closure, separate from PR dependency-delta review.
- Cancel superseded non-release PR runs by workflow and PR/ref.

### Repo-Specific

- Preserve the accepted `dev -> PR -> main` model, but add one repo-owned aggregate pre-PR gate because `dev` intentionally has no push CI.
- Verify tag main ancestry, annotated signature, and `vX.Y.Z == pyproject/__version__` before GitHub Release creation.
- Demonstrate `uv.lock` dependency-graph coverage or install an explicit uv dependency-submission/license gate.
- Keep PyPI/OIDC, service deployment, staging environments, self-hosted runners, and database migrations marked `not needed for this repo` unless scope changes.

### Convention Quality

- conventions_alignment: `partial`
- sound_conventions: `locked uv sync, Python tool SSOT, documented five-check main gate, signed-tag release intent, standard-owned-file discipline`
- convention_misalignment: `mutable Action tags conflict with current secure-use guidance; release workflow does not enforce the signed-main-tag/full-gate contract`
- stale_or_overstated_rationale: `ADR calls the five-check gate airtight and dependency-review comments claim native uv.lock coverage; both depend on external evidence not established in repo`
- ownership_constraint: `standard-owned workflows require an upstream Project Standards change or explicit ADR exception; do not bypass convention 8`

## Pass Log

| pass | lens | new_issue_ids | result |
| --: | --- | --- | --- |
| 1 | inventory, graph, triggers, required checks, release boundary | ISSUE-001 | tag publication boundary not bound to main/gate/version |
| 2 | cache, reproducibility, artifacts, action pinning, convention alignment | ISSUE-002, ISSUE-003, ISSUE-004, ISSUE-005 | mutable automation and build/dependency evidence gaps |
| 3 | secrets, token identity, approvals, runner trust, governance | ISSUE-006 | reusable callers inherit unknown defaults; no self-hosted/untrusted privileged trigger |
| 4 | provenance, retention, periodic reliability, rollback, observability | ISSUE-007, ISSUE-008 | scheduled audit and artifact provenance gaps |
| 5 | lower-severity cost, developer experience, baseline comparison | ISSUE-009, ISSUE-010 | concurrency and local-gate ergonomics gaps |
| 6 | adaptive deepening: release history, signed tag, current-vs-v1.0.2 diff | none | no new issues |
| 7 | convergence: area matrix, anti-pattern replay, external-unknown separation | none | second consecutive no-new-issue pass; review converged |

## Claude Handoff

- priority_1: `ISSUE-001 — make release publication prove main ancestry, signed/version-matched tag, and complete gate success for the exact SHA`
- priority_2: `ISSUE-002 — SHA-pin every Action/reusable workflow, addressing standard-owned sources correctly`
- priority_3: `ISSUE-003 and ISSUE-004 — build/test the exact sdist/wheel contract with pinned build tooling`
- priority_4: `ISSUE-005 and ISSUE-006 — verify dependency graph and repository token defaults before trusting current external controls`
- priority_5: `ISSUE-007 and ISSUE-008 — add scheduled resolved auditing and release provenance/immutability evidence`
- safe_batch: `ISSUE-009 and ISSUE-010 can be handled as a low-risk CI ergonomics change after governance decisions`
- follow_on_reviews: `dependency-supply-chain-review for lock/SBOM/license depth; release-readiness-review for artifact compatibility and consumer install evidence; security review for workflow-token threat modeling`
- change_control_note: `Workflow files are covered by convention 8; use upstream Project Standards changes or an ADR-backed exception where applicable.`
- implementation_status: `review only; no fixes applied`

## Open Questions Or Assumptions

- Does live `main` protection still require all five exact contexts, strict updates, signatures, conversations, PRs, and admin enforcement as ADR 0017 states?
- Are matching release tags protected against deletion/rewrite and restricted to the owner? Is signed-tag enforcement automated anywhere?
- Is the repository default `GITHUB_TOKEN` permission read-only, and can Actions approve pull requests?
- Is an Actions/reusable-workflow allowlist configured?
- Does the live dependency graph/SBOM contain the full direct and transitive `uv.lock` resolution with license metadata?
- Are GitHub immutable releases enabled, and do current releases have platform-generated attestations?
- What Actions log/artifact retention period is configured?
- Do the v1.0.2 release and all required-check runs show the exact expected workflow SHAs and successful results? Public/authenticated run retrieval was unavailable here.
- BasedPyright could not resolve the active venv's third-party packages inside this child-review sandbox. The same HEAD's handoff session records a clean run earlier on 2026-07-10; verify once in a normal shell or GitHub-hosted run before treating it as a project regression.

## Residual Risk

- highest_residual_risk: `official release creation trusts a matching tag and mutable automation more than the documented governance contract permits`
- external_control_risk: `several conclusions depend on unauthenticated GitHub settings that repository files cannot prove`
- artifact_risk: `source tests are strong, but published sdist/wheel and their provenance are not fully established`
- dependency_risk: `locked bootstrap is strong; delta-license and post-publication vulnerability coverage are not demonstrated end to end`
- accepted_repo_specific_tradeoff: `no dev push CI; reasonable only while the protected PR gate and a complete local pre-PR gate remain reliable`
- no_findings_for: `self-hosted runner isolation, service deployment, environment promotion, cloud credentials/OIDC, database migration, container deployment; not needed for this repo`
