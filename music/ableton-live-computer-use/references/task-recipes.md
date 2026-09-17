# Task recipes

Step lists for the jobs the API cannot do. Each one is keyboard-first,
names the verification, and cites the manual section to read when the UI
differs (`python3 scripts/live_manual.py show 5.1.3`).

## Export audio (5.1.3)

1. Decide the range. In Arrangement, select the time (or set the loop
   brace and Cmd+Shift+L); with nothing selected Live exports the whole
   Arrangement. Session clips that are running are what renders.
2. Cmd+Shift+R. Zoom the dialog. Set **Rendered Track** (Main, All
   Individual Tracks, Selected Tracks Only, or a single track), check
   Render Start / Length, then the options: Include Return and Main
   Effects, Render as Loop, Convert to Mono, Normalize, Create Analysis
   File, Sample Rate, Encode PCM (WAV/AIFF/FLAC, bit depth, dither), Encode
   MP3.
3. Click Export. In the macOS sheet, Cmd+Shift+G, type the destination
   folder, Enter, set the file name, Enter. Wait for the progress bar.
4. Verify with `ls -la` on the destination and `ffprobe` or `afinfo` for
   length and sample rate. Report the exact options used.

## Save, Save As, Collect All and Save (5.4, 5.7)

- Save: Cmd+S. Verify the `.als` modification time changed.
- Save As: Cmd+Shift+S, then in the sheet Cmd+Shift+G to the folder, name,
  Enter. Live creates a new Project folder when the target is outside the
  current one. Verify with `ls`.
- Collect All and Save: File menu > Collect All and Save; a dialog asks
  which categories to copy (Files from Library, Factory Packs, User
  Library, Current Project, Elsewhere). Choose per the user; verify
  `Samples/Imported/` grew.

## Settings: audio device, buffer size, sample rate (2.3.3, 40.2)

1. Cmd+, opens Settings. Use the up/down arrows in the page chooser to
   reach **Audio** (or click it).
2. Tab through Driver Type, Audio Input Device, Audio Output Device,
   Sample Rate, Buffer Size; arrows change a focused chooser, Enter
   confirms. Buffer and sample-rate changes restart the audio engine.
3. Esc closes Settings. Verify by reopening or by the sample rate shown in
   the Control Bar's MIDI and CPU group.

Changing the device, buffer, or rate is a config change: ask first unless
the task is exactly that.

## Plug-in rescan (23.3)

Settings > Plug-Ins > Rescan (Option-click to rebuild the database).
Verify in the browser's Plug-Ins label and in `Log.txt`.

## Insert a device or plug-in by name (23.2)

1. Click the destination track's title bar (selects it).
2. Cmd+F, type the device name, wait for results, down arrow to the first
   result, arrows to the right item, Enter. Live appends it to the chain.
3. Verify in the Device View (Option+4) and with `get_track_info`.

Prefer `load_instrument_or_effect` / `load_external_plugin` through the
API when they resolve the item; use the browser when the API lacks the
path.

## Open a plug-in GUI and set a parameter (23.3.1)

1. Option+4 for the Device View; click the plug-in device's title bar.
2. Click the Show/Hide Plug-In Window button in its title bar (hover to
   read the Info View if unsure). Screenshot; the window title carries the
   track name.
3. Zoom on the control, then drag or double-click-type. Read the value
   back from the GUI readout.
4. If the parameter must be automated or MIDI-mapped later, click
   **Configure** and touch the control so it joins the Live panel.
5. Cmd+Option+P hides the windows when done.

## Freeze, unfreeze, bounce (38.2.7, 20)

- Freeze: select the track, Cmd+Option+Shift+F or right-click the title
  bar > Freeze Track (37.1.4). The track and its devices become read-only;
  Unfreeze is the same command.
- Bounce to New Track: select the time or clips, Cmd+B; a new audio track
  appears with the rendered audio and the source is muted. Bounce Track in
  Place is in the track title-bar or clip context menu and replaces the
  source track (20.1). Both render post-effects, pre-mixer. Verify with
  `get_session_info`.

## Consolidate, crop, split (6.11 to 6.13)

Select time across the clips (Shift+drag for multiple tracks), then Cmd+J
to consolidate, Cmd+E to split at the insert marker or selection edges,
Cmd+Shift+J to crop. The new sample goes to `Samples/Processed/`.

## Warp a clip by hand (9.2)

1. Double-click the audio clip to open the Sample Editor. Ensure the
   Sample tab is showing (Option+Shift+1).
2. Set the warp mode chooser in the Audio panel. Check Seg. BPM; fix
   double/half with :2 and ×2.
3. Place the insert marker at a transient (Option+arrows jump between
   markers), Cmd+I inserts a warp marker, arrows nudge it, Delete removes
   it. Drag a marker to align a beat with the grid; Shift-drag the
   waveform to slide it.
4. Verify by playing the clip with the metronome on (O) and by
   `als_clip_region.py` in the transcribe skill if the region matters.

## Add or move locators and set the loop (6.4, 6.6)

- Locator: put the insert marker where you want it, then Set Locator
  (button at the right of the scrub area) or Create menu > Add Locator.
  Cmd+R renames the selected locator.
- Loop brace: select time, Cmd+L toggles the loop over it. Cmd+F10 and
  Cmd+F11 set the loop start and end at the insert marker.

## Group, rename, color, reorder tracks (18.3, 18.1)

- Group: select the tracks, Cmd+G. Ungroup Cmd+Shift+G.
- Rename: select, Cmd+R, type, Enter; Tab renames the next.
- Color: right-click the title bar, pick from the palette. Assign Track
  Color to Clips is in the same menu.
- Reorder: drag the title bar; in Session, Cmd+left/right moves the
  selected track.

## Key or MIDI map a control (33)

Cmd+K (or Cmd+M) enters the map mode: click the control, press the key or
move the controller, then Cmd+K again to leave. The mapping browser on the
left lists every mapping; select one and press Delete to remove it.

## Fix a missing-file dialog (5.6)

Read the Status Bar or the dialog; File > Manage Files opens the File
Manager with a Missing Files section and an automatic search you can point
at a folder. Never "Ignore" for the user without asking: it silences the
warning and leaves clips offline.

## Reading state without changing it

- Which view, what is playing: screenshot the Control Bar and Track
  Status fields.
- Track list, clip positions, tempo: `get_session_info`,
  `get_arrangement_info`.
- Device parameters: `get_device_parameters`, and the Device View with a
  zoom for anything the API does not expose.
- Whether the last MCP command reached Live:
  `tail -20 ~/Library/Preferences/Ableton/Live\ 12.4.5/Log.txt`.
