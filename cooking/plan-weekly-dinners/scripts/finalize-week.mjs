#!/usr/bin/env node
// Send the shopping list to Signal once the household has said what they have.
//
//   node scripts/finalize-week.mjs
//   node scripts/finalize-week.mjs --print-body
//   node scripts/finalize-week.mjs --dry-run --print-body
//   node scripts/finalize-week.mjs --from-recipes --week 2026-08-31   # (re)fill the list first
//
// This is the last step of the ritual. MEAL-SPEC is explicit that the grocery
// list is generated *after* the ingredient check, not before it: the household
// ticks off what is already in the cupboard — in the Mealie app, on the kitchen
// dashboard's todo card, or with --have here — and only what is left gets sent.
//
// So a ticked item is not a formatting detail. It is the household saying "we
// have that", and an item that reappears on the phone after they said so is the
// fastest way to teach them to stop ticking. Nothing checked is printed, ever.
//
// Aisle grouping: Mealie's own label wins whenever a food carries one. Items the
// recipe importer created as plain notes have no food and therefore no label, so
// those fall back to a keyword classifier over the item text. That is a fallback,
// not a replacement — label a food in Mealie and it takes over immediately.

import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  addRecipeToShoppingList,
  itemLabel,
  itemSection,
  planningToken,
  setItemChecked,
  shoppingListItems,
  shoppingListNamed,
  weekDates,
  weekDinners,
} from "./mealie.mjs";
import { send } from "./signal.mjs";

const BEGIN = "-----BEGIN GROCERY-----";
const END = "-----END GROCERY-----";

/* ------------------------------------------------------------------ */
/* arguments                                                            */
/* ------------------------------------------------------------------ */

function parseArgs(argv) {
  const args = {
    list: "Groceries",
    week: null,
    fromRecipes: false,
    have: [],
    dryRun: false,
    printBody: false,
    json: false,
    help: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    const next = () => {
      const v = argv[i + 1];
      if (v === undefined) throw new Error(`${a} needs a value`);
      i += 1;
      return v;
    };
    if (a === "--list") args.list = next();
    else if (a === "--week") args.week = next();
    else if (a === "--from-recipes") args.fromRecipes = true;
    else if (a === "--have") args.have.push(next());
    else if (a === "--dry-run") args.dryRun = true;
    else if (a === "--print-body") args.printBody = true;
    else if (a === "--json") args.json = true;
    else if (a === "--help" || a === "-h") args.help = true;
    else throw new Error(`unknown argument ${a}`);
  }
  return args;
}

const USAGE =
  "usage: finalize-week.mjs [--list NAME] [--from-recipes --week YYYY-MM-DD] [--have TEXT]... " +
  "[--dry-run] [--print-body] [--json]\n";

/* ------------------------------------------------------------------ */
/* aisles                                                              */
/* ------------------------------------------------------------------ */

// Ordered, and the order is the whole trick. "black pepper" and "bell pepper"
// are both peppers; only the first rule that matches wins, so the spice rack
// is asked before the produce aisle, and the tin of tomato sauce before the
// six fresh tomatoes.
const AISLES = [
  [
    "Spices & seasoning",
    /\b(?:salt|black pepper|white pepper|peppercorns?|red pepper flakes|chil[il] (?:powder|flakes)|cayenne|cumin|paprika|coriander|turmeric|cinnamon|nutmeg|allspice|ground cloves|bay lea(?:f|ves)|curry powder|garlic powder|onion powder|italian seasoning|za'?atar|sesame seeds?|vanilla extract)\b|\b(?:dried|ground|rubbed)\s+(?!beef\b|pork\b|lamb\b|veal\b|turkey\b|chicken\b|meat\b|sausages?\b)\w+/i,
  ],
  [
    "Meat & seafood",
    /\b(?:chicken|beef|pork|lamb|turkey|sausages?|bacon|prosciutto|chorizo|steak|mince|salmon|cod|halibut|tilapia|tuna|shrimps?|prawns?|scallops?|mussels?|fish)\b/i,
  ],
  [
    "Dairy & eggs",
    /\b(?:eggs?|milk|butter|ghee|cream|creme fraiche|yogh?urt|cheese|parmesan|pecorino|feta|mozzarella|ricotta|cheddar|halloumi|sour cream)\b/i,
  ],
  [
    "Frozen",
    /\bfrozen\b|\bice cream\b/i,
  ],
  [
    "Bakery",
    /\b(?:bread|baguette|pita|tortillas?|naan|buns?|rolls?|brioche|sourdough)\b/i,
  ],
  [
    "Cans, jars & sauces",
    /\b(?:canned|can of|tin of|jarred?|tomato (?:sauce|paste|pur[eé]e|passata)|crushed tomatoes|diced tomatoes|marinara|passata|coconut milk|broth|stock|soy sauce|fish sauce|oyster sauce|hoisin|sriracha|harissa|mayonnaise|mustard|ketchup|tahini|olives|capers|beans?\b(?! sprouts)|chickpeas|lentils|salsa|pickles?)\b/i,
  ],
  [
    "Produce",
    /\b(?:apples?|onions?|shallots?|garlic|potatoes?|potato|tomatoes?|peppers?|zucchini|courgette|asparagus|cauliflower|broccoli|carrots?|celery|lettuce|spinach|kale|greens|cucumbers?|limes?|lemons?|oranges?|avocados?|mushrooms?|cilantro|coriander leaves|parsley|basil|mint|dill|thyme|rosemary|sage|chives|scallions?|green onions?|ginger|squash|pumpkin|corn|cabbage|leeks?|bok choy|eggplant|aubergine|berries|herbs?)\b/i,
  ],
];

const PANTRY = "Pantry";

/** Which aisle a line belongs to when Mealie has no label for it. */
export function aisleFor(text) {
  for (const [name, re] of AISLES) if (re.test(text)) return name;
  return PANTRY;
}

// The order the sections print in, chosen to match the way the store is walked
// rather than the alphabet. Anything Mealie labelled that is not in this list
// is appended after, in Mealie's own order.
const AISLE_ORDER = [
  "Produce",
  "Meat & seafood",
  "Dairy & eggs",
  "Bakery",
  "Cans, jars & sauces",
  PANTRY,
  "Spices & seasoning",
  "Frozen",
];

/* ------------------------------------------------------------------ */
/* repeated ingredients                                                 */
/* ------------------------------------------------------------------ */

// The unit has to be followed by whitespace. Without that, the "g" alternative
// happily eats the g of "garlic" and the buy-once hint starts talking about
// "arlic cloves".
const QUANTITY_HEAD =
  /^(?:(?:\d+[\d./\s]*|[¼-¾⅐-⅞]+)\s*)?(?:(?:tbsp|tablespoons?|tsp|teaspoons?|cups?|cloves?|oz|ounces?|lbs?|pounds?|g|kg|ml|l|pinch|dash|cans?|jars?|packages?|bunch(?:es)?|sprigs?|slices?|handfuls?|clamshell)\.?\s+)?/i;
const DESCRIPTORS =
  /\b(?:fresh(?:ly)?|chopped|minced|sliced|diced|quartered|halved|crushed|grated|melted|toasted|uncooked|cooked|boneless|skinless|whole|ripe|extra|virgin|sweet|hot|cold|large|medium|small|ground|dried|rubbed|of|and|plus|more|thin(?:ly)?|julienne|cut|leaves|pieces?|florets?|optional|kosher|all[- ]purpose|freshly|cracked|spanish|italian)\b/gi;

/**
 * The rough food a line is about, so the same thing bought for three different
 * meals can be spotted. Deliberately crude: this feeds a "buy once" hint, not
 * an order, so a miss costs nothing and a wrong merge would cost a dinner.
 */
export function coreFood(text) {
  let s = String(text)
    .toLowerCase()
    .replace(/\([^)]*\)/g, " ")
    .replace(/\$[\d.]+/g, " ")
    .replace(/[*,]/g, " ");
  s = s.replace(QUANTITY_HEAD, " ");
  s = s.replace(/^[\d./\s¼-¾⅐-⅞]+/, " ");
  s = s
    .replace(DESCRIPTORS, " ")
    .replace(/[^a-z\s-]/g, " ")
    .replace(/(?:^|\s)-+(?=\s|$)/g, " ")
    .replace(/\s{2,}/g, " ")
    .trim();
  const words = s.split(" ").filter(Boolean);
  if (!words.length) return null;
  return words.slice(-2).join(" ");
}

// "2 garlic cloves" and "2 cloves crushed garlic" are the same thing bought
// twice, so group on the unordered pair rather than the word order the recipe
// writer happened to use.
const foodKey = (core) => core.split(" ").sort().join(" ");

/**
 * Ingredients more than one dinner calls for. MEAL-SPEC asks for duplicates to
 * be combined intelligently and for absurd over-ordering to be avoided — but
 * the per-recipe amounts still have to survive, because "olive oil" without a
 * quantity is not a shopping list. So every line prints as Mealie holds it, and
 * this adds the one sentence that keeps four olive-oil lines from becoming four
 * bottles.
 */
export function repeatedFoods(items) {
  const groups = new Map();
  for (const text of items) {
    const core = coreFood(text);
    if (!core) continue;
    const key = foodKey(core);
    if (!groups.has(key)) groups.set(key, { food: core, count: 0 });
    groups.get(key).count += 1;
  }
  return [...groups.values()]
    .filter((g) => g.count > 1)
    .sort((a, b) => b.count - a.count || a.food.localeCompare(b.food));
}

/* ------------------------------------------------------------------ */
/* the message                                                          */
/* ------------------------------------------------------------------ */

export function composeGroceryList({ listName, needed, haveCount, weekLabel }) {
  const sections = new Map();
  for (const item of needed) {
    const section = item.section || aisleFor(item.text);
    if (!sections.has(section)) sections.set(section, []);
    sections.get(section).push(item.text);
  }
  const ordered = [
    ...AISLE_ORDER.filter((a) => sections.has(a)),
    ...[...sections.keys()].filter((a) => !AISLE_ORDER.includes(a)),
  ];

  const header = weekLabel ? `${listName} · ${weekLabel}` : listName;
  const lines = [header, ""];
  if (!needed.length) {
    lines.push("Nothing left to buy — everything on the list is ticked off.");
  }
  for (const section of ordered) {
    lines.push(section.toUpperCase());
    for (const text of sections.get(section)) lines.push(`  ${text}`);
    lines.push("");
  }

  const repeats = repeatedFoods(needed.map((i) => i.text));
  if (repeats.length) {
    lines.push(
      "Listed once per recipe, so buy for the total, not per line: " +
        repeats.map((r) => `${r.food} (${r.count}×)`).join(", "),
    );
  }
  if (haveCount) {
    lines.push(`${haveCount} more ${haveCount === 1 ? "item" : "items"} you said we already have, left off.`);
  }
  lines.push(`${needed.length} to buy.`);

  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

/**
 * The ingredient check is the whole point of this step, so prove it held before
 * anything is sent.
 *
 * A ticked label printed as its own line is a real leak and stops the send.
 * A ticked label that merely turns up inside a longer line is different — tick
 * the bare "black pepper" and the shakshuka's "1/2 tsp black pepper" still
 * legitimately needs buying — but anything scanning the message for the ticked
 * text will read it as a leak, so say so loudly rather than silently.
 */
export function assertCheckedItemsAreAbsent(body, have) {
  const printed = new Set(body.split("\n").map((l) => l.trim()));
  const leaked = have.filter((text) => text && printed.has(text));
  if (leaked.length) {
    throw new Error(
      `refusing to send a grocery list that puts back ${leaked.length} item(s) the household ticked off: ` +
        leaked.slice(0, 5).join(" | "),
    );
  }
  const shadowed = have.filter((text) => text && !printed.has(text) && body.includes(text));
  if (shadowed.length) {
    process.stderr.write(
      `warning: ${shadowed.length} ticked item(s) still appear as substrings of longer lines — ` +
        `${shadowed.slice(0, 3).join(" | ")}. Nothing ticked is being asked for, but tick the specific ` +
        `line rather than the bare ingredient and this goes away.\n`,
    );
  }
}

/* ------------------------------------------------------------------ */

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
function dayLabel(iso) {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return `${DAY_NAMES[d.getUTCDay()]} ${d.getUTCDate()} ${MONTH_NAMES[d.getUTCMonth()]}`;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    process.stdout.write(USAGE);
    return;
  }

  const token = planningToken();
  const list = shoppingListNamed(token, args.list);

  // Refilling is opt-in. The list is the household's working copy between the
  // proposal and the shop; rebuilding it on every finalize would wipe the ticks
  // that make this step mean anything.
  if (args.fromRecipes) {
    if (!args.week) throw new Error("--from-recipes needs --week YYYY-MM-DD");
    for (const d of weekDinners(token, weekDates(args.week))) {
      if (!d.recipe) continue;
      addRecipeToShoppingList(token, list.id, d.recipe.id);
    }
  }

  let items = shoppingListItems(token, list.id);

  // --have is the shell-side equivalent of ticking the box in the app, for the
  // times the household says it out loud instead of opening Mealie.
  if (args.have.length) {
    for (const phrase of args.have) {
      const matches = items.filter((i) => !i.checked && itemLabel(i).toLowerCase().includes(phrase.toLowerCase()));
      if (!matches.length) throw new Error(`--have ${JSON.stringify(phrase)} matches nothing unchecked on ${list.name}`);
      for (const m of matches) setItemChecked(token, m, true);
      // Say what was ticked. A phrase that matched three lines when one was
      // meant is the sort of thing you want to see before the list goes out.
      process.stderr.write(`ticked off: ${matches.map(itemLabel).join(" | ")}\n`);
    }
    items = shoppingListItems(token, list.id);
  }

  const needed = items
    .filter((i) => !i.checked)
    .map((i) => ({ text: itemLabel(i), section: itemSection(i) }))
    .filter((i) => i.text);
  const have = items.filter((i) => i.checked).map(itemLabel).filter(Boolean);

  const weekLabel = args.week ? `${dayLabel(weekDates(args.week)[0])} to ${dayLabel(weekDates(args.week)[4])}` : null;
  const body = composeGroceryList({ listName: list.name, needed, haveCount: have.length, weekLabel });
  assertCheckedItemsAreAbsent(body, have);

  const timestamp = args.dryRun ? null : send(body);

  if (args.printBody) {
    process.stdout.write(`${BEGIN}\n${body}\n${END}\n`);
  }
  if (args.json) {
    process.stdout.write(
      `${JSON.stringify(
        { list: list.name, needed: needed.length, checked: have.length, sent: !args.dryRun, timestamp, body },
        null,
        2,
      )}\n`,
    );
  } else if (args.dryRun) {
    process.stdout.write(`dry run: ${needed.length} to buy, ${have.length} ticked off, nothing sent\n`);
  } else {
    process.stdout.write(`sent to Signal, timestamp: ${timestamp}\n`);
  }
}

// Importing this module must not send anything: main() only runs when the file
// was invoked as a script. realpath on both sides so running it through the
// symlinked skills directory still counts as direct invocation.
const invokedDirectly = (() => {
  if (!process.argv[1]) return false;
  try {
    return realpathSync(fileURLToPath(import.meta.url)) === realpathSync(process.argv[1]);
  } catch {
    return false;
  }
})();

if (invokedDirectly) {
  try {
    main();
  } catch (err) {
    process.stderr.write(`finalize-week: ${err.message}\n`);
    process.exit(1);
  }
}
