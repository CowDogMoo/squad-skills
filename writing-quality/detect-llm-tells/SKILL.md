---
name: detect-llm-tells
description: Score prose paragraphs or code comments against 8 LLM-generated-text tell categories with cluster scoring (flag at 3+ converging categories), plus a document-level pass for diffuse tells that per-paragraph scoring cannot see. Use when scrubbing LLM slop from documentation, READMEs, talk scripts, or source-code comments.
# NOTE: intentionally no `allowed-tools`. squad applies a skill's allowed-tools
# session-wide and never pops it, so a restrictive list here would permanently
# strip edit tools from the agents that load this skill (degpt,
# go-scrub-comments, rust-scrub-comments) — the very rewrite step they exist
# for. This is a scoring/knowledge skill; the caller's run mode governs tool
# access (readonly mode is still enforced by the readonly backstop).
metadata:
  author: Jayson Grace
  version: 1.4.0
---

# Detect LLM Tells

You are scoring text against known indicators that an LLM (rather than a human) wrote it. Your output is a per-unit classification (`FLAG` / `NO-FLAG`) with the tell categories that convinced you and a confidence level (`HIGH`, `MEDIUM`, `LOW`, or `clean`). The caller decides what to do with flagged units (delete, rewrite, report) — this skill only judges.

Read `references/categories.md` before scoring your first unit so you
check every unit against the full 8-category catalog (vocabulary tiers,
structural patterns, code-comment sub-patterns, em-dash thresholds,
model-specific openers, etc.). Do not skip the catalog for "obvious"
inputs. The decision rules in this file are authoritative; the catalog
is the lookup table you check each unit against.

## How to use this skill

### Unit of analysis

The "unit" depends on the caller's domain:

- **Prose** (Markdown, READMEs, plain text): one paragraph = one unit. Minimum 2 sentences / ~30 words. Single sentences are too short to score reliably.
- **Code comments**: one comment *block* = one unit. A block is contiguous `//`/`#` lines (or a single `/* ... */` / `""" ... """` chunk). Do not score individual lines in a multi-line block separately.

Skip these regardless of caller domain:

- Code fences and indented code blocks (in prose)
- YAML/JSON/TOML frontmatter
- CLI examples and shell transcripts
- Non-English text — these categories are English-specific
- Compiler/linter directives (`//go:*`, `//nolint`, `# noqa`, `# type:`, etc.)
- `TODO` / `FIXME` / `HACK` / `NOTE` / `XXX` / `BUG(` markers
- License and copyright headers
- Auto-generated content (`// Code generated ... DO NOT EDIT.` and equivalents)

### Cluster scoring (the only reliable rule)

Score each unit against the 8 categories from `references/categories.md`.
Count **distinct categories** that fire — not the total number of
individual tells.

| Categories fired | Verdict | Confidence | Meaning |
|---|---|---|---|
| 4 or more | `FLAG` | `HIGH` | Converging multi-category signal |
| Exactly 3 | `FLAG` | `MEDIUM` | Meets cluster threshold |
| Exactly 2: Cat 2 sequential step labels + Cat 6 restatement (code comments) | `FLAG` | `MEDIUM` | Sole 2-category exception — see Example 3 |
| 1 or 2 (any other combination) | `NO-FLAG` | `LOW` | Isolated signal below threshold — report `NO-FLAG (LOW)`, never `FLAG` and never `clean` |
| 0 | `NO-FLAG` | `clean` | Zero tell categories fired |

A single occurrence of "delve," one "Moreover," or one em-dash is never enough on its own. Convergence is the signal; isolated tells are not. Keep `NO-FLAG (LOW)` distinct from `NO-FLAG (clean)`: a unit where one or two categories fire (other than the step-label + Category 6 exception) still carries a weak signal and must be reported with `NO-FLAG` and `LOW` confidence rather than collapsed into `clean`.

### Tell categories that count, even at one hit

A few categories are strong enough that one clear example fires that category toward the cluster:

- **Tier 1 vocabulary** (one Tier 1 word = Category 1 fires)
- **HR-speak openers** ("Certainly!", "Great question!", "I'd be happy to help" = Category 4 fires)
- **Model-specific opener phrases** (Category 7 full phrases, not bare single words)
- **Numbered step/phase labels in code comments** (two or more in sequence = Category 2 fires strongly; when paired with Category 6 code restatement in a comment block, this pair alone reaches `FLAG` at `MEDIUM` confidence — see Example 3 and Category 2 in `references/categories.md`)

For Tier 2/3 vocabulary, transitional phrases, and em-dash use, require **2+ instances** within the same unit before that category fires. Single occurrences are baseline noise — note them as below-threshold rather than firing the category.

### Document-level scoring (second pass, prose callers only)

Cluster scoring is per-unit, so it is structurally blind to any tell that
contributes only one instance per paragraph. A document can score clean at every
paragraph and still read as LLM-drafted. After scoring all units in a document,
run one document-level pass against "Document-level patterns" in
`references/categories.md`: diffuse promotional register, pitch-deck arc,
templated section hinges, and cross-paragraph punctuation density.

Rules for this pass:

- It produces **document-level findings**, reported separately. They are not paragraph flags.
- They **never** count toward any unit's 3-category cluster, and never promote a LOW paragraph to FLAG. The cluster threshold is the false-positive guard; this pass must not weaken it.
- Report the measured rate against the threshold, not an impression ("11.4 em dashes per 500 words, vs >4 strong").
- Skip for code-comment callers. Comment blocks are not documents.

A document with zero flagged paragraphs and one document-level finding is a
normal, correct outcome — say so plainly rather than reaching for a paragraph to
flag.

### Genre governs the baseline

Score against the conventions of what the text actually is:

- **Spoken scripts** (talks, demos, narration): judge as delivery. Contractions, sentence fragments, direct address, and "So," / "Now," openers are correct, not tells. Long unbreathable sentences and stacked tricolons are worse here than on the page. Bold formatting is inert — a script is heard.
- **Marketing copy**: promotional register is the genre, not a tell. Suppress the Category 4 promotional signal entirely; keep vocabulary and structure.
- **Academic / business / ESL prose**: raise the threshold to 4+ categories per Category 8.
- **READMEs and technical docs**: the default baseline these categories were written against.

If the caller states the genre, use it. If not, infer from the file and say which baseline you applied.

### Report shape

The reader sees only your final message. Unless the caller's prompt or `system.md` specifies another format — including on free-form requests such as "which paragraphs or comments look machine-written?" — report every unit explicitly using this structure:

1. **Per-unit verdicts** (table or per-unit entries) covering **every** in-scope unit (each prose paragraph or each contiguous comment block, scored as a whole block rather than line by line), not only the flagged ones:
   - **Unit / location**: paragraph number or comment block line range.
   - **Verdict**: literal `FLAG` or `NO-FLAG` on every unit (do not substitute informal prose headings alone without stating `FLAG` / `NO-FLAG` per unit).
   - **Confidence**: `HIGH` (4+ categories), `MEDIUM` (3 categories, or sequential step labels + Category 6 restatement in code comments), `LOW` (1–2 categories), or `clean` (0 categories). When 1 or 2 categories fire outside that step-label exception, always write `NO-FLAG (LOW)` (or `NO-FLAG` with confidence `LOW`) — never omit `LOW` and never label a 1–2 category unit `clean`.
   - **Categories fired**: named categories from the 8-category catalog (e.g., `Cat 2 Structure`, `Cat 6 Tech-doc`) or `none` when 0 fire, with brief evidence per unit (and note any single Tier 2/3 word or transition that stayed below the 2+ per-unit threshold).
2. **Skipped items**: list skipped frontmatter, code fences, compiler/linter directives (`//nolint`, `//go:*`, `# noqa`, `# type:`), convention markers (`TODO`, `FIXME`), or license/generated headers separately as skipped, not scored.
3. **Document-level pass** (prose callers only; omit for code comments): reported in its own separate section with measured rates against thresholds, never added to per-paragraph category counts.

### What this skill does NOT cover

The caller's `system.md` is authoritative for:

- File discovery (glob patterns, exemptions)
- Edit-mode vs readonly-mode behavior
- Custom output format (when the caller overrides the default report shape above)
- Whether to keep or delete specific kinds of useful comments
- Compilation/lint verification after changes

If guidance in this skill conflicts with the caller's hard rules, the caller's hard rules win.

## Examples

### Example 1 — Prose paragraph FLAGged

Unit:

> Moreover, this comprehensive framework enables developers to seamlessly
> leverage the full power of the underlying ecosystem. It's worth noting
> that the intricate interplay between components fosters robust,
> scalable, and maintainable solutions.

Scoring:

- **Cat 1 Vocabulary (Tier 1 + 2 cluster):** "comprehensive," "intricate," "foster," "leverage," "robust" — fires.
- **Cat 2 Structure:** "robust, scalable, and maintainable" — Rule of Three triplet.
- **Cat 3 Punctuation:** clean — does not fire on this unit alone.
- **Cat 4 Tone:** "It's worth noting" — hedging padding fires.
- **Cat 5 Transitions:** "Moreover" — high-signal transition fires.

5 categories fire → **FLAG, HIGH confidence.**

### Example 2 — Code comment NOT FLAGged

Unit:

```go
// retry uses the caller's context so the parent can cancel mid-backoff
// — otherwise a slow upstream wedges the worker pool.
```

Scoring:

- One em-dash, but well under the 2-per-500-words threshold for a unit
  this size.
- No Tier 1 vocabulary, no Rule of Three, no transitional phrases.
- Explains *why* (the cancellation contract), not *what*.

0 categories fire → **NO-FLAG, clean.**

### Example 3 — Code comment FLAGged (numbered step labels)

Unit:

```python
# Step 1: Validate the input
# Step 2: Process the data
# Step 3: Return the result
```

Scoring:

- **Cat 2 Structure:** three numbered step labels in sequence — strong
  signal by itself (one-hit category).
- **Cat 6 Tech-doc (code comments):** restates what the next lines do
  without explaining why.

2 categories fire — sequential numbered step labels in a code comment
reinforced by Category 6 restatement → **FLAG, MEDIUM confidence.** The
caller (a scrub agent) deletes the block.

### Example 4 — Code comment NOT FLAGged (single-category LOW)

Unit:

```python
# Facilitates token refresh for expired sessions.
def refresh_token(session: Session) -> Token:
```

Scoring:

- **Cat 6 Tech-doc (code comments):** restates what the function name
  and signature already show without explaining why — fires.
- **Cat 1 Vocabulary:** "Facilitates" is a single Tier 3 verb, below the
  2+ per-unit threshold — does not fire.

1 category fires → **NO-FLAG (LOW confidence).** Do not flag on a single
category, and do not label it `clean` because Category 6 fired.

## Troubleshooting

### Error: Single-category hit triggered a FLAG

**Cause:** Caller is using single-tell scoring instead of cluster scoring.

**Solution:** Re-read the Cluster scoring table. One em-dash, one
"Moreover," or one "delve" is never enough on its own. Require 3+
distinct categories before flagging, and report other 1- or 2-category
units as `NO-FLAG (LOW)`. One-hit signals (Tier 1 vocabulary, HR-speak
openers, model-specific opener phrases) still count as *one* category —
they lower the threshold for *that* category firing, not the 3-category
cluster threshold (the sole 2-category exception is 2+ sequential
numbered step/phase labels paired with Category 6 restatement in code
comments, as in Example 3).

### Error: Real human prose getting FLAGged in academic or non-native contexts

**Cause:** Academic English and English-as-second-language writing
naturally use many of the transitions and vocabulary the categories
flag. Stanford HAI found 61.3% false positive rate on TOEFL essays.

**Solution:** Treat the source as context. README in a CLI tool repo:
flag aggressively. Academic paper, business prose, ESL author: raise
the threshold to 4+ categories, and consult Category 8 caveats in
`references/categories.md`.

### Error: Document obviously reads like LLM output, but every paragraph scores clean

**Cause:** The tell is diffuse. Promotional register, a pitch-deck arc, and
document-wide em-dash density each contribute about one instance per paragraph,
so no unit ever reaches 3 categories. This is the expected failure mode of
per-unit scoring, not a scoring mistake.

**Solution:** Run the document-level pass (see "Document-level scoring" above)
and report those findings separately. Do NOT lower the cluster threshold or
stretch weak per-paragraph signals to force a flag — that trades a real miss for
a false positive on good prose. Report honestly: "0 paragraphs flagged, 2
document-level findings" is a complete and correct result.

### Error: Couldn't decide between FLAG and NO-FLAG

**Cause:** The unit is on the boundary (e.g., 2-3 categories firing
weakly).

**Solution:** When exactly 3 categories fire weakly, default to
`FLAG` (`MEDIUM` confidence) and let the caller (which has the edit/keep
authority) decide. If only 1 or 2 categories fire, report `NO-FLAG (LOW)`
(never `clean`, which is reserved for 0 categories) unless they are the
step-label + Category 6 pair from Example 3. Never flag on 1.

### Error: References file not loaded

**Cause:** Scorer skipped reading `references/categories.md` or could not
locate it relative to the skill directory.

**Solution:** Always Read `references/categories.md` (in this skill's
directory) before scoring your first unit — vocabulary tiers,
code-comment sub-patterns, model-specific openers, and numeric
thresholds live there. Only score from `SKILL.md` alone if the file
genuinely cannot be read in the caller's environment, and note that in
your report.
