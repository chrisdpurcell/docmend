# Backup Integrity Verification and Preservation-Strategy Proof for FR-005/FR-006

**Date:** 2026-07-05

**Related:** GAP-34, GAP-35 (external gap-tracker IDs supplied with this research request — not yet present in this repo's own tracker as of this writing; see [Reconciliation notes](#reconciliation-notes), consistent with the same external-GAP-ID pattern already documented in `docs/research/path-containment-toctou.md` (GAP-40), `docs/research/atomic-write-filesystem-semantics.md` (GAP-41), and others) · `docs/open-questions.md` OQ-005 (apply safety-gate and preservation semantics — the primary decision this report feeds), OQ-008 (library version control and backup posture), OQ-012 (in-place mutation, resolved-in-agent-notes) · `docs/specs/docmend.md` §7.1 FR-005, FR-006, FR-003 (stale-hash re-validation, the same pattern this report extends to preservation proofs), §12.1 ERR-004 (backup failure), §12.3 (rollback/recovery), §18.6 (Backup and Disaster Recovery, RPO=zero), §21 OQ-005/OQ-008 · sibling research: `docs/research/atomic-write-filesystem-semantics.md` (D-004 fsync-before-rename discipline, extended here to backup writes), `docs/research/path-containment-toctou.md` (the "re-validate at time-of-use, not time-of-check" principle, extended here to preservation-strategy proofs), `docs/research/self-hosted-corpus-storage-options.md` (OQ-008 storage posture), `docs/research/append-safe-manifest-format.md` (DR-004 manifest durability).

**Gap it fills:** FR-005 today only requires that _a_ preservation strategy be "satisfied" — in practice, implemented as a config-presence check (is `write.backup_dir` set? is a `--git-strategy` flag passed?) — and FR-006 requires only that a backup be _copied_ before mutation, with no requirement that the copy be verified before the original is touched. Both are boolean-trust gaps at the exact point the spec's own RPO (§18.6: "zero for original content") is most exposed: a corrupted or partial backup copy, or a Git tree that looks configured but is actually dirty/untracked for the specific files about to be mutated, currently passes the gate and lets the writer proceed to destroy the only remaining good copy of the original bytes. This report closes that gap with (1) a concrete verify-then-mutate hash-compare algorithm for FR-006, (2) per-strategy machine-checkable substantiation procedures for FR-005 (Git clean-tree/commit-coverage; tool-written/Borg/restic backup recency and coverage; a ranked tiering for the weaker "external backups declared" case), and (3) proposed acceptance-criteria language for both requirements.

---

## 1. The question in docmend's own terms

FR-005 and FR-006 currently describe _intent_ ("refuse unless a strategy is satisfied," "copy before mutating") without describing _proof_. Two distinct failure modes follow directly from that gap, and they are different problems requiring different fixes:

1. **FR-006's problem is temporal ordering plus verification, scoped to one file.** The writer copies bytes to a backup location, then mutates the original. Nothing today confirms the copy that landed on disk is byte-identical to the source _before_ the original is touched. A truncated copy (disk full mid-copy), a copy that silently used stale cached metadata, or a copy whose destination filesystem lied about durability would all currently be invisible until the (now-mutated) original is compared against a (silently bad) backup during a restore attempt — which is exactly when it is too late to matter.
2. **FR-005's problem is that "a preservation strategy is satisfied" is evaluated as a declared category, not a proven fact about the specific files this run is about to mutate.** "Library is in Git" is true in the trivial sense that a `.git/` directory exists somewhere above the source root; it says nothing about whether the files in _this run's plan_ are tracked, committed, and clean at the moment the writer is about to act. The same is true for "external backups declared" — a boolean config flag proves the user believes a backup mechanism exists, not that a recent backup actually covers the files about to be mutated.

Both problems share one design principle already established for a structurally identical race in this project's own research: FR-003 re-validates source hashes at apply time rather than trusting the plan's snapshot, and `docs/research/path-containment-toctou.md` extends the same "re-validate at time-of-use, not time-of-check" discipline to path containment. This report applies that same principle to (a) backup byte-correctness and (b) preservation-strategy proof.

---

## 2. FR-006: verify-then-mutate backup integrity

### 2.1 Why "copy, then trust" is the wrong default

Every general-purpose copy tool this research surveyed defaults to **not** verifying copies, for performance reasons, and treats verification as an explicit opt-in:

- `rsync` by default decides whether to re-transfer a file using size and mtime only; it verifies a **whole-file checksum only during transfer** to detect network corruption, and that automatic check "has nothing to do with" whether the destination file's _content_ actually matches the source afterward if the fast-path (size/mtime match) was taken instead [official, `rsync` docs via community summary at czyzykowski.com and confirmed in multiple independent threads]. The documented fix is the explicit `--checksum`/`-c` flag, which reads and hashes both sides — acknowledged everywhere as "quite slow" because it defeats the size/mtime shortcut entirely [community, corroborated across serverfault.com, askubuntu.com, and blog.wirelessmoves.com].
- Windows' `robocopy` has no built-in post-copy verification at all; community guidance is unanimous that a separate hash comparison step is required if correctness matters [community, learn.microsoft.com Q&A].
- Python's `shutil.copy2()` (the natural stdlib primitive for this, and already referenced in `OQ-005`'s own Agent notes) copies data and attempts to preserve metadata; it performs no post-write readback or hash comparison — its contract is "copy the bytes," not "prove the bytes landed" [official, docs.python.org/3/library/shutil.html].
- Enterprise backup tooling treats this as a first-class, separate operation from the backup itself: Borg's `check --verify-data` explicitly reads and cryptographically re-verifies archive data as a _distinct_ step from `borg create`, because the write path alone does not guarantee it [official, borgbackup.readthedocs.io/en/stable/usage/check.html]. Restic's `check --read-data` does the same, and restic's own docs are explicit that the plain `check` (no flag) **does not** verify pack-file content on disk at all — only `--read-data` (full) or `--read-data-subset` (sampled) does [official, restic.readthedocs.io/en/stable/045_working_with_repos.html].

The pattern across every one of these tools is the same: **write and verify are different operations, and the tool's designers all treat "verify" as something that must be explicitly invoked, not something the copy implicitly guarantees.** docmend should not repeat the "copy, assume, trust" default; it should make the copy-then-verify sequence unconditional and internal to FR-006, not an optional flag the user might forget.

### 2.2 Recommended algorithm

```python
def backup_and_verify(
    source_path: Path,
    backup_path: Path,
    expected_hash: str,  # source.hash already recorded in the plan (DR-002) and
                          # re-confirmed against the live file by FR-003's stale-hash check
) -> BackupOutcome:
    """Copy `source_path` to `backup_path`, then independently prove the copy is
    byte-identical before the caller is allowed to mutate `source_path`.
    Never returns a "verified" outcome without re-reading the backup from disk."""

    # 1. Copy bytes + metadata. shutil.copy2 does not verify anything on its own
    #    (docs.python.org/3/library/shutil.html) -- that is the point of steps 2-3.
    shutil.copy2(source_path, backup_path)

    # 2. Force the copy past any write-back cache before trusting it. This is the
    #    same fsync-before-trust discipline D-004/NFR-002 already require for the
    #    writer's own atomic-replace path (see atomic-write-filesystem-semantics.md);
    #    a backup that only "succeeded" in page cache is not yet a backup.
    fd = os.open(backup_path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

    # 3. Recompute the hash by re-reading the backup file from disk -- never reuse
    #    the in-memory buffer that produced it. Re-reading is what proves the bytes
    #    that landed on the backup medium, not merely the bytes the process held in
    #    memory, match the source. This is the same principle rsync's --checksum,
    #    borg check --verify-data, and restic check --read-data all apply: the
    #    write path is not evidence, an independent read-back-and-hash pass is.
    actual_hash = sha256_file(backup_path)  # streamed, bounded memory (NFR-001)

    if actual_hash != expected_hash:
        # Backup verification failure: ERR-004. The original must NOT be mutated.
        return BackupOutcome(verified=False, backup_hash=actual_hash)

    return BackupOutcome(verified=True, backup_hash=actual_hash)
```

The writer only proceeds to its atomic-replace of the original (D-004: temp file, fsync, `os.replace`) **after** `BackupOutcome.verified is True`. A verification failure is routed through the existing ERR-004 failure class ("Backup copy fails while backups are enabled... The mutation is aborted **before** touching the original; file marked Failed" — §12.1 already states this ordering requirement in words; §2.2's algorithm is the missing mechanism that actually proves it happened).

Two refinements worth adopting alongside the core algorithm:

- **Cheap pre-check before the expensive hash pass:** compare `backup_path.stat().st_size` against the source's recorded `size_bytes` (DR-001/DR-002) first. A size mismatch is a certain failure and avoids a wasted full read for the obviously-truncated case — the same size-then-checksum ordering `rsync` itself uses internally [community, czyzykowski.com; corroborated by serverfault.com's summary of rsync's own algorithm].
- **Sampling only ever applies to periodic health checks, never to the per-run gate.** Borg's `--verify-data` and restic's `--read-data`/`--read-data-subset` exist because re-reading an _entire remote/deduplicated repository_ is expensive at operational scale, so those tools offer a sampled or scheduled alternative [official, restic.readthedocs.io/en/stable/045_working_with_repos.html]. docmend's FR-006 backup is a **local, per-file, same-run** copy of files that are typically small text documents (§1: "GBs of text" across 100k+ files, not GB-scale individual files) — there is no equivalent cost problem, so every backup should be hash-verified in full, every time, before the corresponding original is mutated. Reserve sampling for the FR-005 "external backups declared"/snapshot-coverage checks in §4, where the backup lives outside docmend's own write path and a full-repository read genuinely is expensive.

### 2.3 What this closes

This directly satisfies the "byte-for-byte before mutating the original" framing in the research question: the gate is not "did the copy syscall return success" but "does an independently recomputed hash of the bytes now resting on the backup medium equal the hash the plan already proved matches the live source file." It also gives the manifest (DR-004) a concrete new field to record truthfully — `backup_verified: bool` — rather than implicitly asserting verification happened because a backup path is populated.

---

## 3. FR-005: substantiating "library in Git" as a preservation strategy

### 3.1 The core check: clean tree _for the covered paths_, not "some `.git/` exists somewhere"

Git ships two logically different verbs for this, and docmend needs both:

- **"Is anything different from the last commit"** — the working-tree-dirty question. The canonical script-safe primitive is `git status --porcelain`, whose output format is explicitly documented as script-stable across Git versions and independent of user config, unlike plain `git status` [official/community consensus, unix.stackexchange.com's accepted answer citing the Git docs' own guidance; corroborated independently by baeldung.com and remarkablemark.org]. The lower-level equivalent, `git diff-index --quiet HEAD --`, exits `0` for "no differences" and `1` for "differences exist" per Git's own documented `--exit-code`/`--quiet` semantics [official, git-scm.com/docs/git-diff-index]. Community benchmarking found `git diff-index --quiet HEAD --` measurably faster than `git status --porcelain` for a pure yes/no dirty check, but noted it "can return outdated information" relative to a freshly refreshed index unless preceded by `git update-index -q --refresh` — the classic `require_clean_work_tree()` idiom (`git-sh-setup`) does exactly that refresh-then-check sequence before trusting the result [community, gist.github.com/sindresorhus/3898739; stackoverflow.com/questions/3878624].
- **"Is this specific path even tracked at all"** — a materially different question a plain dirty-check does not answer. An untracked new file is not "dirty" relative to HEAD in the sense `diff-index` checks (there is no tracked blob to diff against); it simply does not appear in `git status --porcelain`'s tracked-file comparison unless `--untracked-files` handling surfaces it as a `??` entry.

**docmend should use Python's GitPython** (already the natural fit given the project's stdlib-first, subprocess-avoiding style elsewhere) rather than shelling out to `git` directly, and the exact API call matters:

```python
import git  # GitPython

def git_preservation_proof(source_root: Path, covered_paths: list[Path]) -> GitProof:
    try:
        repo = git.Repo(source_root, search_parent_directories=True)
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        return GitProof(satisfied=False, reason="source_root is not inside a Git working tree")

    if repo.bare:
        return GitProof(satisfied=False, reason="repository has no working tree")

    rel_paths = [str(p.relative_to(repo.working_tree_dir)) for p in covered_paths]

    # 1. Every covered path must be tracked. An untracked file has no committed
    #    blob to restore from -- Git preserves nothing for it.
    tracked = set(repo.git.ls_files(*rel_paths).splitlines())
    untracked_covered = set(rel_paths) - tracked
    if untracked_covered:
        return GitProof(satisfied=False,
                         reason=f"not tracked by Git: {sorted(untracked_covered)}")

    # 2. The tree must be clean for exactly the covered paths -- and untracked_files
    #    MUST be passed explicitly as True. GitPython's own documented default is
    #    is_dirty(index=True, working_tree=True, untracked_files=False, submodules=True,
    #    path=None) [gitpython.readthedocs.io/en/stable/reference.html] -- the default
    #    silently EXCLUDES untracked files from the dirty check. A newly created file
    #    inside covered_paths that was never `git add`-ed would pass this check as
    #    "clean" under the library default, even though Git holds zero history for it.
    #    This is exactly the false-negative this research was commissioned to find.
    if repo.is_dirty(path=rel_paths, untracked_files=True):
        return GitProof(satisfied=False, reason="working tree not clean for covered paths")

    return GitProof(
        satisfied=True,
        restore_commit=repo.head.commit.hexsha,
        restore_commit_date=repo.head.commit.committed_datetime.isoformat(),
    )
```

**This is the single most important finding in this report:** GitPython's `Repo.is_dirty()` has supported a `path` filter since version 2.0.8 for exactly this per-subtree use case [official, gitpython.readthedocs.io changelog], but its **documented default excludes untracked files** [official, gitpython.readthedocs.io/en/stable/reference.html — `is_dirty(index=True, working_tree=True, untracked_files=False, submodules=True, path=None)`]. A naive `repo.is_dirty(path=covered_paths)` call — the obvious first thing an implementer would write — silently reproduces the exact failure mode OQ-005/GAP-34/35 are asking about: it reports "clean" for a directory that contains a brand-new, never-committed file, because that is Git's own conventional definition of "dirty" (matching plain `git status`'s default framing of untracked files as a separate category from modifications). docmend must pass `untracked_files=True` explicitly and treat the result as authoritative only with that argument set.

### 3.2 Recording the restore anchor

`repo.head.commit.hexsha` should be written into the plan/report/manifest (DR-002/DR-003/DR-004) as the concrete restore instruction: "these files, if this run goes wrong, are recoverable via `git checkout <hexsha> -- <path>`." Because §3.1's check already proves the working tree, index, and `HEAD` blob are identical content for every covered tracked path, `HEAD` is sufficient — there is no need to separately walk `repo.iter_commits(paths=..., max_count=1)` to find "the last commit that touched this path" for restore purposes (that call is documented and available via GitPython's `paths` argument to `iter_commits()`, mirroring `git log <file>` [official, gitpython.readthedocs.io/en/stable/tutorial.html], and remains useful as a **freshness/audit signal** — e.g. flagging in the report if a covered file's last real content change is years old, which is informative but not a substitute for the clean-tree proof).

### 3.3 Optional defense-in-depth: verifying against the object database directly

Git's own dirty-check machinery (`diff-index`, the index cache) uses a stat-cache optimization keyed on mtime+size, conceptually the same shortcut `rsync`'s default mode uses and the same shortcut this report's §2 explicitly rejects for backup verification. In the overwhelmingly common case this is fine and fast; as a "trust but verify" option consistent with the project's safety-first posture (C-003, NFR-004), docmend could optionally hash-compare a **sampled** subset of covered paths' committed blob content (`repo.git.show(f'HEAD:{relpath}')`) against on-disk content, independent of Git's own cached dirty-bit — cheap insurance against a corrupted/stale index, applied as a sampled spot-check (per §2.2's sampling-is-for-external-verification-only distinction, this sampling is warranted here because it defends against index-cache staleness, not against docmend's own write path, and running it exhaustively at 100k-file scale would be needless overhead for a defense against a rare failure mode).

---

## 4. FR-005: substantiating backup-based preservation strategies

Three distinct backup postures appear in the spec/OQ-008, and they deserve different substantiation strength because docmend has different visibility into each:

### 4.1 Tool-written backups (docmend's own `write.backup_dir`)

This posture's substantiation **is** FR-006's own per-file verify-then-mutate result (§2). There is no separate "is the backup recent enough" question to ask, because every mutating apply run performs and verifies its own backup for every file it is about to touch, in the same run, immediately before mutation. The gate's job here is simply: confirm `backup_dir` is configured, writable, and **not contained within (or overlapping) `source_root`** (already an OQ-005 checklist item — "Backup destination... is outside the mutation target path" — implementable with the same `is_contained()` primitive `path-containment-toctou.md` already specifies for output-path containment) before the run starts, and then treat FR-006's per-file result as the strategy's proof for that file.

### 4.2 Filesystem snapshot / Borg / restic (OQ-008's "stronger local posture")

Here docmend is _not_ the tool performing the backup, so it cannot inline-verify the way §2 does. The recommended substantiation is a machine-readable receipt, produced by (or immediately after) the external backup step and read by docmend's safety gate before apply:

- After `borg create` or `restic backup` completes, capture the resulting archive/snapshot ID and timestamp — both tools report this on success and expose it for later querying (`borg list`, `restic snapshots --json`).
- Docmend's gate reads a small JSON receipt (e.g. `--backup-receipt PATH`, written by a wrapper script the owner runs immediately before `docmend apply`, or by a future first-party integration) containing at minimum `{"tool": "restic", "snapshot_id": "...", "timestamp": "...", "root": "..."}`.
- **Recency check:** `receipt.timestamp >= now - staleness_window` (a config value; default should be tight — e.g. the same run session, not a stale multi-day-old snapshot — since RPO is zero).
- **Coverage check, sampled rather than exhaustive:** restic's own `--read-data-subset=nS`/`n/t` design is the direct precedent for bounding verification cost by sampling a percentage or fixed-size slice of a repository rather than reading all of it [official, restic.readthedocs.io/en/stable/045_working_with_repos.html]. docmend's gate should apply the same idea at the coverage layer: run `restic find <sampled-path>` / `borg list --pattern <sampled-path>` for a bounded random sample of N paths drawn from this run's plan (not the whole 100k-file corpus) as a coverage smoke test. This proves "the declared snapshot plausibly contains recent versions of files this run is about to touch" without docmend paying the cost of a full `--read-data` pass on every apply — that full, expensive integrity read (`borg check --verify-data` / `restic check --read-data`) belongs in §18.6's periodic "Restore Test Cadence" drill, not the per-apply gate.

### 4.3 External backups declared (the weakest tier — and the one FR-005 currently under-specifies most)

This is the posture the research question is most pointedly about: today, "external backups declared" can be satisfied by a bare config boolean with zero verifiable evidence. Ranked substantiation tiers, from strongest to weakest, all stronger than a bare flag:

| Tier | Evidence required | Strength |
| --- | --- | --- |
| A | Tool-emitted receipt (§4.2's JSON shape) with a snapshot/archive ID docmend can independently query via `restic find`/`borg list` for sampled coverage | Strongest — machine-verifiable coverage, not just an attestation |
| B | A minimal timestamp + covered-root attestation file the user (or a cron job) writes/updates (e.g. `.docmend-backup-proof` with an ISO 8601 timestamp and the backed-up root path), checked only for **recency**, not content coverage | Weaker — proves _something_ happened recently, not that it covered the right files or that the copy was correct |
| C | A bare config boolean (`external_backup = true`) with no receipt at all | Insufficient — this is the status quo gap; the research question's framing ("trusting a config flag") describes exactly this tier |

**Recommendation:** FR-005 should refuse to accept Tier C as satisfying the gate. At minimum, require Tier B (recency-only attestation) so a stale or one-time "I backed this up once, six months ago" claim cannot silently satisfy a zero-RPO requirement indefinitely; strongly prefer Tier A wherever the external tool is inspectable (which covers Borg/restic/most serious backup tooling — see §4.2). This tiering should be recorded explicitly in the manifest/report so the operator (the owner, per §5 Stakeholders) can see which tier a given run actually relied on, rather than the report simply saying "preservation strategy: satisfied."

---

## 5. Timing: re-validate at time-of-use, not only at time-of-check

`path-containment-toctou.md` already establishes the load-bearing principle for this codebase: a plan-time check is a promise about the filesystem at plan time, and a batch apply run over 100k+ files (§14: "occasional incremental runs," potentially hours) can see that promise go stale before every file is actually written. The same window applies here, and for the same class of reason (the owner's own concurrent tooling — an editor, a second docmend invocation, a scheduled backup job — not an adversary; see that report's §5 threat-model analysis, which applies unchanged to this topic):

- A Git working tree that was clean when `apply` started can become dirty mid-run if the owner edits a file elsewhere while a long batch executes.
- A backup destination that had free space and was correctly mounted at gate-check time can fill up, or the mount can drop, mid-run — orthogonal to per-file FR-006 verification (§2), which still catches this per file, but the _strategy-level_ gate check (is `backup_dir` still writable and outside `source_root`) should not be trusted as a one-time-only fact for an hours-long run either.
- An external backup receipt's staleness window (§4.3) can simply expire while a long run is still in progress.

**Recommendation:** re-run the strategy-substantiation checks (§3, §4) at a bounded interval during a long apply run — e.g., every N files or every T minutes, whichever comes first, using the same config-driven proportionality this project already applies elsewhere (NFR-001's memory bounds, FR-013's resumability) — rather than only once at the very start of `apply`. This is cheap for the Git case (`is_dirty()` is fast) and cheap for receipt-based cases (re-reading a small JSON file's timestamp), so the cost is negligible relative to the risk it closes.

---

## 6. Proposed FR-005/FR-006 acceptance-criteria additions

These are drafted as fold-in candidates for §7.1 of `docs/specs/docmend.md`, phrased in the spec's own acceptance-criteria style, for the owner to review alongside OQ-005:

**FR-006 additions:**

1. When backups are enabled, apply computes an independent hash of the just-written backup file — re-read from disk after an explicit `fsync`, never reused from the in-memory write buffer — and compares it against the source hash already confirmed live by FR-003's stale-hash check; a mismatch aborts that file's mutation (ERR-004), leaves the original untouched, and is proven by a fixture in which the backup destination is truncated/corrupted after the copy syscall returns but before verification runs — asserting the original remains byte-identical to its pre-run state and the manifest records `backup_verified: false`.
2. A manifest entry's `backup_verified: true` field is set only after check (1) passes; the writer's atomic-replace of the original for a given file never executes before that file's `backup_verified` is `true` when the tool-written-backup strategy is active for it.
3. Backup writes are fsync'd before verification reads them back, so verification can never pass against page-cache-only bytes a crash could still lose — proven by the same crash-simulation harness NFR-002's kill-during-write test already exercises for the original write path, extended to cover the backup write.

**FR-005 additions:**

4. The safety gate resolves each declared preservation strategy to a concrete, machine-checked proof scoped to the specific files this run's plan will mutate, not a boolean config value. For the `git` strategy: the source root resolves inside a non-bare Git working tree; every covered file is tracked (`git ls-files`-equivalent); and `is_dirty(path=<covered paths>, untracked_files=True)` is `False` — proven by a fixture containing an untracked new file inside the covered subtree, which must fail this check even though the underlying library call's own default (`untracked_files=False`) would otherwise report the tree clean.
5. For the `tool-written backups` strategy, satisfaction for a given file is defined as that file's FR-006 `backup_verified: true` result — not merely the presence of a `backup_dir` config value.
6. For the `external backups declared` strategy, the gate requires at minimum a recency-checked attestation (Tier B, §4.3) — timestamp plus covered-root path, no older than a configured staleness window — and prefers a tool-emitted, sample-coverage-checkable receipt (Tier A) wherever the declared tool supports it; a bare config boolean with no receipt fails the gate.
7. For a batch apply run exceeding a configured duration/file-count threshold, the strategy proof from (4)–(6) is re-validated at a bounded interval during the run, not only once at the start.
8. Gate refusal messages name the specific strategy and the specific reason it failed (e.g. "git: 3 files untracked: [...]", "git: working tree dirty for covered paths", "external backup receipt stale: last verified 2026-06-01, staleness window 24h") rather than a generic "no preservation strategy satisfied" message.

---

## 7. Version/date sensitivity

- GitPython's documented `is_dirty()` default signature (`untracked_files=False`) was confirmed against the current stable API reference (GitPython 3.1.50 docs, pulled 2026-07) [official]; the `path` parameter has been supported since GitPython 2.0.8 per the project's own changelog [official] — both are long-stable, low-churn APIs, but any future GitPython major version should have this default re-confirmed before relying on it silently.
- `git diff-index --quiet`/`--exit-code` semantics and `git status --porcelain`'s script-stability guarantee are core, long-stable Git plumbing/porcelain behavior, not expected to change; cited against current git-scm.com documentation (2026).
- restic's `check`/`--read-data`/`--read-data-subset` behavior was confirmed against restic 0.19.1 docs (2026) [official]; borg's `check --verify-data` against current borgbackup stable docs [official]. Both tools' verification-is-separate-from-write design has been stable across major versions referenced in this research (restic 0.11–0.19, borg's current stable series) and is not expected to change materially.
- `shutil.copy2()`'s no-verification contract is a long-standing, unchanged stdlib behavior; no version sensitivity beyond confirming it remains true on Python 3.14 (it does — the module has not changed this behavior).

---

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://restic.readthedocs.io/en/stable/045_working_with_repos.html> | Working with repositories — restic 0.19.1 documentation (`check`, `--read-data`, `--read-data-subset`) | 2026 (current) | official |
| <https://borgbackup.readthedocs.io/en/stable/usage/check.html> | `borg check` — Borg Deduplicating Archiver 1.4.4 documentation | 2026 (current) | official |
| <https://manpages.debian.org/testing/borgbackup/borg-check.1.en.html> | borg-check(1) — Debian testing manpage | 2026 | community (distro-packaged manpage mirror of official docs) |
| <https://gitpython.readthedocs.io/en/stable/reference.html> | API Reference — GitPython 3.1.50 documentation (`is_dirty` full signature and default) | 2026 (current) | official |
| <https://github.com/gitpython-developers/gitpython> (via Context7 `doc/source/changes.md`, `doc/source/tutorial.md`, `doc/source/quickstart.md`) | GitPython documentation source: `is_dirty` path-filter history, `untracked_files` property, `iter_commits(paths=...)` | current | official |
| <https://git-scm.com/docs/git-diff-index> | Git - git-diff-index Documentation (`--quiet`, `--exit-code` semantics) | current | official |
| <https://git-scm.com/docs/pretty-formats> | Git - pretty-formats Documentation (`%cI` strict ISO 8601 committer date, `%H`) | current | official |
| <https://unix.stackexchange.com/questions/155046/determine-if-git-working-directory-is-clean-from-a-script> | Determine if Git working directory is clean from a script | community | community |
| <https://gist.github.com/sindresorhus/3898739> | Benchmark results of the fastest way to check if a git branch is dirty (`diff-index` vs `status --porcelain`, staleness caveat) | community | community |
| <https://stackoverflow.com/questions/3878624/how-do-i-programmatically-determine-if-there-are-uncommitted-changes> | `require_clean_work_tree()` idiom (`git-sh-setup`, `update-index --refresh`) | community | community |
| <https://docs.python.org/3/library/shutil.html> | `shutil` — High-level file operations (`copy2` contract, no verification) | 2026 (current, Python 3.14 docs) | official |
| <https://czyzykowski.com/posts/rsync-checksum.html> | rsync and checksums (default size/mtime shortcut vs `--checksum`) | community | community |
| <https://serverfault.com/questions/211005/rsync-difference-between-checksum-and-ignore-times-options> | rsync `--checksum` vs `--ignore-times` (algorithm detail, corroborating czyzykowski.com) | community | community |
| <https://www.reddit.com/r/DataHoarder/comments/ijy38s/i_transferred_all_data_from_one_drive_to_another/> | rsync checksum-verification-after-copy discussion (corroborates rsync does not verify post-write by default) | community | community |
| <https://learn.microsoft.com/en-us/answers/questions/4320236/robocopy-is-there-any-way-to-verify-the-copied-fil> | Robocopy has no built-in post-copy verification | community | community (Microsoft Q&A) |
| `docs/research/atomic-write-filesystem-semantics.md` (this repo) | fsync-before-rename discipline for D-004/NFR-002, extended here to backup writes | 2026-07-05 | project research (prior report) |
| `docs/research/path-containment-toctou.md` (this repo) | "Re-validate at time-of-use, not time-of-check" principle and threat-model scoping, applied here to preservation-strategy proofs | 2026-07-05 | project research (prior report) |

---

## Reconciliation notes

- **Fold into spec §7.1 FR-005/FR-006:** add the acceptance-criteria language in §6 above; the current FR-005/FR-006 rows and their acceptance-criteria columns should be expanded, not replaced, per the spec's living-document convention.
- **Fold into `docs/open-questions.md` OQ-005:** this report's §3–§4 substantiation procedures directly answer OQ-005's open question ("Define the exact apply safety-gate checklist and what satisfies the preservation strategy requirement"). Recommend adding a cross-reference from OQ-005's Agent notes to this report, and updating its "Decision impact" line to note that preservation-strategy satisfaction is now understood to be per-file and per-strategy-tier, not a single run-level boolean.
- **Fold into `docs/open-questions.md` OQ-008:** §4.2/§4.3's receipt-based substantiation design gives OQ-008's "stronger local posture" (Borg/restic) and "Git posture" options a concrete verification mechanism the current OQ-008 text does not specify.
- **GAP-34, GAP-35:** as with every other external `GAP-` ID referenced across this repo's research reports (GAP-19 through GAP-60, none of which exist as native identifiers in `docs/open-questions.md`, `docs/resolved-questions.md`, `docs/decisions/`, or `docs/handoff/*`), these are carried here verbatim as supplied by the calling task. No `GAP-` numbering scheme exists in-repo as of this writing; treat GAP-34/GAP-35 as external tracker references for the owner to reconcile, most naturally by folding their substance into OQ-005 as noted above rather than minting a parallel in-repo `GAP-` register.
- **Spec §21 table drift (re-confirmed, orthogonal to this topic):** re-verified during this pass that `docs/open-questions.md` still defines OQ-012, OQ-013, and OQ-014 with full Agent-notes/My-Comments sections, while `docs/specs/docmend.md` §21's table still stops at OQ-011 — consistent with the drift already documented independently in `docs/research/unicode-normalization-policy.md` and `docs/research/architecture-and-traceability-enforcement.md`. No new instances of this drift class were found during this pass beyond what those two reports already identified; this note is provided only as the requested independent re-verification, not as new information.
