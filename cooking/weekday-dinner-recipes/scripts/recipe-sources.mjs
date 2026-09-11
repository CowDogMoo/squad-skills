#!/usr/bin/env node
// Read the household's recipe source list from a Mealie instance.
//
// Usage:
//   node recipe-sources.mjs                 # every entry: status<TAB>domain<TAB>note
//   node recipe-sources.mjs --lookup <url>  # the entry that covers <url>, or "unlisted"
//   node recipe-sources.mjs --json ...      # the API's own JSON instead of lines
//
// Configuration comes from the environment: MEALIE_API_URL (or MEALIE_URL) and a
// token in MEALIE_TOKEN, or failing that the first MEALIE_TOKEN_* variable set, for
// hosts that carry one token per household member. The list is household-scoped, so
// any member's token answers the same.
//
// Exit status: 0 on an answer, 2 when Mealie is not configured (fall back to
// references/sources.md), 1 when the request failed (say so, then fall back).
// Only node's built-in fetch is used, so this runs anywhere node 18+ does.

const RANK = { "known-good": 0, caution: 1, blocked: 2 };

function config() {
  const base = (process.env.MEALIE_API_URL || process.env.MEALIE_URL || "").replace(/\/+$/, "");
  let token = process.env.MEALIE_TOKEN || "";
  if (!token) {
    const named = Object.keys(process.env)
      .filter((k) => k.startsWith("MEALIE_TOKEN_") && process.env[k])
      .sort();
    token = named.length ? process.env[named[0]] : "";
  }
  return { base, token };
}

async function get(base, token, path) {
  const res = await fetch(`${base}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) {
    throw new Error(`GET ${path} answered HTTP ${res.status}`);
  }
  return res.json();
}

function line(entry) {
  return [entry.status, entry.domain, entry.note || ""].join("\t");
}

async function main(argv) {
  const json = argv.includes("--json");
  const lookupAt = argv.indexOf("--lookup");
  const lookupUrl = lookupAt >= 0 ? argv[lookupAt + 1] : null;
  if (lookupAt >= 0 && !lookupUrl) {
    console.error("--lookup needs a URL or domain");
    return 2;
  }

  const { base, token } = config();
  if (!base || !token) {
    console.error("Mealie is not configured: set MEALIE_API_URL (or MEALIE_URL) and MEALIE_TOKEN (or a MEALIE_TOKEN_* variable)");
    return 2;
  }

  try {
    if (lookupUrl) {
      const found = await get(base, token, `/api/households/recipe-sources/lookup?url=${encodeURIComponent(lookupUrl)}`);
      if (json) {
        console.log(JSON.stringify(found));
      } else if (found.source) {
        console.log(line(found.source));
      } else {
        console.log(["unlisted", found.domain, ""].join("\t"));
      }
      return 0;
    }

    const page = await get(base, token, "/api/households/recipe-sources?perPage=-1");
    const items = [...(page.items || [])].sort(
      (a, b) => (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9) || a.domain.localeCompare(b.domain),
    );
    if (json) {
      console.log(JSON.stringify(items));
    } else {
      for (const entry of items) console.log(line(entry));
    }
    return 0;
  } catch (err) {
    console.error(`could not read the recipe source list: ${err.message}`);
    return 1;
  }
}

process.exitCode = await main(process.argv.slice(2));
