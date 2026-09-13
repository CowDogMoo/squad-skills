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

## The band-limited-search trap (read this first)

The worst failure this pipeline has produced was not a close call. A tab
shipped with its entire heavy section an octave low and a second section two
octaves low, and every check passed.

The mechanism, exactly:

1. An early reading put a riff on the 8th string, F1/F#1.
2. A "confirmation" pass ran a harmonic-comb tracker over **38-100 Hz** and
   reported F1/F#1. That was written up as independent corroboration.
3. It was not independent of anything. The search band excluded every answer
   except a low one. The comb had no way to return F#2 (92.5 Hz was inside the
   band, but its own 3rd and 5th partials - the evidence that decides the
   octave - sat above 100 Hz and were never examined).
4. The real fundamental was F#2, the loudest peak in the spectrum, one cent
   flat of concert pitch. Basic Pitch, asked independently, put the riff's
   modal note at MIDI 42. The tab said MIDI 29.
5. Nothing downstream caught it: chroma-top-3 is octave-blind by construction,
   onset backing does not look at pitch at all, and the falsification control
   (transpose a semitone) is passed just as happily by a reading that is a
   perfect octave out.

**Rules that follow.** Run `octave_check.py` over a wide band before choosing
any `--fmin/--fmax`. Treat a band as a hypothesis that must already be
supported. Never let a band-limited result corroborate the register it was
configured to find. Cross-check with Basic Pitch's note histogram, which is
free and independent. And when adding an accuracy metric, ask what a
perfectly-octave-shifted tab would score on it - if the answer is "the same",
the metric cannot see the most common serious transcription error.

## Measure pitch in the fundamental band, never in a harmonic band

The trap above has a quieter second form that cost a whole round on a later job.
Asked whether a riff written on D1 was really D1, a template scored the written
note's fundamental *and its second harmonic* over 70-100 Hz and came back
preferring F#, a semitone off the right answer. The 91.6 Hz peak driving that
result was not twice anything in the part being tested - it was the other
guitar, which happened to overlap that band. Looking instead at 34-50 Hz, where
nothing else in the mix plays, gave 44.112 Hz = F1 +18 cents outright, with the
written D1's 36.71 a full 318 cents away.

So: **identify a note from the band its own fundamental lives in, chosen because
nothing else plays there.** Harmonic bands are crowded by definition - every
instrument above you has fundamentals where you have partials. If the
fundamental is genuinely unmeasurable, say so rather than substituting a
harmonic and not mentioning it.

Two habits make this cheap:

- **Calibrate the recording's pitch first, on notes already settled.** A peak at
  90.8 Hz is F#2 thirty cents flat or F2 seventy cents sharp, and only the
  reference pitch says which. Take a 65536-point FFT with parabolic peak
  interpolation over a passage whose notes are known, and check the offset is
  small before trusting any absolute call. On the job above the intro's four
  verified notes came out at +3.9, -4.1, +1.2 and -4.5 cents, which is what
  licensed every later reading.
- **Know what your metric can and cannot resolve.** Chroma similarity against
  the recording scored every candidate shift from -1 to +6; +2 and +3 tied at
  0.66 and +2 was marginally ahead on DTW cost. Chroma settled "about a minor
  third up" and nothing finer. Reporting it as though it had picked +3 would
  have been a fabricated precision. Use the coarse metric to bound the answer
  and a direct measurement to pin it.

## The easy-to-pitch note is the tell

When a transcription is wholesale wrong about a key, look for the note in it
that was easy to transcribe. A fast palm-muted chug on the bottom strings is the
hardest thing on a distorted record to pitch; a long ringing note is the easiest.
A transcriber that gets the chug wrong and the sustain right leaves a signature:
one note that does not fit the key it wrote.

On the job above, a riff was written as a D chug with a ringing A# over it. A# is
the b6 over D and the 4th over F. That single note said the music was in F before
any spectrum was computed, and the audio then agreed. It also said *how much* to
move - the chug, not the sustain - which no global transpose would have got
right.

## Structure beats per-slot accuracy

A related failure from the same job: bars the audio repeats four times were
transcribed one at a time, producing sixteen different bars. Every note was
individually defensible; the result was unplayable, and a guitarist who had
played a good tab of the song called it trash on sight.

Per-note metrics cannot see this. Two tabs with identical per-note scores can
differ by "is a riff" versus "is not a riff". `riff_cycle.py` exists for this:
find the repeating unit from the audio, fold every repetition together, read it
once, stamp it. Folding also buys about sqrt(N) signal-to-noise, so the cycle
reading is better than any single bar's reading as well as being musical.

When the fold reports that many cycle positions disagree across their own
repetitions, that is the material telling you per-slot tracking has run out of
resolution. Report it and get a reference tab; do not keep processing.

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
- **Take lanes are silent.** Live 12 keeps alternate takes as `AudioClip`
  elements under `TakeLanes`; only clips under
  `DeviceChain/MainSequencer/Sample/ArrangerAutomation/Events` sound. The
  parser skips take lanes (measured on a real set: three whole-take clips
  summed under a comped bridge, six pinch-harmonic takes stacked on one bar).
- **Unwarped clips count in seconds.** `Loop/LoopStart` and `StartRelative`
  of an unwarped clip are sample seconds, not beats; treating them as beats
  halved every unwarped region at 120 BPM and made overdubs look like they
  started mid-phrase. Warped clips go through the warp markers as before.
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
