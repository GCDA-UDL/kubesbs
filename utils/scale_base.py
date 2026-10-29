#!/usr/bin/env python3
"""Scale the base trace manifests so that every node fits on a small real machine.

The fidelity study runs the same workload on the simulators and on real clusters
(k3d on one host, one VM per node in the cloud). No real machine can advertise
the capacity of the trace nodes (up to 128 CPU and 1 TiB), so node capacities and
pod requests are divided by the same factor per resource, for every tool and
platform. The default scheduler compares requested/allocatable fractions
(NodeResourcesFit, BalancedAllocation), which this scaling preserves except for
rounding to 1 millicore and 1 KiB.

Other changes, also applied to every tool so that all of them see the same input:
- nodes keep only cpu, memory and pods (no GPU extended resources: pods request
  GPUs through annotations, which the default scheduler ignores);
- the pods allocatable of every node is set to --max-pods (the real kubelet's
  max-pods, limited by the /24 pod CIDR of each node);
- pods keep their requests but lose their limits (a scaled memory limit of a few
  MiB would get the container OOM-killed on a real node), and run --image.

Usage:
  python3 utils/scale_base.py -o utils/base-fidelity \
      [--nodes utils/base/nodes.yaml] [--pods utils/base/pods.yaml] \
      [--cpu-factor 200] [--mem-factor 512] [--max-pods 250] \
      [--image registry.k8s.io/pause:3.9]
Then generate the datasets with kube-gen.py -n <out>/nodes.yaml -p <out>/pods.yaml.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_MEM_UNITS = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40,
              "K": 10**3, "M": 10**6, "G": 10**9, "T": 10**12}


def cpu_millicores(value) -> float:
    """Kubernetes CPU quantity ('64000m', '64', 64, '0.5') -> millicores."""
    text = str(value).strip()
    if text.endswith("m"):
        return float(text[:-1])
    return float(text) * 1000


def mem_bytes(value) -> float:
    """Kubernetes memory quantity ('262144Mi', '1Gi', '1000M', 1024) -> bytes."""
    text = str(value).strip()
    for suffix in sorted(_MEM_UNITS, key=len, reverse=True):
        if text.endswith(suffix):
            return float(text[: -len(suffix)]) * _MEM_UNITS[suffix]
    return float(text)


def scale_cpu(value, factor: float) -> str:
    """Scaled CPU in millicores, at least 1m for a non-zero request."""
    mc = cpu_millicores(value)
    if mc == 0:
        return "0m"
    return f"{max(1, round(mc / factor))}m"


def scale_mem(value, factor: float) -> str:
    """Scaled memory in KiB, at least 1Ki for a non-zero request."""
    b = mem_bytes(value)
    if b == 0:
        return "0Ki"
    return f"{max(1, round(b / 1024 / factor))}Ki"


def scale_node(node: dict, cpu_factor: float, mem_factor: float, max_pods: int) -> dict:
    status = node.setdefault("status", {})
    for key in ("capacity", "allocatable"):
        src = status.get(key) or status.get("capacity") or {}
        status[key] = {
            "cpu": scale_cpu(src.get("cpu", 0), cpu_factor),
            "memory": scale_mem(src.get("memory", 0), mem_factor),
            "pods": str(max_pods),
        }
    return node


def scale_pod(pod: dict, cpu_factor: float, mem_factor: float, image: str) -> dict:
    for container in pod.get("spec", {}).get("containers", []):
        requests = (container.get("resources") or {}).get("requests") or {}
        scaled = {}
        if "cpu" in requests:
            scaled["cpu"] = scale_cpu(requests["cpu"], cpu_factor)
        if "memory" in requests:
            scaled["memory"] = scale_mem(requests["memory"], mem_factor)
        container["resources"] = {"requests": scaled}
        container["image"] = image
        container["imagePullPolicy"] = "IfNotPresent"
    return pod


def load_all(path: str) -> list:
    with open(path, encoding="utf-8") as fh:
        return [doc for doc in yaml.safe_load_all(fh) if doc]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", required=True, help="output folder (nodes.yaml, pods.yaml, scaling.json)")
    ap.add_argument("--nodes", default=os.path.join(SCRIPT_DIR, "base", "nodes.yaml"))
    ap.add_argument("--pods", default=os.path.join(SCRIPT_DIR, "base", "pods.yaml"))
    ap.add_argument("--cpu-factor", type=float, default=200.0,
                    help="divide CPU by this (200: 1 CPU -> 5m, 128-CPU node -> 640m)")
    ap.add_argument("--mem-factor", type=float, default=512.0,
                    help="divide memory by this (512: 1 MiB -> 2 KiB, 1-TiB node -> 2 GiB)")
    ap.add_argument("--max-pods", type=int, default=250)
    ap.add_argument("--image", default="registry.k8s.io/pause:3.9")
    args = ap.parse_args(argv)

    nodes = [scale_node(n, args.cpu_factor, args.mem_factor, args.max_pods)
             for n in load_all(args.nodes)]
    pods = [scale_pod(p, args.cpu_factor, args.mem_factor, args.image)
            for p in load_all(args.pods)]

    os.makedirs(args.output, exist_ok=True)
    with open(os.path.join(args.output, "nodes.yaml"), "w", encoding="utf-8") as fh:
        yaml.safe_dump_all(nodes, fh, sort_keys=False)
    with open(os.path.join(args.output, "pods.yaml"), "w", encoding="utf-8") as fh:
        yaml.safe_dump_all(pods, fh, sort_keys=False)
    meta = {"source_nodes": os.path.relpath(args.nodes, SCRIPT_DIR),
            "source_pods": os.path.relpath(args.pods, SCRIPT_DIR),
            "cpu_factor": args.cpu_factor, "mem_factor": args.mem_factor,
            "max_pods": args.max_pods, "image": args.image,
            "nodes": len(nodes), "pods": len(pods)}
    with open(os.path.join(args.output, "scaling.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
        fh.write("\n")
    print(f"{len(nodes)} nodes and {len(pods)} pods scaled by cpu/{args.cpu_factor:g}, "
          f"mem/{args.mem_factor:g} -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
