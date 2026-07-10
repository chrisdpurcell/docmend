# Integration And Third-Party Boundary Review

## Review Metadata

- review_type: `integration-and-third-party-boundary-review`
- repo_path: `.`
- repo_name: `docmend`
- report_path: `docs/codex-reviews/2026-07-10-2034-integration-and-third-party-boundary-review-report.md`
- reviewed_at: `2026-07-10`
- branch: `dev`
- commit_sha: `ad8a899f5e718a1530f387093badfdf2eae3e2da`
- working_tree_state: `dirty before review; pre-existing modified AGENTS.md and untracked docs/codex-reviews/`
- review_mode: `read-only except for this requested report`
- detected_runtime: `Python >=3.14 library/CLI; Typer command boundary; local POSIX filesystem processing`
- detected_frameworks_and_libraries: `charset-normalizer, jsonschema Draft 2020-12, Pydantic v2, ruamel.yaml, pathspec, structlog, Typer, Rich, uv`
- runtime_network_boundary: `none found`
- third_party_providers_reviewed: `PyPI dependency resolution; GitHub Actions; GitHub Dependency Review; Dependabot; GitHub Releases API`
- internal_externalized_services_reviewed: `local filesystem; JSON/NDJSON artifacts; YAML frontmatter; backup store; run-lock state directory`
- provider_ownership_and_criticality_artifacts_reviewed: `docs/specs/docmend.md; docs/adr/adr-0005-durable-artifact-schema-contract.md; docs/adr/adr-0006-resume-and-recovery-model.md; docs/adr/adr-0013-v1-dependency-selection.md; docs/adr/adr-0017-branch-and-ci-cd-workflow.md; docs/dependency-licenses.md; docs/handoff/conventions.md`
- webhook_or_callback_surfaces_reviewed: `none found; not needed for this repo`
- auth_and_credential_flows_reviewed: `no runtime credentials; GitHub release uses ephemeral github.token as GH_TOKEN`
- rate_limit_retry_and_degradation_artifacts_reviewed: `local per-file watchdog; apply/resume/restore behavior; GitHub release workflow; no remote runtime retry or quota surface`
- provider_lifecycle_and_change_monitoring_artifacts_reviewed: `uv.lock; Dependabot configuration; dependency-review workflow; dependency ADRs; schema version policy; release workflow`
- data_mapping_and_serialization_surfaces_reviewed: `inventory, plan, report, manifest NDJSON, frontmatter YAML, Pydantic models, hand-authored JSON Schemas`
- reconciliation_and_manual_repair_artifacts_reviewed: `verify engine; resume path; restore engine; restore and resume runbooks`
- sandbox_staging_or_test_environment_artifacts_reviewed: `synthetic fixtures; tmp_path filesystem tests; dry-run defaults; staged include-filter rollout; GitHub release workflow`
- important_external_provider_surfaces_not_in_repo: `GitHub repository settings, tag/branch protection, dependency-graph ingestion state, immutable-release settings, consumer install environments, external backup systems`
- important_runtime_unknowns: `supported OS/filesystem matrix; whether manifests are attacker-modifiable; behavior on network/removable filesystems; real external-preservation proof; released-wheel dependency resolutions over time`
- prior_baseline_or_release_artifacts_compared: `v1.0.2 status; ADR/spec contract history; manifest schema 1.0-1.3 descriptions; current GitHub release workflow`
- conventions_input: `docs/handoff/conventions.md`
- shared_research_reused: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md`
- targeted_external_research: `none; the current 2026-07-10 shared pack covered the detected boundaries`
- validation: `619 passed, 1 skipped with UV_CACHE_DIR and XDG_STATE_HOME redirected to /tmp; the skip is the opt-in 100k-file scale test`
- environment_note: `an initial full-suite run had seven lock-related refusals because the review sandbox's inherited XDG_STATE_HOME was read-only; the redirected rerun passed`

## Integration Area Matrix

| integration_area | applicability | assessment | primary evidence |
| --- | --- | --- | --- |
| `provider-inventory-criticality-and-ownership` | applicable | partial; runtime dependencies and GitHub delivery are inventoried, but several stated controls are unverified or dormant | `pyproject.toml:10-18`; `docs/adr/adr-0013-v1-dependency-selection.md:59-91`; ISSUE-012; ISSUE-013 |
| `auth-credentials-and-secret-boundaries` | delivery only | partial; no runtime secrets, but release runs third-party code with job-wide `contents: write` | `.github/workflows/release.yml:11-38`; ISSUE-005 |
| `request-signing-verification-and-trust` | delivery only | insufficient; docs call for signed tags, while the workflow only asks `gh` to verify that the tag exists | `README.md:97-103`; `.github/workflows/release.yml:35-42`; ISSUE-011 |
| `timeout-retry-and-backoff` | local filesystem only | partial; no remote retry is needed, but manifest append failure after mutation is unreconciled | `src/docmend/watchdog.py:35-65`; ISSUE-002 |
| `idempotency-deduplication-and-replay-safety` | applicable | partial; resume/idempotency are strong for recorded work, but missing records and unvalidated manifest collections break replay evidence | `src/docmend/writer/apply.py:606-676`; ISSUE-002; ISSUE-008 |
| `schema-version-and-contract-drift` | applicable | insufficient; schemas are explicit, but version rejection and historical compatibility evidence are inconsistent | `src/docmend/schemas/README.md:13-18`; ISSUE-007 |
| `provider-change-detection-and-deprecation` | applicable | partial; Dependabot and locked CI exist, but released runtime ranges and release tooling can drift | `.github/dependabot.yml:9-39`; ISSUE-009; ISSUE-011; ISSUE-012 |
| `rate-limits-quotas-and-budgeting` | not needed for this repo | no runtime paid/rate-limited API or resident service exists | `docs/specs/docmend.md:1217-1223` |
| `webhooks-callbacks-and-event-ordering` | not needed for this repo | no inbound webhook, callback, queue, or event-consumer surface exists | source inventory; shared research applicability warning |
| `sandbox-staging-and-production-separation` | local CLI | adequate for corpus rollout; GitHub release publication lacks a draft/verify/promote transaction | `docs/specs/docmend.md:920-939`; ISSUE-011 |
| `fallbacks-degradation-and-failure-isolation` | applicable | insufficient at the manifest/restore boundary | ISSUE-001; ISSUE-002; ISSUE-004 |
| `data-mapping-serialization-and-normalization` | applicable | insufficient because duplicate JSON members reach validation only after silent collapse | `src/docmend/artifacts.py:115-188`; ISSUE-003 |
| `error-handling-observability-and-runbooks` | applicable | partial; run IDs/reports are strong, but verify omits binding plan and backup checks | `src/docmend/observability.py:71-145`; ISSUE-004; ISSUE-006 |
| `reconciliation-and-manual-repair` | applicable | insufficient; restore trusts artifact paths and manifest-level invariants are not checked | ISSUE-001; ISSUE-002; ISSUE-004; ISSUE-008 |
| `integration-testing-mocks-and-fixtures` | applicable | partial; real filesystem and interruption coverage are strong, but critical negative contract/version cases are missing | targeted 86-test pass; full 619-test pass; ISSUE-003; ISSUE-004; ISSUE-007; ISSUE-008 |

## Severity Summary

| severity | count | issue_ids                                                        |
| -------- | ----: | ---------------------------------------------------------------- |
| critical |     0 | —                                                                |
| high     |     6 | ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-008 |
| medium   |     6 | ISSUE-006, ISSUE-007, ISSUE-009, ISSUE-010, ISSUE-011, ISSUE-012 |
| low      |     1 | ISSUE-013                                                        |

## Findings

### ISSUE-001 — Restore can mutate paths outside the manifest's recorded source root

- first_seen_pass: `2`
- severity: `high`
- confidence: `high`
- integration_area: `reconciliation-and-manual-repair`
- issue_type: `reconciliation-manual-repair-gap`
- evidence_status: `verified directly from repo evidence; independently re-checked`
- evidence:
  - `src/docmend/writer/manifest.py:54-75` models manifest paths as non-empty strings and makes `source_root` optional.
  - `src/docmend/cli.py:711-756` reads the manifest and enters restore without a containment validation pass.
  - `src/docmend/cli.py:379-394` uses only the first record's `source_root` to choose a lock; it does not bind record paths to that root.
  - `src/docmend/restore.py:121-132` replays every applied record, and `src/docmend/restore.py:156-258` constructs paths directly from the record before write/rename/unlink operations.
  - `docs/specs/docmend.md:716-720` promises writes are denied outside the source root regardless of user permissions.
- impact: `A crafted, mixed, or operator-edited manifest can direct restore --write at files outside the intended library. Hash and backup checks limit blind clobbering, and the process gains no privileges, but the command crosses its explicit mutation authority boundary.`
- recommendation: `Before acquiring the lock or reading recovery bytes, require one consistent resolved source_root for the manifest and validate original_path, target_path, backup_path, and overwritten_backup_path against their allowed roots. Repeat containment immediately before every mutation and add out-of-root restore tests.`
- follow_on_review: `security-review and api-contract-review`

### ISSUE-002 — Pure rewrite/rename and restore mutations can complete before durable manifest evidence exists

- first_seen_pass: `2`
- severity: `high`
- confidence: `high`
- integration_area: `idempotency-deduplication-and-replay-safety`
- issue_type: `idempotency-dedup-replay-gap`
- evidence_status: `verified directly from code and existing tests; independently re-checked`
- evidence:
  - `src/docmend/writer/apply.py:485-502` writes an intent only for `rename_and_rewrite`.
  - `src/docmend/writer/apply.py:503-560` performs pure rewrite/rename mutations, while `src/docmend/writer/apply.py:562-583` appends their only applied record afterward.
  - `src/docmend/writer/manifest.py:112-130` can fail while validating, writing, flushing, or fsyncing that record; the mutation is not rolled back.
  - `tests/test_resume.py:233-263` explicitly covers a completed pure mutation whose record was lost and accepts a `stale-hash` or `unreadable` finding rather than reconstructing recovery evidence.
  - `src/docmend/restore.py:238-283` likewise mutates first and appends its inverse record afterward.
  - `docs/specs/docmend.md:704-706` states that a crash cannot orphan completed mutations.
- impact: `A process kill, disk-full event, or manifest fsync error can leave converted or restored state with no durable applied record. Resume avoids a second mutation but cannot reconstruct the record; mechanical restore and audit completeness are lost.`
- recommendation: `Use a durable pre-mutation intent for every mutation class, including restore inverses, and reconcile it into a final record after publication. Reserve artifact-disk headroom and add crash/append-failure tests at each mutation-to-record boundary.`
- follow_on_review: `background-jobs-and-async-workflow-review and incident-readiness-review`

### ISSUE-003 — Duplicate JSON members are silently collapsed before durable-artifact validation

- first_seen_pass: `2`
- severity: `high`
- confidence: `high`
- integration_area: `data-mapping-serialization-and-normalization`
- issue_type: `data-mapping-serialization-gap`
- evidence_status: `verified directly from parser call sites and test inventory`
- evidence:
  - `src/docmend/artifacts.py:115-128`, `:141-154`, and `:175-188` call ordinary `json.loads` for inventory, plan, and report before schema/Pydantic validation.
  - `src/docmend/writer/manifest.py:157-170` does the same per manifest line.
  - `tests/test_schemas.py:49-93` checks schema strictness but not duplicate JSON names; YAML duplicate-key rejection is implemented separately in `src/docmend/frontmatter.py:65-81`.
  - The shared research pack cites RFC 8259's cross-implementation ambiguity and recommends rejection before validation: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md:32-37`.
- impact: `A plan or manifest can contain two source_root, target_path, result, hash, or schema_version members. Python keeps the last value before the schema sees the object, while reviewers or other consumers may interpret a different value. This undermines reviewed-plan and recovery-ledger trust.`
- recommendation: `Centralize duplicate-aware JSON decoding with object_pairs_hook, raise ArtifactError on the first duplicate, and add negative tests for every durable artifact and NDJSON record.`
- follow_on_review: `api-contract-review and security-review`

### ISSUE-004 — Verify can report clean without checking whether recovery backups still exist or match their recorded hashes

- first_seen_pass: `3`
- severity: `high`
- confidence: `high`
- integration_area: `reconciliation-and-manual-repair`
- issue_type: `reconciliation-manual-repair-gap`
- evidence_status: `verified directly against the binding ADR and implementation`
- evidence:
  - `docs/adr/adr-0012-verify-semantics-exit-code-taxonomy.md:68` requires manifest before/after hashes and backup references to reconcile.
  - `src/docmend/verify.py:88-114` checks only the live target against `after_sha256`.
  - `tests/test_verify.py:17-55` uses `backup_path=None`; there is no missing/corrupt backup verification case.
  - `src/docmend/restore.py:48-80` discovers missing or corrupt original backups only during restore, and `src/docmend/restore.py:193-225` does the same for overwritten-target backups.
- impact: `An operator can receive verify exit 0 before a destructive rollout even though the actual recovery bytes have been deleted or corrupted. The failure is deferred until disaster recovery is attempted.`
- recommendation: `Have manifest reconciliation validate every required backup's existence and digest, including overwritten-target backups, and produce exit-1 findings. If backup validation is intentionally restore-only, narrow ADR-0012 and user-facing verify claims rather than reporting a stronger guarantee.`
- follow_on_review: `incident-readiness-review and product-and-business-logic-review`

### ISSUE-005 — Release publication executes mutable Action tags with a write-capable token

- first_seen_pass: `3`
- severity: `high`
- confidence: `high`
- integration_area: `auth-credentials-and-secret-boundaries`
- issue_type: `auth-credential-boundary-gap`
- evidence_status: `verified directly from workflow; current official guidance already captured in shared research`
- evidence:
  - `.github/workflows/release.yml:11-12` grants job-wide `contents: write`.
  - `.github/workflows/release.yml:19` executes `actions/checkout@v7` before `.github/workflows/release.yml:35-42` uses `github.token` to create a release.
  - `.github/workflows/check.yml:16-18`, `.github/workflows/dependency-review.yml:32-34`, and `.github/workflows/traceability.yml:19-21` also use mutable action tags; reusable workflows use `@v4` in `.github/workflows/lint-markdown.yml:11` and `.github/workflows/validate-specs.yml:11`.
  - The shared research pack records GitHub's guidance that a full commit SHA is the only immutable Action reference: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md:58-64`.
- impact: `A moved or compromised action/reusable-workflow tag can execute with release credentials and alter repository releases. The release job has the highest provider-side privilege in the repo.`
- recommendation: `Pin every action and reusable workflow to a reviewed full SHA. Split build/test from publication so only a minimal final job receives contents: write, and protect that job with an environment or approval if available.`
- follow_on_review: `ci-cd-review and dependency-supply-chain-review`

### ISSUE-008 — Manifest readers validate records individually but not the ledger's run, root, version, identity, or sequence invariants

- first_seen_pass: `5`
- severity: `high`
- confidence: `high`
- integration_area: `reconciliation-and-manual-repair`
- issue_type: `reconciliation-manual-repair-gap`
- evidence_status: `verified directly and independently re-checked`
- evidence:
  - `src/docmend/writer/manifest.py:142-171` parses and validates each line, then returns the list without a whole-file validation pass.
  - `src/docmend/schemas/manifest.schema.json:5` explicitly scopes the schema to one record.
  - `src/docmend/schemas/manifest.schema.json:27-41` allows any `1.x` version and only bounds `seq >= 1`; it cannot enforce one run ID, action/run identity, one source root, unique/contiguous sequence, or unique terminal action state.
  - `src/docmend/restore.py:121-125` sorts the unvalidated collection only by `seq` before mutation.
  - `src/docmend/cli.py:611-641` says every resume record's root must match, but checks only the first non-null root.
  - `src/docmend/verify.py:141-150` catches duplicate applied action IDs only during optional report reconciliation, not in manifest read, restore, resume, or manifest-only verify.
- impact: `A concatenated, truncated, reordered, mixed-root, mixed-run, or mixed-version manifest can pass per-record validation and drive replay under the wrong lock or in an ambiguous order. Missing interior records are not detected even though seq is described as a truncation signal.`
- recommendation: `Add a manifest-ledger validator invoked by restore, resume, and verify. Enforce supported version, one run/root, action_id/run_id coherence, seq start/contiguity/uniqueness, allowed state transitions, and duplicate terminal-record policy before any mutation.`
- follow_on_review: `data-schema-migration-review and background-jobs-and-async-workflow-review`

### ISSUE-006 — The binding verify contract advertises plan input and reconciliation that the CLI does not implement

- first_seen_pass: `2`
- severity: `medium`
- confidence: `high`
- integration_area: `schema-version-and-contract-drift`
- issue_type: `convention-misalignment`
- evidence_status: `verified directly against binding spec and CLI`
- evidence:
  - `docs/specs/docmend.md:371` specifies `docmend verify PATH [--manifest FILE] [--report FILE] [--plan FILE]`.
  - `docs/adr/adr-0012-verify-semantics-exit-code-taxonomy.md:68` also lists `--plan` as an explicit input.
  - `src/docmend/cli.py:767-803` exposes manifest, run ID, report, and config, but no plan argument.
  - `docs/specs/docmend.md:859` nevertheless marks IR-004 complete.
- impact: `Verify cannot validate the advertised plan or reconcile report.plan_ref identity/hash with a supplied plan, so the cross-artifact chain is weaker than the published CLI contract.`
- recommendation: `Implement and test --plan plus plan/report/manifest identity and hash reconciliation, or deliberately amend the binding spec and ADR to remove that surface and correct traceability.`
- follow_on_review: `api-contract-review`

### ISSUE-007 — Artifact-version policy is not enforced consistently and lacks genuine historical compatibility fixtures

- first_seen_pass: `2`
- severity: `medium`
- confidence: `high`
- integration_area: `schema-version-and-contract-drift`
- issue_type: `schema-version-drift-gap`
- evidence_status: `verified directly from schemas, readers, and tests`
- evidence:
  - `src/docmend/schemas/README.md:13-18` promises backward-only MAJOR.MINOR compatibility and requires older binaries to refuse unsupported future data.
  - Inventory, plan, report, manifest, and frontmatter schemas accept any `1.x` string; examples include `src/docmend/schemas/manifest.schema.json:27` and `src/docmend/schemas/inventory.schema.json:25-28`.
  - `src/docmend/cli.py:489-500` adds a future-minor check only for apply's plan; inventory, report, manifest, and frontmatter consumers have no equivalent policy gate.
  - `tests/test_schemas.py:73-93` asserts only that a version pattern exists.
  - `tests/unit/writer/test_manifest.py:156-165` simulates pre-1.2 by deleting a field from a current record rather than preserving an actual historical 1.1 artifact/version.
- impact: `Unsupported future-minor artifacts may be accepted when their present fields happen to fit, while claimed backward compatibility is not proven against historical producers. Restore and verify are the most consequential consumers.`
- recommendation: `Centralize version negotiation per artifact kind, implement the documented mismatch table, and preserve golden fixtures from every released artifact version with valid, malformed, older-minor, newer-minor, and newer-major tests.`
- follow_on_review: `data-schema-migration-review and release-readiness-review`

### ISSUE-009 — Released wheels permit untested future dependency majors at behavior-critical boundaries

- first_seen_pass: `1`
- severity: `medium`
- confidence: `high`
- integration_area: `provider-change-detection-and-deprecation`
- issue_type: `provider-change-detection-gap`
- evidence_status: `verified directly; release-consumer resolutions remain external`
- evidence:
  - `pyproject.toml:10-18` uses lower-only bounds for every runtime dependency, including `charset-normalizer>=3.4.2`, `pydantic>=2.12`, and `ruamel-yaml>=0.18`.
  - `tests/test_detection.py:1-66` intentionally pins behavior that a detector upgrade can change.
  - `tests/test_detection_provenance.py:37-47` records the installed detector version but does not constrain what a future installation may resolve.
  - `uv.lock:103-106` currently locks charset-normalizer 3.4.7 for repo CI, but the lock is not an install constraint embedded in a released wheel.
- impact: `The same docmend release can install with a future major parser/model/detector version that never passed this release's tests. At the encoding boundary, a changed high-confidence verdict can alter destructive plans.`
- recommendation: `Define and test a supported version window for behavior-critical dependencies, cap unsupported majors in wheel metadata, and use Dependabot-driven compatibility updates to widen ranges deliberately. Consider recording the complete runtime closure in run metadata for field diagnosis.`
- follow_on_review: `dependency-supply-chain-review and release-readiness-review`

### ISSUE-010 — Package metadata does not disclose the runtime's POSIX-only boundary

- first_seen_pass: `1`
- severity: `medium`
- confidence: `high`
- integration_area: `sandbox-staging-and-production-separation`
- issue_type: `sandbox-production-separation-gap`
- evidence_status: `verified directly; consumer OS behavior inferred from standard-library availability`
- evidence:
  - `src/docmend/lock.py:19-20` imports `fcntl` unconditionally and `src/docmend/lock.py:65` uses `flock`.
  - `src/docmend/watchdog.py:59-65` requires SIGALRM/setitimer.
  - `src/docmend/cli.py:35` imports the lock module at CLI import time.
  - `pyproject.toml:1-19` declares no operating-system restriction, while `pyproject.toml:67-72` asks static analysis to consider `pythonPlatform = "All"`.
  - CI and release use only Ubuntu, for example `.github/workflows/check.yml:13` and `.github/workflows/release.yml:16`.
- impact: `A consumer can install the universal package on Windows and fail before the CLI starts. Non-Linux POSIX behavior and filesystem durability promises are also unverified.`
- recommendation: `Either declare and document POSIX-only support clearly in packaging/user docs, or add portable lock/watchdog abstractions and an OS matrix. Record the supported filesystem/durability matrix separately from Python compatibility.`
- follow_on_review: `release-readiness-review`

### ISSUE-011 — GitHub release creation is not a pinned, identity-checked, retry-safe transaction

- first_seen_pass: `3`
- severity: `medium`
- confidence: `high`
- integration_area: `fallbacks-degradation-and-failure-isolation`
- issue_type: `degradation-failure-isolation-gap`
- evidence_status: `verified directly; provider-side partial-failure behavior remains external`
- evidence:
  - `.github/workflows/check.yml:24-27` pins the uv executable, but `.github/workflows/release.yml:26-29` does not.
  - `pyproject.toml:44-46` permits a range of uv_build backends.
  - `.github/workflows/release.yml:7-9` triggers on any matching tag, but `.github/workflows/release.yml:28-42` does not compare the tag to `project.version` or cryptographically verify the signed-tag policy in `README.md:99-103`.
  - `.github/workflows/release.yml:35-42` creates the live release and uploads all `dist/*` in one call, without a draft, asset digest inventory, completion check, rerun policy, or manual repair path.
- impact: `A mistyped tag or changed toolchain can publish mislabeled artifacts. An ambiguous/partial provider failure can leave an incomplete release that a rerun cannot reconcile cleanly.`
- recommendation: `Pin uv and the build backend; verify tag, source commit, package version, and signed-tag policy; build once and inventory exact asset digests; create a draft, upload and verify assets, then publish; define idempotent rerun/manual repair behavior and a job timeout.`
- follow_on_review: `ci-cd-review and release-readiness-review`

### ISSUE-012 — The dependency-review license gate assumes uv.lock ingestion that is not proven in the repo

- first_seen_pass: `3`
- severity: `medium`
- confidence: `medium`
- integration_area: `provider-inventory-criticality-and-ownership`
- issue_type: `provider-inventory-ownership-gap`
- evidence_status: `repo claim verified; actual GitHub ingestion could not be verified from repository evidence`
- evidence:
  - `.github/workflows/dependency-review.yml:3-11` claims GitHub resolves `uv.lock` natively and acknowledges that undetectable/unknown licenses do not fail the gate.
  - `.github/workflows/dependency-review.yml:21-41` relies on the provider action and an allowlist, with no independent resolved-environment/SBOM submission.
  - The current shared research notes that GitHub's documented dependency-graph ecosystems do not list uv.lock and says actual ingestion/submission must be verified: `docs/codex-reviews/2026-07-10-2034-codex-review-shared-research.md:58-64`.
- impact: `The required check can succeed without evaluating Python dependency deltas, making the documented license-control guarantee stronger than the evidence.`
- recommendation: `Prove coverage with a controlled uv.lock-only dependency change and inspect the action output/provider graph. If unresolved, submit an SBOM/dependency snapshot or add an independent resolved-license gate and update the workflow comments to the observed behavior.`
- follow_on_review: `dependency-supply-chain-review and ci-cd-review`

### ISSUE-013 — Some documented provider/test controls are installed or claimed but not active

- first_seen_pass: `4`
- severity: `low`
- confidence: `high`
- integration_area: `provider-change-detection-and-deprecation`
- issue_type: `provider-change-detection-gap`
- evidence_status: `verified from repo inventory`
- evidence:
  - `pyproject.toml:30-42` installs pyfakefs and pytest-xdist, but no test imports pyfakefs and `.github/workflows/check.yml:41-42` invokes pytest without xdist.
  - `docs/specs/docmend.md:515-520` describes both tools as active test controls and calls check-jsonschema a pre-commit hook.
  - `docs/adr/adr-0005-durable-artifact-schema-contract.md:68-70` lists that hook as confirmation, but no pre-commit configuration exists in the repository.
- impact: `The provider inventory and confirmation record overstate active coverage while retaining unused dependency surface.`
- recommendation: `Remove unused dependencies/claims or wire the intended controls. Keep provider ownership documents limited to controls that are executable and evidenced.`
- follow_on_review: `dependency-supply-chain-review and conventions-review`

## High-Risk Integration Failure Paths

| path_id | trigger | path | terminal risk | controls present | missing control |
| --- | --- | --- | --- | --- | --- |
| HR-001 | crafted or mixed manifest | `restore --write` -> first-record lock root -> record-controlled absolute path -> atomic write/rename | mutation outside intended library | explicit write opt-in; hashes; backup validation | manifest/root/path containment before and at mutation |
| HR-002 | kill, ENOSPC, or fsync failure after pure mutation | atomic rewrite/rename succeeds -> final manifest append absent/fails -> resume sees stale/missing source | completed mutation cannot be mechanically discovered/restored | atomic document write; optional backup; safe no-repeat outcome | pre-mutation intent and reconciliation for every mutation class |
| HR-003 | deleted/corrupt backup before rollout | `verify` checks live after-hash only -> exit 0 -> later restore reads backup | recovery fails only during incident | restore-time backup hash validation | verify-time recovery-evidence validation |
| HR-004 | moved/compromised Action tag | release job starts with `contents: write` -> mutable action executes -> GitHub token available to job | malicious or unauthorized release mutation | setup-uv SHA pin; scoped repository token | full-SHA pins and privilege-separated publish job |
| HR-005 | concatenated/truncated/reordered manifest | per-line validation passes -> mixed ledger sorted by seq -> restore/resume | wrong lock, ambiguous replay, missing work, duplicate state transition | per-record schema; torn syntax handling | whole-ledger invariant validation |
| HR-006 | future dependency resolution | install released wheel -> lower-only dependency range resolves new major -> detector/parser semantics change | untested plan or validation behavior in the field | repo lock; Dependabot; detector provenance | supported-version window and released-wheel compatibility testing |

## Provider Inventory, Ownership, And Criticality

| provider_or_boundary | role | criticality | ownership_artifact | change_monitoring | review_result |
| --- | --- | --- | --- | --- | --- |
| local POSIX filesystem | corpus, artifacts, backups, locks | critical | spec §§8, 12, 13, 18; ADR-0003/0004/0006 | tests and runbooks | unsafe restore/manifest failure paths remain |
| charset-normalizer | legacy-encoding decision fact | critical | ADR-0009; detection seam | locked CI, behavior fixtures, provenance | field install range can drift beyond tested behavior |
| jsonschema + Pydantic | external contract validation and internal models | critical | ADR-0005/0013 | schema tests, Dependabot | version negotiation and duplicate JSON parsing incomplete |
| ruamel.yaml | frontmatter parser | high | ADR-0011/0013 | codec tests, documented fallback | adequate for current v1 parse-only scope |
| pathspec | selection/filter semantics | high | spec/ADR dependency set | locked CI, filter tests | no material defect found |
| structlog/Typer/Rich | logging and CLI boundary | medium | ADR-0013 and observability contract | locked CI, CLI/log tests | no material runtime integration defect found |
| PyPI/uv | dependency and build resolution | high | pyproject, uv.lock, ADR-0013 | Dependabot, pip-audit | released-wheel and release-toolchain drift gaps |
| GitHub Actions | CI/release execution | critical for delivery | ADR-0017 | Dependabot | mutable references remain |
| GitHub Releases API | public artifact publication | critical for delivery | ADR-0017 and release workflow | workflow only | transaction/identity/reconciliation gaps remain |
| GitHub Dependency Review | license gate | high for distribution policy | ADR-0017 and workflow | provider action | uv.lock coverage unverified |
| external Git/Git snapshots/backups | operator-declared preservation | critical when selected | ADR-0004; README | outside repo | existence/freshness cannot be verified here |

## Auth, Trust, And Credential Boundaries

- runtime_auth: `not needed for this repo; local process runs as invoking user`
- runtime_secrets: `none found`
- inbound_request_signing: `not needed for this repo`
- release_credential: `github.token exposed as GH_TOKEN to the release job`
- trust_boundary_result: `runtime credential posture is appropriate; release privilege is not isolated from mutable action code`
- artifact_trust_result: `plans and manifests are operator-supplied durable inputs and must be treated as untrusted; restore currently does not do so consistently`
- external_preservation_result: `git/external preservation is an accepted operator attestation, not repo-verifiable proof; this remains residual risk rather than a new decision in this review`

## Contract Drift And Data Mapping Risks

- duplicate_member_policy: `missing for JSON/NDJSON; ISSUE-003`
- schema_dialect: `Draft 2020-12 explicitly pinned; format assertion enabled`
- unknown_field_policy: `strict additionalProperties:false and Pydantic extra=forbid`
- version_policy: `documented but inconsistently enforced; ISSUE-007`
- historical_compatibility_evidence: `insufficient; current-shape simulations are not genuine released fixtures`
- plan_report_manifest_chain: `report/manifest accounting exists; plan input/reconciliation missing from verify; ISSUE-006`
- dependency_behavior_contract: `detector behavior tests are strong, but wheel metadata permits future untested majors; ISSUE-009`

## Retry, Replay, And Outage Behavior

- remote_retry: `not needed for this repo; no remote runtime calls`
- local_retry: `manual re-plan/re-apply; resume reconciles recorded applied work`
- idempotency_key: `source hash plus action/run identity`
- replay_safety: `strong for well-formed recorded runs; weak for missing records and malformed-but-per-record-valid manifests`
- manifest_outage_behavior: `unsafe after pure mutation; ISSUE-002`
- artifact_disk_budget: `manifest directory writability is probed, but no artifact-space budget prevents mid-run ENOSPC`
- provider_publish_retry: `GitHub release rerun/manual repair is unspecified; ISSUE-011`

## Webhook And Callback Risks

- applicability: `not needed for this repo`
- inbound_webhooks: `none`
- outbound_callbacks: `none`
- event_ordering: `no provider events; local manifest ordering is applicable and covered by ISSUE-008`
- signature_verification: `no runtime request signatures; release tag identity verification is incomplete under ISSUE-011`

## Testing, Sandbox, And Environment Separation

- local_runtime_environments: `single offline CLI; dev/staging/prod endpoints are not needed`
- safe_rollout: `dry-run default, plan review, include-filter staging, backups, resume/restore drills`
- test_data: `synthetic/public fixtures; no real library data reviewed`
- filesystem_semantics: `real tmp paths used for writer/crash tests; targeted integration set passed 86/86`
- full_suite: `619 passed, 1 opt-in scale test skipped after sandbox state/cache redirection`
- missing_negative_tests: `restore out-of-root paths; manifest append failure after every mutation class; duplicate JSON members; backup deletion/corruption in verify; manifest ledger invariants; artifact version mismatch matrix; actual historical artifacts`
- OS_matrix: `Ubuntu only; package support boundary not declared; ISSUE-010`
- release_sandbox: `no draft/verify/promote release flow; ISSUE-011`

## Operational Controls And Visibility

- strong_controls: `per-run correlation IDs; JSONL logs; report/manifest schemas; dry-run; run locks; source hashes; backup verification at restore; resume and restore runbooks`
- weak_controls:
  - `verify omits backup and plan reconciliation`
  - `manifest collection integrity is not validated`
  - `missing pure-mutation records cannot be reconstructed`
  - `release completion and asset identity are not reconciled`
- operator_controls: `explicit --write; --backup-dir; --preserved-by; --allow-no-backup; include/exclude filters; --resume-manifest; --manifest/--run-id`
- manual_repair_gaps: `no wrong-root containment-breach runbook; no bad schema/release runbook; no partial GitHub release repair path`
- external_visibility_unknowns: `GitHub settings, provider ingestion, immutable releases, backup freshness, consumer filesystem behavior`

## Convention Recommendations

### Shared Across Projects

1. Reject duplicate JSON member names before schema/model validation for every durable or mutation-driving input.
2. Treat every persisted recovery artifact as untrusted at every consumer; bind it to an explicit authority root before reading or mutating paths.
3. Require durable intent before mutation whenever completion evidence is needed for replay, reconciliation, or rollback.
4. Define and test an artifact-version mismatch matrix with preserved historical fixtures.
5. Pin GitHub Actions and reusable workflows to full SHAs and isolate publish credentials to the smallest job.
6. Make release publication a draft -> upload exact assets -> verify identities/digests -> publish transaction with an idempotent rerun path.

### Repo-Specific

1. Add a durable-artifact convention to `docs/handoff/conventions.md` covering duplicate-key rejection, version gates, historical fixtures, and whole-manifest invariants.
2. Require restore/verify/resume to share one manifest-ledger and containment validator.
3. Extend `verify` to prove recovery bytes and the advertised plan/report/manifest reference chain.
4. Declare POSIX-only support or implement/test portable lock and watchdog adapters.
5. Define supported runtime dependency windows, especially for charset-normalizer.
6. Remove dormant dependency/control claims or wire them into the executable gate.

### Convention Quality Assessment

- conventions_alignment: `The implementation follows the repo's general tooling, sensitive-data, and standard-ownership conventions.`
- conventions_gap: `docs/handoff/conventions.md has no durable-artifact parsing/version/recovery-boundary rule despite those being the primary cross-command integration contract.`
- convention_misalignment: `IR-004/ADR-0012 advertise verify --plan and backup-ref reconciliation that the implementation does not provide.`
- justified_deviation: `No network auth/webhook/rate-limit conventions are needed for the fully offline v1 scope.`

## Pass Log

| pass | lens | new_issue_ids | result |
| --: | --- | --- | --- |
| 1 | provider inventory, ownership, criticality, contracts, auth, environment boundaries | ISSUE-009, ISSUE-010 | Confirmed offline runtime; identified PyPI/uv and implicit POSIX boundaries. |
| 2 | retries, idempotency, artifact trust, schema drift, data mapping, code-to-convention alignment | ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-006, ISSUE-007 | Confirmed mutation-driving artifact and compatibility gaps. |
| 3 | fallback behavior, reconciliation, observability, provider controls, contract testing | ISSUE-004, ISSUE-005, ISSUE-011, ISSUE-012 | Confirmed recovery-evidence and GitHub delivery risks. |
| 4 | lower-severity maintainability, docs, provider churn, convention quality | ISSUE-013 | Found dormant/absent provider-control claims. |
| 5 | adaptive deepening: whole-manifest invariants and mutation consumers | ISSUE-008 | Independent verification confirmed collection-level validation gap. |
| 6 | adaptive convergence: restore/manifest counterevidence and tests | none | No new issues; severity and scope refined. |
| 7 | adaptive convergence: final provider, convention, and non-applicability sweep | none | No new issues; convergence reached after two consecutive no-new-issue passes. |

## Claude Handoff

- highest_priority_sequence:
  1. `ISSUE-001`: enforce restore manifest/root/path containment before any mutation.
  2. `ISSUE-002`: make all apply/restore mutation classes write-ahead and reconcilable.
  3. `ISSUE-008`: validate whole-manifest invariants at every consumer.
  4. `ISSUE-004`: make verify prove backup recoverability.
  5. `ISSUE-003`: reject duplicate JSON members centrally.
  6. `ISSUE-005`: SHA-pin release dependencies and privilege-separate publication.
- recommended_change_shape: `One ADR/spec-aligned recovery-boundary change should cover ISSUE-001, ISSUE-002, ISSUE-004, and ISSUE-008 together; avoid isolated patches that leave consumers inconsistent.`
- conventions_change: `Add the repo-specific durable-artifact convention only after the binding spec/ADR behavior is settled.`
- required_regression_tests: `out-of-root restore, mixed-root/run ledger, seq gaps/duplicates, kill/append failure after pure rewrite/rename/restore, missing/corrupt backups under verify, duplicate JSON keys, version mismatch matrix, historical artifact fixtures`
- follow_on_reviews: `security-review for restore/artifact trust; background-jobs-and-async-workflow-review for crash windows; api-contract-review for verify/artifact contracts; ci-cd-review and dependency-supply-chain-review for GitHub/PyPI; release-readiness-review for package/platform/release identity`
- do_not_assume: `Do not infer network APIs, FastAPI, webhooks, queues, OAuth, AI providers, or staging endpoints from documentation vocabulary; none exists in executable v1 scope.`
- owner_decisions_needed: `supported OS/filesystem matrix; manifest threat model; supported dependency version window; whether verify --plan is implemented or removed; whether GitHub publication should use protected environments/draft releases`

## Open Questions Or Assumptions

1. Are manifest and plan files assumed trusted single-user outputs, or can they be downloaded, synced, edited, or supplied by wrappers? The binding containment promise currently implies they must be treated as untrusted regardless.
2. Is support intentionally limited to Linux, all POSIX systems, or a broader OS set?
3. Which local, removable, or network filesystems are supported for atomicity, fsync, and flock semantics?
4. Does GitHub's live dependency graph actually ingest this repository's uv.lock, and does the dependency-review action report Python deltas?
5. Are immutable GitHub Releases, tag protection, and protected release environments enabled outside the repo?
6. What dependency compatibility window should released wheels promise for charset-normalizer, Pydantic, jsonschema, ruamel.yaml, pathspec, structlog, Typer, and Rich?
7. Should verify implement its binding --plan and backup-reference checks, or should the spec/ADR be narrowed?
8. What is the operator recovery procedure after a manifest append/fsync failure, a wrong-root manifest, or a partially created GitHub Release?

## Residual Risk

- overall_residual_risk: `high until ISSUE-001, ISSUE-002, ISSUE-004, ISSUE-005, and ISSUE-008 are addressed`
- runtime_network_risk: `none in v1 executable scope`
- data_corruption_risk: `medium; conservative detection and atomic writes are strong, but missing recovery evidence can make successful mutations operationally irreversible`
- authority_boundary_risk: `high; restore does not enforce its recorded root`
- recovery_risk: `high; verify can miss unusable backups and pure mutations can be unmanifested`
- provider_delivery_risk: `high; mutable actions execute in a write-capable release job`
- compatibility_risk: `medium; artifact and dependency version policy is incompletely enforced`
- confidence_limitations: `GitHub settings/provider state, real consumer OS/filesystem behavior, external backup freshness, and hostile-artifact assumptions are outside repository evidence`
