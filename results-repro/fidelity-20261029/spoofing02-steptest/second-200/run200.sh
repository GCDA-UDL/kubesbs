#!/bin/bash
# 200-node fidelity runs: 3 repetitions of the real k3d cluster and of KWOK, with the same
# invocation as the 10-100 node matrix (kube-run.sh -n 3 -x 1800). Safety: a 1-minute load
# guard stops the run and deletes the cluster above MAX_LOAD, and k3d node containers are set
# to restart=no so a reboot does not bring 200 agents back.
# Usage: bash run200.sh <platform-label> <max-load> <tools...>   e.g. bash run200.sh k3d-s02 1500 real kwok
cd ~/kubesbs-fidelity || exit 1
LABEL=$1; MAX_LOAD=$2; shift 2
R=$HOME/kubesbs-fidelity/results/fidelity-200
mkdir -p "$R/work"
export PATH=$HOME/bin:$PATH POD_RECORDS_DIR=$R REAL_WORK_DIR=$R/work KWOK_KUBE_VERSION=v1.29.0 REAL_PLATFORM=$LABEL
rm -f "$R/ABORT" "$R/STATUS"
{ date; uptime; nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader; } > "$R/load-start.txt" 2>&1
sha256sum data/fidelity/pilot200/nodes-200.yaml data/fidelity/pilot200/pods-200.yaml > "$R/input.sha256"
(
  i=0
  while true; do
    load=$(cut -d" " -f1 /proc/loadavg)
    avail=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)
    ids=$(docker ps -q --filter name=k3d-kube-bench)
    n=$(echo "$ids" | grep -c .)
    echo "$(date +%T) load=$load avail_gb=$avail k3d_containers=$n" >> "$R/load.log"
    if [ $((i % 6)) -eq 0 ] && [ "$n" -gt 0 ]; then docker update --restart=no $ids >/dev/null 2>&1; fi
    if awk -v l="$load" -v m="$MAX_LOAD" 'BEGIN{exit !(l>m)}'; then
      echo "$(date '+%F %T') GUARD: load $load > $MAX_LOAD, stopping and deleting the cluster" >> "$R/progress"
      touch "$R/ABORT"; pkill -f kube-run.sh; k3d cluster delete --all >/dev/null 2>&1
      break
    fi
    i=$((i + 1)); sleep 10
  done
) &
SAMPLER=$!
for tool in "$@"; do
  [ -f "$R/ABORT" ] && break
  date +"%F %T start $tool 200 ($LABEL)" >> "$R/progress"
  bash kube-run.sh -m "$tool" -e data/fidelity/pilot200 -n 3 -x 1800 -o "$R/$tool-200.csv" > "$R/$tool-200.log" 2>&1
  date +"%F %T end $tool 200" >> "$R/progress"
done
kill $SAMPLER 2>/dev/null
{ date; uptime; nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader; } > "$R/load-end.txt" 2>&1
if [ -f "$R/ABORT" ]; then echo ABORTED > "$R/STATUS"; else echo FINISHED > "$R/STATUS"; fi
