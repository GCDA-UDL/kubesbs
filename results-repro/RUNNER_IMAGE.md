# Runner image of the published runs (checked 2026-11-09 on the reference host)

All checks on `spoofing-gcd` (2× Xeon Silver 4210R), the host of the June and
October 2026 sweeps.

## Same image in both sessions

```
$ docker image inspect 49601a9c8550 --format 'id={{.Id}} digests={{.RepoDigests}} tags={{.RepoTags}} created={{.Created}}'
id=sha256:49601a9c8550dd83012a730d2acef735151dce05b1062833f35e81179dbe7adf
digests=[thesmuks/k8s-sims@sha256:162f8e963bc29eb224bf0f1f3110e7b7d9159fdf957c7894d8275a500d015ed4]
tags=[thesmuks/k8s-sims:latest] created=2025-07-05T20:28:03+02:00

$ docker inspect k8s-sims-bigall --format '{{.Image}} {{.Config.Image}} {{.State.StartedAt}} {{.State.FinishedAt}}'
sha256:49601a9c8550dd83012a730d2acef735151dce05b1062833f35e81179dbe7adf thesmuks/k8s-sims:latest
2026-06-15T14:08:33Z 2026-06-16T11:27:15Z
```

- The October runs record `image_id=sha256:49601a9c…` in their `RUN_INFO`.
- The container of the June big sweep (`k8s-sims-bigall`, 15–16 June 2026) is still
  on the host and records the same image ID.
- That image's registry digest is `sha256:162f8e96…`, the digest `run_sweep.sh` pins.
- The host also holds an older, untagged image (`8bfd32231c49`, digest
  `sha256:e121d7b3…`, built 2025-06-20) that no published run used.

## Tool versions inside the image

```
$ docker run --rm --entrypoint sh <image> -c 'kwokctl --version; skctl --version; kind version'
kwokctl version v0.7.0 go1.24.4 (linux/amd64)
skctl 2.3.1
kind v0.29.0 go1.24.4 linux/amd64
```

KWOK's control plane: `modules/kwok/module.sh` passes `--kind-node-image
kindest/node:v1.29.0`, which only the kind runtime uses, and does not set
`KWOK_KUBE_VERSION`. With dockerd running (as in the runner), kwokctl picks its
docker runtime and its default Kubernetes version:

```
$ kwokctl create cluster --name t --kind-node-image kindest/node:v1.29.0 --dry-run
… registry.k8s.io/kube-apiserver:v1.33.0, kube-controller-manager:v1.33.0,
  kube-scheduler:v1.33.0, etcd:3.5.21-0, kwok:v0.7.0
```

So KWOK ran Kubernetes 1.33 in the cost sweep (both sessions), and 1.29 in the
fidelity study, which sets `KWOK_KUBE_VERSION=v1.29.0`. Kubemark, SimKube and vanilla
use `kindest/node:v1.29.0`; KSS runs its v0.4.0 images.

## OpenSimulator binary

`modules/opensim/cmd` (the same file on the host, sha256
`92f0799fae281ee27832c254941adb2cfc65e1dea4eb5dc473c8432c27042301`): Go build info
`vcs.revision=c11c72ed298fa8b2174fa94394fb32c5c5e03478`,
`vcs.time=2023-04-25T02:51:22Z`, `vcs.modified=true` (built from a locally modified
tree); it contains the `open-gpu-share` plugin (`GpuSharePlugin`).

## kcs binary

`modules/kcs/kcs-yamlsim` on the host, built 2026-06-15 from commit 55e4108 with the
driver of `modules/kcs/sim`: sha256
`f0033c13cf8dafb8029a848752385c63f2f1a3b5b92490e0fed8f29928b92770` (used by both
sessions; see `kcs-check-20261109/`).
