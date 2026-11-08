# Unjiggle 0.3.3 operations and engine behavior

Read this when writing an ops file by hand, or when a `check-operations` preview doesn't
match what you meant. Everything here was observed on iOS 26 with Unjiggle 0.3.3; the engine
lives in `unjiggle/layout_engine.py` and `unjiggle/analyzer.py` inside the venv if you need
to confirm a detail.

## Ops file

```json
{"snapshot_id": "<from state/scan.json>", "operations": [{"action": "...", "...": "..."}]}
```

Operations run in order, each on the result of the one before.

| action | fields | effect |
| --- | --- | --- |
| `create_folder` | `folder_name`, `bundle_ids`, optional `target_page` | New folder from Home Screen apps, placed on `target_page` if given |
| `move_to_folder` | `folder_name` (existing), `bundle_ids` | Append apps to an existing folder (fills its last page to 9, then new pages) |
| `rename_folder` | `old_name`, `folder_name` | Rename the first folder with that name |
| `move_to_page` | `bundle_ids`, `target_page` | Append apps to a page; dropped if the page is full or doesn't exist |
| `move_to_app_library` | `bundle_ids` | Take icons off the Home Screen. Apps stay installed |
| `rebuild_pages` | `bundle_ids` (ordered) | Re-flow every page (see below) |
| `compact_to_single_page` | `bundle_ids` | Pull the listed apps onto page 1, only if they all fit |

- `target_page` is 0-based over Home Screen pages. The dock is not a page.
- A page holds 24 slots (6 rows × 4). A small widget takes 4, medium 8, large 16. A folder
  takes 1. A folder page holds 9 apps. At most 15 pages.
- Apps named in `move_to_page`, `move_to_folder` and `create_folder` must already be on the
  Home Screen. An App-Library-only app has to be dragged out on the phone first.
- No op puts an app in the dock. Dock entries stay unless an op names them.
- An op that can't take effect is dropped without an error. Always confirm every intended
  move in `proposed_layout`, not just that the check succeeded.

## Fixed icons

Before running any op, the engine removes every fixed ID from it (`_raw_fixed_ids`):

- **Pinned:** an entry with no `bundleIdentifier`, only a `displayIdentifier`. On iOS 26
  every offloaded app (cloud icon) is stored like this, as are web clips and App Clips.
  The App Library can't hold them, so the engine never moves or removes them.
- **Duplicate:** an app with more than one icon (iOS 26 can show Settings or Shortcuts twice).

Consequences:

- A folder holding a fixed icon survives every operation, `rebuild_pages` included. You
  can't dissolve or recreate it, so rename it and fill it instead.
- Fixed icons keep their place inside a folder. `move_to_folder` appends after them, so
  installed apps land behind cloud icons. `scripts/installed_first.py` is the fix.
- `scripts/fixed_ids.py` prints the fixed IDs, split into `pinned` and `duplicate`. Unjiggle's
  `json inventory` lists offloaded apps under `placeholder_home_screen_ids`.

## rebuild_pages

The biggest hammer, and the one that surprises people:

1. Every non-fixed app not in `bundle_ids` is taken off the Home Screen first.
2. Page 1 keeps its widgets and fixed items (including folders that hold fixed icons) in
   place. The listed apps fill the page-1 slots that the removed items left, in order.
3. Fixed items and widgets from later pages are packed from page 2 on.
4. A later `create_folder` or `move_to_folder` in the same ops file can bring back apps that
   step 1 removed: the engine keeps each app's original entry for that.

So a full reorganization is `rebuild_pages(daily apps)`, then renames, then creates, then
moves that place every other movable app. If an app isn't placed anywhere, it ends up in the
App Library. `scripts/build_plan.py` refuses to write that plan.

## check-operations output

`json check-operations < plans/x.ops.json > state/x.check.json` is read-only and bound to
the snapshot. Read `proposed_layout` (same shape as a scan). The file carries every binding
field, so `json apply-checked < state/x.check.json` applies exactly that check. It refuses if
the phone changed since the scan.

## apply-checked

It takes a verified backup in `~/.unjiggle/backups/layout-<timestamp>.json`, rereads the phone,
writes, and compares the raw read-back to the checked destination. A mismatch exits 1 with
`Write verification failed` even when the planned layout landed: iOS can change things
during the write. See the iOS 26 notes in SKILL.md.

`json pending-checked` lists recovery candidates from interrupted writes. `json restore
<backup>` and `json restore-checked` write a backup back. Both are phone writes that need
approval.

## Not used here

`json apply` (unchecked), `suggest`, `go`, `analyze`, `mirror`, `obituary`, `report`,
`safety-test --write-roundtrip`, and the experimental `*-library-*` / `*-mixed-*` commands.
Unjiggle's AI commands send the layout to a model provider; the agent does the planning instead.
`json scan` sends bundle IDs to Apple's iTunes lookup API for names and categories.

## Can't do at all

Wallpaper, icon appearance (dark or tinted), creating widgets, blank slots or free placement,
Today View, reordering apps inside a folder (except via `installed_first.py`, and only
installed-before-offloaded), uninstalling apps.
