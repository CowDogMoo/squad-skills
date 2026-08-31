#!/usr/bin/env node
// Propose one week of dinners into Mealie.
//
//   node scripts/propose-week.mjs --week 2026-08-31                 # plan only
//   node scripts/propose-week.mjs --week 2026-08-31 --apply         # write it
//   node scripts/propose-week.mjs --week 2026-08-31 --apply --json  # machine-readable
//
// The flow, in order:
//
//   1. Take the candidate batch. Discovery is NOT this skill's job -- the public
//      weekday-dinner-recipes skill pulls rated, link-verified, season-
//      appropriate recipes off the curated sources, and references/candidate-
//      pool.json is that batch annotated with dish/source/cuisine/role/protein.
//   2. Drop whatever the household's scoped feedback removes (scope-feedback).
//   3. Drop whatever is still inside the 28-day reuse cooldown, asking Mealie
//      itself with `lastMade <= "$NOW-28d"` rather than recomputing dates here.
//   4. Audition the survivors with Mealie's scraper to learn their real total
//      time and ingredients.
//   5. Pick the five that make the best week under MEAL-SPEC: a quick night, at
//      most one tomato-heavy meal, protein/cuisine variety, and not a pile of
//      45-60 minute dinners.
//   6. Import the five by URL so each keeps a live orgURL, normalize totalTime,
//      tag them from their OWN ingredients, and write the mealplan.
//   7. Record the proposals in history.json with per-person vote slots.

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  BAND_TAG,
  COOLDOWN_DAYS,
  COOLDOWN_QUERY,
  applyTags,
  candidatesOffCooldown,
  constraintTagsFor,
  derive,
  getRecipe,
  importByUrl,
  parseMinutes,
  patchRecipe,
  PEOPLE,
  planningToken,
  readPerPersonVotes,
  recipesOnCooldown,
  sesameComponents,
  setWeekDinners,
  testScrape,
} from "./mealie.mjs";
import { HISTORY_FILE, canonicalUrl, loadStore, recordProposal, saveStore, scopeCandidates } from "./history.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_POOL = resolve(HERE, "../references/candidate-pool.json");
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const WEEK_LENGTH = DAYS.length;

/* ------------------------------------------------------------------ */

function parseArgs(argv) {
  const args = { week: null, pool: DEFAULT_POOL, store: HISTORY_FILE, apply: false, json: false };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    const next = () => {
      const v = argv[i + 1];
      if (v === undefined) throw new Error(`${a} needs a value`);
      i += 1;
      return v;
    };
    if (a === "--week") args.week = next();
    else if (a === "--candidates" || a === "--pool") args.pool = next();
    else if (a === "--store") args.store = next();
    else if (a === "--apply") args.apply = true;
    else if (a === "--json") args.json = true;
    else if (a === "--help" || a === "-h") args.help = true;
    else throw new Error(`unknown argument ${a}`);
  }
  return args;
}

/** Monday of the coming week, when --week is not given. */
function nextMonday(from = new Date()) {
  const d = new Date(Date.UTC(from.getFullYear(), from.getMonth(), from.getDate()));
  d.setUTCDate(d.getUTCDate() + ((8 - d.getUTCDay()) % 7 || 7));
  return d.toISOString().slice(0, 10);
}

function weekDates(monday) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(monday)) throw new Error(`--week must be YYYY-MM-DD, got ${monday}`);
  const start = new Date(`${monday}T00:00:00Z`);
  return Array.from({ length: WEEK_LENGTH }, (_, i) => {
    const d = new Date(start);
    d.setUTCDate(d.getUTCDate() + i);
    return d.toISOString().slice(0, 10);
  });
}

/* ------------------------------------------------------------------ */
/* week shape                                                           */
/* ------------------------------------------------------------------ */

const VEGGIE_ROLES = new Set(["vegetarian", "vegan"]);


/**
 * Re-key both people's Mealie votes by canonical source URL, which is the only
 * identity a candidate has before it is imported. Votes on recipes whose source
 * URL is unknown are dropped rather than guessed at.
 */
export function voteIndexByUrl({ votes = {}, urlByRecipeId = {} } = {}) {
  const out = {};
  for (const [person, byId] of Object.entries(votes)) {
    for (const [recipeId, rating] of Object.entries(byId)) {
      const url = urlByRecipeId[recipeId];
      if (!url) continue;
      const key = canonicalUrl(url);
      out[key] ||= {};
      out[key][person] = rating;
    }
  }
  return out;
}

/**
 * Score a candidate week against MEAL-SPEC's weekly summary. Higher is better.
 * The scoring is deliberately explicit rather than a black box, because the
 * review page has to be able to say *why* a week was proposed.
 */
export function scoreWeek(week, { sourcePriors = {}, votesByUrl = {} } = {}) {
  const reasons = [];
  let score = 0;

  const quick = week.filter((c) => c.flags.timing === "quick").length;
  const tomato = week.filter((c) => c.flags.tomato).length;
  const sesame = week.filter((c) => c.flags.sesame).length;
  const band = week.filter((c) => c.flags.band).length;
  const veg = week.filter((c) => VEGGIE_ROLES.has(c.role)).length;
  const roles = new Set(week.map((c) => c.role));
  // MEAL-SPEC's roles are a menu classification, not a protein: two "flex"
  // nights can both be fish. Track the protein separately, or a week of
  // salmon, cod and shrimp scores as varied.
  const proteins = new Set(week.map((c) => c.protein).filter(Boolean));
  const cuisines = new Set(week.map((c) => c.cuisine));
  const sources = new Set(week.map((c) => c.source));
  const minutes = week.reduce((sum, c) => sum + (c.flags.minutes || 0), 0);

  if (quick >= 1) { score += 60; } else { reasons.push("no quick night"); score -= 120; }
  if (veg >= 1) { score += 30; } else { reasons.push("no vegetarian night"); score -= 60; }
  if (tomato > 1) { reasons.push(`${tomato} tomato-heavy meals`); score -= 70 * (tomato - 1); }
  if (sesame > 1) { reasons.push(`${sesame} sesame meals to separate`); score -= 20 * (sesame - 1); }
  if (band > 1) { reasons.push(`${band} meals in the 45-60 band`); score -= 25 * (band - 1); }

  score += 16 * roles.size + 14 * proteins.size + 11 * cuisines.size + 7 * sources.size;
  // Distinct-role count alone is not balance: three vegetarian nights and two
  // chicken nights still reads as two roles. Penalize any role that takes over
  // the week, which is what "accidentally repetitive" looks like in practice.
  const roleCounts = new Map();
  for (const c of week) roleCounts.set(c.role, (roleCounts.get(c.role) || 0) + 1);
  for (const [role, n] of roleCounts) {
    if (n > 2) { reasons.push(`${n} ${role} meals`); score -= 25 * (n - 2); }
  }
  // Three of five dinners off one blog is a narrow week, whatever the ratings
  // say. MEAL-HISTORY-SPEC is explicit that source priors must not collapse the
  // rotation onto a favorite site.
  const sourceCounts = new Map();
  for (const c of week) sourceCounts.set(c.source, (sourceCounts.get(c.source) || 0) + 1);
  for (const [source, n] of sourceCounts) {
    if (source && n > 2) { reasons.push(`${n} recipes from ${source}`); score -= 20 * (n - 2); }
  }
  const proteinCounts = new Map();
  for (const c of week) proteinCounts.set(c.protein, (proteinCounts.get(c.protein) || 0) + 1);
  for (const [protein, n] of proteinCounts) {
    if (protein && n > 2) { reasons.push(`${n} ${protein} meals`); score -= 30 * (n - 2); }
  }
  // A week that adds up to more than about three and a half hours of cooking is
  // a week somebody bails on by Wednesday.
  if (minutes > 200) { reasons.push(`${minutes} minutes of cooking across the week`); score -= (minutes - 200); }

  for (const c of week) {
    score += 10 * (sourcePriors[c.source]?.prior || 0);
    score -= 0.5 * (c.rank || 0);
    if (c.penalty) score -= 15 * c.penalty;
  }

  // MEAL-HISTORY-SPEC treats the two votes on a recipe as two separate facts,
  // never as one household number. So a dislike is charged on its own terms even
  // when the other person loved the dish -- averaging a 5 and a 2 into "fine"
  // erases exactly the disagreement the planner is supposed to act on -- and the
  // household-favorite bonus is reserved for actual agreement.
  for (const c of week) {
    const cast = Object.entries(votesByUrl[canonicalUrl(c.url)] || {})
      .filter(([, r]) => typeof r === "number");
    if (!cast.length) continue;
    const label = c.title || c.dish || c.url;
    const liked = cast.filter(([, r]) => r >= 4);
    const disliked = cast.filter(([, r]) => r <= 2);
    for (const [person, r] of disliked) {
      reasons.push(`${person} rated ${label} ${r}/5`);
      score -= 45 * (3 - r);
    }
    if (disliked.length === 0 && liked.length === cast.length && cast.length === PEOPLE.length) {
      reasons.push(`both rated ${label} highly`);
      score += 55;
    } else {
      for (const [, r] of liked) score += 18 * (r - 3);
    }
  }
  return { score, reasons, summary: { quick, tomato, sesame, band, veg, roles: roles.size, proteins: proteins.size, cuisines: cuisines.size, sources: sources.size, minutes } };
}

/** Best WEEK_LENGTH-subset of the candidates. The pool is small; search it exhaustively. */
export function chooseWeek(candidates, opts) {
  if (candidates.length < WEEK_LENGTH) {
    throw new Error(`only ${candidates.length} usable candidates, need ${WEEK_LENGTH}`);
  }
  // The search is exhaustive because a good week is a property of the whole
  // set, not of any one dinner. C(n,5) stays cheap up to a couple of dozen
  // candidates; beyond that, shortlist by editorial rank first so the run
  // cannot quietly turn into minutes of combinatorics.
  const MAX_SEARCH = 24;
  if (candidates.length > MAX_SEARCH) {
    candidates = [...candidates].sort((a, b) => (a.rank || 99) - (b.rank || 99)).slice(0, MAX_SEARCH);
  }
  let best = null;
  const pick = [];
  const walk = (start) => {
    if (pick.length === WEEK_LENGTH) {
      const scored = scoreWeek(pick, opts);
      if (!best || scored.score > best.score) best = { ...scored, week: [...pick] };
      return;
    }
    for (let i = start; i < candidates.length; i += 1) {
      pick.push(candidates[i]);
      walk(i + 1);
      pick.pop();
    }
  };
  walk(0);
  return best;
}

/* ------------------------------------------------------------------ */

/** Mealie sometimes imports a recipe with no usable totalTime. Rebuild one rather than guessing. */
function resolveTotalTime(recipe, scraped) {
  if (parseMinutes(recipe.totalTime) !== null) return null;
  const parts = [recipe.prepTime, recipe.performTime, recipe.cookTime].map(parseMinutes).filter((m) => m !== null);
  const scrapedTotal = scraped ? parseMinutes(scraped.totalTime) : null;
  const minutes = scrapedTotal ?? (parts.length ? parts.reduce((a, b) => a + b, 0) : null);
  if (minutes === null) {
    throw new Error(
      `${recipe.slug}: the source page gave no usable total time. Set it by hand ` +
        `(PATCH /api/recipes/${recipe.slug} {"totalTime":"40 Minutes"}) before this recipe can be tagged.`,
    );
  }
  return `${minutes} Minutes`;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    process.stdout.write("usage: propose-week.mjs [--week YYYY-MM-DD] [--candidates file] [--store file] [--apply] [--json]\n");
    return;
  }

  const monday = args.week || nextMonday();
  const dates = weekDates(monday);
  const token = planningToken();
  const store = loadStore(args.store);

  const poolDoc = JSON.parse(readFileSync(args.pool, "utf8"));
  const pool = Array.isArray(poolDoc) ? poolDoc : poolDoc.pool || poolDoc.candidates;
  if (!Array.isArray(pool) || !pool.length) throw new Error(`${args.pool} holds no candidate pool`);

  // 2. Scoped feedback. A recipe-scoped block kills one URL; only an explicitly
  //    broad reason reaches the dish, the ingredient or the source.
  const { kept, dropped } = scopeCandidates(pool, store.blocks || []);

  // 3. The 28-day reuse cooldown, answered by Mealie.
  const onCooldown = recipesOnCooldown(token);
  const offCooldown = candidatesOffCooldown(token);
  const cooldownUrls = new Set();
  for (const stub of onCooldown) {
    const full = getRecipe(token, stub.slug);
    if (full && full.orgURL) cooldownUrls.add(canonicalUrl(full.orgURL));
  }
  const importedBySource = new Map();
  for (const stub of offCooldown) {
    const full = getRecipe(token, stub.slug);
    if (full && full.orgURL) importedBySource.set(canonicalUrl(full.orgURL), full);
  }

  const eligible = [];
  const skipped = dropped.map((c) => ({ url: c.url, why: `blocked: ${c.blockedBy.map((b) => `${b.person} ${b.reason}`).join("; ")}` }));
  for (const candidate of kept) {
    const key = canonicalUrl(candidate.url);
    if (cooldownUrls.has(key)) {
      skipped.push({ url: candidate.url, why: `made within the last ${COOLDOWN_DAYS} days (${COOLDOWN_QUERY} excludes it)` });
      continue;
    }
    // 4. Learn the real time and ingredients before committing to anything.
    const existing = importedBySource.get(key);
    const scraped = existing || testScrape(token, candidate.url);
    if (!scraped) {
      skipped.push({ url: candidate.url, why: "Mealie could not scrape this page" });
      continue;
    }
    const flags = derive(scraped);
    if (flags.timing === null) {
      skipped.push({ url: candidate.url, why: `no usable total time (${JSON.stringify(scraped.totalTime)})` });
      continue;
    }
    eligible.push({ ...candidate, flags, scraped, existingSlug: existing ? existing.slug : null });
  }

  // 5. Pick the week.
  // Both people's votes, read per person. Selection is the only place they can
  // change anything: a vote nobody reads is a vote that does not exist.
  const voteRead = readPerPersonVotes();
  const votesByUrl = voteIndexByUrl(voteRead);
  for (const err of voteRead.errors) {
    console.error(`warning: could not read votes for ${err} — proposing without them`);
  }

  const best = chooseWeek(eligible, { sourcePriors: store.sourcePriors || {}, votesByUrl });
  // Ramp up: the quickest dinner lands on Monday, the longest on Friday.
  const ordered = [...best.week].sort((a, b) => a.flags.minutes - b.flags.minutes || (a.rank || 0) - (b.rank || 0));
  const plan = ordered.map((c, i) => ({ ...c, date: dates[i], day: DAYS[i] }));

  const warnings = [];
  if (best.summary.tomato > 1) warnings.push(`${best.summary.tomato} tomato-heavy meals this week -- the household target is at most one.`);
  for (const c of plan) {
    if (c.flags.sesame) {
      const components = sesameComponents(c.scraped);
      warnings.push(`${c.title} (${c.day}) contains sesame: ${components.join("; ") || "see ingredients"}. Separate the child-safe portion before that component goes in.`);
    }
    if (c.flags.band) warnings.push(`${c.title} (${c.day}) is ${c.flags.minutes} minutes -- inside the ${BAND_TAG} band, needs explicit approval.`);
  }

  const applied = [];
  if (args.apply) {
    // 6. Import by URL so every recipe keeps a live source link.
    for (const c of plan) {
      let slug = c.existingSlug;
      if (!slug) slug = importByUrl(token, c.url);
      let recipe = getRecipe(token, slug);
      if (!recipe) throw new Error(`imported ${c.url} as ${slug} but cannot read it back`);

      const fixedTime = resolveTotalTime(recipe, c.scraped);
      if (fixedTime) {
        patchRecipe(token, slug, { totalTime: fixedTime });
        recipe = getRecipe(token, slug);
      }
      // Tags are derived from the recipe as Mealie actually stored it, never
      // from the candidate file, so a tag can never disagree with the pantry.
      const tags = constraintTagsFor(recipe, [c.role]);
      applyTags(token, slug, tags);
      recipe = getRecipe(token, slug);
      applied.push({ ...c, slug, recipeId: recipe.id, tags, stored: derive(recipe), totalTime: recipe.totalTime });
    }

    setWeekDinners(token, Object.fromEntries(applied.map((c) => [c.date, c.recipeId])));

    // 7. History: per-person vote slots, waiting to be filled in after dinner.
    for (const c of applied) {
      recordProposal(store, {
        url: c.url,
        title: c.title,
        source: c.source,
        dish: c.dish,
        cuisine: c.cuisine,
        role: c.role,
        mealieSlug: c.slug,
        mealieId: c.recipeId,
        totalMinutes: c.stored.minutes,
        timing: c.stored.timing,
        tomato: c.stored.tomato,
        sesame: c.stored.sesame,
        band4560: c.stored.band,
        plannedFor: c.date,
        proposedAt: new Date().toISOString().slice(0, 10),
      });
    }
    saveStore(store, args.store);
  }

  const result = {
    week: monday,
    dates,
    applied: args.apply,
    cooldown: { days: COOLDOWN_DAYS, query: COOLDOWN_QUERY, excluded: [...cooldownUrls] },
    considered: pool.length,
    eligible: eligible.length,
    skipped,
    summary: best.summary,
    tradeoffs: best.reasons,
    warnings,
    dinners: (args.apply ? applied : plan).map((c) => ({
      day: c.day,
      date: c.date,
      title: c.title,
      url: c.url,
      source: c.source,
      cuisine: c.cuisine,
      role: c.role,
      protein: c.protein,
      minutes: c.flags.minutes,
      timing: c.flags.timing,
      band4560: c.flags.band,
      tomato: c.flags.tomato,
      sesame: c.flags.sesame,
      slug: c.slug || null,
      tags: c.tags || null,
      why: c.why,
    })),
  };

  if (args.json) {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return;
  }

  process.stdout.write(`Week of ${monday}${args.apply ? "" : "  (dry run -- pass --apply to write it)"}\n\n`);
  for (const d of result.dinners) {
    const flags = [d.timing, d.band4560 ? BAND_TAG : null, d.tomato ? "tomato" : null, d.sesame ? "sesame" : null, d.role]
      .filter(Boolean)
      .join(", ");
    process.stdout.write(`  ${d.day} ${d.date}  ${d.title}\n`);
    process.stdout.write(`        ${d.minutes} min [${flags}]  ${d.source}  ${d.url}\n`);
    if (d.why) process.stdout.write(`        ${d.why}\n`);
  }
  const s = result.summary;
  process.stdout.write(
    `\nSummary: ${s.veg} vegetarian, ${s.roles} roles, ${s.proteins} proteins, ${s.cuisines} cuisines, ` +
      `${s.quick} quick / ${WEEK_LENGTH - s.quick} longer, ${s.tomato} tomato-heavy, ${s.sesame} with sesame, ` +
      `${s.band} in the ${BAND_TAG} band, ${s.minutes} minutes total.\n`,
  );
  for (const w of warnings) process.stdout.write(`  ! ${w}\n`);
  for (const skip of skipped) process.stdout.write(`  - skipped ${skip.url}: ${skip.why}\n`);
  if (args.apply) process.stdout.write(`\nWrote ${result.dinners.length} dinners to Mealie and recorded them in ${args.store}\n`);
}

// scoreWeek and chooseWeek are exported so the week policy can be tested
// without a Mealie or 1Password round trip, so only run the CLI when this file
// is the entry point rather than on every import.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    main();
  } catch (err) {
    process.stderr.write(`propose-week: ${err.message}\n`);
    process.exit(1);
  }
}
