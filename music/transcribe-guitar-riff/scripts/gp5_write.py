#!/usr/bin/env python3
"""Write a riff string to a Guitar Pro 5 file, then check the FILE, not the writer.

The input is the riff string `tab_build.py` prints: beats `DURATION:STRING.FRET`
(chords join notes with `+`, rests are `DURATION:r`), bars separated by `|`,
`#` lines ignored. Strings are numbered 1 = highest, as Guitar Pro shows them.

    python gp5_write.py riff.txt --tuning E2,A2,D3,G3,B3,E4 --bpm 120 \\
        --out tab.gp5 --midi tab.mid

After writing, it reloads the .gp5 from disk and does everything else from that
reload: the summary line (measures, tempo, tuning, notes), the MIDI export and
the ASCII tab. So `compare_rolls.py tab.mid cleaned.mid` tests the file the user
will open, and the ASCII in the report is the file's, not a hand drawing.

The .gp5 format stores a beat's strings as bit flags in one byte, so it holds
at most seven strings. For eight or more this script refuses; write a native
.gp with the guitar-pro skill instead.

It guards the three PyGuitarPro defaults that fail silently: Note.type defaults
to `rest` (notes that make no sound), Beat.status to `empty` (zero-length beats
that collapse a bar onto beat one), and a measure header needs a Measure on
every track. gp5_write also refuses a bar that does not add up to its meter.
"""
from __future__ import annotations

import argparse
import re
import sys

import guitarpro as gp
import librosa
import mido
from guitarpro import models as gpm

MAX_GP5_STRINGS = 7
QUARTER = gpm.Duration.quarterTime  # 960 ticks
TOKEN = re.compile(r"^(1|2|4|8|16|32|64)(\.|t)?:(r|\d+\.\d+(?:\+\d+\.\d+)*)$")


def note_name(midi: int) -> str:
    return librosa.midi_to_note(midi, unicode=False)


def parse_riff(text: str) -> list[list[tuple[int, str, list[tuple[int, int]]]]]:
    """Bars of (duration value, mark, [(string, fret), ...]) beats."""
    body = " ".join(ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#"))
    bars = []
    for chunk in body.split("|"):
        beats = []
        for token in chunk.split():
            m = TOKEN.match(token)
            if not m:
                raise SystemExit(f"bad riff token {token!r} (want DURATION:STRING.FRET, e.g. 16:3.3+1.2)")
            value, mark, notes = int(m.group(1)), m.group(2) or "", m.group(3)
            placed = [] if notes == "r" else [tuple(int(x) for x in n.split(".")) for n in notes.split("+")]
            beats.append((value, mark, placed))
        if beats:
            bars.append(beats)
    if not bars:
        raise SystemExit("the riff has no beats")
    return bars


def beat_ticks(value: int, mark: str) -> int:
    ticks = QUARTER * 4 // value
    if mark == ".":
        ticks = ticks * 3 // 2
    elif mark == "t":
        ticks = ticks * 2 // 3
    return ticks


def build_song(bars, tuning_midi, bpm, beats_per_bar, title):
    n_strings = len(tuning_midi)
    song = gpm.Song()
    song.title = title
    song.tempo = int(round(bpm))
    song.tracks, song.measureHeaders = [], []
    track = gpm.Track(song, number=1)
    track.name = "Guitar"
    track.fretCount = 24
    # String 1 is the highest; the tuning arrives low string first.
    track.strings = [gpm.GuitarString(number=i + 1, value=p) for i, p in enumerate(reversed(tuning_midi))]
    track.channel = gpm.MidiChannel(channel=0, effectChannel=1, instrument=30, volume=104)
    song.tracks.append(track)
    bar_ticks = int(round(beats_per_bar * QUARTER))
    for index, beats in enumerate(bars, start=1):
        total = sum(beat_ticks(v, m) for v, m, _ in beats)
        if total != bar_ticks:
            raise SystemExit(f"bar {index} lasts {total / QUARTER:g} beats, not {beats_per_bar:g}; "
                             "fix the riff before writing a file")
        header = gpm.MeasureHeader(number=index)
        header.timeSignature = gpm.TimeSignature(numerator=int(beats_per_bar), denominator=gpm.Duration(value=4))
        song.measureHeaders.append(header)
        measure = gpm.Measure(track, header)
        track.measures.append(measure)
        voice = measure.voices[0]
        for value, mark, placed in beats:
            duration = gpm.Duration(value=value, isDotted=(mark == "."))
            if mark == "t":
                duration.tuplet = gpm.Tuplet(enters=3, times=2)
            beat = gpm.Beat(voice, duration=duration)
            beat.status = gpm.BeatStatus.normal if placed else gpm.BeatStatus.rest
            used = set()
            for string, fret in placed:
                if not 1 <= string <= n_strings:
                    raise SystemExit(f"bar {index}: string {string} does not exist on a {n_strings}-string tuning")
                if string in used:
                    raise SystemExit(f"bar {index}: two notes on string {string} in one beat")
                if not 0 <= fret <= track.fretCount:
                    raise SystemExit(f"bar {index}: fret {fret} is off the neck")
                used.add(string)
                note = gpm.Note(beat, value=fret, string=string)
                note.type = gpm.NoteType.normal
                beat.notes.append(note)
            voice.beats.append(beat)
    return song


def sounding(song):
    """(start_beat, end_beat, midi) for every note in the song's first track."""
    track = song.tracks[0]
    tuning = {s.number: s.value for s in track.strings}
    out, cursor = [], 0
    for measure in track.measures:
        for beat in measure.voices[0].beats:
            length = beat.duration.time
            for note in beat.notes:
                if note.type in (gpm.NoteType.normal, gpm.NoteType.tie):
                    out.append((cursor / QUARTER, (cursor + length) / QUARTER, tuning[note.string] + note.value))
            cursor += length
    return out


def write_midi(song, path):
    """Type-1 MIDI of the reloaded song; each beat's notes end where the next beat starts."""
    mid = mido.MidiFile(ticks_per_beat=QUARTER)
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.tempo), time=0))
    mid.tracks.append(meta)
    trk = mido.MidiTrack()
    trk.append(mido.Message("program_change", program=30, channel=0, time=0))
    events = []
    for start, end, pitch in sounding(song):
        events.append((round(start * QUARTER), 1, pitch))
        events.append((round(end * QUARTER), 0, pitch))
    events.sort(key=lambda e: (e[0], e[1]))  # note-offs before note-ons at the same tick
    last = 0
    for tick, on, pitch in events:
        trk.append(mido.Message("note_on" if on else "note_off", note=pitch, velocity=100 if on else 0,
                                channel=0, time=tick - last))
        last = tick
    mid.tracks.append(trk)
    mid.save(path)


def ascii_tab(song, width=80):
    """One column per beat, every string shown, rendered from the reloaded song.
    Whole bars are packed onto each system up to about `width` characters."""
    track = song.tracks[0]
    labels = [note_name(s.value).ljust(3) for s in track.strings]
    rendered = []
    for measure in track.measures:
        rows = [[] for _ in track.strings]
        for beat in measure.voices[0].beats:
            cells = ["-"] * len(track.strings)
            for note in beat.notes:
                cells[note.string - 1] = str(note.value)
            cell = max(len(c) for c in cells)
            for i, c in enumerate(cells):
                rows[i].append(c.ljust(cell, "-"))
        rendered.append(["-" + "-".join(r) + "-" for r in rows])
    systems, current = [], []
    for bar in rendered:
        if current and 4 + sum(len(b[0]) + 1 for b in current + [bar]) > width:
            systems.append(current)
            current = []
        current.append(bar)
    if current:
        systems.append(current)
    lines = []
    for group in systems:
        for i, label in enumerate(labels):
            lines.append(f"{label}|" + "|".join(bar[i] for bar in group) + "|")
        lines.append("")
    return "\n".join(lines).rstrip()


def write_tab(riff_text, tuning, bpm, out, midi=None, beats_per_bar=4.0, title="Transcription"):
    """Write, reload and report. Returns the printed report as a string."""
    tuning_midi = [int(librosa.note_to_midi(t.strip())) for t in tuning.split(",")]
    if len(tuning_midi) > MAX_GP5_STRINGS:
        raise SystemExit(f"a {len(tuning_midi)}-string tuning cannot be stored in .gp5 (seven strings is the "
                         "format's ceiling); write a native .gp with the guitar-pro skill instead")
    if not out.lower().endswith(".gp5"):
        raise SystemExit("--out must end in .gp5")
    song = build_song(parse_riff(riff_text), tuning_midi, bpm, beats_per_bar, title)
    gp.write(song, out, version=(5, 1, 0))
    saved = gp.parse(out)
    notes = sounding(saved)
    track = saved.tracks[0]
    low_first = " ".join(note_name(s.value) for s in reversed(track.strings))
    report = [f"wrote {out}",
              f"reloaded {out}: {len(saved.measureHeaders)} measures, {saved.tempo} BPM, "
              f"{len(track.strings)} strings tuned {low_first} (low to high), {len(notes)} notes"]
    if midi:
        write_midi(saved, midi)
        report.append(f"wrote {midi} (exported from the reloaded .gp5)")
    report += ["", ascii_tab(saved)]
    text = "\n".join(report)
    print(text)
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("riff", help="riff text from tab_build.py, or - for stdin")
    ap.add_argument("--tuning", required=True, help="low string first, e.g. E2,A2,D3,G3,B3,E4")
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--beats-per-bar", type=float, default=4.0)
    ap.add_argument("--out", required=True, help="the .gp5 to write")
    ap.add_argument("--midi", help="also write a MIDI export of the reloaded file")
    ap.add_argument("--title", default="Transcription")
    args = ap.parse_args(argv)
    text = sys.stdin.read() if args.riff == "-" else open(args.riff).read()
    write_tab(text, args.tuning, args.bpm, args.out, args.midi, args.beats_per_bar, args.title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
