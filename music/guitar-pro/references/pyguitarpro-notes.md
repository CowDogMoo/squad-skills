# PyGuitarPro reference notes

Everything here was verified empirically against the installed PyGuitarPro
(the `guitarpro` package) rather than taken from documentation, because several
of the library's behaviors are undocumented and a few published examples on the
web are written against an older API that no longer exists.

## Contents

- [Silent failure modes](#silent-failure-modes)
- [Object model](#object-model)
- [String numbering and tuning](#string-numbering-and-tuning)
- [Format limits](#format-limits)
- [Durations and timing](#durations-and-timing)
- [Effects](#effects)
- [Stale APIs that no longer exist](#stale-apis-that-no-longer-exist)
- [MusicXML tablature structure](#musicxml-tablature-structure)
- [General MIDI instruments](#general-midi-instruments)

---

## Silent failure modes

These are the ways a script produces a file that saves without error and is
still wrong. All three are handled inside `gp_tab.py`; this section is for when
you write something new.

### 1. `Beat.status` defaults to `empty`

The worst one. `Beat.status` is an attrs field defaulting to
`BeatStatus.empty`. The writer checks it:

```python
if beat.status != gp.BeatStatus.normal:
    flags |= 0x40      # marks the beat as empty in the file
```

and the reader treats an empty beat as zero-length:

```python
return duration.time if not beat.status == gp.BeatStatus.empty else 0
```

`readVoice` advances its cursor by that return value and calls
`getBeat(voice, start)`, which returns *the existing beat at that tick* rather
than making a new one. So every beat in the measure lands at tick 0 and merges
into one object. Write four sixteenth notes, read back one beat holding four
notes. The notes survive; the rhythm does not.

Always set it:

```python
beat.status = gpm.BeatStatus.normal   # a beat with notes
beat.status = gpm.BeatStatus.rest     # a rest
```

### 2. `Note.type` defaults to `rest`

`NoteType` is `rest | normal | tie | dead`, defaulting to `rest`. A note with
`value` and `string` set but `type` left alone is written as a silent rest.

```python
note.type = gpm.NoteType.normal   # or .dead for an x
```

### 3. Measures exist twice

A measure is a `MeasureHeader` on `song.measureHeaders` *and* a `Measure` on
every `track.measures`. Adding one without the other yields a file that reads
truncated or renders blank measures on some tracks.

`song.newMeasure()` does both, but numbers every header `1`. Setting
`MeasureHeader(number=...)` correctly matters for repeats and navigation.

A fresh `Song()` also arrives with one track and one measure header already
attached — append to those blindly and the file gains a phantom empty
"Track 1".

### 4. `Measure.voices` must be fully populated

`gp5.writeMeasure` iterates `measure.voices[:Measure.maxVoices]`
(`maxVoices == 2`). A measure with fewer voice objects than that writes short.
Construct all of them, leaving the second empty if unused.

---

## Object model

```
Song
├── tempo (int, song-level — there is no per-measure tempo field)
├── title / artist / album
├── measureHeaders: [MeasureHeader]   (timeSignature, keySignature, repeats)
└── tracks: [Track]
    ├── strings: [GuitarString(number, value)]   value = MIDI pitch of open string
    ├── channel: MidiChannel(channel, effectChannel, instrument, volume, ...)
    ├── fretCount (default 24)
    └── measures: [Measure]           one per MeasureHeader, same order
        └── voices: [Voice] × 2
            └── beats: [Beat]
                ├── duration: Duration(value, isDotted, tuplet)
                ├── status: BeatStatus
                └── notes: [Note(value=fret, string=..., type=..., effect=...)]
```

Tempo is song-level: `song.tempo`. `MeasureHeader` has **no** `tempo`
attribute. Mid-song tempo changes go through a `MixTableChange` on a beat.

Constructors take their parent positionally: `Measure(track, header)`,
`Voice(measure)`, `Beat(voice)`, `Note(beat)`. Appending to the parent's list
is a separate step the constructor does not do for you.

---

## String numbering and tuning

**String 1 is the highest-pitched string.** On a standard 6-string, a default
`Track` has:

```
GuitarString(number=1, value=64)   E4  (thinnest)
GuitarString(number=2, value=59)   B3
GuitarString(number=3, value=55)   G3
GuitarString(number=4, value=50)   D3
GuitarString(number=5, value=45)   A2
GuitarString(number=6, value=40)   E2  (thickest)
```

`value` is the MIDI pitch of the open string, so sounding pitch is
`string.value + note.value` (open-string pitch plus fret).

Players say tunings low-to-high ("drop C is C G C F A D"), which is the reverse
of this order. `gp_tab.py` takes tunings low-first and reverses internally;
if you build tracks by hand, do the same or your low string ends up on top.

Scientific pitch notation, middle C = C4 = MIDI 60:

| String | Standard | Drop D | 7-string | 8-string | Baritone B | Bass |
|---|---|---|---|---|---|---|
| lowest | E2 (40) | D2 (38) | B1 (35) | F#1 (30) | B1 (35) | E1 (28) |
| highest | E4 (64) | E4 (64) | E4 (64) | E4 (64) | B3 (59) | G2 (43) |

---

## Format limits

`gp3.writeNotes` builds a per-beat bitmask of which strings are used:

```python
stringFlags |= 1 << (7 - note.string)
```

String 8 gives a negative shift and raises `ValueError: negative shift count`,
surfaced as `GPException: writing track 1, measure 1, voice 1, beat 1`.

**Seven strings is a hard ceiling for .gp3, .gp4 and .gp5.** It is a property
of the file format's on-disk layout, so no library version or workaround lifts
it. Eight-string and nine-string parts have to travel as MusicXML.

Other boundaries:

- `.gpx` and `.gp` (Guitar Pro 6/7+) cannot be read or written at all — they
  are a zip-based container PyGuitarPro does not implement. Export to
  Guitar Pro 5 from within Guitar Pro first.
- Version tuples for writing: `(3, 0, 0)`, `(4, 0, 6)`, `(5, 1, 0)`.
- Percussion belongs on MIDI channel 9.

---

## Durations and timing

`Duration.quarterTime == 960` ticks per quarter note. `Duration.time` gives the
tick length, accounting for dots and tuplets:

| Duration | `value` | ticks |
|---|---|---|
| whole | 1 | 3840 |
| half | 2 | 1920 |
| quarter | 4 | 960 |
| dotted quarter | 4 + `isDotted` | 1440 |
| eighth | 8 | 480 |
| triplet eighth | 8 + `Tuplet(3, 2)` | 320 |
| sixteenth | 16 | 240 |
| thirty-second | 32 | 120 |

On disk the duration byte is `value.bit_length() - 3` (quarter → 0, eighth → 1),
read back as `1 << (byte + 2)`.

`TimeSignature.denominator` is itself a `Duration`, not an int:

```python
gpm.TimeSignature(numerator=7, denominator=gpm.Duration(value=8))   # 7/8
```

---

## Effects

`NoteEffect` fields: `accentuatedNote`, `bend`, `ghostNote`, `grace`, `hammer`,
`harmonic`, `heavyAccentuatedNote`, `leftHandFinger`, `letRing`, `palmMute`,
`rightHandFinger`, `slides`, `staccato`, `tremoloPicking`, `trill`, `vibrato`.

`BeatEffect` fields: `stroke`, `hasRasgueado`, `pickStroke`, `chord`, `fadeIn`,
`tremoloBar`, `mixTableChange`, `slapEffect`, `vibrato`.

Note that palm mute and let ring live on the **note**, not the beat.

`slides` is a list of `SlideType`: `intoFromAbove (-2)`, `intoFromBelow (-1)`,
`none (0)`, `shiftSlideTo (1)`, `legatoSlideTo (2)`, `outDownwards (3)`,
`outUpwards (4)`.

A bend needs points, not just a value — a bare `BendEffect` renders as nothing:

```python
gpm.BendEffect(
    type=gpm.BendType.bend, value=50,
    points=[gpm.BendPoint(position=0, value=0),
            gpm.BendPoint(position=6, value=4),
            gpm.BendPoint(position=12, value=4)],
)
```

`position` runs 0–12 across the note; `value` is in quarter tones, so 4 is a
full step.

---

## Stale APIs that no longer exist

Code found online (including at least one published Guitar Pro MCP server) uses
these. They raise `AttributeError` against the current library:

| Stale | Current |
|---|---|
| `note.isTiedNote` | `note.type == NoteType.tie` |
| `song.author` | `song.artist` |
| `guitarpro.models.write_midi` | never existed; use `mido` |
| `song.addMeasureHeader()` with no args | takes a `header` argument |

If a transpose or export function returns `False` for no clear reason, one of
these inside a swallowed `try/except` is the usual cause.

---

## Native GP7 export via alphaTab

The nicer escape hatch for 8+ strings, used by `scripts/gp7_export.mjs`.
Guitar Pro 6/7/8 files are a zip containing `Content/score.gpif` (XML), with no
string-count limit. PyGuitarPro cannot write them, but alphaTab can.

```bash
cd scripts && npm install @coderline/alphatab
```

Building the score model directly is more predictable than generating alphaTex
and importing it. Two API details cost real debugging time:

- **`Score.tempo` is getter-only.** Setting it throws
  `TypeError: Cannot set property tempo of #<Score> which has only a getter`.
  Tempo is derived from an automation on the first master bar:

  ```js
  masterBar.tempoAutomations = [model.Automation.buildTempoAutomation(false, 0, bpm, 2)];
  ```

- **alphaTab numbers strings the opposite way from Guitar Pro.** In alphaTab,
  `note.string = 1` is the *lowest* string, and `staff.stringTuning.tunings` is
  ordered *highest* first. PyGuitarPro uses 1 = highest. `gp7_export.mjs`
  flips both, so callers keep using the skill's convention throughout.

Call `score.finish(new alphaTab.Settings())` before exporting, then
`new alphaTab.exporter.Gp7Exporter().export(score, settings)` returns a
`Uint8Array` to write straight to disk.

Verify by re-importing:
`alphaTab.importer.ScoreLoader.loadScoreFromBytes(bytes, settings)`.

### alphaTab writes GPIF that Guitar Pro will not open

This matters more than the API details above. alphaTab's `Gp7Exporter` produces
a file alphaTab reads back perfectly and **Guitar Pro crashes on** -- no error
dialog, the application just dies. Because the round trip succeeds, reloading
the file you wrote proves nothing. `repair_gpif()` in `gp_tab.py` fixes all of
the following, each found by diffing against a Guitar Pro file that does open:

| Defect | What alphaTab writes | What Guitar Pro needs |
|---|---|---|
| `FretCount` | `<Fret>24</Fret>` | `<Number>24</Number>` |
| Percussion staff | no `Tuning` property | `<Tuning><Pitches>0 0 0 0 0 0</Pitches>…` |
| Percussion notes | no `String`/`Fret`, duplicated `ConcertPitch` | both present, once each |
| Section `<Letter>` | whatever you set as the marker | a short rehearsal mark ("A", "0:00") |
| Lyrics | one line per block, text truncated to its first word, every `Offset` set to the block count | exactly 5 `<Line>`s, `Offset` = start bar, full text |
| Beat `<Lyrics>` | emitted per beat | never used; lyrics live on the track |

Percussion notes also need `note.string` and `note.fret` set before export --
alphaTab drops them on import and does not regenerate them, and Guitar Pro
positions the note on the staff from those fields.

**Validate against a real Guitar Pro file, never against a re-import.** The only
reliable check is to open the result in Guitar Pro, or to diff its GPIF against
a file known to open.

## MusicXML tablature structure

The escape hatch for 8+ strings. Guitar Pro 7/8, MuseScore, and Dorico all
import it with tablature intact.

```xml
<attributes>
  <divisions>960</divisions>            <!-- ticks per quarter; match Duration.quarterTime -->
  <key><fifths>0</fifths></key>
  <time><beats>4</beats><beat-type>4</beat-type></time>
  <clef><sign>TAB</sign><line>5</line></clef>
  <staff-details>
    <staff-lines>8</staff-lines>
    <staff-tuning line="1">           <!-- line 1 = BOTTOM = lowest string -->
      <tuning-step>F</tuning-step>
      <tuning-alter>1</tuning-alter>  <!-- 1 = sharp -->
      <tuning-octave>1</tuning-octave>
    </staff-tuning>
    <!-- ... one per string, counting up ... -->
  </staff-details>
</attributes>
```

The critical inversion: MusicXML numbers **staff lines bottom-up** (line 1 is
the lowest-pitched string), while the `<string>` element inside
`<notations><technical>` numbers strings **high-to-low**, matching Guitar Pro.
So line 1 corresponds to `<string>N</string>` where N is the string count.

Each note carries both its sounding pitch and its fretboard position:

```xml
<note>
  <pitch><step>F</step><alter>1</alter><octave>1</octave></pitch>
  <duration>480</duration>
  <voice>1</voice>
  <type>eighth</type>
  <notations><technical>
    <string>8</string><fret>0</fret>
  </technical></notations>
</note>
```

Subsequent notes of a chord repeat the structure with `<chord/>` as the first
child. Rests use `<rest/>` in place of `<pitch>`.

---

## General MIDI instruments

Stored on `track.channel.instrument`, zero-based (MusicXML wants it one-based).

| Program | Instrument |
|---|---|
| 24 | Nylon acoustic guitar |
| 25 | Steel acoustic guitar |
| 26 | Jazz electric guitar |
| 27 | Clean electric guitar |
| 28 | Muted electric guitar |
| 29 | Overdriven guitar |
| 30 | Distortion guitar |
| 31 | Guitar harmonics |
| 33 | Finger bass |
| 34 | Picked bass |
| 35 | Fretless bass |
| 38 | Synth bass |
| 0 | Acoustic grand piano |
| 48 | String ensemble |
