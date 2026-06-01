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

OS-layer repairs follow a stage-confirm-commit flow:

1. `stage_generation(host, generation)` arms the per-node `rollback-gate.timer` via `systemctl start`, then activates the target generation with `switch-to-configuration test`. The running system uses the new configuration; the bootloader default still points at the prior committed generation.
2. The deterministic Watchdog confirms cluster health within its window.
3. Only after confirmation, the Orchestrator (not the remediation LLM) calls `commit_generation(host)`, which runs `switch-to-configuration boot` to set the bootloader default to the staged generation and disarms the timer via `systemctl stop`.

If health is not confirmed by the deadline, whether from degradation, timeout, or an agent crash, the armed timer fires `rollback-gate.service`, which exits non-zero and triggers `FailureAction=reboot-force`. Because nothing was committed to the bootloader, the reboot restores the prior generation. The timer fires independently of the agent process, so the guarantee holds even on agent crash.

**Validation Status:** Implemented. `stage_generation` activates non-durably and arms `rollback-gate.timer`; the Watchdog confirms; `commit_generation` makes the change durable and disarms the timer; non-confirmation or agent crash reverts on reboot. End-to-end OS-layer eval revalidation is pending.

### Scope: `git_commit_nix`

The dead-man's switch covers OS repairs applied directly to a node via `stage_generation`. It does **not** cover `git_commit_nix`, which commits a NixOS change to the Git repository for `vigil-auto-reconcile` to apply. The reversal path for `git_commit_nix` is GIT-REVERT: `revert_commit` followed by `trigger_reconcile` re-converges the cluster to a corrected Git state. `git_commit_nix` is therefore out of scope for the dead-man's switch.

Residual risk: a merged configuration that bricks a node below k3s defeats the auto-reconciler's self-heal, because the node can no longer pull and apply the corrected commit. This risk is mitigated by the CI/PR gate and the human-review path, not by staging. Adding staging discipline to `vigil-auto-reconcile` is a deliberate non-goal: the GitOps path's safety property is Git revertibility plus pre-merge review, not in-place activation gating.

### Confirmation

The decision holds as long as:
- `switch-to-configuration test` activates a new configuration without changing the bootloader default on all cluster nodes
- `stage_generation` arms `rollback-gate.timer` (via `systemctl start`) when it activates the staged configuration non-durably
- The systemd timer (`rollback-gate.timer`) forces a reboot within the configured window when health confirmation is not received, regardless of agent liveness
- `commit_generation` is the deterministic Orchestrator-invoked verb that makes a confirmed repair durable (`switch-to-configuration boot`) and disarms the timer
- OS-layer and cross-layer eval scenarios pass end-to-end via the stage-confirm-commit flow

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

- NixOS generation model, dead-man's switch timer, and OS remediation sequence: [docs/architecture/gitops-nixos.md](../architecture/gitops-nixos.md)
