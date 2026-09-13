---
name: transcribe-guitar-riff
description: Work out the actual notes of a recorded guitar riff - from an Ableton Live track/clip or a WAV - and deliver them as a per-beat reading, a cleaned MIDI, a MIDI A/B reference track in the DAW, and a Guitar Pro tab in the player's tuning (8-string and drop tunings included), using the bundled scripts (als_clip_region.py to find the exact sample region a clip plays, riff_salience.py for CQT harmonic-salience pitch estimation that survives high-gain tremolo picking where pYIN fails, riff_midi.py, compare_rolls.py). Trigger on "what notes is this", "figure out the notes for this track", "transcribe this riff", "tab out this recording", "what is he playing here", "get the isolated guitar out of Ableton and transcribe it", or any request to turn guitar audio into notes, MIDI, or tab. Do NOT use for writing a tab from an idea with no audio (guitar-pro), for scoring an existing tab against a recording (tab-vs-recording), or for vocals, drums, or full mixes.
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
| Write the tab | `Skill("guitar-pro")` | load the guitar-pro SKILL.md and run its `gp_tab.py` |
| Hand files to the user | `SendUserFile` | attach or link the files |

Scripts live in this skill's `scripts/` and run with
`uv run --with-requirements scripts/requirements.txt python scripts/<name>.py`
(numpy, scipy, librosa, soundfile, pretty_midi, mido, matplotlib). `ffmpeg`
must be on PATH for the cut. Paths below are relative to this skill's
directory (`${CLAUDE_SKILL_DIR}` or `$SQUAD_SKILL_DIR`).

## Inputs to collect first

- **Tuning, low string to high**, as note names (`C1,G1,C2,F2,A#2,D#3,G3,C4`).
  Ask if not given; fret numbers are meaningless without it.
- **Tempo and meter** from the set (`get_session_info`) or the user.
- **Which track/clip**, or which file and which seconds of it.

## Step 1 - isolate the source without rendering

1. Find the track and its arrangement clips with `get_arrangement_info`.
   Note the bars the clip occupies.
2. Map the clip to sample seconds from the saved set:

   ```bash
   python scripts/als_clip_region.py "SET.als" --track "REAL 5"
   ```

   It prints, per clip, the arrangement bars, the sample path, and
   `start_s`/`end_s` computed through the clip's warp markers, plus the exact
   `ffmpeg` cut line. Warnings flag pitch-shifted clips and unusual warping.
   If the open session has unsaved edits, compare its bars with the file's;
   the region is still right unless the clip itself moved.
3. Cut the region from the raw sample (bit-exact; do not bounce through the
   track's EQ/compressor/limiter):

   ```bash
   ffmpeg -y -ss START -to END -i "SAMPLE.wav" -c:a pcm_s24le "OUT/clip (raw).wav"
   ffmpeg -y -ss START -to END -i "SAMPLE.wav" -ac 1 -c:a pcm_s24le "OUT/clip (mono).wav"
   ```

   Prove the cut with `ffmpeg -ss START -to END -i SAMPLE.wav -f md5 -`
   against `ffmpeg -i OUT.wav -f md5 -`; check the mono file is not silent
   (`-af volumedetect`). Put outputs in a folder next to the project, not in
   the project's `Samples/`.
4. If the input is already a file, skip to Step 2, but still trim to the
   passage in question and note where its first downbeat is.

## Step 2 - settle the octave BEFORE anything band-limited

Do this first, every time, and never skip it because a previous reading
"already established" the register.

```bash
python scripts/octave_check.py "OUT/clip (raw).wav" --bpm 120 --origin-beat 64 \
  --bars 21,36 --candidates F1,F#1,F2,F#2,F3
```

It samples attacks across the whole section and fits a harmonic comb at every
octave of the candidate over a wide band, reporting how often each wins.

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

Read three things, in this order:

1. **The per-beat summary.** Notes in the top two of at least half a beat's
   slots are what is sounding; two stable notes per beat is a dyad. This is
   the draft.
2. **The per-sixteenth table** for the beats where the summary is unsure
   (`?` or three notes). Note changes usually land on a sixteenth boundary;
   read the dB column to see which note leads.
3. **The long-term spectrum peaks** to settle the octave. A played note sits
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

Optional second opinion: basic-pitch (polyphonic MIDI in one command; needs
its own Python 3.11 venv, see the reference). Use it to corroborate, not to
author.

## Step 5 - author the cleaned reading

Write a spec, one segment per line, from the per-beat summary and the table:

```text
# bar start end notes      (beats 1-based, end exclusive; 5.0 = end of a 4/4 bar)
1 1.0 2.0 A#3
1 2.0 5.0 A#3 F#4
2 1.0 2.0 A#3
2 2.0 3.5 A#3 F4
```

Then build the MIDI and the Ableton note list:

```bash
python scripts/riff_midi.py OUT/riff.spec --bpm 120 --bar-offset 70 \
  --out "OUT/cleaned.mid" --ableton-json OUT/notes.json
```

Quantize to the grid the table shows (sixteenths). A note that flickers for
one slot is usually an attack transient of the next note, not a note.

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

Hand the spec to the `guitar-pro` skill: straight sixteenths for tremolo
(`16:2.3+1.6 ...`), the user's tuning low to high, `.gp5` up to seven
strings, native `.gp` for eight or more (it says why). Verify the written
file, not the writer:

```bash
python scripts/compare_rolls.py "OUT/tab.mid" "OUT/cleaned.mid" --expect match
```

The tab writes every tremolo hit as its own note and the cleaned MIDI uses
sustained notes, so compare sounding pitches per sixteenth (this script),
never onset lists. For `.gp`, also load it back with alphaTab and check
string count, measure count, and tuning MIDI numbers.

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

If the user has a reference tab (Songsterr, a published transcription, an
earlier version they have actually played), get it and compare bar by bar
against BOTH readings with the audio as arbiter. A player who has played the
song is better evidence than any metric here.

## Step 8 - report

Deliver, in one folder next to the project: the raw and mono cuts, the
salience PNG, the cleaned `.mid` (and the basic-pitch `.mid` if made), the
tab and its `.mid`, and a README with:

- where the audio came from (set, track, clip bars, sample seconds);
- a bar-by-beat table of the reading and the intervals it forms;
- the fretting in the user's tuning, with the alternative position;
- the octave evidence (cents offsets, difference tones, upper voice);
- the sentence **"Not yet verified by ear against the audio."** until the
  user has done that, and what to A/B in the DAW.

Then stop and ask for the ear check. When the user reports a wrong bar,
fix the spec and regenerate MIDI, tab, and README together.

## Guardrails

- Never present a pitch the table does not support; if the summary says
  `?`, say the beat is unresolved and show the candidates.
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
