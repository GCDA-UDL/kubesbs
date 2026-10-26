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
- [x] **Kubemark run time** included the harness's per-pod event scan of the pending
      pods (52 % of the run time at 400 nodes, 80–82 % from 800 nodes). Fixed on
      2026-10-26: one `FailedScheduling` query per pass. Re-run all simulators with
      the fixed harness (session 3) and use it as the paper's primary data.
- [ ] **vanilla pre-check:** every vanilla run first tries `data/test/vanilla/cluster-1.yaml`,
      which does not exist, and logs "Cluster setup failed" (results go to `/tmp`, the
      benchmark rows are unaffected). Add the file or skip the pre-check.
- [ ] **Zenodo DOI for KubeSBS v0.3.0:** enable the repository in Zenodo's GitHub
      integration, publish the v0.3.0 GitHub release, then add the concept DOI to
      `CITATION.cff`, `README.md` and the survey's `k8s-sims` bib entry.
- [ ] **Philly converter — real-trace + GPU run:** `philly2base.py` is validated on
      the synthetic sample only (5 jobs → 2 GPU nodes, 16 GPUs). Download the real
      `cluster_job_log` (`msr-fiddle/philly-traces`, via `download_traces.sh --philly`)
      and run it through a **GPU-aware scheduler** to actually exercise
      `nvidia.com/gpu`; current sims schedule by cpu/memory, so GPU placement is
      untested. Feeds the GPU-scheduling-fidelity sub-study of paper #3 (C1).

## Done (for reference)

- [x] ~~Software DOI on Zenodo (concept `10.5281/zenodo.20694295`)~~ — **record
      DELETED 2026-06-29.** Renamed to **KubeSBS** in v0.3.0 (DOI item above).
