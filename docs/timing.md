# Cold-start timing

For tuning `OnActiveSec` on the rollback gate. Run `scripts/measure-cold-start.sh worker-1` (or `worker-2`) from somewhere that can SSH as root, then fix the numbers below from the script output. What's here now is just a stub.

## Local cluster

| Run | Host | s |
|-----|------|---|
| 1 | worker-1 | 60 |
| 2 | worker-1 | 60 |
| 3 | worker-1 | 60 |

Max: 60s  
OnActiveSec: 90s (`ceil(max * 1.5)`)

## Hetzner

Don't reuse the local times on cloud VMs; run the script again there when those nodes exist.
