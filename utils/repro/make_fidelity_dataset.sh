#!/bin/bash
# Dataset of the fidelity study: the Alibaba base trace scaled to fit real k3s
# nodes on one host (CPU / 200, memory / 512, see utils/scale_base.py), then cut
# at each cluster size with kube-gen. Both steps are deterministic: the output
# matches results-repro/fidelity-20261029/DATASET.sha256 byte for byte.
#
# Usage (from the repository root):
#   bash utils/repro/make_fidelity_dataset.sh [OUT_DIR] [SCALES]
#   default: data/fidelity "10 30 60 100"
set -euo pipefail

OUT="${1:-data/fidelity}"
SCALES="${2:-10 30 60 100}"
PY="${PYTHON:-python3}"

"$PY" utils/scale_base.py -o "$OUT/base"
for n in $SCALES; do
    # -c N -i N: one cut of exactly N nodes (with -i 10, kube-gen writes disjoint slices).
    "$PY" utils/kube-gen.py -o "$OUT/vanilla" -c "$n" -i "$n" \
        -n "$OUT/base/nodes.yaml" -p "$OUT/base/pods.yaml" >/dev/null
done
echo "fidelity dataset in $OUT (scales: $SCALES)"
echo "check: (cd $OUT && sha256sum -c ../../results-repro/fidelity-20261029/DATASET.sha256)"
