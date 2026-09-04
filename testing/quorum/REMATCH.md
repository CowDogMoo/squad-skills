# Panel rematch protocol (staged, not yet run)

The 2026-09-04 measurements shelved multi-seat panels: on 8 seeded fixtures a
single briefed skeptic hit 0.00 false-complete / 0.00 false-incomplete at
$0.40/gate, a personality panel matched it in 95.83% ballot lockstep at 2.41x,
and a jurisdiction panel wrongly held 100% of genuinely complete work. Panels
get a rematch only under this protocol — its whole point is that the bar is
chosen before the data exists.

## Preconditions (all required before any run)

1. **A fixture set that separates.** Build fixtures hard enough that the
   single-skeptic baseline demonstrably false-completes (> 0.20 measured in a
   calibration pass). The 2026-09-04 null was partly a ceiling effect; a
   rematch on easy fixtures proves nothing either way.
2. **Genuinely different seat families.** At least one panel arm uses a
   second model family (locally: gpt-oss-120b / glm-4.7-flash via the
   openai-compat boxes; gemini if its auth ever works here). Same-model
   personas are one voter sampled N times — measured twice.
3. **The two fixes for the measured failure modes:** every jurisdiction
   persona carries the veto-scope rule ("a veto must cite an acceptance
   criterion's required artifact; the criterion's own text is the bar"), and
   the runner applies exactly one re-ask on an absent/malformed ballot
   (19.6% of seats returned prose in the last run; fail-closed unanimity
   turns that into false-incompletes without the re-ask).

## Procedure

1. PRE-COMMIT the criterion in writing and log it before building fixtures or
   invoking any voter: required false-complete margin over the single-skeptic
   baseline, maximum added false-incomplete, maximum cost multiple, and what
   happens on a ceiling (baseline at 0.00). Reference values from the prior
   run: margin >= 0.40 for default adoption, 0.20-0.39 conditional, FI cap
   +0.34, cost cap 4x. Choosing numbers after seeing results is fabrication.
2. Conditions per fixture: (S) single skeptic; (X) cross-family panel of 3
   under unanimity; optionally (J') veto-scope-disciplined jurisdiction panel.
   Private contexts, fresh seats per fixture, ground truth never staged.
3. Judge with `scripts/judge.mjs` unchanged; rates recomputed independently
   from results by a separate oracle, not read from the analysis.
4. Apply the criterion as written; record the outcome and every prediction
   miss; label the runs in the outcome log (`scripts/log-verdict.mjs`).

Prior art the rematch tests: PoLL-style disjoint-family juries (the one panel
design the literature supports) versus the measured single-skeptic optimum.
