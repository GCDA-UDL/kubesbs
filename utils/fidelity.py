#!/usr/bin/env python3
"""Pairwise fidelity metrics between runs, from their per-pod records (pods.csv).

Every pair of runs at the same scale (simulator vs. real, real vs. real, ...) is
compared on the same pods and the same nodes:

- agreement: share of pods with the same outcome in both runs (same node, or
  unscheduled in both). The kube-scheduler breaks ties at random, so two real
  runs do not reach 1 either: compare a simulator with that noise floor.
- agreement_equiv: the same, once the nodes of identical allocatable (which the
  scheduler cannot tell apart) are matched between the two runs so that as many
  pods as possible agree (optimal assignment per class of identical nodes).
- unsched_a, unsched_b: pods left unscheduled in each run.
- w1_cpu, w1_mem: Wasserstein-1 distance between the per-node occupancy
  (requested / allocatable) of the two runs, over the same set of nodes.
- latency_p50_a/b, latency_p95_a/b: t_scheduled - t_create (s) of bound pods,
  when the run has them.

Usage:
  python3 utils/fidelity.py --pods 'results/fidelity/pods-*.csv' \
      --nodes-dir data/fidelity/vanilla --out results/fidelity/pairs.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import itertools
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scale_base import cpu_millicores, mem_bytes  # noqa: E402

PAIR_COLUMNS = ["scale", "a_tool", "a_platform", "a_rep", "b_tool", "b_platform", "b_rep",
                "pods", "agreement", "agreement_equiv", "unsched_a", "unsched_b", "w1_cpu", "w1_mem",
                "latency_p50_a", "latency_p50_b", "latency_p95_a", "latency_p95_b"]


def read_runs(paths: list[str]) -> dict[tuple, list[dict]]:
    """(tool, platform, scale, rep) -> rows of that run."""
    runs: dict[tuple, list[dict]] = {}
    for path in paths:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                key = (row["tool"], row["platform"], int(row["scale"]), int(row["rep"]))
                runs.setdefault(key, []).append(row)
    return runs


def node_capacity(nodes_file: str) -> dict[str, tuple[float, float]]:
    """Node name -> (allocatable cpu m, allocatable memory KiB)."""
    with open(nodes_file, encoding="utf-8") as fh:
        nodes = [d for d in yaml.safe_load_all(fh) if d and d.get("kind") == "Node"]
    return {n["metadata"]["name"]: (cpu_millicores(n["status"]["allocatable"]["cpu"]),
                                    mem_bytes(n["status"]["allocatable"]["memory"]) / 1024)
            for n in nodes}


def occupancy(rows: list[dict], capacity: dict) -> tuple[list[float], list[float]]:
    used = {name: [0.0, 0.0] for name in capacity}
    for r in rows:
        if r["node"] in used:
            used[r["node"]][0] += float(r["cpu_m"] or 0)
            used[r["node"]][1] += float(r["mem_kib"] or 0)
    names = sorted(capacity)
    return ([used[n][0] / capacity[n][0] for n in names],
            [used[n][1] / capacity[n][1] for n in names])


def wasserstein_1d(a: list[float], b: list[float]) -> float:
    """W1 between two equally sized samples: mean gap of the sorted values."""
    if len(a) != len(b) or not a:
        raise ValueError("W1 needs two non-empty samples of the same size")
    return sum(abs(x - y) for x, y in zip(sorted(a), sorted(b))) / len(a)


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def latencies(rows: list[dict]) -> list[float]:
    return [float(r["t_scheduled"]) - float(r["t_create"]) for r in rows
            if r["node"] and r["t_scheduled"] and r["t_create"]]


def agreement_up_to_identical_nodes(node_a: dict, node_b: dict, capacity: dict) -> float:
    """Pod agreement after the best matching of identical nodes between the runs."""
    from scipy.optimize import linear_sum_assignment

    classes: dict[tuple, list[str]] = {}
    for name, cap in capacity.items():
        classes.setdefault(cap, []).append(name)
    agree = sum(1 for p in node_a if not node_a[p] and not node_b[p])
    for names in classes.values():
        index = {n: i for i, n in enumerate(names)}
        counts = [[0] * len(names) for _ in names]
        for pod, na in node_a.items():
            nb = node_b[pod]
            if na in index and nb in index:
                counts[index[na]][index[nb]] += 1
        rows, cols = linear_sum_assignment(counts, maximize=True)
        agree += sum(counts[r][c] for r, c in zip(rows, cols))
    return agree / len(node_a)


def compare(a: list[dict], b: list[dict], capacity: dict) -> dict:
    node_a = {r["pod"]: r["node"] for r in a}
    node_b = {r["pod"]: r["node"] for r in b}
    if set(node_a) != set(node_b):
        raise ValueError(f"runs have different pods ({len(node_a)} vs {len(node_b)})")
    same = sum(1 for p in node_a if node_a[p] == node_b[p])
    cpu_a, mem_a = occupancy(a, capacity)
    cpu_b, mem_b = occupancy(b, capacity)
    lat_a, lat_b = latencies(a), latencies(b)
    fmt = lambda v: "" if v is None else f"{v:.6f}"  # noqa: E731
    return {"pods": len(node_a), "agreement": f"{same / len(node_a):.6f}",
            "agreement_equiv": f"{agreement_up_to_identical_nodes(node_a, node_b, capacity):.6f}",
            "unsched_a": sum(1 for n in node_a.values() if not n),
            "unsched_b": sum(1 for n in node_b.values() if not n),
            "w1_cpu": f"{wasserstein_1d(cpu_a, cpu_b):.6f}",
            "w1_mem": f"{wasserstein_1d(mem_a, mem_b):.6f}",
            "latency_p50_a": fmt(quantile(lat_a, 0.5)), "latency_p50_b": fmt(quantile(lat_b, 0.5)),
            "latency_p95_a": fmt(quantile(lat_a, 0.95)), "latency_p95_b": fmt(quantile(lat_b, 0.95))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="pairwise fidelity metrics between runs")
    ap.add_argument("--pods", required=True, help="glob of pods-*.csv files")
    ap.add_argument("--nodes-dir", required=True, help="folder with the nodes-N.yaml of the dataset")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    runs = read_runs(sorted(glob.glob(args.pods)))
    if not runs:
        raise SystemExit(f"no rows in {args.pods}")
    rows_out = []
    for scale in sorted({k[2] for k in runs}):
        capacity = node_capacity(os.path.join(args.nodes_dir, f"nodes-{scale}.yaml"))
        keys = sorted(k for k in runs if k[2] == scale)
        for ka, kb in itertools.combinations(keys, 2):
            metrics = compare(runs[ka], runs[kb], capacity)
            rows_out.append({"scale": scale, "a_tool": ka[0], "a_platform": ka[1], "a_rep": ka[3],
                             "b_tool": kb[0], "b_platform": kb[1], "b_rep": kb[3], **metrics})
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=PAIR_COLUMNS)
        writer.writeheader()
        writer.writerows(rows_out)
    print(f"{len(runs)} runs, {len(rows_out)} pairs -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
