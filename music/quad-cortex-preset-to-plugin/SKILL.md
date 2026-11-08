---
name: quad-cortex-preset-to-plugin
description: Port a Quad Cortex preset into a plugin chain in the DAW and prove the match - the reverse of quad-cortex-plugin-capture. Maps QC block values to plugin settings and handles blocks that do not carry over (e.g. the Fortin Grind chained in from Fortin Nameless Suite X ahead of Archetype Gojira X), writes Neural DSP preset files directly (custom-IR slot quirk included), re-amps the DI offline through the chain without opening plugin windows, scores it against the QC with quad-cortex-capture-measurement's analyzer, fits EQ, and re-checks on a second take. Trigger on "match my Quad tone in the plugin", "make Gojira sound like my QC preset", "port this Quad Cortex preset to Neural DSP", "align the amp sims with the quad", "re-amp the DI offline", or any request to rebuild a QC preset as plugins. Do NOT use for capturing a plugin into the QC (quad-cortex-plugin-capture), measuring a capture against its plugin (quad-cortex-capture-measurement), or editing the QC preset grid (quad-cortex-preset-editing).
---

# Quad Cortex preset to plugin tone match

Rebuild a Quad Cortex preset as a chain of amp-sim plugins so guitars can be
recorded in the DAW with the tone the player already uses on the Quad, then
say with numbers how close it is. The other QC skills go plugin → Quad; this
one goes Quad → plugin.

Rig: Quad Cortex over USB, an audio interface for monitoring, Ableton Live,
Neural DSP plugins (VST3) on macOS. Worked on Archetype Gojira X and Fortin
Nameless Suite X; the file format and render path are shared by the Neural
DSP plugin family, but the key names below are only verified for those two.

Measurement method, thresholds, and the claim ladder are owned by
`quad-cortex-capture-measurement`. Read its "Recording the take", "Reading
the numbers", and "What EQ moves" sections before step 5; this skill does
not restate them.

## Workflow

1. Read the QC preset block by block, scene by scene, without changing it.
2. Map every block to a plugin setting, or record why it does not carry over.
3. Write the plugin presets with `scripts/write_preset.py`.
4. Record one take that holds the DI and the QC's wet signal together.
5. Render the DI through the chain offline with `scripts/render_chain.py`.
6. Score the render against the QC with the measurement skill's `analyze.py`.
7. Fit what is left with EQ and output level, one render per variant.
8. Re-check on a second take without changing the fitted values.
9. Check the chain is cheap enough to track through (`scripts/chain_cost.py`).
10. Report the claim-ladder rung reached and the caveats, never more.

## Guardrails

- **Reading the Quad is yours; changing it is not.** Read block values in
  Cortex Control (screen control is covered by `quad-cortex-preset-editing`)
  or ask the player to read them. The QC preset is the reference: do not
  "fix" it to make the plugins easier to match.
- **Never overwrite a preset the player uses.** Write new names into the
  User folder. `write_preset.py` refuses to overwrite without `--force`, and
  keeps `OUT.bak` when forced; `repoint_ir.py` keeps `.pre-irmove`. Fit EQ
  on scratch copies outside the User folder and write the winner once.
- **A stand-in is not the block.** When the amp sim lacks a QC block, find
  the same model in another plugin and chain it. Do not substitute a
  different pedal and call the result matched — on the worked example the
  Gojira OD as a Fortin Grind stand-in matched level and broad EQ and still
  missed the drive badly (ESR 0.68–0.85, coherence ≤ 0.80 in every band, no
  OD setting in an 8-point sweep better than ESR 0.68).
- **Plugin windows stay closed** unless a step needs one (loading a custom
  IR, below). The render reads and writes state headless.
- **Rung-3 words need rung-3 evidence.** "Matches", "within N dB", "nulls to
  −X dB" only after step 6, and "matches across takes" only after step 8.

## 1. Read the QC preset

Write down, for the scene the player uses, every block in signal order with
its model, bypass state, and every value: input gate, pitch blocks, drives,
amp (all knobs, including Output), EQ (every band, HPF/LPF, output), IR
name and level, cab mic if the cab is a stock one, reverb/delay mix and
times, lane output level. Note the scene. Blocks at unity (a Pitch Shifter
at 0 st, a Wham at pedal 0) are recorded as unity, not skipped silently.

## 2. Map blocks to plugin settings

Rules that held on the worked example (full key map and the 1A Graft table:
`references/block-mapping.md`):

- Pick the plugin whose amp is the same model as the QC amp block, then the
  amp channel inside it (Gojira `selectedAmp` 2 = the HOT amp, keys
  `leadAmp*`).
- QC 0–10 knobs → plugin 0–1 (`7.5` → `0.75`). dB values copy as dB.
- QC Graphic-9 bands copy one for one into Gojira's 9-band EQ (`leadEQBand1`
  … `leadEQBand9`, `leadEQHpf`, `leadEQLpf`). The QC EQ's output gain has no
  EQ slot in Gojira: add it to `outputGain` on top of the template's value.
- Unity blocks → off in the plugin. The QC's input gate → the plugin gate
  (threshold by ear; it is not a measured value).
- A QC block the amp sim does not have → the same model from another plugin,
  chained in front, with every other section of that plugin off and its
  in/out gain at 0 dB. Fortin Grind → Fortin Nameless Suite X with only the
  gate and the Grind on; the chain's gate then lives in Nameless and the
  Gojira gate goes off, so the signal is gated once.
- Reverb: the mix percentage carries (`reverbMix` 0.2 for 20 %); decay and
  cuts use different units in Gojira (normalized, not seconds/Hz), so leave
  them at the template and say so.
- A custom IR goes on the **selected** cab slot only (next section).

Anything that does not map — a model no plugin has, a parameter with no
counterpart — goes in the report as "not carried over", with the plugin
setting used instead.

## 3. Write the presets

Neural DSP preset `.xml` files are JUCE ValueTree **binary**, not XML. They
live in `/Library/Audio/Presets/Neural DSP/<Plugin>/User/` and are shared by
the plugin and the standalone app; the factory template is
`/Library/Audio/Presets/Neural DSP/<Plugin>/Default.xml`. Format details and
the plugin-state format the renderer uses: `references/preset-file-format.md`.

```bash
S=<this skill>/scripts
python3 -I $S/ndsp_preset.py "<preset>.xml" | rg leadEQ     # read any preset
python3 -I $S/write_preset.py "<Plugin>/Default.xml" "<Plugin>/User/<New name>.xml" \
  --spec references/specs/<spec>.json [--set key=value ...]
```

Keys are `prop` or `prop@node` (`sectionActive` exists in every section, so
`sectionActive@pedalParameters`). The script refuses unknown keys, loads the
written file back and checks every value. The two bundled specs build the
worked example's final chain from the factory defaults. The Nameless spec
reproduces the saved "Graft Grind" preset exactly. The Gojira spec matches
the saved "Graft with Nameless Grind" except the custom IR
(`leftCab2MicType`, `leftCab2ChosenIRFilePath`) and the knobs of the OD,
which is off; until the IR is loaded and saved in the plugin (or passed
with `--set`), it renders the stock cab mic, not the IR.

**Custom IR quirk.** A custom IR is honoured only on the selected cab slot:
`selectedCab` N, `leftCab<N>MicType` 7 (the custom-IR entry after the stock
mics), `leftCab<N>ChosenIRFilePath` the absolute `.wav` path, the other
slots left alone. Hand-written IR fields did not always load. The reliable
route: write everything else with the script, open the plugin once, load the
IR on the selected slot, press **SAVE** so the plugin writes the IR fields
itself. Plain value edits (EQ, output, knobs) load fine from the script,
before or after that save. If the IR file moves later (out of Downloads,
say), `repoint_ir.py PRESET OLD_PREFIX NEW_PREFIX` rewrites the path in
place and checks the new path exists; re-render once and confirm the output
is bit-identical.

## 4. Record the reference take

Use `quad-cortex-capture-measurement`'s one-cable method: guitar → QC
Input 1, Live's audio **input** device = Quad Cortex, output device stays on
the interface. One take records QC USB channel 1 (Dry Input 1, the DI, pre
grid) and channels 3/4 (Wet Signal L/R) together, sample-locked. Two
facts from this work, kept in that skill's pre-flight: the QC is a 48 kHz
device, so Live must run at 48 kHz to use it as input; and the Wet channels
are silent until the lane's Out tile is Multi Out with USB Output 3/4 on.

For a measurement take, bypass time-based effects on the QC (reverb, delay)
and leave them off in the plugin render too; put them back after. The worked
example kept a 20 % room reverb on both sides, and that is one of its
caveats. Play 20–30 s continuously: chugs, single notes, one ringing chord.

## 5. Render the DI offline

```bash
uv run --with pedalboard --with soundfile --with numpy python -I $S/render_chain.py \
  "<DI>.wav" "<out>.wav" \
  "/Library/Audio/Plug-Ins/VST3/Fortin Nameless Suite X.vst3=<grind preset>.xml" \
  "/Library/Audio/Plug-Ins/VST3/Archetype Gojira X.vst3=<gojira preset>.xml"
```

Each plugin loads headless (the plugin must be installed and licensed on
this machine), the preset values are applied onto the plugin's own state by
node path, the script waits 3 s for file loads such as an IR, then reads
the state back and prints every value that did not take. Read that line:
zero mismatches, or a reason for each. A mono DI is fed as two identical
channels, as Live feeds a mono track into a stereo plugin. The render is a
32-bit float wav, so a hot `outputGain` does not clip the file.

Validated once against Live: the offline render and Live's own re-amp of the
same DI through the same preset nulled to −20.5 dB, ESR 0.009. So compare
settings offline, and use Live only for the final listen and for tracking.

## 6. Score against the QC

Run the measurement skill's analyzer with the render in the plugin slot:

```bash
uv run --with numpy --with scipy --with soundfile --with pyloudnorm --with matplotlib \
  python -I <quad-cortex-capture-measurement>/scripts/analyze.py \
  "<DI>.wav" "<render>.wav" "<QC wet>.wav" --out-dir <dir> --label "<what is compared>"
```

Deltas are QC − plugin. Read them against that skill's thresholds: bands
within ±0.5 dB from 250 Hz up = matched; coherence ~0.9 is normal and < 0.6
in the body means the chain is wrong (drive, not EQ); ESR < 0.05 good, ~0.1
borderline, > 0.2 wrong. Low coherence with small deltas means the
nonlinear part (a drive, the amp gain, a missing block) differs, and no EQ
will fix it — go back to step 2.

## 7. Fit EQ and level

Only once coherence says the drive is right. One variable per render, all
renders from the same DI:

```bash
python3 -I $S/write_preset.py "<gojira preset>.xml" "<scratch>/v1.xml" \
  --set leadEQBand1=2.7 --set leadEQBand3=-5.2
```

then render and analyze `v1.xml`. Predict each move with the band-mean gain
rule in `quad-cortex-capture-measurement` ("What EQ moves") rather than by
the band's peak gain. Level last, with `outputGain`. Write the winning
values into a new User preset once.

## 8. Re-check on a second take

The values from step 7 were fitted to one performance. Record a second take
(different playing, same rig and levels), render it with the fitted presets
unchanged, analyze. If the band deltas hold within the cross-take noise the
measurement skill gives (about ±0.8 dB around 250–500 Hz), the fit is the
chain, not that take. If not, report both takes and fit to neither.

## 9. Check the cost

```bash
uv run --with pedalboard --with soundfile --with numpy python -I $S/chain_cost.py \
  "<DI>.wav" "<plugin>.vst3=<preset>.xml" [...]
```

Reports average load as a share of one core, the worst block against its
real-time budget, and each plugin's reported latency. Worked example at
48 kHz / 128: Gojira alone 4.8 % of a core and 42 samples, Nameless
Grind-only 1.6 % and 57 samples, the chain 6.2 % and 99 samples (2.1 ms).
The worst-block figure on a short file includes the first block's warm-up,
so read the average and the latency.

## 10. Report

State the rung from the measurement skill's claim ladder:

- **Configured** — presets written and load in the plugin.
- **Structurally faithful** — every QC block is mapped or listed as not
  carried over, and nothing is in the chain the QC preset lacks.
- **Measured** — steps 5–6 done; quote xcorr, loudness offset, per-band
  deltas, per-band coherence, null depth, ESR. "Matches across takes" only
  after step 8.

Then the caveats that apply, each in one line. The worked example reached
**measured, on one take**, with these open: one take only; reverb on both
sides; EQ fitted on the same take it was scored on; top-band coherence
lowest (0.68 at 8–12 kHz); nobody had listened A/B yet. Drive and feel are
judged by ear, by the player, through the actual monitoring path.

If tracking will go through the interface's instrument input rather than the
QC's dry USB channel, say that the input path changes how hard the chain is
driven and gain staging must be re-checked (see the measurement skill).

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `write_preset.py`: keys not found | Typo, a key the plugin version lacks, or an unscoped `sectionActive` | Dump the template with `ndsp_preset.py` piped through `rg`; scope as `key@node` |
| Render ignores the custom IR | IR fields hand-written, or set on a slot that is not `selectedCab` | Load the IR in the plugin UI on the selected slot and press SAVE; re-render |
| Read-back mismatch `'1'` vs `'1.0'` | Number formatting | Not counted; nothing to fix |
| Coherence < 0.8 everywhere, deltas small | Drive stage differs (a stand-in pedal, wrong amp gain) | Back to step 2; EQ cannot fix it |
| QC wet file silent | Wet follows the preset's output routing | Out tile → Multi Out, USB Output 3/4 on, save (measurement skill) |
| Live refuses the Quad as input | Live is not at 48 kHz | Set 48 kHz; the QC has no other rate |
| Render and Live re-amp disagree | Different preset state in Live, or Live's input feeding the wrong channel | Reload the preset in Live; check the track input is QC channel 1, not 3/4 |

## Reference files

- `references/block-mapping.md` — QC block → Gojira / Nameless keys, the
  1A Graft mapping table, and what did not carry over.
- `references/preset-file-format.md` — the ValueTree binary layout, where
  presets live, the custom-IR slot rule, and the VST3 state format
  `render_chain.py` edits.
- `references/worked-example-1a-graft.md` — the full run: the OD stand-in
  that failed, the Nameless Grind chain that worked, every number, and the
  open caveats.
- `references/specs/` — `write_preset.py` specs for the worked example's
  final chain (Nameless "Graft Grind", Gojira "Graft with Nameless Grind").
- `scripts/ndsp_preset.py` — read, dump, and round-trip-verify presets;
  library for the others.
- `scripts/write_preset.py` — template + spec/`--set` → new preset, with
  read-back.
- `scripts/render_chain.py` — offline re-amp through a preset chain, with
  state read-back.
- `scripts/juce_state.py` — JUCE VST3 state codec used by the renderer.
- `scripts/repoint_ir.py` — move a preset's IR paths, with backup and check.
- `scripts/chain_cost.py` — CPU and latency of a chain.
