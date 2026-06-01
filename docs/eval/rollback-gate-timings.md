# Rollback gate timings

Activation times for the rollback gate. Measured with `scripts/measure-cold-start.sh <host> ~/nixos-homelab` (three `nixos-rebuild test` runs per node, Ready via local `kubectl`).

These measurements cover only the **activation** component of the gate deadline (`switch-to-configuration test` on an already-built generation). The `OnActiveSec` deadline is dominated by the Watchdog confirm window, not by activation time: the calibrated value is **180 s**, covering the full stage-confirm-commit budget (120 s Watchdog window + ≤16 s activation + ≤25 s commit and dispatch overhead, rounded up for headroom). The per-environment `ceil(max × 1.5)` figures below (24 s Hetzner, 33 s local) were the earlier activation-only derivation; they are superseded by the single 180 s value because the dominant 120 s window absorbs the activation variance across environments. See `docs/adr/0012-empirically-calibrated-rollback-deadline.md` for the derivation.

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

Activation max: 22s (worker-1 run 1). The earlier activation-only derivation gave `ceil(max * 1.5) = 33s`; the gate now uses the single 180 s full-budget value.

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

Steady-state activation max (runs 2–3): 16s (hetzner-worker-2 run 2). The earlier activation-only derivation gave `ceil(16 * 1.5) = 24s`; the gate now uses the single 180 s full-budget value, which subsumes this activation component.
