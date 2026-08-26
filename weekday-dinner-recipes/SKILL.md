---
name: weekday-dinner-recipes
description: Pull a fresh batch of well-rated, season-appropriate weekday dinner recipes from a curated list of reputable food sites, with the star rating and review count extracted from each live page and every link verified (no 404s). Use whenever the user asks for dinner ideas, weeknight meals, a recipe round-up, a meal plan, "more recipes," or anything resembling "what should I cook this week." Defaults to the current season; honors an explicit season if the user names one. Skips recipes already returned in prior runs by reading a local history file.
---

# Weekday Dinner Recipes

You are pulling 8–10 rated, link-verified weekday dinner recipes for the user. Every recipe must come with an exact star rating and an exact review count taken from the actual recipe page — no guessing, no estimating. Every URL must resolve. Never return a recipe you couldn't verify.

The user re-runs this frequently. They've already seen prior batches. Reading the history file and excluding past picks is part of doing the job.

## Host-environment translation

Two things vary by host: link verification and page fetch. Resolve to whichever your host supports:

| Action | Squad / shell hosts | Claude Code / Desktop | Browser-MCP-only hosts |
|---|---|---|---|
| Check URL returns 200 | `Bash`: `curl -sIL -o /dev/null -w "%{http_code}" -A "Mozilla/5.0" --max-time 15 <URL>` | `WebFetch` (treat non-empty body as live) | `mcp__chrome__navigate` then check page |
| Fetch page HTML for rating | `Bash`: `curl -sL -A "Mozilla/5.0" --max-time 15 <URL>` | `WebFetch <URL>` | browser MCP `get_page_text` |
| Search the web for candidates | `WebSearch` | `WebSearch` | `WebSearch` |

Anti-bot note: Damn Delicious and a few others return `403` to plain `curl` but render fine in a real browser. If `curl` returns 403, fall back to `WebFetch` / browser MCP before declaring the link broken. A 200 from any method is sufficient; a 404 from any method disqualifies the recipe.

## Inputs

The user invocation may include:

- A season (`"spring"`, `"summer"`, `"fall"`, `"winter"`) — honor it.
- A count (default 8–10).
- Specific constraints ("vegetarian only", "no seafood", "under 30 min").

If no season is given, derive it from today's date (Northern Hemisphere): Mar–May spring, Jun–Aug summer, Sep–Nov fall, Dec–Feb winter. Use `date +%m` if you're unsure of the current month.

## Step-by-step

### 1. Read the history file

Location: `${XDG_STATE_HOME:-$HOME/.local/state}/squad-skills/weekday-dinner-recipes/history.jsonl` (one JSON object per line: `{"url": "...", "title": "...", "date": "YYYY-MM-DD"}`).

If the file doesn't exist, treat history as empty and create it later (the append step does `mkdir -p` on the parent). Read every URL into an exclusion set. **Never return a URL already in history** — this is the main reason the skill exists across runs.

### 2. Pick the source set

Use the curated source list in `references/sources.md`. Each entry lists the site, why it's on the list, and any quirks (rating selector, anti-bot behavior). Don't search arbitrary sites — most recipe blogs either don't show review counts, hide them behind JavaScript, or fabricate them. The curated list is what makes the output trustworthy.

For seasonal cues (what counts as "summer-feeling" vs "winter-feeling"), see `references/seasonal-cues.md`.

### 3. Generate candidates

For each target slot (aim for 12–15 candidates to end up with 8–10 verified), search with queries like:

- `site:skinnytaste.com summer chicken weeknight`
- `site:halfbakedharvest.com grilled summer recipe`
- `site:cookieandkate.com vegetarian summer dinner`

Aim for variety across:

- **Protein**: chicken, beef/pork, seafood, vegetarian (≥2 of each in the final 10)
- **Style**: grill, sheet pan, skillet, pasta, salad-as-meal, tacos
- **Cuisine**: Mediterranean, Mexican, Asian, BBQ/American, Italian

### 4. Verify each candidate — DROP if any fail

For each candidate URL:

1. **Fetch the page.** Use `WebFetch` or `curl` (with the User-Agent header — many sites 403 the default `curl/x` UA).
2. **Confirm the page is the recipe** (title matches, no "Page Not Found", redirect didn't land on the homepage).
3. **Extract the exact star rating** from the page text. Look for patterns like `4.97 / 5`, `★★★★★ 4.9`, `Rated 5 stars`. Most recipe-card plugins (WPRM, Tasty) emit a visible rating block.
4. **Extract the exact review count.** Look for `"(312 reviews)"`, `"from 50 votes"`, `"Rated 5 stars by 7 readers"`. The label varies (reviews / ratings / votes / readers) — preserve whatever the site uses.
5. **Confirm total time** is roughly weeknight-friendly (~≤45 min active+passive, excluding overnight marinades).

If you cannot find either the rating or the count on the page, DROP the recipe. Do not estimate, do not infer from "looks popular." A recipe without a verifiable rating doesn't ship.

### 5. Verify the link returns 200

After extraction, sanity-check the URL is live: `curl -sIL -o /dev/null -w "%{http_code}"` (with UA). A `200` passes; `403` is acceptable IF a real fetch succeeded in step 4 (anti-bot block, not a broken link); `404`, `410`, `5xx` disqualify.

### 6. Format the output

```
**[Section header by category — Grilled / Sheet pan / Pasta / etc.]**

1. **[Recipe title]** — [Site] — [rating]/5, [count] [reviews|ratings|votes]. [One-line description: protein, style, time hint]. [Link](URL)
```

Group by category (grill / sheet pan / pasta / salad / tacos) when there's enough variety. Keep descriptions to one line — the user is scanning.

End with a soft offer: a meal plan, a grocery list, or scheduling the skill weekly.

### 7. Append to history

After delivering, append one line per returned recipe to the history file in `$XDG_STATE_HOME` (defaults to `~/.local/state`):

```bash
HIST="${XDG_STATE_HOME:-$HOME/.local/state}/squad-skills/weekday-dinner-recipes/history.jsonl"
mkdir -p "$(dirname "$HIST")"
cat >> "$HIST" <<EOF
{"url": "https://...", "title": "...", "date": "$(date +%Y-%m-%d)"}
EOF
```

This is what makes future runs return *different* recipes. The path lives outside the repo on purpose — it's per-machine runtime state, not skill source.

## What to skip

- **Slow-cooker / overnight / multi-hour braise recipes** unless explicitly requested. Weeknight = under 45 active min.
- **"Salad" recipes that are sides**, not meals. A meal-salad has protein and substance.
- **Roundup posts / listicles** (`"15 Best Summer Dinners"`). Only single-recipe pages with their own rating block.
- **Sites that show "5 stars" with no count visible** — the count is the credibility signal. If it's missing, the rating is noise.

## Anti-patterns to avoid

- ❌ Returning a rating without a count ("4.8 stars" alone). Always pair them.
- ❌ Rounding the rating ("4.97 → 5"). Preserve what the page shows.
- ❌ Skipping link verification because the URL "looks fine."
- ❌ Re-returning a recipe from the history file. The user notices and it erodes trust in the skill.
- ❌ Padding the output with recipes you couldn't verify, with a footnote excusing it. Better to return 7 verified than 10 with caveats.

## Why this skill exists

Most "recipe round-up" answers from a generic model fall down in three predictable ways: ratings get made up, links 404 or redirect, and the same dishes show up every week. This skill closes all three holes. The cost is real work per recipe — fetch, parse, verify — but the user trusts the output because every number on the page traces back to the recipe site.
