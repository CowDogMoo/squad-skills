#!/usr/bin/env python3
"""
gp_tab.py -- build, read, and render Guitar Pro files with PyGuitarPro.

Why this exists: PyGuitarPro's object model is low-level and has a few sharp
edges that silently produce wrong or empty files (notes defaulting to rests,
measures existing on the song but not on the track, string numbering running
high-to-low). This module wraps those edges so the common jobs -- write a riff,
read someone else's tab, render readable ASCII, get a MIDI stem -- are one call
each and fail loudly instead of quietly.

Quick start:

    from gp_tab import Tab, TUNINGS

    t = Tab(title="Test", artist="Example Artist", tempo=140, tuning=TUNINGS["8-string"])
    t.riff("8:8.0 8:8.0 8:8.3 8:8.0 | 4:7.5+8.5 4:r 2:8.0")
    t.save("riff.gp5")
    print(t.ascii())
    t.midi("riff.mid")

Everything is also usable from the command line -- see `python gp_tab.py --help`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Iterable, Sequence

try:
    import guitarpro as gp
    from guitarpro import models as gpm
except ImportError:  # pragma: no cover
    sys.exit(
        "PyGuitarPro is required. From the skill directory:\n"
        "    uv venv .venv\n"
        "    uv pip install --python .venv/bin/python -r scripts/requirements.txt\n"
        "then run this script with .venv/bin/python."
    )


# --------------------------------------------------------------------------
# Pitch helpers
# --------------------------------------------------------------------------

_PITCH_CLASSES = {
    "C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "FB": 4,
    "F": 5, "E#": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9,
    "A#": 10, "BB": 10, "B": 11, "CB": 11,
}

_SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")


def midi_from_name(name: str) -> int:
    """'F#1' -> 30, 'E2' -> 40, 'E4' -> 64.

    Scientific pitch notation, where middle C is C4 = 60. This matches how
    Guitar Pro and most tuner apps label strings, so a tuning copied off a
    forum post drops straight in.
    """
    m = _NOTE_RE.match(name.strip())
    if not m:
        raise ValueError(
            f"Bad note name {name!r}. Use scientific pitch notation like "
            f"'E2', 'F#1', 'Bb1' (middle C is C4)."
        )
    letter, accidental, octave = m.groups()
    key = (letter + accidental).upper()
    if key not in _PITCH_CLASSES:
        raise ValueError(f"Unknown pitch class {key!r} in {name!r}")
    return _PITCH_CLASSES[key] + (int(octave) + 1) * 12


def name_from_midi(value: int) -> str:
    """60 -> 'C4'. Inverse of midi_from_name (always spells with sharps)."""
    return f"{_SHARP_NAMES[value % 12]}{value // 12 - 1}"


# Tunings are written LOW string first, the way players say them out loud
# ("drop C is C G C F A D"). The Tab class reverses them internally, because
# Guitar Pro numbers string 1 as the *highest* string.
TUNINGS: dict[str, list[str]] = {
    "standard": ["E2", "A2", "D3", "G3", "B3", "E4"],
    "drop-d": ["D2", "A2", "D3", "G3", "B3", "E4"],
    "drop-c": ["C2", "G2", "C3", "F3", "A3", "D4"],
    "drop-b": ["B1", "F#2", "B2", "E3", "G#3", "C#4"],
    "d-standard": ["D2", "G2", "C3", "F3", "A3", "D4"],
    "c-standard": ["C2", "F2", "A#2", "D#3", "G3", "C4"],
    "open-d": ["D2", "A2", "D3", "F#3", "A3", "D4"],
    "open-g": ["D2", "G2", "D3", "G3", "B3", "D4"],
    "dadgad": ["D2", "A2", "D3", "G3", "A3", "D4"],
    # Extended range
    "7-string": ["B1", "E2", "A2", "D3", "G3", "B3", "E4"],
    "7-string-drop-a": ["A1", "E2", "A2", "D3", "G3", "B3", "E4"],
    "8-string": ["F#1", "B1", "E2", "A2", "D3", "G3", "B3", "E4"],
    "8-string-drop-e": ["E1", "B1", "E2", "A2", "D3", "G3", "B3", "E4"],
    "9-string": ["C#1", "F#1", "B1", "E2", "A2", "D3", "G3", "B3", "E4"],
    # Baritone
    "baritone-b": ["B1", "E2", "A2", "D3", "F#3", "B3"],
    "baritone-a": ["A1", "D2", "G2", "C3", "E3", "A3"],
    "baritone-c": ["C2", "F2", "A#2", "D#3", "G3", "C4"],
    # Bass
    "bass": ["E1", "A1", "D2", "G2"],
    "bass-5": ["B0", "E1", "A1", "D2", "G2"],
    "bass-6": ["B0", "E1", "A1", "D2", "G2", "C3"],
    "bass-drop-d": ["D1", "A1", "D2", "G2"],
}

# General MIDI programs worth having at hand. Guitar Pro stores these per track.
INSTRUMENTS: dict[str, int] = {
    "clean-guitar": 27,
    "jazz-guitar": 26,
    "acoustic-guitar": 25,
    "nylon-guitar": 24,
    "overdriven-guitar": 29,
    "distortion-guitar": 30,
    "muted-guitar": 28,
    "harmonics-guitar": 31,
    "bass": 33,
    "picked-bass": 34,
    "fretless-bass": 35,
    "synth-bass": 38,
    "piano": 0,
    "strings": 48,
}

PERCUSSION_CHANNEL = 9


# --------------------------------------------------------------------------
# Riff notation
# --------------------------------------------------------------------------
#
# One beat looks like   DURATION ':' NOTES
#
#   8:6.5          eighth note, string 6 fret 5
#   4:5.7+4.7      quarter chord, two strings at once
#   16:8.0x        sixteenth, dead/muted note
#   4.:7.3         dotted quarter (the '.' rides on the duration)
#   8t:6.5         triplet eighth
#   4:r            quarter rest
#
# Note suffixes stack:  x dead   ~ vibrato   h hammer-on   p pull-off
#                       / slide  b bend      g ghost       o harmonic
#                       m palm-mute          l let-ring
#
# Measures are separated by '|'. Whitespace elsewhere is free.

_DURATION_RE = re.compile(r"^(\d+)(\.?)(t?)$")
_NOTE_TOKEN_RE = re.compile(r"^(\d+)\.(\d+)([xX~hpb/gomls]*)$")

_EFFECT_FLAGS = {
    "x": "dead",
    "X": "dead",
    "~": "vibrato",
    "h": "hammer",
    "p": "hammer",  # pull-off is the same flag in the format; direction is implied by pitch
    "b": "bend",
    "/": "slide",
    "s": "slide",
    "g": "ghost",
    "o": "harmonic",
    "m": "palmMute",
    "l": "letRing",
}


class RiffSyntaxError(ValueError):
    """Raised with the offending token so the caller can fix it precisely."""


def parse_riff(source: str) -> list[list[dict[str, Any]]]:
    """Parse riff notation into a list of measures, each a list of beat dicts.

    Returned beats look like:
        {"duration": 8, "dotted": False, "tuplet": False,
         "notes": [{"string": 6, "fret": 5, "effects": {"vibrato"}}]}
    A rest is the same shape with an empty notes list.
    """
    measures: list[list[dict[str, Any]]] = []
    for chunk in source.split("|"):
        beats: list[dict[str, Any]] = []
        for token in chunk.split():
            beats.append(_parse_beat(token))
        # A trailing '|' or doubled '||' yields an empty chunk; skip those
        # rather than emitting a phantom measure.
        if beats:
            measures.append(beats)
    if not measures:
        raise RiffSyntaxError(f"No beats found in riff: {source!r}")
    return measures


def _parse_beat(token: str) -> dict[str, Any]:
    if ":" not in token:
        raise RiffSyntaxError(
            f"Beat {token!r} is missing its ':'. Expected DURATION:NOTES, "
            f"for example '8:6.5' or '4:r'."
        )
    dur_part, note_part = token.split(":", 1)
    dm = _DURATION_RE.match(dur_part)
    if not dm:
        raise RiffSyntaxError(
            f"Bad duration {dur_part!r} in beat {token!r}. Use 1, 2, 4, 8, 16, "
            f"32 or 64, optionally with '.' for dotted or 't' for triplet."
        )
    value, dot, trip = dm.groups()
    value = int(value)
    if value not in (1, 2, 4, 8, 16, 32, 64):
        raise RiffSyntaxError(
            f"Duration {value} in {token!r} is not a real note length. "
            f"Use 1, 2, 4, 8, 16, 32 or 64."
        )

    beat: dict[str, Any] = {
        "duration": value,
        "dotted": bool(dot),
        "tuplet": bool(trip),
        "notes": [],
    }
    if note_part.lower() == "r":
        return beat

    for note_token in note_part.split("+"):
        nm = _NOTE_TOKEN_RE.match(note_token)
        if not nm:
            raise RiffSyntaxError(
                f"Bad note {note_token!r} in beat {token!r}. Expected "
                f"STRING.FRET like '6.5', optionally with effect suffixes."
            )
        string, fret, flags = nm.groups()
        effects = {_EFFECT_FLAGS[f] for f in flags if f in _EFFECT_FLAGS}
        beat["notes"].append(
            {"string": int(string), "fret": int(fret), "effects": effects}
        )
    return beat


# --------------------------------------------------------------------------
# Tab builder
# --------------------------------------------------------------------------


class Tab:
    """A Guitar Pro song under construction (or one you loaded to inspect)."""

    def __init__(
        self,
        title: str = "Untitled",
        artist: str = "",
        album: str = "",
        tempo: int = 120,
        tuning: Sequence[str] | str = "standard",
        track_name: str = "Guitar",
        instrument: str | int = "distortion-guitar",
        fret_count: int = 24,
        time_signature: tuple[int, int] = (4, 4),
        _song: gpm.Song | None = None,
    ):
        if _song is not None:
            self.song = _song
            # A loaded song carries its meter in its measure headers, not in
            # the constructor argument. Without picking it up here, riff() on
            # a loaded tab dies with AttributeError as soon as it has to grow
            # the song -- which is the whole point of loading one.
            first = _song.measureHeaders[0] if _song.measureHeaders else None
            self._time_signature = (
                time_signature
                if first is None
                else (
                    first.timeSignature.numerator,
                    first.timeSignature.denominator.value,
                )
            )
            return

        self.song = gpm.Song()
        self.song.title = title
        self.song.artist = artist
        self.song.album = album
        self.song.tempo = int(tempo)

        # A fresh Song ships with one track and one measure header already
        # attached. Reuse them rather than appending, or you get a phantom
        # empty "Track 1" in the file -- a common way these scripts go wrong.
        self.song.tracks = []
        self.song.measureHeaders = []
        self._time_signature = time_signature
        self._add_header(time_signature)
        self.add_track(
            name=track_name,
            tuning=tuning,
            instrument=instrument,
            fret_count=fret_count,
        )

    # -- structure ---------------------------------------------------------

    def _add_header(self, time_signature: tuple[int, int] | None = None) -> gpm.MeasureHeader:
        header = gpm.MeasureHeader(number=len(self.song.measureHeaders) + 1)
        ts = time_signature or self._time_signature
        header.timeSignature = gpm.TimeSignature(
            numerator=ts[0], denominator=gpm.Duration(value=ts[1])
        )
        self.song.measureHeaders.append(header)
        # Every track needs a measure for every header, otherwise Guitar Pro
        # reads a truncated song (or refuses the file outright).
        for track in self.song.tracks:
            track.measures.append(gpm.Measure(track, header))
        return header

    def add_track(
        self,
        name: str = "Guitar",
        tuning: Sequence[str] | str = "standard",
        instrument: str | int = "distortion-guitar",
        fret_count: int = 24,
        volume: int = 104,
        is_percussion: bool = False,
    ) -> int:
        """Add a track and return its index.

        `tuning` is a TUNINGS key or an explicit list written LOW string first,
        e.g. ["F#1","B1","E2","A2","D3","G3","B3","E4"] for an 8-string.
        """
        pitches = self._resolve_tuning(tuning)
        track = gpm.Track(self.song, number=len(self.song.tracks) + 1)
        track.name = name
        track.fretCount = fret_count
        track.isPercussionTrack = is_percussion

        # String 1 is the highest-pitched string, so reverse the low-first
        # tuning the caller gave us.
        track.strings = [
            gpm.GuitarString(number=i + 1, value=pitch)
            for i, pitch in enumerate(reversed(pitches))
        ]

        program = (
            instrument
            if isinstance(instrument, int)
            else INSTRUMENTS.get(str(instrument).lower())
        )
        if program is None:
            raise ValueError(
                f"Unknown instrument {instrument!r}. Choose from "
                f"{sorted(INSTRUMENTS)} or pass a General MIDI program number."
            )
        channel_index = len(self.song.tracks) * 2
        track.channel = gpm.MidiChannel(
            channel=PERCUSSION_CHANNEL if is_percussion else channel_index % 16,
            effectChannel=PERCUSSION_CHANNEL if is_percussion else (channel_index + 1) % 16,
            instrument=program,
            volume=volume,
        )

        track.measures = [gpm.Measure(track, h) for h in self.song.measureHeaders]
        self.song.tracks.append(track)
        return len(self.song.tracks) - 1

    @staticmethod
    def _resolve_tuning(tuning: Sequence[str] | str) -> list[int]:
        if isinstance(tuning, str):
            key = tuning.lower()
            if key not in TUNINGS:
                raise ValueError(
                    f"Unknown tuning {tuning!r}. Known names: {sorted(TUNINGS)}. "
                    f"Or pass an explicit list like ['B1','E2','A2','D3','G3','B3','E4']."
                )
            names = TUNINGS[key]
        else:
            names = list(tuning)
        if len(names) < 4:
            raise ValueError(f"A tuning needs at least 4 strings, got {names!r}")
        pitches = [
            n if isinstance(n, int) else midi_from_name(n) for n in names
        ]
        if pitches != sorted(pitches):
            # Not fatal -- drop tunings are still ascending overall -- but a
            # fully reversed list is almost always a caller mistake.
            if pitches == sorted(pitches, reverse=True):
                raise ValueError(
                    f"Tuning {names!r} looks high-to-low. Write tunings low "
                    f"string first, e.g. ['E2','A2','D3','G3','B3','E4']."
                )
        return pitches

    # -- content -----------------------------------------------------------

    def riff(self, source: str, track: int = 0, start_measure: int | None = None) -> "Tab":
        """Write riff notation into a track, growing the song as needed.

        By default this appends after whatever is already in the track, so you
        can build a song section by section with repeated calls.
        """
        measures = parse_riff(source)
        trk = self._track(track)

        if start_measure is None:
            start_measure = self._first_empty_measure(trk)

        needed = start_measure + len(measures)
        while len(self.song.measureHeaders) < needed:
            self._add_header()

        for offset, beats in enumerate(measures):
            measure = trk.measures[start_measure + offset]
            voice = self._voice(measure)
            for beat_spec in beats:
                self._append_beat(voice, beat_spec, trk)
        return self

    def _append_beat(self, voice: gpm.Voice, spec: dict[str, Any], track: gpm.Track) -> None:
        duration = gpm.Duration(value=spec["duration"], isDotted=spec["dotted"])
        if spec["tuplet"]:
            duration.tuplet = gpm.Tuplet(enters=3, times=2)
        beat = gpm.Beat(voice, duration=duration)
        # Beat.status defaults to `empty`, and an empty beat is written with a
        # zero length. Guitar Pro then stacks every following beat at the same
        # tick, so a whole measure collapses onto beat one -- notes present but
        # rhythm destroyed. Setting status explicitly is what keeps the riff a
        # riff. Rests need `rest`, not `normal`, or they render as silence with
        # no visible rest symbol.
        beat.status = gpm.BeatStatus.rest if not spec["notes"] else gpm.BeatStatus.normal

        string_count = len(track.strings)
        used_strings: set[int] = set()
        for note_spec in spec["notes"]:
            string = note_spec["string"]
            if not 1 <= string <= string_count:
                raise ValueError(
                    f"String {string} does not exist on track {track.name!r}, "
                    f"which has {string_count} strings (1 = highest, "
                    f"{string_count} = lowest)."
                )
            # A beat stores its strings as bit flags, one bit per string, so a
            # second note on the same string overwrites the first and the rest
            # of the beat decodes as garbage. gp.write accepts it; gp.parse
            # then fails on the file with an unrelated-looking error, so catch
            # it here where the offending token is still in hand.
            if string in used_strings:
                raise ValueError(
                    f"Two notes fall on string {string} in the same beat. A "
                    f"string can only sound one note at a time, and the .gp5 "
                    f"format has no way to store the second one -- the file "
                    f"would write and then fail to reopen. Move one note to "
                    f"another string."
                )
            used_strings.add(string)
            fret = note_spec["fret"]
            if not 0 <= fret <= track.fretCount:
                raise ValueError(
                    f"Fret {fret} is outside 0-{track.fretCount} on track "
                    f"{track.name!r}."
                )
            note = gpm.Note(beat, value=fret, string=string)
            effects = note_spec.get("effects") or set()
            # NoteType defaults to `rest`, which writes a note that silently
            # does not sound. Setting it explicitly is the single most
            # important line in this file.
            note.type = gpm.NoteType.dead if "dead" in effects else gpm.NoteType.normal
            self._apply_effects(note, effects)
            beat.notes.append(note)

        voice.beats.append(beat)

    @staticmethod
    def _apply_effects(note: gpm.Note, effects: Iterable[str]) -> None:
        eff = note.effect
        for name in effects:
            if name == "vibrato":
                eff.vibrato = True
            elif name == "hammer":
                eff.hammer = True
            elif name == "ghost":
                eff.ghostNote = True
            elif name == "palmMute":
                eff.palmMute = True
            elif name == "letRing":
                eff.letRing = True
            elif name == "harmonic":
                eff.harmonic = gpm.NaturalHarmonic()
            elif name == "slide":
                eff.slides = [gpm.SlideType.shiftSlideTo]
            elif name == "bend":
                eff.bend = gpm.BendEffect(
                    type=gpm.BendType.bend,
                    value=50,
                    points=[
                        gpm.BendPoint(position=0, value=0),
                        gpm.BendPoint(position=6, value=4),
                        gpm.BendPoint(position=12, value=4),
                    ],
                )

    @staticmethod
    def _voice(measure: gpm.Measure) -> gpm.Voice:
        if not measure.voices:
            measure.voices = [gpm.Voice(measure) for _ in range(gpm.Measure.maxVoices)]
        return measure.voices[0]

    @staticmethod
    def _first_empty_measure(track: gpm.Track) -> int:
        for i, measure in enumerate(track.measures):
            if all(not v.beats for v in measure.voices) or not measure.voices:
                return i
        return len(track.measures)

    def _track(self, index: int) -> gpm.Track:
        try:
            return self.song.tracks[index]
        except IndexError:
            raise IndexError(
                f"Track {index} does not exist; the song has "
                f"{len(self.song.tracks)} track(s)."
            ) from None

    def set_tempo(self, bpm: int) -> "Tab":
        self.song.tempo = int(bpm)
        return self

    # -- output ------------------------------------------------------------

    # The .gp3/.gp4/.gp5 binary format packs which strings a beat uses into a
    # single byte (bit `7 - string_number`), so seven strings is a hard ceiling
    # of the file format itself -- not a PyGuitarPro limitation, and not
    # something a workaround can lift. Eight-string and nine-string parts have
    # to travel as MusicXML, which Guitar Pro 7+ imports with tablature intact.
    MAX_GP_STRINGS = 7

    def save(self, path: str) -> str:
        """Write .gp5 (recommended), .gp4, .gp3, or .musicxml based on extension.

        Raises with a concrete alternative if the song has more strings than
        the binary format can hold, rather than writing a corrupt file.
        """
        ext = os.path.splitext(path)[1].lower()
        self._warn_about_measure_lengths()
        if ext in (".musicxml", ".xml"):
            return self.musicxml(path)
        if ext == ".gp":
            return self.gp7(path)

        versions = {".gp3": (3, 0, 0), ".gp4": (4, 0, 6), ".gp5": (5, 1, 0)}
        if ext not in versions:
            raise ValueError(
                f"Cannot write {ext!r}. Use .gp5 (best), .gp4, .gp3, or "
                f".musicxml. Guitar Pro 7+ .gpx/.gp files are read-only in "
                f"PyGuitarPro."
            )

        oversized = [t for t in self.song.tracks if len(t.strings) > self.MAX_GP_STRINGS]
        if oversized:
            names = ", ".join(f"{t.name!r} ({len(t.strings)} strings)" for t in oversized)
            raise ValueError(
                f"The .gp5 file format tops out at {self.MAX_GP_STRINGS} strings "
                f"per track, so {names} cannot be written to {ext}. Save as "
                f"'.musicxml' instead -- Guitar Pro 7 and 8 import it with the "
                f"tablature and tuning intact. ASCII and MIDI output work at any "
                f"string count."
            )

        self._pad_short_measures()
        gp.write(self.song, path, version=versions[ext])
        return path

    def gp7(self, path: str, node_modules: str | None = None) -> str:
        """Export a native Guitar Pro 7/8 `.gp` file via the bundled alphaTab script.

        This is the nicest outcome for 8-string parts -- a real Guitar Pro file
        with no import step -- but it needs Node and `@coderline/alphatab`
        installed, so treat it as an upgrade over `musicxml()`, not a
        replacement. Raises RuntimeError with install instructions if the
        toolchain isn't there, so callers can fall back cleanly.
        """
        import json as _json
        import shutil
        import subprocess
        import tempfile

        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gp7_export.mjs")
        if not os.path.exists(script):
            raise RuntimeError(f"gp7_export.mjs is missing from {os.path.dirname(script)}")
        if shutil.which("node") is None:
            raise RuntimeError(
                "Node is required for .gp export. Either install Node, or use "
                "save('out.musicxml') instead -- Guitar Pro 7+ imports MusicXML "
                "with the tablature intact."
            )

        spec: dict[str, Any] = {
            "title": self.song.title,
            "artist": self.song.artist,
            "album": self.song.album,
            "tempo": self.song.tempo,
            "tracks": [],
        }
        for index, trk in enumerate(self.song.tracks):
            bars = []
            for measure in trk.measures:
                voice = measure.voices[0] if measure.voices else None
                beats = []
                for beat in (voice.beats if voice else []):
                    notes = []
                    for note in beat.notes:
                        if note.type == gpm.NoteType.rest:
                            continue
                        eff = note.effect
                        notes.append(
                            {
                                "string": note.string,
                                "fret": note.value,
                                "palmMute": bool(eff.palmMute),
                                "letRing": bool(eff.letRing),
                                "vibrato": bool(eff.vibrato),
                                "hammer": bool(eff.hammer),
                                "ghost": bool(eff.ghostNote),
                                "dead": note.type == gpm.NoteType.dead,
                                "harmonic": eff.harmonic is not None,
                                "slide": bool(eff.slides),
                            }
                        )
                    beats.append(
                        {
                            "duration": beat.duration.value,
                            "dots": 1 if beat.duration.isDotted else 0,
                            "tuplet": bool(
                                beat.duration.tuplet and beat.duration.tuplet.enters != 1
                            ),
                            "notes": notes,
                        }
                    )
                bars.append(
                    {
                        "ts": [
                            measure.timeSignature.numerator,
                            measure.timeSignature.denominator.value,
                        ],
                        "beats": beats,
                    }
                )
            spec["tracks"].append(
                {
                    "name": trk.name,
                    "program": trk.channel.instrument,
                    "channel": index * 2,
                    # Low string first, matching the rest of this module.
                    "tuning": [s.value for s in reversed(trk.strings)],
                    "bars": bars,
                }
            )

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            _json.dump(spec, fh)
            spec_path = fh.name
        try:
            env = dict(os.environ)
            if node_modules:
                env["NODE_PATH"] = node_modules
            result = subprocess.run(
                ["node", script, spec_path, path],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(script),
                env=env,
            )
        finally:
            os.unlink(spec_path)

        if result.returncode != 0:
            raise RuntimeError(
                f"alphaTab export failed (exit {result.returncode}).\n"
                f"{result.stderr.strip()}\n"
                f"Falling back to save('...musicxml') is usually the right move."
            )
        repair_gpif(path, lyrics=spec["tracks"][0].get("lyrics"))
        return path

    def musicxml(self, path: str) -> str:
        """Export to MusicXML with tablature, for 8-string and beyond.

        Guitar Pro 7+, MuseScore, and Dorico all import this. The tuning is
        written into staff-details, so an F# standard 8-string opens showing
        eight lines tuned correctly rather than a mangled six.
        """
        import xml.etree.ElementTree as ET

        divisions = gpm.Duration.quarterTime  # 960 per quarter note
        type_names = {
            1: "whole", 2: "half", 4: "quarter", 8: "eighth",
            16: "16th", 32: "32nd", 64: "64th",
        }

        root = ET.Element("score-partwise", version="4.0")
        work = ET.SubElement(root, "work")
        ET.SubElement(work, "work-title").text = self.song.title or "Untitled"
        ident = ET.SubElement(root, "identification")
        if self.song.artist:
            creator = ET.SubElement(ident, "creator", type="composer")
            creator.text = self.song.artist
        encoding = ET.SubElement(ident, "encoding")
        ET.SubElement(encoding, "software").text = "gp_tab.py"

        part_list = ET.SubElement(root, "part-list")
        for i, trk in enumerate(self.song.tracks):
            pid = f"P{i + 1}"
            sp = ET.SubElement(part_list, "score-part", id=pid)
            ET.SubElement(sp, "part-name").text = trk.name or f"Track {i + 1}"
            inst = ET.SubElement(sp, "score-instrument", id=f"{pid}-I1")
            ET.SubElement(inst, "instrument-name").text = trk.name or f"Track {i + 1}"
            midi = ET.SubElement(sp, "midi-instrument", id=f"{pid}-I1")
            ET.SubElement(midi, "midi-channel").text = str(trk.channel.channel + 1)
            ET.SubElement(midi, "midi-program").text = str(trk.channel.instrument + 1)

        for i, trk in enumerate(self.song.tracks):
            part = ET.SubElement(root, "part", id=f"P{i + 1}")
            string_count = len(trk.strings)
            tuning = {s.number: s.value for s in trk.strings}

            for m_index, measure in enumerate(trk.measures):
                me = ET.SubElement(part, "measure", number=str(m_index + 1))

                if m_index == 0:
                    attrs = ET.SubElement(me, "attributes")
                    ET.SubElement(attrs, "divisions").text = str(divisions)
                    key = ET.SubElement(attrs, "key")
                    ET.SubElement(key, "fifths").text = "0"
                    ts = measure.timeSignature
                    time_el = ET.SubElement(attrs, "time")
                    ET.SubElement(time_el, "beats").text = str(ts.numerator)
                    ET.SubElement(time_el, "beat-type").text = str(ts.denominator.value)
                    clef = ET.SubElement(attrs, "clef")
                    ET.SubElement(clef, "sign").text = "TAB"
                    ET.SubElement(clef, "line").text = "5"
                    details = ET.SubElement(attrs, "staff-details")
                    ET.SubElement(details, "staff-lines").text = str(string_count)
                    # MusicXML numbers staff lines bottom-up, so line 1 is the
                    # lowest-pitched string -- the reverse of Guitar Pro's
                    # string numbering, which is why this loop counts down.
                    for line, number in enumerate(range(string_count, 0, -1), start=1):
                        st = ET.SubElement(details, "staff-tuning", line=str(line))
                        step, alter, octave = self._spell(tuning[number])
                        ET.SubElement(st, "tuning-step").text = step
                        if alter:
                            ET.SubElement(st, "tuning-alter").text = str(alter)
                        ET.SubElement(st, "tuning-octave").text = str(octave)

                    direction = ET.SubElement(me, "direction", placement="above")
                    dtype = ET.SubElement(direction, "direction-type")
                    metronome = ET.SubElement(dtype, "metronome")
                    ET.SubElement(metronome, "beat-unit").text = "quarter"
                    ET.SubElement(metronome, "per-minute").text = str(self.song.tempo)
                    ET.SubElement(direction, "sound", tempo=str(self.song.tempo))

                voice = measure.voices[0] if measure.voices else None
                beats = voice.beats if voice else []
                if not beats:
                    note_el = ET.SubElement(me, "note")
                    ET.SubElement(note_el, "rest")
                    ET.SubElement(note_el, "duration").text = str(divisions * 4)
                    ET.SubElement(note_el, "voice").text = "1"
                    continue

                for beat in beats:
                    live = [n for n in beat.notes if n.type != gpm.NoteType.rest]
                    dur_ticks = beat.duration.time
                    type_name = type_names.get(beat.duration.value, "quarter")

                    if not live:
                        note_el = ET.SubElement(me, "note")
                        ET.SubElement(note_el, "rest")
                        ET.SubElement(note_el, "duration").text = str(dur_ticks)
                        ET.SubElement(note_el, "voice").text = "1"
                        ET.SubElement(note_el, "type").text = type_name
                        continue

                    for n_index, note in enumerate(live):
                        note_el = ET.SubElement(me, "note")
                        if n_index:
                            ET.SubElement(note_el, "chord")
                        base = tuning.get(note.string)
                        pitch_value = (base or 40) + note.value
                        step, alter, octave = self._spell(pitch_value)
                        pitch_el = ET.SubElement(note_el, "pitch")
                        ET.SubElement(pitch_el, "step").text = step
                        if alter:
                            ET.SubElement(pitch_el, "alter").text = str(alter)
                        ET.SubElement(pitch_el, "octave").text = str(octave)
                        ET.SubElement(note_el, "duration").text = str(dur_ticks)
                        ET.SubElement(note_el, "voice").text = "1"
                        ET.SubElement(note_el, "type").text = type_name
                        if beat.duration.isDotted:
                            ET.SubElement(note_el, "dot")
                        if beat.duration.tuplet and beat.duration.tuplet.enters != 1:
                            tm = ET.SubElement(note_el, "time-modification")
                            ET.SubElement(tm, "actual-notes").text = str(beat.duration.tuplet.enters)
                            ET.SubElement(tm, "normal-notes").text = str(beat.duration.tuplet.times)
                        notations = ET.SubElement(note_el, "notations")
                        technical = ET.SubElement(notations, "technical")
                        ET.SubElement(technical, "string").text = str(note.string)
                        ET.SubElement(technical, "fret").text = str(note.value)
                        if note.effect.hammer:
                            ET.SubElement(technical, "hammer-on", type="start").text = "H"
                        if note.effect.vibrato:
                            orn = ET.SubElement(notations, "ornaments")
                            ET.SubElement(orn, "wavy-line", type="start")

        ET.indent(root, space="  ")
        xml_body = ET.tostring(root, encoding="unicode")
        doctype = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 '
            'Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">\n'
        )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(doctype + xml_body + "\n")
        return path

    @staticmethod
    def _spell(midi_value: int) -> tuple[str, int, int]:
        """MIDI number -> (step letter, alter, octave) for MusicXML."""
        name = _SHARP_NAMES[midi_value % 12]
        octave = midi_value // 12 - 1
        if len(name) == 2:
            return name[0], 1, octave
        return name, 0, octave

    def check_measures(self) -> list[dict[str, Any]]:
        """Find measures whose beats don't add up to their time signature.

        This is the single easiest way to write a tab that looks right and
        plays wrong: miscount an eighth somewhere and every following bar is
        shoved off the grid, which reads as "the riff is subtly out of time"
        rather than as an obvious error. Guitar Pro will happily open such a
        file, so nothing catches it except an explicit check.

        Returns one dict per offending measure; an empty list means everything
        lines up.
        """
        issues: list[dict[str, Any]] = []
        for track_index, trk in enumerate(self.song.tracks):
            for measure_index, measure in enumerate(trk.measures):
                voice = measure.voices[0] if measure.voices else None
                beats = voice.beats if voice else []
                if not beats:
                    continue
                actual = sum(b.duration.time for b in beats)
                ts = measure.timeSignature
                expected = int(
                    gpm.Duration.quarterTime * 4 * ts.numerator / ts.denominator.value
                )
                if actual != expected:
                    issues.append(
                        {
                            "track": track_index,
                            "track_name": trk.name,
                            "measure": measure_index + 1,
                            "time_signature": f"{ts.numerator}/{ts.denominator.value}",
                            "expected_beats": round(expected / gpm.Duration.quarterTime, 3),
                            "actual_beats": round(actual / gpm.Duration.quarterTime, 3),
                        }
                    )
        return issues

    def _warn_about_measure_lengths(self) -> None:
        for issue in self.check_measures():
            short_or_long = "short" if issue["actual_beats"] < issue["expected_beats"] else "long"
            print(
                f"warning: track {issue['track']} ({issue['track_name']!r}) measure "
                f"{issue['measure']} is {short_or_long} -- {issue['actual_beats']} "
                f"quarter notes of material in a {issue['time_signature']} bar that "
                f"holds {issue['expected_beats']}. Guitar Pro will open it, but the "
                f"timing will drift from what you intended.",
                file=sys.stderr,
            )

    def _pad_short_measures(self) -> None:
        """Fill measures that have no beats with a rest.

        Guitar Pro tolerates a truly empty measure, but a measure that exists
        on one track and not another renders as a glitchy blank, so give every
        measure at least something.
        """
        for track in self.song.tracks:
            for measure in track.measures:
                voice = self._voice(measure)
                if not voice.beats:
                    beat = gpm.Beat(voice, duration=gpm.Duration(value=1))
                    beat.status = gpm.BeatStatus.rest
                    voice.beats.append(beat)

    def ascii(self, track: int = 0, width: int = 76) -> str:
        """Render a track as readable ASCII tab.

        The layout is proportional to note duration, so a run of sixteenths
        looks tighter than a row of whole notes -- which is what makes the
        output usable for checking rhythm at a glance, not just pitches.
        """
        trk = self._track(track)
        strings = trk.strings  # string 1 first == highest pitch == top line
        labels = [name_from_midi(s.value).ljust(3) for s in strings]

        columns: list[list[str]] = []  # each column is one char slot per string
        bar_positions: list[int] = []

        for measure in trk.measures:
            voice = measure.voices[0] if measure.voices else None
            beats = voice.beats if voice else []
            if not beats:
                continue
            bar_positions.append(len(columns))
            for beat in beats:
                slot = ["-"] * len(strings)
                for note in beat.notes:
                    idx = note.string - 1
                    if 0 <= idx < len(strings):
                        slot[idx] = "x" if note.type == gpm.NoteType.dead else str(note.value)
                cell_width = max(len(s) for s in slot)
                for i in range(len(strings)):
                    slot[i] = slot[i].ljust(cell_width, "-")
                for i in range(cell_width):
                    columns.append([slot[s][i] for s in range(len(strings))])
                # Space proportional to duration, so a run of sixteenths looks
                # tighter than a row of half notes and you can read the rhythm
                # off the page instead of counting note heads.
                pad = min(10, max(1, beat.duration.time // 240))
                for _ in range(pad):
                    columns.append(["-"] * len(strings))
        bar_positions.append(len(columns))

        if not columns:
            return f"{trk.name}: (no notes)"

        header = f"{trk.name}  |  {self.song.title}"
        if self.song.artist:
            header += f" -- {self.song.artist}"
        header += f"  |  {self.song.tempo} BPM  |  "
        header += "-".join(name_from_midi(s.value) for s in reversed(strings))

        avail = max(20, width - 5)
        out = [header, ""]
        chunk_start = 0
        while chunk_start < len(columns):
            chunk_end = min(chunk_start + avail, len(columns))
            # Prefer to break on a barline so measures stay intact.
            candidates = [b for b in bar_positions if chunk_start < b <= chunk_end]
            if candidates and chunk_end < len(columns):
                chunk_end = max(candidates)
            lines = []
            for s in range(len(strings)):
                row = [labels[s], "|"]
                for c in range(chunk_start, chunk_end):
                    if c in bar_positions and c != chunk_start:
                        row.append("|")
                    row.append(columns[c][s])
                row.append("|")
                lines.append("".join(row))
            out.extend(lines)
            out.append("")
            chunk_start = chunk_end
        return "\n".join(out).rstrip()

    def midi(self, path: str) -> str:
        """Export to a standard MIDI file (one MIDI track per Guitar Pro track).

        Useful for dropping a riff into a DAW. Pitch is string tuning + fret,
        so alternate and extended-range tunings come out correct.
        """
        try:
            import mido
        except ImportError:  # pragma: no cover
            raise ImportError(
                "MIDI export needs mido. From the skill directory:\n"
                "    uv pip install --python .venv/bin/python -r scripts/requirements.txt"
            ) from None

        ticks_per_beat = gpm.Duration.quarterTime
        mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)

        meta = mido.MidiTrack()
        meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(self.song.tempo), time=0))
        meta.append(mido.MetaMessage("track_name", name=self.song.title or "Song", time=0))
        mid.tracks.append(meta)

        for trk in self.song.tracks:
            mtrack = mido.MidiTrack()
            mtrack.append(mido.MetaMessage("track_name", name=trk.name, time=0))
            channel = trk.channel.channel % 16
            mtrack.append(
                mido.Message(
                    "program_change",
                    program=trk.channel.instrument % 128,
                    channel=channel,
                    time=0,
                )
            )
            tuning = {s.number: s.value for s in trk.strings}

            events: list[tuple[int, int, int, int]] = []  # (tick, on/off, pitch, velocity)
            cursor = 0
            for measure in trk.measures:
                voice = measure.voices[0] if measure.voices else None
                for beat in (voice.beats if voice else []):
                    length = beat.duration.time
                    for note in beat.notes:
                        if note.type == gpm.NoteType.rest:
                            continue
                        base = tuning.get(note.string)
                        if base is None:
                            continue
                        pitch = base + note.value
                        if not 0 <= pitch <= 127:
                            continue
                        # Clip slightly so repeated notes retrigger cleanly.
                        events.append((cursor, 1, pitch, min(127, note.velocity)))
                        events.append((cursor + max(1, int(length * 0.95)), 0, pitch, 0))
                    cursor += length

            events.sort(key=lambda e: (e[0], e[1]))
            last = 0
            for tick, kind, pitch, velocity in events:
                delta = tick - last
                last = tick
                mtrack.append(
                    mido.Message(
                        "note_on" if kind else "note_off",
                        note=pitch,
                        velocity=velocity,
                        channel=channel,
                        time=delta,
                    )
                )
            mid.tracks.append(mtrack)

        mid.save(path)
        return path

    # -- reading -----------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> "Tab":
        """Open an existing .gp3/.gp4/.gp5 file.

        Guitar Pro 7+ (.gpx, .gp) is a different container that PyGuitarPro
        cannot open -- export to .gp5 from Guitar Pro first.
        """
        ext = os.path.splitext(path)[1].lower()
        if ext in (".gpx", ".gp"):
            raise ValueError(
                f"{path} is a Guitar Pro 6/7+ file, which PyGuitarPro cannot "
                f"read. In Guitar Pro, use File > Export > Guitar Pro 5 first."
            )
        return cls(_song=gp.parse(path))

    def info(self) -> dict[str, Any]:
        """Structured summary of the song -- the thing to reach for when asked
        to analyze someone else's tab."""
        song = self.song
        tracks = []
        for i, trk in enumerate(song.tracks):
            note_count = sum(
                1
                for m in trk.measures
                for v in m.voices
                for b in v.beats
                for n in b.notes
                if n.type != gpm.NoteType.rest
            )
            frets = [
                n.value
                for m in trk.measures
                for v in m.voices
                for b in v.beats
                for n in b.notes
                if n.type != gpm.NoteType.rest
            ]
            tuning_low_first = [name_from_midi(s.value) for s in reversed(trk.strings)]
            tracks.append(
                {
                    "index": i,
                    "name": trk.name,
                    "strings": len(trk.strings),
                    "tuning": tuning_low_first,
                    "tuning_name": self._name_tuning(tuning_low_first),
                    "measures": len(trk.measures),
                    "notes": note_count,
                    "fret_range": [min(frets), max(frets)] if frets else None,
                    "instrument": trk.channel.instrument,
                    "is_percussion": trk.isPercussionTrack,
                }
            )
        signatures = []
        for h in song.measureHeaders:
            sig = (h.timeSignature.numerator, h.timeSignature.denominator.value)
            if not signatures or signatures[-1] != sig:
                signatures.append(sig)
        return {
            "title": song.title,
            "artist": song.artist,
            "album": song.album,
            "tempo": song.tempo,
            "measures": len(song.measureHeaders),
            "time_signatures": [f"{n}/{d}" for n, d in signatures],
            "tracks": tracks,
        }

    @staticmethod
    def _name_tuning(tuning_low_first: list[str]) -> str | None:
        for name, pitches in TUNINGS.items():
            if pitches == tuning_low_first:
                return name
        return None

    def to_riff(self, track: int = 0) -> str:
        """Round-trip a track back into riff notation.

        Handy for reading in an existing tab, transforming it, and writing it
        back out without hand-transcribing anything.
        """
        trk = self._track(track)
        measures_out = []
        for measure in trk.measures:
            voice = measure.voices[0] if measure.voices else None
            tokens = []
            for beat in (voice.beats if voice else []):
                d = beat.duration
                dur = f"{d.value}{'.' if d.isDotted else ''}"
                if d.tuplet and d.tuplet.enters == 3 and d.tuplet.times == 2:
                    dur += "t"
                live = [n for n in beat.notes if n.type != gpm.NoteType.rest]
                if not live:
                    tokens.append(f"{dur}:r")
                else:
                    parts = []
                    for n in live:
                        suffix = "x" if n.type == gpm.NoteType.dead else ""
                        if n.effect.vibrato:
                            suffix += "~"
                        if n.effect.hammer:
                            suffix += "h"
                        if n.effect.palmMute:
                            suffix += "m"
                        if n.effect.letRing:
                            suffix += "l"
                        if n.effect.ghostNote:
                            suffix += "g"
                        if n.effect.harmonic is not None:
                            suffix += "o"
                        if n.effect.bend is not None:
                            suffix += "b"
                        if n.effect.slides:
                            suffix += "/"
                        parts.append(f"{n.string}.{n.value}{suffix}")
                    tokens.append(f"{dur}:{'+'.join(parts)}")
            if tokens:
                measures_out.append(" ".join(tokens))
        return " | ".join(measures_out)

    def transpose(self, semitones: int, track: int | None = None) -> "Tab":
        """Shift pitch by moving frets, keeping the tuning fixed.

        Notes that would fall below the open string or above the last fret are
        left alone rather than silently wrapping to a wrong pitch -- the count
        of skipped notes is reported so you know the shift did not fit.
        """
        targets = self.song.tracks if track is None else [self._track(track)]
        skipped = 0
        for trk in targets:
            for measure in trk.measures:
                for voice in measure.voices:
                    for beat in voice.beats:
                        for note in beat.notes:
                            if note.type == gpm.NoteType.rest:
                                continue
                            new_fret = note.value + semitones
                            if 0 <= new_fret <= trk.fretCount:
                                note.value = new_fret
                            else:
                                skipped += 1
        if skipped:
            print(
                f"note: {skipped} note(s) left unchanged -- transposing them by "
                f"{semitones} would move them off the fretboard. Consider "
                f"retuning the track instead.",
                file=sys.stderr,
            )
        return self


# --------------------------------------------------------------------------
# GPIF repair
# --------------------------------------------------------------------------

# Guitar Pro's own file (.gp) is a zip containing Content/score.gpif. alphaTab
# writes a GPIF that alphaTab reads back perfectly and that Guitar Pro refuses
# to open -- it crashes with no error message. Every fix below comes from
# diffing alphaTab's output against a file Guitar Pro actually opens.
#
# Because the round trip through alphaTab succeeds either way, none of this is
# catchable by reloading the file you just wrote. If you extend the exporter,
# validate against a real Guitar Pro file, not against a re-import.

GP_LYRIC_LINES = 5  # Guitar Pro has exactly five lyric lines

_PERCUSSION_TUNING = (
    '<Property name="Tuning"><Pitches>0 0 0 0 0 0</Pitches>'
    "<Instrument>Undefined</Instrument><Label></Label>"
    "<LabelVisible>true</LabelVisible><Flat /></Property>"
)


def repair_gpif(path: str, lyrics: list[dict[str, Any]] | None = None) -> dict[str, int]:
    """Make an alphaTab-written .gp file openable in Guitar Pro.

    Fixes, all verified against a working Guitar Pro file:

    1. `FretCount` is written as `<Fret>` where Guitar Pro expects `<Number>`.
    2. Percussion staves are written with no `Tuning` property at all.
    3. Section `<Letter>` is a short rehearsal mark; a long section title there
       is fatal.
    4. Lyrics are written truncated to one word per line, with the wrong
       offsets and too many lines. They are rebuilt from `lyrics` here.
    5. Per-beat `<Lyrics>` elements are removed; Guitar Pro carries lyrics on
       the track, not the beat.
    """
    import xml.etree.ElementTree as ET
    import zipfile

    with zipfile.ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}

    key = next((n for n in members if n.endswith("score.gpif")), None)
    if key is None:
        raise ValueError(f"{path} has no score.gpif; is it really a .gp file?")

    xml = members[key].decode("utf-8")
    report: dict[str, int] = {}

    xml, count = re.subn(
        r'(<Property name="FretCount">)\s*<Fret>(\d+)</Fret>\s*(</Property>)',
        r"\1<Number>\2</Number>\3",
        xml,
    )
    report["fretcount"] = count

    root = ET.fromstring(xml)

    added = 0
    for track in root.find("Tracks"):
        staff = track.find(".//Staff")
        props = staff.find("Properties") if staff is not None else None
        if props is None:
            continue
        if "Tuning" not in {p.get("name") for p in props.findall("Property")}:
            props.append(ET.fromstring(_PERCUSSION_TUNING))
            added += 1
    report["tuning_added"] = added

    shortened = 0
    for measure in root.find("MasterBars"):
        section = measure.find("Section")
        if section is None:
            continue
        text = section.findtext("Text") or section.findtext("Letter") or ""
        match = re.match(r"\s*(\d{1,2}:\d{2})", text)
        short = match.group(1) if match else text[:6]
        letter = section.find("Letter")
        if letter is None:
            letter = ET.SubElement(section, "Letter")
        if letter.text != short:
            letter.text = short
            shortened += 1
        node = section.find("Text")
        if node is None:
            node = ET.SubElement(section, "Text")
        node.text = text
    report["sections"] = shortened

    stripped = 0
    for beat in root.find("Beats"):
        for element in beat.findall("Lyrics"):
            beat.remove(element)
            stripped += 1
    report["beat_lyrics_stripped"] = stripped

    lines = _lyric_lines(lyrics or [])
    for index, track in enumerate(root.find("Tracks")):
        for old in track.findall("Lyrics"):
            track.remove(old)
        block = ET.Element("Lyrics")
        block.set("dispatched", "true")
        mine = lines if index == 0 else []
        for i in range(GP_LYRIC_LINES):
            line = ET.SubElement(block, "Line")
            ET.SubElement(line, "Text").text = mine[i]["text"] if i < len(mine) else ""
            ET.SubElement(line, "Offset").text = str(mine[i]["bar"]) if i < len(mine) else "0"
        staves_at = next((n for n, c in enumerate(track) if c.tag == "Staves"), len(track))
        track.insert(staves_at, block)
    report["lyric_lines"] = len(lines)

    out = ET.tostring(root, encoding="unicode")
    if not out.startswith("<?xml"):
        out = '<?xml version="1.0" encoding="UTF-8"?>\n' + out
    members[key] = out.encode("utf-8")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        # VERSION goes first, matching how Guitar Pro writes the archive.
        if "VERSION" in members:
            archive.writestr("VERSION", members["VERSION"])
        for name, data in members.items():
            if name != "VERSION":
                archive.writestr(name, data)
    return report


def _lyric_lines(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold lyric blocks into Guitar Pro's five lines, keeping song order.

    Guitar Pro spreads a line's words one per beat from its start bar, so a
    line covering several sections places words in roughly the right region
    rather than exactly under the beat they are sung on.
    """
    if not blocks:
        return []
    ordered = sorted(blocks, key=lambda b: b.get("startBar", 0))
    per = (len(ordered) + GP_LYRIC_LINES - 1) // GP_LYRIC_LINES
    groups: list[list[dict[str, Any]]] = [[] for _ in range(GP_LYRIC_LINES)]
    for i, block in enumerate(ordered):
        groups[min(i // per, GP_LYRIC_LINES - 1)].append(block)
    lines = []
    for group in groups:
        if not group:
            continue
        text = " ".join(b["text"] for b in group)
        text = re.sub(r"\s+", " ", text).strip()
        lines.append({"bar": group[0].get("startBar", 0), "text": text})
    return lines


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and inspect Guitar Pro files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python gp_tab.py info song.gp5\n"
            "  python gp_tab.py ascii song.gp5 --track 0\n"
            "  python gp_tab.py riff out.gp5 --tuning 8-string --tempo 150 \\\n"
            "      --notes '8:8.0 8:8.0 8:8.3 | 4:8.0 4:r'\n"
            "  python gp_tab.py tunings\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="summarize a Guitar Pro file as JSON")
    p_info.add_argument("path")

    p_ascii = sub.add_parser("ascii", help="render a track as ASCII tab")
    p_ascii.add_argument("path")
    p_ascii.add_argument("--track", type=int, default=0)
    p_ascii.add_argument("--width", type=int, default=76)

    p_riff = sub.add_parser("riff", help="create a Guitar Pro file from riff notation")
    p_riff.add_argument("out")
    p_riff.add_argument("--notes", required=True)
    p_riff.add_argument("--title", default="Untitled")
    p_riff.add_argument("--artist", default="")
    p_riff.add_argument("--tempo", type=int, default=120)
    p_riff.add_argument("--tuning", default="standard")
    p_riff.add_argument("--instrument", default="distortion-guitar")
    p_riff.add_argument("--track-name", default="Guitar")
    p_riff.add_argument("--midi", help="also write a .mid file here")
    p_riff.add_argument("--print-ascii", action="store_true")

    sub.add_parser("tunings", help="list built-in tuning names")

    p_riffout = sub.add_parser("to-riff", help="dump a track as riff notation")
    p_riffout.add_argument("path")
    p_riffout.add_argument("--track", type=int, default=0)

    args = parser.parse_args(argv)

    if args.command == "tunings":
        for name, pitches in TUNINGS.items():
            print(f"{name:22} {' '.join(pitches)}  ({len(pitches)} strings)")
        return 0

    if args.command == "info":
        print(json.dumps(Tab.load(args.path).info(), indent=2))
        return 0

    if args.command == "ascii":
        print(Tab.load(args.path).ascii(track=args.track, width=args.width))
        return 0

    if args.command == "to-riff":
        print(Tab.load(args.path).to_riff(track=args.track))
        return 0

    if args.command == "riff":
        tuning: Sequence[str] | str = args.tuning
        if " " in args.tuning:
            tuning = args.tuning.split()
        # argparse hands back a string, but add_track also takes a General
        # MIDI program number, so '--instrument 30' has to survive the trip.
        instrument: str | int = args.instrument
        if instrument.isdigit():
            instrument = int(instrument)
        tab = Tab(
            title=args.title,
            artist=args.artist,
            tempo=args.tempo,
            tuning=tuning,
            track_name=args.track_name,
            instrument=instrument,
        )
        tab.riff(args.notes)
        tab.save(args.out)
        print(f"wrote {args.out}")
        if args.midi:
            tab.midi(args.midi)
            print(f"wrote {args.midi}")
        if args.print_ascii:
            print()
            print(tab.ascii())
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
