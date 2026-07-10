# Dependency And Supply-Chain Review

## Review Metadata

- repo_path: `.`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- working_tree_state: `dirty`; pre-existing `AGENTS.md` modification and orchestrator artifacts under `docs/codex-reviews/` were preserved
- review_date: `2026-07-10`
- review_mode: `read-only except for this requested report`
- conventions_input: `docs/handoff/conventions.md`
- governing_dependency_inputs: `pyproject.toml`, `uv.lock`, `docs/specs/docmend.md` section 8.6, `docs/adr/adr-0013-v1-dependency-selection.md`, `docs/adr/adr-0017-branch-and-ci-cd-workflow.md`, and `docs/dependency-licenses.md`
- shared_research_reused: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
- targeted_follow_up_research: [GitHub dependency-graph ecosystem support](https://docs.github.com/en/code-security/reference/supply-chain-security/dependency-graph-supported-package-ecosystems), [dependency-review-action configuration](https://github.com/actions/dependency-review-action), [GitHub Action SHA pinning](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/find-and-customize-actions), [GitHub immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases), and [uv package builds](https://docs.astral.sh/uv/guides/package/)
- package_managers_and_artifact_sources: `uv 0.11.6`; PyPI/`files.pythonhosted.org`; GitHub Actions; GitHub reusable workflows; GitHub Releases; ambient `npx`; `uvx` from a GitHub tag
- manifests_and_lockfiles_reviewed: `pyproject.toml`, `uv.lock`
- lock_inventory: `75` package records including `docmend`; `74` third-party records; all lock sources are PyPI registry artifacts with recorded hashes
- direct_runtime_dependencies: `8`
- direct_dev_dependencies: `11`
- build_dependencies: `uv_build>=0.11,<0.12`
- dependency_classes_reviewed: direct, transitive, build-time, dev/test, publish-time, install-time, automation, and runtime-loaded
- container_or_base_image_surfaces: `none found; not needed for this repo`
- automation_or_release_references_reviewed: all six `.github/workflows/*.yml` files and `.github/dependabot.yml`
- registry_and_source_boundaries_reviewed: PyPI, `files.pythonhosted.org`, GitHub Action repositories, `L3DigitalNet/project-standards`, and GitHub Releases
- trusted_publishing_or_provenance_surfaces: GitHub tag-triggered release with `contents: write`; no PyPI publishing; no repository-defined artifact attestation or SBOM publication
- prior_baseline_compared: signed-tag object `v1.0.2`; no dependency-surface diff between `v1.0.2` and `HEAD`
- validation_evidence: `UV_CACHE_DIR=/tmp/docmend-review-uv-cache uv lock --check` passed and resolved 75 records; `uv tree --locked --all-groups --depth 2` completed
- advisory_scan_evidence: `pip-audit` could not reach PyPI because shell network/DNS is restricted; current advisory cleanliness was not independently verified
- critical_external_controls_not_verified: branch protection, tag rules, Actions token defaults, immutable-release setting, release attestations, Dependabot alert state, dependency-graph contents, and GitHub environment reviewers
- evidence_labels: `verified` means direct repository or successful local-command evidence; `inferred` means a conclusion from repository evidence and current official semantics; `unverified-external` means a required hosting control was not available from the repository or unauthenticated environment

## Dependency Area Matrix

| Dependency area | Applicability | Posture | Evidence / issue IDs |
| --- | --- | --- | --- |
| `manifest-lock-alignment` | yes | protected | `uv lock --check` passed; exact hashes in `uv.lock` |
| `dependency-classes-and-inventory` | yes | partial | Runtime/dev separation is clear; build, automation, and ambient tooling are not governed together; ISSUE-002, ISSUE-008 |
| `version-pinning-and-ranges` | yes | partial | Public runtime floors plus exact lock are sound; release tooling and Actions remain mutable; ISSUE-002, ISSUE-004, ISSUE-008 |
| `transitive-risk-visibility` | yes | insufficient | Complete local uv tree exists, but the PR dependency-graph path is not established; ISSUE-003 |
| `update-strategy-and-staleness` | yes | partial | Weekly Dependabot with seven-day cooldown; no repository-visible scheduled audit; ISSUE-007 |
| `vulnerability-and-advisory-posture` | yes | partial | PR/main `pip-audit`; current scan not independently completed; ISSUE-003, ISSUE-007 |
| `package-source-trust` | yes | protected | One public Python index and hash-bearing lock; no direct URLs or custom mirrors found |
| `dependency-confusion-and-private-sources` | yes | protected | No private namespace, alternate index, or unsafe fallback found |
| `provenance-attestation-sbom` | yes | insufficient | No repo-defined release SBOM or attestation; ISSUE-005 |
| `trusted-publishing-and-signing` | yes | insufficient | GitHub Release only; tag-trigger boundary is not enforced in workflow; ISSUE-001 |
| `container-base-images` | no | not needed for this repo | No container or image definitions found |
| `build-time-downloads-and-bootstrap` | yes | insufficient | Release resolves uv/build tooling dynamically; local docs tooling also downloads mutable code; ISSUE-002, ISSUE-008 |
| `ci-actions-plugins-extensions` | yes | partial | Least-privilege permissions in most local jobs; multiple mutable Action/workflow refs; ISSUE-004 |
| `license-and-policy-compliance` | yes | partial | Detailed runtime record and allowlist exist; graph coverage and unknown-license behavior weaken enforcement; ISSUE-003, ISSUE-009 |
| `maintenance-health-and-ownership` | yes | partial | Dependency ADRs and Dependabot exist; quiet-repo advisory drift is not observed in-repo; ISSUE-007 |
| `vendoring-and-forks` | no | not needed for this repo | No vendored or forked dependencies found |
| `runtime-loading-and-plugin-risk` | no | not needed for this repo | No plugin discovery, dynamic entry-point loading, or runtime network fetch found |
| `dependency-observability-and-review-process` | yes | partial | Lock and license records are reviewable; policy gates do not prove complete inventory; ISSUE-003, ISSUE-007, ISSUE-009 |

## Severity Summary

| Severity | Count | Issue IDs                                                        |
| -------- | ----: | ---------------------------------------------------------------- |
| critical |     0 | —                                                                |
| high     |     3 | ISSUE-001, ISSUE-002, ISSUE-003                                  |
| medium   |     6 | ISSUE-004, ISSUE-005, ISSUE-006, ISSUE-007, ISSUE-008, ISSUE-009 |
| low      |     0 | —                                                                |

## Findings

### ISSUE-001: The release tag boundary does not enforce the documented release provenance

- first_pass: `2`
- severity: `high`
- confidence: `medium`
- dependency_area: `trusted-publishing-and-signing`
- issue_type: `trusted-publishing-signing-gap`
- evidence_state: `verified repo behavior; tag-hosting controls unverified-external`
- evidence: `.github/workflows/release.yml:7-12` grants `contents: write` for every pushed tag matching `v*.*.*`; lines 35-42 immediately create a public release. The workflow has no main-ancestry check, tag-signature verification, protected environment, or comparison between the tag and `pyproject.toml` version. `README.md:99-103` documents signed tags on `main`, but that is a human procedure rather than a workflow invariant.
- risk: A write-capable actor who can push a matching tag to an unreviewed commit can bypass the protected-main dependency and code gates and publish release artifacts with the repository token. `gh release create --verify-tag` does not itself provide the missing repository policy evidence in this workflow.
- recommendation: Gate the release job with a protected environment/manual approval; prove that the tagged commit is reachable from `origin/main`; compare `vX.Y.Z` to the package version; and enforce/verify the trusted tag identity. Confirm external tag rules and environment reviewers. Create a draft, attach and validate all assets, then publish, which also aligns with immutable-release guidance.
- follow_on_review: `ci-cd-review` and `release-readiness-review`

### ISSUE-002: The artifact-producing release toolchain is resolved dynamically

- first_pass: `2`
- severity: `high`
- confidence: `high`
- dependency_area: `build-time-downloads-and-bootstrap`
- issue_type: `build-bootstrap-gap`
- evidence_state: `verified`
- evidence: `.github/workflows/check.yml:24-27` pins both `setup-uv` and uv `0.11.6`, but `.github/workflows/release.yml:26-29` pins only the setup Action and omits its `version` input before `uv build`. `pyproject.toml:44-46` declares the build backend as the range `uv_build>=0.11,<0.12`; `uv.lock` has no `uv-build` package record. Thus the privileged build can consume a different uv binary and a newly published build-backend artifact without a source change.
- risk: The tools that determine wheel/sdist contents are not bound to the reviewed lock or to the CI-tested toolchain. A compromised or regressed in-range release can alter published artifacts even when source and runtime lock are unchanged.
- recommendation: Pin the uv executable in the release workflow to the reviewed CI version. Constrain and hash the isolated build environment through a reviewed build constraint or equivalent reproducible-build input while preserving an appropriate public `[build-system]` compatibility bound. Run `uv build --no-sources` for publication and record the exact tool/backend versions in release provenance.
- source: [uv recommends `--no-sources` for publishable builds](https://docs.astral.sh/uv/guides/package/)
- follow_on_review: `release-readiness-review`

### ISSUE-003: The required dependency-review gate has no proven `uv.lock` inventory path

- first_pass: `1`
- severity: `high`
- confidence: `medium`
- dependency_area: `transitive-risk-visibility`
- issue_type: `transitive-visibility-gap`
- evidence_state: `verified repo configuration; GitHub graph contents unverified-external`
- evidence: `.github/workflows/dependency-review.yml:3-6` asserts that GitHub natively resolves `uv.lock`, and the required gate runs only `actions/dependency-review-action` (`:21-51`). The repository has no dependency submission workflow or supported generated lock manifest. Current GitHub dependency-graph documentation lists pip `requirements.txt`/`pipfile.lock` and Poetry `poetry.lock`, but not `uv.lock`. The shared research explicitly flagged this uncertainty. An authenticated graph/SBOM query was unavailable.
- risk: The required status check can report zero added Python dependencies while comparing an empty or partial graph. That would make the stated vulnerability and license controls ineffective for the repository's primary 74-package third-party inventory.
- recommendation: Prove coverage with a controlled PR and inspect the dependency diff/SBOM. If `uv.lock` is not fully represented, submit the locked graph explicitly or generate a supported, hash-bearing manifest from `uv.lock`; keep a separate lock-derived license policy check. Fail when graph snapshots are missing or incomplete rather than accepting zero changes as success.
- source: [GitHub dependency-graph supported ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/dependency-graph-supported-package-ecosystems)
- follow_on_review: `ci-cd-review` and `security-review`

### ISSUE-004: Multiple executable Actions and reusable workflows use mutable tags

- first_pass: `2`
- severity: `medium`
- confidence: `high`
- dependency_area: `ci-actions-plugins-extensions`
- issue_type: `ci-plugin-action-gap`
- evidence_state: `verified`
- evidence: Mutable references include `actions/checkout@v7` in four workflows, `actions/setup-python@v6` in two workflows, `actions/dependency-review-action@v5`, and both `L3DigitalNet/project-standards` reusable workflows at `@v4`. The release checkout runs inside a `contents: write` job. Only `astral-sh/setup-uv` is pinned to a full commit SHA.
- risk: Moving or compromised upstream tags can change code executed in CI without a repository diff. The release job provides the largest blast radius; the standard-owned reusable workflows also sit on required-check trust paths.
- recommendation: Pin every Action and reusable workflow to a reviewed full commit SHA with a trailing version comment and retain Dependabot updates. Because several files are standard-owned under conventions #8, route those changes through the adopted standard or a documented ADR exception rather than bypassing the ownership contract.
- source: [GitHub documents full SHAs as immutable Action references](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/find-and-customize-actions)
- follow_on_review: `ci-cd-review`

### ISSUE-005: Release artifacts have no repository-defined SBOM or verifiable provenance

- first_pass: `2`
- severity: `medium`
- confidence: `medium`
- dependency_area: `provenance-attestation-sbom`
- issue_type: `provenance-sbom-gap`
- evidence_state: `verified repo absence; immutable-release status unverified-external`
- evidence: `.github/workflows/release.yml` attaches only `dist/*`; it has no SBOM export, checksums, `attestations: write`, `id-token: write`, or attestation action. `docs/research/license-compliance-tooling.md` already recommends a release CycloneDX export as a point-in-time provenance artifact. GitHub may generate a release attestation when immutable releases are enabled, but that external repository setting could not be inspected.
- risk: Consumers cannot bind a downloaded wheel/sdist to a reviewed dependency inventory and expected workflow identity using repository-defined evidence. Mutable release assets would further weaken integrity if immutable releases are not enabled.
- recommendation: Export a runtime CycloneDX SBOM from the locked graph, attach it and checksums, generate build provenance for the exact wheel and sdist, and document consumer verification. Enable and verify immutable releases; treat their automatic release attestation as complementary evidence, not as an SBOM.
- source: [GitHub immutable releases and automatic release attestations](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)
- follow_on_review: `release-readiness-review`

### ISSUE-006: The release validates only a wheel version smoke path, not the complete distribution chain

- first_pass: `2`
- severity: `medium`
- confidence: `high`
- dependency_area: `build-time-downloads-and-bootstrap`
- issue_type: `build-bootstrap-gap`
- evidence_state: `verified`
- evidence: `.github/workflows/release.yml:28-33` builds wheel and sdist from the checkout and then runs only `docmend --version` from the wheel. It does not build a wheel from the produced sdist, inspect included package data, install/test both distributions in clean locked environments, or run the dependency and test gate against the exact release artifact.
- risk: Sdist-only defects, wheel/sdist divergence, omitted schemas/package data, and tag-time dependency/toolchain differences can reach a release despite a green source-tree CI run.
- recommendation: Build once, inspect both artifacts, rebuild the wheel from the sdist, compare expected contents, install the exact artifacts in clean environments, and run CLI/schema contract smoke tests plus the release-critical gate before publish. Preserve the tested artifacts for the publish step rather than rebuilding.
- source: [PyPA packaging flow](https://packaging.python.org/en/latest/flow/)
- follow_on_review: `release-readiness-review` and `test-suite-review`

### ISSUE-007: Advisory detection is event-driven and can go stale in a quiet repository

- first_pass: `4`
- severity: `medium`
- confidence: `medium`
- dependency_area: `vulnerability-and-advisory-posture`
- issue_type: `advisory-posture-gap`
- evidence_state: `verified repo behavior; external alert state unverified-external`
- evidence: `.github/workflows/check.yml:3-6,47-48` runs `pip-audit` only for pull requests and pushes to `main`; there is no scheduled audit workflow. Dependabot is scheduled weekly and repository docs say vulnerability alerts/automatic fixes are enabled, but those external controls could not be verified. The review's local `pip-audit` attempt failed because the execution sandbox could not resolve PyPI, so current advisory cleanliness is also unresolved.
- risk: A new advisory against an unchanged locked version may remain without a repository-visible failing run or recorded disposition until another change occurs. Dependabot coverage is especially important but is not evidenced in-repo if ISSUE-003 leaves the graph incomplete.
- recommendation: Add a scheduled locked-environment `pip-audit` run with a visible failure and triage path. Verify Dependabot alerts and automated security updates in GitHub. If evaluating `uv audit --locked`, change the existing pip-audit convention explicitly rather than silently substituting tools.
- follow_on_review: `security-review` and `ci-cd-review`

### ISSUE-008: Repository conventions execute unpinned ambient Node and Git tooling

- first_pass: `4`
- severity: `medium`
- confidence: `high`
- dependency_area: `build-time-downloads-and-bootstrap`
- issue_type: `convention-quality`
- evidence_state: `verified`
- evidence: `docs/handoff/conventions.md:55-62` requires bare `npx prettier` and `npx markdownlint-cli2`, but the repository has no `package.json` or Node lockfile. Lines 79-85 execute `project-standards` from the mutable Git tag `git+https://github.com/L3DigitalNet/project-standards@v4`. These are executable development dependencies outside `uv.lock` and the documented 75-record inventory.
- risk: A clean local run can fetch and execute different third-party code over time, including during fix operations that write across the repository. The stated deterministic-tooling rationale is therefore not true for the Markdown/spec toolchain.
- recommendation: Put Prettier and markdownlint-cli2 behind a checked-in, lock-backed version contract or invoke explicit reviewed versions without ambient latest resolution. Pin `project-standards` to a reviewed commit or immutable artifact. Coordinate with the adopted standards owner because the convention is standard-derived.
- follow_on_review: `conventions-review`

### ISSUE-009: License enforcement permits unknown licenses and lacks a complete lock-derived record

- first_pass: `3`
- severity: `medium`
- confidence: `high`
- dependency_area: `license-and-policy-compliance`
- issue_type: `license-policy-gap`
- evidence_state: `verified`
- evidence: `.github/workflows/dependency-review.yml:8-11` explicitly allows undetectable/unknown licenses; upstream action behavior confirms unknown licenses inform but do not fail. `docs/dependency-licenses.md:1-3` says CI keeps the record mechanically current, but its dev section (`:50-52`) is a selected list rather than the current full dev closure, and its effectiveness depends on the unresolved graph coverage in ISSUE-003.
- risk: A newly added runtime dependency with absent or ambiguous metadata can pass an allowlist intended to reject everything outside the approved set. The manual record can drift from the 74-package third-party lock without detection.
- recommendation: Require explicit disposition for unknown/compound licenses, generate a lock-derived license inventory for every release, compare it to the reviewed allowlist, and keep narrowly reasoned purl exceptions such as the existing `rfc3987-syntax` entry. Do not rely on an empty dependency diff as proof.
- source: [dependency-review-action documents that unknown licenses do not fail](https://github.com/actions/dependency-review-action)
- follow_on_review: `security-review`

## High-Risk Dependency Paths

1. `v*.*.*` tag push → mutable `actions/checkout@v7` → pinned setup Action but unpinned uv executable → dynamically resolved `uv_build` → wheel/sdist → `gh release create` with `contents: write` (ISSUE-001, ISSUE-002, ISSUE-004).
2. Python dependency change → `uv.lock` → unproven GitHub dependency graph → mutable `dependency-review-action@v5` → required status check that may see no Python delta (ISSUE-003, ISSUE-004, ISSUE-009).
3. Local Markdown/spec maintenance → bare `npx` or `uvx` from mutable `@v4` → third-party code executes with developer workspace write access (ISSUE-008).
4. Release consumer → unattested wheel/sdist → broad public runtime ranges → PyPI-resolved install closure without a published release SBOM (ISSUE-005).

## Trust, Provenance, And Inventory Risks

- verified: `uv.lock` is aligned, hash-bearing, single-index, and unchanged from the `v1.0.2` dependency baseline.
- verified: runtime dependencies are explicitly approved in the spec and ADRs; no unexpected runtime import, plugin loader, or network client was found.
- inferred: the release artifact is less reproducible than the test environment because its uv executable and isolated build backend are not bound to the CI lock.
- unverified-external: GitHub dependency graph completeness, release immutability, artifact attestations, tag protection, and environment approval.
- primary_issue_ids: ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-005.

## Registry And Source Boundary Risks

- Python packages use only PyPI/`files.pythonhosted.org`; artifact hashes are present in `uv.lock`.
- No private packages, alternate indexes, direct URLs, local source overrides, or unsafe multi-index fallback were found; dependency-confusion controls are sufficient for the current repo.
- GitHub-hosted Actions and reusable workflows form a second executable registry boundary; most references are mutable tags (ISSUE-004).
- Ambient npm and tagged Git sources form undocumented development registry boundaries (ISSUE-008).

## Trusted Publishing And Signing Risks

- PyPI trusted publishing: `not needed for this repo`; PyPI publication is explicitly out of scope for v1.
- GitHub release publication is live and uses the short-lived repository token, not a long-lived secret; this is positive.
- The workflow does not itself enforce the documented signed-main-tag rule or a protected environment (ISSUE-001).
- The `v1.0.2` tag object contains an EdDSA signature, but cryptographic verification could not complete because the signer public key was unavailable in the sandbox.
- Immutable-release and automatic release-attestation status remain external unknowns (ISSUE-005).

## Update, Staleness, And Maintenance Risks

- Weekly Dependabot covers `pip` and `github-actions`, groups low-noise updates, and applies a seven-day cooldown; this is a strong baseline.
- Runtime public constraints are compatibility floors while CI uses exact locked versions; no manifest-lock drift was found.
- Quiet-repo advisory detection is not independently scheduled (ISSUE-007).
- The documented single-maintainer/Beta concern for `ruamel.yaml` has a named fallback in ADR-0013; no additional issue is raised.
- Current advisory state could not be verified in this environment.

## Container, Bootstrap, And Binary Risks

- Containers/base images: `not needed for this repo`.
- Vendored binaries/runtime tools: `not needed for this repo`.
- `basedpyright` brings the hash-locked `nodejs-wheel-binaries` package into the dev closure; it is not a runtime or release artifact dependency.
- Release-time uv and build-backend resolution are the primary bootstrap risks (ISSUE-002).
- Bare `npx` and tagged `uvx` are secondary developer bootstrap risks (ISSUE-008).

## Policy, License, And Governance Risks

- The spec, dependency ADR, and license record provide unusually clear direct dependency rationale and layer separation.
- The spec's owner-approval rule for new dependencies is sound.
- The license gate's inventory assumption conflicts with current official dependency-graph documentation (ISSUE-003).
- Unknown-license acceptance and the non-generated manual record weaken the stated closed allowlist (ISSUE-009).
- Standard ownership prevents silent CI weakening, but it also means Action and local-tool pinning changes must be routed deliberately (ISSUE-004, ISSUE-008).

## Convention Recommendations

1. Amend the dependency convention to inventory runtime, dev, build, automation, ambient Node, and release dependencies as separate reviewed classes.
2. Make the release-toolchain pin contract explicit: setup Action SHA, uv binary version, isolated build constraints, build source policy, and provenance.
3. Replace the assertion that GitHub resolves `uv.lock` with a verified graph submission contract and a controlled regression test.
4. Require SHA pins for executable Actions/reusable workflows, routed through the adopted standard or an ADR exception where ownership requires it.
5. Add scheduled advisory review and unknown-license disposition rules.
6. Pin the Markdown/spec tooling currently invoked through bare `npx` and mutable Git tags.
7. Add release SBOM, attestation, immutability, and consumer-verification requirements.

## Pass Log

| Pass | Lens | New issues | Result |
| --: | --- | --- | --- |
| 1 | Dependency classes, manifest-lock alignment, artifact sources, registry boundaries, high-risk trust edges | ISSUE-003 | 8 runtime direct, 11 dev direct, 1 build dependency, 75 total lock records; one unproven graph boundary |
| 2 | Update strategy, pinning, publishing, provenance, build downloads, convention alignment | ISSUE-001, ISSUE-002, ISSUE-004, ISSUE-005, ISSUE-006 | Release/tag/toolchain and artifact-provenance gaps identified |
| 3 | Automation identity, license, maintenance, transitive hotspots, rationale consistency | ISSUE-009 | License enforcement and record do not close unknown/incomplete inventory |
| 4 | Hygiene, policy enforcement, drift observability, operator ergonomics, convention quality | ISSUE-007, ISSUE-008 | Scheduled audit and ambient-tool gaps identified; no lower-severity issue suppressed |
| 5 | Adaptive deepening: compare `HEAD` with `v1.0.2`, inspect package imports, dynamic loading, vendoring, source overrides, and release artifacts | none | No dependency-surface regression since `v1.0.2`; no new issue |
| 6 | Adaptive convergence: re-scan attestation/SBOM/index/environment/tag controls and reconcile merged inventory | none | Second consecutive pass with no new issue; review converged |

## Claude Handoff

- fix_first: ISSUE-001, ISSUE-002, and ISSUE-003; they govern who can publish, what code builds the artifact, and whether dependency changes are actually reviewed.
- recommended_sequence:
  1. Prove and harden the tag-to-release identity boundary.
  2. Pin the release uv/build environment and validate exact artifacts.
  3. Establish an explicit `uv.lock` dependency submission/license gate.
  4. SHA-pin remaining automation through the standard/ADR ownership path.
  5. Add SBOM/provenance/immutable-release verification.
  6. Schedule advisory scans and close local-tool/license policy gaps.
- preserve: the single PyPI boundary, hash-bearing uv lock, runtime/dev separation, seven-day Dependabot cooldown, dependency ADR rationale, and narrow `rfc3987-syntax` license exception.
- convention_change_required: yes for ISSUE-004 and ISSUE-008; likely yes for the release/dependency-graph contracts.
- follow_on_reviews: `ci-cd-review`, `release-readiness-review`, and `security-review`.
- do_not_assume: that a green dependency-review job proves `uv.lock` coverage; that `--verify-tag` verifies the intended signer/main ancestry; or that GitHub releases are immutable/attested without checking repository settings.

## Open Questions Or Assumptions

- Does the live GitHub dependency graph contain all direct and transitive packages from `uv.lock`, and does a controlled lock delta appear in the PR dependency diff?
- Are tag rules configured to restrict `v*` creation, require signed tags, and prevent arbitrary write collaborators from triggering releases?
- Is the release job protected by an external environment or approval not visible in the workflow?
- Are immutable releases enabled, and do existing `v1.0.x` assets have verifiable release/build attestations?
- What are the repository Actions default token permissions and allowed-Action policies for callers without an explicit top-level `permissions` block?
- Are Dependabot vulnerability alerts and automated security fixes currently enabled and successfully ingesting the uv resolution?
- Is unknown license metadata intentionally accepted for future runtime dependencies, or should it require owner disposition?
- Assumption: the ignored local `dist/` containing v1.0.0 artifacts is a stale developer build and not authoritative release evidence.

## Residual Risk

- Overall residual risk: `high until ISSUE-001 through ISSUE-003 are resolved or disproved by external control evidence`.
- The Python runtime dependency posture itself is comparatively strong: a single trusted public index, exact hash-bearing lock, no private namespace, clear dependency rationale, and no runtime plugin/network expansion.
- The dominant residual risk is control-plane integrity: tag authorization, dynamically selected build tooling, incomplete dependency-graph evidence, mutable automation references, and absent repository-defined release provenance.
- A clean vulnerability scan, if later obtained, would not close the provenance, license-inventory, or release-identity findings.
