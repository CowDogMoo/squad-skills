# Why cross-take plugin comparison does not work

Evidence behind the rule that only same-performance QC−plugin deltas are
trustworthy. Measured 2026-08-30 against a control set of four plugin
recordings all made at the same setting.

| Statistic tried | Spread across same-reference takes |
| --------------- | ---------------------------------- |
| Normalised band levels below 500 Hz | up to **2.13 dB** |
| DI-relative transfer (plugin/DI per band) | **3.38 dB** — worse, because the amp is strongly level-dependent, so playing intensity changes the effective transfer |
| Low/mid energy ratio over time | spans **4.65–7.59 dB** |

Three attempts to build a statistic that could prove *from the audio* which
plugin setting a take used all failed on this. Absolute plugin spectra are
not trustworthy across takes better than about 2–3 dB.

None of this affects the QC−plugin deltas the skill reports: those compare
two signals from the same performance, so common-mode playing variation
cancels. That is the entire reason for the one-pass method.

Single-take band deltas also carry roughly ±0.8 dB of take-content variance
around 250–500 Hz. Treat a change smaller than that, between takes of the
same configuration, as noise rather than a result.
