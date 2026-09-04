# Alignment and scoring choices

Distilled from a 2026-09-04 deep-research pass over the music-synchronization
and transcription-evaluation literature. This file is why `compare_tab.py`
does what it does, and what to reach for when it isn't enough.

## Features and alignment

- **Chroma both sides, no rendering.** `pretty_midi.get_chroma()` computes
  chroma straight from the MIDI, and chroma is timbre-robust, so no
  soundfont choice enters the comparison. Rendering only matters for
  onset/spectral-flux features.
- **Onset channel (lightweight DLNCO).** Plain chroma gives DTW no gradient
  inside a sustained note, so the path wanders the plateau and note onsets
  smear past the ±50 ms tolerance — measured on the bundled fixtures: F1
  0.67 with plain chroma, 1.0 with the decaying half-wave-rectified
  chroma-onset channel stacked on. This is the idea behind DLNCO features
  (Ewert/Müller/Grosche, ICASSP 2009), which cut mean sync error from
  ~44 ms to ~19 ms on piano:
  <https://www.researchgate.net/publication/224461222_High_resolution_audio_synchronization_using_chroma_onset_features>
- **Silence handling.** DTW must start and end at the corners, so a
  count-in or trailing ring smears the first/last note's mapping by half
  the silent run. The script trims both sides and adds the offsets back
  after warping. Two boundary facts cost real notes before they were
  handled: the last chroma frame starts one hop before the tab ends, and
  `pretty_midi.adjust_times` silently drops any note whose *end* lies past
  the last anchor — the mapping is therefore extrapolated to the true tab
  end at the local tempo.
- **Scaling up.** For full-length songs or batch work, `synctoolbox`
  (Müller's group) is the reference implementation — MrMsDTW handles
  recordings plain O(N·M) DTW cannot, with the real DLNCO:
  <https://github.com/meinardmueller/synctoolbox>. The librosa DTW used
  here is fine to a few minutes of audio:
  <https://librosa.org/doc/0.10.2/auto_examples/plot_music_sync.html>
- **Structure mismatches.** `--subseq` (subsequence DTW) covers a partial
  tab. For repeats/jumps, JumpDTW needs block boundaries — which a Guitar
  Pro file provides explicitly:
  <https://www.audiolabs-erlangen.de/content/05_fau/professor/00_mueller/03_publications/2010_FremereyMuellerClausen_PartialSync_ISMIR.pdf>

## The confidence score

The normalized DTW cost is a calibrated same-song confidence — the Raffel &
Ellis recipe (log-CQT, cosine distance, penalty = median pairwise distance,
gully 0.96) achieved **ROC AUC 0.981** against human right-song/wrong-song
judgments and built the Lakh MIDI Dataset:
<https://colinraffel.com/publications/icassp2016optimizing.pdf>,
<https://github.com/craffel/midi-dataset>. The script's cost/step is the
same quantity in simpler clothes; on the bundled fixtures, matching scores
0.075 vs 0.69 for a wrong song. No universal threshold exists — calibrate
on a known pair. The essentia cover-song chain (Serra's Qmax) is the
zero-ML alternative gate: <https://essentia.upf.edu/tutorial_similarity_cover.html>

## Scoring conventions

- **`mir_eval.transcription`** is the standard scorer: note-level
  precision/recall/F-measure with bipartite matching. MIREX conventions:
  onset tolerance **±50 ms**, pitch tolerance **50 cents**,
  `offset_ratio=None` for the common onset+pitch-only variant:
  <https://mir-eval.readthedocs.io/latest/api/transcription.html>
- **Octave errors:** tabs are routinely written an octave off. For lead
  lines, `mir_eval.melody`'s Raw Chroma Accuracy forgives octaves where Raw
  Pitch Accuracy does not — a big onset-vs-pitch F1 gap is the same signal
  at note level.
- **Per-section scores:** Raffel's own qualitative finding is that global
  scores under-penalize one missing part or sparse embellishments; report
  per-quarter (or per-Guitar-Pro-section) F1 to expose locally wrong
  passages.

## Transcribers and their ceilings

- **Basic Pitch** (Spotify) — the practical default, `pip install
  basic-pitch`: <https://github.com/spotify/basic-pitch>
- **YourMT3+ / MT3** — better on full-band mixes (MT3 onset F1 ≈ 0.90 on
  GuitarSet): <https://github.com/mimbres/YourMT3>
- **crepe** — monophonic f0 for isolated lead lines:
  <https://github.com/marl/crepe>
- Guitar-specific string/fret research and the natural validation corpus
  (GOAT: 5.9 h paired DI guitar + Guitar Pro tabs):
  <https://arxiv.org/abs/2509.22655>; GuitarSet:
  <https://zenodo.org/records/3371780>

Transcriber F1 on guitar sits around 0.7–0.9, so every score this pipeline
produces is a lower bound on tab faithfulness. The discipline that keeps
reports honest: calibrate on a known-good tab of similar material first,
and interpret everything relative to that ceiling.
