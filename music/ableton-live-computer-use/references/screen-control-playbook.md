# Screen-control playbook for Live

Mechanics that make computer use on Ableton Live reliable: getting in,
seeing, aiming, typing values, and handling the rig's known quirks.

## Getting in

1. Request access for `Ableton Live 12 Suite` (bundle
   `com.ableton.live`). If a plug-in GUI, TotalMix, or Cortex Control is
   part of the job, request it in the same call: an un-granted app in
   front blocks every click, and granted apps are the only ones visible
   in screenshots.
2. Read the access reply: it names the display each app is on. Call
   `switch_display` with that name before the first screenshot if Live is
   not on the primary display.
3. `open_application` on Live brings it forward without asking the user;
   do this whenever a click reports the wrong app frontmost.
4. Screenshot. Confirm the Set name in the window title (Live shows it
   centered in the title bar), the view
   (Session grid or Arrangement timeline), transport state (Play lit?
   Record lit? Session Record lit?), and whether any dialog is open.

Access grants drop when the session drops. Re-request rather than
retrying clicks.

## Seeing

- Full screenshot for orientation; `zoom` on any region whose text you
  will act on. Never read a value from the downsampled image: a tempo of
  120.00 and 128.00 look alike at scale.
- Hover with `mouse_move` and read the **Info View** (bottom-left) to
  identify an unfamiliar control; it names every widget in Live.
- The **Status Bar** shows the last message ("Set saved", missing files,
  analysis progress) and note details in the note editor.
- Read state from the UI, not memory: the Play button, the arm buttons,
  the orange Back to Arrangement button, the `(B)` after a device name,
  the Hot-Swap bar above the browser content. A screenshot taken before an action is
  stale after it.
- Verify with the API when you can: `get_session_info`, `get_track_info`,
  `get_device_parameters`, `get_arrangement_info` are exact where a
  screenshot is approximate. Verify writes to disk with `ls` and file
  times, and Live-side errors with the tail of `Log.txt`.

## Aiming

- **Keys first.** Menu commands and shortcuts are layout-independent.
  Reach a view with Option+0..7, a menu with the menu bar, a dialog field
  with Tab.
- **Re-screenshot before every click** at a new location. The window
  moves, panels resize, and the user works in the same app.
- Click **text or the control body**, not the edge. Track title bars
  select on a single click and open the Device View on a double click.
- **Drags**: `left_click_drag` from the center of the source to the center
  of the target; for a device reorder, drop between two devices; for
  clips, drop onto empty lane space. Screenshot after every drag.
- **Scroll** with the scroll tool over the region; Shift+scroll scrolls
  horizontally in timelines.
- **Menus**: click the menu title in the macOS menu bar, screenshot, then
  click the item; or type the first letters once the menu is open. Esc
  closes a menu without choosing.
- **Context menus** via `right_click` on the element; they list the exact
  command names the manual uses.

## Typing values

Live's numeric fields are drag-or-type:

1. Single-click the field. It highlights for text entry (Tempo, loop
   length, clip start, warp Seg. BPM, device value boxes).
2. Type the number, press Enter. Esc cancels.
3. For knobs and sliders with no field, hover and use up/down arrow keys
   for unit steps, Shift+arrows for fine steps, or drag vertically.
   Delete resets a hovered or selected parameter to default.
4. Bars.beats.sixteenths fields take `.` and `,` to move between subfields.

Rename with Cmd+R: type the new name, Enter; Tab moves to the next
track/scene rename without leaving edit mode.

## Focus rules

- Live 12 has a keyboard-focus model. Option+1 puts focus on the Session
  grid, Option+2 on the Arrangement, Option+3 Clip View, Option+4 Device
  View, Option+5 Browser. Shortcuts act on the focused element: Cmd+A in
  the browser selects browser items, in the note editor notes.
- Esc walks focus back up (from a mixer control to the track title, from
  a dialog to nothing). If a shortcut does nothing, focus is elsewhere:
  click into the intended area first.
- The **Computer MIDI Keyboard** (M) turns letter keys into notes. If
  typing letters plays sounds instead of triggering shortcuts, toggle it
  off (Control Bar, keyboard icon lit).
- Key Map Mode (Cmd+K) and MIDI Map Mode (Cmd+M) overlay the UI in orange
  and blue; nothing else works until you leave them.

## Plug-in windows

- They are separate floating windows owned by Live; screenshots show them
  when Live is granted. Cmd+Option+P hides and shows all open ones.
- Open one from the device title-bar button, not by double-clicking the
  device (that folds it).
- Vendor GUIs (Neural DSP, Odeholm) are bitmap knobs: drag vertically for
  value, double-click for a text entry if the plug-in supports it, and
  read the value from the plug-in's own readout or from the Live panel
  slider after Configure. Prefer `set_device_parameter` through the API
  when the parameter is exposed there.
- Close with the window's own close control, never Cmd+W (that is not a
  Live shortcut and may hit another app).

## Dialogs

- Live's own dialogs (Export, Settings, missing files) take Tab/Enter/Esc.
  macOS save sheets take Cmd+Shift+G to type a folder path, then Enter.
- A modal dialog swallows every shortcut; screenshot first when Live seems
  unresponsive.
- Never dismiss an unexpected dialog blindly. Read it, quote it to the
  user if it asks a question you were not asked to answer.

## Known quirks on this rig

- **Click-offset bug**: some computer-use sessions land every click about
  260-270 px above the aim point while hover lands correctly. It is per
  session and can be absent. Calibrate at the start: click a harmless
  unique-height target (the Info View toggle, a scene number) and compare
  `cursor_position` with the aim; if offset, aim `y + offset` for the rest
  of the session and prefer keyboard commands. `left_mouse_down` /
  `left_mouse_up` do not bypass it. Calibration example (2026-09-16):
  `cursor_position` after a click on the mixer toggle at (1290, 810)
  reported exactly (1290, 810), so that session had no offset.
- **Two displays**: clicks go to the display last selected with
  `switch_display`. A cursor parked on the other display sends clicks
  nowhere; move the mouse onto the target display first.
- **Frontmost app**: TotalMix or a plug-in window can be frontmost while
  Live looks focused. `open_application` fixes it.
- **Log.txt** grows past 3 MB; read it with `tail`, not `cat`.

## Safety habits

- One change, one screenshot. Batch only what you can predict (click
  field, type, Enter, screenshot).
- Cmd+Z is the escape hatch for edits. It is not one for Save, Export,
  Collect, plug-in rescans, audio settings, or anything in a dialog: those
  wait for a yes.
- Stop the transport before structural edits unless the task needs
  playback; a running Set keeps redrawing and moving under the cursor.
- Say what you saw, not what you intended. "Pressed Cmd+S; the Status Bar
  did not confirm and the file time is unchanged" is a finding.
