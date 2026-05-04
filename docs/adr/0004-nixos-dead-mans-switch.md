---
status: Accepted
date: 2026-04-19
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0004: NixOS generations as dead-man's switch for OS-level repairs

## Context and Problem Statement

OS-level repairs carry a higher blast radius than Kubernetes operations. A bad systemd unit, a misconfigured kernel parameter, or a failed package installation can leave a node unbootable. In an autonomous system with no human in the loop, manual rollback is not viable.

Two properties of NixOS make safe OS mutation feasible:

1. `nixos-rebuild test` activates a new configuration without writing it to the boot loader; a reboot reverts to the previous generation automatically
2. Generations are atomic; every generation is a complete, bootable system state

The system requires a mechanism that converts every OS repair attempt into a reversible operation: if the repair succeeds and the cluster remains healthy, the new generation is committed; if anything goes wrong (the health check fails, the timer fires, or the agent crashes), the node reboots back to the last known-good generation without operator intervention.

## Decision Drivers

- Autonomous operation means no human operator can intervene at 03:00 to type `nixos-rebuild --rollback`
- NixOS atomic generations make every OS state transition inherently reversible
- `nixos-rebuild test` activates without committing to the boot loader; a reboot is always a safe escape hatch
- The systemd timer provides a hard deadline: the repair either completes and is confirmed, or the node reboots
- OS-layer failures must not permanently brick a node; worst-case outcome must be an unplanned reboot

## Considered Options

- NixOS dead-man's switch
- Manual rollback
- etcd-snapshot rollback only

## Decision Outcome

Chosen option: "NixOS dead-man's switch", because it makes OS repair attempts inherently reversible without operator intervention, using NixOS's atomic generation model as the safety guarantee rather than application-level error handling.

### Consequences

- Good: Any OS repair attempt is inherently reversible; the worst case is an unplanned reboot, not a permanently broken node
- Good: Boot safety is guaranteed by NixOS's atomic generation model, not by application-level error handling
- Bad: The rollback-gate window introduces mandatory latency before an OS repair can be committed (empirical timings in `docs/eval/rollback-gate-timings.md`)
- Bad: This mechanism is specific to NixOS; nodes running other distributions would require a different rollback strategy
- Bad: The Watchdog agent must complete its health assessment within the rollback-gate window

`switch_generation` is the primary OS remediation verb validated in the v1.0 eval campaign; `rebuild_test` is the trial activation step; the systemd timer + health-gate is the safety net that triggers a forced reboot when health checks fail. The agent converges on `switch_generation` reliably across all OS-layer eval scenarios.

**Validation Status:** Verified — v1.0 initial deployment (timer + health gate deployed and calibrated); v1.0 eval campaign (all 7 OS/cross scenarios pass via `switch_generation`).

### Confirmation

The decision holds as long as:
- `nixos-rebuild test` activates a new configuration without committing it to the boot loader on all cluster nodes
- The systemd timer (`nixos-rollback-gate.timer`) forces a reboot within the configured window when health confirmation is not received
- `switch_generation` is the agent-facing verb for committing a validated OS repair in the nixos-mcp tool
- All 7 OS-layer and cross-layer eval scenarios continue to pass end-to-end via the dead-man's switch flow

### Pros and Cons of the Options

#### NixOS dead-man's switch

- Good: Atomic generation model makes every OS state transition reversible; no application-level error handling required for the rollback path
- Good: `nixos-rebuild test` is a NixOS primitive: the revert-on-reboot guarantee is built into the bootloader, not into Vigil's code
- Good: The systemd timer provides a hard deadline independent of the agent's health: even if the agent crashes, the node reverts
- Bad: Health-gate window introduces latency; empirical tuning of the timer is required per hardware profile

#### Manual rollback

- Good: Simple conceptual model; no additional NixOS module required
- Bad: Manual rollback presupposes a human operator. Vigil is autonomous; there is no operator at 03:00 to type `nixos-rebuild --rollback`. A bad systemd unit applied via the agent could leave a node unbootable with no path back to a working state.

#### etcd-snapshot rollback only

- Good: Restores full Kubernetes state from a known-good snapshot; well-understood recovery path for K8s failures
- Bad: etcd snapshots roll back Kubernetes state but not OS state. A NixOS misconfiguration at the kernel parameter level (an OS-layer boundary scenario) would not appear in etcd at all; the K8s API would never see the failure cause. The dead-man's switch operates one layer below.

## More Information

- NixOS GitOps depth and dead-man's switch design philosophy: `docs/architecture/gitops-nixos.md` (forthcoming)
- A forthcoming architecture document will provide the full deep-dive treatment of the NixOS generation model and Flux reconciliation interaction with the dead-man's switch
