# Live 12 UI map

What is where in the single-window layout, so a screenshot can be read
without hunting. Section numbers point into the manual
(`python3 scripts/live_manual.py show 3.1`).

## Window anatomy, top to bottom

```text
 macOS menu bar:  Live | File | Edit | Create | Playback | View | Navigate | Options | Help
 ┌───────────────────────────── Control Bar (3.1) ─────────────────────────────┐
 │ Browser ▸ | Link · Tempo · Sig · Metronome · Follower | Scale | Follow · Pos │
 │ ▶ ■ ● (Arr. Rec) | Overdub · Auto-Arm · Re-enable · Capture MIDI · Sess Rec │
 │ Loop ⟲ · Punch In/Out · Loop start · Loop length | Draw · Kbd · Key · MIDI  │
 │ CPU meter | View selector: Session ▦ / Arrangement ≡                        │
 ├─────────────┬───────────────────────────────────────────────────────────────┤
 │ Browser     │  Session grid  or  Arrangement timeline                       │
 │ (sidebar +  │  (tracks share the same mixer in both, 3.14)                  │
 │ content)    │                                                               │
 ├─────────────┴───────────────────────────────────────────────────────────────┤
 │ Clip View (8.1)  and/or  Device View (23.1), stackable                      │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Info View (bottom-left, 2.2.2)      Status Bar (3.2)      View toggles (br) │
 └─────────────────────────────────────────────────────────────────────────────┘
```

Bottom-right corner, right to left: the Mixer View Toggle with its config
menu (In/Out, Sends, Returns, Mixer, Track Options, Crossfader,
Performance Impact), then the Device View Selector (shows the highlighted
track's name and a miniature of its device chain; click to open the Device
View, scroll it when the view is open) and the Clip View Selector, each
with a small triangle that stacks that view above the other. Bottom-left is
the Info View toggle; the Status Bar runs along the bottom between them and
turns orange for warnings such as "Media files are missing".

A **Help View** pane can occupy the right edge (lessons, and "Report a
Crash" after a crash); it has its own close X at its top-left and does not
belong to the Set.

## Control Bar, left to right (3.1)

| Group | Contains | Keys |
| --- | --- | --- |
| Browser options | Show/Hide Browser toggle, Browser Config menu (full height, Tuning, Groove Pool) | Cmd+Option+B |
| Tempo and metronome | Link toggle, Tap Tempo, Tempo field (drag or type), Nudge down/up, Time Signature, Global Groove Amount (%), Metronome toggle and its dropdown, then the launch Quantization chooser (None, 1 Bar, ...) | Tempo: click the field, type, Enter; quantization Cmd+6..0 |
| Scale settings | Scale Mode toggle, Root Note, Scale Name; reflects the selected clip | |
| Follow and position | Follow toggle, Arrangement Position (bars.beats.16ths) | Option+Shift+F |
| Transport | Play, Stop, Arrangement Record | Space, F9 |
| Automation and Capture MIDI | MIDI Overdub, Automation Arm, Re-Enable Automation, Capture MIDI, Session Record | Cmd+Shift+F9 |
| Arrangement loop | Loop toggle, Punch In, Punch Out, Loop Start, Loop Length | Cmd+L |
| MIDI and CPU | Draw Mode, Computer MIDI Keyboard, Key Map, MIDI Map, sample rate, CPU meter | B, M, Cmd+K, Cmd+M |
| View selector | Session / Arrangement toggle | Tab |

The Play button stays lit while any Session clip runs, and the position
fields keep counting. Pressing Stop twice returns the position to 1.1.1 and
stops every clip (7.1).

## Session View (7, 40.4.1.2)

- **Track title bars** across the top: name, color, fold arrow for groups.
  Double-click a title bar to open its Device View. Right-click for the
  track context menu (insert, rename, color, group, freeze, delete).
- **Clip slots** below each title bar; scenes run left to right across
  tracks. A slot holds a triangular launch button on its left edge, a
  square stop button, or nothing.
- **Main track** column on the right: scene launch buttons and scene names,
  the Back to Arrangement button, and the Stop All Clips button.
- **Track Status fields** under the grid show what each track is playing.
- **Mixer** under that: In/Out (Audio From, Monitor In/Auto/Off, Audio To),
  Sends, Return tracks, then Meter, Volume, Pan, Track Activator, Solo,
  Arm. Return tracks and the Main track have their own strips.
- Cross-view rule: a track plays either a Session clip or the Arrangement,
  never both; Session wins, and the orange Back to Arrangement button lights
  while the Arrangement is overridden (3.7).

## Arrangement View (6.1)

Top strip: the **Overview** (drag to scroll, drag vertically to zoom,
double-click to see everything), then the **beat-time ruler**, then the
**scrub area** (click to launch playback from there; locators live here),
with the **Set Locator**, **Previous/Next Locator**, **Automation Mode**
(A) and **Lock Envelopes** toggles at its right end, next to the Back to
Arrangement button.

Body: tracks stacked vertically, each with a **main lane** (plus take lanes
when comping), the **Arrangement Track Controls** on the right (name, arm,
solo, activator, volume, pan, I/O), and a **Mixer Drop Area** under the
last track where a dropped instrument or effect creates a track. The
**Optimize Height / Width** toggles (H, W) and the **waveform vertical
zoom** slider sit at the bottom right of the track area; the
minutes-seconds **time ruler** runs along the bottom.

Time selection is the editing primitive: click-drag in a lane selects time
within one track, Shift extends across tracks, and Cmd+E/Cmd+J/Cmd+Shift+D
act on whatever is selected. The insert marker (a flashing line) is where
Enter, Paste, and split land.

## Clip View (8.1)

Title bar: Clip Activator toggle, clip name and color, Save Default Clip
(audio). Left: the **clip panels** (Main: start/end, loop, signature,
groove, scale; Extended: launch mode, quantization, legato, velocity,
follow actions for Session clips; then Audio Utilities and Transformation
Tools for audio, Pitch and Time Utilities and MIDI Tools for MIDI). Right:
the **editor**, with tabs Sample / Envelopes for audio and Notes /
Envelopes / MPE for MIDI (Option+Tab cycles).

Sample Editor: warp markers along the top of the waveform, gray transient
markers above them, Warp on/off and warp mode chooser (Beats, Tones,
Texture, Re-Pitch, Complex, Complex Pro) in the Audio panel, Seg. BPM with
:2 and ×2 buttons, clip Gain slider, Reverse, Edit (external editor).

MIDI Note Editor: piano roll with a key-track strip on the left, velocity
and chance lanes underneath, Draw Mode (B), Fold and Highlight Scale
toggles, grid chooser in the context menu.

## Device View (23.1)

Devices chain left to right. Each **device title bar** carries: Activator
(power), an expanded-view arrow on devices that have one (EQ Eight
display, Roar), name, Hot-Swap Presets (Q), Save Preset, and the Show
Options toggle (context menu, A/B compare). Small **level meters** sit
between devices. Racks add Show/Hide Macro, Chain and Device panels on the
left edge. Plug-in devices show a Live panel of sliders (up to 64 params)
plus **Unfold**, the **Show/Hide Plug-In Window** wrench-style button that
opens the vendor GUI in a floating window (title bar shows the track name),
and **Configure**. Click in the empty space after the last device to
select the chain end, so Paste or Enter from the browser appends there.

## Browser (4, 40.4.1.6)

Left sidebar labels in Live 12: Collections (colored), Sounds, Drums,
Instruments, Audio Effects, MIDI Effects, Max for Live, Plug-Ins, Clips,
Samples, Grooves, Templates, Packs, User Library, Current Project, Cloud,
Push, and any user-added Places. Top: the search field (Cmd+F selects the
All label and focuses it), the Show/Hide Filter View toggle, then the
**content pane** with a Name column (extra columns via the Content Options
menu). Headphones icon at the bottom of the sidebar is Browser File
Preview. While hot-swapping, a **Hot-Swap bar** with an X appears at the
top of the content pane.

## Menus (macOS)

- **Live**: About, Settings (Cmd+,), Hide, Quit.
- **Playback** (observed 12.4.5): Play (Space), Continue Playback
  (Shift+Space), Play From Insert Marker (Option+Space), Return Play
  Position to 1.1.1, Move Insert Marker To Playhead (Cmd+Shift+Space), an
  Options submenu, Record to Arrangement (F9), Arm Recording to
  Arrangement (Shift+F9), Record to Session (Cmd+Shift+F9), Metronome (O),
  Hear Metronome Only While Recording, Back to Arrangement (F10).
- **File**: New/Open/Save/Save As, Save a Copy, Collect All and Save,
  Manage Files, Export Audio/Video (Cmd+Shift+R), Export MIDI Clip,
  Import, recent Sets.
- **Edit**: Undo/Redo, Cut/Copy/Paste/Duplicate/Delete, Rename, Select
  All, Select Loop, Deactivate, Return to Default, Compare A/B, Split,
  Consolidate, Crop, Quantize, Freeze Track / Unfreeze, Bounce commands.
- **Create**: Insert Audio/MIDI/Return Track, Insert Scene, Capture and
  Insert Scene, Insert Locator, Insert MIDI Clip, Insert Silence, Add
  Locator, Capture MIDI, Group/Ungroup.
- **View**: Browser, Info, Overview, Mixer Controls submenu, Arrangement
  Track Controls submenu, Clip View / Device View, editor tabs, Full
  Screen, Second Window, Show/Hide Plug-In Windows, Zoom.
- **Options**: Draw Mode, Follow, MIDI Note Editor Preview, Browser File
  Preview, Computer MIDI Keyboard, Edit MIDI Map / Key Map, Solo/Cue,
  Accessibility submenu.
- **Navigate**: focus commands (Option+0 ... 7), Use Tab Key to Move Focus,
  Wrap Tab Navigation, Next/Previous Neighbor.
- **Help**: Learn View, Info View, links to the manual, Knowledge Base,
  and updates. Plug-in rescan is in Settings > Plug-Ins, not here.

## Dialogs you will meet

- **Settings** (Cmd+,): page chooser on the left with Display & Input,
  Theme & Colors, Audio, Link, Tempo & MIDI, File & Folder, Library,
  Plug-Ins, Record Warp & Launch, Licenses & Updates. Esc closes it. Tab
  and arrows navigate inside it whatever the Tab setting (40.1.2).
- **Export Audio/Video** (Cmd+Shift+R, 5.1.3): Rendered Track chooser,
  Render Start / Length, Include Return and Main Effects, Render as Loop,
  Convert to Mono, Normalize, Create Analysis File, Sample Rate, Encode
  PCM (WAV/AIFF/FLAC, bit depth, dither), Encode MP3, then a macOS save
  sheet for the folder and name.
- **Save As / Collect All and Save**: macOS save sheet; Collect asks which
  external files to copy into the Project.
- **Missing files / plug-in rescan / crash recovery** dialogs appear on
  open; read them before touching anything.
- **Plug-in windows** are separate floating windows, one per instance;
  Cmd+Option+P hides and shows all of them.

## Rig notes for this machine

- Live 12.4.5 Suite, macOS, two displays (ASUS XG32VQR and ASUS VG32VQ1B).
  Live has been observed on the non-primary XG32VQR; screenshots capture
  one display at a time and the screenshot note names the others for
  `switch_display`.
- Observed layout on 2026-09-16: Arrangement View with the mixer open under
  the tracks, browser on the left, Device View at the bottom showing the
  thall amp, Fortin Nameless and Archetype Gojira X plug-in devices (each
  with activator, expand, plug-in window, hot-swap, save and options
  buttons; Gojira with a Configure button), Info View bottom-left, Help View
  on the right.
- Preferences: `~/Library/Preferences/Ableton/Live 12.4.5/` holds `Log.txt`
  (remote-script traffic, plug-in load errors, crashes), `Options.txt`,
  `Preferences.cfg`, `Undo/`, `Crash/`.
- Control surfaces `AbletonMCP` and `AbletonOSC` are installed under
  `~/Music/Ableton/User Library/Remote Scripts/`; the MCP server lives in
  `~/Music/ableton-mcp-extended`.
- Plug-ins in use: Neural DSP (Archetype Gojira X, Fortin Nameless Suite X),
  Odeholm thall amp, EZdrummer 3. Their windows are large and can cover the
  Device View.
