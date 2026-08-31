#!/usr/bin/env python3
"""Regression tests for gp_tab.py.

Run with:  python test_gp_tab.py

These exist because the failure modes in this corner of PyGuitarPro are silent
-- a file writes "successfully" and opens with the rhythm destroyed. Each test
here maps to a specific way that happens.
"""

import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import guitarpro as gp
from guitarpro import models as gpm

from gp_tab import (
    INSTRUMENTS,
    TUNINGS,
    RiffSyntaxError,
    Tab,
    midi_from_name,
    name_from_midi,
    parse_riff,
)

FAILURES: list[str] = []
PASSES = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSES
    if condition:
        PASSES += 1
        print(f"  pass  {label}")
    else:
        FAILURES.append(f"{label} -- {detail}")
        print(f"  FAIL  {label}  {detail}")


def beats_of(tab: Tab, track: int = 0, measure: int = 0):
    m = tab.song.tracks[track].measures[measure]
    return m.voices[0].beats if m.voices else []


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="gp_tab_test_")

    print("\n[pitch helpers]")
    check("E2 is MIDI 40", midi_from_name("E2") == 40, str(midi_from_name("E2")))
    check("F#1 is MIDI 30", midi_from_name("F#1") == 30, str(midi_from_name("F#1")))
    check("middle C is 60", midi_from_name("C4") == 60)
    check("flats parse", midi_from_name("Bb1") == midi_from_name("A#1"))
    check("round trip name", name_from_midi(40) == "E2")
    try:
        midi_from_name("H9")
        check("bad note rejected", False, "no error raised")
    except ValueError:
        check("bad note rejected", True)

    print("\n[riff parsing]")
    parsed = parse_riff("8:6.5 16:6.7x 4:5.3+4.3 | 2:r 4.:6.0 8t:6.2")
    check("two measures", len(parsed) == 2, str(len(parsed)))
    check("first measure has 3 beats", len(parsed[0]) == 3)
    check("chord has 2 notes", len(parsed[0][2]["notes"]) == 2)
    check("dead flag parsed", "dead" in parsed[0][1]["notes"][0]["effects"])
    check("rest has no notes", parsed[1][0]["notes"] == [])
    check("dotted parsed", parsed[1][1]["dotted"] is True)
    check("triplet parsed", parsed[1][2]["tuplet"] is True)
    for bad in ["6.5", "9:6.5", "8:6", "8:x.y"]:
        try:
            parse_riff(bad)
            check(f"rejects {bad!r}", False, "no error raised")
        except RiffSyntaxError:
            check(f"rejects {bad!r}", True)

    print("\n[beat integrity -- the silent-corruption case]")
    t = Tab(tuning="standard")
    t.riff("16:6.0 16:6.1 16:6.2 16:6.3")
    check("4 beats in memory", len(beats_of(t)) == 4, str(len(beats_of(t))))
    check(
        "no beat left as status=empty",
        all(b.status != gpm.BeatStatus.empty for b in beats_of(t)),
        "an empty beat collapses the measure on read",
    )
    check(
        "notes are not rests",
        all(n.type == gpm.NoteType.normal for b in beats_of(t) for n in b.notes),
    )
    p = os.path.join(tmp, "beats.gp5")
    t.save(p)
    reloaded = Tab.load(p)
    check("4 beats survive the round trip", len(beats_of(reloaded)) == 4, str(len(beats_of(reloaded))))
    check(
        "frets survive in order",
        [n.value for b in beats_of(reloaded) for n in b.notes] == [0, 1, 2, 3],
    )
    check(
        "durations survive",
        [b.duration.value for b in beats_of(reloaded)] == [16, 16, 16, 16],
    )

    print("\n[rests]")
    t = Tab(tuning="standard")
    t.riff("4:6.0 4:r 4:6.0 4:r")
    rest_beats = [b for b in beats_of(t) if not b.notes]
    check("rests exist", len(rest_beats) == 2)
    check(
        "rests marked as rest not empty",
        all(b.status == gpm.BeatStatus.rest for b in rest_beats),
    )
    p = os.path.join(tmp, "rests.gp5")
    t.save(p)
    check("rests survive round trip", len(beats_of(Tab.load(p))) == 4)

    print("\n[tunings]")
    for name, pitches in TUNINGS.items():
        tab = Tab(tuning=name)
        strings = tab.song.tracks[0].strings
        check(
            f"{name}: {len(pitches)} strings, string 1 highest",
            len(strings) == len(pitches) and strings[0].value == max(s.value for s in strings),
            f"got {[s.value for s in strings]}",
        )
    t = Tab(tuning=["D2", "A2", "D3", "G3", "B3", "E4"])
    check("explicit tuning accepted", len(t.song.tracks[0].strings) == 6)
    try:
        Tab(tuning=["E4", "B3", "G3", "D3", "A2", "E2"])
        check("high-to-low tuning rejected", False, "no error raised")
    except ValueError:
        check("high-to-low tuning rejected", True)
    try:
        Tab(tuning="nonexistent-tuning")
        check("unknown tuning rejected", False, "no error raised")
    except ValueError:
        check("unknown tuning rejected", True)

    print("\n[format limits]")
    for name in ["standard", "7-string", "baritone-b", "bass", "bass-6", "drop-c"]:
        tab = Tab(tuning=name)
        tab.riff("8:1.0 8:2.3 4:r")
        out = os.path.join(tmp, f"{name}.gp5")
        try:
            tab.save(out)
            check(f"{name} writes .gp5", os.path.getsize(out) > 0)
        except Exception as exc:  # noqa: BLE001
            check(f"{name} writes .gp5", False, repr(exc))
    for name in ["8-string", "9-string"]:
        tab = Tab(tuning=name)
        tab.riff("8:1.0 8:8.0 4:r")
        try:
            tab.save(os.path.join(tmp, f"{name}.gp5"))
            check(f"{name} refuses .gp5 with guidance", False, "wrote a file it should not have")
        except ValueError as exc:
            check(f"{name} refuses .gp5 with guidance", "musicxml" in str(exc).lower(), str(exc)[:60])
        xml_path = os.path.join(tmp, f"{name}.musicxml")
        tab.save(xml_path)
        check(f"{name} writes musicxml", os.path.getsize(xml_path) > 0)

    print("\n[musicxml validity]")
    import xml.etree.ElementTree as ET

    tab = Tab(title="XML", tempo=133, tuning="8-string")
    tab.riff("8:8.0 8:8.3 4:7.5+8.5 | 2:r 2:6.7")
    xml_path = os.path.join(tmp, "check.musicxml")
    tab.save(xml_path)
    root = ET.parse(xml_path).getroot()
    check("parses as xml", root.tag == "score-partwise")
    lines = root.find(".//staff-details/staff-lines")
    check("8 staff lines", lines is not None and lines.text == "8", getattr(lines, "text", None))
    tunings_xml = root.findall(".//staff-tuning")
    check("8 staff tunings", len(tunings_xml) == 8, str(len(tunings_xml)))
    bottom = tunings_xml[0]
    check(
        "line 1 is the lowest string (F#1)",
        bottom.get("line") == "1"
        and bottom.find("tuning-step").text == "F"
        and bottom.find("tuning-octave").text == "1",
        ET.tostring(bottom, encoding="unicode"),
    )
    check("tempo written", root.find(".//sound").get("tempo") == "133")
    frets = [f.text for f in root.findall(".//technical/fret")]
    check("frets present", frets == ["0", "3", "5", "5", "7"], str(frets))
    check("chord element used", root.find(".//note/chord") is not None)

    print("\n[ascii rendering]")
    tab = Tab(title="Asc", tuning="7-string")
    tab.riff("8:7.0 8:7.3 8:6.5 | 4:5.7 2:r")
    art = tab.ascii()
    # Tab rows look like "B1 |0---3---|"; the title line also contains "|",
    # so match on the string-label-then-bar shape rather than position.
    import re as _re

    body = [ln for ln in art.splitlines() if _re.match(r"^[A-G][#b]?-?\d\s*\|", ln)]
    check("one line per string", len(body) == 7, str(len(body)))
    check("lowest string on the bottom line", body[-1].startswith("B1"), body[-1][:6])
    check("highest string on the top line", body[0].startswith("E4"), body[0][:6])
    check("fret 3 appears on the bottom line", "3" in body[-1])
    check("fret 7 appears somewhere", any("7" in ln for ln in body))
    check(
        "renders measure separators",
        all(ln.count("|") >= 3 for ln in body),
        str([ln.count("|") for ln in body]),
    )
    empty = Tab(tuning="standard").ascii()
    check("empty song does not crash", "no notes" in empty, empty[:40])

    print("\n[midi export]")
    tab = Tab(title="Midi", tempo=155, tuning="7-string")
    tab.riff("8:7.0 8:7.3 8:7.5 | 4:6.0+7.0 2:r")
    mid_path = os.path.join(tmp, "out.mid")
    tab.midi(mid_path)
    check("midi file written", os.path.getsize(mid_path) > 0)
    import mido

    mf = mido.MidiFile(mid_path)
    notes_on = [m for tr in mf.tracks for m in tr if m.type == "note_on" and m.velocity > 0]
    check("5 note-ons", len(notes_on) == 5, str(len(notes_on)))
    # 7-string low B is B1 = 35; fret 3 on it = 38
    pitches = sorted(m.note for m in notes_on)
    check("low B open is MIDI 35", 35 in pitches, str(pitches))
    check("fret 3 on low B is 38", 38 in pitches, str(pitches))
    tempos = [m.tempo for tr in mf.tracks for m in tr if m.type == "set_tempo"]
    check("tempo is 155", tempos and abs(mido.tempo2bpm(tempos[0]) - 155) < 1, str(tempos))

    # 8-string MIDI must work even though .gp5 cannot hold it
    tab8 = Tab(tuning="8-string")
    tab8.riff("4:8.0 4:8.5")
    mid8 = os.path.join(tmp, "eight.mid")
    tab8.midi(mid8)
    on8 = sorted(
        m.note for tr in mido.MidiFile(mid8).tracks for m in tr if m.type == "note_on" and m.velocity > 0
    )
    check("8-string low F#1 is MIDI 30", on8 == [30, 35], str(on8))

    print("\n[multi-track]")
    tab = Tab(title="Band", tuning="7-string", track_name="Guitar")
    tab.riff("4:7.0 4:7.3 4:7.5 4:r")
    bass_idx = tab.add_track(name="Bass", tuning="bass-5", instrument="bass")
    check("second track added", bass_idx == 1)
    tab.riff("4:5.0 4:5.3 4:5.5 4:r", track=bass_idx)
    check("guitar keeps 7 strings", len(tab.song.tracks[0].strings) == 7)
    check("bass has 5 strings", len(tab.song.tracks[1].strings) == 5)
    check(
        "both tracks have equal measure counts",
        len(tab.song.tracks[0].measures) == len(tab.song.tracks[1].measures),
    )
    p = os.path.join(tmp, "band.gp5")
    tab.save(p)
    back = Tab.load(p)
    check("2 tracks survive", len(back.song.tracks) == 2, str(len(back.song.tracks)))
    check("bass notes survive", len(beats_of(back, track=1)) == 4)
    check(
        "bass instrument preserved",
        back.song.tracks[1].channel.instrument == INSTRUMENTS["bass"],
        str(back.song.tracks[1].channel.instrument),
    )
    check("no phantom empty track", all(t.name in ("Guitar", "Bass") for t in back.song.tracks))

    print("\n[appending sections]")
    tab = Tab(tuning="standard")
    tab.riff("4:6.0 4:6.2 4:6.3 4:r")
    tab.riff("4:5.0 4:5.2 4:5.3 4:r")
    check("appends into new measures", len(tab.song.tracks[0].measures) == 2)
    check("first measure untouched", len(beats_of(tab, measure=0)) == 4)
    check("second measure filled", len(beats_of(tab, measure=1)) == 4)

    print("\n[effects]")
    tab = Tab(tuning="standard")
    tab.riff("8:6.5~ 8:6.5h 8:6.5m 8:6.5l 8:6.5g 8:6.12o 8:6.5b 8:6.5/ 8:6.5x")
    bs = beats_of(tab)
    check("vibrato set", bs[0].notes[0].effect.vibrato)
    check("hammer set", bs[1].notes[0].effect.hammer)
    check("palm mute set", bs[2].notes[0].effect.palmMute)
    check("let ring set", bs[3].notes[0].effect.letRing)
    check("ghost set", bs[4].notes[0].effect.ghostNote)
    check("harmonic set", bs[5].notes[0].effect.harmonic is not None)
    check("bend set", bs[6].notes[0].effect.bend is not None)
    check("slide set", bool(bs[7].notes[0].effect.slides))
    check("dead note type", bs[8].notes[0].type == gpm.NoteType.dead)
    p = os.path.join(tmp, "fx.gp5")
    tab.save(p)
    fx = beats_of(Tab.load(p))
    check("effects survive round trip", len(fx) == 9 and fx[0].notes[0].effect.vibrato)

    print("\n[validation]")
    tab = Tab(tuning="standard")
    try:
        tab.riff("4:9.0")
        check("rejects nonexistent string", False, "no error raised")
    except ValueError as exc:
        check("rejects nonexistent string", "does not exist" in str(exc))
    try:
        tab.riff("4:6.99")
        check("rejects impossible fret", False, "no error raised")
    except ValueError as exc:
        check("rejects impossible fret", "outside" in str(exc))
    try:
        Tab(tuning="standard").save(os.path.join(tmp, "x.gpx"))
        check("refuses .gpx write", False, "no error raised")
    except ValueError:
        check("refuses .gpx write", True)
    try:
        Tab.load("nope.gpx")
        check("refuses .gpx read with guidance", False, "no error raised")
    except ValueError as exc:
        check("refuses .gpx read with guidance", "Export" in str(exc) or "export" in str(exc))

    print("\n[info + to_riff]")
    tab = Tab(title="Info", artist="Jayson", tempo=142, tuning="7-string")
    source = "16:7.0 16:7.0 16:7.3 8:7.0 | 4:6.0+7.0 4:r 2:5.7"
    tab.riff(source)
    p = os.path.join(tmp, "info.gp5")
    tab.save(p)
    data = Tab.load(p).info()
    check("title", data["title"] == "Info")
    check("artist", data["artist"] == "Jayson")
    check("tempo", data["tempo"] == 142)
    check("measures", data["measures"] == 2, str(data["measures"]))
    check("tuning named", data["tracks"][0]["tuning_name"] == "7-string")
    check("tuning low first", data["tracks"][0]["tuning"][0] == "B1")
    check("note count", data["tracks"][0]["notes"] == 7, str(data["tracks"][0]["notes"]))
    check("fret range", data["tracks"][0]["fret_range"] == [0, 7], str(data["tracks"][0]["fret_range"]))
    check("time signature", data["time_signatures"] == ["4/4"], str(data["time_signatures"]))
    round_tripped = Tab.load(p).to_riff()
    check(
        "to_riff preserves beat count",
        len(round_tripped.split("|")[0].split()) == 4,
        round_tripped,
    )
    check("to_riff is re-parseable", len(parse_riff(round_tripped)) == 2, round_tripped)

    print("\n[transpose]")
    tab = Tab(tuning="standard")
    tab.riff("4:6.5 4:6.7 4:5.5")
    tab.transpose(2)
    check("frets shifted up", [n.value for b in beats_of(tab) for n in b.notes] == [7, 9, 7])
    tab.transpose(-2)
    check("shift is reversible", [n.value for b in beats_of(tab) for n in b.notes] == [5, 7, 5])
    tab2 = Tab(tuning="standard")
    tab2.riff("4:6.0 4:6.5")
    tab2.transpose(-3)
    check(
        "off-fretboard notes left alone, not wrapped",
        [n.value for b in beats_of(tab2) for n in b.notes] == [0, 2],
        str([n.value for b in beats_of(tab2) for n in b.notes]),
    )

    print("\n[measure length validation]")
    tab = Tab(tuning="7-string")
    tab.riff("8:7.0 8:7.0 16:7.0 16:7.3 8:7.5 8:7.0 4:7.0")  # 3.5 beats, not 4
    issues = tab.check_measures()
    check("short bar detected", len(issues) == 1, str(issues))
    check("reports actual length", issues and issues[0]["actual_beats"] == 3.5, str(issues))
    check("reports expected length", issues and issues[0]["expected_beats"] == 4.0, str(issues))
    check("full bar is clean", Tab(tuning="7-string").riff("4:7.0 4:7.3 4:7.5 4:r").check_measures() == [])
    odd = Tab(tuning="7-string", time_signature=(7, 8))
    odd.riff("8:7.0 8:7.0 8:7.3 8:7.0 8:7.0 8:7.3 8:7.5")
    check("7/8 bar with 7 eighths is clean", odd.check_measures() == [], str(odd.check_measures()))
    trip = Tab(tuning="standard")
    trip.riff("8t:6.0 8t:6.2 8t:6.3 8t:6.0 8t:6.2 8t:6.3 8t:6.0 8t:6.2 8t:6.3 8t:6.0 8t:6.2 8t:6.3")
    check("12 triplet eighths fill 4/4", trip.check_measures() == [], str(trip.check_measures()))

    print("\n[time signatures]")
    tab = Tab(title="Odd", tuning="7-string", time_signature=(7, 8))
    tab.riff("8:7.0 8:7.0 8:7.3 8:7.0 8:7.0 8:7.3 8:7.5")
    p = os.path.join(tmp, "odd.gp5")
    tab.save(p)
    info = Tab.load(p).info()
    check("7/8 preserved", info["time_signatures"] == ["7/8"], str(info["time_signatures"]))

    print("\n[native GP7 export -- skipped if Node/alphaTab absent]")
    tab = Tab(title="GP7", artist="Jayson", tempo=150, tuning="8-string")
    tab.riff("16:8.0m 16:8.0m 16:8.3 8:8.0 8:7.2 | 4:8.0+7.0 4:r 2:6.5~")
    gp7_path = os.path.join(tmp, "eight.gp")
    try:
        tab.gp7(gp7_path)
    except RuntimeError as exc:
        print(f"  skip  native .gp export ({str(exc).splitlines()[0][:60]})")
    else:
        check("wrote a .gp file", os.path.getsize(gp7_path) > 0)
        import zipfile

        with zipfile.ZipFile(gp7_path) as z:
            names = z.namelist()
            gpif = next((n for n in names if n.endswith(".gpif")), None)
            check("is a GP7 container with score.gpif", gpif is not None, str(names[:4]))
            import xml.etree.ElementTree as ET

            root = ET.fromstring(z.read(gpif))
        tunings = [
            [int(x) for x in p.find("Pitches").text.split()]
            for p in root.iter("Property")
            if p.get("name") == "Tuning" and p.find("Pitches") is not None
        ]
        check(
            "8 strings in F# standard survive",
            any(sorted(t) == [30, 35, 40, 45, 50, 55, 59, 64] for t in tunings),
            str(tunings),
        )
        check("4 bars", len(root.findall(".//MasterBar")) == 2, str(len(root.findall(".//MasterBar"))))

        # Everything below crashed Guitar Pro before repair_gpif existed, and
        # none of it is detectable by reloading the file -- alphaTab reads its
        # own broken output back without complaint. Validate the XML directly.
        with zipfile.ZipFile(gp7_path) as zz:
            raw = zz.read(gpif).decode("utf-8")
        check(
            "FretCount uses <Number>, not <Fret>",
            '<Property name="FretCount"><Fret>' not in raw.replace(" ", "")
            and re.search(r'<Property name="FretCount">\s*<Number>', raw) is not None,
        )
        check(
            "every staff has a Tuning property",
            all(
                any(p.get("name") == "Tuning" for p in tr.find(".//Staff").findall(".//Property"))
                for tr in root.find("Tracks")
            ),
        )
        check(
            "exactly five lyric lines per track",
            all(
                tr.find("Lyrics") is not None and len(tr.find("Lyrics").findall("Line")) == 5
                for tr in root.find("Tracks")
            ),
        )
        check("no per-beat Lyrics elements", not root.findall(".//Beats/Beat/Lyrics"))
        long_letters = [
            s.findtext("Letter") or ""
            for s in root.findall(".//Section")
            if len(s.findtext("Letter") or "") > 10
        ]
        check("section letters stay short", not long_letters, str(long_letters[:3]))

    print("\n" + "=" * 62)
    if FAILURES:
        print(f"{PASSES} passed, {len(FAILURES)} FAILED")
        for f in FAILURES:
            print("  -", f)
        return 1
    print(f"all {PASSES} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
