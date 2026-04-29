# Rollback gate timings

Cold-start times for `OnActiveSec` on the rollback gate. Measured with `scripts/measure-cold-start.sh <host> ~/nixos-homelab` (three `nixos-rebuild test` runs per node, Ready via local `kubectl`).

## Local cluster

| Run | Host | s |
|-----|------|---|
| 1 | worker-1 | 22 |
| 2 | worker-1 | 11 |
| 3 | worker-1 | 11 |
| 1 | worker-2 | 12 |
| 2 | worker-2 | 10 |
| 3 | worker-2 | 12 |
| 1 | master | 19 |
| 2 | master | 11 |
| 3 | master | 11 |

Max: 22s (worker-1 run 1) — `OnActiveSec: 33s` (`ceil(max * 1.5)`)

## Hetzner

Measured on CX33 (master) and CX23 (worker-1, worker-2). Run 1 on each node is inflated by a cold Nix store download on a fresh VM (~5 min to fetch packages never seen before). Runs 2–3 reflect steady-state activation time (warm store), which is the relevant scenario for the rollback gate.

| Run | Host | Type | s |
|-----|------|------|---|
| 1 | hetzner-master | CX33 | 297 |
| 2 | hetzner-master | CX33 | 14 |
| 3 | hetzner-master | CX33 | 14 |
| 1 | hetzner-worker-1 | CX23 | 258 |
| 2 | hetzner-worker-1 | CX23 | 15 |
| 3 | hetzner-worker-1 | CX23 | 14 |
| 1 | hetzner-worker-2 | CX23 | 312 |
| 2 | hetzner-worker-2 | CX23 | 16 |
| 3 | hetzner-worker-2 | CX23 | 14 |

Steady-state max (runs 2–3): 16s (hetzner-worker-2 run 2) — `OnActiveSec: 24s` (`ceil(16 * 1.5)`)
