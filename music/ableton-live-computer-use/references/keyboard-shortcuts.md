# Live 12 keyboard shortcuts (macOS)

Keys beat clicks: a shortcut lands the same way whatever the window size, and
it leaves no ambiguity about which widget took the event. Every row below is
copied verbatim from the manual's shortcut tables (chapter 41); the full list
of 290-odd rows is one command away:

```bash
python3 scripts/live_manual.py shortcuts            # everything, grouped
python3 scripts/live_manual.py shortcuts "warp"     # filter by action or key
python3 scripts/live_manual.py show 41 --deep       # the whole chapter
```

Windows equivalents: swap Cmd for Ctrl and Option for Alt, or pass
`--windows`.

Two Live-wide rules shape the tables:

- **Tab** toggles Session/Arrangement only while "Use Tab Key to Move Focus"
  is off (Navigate menu, or Display & Input settings). With it on, Tab walks
  focus between controls and you switch views with Option+1 / Option+2.
- Single-letter keys (A, B, Q, S, C, 0, F, H, W, Z, X ...) are momentary
  latching in Live 12: a short tap toggles, a long hold latches only while
  held. Tap, do not hold, unless you want the momentary behavior.

## Views and focus

| Action | Mac |
| --- | --- |
| Toggle Session/Arrangement View | Tab |
| Toggle Between Device/Clip View | Shift+Tab or F12 |
| Hide/Show Browser | Cmd+Option+B or Cmd+Option+5 |
| Hide/Show Clip View | Cmd+Option+3 |
| Hide/Show Device View | Cmd+Option+4 |
| Hide/Show Mixer | Cmd+Option+M |
| Hide/Show In/Out | Cmd+Option+I |
| Hide/Show Sends | Cmd+Option+S |
| Hide/Show Overview | Cmd+Option+O |
| Hide/Show Info View | Shift+? |
| Hide/Show the Groove Pool | Cmd+Option+6 |
| Hide/Show the Learn View | Cmd+Option+7 |
| Toggle Full Screen Mode | Ctrl+Cmd+F |
| Toggle Second Window | Cmd+Shift+W |
| Open the Settings | Cmd+, |
| Close Window/Dialog | Esc |
| Move Focus to the Control Bar | Option+0 |
| Move Focus to the Session View | Option+1 |
| Move Focus to the Arrangement View | Option+2 |
| Move Focus to the Clip View | Option+3 |
| Move Focus to the Device View | Option+4 |
| Move Focus to the Browser | Option+5 |
| Move Focus to the Clip Panels | Option+Shift+P |
| Move to Next Focusable Control | Tab |
| Move to Previous Focusable Control | Shift+Tab |
| Move to Next Neighbor of Current Control | Option+Tab |
| Move to Previous Neighbor of Current Control | Option+Shift+Tab |

## Sets and the program

| Action | Mac |
| --- | --- |
| New Live Set | Cmd+N |
| Open Live Set | Cmd+O |
| Save Live Set | Cmd+S |
| Save Live Set As… | Cmd+Shift+S |
| Export Audio/Video | Cmd+Shift+R |
| Export MIDI File | Cmd+Shift+E |
| Quit Live | Cmd+Q |
| Hide Live | Cmd+H |

## Transport and recording

| Action | Mac |
| --- | --- |
| Play from Start Marker/Stop | Space |
| Continue Play from Stop Point | Shift+Space |
| Play Arrangement View Selection | Space |
| Stop Playback at End of Selection | Option+Space |
| Play from Insert Marker in Selected Clip | Option+Space |
| Move Insert Marker to Playhead Position | Cmd+Shift+Space |
| Move Insert Marker to Beginning | Home or Function left arrow key |
| Record | F9 |
| Arm Recording in Arrangement View | Shift+F9 |
| Record to Session View | Cmd+Shift+F9 |
| Back to Arrangement | F10 |
| Toggle Metronome | O |
| Activate/Deactivate Track 1…8 | F1…F8 |
| Turn Audio Engine On/Off | Cmd+Option+Shift+E |

## Editing and values

| Action | Mac |
| --- | --- |
| Cut | Cmd+X |
| Copy | Cmd+C |
| Paste | Cmd+V |
| Duplicate | Cmd+D |
| Delete | Delete |
| Undo | Cmd+Z |
| Redo | Cmd+Shift+Z |
| Rename | Cmd+R |
| Select All | Cmd+A |
| Move to Next Track/Scene When Renaming | Tab |
| Ignore Grid Quantization When Dragging | Cmd |
| Decrement/Increment | up and down arrow keys |
| Decrement/Increment in Octaves or Fine Adjustments | Shift up and down arrow keys |
| Finer Resolution When Dragging | Shift |
| Return to Default | Delete |
| Type In Value | 0…9 |
| Go to Next Field (Bar/Beat/16th) | .+, |
| Confirm Value Entry | Enter |
| Cancel Value Entry | Esc |

## Tracks

| Action | Mac |
| --- | --- |
| Insert Audio Track | Cmd+T |
| Insert MIDI Track | Cmd+Shift+T |
| Insert Return Track | Cmd+Option+T |
| Rename Selected Track | Cmd+R |
| Group Selected Tracks | Cmd+G |
| Ungroup Tracks | Cmd+Shift+G |
| Collapse/Expand Grouped Tracks | U |
| Hide/Show Return Tracks | Cmd+Option+R |
| Arm Selected Tracks | C |
| Solo Selected Tracks | S |
| Deactivate Selected Track | 0 |
| Freeze/Unfreeze Tracks | Cmd+Option+Shift+F |
| Delete Track from Track Title Bar | Delete |
| Add Device from Browser | Enter |
| Bounce to New Track | Cmd+B |
| Paste Bounced Audio | Cmd+Option+V |

## Session View

| Action | Mac |
| --- | --- |
| Launch Selected Clip/Slot | Enter |
| Select Neighboring Clip/Slot | arrow keys |
| Stop Clips in Track with Slot Selection | Cmd+Enter |
| Insert MIDI clip | Cmd+Shift+M |
| Insert Scene | Cmd+I |
| Insert Captured Scene | Cmd+Shift+I |
| Add/Remove Stop Button | Cmd+E |
| Deactivate Selected Clip | 0 |
| Move Selected Track Left/Right | Cmd left and right arrow keys |
| Toggle Follow Actions for Selected Clips | Shift+Enter |
| Jump to Highlighted Track Title Bar | Esc |

## Arrangement View

| Action | Mac |
| --- | --- |
| Split Clip at Selection | Cmd+E |
| Consolidate Selection into Clip | Cmd+J |
| Crop Selected Clips | Cmd+Shift+J |
| Resize Clip When Insert Marker is at Clip Edge | Enter left and right arrow keys |
| Create Fade/Crossfade | Cmd+Option+F |
| Delete Fades/Crossfades in Selected Clip(s) | Cmd+Option+Delete |
| Toggle Loop Brace | Cmd+L |
| Select Loop Brace Contents | Cmd+Shift+L |
| Insert Silence | Cmd+I |
| Cut Time | Cmd+Shift+X |
| Copy Time | Cmd+Shift+C |
| Paste Time | Cmd+Shift+V |
| Duplicate Time | Cmd+Shift+D |
| Delete Time | Cmd+Shift+Delete |
| Fold/Unfold Selected Tracks | U or left and right arrow keys |
| Unfold All Tracks | Option+U |
| Optimize Arrangement Height | H |
| Optimize Arrangement Width | W |
| Zoom to Arrangement Time Selection | Z |
| Zoom Back from Arrangement Time Selection | X |
| Deactivate Selection | 0 |
| Nudge Selection Left/Right | right and left arrow keys |
| Reverse Audio Clip Selection | R |
| Scroll Display to Follow Playback | Option+Shift+F |
| Move Focus to Mixer | Option+Shift+M |
| Set Start Marker | Cmd+F9 |
| Set Loop Brace Start | Cmd+F10 |
| Set Loop Brace End | Cmd+F11 |
| Set End Marker | Cmd+F12 |
| Show Take Lanes | Cmd+Option+U |
| Audition Selected Take Lane | T |

## Grid, quantization, automation, zoom

| Action | Mac |
| --- | --- |
| Toggle Draw Mode (Pitch Lock Off) | B |
| Narrow Grid | Cmd+1 |
| Widen Grid | Cmd+2 |
| Triplet Grid | Cmd+3 |
| Snap to Grid | Cmd+4 |
| Fixed/Zoom-Adaptive Grid | Cmd+5 |
| Sixteenth-Note Quantization | Cmd+6 |
| Eighth-Note Quantization | Cmd+7 |
| Quarter-Note Quantization | Cmd+8 |
| 1-Bar Quantization | Cmd+9 |
| Quantization Off | Cmd+0 |
| Toggle Automation Mode | A |
| Delete Selected Breakpoint Envelope | Cmd+Delete |
| Zoom In Window | Cmd++ |
| Zoom Out Window | Cmd+- |
| Zoom In Time Ruler | + |
| Zoom Out Time Ruler | - |

## Clip View

| Action | Mac |
| --- | --- |
| Switch Between Sample/Envelopes Tabs | Option+Tab |
| Switch to Sample/Notes Tab | Option+Shift+1 |
| Switch to Envelopes Tab | Option+Shift+2 |
| Switch to MPE Tab | Option+Shift+3 |
| Quantize | Cmd+U |
| Quantize Settings… | Cmd+Shift+U |
| Insert Warp Marker | Cmd+I |
| Delete Warp Marker | Delete |
| Move Selected Warp Marker | right and left arrow keys |
| Select Warp Marker | Cmd right and left arrow keys |
| Insert Transient | Cmd+Shift+I |
| Zoom to Clip Selection | Z |
| Zoom Back from Clip Selection | X |
| Fit Content to View Width | W |
| Fit Content to View Height | H |
| Select All Notes | Cmd+A |
| Join Notes | Cmd+J |
| Fit Notes to Time Range | Cmd+Option+J |
| Adjust Note Selection Velocity | Cmd up and down arrow keys |
| Adjust Note Selection Chance | Cmd+Option up and down arrow keys |
| Toggle Full-Size Clip View | Cmd+Option+E |
| Invert Note Selection | Cmd+Shift+A |
| Highlight Scale | K |

## Devices and plug-ins

| Action | Mac |
| --- | --- |
| Toggle Hot-Swap Mode | Q |
| Load Selected Device from Browser | Enter |
| Group Devices | Cmd+G |
| Ungroup Devices | Cmd+Shift+G |
| Hide/Show Open Plug-In Windows | Cmd+Option+P |
| Compare A/B: Switch Device State | P |
| Reset Parameter Value | Delete or double-click |
| Toggle Drum Rack/Last Selected Pad | D |

## Browser

| Action | Mac |
| --- | --- |
| Search in Browser | Cmd+F |
| Jump to Search Results | down arrow key or Enter |
| Scroll Down/Up | up and down arrow keys |
| Close/Open Folders | right and left arrow keys |
| Load Selected Item from Browser | Enter |
| Preview Selected File | Shift+Enter or right arrow key |
| Browser History Back | Cmd+[ |
| Browser History Forward | Cmd+] |
| Hide/Show Filter View | Cmd+Option+G |
| Show Similar Files Using Similarity Search | Cmd+Shift+F |

## Mapping and the computer keyboard

| Action | Mac |
| --- | --- |
| Toggle MIDI Map Mode | Cmd+M |
| Toggle Key Map Mode | Cmd+K |
| Computer MIDI Keyboard | M |
| Adjust Computer MIDI Keyboard Octave Range Up/Down | X and Z keys |
