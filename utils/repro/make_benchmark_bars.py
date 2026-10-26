# -*- coding: utf-8 -*-
"""Small-scale benchmark bars (4 nodes, 400 synthetic pods): run time, total
CPU, peak memory and unscheduled pods for the six simulators and vanilla
Kubernetes. Bars are the mean over all runs of all given sessions; the error
bars span the min-max of the individual runs. Log y for the cost metrics.

Usage (from the repository root):
  python3 utils/repro/make_benchmark_bars.py --out bars.png \
      --session june=results-repro/benchmark-all \
      --session oct=results-repro/benchmark-spoofing-20261022
  python3 utils/repro/make_benchmark_bars.py --results results-repro/benchmark-all --out bars.png
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sessions import load_sessions, pooled  # noqa: E402

ORDER = ["kcs", "opensim", "kwok", "kube-sched", "kubemark", "simkube", "vanilla"]
LABEL = {"kcs": "kcs", "opensim": "OpenSimulator", "kwok": "KWOK", "kube-sched": "KSS",
         "kubemark": "Kubemark", "simkube": "SimKube", "vanilla": "vanilla"}
PANELS = [("Run time (s)", "run_time", True), ("Total CPU time (s)", "total_cpu_seconds", True),
          ("Peak memory (GB)", "memory_peak_gb", True), ("Unscheduled pods", "unscheduled_pods", False)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", action="append", default=[])
    ap.add_argument("--results")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    specs = a.session + ([a.results] if a.results else [])
    data = pooled(load_sessions(specs))
    sims = [s for s in ORDER if s in data]
    colors = plt.cm.tab10(range(len(sims)))
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for ax, (title, key, logy) in zip(axes.flat, PANELS):
        means, los, his = [], [], []
        for s in sims:
            vals = [r[key] for runs in data[s].values() for r in runs]
            means.append(sum(vals) / len(vals))
            los.append(min(vals))
            his.append(max(vals))
        floor = 0.01 if logy else None
        disp = [max(m, floor) for m in means] if logy else means
        lo = [max(l, floor) for l in los] if logy else los
        hi = [max(h, floor) for h in his] if logy else his
        err = [[d - l for d, l in zip(disp, lo)], [h - d for d, h in zip(disp, hi)]]
        bars = ax.bar([LABEL[s] for s in sims], disp, color=colors, yerr=err, capsize=3,
                      error_kw={"elinewidth": 0.8})
        if logy:
            ax.set_yscale("log")
        ax.set_title(title, fontsize=11)
        ax.tick_params(axis="x", rotation=40, labelsize=8)
        for lbl in ax.get_xticklabels():
            lbl.set_ha("right")
        ax.grid(True, axis="y", ls=":", alpha=0.5)
        for b, m, h in zip(bars, means, hi):
            ax.text(b.get_x() + b.get_width() / 2, max(h, floor or 0),
                    (f"{m:.0f}" if m >= 1 else f"{m:.2f}"), ha="center", va="bottom", fontsize=7)
    n = {s: sum(len(v) for v in data[s].values()) for s in sims}
    fig.suptitle("Small-scale benchmark (4 nodes, 400 pods): simulators vs. vanilla Kubernetes",
                 fontsize=12)
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(a.out, dpi=150)
    print("wrote", a.out, "| runs:", n)


if __name__ == "__main__":
    main()
