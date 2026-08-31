# Rig and DAW setup for the one-pass comparison

Everything the one-cable QC-over-USB method assumes about the hardware, the
Ableton set, and Cortex Control. Read this when a take comes out wrong, when
a channel is silent, or when the routing has to be changed.

## QC USB channel map

As macOS lists them for the "Quad Cortex" device (8 in / 8 out):

| Channel | Carries |
| ------- | ------- |
| in 1–2 | Dry Input 1/2 — the guitar pre-grid |
| in 3–4 | Wet Signal L/R — the processed output |
| in 5–8 | From Grid 5–8 |
| out 1–2 | XLR Output 1/2 |
| out 3–4 | TRS Output 3/4 |
| out 5–8 | To Grid 5–8 |

## Wet Signal is silent in Ableton

Wet Signal follows the preset's output routing. With the last row ending on
"Out 3" the Wet channels carry nothing. Fix: set the lane output tile to
**Multi Out** and enable **USB Output 3/4** in the Multiple Outputs list
(Cortex Control: click the Out tile → OUTPUT list → Multiple Outputs), then
save the preset. This is the only silent-channel cause seen.

## Ableton audio devices

- Live only enumerates CoreAudio devices at launch. Separate input (Quad
  Cortex) and output (Fireface) devices work fine and need no restart, and
  both recorded signals come off the same device, so their alignment is
  exact regardless.
- A device hot-plugged after launch shows up as a later `CoreAudio: Device
  init:` line in the log and is usable. An **Aggregate Device** created
  while Live is open is not — it only appears in the input list after a
  restart.
- The Aggregate Device on this Mac (Fireface + QC, Fireface as clock,
  48 kHz, drift correction on the QC, built in macOS **Audio MIDI Setup**)
  reported **20 In / 20 Out** — that is the Fireface alone, without the QC's
  USB channels. "Aggregate for the DI" is therefore not a shortcut; it is an
  Audio MIDI Setup job plus a Live restart.
- Live Input Config: enable Mono 1&2 and Stereo 3/4 (Mono 3&4 too, harmless).

## Reading the set without the UI

Live's audio input device: `~/Library/Preferences/Ableton/Live <version>/
Log.txt`, the `CoreAudio: Device init:` lines from the last launch.

Track routing: the `.als` is gzipped XML. Each `<AudioTrack>` carries

```xml
<AudioInputRouting><Target Value="AudioIn/External/M0"/>
```

M = mono, S = stereo, 0-based, so `M0` = Ext. In 1, `S1` = Ext. In 3/4, and
`AudioIn/Track.N/PostFxOut` = Post FX of track N. `<LowerDisplayString>`
mirrors it ("1", "3/4"). Arm is the first `<Recorder><IsArmed>` inside the
track's `<MainSequence>`; solo is `<SoloSink>` (true = soloed).

Wanted state: Thall `M0` armed, REC `Track.<thall>/PostFxOut` armed, QC `S1`
armed, nothing soloed.

## Driving Live when the UI won't cooperate

Live's **Settings window and the routing/chooser popups do not respond to
screen-control clicks** — Settings closes on the first click, chooser popups
never appear in screenshots, arrow keys do nothing in them. Don't burn more
than one attempt. The macOS **menu bar works**, including keyboard
navigation inside it.

To change routing, arm, or solo anyway:

1. `cmd+s`, and verify File → Save Live Set is greyed out.
2. Copy the `.als` into `Backup/` with a descriptive name.
3. Patch the XML with a short python read-modify-write on the device:
   `gzip.open` → `str.replace` scoped to the one `<AudioTrack Id="N">` block
   → `gzip.open(..., "wb")`.
4. Reload: click **File**, `Down`×3 to "Open Recent Set", `Right`, `Return`
   on the first entry (the current set). Live reloads from disk without a
   prompt; the input meters light up immediately if routing is right.
5. Re-check plugin state — it can come back different after the reload.

`ableton-mcp` cannot read or set input routing, monitoring, or the audio
device. It can read and set device parameters, arm, solo, mute, and volume.
Use it for state verification and the `.als` for routing.

## Recorded files

- Takes land in `<project>/Samples/Recorded/<track name> NNNN
  [timestamp].wav` — mono 24-bit 48k. A stereo Post-FX take from a mono
  plugin is dual-mono.
- The Ableton timestamp is the moment the take was **armed**, which can
  precede the playing by a few minutes.
- Zero-byte files are aborted takes; ignore them. A 3 s take at −90 dBFS is
  an arm-and-stop, not data.
- Live reuses a previous aborted arm's filenames and creates fresh 0-byte
  arms. Pair files by mtime and size.
- The capture models the plugin's noise floor: the plugin with its gate at
  −100 dB idled at −30 dBFS RMS and so did the QC takes. A gate after the
  capture in the preset handles this; the input gate cannot remove modelled
  hiss.
