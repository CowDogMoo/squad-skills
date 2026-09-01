# thall amp — every control, and what a Neural Capture does with it

Odeholm Audio "thall amp", version **1.0.4**. Descriptions are the plugin's
own tooltip text (hover any control to see them in the UI). Ranges and
defaults are the plugin's published parameter info, read with
`auval -v aufx Th4m OdAu`. The index column is the position in Ableton's
parameter list, which is what `ableton-mcp` addresses.

The plugin exposes **30 automatable parameters**. Live shows 30 entries but
the first is the plugin's Host Bypass surfaced as Live's own **Device On**
switch — there is no separate Host Bypass row, and toggling Device On writes
`host_bypass` in the preset file.

## Signal chain

    in -> Input Gain -> Tone Matching -> Shape (Gate, Chug)
       -> Pitch (Whammy, Low Dirt, Thicken) -> Amp -> Cab
       -> Lo-Cut / Hi-Cut / Lo-Fi -> Output Gain -> out

Five section power switches sit on that chain: **Tone Matching Power**,
**Shape Power**, **Pitch Power**, **Amplifier Power**, **Cab Power**. Each
bypasses everything in its section, which is the part that catches people
out — see "Section switches are blunt" below.

## Global

| # | Control | Range | Default | What it does | Capture |
| - | ------- | ----- | ------- | ------------ | ------- |
| 1 | Host Bypass (Live's "Device On") | Off/On | Off | Host-side bypass. | n/a |
| 2 | Power | Off/On | On | "Powers or bypasses the plugin." Separate from Device On; when off the UI shows "Click anywhere to unbypass". | Must be On |
| 3 | Input Gain | −30…+30 dB | +0.0 | "Sets the input gain level." | **Baked in** — it sets how hard the amp is driven |
| 4 | Output Gain | −30…+30 dB | +0.0 | "Sets the output gain level." | Loudness only; safe to change |
| 30 | Mono/Stereo Toggle | Off/On | On | Off = mono, On = stereo. | Set **Off**; the QC capture loop is mono |

Next to Input Gain in the UI is **Auto Gain**: "Click and play hard for 5
seconds to have the plugin automatically set your input gain." It is the
plugin's own version of the level calibration in
`quad-cortex-plugin-capture`, and it moves a parameter that gets baked into
the capture — so run it *before* the capture, never between the capture and
a measurement take.

## Tone Matching

| # | Control | Range | Default | What it does |
| - | ------- | ----- | ------- | ------------ |
| 6 | Tone Matching Power | Off/On | On | "Powers or bypasses the tone matching section." |
| 7 | Tone Matching Amount | 0–100% | 30% | "Adjust the strength of the correction EQ applied to your input." |
| 8 | Tone Matching Smooth | 0–100% | 80% | "Smooths the response of the tone match correction filter." |

Tone Matching is **not an amp EQ**. Tone Match: "Click and play for 5
seconds to have the amp learn the spectral response of your guitar" — it is
a correction filter on the *input*, derived from one guitar. A capture bakes
in whichever profile was active, so a capture made with a profile is
specific to the guitar that profile was learned from.

Three buttons live with it, none of them automatable:

- **Tone Lock** — "When locked, prevents tone match and input gain
  parameters from changing when switching presets." Read the trap in
  `SKILL.md`; it is the single biggest reason a preset does not sound the
  way its file says it should.
- **Save / Reset Tone Profile** — writes or clears a `.odtp` file in
  `~/Library/Odeholm Audio/thall amp/Tone Match Presets/`. A profile stores
  the sample rate it was learned at; both profiles on this rig say 44100
  while the capture and measurement sessions run at 48 kHz. Whether that
  matters is untested — re-learn at 48 kHz if you want to remove the
  question.
- The profile name shows in the UI. **"No Tone Profile" means nothing is
  loaded**, whatever the Amount knob says.

## Shape (gate and chug)

| # | Control | Range | Default | What it does |
| - | ------- | ----- | ------- | ------------ |
| 9 | Shape Power | Off/On | On | "Powers or bypasses the shape section." |
| 10 | Tighten Gate | −100…−12 dB | −50 | "Adjusts the threshold of the noise gate. Higher values result in more aggressive gating." |
| 11 | Tighten Chug | 0–100% | 50% | "Adjusts the strength of the chug processor. Higher values put more emphasis on pick attack. Processing is disabled at 0." |
| 12 | Tighten Frequency | 20 Hz…2.5 kHz | 250 Hz | "Adjusts the cutoff for chug processing. Higher values result in a more 'scrape-y' sound." |

The gate's parameter range stops at **−12 dB**, and −100 dB is fully off.
Normalized-to-dB is not linear here (−30 dB reads as normalized 0.61, not
0.795), so write the gate by its dB display and read it back rather than
computing a normalized value. Normalized **0 is −100 dB**, which is the one
value the capture workflow needs.

"Emphasis on pick attack" is the whole story for why Chug cannot be
captured: emphasis that follows the attack is a function of time, and a
Neural Capture is a static model. See `SKILL.md`.

## Pitch (and Low Dirt)

| # | Control | Range | Default | What it does |
| - | ------- | ----- | ------- | ------------ |
| 13 | Pitch Power | Off/On | On | "Powers or bypasses the pitch section." |
| 14 | Pitch Whammy | −24…+24 st | 0.0 | "Pitch shifts the incoming signal. Shift-Click and drag to trim the pitch in between semi-tone increments." |
| 15 | Pitch Thicken | 0–100% | 20% | "Adds a lower octave in parallel with the dry signal. Adjusts the mix % between the dry signal and lower octave. 0% is fully dry and 100% solos the parallel octave." |
| 16 | Pitch Hi-Cut | 20 Hz…20 kHz | 10 kHz | "Adjusts a low-pass filter applied to the parallel octave." |
| 17 | Pitch Cleanse | Off/On | Off | "When cleanse is enabled, low-dirt and thicken will be disabled when whammy is not at 0. Useful for creative automation moves." |
| 18 | Pitch Latency | Off/On | Off | "Compensates the dry signal for latency introduced during pitch shifting. Improves the time alignment between the dry and thicken signal." |
| 19 | Thicken Amp Parallel | Off/On | Off | "When enabled, the parallel octave runs through a separate amp chain. When disabled, it's combined with the dry direct signal before to the amp." |
| 20 | Low Dirt | 0–100% | 0% | "Adds an aggressive pre-distortion to the input. Higher values increase the mix percentage. Processing is disabled at 0." |

Whammy and Thicken both generate pitch material. Nothing a static model
learns can reproduce them, so a capture of a preset using either is a
capture of something else.

**Low Dirt is the odd one out.** It is a static pre-distortion, exactly the
kind of thing a Neural Capture models well — but the UI files it under the
pitch section (its tooltip sits between Pitch Power and Whammy, and its
parameter index falls inside the pitch block). Whether Pitch Power off also
bypasses it is **untested**. It has not mattered on this rig because every
capture so far used Low Dirt 0, but 37 of the 54 installed presets have it
above zero. Test before capturing one of those: set Low Dirt to 100, then
toggle Pitch Power and listen.

Pitch Latency matters for measurement, not just tone: it delays the dry path
to line up with the shifted path. If it is on in the plugin and the capture
has no equivalent, the two are not time-aligned.

## Amp

| # | Control | Range | Default | What it does |
| - | ------- | ----- | ------- | ------------ |
| 21 | Amplifier Power | Off/On | On | "Powers or bypasses the amp section." |
| 22 | Amp Drive | 0–100% | 50% | "Adjusts the amount of distortion." |
| 23 | Amp Lo | −12…+12 dB | +0.0 | "Boosts or cuts the low end of the amp output." |
| 24 | Amp Mid | −12…+12 dB | +0.0 | "Boosts or cuts the mid frequencies of the amp output." |
| 25 | Amp Hi | −12…+12 dB | +0.0 | "Boosts or cuts the hi frequencies of the amp output." |
| 26 | Amp Presence | −12…+12 dB | +0.0 | "Boosts or cuts the presence frequencies of the amp output." |

All five are static and capture cleanly. This is the part of the plugin a
Neural Capture is actually good at.

## Cab

| # | Control | Range | Default | What it does |
| - | ------- | ----- | ------- | ------------ |
| 27 | Cab Power | Off/On | On | "Powers or bypasses the cabinet secction." |

There is **one** internal cab. "Cab Load" swaps in a third-party IR, "Cab
Remove" resets "back to the default cabinet", and the loaded IR's path is
stored in the preset as an absolute path — which is why presets from other
people can arrive pointing at a file that does not exist on this machine.
See `factory-presets.md`.

Cab Power decides the capture type: **off → capture as "Amp"** and put an IR
after it on the QC; **on → capture as "Amp and Cab"**, which is the only way
to keep this cab, because it cannot be exported.

## Output stage

| # | Control | Range | Default | What it does |
| - | ------- | ----- | ------- | ------------ |
| 5 | Lo-Fi | Off/On | Off | "Adds a lo-fi effect filter on the output." |
| 28 | Lo-Cut | Off (20 Hz)…20 kHz | Off | "Adjusts a first order highpass filter applied to the amp's output." |
| 29 | Hi-Cut | 20 Hz…Off (20 kHz) | Off | "Adjusts a second order low pass filter applies to the amp's output." |

Lo-Cut is **first order** (6 dB/oct) and Hi-Cut is **second order**
(12 dB/oct). Both display "Off" at the far end of their travel rather than
having a bypass. A capture reproduces these slopes less steeply than the
plugin does, which is the measured reason a high-pass on the QC side is
always worth having.

Lo-Fi is described as a filter, so it should capture, but nothing here has
tested it. One installed preset uses it (James Carey – Lofi Octave Vocal).

## Tuner

Not automatable, and it can ruin a session: **Tuner Auto-Mute** — "Enables or
disables automatically muting the input while the tuner is active" — is on
by default. A tuner left open mutes the plugin's input, so the capture loop
records silence and the QC trains on nothing.

## Section switches are blunt

Each power switch takes out everything in its section, and two of them are
easy to reach for by mistake:

- **Shape Power off** removes the gate *and* Chug. To silence only the gate,
  set Tighten Gate to −100 dB and leave Shape Power on.
- **Pitch Power off** removes Whammy, Thicken, Thicken Hi-Cut, Cleanse,
  Latency, and possibly Low Dirt. The capture workflow turns it off to drop
  the pitch shifter's latency, which is right when Thicken is 0 and wrong
  when it is not.

## State the preset file holds but the host cannot automate

`scripts/read_preset.py` surfaces these; they are in the file and not in the
parameter list: **Tone Lock**, **Thicken Solo**, **Tuner Auto-Mute**, the cab
IR path, the embedded tone profile (with the sample rate it was learned at),
and an LFO/modulation table with one entry per parameter. Every installed
preset leaves the modulation table unassigned, and no tooltip mentions an
LFO, so treat those bytes as inert unless something proves otherwise — but a
modulated parameter would be time-varying, and therefore uncapturable, in
exactly the way Chug is.

## Licensing

The binary carries the string "Trial has ended, a timed noise will be added
to the output." An unlicensed instance injects noise, and a capture would
model it. Confirm the licence is live before a capture session.
