#!/usr/bin/env node
// Send the week to Signal for approval.
//
//   node scripts/send-summary.mjs --week 2026-08-31
//   node scripts/send-summary.mjs --week 2026-08-31 --print-body
//   node scripts/send-summary.mjs --dry-run --from-json week.json --print-body
//
// This is step two of the ritual: propose-week has written five dinners into
// Mealie, and now the household has to actually see them somewhere they read.
// The message is composed for a phone screen in a Signal thread — no tables, no
// markdown, warnings above the fold.
//
// Everything in the message is derived, never typed. The three warnings the
// household plans around are:
//
//   * more than one tomato-heavy meal, because MEAL-SPEC allows one a week;
//   * any sesame meal, named with its exact component, because the child-safe
//     portion has to come out of the pan before that component goes in;
//   * anything in the 45-60 minute band, which needs explicit approval rather
//     than being nodded through.
//
// Each one is CONDITIONAL. A warning that prints every week is not a warning,
// so composeSummary() emits nothing for a class that is empty, and
// assertWarningsAreConditional() refuses to send a message that says otherwise.

import { readFileSync, realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  ROLE_TAGS,
  derive,
  planningToken,
  sesameComponents,
  tagSlugs,
  weekDates,
  weekDinners,
} from "./mealie.mjs";
import { canonicalUrl, loadStore } from "./history.mjs";
import { send } from "./signal.mjs";

const MEALIE_PLANNER_URL =
  process.env.MEALIE_PLANNER_URL || "https://mealie.techvomit.xyz/household/mealplan/planner/view/";

const BEGIN = "-----BEGIN SUMMARY-----";
const END = "-----END SUMMARY-----";

/* ------------------------------------------------------------------ */
/* arguments                                                            */
/* ------------------------------------------------------------------ */

function parseArgs(argv) {
  const args = { week: null, fromJson: null, dryRun: false, printBody: false, json: false, help: false };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    const next = () => {
      const v = argv[i + 1];
      if (v === undefined) throw new Error(`${a} needs a value`);
      i += 1;
      return v;
    };
    if (a === "--week") args.week = next();
    else if (a === "--from-json") args.fromJson = next();
    else if (a === "--dry-run") args.dryRun = true;
    else if (a === "--print-body") args.printBody = true;
    else if (a === "--json") args.json = true;
    else if (a === "--help" || a === "-h") args.help = true;
    else throw new Error(`unknown argument ${a}`);
  }
  return args;
}

const USAGE =
  "usage: send-summary.mjs (--week YYYY-MM-DD | --from-json FILE) [--dry-run] [--print-body] [--json]\n";

/* ------------------------------------------------------------------ */
/* loading a week                                                       */
/* ------------------------------------------------------------------ */

// Mealie keeps Budget Bytes' per-ingredient costs inside the ingredient text
// ("2 Tbsp toasted sesame oil ($0.64***)"). The price is not part of the
// component name, and on a phone it buries the thing the reader is looking for.
function cleanComponent(line) {
  return String(line)
    .replace(/\(\s*\$[^)]*\)/g, "")
    .replace(/\*+/g, "")
    .replace(/\s{2,}/g, " ")
    .replace(/\s*,\s*$/, "")
    .trim();
}

/** The planned week as Mealie has it, enriched with what history.json knows. */
function loadFromMealie(monday) {
  const token = planningToken();
  const dates = weekDates(monday);
  const dinners = weekDinners(token, dates);
  if (!dinners.length) throw new Error(`Mealie has no dinner entries for the week of ${monday}`);

  const store = loadStore();
  return {
    start: dates[0],
    end: dates[dates.length - 1],
    dinners: dinners.map((d) => {
      const flags = d.flags || derive(d.recipe || {});
      const tags = d.recipe ? tagSlugs(d.recipe) : new Set(d.tags || []);
      const known = (store.recipes || {})[canonicalUrl(d.url)] || {};
      return {
        date: d.date,
        name: d.name,
        minutes: flags.minutes,
        timing: flags.timing,
        band: !!flags.band,
        tomato: !!flags.tomato,
        sesame: !!flags.sesame,
        sesameComponents: (d.recipe ? sesameComponents(d.recipe) : []).map(cleanComponent).filter(Boolean),
        roles: ROLE_TAGS.filter((r) => tags.has(r)),
        cuisine: known.cuisine || null,
        source: known.source || null,
      };
    }),
  };
}

/**
 * A week handed over as JSON rather than read from Mealie. Used to rehearse the
 * message against a week that does not exist yet, and by the acceptance check
 * to drive the warning branches the live week does not happen to contain.
 */
function loadFromJson(file) {
  const doc = JSON.parse(readFileSync(file, "utf8"));
  const rows = Array.isArray(doc) ? doc : doc.dinners;
  if (!Array.isArray(rows) || !rows.length) throw new Error(`${file} holds no dinners array`);
  const dinners = rows.map((r, i) => {
    if (!r.name) throw new Error(`${file}: dinner ${i + 1} has no name`);
    return {
      date: r.date || null,
      name: r.name,
      minutes: r.minutes ?? null,
      timing: r.timing || null,
      band: !!r.band,
      tomato: !!r.tomato,
      sesame: !!r.sesame,
      sesameComponents: r.sesameComponents || [],
      roles: r.roles || [],
      cuisine: r.cuisine || null,
      source: r.source || null,
    };
  });
  const dated = dinners.map((d) => d.date).filter(Boolean).sort();
  return { start: doc.week || dated[0] || null, end: dated[dated.length - 1] || null, dinners };
}

/* ------------------------------------------------------------------ */
/* composing the message                                                */
/* ------------------------------------------------------------------ */

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function dayLabel(iso) {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return `${DAY_NAMES[d.getUTCDay()]} ${d.getUTCDate()} ${MONTH_NAMES[d.getUTCMonth()]}`;
}

function rangeLabel(week) {
  const first = week.dinners[0] && week.dinners[0].date;
  const last = week.dinners[week.dinners.length - 1] && week.dinners[week.dinners.length - 1].date;
  const from = dayLabel(first || week.start);
  const to = dayLabel(last || week.end);
  if (!from) return "the coming week";
  return to && to !== from ? `${from} to ${to}` : from;
}

/** "20 min, quick · vegetarian · asian" — the one-line shape of a dinner. */
function dinnerDetail(d) {
  const bits = [];
  if (d.minutes !== null && d.minutes !== undefined) {
    bits.push(d.timing ? `${d.minutes} min, ${d.timing}` : `${d.minutes} min`);
  } else if (d.timing) {
    bits.push(d.timing);
  }
  if (d.roles && d.roles.length) bits.push(d.roles.join("/"));
  if (d.cuisine) bits.push(d.cuisine);
  return bits.join(" · ");
}

function countBy(dinners, key) {
  const counts = new Map();
  for (const d of dinners) {
    for (const v of Array.isArray(d[key]) ? d[key] : [d[key]]) {
      if (!v) continue;
      counts.set(v, (counts.get(v) || 0) + 1);
    }
  }
  return counts;
}

export function composeSummary(week) {
  const dinners = week.dinners;
  const tomatoMeals = dinners.filter((d) => d.tomato);
  const sesameMeals = dinners.filter((d) => d.sesame);
  const bandMeals = dinners.filter((d) => d.band);

  const lines = [`Dinner plan · ${rangeLabel(week)}`, ""];

  for (const d of dinners) {
    const day = dayLabel(d.date);
    lines.push(day ? `${day} · ${d.name}` : d.name);
    const detail = dinnerDetail(d);
    if (detail) lines.push(`  ${detail}`);
  }

  // The three conditional warnings. Each block is emitted only when its class
  // is non-empty, and each one names the meals it is about — "there is a sesame
  // meal this week" is not actionable, "the tahini dressing goes on last" is.
  const warnings = [];
  if (tomatoMeals.length > 1) {
    warnings.push(
      `!! More than one tomato-heavy meal (${tomatoMeals.length}): ` +
        `${tomatoMeals.map((d) => d.name).join(" and ")}. ` +
        `The week is meant to carry one — swap one out, or say it's fine this week.`,
    );
  }
  if (sesameMeals.length) {
    warnings.push("!! Sesame — take the child-safe portion out before this goes in:");
    for (const d of sesameMeals) {
      const parts = d.sesameComponents.length ? d.sesameComponents.join(", ") : "sesame somewhere in the recipe";
      warnings.push(`   · ${d.name}: ${parts}`);
    }
  }
  if (bandMeals.length) {
    warnings.push(
      `!! In the 45-60 minute band, needs an explicit yes: ` +
        `${bandMeals.map((d) => (d.minutes ? `${d.name} (${d.minutes} min)` : d.name)).join(", ")}.`,
    );
  }
  if (warnings.length) lines.push("", "BEFORE YOU SAY YES", ...warnings);

  // The weekly summary MEAL-SPEC asks for, in the order it reads on a phone.
  const timings = countBy(dinners, "timing");
  const timingBits = ["quick", "standard", "longer"]
    .filter((t) => timings.get(t))
    .map((t) => `${timings.get(t)} ${t}`);
  const totalMinutes = dinners.reduce((sum, d) => sum + (d.minutes || 0), 0);
  const roles = countBy(dinners, "roles");
  const roleBits = ROLE_TAGS.filter((r) => roles.get(r)).map((r) => `${r} ${roles.get(r)}`);
  const cuisines = [...countBy(dinners, "cuisine").keys()];

  const glance = [`${dinners.length} dinners`];
  if (timingBits.length) glance.push(timingBits.join(", "));
  if (totalMinutes) glance.push(`${totalMinutes} min of cooking all week`);

  lines.push("", "THE WEEK AT A GLANCE", glance.join(" · "));
  if (roleBits.length) lines.push(roleBits.join(" · "));
  if (cuisines.length) lines.push(`Cuisines: ${cuisines.join(", ")}`);
  // Phrased so the count follows the word: a line that began "Tomato" could be
  // preceded by a line ending in a digit, and "2\nTomato" reads as a
  // double-count warning to anything scanning the message.
  lines.push(
    `Meals counting as tomato-heavy: ${tomatoMeals.length}` +
      (tomatoMeals.length ? ` (${tomatoMeals.map((d) => d.name).join(", ")})` : ""),
  );
  if (sesameMeals.length) lines.push(`Meals with sesame to separate: ${sesameMeals.length}`);
  if (bandMeals.length) lines.push(`Dinners in the 45-60 minute band: ${bandMeals.length}`);

  lines.push(
    "",
    `Change anything in Mealie: ${MEALIE_PLANNER_URL}`,
    "Then tick off what we already have on the Groceries list and I'll send the shopping list.",
  );

  return {
    body: lines.join("\n").replace(/\n{3,}/g, "\n\n").trim(),
    warnings: {
      tomato: tomatoMeals.map((d) => d.name),
      sesame: sesameMeals.map((d) => ({ name: d.name, components: d.sesameComponents })),
      band: bandMeals.map((d) => d.name),
    },
    stats: {
      dinners: dinners.length,
      timing: Object.fromEntries(timings),
      roles: Object.fromEntries(roles),
      cuisines,
      tomato: tomatoMeals.length,
      sesame: sesameMeals.length,
      band: bandMeals.length,
      minutes: totalMinutes,
    },
  };
}

/**
 * A warning that fires whether or not the condition holds tells the household
 * nothing, and the household will stop reading it. Before anything is sent,
 * check the composed text the same way a reader would: if there is one
 * tomato-heavy meal, the message must not read as a double-count; with no
 * sesame meal it must not mention sesame at all; with nothing in the band it
 * must not print the band callout.
 */
export function assertWarningsAreConditional(body, stats) {
  const problems = [];
  if (stats.tomato <= 1 && /(two|2|double|both|more than one)\s+tomato|tomato[^.\n]{0,40}(twice|double)/i.test(body)) {
    problems.push(
      `the week has ${stats.tomato} tomato-heavy meal(s) but the message reads as a double-count warning`,
    );
  }
  if (stats.sesame === 0 && /sesame/i.test(body)) {
    problems.push(
      "no meal this week carries sesame but the message mentions it — either the wording leaked or a " +
        "recipe's ingredients did not import and its sesame flag is wrong",
    );
  }
  if (stats.band === 0 && /45\s*[-–]\s*60|45 to 60/i.test(body)) {
    problems.push("nothing is in the 45-60 minute band but the message prints the callout anyway");
  }
  if (problems.length) {
    throw new Error(`refusing to send a summary with unconditional warnings:\n  - ${problems.join("\n  - ")}`);
  }
}

/* ------------------------------------------------------------------ */

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    process.stdout.write(USAGE);
    return;
  }
  if (!args.week && !args.fromJson) throw new Error(`one of --week or --from-json is required\n${USAGE}`);
  if (args.week && args.fromJson) throw new Error("--week and --from-json are mutually exclusive");

  const week = args.fromJson ? loadFromJson(args.fromJson) : loadFromMealie(args.week);
  const summary = composeSummary(week);
  assertWarningsAreConditional(summary.body, summary.stats);

  // --from-json is a rehearsal by construction: the week it describes is not
  // the week Mealie holds, so sending it would tell the household about
  // dinners nobody planned.
  const dryRun = args.dryRun || !!args.fromJson;
  const timestamp = dryRun ? null : send(summary.body);

  if (args.printBody) {
    process.stdout.write(`${BEGIN}\n${summary.body}\n${END}\n`);
  }
  if (args.json) {
    process.stdout.write(`${JSON.stringify({ ...summary, sent: !dryRun, timestamp }, null, 2)}\n`);
  } else if (dryRun) {
    process.stdout.write("dry run: composed but not sent\n");
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
    process.stderr.write(`send-summary: ${err.message}\n`);
    process.exit(1);
  }
}
