# -*- coding: utf-8 -*-
"""Summary of the kcs check of 2026-11-09 (results-repro/kcs-check-20261109).

Three kcs configurations, three runs each, on the host of the cost sweep:
  A  published: 60-s pods, GPU counts kept, the run ends when every pod has finished
  C  as A without GPU counts
  B  placement only: no GPU counts, pods never finish, stop at a 120-s horizon
For every size it prints the mean run time, CPU time and peak memory of each
configuration, the share of pods left unscheduled (min-max over runs), and the
cost of C and B relative to A on the points above the resolution floor (5 s, 0.1 GB).

Usage (from the repository root):
  python3 utils/repro/kcs_check_summary.py results-repro/kcs-check-20261109 [--dataset big]
"""
import argparse
import csv
import os
import statistics as st

CONFIGS = [("A", "A-published"), ("C", "C-nogpu"), ("B", "B-placement")]
COST = [("run_time", "run s", 5), ("total_cpu_seconds", "cpu s", 5), ("memory_peak_gb", "mem GB", 0.1)]


def read(path):
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="|"):
            out.setdefault(int(r["node_count"]), []).append(
                {k: float(v) for k, v in r.items() if v not in ("", None)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--dataset", default="big")
    a = ap.parse_args()
    data = {c: read(os.path.join(a.base, f"{d}-{a.dataset}", "kcs.csv")) for c, d in CONFIGS}
    sizes = sorted(data["A"])
    print(f"kcs check, dataset {a.dataset}: mean of 3 runs; unscheduled share min-max over runs")
    print("nodes  pods  " + "  ".join(f"{c}:{lab:>7s}" for c, _ in CONFIGS for _, lab, _ in COST)
          + "  " + "  ".join(f"{c}:unsched" for c, _ in CONFIGS))
    ratios = {(c, k): [] for c in ("C", "B") for k, _, _ in COST}
    shares = {c: [] for c, _ in CONFIGS}
    for n in sizes:
        pods = data["A"][n][0]["pod_count"]
        cells = []
        for c, _ in CONFIGS:
            for k, _, _ in COST:
                cells.append(f"{st.mean(r[k] for r in data[c][n]):9.2f}")
        us = []
        for c, _ in CONFIGS:
            sh = [r["unscheduled_pods"] / r["pod_count"] for r in data[c][n]]
            shares[c] += sh
            us.append(f"{100 * min(sh):5.1f}-{100 * max(sh):5.1f}%")
        print(f"{n:5d} {int(pods):5d}  " + "  ".join(cells) + "  " + "  ".join(us))
        for c in ("C", "B"):
            for k, _, floor in COST:
                ma = st.mean(r[k] for r in data["A"][n])
                mc = st.mean(r[k] for r in data[c][n])
                if ma >= floor and mc >= floor:
                    ratios[(c, k)].append(mc / ma)
    print()
    for c in ("C", "B"):
        for k, lab, _ in COST:
            v = ratios[(c, k)]
            print(f"{c}/A {lab:7s}: " + (f"{min(v):.2f}-{max(v):.2f} over {len(v)} sizes" if v else "no point above the floor"))
    for c, _ in CONFIGS:
        print(f"{c}: unscheduled share over all runs {100 * min(shares[c]):.1f}-{100 * max(shares[c]):.1f}%")


if __name__ == "__main__":
    main()
