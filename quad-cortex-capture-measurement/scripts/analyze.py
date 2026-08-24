#!/usr/bin/env python3
"""Same-performance comparison of a Quad Cortex capture against its plugin reference.

Takes the three files recorded in one pass over the QC's USB interface
(DI = Dry Input 1, plugin = the Post-FX REC track, QC = Wet Signal L/R) and
reports: same-performance check (full-band cross-correlation), LUFS/peak,
1/6-oct spectra normalised at 500 Hz-2 kHz with banded QC-plugin deltas,
per-band coherence, and null depth after signed gain match and after a
best-fit 512-tap linear EQ. Saves the two-panel plot as
null-test-YYYY-MM-DD-HHMM.png.

Deps: numpy scipy soundfile pyloudnorm matplotlib
  uv run --with numpy --with scipy --with soundfile --with pyloudnorm \
    --with matplotlib analyze.py DI.wav PLUGIN.wav QC.wav --out-dir <project>

The algorithm is the one validated on Jayson's rig on 2026-08-24
(null-test-analyze.py in the amp-sim-neural-capture project); keep changes
result-compatible so numbers stay comparable across sessions.
"""

import argparse
import datetime
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BANDS = [
    (60, 120), (120, 250), (250, 500), (500, 1000), (1000, 2000),
    (2000, 4000), (4000, 5000), (5000, 8000), (8000, 12000),
]
HOP_S = 0.01  # 10 ms envelope hop


def load(path, expect_sr=None):
    x, sr = sf.read(path)
    if expect_sr is not None and sr != expect_sr:
        sys.exit(f"{path}: sample rate {sr} != {expect_sr}; all files must match")
    if x.ndim > 1:
        x = x.mean(axis=1)  # dual-mono Post-FX takes collapse cleanly
    return x.astype(np.float64), sr


def envelope_db(x, sr):
    hop = int(HOP_S * sr)
    m = len(x) // hop * hop
    e = np.sqrt((x[:m].reshape(-1, hop) ** 2).mean(axis=1))
    return 20 * np.log10(e + 1e-9)


def sixth_oct_smooth(P, f, frac=6):
    out = np.zeros_like(P)
    for i, fc in enumerate(f):
        if fc <= 0:
            out[i] = P[i]
            continue
        lo, hi = fc * 2 ** (-1 / (2 * frac)), fc * 2 ** (1 / (2 * frac))
        sel = (f >= lo) & (f <= hi)
        out[i] = P[sel].mean()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("di")
    ap.add_argument("plugin")
    ap.add_argument("qc")
    ap.add_argument("--out-dir", default=".", help="where the PNG lands (project folder)")
    ap.add_argument("--label", default="", help="title context, e.g. '15:07 take, Thall Amp+Cab vs plugin'")
    args = ap.parse_args()

    di, sr = load(args.di)
    pl, _ = load(args.plugin, sr)
    qc, _ = load(args.qc, sr)
    n = min(len(pl), len(qc))
    pl, qc = pl[:n], qc[:n]

    # --- same-performance check: FULL-BAND waveform xcorr, never envelope
    # correlation (a gate-off high-gain plugin has an almost flat envelope,
    # so envelope corr reads ~0.3 even on the same take).
    a0, b0 = pl[: sr * 30], qc[: sr * 30]
    cc0 = signal.correlate(b0, a0, "full", method="fft")
    k = np.argmax(np.abs(cc0))
    r_wave = cc0[k] / np.sqrt((a0 * a0).sum() * (b0 * b0).sum())
    same_take = abs(r_wave) >= 0.4
    polarity = "inverted" if r_wave < 0 else "normal"
    print(f"waveform xcorr peak {r_wave:+.2f} -> "
          f"{'SAME take' if same_take else 'NOT confidently the same take'}, polarity {polarity}")
    if not same_take:
        print("  !! do not report band deltas / null depth from different takes")

    # --- trim to active region, align by xcorr lag
    edb_p, edb_q = envelope_db(pl, sr), envelope_db(qc, sr)
    hop = int(HOP_S * sr)
    act = (edb_p > -60) & (edb_q > -60)
    if not act.any():
        sys.exit("no overlapping active region above -60 dBFS; wrong files?")
    i0 = np.argmax(act) * hop
    i1 = (len(act) - np.argmax(act[::-1])) * hop
    a, b = pl[i0:i1], qc[i0:i1]
    seg = slice(0, min(len(a), sr * 20))
    cc = signal.correlate(b[seg], a[seg], mode="full", method="fft")
    lag = int(np.argmax(np.abs(cc)) - (len(a[seg]) - 1))
    print(f"active region {i0 / sr:.1f}-{i1 / sr:.1f}s, lag qc-vs-plugin = {lag} samples ({lag / sr * 1000:.2f} ms)")
    if lag > 0:
        a, b = a[:-lag], b[lag:]
    elif lag < 0:
        a, b = a[-lag:], b[:lag]
    m = min(len(a), len(b))
    a, b = a[:m], b[:m]

    # --- loudness / peak (difference = capture Volume makeup or QC-track Utility)
    meter = pyln.Meter(sr)
    L_p, L_q = meter.integrated_loudness(a), meter.integrated_loudness(b)
    pk_p, pk_q = 20 * np.log10(np.abs(a).max()), 20 * np.log10(np.abs(b).max())
    print(f"plugin {L_p:.1f} LUFS peak {pk_p:.1f} | qc {L_q:.1f} LUFS peak {pk_q:.1f} | offset {L_q - L_p:+.1f} dB")

    # --- spectra (Welch), 1/6-oct smoothed, normalised at 500 Hz-2 kHz
    f, Pp = signal.welch(a, sr, nperseg=8192)
    _, Pq = signal.welch(b, sr, nperseg=8192)
    Sp, Sq = sixth_oct_smooth(Pp, f), sixth_oct_smooth(Pq, f)
    ref = (f >= 500) & (f <= 2000)
    dp = 10 * np.log10(Sp) - 10 * np.log10(Sp[ref].mean())
    dq = 10 * np.log10(Sq) - 10 * np.log10(Sq[ref].mean())

    print("band        plugin     qc    delta(qc-plugin)")
    band_rows = []
    for lo, hi in BANDS:
        s = (f >= lo) & (f < hi)
        p_ = 10 * np.log10(Pp[s].mean() / Pp[ref].mean())
        q_ = 10 * np.log10(Pq[s].mean() / Pq[ref].mean())
        band_rows.append((lo, hi, p_, q_, q_ - p_))
        print(f"{lo:5d}-{hi:<5d} {p_:6.1f} {q_:6.1f}   {q_ - p_:+5.1f}")

    # --- per-band coherence (only chase a delta with EQ where this is > ~0.8)
    fc_, Cxy = signal.coherence(a, b, sr, nperseg=4096)
    print("coherence per band:")
    for lo, hi in BANDS:
        s = (fc_ >= lo) & (fc_ < hi)
        print(f"{lo:5d}-{hi:<5d} {Cxy[s].mean():.2f}")

    # --- null depth: signed gain match, then best-fit 512-tap linear EQ (Wiener)
    g = (a * b).sum() / (a * a).sum()
    null_gain = 10 * np.log10(((b - g * a) ** 2).mean() / (b * b).mean())
    nfft = 4096
    _, Sab = signal.csd(a, b, sr, nperseg=nfft)
    _, Saa = signal.welch(a, sr, nperseg=nfft)
    H = Sab / (Saa + 1e-15)
    h = np.roll(np.fft.irfft(H), nfft // 2)[nfft // 2 - 256: nfft // 2 + 256]
    a_eq = signal.fftconvolve(a, h, mode="full")[256: 256 + len(a)]
    null_eq = 10 * np.log10(((b - a_eq) ** 2).mean() / (b * b).mean())
    print(f"null after gain match: {null_gain:.1f} dB ; after best-fit linear EQ (512 taps): {null_eq:.1f} dB")
    print("(-1.5 to -2.5 dB is NORMAL for high-gain; residual is drive character)")

    # --- plot: spectra + coherence on top, envelopes below
    fig, ax = plt.subplots(2, 1, figsize=(14, 12))
    ax[0].semilogx(f, dp, label=f"Plugin post-FX   {L_p:.1f} LUFS, peak {pk_p:.1f} dBFS", color="#2f6fd6", lw=2)
    ax[0].semilogx(f, dq, label=f"QC capture (USB Wet 3/4)   {L_q:.1f} LUFS, peak {pk_q:.1f} dBFS", color="#2aa876", lw=2)
    ax[0].set_xlim(40, 20000)
    ax[0].set_ylim(-60, 20)
    ax[0].grid(alpha=0.3, which="both")
    ax[0].set_xticks([50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000])
    ax[0].set_xticklabels(["50", "100", "200", "500", "1k", "2k", "5k", "10k", "20k"])
    ax[0].set_ylabel("dB relative to 500 Hz–2 kHz mean")
    ax[0].set_xlabel("Hz")
    label = f"{args.label} — " if args.label else ""
    ax[0].set_title(f"{label}long-term spectra, 1/6-oct smoothed — SAME performance "
                    f"(waveform xcorr peak {r_wave:+.2f}, polarity {polarity})")
    ax[0].legend(loc="lower left")
    ax2 = ax[0].twinx()
    ax2.semilogx(fc_, Cxy, color="#999", lw=1, alpha=0.7)
    ax2.set_ylim(0, 1)
    ax2.set_ylabel("coherence (grey)")
    for lo, hi, _, _, d in band_rows:
        ax[0].annotate(f"{d:+.1f}", xy=(np.sqrt(lo * hi), 17), ha="center", fontsize=9, color="#a33")

    edb_d = envelope_db(di, sr)
    tt = np.arange(len(edb_p)) * HOP_S
    ax[1].plot(tt, edb_p, color="#2f6fd6", label="Plugin post-FX")
    ax[1].plot(np.arange(len(edb_q)) * HOP_S, edb_q, color="#2aa876", label="QC (USB Wet 3/4)")
    ax[1].plot(np.arange(len(edb_d)) * HOP_S, edb_d, color="#444", label="DI (USB Dry Input 1)")
    ax[1].set_ylim(-110, 0)
    ax[1].set_xlabel("seconds")
    ax[1].set_ylabel("RMS dBFS (10 ms)")
    ax[1].grid(alpha=0.3)
    ax[1].set_title(f"Envelopes — LUFS offset QC−plugin {L_q - L_p:+.1f} dB; "
                    f"null after gain match {null_gain:.1f} dB, after best-fit linear EQ {null_eq:.1f} dB")
    ax[1].legend(loc="lower right")
    plt.tight_layout()

    out = Path(args.out_dir) / datetime.datetime.now().strftime("null-test-%Y-%m-%d-%H%M.png")
    plt.savefig(out, dpi=110)
    print(f"plot: {out}")


if __name__ == "__main__":
    main()
