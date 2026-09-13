#!/usr/bin/env python3
"""Find which seconds of a source sample an Ableton arrangement clip plays.

Reads a Live set (.als, gzip-compressed XML), finds an audio track by name,
lists its arrangement clips, and maps each clip's loop region through the
clip's warp markers to sample seconds. That region is what to cut out of
the raw sample with ffmpeg; it is the "isolated track" without rendering.

    python als_clip_region.py SET.als --track "REAL 5"
    python als_clip_region.py SET.als --track "REAL 5" --json
    python als_clip_region.py SET.als --track "REAL 5" --check-region 136.0 151.0
    python als_clip_region.py SET.als --track "REAL 5" --tempo 120

Assumptions, printed as warnings when they matter:
- 4/4 unless --beats-per-bar is given (bar numbers only; seconds are exact).
- Beyond the last warp marker the sample continues at the last segment's
  tempo. Before the first marker, at the song tempo.
- An unwarped clip's loop positions are in seconds; it plays at 1:1, so its
  region is that offset plus the arrangement length in seconds. That
  conversion uses the song tempo, so a saved tempo that no longer matches the
  open session silently scales every unwarped region: check the printed tempo
  against Live and override it with --tempo when they disagree.
- PitchCoarse/PitchFine are reported; a non-zero value means the audible
  pitch differs from the sample's, so transcribe the shifted version.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import xml.etree.ElementTree as ET


def _val(el, path, default=None):
    node = el.find(path)
    return node.get("Value") if node is not None else default


def beat_to_sec(beat: float, markers: list[tuple[float, float]], song_tempo: float) -> float:
    """Piecewise-linear map from clip beat time to sample seconds via warp markers."""
    if not markers:
        return beat * 60.0 / song_tempo
    markers = sorted(markers)  # (beat, sec)
    if beat <= markers[0][0]:
        return markers[0][1] - (markers[0][0] - beat) * 60.0 / song_tempo
    for (b0, s0), (b1, s1) in zip(markers, markers[1:]):
        if b0 <= beat <= b1:
            if b1 == b0:
                return s0
            return s0 + (beat - b0) * (s1 - s0) / (b1 - b0)
    (b0, s0), (b1, s1) = markers[-2], markers[-1]
    slope = (s1 - s0) / (b1 - b0) if b1 != b0 else 60.0 / song_tempo
    return s1 + (beat - b1) * slope


def load_set(path: str) -> ET.Element:
    with gzip.open(path, "rb") as fh:
        return ET.fromstring(fh.read())


def find_tracks(root: ET.Element, needle: str) -> list[ET.Element]:
    out = []
    for t in root.iter("AudioTrack"):
        name = _val(t, "Name/EffectiveName", "") or ""
        if needle.lower() in name.lower():
            out.append(t)
    return out


def arrangement_clips(track: ET.Element):
    """Audible arrangement clips only. Live 12 also stores alternate takes as
    AudioClip elements under TakeLanes; they are silent unless promoted, so a
    naive iter("AudioClip") double-counts them (measured: three whole-take
    clips summed under a comped bridge)."""
    parent = {c: p for p in track.iter() for c in p}
    for c in track.iter("AudioClip"):
        e = parent.get(c)
        in_take_lane = False
        while e is not None and e is not track:
            if e.tag == "TakeLane":
                in_take_lane = True
                break
            e = parent.get(e)
        if not in_take_lane:
            yield c


def song_tempo(root: ET.Element, default: float = 120.0) -> float:
    """The transport tempo, read from the main/master track rather than the first
    Tempo element in the document (devices carry their own Tempo/Manual)."""
    for main in ("MainTrack", "MasterTrack"):
        node = root.find(f".//{main}")
        if node is None:
            continue
        for tempo in node.iter("Tempo"):
            value = _val(tempo, "Manual")
            if value is not None:
                return float(value)
    value = _val(root, ".//Tempo/Manual")
    return float(value) if value is not None else default


def clip_regions(track: ET.Element, song_tempo: float, beats_per_bar: int) -> list[dict]:
    regions = []
    for c in arrangement_clips(track):
        start = float(c.get("Time", _val(c, "CurrentStart", 0)))
        end = float(_val(c, "CurrentEnd", start))
        loop_start = float(_val(c, "Loop/LoopStart", 0))
        start_rel = float(_val(c, "Loop/StartRelative", 0))
        play_from = loop_start + start_rel
        length_beats = end - start
        markers = [
            (float(m.get("BeatTime")), float(m.get("SecTime")))
            for m in c.iter("WarpMarker")
            if m.get("BeatTime") is not None and m.get("SecTime") is not None
        ]
        warped = (_val(c, "IsWarped", "true") or "true").lower() == "true"
        if warped:
            s0 = beat_to_sec(play_from, markers, song_tempo)
            s1 = beat_to_sec(play_from + length_beats, markers, song_tempo)
        else:
            # An unwarped clip stores LoopStart/StartRelative in SECONDS of the
            # sample, and plays at 1:1, so its region is that offset plus the
            # arrangement length in seconds. (Measured: treating the value as
            # beats halved every unwarped region at 120 BPM.)
            s0 = play_from
            s1 = play_from + length_beats * 60.0 / song_tempo
        fr = c.find("SampleRef/FileRef")
        regions.append(
            {
                "clip_name": _val(c, "Name", ""),
                "arr_start_beat": start,
                "arr_end_beat": end,
                "arr_start_bar": start / beats_per_bar + 1,
                "arr_end_bar": end / beats_per_bar + 1,
                "loop_start_beat": loop_start,
                "loop_end_beat": float(_val(c, "Loop/LoopEnd", 0)),
                "start_relative": start_rel,
                "sample_start_s": round(s0, 3),
                "sample_end_s": round(s1, 3),
                "sample_len_s": round(s1 - s0, 3),
                "warped": warped,
                "warp_markers": [{"beat": b, "sec": s} for b, s in sorted(markers)],
                "muted": (_val(c, "Disabled", "false") or "false").lower() == "true",
                "pitch_coarse": int(float(_val(c, "PitchCoarse", 0) or 0)),
                "pitch_fine": int(float(_val(c, "PitchFine", 0) or 0)),
                "gain": float(_val(c, "SampleVolume", 1) or 1),
                "sample_path": _val(fr, "Path") if fr is not None else None,
                "sample_relpath": _val(fr, "RelativePath") if fr is not None else None,
            }
        )
    return regions


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("als")
    ap.add_argument("--track", required=True, help="case-insensitive substring of the track name")
    ap.add_argument(
        "--track-index",
        type=int,
        help="when several tracks match --track, pick this one (1-based, in set order)",
    )
    ap.add_argument("--beats-per-bar", type=int, default=4)
    ap.add_argument("--json", action="store_true", help="print machine-readable output")
    ap.add_argument(
        "--tempo",
        type=float,
        help="override the set's saved tempo (use Live's live tempo when the saved one is stale)",
    )
    ap.add_argument(
        "--check-region",
        nargs=2,
        type=float,
        metavar=("START_S", "END_S"),
        help="assert the first unmuted clip plays exactly this sample region (±5 ms)",
    )
    args = ap.parse_args(argv)

    root = load_set(args.als)
    tempo = args.tempo if args.tempo else song_tempo(root)
    tracks = find_tracks(root, args.track)
    if not tracks:
        print(f"ERROR: no audio track name contains {args.track!r}", file=sys.stderr)
        return 2
    if args.track_index is not None:
        if not 1 <= args.track_index <= len(tracks):
            print(
                f"ERROR: --track-index {args.track_index} out of range; {len(tracks)} track(s) match",
                file=sys.stderr,
            )
            return 2
        track = tracks[args.track_index - 1]
    else:
        if len(tracks) > 1:
            names = [_val(t, "Name/EffectiveName", "") for t in tracks]
            print(
                f"WARNING: {len(tracks)} tracks match; using the first: {names}. "
                "Pass --track-index to choose.",
                file=sys.stderr,
            )
        track = tracks[0]
    regions = clip_regions(track, tempo, args.beats_per_bar)
    result = {"als": args.als, "tempo": tempo, "track": _val(track, "Name/EffectiveName", ""), "clips": regions}

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"set: {args.als}\ntempo: {tempo}\ntrack: {result['track']}\nclips: {len(regions)}")
        for i, r in enumerate(regions, 1):
            flag = " [MUTED]" if r["muted"] else ""
            print(
                f"  {i}. {r['clip_name']!r}{flag} arrangement bars {r['arr_start_bar']:.2f}-{r['arr_end_bar']:.2f} "
                f"(beats {r['arr_start_beat']:g}-{r['arr_end_beat']:g}) plays sample "
                f"start_s={r['sample_start_s']:.3f} end_s={r['sample_end_s']:.3f} len_s={r['sample_len_s']:.3f} "
                f"warped={r['warped']} pitch={r['pitch_coarse']:+d}st{r['pitch_fine']:+d}c"
            )
            print(f"     sample: {r['sample_path']}")
            if r["pitch_coarse"] or r["pitch_fine"]:
                print("     WARNING: clip is pitch-shifted; the audible pitch is not the sample's pitch")
            if len(r["warp_markers"]) > 2:
                print(f"     note: {len(r['warp_markers'])} warp markers; timing inside the region is not uniform")
        if regions:
            r = next((x for x in regions if not x["muted"]), regions[0])
            print(
                "cut with: ffmpeg -y -ss {s:.3f} -to {e:.3f} -i \"{p}\" -c:a pcm_s24le OUT.wav".format(
                    s=r["sample_start_s"], e=r["sample_end_s"], p=r["sample_path"]
                )
            )

    if args.check_region:
        live = [r for r in regions if not r["muted"]] or regions
        if not live:
            print("REGION CHECK FAILED: no clips")
            return 1
        r = live[0]
        s, e = args.check_region
        if abs(r["sample_start_s"] - s) <= 0.005 and abs(r["sample_end_s"] - e) <= 0.005:
            print(f"REGION CHECK PASSED: {r['sample_start_s']:.3f}-{r['sample_end_s']:.3f} s")
            return 0
        print(f"REGION CHECK FAILED: measured {r['sample_start_s']:.3f}-{r['sample_end_s']:.3f} s, expected {s:.3f}-{e:.3f} s")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
