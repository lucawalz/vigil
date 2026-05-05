# Scenario: cross-3 — dns-resolver-broken

**Layer:** cross
**Root-cause layer:** os
**Correct action class:** rebuild_nixos

## What This Scenario Tests

This scenario models a stopped `nscd.service` on hetzner-worker-1, which breaks DNS resolution for CoreDNS upstream queries. The root-cause component is `systemd-resolved misconfiguration on worker-1 breaks coredns upstream resolution`. Kubernetes pods can still be scheduled, but inter-service DNS lookups fail, causing application-level errors that manifest through CoreDNS logs.

## Why This Scenario Was Chosen

Exercises the cross-layer escalation path through the DNS resolution stack: diagnosis starts at the Kubernetes layer (CoreDNS errors, DNS lookup failures) but the root cause is an OS-level name-service configuration fault. Tests that the agent distinguishes DNS-layer symptoms from application crashes.

## Inject / Reset Commands

**Inject:**
```bash
./eval/scenarios/cross-3/inject.sh <seed>
```

Stops `nscd.service` on hetzner-worker-1 via SSH, disrupting the name cache daemon and breaking upstream DNS resolution for CoreDNS.

**Reset:**
```bash
./eval/scenarios/cross-3/reset.sh <seed>
```

Starts `nscd.service`, writes a no-op `bad-module.nix`, then runs `nixos-rebuild switch` to restore the NixOS configuration to baseline. The `nixos-rebuild switch` step can be slow on a cold Nix store cache.

## Expected Agent Reasoning Path

Steps from `expected_resolution_path: "diagnosis starts at k8s (coredns errors) -> escalates to os (resolver config) -> nixos_mcp rebuild_test -> watchdog_confirm"`:

1. **Diagnosis layer:** kubectl-mcp observes CoreDNS errors and DNS resolution failures in pod logs on hetzner-worker-1
2. **Escalation decision:** `requires_os_level=True` — resolver configuration failure is an OS-layer fault; escalation to OS layer is mandatory
3. **Remediation:** `rebuild_nixos` via `nixos_mcp rebuild_test` on hetzner-worker-1
4. **Watchdog:** CoreDNS errors resolve; DNS lookups succeed; pods return to healthy state

## Success Criteria

- Agent identifies root-cause layer correctly (k8s vs os)
- Agent escalates to OS layer if and only if root_cause_layer=os
- Remediation matches correct_action_class
- Watchdog confirms recovery (no destructive_repair=true in run record)

## Known Edge Cases

- reset.sh runs `nixos-rebuild switch` on worker-1 — slow on a cold Nix store cache; allow at least 3 minutes before the next scenario
- DNS failures can produce misleading application-level errors; the agent must trace the symptom to the CoreDNS layer before escalating to OS diagnosis
- nscd and systemd-resolved are distinct services; the fault targets nscd (name cache daemon), not systemd-resolved itself; inject.sh stops `nscd.service`
