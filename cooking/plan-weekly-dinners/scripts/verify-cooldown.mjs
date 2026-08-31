#!/usr/bin/env node
// Prove the 28-day reuse cooldown is actually live against this Mealie build.
//
//   node scripts/verify-cooldown.mjs
//
// Creates a throwaway recipe, marks it made today, and checks that
// `lastMade <= "$NOW-28d"` excludes it while `lastMade > "$NOW-28d"` returns it.
// Deletes the probe either way.
//
// This exists because the cooldown has exactly one failure mode that looks like
// success: Mealie v3 keeps `lastMade` per household, and a plain
// PATCH /api/recipes/<slug> {"lastMade": ...} updates what GET returns while
// leaving the household row untouched. Every read looks right, the query keeps
// treating the recipe as never made, and the household starts getting the same
// dinner every fortnight. Run this after a Mealie upgrade.

import { COOLDOWN_QUERY, RECENTLY_MADE_QUERY, deleteRecipe, getRecipe, householdRecipeRecord, listRecipes, markMade, must, planningToken } from "./mealie.mjs";

const token = planningToken();
const name = `zz cooldown selftest ${process.pid}`;
let slug = null;
const failures = [];

try {
  const created = must("/api/recipes", { token, method: "POST", body: { name } });
  slug = typeof created.json === "string" ? created.json : created.json && created.json.slug;
  if (!slug) throw new Error(`could not create the probe recipe: ${created.text.slice(0, 200)}`);

  const before = listRecipes(token, { queryFilter: COOLDOWN_QUERY }).map((r) => r.slug);
  if (!before.includes(slug)) {
    failures.push(`a never-made recipe is NOT returned by ${COOLDOWN_QUERY} — new recipes would never be proposed`);
  }

  markMade(token, slug, new Date());

  const record = householdRecipeRecord(token, slug);
  if (!record || !record.lastMade) {
    failures.push(`markMade did not write the household record for ${slug} (${JSON.stringify(record)})`);
  }

  const after = listRecipes(token, { queryFilter: COOLDOWN_QUERY }).map((r) => r.slug);
  if (after.includes(slug)) {
    failures.push(`a recipe made today is STILL returned by ${COOLDOWN_QUERY} — the cooldown does not exclude it`);
  }

  const inverse = listRecipes(token, { queryFilter: RECENTLY_MADE_QUERY }).map((r) => r.slug);
  if (!inverse.includes(slug)) {
    failures.push(`positive control failed: the just-made probe is not returned by ${RECENTLY_MADE_QUERY} either, so the exclusion above proves nothing`);
  }

  const full = getRecipe(token, slug);
  process.stdout.write(`probe ${slug}: recipe.lastMade=${full && full.lastMade} household.lastMade=${record && record.lastMade}\n`);
} finally {
  if (slug) deleteRecipe(token, slug);
}

if (failures.length) {
  for (const f of failures) process.stdout.write(`FAIL: ${f}\n`);
  process.exit(1);
}
process.stdout.write(`COOLDOWN-VERIFIED ${COOLDOWN_QUERY}\n`);
