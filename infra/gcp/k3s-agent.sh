#!/bin/bash
# GCE startup script of every node VM: a k3s agent named after its trace node,
# whose allocatable equals the trace node's scaled capacity (system-reserved =
# VM capacity - target - eviction threshold), as in the local k3d clusters.
# The VM kubesbs-agent-N takes line N of the kubesbs-targets metadata
# ("name cpu_m mem_ki pods", from utils/real_k3d.py targets).
set -euo pipefail
md(){ curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/$1"; }

[[ -x /usr/local/bin/k3s ]] && exit 0   # already installed (reboot)
NUM=$((10#$(hostname | grep -o '[0-9]\+$')))
read -r NAME CPU_M MEM_KI PODS <<< "$(md instance/attributes/kubesbs-targets | sed -n "${NUM}p")"
if [[ -z "${NAME:-}" ]]; then
    echo "kubesbs: no target for VM number $NUM" >&2
    exit 1
fi
SERVER="$(md instance/attributes/kubesbs-server)"
TOKEN="$(md instance/attributes/kubesbs-token)"
K3S_VERSION="$(md instance/attributes/kubesbs-k3s-version)"
EVICTION_KI=102400   # memory.available<100Mi
RES_CPU=$(( $(nproc) * 1000 - CPU_M ))
RES_MEM=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) - MEM_KI - EVICTION_KI ))
if (( RES_CPU < 0 || RES_MEM < 0 )); then
    echo "kubesbs: target ${CPU_M}m/${MEM_KI}Ki of $NAME exceeds this VM" >&2
    exit 1
fi

curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$K3S_VERSION" \
    K3S_URL="https://${SERVER}:6443" K3S_TOKEN="$TOKEN" sh -s - agent \
    --node-name "$NAME" \
    --pause-image registry.k8s.io/pause:3.9 \
    --kubelet-arg "system-reserved=cpu=${RES_CPU}m,memory=${RES_MEM}Ki" \
    --kubelet-arg "max-pods=${PODS}" \
    --kubelet-arg "eviction-hard=memory.available<100Mi,nodefs.available<1%,nodefs.inodesFree<1%,imagefs.available<1%" \
    --kubelet-arg "image-gc-high-threshold=100" \
    --kubelet-arg "image-gc-low-threshold=99"

# The pods run the pause image: pull it now so no pod waits for it.
until k3s ctr -n k8s.io images pull registry.k8s.io/pause:3.9 >/dev/null 2>&1; do sleep 2; done
