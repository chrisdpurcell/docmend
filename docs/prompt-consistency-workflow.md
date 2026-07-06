# **Workflow:** Spec & ADR Consistency

Run a **workflow** to ensure consistency among the **Source of Truth** documents: the `docmend.md` spec and ADRs. Use _Sonnet_ (workers/routine) and _Opus_ (complex tasks) subagents only.

## Goals

- The `docmend.md` spec is **100%** internally consistent.
- Each ADR is **100%** internally consistent.
- There are **zero** contradictions or conflicts between ADRs.
- There are **zero** contradictions or conflicts between any ADR and the `docmend.md` spec.
- Any resolved questions in `resolved-questions.md` found to be inconsistent with the spec or ADRs are downgraded to open questions and relocated to `open-questions.md` for further research and resolution.

## Additional Guidelines

If inconsistences are found that are not obviously resolvable, seek clarification from:

- Research reports in `docs/research/` and `docs/deep-research-queue.md`.
- Internet research using `/qdev:research`.
- If still unresolved, escalate to a deep-research prompt in `docs/deep-research-queue.md` for further investigation.

## Resources and References

- [`docmend` Specification](docs/specs/docmend.md)
- [Resolved Questions](docs/resolved-questions.md)
- [Open Questions](docs/open-questions.md)
- [Architecture Decision Records](docs/decisions/)
- [Research Reports](docs/research/)
- [Deep Research Queue](docs/deep-research-queue.md)
