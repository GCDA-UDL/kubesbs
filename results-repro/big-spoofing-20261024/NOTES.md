# Big-sweep re-run, part 2 (2026-10-24/25)

SimKube, Kubemark and kcs on `data/big`, 3 runs each, on the reference server
with `gc_thresh1/2/3 = 4096/8192/16384`, `MAX_TIME=7200` and DNS fallbacks
(`RUN_INFO`). No timeouts, no memory-threshold stops, no DNS errors and no
neighbour-table overflow. opensim, kwok and kube-sched come from part 1
(`../big-spoofing-20261022`).

`COMPARE-big.txt` compares the six simulators (216 runs) with `big-all`:

| Simulator | Run time | CPU time | Peak memory | Unscheduled pods, max diff / pods |
|---|---|---|---|---|
| kcs | +0 … +5 % | −1 … +7 % | −5 … +5 % | 0.0 % |
| kube-sched | +4 … +6 % | −5 … +8 % | −6 … +2 % | 0.1 % |
| kwok | −1 … +9 % | −1 … +10 % | −2 … +1 % | 0.1 % |
| opensim | −1 … +2 % | −2 … +2 % | −11 … +19 % | 0.1 % |
| Kubemark | −4 … +11 % | −3 … +6 % | −9 … +12 % | 6.9 % |
| SimKube | −43 … +25 % | −39 … +21 % | −9 … +3 % | 0.0 % |

Run time and CPU use only points ≥ 5 s, memory only points ≥ 0.1 GB.

- SimKube's run time also varies that much between the repetitions of one session
  (e.g. 200 nodes: 117–299 s in June, 120–371 s here).
- Kubemark's unscheduled pods vary between repetitions too (200 nodes: 32–683 in
  June, 213–707 here). With the larger ARP table Kubemark leaves the same share of
  pods unscheduled as in June, so that share is a Kubemark behaviour, not a limit
  of the host.
