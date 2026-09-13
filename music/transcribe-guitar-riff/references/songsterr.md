# What Songsterr's player knows that our pipeline did not

Reverse-engineered on 2026-09-13 by driving the app in Chrome against the
user's own unpublished tab (songId 5625837, revision 7352403) and reading the
shipped bundles. Everything below is from an observed request or a string in
the client JS; anything not established is marked unknown rather than guessed.

This is here because a Songsterr tab of a song beat ours badly, and the reasons
turned out to be model choices, not signal processing.

## 1. The three ideas worth stealing

### A measured per-bar grid, not a BPM

`GET /api/useraudio/{songId}` returns, alongside the uploaded audio URL:

```json
{"audio":"https://user-audio.songsterr.com/….opus","status":"finished",
 "separationStatus":"not_started",
 "points":[0, 1.47, 2.95, 4.42, 5.91, …]}
```

`points` is **one onset per bar, in seconds, measured from the audio** — 105
points for a 105-measure tab. The implied per-bar tempo wobbles (163.27, 162.16,
163.27, 161.07, 164.38 …) because a real performance wobbles.

This is the single most valuable idea here, though the first reading of it was
wrong and the correction is instructive.

A clip has **two** tempos that matter and they are not the same number:

- the rate it was **recorded** at, which is what its own attacks sit on and
  therefore what you must READ it at;
- the rate the arrangement **plays** it at after warping, which is what a
  player needs and therefore what you must WRITE.

On this job the intro clips were recorded at **86 BPM** — confirmed three ways:
the Live warp markers, `tempo_fit.py`'s grid score (86.000 beating its
runner-up by 10.6% on one clip and 85.2% on another), and normalised drift
(30.6% of a grid step at 86 against 37.9% at 81.33 and 45.6% at 120). The
Songsterr grid reads ~81.235 for the same music because the mix that was
uploaded was rendered with the Ableton project at 81.3253, which warps those
86 BPM clips down.

So the original 86 was *not* an error. The actual error was writing the whole
tab at a single 120 BPM when the song changes tempo at bar 17. A per-bar grid
would have shown that immediately; a single BPM cannot express it at all.

`scripts/ss_convert.py grid USERAUDIO.json` turns `points` into
`{bar, onset_s, span_s, implied_bpm}` rows.

### A closed rhythm vocabulary

A beat is:

```json
{"duration":[1,16], "type":16, "dots":1, "tuplet":…, "rest":true,
 "notes":[{"string":4,"fret":7}], "beamStart":true, "beamStop":true}
```

`type` is the note value (1,2,4,8,16,32,64); `duration` is that value as a
fraction of a whole note; `dots` and `tuplet` modify it. Tuplets offered by
their editor: 3,5,6,7,9,10,11,12,13.

Measured on this tab's 105-bar lead track: **eight beat kinds counting rests
separately, seven distinct (type, dots, tuplet) note values** — 16th ×320,
32nd ×128, whole rest ×64, dotted quarter ×20, quarter ×8, half ×6, eighth ×4,
whole ×4. No tuplets, no double dots, and
`ss_convert.py check-durations` finds zero beats whose duration disagrees with
its declared note value.

Ours, by contrast, emitted **13 distinct durations** including 5/4, 7/4, 9/4,
5/2 and 7/2 quarter-notes — spans that cannot be written as one note value at
all, because they came from measuring gaps between attacks. The writer then
split each into several re-picked notes, which is why the tab read as a stutter
of repeated notes rather than as sustained or tied ones.

**Rule: decide durations from a closed set; never let an onset-to-onset span
become a duration.**

### Rests are first-class beats

Every bar's beats sum to its signature because rests are written as beats
(`{"rest":true, "duration":[1,1], "type":1, "notes":[{"rest":true}]}`). Our
spec left rests implicit, so a bar could quietly fail to add up.

## 2. The track data model

`GET https://dqsljvtekg760.cloudfront.net/{songId}/{revisionId}/{assetHash}/{trackIndex}.json`

The `assetHash` (e.g. `v0-3-2-pF-_HyeVUB3SOQAc`) is **not derivable** — read it
from a `performance.getEntriesByType('resource')` entry while the app is open.
The CDN returns 403 to a plain curl; it works from the page's context.

```
track = {
  measures: [ { signature?: [num, den],      // only on change; inherit otherwise
                voices: [ { beats: [beat] } ] } ],
  automations: { tempo: [ {measure, bpm, type, linear, position, visible} ] },
  tuning: [int],        // MIDI numbers, HIGHEST string first
  strings: int, frets: int,
  instrumentId: int, instrument: str, name: str,
  partId, songId, revisionId
}
```

- **String indexing runs high to low.** `tuning[0]` is the highest course. A
  note's pitch is `tuning[note.string] + note.fret`. Getting this backwards
  silently mirrors the whole tab.
- `automations.tempo` is **measure-indexed and 0-based**, with `linear` for
  ramps. On this tab: `{measure:0, bpm:162}` then `{measure:32, bpm:120}`.
- A `note` is `{string, fret}` or `{rest:true}`; articulations observed in the
  editor's own command list: tie, dot, doubleDot, tuplet3…13, rest, chord,
  pickStroke, tremoloVibrato, bend, slide, harmonic, vibrato, graceNote,
  letRing, palmMute, golpe, wah, accent. **Unknown:** the exact JSON encoding
  of each articulation — this tab is AI-generated and carries none of them, so
  there was nothing to observe.

## 3. The fingering cost model

The client lazy-loads `fingeringEngine-*.js`, exporting `calculateFingeringLabels`
and `isValidRulesConfig`, and fetches versioned rules from
`GET /api/fingering-ruleset/versions/{version}`. The baked default weights:

| term | default | what it does |
|---|---|---|
| `outOfReachPenalty` | 50 | cost when a shape exceeds the hand's reach |
| `crossStringJumpPenalty` | 50 | cost for changing string with both notes fretted |
| `crossStringJumpMinFretDelta` | 3 | …only when the fret delta is at least this |
| `directionalShiftBias` | 8 | prefers shifts that continue the current direction |
| `repeatedShiftLeadPenalty` | 16 | discourages shifting the same finger repeatedly |
| `crossStringPositionBias` | 1 | mild preference to stay in position across strings |
| `barreBias` | 0 | barre preference (off by default) |
| `rankScale` | 1 | overall scaling |

`horizontalReach` / `verticalReach` are lookup tables keyed by finger pair, not
scalars. Fingers are `index/middle/ring/pinky/open`; transitions are classified
`legato / shift / sustained / attacked`, with `abovelegato`, `aboveshift`,
`belowlegato`, `belowshift` variants.

Our `tab_build.py` scorer had fret-spread, mean fret, position continuity and a
string-stay bonus. It had **no reach limit and no cross-string jump penalty**,
which is how a lone fret 11 landed in the middle of a frets-3-to-7 riff.

## 4. Endpoint map (observed)

| Endpoint | Purpose | Auth |
|---|---|---|
| `/api/meta/{songId}` | song metadata | 403 `ERR_UNPUBLISHED` for unpublished tabs |
| `/api/meta/{songId}/{revisionId}` | revision metadata incl. `tracks[]` with `tuning`, `hash` | session |
| `/api/meta/{songId}/revisions` | revision list; carries `aiGenerated`, `createdVia` | session |
| `/api/useraudio/{songId}` | uploaded audio URL + the per-bar `points` grid | session |
| `/api/part-switching-markers/{songId}/{revisionId}` | section markers | needs `x-expected-user-id` |
| `/api/contributions/available-transcriptions-count` | AI quota — returned `{count:97, limit:100, maxDuration:20}` | session |
| `/api/song/transcription/process` | POST `{transcriptionId, revisionId?}` — triggers processing of an already-uploaded transcription | session |
| `/api/upload/sign`, `/api/upload/proxy` | upload flow for source audio | session |
| `/api/fingering-ruleset/versions/{v}` | versioned fingering rules | session |
| `/api/chords/{revisionId}/detect` | chord detection | session |
| `/api/audio/{songId}/{revisionId}/export` | audio export | session |
| `/api/rag-chat/*` | in-app LLM assistant | session |

**The AI transcription itself is server-side.** The client only uploads audio
and polls; there is no client-reachable "audio in, tab out" call to borrow.
`separationStatus` on `/api/useraudio` shows stem separation is a pipeline stage
they run too.

## 4b. The CDN JSON and the Guitar Pro export are NOT the same tab

This is the single most expensive thing on this page. The track JSON at
`dqsljvtekg760.cloudfront.net/{song}/{rev}/{hash}/{track}.json` is not what the
player shows and not what Download -> Guitar Pro produces. On the reference
revision they differ in the intro's fingering (fret 7 on the F2 string vs fret 12
on C2) and in bars 17-21 (frets 2/1/2/3 vs 5/4/5/6). Two rounds were lost
building from the JSON.

**Always take the export.** It is generated client-side as a blob, so it is
exactly what is on screen - but that means a synthetic `.click()` will not fire
it. Use a real computer-use click on Download -> Guitar Pro.

**And then diff the two, because the difference is a gift.** A Songsterr
revision marked `aiGenerated: true` is a machine transcription that a human may
have partly edited, and the edits live only in the published revision. Where the
JSON and the export agree, you are looking at raw machine output. Where they
differ, somebody with ears decided something.

On the reference revision the export raises bars 17-21 by a minor third and
leaves bars 22-52 where the JSON had them. That is not a musical event at bar 22

- it is an editor who corrected five bars and stopped. The corrected bars are
then the best available specification for the uncorrected ones, including *what
kind* of correction to make: at bars 20-21 the editor moved the palm-muted chug
and left the ringing note alone, so bars 22-32 got the same treatment rather than
a blanket transpose.

So the routine is: pull both, diff them, and treat an edited region as ground
truth and as a worked example for the regions nobody got to.

Corollary for any AI-generated tab, Songsterr's or ours: **a wholesale key error
over one section is a realistic failure mode, and downstream checks will not
catch it.** The user is the fastest detector - "these should be the same as the
ones before" took one message and settled what a day of spectra had circled.

## 5. What this changes in our pipeline

1. Take the bar grid from measurement, per bar, not a constant BPM
   (`ss_convert.py grid`). Where no such grid exists, derive one and check it
   against the audio bar by bar instead of trusting warp markers.
2. Quantise every duration to a closed note-value set before writing.
3. Write rests explicitly so bars are verifiably complete.
4. Add reach and cross-string-jump terms to the fretting scorer.
5. Index strings the way the target format does, and assert it — high-first
   here, low-first in our spec.

## 6. Provenance and limits

This was the user's **own** unpublished tab, read through their own signed-in
browser session at their request. The CDN asset hash is session-scoped and the
converter therefore works from a **saved JSON file**; nothing in our pipeline
fetches Songsterr at run time. The tab itself is `aiGenerated: true`, so it is a
machine reading too — on the heavy riff our measured pitches fit the recording
better than its do (see the project's `songsterr/COMPARISON.md`). What it is
unambiguously better at is being a *tab*: repeating, readable, playable.
