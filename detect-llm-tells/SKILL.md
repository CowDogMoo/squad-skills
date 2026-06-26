---
name: detect-llm-tells
description: Score prose paragraphs or code comments against 8 LLM-generated-text tell categories with cluster scoring (flag at 3+ converging categories). Use when scrubbing LLM slop from documentation, READMEs, or source-code comments.
# NOTE: intentionally no `allowed-tools`. squad applies a skill's allowed-tools
# session-wide and never pops it, so a restrictive list here would permanently
# strip edit tools from the agents that load this skill (degpt,
# go-scrub-comments, rust-scrub-comments) — the very rewrite step they exist
# for. This is a scoring/knowledge skill; the caller's run mode governs tool
# access (readonly mode is still enforced by the readonly backstop).
metadata:
  author: Jayson Grace
  version: 1.2.0
---

# Detect LLM Tells

You are scoring text against known indicators that an LLM (rather than a human) wrote it. Your output is a per-unit classification (FLAG / NO-FLAG) with the tell categories that convinced you and a confidence level. The caller decides what to do with flagged units (delete, rewrite, report) — this skill only judges.

Before scoring, consult `references/categories.md` for the full catalog
of patterns that count toward each of the 8 categories (vocabulary tiers,
structural patterns, em-dash thresholds, model-specific openers, etc.).
The decision rules in this file are authoritative; the catalog is the
lookup table you check each unit against.

# How to use this skill

## Unit of analysis

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

## Cluster scoring (the only reliable rule)

Score each unit against the 8 categories from `references/categories.md`.
Count **distinct categories** that fire — not the total number of
individual tells.

| Categories fired | Confidence | Action |
|---|---|---|
| 4 or more | HIGH | FLAG |
| Exactly 3 | MEDIUM | FLAG |
| 1 or 2 | LOW | DO NOT flag — single-category hits are too noisy |
| 0 | — | clean |

A single occurrence of "delve," one "Moreover," or one em-dash is never enough on its own. Convergence is the signal; isolated tells are not.

## Tell categories that count, even at one hit

A few categories are strong enough that one clear example counts toward the cluster:

- **Tier 1 vocabulary** (one Tier 1 word = vocabulary fires)
- **HR-speak openers** ("Certainly!", "Great question!", "I'd be happy to help")
- **Numbered step/phase labels in code comments** (two or more in sequence = strong by themselves; see Category 2 in `references/categories.md`)
- **Model-specific opener phrases** (Category 7, full phrases not single words)

For Tier 2/3 vocabulary, transitional phrases, and em-dash use, require **2+ instances** within the same unit before that category fires. Single occurrences are baseline noise.

## What this skill does NOT cover

The caller's `system.md` is authoritative for:

- File discovery (glob patterns, exemptions)
- Edit-mode vs readonly-mode behavior
- Output format
- Whether to keep or delete specific kinds of useful comments
- Compilation/lint verification after changes

If guidance in this skill conflicts with the caller's hard rules, the caller's hard rules win.

# Examples

## Example 1 — Prose paragraph FLAGged

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

## Example 2 — Code comment NOT FLAGged

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

0 categories fire → **clean, NO-FLAG.**

## Example 3 — Code comment FLAGged (numbered step labels)

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

2 categories fire — but the numbered-step-labels signal is in the
one-hit list, and it's reinforced by Category 6 → **FLAG, MEDIUM
confidence.** The caller (a scrub agent) deletes the block.

# Troubleshooting

## Error: Single-category hit triggered a FLAG

**Cause:** Caller is using single-tell scoring instead of cluster scoring.

**Solution:** Re-read the Cluster scoring table. One em-dash, one
"Moreover," or one "delve" is never enough on its own. Require 3+
distinct categories before flagging. The exceptions (Tier 1 vocabulary,
HR-speak openers, numbered step labels in comments, model-specific
opener phrases) still count as *one* category — they don't bypass the
cluster threshold; they just lower the threshold for *that* category
firing.

## Error: Real human prose getting FLAGged in academic or non-native contexts

**Cause:** Academic English and English-as-second-language writing
naturally use many of the transitions and vocabulary the categories
flag. Stanford HAI found 61.3% false positive rate on TOEFL essays.

**Solution:** Treat the source as context. README in a CLI tool repo:
flag aggressively. Academic paper, business prose, ESL author: raise
the threshold to 4+ categories, and consult Category 8 caveats in
`references/categories.md`.

## Error: Couldn't decide between FLAG and NO-FLAG

**Cause:** The unit is on the boundary (e.g., 2-3 categories firing
weakly).

**Solution:** When exactly 3 categories fire weakly, default to
MEDIUM-confidence FLAG and let the caller (which has the edit/keep
authority) decide. If only 2 fire, mark NO-FLAG. Never flag on 1.

## Error: References file not loaded

**Cause:** `references/categories.md` is not visible to the caller.

**Solution:** Read it explicitly on the first iteration that needs the
catalog. The cluster-scoring rule in SKILL.md can be applied without
it for obvious cases, but Tier 2/3 vocabulary and threshold numbers
(em-dashes per 500 words, transition density, CV of sentence length)
live in the reference file.
