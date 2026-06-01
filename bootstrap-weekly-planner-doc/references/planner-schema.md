# Weekly planner doc schema

The weekly-planner agent expects a Google Doc with this structure. The setup script in `../scripts/setup.py` creates a doc matching this contract; this document is the human-readable spec the script implements.

## Top-level shape

The doc is a **rolling planner** — multiple weeks stacked top-to-bottom. Each week is one self-contained section. Adding next week's section doesn't disturb prior weeks; the agent picks the section whose date is the highest (most recent), so week order in the doc doesn't matter.

A single week's section is:

1. The week heading paragraph
2. A 7-column planner table (one column per weekday)
3. The GROCERIES heading paragraph
4. A 2-column GROCERIES table (category + items)
5. A blank line separator

## Week heading

Exact form:

    WEEKLY FAMILY PLANNER · Week of <Month> <Day>, <Year>

- Separator is `·` (U+00B7 middle dot), **not** a hyphen, em-dash, or bullet.
- Month is the full English month name (`June`, not `Jun`).
- Day has no leading zero (`7`, not `07`).
- Year is the four-digit year.
- The heading must occupy its own paragraph (no inline text on the same line).

Example: `WEEKLY FAMILY PLANNER · Week of June 7, 2026`

The agent locates each week's section by matching this exact heading pattern, parsing the date, and picking the highest date. If you rename "FAMILY" to something else, update the agent's regex to match.

## Planner table

Dimensions: `(1 + N) rows × 7 columns`, where `N` is the count of category rows (Commitments, Dinner, etc.). The default `N = 4` (Commitments, Childcare, Dinner with recipe links, Notes).

| Row | Column 0 | Columns 1-6 |
|---|---|---|
| 0 | `SUNDAY <Month> <Day>` | weekday headers for Mon-Sat with dates |
| 1 | `Commitments` | cell content for each weekday |
| 2 | `Childcare` | cell content for each weekday |
| 3 | `Dinner (with recipe links)` | cell content for each weekday |
| 4 | `Notes` | cell content for each weekday |

Notes:

- **Column 0 is Sunday.** Many planners start the week on Monday; this one is Sun-Sat. The setup script enforces this by rejecting `--start-date` values that aren't a Sunday.
- Header dates in row 0 are weekday name (uppercased) + month + day, e.g. `MONDAY June 8`.
- Year is in the week heading, not in the column headers. The agent infers the year for column headers from the heading.
- Row labels live in column 0 only; columns 1-6 of row N hold the seven days' content for that category.
- **Dinner cells should contain a dish name plus a recipe URL** when applicable. The agent looks for URLs in the cell (either as a hyperlink attached to the dish name or as plain text) to drive the recipe-fetch step.

## GROCERIES heading

Exact form:

    GROCERIES · Week of <Month> <Day>

- Same `·` separator as the week heading.
- **No year here.** The agent matches this heading against the most-recent week section, so the year is unambiguous from context.
- The heading lives in row 0, column 0 of the GROCERIES *table* (not as a standalone paragraph above the table). This is how the agent's `mcp__gdrive__replace_table_cells` tool locates the right table by heading text.

## GROCERIES table

Dimensions: `(2 + M) rows × 2 columns`, where `M` is the count of categories.

| Row | Column 0 | Column 1 |
|---|---|---|
| 0 | `GROCERIES · Week of <Month> <Day>` | (empty — heading visually spans both cols) |
| 1 | `Covers: <dish names>` | (empty — Covers visually spans both cols) |
| 2 | `Produce` | item list, one per line |
| 3 | `Protein` | item list |
| 4 | `Dairy` | item list |
| 5 | `Pantry` | item list |
| 6 | `Frozen` | item list |
| 7 | `Refrigerated / Other` | item list |

Notes:

- Row index → category mapping is positional. The agent writes to specific row indices, so if you reorder categories you must update both ends.
- Item-list cells are populated by the agent (each cell is one ingredient per line, no leading bullet). The setup script leaves these empty.
- You can prepend emoji to category labels (`🥬 Produce`) — the agent matches by row index, not by label text, so cosmetic decoration is safe. Renaming `Produce` to `Veggies` is also safe as long as the row index stays put.

## Customization knobs

Things you can change without touching the agent:

- Doc title
- Planner row labels (the agent reads them as configured; if your agent is parameterized via vars, sync the new labels there)
- Adding more weeks to pre-seed
- Adding emoji or formatting to category labels

Things that require the agent to change too:

- Adding/removing planner rows or GROCERIES categories (row-index references in the agent's `replace_table_cells` calls)
- Renaming `FAMILY` in the heading (regex match)
- Switching from Sunday-start to Monday-start weeks (date arithmetic)
- Changing the `·` separator
