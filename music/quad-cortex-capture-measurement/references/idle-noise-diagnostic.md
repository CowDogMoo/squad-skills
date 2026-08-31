# Idle-noise diagnostic — what is the device actually running?

Use this when a measurement contradicts what Cortex Control displays, or
when you need to know whether an edit reached the device before asking for a
played take. Nobody touches the guitar; the whole test is silence.

## Why it works

The capture models the plugin's idle hiss, so a silent window's spectrum
carries the entire post-capture chain: capture Volume, EQ block, lane
output. An engaged HPF 55 shows up as roughly −14 dB at 20–30 Hz and −8 dB
at 30–45 Hz in the hiss. Capture Volume moves the QC−plugin broadband level
roughly dB-for-dB.

## Recording ~30 s of idle without touching Live's UI

Via `ableton-mcp` alone:

1. `set_song_time` past the last clip, then `start_playback`.
2. Punch in with F9 via `osascript` System Events key code 101. F9 while
   *playing* punches in at the playhead, so there is no bar-1 overwrite.
   Needs terminal accessibility permission.
3. Poll the growing WAV's size, then `stop_playback`.

## Analysing it

Take the quietest ≥ 8 s window per take. Compare **QC minus plugin** band
levels within each take — both hear the same input, so guitar-hum drift
cancels — then delta that across takes.

## The 2026-08-29 result

Fresh idle matched the flagged 21:17 take's idle within 1.1 dB in every
band: HPF signature absent, no makeup gain. The device was still running the
old state although Cortex Control had shown the edits saved (toast shown,
`*` cleared).

**USB audio alive does not mean Cortex Control is synced.** The app can save
to its local copy while the device runs something else. After reconnecting
and re-saving, confirm with a fresh idle spectrum before asking for a played
take.

Caveat on that session's evidence: the idle comparison was made at the same
Volume with the EQ bypassed in both takes, so on its own it cannot separate
"edit not applied" from "the EQ was off anyway". What settled it was a
Volume-step test on the 21:44 take, which showed the control reaching the
audio within a second, plus the EQ panel glyph confirming the block was
bypassed.

## Idle time skews the level offset

The capture's modelled noise floor sits about 13 dB below the plugin's, so a
take with pauses reads a more negative QC−plugin offset than the same preset
played continuously — measured 2026-08-29 at −8.5 dB idle-heavy versus
−6.6 dB continuous. Check the DI envelope in the plot and quote the offset
only from continuous playing.

A useful variant: one take, change one control mid-way, then compare 1 s RMS
ratios before and after. That proves whether the control reaches the audio.
