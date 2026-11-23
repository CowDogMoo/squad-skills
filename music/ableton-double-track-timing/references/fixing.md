# Fixing: moving clips in Live safely (only on explicit request)

## The socket

Live's AbletonMCP control surface listens on `127.0.0.1:9877`. Send one JSON
object per connection, `{"type": <command>, "params": {...}}`, and get back
`{"status": "success"|"error", "result"|"message": ...}`. Track and clip
indices are 0-based. Clip indices are the clip's position in
`track.arrangement_clips` and shift after every move, so re-read the track
before each command (`apply_moves.py` does this).

| Command | Params | Use |
| --- | --- | --- |
| `get_arrangement_info` | `track_index` (-1 = all; group tracks are skipped but keep their index) | Snapshot and verification |
| `move_arrangement_clip` | `track_index`, `clip_index`, `destination_time` (beats) | Copy, verify, then delete the original. Returns `overlapped_clips` |
| `set_arrangement_clip_property` | `track_index`, `clip_index`, `property`, `value` | `loop_end` (beats on warped clips) moves an unlooped clip's end |

Some older remote-script builds lack newer MCP tools such as `set_track_mute`.
If a tool says "Unknown command", talk to the socket directly; the commands
above are the ones the fix needs.

## Move order and overlaps

Live truncates any clip that a moved clip lands on. Order the moves so a
destination never overlaps a clip that hasn't moved yet:

- When moving clips later, move the latest first.
- When moving clips earlier, move the earliest first.

`apply_moves.py` simulates the order per track. If no safe order exists, it
refuses before touching anything. It also stops if a move reports
`overlapped_clips`, or if any neighbour's start or end changed.

## Gaps

A move opens a gap against a clip it used to touch:

- Moving a clip earlier leaves a gap after it.
- Moving a clip later leaves a gap before it.

The dry run lists these. `--close-gaps` extends the earlier clip's
`loop_end` by the gap so the clips meet again. That only works on warped
clips, because unwarped clips keep loop values in seconds. Closing reveals
a little more of the take, which is usually the natural continuation.
Leave the gap open when that audio is noise or ringing; on gated scratch
DIs a 30 ms gap is inaudible.

## Procedure

1. Write `plan.json`: `{"moves": [{"track": "Name or #idx", "from": 357.0625, "to": 357.0}]}`.
   The `from` value is the clip's current start, exact to 4 decimals (take it
   from the placement report).
2. Dry run: `python scripts/apply_moves.py plan.json --als SET.als`. Show the
   order and gaps to the user.
3. Make sure the transport is stopped (the script refuses otherwise), then
   run `python scripts/apply_moves.py plan.json --execute --out fix/ [--close-gaps]`.
4. Ask the user to save. Then re-run `placement_check.py` (the fixed flags
   should be gone) and `attack_audit.py --range` over the fixed bars, plus
   `render_xcheck.py` if you rendered before.
5. Run `python scripts/collateral.py --before fix/pre_fix_snapshot.json --live --allowed fix/applied_moves.json`
   and expect COLLATERAL OK. Offline after saving, the same check is
   `--after SET.als`.
6. If anything is wrong, Live's Undo (Cmd+Z) reverts each move. Moves are
   copy plus delete, so expect two undo steps per move.

## Rendering stems for the cross-check

Use the ableton-live-computer-use skill. These lessons came from a session
where a stray keystroke deleted selected tracks:

- Export one track at a time: pick it in Export Audio/Video's **Rendered
  Track** dropdown, and type **Render Start** and **Length**. Don't select
  time or tracks in the arrangement.
- Screenshot before every dropdown pick. The list's position shifts with the
  current choice.
- Close Settings and plug-in windows and stop the transport before
  exporting. Another app taking focus breaks the Save panel.
- Press Esc after every export so nothing stays selected.
- The export tool may report failure when the file is fine (a timeout, or a
  length computed across a tempo change). Poll for the file and check its
  duration yourself.
- Render the fewest stems that settle the question: one per side of the
  pair, over the bars in doubt. Re-render only the fixed section afterwards,
  and pass it as a later `--stem`.
