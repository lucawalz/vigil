# Scenario: cross-3 — dns-resolver-broken

**Layer:** cross
**Root-cause layer:** os
**Correct action class:** rebuild_nixos

## What This Scenario Tests

This scenario models a stopped `systemd-resolved.service` on hetzner-worker-1, which breaks DNS resolution for CoreDNS upstream queries. The root-cause component is `systemd-resolved misconfiguration on worker-1 breaks coredns upstream resolution`. Kubernetes pods can still be scheduled, but inter-service DNS lookups fail, causing application-level errors that manifest through CoreDNS logs.

## Why This Scenario Was Chosen

Exercises the cross-layer escalation path through the DNS resolution stack: diagnosis starts at the Kubernetes layer (CoreDNS errors, DNS lookup failures) but the root cause is an OS-level name-service configuration fault. Tests that the agent distinguishes DNS-layer symptoms from application crashes.

## Inject / Reset Commands

**Inject:**
```bash
./eval/scenarios/cross-3/inject.sh <seed>
```

Stops `systemd-resolved.service` on hetzner-worker-1 via SSH. Because `services.resolved` is declared in the NixOS configuration, resolved manages `/etc/resolv.conf` (pointing at the 127.0.0.53 stub). Stopping it makes the stub unreachable, breaking CoreDNS upstream resolution.

**Reset:**
```bash
./eval/scenarios/cross-3/reset.sh <seed>
```

Starts `systemd-resolved.service` on hetzner-worker-1, restoring the stub resolver and CoreDNS upstream connectivity.

## Expected Agent Reasoning Path

Steps from `expected_resolution_path: "diagnosis starts at k8s (coredns errors) -> escalates to os (resolver config) -> nixos_mcp nixos_rebuild -> watchdog_confirm"`:

1. **Diagnosis layer:** kubectl-mcp observes CoreDNS errors and DNS resolution failures in pod logs on hetzner-worker-1
2. **Escalation decision:** `requires_os_level=True` — resolver configuration failure is an OS-layer fault; escalation to OS layer is mandatory
3. **Remediation:** `rebuild_nixos` via `nixos_mcp rebuild_test` on hetzner-worker-1; `switch-to-configuration` restarts the stopped unit because it is enabled in the NixOS config
4. **Watchdog:** CoreDNS errors resolve; DNS lookups succeed; pods return to healthy state

## Success Criteria

- Agent identifies root-cause layer correctly (k8s vs os)
- Agent escalates to OS layer if and only if root_cause_layer=os
- Remediation matches correct_action_class
- Watchdog confirms recovery (no destructive_repair=true in run record)

## Known Edge Cases

- DNS failures can produce misleading application-level errors; the agent must trace the symptom to the CoreDNS layer before escalating to OS diagnosis
