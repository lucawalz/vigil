# Cold-start timing

For `OnActiveSec` on the rollback gate. Measured with `scripts/measure-cold-start.sh <host> ~/nixos-homelab` (three `nixos-rebuild test` runs per node, Ready via local `kubectl`).

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

Max: 22s (worker-1 run 1)
OnActiveSec: 33s (`ceil(max * 1.5)`)

## Hetzner

Don't reuse these on cloud VMs; run the script again there when those nodes exist.
