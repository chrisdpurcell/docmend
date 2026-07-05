# Encoding Detection at Corpus Scale: Detector Choice, Confidence Semantics, and Threshold

**Date:** 2026-07-05

**Related:** `docs/specs/docmend.md` FR-007, AW-003, EC-003/EC-007, R-001, §8.6 (Dependency Policy), §9 (`source.detected_encoding`), Appendix C.4 (decision provenance) · `docs/open-questions.md` (no dedicated OQ yet — see Reconciliation notes) · `docs/deep-research-queue.md` Candidate Topics row "Encoding detection at corpus scale" · GAP-42 (detector choice), GAP-43 (single confidence signal for FR-007), GAP-44 (defensible threshold / short-text tie failure mode) — gap IDs as supplied by the requesting task; no `GAP-` numbering scheme exists elsewhere in this repo yet, so this mapping (42→detector, 43→signal, 44→threshold) is inferred from the research question's three sub-parts, not read from a tracked gap register.

**Gap it fills:** FR-007 currently pins `charset-normalizer` as the detection dependency (§8.6) and a `fail_below_confidence` default of `0.80` (§18.2), but the spec never justifies either choice against alternatives, and — more importantly — `charset-normalizer`'s public API has no `confidence` attribute at all; it exposes `chaos` and `coherence` on `CharsetMatch`, so FR-007's "detection confidence" is presently an undefined term with no implementation-ready meaning. This report closes that gap: it compares the four named detectors on API surface, confidence semantics, license, and Python 3.14 support; traces `charset-normalizer`'s own chardet-compatibility shim to find the exact, already-shipped formula for turning chaos into a 0–1 confidence number; shows why the current `0.80` default is defensible against that formula; and documents a live, upstream-acknowledged failure mode — a short, mostly-ASCII string decoding with zero chaos into the _wrong_ legacy CJK encoding at confidence 1.0 — that the confidence signal alone cannot catch, with a concrete mitigation and fixture proposal.

## Bottom Line and Recommendation

Keep `charset-normalizer` as FR-007's sole detector; do not add `chardet`, `faust-cchardet`, or `uchardet`. Define docmend's `source.detected_encoding.confidence` as exactly `1.0 - CharsetMatch.chaos` — the same derivation `charset-normalizer`'s own chardet-compatibility shim already uses internally[^legacy] — rather than inventing a bespoke chaos/coherence blend. Keep `coherence` (and `language`, `could_be_from_charset`) as recorded provenance fields (§9, Appendix C.4) that a human/agent can inspect when triaging the skip pile, but do not fold them into the single scalar that `fail_below_confidence` gates on — a blended formula would drift from upstream's own documented semantics on every dependency bump and would be harder to reason about at review time. Keep the spec's existing `fail_below_confidence = 0.80` default; §"Threshold" below shows it already sits above the worst case the library's own built-in small-sample guard can produce. Add one thing the spec does not yet have: a second, independent skip condition based on the count of non-ASCII bytes in the decoded sample, because the documented short-text failure mode (below) produces `chaos = 0.0` — i.e. **maximum** confidence — on a wrong answer, so no confidence threshold, however conservative, catches it.

## 1. Detector Comparison

| Detector | API surface | Confidence semantics | License | Python 3.14 wheels | Maintenance (2026-07) |
| --- | --- | --- | --- | --- | --- |
| **`charset-normalizer`** 3.4.7 | `from_bytes()`/`from_path()`/`from_fp()` return a sorted `CharsetMatches`; `.best()` gives a `CharsetMatch` with `.chaos` (0–1, mess ratio), `.coherence` (0–100, language-fit score), `.language`, `.languages`, `.could_be_from_charset`, `.alphabets`, `.bom`. No `.confidence` attribute on `CharsetMatch` itself. A separate chardet-compatible `detect()` shim _does_ return a `confidence` key, computed as documented in §2 below.[^api][^legacy] | No native single confidence float on the rich object; the chardet-shim's `confidence = 1.0 - chaos`, penalized on tiny inputs. | MIT[^pypi-cn] | `cp314` and `cp314t` (free-threaded) wheels published for 3.4.7, all major platforms.[^pypi-cn-files] | Active; already docmend's approved dependency (§8.6). Weekly-scale release cadence; healthy per Snyk.[^snyk-cn] |
| **`chardet`** 7.4.3 | `detect()`/`detect_all()` return chardet's original dict shape: `{"encoding", "confidence", "language"}`; `detect_all()` ranks multiple candidates; `UniversalDetector` supports streaming; `encoding_era=` and `include_encodings=`/`exclude_encodings=` narrow the candidate set.[^chardet-faq] | Native `confidence` float 0.0–1.0 per result, produced by chardet's internal per-encoding heuristics/statistical models — the same general design lineage as the original Mozilla/chardet approach; not a calibrated probability, "your mileage may vary" per its own FAQ. | Disputed: PyPI `license_expression` for 7.4.3 is `0BSD`; project README separately claims MIT at points in its history; original chardet was LGPL-2.1.[^pypi-chardet][^register] | `cp310`–`cp314`, including `cp314t`, published.[^pypi-chardet-files] | Actively releasing (7.4.x line), but under public dispute over whether the underlying LGPL→permissive relicense is valid — see §4. |
| **`faust-cchardet`** 2.1.19 | Chardet-compatible `detect()` dict (`encoding`, `confidence`, `language`); C-extension binding to the uchardet engine (fork of the unmaintained `PyYoshi/cChardet`).[^faust-pypi] | Native `confidence` float, but coarse/bucketed in practice (observed values like `0.50`, `0.99` rather than a smooth distribution) because it surfaces uchardet's internal per-model scores directly.[^bytetunnels] | MPL (per PyPI classifier: "Mozilla Public License").[^faust-pypi-json] | No published wheels past `cp312`; would require a C compiler to build from source for 3.13/3.14, with no verified 3.14 build reported anywhere found in this research.[^faust-pypi-files] | Explicitly a stopgap fork ("since the original project is no longer maintained"); itself shows no recent activity signal in this research pass. |
| **`uchardet`** (C library / CLI, freedesktop.org) | Not a Python package. A C library (originally Mozilla's universal charset detector, C-language-bound by BYVoid) plus a `uchardet` CLI that prints a best-guess encoding name — no documented numeric confidence output from the CLI.[^uchardet-debian][^uchardet-gh] | None exposed as a score; binary "this is the answer" output only. (`faust-cchardet`/`cchardet` are the Python-facing wrappers around this same engine and _do_ expose a score — see row above.) | LGPL-2.1 (library).[^uchardet-debian] | N/A — not a Python wheel; would require shelling out to a system binary or vendoring the C library via a build step. | Low-churn C project; stable but not something docmend can `pip install`. |

Practical reading for docmend: `uchardet` is out because it is not a Python dependency and exposes no confidence value at all — using it would mean inventing a synthetic confidence, which is strictly worse for the Appendix C.4 provenance requirement than using a library that documents its own number. `faust-cchardet` is out on packaging grounds alone (no 3.13/3.14 wheels, C-compiler-at-install-time, unmaintained lineage) before accuracy is even considered — this conflicts with C-001 (locked Python 3.14 tooling stack) and the offline, single-machine posture (§18.1). `chardet` is the only real contender to displace the incumbent, and its accuracy claims are covered in §3; its licensing status is covered in §4 and is, on its own, reason enough not to introduce it without an explicit `OQ-` per §8.6's dependency-approval gate.

## 2. The Confidence Signal: What FR-007 Should Actually Compute

`charset-normalizer`'s public `CharsetMatch` object never exposes a field literally called `confidence`. It exposes:

- `chaos` (0.0–1.0): the "mess ratio" — how much of the decoded text looks like noise/garbage under a battery of heuristic plugins (`MessDetectorPlugin`s testing things like suspicious character-range transitions, accent density, and so on).[^mess]
- `coherence` (0–100): a language-fit score from letter-frequency analysis against the library's per-language frequency tables; used to break near-ties in `chaos` between candidates, and to pick a probable language label — it is **not** part of the confidence computation described below.[^coherence]

The library ships its own answer to "how do I get one 0–1 number," in the chardet-backward-compatibility shim (`charset_normalizer.detect()`), read directly from the current source (`src/charset_normalizer/legacy.py`, `master` as of 2026-07):

```python
r = from_bytes(byte_str).best()
confidence = 1.0 - r.chaos if r is not None else None

# automatically lower confidence on small byte samples
# https://github.com/jawah/charset_normalizer/issues/391
if (
    confidence is not None
    and confidence >= 0.9
    and encoding not in {"utf_8", "ascii"}
    and r.bom is False
    and len(byte_str) < TOO_SMALL_SEQUENCE   # TOO_SMALL_SEQUENCE = 32 (constant.py)
):
    confidence -= 0.2
```

This is a documented, currently-shipping, primary-source formula[^legacy][^constant] — not a guess. **Recommendation: docmend's FR-007 should compute `source.detected_encoding.confidence` the same way** — `1.0 - best_match.chaos`, with the same small-sample guard — rather than blending in `coherence`. Reasons:

1. **Semantic stability.** `1.0 - chaos` is what "confidence" already means for anyone who has used this library's chardet-compat mode (`requests`, and any project migrated from `chardet`, already relies on this exact mapping). Inventing a different chaos/coherence blend for docmend would silently diverge from that shared meaning the next time someone (or an agent) reads `charset-normalizer`'s docs while debugging a docmend skip.
2. **Reimplement, don't call the shim directly.** Use `from_path()`/`from_bytes()` and read `.best().chaos` yourself rather than calling the deprecated-but-not-removed `detect()` shim, because the shim only returns `{encoding, language, confidence}` — it discards `coherence`, `could_be_from_charset`, and `alphabets`, all of which Appendix C.4 requires docmend to record as decision provenance alongside the confidence value. Docmend needs `charset-normalizer`'s richer object anyway; only the _arithmetic_ should match the shim.
3. **`coherence` earns its keep as a secondary, recorded signal, not a blended one.** Folding it into a single number obscures two different questions — "does this decode cleanly?" (chaos) vs. "does the decoded text look like a real language?" (coherence) — that a human reviewing the skip pile (§20, "Operational usability") benefits from seeing separately.

## 3. Threshold: Why `0.80` Is Defensible, and Where It Still Fails

The spec's current default, `encoding.fail_below_confidence = 0.80` (§18.2), interacts cleanly with the formula above:

- If a match's raw `1.0 - chaos` lands at the small-sample guard's trigger point (`>= 0.9`) and the guard fires, the penalized value is at most `0.9 - 0.2 = 0.70` — always below `0.80`. **The default threshold is set high enough that it always catches the library's own worst-case penalized result for genuinely tiny samples (< 32 bytes).** This is not a coincidence worth losing if the threshold is ever "rounded down" for convenience — `0.80` is doing real work at exactly this boundary.
- Independent, non-`charset-normalizer` evidence backs the general shape of this guard. Henri Sivonen's (Mozilla `chardetng`, the detector behind Firefox's own legacy-encoding fallback) published convergence analysis found windows-1252-family languages need roughly 20 non-ASCII bytes, and CJK legacy encodings need roughly 10 non-ASCII bytes, before detection accuracy stabilizes at document-length levels; some ISO-8859-2/windows-1250 language pairs still had not fully converged even at 1000 non-ASCII bytes.[^chardetng] This corroborates, from a different detector's author entirely, that "how many non-ASCII bytes are actually in the sample" — not raw file length — is the variable that governs short-text reliability.

**Where `0.80` (or any confidence-only threshold) still fails:** `charset-normalizer`'s own issue tracker documents a live case where `TOO_SMALL_SEQUENCE`'s 32-byte cutoff does not apply because the sample is _slightly longer_ than 32 bytes, yet the misdetection is just as severe. A ~38-byte, almost entirely ASCII English sentence containing exactly one non-ASCII byte (`\xba`, the Latin-1/Windows-1252 masculine ordinal indicator `º`) was detected as **Big5** (a two-byte CJK encoding) with `chaos = 0.0` and reported chardet-shim confidence `1.0` — the byte pair that byte coincidentally forms happens to be a structurally valid Big5 code point, so the "mess" heuristics see zero noise. `chardet` 7, run on the same input, correctly identified ISO-8859-1 at a self-reported confidence of `0.73`.[^issue391] This is a single-source example (one GitHub issue), but it is on the tool's own official issue tracker, filed against and reproduced by the maintaining project, and its mechanism — a short run of non-ASCII bytes coincidentally forming a valid multi-byte sequence in an unrelated legacy charset — is exactly the class of "multiple unrelated charsets tie" scenario named in the research question; treat the _mechanism_ as corroborated (it follows directly from how byte-based multi-byte encodings work, and matches Sivonen's independent short-sample convergence data) even though this exact reproduction is `[unverified]` as a permanently-fixed/unfixed bug (no changelog entry confirming a fix was located in this research pass).

**Recommendation — add a second, independent gate, not a lower threshold:** because the failure mode above produces the _maximum possible_ confidence (chaos = 0), no amount of tightening `fail_below_confidence` fixes it — the fix has to look at something confidence doesn't capture. Add a docmend-level, pre-decode risk check in the Planning layer (§8.1, "collisions, files that appear binary... low-confidence encodings" is exactly this layer's job): count non-ASCII bytes in the sampled content, and classify the file as risky (FR-015 skip-and-report, distinct reason code from "low confidence") whenever that count is below a configurable floor — informed by Sivonen's data, a starting default in the 8–20 non-ASCII-byte range depending on whether the winning encoding is single-byte (windows-1252/ISO-8859 family, need more) or multi-byte (CJK legacy, need fewer) is defensible, though the exact number needs validation against docmend's real weird-document corpus once it exists (§17.2) rather than being asserted as final here. This is a **docmend-specific synthesis**, not a documented recommendation from any one source — flag it as such if folded into the spec, and track the exact default as a new `OQ-` rather than silently hardcoding it (see Reconciliation notes).

## 4. Security and Licensing: The `chardet` 7 Relicensing Dispute

This is directly relevant to "detector choice" even though it is not an accuracy question. In 2026, `chardet` was rewritten from a clean-room brief using an AI coding agent and relicensed from LGPL-2.1 to a permissive license (`0BSD` per current PyPI metadata; MIT is referenced elsewhere in project material during the transition). The dispute is corroborated across three independent sources:

- A GitHub issue on `chardet`'s own repository, from an account claiming to be original author Mark Pilgrim, arguing the relicense is invalid because the rewrite is not a clean-room implementation (the maintainer had prior exposure to the LGPL code) and LGPL requires derivative works to keep the same license.[^register]
- Independent tech-press coverage (The Register) of the dispute, including the maintainer's own rebuttal using code-similarity tooling (JPlag) to argue near-zero structural overlap with prior versions.[^register]
- The rewriting maintainer's own detailed public account of the process, including an admission that "every time old chardet code entered Claude's active context during the rewrite, despite my instructions" not to look at it.[^blanchard]

Separately, `charset-normalizer`'s maintainers publicly dispute `chardet` 7's _accuracy_ claims on methodological grounds: they allege `chardet` imported `charset-normalizer`'s own test corpus to train/benchmark against and then reported superior accuracy on those same files, and that `chardet` 7 adopted `charset-normalizer`'s "decode-first validity filtering" and "encoding pairwise similarity" techniques without attribution.[^cn-readme] `chardet`'s own documentation, in turn, reports `chardet` 7.4.0 at 99.3% accuracy vs. `charset-normalizer` 3.4.6 at 85.4% on a 2,517-file suite drawn from `chardet`'s own test corpus (with `charset-normalizer`'s test files merged in and some manually relabeled/excluded by the `chardet` maintainer).[^chardet-perf] **Treat both accuracy numbers as self-reported by interested parties on a disputed dataset — neither is an independently audited, third-party benchmark**, and no such independent benchmark surfaced in this research pass. Combined with the unresolved relicensing dispute, this is sufficient reason on its own — independent of any accuracy question — not to introduce `chardet` into a public repository's dependency tree without an explicit owner-approved `OQ-` per §8.6.

No CVEs were found for either `charset-normalizer` or `chardet` in Snyk's database as of this research pass; one Snyk advisory ID nominally scoped to a SUSE `charset-normalizer` package (`SNYK-SLES154-PYTHON311CHARSETNORMALIZER-*`) describes a ReDoS in an unrelated "SQL parser" regular expression, which does not match anything in `charset-normalizer`'s actual codebase — flagging this as `[unverified]`/likely-mislabeled advisory metadata rather than a real finding.[^snyk-cn]

## 5. Recent Changes

- `charset-normalizer` 3.4.x line now ships `cp314`/`cp314t` (free-threaded) wheels across all major platforms as of 3.4.7 (2026-04).[^pypi-cn-files]
- `chardet` 7.x is a full rewrite (see §4): different architecture, `detect_all()`, `encoding_era=` filtering, `UniversalDetector` streaming, MIME-type detection for binary input, and a license change whose validity is actively disputed.[^chardet-faq]
- `faust-cchardet` last tagged release (2.1.19) has not published wheels beyond `cp312`; no evidence of a 3.13/3.14-compatible build found.[^faust-pypi-files]

## 6. Proposed Weird-Document Fixture Set (encoding-detection focus)

All fixtures below are synthetic, ASCII-derived, or public-domain-style text (no real library content, per C-002). Proposed additions to the §17.2 weird-document corpus, scoped to FR-007/FR-015:

| Fixture | Purpose | Notes |
| --- | --- | --- |
| `utf8_plain.txt`, `utf8_bom.txt` | Baseline EC-007 (BOM present/absent) | Confirm BOM stripped on write, decode identical either way. |
| `windows1252_smartquotes.txt` | Curly quotes, em-dash, `€` (bytes only defined in the 0x80–0x9F range under cp1252, undefined/control in Latin-1) | Exercises the genuine cp1252/ISO-8859-1 ambiguity zone noted by all three vendor comparisons.[^bytetunnels] |
| `latin1_c1_controls.txt` | Bytes in 0x80–0x9F used as C1 control codes rather than cp1252 printable characters | The "wrong-guess-either-way" counterpart to the fixture above. |
| `utf16le_bom.txt`, `utf16be_bom.txt`, `utf16_no_bom.txt` | UTF-16 variants; the no-BOM case is genuinely ambiguous (endianness must be inferred from null-byte parity) | No-BOM UTF-16 should skip-and-report rather than guess. |
| `utf32le_bom.txt`, `utf32be_bom.txt` | UTF-32 variants | Lower priority; rare in a legacy `.txt`/`.html` corpus but cheap to cover. |
| `shiftjis_greeting.txt`, `eucjp_greeting.txt`, `gb18030_greeting.txt`, `big5_greeting.txt`, `euckr_greeting.txt` | Short (~15–30 byte) CJK legacy greetings in five different legacy charsets | Directly targets "CJK legacy charsets" in the research question; short enough to test the non-ASCII-byte-count gate from §3. |
| `short_ascii_one_highbyte_tie.txt` | ~35–40 bytes, ASCII plus exactly one non-ASCII byte chosen to be simultaneously valid in cp1252/ISO-8859-1 and as half of a valid CJK double-byte pair | Reproduces the class of failure in GH issue #391 (§3) without copying the original issue's exact text — construct fresh synthetic wording. This is the concrete "short multi-charset tie" fixture the research question asked for. |
| `below_guard_16bytes.txt`, `at_guard_32bytes.txt`, `above_guard_38bytes.txt` | 16, 32, and 38-byte non-ASCII payloads straddling `TOO_SMALL_SEQUENCE = 32` | Pins the exact boundary behavior of the built-in small-sample penalty from §2, and demonstrates it does _not_ fire at 38 bytes. |
| `mixed_encoding_concatenated.txt` | First half UTF-8, second half Windows-1252 (simulating a poorly merged/concatenated legacy file) | Named as a known failure class for every detector by an independent comparison.[^bytetunnels] Expect low confidence and a skip. |
| `nul_bytes.bin_named.txt` | NUL bytes present, `.txt` extension | Already covered by EC-004; retained here to test its interaction with encoding detection (should short-circuit to "binary," not attempt decode). |
| `empty.txt` | Zero-byte file | Confirms detection code path does not raise on empty input (`from_bytes(b"")`). |

## Reconciliation notes

Fold these findings into:

- **`docs/specs/docmend.md` §9** — extend the `source.detected_encoding` example to note that `confidence` is defined as `1.0 - chaos` (not a chaos/coherence blend), and consider adding optional `chaos`/`coherence`/`language` diagnostic sub-fields for provenance (Appendix C.4).
- **`docs/specs/docmend.md` FR-007 / FR-015** — add the non-ASCII-byte-count floor as a second, distinct skip reason from "low confidence below threshold"; needs a new `OQ-` (no existing OQ-XXX covers this) recording the proposed default range (8–20 non-ASCII bytes, encoding-family-dependent) as **not yet validated** pending the real weird-document corpus.
- **`docs/specs/docmend.md` §17.2** — add the fixture set in §6 above to the weird-document corpus plan.
- **`docs/deep-research-queue.md`** — mark the "Encoding detection at corpus scale" candidate-topics row as promoted/answered, linking to this report.
- Before writing the new `OQ-`, note the pre-existing spec/open-questions drift already spotted in this codebase: `docs/open-questions.md` defines OQ-012, OQ-013, and OQ-014, but the spec's own §21 table stops at OQ-011 — those three are currently invisible to the spec of record. This report's new OQ (whatever number the owner assigns) should be added to **both** files together to avoid extending that drift.

## Sources

| URL | Title | Date | Authority |
| --- | --- | --- | --- |
| <https://github.com/jawah/charset_normalizer> | jawah/charset_normalizer README (performance, licensing dispute narrative) | accessed 2026-07-05 | [official] |
| <https://raw.githubusercontent.com/jawah/charset_normalizer/master/src/charset_normalizer/legacy.py> | `legacy.py` source — chardet-compat `detect()` confidence formula | `master` branch, accessed 2026-07-05 | [official] |
| <https://raw.githubusercontent.com/jawah/charset_normalizer/master/src/charset_normalizer/models.py> | `models.py` source — `CharsetMatch.chaos`/`.coherence`/`.percent_chaos` properties | `master` branch, accessed 2026-07-05 | [official] |
| <https://raw.githubusercontent.com/jawah/charset_normalizer/master/src/charset_normalizer/constant.py> | `constant.py` source — `TOO_SMALL_SEQUENCE = 32` | `master` branch, accessed 2026-07-05 | [official] |
| <https://charset-normalizer.readthedocs.io/en/latest/api.html> | Developer Interfaces — `CharsetMatch`/`CharsetMatches`/`detect()` API reference | v3.4.7 docs, accessed 2026-07-05 | [official] |
| <https://github.com/jawah/charset_normalizer/blob/master/docs/user/advanced_search.md> (via Context7) | Advanced byte-string detection — `from_bytes()` kwargs (`threshold`, `language_threshold`, etc.) | accessed 2026-07-05 | [official] |
| <https://github.com/jawah/charset_normalizer/issues/391> | "Detection and Tiny sequences" — documented short-text Big5 misdetection at confidence 1.0 | filed/accessed 2026-07-05 | [official] (project issue tracker) |
| <https://pypi.org/pypi/charset-normalizer/json> | PyPI JSON API — license, wheel tags (`cp314`, `cp314t`) | queried 2026-07-05 | [official] |
| <https://pypi.org/pypi/chardet/json> | PyPI JSON API — `license_expression: 0BSD`, wheel tags | queried 2026-07-05 | [official] |
| <https://pypi.org/pypi/faust-cchardet/json> | PyPI JSON API — license, wheel tags (max `cp312`) | queried 2026-07-05 | [official] |
| <https://chardet.readthedocs.io/en/latest/faq.html> | chardet FAQ — confidence caveats, `detect_all()`, era filtering, chardet-vs-others comparison | accessed 2026-07-05 | [official] |
| <https://chardet.readthedocs.io/en/latest/performance.html> | chardet performance page — self-reported accuracy/speed benchmark table | accessed 2026-07-05 | [official] (self-reported, disputed — see §4) |
| <https://github.com/chardet/chardet> | chardet README — 0BSD license note, comparison table | accessed 2026-07-05 | [official] |
| <https://www.theregister.com/software/2026/03/06/chardet-dispute-shows-how-ai-will-kill-software-licensing/> | "Chardet dispute shows how AI will kill software licensing" | 2026-03-06 | [community] (tech press) |
| <http://dan-blanchard.github.io/blog/chardet-rewrite-controversy> | "Everything Claude Saw: A Transparent Account of the Chardet v7 Rewrite" — maintainer's own account | accessed 2026-07-05 | [blog] (primary-party account) |
| <https://hsivonen.fi/chardetng/> | Henri Sivonen, "chardetng: A More Compact Character Encoding Detector for the Legacy Web" — independent non-ASCII-byte convergence data | accessed 2026-07-05 | [community] (independent detector author) |
| <https://bytetunnels.com/posts/charset-detection-python-chardet-cchardet-charset-normalizer> | Third-party comparison with reproducible short-string examples (cp1252 vs ISO-8859-1 ambiguity, mixed-encoding failure class) | accessed 2026-07-05 | [blog] |
| <https://packages.debian.org/sid/utils/uchardet> | Debian package description for `uchardet` (C library/CLI, LGPL-2.1) | accessed 2026-07-05 | [community] (distro packaging) |
| <https://github.com/TypesettingTools/uchardet> | uchardet upstream description (freedesktop.org project, C library + CLI) | accessed 2026-07-05 | [community] |
| <https://security.snyk.io/package/pip/charset-normalizer> | Snyk vulnerability database — no direct vulnerabilities found for `charset-normalizer` | accessed 2026-07-05 | [community] |

[^api]: <https://charset-normalizer.readthedocs.io/en/latest/api.html>

[^legacy]: <https://raw.githubusercontent.com/jawah/charset_normalizer/master/src/charset_normalizer/legacy.py>

[^constant]: <https://raw.githubusercontent.com/jawah/charset_normalizer/master/src/charset_normalizer/constant.py>

[^mess]: <https://charset-normalizer.readthedocs.io/en/latest/api.html> (Mess Detector section)

[^coherence]: <https://raw.githubusercontent.com/jawah/charset_normalizer/master/src/charset_normalizer/models.py>

[^issue391]: <https://github.com/jawah/charset_normalizer/issues/391>

[^chardetng]: <https://hsivonen.fi/chardetng/>

[^pypi-cn]: <https://pypi.org/pypi/charset-normalizer/json>

[^pypi-cn-files]: <https://pypi.org/pypi/charset-normalizer/json>

[^snyk-cn]: <https://security.snyk.io/package/pip/charset-normalizer>

[^chardet-faq]: <https://chardet.readthedocs.io/en/latest/faq.html>

[^chardet-perf]: <https://chardet.readthedocs.io/en/latest/performance.html>

[^pypi-chardet]: <https://pypi.org/pypi/chardet/json>

[^pypi-chardet-files]: <https://pypi.org/pypi/chardet/json>

[^register]: <https://www.theregister.com/software/2026/03/06/chardet-dispute-shows-how-ai-will-kill-software-licensing/>

[^blanchard]: <http://dan-blanchard.github.io/blog/chardet-rewrite-controversy>

[^cn-readme]: <https://github.com/jawah/charset_normalizer>

[^faust-pypi]: <https://pypi.org/project/faust-cchardet/>

[^faust-pypi-json]: <https://pypi.org/pypi/faust-cchardet/json>

[^faust-pypi-files]: <https://pypi.org/pypi/faust-cchardet/json>

[^uchardet-debian]: <https://packages.debian.org/sid/utils/uchardet>

[^uchardet-gh]: <https://github.com/TypesettingTools/uchardet>

[^bytetunnels]: <https://bytetunnels.com/posts/charset-detection-python-chardet-cchardet-charset-normalizer>
