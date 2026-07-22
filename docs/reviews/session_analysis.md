# Session Analysis: Code Simplification Review

## Executive summary

The code-simplification review ultimately succeeded: it reviewed all 40 in-scope Python files at commit `834f07515a5308edd2d6c97f1cf940233c2e6b01`, left source and project configuration unchanged, and produced eight independently reviewed actionable findings. The path to that result was substantially more expensive and interruption-prone than the repository, threat model, or deliverable justified.

The central problem was not insufficient model capability. It was a mismatch between the operating context and the prompt's assurance model. The prompt described a forensic, adversarial, shared-workstation audit while the actual context was a trusted personal repository on a secure, private, single-developer workstation. Harmless local state—askpass helpers, Python bytecode, Hypothesis caches, directory `ctime`, and inode replacement—was consequently treated as if it could invalidate the review's source evidence.

That mismatch produced:

- one immediate preflight stop over inherited askpass variables;
- two nominally terminal `execution-blocked` outcomes over ignored cache metadata while `HEAD` and tracked source remained unchanged;
- one user-aborted restart caused by ambiguous continuation semantics;
- repeated guard-construction, sandbox, scanner-launcher, and resume-preflight retries;
- 29 registered workstreams and 10 model sessions for 40 source files and eight actionable findings;
- 326.2 million raw model tokens across the coordinator and workers, of which 96.8% of input was cached context;
- 660 requested integrity-check expressions, many after purely read-only commands;
- seven coordinator context compactions and 20 worker compactions; and
- repeated user intervention to authorize recoveries that could have been automatic under a proportional policy.

The prompt should not simply be shortened. It should be reorganized into assurance tiers:

1. A concise default mode for trusted personal repositories.
2. Candidate-specific add-ons for public API, deletion, dependencies, concurrency, persistence, security, or high-blast-radius changes.
3. An explicitly selected forensic mode for untrusted repositories, shared worktrees, formal compliance evidence, or commands with unknown external effects.

The original prompt is suitable as source material for the third tier, after removing the unsatisfiable `ctime`/inode invariant. It is not a good default.

## Scope and method

This report analyzes the code-simplification review session that began at `2026-07-22T00:34:18Z` and completed at `2026-07-22T13:20:16Z`. It covers the original prompt, coordinator behavior, worker behavior, tool execution, context management, interruption and resume handling, report auditing, and token use.

Per the owner's instruction, the scope-guard hook is excluded as a cause. Messages sent in response to it are considered only where they exposed a broader continuation or override problem that also affected non-hook incidents.

Evidence came from:

- the owner-local primary rollout transcript;
- nine worker rollout transcripts;
- the three review-run directories under `.scratch/code-simplify/`;
- the final workstream manifest, incident records, audit records, and publication receipt;
- the immutable audited report draft; and
- the current durable report, inspected read-only for comparison with its publication receipt.

Evidence aliases used below are:

| Alias | Evidence |
| --- | --- |
| `T` | Owner-local primary rollout transcript; the exact path and session identifier are intentionally omitted from this public report |
| `R1` | `.scratch/code-simplify/20260722T004716Z-834f07515a53/` |
| `R2` | `.scratch/code-simplify/20260722T104238Z-834f07515a53/` |
| `R3` | `.scratch/code-simplify/20260722T113413Z-834f07515a53/` |

Transcript line references identify JSONL records, not lines within the embedded prompt. Prompt-line references identify the 520-line prompt extracted from `T:10`.

Evidence collection and report authoring were read-only except for this report. No source, test, configuration, or prior review file was intentionally edited. Repository handoff documents were updated afterward under the owner's explicit closeout authorization.

## Quantitative profile

### Request and deliverable size

| Measure | Result |
| --- | --: |
| Original prompt | 520 lines, 9,760 words, 75,207 bytes |
| In-scope Python files | 40 |
| Registered workstreams | 29 |
| Completed or adopted-complete workstreams | 24 |
| Failed, interrupted, boundary-failed, or superseded workstreams | 5 |
| Actionable findings | 8 |
| Retained/do-not-apply findings | 7 |
| Manual-review findings | 3 |
| Immutable final report draft | 858 lines, 10,343 words, 87,464 bytes |
| Three run directories | 24,260 files, about 305 MiB allocated |

The resulting process used roughly 0.73 workstreams per source file and produced one actionable finding per 3.6 workstreams. This ratio does not prove that a workstream was individually wasteful, but it shows that orchestration became a first-class workload rather than a light aid to review.

### Time

| Measure                                               |           Result |
| ----------------------------------------------------- | ---------------: |
| Wall-clock session duration                           | 12 h 45 min 58 s |
| Coordinator active-turn time                          |  4 h 28 min 38 s |
| Time between coordinator turns                        |  8 h 17 min 20 s |
| Dominant owner-offline pause                          |  8 h 10 min 32 s |
| Worker active-turn time, overlapping coordinator time |   8 h 39 min 9 s |
| Recorded agent/tool waits                             |      54 min 35 s |

The overnight interval after the first terminal block was not tool latency. It was a user-offline wait caused by a process that required owner intervention before it could resume.

### Model usage

Terminal cumulative counters were taken once from each distinct rollout. Intermediate cumulative snapshots were not summed.

| Metric                               | Coordinator plus nine workers |
| ------------------------------------ | ----------------------------: |
| Input tokens                         |                   324,637,316 |
| Cached input, included in input      |                   314,255,872 |
| Uncached input                       |                    10,381,444 |
| Output tokens                        |                     1,574,150 |
| Reasoning output, included in output |                       606,746 |
| Total, input plus output             |                   326,211,466 |

Cached input was 96.8% of all input. Across 2,644 token snapshots/model steps, average input was about 122,800 tokens per step, while average uncached input was only about 3,900 tokens. The dominant raw-token cost was therefore repeated invocation with large retained contexts—not creation of the final prose.

The weekly usage meter rose from 3% at the first snapshot to 18% at the terminal snapshot. This observed 15-percentage-point increase is consistent with the owner's experience, but it is not a billing equation: the meter is rounded, applies to the plan window, may include other account activity, and does not expose the relative weighting of cached input, uncached input, output, and reasoning.

### Where model usage went

| Session group                       | Raw tokens | Share |
| ----------------------------------- | ---------: | ----: |
| Coordinator                         |  118.007 M | 36.2% |
| First five semantic workers         |  143.797 M | 44.1% |
| Three fresh post-incident verifiers |   38.167 M | 11.7% |
| Final auditor                       |   26.240 M |  8.0% |

The nine worker rollouts consumed 63.8% of total raw tokens. All semantic scanning, verification, and final auditing used the same high-cost Ultra class, even though the original prompt permitted lighter models for deterministic or read-heavy discovery. Ultra was justified for coordination and subtle adjudication; it was not necessary for every scan, inventory, and low-risk verification pass.

### Tool and orchestration load

| Recorded operation               | Count |
| -------------------------------- | ----: |
| Outer `exec` calls               | 2,288 |
| `wait_agent` calls               |    85 |
| Agent messages                   |    57 |
| Agent follow-up tasks            |    33 |
| Agent status listings            |    29 |
| Yielded-execution waits          |    18 |
| Spawn attempts                   |    12 |
| Worker rollouts actually created |     9 |
| Agent interrupts                 |     8 |
| Context compactions              |    27 |

The review requested 660 explicit integrity-check expressions across 655 execution envelopes and another 51 explicit Git-status probes. Checker-bearing envelopes represented 28.6% of all execution envelopes. The final guard contained 65,753 entries, and the final auditor applied it after ordinary evidence reads. This was a direct implementation of the prompt's “after every tool” rule, not incidental shell noise.

## Non-scope-guard interruption chronology

The table distinguishes actual stops from nonterminal retry overhead. It includes all material interruption patterns found in the transcript and run evidence.

| UTC | Event | Classification | Cause and impact | Evidence |
| --- | --- | --- | --- | --- |
| 00:36–00:41 | Inherited `GIT_ASKPASS` and `SSH_ASKPASS` | Actual preflight stop | The prompt grouped credential-prompt helpers with repository-redirection variables and forbade sanitizing them. The user had to request a resolution and then authorize a same-session override. No files were written. | `T:70-80`, `T:86-119`, `R1/progress.md:13` |
| 00:43–00:51 | Git-flag incompatibility and guard self-inclusion | Nonterminal retry | `GIT_LITERAL_PATHSPECS=1` conflicted with a `git check-ignore` invocation. Separately, the pre-write guard included metadata for a scratch parent created during initialization, so the guard detected its own setup. The guard was deleted and rebuilt. | `T:224-236`, `R1/evidence-index.md:14-15` |
| 00:55–00:58 | Bubblewrap bootstrap failures | Nonterminal retry | The first sandbox mounted a path below a read-only root incorrectly. The second omitted `/dev` and `/proc`, causing five `uv` interpreter-query failures. A third recipe corrected both. | `T:340-374` |
| 01:04–01:12 | Three artificial pytest failures | Baseline-invalidating retry | The read-only sandbox prevented the CLI's intentional `.docmend/*.jsonl` logging side effect. A 137-second full suite failed, focused diagnosis established `EROFS`, and the full 1,728-test suite was rerun with `.docmend` writable. | `T:458-613`, `R1/evidence-index.md:31-35` |
| 01:08 and 12:27 | Scratch-state patch context misses | Minor retry | Two exact patches used stale context or a mismatched shell-variable spelling. They were retried after rereading the target state. | `T:535-542`, `T:3368` |
| 01:19 onward | Optional-scanner launcher failures | Nonterminal retry | Literal escaped newlines broke an inline Python command; npm configuration was initially unsuitable; mode-0644 wrappers were executed directly before being invoked through Bash. These were harness defects, not scanner findings. | `T:699-761`, `R1/ultra/deterministic/result.md:10-23` |
| 02:13–02:18 | Cache and bytecode metadata drift | First terminal execution block | Verifier commands escaped cache/bytecode redirection and changed Hypothesis, pytest, project, and virtual-environment cache state. Paths, contents, modes, sizes, and mtimes were restored, but five `ctime` values and one inode could not be restored. `HEAD` and tracked source were unchanged. The run nevertheless ended terminally. | `T:1568-1660`, `R1/execution-blocked-incident.md:3-15` |
| 10:29–10:31 | “Restart” interpreted as rediscovery | User-aborted turn | After “Continue,” the assistant required an owner phrase containing “restart,” then announced a new run rather than adoption of the last verified checkpoint. The user stopped the turn and clarified “Start where you left off.” | `T:1673-1707` |
| 10:40–10:46 | Mode-000 predecessor fixture | Resume-preflight retry | The new guard recursively hashed the prior run and encountered an intentionally unreadable pytest fixture. The prior run then had to be treated as adopted, metadata-only evidence. | `T:1781-1837`, `R2/preflight.json:14-30` |
| 11:21–11:26 | One Hypothesis `.pyc` and directory metadata drift | Second terminal execution block | A paired-snapshot verifier used raw `uv run python`, pytest, and `pytest.main()` without bytecode suppression or common isolation. One `.pyc` appeared in `.venv`; the parent `ctime` changed. Tracked source and `HEAD` were unchanged. Three verifier lanes were later rerun after another owner override. | `T:2412-2551`, `R2/coordinator/integrity-incident-20260722T111949Z.md:3-38` |
| 11:34–11:36 | Guard diagnostic-text mismatch | False alarm | Stored and current rows differed only in explanatory wording: “mode 000 prior-run test fixture” versus “mode 000 prior-run fixture.” The checker compared prose as state and briefly paused launches. | `T:2623-2646` |
| 12:31–12:59 | Fresh final audit | Expected work with disproportionate latency | No defect blocked progress. The auditor reread broad evidence and ran the 65,753-entry checker after every read, making assurance mechanics the dominant audit latency. | `T:3416-3731`, `R3/evidence-index.md:12,28-30` |
| 13:06–13:16 | Stale “as above” reference | Legitimate publication block | Reordering do-not-apply findings left D-004 pointing to unrelated D-003. The auditor correctly required self-contained wording. The fix did not change any disposition, count, or implementation order, but exact-byte re-audit took about ten minutes. | `T:3889-4071`, `R3/ultra/final-audit/reaudit.md:14-30` |

The first askpass stop followed the prompt literally. The two cache incidents also followed the prompt once the coordinator interpreted `ctime` and inode identity as terminal invariants. The problem was therefore not simply that the assistant ignored a reasonable procedure. The procedure itself made normal Python cache behavior unrecoverable.

## Root-cause analysis

### 1. The default threat model was disproportionate

The prompt assumed that repository files, ignored files, test plugins, Git configuration, filters, wrappers, package metadata, and tool output could all be hostile. That posture is defensible for an unknown third-party repository or a formal evidence-preservation exercise. It was disproportionate for a known personal project on a private workstation.

Because the prompt did not declare an assurance mode, the strictest rule always won. “Operate autonomously” could not override explicit instructions to stop on ambient askpass helpers, exact metadata drift, missing fresh verifiers, or a late audit inconsistency.

### 2. The filesystem integrity invariant was unsatisfiable

Prompt lines 60–68 required a guard for pre-existing ignored and untracked paths. Prompt line 293 required comparison after every tool. The implementation included directory metadata, `ctime`, and inode identity.

Creating and deleting a file necessarily changes parent-directory `ctime`; ordinary user-space code cannot restore it. Replacing a generated cache file can also change inode identity while restoring identical bytes, mode, size, and mtime. Therefore the process could not both permit run-attributable cleanup and require exact post-cleanup metadata identity.

This is the most important technical correction: integrity should be defined in terms of semantic assets—Git refs/index, tracked and user-authored content, type, mode, existence, and intended write boundaries—not volatile cache metadata.

### 3. Safety constraints were prose-only at worker boundaries

Both terminal incidents came from worker code-loading commands that bypassed the intended cache redirection and bytecode suppression. The prompt instructed workers to be careful but did not give them a mandatory, coordinator-owned launcher. The second incident repeated the first after the failure mode was already known.

For strict execution, technical confinement must replace repeated prose: one tested command wrapper, writable scratch, bytecode disabled, known cache variables, and read-only mounts only where necessary. For default trusted execution, the repository's existing command can run directly with redirected caches and a post-command tracked-file check.

### 4. The state model confused objective, run, and integrity epoch

The persistent objective was “finish the code-simplification review at this SHA.” A scratch run directory was only one evidence envelope. A cache incident invalidated that envelope's exact metadata claim, not the semantic work already completed at the same SHA.

The prompt exposed only terminal statuses and did not define:

- a recoverable integrity incident;
- an owner-approved baseline rollover;
- adoption of same-SHA evidence;
- override scope or expiry;
- the meaning of bare “Continue”; or
- the difference between restarting an objective and replacing an integrity epoch.

The assistant first said a new Codex session was required, then accepted a same-session override. Later it said the review must restart, then resumed from the old checkpoint after user correction. These inconsistencies were predictable consequences of missing state semantics.

### 5. Mandatory independent verification was too broad

The prompt defined a candidate as non-trivial if it touched more than one module, changed control flow, deleted executable code, altered an import or patch point, affected a public or registered symbol, added a dependency, lacked direct tests, or involved several other common review conditions. Each such candidate required a fresh non-proposer verifier, often with a two-stage conclusion-blind exchange.

That threshold captured nearly every useful simplification. It also conflicted with the instruction to use the fewest coherent workstreams. The result was 29 workstreams, repeated follow-ups to long-lived workers, three fresh recovery verifiers, and 20 worker compactions.

Independent scrutiny was valuable, but it should have been batched for low- and medium-risk private changes and dedicated only to high-risk candidates.

### 6. The behavior envelope elevated implementation accidents into contracts

The prompt universally preserved callable identity, precise evaluation counts, allocation timing, caller and traceback shape, callable metadata, private reflection, random-state consumption, stack inspection, and externally observable timing. It did not first ask whether the repository supported or observed those properties.

This forced verification against theoretical CPython observability rather than the project's supported behavior. Examples in the final retained-findings section include keeping a literal tuple because tracer mutation or cross-execution identity might observe a difference and keeping an unreachable built-in-`str` guard because an adversarial subclass could override `split`.

The correct boundary is documented, tested, public, supported-input, and repository-observed behavior. Private frame shape, code-object identity, pure-helper call count, negligible allocation timing, line-tracer mutation, and adversarial built-in subclasses should be contracts only when repository evidence makes them so.

### 7. The report and audit contract was recursive

The fresh auditor had to inspect a complete draft, while the draft's final-audit section had to contain the auditor verdict, final Git status, integrity result, and publication facts that did not yet exist. This forced placeholders, post-audit substitutions, re-audit, publication, and a separate completion audit.

The current durable report also no longer matches its audited publication hash. The audited draft and receipt record SHA-256 `b4dfa368…` at 87,464 bytes; the current file is `e0c79845…` at 87,700 bytes. The observed diff contains only Prettier-style table alignment and one blank line. The actor was not established, so this report does not attribute the write. The observation nevertheless demonstrates that an exact Markdown-byte receipt is brittle and has little value when semantic content and deterministic validators are the real contract.

### 8. The harness was assembled during the review

Bubblewrap mounts, npm isolation, wrapper invocation, cache redirection, report linting, and the filesystem guard were developed and corrected live. That produced several minutes of avoidable retries and exposed workers to inconsistent execution rules.

The original prompt itself anticipated the better design in its reusable-skill note: keep orchestration and safety gates concise, move detailed rubrics to one-level references, and implement baseline, coverage, report-lint, and dependency-evidence collection as tested scripts. That recommendation should be implemented before this workflow is run again.

## Prompt design assessment

### Controls to retain by default

- Anchor the review to a commit and verify that `HEAD` remains stable.
- Validate include and exclude paths without allowing worktree escape.
- Refuse to overwrite an existing report; publish atomically or with exclusive creation.
- Keep source, tests, configuration, manifests, and lockfiles read-only during analysis.
- Record the actual baseline command, tool versions, exit status, and non-pass identities.
- Read every in-scope source file when full coverage is requested.
- Search repository-wide callers, exports, registrations, tests, and documentation when a candidate affects a symbol contract.
- Preserve documented/public behavior, meaningful errors, ordering, side effects, persistence, cleanup, concurrency, and supported malformed-input behavior.
- Prevent secrets from entering logs or reports, and never upload repository content.
- Use independent review for high-risk or high-blast-radius findings.
- Validate the final Markdown and perform one substantive report audit.

These controls materially improved the result. Independent review rejected candidate proposals that would have changed semantics, qualified a CPU-parsing proposal, and caught a stale cross-reference before publication. The problem was universal application, not the existence of scrutiny.

### Controls to simplify

| Control | Recommended default |
| --- | --- |
| Git environment | Construct a known child environment. Reject structural repository/index/object/config redirects when the expected repository cannot be established. Unset pager, prompt, external-diff, and askpass helpers for local reads; record sanitization without stopping. |
| Clean tree | Require stable `HEAD` and clean tracked source plus evidence paths. Record unrelated dirtiness. If baseline behavior would be affected, use an isolated worktree or ask once which snapshot is authoritative. |
| Integrity | Compare Git state and tracked content at start, after code-loading commands, at phase boundaries, and before publication. Separately snapshot non-cache ignored/untracked user paths by path, existence, type, mode, size, and local content hash; exclude an explicit volatile-cache allowlist, `ctime`, and inode identity. Treat unhashable large user trees as no-write zones. |
| Command isolation | Run trusted configured commands in the existing frozen/no-sync environment with redirected temp/cache/bytecode and bounded timeout. Inspect project configuration and command behavior for project-specific outputs such as `.docmend`; redirect or bind-map them to scratch, or mark the command unavailable. Sandbox unknown or externally effectful commands, not every local test. |
| Baseline | Capture once. Record exact identities only for non-pass outcomes. Reuse the immutable baseline across same-SHA resume epochs. |
| Verification | Batch related private findings into one adversarial pass. Use a dedicated verifier for public API, deletion/dynamic-reference risk, state-sharing, dependency, persistence, concurrency, recovery, security, or high blast radius. |
| Report audit | Audit a publication-ready substantive draft once. After administrative or formatting edits, use deterministic validation and a focused diff review. Repeat model audit only after substantive finding changes. |

### Controls to make conditional

The following sections should not occupy the always-loaded prompt unless a trigger exists:

- dependency ownership, advisories, licenses, artifact hashes, wheels, and package typing;
- codemod framework selection and fixture proof;
- Git filter, textconv, fsmonitor, partial clone, and attribute-driver threat analysis;
- symlink, hardlink, gitlink, and nested-repository deep inspection after a cheap initial scan finds none;
- exact diagnostic identity mapping for a completely clean baseline;
- public serialization, pickle, plugin, or reflection checks for purely local private expressions;
- per-candidate fresh verifiers;
- complete raw-output and every-opened-file ledgers; and
- exact publication hashes and full ignored-tree manifests.

### Controls to remove

- Terminal comparison of directory `ctime` or inode identity.
- Full ignored/cache-tree hashing after purely read-only tools.
- Mutation of `.git/info/exclude` solely to hide review scratch.
- Mandatory zero-actionable-finding fallback when a fresh verifier or final auditor is unavailable.
- Requirements for the report to contain facts that only exist after the report is audited or published.
- Universal preservation of unsupported private runtime observability.
- An “every opportunity” completeness claim. The defensible claim is that every source file was reviewed and every reported finding met its evidence threshold.

## Orchestration and context-management assessment

### What worked

- Worker assignments were generally bounded and source coverage was complete.
- Same-SHA baseline and scanner evidence was eventually adopted instead of being fully rerun after each incident.
- Candidate-specific fresh verification recovered from contaminated lanes.
- The coordinator retained final judgment and report ownership.
- The final auditor found a real semantic cross-reference defect.

### What cost too much

The five initial semantic workers alone consumed 143.8 million raw tokens. They were reused through follow-up turns, accumulating evidence and contributing 20 worker compactions. A later skill/reference reload emitted 2,518 lines and about 22,657 tokens in one operation. Seven coordinator compactions retained the full 9,760-word request plus superseded continuation language.

Compaction did not cause wholesale rediscovery, which is important. The review generally resumed progressively later checkpoints. Its cost was semantic ambiguity and repeated context: old “restart” wording coexisted with the later correction to resume, overrides were re-announced after compaction, and broad guidance was reloaded when a compact state capsule would have sufficed.

The recommended orchestration shape for this repository is:

- one Ultra coordinator;
- two to four mostly disjoint discovery lanes, using a more efficient model for deterministic and straightforward read-heavy work where available;
- one batched high-reasoning verifier for surviving findings;
- one final substantive auditor only if the report contains high-risk actionable findings; and
- no more than one rerun lane for evidence contaminated by a proven execution-boundary failure.

Workers should receive a compact evidence packet containing only:

- anchored SHA and assigned paths;
- governing local conventions relevant to those paths;
- baseline summary and evidence hashes;
- exact candidate questions;
- mandatory command wrapper, if any;
- required return schema; and
- current checkpoint and incident exclusions.

They should not repeatedly reload the full master prompt, every skill reference, all baseline logs, or unrelated candidate evidence.

### Waiting and status

Eighty-five `wait_agent` calls plus 29 status listings produced about 54 minutes of recorded waits, roughly 20% of coordinator active-turn time. Parallel work necessarily requires waiting, and combining polls does not make agent work finish sooner. The avoidable cost is extra tool/model turns and context churn, not the full recorded wait duration.

Use event-driven waits capped at 60 seconds while the interactive channel requires a heartbeat; use longer waits only when a separate progress mechanism remains visible. Query agent state only after a timeout, contradictory message, or phase transition. User-facing status should say whether action is required; internal S4/S5/S6-style counters should not dominate the update.

## Recommended assurance modes

| Mode | Use when | Process |
| --- | --- | --- |
| Fast | Trusted personal repo; low-risk private simplification; no dependency, public API, persistence, recovery, security, or concurrency candidates | Stable SHA, scoped tracked-status checks, configured baseline once, coordinator plus at most two discovery workers, coordinator verification for local mechanical findings, concise report, deterministic validation |
| Default | Trusted personal repo with broad source coverage; recommended for `docmend` | Stable SHA and clean relevant tracked paths, two to four semantic lanes, redirected caches, one baseline, risk-based contract/history checks, one batched verifier, one substantive report audit, start/phase/end integrity checks |
| Forensic | Untrusted or third-party repo, shared/CI worktree, formal compliance evidence, credentials/external services, unknown commands/plugins, or explicitly requested evidentiary rigor | Deep Git/config/attribute inspection, no-network/read-only sandbox, sanitized raw logs, stronger non-cache filesystem guard, dedicated high-risk verifiers, formal receipts and audit trail |

Escalation should normally be candidate- or command-specific. A dependency replacement can use forensic dependency checks without forcing every read-only `rg` call through a 65,000-entry filesystem audit.

Even forensic mode should not make `ctime`, inode identity, bytecode/cache paths inside `.venv`, or ordinary tool-cache metadata terminal integrity conditions. Other virtual-environment executables, dependencies, and metadata remain immutable evidence or a no-write zone.

## Recommended prompt architecture

### Always-loaded core

The default prompt should be approximately 1,500–2,000 words and contain only:

1. Parameters, anchored scope, and output path.
2. The comprehension-first objective and behavior-preservation boundary.
3. Analysis-only write boundary.
4. Proportional Git and tracked-content integrity checks.
5. Existing environment and baseline rules.
6. Full in-scope source coverage with material-findings language.
7. Risk-based public-contract, history, typing, and behavior checks.
8. Bounded orchestration and verifier rules.
9. Concise report schema.
10. Resume, incident, override, and completion semantics.

This is an 80–85% reduction from the 9,760-word always-loaded request. The detailed dependency, codemod, untrusted-command, forensic Git, and evidence-retention rules should live in triggered references or tested helpers.

### Ready-to-use assurance and autonomy clause

```text
## Assurance mode

Operating context: trusted personal repository, one developer, secure private
workstation. Use default assurance unless a specific command or candidate
triggers stricter treatment. Protect tracked and user-authored content; do not
turn harmless cache or metadata changes into terminal failures.

Anchor HEAD once. Require requested source and evidence paths to be tracked,
materialized, readable, and unchanged from the anchor. Record unrelated
worktree state. Build a known Git subprocess environment: unset repository
routing variables, pager, prompts, external diff, and askpass helpers; then
verify repository root and HEAD. Ambient askpass helpers are sanitized events,
not blockers.

At startup, inventory non-cache ignored and untracked user paths by path,
existence, type, mode, size, and a local content hash without retaining their
bytes. Exclude only an explicit volatile allowlist such as declared scratch,
tool caches, `__pycache__`, and `*.pyc` paths inside `.venv`; all other virtual-
environment files remain immutable evidence or a no-write zone. Treat large
un-hashed user trees as no-write zones. Recheck this inventory after code-loading
commands, at phase boundaries, and before publication; do not compare `ctime` or
inode identity.

Writes are limited to the report and declared scratch. Before running a project
command, inspect its configuration and known behavior for project-specific
outputs. Redirect or bind-map outputs such as `.docmend` logs into scratch as
well as generic temp, cache, coverage, Hypothesis, and bytecode state. If a
required output cannot be redirected without changing behavior, mark the command
unavailable or use a disposable writable worktree. Run established commands in
the existing environment without install or sync. Sandbox only unknown or
externally effectful commands. Check HEAD and relevant tracked content after
code-loading commands, at phase boundaries, and before publication. Batch
consecutive pure reads without an integrity check.

Cache, bytecode, test-temp, scratch, directory mtime/ctime, and inode-only drift
is nonterminal when tracked and user-authored content remains intact. Record the
incident once, redirect subsequent commands, safely remove run-created artifacts
when ownership is certain, and continue. Stop only for an unresolvable repository,
unstable anchor, unsafe report path, unexpected tracked/user-content mutation,
or inability to complete truthful source coverage.

Preserve documented and public behavior, repository-observed private integration
points, supported inputs, meaningful errors, ordering, side effects, persistence,
cleanup, and concurrency guarantees. Do not treat unsupported subclasses,
unobserved reflection, private frame shape, code-object identity, tracer mutation,
negligible timing/allocation, pure-helper call count, or low-memory failure points
as contracts unless repository evidence says otherwise.

Read every in-scope source file. Report material, high-confidence opportunities;
do not claim metaphysical completeness. Use configured tools first, at most one
clone detector, and one dead-code/lint pass. Optional scanner failure blocks only
claims that depend on it.

Use two to four coherent discovery lanes. Batch related private findings into one
independent adversarial review. Require a dedicated fresh verifier only for public
API, deletion with dynamic-reference risk, state sharing, dependencies, persistence,
recovery, concurrency, security, or high blast radius. Lack of an optional verifier
lowers confidence or blocks that candidate; it does not erase unrelated findings.

Draft a concise, self-contained report. For each actionable finding include exact
locations, the comprehension problem, the proposed edit, relevant contract risks,
and runnable verification. Summarize retained, manual, and blocked items compactly.
Run deterministic Markdown/schema/secret checks and one substantive audit. Repeat
model audit only after substantive finding, disposition, or ordering changes.
Publish without overwrite.
```

### Ready-to-use continuation clause

```text
## Continuation and incidents

"Continue" resumes the current objective from the latest verified checkpoint. It
does not repeat completed discovery or restart the objective. Track the objective,
anchored SHA, integrity epoch, last verified checkpoint, active incident/override,
superseded directives, remaining work, and next action in one compact state capsule.

If HEAD and tracked/user-authored content remain intact, drift limited to caches or
non-semantic metadata is a recoverable integrity incident. Append an incident record,
prevent recurrence, create a new integrity epoch, adopt same-SHA evidence, and resume
automatically. ctime or inode differences alone are never terminal.

Accept natural-language owner authority or `override <incident>: <action>`. Normalize
it to the incident, permitted action, unchanged scope, adopted checkpoint, redo policy,
and expiry. An override changes only the named safety condition and never silently
rebaselines tracked source, index, or refs.

Status requests are informational and do not pause work. State whether user action is
needed, the checkpoint, active work, remaining work, permitted writes, integrity epoch,
active override, and next automatic action.
```

### Triggered references

Load one-level-deep reference material only when its trigger appears:

| Trigger | Reference content |
| --- | --- |
| New or transitive dependency | Package identity, maintenance, advisories, license, wheels, artifacts, typing, resolution, and differential behavior |
| Public symbol, registration, deletion, or move | Exports, docs, entry points, reflection, monkeypatching, serialization, subclassing, and exhaustive references |
| Concurrency, persistence, restore, or security | Dedicated behavior matrix and fresh high-reasoning verifier |
| Approximately 500 lines or 50 call sites | Codemod selection, fixture proof, idempotence, and dry-run protocol |
| Unknown repository or executable hooks | Git driver inspection, plugin review, no-network/read-only sandbox, stronger evidence guard |
| Formal forensic request | Raw evidence ledger, non-cache filesystem manifest, per-candidate verifier, exact receipts |

## Efficiency recommendations and expected effect

The ranges below are directional and non-additive. Cached-token pricing and plan-meter weighting are not exposed, so these are raw-workload targets rather than billing guarantees.

| Priority | Change | Expected effect |
| --- | --- | --- |
| P0 | Remove volatile caches, `ctime`, and inode identity from terminal integrity; establish automatic same-SHA epoch rollover | Prevents both terminal incidents and most owner babysitting; plausibly 15–25% fewer raw tokens in a comparable run |
| P0 | Centralize command execution in one tested default/strict launcher | Prevents repeated sandbox and cache-boundary failures; reduces interrupted and fresh recovery lanes |
| P0 | Replace per-tool full guards with checks after code-loading commands, writes, phase boundaries, and publication | Reduce roughly 660 checks to about 60–100; plausibly 5–15% fewer raw tokens plus substantial wall-time reduction |
| P1 | Use Ultra for coordination/adjudication, efficient models for deterministic/read-heavy lanes, and one batched verifier | Reduces the 63.8% worker share; likely the largest plan-cost reduction after incident prevention |
| P1 | Reduce 29 workstreams to roughly 6–10 | Less agent messaging, waiting, evidence duplication, and compaction |
| P1 | Use a compact shared evidence packet and authoritative resume capsule | Plausibly 10–20% fewer raw tokens by avoiding repeated broad context and skill reloads |
| P1 | Finalize ordering and administrative fields before one final audit | Avoids a second full 26.2M-token auditor turn; plausibly 2–4% overall |
| P2 | Use event-driven agent waits with a 60-second interactive heartbeat | Fewer polling tool/model turns and plausibly 1–3% fewer raw tokens; wall-time savings are unmeasured |
| P2 | Pretest scanner and Markdown helpers; run one clone detector | Removes low-yield launcher retries and overlapping scanner reconciliation |

A reasonable engineering target is a 60–75% reduction in raw model workload for a comparable trusted-repository review. This is not a guaranteed plan-meter reduction. A conservative success criterion for the next run is at least 50% fewer model steps, no owner intervention for cache-only drift, no more than 10 workstreams, and one final semantic audit.

## Suggested compact report contract

A future durable report does not need sixteen mandatory fields per finding plus a full every-opened-file ledger. A self-contained report can use:

1. Header: repository, SHA, scope, environment, assurance mode, baseline summary.
2. Coverage: each in-scope file accounted for and any actual gaps.
3. Actionable findings, each with:
   - ID, category, and exact anchors;
   - current comprehension cost;
   - exact proposed edit and typed signature where applicable;
   - relevant public/dynamic/typing/behavior checks;
   - verification commands;
   - independent-review result when required; and
   - benefit, confidence, and blast radius.
4. Compact retained/manual/blocked tables.
5. Implementation order.
6. Tool limitations and final audit summary.

Raw scanner output, command logs, complete opened-file inventories, and exhaustive negative results can remain in scratch for the current run. The durable report should summarize all load-bearing evidence so it remains useful after scratch is removed.

## What should not be optimized away

Efficiency improvements should not eliminate the controls that produced real value:

- The exact commit anchor prevented stale findings.
- Complete source-file coverage made the review auditable.
- Repository-wide reference checks prevented unsafe deletion and movement claims.
- Behavior-focused verification rejected genuine semantic drift.
- The clean baseline and exact non-pass treatment avoided calling a failing suite “passed.”
- Atomic, non-overwriting publication protected an existing report path.
- Final semantic review caught a cross-reference error that deterministic Markdown checks could not detect.
- Secret and network boundaries were appropriate for a public repository.

The goal is fewer universal controls and more targeted controls, not a casual review.

## Implementation roadmap for the revised workflow

1. Convert the prompt into a reusable skill with a 1,500–2,000-word default entry point.
2. Move dependency, codemod, untrusted-command, forensic Git, and full evidence schemas into one-level-deep triggered references.
3. Implement tested scripts for:
   - preflight and path normalization;
   - tracked-source inventory and coverage;
   - baseline capture and normalized non-pass identities;
   - project-specific output discovery plus default and strict command launchers;
   - lightweight tracked and non-cache-user-path phase-boundary integrity;
   - report schema and count checks; and
   - atomic publication.
4. Define the authoritative resume capsule and integrity-epoch transition.
5. Add a dry-run fixture repository that includes:
   - inherited askpass helpers;
   - an existing `.venv` and cache trees;
   - a test that intentionally writes a project-local runtime log;
   - a mode-000 ignored fixture;
   - an existing report collision; and
   - a recoverable cache-only incident.
6. Measure the next comparable review against:
   - model sessions and steps;
   - raw and uncached tokens;
   - workstream count;
   - full integrity-check count;
   - owner interventions;
   - wall and active time; and
   - findings accepted, rejected, and later found incorrect.
7. Promote controls from default to forensic only when measured failures justify it.

## Limitations

- The session transcript provides raw token counters and a rounded weekly meter, not OpenAI's internal plan-weighting formula. Cost-savings estimates are therefore directional.
- Agent active-time accounting is based on recorded turn boundaries. Parallel worker durations overlap and must not be added to wall-clock duration.
- The current report's post-publication formatting change was observed but not attributed to a particular process.
- This analysis evaluates process proportionality for a trusted personal workstation. A shared, hostile, regulated, or evidence-preservation environment would justify stricter defaults.
- No source finding from the code-simplification report was re-adjudicated here; this report evaluates how the review was performed.

## Evidence index

The following records carry the load-bearing facts summarized above:

- Initial askpass block and owner override: `T:70-119`.
- First guard initialization and sandbox retries: `T:224-374`.
- Baseline false failures and successful rerun: `T:458-613`; `R1/evidence-index.md:31-35`.
- Scanner-launcher retries: `T:699-761`; `R1/ultra/deterministic/result.md`.
- First cache incident and terminal status: `T:1568-1660`; `R1/execution-blocked-incident.md`.
- Restart/resume correction: `T:1673-1707`.
- Mode-000 predecessor-guard retry: `T:1781-1837`; `R2/preflight.json`.
- Second cache incident and owner override: `T:2412-2551`; `R2/coordinator/integrity-incident-20260722T111949Z.md`.
- Third-run false checker alarm: `T:2623-2646`.
- Final audit and guard latency: `T:3416-3731`; `R3/ultra/final-audit/audit.md`.
- Cross-reference correction and re-audit: `T:3889-4071`; `R3/ultra/final-audit/reaudit.md`.
- Completion counts and integrity: `T:4098-4183`; `R3/coordinator/completion-audit.md`.
- Workstream inventory: `R3/manifest.md`.
- Publication receipt: `R3/coordinator/publication.json`.
- Immutable audited report: `R3/report-draft.md`.

## Final assessment

The review was rigorous and ultimately useful, but its default controls were not proportional to the actual risk. The two most damaging choices were treating volatile filesystem metadata as a terminal integrity boundary and requiring high-cost, repeated verification for nearly every candidate. Both choices increased the chance of interruption without increasing confidence in the tracked source.

For future runs, use the default assurance mode above, reserve the original machinery for explicit forensic work, and make continuation automatic whenever the anchored SHA and tracked/user-authored content remain intact. That change would preserve the strongest parts of the review while making the process substantially faster, cheaper, and genuinely autonomous.
