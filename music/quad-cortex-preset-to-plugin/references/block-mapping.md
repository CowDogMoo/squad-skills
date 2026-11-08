# QC block → plugin mapping

How Quad Cortex block values were carried into Neural DSP plugins on the
worked example, and the key names involved. Keys are verified on Archetype
Gojira X (preset `version` 1.0.1–1.0.2) and Fortin Nameless Suite X. For any
other plugin, dump its `Default.xml` with `scripts/ndsp_preset.py` and find
the equivalents; do not guess a key from these.

## General rules

| QC side | Plugin side |
| --- | --- |
| 0–10 knob | 0–1 (divide by 10) |
| dB value (EQ band, IR level) | same number in dB |
| Graphic EQ output gain | no EQ slot; add to the plugin's `outputGain` |
| Block at unity (Pitch Shifter 0 st, Wham pedal 0) | section or effect off |
| Adaptive Gate | plugin gate on, threshold by ear (not a measured value) |
| Reverb mix % | `reverbMix` 0–1; decay and cuts use other units, leave at template |
| Lane output level | `outputGain` (after the EQ output above) |
| A block the plugin lacks | the same model from another plugin, chained, everything else in it off |

A plugin's sections run in its own fixed order. If the QC grid orders
blocks differently, say which ones moved.

## Archetype Gojira X keys

Node names are the ValueTree types; scope `sectionActive` with them.

| Section (node) | Keys |
| --- | --- |
| root `appModel` | `selectedAmp` (2 = HOT, the `leadAmp*` channel; the other channels are `rhythmAmp*` and `cleanAmp*` — confirm the index by saving a preset with that amp selected), `selectedCab`, `ampCabLinkedState` |
| header (`parameters`) | `gateActive`, `gateThreshold`, `transpose`, `inputGain`, `outputGain` (factory Default 8 dB), `doublerActive`, `doublerSpread` |
| `pitchParameters` | `whammyActive`, `whammyPedal`, `whammyMode`, `whammyMix`, `octaverActive`, `octaverOct1`, `octaverOct2`, `octaverLevel` |
| `pedalParameters` | OD `odActive`/`odDist`/`odLevel`/`odTone`; `drtActive`…; `phsrActive`, `phsrRate`; `chrActive`… |
| `leadAmp` | `leadAmpGain`, `Low`, `Mid`, `High`, `Presence`, `Depth`, `Master`, `Level` (Default 0.408333, left alone ≈ QC Output 0 dB) |
| `leadEQ` | `leadEQActive`, `leadEQHpf` (Hz), `leadEQLpf` (Hz), `leadEQBand1`–`leadEQBand9` (dB) |
| `cabParameters` | `leftCabActive`, `leftCabMicLevel` (dB), `leftCabPan`, `leftCab<N>MicType`, `leftCab<N>ChosenIRFilePath` (N = 0–2), `rightCab*` mirror, `*Room*` |
| `reverb` | `reverbActive`, `reverbMix`, `reverbDecay`, `reverbLowCut`, `reverbHighCut`, `reverbShimmer` |
| `delay` | `delayActive`, `delayMix`, `delayTime`, … |

Custom IR: `selectedCab` N, `leftCab<N>MicType` 7, path on the same N. See
`preset-file-format.md` for why it should be saved from the plugin UI.

## Fortin Nameless Suite X keys (used as a pedal)

| Section (node) | Keys |
| --- | --- |
| header | `gateActive`, `transpose`, `inputGain`, `outputGain`, `doublerActive` |
| `preFXParameters` | `sectionActive`, `grindActive`, `grindBoost` (0–1 = QC Boost 0–10), `hexDriveActive`, `zuulActive` |
| `ampParameters`, `eqParameters`, `cabParameters`, `postFXParameters` | `sectionActive` (all false when used as a pedal); also `namelessEQActive`, `reverbActive`, `delayActive` |

## The 1A Graft mapping (scene A)

QC chain as read: Adaptive Gate → Pitch Shifter 0 st → Wham at pedal 0 →
Fortin Grind (Boost 4.6) → HOT amp → Graphic-9 EQ → IR "Impact Studios_IR 5"
+3 dB → Room reverb 20 %.

| QC block and value | Plugin setting | Notes |
| --- | --- | --- |
| Adaptive Gate | Nameless `gateActive` true; Gojira `gateActive` false | Gated once, at the front |
| Pitch Shifter 0 st | Gojira `transpose` 0 | Unity |
| Wham at pedal 0 | `whammyActive` false, `octaverActive` false | Unity → off |
| Fortin Grind, Boost 4.6 | Nameless `grindActive` true, `grindBoost` 0.46; amp/EQ/cab/post-FX off; in/out 0 dB | Gojira has no Grind. Gojira OD as a stand-in failed (see the worked example) |
| HOT amp: Gain 7, Low 3, Mid 5.5, High 6.5, Presence 7, Depth 3, Master 7.5, Output 0 | `selectedAmp` 2; `leadAmpGain` 0.7, `Low` 0.3, `Mid` 0.55, `High` 0.65, `Presence` 0.7, `Depth` 0.3, `Master` 0.75; `leadAmpLevel` left at Default | |
| Graphic-9: HPF 85, −4 / −3.5 / −5 / −5 / +2.5 / +3.5 / +2 / +1.5 / 0, output +2 dB | `leadEQHpf` 85, bands copied, `outputGain` 8 + 2 = 10 | Starting point. Re-fitted after measuring to +2.7 / −0.5 / −5.2 / −4.5 / +2.5 / +3 / +1.5 / +1 / 0, `outputGain` 3.4 |
| IR "Impact Studios_IR 5" +3 dB | custom IR on selected cab slot 2, `leftCabMicLevel` 3, right cab off | Loaded and saved from the plugin UI |
| Room reverb 20 % | `reverbActive` true, `reverbMix` 0.2 | Decay/cuts at Default; units differ |

Not carried over: the QC Room reverb's decay and cut values (left at
Gojira's defaults), and the Adaptive Gate's threshold (set by ear).
