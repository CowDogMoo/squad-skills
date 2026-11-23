# Method: how each detector works, and its limits

## Contents

1. Reading the saved set
2. Exact placement check
3. Pair alignment check
3b. Section self-comparison
4. DI attack-envelope audit
5. Amp-render cross-check
6. Controls
7. Numbers from the reference song
8. Things tried and dropped

## 1. Reading the saved set (`alsio.py`)

A `.als` is gzipped XML. The scripts read:

- **The tempo map** comes from the Main (formerly Master) track's tempo
  automation: `FloatEvent`s in beats. Live ramps tempo linearly between
  breakpoints, and two breakpoints at the same beat form a step. The map is
  integrated on a 1/64-beat grid. On the reference song it matched a
  hand-built map to 0.00 ms over 416 beats (87, 60, 120, 110, 100, 90, 80
  and 72 BPM sections).
- **Arrangement audio clips** come from main-lane `AudioClip`s only (take
  lanes don't play). Each clip records `CurrentStart`/`CurrentEnd` (beats),
  `Loop/LoopStart` and `StartRelative` (the start marker), `LoopOn`,
  `Disabled` (muted), `IsWarped`, the warp markers (`SecTime`/`BeatTime`
  pairs), and the file. The file is the absolute `Path`, with a fallback to
  `RelativePath` from the set's folder.
- **Track indices** skip return tracks, which matches the index the
  AbletonMCP socket uses. A deactivated track (track activator off) and a
  muted clip don't sound, so they aren't analysed.
- **Clip time to file time:** a warped clip maps arrangement beat x to clip
  beat `loop_start + start_rel + (x - start)` (wrapping for looped clips),
  then to file seconds through the warp markers. That mapping is linear
  between markers and extrapolated with the first and last segments.
  Unwarped clips play in real time and keep their loop values in seconds.

## 2. Exact placement check (`placement_check.py`)

`anchor = start - (loop_start + start_rel)` is the arrangement beat where the
take's beat 0 lands. Group clips by track, file and identical warp markers.
Inside a group, copies moved by whole beats share `anchor mod 1`. The
reference fraction is the most common one; on a tie it's the one nearest the
beat grid. Any copy more than `--tol` (0.005 beat, 2.5 ms at 120 BPM) away is
flagged with:

- `off_beats`: the signed offset, converted to ms with the tempo at that point;
- `suggest_start`: the start that restores the group's fraction;
- the reference copies, so you can point at the evidence;
- notes: a repeated pattern (the same offset on several copies of one take),
  "nudged together" (the same offset on a neighbouring clip from another
  take), and ties.

Why group by warp markers: a re-warped slice maps audio to beats
differently, so its anchor isn't comparable with unwarped copies. In the
reference song, the bars 68-70 slice edit and two pickup slivers were
re-warped. Grouping by file alone flagged them as nudges, but they were
deliberate.

**Blind spots.** It can't see a take that's used only once, a slip shared
by every copy of a take, unwarped clips, or a whole-beat shift.

## 3. Pair alignment check (also in `placement_check.py`)

For each pair, every overlapping pair of clips (one take on side A, one on
side B) gets a relative anchor `anchor(A) - anchor(B) mod 1`. Wherever the
same two takes meet again (a repeated section built from copies), the
relative anchor should match. An occurrence that differs means one side
moved against the other: that is the flam, located exactly.

- **Reference:** the most common relative fraction. On a tie (often just two
  occurrences), the occurrence whose clips sit on their own takes' anchors
  wins, then the on-grid relation.
- **Who moved:** compare each side's anchor fraction with the same side in
  the reference occurrence. The side whose fraction changed moved. If both
  changed, the script says "decide by ear".

This is what makes the planted bar 90-91 case unambiguous. Jason's slice at
362.3125 is deliberately +0.0625 off its own take, both in bar 87 and in bar
91, so it pairs with Jayson consistently. Only Jayson's clips changed between
cycle 1 and cycle 3.

## 3b. Section self-comparison (`section_compare.py`)

When the suspect bars are a copy of earlier bars, a track's source audio over
the suspect section should match the same track's audio over the reference
section exactly. The script takes the attack curves on a 0.5 ms grid and
cross-correlates them within ±100 ms. Identical audio peaks near corr 1.0 at
the true shift, and periodicity can't produce a competing peak of the same
height, because it's the same signal. Both evaluation runs, with and without
the skill, invented this check on their own, so it's bundled.

- On the planted bar 90-91 nudge it reads Jayson +31.0 ms (corr 0.96) and
  Jason 0 ms (corr 1.00).
- On the unplanted set it reads 0 ms for both.
- Where the "copy" is really a different take (bar 88 Jason), corr falls to
  0.28 and the script says the shift is unreliable.

## 4. DI attack-envelope audit (`attack_audit.py`)

1. Each usable clip's source file becomes an RMS envelope on 2 ms frames, in
   dB. Anything below the gate (-25 dBFS) is set to -60 dB, or to 20 dB under
   the gate when the gate is lower than -40.
2. The envelope is placed on the song's time grid (500 Hz) through the warp
   markers and tempo map. Overlapping clips on one track take the maximum.
3. The attack curve is the positive part of the dB derivative, smoothed by a
   3 ms Gaussian. Pick attacks and gate openings dominate it.
4. Per clip, over the clip's own span, the partner's attack curve is
   cross-correlated with this clip's within ±25 ms. The peak gives the lag
   and the normalised correlation. A clip is measured if it's at least
   0.25 s long and both sides are above the gate for at least 5% of it.
5. Flag at |lag| >= 15 ms with corr >= 0.3. "edge" marks lags within one
   grid step of the window limit.

The overall lag per pair uses the clip-coverage overlap mask, not the
above-gate mask. Masking both curves with the same activity mask biases the
peak to 0 ms.

**Why -25 dBFS.** On the reference rig the amp's input gate sat at -25 dB and
the amp saturated anything above about -75 dBFS. Handling noise (-60 to
-90) and ringing strings (-12 to -25) would otherwise read as attacks.
Picked notes peak at -3 to -8 DI. Quieter DIs (peaks near -18) need
`--gate-db -40`; the script says so when a pair has no measurable clip.

**Why ±25 ms.** Dense 16th and 32nd riffs repeat every 125 and 62.5 ms. A
±40 ms window can lock onto the neighbouring attack. On 7- and 8-strings,
low notes (F#1 is about 46 Hz, a 22 ms period) add pitch-period ripple to a
2 ms RMS envelope, which shows as correlation peaks about 19 ms apart. That
is why a single audio method often contradicts the other, and why the
positive control is per region. The cost is that a slip larger than the
window (a 0.0625-beat nudge is 31 ms at 120 BPM) reads as "edge" with low
corr. A wider window measures it only while the window stays under half the
riff's shortest attack period; on the synthetic fixtures `--window-ms 45`
reads the planted 31 ms nudge as +32 ms at corr 1.00.

## 5. Amp-render cross-check (`render_xcheck.py`)

The same attack-curve machinery runs on what you hear: one rendered stem per
doubled track, placed at its render start beat. A later `--stem` overrides an
earlier one over its span, so you can re-render one section. The rendered
gate is -45 dB. Rows are matched with the DI rows by track and clip start.

**Agreed problem** (the only audio result worth acting on): both methods
give at least 15 ms, in the same direction, within 10 ms of each other.
**contradict**: both give at least 15 ms with opposite signs. This means
aliasing in at least one method, so listen.

## 6. Controls

Controls test two different failure modes: a known-clean negative control
checks false alarms, while injected positive controls check sensitivity. A
timing audit without both cannot distinguish a tight double from a detector
that cannot measure it. Execute controls with the audit's settings and retain
commands and measured results in GATES.md and the report.

- **Negative:** run placement and DI checks on a supplied known-clean set or
  independently established clean pair/region. Report flags and lags. Do not
  declare the reference clean merely because placement is silent: placement
  cannot see every audio slip. If a clean reference cannot be established,
  mark affected conclusions unconfirmed rather than manufacture a pass.

- **Placement: `--inject "TRACK@START+DELTA"`.** The script shifts that clip
  in a copy of the parsed data (the file isn't touched), requires the clip to
  be flagged with the injected offset, and requires the real state to be
  clean at that clip. It refuses whole-beat shifts, clips that are the only
  copy of their take, and clips that are already flagged. Choose a take with
  no flagged copies so the injection does not flip a suspect reference majority.
- **DI: `--inject`, the same way.** The clip's lag must move by about the
  injected ms within 6 ms. The injection magnitude must be at least half
  `--min-ms` (default 7.5 ms), and the absolute baseline-plus-injection lag
  must be strictly below `--window-ms - 1` (default 24 ms). Convert the beat
  delta at the clip midpoint tempo, as the script does. A shift cancelling
  an existing lag is valid; the final lag need not exceed the flag threshold.
  An out-of-window plant cannot establish sensitivity. Run per reported
  region, including the clean reference. A MISSED result means the DI method
  can't resolve that region.
- **Render: `--control-shift-ms`.** The script shifts the second side's stems
  and requires at least 80% of clips to follow. It lists the clips that don't
  follow as unresolvable.
- **Collateral:** run once with an incomplete allowed list (or none) to see
  that it fails.
- **Offline evals:** `evals/files/make_fixtures.py OUTDIR` generates gzipped
  XML parser fixtures and short synthetic attack signals without a source
  set. Cases cover +0.0625-beat nudges, a -20 ms placement slip, a +20 ms
  audio-only slip, deliberate slices, and a clean control. These sparse
  signals test placement and attack correlation; real guitar recordings,
  amp-render cross-checks, and Live edits are outside this CI case set.

## 7. Numbers from the reference song (Coven, 2026-11-22)

- **Real fixes made by hand with this method:**
  - Bar 91: two Jayson Scratch clips at +0.0625 beat (31 ms; flam up to
    46 ms). Moved back, and the cycle then matched bar 87 sample for sample.
  - Bars 63-66: Jason about 20 ms early (+0.04 beat).
  - Bar 30: Bar 17 High R about 20 ms late (-0.04 beat).
  - All were re-verified at 0-6 ms by both audio methods.
- **Explained and left alone:**
  - Jayson 209.01 (a deliberate fix; already within 4-8 ms of Jason).
  - The bars 68-70 slice edit (a pattern repeated three times).
  - Jason 346.3125 and 362.3125 (+0.0625 off their take, but already within
    0-12 ms of Jayson; moving them would make them 31 ms early).
  - The After Riff pickup slivers (identical on L and R).
- **Placement control:** the bar 90-91 plant was caught, and the real state
  stayed clean.
- **DI control:** the riff at bars 63-66 was caught (-20 ms shift read as
  -16/-18). The 32nd-note bursts at bars 90-91 were MISSED, because they
  alias.
- **Render control** on the scratch doubles: a 12-20 ms shift was tracked in
  about 55-60% of clips. The After Riff pair tracked it in 4 of 4 clips.

## 8. Things tried and dropped

- **Guitar vs kick drum (MIDI kick onsets as the reference):** too noisy to
  use. The drums aren't the reference for a double anyway.
- **Per-bar windows instead of per-clip windows:** clip boundaries are where
  edits happen, so per-clip windows point straight at the clip to move.
- **Longer envelope windows (6-32 ms) to suppress pitch ripple:** no decisive
  gain in control catch rate, and the baseline lags themselves moved. The
  hand-validated 2 ms frames were kept.
