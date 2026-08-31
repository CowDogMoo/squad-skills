---
name: plan-weekly-dinners
description: Plan one week of household dinners in Mealie and run the week ritual — import candidate recipes by URL, tag them with the household's constraint vocabulary, honor the 28-day reuse cooldown, read BOTH people's ratings with their own API tokens, write the Mon–Fri dinner mealplan, send the week to Signal for approval, and send the still-needed groceries once the household has ticked off what it already has. Use for "plan our dinners for the week", "what are we eating next week", "redo Thursday", "add this recipe to the plan", "send the week", "send the grocery list", or anything that produces a whole week rather than a list of ideas. Candidate discovery belongs to weekday-dinner-recipes; this skill decides the week, writes it down, and gets it in front of both people.
---

# Plan weekly dinners

You are turning a batch of candidate recipes into one committed week of dinners for a two-adult, one-small-child household, and writing it into Mealie so the calendar, the shopping list, and the review page all read from the same place.

You are not a recipe search engine. Finding well-rated, link-verified, season-appropriate candidates is the **weekday-dinner-recipes** skill's job — call it, or use the batch it already produced. This skill starts once there are candidates and ends with a grocery list on somebody's phone: five dinners on the Mealie mealplan, tagged, with the tradeoffs written down, sent to Signal for approval, and — after the household has said what it already has — the shopping list that is actually left.

## Mealie is the substrate

Everything lives in Mealie at `https://mealie.techvomit.xyz` (v3.24, OIDC via authentik, one group `Home`, one household `Family`).

| What | Where |
|---|---|
| Recipes | imported **by URL** (`POST /api/recipes/create/url`) so each keeps a live `orgURL` |
| Constraint flags | Mealie tags, from a fixed vocabulary (below) |
| The week | dinner entries on `/api/households/mealplans` |
| Reuse cooldown | Mealie's own query language, `lastMade <= "$NOW-28d"` |
| Ratings | per user; only that user's token can read them |
| Groceries | the `Groceries` shopping list |
| The week in front of people | Signal, via the bridge in LXC 109 |
| Feedback, blocks, priors | `history.json` in `$XDG_STATE_HOME/meal-planner/` — outside every repo |

Home Assistant mirrors the mealplan and the shopping list, so anything written here shows up on the kitchen dashboard without a second write.

## Host-environment translation

| Action | This host (Claude Code / shell) | Notes |
|---|---|---|
| Talk to Mealie | `node scripts/*.mjs` | **Node's own sockets are blocked here.** `fetch()` gets EHOSTUNREACH on the LAN; `curl` is proxied through. Every request in `scripts/mealie.mjs` shells out to curl. Do not "modernise" it. |
| Read a token | `sh -c '. ~/.op-token; op read "op://automation/mealie-api-tokens/<field>"'` | Never write a token to a file, never paste one into a commit. |
| Find candidates | the `weekday-dinner-recipes` skill | It verifies ratings and links; this skill trusts that verification. |
| Talk to Signal | `node scripts/send-summary.mjs`, `node scripts/finalize-week.mjs` | Same curl constraint, same reason. A send is only real once the bridge hands back a `timestamp`. |

## Scripts

    scripts/mealie.mjs           shared adapter: auth, request, import-by-URL, tags, mealplan, ratings, shopping list, flag derivation
    scripts/history.mjs          the history store and the MEAL-HISTORY-SPEC scoping rules
    scripts/propose-week.mjs     the whole flow; --apply to write, otherwise a dry run
    scripts/read-ratings.mjs     both people's ratings, separately (--json for planning context)
    scripts/scope-feedback.mjs   filter candidates through the household's scoped blocks
    scripts/record-feedback.mjs  record one person's vote, a scoped block, and that a meal was cooked
    scripts/verify-cooldown.mjs  prove the cooldown query still excludes a recipe made today
    scripts/signal.mjs           the Signal bridge: mode check and one send that returns a real timestamp
    scripts/send-summary.mjs     the proposal message — the week, the three warnings, the at-a-glance counts
    scripts/finalize-week.mjs    the grocery message — only what is still unticked, grouped by aisle

## The constraint tag vocabulary

Exact slugs. Anything outside this list is somebody's personal tag and is left alone.

| Group | Slugs | Where it comes from |
|---|---|---|
| Timing | `quick` (≤30 min) · `standard` (31–45) · `longer` (>45) | derived from `totalTime` |
| Band callout | `45-60` | derived: total time is 45 to 60 minutes inclusive |
| Flags | `tomato` · `sesame` | derived from the recipe's own ingredients |
| Role | `vegetarian` · `vegan` · `chicken` · `flex` · `indulgent` | the planner's judgement, one per recipe |

**Derive the flags; never type them.** `constraintTagsFor()` reads the recipe back out of Mealie and decides from what Mealie actually stored, so a tag can never quietly disagree with the ingredient list. The two flags that matter:

- **tomato** means tomato-*heavy*: the processed base forms — canned, crushed, diced, whole peeled, San Marzano, fire-roasted, paste, purée, sauce, passata, marinara, sun-dried, ketchup — **and** fresh tomatoes in volume, because shakshuka built on six medium tomatoes is as tomato-heavy as one built on a tin and reads as neither with a base-form-only test. A sliced tomato on top for garnish does **not** count, and neither does half a cup of grape tomatoes in a noodle salad — if they did, the "at most one tomato-heavy meal a week" target would fire every week and mean nothing.
- **sesame** is a child-safety flag and is deliberately broad: sesame seeds, sesame oil, tahini, za'atar, gomashio, halva. For every sesame meal the summary must name the exact component and say whether it can be left out, because the child-safe portion has to be separated before that component goes in.

If Mealie imported a recipe with no usable `totalTime`, fix it before tagging — a missing total time means the timing tag and the `45-60` callout cannot be derived at all, and an untagged dinner is worse than a slow one:

    curl -X PATCH -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
      -d '{"totalTime":"40 Minutes"}' "$MEALIE/api/recipes/<slug>"

## The 28-day reuse cooldown

The cooldown is a Mealie query, not arithmetic in this skill:

    lastMade <= "$NOW-28d"

Mealie resolves `$NOW` server-side, so the planner never computes a date and never drifts from the server's clock. `candidatesOffCooldown()` runs exactly that filter; `RECENTLY_MADE_QUERY` (`lastMade > "$NOW-28d"`) is its complement and is what tells you which candidate URLs to drop from this week's pool. A recipe that has never been made has no `lastMade` and is treated as long ago — "new recipe", eligible.

**Write `lastMade` only through `PATCH /api/recipes/<slug>/last-made`.** Mealie v3 keeps `lastMade` per household. A plain `PATCH /api/recipes/<slug>` with a `lastMade` field changes what `GET` hands back but leaves the household row untouched, so the cooldown query goes on treating the recipe as never made. Verified against v3.24.0: after a plain PATCH, `GET /api/households/self/recipes/<slug>` still reports `lastMade: null`, and the recipe is still returned by the cooldown query. `PUT /api/recipes/<slug>` with a full body and `POST /api/recipes/timeline/events` do not write it either. Use `markMade()` and this stays right.

Because that failure mode looks exactly like success from every read, `scripts/verify-cooldown.mjs` exists: it creates a throwaway recipe, marks it made today, asserts the cooldown query excludes it *and* the inverse query returns it, then deletes the probe. Run it after every Mealie upgrade.

## Per-person ratings are a hard requirement

Mealie only lets a token read **its own** user's ratings. There is no household ratings endpoint, and you must not invent one by averaging.

So the planner holds one long-lived API token **per account**, in 1Password item `mealie-api-tokens` (vault `automation`):

| Field | Account |
|---|---|
| `jayson-planner` | jayson — also the token the planner acts as for imports, tags and mealplan writes |
| `amanda-planner` | amanda |
| `amanda-password` | recovery password for her Mealie account (she normally signs in with authentik SSO) |

`read-ratings.mjs` reads each person's ratings with **each person's own token** and keeps them apart. Both votes are surfaced separately, always. Agreement makes a household favorite; disagreement is a per-person preference signal and is exactly the thing an average destroys. A single blended "household rating" is a spec violation, not a simplification.

Amanda's Mealie username and email match her authentik identity character for character (`amanda` / `amandajean119@gmail.com`). Keep it that way — if they drift, her next SSO login creates a *second* account and silently orphans the token her votes are read with.

## The week shape

From MEAL-SPEC, in priority order:

1. **A quick night.** At least one dinner at 30 minutes or less.
2. **At most one tomato-heavy meal.** Two is allowed but must be surfaced as a warning before approval, not smuggled through.
3. **Protein variety.** The role tag is a menu classification, not a protein — two `flex` nights can both be fish. Track the protein separately or a week of salmon, cod and shrimp scores as "varied".
4. **At least one vegetarian night.**
5. **Not a pile of `45-60` dinners.** Anything in that band needs explicit human approval, so one is a feature and three is a chore.
6. **Don't let one source take the week.** Three of five dinners off one blog is a narrow week however good the ratings are.
7. **Keep the whole week under about three and a half hours of cooking.**

`scoreWeek()` in `propose-week.mjs` states every one of these as an explicit term, and the tradeoffs it had to make come back in `tradeoffs` so the review page can say *why* this week and not another.

Day order: shortest dinner on Monday, longest on Friday.

## history.json — feedback, scoped

`$XDG_STATE_HOME/meal-planner/history.json` (in practice `~/.local/state/meal-planner/history.json`). Per-machine runtime state, deliberately outside every repo.

    recipes          canonical URL -> { title, source, dish, cuisine, timing, tomato, sesame,
                                        proposedAt, cookedAt, votes: { jayson, amanda }, ... }
    blocks           [ { id, person, reason, scope, target, recordedAt, confidence } ]
    sourcePriors     source -> { up, down, prior, samples, confidence }
    reasonVocabulary the 12 structured reasons from MEAL-HISTORY-SPEC
    ingredientSignals / workflowSignals   repeated-signal counters

`votes` is a **map keyed by person**. Never one household score.

### Scope the negative feedback to the reason

A generic thumbs down means "not this exact recipe" and nothing more. Only an explicitly broad reason reaches wider:

| Reason | Reaches |
|---|---|
| `i-did-not-like-this-recipe` | that one URL |
| `i-do-not-like-this-dish` | that dish, across sources |
| `i-do-not-like-a-specific-ingredient` | recipes where it is a meaningful component — **not** adjacent ingredients (a fennel block does not touch star anise) |
| `bad-source` | that source |
| `too-repetitive` | that dish or cuisine |
| everything else (`too-much-work`, `took-too-long`, `too-heavy`, `not-flavorful-enough`, `too-spicy`, `did-not-work-for-our-household`, `other`) | that one URL |

A block that reaches wider than its reason licenses is **advisory**: the candidate stays in play with a penalty until the household says it a second time. One rejected tofu recipe is not a tofu ban.

    node scripts/scope-feedback.mjs --candidates pool.json           # blocks from the store
    node scripts/scope-feedback.mjs --candidates pool.json --blocks other.json

When `--blocks` is given it is the whole world — the store's own blocks are not mixed in, because the caller is asking what survives *those* blocks.

## The week ritual

The week is not finished when the mealplan is written. It is finished when two
people have seen it, changed what they wanted to change, said what is already in
the cupboard, and been handed a list they can shop from.

| Step | What runs | Who acts |
|---|---|---|
| 1. Propose | `propose-week.mjs --week … --apply` | the planner writes five dinners into Mealie |
| 2. Summary | `send-summary.mjs --week …` | the household reads the week on their phones |
| 3. Edit | Mealie itself, or another `propose-week.mjs` run | the household swaps whatever it does not want |
| 4. Ingredient check | the Mealie app, the kitchen dashboard's todo card, or `--have` | the household ticks off what it already has |
| 5. Finalize | `finalize-week.mjs` | the still-needed groceries go to Signal |

**The order is the point.** MEAL-SPEC generates the grocery list *after* the
ingredient check, never before, and steps 4 and 5 do not collapse into one. A
list that asks the household to buy the olive oil they told you they had is a
list they stop reading, and then the whole ritual is theatre.

### The summary message

    node scripts/send-summary.mjs --week 2026-08-31                          # send it
    node scripts/send-summary.mjs --week 2026-08-31 --dry-run --print-body   # read it first
    node scripts/send-summary.mjs --from-json week.json --print-body         # rehearse a week Mealie does not hold

It reads the week back out of Mealie, so what goes to Signal is what Mealie
actually holds rather than what the planner meant to write. Every meal is named,
followed by three warnings and then MEAL-SPEC's weekly counts — vegetarian /
chicken / flex, cuisine mix, tomato count, quick / standard / longer, sesame.

The three warnings are the whole reason the message exists:

| Warning | Fires when | Says |
|---|---|---|
| tomato double-count | more than one tomato-heavy meal | which meals, and that the week is meant to carry one |
| sesame | any meal carries sesame | the meal **and its exact component**, so the child-safe portion comes out before that component goes in |
| `45-60` | any meal lands in the band | which meals, and their times, for an explicit yes |

**Every one of them is conditional.** A warning that prints every week is
wallpaper, so nothing is emitted for an empty class, and
`assertWarningsAreConditional()` re-reads the composed text before it is sent and
refuses a message that reads as a double-count on a one-tomato week, mentions
sesame when nothing has any, or prints the band callout with nothing in the band.
`--from-json` exists so both branches can be rehearsed against a week that has
two of each, because the live week usually has one of each and a warning nobody
has ever seen fire is a warning nobody knows is broken. A `--from-json` run never
sends: the week it describes is not the week Mealie holds.

### The grocery message

    node scripts/finalize-week.mjs --print-body
    node scripts/finalize-week.mjs --have "1/2 tsp salt" --have "2 Tbsp olive oil"
    node scripts/finalize-week.mjs --from-recipes --week 2026-08-31   # fill an empty list first

Reads the `Groceries` list and sends **only the unticked items**.
`assertCheckedItemsAreAbsent()` re-reads the composed text before the send and
refuses outright if a ticked label was printed as a line of the list. It only
warns when a ticked label turns up *inside* a longer line, because those are
different things: tick the bare `black pepper` and the shakshuka's
`1/2 tsp black pepper` still legitimately needs buying. Tick the specific line
rather than the bare ingredient and the warning goes away.

Quantities go out exactly as Mealie holds them, one line per recipe, because
"olive oil" with no amount is not a shopping list. Sections come from Mealie's
own label when the food carries one; the recipe importer creates most items as
plain notes with no food and therefore no label, so those fall back to a keyword
classifier over the item text — spice rack asked before produce, tinned tomatoes
before fresh. Ingredients several dinners want get one "buy for the total, not
per line" note at the bottom, which is how MEAL-SPEC's "combine duplicates
intelligently" survives without deleting the per-recipe amounts.

`--from-recipes` is opt-in and only that. The list is the household's working
copy between the proposal and the shop; refilling it on every finalize would wipe
the ticks that make step 4 mean anything.

## The Signal bridge

signal-cli REST API in Proxmox LXC 109, compose at `/opt/signal-bridge/docker-compose.yml`.

| | |
|---|---|
| Send API | `http://192.168.20.45:8080` — `POST /v2/send`, and a send is only proven by the `timestamp` it returns |
| Port 8081 | the Alertmanager adapter for the whole cluster. Alert-shaped bodies only; meal messages do not go through it |
| Mode | `MODE: json-rpc` |
| Image | pinned to a real version tag, never `:latest` |

**`MODE: normal` is a disk bomb.** It spawns signal-cli per request, and each
spawn extracts ~153 MB of libsignal into `/tmp`; about fifty sends fill the 7.8 G
rootfs and the API starts answering `400 No space left on device`. In `json-rpc`
mode one daemon extracts it once at startup and every send reuses it — one
`/tmp/libsignal*` directory dated container start, however many messages later.
`send()` warns on stderr if it ever finds the bridge back in `normal`.

Both settings live in the compose file so a restart cannot revert them, and the
image is pinned in the same change: `docker compose up -d` on an unpinned
`:latest` pulls whatever upstream tagged since, which is exactly the wrong moment
to find out a new build behaves differently. Pin to the tag that resolves to the
digest already running — check with `docker inspect <tag> --format '{{.Id}}'`
against the running container's image, and pin by `@sha256:` if no tag matches.

Pinned to `bbernhard/signal-cli-rest-api:0.99` (`sha256:96578363477d…`), which
is the digest `:latest` had already pulled; upstream `:latest` has since moved on
to `0.100`. Every change to this file leaves a dated backup beside it, and a
rollback is that backup plus a recreate:

    ssh proxmox
    pct exec 109 -- sh -c 'cd /opt/signal-bridge && cp docker-compose.yml.bak-2026-08-30-prejsonrpc docker-compose.yml && docker compose up -d'

Afterwards, confirm what you meant to change: `GET /v1/about` reports the mode,
and `POST http://192.168.20.45:8081/` with an Alertmanager-shaped body must still
answer `ok` — the cluster's alerts ride the same bridge.

## Step-by-step

1. **Get candidates.** Run `weekday-dinner-recipes` for the season, or reuse `references/candidate-pool.json`. Annotate each with `dish`, `source`, `cuisine`, `role`, `protein` and a one-line `why`.
2. **Dry-run the week.** `node scripts/propose-week.mjs --week YYYY-MM-DD`. Read the summary and the warnings. This writes nothing.
3. **Adjust and re-run** if the shape is wrong — add candidates, fix a `role`, record a block.
4. **Apply.** `node scripts/propose-week.mjs --week YYYY-MM-DD --apply`. This imports by URL, normalizes `totalTime`, tags from the stored recipe, replaces the week's dinner entries (idempotent — re-running does not stack duplicates), and records the proposals in `history.json`.
5. **Send the week.** `node scripts/send-summary.mjs --week YYYY-MM-DD`. Read it once with `--dry-run --print-body` first if the week is unusual. The tomato count, the sesame components and the `45-60` callouts are derived from the recipes Mealie stored, not from the proposal.
6. **Wait for the ingredient check.** The household edits the week in Mealie and ticks off what it already has on the `Groceries` list. Do not shortcut this by sending the list early.
7. **Finalize.** `node scripts/finalize-week.mjs --print-body`. Only the unticked items go out.
8. **After dinner, record votes.** One entry per person — `--vote` refuses to run without `--person`, because a household vote is not a thing:

       node scripts/record-feedback.mjs --url <url> --person amanda --vote down --reason too-much-work
       node scripts/record-feedback.mjs --url <url> --cooked 2026-09-02

   `--cooked` marks it made in Mealie through `/last-made`, which is what starts the 28-day cooldown. A block wider than its reason licenses (`--scope dish` on a `not-flavorful-enough`) is stored as advisory and only becomes binding the second time the household says it.

## Hard rules

- Import **by URL**. A pasted recipe has no `orgURL`, so the review page cannot link out and link rot can never be detected.
- Derive `tomato`, `sesame` and the timing tags from the recipe Mealie stored. Never from the candidate file, never from memory.
- Exactly one dinner entry per weekday, each linked to a **distinct** recipe. Re-running the planner replaces the week; it does not stack.
- The cooldown is `lastMade <= "$NOW-28d"`, asked of Mealie. Do not reimplement it with local date maths.
- Read ratings **per account**, with that person's own token. Never average.
- Never write a token, or a password, into a file in this skill.
- If a recipe has no usable `totalTime`, fix the recipe. Do not guess a timing tag.
- After a Mealie upgrade, run `scripts/verify-cooldown.mjs` before trusting a proposed week.
- Send the grocery list **after** the ingredient check, and never send a ticked item back.
- Keep the Signal bridge in `json-rpc` on a pinned image. Both live in the compose file so a restart cannot undo them.
- Meal messages go to `:8080`. Port `:8081` belongs to the cluster's Alertmanager path; do not borrow it.

## Anti-patterns

- ❌ Searching for recipes here instead of delegating to `weekday-dinner-recipes`, and skipping its rating/link verification.
- ❌ Setting `lastMade` with a plain recipe PATCH — it looks like it worked and the cooldown silently stops working.
- ❌ Collapsing two people's ratings into one number because the API made it awkward.
- ❌ Tagging `tomato` because the recipe mentions a tomato somewhere. Garnish is not a base.
- ❌ Blocking a whole cuisine because one recipe from it was a miss.
- ❌ Five dinners that are all 50 minutes, or all from one blog, because each one looked good on its own.
- ❌ Printing all three warnings every week "so nobody misses one". Two weeks later nobody reads any of them.
- ❌ Saying "one meal has sesame" without naming the component. The cook needs to know what goes in last, not that a flag is set.
- ❌ Sending the grocery list straight after the summary. The tick-off step is what makes it a *shopping* list.
- ❌ Rebuilding the shopping list from the recipes on every finalize. That erases the household's ticks.
- ❌ Restoring `MODE: normal`, or unpinning the image "to get the latest fixes", on a bridge that also carries the cluster's alerts.

## Related skills

- [[weekday-dinner-recipes]] — candidate discovery, rating and link verification. Public; keep household specifics out of it.
- [[extract-recipe-grocery-list]] — turns the approved week's URLs into an aisle-grouped list.
- [[detect-dinner-freezer-protein]] — what to pull out of the freezer that morning.
