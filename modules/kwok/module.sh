#!/bin/bash
readonly LOCAL_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CLUSTER_NAME="kwok"
NAMESPACE="paib-gpu"
CONTAINERS_TO_WATCH="$CLUSTER_NAME"

create_cluster(){
    if kwokctl get clusters | grep -q "$CLUSTER_NAME"; then
        log INFO "$CLUSTER_NAME already exists. Deleting..."
        kwokctl delete cluster --name "$CLUSTER_NAME" 2>/dev/null || true
    fi
    # kwokctl reads KWOK_KUBE_VERSION (e.g. v1.29.0) from the environment and pins
    # the control-plane images with it, so that the fidelity study runs the same
    # kube-scheduler as the real cluster; unset keeps the published behaviour.
    kwokctl create cluster --name "$CLUSTER_NAME" \
    --timeout 60s \
    --kind-node-image kindest/node:v1.29.0
}

cluster_setup(){
    kubectl config use-context "kwok-${CLUSTER_NAME}"
}

cleanup_cluster(){
    kwokctl delete cluster --name "$CLUSTER_NAME"
}

deploy_objects(){
    local NODE_FILE="$1"
    local POD_FILE="$2"
    kubectl create namespace "$NAMESPACE"
    wait_for_namespace "$NAMESPACE"
    kubectl create -f "$NODE_FILE"
    kubectl create -f "$POD_FILE" -n "$NAMESPACE"
}

log INFO "KWOK module loaded!"
