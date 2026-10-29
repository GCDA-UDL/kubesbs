#!/usr/bin/env python3
"""Watch the pods of a namespace and log, with the local clock, when each one
appears and when it is first seen bound to a node.

metadata.creationTimestamp has a resolution of 1 s, too coarse for scheduling
latencies; this watcher stamps the API's watch events on arrival instead. Start it
before the pods are created (kube-run.sh does when POD_RECORDS_DIR is set) and
stop it with SIGTERM; collect_pods.py --watch reads its output.

Output CSV: pod,t_added,t_bound (POSIX seconds, local clock; t_bound empty if the
pod was never seen bound).

Usage:
  python3 utils/watch_pods.py --namespace paib-gpu --out watch.csv [--context CTX]
"""
from __future__ import annotations

import argparse
import csv
import json
import signal
import subprocess
import sys
import time


def follow(lines, clock=time.time) -> dict[str, list]:
    """Watch-event lines (one JSON object each) -> pod -> [t_added, t_bound]."""
    seen: dict[str, list] = {}
    for line in lines:
        now = clock()
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        obj = event.get("object") or {}
        name = (obj.get("metadata") or {}).get("name")
        if not name or event.get("type") == "DELETED":
            continue
        rec = seen.setdefault(name, [now, None])
        if rec[1] is None and (obj.get("spec") or {}).get("nodeName"):
            rec[1] = now
    return seen


def write(seen: dict[str, list], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["pod", "t_added", "t_bound"])
        for name in sorted(seen):
            t_added, t_bound = seen[name]
            writer.writerow([name, f"{t_added:.6f}", "" if t_bound is None else f"{t_bound:.6f}"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="timestamp pod watch events")
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--context")
    args = ap.parse_args(argv)

    cmd = ["kubectl"] + (["--context", args.context] if args.context else []) + [
        "get", "--raw", f"/api/v1/namespaces/{args.namespace}/pods?watch=1&allowWatchBookmarks=false"]
    seen: dict[str, list] = {}
    state = {"stop": False, "proc": None}

    def stop(*_):
        state["stop"] = True
        if state["proc"] is not None and state["proc"].poll() is None:
            state["proc"].terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    failures = 0
    try:
        # The API server closes a watch after a while; reopen it until stopped. A
        # reopened watch replays the existing pods as ADDED: keep the first times.
        while not state["stop"]:
            state["proc"] = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, bufsize=1)
            for name, (t_added, t_bound) in follow(state["proc"].stdout).items():
                rec = seen.setdefault(name, [t_added, t_bound])
                if rec[1] is None and t_bound is not None:
                    rec[1] = t_bound
            rc = state["proc"].wait()
            if state["stop"]:
                break
            failures = failures + 1 if rc != 0 else 0
            if failures >= 5:
                print(f"watch_pods: kubectl failed {failures} times, giving up", file=sys.stderr)
                break
            time.sleep(1 if rc != 0 else 0.1)
    finally:
        write(seen, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
