# kcs check, 2026-11-09

Why: the kcs module of both published sessions gives every pod one phase of 60
simulated seconds (`KCS_DURATION=60`), turns the trace's GPU counts into
`nvidia.com/gpu` requests and capacities, and ends a run only when every pod has run
and finished. Its final pending count is therefore always 0, unlike the tools that
place each pod once and stop. kcs's scheduler (upstream
`pkg/scheduler/generic_scheduler.go`, commit 55e4108) also stops at the first pod in
its queue that fits no node and retries it at the next tick, so a pod that does not
fit blocks the pods behind it.

Host: spoofing-gcd (2× Xeon Silver 4210R, the host of the cost sweep), runner image
`thesmuks/k8s-sims@sha256:162f8e96…` (image ID `49601a9c…`, the published one),
`utils/repro/run_sweep.sh`, three runs per size, datasets `big` and `benchmark`.

| Folder | Binary (sha256) | Settings |
|---|---|---|
| `A-published-*` | June 2026 binary `f0033c13…` (both sessions) | defaults: 60-s pods, GPU counts, run until drained |
| `C-nogpu-*` | `kcs-yamlsim-horizon` `cab32545…` (commit 5080669) | `KCS_GPU=0` |
| `B-placement-*` | same | `KCS_GPU=0 KCS_DURATION=10000000 KCS_HORIZON=120`: pods never finish, stop after 120 simulated s |

`RUN_INFO` records commit, image, binary hash and settings. C and B ran with commit
5080669, A with ea4e2dd (the module fix below); the kcs code paths they use are the
same. Scripts and console logs: `kcs_check_run.sh`, `kcs_check_A.sh`, `*.log`.

`failed-first-attempt/`: the first A runs passed the new `--gpu`/`--horizon` flags to
the June binary, which rejected them; the module then reported 0 unscheduled pods
for runs that had not simulated anything (run time 1–4 s). Commit ea4e2dd passes the
flags only when they differ from the defaults and counts every pod of a failed run
as unscheduled. No published run had failed (no "returned non-zero" in their logs).

## Results (`python3 utils/repro/kcs_check_summary.py results-repro/kcs-check-20261109`)

- A reproduces the October costs: run time −4.5…+8.3 %, CPU −4.5…+5.3 %, memory
  −6.5…+5.7 % (points ≥ 5 s / 0.1 GB); 0 unscheduled.
- C (no GPU counts): 0 unscheduled; relative to A, run time 0.83–1.00, CPU time
  0.33–0.67, memory 0.93–1.03.
- B (placement only): 33.6–96.8 % of the pods unscheduled over all runs (100 nodes
  33.6 %, 500 nodes 93.7 %, 80.1 % from 800 nodes on). At 300 nodes one run left
  63.3 % and two 96.8 % (the queue order of equal-priority pods is not fixed). At
  1,213 nodes the metrics show 1,407 pods running, about one per node, and 5,657
  pending at every record after the first tick: the queue stops at the first pod
  that fits no node. On the benchmark (400 small pods, 4 nodes) all pods fit and B
  leaves none unscheduled.
