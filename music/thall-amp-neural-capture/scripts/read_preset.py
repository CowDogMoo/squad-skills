#!/usr/bin/env python3
"""Read Odeholm thall amp preset files (.afx) and tone profiles (.odtp).

A preset is a sequence of JUCE ValueTrees written back to back:
`preset_data_tree` (name, category, id) followed by `thall amp_state`
(one PARAM node per automatable parameter, plus hidden_param nodes, the
cab IR path, the embedded tone profile, and an LFO table).

Use it to read the exact capture-time state of a preset without touching
the live plugin, to diff two presets, or to survey the whole library:

    python3 read_preset.py "Mirar - Leo.afx"          # one preset, full table
    python3 read_preset.py --plan "Mirar - Leo.afx"   # how to capture it faithfully
    python3 read_preset.py --library                  # every installed preset
    python3 read_preset.py --diff A.afx B.afx         # only what differs
    python3 read_preset.py --json "Mirar - Leo.afx"   # machine-readable

Two things the file cannot tell you, both covered in SKILL.md: switch
parameters saved by some plugin versions carry no value (reported as
"not stored"), and with Tone Lock enabled the plugin ignores a preset's
tone-match and input-gain values on load. Read those back from the live
plugin.

Stdlib only. Ranges and defaults below come from the plugin's own
published parameter info (`auval -v aufx Th4m OdAu`), descriptions from
its tooltip strings; plugin version 1.0.4.
"""

import argparse
import glob
import json
import os
import struct
import sys

MAC_PRESET_DIR = os.path.expanduser("~/Library/Odeholm Audio/thall amp/Presets")

# id -> (Ableton param index, UI name, section, kind, min, default, max, unit)
# kind: sw = switch, pct/db/hz/st = continuous. Index 1 is Live's "Device On".
PARAMS = [
    ("host_bypass",      1,  "Host Bypass",          "Global", "sw",    0, 0, 1, ""),
    ("power",            2,  "Power",                "Global", "sw",    0, 1, 1, ""),
    ("input_gain",       3,  "Input Gain",           "Global", "db",  -30, 0, 30, "dB"),
    ("output_gain",      4,  "Output Gain",          "Global", "db",  -30, 0, 30, "dB"),
    ("lofi",             5,  "Lo-Fi",                "Output", "sw",    0, 0, 1, ""),
    ("tone_power",       6,  "Tone Matching Power",  "Tone",   "sw",    0, 1, 1, ""),
    ("tone_amount",      7,  "Tone Matching Amount", "Tone",   "pct",   0, 30, 100, "%"),
    ("tone_smooth",      8,  "Tone Matching Smooth", "Tone",   "pct",   0, 80, 100, "%"),
    ("tighten_power",    9,  "Shape Power",          "Shape",  "sw",    0, 1, 1, ""),
    ("tighten_gate",     10, "Tighten Gate",         "Shape",  "db", -100, -50, -12, "dB"),
    ("tighten_chug",     11, "Tighten Chug",         "Shape",  "pct",   0, 50, 100, "%"),
    ("tighten_freq",     12, "Tighten Frequency",    "Shape",  "hz",   20, 250, 2500, "Hz"),
    ("pitch_power",      13, "Pitch Power",          "Pitch",  "sw",    0, 1, 1, ""),
    ("pitch_whammy",     14, "Pitch Whammy",         "Pitch",  "st",  -24, 0, 24, "st"),
    ("pitch_thicken",    15, "Pitch Thicken",        "Pitch",  "pct",   0, 20, 100, "%"),
    ("pitch_hi_cut",     16, "Pitch Hi-Cut",         "Pitch",  "hz",   20, 10000, 20000, "Hz"),
    ("pitch_cleanse",    17, "Pitch Cleanse",        "Pitch",  "sw",    0, 0, 1, ""),
    ("pitch_latency",    18, "Pitch Latency",        "Pitch",  "sw",    0, 0, 1, ""),
    ("thicken_parallel", 19, "Thicken Amp Parallel", "Pitch",  "sw",    0, 0, 1, ""),
    ("low_dirt",         20, "Low Dirt",             "Pitch",  "pct",   0, 0, 100, "%"),
    ("amp_power",        21, "Amplifier Power",      "Amp",    "sw",    0, 1, 1, ""),
    ("amp_drive",        22, "Amp Drive",            "Amp",    "pct",   0, 50, 100, "%"),
    ("amp_lo",           23, "Amp Lo",               "Amp",    "db",  -12, 0, 12, "dB"),
    ("amp_mid",          24, "Amp Mid",              "Amp",    "db",  -12, 0, 12, "dB"),
    ("amp_hi",           25, "Amp Hi",               "Amp",    "db",  -12, 0, 12, "dB"),
    ("amp_presence",     26, "Amp Presence",         "Amp",    "db",  -12, 0, 12, "dB"),
    ("cab_power",        27, "Cab Power",            "Cab",    "sw",    0, 1, 1, ""),
    ("lo_cut",           28, "Lo-Cut",               "Output", "hz",   20, 20, 20000, "Hz"),
    ("hi_cut",           29, "Hi-Cut",               "Output", "hz",   20, 20000, 20000, "Hz"),
    ("mono_stereo",      30, "Mono/Stereo Toggle",   "Global", "sw",    0, 1, 1, ""),
]
BY_ID = {p[0]: p for p in PARAMS}

# Saved in the preset but not automatable, so absent from the host's list.
UI_ONLY = {
    "tone_lock": "Tone Lock",
    "pitch_thicken_solo": "Thicken Solo",
    "tuner_auto_mute": "Tuner Auto-Mute",
}


class Reader:
    """Minimal reader for JUCE's ValueTree binary format."""

    def __init__(self, data):
        self.b, self.i = data, 0

    def byte(self):
        v = self.b[self.i]
        self.i += 1
        return v

    def compressed_int(self):
        n = self.byte()
        neg, n = n & 0x80, n & 0x7F
        v = 0
        for k in range(n):
            v |= self.b[self.i] << (8 * k)
            self.i += 1
        return -v if neg else v

    def string(self):
        end = self.b.index(b"\x00", self.i)
        s = self.b[self.i:end].decode("utf-8", "replace")
        self.i = end + 1
        return s

    def var(self):
        n = self.compressed_int()
        if n == 0:
            return None
        end = self.i + n
        marker = self.byte()
        if marker == 1:
            v = struct.unpack_from("<i", self.b, self.i)[0]
        elif marker == 2:
            v = True
        elif marker == 3:
            v = False
        elif marker == 4:
            v = struct.unpack_from("<d", self.b, self.i)[0]
        elif marker == 5:
            v = self.b[self.i:end - 1].decode("utf-8", "replace")
        elif marker == 6:
            v = struct.unpack_from("<q", self.b, self.i)[0]
        elif marker == 7:
            v = "<array>"
        elif marker == 8:
            v = "<binary %d bytes>" % (end - self.i)
        else:
            v = None
        self.i = end
        return v

    def tree(self):
        node = {"type": self.string(), "props": {}, "children": []}
        for _ in range(self.compressed_int()):
            # Name before value: a single subscript assignment would read them
            # back to front, because Python evaluates the right side first.
            name = self.string()
            node["props"][name] = self.var()
        for _ in range(self.compressed_int()):
            node["children"].append(self.tree())
        return node


def read(path):
    """Parse one .afx/.odtp into a flat dict of preset metadata and state."""
    r = Reader(open(path, "rb").read())
    out = {"path": path, "file": os.path.basename(path), "params": {},
           "not_stored": [], "cab_file": "", "tone_profile_rate": None, "lfo": []}
    while r.i < len(r.b):
        t = r.tree()
        if t["type"] == "source_tree_id":
            # A .odtp is a tone profile on its own: no state tree wrapping it.
            rate = t["props"].get("source_sr_id")
            out["tone_profile_rate"] = rate if rate and rate > 0 else None
        elif t["type"] == "preset_data_tree":
            out.setdefault("name", t["props"].get("preset_name"))
            out.setdefault("category", t["props"].get("preset_cat"))
            out.setdefault("creator", t["props"].get("preset_creator"))
        elif t["type"].endswith("_state"):
            for c in t["children"]:
                kind, p = c["type"], c["props"]
                if kind in ("PARAM", "hidden_param"):
                    key = p.get("id") or p.get("param_name")
                    val = p.get("value", p.get("param_val"))
                    if val is None:
                        out["not_stored"].append(key)
                    else:
                        out["params"][key] = val
                elif kind == "cab_tree_id":
                    out["cab_file"] = p.get("cab_file_id") or ""
                elif kind == "source_tree_id":
                    rate = p.get("source_sr_id")
                    out["tone_profile_rate"] = rate if rate and rate > 0 else None
                elif kind == "lfo_data_tree":
                    out["lfo"] = [k["props"]["lfo_data_param"] for k in c["children"]
                                  if k["props"].get("lfo_data_index", -1) != -1
                                  or k["props"].get("lfo_data_depth", 0)]
    return out


def fmt(pid, value):
    if value is None:
        return "not stored"
    meta = BY_ID.get(pid)
    if not meta:
        return "%g" % value
    kind, unit = meta[4], meta[8]
    if kind == "sw":
        return "On" if value >= 0.5 else "Off"
    if kind == "hz":
        if pid == "lo_cut" and value <= 20.5:
            return "Off (20 Hz)"
        if pid == "hi_cut" and value >= 19950:
            return "Off (20 kHz)"
        return "%.1f kHz" % (value / 1000) if value >= 1000 else "%.0f Hz" % value
    if kind == "db":
        return "%+.1f dB" % (value + 0.0)
    if kind == "st":
        return "%+.1f st" % (value + 0.0)
    return "%.0f%s" % (value, unit)


def capture_notes(p):
    """Everything about this preset that changes how it should be captured."""
    v, notes = p["params"], []
    on = lambda k: v.get(k, 1) >= 0.5

    if v.get("tighten_chug", 0) > 0 and on("tighten_power"):
        notes.append(
            "Tighten Chug %.0f%% at %s — dynamic, cannot be modelled. Capture it "
            "anyway; expect a permanent low-mid deficit with low coherence."
            % (v["tighten_chug"], fmt("tighten_freq", v.get("tighten_freq"))))
    if on("pitch_power") and v.get("pitch_thicken", 0) > 0:
        notes.append(
            "Pitch Thicken %.0f%% — an octave-down generator, also unmodellable. "
            "Powering the Pitch section off for the capture REMOVES it; decide "
            "whether that is the sound you play." % v["pitch_thicken"])
    if on("pitch_power") and abs(v.get("pitch_whammy", 0)) > 0.05:
        notes.append("Pitch Whammy %s — pitch shifting cannot be captured at all."
                     % fmt("pitch_whammy", v["pitch_whammy"]))
    if on("pitch_power") and v.get("low_dirt", 0) > 0:
        notes.append(
            "Low Dirt %.0f%% — static pre-distortion, so it captures fine, but the "
            "UI groups it with the Pitch section. Confirm by ear that Pitch Power "
            "off does not also mute it before capturing this preset."
            % v["low_dirt"])
    if v.get("tighten_gate", -100) > -99 and on("tighten_power"):
        notes.append("Tighten Gate %s — set it to -100 dB before capturing; a gate "
                     "swallows the capture's own test signal."
                     % fmt("tighten_gate", v["tighten_gate"]))
    if p["cab_file"]:
        exists = os.path.exists(p["cab_file"])
        notes.append("Loads a third-party cab IR: %s%s"
                     % (p["cab_file"], "" if exists else
                        "  <-- MISSING on this machine, so the preset is not "
                        "sounding as its author built it"))
    if p["tone_profile_rate"]:
        notes.append(
            "Ships an embedded tone-match profile learned at %d Hz from the "
            "author's guitar, applied at %s. With Tone Lock enabled the plugin "
            "does not load it and your own profile stays in the signal path."
            % (p["tone_profile_rate"], fmt("tone_amount", v.get("tone_amount"))))
    if not on("cab_power"):
        notes.append("Cab Power off — this is an amp-only preset; capture it as "
                     "\"Amp\" and put an IR after it on the QC.")
    if p["not_stored"]:
        notes.append("Saved without values for: %s. The file cannot tell you their "
                     "state; read them from the live plugin."
                     % ", ".join(sorted(p["not_stored"])))
    if p["lfo"]:
        notes.append("Modulation assigned to: %s." % ", ".join(p["lfo"]))
    return notes


def show(p):
    print("%s\n  name %r   category %r%s"
          % (p["file"], p.get("name"), p.get("category"),
             ("   by %r" % p["creator"]) if p.get("creator") else ""))
    section = None
    for pid, idx, label, sect, kind, lo, dflt, hi, unit in PARAMS:
        if pid not in p["params"] and pid not in p["not_stored"]:
            continue
        if sect != section:
            print("  [%s]" % sect)
            section = sect
        value = p["params"].get(pid)
        mark = " " if value is not None and abs(value - dflt) < 1e-6 else "*"
        print("   %2d %-22s %-14s %s" % (idx, label, fmt(pid, value), mark))
    if not p["params"]:
        # A .odtp holds a tone profile only: the learned curve and its rate.
        print("  tone-match profile, learned at %s Hz"
              % (int(p["tone_profile_rate"]) if p["tone_profile_rate"] else "unknown"))
        return
    extra = [(UI_ONLY[k], p["params"][k]) for k in UI_ONLY if k in p["params"]]
    if extra:
        print("  [UI state, not automatable]")
        for label, value in extra:
            print("   -- %-22s %s" % (label, "On" if value >= 0.5 else "Off"))
    print("  (* = not the plugin default)")
    notes = capture_notes(p)
    if notes:
        print("  Capture notes:")
        for n in notes:
            print("   - " + n)
    print()


def plan(p):
    """A capture plan: what to change, what bakes in, what to rebuild, what is lost."""
    v = p["params"]
    on = lambda k: v.get(k, 1) >= 0.5
    get = lambda k, d=0: v.get(k, d)
    print("%s — capture plan\n" % p["file"])

    print("BEFORE YOU CAPTURE — change these, then read them back from the plugin")
    if get("tighten_gate", -100) > -99 and on("tighten_power"):
        print("  Tighten Gate        %-12s -> -100 dB   a gate swallows the QC's own"
              % fmt("tighten_gate", get("tighten_gate", -100)))
        print("%stest signal" % (" " * 48))
    if on("mono_stereo"):
        print("  Mono/Stereo Toggle  %-12s -> Off       the capture loop is mono" % "On")
    if on("pitch_power"):
        why = ("removes the octave, which you rebuild on the grid"
               if get("pitch_thicken") > 0 or abs(get("pitch_whammy")) > 0.05
               else "drops the pitch shifter's latency; nothing audible is lost")
        print("  Pitch Power         %-12s -> Off       %s" % ("On", why))
    print("  Output Gain         %-12s -> +0.0 dB   make up level on the QC capture"
          % fmt("output_gain", get("output_gain")))
    print("%sblock's Volume, never its Gain" % (" " * 48))
    print("  Input Gain          set by level calibration, not by this file; it is baked")
    print("                      into the capture and decides how hard the model is driven")
    print("  Capture type:       %s"
          % ("\"Amp and Cab\" (Cab Power is on — the only way to keep the internal cab)"
             if on("cab_power") else
             "\"Amp\" (Cab Power is off — put an IR Loader after the capture)"))

    print("\nBAKED IN — leave exactly as the preset has them")
    print("  Amp        Drive %s, Lo %s, Mid %s, Hi %s, Presence %s"
          % (fmt("amp_drive", get("amp_drive")), fmt("amp_lo", get("amp_lo")),
             fmt("amp_mid", get("amp_mid")), fmt("amp_hi", get("amp_hi")),
             fmt("amp_presence", get("amp_presence"))))
    print("  Low Dirt   %s%s" % (fmt("low_dirt", get("low_dirt")),
                                 "" if get("low_dirt") else "  (off)"))
    if get("low_dirt") > 0 and not on("pitch_power"):
        print("             but Pitch Power is off, and Low Dirt may sit inside that")
        print("             section — check by ear whether it is audible at all")
    print("  Output     Lo-Cut %s, Hi-Cut %s, Lo-Fi %s"
          % (fmt("lo_cut", get("lo_cut", 20)), fmt("hi_cut", get("hi_cut", 20000)),
             fmt("lofi", get("lofi", 0))))
    print("  Tone Match file says %s at %s / smooth %s — Tone Lock overrides this on"
          % (fmt("tone_power", get("tone_power", 1)), fmt("tone_amount", get("tone_amount", 30)),
             fmt("tone_smooth", get("tone_smooth", 80))))
    print("             load, so read what is actually running from the live plugin")

    print("\nREBUILD ON THE GRID")
    rebuilt = False
    if get("tighten_gate", -100) > -99 and on("tighten_power"):
        print("  Input-block gate or Utility > Adaptive Gate, before the capture.")
        print("    The plugin gated at %s. The QC's control is a percentage, so the"
              % fmt("tighten_gate", get("tighten_gate")))
        print("    number does not transfer — dial it by ear against the plugin.")
        rebuilt = True
    if on("pitch_power") and get("pitch_thicken") > 0:
        where = ("its own row with its own capture, joined by a mixer"
                 if on("thicken_parallel") else "before the Neural Capture block")
        print("  Pitch block: -12 st, mix %s, low-pass %s — %s."
              % (fmt("pitch_thicken", get("pitch_thicken")),
                 fmt("pitch_hi_cut", get("pitch_hi_cut", 10000)), where))
        print("    Thicken Amp Parallel is %s. On a single row you cannot low-pass only"
              % fmt("thicken_parallel", get("thicken_parallel", 0)))
        print("    the octave; an exact rebuild needs Splitter > [pitch + EQ] and dry > Mixer.")
        rebuilt = True
    if on("pitch_power") and abs(get("pitch_whammy")) > 0.05:
        print("  Wham or Pitch Shifter block before the capture, at %s."
              % fmt("pitch_whammy", get("pitch_whammy")))
        rebuilt = True
    if not on("cab_power"):
        print("  IR Loader after the capture — this is an amp-only capture.")
        rebuilt = True
    if not rebuilt:
        print("  Nothing. Capture straight into the preset.")

    print("\nLOST — expect it, record it, do not EQ it away")
    if get("tighten_chug") > 0 and on("tighten_power"):
        print("  Tighten Chug %s at %s. A static model cannot follow pick attack, so"
              % (fmt("tighten_chug", get("tighten_chug")),
                 fmt("tighten_freq", get("tighten_freq", 250))))
        print("  the capture will show a permanent band deficit at low coherence. The one")
        print("  measured case on this rig — Chug 50 — sat at -4 dB / 0.4-0.5 over 60-120 Hz.")
    else:
        print("  Nothing. No dynamic control is running in this preset.")

    warnings = []
    if p["cab_file"] and not os.path.exists(p["cab_file"]):
        warnings.append("Cab IR is missing on this machine (%s), so the preset falls back\n"
                        "  to the internal cab and you would capture the fallback."
                        % p["cab_file"])
    if p["tone_profile_rate"]:
        warnings.append("Ships a tone-match profile learned at %d Hz from the author's guitar.\n"
                        "  Tone Lock stops it loading, so your own profile gets captured instead."
                        % p["tone_profile_rate"])
    if p["not_stored"]:
        warnings.append("Saved without values for: %s.\n"
                        "  Read those from the live plugin." % ", ".join(sorted(p["not_stored"])))
    if warnings:
        print("\nWARNINGS")
        for w in warnings:
            print("  " + w)
    print()


def diff(a, b):
    print("%s  ->  %s" % (a["file"], b["file"]))
    for pid, idx, label, _s, _k, _lo, _d, _hi, _u in PARAMS:
        x, y = a["params"].get(pid), b["params"].get(pid)
        if x is None and y is None:
            continue
        if x is None or y is None or abs(x - y) > 1e-6:
            print("  %2d %-22s %-16s -> %s" % (idx, label, fmt(pid, x), fmt(pid, y)))
    if a["cab_file"] != b["cab_file"]:
        print("  -- cab IR                %-16s -> %s"
              % (a["cab_file"] or "(internal)", b["cab_file"] or "(internal)"))


def compact(pid, value):
    """Short form for the library table, where columns have to line up."""
    if value is None:
        return "-"
    if pid in ("lo_cut", "hi_cut") and fmt(pid, value).startswith("Off"):
        return "off"
    return fmt(pid, value).replace(" ", "").replace("+", "")


def library(paths):
    cols = [("amp_drive", "drive"), ("tighten_chug", "chug"),
            ("tighten_freq", "chugHz"), ("tighten_gate", "gate"),
            ("pitch_thicken", "thickn"), ("low_dirt", "dirt"),
            ("lo_cut", "locut"), ("hi_cut", "hicut"), ("tone_power", "tone")]
    head = "  ".join(label.rjust(7) for _pid, label in cols)
    print("%-46s %s   flags" % ("preset", head))
    for path in paths:
        p = read(path)
        row = "  ".join(compact(pid, p["params"].get(pid)).rjust(7) for pid, _l in cols)
        flags = []
        if p["cab_file"]:
            flags.append("IR!" if not os.path.exists(p["cab_file"]) else "IR")
        if p["tone_profile_rate"]:
            flags.append("profile@%dk" % round(p["tone_profile_rate"] / 1000))
        if p["not_stored"]:
            flags.append("%d unsaved" % len(p["not_stored"]))
        print("%-46s %s   %s" % (p["file"][:46], row, " ".join(flags)))
    print("\nIR = loads a third-party cab IR, IR! = that file is missing here.\n"
          "profile@Nk = ships an embedded tone-match profile learned at N kHz.\n"
          "unsaved = switch parameters the file stores without a value.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*", help=".afx preset files")
    ap.add_argument("--library", action="store_true",
                    help="summarise every preset installed under %s" % MAC_PRESET_DIR)
    ap.add_argument("--diff", nargs=2, metavar=("A", "B"))
    ap.add_argument("--plan", action="store_true",
                    help="print a capture plan instead of the parameter table")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.diff:
        diff(read(args.diff[0]), read(args.diff[1]))
        return 0
    paths = args.files
    if args.library:
        paths = sorted(glob.glob(os.path.join(MAC_PRESET_DIR, "*", "*.afx")))
        if not paths:
            print("no presets found under %s" % MAC_PRESET_DIR, file=sys.stderr)
            return 1
        if not args.json:
            library(paths)
            return 0
    if not paths:
        ap.print_help()
        return 1
    if args.json:
        print(json.dumps([read(p) for p in paths], indent=1))
    else:
        for path in paths:
            (plan if args.plan else show)(read(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
