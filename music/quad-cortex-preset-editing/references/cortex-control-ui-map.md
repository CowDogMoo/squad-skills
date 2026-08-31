# Cortex Control coordinate maps (v4.0.0)

Rough orientation only — the window moves and resizes between sessions.
Always take a fresh 1.0-scale screenshot and read positions from it rather
than trusting either set below.

## Window centered, 1456x819 screenshot frame

- Preset header y~99: back/forward arrows, name, disk icon (~x 861), `⋮`
  menu (~x 896), scenes A-H.
- Grid rows at y~177 / 275 / 372 / 470; row-1 input tile ~x 481; slot centers
  ~x 560, 647, 734, 821, 908, 995, 1083, 1170; right tiles ~x 1249.
- Block panel below the grid: title y~547, power button ~x 1254 same y,
  RESET (EQ) left of it; first row of values y~657.

## Window at upper left (as observed 2026-08-24, ~x 177-912, y 18-555)

- Header y~77, disk icon ~x 633.
- Rows y~129/194/259/324; row-3 slots ~x 432, 548, 606, 664, 722; out tile
  ~x 890.
- Panel title y~376, power ~x 895, RESET ~x 864, value text y~449 (capture)
  / y~523 (EQ).

## UI facts (v4.0.0)

- Layout: preset header (back/forward arrows, name, disk icon, `⋮` menu,
  scenes A–H) above the 4-row grid; block panel below the grid, its title at
  the top with the power button top-right and RESET (EQ) left of that.
- Selecting a block opens the matching category list on the left (for example
  every reverb type), which is how you learn what the block really is.
- The `x` at a block's top-right corner deletes it. Avoid it unless deleting.
- Value fields accept typed numbers after a double-click; knobs ignore scroll.
- Clicking the Out tile at the end of a row opens the OUTPUT list on the left
  (Multiple Outputs / Output 1/2 / Output 3/4 / USB Output 3/4 and so on); the
  panel below shows the lane output control — Volume, Pan, Mute, Solo, meter.
- Panel state glyphs: bright panel plus a plain power glyph = active; dimmed
  panel plus a strikethrough glyph = bypassed. A block's filled look on the
  grid is selection, not state.
