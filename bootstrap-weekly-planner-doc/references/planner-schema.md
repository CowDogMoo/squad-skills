# Weekly planner doc schema

This document describes the structure of the **template doc** (`TEMPLATE_ID` in `../scripts/setup.py`) that the bootstrap skill copies into a new user's Drive. The weekly-planner agent reads from copies of that template — so this spec defines the contract for both ends.

## Top-level shape

The doc is a **rolling planner** — multiple weeks stacked top-to-bottom inside a single doc. Each week's content lives between two structural markers:

- `📅 Current Week` paragraph — marks where this week's section starts.
- `📚 Previous Weeks` paragraph — marks where older weeks are archived.

The template ships with **one** week (the upcoming one) under `📅 Current Week`, plus an empty `📚 Previous Weeks` section. The user adds more weeks as they roll forward (either by hand-copying the current-week's tables and bumping the dates, or with their own roll-week tooling).

A week's section is:

1. The planner table (9 rows × 8 cols)
2. A blank-line separator paragraph
3. The GROCERIES table (8 rows × 2 cols)

## Planner table

Dimensions: **9 rows × 8 columns**. Column 0 is the label column; columns 1-7 are the seven weekdays (Sunday through Saturday).

| Row | Column 0 | Columns 1-7 |
|---|---|---|
| 0 | `WEEKLY FAMILY PLANNER  ·  Week of <Month> <Day>, <Year>` (spans the full width via cell merge / styling) | — |
| 1 | empty / decorative | weekday + date column headers, e.g. `SUNDAY June 7`, `MONDAY June 8`, … |
| 2 | `⚑ Commitments` | scheduled commitments per weekday |
| 3 | `👶 Childcare` | childcare details |
| 4 | `🌿 Iris Outing` | outing notes |
| 5 | `🥄 Iris Solids` | feeding notes |
| 6 | `🐾 Dog Exercise` | dog activity |
| 7 | `🍽️ Dinner` | dish name + recipe URL |
| 8 | `📌 Notes` | freeform |

Notes:

- **The week heading lives INSIDE row 0** of the table, not as a standalone paragraph above the table. The agent locates each week's section by matching `WEEKLY FAMILY PLANNER  ·  Week of <date>` inside table cells, not in paragraph text.
- Separator in the heading is `·` (U+00B7 middle dot) with **two spaces** on each side: `PLANNER  ·  Week`. Other headings (GROCERIES) use a single space — both are real, agent matches each in the right place.
- **Column 0 is Sunday.** The setup script enforces this by rejecting `--start-date` values that aren't Sunday.
- Row 1 column headers are `<WEEKDAY> <Month> <Day>` — full uppercase weekday + month + day. Year comes from the row-0 heading.
- The Iris-/Dog-specific rows are starter content carried over from the template's source. Rename or delete rows that don't apply to your household; the agent reads row labels dynamically, so it'll match whatever you put in column 0.

## GROCERIES table

Dimensions: **8 rows × 2 columns**.

| Row | Column 0 | Column 1 |
|---|---|---|
| 0 | `GROCERIES · Week of <Month> <Day>` (spans full width) | — |
| 1 | `Covers: <dish names>` | — |
| 2 | `🥬 Produce` | item list, one per line |
| 3 | `🥩 Protein` | item list |
| 4 | `🧈 Dairy` | item list |
| 5 | `🧂 Pantry` | item list |
| 6 | `❄️ Frozen` | item list |
| 7 | `🥡 Refrigerated / Other` | item list |

Notes:

- GROCERIES separator is single-space (`GROCERIES · Week`), unlike the planner heading's two-space form. Match each exactly.
- **No year** in this heading — the agent matches against the most-recent week section, so the year is unambiguous from context.
- Row index → category mapping is positional. Reorder cautiously; the weekly-planner agent's `replace_table_cells` calls reference specific row indices.
- You can rename the labels (`Pantry` → `Dry Goods`, etc.) without breaking anything — the agent goes by row index, not by label text.

## Placeholders in the template

The template doc carries these placeholders. The setup script substitutes them via `replaceAllText`:

| Placeholder | Substituted with | Example |
|---|---|---|
| `{{WEEK_DATE}}` | `<Month> <Day>, <Year>` | `June 7, 2026` |
| `{{GROCERIES_DATE}}` | `<Month> <Day>` | `June 7` |
| `{{SUN_DATE}}` … `{{SAT_DATE}}` | `<Month> <Day>` for each day Sunday-Saturday | `June 7`, `June 8`, … `June 13` |

After substitution, the doc has no placeholders left and is ready for the weekly-planner agent.

## Customization

Things you can change without touching the agent:

- Doc title (`--title` flag on setup.py)
- Row labels in column 0 of the planner table (rename or remove rows)
- Category labels in column 0 of the GROCERIES table
- Styling (colors, fonts, column widths) — all preserved across copies

Things that DO affect the agent:

- Removing rows the agent references by name (e.g., `Dinner`, `Commitments`)
- Changing the `·` separator or the heading prefix (`WEEKLY FAMILY PLANNER`, `GROCERIES`)
- Switching from Sunday-start to Monday-start weeks (would require re-anchoring `column 1 = Sunday`)
