---
schema_version: '1.1'
id: 'adr-0017-docmend-branch-and-ci-cd-workflow'
title: 'ADR 0017: Branch strategy, branch protection, release process, and CI/CD workflow'
description: 'Adopts the hw-radar workflow model for docmend: a protected main advanced only by merge-commit PRs from a long-lived dev branch; classic branch protection on main requiring all five CI gates (strict), signed commits, admin enforcement, and conversation resolution; release automation deferred to MS-5 with the intended tag-to-GitHub-Release path documented; and dependabot + a distribution-tightened dependency-review license gate. Records why standard-owned workflows were left unedited (no dev push-trigger) and why classic protection was chosen over rulesets.'
doc_type: 'adr'
status: 'accepted'
created: '2026-07-06'
updated: '2026-07-06'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'ci-cd'
  - 'workflow'
  - 'branch-protection'
  - 'release'
aliases: []
related:
  - 'docs/specs/docmend.md'
  - 'docs/handoff/conventions.md'
  - 'docs/handoff/deployed.md'
  - 'docs/adr/adr-0013-v1-dependency-selection.md'
  - 'docs/adr/adr-0014-tool-first-product-scope.md'
supersedes: []
superseded_by: null
source: []
confidence: 'high'
visibility: 'public'
license: null
project:
  decision_makers:
    - 'chrisdpurcell'
---

# Branch strategy, branch protection, release process, and CI/CD workflow

## Context and Problem Statement

docmend had CI gates (`check`, `validate-specs`, `lint-markdown`, `traceability`) but no branch strategy, no branch protection, and no release process — every commit landed directly on an unprotected `main`. Before feature work begins (MS-0), the collaboration and integration workflow needs to be fixed so the first implementation branches land under the intended discipline rather than retrofitting protections onto an active history. The sibling `hw-radar` repo already runs a proven single-developer model; the decision is which parts of it port to docmend, and how they adapt to two structural differences: docmend is a **distributed CLI** (not a deployed web service) and its CI workflows are partly **standard-owned** (the adopted `@v4` Project Standards).

## Decision Drivers

- Establish the workflow before MS-0 so feature branches inherit it, not the reverse.
- Reuse the battle-tested hw-radar model rather than invent a parallel one.
- Preserve the repo's non-negotiable: never hand-edit a standard-owned file to bypass or drift a check (conventions #8).
- Match the single-developer reality — gate on CI and signatures, not on a second human reviewer that does not exist.
- Don't build release machinery for a tool that has no implemented CLI yet.

## Considered Options

- **Port the hw-radar model, adapting the two divergences** (chosen).
- Mirror hw-radar byte-for-byte, including editing `check.yml` to add a `dev` push-trigger and a `deploy.yml`.
- Modern repository **rulesets** instead of classic branch protection.
- Defer the whole workflow until an implementation branch actually needs it.

## Decision Outcome

Chosen option: **port the hw-radar model, adapting the two divergences**, because it reuses a proven workflow while respecting docmend's standard-owned-file constraint and its distributed-CLI (rather than deployed-service) nature.

**Branching.** `main` is protected and advances **only via a pull request from `dev`**, merged with a **merge commit** (not squash — keeps `dev` in sync with `main` and preserves history). `dev` is the long-lived working branch: commit and push to it directly, no PR needed; use a short-lived `feature/*` branch only for isolation.

**Branch protection on `main`** (classic protection, not rulesets — see below), replicating hw-radar with docmend's actual check-run names:

- Required status checks, **strict** (branch must be up to date before merge): `check`, `validate-specs / Specs`, `lint-markdown / Markdown`, `traceability`, `dependency-review`. The two namespaced names are how GitHub reports a reusable-workflow job (`<caller-job> / <called-job>`); a bare `validate-specs` would never match and would deadlock every PR.
- Required signatures: enabled (all history is already GPG-signed).
- Pull request required; **required approvals = 0** (self-merge permitted — there is one developer); dismiss stale reviews on.
- Enforce for admins: enabled — the owner is subject to the same gate.
- Required conversation resolution: enabled.
- Force pushes and branch deletion: blocked. Linear history: not required (merge-commit strategy depends on it being off).

**Release process: deferred (documented, not built).** docmend is pre-implementation with no `[project.scripts]` entry point, so hw-radar's `deploy.yml` has no analog and there is nothing to ship. The intended path — tag `vX.Y.Z` → `uv build` (sdist + wheel) → GitHub Release — is documented in the README and will be wired as a workflow at **MS-5** (spec §19), when v1 is real. PyPI publishing is out of scope for now.

**Supply-chain / license CI.** Port `dependabot.yml` (pip + github-actions, weekly, 7-day cooldown, grouped) and add a `dependency-review.yml` license gate (PR-only). The allowlist is **tightened relative to hw-radar**: no (L)GPL entries and no per-package exemptions, because docmend is distributed and copyleft therefore carries real obligations — each copyleft dependency must be a deliberate, per-package decision when it first appears (enforcing spec §16 / §8.6).

### Consequences

- Good, because the enforcement point (every `dev → main` PR runs all five gates, strict, before merge) is airtight, and admin enforcement + required signatures give it teeth without a phantom reviewer.
- Good, because standard-owned workflows (`check.yml`, `validate-specs.yml`, `lint-markdown.yml`) are left untouched — zero drift risk from a future standards-sync.
- Bad, because direct pushes to `dev` get **no CI until the PR to `main`** (the price of not editing standard-owned `check.yml` to add a `dev` push-trigger). Mitigation: run the local `uv run` gates on `dev`; the PR is the hard gate regardless. Revisit with an ADR-amendment + documented `check.yml` exception if per-push `dev` CI becomes worth the drift.
- Bad, because required approvals = 0 means CI is the only automated barrier to a bad merge — acceptable for a single-developer repo, revisit if the repo gains collaborators.

### Confirmation

Enforced by the live `main` branch protection (queryable via `gh api repos/chrisdpurcell/docmend/branches/main/protection`) and by CI: no PR merges without all five required checks green. The `dependency-review` gate confirms the license posture on every PR.

## Pros and Cons of the Options

### Port the hw-radar model, adapting the two divergences

- Good, because it reuses a proven single-developer workflow.
- Good, because it honors conventions #8 (no standard-owned edits) and the distributed-tool license posture.
- Neutral, because it accepts a known `dev`-CI gap in exchange for zero standard drift.

### Mirror hw-radar byte-for-byte (edit check.yml, add deploy.yml)

- Good, because per-push `dev` CI and a symmetric structure.
- Bad, because editing standard-owned `check.yml` drifts a byte-identical twin and invites a standards-sync clobber (conventions #8).
- Bad, because `deploy.yml` deploys a service docmend does not have.

### Modern rulesets instead of classic protection

- Good, because rulesets are GitHub's forward-looking, layerable mechanism.
- Bad, because hw-radar — the model being ported — uses classic protection, so classic keeps the two repos operationally identical and the config directly comparable. Revisit if org-level rulesets become desirable.

### Defer the whole workflow

- Bad, because feature branches would then land on an unprotected `main` and protections would be retrofitted onto live history.

## More Information

Ported from `hw-radar` (`.github/workflows/`, README branching section, live `main` protection). Realized on branch `dev` via the first `dev → main` PR, which dogfoods the pipeline. Operational how-to for humans lives in the README (Branching, Release process); CI/CD truth lives in `docs/handoff/deployed.md`. Revisit triggers: the repo gains a collaborator (reconsider approvals = 0); per-push `dev` CI becomes worth a documented `check.yml` exception; MS-5 lands the release workflow; a copyleft dependency is proposed (extend the dependency-review allowlist deliberately).
