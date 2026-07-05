# Path-Containment Algorithm and TOCTOU Symlink-Race Mitigation for the docmend Writer

**Date:** 2026-07-05

**Related:** GAP-40 · OQ-004 (artifact schemas / symlink policy) · OQ-005 (apply safety-gate checklist) · OQ-012 (in-place mutation, resolved-in-agent-notes) · `docs/specs/docmend.md` §8.5 (Design Constraints), §13.5 (Threats and Mitigations), §10.3 EC-008 (symlinks in source tree), NFR-002/D-004 (atomic writer)

**Gap it fills:** The spec already _names_ path containment and symlink handling as required (§8.5: "Output paths must stay inside the intended output root"; §13.5: "Path escape... Output-path containment check in the safety gate"; EC-008: "symlinks... not followed for mutation") but never specifies the algorithm, at which pipeline stage(s) it runs, or how the check survives the gap between validating a path in `plan` and mutating it in `apply` — the exact TOCTOU window every symlink-race CVE in this space exploits. This report closes that gap with a concrete, code-level algorithm, a race analysis grounded in current Python stdlib semantics and real-world CVEs, and an explicit adversarial-rigor recommendation scoped to docmend's actual threat model (solo user, offline, no privilege boundary).

---

## 1. The question in docmend's own terms

Because OQ-012's agent recommendation is in-place mutation (source root doubles as output root, `target_path` differs from `source_path` only by extension), the general "arbitrary output-root escape" problem collapses to three concrete containment boundaries docmend must actually enforce:

1. **Discovery containment** — `scan` must not let a symlink inside the tree cause the walker to record (or, later, mutate) a file outside `source_root`.
2. **Target containment** — the `target_path` a `plan` action computes (today: same directory, renamed suffix; later, if OQ-002 naming policy changes) must resolve inside `source_root`.
3. **Backup containment** — `backup_dir` must not overlap `source_root` in either direction (already implied by OQ-005's checklist item, "Backup destination... is outside the mutation target path").

All three reduce to one primitive — "is resolved-path A inside resolved-root B" — applied at different times, plus a TOCTOU concern only for (2), because only the writer (§8.4 D-004) crosses a check→act boundary against a filesystem the tool does not exclusively control.

## 2. Containment algorithm: lexical checks are necessary but never sufficient

Python offers two families of "is this under that" checks, and they are not interchangeable:

- **Lexical (`PurePath`) checks** — `PurePath.is_relative_to()`, string-prefix comparison, `os.path.commonpath()`. These operate on path _text_ only. The official docs are explicit that `is_relative_to()` "does not check or access the underlying file structure. This can impact the `walk_up` option as it assumes that no symlinks are present in the path; call `resolve()` first if necessary to resolve symlinks" [official, docs.python.org/3/library/pathlib.html]. A naive `candidate.is_relative_to(source_root)` on un-resolved paths is trivially defeated by a symlink anywhere in the ancestry, or by `..` segments the config/include-glob layer let through.
- **Canonical (`os.path.realpath` / `Path.resolve()`) checks** — resolve every symlink and `..`/`.` component against the live filesystem, then compare. `os.path.realpath(path, strict=False)` is the stdlib primitive; `strict` was added in Python 3.10 to control whether a nonexistent path raises `OSError` instead of resolving as far as it can [official, docs.python.org/3/library/os.path.html]. `pathlib.Path.resolve(strict=False)` is the object-oriented equivalent and is what `is_relative_to()`'s own docs point back to.

**Recommended algorithm — layered, not either/or:**

```python
from pathlib import Path

def is_contained(candidate: Path, root: Path) -> bool:
    """True iff candidate resolves to a path inside root, symlinks included."""
    resolved_root = root.resolve(strict=True)          # root must exist; resolve once per run
    resolved_candidate = candidate.resolve(strict=False)  # target may not exist yet (new .md file)
    return resolved_candidate.is_relative_to(resolved_root)
```

1. **Plan-time, cheap lexical pre-filter** (fast-fail on obviously bad config/include-patterns before touching disk): reject any computed relative segment that is absolute or contains `..`/empty components, using `PurePath.parts` inspection. This is a UX/early-diagnostics layer, not a security boundary — it exists so a bad `pathspec` pattern or config typo produces a clear planning-stage error instead of a confusing filesystem error later.
2. **Plan-time canonical check** (the real check): resolve both `source_root` and the per-file `target_path` with `resolve()`/`realpath()` and compare with `is_relative_to()` as above. Record the result in the plan artifact (DR-002) as part of the per-file risk/conflict decision (§8.1 planning layer: "collisions... before any file is touched").
3. **Apply-time re-check, immediately before the write** (closes most of the TOCTOU window — see §3): re-run the identical canonical check on the _live_ filesystem state right before the writer's atomic-replace sequence, not just once at plan time. This is the same "re-validate at time-of-use, not time-of-check" principle FR-003 already applies to source hashes; path containment needs the identical treatment for the same reason (stale plan, changed filesystem).

`os.path.commonpath()` is a viable alternative comparator to `is_relative_to()` but has the same "lexical, needs pre-resolved input" caveat and no meaningful advantage for docmend; `is_relative_to()` is preferred because it is a first-class `pathlib` method (docmend's implementation reads as `pathlib`-native throughout) and its raise-free `bool` return is easier to test than `commonpath()`'s string-manipulation exception cases.

## 3. TOCTOU race analysis: where the window is, and how narrow it already is by design

**The general race pattern** (per CWE-367 and its canonical filesystem instance, CWE-59 "Improper Link Resolution Before File Access"): a program checks a path's identity (`stat`, `realpath`, `is_relative_to`), then later _acts_ on the same path by name. Between check and act, an attacker with concurrent filesystem write access swaps a component for a symlink; the kernel resolves the new symlink at act-time, not check-time, so the containment check that passed is now stale [CWE-367, cwe.mitre.org/data/definitions/367.html].

**Real-world instances confirm the pattern is always "check-then-open-by-name":**

- `filelock` GHSA-w853-jp5j-5j7f (CVSS 7.0): Unix lock acquisition called `os.open()` without `O_NOFOLLOW`; a symlink swapped into the lock-file path between existence-check and open caused the kernel to follow it and truncate an attacker-chosen target file. Fixed in 3.20.1 by adding `O_NOFOLLOW` to the `os.open()` call [official/advisory, GitHub Security Advisories].
- `uutils coreutils cp` (CVE-2026-35359, CWE-367): `cp` checked whether the source was a symlink, then opened it without `O_NOFOLLOW`; an attacker who swapped a regular file for a symlink between the check and the open caused a privileged `cp` process to copy an arbitrary sensitive file to an attacker-controlled destination [community, radar.offseq.com CVE record].
- OWASP's canonical TOCTOU writeup for filesystem races: `if os.path.exists(path): os.remove(path)` — the fix is not a better check, it is _removing the check entirely_ and handling the resulting exception, because "no check means no TOCTOU window" [official/community, owasp.org/www-community/pages/vulnerabilities/race_conditions].
- Every published TOCTOU CWE-367 CVE surfaced in this research (Windows HTTP.sys CVE-2026-21240, Windows Graphics CVE-2025-59261, Defender-for-Endpoint-on-Linux CVE-2025-59497, the `cp` case above) shares one precondition: **a local, lower-privileged attacker races a separate, higher-privileged process** to make it act on a resource the attacker controls. The exploit's value comes entirely from crossing a privilege boundary the attacker could not otherwise cross.

**The stdlib-correct mitigation, and its availability:**

- `os.O_NOFOLLOW`: causes `os.open()` to fail with `ELOOP`/`OSError` instead of following a symlink at the final path component. Available on Unix.
- `dir_fd` parameters: `os.open()`, `os.stat()`, `os.replace()`, `os.rename()`, `os.unlink()` and others accept `dir_fd` (`os.replace(src, dst, *, src_dir_fd=None, dst_dir_fd=None)`, added in Python 3.3) to resolve the final path component relative to an already-open directory file descriptor rather than re-walking the full path string by name. Opening the directory once and pinning it by descriptor means the kernel resolves the _directory_ portion of the path exactly once; only the leaf component is subject to a further race, and `O_NOFOLLOW` on that leaf closes it. Check support per-platform with `os.supports_dir_fd`, since — per the stdlib docs — **"Currently `dir_fd` parameters only work on Unix platforms; none of them work on Windows"** [official, docs.python.org/3/library/os.html]. This matches docmend's own A-001 (local POSIX filesystem assumption), so no portability tax applies.
- `os.walk(..., followlinks=False)` (the default) already prevents directory-level symlink descent during discovery — this is the primitive EC-008's "not followed for mutation" behavior should build on for the discovery layer, and it requires no additional code.
- The **general-purpose, fully adversarial** defense — walk every path component one at a time via `openat(dirfd, component, O_NOFOLLOW)`, discarding and re-opening the descriptor at each level (the pattern behind Chromium's `libbrillo/safe_fd.cc` and Rust's `cap-std`) — exists precisely because on a _fully hostile_, multi-tenant filesystem an attacker can swap _any_ intermediate directory component, not just the leaf, between check and use [community, Snyk "Why Secure Filesystem Operations Are Harder Than You Think"]. Notably, even the Python core team judged the _narrower_ version of this problem (tar-archive extraction path traversal, CVE-2007-4559) hard enough that it took roughly 15 years and a dedicated PEP (PEP 706, `tarfile.extractall(filter=...)`) to land a _partial_, non-airtight fix, and the maintainers explicitly declined to attempt full TOCTOU-proof extraction as out of proportion to the threat most callers face [official, discuss.python.org/t/policies-for-tarfile-extractall-a-k-a-fixing-cve-2007-4559].

**Where this leaves docmend's actual TOCTOU window:** because NFR-002/D-004 already mandate "temp file in the same directory, fsync, `os.replace`," the parent directory for every writer operation is fixed and known at write time — the hard, multi-level "attacker moved an ancestor directory" case that motivates full `openat`-per-component walking does not arise for the _write_ step. The remaining window is narrow: between the apply-time re-check (§2 step 3) and the `os.replace()` call, the _original file itself_ could theoretically be swapped for a symlink. Pinning the parent directory by `dir_fd` and opening/statting the leaf with `O_NOFOLLOW` collapses that window to the single syscall pair immediately around the write, which is the same order of magnitude of residual risk stdlib `tempfile` and `shutil` already accept for their own atomic-replace patterns.

## 4. Concrete algorithm for docmend's writer layer

```python
import os
import stat
from pathlib import Path

def atomic_replace_contained(
    parent_dir: Path,
    original_name: str,
    tmp_name: str,
    data: bytes,
) -> None:
    """
    Writer-layer atomic replace with symlink-race hardening.
    parent_dir must already be canonical-checked against source_root (§2)
    at plan time and immediately before this call.
    """
    use_dir_fd = os.stat in os.supports_dir_fd and os.replace in os.supports_dir_fd
    dir_fd = os.open(parent_dir, os.O_RDONLY | os.O_DIRECTORY) if use_dir_fd else None
    try:
        # Refuse if the original became a symlink between plan and apply (EC-008).
        st = os.stat(
            original_name,
            dir_fd=dir_fd,
            follow_symlinks=False,
        ) if dir_fd is not None else os.lstat(parent_dir / original_name)
        if stat.S_ISLNK(st.st_mode):
            raise RiskySkip("target became a symlink between plan and apply")

        open_kwargs = {"dir_fd": dir_fd} if dir_fd is not None else {}
        fd = os.open(
            tmp_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o644,
            **open_kwargs,
        )
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)

        if dir_fd is not None:
            os.replace(tmp_name, original_name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        else:
            os.replace(parent_dir / tmp_name, parent_dir / original_name)
    finally:
        if dir_fd is not None:
            os.close(dir_fd)
```

Notes for the implementer:

- `os.supports_dir_fd` must be checked per function, not assumed globally true — some platforms support `dir_fd` for `os.open()` but not `os.stat()` or vice versa [official, docs.python.org/3/library/os.html].
- `O_EXCL` on the temp-file create means "never silently reuse an existing name" — combined with a per-run unique temp suffix (e.g. containing the source hash or a UUID), this removes an entire class of concurrent-run collisions, which is a more likely real failure mode for docmend than adversarial symlink injection (see §5).
- On platforms without `dir_fd` support, the function degrades to plain path-based `os.replace()` — the same operation NFR-002/D-004 already specify — with a slightly wider (but still sub-millisecond, single-syscall) race window. This degrade path should be logged at debug level so a real-library run on an unusual filesystem doesn't silently run in the weaker mode without a trace.
- The discovery layer should record `entry.is_symlink()` per `os.DirEntry`/`os.scandir()` and must not descend into symlinked directories (`os.walk(..., followlinks=False)`, the stdlib default) — this is the concrete implementation of EC-008 and should populate the "symlink records" OQ-004 already calls for in the inventory schema.

## 5. How much adversarial rigor is warranted here

The load-bearing fact from §3 is that **every published TOCTOU/CWE-367 exploit in this research required a local attacker with concurrent filesystem write access, racing a separate process running at _higher privilege_ than the attacker** (a setuid binary, a privileged agent, a service account). docmend's threat model has neither element:

- **No privilege boundary.** docmend runs as the invoking user against files that user already owns and can already read, write, or delete directly (§13.1/§13.2: no auth, no service surface, "runs as the invoking user; requires no elevation"). There is no higher-privilege process for an attacker to trick.
- **No adversarial concurrent writer.** §14 explicitly frames this as "single user... occasional incremental runs," not a multi-tenant or networked system. The library is not exposed to untrusted local users.
- **No untrusted input crossing a trust boundary.** The tar-extraction and archive-based path-traversal CVEs (CVE-2007-4559 and its ecosystem) exist because the _content being processed_ is attacker-supplied. docmend's `.txt`/`.html` corpus is the owner's own legacy library, not adversarial input designed to escape containment — the actual risk there (per §13.5/R-006) is malformed/degraded content crashing or misclassifying the pipeline, not maliciously engineered symlinks.

What remains a **real, non-adversarial reliability risk** — and is worth defending against regardless of trust model — is the owner's own tooling touching the library mid-run: a backup/sync client, an editor autosave, antivirus/indexing scans, or a second concurrent `docmend` invocation. These can legitimately change file identity (rename, replace, or — rarely — symlink) between `plan` and `apply` without any attacker involved. FR-003's hash re-validation already exists for exactly this reason; the path-containment re-check in §2 step 3 is the same insurance applied to path identity instead of content identity.

**Recommendation — proportionate hardening, not maximal hardening:**

| Adopt (low cost, matches existing design) | Skip for v1 (solves a problem docmend doesn't have) |
| --- | --- |
| `resolve()` + `is_relative_to()` canonical check at plan time, re-run immediately before write (§2) | Full per-component `openat`/`O_NOFOLLOW` directory-walk hardening (Chromium/`cap-std` style) |
| `dir_fd`-scoped `os.stat()`/`os.open()`/`os.replace()` in the writer, with graceful degrade via `os.supports_dir_fd` (§4) | File locking or advisory locks against concurrent writers |
| `O_NOFOLLOW` on the leaf open of the original file (EC-008 enforcement) and `O_EXCL` on temp-file creation | Sandboxing / `chroot()` / capability-based filesystem restriction (`cap-std`-equivalent) |
| `os.walk(followlinks=False)` (stdlib default) for discovery; record symlinks in the inventory, never descend | Adversarial fuzzing of the containment check itself as a security control (useful only if an untrusted party can influence config or the corpus, which is out of scope here) |
| Backup-dir containment check reusing the same `is_contained()` primitive (OQ-005's "outside the mutation target path" item) | Treating a passed containment check as a permanent guarantee — always re-check at time-of-use per file, not once per run |

This mirrors Python core's own judgment on the structurally similar `tarfile` problem: land the practical, layered check that closes the overwhelmingly likely race, and explicitly decline to chase a fully airtight adversarial guarantee that the threat model does not justify (§3, PEP 706 discussion).

## 6. Version/date sensitivity

- `os.path.realpath(path, *, strict=False)` — `strict` parameter added in Python 3.10; docmend targets 3.14, well past this.
- `PurePath.is_relative_to()` — added in Python 3.9; its explicit "does not resolve symlinks" warning is current as of the Python 3.14 docs pulled for this report (2026-07).
- `dir_fd` support is platform-dependent and must be probed at runtime via `os.supports_dir_fd`, not assumed from the Python version alone — this has been stable stdlib behavior since Python 3.3 and is not expected to change.
- The `filelock` GHSA-w853-jp5j-5j7f advisory and the `uutils coreutils cp` CVE-2026-35359 are both recent (2026) real-world confirmations that the "`stat`-then-`open`-without-`O_NOFOLLOW`" anti-pattern is still being shipped in widely used tools — this is not a theoretical concern, it recurs regularly, which is why §4's pattern avoids it even though §5 concludes the exploitation precondition doesn't hold for docmend.

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://docs.python.org/3/library/pathlib.html> | `pathlib` — Object-oriented filesystem paths (Python 3.14.6 docs) | 2026 (current) | official |
| <https://docs.python.org/3/library/os.html> | `os` — Miscellaneous operating system interfaces (Python 3.14.6 docs) | 2026 (current) | official |
| <https://github.com/python/cpython/issues/118289> | `os.path.realpath('notadir/', strict=True)` doesn't raise (symlink-loop limit discussion) | ongoing | official (CPython tracker) |
| <https://cwe.mitre.org/data/definitions/367.html> | CWE-367: Time-of-check Time-of-use (TOCTOU) Race Condition | v4.20 | official (MITRE) |
| <https://owasp.org/www-community/pages/vulnerabilities/race_conditions> | OWASP: Race Conditions (TOCTOU filesystem pattern and fix) | current | official (OWASP) |
| <https://github.com/tox-dev/filelock/security/advisories/GHSA-w853-jp5j-5j7f> | TOCTOU race condition allows symlink attacks during lock file creation (filelock) | 2026 | official (GitHub Security Advisory) |
| <https://radar.offseq.com/threat/cve-2026-35359-cwe-367-time-of-check-time-of-use-t-f2d68315> | CVE-2026-35359: TOCTOU in uutils coreutils `cp` | 2026 | community (aggregator, CVE-sourced) |
| <https://discuss.python.org/t/policies-for-tarfile-extractall-a-k-a-fixing-cve-2007-4559/23149> | Policies for `tarfile.extractall`, a.k.a. fixing CVE-2007-4559 (PEP 706 background) | 2023–2026 | official (Python core dev discussion) |
| <https://snyk.io/articles/safe-path-handling> | Why Secure Filesystem Operations Are Harder Than You Think | 2026 | community (vendor blog, technically substantive) |
| <https://nvd.nist.gov/vuln/detail/cve-2007-4559> | CVE-2007-4559 Detail (NVD) | 2007 (record; ongoing relevance) | official (NIST NVD) |

## Reconciliation notes

- **Fold into spec §8.5** (Design Constraints): replace "Output paths must stay inside the intended output root (§13.5)" with the concrete two-stage check from §2 (plan-time + apply-time re-check via `resolve()` + `is_relative_to()`), cross-referenced to the writer algorithm in §4.
- **Fold into spec §13.5** (Threats and Mitigations): update the "Path escape" mitigation cell from the current one-line pointer to name the specific primitives (`O_NOFOLLOW`, `dir_fd`-scoped `os.replace()`) and cite this report.
- **OQ-004** (artifact schemas, symlink policy): the inventory schema's "symlink records" should capture `is_symlink` per `os.DirEntry`/`os.scandir()` and rely on `os.walk(followlinks=False)`; this report supplies the concrete stdlib call to cite there.
- **OQ-005** (apply safety-gate checklist): the existing "Output root/path containment passes" checklist item should be expanded to state _when_ it runs (plan time and immediately pre-write) and reuse this report's `is_contained()` primitive for the backup-dir containment item too.
- **Spec §21 table drift (verified, orthogonal to this topic):** confirmed during this research that `docs/open-questions.md` defines OQ-012, OQ-013, and OQ-014, but the spec's own §21 "Open Questions and Decisions" table (docs/specs/docmend.md, ends at line ~906) stops at OQ-011 — those three questions are invisible to anyone reading the spec of record in isolation. This report's own subject-matter OQs (OQ-004, OQ-005) _are_ correctly present in the §21 table, so the drift is confined to OQ-012–OQ-014 and does not appear to extend further; worth a follow-up pass across all OQ-record vs. spec-table pairs the next time §21 is touched.
