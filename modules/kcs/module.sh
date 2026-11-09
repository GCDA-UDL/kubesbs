#!/bin/bash
# pfn k8s-cluster-simulator (kcs) module.
#
# Preferred Networks' discrete-event Kubernetes scheduler simulator. Unlike the
# kube-scheduler-based modules it models pod *execution over simulated time*
# (each pod runs for a configurable duration via a synthesised simSpec), so it
# evaluates a scheduler against a temporal workload very cheaply.
#
# Integration mirrors `opensim`/`k8ssim`: a single Go process runs inside a
# dedicated cgroup and metric_collector reads that cgroup's cpu.stat /
# memory.current (cgroup v2). The simulator reuses the toolkit's *standard*
# datasets directly (data/<size>/vanilla): node-<N>.yaml -> a generated config,
# pods-<N>.yaml -> the workload. No new dataset format is required.
#
# Needs the `kcs-yamlsim` binary built from the pinned pfn commit; see
# modules/kcs/build.sh and README.md. Point K8S_CLUSTER_SIM_BIN at it.

readonly LOCAL_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly CGROUP_NAME="kcs"
readonly KCS_DURATION="${KCS_DURATION:-60}"   # simulated seconds each pod runs
# KCS_GPU=1 (default) turns the Alibaba GPU counts of nodes and pods into
# nvidia.com/gpu; KCS_GPU=0 drops them, as the other tools see only CPU and memory.
readonly KCS_GPU="${KCS_GPU:-1}"
# KCS_HORIZON=0 (default) runs until every pod has run and finished, so no pod is
# left pending. KCS_HORIZON=<s> stops after s simulated seconds; with
# KCS_DURATION > KCS_HORIZON no pod finishes and the pods pending at the end are
# the pods kcs could not place (the outcome the other tools report).
readonly KCS_HORIZON="${KCS_HORIZON:-0}"
readonly KCS_METRICS="${LOCAL_PATH}/kcs-metrics.jsonl"
readonly KCS_CONFIG="${LOCAL_PATH}/kcs-config.yaml"

FILE_PATTERN="nodes-*.yaml"

resolve_binary(){
    if [[ -n "${K8S_CLUSTER_SIM_BIN:-}" && -x "${K8S_CLUSTER_SIM_BIN}" ]]; then
        echo "${K8S_CLUSTER_SIM_BIN}"; return 0
    fi
    for cand in "${LOCAL_PATH}/kcs-yamlsim" "/usr/local/bin/kcs-yamlsim" "/tmp/kcs-yamlsim"; do
        [[ -x "$cand" ]] && { echo "$cand"; return 0; }
    done
    return 1
}

metric_collector(){
    local TYPE="$1"
    if [[ "$TYPE" == "cpu" ]]; then
        get_cpu_usage "false" "$CGROUP_NAME"
    elif [[ "$TYPE" == "memory" ]]; then
        get_memory_usage "false" "$CGROUP_NAME"
    fi
}

create_cluster(){
    if ! resolve_binary >/dev/null; then
        log ERROR "kcs-yamlsim binary not found. Build it (modules/kcs/build.sh) and set K8S_CLUSTER_SIM_BIN."
        return 1
    fi
    if [[ -d "/sys/fs/cgroup/$CGROUP_NAME" ]]; then
        cgdelete -g memory,cpu:/$CGROUP_NAME 2>/dev/null || true
    fi
    cgcreate -g memory,cpu:/$CGROUP_NAME
    [[ -d "/sys/fs/cgroup/$CGROUP_NAME" ]] || { log ERROR "Failed to create cgroup $CGROUP_NAME"; return 1; }
    log INFO "kcs cgroup ready"
}

cluster_setup(){
    # NODE_FILE is set per-iteration by deploy_objects via the runner; here we
    # only verify python is usable. Config is generated in deploy_objects, which
    # is the first place the node file path is known.
    command -v python3 >/dev/null || { log ERROR "python3 required for kcs config"; return 1; }
    :;
}

deploy_objects(){
    local NODE_FILE="$1"
    local POD_FILE="$2"
    local BIN; BIN="$(resolve_binary)"

    local GPU_FLAG=() BIN_GPU="true"
    if [[ "$KCS_GPU" == "0" ]]; then GPU_FLAG=(--no-gpu); BIN_GPU="false"; fi
    python3 "${LOCAL_PATH}/kcs_config.py" --nodes "$NODE_FILE" --metrics "$KCS_METRICS" -o "$KCS_CONFIG" "${GPU_FLAG[@]}" \
        || { log ERROR "kcs config generation failed"; UNSCHEDULED_PODS=0; return 1; }
    rm -f "$KCS_METRICS"

    log INFO "Running kcs: $(basename "$NODE_FILE") + $(basename "$POD_FILE") (duration ${KCS_DURATION}s, gpu ${KCS_GPU}, horizon ${KCS_HORIZON}s)"
    # --config takes the path without extension; KubeSim appends .yaml.
    local CFG_NOEXT="${KCS_CONFIG%.yaml}"
    cgexec -g "memory,cpu:/$CGROUP_NAME" "$BIN" \
        --config "$CFG_NOEXT" --pods "$POD_FILE" --duration "$KCS_DURATION" \
        --gpu="$BIN_GPU" --horizon "$KCS_HORIZON" \
        > "${LOCAL_PATH}/kcs-run.out" 2>&1 || log WARN "kcs binary returned non-zero"

    # Unscheduled = pods still pending in the final metrics record.
    UNSCHEDULED_PODS=$(python3 -c '
import json,sys
last=None
try:
    for line in open(sys.argv[1]):
        line=line.strip()
        if line: last=json.loads(line)
    print(int(last["Queue"]["PendingPodsNum"]) if last else 0)
except Exception:
    print(0)
' "$KCS_METRICS" 2>/dev/null)
    [[ -z "$UNSCHEDULED_PODS" ]] && UNSCHEDULED_PODS=0
    log INFO "kcs unscheduled (final pending): $UNSCHEDULED_PODS"
}

watch_pod_scheduling(){
    # The binary runs the whole simulation synchronously in deploy_objects.
    :;
}

cleanup_cluster(){
    cgdelete -g memory,cpu:/$CGROUP_NAME 2>/dev/null || true
    log INFO "kcs cleaned up"
}

log INFO "pfn k8s-cluster-simulator (kcs) module loaded!"
