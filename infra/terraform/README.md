# infra/terraform

Terraform module that provisions the Hetzner Cloud eval cluster: four `cpx22` servers for the hosts `vigil-control-plane-1`, `vigil-worker-1`, `vigil-worker-2` and `vigil-agent` (the control plane, two workers and the agent host) in `hel1` by default, a private network, a firewall and an SSH key. The servers boot from pre-built NixOS snapshots and take their private addresses from [`infra/inventory.json`](../inventory.json). Terraform then joins the K3s nodes, installs Flux on the eval branch through [`infra/scripts/flux-sync.sh`](../scripts/flux-sync.sh), applies the eval RBAC and starts the orchestrator on the agent host.

## Prerequisites

- Terraform 1.14 or later, `ssh`, `kubectl`, and `nix` on `PATH` (Flux is installed through `nix shell`).
- A Hetzner Cloud project and a read-write API token.
- One NixOS snapshot per role in that project, labelled `vigil-role=control-plane-1`, `worker-1`, `worker-2` and `agent` plus `vigil-run=<run id>`. The Eval Campaign workflow builds them for each campaign through the Build NixOS Snapshots workflow, with Packer from [`infra/packer/`](../packer/).
- The SOPS age private key for the recipient in [`infra/overlays/hetzner/.sops.yaml`](../overlays/hetzner/.sops.yaml), exported as `SOPS_AGE_KEY_FILE` or `SOPS_AGE_KEY`. Terraform decrypts the orchestrator webhook secret with it.
- An SSH key pair, `~/.ssh/id_ed25519` by default (`ssh_public_key_path` and `ssh_private_key_path` override it), and an existing `~/.kube/` directory.
- A GitHub token with write access to `lucawalz/vigil`, the repository that Flux, the hosts and the scenario scripts track.

## Variables

[`variables.tf`](variables.tf) is the source of truth.

| Variable | Default | Purpose |
|----------|---------|---------|
| `TF_VAR_hcloud_token` | required | Hetzner Cloud API token |
| `TF_VAR_github_token` | required | GitHub token for the orchestrator's pull requests and pushes; the Eval Campaign workflow maps the `VIGIL_GITHUB_TOKEN` secret to it |
| `TF_VAR_group_name` | required | Scenario group (`k8s`, `os`, `cross`, `misc`); prefixes every resource name |
| `TF_VAR_llm_model_name` | required | Orchestrator model, for example `qwen3.5:cloud` or `claude-sonnet-4-6` |
| `TF_VAR_anthropic_api_key` | empty | Required for `claude-*` models |
| `TF_VAR_ollama_api_key`, `TF_VAR_ollama_base_url` | empty | Required for every other model (OpenAI-compatible endpoint) |
| `TF_VAR_location` | `hel1` | `hel1`, `fsn1` or `nbg1` |
| `TF_VAR_vigil_branch` | `chore/eval-cluster-baseline` | Branch that Flux and the hosts track |
| `TF_VAR_run_id` | `local` | Suffix for resource names |
| `TF_VAR_campaign_run_id` | `local` | Value of the `vigil-run` label on every resource; selects the snapshots built for the same run |
| `TF_VAR_operator_ssh_pubkey` | empty | Extra public key added to every host |
| `TF_VAR_ssh_public_key_path`, `TF_VAR_ssh_private_key_path` | `~/.ssh/id_ed25519.pub`, `~/.ssh/id_ed25519` | Key pair for provisioning |

## Provision

```bash
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform apply
```

## After apply

The kubeconfig is written to `~/.kube/hetzner-vigil-<group_name>`. Flux decrypts the cluster secrets with a `sops-age` secret, created from the same age key:

```bash
export KUBECONFIG=~/.kube/hetzner-vigil-k8s
kubectl create secret generic sops-age --namespace=flux-system --from-file=age.agekey="$SOPS_AGE_KEY_FILE"
```

The orchestrator listens on port 9099 of the agent host:

```bash
ssh root@"$(terraform -chdir=infra/terraform output -raw agent_public_ip)" curl -sf http://localhost:9099/healthz
```

## Tear down

```bash
terraform -chdir=infra/terraform destroy
```

This removes the servers, network, firewall and SSH key. Every resource and snapshot carries `vigil-managed=true` and `vigil-run=<run id>`: the cleanup job of the Eval Campaign workflow deletes the ones of its run at the end of the campaign, and the Hetzner Sweep workflow runs daily and deletes any that are older than 12 hours and belong to no queued or running campaign or snapshot build.

## State

State is local and holds decrypted secrets. [`.gitignore`](.gitignore) excludes it from git.
