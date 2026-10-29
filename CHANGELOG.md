# Changelog

All notable changes to KubeSBS (formerly the GCDA fork of k8s-sims). The original
toolkit by Matias Medina (TFG UdL 2025) is tagged **`v0.1`** and is the baseline below.

## [v0.4.0] — Fidelity study (2026-10-29)

### Added

- `modules/real`: a real Kubernetes cluster as a KubeRun module. `PROVIDER=k3d` (default)
  runs one k3s v1.29 node per dataset node as k3d containers on the host, named after
  the trace node, with its allocatable set to the node's capacity through the kubelet's
  `system-reserved` (`utils/real_k3d.py` renders the config and verifies the live
  allocatable before every run). `PROVIDER=gcp` creates one Compute Engine VM per node
  (`infra/gcp/`, not yet run against GCP). `REAL_PLATFORM` labels the runs of each host.
- `utils/scale_base.py`: scales the base trace (CPU / 200, memory / 512 by default) so
  that a real node fits on one host.
- Per-pod records for every tool with a Kubernetes API: set `POD_RECORDS_DIR` and
  KubeRun writes `pods-<tool>-<platform>-<nodes>-<rep>.csv` (node, creation time from
  a watcher with ms resolution, `Scheduled` event time) — `utils/collect_pods.py`,
  `utils/watch_pods.py`.
- `utils/fidelity.py`: pairwise comparison of runs (agreement after matching identical
  nodes, Wasserstein-1 of the per-node occupancy, unscheduled pods, latency).
- `utils/repro/make_fidelity_dataset.sh` and `utils/repro/fidelity_report.py`: the
  dataset, table and figure of the paper's fidelity section.
- `results-repro/fidelity-20261029/`: 36 runs (real cluster on two servers + KWOK,
  10–100 nodes, 3 runs each) with `NOTES.md` and `DATASET.sha256`.

### Changed

- `modules/kwok`: `kwokctl` 0.7.0 has no `--kube-version`; the module documents that it
  reads `KWOK_KUBE_VERSION` from the environment.

### Notes

- v0.3.0 is described below but was never tagged; v0.4.0 is the first tag after v0.2.4.

## [v0.3.0] — KubeSBS (2026-10-22)

First release under the **KubeSBS** name. The repository was renamed from
`GCDA-UDL/k8s-sims` to `GCDA-UDL/kubesbs` on 2026-10-26; GitHub redirects the old
URLs, clones and remotes. The earlier k8s-sims Zenodo record was deleted on
2026-06-29; this release is archived on Zenodo under a new DOI.

### Renamed and metadata

- Title, `README.md`, `CITATION.cff` and `.zenodo.json` renamed to "KubeSBS: a
  reproducible measurement framework for Kubernetes cluster simulators";
  version 0.3.0 (0.2.5 was never tagged).
- Author list and order: Medina, Tomàs, Lérida, Guirado, da Silva (corresponding).
  Affiliation: SEMBAC, Universitat de Lleida.

### Added

- `utils/repro/`: `run_sweep.sh` (containerised re-run of any dataset and set of
  simulators, writing `RUN_INFO` with host, commit and image), `compare_runs.py`
  (new run vs. reference, per simulator and node count), and the two scripts that
  generate the paper figures (`make_benchmark_bars.py`, `make_paper_plots.py`).
- `results-repro/benchmark-all/`: small-scale benchmark (4 nodes, 400 pods), six
  simulators + vanilla Kubernetes, 3 runs each (2026-06-17).
- `results-repro/benchmark-spoofing-20261022/`: pre-release re-run of that benchmark
  with `utils/repro/run_sweep.sh` on the same server and runner image; it matches
  the reference (see `utils/repro/README.md` and `COMPARE.txt` in that folder).
- `results-repro/big-spoofing-20261022/` + `big-spoofing-20261024/`: re-run of the
  big sweep (6 simulators, 216 runs) on the same server; it matches `big-all`
  (`NOTES.md` and `COMPARE-big.txt`). The SimKube and Kubemark rows of the first
  part are kept under `discarded/`: they broke during a DNS outage.
- `utils/trace-convert/download_traces.sh`: fetches the Alibaba, Borg and Azure
  traces (and Philly with `--philly`).
- `utils/trace-convert/philly2base.py`: Microsoft Philly GPU-trace converter
  (validated on the synthetic sample only).
- Synthetic Borg and Azure sample CSVs committed under
  `utils/trace-convert/samples/` (they were gitignored).
- `run_sweep.sh`: `DNS` option, `MAX_TIME` default of 7200 s, and a preflight
  that stops when containers cannot resolve names or when the host neighbour (ARP)
  table limit is too low for Kubemark at scale (see `utils/repro/README.md`).

### Fixed

- `kube-run.sh`: the maximum simulation time (`-x`) is also checked inside the
  per-pod event scan of the scheduling wait. Before, one pass over thousands of
  pending pods could run for hours without ever checking it (a Kubemark run at
  700 nodes waited 21 h during the 2026-10-23 network outage).
- SimKube module: kube-prometheus is pinned to commit `8355ca5` (v0.17.0-44), the
  clone used by every published run; before, a fresh clone took the moving
  default branch.
- `run_sweep.sh`: the runner image is pinned by digest
  (`thesmuks/k8s-sims@sha256:162f8e96…`), the image used for every published run;
  the `:latest` tag can move.

### Known issue (documented, harness unchanged)

- The scheduling wait in `kube-run.sh` ends a run when every pending pod has a
  `FailedScheduling` event, and it checks this with one `kubectl get events` call
  per pending pod and pass. For Kubemark at scale (thousands of pods that stay
  pending) that check is 52 % of the measured run time at 400 nodes and 80–82 %
  from 800 nodes (measured from the 2026-10-24 run log). The check cannot simply
  be made faster: Kubemark creates its hollow nodes and the workload pods at the
  same time, so the slow check also gives late-registering nodes time to take
  pods, and a fast check would end runs before they do. All published runs use
  this harness; `utils/repro` reports the phases of each run.

### Shipped in v0.2.4 without a changelog entry

- `results-repro/big-all/`: unified big sweep, six simulators, 100–1200 nodes,
  3 runs each, on one host (2× Xeon Silver 4210R, 40 threads, 128 GB, Rocky Linux 9.3).
- Fixed (opensim): `cgcreate`/`cgexec`/`cgdelete` no longer use `sudo`; inside the
  container the cgroup measurement returned zeros. The opensim big sweep was re-run.

## [v0.2.0 – v0.2.4] — GCDA (2026-06)

Continuation by GCDA (Grupo de Computación Distribuida y Avanzada), Universitat de Lleida of
Matias Medina's toolkit. Verified reproducibility, fixed a silent benchmark bug,
added two simulators and two trace sources. All work was validated on Docker
Desktop / WSL2 (cgroup v2); see `REPRODUCIBILITY_REPORT.md` for evidence.

### Phase 1 — reproducibility

- **Verified** the original benchmark is reproducible: all 5 published simulators
  (kwok, opensim, kube-sched, simkube, kubemark) run end-to-end and the headline
  trends of `summaries/summary.json` hold (kwok/opensim lightest, kubemark/simkube
  heaviest). Full report: `REPRODUCIBILITY_REPORT.md`.
- **Fixed (kubemark): silent scheduling failure.** The hollow-node kubeconfig kept
  `server: https://127.0.0.1:<port>` (the rewrite `sed` was commented out), so no
  fake node registered and every pod stayed Pending while the run still reported
  success. Un-commented the rewrite to the in-cluster Service endpoint; verified
  the hollow node registers and pods schedule (`modules/kubemark/module.sh`).
- **Added `.gitattributes`** forcing LF for shell/py/yaml/conf. The repo shipped
  CRLF with no `.gitattributes`; sourcing those files in the Alpine container from
  a Windows checkout broke them. (This was the only cause of the 2 transient bats
  failures observed.)
- Preserved the original reference summary as `summaries/summary.matias-big.json`.
- Evidence (CSVs, aggregated summary, 13 plots) under `results-repro/`.

### Phase 2 — new simulators (opt-in)

- **K8sSim (Volcano)** — `modules/k8ssim/`. The only simulator covering the
  **Volcano** scheduler (gang/DRF/SLA × LRP/MRP/BRA/BINPACK), closing a gap left
  by the five kube-scheduler-only simulators. Builds from pinned commit `7168cb3`
  (vendored Go). Includes a stdlib-only HTTP driver (`k8ssim_driver.py`) and the
  Volcano scheduling configs. The TFG marked K8sSim "not available" — it is public
  and builds/runs.
- **`kube-gen.py --k8ssim`** — emits the K8sSim Volcano dataset (Node → cluster
  entry, each bin-packed Pod → a Volcano Job) from the same Alibaba base data.
- **Volcano scheduler sweep** — all 20 Volcano configs over a 1067-job Alibaba
  dataset; results in `results-repro/k8ssim/VOLCANO_SWEEP.md`.
- **kcs (pfn k8s-cluster-simulator)** — `modules/kcs/`. Preferred Networks'
  discrete-event scheduler simulator (pinned commit `55e4108`, GOPATH/vendored).
  Custom Go entry point reads the toolkit's standard `pods-<N>.yaml` and
  synthesises pod execution; reuses the existing `vanilla` datasets (no new
  dataset format). Build via `modules/kcs/build.sh`.

### Datasets — new trace sources

- **`utils/trace-convert/`** — converters that emit the existing base manifest
  format, so every simulator and `kube-gen.py` consume them unchanged:
  - `borg2base.py` — Google Borg (`google/cluster-data`, ClusterData2011).
  - `azure2base.py` — Azure (`Azure/AzurePublicDataset` vmtable).
  - `samples/` — tiny synthetic CSVs in the documented schemas for offline tests.

### Assessed, not integrated

- **Q8S** (QEMU/OpenStack heterogeneous-cluster emulator) — infeasible on a
  WSL2 desktop host (needs KVM + OpenStack).
- **Reckon** (`AleSassi/reckon-k8s`) — runnable here (the OVS kernel module ships
  in the WSL2 kernel) but it is a network-fault / consensus-availability emulator,
  not a scheduler simulator, so it does not fit this benchmark's metric model.
  Rationale in `research_notes/.../16_reckon_q8s_feasibility.md` (survey workspace).

### Docs

- New: `REPRODUCIBILITY_REPORT.md`, `CHANGELOG.md`, per-module READMEs
  (`modules/k8ssim`, `modules/kcs`), `utils/trace-convert/README.md`.
- Updated: `README.md` (fork status + documentation map), `ARCHITECTURE.md`
  (structure, module table, generator, glossary), `SIM_MODULES.md` (k8ssim/kcs
  rows), `DATASETS.md` (trace sources), `modules/README.md`, `utils/README.md`.

## [v0.1] — Matias Medina (2025)

Original toolkit: 5 simulators (kwok, opensim, kube-sched, simkube, kubemark),
Alibaba-trace dataset generator (`kube-gen.py`), plotter, Docker Compose
environment, bats/pytest test suites. See `git log v0.1`.
