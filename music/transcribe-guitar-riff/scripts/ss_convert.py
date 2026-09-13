#!/usr/bin/env python3
"""Convert a Songsterr track JSON to our spec, and our spec back to that shape.

Songsterr's model is better than the one this pipeline started with, in three
ways worth stealing:

1. **Rhythm is a closed vocabulary.** A beat carries `duration:[num,den]` plus
   `type` (the note value: 1,2,4,8,16,32), optional `dots` and optional
   `tuplet`. It is never an onset-to-onset float. Our first tab had durations
   like "1.75 to 2.25" because it measured gaps between attacks; that is how a
   tab ends up unreadable even when the pitches are right.
2. **Tempo is a map, not a number.** `automations.tempo` is a list of
   `{measure, bpm, linear}`. Assuming one tempo for a whole song is what made
   this project read the intro at 86 BPM when it is 162 (= 2 x 81.33).
3. **Rests are first-class beats**, so a bar always sums to its signature.

Strings are indexed from the HIGH string: `tuning[0]` is the highest course.
A note is `{string, fret}` and its pitch is `tuning[string] + fret`.

    python ss_convert.py to-spec TRACK.json --offset 16 --out gtr.spec
    python ss_convert.py tempo-map TRACK.json
    python ss_convert.py grid USERAUDIO.json --out bars.json
"""
from __future__ import annotations

import argparse
import json
from fractions import Fraction

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# The note values Songsterr's editor offers, which is the set a readable tab
# draws from. Anything outside it is a sign the rhythm was measured rather than
# decided.
NOTE_TYPES = [1, 2, 4, 8, 16, 32, 64]
TUPLETS = [3, 5, 6, 7, 9, 10, 11, 12, 13]


def name_of(midi: int) -> str:
    return f"{NAMES[midi % 12]}{midi // 12 - 1}"


def beat_length(beat) -> Fraction:
    """Length in quarter notes, from the declared duration fraction."""
    num, den = beat.get("duration", [1, 4])
    return Fraction(int(num), int(den)) * 4


def to_spec(track, offset=0, beats_per_bar=4, include_rests=False):
    """Songsterr track -> our 'bar start end notes' lines, in arrangement bars."""
    tuning = track["tuning"]
    lines = []
    for index, measure in enumerate(track.get("measures", [])):
        bar = index + 1 - offset
        for voice in measure.get("voices", []):
            pos = Fraction(0)
            for beat in voice.get("beats", []):
                length = beat_length(beat)
                notes = [n for n in beat.get("notes", []) if n.get("fret") is not None and not n.get("rest")]
                if notes:
                    midis = sorted(tuning[n["string"]] + n["fret"] for n in notes)
                    lines.append(
                        f"{bar} {float(pos) + 1:.4f} {float(pos + length) + 1:.4f} "
                        + " ".join(name_of(m) for m in midis)
                    )
                elif include_rests:
                    lines.append(f"{bar} {float(pos) + 1:.4f} {float(pos + length) + 1:.4f} r")
                pos += length
    return lines


DUR_TOKEN = {1:"1", 2:"2", 4:"4", 8:"8", 16:"16", 32:"32", 64:"64"}


def to_riff(track, n_bars=None, prefer_string=None, max_fret=24,
            transpose=0, transpose_from_bar=1, prefer_to_bar=None):
    """Songsterr track -> gp_tab riff notation, keeping THEIR string and fret.

    Re-deriving the fretting from pitch throws away the thing that makes a tab
    playable. Songsterr puts this song's intro on one string at frets 12/11/16/15
    where a pitch-only solver scattered it over three strings; the player reads
    the first and fights the second. Both number strings from the high string,
    so the index maps straight across (+1 for gp_tab's 1-based strings).
    """
    tuning = track["tuning"]
    bars = []
    measures = track.get("measures", [])
    if n_bars:
        measures = measures[:n_bars]
    for bar_index, measure in enumerate(measures, start=1):
        beats_out = []
        voice = (measure.get("voices") or [{}])[0]
        for beat in voice.get("beats", []):
            num, den = beat.get("duration", [1, 4])
            note_type = beat.get("type") or den
            token = DUR_TOKEN.get(int(note_type), "4")
            if beat.get("dots"):
                token += "." * int(beat["dots"])
            # Tuplets change the length without changing the note value, so
            # dropping them silently makes the bar overflow. Songsterr's rhythm
            # track uses 16th triplets (duration [1,24] with type 16, tuplet 3);
            # emitting those as plain 16ths made six bars run long.
            tup = beat.get("tuplet")
            n_tup = tup.get("n", tup) if isinstance(tup, dict) else tup
            if n_tup:
                if int(n_tup) == 3:
                    token += "t"
                else:
                    raise SystemExit(
                        f"measure carries a {n_tup}-tuplet, which the riff notation "
                        f"cannot express; handle it before converting"
                    )
            played = [n for n in beat.get("notes", []) if n.get("fret") is not None and not n.get("rest")]
            if not played:
                beats_out.append(f"{token}:r")
                continue
            parts = []
            for n in sorted(played, key=lambda x: x["string"]):
                # Optionally re-finger onto one string, keeping the pitch. The
                # screenshot of this song's intro plays it all on the C2 string
                # at frets 12/11/16/15 rather than crossing from F2 to C2; same
                # notes, one hand position, far easier to read.
                # Shift a section that the source transcribed in the wrong key.
                if transpose and bar_index >= transpose_from_bar:
                    n = dict(n, fret=n["fret"] + transpose)
                    # Transposing up can push a high note past the last fret.
                    # Move it to a lower-pitched string (higher index) so the
                    # PITCH is preserved rather than the position, and fail
                    # loudly if no string can hold it.
                    if n["fret"] > max_fret:
                        pitch = tuning[n["string"]] + n["fret"]
                        options = [
                            (abs(c - n["string"]), c, pitch - tuning[c])
                            for c in range(len(tuning))
                            if 0 <= pitch - tuning[c] <= max_fret
                        ]
                        if options:
                            _, cand, f = min(options)
                            n = dict(n, string=cand, fret=f)
                        else:
                            raise SystemExit(
                                f"bar {bar_index}: transposing puts pitch {pitch} beyond "
                                f"fret {max_fret} on every string"
                            )
                use_prefer = (prefer_string is not None
                              and (prefer_to_bar is None or bar_index <= prefer_to_bar))
                if use_prefer and n["string"] != prefer_string:
                    pitch = tuning[n["string"]] + n["fret"]
                    fret = pitch - tuning[prefer_string]
                    if 0 <= fret <= max_fret:
                        n = dict(n, string=prefer_string, fret=fret)
                suffix = ""
                if n.get("slide"):
                    suffix += "/"
                if n.get("bend"):
                    suffix += "b"
                if n.get("harmonic"):
                    suffix += "o"
                if n.get("palmMute") or beat.get("palmMute"):
                    suffix += "m"
                if n.get("vibrato") or beat.get("vibrato"):
                    suffix += "~"
                if n.get("letRing") or beat.get("letRing"):
                    suffix += "l"
                if n.get("dead"):
                    suffix += "x"
                if n.get("tie"):
                    suffix += "-"
                parts.append(f"{n['string'] + 1}.{n['fret']}{suffix}")
            beats_out.append(f"{token}:" + "+".join(parts))
        bars.append(" ".join(beats_out) if beats_out else "1:r")
    while n_bars and len(bars) < n_bars:
        bars.append("1:r")
    return " | ".join(bars)


def tempo_map(track):
    """[{measure, bpm, linear}] in Songsterr's own 0-based measure numbering."""
    return (track.get("automations") or {}).get("tempo", [])


def bar_grid(useraudio):
    """Per-bar onset seconds measured from the audio, plus the BPM each implies.

    This is the artifact worth copying most: a real per-bar grid absorbs the
    performance's own drift, where a single BPM forces you to explain drift away
    as 'human wobble' - which this project did, wrongly, for 8 bars.
    """
    points = useraudio.get("points") or []
    out = []
    for i, t in enumerate(points):
        row = {"bar": i + 1, "onset_s": t}
        if i + 1 < len(points):
            span = points[i + 1] - t
            row["span_s"] = round(span, 4)
            row["implied_bpm"] = round(240 / span, 2) if span > 0 else None
        out.append(row)
    return out


def check_durations(track):
    """Every beat's duration must come from the closed vocabulary."""
    bad = []
    for index, measure in enumerate(track.get("measures", [])):
        for voice in measure.get("voices", []):
            for beat in voice.get("beats", []):
                num, den = beat.get("duration", [1, 4])
                t = beat.get("type")
                ok = t in NOTE_TYPES
                frac = Fraction(int(num), int(den))
                base = Fraction(1, t) if t else None
                if base is not None:
                    dots = beat.get("dots", 0) or 0
                    expect = base * (2 - Fraction(1, 2 ** dots)) if dots else base
                    tup = beat.get("tuplet")
                    if tup:
                        n = tup.get("n", tup) if isinstance(tup, dict) else tup
                        if isinstance(n, int) and n in TUPLETS:
                            ok = ok and True
                            expect = None      # tuplet scaling varies; do not over-claim
                    if expect is not None and frac != expect:
                        ok = False
                if not ok:
                    bad.append({"measure": index + 1, "duration": [num, den],
                                "type": t, "dots": beat.get("dots"), "tuplet": beat.get("tuplet")})
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["to-spec", "to-riff", "tempo-map", "grid", "check-durations", "summary"])
    ap.add_argument("path")
    ap.add_argument("--offset", type=int, default=0,
                    help="subtract this from Songsterr bar numbers to get arrangement bars")
    ap.add_argument("--rests", action="store_true")
    ap.add_argument("--transpose", type=int, default=0,
                    help="add this many semitones (as frets) from --transpose-from-bar on")
    ap.add_argument("--transpose-from-bar", type=int, default=1)
    ap.add_argument("--prefer-to-bar", type=int, default=0,
                    help="only apply --prefer-string up to this bar")
    ap.add_argument("--prefer-string", type=int, default=-1,
                    help="re-finger onto this Songsterr string index where reachable "
                         "(5 = the C2 string on this 8-string tuning)")
    ap.add_argument("--bars", type=int, default=0, help="pad/trim to this many bars (to-riff)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    data = json.load(open(args.path))
    failed = False

    if args.mode == "grid":
        rows = bar_grid(data)
        text = json.dumps(rows, indent=2)
        print(f"{len(rows)} bars, {rows[-1]['onset_s']:.2f}s total" if rows else "no points")
        for r in rows[:3] + rows[-2:]:
            print(f"  bar {r['bar']:>4d} at {r['onset_s']:8.3f}s  {r.get('implied_bpm')}")
    elif args.mode == "tempo-map":
        rows = tempo_map(data)
        text = json.dumps(rows, indent=2)
        for r in rows:
            print(f"  from measure {r['measure'] + 1}: {r['bpm']} BPM"
                  f"{' (linear ramp)' if r.get('linear') else ''}")
    elif args.mode == "check-durations":
        bad = check_durations(data)
        text = json.dumps(bad, indent=2)
        print(f"{len(bad)} beats whose duration does not match their declared note value")
        for b in bad[:10]:
            print("  ", b)
        # Exit non-zero on a finding so this is usable as a gate. A checker that
        # always succeeds gets wired into a pipeline and then certifies nothing.
        failed = bool(bad)
    elif args.mode == "summary":
        t = data
        text = ""
        print(f"name={t.get('name')!r} instrument={t.get('instrument')!r} "
              f"strings={t.get('strings')} frets={t.get('frets')}")
        print(f"tuning (high->low) = {t.get('tuning')}")
        print(f"measures = {len(t.get('measures', []))}")
        for r in tempo_map(t):
            print(f"  tempo from measure {r['measure'] + 1}: {r['bpm']}")
        kinds = {}
        for m in t.get("measures", []):
            for v in m.get("voices", []):
                for b in v.get("beats", []):
                    key = (b.get("type"), b.get("dots"), bool(b.get("tuplet")), bool(b.get("rest")))
                    kinds[key] = kinds.get(key, 0) + 1
        print("beat kinds (type, dots, tuplet, rest) -> count:")
        for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
            print(f"   {k} -> {n}")
    elif args.mode == "to-riff":
        text = to_riff(data, args.bars or None,
                       args.prefer_string if args.prefer_string >= 0 else None,
                       transpose=args.transpose,
                       transpose_from_bar=args.transpose_from_bar,
                       prefer_to_bar=args.prefer_to_bar or None)
        print(f"{len(text.split('|'))} bars of riff notation, Songsterr's own fretting kept")
    else:
        lines = to_spec(data, args.offset, include_rests=args.rests)
        text = "\n".join(lines)
        print(f"{len(lines)} spec lines (arrangement bars = songsterr bar - {args.offset})")

    if args.out:
        open(args.out, "w").write(text + ("\n" if text else ""))
        print(f"wrote {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
