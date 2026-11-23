---
name: tab-vs-recording
description: Score how faithful a MIDI guitar tab is to a real recording with the bundled scripts/compare_tab.py (chroma DTW alignment, same-song confidence, and note-level F-measure with per-quarter scores). Trigger on "how accurate is this tab", "is this tab right", "how do I know a tab I found online is correct before I learn it", "score my tab", "compare this MIDI to the recording", including before any files are sent. Get the MIDI from a Guitar Pro file with guitar-pro first. Do NOT use for writing or editing tabs (guitar-pro), or for comparing two recordings of one performance (quad-cortex-neural-capture).
---

# Tab vs. recording

Decide — with numbers — how faithful a MIDI guitar tab is to the real
recorded song. A tab and a recording share a *composition*, not a signal, so
the method is: align the timelines, then score note-by-note. This is the
same machinery Raffel & Ellis used to match 45k MIDI files to audio for the
Lakh MIDI Dataset; nothing here is invented.

## Workflow

1. Get the tab as MIDI. A Guitar Pro file goes through the `guitar-pro`
   skill (`gp_tab.py` exports MIDI); a `.mid` from anywhere else works as-is.
2. Get the recording as a file librosa can read (wav, mp3, flac).
3. For note-level scoring, transcribe the recording to MIDI — Basic Pitch is
   the practical default (`pip install basic-pitch`, then
   `basic-pitch <out-dir> SONG.wav`). Skippable: without it you still get
   the alignment confidence and chroma similarity.
4. Run the script:

```bash
uv run --with numpy --with scipy --with soundfile --with librosa \
  --with pretty_midi --with mir_eval scripts/compare_tab.py \
  TAB.mid SONG.wav --ref-midi SONG_basic_pitch.mid --json report.json
```

If `uv` is not installed but `python3 -c "import librosa, mir_eval,
pretty_midi"` works, run `python3 scripts/compare_tab.py ...` with the same
arguments; the packages are what matter, not the launcher.

Pass `--subseq` when the tab covers only part of the song (a riff, one
section). The script trims silence on both sides, aligns in chroma space
with an onset-weighted feature (a lightweight DLNCO), warps the tab's note
times onto the recording's timeline, and scores.

## Reading the numbers

- **DTW cost/step** is the same-song confidence — lower is better. It has
  no universal threshold; calibrate once against a known-good pair. On the
  bundled synthetic fixtures the wrong song's cost is many times the
  matching tab's, not a close call. If the confidence is in wrong-song
  territory, stop: the note-level scores below are meaningless.
- **Onset+pitch F1** at the MIREX tolerances (onset ±50 ms, pitch
  ±50 cents, offsets ignored) is the headline faithfulness number:
  **≥ 0.9 excellent** (at the ceiling of what transcribers resolve),
  **0.7–0.9 usable with errors**, **0.5–0.7 weak**, **< 0.5 substantially
  unfaithful**. The script prints the rung it landed on as a `rung:` line.
- **Per-quarter F1** localizes the damage — a global score hides one wrong
  section; a bad quarter says where to look.
- **The ceiling is the transcriber, not the tab.** Basic Pitch itself lands
  around 0.7–0.9 F1 on guitar, so scores are a *lower bound* on tab
  faithfulness. Calibrate with a tab you know is right before judging one
  you suspect is wrong, and quote scores relative to that calibration.
- Tabs are often written an octave off. Onset F1 far above onset+pitch F1
  with clean quarters suggests octave errors rather than wrong notes; see
  the octave note in `references/alignment-and-scoring.md`.

## Answering before there are files

When the user asks how to check a tab but has sent no files yet, give no
verdict, and explain the method. Two points belong in every such reply:

- Name the `guitar-pro` skill (`gp_tab.py`) as the way to export a Guitar
  Pro file to MIDI. Don't just say "export it to MIDI".
- Say the score is a lower bound because the transcriber misses notes
  itself, and recommend scoring a tab you know is right first, as the
  calibration to judge this one against.

## Reporting the result

The point of running a script is that the verdict rests on measurements, so
the report must not mix in numbers that were never measured. **Every number
in the reply comes from this run's script output**, copied as printed:

- Paste the script's printed result lines for each tab (cost/step, chroma
  similarity, alignment span, onset and onset+pitch F1, per-quarter scores,
  `rung:`) verbatim in a code block, headed by the tab's name. The reader can
  then check every number in the reply against the output it came from, and
  so can you before sending. Say which command ran, including `--ref-midi`
  when a reference transcription was used.
- Say the verdict in words the output supports: the matching tab's `rung:`
  (for example "excellent"), and for a tab whose cost/step is far above the
  known-good one, that it is not the same music and its F1 is meaningless.
- A number in the prose is one copied from that block. Do not hang a reading
  on a single number that the output does not give ("the 0.22 is chance
  overlap", "the 1.00 is a best case"), and do not count or total what the
  script did not ("all four quarters"). Make such points about the run in
  words instead ("the reference is the exact source MIDI, so this pair is a
  best case").
- Compare two runs in words ("far higher than the matching tab's"), not with
  a ratio or difference you computed yourself.
- Explain the transcriber ceiling and calibration in words ("scores are a
  lower bound, because the transcriber itself misses notes"). Do not restate
  ranges or calibration values from this document, the references, or a
  fixture generator's docstring as if they were results.
- What an input says about itself is not a measurement. A generator's
  docstring, a filename or the user's description may say how the
  performance was stretched or shifted, or what the wrong tab plays. Do not
  use that to explain the output ("alignment absorbed the stretch and
  shift"). The script printed an alignment span, not the cause of it, so
  report what it printed.
- If you want to state something the script did not print, run something
  that prints it, or leave the number out.

## Quick check without Basic Pitch

For a short lead line or a single bar - a lick the user says is wrong, two
candidate readings to choose between - a full alignment is more machinery than
the question needs. `transcribe-guitar-riff/scripts/shift_score.py` tracks the
recording's pitch frame by frame and reports how often the tab's sounding pitch
matches, next to the same notes shifted -1/+1 semitone and -1/+1 octave:

```bash
python ../transcribe-guitar-riff/scripts/shift_score.py CLIP.wav --start S --bpm 120 \
  --bar 36 --bars 1 --spec new.spec --require-beats old.spec --fmin 300 --band 280 5000
```

A real match clears all four controls by a wide margin (77-88% against 1-21%
on two real jobs). It needs the region already located (`--start` is the
file's seconds at the first downbeat) and the octave already settled - the
pYIN floor decides which octave it can see. Pair it with
`overlay_tab.py` from the same folder for the picture. Use the full
`compare_tab.py` run when the question is the whole song.

## What this cannot decide

- Anything about tone, feel, or arrangement quality — it scores notes and
  timing only.
- Structure differences bigger than alignment can absorb: a tab that skips
  the solo scores against the whole song only with `--subseq`, and a
  recording with an extra chorus will drag the confidence down without the
  notes being wrong. Score section-by-section when structures differ.
- Absolute faithfulness beyond the transcriber ceiling — report the rung
  the evidence supports, never a higher one.

## Reference files

- `references/alignment-and-scoring.md` — feature and alignment choices
  (chroma + onset channel, MrMsDTW when scaling up), the Raffel confidence
  recipe, mir_eval conventions, transcriber options with their measured
  ceilings, and the calibration discipline — with sources.
- `evals/files/make_fixtures.py` — deterministic fixtures (matching tab,
  tempo-warped rendition, wrong tab) that prove the pipeline's positive and
  negative controls.
