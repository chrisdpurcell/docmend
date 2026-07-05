---
schema_version: '1.1'
id: 'adr-0001-docmend-do-not-adopt-markdown-frontmatter-standard'
title: 'ADR 0001: Do not adopt the Markdown Frontmatter Standard'
description: "docmend adopts four Project Standards but deliberately excludes the Markdown Frontmatter Standard, whose canonical schema conflicts with docmend's own frontmatter contracts."
doc_type: 'adr'
status: 'accepted'
created: '2026-07-05'
updated: '2026-07-05'
reviewed: null
owner: 'chrisdpurcell'
consumer: 'agent'
tags:
  - 'standards'
  - 'frontmatter'
  - 'markdown'
  - 'deviation'
aliases: []
related:
  - '.project-standards.yml'
  - 'docs/specs/docmend-spec-draft.md'
supersedes: []
superseded_by: null
source: []
confidence: 'high'
visibility: 'public'
license: null
project:
  decision_makers:
    - 'chrisdpurcell'
  consulted: []
  informed: []
---

# Do not adopt the Markdown Frontmatter Standard

## Context and Problem Statement

docmend adopts four standards from [Project Standards](https://github.com/L3DigitalNet/project-standards): Python Tooling SSOT, Markdown Tooling, Project Specification, and ADR. The ADR Standard's adoption guide names the **Markdown Frontmatter Standard** as a prerequisite ("Adopt the Frontmatter Standard first — ADR enforcement rides on top of it"), and the Project Specification Standard documents how its own frontmatter must be partitioned away from the canonical frontmatter validator.

Should docmend also adopt the Markdown Frontmatter Standard so that ADR and other managed Markdown carry CI-validated canonical frontmatter?

## Decision Drivers

- docmend's **product output** is Markdown files whose YAML frontmatter follows a **Pandoc-flavored, purpose-built schema** (title, author, date, tags, source provenance, generated fields such as word/chapter count and checksum) validated against docmend's _own_ schema — see [`docs/specs/docmend-spec-draft.md`](../specs/docmend-spec-draft.md). This is the tool's core contract, not a docs concern.
- The repository's spec draft uses **Pandoc-style metadata blocks**, again distinct from the canonical schema.
- The canonical Markdown Frontmatter Standard defines one repo-wide frontmatter schema and a validator that would compete with both of the above over the same file surface.
- Adopting a standard must not force fighting a validator against docmend's primary output format, and the two other Markdown-frontmatter-adjacent standards we _do_ want (ADR, Project Spec) can function without it.

## Considered Options

- **Adopt the Markdown Frontmatter Standard** alongside the other four, scoping its globs to avoid product output.
- **Do not adopt the Markdown Frontmatter Standard**; take ADR and Project Spec in their non-frontmatter-validated forms.

## Decision Outcome

Chosen option: **"Do not adopt the Markdown Frontmatter Standard"**, because docmend already owns two conflicting frontmatter contracts (its Pandoc-flavored product output and the Pandoc-style spec draft), and a repo-wide canonical frontmatter validator would either fight those contracts or require fragile glob carve-outs that grow with every new document type. The ADR and Project Specification standards are adopted in the forms that do not depend on the frontmatter validator.

### Consequences

- Good, because docmend's product frontmatter schema and the Pandoc spec metadata remain the uncontested authority over their files — no second validator competes for them.
- Good, because glob-partitioning fragility (canonical vs. spec vs. product frontmatter) is avoided entirely.
- Bad, because **ADR frontmatter is not CI-validated** in this repo. The `markdown.adr.require_sections` check "rides the same frontmatter workflow," which is not installed, so it would be inert; it is therefore omitted from `.project-standards.yml`. ADRs are authored from `docs/decisions/adr.template.md` and kept consistent **by convention**.
- Bad, because other managed Markdown (docs/) likewise gets no canonical frontmatter validation. Markdown **body** linting/formatting is unaffected — the Markdown Tooling Standard (markdownlint + Prettier) is fully adopted and does cover these files.

### Confirmation

Compliance is confirmed by inspection of `.project-standards.yml`: it declares `python_tooling`, `markdown_tooling`, and `spec` blocks and carries **no** `markdown.frontmatter` block and **no** `markdown.adr` block. This ADR is the recorded exception (per the standards' §20 exceptions process) that authorizes those omissions.

## More Information

- Adopted standards and their wiring: [`.project-standards.yml`](../../.project-standards.yml).
- The prerequisite relationship this ADR opts out of: the [ADR Standard adoption guide](https://github.com/L3DigitalNet/project-standards/blob/v4/standards/adr/adopt.md) §1 and the [Project Specification Standard adoption guide](https://github.com/L3DigitalNet/project-standards/blob/v4/standards/project-spec/adopt.md) §1.
- Revisit this decision if docmend's product frontmatter and the canonical schema converge, or if a per-directory frontmatter-schema selection mechanism is added to the standard.
