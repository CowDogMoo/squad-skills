---
tags: [ableton-double-track-timing, offline]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Bash]
---

Generate the synthetic test sets by running `python3 evals/files/make_fixtures.py OUTDIR` with a fresh temporary output directory. This needs no source set, Live, or network. Work only from the generated files and bundled scripts; use installed Python dependencies rather than downloading packages. Then inspect planted-nudge.als: Scratch A and Scratch B are a double, and sound smeared around bars 6 and 8. Find the cause and tell me exactly what to change. Compare the repeated sections against bar 2, and check clean-control.als as a negative control. Do not change either set or its samples, connect to Live, or move anything. Reports in your working directory are fine.
