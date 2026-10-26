# -*- coding: utf-8 -*-
"""Load result CSVs grouped into sessions (shared by the paper scripts).

A session is one or more result folders run on the same host in one campaign;
each simulator must appear in only one folder of a session. Specify sessions
as  NAME=DIR[,DIR...]  e.g.
  june=results-repro/big-all
  oct=results-repro/big-spoofing-20261022,results-repro/big-spoofing-20261024
Only the CSVs directly in each folder are read (not subfolders such as
discarded/). CSVs are pipe-delimited with the kube-run.sh schema.
"""
import csv
import glob
import os
from collections import defaultdict

METRICS = ["run_time", "total_cpu_seconds", "user_cpu_seconds", "system_cpu_seconds",
           "memory_peak_gb", "unscheduled_pods", "pod_count"]


def parse_spec(spec):
    name, _, dirs = spec.partition("=")
    if not dirs:
        name, dirs = os.path.basename(spec.rstrip("/\\")), spec
    return name, [d for d in dirs.split(",") if d]


def load_session(dirs):
    """sim -> node_count -> list of runs (dict metric -> float)."""
    data, seen = defaultdict(lambda: defaultdict(list)), {}
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.csv"))):
            sim = os.path.splitext(os.path.basename(path))[0]
            if sim in seen:
                raise SystemExit(f"{sim} appears in both {seen[sim]} and {d}")
            seen[sim] = d
            with open(path, encoding="utf-8") as f:
                for r in csv.DictReader(f, delimiter="|"):
                    try:
                        n = int(float(r["node_count"]))
                        run = {m: float(r[m]) for m in METRICS}
                    except (KeyError, ValueError, TypeError):
                        continue
                    data[sim][n].append(run)
    return data


def load_sessions(specs):
    """[(name, data)] in the given order."""
    return [(name, load_session(dirs)) for name, dirs in map(parse_spec, specs)]


def pooled(sessions):
    """sim -> node_count -> runs of all sessions."""
    out = defaultdict(lambda: defaultdict(list))
    for _, data in sessions:
        for sim, by_n in data.items():
            for n, runs in by_n.items():
                out[sim][n].extend(runs)
    return out
