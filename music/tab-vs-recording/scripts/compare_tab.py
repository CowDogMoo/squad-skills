#!/usr/bin/env python3
"""Score how faithful a MIDI guitar tab is to a real recording of the song.

Aligns the tab's MIDI to the recording in chroma space (no audio rendering
needed), reports the normalized DTW cost as a same-song confidence, warps the
tab's note times onto the recording's timeline, and - when a transcription of
the recording is supplied - scores note-level precision/recall/F-measure at
the MIREX tolerances (onset +-50 ms, pitch +-50 cents, offsets ignored) plus
per-quarter F1 to localize wrong passages.

Deps: numpy scipy soundfile librosa pretty_midi mir_eval
  uv run --with numpy --with scipy --with soundfile --with librosa \\
    --with pretty_midi --with mir_eval scripts/compare_tab.py TAB.mid SONG.wav \\
    [--ref-midi SONG_transcribed.mid] [--subseq] [--json report.json]

Get the transcription with Basic Pitch (`pip install basic-pitch`, then
`basic-pitch <out-dir> SONG.wav`) or any transcriber that writes MIDI.
Without --ref-midi only the alignment confidence and chroma similarity are
reported. The transcriber's own accuracy (~0.7-0.9 F1 on guitar) bounds the
ceiling, so calibrate with a known-good tab before trusting absolute numbers.
"""

import argparse
import json
import sys

import librosa
import mir_eval
import numpy as np
import pretty_midi

SR = 22050
HOP = 512


def unit_columns(chroma):
    """L2-normalize chroma columns; silent frames become uniform vectors so
    cosine distance stays defined instead of going NaN."""
    chroma = chroma.astype(np.float64)
    norms = np.linalg.norm(chroma, axis=0)
    silent = norms < 1e-9
    chroma[:, silent] = 1.0 / np.sqrt(chroma.shape[0])
    norms[silent] = 1.0
    return chroma / norms


def sync_features(chroma, gain=2.0):
    """Stack a decaying half-wave-rectified chroma-onset channel onto the
    chroma (a lightweight DLNCO, per Ewert/Mueller): sustained notes give DTW
    no gradient inside the note, so attacks carry extra weight to pin the
    warping path at onsets instead of letting it wander the plateau."""
    onset = np.maximum(np.diff(chroma, axis=1, prepend=chroma[:, :1]), 0.0)
    tail = np.array([1.0, 0.8, 0.6, 0.4, 0.2])
    onset = np.apply_along_axis(lambda r: np.convolve(r, tail)[: r.size], 1, onset)
    return unit_columns(np.vstack([chroma, gain * onset]))


def load_notes(pm, label):
    notes = [n for inst in pm.instruments if not inst.is_drum for n in inst.notes]
    if not notes:
        sys.exit(f"{label}: no non-drum notes found")
    notes.sort(key=lambda n: (n.start, n.pitch))
    intervals = np.array([[n.start, max(n.end, n.start + 0.05)] for n in notes])
    pitches = np.array([440.0 * 2 ** ((n.pitch - 69) / 12.0) for n in notes])
    return intervals, pitches


def f1_for(ref_i, ref_p, est_i, est_p):
    if len(ref_i) == 0 and len(est_i) == 0:
        return None
    if len(ref_i) == 0 or len(est_i) == 0:
        return 0.0
    _, _, f, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_i, ref_p, est_i, est_p,
        onset_tolerance=0.05, pitch_tolerance=50.0, offset_ratio=None)
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tab", help="the tab as MIDI (Guitar Pro export, gp_tab.py --to-midi, ...)")
    ap.add_argument("audio", help="the recording (wav/mp3/anything librosa reads)")
    ap.add_argument("--ref-midi", help="transcription of the recording; enables note-level scoring")
    ap.add_argument("--subseq", action="store_true",
                    help="the tab covers only part of the song (subsequence DTW)")
    ap.add_argument("--json", dest="json_out", help="also write the report as JSON")
    args = ap.parse_args()

    y, _ = librosa.load(args.audio, sr=SR, mono=True)
    if not len(y):
        sys.exit(f"{args.audio}: empty audio")
    # Trim silence on both sides before aligning: DTW must start at the
    # corner, so a count-in or trailing ring smears the first/last note's
    # mapping by half the silent run. Offsets are added back after warping.
    y_t, (i0, _) = librosa.effects.trim(y)
    t_audio0 = i0 / SR
    fs_frames = SR / HOP
    chroma_audio = unit_columns(librosa.feature.chroma_cqt(y=y_t, sr=SR, hop_length=HOP))

    tab = pretty_midi.PrettyMIDI(args.tab)
    raw_tab = tab.get_chroma(fs=fs_frames)
    active = np.flatnonzero(np.linalg.norm(raw_tab, axis=0) > 1e-9)
    if len(active) < 4:
        sys.exit(f"{args.tab}: tab too short to align")
    k0 = int(active[0])
    chroma_tab = unit_columns(raw_tab[:, k0:int(active[-1]) + 1])

    D, wp = librosa.sequence.dtw(X=sync_features(chroma_tab),
                                 Y=sync_features(chroma_audio),
                                 metric="cosine", subseq=args.subseq)
    wp = np.asarray(wp)[::-1]  # ascending in time
    cost = float(D[wp[-1, 0], wp[-1, 1]] / len(wp))
    sim = float(np.mean(np.sum(chroma_tab[:, wp[:, 0]] * chroma_audio[:, wp[:, 1]], axis=0)))

    # Map tab time -> audio time: mean audio frame per tab frame, forced
    # strictly increasing so pretty_midi.adjust_times accepts it.
    u, inv = np.unique(wp[:, 0], return_inverse=True)
    audio_t = np.bincount(inv, weights=wp[:, 1] / fs_frames) / np.bincount(inv)
    audio_t = np.maximum.accumulate(audio_t) + np.arange(len(u)) * 1e-9 + t_audio0
    tab_t = (u + k0) / fs_frames
    # adjust_times drops any note whose END lies past the last anchor, and the
    # last chroma frame starts one hop before the tab ends - so extend the
    # mapping to the true end at the recent local tempo.
    tab_end = tab.get_end_time() + 1e-3
    if tab_t[-1] < tab_end:
        k = min(len(tab_t) - 1, 44)
        slope = (audio_t[-1] - audio_t[-1 - k]) / max(tab_t[-1] - tab_t[-1 - k], 1e-9)
        audio_t = np.append(audio_t, audio_t[-1] + slope * (tab_end - tab_t[-1]))
        tab_t = np.append(tab_t, tab_end)
    tab.adjust_times(tab_t, audio_t)

    span = (float(audio_t[0]), float(audio_t[-1]))
    print(f"same-song confidence: DTW cost/step {cost:.3f} "
          f"(lower = better; calibrate on a known-good pair - wrong songs score far higher)")
    print(f"chroma similarity along path: {sim:.2f}")
    print(f"tab aligned to {span[0]:.1f}-{span[1]:.1f}s of the recording"
          + (" (subsequence)" if args.subseq else ""))

    scores = None
    if args.ref_midi:
        ref_i, ref_p = load_notes(pretty_midi.PrettyMIDI(args.ref_midi), args.ref_midi)
        est_i, est_p = load_notes(tab, "warped tab")
        p_on, r_on, f_on = mir_eval.transcription.onset_precision_recall_f1(
            ref_i, est_i, onset_tolerance=0.05)
        p, r, f, _ = mir_eval.transcription.precision_recall_f1_overlap(
            ref_i, ref_p, est_i, est_p,
            onset_tolerance=0.05, pitch_tolerance=50.0, offset_ratio=None)
        quarters = np.linspace(span[0], span[1], 5)
        per_q = []
        for lo, hi in zip(quarters[:-1], quarters[1:]):
            rsel = (ref_i[:, 0] >= lo) & (ref_i[:, 0] < hi)
            esel = (est_i[:, 0] >= lo) & (est_i[:, 0] < hi)
            per_q.append(f1_for(ref_i[rsel], ref_p[rsel], est_i[esel], est_p[esel]))
        print(f"onset F1 {f_on:.2f} | onset+pitch F1 {f:.2f} (+-50 ms / 50 cents, offsets ignored)")
        print("per-quarter onset+pitch F1: "
              + "  ".join("n/a" if q is None else f"{q:.2f}" for q in per_q))
        print("ladder: >=0.9 excellent (at the transcriber ceiling), "
              "0.7-0.9 usable with errors, <0.5 substantially unfaithful")
        scores = {"p_onset": p_on, "r_onset": r_on, "f_onset": f_on,
                  "p_onset_pitch": p, "r_onset_pitch": r, "f_onset_pitch": f,
                  "per_quarter_f": per_q}
    else:
        print("no --ref-midi: alignment-only report; transcribe the recording "
              "(e.g. Basic Pitch) for note-level F-measure")

    if args.json_out:
        with open(args.json_out, "w") as fh:
            json.dump({"alignment": {"dtw_cost_per_step": cost,
                                     "chroma_similarity": sim,
                                     "subsequence": bool(args.subseq),
                                     "audio_span_s": span},
                       "scores": scores}, fh, indent=2)
        print(f"json: {args.json_out}")


if __name__ == "__main__":
    main()
