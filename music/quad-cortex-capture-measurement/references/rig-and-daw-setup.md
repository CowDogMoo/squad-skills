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

## Two Live sets: capture and measurement

Since 2026-09-08 the rig has two projects side by side under
`~/Music/Ableton/Recording Projects/`:

| Project | Set | Used for |
| ------- | --- | -------- |
| `amp-sim-neural-capture Project` | `amp-sim-neural-capture.als` | Neural Capture runs (`quad-cortex-plugin-capture`); home of `CAPTURE-TEST-STATE*.md`, `NOTES.md`, the historic `null-test-*.png` plots |
| `amp-sim-measurement Project` | `amp-sim-measurement.als` | Measurement takes only. Three audio tracks, routed and armed as this skill wants, no clips |

The measurement set was built from the capture set by XML patch (see
"Stripping clips from a set" below), so both share the same thall amp
instance settings as of that moment; the plugin reference is still the
capture project's state file. The measurement project carries its own
`README.md` with the pre-flight, a `Backup/` with every intermediate variant
(including the one that crashes Live, labelled), and `.capture-set.sha256`,
the checksum of the capture set it was built from.

What the split does and does not fix:

- Track routing, arm, monitor and solo are per set, so they are now right the
  moment the measurement set opens. No more Ext. In 1 / Ext. In 4 juggling on
  the plugin track after a capture.
- The audio input device is a **global Live preference**. The capture skill
  leaves it on the Fireface; the measurement set cannot switch it back. That
  is the one manual step left before a take.
- A `Utility` on the QC track is not in the recorded file (Live records
  pre-FX), so the measurement set keeps it and it does no harm.

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

Live's log is `~/Library/Preferences/Ableton/Live <version>/Log.txt` (pick
the newest version directory).

- **Audio input device:** the last `Audio In Out: Input Device:` line, e.g.
  `Audio In Out: Input Device: Fireface UCX II (24196183) (20 In, 20 Out)`.
  It is written at launch and whenever Live reconfigures audio, including a
  document load, and it carries a timestamp, so the history of switches is
  readable too. The `CoreAudio: Device init:` lines only enumerate what
  exists; they do not say which one is selected. Caveat: on 2026-09-06 a
  checker reading this line reported Fireface while Settings showed Quad
  Cortex, so a switch made in Settings can go unlogged until the next
  reconfigure. Use the log to catch the common case (left on the Fireface
  after a capture) and confirm in Settings > Audio by eye before the take.
- **Which set is open:** the last `Loading document "<path>"` line. A Live
  relaunch loads whatever the user picks from the recent list, not the last
  set this skill worked in. Cross-check with `ableton-mcp` `get_session_info`
  (track count) and `get_track_info` (names): the measurement set has three
  audio tracks named "Thall Amp Raw Dawg", "REC plugin post FX", "QC amp and
  cab" plus three empty MIDI tracks.

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

## Driving Live's routing

Live's **Settings window and the routing/chooser popups do take screen
control**. Settings opens and reads normally, and both chooser popups render
and accept clicks — observed at the rig on 2026-08-31. The macOS **menu bar**
works too, including keyboard navigation inside it.

An earlier version of this file said the opposite: that Settings closed on the
first click, that the popups never appeared in screenshots, and that you should
not burn more than one attempt on them. That was wrong, and it cost a session
real time. The likely origin is a session whose own tooling had no desktop
screen control writing its limitation down as a property of Ableton. **Check
what your session can actually drive before concluding the application refuses
it**, and do not record a one-session failure as an application fact.

The `.als` patch below is still worth keeping: `ableton-mcp` cannot write
routing, arm or solo (see below), so a session with no desktop screen control
has no other route. It is no longer the first thing to reach for.

To change routing, arm, or solo by patching the set instead:

1. `cmd+s`, and verify File → Save Live Set is greyed out.
2. Copy the `.als` into `Backup/` with a descriptive name.
3. Patch the XML with a short python read-modify-write on the device:
   `gzip.open` → `str.replace` scoped to the one `<AudioTrack Id="N">` block
   → `gzip.open(..., "wb")`.
4. Reload: click **File**, `Down`×3 to "Open Recent Set", `Right`, `Return`
   on the first entry (the current set). Live reloads from disk without a
   prompt; the input meters light up immediately if routing is right.
5. Re-check plugin state — it can come back different after the reload.

Reloading from the shell also works: `open -a "Ableton Live 12 Suite"
"<set>.als"`. If the set currently open has unsaved changes, Live prompts,
and **Save is the default button** — Return saves the old set (Live writes a
copy into that project's `Backup/` first). That is how the capture set's
Ext. In 4 routing fix got committed on 2026-09-08 without anyone choosing to
save it. Decide before pressing Return, and note in the new project's README
what the prompt committed.

### Stripping clips from a set (building a new set from an old one)

Copying a set and deleting its clips by XML is fine only in Live's own form.
Learned 2026-09-08 building the measurement set from a capture set that held
968 take-lane clips pointing at the other project's samples:

- Removing every `<AudioClip>` / `<MidiClip>` but leaving each
  `<TakeLane Id="n">` in place with an empty `<ClipAutomation>` makes Live
  12.4.5 segfault (EXC_BAD_ACCESS at 0x0) while "Loading document". The
  crashed variant is kept in the measurement project's `Backup/`, labelled.
- What loads: per track, replace the whole `<TakeLanes>…</TakeLanes>` block
  with `<TakeLanes><TakeLanes /><AreTakeLanesFolded Value="true" /></TakeLanes>`,
  collapse `<ArrangerAutomation><Events>…</Events>` to `<Events />`, and write
  each session slot as `<ClipSlot><Value /></ClipSlot>`. That is exactly what
  Live writes after a delete. Routing, arm, monitor and Speaker patches on
  the same pass are safe.
- Keep the previous `.als` in `Backup/` before every patch, reload with
  `open -a`, and confirm the Live process is still alive before trusting the
  file. Confirm the result with a parse: zero `<TakeLane`, zero
  `<AudioClip`, and the three routings above.

### Screen control is one session at a time

`request_access` returns "Computer use is in use by another Claude session
(<id>)" when a second session tries to drive the desktop. Nothing in that
session can open Settings, the routing choosers, or Cortex Control until the
first one exits or finishes. The log and `.als` checks above still work, so do
those, report which session holds the screen, and stop rather than looping on
the request.

`ableton-mcp` cannot read or set input routing, monitoring, or the audio
device, and it cannot **set** arm, solo, or mute either — verified against the
installed build 2026-08-30, when a track needed arming and no tool existed.
`get_track_info` *reports* arm, solo and mute; the only writes on offer are
device parameters, device enable/disable, track volume, panning, and name.
Use it for state verification and device state, and the `.als` patch + reload
above for routing, arm, and solo — or ask the user, which is two clicks and
does not risk the plugin coming back in a different state.

`delete_track` does work (used 2026-09-08 to strip the capture set down to
its one capture track). Delete by name, one call at a time, and re-read the
track list between calls: Live renumbers unnamed default tracks as others go,
so after "1-MIDI" and "2-MIDI" are deleted the former "3-MIDI" is called
"1-MIDI", and a delete by the old name reports "No track named" rather than
removing the wrong one. Deleting a track drops its clip references only; the
WAVs stay in `Samples/Recorded/`. The change is unsaved until the user saves.

## thall amp normalized parameter mappings

`set_device_parameter` takes 0.0-1.0 and its response echoes a stale display
string, so always re-read with `get_device_parameters(show_all=true)`. Worked
out 2026-08-30 restoring the V4 reference after a preset had been loaded over
Mirar-Leo:

| Parameter | Normalized |
| --------- | ---------- |
| Amp Lo / Mid / Hi / Presence | `n = 0.5 + dB / 23.5` (0.5 = 0.0 dB) |
| Input Gain | `n = 0.5 + dB / 60` — inferred from one point (+2.4 dB = 0.54), unverified |
| Amp Drive, Tighten Chug, Tone Match Amount/Smooth | percent / 100 |
| Tighten Frequency | log; fitted from 51 Hz @ 0.19 and 362 Hz @ 0.60: `n = 0.6 + (log10(f) - 2.5587) / 2.0759`. 1.6 kHz = 0.9109, confirmed by read-back; the implied 20.6 Hz / 2.45 kHz endpoints are extrapolation |
| Tighten Gate off (-100 dB), Pitch Power off, Lo-Cut off | 0.0 |
| Hi-Cut off | 1.0 |
| Mono | 0.0 (Mono/Stereo Toggle) |

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
