# -*- coding: utf-8 -*-
"""Fidelity table, figure and summary for the paper, from per-pod records.

Runs are grouped by the platform given on the command line (the label stored in
pods.csv is ignored), so runs of several hosts can be told apart:

  --real NAME=GLOB[,GLOB]   a real cluster (one per host)
  --sim  NAME=GLOB[,GLOB]   a simulator

Every pair of runs at the same scale is compared with utils/fidelity.py
(agreement up to identical nodes, Wasserstein-1 distance of the per-node
occupancy) and grouped as: real vs. real on the same host, real vs. real across
hosts, and simulator vs. real. Outputs:

  fidelity.tex                        LaTeX table (placement)
  fidelity_latency_vs_node_count.png  scheduling latency p50 / p99 per platform
  fidelity-summary.txt                the numbers quoted in the text
  fidelity-pairs.csv                  every pair with its metrics

Usage (from the repository root):
  bash utils/repro/make_fidelity_dataset.sh       # data/fidelity/vanilla
  F=results-repro/fidelity-20261029
  python3 utils/repro/fidelity_report.py --out fidelity-out \
      --nodes-dir data/fidelity/vanilla \
      --real spoofing02="$F/spoofing02/pods-real-*.csv" \
      --real spoofing-gcd="$F/spoofing-gcd/pods-real-*.csv" \
      --sim KWOK="$F/spoofing02/pods-kwok-*.csv"
Needs: matplotlib, scipy, PyYAML.
"""
import argparse
import csv
import glob
import itertools
import os
import statistics as st
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import fidelity  # noqa: E402


def load(specs, kind):
    """NAME=GLOB[,GLOB] -> {(kind, NAME, scale, rep): rows}."""
    runs = {}
    for spec in specs:
        name, _, globs = spec.partition("=")
        paths = sorted(p for g in globs.split(",") for p in glob.glob(g) if not p.endswith(".watch.csv"))
        if not paths:
            sys.exit(f"{spec}: no pods CSV matched")
        for (_, _, scale, rep), rows in fidelity.read_runs(paths).items():
            runs[(kind, name, scale, rep)] = rows
    return runs


def group(ka, kb):
    if ka[0] == "real" and kb[0] == "real":
        return "real-same-host" if ka[1] == kb[1] else "real-across-hosts"
    if {ka[0], kb[0]} == {"real", "sim"}:
        sim = ka if ka[0] == "sim" else kb
        return f"{sim[1]}-vs-real"
    if ka[0] == "sim" and kb[0] == "sim" and ka[1] == kb[1]:
        return f"{ka[1]}-same-tool"
    return None


def stats(vals):
    return st.mean(vals), min(vals), max(vals)


def run_latency_ms(rows):
    lat = [1000 * v for v in fidelity.latencies(rows)]
    return {q: fidelity.quantile(lat, q) for q in (0.5, 0.95, 0.99)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="append", default=[], help="NAME=GLOB[,GLOB]")
    ap.add_argument("--sim", action="append", default=[], help="NAME=GLOB[,GLOB]")
    ap.add_argument("--nodes-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not a.real:
        sys.exit("give at least one --real")
    runs = {**load(a.real, "real"), **load(a.sim, "sim")}
    os.makedirs(a.out, exist_ok=True)
    o = lambda f: os.path.join(a.out, f)  # noqa: E731
    scales = sorted({k[2] for k in runs})
    sims = [s.partition("=")[0] for s in a.sim]
    reals = [s.partition("=")[0] for s in a.real]

    # Pairs.
    pairs = []
    for scale in scales:
        capacity = fidelity.node_capacity(os.path.join(a.nodes_dir, f"nodes-{scale}.yaml"))
        keys = sorted(k for k in runs if k[2] == scale)
        for ka, kb in itertools.combinations(keys, 2):
            g = group(ka, kb)
            if g is None:
                continue
            m = fidelity.compare(runs[ka], runs[kb], capacity)
            pairs.append({"scale": scale, "group": g, "a": f"{ka[1]}#{ka[3]}", "b": f"{kb[1]}#{kb[3]}",
                          **{k: m[k] for k in ("pods", "agreement", "agreement_equiv", "unsched_a",
                                               "unsched_b", "w1_cpu", "w1_mem")}})
    with open(o("fidelity-pairs.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pairs[0]))
        w.writeheader()
        w.writerows(pairs)

    def metric(scale, g, key):
        return [float(p[key]) for p in pairs if p["scale"] == scale and p["group"] == g]

    unsched = {}
    for (kind, name, scale, rep), rows in runs.items():
        unsched.setdefault((kind, scale), []).append(sum(1 for r in rows if not r["node"]))
    pods = {k[2]: len(v) for k, v in runs.items()}

    # Table (placement): one simulator column group per --sim.
    sim_groups = [f"{s}-vs-real" for s in sims]
    groups = ["real-same-host", "real-across-hosts"] + sim_groups
    heads = ["Same", "Across"] + sims  # caption: same host / across hosts / simulator vs. real

    def rng(lo, hi, fmt):
        return fmt.format(lo) if fmt.format(lo) == fmt.format(hi) else f"{fmt.format(lo)}--{fmt.format(hi)}"

    lines = ["% generated by utils/repro/fidelity_report.py",
             "\\begin{tabular}{rr" + "r" * (1 + len(sims)) + "r" * len(groups) * 2 + "}",
             "\\toprule",
             f" & & \\multicolumn{{{1 + len(sims)}}}{{c}}{{Unscheduled pods}}"
             f" & \\multicolumn{{{len(groups)}}}{{c}}{{Agreement (\\%)}}"
             f" & \\multicolumn{{{len(groups)}}}{{c}}{{$W_1$ CPU occupancy (pp)}}\\\\"]
    c0 = 3
    lines.append(f"\\cmidrule(lr){{{c0}-{c0 + len(sims)}}}"
                 f"\\cmidrule(lr){{{c0 + len(sims) + 1}-{c0 + len(sims) + len(groups)}}}"
                 f"\\cmidrule(lr){{{c0 + len(sims) + len(groups) + 1}-{c0 + len(sims) + 2 * len(groups)}}}")
    lines.append("Nodes & Pods & Real & " + " & ".join(sims) + " & "
                 + " & ".join(heads) + " & " + " & ".join(heads) + "\\\\")
    lines.append("\\midrule")
    for scale in scales:
        cells = [str(scale), f"{pods[scale]:,}"]
        u_real = unsched[("real", scale)]
        cells.append(rng(min(u_real), max(u_real), "{:d}"))
        for s in sims:
            u = [sum(1 for r in rows if not r["node"]) for k, rows in runs.items()
                 if k[0] == "sim" and k[1] == s and k[2] == scale]
            cells.append(rng(min(u), max(u), "{:d}"))
        for key, fmt in (("agreement_equiv", "{:.1f}"), ("w1_cpu", "{:.2f}")):
            for g in groups:
                vals = metric(scale, g, key)
                cells.append(fmt.format(100 * st.mean(vals)) if vals else "--")
        lines.append(" & ".join(cells) + "\\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    with open(o("fidelity.tex"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # Latency per run, then per platform and scale.
    lat = {}
    for (kind, name, scale, rep), rows in runs.items():
        lat.setdefault((name, scale), []).append(run_latency_ms(rows))
    platforms = [f"{n}" for n in reals] + sims
    fig, axes = plt.subplots(1, 2, figsize=(7, 3.0), sharey=True)
    for ax, q, title in ((axes[0], 0.5, "Median (p50)"), (axes[1], 0.99, "Tail (p99)")):
        for name in platforms:
            ns = [s for s in scales if (name, s) in lat]
            vals = [[r[q] for r in lat[(name, s)]] for s in ns]
            label = f"Real, {name}" if name in reals else name
            line, = ax.plot(ns, [st.mean(v) for v in vals], marker="o", ms=3, label=label,
                            ls="-" if name in reals else "--")
            ax.fill_between(ns, [min(v) for v in vals], [max(v) for v in vals],
                            color=line.get_color(), alpha=0.18, linewidth=0)
        ax.set_yscale("log")
        ax.set_xlabel("Node count")
        ax.set_title(title, fontsize=10)
        ax.grid(True, which="both", ls=":", alpha=0.5)
    axes[0].set_ylabel("Scheduling latency (ms, log)")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(o("fidelity_latency_vs_node_count.png"), dpi=150)
    plt.close(fig)

    # Summary.
    out = [f"runs: {len(runs)} ({', '.join(f'{n}' for n in platforms)}); pairs: {len(pairs)}"]
    for scale in scales:
        out.append(f"\n== {scale} nodes, {pods[scale]} pods")
        for kind, name in [("real", n) for n in reals] + [("sim", s) for s in sims]:
            u = [sum(1 for r in rows if not r["node"]) for k, rows in runs.items()
                 if k[0] == kind and k[1] == name and k[2] == scale]
            ls = lat[(name, scale)]
            q = {k: stats([r[k] for r in ls]) for k in (0.5, 0.95, 0.99)}
            out.append(f"  {name:14s} unscheduled {u}  latency ms p50 {q[0.5][0]:.1f} "
                       f"({q[0.5][1]:.1f}-{q[0.5][2]:.1f})  p95 {q[0.95][0]:.1f}  "
                       f"p99 {q[0.99][0]:.1f} ({q[0.99][1]:.1f}-{q[0.99][2]:.1f})")
        for g in sorted({p["group"] for p in pairs if p["scale"] == scale}):
            parts = []
            for key, scale_by, fmt in (("agreement", 100, "{:.1f}%"), ("agreement_equiv", 100, "{:.1f}%"),
                                       ("w1_cpu", 100, "{:.2f}pp"), ("w1_mem", 100, "{:.2f}pp")):
                mean, lo, hi = stats(metric(scale, g, key))
                parts.append(f"{key} " + fmt.format(scale_by * mean)
                             + f" [{fmt.format(scale_by * lo)}, {fmt.format(scale_by * hi)}]")
            out.append(f"  {g:20s} n={len(metric(scale, g, 'w1_cpu'))}  " + "  ".join(parts))
    with open(o("fidelity-summary.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("\n".join(out))
    print("wrote", ", ".join(o(f) for f in ("fidelity.tex", "fidelity_latency_vs_node_count.png",
                                             "fidelity-summary.txt", "fidelity-pairs.csv")))


if __name__ == "__main__":
    main()
