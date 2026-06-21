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

The deadline must outlast the entire stage-confirm-commit time of a successful repair, not raw activation time alone. On the success path the Watchdog confirms as soon as it observes a healthy streak during the synchronous rebuild, so the dominant term is the rebuild-and-confirm time, not the `WATCHDOG_WINDOW_S` ceiling that bounds only failure detection.

## Decision Drivers

- The deadline must cover the full stage-confirm-commit budget, not activation time alone. An earlier `ceil(16 × 1.5) = 24 s` derivation counted only activation and would fire mid-confirmation.
- The success-path confirm completes when the Watchdog observes a healthy streak during the synchronous rebuild, well inside the `WATCHDOG_WINDOW_S` ceiling (300 s) that bounds only failure detection
- Stage activation (`switch-to-configuration test` on an already-built generation): ≤16 s steady-state, measured across three warm-store activation runs per node on the Hetzner cluster
- Commit (`switch-to-configuration boot`) plus Orchestrator dispatch overhead: ≤25 s
- A single value should serve all environments: the headroom absorbs the small Hetzner-vs-local activation variance (16 s vs 22 s) rather than requiring per-environment calibration
- Cold-start (first activation on a fresh VM) is excluded: warm-store runs 2-3 are the steady-state scenario the gate must handle; cold starts are an infra-provisioning concern, not a per-repair concern

## Considered Options

- Full-budget deadline (180 s, derived from the stage-confirm-commit budget)
- Activation-only deadline (24 s, derived from measured activation time with 50 % margin)
- Conservative placeholder deadline (120 s, no timing evidence)
- Dynamic deadline (agent computes/maintains the deadline; timer cancelled by agent signal)

## Decision Outcome

Chosen option: "Full-budget deadline (180 s)", because the gate must outlast the stage-confirm-commit time of a successful repair. That time is stage activation (≤16 s) plus the synchronous rebuild-and-confirm (the Watchdog returns as soon as it observes a healthy streak) plus commit and Orchestrator dispatch overhead (≤25 s); 180 s covers it with headroom against run-to-run variance. The `WATCHDOG_WINDOW_S` ceiling (300 s) bounds only how long the Watchdog waits before declaring failure, so the gate need not outlast it: on the failure path the 180 s gate fires first and reverts the bad configuration sooner. One value serves all environments because the headroom absorbs the small Hetzner-vs-local activation variance (16 s vs 22 s), collapsing the previous 24 s (Hetzner) / 33 s (local) split into a single calibrated value.

### Consequences

- Good: The 180 s deadline covers the full stage-confirm-commit budget; it cannot fire mid-confirmation the way the activation-only 24 s value could
- Good: One value applies to every environment; the headroom makes the per-environment activation variance negligible
- Good: The deadline moves only if the measured stage-confirm-commit time changes, so it is re-derived when the rebuild or hardware profile changes, not on every Watchdog-window tweak
- Bad: A node running a broken configuration remains active for up to 180 s before the dead-man's switch reverts it; this is the cost of letting a successful repair confirm and commit first
- Documented dependency: `OnActiveSec` must exceed the worst-case success-path stage-confirm-commit time (activation + rebuild-confirm + commit + dispatch); it is independent of `WATCHDOG_WINDOW_S`, which bounds only failure detection

**Validation Status:** Implemented. `OnActiveSec=180s` covers the measured success-path stage-confirm-commit time (≤16 s activation, the synchronous rebuild-confirm, and ≤25 s commit/dispatch) on the Hetzner cluster, with headroom below the 300 s failure-detection ceiling. A single value applies to both Hetzner and local environments. End-to-end revalidation of the full stage-confirm-commit timing is pending.

### Confirmation

The decision holds as long as:
- The success-path stage-confirm-commit time stays within `OnActiveSec`; a slower rebuild or commit profile requires recomputing `OnActiveSec`, independent of `WATCHDOG_WINDOW_S`
- The steady-state activation time stays within the ≤16 s activation component the budget assumes
- `rollback-gate.timer` has `OnActiveSec=180s` in the NixOS module on all cluster nodes

### Pros and Cons of the Options

#### Full-budget deadline (180 s)

- Good: Covers the entire success-path stage-confirm-commit sequence; the deadline cannot expire before a valid repair has confirmed and committed
- Good: A single value serves all environments because the headroom absorbs the per-environment activation variance
- Good: The deadline is a static value baked into the NixOS module; it is armed once at staging by a deterministic `systemctl start` and fires by default regardless of agent liveness
- Bad: A node running a broken configuration stays active for up to 180 s; this latency is the cost of guaranteeing the confirm window can finish before the gate fires

#### Activation-only deadline (24 s)

- Good: Derived from three activation runs per node across all Hetzner cluster members; worst-case steady-state value is the baseline, not the average
- Bad: Counts only `switch-to-configuration test` activation, ignoring the rebuild-confirm and commit steps; the timer would fire mid-confirmation and revert every valid repair before it could be committed

#### Conservative placeholder deadline (120 s)

- Good: Guaranteed to outlast any realistic activation time; no risk of premature rollback due to an underestimated activation time
- Bad: 120 s is a placeholder with no timing evidence; it leaves little margin for a slow rebuild-confirm plus the activation and commit steps that bracket it, so a repair that confirms late would race the gate. The full-budget 180 s value adds the activation and commit components plus headroom so the gate reliably outlasts a successful confirm-then-commit.

#### Dynamic deadline (agent-computed timer)

- Good: The rollback window would be exactly as long as the repair takes; no fixed margin required
- Bad: A dynamic deadline requires the agent to compute and maintain the timer at runtime through a control file or socket. If the agent crashes after activating but before maintaining the timer, the node runs an unconfirmed configuration indefinitely. The chosen design avoids this: the timer has a static deadline baked into the NixOS module and is armed once at staging by a deterministic `systemctl start`, so it fires by default. Only the success-path disarm (`systemctl stop` at commit) is an agent action, and a missed disarm still fires and reverts. A deadline the agent computes or maintains stays rejected because it makes the firing path depend on agent liveness.

## More Information

- NixOS dead-man's switch mechanism: `docs/adr/0004-nixos-dead-mans-switch.md`
- Watchdog health assessment: `docs/adr/0011-deterministic-watchdog.md`
