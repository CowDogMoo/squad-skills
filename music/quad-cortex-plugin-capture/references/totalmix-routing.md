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

## Input receiving the QC's normal output (In 3, for A/B recording)

Inst OFF, +13 dBu, gain 0, AutoSet OFF. The QC's main out is far hotter than
its Capture Out.

## When the input gain knob will not take screen control

Put the same dB into the plugin's Input Gain via `ableton-mcp`
(`set_device_parameter`, param 3 on the thall amp; +2.4 dB = 0.54,
+15.4 dB = 0.7567), then reset it before the measurement take. It is
equivalent pre-nonlinearity gain. The click-offset conditions under which the
knob refuses every drag form are described in `quad-cortex-preset-editing`.

## Snapshot warning

Loading any TotalMix snapshot or workspace silently reverts all of the above —
Inst modes, gains, AutoSet, output faders. Re-verify every setting after any
snapshot change, and again before each capture session.
