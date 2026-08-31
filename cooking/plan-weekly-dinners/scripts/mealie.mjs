// Shared Mealie adapter for the plan-weekly-dinners skill.
//
// Everything the planner does to Mealie goes through here: auth, recipe import
// by URL, the constraint tag vocabulary, the weekly mealplan, ratings, and the
// shopping list.
//
// Two environment facts shape this file:
//
//   1. Node's own sockets are blocked on this host (undici gets EHOSTUNREACH on
//      the LAN) while curl is proxied through fine. Every request therefore
//      shells out to curl. Do not "modernize" this to fetch().
//   2. Tokens are per-account. Ratings in Mealie are only readable by the
//      requesting user, so the planner holds one long-lived token per person
//      and never a single household token.

import { execFileSync } from "node:child_process";

export const MEALIE_URL = (process.env.MEALIE_URL || "https://mealie.techvomit.xyz").replace(/\/+$/, "");
export const OP_ITEM = process.env.MEALIE_OP_ITEM || "op://automation/mealie-api-tokens";

// Both household members, in planning order. `tokenField` is the 1Password
// field holding that person's own Mealie API token.
export const PEOPLE = [
  { key: "jayson", mealieUsername: "jayson", tokenField: "jayson-planner" },
  { key: "amanda", mealieUsername: "amanda", tokenField: "amanda-planner" },
];

// The reuse cooldown, expressed exactly as Mealie's query language wants it.
// Mealie resolves $NOW server-side, so the planner never has to compute a date
// and never drifts from the server's clock.
export const COOLDOWN_DAYS = 28;
export const COOLDOWN_QUERY = 'lastMade <= "$NOW-28d"';
export const RECENTLY_MADE_QUERY = 'lastMade > "$NOW-28d"';

// The constraint tag vocabulary. These slugs are the contract between the
// planner, the review page, and the Signal summary.
export const TIMING_TAGS = ["quick", "standard", "longer"];
export const BAND_TAG = "45-60";
export const FLAG_TAGS = ["tomato", "sesame"];
export const ROLE_TAGS = ["vegetarian", "vegan", "chicken", "flex", "indulgent"];

/* ------------------------------------------------------------------ */
/* secrets                                                              */
/* ------------------------------------------------------------------ */

const secretCache = new Map();

/** Read a secret by op:// reference. Never write the result to disk. */
export function opRead(ref) {
  if (secretCache.has(ref)) return secretCache.get(ref);
  let value = "";
  try {
    value = execFileSync("sh", ["-c", '. "$HOME/.op-token" >/dev/null 2>&1; op read "$1"', "sh", ref], {
      encoding: "utf8",
      timeout: 30000,
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
  } catch (err) {
    throw new Error(`could not read ${ref} from 1Password: ${err.message}`);
  }
  if (!value) throw new Error(`1Password reference ${ref} is empty`);
  secretCache.set(ref, value);
  return value;
}

/** That person's own Mealie API token. `who` is a PEOPLE key or a field name. */
export function tokenFor(who) {
  const person = PEOPLE.find((p) => p.key === who);
  const field = person ? person.tokenField : who;
  return opRead(`${OP_ITEM}/${field}`);
}

/** The token the planner itself acts as (imports, tags, mealplan writes). */
export const planningToken = () => tokenFor("jayson");

/* ------------------------------------------------------------------ */
/* http                                                                 */
/* ------------------------------------------------------------------ */

const STATUS_SEP = "\n<<<MEALIE-HTTP-STATUS>>>";

/**
 * One Mealie request. Returns { status, ok, text, json }.
 * `query` is an object of query-string params; values are encoded here so
 * callers never hand-build a query string (queryFilter values contain spaces,
 * quotes and $ and are easy to get wrong).
 */
export function request(path, { token, method = "GET", body, headers = {}, query, timeoutMs = 90000 } = {}) {
  let url = MEALIE_URL + path;
  if (query && Object.keys(query).length) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null) continue;
      qs.append(k, String(v));
    }
    url += (url.includes("?") ? "&" : "?") + qs.toString();
  }

  const args = ["-sS", "--max-time", String(Math.round(timeoutMs / 1000)), "-X", method, "-o", "-", "-w", `${STATUS_SEP}%{http_code}`];
  const h = { ...headers };
  if (token) h.Authorization = `Bearer ${token}`;
  if (body !== undefined) h["Content-Type"] = "application/json";
  for (const [k, v] of Object.entries(h)) args.push("-H", `${k}: ${v}`);
  if (body !== undefined) args.push("--data-binary", JSON.stringify(body));
  args.push(url);

  let raw = "";
  let transportFailed = false;
  try {
    raw = execFileSync("curl", args, {
      encoding: "utf8",
      timeout: timeoutMs + 15000,
      maxBuffer: 32 * 1024 * 1024,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (err) {
    raw = `${err.stdout || ""}`;
    transportFailed = true;
  }
  const cut = raw.lastIndexOf(STATUS_SEP);
  const text = cut === -1 ? raw : raw.slice(0, cut);
  const status = cut === -1 ? 0 : Number(raw.slice(cut + STATUS_SEP.length).trim()) || 0;
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    /* non-JSON bodies are legal here; callers that need json check for null */
  }
  return { status, ok: !transportFailed && status >= 200 && status < 300, text, json };
}

/** request(), but throws on a non-2xx so call sites do not have to branch. */
export function must(path, opts = {}) {
  const res = request(path, opts);
  if (!res.ok) {
    throw new Error(`${opts.method || "GET"} ${path} -> ${res.status}: ${res.text.slice(0, 400)}`);
  }
  return res;
}

/* ------------------------------------------------------------------ */
/* constraint derivation                                                */
/* ------------------------------------------------------------------ */

// Tomato-HEAVY, not merely tomato-containing. A garnish tomato does not count
// against the household's one-tomato-heavy-meal-per-week target; a can of
// crushed tomatoes does. Only base forms match.
export const TOMATO_BASE =
  /\b(?:canned|crushed|diced|stewed|strained|whole peeled|san marzano|fire[- ]roasted)\s+tomato|tomato\s+(?:paste|pur[eé]e|sauce|passata|juice)\b|\bpassata\b|\bmarinara\b|\bsun[- ]dried tomato|\bketchup\b|\btomato,?\s+crushed\b/i;

// Sesame is a child-safety flag, so it is deliberately broad: seeds, oil,
// tahini, za'atar, halva, gomashio.
export const SESAME = /\bsesame\b|\btahini\b|\bgomashio\b|\bza'?atar\b|\bhalva\b/i;

/** Every scrap of text Mealie kept for an ingredient line. */
export function ingredientText(recipe) {
  return (recipe.recipeIngredient || [])
    .map((i) => {
      if (typeof i === "string") return i;
      return [i.originalText, i.display, i.note, i.food && i.food.name].filter(Boolean).join(" ");
    })
    .join("\n");
}

/** Mealie stores times as free text: "45 minutes", "1 hour 10 minutes", "PT50M". */
export function parseMinutes(value) {
  if (value === null || value === undefined) return null;
  const s = String(value).trim();
  if (!s) return null;
  const iso = s.match(/^P(?:T)?(?:(\d+)H)?(?:(\d+)M)?$/i);
  if (iso && (iso[1] || iso[2])) return Number(iso[1] || 0) * 60 + Number(iso[2] || 0);
  let total = 0;
  let seen = false;
  for (const m of s.matchAll(/(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b/gi)) {
    seen = true;
    const n = Number(m[1]);
    total += /^(h|hr|hrs|hour|hours)$/i.test(m[2]) ? n * 60 : n;
  }
  if (seen) return Math.round(total);
  const bare = s.match(/^(\d+)$/);
  return bare ? Number(bare[1]) : null;
}

export function timingClass(minutes) {
  if (minutes === null) return null;
  if (minutes <= 30) return "quick";
  if (minutes <= 45) return "standard";
  return "longer";
}

/**
 * Derive the constraint flags from the recipe's own data. The tags on a recipe
 * are never the source of truth — this is. Tagging reads a recipe back from
 * Mealie and derives, so a scraper quirk can never leave a tag lying.
 */
export function derive(recipe) {
  const ing = ingredientText(recipe);
  const minutes = parseMinutes(recipe.totalTime);
  return {
    tomato: tomatoHeavy(ing),
    sesame: SESAME.test(ing),
    minutes,
    timing: timingClass(minutes),
    band: minutes !== null && minutes >= 45 && minutes <= 60,
  };
}

/**
 * A dish can be tomato-heavy on fresh tomatoes alone, with no sauce, paste or
 * can in the ingredient list — shakshuka built on "6 medium tomatoes" is the
 * standing example. TOMATO_BASE catches the processed forms; this catches the
 * volume ones, while leaving a garnish or a half cup of grape tomatoes in a
 * noodle salad correctly uncounted.
 *
 * Quantities are written as "2", "2.5", "1/2", "1 1/2" or "½". Reading only the
 * trailing integer turns half a cup into two cups, so parse the whole form.
 */
const UNICODE_FRACTIONS = {
  "¼": 0.25, "½": 0.5, "¾": 0.75, "⅐": 1 / 7, "⅑": 1 / 9, "⅒": 0.1,
  "⅓": 1 / 3, "⅔": 2 / 3, "⅕": 0.2, "⅖": 0.4, "⅗": 0.6, "⅘": 0.8,
  "⅙": 1 / 6, "⅚": 5 / 6, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
};
const QTY = "((?:\\d+\\s+)?\\d+\\s*/\\s*\\d+|[\\u00BC-\\u00BE\\u2150-\\u215E]|\\d+(?:\\.\\d+)?)";

export function parseQuantity(raw) {
  const s = String(raw).trim();
  const mixed = s.match(/^(\d+)\s+(\d+)\s*\/\s*(\d+)$/);
  if (mixed) return Number(mixed[1]) + Number(mixed[2]) / Number(mixed[3]);
  const frac = s.match(/^(\d+)\s*\/\s*(\d+)$/);
  if (frac) return Number(frac[1]) / Number(frac[2]);
  if (UNICODE_FRACTIONS[s] !== undefined) return UNICODE_FRACTIONS[s];
  return /^\d+(?:\.\d+)?$/.test(s) ? Number(s) : null;
}

// Per unit, the amount of tomato that stops being an accent and starts being
// the base of the dish.
const TOMATO_QTY = [
  { re: new RegExp(`${QTY}\\s*(?:cups?)\\s+[^,\\n]{0,40}tomato`, "i"), min: 2 },
  { re: new RegExp(`${QTY}\\s*(?:lbs?|pounds?)\\s+[^,\\n]{0,40}tomato`, "i"), min: 1 },
  { re: new RegExp(`${QTY}\\s*(?:kg)\\s+[^,\\n]{0,40}tomato`, "i"), min: 0.5 },
  { re: new RegExp(`${QTY}\\s*(?:oz|ounces?)\\s+[^,\\n]{0,40}tomato`, "i"), min: 14 },
  { re: new RegExp(`${QTY}\\s+(?:medium|large|small|ripe|roma|plum)?\\s*tomatoes\\b`, "i"), min: 4 },
];

/** True when tomato is the base of the dish rather than something on top of it. */
export function tomatoHeavy(text) {
  if (TOMATO_BASE.test(text)) return true;
  for (const line of text.split("\n")) {
    if (!/tomato/i.test(line)) continue;
    if (/\bfor garnish\b|\bto garnish\b|\bfor serving\b|\bgarnish\b/i.test(line)) continue;
    for (const { re, min } of TOMATO_QTY) {
      const m = line.match(re);
      const qty = m ? parseQuantity(m[1]) : null;
      if (qty !== null && qty >= min) return true;
    }
  }
  return false;
}

/** Which ingredient lines triggered the sesame flag, for the review page. */
export function sesameComponents(recipe) {
  return (recipe.recipeIngredient || [])
    .map((i) => (typeof i === "string" ? i : [i.originalText, i.display, i.note].filter(Boolean)[0] || ""))
    .filter((line) => SESAME.test(line));
}

export const tagSlugs = (recipe) => new Set((recipe.tags || []).map((t) => t.slug || t.name).filter(Boolean));

/**
 * The full tag set a recipe should carry, given its derived flags and the role
 * the planner assigned it. Timing and flags are derived; only the role is a
 * human/planner judgement.
 */
export function constraintTagsFor(recipe, roles = []) {
  const d = derive(recipe);
  if (d.timing === null) {
    throw new Error(`${recipe.slug}: totalTime ${JSON.stringify(recipe.totalTime)} is unparsable — set it before tagging`);
  }
  const tags = [d.timing];
  if (d.band) tags.push(BAND_TAG);
  if (d.tomato) tags.push("tomato");
  if (d.sesame) tags.push("sesame");
  for (const r of roles) {
    if (!ROLE_TAGS.includes(r)) throw new Error(`unknown role tag ${r} (expected one of ${ROLE_TAGS.join("/")})`);
    tags.push(r);
  }
  return [...new Set(tags)];
}

/* ------------------------------------------------------------------ */
/* recipes                                                              */
/* ------------------------------------------------------------------ */

export function listRecipes(token, { queryFilter, perPage = 200, orderBy, orderDirection } = {}) {
  const res = must("/api/recipes", { token, query: { perPage, queryFilter, orderBy, orderDirection } });
  return (res.json && res.json.items) || [];
}

export function getRecipe(token, slug) {
  const res = request(`/api/recipes/${encodeURIComponent(slug)}`, { token });
  return res.ok ? res.json : null;
}

/**
 * Import a recipe by URL so Mealie keeps a live orgURL pointing at the source.
 * Returns the new slug. Importing by URL (rather than pasting content) is what
 * lets the review page link out and lets link-rot be detected later.
 */
export function importByUrl(token, url, { includeTags = false } = {}) {
  const res = must("/api/recipes/create/url", { token, method: "POST", body: { url, includeTags }, timeoutMs: 120000 });
  const slug = typeof res.json === "string" ? res.json : res.json && res.json.slug;
  if (!slug) throw new Error(`import of ${url} returned no slug: ${res.text.slice(0, 200)}`);
  return slug;
}

/** Scrape without importing — used to audition candidates before committing. */
export function testScrape(token, url) {
  const res = request("/api/recipes/test-scrape-url", { token, method: "POST", body: { url, useOpenAI: false }, timeoutMs: 120000 });
  return res.ok && res.json && res.json.name ? res.json : null;
}

export function patchRecipe(token, slug, patch) {
  return must(`/api/recipes/${encodeURIComponent(slug)}`, { token, method: "PATCH", body: patch }).json;
}

export function deleteRecipe(token, slug) {
  return request(`/api/recipes/${encodeURIComponent(slug)}`, { token, method: "DELETE" }).ok;
}

/**
 * Record that the household cooked a recipe.
 *
 * This MUST go through /last-made. Mealie v3 keeps `lastMade` per household,
 * and only this endpoint writes that record — a plain PATCH of the `lastMade`
 * field updates what GET returns but leaves the household row untouched, so the
 * cooldown query keeps treating the recipe as never made. Verified against
 * v3.24.0: after a plain PATCH, GET /api/households/self/recipes/<slug> still
 * reports lastMade: null and the recipe is still returned by COOLDOWN_QUERY.
 */
export function markMade(token, slug, when = new Date()) {
  return must(`/api/recipes/${encodeURIComponent(slug)}/last-made`, {
    token,
    method: "PATCH",
    body: { timestamp: new Date(when).toISOString() },
  }).json;
}

export function householdRecipeRecord(token, slug) {
  const res = request(`/api/households/self/recipes/${encodeURIComponent(slug)}`, { token });
  return res.ok ? res.json : null;
}

/**
 * Every recipe that is off the 28-day reuse cooldown, as Mealie itself judges
 * it: `lastMade <= "$NOW-28d"`. Never-made recipes are included — Mealie treats
 * an absent lastMade as long ago, which is what "new recipe" should mean.
 */
export function candidatesOffCooldown(token, extraFilter) {
  const queryFilter = extraFilter ? `(${COOLDOWN_QUERY}) AND (${extraFilter})` : COOLDOWN_QUERY;
  return listRecipes(token, { queryFilter });
}

/** The complement: what is still inside the cooldown window and must not repeat. */
export function recipesOnCooldown(token) {
  return listRecipes(token, { queryFilter: RECENTLY_MADE_QUERY });
}

/* ------------------------------------------------------------------ */
/* tags                                                                 */
/* ------------------------------------------------------------------ */

export function listTags(token) {
  const res = must("/api/organizers/tags", { token, query: { perPage: 500 } });
  return (res.json && res.json.items) || [];
}

/** Create any missing tags and return a slug -> tag object map. */
export function ensureTags(token, wanted) {
  const existing = new Map(listTags(token).map((t) => [t.slug, t]));
  for (const slug of wanted) {
    if (existing.has(slug)) continue;
    const res = request("/api/organizers/tags", { token, method: "POST", body: { name: slug } });
    if (res.ok && res.json) {
      existing.set(res.json.slug, res.json);
      continue;
    }
    // A concurrent create (or a name that slugifies to an existing tag) is fine;
    // re-read rather than failing the run.
    const again = listTags(token).find((t) => t.slug === slug);
    if (!again) throw new Error(`could not create tag ${slug}: ${res.status} ${res.text.slice(0, 200)}`);
    existing.set(again.slug, again);
  }
  return existing;
}

/**
 * Set a recipe's constraint tags. Replaces the constraint vocabulary wholesale
 * so a stale tag from an earlier week cannot survive, but leaves any unrelated
 * tag the household added by hand.
 */
export function applyTags(token, slug, wantedSlugs) {
  const vocabulary = new Set([...TIMING_TAGS, BAND_TAG, ...FLAG_TAGS, ...ROLE_TAGS]);
  const tagMap = ensureTags(token, wantedSlugs);
  const recipe = getRecipe(token, slug);
  if (!recipe) throw new Error(`cannot tag ${slug}: recipe not found`);
  const kept = (recipe.tags || []).filter((t) => !vocabulary.has(t.slug));
  const next = [...kept, ...wantedSlugs.map((s) => tagMap.get(s))].filter(Boolean);
  patchRecipe(token, slug, { tags: next });
  return next.map((t) => t.slug);
}

/* ------------------------------------------------------------------ */
/* mealplan                                                             */
/* ------------------------------------------------------------------ */

export function listMealplan(token, start, end) {
  const res = must("/api/households/mealplans", { token, query: { start_date: start, end_date: end, perPage: 200 } });
  return (res.json && res.json.items) || [];
}

export function addMealplanEntry(token, { date, recipeId, entryType = "dinner", title = "", text = "" }) {
  return must("/api/households/mealplans", {
    token,
    method: "POST",
    body: { date, entryType, title, text, recipeId },
  }).json;
}

export function deleteMealplanEntry(token, id) {
  return request(`/api/households/mealplans/${id}`, { token, method: "DELETE" }).ok;
}

/**
 * Make the week's dinners exactly `plan` ({date -> recipeId}). Existing dinner
 * entries in the window are removed first so re-running the planner is
 * idempotent instead of stacking duplicate dinners on a day.
 */
export function setWeekDinners(token, plan) {
  const dates = Object.keys(plan).sort();
  if (!dates.length) return [];
  const stale = listMealplan(token, dates[0], dates[dates.length - 1]).filter(
    (e) => (e.entryType || "").toLowerCase() === "dinner",
  );
  // Write the new week first, then retire the old entries. Deleting first would
  // leave the household with an empty week if an add failed halfway through.
  const created = dates.map((date) => addMealplanEntry(token, { date, recipeId: plan[date] }));
  for (const entry of stale) deleteMealplanEntry(token, entry.id);
  return created;
}

/**
 * The week's dinners, each with its fully-hydrated recipe and derived flags.
 * This is the shape the review page and the Signal summary both want: one
 * entry per weekday, in date order, already carrying the tomato / sesame /
 * 45-60 facts so no downstream consumer re-derives them differently.
 */
export function weekDinners(token, dates) {
  const sorted = [...dates].sort();
  const entries = listMealplan(token, sorted[0], sorted[sorted.length - 1])
    .filter((e) => (e.entryType || "").toLowerCase() === "dinner")
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  return entries.map((entry) => {
    const slug = entry.recipe && entry.recipe.slug;
    const recipe = slug ? getRecipe(token, slug) : null;
    return {
      date: entry.date,
      entryId: entry.id,
      slug,
      recipe,
      name: recipe ? recipe.name : entry.title,
      url: recipe ? recipe.orgURL : null,
      tags: recipe ? [...tagSlugs(recipe)] : [],
      flags: recipe ? derive(recipe) : null,
      sesame: recipe ? sesameComponents(recipe) : [],
    };
  });
}

/* ------------------------------------------------------------------ */
/* ratings + shopping list                                              */
/* ------------------------------------------------------------------ */

export function whoAmI(token) {
  const res = must("/api/users/self", { token });
  return res.json;
}

/**
 * One person's own ratings. Mealie only lets a token read its own user's
 * ratings, which is exactly why the planner holds a token per person: there is
 * no household-wide ratings read, and inventing one by averaging would violate
 * the per-person-votes hard requirement.
 */
export function readOwnRatings(token) {
  const res = must("/api/users/self/ratings", { token });
  const rows = (res.json && (res.json.ratings || res.json.items)) || [];
  return rows.map((r) => ({ recipeId: r.recipeId, rating: r.rating, isFavorite: !!r.isFavorite }));
}

export function setRating(token, userId, recipeIdOrSlug, { rating, isFavorite = false }) {
  return must(`/api/users/${userId}/ratings/${encodeURIComponent(recipeIdOrSlug)}`, {
    token,
    method: "POST",
    body: { rating, isFavorite },
  });
}

export function shoppingLists(token) {
  const res = must("/api/households/shopping/lists", { token, query: { perPage: 50 } });
  return (res.json && res.json.items) || [];
}

export function shoppingListItems(token, listId) {
  const res = must("/api/households/shopping/items", {
    token,
    query: { queryFilter: `shoppingListId="${listId}"`, perPage: 500 },
  });
  return (res.json && res.json.items) || [];
}

export const itemLabel = (i) => (i.display || i.note || (i.food && i.food.name) || "").trim();

/** The Mealie label a shopping item carries, or null when the food has none. */
export const itemSection = (i) => (i.label && (i.label.name || i.label.text)) || null;

/** The named shopping list, falling back to the household's first one. */
export function shoppingListNamed(token, name = "Groceries") {
  const lists = shoppingLists(token);
  if (!lists.length) throw new Error("this household has no Mealie shopping list");
  return lists.find((l) => (l.name || "").toLowerCase() === name.toLowerCase()) || lists[0];
}

/**
 * Push one recipe's ingredients onto a shopping list — the same call the
 * "Add to shopping list" button in Mealie makes, so the list carries the
 * recipe references Mealie needs to take them off again later.
 */
export function addRecipeToShoppingList(token, listId, recipeId, { scale = 1 } = {}) {
  return must(`/api/households/shopping/lists/${listId}/recipe/${recipeId}`, {
    token,
    method: "POST",
    body: { recipeIncrementQuantity: scale },
  }).json;
}

/**
 * Tick an item off (or back on). This is the ingredient check from MEAL-SPEC:
 * the household says "we already have this" and the item drops out of the
 * grocery send. Mealie's PUT replaces the row, so the item's own fields go back
 * with the flag rather than a bare {checked}.
 */
export function setItemChecked(token, item, checked = true) {
  return must(`/api/households/shopping/items/${item.id}`, {
    token,
    method: "PUT",
    body: { ...item, checked },
  }).json;
}

/* ------------------------------------------------------------------ */
/* the week                                                             */
/* ------------------------------------------------------------------ */

/**
 * The five weekday dates of the week starting on `monday`. Everything that
 * speaks about "the week" — the planner, the Signal summary, the grocery
 * send — resolves it here so they cannot disagree about which days they mean.
 */
export function weekDates(monday, length = 5) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(monday))) {
    throw new Error(`week start must be YYYY-MM-DD, got ${monday}`);
  }
  const start = new Date(`${monday}T00:00:00Z`);
  if (Number.isNaN(start.getTime())) throw new Error(`${monday} is not a real date`);
  return Array.from({ length }, (_, i) => {
    const d = new Date(start);
    d.setUTCDate(d.getUTCDate() + i);
    return d.toISOString().slice(0, 10);
  });
}
