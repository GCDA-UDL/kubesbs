# -*- coding: utf-8 -*-
"""Line plots of the big sweep for the paper: mean over all runs of all given
sessions, with the min-max range of the individual runs as a shaded band.
Log y-axis for the cost metrics so kcs (~0.1 GB) and Kubemark (~20 GB) are both
legible; the scheduling success rate uses a linear axis.

Usage (from the repository root):
  python3 utils/repro/make_paper_plots.py --out figures-out \
      --session june=results-repro/big-all \
      --session oct=results-repro/big-spoofing-20261022,results-repro/big-spoofing-20261024
  # one session only (older interface):
  python3 utils/repro/make_paper_plots.py --results results-repro/big-all --out figures-out
Needs: matplotlib.
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sessions import load_sessions, pooled  # noqa: E402

LABELS = {"opensim": "OpenSimulator", "kwok": "KWOK", "kube-sched": "KSS",
          "simkube": "SimKube", "kubemark": "Kubemark", "kcs": "kcs"}
ORDER = ["kcs", "kwok", "opensim", "kube-sched", "simkube", "kubemark"]
FLOOR = {"memory_peak_gb": 0.01, "total_cpu_seconds": 0.5, "run_time": 0.5}


def series(runs_by_n, metric):
    ns, mean, lo, hi = [], [], [], []
    for n in sorted(runs_by_n):
        runs = runs_by_n[n]
        if metric == "success_rate":
            vals = [1.0 - r["unscheduled_pods"] / r["pod_count"] for r in runs if r["pod_count"] > 0]
        elif metric == "run_time":
            vals = [r[metric] for r in runs if r[metric] >= 0]  # drop -1 sentinel
        else:
            vals = [r[metric] for r in runs]
        if not vals:
            continue
        ns.append(n)
        mean.append(sum(vals) / len(vals))
        lo.append(min(vals))
        hi.append(max(vals))
    return ns, mean, lo, hi


def line_plot(data, metric, ylabel, title, out_png, logy=True):
    plt.figure(figsize=(7, 4.2))
    floor = FLOOR.get(metric, 0) if logy else None
    for sim in ORDER:
        if sim not in data:
            continue
        ns, mean, lo, hi = series(data[sim], metric)
        if floor is not None:
            mean, lo, hi = ([max(v, floor) for v in xs] for xs in (mean, lo, hi))
        line, = plt.plot(ns, mean, marker="o", ms=3, label=LABELS[sim])
        plt.fill_between(ns, lo, hi, color=line.get_color(), alpha=0.18, linewidth=0)
    if logy:
        plt.yscale("log")
    plt.xlabel("Node count")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, which="both", ls=":", alpha=0.5)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.close()
    print("wrote", out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", action="append", default=[],
                    help="NAME=DIR[,DIR...]; repeat for several sessions")
    ap.add_argument("--results", help="single result folder (same as --session DIR)")
    ap.add_argument("--out", required=True, help="output folder")
    a = ap.parse_args()
    specs = a.session + ([a.results] if a.results else [])
    if not specs:
        sys.exit("give --session or --results")
    sessions = load_sessions(specs)
    data = pooled(sessions)
    if not data:
        sys.exit("No simulator CSVs found")
    os.makedirs(a.out, exist_ok=True)
    runs = {s: sum(len(v) for v in data[s].values()) for s in data}
    print("sessions:", ", ".join(n for n, _ in sessions), "| runs per simulator:", runs)
    o = lambda f: os.path.join(a.out, f)
    line_plot(data, "memory_peak_gb", "Peak memory (GB, log)",
              "Peak memory vs. node count", o("memory_peak_gb_vs_node_count.png"))
    line_plot(data, "total_cpu_seconds", "Total CPU time (s, log)",
              "Total CPU time vs. node count", o("total_cpu_seconds_vs_node_count.png"))
    line_plot(data, "run_time", "Run time (s, log)",
              "Run time vs. node count", o("run_time_vs_node_count.png"))
    line_plot(data, "success_rate", "Scheduling success rate",
              "Scheduling success rate vs. node count",
              o("scheduling_success_rate_vs_node_count.png"), logy=False)


if __name__ == "__main__":
    main()
