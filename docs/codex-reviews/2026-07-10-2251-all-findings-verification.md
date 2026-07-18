# Review Findings Verification — Post-Plan-A

Verification of the [2026-07-10-2034 complete sweep findings](2026-07-10-2034-all-review-findings.md) against `dev` HEAD `24b57bb`, per the urgent task in `docs/TODO.md`. The sweep snapshot predates the entire safety-core Plan A implementation (`66b0140..24b57bb`, landed 21:00–22:40 the same evening), so every verdict below was re-established against current code, not the sweep's line references.

Method: direct inspection of the full Plan A diff (`b9d5195..6ae7547`), two independent targeted code-verification passes over the DMR evidence paths, and a full test-suite run at HEAD (651 passed, 1 skipped — the opt-in scale test).

## Rollout-blocker verdicts

| ID | Sweep status | Verified status at HEAD | Owner |
| --- | --- | --- | --- |
| DMR-01 | High | **Closed by Plan A** | done |
| DMR-02 | High | **Closed by Plan A** (CLI surface) | done |
| DMR-03 | High | Still open | Plan B |
| DMR-04 | High | Still open | Plan B/C |
| DMR-05 | High | Still open | Plan D |
| DMR-06 | High | Still open | Plan C |
| DMR-07 | High | Still open, marginally mitigated | Plan C |
| DMR-08 | High contract failure | Still open | Sub-project 2 |
| DMR-09 | High future-release risk | Still open | Sub-project 3 |

### DMR-01 — closed

`build_plan` now keeps an output ledger (`claimed_outputs`) that reserves every action's effective output path — rename targets AND in-place rewrite paths — so no two actions in one plan can share an output; the second claimant becomes a `collision` skip naming the claimer (`src/docmend/planning.py`). Independently, backup keys are namespaced `{run_id}/{action_seq}/{role}/{relative_path}` and write-once: publication is a no-clobber hardlink, and an occupied key raises `BackupError` (`src/docmend/writer/backup.py`). The sweep's exact reproduction (in-place `a.md` rewrite + `a.txt → a.md` rename sharing one backup key) is impossible at both layers; both claim orderings have regression tests (`tests/test_planning.py::TestCollisions`).

### DMR-02 — closed at the CLI surface

`guard_artifact_destination` (`src/docmend/artifacts.py`) refuses destinations whose lexical entry or resolved referent lands in the corpus (with the per-destination `.docmend/` carve-out), non-regular-file destinations, and aliases of the invocation's input artifacts. It runs before the pipeline on `scan --report`, both `plan` branches (including the shorthand's inventory artifact), and `apply` report+manifest paths; manifests reachable via `--resume-run-id` count as input aliases. Report finalization moved inside the run lock. Staging is randomized `O_EXCL` with cleanup on every unpublished exit, in both the artifact writer and `writer/atomic.py`.

Residual (known, scoped): the guard-to-write window is a TOCTOU — a destination parent swapped to a corpus symlink after preflight is not re-checked at write time. That is DMR-06's class and is Plan C scope, not a Plan A gap.

### DMR-03 — still open

`read_manifest` (`src/docmend/writer/manifest.py:142-171`) still validates line-by-line with no run-level pass for single root, single run, version ceiling (schema pattern `^1\.\d+$` accepts any future minor), sequence integrity, or lifecycle. `_restore_one` (`src/docmend/restore.py:146-287`) reads and mutates recorded paths verbatim with no containment against the recorded `source_root`; the restore lock root comes from `records[0]` alone (`src/docmend/cli.py:424-439`). The containment guard added for apply resume (`apply.py:248-255`) was never extended to restore/verify.

### DMR-04 — still open

Only `rename_and_rewrite` writes a pre-mutation intent (`apply.py:495-512`); pure rewrite and pure rename mutate first and append their only record after (`apply.py:515-522` then `581-593`). Restore mutates before appending inverse evidence (`restore.py:238-266` then `268-284`). Verify and restore both filter to `result == "applied"` and ignore dangling intents (`verify.py:98`, `restore.py:124`).

### DMR-05 — still open

All four false-clean outcomes reproduce in current code: `reconcile_manifest` never reads or hashes backup bytes (`verify.py:88-114`); verify iterates only readable inventory files and exits 0 on zero checked files (`verify.py:43,68`; `cli.py:933-934`); a `fail`-policy mid-plan abort leaves trailing actions in neither outcome nor record set, invisible to `reconcile_report` (`verify.py:117-151`); no root-match check between manifest and PATH argument; no `verify --plan` interface.

### DMR-06 — still open

Apply hashes and containment-checks a pathname (`apply.py:372-385`), then later mutates whatever that name resolves to (`apply.py:514-525`) with no fd pinning, `O_NOFOLLOW`, or commit-time re-hash. Restore is symmetric (`restore.py:84-102` vs `238-258`).

### DMR-07 — still open, marginally mitigated

The collision policy and overwritten-target backup are evaluated at apply time from a fresh `target.exists()` (`apply.py:396-446`), and Plan A's write-once keys removed the backup-collision failure mode — so with tool backups configured, a late-appearing target IS now preserved. The open remainder: the gate's preservation contract is never re-asserted at commit, and when `backup_root is None` (external/git preservation declared) a late target is clobbered with only `overwritten_sha` recorded and no recoverable bytes. The action-time preservation invariant remains Plan C scope.

### DMR-08 — still open

Corpus-wide collections persist (`discovery.py:222-229`, `planning.py:189-190`); `ParallelConfig` has zero runtime consumers; the scale test still budgets 10 KiB/file (`tests/test_scale.py:51`) and still asserts one manifest record per applied action (`test_scale.py:186`), which manifest 1.3's intent+terminal records violate — the staleness is unchanged and, as already planned, gets mechanically fixed with Plan B's manifest 2.0.

### DMR-09 — still open

`release.yml` still publishes on any `v*.*.*` tag with no main-ancestry, signature, or package-version-equality proof; `actions/checkout@v7` remains a mutable tag inside the write-capable job (first-party `actions/*` on tags is a documented deliberate choice — the finding stands as accepted-risk-vs-hardening for sub-project 3).

## Medium-theme verdicts

| Theme | Verified status at HEAD |
| --- | --- |
| Planning mints a new UUID per document (no stable identity) | Still open (`planning.py:178,374`) |
| JSON readers: duplicate keys, unenforced aggregates, future minors accepted | Still open (bare `json.loads` everywhere; only apply's plan read guards minors) |
| Public write engines callable outside CLI lock/gate coordination | Still open (`execute_plan`, `run_restore` are plain exports) |
| Fixed staging names block retry after hard kill | **Fixed by Plan A** (randomized EEXIST-retried staging, `atomic.py:45-73`, `artifacts.py:169-178`) |
| Disk preflight double-counts shared filesystems | Still open (`gate.py:162-215`, two independent `shutil.disk_usage` checks) |
| Timeouts treated as success; targeted restore silent no-op on unmatched IDs | Still open (both: `discovery.py:313-323`/`planning.py:386-403` skip-and-continue; `restore.py:121-125` + `cli.py:827-833` exit 0) |
| Logs: no terminal event contract, 0644 under 022 umask, no sink-level redaction | Still open (`observability.py:98`, caller-obligation comment only) |

The sweep's "Corrected Or Non-Applicable" section needed no re-verification — none of its five entries concern code that changed.

## Plan A regression review

- **Full suite green at HEAD**: 651 passed, 1 skipped. The two failures visible in stale session tooling (`test_schemas.py` frontmatter schema, `test_cli_scan.py` exclude-flag skips) do not reproduce — pre-Plan-A cache, not regressions.
- **Behavior change from the output ledger is intended and tested**: plans over corpora where a rename target coincides with an in-place rewrite path now emit one action plus one `collision` skip (deterministic lexicographic first-claimant) instead of two actions. This counts toward `fail`-policy exit accounting, matching G-005.
- **One false alarm refuted during verification**: `apply.py:542`'s unparenthesized `except WriteError, OSError:` was flagged as a `SyntaxError` — it is deliberate PEP 758 syntax, valid on the project's Python 3.14 floor, carries an in-code comment anticipating the misread, and the green suite proves the module parses.
- **No interaction found** between Plan A's changes (planning ledger, backup keys, artifact guard, staging) and the DMR-03/04/05 code paths — the restore/verify/manifest-read surfaces are byte-untouched by Plan A, so the remaining verdicts carry no hidden coupling to the landed work.

## Appendix — raw catalog verdicts (all 189 findings)

Round 2 of this verification: every ISSUE in all 18 lens reports was individually classified against HEAD via five targeted verification passes. A finding that "maps to" a DMR or medium theme inherits that section's verdict (and evidence) above; only exceptions and distinct claims are annotated here. Tally: **4 fixed** by Plan A, **6 partially fixed**, **179 still open** (most inheriting DMR/theme verdicts; the rest distinct lens-local findings owned by sub-projects 2–4 and the docs sweep).

### AI and prompt workflow (8)

All eight still open — the prompts and their governance docs are untouched since 2026-07-06. ISSUE-003's dead paths (`docs/research-reports/`, `docs/decisions`) persist; ISSUE-007's WH-006 ownership conflict between spec §semantic-enrichment and adr-0018 is unreconciled.

### API contract (10)

001/002 → DMR-03; 004 → aggregates-on-read theme; 005 → duplicate-keys theme; 006 → future-minors theme; 007 → DMR-05 (spec-vs-CLI verify contract). Distinct, still open: **003** — report schema allows free-string `skip_reason` where the internal model is a closed literal, and `read_report` lets `ValidationError` escape `ArtifactError` (`artifacts.py:263-276`); **008** — `run_id`/`action_id` ownership undocumented; **009** — UUIDv7 contract unvalidated (`plan.py:25-28` accepts any UUID); **010** — no CLI/TOML deprecation policy.

### Architecture and boundary (10)

**002 — fixed by Plan A** (report finalization now inside the run lock with a guarded destination; residual: `gate.py` itself still takes no report path). 001 → public-engines theme; 003 → DMR-04/03; 005 → DMR-08; 006 → future-minors theme. Distinct, still open: **004** — inert `ParallelConfig` (no runtime consumer); **007** — transform policy duplicated between planning and apply; **008** — `cli.py` grew further (865 → 934 lines); **009** — the only import-linter contract still covers transform purity alone; **010** — `docs/handoff/architecture.md:23` still says "v1.0.1 is released" and its writer-only-mutation claim still contradicts `restore.py`.

### Background jobs and async workflow (13)

**007 — fixed by Plan A** (randomized EEXIST-retried staging). **009 — partially fixed**: the lock-released-before-report half closed with DMR-02; the no-durable-terminal-run-state half remains (DMR-04/05). 001/011 → DMR-03; 002/003 → DMR-04; 004 → public-engines theme; 010 → DMR-08. Distinct, still open: **005** — inert parallel config; **006** — SIGALRM watchdog is cooperative, not a hard boundary; **008** — no durable resume/attempt lineage in the manifest; **012** — standalone `scan` and `verify` acquire no run lock (verified directly: the only `_acquire_run_lock*` sites are plan `cli.py:322,343`, apply `:588`, restore `:813`); **013** — no recovery-protocol convention.

### CI/CD (10)

All ten still open; 001/002 → DMR-09. Workflow files are byte-unchanged since the sweep: no sdist/installed-product release test (003), unpinned `uv_build` range with no locked `uv-build` record (004), no scheduled `pip-audit` (007), no checksums/attestations (008), no `concurrency:` blocks (009), `scripts/check.py` still omits Markdown/spec/traceability checks (010). Server-side claims (005/006 graph ingestion, token defaults) are not locally verifiable.

### Comprehensive code review (19)

**018 — stale (fixed by Plan A)**: the deterministic `.docmend-tmp` residue blocker no longer exists. **009 — partially fixed**: report lock-scope and destination guard closed via DMR-02; still open — `write_json_artifact` never fsyncs the parent directory after `tmp.replace` (`artifacts.py:186`), unlike `atomic.py:107`. Mapped: 001 → DMR-04, 002/010 → DMR-03, 003 → DMR-06, 004 → DMR-07, 005/006/007/015 → DMR-05, 008 → DMR-08, 011 → duplicate-keys + aggregates themes, 014 → logs theme, 017 → targeted-restore theme, 019 → public-engines theme. Distinct, still open: **012** — `parallel`/`write.atomic`/`write.dry_run_default` accepted but inert; **013** — 100 MiB default file size with no measured working-set budget; **016** — `verify` (and `scan`, per background-jobs 012) runs unlocked against an active mutation run.

### Conventions (9)

All nine still open — `docs/handoff/conventions.md` is unchanged since 2026-07-06: frontmatter-emission overstatement (001), stale standard-ownership entry (002), no artifact-schema-evolution convention (003, now more acute with manifest 2.0 approved), sensitive-data convention excludes runtime artifacts (004), wrong spec profile in the scaffold (005), unpinned npx tooling (006), no lock-freshness step in the gate example (007), house-schema ordering violations (008), no branch/release convention (009).

### Data schema and migration (9)

**008 — partially fixed**: collision-safety closed by Plan A's randomized `O_EXCL` staging; the durability half (no parent-dir fsync after replace) remains. Mapped: 001 → DMR-04; 002/003 → DMR-03; 004 → report-schema mismatch (API 003); 005 → future-minors theme (evidence line shifted to `cli.py:539`, claim intact); 006 → aggregates theme; 007 → duplicate-keys theme. Distinct, still open: **009** — no artifact-schema-evolution trigger in the conventions index.

### Dependency and supply chain (9)

All nine still open; 001/004 → DMR-09. Same evidence set as CI/CD: dynamic release toolchain (002), no SBOM/provenance (005), wheel-version-only smoke (006), event-driven-only auditing (007), unpinned ambient npx/uvx conventions (008), allowlist-only license gate (009). Graph-ingestion claims (003) not locally verifiable.

### Documentation and runbook (14)

**001 — partially fixed**: spec rev 0.26 recontracts the recovery model (journal-every-mutation intent), but it is unimplemented until Plan B and `README.md:75-77` plus both runbooks still carry the unconditional v1 reversibility language. All other thirteen still open, two now slightly worse: the recontract added `verify --plan` and the verify-report artifact as documented-but-unimplemented surface (002/008 widen until Plans B–D land), and the spec revision table's ordering degraded further (…0.24, 0.27, 0.26, 0.25 — 014).

### Frontend state and interaction (5)

**003 — fixed by Plan A** (report finalizes in-lock with guarded destination; residual: a valid-but-unwritable report path can still error after mutation, minor). 001 → DMR-04; 002 → DMR-05; 004 → targeted-restore theme. Distinct, still open: **005** — successful `-q` commands still emit paths/summaries (`typer.echo` calls ungated on `opts.quiet`).

### Incident readiness (15)

001 → DMR-04; 002 → DMR-03; 003 → DMR-06; 004/006/007/008 → DMR-05 (006's report-publication half closed via DMR-02); 010 → targeted-restore theme; 011 → future-minors theme; 012 → DMR-09. Distinct, still open: **005** — restore runbook cannot prove pre-apply state (no before-state reconciliation command); **009** — external preservation declarations (`preserved_by`) capture no recovery point; **013** — only two runbooks, no incident template; **014** — no `SECURITY.md`/intake/severity policy; **015** — no drill cadence or field evidence.

### Integration and third-party boundary (13)

**011 — partially fixed**: the uv-not-pinned sub-claim is stale (`setup-uv` is now SHA-pinned in `release.yml:26`); the untransacted `gh release create` and mutable `checkout@v7` remain (→ DMR-09). **013 — partially fixed**: the unused-pyfakefs sub-claim is stale (`tests/unit/writer/test_atomic.py` now uses it); inactive pytest-xdist and the missing pre-commit config remain. Mapped: 001/008 → DMR-03; 002 → DMR-04; 003 → duplicate-keys theme; 004/006 → DMR-05; 005 → DMR-09; 007 → future-minors theme (fixtures still simulate old versions by field deletion, not preserved released artifacts). Distinct, still open: **009** — runtime deps have lower bounds only (`pyproject.toml:10-18`), future majors permitted at release-critical boundaries; **010** — no OS classifiers while `lock.py:20` imports `fcntl` unconditionally (POSIX-only boundary undisclosed); **012** — license gate rests on unproven `uv.lock` ingestion.

### Observability (9)

All nine still open — they collectively ARE the logs/terminal-event/redaction medium theme; `src/docmend/observability.py` is untouched by Plan A (0755 dirs + 0644 `FileHandler`, no terminal event contract, no sink-side redaction, no exception boundary, no heartbeat, transport-only tests, no disk budget, no convention entry).

### Performance (8)

All eight still open; 001/003/004 → DMR-08 (note: Plan A's `claimed_outputs` ledger and `inventory_paths` set marginally ADD per-corpus retention — directionally against NFR-001, for sub-project 2 to absorb); 006 → observability theme. Distinct: **002** — ~10× heap amplification path for large files unchanged (`backup.py:68` re-read included); **005** — verify re-reads and re-hashes what scan already hashed; **007** — watchdog not a hard boundary; **008** — no performance convention.

### Product and business logic (9)

001 → DMR-06; 002 → DMR-03; 003/004/005/006 → DMR-05; 008 → targeted-restore theme. Distinct, still open: **007** — `parallel` AND `write.atomic`/`write.dry_run_default` accepted but operationally inert; **009** — reversibility rationale still internally contradictory (nullable `backup_path` vs "every mutation undoable").

### Release readiness (7)

All seven still open; 002 → DMR-09 (003's mutable-tag half too). **001 carries one stale sub-claim**: `CHANGELOG.md` now has an `[Unreleased]` section (Plan A), but no version surface moved — HEAD is 30 commits past `v1.0.2` while `pyproject.toml`/`__init__.py` still say 1.0.2, so the incoherent-candidate core stands (by design until the v2.0.0 release PR). 004–007: install-artifact testing, provenance, rollback runbook, and duplicate-release rejection all unchanged.

### Test suite (12)

All twelve still open; 002 → DMR-05; 004/005 → DMR-08 (the scale test's manifest assertion was reworded but still assumes one record per applied action — still fails when enabled, mechanically fixed by Plan B's manifest 2.0); 011 → observability theme. Plan A's new tests (`test_artifact_guard.py`, ledger/backup/staging additions) cover only the Plan A surfaces — containment-consumer coverage (001), terminal accounting (003), TOCTOU seams (006), traceability strength (007), packaging journey (008), released-producer fixtures (009), recovery-state property tests (010), and mutation baseline (012) are all unchanged.

## New facts surfaced by the raw-catalog pass

Three things the consolidated layer didn't isolate, worth carrying into the remaining plans:

1. **`write_json_artifact` never fsyncs the parent directory after `tmp.replace`** (`artifacts.py:186`), while `writer/atomic.py:107` does — the one durability asymmetry Plan A left on its own surface. Cheap, well-bounded; fold into Plan B's artifact work (it owns the surviving halves of comprehensive-009 and data-schema-008).
2. **Standalone `scan` also runs unlocked**, not just `verify` — both can observe (and report on) a corpus mid-mutation. Plan D / sub-project scope should treat them together.
3. **The rev 0.26 recontract temporarily widened the documented-vs-implemented gap** (`verify --plan`, verify-report artifact, journal-every-mutation are now spec'd but not built) — expected for a recontract-first program, but the docs sub-project must reconcile README/runbooks only after Plans B–D land, not before.

## Conclusion

The sweep's findings remain accurate at HEAD with exactly the closures the changelog claims. Across all 189 raw findings: 4 fixed by Plan A (architecture-002, background-jobs-007, frontend-003, comprehensive-018), 6 partially fixed (background-jobs-009, comprehensive-009, data-schema-008, documentation-001, integration-011/013 — each with the residual half annotated above), and 179 still open, the majority inheriting the DMR-03..09 and medium-theme verdicts. No finding invalidates or is invalidated by the landed Plan A work, and no re-planning of Plans B, C, or D is needed — the approved design's decomposition, plus sub-projects 2–4, still covers the verified defect set.
