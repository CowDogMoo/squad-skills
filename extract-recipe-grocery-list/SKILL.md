---
name: extract-recipe-grocery-list
description: Given a list of online recipe URLs, fetch each, extract ingredients (preferring schema.org JSON-LD), and produce a deduplicated grocery list grouped by aisle with each item annotated by which dish needs it. Use when building a weekly shopping list from a meal plan.
---

# Extract Recipe Grocery List

You are turning a set of recipe URLs into a single shopping list. The output is a deduplicated, aisle-grouped list where every line is one thing the user buys, with the dish(es) needing it annotated in parentheses. The caller decides what to do with the list (write to a doc, hand to a grocery-shopping agent, print to stdout).

## Host-environment translation

Fetching is the only host-dependent step; everything after it is reasoning
over text. Pick the row that matches the host:

| Host                        | Fetch + extract                                                                 |
| --------------------------- | ------------------------------------------------------------------------------- |
| Bash + python3 available    | `python3 scripts/extract_ingredients.py <URL> [<URL> ...]` (preferred)          |
| Claude Code / Desktop       | same; or `WebFetch <URL>` and read the ingredients from the returned text       |
| Browser-MCP-only hosts      | `mcp__chrome__evaluate_script` with `fetch(url).then(r => r.text())`, then reason over the HTML |

The bundled script is the most repeatable path: it parses every JSON-LD block
properly (including `@graph`-wrapped recipes that a naive regex misses),
decodes HTML entities, falls back to the visible ingredients list, and reports
per-URL failures without aborting. Fall back to browser MCP only when a site
rejects direct fetches (Cloudflare and similar).

## Inputs

A list of `(dish_name, recipe_url)` pairs. Example:

    [
      ("pasta primavera",  "https://example.com/pasta-primavera"),
      ("chicken stir-fry", "https://example.com/chicken-stir-fry"),
      ("vegetable curry",  "https://example.com/vegetable-curry"),
    ]

The dish name is what gets annotated onto each ingredient (`5 tablespoons butter (pasta primavera 3 tbsp, chicken stir-fry 2 tbsp)`). Recipe URLs that are missing or fail to fetch are reported but do not abort the run.

## Step-by-step

### 1. Fetch and extract ingredients

Run the bundled script once with every URL:

```bash
python3 scripts/extract_ingredients.py --json "<URL-1>" "<URL-2>" ...
```

Each result carries `url`, `source` (`json-ld`, `visible`, `none`, or
`error`), and `ingredients`. A `none` or `error` entry means that recipe
contributes nothing — note `"couldn't fetch recipe for <dish>"` in the final
summary and keep going with the rest. One bad URL doesn't abort the run.

Without the script (browser-only hosts), look for a
`<script type="application/ld+json">` block containing `"recipeIngredient"`
and read the array; decode HTML entities (`&#8217;` → `'`, `&amp;` → `&`)
because JSON-LD on many sites holds encoded text.

If JSON-LD isn't present (rare on modern recipe blogs), the script — or you,
on browser hosts — reads the visible "Ingredients" section instead.

For each ingredient, capture both the quantity and the item (`1 lb chicken thighs`, `2 cloves garlic`, `1/4 cup soy sauce`). Preserve the original wording — don't normalize units.

### 3. Filtering rules — apply in order

#### 3a. Keep multi-part strings intact

`"1 lb egg noodles, or 6 baked potatoes"` is ONE ingredient with an alternative, not two. Never split on commas inside an ingredient string. The word `"or"` inside an ingredient line is your tell that you're looking at an alternative — keep the line intact.

⚠️ Anti-example: an agent took `"1 lb egg noodles, or 6 baked potatoes"` and emitted `"1 lb. egg noodles,"` into Pantry and `"or 6 baked potatoes"` into Produce. Both lines are wrong. The correct output is ONE Pantry line: `1 lb egg noodles, or 6 baked potatoes (chicken stir-fry)`. A line starting with `"or "` in your output means the string was split — rejoin it.

#### 3b. Skip serving-suggestion lines

Some recipe sites pack non-ingredient guidance into the `recipeIngredient` array (`"Salad with Caesar, ranch, or bleu cheese dressing"`, `"Serve with crusty bread"`, `"Optional: lemon wedges"`). Drop any line that starts with `"Serve with"`, `"Salad with"`, `"Optional:"`, `"For serving"`, or reads as a suggestion rather than a measurable ingredient.

#### 3c. Skip pantry staples

This is a shopping list, not a recipe transcription. The user already owns:

- water (any form: `3 cups water`, `2 cups cold water`, `water for boiling`, `1 cup hot water`)
- salt, kosher salt, sea salt, table salt
- black pepper, white pepper, ground pepper
- all salt/pepper variants regardless of quantity — explicit measure (`2 teaspoons salt`), `to taste`, `a pinch`, `as needed` — all skipped
- tap-water-equivalent items (ice, etc.)

Drop these lines entirely. Other staples (oil, flour, eggs, milk, butter) stay — people run out of those and expect them on the list.

⚠️ Anti-example: agent emitted `3 cups water (chicken stir-fry)`, `2 teaspoons salt (chicken stir-fry)`, and `1/4 teaspoon ground black pepper (chicken stir-fry)` into Pantry. All three must be dropped. The test is: would a normal household NOT have this in the cabinet? If they would have it, skip. Water/salt/pepper are always skipped.

#### 3d. Consolidate duplicates into one line per purchase

The most important rule. Every line in the output is one thing the user buys — that is what makes the list usable in a store. If two recipes both call for "butter," that's ONE line with both quantities and both dishes annotated:

    5 tablespoons butter (pasta primavera 3 tbsp, chicken stir-fry 2 tbsp)

Same rule across all of:

- **Same recipe, same ingredient, multiple lines (sum):** `1 cup water + 2 cups water → 3 cups water` (then dropped by 3c since water is a staple)
- **Same recipe, ONE ingredient appears twice with different roles** (e.g. `bouillon paste` used in two steps of one recipe at `1 tsp` and `1 1/2 tbsp`): emit ONE line summing or listing both:
  `1 tsp + 1 1/2 tbsp bouillon paste (chicken stir-fry)`
- **Same ingredient across DIFFERENT recipes** (`1/2 tsp garlic powder (pasta primavera)` + `1 tsp garlic powder (chicken stir-fry)`): ONE line with both quantities and both dishes annotated:
  `1 1/2 tsp garlic powder (pasta primavera 1/2 tsp, chicken stir-fry 1 tsp)`

Match items by normalized name (lowercase, ignore minor descriptors like "thinly sliced," "fresh," "minced"). When in doubt, consolidate aggressively — one shopping line is better than two cluttering entries.

⚠️ Anti-examples from a real failed run — these are the concrete bugs to avoid:

- Two butter lines:
  `3 tablespoons butter (pasta primavera)`
  `2 tablespoons butter (chicken stir-fry)`
  Correct: ONE line —
  `5 tablespoons butter (pasta primavera 3 tbsp, chicken stir-fry 2 tbsp)`

- Two `bouillon paste` lines from the same recipe:
  `1 teaspoon bouillon paste (chicken stir-fry)`
  `1 1/2 tablespoons bouillon paste (chicken stir-fry)`
  Correct: ONE line —
  `1 tsp + 1 1/2 tbsp bouillon paste (chicken stir-fry)`

- Two garlic powder lines:
  `1/2 teaspoon garlic powder (pasta primavera)`
  `1 teaspoon garlic powder (chicken stir-fry)`
  Correct: ONE line —
  `1 1/2 tsp garlic powder (pasta primavera 1/2 tsp, chicken stir-fry 1 tsp)`

**Before finalizing each category, scan it for duplicates.** Two lines in the same category with the same item name means consolidation was missed — merge them.

### 4. Group by aisle

Combine all ingredients across the recipes, then bucket each into one of:

- **Produce** — fruits, vegetables, fresh herbs
- **Protein** — fresh/frozen meat, seafood, eggs, tofu
- **Dairy** — milk, cheese, yogurt, butter, cream
- **Refrigerated** — hummus, fresh salsa, tortillas in the fridge case, fresh pasta, anything else in a refrigerated case but not dairy or protein
- **Pantry** — oils, vinegars, spices, **grains (rice of all kinds incl. jasmine/basmati/brown, quinoa, oats, farro, barley, couscous, polenta), dried beans/lentils**, pasta, canned goods, condiments, sauces, broths/stocks, baking staples (flour, sugar, baking powder), nuts and seeds (shelf-stable), dried herbs/spices
- **Frozen** — anything explicitly frozen aside from protein
- **Bakery / Other** — bread, tortillas, anything else

If a bucket is empty, omit it from the output (don't emit empty headers).

⚠️ Anti-example: agent put `1¼ cups brown jasmine rice or long-grain brown rice — optional (lentil stew)` into **Refrigerated**. Rice — brown, white, jasmine, basmati, wild, any variety — is a shelf-stable grain and belongs in **Pantry**. The word "optional" in the line and the recipe name (stew) do not change the aisle. Same rule for quinoa, oats, lentils, dried beans, flour, sugar, broth, canned tomatoes — when in doubt about a shelf-stable dry/canned good, it's Pantry, not Refrigerated.

### 5. Return the list

The default output shape is a structured list the caller can render however they want:

    {
      "Produce": [
        "1 lb chicken thighs (chicken tacos)",
        "2 cloves garlic (chicken tacos, vegetable curry)"
      ],
      "Pantry": [
        "1 lb egg noodles, or 6 baked potatoes (chicken stir-fry)",
        "5 tablespoons butter (pasta primavera 3 tbsp, chicken stir-fry 2 tbsp)"
      ],
      ...
    }

If the caller asks for plain text instead, render as one ingredient per line, category headers on their own line, no leading bullet:

    Produce
    1 lb chicken thighs (chicken tacos)
    2 cloves garlic (chicken tacos, vegetable curry)

    Pantry
    1 lb egg noodles, or 6 baked potatoes (chicken stir-fry)
    5 tablespoons butter (pasta primavera 3 tbsp, chicken stir-fry 2 tbsp)

Always pair the list with a short summary:

- Recipes successfully fetched and parsed (count + names)
- Recipes that failed (URL + reason: paywall, timeout, no JSON-LD)
- Ingredients dropped as staples (count, not full list)
- Lines consolidated (count)

## Constraints

- Annotate every line with the dish in parens using the FULL dish name as it appears in the input (`(pasta primavera)`, `(chicken stir-fry)`) — never short tags like `(chicken)` or `(stew)`.
- A line in the output starting with `"or "` is always a bug — it means rule 3a was violated.
- Two lines in the same category with the same item name is always a bug — it means rule 3d was violated. Re-consolidate.
- Don't fabricate ingredients. If a recipe fetch fails, the recipe contributes nothing — say so in the summary.
- Don't normalize units silently. `1 cup` stays `1 cup`, not "8 fluid ounces."
