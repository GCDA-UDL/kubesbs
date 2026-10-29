# Real clusters on Google Compute Engine (fidelity study)

The `real` module with `PROVIDER=gcp` builds, for each run, a Kubernetes cluster of
one Compute Engine VM per trace node (k3s agent) plus a control-plane VM (k3s
server, embedded etcd), with the same k3s and kubelet flags as the local k3d
clusters (`utils/real_k3d.py`): each node is named after its trace node and its
allocatable equals the scaled trace capacity. GKE is not used: the study needs full
control of the scheduler and kubelet configuration.

| Piece | Default | Notes |
|---|---|---|
| Node VMs | `n1-standard-1`, 10 GB standard disk, no public IP | largest scaled node: 640m CPU, 2 GiB |
| Control plane | `n1-standard-8`, 30 GB balanced disk | embedded etcd |
| Runner | `n1-standard-2`, public IP for SSH | runs `kube-run.sh` in tmux, same zone |
| Network | `default` VPC + Cloud NAT | nodes download k3s and the pause image |
| Safety | every VM deletes itself after 3 h (runner 8 h) | `GCP_MAX_RUN` |

## One-time setup (Google Cloud console)

1. Create a project and link a billing account (a free-trial account must be
   upgraded to a full account to run this many vCPUs at once).
2. Enable the Compute Engine API.
3. Quotas: `CPUs` in the region (default `us-central1`) >= nodes + 10.
4. Create a service account with roles **Compute Admin** and **Service Account
   User**, add a JSON key, and copy it to the host that will launch the runs
   (`chmod 600`). Delete the key when the study is over.
5. Optional but recommended: a budget alert on the billing account.

## Run

```bash
export GCP_PROJECT=<project-id> GCP_KEY_FILE=~/.config/kubesbs-gcp-key.json
infra/gcp/run-fidelity.sh start 100 3      # 3 runs of the 100-node dataset
infra/gcp/run-fidelity.sh status
infra/gcp/run-fidelity.sh fetch            # -> results/fidelity-gcp-<date>/
infra/gcp/run-fidelity.sh teardown         # cluster, runner and NAT
```

The dataset must exist in `data/fidelity/vanilla/` (`utils/scale_base.py`, then
`utils/kube-gen.py -c N -i N` per scale). Each run creates and deletes its own
cluster; `infra/gcp/cluster.sh status` lists anything left.

Cost of 3 runs at 100 nodes: about 100 VMs x 3 x ~10 min plus the control plane,
runner and NAT, i.e. roughly USD 10-20 at on-demand prices (check the pricing
calculator for the chosen region).
