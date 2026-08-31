# Screen-control workarounds for Cortex Control

Read this when clicks are not landing where they are aimed, when a control
refuses every input form, or when the app will not come forward.

## The click-offset bug

Hover (`computer_mouse_move`) lands where aimed, but every click and
mouse-down lands a fixed ~260–270 px **above** the aim point, on both
monitors. Observed across two sessions at 270 px and 260 px.

**Symptoms.** Clicking a row-3 block opens the preset browser or switches
scenes. Clicks in the top ~260 px do nothing. Double-clicks deselect the block
instead of entering a value field.

**Diagnosis, one call:** `computer_cursor_position` immediately after a click
reports `y − 260`. Otherwise probe-click something harmless whose y is unique —
a scene button, a left-panel category — never a block's `x`.

It is app-side. The displays are top-aligned in System Settings, so there is
nothing for the user to rearrange; report it through thumbs-down feedback.

**What does not work:** `left_mouse_down` / `up` at an exactly-moved cursor do
not register either, so move+down+up is not a workaround.

### Working around it

Aim `y_real + offset` for every click. Two ways to reach the bottom band that
the offset puts out of range:

1. **Shrink the window** (better — window-level drags work through the
   offset). Drag its top-left corner down ~260 px: start at corner `y+260`,
   end at corner `y+520`. Then drag the title bar back to the top: start at
   bar `y+260`, end at 286. The window then ends around y 555, and the
   wizard's FILL METADATA / START / SAVE plus the bottom bar become reachable.
   Verify by toggling GIG VIEW at its `y+260` and back.

   **Moving a window upward needs the Finder grant.** Any drag that ends above
   the window ends over bare desktop, and the click guard refuses it with
   "would land on the desktop shell". `computer_resolve_access` /
   `computer_request_access` with exactly `Finder` clears it — one extra
   approval, and window drags then work normally. Resizing from the top-left
   corner does not need it; only the reposition does. The window's bottom edge
   is usually unreachable (its `y+260` exceeds the frame), so shrink from the
   top corner and then move, never the other way round.
2. **Gig View.** Have the user click GIG VIEW in the bottom bar. The selected
   row then sits at y~177, panel title and power at y~322, value text at
   y~432–543.

After any calibration probes, re-check scene A and the scene/stomp toggle at
the top right of the header before saving.

### Value fields under the offset

A single `computer_left_click` on the value text at its `y+offset` puts the
field into edit mode with the value highlighted. `computer_double_click` at
the same aim does **not** — it lands as a plain click at the uncorrected y and
selects an empty grid slot. Use single click, then `cmd+a`, type, `return`.

### TotalMix under the offset

Buttons — Inst, AutoSet, submix mute — take clicks at the offset. The gain
knob ignores every input form tried: `left_click_drag`, stepped
down/move/up, scroll, and typed value; a double-click resets it to 0. When a
capture needs analog input gain you cannot set this way, put the same dB into
the plugin's Input Gain via `ableton-mcp` and reset it afterwards — it is
equivalent pre-nonlinearity gain. See `quad-cortex-plugin-capture`.

## Focus and monitor problems

- **An un-granted app in front blocks every click**, even when it is on the
  other monitor. `computer_open_application` on Cortex Control brings it back
  to front without asking the user.
- **Windows on the non-primary display can receive no clicks at all.** Ask for
  the app on the primary (menu-bar) monitor.
- **Cursor parked on the other monitor sends your clicks nowhere.** Move to
  any point on the primary display first; the next click then lands, with the
  usual offset. `computer_cursor_position` reporting `logical_points` on
  another monitor is the tell.
- Access grants drop when the remote-device session drops. Re-resolve and
  re-request rather than retrying clicks.
