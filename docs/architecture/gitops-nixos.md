# Vigil — NixOS GitOps and the Dead-Man's Switch

Vigil performs OS-level repairs through a stage-confirm-commit flow on cluster nodes over SSH.
Every such repair is reversible by construction, not by convention: a generation is staged
non-durably, the cluster's health is confirmed, and only a confirmed repair is committed to the
bootloader. This document covers the NixOS generation model as the rollback substrate, the
dead-man's switch timer that enforces a hard revert deadline, the Flux GitOps layer that manages the
desired NixOS state, and the `nixos-mcp` tool sequence that agents follow for OS-layer fault
remediation.

## NixOS Generation Model

NixOS stores every system configuration as an immutable, bootloader-registered generation. A
generation is a complete, independently bootable system closure in `/nix/var/nix/profiles/system`.
Switching generations is atomic: the bootloader entry changes, the active configuration changes, and
the previous generation remains intact until explicitly garbage-collected.

`switch-to-configuration test` activates a new configuration in the running system without changing
the bootloader default. The committed-generation pointer does not move. If the node reboots before a
subsequent `switch-to-configuration boot`, it boots back to the generation that was the bootloader
default before activation. This is the standard NixOS behaviour for the `test` activation mode.

Vigil exploits this property as a safety primitive. An OS repair is staged with
`switch-to-configuration test` and is durable only after `switch-to-configuration boot` writes the
new bootloader default. Between staging and commit, if the health check fails, the agent crashes, or
the node reboots for any reason, the node returns to its prior committed generation without agent
intervention.

`stage_generation` and `commit_generation` in `nixos-mcp` implement the two halves of this flow.
`stage_generation` activates the target generation non-durably and arms the dead-man's switch timer:

```go
// mcp-servers/nixos-mcp/internal/nixos/client.go
func (c *realNixOSClient) StageGeneration(ctx context.Context, host string, generation int) (string, error) {
    cmd := fmt.Sprintf(
        "sudo systemctl start rollback-gate.timer && sudo nix-env --switch-generation %d -p /nix/var/nix/profiles/system && sudo /nix/var/nix/profiles/system/bin/switch-to-configuration test",
        generation,
    )
    return c.runSSH(ctx, host, cmd)
}
```

The timer is armed first, so a failure during activation is still covered by the deadline.

`switch-to-configuration test` activates the staged generation in the running system without touching
the bootloader default, so an uncommitted stage is reverted by any reboot. `commit_generation` makes
a confirmed repair durable with `switch-to-configuration boot` and disarms the timer with
`systemctl stop rollback-gate.timer`. The commit step is invoked deterministically by the
Orchestrator, not by the remediation LLM; the remediation agent can only stage.

## Dead-Man's Switch Timer

The dead-man's switch is a systemd timer and service pair deployed on every cluster node via the
`rollback-gate.nix` NixOS module. It provides a hard revert deadline that operates independently of
the agent: the timer is not started at boot. `stage_generation` arms it at staging time and
`commit_generation` disarms it on a confirmed repair. Health assessment belongs to the Watchdog;
the timer is a pure deadline. If the staged repair is not committed before the deadline, the timer
fires the service, which forces a reboot to the prior committed generation.

```nix
# infra/nixos/modules/services/rollback-gate.nix
systemd.services.rollback-gate = {
  serviceConfig = {
    Type = "oneshot";
    ExecStart = pkgs.writeShellScript "rollback-gate-expire" ''
      echo "rollback-gate: confirmation deadline expired without commit; reverting to boot default" >&2
      exit 1
    '';
    FailureAction = "reboot-force";
  };
};

systemd.timers.rollback-gate = {
  timerConfig = {
    OnActiveSec = "180s";
    Unit = "rollback-gate.service";
  };
};
```

The timer is not bound to `multi-user.target`, so it does not start at boot; `stage_generation` arms
it with `systemctl start rollback-gate.timer`. Once armed, it fires once, 180 seconds later. Firing
is itself the revert signal: the service exits non-zero, and `FailureAction = "reboot-force"`
triggers an immediate kernel-level reboot. Because a staged generation does not change the bootloader
default, this reboot lands on the previous committed generation.

The 180-second `OnActiveSec` value covers the full stage-confirm-commit budget, not activation
time alone. The dominant term is the deterministic Watchdog confirm window (120 s); stage activation
adds ≤16 s and the commit plus Orchestrator dispatch overhead adds ≤25 s, giving ≈161 s rounded up to
180 s for headroom. A single value serves all environments because the 120 s window dominates the
per-environment activation variance. Full timing data and the derivation are in
`docs/eval/rollback-gate-timings.md` and `docs/adr/0012-empirically-calibrated-rollback-deadline.md`.

The timer is armed only during a staged-but-uncommitted window. On a confirmed repair,
`commit_generation` disarms it with `systemctl stop rollback-gate.timer` before it can fire; on a
non-confirmed repair or an agent crash, the timer fires once and forces the revert. It uses
`OnActiveSec` rather than a repeating interval, so a single firing covers the window.

## Flux GitOps Layer

The desired NixOS configuration for each cluster node lives in the `infra/nixos/` tree in the Vigil
git repository, managed by Flux. Flux runs as a Kubernetes controller on the master node and
reconciles Kustomization resources against the git repository. The NixOS configurations are not
applied by Flux directly; they are applied by `nixos-rebuild` running on each node. Flux manages
the Kubernetes workloads and cluster-level resources; the NixOS configuration is applied out-of-band
via `nixos-mcp` when a fault requires it.

The interaction between the two layers becomes relevant when a cross-layer fault occurs: a NixOS
misconfiguration that also affects Kubernetes workloads. In such a scenario, the Remediation agent
must suspend the Flux Kustomization before patching any Kubernetes resource, and separately invoke
`stage_generation` on the affected node (with the Orchestrator committing via `commit_generation`
after the Watchdog confirms health). The Flux suspension prevents Flux from reconciling the
Kubernetes resource back to the faulty state while the NixOS repair is in progress.

The NixOS Flake at `infra/nixos/flake.nix` defines four host configurations:

| Host | Role | NixOS module |
|------|------|-------------|
| `hetzner-master` | K3s server, etcd, Flux controller | `k3s/server.nix`, `rollback-gate.nix` |
| `hetzner-worker-1` | K3s agent | `k3s/agent.nix`, `rollback-gate.nix` |
| `hetzner-worker-2` | K3s agent | `k3s/agent.nix`, `rollback-gate.nix` |
| `hetzner-agent` | Vigil agent host | (no k3s, no rollback-gate) |

Every cluster node imports `rollback-gate.nix`. The Vigil agent host does not, because it runs no
Kubernetes component and is not subject to OS-level repairs by the agent.

## Staging and the Health Gate

`stage_generation` is the entry verb for an OS-layer repair. It activates the target generation
non-durably with `switch-to-configuration test` and arms `rollback-gate.timer`, leaving the
bootloader default unchanged so any reboot reverts the stage. It does not commit the configuration:
the running system reflects the staged generation, but durability requires a later
`commit_generation` (`switch-to-configuration boot`).

The health gate has two independent enforcement points:

- The deterministic Watchdog confirms cluster health within its window after staging. Confirmation is
  the precondition the Orchestrator checks before committing.
- The armed `rollback-gate.timer` fires `rollback-gate.service`, which exits non-zero and forces a
  reboot to the prior committed generation. This enforcement runs independently of the agent: it
  fires by default and is suppressed only by the success-path disarm at commit.

On a confirmed repair, the Orchestrator deterministically calls `commit_generation`, which writes the
new bootloader default with `switch-to-configuration boot` and disarms the timer with
`systemctl stop rollback-gate.timer`. The remediation agent never commits; it can only stage.

If health is not confirmed, whether from degradation, timeout, or an agent crash, the timer fires and
`FailureAction=reboot-force` reboots the node. Because the stage never changed the bootloader default,
the reboot lands on the prior committed generation.

## OS Remediation Sequence

The full OS path for an agent-driven remediation:

1. Diagnosis agent sets `requires_os_level=True` in `DiagnosisReport`, populates `target_host` from
   the alert's `node` label.
2. Orchestrator passes `target_host` through `RemediationDeps` to the Remediation agent.
3. Remediation agent calls `get_generations(host=target_host)` to list available generations, then
   `stage_generation(host=target_host, generation=N)` to activate the target generation non-durably
   and arm `rollback-gate.timer`.
4. The deterministic Watchdog confirms cluster health within its window.
5. On confirmation, the Orchestrator deterministically calls `commit_generation(host=target_host)`,
   which makes the generation durable (`switch-to-configuration boot`) and disarms the timer.
6. On non-confirmation or an agent crash, the dead-man's switch timer fires 180 seconds after
   staging armed it and forces a reboot to the prior committed generation, regardless of agent state.

The `etcd_snapshot_save` tool provides a recovery point for the etcd control plane before a
destructive generation switch that crosses a major NixOS configuration boundary. It is called as a
precautionary step; the generation model itself provides OS-layer recovery without it.

## Host Allowlist

`nixos-mcp` maintains a static allowlist of SSH targets populated from the `SSH_HOSTS` environment
variable at server startup. Any `host` argument that is not in the allowlist is rejected before an
SSH connection is attempted:

```go
// mcp-servers/nixos-mcp/internal/nixos/client.go
func validateHost(host string, allowed []string) error {
    if len(allowed) == 0 {
        return fmt.Errorf("SSH_HOSTS is not configured; refusing to connect")
    }
    for _, h := range allowed {
        if h == host {
            return nil
        }
    }
    return fmt.Errorf("host %q is not in SSH_HOSTS allow-list", host)
}
```

This is a defence-in-depth measure: even if the LLM generates a `target_host` value that does not
correspond to a cluster node (e.g. an external host or a local path traversal attempt), the Go
server rejects it before any SSH dial. The `target_host` value itself originates from the alert's
`node` label, which is set by Prometheus at alert-fire time and is not under agent control.

## Related Documents

- [ADR-0004](../adr/0004-nixos-dead-mans-switch.md) — decision record for the dead-man's switch approach, including the alternatives considered
- `docs/eval/rollback-gate-timings.md` — empirical cold-start and warm-store timing measurements used to calibrate `OnActiveSec`
- `docs/architecture/mcp-servers.md` — nixos-mcp tool inventory and the read/write distinction within the tool set
- `docs/architecture/agent-design.md` — OS path branching in the Remediation agent and how `target_host` propagates from `DiagnosisReport`
