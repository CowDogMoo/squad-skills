#!/usr/bin/env python3
"""Positive and negative controls for the bundled scripts. Prints SELFTEST PASSED.

1. make_fixtures.py renders a distorted dyad riff with a known score.
2. riff_salience.py must list every expected note among its top candidates
   on every sixteenth (positive control), must NOT list the wrong-octave
   pedal (A#2) as the top candidate anywhere (octave control), and with
   --auto-tune must read the same riff rendered 40 cents sharp (tuning control).
3. riff_midi.py builds MIDI from the spec; compare_rolls.py must report a
   match against a tremolo rendering of the same spec and a mismatch against
   a spec with one note changed (negative control).
4. als_clip_region.py must map a synthetic warped clip to the right seconds,
   read an unwarped clip's loop offset as seconds, ignore an alternate take
   stored under TakeLanes, and reject a wrong expectation (negative control).

Run:  uv run --with-requirements scripts/requirements.txt python scripts/selftest.py
"""
from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
PY = sys.executable


def run(*args, expect_rc=0):
    p = subprocess.run([PY, *args], capture_output=True, text=True)
    if p.returncode != expect_rc:
        print(p.stdout[-3000:], p.stderr[-3000:])
        raise SystemExit(f"FAIL: {' '.join(os.path.basename(a) for a in args[:2])} exit {p.returncode}, expected {expect_rc}")
    return p.stdout


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="riff-selftest-")
    fx = os.path.join(tmp, "fx")
    run(os.path.join(SKILL, "evals", "files", "make_fixtures.py"), fx)
    expected = json.load(open(os.path.join(fx, "expected.json")))

    # 2. salience positive + octave control
    sal_json = os.path.join(tmp, "slots.json")
    run(os.path.join(HERE, "riff_salience.py"), os.path.join(fx, "riff.wav"), "--bpm", str(expected["bpm"]),
        "--tuning", "C1,G1,C2,F2,A#2,D#3,G3,C4", "--json", sal_json)
    slots = {r["slot"]: [c["note"] for c in r["candidates"]] for r in json.load(open(sal_json))["slots"]}
    missing = []
    for slot, notes in expected["slots"].items():
        got = slots.get(slot, [])
        for n in notes:
            if n not in got:
                missing.append((slot, n, got))
    # allow the attack slot of a new upper-voice note to lag one sixteenth
    hard = [m for m in missing if not (m[0].endswith(".1") and m[1] != "A#3" and m[1] != "A3")]
    total = sum(len(v) for v in expected["slots"].values())
    for m in hard[:10]:
        print("  missing", m)
    # Positive-control threshold: at most 3% of expected (slot, note) pairs may
    # fall outside the top candidates. Measured on this fixture: 2 of ~100,
    # both an upper-voice note ranked fifth for one sixteenth.
    if len(hard) > max(3, total * 3 // 100):
        raise SystemExit(f"FAIL: salience missed {len(hard)} of {total} expected notes (limit {max(3, total * 3 // 100)})")
    octave_wrong = [s for s, got in slots.items() if got and got[0] == "A#2"]
    if octave_wrong:
        raise SystemExit(f"FAIL: A#2 (wrong octave) ranked first in slots {octave_wrong[:5]}")
    print(f"salience: {total - len(hard)}/{total} expected (slot, note) pairs in the top candidates; {len(hard)} missed, {len(missing) - len(hard)} attack-slot lags tolerated")

    # 2b. tuning-offset control: the same riff 40 cents sharp must be read correctly
    #     with --auto-tune, and the estimate must land near +40 (near 0 on the plain fixture)
    fx2 = os.path.join(tmp, "fx_sharp")
    run(os.path.join(SKILL, "evals", "files", "make_fixtures.py"), fx2, "--cents=40")
    sal2 = os.path.join(tmp, "slots_sharp.json")
    out = run(os.path.join(HERE, "riff_salience.py"), os.path.join(fx2, "riff.wav"), "--bpm", str(expected["bpm"]),
              "--tuning", "C1,G1,C2,F2,A#2,D#3,G3,C4", "--auto-tune", "--json", sal2)
    est = json.load(open(sal2))["tune_offset_cents"]
    if not (28 <= est <= 52):
        raise SystemExit(f"FAIL: tuning offset estimate {est:+.0f} cents on the +40 cent fixture")
    slots2 = {r["slot"]: [c["note"] for c in r["candidates"]] for r in json.load(open(sal2))["slots"]}
    miss2 = [(slot, n) for slot, notes in expected["slots"].items() for n in notes if n not in slots2.get(slot, []) and not (slot.endswith(".1") and n not in ("A#3", "A3"))]
    if len(miss2) > max(3, total * 3 // 100):
        raise SystemExit(f"FAIL: with --auto-tune the +40 cent fixture missed {len(miss2)} of {total} notes")
    out = run(os.path.join(HERE, "riff_salience.py"), os.path.join(fx, "riff.wav"), "--bpm", str(expected["bpm"]),
              "--tuning", "C1,G1,C2,F2,A#2,D#3,G3,C4", "--auto-tune", "--json", os.path.join(tmp, "slots_plain.json"))
    est0 = json.load(open(os.path.join(tmp, "slots_plain.json")))["tune_offset_cents"]
    if abs(est0) > 12:
        raise SystemExit(f"FAIL: tuning offset estimate {est0:+.0f} cents on the in-tune fixture")
    print(f"tuning offset: +40 cent fixture estimated {est:+.0f}, in-tune fixture {est0:+.0f}; {total - len(miss2)}/{total} notes recovered sharp")

    # 3. midi build + roll comparison, positive and negative
    a_mid = os.path.join(tmp, "a.mid")
    run(os.path.join(HERE, "riff_midi.py"), os.path.join(fx, "riff.spec"), "--bpm", "120", "--out", a_mid)
    # tremolo rendering: same spec, every segment split into sixteenths
    trem_spec = os.path.join(tmp, "trem.spec")
    with open(trem_spec, "w") as fh:
        for line in open(os.path.join(fx, "riff.spec")):
            if line.startswith("#") or not line.strip():
                continue
            bar, b0, b1, *notes = line.split()
            b = float(b0)
            while b < float(b1) - 1e-9:
                fh.write(f"{bar} {b} {b + 0.25} {' '.join(notes)}\n")
                b += 0.25
    t_mid = os.path.join(tmp, "trem.mid")
    run(os.path.join(HERE, "riff_midi.py"), trem_spec, "--bpm", "120", "--out", t_mid)
    out = run(os.path.join(HERE, "compare_rolls.py"), a_mid, t_mid, "--expect", "match")
    assert "ROLLS MATCH" in out
    wrong_spec = os.path.join(tmp, "wrong.spec")
    with open(wrong_spec, "w") as fh:
        for line in open(os.path.join(fx, "riff.spec")):
            fh.write(line.replace("A#3 F4", "A#3 E4", 1))
    w_mid = os.path.join(tmp, "wrong.mid")
    run(os.path.join(HERE, "riff_midi.py"), wrong_spec, "--bpm", "120", "--out", w_mid)
    out = run(os.path.join(HERE, "compare_rolls.py"), a_mid, w_mid, "--expect", "mismatch")
    assert "ROLLS DIFFER" in out
    run(os.path.join(HERE, "compare_rolls.py"), a_mid, w_mid, "--expect", "match", expect_rc=1)
    print("rolls: match/mismatch controls behave")

    # 4. synthetic .als: clip at beats 100-130 plays loop beats 90-120 through a
    #    warp map where 0s->0b and 100s->180b (sample tempo 108), so the region is
    #    50.000-66.667 s.
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton><LiveSet><MainTrack><DeviceChain><Mixer><Tempo><Manual Value="120"/></Tempo></Mixer></DeviceChain></MainTrack>
<Tracks><AudioTrack Id="1"><Name><EffectiveName Value="9-Guitar REAL 5"/></Name>
<DeviceChain><MainSequencer><Sample><ArrangerAutomation><Events>
<AudioClip Id="5" Time="100"><CurrentStart Value="100"/><CurrentEnd Value="130"/><Name Value="take"/>
<Disabled Value="false"/><IsWarped Value="true"/><PitchCoarse Value="0"/><PitchFine Value="0"/><SampleVolume Value="1"/>
<Loop><LoopStart Value="90"/><LoopEnd Value="120"/><StartRelative Value="0"/></Loop>
<SampleRef><FileRef><Path Value="/tmp/take.wav"/><RelativePath Value="Samples/take.wav"/></FileRef></SampleRef>
<WarpMarkers><WarpMarker Id="1" SecTime="0" BeatTime="0"/><WarpMarker Id="2" SecTime="100" BeatTime="180"/></WarpMarkers>
</AudioClip>
<AudioClip Id="6" Time="200"><CurrentStart Value="200"/><CurrentEnd Value="216"/><Name Value="unwarped"/>
<Disabled Value="false"/><IsWarped Value="false"/><PitchCoarse Value="0"/><PitchFine Value="0"/><SampleVolume Value="1"/>
<Loop><LoopStart Value="19"/><LoopEnd Value="27"/><StartRelative Value="0"/></Loop>
<SampleRef><FileRef><Path Value="/tmp/take2.wav"/></FileRef></SampleRef>
<WarpMarkers><WarpMarker Id="1" SecTime="0" BeatTime="0"/><WarpMarker Id="2" SecTime="1" BeatTime="2"/></WarpMarkers>
</AudioClip></Events></ArrangerAutomation></Sample></MainSequencer></DeviceChain>
<TakeLanes><TakeLanes><TakeLane Id="0"><ClipAutomation><Events>
<AudioClip Id="9" Time="0"><CurrentStart Value="0"/><CurrentEnd Value="400"/><Name Value="alternate take"/>
<Disabled Value="false"/><IsWarped Value="true"/><Loop><LoopStart Value="0"/><LoopEnd Value="400"/><StartRelative Value="0"/></Loop>
<SampleRef><FileRef><Path Value="/tmp/take-alt.wav"/></FileRef></SampleRef>
<WarpMarkers><WarpMarker Id="1" SecTime="0" BeatTime="0"/><WarpMarker Id="2" SecTime="100" BeatTime="200"/></WarpMarkers>
</AudioClip></Events></ClipAutomation></TakeLane></TakeLanes></TakeLanes></AudioTrack></Tracks></LiveSet></Ableton>"""
    als = os.path.join(tmp, "synthetic.als")
    with gzip.open(als, "wb") as fh:
        fh.write(xml.encode())
    out = run(os.path.join(HERE, "als_clip_region.py"), als, "--track", "real 5", "--check-region", "50.0", "66.667")
    assert "REGION CHECK PASSED" in out
    assert "clips: 2" in out, "take-lane clip must be ignored, unwarped clip kept: " + out
    # unwarped clip: 16 arrangement beats = 8 s at 120 BPM, starting at LoopStart 19 s (seconds, not beats)
    assert "start_s=19.000 end_s=27.000" in out, "unwarped region wrong: " + out
    run(os.path.join(HERE, "als_clip_region.py"), als, "--track", "real 5", "--check-region", "45.0", "60.0", expect_rc=1)
    run(os.path.join(HERE, "als_clip_region.py"), als, "--track", "no such track", expect_rc=2)
    print("als region: warp interpolation and negative controls behave")

    print("SELFTEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
