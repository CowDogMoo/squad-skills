---
name: bootstrap-weekly-planner-doc
description: Create a new Google Doc weekly planner with the table structure the weekly-planner agent expects (rolling planner table + GROCERIES table, one section per week). Use when a user is first setting up the weekly-planner agent or wants to seed additional weeks ahead.
---

# Bootstrap weekly planner doc

You are creating an empty Google Doc whose structure matches what the `weekly-planner` agent reads from: a rolling planner with `WEEKLY FAMILY PLANNER · Week of <date>` headings, a 7-column day-of-week planner table, and a 2-column GROCERIES table per week. The script in `scripts/setup.py` does the heavy lifting via the Google Docs API; this body is the runbook for running it.

# Why a script, not a `.docx` template?

The weekly-planner agent already needs OAuth + Docs/Drive APIs to operate (it calls `documents.batchUpdate` to write the grocery list each week), so the marginal cost of one more API-driven setup step is near zero — and the script makes the schema authoritative. `.docx` upload-to-Drive loses table column widths and merged-cell behavior unpredictably; programmatic build is reproducible.

# Inputs

The caller (or the user running the script directly) provides:

- A Google Cloud Console OAuth 2.0 Client ID of type "Desktop app", downloaded as `credentials.json`.
- The first week's start date (must be a Sunday, ISO `YYYY-MM-DD`).
- Optional: doc title (default `Family Planner`), number of weeks to pre-seed (default `1`).

Scopes used: `documents` (create + modify the doc) and `drive.file` (the script only ever sees files it created — it does NOT grant read access to the user's whole Drive).

# Step-by-step

## 1. One-time OAuth setup

If the user hasn't done it before:

1. Open https://console.cloud.google.com/apis/credentials in the user's Google account.
2. Create a new OAuth 2.0 Client ID. Application type: **Desktop app**.
3. Download the resulting JSON; save as `credentials.json` in the same directory where you'll run `setup.py`.
4. On the **OAuth consent screen** tab, ensure the Google account that will own the planner doc is listed as a Test User (or publish the consent screen to "In production" if you want any account).

This is a one-time setup. The script writes `token.json` after the first run; subsequent runs are non-interactive as long as the token is still valid (refresh tokens last ~6 months for unverified test apps).

## 2. Install Python dependencies

    python3 -m pip install --user google-api-python-client google-auth google-auth-oauthlib

(Or use a venv — `python3 -m venv .venv && . .venv/bin/activate && pip install ...`.)

## 3. Run the setup script

From the directory holding `credentials.json`:

    python3 "$SQUAD_SKILL_DIR/scripts/setup.py" --start-date 2026-06-07

On hosts that don't expose `$SQUAD_SKILL_DIR`, copy `scripts/setup.py` to a working directory first and call it directly:

    python3 setup.py --start-date 2026-06-07

The first run opens a browser to the OAuth consent screen. Approve it; the script writes `token.json` and proceeds.

Other flags:

- `--title "My Planner"` — sets the doc title (default `Family Planner`).
- `--weeks 4` — pre-seeds N weeks of empty sections (default 1).

The script prints the new doc's URL and `file_id` to stdout. The `file_id` is what the `weekly-planner` agent needs in its config or vars.

## 4. Verify the structure

Open the doc URL printed by the script. You should see:

- A heading `WEEKLY FAMILY PLANNER · Week of <Month> <Day>, <Year>`.
- A 7-column table with weekday headers in row 0 (Sunday through Saturday with the actual dates) and Commitments / Childcare / Dinner / Notes labels in column 0.
- A `GROCERIES · Week of <Month> <Day>` heading inside row 0 of a second table.
- A 2-column GROCERIES table with `Covers:` in row 1 and Produce / Protein / Dairy / Pantry / Frozen / Refrigerated rows below.

If anything looks off, see `references/planner-schema.md` for the exact contract. Differences from the spec will confuse the weekly-planner agent's date detection or its `replace_table_cells` calls.

## 5. Pass the file_id to the agent

Configure the weekly-planner agent with the new `file_id`. Depending on host:

- **Squad agent vars**: set `PLANNER_DOC_ID` (or whatever var name the agent expects) in `agent.yaml` or via `--var PLANNER_DOC_ID=<id>` at run time.
- **Claude Code / other hosts**: paste the `file_id` into the agent's kickoff prompt or wherever the agent reads doc IDs from.

# When to re-run

Run the script again to:

- Pre-seed additional empty weeks for the future. Use the same doc by editing the script to call `append_week` against an existing `doc_id` instead of creating a new doc — or just re-run with a fresh `--title` and copy/paste the table into your existing doc.
- Bootstrap a fresh doc for a different family member or co-parenting calendar.

# Schema reference

The detailed table-row contract lives in `references/planner-schema.md`. Read that before changing `PLANNER_ROWS` or `GROCERIES_CATEGORIES` in the script — the row indices are load-bearing and the weekly-planner agent's `replace_table_cells` calls depend on them.

# Guardrails

- The script's `drive.file` scope means it can only see/modify files it creates. It cannot read or delete other docs in the user's Drive — this is intentional and should not be widened.
- The script uses OAuth installed-app flow. The `token.json` it writes contains a refresh token; treat it like a secret (it grants the script ongoing access to docs it has created). Don't commit it to git.
- If `documents.create` fails, fix the auth before retrying. If the structural `batchUpdate` succeeds but the cell-content `batchUpdate` fails, the doc is left in a partial state — easier to delete the partial doc and re-run than to fix in place.
