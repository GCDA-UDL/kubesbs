#!/bin/bash
# Real Kubernetes clusters on Google Compute Engine for the fidelity study: one
# VM per trace node (k3s agent) plus a control-plane VM (k3s server, embedded
# etcd), with the same k3s flags as the local k3d clusters. No GKE: the study
# needs full control of the scheduler and the kubelet configuration.
#
#   cluster.sh net-up | net-down          Cloud NAT so VMs without public IP can
#                                         download k3s (one per region)
#   cluster.sh runner-up | runner-down    small VM that runs the harness in the
#                                         same zone (same network, NTP clock)
#   cluster.sh up NODES_FILE              server + one VM per node of NODES_FILE;
#                                         waits until every node is Ready and
#                                         writes $KUBECONFIG
#   cluster.sh down                       deletes the server and node VMs
#   cluster.sh status                     lists the VMs of the cluster
#
# Every VM is labelled kubesbs-cluster=$CLUSTER_NAME and deletes itself after
# $GCP_MAX_RUN (default 3h) whatever happens, so a failed run cannot keep billing.
set -euo pipefail

: "${GCP_PROJECT:?set GCP_PROJECT to the Google Cloud project id}"
GCP_ZONE="${GCP_ZONE:-us-central1-a}"
GCP_REGION="${GCP_ZONE%-*}"
GCP_NETWORK="${GCP_NETWORK:-default}"
GCP_NODE_TYPE="${GCP_NODE_TYPE:-n1-standard-1}"
GCP_SERVER_TYPE="${GCP_SERVER_TYPE:-n1-standard-8}"
GCP_RUNNER_TYPE="${GCP_RUNNER_TYPE:-n1-standard-2}"
GCP_MAX_RUN="${GCP_MAX_RUN:-3h}"
GCP_IMAGE_FAMILY="${GCP_IMAGE_FAMILY:-ubuntu-2204-lts}"
GCP_IMAGE_PROJECT="${GCP_IMAGE_PROJECT:-ubuntu-os-cloud}"
CLUSTER_NAME="${GCP_CLUSTER_NAME:-kubesbs}"
K3S_VERSION="${K3S_VERSION:-v1.29.0+k3s1}"
KUBECONFIG="${KUBECONFIG:-$HOME/.kube/kubesbs-gcp.yaml}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS="$(cd "${HERE}/../../utils" && pwd)"
SERVER="${CLUSTER_NAME}-server"
RUNNER="${CLUSTER_NAME}-runner"

g(){ gcloud --project "$GCP_PROJECT" --quiet "$@"; }
say(){ echo "[$(date '+%H:%M:%S')] gcp: $*"; }
ttl(){ [[ -n "$GCP_MAX_RUN" ]] && echo "--max-run-duration=$GCP_MAX_RUN --instance-termination-action=DELETE"; }

net_up(){
    if ! g compute routers describe "${CLUSTER_NAME}-router" --region "$GCP_REGION" >/dev/null 2>&1; then
        g compute routers create "${CLUSTER_NAME}-router" --network "$GCP_NETWORK" --region "$GCP_REGION"
    fi
    if ! g compute routers nats describe "${CLUSTER_NAME}-nat" --router "${CLUSTER_NAME}-router" \
            --region "$GCP_REGION" >/dev/null 2>&1; then
        g compute routers nats create "${CLUSTER_NAME}-nat" --router "${CLUSTER_NAME}-router" \
            --region "$GCP_REGION" --auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges
    fi
    say "Cloud NAT ready in $GCP_REGION"
}

net_down(){
    g compute routers delete "${CLUSTER_NAME}-router" --region "$GCP_REGION" 2>/dev/null || true
    say "Cloud NAT removed"
}

runner_up(){
    # shellcheck disable=SC2046
    g compute instances create "$RUNNER" --zone "$GCP_ZONE" --machine-type "$GCP_RUNNER_TYPE" \
        --image-family "$GCP_IMAGE_FAMILY" --image-project "$GCP_IMAGE_PROJECT" \
        --boot-disk-size 30GB --boot-disk-type pd-balanced --scopes cloud-platform \
        --labels "kubesbs-cluster=${CLUSTER_NAME},kubesbs-role=runner" $(GCP_MAX_RUN=8h ttl) \
        --metadata-from-file startup-script="${HERE}/runner-setup.sh"
    say "runner $RUNNER created (deletes itself after 8h)"
}

runner_down(){
    g compute instances delete "$RUNNER" --zone "$GCP_ZONE" 2>/dev/null || true
}

up(){
    local nodes_file="$1" targets token count server_ip
    targets="$(mktemp)"
    python3 "${UTILS}/real_k3d.py" targets --nodes "$nodes_file" > "$targets"
    count=$(wc -l < "$targets")
    token="$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    say "creating $SERVER ($GCP_SERVER_TYPE) for $count nodes"
    # shellcheck disable=SC2046
    g compute instances create "$SERVER" --zone "$GCP_ZONE" --machine-type "$GCP_SERVER_TYPE" \
        --image-family "$GCP_IMAGE_FAMILY" --image-project "$GCP_IMAGE_PROJECT" \
        --boot-disk-size 30GB --boot-disk-type pd-balanced --no-address \
        --labels "kubesbs-cluster=${CLUSTER_NAME},kubesbs-role=server" $(ttl) \
        --metadata "kubesbs-k3s-version=${K3S_VERSION},kubesbs-token=${token},enable-guest-attributes=TRUE" \
        --metadata-from-file startup-script="${HERE}/k3s-server.sh" >/dev/null
    server_ip="$(g compute instances describe "$SERVER" --zone "$GCP_ZONE" \
        --format 'value(networkInterfaces[0].networkIP)')"

    say "creating $count node VMs ($GCP_NODE_TYPE)"
    # shellcheck disable=SC2046
    g compute instances bulk create --name-pattern "${CLUSTER_NAME}-agent-####" --count "$count" \
        --zone "$GCP_ZONE" --machine-type "$GCP_NODE_TYPE" \
        --image-family "$GCP_IMAGE_FAMILY" --image-project "$GCP_IMAGE_PROJECT" \
        --boot-disk-size 10GB --boot-disk-type pd-standard --no-address \
        --labels "kubesbs-cluster=${CLUSTER_NAME},kubesbs-role=agent" $(ttl) \
        --metadata "kubesbs-k3s-version=${K3S_VERSION},kubesbs-token=${token},kubesbs-server=${server_ip}" \
        --metadata-from-file "startup-script=${HERE}/k3s-agent.sh,kubesbs-targets=${targets}" >/dev/null
    rm -f "$targets"

    say "waiting for the API server"
    mkdir -p "$(dirname "$KUBECONFIG")"
    local t0=$SECONDS
    until g compute instances get-guest-attributes "$SERVER" --zone "$GCP_ZONE" \
            --query-path kubesbs/kubeconfig --format 'value(value)' 2>/dev/null \
            | base64 -d > "$KUBECONFIG" 2>/dev/null && [[ -s "$KUBECONFIG" ]]; do
        (( SECONDS - t0 > 900 )) && { say "API server not up after 15 min"; return 1; }
        sleep 10
    done
    chmod 600 "$KUBECONFIG"

    say "waiting for $count nodes to be Ready"
    local ready=0
    while (( ready < count )); do
        (( SECONDS - t0 > 1500 )) && { say "only $ready/$count nodes Ready after 25 min"; return 1; }
        sleep 10
        ready=$(KUBECONFIG="$KUBECONFIG" kubectl get nodes --no-headers 2>/dev/null \
                | awk '$2 == "Ready" && $3 !~ /control-plane/' | wc -l)
        say "$ready/$count nodes Ready"
    done
}

down(){
    local names
    names="$(g compute instances list --filter "labels.kubesbs-cluster=${CLUSTER_NAME} AND NOT labels.kubesbs-role=runner" \
        --format 'value(name)' | tr '\n' ' ')"
    if [[ -n "${names// /}" ]]; then
        say "deleting $(wc -w <<< "$names") VMs"
        # shellcheck disable=SC2086
        g compute instances delete $names --zone "$GCP_ZONE" >/dev/null
    fi
}

status(){
    g compute instances list --filter "labels.kubesbs-cluster=${CLUSTER_NAME}" \
        --format 'table(name,labels.kubesbs-role,status,machineType.basename())'
}

case "${1:-}" in
    net-up) net_up ;;
    net-down) net_down ;;
    runner-up) runner_up ;;
    runner-down) runner_down ;;
    up) up "${2:?usage: cluster.sh up NODES_FILE}" ;;
    down) down ;;
    status) status ;;
    *) sed -n '2,20p' "$0"; exit 1 ;;
esac
