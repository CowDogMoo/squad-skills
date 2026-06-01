---
name: bootstrap-weekly-planner-doc
description: Copy a fully-styled Google Doc weekly planner template into the user's Drive and substitute this week's dates. Use when a user is first setting up the weekly-planner agent and needs an empty planner doc to point it at.
---

# Bootstrap weekly planner doc

You are creating a new Google Doc weekly planner for the user by copying a public template (`TEMPLATE_ID` in `scripts/setup.py`) into their Drive and filling in this week's dates. The template carries all the styling — colored category bands, emoji prefixes, column widths, header formatting — so the resulting doc is presentable on first run, not a bare API-built skeleton. The script in `scripts/setup.py` does the work; this body is the runbook.

# Why copy-a-template vs build-via-API?

Programmatic `documents.batchUpdate` can build the structural skeleton fine, but every styling detail (per-row colors, column widths, paragraph styles, cell merges) has to be re-issued as additional API calls — and personal taste in styling is a moving target. Cloning a Drive file via `files.copy` preserves the template's appearance 1:1 with one API call. The script's only job after the copy is filling in the dates.

# Inputs

The caller (or the user running the script) provides:

- A Google Cloud Console OAuth 2.0 Client ID of type "Desktop app", downloaded as `credentials.json`.
- The first week's start date (must be a Sunday, ISO `YYYY-MM-DD`).
- Optional: doc title (default `Weekly Planner`).

Scopes used: `documents` (substitute date placeholders) + `drive.file` (copy the public template into the user's Drive). `drive.file` is per-file — the script can only see/modify files it created, never the user's broader Drive.

# Step-by-step

## 1. One-time OAuth setup

If the user hasn't done it before:

1. Open https://console.cloud.google.com/apis/credentials in the user's Google account.
2. Create a new OAuth 2.0 Client ID. Application type: **Desktop app**.
3. Download the resulting JSON; save as `credentials.json` in the directory where you'll run `setup.py`.
4. On the **OAuth consent screen** tab, make sure the Google account that will own the planner doc is listed as a Test User (or publish the consent screen to "In production").

The script writes `token.json` after the first run; subsequent runs are non-interactive as long as the refresh token is valid.

## 2. Install Python dependencies

    python3 -m pip install --user google-api-python-client google-auth google-auth-oauthlib

## 3. Run the setup script

From the directory holding `credentials.json`:

    python3 "$SQUAD_SKILL_DIR/scripts/setup.py" --start-date 2026-06-07

On hosts that don't expose `$SQUAD_SKILL_DIR`, copy `scripts/setup.py` to a working directory first and call it directly.

The first run opens a browser to the OAuth consent screen. Approve it; the script writes `token.json` and proceeds.

Flags:

- `--start-date` (required) — Sunday `YYYY-MM-DD` that anchors the week.
- `--title "My Planner"` — sets the doc title (default `Weekly Planner`).

The script prints the new doc's URL and `file_id` to stdout. The `file_id` is what the `weekly-planner` agent needs in its config or vars.

## 4. Verify the result

Open the doc URL printed by the script. You should see:

- A fully-styled planner table with the week heading filled in (`WEEKLY FAMILY PLANNER  ·  Week of June 7, 2026` or similar), seven weekday columns with dates, and category rows for Commitments, Childcare, Iris Outing, Iris Solids, Dog Exercise, Dinner, Notes.
- A styled GROCERIES table with category rows (Produce, Protein, Dairy, Pantry, Frozen, Refrigerated/Other) all empty.
- A `📚 Previous Weeks` section heading underneath, ready for the user to archive future weeks.

If any placeholders show through (`{{WEEK_DATE}}`, `{{SUN_DATE}}`, etc.), the script's `replaceAllText` pass didn't complete — re-run or report.

The category rows include `Iris Outing`, `Iris Solids`, `Dog Exercise` because they were in the template's source planner. **Rename or delete rows that don't apply to your household** — the weekly-planner agent reads row labels dynamically.

## 5. Pass the file_id to the agent

Configure the weekly-planner agent with the new `file_id`:

- **Squad**: set `PlannerDocId` via `--var PlannerDocId=<id>` or in `agent.yaml` vars.
- **Claude Code / other hosts**: paste the `file_id` into the agent's kickoff prompt or wherever it reads doc IDs from.

## 6. Adding more weeks later

The template ships with one week. To add another week (say, after rolling the current week into the `📚 Previous Weeks` section):

1. Re-run `setup.py` against a fresh date — but that creates a *new* doc, which probably isn't what you want.
2. Or copy the planner+GROCERIES tables from the current week, paste them below `📅 Current Week`, and update the heading dates by hand.
3. Or write a small `roll-week.py` script that does step 2 programmatically (a future enhancement; not shipped here).

# Schema reference

The detailed table-row contract lives in `references/planner-schema.md`. Read it before customizing if the agent stops finding sections after your edits — the heading regex and row-index references in the agent are sensitive to specific shapes.

# Guardrails

- The `drive.file` scope means the script can only see/modify files it created (including the freshly-copied planner). It cannot read or delete other docs in the user's Drive.
- `token.json` grants ongoing access to docs the script has created. Treat it like a secret; don't commit it to git.
- If `files.copy` fails with a 403 about insufficient scopes, the OAuth client is missing `drive.file` — re-consent with the scope added. The error message will name it explicitly.
- If `replaceAllText` succeeds but the doc still shows `{{...}}` placeholders, the template's text was edited in a way that broke the placeholders (e.g. a placeholder was split across two text runs by inline styling). Re-sanitize the template or report.
