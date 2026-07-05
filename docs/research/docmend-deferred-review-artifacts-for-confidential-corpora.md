# docmend Deferred Review Artifacts for Confidential Corpora

**Date:** 2026-07-05

## Executive summary

A deferred human-review layer can fit docmend’s **headless** non-goal, but only if the artifact remains a **decision package** rather than becoming a **navigable text surface**. Real precedents support that distinction. `patch`/`git apply --reject` expose only failed hunks in `.rej` files, unified diffs expose bounded context around changes, `rdfind` and `fclones` emit report files that are acted on later, the `dedupe` library separates its matching engine from any user interface, and Terraform separates speculative plans and machine-readable JSON from the eventual apply step. None of those patterns requires an integrated browser or reader; some expose snippets, some expose only metadata, and some explicitly warn that saved artifacts can themselves be sensitive. [\[1\]](https://man7.org/linux/man-pages/man1/patch.1.html)

For docmend, the strongest boundary is this: **a review artifact remains headless if it is bounded to specific flagged issues, contains only the minimum information needed for a yes/no/edit verdict, and does not support arbitrary document exploration, search, or whole-file expansion from within docmend**. That means fuzzy-duplicate review can stay metadata-only by default, while semantic review should default to either an opaque manifest or a tightly bounded excerpt format that is explicitly opt-in and locally handled. The moment docmend adds first-party whole-file expansion, corpus search, or progressive context retrieval, it stops looking like `patch`, `fclones`, or Terraform and starts looking like a reading UI. [\[2\]](https://man7.org/linux/man-pages/man1/patch.1.html)

The recommended posture is **pessimistic-skip / exception-only review**, not review-everything. The automation-bias literature is consistent enough to matter here: overreliance increases with workload, task complexity, and time pressure; people are prone to follow automated recommendations or fail to look for contradictory information; and policy regimes that assume a human can reliably “oversee” every automated recommendation often provide a false sense of safety. In practice, a massive review queue is likely to degrade into rubber-stamping. For confidential semantic changes, that risk combines with the confidentiality cost of exposing text. [\[3\]](https://pubmed.ncbi.nlm.nih.gov/21685142/)

My recommendation is therefore: keep **artifact generation** inside docmend if it is useful, but keep **rendering and browsing** outside docmend. For WH-002, the safest architecture is a two-layer design: a durable, machine-readable manifest that contains no body text, plus an opt-in, local-only text sidecar or external-diff handoff for the small subset of issues that truly require human judgment. For WH-005, keep the default artifact metadata-only, and strongly consider pseudonymized path labels in any artifact that might be shared or retained. [\[4\]](https://docs.dedupe.io/en/latest/API-documentation.html)

## Bottom line and recommendation

**Observation.** Standards and guidance do not require “zero text ever.” ISO/IEC 20889 describes de-identification as transforming a dataset to reduce association with individual data principals and classifies techniques by how they reduce re-identification risk; NIST SP 800-188 frames release design as a choice among access models and explicitly evaluates not just “safe data,” but also “safe settings” and “safe outputs.” Real tool precedent likewise shows that headless workflows can include bounded excerpts when those excerpts are keyed to a specific action, as with unified diffs and reject hunks. [\[5\]](https://cdn.standards.iteh.ai/samples/69373/f0200837a1484de9891b77fb7688e24b/ISO-IEC-20889-2018.pdf)

**Inference.** For docmend, “headless” is best preserved by limiting review artifacts to **issue-scoped evidence** rather than **document-scoped presentation**. In other words, a review file can contain just enough text to decide a proposed correction and still remain consistent with NG-001, but only if docmend itself does not become the place where users browse, expand, search, or read documents as documents. That inference is supported by the separation seen in `dedupe` between core matching APIs and UI-building functions, and by the difference between bounded diff comments and GitHub’s explicit whole-file expansion affordances. [\[6\]](https://docs.dedupe.io/en/latest/API-documentation.html)

**Recommendation.**  
Use the following default boundary:

| Decision area | Recommended default | Why |
| --- | --- | --- |
| **WH-002 semantic corrections** | **No text in durable artifacts by default.** Emit only opaque issue metadata unless the operator explicitly opts into local text exposure. | This keeps the default artifact aligned with minimization and avoids turning routine runs into confidential text exports. [\[7\]](https://cdn.standards.iteh.ai/samples/69373/f0200837a1484de9891b77fb7688e24b/ISO-IEC-20889-2018.pdf) |
| **WH-002 review display** | **Out of docmend.** Allow export of bounded hunks or sidecars for external diff/review tools, but do not add first-party browse/search/reader affordances. | This matches `dedupe`’s engine/UI split and avoids the “expand whole file” boundary crossing visible in code-review UIs. [\[6\]](https://docs.dedupe.io/en/latest/API-documentation.html) |
| **WH-005 fuzzy duplicate clusters** | **Metadata-only by default.** Paths, aliases, sizes, hashes, similarity scores, cluster IDs, and action recommendations. | Duplicate review does not require body text, and existing tools already follow report-then-act patterns on file metadata. [\[8\]](https://github.com/pkolaczk/fclones) |
| **Review posture** | **Exception-only, capped batches, no preselected “accept.”** | Human oversight degrades under workload and recommendation framing; evaluate fewer, higher-value cases. [\[3\]](https://pubmed.ncbi.nlm.nih.gov/21685142/) |

The practical answer to your last question is **yes, the confidentiality concern absolutely justifies keeping WH-002 review rendering out of docmend**. What it does **not** justify is forbidding docmend from generating a minimal, machine-readable handoff package. The best line is: **docmend may identify, package, and record review decisions; external tools may render text**. [\[9\]](https://docs.dedupe.io/en/latest/API-documentation.html)

## Survey of headless report-then-act patterns

| Pattern | Real precedent | Artifact shape | Content-exposure level | Why it is still headless |
| --- | --- | --- | --- | --- |
| Reject-then-fix patching | GNU `patch` and `git apply --reject` write failed hunks to `.rej` files. Rejected hunks come out in unified or context diff format, and `git apply --reject` applies what it can while leaving rejects for later handling. [\[10\]](https://man7.org/linux/man-pages/man1/patch.1.html) | Per-file reject hunks | **Bounded changed text with bounded context** | The artifact is tied to discrete failed hunks, not arbitrary file reading. [\[11\]](https://man7.org/linux/man-pages/man1/patch.1.html) |
| Unified diff review | GNU diff unified format uses hunk headers and surrounding context; Git lets callers tune context with `-U<n>` and inter-hunk fusion with `--inter-hunk-context`. GNU diff can also replace real names with labels. [\[12\]](https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html) | Patch/diff text | **Bounded changed text with tunable context** | It is a transport/review format for changes, not a general document browser. [\[13\]](https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html) |
| Report-then-act duplicate handling | `rdfind` can emit a `results.txt` file with one row per duplicate and can dry-run actions; `fclones group` produces a report that is piped to `remove`, `move`, or `link`. [\[14\]](https://manpages.ubuntu.com/manpages/trusty/man1/rdfind.1.html) | Report file / JSON / text groups | **Metadata only** | The review surface is file identity and actionability, not contents. [\[8\]](https://github.com/pkolaczk/fclones) |
| Human-labeled dedupe candidates | `dedupe` exposes `uncertain_pairs()` and `mark_pairs()`, explicitly “mainly useful for building a user interface”; its console labeling flow asks for `yes`, `no`, or `unsure`. [\[15\]](https://docs.dedupe.io/en/latest/API-documentation.html) | Pair proposals plus verdict categories | **Task-scoped record excerpts** | The core library is separate from the review UI; that separation is the key precedent. [\[15\]](https://docs.dedupe.io/en/latest/API-documentation.html) |
| Plan-before-apply infrastructure changes | Terraform `plan` produces a speculative execution plan; machine-readable UI and JSON output describe planned changes separately from apply. [\[16\]](https://developer.hashicorp.com/terraform/cli/commands/plan) | Human-readable plan plus machine-readable JSON | **Usually metadata-rich; may include sensitive values** | It is explicitly a review/approval step before action, but still a CLI/report workflow. [\[17\]](https://developer.hashicorp.com/terraform/cli/commands/plan) |
| Code review on unified diffs | GitHub review comments attach to a portion of the unified diff; PRs default to diff views, but the UI can also show rich diff, source, and whole-file context. [\[18\]](https://docs.github.com/rest/pulls/comments) | Diff hunks with optional expansion | **Bounded by default; can escalate to whole-file viewing** | The default diff is review-like; whole-file expansion is the boundary where it starts acting like a reader. [\[19\]](https://docs.github.com/articles/about-comparing-branches-in-pull-requests) |

The table points to a clear pattern: **headless review artifacts are normal even when they contain snippets**. What makes them headless is not the absence of text, but the absence of **open-ended navigation and rendering**. [\[20\]](https://man7.org/linux/man-pages/man1/patch.1.html)

## Recommended content-exposure boundary

The most defensible boundary for docmend is:

> **Issue-bounded, decision-sufficient, non-navigable, and opt-in for text.**

That boundary is consistent with unified-diff practice, reject hunks, and report-then-act tools, and it fits NIST’s framing that release design must account for the data, the setting, and the output together rather than treating “de-identified” as a binary label. [\[21\]](https://man7.org/linux/man-pages/man1/patch.1.html)

In practical terms, a docmend review artifact stays on the safe side of NG-001 if all of the following are true:

| Keep it headless | Crosses into de-facto reading UI |
| --- | --- |
| Records are keyed to a finite set of flagged issues or clusters. [\[22\]](https://man7.org/linux/man-pages/man1/patch.1.html) | Users can open arbitrary documents or arbitrary regions on demand. [\[23\]](https://docs.github.com/en/desktop/making-changes-in-a-branch/committing-and-reviewing-changes-to-your-project-in-github-desktop) |
| Text, if present, is limited to bounded hunks or record excerpts needed for a verdict. [\[24\]](https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html) | The system supports whole-file expansion, rich rendering, or accumulates enough hunks to reconstruct normal reading flow. [\[23\]](https://docs.github.com/en/desktop/making-changes-in-a-branch/committing-and-reviewing-changes-to-your-project-in-github-desktop) |
| There is no search, browse, ranking-by-text, or progressive context expansion surface in docmend. This is an architectural inference from the preceding tools and UI contrasts. [\[6\]](https://docs.dedupe.io/en/latest/API-documentation.html) | The artifact becomes a substitute for opening and reading the document corpus. This is the failure mode NIST would treat as a distinct access model question, not merely a file-format question. [\[25\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) |
| Durable artifacts default to metadata-only, with text exposure requiring explicit opt-in and safer settings. [\[26\]](https://developer.hashicorp.com/terraform/language/manage-sensitive-data) | Text-bearing artifacts are produced routinely, retained broadly, or handled like ordinary logs. Terraform explicitly warns against treating sensitive plan/state artifacts casually. [\[27\]](https://developer.hashicorp.com/terraform/cli/commands/plan?utm_source=chatgpt.com) |

A useful analogy is Terraform’s distinction between **redacted UI output** and **persisted plan/state artifacts**, plus its newer **ephemeral** mechanism for values that should not be stored at all. That is not the same domain, but it is exactly the right design lesson: expose less in the durable artifact than in the runtime review surface, and omit what does not need to persist. [\[28\]](https://developer.hashicorp.com/terraform/language/manage-sensitive-data)

## Artifact-shape options for WH-002 and WH-005

### WH-002 semantic correction review

The semantic-correction case is the hard one because the reviewer cannot judge the proposed change without seeing at least some text. The safest design is therefore a **split artifact model**.

| Option | Shape | Exposure | Strengths | Weaknesses | Recommendation |
| --- | --- | --- | --- | --- | --- |
| **Opaque manifest only** | Durable NDJSON contains `issue_id`, `doc_id`, location/range, rule ID, model confidence, and maybe a hash of the proposed replacement, but **no text**. | **None** beyond metadata | Maximum confidentiality; easiest to keep clearly headless; safest for public-repo workflows. | Not self-sufficient for human semantic review; requires a second step to derive what changed. | Best **default**. Use when review is rare or must be tightly controlled. Supported by the engine/UI split in `dedupe` and by Terraform’s omission-oriented handling of sensitive values. [\[9\]](https://docs.dedupe.io/en/latest/API-documentation.html) |
| **Inline bounded hunk** | A single NDJSON record embeds a unified-diff-style miniature hunk: old/new token span plus small surrounding context, with explicit char/line caps. | **Minimal necessary text** | Self-contained; easy to feed to generic diff tooling; directly analogous to reject hunks and unified diffs. | Durable artifact now contains confidential text; line/char caps can distort grammar judgment if too tight. | Good only as an explicit opt-in mode, preferably for small batches. [\[29\]](https://man7.org/linux/man-pages/man1/patch.1.html) |
| **Metadata ledger + text sidecar** | Main NDJSON stays text-free; separate local sidecar stores bounded snippets keyed by `issue_id`. | **Controlled local text** | Preserves safe default while enabling review; can isolate retention policy and storage controls from the durable ledger. | More moving parts; resolver integrity matters. | Best overall balance. This is the strongest recommended architecture. By analogy to Terraform, the main ledger is durable, the text sidecar is the ephemeral/sensitive component. [\[28\]](https://developer.hashicorp.com/terraform/language/manage-sensitive-data) |
| **Redacted bounded hunk** | Same as inline hunk, but untouched context is redacted or generalized where regex/NER can identify obvious PII. | **Minimal text plus minimization** | Better than raw context if names, SSNs, emails, or account-like strings appear nearby. NIST treats redaction/suppression as a de-identification technique, though not sufficient by itself. | Redaction can destroy the very grammar signal the reviewer needs; also creates a false sense of safety if used casually. | Useful as a secondary mode, not a default. [\[30\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) |
| **External diff handoff** | docmend emits metadata and optionally writes transient before/after excerpt files or a patch file for another tool to render. | **No built-in display surface** | Best alignment with NG-001; leverages standard diff tooling and keeps docmend from growing viewer features. | More operational friction; some users will want integrated convenience. | Recommended for any environment with stricter confidentiality expectations. Supported by `patch`/diff conventions and `dedupe`’s engine/UI separation. [\[31\]](https://man7.org/linux/man-pages/man1/patch.1.html) |

A good **schema split** would look like this:

    {"issue_id":"wh002-000123","doc_id":"doc-04f7","path_ref":"alias-219","span":{"start_byte":18432,"end_byte":18457},"kind":"grammar","confidence":0.82,"proposal_hash":"sha256:...","review_mode":"sidecar","decision":null}

And, only when explicitly requested:

    {"issue_id":"wh002-000123","exposure":"bounded-diff","label_old":"doc-04f7:before","label_new":"doc-04f7:after","context_before":"...","old":"its","new":"it's","context_after":"...","redactions":[{"kind":"email","range":[0,12]}]}

Two design details matter more than they first appear.

First, use **aliases rather than raw paths** in any text-bearing artifact. GNU diff’s `--label` precedent shows that review formats do not need to expose real file names. That is especially useful because a path can itself be identifying. [\[32\]](https://www.gnu.org/software/diffutils/manual/html_node/Alternate-Names.html)

Second, bound the context tightly. Git’s diff context is tunable, and context-free patches are explicitly discouraged because too little context becomes unsafe for correct application. For docmend, the analogue is: use enough context for judgment, but not enough for comfortable reading. A defensible default is an **operator-configurable small cap** measured in characters or lines, rather than a fixed “show lots of surrounding prose.” That conclusion is an inference from unified-diff practice plus minimization guidance. [\[33\]](https://git-scm.com/docs/git-apply)

### WH-005 fuzzy duplicate review

WH-005 is much easier because body text is unnecessary.

| Option | Shape | Exposure | Strengths | Weaknesses | Recommendation |
| --- | --- | --- | --- | --- | --- |
| **Pure metadata cluster report** | NDJSON or CSV with `cluster_id`, aliases or paths, sizes, hashes, similarity scores, and canonical recommendation. | **Metadata only** | Closest to `rdfind`/`fclones`; strongly compatible with headless design. | If real paths are included, paths may still leak sensitive meaning. | Strong default, preferably with aliases in shareable artifacts. [\[34\]](https://github.com/pkolaczk/fclones) |
| **Two-file cluster + resolver** | Main report uses `doc_id`/`path_ref`; local resolver maps aliases to actual paths. | **Metadata only in durable/shareable file** | Best for public-repo hygiene and for sharing reports among collaborators without exposing raw path strings. | Slightly more cumbersome for local review. | Recommended for any workflow where artifacts may leave the workstation. [\[35\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) |
| **Verdict column workflow** | Review file includes blank decision fields such as `keep`, `drop`, `not_dupe`, `unsure`, `canonical_id`. | **Metadata only** | Familiar spreadsheet/CSV review pattern; easy to audit and diff. | Spreadsheet tooling can tempt ad hoc handling and accidental sync/share. | Good if stored privately and not committed. The general pattern matches `dedupe`’s verdict categories and report-then-act duplicate tools. [\[36\]](https://github.com/pkolaczk/fclones) |

A concrete WH-005 record can stay comfortably within your current confidentiality posture:

    {
      "cluster_id":"wh005-0042",
      "members":[
        {"doc_id":"doc-a1","path_ref":"alias-001","size":48123,"sha256":"...","similarity":1.0},
        {"doc_id":"doc-b7","path_ref":"alias-118","size":48123,"sha256":"...","similarity":1.0}
      ],
      "recommended_canonical":"doc-a1",
      "decision":null
    }

If you expect artifacts to be shared across machines or people, separate `path_ref` from the real path by default. That is not overkill: NIST notes that simply stripping obvious direct identifiers is often not enough because other remaining attributes can still support re-identification, and ISO/IEC 20889 explicitly frames de-identification in terms of reducing association through attribute-level transformations. A human-readable file path can easily act like an identifying or quasi-identifying attribute in this operational context. [\[37\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf)

## Default review posture and automation-bias risk

The evidence base does **not** support “review everything” as a default safety strategy. Goddard et al.’s systematic review found automation bias to be a real and recurring phenomenon; workload, task complexity, and time pressure are among the mediators that worsen it; and mitigators include training, accountability, confidence signaling, and presenting information rather than naked recommendations. [\[38\]](https://pubmed.ncbi.nlm.nih.gov/21685142/)

Cummings’ review makes the mechanism especially relevant to your case: automation bias is the tendency to disregard or not search for contradictory information once a computer-generated solution is accepted as correct; errors can be by **commission** (following a bad recommendation) or **omission** (failing to notice a problem because the system did not flag it). Her paper also reports experimental cases where users accepted automated plans without adequate scrutiny and argues that higher levels of automation are not advisable in complex, time-critical settings. Even though docmend is not aviation, the cognitive pattern is directly transferable to large, repetitive review queues. [\[39\]](https://maritimesafetyinnovationlab.org/wp-content/uploads/2023/02/Automation-Bias-in-Intelligent-Time-Critical-Decision-Support-Systems.pdf)

Green’s critique of “human oversight” policies is also load-bearing here. The argument is not that human review never helps, but that organizations often assume humans can effectively supervise automated outputs when the actual evidence says otherwise. In those cases, the review step can become a legitimacy layer rather than a genuine error-control layer. That is exactly the failure mode a giant semantic-correction queue would invite. [\[40\]](https://www.sciencedirect.com/science/article/pii/S0267364922000292)

The recommended posture is therefore:

| Review question | Recommended default |
| --- | --- |
| Should docmend generate a full semantic review queue by default? | **No.** Default to **skip** unless the operator explicitly asks for review artifacts over a bounded scope. [\[41\]](https://pubmed.ncbi.nlm.nih.gov/21685142/) |
| When should WH-002 review be generated? | **Exception-only.** Use it for low-confidence, policy-sensitive, or user-specified subsets, not the entire corpus. This is an inference from the automation-bias evidence and the confidentiality cost of text exposure. [\[3\]](https://pubmed.ncbi.nlm.nih.gov/21685142/) |
| Should the artifact pre-fill “accept” or emphasize the model’s recommendation? | **No.** Leave `decision` null and avoid framing that encourages recommendation-following. Goddard et al. specifically note value in information design and accountability. [\[38\]](https://pubmed.ncbi.nlm.nih.gov/21685142/) |
| Should there be bulk-approve for WH-002 text-bearing changes? | **Prefer no**, or at least keep it out of the default path. Large repetitive queues create the exact conditions under which automation bias grows. [\[42\]](https://pubmed.ncbi.nlm.nih.gov/21685142/) |
| Should WH-005 be broader? | **Yes, somewhat.** Metadata-only duplicate review is much less confidentiality-sensitive and less cognitively deceptive than semantic prose edits, though destructive actions should still remain separate from identification. [\[43\]](https://github.com/pkolaczk/fclones) |

In short: **for WH-002, “review everything” is the wrong default twice over**—first because it leaks more text than necessary, and second because it creates the kind of repetitive oversight process humans perform poorly. [\[3\]](https://pubmed.ncbi.nlm.nih.gov/21685142/)

## Public-repo data-minimization and implementation controls

A public repository is not itself the problem. The problem is that a text-bearing review artifact is a **data release** derived from confidential source material, and NIST SP 800-188 makes clear that release design must account for the access model, the setting, repeated releases, and the output itself. Terraform’s guidance adds a very practical warning from another domain: sensitive artifacts are often exposed not through the runtime interface but through saved plan/state files, JSON exports, and ordinary version-control habits. [\[44\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf)

The mapping for docmend should be:

| Constraint | Guidance from standards and precedent | Implementation implication for docmend |
| --- | --- | --- |
| **Public source repo** | ISO/IEC 20889 and NIST both focus on the attributes and outputs that can enable re-identification, not on whether the generating code is proprietary. [\[45\]](https://cdn.standards.iteh.ai/samples/69373/f0200837a1484de9891b77fb7688e24b/ISO-IEC-20889-2018.pdf) | Keep examples, fixtures, tests, and docs synthetic or public-domain only; never rely on “private generated at runtime” as an excuse to show real text in repository materials. |
| **Confidential generated artifacts** | NIST distinguishes among public release, DUA-style controlled sharing, and enclave-style protected access, and emphasizes safe settings and safe outputs. [\[46\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) | Treat text-bearing review artifacts as **private local artifacts**, not normal build outputs. If they ever leave the workstation, that is a distinct release decision. |
| **Path strings may leak meaning** | ISO frames de-identification as attribute transformation to reduce association; NIST warns that removing obvious identifiers alone is often insufficient because remaining attributes can still re-identify. [\[47\]](https://cdn.standards.iteh.ai/samples/69373/f0200837a1484de9891b77fb7688e24b/ISO-IEC-20889-2018.pdf) | Use path aliases in durable or shareable artifacts; keep real-path mapping local. |
| **Repeated artifact generation compounds leakage** | NIST warns that repeated queries or repeated de-identified releases can combine to reveal identifying information, even when each release looks harmless in isolation. [\[48\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) | Avoid versioning text sidecars, avoid long-lived snippet archives, and do not treat prior review bundles as harmless audit crumbs. |
| **Saved artifacts are easy to mishandle** | Terraform explicitly says plan/state artifacts with sensitive values should be treated as sensitive, excluded from Git workflows, and secured; redaction in CLI output is not enough if persistence still occurs. [\[49\]](https://developer.hashicorp.com/terraform/language/manage-sensitive-data) | Keep text-bearing outputs outside ordinary repo trees and CI artifacts by default; separate durable metadata from ephemeral text. |
| **Need for governance on exports** | NIST’s Disclosure Review Board model emphasizes written applications, methodology review, result review, and records of releases. [\[50\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) | If you ever support exporting review text for collaboration, make that a deliberate, documented “release” pathway with a policy gate, not a casual flag. |

Two recommendations follow directly.

First, adopt a **durable-manifest / ephemeral-sidecar** pattern. Terraform’s `sensitive` versus `ephemeral` distinction is a strong precedent: some information may be shown or used transiently while being deliberately omitted from persisted artifacts. For docmend, that means the durable ledger can remain hash/path/score oriented, while any text snippets live in opt-in, locally controlled sidecars that are designed to be omitted from ordinary retention. [\[28\]](https://developer.hashicorp.com/terraform/language/manage-sensitive-data)

Second, if you want the cleanest alignment with NG-001 and the lowest future-maintenance risk, keep WH-002 **review rendering entirely out of docmend**. That does not mean docmend cannot generate the bundle. It means docmend should stop at detection, packaging, and decision recording, and let external diff or merge tools do the viewing. The `dedupe` APIs are an especially relevant precedent here: they are explicit that the uncertain-pair functionality is mainly for building a user interface, which is separate from the matching engine itself. [\[15\]](https://docs.dedupe.io/en/latest/API-documentation.html)

There is one meaningful uncertainty worth stating plainly: no cited source gives a formal industry definition of “headless” for confidential-document remediation tools. The boundary recommended here is therefore an **architectural inference** drawn from diff/reject/report patterns, UI contrasts, and de-identification release guidance. It is, however, a well-supported inference. [\[51\]](https://man7.org/linux/man-pages/man1/patch.1.html)

## Sources

- GNU `patch` manual and man page on reject hunks, `.rej` files, and reject format. [\[52\]](https://man7.org/linux/man-pages/man1/patch.1.html)
- Git documentation for `git apply --reject`, unified diff expectations, and diff context controls. [\[53\]](https://git-scm.com/docs/git-apply)
- `rdfind` man page and `fclones` documentation for report-then-act duplicate handling. [\[14\]](https://manpages.ubuntu.com/manpages/trusty/man1/rdfind.1.html)
- `dedupe` API and `console_label` documentation for uncertain pairs, match/distinct labeling, and UI separation. [\[15\]](https://docs.dedupe.io/en/latest/API-documentation.html)
- Terraform documentation for speculative plans, machine-readable UI/JSON output, and sensitive/ephemeral artifact handling. [\[54\]](https://developer.hashicorp.com/terraform/cli/commands/plan)
- GitHub documentation for PR diff review, unified/split views, and whole-file expansion affordances. [\[18\]](https://docs.github.com/rest/pulls/comments)
- ISO/IEC 20889 scope and terminology preview for de-identification techniques, re-identification risk, and applicability to free-form text. [\[55\]](https://cdn.standards.iteh.ai/samples/69373/f0200837a1484de9891b77fb7688e24b/ISO-IEC-20889-2018.pdf)
- NIST SP 800-188 on data-sharing models, repeated-release risk, Five Safes, DRBs, and output governance. [\[56\]](https://csrc.nist.gov/pubs/sp/800/188/final)
- Automation-bias evidence from Goddard et al., Cummings, and Green. [\[3\]](https://pubmed.ncbi.nlm.nih.gov/21685142/)

---

[\[1\]](https://man7.org/linux/man-pages/man1/patch.1.html) [\[2\]](https://man7.org/linux/man-pages/man1/patch.1.html) [\[10\]](https://man7.org/linux/man-pages/man1/patch.1.html) [\[11\]](https://man7.org/linux/man-pages/man1/patch.1.html) [\[20\]](https://man7.org/linux/man-pages/man1/patch.1.html) [\[21\]](https://man7.org/linux/man-pages/man1/patch.1.html) [\[22\]](https://man7.org/linux/man-pages/man1/patch.1.html) [\[29\]](https://man7.org/linux/man-pages/man1/patch.1.html) [\[31\]](https://man7.org/linux/man-pages/man1/patch.1.html) [\[51\]](https://man7.org/linux/man-pages/man1/patch.1.html) [\[52\]](https://man7.org/linux/man-pages/man1/patch.1.html) patch(1) - Linux manual page

<https://man7.org/linux/man-pages/man1/patch.1.html>

[\[3\]](https://pubmed.ncbi.nlm.nih.gov/21685142/) [\[38\]](https://pubmed.ncbi.nlm.nih.gov/21685142/) [\[41\]](https://pubmed.ncbi.nlm.nih.gov/21685142/) [\[42\]](https://pubmed.ncbi.nlm.nih.gov/21685142/) Automation bias: a systematic review of frequency, effect mediators, and mitigators - PubMed

<https://pubmed.ncbi.nlm.nih.gov/21685142/>

[\[4\]](https://docs.dedupe.io/en/latest/API-documentation.html) [\[6\]](https://docs.dedupe.io/en/latest/API-documentation.html) [\[9\]](https://docs.dedupe.io/en/latest/API-documentation.html) [\[15\]](https://docs.dedupe.io/en/latest/API-documentation.html) Library Documentation — dedupe 3.0.2 documentation

<https://docs.dedupe.io/en/latest/API-documentation.html>

[\[5\]](https://cdn.standards.iteh.ai/samples/69373/f0200837a1484de9891b77fb7688e24b/ISO-IEC-20889-2018.pdf) [\[7\]](https://cdn.standards.iteh.ai/samples/69373/f0200837a1484de9891b77fb7688e24b/ISO-IEC-20889-2018.pdf) [\[45\]](https://cdn.standards.iteh.ai/samples/69373/f0200837a1484de9891b77fb7688e24b/ISO-IEC-20889-2018.pdf) [\[47\]](https://cdn.standards.iteh.ai/samples/69373/f0200837a1484de9891b77fb7688e24b/ISO-IEC-20889-2018.pdf) [\[55\]](https://cdn.standards.iteh.ai/samples/69373/f0200837a1484de9891b77fb7688e24b/ISO-IEC-20889-2018.pdf) cdn.standards.iteh.ai

<https://cdn.standards.iteh.ai/samples/69373/f0200837a1484de9891b77fb7688e24b/ISO-IEC-20889-2018.pdf>

[\[8\]](https://github.com/pkolaczk/fclones) [\[34\]](https://github.com/pkolaczk/fclones) [\[36\]](https://github.com/pkolaczk/fclones) [\[43\]](https://github.com/pkolaczk/fclones) GitHub - pkolaczk/fclones: Efficient Duplicate File Finder · GitHub

<https://github.com/pkolaczk/fclones>

[\[12\]](https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html) [\[13\]](https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html) [\[24\]](https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html) Detailed Unified (Comparing and Merging Files)

<https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html>

[\[14\]](https://manpages.ubuntu.com/manpages/trusty/man1/rdfind.1.html) Ubuntu Manpage: rdfind - finds duplicate files

<https://manpages.ubuntu.com/manpages/trusty/man1/rdfind.1.html>

[\[16\]](https://developer.hashicorp.com/terraform/cli/commands/plan) [\[17\]](https://developer.hashicorp.com/terraform/cli/commands/plan) [\[54\]](https://developer.hashicorp.com/terraform/cli/commands/plan) terraform plan command reference \| Terraform \| HashiCorp Developer

<https://developer.hashicorp.com/terraform/cli/commands/plan>

[\[18\]](https://docs.github.com/rest/pulls/comments) REST API endpoints for pull request review comments - GitHub Docs

<https://docs.github.com/rest/pulls/comments>

[\[19\]](https://docs.github.com/articles/about-comparing-branches-in-pull-requests) About comparing branches in pull requests - GitHub Docs

<https://docs.github.com/articles/about-comparing-branches-in-pull-requests>

[\[23\]](https://docs.github.com/en/desktop/making-changes-in-a-branch/committing-and-reviewing-changes-to-your-project-in-github-desktop) Committing and reviewing changes to your project in GitHub Desktop - GitHub Docs

<https://docs.github.com/en/desktop/making-changes-in-a-branch/committing-and-reviewing-changes-to-your-project-in-github-desktop>

[\[25\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) [\[30\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) [\[35\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) [\[37\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) [\[44\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) [\[46\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) [\[48\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) [\[50\]](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf) De-Identifying Government Datasets: Techniques and Governance

<https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf>

[\[26\]](https://developer.hashicorp.com/terraform/language/manage-sensitive-data) [\[28\]](https://developer.hashicorp.com/terraform/language/manage-sensitive-data) [\[49\]](https://developer.hashicorp.com/terraform/language/manage-sensitive-data) Manage sensitive data in your configuration \| Terraform \| HashiCorp Developer

<https://developer.hashicorp.com/terraform/language/manage-sensitive-data>

[\[27\]](https://developer.hashicorp.com/terraform/cli/commands/plan?utm_source=chatgpt.com) terraform plan command reference

<https://developer.hashicorp.com/terraform/cli/commands/plan?utm_source=chatgpt.com>

[\[32\]](https://www.gnu.org/software/diffutils/manual/html_node/Alternate-Names.html) Alternate Names (Comparing and Merging Files)

<https://www.gnu.org/software/diffutils/manual/html_node/Alternate-Names.html>

[\[33\]](https://git-scm.com/docs/git-apply) [\[53\]](https://git-scm.com/docs/git-apply) Git - git-apply Documentation

<https://git-scm.com/docs/git-apply>

[\[39\]](https://maritimesafetyinnovationlab.org/wp-content/uploads/2023/02/Automation-Bias-in-Intelligent-Time-Critical-Decision-Support-Systems.pdf) maritimesafetyinnovationlab.org

<https://maritimesafetyinnovationlab.org/wp-content/uploads/2023/02/Automation-Bias-in-Intelligent-Time-Critical-Decision-Support-Systems.pdf>

[\[40\]](https://www.sciencedirect.com/science/article/pii/S0267364922000292) The flaws of policies requiring human oversight of government algorithms - ScienceDirect

<https://www.sciencedirect.com/science/article/pii/S0267364922000292>

[\[56\]](https://csrc.nist.gov/pubs/sp/800/188/final) SP 800-188, De-Identifying Government Datasets: Techniques and Governance \| CSRC

<https://csrc.nist.gov/pubs/sp/800/188/final>
