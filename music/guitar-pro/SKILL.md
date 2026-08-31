---
name: guitar-pro
description: Create, read, edit, and analyze Guitar Pro tablature (.gp5/.gp4/.gp3, native .gp, MusicXML) using the bundled gp_tab.py helper. Use whenever the user wants a riff, lick, exercise, chord progression, drill, or arrangement written out as a real tab file they can open in Guitar Pro — and equally when they want an existing tab read, summarized, transposed, re-tuned, exported to MIDI, or rendered as ASCII. Trigger on "Guitar Pro", ".gp5", ".gpx", "tab", "tablature", "guitar tab", "bass tab", "riff", "write me a lick", "practice exercise", "chord chart", "transpose this tab", "what tuning is this in", or any request involving frets, strings, tunings (drop D, drop C, DADGAD, open G), extended-range instruments (7-string, 8-string, 9-string, baritone), or bass. Also use it to turn a chord progression, scale, or MIDI idea into notation a guitarist could read and play. Do NOT use for transcribing audio recordings into tab, or for music theory questions needing no file.
---

# Guitar Pro tablature

Write and read real Guitar Pro files instead of ASCII approximations. The
bundled `scripts/gp_tab.py` wraps PyGuitarPro and handles the parts of that
library that fail silently — producing files that open, sound, and notate
correctly.

## Why the helper exists

PyGuitarPro is a faithful but very low-level mapping of a 1990s binary format.
Three of its defaults are actively wrong for anyone writing a tab, and all
three fail *silently* — the file writes without an error and looks plausible
until you open it:

- `Note.type` defaults to `rest`, so notes you carefully placed make no sound.
- `Beat.status` defaults to `empty`, which writes a zero-length beat. Guitar
  Pro stacks every following beat at the same tick, so an entire measure
  collapses onto beat one. The notes are all there; the rhythm is gone.
- Measures live on the song *and* on each track. Add a measure header without
  adding the matching `Measure` to every track and the file reads truncated.

`gp_tab.py` gets these right and raises loudly on anything it cannot represent.
Reach for it first; drop to raw PyGuitarPro only for something it doesn't cover,
and read `references/pyguitarpro-notes.md` before you do.

## Setup

Install the dependencies into a virtualenv inside this skill directory, so
nothing lands in the system Python:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r scripts/requirements.txt
```

Then run everything with `.venv/bin/python` instead of `python3`. Without `uv`,
`python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt`
does the same job.

`mido` is only needed for MIDI export. Everything else works without it. Native
`.gp` export additionally needs Node and `npm install @coderline/alphatab` in
`scripts/`; `save()` falls back to MusicXML with a clear message when it is
absent.

## The seven-string ceiling — read this before writing extended range

The `.gp3/.gp4/.gp5` binary format encodes which strings a beat uses as bit
flags in a single byte (`1 << (7 - string_number)`). **Seven strings is a hard
ceiling of the file format**, not a library limitation and not something a
workaround can lift. An 8-string part written to `.gp5` produces a crash or a
corrupt file.

So route by string count:

| Strings | Write to | Opens in |
|---|---|---|
| 4–7 (bass, standard, 7-string, baritone) | `.gp5` | Guitar Pro 5, 6, 7, 8 |
| 8+ (8-string, 9-string) | `.gp` (native GP7) — best | Guitar Pro 7, 8 |
| 8+, no Node available | `.musicxml` | Guitar Pro 7/8, MuseScore, Dorico |

`.gp` is the better 8-string answer when you can produce it: it's a real Guitar
Pro file that opens with a double-click, no import step. It goes through
`scripts/gp7_export.mjs`, which needs Node and `@coderline/alphatab`:

```bash
cd scripts && npm install @coderline/alphatab
```

If that isn't available, `.musicxml` is a perfectly good fallback — Guitar Pro
7 and 8 import it with tuning and tablature intact, it just costs the user one
extra step. `tab.gp7(path)` raises with install instructions rather than
failing obscurely, so `try` it and fall back.

ASCII and MIDI output work at any string count. `save()` refuses an oversized
`.gp5` with a message naming the alternatives rather than writing a broken
file, so you don't have to memorize this — but you *should* tell the user which
format you picked and why when they're on an 8-string, because an unexplained
`.musicxml` is a surprise.

## Riff notation

Beats are written `DURATION:NOTES`, separated by spaces, with `|` between
measures. This is the fastest correct way to get music into a file — prefer it
over building `Beat` and `Note` objects by hand.

```
8:6.5          eighth note, string 6, fret 5
4:5.7+4.7      quarter-note chord, two strings struck together
16:7.0x        sixteenth, dead/muted note
4.:6.3         dotted quarter (the dot rides on the duration)
8t:6.5         triplet eighth
2:r            half rest
```

**Strings are numbered 1 = highest/thinnest.** On a 6-string, string 6 is low
E; on a 7-string, string 7 is the low B; on an 8-string, string 8 is the low
F#. This matches Guitar Pro's own numbering, so it also matches what the user
sees on screen.

Durations are `1, 2, 4, 8, 16, 32, 64`, optionally `.` for dotted or `t` for
triplet.

Note suffixes stack: `x` dead · `~` vibrato · `h` hammer-on · `p` pull-off ·
`/` slide · `b` bend · `g` ghost · `o` natural harmonic · `m` palm mute ·
`l` let ring.

A palm-muted low-string chug pattern in drop tuning:

```
16:7.0m 16:7.0m 16:7.0m 8:7.3 16:7.0m 8:7.5 | 4:7.0+6.0 2:5.7~ 4:r
```

## Writing a tab

```python
import sys; sys.path.insert(0, "scripts")
from gp_tab import Tab

tab = Tab(
    title="Warmup",
    artist="Example Artist",
    tempo=140,
    tuning="7-string",          # name from TUNINGS, or ["B1","E2","A2",...]
    track_name="Guitar",
    instrument="distortion-guitar",
)
tab.riff("16:7.0m 16:7.0m 16:7.3 8:7.0 | 4:7.0+6.0 4:r 2:5.7~")
tab.save("warmup.gp5")
tab.midi("warmup.mid")
print(tab.ascii())
```

Repeated `riff()` calls append, so build a song section by section — verse,
then chorus — rather than assembling one enormous string.

Add another instrument with `add_track()`, then aim `riff()` at it:

```python
bass = tab.add_track(name="Bass", tuning="bass-5", instrument="bass")
tab.riff("4:5.0 4:5.3 8:5.5 8:r", track=bass)
```

Tunings are written **low string first**, the way players say them out loud
("drop C is C G C F A D"). Built-ins cover standard, drop D/C/B, D and C
standard, open D/G, DADGAD, 7- and 8- and 9-string, drop variants, baritone B/A/C,
and 4/5/6-string bass. Run `python scripts/gp_tab.py tunings` for the list, or
pass explicit scientific pitch names like `["F#1","B1","E2","A2","D3","G3","B3","E4"]`.

## Reading and analyzing a tab

```python
tab = Tab.load("song.gp5")
tab.info()        # title, tempo, per-track tuning + string count + fret range
tab.ascii()       # readable tab, proportional to rhythm
tab.to_riff()     # back into riff notation, so you can edit and rewrite it
tab.transpose(-2) # move frets, keeping tuning fixed
```

`info()` names the tuning when it recognizes it, which is usually the fastest
answer to "what tuning is this in?" `to_riff()` closes the loop: read an
existing tab, transform the notation as text, write it back out — no hand
transcription.

Guitar Pro 6/7+ files (`.gpx`, `.gp`) are a different container that PyGuitarPro
cannot open. If the user has one, tell them to use **File → Export → Guitar Pro 5**
in Guitar Pro first; `Tab.load()` says the same thing if you try.

## Command line

Useful for one-liners and for checking your work without writing a script:

```bash
python scripts/gp_tab.py info song.gp5
python scripts/gp_tab.py ascii song.gp5 --track 0
python scripts/gp_tab.py to-riff song.gp5
python scripts/gp_tab.py tunings
python scripts/gp_tab.py riff out.gp5 --tuning 7-string --tempo 150 \
    --notes '8:7.0 8:7.3 4:r' --midi out.mid --print-ascii
```

## What to deliver

Unless the user says otherwise, hand back **the tab file plus an ASCII preview
plus MIDI**:

1. The `.gp5` (or `.musicxml` for 8+ strings) — the thing they actually open.
2. ASCII printed in your reply, so they can sanity-check the notes and rhythm
   without launching anything.
3. A `.mid` alongside it, for dropping into a DAW.

Send files with the file-delivery tool rather than only describing them.

## Verify before you deliver

Musical output fails in ways that a successful `save()` will not reveal, so
spend the extra few seconds:

- **Check the bar math.** `tab.check_measures()` returns every measure whose
  beats don't add up to its time signature. A bar that's an eighth short still
  opens fine and still looks fine — it just drags everything after it off the
  grid, which the user experiences as "the riff feels wrong" rather than as an
  error. `save()` warns automatically; an empty list from `check_measures()` is
  the thing to confirm before you hand anything over.
- **Reload and render.** `Tab.load(path).ascii()` on the file you just wrote.
  If beats collapsed or notes landed on the wrong string, you see it instantly.
  Note the limit: a reload only proves the writer and reader agree with each
  other. For `.gp` files it says nothing about whether Guitar Pro will open the
  file — see the GPIF table in `references/pyguitarpro-notes.md`.
- **Check the note count** in `info()` against how many you meant to write.
- **Read the ASCII as a player would.** Are the frets reachable in one position,
  or did you write a stretch from fret 2 to fret 14? Is the low string doing the
  riff and the high strings empty, as you'd expect for a chug pattern?
- **Sanity-check the pitch**, not just the fret. On a 7-string in B standard,
  string 7 fret 0 is B1 (MIDI 35) — `info()` reports the tuning so you can
  confirm the part sits where the user expects.

`.venv/bin/python scripts/test_gp_tab.py` runs 137 checks over the helper
itself (plus a native-`.gp` block that skips when Node or alphaTab is missing).
Run it if you change `gp_tab.py`, or if something behaves unexpectedly and you
want to rule the helper out. See Setup above for the virtualenv it needs.

## Writing music that's worth playing

The file mechanics are the easy half. When the user asks for a riff, an
exercise, or a progression, they're asking for something *musical*, so:

- **Honor the instrument.** A request on an 8-string in F# standard usually
  wants the low strings doing the work; writing everything in first position on
  the top three strings ignores why they own that guitar.
- **Match the idiom.** Chugs want palm mutes (`m`) and tight sixteenths. A
  clean arpeggio wants let-ring (`l`). Legato lines want hammers and pulls.
  The effect suffixes exist so the notation reads the way the music sounds.
- **Keep it playable** unless asked otherwise — reachable stretches, sensible
  position shifts, and a tempo that matches the note density you wrote.
- **Say what you wrote.** A sentence on the key, the pattern, and where it sits
  on the neck is worth more to the user than a description of the file format.

If the request is ambiguous in a way that changes the music — tempo, key,
length, feel, tuning — ask before writing, since a tab is cheap to get wrong
and annoying to re-read.

## Reference

`references/pyguitarpro-notes.md` documents the PyGuitarPro API details, the
silent-failure modes and their causes, the MusicXML tab structure, and the
General MIDI instrument numbers. Read it when extending `gp_tab.py` or when you
need something the helper doesn't expose.
