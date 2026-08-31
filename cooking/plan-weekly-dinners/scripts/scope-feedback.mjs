#!/usr/bin/env node
// Apply MEAL-HISTORY-SPEC feedback scoping to a candidate set.
//
//   node scripts/scope-feedback.mjs --blocks blocks.json --candidates cands.json
//   node scripts/scope-feedback.mjs --candidates cands.json          # blocks from the store
//   node scripts/scope-feedback.mjs --candidates - < cands.json      # stdin
//
// Prints one JSON object on stdout: { kept, dropped, blocksApplied, ... }.
// Everything else goes to stderr, so the output can be piped straight into the
// planner.
//
// The point of this script is restraint. A thumbs down on one Pad See Ew
// recipe removes that recipe and nothing else — not the dish, not the source,
// not Thai food. Only a block whose scope its reason actually licenses reaches
// wider, and a block that reaches wider than its reason licenses is advisory
// until the household repeats it.

import { readFileSync } from "node:fs";
import { HISTORY_FILE, loadStore, scopeCandidates } from "./history.mjs";

function parseArgs(argv) {
  const args = { blocks: null, candidates: null, store: HISTORY_FILE, pretty: false };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    const next = () => {
      const v = argv[i + 1];
      if (v === undefined) throw new Error(`${a} needs a value`);
      i += 1;
      return v;
    };
    if (a === "--blocks") args.blocks = next();
    else if (a === "--candidates") args.candidates = next();
    else if (a === "--store") args.store = next();
    else if (a === "--pretty") args.pretty = true;
    else if (a === "--help" || a === "-h") args.help = true;
    else throw new Error(`unknown argument ${a}`);
  }
  return args;
}

function readJson(path) {
  const text = path === "-" ? readFileSync(0, "utf8") : readFileSync(path, "utf8");
  return JSON.parse(text);
}

/** Accept either a bare array or an object with a candidates/blocks/items key. */
function unwrap(value, ...keys) {
  if (Array.isArray(value)) return value;
  for (const k of keys) {
    if (Array.isArray(value?.[k])) return value[k];
  }
  throw new Error(`expected an array or an object with one of: ${keys.join(", ")}`);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.candidates) {
    process.stderr.write(
      "usage: scope-feedback.mjs --candidates <file|-> [--blocks <file>] [--store <file>] [--pretty]\n",
    );
    process.exit(args.help ? 0 : 2);
  }

  const candidates = unwrap(readJson(args.candidates), "candidates", "items", "recipes");

  // An explicit --blocks file is the whole world: the caller is asking "what
  // survives THESE blocks". Mixing in the state store's own blocks would
  // silently answer a different question.
  let blocks;
  let blockSource;
  if (args.blocks) {
    blocks = unwrap(readJson(args.blocks), "blocks", "items");
    blockSource = args.blocks;
  } else {
    blocks = loadStore(args.store).blocks || [];
    blockSource = args.store;
  }

  const { kept, dropped } = scopeCandidates(candidates, blocks);
  const out = {
    blockSource,
    blocksApplied: blocks.length,
    candidates: candidates.length,
    kept,
    dropped,
    deprioritized: kept.filter((c) => c.deprioritizedBy).map((c) => c.url),
  };
  process.stdout.write(`${JSON.stringify(out, null, args.pretty ? 2 : 0)}\n`);
}

try {
  main();
} catch (err) {
  process.stderr.write(`scope-feedback: ${err.message}\n`);
  process.exit(1);
}
