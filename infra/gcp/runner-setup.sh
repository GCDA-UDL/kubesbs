#!/bin/bash
# GCE startup script of the runner VM: the tools the harness needs (gcloud is
# preinstalled on the Ubuntu images of Compute Engine).
set -euo pipefail
[[ -f /var/lib/kubesbs-runner-ready ]] && exit 0
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3-yaml tmux
curl -sfL -o /usr/local/bin/kubectl https://dl.k8s.io/release/v1.29.0/bin/linux/amd64/kubectl
chmod +x /usr/local/bin/kubectl
touch /var/lib/kubesbs-runner-ready
