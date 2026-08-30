# Recipe sources for weekly planning

The catalog for `plan-weekly-dinners`. It optimizes for what this
skill needs from a page: the household's flavor style, a complete
ingredient list with quantities (the inventory checker depends on
it), honest time estimates, and complete-meal orientation. It is
deliberately self-contained — other cooking skills keep their own
lists for their own purposes.

## Calibration point — Pinch of Yum

Pinch of Yum is the strong positive reference for the preferred style
of recipe: flavorful, approachable, saucy, weeknight-friendly, and
often good at pairing mains with simple sides. When you're unsure
whether a candidate fits the household's style, ask whether it would
look at home on Pinch of Yum. Reach for it first when sketching the
week.

## Deprioritized — RecipeTin Eats

Deprioritize RecipeTin Eats: recent recipes from that source have not
been landing well for flavor. It is not banned — a specific well-loved
recipe can still earn a slot — but don't reach for it by default, and
prefer another catalog site when an equivalent dish exists elsewhere.

## Good fits

| Site | Why it's here | Notes |
|---|---|---|
| Pinch of Yum | The calibration point (above): saucy, weeknight, mains-plus-easy-sides | Clean recipe cards, full quantities. |
| Budget Bytes | Best-in-catalog for beans and lentils; cheap, honest step timing | Quantities always explicit — ideal for the inventory checker. |
| Cookie and Kate | Vegetarian-only; strong for the 2–3 veg/vegan slots | Whole-food leaning but flavorful, not austere. |
| The Mediterranean Dish | Vegetable-forward, saucy, good sheet-pan dinners | Many mains are tomato-based — check the tomato limit per pick. |
| The Woks of Life | Deep, authentic bench for a distinct Asian slot | Frequent sesame: seeds as garnish are removable, but sesame oil stirred into a sauce is integrated — check each recipe's component. |
| Damn Delicious | Reliably fast — good hunting for the ~25-minute quick slot | Returns `403` to plain `curl`; fetch via `WebFetch`, a browser MCP, or `curl` with a real browser User-Agent. |
| Half Baked Harvest | Big flavor, good for the one indulgent slot | Skews cream/cheese-heavy; real time often exceeds the stated time — read the steps before trusting the card. |
| The Modern Proper | Complete-meal orientation; solid chicken mains | Sides are usually built into the recipe. |
| Once Upon a Chef | Dependable chicken and simple-roast dinners | Classic technique; occasionally longer than weeknight — check total time. |
| Skinnytaste | Useful for quick and light picks | Can skew austere — pick from the saucier end of the site. |

## Not usable for this skill

| Source type | Why |
|---|---|
| Roundup posts / listicles ("15 Best Weeknight Dinners") | No single ingredient list — nothing for the record or the checker. |
| TikTok / Instagram / video-only recipes | No written quantity list; timing unverifiable. |
| Pinterest | Aggregator, not a source — follow through to the real site instead. |

## Fetch quirks

- **Damn Delicious**: `403`s plain `curl`. Use `WebFetch`, a browser
  MCP, or pass a real browser UA such as
  `-A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"`.
- **WPRM recipe cards** (most sites above): the card's "total time"
  sometimes omits a marinade or rest window mentioned only in the
  prose steps. Read the steps before classifying a recipe as quick,
  standard, or longer — the card alone can under-count.
- **Serving sizes vary** across sites. Always record quantities
  exactly as the page states them, along with the page's serving
  count, so the inventory checker works from real numbers.
