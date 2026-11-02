#!/usr/bin/env python3
"""Read a native Guitar Pro 7/8 file (.gp) with nothing but the standard library.

A .gp file is a zip whose Content/score.gpif is XML. Bars, voices, beats, notes
and rhythms are separate id-referenced tables, so one MasterBar points at one
Bar per track, each Bar at up to four Voices, each Voice at Beats, each Beat at
a Rhythm and Notes. This reader walks that graph and returns, per bar, the beats
with their position and duration in quarter notes (dots and tuplets applied) and
each note's string, fret, MIDI pitch and flags.

Use it when Node/alphaTab (scripts/gp7_tool.mjs) is not available - for example
in a shell on the user's machine - or when you need to script against the notes
in Python. It is read-only; edit in place with gp7_tool.mjs and gate the edit
with its `diff`.

    python gpif.py song.gp                      # tracks, tunings, bar count
    python gpif.py song.gp --track 1 --bars 33-36
    python gpif.py song.gp --track 0 --bars 80 --json

String numbers printed are Guitar Pro's own (1 = highest string), which is what
the user sees on screen. GPIF itself stores String 0 = LOWEST string; this
reader converts, so do not convert again.
"""

import argparse
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from fractions import Fraction as F

NV = {"Whole": F(4), "Half": F(2), "Quarter": F(1), "Eighth": F(1, 2), "16th": F(1, 4),
      "32nd": F(1, 8), "64th": F(1, 16), "128th": F(1, 32)}
NAMES = "C C# D D# E F F# G G# A A# B".split()
SKIP = {"String", "Fret", "Midi", "Tone", "Octave", "Element", "Variation", "ConcertPitch", "TransposedPitch"}


def pn(m):
    return f"{NAMES[m % 12]}{m // 12 - 1}"


class GP:
    def __init__(self, path):
        self.root = r = ET.fromstring(zipfile.ZipFile(path).read("Content/score.gpif"))
        table = lambda tag: {e.get("id"): e for e in r.find(tag)}
        self.B, self.V, self.BT, self.N, self.R = (table(t) for t in ("Bars", "Voices", "Beats", "Notes", "Rhythms"))
        self.masterbars = r.find("MasterBars").findall("MasterBar")
        self.tracks = []
        for t in r.find("Tracks"):
            p = t.find(".//Property[@name='Tuning']/Pitches")
            tun = [int(v) for v in p.text.split()] if p is not None else None  # GPIF: low string first
            self.tracks.append((t.find("Name").text, tun))

    def duration(self, rh):
        v = NV[rh.find("NoteValue").text]
        dot = rh.find("AugmentationDot")
        if dot is not None:
            v *= 2 - F(1, 2 ** int(dot.get("count")))
        tup = rh.find("PrimaryTuplet")
        if tup is not None:
            v *= F(int(tup.get("den")), int(tup.get("num")))
        return v

    def time_signature(self, bar):
        return self.masterbars[bar - 1].find("Time").text

    def beats(self, bar, track, voice=0):
        """[(pos_quarters, dur_quarters, [note dicts])] for one bar (1-based) of one track."""
        name, tun = self.tracks[track]
        nstr = len(tun) if tun else 0
        bar_id = self.masterbars[bar - 1].find("Bars").text.split()[track]
        vids = self.B[bar_id].find("Voices").text.split()
        if voice >= len(vids) or vids[voice] == "-1":
            return []
        out, pos = [], F(0)
        for bid in self.V[vids[voice]].find("Beats").text.split():
            bt = self.BT[bid]
            dur = self.duration(self.R[bt.find("Rhythm").get("ref")])
            notes = []
            if bt.find("Notes") is not None:
                for nid in bt.find("Notes").text.split():
                    n = self.N[nid]
                    props = {p.get("name"): p for p in n.iter("Property")}
                    gstr = int(props["String"][0].text)
                    fret = int(props["Fret"][0].text)
                    flags = sorted(k for k in props if k not in SKIP)
                    tie = n.find("Tie")
                    if tie is not None and tie.get("destination") == "true":
                        flags.append("tie")
                    if "Slide" in props:
                        flags[flags.index("Slide")] = "Slide=" + props["Slide"][0].text
                    notes.append(dict(string=nstr - gstr, fret=fret,
                                      midi=(tun[gstr] + fret) if tun else None, flags=flags))
            out.append((pos, dur, notes))
            pos += dur
        return out


def parse_bars(spec, nbars):
    if not spec:
        return range(1, nbars + 1)
    a, _, b = spec.partition("-")
    return range(int(a), int(b or a) + 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gp")
    ap.add_argument("--track", type=int)
    ap.add_argument("--bars")
    ap.add_argument("--voice", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    g = GP(a.gp)
    if a.track is None:
        print(f"{len(g.masterbars)} bars")
        for i, (name, tun) in enumerate(g.tracks):
            print(f"  track {i}: {name}  tuning (low->high) {' '.join(pn(t) for t in tun) if tun else '-'}")
        return
    rows = []
    for bar in parse_bars(a.bars, len(g.masterbars)):
        beats = g.beats(bar, a.track, a.voice)
        total = sum((d for _, d, _ in beats), F(0))
        if a.json:
            rows.append(dict(bar=bar, time=g.time_signature(bar), beats=[
                dict(pos=str(p), dur=str(d), notes=n) for p, d, n in beats]))
            continue
        print(f"BAR {bar}  {g.time_signature(bar)}  total {total} quarters")
        for p, d, notes in beats:
            desc = " + ".join(f"s{n['string']}f{n['fret']}({pn(n['midi']) if n['midi'] is not None else '?'})"
                              + (f"[{','.join(n['flags'])}]" if n["flags"] else "") for n in notes) or "rest"
            print(f"  {float(p) + 1:6.3f}  {str(d):5s} {desc}")
    if a.json:
        json.dump(rows, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
