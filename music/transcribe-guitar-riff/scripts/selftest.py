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
5. octave_check.py must name every synthetic fundamental EXACTLY, attacked and
   sustained, with the octave below and both neighbouring semitones available
   to be chosen. This one is exhaustive on purpose: the first version of that
   script scored 0 of 9 here while printing "100.0% of sampled attacks", and a
   gate that is confidently wrong is worse than no gate at all.
6. tempo_fit.py, fundamental.py, riff_cycle.py, stamp_cycle.py, tab_build.py
   and ss_convert.py each hit a ground truth we chose, and each has a negative
   control: a band holding another instrument must not answer for this one, a
   malformed spec must be rejected, an undrawable span must be reported, and a
   beat whose fraction contradicts its note value must fail check-durations.
7. The documents and the scripts directory must agree - no SKILL.md may name a
   script that does not exist, and no script may ship unreferenced.

Run:  uv run --with-requirements scripts/requirements.txt python scripts/selftest.py
"""
from __future__ import annotations

import gzip
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
PY = sys.executable


def resolve_ref(ref: str, skill_dir: str, repo_root: str) -> str:
    """Where a `scripts/...` reference in prose should point.

    A skill may legitimately name a sibling skill's script by repository path
    (transcribe-guitar-riff sends the reader to tab-vs-recording), so a bare
    join against the local scripts directory reports a false miss.
    """
    ref = ref.lstrip("./").lstrip("/")
    if ref.startswith("scripts/"):
        return os.path.join(skill_dir, ref)
    if "/scripts/" in ref:
        return os.path.join(repo_root, ref)
    return os.path.join(skill_dir, "scripts", os.path.basename(ref))


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

    # ---------------------------------------------------------------------
    # 5. octave_check.py -- the gate the whole skill leans on.
    #
    # The first version of this script answered with a relative odd-minus-even
    # partial margin, which never required a candidate to sit on a real peak.
    # It scored 0 of 9 on fixtures like these and printed "100.0% of sampled
    # attacks" every time. A gate that is confidently wrong is worse than no
    # gate, so this control is exhaustive: every fixture, exactly right.
    import numpy as np
    import soundfile as sf
    import librosa

    SR = 44100

    def render(note, path, attacked=True, seconds=8.0, partials=12, drive=3.0):
        f0 = float(librosa.note_to_hz(note))
        n = int(seconds * SR)
        y = np.zeros(n)
        if attacked:
            step = int(0.25 * SR)
            for start in range(0, n - step, step):
                tt = np.arange(step) / SR
                y[start:start + step] += (
                    sum((1.0 / k) * np.sin(2 * np.pi * f0 * k * tt + k * 0.7)
                        for k in range(1, partials))
                    * np.exp(-tt * 6)
                )
        else:
            tt = np.arange(n) / SR
            y = sum((1.0 / k) * np.sin(2 * np.pi * f0 * k * tt + k * 0.3)
                    for k in range(1, partials + 1))
        if drive:
            y = np.tanh(y * drive)
        sf.write(path, y / np.abs(y).max(), SR)
        return f0

    # Candidates span three octaves and both neighbours of every answer, so a
    # wrong octave AND a wrong pitch class are both available to be chosen.
    OCTAVE_CANDIDATES = "D1,E1,F1,F#1,G1,A1,D2,E2,F2,F#2,G2,A2,D3,F3,F#3"
    wav = os.path.join(tmp, "octave.wav")
    oc_json = os.path.join(tmp, "octave.json")
    wrong = []
    for attacked in (True, False):
        for note in ["F#2", "F2", "D1", "E2", "A1", "G2"]:
            render(note, wav, attacked=attacked)
            out = run(os.path.join(HERE, "octave_check.py"), wav, "--bpm", "120",
                      "--origin-beat", "0", "--bars", "1,4",
                      "--candidates", OCTAVE_CANDIDATES, "--json", oc_json)
            verdict = [ln for ln in out.splitlines() if ln.startswith("verdict:")]
            got = verdict[0].split()[1] if verdict else "(none)"
            if got != note:
                wrong.append((("attacked" if attacked else "sustained"), note, got))
    # A dull note with only low-order partials is the case that separates the
    # two halves of the score. Every real partial of f is also an even partial
    # of f/2 and stays inside the harmonic cap, so f/2 explains the spectrum
    # just as completely -- coverage alone cannot break the tie, and only the
    # absence of f/2's own odd partials can. Without a fixture like this the
    # control passes a one-factor scorer, which is how the first version of
    # this script shipped an entire section an octave low.
    for note in ["F#2", "E2", "A1", "D2"]:
        render(note, wav, attacked=False, partials=4, drive=0.0)
        out = run(os.path.join(HERE, "octave_check.py"), wav, "--bpm", "120",
                  "--origin-beat", "0", "--bars", "1,4",
                  "--candidates", OCTAVE_CANDIDATES)
        verdict = [ln for ln in out.splitlines() if ln.startswith("verdict:")]
        got = verdict[0].split()[1] if verdict else "(none)"
        if got != note:
            wrong.append(("4-partial", note, got))
    if wrong:
        raise SystemExit(f"FAIL: octave_check named the wrong note on {len(wrong)} fixture(s): {wrong}")

    # The historical failure, named: on an F#2 recording the octave below must
    # never win, and neither may the semitone either side.
    render("F#2", wav)
    run(os.path.join(HERE, "octave_check.py"), wav, "--bpm", "120", "--origin-beat", "0",
        "--bars", "1,4", "--candidates", OCTAVE_CANDIDATES, "--json", oc_json)
    detail = json.load(open(oc_json))
    if detail["verdict"] != "F#2" or detail["share"] < 90:
        raise SystemExit(f"FAIL: F#2 fixture read as {detail['verdict']} at {detail['share']:.0f}%")
    scores = detail["rows"][0]["scores"]
    for rival in ("F#1", "F#3", "F2", "G2"):
        if scores[rival] >= scores["F#2"]:
            raise SystemExit(f"FAIL: {rival} scored {scores[rival]} >= F#2 {scores['F#2']}")
    row = detail["rows"][0]
    if row["coverage"] < 0.6 or row["presence"] < 0.6:
        raise SystemExit(f"FAIL: winner had weak evidence {row['coverage']}/{row['presence']}")
    print(f"octave: 16/16 fixtures named exactly (12 rich, 4 low-order); F#2 beats F#1 by "
          f"{scores['F#2'] - scores['F#1']:.3f} on the same spectrum")
    print("OCTAVE CONTROL PASSED")

    # ---------------------------------------------------------------------
    # 6. The rest of the bundled scripts, each against a known answer.
    # tempo_fit: a click grid at a tempo we chose.
    for bpm in (81.3253, 86.0, 120.0):
        spb = 60.0 / bpm
        n = int(20 * SR)
        y = np.zeros(n)
        for i in range(int(20 / (spb / 2))):
            a = int(i * spb / 2 * SR)
            length = int(0.12 * SR)
            if a + length > n:
                break
            tt = np.arange(length) / SR
            y[a:a + length] += np.sin(2 * np.pi * 110 * tt) * np.exp(-tt * 25)
        click = os.path.join(tmp, "click.wav")
        sf.write(click, y / np.abs(y).max(), SR)
        out = run(os.path.join(HERE, "tempo_fit.py"), click, "--min", "70", "--max", "130", "--div", "2")
        best = float([ln for ln in out.splitlines() if "best fit" in ln][0].split()[2])
        # 0.25 BPM is the script's own search step, so that is the tightest
        # honest tolerance; anything looser would not notice a real miss.
        if abs(best - bpm) > 0.30:
            raise SystemExit(f"FAIL: tempo_fit read {best} for a {bpm} BPM grid\n{out}")

    # fundamental: the note, and the trap it exists to make visible.
    render("F#2", wav, attacked=False)
    out = run(os.path.join(HERE, "fundamental.py"), wav, "--band", "60", "130")
    top = [ln for ln in out.splitlines() if not ln.startswith("#") and ln.strip()][0].split()
    if top[3] != "F#2" or abs(float(top[4])) > 10:
        raise SystemExit(f"FAIL: fundamental read {top[3]} {top[4]} cents for F#2\n{out}")
    # Negative control for the documented trap, staged the way it happened: two
    # guitars, and a band that is the low one's HARMONIC band but the high
    # one's fundamental band. Asked there, the answer must belong to the other
    # instrument -- which is the whole reason the rule says to read a part in
    # the band its own fundamental lives in.
    tt = np.arange(int(6 * SR)) / SR
    low_f0 = float(librosa.note_to_hz("F#2"))
    high_f0 = float(librosa.note_to_hz("C4"))
    mix = sum((1.0 / k) * np.sin(2 * np.pi * low_f0 * k * tt) for k in range(1, 13))
    mix = np.tanh(mix * 3)
    mix += 3.0 * sum((1.0 / k) * np.sin(2 * np.pi * high_f0 * k * tt + k * 0.2) for k in range(1, 6))
    two = os.path.join(tmp, "two_guitars.wav")
    sf.write(two, mix / np.abs(mix).max(), SR)
    out = run(os.path.join(HERE, "fundamental.py"), two, "--band", "60", "130")
    own = [ln for ln in out.splitlines() if not ln.startswith("#") and ln.strip()][0].split()
    if own[3] != "F#2":
        raise SystemExit(f"FAIL: in its own fundamental band the low part read {own[3]}\n{out}")
    out = run(os.path.join(HERE, "fundamental.py"), two, "--band", "240", "290")
    crowded = [ln for ln in out.splitlines() if not ln.startswith("#") and ln.strip()][0].split()
    if crowded[3] in ("F#2", "F#3", "F#4"):
        raise SystemExit(f"FAIL: the harmonic band still answered {crowded[3]}; the trap "
                         f"control proves nothing\n{out}")
    # And a band with nothing in it must decline rather than invent an answer.
    run(os.path.join(HERE, "fundamental.py"), wav, "--band", "34", "50", expect_rc=1)

    # riff_cycle: a genuine 2-bar cycle, so a 1-bar lag must not satisfy it.
    bpm, spb = 120.0, 0.5
    bar_a = ["E2", "E2", "G2", "E2", "E2", "E2", "A2", "G2"]
    bar_b = ["E2", "E2", "G2", "E2", "D2", "D2", "C2", "D2"]
    seq = (bar_a + bar_b) * 4
    n = int(len(seq) * spb / 2 * SR) + SR
    y = np.zeros(n)
    for i, note in enumerate(seq):
        f0 = float(librosa.note_to_hz(note))
        a = int(i * spb / 2 * SR)
        length = int(spb / 2 * SR)
        tt = np.arange(length) / SR
        y[a:a + length] += (
            sum((1.0 / k) * np.sin(2 * np.pi * f0 * k * tt) for k in range(1, 10)) * np.exp(-tt * 5)
        )
    cyc_wav = os.path.join(tmp, "cycle.wav")
    sf.write(cyc_wav, np.tanh(y * 3) / np.abs(np.tanh(y * 3)).max(), SR)
    out = run(os.path.join(HERE, "riff_cycle.py"), cyc_wav, "--bpm", str(bpm),
              "--origin-beat", "0", "--bars", "1,8", "--band", "60,200")
    header = [ln for ln in out.splitlines() if "one cycle" in ln][0]
    if "= 2 bar(s)" not in header:
        raise SystemExit(f"FAIL: riff_cycle missed the 2-bar cycle: {header}")
    cycle_spec = os.path.join(tmp, "cycle.spec")
    with open(cycle_spec, "w") as fh:
        fh.write(out)

    # stamp_cycle: 2-bar cycle over 8 bars is 4 blocks, and bars stay in range.
    out = run(os.path.join(HERE, "stamp_cycle.py"), cycle_spec, "--bars", "1,8")
    lines = [ln.split() for ln in out.splitlines() if ln and not ln.startswith("#")]
    bars_seen = sorted({int(p[0]) for p in lines})
    if bars_seen != list(range(1, 9)):
        raise SystemExit(f"FAIL: stamp_cycle filled bars {bars_seen}, wanted 1..8")
    per_bar = {b: sum(1 for p in lines if int(p[0]) == b) for b in bars_seen}
    if per_bar[1] != per_bar[3] or per_bar[2] != per_bar[4]:
        raise SystemExit(f"FAIL: stamped blocks disagree: {per_bar}")
    bad_spec = os.path.join(tmp, "bad.spec")
    with open(bad_spec, "w") as fh:
        fh.write("1 1.00 nonsense\n")
    run(os.path.join(HERE, "stamp_cycle.py"), bad_spec, "--bars", "1,2", expect_rc=1)

    # tab_build: a bar whose measured spans are deliberately undrawable.
    # 1.25 and 1.75 quarter notes are exactly the 5/4 and 7/4 lengths the docs
    # name; no single note value can draw either.
    rough = os.path.join(tmp, "rough.spec")
    with open(rough, "w") as fh:
        fh.write("1 1.00 2.25 E2\n1 2.25 4.00 G2\n1 4.00 5.00 A2\n"
                 "2 1.00 2.25 E2\n2 2.25 4.00 G2\n2 4.00 5.00 A2\n")
    solved = run(os.path.join(HERE, "tab_build.py"), rough,
                 "--tuning", "E2,A2,D3,G3,B3,E4", "--single-note-durations")
    riff = [ln for ln in solved.splitlines() if not ln.startswith("#")][0]
    LEGAL = {"1", "2", "4", "8", "16", "32"}
    BEATS = {"1": 4.0, "2": 2.0, "4": 1.0, "8": 0.5, "16": 0.25, "32": 0.125}
    for bar_index, bar in enumerate(riff.split("|"), start=1):
        total = 0.0
        for token in bar.split():
            dur = token.split(":")[0]
            base = dur.rstrip(".t")
            if base not in LEGAL:
                raise SystemExit(f"FAIL: tab_build emitted the illegal duration {dur!r}")
            beats = BEATS[base]
            if dur.endswith("."):
                beats *= 1.5
            elif dur.endswith("t"):
                beats *= 2 / 3
            total += beats
        if abs(total - 4.0) > 1e-6:
            raise SystemExit(f"FAIL: solved bar {bar_index} sums to {total} beats, not 4")
    frets = [int(t.split(".")[-1]) for t in riff.replace("|", " ").split() if ":r" not in t]
    if any(abs(b - a) > 5 for a, b in zip(frets, frets[1:])):
        raise SystemExit(f"FAIL: tab_build ignored its reach limit: {frets}")
    # Negative control: without the flag those spans must be reported as not
    # writable, or --single-note-durations would be solving nothing.
    naive = run(os.path.join(HERE, "tab_build.py"), rough, "--tuning", "E2,A2,D3,G3,B3,E4")
    forced = [ln for ln in naive.splitlines() if "not writable" in ln]
    if not forced or forced[0].split("; ")[1].startswith("0 of"):
        raise SystemExit(f"FAIL: the undrawable-span control did not fire:\n{naive}")

    # ss_convert: a track whose durations we chose, and a bar that breaks them.
    track = {
        "tuning": [64, 59, 55, 50, 45, 40],
        "automations": {"tempo": [{"measure": 0, "bpm": 162}, {"measure": 2, "bpm": 120}]},
        "measures": [
            {"voices": [{"beats": [
                {"duration": [1, 4], "type": 4, "notes": [{"string": 5, "fret": 0}]},
                {"duration": [1, 4], "type": 4, "notes": [{"string": 5, "fret": 3}]},
                {"duration": [1, 2], "type": 2, "notes": [{"string": 5, "fret": 5}]},
            ]}]},
            {"voices": [{"beats": [
                {"duration": [1, 1], "type": 1, "notes": [{"string": 5, "fret": 0}]},
            ]}]},
        ],
    }
    ss_path = os.path.join(tmp, "track.json")
    with open(ss_path, "w") as fh:
        json.dump(track, fh)
    out = run(os.path.join(HERE, "ss_convert.py"), "check-durations", ss_path)
    if not out.lstrip().startswith("0 beats"):
        raise SystemExit(f"FAIL: ss_convert rejected durations that are legal:\n{out}")
    out = run(os.path.join(HERE, "ss_convert.py"), "tempo-map", ss_path)
    if "162" not in out or "120" not in out:
        raise SystemExit(f"FAIL: ss_convert lost a tempo change:\n{out}")
    riff_out = os.path.join(tmp, "ss.riff")
    run(os.path.join(HERE, "ss_convert.py"), "to-riff", ss_path, "--out", riff_out)
    ss_riff = open(riff_out).read().strip()
    if ss_riff.split("|")[0].split() != ["4:6.0", "4:6.3", "2:6.5"]:
        raise SystemExit(f"FAIL: ss_convert to-riff lost the fretting or the rhythm:\n{ss_riff}")
    for bar in ss_riff.split("|"):
        total = sum(BEATS[t.split(":")[0].rstrip(".t")] for t in bar.split())
        if abs(total - 4.0) > 1e-6:
            raise SystemExit(f"FAIL: ss_convert wrote a bar of {total} beats: {bar}")
    # Negative control: a beat whose declared fraction contradicts its note
    # type must be reported, or check-durations proves nothing.
    broken = json.loads(json.dumps(track))
    broken["measures"][0]["voices"][0]["beats"][0]["duration"] = [1, 3]
    broken_path = os.path.join(tmp, "broken.json")
    with open(broken_path, "w") as fh:
        json.dump(broken, fh)
    out = run(os.path.join(HERE, "ss_convert.py"), "check-durations", broken_path, expect_rc=1)
    print("new scripts: tempo_fit, fundamental, riff_cycle, stamp_cycle, tab_build "
          "and ss_convert all hit ground truth, negative controls fire")
    print("NEW SCRIPT CONTROLS PASSED")

    # ---------------------------------------------------------------------
    # 7. The docs and the scripts directory must agree. A SKILL.md that names a
    # script which does not exist sends the reader into a dead end; a script no
    # document names never gets run. Both shipped here, so both are checked.
    prose = ""
    for root_dir, dirs, files in os.walk(SKILL):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "node_modules", ".venv")]
        for fname in files:
            if fname.endswith(".md"):
                with open(os.path.join(root_dir, fname), encoding="utf-8") as fh:
                    prose += fh.read()
    repo = os.path.dirname(os.path.dirname(SKILL))
    named = set(re.findall(r"[\w./-]*scripts/[A-Za-z0-9_]+\.(?:py|mjs)", prose))
    missing = sorted(r for r in named if not os.path.exists(resolve_ref(r, SKILL, repo)))
    if missing:
        raise SystemExit(f"FAIL: the docs name scripts that do not exist: {missing}")
    on_disk = {f for f in os.listdir(HERE)
               if f.endswith((".py", ".mjs")) and f not in ("selftest.py", "check_evals.py")}
    orphans = sorted(f for f in on_disk if f not in prose)
    if orphans:
        raise SystemExit(f"FAIL: these scripts are referenced by no document: {orphans}")
    print(f"skill docs: {len(named)} referenced script(s) all present, "
          f"{len(on_disk)} script(s) all referenced")
    print("TGR SKILL DOCS PASSED")

    print("SELFTEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
