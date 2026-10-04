# infra/overlays/hetzner

Flux GitOps source for the Hetzner Cloud eval cluster. [`infra/scripts/flux-sync.sh`](../../scripts/flux-sync.sh) installs Flux and points it at `lucawalz/vigil` on the branch set by the Terraform variable `vigil_branch`, path `infra/overlays/hetzner/kubernetes/clusters/hetzner`.

## Platform values

- Disk device - `/dev/sda`; captured in `infra/nixos/profiles/hetzner.nix`.
- Private network interface - `enp7s0` (Hetzner CPX22); captured in `infra/nixos/profiles/hetzner.nix`.
- Alertmanager webhook URL - `http://10.250.0.20:9099/webhook` (agent host private IP, no TLS); captured in `values-alertmanager.yaml`.

## Rollback deadline

The dead-man's switch deadline is `OnActiveSec = 180s`, set once in `infra/nixos/modules/services/rollback-gate.nix`.

## Tree

- `kubernetes/clusters/hetzner/config/` - Kustomization chain (namespaces -> sources -> secrets -> infrastructure -> apps).
- `kubernetes/clusters/hetzner/{namespaces,sources,secrets,infrastructure,apps}/` - contents of each stage.
- `.sops.yaml` - SOPS creation rule binding `*.sops.yaml` to the operator's age recipient.
