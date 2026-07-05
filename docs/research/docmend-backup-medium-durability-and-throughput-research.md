# docmend Backup-Medium Durability and Throughput Research

Date: 2026-07-05  
Language: en-US

## Executive summary

Your current safety model is the classic durable-rewrite pattern: make a backup copy, write a new temp file, `fsync()` the file data, `os.replace()` it into place, and `fsync()` the parent directory so the name update is durable. On Linux, that last directory `fsync()` is not optional if you want the rename itself to survive a crash; `rename()` gives atomic namespace replacement, but `fsync(file)` does not imply the directory entry is on stable storage. [\[1\]](https://man7.org/linux/man-pages/man2/fsync.2.html)

The most important practical result is this: **if the library being rewritten stays on your local SSD and only the backup destination changes, your measured local parent-directory** `fsync` **cost does not move with the backup medium.** What moves is only the backup-copy side of the stage. If the source library itself is on NFS, SMB, or a USB HDD, then the temp-file `fsync`, rename durability, and parent-directory `fsync` all move onto that slower medium too, and the slowdown is much larger. This follows directly from where the syscalls land in the algorithm. [\[1\]](https://man7.org/linux/man-pages/man2/fsync.2.html)

Among the media you asked about, only **local filesystems and carefully configured network filesystems** can approximate docmend’s current durability contract. A local USB HDD can honor the same semantics as any other local POSIX filesystem, but its `fsync` latency is far worse than SSD. NFS can preserve durability only when the server uses `sync` exports; `async` explicitly allows replies before stable-storage commit and Linux NFS documentation notes that it can affect metadata operations too. SMB/CIFS can be safe enough only with a client/server pair that actually honors flushes; on Linux that means at least `cache=strict` on the client side, and on Samba the default since 4.7 is `strict sync = yes`, but that safety can still be weakened by server configuration or by appliance behavior you do not control. [\[2\]](https://man7.org/linux/man-pages/man5/exports.5.html)

Borg, restic, and S3-compatible object storage are **not semantic substitutes** for “copy original file into a durable POSIX directory, then atomically rewrite source in place.” Borg and restic use their own transactional, content-addressed repository formats; restic writes immutable objects and says writes should occur atomically, while Borg appends repository segments and commits them with `COMMIT` tags. S3 has strong object consistency today, but object keys are immutable, there is no native rename, and there is no directory `fsync` concept. Those are good replication targets, but they are the wrong place to put the synchronous per-file safety barrier for docmend. [\[3\]](https://restic.readthedocs.io/en/latest/100_references.html)

The operational recommendation is therefore straightforward: **keep the per-file safety barrier on a fast local filesystem, and replicate asynchronously to slower or weaker media.** Direct-to-medium is reasonable only for a local USB HDD when you accept the slowdown, or for NFS/SMB when you control the server configuration, latency is low, the backing storage is SSD-class, and a short warm-up benchmark proves the medium is not pathologically slower than your local baseline. [\[4\]](https://www.percona.com/blog/fsync-performance-storage-devices/)

## Bottom line

Use **local-fast-backup + asynchronous replication** as the default architecture.

Direct-to-medium is acceptable only under narrow conditions:

- **External USB HDD:** semantically fine, but expect a major slowdown.
- **NFS:** only if you control the export and it is explicitly `sync`, low-latency, and SSD-backed.
- **SMB/CIFS:** only if the Linux client is in strict cache mode and the server actually honors flushes.
- **Borg/restic/S3-compatible object storage:** not as the inline durability barrier for each file; use them only as batched replication targets after the local-safe rewrite completes. [\[5\]](https://man7.org/linux/man-pages/man5/exports.5.html)

A good operational rule is: **if a warm-up run shows the synchronous backup destination pushing the stage above roughly 10× your local-SSD baseline, abort that destination and fall back to local staging.** With your current ~14 ms/file baseline, that means treating sustained stage times above about **140 ms/file** as a red-alert condition. This threshold is a design recommendation derived from your measurement, not a protocol guarantee.

## Backup-medium comparison

The right mental model for docmend’s critical path is:

    Tstage ≈ Tbackup_write+fsync(dst)
           + Ttemp_write(src)
           + Ttemp_fsync(src)
           + Trename(src)
           + Tdir_fsync(parent(src))

`rename()` supplies atomic namespace replacement, but Linux requires an explicit parent-directory `fsync()` if you need that rename to be crash-durable. Therefore, **only the first term moves when only the backup destination changes**; the source-side terms stay on the source filesystem unless the source library itself is remote or slow storage. [\[1\]](https://man7.org/linux/man-pages/man2/fsync.2.html)

| Medium | If this medium is only the backup destination | If the source library also lives on this medium | Can it honor docmend’s current durability contract? | What silently weakens it? | Practical expectation |
| --- | --- | --- | --- | --- | --- |
| **NFS** | **Inference:** add at least one remote stable-storage barrier per file. On Linux NFSv3, `fsync()`/`close()` uses `COMMIT`; with low RTT and SSD-backed servers, this is often still workable, but materially slower than local SSD. [\[6\]](https://nfs.sourceforge.net/) | The temp-file `fsync` and parent-dir durability barrier also become remote. Expect a much larger slowdown, because the rename path now depends on server-side metadata commit too. NFS `RENAME` is atomic to the client only within one server filesystem. [\[7\]](https://www.rfc-editor.org/rfc/rfc7530.html) | **Conditionally yes.** Safe only when the export is `sync`; Linux `exports(5)` says `async` violates the protocol by replying before stable storage, and the NFS FAQ says `async` can affect metadata operations too. [\[8\]](https://man7.org/linux/man-pages/man5/exports.5.html) | `async` exports; unknown NAS implementation; attribute and directory-entry caching can delay visibility to other clients. [\[9\]](https://man7.org/linux/man-pages/man5/exports.5.html) | **Use only if you control the server.** Expect roughly **2×–7× slower** than local SSD on a good LAN SSD-backed server, and potentially **10×+ slower** on HDD-backed or cloud NFS. This range is a synthesis from the NFS commit model and vendor guidance, not a universal benchmark. [\[10\]](https://nfs.sourceforge.net/) |
| **SMB/CIFS** | **Inference:** backup copy cost rises because each durable write depends on SMB flush behavior and network latency. Linux recommends `cache=strict`; on Samba, `strict sync = yes` (default since 4.7) means client flush requests are honored. [\[11\]](https://man7.org/linux//man-pages/man8/mount.cifs.8.html) | If the source tree also sits on SMB, temp-file `fsync` and directory durability move there too. Metadata-heavy workloads are notably sensitive; Azure’s SMB guidance explicitly recommends metadata caching and same-zone placement to reduce latency. [\[12\]](https://learn.microsoft.com/en-us/azure/storage/files/smb-performance) | **Conditionally yes.** Namespace operations are generally filesystem-like, but the durability story depends on client cache mode and whether the server honors flushes. The docs reviewed support flush safety, but they do not give a POSIX-style directory-`fsync` guarantee equivalent to local ext4/XFS wording. [\[13\]](https://man7.org/linux//man-pages/man8/mount.cifs.8.html) | `cache=loose` or otherwise non-strict client caching; Samba `strict sync = no`; opaque appliance behavior; high WAN/VPN latency. [\[14\]](https://man7.org/linux//man-pages/man8/mount.cifs.8.html) | **Use only on low-latency SMB3 with known-good settings.** Expect roughly **3×–9× slower** than local SSD when each file must wait for a durable remote flush, with much worse behavior over high-latency links. This is an inference from protocol/config semantics and cloud file-share guidance. [\[14\]](https://man7.org/linux//man-pages/man8/mount.cifs.8.html) |
| **External USB HDD** | If only the backup destination is USB spinning disk, only the backup copy/`fsync` term moves. Percona’s measurements on rotational media show about **15–58** `fsync`**s/sec**, including **15/sec** on a 5400 RPM USB 3 portable drive and **56/sec** on a 7200 RPM SATA drive. [\[15\]](https://www.percona.com/blog/fsync-performance-storage-devices/) | If the source tree also lives there, the source temp-file `fsync` and parent-directory `fsync` become spinning-disk flushes too. That pushes the full stage toward HDD seek/rotation limits. [\[16\]](https://www.percona.com/blog/fsync-performance-storage-devices/) | **Yes, in principle.** It is still a local filesystem, and Linux local durability semantics remain the same. The risk is performance and whether the device/bridge truthfully honors flushes. `fsync()` is defined to flush through disk cache if present, and ext4 barriers exist specifically to make volatile write caches safe when the stack supports them. [\[17\]](https://man7.org/linux/man-pages/man2/fsync.2.html) | Cheap USB-SATA bridges and consumer caches; mount options that disable barriers; power-loss behavior of the drive enclosure. [\[18\]](https://docs.kernel.org/admin-guide/ext4.html?utm_source=chatgpt.com) | **Semantically acceptable, operationally slow.** For a synchronous path, expect something in the rough neighborhood of **40–140+ ms/file** if two flush-like barriers matter, which lands in the **7–25 files/sec** class. The exact range is an inference from measured per-`fsync` HDD latencies. [\[15\]](https://www.percona.com/blog/fsync-performance-storage-devices/) |
| **Borg repository** | Not comparable to per-file copy+`fsync`. Borg is a transactional repository, not a replacement for a POSIX backup tree. Data is appended to repository segments; uncommitted operations are discarded unless followed by a `COMMIT` tag. [\[19\]](https://borgbackup.readthedocs.io/_/downloads/en/1.0.0/pdf/) | Using the source library itself from inside a Borg repository is not the intended model. | **No, not for docmend’s inline file-by-file contract.** Borg provides its own repository transaction semantics, not “copy this exact source file into a directory and `fsync` it before rewrite.” [\[20\]](https://borgbackup.readthedocs.io/_/downloads/en/1.0.0/pdf/) | Repository free-space reporting can be wrong on CIFS/FUSE; append-only mode changes deletion behavior; performance depends heavily on the files cache and changed-vs-unchanged data mix. [\[21\]](https://borgbackup.readthedocs.io/en/2.0.0b9/faq.html?utm_source=chatgpt.com) | **Good async replication target, bad inline safety barrier.** Borg can process about **1 million unchanged files in ~4 minutes** in a favorable setup, but that says more about batched archive processing than about per-file synchronous durability. [\[22\]](https://borgbackup.readthedocs.io/en/stable/faq.html) |
| **restic repository** | Also not comparable to per-file copy+`fsync`. restic stores immutable repository objects; all files are written once and should be written atomically. It defaults to **2 local backend connections** and **5 remote backend connections**, with a default **16 MiB pack size**. [\[23\]](https://restic.readthedocs.io/en/latest/100_references.html) | A source library “living on restic” is not a normal operating mode. | **No, not for the same contract.** It gives repository-level atomicity for repository objects, not local-directory backup semantics. [\[24\]](https://restic.readthedocs.io/en/latest/100_references.html) | High-latency backends, poor pack-size tuning, temp-space exhaustion from pack creation. restic warns that too many backend connections can degrade performance. [\[25\]](https://restic.readthedocs.io/en/latest/047_tuning_parameters.html) | **Good batched replication target, bad inline safety barrier.** Because packs amortize object creation, restic is much better as “backup after the run” than “wait on a repository update before every file rewrite.” [\[26\]](https://restic.readthedocs.io/en/latest/047_tuning_parameters.html) |
| **S3-compatible object storage** | If used directly as the synchronous backup destination, the per-file backup becomes a PUT workload. Amazon documents at least **3,500 PUT/COPY/POST/DELETE requests/sec per prefix**, but S3 access is still in the **tens-of-milliseconds** latency range per request. [\[27\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html?utm_source=chatgpt.com) | If the source library itself is on object storage, you no longer have the local POSIX rewrite model at all. | **No.** S3 now has strong read-after-write consistency for PUT and DELETE, but object keys are immutable, there is no native rename, and “rename” is implemented as copy+delete. There is no directory `fsync` concept. [\[28\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html?utm_source=chatgpt.com) | Assuming “S3-compatible” means “same semantics.” Consistency and multipart behavior vary by vendor; MinIO, for example, says operations are atomic and strictly consistent, but that still does not add POSIX rename/directory durability semantics. [\[29\]](https://docs.min.io/aistor/operations/scaling/expansion/?utm_source=chatgpt.com) | **Use only as an async replication target.** Serial per-file PUTs end up in the **tens-of-files/sec** regime by latency alone; parallelized bulk replication can scale far higher, but it does not satisfy docmend’s inline rename-and-directory-durability contract. [\[30\]](https://docs.aws.amazon.com/pdfs/fsx/latest/OpenZFSGuide/OpenZFSGuide.pdf) |

### What changes if only the backup destination moves

**Observation:** your measured local parent-directory `fsync` is attached to the source filesystem, not the backup destination. Linux `fsync(2)` explicitly distinguishes file data/metadata from directory-entry persistence, and `rename(2)` is a source-filesystem namespace operation. [\[1\]](https://man7.org/linux/man-pages/man2/fsync.2.html)

**Inference:** if the library remains on local SSD, moving only the backup directory to NFS, SMB, or USB HDD should increase wall time materially less than moving the source library itself. In your case that likely means the fixed local rename/directory portion remains close to the current baseline, while only the backup copy/flush portion stretches.

**Recommendation:** benchmark two scenarios separately before the 100k run: “source local, backup remote” and “source remote, backup local/remote.” They are different systems and should not be conflated.

## Preflight formulas

The formulas below are intended for a real run planner. I use:

- `N` = number of files that will be rewritten.
- `D` = number of directories that must exist in the backup tree.
- `B` = sum of original file sizes for those `N` files.
- `P` = maximum parallel file operations docmend allows at once.
- `Smax` = maximum size of any one source file in the rewrite set.
- `Fsrc` = free space on the source filesystem.
- `Fdst` = free space on the backup destination.
- `Iavail` = free inodes, if the destination filesystem has an inode limit.

### POSIX filesystem backup trees

For a plain filesystem destination — local SSD, USB HDD, NFS export, or SMB share — the destination store behaves like a normal mirrored backup tree:

    Bytes_needed(dst) ≈ Σ round_up(size_i, alloc_unit) + D × dir_overhead + reserve

In practice, if you do not know the exact allocation unit, a conservative operator formula is:

    Bytes_needed(dst) ≈ B × (1 + small_file_margin) + reserve

Use `small_file_margin ≈ 0.05` for SSD-backed local filesystems and `≈ 0.10–0.15` for spinning disks or remote NAS shares with lots of small files. That margin is an operational recommendation, not a protocol constant.

For inode-limited filesystems, use:

    Inodes_needed(dst) ≈ N + D + slack

with `slack ≈ max(0.05 × (N + D), 1024)`.

On ext-family filesystems, inode capacity is set at filesystem creation time by the bytes-per-inode ratio; `mke2fs` documents that it creates one inode per configured bytes-per-inode. On XFS, metadata and inode placement are dynamically allocated, so you usually treat inode exhaustion more like a quota/metadata-capacity problem than a fixed inode-table problem. [\[31\]](https://man7.org/linux/man-pages/man8/mke2fs.8.html?utm_source=chatgpt.com)

If the **backup destination and source are the same filesystem**, preflight must also cover the temp rewrite file:

    Bytes_needed(same_fs) ≈ Bytes_needed(dst) + P × max(Smax, estimated_output_max) + source_reserve

That extra term exists because atomic replace requires a second file to exist until `os.replace()` completes. This is an implementation inference from the rewrite algorithm.

### NFS and SMB-specific preflight notes

For NFS and SMB, the byte formula above still applies, but durability depends on server policy as much as on free space.

For **NFS**, preflight must verify that the export is `sync`; `exports(5)` states that `async` replies may be sent before stable-storage commit, and the Linux NFS FAQ says `async` can affect metadata operations as well. For **SMB**, preflight should capture the client cache mode and the server’s flush policy because Linux recommends `cache=strict`, and Samba’s `strict sync` governs whether client flush requests are honored. [\[32\]](https://man7.org/linux/man-pages/man5/exports.5.html)

Operationally, that means your preflight for NFS/SMB is not just `df -h` and `df -i`. It is also “what exact mount options and server config am I standing on?”

### Borg repository preflight

Borg is not one-backup-file-per-source-file. The repository is an append-only transactional store of chunks and metadata objects. Uncommitted operations are discarded unless followed by a `COMMIT` tag. Borg also recommends reserving explicit free space with `additional_free_space`, especially on filesystems such as XFS that do not expose root-reserved blocks the way ext filesystems do. [\[33\]](https://borgbackup.readthedocs.io/_/downloads/en/1.0.0/pdf/)

A practical growth formula is:

    Repo_growth(Borg) ≈ U / C + Mmeta + Mindex + additional_free_space

where:

- `U` = unique changed plaintext bytes after dedup scope is considered.
- `C` = effective compression ratio.
- `Mmeta` = archive/item/chunk-metadata growth.
- `Mindex` = repository index growth.

For filesystem-backed Borg repositories, inode pressure is tied to **segment and index files**, not source files:

    Repo_inode_need(Borg) ≈ ceil(Repo_growth / max_segment_size) + index_files + hints_files + manifest/lock slack

Use the repository’s configured `max_segment_size`; do not assume a default without inspecting the repo. If free-space reporting is coming through CIFS or FUSE, Borg’s own FAQ warns that reported free space can be wrong. [\[34\]](https://borgbackup.readthedocs.io/en/stable/internals/data-structures.html?utm_source=chatgpt.com)

### restic repository preflight

restic stores immutable objects and says repository files are write-once and should be written atomically. For modified repositories, the key temporary-space formula is explicit in the docs:

    Temp_space(restic) ≥ pack_size × (connections + 1)

The current docs state a default pack size of **16 MiB**, default **5 backend connections** for most backends, and **2** for the local backend. That means the default temp-space floor is:

    16 MiB × (5 + 1) = 96 MiB   for most remote backends
    16 MiB × (2 + 1) = 48 MiB   for the local backend

and grows linearly if you tune either connections or pack size upward. [\[25\]](https://restic.readthedocs.io/en/latest/047_tuning_parameters.html)

A practical repository-growth formula is:

    Repo_growth(restic) ≈ U / C + Mpacks + Mindex + Msnapshots

For a filesystem-backed restic repo, inode demand is roughly pack-file count plus index/snapshot/lock files:

    Repo_inode_need(restic) ≈ ceil(Repo_growth / pack_size) + O(indexes + snapshots + locks)

Again, that is **not** one inode per source file. [\[23\]](https://restic.readthedocs.io/en/latest/100_references.html)

### S3-compatible object storage preflight

For **raw object-per-backup-file** designs:

    Bytes_needed(S3 raw) ≈ B + versioning_multiplier + reserve_budget

There is **no inode concept**. If bucket versioning or object lock is enabled, storage can grow above simple overwrite assumptions because multiple object versions may be retained. Amazon documents S3 versioning as preserving multiple variants of an object. [\[35\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html?utm_source=chatgpt.com)

For **restic-on-S3**, use the restic formula above, not the raw-object formula.

For **docmend specifically**, S3 should be treated as a replication destination, not the store that must durably acknowledge each source-file backup before the local rewrite continues. The reason is semantic, not capacity-related: S3 has no native rename and no directory durability primitive. [\[36\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html?utm_source=chatgpt.com)

## Instrumentation and heartbeat design

The design goal is to detect a backup medium that is **pathologically slower than your local-SSD baseline** early enough to stop or reroute before wasting most of the run.

### What to measure for every file

Record these timestamps separately for every file:

- backup open/create
- backup bytes copied
- backup file `fsync`
- temp output bytes written
- temp file `fsync`
- `os.replace`
- parent-directory `fsync`
- total stage time
- destination free bytes
- destination free inodes if available
- retry/error counters

This separation matters because a slow backup medium and a slow source filesystem produce different signatures. A slow backup destination inflates the backup-copy and backup-`fsync` slices. A slow source filesystem inflates temp-file `fsync` and parent-directory `fsync`.

### Warm-up policy

Run a small warm-up on the exact intended configuration before committing to the full 100k job.

A good warm-up size is **200–1,000 files** spread across realistic file sizes and directories. From that warm-up, compute:

- mean and p95 of total stage time
- mean and p95 of backup-`fsync`
- mean and p95 of parent-directory `fsync`
- effective files/sec and MiB/sec

Then compare those figures against your local baseline.

Because your current baseline is about **14 ms/file**, treat these as the first hard thresholds:

- **warning:** rolling mean stage time exceeds **5× baseline** for two consecutive windows
- **critical:** rolling mean stage time exceeds **10× baseline** — about **140 ms/file** — for one full window
- **critical:** p95 parent-directory `fsync` exceeds **10×** its current local value
- **critical:** destination free space or inode headroom drops below the preflight reserve

Those thresholds are design recommendations derived from your measurement, not vendor guarantees.

### Rolling windows and heartbeat

Use two rolling views at once:

- a **count window** of the last **256 files**
- a **time window** of the last **30 seconds**

Emit a heartbeat every **30 seconds** or every **1,000 files**, whichever comes first. Include:

- files processed and files/sec
- stage mean, p95, and max
- backup-`fsync` mean/p95
- source parent-dir `fsync` mean/p95
- bytes copied and MiB/sec
- destination free bytes and inode headroom
- recent retries/timeouts
- detected medium identity and mount/backend parameters

For NFS and SMB, log the actual mount identity once at startup and in every heartbeat summary: protocol version, mount options, and relevant cache settings. For NFS, that means at least version and whether the workload is on a known `sync` export. For SMB, include whether the client is effectively in strict cache mode and which server family is in use. This ties the run artifacts back to the semantics you actually relied on. [\[37\]](https://man7.org/linux/man-pages/man5/nfs.5.html)

### Sentinel microprobe

Add a low-rate sentinel probe to directly test “tiny durable file lifecycle” on the backup medium without waiting for a pathological file to reveal it.

For POSIX-like destinations, every **5,000–10,000 files**:

- create a hidden sentinel file in the backup tree
- write a tiny payload
- `fsync` the file
- rename it within the same directory
- `fsync` the directory
- delete it
- `fsync` the directory again if you want deletion durability too

This probe directly measures the exact durability pattern docmend cares about. On NFS/SMB it also reveals abrupt latency inflation caused by server state or throttling. The probe should write to a dedicated hidden control directory so it does not pollute the mirrored backup tree. The correctness of the pattern itself follows from the same Linux `fsync` and `rename` rules already discussed. [\[1\]](https://man7.org/linux/man-pages/man2/fsync.2.html)

For Borg and restic, use a backend-native probe instead: time a tiny repository update or pack/object upload into a dedicated control namespace. For raw S3 replication, probe with a tiny PUT and DELETE in a control prefix.

### Abort and fallback policy

If the medium is in the synchronous path and any **critical** condition holds for more than one heartbeat interval, stop using that medium for inline safety. The safest fallback is:

1.  keep rewriting on the local-safe path only
2.  spool backups locally
3.  continue replication asynchronously after the rewrite stage

This policy is especially important for NFS/SMB where a misconfigured server can look fine for a while and then collapse under metadata-heavy sync traffic, and for cloud/object backends where throttling or transient network behavior can create long latency tails. [\[38\]](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-files)

## Version and environment sensitivity

Several of the conclusions above are version- and stack-sensitive.

On **local Linux filesystems**, ext4’s `auto_da_alloc` exists specifically to reduce the old replace-via-rename zero-length-file failure mode, but it is not a replacement for the explicit `fsync(file)` and `fsync(parent dir)` sequence. ext4 barrier settings also matter because barriers are what make volatile write caches safe when the I/O stack supports them. [\[39\]](https://www.kernel.org/doc/html/v5.2/admin-guide/ext4.html?utm_source=chatgpt.com)

On **NFS**, safety depends on both protocol/version and server export policy. Linux NFS documentation notes that `nconnect` is available broadly on modern kernels, and AWS FSx for OpenZFS documents `nconnect` support on kernel 5.3+ and RHEL 8.3 backports. The same FSx documentation also notes that NFSv3 may still have better latency/throughput/IOPS for performance-sensitive workloads than newer NFS versions in some cases. None of that helps if the server export is `async`, because `async` weakens the stable-storage contract. [\[40\]](https://docs.aws.amazon.com/pdfs/fsx/latest/OpenZFSGuide/OpenZFSGuide.pdf)

On **SMB/CIFS**, Linux clients prior to kernel 3.7 defaulted to loose caching; the modern default is strict caching. On Samba, the default for `strict sync` changed from `no` to `yes` in 4.7, specifically to match SMB2/3 client expectations better. That means old kernels and old Samba deployments should be treated with extra suspicion. [\[41\]](https://man7.org/linux//man-pages/man8/mount.cifs.8.html)

For **restic**, the current docs I found are for the 0.19.1-dev stream and document the present defaults as **16 MiB packs**, **5 remote connections**, and **2 local connections**. Operators should verify these against the exact restic version they will run. [\[25\]](https://restic.readthedocs.io/en/latest/047_tuning_parameters.html)

For **Borg**, repository behavior is stable at the conceptual level — append-only segments plus commit markers — but details such as segment sizing and append-only administration differ across 1.x and 2.x lines. The safe operational stance is to inspect the repository’s actual config instead of assuming defaults. [\[42\]](https://borgbackup.readthedocs.io/en/stable/internals/data-structures.html?utm_source=chatgpt.com)

For **S3-compatible object storage**, do not assume every compatible product matches AWS S3 on consistency details. AWS documents strong object consistency and no native rename; MinIO documents atomic and strictly consistent operations. Those are strong object-store guarantees, but they still do not recreate POSIX directory durability semantics. [\[43\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html?utm_source=chatgpt.com)

## Sources

- Linux `fsync(2)` and `rename(2)` man pages, plus `sync(2)`, from man7.org, for local durability and rename semantics. [\[44\]](https://man7.org/linux/man-pages/man2/fsync.2.html)
- Linux NFS client and server documentation: `nfs(5)`, `exports(5)`, and the Linux NFS FAQ, for COMMIT behavior, cache behavior, and `sync` vs `async`. [\[45\]](https://man7.org/linux/man-pages/man5/nfs.5.html)
- NFSv4 RFC 7530 for `RENAME` atomicity to the client and stable-storage concepts. [\[46\]](https://www.rfc-editor.org/rfc/rfc7530.html)
- Linux CIFS and Samba documentation: `mount.cifs(8)`, Samba `smb.conf`, and Samba release notes for `cache=strict`, `strict sync`, and `sync always`. [\[47\]](https://man7.org/linux//man-pages/man8/mount.cifs.8.html)
- Percona’s `fsync` benchmark article for rotational-media `fsync` rates, including a USB 3 portable HDD datapoint. [\[15\]](https://www.percona.com/blog/fsync-performance-storage-devices/)
- Azure Files docs for SMB/NFS metadata limits, metadata caching, and latency-sensitive deployment advice. [\[48\]](https://learn.microsoft.com/en-us/azure/storage/files/storage-files-scale-targets)
- AWS S3 docs for strong consistency, copy/delete rename behavior, and request-rate guidance. [\[49\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html?utm_source=chatgpt.com)
- AWS FSx for OpenZFS docs for S3 latency guidance and NFS `nconnect` / NFSv3 performance notes. [\[50\]](https://docs.aws.amazon.com/pdfs/fsx/latest/OpenZFSGuide/OpenZFSGuide.pdf)
- restic repository-format and tuning docs for atomic write-once repository objects, connection defaults, pack size, and temp-space formulas. [\[23\]](https://restic.readthedocs.io/en/latest/100_references.html)
- Borg internals, FAQ, quick-start, and changelog docs for transactional commit semantics, append-only behavior, files-cache performance, and free-space reserve guidance. [\[51\]](https://borgbackup.readthedocs.io/_/downloads/en/1.0.0/pdf/)
- Linux ext4 and XFS docs, plus `mke2fs(8)`, for barrier semantics, `auto_da_alloc`, and inode/metadata allocation behavior. [\[52\]](https://www.kernel.org/doc/html/v5.2/admin-guide/ext4.html?utm_source=chatgpt.com)

---

[\[1\]](https://man7.org/linux/man-pages/man2/fsync.2.html) [\[17\]](https://man7.org/linux/man-pages/man2/fsync.2.html) [\[44\]](https://man7.org/linux/man-pages/man2/fsync.2.html) fsync(2) - Linux manual page

<https://man7.org/linux/man-pages/man2/fsync.2.html>

[\[2\]](https://man7.org/linux/man-pages/man5/exports.5.html) [\[5\]](https://man7.org/linux/man-pages/man5/exports.5.html) [\[8\]](https://man7.org/linux/man-pages/man5/exports.5.html) [\[9\]](https://man7.org/linux/man-pages/man5/exports.5.html) [\[32\]](https://man7.org/linux/man-pages/man5/exports.5.html) exports(5) - Linux manual page

<https://man7.org/linux/man-pages/man5/exports.5.html>

[\[3\]](https://restic.readthedocs.io/en/latest/100_references.html) [\[23\]](https://restic.readthedocs.io/en/latest/100_references.html) [\[24\]](https://restic.readthedocs.io/en/latest/100_references.html) References — restic 0.19.1-dev documentation

<https://restic.readthedocs.io/en/latest/100_references.html>

[\[4\]](https://www.percona.com/blog/fsync-performance-storage-devices/) [\[15\]](https://www.percona.com/blog/fsync-performance-storage-devices/) [\[16\]](https://www.percona.com/blog/fsync-performance-storage-devices/) Fsync Performance on Storage Devices - Percona

<https://www.percona.com/blog/fsync-performance-storage-devices/>

[\[6\]](https://nfs.sourceforge.net/) [\[10\]](https://nfs.sourceforge.net/) Linux NFS faq

<https://nfs.sourceforge.net/>

[\[7\]](https://www.rfc-editor.org/rfc/rfc7530.html) [\[46\]](https://www.rfc-editor.org/rfc/rfc7530.html) <www.rfc-editor.org>

<https://www.rfc-editor.org/rfc/rfc7530.html>

[\[11\]](https://man7.org/linux//man-pages/man8/mount.cifs.8.html) [\[13\]](https://man7.org/linux//man-pages/man8/mount.cifs.8.html) [\[14\]](https://man7.org/linux//man-pages/man8/mount.cifs.8.html) [\[41\]](https://man7.org/linux//man-pages/man8/mount.cifs.8.html) [\[47\]](https://man7.org/linux//man-pages/man8/mount.cifs.8.html) mount.cifs(8) - Linux manual page

<https://man7.org/linux//man-pages/man8/mount.cifs.8.html>

[\[12\]](https://learn.microsoft.com/en-us/azure/storage/files/smb-performance) Improve SMB Azure File Share Performance \| Microsoft Learn

<https://learn.microsoft.com/en-us/azure/storage/files/smb-performance>

[\[18\]](https://docs.kernel.org/admin-guide/ext4.html?utm_source=chatgpt.com) ext4 General Information

<https://docs.kernel.org/admin-guide/ext4.html?utm_source=chatgpt.com>

[\[19\]](https://borgbackup.readthedocs.io/_/downloads/en/1.0.0/pdf/) [\[20\]](https://borgbackup.readthedocs.io/_/downloads/en/1.0.0/pdf/) [\[33\]](https://borgbackup.readthedocs.io/_/downloads/en/1.0.0/pdf/) [\[51\]](https://borgbackup.readthedocs.io/_/downloads/en/1.0.0/pdf/) borgbackup.readthedocs.io

<https://borgbackup.readthedocs.io/_/downloads/en/1.0.0/pdf/>

[\[21\]](https://borgbackup.readthedocs.io/en/2.0.0b9/faq.html?utm_source=chatgpt.com) Frequently asked questions — Borg - Deduplicating Archiver ...

<https://borgbackup.readthedocs.io/en/2.0.0b9/faq.html?utm_source=chatgpt.com>

[\[22\]](https://borgbackup.readthedocs.io/en/stable/faq.html) Frequently asked questions — Borg - Deduplicating Archiver 1.4.4 documentation

<https://borgbackup.readthedocs.io/en/stable/faq.html>

[\[25\]](https://restic.readthedocs.io/en/latest/047_tuning_parameters.html) [\[26\]](https://restic.readthedocs.io/en/latest/047_tuning_parameters.html) Tuning parameters — restic 0.19.1-dev documentation

<https://restic.readthedocs.io/en/latest/047_tuning_parameters.html>

[\[27\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html?utm_source=chatgpt.com) Best practices design patterns: optimizing Amazon S3 ...

<https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html?utm_source=chatgpt.com>

[\[28\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html?utm_source=chatgpt.com) [\[36\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html?utm_source=chatgpt.com) [\[43\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html?utm_source=chatgpt.com) [\[49\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html?utm_source=chatgpt.com) What is Amazon S3? - Amazon Simple Storage Service

<https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html?utm_source=chatgpt.com>

[\[29\]](https://docs.min.io/aistor/operations/scaling/expansion/?utm_source=chatgpt.com) Expand Available Storage \| MinIO AIStor Documentation

<https://docs.min.io/aistor/operations/scaling/expansion/?utm_source=chatgpt.com>

[\[30\]](https://docs.aws.amazon.com/pdfs/fsx/latest/OpenZFSGuide/OpenZFSGuide.pdf) [\[40\]](https://docs.aws.amazon.com/pdfs/fsx/latest/OpenZFSGuide/OpenZFSGuide.pdf) [\[50\]](https://docs.aws.amazon.com/pdfs/fsx/latest/OpenZFSGuide/OpenZFSGuide.pdf) FSx for OpenZFS - OpenZFS User Guide

<https://docs.aws.amazon.com/pdfs/fsx/latest/OpenZFSGuide/OpenZFSGuide.pdf>

[\[31\]](https://man7.org/linux/man-pages/man8/mke2fs.8.html?utm_source=chatgpt.com) mke2fs(8) - Linux manual page

<https://man7.org/linux/man-pages/man8/mke2fs.8.html?utm_source=chatgpt.com>

[\[34\]](https://borgbackup.readthedocs.io/en/stable/internals/data-structures.html?utm_source=chatgpt.com) [\[42\]](https://borgbackup.readthedocs.io/en/stable/internals/data-structures.html?utm_source=chatgpt.com) Data structures and file formats - Borg Documentation

<https://borgbackup.readthedocs.io/en/stable/internals/data-structures.html?utm_source=chatgpt.com>

[\[35\]](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html?utm_source=chatgpt.com) Retaining multiple versions of objects with S3 Versioning

<https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html?utm_source=chatgpt.com>

[\[37\]](https://man7.org/linux/man-pages/man5/nfs.5.html) [\[45\]](https://man7.org/linux/man-pages/man5/nfs.5.html) nfs(5) - Linux manual page

<https://man7.org/linux/man-pages/man5/nfs.5.html>

[\[38\]](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-files) Architecture Best Practices for Azure Files - Microsoft Azure Well-Architected Framework \| Microsoft Learn

<https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-files>

[\[39\]](https://www.kernel.org/doc/html/v5.2/admin-guide/ext4.html?utm_source=chatgpt.com) [\[52\]](https://www.kernel.org/doc/html/v5.2/admin-guide/ext4.html?utm_source=chatgpt.com) ext4 General Information — The Linux Kernel documentation

<https://www.kernel.org/doc/html/v5.2/admin-guide/ext4.html?utm_source=chatgpt.com>

[\[48\]](https://learn.microsoft.com/en-us/azure/storage/files/storage-files-scale-targets) Azure Files Scale and Performance Targets \| Microsoft Learn

<https://learn.microsoft.com/en-us/azure/storage/files/storage-files-scale-targets>
