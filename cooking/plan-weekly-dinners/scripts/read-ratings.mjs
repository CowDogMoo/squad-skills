#!/usr/bin/env node
// Read BOTH household members' Mealie ratings, separately.
//
//   node scripts/read-ratings.mjs            # human-readable table
//   node scripts/read-ratings.mjs --json     # planning context, machine-readable
//
// Mealie only lets a token read its own user's ratings, so this reads once per
// person with that person's own API token out of 1Password. There is no
// household ratings endpoint and the planner must not invent one: MEAL-HISTORY-
// SPEC makes per-person votes a hard requirement, and an average would erase
// exactly the disagreement the planner is supposed to see.

import { PEOPLE, listRecipes, planningToken, readOwnRatings, tokenFor, whoAmI } from "./mealie.mjs";

const args = new Set(process.argv.slice(2));
const asJson = args.has("--json");

function recipeIndex() {
  try {
    const rows = listRecipes(planningToken(), { perPage: 500 });
    return new Map(rows.map((r) => [r.id, { slug: r.slug, title: r.name }]));
  } catch {
    return new Map();
  }
}

function main() {
  const index = recipeIndex();
  const out = { generatedAt: new Date().toISOString(), source: "mealie", perPersonTokens: true };
  const errors = [];

  for (const person of PEOPLE) {
    try {
      const token = tokenFor(person.key);
      const self = whoAmI(token);
      if (self.username !== person.mealieUsername) {
        throw new Error(`token ${person.tokenField} authenticates as ${self.username}, not ${person.mealieUsername}`);
      }
      const ratings = readOwnRatings(token).map((r) => ({
        recipeId: r.recipeId,
        rating: r.rating,
        isFavorite: r.isFavorite,
        slug: index.get(r.recipeId)?.slug || null,
        title: index.get(r.recipeId)?.title || null,
      }));
      out[person.key] = { username: self.username, userId: self.id, household: self.household, ratings };
    } catch (err) {
      errors.push(`${person.key}: ${err.message}`);
      out[person.key] = { username: person.mealieUsername, userId: null, ratings: [], error: err.message };
    }
  }

  // A per-recipe view that keeps both votes side by side. Deliberately no mean,
  // no "household rating": disagreement is signal, not noise to be averaged out.
  const byRecipe = {};
  for (const person of PEOPLE) {
    for (const row of out[person.key].ratings) {
      const key = row.slug || row.recipeId;
      byRecipe[key] ||= { recipeId: row.recipeId, slug: row.slug, title: row.title, votes: {} };
      byRecipe[key].votes[person.key] = { rating: row.rating, isFavorite: row.isFavorite };
    }
  }
  for (const entry of Object.values(byRecipe)) {
    const seen = PEOPLE.map((p) => entry.votes[p.key]?.rating).filter((v) => v !== null && v !== undefined);
    entry.agreement = seen.length < PEOPLE.length ? "incomplete" : new Set(seen).size === 1 ? "agree" : "split";
  }
  out.byRecipe = byRecipe;

  if (asJson) {
    process.stdout.write(`${JSON.stringify(out)}\n`);
  } else {
    for (const person of PEOPLE) {
      const bucket = out[person.key];
      process.stdout.write(`${person.key} (${bucket.username})${bucket.error ? ` -- ERROR: ${bucket.error}` : ""}\n`);
      if (!bucket.ratings.length) process.stdout.write("  (no ratings yet)\n");
      for (const r of bucket.ratings) {
        process.stdout.write(`  ${String(r.rating).padStart(4)}  ${r.title || r.recipeId}${r.isFavorite ? "  *" : ""}\n`);
      }
    }
    const split = Object.values(byRecipe).filter((e) => e.agreement === "split");
    if (split.length) {
      process.stdout.write(`\nsplit votes (keep both, never average): ${split.map((e) => e.title || e.slug).join(", ")}\n`);
    }
  }
  if (errors.length) {
    process.stderr.write(`${errors.join("\n")}\n`);
    process.exit(1);
  }
}

main();
