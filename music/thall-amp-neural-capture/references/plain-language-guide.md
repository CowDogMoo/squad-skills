# thall amp in plain language, and where each control ends up on the QC

Two columns for every control: what it means in ordinary guitar terms, and
what has to happen to it for a Quad Cortex capture to sound like the preset.

The exact ranges, defaults and the plugin's own wording are in
`control-reference.md`. This file is the translation.

## The three buckets

Everything on the plugin lands in one of three places. Sort a preset into
these before capturing it and the capture will sound like the preset; skip
this and it will not.

1. **Baked in** — set it correctly *before* you press Start Capture and the
   QC reproduces it for free. Change it afterwards and you have to recapture.
2. **Rebuilt on the grid** — a QC block does this job, so turn it off in the
   plugin for the capture and add the block to the preset.
3. **Lost** — no static model reproduces it. Capture it as played, expect the
   measured deficit, and do not chase it with EQ.

| Bucket | Controls |
| ------ | -------- |
| Baked in | Input Gain, Tone Matching (Power/Amount/Smooth), Low Dirt, Amp Drive/Lo/Mid/Hi/Presence, the cab, Lo-Cut, Hi-Cut, Lo-Fi |
| Rebuilt on the grid | Tighten Gate, Pitch Whammy, Pitch Thicken (+ its Hi-Cut and Parallel switch), Output Gain |
| Lost | Tighten Chug and Tighten Frequency |

## Global

**Input Gain** — *how hard you are hitting the front of the amp.* Same job as
rolling your guitar volume up, or a clean boost in front of a head. Up: more
saturation, more compression, more low-end bloom, less pick definition.
→ **Baked in.** It is the single most important capture-time setting, because
it decides how hard the model is driven. The plugin's **Auto Gain** button
sets it for you — click it and play hard for five seconds.

**Output Gain** — *master volume.* Changes loudness, not tone.
→ Leave at 0.0 for the capture and make up level on the QC capture block's
**Volume**, never its Gain.

**Power** — *the amp's on/off switch*, inside the plugin. Separate from the
DAW's bypass, which the plugin calls Host Bypass and Live shows as **Device
On**.

**Mono/Stereo Toggle** — *one speaker or two.* → Set **Off** (mono). The
capture loop is mono, and a stereo source is not what the QC is listening to.

## Tone Matching — "make my guitar sound like the guitar this was built on"

**Tone Matching Power / Amount / Smooth** — a correction EQ applied to your
*input*, learned by playing for five seconds. Amount is how much of that
correction gets applied. Smooth is how broad the correction curve is — low
values chase every peak and dip in your pickup's response, high values only
follow the general shape.

→ **Baked in, and guitar-specific.** A capture made with a profile active
carries that profile's EQ forever, tuned to one guitar. That is fine if it is
your guitar; it is a permanent mismatch if it came from someone else's.

Two traps live here, both covered in `SKILL.md`: **Tone Lock** stops presets
from loading their own tone-match settings, and the UI reading **"No Tone
Profile"** means nothing is loaded no matter what the Amount knob says.

## Shape — the tightening section

**Shape Power** — *the tightening section on/off.* Bypasses the gate and Chug
together, which is why the gate gets silenced with its own knob instead.

**Tighten Gate** — *noise gate threshold: how loud you have to play before
the amp lets sound through.* −100 dB never gates. −12 dB, the top of the
range, gates hard and will cut quiet notes and tails off.
→ **Rebuilt on the grid.** Set it to −100 dB for the capture — a gate
swallows the QC's own test signal — and put the gating back with the preset's
**input block gate** or a **Utility → Adaptive Gate** before the capture
block. The numbers do not transfer (the QC's gate is a percentage, the
plugin's is a dB threshold), so dial it by ear against the plugin.

**Tighten Chug** — *how percussive the palm mutes are.* The plugin's own
words: "more emphasis on pick attack". This is the djent knob — it makes
chugs pop and separate rather than blooming into each other. At 0 the
processing is off and you have a plain amp; at 100 the attack is the loudest
thing in the note.
→ **Lost.** It follows the playing, and a Neural Capture is frozen in time.

**Tighten Frequency** — *how far up the guitar's range the tightening
reaches.* Low (50–250 Hz) works on the boom, for thick chunky low chugs.
High (1–2.5 kHz) works on the pick noise instead, which is what the plugin
means by "scrape-y".
→ **Lost with Chug**, since it only shapes what Chug does.

Whether Chug lifts the attack or ducks what follows it has not been measured
here — only its effect on the capture has. If it matters, one render of the
same DI at Chug 0 and Chug 100 through the plugin, compared as envelopes,
settles it in ten minutes.

## Pitch — whammy, octave, and the fuzz that lives with them

**Pitch Power** — *the octave/whammy section on/off.* Also takes Low Dirt's
neighbourhood with it; whether it mutes Low Dirt itself is untested and is
open item 2 in `SKILL.md`.

**Pitch Whammy** — *a pitch shifter on the whole signal*, ±24 semitones.
−12 is an octave down, +12 an octave up. It transposes rather than blending.
→ **Rebuilt on the grid**, with a **Wham** or **Pitch Shifter** block before
the capture. Six factory presets use it.

**Pitch Thicken** — *blend a bass guitar in underneath your riff.* An octave
below, mixed with the dry signal: 0% is dry only, 100% is the octave only.
→ **Rebuilt on the grid**, and read the Parallel switch first — it decides
*where* on the grid.

**Pitch Hi-Cut** — *how much treble that added octave keeps.* Down at
100–300 Hz the octave is a subby rumble under the riff. Up near 10 kHz it is
a full-range octave that argues with the guitar.
→ Rebuilt with the octave — but **not on the pitch block**, which carries only
Mix, Coarse and Fine and has no filter of its own. On a single row you cannot
low-pass only the octave: an EQ next to the pitch block low-passes the dry
guitar and everything else feeding the capture with it. An exact rebuild needs
a **Splitter → [pitch block + EQ] and dry → Mixer** into the capture. A
single-row pitch block gets you close, not exact — and a Hi-Cut value copied
from the plugin into a single-row spec is how a preset gets wrecked.

**Thicken Amp Parallel** — *does the octave go through its own amp, or get
mixed into your guitar before the amp?* Off (the common case) means the
octave is summed in **before** the distortion, so it drives the amp and
changes the whole character, not just what sits underneath. On means a
separate amp channel alongside.
→ Off: the pitch block goes **before** the Neural Capture. On: it needs its
own row with its own capture, joined by a mixer.

**Pitch Cleanse** — *when the whammy moves, mute the octave and the fuzz
automatically.* A performance convenience for automation, nothing else.

**Pitch Latency** — *line the dry signal up with the octave so the attack
does not smear.* On is tighter and delays everything a little. It matters for
measurement too: if it is on in the plugin and nothing on the QC matches it,
the two are not time-aligned.

**Low Dirt** — *a fuzz blended in underneath the amp.* Aggressive
pre-distortion, mixed in by percentage. 37 of the 54 installed presets use
it.
→ **Baked in.** It is static, which is what a capture is good at.

## Amp

**Amplifier Power** — *amp section on/off.*

**Amp Drive** — *the gain knob.* How much distortion.

**Amp Lo / Mid / Hi** — *the tone stack:* bass, mids, treble, ±12 dB each.

**Amp Presence** — *the bite and air knob* on top of the treble.

→ All five are **baked in**, and this is the part a Neural Capture is
genuinely excellent at. Leave the QC capture block's own Gain and
Bass/Mid/Treble at 0.0 — they are not these knobs, and its Gain changes how
hard the model is driven.

## Cab

**Cab Power** — *the speaker cabinet on/off.* There is one internal cab, and
it cannot be exported.
→ On: capture as **"Amp and Cab"** — the only way to keep this cab. Off:
capture as **"Amp"** and put an **IR Loader** after the capture block.

A preset may also have a third-party IR loaded, stored as an absolute file
path. Eleven factory presets point at files that are not on this machine and
silently fall back to the internal cab — list in `factory-presets.md`.

## Output stage

**Lo-Cut** — *roll off the bass, gently.* First order, 6 dB per octave, so a
tilt rather than a cliff. Displays "Off" at the bottom of its travel.

**Hi-Cut** — *roll off the treble and fizz.* Second order, 12 dB per octave —
twice as steep as Lo-Cut. Displays "Off" at the top of its travel.

→ **Baked in.** A capture reproduces both slopes less steeply than the plugin
does, so if a preset leans on them, expect the QC to be a little bassier and
fizzier than the plugin and correct it with a **Parametric-3** after the
capture. Separately, and regardless of where Lo-Cut sits, a high-pass on the
QC side is always worth having: the capture carried +22 dB at 30–45 Hz that
the plugin did not.

**Lo-Fi** — *a filter that makes it sound small, cheap and telephone-y.*
Described as a filter, so it should capture, but nothing here has tested it.
One installed preset uses it.

## Not knobs, but they will ruin a session

**Tuner Auto-Mute** — *mute the signal while the tuner is open.* On by
default. A tuner left open feeds the capture loop silence.

**Tone Lock** — *keep my tone-match and my input gain when I change presets.*
On for this rig. See `SKILL.md`.

**Auto Gain** — *set my input gain for me.* Sets a baked-in parameter, so run
it before a capture and never between a capture and its measurement take.

## The order it all goes back together on the grid

```text
Input (gate)  →  Wham / Pitch Shifter  →  Neural Capture  →  IR Loader
              →  Parametric-3  →  modulation  →  delay  →  reverb  →  Multi Out
```

The pitch block sits **before** the capture because that is where Thicken
sits in the plugin when Thicken Parallel is off. The IR Loader is bypassed or
empty for an Amp-and-Cab capture. This is the canonical order from
`quad-cortex-preset-editing`; keep it so switching between an amp-only and an
amp-and-cab capture is one block change.

## What "sounds like the preset" can actually mean

Three honest outcomes, worth naming before starting:

- **Everything but Chug.** The realistic target for most presets. Bake the
  static side, rebuild gate and octave on the grid, accept the Chug deficit
  and record it. This is what the standing V4 capture is.
- **Everything, including the feel** — only for the two presets with no
  dynamic control running at all (Drewsif – Air On Marshall, Mirar – Marius).
- **Chug rebuilt separately** — capture at Chug 0, which models the static
  amp beautifully, then approximate Chug with a QC **Compressor** (fast
  attack, quick release) or a dynamic **Filter** block before the capture.
  Untested, and the one time Chug 0 was captured the result was rejected by
  ear, so this is a project rather than a recipe.

Whichever you pick, say which one you reached. The claim ladder in
`quad-cortex-capture-measurement` is the vocabulary for that.
