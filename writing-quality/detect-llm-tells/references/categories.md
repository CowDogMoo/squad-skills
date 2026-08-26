# Reference: 8 tell categories

Load this file from SKILL.md when scoring a unit. The cluster-scoring
rule lives in SKILL.md; the catalog of which patterns count toward
which category lives here.

## 1. Telltale Vocabulary

Frequency data from corpus analysis: Kobak et al. (Science Advances, 2025) analyzed 15M PubMed abstracts; PMC12679996 (2025) analyzed 135 AI-influenced terms; GPTZero (2026) analyzed 3.3M texts. COLING 2025 identified RLHF (not training data or architecture) as the primary cause of vocabulary skew.

### Tier 1 — Strongest signals (10x+ overrepresentation in LLM text)

These words appear in LLM output at 10-50x the rate of human writing. Any ONE of these in a unit is enough to fire the vocabulary category; two or more makes it a strong signal.

- **"delve"** — 40x overrepresented in early GPT-4 (2023-2024); dropped to ~8x by mid-2025 after widespread mockery. Still a strong signal in older or untuned outputs.
- **"tapestry"** — ~25x overrepresented. Almost never appears in technical documentation written by humans.
- **"testament"** — ~20x. "This is a testament to..." is a near-certain LLM construction in technical contexts.
- **"vibrant"** — ~15x. Humans use it for colors; LLMs use it for communities, ecosystems, and discussions.
- **"underscore" / "underscores"** — 13.8x (Kobak). "This underscores the importance of..." is a stock LLM construction.
- **"foster"** — ~12x. "Foster collaboration/innovation/growth" is a signature LLM phrase.
- **"showcasing"** — 10.7x (Kobak). Rare in human technical writing.
- **"intricate"** — ~10x. Used by LLMs to describe anything with more than two moving parts.

### Tier 2 — Strong signals (5-10x overrepresentation)

Require 2+ in the same unit before this fires the category.

- **"crucial," "pivotal," "essential"** — LLMs over-qualify importance. Humans say "important" or just let the context speak.
- **"landscape"** (non-geographic) — "the AI landscape," "the threat landscape." ~7x overrepresented in non-geographic contexts.
- **"comprehensive"** — In Kobak's 10-word marker set. "Gain a comprehensive understanding" appears at 120x frequency (GPTZero). Strong signal in technical docs.
- **"meticulous"** — ~6x. "Meticulous attention to detail" is a stock LLM phrase.
- **"particularly"** — In Kobak's 10-word marker set. Humans use it but LLMs cluster it far more densely.
- **"notably"** — In Kobak's 10-word marker set. "Notably, this approach..." is a classic LLM transition-into-emphasis.
- **"noteworthy"** — Validated by PMC study. Part of the LLM significance-inflation pattern.
- **"enhance," "bolster"** — ~5-6x each.

### Tier 3 — Moderate signals (3-5x overrepresentation)

Common in human writing too but appear more often in LLM output. Only count when 2+ cluster in a single unit.

- **Filler verbs**: "leverage," "unlock," "navigate," "harness," "embark," "utilize," "facilitate," "streamline," "spearhead," "ensure," "exhibit"
- **Generic nouns**: "ecosystem," "framework," "dynamic," "interplay," "synergy," "paradigm," "insights"
- **Dramatic openers**: "unleash the power of," "at the forefront of," "pave the way for," "bridging the gap between," "in the realm of"
- **Emphasis adverbs**: "primarily," "particularly" (when clustered), "especially," "significantly"

### Era-specific shifts

LLM vocabulary tells evolve as models are updated and fine-tuned:

- **2023 (early GPT-4)**: "delve," "tapestry," "testament," "vibrant" at peak frequency. "Certainly!" and "Great question!" as openers.
- **2024 (GPT-4-turbo, Claude 3)**: "delve" usage drops ~60% after public awareness. "Crucial," "landscape," "foster" remain strong. Claude introduces "I'd be happy to" as a signature opener.
- **2025 (GPT-4o, Claude 3.5/4)**: Models trained to suppress the most mocked words. "Delve" rare. But "foster," "enhance," "streamline" persist. New tells emerge: "straightforward," "robust," "seamless." RLHF identified as the primary driver of vocabulary tells (COLING 2025: Llama-2-Chat with RLHF showed 267-6697% increases in focal words vs Llama-2-Base without RLHF).
- **2026 (current)**: Watch for: "comprehensive," "walkthrough," "hands-on," "step-by-step" in contexts where humans would just write instructions without labeling them. LLM buzzwords entering everyday human speech (FSU 2025 study) means individual word tells are becoming less reliable — cluster scoring (3+ tells) is more important than ever.

## 2. Structural Patterns

- **Rule of Three**: AI defaults to grouping things in triplets (adjectives, benefits, examples) with unnatural consistency. In human writing, lists of 2, 4, or 5 are equally common. A document where every bullet list has exactly 3 items is suspicious.
  - **Threshold**: 3+ triplet lists in a single document, or a triplet pattern in >50% of bullet lists.
  - **Example**: "fast, reliable, and scalable" / "simplicity, power, and flexibility" / "developers, teams, and organizations" — three triplets in one page is a strong structural signal.
- **Negative parallelism / "Not X, but Y"**: Variations of "not just X, but Y" appeared in ~6% of LLM messages in one dataset vs <0.5% in human writing — a 12x overrepresentation. Identified as "the single most commonly identified AI writing tell" (tropes.fyi). Also includes "It's not X — it's Y" constructions.
- **False ranges**: "From intimate gatherings to global movements" implies a spectrum where none exists. LLMs use this to sound comprehensive without saying anything specific.
- **Mathematically even cadence**: Paragraphs follow textbook patterns, transitions are frictionless, sentence lengths are suspiciously uniform (typically 15-25 words per sentence with low variance). Human writing has higher variance — short punchy sentences mixed with long complex ones.
  - **Threshold**: Compute the coefficient of variation (CV) of sentence lengths in a paragraph. CV < 0.25 across 5+ sentences is suspicious. Human prose typically has CV > 0.35.
- **Formulaic section structure**: Neat headers, bullet points, and parallel constructions throughout. Every section follows the same pattern: topic sentence, 3 bullets, concluding sentence.
- **Bold-first bullets**: Every list item starting with bolded text is a hallmark of AI markdown formatting. Human bullet lists rarely bold the first word of every item.
- **Fractal summaries**: Introductions, section headers, and conclusions all restate the same content at different zoom levels. Humans write forward; LLMs summarize recursively.
- **Suspiciously balanced pros/cons**: When listing advantages and disadvantages, LLMs tend to produce exactly equal numbers of each. Humans are usually biased toward one side.
- **Numbered step/phase labels in comments**: LLMs impose sequential numbering on code comments: "Step 1:", "Step 2:", "Phase 1:", "Phase 2:" etc. Human developers use function decomposition for multi-step logic — they don't write numbered roadmaps through a function body. Variants include `Step N:`, `Phase N:`, `Step N/M:`, `Step N of M:`, `Phase N —`, and bare `Step N` without a colon.
  - **Threshold**: A single numbered step/phase label in a code comment is a moderate signal. Two or more in sequence is a strong structural signal — near-certain LLM output.
  - **NOT a signal**: User-facing output strings, log messages, and progress indicators that show step numbers to end users. Format strings like `format!("Step 1/2: Connecting")` or `fmt.Sprintf("Step 1/2: Connecting")` are code, not comments — never touch these.

## 3. Punctuation and Formatting

- **Em dash overuse**: LLMs use em dashes (—) at 3-5x the rate of typical human technical writers. Often appears where commas, parentheses, or colons would be more natural. Claude in particular is known for heavy em-dash usage — it is Claude's most distinctive formatting tell.
  - **Threshold**: More than 2 em dashes per 500 words of prose in a technical document is elevated. More than 4 per 500 words is a strong signal.
  - **Exception**: Some human writers (especially those influenced by journalism or literary nonfiction) use em dashes heavily. Check whether the frequency is consistent across the whole document or concentrated in specific sections.
- **Markdown in non-Markdown contexts**: Fenced code blocks or Markdown syntax (bold, headers, links) appearing in plain text files, emails, or contexts where Markdown is not rendered.
- **Overly clean formatting**: Perfect consistency in bullet styles, heading levels, and whitespace throughout a long document. Human-written docs accumulate inconsistencies over time as multiple people edit them.
- **Exclamation mark avoidance**: LLMs in "professional" mode almost never use exclamation marks. Human technical writers occasionally do, especially in warnings, tips, or informal docs.

## 4. Tone and Register

- **HR-speak friendliness**: "It's understandable that...," "Great question!," gentle summarizing endings ("Ultimately...," "In conclusion..."). This register is appropriate in customer support but jarring in technical documentation.
  - **Example**: "We understand that getting started can feel overwhelming, but rest assured that..." — no human engineer writes this in a README.
- **Hedging padding**: "It's worth noting," "it's important to remember," "one might argue," "it should be mentioned that" add nothing but word count. In a 500-word section, 3+ hedging phrases is a strong signal.
  - **Threshold**: Count hedging phrases per 500 words. Human baseline: 0-1. LLM typical: 3-6.
- **Overemphasis of importance**: Everything is "fascinating," "captivating," "remarkable," or "a pivotal moment." When every feature is "crucial" and every update is "exciting," nothing actually stands out.
- **Emotional flatness**: Text reads as polished but objective; lacks the subjective punctuation patterns (exclamation marks, ellipses, rhetorical questions, parenthetical asides) that humans naturally use. The voice never wavers, never shows frustration or humor.
- **Compulsive revision, no improvisation**: Reads like it was endlessly edited but never spontaneous. Every sentence is grammatically perfect. Human first drafts (even published ones) have rough edges.
- **Uniform register across topics**: LLMs maintain the same level of formality whether describing a critical security patch or a minor whitespace fix. Humans naturally shift register based on stakes.
- **"Despite its challenges..." formula**: Rigid acknowledgment of problems immediately dismissed with optimism. LLMs rarely let a negative point stand without a "however" or "that said" pivot.
- **Promotional / pitch register**: Sales vocabulary in what should be a technical document: "big win," "high-value," "unlock," "game-changing," "best-in-class," "empowers," "opportunity," "prime real estate," "takes it to the next level." Distinct from Overemphasis above — overemphasis inflates *importance* ("crucial," "remarkable"); promotional register borrows the *sales frame*: benefits, wins, value, and a closing ask. LLMs default to it whenever a document describes a product, project, or capability.
  - **Threshold**: diffuse by nature — typically one hype word per paragraph, so it rarely fires as a per-unit category and is easy to miss with paragraph-only scoring. Count it across the whole document: 4+ promotional terms per 1000 words, or any call-to-action closer ("start experimenting today," "give it a try," "reach out to learn more"), is a document-level signal. See "Document-level patterns" below.
- **Editorializing your own evidence**: "the results are strong," "a staggering amount of waste," "impressively fast" placed right before or after the actual numbers. Writers who trust their data present it unadorned; LLMs attach an adjective telling the reader how to feel about a measurement that already speaks for itself. One instance is weak; three across a document that reports real numbers is a reliable signal.

## 5. Transitional Phrases

Overuse of formal transitions. In human technical writing, most paragraphs start with the subject or a short connector ("But," "So," "Also,"). LLMs default to academic-style transitions:

**High-signal transitions** (rare in human tech docs, common in LLM output):

- "Moreover," "Furthermore," "Additionally," "Indeed," "Notably," "Consequently," "Subsequently," "Accordingly," "Conversely"

**Medium-signal transitions** (used by humans too, but at lower density):

- "It is worth noting," "In terms of," "With regard to," "In light of," "As such," "To that end," "In particular"

**Threshold**: More than 2 high-signal transitions per 500 words is suspicious. More than 4 is a strong signal. Count only prose paragraphs, not bullet lists or headers.

**Not a signal**: "However," "For example," "That said," "In practice" — these are common in both human and LLM writing.

## 6. Technical Documentation-Specific Tells

- **"Correct but useless" descriptions**: Restating what the code does without explaining why. "The `processData` function processes the data" tells the reader nothing they could not see from the function name.
  - **Example of LLM-style**: "This function takes a configuration object and returns a validated configuration." (just restates the signature)
  - **Example of human-style**: "Validates config before the server starts — catches typos in field names that would otherwise cause a cryptic panic 30 seconds into startup."
- **Missing business context**: The "why" behind decisions is absent; only the "what" is documented. LLMs describe mechanisms well but cannot explain motivations they were never told.
- **Knowledge-cutoff disclaimers**: Statements that information is accurate "as of" a certain date, or "at the time of writing." Humans rarely add these to project docs.
- **Suspiciously complete boilerplate**: Perfect JSDoc/docstrings that describe parameters mechanically but add no insight beyond what the type signature already says.
- **Generic README prose under standard headers**: Standard section headers like "Installation," "Usage," "Contributing," and "License" are human convention — virtually every project uses them, and their presence is NOT a tell. The signal is in the **prose under those headers**: if the Installation section says "Getting started is straightforward — simply follow these steps to leverage the full potential of this framework," that is LLM slop. If it says `pip install foo`, that is human.
  - **Rule**: NEVER flag a document solely because it has standard README section headers. Only flag when the prose content under those headers exhibits 3+ tell categories.
- **Artificially comprehensive scope**: LLMs tend to cover every possible sub-topic even when the user asked about one thing. A "Getting Started" guide that covers installation, configuration, deployment, monitoring, and troubleshooting in exhaustive detail is suspicious — humans write focused docs.

### Code Comment-Specific Tells

These patterns apply specifically to LLM-generated code comments:

- **Over-commenting**: LLMs write comments on nearly every line or block. Comment-to-code ratios that far exceed human norms for the language are a density signal. Humans comment selectively.
- **Consistent commenting style**: LLM-generated comments maintain remarkably consistent style, tone, and formatting across an entire codebase. Human codebases accumulate inconsistencies from multiple authors and time periods.
- **LLM vocabulary in code comments**: Code comments containing "ensure," "robust," "comprehensive," "seamless," "leverage" at rates far exceeding human developer norms. Human code comments tend to be terse, informal, and use domain-specific jargon rather than generic adjectives.
- **Mechanically perfect boilerplate**: Every function gets the same doc-comment template with `@param`, `@returns`, `@throws` (or language equivalent) that adds no insight beyond the type signature.

## 7. Model-Specific Opening Words and Signatures

These apply to the first sentence of a response or document section:

- **ChatGPT** tends to start with: "As," "Sure," "Certainly," "Here," "Creating," "To," "Let's." The "Certainly!" opener was extremely common in GPT-3.5 and early GPT-4 but has been suppressed in later versions. ChatGPT has the strongest documented vocabulary fingerprint of any model family. Detection rate: ~68% average across detectors.
- **Claude** tends to start with: "I'd," "Based," "Here," "This," "How," "Looking." The "I'd be happy to help" pattern is a strong Claude signal, especially in technical contexts where no help was requested. Claude's strongest formatting tell is em-dash overuse. Distinctive Claude phrases include "complex and multifaceted" (700x more frequent in AI text), "intricate interplay" (100x). Claude has higher burstiness (genuine sentence-length variation) than ChatGPT, making it harder to detect. Detection rate: ~23% average — the least detectable major model.
- **Gemini** tends to start with: "Absolutely," "Great," "Here," "That's a great question." Gemini's tells are structural rather than lexical — heavy reliance on bullet points and numbered lists even when not requested, bold headings and subheadings, strict claim-evidence-conclusion paragraph format. Reads like a well-organized Wikipedia entry. Detection rate: ~61% average.
- **General LLM pattern**: Starting a document or section with a meta-statement about what the document will cover ("In this guide, we'll explore...") rather than just starting the content.

## 8. Caveats and Operationalization

### False positive risks

- No single indicator is conclusive. LLMs learned from human writing, so humans use these patterns too — especially humans who read a lot of LLM output and unconsciously adopt its style (FSU 2025 study found LLM buzzwords are entering everyday human speech).
- Academic and formal business writing naturally uses many of the transitions and structures that flag as LLM tells. Context matters: "Moreover" in a physics paper is normal; "Moreover" in a CLI tool's README is suspicious.
- Non-native English speakers sometimes produce text that triggers vocabulary and structure tells because they learned formal English from textbooks (which LLMs also learned from). Stanford HAI study found 61.3% false positive rate on TOEFL essays from non-native writers.

### Detection accuracy

- Heavy LLM users can detect AI text ~90% of the time (per a 2025 study of 500 participants).
- Automated detection using the tell-category convergence approach (3+ categories) achieves ~85% precision and ~70% recall on mixed corpora.
- ML-based detectors achieve 96-100% accuracy on clean AI text, but drop to 60-70% on paraphrased or humanized content.
- Recall drops to ~40% on text that was prompted with specific style instructions or heavily edited post-generation.

### Temporal drift

- These tells evolve as models are updated. What screams "AI" today may not tomorrow.
- Paraphrasing, editing, or prompting for a specific style can mask most of these signals.
- The strongest long-term signal is not any single word but the combination of uniform cadence + absence of genuine opinion + suspiciously complete coverage of a topic.
- Individual word tells are becoming less reliable as LLM vocabulary enters human speech. Cluster scoring (3+ tell categories converging) remains the most robust detection method.

# Document-level patterns

**These are not a 9th category and never count toward the 3-category cluster.**
They are scored once per document, in a separate pass, and reported separately.
Keeping them out of the cluster is deliberate: the per-unit threshold exists to
suppress false positives on good prose, and folding a document-wide signal into
it would let one diffuse pattern flip every paragraph in the file.

A document can be clean at every paragraph and still be obviously LLM-drafted.
The four patterns below are invisible to paragraph-level scoring because each
paragraph contributes only one instance:

- **Diffuse promotional register**: 4+ promotional terms per 1000 words (see Category 4), or a call-to-action closer. Individually each word is defensible; in aggregate the document reads as a pitch.
- **Pitch-deck arc**: the document's *skeleton* is a sales narrative — problem framed with an alarming statistic, then "the opportunity," then benefits/wins, then validation, then a call to action. A technical document's natural arc is mechanism, measurements, limitations. Absence of any limitation, tradeoff, or failure mode anywhere in a document that makes performance claims is part of this signal.
- **Templated section hinges**: sibling sections opening with the same syntactic frame — "The first block is X" / "The second block tackles a different but related problem" / "The third block takes a different angle." Three or more identically-shaped openers is a drafting fingerprint, even when each sentence is fine alone.
- **Cross-paragraph punctuation and formatting density**: em-dash rate computed over the whole document rather than per paragraph (Category 3's >2/500-word threshold applied document-wide), every headline number bolded, or the same appositive interruption rhythm (`X — aside — Y`) recurring throughout.

**Reporting.** Report document-level findings with the measured rate and the
comparison threshold (e.g. "31 em dashes / 1364 words = 11.4 per 500, vs >4
strong"). Do not convert them into paragraph flags, and do not let them raise
any paragraph's category count.

# Quick reference table

| # | Category | Strongest signals |
|---|----------|-------------------|
| 1 | Vocabulary | "delve," "tapestry," "underscore," "foster," "showcasing," "crucial," "comprehensive" |
| 2 | Structure | Rule of Three, "not X but Y," uniform cadence (CV < 0.25), numbered step labels |
| 3 | Punctuation | Em dash overuse (>2 per 500 words), Markdown in non-Markdown contexts |
| 4 | Tone | HR-speak, hedging padding (3+ per 500 words), overemphasis, "Despite its challenges…" |
| 5 | Transitions | "Moreover," "Furthermore," "Additionally," "Notably," "Indeed" (>2 per 500 words) |
| 6 | Tech-doc | Signature-restating descriptions, missing "why," mechanical boilerplate, over-commenting |
| 7 | Model openers | "Certainly!" (ChatGPT), "I'd be happy to help" (Claude), "Absolutely!" (Gemini) |
| 8 | Caveats | Require 3+ categories — single tells are noise; suppress in academic/non-native contexts |
