# -*- coding: utf-8 -*-
"""Split each run's measured run time into phases, from a harness log.

The run time in the CSVs (kube-run.sh: START_TIME to the end of container
tracking) covers three phases, delimited by harness log lines:

  setup      "Starting run N for M nodes"  -> "Cluster setup successful"
  workload   "Cluster setup successful"    -> "Waiting for pods to be scheduled"
  end check  "Waiting for pods to be scheduled" -> "All pods scheduled successfully" |
             "All pending pods can not be scheduled" | "No changes after ..."

The end check is the harness confirming that every pending pod has a
FailedScheduling event, one kubectl call per pending pod and pass. Simulators
with their own wait (opensim, kcs, k8ssim) only report setup.

Input: harness.log (the "[date time] [LEVEL] module: message" lines of a
run_sweep.sh run; results-repro/*/harness.log). The 1-node pre-check runs on
data/test are ignored.

Usage:
  python3 utils/repro/run_phases.py results-repro/big-spoofing-20261024/harness.log
  python3 utils/repro/run_phases.py LOG --csv out.csv     # one row per run
"""
import argparse
import csv
import re
import statistics as st
from collections import defaultdict
from datetime import datetime

LINE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] \[(\w+)\] ([\w-]+): (.*)$")
END = ("All pods scheduled successfully", "All pending pods can not be scheduled", "No changes after")


def parse(path):
    runs, cur = [], {}
    for line in open(path, encoding="utf-8", errors="replace"):
        m = LINE.match(line.rstrip("\n"))
        if not m:
            continue
        ts, _level, sim, msg = m.groups()
        t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        start = re.match(r"Starting run (\d+) for (\d+) nodes", msg)
        if start:
            run = {"sim": sim, "run": int(start.group(1)), "nodes": int(start.group(2)), "start": t}
            cur[sim] = run
            if run["nodes"] > 1:
                runs.append(run)
            continue
        run = cur.get(sim)
        if run is None:
            continue
        if msg.startswith("Cluster setup successful"):
            run.setdefault("setup_ok", t)
        elif msg.startswith("Waiting for pods to be scheduled"):
            run.setdefault("wait", t)
        elif msg.startswith(END):
            run.setdefault("end", t)
            run.setdefault("end_reason", msg.split(".")[0])
    return runs


def phases(run):
    s = lambda a, b: (run[b] - run[a]).total_seconds() if a in run and b in run else None
    return {"setup": s("start", "setup_ok"), "workload": s("setup_ok", "wait"),
            "end_check": s("wait", "end"), "total": s("start", "end")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--csv", help="write one row per run")
    a = ap.parse_args()
    runs = parse(a.log)
    rows = [r | phases(r) for r in runs]
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["sim", "nodes", "run", "setup_s", "workload_s", "end_check_s", "total_s", "end_reason"])
            for r in rows:
                w.writerow([r["sim"], r["nodes"], r["run"], r["setup"], r["workload"], r["end_check"],
                            r["total"], r.get("end_reason", "")])
    groups = defaultdict(list)
    for r in rows:
        groups[(r["sim"], r["nodes"])].append(r)
    print(f"{'sim':11s} {'nodes':>5s} {'runs':>4s} {'setup':>7s} {'workload':>9s} {'end check':>9s} "
          f"{'total':>7s} {'end check share':>15s}")
    for (sim, n), g in sorted(groups.items()):
        mean = lambda k: st.mean(v[k] for v in g if v[k] is not None) if any(v[k] is not None for v in g) else None
        su, wl, ec, tot = mean("setup"), mean("workload"), mean("end_check"), mean("total")
        f = lambda x: f"{x:7.0f}" if x is not None else "    n/a"
        share = f"{ec / tot:15.0%}" if ec is not None and tot else f"{'n/a':>15s}"
        print(f"{sim:11s} {n:5d} {len(g):4d} {f(su)} {f(wl):>9s} {f(ec):>9s} {f(tot)} {share}")


if __name__ == "__main__":
    main()
