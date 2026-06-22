# infra/overlays/hetzner

Flux GitOps source for the Hetzner Cloud eval cluster. Self-contained in this repo - `flux bootstrap` points at `lucawalz/vigil` on the current branch, path `infra/overlays/hetzner/kubernetes/clusters/hetzner`.

## Differences vs infra/local

- Disk device - `/dev/sda` (Hetzner Cloud VMs); captured in `infra/nixos/hosts/hetzner-*/disko-config.nix`.
- Private network interface - `enp7s0` (Hetzner CX23/CX33); captured in `infra/nixos/modules/k3s/hetzner.nix`.
- Alertmanager webhook URL - `http://10.0.0.40:9099/webhook` (agent host private IP, no TLS); captured in `values-alertmanager.yaml`.
- Rollback-gate `OnActiveSec` - re-measured on Hetzner hardware; value set per-host in the `hetzner-*` NixOS configs.

## Tree

- `kubernetes/clusters/hetzner/flux-system/` - Flux install manifests (written by `flux bootstrap github`).
- `kubernetes/clusters/hetzner/config/` - three-tier Kustomization chain (namespaces -> sources -> secrets -> infrastructure -> apps).
- `kubernetes/clusters/hetzner/{namespaces,sources,secrets,infrastructure}/` - tier contents.
- `.sops.yaml` - SOPS creation rule binding `*.sops.yaml` to the operator's age recipient.
