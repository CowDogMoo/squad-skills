---
name: tab-vs-recording
description: Score how faithful a MIDI guitar tab is to a real recording of the song, using the bundled scripts/compare_tab.py - chroma DTW alignment (no rendering needed), a same-song confidence from the normalized alignment cost, and note-level F-measure at the MIREX tolerances against a transcription of the recording, with per-quarter scores to localize wrong passages. Trigger on "how accurate is this tab", "does this tab match the song", "score my tab", "compare this MIDI to the recording", "is this transcription right", "check my tab against the record", or any request to grade a tab/MIDI against audio with numbers. Get the MIDI from a Guitar Pro file with the guitar-pro skill first. Do NOT use for writing or editing tabs (guitar-pro), or for comparing two recordings of the same performance (quad-cortex-capture-measurement).
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

Pass `--subseq` when the tab covers only part of the song (a riff, one
section). The script trims silence on both sides, aligns in chroma space
with an onset-weighted feature (a lightweight DLNCO), warps the tab's note
times onto the recording's timeline, and scores.

## Reading the numbers

- **DTW cost/step** is the same-song confidence — lower is better. It has
  no universal threshold; calibrate once against a known-good pair. On the
  bundled synthetic fixtures a matching tab scores **0.075** and a wrong
  song **0.69** — the separation is roughly an order of magnitude, not a
  close call. If the confidence is in wrong-song territory, stop: the
  note-level scores below are meaningless.
- **Onset+pitch F1** at the MIREX tolerances (onset ±50 ms, pitch
  ±50 cents, offsets ignored) is the headline faithfulness number:
  **≥ 0.9 excellent** (at the ceiling of what transcribers resolve),
  **0.7–0.9 usable with errors**, **< 0.5 substantially unfaithful**.
- **Per-quarter F1** localizes the damage — a global score hides one wrong
  section; a bad quarter says where to look.
- **The ceiling is the transcriber, not the tab.** Basic Pitch itself lands
  around 0.7–0.9 F1 on guitar, so scores are a *lower bound* on tab
  faithfulness. Calibrate with a tab you know is right before judging one
  you suspect is wrong, and quote scores relative to that calibration.
- Tabs are often written an octave off. Onset F1 far above onset+pitch F1
  with clean quarters suggests octave errors rather than wrong notes; see
  the octave note in `references/alignment-and-scoring.md`.

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
