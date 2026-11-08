#!/usr/bin/env python3
"""CPU load and reported latency of a plugin chain, measured offline.

Loads the chain the way render_chain.py does, waits 2 s for it to settle,
then processes the DI in 128-sample blocks (the tracking buffer) and reports
the chain's average load as a percentage of one core, the worst block
against its real-time budget, and each plugin's reported latency. Use it to
check a chain is cheap enough to track through before committing to it.

Usage:
  uv run --with pedalboard --with soundfile --with numpy python -I chain_cost.py \\
    DI.wav "/Library/Audio/Plug-Ins/VST3/<Plugin>.vst3=<preset>.xml" [...]

Run once per candidate chain; the numbers are for this machine only.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from render_chain import load_chain  # noqa: E402

BLOCK = 128
SETTLE = 2.0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('di')
    ap.add_argument('chain', nargs='+', metavar='PLUGIN.vst3[=PRESET.xml]')
    a = ap.parse_args()

    x, sr = sf.read(a.di, always_2d=True)
    x = x.T
    if x.shape[0] == 1:
        x = np.vstack([x, x])
    x = x.astype(np.float32)
    dur = x.shape[1] / sr

    plugins = [p for p, _ in load_chain(a.chain)]
    time.sleep(SETTLE)
    lat = [getattr(p, 'reported_latency_samples', None) for p in plugins]
    for p in plugins:
        p.reset()
    bs = BLOCK
    worst = 0.0
    t0 = time.perf_counter()
    for i in range(0, x.shape[1] - bs, bs):
        tb = time.perf_counter()
        y = x[:, i:i + bs]
        for p in plugins:
            y = p.process(y, sr, buffer_size=bs, reset=False)
        worst = max(worst, time.perf_counter() - tb)
    elapsed = time.perf_counter() - t0
    total = sum(v for v in lat if v) if all(v is not None for v in lat) else None
    print(f"load {100 * elapsed / dur:.1f}% of one core | worst block {1000 * worst:.2f} ms "
          f"of {1000 * bs / sr:.2f} ms budget | reported latency {lat} samples"
          + (f" (total {total}, {1000 * total / sr:.1f} ms @ {sr} Hz)" if total is not None else ""))
    return 0


if __name__ == '__main__':
    sys.exit(main())
