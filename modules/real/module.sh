#!/bin/bash
# Real Kubernetes cluster: the ground truth of the fidelity study.
#
#   PROVIDER=k3d (default): one k3s v1.29 node per trace node, as k3d containers
#     on this host (utils/real_k3d.py renders the k3d config).
#   PROVIDER=gcp: one Compute Engine VM per trace node plus a control-plane VM
#     (infra/gcp/cluster.sh; run the harness on the runner VM, see
#     infra/gcp/README.md).
#
# On both, each node is named after its trace node and its allocatable equals the
# trace node's (scaled) capacity, through the kubelet's system-reserved. Use a
# dataset scaled with utils/scale_base.py: no machine can advertise the capacity
# of the trace nodes. The pods are the same manifests the simulators receive and
# run the pause image. Set POD_RECORDS_DIR to keep the per-pod record of each run.
readonly REAL_MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REAL_ROOT_DIR="$(cd "${REAL_MODULE_DIR}/../.." && pwd)"

PROVIDER="${PROVIDER:-k3d}"
# Label of the runs in pods.csv; set REAL_PLATFORM to tell hosts apart (k3d-s02, ...).
PLATFORM="${REAL_PLATFORM:-$PROVIDER}"
CLUSTER_NAME="kube-bench"
NAMESPACE="paib-gpu"
CONTAINERS_TO_WATCH="k3d-${CLUSTER_NAME}"
K3S_IMAGE="${K3S_IMAGE:-rancher/k3s:v1.29.0-k3s1}"
PAUSE_IMAGE="registry.k8s.io/pause:3.9"
REAL_WORK_DIR="${REAL_WORK_DIR:-${TMPDIR:-/tmp}/kubesbs-real}"

if [[ ! "$PROVIDER" =~ ^(k3d|gcp)$ ]]; then
    log ERROR "real module: PROVIDER=$PROVIDER is not implemented (k3d, gcp)"
    exit 1
fi
if [[ "$PROVIDER" = "gcp" ]]; then
    export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/kubesbs-gcp.yaml}"
fi

# The node file is needed to build the cluster, but kube-run.sh passes it to
# deploy_objects only; derive it from the cluster config path it gives
# create_cluster (cluster-N.yaml and nodes-N.yaml share the folder and N).
real_node_file(){
    local cluster_config="$1"
    echo "$(dirname "$cluster_config")/nodes-$(basename "$cluster_config" | grep -o '[0-9]\+' | tail -1).yaml"
}

create_cluster(){
    local node_file
    node_file="$(real_node_file "$1")"
    if [[ ! -f "$node_file" ]]; then
        log ERROR "real module: node file not found: $node_file"
        return 1
    fi
    REAL_NODE_FILE="$node_file"
    if [[ "$PROVIDER" = "gcp" ]]; then
        "${REAL_ROOT_DIR}/infra/gcp/cluster.sh" down
        "${REAL_ROOT_DIR}/infra/gcp/cluster.sh" up "$node_file"
        return
    fi
    if k3d cluster get "$CLUSTER_NAME" >/dev/null 2>&1; then
        log INFO "$CLUSTER_NAME already exists. Deleting..."
        k3d cluster delete "$CLUSTER_NAME" >/dev/null 2>&1 || true
    fi
    mkdir -p "$REAL_WORK_DIR"
    local k3d_config="${REAL_WORK_DIR}/k3d-$(basename "$node_file")"
    python3 "${REAL_ROOT_DIR}/utils/real_k3d.py" render --nodes "$node_file" \
        --out "$k3d_config" --name "$CLUSTER_NAME" --image "$K3S_IMAGE" || return 1
    log INFO "Creating k3d cluster $CLUSTER_NAME from $k3d_config..."
    k3d cluster create --config "$k3d_config" || return 1
    log INFO "Preloading $PAUSE_IMAGE on every node..."
    docker image inspect "$PAUSE_IMAGE" >/dev/null 2>&1 || docker pull "$PAUSE_IMAGE" >/dev/null
    k3d image import "$PAUSE_IMAGE" --cluster "$CLUSTER_NAME" --mode direct >/dev/null || return 1
}

cluster_setup(){
    local context_args=()
    if [[ "$PROVIDER" = "k3d" ]]; then
        kubectl config use-context "k3d-${CLUSTER_NAME}" || return 1
        context_args=(--context "k3d-${CLUSTER_NAME}")
    fi
    local tries=0
    until python3 "${REAL_ROOT_DIR}/utils/real_k3d.py" verify --nodes "$REAL_NODE_FILE" \
            "${context_args[@]}"; do
        tries=$((tries + 1))
        if [[ $tries -ge 30 ]]; then
            log ERROR "real module: node allocatable does not match the trace after ${tries} checks"
            return 1
        fi
        sleep 10
    done
}

deploy_objects(){
    local POD_FILE="$2"
    kubectl create namespace "$NAMESPACE"
    wait_for_namespace "$NAMESPACE"
    # Nodes are real: only the pods are created.
    kubectl create -f "$POD_FILE" -n "$NAMESPACE" >/dev/null
}

cleanup_cluster(){
    if [[ "$PROVIDER" = "gcp" ]]; then
        "${REAL_ROOT_DIR}/infra/gcp/cluster.sh" down || true
    else
        k3d cluster delete "$CLUSTER_NAME" >/dev/null 2>&1 || true
    fi
}

log INFO "real module loaded (provider $PROVIDER)"
