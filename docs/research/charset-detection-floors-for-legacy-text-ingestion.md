# Charset Detection Floors for Legacy Text Ingestion

Date: 2026-07-05

## Executive summary

The strongest direct evidence I found for a **non-ASCII-byte floor** comes from Henri Sivonen’s evaluation of **chardetng**, which explicitly measures the number of non-ASCII bytes needed for the detector’s answer on a truncated prefix to match the answer on the full document. In that evaluation, **legacy CJK encodings reach document-length-equivalent accuracy at about 10 non-ASCII bytes**, while **most windows-1252 and windows-1251 cases reach it at about 20 non-ASCII bytes**; by **50 non-ASCII bytes** very few language/encoding combinations remain unconverged, and by **90** almost everything has settled, with some known outliers such as Hungarian and ISO-8859-2 Romanian remaining difficult. ICU’s own documentation is much broader but points in the same direction, saying detection works best with **at least a few hundred bytes** of text in mostly one language; ICU also notes that multi-byte and single-byte detection use different signals, with byte-pattern legality helping multi-byte encodings and language statistics carrying more of the load for single-byte encodings. [\[1\]](https://hsivonen.fi/chardetng/)

For your use case, the safest default is to **treat BOM and full-file UTF-8 validity as pre-checks that bypass legacy detection**, and then apply a **hard absolute floor** before trusting any legacy guess. For a corpus dominated by short English-language `.txt` files, the best one-size-fits-most default is: **if there is no BOM, the file is not strict-valid UTF-8, and** `non_ascii_bytes < 20`**, skip-and-report instead of accepting any legacy encoding**. That choice is intentionally conservative: it will false-skip some genuine tiny Latin-1 files and some genuinely short CJK snippets, but it sharply reduces the exact failure mode you described—tiny mostly-ASCII files receiving a high-confidence but wrong legacy guess. If you want a family-aware mode, a good split is **20 bytes for Western single-byte legacy** and **12 bytes for multi-byte CJK legacy**, with **Big5 optionally relaxed to 10**. [\[2\]](https://hsivonen.fi/chardetng/)

A **ratio floor should not be the primary gate**. The best direct published evidence is expressed in **absolute non-ASCII counts**, not ratios. A ratio can still be useful as a **secondary hardening rule** for long, overwhelmingly ASCII files, but the count should drive the accept/skip decision. A practical secondary rule is: for files of at least 4 KiB, if `non_ascii_ratio < 0.5%`, mark any accepted legacy result as **suspect** unless it is backed by a BOM or by strict UTF-8 validity. That ratio rule is an operational recommendation, not something directly specified by the detector literature. [\[3\]](https://hsivonen.fi/chardetng/)

## Bottom line and recommendation

For `docmend`, the default behavior I recommend is this:

1.  **BOM sniff first.** If the file begins with a recognized BOM, trust it and bypass legacy detection. The WHATWG Encoding Standard says the BOM is “more authoritative than anything else,” and Python’s Unicode codecs are designed around BOM-assisted decoding for UTF-16 and UTF-32. charset-normalizer’s legacy API also surfaces BOM-backed UTF-8 as `utf_8_sig`. [\[4\]](https://encoding.spec.whatwg.org/)

2.  **Run a strict full-file UTF-8 validity check next.** If the file is valid UTF-8 and contains at least one non-ASCII UTF-8 sequence, accept UTF-8 and bypass legacy detection. The Encoding Standard explicitly notes UTF-8’s highly detectable bit pattern, and browser/encoding discussions treat valid non-ASCII UTF-8 as strong positive evidence. For a finite local file, full-file validation is materially safer than incremental or prefix-only guessing. [\[5\]](https://bugzilla.mozilla.org/show_bug.cgi?id=815551)

3.  **If all bytes are ASCII, stop treating the file as a legacy-detection problem.** ASCII-only content is inherently ambiguous among ASCII-superset encodings, and both the literature and detector maintainers repeatedly note that near-ASCII text with only a few exceptions is where statistical detection is weakest. Treat ASCII-only as ASCII/UTF-8-compatible text, not as something that should be “detected” as Big5, Shift_JIS, or Latin-1. [\[6\]](https://cs229.stanford.edu/proj2007/KimPark-AutomaticDetectionOfCharacterEncodingAndLanguages.pdf)

4.  **If there is no BOM and the file is not valid UTF-8, enforce a hard legacy floor.**  
    **Default:** skip any legacy guess when `non_ascii_bytes < 20`.  
    **Family-aware alternative:** skip Western single-byte legacy when `non_ascii_bytes < 20`; skip CJK multi-byte legacy when `non_ascii_bytes < 12`, with an optional Big5-specific relaxation to `10`. [\[7\]](https://hsivonen.fi/chardetng/)

This default is tuned to your corpus, where the dominant risk is **false-accepting a wrong legacy encoding on short English text**. The tradeoff is straightforward:

- **False-accept risk:** much lower than trusting detector confidence alone on tiny samples. This is the main goal. [\[8\]](https://github.com/jawah/charset_normalizer/blob/master/README.md)
- **False-skip risk:** higher for genuinely short Latin-1 files with only a few accents, for very short CJK snippets, and for sparse long files with only a few non-ASCII bytes. That is acceptable here because the corpus is mostly short English `.txt`, and skip-and-report is safer than silently normalizing to the wrong text. [\[9\]](https://cs229.stanford.edu/proj2007/KimPark-AutomaticDetectionOfCharacterEncodingAndLanguages.pdf)

## Evidence from detector literature

The clearest published byte-count result is from Sivonen’s **“document-length-equivalent number of non-ASCII bytes”** metric for chardetng. He reports that **legacy CJK encodings** reach document-length-equivalent accuracy with **about 10 non-ASCII bytes**, while **most windows-1252 and windows-1251 languages** reach it with **about 20 non-ASCII bytes**. He further reports that at **50 non-ASCII bytes** very few language/encoding combinations have not fully converged, that almost everything settles by **90**, and that **Hungarian and ISO-8859-2 Romanian** remain special cases even at **1000** non-ASCII bytes. For your question, this is the best evidence-backed basis for a floor because it is explicitly expressed in the unit you want to gate on. [\[10\]](https://hsivonen.fi/chardetng/)

ICU’s own detector documentation is less granular but reinforces the same shape of problem. ICU says charset detection is “at best, an imprecise operation using statistics and heuristics,” that it works best with **at least a few hundred bytes** of text in mostly one language, and that for **multi-byte** encodings it uses a mix of **legal byte-pattern checks** and frequent-character checks, while for **single-byte** encodings it relies on frequent **three-letter groups** for each language. That matters because it explains why multi-byte CJK families often become distinguishable sooner than Western single-byte families: the byte-pattern legality itself carries signal. [\[11\]](https://unicode-org.github.io/icu/userguide/conversion/detection.html?utm_source=chatgpt.com)

The older Stanford evaluation of Mozilla’s detector helps explain why your tiny mostly-ASCII case goes wrong. That paper found Mozilla’s detector very accurate overall on its evaluation set, but also states that the **majority of errors** came from detecting **UTF-8 or ISO-8859-1 documents as US-ASCII**, precisely because many English files are mostly ASCII with only a few exceptional characters. It also emphasizes that the detector uses **different methods for multi-byte and single-byte charsets**, which again supports family-specific thresholds instead of a single notion of “confidence is enough.” [\[12\]](https://cs229.stanford.edu/proj2007/KimPark-AutomaticDetectionOfCharacterEncodingAndLanguages.pdf)

Sivonen’s chardetng write-up adds important family-level nuance. He says that **Big5 is structurally distinctive even with short inputs**, to the point that a frequency table for common Big5 Hanzi turned out to be unnecessary. By contrast, he says the differences between **EUC-JP, EUC-KR, and GBK** do **not necessarily show up in short titles**, and specifically notes that **GBK accuracy is bad with fewer than 6 hanzi**. That is the best direct evidence I found for setting Big5 slightly lower and GBK/GB18030 slightly higher than the generic CJK floor. [\[13\]](https://hsivonen.fi/chardetng/)

The detector ecosystem itself also documents the general short-input failure mode. charset-normalizer’s README says that every charset detector depends heavily on **sufficient content** and warns against very tiny content; issue trackers show failures on one-character and short-sample inputs; and the package changelog notes that **3.4.3** specifically began to **lower confidence on small non-Unicode byte samples** in the legacy `detect()` output. That change is itself evidence that small-sample overconfidence was a real-enough problem to warrant a versioned behavioral adjustment. [\[14\]](https://github.com/jawah/charset_normalizer/blob/master/README.md)

## Threshold model for docmend

### Per-family threshold table

The table below separates **observation** from **recommendation**. The observed counts come from published detector behavior where available, chiefly chardetng. The recommended floors are operational thresholds for a **skip-and-report** policy in a corpus dominated by short English `.txt` files.

| Encoding family | What the literature supports | Recommended minimum reliable non-ASCII bytes for `docmend` | Notes |
| --- | --: | --: | --- |
| Western single-byte legacy: windows-1252, ISO-8859 family | About **20** bytes for document-length-equivalent convergence in most windows-1252/windows-1251 cases; **50** is near-fully converged for almost all; some Central/Eastern European cases remain hard even at much higher counts. [\[10\]](https://hsivonen.fi/chardetng/) | **20** hard floor; optionally treat **50** as “high-confidence zone” | Best default for a conservative English-heavy corpus. Count alone still does **not** reliably separate cp1252 from ISO-8859 variants when bytes stay in shared ranges. [\[15\]](https://hsivonen.fi/chardetng/) |
| Big5 | Legacy CJK generally converges at about **10** non-ASCII bytes; Big5 is described as **structurally distinctive even with short inputs**. [\[16\]](https://hsivonen.fi/chardetng/) | **10** in family-aware mode; **20** under a single universal floor | If you want a simple single default, keep 20. If you want better CJK recall, Big5 can be safely lower than Western single-byte. [\[16\]](https://hsivonen.fi/chardetng/) |
| Shift_JIS / Windows-31J / cp932 | Legacy CJK generally converges at about **10** non-ASCII bytes, but short-input CJK scaling is acknowledged as weaker than ced in some cases. Japanese detection is special-cased in Firefox because it matters operationally. [\[17\]](https://hsivonen.fi/chardetng/) | **12** in family-aware mode; **20** under a single universal floor | Treat `cp932` and Shift_JIS-family outcomes as acceptable siblings in tests, not as fundamentally different ground truths. Windows-31J is commonly declared as Shift_JIS in practice. [\[18\]](https://www.iana.org/assignments/charset-reg/windows-31J?utm_source=chatgpt.com) |
| GBK / GB18030 / Simplified Chinese legacy | Generic CJK convergence is about **10** non-ASCII bytes, but **GBK is bad with fewer than 6 hanzi**, which is roughly **12 non-ASCII bytes** for 2-byte characters. The GBK decoder is the same as GB18030 for decoding in the web-compatible model. [\[19\]](https://hsivonen.fi/chardetng/) | **12** in family-aware mode; **20** under a single universal floor | If you evaluate detector correctness for ingestion, accept **GBK/GB18030-family equivalence** unless your own codec policy distinguishes the encoder side. [\[20\]](https://docs.rs/encoding_rs/latest/encoding_rs/static.GBK.html?utm_source=chatgpt.com) |
| EUC-JP / EUC-KR / related EUC CJK families | Generic CJK convergence is about **10** non-ASCII bytes, but Sivonen notes that **differences may not show up in short titles** for EUC-JP, EUC-KR, and GBK. [\[7\]](https://hsivonen.fi/chardetng/) | **12** in family-aware mode; **20** under a single universal floor | These are more structurally informative than Western single-byte encodings, but not as forgiving as Big5 on tiny samples. [\[21\]](https://hsivonen.fi/chardetng/) |

### Count versus ratio

**Observation.** The best direct evidence is based on **absolute non-ASCII counts**, not on ratios. chardetng’s published convergence numbers are explicitly about the number of **non-ASCII bytes** required to match full-document results. ICU and chardet speak in terms of “a few hundred bytes” of text rather than percentage density. [\[22\]](https://hsivonen.fi/chardetng/)

**Observation.** Ratio still matters operationally for long, overwhelmingly ASCII files. uchardet maintainers explicitly discuss cases where a file is hundreds of lines of ASCII with only a few late exceptions, and they emphasize that **the whole file must be fed** because “the more, the better,” especially for single-byte legacy encodings that are statistics-based and share many code points. They also note that validity testing alone is a poor discriminator because many single-byte encodings accept the same bytes. [\[23\]](https://bugzilla.gnome.org/show_bug.cgi?id=669448)

**Inference.** For `docmend`, the **hard skip gate should be count-based**, because that is what the best direct evidence supports. A **ratio** is still useful, but mainly as a **secondary hardening signal** for extremely sparse cases, not as the primary rule. [\[3\]](https://hsivonen.fi/chardetng/)

**Recommendation.** Use this policy:

- **Primary hard gate:** `non_ascii_bytes >= 20` before trusting any non-Unicode legacy guess.
- **Optional family-aware mode:** Western single-byte `>= 20`; CJK multi-byte `>= 12`; Big5 `>= 10`.
- **Optional sparse-file hardening:** if `total_bytes >= 4096` and `non_ascii_ratio < 0.005`, downgrade any accepted legacy result to **suspect** and prefer skip-and-report unless a stronger signal exists.

That ratio threshold is a conservative engineering choice, not a literature-derived constant. It is there to catch the “one smart quote in a sea of ASCII” class of files, not to replace the count gate. [\[24\]](https://bugzilla.gnome.org/show_bug.cgi?id=669448)

### BOM and UTF-8 validity interaction

**Observation.** BOMs are a stronger signal than detector confidence. The WHATWG Encoding Standard says BOMs are more authoritative than anything else in the sniffing process and defines BOM sniffing for UTF-8, UTF-16BE, and UTF-16LE. Python’s Unicode docs describe BOM-assisted autodetection for UTF-16 and UTF-32, and charset-normalizer’s legacy wrapper maps a BOM-backed UTF-8 result to `utf_8_sig`. [\[4\]](https://encoding.spec.whatwg.org/)

**Observation.** Strict UTF-8 validity is the right second pre-check for finite local files. The Encoding discussion inside Mozilla notes that UTF-8 has a highly detectable bit pattern, but Sivonen also warns that incremental or prefix-only UTF-8 autodetection is brittle on mostly-ASCII English text because success can depend on how soon the first non-ASCII punctuation appears. That warning argues for **full-file** UTF-8 validation, not for skipping the UTF-8 check entirely. [\[25\]](https://bugzilla.mozilla.org/show_bug.cgi?id=815551)

**Recommendation.** The floor should apply **only after** BOM sniffing and strict full-file UTF-8 validation fail. If the bytes are pure ASCII, do not attempt legacy-family inference at all. If they are valid UTF-8 with non-ASCII sequences, accept UTF-8. Only files that are **not BOM-backed and not valid Unicode** should reach the legacy floor. [\[26\]](https://encoding.spec.whatwg.org/)

## Synthetic fixture design

A reproducible fixture set should be **algorithmic**, cover both **false accepts** and **false skips**, and vary three independent axes: **total length**, **non-ASCII byte count**, and **placement** of the informative bytes. That lets you test both the gate and the detector independently, while staying within your synthetic-or-public-domain constraint. The recipe below is enough to validate the proposed floors without using private content. [\[3\]](https://hsivonen.fi/chardetng/)

### Fixture families

Use a generator that starts from **synthetic English ASCII scaffolding**, then injects target-script or target-byte tokens at controlled counts and positions.

| Fixture class | Purpose | Parameters |
| --- | --- | --- |
| Tiny mostly-ASCII false-accept set | Reproduce wrong high-confidence legacy guesses on tiny samples | `total_bytes ∈ {24, 32, 38, 48, 64}`; `non_ascii_bytes ∈ {1, 2, 4, 6, 8}`; placement `{front, middle, tail}` |
| Western single-byte boundary set | Find the skip/accept boundary for cp1252 / ISO-8859 family | `total_bytes ∈ {64, 128, 256, 512, 1024}`; `non_ascii_bytes ∈ {2, 4, 8, 12, 16, 20, 30, 50}` |
| CJK boundary set | Find the skip/accept boundary for Shift_JIS, Big5, GB18030, EUC-JP, EUC-KR | `total_bytes ∈ {32, 64, 128, 256, 512, 1024}`; `non_ascii_bytes ∈ {4, 6, 8, 10, 12, 16, 20}` |
| Sparse long-file set | Test the ratio hardening and whole-file behavior | `total_bytes ∈ {4096, 8192, 16384}`; `non_ascii_bytes ∈ {4, 8, 12, 20, 30}`; placement should emphasize tail-loaded exceptions |
| BOM / Unicode pre-check set | Verify bypass rules | UTF-8 BOM, UTF-16LE BOM, UTF-16BE BOM, strict-valid UTF-8 without BOM, ASCII-only |

### Content recipe

For the ASCII scaffold, use deterministic synthetic English text such as repeated sentence templates or a generated word list. For example, build lines from a small public-domain-safe vocabulary such as “report”, “system”, “status”, “normal”, “warning”, “chapter”, “appendix”, and similar ordinary English tokens. This keeps the base text stable while avoiding any copyrighted corpus dependence.

For injected tokens:

- **Western single-byte:** use characters that map cleanly into the target encoding and are known to matter operationally, such as `é`, `ö`, `ñ`, `ü`, NBSP, and typographic punctuation for cp1252-like data. Include cases where the informative bytes are only in the cp1252-differentiating area as well as cases where they sit entirely in the shared upper-half range, because the latter are much harder to distinguish cleanly. [\[27\]](https://encoding.spec.whatwg.org/?utm_source=chatgpt.com)
- **Shift_JIS / EUC-JP:** use short mixtures of kana, kanji, and ASCII, because Sivonen specifically notes that short CJK samples do not always surface family differences, and Japanese detection often depends on kana as well as byte legality. [\[28\]](https://hsivonen.fi/chardetng/)
- **Big5 / GB18030:** use short Han-only and Han-plus-ASCII variants. Include **5-hanzi** and **6-hanzi** cases specifically for GBK/GB18030 because the published short-input weakness is “fewer than 6 hanzi.” [\[29\]](https://hsivonen.fi/chardetng/)
- **EUC-KR:** use Hangul-heavy tokens with surrounding ASCII, because the detector literature notes that short-title distinctions among EUC-KR, EUC-JP, and GBK may not show up immediately. [\[21\]](https://hsivonen.fi/chardetng/)

### Boundary cases to include explicitly

#### False-accept fixtures

- A **~38-byte mostly-ASCII file** with only **2–4 non-ASCII bytes**, designed so the byte sequence is invalid UTF-8 but legal in one or more CJK legacy encodings. This is the class of sample that can provoke “chaos 0.0 / confidence 1.0” style overtrust on the wrong family. The exact byte pattern can be generated by selecting a desired wrong-family-valid pair and embedding it in otherwise ASCII English. [\[30\]](https://charset-normalizer.readthedocs.io/en/3.4.1/_modules/charset_normalizer/legacy.html)
- A **single-character** Latin-1 fixture such as one encoded `ü`, because charset-normalizer has a documented short-input failure case there. [\[31\]](https://github.com/jawah/charset_normalizer/issues/486?utm_source=chatgpt.com)
- An **ASCII-plus-late-NBSP** long fixture, with the non-ASCII bytes only near the end, to verify that the gate works on whole-file counts rather than prefix-biased behavior. This is explicitly similar to the uchardet/GtkSourceView bug discussion. [\[23\]](https://bugzilla.gnome.org/show_bug.cgi?id=669448)

#### False-skip fixtures

- Genuine cp1252 / ISO-8859 fixtures with **8**, **12**, **16**, and **20** non-ASCII bytes scattered through short English text. These tell you exactly how many real short Western files your chosen floor will sacrifice.
- Genuine CJK fixtures with **4**, **6**, **8**, **10**, **12**, and **16** non-ASCII bytes, especially **5- and 6-character** Han variants for GB18030-family tests. That validates whether the family-aware 12-byte floor is worth it in your corpus. [\[32\]](https://hsivonen.fi/chardetng/)

### Fixture evaluation protocol

For each generated file, record:

- raw length in bytes
- non-ASCII byte count
- non-ASCII byte ratio
- BOM present or absent
- strict UTF-8 validity
- detector outputs from at least charset-normalizer and one independent detector family such as ICU or uchardet/chardetng where practical
- whether detection is counted as **exactly correct**, **family-equivalent**, **wrong**, or **skipped by policy**

Treat these as **family-equivalent** for evaluation unless your own decoding policy needs stricter separation:

- `cp932` / `windows-31j` / `shift_jis` family as one acceptable Japanese family outcome on decode-focused ingestion. [\[18\]](https://www.iana.org/assignments/charset-reg/windows-31J?utm_source=chatgpt.com)
- `gbk` / `gb18030` as one acceptable Simplified Chinese family outcome on the decoder side. [\[20\]](https://docs.rs/encoding_rs/latest/encoding_rs/static.GBK.html?utm_source=chatgpt.com)

Your final floor should be chosen from the boundary plot where **false accepts collapse sharply** while the **remaining false skips** are acceptable for manual review. In your corpus, that decision point is likely to be the conservative **20-byte universal floor**, with the **12-byte CJK override** available if short true CJK content matters enough to justify the added complexity. [\[16\]](https://hsivonen.fi/chardetng/)

## Version and date sensitivity

The most important version fact is that **charset-normalizer 3.x behavior changed during the 3.4 series in ways directly relevant to your question**. The project changelog says **3.4.2** “improved the overall reliability of the detector with CJK Ideographs,” which means any CJK-specific threshold work must be validated on at least 3.4.2+, not on early 3.4.0 behavior. It also says **3.4.3** began to **automatically lower confidence on small bytes samples that are not Unicode** in the legacy `detect()` output, which is directly relevant if you currently consume `detect()`’s `confidence = 1.0 - chaos`. Current PyPI metadata shows **3.4.7** as the current 3.x release and lists explicit **Python 3.14** support. [\[33\]](https://github.com/jawah/charset_normalizer/blob/master/CHANGELOG.md)

The `detect()` API itself is a compatibility wrapper. The official docs show that its `confidence` field is computed as `1.0 - r.chaos`, that it calls `from_bytes(...).best()`, and that BOM-backed UTF-8 is surfaced as `utf_8_sig`. If you are building production policy around a `confidence` threshold, that policy is exposed to version-to-version changes in how `chaos` is scored and in how small-sample confidence is damped. That is another reason a separate byte-count gate is the right design: it is simple, explainable, and version-stable. [\[34\]](https://charset-normalizer.readthedocs.io/en/3.4.1/_modules/charset_normalizer/legacy.html)

On the Python side, **Python 3.14** is supported by charset-normalizer 3.4.3+ and 3.4.7 publishes CPython 3.14 wheels. But Python itself is in the middle of an encoding-default transition: the 3.14 docs still describe **UTF-8 Mode** as a mode-dependent behavior for text I/O, while the official **What’s New in Python 3.15** says Python is moving to use UTF-8 as the default encoding independent of the environment. For `docmend`, the stable choice is to keep all ingest logic on **explicit binary reads plus explicit decode decisions** rather than relying on ambient `open()` defaults. [\[35\]](https://pypi.org/project/charset-normalizer/)

## Sources

- Henri Sivonen, **chardetng: A More Compact Character Encoding Detector for the Legacy Web** — especially the sections on title-length accuracy, document-length-equivalent non-ASCII bytes, and CJK short-input behavior. [\[36\]](https://hsivonen.fi/chardetng/?utm_source=chatgpt.com)
- ICU User Guide, **Charset Detection** — detector caveats, “few hundred bytes” guidance, and the distinction between single-byte and multi-byte detection methods. [\[11\]](https://unicode-org.github.io/icu/userguide/conversion/detection.html?utm_source=chatgpt.com)
- Kim and Park, **Automatic Detection of Character Encoding and Language** — Mozilla detector summary and the near-ASCII ambiguity findings. [\[37\]](https://cs229.stanford.edu/proj2007/KimPark-AutomaticDetectionOfCharacterEncodingAndLanguages.pdf)
- WHATWG **Encoding Standard** — BOM authority and UTF-8 decode rules. [\[38\]](https://encoding.spec.whatwg.org/)
- Python documentation, **codecs** and **Unicode HOWTO** — BOM behavior in Python; official Python 3.14 docs and 3.15 encoding-default note. [\[39\]](https://docs.python.org/3/library/codecs.html?utm_source=chatgpt.com)
- charset-normalizer documentation and changelog — `confidence = 1 - chaos`, BOM handling, tiny-content limitation, CJK reliability changes, small-sample confidence lowering, Python 3.14 support. [\[40\]](https://charset-normalizer.readthedocs.io/en/3.4.1/_modules/charset_normalizer/legacy.html)
- GNOME / uchardet discussion — full-file processing, sparse late non-ASCII failures, and why count-based whole-file policy is safer than prefix-based heuristics for single-byte encodings. [\[23\]](https://bugzilla.gnome.org/show_bug.cgi?id=669448)
- WHATWG / encoding_rs / IANA references for family-equivalent decoding outcomes such as GBK vs GB18030 and Windows-31J vs Shift_JIS. [\[41\]](https://docs.rs/encoding_rs/latest/encoding_rs/static.GBK.html?utm_source=chatgpt.com)

---

[\[1\]](https://hsivonen.fi/chardetng/) [\[2\]](https://hsivonen.fi/chardetng/) [\[3\]](https://hsivonen.fi/chardetng/) [\[7\]](https://hsivonen.fi/chardetng/) [\[10\]](https://hsivonen.fi/chardetng/) [\[13\]](https://hsivonen.fi/chardetng/) [\[15\]](https://hsivonen.fi/chardetng/) [\[16\]](https://hsivonen.fi/chardetng/) [\[17\]](https://hsivonen.fi/chardetng/) [\[19\]](https://hsivonen.fi/chardetng/) [\[21\]](https://hsivonen.fi/chardetng/) [\[22\]](https://hsivonen.fi/chardetng/) [\[28\]](https://hsivonen.fi/chardetng/) [\[29\]](https://hsivonen.fi/chardetng/) [\[32\]](https://hsivonen.fi/chardetng/) chardetng: A More Compact Character Encoding Detector for the Legacy Web

<https://hsivonen.fi/chardetng/>

[\[4\]](https://encoding.spec.whatwg.org/) [\[26\]](https://encoding.spec.whatwg.org/) [\[38\]](https://encoding.spec.whatwg.org/) Encoding Standard

<https://encoding.spec.whatwg.org/>

[\[5\]](https://bugzilla.mozilla.org/show_bug.cgi?id=815551) [\[25\]](https://bugzilla.mozilla.org/show_bug.cgi?id=815551) 815551 - Autodetect UTF-8 by default

<https://bugzilla.mozilla.org/show_bug.cgi?id=815551>

[\[6\]](https://cs229.stanford.edu/proj2007/KimPark-AutomaticDetectionOfCharacterEncodingAndLanguages.pdf) [\[9\]](https://cs229.stanford.edu/proj2007/KimPark-AutomaticDetectionOfCharacterEncodingAndLanguages.pdf) [\[12\]](https://cs229.stanford.edu/proj2007/KimPark-AutomaticDetectionOfCharacterEncodingAndLanguages.pdf) [\[37\]](https://cs229.stanford.edu/proj2007/KimPark-AutomaticDetectionOfCharacterEncodingAndLanguages.pdf) cs229.stanford.edu

<https://cs229.stanford.edu/proj2007/KimPark-AutomaticDetectionOfCharacterEncodingAndLanguages.pdf>

[\[8\]](https://github.com/jawah/charset_normalizer/blob/master/README.md) [\[14\]](https://github.com/jawah/charset_normalizer/blob/master/README.md) charset_normalizer/README.md at master · jawah/charset_normalizer · GitHub

<https://github.com/jawah/charset_normalizer/blob/master/README.md>

[\[11\]](https://unicode-org.github.io/icu/userguide/conversion/detection.html?utm_source=chatgpt.com) Charset Detection \| ICU Documentation

<https://unicode-org.github.io/icu/userguide/conversion/detection.html?utm_source=chatgpt.com>

[\[18\]](https://www.iana.org/assignments/charset-reg/windows-31J?utm_source=chatgpt.com) windows-31J

<https://www.iana.org/assignments/charset-reg/windows-31J?utm_source=chatgpt.com>

[\[20\]](https://docs.rs/encoding_rs/latest/encoding_rs/static.GBK.html?utm_source=chatgpt.com) [\[41\]](https://docs.rs/encoding_rs/latest/encoding_rs/static.GBK.html?utm_source=chatgpt.com) GBK in encoding_rs - Rust

<https://docs.rs/encoding_rs/latest/encoding_rs/static.GBK.html?utm_source=chatgpt.com>

[\[23\]](https://bugzilla.gnome.org/show_bug.cgi?id=669448) [\[24\]](https://bugzilla.gnome.org/show_bug.cgi?id=669448) Bug 669448 – Use universal encoding auto-detection (e.g. universalchardet by mozilla)

<https://bugzilla.gnome.org/show_bug.cgi?id=669448>

[\[27\]](https://encoding.spec.whatwg.org/?utm_source=chatgpt.com) Encoding Standard

<https://encoding.spec.whatwg.org/?utm_source=chatgpt.com>

[\[30\]](https://charset-normalizer.readthedocs.io/en/3.4.1/_modules/charset_normalizer/legacy.html) [\[34\]](https://charset-normalizer.readthedocs.io/en/3.4.1/_modules/charset_normalizer/legacy.html) [\[40\]](https://charset-normalizer.readthedocs.io/en/3.4.1/_modules/charset_normalizer/legacy.html) charset_normalizer.legacy - charset_normalizer 3.4.0 documentation

<https://charset-normalizer.readthedocs.io/en/3.4.1/_modules/charset_normalizer/legacy.html>

[\[31\]](https://github.com/jawah/charset_normalizer/issues/486?utm_source=chatgpt.com) \[DETECTION\] fails on short input · Issue \#486

<https://github.com/jawah/charset_normalizer/issues/486?utm_source=chatgpt.com>

[\[33\]](https://github.com/jawah/charset_normalizer/blob/master/CHANGELOG.md) charset_normalizer/CHANGELOG.md at master · jawah/charset_normalizer · GitHub

<https://github.com/jawah/charset_normalizer/blob/master/CHANGELOG.md>

[\[35\]](https://pypi.org/project/charset-normalizer/) charset-normalizer · PyPI

<https://pypi.org/project/charset-normalizer/>

[\[36\]](https://hsivonen.fi/chardetng/?utm_source=chatgpt.com) chardetng: A More Compact Character Encoding Detector ...

<https://hsivonen.fi/chardetng/?utm_source=chatgpt.com>

[\[39\]](https://docs.python.org/3/library/codecs.html?utm_source=chatgpt.com) Codec registry and base classes

<https://docs.python.org/3/library/codecs.html?utm_source=chatgpt.com>
