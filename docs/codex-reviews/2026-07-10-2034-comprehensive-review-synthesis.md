# Comprehensive Review Synthesis

## Outcome

The default Python gate and current v1.0.2 package remain healthy, but docmend is not ready for a real-library write rollout. The review confirmed data-safety, recovery, and false-clean verification defects that should be fixed before the owner's staged rollout.

The exhaustive sweep ran and completed all 18 review lenses. The generic code lens initially failed when a classifier flagged the benign `SIGALRM` watchdog source, then completed successfully on retry. An independent fallback also reviewed the complete codebase and found the same root causes plus the plan/backup collision below. The raw lens severity counts are not additive because the same recovery defects appear in several reports.

## Confirmed Rollout Blockers

### DMR-01 — One plan can overwrite its own recovery backup

- Severity: High
- Confidence: High
- Evidence: [planning.py](../../src/docmend/planning.py#L218), [apply.py](../../src/docmend/writer/apply.py#L430), and [backup.py](../../src/docmend/writer/backup.py#L24)

The planner reserves rename targets but not paths scheduled for in-place work. With dirty `a.md`, dirty `a.txt`, and collision policy `overwrite`, it schedules both the `a.md` rewrite and `a.txt -> a.md`. The source backup for the first action and overwritten-target backup for the second action use the same `<backup>/<run>/a.md` key.

A temporary CLI reproduction applied both actions successfully. LIFO restore then restored `a.txt` but rejected the overwritten `a.md` backup with an `ERR-004` hash mismatch. The original `a.md` bytes were no longer available from the tool backup.

Required direction: reserve every action's effective output path across the whole plan and namespace backups immutably by action and role.

### DMR-02 — Artifact destinations can overwrite corpus inputs

- Severity: High
- Confidence: High
- Evidence: [cli.py](../../src/docmend/cli.py#L189), [artifacts.py](../../src/docmend/artifacts.py#L93), and [gate.py](../../src/docmend/writer/gate.py#L218)

`scan --report`, `plan --out`, and `apply --report` accept unchecked paths. The artifact writer truncates a predictable staging path and replaces the requested destination. The apply gate does not receive the report path.

Temporary reproductions replaced source files with inventory, plan, and report JSON during scan, plan, apply dry-run, and a refused write. The commands returned their normal success or refusal status, and dry-run created no manifest.

Required direction: add one source-aware artifact preflight, reject aliases to protected inputs, use exclusive randomized staging, and keep apply finalization inside the lock and safety boundary.

### DMR-03 — Manifest consumers trust paths and invalid ledger states

- Severity: High
- Confidence: High
- Evidence: [manifest.py](../../src/docmend/writer/manifest.py#L142), [restore.py](../../src/docmend/restore.py#L48), and [cli.py](../../src/docmend/cli.py#L379)

Manifest records are validated one line at a time. There is no run-level check for one root, one run, supported version, sequence integrity, action lifecycle, or result-dependent fields. Restore reads and mutates recorded paths directly while the lock is derived from only the first record's root.

An out-of-root restore reproduction changed a file outside the recorded source root. A mixed-root, mixed-run manifest with duplicate sequence values was also accepted. A crafted completed resume record can point at a matching outside file and suppress the real planned action as `already-applied`.

Required direction: introduce one manifest-set model used before resume, restore, and verify. Validate root, paths, version, run, sequence, identity, and lifecycle before any referenced file is read or mutated, then repeat containment at the mutation boundary.

### DMR-04 — Apply and restore have unjournaled commit windows

- Severity: High
- Confidence: High
- Evidence: [apply.py](../../src/docmend/writer/apply.py#L485), [restore.py](../../src/docmend/restore.py#L232), [test_resume.py](../../tests/test_resume.py#L233), and [test_restore.py](../../tests/test_restore.py#L459)

Only `rename_and_rewrite` writes an intent before mutation. Pure rewrite and rename operations mutate first and append their only record afterward. Restore also performs its inverse mutation before appending inverse evidence.

Fault injection confirmed completed mutations with no durable applied record. Resume then reports `stale-hash` or `unreadable` instead of adopting the work. An interrupted multi-step restore can leave both names present, after which the same restore command stops on a collision instead of converging. Verify and restore also ignore dangling intent records.

Required direction: use a prepare/commit protocol for every apply and restore mutation, and make resume, verify, and restore consume one shared lifecycle reducer.

### DMR-05 — Verify has multiple false-clean outcomes

- Severity: High
- Confidence: High
- Evidence: [verify.py](../../src/docmend/verify.py#L88), [cli.py](../../src/docmend/cli.py#L843), and [apply.py](../../src/docmend/writer/apply.py#L634)

Independent CLI reproductions confirmed that verify exits `0` when:

- a recorded tool backup is missing or corrupt;
- every candidate is unreadable or times out, producing zero checked files;
- collision policy `fail` aborts a plan and trailing actions are never reported;
- a manifest belongs to another root or contains a dangling intent.

Current reconciliation checks live after-hashes and applied ID sets only. It does not validate backup bytes, discovery error skips, complete plan coverage, or nonterminal manifest state. The binding `verify --plan` interface is absent.

Required direction: make verification plan-aware, backup-aware, skip-aware, root-aware, and lifecycle-aware. Every planned action needs exactly one terminal outcome, including an explicit aborted or not-attempted state.

### DMR-06 — Path identity is not held through mutation

- Severity: High
- Confidence: High for reachability; Medium for field likelihood
- Evidence: [apply.py](../../src/docmend/writer/apply.py#L363) and [restore.py](../../src/docmend/restore.py#L83)

Apply and restore validate a pathname, then later stat and mutate whatever object that pathname names. The run lock excludes other docmend runs, not editors, sync clients, or other local processes. A controlled replacement after the hash check was silently overwritten and reported as applied.

Required direction: bind validation and commit to one object identity, or repeat identity, containment, and digest checks at the exact commit boundary.

### DMR-07 — A target created after the gate can be overwritten without preservation

- Severity: High
- Confidence: High
- Evidence: [gate.py](../../src/docmend/writer/gate.py#L116) and [apply.py](../../src/docmend/writer/apply.py#L389)

The preservation gate checks only overwrite targets that exist during gate evaluation. Apply checks again later; if the target appeared in between, it switches to overwrite mode without re-evaluating preservation. A controlled rename-only reproduction passed the gate, created the target afterward, and then replaced it without a backup or external-preservation declaration.

Required direction: make overwrite preservation an action-time invariant. Any target present at commit must have a verified preservation strategy, regardless of what the earlier gate observed.

### DMR-08 — The scale contract and acceptance gate are not validly closed

- Severity: High contract failure
- Confidence: High
- Evidence: [test_scale.py](../../tests/test_scale.py#L39), [discovery.py](../../src/docmend/discovery.py#L222), and [config.py](../../src/docmend/config.py#L139)

NFR-001 requires memory independent of corpus size and a parallel execution mode. The implementation retains corpus-wide collections, the parallel settings are accepted but unused, and the test explicitly allows memory to grow by 10 KiB per file.

The opt-in test is also stale. A fresh 1,000-file run failed because manifest 1.3 correctly emits intent plus terminal records while the test still assumes one record per applied action. This invalidates the acceptance evidence; it does not by itself prove that the historical 100,000-file runtime result is false.

Separately, focused measurements found 8, 16, and 32 MiB inputs peaking at 85.7, 168.5, and 336.8 MiB during planning. The default 100 MiB input limit therefore has no demonstrated safe memory envelope.

Required direction: decide and document the intended asymptotic contract, repair and own a scale lane, reject inert parallel settings, and set the file-size limit from a measured working-set budget.

### DMR-09 — Future releases are not bound to the documented release candidate

- Severity: High future-release risk
- Confidence: High
- Evidence: [release.yml](../../.github/workflows/release.yml#L7)

Any matching version tag can publish without proving main ancestry, signature, package-version equality, or successful checks for the exact commit. Most Actions and reusable workflows use mutable tags, including checkout in the write-capable release job.

The current v1.0.2 tag is signed, recent checks are green, and the published wheel and sdist are present with GitHub-computed digests. This finding concerns future release-chain enforcement, not evidence that v1.0.2 was compromised.

## Consolidated Medium Themes

- Stable document identity is not implemented. Planning always mints a new UUID, despite ADR-0008's three-tier recovery contract.
- Artifact readers do not reject duplicate JSON keys, enforce aggregate totals, consistently reject unsupported future versions, or fully align schemas with Pydantic models.
- Public write-capable engine functions can bypass CLI lock and preservation coordination. Fixed writer staging names can block retry after a hard kill.
- Disk preflight checks backup space and source temporary space independently, even when both consume the same filesystem.
- Scan and plan treat timeouts as successful; targeted restore succeeds when no requested ID matches; resume chains lack durable lineage.
- Logs lack a stable terminal event contract, default to metadata-readable permissions under a typical `022` umask, and do not enforce path minimization or redaction at the sink.
- Recovery, privacy, prerequisites, and release documentation overstate some guarantees or omit executable operator procedures.

## Corrected Or Non-Applicable Raw Findings

- GitHub's live dependency graph does ingest the lock: its SBOM reported 82 packages and 122 relationships, including the key runtime dependencies.
- `uv build` builds the wheel from the generated sdist. The remaining release test gap is the shallow installed-product smoke, not absence of an sdist build.
- GitHub's current default workflow permission is read-only, with pull-request approval disabled. Explicit workflow permissions remain useful hardening.
- The current `dev` head is not a declared release candidate, so its distance from v1.0.2 is not a release defect.
- Scanner matches for FastAPI, SQLAlchemy, Svelte, webhooks, containers, databases, background workers, and runtime AI came from prose and research. These product surfaces do not exist in docmend v1.

## Verification Evidence

- Default Python gate: Ruff format and lint clean, BasedPyright clean, 619 tests passed, one opt-in scale test skipped, 97% branch coverage, and `pip-audit` reported no known third-party vulnerabilities.
- Packaging: wheel and sdist built; the isolated wheel exposed `docmend 1.0.2` and included the schemas, `py.typed`, metadata, and console entry point.
- Specification: project-spec validation, strict lint, and the current traceability checker passed. The review separately confirmed that the checker accepts comment-only requirement IDs and does not validate cited pytest nodes.
- Focused safety probes reproduced the plan/backup collision, artifact clobber, out-of-root restore, unjournaled mutation, nonconvergent restore, false-clean verification paths, and pathname replacement race using synthetic temporary corpora only.
- GitHub: protected `main` checks and recent release runs were green; the v1.0.2 signed tag points at the released main/dev baseline.

## Fix Order

1. Fix same-plan path ownership and make backups immutable by action and role.
2. Add source-aware artifact destination checks and guarded report finalization.
3. Introduce the validated manifest-set model and bind every referenced path to the selected corpus before access.
4. Implement apply/restore prepare-and-commit journaling with one lifecycle reducer shared by resume, verify, and restore.
5. Close all false-clean verification paths and add a durable verify result.
6. Close pathname identity races and re-evaluate overwrite preservation at the mutation boundary.
7. Reconcile the scale, identity, parallelism, file-size, and watchdog contracts with executable acceptance evidence.
8. Harden remaining artifact parsers, release automation, observability, and operator documentation.

## Review Artifacts

- [Sweep summary](2026-07-10-2034-codex-review-sweep.md)
- [Sweep manifest](2026-07-10-2034-codex-review-sweep.json)
- [Shared research](2026-07-10-2034-codex-review-shared-research.md)
- Individual lens reports and execution manifests in this directory
