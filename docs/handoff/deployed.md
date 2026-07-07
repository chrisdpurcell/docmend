# Deployed

**Runtime deployment: not applicable.** docmend is a local, single-user CLI with no deployment target and no environment matrix (spec §18.1/§18.3): manual `uv tool install`/`uvx` from the repo or a tagged release, no service to run, no dev/staging/prod split.

## CI/CD & branch protection

Ported from `hw-radar`; the decision record is [`../adr/adr-0017-branch-and-ci-cd-workflow.md`](../adr/adr-0017-branch-and-ci-cd-workflow.md).

**Branch model.** `main` protected; advances only via merge-commit PR from the long-lived `dev` branch. `dev` takes direct pushes (no CI until the PR — the `dev → main` PR is the gate).

**`main` protection (classic).** Query with `gh api repos/chrisdpurcell/docmend/branches/main/protection`.

- Required status checks (**strict** / up-to-date): `check`, `validate-specs / Specs`, `lint-markdown / Markdown`, `traceability`, `dependency-review`. The two `/`-namespaced names are how GitHub reports reusable-workflow jobs — required contexts must match them verbatim.
- Required signatures ✅ · PR required (approvals = 0, dismiss stale ✅) · enforce-admins ✅ · conversation resolution ✅ · force-push / deletion blocked.

**Workflows** (`.github/workflows/`): `check.yml`, `validate-specs.yml`, `lint-markdown.yml` are **standard-owned** (`@v4`, conventions #8 — do not hand-edit); `traceability.yml` and `dependency-review.yml` are repo-owned additive gates. `dependency-review.yml` is PR-only and enforces a distribution-tightened license allowlist (no copyleft pre-approved — spec §16/§8.6).

**Dependabot** (`.github/dependabot.yml`): weekly pip + github-actions, 7-day cooldown, grouped.

**Release: live (`release.yml`, adr-0017, wired at MS-5 as planned).** Signed `vX.Y.Z` tag on `main` → `uv build` (sdist + wheel) → wheel smoke-test → GitHub Release with artifacts attached. No PyPI in v1. Releases: `v1.0.0` (2026-07-07, first), `v1.0.1` (2026-07-07, issue #15 fix — latest). **Repo security posture:** Dependabot vulnerability alerts + automated security fixes enabled (post-v1.0.0 hygiene pass, 2026-07-07).
