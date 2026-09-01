# Rig inventory and screen-control notes

## The rig

- Interface: RME Fireface UCX II ("Fireface UCX II (24196183)"), TotalMix FX.
- DAW: Ableton Live 12 Suite, project `~/Music/Ableton/Recording Projects/
  amp-sim-neural-capture Project`.
- Cortex Control (desktop app) runs the entire Neural Capture flow, so the
  hardware screen is never needed. Menu (⋯, top right) → **New Neural
  Capture**.
- Two monitors: Ableton usually on one (ASUS XG32VQR or VG32VQ1B), TotalMix
  and Cortex Control on the other. When automating, expect windows on either.

## Screen control during a capture

- **One click → screenshot → verify** for anything with state: dropdowns,
  metadata forms, TotalMix strips. Batched blind clicks are what caused the
  one real failure of a capture session — a capture started with the wrong
  name and type.
- **TotalMix faders and knobs both take `computer_left_click_drag`.** Verified
  2026-09-01 in a session with no click offset. There is no class of TotalMix
  control that drags refuse; when one seems dead, the cause is the click-offset
  session bug (`quad-cortex-preset-editing`,
  `references/screen-control-workarounds.md`) or a stray Data Edit Window
  holding focus — check those two, in that order, before recording a
  limitation.
- **TotalMix knobs take the scroll wheel.** Measured 2026-08-31 on the Reverb
  Pre Delay knob: three line-scroll events moved it 20 → 11 (≈3 units a tick)
  and three the other way put it back to exactly 20. There is a preference for
  it — `DisableMouseWheel` in `~/Library/Application Support/RME TotalMix
  FX/rme.totalmix.preferences.xml` — set to `0` (enabled) on this rig. An
  earlier note here said knobs ignore scroll and that `cmd+click` does not
  reset faders. Both were wrong; `cmd+click` is not a TotalMix binding at all.
- **Double-click a knob and you get the Data Edit Window, not a reset.** It is
  a small numeric-entry dialog and it opens *away from the control* — about
  1190 px away in the measured case. It takes focus, so every drag, scroll and
  keystroke aimed at the knob afterwards does nothing. That is the likeliest
  explanation of the old "the gain knob refuses every input form" note: the
  dialog was open off to one side, unnoticed, eating the input.
- **Setting an exact value, the reliable way.** The Data Edit Window is fully
  accessible even though the mixer canvas is not:

  | element | use |
  | ------- | --- |
  | `AXStaticText`, e.g. "Pre Delay Time" | **confirms which control you hit** |
  | `AXTextField` | the value |
  | `AXButton "OK"` / `AXButton "Cancel"` | commit, or back out changing nothing |

  Double-click the control, read the label to check you got the right one, set
  the field, press OK. Reading that label before committing is what removes
  the blind-click risk that cost this project a capture session.
- **The mixer canvas exposes nothing to accessibility.** The main window has
  four AX children, all window chrome — there is no AX path to strips, knobs
  or faders, only to dialogs like the Data Edit Window. The **menu bar is
  fully accessible** though: File carries Load/Save Snapshot, Preload all
  Snapshots, Load/Save Workspace, Workspace Quick Select and Open Recent;
  Options carries Enable MIDI/OSC Control, Settings, Channel Layout, Reset
  Mix and Store current State into Device.
- **Do not read current state from `~/Library/Application Support/RME TotalMix
  FX/last.<device>.xml`.** It dumps every parameter, which makes it tempting,
  but it is only written on save: on 2026-08-31 it was 25 days stale while a
  different workspace was loaded. Read the UI, not that file.
- The wrench icon on an Ableton device titlebar is **hot-swap**, not "open
  plugin UI" — escape it via the X on the orange "Swapping Audio Effect"
  banner. The plugin window opens from the device's edit (plug) icon and may
  appear on the other monitor.
- App grants drop when the remote-device session drops; re-resolve and
  re-request rather than retrying clicks. Windows move between monitors, and
  TotalMix's window can vanish (closed = hidden) — relaunch it by opening the
  app. Ask the user rather than fighting either for more than two attempts.
- Live's Settings window and routing popups **do** respond to screen-control
  clicks — Settings opens and reads, and both chooser popups render and take
  clicks (observed 2026-08-31). An earlier note here claimed they never
  responded; it was wrong. The `.als`-patch plus File → Open Recent route is
  still in `quad-cortex-capture-measurement` for sessions that have no desktop
  screen control at all.
