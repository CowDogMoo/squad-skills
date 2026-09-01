# thall amp — the installed preset library

53 factory presets plus whatever is in `User/`, read straight from the files
under `~/Library/Odeholm Audio/thall amp/Presets/` (shift-click the preset
button in the plugin to open that folder). Regenerate any of this with:

```bash
python3 scripts/read_preset.py --library          # the table below
python3 scripts/read_preset.py "<preset>.afx"     # one preset in full
python3 scripts/read_preset.py --diff A.afx B.afx # what changed
```

Read the file, not the UI, when you want the preset **as its author saved
it** — with Tone Lock on, the plugin does not load a preset's tone-match or
input-gain values, so the UI and the file disagree by design. Read the live
plugin when you want to know what is **actually running**.

## The whole library at a glance

`chugHz` is Tighten Frequency, `thickn` is Pitch Thicken, `dirt` is Low Dirt.

```text
preset                                           drive     chug   chugHz     gate   thickn     dirt    locut    hicut     tone   flags
Buster Odeholm - Ashen                             70%      30%    250Hz  -50.0dB      20%       0%      off      off      Off
Buster Odeholm - Fuzz                              50%       0%    250Hz  -60.0dB      70%      68%      off      off       On   2 unsaved
Buster Odeholm - Thick Chugs                       50%      50%    250Hz  -50.0dB      30%      10%      off      off      Off
Calle Thomer - Rhythm                              61%      47%    240Hz  -30.0dB      10%       5%      off      off      Off
Calle Thomer - Thall                               57%      82%     87Hz  -30.0dB      50%      60%      off  11.4kHz      Off
Connor Sweeney - Baritone Humbucker Rhythm         59%      66%   1.0kHz  -50.0dB       8%       1%     78Hz      off       On
Connor Sweeney - Baritone P90 Rhythm               60%      64%   1.0kHz  -50.0dB      35%      11%     78Hz      off       On
Connor Sweeney - Single Coil Rhythm                60%      15%   1.0kHz  -50.0dB       8%      11%     78Hz      off       On
Connor Sweeney - Very Heavy Chugging               85%      69%   1.1kHz  -50.0dB     100%      10%     95Hz      off       On
Drewsif - Air On Marshall                          33%       0%    250Hz  -59.0dB       0%       0%     78Hz  10.7kHz       On
Drewsif - Dog Father                               22%      21%    900Hz  -59.0dB      65%      96%    104Hz   7.9kHz       On
Drewsif - Hell Yeah Brother                        60%      28%     92Hz  -31.0dB       0%       6%      off   9.3kHz       On
Drewsif - Kahney DoIt                              51%      40%   1.0kHz  -50.0dB       0%       0%    103Hz      off       On
Drewsif - MOON                                    100%       0%    743Hz  -59.0dB      95%     100%     75Hz   7.3kHz      Off
Drewsif - Pyongyang                                62%      84%   1.7kHz  -50.0dB       7%       7%    117Hz  15.5kHz      Off
Drewsif - ROMANTIC                                 37%      50%    250Hz  -50.0dB      12%       0%     86Hz      off       On
Drewsif - Rang Gang                                59%      57%    409Hz  -43.0dB      11%      76%    112Hz  12.2kHz       On
Elliot Merriman - Coil Split                       41%      42%    817Hz  -41.0dB       5%       8%      off  14.6kHz       On
Elliot Merriman - Ooey                             56%      43%   1.2kHz  -30.0dB       5%       0%     61Hz      off       On
Elliot Merriman - Sauron Chugs                     50%      60%    682Hz  -27.0dB      26%      56%     59Hz      off       On   profile@48k
Elliot Merriman - Some More Ooey                   59%      29%   1.4kHz  -30.0dB       7%      10%     63Hz  14.0kHz       On
James Carey - 808 Bass Destruction                 38%     100%     76Hz  -40.0dB       0%       0%     31Hz   5.3kHz       On
James Carey - Big Chungus                          66%      27%    898Hz  -45.0dB       6%       0%     81Hz  10.0kHz       On   profile@48k 2 unsaved
James Carey - Biting Synth Lead                    24%      19%    870Hz -100.0dB       0%      48%    138Hz   8.0kHz       On
James Carey - Lofi Octave Vocal                     1%       0%    250Hz -100.0dB      53%       7%    200Hz   2.5kHz       On
James Carey - Saturate My Square Wave              24%      19%    870Hz -100.0dB       0%      48%    115Hz   8.0kHz       On
James Morgan - The Old Way                         75%      80%    212Hz  -42.0dB      30%       5%     90Hz      off      Off   IR!
Jesse Zuretti - Concatenation                     100%       0%    250Hz  -47.0dB       4%       0%      off   8.6kHz       On   profile@48k
Jesse Zuretti - Galactus Guts                      53%      46%    250Hz  -31.0dB      48%      53%      off   8.6kHz       On   profile@48k
Jesse Zuretti - Jesseract Neck Pup                 21%       0%    250Hz  -56.0dB      48%       0%      off   8.6kHz       On   profile@48k
Jesse Zuretti - Monomythic                        100%     100%     51Hz  -23.0dB       0%       0%     97Hz   8.6kHz       On   profile@48k
Jesse Zuretti - RDS 220                           100%      79%     48Hz  -33.0dB      23%       0%     81Hz   8.6kHz       On   profile@48k
Jesse Zuretti - Special Defukt                     20%     100%     48Hz -100.0dB      11%       0%      off   8.6kHz       On   profile@48k
Jesse Zuretti - Starscream Fuzztronics            100%     100%    250Hz  -23.0dB      67%      84%     97Hz   8.6kHz       On
Lance Prenc - All Thicked Out                      42%      27%    537Hz  -35.0dB      40%      13%      off      off       On   IR!
Lance Prenc - Amp Explode                          70%      76%    175Hz  -33.0dB      39%     100%      off      off       On   IR!
Lance Prenc - Chuggy Rhythm                        45%      40%    553Hz  -33.0dB      20%       0%      off      off       On   IR!
Lance Prenc - Chuggy Thicked                       45%      40%    553Hz  -33.0dB      57%       0%      off      off       On   IR!
Lance Prenc - NuMetalcore                          35%      38%    553Hz  -33.0dB      20%      11%      off      off       On   IR!
Lance Prenc - Southern Lofi                        42%      27%    537Hz  -35.0dB      64%      13%    344Hz   1.5kHz       On   IR!
Lance Prenc - The Quads                            35%      68%    175Hz  -33.0dB      20%      60%      off      off       On   IR!
Lance Prenc - World Ender                          45%      45%    175Hz  -33.0dB      23%      83%      off      off       On   IR!
Luka Rozaka - browner                              50%     100%   2.5kHz  -30.0dB      48%     100%      off      off      Off
Luka Rozaka - downer                               47%     100%   2.5kHz  -30.0dB      41%      38%      off      off      Off
Luka Rozaka - stone56                              63%       0%     20Hz  -46.0dB      69%      61%      off      off      Off
Luka Rozaka - thall56                              47%      82%   2.5kHz  -30.0dB      50%       9%      off      off      Off
Luka Rozaka - tight chugs                          37%      31%    591Hz  -30.0dB      29%       0%      off      off      Off
Mirar - Leo                                        61%      50%   1.6kHz  -12.0dB      17%       0%      off      off      Off
Mirar - Marius                                     60%       0%   1.2kHz -100.0dB       0%      14%     60Hz   3.6kHz      Off
Simone Pietroforte - Brutal Death Thall            47%      19%   1.9kHz  -30.0dB       4%      16%     98Hz   7.3kHz       On   profile@44k
Simone Pietroforte - HC THALL                      50%      18%   1.3kHz  -43.0dB      40%       3%     70Hz  11.1kHz       On   IR! profile@44k
Simone Pietroforte - Octave Thall Doom             47%      48%   1.7kHz  -39.0dB       0%      60%     69Hz  10.1kHz       On   profile@44k
Simone Pietroforte - Southern Thall                50%      14%   1.7kHz  -40.0dB       0%      60%     50Hz   9.1kHz       On   IR! profile@44k
Jayson Smash (User)                                50%      31%    249Hz  -44.0dB       0%       0%      off      off        -   5 unsaved
```

## What the flags mean for a capture

**`IR!` — 11 presets load a cab IR that is not on this machine.** The path is
stored absolutely, and these came from other people's computers:

| Preset(s) | Missing file |
| --------- | ------------ |
| all 8 Lance Prenc | `C:\ProgramData\Odeholm Audio\Thall Amp\Presets\Factory\Lance Prenc Custom.wav` |
| James Morgan – The Old Way | `F:\CatsCab.wav` |
| Simone Pietroforte – HC THALL, Southern Thall | `/Users/simonepietroforte/Desktop/PRODUCER STUFF/IMPULSE RESPONSES/HC THALL.wav` |

They fall back to the internal cab, so what you hear is not what the author
built. Capturing one of these captures the fallback. If the preset matters,
find the IR or accept that the cab is your own.

**`profile@Nk` — 12 presets ship an embedded tone-match profile** learned
from the author's guitar, several at Amount 100% (Monomythic, RDS 220,
Special Defukt). With Tone Lock on, the plugin **does not** load them and
your own profile stays in the chain at your own Amount. That is a different
input EQ from the one the preset was voiced around, and it is baked into any
capture you make. Check the profile name in the UI before capturing one of
these.

**`unsaved`** — the file records those switch parameters with no value, so it
cannot tell you their state. Read them from the live plugin.

## Presets a Neural Capture can reproduce faithfully

Only two have no dynamic control running at all — Chug 0, Thicken 0,
Whammy 0:

- **Drewsif – Air On Marshall** (Chug 0, everything static, cab on)
- **Mirar – Marius** (Chug 0, Pitch section already off, **Cab Power off** so
  it is an amp-only capture, gate already at −100)

Everything else carries Chug, Thicken, Whammy or several at once. That is not
a reason to avoid capturing them — it is the reason to expect and record the
deficit rather than treat it as a fault. See `SKILL.md`.

Six presets use **Pitch Whammy** and cannot be captured meaningfully at all:
Kahney DoIt (+1 st), Big Chungus, RDS 220, browner, Octave Thall Doom
(−12 st), Southern Lofi (+12 st).

## Other structural oddities

- **Pitch Power already off**: Calle Thomer – Rhythm, Lance Prenc – Chuggy
  Rhythm / NuMetalcore / The Quads, Mirar – Marius. For these, the capture
  workflow's "power the pitch section off" is a no-op, and their Low Dirt is
  already inaudible if the section gates it.
- **Cab Power off**: Mirar – Marius only. Every other preset is an
  amp-and-cab preset.
- **Lo-Fi on**: James Carey – Lofi Octave Vocal only.
- Every factory file records `preset_cat` as `User` and an empty creator.
  The author's name lives in the filename, not the metadata.
- Several presets are not guitar-amp presets at all — 808 Bass Destruction,
  Biting Synth Lead, Lofi Octave Vocal, Saturate My Square Wave are for
  running other sources through the plugin.

## The two that matter here

**Mirar – Leo** is the source of the standing V4 capture. **Jesse Zuretti –
Monomythic** is the source of V1. Their factory values, and the deliberate
changes made before capturing Leo, are in `SKILL.md`.
