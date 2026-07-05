# **Workflow:** Gap Analysis

## Goals

Perform a comprehensive gap analysis of the `docmend` project.

## Instructions

- Run a **workflow** using Sonnet workers and Opus where complexity is high. Do not use Haiku or Fable.
- The workflow should comprehensively review the `docmend` spec and overall project, identifying gaps in functionality, documentation, research, etc.
- Document each identified gap in `docs/deep-research-queue.md` and `docs/open-questions.md` as appropriate following the guidelines in those files.
- Perform follow-up internet research using `/qdev:research` to provide evidence-backed recommendations for each gap, and document findings in `docs/research-reports/` as well as summaries in the `open-questions.md` and `deep-research-queue.md` files.
- Where deeper research is required or warranted I will use ChatGPT Deep-Research. Create prompts for each justified deep-research candidate in `docs/deep-research-queue.md`.
- Provide your analysis of the research findings and present recommendations for each gap and open question in `docs/open-questions.md`. Include an analysis of potential downstream impacts of each recommendation on the `docmend` project.
- Assign each gap and open question a priority level (High, Medium, Low) based on its impact on the project and the urgency of addressing it.

## Resources and References

- [docmend Specification](docs/specs/docmend.md)
- [Open Questions](docs/open-questions.md)
- [Deep Research Queue](docs/deep-research-queue.md)
- [Research Reports](docs/research-reports/)
- [Architecture Decision Records](docs/decisions/)
