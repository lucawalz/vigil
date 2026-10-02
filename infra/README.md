# Infrastructure

Configuration for the Hetzner Cloud eval cluster: NixOS hosts running K3s, reconciled by Flux.

- [`nixos/`](nixos/) - NixOS flake for the master, worker and agent hosts
- [`packer/`](packer/) - Packer template that builds one NixOS snapshot per host role
- [`terraform/`](terraform/README.md) - Terraform module that provisions the eval cluster from those snapshots
- [`overlays/hetzner/`](overlays/hetzner/README.md) - Flux GitOps source for the cluster
- [`kubernetes/rbac/`](kubernetes/rbac/) - service accounts and cluster roles for the eval runner and fault injection
- [`policy/`](policy/) - Rego policy applied by the remediation gate workflow
