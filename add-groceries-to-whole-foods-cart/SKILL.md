---
name: add-groceries-to-whole-foods-cart
description: Parse the weekly grocery list from Jayson's Google Doc planner and add non-completed items to his Amazon/Whole Foods cart (stops at cart, never checks out).
---

You are adding this week's groceries from Jayson's weekly planner Google Doc to his Amazon Whole Foods cart. This task is triggered manually on-demand — there is no schedule.

# Tool-name translation (READ FIRST)

This skill was originally written against the `Claude in Chrome` MCP. When run from the squad weekly-planner agent, the Chrome MCP server is named `chrome` and uses different tool names. Translate every reference below before calling:

| What the skill body says | Call this instead |
|---|---|
| `mcp__Claude_in_Chrome__navigate` | `mcp__chrome__navigate_page` with `{type: "url", url: "..."}` |
| `mcp__Claude_in_Chrome__javascript_tool` | `mcp__chrome__evaluate_script` with `{function: "() => { ...; return RESULT; }"}` — must wrap as a JS function expression, must `return` what you want |
| `browser_batch` | not available — chain individual tool calls instead, one per step |

For Drive reads (the mobilebasic export trick), the skill body says to navigate via Chrome. That still works, but you can ALSO use the workspace MCP that's already wired up: `mcp__workspace__get_drive_file_content` with `file_id: "1-fjgU9MjdbxduyzC-Wq3obpW6tTgJH4s2vqbv4HonyQ"` returns the doc as plain text. **However, the workspace text export drops strikethrough formatting** — so if you need strikethrough detection (you do), still use the Chrome mobilebasic route via `mcp__chrome__navigate_page` + `mcp__chrome__evaluate_script` as the skill body describes.

Every Chrome call uses the user's actively-running Chrome (attached via `--autoConnect`). Amazon is already signed in there. You do not need to log in.

Other tools available in this agent:
- `mcp__workspace__*` — Google Drive + Calendar (auth handled by the workspace daemon). Useful only as a backup if Chrome navigation fails.
- `Confirm(summary, options)` — squad's confirmation tool. Use this in step 3 (the go/no-go check) instead of `AskUserQuestion` which the original skill body mentions.

# Objective

Read the grocery list from the weekly planner Google Doc, extract only the items that are NOT struck through (strikethrough = already obtained), and add each one to the Whole Foods cart on Amazon. Stop after everything is in the cart — do NOT check out under any circumstances.

# Inputs

- Planner Google Doc: https://docs.google.com/document/d/1-fjgU9MjdbxduyzC-Wq3obpW6tTgJH4s2vqbv4HonyQ
- Amazon cart URL: https://www.amazon.com/gp/cart/view.html?ref_=nav_cart
- Whole Foods subcart URL: https://www.amazon.com/cart/localmarket?almBrandId=VUZHIFdob2xlIEZvb2Rz
- User's Amazon account is already signed in via Chrome. Delivery address is Lakewood 80228.

# Step-by-step

## 1. Read the grocery list — use the mobilebasic export, NOT the Drive MCP

**Critical lesson from prior runs:** The Drive MCP's `read_file_content` returns a markdown representation that **does NOT preserve strikethrough formatting** (bold survives as `**text**` but strikethrough does not survive as `~~text~~`). It also truncates long docs. The Google Docs canvas-rendered edit view also has no DOM text. Skip both.

**Working approach** — open the mobilebasic export in Chrome and read styled spans:

1. `mcp__Claude_in_Chrome__navigate` to `https://docs.google.com/document/d/1-fjgU9MjdbxduyzC-Wq3obpW6tTgJH4s2vqbv4HonyQ/mobilebasic`
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

4. Get the full `GROCERIES` section text by slicing `document.body.innerText` from the "GROCERIES" anchor. Body text may exceed 3000 chars — read in slices.

The doc contains a `GROCERIES` section organized by category (Produce, Protein, Dairy, Pantry, Frozen, Refrigerated/Other). Items that are already obtained are struck-through — SKIP THESE. Parse each ingredient with its quantity. Items often have parenthetical recipe labels like `"8 tbsp / 1 stick unsalted butter (pie)"` — strip the parenthetical.

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

### Add-to-cart mechanic that works

For each chosen ASIN:

1. Navigate to `https://www.amazon.com/dp/<ASIN>`
2. Wait ~2.2s for page render.
3. If quantity > 1, set the dropdown:

   ```js
   const qty = document.querySelector('#quantity, select[name="quantity"]');
   qty.value = '2';
   qty.dispatchEvent(new Event('change', {bubbles: true}));
   ```

   **Warning:** Sometimes the qty=2 doesn't stick (clicked too fast). Verify `#nav-cart-count` increased by the expected delta after; if short, re-add.
4. Click the button:

   ```js
   document.querySelector('#add-to-cart-button-grocery, #add-to-cart-button')?.click();
   ```

5. The page redirects to `/cart/smart-wagon?newItems=...`. **Tail JS calls after the click will error with "Inspected target navigated or closed"** — that's harmless, the add already happened. Verify by reading `#nav-cart-count` after a fresh navigation or wait.

### Batching for speed

Use `browser_batch` to run navigate → wait → click → wait → navigate → wait → readSearchResults all in one round trip. Each item is ~5 actions; aim for one item per batch call. Expect occasional batch failures on the post-click wait (page navigated) — recover by reading `#nav-cart-count` in a follow-up call. The click already worked.

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
