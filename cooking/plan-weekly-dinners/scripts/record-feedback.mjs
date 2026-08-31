#!/usr/bin/env node
// Record what actually happened at dinner: who liked it, why not, and that the
// household cooked it (which is what starts the 28-day cooldown).
//
//   node scripts/record-feedback.mjs --url <recipe url> --cooked 2026-09-02
//   node scripts/record-feedback.mjs --url <recipe url> --person amanda --vote down \
//        --reason i-do-not-like-a-specific-ingredient --scope ingredient --target fennel
//
// One vote belongs to one person. There is no household vote, and this script
// will not let you record one.
//
// A --scope wider than the --reason licenses is stored as advisory: the
// candidate keeps showing up with a penalty until the household says it twice.
// That is deliberate. One bad tofu night is not a tofu ban.

import { REASONS, SCOPES, canonicalUrl, loadStore, recordBlock, recordVote, saveStore } from "./history.mjs";
import { HISTORY_FILE } from "./history.mjs";
import { PEOPLE, markMade, planningToken } from "./mealie.mjs";

function parseArgs(argv) {
  const args = { store: HISTORY_FILE };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    const next = () => {
      const v = argv[i + 1];
      if (v === undefined) throw new Error(`${a} needs a value`);
      i += 1;
      return v;
    };
    if (a.startsWith("--")) args[a.slice(2)] = ["--help", "-h"].includes(a) ? true : next();
    else throw new Error(`unknown argument ${a}`);
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.url) {
    process.stdout.write(
      "usage: record-feedback.mjs --url <url> [--person jayson|amanda --vote up|down|neutral]\n" +
        "                          [--reason <reason>] [--scope recipe|dish|ingredient|source|cuisine --target <t>]\n" +
        `                          [--note "..."] [--cooked YYYY-MM-DD] [--store <file>]\n\n` +
        `reasons: ${REASONS.join(", ")}\nscopes:  ${SCOPES.join(", ")}\n`,
    );
    process.exit(args.help ? 0 : 2);
  }

  const store = loadStore(args.store);
  const key = canonicalUrl(args.url);
  const entry = store.recipes[key];
  if (!entry) throw new Error(`${args.url} is not in the history store — propose it first`);

  if (args.vote) {
    if (!args.person) throw new Error("--vote needs --person: a vote belongs to a person, not the household");
    if (!PEOPLE.some((p) => p.key === args.person)) throw new Error(`unknown person ${args.person}`);
    recordVote(store, { url: args.url, person: args.person, vote: args.vote, reason: args.reason || null, note: args.note || null });
    process.stdout.write(`recorded ${args.person}: ${args.vote}${args.reason ? ` (${args.reason})` : ""}\n`);
  }

  if (args.scope || args.target) {
    if (!args.scope || !args.target) throw new Error("--scope and --target go together");
    if (!args.person) throw new Error("--scope needs --person: a block belongs to whoever asked for it");
    const block = recordBlock(store, {
      person: args.person,
      reason: args.reason || "other",
      scope: args.scope,
      target: args.target,
      note: args.note || null,
    });
    process.stdout.write(`block ${block.id}: ${block.person} ${block.reason} scope=${block.scope} target=${block.target} confidence=${block.confidence}\n`);
  }

  if (args.cooked) {
    entry.cookedAt = args.cooked;
    entry.timesCooked = (entry.timesCooked || 0) + 1;
    if (entry.mealieSlug) {
      // Through /last-made, so the cooldown query actually sees it.
      markMade(planningToken(), entry.mealieSlug, `${args.cooked}T18:30:00.000Z`);
      process.stdout.write(`marked ${entry.mealieSlug} made on ${args.cooked}; it is now on cooldown for 28 days\n`);
    }
  }

  saveStore(store, args.store);
  process.stdout.write(`updated ${args.store}\n`);
}

try {
  main();
} catch (err) {
  process.stderr.write(`record-feedback: ${err.message}\n`);
  process.exit(1);
}
