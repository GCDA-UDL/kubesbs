#!/usr/bin/env python3
"""Build a pfn k8s-cluster-simulator config.yaml from the toolkit's standard
nodes-<N>.yaml (k8s Node manifests, Alibaba-derived).

The simulator's `cluster:` entries map almost 1:1 from k8s Nodes: resource
quantities are passed through verbatim (cpu '64000m', memory '262144Mi', pods),
and the Alibaba GPU annotation `alibabacloud.com/gpu-count` becomes
`nvidia.com/gpu`. The metricsLogger writes one JSON record per metricsTick to
--metrics, from which the module reads the final Queue.PendingPodsNum (= pods
that never scheduled = unscheduled).

Usage: kcs_config.py --nodes nodes-100.yaml --metrics /tmp/kcs.jsonl -o config.yaml [--no-gpu]
"""
import argparse
import yaml


def node_to_entry(node: dict, use_gpu: bool = True) -> dict:
    meta = node.get("metadata", {})
    alloc = node.get("status", {}).get("allocatable", {})
    out_alloc = {}
    for key in ("cpu", "memory", "pods"):
        if key in alloc:
            out_alloc[key] = str(alloc[key])
    gpu = alloc.get("nvidia.com/gpu") or alloc.get("alibabacloud.com/gpu-count")
    if gpu and use_gpu:
        out_alloc["nvidia.com/gpu"] = str(gpu)
    out_alloc.setdefault("cpu", "1")
    out_alloc.setdefault("memory", "1Gi")
    out_alloc.setdefault("pods", "110")
    return {
        "metadata": {"name": meta.get("name"), "labels": meta.get("labels", {}) or {}},
        "spec": {"unschedulable": False},
        "status": {"allocatable": out_alloc},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", required=True)
    ap.add_argument("--metrics", default="/tmp/kcs-metrics.jsonl")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--tick", type=int, default=10)
    ap.add_argument("--metrics-tick", type=int, default=30)
    ap.add_argument("--no-gpu", action="store_true",
                    help="drop the nodes' GPUs (the other tools only see CPU and memory)")
    args = ap.parse_args()

    with open(args.nodes) as fh:
        nodes = [n for n in yaml.safe_load_all(fh) if n]
    cluster = [node_to_entry(n, use_gpu=not args.no_gpu) for n in nodes]

    cfg = {
        "tick": args.tick,
        "metricsTick": args.metrics_tick,
        "logLevel": "warn",
        "metricsLogger": [{"dest": args.metrics, "formatter": "JSON"}],
        "cluster": cluster,
    }
    with open(args.output, "w") as fh:
        yaml.safe_dump(cfg, fh, default_flow_style=False)
    print(f"kcs config: {len(cluster)} nodes -> {args.output}")


if __name__ == "__main__":
    main()
