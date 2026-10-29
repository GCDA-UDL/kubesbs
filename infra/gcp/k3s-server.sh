#!/bin/bash
# GCE startup script of the control-plane VM: k3s server with embedded etcd and
# the same flags as the local k3d clusters (utils/real_k3d.py). When the API is
# up, it publishes a kubeconfig that points to its internal IP as the guest
# attribute kubesbs/kubeconfig, read by infra/gcp/cluster.sh.
set -euo pipefail
md(){ curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/$1"; }

[[ -f /etc/rancher/k3s/k3s.yaml ]] && exit 0   # already installed (reboot)
K3S_VERSION="$(md instance/attributes/kubesbs-k3s-version)"
TOKEN="$(md instance/attributes/kubesbs-token)"
IP="$(md instance/network-interfaces/0/ip)"

curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$K3S_VERSION" K3S_TOKEN="$TOKEN" sh -s - server \
    --cluster-init \
    --disable=traefik,servicelb,metrics-server,local-storage,coredns \
    --node-taint node-role.kubernetes.io/control-plane=true:NoSchedule \
    --cluster-cidr 10.64.0.0/12 \
    --pause-image registry.k8s.io/pause:3.9 \
    --tls-san "$IP" \
    --write-kubeconfig-mode 644

until k3s kubectl get --raw /readyz >/dev/null 2>&1; do sleep 2; done
# Base64, so that no tool on the way reformats the multi-line YAML.
sed "s#https://127.0.0.1:6443#https://${IP}:6443#" /etc/rancher/k3s/k3s.yaml | base64 -w0 \
    | curl -sf -X PUT -H "Metadata-Flavor: Google" --data-binary @- \
    "http://metadata.google.internal/computeMetadata/v1/instance/guest-attributes/kubesbs/kubeconfig"
