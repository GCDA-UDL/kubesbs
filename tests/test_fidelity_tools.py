"""Tests for the fidelity-study tools: scale_base, real_k3d (render) and collect_pods."""

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))

import collect_pods  # noqa: E402
import fidelity  # noqa: E402
import real_k3d  # noqa: E402
import scale_base  # noqa: E402


# ---------------------------------------------------------------------------
# scale_base
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value,expected", [("64000m", 64000), ("64", 64000), (2, 2000), ("0.5", 500)])
def test_cpu_millicores(value, expected):
    assert scale_base.cpu_millicores(value) == expected


@pytest.mark.parametrize("value,expected", [("262144Mi", 262144 * 2**20), ("1Gi", 2**30),
                                            ("1000M", 10**9), (1024, 1024), ("16Ki", 16384)])
def test_mem_bytes(value, expected):
    assert scale_base.mem_bytes(value) == expected


def test_scale_is_exact_for_integer_cpus_and_mib():
    # cpu/200: 1 CPU -> 5m; mem/512: 1 MiB -> 2 KiB, so trace values stay exact.
    assert scale_base.scale_cpu("128000m", 200) == "640m"
    assert scale_base.scale_cpu("1000m", 200) == "5m"
    assert scale_base.scale_mem("1048576Mi", 512) == "2097152Ki"
    assert scale_base.scale_mem("31250Mi", 512) == "62500Ki"


def test_scale_keeps_tiny_requests_nonzero_and_zero_as_zero():
    assert scale_base.scale_cpu("1m", 200) == "1m"
    assert scale_base.scale_cpu("0", 200) == "0m"
    assert scale_base.scale_mem("0", 512) == "0Ki"
    assert scale_base.scale_mem("1Ki", 512) == "1Ki"


def test_scale_node_drops_gpu_resources_and_sets_max_pods():
    node = {"kind": "Node", "metadata": {"name": "n0"},
            "status": {"capacity": {"cpu": "64000m", "memory": "262144Mi", "pods": "1001",
                                    "alibabacloud.com/gpu-count": "2"},
                       "allocatable": {"cpu": "64000m", "memory": "262144Mi", "pods": "1001",
                                       "alibabacloud.com/gpu-count": "2"}}}
    out = scale_base.scale_node(node, 200, 512, 250)
    for key in ("capacity", "allocatable"):
        assert out["status"][key] == {"cpu": "320m", "memory": "524288Ki", "pods": "250"}


def test_scale_pod_keeps_requests_drops_limits_and_sets_image():
    pod = {"kind": "Pod", "metadata": {"name": "p0", "annotations": {"a": "1"}},
           "spec": {"containers": [{"name": "main", "image": "tensorflow:latest",
                                    "resources": {"limits": {"cpu": "12000m", "memory": "16384Mi"},
                                                  "requests": {"cpu": "12000m", "memory": "16384Mi"}}}]}}
    out = scale_base.scale_pod(pod, 200, 512, "registry.k8s.io/pause:3.9")
    c = out["spec"]["containers"][0]
    assert c["resources"] == {"requests": {"cpu": "60m", "memory": "32768Ki"}}
    assert c["image"] == "registry.k8s.io/pause:3.9"
    assert out["metadata"]["annotations"] == {"a": "1"}


def test_scale_preserves_request_to_capacity_fractions():
    # The default scheduler scores requested/allocatable; scaling must keep it.
    node_cpu, pod_cpu = 96000, 11300
    frac = pod_cpu / node_cpu
    scaled = (scale_base.cpu_millicores(scale_base.scale_cpu(f"{pod_cpu}m", 200))
              / scale_base.cpu_millicores(scale_base.scale_cpu(f"{node_cpu}m", 200)))
    assert abs(scaled - frac) / frac < 0.01


# ---------------------------------------------------------------------------
# real_k3d
# ---------------------------------------------------------------------------


def _node(name, cpu="640m", mem="2097152Ki", pods="250"):
    return {"kind": "Node", "metadata": {"name": name},
            "status": {"allocatable": {"cpu": cpu, "memory": mem, "pods": pods}}}


def _args_for(config, flt):
    return [a["arg"] for a in config["options"]["k3s"]["extraArgs"] if flt in a["nodeFilters"]]


def test_render_sets_allocatable_through_system_reserved():
    host_cpu, host_mem = 32000, 196_000_000
    cfg = real_k3d.render([_node("openb-node-0000"), _node("openb-node-0001", "320m", "524288Ki")],
                          "kube-bench", "rancher/k3s:v1.29.0-k3s1", host_cpu, host_mem)
    assert cfg["agents"] == 2 and cfg["servers"] == 1
    a1 = _args_for(cfg, "agent:1")
    assert "--node-name=openb-node-0001" in a1
    res = next(a for a in a1 if "system-reserved" in a)
    eviction = real_k3d.EVICTION_MEM_MI * 1024
    assert res == f"--kubelet-arg=system-reserved=cpu={host_cpu - 320}m,memory={host_mem - 524288 - eviction}Ki"
    assert "--kubelet-arg=max-pods=250" in a1


def test_render_keeps_pods_off_the_server_and_disables_addons():
    cfg = real_k3d.render([_node("n0")], "kube-bench", "img", 32000, 196_000_000)
    server = _args_for(cfg, "server:*")
    assert any("NoSchedule" in a for a in server)
    disabled = next(a for a in server if a.startswith("--disable="))
    assert "coredns" in disabled and "metrics-server" in disabled
    # Disk pressure must never taint the nodes.
    assert any("nodefs.available<1%" in a for a in _args_for(cfg, "agent:*"))


def test_render_rejects_nodes_larger_than_the_host():
    with pytest.raises(SystemExit):
        real_k3d.render([_node("big", cpu="64000m")], "kube-bench", "img", 32000, 196_000_000)


# ---------------------------------------------------------------------------
# collect_pods
# ---------------------------------------------------------------------------


def test_parse_time_handles_fractions_and_zulu():
    base = datetime(2026, 10, 29, 17, 0, 0, tzinfo=timezone.utc).timestamp()
    assert collect_pods.parse_time("2026-10-29T17:00:00Z") == pytest.approx(base)
    assert collect_pods.parse_time("2026-10-29T17:00:00.123456Z") == pytest.approx(base + 0.123456)
    assert collect_pods.parse_time("2026-10-29T17:00:00.5Z") == pytest.approx(base + 0.5)
    assert collect_pods.parse_time("2026-10-29T18:00:00+01:00") == pytest.approx(base)
    assert collect_pods.parse_time(None) is None


def _pod(name, node, created, sched_cond=None, started=None, phase="Running"):
    status = {"phase": phase, "conditions": []}
    if sched_cond:
        status["conditions"].append({"type": "PodScheduled", "status": "True",
                                     "lastTransitionTime": sched_cond})
    if started:
        status["containerStatuses"] = [{"state": {"running": {"startedAt": started}}}]
    spec = {"containers": [{"resources": {"requests": {"cpu": "60m", "memory": "32768Ki"}}}]}
    if node:
        spec["nodeName"] = node
    return {"metadata": {"name": name, "creationTimestamp": created}, "spec": spec, "status": status}


def test_pod_rows_prefers_scheduled_events_and_is_relative_to_first_creation():
    pods = {"items": [
        _pod("p1", "n1", "2026-10-29T17:00:01Z", "2026-10-29T17:00:02Z", "2026-10-29T17:00:03Z"),
        _pod("p0", "n0", "2026-10-29T17:00:00Z", "2026-10-29T17:00:01Z"),
        _pod("p2", "", "2026-10-29T17:00:00Z", phase="Pending"),
    ]}
    events = {"items": [
        {"reason": "Scheduled", "regarding": {"kind": "Pod", "name": "p1"},
         "eventTime": "2026-10-29T17:00:01.250000Z"},
        {"reason": "FailedScheduling", "regarding": {"kind": "Pod", "name": "p2"},
         "eventTime": "2026-10-29T17:00:00.100000Z"},
    ]}
    meta = {"tool": "real", "platform": "k3d", "scale": "10", "rep": "1", "workload": "alibaba"}
    rows = {r["pod"]: r for r in collect_pods.pod_rows(pods, events, meta)}
    assert list(rows) == ["p0", "p1", "p2"]
    assert rows["p1"]["t_create"] == "1.000000"
    assert rows["p1"]["t_scheduled"] == "1.250000" and rows["p1"]["t_scheduled_source"] == "event"
    assert rows["p1"]["t_start"] == "3.000000"
    assert rows["p0"]["t_scheduled"] == "1.000000" and rows["p0"]["t_scheduled_source"] == "condition"
    assert rows["p2"]["node"] == "" and rows["p2"]["t_scheduled"] == "" and rows["p2"]["status"] == "Pending"
    assert rows["p0"]["cpu_m"] == "60" and rows["p0"]["mem_kib"] == "32768"
    assert set(rows["p0"]) == set(collect_pods.COLUMNS)


def test_pod_rows_reads_core_v1_events():
    pods = {"items": [_pod("p0", "n0", "2026-10-29T17:00:00Z")]}
    events = {"items": [{"reason": "Scheduled", "involvedObject": {"kind": "Pod", "name": "p0"},
                         "eventTime": None, "lastTimestamp": "2026-10-29T17:00:02Z"}]}
    row = collect_pods.pod_rows(pods, events, {})[0]
    assert row["t_scheduled"] == "2.000000" and row["t_scheduled_source"] == "event"


# ---------------------------------------------------------------------------
# fidelity
# ---------------------------------------------------------------------------

CAPACITY = {"n0": (100.0, 1000.0), "n1": (100.0, 1000.0)}


def _row(pod, node, cpu=50, mem=500, t_create="0.0", t_sched="0.5"):
    return {"pod": pod, "node": node, "cpu_m": str(cpu), "mem_kib": str(mem),
            "t_create": t_create, "t_scheduled": t_sched if node else ""}


def test_identical_runs_agree_fully():
    run = [_row("p0", "n0"), _row("p1", "n1"), _row("p2", "")]
    m = fidelity.compare(run, list(run), CAPACITY)
    assert m["agreement"] == "1.000000" and m["w1_cpu"] == "0.000000"
    assert m["unsched_a"] == m["unsched_b"] == 1


def test_mirrored_placement_disagrees_but_has_the_same_occupancy():
    a = [_row("p0", "n0"), _row("p1", "n1")]
    b = [_row("p0", "n1"), _row("p1", "n0")]
    m = fidelity.compare(a, b, CAPACITY)
    assert m["agreement"] == "0.000000"
    assert m["w1_cpu"] == "0.000000"   # same distribution of per-node load


def test_consolidated_placement_has_occupancy_distance():
    a = [_row("p0", "n0"), _row("p1", "n1")]       # 0.5 / 0.5
    b = [_row("p0", "n0"), _row("p1", "n0")]       # 1.0 / 0.0
    m = fidelity.compare(a, b, CAPACITY)
    assert m["agreement"] == "0.500000"
    assert float(m["w1_cpu"]) == pytest.approx(0.5)


def test_compare_rejects_runs_with_different_pods():
    with pytest.raises(ValueError):
        fidelity.compare([_row("p0", "n0")], [_row("p1", "n0")], CAPACITY)


def test_quantile_interpolates():
    assert fidelity.quantile([1.0, 2.0, 3.0, 4.0], 0.5) == pytest.approx(2.5)
    assert fidelity.quantile([], 0.5) is None
