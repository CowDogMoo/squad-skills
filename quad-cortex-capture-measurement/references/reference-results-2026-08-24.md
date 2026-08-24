# Reference results — 2026-08-24, "Thall Monomythic Amp and Cab"

Calibration baseline: what a finished, matched high-gain capture preset
measured on Jayson's rig. Compare new runs against these numbers to judge
"is this normal" — the coherence profile and null depths especially.

Setup: "Thall Monomythic Amp and Cab" capture vs the Raw Dawg thall amp
plugin (cab ON), same performance, one-pass QC-USB method, one take per
preset variant. Four takes, one post-capture EQ variant each:

| take  | post-capture EQ                       | 60–120 | 120–250 | ≥250 Hz | coh 120–500 | null gain / lin-EQ |
|-------|---------------------------------------|--------|---------|---------|-------------|--------------------|
| 13:07 | lo shelf +3 @ 75 Hz                   | −3.4   | +2.5    | ≤0.5 dB | 0.90        | −1.5 / −2.3 dB     |
| 13:24 | peak +3 @ 90 Hz Q1.5                  | −2.3   | +2.0    | ≤0.5    | 0.89        | −1.4 / −3.8        |
| 13:31 | peak +4 @ 90 Q3 + HPF 50 Hz           | −2.5   | +1.9    | ≤0.6    | 0.90        | −2.6 / −3.8        |
| 15:07 | peak +3 @ 90 Q1.5 + HPF 65 Hz (final) | −3.1   | +2.4    | ≤0.2    | 0.93        | −3.4 / −4.9        |

Final (15:07) detail: 250 Hz–12 kHz within 0.2 dB of the plugin in every
band; coherence 0.93 / 0.94 / 0.87 at 120–250 / 250–500 / 500–1k, 0.55 at
60–120. QC ran +3.7 to +4.1 dB louder than the plugin with capture Volume
+6 and lane volume −3; the Utility on the Live QC track is −3.8 dB.
Polarity inverted on every take. Capture Volume +14 clipped ("crackly") —
+6 is the ceiling on this path.

The take sequence is the EQ-vs-coherence lesson in data: the 80–100 Hz
deficit never moved more than ~1 dB across three bell shapes because
coherence there is ~0.5; the HPF (below the plugin's own 65 Hz low cut) is
what improved the null and lifted coherence in every band. The residual
80–100 Hz gap is a recapture item (try Chug at 0), not an EQ item.
