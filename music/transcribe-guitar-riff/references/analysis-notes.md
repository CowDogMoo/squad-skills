# Analysis notes: why the pipeline is shaped this way

Read this when a step behaves unexpectedly or when you need to defend a
pitch decision. `SKILL.md` is the runbook; this is the reasoning.

## Why not a pitch tracker

pYIN (and other monophonic f0 trackers) returned "unvoiced" on 100% of
frames of a tremolo-picked, high-gain 8-string riff at 120 BPM. Eight
attacks per second, a harmonic series flattened by the waveshaper, and two
strings ringing at once break the periodicity assumption. Do not spend time
tuning `fmin`/`fmax`/frame sizes; it is the wrong model. The spectrogram
pass is the one that worked on the first try.

## The salience pass

`riff_salience.py` computes a constant-Q transform (C1 upward, 3 bins per
semitone), then `librosa.salience` sums energy at 1f, 2f, 3f, 4f, 5f back
onto each candidate f with decreasing weights. Distorted guitar has strong
harmonics, so the fundamental collects the most energy even when its own
bin is not the loudest. The result is averaged over each rhythmic grid slot
(sixteenths by default) and the local maxima are ranked.

Two filters are on by default:

- **On-grid only.** With 3 bins per semitone, a tuned note lands on the
  0-cent bin; junk lands on any bin. Dropping the +-33-cent bins removes two
  thirds of the intermodulation clutter without touching played notes. If
  the guitar is not at A440, pass `--all-peaks` and read the cents column.
- **No octave collapsing.** Folding a peak onto a strong peak one octave
  below sounds right in theory, but heavy distortion puts subharmonic energy
  everywhere and the fold deletes real upper-voice notes (measured: F4 and
  D4 vanished from the synthetic control). It exists as `--collapse-octaves`
  for cleaner sources only.

The per-16th table is the evidence. The per-beat summary is a reading aid:
notes that sit in the top two of at least half the beat's slots. A dyad
shows up as two stable notes per beat; a single line as one.

## Deciding the octave

Every fundamental f also lights up 2f (f's even harmonics are 2f's
harmonics), so A#3 and A#4 both rank high on an A#3 note. The evidence that
decides:

1. The long-term spectrum peak for the true fundamental sits within a few
   cents of equal temperament. In the reference riff every played note was
   within +-14 cents; the "A#2" at 118.4 Hz was +28 cents sharp of the tuned
   open string (116.54 Hz).
2. A distortion **difference tone** sits at |a - b| of two other components.
   118.4 = 349.9 (F4) - 231.5 (A#3), exactly. The script flags a peak only
   when it is BOTH off-grid by more than 20 cents AND equals a difference of
   two other peaks; either alone is common by coincidence.
3. The upper voice pins the register: D4 (296 Hz) and F#4 (371 Hz) are not
   harmonics of any lower pedal, so the pedal they sit above is A#3, not
   A#2.

State the octave decision and its evidence in the README you deliver; the
user cannot hear the spectrogram.

## Tempo grid

Everything is sliced on the DAW grid, so the tempo and the downbeat offset
must be right before the per-slot table means anything. Take the tempo
from the set. If the clip does not start on beat 1 (the reference clip
entered on beat 3 of bar 70), either cut the export on a downbeat or pass
`--offset` so slot labels line up with the arrangement. When the tempo is
unknown, run once without `--bpm`, read the estimate, then rerun with it
fixed.

## basic-pitch as a second opinion

Spotify's basic-pitch gives a polyphonic MIDI in one command and agreed
with the salience reading on every dyad, with noise (158 raw notes for a
33-note riff). Install gotchas as of 2026-09: it needs Python <= 3.11 and
`setuptools<81` (resampy imports `pkg_resources`), so create a separate
venv: `uv venv -p 3.11 bpenv && VIRTUAL_ENV=bpenv uv pip install
"basic-pitch[onnx]" "setuptools<81"`. Use `melodia_trick=True`,
`minimum_frequency=30`, `minimum_note_length=80`. Treat its output as
corroboration; the cleaned reading is authored from the salience table.

## Ableton specifics

- **Clip region.** The arrangement clip's loop start/end are in clip beats;
  warp markers map beats to sample seconds. `als_clip_region.py` does the
  piecewise-linear map. The set on disk can lag the open session (unsaved
  edits); the region is still right if the clip itself was not moved, and
  `get_arrangement_info` from the MCP shows the live bars to compare.
- **Cut, do not render.** A render goes through EQ, compression, widening,
  and limiting on the track. The raw sample region is the honest input for
  pitch work, and cutting it is bit-exact (verify with `ffmpeg -f md5`).
- **Arrangement loop.** `set_arrangement_loop` fails with "Cannot set the
  Loopstart behind the Songlength" when the current loop is long: the
  remote script sets start before length. Set a short loop at bar 1 first,
  then the real one.
- **No note read-back.** The AbletonMCP remote script (2026-09) has no
  command that returns notes from any clip. Add notes to a session clip,
  duplicate it to the arrangement, and verify by opening the clip in Live's
  editor (screen control) if a reviewer demands direct evidence.
- **Live's octave naming** is C3 = MIDI 60, so MIDI 58 shows as A#2 in the
  clip editor while the analysis calls it A#3. Say which convention a number
  uses.

## Tab output

The guitar-pro skill owns file writing. Eight or more strings cannot be
written to `.gp5`; the native `.gp` route needs alphaTab installed next to
that skill's scripts. Verify the written file by loading it back with
alphaTab (string count, measure count, tuning MIDI numbers) and by the
piano-roll comparison against the cleaned MIDI, not by trusting the writer.
