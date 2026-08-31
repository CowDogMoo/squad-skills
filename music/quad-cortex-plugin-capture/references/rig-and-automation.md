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
- TotalMix knobs ignore scroll. **Drag** them (≈30 px ≈ 13 dB) or find the
  value box. `cmd+click` does not reset faders reliably.
- The wrench icon on an Ableton device titlebar is **hot-swap**, not "open
  plugin UI" — escape it via the X on the orange "Swapping Audio Effect"
  banner. The plugin window opens from the device's edit (plug) icon and may
  appear on the other monitor.
- App grants drop when the remote-device session drops; re-resolve and
  re-request rather than retrying clicks. Windows move between monitors, and
  TotalMix's window can vanish (closed = hidden) — relaunch it by opening the
  app. Ask the user rather than fighting either for more than two attempts.
- Live's Settings window and routing popups do not respond to screen-control
  clicks at all. The `.als`-patch plus File → Open Recent workaround is in
  `quad-cortex-capture-measurement`.
