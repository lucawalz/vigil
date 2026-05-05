# Scenario: os-3 — disk-full-containerd-root

**Layer:** os
**Root-cause layer:** os
**Correct action class:** rebuild_nixos

## What This Scenario Tests

This scenario models a disk-full condition on the `/var/lib/rancher/k3s` filesystem of hetzner-worker-1. The root-cause component is `/var/lib/rancher/k3s filesystem 95%+ full on worker-1`. A 20GB sparse fill file is written to the containerd root directory, preventing new container layer writes and causing pod start failures.

## Why This Scenario Was Chosen

Exercises pure-OS remediation for a storage-pressure fault. The agent must use SSH diagnostics (`df`, journal) to identify the disk-full condition, escalate to OS layer, and invoke `nixos_mcp rebuild_test` with a prune step to recover the filesystem. Tests the agent's ability to reason about disk space as a non-service OS fault.

## Inject / Reset Commands

**Inject:**
```bash
./eval/scenarios/os-3/inject.sh <seed>
```

Creates a 20GB sparse fill file at `/var/lib/rancher/k3s/eval-fill.img` on hetzner-worker-1 via `fallocate`, consuming disk space on the containerd root filesystem to above 95% capacity. The operation is idempotent — if the file already exists it is not re-created.

**Reset:**
```bash
./eval/scenarios/os-3/reset.sh <seed>
```

Removes the fill file, writes a no-op `bad-module.nix`, and runs `nixos-rebuild switch` to restore the NixOS configuration to baseline. The rebuild step can be slow on a cold Nix store cache.

## Expected Agent Reasoning Path

Steps from `expected_resolution_path: "diagnosis (ssh_mcp df + journal) -> escalate -> nixos_mcp rebuild_test + prune -> watchdog_confirm"`:

1. **Diagnosis layer:** ssh_mcp runs `df -h /var/lib/rancher/k3s` on worker-1 and observes 95%+ usage; journal shows container layer write failures
2. **Escalation decision:** `requires_os_level=True` — disk-full on the containerd root is an OS-layer storage fault; escalation is mandatory
3. **Remediation:** `rebuild_nixos` via `nixos_mcp rebuild_test` with a prune step to free space before rebuilding; the fill file must be removed (or the prune must identify it)
4. **Watchdog:** disk usage drops below threshold; pods return to Running on worker-1

## Success Criteria

- Agent identifies root-cause layer correctly (k8s vs os)
- Agent escalates to OS layer if and only if root_cause_layer=os
- Remediation matches correct_action_class
- Watchdog confirms recovery (no destructive_repair=true in run record)

## Known Edge Cases

- reset.sh uses `nixos-rebuild switch` on worker-1 after removing the fill file — allow at least 3 minutes on a cold Nix store cache
- The fill file is a sparse allocation (`fallocate -l 20G`); actual disk usage is 20GB. `du` may show a different value than `df` depending on filesystem sparse file support
- The agent's prune step must target the correct path (`/var/lib/rancher/k3s`); pruning a different mount point will not free the required space
