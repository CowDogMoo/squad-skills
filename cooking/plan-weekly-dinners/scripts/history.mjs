// The household's recipe history, feedback, and reuse logic.
//
// Implements MEAL-HISTORY-SPEC: per-person votes (never a household average),
// scoped negative feedback (a thumbs down on one recipe does not condemn the
// dish, the ingredient, the cuisine, or the source), source-level priors kept
// separately from recipe-level signals, and confidence that grows with repeated
// signals instead of overreacting to one bad night.
//
// The store lives outside any repo, in $XDG_STATE_HOME: it is per-machine
// runtime state, not skill source.

import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

export const HISTORY_FILE =
  process.env.MEAL_HISTORY_FILE ||
  join(process.env.XDG_STATE_HOME || join(homedir(), ".local", "state"), "meal-planner", "history.json");

export const SCHEMA_VERSION = 1;

/** The 12 structured negative-feedback reasons from MEAL-HISTORY-SPEC. */
export const REASONS = [
  "i-did-not-like-this-recipe",
  "i-do-not-like-this-dish",
  "i-do-not-like-a-specific-ingredient",
  "too-much-work",
  "took-too-long",
  "too-heavy",
  "not-flavorful-enough",
  "too-spicy",
  "too-repetitive",
  "bad-source",
  "did-not-work-for-our-household",
  "other",
];

export const SCOPES = ["recipe", "dish", "ingredient", "source", "cuisine"];

/**
 * How wide a reason is allowed to reach on its own.
 *
 * "The scope of the learning should match the selected reason." A generic
 * thumbs down means "not this exact recipe" and nothing more; only an explicit
 * broad reason licenses a broad block. Anything wider than the reason licenses
 * is advisory until repeated (see CONFIDENCE_THRESHOLD).
 */
export const LICENSED_SCOPES = {
  "i-did-not-like-this-recipe": ["recipe"],
  "i-do-not-like-this-dish": ["recipe", "dish"],
  "i-do-not-like-a-specific-ingredient": ["recipe", "ingredient"],
  "too-much-work": ["recipe"],
  "took-too-long": ["recipe"],
  "too-heavy": ["recipe"],
  "not-flavorful-enough": ["recipe"],
  "too-spicy": ["recipe"],
  "too-repetitive": ["recipe", "dish", "cuisine"],
  "bad-source": ["recipe", "source"],
  "did-not-work-for-our-household": ["recipe"],
  other: ["recipe"],
};

// One interaction is weak evidence. A block that reaches wider than its reason
// licenses only becomes binding once the household has said it this many times.
export const CONFIDENCE_THRESHOLD = 2;

/* ------------------------------------------------------------------ */
/* normalization                                                        */
/* ------------------------------------------------------------------ */

/** Canonical form of a recipe URL: host without www, path without a trailing slash, no query or fragment. */
export function canonicalUrl(url) {
  if (!url) return "";
  const raw = String(url).trim();
  try {
    const u = new URL(raw);
    const host = u.hostname.toLowerCase().replace(/^www\./, "");
    const path = u.pathname.replace(/\/+$/, "").toLowerCase();
    return `${host}${path}`;
  } catch {
    return raw.toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/[/?#].*$/, "");
  }
}

/** Host of a candidate, from its explicit source or its URL. */
export function canonicalSource(value, url) {
  const raw = String(value || "").trim();
  if (raw) {
    const host = raw.replace(/^https?:\/\//i, "").replace(/^www\./i, "").split("/")[0].toLowerCase();
    if (host) return host;
  }
  const c = canonicalUrl(url);
  return c ? c.split("/")[0] : "";
}

export const normalizeText = (value) =>
  String(value || "")
    .toLowerCase()
    .replace(/[‘’]/g, "'")
    .replace(/[^a-z0-9']+/g, " ")
    .trim()
    .replace(/\s+/g, " ");

/** Whole-phrase, word-boundary containment: "fennel" hits "1 bulb fennel" but never "star anise". */
export function containsPhrase(haystack, phrase) {
  const h = normalizeText(haystack);
  const p = normalizeText(phrase);
  if (!h || !p) return false;
  return new RegExp(`(?:^| )${p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?: |$)`).test(h);
}

/** Every ingredient line of a candidate, as plain strings. */
export function candidateIngredients(candidate) {
  const list = candidate.ingredients || candidate.recipeIngredient || [];
  return list.map((i) => {
    if (typeof i === "string") return i;
    return [i.originalText, i.display, i.note, i.food && i.food.name].filter(Boolean).join(" ");
  });
}

/* ------------------------------------------------------------------ */
/* scoping                                                              */
/* ------------------------------------------------------------------ */

/** Does this block's scope reach this candidate? Scope semantics only — no strength judgement. */
export function blockMatches(block, candidate) {
  const scope = String(block.scope || "recipe").toLowerCase();
  const target = block.target;
  if (!target) return false;

  switch (scope) {
    case "recipe":
      // Only that exact recipe. Never the dish, the source, or the cuisine.
      return canonicalUrl(candidate.url) === canonicalUrl(target);
    case "dish":
      // That dish across every source.
      return containsPhrase(candidate.dish || candidate.title, target);
    case "ingredient":
      // Recipes where it is a meaningful component. Adjacent ingredients
      // ("star anise" for a fennel block) are explicitly NOT inferred.
      return candidateIngredients(candidate).some((line) => containsPhrase(line, target));
    case "source": {
      const src = canonicalSource(candidate.source, candidate.url);
      const want = canonicalSource(target, target);
      return src === want || (!!src && !!want && src.endsWith(`.${want}`));
    }
    case "cuisine":
      return containsPhrase(candidate.cuisine, target);
    default:
      return false;
  }
}

/** Is this block binding on its own, or only advisory until repeated? */
export function blockStrength(block, confidenceCount = 1) {
  const scope = String(block.scope || "recipe").toLowerCase();
  const reason = String(block.reason || "other").toLowerCase();
  const licensed = LICENSED_SCOPES[reason] || LICENSED_SCOPES.other;
  if (licensed.includes(scope)) return "binding";
  return confidenceCount >= CONFIDENCE_THRESHOLD ? "binding" : "advisory";
}

/**
 * Split candidates into kept and dropped.
 *
 * A binding block removes the candidate. An advisory one (a block reaching
 * wider than its reason licenses, seen only once) leaves it in play with a
 * penalty so the planner deprioritizes it instead of pretending it never
 * happened.
 */
export function scopeCandidates(candidates, blocks) {
  const counts = new Map();
  for (const b of blocks) {
    const key = `${b.person || "*"}|${b.scope}|${normalizeText(b.target)}`;
    counts.set(key, (counts.get(key) || 0) + (Number(b.confidence) || 1));
  }

  const kept = [];
  const dropped = [];
  for (const candidate of candidates) {
    const binding = [];
    const advisory = [];
    for (const block of blocks) {
      if (!blockMatches(block, candidate)) continue;
      const key = `${block.person || "*"}|${block.scope}|${normalizeText(block.target)}`;
      const strength = blockStrength(block, counts.get(key) || 1);
      const record = {
        id: block.id,
        person: block.person,
        reason: block.reason,
        scope: block.scope,
        target: block.target,
        strength,
      };
      (strength === "binding" ? binding : advisory).push(record);
    }
    if (binding.length) {
      dropped.push({ ...candidate, blockedBy: binding });
    } else {
      kept.push(advisory.length ? { ...candidate, deprioritizedBy: advisory, penalty: advisory.length } : candidate);
    }
  }
  return { kept, dropped };
}

/* ------------------------------------------------------------------ */
/* the store                                                            */
/* ------------------------------------------------------------------ */

export function emptyStore(people = ["jayson", "amanda"]) {
  return {
    version: SCHEMA_VERSION,
    updatedAt: new Date().toISOString(),
    people,
    cooldownDays: 28,
    cooldownQuery: 'lastMade <= "$NOW-28d"',
    reasonVocabulary: [...REASONS],
    scopes: [...SCOPES],
    licensedScopes: LICENSED_SCOPES,
    confidenceThreshold: CONFIDENCE_THRESHOLD,
    recipes: {},
    blocks: [],
    sourcePriors: {},
    ingredientSignals: {},
    workflowSignals: {},
  };
}

export function loadStore(file = HISTORY_FILE) {
  if (!existsSync(file)) return emptyStore();
  const store = JSON.parse(readFileSync(file, "utf8"));
  // Keep the declared taxonomy authoritative even for a store written by an
  // older version of the skill.
  store.reasonVocabulary = [...REASONS];
  store.scopes = [...SCOPES];
  store.licensedScopes = LICENSED_SCOPES;
  store.confidenceThreshold = CONFIDENCE_THRESHOLD;
  store.recipes ||= {};
  store.blocks ||= [];
  store.sourcePriors ||= {};
  store.ingredientSignals ||= {};
  store.workflowSignals ||= {};
  return store;
}

export function saveStore(store, file = HISTORY_FILE) {
  store.updatedAt = new Date().toISOString();
  mkdirSync(dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  writeFileSync(tmp, `${JSON.stringify(store, null, 2)}\n`, { mode: 0o600 });
  renameSync(tmp, file);
  return file;
}

const emptyVotes = (people) => Object.fromEntries(people.map((p) => [p, { vote: null, reason: null, note: null, at: null }]));

/**
 * Record that a recipe was proposed for a week. Votes stay per person; an
 * existing entry keeps its votes and cook history so re-proposing a favorite
 * does not erase what the household already told us about it.
 */
export function recordProposal(store, entry) {
  const key = canonicalUrl(entry.url);
  const people = store.people || ["jayson", "amanda"];
  const prior = store.recipes[key] || {};
  const repeatOfSameWeek = !!prior.plannedFor && prior.plannedFor === entry.plannedFor;
  store.recipes[key] = {
    url: entry.url,
    title: entry.title,
    source: canonicalSource(entry.source, entry.url),
    dish: entry.dish || prior.dish || null,
    cuisine: entry.cuisine || prior.cuisine || null,
    category: entry.category || prior.category || "dinner",
    role: entry.role || prior.role || null,
    mealieSlug: entry.mealieSlug || prior.mealieSlug || null,
    mealieId: entry.mealieId || prior.mealieId || null,
    totalMinutes: entry.totalMinutes ?? prior.totalMinutes ?? null,
    timing: entry.timing || prior.timing || null,
    tomato: entry.tomato ?? prior.tomato ?? null,
    sesame: entry.sesame ?? prior.sesame ?? null,
    band4560: entry.band4560 ?? prior.band4560 ?? null,
    plannedFor: entry.plannedFor || prior.plannedFor || null,
    proposedAt: entry.proposedAt || new Date().toISOString().slice(0, 10),
    firstProposedAt: prior.firstProposedAt || entry.proposedAt || new Date().toISOString().slice(0, 10),
    // Re-running the planner for the same week is a correction, not a second
    // proposal, so it must not inflate the novelty counters.
    timesProposed: (prior.timesProposed || 0) + (repeatOfSameWeek ? 0 : 1),
    cookedAt: prior.cookedAt || null,
    timesCooked: prior.timesCooked || 0,
    votes: { ...emptyVotes(people), ...(prior.votes || {}) },
    notes: prior.notes || [],
  };
  if (!repeatOfSameWeek) touchSourcePrior(store, store.recipes[key].source, { proposed: 1 });
  return store.recipes[key];
}

/** One person's vote on one recipe. Never merged into a household score. */
export function recordVote(store, { url, person, vote, reason = null, note = null, at = new Date().toISOString() }) {
  const key = canonicalUrl(url);
  const entry = store.recipes[key];
  if (!entry) throw new Error(`no history entry for ${url} — record the proposal first`);
  if (!["up", "down", "neutral"].includes(vote)) throw new Error(`vote must be up/down/neutral, got ${vote}`);
  if (reason && !REASONS.includes(reason)) throw new Error(`unknown feedback reason ${reason}`);
  entry.votes[person] = { vote, reason, note, at };
  touchSourcePrior(store, entry.source, vote === "up" ? { up: 1 } : vote === "down" ? { down: 1 } : {});
  return entry.votes[person];
}

/** Add a scoped block. Repeats of the same (person, scope, target) raise its confidence. */
export function recordBlock(store, { person, reason, scope, target, recordedAt = new Date().toISOString().slice(0, 10), note = null }) {
  if (!REASONS.includes(reason)) throw new Error(`unknown feedback reason ${reason}`);
  if (!SCOPES.includes(scope)) throw new Error(`unknown scope ${scope}`);
  const existing = store.blocks.find(
    (b) => b.person === person && b.scope === scope && normalizeText(b.target) === normalizeText(target),
  );
  if (existing) {
    existing.confidence = (existing.confidence || 1) + 1;
    existing.recordedAt = recordedAt;
    if (reason) existing.reason = reason;
    return existing;
  }
  const block = {
    id: `b${store.blocks.length + 1}-${normalizeText(target).replace(/ /g, "-").slice(0, 32) || "x"}`,
    person,
    reason,
    scope,
    target,
    recordedAt,
    confidence: 1,
    note,
  };
  store.blocks.push(block);
  if (scope === "ingredient") {
    const k = normalizeText(target);
    store.ingredientSignals[k] = (store.ingredientSignals[k] || 0) + 1;
  }
  if (scope === "source") touchSourcePrior(store, canonicalSource(target, target), { down: 1 });
  return block;
}

/**
 * Source-level signals, kept separate from recipe-level ones so a single good
 * recipe can still override a mildly negative source tendency.
 */
export function touchSourcePrior(store, source, { up = 0, down = 0, proposed = 0 }) {
  if (!source) return null;
  const prior = store.sourcePriors[source] || { up: 0, down: 0, proposed: 0, prior: 0 };
  prior.up += up;
  prior.down += down;
  prior.proposed += proposed;
  const samples = prior.up + prior.down;
  // Bounded to [-1, 1] and damped by sample count, so one thumbs down on one
  // recipe never reads as "this source is bad".
  prior.samples = samples;
  prior.prior = samples ? Number((((prior.up - prior.down) / samples) * (samples / (samples + CONFIDENCE_THRESHOLD))).toFixed(3)) : 0;
  prior.confidence = samples >= CONFIDENCE_THRESHOLD ? "meaningful" : "weak";
  store.sourcePriors[source] = prior;
  return prior;
}

/** "Last made 5 weeks ago" / "New recipe", for the review page. */
export function lastMadeLabel(entry, now = new Date()) {
  if (!entry || !entry.cookedAt) return "New recipe";
  const days = Math.floor((now - new Date(entry.cookedAt)) / 86400000);
  if (days < 7) return `Last made ${days} day${days === 1 ? "" : "s"} ago`;
  const weeks = Math.floor(days / 7);
  return `Last made ${weeks} week${weeks === 1 ? "" : "s"} ago`;
}
