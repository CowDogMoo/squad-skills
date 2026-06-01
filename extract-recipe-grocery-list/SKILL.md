---
name: extract-recipe-grocery-list
description: Given a list of online recipe URLs, fetch each, extract ingredients (preferring schema.org JSON-LD), and produce a deduplicated grocery list grouped by aisle with each item annotated by which dish needs it. Use when building a weekly shopping list from a meal plan.
---

# Extract Recipe Grocery List

You are turning a set of recipe URLs into a single shopping list. The output is a deduplicated, aisle-grouped list where every line is ONE thing the user buys, with the dish(es) needing it annotated in parentheses. The caller decides what to do with the list (write to a doc, hand to a grocery-shopping agent, print to stdout).

# Host-environment translation (READ FIRST)

The fetch step is the only host-dependent part. Resolve one of these to the host:

| Action | Squad / shell hosts | Claude Code / Desktop | Browser-MCP-only hosts |
|---|---|---|---|
| Fetch a recipe page | `Bash` with `curl -sL --max-time 10 <URL>` | `WebFetch <URL>` | `mcp__chrome__evaluate_script` with `fetch(url).then(r => r.text())` |
| Parse HTML / JSON | inline Python via Bash (`python3 -c '...'`) | same, or inline reasoning | inline reasoning over returned HTML |
| HTML entity decode | `html.unescape` in Python | same | inline reasoning |

The Python-via-curl one-liner below is the simplest and most repeatable; prefer it when Bash + `python3` are available. Fall back to browser MCP only when the recipe site rejects direct curl (Cloudflare, etc.).

# Inputs

A list of `(dish_name, recipe_url)` pairs. Example:

    [
      ("crispy buffalo tofu",  "https://example.com/crispy-buffalo-tofu"),
      ("beef stroganoff",      "https://example.com/beef-stroganoff"),
      ("bang bang salmon",     "https://example.com/bang-bang-salmon"),
    ]

The dish name is what gets annotated onto each ingredient (`5 tablespoons butter (crispy buffalo tofu 3 tbsp, beef stroganoff 2 tbsp)`). Recipe URLs that are missing or fail to fetch are reported but do not abort the run.

# Step-by-step

## 1. Fetch each recipe page

For each `(dish, url)` pair, fetch the page HTML. On Bash/curl hosts:

```bash
curl -sL --max-time 10 "<URL>"
```

If a fetch errors, paywalls, or times out, skip that one recipe and note `"couldn't fetch recipe for <dish>"` in the final summary. Keep going with the others — one bad URL does not abort the run.

## 2. Extract ingredients

**Preferred path: schema.org JSON-LD.** Most recipe sites embed a `"recipeIngredient"` array inside a JSON-LD `<script type="application/ld+json">` block. Search the page HTML for `"recipeIngredient"` and parse the array. **Decode HTML entities** in each ingredient string (`&#8217;` → `'`, `&amp;` → `&`) — JSON-LD often holds HTML-encoded text.

One-liner that does both extraction and decoding:

```bash
curl -sL --max-time 10 "<URL>" | python3 -c '
import sys, re, json, html
m = re.search(r"\"recipeIngredient\":\s*(\[.*?\])", sys.stdin.read())
if m:
    for line in json.loads(m.group(1)):
        print(html.unescape(line))
'
```

**Fallback: visible Ingredients section.** If JSON-LD isn't present (rare on modern recipe blogs), parse the visible "Ingredients" section in the rendered HTML. Apply `html.unescape` to each line likewise.

For each ingredient, capture both the quantity and the item (`1 lb chicken thighs`, `2 cloves garlic`, `1/4 cup soy sauce`). Preserve the original wording — don't normalize units.

## 3. Filtering rules — apply in order

### 3a. Keep multi-part strings INTACT

`"1 lb egg noodles, or 6 baked potatoes"` is ONE ingredient with an alternative, not two. Never split on commas inside an ingredient string. The word `"or"` inside an ingredient line is your tell that you're looking at an alternative — keep the line intact.

⚠️ Anti-example: an agent took `"1 lb egg noodles, or 6 baked potatoes"` and emitted `"1 lb. egg noodles,"` into Pantry and `"or 6 baked potatoes"` into Produce. Both lines are wrong. The correct output is ONE Pantry line: `1 lb egg noodles, or 6 baked potatoes (beef stroganoff)`. A line starting with `"or "` in your output is ALWAYS a bug.

### 3b. Skip serving-suggestion lines

Some recipe sites pack non-ingredient guidance into the `recipeIngredient` array (`"Salad with Caesar, ranch, or bleu cheese dressing"`, `"Serve with crusty bread"`, `"Optional: lemon wedges"`). Drop any line that starts with `"Serve with"`, `"Salad with"`, `"Optional:"`, `"For serving"`, or reads as a suggestion rather than a measurable ingredient.

### 3c. Skip pantry staples

This is a shopping list, not a recipe transcription. The user already owns:

- water (any form: `3 cups water`, `2 cups cold water`, `water for boiling`, `1 cup hot water`)
- salt, kosher salt, sea salt, table salt
- black pepper, white pepper, ground pepper
- ALL salt/pepper variants regardless of quantity — explicit measure (`2 teaspoons salt`), `to taste`, `a pinch`, `as needed` — all skipped
- tap-water-equivalent items (ice, etc.)

Drop these lines entirely. Other staples (oil, flour, soy sauce, eggs, tofu) STAY — those are real purchases.

⚠️ Anti-example: agent emitted `3 cups water (beef stroganoff)`, `2 teaspoons salt (beef stroganoff)`, and `1/4 teaspoon ground black pepper (beef stroganoff)` into Pantry. All three must be dropped. The test is: would a normal household NOT have this in the cabinet? If they would have it, skip. Water/salt/pepper are always skipped.

### 3d. CONSOLIDATE duplicates into ONE line per purchase

The most important rule. Every line in the output is ONE THING THE USER BUYS. If two recipes both call for "butter," that's ONE line with both quantities and both dishes annotated:

    5 tablespoons butter (crispy buffalo tofu 3 tbsp, beef stroganoff 2 tbsp)

Same rule across all of:

- **Same recipe, same ingredient, multiple lines (sum):** `1 cup water + 2 cups water → 3 cups water` (then dropped by 3c since water is a staple)
- **Same recipe, ONE ingredient appears twice with different roles** (e.g. `Better Than Bouillon` used in two steps of stroganoff at `1 tsp` and `1 1/2 tbsp`): emit ONE line summing or listing both:
  `1 tsp + 1 1/2 tbsp Better Than Bouillon Roasted Beef Base (beef stroganoff)`
- **Same ingredient across DIFFERENT recipes** (`1/2 tsp garlic powder (crispy buffalo tofu)` + `1 tsp garlic powder (beef stroganoff)`): ONE line with both quantities and both dishes annotated:
  `1 1/2 tsp garlic powder (crispy buffalo tofu 1/2 tsp, beef stroganoff 1 tsp)`

Match items by normalized name (lowercase, ignore minor descriptors like "thinly sliced," "fresh," "minced"). When in doubt, consolidate aggressively — one shopping line is better than two cluttering entries.

⚠️ Anti-examples from a real failed run — these are the concrete bugs to avoid:

- Two butter lines:
  `3 tablespoons butter (crispy buffalo tofu)`
  `2 tablespoons butter (beef stroganoff)`
  Correct: ONE line —
  `5 tablespoons butter (crispy buffalo tofu 3 tbsp, beef stroganoff 2 tbsp)`

- Two `Better Than Bouillon` lines from the same recipe:
  `1 teaspoon Better Than Bouillon Roasted Beef Base (beef stroganoff)`
  `1 1/2 tablespoons Better Than Bouillon Roasted Beef Base (beef stroganoff)`
  Correct: ONE line —
  `1 tsp + 1 1/2 tbsp Better Than Bouillon Roasted Beef Base (beef stroganoff)`

- Two garlic powder lines:
  `1/2 teaspoon garlic powder (crispy buffalo tofu)`
  `1 teaspoon garlic powder (beef stroganoff)`
  Correct: ONE line —
  `1 1/2 tsp garlic powder (crispy buffalo tofu 1/2 tsp, beef stroganoff 1 tsp)`

**Before finalizing each category, scan it for duplicates.** Two lines in the same category with the same item name is ALWAYS a bug. Consolidate them.

## 4. Group by aisle

Combine all ingredients across the recipes, then bucket each into one of:

- **Produce** — fruits, vegetables, fresh herbs
- **Protein** — fresh/frozen meat, seafood, eggs, tofu
- **Dairy** — milk, cheese, yogurt, butter, cream
- **Refrigerated** — kimchi, miso, tortillas in the fridge case, fresh pasta, anything else in a refrigerated case but not dairy or protein
- **Pantry** — oils, vinegars, spices, grains, pasta, canned goods, condiments, sauces
- **Frozen** — anything explicitly frozen aside from protein
- **Bakery / Other** — bread, tortillas, anything else

If a bucket is empty, omit it from the output (don't emit empty headers).

## 5. Return the list

The default output shape is a structured list the caller can render however they want:

    {
      "Produce": [
        "1 lb chicken thighs (chicken tinga tacos)",
        "2 cloves garlic (chicken tinga tacos, bang bang salmon)"
      ],
      "Pantry": [
        "1 lb egg noodles, or 6 baked potatoes (beef stroganoff)",
        "5 tablespoons butter (crispy buffalo tofu 3 tbsp, beef stroganoff 2 tbsp)"
      ],
      ...
    }

If the caller asks for plain text instead, render as one ingredient per line, category headers on their own line, no leading bullet:

    Produce
    1 lb chicken thighs (chicken tinga tacos)
    2 cloves garlic (chicken tinga tacos, bang bang salmon)

    Pantry
    1 lb egg noodles, or 6 baked potatoes (beef stroganoff)
    5 tablespoons butter (crispy buffalo tofu 3 tbsp, beef stroganoff 2 tbsp)

Always pair the list with a short summary:

- Recipes successfully fetched and parsed (count + names)
- Recipes that failed (URL + reason: paywall, timeout, no JSON-LD)
- Ingredients dropped as staples (count, not full list)
- Lines consolidated (count)

# Constraints

- Annotate every line with the dish in parens using the FULL dish name as it appears in the input (`(crispy buffalo tofu)`, `(beef stroganoff)`) — never short tags like `(tofu)` or `(beef)`.
- A line in the output starting with `"or "` is always a bug — it means rule 3a was violated.
- Two lines in the same category with the same item name is always a bug — it means rule 3d was violated. Re-consolidate.
- Don't fabricate ingredients. If a recipe fetch fails, the recipe contributes nothing — say so in the summary.
- Don't normalize units silently. `1 cup` stays `1 cup`, not "8 fluid ounces."
