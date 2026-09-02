# TotalMix routing for a plugin capture

The return path is what breaks a plugin capture. Anything other than the
plugin's output reaching QC Input 2 sums with the model and the capture is
garbage. These settings exist to guarantee that.

## Input receiving CAPTURE OUT (In 4)

- **Inst. OFF** (line mode), reference level **+13 dBu** (front 3/4 offer only
  +13/+19), **AutoSet OFF**, no EQ or dynamics, FX send −∞.
- Gain **+13 dB** was the calibrated value that landed the capture signal at
  DI-realistic levels (~−15 dBFS peaks) in Ableton. Recalibrate against the
  meters rather than trusting the number.

## Output feeding QC In 2 (Out 3 or 5)

- In that output's mix: **only the Ableton playback channel at 0.0 dB, every
  hardware input row at −∞.** A hardware input leaking into the return output
  sums dry signal with the plugin. This is the single most common
  plugin-capture killer.
- Hardware output fader at 0 dB — check it, since snapshots leave it at −∞.
  Reference +13 dBu, Loopback OFF, FX Return −∞.
- **Check the other software playback rows in the same submix.** A workspace
  was found with playback **Analog 1/2 at −9 dB inside the Analog 3/4
  submix**: Ableton's Main — carrying the monitored dry capture signal and the
  REC track's plugin output — was summing into the return alongside the real
  Ext. Out 3 feed. Same failure as a hardware-input leak, different row.
  Mute or −∞ every playback row except the one Ableton track output, and
  unmute afterwards; it is the user's monitoring. Removing that leak dropped
  the capture wizard's In 2 meter from −8.4 to −13.0 at the same In 2 level.

## Which strip is which on this rig

The playback and hardware-output strips carry custom names that do not say
which channel they are, and picking the wrong one is the difference between a
capture and silence. Read 2026-09-01:

| Strip | Channel | Carries |
| ----- | ------- | ------- |
| "Computer Ou" | software playback 1/2 | Ableton's **Main** — the leak row |
| "Music Out" | software playback 3/4 | Ableton's **Ext. Out 3** — the plugin feed to QC In 2 |
| "Vox Out" | software playback 5/6 | |
| "Phones" | software playback 7/8 | |
| "Main" (right, control room) | hardware output Analog 1/2 | |
| "Analog 3/4" | hardware output Analog 3/4 | the output feeding QC In 2 |

Click the **Analog 3/4** hardware output strip to put every other strip into
that submix; each strip's send value then reads at the bottom of the strip.
Check both rows — hardware inputs and software playback — every strip.

## The other half of the check: the Ableton row must be UP

The leak check above is only half of it. On 2026-09-01 the Analog 3/4 submix
had every hardware input at −∞ (clean), "Computer Ou" leaking at −11.9 dB,
**and "Music Out" at −∞** — so nothing from the plugin reached QC In 2 at all.
A capture started in that state records silence for 2–3 minutes and then
spends another 3–5 minutes training on it before anything looks wrong.

Verify both, every session: the wrong rows down **and** the Ableton track's own
playback row up.

## Keep a capture workspace

The workspace loaded on 2026-09-01 was "Loud Fucking Vocals", and none of the
seven entries in File → Open Recent was a capture one — which is why this
routing gets rebuilt by hand every session and why a vocals workspace can
silently undo it. Once the levels are dialed, **File → Save Workspace As
"capture"**, and load that first thing in every capture session.

## Input receiving the QC's normal output (In 3, for A/B recording)

Inst OFF, +13 dBu, gain 0, AutoSet OFF. The QC's main out is far hotter than
its Capture Out.

## Driving TotalMix without clicking pixels

TotalMix has OSC and MIDI remote control, and OSC is already configured on
this rig: `Options → Enable OSC Control`, slot 0 set to own port 7001, remote
host 127.0.0.1, remote port 9001, 8 channels per bank. Checked 2026-08-31 it
was configured but not switched on — the process held no UDP socket — and UDP
9001 was occupied by another process, so the reply path needs that freed or
the port changed first. Every fader, gain, Inst, AutoSet and mute is
addressable this way. Nothing in this corpus ever used it, which is why the
older notes are full of pixel-drag calibration.

**Faders and knobs both take `computer_left_click_drag`** (2026-09-01, a
session with no click offset). Riding a send down to −∞ by dragging its fader
works, and so does the input gain knob. Every "TotalMix faders/knobs don't
respond" note in this project's history was the click-offset session bug or a
stray Data Edit Window swallowing the input — not this app and not this rig.
Diagnose both before writing a control off.

For a one-off exact value, double-click the control and use the Data Edit
Window — see `quad-cortex-plugin-capture`, "Screen control during a capture".
That works on a **knob**. On a **fader's** dB value text it does not: on
2026-09-01 a double-click there opened no editor and toggled TotalMix's Info
View instead. Drag the fader for that case, or mute the channel. Buttons —
Inst, AutoSet, channel M, hardware-output strip select — take clicks
normally.

Two more mechanics worth not rediscovering:

- **TotalMix menus do not close on Escape.** Click outside the menu instead.
- `computer_resolve_access` resolves this app as **`Totalmix`** (bundle
  `de.rme-audio.TotalmixFX`). "TotalMix FX" does not resolve.

## If the input gain knob will not take screen control

The knob normally **does** take screen control — `left_click_drag` and the
scroll wheel both (measured 2026-08-31 and 2026-09-01). An earlier note
presented refusal as the expected state; it is not. Check, in order:

1. **A stray Data Edit Window holding focus.** A double-click anywhere opens
   one, it appears away from the control, and it swallows everything aimed at
   the knob until dismissed. This is the most common cause.
2. **The click-offset session bug** in `quad-cortex-preset-editing`.

If neither explains it, put the same dB into the plugin's Input Gain via
`ableton-mcp` (`set_device_parameter`, param 3 on the thall amp;
+2.4 dB = 0.54, +15.4 dB = 0.7567), then reset it before the measurement take.
It is equivalent pre-nonlinearity gain.

## Snapshot warning

Loading any TotalMix snapshot or workspace silently reverts all of the above —
Inst modes, gains, AutoSet, output faders. Re-verify every setting after any
snapshot change, and again before each capture session.
