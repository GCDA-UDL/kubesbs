

# KubeSBS — a reproducible measurement framework for Kubernetes cluster simulators

_Formerly **k8s-sims** (repository renamed from `GCDA-UDL/k8s-sims` to `GCDA-UDL/kubesbs` on 2026-10-26; old links and clones redirect). DOI: assigned by Zenodo on the v0.3.0 release (pending)._

KubeSBS runs a selected number of Kubernetes simulators on the same trace-derived
workloads and measures their CPU, memory, run time and scheduling outcomes. The
original guide for running each simulator follows below.

## About this fork (GCDA)

This is the **GCDA** (Grupo de Computación Distribuida y Avanzada, Universitat de Lleida)
continuation of Matias Medina's original toolkit (TFG UdL 2025, tagged **`v0.1`**).
On top of the original five simulators it adds:

- **Reproducibility verification + fixes** — the benchmark was confirmed
  reproducible on Docker Desktop / WSL2 (cgroup v2); a silent **kubemark**
  scheduling bug was fixed, `.gitattributes` added. See
  [REPRODUCIBILITY_REPORT.md](REPRODUCIBILITY_REPORT.md).
- **Two new simulators** (opt-in): **K8sSim** — the only one covering the
  **Volcano** scheduler ([modules/k8ssim](modules/k8ssim/README.md)) — and
  **kcs**, Preferred Networks' discrete-event simulator
  ([modules/kcs](modules/kcs/README.md)). 7 simulators total.
- **Two new workload sources** beyond Alibaba: **Google Borg** and **Azure**
  trace converters ([utils/trace-convert](utils/trace-convert/README.md)).

### Documentation map

| Topic | Document |
|---|---|
| Run the simulators (this guide) | `README.md` |
| Architecture & code layout | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Simulator inventory & status (incl. opt-in k8ssim/kcs) | [SIM_MODULES.md](SIM_MODULES.md) |
| Datasets, trace sources & retention | [DATASETS.md](DATASETS.md) |
| Reproducibility report (Phase 1) | [REPRODUCIBILITY_REPORT.md](REPRODUCIBILITY_REPORT.md) |
| Changes since v0.1 | [CHANGELOG.md](CHANGELOG.md) |
| K8sSim / Volcano module | [modules/k8ssim/README.md](modules/k8ssim/README.md) |
| kcs (pfn) module | [modules/kcs/README.md](modules/kcs/README.md) |
| Borg / Azure trace converters | [utils/trace-convert/README.md](utils/trace-convert/README.md) |
| Volcano scheduler sweep results | [results-repro/k8ssim/VOLCANO_SWEEP.md](results-repro/k8ssim/VOLCANO_SWEEP.md) |
| Re-run the published sweeps, compare runs, regenerate the paper figures | [utils/repro/README.md](utils/repro/README.md) |

> The original five simulators (kwok, opensim, kube-sched, simkube, kubemark) run
> via `docker compose up` / `kube-director.sh` as below. The two new simulators
> are opt-in (need a binary built from source) — see their module READMEs.

## Citing

If you use KubeSBS, please cite it via the metadata in
[`CITATION.cff`](CITATION.cff). The earlier k8s-sims Zenodo record was deleted;
the Zenodo DOI of KubeSBS will be added here once minted.

> Corresponding author: Vitor da Silva (vitor.dasilva@udl.cat).

Attribution for the original work and bundled/integrated simulators is in
[`NOTICE`](NOTICE). Licensed under Apache-2.0 ([`LICENSE`](LICENSE)).

## Funding

This work has been granted by the Ministerio de Ciencia, Innovación y Universidades (MICIU) AEI/10.13039/501100011033 under contract PID2023-146193OB-I00.

## Original guide

Specs of the computer where the simulations were run.
```
OS: Alpine Linux v3.22
CPU: 2 x Intel(R) Xeon(R) Silver 4210R (40) @ 3.20 Gz
Memory: 128GB DDR4
```
## Required Dependencies
This project requires several tools and languages to be installed on your system. Ensure all dependencies below are properly installed before proceeding.

1. [Go](https://go.dev/doc/install)
2. [Docker](https://docs.docker.com/engine/install/)
	2.1 [Docker Compose](https://docs.docker.com/compose/install/)
3. [make](https://www.gnu.org/software/make/)
4. [Python3.12.3](https://www.python.org/downloads/release/python-3123/) and [requirements.txt](requirements.txt)
5. [Rust 1.86.0](https://www.rust-lang.org/tools/install)
6. skctl: `cargo install skctl`
7. [Alibaba Cluster Traces](https://github.com/alibaba/clusterdata.git)
## Obtain traces
The first step is to clone the clusterdata repository containing Alibaba's production traces.
```sh
git clone https://github.com/alibaba/clusterdata.git
```
Next we are going to use the 2023 dataset.
```sh
cd ./clusterdata/cluster-trace-gpu-v2023
```
Once we are in the proper directory, the csv data needs to be transformed into yaml pod manifest files. For this we execute the `prepare_input` script. But first we need to install the dependencies to execute the script.
```sh
./prepare_input.sh
```
After the script finishes there should be 23 folders, one per each csv file containing the traces.
### Modifying traces
[kube-gen.py](utils/kube-gen.py) is a script that can be used to modify the traces to generate new traces that fit the supported simulators (Vanilla Kubernetes, OpenSimulator, SimKube, Kubemark). For more detail refer to the [README.md](utils/README.md).
## Running simulations
Simulations can be run by setting up the environment step by step or spin up a docker compose for an easy and fast setup.
### Docker Compose
To reproduce the default experiments just deploy the [docker-compose.yaml](docker-compose.yaml) provided. This will pull the proper image and run all the experiments using the [big dataset](data/big).
[.env](.env) cotains variable that can be changed and loaded on the compose.
```sh
docker compose up
```
### Experiment Script
If all the dependencies are installed, the user can opt to run the experiments on the host machine.
This can be done by executing the file [kube-director.sh](kube-director.sh).
```bash
./kube-director.sh
```
Alternatively, to run a single experiment, the user can execute the file [kube-run.sh](kube-run.sh).
```bash
./kube-run.sh -m module_name -d data_path
```
### Manual Approach
- In order to run Alibaba's OpenSimulator refer to [README-OpenSim](modules/opensim/README.md)
- In order to run Kubernetes Scheduler Simulator refer to [README-kube-sched-sim](modules/kube-sched/README.md)
- In order to run SimKube refer to [README-SimKube](modules/simkube/README.md)
- In order to run Kubemark refer to [README-Kubemark](modules/kubemark/README.md)
