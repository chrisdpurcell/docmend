# Resolved Questions — `docs/specs/docmend.md`

**Companion to [`open-questions.md`](open-questions.md)** — that file holds questions that still need decisions plus the shared [maintenance rules](open-questions.md#how-to-maintain-this-document). This file is the settled record for decisions that do not yet live in an ADR or in the spec itself.

**Terminology:** an **open question** (`OQ-###`) is a decision still to be made and lives in [`open-questions.md`](open-questions.md). A **resolved question** (`RQ-###`) is already settled and lives here until it is superseded by an ADR or folded back into the canonical spec.

## Table of Contents

- [Resolved Questions — `docs/specs/docmend.md`](#resolved-questions--docsspecsdocmendmd)
  - [Table of Contents](#table-of-contents)
  - [Resolved questions](#resolved-questions)
  - [How to use this document](#how-to-use-this-document)

## Resolved questions

No docmend questions are settled in this companion document yet.

When the first question is resolved, add it below using this shape:

```markdown
### RQ-001 — short decision title

**Resolved:** YYYY-MM-DD  
**Source question:** OQ-###  
**Decision owner:** owner | implementer  
**Canonical references:** ADR link, spec section, research document, or TODO item

Decision summary in one or two paragraphs.

#### Rationale

- Why this option won.
- Important alternatives rejected.
- Consequences for implementation.

#### My Comments

Owner comments or decision notes, preserved verbatim when moved from `open-questions.md`.
```

## How to use this document

- Keep only settled docmend decisions here.
- Remove copied template content from other repositories before committing.
- Preserve owner comments from `open-questions.md` when moving a settled item.
- If a resolved question later gets an ADR, replace the body here with a short pointer to the ADR or remove the entry once the ADR is the canonical record.
- Do not use this file as a session log; use Git history and the repo handoff docs for routine maintenance history.
