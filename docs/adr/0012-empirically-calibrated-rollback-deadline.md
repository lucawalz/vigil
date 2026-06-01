---
status: Accepted
date: 2026-05-08
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0012: Empirically-calibrated dead-man's switch deadline

## Context and Problem Statement

The NixOS rollback gate (`rollback-gate.timer`) is armed at staging and fires `OnActiveSec` after `stage_generation` activates a new configuration non-durably (`switch-to-configuration test`). If the Watchdog has not confirmed cluster health and the Orchestrator has not committed (disarming the timer) by that time, the timer triggers a forced reboot, reverting to the previous NixOS generation.

The timer deadline must satisfy two competing constraints:

1. **Too short**: the full stage-confirm-commit budget has not elapsed when the timer fires; a valid repair triggers an unnecessary rollback every time.
2. **Too long**: a broken configuration remains active longer than necessary before the dead-man's switch engages; MTTR for OS-layer failures is extended.

The deadline must outlast the entire stage-confirm-commit budget, not raw activation time alone. The dominant term is the Watchdog confirm window, which is environment-independent.

## Decision Drivers

- The deadline must cover the full stage-confirm-commit budget, not activation time alone. An earlier `ceil(16 × 1.5) = 24 s` derivation counted only activation and would fire mid-confirmation.
- The Watchdog confirm window (`WATCHDOG_WINDOW_S=120 s`) is the dominant, environment-independent term in the budget
- Stage activation (`switch-to-configuration test` on an already-built generation): ≤16 s steady-state (`docs/eval/rollback-gate-timings.md`)
- Commit (`switch-to-configuration boot`) plus Orchestrator dispatch overhead: ≤25 s
- A single value should serve all environments: the 120 s window dominates, so the small Hetzner-vs-local activation variance (16 s vs 22 s) is absorbed by the headroom rather than requiring per-environment calibration
- Cold-start (first activation on a fresh VM) is excluded: warm-store runs 2–3 are the steady-state scenario the gate must handle; cold starts are an infra-provisioning concern, not a per-repair concern

## Considered Options

- Full-budget deadline (180 s, derived from the stage-confirm-commit budget)
- Activation-only deadline (24 s, derived from measured activation time with 50 % margin)
- Conservative placeholder deadline (120 s, no timing evidence)
- Dynamic deadline (agent computes/maintains the deadline; timer cancelled by agent signal)

## Decision Outcome

Chosen option: "Full-budget deadline (180 s)", because the gate must outlast the entire stage-confirm-commit sequence. The budget is the Watchdog confirm window (120 s, the dominant term) plus stage activation (≤16 s) plus commit and Orchestrator dispatch overhead (≤25 s), giving a subtotal of ≈161 s rounded up to 180 s for ~12 % headroom against run-to-run variance. One value serves all environments: because the 120 s window dominates, the small Hetzner-vs-local activation variance (16 s vs 22 s) is absorbed by the headroom, collapsing the previous 24 s (Hetzner) / 33 s (local) split into a single calibrated value.

### Consequences

- Good: The 180 s deadline covers the full stage-confirm-commit budget; it cannot fire mid-confirmation the way the activation-only 24 s value could
- Good: One value applies to every environment; the dominant 120 s Watchdog window makes the per-environment activation variance negligible within the headroom
- Good: The derivation is documented in `docs/eval/rollback-gate-timings.md`; the activation-time component is re-measured when the hardware profile changes, but the deadline only moves if the Watchdog window changes
- Bad: A node running a broken configuration remains active for up to 180 s before the dead-man's switch reverts it; this is the cost of guaranteeing the confirm window can complete
- Documented dependency: if `WATCHDOG_WINDOW_S` changes, `OnActiveSec` must be recomputed as ≥ window + ~60 s (activation + commit + dispatch headroom)

**Validation Status:** Implemented. `OnActiveSec=180s` is derived from the 120 s Watchdog window plus the ≤16 s activation and ≤25 s commit/dispatch components documented in `docs/eval/rollback-gate-timings.md`. A single value applies to both Hetzner and local environments. End-to-end revalidation of the full stage-confirm-commit timing is pending.

### Confirmation

The decision holds as long as:
- The Watchdog confirm window remains `WATCHDOG_WINDOW_S=120 s`; a change requires recomputing `OnActiveSec` as ≥ window + ~60 s
- The steady-state activation time measured in `docs/eval/rollback-gate-timings.md` stays within the ≤16 s activation component the budget assumes
- `rollback-gate.timer` has `OnActiveSec=180s` in the NixOS module on all cluster nodes

### Pros and Cons of the Options

#### Full-budget deadline (180 s)

- Good: Covers the entire stage-confirm-commit sequence; the deadline cannot expire while the Watchdog is still inside its confirm window
- Good: A single value serves all environments because the 120 s Watchdog window dominates and absorbs the per-environment activation variance
- Good: The deadline is a static value baked into the NixOS module; it is armed once at staging by a deterministic `systemctl start` and fires by default regardless of agent liveness
- Bad: A node running a broken configuration stays active for up to 180 s; this latency is the cost of guaranteeing the confirm window can finish before the gate fires

#### Activation-only deadline (24 s)

- Good: Derived from three activation runs per node across all Hetzner cluster members; worst-case steady-state value is the baseline, not the average
- Bad: Counts only `switch-to-configuration test` activation, ignoring the 120 s Watchdog confirm window and the commit step; the timer would fire mid-confirmation and revert every valid repair before it could be committed

#### Conservative placeholder deadline (120 s)

- Good: Guaranteed to outlast any realistic activation time; no risk of premature rollback due to an underestimated activation time
- Bad: 120 s equals the Watchdog confirm window exactly, leaving no margin for the activation and commit steps that bracket it; a confirm that completes near the end of its window would race the gate. The full-budget 180 s value adds the activation and commit components plus headroom so the gate reliably outlasts a successful confirm-then-commit.

#### Dynamic deadline (agent-computed timer)

- Good: The rollback window would be exactly as long as the repair takes; no fixed margin required
- Bad: A dynamic deadline requires the agent to compute and maintain the timer at runtime through a control file or socket. If the agent crashes after activating but before maintaining the timer, the node runs an unconfirmed configuration indefinitely. The chosen design avoids this: the timer has a static deadline baked into the NixOS module and is armed once at staging by a deterministic `systemctl start`, so it fires by default. Only the success-path disarm (`systemctl stop` at commit) is an agent action, and a missed disarm still fires and reverts. A deadline the agent computes or maintains stays rejected because it makes the firing path depend on agent liveness.

## More Information

- Timing measurements and derivation: `docs/eval/rollback-gate-timings.md`
- NixOS dead-man's switch mechanism: `docs/adr/0004-nixos-dead-mans-switch.md`
- Watchdog health assessment: `docs/adr/0011-deterministic-watchdog.md`
