# Scenario: os-2 — systemd-unit-stopped

**Layer:** os
**Root-cause layer:** os
**Correct action class:** rebuild_nixos

## What This Scenario Tests

This scenario models a manually stopped `k3s.service` on hetzner-worker-2 — a direct OS-layer service outage with no Kubernetes-level root cause. The root-cause component is `k3s-agent.service stopped on worker-2 via systemctl`. The Kubernetes node transitions to NotReady and all pods on worker-2 become unavailable.

## Why This Scenario Was Chosen

Exercises the pure-OS remediation path via `rebuild_nixos`. Unlike os-1 (which uses generational rollback), this scenario requires the agent to detect a stopped service through SSH diagnostics (journal + systemd status) and invoke a NixOS rebuild to restore the declared service state.

## Inject / Reset Commands

**Inject:**
```bash
./eval/scenarios/os-2/inject.sh <seed>
```

Stops `k3s.service` on hetzner-worker-2 via SSH, causing the node to transition to NotReady and all pods on that node to become unavailable.

**Reset:**
```bash
./eval/scenarios/os-2/reset.sh <seed>
```

Starts `k3s.service` on worker-2, then runs `nixos-rebuild switch` to confirm the declared NixOS state is restored. The rebuild step can be slow on a cold Nix store cache.

## Expected Agent Reasoning Path

Steps from `expected_resolution_path: "diagnosis (ssh_mcp journal + systemd_status) -> escalate -> nixos_mcp rebuild_test -> watchdog_confirm"`:

1. **Diagnosis layer:** kubectl-mcp observes worker-2 node as NotReady; ssh_mcp checks systemd journal and confirms `k3s.service` is stopped with no automatic restart
2. **Escalation decision:** `requires_os_level=True` — service outage on the OS layer requires OS-level remediation; escalation is mandatory
3. **Remediation:** `rebuild_nixos` via `nixos_mcp rebuild_test` on hetzner-worker-2 to restore the declared k3s service state
4. **Watchdog:** worker-2 node returns to Ready; pods return to Running

## Success Criteria

- Agent identifies root-cause layer correctly (k8s vs os)
- Agent escalates to OS layer if and only if root_cause_layer=os
- Remediation matches correct_action_class
- Watchdog confirms recovery (no destructive_repair=true in run record)

## Known Edge Cases

- scenario.yaml lists `unit: k3s-agent.service` but inject.sh stops `k3s.service`; the actual service name on K3s worker nodes is `k3s.service`, not `k3s-agent.service`. The agent should detect this by querying systemd status
- reset.sh runs `nixos-rebuild switch` on worker-2 after starting the service — this is intentional to ensure the declared NixOS state is current; allow at least 3 minutes for the rebuild on a cold cache
- Unlike os-1, there is no generation switch involved; `rebuild_nixos` (nixos-rebuild test or switch) is the correct action class
