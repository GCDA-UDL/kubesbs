# Dataset and Generated Data Policy

## Trace sources

The base manifests (`utils/base/{nodes,pods}.yaml`) the generator slices are
derived from the **Alibaba** cluster trace (2023 GPU). Three more public sources
are supported via converters that emit the **same** base format, so every
simulator and `kube-gen.py` consume them unchanged (GCDA addition):

| Source | Origin | Converter |
|---|---|---|
| Alibaba (default) | `github.com/alibaba/clusterdata` | built into `utils/base` |
| Google Borg | `github.com/google/cluster-data` (ClusterData2011) | `utils/trace-convert/borg2base.py` |
| Azure | `github.com/Azure/AzurePublicDataset` (vmtable) | `utils/trace-convert/azure2base.py` |
| Philly (GPU) | `github.com/msr-fiddle/philly-traces` (cluster_job_log) | `utils/trace-convert/philly2base.py` |

Full traces are large (GCS / Azure Blob) and downloaded by the user; tiny
synthetic samples for offline testing live in `utils/trace-convert/samples/`.
See [utils/trace-convert/README.md](utils/trace-convert/README.md).

## Categories

- `data/test/`: small curated smoke-test inputs kept in the repository.
- `data/benchmark/`: benchmark fixtures that are small enough to review and keep.
- `data/small/`, `data/medium/`, `data/big/`: generated or large datasets. These are ignored by default unless explicitly curated.
- `tests/fixtures/results/`: small result CSV fixtures for plotting and summary validation.
- `results/`, `plots/`, temporary validation outputs: generated artifacts, ignored by default.

## Retention policy

Keep only compact fixtures needed for repeatable local validation. Large generated datasets and benchmark outputs should be regenerated, archived outside git, or attached to releases when intentionally preserved.

## Regeneration examples

```bash
python utils/kube-gen.py -o data/small -c 10 -i 5
python utils/kube-gen.py -o data/medium -c 100 -i 25
python utils/kube-gen.py -o data/big -c 400 -i 50
```

The fidelity dataset (real k3s cluster, paper Section "Fidelity Against a Real
Cluster") is the base trace scaled down and cut at 10, 30, 60 and 100 nodes; it is
not committed and regenerates byte for byte:

```bash
bash utils/repro/make_fidelity_dataset.sh     # -> data/fidelity/{base,vanilla}
(cd data/fidelity && sha256sum -c ../../results-repro/fidelity-20261029/DATASET.sha256)
```

For simulator-specific formats, add the relevant flags such as `--kubemark`, `--simkube`, `--open_sim`, or `--k8ssim` (K8sSim Volcano) and record the exact command in the checkpoint log. The `kcs` simulator reuses the standard `vanilla` datasets directly (no flag).

To generate from Google Borg, Azure or Philly traces instead of Alibaba:

```bash
python utils/trace-convert/borg2base.py --machines machine_events.csv --tasks task_events.csv -o data/borg --max-nodes 100
python utils/trace-convert/azure2base.py --vmtable vmtable.csv -o data/azure --max-pods 1000
python utils/trace-convert/philly2base.py --joblog cluster_job_log -o data/philly --max-pods 1000  # GPU-aware (nvidia.com/gpu)
```

## Sensitive data

Do not store secrets, kubeconfigs, private keys, certificates, or real `.env` files in generated dataset directories.
