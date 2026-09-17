---
name: ableton-live-computer-use
description: Drive Ableton Live 12 through screen control (computer use) when the ableton-mcp API cannot do the job - export or bounce, Save As, Collect All, Settings (audio device, buffer, plug-in rescan), plug-in GUI windows, warp markers, consolidate, freeze, comping, locators, key/MIDI mapping, dialogs - with a full UI map, how Live works, manual-verified shortcuts, and a script that caches and full-text searches the official Live 12 manual (scripts/live_manual.py search, show, shortcuts). Use for "click in Ableton", "do it in the Live UI", "export the track from Live", "open Settings in Ableton", "change the buffer size", "open the plug-in window", "what does this button do in Live", "look up the Live manual", or any Live task with no matching MCP function. Do NOT use for jobs the API covers (tracks, clips, notes, tempo, volume, pan, device parameters - use ableton-mcp directly), for Cortex Control or TotalMix screen work (quad-cortex-preset-editing), or for transcribing audio (transcribe-guitar-riff).
---

# Ableton Live via screen control

Do in Live's UI what the API cannot, and know the program well enough to
do it right the first time. The manual is one command away; the screen is
the source of truth for state; the API is the source of truth for numbers.

Rig: Live 12.4.5 Suite on macOS, two displays, `ableton-mcp` control
surface installed, Neural DSP and Odeholm plug-ins in use.

## Host-environment translation

| Abstract action | Claude Code (this host) | Cowork / desktop bridge |
| --- | --- | --- |
| Ask for app control | `mcp__computer-use__request_access` with apps `["Ableton Live 12 Suite"]` (bundle `com.ableton.live`) | `computer_resolve_access` then `computer_request_access` |
| Look | `mcp__computer-use__screenshot`, then `zoom` on the region you will act on | `computer_screenshot` (scale 0.6 to orient, 1.0 to aim), `computer_zoom` |
| Pick the display | `mcp__computer-use__switch_display` with the name from the screenshot note | `computer_switch_display` |
| Bring Live forward | `mcp__computer-use__open_application` | `computer_open_application` |
| Click, drag, type, keys | `left_click`, `double_click`, `right_click`, `left_click_drag`, `type`, `key`, `scroll`; `computer_batch` for predictable sequences | `computer_left_click`, `computer_left_click_drag`, `computer_type`, `computer_key` |
| Where did the click land | `mcp__computer-use__cursor_position` | `computer_cursor_position` |
| Read or write Live state exactly | `mcp__ableton-mcp__get_session_info`, `get_track_info`, `get_device_parameters`, `get_arrangement_info`, `set_*`, `load_*` | ableton-mcp equivalents, or ask the user to read the value |
| Query the manual | `python3 scripts/live_manual.py search "..."` (Bash) | same script; needs Python 3.9+ and network once |
| Check files and logs | Bash: `ls -la`, `tail ~/Library/Preferences/Ableton/Live\ 12.4.5/Log.txt` | `device_bash` |

Paths are relative to this skill's directory (`${CLAUDE_SKILL_DIR}` or
`$SQUAD_SKILL_DIR`). The manual script is standard-library Python; the
first query downloads the 42 chapters into
`~/.cache/ableton-live-manual/12/` and every later query is offline.

## Objective and guardrails

Done means: the requested change is visible on screen or in a file, has
been verified by a second channel (API read, file time, Status Bar, or a
zoomed screenshot taken after the action), and the report says exactly
what was changed, what was left alone, and what could not be verified.

- **API before pixels.** If `ableton-mcp` has a function for it, use the
  function and verify with a screenshot. Screen control is for the rest:
  see "Where the API stops" in `references/how-live-works.md`.
- **Keys before clicks.** Every menu command has a shortcut or a menu-bar
  path; both are layout-independent. Click only when no key reaches the
  control. `references/keyboard-shortcuts.md` is verified against the
  manual's tables.
- **One change, one screenshot.** Re-screenshot before every click at a
  new position: the user works in the same window and it moves.
- **Undo covers edits, not I/O.** Cmd+Z reverts clip, note, device, and
  mixer edits. It does not revert Save, Save As, Collect, Export, Bounce
  files on disk, plug-in rescans, Options.txt, or audio-device changes.
  Those wait for the user's yes unless the request names them.
- **Never** quit Live, close the Set, press Arrangement Record (F9) or
  Session Record, arm tracks, delete tracks or clips, change the audio
  device or buffer, or answer a dialog's question, unless the request
  says so. Live's dialogs ("Save changes?", missing files, "Set was not
  closed properly") are the user's to answer: quote them and stop.
- **Stop and ask** when: a plug-in GUI or dialog you do not recognize is
  in front; a click landed somewhere other than aimed twice in a row (see
  the click-offset section of `references/screen-control-playbook.md`); the
  Set name in the title bar is not the one the user named; the transport
  is recording; or a step would write outside the Project folder.
- **Report what the screen showed**, not what you intended. A shortcut
  that produced no visible change is a finding, not a success.

## Step-by-step

### 1. Route the task

Split the request into API steps and screen steps. Anything in the
ableton-mcp tool list (tracks, clips, notes, tempo, volume, pan, device
parameters, browser loads, playback, cue points, arrangement loop) is an
API step. Everything else (Settings, Save/Export, plug-in windows,
Consolidate, Freeze, warp markers, comping, mapping, dialogs, browser
operations the API cannot resolve) is a screen step. If the whole task is
API-shaped, this skill is not needed; do it with the API and finish.

### 2. Read the manual before an unfamiliar UI step

```bash
python3 scripts/live_manual.py search "render as loop"      # ranked hits with section number, URL, snippet
python3 scripts/live_manual.py show 5.1.3 --deep            # a section and its subsections
python3 scripts/live_manual.py shortcuts "locator"          # shortcut rows, Mac keys
python3 scripts/live_manual.py toc arrangement-view         # a chapter's outline
```

Search is AND-of-terms with title bonus; it falls back to partial
matches and exits 1 with "no results" when nothing matches. `show`
accepts a number (`6.13`), an anchor id (`consolidating-clips`), or a
title. Cite the section number in the report when the manual decided a
step. `references/how-live-works.md` is the short model; the manual is the
long one.

### 3. Get in and orient

1. Request access (table above). Read which display Live is on; switch
   to it. `open_application` if Live is not frontmost.
2. Screenshot. Record: Set name, view (Session or Arrangement), Play and
   Record state, any open dialog or plug-in window, browser visible or
   not, Clip/Device View showing. `references/ui-map.md` names every
   region of the window and the nine Control Bar groups.
3. Calibrate the click offset once: click a harmless unique-height
   target and compare `cursor_position` with the aim. If offset, aim
   `y + offset` all session and lean harder on keys.
4. Stop the transport (Space, or the Stop button) unless the task needs
   playback.

### 4. Act, keyboard-first

For each screen step, follow the matching recipe in
`references/task-recipes.md` (export, Save As, Collect All, Settings,
plug-in windows, freeze and bounce, consolidate, warp, locators, groups,
mapping, missing files). The generic loop:

1. Put focus where the command applies (Option+1 Session, Option+2
   Arrangement, Option+3 Clip View, Option+4 Device View, Option+5
   Browser; or click the target's title bar).
2. Issue the command by shortcut or menu path. Type values by clicking
   the field, typing, Enter. `references/screen-control-playbook.md` has
   value entry, drags, focus rules, and dialog handling.
3. Screenshot and zoom the result. Compare against what the manual says
   should have happened.
4. If nothing changed: check focus (Esc, click the area), the Computer
   MIDI Keyboard toggle (letters play notes when it is on), Key/MIDI Map
   mode (colored overlay), and a modal dialog. Retry once with the menu
   path instead of the shortcut. Then stop and report.

### 5. Verify by a second channel

| Change | Verify with |
| --- | --- |
| Track, clip, tempo, device parameter | `get_session_info`, `get_track_info`, `get_device_parameters` |
| File written (Save, Export, Bounce, Collect) | `ls -la` and the modification time; `afinfo` or `ffprobe` for audio length |
| Settings change | Reopen Settings and zoom the field; sample rate also shows in the Control Bar |
| Plug-in window edit | The plug-in's own readout, then the Live panel slider after Configure |
| Live-side error or MCP delivery | `tail -20` of `Log.txt` in the version's Preferences folder |
| Anything else | A zoomed screenshot taken after the action, with the Info View hovered on the control |

### 6. Report

In prose: what was changed (command, where, resulting value); what was
verified and how; what was left alone; anything the screen showed that
you did not expect; manual sections consulted. If a step was blocked by a
dialog, an un-granted app, or the click offset, say which step and what
the user can do.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Shortcut does nothing | Focus is in another area, or a dialog is modal | Esc, click the target area, retry; screenshot for a dialog |
| Letters play notes instead of commands | Computer MIDI Keyboard is on | Press M or click the keyboard icon in the Control Bar |
| UI is tinted orange or blue and clicks select controls | Key Map or MIDI Map mode | Cmd+K or Cmd+M to leave |
| Tab does not switch views | Use Tab Key to Move Focus is on | Option+1 / Option+2, or Navigate menu |
| Arrangement is silent while a clip plays | Session clip overriding the track | F10 (Back to Arrangement) |
| Clicks land above the aim point | Per-session click-offset bug | Measure with `cursor_position`, aim `y + offset`, prefer keys |
| Every click hits nothing | Un-granted app frontmost, or cursor on the other display | `open_application` Live; `switch_display`; move the mouse onto the display |
| Screenshot shows no Live window | Live on the other display, or not granted | `switch_display`; re-request access |
| Export button disabled | Neither Encode PCM nor Encode MP3 is on | Enable one |
| Exported audio is not what plays | Running Session clips render, not the Arrangement | F10 then export, or stop the clips |
| Plug-in missing from the browser | Not scanned or failed to load | Settings > Plug-Ins > Rescan; check `Log.txt` |
| Value typed into a field was ignored | Field was not in edit mode | Single-click the number, type, Enter |
| `live_manual.py` exits 3 | No network on first sync | Run `sync` once online, or set `LIVE_MANUAL_CACHE` to a synced copy |

## Reference files

- `references/ui-map.md` — window anatomy, Control Bar groups, Session,
  Arrangement, Clip View, Device View, Browser, menus, dialogs, rig notes.
- `references/how-live-works.md` — the model: Sets and Projects, two views
  one track set, signal flow, clips and warping, devices and plug-ins,
  recording, export, CPU, Options.txt, and where the API stops.
- `references/keyboard-shortcuts.md` — Mac shortcuts verified against the
  manual, grouped by task.
- `references/screen-control-playbook.md` — access, seeing, aiming,
  typing values, focus, plug-in windows, dialogs, rig quirks, safety.
- `references/task-recipes.md` — step lists for export, save, settings,
  plug-ins, freeze and bounce, consolidate, warp, locators, groups,
  mapping, missing files.
- `scripts/live_manual.py` — sync, toc, search, show, shortcuts, status.
