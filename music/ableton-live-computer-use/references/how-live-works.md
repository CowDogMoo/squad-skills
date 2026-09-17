# How Live works

The model behind the pixels. Knowing it tells you what a click will do
before you make it, and what a screenshot means afterwards. Section
numbers are manual sections (`python3 scripts/live_manual.py show 3.7`).

## Documents: Sets, Projects, samples (3.5, 5.4, 5.5)

- A **Live Set** (`.als`) is the document. It lives inside a **Project**
  folder that also holds `Samples/`, `Backup/`, and `Ableton Project
  Info/`. Save As into a new folder creates a new Project.
- Audio clips **reference** sample files; MIDI is embedded. Move or delete a
  sample and the clip goes offline (5.6). **Collect All and Save** copies
  every external sample into the Project (5.7). Consolidated and frozen
  audio lands in `Samples/Processed/`.
- Every sample gets an `.asd` analysis file beside it (warp markers,
  default clip settings, waveform cache).
- The **undo history** is per Set and survives across views; Cmd+Z undoes
  edits, not transport actions, and not Save.
- Templates and default Sets come from Settings > File & Folder.

## Two views, one set of tracks (3.6, 3.7)

- The **Session View** is a grid: tracks are columns, **scenes** are rows,
  and each **clip slot** launches independently. Clips loop until stopped;
  launching quantizes to the global Quantization chooser.
- The **Arrangement View** is a timeline: the same tracks stacked, clips at
  positions in bars.beats.sixteenths.
- A track plays **either** its Session clip **or** its Arrangement lane.
  Session wins; the **Back to Arrangement** button (F10) hands control
  back. If Arrangement audio is silent while a clip plays, that button is
  the reason.
- Both views share the **mixer** and the **device chains**.

## Tracks and signal flow (3.8, 3.11, 3.14, 3.16)

- Track types: **audio** (audio clips, audio effects), **MIDI** (MIDI
  clips, MIDI effects then an instrument then audio effects), **return**
  (effects fed by sends, no clips), **group** (a submix folder of tracks),
  and the **Main** track. A MIDI track with no instrument outputs MIDI and
  its mixer volume disappears.
- Signal path per track: clip -> device chain, left to right -> mixer
  (volume, pan, sends) -> output routing. Audio between devices is 32-bit
  float: nothing clips inside Live, only at physical outputs and exported
  files (18.1.1).
- **Routing** lives in the In/Out section of the mixer (Cmd+Option+I):
  Audio/MIDI From, input channel, **Monitor** (In / Auto / Off), Audio/MIDI
  To, output channel (17). Auto monitors while armed and no clip plays; In
  always passes the input (track activator turns blue); Off never does.
- **Arm** (C) enables recording and, under Auto, monitoring. Exclusive Arm
  and Exclusive Solo are Settings > Record Warp & Launch options; Cmd-click
  arms or solos several tracks at once (18.1).
- **Freeze** (Cmd+Option+Shift+F) renders the track to temporary audio
  and disables its devices to save CPU; the track becomes read-only until
  unfrozen (38.2.7). Live 12 replaced "Freeze and Flatten" with **Bounce
  Track in Place** and **Bounce to New Track** (Cmd+B), which render
  through the chain into a real audio clip (20.1).

## Clips (3.9, 3.10, 8, 9)

- Every clip has a Clip View: start/end, **loop** brace, signature, groove,
  and for Session clips the launch settings (launch mode, quantization,
  legato, follow actions).
- **Audio clips** have **Warp**: when on, Live time-stretches the sample to
  the Set tempo using **warp markers** that pin sample positions to beats;
  when off, the sample plays at its native speed. Warp modes trade
  artifacts: Beats for drums, Tones for monophonic, Texture for pads,
  Re-Pitch for vinyl-style, Complex / Complex Pro for full mixes (9.3).
  Seg. BPM is the tempo Live thinks the sample was recorded at; the ×2 / :2
  buttons fix a doubled or halved detection.
- **MIDI clips** hold notes with velocity, chance, and release velocity;
  the note editor snaps to the grid (Cmd+1..5), Draw Mode (B) paints notes,
  and MIDI Tools transform or generate notes (10, 11).
- **Clip envelopes** automate or modulate parameters per clip and can be
  unlinked from the clip length (26). **Track automation** lives in the
  Arrangement (Automation Mode, A) and in Session clips; touching an
  automated control overrides it until Re-Enable Automation is pressed (25).
- **Consolidate** (Cmd+J) renders a time selection into one new clip per
  track, pre-effects (6.13). **Crop** trims the sample to the clip.

## Devices and plug-ins (23, 24)

- Live devices, Max for Live devices, and VST2/VST3/AU plug-ins all sit in
  the same chain. Instruments only accept MIDI on their left; audio effects
  only accept audio.
- **Racks** wrap chains with **Macro** knobs, chain selectors, and key/
  velocity zones; Drum Racks map pads to notes (24).
- Plug-ins show a Live panel of up to 64 parameters; more than that starts
  empty and needs **Configure** mode. The vendor GUI opens in a floating
  window from the title-bar button. Automation of a plug-in parameter
  requires that parameter to be in the Live panel (23.3.1).
- Plug-in scanning happens at launch and on **Rescan** in Settings >
  Plug-Ins; Option-click Rescan wipes the plug-in database first.
  `Log.txt` records every plug-in that failed to load.

## Recording (19)

- Arrangement recording: arm tracks, press Arrangement Record (F9), Play.
  Every take becomes a new clip; **take lanes** and **comping** stitch
  takes (21). Punch In/Out use the loop brace.
- Session recording: arm, press Session Record (Cmd+Shift+F9); the new
  clip lands in the selected scene and starts looping when you press again.
- **Capture MIDI** grabs what you just played on an unarmed instrument
  track after the fact.
- Record Quantization and MIDI Overdub are Control Bar settings; Count-In
  is in the metronome dropdown.

## Tempo, sync, time (9.1, 36)

- Set tempo lives in the Control Bar; clips can be tempo leaders with
  Tempo Follower; **Link** syncs over the LAN; MIDI clock and Tempo
  Follower (audio) are in Settings > Link, Tempo & MIDI.
- Time signature changes are Arrangement markers. The **loop brace**
  (Cmd+L) drives Arrangement looping and export length by selection.

## Export (5.1.3)

Export Audio/Video (Cmd+Shift+R) renders offline from the Set as it plays
now: Session clips that are running are what gets rendered, whatever view
is open. Select a time range first to prefill Render Start and Length.
Rendered Track chooses Main, all tracks, selected tracks, or one track.
Sets with External Instrument or External Audio Effect render in real
time. Export is not undoable and writes files, so confirm the folder.

## CPU and audio settings (37)

- Buffer size, sample rate, driver, and input/output channels are in
  Settings > Audio. Changing the device or buffer interrupts audio;
  changing the sample rate re-warps every clip's playback math.
- The CPU meter in the Control Bar is the mixer's worst-case load; the
  Performance Impact mixer section shows per-track load. Freeze or Bounce
  heavy tracks; Reduced Latency When Monitoring is in the Options menu.

## Options.txt and preferences (2.3)

`~/Library/Preferences/Ableton/Live <version>/Options.txt` takes one flag
per line and is read at launch. Known flags include
`-EnableHotSwapOnSelection`, `-DisableHotKeyLatching`,
`-MaxForLiveDeveloperMode`, and `-DisableAppleSiliconBurstWorkaround`
(present on this rig). Editing it is a config change: ask first, and Live
must restart to read it.

## Where the API stops

The `ableton-mcp` control surface (Live Object Model) can create and name
tracks, clips, notes, scenes, cue points, load browser items, set device
parameters, tempo, volume, pan, arrangement loop, playback, and read the
session. It cannot: open Settings, change audio device or buffer, save or
Save As, Collect All, export or bounce, consolidate, freeze, crop, split,
warp, edit fades or automation breakpoints by hand, open or drive a
plug-in window, rescan plug-ins, resolve missing-file dialogs, rename
scenes, or touch anything in a modal dialog. Those
are the screen-control jobs.
