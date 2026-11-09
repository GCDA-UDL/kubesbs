#!/usr/bin/env bash
# Re-run of configuration A (published binary, defaults) after the module fix of ea4e2dd:
# the first attempt passed --gpu/--horizon to the June binary, which rejected them.
set -u
cd ~/kubesbs-kcs-20261109
BASE=results-repro/kcs-check-20261109
for ds in benchmark big; do
  echo "=== A-published $ds $(date -Iseconds)"
  env KCS_BIN=$HOME/kcs-yamlsim-20260615 DATASET=$ds MODULES=kcs RUNS=3 OUT=$BASE/A-published-$ds bash utils/repro/run_sweep.sh > $BASE/A-published-$ds.console.log 2>&1
  echo "=== A-published $ds exit $? $(date -Iseconds)"
done
echo "=== ALL DONE $(date -Iseconds)"
