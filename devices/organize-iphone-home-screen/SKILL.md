---
name: organize-iphone-home-screen
description: Reorganize an iPhone Home Screen from a Mac over USB with the open-source Unjiggle CLI - scan the layout, plan folders and pages with the user, preview every change with a read-only check, apply only after explicit approval, then verify by rescanning - plus a bundled script that puts installed apps ahead of offloaded (cloud) icons inside folders, which Unjiggle can't do. Use for "organize my iPhone home screen", "clean up my apps", "sort my apps into folders", "put installed apps first in my folders", "why can't you move this app", "undo the home screen change", or any request to read or rearrange iPhone icons, folders, or pages from the computer. Not for Android, iPad-specific layouts, wallpaper, widgets, or uninstalling apps.
compatibility: macOS with Python 3.10+, a USB-connected and trusted iPhone, and unjiggle==0.3.3 (installed by scripts/setup_workspace.sh). Tested on iOS 26.
license: MIT
---

# Organize an iPhone Home Screen with Unjiggle

## Objective

Rearrange the user's Home Screen the way they want, in a few reviewable writes, without
losing an icon. Unjiggle reads and writes SpringBoard's icon state over USB through
pymobiledevice3. You are the planner; Unjiggle's own AI commands are never used.

## Guardrails

These exist because each one has been needed on a real phone:

- **No write without approval of that exact preview.** Show the before → after per page and
  per folder, ask "Apply this?", and wait for a clear yes. Approval covers one apply. A
  changed plan, a re-run preview, or a restore needs a new yes.
- **Every Unjiggle write is `json check-operations` → `json apply-checked`.** Never `json apply`,
  `suggest`, `go`, or `safety-test --write-roundtrip`. The only other write path is
  `scripts/installed_first.py apply`, after its preview is approved.
- **When a write looks off, stop.** Don't retry and don't restore on your own. Rescan
  (read-only), diff against the preview, and report what changed plus the backup path. A
  failed read-back has so far meant "iOS changed something during the write", not damage.
  Diffing tells you which.
- **Nothing gets uninstalled.** `move_to_app_library` only removes the icon; say so plainly
  when proposing it.
- **Phone changes between steps invalidate the plan.** The user often keeps tidying by hand.
  Every check is bound to a snapshot, so rescan and rebuild rather than forcing a stale plan.

## Inputs

- A workspace folder (default `~/src/iphone-homescreen`) with `.venv/`, `plans/` and `state/`.
  If it doesn't exist, run `bash <skill>/scripts/setup_workspace.sh [dir]` first. It never
  touches the phone.
- What the user wants: by function, most-used first, fewest pages, what goes to the App
  Library. Ask if they haven't said.

`<skill>` below is this skill's folder. Run everything from the workspace root, with the
venv's python for the scripts that import Unjiggle.

## Step-by-step

1. **Connect.** `.venv/bin/unjiggle json status`. If `"connected": false`, ask the user to
   plug in the iPhone, unlock it and tap Trust.
2. **Scan (read-only).**

   ```bash
   .venv/bin/unjiggle json scan > state/scan.json
   .venv/bin/unjiggle json inventory > state/inventory.json
   .venv/bin/python <skill>/scripts/fixed_ids.py > state/fixed.json
   python3 <skill>/scripts/show_layout.py state/scan.json --fixed state/fixed.json
   ```

   Check `parse_integrity.structure_preserved` is true. Note how many icons are fixed
   (☁ offloaded, ⧉ duplicate). No op can move them, which shapes the whole plan.
3. **Plan with the user.** Draft the target page by page: dock, loose apps on page 1,
   each folder and its apps, what goes to the App Library. Work around fixed icons. A folder
   holding one can't be dissolved, so rename it to the function you want and fill it
   rather than recreating it. Say which leftovers can't be fixed (offloaded apps stuck in
   the wrong folder) and how the user can free them on the phone (see iOS 26 notes).
4. **Write the ops.** For anything bigger than a couple of moves, write
   `plans/<name>.target.json` and generate the ops so the coverage check runs:

   ```bash
   python3 <skill>/scripts/build_plan.py build plans/<name>.target.json state/scan.json state/fixed.json plans/<name>.ops.json
   ```

   The target format is in the script's docstring. It refuses to write ops that name fixed
   or missing apps, place an app twice, or would drop unplaced apps to the App Library via
   `rebuild_pages`. Small plans can be written by hand. Op semantics, limits and
   `rebuild_pages` behavior are in [references/operations.md](references/operations.md).
5. **Check (read-only) until it matches.**

   ```bash
   .venv/bin/unjiggle json check-operations < plans/<name>.ops.json > state/<name>.check.json
   python3 <skill>/scripts/build_plan.py verify plans/<name>.target.json state/scan.json state/<name>.check.json
   python3 <skill>/scripts/show_layout.py state/<name>.check.json --fixed state/fixed.json --names state/scan.json
   ```

   Ops that can't take effect are dropped silently, so confirm every move in the preview.
   Fix and recheck. Big reorganizations go in a few checked applies (folders first, then page
   order), rescanning between them because every apply changes `snapshot_id`.
6. **Show the diff and ask.** Before → after per page and per folder, fixed icons called out,
   anything going to the App Library listed. Wait for a clear yes.
7. **Apply.** `.venv/bin/unjiggle json apply-checked < state/<name>.check.json > state/<name>.apply.json`.
   It refuses if the phone changed, takes a verified backup, writes and reads back.
8. **Verify.** Rescan to `state/scan.json`, compare with the preview, and report the backup
   path from the apply output. Mention any apps iOS added. If it doesn't match, follow
   the "when a write looks off" guardrail.

## Installed apps first inside folders

Unjiggle can't reorder a folder, and `move_to_folder` appends behind the offloaded icons, so
installed apps end up on a folder's second or third page. `scripts/installed_first.py`
writes the icon state directly. In each folder it moves the installed apps ahead of the
pinned (offloaded) ones, keeping both groups' current order, and refills folder pages 9 at
a time. Nothing else changes.

1. `.venv/bin/python <skill>/scripts/installed_first.py preview`. It's read-only, prints
   each changed folder with ☁ marks, verifies that only in-folder order changes, and saves
   the before and proposed states in `state/`.
2. Show the per-folder result. Say that this write skips Unjiggle's own pre-write checks
   (`check-operations` / `apply-checked`), that the script checks it instead, and that a
   backup comes first. Ask for approval.
3. `.venv/bin/python <skill>/scripts/installed_first.py apply`. It refuses if the phone changed
   since the preview, takes Unjiggle's verified backup, rereads, writes, and reads back. On a
   mismatch it prints what differs and exits non-zero. Then stop and report.
4. Rescan and confirm no installed app sits behind a cloud icon.

`--from-file <raw-state.json>` previews against a saved state (an Unjiggle backup works)
with no phone attached.

## iOS 26 notes

- **Offloaded apps are fixed.** "Offload Unused Apps" can leave dozens of cloud icons that no
  op can move. The user can free one on the phone: tap it to reinstall (then it's an
  ordinary app), or long-press → Remove App → Remove from Home Screen. Multi-drag (start
  dragging one icon, tap others to stack them) moves a batch by hand.
- **iOS can add App Library apps during a big write.** After a `rebuild_pages` apply,
  SpringBoard has put App-Library-only apps (Safari, Music, TV and the like) back on the Home
  Screen and shifted a widget, failing the read-back even though the plan landed. Rescan,
  diff, report, and propose folding them into folders (a new checked plan) rather than
  sending them back. Small `move_to_folder` writes have read back cleanly.
- **Folder names must be unique** for the plan checks and read-back comparisons to mean
  anything.

## Undo

Backups are `~/.unjiggle/backups/layout-*.json`; the apply output names the one it took.
With fresh approval: `.venv/bin/unjiggle json restore <backup>`. It backs up the current
layout first, writes, and verifies. A restore can't bring back an icon the backup doesn't
hold. Offloaded and App-Library-only apps stay installed either way.

## Host notes

- Claude Code: the workspace's `.claude/settings.json` (written by setup) allows the read-only
  commands, forces a prompt for every write, and denies the risky commands. Keep that file.
- Other hosts: there's no permission layer, so the guardrails above are the only gate. Ask
  in chat before every write.
