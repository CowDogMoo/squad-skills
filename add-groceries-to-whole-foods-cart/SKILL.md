---
name: add-groceries-to-whole-foods-cart
description: Parse the weekly grocery list from Jayson's Google Doc planner and add non-completed items to his Amazon/Whole Foods cart (stops at cart, never checks out).
---

You are adding this week's groceries from Jayson's weekly planner Google Doc to his Amazon Whole Foods cart. This task is triggered manually on-demand — there is no schedule.

# Host-environment translation (READ FIRST)

This skill is portable across hosts: Claude Code, Claude Desktop, and
the squad grocery-runner agent. The doc-reading and Amazon-driving
steps below are tool-agnostic; resolve the right MCP names from
whichever tools your host actually exposes.

## Reading the planner doc

**Prefer a Drive/Workspace MCP if your host has one** — pass the doc
file_id (`1wOTsLdEym1ml9oKCAkjmSEE4sN5q-6A-CzHLlcxfq1w`) to its
read-file tool and ask for HTML output. HTML preserves strikethrough
styling (items already obtained appear inside `<s>...</s>` tags or
with `style="text-decoration:line-through"` on a span). Examples by
host:

- squad grocery-runner: `mcp__gdrive__read_file_content` with
  `fileId` arg. Returns HTML.
- Claude Code / Desktop with Google Drive connector: the connector's
  read-file tool; pass the file_id and ask for HTML.

**Only fall back to the mobilebasic-via-Chrome trick if no Drive MCP
is available.** The fallback open the mobilebasic export
(`/document/d/<ID>/mobilebasic`) in a browser MCP and reads spans
with `line-through` styles. The Google web app blocks sign-in inside
chrome-devtools-mcp's spawned profile as "insecure," so Chrome-based
doc reads only work when the host's browser is your daily browser
(via `--autoConnect` against an existing Chrome instance) — not in
squad's grocery-runner default.

## Driving Amazon

Use whatever browser MCP your host exposes:

| Original (Claude in Chrome) | squad chrome MCP equivalent |
|---|---|
| `mcp__Claude_in_Chrome__navigate` | `mcp__chrome__navigate_page` with `{type: "url", url: "..."}` |
| `mcp__Claude_in_Chrome__javascript_tool` | `mcp__chrome__evaluate_script` with `{function: "() => { ...; return RESULT; }"}` — must wrap as a JS function expression, must `return` what you want |
| `browser_batch` | not available in squad — chain individual tool calls instead |

In the squad grocery-runner agent, chrome MCP runs against a
squad-managed browser profile (resolved by the
`{{.BrowserProfile "amazon"}}` template helper). Sign into Amazon
once via `squad browser open amazon https://www.amazon.com/`; the
session persists across subsequent runs. If Chrome navigation lands
on an Amazon sign-in page on any later run, stop and tell Jayson —
don't try to fill credentials.

## Confirmation prompt

If the host exposes a `Confirm` tool (squad does), call it for the
go/no-go check in Step 3. Otherwise use the host's native
ask-user primitive (`AskUserQuestion`, the Claude Code/Desktop
elicitation, etc.).

# Objective

Read the grocery list from the weekly planner Google Doc, extract only the items that are NOT struck through (strikethrough = already obtained), and add each one to the Whole Foods cart on Amazon. Stop after everything is in the cart — do NOT check out under any circumstances.

# Inputs

- Planner Google Doc: https://docs.google.com/document/d/1wOTsLdEym1ml9oKCAkjmSEE4sN5q-6A-CzHLlcxfq1w
- Amazon cart URL: https://www.amazon.com/gp/cart/view.html?ref_=nav_cart
- Whole Foods subcart URL: https://www.amazon.com/cart/localmarket?almBrandId=VUZHIFdob2xlIEZvb2Rz
- Delivery address is Lakewood 80228. Amazon sign-in lives in the chrome-devtools-mcp profile (`~/.cache/chrome-devtools-mcp/chrome-profile`) — already signed in after the first manual login; abort the run if you see a sign-in page.

# Step-by-step

## 1. Read the grocery list

**Preferred path: ask your host's Drive MCP for HTML.** When the
read-file tool returns HTML (squad's `mcp__gdrive__read_file_content`
does this by default; ask the connector explicitly otherwise),
strikethrough survives as `<li style="...line-through...">` on the
list-item element. Plain-text / markdown exports from older Drive
MCPs lose strikethrough — refuse those if a richer format is
available.

**Important — call `read_file_content` ONCE.** Do not also call
`mcp__gdrive__get_doc`; the structured JSON dump (~500 KB) won't
fit in budget and isn't needed for strikethrough detection. The
HTML export alone is enough.

**Fallback path (only if no Drive MCP exposes HTML):** open the
mobilebasic export in a browser MCP and read styled spans directly.
This only works when the browser MCP attaches to a Chrome instance
that's already signed into Google — otherwise the mobilebasic page
redirects to a "this browser may not be secure" wall. Procedure:

1. `mcp__Claude_in_Chrome__navigate` to `https://docs.google.com/document/d/1wOTsLdEym1ml9oKCAkjmSEE4sN5q-6A-CzHLlcxfq1w/mobilebasic`
2. Wait ~2s for render.
3. Run JS to find struck-through items:

   ```js
   const struck = [];
   document.querySelectorAll('*').forEach(el => {
     const s = el.getAttribute('style') || '';
     if (/line-through/.test(s)) {
       const t = el.textContent.trim();
       if (t) struck.push(t);
     }
   });
   ```

4. Get the full `GROCERIES` section text by slicing `document.body.innerText` from the matching anchor. Body text may exceed 3000 chars — read in slices.

## 1a. The doc is a rolling planner — pick the right week's GROCERIES section

The planner is now a single rolling doc with multiple weeks stacked top-to-bottom. The grocery section for each week has a heading like `GROCERIES · Week of <Month> <Day>` (using `·` U+00B7 middle dot as the separator; the year may or may not be in the heading — assume current year when absent).

**Find every `GROCERIES · Week of <date>` heading in the doc. Parse the date out of each. Pick the heading whose date is the highest (most recent).** Then read only the list under THAT heading; ignore earlier weeks.

This is "highest date wins" (not "first occurrence" and not "last occurrence in doc") — it stays correct regardless of how you order the weeks in the doc, and survives you adding next week's section above this week's.

The section under the chosen heading is organized by category (Produce, Protein, Dairy, Pantry, Frozen, Refrigerated/Other). Items that are already obtained are struck-through (Google Docs encodes this with `text-decoration:line-through` on the `<li>` element's style attribute — NOT inside an inner `<span>` — make sure your strikethrough check inspects the `<li>` style, not just child spans). SKIP struck items.

Parse each remaining ingredient with its quantity. Items often have parenthetical recipe labels like `"8 tbsp / 1 stick unsalted butter (pie)"` — strip the parenthetical.

## 2. Resolve ambiguities by reading the linked recipes — don't ask the user

The doc's weekly planner table includes recipe URLs under the "Dinner" row. If the grocery list is ambiguous on quantity, size, "optional" status, or pack size — **fetch the recipe URLs directly via the Chrome MCP** rather than asking Jayson. He's explicitly told the agent to do this.

Recipe URLs from the doc are NOT in WebFetch's provenance set (because they came via the Drive MCP), so use `mcp__Claude_in_Chrome__navigate` + `javascript_tool` to scrape `.tasty-recipes`, `.wprm-recipe-container`, or `.wprm-recipe` containers for the ingredient list.

Things the recipes resolve:

- Salmon weight (recipe is 1-2 lbs; pick the smaller end ~1 lb for a single dinner)
- Whether "Shaoxing wine" / similar specialty items are optional and what's a valid substitute
- Whether something marked "kewpie mayo" must be that specific brand vs. a substitute

## 3. Confirm the parsed list with the user

Before touching the cart, show Jayson:

- The list of items you will add, organized by category, with quantities.
- Any recipe-derived decisions (e.g. "going with ~1 lb salmon fillet; recipe range was 1-2 lb").
- Anything truly outside the recipes that needs his input (e.g. whether to skip pantry staples he might already own — but note the strikethrough convention is the source of truth: if it's NOT struck through, he wants it).

Use `AskUserQuestion` with a clear go/no-go question. Don't proceed to cart adds until he confirms.

## 4. Add to cart on Amazon Whole Foods

Use the Claude in Chrome MCP for all browser interaction. Do NOT use computer-use clicks for the browser — Chrome is at "read" tier.

### Search pattern that works

The reliable search URL is:

```
https://www.amazon.com/s?k=<ITEM>&i=wholefoods
```

The `i=wholefoods` storefront filter restricts to Whole Foods. Don't use the `rh=p_4%3AWhole+Foods+Market` brand filter — `i=wholefoods` is cleaner.

To read search results:

```js
const cards = [...document.querySelectorAll('[data-component-type="s-search-result"]')];
cards.slice(0, 6).map(c => ({
  asin: c.getAttribute('data-asin'),
  title: c.querySelector('h2 a span, h2 span')?.innerText,
  price: c.querySelector('.a-price .a-offscreen')?.innerText
}));
```

### Picking products — priority order

1. **PRODUCE: organic by default.** Jayson explicitly directs organic for fresh produce, even if it's more expensive than conventional. If the only organic option is a larger bag (e.g. organic russet potatoes only come in a 5 lb bag, organic limes only in a 1 lb bag), buy the bag and flag the over-purchase. If no organic version exists (e.g. fresh jalapeños — Whole Foods only stocks jarred sliced organic), keep the conventional and flag it.
2. **365 BY WHOLE FOODS MARKET** brand preference for pantry, dairy, frozen, refrigerated — usually cheapest and matches Jayson's pattern.
3. **Smallest pack size** that satisfies the recipe quantity. Don't over-buy.
4. Previous purchases — Amazon's `Buy it again` / `Purchased before` signal exists but is unreliable to detect from search-result DOM text (it matches recommendations too). Don't try to detect it programmatically; rely on the rules above.

### Add-to-cart pattern — ONE evaluate_script per item

To stay under the run's cost budget, do the whole per-item flow
(search → pick best result → navigate → click add → verify) in a
**single `mcp__chrome__evaluate_script` call per item**, using
`fetch()` for any extra HTTP and `window.location` for navigations
that need a real browser context. Each call should return a small
JSON object (≤2 KiB) like:

    {"asin": "B07...", "title": "...", "added": true, "cartCount": 7}

DO NOT chain navigate_page → evaluate_script → navigate_page →
evaluate_script per item. That's ~6 calls per item and burns the
budget on tool-result bloat. The chrome MCP is configured with
`max_result_bytes: 2048` — anything over that gets truncated, so
return parsed JSON, never raw DOM.

Template for one item (the agent should embed this kind of script
per item, parameterized):

```js
async () => {
  const q = "8 ounces button mushrooms";
  // 1. Search
  const searchHTML = await fetch(
    "https://www.amazon.com/s?k=" + encodeURIComponent(q) + "&i=wholefoods"
  ).then(r => r.text());
  const sdoc = new DOMParser().parseFromString(searchHTML, "text/html");
  const cards = [...sdoc.querySelectorAll('[data-component-type="s-search-result"]')];
  // 2. Pick first organic / 365 / smallest pack — heuristic in plain JS
  const picks = cards.slice(0, 8).map(c => ({
    asin: c.getAttribute("data-asin"),
    title: c.querySelector("h2 a span, h2 span")?.innerText || "",
    price: c.querySelector(".a-price .a-offscreen")?.innerText || ""
  })).filter(p => p.asin);
  const pick = picks.find(p => /organic|365/i.test(p.title)) || picks[0];
  if (!pick) return {q, error: "no results"};
  // 3. Navigate to product (real navigation — sets cookies, gets CSRF)
  window.location.href = "https://www.amazon.com/dp/" + pick.asin;
  // execution context is destroyed here; the next evaluate_script will run on the product page
  return {q, asin: pick.asin, title: pick.title.slice(0, 80), navigated: true};
}
```

After the navigation the agent does ONE follow-up
`evaluate_script` that clicks add-to-cart and reads the new cart
count, then returns the result. That's **two** chrome calls per
item total. With 9 items that's 18 chrome calls, well under
budget.

Click + verify follow-up:

```js
async () => {
  const titleEl = document.querySelector("#productTitle");
  const btn = document.querySelector("#add-to-cart-button-grocery, #add-to-cart-button");
  const before = document.querySelector("#nav-cart-count")?.innerText || "0";
  btn?.click();
  // wait a beat for the cart count to update — DOM does it async
  await new Promise(r => setTimeout(r, 1500));
  const after = document.querySelector("#nav-cart-count")?.innerText || before;
  return {
    title: titleEl?.innerText?.slice(0, 80),
    before, after,
    added: after !== before
  };
}
```

`#nav-cart-count` may not update if Amazon navigated to a "smart
wagon" interstitial; in that case `added` will be false but the
item probably DID land in the cart. Trust the click and continue.

### After each successful add — mark the item obtained in the doc

Immediately after a successful add-to-cart for an item, call
`mcp__gdrive__mark_items_obtained` with the planner file_id, the
GROCERIES heading match for this week, and the item text you just
added. This applies strikethrough to that line in the planner
doc so future grocery runs (and the user) see it as done.

Example call after adding mushrooms:

    mcp__gdrive__mark_items_obtained({
      "documentId": "<planner file_id>",
      "tableHeadingMatch": "GROCERIES · Week of <Month> <Day>",
      "items": ["button mushrooms"]
    })

Match is a case-insensitive substring against the line text in
col 1 of any items row. Use a short distinctive snippet
(`"button mushrooms"`) — not the whole quantity-prefixed string
— so the match is robust to formatting variation.

You can batch several items in one `items` array if you're adding
in groups. Don't wait until the end to call this once for
everything — if the run aborts midway, items added but not marked
will get re-added on the next run.

### Items with no fresh organic option

Whole Foods does NOT carry fresh organic versions of some produce (verified: jalapeños). Don't loop searching — accept the conventional and flag in the report.

## 5. Handle problems

- If an item isn't available at Whole Foods, note it and skip — do NOT substitute without asking.
- For ambiguous matches (e.g. "shrimp" — fresh vs frozen), check the recipe URL first. If still ambiguous, ask.
- If you get logged out or hit a CAPTCHA, stop and tell Jayson.

## 6. Stop at the cart

When all items are added, navigate to `https://www.amazon.com/gp/cart/view.html?ref_=nav_cart` and verify the items.

**The Whole Foods cart is split across two views:**

- **Main cart** (`/gp/cart/view.html`) — non-Whole-Foods items + most recently added Whole Foods items.
- **Whole Foods subcart** (`/cart/localmarket?almBrandId=VUZHIFdob2xlIEZvb2Rz`) — older Whole Foods items get collapsed here. Reach it via the "collapsed_item_list" expand link, or navigate directly.

Items have different delete UIs in each view:

- **Main cart**: `row.querySelector('input[data-action="delete-active"], input[name^="submit.delete"]')`.click()
- **WF subcart**: `row.querySelector('input')` where `aria-label` starts with `"Remove "` (the decrement button). When qty=1 it deletes the item; for qty=N, click N times with delays between clicks.

After deletes, the cart's async update lags a few seconds. Wait 3-4s before re-reading `#nav-cart-count` or DOM state. The cart row will linger with a "moved to Saved for Later / Undo" message even after deletion — check `row.className` for `sc-list-item-optimistic-updates` to identify already-deleted rows.

**Do NOT click "Proceed to checkout."** Do NOT place an order. Even if Jayson asks during the run, decline politely — checkout is out of scope.

# Output

Report back to Jayson with:

- Items added, organized by category, with the matched product name and pack size.
- Anything flagged: items where you bought a larger pack because the smaller size wasn't available organic; items unavailable; conventional kept because no organic exists; recipe quantities that don't match retail pack sizes.
- The cart link.
- A reminder that the cart is ready for him to review and check out himself.

# Constraints

- NEVER check out. NEVER place an order. NEVER enter payment info. Stop at cart, always.
- Only add items that are NOT struck through in the doc.
- **Produce: organic by default.** Other categories: 365 brand first, smallest pack second.
- One unit per item unless the recipe needs more than one pack size (rare).
- Resolve ambiguity from recipe URLs before asking Jayson.

# Verified item references (May 2026)

Reference picks from a successful run — re-verify ASINs each time, they can change:

| Need | ASIN | Product |
|------|------|---------|
| Yellow onion, organic | B07QV6B5WV | Organic Yellow Onion, 1 Each |
| Russet potatoes, organic | B000P6G0ZI | Organic Russet Potatoes, 5 lb bag (over-buys but only organic option) |
| Mango | B001392XUC | Large Organic Mango, 1 Each |
| Avocado, organic | B0014GLSE6 | Large Organic Hass Avocado |
| Cilantro, organic | B07819RK9C | Herb Cilantro Organic, 1 Bunch |
| Red onion, organic | B0787Y45SB | ONION RED OG |
| Jalapeño | B0787VZY5V | Green Jalapeno Pepper (conventional — no fresh organic at WF) |
| Limes, organic | B0792NT1VJ | Organic Limes, 1 lb bag (over-buys for 1–2 lime needs) |
| Broccoli, organic | B000P6L3K0 | Organic Broccoli, 1 Each |
| Green onions, organic | B07883LXVL | Green Onion (Scallions) Organic, 1 Bunch |
| Salmon fillet | B079W28NJW | Atlantic Salmon Fillet (~1 lb) |
| Unsalted butter | B08BQWY8YJ | 365 Unsalted Butter, 16 OZ |
| Half & half | B08G9TMJ4B | 365 Organic Half And Half, 16 Ounce |
| Avocado oil | B07Q4YNG8W | 365 Avocado Oil, Expeller Pressed, 16.9 Fl Oz |
| Honey | B074H5BV6W | 365 Organic Light Amber Wildflower Honey, 12 oz |
| Soy sauce (regular, not low-sodium) | B0005YW2VQ | Kikkoman All-Purpose Naturally Brewed Soy Sauce, 10 oz |
| Toasted sesame oil | B074H6M5XH | 365 Toasted Sesame Seed Oil, 8.4 Fl Oz |
| Garlic powder | B074V3VP5K | 365 Garlic Powder, 2.01 Ounce |
| Worcestershire | B074H7LFNJ | 365 Organic Worcestershire Sauce, 5 oz |
| Dried parsley | B074H81M9K | 365 Organic Parsley, 0.24 oz |
| Dried rosemary | B074VDGJ9Q | 365 Whole Rosemary Leaf, 0.46 OZ |
| Dried thyme | B074VBLHMH | 365 Thyme, .49 oz |
| All-purpose flour | B0078DPQGU | King Arthur Unbleached All Purpose Flour, 2 lb |
| Beef broth | B004SI9W7M | Pacific Foods Organic Beef Broth, 32 oz |
| Brown sugar | B07NS86M42 | 365 Organic Light Brown Sugar, 24 oz |
| Smoked paprika | B07NRRGV7Q | 365 Smoked Paprika, 1.87 oz |
| Onion powder | B074VDGJ8Z | 365 Onion Powder, 2.43 oz |
| Chili powder | B0B414VXRM | 365 Chili Powder Blend Seasoning, 2.52 oz |
| Kosher salt | B074H5TMQ7 | 365 Kosher Sea Salt, Coarse, 2.2 lb |
| Jasmine rice | B084NJJJQ7 | 365 Organic Jasmine Thai White Rice, 32 oz |
| Teriyaki sauce | B074H6VR3V | 365 Organic Teriyaki Sauce, 10 oz |
| Kewpie mayo | B0F148N2G1 | KEWPIE Organic Mayonnaise, 12 FZ |
| Black pepper | B074H5LYJN | 365 Black Pepper Ground, 1.8 oz |
| Frozen peas & carrots | B074H64BPW | 365 Organic Peas & Carrots, 16 oz |
| Kimchi | B098PVNV18 | Cleveland Kitchen Classic Kimchi |

# Anti-patterns — things that don't work, don't try again

- `mcp__workspace__web_fetch` on the recipe URLs: provenance set rejects them (URLs originated from the Drive MCP, which doesn't count). Use Chrome navigation instead.
- `https://docs.google.com/document/d/.../export?format=html`: redirects back to the edit URL in this account, returns empty page.
- DOM text from the Google Docs edit view (`/edit?tab=t.0`): empty — Docs renders to canvas.
- Drive MCP `read_file_content` for strikethrough detection: doesn't preserve strikethrough formatting. Use mobilebasic.
- Search-result "Buy it again" badge detection by text matching: false positives from "similar shoppers bought" sections. Don't trust it; rely on org/365/smallest-pack rules.
- Setting qty=2 in dropdown then immediately clicking add: occasionally adds only 1. Verify cart count after, retry if short.
