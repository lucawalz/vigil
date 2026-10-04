# Infrastructure

Configuration for the vigil hosts: NixOS hosts running K3s, reconciled by Flux, on the Hetzner Cloud eval cluster or as local lab VMs.

- [`nixos/`](nixos/) - NixOS flake for the control plane, worker and agent hosts, with hetzner and lab profiles
- [`inventory.json`](inventory.json) - host names, roles and the address plan (`10.250.0.0/16`) shared by Nix, Terraform and the lab
- [`lab/`](lab/README.md) - lab runner that boots the hosts as local qemu VMs
- [`scripts/flux-sync.sh`](scripts/flux-sync.sh) - installs Flux and points it at a branch, for the eval cluster and the lab
- [`packer/`](packer/) - Packer template that builds one NixOS snapshot per host role
- [`terraform/`](terraform/README.md) - Terraform module that provisions the eval cluster from those snapshots
- [`overlays/hetzner/`](overlays/hetzner/README.md) - Flux GitOps source for the cluster
- [`overlays/lab/`](overlays/lab/) - Flux GitOps source for the lab cluster
- [`kubernetes/rbac/`](kubernetes/rbac/) - service accounts and cluster roles for the eval runner and fault injection
- [`policy/`](policy/) - Rego policy applied by the remediation gate workflow
