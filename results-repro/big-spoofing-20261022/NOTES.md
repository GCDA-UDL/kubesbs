# Big-sweep re-run, part 1 (2026-10-22/24)

`utils/repro/run_sweep.sh` with `DATASET=big`, the six simulators of
`results-repro/big-all`, 3 runs each, on the reference server (`RUN_INFO`).

**Valid here:** `opensim.csv`, `kwok.csv`, `kube-sched.csv` (36 rows each). They
finished on 2026-10-23 before 03:07 UTC.

**Discarded (`discarded/`):** `simkube.csv` (1 row) and `kubemark.csv` (19 rows).

- From 2026-10-23 03:08 UTC the site DNS stopped answering containers
  (`i/o timeout` towards 172.23.32.1). SimKube could not pull images and stopped
  after one run; Kubemark got no hollow nodes and left every pod unscheduled.
- From about 08:00 UTC Kubemark at 700 nodes overflowed the host neighbour (ARP)
  table (`gc_thresh3=1024`, `dmesg: neighbor table overflow`), which cut network
  access for every container on the host. One run then waited 21 h in the per-pod
  event scan. The sweep was stopped on 2026-10-24 08:34 CEST; kcs never ran.

SimKube, Kubemark and kcs were re-run in `../big-spoofing-20261024` after raising
`gc_thresh1/2/3` to 4096/8192/16384 and fixing the time limit (commit `a16354c`).
The comparison of the combined re-run with `big-all` is in
`../big-spoofing-20261024/COMPARE-big.txt`.
