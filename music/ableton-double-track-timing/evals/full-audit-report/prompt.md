---
tags: [ableton-double-track-timing, offline]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Bash]
---

Generate the synthetic test sets by running `python3 evals/files/make_fixtures.py OUTDIR` with a fresh temporary output directory. This needs no source set, Live, or network. Work only from the generated files and bundled scripts; use installed Python dependencies rather than downloading packages. Then do a full read-only timing audit of full-audit.als. Scratch A and Scratch B are a double too, despite their names. Cover all the doubles, using placement checks and source attack-envelope measurements. The matching half-beat slices on both Scratch tracks in bars 10-12 are an intentional rhythmic edit: account for them in the report. Use clean-control.als to check the detectors. No amp-rendered stems are available. Do not change the sets or samples, connect to Live, or move anything. Reports in your working directory are fine.
