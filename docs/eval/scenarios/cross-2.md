# Scenario: cross-2 — node-oom-kills-critical-pod

**Layer:** cross
**Root-cause layer:** os
**Correct action class:** rebuild_nixos

## What This Scenario Tests

This scenario models a stopped `k3s.service` on hetzner-worker-2, causing all pods scheduled on that node to transition to NotReady. The root-cause component is `k3s-agent stopped on worker-2; all pods on node transition to NotReady`. The Kubernetes-visible symptom (pods NotReady) is identical to a scheduling failure, but the actual cause is an OS-level service outage.

## Why This Scenario Was Chosen

Exercises the cross-layer escalation path on worker-2, verifying that the agent generalises its OS-layer detection logic across nodes. Complements cross-1 (worker-1) by targeting the second worker, ensuring the reasoning path is not node-specific.

## Inject / Reset Commands

**Inject:**
```bash
./eval/scenarios/cross-2/inject.sh <seed>
```

Stops `k3s.service` on hetzner-worker-2 via SSH, causing all pods on that node to transition to NotReady.

**Reset:**
```bash
./eval/scenarios/cross-2/reset.sh <seed>
```

Starts `k3s.service`, writes a no-op `bad-module.nix`, runs `nixos-rebuild switch` to restore the NixOS configuration, then re-applies the `vigil-app` deployment manifest and waits for rollout. The `nixos-rebuild switch` step can be slow on a cold Nix store cache.

## Expected Agent Reasoning Path

Steps from `expected_resolution_path: "diagnosis starts at k8s (pod NotReady) -> escalates to os (node NotReady, k3s stopped) -> nixos_mcp rebuild_test -> watchdog_confirm"`:

1. **Diagnosis layer:** kubectl-mcp reports pods in NotReady on hetzner-worker-2; node shows NotReady
2. **Escalation decision:** `requires_os_level=True` — node NotReady with k3s stopped confirms an OS-level service failure; escalation is mandatory
3. **Remediation:** `rebuild_nixos` via `nixos_mcp rebuild_test` on hetzner-worker-2
4. **Watchdog:** pods return to Running; node returns to Ready

## Success Criteria

- Agent identifies root-cause layer correctly (k8s vs os)
- Agent escalates to OS layer if and only if root_cause_layer=os
- Remediation matches correct_action_class
- Watchdog confirms recovery (no destructive_repair=true in run record)

## Known Edge Cases

- reset.sh runs `nixos-rebuild switch` on worker-2 — slow on a cold Nix store cache; allow at least 3 minutes before the next scenario
- reset.sh also re-creates the `vigil-app` deployment; the combined reset time is longer than for cross-1
- The agent must target worker-2 specifically; a node-unaware remediation that issues `rebuild_nixos` on the wrong host leaves the fault in place
