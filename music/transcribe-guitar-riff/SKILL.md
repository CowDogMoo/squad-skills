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

## Step 2 - estimate pitches on the grid

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

Open the PNG (Read it) when the table is ambiguous; a sustained pedal and a
moving upper line are obvious by eye. `references/analysis-notes.md`
explains the method and the failure modes; read it if a result looks wrong.

Optional second opinion: basic-pitch (polyphonic MIDI in one command; needs
its own Python 3.11 venv, see the reference). Use it to corroborate, not to
author.

## Step 3 - author the cleaned reading

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

Map to the neck yourself with the string:fret candidates in the table.
Prefer one position and a shape the riff repeats (a pedal on one string
with the moving voice on the next string up is the common tremolo-dyad
shape); say which alternative fingering also works.

## Step 4 - put an A/B reference in the DAW

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

## Step 5 - tab

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

## Step 6 - report

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
