# Lab history

Dated notes from the capture and measurement work on this rig: what was
tried, what it measured, and which incident set which rule. The current
rules live in `SKILL.md` and the runbooks; this file is the evidence behind
them and the state of the standing capture. When a project's
`CAPTURE-TEST-STATE.md` or README disagrees with this file, the project
file is newer.

## How the current capture rules were set

- **2026-09-11, the Ashen captures.** Three Neural Capture **V2** captures
  with the gate at −50 and everything else as played were all rejected by
  ear — thin, clanky, unamped — although "wind" measured ±0.9 dB, ESR 0.66,
  body coherence 0.68–0.71. The first capture with the gate at −100,
  otherwise untouched and made with **V1**, was accepted immediately. The
  user confirmed the gate-only rule that day; it superseded the
  "capture-safe" recipe (gate off, pitch off, mono) that V4 was made with.
  The two downloaded thall-amp captures the user rates highest are also V1.
- **Accepted-capture levels (2026-09-11).** RME In 4 gain 13 with plugin
  Input Gain +16.8 dB; In 4 tracked the QC In 1 meter at IN 1 LEVEL 0 dB to
  0.1 dB. An earlier note warned against a +17 Input Gain as "chasing
  meters"; the accepted capture disproved it. Both screenshots in
  `references/` were taken right before Start Capture on this capture.
- **Organic vs capture-safe (2026-09-05).** Brutal Death Thall captured as
  played read coherence 0.68–0.81 through the body, level with the
  capture-safe V2b of the same preset (0.67–0.77) and inside the spread two
  capture-safe draws of identical state showed. No organic penalty measured.

## Rig incidents

- **CAPTURE OUT input.** The 2026-08-23 capture that set the quality bar used
  RME **In 3** at gain +13. The cable moved to In 4 on 2026-08-24 for an
  experiment that measured worse, and In 4 became standard on 2026-08-25.
  In 4 is fine; the calibration (gain 13, Line, AutoSet off) is what travels.
- **2026-09-01.** The Ableton playback row feeding QC In 2 was found at −∞
  in TotalMix, which would have captured silence.
- **2026-09-11.** In 4 was sending to Analog 1/2 at −3.7 dB while RME Out 1/2
  reached QC In 1; at gain 13 that loop oscillated (QC In 1 −7.8 dBFS with no
  guitar). Muting In 4 in the capture workspace is the fix.
- **2026-09-08.** The measurement set (`amp-sim-measurement Project`) was
  built from the capture set with every clip stripped, and verified: M0 /
  Track.8 PostFxOut / S1, all armed, nothing soloed, no take lanes, no clips.
  The same day a hand-off said "the measurement set is open", but Live had
  been relaunched and was showing the band's live template.

## Thall amp captures

### Capture-time state for V4 (the standing capture)

V4 is the factory preset **Mirar – Leo** with five deliberate changes. This
is the record of how V4 was made, not the current procedure — since
2026-09-11 only the gate changes (`SKILL.md`):

| Control | Mirar – Leo as shipped | V4 capture-time | Why |
| ------- | ---------------------- | --------------- | --- |
| Tighten Gate | −12 dB | **−100 dB** | a gate swallows the QC's own test signal |
| Pitch Power | On | **Off** | drops the pitch shifter's latency — and Thicken with it |
| Mono/Stereo Toggle | On (stereo) | **Off** (mono) | the capture loop is mono |
| Tone Matching Power | Off in the file | **On**, Amount 30%, Smooth 80% | Tone Lock kept the rig's own profile |
| Input Gain | +0.0 dB | **+2.4 dB** | level calibration into the plugin |
| Cab Power | On | On | an "Amp and Cab" capture |

Unchanged from the factory preset: Amp Drive 61%, Lo +0.0, Mid +1.9,
Hi +3.1, Presence +1.6; Tighten Chug 50% at 1.6 kHz; Low Dirt 0%; Lo-Fi,
Lo-Cut and Hi-Cut all Off; Output Gain +0.0.

**What is missing is on the QC, not in the capture.** Mirar – Leo ships
**Pitch Thicken at 17%** — an octave-down summed into the dry signal before
the amp, so it changes how the amp distorts, not just what sits under it.
V4's capture turned the Pitch section off, so the octave has to come back
as a **QC pitch block before the capture**, and the standing preset does not
have one — its Wham and Pitch Shifter blocks are bypassed. No recapture is
needed; enable the Pitch Shifter at **Coarse −12, Mix 17%**.

**Do not write a low-pass into that spec.** The QC Pitch Shifter block has
exactly three parameters — **Mix, Coarse, Fine** — and no wet-path filter, so
there is nowhere on it to put the plugin's Pitch Hi-Cut (10.0 kHz in Leo, read
from the preset file). An EQ dropped on the same row to supply it filters the
**whole** signal into the capture, not the octave: a handoff spec of "−12 st,
mix 17%, low-pass 270 Hz" applied literally would have hung a 270 Hz brick
wall across the entire guitar. Filtering only the shifted voice needs a
Splitter → [pitch block + EQ] and dry → Mixer. Leo's Hi-Cut is near full range
anyway, so a bare single-row pitch block is a small error here — but say
"close, not exact". See `references/thall-amp-plain-language-guide.md`.

### Capture history and verdicts

| Version | What it was | Verdict |
| ------- | ----------- | ------- |
| V1 | First Monomythic capture, Chug 50 | Superseded; had the 60–120 hole |
| V2 | Hotter capture input | **Rejected** — proved hotter input makes the hole worse, plus 1 kHz+ fizz |
| V3 | No notes kept | **Rejected** — +10–15 dB sub, rolled off above 2 kHz, coherence 0.29 |
| V4 | "Thall Mirar Leo Amp and Cab", Chug 50 | **STANDING CAPTURE.** Sounds right, measures well everywhere Chug allows |
| V5 | "…Amp and Cab NoCh", Chug 0 | **Rejected by ear** despite being the best-measuring capture made here |
| Ashen ×3 (2026-09-11) | Ashen preset, **Neural Capture V2**, gate at −50, otherwise as played | **Rejected by ear** — thin, clanky, unamped — although "wind" measured ±0.9 dB, ESR 0.66, body coherence 0.68–0.71 |
| Ashen (2026-09-11) | Ashen preset, **Neural Capture V1**, gate −100, nothing else changed | **Accepted immediately.** Established the gate-only rule and the V1 rule |

Keep V5 on the unit. It is the proof of the Chug hypothesis and the reason
the 60–120 item is closed.

V1's source preset, **Jesse Zuretti – Monomythic**, is worth knowing about:
it runs Chug at 100% at 51 Hz, Drive 100%, and a 48 kHz tone profile at
Amount 100% that Tone Lock prevented from loading. Chug at 100% right in the
band that later became "the 60–120 hole" is the whole story of V1.

### The standing preset ("1D Thall Experimental")

- Capture block: **Thall Mirar Leo Amp and Cab** (V4), Gain 0.0,
  Bass/Mid/Treble 0.0, **Volume +6.0**
- Parametric-3 **active**: band 1 Peak **350 Hz Q1.00 +2.5 dB**, band 2
  **HPF 55 Hz Q0.71**, band 3 hi shelf **0.0** (zeroed — it was V1's fix and
  pulled V4's flat top down ~0.5 dB)
- IR Loader and Reverb **bypassed**; lane output **0.0**, Multi Out with
  USB Output 3/4 enabled

The makeup is on Volume, not Gain: `SKILL.md`, "The user's instrument".

### Known-good measured envelope (V4 vs the real amp at Chug 50)

Best measurement to date, 2026-08-30 16:54 take, 67.6 s continuous:

| Band | Delta | Coherence |
| ---- | ----- | --------- |
| Level offset | **+0.01 dB** | — |
| 60–120 | **−3.7** (expected — Chug) | 0.51 |
| 120–250 | +1.2 | 0.79 |
| 250–500 | +0.7 | 0.84 |
| 500 Hz–1 kHz | +0.4 | 0.80 |
| 1–2 kHz | −0.2 | 0.60 |
| 2–8 kHz | −0.1 to +0.0 | 0.14 – 0.36 |
| 8–12 kHz | −0.6 | 0.05 |
| Null | **−3.0 gain / −4.1 linear EQ** | — |

A later take that measures materially worse than this between 250 Hz and
8 kHz means something drifted — reverb un-bypassed, lane output moved, wrong
capture loaded, or the plugin left on a different preset — not that the
capture degraded.

### What is closed, and what is still open

**Closed:** the 60–120 Hz deficit. Cause identified (Chug is dynamic and
unmodellable), hypothesis confirmed by V5, control take rules out the
reference as an explanation. V4 plus the standing preset is finished at
rung 3, measured.

**Open:**

1. **The standing preset is missing Leo's octave.** Mirar – Leo ships Pitch
   Thicken at 17% and V4's capture excluded it, but the QC pitch block that
   should replace it is bypassed. Enable the Pitch Shifter at
   **Coarse −12, Mix 17%**, before the capture block, then A/B against the
   plugin with its pitch section on. **No low-pass on that row** — the block
   has only Mix/Coarse/Fine, and an EQ beside it filters the dry signal too
   (see the note above). A preset edit, not a recapture.
2. **Does Pitch Power off also bypass Low Dirt?** The UI files Low Dirt
   under the pitch section. It has not mattered — every capture so far used
   Low Dirt 0 — but 37 of 54 installed presets have it above zero. Set Low
   Dirt to 100, toggle Pitch Power, listen.
3. A **Chug 25** capture, only if curiosity strikes. A two-point
   dose-response now exists, so it should land between V4 and V5 on both
   coherence and delta. The only question is whether the feel survives — and
   "100% does not sound right" at Chug 0 is not encouraging.
4. Capture at Chug 0 (which models the static amp beautifully) and reproduce
   the dynamic Chug behaviour with a QC dynamics block after the capture.
   Splits the problem along the line the measurement drew. Unproven, and
   matching Chug by ear would be its own project.

Do not reopen the 60–120 item by any other route.
