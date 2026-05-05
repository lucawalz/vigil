# Vigil — NixOS GitOps and the Dead-Man's Switch

Vigil performs OS-level repairs by invoking `nixos-rebuild` on cluster nodes over SSH. Every such
repair is reversible by construction, not by convention. This document covers the NixOS generation
model as the rollback substrate, the dead-man's switch timer that enforces a hard revert deadline,
the Flux GitOps layer that manages the desired NixOS state, and the `nixos-mcp` tool sequence that
agents follow for OS-layer fault remediation.

## NixOS Generation Model

NixOS stores every system configuration as an immutable, bootloader-registered generation. A
generation is a complete, independently bootable system closure in `/nix/var/nix/profiles/system`.
Switching generations is atomic: the bootloader entry changes, the active configuration changes, and
the previous generation remains intact until explicitly garbage-collected.

`nixos-rebuild test` activates a new configuration in memory without writing a new bootloader entry.
The current generation pointer does not change. If the node reboots before a subsequent
`nixos-rebuild switch`, it boots back to the generation that was active before `nixos-rebuild test`
ran. This is not a Vigil-specific property; it is the standard NixOS behaviour for the `test`
subcommand.

Vigil exploits this property as a safety primitive: every OS repair attempt is a `nixos-rebuild test`
followed by a health check. If the health check fails, or if the agent crashes, or if the node
reboots for any reason, the node returns to its prior generation without agent intervention.

`switch_generation` in `nixos-mcp` provides the path for reverting to a specific prior generation:

```go
// mcp-servers/nixos-mcp/internal/nixos/client.go
func (c *realNixOSClient) SwitchGeneration(_ context.Context, host string, generation int) (string, error) {
    cmd := fmt.Sprintf(
        "sudo nix-env --switch-generation %d -p /nix/var/nix/profiles/system && sudo /nix/var/nix/profiles/system/bin/switch-to-configuration switch",
        generation,
    )
    return c.runSSH(host, cmd)
}
```

The two-step implementation reflects the difference between switching the profile pointer
(`nix-env --switch-generation`) and activating the configuration it points to
(`switch-to-configuration switch`). Switching the pointer alone does not restart services or update
the running environment; calling `switch-to-configuration switch` after it makes the system state
consistent with the newly active generation.

## Dead-Man's Switch Timer

The dead-man's switch is a systemd timer and service pair deployed on every cluster node via the
`rollback-gate.nix` NixOS module. It provides a hard revert deadline that operates independently of
the agent: if the node does not pass its health gate within the configured window after a
`nixos-rebuild test`, the timer fires the service, which either confirms the node is healthy or
forces a reboot.

```nix
# infra/nixos/modules/services/rollback-gate.nix
systemd.services.rollback-gate = {
  serviceConfig = {
    Type = "oneshot";
    ExecStart = pkgs.writeShellScript "rollback-gate-check" ''
      set -euo pipefail
      ${pkgs.systemd}/bin/systemctl is-active k3s.service
      kc=/etc/rancher/k3s/k3s.yaml
      if [ ! -f "$kc" ]; then kc=/var/lib/rancher/k3s/agent/kubelet.kubeconfig; fi
      status=$(KUBECONFIG=$kc ${pkgs.k3s}/bin/kubectl get node "${meta.hostname}" \
        -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
      [ "$status" = "True" ]
    '';
    FailureAction = "reboot-force";
    TimeoutStartSec = "120s";
  };
};

systemd.timers.rollback-gate = {
  wantedBy = [ "multi-user.target" ];
  timerConfig = {
    OnActiveSec = "24s";
    Unit = "rollback-gate.service";
  };
};
```

The timer fires once, 24 seconds after the system enters `multi-user.target`. The service checks two
conditions in sequence: `k3s.service` must be active, and the node must report `Ready` in the
Kubernetes API. If either check fails, `FailureAction = "reboot-force"` triggers an immediate
kernel-level reboot. Because `nixos-rebuild test` does not write a new bootloader entry, this reboot
lands on the previous generation.

The 24-second `OnActiveSec` value comes from empirical measurement. The worst-case warm-store
`nixos-rebuild test` activation time on the Hetzner CX23/CX33 VMs used in evaluation was 16 seconds
(hetzner-worker-2, run 2). The timer deadline is `ceil(16 * 1.5) = 24s`, giving a 50% margin above
the measured maximum. Full timing data is in `docs/eval/rollback-gate-timings.md`.

The timer runs unconditionally on every boot. On a node that is not in a `nixos-rebuild test` state,
the service checks health, finds `k3s.service` active and the node Ready, and exits successfully. The
timer fires exactly once per boot because it uses `OnActiveSec` rather than a repeating interval.

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
`rebuild_test` or `switch_generation` on the affected node. The Flux suspension prevents Flux from
reconciling the Kubernetes resource back to the faulty state while the NixOS repair is in progress.

The NixOS Flake at `infra/nixos/flake.nix` defines four host configurations:

| Host | Role | NixOS module |
|------|------|-------------|
| `hetzner-master` | K3s server, etcd, Flux controller | `k3s/server.nix`, `rollback-gate.nix` |
| `hetzner-worker-1` | K3s agent | `k3s/agent.nix`, `rollback-gate.nix` |
| `hetzner-worker-2` | K3s agent | `k3s/agent.nix`, `rollback-gate.nix` |
| `hetzner-agent` | Vigil agent host | (no k3s, no rollback-gate) |

Every cluster node imports `rollback-gate.nix`. The Vigil agent host does not, because it runs no
Kubernetes component and is not subject to OS-level repairs by the agent.

## RebuildTest and the Health Gate

The `rebuild_test` tool in `nixos-mcp` runs `nixos-rebuild test` on the target node and immediately
probes two health signals:

```go
// mcp-servers/nixos-mcp/internal/nixos/client.go
func (c *realNixOSClient) RebuildTest(_ context.Context, host string) (string, error) {
    _, rebuildErr := c.runSSH(host, "sudo nixos-rebuild test")
    exitCode := 0
    if rebuildErr != nil {
        exitCode = 1
    }

    healthGate, _ := c.runSSH(host, "systemctl is-active rollback-gate.service")
    healthGate = strings.TrimSpace(healthGate)

    k8sReady, _ := c.runSSH(host, `kubectl get node $(hostname) -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'`)
    k8sReady = strings.TrimSpace(k8sReady)

    result := fmt.Sprintf("nixos-rebuild exit: %d\nhealth-gate: %s\nk8s-node-ready: %s", exitCode, healthGate, k8sReady)
    return result, nil
}
```

The return value is a three-line string. The agent parses it to decide whether the trial activation
succeeded:

- `nixos-rebuild exit: 0` confirms the rebuild completed without error
- `k8s-node-ready: True` confirms the node is Ready in the Kubernetes API

The `health-gate` field reflects `systemctl is-active rollback-gate.service` at the moment of the
probe. This value is informational for the agent; the authoritative health enforcement is performed
by the timer firing independently, not by the agent reading this field.

A successful `rebuild_test` does not commit the new configuration. The Remediation agent exits the
OS path after a successful `rebuild_test` without calling `switch_generation`; the running system
reflects the `nixos-rebuild test` state, and the new configuration becomes permanent only after a
subsequent `nixos-rebuild switch` (outside the agent's scope) or a reboot that writes the new
bootloader entry through a later `switch` call.

If `rebuild_test` returns `nixos-rebuild exit: 1` or `k8s-node-ready: False`, the Remediation agent
calls `get_generations` to retrieve the available generation list and then calls `switch_generation`
with the previous generation number. `switch_generation` is therefore the rollback verb, not the
success verb.

## OS Remediation Sequence

The full OS path for an agent-driven remediation:

1. Diagnosis agent sets `requires_os_level=True` in `DiagnosisReport`, populates `target_host` from
   the alert's `node` label.
2. Orchestrator passes `target_host` through `RemediationDeps` to the Remediation agent.
3. Remediation agent calls `rebuild_test(host=target_host)`.
4. If `rebuild_test` returns a healthy result: exit OS path, no further action.
5. If `rebuild_test` returns an unhealthy result: call `get_generations(host=target_host)` to list
   available generations, then call `switch_generation(host=target_host, generation=N-1)` where
   `N-1` is the previous generation number.
6. The dead-man's switch timer fires 24 seconds after the next `multi-user.target` activation,
   regardless of agent state.

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
