#!/usr/bin/env python3
"""Per-pod record of a run (pods.csv), from the Kubernetes API of any tool.

One row per pod: where it was placed, when it was created and scheduled, and its
requests. It works for every tool that exposes a Kubernetes API (KWOK,
kube-scheduler-simulator, SimKube, Kubemark, vanilla and the real clusters), so
the fidelity comparison reads the same format for all of them.

Times are seconds relative to the first pod creation of the run (t = 0).
- t_create: metadata.creationTimestamp (1 s resolution).
- t_scheduled: eventTime of the scheduler's `Scheduled` event (events.k8s.io/v1,
  microsecond resolution); if there is none, the PodScheduled condition (1 s).
  Column t_scheduled_source says which one was used.
- t_start: the container's running startedAt (real clusters only; empty if the
  tool does not run containers).

Usage:
  python3 utils/collect_pods.py --namespace paib-gpu --out pods.csv \
      --tool kwok --platform sim --scale 10 --rep 1 --workload alibaba \
      [--context CTX] [--append]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scale_base import cpu_millicores, mem_bytes  # noqa: E402

COLUMNS = ["tool", "platform", "scale", "rep", "workload", "pod", "node",
           "t_create", "t_scheduled", "t_scheduled_source", "t_start", "status",
           "cpu_m", "mem_kib"]


def parse_time(value: str | None) -> float | None:
    """RFC 3339 timestamp (with or without fraction) -> POSIX seconds."""
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    if "." in text:
        head, rest = text.split(".", 1)
        frac, sign, tz = rest.partition("+") if "+" in rest else rest.partition("-")
        text = f"{head}.{frac[:6].ljust(6, '0')}{sign}{tz}"
    return datetime.fromisoformat(text).astimezone(timezone.utc).timestamp()


def kubectl_json(args: list[str], context: str | None) -> dict:
    cmd = ["kubectl"] + (["--context", context] if context else []) + args + ["-o", "json"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {res.stderr.strip()}")
    return json.loads(res.stdout)


def scheduled_events(events: dict) -> dict[str, float]:
    """Pod name -> eventTime of its first `Scheduled` event."""
    out: dict[str, float] = {}
    for ev in events.get("items", []):
        if ev.get("reason") != "Scheduled":
            continue
        obj = ev.get("regarding") or ev.get("involvedObject") or {}
        if obj.get("kind") != "Pod":
            continue
        t = parse_time(ev.get("eventTime")) or parse_time(
            (ev.get("deprecatedLastTimestamp") or ev.get("lastTimestamp")))
        if t is not None and (obj["name"] not in out or t < out[obj["name"]]):
            out[obj["name"]] = t
    return out


def pod_rows(pods: dict, events: dict, meta: dict) -> list[dict]:
    sched = scheduled_events(events)
    items = pods.get("items", [])
    created = [parse_time(p["metadata"].get("creationTimestamp")) for p in items]
    t0 = min((c for c in created if c is not None), default=0.0)
    rows = []
    for pod, t_create in zip(items, created):
        name = pod["metadata"]["name"]
        status = pod.get("status", {})
        if name in sched:
            t_sched, source = sched[name], "event"
        else:
            cond = next((c for c in status.get("conditions", [])
                         if c.get("type") == "PodScheduled" and c.get("status") == "True"), None)
            t_sched = parse_time(cond.get("lastTransitionTime")) if cond else None
            source = "condition" if t_sched is not None else ""
        running = [cs.get("state", {}).get("running", {}).get("startedAt")
                   for cs in status.get("containerStatuses", [])]
        starts = [parse_time(s) for s in running if s]
        cpu = mem = 0.0
        for c in pod["spec"].get("containers", []):
            req = (c.get("resources") or {}).get("requests") or {}
            cpu += cpu_millicores(req.get("cpu", 0))
            mem += mem_bytes(req.get("memory", 0)) / 1024
        rel = lambda t: "" if t is None else f"{t - t0:.6f}"  # noqa: E731
        rows.append({**meta, "pod": name, "node": pod["spec"].get("nodeName", ""),
                     "t_create": rel(t_create), "t_scheduled": rel(t_sched),
                     "t_scheduled_source": source,
                     "t_start": rel(max(starts)) if starts else "",
                     "status": status.get("phase", ""),
                     "cpu_m": f"{cpu:g}", "mem_kib": f"{mem:g}"})
    rows.sort(key=lambda r: r["pod"])
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="per-pod record of a run")
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tool", required=True)
    ap.add_argument("--platform", default="sim")
    ap.add_argument("--scale", required=True)
    ap.add_argument("--rep", required=True)
    ap.add_argument("--workload", default="alibaba")
    ap.add_argument("--context")
    ap.add_argument("--append", action="store_true", help="append to --out instead of overwriting")
    args = ap.parse_args(argv)

    pods = kubectl_json(["get", "pods", "-n", args.namespace], args.context)
    try:
        events = kubectl_json(["get", "events.events.k8s.io", "-n", args.namespace], args.context)
    except RuntimeError:
        events = kubectl_json(["get", "events", "-n", args.namespace], args.context)
    meta = {"tool": args.tool, "platform": args.platform, "scale": args.scale,
            "rep": args.rep, "workload": args.workload}
    rows = pod_rows(pods, events, meta)

    new_file = not (args.append and os.path.exists(args.out))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w" if new_file else "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)
    bound = sum(1 for r in rows if r["node"])
    from_events = sum(1 for r in rows if r["t_scheduled_source"] == "event")
    print(f"{len(rows)} pods ({bound} bound, {from_events} with Scheduled events) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
