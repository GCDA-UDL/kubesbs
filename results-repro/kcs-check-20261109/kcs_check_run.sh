#!/usr/bin/env bash
# kcs check of 2026-11-09 (KubeSBS paper, audit finding K01).
# Three kcs configurations, big sweep and benchmark, three runs each, on the host
# of the cost sweep (spoofing-gcd), with the published runner image:
#   A  published: binary of June 2026 (sha256 f0033c13...), 60-s pods, GPU counts kept,
#      run ends when every pod has finished (the configuration of both sessions);
#   C  as A but without GPU counts (new binary, defaults otherwise);
#   B  placement only: no GPU counts, pods never finish (duration 1e7 s), stop at a
#      120-s simulated horizon, so the pods still pending are those kcs could not place.
set -u
cd ~/kubesbs-kcs-20261109
BASE=results-repro/kcs-check-20261109
mkdir -p "$BASE"
NEW=modules/kcs/kcs-yamlsim-horizon
run() {  # name dataset env...
  local name=$1 ds=$2; shift 2
  echo "=== $name $ds $(date -Iseconds)"
  env "$@" DATASET=$ds MODULES=kcs RUNS=3 OUT=$BASE/$name-$ds bash utils/repro/run_sweep.sh > $BASE/$name-$ds.console.log 2>&1
  echo "=== $name $ds exit $? $(date -Iseconds)"
}
for ds in benchmark big; do
  run A-published $ds KCS_BIN=$HOME/kcs-yamlsim-20260615
  run C-nogpu     $ds KCS_BIN=$NEW KCS_GPU=0
  run B-placement $ds KCS_BIN=$NEW KCS_GPU=0 KCS_DURATION=10000000 KCS_HORIZON=120
done
echo "=== ALL DONE $(date -Iseconds)"
