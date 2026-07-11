# Safety-Core Plan A Foundations Review

Claude Code note: consider using the `superpowers:receiving-code-review` skill.

## Verdict

Verdict: **REVISE AND RE-REVIEW**

The plan's decomposition and implementation direction match SPEC-VHHB revision 0.26 and the approved safety-core design, but the plan is not executable as written. Three blocking defects remain: several required red/green tests fail before reaching the behavior they are meant to exercise; the `.docmend/` carve-out is licensed from a synthetic probe rather than the actual destination; and the destination guard can approve a corpus-owned directory entry when that entry is a symlink resolving outside the corpus. Two staging and test-contract issues should also be corrected before implementation.

## Review Target and Method

- Target: `docs/superpowers/plans/2026-07-10-safety-core-a-foundations.md`
- Pinned state: commit `66b014094c6cb93e3f64267e0a82b9828e31a2d4` on `dev`; worktree clean at review start; branch one commit ahead of `origin/dev`
- Round: 1
- Ground truth checked: SPEC-VHHB revision 0.26; the approved safety-core remediation design; ADR-backed handoff conventions; current `artifacts.py`, `cli.py`, `planning.py`, `plan.py`, `inventory.py`, `writer/atomic.py`, `writer/apply.py`, `writer/backup.py`, `writer/manifest.py`, and `restore.py`; the named test modules
- Live checks: Git status/history; exact run-ID model pattern; current test fixtures/helpers; current apply/restore signatures and lock ordering; PathSpec negation behavior for the proposed `.docmend/probe` check
- Review posture: read-only implementation-plan audit; no product or plan fixes applied

## Verified and Held

These parts line up with the current contracts and need not be re-litigated unless the plan changes materially:

- The plan-wide output ledger correctly generalizes the existing rename-only claim set to every emitted action's effective output path.
- The run/action/role BackupStore layout and no-clobber publication match FR-006 and the approved DMR-01 design.
- Wiring both source and overwritten-target backups through the action/role key preserves the current manifest's opaque-path compatibility for Plan A.
- Randomized same-directory staging is the correct direction for both writer bytes and JSON artifacts.
- Guarding scan, both plan branches, and apply before their substantive pipeline work covers the current operator-selectable DMR-02 destinations.
- Moving apply report publication inside the held run lock matches the approved coordination boundary for the current implementation stage.
- The final full gate, changed-file staging discipline, public-fixture restriction, unreleased version posture, and `dev` push target match repository conventions.

## Round Ledger

| Finding | Severity | Round 1 status | Required closure evidence |
| --- | --- | --- | --- |
| F1 | Blocking | Open | Every pasted test uses valid schema values, live fixtures/helpers, deterministic event setup, and passes collection, Ruff, BasedPyright, and its intended red/green sequence. |
| F2 | Blocking | Open | The carve-out is decided for each actual destination under the actual corpus-relative path, including negated/re-included patterns. |
| F3 | Blocking | Open | Guard tests cover both lexical and resolved containment so publication cannot replace a corpus-owned directory entry through an outward symlink. |
| F4 | Should fix | Open | JSON staging cleans up and closes resources for serialization failures as well as `OSError`, without a process-global umask race. |
| F5 | Should fix | Open | The atomic staging test deterministically exercises a generated-name collision and the implementation retries it without touching stale residue. |

## Findings

### F1 — Blocking: the required tests do not reach the behavior they claim to test

**Defect:** Multiple pasted tests fail during setup, collection, lint, or type checking rather than at the intended missing implementation. That breaks the plan's TDD sequencing and makes the stated full-gate outcome unattainable if an implementer follows the plan literally.

**Evidence:**

- Plan lines 246 and 307 use run IDs ending in `00dmr1` and `00dmr2`; line 588 uses `0ledgr`. `src/docmend/inventory.py:32` requires the six-character suffix to match `[0-9a-f]{6}`. The Task 2 `ArtifactRef`/`Plan` construction and Task 5 discovery/plan construction therefore raise validation errors before exercising backup or output-ledger behavior.
- Plan lines 853–875 and 1069–1082 declare a `runner` fixture, but all three current CLI test modules expose a module-level `runner = CliRunner()` and no `runner` fixture. The plan acknowledges that implementers must adapt these signatures later, so the snippets are not executable instructions.
- Plan lines 1073 and 1104 call `_scan_and_plan*` helpers that do not exist. The live apply test helper is `_make_plan(corpus, *, out=...)`, with corpus construction handled separately.
- The lock-order test patches `RunLock.release` before it creates its plan (lines 1101–1104). The live `_make_plan` invokes the `plan` CLI, which acquires and releases a run lock. Consequently the first `lock-released` event belongs to setup, so line 1109 fails even after apply correctly writes its report before releasing its own lock.
- Several new helpers/spies omit the annotations required by the repository's strict Ruff/BasedPyright gate; the Task 1 heterogeneous `kwargs` dictionary is also spread into a strictly typed keyword-only call without a typed mapping seam.

**Concrete fix:** Replace every mnemonic run suffix with six hexadecimal characters; rewrite the CLI tests in the live module style with typed pytest parameters and the module-level runner; use `_make_plan` or add one exact typed helper in the plan; prepare the plan before installing the event spies (or clear `events` immediately before apply); and show gate-clean typed code rather than adaptation placeholders. Re-run each named red test to prove it fails for the intended missing behavior, then run it green after the proposed implementation.

### F2 — Blocking: the carve-out checks a probe, not whether the actual destination remains excluded

**Defect:** `_guard_artifact_paths` licenses the entire canonical `.docmend/` root when `.docmend/probe` matches the effective excludes. Gitignore-style patterns can exclude the probe while negating one specific output path. The proposed guard then allows that re-included destination inside the corpus, contrary to the approved design's condition that the destination itself remain covered by the effective exclusions.

**Evidence:**

- Approved design lines 144–148 and SPEC-VHHB IR-007 require the carve-out only while the effective exclude patterns still cover the destination.
- Plan lines 912–920 evaluate only `exclude.match_file(".docmend/probe")` and pass one root-wide `allowed_root` to every destination.
- Live PathSpec evaluation with `['**/.docmend/**', '!.docmend/docmend-*-report.json']` returns `True` for `.docmend/probe` but `False` for `.docmend/docmend-run_x-report.json`. Under the proposed code, the report is nevertheless licensed.
- The plan tests only total removal of the default exclusion (`--exclude '*.bin'`); no test covers a negated/re-included destination or differing destinations in one invocation.

**Concrete fix:** Make carve-out authorization destination-specific. Compute the destination's path relative to the corpus root (when the canonical root lies inside it) and require `exclude.match_file(actual_relative_destination)` for every proposed output. Do not pass a root-wide license inferred from a probe. Add scan, plan, and apply tests with a default exclusion plus a negation that re-includes the exact inventory/plan/report destination; each must refuse at exit 3 before writing that artifact.

### F3 — Blocking: resolving the destination loses the directory entry that publication actually replaces

**Defect:** The guard checks only `destination.resolve()`, while `write_json_artifact` publishes with `tmp.replace(destination)`. If a destination name inside the corpus is a symlink to a regular file outside the corpus, resolution is outside and the proposed guard approves it; publication then replaces the symlink directory entry inside the corpus. The guard therefore does not uphold its own claim that docmend artifacts cannot mutate the corpus they describe.

**Evidence:**

- Plan lines 791–820 state the no-corpus-destruction invariant but use only the resolved path for type, alias, and containment decisions.
- Current `src/docmend/artifacts.py:93-102` and proposed Task 4 both publish to the lexical `path` with `os.replace` semantics.
- Plan lines 724–731 cover only an outside name resolving inward. There is no mirror test for an inside name resolving outward, which is the case where the checked object and replaced directory entry diverge.
- The approved design requires path-aware refusal before publication; its carve-out is the only authorized in-corpus namespace.

**Concrete fix:** Check both the lexical destination location (using a resolved parent plus the final name without following the final component) and the fully resolved referent. Refuse when either is inside the corpus unless the exact destination receives the destination-specific `.docmend/` license from F2. Add mirror symlink tests: outside-to-inside refuses, inside-to-outside refuses, and no directory entry or referent changes on refusal.

### F4 — Should fix: JSON staging cleanup is narrower than the function's failure surface

**Defect:** The proposed `write_json_artifact` removes the staging file only for `OSError`. `json.dump` can raise `TypeError` or `ValueError`, leaving a randomized staging artifact behind. It also discovers the desired mode by temporarily changing the process-wide umask, which is unnecessary shared global mutation in a library function.

**Evidence:**

- Plan lines 487–510 wrap staging cleanup in `except OSError` only.
- `write_json_artifact` is a public internal seam accepting `dict[str, object]`; serialization errors are part of its reachable input surface even though model-specific writers normally validate serializable data first.
- The same block calls `os.umask(0)` and restores it in a second call; another thread or signal handler can observe the temporary zero umask.
- The proposed test supplies only a serializable dictionary and cannot detect either failure path.

**Concrete fix:** Use a resource-safe structure that closes the descriptor and unlinks the temp in `finally` whenever publication has not succeeded, including serialization exceptions. Preserve the secure `mkstemp` mode unless a documented artifact-mode contract requires widening it; if widening is required, derive that policy without a transient process-global umask change. Add a serialization-failure test asserting no destination and no staging residue remain.

### F5 — Should fix: writer staging treats a generated-name collision as a write failure

**Defect:** Task 3 generates one random name and calls `O_EXCL` once. A collision with stale residue raises `WriteError`; this weakens the plan's categorical claim that kill residue is inert and never blocks retry. `tempfile.mkstemp` in Task 4 already provides the stronger collision-retry behavior.

**Evidence:**

- Plan lines 407–413 select one `secrets.token_hex(4)` name and immediately call `os.open(..., O_EXCL)`.
- The test plants `.a.md.deadbeef.docmend-tmp` but never forces `token_hex` to return `deadbeef`, so it proves only that a different random name works.
- The approved design requires randomized `O_EXCL` staging; robust exclusive-name allocation must handle `EEXIST` as a name collision, not as an environmental write failure.

**Concrete fix:** Use `tempfile.mkstemp` with the writer naming pattern or a bounded loop that retries only `EEXIST` and propagates other errors. Monkeypatch the first candidate to collide and the second to succeed; assert the stale file is unchanged, the target contains the new bytes, and no successful-attempt temp remains.

## Re-Review Gate

Round 2 should preserve finding IDs and update each status to `closed`, `still open`, or `superseded`. Approval requires:

1. All named test snippets collect and reach their intended red state against the pinned pre-implementation code.
2. Every pasted addition passes Ruff and BasedPyright in the live modules after the green implementation.
3. The carve-out is authorized per actual destination, with negation/re-inclusion tests.
4. Both lexical and resolved destination containment are checked, with mirror symlink tests proving refusal is non-mutating.
5. JSON staging cleans every failure class without a process-global umask window.
6. Writer staging deterministically survives an `EEXIST` candidate collision.
7. `uv run scripts/check.py` passes without lowering coverage or weakening any standard-owned gate.

## Round 2 — 2026-07-10

### Verdict

Verdict: **REVISE AND RE-REVIEW**

Round 2 reviewed commit `a6b497052b898e93e62b47b21c3d0b9fe3d58bc7`. The revision closes F1–F5 at the implementation-plan level. One new blocking change-control finding, F6, remains: the plan adds a lexical-containment rule and a mode-0600 artifact policy that the approved revision 0.26 contract does not state.

### Round 2 Target and Method

- Target revision: commit `a6b497052b898e93e62b47b21c3d0b9fe3d58bc7` on `dev`
- Delta reviewed: 478 insertions and 289 deletions relative to round 1's `66b014094c6cb93e3f64267e0a82b9828e31a2d4`
- Worktree note: only this review report remained untracked; the revised plan itself was committed
- Re-verified against: SPEC-VHHB revision 0.26; the approved safety-core design; ADR 0021; live Pydantic run-ID patterns; current CLI test fixtures/helpers; current artifact, atomic-writer, apply, restore, and planning code
- Live checks: PathSpec negation behavior; exact import/helper availability; current lock setup order; Git status/history; scoped plan/report Markdown validation inputs

### Prior Finding Disposition

| Finding | Round 2 status | Evidence |
| --- | --- | --- |
| F1 | Closed | Run IDs now use hexadecimal suffixes; typed helpers use the live module-level runner and `_make_plan`/`make_corpus` conventions; explicit keywords replace the heterogeneous kwargs spread; apply spies are installed after plan creation. |
| F2 | Closed | `guard_artifact_destination` now receives the effective `PathSpec` and checks each actual corpus-relative destination. Unit and scan CLI tests cover a negation that re-includes the exact output. |
| F3 | Closed technically; change control tracked in F6 | The guard checks the resolved-parent lexical name and the fully resolved referent. Mirror symlink tests prove both directions refuse without mutation. |
| F4 | Closed technically; mode policy tracked in F6 | JSON staging now unlinks unpublished temps in `finally`, including serialization failures, and no longer changes the process umask. |
| F5 | Closed | Writer staging retries `FileExistsError` up to eight times. The deterministic test forces the first candidate to collide, verifies residue survival, and confirms the second candidate publishes and cleans up. |

### F6 — Blocking: the revised plan introduces unapproved path and permission policy

**Defect:** The revised plan turns two review fixes into externally visible policy without reconciling the approved sources. It expands containment from “resolved destination is inside the corpus” to “either the lexical directory entry or resolved referent is inside,” and changes every JSON run artifact from umask-derived mode to mode 0600. Both are sensible candidate policies, but neither appears in SPEC-VHHB revision 0.26 or ADR 0021. The plan incorrectly describes mode 0600 as aligned with a revision 0.26 metadata-permissions direction.

**Evidence:**

- Plan lines 513 and 556–579 deliberately retain `mkstemp`'s mode 0600. Lines 1390–1392 announce the change as new user-visible behavior.
- Plan lines 909–973 reject based on both the lexical name and resolved referent. The revised CHANGELOG text at line 1386 announces that stronger rule.
- SPEC-VHHB IR-007 requires refusal for destinations “resolving inside” the corpus and randomized `O_EXCL` staging. It does not define lexical-entry containment or artifact modes.
- ADR 0021 lines 58–71 owns this decision. It likewise defines resolved containment, the `.docmend/` carve-out, randomized staging, and confirmation tests, but no lexical-entry or permission rule.
- The approved design line 181 explicitly defers log permissions and redaction to later sub-projects and records no JSON-artifact mode decision. The comprehensive review's permissions finding recommends aligning inventory, plan, and report permissions in a follow-on security review rather than silently selecting a mode here.
- The repository's approved-spec lifecycle requires post-approval behavior changes to receive a new revision row and owner approval when scope-affecting.

**Impact:** Implementing the plan would make the code, CHANGELOG, spec, ADR, and approved design disagree about which paths are refused and which filesystem modes operators receive. Future tests and plans would have no authoritative source for those behaviors.

**Concrete fix:** Choose one of these change-controlled paths before implementation:

1. Keep both policies: amend ADR 0021 and SPEC-VHHB IR-007 to state lexical-plus-resolved containment and mode 0600 for JSON run artifacts; add the spec revision row and required owner approval; update the design's artifact-guard section and deferred-work boundary; add mode tests under representative umasks.
2. Keep Plan A within the current contract: remove the 0600 claim/change and defer artifact permissions to the approved follow-on; for lexical containment, either record it as a non-behavioral clarification in the approved sources or remove it until that clarification lands.

Do not describe confidentiality classification alone as a file-mode decision. If 0600 remains, test it explicitly rather than relying on `mkstemp` as an incidental implementation detail.

### Round 3 Gate

Round 3 should preserve F1–F6 and confirm:

1. F1–F5 remain closed after any contract edits.
2. SPEC-VHHB, ADR 0021, the approved design, plan, and CHANGELOG state one identical lexical/resolved containment rule.
3. Artifact mode behavior is either formally approved and directly tested or removed from Plan A and deferred.
4. Any spec change has its revision/history update and required owner approval.
5. The revised plan and durable review report pass Prettier, markdownlint, and `git diff --check`.

## Round 3 — 2026-07-10

### Verdict

Verdict: **APPROVED**

Round 3 reviewed commit `b9d519517f03033bdd31804794e3c3ebf2fa6f07`. F6 is closed: the owner-approved SPEC-VHHB revision 0.27 and ADR 0021 amendment now bind lexical-plus-resolved containment and destination-specific carve-out licensing, while Plan A drops the unapproved mode-0600 policy and preserves existing umask-derived JSON artifact modes. F1–F5 remain closed. No blocking or should-fix implementation-plan findings remain.

### Round 3 Target and Method

- Target revision: commit `b9d519517f03033bdd31804794e3c3ebf2fa6f07` on `dev`
- Delta reviewed: 37 insertions and 23 deletions across the spec, ADR 0021, approved design, and Plan A relative to round 2's `a6b497052b898e93e62b47b21c3d0b9fe3d58bc7`
- Worktree note: only this review report remained untracked; all contract and plan revisions were committed
- Re-verified against: SPEC-VHHB revision history and IR-007; ADR 0021 decision, confirmation, and amendment note; approved design artifact-guard section; Plan A Task 4, guard tasks, CHANGELOG instructions, and F1–F6 self-review
- Live validation: `project-standards spec validate` passed; strict `project-standards spec lint` passed

### Finding Disposition

| Finding | Round 3 status | Closure evidence |
| --- | --- | --- |
| F1 | Closed | Valid schema values, live test helpers, typed snippets, and deterministic lock-spy setup remain unchanged from the accepted round-2 disposition. |
| F2 | Closed | Destination-specific PathSpec evaluation and negation tests remain in the plan and match rev 0.27 IR-007. |
| F3 | Closed | Lexical-plus-resolved containment is now both technically specified in the plan and formally owned by rev 0.27 plus amended ADR 0021. |
| F4 | Closed | Full-failure-class temp cleanup remains; JSON artifacts now use kernel-masked `0o666`, preserving current umask-derived modes without calling `os.umask()` in product code. |
| F5 | Closed | Bounded `EEXIST` retry and its deterministic collision test remain unchanged. |
| F6 | Closed | Owner-approved rev 0.27, ADR 0021, the design, plan, and CHANGELOG instructions now state the same path policy; mode 0600 was removed and permission policy was explicitly deferred. |

### Approval Basis

The implementation plan is now sufficiently complete and internally consistent to execute task by task:

1. DMR-01 has both a planner invariant and BackupStore defense in depth, with a crafted-plan apply/restore regression.
2. DMR-02 has randomized exclusive staging, lexical and resolved destination checks, per-destination `.docmend/` licensing, input-alias refusal, and command-level wiring before substantive pipeline work.
3. The proposed tests identify their intended red states, use current repository helpers and types, and cover the review's counterexamples.
4. Apply report finalization is placed inside the existing run-lock lifetime.
5. The plan finishes with the repository's complete Python gate, Markdown checks, explicit-file commits, and `dev` push workflow.

### Optional Editorial Cleanup

These items do not affect implementation or approval:

- ADR 0021's final spec pointer still says “rev 0.26”; changing it to “rev 0.26/0.27” would match its immediately preceding amendment note.
- Plan A's architecture paragraph and proposed CHANGELOG introduction still call rev 0.26 the safety-core baseline. Adding “as amended by rev 0.27” would make the current contract version more obvious.
- The self-review heading still says “updated after plan-review round 1” although its disposition bullet includes F6.

Re-review is required only if these edits change behavior, test scope, task ordering, or the approved contracts. Pure label cleanup does not require another technical round.
