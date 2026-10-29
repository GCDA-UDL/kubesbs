#!/bin/bash
# Run the real-cluster side of the fidelity study on Google Compute Engine, from
# any host with gcloud (e.g. a lab server). The harness itself runs on a runner
# VM in the same zone as the cluster, so that the watch timestamps and the
# scheduler's event times come from machines on the same network and NTP source.
#
#   run-fidelity.sh start [SCALE=100] [REPS=3]   NAT + runner, copy the harness and
#                                               the dataset, start kube-run in tmux
#   run-fidelity.sh status                      progress on the runner
#   run-fidelity.sh fetch [DEST]                copy the results here
#   run-fidelity.sh teardown                    delete cluster, runner and NAT
#
# Environment: GCP_PROJECT (required), GCP_ZONE (us-central1-a), and
# GCP_KEY_FILE, a service-account key (roles Compute Admin + Service Account
# User) used instead of a personal login when set.
set -euo pipefail

: "${GCP_PROJECT:?set GCP_PROJECT}"
export GCP_ZONE="${GCP_ZONE:-us-central1-a}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
RUNNER="${GCP_CLUSTER_NAME:-kubesbs}-runner"

g(){ gcloud --project "$GCP_PROJECT" --quiet "$@"; }
on_runner(){ g compute ssh "$RUNNER" --zone "$GCP_ZONE" --command "$1"; }
say(){ echo "[$(date '+%H:%M:%S')] $*"; }

if [[ -n "${GCP_KEY_FILE:-}" ]]; then
    gcloud auth activate-service-account --key-file "$GCP_KEY_FILE" --quiet >/dev/null
fi

start(){
    local scale="${1:-100}" reps="${2:-3}" bundle
    [[ -f "${ROOT}/data/fidelity/vanilla/nodes-${scale}.yaml" ]] || {
        echo "missing data/fidelity/vanilla/nodes-${scale}.yaml (utils/scale_base.py + kube-gen.py)"; exit 1; }
    "${HERE}/cluster.sh" net-up
    "${HERE}/cluster.sh" runner-up
    say "waiting for the runner to finish its setup"
    until on_runner "test -f /var/lib/kubesbs-runner-ready" >/dev/null 2>&1; do sleep 10; done

    bundle="$(mktemp -d)"
    mkdir -p "${bundle}/data/fidelity/gcp${scale}"
    cp "${ROOT}/data/fidelity/vanilla/nodes-${scale}.yaml" "${ROOT}/data/fidelity/vanilla/pods-${scale}.yaml" \
        "${bundle}/data/fidelity/gcp${scale}/"
    tar -C "$ROOT" --exclude __pycache__ --exclude utils/repro -czf "${bundle}/harness.tgz" \
        kube-run.sh modules/real modules/template utils infra/gcp
    tar -C "$bundle" -czf "${bundle}/data.tgz" data
    g compute scp "${bundle}/harness.tgz" "${bundle}/data.tgz" "${RUNNER}:" --zone "$GCP_ZONE"
    rm -rf "$bundle"

    say "starting $reps runs of $scale nodes on the runner (tmux session kubesbs)"
    on_runner "mkdir -p kubesbs results && tar -xzf harness.tgz -C kubesbs && tar -xzf data.tgz -C kubesbs && \
cat > run.sh <<EOF
#!/bin/bash
cd \$HOME/kubesbs
export PROVIDER=gcp GCP_PROJECT=${GCP_PROJECT} GCP_ZONE=${GCP_ZONE} POD_RECORDS_DIR=\$HOME/results
date +'%F %T start' >> \$HOME/results/progress
bash kube-run.sh -m real -e data/fidelity/gcp${scale} -n ${reps} -x 3600 -o \$HOME/results/real-gcp-${scale}.csv > \$HOME/results/run.log 2>&1
date +'%F %T end' >> \$HOME/results/progress
infra/gcp/cluster.sh down >> \$HOME/results/run.log 2>&1
echo FINISHED > \$HOME/results/STATUS
EOF
chmod +x run.sh && tmux new-session -d -s kubesbs ./run.sh"
    say "started; check with: $0 status"
}

status(){
    on_runner 'cat results/progress 2>/dev/null; cat results/STATUS 2>/dev/null; \
sed "s/\x1b\[[0-9;]*m//g" results/run.log 2>/dev/null | grep -E "gcp:|ERROR|pods \(" | tail -8'
}

fetch(){
    local dest="${1:-${ROOT}/results/fidelity-gcp-$(date +%F)}"
    mkdir -p "$dest"
    on_runner 'tar -czf results.tgz results'
    g compute scp "${RUNNER}:results.tgz" "${dest}/" --zone "$GCP_ZONE"
    tar -xzf "${dest}/results.tgz" -C "$dest" && rm "${dest}/results.tgz"
    say "results in $dest"
}

teardown(){
    on_runner 'kubesbs/infra/gcp/cluster.sh down' 2>/dev/null || "${HERE}/cluster.sh" down || true
    "${HERE}/cluster.sh" runner-down
    "${HERE}/cluster.sh" net-down
    "${HERE}/cluster.sh" status
}

case "${1:-}" in
    start) start "${2:-100}" "${3:-3}" ;;
    status) status ;;
    fetch) fetch "${2:-}" ;;
    teardown) teardown ;;
    *) sed -n '2,16p' "$0"; exit 1 ;;
esac
