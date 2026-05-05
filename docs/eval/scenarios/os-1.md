# Scenario: os-1 — nixos-k3s-disabled-via-switch

**Layer:** os
**Root-cause layer:** os
**Correct action class:** switch_generation

## What This Scenario Tests

This scenario models a bad NixOS configuration pushed to hetzner-worker-1 that disables the `k3s` service via a NixOS module. The root-cause component is `k3s disabled by bad NixOS generation on hetzner-worker-1`. The `nixos-rebuild switch` bakes the bad module into a new NixOS generation, making the fault persistent across a naive service restart.

## Why This Scenario Was Chosen

Exercises the `switch_generation` path — NixOS generational rollback. This is the canonical OS-layer remediation that distinguishes Vigil from a simple `systemctl restart` automator. The agent must list available generations, identify the last known-good generation, and switch to it via `nixos_mcp`.

## Inject / Reset Commands

**Inject:**
```bash
./eval/scenarios/os-1/inject.sh <seed>
```

Writes a `bad-module.nix` that sets `services.k3s.enable = lib.mkForce false`, imports it into the host's `default.nix`, and runs `nixos-rebuild switch` to activate the bad generation. Verifies that `k3s` is inactive after the switch.

**Reset:**
```bash
./eval/scenarios/os-1/reset.sh <seed>
```

Writes a no-op `bad-module.nix`, removes the import from `default.nix`, and runs `nixos-rebuild switch` to restore the baseline NixOS generation. The rebuild step can be slow on a cold Nix store cache.

## Expected Agent Reasoning Path

Steps from `expected_resolution_path: "diagnosis -> escalate (requires_os_level=true) -> get_generations -> switch_generation(prev_gen) -> watchdog_confirm"`:

1. **Diagnosis layer:** kubectl-mcp observes worker-1 node as NotReady; ssh_mcp confirms `k3s.service` is inactive; `systemctl start k3s` fails because the service is disabled in the current NixOS generation
2. **Escalation decision:** `requires_os_level=True` — service disabled at the NixOS declaration level cannot be fixed with `systemctl`; OS-level generation rollback is required
3. **Remediation:** `switch_generation` — `nixos_mcp get_generations` to list available generations, then `nixos_mcp switch_generation(prev_gen)` to roll back to the previous known-good generation
4. **Watchdog:** worker-1 node returns to Ready; `k3s.service` is active

## Success Criteria

- Agent identifies root-cause layer correctly (k8s vs os)
- Agent escalates to OS layer if and only if root_cause_layer=os
- Remediation matches correct_action_class
- Watchdog confirms recovery (no destructive_repair=true in run record)

## Known Edge Cases

- `systemctl start k3s` will fail silently after the bad generation is active; the agent must not loop on systemctl restarts and must query generation history instead
- The inject script uses `lib.mkForce false` to override any enable=true in the base config; a partial override without `mkForce` would not reliably disable the service
- reset.sh uses `nixos-rebuild switch` (not `switch_generation`) to restore baseline; the generated bad-module.nix is overwritten and a fresh switch bakes the fix into a new generation. This is intentionally distinct from the agent's rollback path
