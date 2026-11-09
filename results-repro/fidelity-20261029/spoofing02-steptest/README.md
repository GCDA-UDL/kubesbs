# Step test of the real cluster on spoofing02 (2026-10-29/30)

Scale-up test of the local real cluster (`modules/real`, k3d, k3s v1.29.0) on the
W-3245 server (16c/32t, 192 GB, shared with other users), beyond the 10–100 nodes of
the fidelity matrix. Copied from `~/kubesbs-fidelity/results/` on that host on
2026-11-09. Not part of the fidelity table; the paper quotes it in the paragraph
"Cost of the real cluster" of the fidelity section.

## `step-test/` — one run per size: 200, 300, 500 nodes (2026-10-29 19:10 → 10-30 10:09)

- `run.sh`: the script. A sampler writes `mem.log` every 10 s (MemAvailable,
  k3d containers, their memory, 1-min load) and deletes the cluster if MemAvailable
  drops below 20 GB (it never did: the minimum was 57 GB).
- `real-<N>.csv`, `real-<N>.log`: KubeRun rows and harness logs (cgroups v1 on this
  host, so the cost columns are 0).
  - 200 nodes: 2,094 pods, 21 unscheduled, 459 s.
  - 300 nodes: hit the 1-hour limit at 20:27 (`timeout_reached=1`) with 1,704 pods
    still pending; the pod records collected afterwards show 2,941 of 2,967 pods bound.
    The load average reached 5,383 at 20:29 (`mem.log`), and the run's clean-up
    lasted until 09:06 the next morning.
  - 500 nodes: k3d could not start the cluster (run time 0).
- `pods-real-k3d-s02-<N>-1.csv`, `*.watch.csv`: per-pod records of the 200- and
  300-node runs.
- `work/k3d-nodes-<N>.yaml`: the generated k3d configurations.

## `second-200/` — a second 200-node run (2026-10-30 11:41 → 12:03)

- `run200.sh`: the script, meant to repeat 200 nodes three times. A sampler writes
  `load.log` every 10 s and, when the 1-minute load average exceeds the limit given
  on the command line (1,500), writes `GUARD` to `progress`, kills the run and deletes
  the cluster.
- `progress`: the guard fired at 11:46:16 at a load of 1,595.93 (32 threads).
- `real-200.log`: the last harness lines show 2,048 pods still pending
  (`Current pending count: 2048`); `real-200.csv` is the incomplete row of the
  killed run.
- `load-start.txt`, `load-end.txt`: `uptime` (load 2.3 before, 9 users logged in)
  and GPU utilisation; `input.sha256`: checksums of the dataset; `cleanup.log`:
  the deletion of the cluster.
