# ADR-0004: NixOS generations as dead-man's switch for OS-level repairs

**Status**: Accepted

## Context

OS-level repairs carry a higher blast radius than Kubernetes operations. A bad systemd unit, a misconfigured kernel parameter, or a failed package installation can leave a node unbootable. In an autonomous system with no human in the loop, manual rollback is not viable.

Two properties of NixOS make safe OS mutation feasible:

1. `nixos-rebuild test` activates a new configuration without writing it to the boot loader — a reboot reverts to the previous generation automatically
2. Generations are atomic; every generation is a complete, bootable system state

## Decision

Implement a two-step dead-man's switch for OS-level repairs:

1. `nixos-rebuild test` applies the repair. The change is non-persistent.
2. A systemd timer (`nixos-rollback-gate.timer`) forces a reboot within a configurable window unless explicitly cancelled by the Watchdog agent after it confirms cluster health.
3. If health is confirmed, `nixos-rebuild switch` commits the generation. If the timer fires first, the node boots back to the previous generation automatically.

## Consequences

- Any OS repair attempt is inherently reversible; the worst case is an unplanned reboot, not a permanently broken node
- Boot safety is guaranteed by NixOS's atomic generation model, not by application-level error handling
- The rollback-gate window introduces mandatory latency before an OS repair can be committed (empirical timings in `docs/eval/rollback-gate-timings.md`)
- This mechanism is specific to NixOS; nodes running other distributions would require a different rollback strategy
- The Watchdog agent must complete its health assessment within the rollback-gate window
