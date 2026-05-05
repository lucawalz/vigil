# Scenario: cross-1 — kubelet-down-pods-notready

**Layer:** cross
**Root-cause layer:** os
**Correct action class:** rebuild_nixos

## What This Scenario Tests

This scenario models a stopped `k3s.service` on hetzner-worker-1, causing all pods scheduled on that node to transition to NotReady. The root-cause component is `k3s-agent on worker-1 stopped; all pods on node transition to NotReady`. The fault is invisible from the Kubernetes API surface alone — pods appear unhealthy, but the underlying cause is an OS-level service failure.

## Why This Scenario Was Chosen

Exercises the cross-layer escalation path: diagnosis begins at the Kubernetes layer (pod NotReady) but the agent must escalate to the OS layer (node NotReady, kubelet down) and invoke `rebuild_nixos` rather than attempting a K8s-only repair.

## Inject / Reset Commands

**Inject:**
```bash
./eval/scenarios/cross-1/inject.sh <seed>
```

Stops `k3s.service` on hetzner-worker-1 via SSH, causing all pods on that node to transition to NotReady.

**Reset:**
```bash
./eval/scenarios/cross-1/reset.sh <seed>
```

Starts `k3s.service`, writes a no-op `bad-module.nix`, then runs `nixos-rebuild switch` to restore the NixOS configuration to baseline. The `nixos-rebuild switch` step can be slow on a cold Nix store cache.

## Expected Agent Reasoning Path

Steps from `expected_resolution_path: "diagnosis starts at k8s layer (pod NotReady) -> escalates to os (node NotReady, kubelet down) -> nixos_mcp rebuild_test or ssh_mcp systemctl start -> watchdog_confirm"`:

1. **Diagnosis layer:** kubectl-mcp reports pods in NotReady on hetzner-worker-1; node status also shows NotReady
2. **Escalation decision:** `requires_os_level=True` — node NotReady with kubelet down indicates an OS-level service failure; escalation to OS layer is mandatory
3. **Remediation:** `rebuild_nixos` via `nixos_mcp rebuild_test` or `ssh_mcp systemctl start k3s.service`
4. **Watchdog:** pods return to Running; node returns to Ready

## Success Criteria

- Agent identifies root-cause layer correctly (k8s vs os)
- Agent escalates to OS layer if and only if root_cause_layer=os
- Remediation matches correct_action_class
- Watchdog confirms recovery (no destructive_repair=true in run record)

## Known Edge Cases

- reset.sh writes a no-op `bad-module.nix` and runs `nixos-rebuild switch` — this step is slow on a cold Nix store cache; allow at least 3 minutes for reset to complete before the next scenario
- The agent must not attempt a K8s-only repair (e.g., `rollout_undo`) — the pod NotReady symptom could resemble a K8s image fault; correct escalation requires checking node status
