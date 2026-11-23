---
name: transcribe-guitar-riff
description: Work out the notes of a recorded guitar riff, from an Ableton Live clip or a WAV, and deliver a per-beat reading, cleaned MIDI, an A/B reference track in Live, and a Guitar Pro tab in the player's tuning (8-string and drop included). Also use it to settle which octave or register a recorded riff is in, including when someone reads the octave off a single spectrum or analyzer peak that lands near an open string. Trigger on "what notes is this", "transcribe this riff", "tab out this recording", "which octave is this riff in". Do NOT use for writing a tab with no audio (guitar-pro), scoring a tab against a recording (tab-vs-recording), or for vocals, drums, or full mixes.
---

# Transcribe a guitar riff

Turn a recorded guitar part into notes the player can trust. The audio is
the evidence; every pitch you deliver traces back to a number the scripts
printed, and the report says plainly what has not been checked by ear.

## Host-environment translation

| Action | Claude Code | Other hosts |
|---|---|---|
| Read the Live set's tracks and clips | `mcp__ableton-mcp__get_session_info`, `get_track_info`, `get_arrangement_info` | ableton-mcp equivalents, or parse the `.als` only |
| Put a MIDI reference in Live | `create_midi_track`, `set_track_name`, `load_instrument_or_effect`, `create_clip`, `add_notes_to_clip`, `duplicate_clip_to_arrangement`, `set_arrangement_loop` | same names on ableton-mcp; skip the step and deliver the `.mid` if absent |
| See Live's screen (verify a clip, read a meter) | `mcp__computer-use__*` after `request_access` for "Ableton Live 12 Suite" | any screen-control MCP; otherwise ask the user to look |
| Write the tab | `scripts/tab_build.py` for the riff string, then `scripts/gp_tab.py riff` for the `.gp5` and its MIDI; `Skill("guitar-pro")` for a native `.gp` (8+ strings) | same scripts; load the guitar-pro SKILL.md for `.gp` |
| Hand files to the user | `SendUserFile` | attach or link the files |

Scripts live in this skill's `scripts/` and run with
`uv run --with-requirements scripts/requirements.txt python scripts/<name>.py`
(numpy, scipy, librosa, soundfile, pretty_midi, mido, matplotlib, pyguitarpro).
If `uv` is missing but `python3 -c "import librosa, pretty_midi, guitarpro"`
works, run `python3 scripts/<name>.py` instead - check this once, first, rather
than discovering it command by command. `ffmpeg` must be on PATH for the cut.
Paths below are relative to this skill's directory (`${CLAUDE_SKILL_DIR}` or
`$SQUAD_SKILL_DIR`).

## When the question is about the octave, not the notes

People often settle the register from one spectrum peak that lands near an
open string's frequency, and conclude the riff sits in that string's octave. Do
not agree on that evidence alone, even when no audio is attached. Walk them
through the tests that decide it, using their numbers, and answer about the
octave or peak they named directly, by name, even when the measurement rules
it out:

1. **Cents offset.** A played note sits within a few cents of where the guitar
   is tuned. Compute the offset, cents = 1200 x log2(peak / tuned frequency),
   and say what it means. For example, a peak read as "C2" at 66.5 Hz sits
   +29 cents sharp of the tuned string (65.41 Hz) - far too much for a
   string the player tuned - so it is not a played note.
2. **Difference tone.** Distortion makes intermodulation products at |a - b|
   of two stronger components. Check whether the suspect peak equals the
   difference of two other peaks: in that example 66.5 = 196.4 (G3) - 129.9
   (C3), exactly. A peak that is off-grid AND equals a difference is a
   distortion product, not the riff.
3. **Independent harmonics.** A real fundamental also lights up its octave
   above, so the loudest octave proves nothing; the register is the one whose
   own harmonics stand up independently, and the upper voice (which is not a
   harmonic of the lower octave) usually settles it.
4. **Measure instead of reading the analyzer.** Run
   `scripts/riff_salience.py` on the clip and read its **long-term spectrum
   peaks** block: it prints every strong peak with its note and cents offset
   and tags the off-grid peaks that equal the difference of two others as
   distortion difference tones. Then confirm with `scripts/octave_check.py`
   (Step 2). Offer to run both if they send the audio. When no audio is
   attached, the reply still recommends running `riff_salience.py` and says
   to read its long-term peaks block, by that name, before deciding the
   octave.

## Inputs to collect first

- **Tuning, low string to high**, as note names (`C1,G1,C2,F2,A#2,D#3,G3,C4`).
  Ask if not given; fret numbers are meaningless without it.
- **Tempo and meter** from the set (`get_session_info`) or the user.
- **Which track/clip**, or which file and which seconds of it.

## Step 1 - isolate the source without rendering

1. Find the track and its arrangement clips with `get_arrangement_info`.
   Note the bars the clip occupies. If the user's notes give a time
   ("the lick at 1:11"), convert it to an arrangement beat first
   (seconds x BPM / 60) and look at every clip that plays there - on one job
   1:11 landed exactly on a short clip that had been written off as FX.
2. Map the clip to sample seconds from the saved set:

   ```bash
   python scripts/als_clip_region.py "SET.als" --track "REAL 5"
   ```

   It prints, per clip, the arrangement bars, the sample path, and
   `start_s`/`end_s` computed through the clip's warp markers, plus the exact
   `ffmpeg` cut line. Warnings flag pitch-shifted clips and unusual warping.
   If the open session has unsaved edits, compare its bars with the file's;
   the region is still right unless the clip itself moved.

   **Read the set before you read the audio.** The arrangement carries
   musical facts the audio alone will not give you:

   - **Disabled clips and muted tracks are part of the part.** A loop with its
     second half switched off in one bar meant the riff stops there; transcribing
     the raw take would have played straight through it.
   - **Frozen tracks still hold their raw clips.** In the `.als` the
     `MainSequencer` events are the source clips and the `FreezeSequencer`
     events are the render. `als_clip_region.py` lists both; read the raw
     (often `Samples/Processed/Consolidate/`) clips, not the freeze render.
   - **Warp markers that sit on a sixteenth grid usually mark note onsets** -
     the player put them there. Print them per clip; they are a free onset
     list to check yours against.
   - **Never dismiss a clip as noise or FX without a pitch pass.** On one job a
     two-beat clip on a bounced group track was called a "noise sweep" and
     dropped; it was the lead lick the user asked about.
3. Cut the region from the raw sample (bit-exact; do not bounce through the
   track's EQ/compressor/limiter):

   ```bash
   ffmpeg -y -ss START -to END -i "SAMPLE.wav" -c:a pcm_s24le "OUT/clip (raw).wav"
   ffmpeg -y -ss START -to END -i "SAMPLE.wav" -ac 1 -c:a pcm_s24le "OUT/clip (mono).wav"
   ```

   Set END one beat (60/BPM seconds) past the region's last barline. That
   tail is the last notes' ring: the reader still stops at the last barline,
   but without it nothing tells a note still picked at the barline from one
   ringing out, and every note that reaches the clip's end is listed as a
   doubt.

   Prove the cut with `ffmpeg -ss START -to END -i SAMPLE.wav -f md5 -`
   against `ffmpeg -i OUT.wav -f md5 -`; check the mono file is not silent
   (`-af volumedetect`). Put outputs in a folder next to the project, not in
   the project's `Samples/`.
4. If the input is already a file, skip to Step 2, but still trim to the
   passage in question, keeping one beat past its last barline, and note
   where its first downbeat is.

## Step 2 - settle the octave BEFORE anything band-limited

Do this first, every time, and never skip it because a previous reading
"already established" the register.

```bash
python scripts/octave_check.py "OUT/clip (raw).wav" --bpm 120 --origin-beat 64 \
  --bars 21,36 --candidates F#1,F#2,F#3,F#4
```

It samples attacks across the whole section and fits a harmonic comb at every
octave of the candidate over a wide band, reporting how often each wins.

It decides the register of the lowest voice; the upper voices then follow
from the cents column and the fact that they are not harmonics of it (Step 4).
Give it one pitch class at each octave in reach (`E1,E2,E3,E4` for a pedal
you read as E), over only the bars where that note is the lowest voice. When
the pedal changes (E3 for three bars, then D#3), check each stretch on its
own: mixing stretches with different pedal notes splits the wins and prints
LOW AGREEMENT even when the octave is clear. LOW AGREEMENT from a run set up
that way means the register is unresolved. Then the reply says so and does not
assert it, and the same goes for a register you never ran this check on.
Quote the `verdict:` line in the reply.

**Why this is a hard gate and not an optional nicety.** On a real job a
low-string tracker was run over 38-100 Hz, answered "F1/F#1", and that answer
was then written up as independent confirmation of an earlier F1/F#1 reading.
It confirmed nothing: *a comb that can only look below 100 Hz can only ever
return a note below 100 Hz.* The riff was on F#2 at 92.5 Hz - the loudest peak
in the spectrum, one cent flat - and the whole heavy section shipped an octave
low, on the wrong strings, unplayable. A second section shipped two octaves
low. Every downstream metric passed, because they were all octave-blind or
band-limited too.

So: a band-limited search is a HYPOTHESIS, never a measurement. Before you pass
`--fmin/--fmax` or `--band` to anything, you must already have a wide-band
verdict, and the band you choose must contain the octave that verdict named. If
you ever catch yourself citing a band-limited tool as confirmation of the octave
it was configured to find, stop and re-run this step.

Cross-check it with a second, independent opinion before proceeding - the
cheapest is Basic Pitch's note distribution (see below); if its modal MIDI
numbers sit an octave from yours, yours is wrong.

**Bounced and heavily processed sources resist this step.** On a bounced lead
group (amp, compression, effects baked in) `octave_check.py` returned LOW
AGREEMENT, and pYIN's own floor decided the answer: `fmin` 150 Hz read the lick
an octave low, `fmin` 300 Hz read it right. Neither run is evidence for the
octave it was allowed to see. Basic Pitch settled it (D#5/B4/G4, matching the
player's position). Install it once, in its own venv (about two minutes; it
pulls TensorFlow):

```bash
python3.11 -m venv bpvenv && . bpvenv/bin/activate
pip install "basic-pitch[onnx]==0.4.0"
```

```python
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH
_, midi, notes = predict("clip.wav", ICASSP_2022_MODEL_PATH,
                         minimum_note_length=20, minimum_frequency=150)  # leads
# notes: (start_s, end_s, midi, amplitude, bends) - read the register off these
```

It reports fewer notes than are played (short legato notes drop out), so use
it for the octave and the strongest notes, not as the transcription.

**Calibrate the recording's pitch before you call any note by name**, with
`scripts/fundamental.py`:

```bash
python scripts/fundamental.py "OUT/clip (mono).wav" --band 115 175 --expect C3,B2,E3,D#3
python scripts/fundamental.py "OUT/clip (mono).wav" --band 34 50 --candidates D1,F1,F#1
```

Pointed at a passage whose notes are already settled, `--expect` prints how far
each sits from concert pitch; until you know that, an absolute call is
meaningless, because a peak at 90.8 Hz is F#2 thirty cents flat or F2 seventy
cents sharp and nothing in the peak itself decides which. Then read notes in the
band their own **fundamental** lives in, chosen because nothing else in the mix
plays there - never in a harmonic band, which is crowded by every instrument
above you. See "Measure pitch in the fundamental band" in
`references/analysis-notes.md`; this is the quiet second form of the trap above,
and it produced a confident off-by-a-semitone answer on a later job.

**If the user has a Songsterr tab of this song, read `references/songsterr.md`
now.** Their `/api/useraudio/{songId}` carries a measured per-bar onset grid for
the actual recording, which beats deriving a tempo from warp markers and is the
fastest way to get the bar grid right. `scripts/ss_convert.py` reads a saved
track JSON into our spec and prints that grid.

Take the tab from Download -> Guitar Pro, not from the CDN JSON - they are
different tabs - and then **diff the two**. Where they differ, a human edited the
published revision, and those bars are both ground truth and a worked example of
what kind of correction the rest needs. A Songsterr revision marked
`aiGenerated: true` can be wholesale wrong about the key over one section, and
nothing downstream will catch it.

## Step 3 - find the repeating unit before reading any slot

Music repeats. A riff is written once and played N times, so read it once:

```bash
python scripts/riff_cycle.py "OUT/clip (raw).wav" --bpm 120 --origin-beat 64 \
  --bars 21,36 --band 75,200 --json OUT/cycle.json
```

It scores every whole-bar lag by how many discretised slots actually repeat at
that lag, folds all repetitions of the winning cycle together (about sqrt(N)
better signal-to-noise), and emits ONE cycle. Stamp that cycle back across the
section rather than reading each bar again:

```bash
python scripts/riff_cycle.py ... > OUT/cycle.spec
python scripts/stamp_cycle.py OUT/cycle.spec --bars 21,36 --out OUT/section.spec
```

Reading each bar independently is the single biggest tell of a machine
transcription and the reason a tab can score well per note and be worthless:
sixteen subtly different bars where the music has four, repeated. Compare the
detected cycle against the section map you wrote in Step 1 - if the audio says
4 bars and your map says 4 bars, stamp it; if they disagree, find out why before
writing anything.

**Read the instance-agreement number the fold prints.** It is the honest
confidence: when a large share of cycle positions disagree across their own
repetitions, per-slot pitch tracking is not resolving this material and no
amount of further processing will fix that. Say so, and get a reference
(Step 7) rather than shipping a confident reading built on it.

## Step 3b - measure the tempo; never inherit it

A warp marker records the tempo Live *guessed* at record time, and a project
tempo is whatever the project is set to now. Neither is a measurement:

```bash
python scripts/tempo_fit.py "OUT/clip (mono).wav" --min 70 --max 100 --div 2
```

It scores how much onset energy lands on a grid at each candidate tempo, over
all phases, and prints the margin over the runner-up so a weak fit is visible.

Then keep the two tempos separate, because they are different numbers:

- **Read** the clip at the rate it was RECORDED at - that is what its own
  attacks sit on.
- **Write** the tab at the rate the arrangement PLAYS it at after warping -
  that is what a player needs to play along.

On this project those were 86 and 81.3253, and conflating them sent a whole
turn down the wrong path in both directions. And if the song changes tempo,
the tab must say so: `tab.set_tempo_at(bar, bpm)` puts the change in the file
(both the `.gp5` mix table and the `.gp` master-bar automation). A single
tempo for a song that has two is not a rounding error - every bar after the
change is in the wrong place.

## Step 4 - estimate pitches on the grid

Do not start with pYIN or another monophonic tracker on distorted guitar;
it reports every frame unvoiced. Run the salience pass:

```bash
python scripts/riff_salience.py "OUT/clip (mono).wav" --bpm 120 \
  --tuning C1,G1,C2,F2,A#2,D#3,G3,C4 --bar-offset 70 \
  --png "OUT/salience.png" --json "OUT/slots.json"
```

Read two things here; Step 5's reader makes the note decisions:

1. **The per-beat summary** is a draft: notes in the top two candidates of
   at least half a beat's slots. It ranks harmonics and images
   with the played notes, so it is never the reading.
2. **The long-term spectrum peaks** to settle the octave. A played note sits
   within a few cents of the tuned grid; a peak more than 20 cents off that
   also equals the difference of two other peaks is distortion
   intermodulation and gets flagged. A fundamental always lights up its
   octave too, so decide the register from the upper voice (which is not a
   harmonic of the lower octave) and from the cents column, not from which
   octave is loudest.

If the strongest long-term peaks all sit 20-50 cents off the grid in the
same direction, the guitar was not at A440. Re-run with `--auto-tune` (or
`--tune-offset N` when the cents are known); the script shifts the note grid,
prints the offset it applied, and stores it as `tune_offset_cents` in the
JSON. Without it a sharp take loses most of its notes to the 20-cent filter.

Open the PNG (Read it) when the table is ambiguous; a sustained pedal and a
moving upper line are obvious by eye. `references/analysis-notes.md`
explains the method and the failure modes; read it if a result looks wrong.

Do not count attacks off a waveform plot of a low part: below ~60 Hz every
cycle is a spike, so a single chug looks like a burst of attacks. Take onsets
from a high-passed (> 1.5 kHz) RMS or onset envelope, and check the level at a
clip's first frames before calling a first note - pYIN reported a note over
half a beat of silence at the start of a clip.

Optional second opinion: basic-pitch (polyphonic MIDI in one command; needs
its own Python 3.11 venv, see the reference). Use it to corroborate, not to
author.

## Step 5 - read the notes with `riff_read.py`

Do not author the reading by hand from the table. Which candidates are
voices and where each note starts and stops are decided by a script, the same
way every time, and it prints the row behind every decision:

```bash
python scripts/riff_read.py "OUT/clip (mono).wav" --bpm 120 \
  --tuning E2,A2,D3,G3,B3,E4 --lowest A#3@1-3,A3@4 --spec OUT/riff.spec --json OUT/reading.json
```

`--lowest` takes the note each `octave_check.py` `verdict:` line named, with
the bars that run covered, one per pedal stretch (Step 2): `NOTE@FIRST-LAST`,
or `NOTE@BAR` for one bar, with bars numbered as in the slot ids. Each note
applies only in its own bars, so one stretch's pedal never sets aside the
octave of another stretch's upper voice; a bare note covers the whole riff.
The script refuses to run without it, or with a bar it leaves uncovered,
because the register is the octave check's call, not the reader's. Pass the same
`--tuning`, `--offset`, `--bar-offset` and `--tune-offset`/`--auto-tune` as
the salience run, and `--voices 3` for a three-note chord riff. Its docstring
lists the rules; in short:

- **Voices.** Every candidate that is not a voice is printed with its
  measured reason: `no fret` (below the lowest open string), `below X` (under
  the register the octave check named, so a sub-octave image or difference
  tone, including the octave below an upper voice), `octave above/below X`,
  `12th above X` or `two octaves above X` (a harmonic or image of a stronger
  note), `N dB under the lead`, or `weaker than 2 voices`. Of a `--lowest`
  note and its octave, the `--lowest` note wins unless the octave leads it
  for two or more slots in a row (more than 6 dB stronger, or the slot's
  strongest where the `--lowest` note has no peak): then the octave is
  played and the `--lowest` note under it is its image.
- **Edges.** A one-slot dip is held; a one-slot flicker is dropped. A note
  that a new note in the same line attacks over ends at that attack. A note
  that ends on its own is cut 0.25 s before its fade: that sound is taken as
  its last pick ringing on, so a held or let-ring note may be written up to
  0.25 s short. A note still sounding at the last barline ends there; the
  ring-out after the final chord is not another bar. A pedal ends where the
  next stretch's `--lowest` note puts it under the octave check's register.
  In a clip with no tail past the last barline, every note that reaches the
  clip's end is listed under `check by ear` as possibly ringing.

It prints the reading as a spec (also written by `--spec`), a `note edges`
block giving each note's first and last slot, why it stops there and its level
in every slot read, the `salience rows` for every edge, held dip and cut ring,
and a `check by ear` block. Build everything downstream from that spec unchanged:

```bash
python scripts/riff_midi.py OUT/riff.spec --bpm 120 --bar-offset 70 \
  --out "OUT/cleaned.mid" --ableton-json OUT/notes.json
```

`riff_midi.py` prints the reading back with the interval each upper note
forms above the lowest one. Copy intervals from that column rather than
naming them by hand.

If the reading looks wrong to you, do not edit the spec to taste. Re-check
the inputs (tempo, offset, tuning, `--lowest`), rerun, and report what still
looks wrong as a doubt for the ear check, quoting the rows. The reader's
spec, the MIDI, the tab and the table in the reply then all show the same
notes. It is built for picked notes on the grid (tremolo or re-picked
lines). Every note that ends on its own is cut 0.25 s before its fade, so a
held or let-ring note may end early; the `check by ear` block says so and
lists each one, so pass those on.

**Author the reading from the audio alone.** When the audio comes with its
answer (a test fixture's spec or expected notes, the MIDI it was rendered
from, the generator's source or docstring), leave that file unopened, and say
in the reply that the reading was made without it. Do not use it to correct
your reading afterwards either: a note or boundary taken from the answer is
not one the audio showed you, and the reading stops being evidence of
anything. If a boundary is uncertain, report the reader's doubt and its rows. Run a fixture generator without reading it, with the output
directory as its only argument, adding each module it reports missing to
`uv run --with`.

**Decide durations from a closed set; never let an onset-to-onset span become a
duration.** Measured gaps produce lengths like 5/4 or 7/4 of a quarter note,
which no single note value can draw, so the writer splits each into re-picked
notes and the rhythm reads as a stutter. 7.6% of our segments were like that.
`scripts/tab_build.py --single-note-durations` instead solves each bar: it walks
the bar in legal note values and picks the partition whose boundaries land
nearest the measured attacks, charging for every attack it has to swallow. The
bar still sums to its signature and every beat is writable. Songsterr's 105-bar
track uses eight duration kinds total - that is the target.

```bash
python scripts/tab_build.py OUT/section.spec --tuning E1,B1,E2,A2,D3,G3,B3,E4 \
  --single-note-durations --out OUT/riff.txt
```

A tremolo-picked riff is the other case: every note is re-picked on a fixed
grid, so the tab is straight sixteenths, not held values. `--tremolo 16` writes
each segment that way, and dyad lines are fingered as shapes on two strings
within the hand's reach.

The same command maps the notes to the neck, and its fingering scorer carries a
reach limit and a cross-string jump penalty - the two terms the first version
lacked, which is how a lone fret 11 landed in the middle of a frets-3-to-7 riff
(`references/songsterr.md` has the full weight list). Read what it chose rather
than trusting it: prefer one position and a shape the riff repeats (a pedal on
one string with the moving voice on the next string up is the common
tremolo-dyad shape), and say which alternative fingering also works.

## Step 6 - put an A/B reference in the DAW

The fastest ear check is the cleaned MIDI on a plain tone under the real
track. In Live via ableton-mcp:

1. `create_midi_track` at the index right after the source track;
   `set_track_name` to `<track> transcription (A/B ref)`.
2. `load_instrument_or_effect` with `query:Synths#Operator` (default sine).
3. `create_clip` on slot 1 with the riff's length in beats; `add_notes_to_clip`
   with the `notes.json` list; `set_clip_name`.
4. `duplicate_clip_to_arrangement` at the clip's start bar.
5. `set_arrangement_loop` over the bars. If it errors with "Cannot set the
   Loopstart behind the Songlength", set a short loop at bar 1 first, then
   the real one (the remote script sets start before length).
6. Tell the user the set is unsaved and how to solo the pair.

There is no MCP call that reads notes back from a clip. If a reviewer needs
direct evidence, open the arrangement clip in Live's editor with screen
control and screenshot the note editor.

## Step 7 - tab, and score it with the real metric

Build the riff string from the same spec, in the user's tuning (low to high),
then hand it to `scripts/gp_tab.py riff`, which writes the Guitar Pro file and
its MIDI export. Up to seven strings:

```bash
python scripts/tab_build.py OUT/riff.spec --tuning E2,A2,D3,G3,B3,E4 --tremolo 16 \
  --out OUT/riff.txt
python scripts/gp_tab.py riff "OUT/tab.gp5" --tuning "E2 A2 D3 G3 B3 E4" \
  --tempo 120 --notes "$(tail -1 OUT/riff.txt)" --midi "OUT/tab.mid" --print-ascii
```

`scripts/gp_tab.py` is a byte-identical copy of the `guitar-pro` skill's
helper, kept here so this skill runs on its own (`scripts/selftest.py` fails if
the two drift; change the guitar-pro original and copy it over). It writes the
`.gp5`, reloads it from disk, and does the rest from the reload: a summary line
(measures, tempo, tuning, note count), the MIDI export, and the ASCII tab. Use
`--single-note-durations` instead of `--tremolo 16` for a single-note line with
held notes. The `.gp5` format stops at seven strings; for eight or more, write
a native `.gp` through the `guitar-pro` skill (it says why), and load that back
with alphaTab to check string count, measure count, and tuning MIDI numbers.

Then verify the written file, not the writer:

```bash
python scripts/compare_rolls.py "OUT/tab.mid" "OUT/cleaned.mid" --expect match
```

It must print `ROLLS MATCH`. The tab writes every tremolo hit as its own note
and the cleaned MIDI uses sustained notes, so compare sounding pitches per
sixteenth (this script), never onset lists. On `ROLLS DIFFER`, fix the spec
or the riff string and rebuild both files before reporting; a tab that does
not match its own reading is not a deliverable. A common cause is a partial
last bar: the writer pads it to a whole bar, so end the spec at the last
barline and mention the ring-out past it in words.

That only proves the writer matched your spec. To find out whether the SPEC is
any good, hand the tab to the `tab-vs-recording` skill, which does chroma-DTW
alignment and note-level F-measure at the MIREX tolerances against a Basic Pitch
transcription of the recording:

```bash
uv run ... music/tab-vs-recording/scripts/compare_tab.py TAB.mid SONG.wav \
  --ref-midi SONG_basic_pitch.mid
```

**Use this instead of inventing your own accuracy metric.** On the job above, a
home-rolled octave-blind chroma-top-3 score plus onset backing reported healthy
numbers on a tab whose real onset+pitch F1 was **0.05** - "substantially
unfaithful" on this skill's own ladder - and whose whole heavy section was an
octave out. `compare_tab.py` would have said so in one command. Basic Pitch's
note histogram is also the cheapest octave cross-check there is: if its modal
MIDI numbers are an octave from your tab's, believe Basic Pitch.

**Then look at it, and score it against shifted copies of itself.** Two
checks did more than any other on real jobs, and both are now scripts:

```bash
python scripts/overlay_tab.py "OUT/clip (mono).wav" --start S --bpm 120 --bar 36 --bars 1 \
  --spec OUT/old.spec --spec OUT/new.spec --compare --label before --label after \
  --tuning B0,E1,A1,E2,A2,D3,G3,B3,E4 --fmin C4 --octaves 2 --png OUT/overlay.png
python scripts/shift_score.py "OUT/clip (mono).wav" --start S --bpm 120 --bar 36 --bars 1 \
  --spec OUT/new.spec --require-beats OUT/old.spec --fmin 300 --band 280 5000
```

- `overlay_tab.py` draws every written note as a line on a constant-Q
  spectrogram of the clip, on a 32nd grid. A right note sits on a bright trace;
  a wrong one floats in the dark. It is a required step and a deliverable: it is
  the one piece of evidence the user can check without trusting a metric.
- `shift_score.py` tracks pitch frame by frame (pYIN, frame 1024, hop 64 - hop 32
  left a distorted lead almost all unvoiced) and counts the frames where the
  tab's sounding pitch matches, next to the same notes shifted -1/+1 semitone
  and -1/+1 octave. A real match clears every control by a wide margin (77-88%
  against 1-21% on two jobs). Score the whole timeline frame by frame; scoring
  each note on the middle of its own window misjudged a 32nd-note lick and
  ranked the wrong version higher. `--require-beats` exits non-zero unless the
  new tab beats the known-bad one - the gate the guardrail below asks for.
  pYIN follows one pitch, so this is for single-note lines; on a dyad or chord
  riff a low match rate says nothing either way, so skip it there.

If the user has a reference tab (Songsterr, a published transcription, an
earlier version they have actually played, a tab in their own notes), get it
and compare bar by bar against BOTH readings with the audio as arbiter.

**A tab the player wrote is a hypothesis about the recording, not a measurement
of it.** It is the best evidence there is for which version they *mean* to play,
and no evidence at all for which version is *on the recording*. On one job the
player's own doc had a lick as `19 20h 17 18h 15 16h 13 14h 12`; all three
recorded takes played `19 20h 19p 18 ~ 16 13 12` (88% frame agreement against
61% for the doc version). When you are asked what was recorded, the recording
decides: write what is there, and report the difference note by note so the
player can say which one they want in the tab.

## Step 8 - report

Deliver, in one folder next to the project: the raw and mono cuts, the
salience PNG, the cleaned `.mid` (and the basic-pitch `.mid` if made), the
tab and its `.mid`, and a README with:

- where the audio came from (set, track, clip bars, sample seconds);
- a bar-by-beat table of the reading and the intervals it forms;
- the fretting in the user's tuning, with the alternative position;
- the octave evidence (cents offsets, difference tones, upper voice, Basic
  Pitch's register);
- the overlay PNG and the `shift_score.py` table, old tab vs new;
- every place the transcription departs from a tab the player wrote;
- the sentence **"Not yet verified by ear against the audio."** until the
  user has done that, and what to A/B in the DAW.

**The reply itself carries the evidence** - the user reads your message, not
the folder. Put these in it, each copied from a script's output:

- The reading: a bar-by-beat table of `riff_read.py`'s spec, with intervals
  from `riff_midi.py`. Every row and every boundary is the reader's; do not
  move, extend or add one by hand, and name no pitch the reading does not
  hold and no key, scale or chord name the scripts did not print. A blanket
  line such as "every note is supported" checks nothing; the evidence block
  below is the support.
- The evidence, pasted verbatim and whole in one code block: `riff_read.py`'s
  `note edges`, `salience rows` and `check by ear` blocks, and each
  `verdict:` line from `octave_check.py`. Make rerunning `riff_read.py` with
  the same arguments your last command before writing the reply (it prints
  the same reading every time) and copy the blocks from that output, not
  from memory of an earlier one; do not excerpt or summarise them. Those
  rows show each note where it starts and stops, and every other candidate
  in the slot with the reader's measured reason for leaving it out. A
  candidate the reading leaves out is named in your own words only with
  that reason (`D3 -14.4 (below A3)`), never as a note the user might have
  played. For the octave check, give the chosen octave and its confidence
  from the `verdict:` line. When the user names an octave or peak, answer
  about it directly with the measured numbers ("When the question is about
  the octave").
- The doubts, from the `check by ear` block, in plain words: where a note's
  sound carries on past its last pick (ring, or still picked?), and where a
  one-slot dip was held. These are the ear checks; do not settle them by
  moving the boundary, and do not call a note that is in the reading
  doubtful in other words. Octave doublings cannot be told from harmonics in
  this analysis, so say that any the user played should be added after an
  ear check. Do not cite a check that came out weak as support.
- That the reading came from the audio alone (Step 5).
- The fretting in the user's tuning, with string and fret numbers, and the
  alternative position, both taken from the `frets in this tuning` lines of
  `riff_read.py`'s `note edges` block. Do not work a position out by hand:
  a fret counted on the wrong string names a different octave.
- The ASCII tab, pasted verbatim from `gp_tab.py riff --print-ascii` in a
  code block. Never draw a tab by hand: a hand-drawn grid is
  where wrong frets and garbled rhythms creep in, and nothing checked it.
- The tab file's name and format, and the `compare_rolls.py` result against
  the cleaned MIDI (`ROLLS MATCH`).
- The octave evidence for the octaves you chose, and what you did not run.
- "Not yet verified by ear against the audio." and a direct request for that
  check, saying what to A/B.

Then stop and ask for the ear check. When the user reports a wrong bar,
fix the spec and regenerate MIDI, tab, and README together.

## Guardrails

- Never present a pitch the reading does not hold, and never hand-edit
  `riff_read.py`'s spec; report a doubt with its rows instead.
- Never drop a clip from a section as noise, FX or a riser without running a
  pitch pass on it first.
- Never copy notes from the player's written tab into a transcription the
  audio does not support; show the difference instead.
- Never bounce the track through its effect chain and call that "isolated".
- Never write the DAW's set to disk on the user's behalf; leave saving to
  them and say so.
- Keep the analysis venv separate from the DAW project folder; only
  deliverables go next to the project.
- If the user's claim about the octave rests on one spectral peak, apply
  the cents and difference-tone tests before agreeing.
- For a batch of tracks, run one subagent per track with this skill loaded
  and the same tuning/tempo; do not interleave two tracks in one context.
- Never cite a band-limited tool as evidence for the octave it was configured
  to find, and never inherit a previous reading's register without re-running
  `octave_check.py` yourself.
- Never ship a per-bar reading of a section the audio says is a repeating
  cycle. If you cannot find the cycle, that is a finding to report, not a
  licence to write each bar separately.
- When you rewrite a delivered tab, keep the old one as a known-bad control
  and require every new check to REJECT it. A check that passes the version
  the user called unplayable is not measuring the thing that made it
  unplayable.
