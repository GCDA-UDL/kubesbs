# Reproduction scripts

Scripts that re-run the published experiments and regenerate the figures from
the CSVs in [`results-repro/`](../../results-repro). Run them from the
repository root.

| Script | Purpose |
|---|---|
| [`run_sweep.sh`](run_sweep.sh) | Runs a dataset over a set of simulators in the runner container and writes `<sim>.csv`, `SIM_MODULES` and `RUN_INFO` (host, commit, image) to the output folder. |
| [`compare_runs.py`](compare_runs.py) | Compares a new run with a reference folder, per simulator and node count. |
| [`make_benchmark_bars.py`](make_benchmark_bars.py) | Bar figure of the small-scale benchmark (6 simulators + vanilla). |
| [`make_paper_plots.py`](make_paper_plots.py) | Line plots of the big sweep (6 simulators, 100–1200 nodes). |

## Reference results

| Folder | Dataset | Simulators | Runs | Host |
|---|---|---|---|---|
| `results-repro/benchmark-all` | `data/benchmark` (4 nodes, 400 pods) | opensim, kwok, kube-sched, simkube, kubemark, kcs, vanilla | 3 | 2× Xeon Silver 4210R (40 threads), 128 GB, Rocky Linux 9.3, cgroups v2; 2026-06-17 |
| `results-repro/big-all` | `data/big` (100–1200 nodes) | opensim, kwok, kube-sched, simkube, kubemark, kcs | 3 | same server, 2026-06-15/17 (opensim re-run after the cgroup fix) |

| Re-run | Result |
|---|---|
| `results-repro/benchmark-spoofing-20261022` (v0.3.0 pre-release, same server, same runner image) | All 7 configurations, 3/3 runs. Unscheduled pods: 0 for every tool except Kubemark (55–70 per run; 40–69 in `benchmark-all`). Run time, CPU time and peak memory within ±11 % for the tools that run longer than a few seconds; kcs and OpenSimulator (1–2 s, < 0.01 GB) match within the 1 s / 0.01 GB resolution. Full table: `COMPARE.txt`. |
| `results-repro/big-spoofing-20261022` (opensim, kwok, kube-sched) + `big-spoofing-20261024` (simkube, kubemark, kcs) | All 216 runs. Unscheduled pods within 0.1 % of the pods for every tool except Kubemark (≤ 6.9 %, within its run-to-run spread). Run time and CPU within −5 … +11 % except SimKube (−43 … +25 %, as large as its spread between repetitions); peak memory within ±12 % except opensim (−11 … +19 %). Part 1 lost SimKube and Kubemark to a DNS outage and an ARP-table overflow (see `NOTES.md` in both folders). Full table: `big-spoofing-20261024/COMPARE-big.txt`. |

Re-run on that server to compare absolute numbers. `run_sweep.sh` pins the
runner image by digest (`thesmuks/k8s-sims@sha256:162f8e96…`, the image of every
published run) and records its image ID in `RUN_INFO`.

For Kubemark at scale, most of the measured run time is the harness checking the
events of each pending pod (CHANGELOG, "Known issue"); report it by phase.

## Re-run the benchmark and compare

```bash
bash utils/repro/run_sweep.sh            # DATASET=benchmark, 7 modules, RUNS=3
python3 utils/repro/compare_runs.py results-repro/benchmark-all results-repro/benchmark-<host>-<date>
```

Run times and resource use depend on the host; the number of unscheduled pods
should match.

## Regenerate the figures

```bash
python3 utils/repro/make_benchmark_bars.py --results results-repro/benchmark-all \
    --out bars_run_time_total_cpu_seconds_memory_peak_gb_unscheduled_pods.png
python3 utils/repro/make_paper_plots.py --results results-repro/big-all --out figures-out
```

Requires `matplotlib`.

## Host requirements for the big sweep

Found while re-running `data/big` on the reference server (2026-10-23/24):

- **Name resolution from containers.** Every simulator cluster pulls images. When
  the site DNS stopped answering containers, SimKube failed and Kubemark left every
  pod unscheduled. `run_sweep.sh` now checks resolution before starting; if it
  fails, pass public resolvers with `DNS="8.8.8.8 1.1.1.1"`.
- **Kernel neighbour (ARP) table.** With the default
  `net.ipv4.neigh.default.gc_thresh3=1024`, Kubemark at ~700 hollow nodes
  overflows the table (`dmesg: neighbor table overflow`) and every container on
  the host loses network access. Raise it before a big Kubemark run:

  ```bash
  sudo sysctl -w net.ipv4.neigh.default.gc_thresh1=4096 \
                 net.ipv4.neigh.default.gc_thresh2=8192 \
                 net.ipv4.neigh.default.gc_thresh3=16384
  ```

  `run_sweep.sh` refuses to run Kubemark on a dataset other than `benchmark`/`test`
  while `gc_thresh3` is below 8192 (`PREFLIGHT=0` skips both checks).
- **A time limit.** The scheduling wait queries the events of every pending pod
  in turn; with thousands of pods and a slow API server one pass can take hours.
  `MAX_TIME` (default 7200 s, about 3× the longest June-2026 run) is now also
  checked inside that pass.
