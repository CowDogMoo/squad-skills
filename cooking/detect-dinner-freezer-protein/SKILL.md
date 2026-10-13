---
name: detect-dinner-freezer-protein
description: Given a dish name (and optionally a recipe URL), determine what protein needs to come out of the freezer that morning, or that no protein is needed (vegetarian/vegan dish, or determination failed). Returns a normalized lowercase keyword (`chicken`, `salmon`, `meatballs`, `burgers`, ...) suitable for a freezer-reminder line like `Take out {protein} for tonight's dinner`. Use when asked what to defrost or thaw for tonight's dinner, or when building a morning freezer reminder from a meal plan.
---

# Detect dinner freezer protein

You are deciding what to take out of the freezer in the morning so it's thawed by dinner. The caller has a dish name (e.g. `bang bang salmon`, `chicken Tinga tacos`, `tofu stir fry`) and optionally a recipe URL. Output is a single normalized protein keyword the caller plugs into a reminder, or `null` with a reason when no protein needs thawing.

This is a pure transformation — no side effects, no calendar writes. The caller decides what to do with the result.

# Host-environment translation (READ FIRST)

Step 3 (URL fallback) is the only host-dependent path. Steps 1–2 are dish-name string matching and need no tools.

| Action | Squad / shell hosts | Claude Code / Desktop | Browser-MCP-only hosts |
|---|---|---|---|
| Fetch recipe page (Step 3) | `Bash curl -sL --max-time 10 <URL>` | `WebFetch <URL>` | `mcp__chrome__evaluate_script` with `fetch(url).then(r => r.text())` |

If your host has none of those (extremely restricted environment), skip Step 3 and return `null` with reason `"no fetch capability — dish name didn't match"`.

# Inputs

    {
      dish_name: string,                  # e.g. "bang bang salmon"
      recipe_url: string | null           # may be null/missing/empty
    }

# Output

    {
      protein: string | null,             # lowercased keyword, or null
      source: "specific" | "generic" | "url-fetch" | "skipped",
      reason: string | null               # human-readable; required when protein is null
    }

The `protein` value drops into a sentence like `Take out {protein} for tonight's dinner`. Use plural for ingredients that read naturally as plural (`meatballs`, `burgers`, `sausages`); singular for everything else (`chicken`, `salmon`).

# Step-by-step — first match wins

## 1. Specific protein keyword in the dish name (source = "specific")

Case-insensitive substring match against the dish name. The matched word becomes the protein verbatim (lowercased).

Word list:

- **Land meats**: chicken, beef, steak, pork, bacon, sausage, ham, lamb, turkey, duck
- **Fish & seafood**: salmon, tuna, cod, halibut, tilapia, shrimp, prawn, scallop

Examples:

- `"chicken Tinga tacos"` → `chicken`
- `"bang bang salmon"` → `salmon`
- `"pork belly bao"` → `pork`
- `"grilled steak salad"` → `steak`

The matched word stays in its specific form — don't generalize `steak → beef` or `bacon → pork`; the user is taking *that* item out of the freezer.

## 2. Generic protein-bearing term in the dish name (source = "generic")

When no Step 1 word matched, scan for these. Map to the canonical plural/singular:

| Match (case-insensitive) | Output |
|---|---|
| `meatball` or `meatballs` | `meatballs` |
| `burger` or `burgers` | `burgers` |
| `sausages` (alone — `sausage` already caught in Step 1) | `sausages` |
| `fish` (not preceded by `cat`, `jelly`, etc.) | `fish` |
| `seafood` | `seafood` |

Examples:

- `"harissa meatball"` → `meatballs` (don't fall through to URL fetch — the name tells you)
- `"smash burgers"` → `burgers`
- `"weeknight fish stew"` → `fish`

## 3. URL fallback (source = "url-fetch")

Only run this when Steps 1–2 BOTH miss AND `recipe_url` is non-empty.

Fetch the recipe page and look for the primary animal protein in:

- `<title>` (often "Chicken Tinga Tacos | Foo Blog")
- The schema.org JSON-LD `recipeIngredient` array — the first 1–3 ingredients usually name the headline protein
- `<meta name="description">`

Re-run the Step 1 word list against this text; same lowercased-match semantics. If multiple proteins are mentioned (e.g. chicken broth in a beef recipe), pick the **headline** one — the recipe title and the largest-quantity ingredient outrank a small flavor add.

Worked examples:

- Input: `{dish: "spicy stir fry", url: "https://example.com/sichuan-stir-fry"}`. Fetch finds `<title>Sichuan Chicken Stir Fry</title>` and `1.5 lb chicken thighs` in JSON-LD → `chicken` (source: `url-fetch`).
- Input: `{dish: "harissa meatball", url: "..."}` — Step 2 already matched `meatballs`; do NOT fetch the URL.

If fetch fails (paywall, timeout, network error), return `null` with reason `"couldn't determine protein from recipe link"`.

If the fetch succeeds but no protein is found anywhere in title/ingredients/description, that means the dish is genuinely vegetarian/vegan — go to Step 4.

## 4. Skip — nothing freezer-bound (source = "skipped")

Return `{protein: null, source: "skipped", reason: <one of below>}`:

- `"vegetarian"` — the dish name (or fetched recipe) is plainly meatless. Examples: `"tofu stir fry"`, `"lentil soup"`, `"veggie pasta"`, `"mushroom risotto"`, `"chickpea curry"`. **Tofu, eggs, beans, lentils, chickpeas, mushrooms — none need freezer thawing.**
- `"couldn't determine protein from recipe link"` — Step 3 was attempted but the fetch failed.
- `"no protein keyword in name, no recipe URL to check"` — Steps 1–2 missed and `recipe_url` was null/empty.

The caller will surface this reason in its summary. Be specific so the user can correct the dish name or attach a URL for next week.

# Edge cases

- **Two specific proteins in one dish** (`"surf and turf"`, `"chicken and shrimp paella"`): take the first one mentioned in the dish name. Both need thawing, but the caller's freezer-reminder template only fits one — log a note. (Future improvement: support a list output.)
- **Plant-based "meat"** (`"impossible burger"`, `"beyond sausage"`): treat as the matched generic word (`burgers`, `sausages`). The user still pulls something from the freezer; the keyword is what's on the package.
- **Frozen prep that isn't an animal protein** (e.g. `"frozen pizza dough"`): not in scope for this skill. Return `null` with reason `"not an animal protein"` if the recipe makes it obvious.
- **Stock / broth mentions** in the fetched recipe (`chicken broth`, `beef stock`) when no headline meat exists: do NOT count as protein. Chicken broth alone doesn't mean chicken comes out of the freezer.

# Hard rules

- First match wins, in order: Step 1 → Step 2 → Step 3 → Step 4.
- Step 3 (URL fetch) ONLY runs when 1 and 2 both miss. Don't waste a network call when the dish name already answered the question.
- Output `protein` is lowercase. No leading/trailing whitespace. No quotes.
- A `null` result MUST include a `reason`. The caller surfaces it.
- Don't infer a protein you didn't see. If the answer is uncertain, return `null` with reason `"couldn't determine protein from recipe link"` — better a missed reminder than a wrong one.

# Related skills

- `extract-recipe-grocery-list` — the other consumer of dish names + recipe URLs; for ingredient extraction, not protein detection
