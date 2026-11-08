# Neural DSP preset and plugin-state formats

Everything the bundled scripts assume about the files they read and write.

## Where presets live

`/Library/Audio/Presets/Neural DSP/<Plugin>/`

- `Default.xml` — the factory template, owned by root. Read it; never write it.
- `User/*.xml` — the player's presets, shared by the plugin (in any DAW) and
  the standalone app. A new file here shows up in the plugin's preset
  browser.
- Artist and factory folders beside `User/` are the plugin's own; leave them.

## Preset file: JUCE ValueTree binary

Despite the `.xml` extension a preset is a JUCE `ValueTree` written with
`writeToStream`:

```text
tree  := typeName \0  CompressedInt numProps  prop*  CompressedInt numChildren  tree*
prop  := name \0  var
var   := CompressedInt numBytes  marker  payload
marker: 1 int32 | 2 true | 3 false | 4 double | 5 string (\0-terminated) | 6 int64
CompressedInt := one count byte n (high bit = negative), then n little-endian bytes
```

The root is the plugin's type (`gojira-X`, `nameless-X`) with `version`,
`name`, `isFavorite`, and one child `appModel` holding everything else.
Parameter values are stored as **strings** (`"0.7"`, `"true"`), so a key
is set by writing text; `write_preset.py` converts to whatever type the
template holds. `ndsp_preset.load` re-serializes every file it reads and
refuses one that does not reproduce byte for byte.

A preset saved from the plugin UI after a script edit keeps the script's
values and may bump `version`; that is expected.

## Custom IR on the selected cab slot

Gojira's cab has three mic slots per side (`leftCab0`–`leftCab2`). A custom
IR is used only on the slot `selectedCab` points at:

- `selectedCab` = N
- `leftCab<N>MicType` = 7 (the custom-IR entry after the stock mics)
- `leftCab<N>ChosenIRFilePath` = absolute path to the `.wav`
- the other slots keep their stock mic types and empty paths

Hand-written IR fields did not always load in the plugin. Loading the IR in
the plugin window on the selected slot and pressing SAVE lets the plugin
write those fields itself, and it loaded reliably after that. Ordinary value
edits (EQ, output, amp knobs) load fine from a script, before or after.
`render_chain.py` reads the state back after a settle delay, which catches an
IR path the plugin did not take.

The path is absolute, so moving the IR breaks the preset silently.
`repoint_ir.py` rewrites the prefix in place (keeping `.pre-irmove`) and
checks the new path exists; on the worked example a re-render after the move
was bit-identical. A DAW set that already holds the plugin keeps its own copy
of the state, including the old path, until the preset is reloaded there, so
keep the old file until every set using it has reloaded the preset.

## VST3 plugin state (what the renderer edits)

`pedalboard` exposes a loaded VST3's state as `plugin.raw_state`. For JUCE
plugins:

```text
"VC2!" + uint32 LE size + XML:
  <VST3PluginState><IComponent>N.<JUCE base64></IComponent>...</VST3PluginState>
+ verbatim tail (JUCEPrivateData)
```

The IComponent text is a JUCE `MemoryBlock` in JUCE's own base64: byte count,
a dot, then 6-bit groups packed least-significant-bit first over the
alphabet `.ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+`.
Decoded, a Neural DSP plugin's component state is again `"VC2!"` + size + an
`<appModel>` XML document followed by a verbatim tail. That XML has the same
node tree as the preset file's `appModel`, with values as attributes, so
`render_chain.py` copies each preset prop onto the matching attribute by
node path, re-encodes, and assigns `raw_state`. `juce_state.py` is the codec.
