# kcs — pfn k8s-cluster-simulator module

[`pfnet-research/k8s-cluster-simulator`](https://github.com/pfnet-research/k8s-cluster-simulator)
is Preferred Networks' **discrete-event** Kubernetes scheduler simulator. Unlike
the kube-scheduler-based modules (kube-sched, kwok) it models pod **execution
over simulated time** — each pod runs for a configurable duration and then frees
its resources — so a scheduler is evaluated against a *temporal* workload, very
cheaply (no containers, no API server).

It complements the existing simulators: kube-sched/kwok test placement on a live
(fake) control plane; k8ssim covers Volcano; kcs adds a pure event-driven
scheduler simulator with a programmable workload timeline.

## Reproducible build (pinned)

- Upstream: `https://github.com/pfnet-research/k8s-cluster-simulator`
- **Pinned commit: `55e4108275b4704bc35dfc4eb4774f6d1be597c3`** (2019-04-15)
- GOPATH-era project (no `go.mod`; `dep` + **vendored** deps) → build in legacy mode.

```sh
bash modules/kcs/build.sh           # -> modules/kcs/kcs-yamlsim
# or manually:
#   clone @ 55e4108, copy modules/kcs/sim/{main,submitter}.go into cmd/yamlsim/,
#   GO111MODULE=off go build -o kcs-yamlsim ./cmd/yamlsim
```

Verified build: Go 1.24.4, GOPATH mode, ~13 s, 37 MB binary. Not committed
(build from source). Resolution order: `$K8S_CLUSTER_SIM_BIN` →
`modules/kcs/kcs-yamlsim` → `/usr/local/bin/kcs-yamlsim` → `/tmp/kcs-yamlsim`.

## Custom entry point

The upstream `example` hard-codes a random workload in Go. `modules/kcs/sim/`
replaces it with:
- **`submitter.go`** — reads the toolkit's standard `pods-<N>.yaml` (Alibaba k8s
  Pods) and submits each once, synthesising the `simSpec` annotation the
  simulator needs (one phase of `--duration` seconds at the pod's requested
  cpu/memory/`nvidia.com/gpu`; the Alibaba `alibabacloud.com/gpu-count`
  annotation becomes `nvidia.com/gpu`). Then it terminates so `Run` returns.
- **`main.go`** — wires a `GenericScheduler` (GeneralPredicates +
  BalancedResourceAllocation + LeastRequested) with the YAML submitter; flags
  `--config`, `--pods`, `--duration`.

## How it runs (no new dataset needed)

kcs reuses the **standard** `data/<size>/vanilla` datasets directly:
- `nodes-<N>.yaml` → `kcs_config.py` generates the pfn `config.yaml` (k8s Node
  resources pass through verbatim; GPU annotation → `nvidia.com/gpu`).
- `pods-<N>.yaml` → the workload.

Integration mirrors `opensim`/`k8ssim`: the binary runs inside the `/sys/fs/cgroup/kcs`
cgroup; `kube-run.sh`'s `metric_collector` reads its `cpu.stat`/`memory.current`
(cgroup v2). Unscheduled = the final `Queue.PendingPodsNum` from the JSON metrics
log (pods that never left the queue).

## Usage

```sh
# duration = simulated seconds each pod runs (default 60); override with KCS_DURATION
./kube-run.sh -m kcs -e ./data/small/vanilla -n 1 -o ./results/kcs.csv
```

### What the default run simulates, and the options that change it

By default (`KCS_DURATION=60`, `KCS_GPU=1`, `KCS_HORIZON=0`) every pod runs for 60
simulated seconds and then frees its node, the trace's GPU counts become
`nvidia.com/gpu` requests and capacities, and the run ends only when every pod
has run and finished. kcs's scheduler takes the pods in queue order and stops at
the first pod that fits no node until a later tick (upstream
`pkg/scheduler/generic_scheduler.go`), so a pod that does not fit blocks the pods
behind it until running pods finish. The final pending count of a default run is
therefore always 0: it does not measure the same outcome as the tools that place
each pod once and stop.

- `KCS_GPU=0` drops the GPU counts of nodes and pods, as the other tools see
  only CPU and memory.
- `KCS_HORIZON=<s>` stops the simulation after `s` simulated seconds. With
  `KCS_DURATION` larger than the horizon no pod finishes, and the pods pending
  at the end are those kcs could not place.

`utils/repro/run_sweep.sh` forwards these variables to the runner container and
records them, with the sha256 of the binary, in `RUN_INFO`.

Opt-in (not in the default `SIM_MODULES`): needs the binary built. `kube-director.sh`
maps `kcs` to the `vanilla/` data path, so it can be added to a custom `SIM_MODULES`.

## Verified results

`data/small/vanilla` = 100 nodes / **1067 pods**, container on Docker-Desktop/WSL2 (cgroup v2):

| metric | value |
|---|---|
| pods | 1067 |
| unscheduled (final pending) | **0** |
| wall time | ~0.5 s |
| cpu | 0.53 s |
| memory peak (`memory.peak`) | **30.4 MB** |

Note: like the other pure simulators, kcs finishes faster than `kube-run.sh`'s
1 s `memory.current` sampling, so the harness CSV under-reports memory as
`0.00 GB`; `/sys/fs/cgroup/kcs/memory.peak` gives the real ~30 MB.
