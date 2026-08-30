---
name: plan-weekly-dinners
description: Propose a balanced weekly meal plan — exactly 5 weeknight dinner candidates for human review — enforcing household policy on protein mix, cuisine variety, tomato limit, sesame-allergy handling, complete meals, and weeknight time budget, and emitting a structured JSON-able record per candidate for a downstream review page and inventory checker. Use when the user says "plan my dinners for the week", "make a weekly meal plan", "plan next week's dinners", or "what should we eat this week" and wants a balanced, constraint-checked week. For a plain recipe round-up with no weekly balancing ("dinner ideas", "more recipes", "recipe round-up"), use weekday-dinner-recipes instead.
---

# Plan Weekly Dinners

You are proposing five weeknight dinner candidates for human review.
The goal is not to auto-decide perfectly — it is to propose meals that
fit the household's actual cooking bandwidth, food preferences,
ingredient constraints, and desired variety, while clearly surfacing
tradeoffs. The human picks; you propose and annotate.

The deliverable is host-agnostic structured data: a JSON-able list of
per-candidate records (see "Per-candidate record" below) plus a
whole-week check summary. A downstream review page displays the
records and an inventory checker consumes the ingredient quantities —
they are consumers of the output, not dependencies of this skill. You
are done when the five annotated candidates and the check summary are
returned.

If the user just wants recipe ideas with no weekly balancing, that is
the `weekday-dinner-recipes` skill, not this one.

## Host-environment translation

Candidate sourcing needs web search and page fetch on any host.
Resolve each action to whatever your host supports:

| Action | Squad / shell hosts | Claude Code / Desktop | Browser-MCP-only hosts |
|---|---|---|---|
| Search the web for candidates | `WebSearch` | `WebSearch` | `WebSearch` |
| Fetch a recipe page | `Bash`: `curl -sL -A "Mozilla/5.0" --max-time 15 URL` | `WebFetch URL` | browser MCP `get_page_text` |
| Verify a URL is live | `Bash`: `curl -sIL -o /dev/null -w "%{http_code}" -A "Mozilla/5.0" --max-time 15 URL` | `WebFetch` (treat a non-empty body as live) | browser MCP `navigate`, then check the page |

Anti-bot note: some sites return `403` to plain `curl` but render fine
via `WebFetch` or a real browser (the source catalog flags which). Try
the richer fetch path before declaring a link broken. A successful
fetch from any method is sufficient; a `404` from any method
disqualifies the recipe.

## Inputs

The user invocation may include:

- A dinner count for the week (default 5).
- Week notes ("we're out Thursday", "make Monday the quick one").
- Extra constraints ("no seafood this week", "use up the tofu").
- Vetoes or repeats ("not tacos again", "keep the gochujang bowls").

Household policy below holds unless the user explicitly overrides a
piece of it for this week. Treat the sesame-allergy rule as standing
policy: only an explicit user statement relaxes it, never an
inference from other instructions.

## Step-by-step

### 1. Collect the week's inputs

Note any count changes, vetoes, and which nights need the quick meal.
No inputs is normal — the defaults below fully specify a week.

### 2. Choose sources

Read `references/sources.md` — the curated catalog of sites, why each
is on the list, and per-site fetch quirks. Pinch of Yum is the strong
positive reference for the household's preferred style; RecipeTin
Eats is deprioritized. Other sources are welcome when they fit the
preferences. Don't search arbitrary sites first — the catalog encodes
which sites publish complete ingredient lists with quantities, which
this skill's output contract depends on.

### 3. Sketch the week, then search

Sketch the five slots against the weekly shape and cuisine variety
sections before searching — for example: 1 Latin-inspired vegetarian,
1 Asian-inspired tofu, 1 chicken sheet-pan, 1 quick shrimp or salmon,
1 flexible/indulgent. Then search per slot with site-scoped queries:

- `site:pinchofyum.com weeknight lentil curry`
- `site:budgetbytes.com black bean tacos`
- `site:thewoksoflife.com quick chicken stir fry`

Generate 8–10 candidates so five survive screening.

### 4. Screen each candidate on the live recipe page

Fetch the actual page. Pull the total time, active prep time (when
shown), and the full ingredient list with quantities from the page —
never from memory. A recipe you can't fetch doesn't ship. Then screen
against every household policy section below and drop or flag
accordingly.

### 5. Build one record per surviving candidate

Fill all fields of the per-candidate record. Partial records break
the downstream review page and inventory checker; if a field is
genuinely unavailable (e.g. the page shows no active prep time), say
so in the field rather than omitting it.

### 6. Run the whole-week checks

Evaluate the five as a set (see "Whole-week checks"). A single miss
can ship if it is surfaced as an explicit tradeoff — the shape is a
target, not a quota. If the week fails several checks, regenerate
before presenting it.

### 7. Present and offer follow-ups

Return the records and the check summary, flagging anything that
needs a human call (a 45–60 minute recipe, a tomato ambiguity, a
sesame component). End with a soft offer: once picks are approved,
the `extract-recipe-grocery-list` skill can turn the chosen recipe
URLs into a deduplicated grocery list.

## Household policy

### Weekly shape

Aim for:

- 5 dinners total
- 2 to 3 vegetarian or vegan dinners
- 1 chicken dinner
- 1 flex dinner — vegetarian, chicken, salmon, shrimp, or another
  suitable option
- Minimize beef overall
- Avoid pork-chop-style meals and similar meat-centric dinners that
  don't fit the household's usual cooking style

This is a target, not a rigid quota. The week should feel balanced as
a whole.

### Complete meals

Prefer meals that feel like complete dinners rather than isolated
protein preparations. Each proposed meal must either:

- already include protein + vegetables + a satisfying starch or
  equivalent component, or
- explicitly include very easy sides that complete it — rice plus
  cucumber salad, roasted vegetables, flatbread, potatoes, and the
  like.

Never propose a bare meat preparation and leave the user to figure
out the rest of dinner.

### Time budget

Weeknight practicality is a core requirement. Prefer recipes with
total elapsed time around 45 minutes or less. Recipes in the 45 to 60
minute range are allowed, but must be clearly flagged as longer so
the user can approve them knowingly — an unflagged 60-minute dinner
is how trust in the plan erodes.

Exclude recipes that require:

- long stovetop simmers
- several labor-intensive stages before a simmer or braise
- starting dinner hours before mealtime
- three-hour total cook windows
- extensive sear-then-build-then-simmer workflows

Marinades are acceptable when they are flexible and easy to fit into
the day — the marinade can happen while other prep is underway, or
earlier with little effort. A rigid "marinate exactly 4 hours ahead"
recipe fails the same test as an early-start braise.

### Effort distribution

- Include at least one genuinely quick dinner that works on an
  exhausted night: roughly 25 minutes or less.
- Allow up to one heavier or more indulgent dinner per week — pasta,
  a richer cheesy dish, or another comfort-food option.
- The remaining dinners should feel fresh, balanced, and satisfying
  rather than heavy.

### Flavor and style

Prioritize flavorful food with good sauces, interesting seasoning,
and enough substance to feel satisfying. Strongly favor meals built
around:

- beans and lentils
- tofu
- vegetables
- chicken
- shrimp or salmon when appropriate
- grains, noodles, potatoes, rice, or other satisfying carbs

Avoid weeks dominated by cream, cheese, heavy pasta, or meat-heavy
meals. Equally, don't optimize for austere "healthy" food that feels
like rabbit food — the meals should feel delicious first, while still
being balanced. Saucy beats spartan.

### Cuisine variety

The five-meal set should span cuisines and flavor profiles rather
than clustering in one lane. A good target:

- 1 Latin-inspired meal
- 1 to 2 Asian-inspired meals, preferably from different traditions
  or flavor profiles rather than nearly identical dishes
- up to 1 Italian or pasta-oriented meal
- 1 straightforward sheet-pan, roast, meat-and-veg, or similarly
  simple dinner
- 1 flexible slot

Don't force these categories mechanically — they exist to prevent
repetitive weeks, not to be filled by checkbox.

### Tomato limit

Tomato-heavy meals appear no more than once per week, because tomato
can cause heartburn. Count meals with meaningful amounts of tomato,
tomato sauce, crushed tomatoes, tomato paste, or similar tomato-heavy
bases toward this limit. Small incidental quantities may be
acceptable — but if there is any ambiguity about whether a meal
counts, surface it for review instead of deciding silently.

### Sesame allergy

A household member has a sesame allergy. Sesame is not an automatic
exclusion: a recipe is acceptable when sesame is isolated in a
removable component — a sauce, dressing, topping, or garnish that can
be omitted from the portion served to the household member with the
allergy.

Whenever sesame appears anywhere in a recipe:

- flag it clearly,
- identify exactly which component contains it,
- state whether that component is fully removable, and
- reject the recipe if sesame is integrated throughout the dish in a
  way that cannot be cleanly separated (sesame oil stirred into the
  main sauce is integrated; sesame seeds sprinkled on top are not).

Never silently assume sesame can be omitted. This is an allergy, not
a preference — a wrong guess here has real consequences, so an
uncertain case is a rejection or an explicit flag, never a quiet
pass.

### Pantry floor and quantities

Do not assume the household has everything except unusual
ingredients. Only true always-on-hand basics are excluded from
inventory checking:

- salt
- black pepper
- basic cooking oil

Everything else is inventory that may need checking — produce, meat
and seafood, canned goods, tomato paste, mayonnaise, soy sauce,
oyster sauce, other sauces and condiments, rice, noodles, grains,
beans, dairy, herbs, and spices beyond that narrow always-on-hand
set.

Always preserve required quantities ("2 cans chickpeas", "1 lb
salmon") so the inventory checker can determine whether the household
has *enough*, not merely whether the ingredient exists.

## Per-candidate record

Return every field for every candidate, as structured data the
review page can display:

1. Recipe title
2. Source (site name)
3. Source URL
4. Short description
5. Cuisine / flavor profile
6. Classification: vegetarian / vegan / chicken / flex
7. Total elapsed time
8. Active prep time, when the page provides it
9. Speed class: quick / standard / longer
10. What makes the meal complete
11. Suggested easy sides, if the main recipe is incomplete on its own
12. Tomato presence, and whether it counts toward the weekly
    tomato-heavy limit
13. Sesame presence: the exact component and whether it is removable
14. Any timing gotchas (marinade window, a sauce that needs the rice
    started first, a long oven preheat)
15. Full ingredient list with quantities, excluding only the pantry
    floor (salt, black pepper, basic cooking oil)
16. A one-line explanation of the role this meal plays in the week
    ("the quick night", "the one indulgent dinner")

## Whole-week checks

Before returning the five candidates, evaluate the set as a whole:

- Is there at least one very quick meal (roughly 25 minutes)?
- Is there no more than one heavy / indulgent meal?
- Are 2 to 3 meals vegetarian or vegan?
- Is there roughly one chicken dinner and one flex dinner?
- Is beef minimized?
- Is there cuisine variety?
- Is there no more than one tomato-heavy dinner?
- Are the meals complete dinners, or paired with clear easy sides?
- Are any 45 to 60 minute meals clearly marked?
- Have long-simmer / multi-stage weeknight projects been excluded?
- Are sesame-containing recipes separable and clearly flagged?

If the week fails several of these checks, regenerate before
presenting it. A single miss may ship only when it is surfaced as an
explicit tradeoff for the human to accept.

## Anti-patterns

- Annotating a recipe from memory. Time, ingredients, and sesame
  content come from the live page — model recall of a recipe is
  routinely wrong about exactly the fields the checker needs.
- Assuming sesame is removable without checking which component it
  lives in.
- Dropping quantities from the ingredient list. "Chickpeas" is
  useless to an inventory checker; "2 cans chickpeas" is the point.
- Proposing a bare protein and calling the sides someone else's
  problem.
- Letting a 50-minute recipe through unflagged because it "seemed
  close enough" to 45.
- Padding to five with a candidate that failed screening. Go back to
  step 3 and source a replacement instead of shipping a silent dud —
  and if a slot genuinely can't be filled, say so explicitly.
