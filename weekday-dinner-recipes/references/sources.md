# Curated recipe sources

Sites with reliably visible star ratings + review counts on a per-recipe page. Use only these; bring in others only after confirming they show both numbers on the page (not in a popup, not in JSON-LD only).

## Tier 1 — best for this skill

| Site | URL pattern | Rating block | Notes |
|---|---|---|---|
| Once Upon a Chef | `onceuponachef.com/recipes/<slug>.html` | "Rated X stars by N reviewers" | Clean, weeknight-friendly, large review counts. |
| Skinnytaste | `skinnytaste.com/<slug>/` | "X / 5" + "N votes" | Strong on light/seasonal, healthy weeknight. |
| Half Baked Harvest | `halfbakedharvest.com/<slug>/` | "X from N votes" (WPRM) | Trendy/produce-heavy. Sometimes slightly fussier than 30-min weeknight. |
| Cookie and Kate | `cookieandkate.com/<slug>/` | "X stars (N reviews)" | Vegetarian-only — useful for variety. |
| Damn Delicious | `damndelicious.net/YYYY/MM/DD/<slug>/` | "X stars (N ratings)" | **Curl returns 403** — fetch via WebFetch / browser MCP. |
| The Mediterranean Dish | `themediterraneandish.com/<slug>/` | "X from N votes" | Mediterranean focus, good seasonal coverage. |
| Budget Bytes | `budgetbytes.com/<slug>/` | "X from N votes" | Affordable, simple weeknight dinners. |
| Pinch of Yum | `pinchofyum.com/<slug>` | "X stars (N reviews)" | Solid Asian/comfort coverage. |
| The Modern Proper | `themodernproper.com/<slug>` | "Avg: X / 5" + "Rated by N readers" | Lower review counts but reliable. |

## Tier 2 — usable with care

| Site | Caveat |
|---|---|
| NYT Cooking | Has rating + count but paywalled excerpts may not show in WebFetch. Try, drop if blocked. |
| Bon Appétit | Rating often shown without total count. Verify count is visible before including. |
| Smitten Kitchen | Comments, not formal ratings. Skip unless explicitly requested. |
| Serious Eats | Inconsistent rating visibility — verify per page. |

## Do NOT use

| Site | Why |
|---|---|
| Allrecipes | Blocked from WebSearch in this environment. |
| Food Network | Rating count is hard to extract programmatically. |
| Pinterest | Aggregator, not source. |
| TikTok / Instagram | No rating system. |
| Generic listicle/roundup pages | No per-recipe rating. |

## Fetch quirks

- **Damn Delicious**: 403s plain `curl`. Use `WebFetch` directly, or pass `-A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"` to curl.
- **Half Baked Harvest**: rating block sometimes shows "X votes" and a separate "ratings without comment" — use the votes number as the canonical count.
- **WPRM-based sites** (most of the above): the rating block appears twice on the page (header card + recipe card). Either occurrence is fine to extract.
