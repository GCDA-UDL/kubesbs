#!/usr/bin/env bash
# Containerised sweep runner (KubeSBS reproduction package).
# Generalises the June-2026 unified sweep so any dataset and any set of
# simulators can be re-run with one command. Run from the repository root:
#
#   bash utils/repro/run_sweep.sh                    # benchmark: 6 simulators + vanilla, 3 runs
#   DATASET=big MODULES="opensim kwok kube-sched simkube kubemark kcs" \
#     bash utils/repro/run_sweep.sh                  # the big sweep (several hours)
#
# Variables (all optional):
#   DATASET        data/<DATASET> to run            (default: benchmark)
#   MODULES        space-separated simulators       (default: opensim kwok kube-sched simkube kubemark kcs vanilla)
#   RUNS           repetitions per configuration    (default: 3)
#   OUT            output folder                    (default: results-repro/<DATASET>-<host>-<yyyymmdd>)
#   IMAGE          runner image                     (default: the digest of thesmuks/k8s-sims used for
#                                                    every published run; the :latest tag can move)
#   MEM_THRESHOLD  host memory threshold, percent   (default: 95)
#   MAX_TIME       max seconds per simulation       (default: 7200; -1 = no limit. The longest
#                                                    June-2026 run took 2161 s)
#   DNS            space-separated DNS servers for the runner container, e.g. "8.8.8.8 1.1.1.1"
#                  (default: the host's resolver)
#   PREFLIGHT      1 = check name resolution and the host ARP table limit first (default: 1)
#
# Compare the new run with the published reference afterwards, e.g.:
#   python3 utils/repro/compare_runs.py results-repro/benchmark-all "$OUT"
set -euo pipefail

DATASET="${DATASET:-benchmark}"
MODULES="${MODULES:-opensim kwok kube-sched simkube kubemark kcs vanilla}"
RUNS="${RUNS:-3}"
IMAGE="${IMAGE:-thesmuks/k8s-sims@sha256:162f8e963bc29eb224bf0f1f3110e7b7d9159fdf957c7894d8275a500d015ed4}"
MEM_THRESHOLD="${MEM_THRESHOLD:-95}"
MAX_TIME="${MAX_TIME:-7200}"
DNS="${DNS:-}"
PREFLIGHT="${PREFLIGHT:-1}"
OUT="${OUT:-results-repro/${DATASET}-$(hostname -s)-$(date +%Y%m%d)}"

[[ -f kube-director.sh ]] || { echo "Run this from the repository root."; exit 1; }
[[ -d "data/${DATASET}" ]] || { echo "Dataset not found: data/${DATASET}"; exit 1; }

dns_flags=()
for d in $DNS; do dns_flags+=(--dns "$d"); done

neigh() { cat "/proc/sys/net/ipv4/neigh/default/$1" 2>/dev/null || echo unknown; }

if [[ "$PREFLIGHT" = "1" ]]; then
  echo "==> Preflight: name resolution from a container"
  # Every simulator cluster pulls images; without DNS the runs fail or leave
  # every pod unscheduled.
  if ! docker run --rm "${dns_flags[@]}" --entrypoint nslookup "$IMAGE" quay.io 2>&1 | grep -q '^Name:'; then
    echo "Containers cannot resolve quay.io, so images cannot be pulled." >&2
    echo "Fix the host DNS or set DNS=\"8.8.8.8 1.1.1.1\"." >&2
    exit 1
  fi
  # Kubemark runs hundreds of hollow-node pods; past the kernel's neighbour
  # (ARP) table limit, every container on the host loses network access.
  if [[ " $MODULES " == *" kubemark "* && "$DATASET" != "benchmark" && "$DATASET" != "test" ]]; then
    thresh3="$(neigh gc_thresh3)"
    if [[ "$thresh3" =~ ^[0-9]+$ ]] && (( thresh3 < 8192 )); then
      echo "net.ipv4.neigh.default.gc_thresh3=$thresh3 is too low for Kubemark at this scale." >&2
      echo "Raise it first (as root):" >&2
      echo "  sysctl -w net.ipv4.neigh.default.gc_thresh1=4096 net.ipv4.neigh.default.gc_thresh2=8192 net.ipv4.neigh.default.gc_thresh3=16384" >&2
      exit 1
    fi
  fi
fi

mkdir -p "$OUT"
OUT_ABS="$(cd "$OUT" && pwd)"

if [[ " $MODULES " == *" kcs "* && ! -f modules/kcs/kcs-yamlsim ]]; then
  echo "==> Building kcs-yamlsim (static linux/amd64)"
  docker run --rm -v "$PWD":/work -w /work -e CGO_ENABLED=0 golang:1.24-alpine \
    sh -c "apk add --no-cache git bash >/dev/null && bash modules/kcs/build.sh"
  [[ -f modules/kcs/kcs-yamlsim ]] || { echo "kcs build failed"; exit 1; }
fi

# The module list and the run provenance live next to the results.
printf '%s\n' $MODULES > "$OUT_ABS/SIM_MODULES"
{
  echo "date=$(date -Iseconds)"
  echo "host=$(hostname)"
  echo "commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "image=${IMAGE}"
  docker image inspect --format 'image_id={{.Id}}' "$IMAGE" 2>/dev/null || echo "image_id=unknown"
  echo "dataset=${DATASET}"
  echo "modules=$(paste -sd' ' "$OUT_ABS/SIM_MODULES")"
  echo "runs=${RUNS}"
  echo "max_time=${MAX_TIME}"
  echo "dns=${DNS:-host}"
  echo "neigh_gc_thresh=$(neigh gc_thresh1)/$(neigh gc_thresh2)/$(neigh gc_thresh3)"
  echo "cpus=$(nproc)"
  echo "mem_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
} > "$OUT_ABS/RUN_INFO"
cat "$OUT_ABS/RUN_INFO"

kcs_mount=()
if [[ -f modules/kcs/kcs-yamlsim ]]; then
  kcs_mount=(-v "$PWD/modules/kcs/kcs-yamlsim":/usr/local/bin/kcs-yamlsim:ro)
fi

# The full output is large (dockerd logs); keep only the harness lines, which
# utils/repro/run_phases.py turns into per-phase run times.
full_log="$OUT_ABS/.run.log"
set +e
docker run --rm --privileged --cgroupns host \
  "${dns_flags[@]}" \
  -e CONTAINERIZED=true \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  -v "$PWD/data":/data:ro \
  -v "$PWD/modules":/modules:rw \
  -v "$PWD/kube-director.sh":/kube-director.sh:ro \
  -v "$PWD/kube-run.sh":/kube-run.sh:ro \
  -v "$PWD/utils":/utils:rw \
  -v "$OUT_ABS/SIM_MODULES":/SIM_MODULES:ro \
  "${kcs_mount[@]}" \
  -v "$OUT_ABS":/results \
  "$IMAGE" \
  -e "/data/${DATASET}" -n "$RUNS" -s 0 -o /results -t "$MEM_THRESHOLD" -x "$MAX_TIME" \
  2>&1 | tee "$full_log"
rc=${PIPESTATUS[0]}
set -e
grep -E '^\[[0-9-]+ [0-9:]+\] \[(INFO|ERROR|WARN)' "$full_log" > "$OUT_ABS/harness.log" || true
rm -f "$full_log"
(( rc == 0 )) || { echo "Runner exited with status $rc" >&2; exit "$rc"; }

echo "==> Done. Results in $OUT:"
ls -la "$OUT"
