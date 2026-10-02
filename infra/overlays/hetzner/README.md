# infra/overlays/hetzner

Flux GitOps source for the Hetzner Cloud eval cluster. `flux bootstrap` points at `lucawalz/vigil` on the branch set by the Terraform variable `vigil_branch`, path `infra/overlays/hetzner/kubernetes/clusters/hetzner`.

## Platform values

- Disk device - `/dev/sda`; captured in `infra/nixos/hosts/hetzner-*/disko-config.nix`.
- Private network interface - `enp7s0` (Hetzner CPX22); captured in `infra/nixos/modules/k3s/hetzner.nix`.
- Alertmanager webhook URL - `http://10.0.0.40:9099/webhook` (agent host private IP, no TLS); captured in `values-alertmanager.yaml`.

## Rollback deadline

The dead-man's switch deadline is `OnActiveSec = 180s`, set once in `infra/nixos/modules/services/rollback-gate.nix`.

## Tree

- `kubernetes/clusters/hetzner/flux-system/` - Flux install manifests (written by `flux bootstrap github`).
- `kubernetes/clusters/hetzner/config/` - Kustomization chain (namespaces -> sources -> secrets -> infrastructure -> apps).
- `kubernetes/clusters/hetzner/{namespaces,sources,secrets,infrastructure,apps}/` - contents of each stage.
- `.sops.yaml` - SOPS creation rule binding `*.sops.yaml` to the operator's age recipient.
