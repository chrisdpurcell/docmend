# Atomic-Replace and Directory-Fsync Guarantees Across Filesystems

**Date:** 2026-07-05

**Related:** D-004, NFR-002, FR-011, A-001, OQ-003, OQ-005, OQ-008 (`docs/specs/docmend.md`); GAP-41 (external gap-analysis tracking ID — not yet present in this repo's own docs as of this writing; see Reconciliation Notes).

**Gap it fills:** D-004/NFR-002 specify the writer as "temp file + fsync + `os.replace` in the same directory + fsync parent directory where practical," and OQ-003/OQ-005 already lean on "`os.replace()` is atomic on the same filesystem" as supporting fact — but neither the spec nor the open questions currently say _which_ filesystems actually honor that atomicity end-to-end (name-swap atomicity vs. crash-durability of the new content are different guarantees), what "where practical" should mean operationally when a target directory's fsync is weak or absent (NFS, CIFS, some FUSE mounts), how a case-insensitive-but-preserving destination interacts with FR-011 collision detection, or which filesystems the CI kill-during-write test (NFR-002 acceptance criterion) should actually run against. This report closes that gap with a filesystem-by-filesystem evidence table, a concrete runtime-detection design, a degraded-mode reporting proposal, and a CI validation matrix.

## Bottom Line

1. **POSIX `rename()`/Python `os.replace()` atomicity is real but narrower than commonly assumed.** It guarantees that a reader never observes a half-written name (no window where the target path is missing or points at a partial file), _only_ when source and destination are on the same filesystem, and _only_ with respect to normal operation — not crashes. [1] [2] [3]
2. **Crash-durability of the new content is not guaranteed by `rename()` alone on any mainstream Linux filesystem except btrfs**, and even btrfs has documented edge cases. ext4 and XFS both require an explicit `fsync()` of the temp file _before_ `rename()` to guarantee the new content survives a crash — which is exactly what D-004/NFR-002 already specify. This is not belt-and-suspenders conservatism; it is load-bearing on ext4 and XFS. [4] [5] [6]
3. **NFS and CIFS/SMB weaken the atomicity contract further** because they add a second machine, a cache-coherence protocol, and (for CIFS/SMB) case-insensitive-but-preserving name resolution by default. docmend's A-001 assumption (local POSIX filesystem) should be enforced by runtime detection, not merely assumed. [7] [8] [9] [10]
4. **tmpfs is not a durability question at all — it is categorically volatile.** Nothing in tmpfs survives a reboot regardless of fsync outcome, so it should be refused as a write target, not merely warned about. [11]
5. **Case-insensitive-but-preserving destinations are a real, current risk**, not a hypothetical: ext4 supports opt-in per-directory casefolding, and any USB/exFAT/vfat/NTFS/CIFS mount changes FR-011's collision-detection assumptions. Plan-time collision detection must normalize-compare target paths using the _detected_ case-sensitivity of the destination, not assume Linux-default case-sensitive semantics. [12] [13] [14] [15]

## Filesystem-by-Filesystem Table

"Same-dir atomicity" = does `os.replace(tmp, target)` (same directory, same filesystem) guarantee no observer ever sees a missing/partial name. "Crash durability" = does the _new content_ reliably survive a crash without docmend calling `fsync()` on the temp file before the rename. "Dir-fsync" = what `fsync()` on an `O_DIRECTORY` file descriptor of the parent actually buys you there.

| Filesystem | Same-dir name atomicity | Crash durability without pre-rename fsync | Parent-dir fsync effect | Notes |
| --- | --- | --- | --- | --- |
| **ext4** (`data=ordered`, default) | Yes (normal operation) [1] [3] | **No** — the `auto_da_alloc` workaround forces the new file's data blocks to be flushed at the _next journal commit_, but `rename()` does not wait for that flush, so a crash can still leave partial new content; this is a best-effort mitigation for "broken applications," never a guarantee [4] [5] [16] | Meaningful — forces the journal commit (and thus the rename metadata + the delayed-allocation flush) to happen now rather than at the kernel's discretion | Academic crash-consistency testing (Pillai et al., OSDI'14) found ext4 does **not** provide full atomic-replace-via-rename (ARVR) across crashes [6] |
| **btrfs** | Yes [1] [3] | **Yes** — the only mainstream Linux filesystem documented (and empirically confirmed) to provide full ARVR without a preceding `fsync()`, per its own FAQ and per Pillai et al.'s testing [6] [17] | Still worth doing: on kernels where the file was previously `fsync()`'d, the following `rename()` triggers a parent-directory log flush and waits for the whole log tree to be written — expensive but real | Caveats: ARVR is documented as reliable only for _replace_ (overwriting an existing name), not _create_; independent crash-consistency research (Mohan et al., OSDI'18) found rename-atomicity bugs on btrfs, some newly introduced; do not treat "btrfs never needs fsync" as license to skip it in shared code paths [18] [19] |
| **XFS** | Yes [1] [3] | **No** — XFS maintainers explicitly rejected adding an ext4-`auto_da_alloc`-style workaround for the rename case; XFS provides no implicit data-durability guarantee on replace-via-rename [20] [21] | Meaningful and, on XFS, **mandatory** — without an explicit `fsync()` before rename and a `fsync()` of the parent directory, a crash can leave zero-length or partial content | Of the three "local strong" filesystems, XFS is the one where skipping D-004's explicit fsync would be most immediately dangerous |
| **ZFS** (OpenZFS) | Yes — rename is one atomic operation inside a transaction group (txg); ZFS's copy-on-write design commits whole txgs atomically, so on-disk state is always one of "before" or "after" [22] [23] | Architecturally yes, by design (COW + txg atomicity) — but **not independently corroborated** by the same crash-consistency benchmark methodology used for ext4/btrfs/XFS (Pillai et al.'s OSDI'14 study covers Linux-native ext2/3/4, btrfs, XFS; it does not test ZFS) | The ZIL (ZFS Intent Log) handles synchronous-durability requests; an explicit `fsync()` still has value for making a specific write's durability request explicit rather than relying on txg timing | **Confidence: medium** — strong architectural claim from official OpenZFS/FreeBSD docs, but not benchmarked against the same academic methodology as the others; validate empirically in CI (see below) before relying on it as a "strong" tier without qualification |
| **tmpfs** / ramfs | Yes, as a VFS-level rename (it's an in-memory filesystem, so the "same filesystem" rename path is taken) [1] [24] | **Not applicable — durability across a crash/reboot is impossible by construction.** tmpfs keeps all file data in the page cache/swap; the kernel documentation states plainly that nothing in tmpfs is ever written to persistent storage [24] | `fsync()` succeeds (there is nothing to flush past the page cache) but provides **zero durability guarantee across a reboot**, which is a fundamentally different failure mode than "fsync is weak" — it's "fsync is meaningless for this purpose" | Must be refused as a write target outright, not merely flagged (see Degraded-Mode Behavior below) |
| **NFS** (v3/v4) | RFC-mandated "atomic to the client" for the _issuing_ client [7] [8] | **Weaker in practice.** RFC 7530 (NFSv4) requires RENAME be atomic to the client issuing it, but this is explicitly _not_ a cross-client visibility guarantee: other clients relying on close-to-open cache consistency can observe stale directory state, and there are documented `ENOENT` races on production NFS servers during overwrite-renames [7] [8] [9] [25] | `fsync()` triggers a client→server COMMIT of that client's own pending writes, but does not establish a barrier visible to other clients, and durability still depends on server-side write-back behavior outside docmend's control | docmend's A-001 assumes a local POSIX filesystem; NFS should be _detected_, not silently trusted to behave like local ext4/xfs/btrfs |
| **CIFS/SMB** (Samba or native Windows/NAS share) | Same-filesystem renames on a Samba server are implemented by calling the underlying **POSIX `rename()` server-side** — so the real guarantee is whatever the underlying export filesystem provides (ext4/xfs/btrfs/zfs), transported through SMB [10] | Same as whichever local filesystem backs the share, _plus_ SMB-protocol overhead; cross-share/cross-filesystem renames fall back to non-atomic copy+delete | No portable client-side directory-fsync primitive comparable to POSIX `fsync(O_DIRECTORY fd)`; durability is governed by the SMB server's own commit behavior | **Case-insensitive-but-preserving by default** on Windows/Samba defaults (`case sensitive = no`, `preserve case = yes`) — this is a distinct, additional risk from atomicity and is documented in production multiprotocol NAS guidance (e.g. NetApp ONTAP: SMB clients see case-insensitive/case-preserving names while NFS clients on the _same_ volume see case-sensitive names) [10] [14] [26] |
| **overlayfs** (Docker `overlay2`, many CI runners, live-boot images) | Depends on layer state: renaming a file already on the upper (writable) layer is a normal same-filesystem rename on whatever real filesystem backs `upperdir`; renaming a directory that exists only on a lower layer or is "merged" returns `EXDEV` by default (or, with `redirect_dir=on`, triggers a copy-up plus an xattr redirect marker before the rename completes) [27] [28] | Whatever the real filesystem backing `upperdir` provides (commonly ext4, sometimes tmpfs for ephemeral workdirs) | Whatever the real filesystem backing `upperdir` provides | Directly relevant to CI: Docker's `overlay2` storage driver is a common choice for containerized CI jobs (including containerized GitHub Actions steps) — meaning a "local filesystem" CI job may actually be exercising overlayfs-over-ext4 semantics, not bare ext4 [29] [30] |

## POSIX/Python Baseline

- Linux `rename(2)`: "If `newpath` already exists, it will be atomically replaced, so that there is no point at which another process attempting to access `newpath` will find it missing. However, there will probably be a window in which both `oldpath` and `newpath` refer to the file being renamed." [official, man7.org] [1]
- This atomicity is **not crash atomicity**. POSIX is largely silent on behavior across a crash; the guarantee is about concurrent _readers_ under normal operation, not about what state survives a power loss mid-operation. [3] [6]
- CPython's own tracker has an open issue (as of this writing) that the `os.rename`/`os.replace` documentation's "atomic" language is misleading in exactly this way — it documents same-vs-different-file visibility, not crash durability, and does not claim the old and new names can never simultaneously reference the same file transiently. [2]
- `os.replace()` on POSIX maps directly to `rename(2)`/`renameat2(2)` and only guarantees atomicity **when source and destination are on the same filesystem**; docmend's writer design (temp file in the same directory as the target) already satisfies this precondition and should keep doing so — never create the temp file in a different directory or a different mount. [1] [2]
- Windows note (out of scope for A-001, recorded for completeness): `os.replace()` on Windows uses `MoveFileEx()` with `MOVEFILE_REPLACE_EXISTING`, whose atomicity story is materially different from POSIX `rename()`; if docmend is ever ported off Linux this whole analysis needs redoing, not just re-tested. [31]

## Detecting Weak-Semantics Filesystems at Runtime

Recommended design, scoped to fit the existing layered architecture (§8 of the spec) without adding a new dependency beyond the stdlib:

1. **Classify the target filesystem once per run, at scan/plan time**, by resolving the target directory's mount point and reading its filesystem-type string directly out of `/proc/mounts` (or `/proc/self/mountinfo` for bind-mount-aware resolution) — match the longest mount-point prefix for the target path and read the `fstype` field. This avoids needing `ctypes` bindings for `statfs(2)`'s `f_type` magic-number field (which historically requires cross-referencing `linux/magic.h` constants and is not exposed by the stdlib `os.statvfs()`, since POSIX `statvfs` has no `f_type` member at all — that's a Linux-specific `statfs(2)` field). [32] [33] [34]
   - Optional stronger alternative if a dependency is later approved: `psutil.disk_partitions(all=True)` wraps this same `/proc/mounts` parsing cross-platform and already reports `fstype` per mount, including network filesystems when `all=True`; would need an `OQ-` entry per §8.6 dependency policy since `psutil` is not currently on the allowlist. [35]
2. **Classify the fstype string into durability tiers**:
   - `strong`: `ext4`, `ext3`, `ext2`, `xfs`, `btrfs`, `zfs`
   - `volatile`: `tmpfs`, `ramfs`
   - `weak_network`: `nfs`, `nfs4`, `cifs`, `smb3`, `smbfs`, `fuse.sshfs`, `glusterfs`, `ceph`, and similar
   - `union`: `overlay` (report the type but don't hard-block; the practical guarantee comes from the backing `upperdir`, which is generally not discoverable from userspace without parsing the overlay mount options)
   - `unknown`: anything else — treat conservatively, as `weak_network`
3. **Probe case-sensitivity of the destination directory once per run**, using a create-two-differently-cased-files-in-a-fresh-directory technique (more robust than checking for the existence of an upper/lower-cased variant of an unrelated path, which can produce false negatives/positives depending on what already exists) [37]. Record `case_sensitive: true|false|unknown` in the scan configuration snapshot (DR-001) so planning can use it.
4. **At writer time**, after `os.replace()`, attempt `os.fsync()` on an `os.open(parent_dir, os.O_RDONLY | os.O_DIRECTORY)` descriptor, exactly as D-004 already specifies ("fsync parent directory where practical"). Classify the outcome:
   - Success on a `strong`-tier filesystem: full confidence, log at debug level only.
   - `OSError` (`EINVAL`, `ENOTSUP`, `EBADF`-class errno, or platform-specific "operation not supported") on any tier: filesystem doesn't support directory fsync — log once per (filesystem, error) pair, continue the run; NFR-002's "where practical" clause exists precisely for this case.
   - Success on a `weak_network` or `unknown` tier: treat as **advisory, not proof of durability** — network filesystems can report a successful local `fsync()` while server-side commit semantics remain outside docmend's visibility, and even purely local kernel `fsync()` error reporting has a documented history of being unreliable after a first failure (the 2018 PostgreSQL "fsync error handling" issue, colloquially "fsyncgate," showed the kernel can mark a page clean — and thus report success on retry — even though the data was never durably written) [36]. This is a caution about _trusting_ fsync success blindly, not a reason to skip calling it.

## Proposed Degraded-Mode Behavior and Report

- Extend the apply report (DR-003) and manifest (DR-004) with a per-run `durability` block (not per-file — at 100k+ files, a per-file durability record would either be redundant with the once-per-run filesystem classification or would flood the report):

  ```yaml
  durability:
    target_filesystem:
      type: 'ext4' # raw fstype string from /proc/mounts
      durability_class: 'strong' # strong | weak_network | volatile | union | unknown
      case_sensitive: true
    dir_fsync:
      attempted: true
      succeeded: true
      unsupported_errno: null
    warnings: [] # populated only on weak/volatile/unknown classification
  ```

- **`volatile` (tmpfs/ramfs): refuse to write by default.** This is not a durability _degradation_ — it is an inability to satisfy G-002 ("zero irreversible loss of original content") even in principle, since nothing survives past the next reboot regardless of fsync outcome. Treat this as an extension of the FR-005 safety gate ("preservation strategy satisfied"), not merely a louder warning: a run targeting a `volatile` filesystem should fail the safety gate the same way a missing preservation strategy does, with a distinct, explanatory error message.
- **`weak_network` or `unknown`: warn once, proceed by default.** Emit a single run-level warning (not per-file) the first time such a filesystem is encountered in a run: _"Target is on filesystem type=nfs4 (durability class: weak_network); atomic-replace and durability guarantees are weaker than on local ext4/xfs/btrfs/zfs — see report `durability` block for details."_ Record the classification in the manifest so a later `verify` run or a post-hoc audit of an anomaly has the context without re-deriving it. Add an opt-in `write.require_strong_filesystem` config flag (default `false`) that promotes this warning to a hard safety-gate refusal for owners who want the stricter guarantee — this keeps NFR-004's "conservative by default" posture intentional and owner-controlled rather than surprising, since docmend's actual expected deployment (A-001, local Linux workstation) should land in `strong` in practice, and a hard default block would be pure friction for the primary use case.
- **`union` (overlayfs): report but don't block.** The practical guarantee tracks the backing filesystem, which is only knowable by resolving the "upperdir" mount option, and CI use of overlayfs is expected and fine (see below); surfacing the classification is enough for now.

## Case-Insensitive-but-Preserving Filesystems and FR-011

FR-011's collision policy (`skip`/`fail`/`overwrite`) is defined in terms of "does the target path already exist." That check is correct _at apply time_ against the real filesystem (the OS itself resolves case-insensitively if the underlying directory is case-insensitive, so a live `stat()`/`exists()` call will not be fooled). The actual risk is a **plan/apply divergence**: if the _planning_ layer compares candidate target paths as exact strings (the natural default), two source files that are distinct strings but would resolve to the same physical name on a case-insensitive-but-preserving destination (e.g. an existing `Report.md` versus a newly planned `report.md`) will not be flagged as a collision during `plan`, then either silently overwrite (under an `overwrite` policy) or produce a plan/apply-time surprise (under `skip`/`fail`) that the plan itself never predicted — a real violation of FR-002's "collisions caught before any file is touched" intent and FR-003's "apply executes only what the plan decided."

This is not hypothetical for docmend's actual environment:

- **ext4 supports opt-in, per-directory case-insensitivity** (`casefold` filesystem feature + `+F` inode attribute on an _empty_ directory), name-preserving on disk, using Unicode canonical-decomposition normalization for comparisons — available since Linux 5.2, and also supported by f2fs, tmpfs, and overlayfs. [12] [13]
- **Any externally-mounted vfat/exFAT/NTFS media** (a very plausible destination or backup target for a personal document library — e.g. a USB drive) is case-insensitive-but-preserving by default on Linux, independent of the host root filesystem's own case sensitivity. [37]
- **CIFS/SMB shares** are case-insensitive-but-preserving by default on the Windows/Samba side even when the underlying Linux export filesystem is case-sensitive — a documented, current concern in multiprotocol NAS deployments (NFS clients see case-sensitive names, SMB clients see case-insensitive/preserving names, on the _same_ underlying data). [10] [14] [26]

**Recommendation:** at scan/plan time, use the case-sensitivity probe described above (once per source root and once per output root, since they may differ) and store the result in the plan's config snapshot (DR-002). The planning layer should then normalize-compare all candidate target paths (case-fold them) whenever the _destination_ is detected or assumed case-insensitive, catching same-normalized-form collisions as FR-011 collisions regardless of exact-string difference — with the collision reason explicitly naming case-folding as the cause, so the report distinguishes "two files map to the identical name" from "two files map to the same name modulo case," which the owner will need to disambiguate manually in the `fail`/`skip` case.

## Recommended CI Filesystem Validation Matrix

In priority order, mapped to the NFR-002 kill-during-write acceptance criterion and the new detection/degraded-mode logic above:

| Priority | Filesystem | Setup cost in CI | What it validates |
| --- | --- | --- | --- |
| Must | **ext4** (default mount options) | Free — default on almost every Linux CI runner | The primary real-deployment target (A-001); the actual kill-during-write NFR-002 test |
| Must | **tmpfs** | Free — `mount -t tmpfs` or a tmpfs-backed temp dir | The "refuse to write, safety-gate failure" path deterministically, without special runner privileges |
| Should | **btrfs** (loopback image via `mkfs.btrfs` on a sparse file, loop-mounted) | Low — `btrfs-progs` is a common CI package; no special privileges beyond loop-mount | The stronger ARVR guarantee path and the "advisory success, still log" classification for a `strong`-tier filesystem with different internals than ext4 |
| Should | **XFS** (loopback image via `mkfs.xfs`) | Low — same pattern as btrfs, `xfsprogs` is common | The filesystem where D-004's pre-rename `fsync()` is not optional; a regression here (e.g. someone "optimizing away" the fsync) should be caught here first |
| Should | **overlayfs** (upperdir on ext4 or tmpfs, workdir alongside) | Low-medium — needs `mount -t overlay`, works unprivileged in many modern container runtimes, may need `--cap-add SYS_ADMIN` in some CI sandboxes | Represents the filesystem many CI jobs (including possibly docmend's own CI) are _already_ running on via Docker's `overlay2` driver — validates that the classification logic reports `union` correctly rather than misreporting the backing filesystem |
| Could | **ZFS** (loopback zpool via `zfsutils-linux`, widely available on Ubuntu runners) | Medium — needs the ZFS kernel module loaded, which is not guaranteed on every CI image | Primarily to validate the _detection/classification_ path for a plausible OQ-008 backup-target filesystem, and to start building empirical evidence for the "architecturally atomic but not independently benchmarked" caveat above |
| Could / exploratory | **Loopback NFS** (`nfs-kernel-server` exporting a local directory to `127.0.0.1`) | High — needs a running `nfsd`, real mount privileges, and is fragile in sandboxed CI | Validate the _detection_ path (classify as `weak_network`, warn, proceed) end-to-end; do **not** attempt to validate NFS's actual crash-atomicity in CI — that is a server/network property outside docmend's control and disproportionate to test with academic-grade crash-injection tooling for a single-user tool |
| Deprioritized | **CIFS/SMB** | High — needs a running `smbd`/Samba stack | Rely on the classification+warning path alone (`fstype=cifs`/`smb3` string match) without a dedicated CI job; revisit only if OQ-008 selects a CIFS-backed NAS as the real preservation posture |

Do not attempt genuine power-cut/crash-injection testing (the ALICE/dm-flakey-style tooling used in Pillai et al.'s own study) — that is disproportionate engineering for docmend's single-user, offline, safety-first scope; a kill-9-during-write integration test against real `strong`-tier loopback filesystems (already an NFR-002 acceptance criterion) is the right level of rigor here.

## Recommendation for docmend

1. **Keep D-004/NFR-002 exactly as specified** (temp file → fsync → `os.replace` → fsync parent directory where practical) — the research confirms this is necessary, not excessive, specifically because of ext4's and XFS's documented lack of an implicit replace-via-rename durability guarantee. Make this rationale explicit in §8.3's D-004 row so a future maintainer doesn't remove the pre-rename `fsync()` under the common misconception that POSIX rename alone is crash-atomic.
2. **Add filesystem-type detection to the scan layer** (via `/proc/mounts` string parsing, no new dependency) and thread a `durability` classification through the plan/apply/report/manifest artifacts (new fields for OQ-004's schema-pinning work).
3. **Extend the FR-005 safety gate** to hard-refuse `volatile` (tmpfs/ramfs) targets by default, and add an opt-in `write.require_strong_filesystem` config flag to hard-refuse `weak_network`/`unknown` targets for owners who want it — default posture remains warn-and-proceed on those, matching NFR-004's "conservative by default, not paranoid by default" intent for the actually-expected local-filesystem deployment.
4. **Add a case-sensitivity probe to the scan layer** and feed it into FR-011's planning-time collision detection so plan/apply divergence on case-insensitive-but-preserving destinations (ext4 casefold directories, vfat/exFAT/NTFS media, CIFS/SMB shares) is caught at plan time, not discovered as a surprising apply-time overwrite or an unpredicted collision report.
5. **Validate NFR-002 in CI against ext4 and tmpfs at minimum (Must)**, add btrfs/XFS/overlayfs loopback jobs (Should) given their low setup cost and direct relevance to the documented divergent behaviors above, and treat ZFS/NFS/CIFS as detection-path-only validation (Could) rather than attempting to reproduce their crash-consistency properties in CI.

## Open Questions Surfaced

| # | Question | Why unresolved |
| --- | --- | --- |
| 1 | Should the new filesystem-durability classification be a new top-level `OQ-` (e.g. `OQ-015`) or folded into the existing OQ-005 safety-gate checklist? | Both are defensible; needs an owner decision on how granular the `docs/open-questions.md` backlog should get for a single writer-layer sub-feature. |
| 2 | Is `psutil` worth approving as a dependency (§8.6) for more robust cross-platform mount/fstype detection, or is `/proc/mounts` parsing sufficient given A-001's Linux-only assumption? | Depends on whether cross-platform portability is ever a real goal; out of scope for this research pass. |
| 3 | ZFS's crash-atomicity claim is architectural/official-doc-sourced but not independently benchmarked by the same academic methodology used for ext4/btrfs/XFS — is that gap acceptable for v1, or does it justify a dedicated crash-injection test before ZFS is treated as `strong` tier? | No published equivalent of the Pillai et al. study covering ZFS was found in this research pass; flagged as medium-confidence rather than researched further, per the one-follow-up-pass cap. |

## Reconciliation Notes

Fold this research back into:

- **`docs/specs/docmend.md` §8.3 (D-004)** — add the ext4/XFS "no implicit durability guarantee" rationale so the pre-rename fsync isn't seen as optional.
- **`docs/specs/docmend.md` §7.1 FR-011 and §7.2 NFR-002** — extend acceptance criteria to cover filesystem-durability classification and case-insensitive-destination collision detection.
- **`docs/open-questions.md`** — consider a new OQ (tentatively `OQ-015`) for "filesystem durability detection and degraded-mode policy," referencing this report; also extend OQ-005's safety-gate checklist draft with the tmpfs-refusal and `require_strong_filesystem` items, and OQ-004's schema-pinning work with the proposed `durability` block fields.
- **§21's OQ table drift** noted in this task's framing (spec table stops at OQ-011 while `docs/open-questions.md` already has OQ-012–014) is a pre-existing gap unrelated to this research topic's specific deliverables; whichever session owns closing that drift should also add the new durability-related OQ at the same time so the table doesn't fall behind again immediately.
- **GAP-41**, referenced in this research request, was not found in any tracked docmend document as of this writing (`docs/open-questions.md`, `docs/resolved-questions.md`, `docs/deep-research-queue.md`, `docs/decisions/`, `docs/handoff/*` were all checked). Whoever maintains the external gap-analysis list should link this report from that entry once it lands in-repo.

## Sources

| URL | Title | Date/Version Sensitivity | Authority |
| --- | --- | --- | --- |
| <https://man7.org/linux/man-pages/man2/rename.2.html> | rename(2) — Linux manual page | Current Linux man-pages project rendering (2026-05-30) | [official] |
| <https://github.com/python/cpython/issues/143909> | os.rename documentation about atomic replace misleading | Open CPython issue, current as of this writing | [official] |
| <https://unix.stackexchange.com/questions/464382/which-filesystems-require-fsync-for-crash-safety-when-replacing-an-existing-fi> | Which filesystems require fsync() for crash-safety when replacing an existing file with rename()? | Community answer citing Pillai et al. OSDI'14 directly; stable, widely-cited | [community] |
| <https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-pillai.pdf> | On the Complexity of Crafting Crash-Consistent Applications (Pillai et al., OSDI '14) | Academic/peer-reviewed, 2014 — methodology still the reference benchmark for this topic | [official] |
| <https://en.wikipedia.org/wiki/Ext4#Delayed_allocation_and_potential_data_loss> / <https://www.spinics.net/lists/linux-ext4/msg38774.html> | ext4 `auto_da_alloc` replace-via-rename data-loss workaround | ext4 developer mailing-list explanation; behavior stable since the fix landed (mid-2000s era) | [community] (developer-authored, treated as primary) |
| <https://lore.kernel.org/lkml/YxDFewyU6orvSfZX@mit.edu/T/> | [PATCH] ext4: ensure data forced to disk when rename | ext4 kernel mailing list, 2022 — confirms `auto_da_alloc` is "best effort," never a guarantee | [official] |
| <https://www.spinics.net/lists/xfs/msg36717.html> | State of ext4 auto_da_alloc-like workarounds in XFS | XFS mailing list — confirms XFS maintainers rejected the workaround | [official] |
| <https://lwn.net/Articles/323067/> | ext4 and data loss | LWN, 2009 — corroborating XFS's differing behavior and reputation | [community] |
| <https://btrfs.wiki.kernel.org/index.php/FAQ#What_are_the_crash_guarantees_of_overwrite-by-rename.3F> (via Brave search snippet) | Btrfs FAQ: crash guarantees of overwrite-by-rename | Project wiki, stable | [official] |
| <https://github.com/remzi-arpacidusseau/ostep-code/issues/10> | OSTEP: is rename() actually atomic? | Cites Bornholt et al. ASPLOS'16 and Mohan et al. OSDI'18 on btrfs rename-atomicity edge cases/bugs | [community] |
| <https://docs.kernel.org/admin-guide/ext4.html> and <https://man7.org/linux/man-pages/man5/ext4.5.html> | ext4 casefold feature | Official kernel docs; `casefold` present since Linux 5.2 | [official] |
| <https://www.collabora.com/news-and-blog/blog/2020/08/27/using-the-linux-kernel-case-insensitive-feature-in-ext4> | Using the Linux kernel's Case-insensitive feature in Ext4 | Vendor engineering blog, 2020 — implementation walkthrough | [blog] |
| <https://www.igalia.com/downloads/slides/AndreAlmeida-ImplementingCaseInsensitiveFileSystemsInTheLinuxKernel.pdf> | Implementing case-insensitive file systems in the Linux kernel (OSS Japan 2025) | Conference slides from the kernel feature's maintainer-adjacent developer; confirms tmpfs/overlayfs casefold support | [community] |
| <https://datatracker.ietf.org/doc/html/rfc7530> | RFC 7530 — NFSv4 Protocol, RENAME operation | IETF standard, 2015 | [official] |
| <https://nfs.sourceforge.net/> | Linux NFS FAQ — close-to-open cache consistency | Long-standing canonical Linux NFS client FAQ | [community] (canonical/authoritative in practice) |
| <https://serverfault.com/questions/817887/rename-on-nfs-atomicity> and <https://stackoverflow.com/questions/41362016/rename-atomicity-and-nfs> | rename() atomicity and NFS, multi-client caveats | Practitioner Q&A corroborating RFC text's client-scoped atomicity | [community] |
| <https://comp.protocols.smb.narkive.com/aLV92yYL/are-moves-within-a-samba-share-atomic> | Are moves within a Samba share atomic? (Jeremy Allison, Samba core developer) | Samba developer mailing list, developer-authored | [community] (developer-authored, treated as primary) |
| <https://docs.netapp.com/us-en/ontap/smb-admin/case-sensitivity-file-directory-multiprotocol-concept.html> | Case-sensitivity of ONTAP SMB file and directory names in a multiprotocol environment | Vendor official docs, current | [official] |
| <https://docs.kernel.org/filesystems/overlayfs.html> and <https://www.kernel.org/doc/Documentation/filesystems/overlayfs.txt> | Overlay Filesystem — Linux kernel documentation | Official kernel docs, current | [official] |
| <https://docs.docker.com/engine/storage/drivers/overlayfs-driver> | OverlayFS storage driver — Docker Docs | Official Docker docs, current | [official] |
| <https://www.kernel.org/doc/html/latest/filesystems/tmpfs.html> | Tmpfs — The Linux Kernel documentation | Official kernel docs, current | [official] |
| <https://openzfs.github.io/openzfs-docs/man/master/8/zfs.8.html> and <https://docs.freebsd.org/en/books/handbook/zfs> | OpenZFS docs / FreeBSD Handbook — transaction groups | Official project/vendor docs | [official] |
| <https://man7.org/linux/man-pages/man2/statfs.2.html> and <https://man7.org/linux/man-pages/man3/statvfs.3.html> | statfs(2) / statvfs(3) — Linux manual pages | Official, current | [official] |
| <https://unix.stackexchange.com/questions/77820/test-if-a-file-is-on-nfs> | Test if a file is on NFS? | Corroborates `/proc/mounts`/`statfs` f_type approach | [community] |
| <https://stackoverflow.com/questions/7870041/check-if-file-system-is-case-insensitive-in-python> | Check if file system is case-insensitive in Python | Corroborates the dual-touch-in-fresh-directory probe technique (accepted-answer critique of naive approaches) | [community] |
| <https://pypi.org/project/psutil> and <https://github.com/giampaolo/psutil> | psutil — cross-platform disk_partitions()/fstype | Official project docs, current (7.2.x as of this writing) | [official] |
| <https://wiki.postgresql.org/wiki/Fsync_Errors> | Fsync Errors — PostgreSQL wiki ("fsyncgate") | Official project wiki documenting the 2018 fsync error-handling issue; still the canonical reference | [official] |

<!-- Reference-link definitions for the bracketed inline citations above. -->

[1]: https://man7.org/linux/man-pages/man2/rename.2.html 'rename(2) — Linux manual page'
[2]: https://github.com/python/cpython/issues/143909 'os.rename documentation about atomic replace misleading'
[3]: https://unix.stackexchange.com/questions/464382/which-filesystems-require-fsync-for-crash-safety-when-replacing-an-existing-fi 'Which filesystems require fsync() for crash-safety when replacing an existing file with rename()?'
[4]: https://www.spinics.net/lists/linux-ext4/msg38774.html 'ext4 file replace guarantees (linux-ext4 mailing list)'
[5]: https://lore.kernel.org/lkml/YxDFewyU6orvSfZX@mit.edu/T/ '[PATCH -next] ext4: ensure data forced to disk when rename'
[6]: https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-pillai.pdf "On the Complexity of Crafting Crash-Consistent Applications (Pillai et al., OSDI '14)"
[7]: https://datatracker.ietf.org/doc/html/rfc7530 'RFC 7530 — NFSv4 Protocol, RENAME operation'
[8]: https://nfs.sourceforge.net/ 'Linux NFS FAQ — close-to-open cache consistency'
[9]: https://serverfault.com/questions/817887/rename-on-nfs-atomicity 'rename() on NFS atomicity'
[10]: https://comp.protocols.smb.narkive.com/aLV92yYL/are-moves-within-a-samba-share-atomic 'Are moves within a Samba share atomic? (Jeremy Allison, Samba core developer)'
[11]: https://www.kernel.org/doc/html/latest/filesystems/tmpfs.html 'Tmpfs — The Linux Kernel documentation'
[12]: https://docs.kernel.org/admin-guide/ext4.html 'ext4 General Information — The Linux Kernel documentation'
[13]: https://man7.org/linux/man-pages/man5/ext4.5.html 'ext4(5) — Linux manual page'
[14]: https://docs.netapp.com/us-en/ontap/smb-admin/case-sensitivity-file-directory-multiprotocol-concept.html 'Case-sensitivity of ONTAP SMB file and directory names in a multiprotocol environment'
[15]: https://docs.tuxera.com/docs/latest/configuration/smb-features 'SMB Features and Settings — Tuxera Documentation'
[16]: https://en.wikipedia.org/wiki/Ext4#Delayed_allocation_and_potential_data_loss 'ext4 — Delayed allocation and potential data loss'
[17]: https://btrfs.wiki.kernel.org/index.php/FAQ#What_are_the_crash_guarantees_of_overwrite-by-rename.3F 'Btrfs FAQ — crash guarantees of overwrite-by-rename'
[18]: https://github.com/remzi-arpacidusseau/ostep-code/issues/10 'file-intro page 13: is rename() actually atomic?'
[19]: https://news.ycombinator.com/item?id=37117291 'Things Unix can do atomically — discussion of Bornholt/Mohan rename-atomicity research'
[20]: https://www.spinics.net/lists/xfs/msg36717.html 'Re: State of ext4 auto_da_alloc-like workarounds in XFS'
[21]: https://lwn.net/Articles/323067/ 'ext4 and data loss — LWN.net'
[22]: https://openzfs.github.io/openzfs-docs/man/master/8/zfs.8.html 'zfs.8 — OpenZFS documentation'
[23]: https://docs.freebsd.org/en/books/handbook/zfs 'Chapter 22. The Z File System (ZFS) — FreeBSD Documentation'
[24]: https://www.kernel.org/doc/html/latest/filesystems/tmpfs.html 'Tmpfs — The Linux Kernel documentation'
[25]: https://stackoverflow.com/questions/41362016/rename-atomicity-and-nfs 'rename() atomicity and NFS?'
[26]: https://docs.netapp.com/us-en/ontap/smb-admin/case-sensitivity-file-directory-multiprotocol-concept.html 'Case-sensitivity of ONTAP SMB file and directory names in a multiprotocol environment'
[27]: https://docs.kernel.org/filesystems/overlayfs.html 'Overlay Filesystem — The Linux Kernel documentation'
[28]: https://www.kernel.org/doc/Documentation/filesystems/overlayfs.txt 'overlayfs.txt — The Linux Kernel Archives'
[29]: https://docs.docker.com/engine/storage/drivers/overlayfs-driver 'OverlayFS storage driver — Docker Docs'
[30]: https://github.com/concourse/concourse/issues/1045 'Switch from btrfs to some other filesystem to resolve stability issues (notes Docker overlay2 usage in CI)'
[31]: https://stackoverflow.com/questions/51862186/is-os-replace-atomic-on-windows 'Is os.replace() atomic on Windows?'
[32]: https://manpages.ubuntu.com/manpages/noble/man2/statfs.2.html 'statfs, fstatfs — get filesystem statistics'
[33]: https://man7.org/linux/man-pages/man3/statvfs.3.html 'statvfs(3) — Linux manual page'
[34]: https://unix.stackexchange.com/questions/77820/test-if-a-file-is-on-nfs 'Test if a file is on NFS?'
[35]: https://pypi.org/project/psutil 'psutil — Cross-platform lib for process and system monitoring'
[36]: https://wiki.postgresql.org/wiki/Fsync_Errors 'Fsync Errors — PostgreSQL wiki'
[37]: https://stackoverflow.com/questions/7870041/check-if-file-system-is-case-insensitive-in-python 'Check if file system is case-insensitive in Python'
