---
status: Accepted
date: 2026-05-08
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0012: Empirically-calibrated dead-man's switch deadline

## Context and Problem Statement

The NixOS rollback gate (`nixos-rollback-gate.timer`) fires `OnActiveSec` after `nixos-rebuild test` activates a new configuration. If the Watchdog has not confirmed cluster health by that time, the timer triggers a forced reboot, reverting to the previous NixOS generation.

The timer deadline must satisfy two competing constraints:

1. **Too short**: the Watchdog has not yet completed its health assessment when the timer fires; a valid repair triggers an unnecessary rollback every time.
2. **Too long**: a broken configuration remains active longer than necessary before the dead-man's switch engages; MTTR for OS-layer failures is extended.

The initial placeholder value of 120 s was chosen conservatively before timing data was available. Measured activation times now provide an empirical basis for a tighter deadline.

## Decision Drivers

- Measured 16 s steady-state warm-store rebuild time (Hetzner CX23 worker-2, run 2; the highest steady-state value across all nodes and runs in `docs/eval/rollback-gate-timings.md`)
- 50 % engineering margin applied to the measured max: `ceil(16 × 1.5) = 24 s`
- Faster MTTR than the 120 s placeholder: a node running a bad configuration is reverted 5× sooner
- Cold-start (first `nixos-rebuild test` on a fresh VM) is excluded: warm-store runs 2–3 are the steady-state scenario the gate must handle; cold starts are an infra-provisioning concern, not a per-repair concern

## Considered Options

- Empirically-calibrated deadline (24 s, derived from measured timing data with 50 % margin)
- Conservative placeholder deadline (120 s, no timing evidence)
- Dynamic deadline (Watchdog reports completion time; timer cancelled by agent signal)

## Decision Outcome

Chosen option: "Empirically-calibrated deadline (24 s)", because it is derived from measured activation times on the actual hardware profile (Hetzner CX23 and CX33), applies a 50 % safety margin over the worst observed steady-state run, and reduces the OS-failure window by 5× compared to the placeholder.

### Consequences

- Good: The 24 s deadline is derived from measured hardware timing; the 50 % margin accounts for run-to-run variance
- Good: MTTR for OS-layer faults is reduced: a node running a bad configuration reboots within 24 s rather than 120 s
- Good: The derivation is documented in `docs/eval/rollback-gate-timings.md`; re-calibration requires new timing data when the hardware profile changes
- Bad: The 50 % margin does not cover degraded-network scenarios where the Watchdog's `get_pods` call experiences unusual API server latency; such scenarios require a separate latency budget analysis
- Bad: The deadline is hardware-specific: a different instance type (e.g., CX11) would require re-measurement and a new calibration

**Validation Status:** Verified — `docs/eval/rollback-gate-timings.md` records steady-state max of 16 s on Hetzner CX23; `ceil(16 × 1.5) = 24 s` is the current `OnActiveSec` value. Local cluster timing max is 22 s (`OnActiveSec: 33 s`), calibrated separately.

### Confirmation

The decision holds as long as:
- Hetzner node instance types remain CX33 (master) and CX23 (workers)
- The steady-state activation time measured in `docs/eval/rollback-gate-timings.md` does not exceed 16 s on warm-store runs
- `nixos-rollback-gate.timer` has `OnActiveSec=24s` in the NixOS module for Hetzner nodes

### Pros and Cons of the Options

#### Empirically-calibrated deadline (24 s)

- Good: Derived from three `nixos-rebuild test` runs per node across all Hetzner cluster members; worst-case steady-state value is the baseline, not the average
- Good: 50 % margin (`ceil(max × 1.5)`) is the same formula applied to local cluster timing (22 s → 33 s), making the calibration methodology consistent across environments
- Bad: Requires re-measurement when hardware profile changes; the 24 s value is not portable to a different instance class without new timing data

#### Conservative placeholder deadline (120 s)

- Good: Guaranteed to outlast any realistic activation time; no risk of premature rollback due to an underestimated deadline
- Bad: A node running a misconfigured NixOS generation remains active for up to 120 s before the dead-man's switch reverts it. Measured activation times show steady-state completion at 14–16 s; padding to 120 s extends the OS-failure window by more than 7× beyond what the hardware requires, directly increasing MTTR for every OS-layer fault in the eval and in production.

#### Dynamic deadline (agent-cancelled timer)

- Good: The rollback window would be exactly as long as the repair takes; no fixed margin required
- Bad: A dynamic deadline requires the Watchdog or Orchestrator to cancel the systemd timer by writing to a control file or calling a socket. If the agent crashes after activating the configuration but before cancelling the timer, the timer would never fire: the node would be left running an unconfirmed configuration indefinitely. The static timer is the safety guarantee precisely because it does not depend on the agent's continued liveness.

## More Information

- Timing measurements and derivation: `docs/eval/rollback-gate-timings.md`
- NixOS dead-man's switch mechanism: `docs/adr/0004-nixos-dead-mans-switch.md`
- Watchdog health assessment: `docs/adr/0011-deterministic-watchdog.md`
