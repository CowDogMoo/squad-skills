# Worked examples

Finished presets and what they measured, kept as calibration for what a good
result looks like on this rig. Read one when you want a known-good chain and
its numbers; none of it is a procedure to repeat step by step.

## 1D Thall Experimental with Mirar Leo V4, 2026-08-29 (rung 3)

Block state read from panels (scene A): Wham (byp) → Neural Capture "Thall
Mirar Leo Amp and Cab V4" → IR Loader Single (M) Impact Studios_IR 1 (byp) →
Parametric-3 (HPF 55 Q0.71, +1.5 @ 350, hi shelf −0.5 @ 2k) → Reverb Room 15%
(byp) → Multi Out.

Raw V4 measured with Volume 0 and the EQ bypassed: offset −4.4 dB; 1–12 kHz
within 0.3 dB; 120–250 −0.4; 250–500 −3.2 at coherence 0.77 (worth
correcting: +2 to 3 dB @ 350 Q1); 60–120 −5.0 at coherence 0.31 (EQ would move
the number but not the null; present in V1/V2/V4 alike); null −3.2 / −3.7.

V3, which had no notes kept, had been loaded in this preset and measured −5.8
at Volume +6 with +10–15 dB of sub and a roll-off above 2 kHz. Rejected.

## 1D Thall Experimental, 2026-08-24 (rung 3, final)

Chain: In 1 → Adaptive Gate → Pitch Shifter (bypassed) → row 3: Wham
(bypassed) → Neural Capture "Thall Monomythic Amp and Cab" (Gain 0.0, Volume
+6.0) → IR Loader (bypassed, IR kept) → Parametric-3 (band 1 Peak +3.0 dB @
90 Hz Q 1.50; band 2 Hi pass 65 Hz; band 3 flat; Output 0) → Reverb Room →
Multi Out (USB Output 3/4 enabled). Lane output volume −3.0.

Measured on one same-performance take: 250 Hz–12 kHz within 0.2 dB of the
plugin in every band; 60–120 Hz −3.1; 120–250 +2.4; QC 4.1 dB louder (Utility
on the Live QC track at −3.8 dB); coherence 0.93 / 0.94 / 0.87 at 120–250 /
250–500 / 500 Hz–1 kHz and 0.55 at 60–120; null −3.4 dB after gain match,
−4.9 dB after linear EQ. Volume +14 clipped ("crackly") — +6 is the ceiling on
this path.

How it got there, four takes at one variant each: lo shelf +3 @ 75 → peak +3 @
90 Q1.5 → peak +4 @ 90 Q3 plus HPF 50 → peak +3 @ 90 Q1.5 plus HPF 65. The
four shapes differ by only about a dB in band-mean gain across 60–120 Hz, which
is the whole spread these takes show — the bell moved the band every time, by
the amount its shape predicts (see `quad-cortex-capture-measurement`, "What EQ
moves, and what coherence tells you"). The HPF is what improved the null and the
coherence. Do not add more low-end EQ to this preset: at coherence ~0.5 it would
flatten the number without improving the match. The residual 80–100 Hz gap is a
recapture item.

## 1D Thall Experimental, 2026-08-23 (rung 2)

Reference: thall amp plugin, Monomythic preset, captured as "Thall Monomythic
Amp and Cab" — Internal Cab, Lo Cut 97 Hz, Hi Cut 8.6 kHz baked in; gate off,
pitch off, mono.

Found: In 1 → Adaptive Gate 70% → Pitch Shifter (0 st, 100% mix, ON) → row 3:
Wham (pedal 0%, ON) → Neural Capture (Amp and Cab, all 0.0) → Reverb Room 15%
→ IR Loader (Impact Studios_IR 1, +3 dB, bypassed) → Graphic-9 EQ
(−3/−2/−2/−2/+1.5/0/0/−2/−2, HPF 97, Output +4, ON) → Multi Out.

Did: bypassed both pitch blocks; moved the IR Loader to directly after the
capture with the EQ after that, so reverb is last; bypassed the EQ; set
capture Volume +4.0 with Gain left at 0.0; saved, toast confirmed.

Rung reached: 2. No listening or measurement was done. The first report of
this job said "optimized for the amp sound", which is rung-3 language on
rung-2 work — the guardrail at the top of the skill exists because of it.
