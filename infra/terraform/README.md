# infra/terraform

Terraform module that provisions the Hetzner Cloud eval cluster: 4 VMs (1× master + 2× workers + 1× agent host), a private network, a firewall, and a NixOS installation per VM via the nixos-anywhere all-in-one Terraform module. Idempotent: `terraform apply` re-runs are no-ops unless a VM is replaced.

## Prerequisites

- Terraform 1.14+ installed locally
- `nix` available on PATH (nixos-anywhere is invoked via `nix run`)
- A Hetzner Cloud project and API token with read+write scope
- A local SOPS age private key matching the public key already trusted by the nixos-homelab flake
- The nixos-homelab flake exposing `nixosConfigurations.hetzner-master`, `nixosConfigurations.hetzner-worker-1`, `nixosConfigurations.hetzner-worker-2`, `nixosConfigurations.hetzner-agent`

## Environment variables

Set before running `terraform apply` or `terraform destroy`:

```
export TF_VAR_hcloud_token=<hetzner-cloud-api-token>
export TF_VAR_sops_age_key_path=/Users/luca/.config/sops/age/keys.txt
export SOPS_AGE_KEY_FILE=$TF_VAR_sops_age_key_path
```

Optional override:

```
export TF_VAR_ssh_public_key_path=$HOME/.ssh/id_ed25519.pub
```

Secrets are never written to Terraform state, `.tfvars`, or git.

## Provision

```
cd infra/terraform
terraform init
terraform apply
```

The first apply takes ~10-15 minutes (kexec into rescue, disko partitioning, NixOS install, reboot, K3s join). Subsequent applies converge without changes unless a VM is replaced.

## Tear down

```
cd infra/terraform
terraform destroy
```

This removes Hetzner cloud resources only. The hetzner-* host attributes in nixos-homelab and the additional public keys in `secrets/secrets.nix` remain - remove them manually if no longer needed.

## Cost

Pricing as of 2026-04 (Hetzner Cloud Nuremberg):

| Host             | Type | Hourly  | Daily  |
|------------------|------|---------|--------|
| hetzner-master   | CX33 | €0.012  | €0.288 |
| hetzner-worker-1 | CX23 | €0.008  | €0.192 |
| hetzner-worker-2 | CX23 | €0.008  | €0.192 |
| hetzner-agent    | CX23 | €0.008  | €0.192 |
| **Total**        |      | **€0.036/h** | **€0.864/day** |

Run `terraform destroy` after each eval campaign block to bound spend.
