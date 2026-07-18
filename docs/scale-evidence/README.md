# Scale Qualification Evidence

This directory is the public boundary for DMR-08 scale qualification. Evidence records what an installed wheel proved on a synthetic corpus; it never stores the private corpus, path-bearing logs, build workspace, or document content.

The binding workflow is sequential and runs four fresh supervisors in order: `scan`, `plan`, `apply --write`, and `verify --plan`. A run is acceptable only when the candidate wheel, committed source, reference environment, artifact chain, exact corpus accounting, expected finding multiset, resource telemetry, and applicable thresholds all reconcile.

## Private workspace

`scripts/qualify_scale.py` requires one absent workspace outside the checkout. The orchestrator creates it with mode `0700`, holds its identity through publication, and never clears or reuses it. The workspace contains the archived source, built wheel, virtual environment, synthetic corpus, product artifacts, and path-bearing supervisor logs. Treat all of it as private even though the corpus is synthetic.

The workspace remains after success or failure so an operator can investigate the exact attempt. Review it on the qualification host, then remove it manually under the repository's evidence-retention policy. Never copy the workspace, logs, fixtures, host paths, or real library documents into this public repo.

### Candidate path identity boundary

The harness binds the virtual-environment interpreter and resolved target as soon as the environment is created, then reconciles that identity immediately before and after each installer, package check, and import-proof consumer. Before the import proof it also snapshots the console script and archived measurement wrapper; the complete candidate lease is then reconciled around the import proof and later stage consumers. A permanent replacement makes the attempt incomplete with `harness-error`; the harness does not silently continue with a different candidate.

This is path reconciliation, not descriptor-bound execution. The Task 5 process contract still opens these paths by name, and the interpreter loads the installed package tree from pathname-based `site-packages`; those modules are not individually snapshotted.

Binding qualification therefore assumes quiescent same-UID ownership from source inspection through acceptance across four surfaces: the candidate repository, the bound interpreter, the complete qualification workspace including installed `site-packages`, and both ordinary and accepted publication destinations. No concurrent process under the invoking UID may mutate any of those surfaces. Reject evidence unless the operator can guarantee that exclusivity for the full interval.

Same-UID in-call swap-and-restore, open-inode mutation, `ptrace`, and process injection remain outside the threat model. Removing this limitation would require a separately designed immutable-runtime sandbox, not partial Task 5 descriptor plumbing or a claim that the current path checks provide immutable execution.

## Capture the reference environment

Reference capture uses its own absent external workspace and a no-clobber output:

```bash
uv run python scripts/qualify_scale.py --capture-reference \
  --workspace "$tmp/reference-workspace" \
  --output "$tmp/reference-environment.json"
```

Capture records only the strict public reference model: Linux architecture and CPU label, logical CPU count, RAM, storage and filesystem classes, approved mount flags, and Python and kernel versions. The qualification snapshots and hashes those immutable bytes before evidence begins. Comparison is exact except that mount-flag order is immaterial and `ram_bytes` may differ by at most one current Linux base page because `MemTotal` reports usable rather than immutable installed RAM; wider RAM deltas remain mismatches, and the observed host must independently satisfy the 16 GiB minimum.

If the observed host differs from the reference, the pipeline still runs for diagnostic value. A binding request then publishes `diagnostic` evidence and exits nonzero; an explicitly diagnostic request exits zero when otherwise correct.

## Run qualification

A small diagnostic may override the fixed tier count:

```bash
uv run python scripts/qualify_scale.py --tier pilot --diagnostic --count 40 \
  --workspace "$tmp/qualification-workspace" \
  --reference-environment "$tmp/reference-environment.json" \
  --evidence-out "$tmp/diagnostic.json"
```

Binding counts are fixed: `pilot` and `scheduled` use 100,000 files, and `release` uses 1,000,000 files. `scheduled` and `release` require the executable threshold baseline with `--thresholds`; `pilot` forbids it. Only a `pilot --diagnostic` run may override `--count`. A scheduled or release diagnostic may redundantly spell its fixed tier count, but cannot change it because its thresholds are defined only at that count. Diagnostic evidence cannot use `--accept-to`.

All workspaces and ordinary evidence outputs must be absent and outside the checkout. `--accept-to`, when supplied for a binding run, must name an existing real directory. Input or destination refusal before candidate, reference, and lock provenance is fixed exits `2` without evidence. After that boundary, the orchestrator preserves the validated execution prefix, publishes evidence when possible, and exits `1` for failed or incomplete qualification.

## Status and reason semantics

The evidence schema permits four statuses:

| Status | Meaning |
| --- | --- |
| `passing` | A complete binding run satisfied correctness, telemetry, reference, runtime, and applicable threshold contracts. |
| `diagnostic` | The run was explicitly diagnostic or the host differed from the accepted reference; it is never acceptable evidence. |
| `failed` | Trustworthy observations proved a product, threshold, or runtime failure. |
| `incomplete` | Required proof was unavailable or untrustworthy, so the run cannot make a correctness claim. |

The finite primary reasons are reduced with fixed precedence:

- Failed: `stage-exit`, `conservation-mismatch`, `finding-mismatch`, `threshold-exceeded`, or `runtime-limit-exceeded`.
- Incomplete: `reference-observation-unavailable`, `provenance-changed`, `build-failed`, `install-failed`, `capacity-insufficient`, `capacity-estimate-exceeded`, `corpus-materialization-failed`, `supervisor-failed`, `telemetry-unavailable`, `artifact-invalid`, or `harness-error`.
- Diagnostic: `reference-mismatch` or `explicit-diagnostic`.

A missing, unreadable, schema-invalid, or identity-invalid artifact is `artifact-invalid`. A safely loaded, identity-valid artifact whose facts disagree with corpus conservation, lifecycle or plan coverage is `conservation-mismatch`; disagreement with the exact expected finding multiset is `finding-mismatch`. Failed evidence retains the exact discrepant totals rather than inventing passing counts.

Release timing starts immediately before the scan supervisor dispatch and ends after the last validated attempted result. The published runtime is at least the sum of public stage times. More than 43,200 seconds fails qualification and reopens the concurrency decision; it does not enable concurrency automatically.

## Thresholds and supporting points

`thresholds.json` is the revision-two executable baseline for scheduled and release evidence. It binds the reference-environment hash, immutable 10,000- and 100,000-file supporting-point hashes, stage-aligned external peak RSS data, and the exact-per-stage-linear-projection method. Its frozen limits are 25,902,581,760 bytes absolute peak RSS, 25,804 bytes/file incremental slope, and 0.20 linearity. The implementation recomputes those limits before use; it never weakens a threshold after a miss.

The revision-two fit uses diagnostic point `supporting/14f3118e4f57c992b9d5088b9cb4f35fb3658686-pilot-10000.json` and passing point `accepted/14f3118e4f57c992b9d5088b9cb4f35fb3658686-pilot-100000.json`, both bound to `reference-environment.json`. Store future reviewed diagnostic inputs under `supporting/`; store only complete, reviewed, passing binding evidence under `accepted/`.

## Publication and accepted names

Ordinary evidence is validated and published first with exclusive no-clobber creation. Only passing binding evidence may then be published to `--accept-to`. The accepted bytes must be identical to the ordinary evidence bytes. A race or preexisting target is never overwritten; an acceptance race preserves ordinary evidence and exits `1`.

The three installed-workflow names use the full lowercase candidate commit and fixed count:

```text
<commit>-pilot-100000.json
<commit>-scheduled-100000.json
<commit>-release-1000000.json
```

The separately implemented file-size lane uses `<commit>-file-size.json`. Accepted filenames are deterministic; do not rename evidence to make a failed, diagnostic, different-host, or different-commit run appear binding.

The accepted file-size settlement is `accepted/f050e0aa8e2d4cf05abae09d6834e88a74a00193-file-size.json` (`sha256:4db8276907201dc45366c29053e6da574443197defcc1f2969237fb4523d647e`). Its 12 UTF-8/Windows-1252 cases cover 1, 25, 50, 75, and 100 MiB under external preservation plus both 100 MiB tool-backup cases. All cases passed with zero child swap and a maximum measured stage RSS of 1,894,080,512 bytes, retaining the configured 100 MiB default under the 2 GiB limit.

The accepted one-million-file release settlement is `accepted/ae3a28677390da7c823846c32af2c84b746ae861-release-1000000.json` (`sha256:c5253a874159e938768d0d7cd42e8742cc8464b0044888997cf61bfca13fb7e6`). Candidate `ae3a28677390da7c823846c32af2c84b746ae861` completed all four installed-wheel stages in 25,629.225 seconds with 1,000,000 scanned, 875,000 applied, no apply skips or failures, and the exact 25,000 expected/observed verify findings. All artifacts validated, child swap remained zero, maximum stage RSS was 20,825,497,600 bytes, and the frozen absolute, incremental-slope, linearity, reference-environment, and 43,200-second runtime verdicts passed.

## Public-data rules

Public models and JSON Schemas reject unknown fields and private identifiers. Evidence may contain aggregate counts, timings, rates, byte sizes, version labels, hashes, threshold verdicts, and sanitized reference classes. It must not contain hostnames, usernames, absolute paths, serial or device identifiers, credential material, document bodies, per-file logs, or unknown or value-bearing mount options. Record credential references only; never record secret values.

## Review and validation

Before accepting evidence, a reviewer should confirm:

1. The candidate commit is the intended clean commit and the wheel and lock hashes match the run.
2. The reference and threshold hashes resolve to the reviewed immutable inputs.
3. All four stages are present, completed, artifact-validated, and ordered.
4. Totals conserve the corpus and plan, the manifest lifecycle is complete, and observed findings equal the expected multiset.
5. External RSS, zero child swap, capacity, thresholds, and release runtime pass.
6. The document contains no private data and its accepted bytes equal the ordinary evidence bytes.

Run the repository gate before committing any evidence-boundary change:

```bash
uv run python scripts/check.py
npx --yes prettier@3.6.2 --check docs/scale-evidence/README.md
npx --yes markdownlint-cli2@0.18.1 docs/scale-evidence/README.md
```

Evidence readers and writers perform strict model and JSON Schema validation, immutable-byte hashing, safe relative-name checks, and no-clobber publication. Do not hand-edit evidence to bypass those checks; rerun qualification instead.
