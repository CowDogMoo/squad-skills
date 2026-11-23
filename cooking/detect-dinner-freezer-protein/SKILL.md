---
name: detect-dinner-freezer-protein
description: Given a dish name (and optionally a recipe URL), determine what protein needs to come out of the freezer that morning, or that no protein is needed (vegetarian/vegan dish, or determination failed). Returns a normalized lowercase keyword (`chicken`, `salmon`, `meatballs`, `burgers`, ...) suitable for a freezer-reminder line like `Take out {protein} for tonight's dinner`. Use when asked what to defrost or thaw for tonight's dinner, or when building a morning freezer reminder from a meal plan.
---

# Detect dinner freezer protein

You are deciding what protein to take out of the freezer in the morning so it is thawed by dinner. Given a dish name (and optionally a recipe URL), return the normalized lowercase protein keyword, or `null` with a reason when nothing needs thawing.

This is a pure transformation: no side effects, no calendar writes, and no conversational prose. Whether the caller passes structured fields or asks a natural-language question (such as `"What do I need to defrost for chicken Tinga tacos tonight?"`), extract the dish name and optional URL and reply **only** with the three-line plain-text record defined under `# Output`. The caller owns rendering any reminder sentence such as `Take out {protein} for tonight's dinner`.

# Host-environment translation (READ FIRST)

Step 3 (URL fallback) is the only host-dependent path. Steps 1–2 are dish-name string matching and need no tools.

| Action | Squad / shell hosts | Claude Code / Desktop | Browser-MCP-only hosts |
|---|---|---|---|
| Fetch recipe page (Step 3) | `Bash curl -sL --max-time 10 <URL>` | `WebFetch <URL>` | `mcp__chrome__evaluate_script` with `fetch(url).then(r => r.text())` |

If your host has none of those (for example, a sandboxed environment with no shell, web, or browser tools), skip Step 3 and return `protein: null`, `source: skipped`, `reason: no fetch capability and dish name did not match`.

# Inputs

Callers invoke this skill in either of two shapes:

1. **Structured input** with `dish_name` (string) and optional `recipe_url` (string or `null`/empty).
2. **Natural-language question** naming tonight's dish (and optionally including a recipe URL). Strip conversational framing (`"tonight's"`, `"for dinner"`, `"what protein comes out of the freezer for"`) to isolate `dish_name`; set `recipe_url` to `null` when no URL is present.

# Output

Reply with **only** these three plain-text lines as your entire final message:

```text
protein: <lowercased keyword or null>
source: <specific | generic | url-fetch | skipped>
reason: <lowercased explanation>
```

Formatting rules for every response:

- **Three lines only, nothing else:** emit no greeting, no full-sentence prose before or after, no `Take out ...` reminder sentence, no JSON braces, and no Markdown code fences (` ``` `).
- **All lowercase, unquoted, and trimmed:** every character across all three lines must be lowercase (write `url`, not `URL`). Never wrap `protein` or any other value in double quotes (`"..."`), single quotes (`'...'`), backticks (`` `...` ``), or bold/italic markers (`**...**`, `*...*`). Trim all leading and trailing whitespace on every value and line.
- **Pluralization:** use plural for items stocked and thawed as count plurals (`meatballs`, `burgers`, `sausages`); use singular for cuts, birds, fillets, and shellfish keywords (`chicken`, `steak`, `pork`, `salmon`, `shrimp`).
- **Always populate `reason`** in plain lowercase words (avoid apostrophes or quotes):
  - When `protein` is matched (`specific`, `generic`, or `url-fetch`), state concisely how it was derived (for example, `matched specific keyword in dish name without url fetch`, `matched generic term in dish name without url fetch`, or `matched headline protein from recipe url`).
  - When `protein` is `null` (`skipped`), state why nothing needs thawing (see Step 4).

Anti-example (wrong: prose wrapper, uppercase letters, Markdown bold, and quotes):

```text
Take the **chicken** out of the freezer this morning so it's thawed by dinner. "Chicken Tinga tacos" names the protein directly.
```

Correct output:

```text
protein: chicken
source: specific
reason: matched specific keyword in dish name without url fetch
```

# Step-by-step (first match wins)

## 1. Specific protein keyword in the dish name (source = specific)

Case-insensitive substring match against `dish_name`, so plurals and compound words still match (`steaks` → `steak`, `porkchops` → `pork`). The one exception is `ham`, which matches only as a standalone word (`ham`, `hams`) so it never false-matches inside `champagne`, `hamburger`, or `graham`. Output the matched keyword lowercased, except `sausage` always outputs plural `sausages`:

- **Land meats**: `chicken`, `beef`, `steak`, `pork`, `bacon`, `sausage`, `ham`, `lamb`, `turkey`, `duck`
- **Fish & seafood**: `salmon`, `tuna`, `cod`, `halibut`, `tilapia`, `shrimp`, `prawn`, `scallop`

Keep the matched cut in its specific form. Do not generalize `steak` → `beef` or `bacon` → `pork`; the user is taking that specific item out of the freezer.

Worked examples:

- `"chicken Tinga tacos"` →

  ```text
  protein: chicken
  source: specific
  reason: matched specific keyword in dish name without url fetch
  ```

- `"pork belly bao"` →

  ```text
  protein: pork
  source: specific
  reason: matched specific keyword in dish name without url fetch
  ```

- `"grilled steak salad"` →

  ```text
  protein: steak
  source: specific
  reason: matched specific keyword in dish name without url fetch
  ```

## 2. Generic protein-bearing term in the dish name (source = generic)

When no Step 1 word matched, scan `dish_name` with the same case-insensitive substring match and map to the canonical form:

| Match (case-insensitive substring) | Output `protein` |
|---|---|
| `meatball` or `meatballs` | `meatballs` |
| `burger` or `burgers` | `burgers` |
| `fish` (including `swordfish`, `crawfish`; not `fish sauce` or `jellyfish`) | `fish` |
| `seafood` | `seafood` |

Do **not** fall through to a URL fetch when Step 2 matches; the dish name already resolved the protein.

Worked examples:

- `"smash burgers"` →

  ```text
  protein: burgers
  source: generic
  reason: matched generic term in dish name without url fetch
  ```

- `"weeknight fish stew"` →

  ```text
  protein: fish
  source: generic
  reason: matched generic term in dish name without url fetch
  ```

## 3. URL fallback (source = url-fetch)

Only run this when Steps 1 and 2 **both** miss **and** `recipe_url` is non-empty.

Fetch the recipe page and check for the primary animal protein in:

- `<title>` (often `"Sichuan Chicken Stir Fry | Example Blog"`)
- The schema.org JSON-LD `recipeIngredient` array, where the first 1–3 ingredients usually name the headline protein
- `<meta name="description">`

Re-run the Step 1 and Step 2 word lists against this text with the same case-insensitive substring matching and `ham` guard. If multiple proteins appear (for example, chicken broth in a beef recipe), pick the **headline** one: the recipe title and largest-quantity ingredient outrank minor flavorings.

Worked example:

- Input `{dish_name: "spicy stir fry", recipe_url: "https://example.com/sichuan-stir-fry"}` where fetch finds `<title>Sichuan Chicken Stir Fry</title>` and `1.5 lb chicken thighs` in JSON-LD →

  ```text
  protein: chicken
  source: url-fetch
  reason: matched headline protein from recipe url
  ```

If the fetch fails (paywall, timeout, network error), go to Step 4 with `could not determine protein from recipe link`. If the fetch succeeds and no animal protein appears in title, ingredients, or description, the dish is meatless; go to Step 4 with the vegetarian reason.

## 4. Skip: nothing freezer-bound (source = skipped)

Return `protein: null` and `source: skipped` with one of these lowercase `reason` values:

- `vegetarian - meatless dish needs no freezer thawing`: the dish name or fetched recipe is plainly vegetarian/vegan/meatless (for example, `"lentil soup"`, `"veggie pasta"`, `"mushroom risotto"`, `"chickpea curry"`, `"black bean tacos"`, `"egg fried rice"`, or a tofu dish). **Tofu, eggs, beans, lentils, chickpeas, and mushrooms never need morning freezer thawing in this workflow; do not hedge or add advice about frozen tofu or frozen vegetables.**
- `could not determine protein from recipe link`: Step 3 ran, and the fetch failed or the page did not clearly identify a protein.
- `no protein keyword in dish name and no recipe url to check`: Steps 1–2 missed on a non-obvious dish name (such as `"friday night special"`) and `recipe_url` was null/empty.
- `no fetch capability and dish name did not match`: Step 3 was needed, and the host lacks fetch tools.
- `not an animal protein`: the input refers to frozen non-protein prep such as `"frozen pizza dough"`.

Worked example:

- `"chickpea curry"` →

  ```text
  protein: null
  source: skipped
  reason: vegetarian - meatless dish needs no freezer thawing
  ```

# Edge cases

- **Two specific proteins in one dish** (`"chicken and shrimp paella"`): pick the first protein mentioned in the dish name (`chicken`), since `protein` holds a single keyword, and note the second in `reason` (`matched first specific keyword in dish name also mentions shrimp`).
- **Plant-based meat** (`"impossible burger"`, `"beyond sausage"`): treat as the matched word (`burgers` from Step 2, `sausages` from Step 1); the user still pulls that package from the freezer.
- **Stocks, broths, and condiments** (`chicken broth`, `beef stock`, `fish sauce`, `oyster sauce`) when no headline meat or seafood exists: never count as freezer protein.
- **Frozen non-protein prep** (`"frozen pizza dough"`): out of scope; return `protein: null`, `source: skipped`, `reason: not an animal protein`.

# Hard rules

- First match wins, in order: Step 1 → Step 2 → Step 3 → Step 4.
- Step 3 (URL fetch) runs **only** when Steps 1 and 2 both miss and `recipe_url` is provided.
- Output **only** the three-line `protein` / `source` / `reason` record: no prose sentences, no Markdown formatting (`**`, `*`, `` ` ``, ` ``` `), no JSON braces, and no quotes (`"`, `'`).
- Every character in the output is lowercase, with no leading or trailing whitespace on any value or line.
- Every `null` result must include `source: skipped` and a specific lowercase `reason`.
- Never infer or guess a protein you did not observe in the dish name or fetched recipe.

# Related skills

- `extract-recipe-grocery-list`: the other consumer of dish names + recipe URLs; for ingredient extraction, not protein detection
