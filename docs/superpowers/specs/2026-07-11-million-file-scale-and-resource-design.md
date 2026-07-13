# Million-File Scale and Resource Contract Design

Approved design for closing DMR-08 from the [comprehensive review synthesis](../../codex-reviews/2026-07-10-2034-comprehensive-review-synthesis.md) before docmend v2.0.0. This document replaces the historical 100,000-file acceptance floor with a one-million-file release qualification and reconciles the binding specification with the implementation's actual whole-run artifact model.

Owner decisions recorded in the design conversation:

- v2.0.0 shall qualify the complete pipeline at 1,000,000 files, not merely 100,000 files.
- v2.0.0 shall use a bounded-linear metadata contract and supported sequential execution. Unsupported parallel settings shall be rejected, never accepted as inert configuration.
- Smaller tiers shall protect pull requests and scheduled development; the full one-million-file run is a release qualification and a regression gate after scale-sensitive changes.

This is the design-stage artifact. The binding change-control work is a new SPEC-VHHB revision, a settled OQ-037 recording the owner decision, and a concurrency ADR superseding `adr-0007-concurrency-primitive-process-pool` before implementation begins.

The safety-core prerequisite is already satisfied on current `dev`: Plan D is merged, and the executable `verify` surface includes `--plan`, repeatable manifest/report evidence, and optional `--out` verify-report publication. Sub-project 2 builds on that landed interface; it does not reimplement or fork Plan D.

## Problem

The current NFR-001 contract and its evidence cannot both be true:

- NFR-001 requires corpus-size-independent memory, no whole-corpus in-memory structures, and working parallel execution.
- DR-001 through DR-003 define inventory, plan, and report as whole-run artifacts. The implementation materializes their records and the global indexes required for collision detection, lifecycle reduction, and exactly-once verification.
- The scale test acknowledges that memory grows with file count and allows `64 MiB + 10 KiB/file`.
- `parallel.*` configuration is parsed but has no runtime consumer.
- The existing scale test calls library APIs in one process, suppresses the normal logging path, spot-checks output, and stops before the binding `verify --plan` workflow.
- The 100 MiB per-file default has no demonstrated working-set envelope; file count and file size are independent resource dimensions.

The historical 100,000-file run remains useful evidence, but it is not a product ceiling and cannot close DMR-08 for v2.0.0.

## Contract

### Corpus count

The supported scale range is one file through 1,000,000 files on one local POSIX machine. The complete installed-CLI workflow shall qualify at the upper bound:

```text
scan -> plan -> apply --write -> verify --plan
```

The qualification corpus is deterministic, generated at run time, synthetic, and never committed. It includes actions, clean no-ops, classified skips, renames, rewrites, encoding conversion, collision-free nested paths, and the current Manifest/Report 2.0 evidence path. Because some classified skips deliberately remain below the supported encoding floor, full-root verification is expected to report their deterministic content findings. Qualification requires that exact expected finding multiset, no unexpected finding, and complete plan coverage; it does not mislabel a corpus containing intentional risky skips as globally clean.

### Memory model

Whole-run artifact metadata may grow linearly with file count. Per-file body content may not accumulate across records.

The initial design guardrails are 8 GiB peak RSS at 1,000,000 files, a 6 KiB/file incremental slope, and a 20% linearity band. These are **provisional, not yet binding specification values**: the only historical evidence is a 100,000-file traced-heap result that excludes `verify --plan`. The first implementation slice builds the subprocess harness, then runs an uninstrumented 100,000-file pilot across every stage, including plan-aware verification. A second SPEC-VHHB change-control revision freezes the release thresholds from the largest observed per-stage RSS value and fitted slope, with 25% headroom, before optimization or the one-million-file qualification begins.

The resulting binding contract shall include:

- an absolute peak-RSS ceiling at 1,000,000 files derived from the pilot and constrained to fit the approved reference environment;
- a maximum fitted incremental peak-memory slope from the measured 10,000, 100,000, and 1,000,000-file tiers, derived from the pilot;
- a linearity band requiring the 1,000,000-file observation to remain close to the prediction from the smaller tiers; and
- each CLI stage runs in a separate process, so a prior stage's in-memory artifact model cannot inflate the next stage's measured peak.

Binding RSS is measured externally from uninstrumented subprocesses. `PYTHONTRACEMALLOC`, `-X tracemalloc`, and equivalent in-process allocation tracing are forbidden in binding runs because tracer state consumes memory and biases the measured slope. Python allocation peaks are collected only in a separate diagnostic lane; they never share a process run with binding RSS measurement. The accepted slope and peak become a versioned, sanitized baseline artifact, not an unrecorded console anecdote. This separation follows the [Python `tracemalloc` documentation](https://docs.python.org/3/library/tracemalloc.html), which explicitly warns that stored traces add memory and CPU overhead.

This contract deliberately does not claim memory independent of corpus size. Inventory, plan, report, and lifecycle records are durable per-file evidence; bounded linear growth is the honest contract for the v2 artifact architecture.

### Individual file size

Corpus cardinality and maximum individual file size are separate acceptance axes. A deterministic size matrix exercises planning, transformation, backup, apply, and verification with representative UTF-8 and legacy-encoding inputs, with and without tool backups.

The default `limits.max_file_size_mib` remains 100 MiB only if the measured peak RSS for one maximum-sized file stays within 2 GiB and the complete operation remains below the per-file watchdog budget on the qualification machine. Otherwise, the implementation derives the supported default from the largest measured size satisfying both bounds and synchronizes the config, specification, README, and tests in the same change. No benchmark result is silently converted into a larger limit.

### Execution model

v2.0.0 supports sequential execution and removes the `parallel.*` namespace from `DocmendConfig`. The default-constructed configuration and an empty TOML file therefore remain valid and preserve the G-006/NFR-006 no-config path. Any legacy `[parallel]` table—including `enabled`, `model`, `workers`, `start_method`, `chunksize`, or `maxtasksperchild` in any combination—is rejected before scanning with a migration-specific input error explaining that parallel execution never shipped and the section must be removed. No parallel field parses successfully and is then ignored; `workers = "auto"` has no sequential alias.

`ProcessPoolExecutor` remains a documented future option, not a v2.0.0 feature. Reopening it requires profiling evidence that sequential execution misses the release's practicality target, a new approved design, equivalence tests, parent-only shared-artifact writes, worker-failure isolation, and a hard watchdog design. The accepted ADR 0007 is superseded because it claims a supported process mode that never shipped.

### Plan artifact compatibility

The durable plan embeds the complete effective config snapshot, and plan schema 1.2 requires the legacy `parallel` object. Removing that object is therefore a plan-contract change, not merely a config-model edit. Plan schema 2.0 removes `parallel` from the required snapshot and otherwise preserves the current plan shape. New v2 plans contain only supported configuration.

docmend v2 rejects every 1.x plan before gate evaluation or mutation with an input error directing the operator to regenerate the plan with v2. It does not silently strip the historical snapshot field or execute an old decision artifact under changed configuration semantics. Inventory compatibility is unchanged; operators may reuse a supported inventory to generate a fresh plan. ADR 0005 and the schema README record this clean break.

### Watchdog

The v2.0.0 sequential engine retains the current cooperative SIGALRM watchdog and documents its actual boundary: it interrupts Python-level discovery, detection, and transform work on the main thread but cannot guarantee termination of a stuck native call. FR-019, ERR-009, operator documentation, and DEV-002 shall use that exact language.

A hard per-file process boundary is coupled to future worker-process support. It is not simulated with a thread timeout or a fresh process per million-file record. Safety claims must describe what the shipped engine proves.

## Qualification Architecture

### Harness

The scale harness first requires a clean checkout, captures `HEAD`, and builds the wheel itself into the external qualification workspace. It then invokes that exact wheel in isolated subprocesses and records its hash, so candidate commit and installed artifact cannot drift independently under the binding runtime assumption below. The measured stages do not import docmend from the checkout. Each stage writes and then rereads the real durable artifact used by the next stage. Apply uses a synthetic external preservation declaration for the cardinality lane and a separate smaller lane with tool backups; both are followed by plan-aware verification.

Binding qualification requires exclusive same-user control from source inspection through acceptance: no concurrent process under the invoking UID may mutate the candidate repository, bound interpreter, qualification workspace, installed package tree, or publication destinations. The harness snapshots and reconciles the console script, interpreter binding and target, archived measurement wrapper, held workspace, and clean source at their boundaries, but it does not claim an immutable runtime against same-UID in-call swap-and-restore, open-inode mutation, ptrace, or process injection. “Invokes that exact wheel” means the hash-verified wheel installed and import-proven in the fresh venv under this quiescent-runtime assumption. A hostile same-UID threat model would require a separately designed immutable runtime sandbox, not partial descriptor plumbing through the existing pathname-based Python import and supervisor boundaries.

The 1,000-file pull-request guard is the deliberate exception to the installed-wheel rule: it runs from the checked-out source inside the existing pytest gate so the standard-owned `scripts/check.py` and workflow remain byte-identical. Installed-wheel subprocess qualification starts at the 100,000-file tier. Packaging itself is independently exercised by sub-project 3's installed-artifact release tests.

The harness captures, per stage:

- exact commit, package version, artifact schema versions, Python version, and dependency lock hash;
- file count and total corpus bytes;
- elapsed time, files per second, and bytes per second;
- externally measured peak RSS for binding runs, or Python allocation peak for separately labelled diagnostic runs—never both in one run;
- inventory, plan, report, manifest, verify-report, and log sizes;
- action, skip, failure, not-attempted, and verified totals; and
- filesystem type plus cold/warm-cache classification, without hostnames, usernames, absolute corpus paths, or document content.

The output is a versioned JSON evidence document validated by a repository schema. Accepted sanitized baselines live under `docs/scale-evidence/accepted/`; sanitized pilot inputs needed to reproduce a binding fit live under `docs/scale-evidence/supporting/` without being labelled accepted; the matching public-safe reference-environment description lives at `docs/scale-evidence/reference-environment.json`. Failed, incomplete, or other diagnostic evidence stays outside the accepted directory and never overwrites the last accepted baseline.

The second specification revision publishes `docs/scale-evidence/thresholds.json`, a versioned, schema-validated threshold baseline that records both pilot point identities and hashes, the reference-environment hash, the fitting method, and the frozen ceiling, slope, and linearity values. Scheduled and release qualification must load and validate that file; prose values in the specification are not the executable threshold source.

Before corpus materialization, the harness computes a deterministic disk and inode budget from the recipe distribution, selected file count, expected whole-run artifact growth, log allowance, largest staging file, and a 25% margin. Insufficient capacity makes the qualification incomplete before it creates the corpus.

### Task 6 contract-completion amendment (2026-07-13)

Task 6 may not be implemented literally on top of the Task 3-5 APIs. Four contradictions must be corrected first: scale-evidence 1.1 cannot truthfully represent a failure before a complete scan and plan; the private supervisor permits a null exit code after spawn/reap failure while public stage evidence does not; the provisional threshold helper applies headroom to the largest 100,000-file observation rather than to the required 1,000,000-file prediction; and the exact-HEAD build needs a fixed build frontend/backend rather than a range-resolved backend outside `uv.lock`. These are contract-completion changes under Appendix B, recorded as non-blocking OQ-041 until the Task 9 pilot/revision-two approval boundary.

Task 6 is therefore split without reordering Tasks 7-12:

- **Task 6A** completes the reusable evidence, threshold, transport, reference-observation, capacity, corpus-summary, and schema-version contracts.
- **Task 6B** builds the exact-HEAD installed-wheel orchestrator, four fresh measured stages, complete artifact reconciliation, evidence publication, and acceptance boundary.

#### Evidence lifecycle and partial truth

Scale-evidence advances from 1.1 to 2.0 before any accepted baseline exists. The major version reflects changed non-passing semantics, not merely additive fields. Thresholds likewise advance from 1.0 to 2.0 because the absolute limit changes from a largest-pilot observation to a 1,000,000-file projection. Reference-environment and private stage-wire schemas remain 1.0.

Public evidence uses these exact rules:

- Invalid syntax, an unsafe or occupied output, a dirty tree, a non-commit `HEAD`, or another refusal before candidate/reference/lock provenance is fixed is an input error and produces no evidence. Every later termination attempts no-clobber publication to `--evidence-out`.
- `preflight` is nullable until the capacity/reference check runs. `outcome_reason` is a finite public code: passing evidence has no reason, and every non-passing document has one.
- `stages` is an ordered unique prefix of `scan`, `plan`, `apply`, `verify`. `completed` means the child was reaped and a trustworthy external measurement exists. The separate `artifact_validated` flag means the stage's required durable artifacts were safely loaded and passed their own schema/identity boundary. These are biconditional public-state rules: `completed=false` forces null exit and memory fields; `completed=true` requires a known exit and exactly one memory measurement; `artifact_validated=false` forces a null public run ID; and `artifact_validated=true` requires `completed`, a trusted run ID, and the exact required artifact-size keys. A measured child whose artifact is missing or invalid therefore remains a stage entry with `completed=true`, `artifact_validated=false`, and no public run ID.
- Totals are always present and contain only observations from validated artifacts. Before a validated scan, scan totals are zero; before a validated plan, plan totals are zero; before a validated apply, apply totals are zero; before a validated verify, verified/observed-finding totals are zero. Recipe-derived expected findings may be present from the start. Passing and completed-correct diagnostic evidence enforce full scan/plan/apply/verify conservation. Failed evidence preserves the discrepant observed totals instead of making the document itself invalid.
- `incomplete` means build, install, preflight, materialization, supervisor, telemetry, or missing/invalid-artifact behavior prevented the qualification from proving product correctness. `failed` means trustworthy execution exposed an unexpected exit, conservation/coverage/finding discrepancy, threshold miss, or runtime miss. `diagnostic` means the complete correctness contract passed but the run was explicitly diagnostic or the reference class was non-binding. `passing` means a binding reference, exact installed-wheel provenance, four completed/artifact-validated stages, zero child swap, exact correctness, and every applicable threshold/runtime verdict passed. This precedence prevents environmental failures from masquerading as product failures and prevents product failures from being downgraded to incomplete.
- Artifact-validated stage keys are exact: scan has `inventory`, `structured-log`, `stdout-log`, and `stderr-log`; plan substitutes `plan`; apply has `report`, `manifest`, and the three log keys; verify substitutes `verify-report`. A measured but non-validated stage may publish only the strict subset it actually validated. Public evidence records sizes only, never paths or log content.
- The product artifact-version map is derived from owner constants for inventory, plan, report, manifest, verify-report, and frontmatter. Frontmatter gains a code-owned `FRONTMATTER_SCHEMA_VERSION`; no qualification code duplicates the literal.

#### Threshold context and exact verdicts

The threshold loader reads each referenced pilot document once through the safe no-follow snapshot boundary and returns a frozen context containing the baseline/digest plus stage-aligned 10,000- and 100,000-file RSS values. Evaluation never rereads mutable pilot paths. Acceptance performs a final baseline digest/limits check so a post-load replacement cannot be accepted.

For stage `s`, let `m10[s]` and `m100[s]` be the validated pilot peaks, and define with exact `Fraction` arithmetic:

```text
g[s]    = max(0, (m100[s] - m10[s]) / 90_000)
p[s,n]  = max(m10[s], m100[s], m10[s] + g[s] * (n - 10_000))
```

Threshold schema 2.0 fixes `target_file_count = 1_000_000`. Its absolute limit is `ceil(1.25 * max_s p[s,1_000_000])`; its slope limit is `ceil(1.25 * max_s g[s])`; and its linearity tolerance is exactly `1/5`. The 10,000-file point may be explicitly diagnostic but must otherwise meet passing-quality provenance, preflight, stage, swap, conservation, coverage, and finding rules; the 100,000-file pilot point must pass. Both points bind the same commit, wheel, lock, build versions, artifact versions, reference, Python/kernel versions, and warm-cache class.

At scheduled 100,000 files, observed slope is `max_s max(0, (current100[s] - m10[s]) / 90_000)`. At release, observed slope is `max_s max(0, ols_s)`, where `ols_s` is the exact least-squares slope for stage `s` over 10,000, 100,000, and 1,000,000 files. At either count, linearity is `max_s(abs(current[s] - p[s,n]) / p[s,n])`, and peak is the maximum current stage RSS. Comparisons stay rational; the public slope is upward-ceiled to an integer and the public ratio is upward-rounded to 12 decimal places so serialization cannot turn a failure into a pass.

Only release evidence may carry a workflow-runtime verdict. A release failure before scan dispatch has `workflow_runtime=null`; once scan dispatch begins, release evidence records the elapsed/limit/pass object even if a later stage stops. Passing or otherwise-complete release evidence requires it. Monotonic timing begins immediately before dispatching the scan supervisor and ends after receipt and validation of the last attempted result, including inter-stage artifact validation but excluding build/install, reference checks, corpus materialization, and evidence publication. For a complete release, public workflow elapsed is at least the sum of the four public stage elapsed values; the publisher uses the greater of the observed outer duration and that sum so rounding remains conservative. The limit is exactly 43,200 seconds; equality passes. The harness records a miss after the pipeline returns rather than claiming it can safely hard-kill a native stall.

#### Exact-HEAD build and workspace

The repository fixes both `uv 0.11.6` and `uv_build==0.11.6`; evidence records both versions. The orchestrator refuses another frontend version. It captures a 40-hex commit from a clean tree, creates a mode-0700 absent workspace outside the checkout, archives that commit with `git archive`, safely extracts it, and builds from the immutable snapshot with `uv build --wheel --no-sources --force-pep517`. It requires one regular non-symlink wheel, hashes it, validates wheel metadata against the captured project name/version, and installs it without dependencies into a fresh venv whose runtime closure came from `uv export --locked --no-dev --no-emit-project --no-sources` and a hash-required install. `uv pip check` and an isolated import-origin probe must prove that `docmend` and its scale modules resolve beneath the venv.

The orchestrator rechecks exact `HEAD` and the full tracked/untracked status after archive, build, install, qualification, and immediately before acceptance. The normal evidence path stays outside the checkout or is written only after the final clean check; explicit acceptance is the only permitted operation that may add a repository file.

Each measured stage is launched by a fresh supervisor process using the candidate venv's isolated Python and the wrapper from the immutable source archive. The supervisor launches exactly one absolute candidate-venv `docmend` executable. Its private environment roots `HOME`, `XDG_STATE_HOME`, `XDG_CONFIG_HOME`, and `TMPDIR` inside the held workspace; fixes `LANG`/`LC_ALL` to `C.UTF-8` and `TZ` to `UTC`; and retains the Task 5 tracing/user-site exclusions. The workspace is never cleared or reused, all private request/result/output files are owner-only, and failure residue is preserved for diagnosis without following mutable names.

#### Reference observation, cache class, and provisional capacity

Reference capture derives public fields from injected Linux/platform probes. Storage classification never trusts an operator assertion: memory/network filesystems classify directly; eligible ext4/XFS filesystems traverse `/sys/dev/block/<major>:<minor>`, while btrfs uses unprivileged `BTRFS_IOC_FS_INFO` on the workspace to bind the exact filesystem ID and device count before enumerating `/sys/fs/btrfs/<FSID>/devices`. Every resulting member follows all device-mapper/slave leaves and their `queue/rotational` values. All zero is `local-ssd`, all one is `local-hdd`, and mixed, incomplete, absent, unreadable, or otherwise unprovable telemetry is `unknown` and non-binding. Filesystem/device identities and paths remain private. The immutable reference reader returns the validated model and SHA-256 of the same bytes.

The freshly materialized corpus is classified `warm`: its writes populate the page cache, and the harness neither requires privilege nor pretends to drop system caches. A future cold-cache lane requires separate design and does not alter this binding class silently.

Build/install occur before the capacity check, so their actual allocation is already reflected in free space. Before corpus materialization, the provisional pre-pilot requirement adds the exact corpus allocation/inodes and largest rendered file from `summarize_scale_corpus` to these versioned allowances, rounding each named file estimate to the observed fragment size:

| Allowance | Pre-pilot value |
| --- | --: |
| Fixed non-corpus reserve | 256 MiB |
| Inventory | 2,048 bytes per input |
| Plan | 4,096 bytes per input |
| Report | 2,048 bytes per action |
| Manifest | 8,192 bytes per action |
| Verify report | 1,024 bytes per input |
| Structured logs | 4,096 bytes per input per stage (four stages) |
| Supervisor request/result/stdout/stderr | Four 2 MiB files per stage (8 MiB/stage; four stages) |
| Atomic artifact staging | Maximum of the inventory, plan, report, and verify-report estimates |
| Writer staging | Largest rendered recipe rounded to fragment size |
| Additional non-corpus inodes | 64 |

`qualification_requirements(workspace, corpus, artifact, supervisor, summary)` accepts four identity-held `CapacityPlacement` values. Each placement names an existing no-follow probe directory and its own observed positive `statvfs.f_frsize`; the absent corpus root uses its held existing parent. `ScaleCorpusSummary` records the corpus fragment size that produced its allocation and must match the corpus placement. The function emits four placement-aware requirements before grouping: corpus gets exact corpus allocation/inodes plus one largest-file writer staging allocation/inode rounded with the corpus fragment; artifact gets the five durable artifact estimates, four structured-log files, one maximum atomic staging file, and their ten inodes rounded individually with the artifact fragment; supervisor gets sixteen separately rounded 2 MiB private files and sixteen inodes using the supervisor fragment; workspace gets the fragment-rounded 256 MiB base plus 64 additional non-corpus inodes. Requirements are then grouped by followed `st_dev`, and the existing exact 25% byte/inode margin is applied once per filesystem. Materialization must reproduce the fragment-bound preflight corpus summary exactly. If actual artifact/log growth exceeds any named allowance, the run is `incomplete` with `capacity-estimate-exceeded`; it never accepts evidence based on an under-estimate. Pilot revision two may raise coefficients to observed maxima rounded upward, but never lowers them automatically.

#### Publication and process exits

`--evidence-out` names one absent operator-controlled file outside the checkout. `--accept-to` names an existing accepted directory and is legal only for a binding request. The derived cardinality filename is `{40-hex-commit}-{tier}-{count}.json`; file-size evidence uses `{40-hex-commit}-file-size.json`. The orchestrator publishes ordinary evidence first and then publishes identical canonical bytes to the derived accepted name only when status is `passing`; neither destination is overwritten. An acceptance race preserves ordinary evidence and exits non-zero.

The command exits 2 for pre-run invocation/provenance/output refusal and produces no evidence. It exits 0 for passing evidence, successful reference capture, or an otherwise-correct explicitly requested diagnostic. Failed and incomplete evidence exit 1. A binding request whose reference mismatches completes as diagnostic evidence but exits 1; explicit `--diagnostic` makes the same otherwise-correct result exit 0. Downstream stages stop at the first stage that cannot satisfy its required exit/artifact boundary. When more than one condition exists, status first prefers a trustworthy correctness/threshold/runtime failure over incomplete or diagnostic classification, then selects one finite reason in this order: `stage-exit`, `conservation-mismatch`, `finding-mismatch`, `threshold-exceeded`, `runtime-limit-exceeded`; absent those, the first lifecycle blocker in execution order; then `reference-mismatch`; then `explicit-diagnostic`.

### Reference environment

Binding 100,000- and 1,000,000-file runs require:

- Linux with local POSIX semantics;
- at least 16 GiB physical RAM;
- a disk-backed local SSD filesystem—ext4, XFS, or btrfs—not tmpfs, ramfs, overlayfs, NFS, SMB, or another network filesystem;
- enough free bytes and inodes to pass the harness preflight; and
- no material swap activity during the measured stages.

The accepted reference file records CPU model/architecture, logical CPU count, RAM, storage class, filesystem type, an allowlisted set of relevant flag-only mount semantics, Python version, and kernel version, but no hostname, username, absolute path, serial number, or device identifier. Mount options with values, paths, user or credential data, device identifiers, or unknown keys are rejected from public evidence. A release qualification must match the accepted reference class; a materially different environment produces diagnostic evidence, not a replacement binding baseline.

### Test tiers

| Tier | Trigger | Corpus | Purpose |
| --- | --- | --: | --- |
| Pull request | Default Python gate | 1,000 files | Fast conservation, artifact, and gross memory-regression guard. |
| Scheduled/manual | Weekly and `workflow_dispatch` | 100,000 files | Full installed-CLI workflow, trend comparison, and intermediate slope point. |
| Release qualification | Exact v2.0.0 candidate and scale-sensitive changes | 1,000,000 files | Binding upper-bound acceptance and published release evidence. |
| File-size matrix | Manual and before limit changes | Derived size cases through the configured maximum | Per-file working-set, timeout, and backup envelope. |

The release workflow may publish only the candidate commit whose complete gate and one-million-file evidence both passed. Sub-project 3 (DMR-09) owns the exact workflow binding and provenance mechanism; this design owns the evidence format and qualification command.

The sequential practicality target is completion of the full one-million-file workflow within 12 hours on the accepted reference environment. Exceeding that bound reopens the concurrency decision; it does not silently enable the former process-pool configuration.

### Correctness

Sampling is insufficient at the release tier. The qualification reconciles every record through artifact totals and `verify --plan` exactly-once coverage. It additionally selects deterministic boundary samples from every recipe class for byte/hash/encoding checks. The invariant is not merely that the command completed: every input is accounted for as exactly one action, clean no-op, or classified skip, every plan action has exactly one certified terminal outcome, and verification findings equal the recipe-derived expected multiset exactly. An expected finding for an intentionally unmodified skip does not excuse an additional or missing finding.

## Resource Observability

Scale runs need content-free liveness signals. Every long-running stage emits:

- a start event naming the stage and input count when known;
- a best-effort heartbeat targeting 30-second intervals, emitted between records and whenever the interpreter can schedule the aggregate-only emitter, containing processed count, elapsed time, rate, and aggregate error/skip counts;
- a terminal event containing final totals, elapsed time, artifact sizes, and peak RSS when supported; and
- an explicit incomplete terminal event on handled failure.

Heartbeat and terminal events never contain document bodies. Path-bearing per-file logs remain confidential runtime artifacts and receive the permission, redaction, placement, retention, and purge treatment owned by sub-project 4.

The heartbeat is not a false hard-liveness guarantee: the sequential cooperative watchdog cannot guarantee scheduling during a native call that holds the interpreter. Silence longer than `limits.per_file_timeout` plus one heartbeat interval means the run may be stalled in native work and requires operator investigation; documentation must not describe silence as proof of a crashed process.

Disk preflight accounts per filesystem rather than independently double counting destinations on the same mount. It includes tool backups, the largest simultaneous staging requirement, manifest/report/verify-report growth, and the configured log budget. Qualification records actual artifact growth so the preflight coefficients are evidence-based.

## Error Handling

- Unsupported parallel configuration is exit 2 (input error), before scanning.
- A scale threshold miss fails the qualification and preserves its evidence; it never weakens the threshold automatically.
- Resource measurement unavailable on a platform is explicit. The release qualification must run where binding RSS measurement is supported.
- Corpus generation or disk-capacity failure is an incomplete qualification, not a product correctness failure; it still exits non-zero and records the environmental cause.
- A missing, unreadable, or schema/identity-invalid required artifact makes the run incomplete because its facts are not trustworthy. A safely loaded artifact whose valid facts disagree with corpus conservation, plan coverage, lifecycle, or the expected-finding multiset is a correctness failure regardless of performance results.

## Testing

Implementation follows TDD and adds:

- configuration tests proving every unsupported parallel shape is rejected and sequential/default shapes are accepted;
- scale-harness unit tests for sanitized evidence, threshold evaluation, incomplete runs, and baseline non-overwrite;
- checked-out-source end-to-end tests for the 1,000-file PR tier;
- multi-point slope tests using deterministic synthetic measurements so the threshold math is testable without allocating a million files in unit tests;
- a real 100,000-file scheduled qualification;
- a real 1,000,000-file release qualification;
- file-size working-set tests covering planning, apply, tool backups, and verification;
- heartbeat/terminal-event tests using a fake clock and aggregate-only event assertions;
- disk-preflight tests for shared and distinct filesystems; and
- regressions proving manifest 2.0 line counts, report totals, plan coverage, and verify-report publication at scale.

The existing `tests/test_scale.py` is replaced rather than retained as a competing authority. Its deterministic recipe mix and conservation assertions feed the 1,000-file default-gate test; its `DOCMEND_SCALE` and `DOCMEND_SCALE_COUNT` controls move to the dedicated qualification command and are removed from pytest once the 100,000-file successor passes. The old tracemalloc ceiling and spot-only verification are deleted.

The full local Python and documentation gates remain mandatory. The scale evidence supplements them; it never substitutes for correctness, typing, coverage, dependency, specification, or documentation validation.

## Change-Control and Evidence Follow-Through

The ordered design-to-qualification sequence is:

1. Add and settle OQ-037 as the canonical owner decision for the one-million-file, bounded-linear, sequential v2.0.0 contract and its two-step threshold settlement; preserve the older resolved questions as historical inputs rather than silently rewriting their decisions.
2. Revise SPEC-VHHB: NFR-001, G-006, §3.1, §7.3/IR-006, DR-002, §8.1/§8.5, §9, §12.1/ERR-006/ERR-009, §14, §17.2/§17.3, §18.2/§18.5, §19 MS-5, §20, and DEV-002, with cross-references from the superseded scale/concurrency assumptions to OQ-037. This first revision makes the one-million-file target, bounded-linear model, sequential-only configuration, plan 2.0 clean break, pilot method, and provisional guardrails binding without pretending the numeric RSS thresholds are already measured.
3. Add a new accepted ADR superseding `adr-0007` with the sequential v2.0.0 contract, removed parallel configuration surface, migration error, and evidence-triggered reopen criteria. Update reciprocal metadata, the ADR index, and backlog.
4. Amend ADR 0005 and the schema documentation for plan 2.0: remove `parallel` from the config snapshot, reject 1.x plans with a regeneration message, and preserve inventory compatibility.
5. Specify the scale-evidence artifact's identity, validation, retention, public-safe fields, accepted repository location, and reference-environment record in SPEC-VHHB; implement its JSON Schema and harness as the first TDD slice after change control.
6. Run the uninstrumented 100,000-file per-stage RSS pilot, including `verify --plan`, on the accepted disk-backed reference environment. Use the recorded peak and slope plus 25% headroom to author the second SPEC-VHHB revision that freezes the numeric memory thresholds before optimization and the one-million-file qualification.
7. Regress NFR-001 to Partial until the one-million-file qualification passes; do not carry the historical 100,000-file result forward as v2 evidence.
8. Update `docs/TODO.md`, `docs/STATUS.md`, and handoff plan pointers so DMR-08 remains visibly release-blocking through qualification.

Sub-project 2 ends only when the exact candidate implementation passes the full correctness gate, the 100,000-file scheduled tier, the one-million-file release qualification, and the file-size envelope; the accepted evidence is recorded without private paths or corpus content.
