#!/usr/bin/env python3
"""k3d support for the `real` module: one real k3s node per trace node.

Every agent is a k3s node (real kubelet, containerd and pods) named after its
trace node. Its allocatable must equal the (scaled) capacity of that node, but a
kubelet in a k3d container reports the capacity of the host. The kubelet's
system-reserved is therefore set per agent to host capacity - target - eviction
threshold, so that allocatable = target exactly.

  render  nodes-N.yaml -> k3d config (k3d.io/v1alpha5), on the host that runs k3d
  verify  compare the allocatable of the live cluster with nodes-N.yaml

Usage:
  python3 utils/real_k3d.py render --nodes nodes-10.yaml --out k3d-10.yaml \
      [--name kube-bench] [--image rancher/k3s:v1.29.0-k3s1] \
      [--host-cpu-m N] [--host-mem-ki N]     (default: read from this host)
  python3 utils/real_k3d.py verify --nodes nodes-10.yaml [--context k3d-kube-bench]
  python3 utils/real_k3d.py targets --nodes nodes-100.yaml   (input of infra/gcp)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scale_base import cpu_millicores, mem_bytes  # noqa: E402

EVICTION_MEM_MI = 100
# Every eviction signal is set explicitly: when --eviction-hard is given, the
# kubelet does not merge in its defaults, and a nearly full host disk must not put
# the nodes under DiskPressure (that would taint them and change the scheduling).
EVICTION_HARD = (f"memory.available<{EVICTION_MEM_MI}Mi,nodefs.available<1%,"
                 "nodefs.inodesFree<1%,imagefs.available<1%")
PAUSE_IMAGE = "registry.k8s.io/pause:3.9"
# 10.64.0.0/12 holds 4096 /24 node subnets (cloud runs reach 1,000 nodes) and does
# not overlap the k3s service CIDR 10.43.0.0/16.
CLUSTER_CIDR = "10.64.0.0/12"


def host_capacity() -> tuple[int, int]:
    """CPU (millicores) and memory (KiB) that a kubelet on this host reports."""
    cpu_m = os.cpu_count() * 1000
    with open("/proc/meminfo", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("MemTotal:"):
                return cpu_m, int(line.split()[1])
    raise RuntimeError("MemTotal not found in /proc/meminfo")


def load_nodes(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        docs = [d for d in yaml.safe_load_all(fh) if d and d.get("kind") == "Node"]
    if not docs:
        raise SystemExit(f"{path}: no Node objects")
    return docs


def target(node: dict) -> tuple[int, int, int]:
    """Allocatable cpu (m), memory (KiB) and pods requested by a trace node."""
    alloc = node["status"]["allocatable"]
    return (round(cpu_millicores(alloc["cpu"])), round(mem_bytes(alloc["memory"]) / 1024),
            int(alloc.get("pods", 110)))


def render(nodes: list[dict], name: str, image: str, host_cpu_m: int, host_mem_ki: int) -> dict:
    eviction_ki = EVICTION_MEM_MI * 1024
    args = [
        # Embedded etcd, as in a production control plane (k3s defaults to SQLite).
        {"arg": "--cluster-init", "nodeFilters": ["server:*"]},
        {"arg": "--disable=traefik,servicelb,metrics-server,local-storage,coredns",
         "nodeFilters": ["server:*"]},
        # Keep the trace's pods off the control-plane node.
        {"arg": "--node-taint=node-role.kubernetes.io/control-plane=true:NoSchedule",
         "nodeFilters": ["server:*"]},
        {"arg": f"--cluster-cidr={CLUSTER_CIDR}", "nodeFilters": ["server:*"]},
        {"arg": f"--pause-image={PAUSE_IMAGE}", "nodeFilters": ["server:*", "agent:*"]},
        {"arg": f"--kubelet-arg=eviction-hard={EVICTION_HARD}", "nodeFilters": ["agent:*"]},
        {"arg": "--kubelet-arg=image-gc-high-threshold=100", "nodeFilters": ["agent:*"]},
        {"arg": "--kubelet-arg=image-gc-low-threshold=99", "nodeFilters": ["agent:*"]},
    ]
    for i, node in enumerate(nodes):
        cpu_m, mem_ki, pods = target(node)
        res_cpu = host_cpu_m - cpu_m
        res_mem = host_mem_ki - mem_ki - eviction_ki
        if res_cpu < 0 or res_mem < 0:
            raise SystemExit(f"{node['metadata']['name']}: target {cpu_m}m/{mem_ki}Ki exceeds "
                             f"the host ({host_cpu_m}m/{host_mem_ki}Ki); scale the dataset")
        per_node = [f"--node-name={node['metadata']['name']}",
                    f"--kubelet-arg=system-reserved=cpu={res_cpu}m,memory={res_mem}Ki",
                    f"--kubelet-arg=max-pods={pods}"]
        # A new filter list per entry: a shared one would be dumped as YAML aliases.
        args += [{"arg": a, "nodeFilters": [f"agent:{i}"]} for a in per_node]
    return {
        "apiVersion": "k3d.io/v1alpha5",
        "kind": "Simple",
        "metadata": {"name": name},
        "servers": 1,
        "agents": len(nodes),
        "image": image,
        "options": {
            "k3d": {"wait": True, "timeout": "900s", "disableLoadbalancer": True},
            "k3s": {"extraArgs": args},
            "kubeconfig": {"updateDefaultKubeconfig": True, "switchCurrentContext": True},
        },
    }


def verify(nodes: list[dict], context: str | None) -> list[str]:
    cmd = ["kubectl", "get", "nodes", "-o", "json"]
    if context:
        cmd[1:1] = ["--context", context]
    live = {n["metadata"]["name"]: n for n in
            json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)["items"]}
    problems = []
    for node in nodes:
        name = node["metadata"]["name"]
        if name not in live:
            problems.append(f"{name}: not in the cluster")
            continue
        want = target(node)
        alloc = live[name]["status"]["allocatable"]
        got = (round(cpu_millicores(alloc["cpu"])), round(mem_bytes(alloc["memory"]) / 1024),
               int(alloc["pods"]))
        if got != want:
            problems.append(f"{name}: allocatable {got} != target {want} (cpu m, mem KiB, pods)")
        taints = [t["key"] for t in live[name]["spec"].get("taints", [])]
        if taints:
            problems.append(f"{name}: tainted {taints}")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="k3d support for the real module")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("--nodes", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--name", default="kube-bench")
    r.add_argument("--image", default="rancher/k3s:v1.29.0-k3s1")
    r.add_argument("--host-cpu-m", type=int)
    r.add_argument("--host-mem-ki", type=int)
    v = sub.add_parser("verify")
    v.add_argument("--nodes", required=True)
    v.add_argument("--context")
    t = sub.add_parser("targets", help="one line per node: name cpu_m mem_ki pods (cloud VMs)")
    t.add_argument("--nodes", required=True)
    args = ap.parse_args(argv)

    nodes = load_nodes(args.nodes)
    if args.cmd == "targets":
        for node in nodes:
            print(node["metadata"]["name"], *target(node))
        return 0
    if args.cmd == "render":
        cpu_m, mem_ki = host_capacity() if args.host_cpu_m is None else (args.host_cpu_m, args.host_mem_ki)
        config = render(nodes, args.name, args.image, cpu_m, mem_ki)
        with open(args.out, "w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, sort_keys=False)
        print(f"k3d config for {len(nodes)} agents (host {cpu_m}m, {mem_ki}Ki) -> {args.out}")
        return 0
    problems = verify(nodes, args.context)
    for p in problems:
        print(f"MISMATCH {p}", file=sys.stderr)
    print(f"verified {len(nodes)} nodes: {'OK' if not problems else f'{len(problems)} problems'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
