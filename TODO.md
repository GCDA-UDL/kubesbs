# TODO

## Deferred — after the experiment/test campaign is complete

- [ ] **Upload datasets + benchmark results to CORA / RDR** (Repositori de Dades
      de Recerca, Dataverse, CSUC). Package: `results-repro/` + the generated
      datasets (Alibaba/Borg/Azure/Philly) + a data README + metadata. Use **CC-BY** for
      data (not Apache). Mint a data DOI and **cross-link it with the software
      DOI** (the forthcoming KubeSBS Zenodo DOI) via related identifiers.
      Deferred on 2026-06-15 by maintainer until the test runs finish.

## Open

- [x] Add **Matias Nicolas Medina Jara**'s ORCID (`0009-0000-2858-4317`) to
      `CITATION.cff` + `.zenodo.json`. (The old published Zenodo record was
      deleted; correct ORCIDs will ship with the KubeSBS re-upload.)
- [x] Funding acknowledgment confirmed by the maintainer (2026-10-22): MICIU
      `PID2023-146193OB-I00` only; nothing else to add.
- [x] **Sample parity:** borg/azure `.csv` samples force-added next to the Philly
      `.json` sample (v0.3.0).
- [x] **Re-run the big sweep** (216 runs): `results-repro/big-spoofing-20261022` +
      `big-spoofing-20261024` match `big-all` (see their `NOTES.md`).
- [x] **Kubemark at scale:** with `gc_thresh3` raised to 16384 Kubemark leaves the same
      share of pods unscheduled as in June, so that share is not a host limit.
- [ ] **Kubemark run time** includes the harness's per-pod event check of the pending
      pods (52 % of the run time at 400 nodes, 80–82 % from 800 nodes; CHANGELOG
      "Known issue"). A correct fix must first wait for the hollow nodes to register
      (or for the pending count to stabilise) and only then apply a fast check;
      otherwise Kubemark runs end before late nodes take pods. Until then, report
      run time split into phases (setup, workload, end-of-run check).
- [ ] **vanilla pre-check:** every vanilla run first tries `data/test/vanilla/cluster-1.yaml`,
      which does not exist, and logs "Cluster setup failed" (results go to `/tmp`, the
      benchmark rows are unaffected). Add the file or skip the pre-check.
- [ ] **Zenodo DOI for KubeSBS** (v0.3.0 was never tagged; the first tag after v0.2.4 is
      v0.4.0): enable the repository in Zenodo's GitHub integration, publish the v0.4.0
      GitHub release, then add the concept DOI to
      `CITATION.cff`, `README.md` and the survey's `k8s-sims` bib entry.
- [ ] **Philly converter — real-trace + GPU run:** `philly2base.py` is validated on
      the synthetic sample only (5 jobs → 2 GPU nodes, 16 GPUs). Download the real
      `cluster_job_log` (`msr-fiddle/philly-traces`, via `download_traces.sh --philly`)
      and run it through a **GPU-aware scheduler** to actually exercise
      `nvidia.com/gpu`; current sims schedule by cpu/memory, so GPU placement is
      untested. Feeds the GPU-scheduling-fidelity sub-study of paper #3 (C1).

### Fidelity study (real cluster) — optional

The paper uses the runs of 2026-10-29 (`results/fidelity-prelim-2026-10-29/SUMMARY.md`):
real k3d on spoofing02 and spoofing-gcd + KWOK, 10–100 nodes, 3 repetitions.

- [ ] *(optional)* **Real cluster beyond 100 nodes on one host.** The measured cost of the
      k3d cluster (spoofing-gcd, cgroup v2) grows as ≈ 0.16·N + 0.00065·N² GB, i.e. ≈ 241 GB
      at 500 nodes, more than spoofing02's 187 GB. In the 2026-10-29 step test on spoofing02
      the CPU gave out first: 200 nodes ran, 300 nodes timed out with a load in the thousands
      (sshd unresponsive until the next morning), 500 nodes never started (local copy:
      `results/fidelity-scaleup-2026-10-29/`). A second 200-node attempt (2026-10-30) was
      stopped by the load guard (load 1,596, 2,048 pods pending), so one host is not reliable
      above ~100 nodes; maintainer decision 2026-10-30: the matrix stays at 10–100 nodes, and
      larger sizes need a multi-host cluster. A lean configuration should remove most of the N² term: flannel off
      (`--flannel-backend=none` + a local `bridge` CNI per node), `--disable-network-policy`,
      `--disable-kube-proxy` (pods are `pause`, no Services). Check at 100 nodes that the
      placement stays within the real-vs-real noise before scaling, and abort on load /
      PSI as well as on `MemAvailable`.
- [ ] *(optional)* **Latency without host saturation.** At 60–100 nodes the emulated cluster
      saturates its host (load 206–308 on 40 threads on spoofing-gcd), so the real latency
      there is an upper bound. Either pin the server container to dedicated cores
      (`docker update --cpuset-cpus`) or run the 100-node point on GCP with one VM per node
      (`infra/gcp/run-fidelity.sh start 100 3`, never tested against GCP yet; user-paid).
- [ ] *(optional)* **Fidelity of other simulators** (kube-scheduler-simulator, SimKube,
      Kubemark, OpenSimulator) with `POD_RECORDS_DIR`; opensim, kcs and k8ssim need
      adapters that write `pods.csv`.
- [x] Archive the fidelity results: `results-repro/fidelity-20261029/` (v0.4.0) and the
      reproduction package `GCDA-UDL/repro-kubesbs` v0.1.0 (2026-10-29), where Docker
      regenerates every paper table byte for byte.

### Paper submission (SIGMETRICS 2027, abstract 4 Jan, paper 11 Jan 2027)

- [ ] **Anonymous artefact** for the double-blind review: anonymous.4open.science copy of
      `GCDA-UDL/repro-kubesbs` (needs the maintainer's GitHub login there). Terms to hide
      include the author names, SEMBAC, Lleida, UdL, GCDA/GCD, `spoofing` (host and
      folder names), the e-mail and the funder. Put its URL in `\artefacturl` (review)
      and in the `anonartifact` bib entry of the paper.
- [ ] At submission: tag `repro-kubesbs` **v1.0.0** and the paper repo **`sub1`**.
- [ ] Camera-ready: create the Zenodo community `gcd-udl` (does not exist yet), enable
      Zenodo for `repro-kubesbs`, publish the release, and add the concept DOI to the
      paper's `kubesbsartifact` entry and to the README badge.

## Done (for reference)

- [x] ~~Software DOI on Zenodo (concept `10.5281/zenodo.20694295`)~~ — **record
      DELETED 2026-06-29.** Renamed to **KubeSBS** in v0.3.0 (DOI item above).
