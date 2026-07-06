# **Workflow:** Enforce Consistency and Mitigate Drift Exposures

Run a **workflow** to:

- _Enforce consistency_ between the master spec (`docmend.md`), ADRs, and resolved questions (`resolved-questions.md`).
- _Mitigate drift exposures_ by ensuring that all information is in its canonical location and not duplicated across documents.

## Goals

- The `docmend.md` spec is **100%** internally consistent and adheres to all guidelines and/or published standards under which it is governed.
- Each ADR is **100%** internally consistent, unambiguous, and adheres to all guidelines and/or published standards under which it is governed.
- There are **zero** contradictions or ambiguities between ADRs.
- There are **zero** contradictions or ambiguities between any ADR and the `docmend.md` spec.
- Any resolved questions in `resolved-questions.md` found to be inconsistent with the spec or ADRs are downgraded to open questions and relocated to `open-questions.md` for further research and resolution.

## Additional Guidelines

### Workflow Execution

- _Workers:_ Use Sonnet subagents for routine worker-level tasks.
- _Complex tasks:_ Use Opus for complex tasks.
- _Avoid:_ Haiku and Fable subagents.
- Use as many subagents as needed to achieve a successful outcome.
- You are empowered to expand the workflow with additional steps if needed to fill gaps or address issues that I may have missed.

### Resources for Inconsistency Resolution

- _Repo level sources:_ Research reports in `docs/research/` and `docs/deep-research-queue.md`.
- _Internet research:_ Using `/qdev:research`.
- _Deep research escalation:_ If still unresolved, escalate to a deep-research prompt in `docs/deep-research-queue.md` for further investigation.

### Drift Mitigation Guidelines

- _Deduplication:_ Avoid duplicating information across documents where possible. Comprehensive structured information belongs in its single canonical location (e.g., ADRs, spec, or research reports). Use links/pointers/references to the canonical source instead of restating when it must be referenced elsewhere.
- _Reference; don't repeat:_ Do not verbosely restate ADRs in the spec; the spec should summarize the critical points and reference the ADRs for details.
- _Promote and remove:_ When a piece of information is promoted, ensure it is removed from the original location to avoid duplication and potential drift. A link may be left in the original location to point to the new canonical source, but the original content should be removed to prevent drift.

## References

- [`docmend` Specification](docs/specs/docmend.md)
- [Resolved Questions](docs/resolved-questions.md)
- [Open Questions](docs/open-questions.md)
- [Architecture Decision Records](docs/adr)
- [Research Reports](docs/research)
- [Deep Research Queue](docs/deep-research-queue.md)
