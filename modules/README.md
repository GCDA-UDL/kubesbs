# Modules
This folder contains the modules that are used by the simulation framework.
The simulation framework uses a modular approach to provide flexibility and extensibility.
Each module is designed to be independent and can be easily integrated into the framework.
Modules are separated into different folders, each containing a bash script named `module.sh`. The `module.sh` file is loaded by the framework when the module is activated.

## Available modules

| Module | Simulator | Status |
|---|---|---|
| `kwok` | KWOK (lightweight pods) | active (in `SIM_MODULES`) |
| `opensim` | OpenSimulator (Alibaba) | active |
| `kube-sched` | Kubernetes Scheduler Simulator | active |
| `simkube` | SimKube (trace replay) | active |
| `kubemark` | Kubemark (hollow nodes) | active |
| `k8ssim` | K8sSim — **Volcano** scheduler | opt-in (build binary) — see [k8ssim/README.md](k8ssim/README.md) |
| `kcs` | pfn k8s-cluster-simulator (discrete-event) | opt-in (build binary) — see [kcs/README.md](kcs/README.md) |
| `vanilla` | Real Kubernetes (kind) | experimental |
| `real` | Real cluster for the fidelity study (`PROVIDER=k3d`: one k3s node per trace node, allocatable = scaled trace capacity) | opt-in — dataset from `utils/scale_base.py`, per-pod records with `POD_RECORDS_DIR` |
| `template` | Copy-paste template for new modules | — |

The active list consumed by `kube-director.sh` lives in the top-level `SIM_MODULES`
file; per-module status and dependencies are documented in `SIM_MODULES.md`.

## Adding a module

Copy `template/module.sh`, implement the `create_cluster` / `cluster_setup` /
`deploy_objects` / `watch_pod_scheduling` / `cleanup_cluster` hooks, add the mode
name to `kube-run.sh`'s accepted-modes regex (and `kube-director.sh` if it needs a
non-default data path), then add it to `SIM_MODULES` to include it in batch runs.
The `opensim`, `k8ssim`, and `kcs` modules are worked examples of the
process-under-cgroup pattern (a single binary measured via its own cgroup).
