#!/bin/bash
# Scale-up test of the local real cluster: 200, 300, 500 nodes (1 run each), with
# a memory guard that deletes the cluster if MemAvailable drops below 20 GB.
cd ~/kubesbs-fidelity
R=$HOME/kubesbs-fidelity/results/scale-up
export PATH=$HOME/bin:$PATH POD_RECORDS_DIR=$R REAL_WORK_DIR=$R/work REAL_PLATFORM=k3d-s02
MIN_AVAIL_KB=$((20*1024*1024))
( while true; do
    avail=$(awk "/MemAvailable/{print \$2}" /proc/meminfo)
    ids=$(docker ps -q --no-trunc --filter name=k3d-kube-bench)
    n=$(echo "$ids" | grep -c .)
    used=$(for id in $ids; do cat /sys/fs/cgroup/memory/docker/$id/memory.usage_in_bytes 2>/dev/null; done | awk "{s+=\$1} END{printf \"%.1f\", s/2^30}")
    echo "$(date +%T) avail_gb=$((avail/1024/1024)) k3d_containers=$n k3d_mem_gb=$used load=$(cut -d" " -f1 /proc/loadavg)" >> $R/mem.log
    if [ "$avail" -lt "$MIN_AVAIL_KB" ]; then
      echo "$(date +%T) GUARD: MemAvailable below 20 GB, deleting the cluster" >> $R/progress
      touch $R/ABORT; k3d cluster delete --all >/dev/null 2>&1
    fi
    sleep 10
  done ) &
SAMPLER=$!
for n in 200 300 500; do
  [ -f $R/ABORT ] && break
  date +"%F %T start real $n" >> $R/progress
  bash kube-run.sh -m real -e data/fidelity/pilot$n -n 1 -x 3600 -o $R/real-$n.csv > $R/real-$n.log 2>&1
  date +"%F %T end real $n" >> $R/progress
done
kill $SAMPLER
echo FINISHED > $R/STATUS
