# infra/terraform

Terraform module that provisions the Hetzner Cloud eval cluster: four `cpx22` servers for the hosts `vigil-control-plane-1`, `vigil-worker-1`, `vigil-worker-2` and `vigil-agent` (the control plane, two workers and the agent host) in `hel1` by default, a private network, a firewall and an SSH key. The servers boot from pre-built NixOS snapshots and take their private addresses from [`infra/inventory.json`](../inventory.json). Terraform then joins the K3s nodes, generates the orchestrator webhook secret and stores it as `vigil-webhook-secret` in the `monitoring` namespace, installs Flux on the eval branch through [`infra/scripts/flux-sync.sh`](../scripts/flux-sync.sh), applies the eval RBAC and starts the orchestrator on the agent host.

## Prerequisites

- Terraform 1.14 or later, `ssh`, `kubectl`, and `nix` on `PATH` (Flux is installed through `nix shell`).
- A Hetzner Cloud project and a read-write API token.
- One NixOS snapshot per role in that project, labelled `vigil-role=control-plane-1`, `worker-1`, `worker-2` and `agent` plus `vigil-run=<run id>`. The Eval Campaign workflow builds them for each campaign through the Build NixOS Snapshots workflow, with Packer from [`infra/packer/`](../packer/).
- An SSH key pair, `~/.ssh/id_ed25519` by default (`ssh_public_key_path` and `ssh_private_key_path` override it), and an existing `~/.kube/` directory.
- A GitHub App installed on the repository in `github_repository`, which Flux, the hosts and the scenario scripts track (see [Running from a fork](#running-from-a-fork)).

## Variables

[`variables.tf`](variables.tf) is the source of truth.

| Variable | Default | Purpose |
|----------|---------|---------|
| `TF_VAR_hcloud_token` | required | Hetzner Cloud API token |
| `TF_VAR_github_repository` | required | GitHub repository as `owner/name`; the Eval Campaign workflow passes the repository it runs in |
| `TF_VAR_github_app_client_id` | required | Client ID of the GitHub App the orchestrator acts as; the Eval Campaign workflow maps the `VIGIL_APP_CLIENT_ID` secret to it |
| `TF_VAR_github_app_private_key` | required | Private key of that App in PEM form; the Eval Campaign workflow maps the `VIGIL_APP_PRIVATE_KEY` secret to it |
| `TF_VAR_group_name` | required | Scenario group (`k8s`, `os`, `cross`, `misc`); prefixes every resource name |
| `TF_VAR_llm_model_name` | required | Orchestrator model, for example `gpt-oss:120b` or `claude-sonnet-4-6` |
| `TF_VAR_anthropic_api_key` | empty | Required for `claude-*` models |
| `TF_VAR_ollama_api_key`, `TF_VAR_ollama_base_url` | empty | Required for every other model (OpenAI-compatible endpoint) |
| `TF_VAR_location` | `hel1` | `hel1`, `fsn1` or `nbg1` |
| `TF_VAR_vigil_branch` | `chore/eval-cluster-baseline` | Branch that Flux and the hosts track |
| `TF_VAR_run_id` | `local` | Suffix for resource names |
| `TF_VAR_campaign_run_id` | `local` | Value of the `vigil-run` label on every resource; selects the snapshots built for the same run |
| `TF_VAR_operator_ssh_pubkey` | empty | Extra public key added to every host |
| `TF_VAR_ssh_public_key_path`, `TF_VAR_ssh_private_key_path` | `~/.ssh/id_ed25519.pub`, `~/.ssh/id_ed25519` | Key pair for provisioning |

## Running from a fork

Packer, Flux and the hosts fetch the repository anonymously, so the fork is public.

One-time setup in the fork, in order:

1. Enable GitHub Actions, including scheduled workflows for the daily Hetzner Sweep.
2. Create the `eval` environment with the secrets listed under [Campaign workflow](../../eval/README.md#campaign-workflow).
3. Register a GitHub App under the fork owner's account with the webhook off and "Only on this account". Grant the repository permissions Contents read and write, Pull requests read and write, Checks read and Metadata read, and no others. Install it on the fork only, generate a private key, and add the App's client ID and the key as the `VIGIL_APP_CLIENT_ID` and `VIGIL_APP_PRIVATE_KEY` secrets. Pull requests, merges and agent commits then appear as `<app-slug>[bot]`. The App must not be a bypass actor of any ruleset, so that `remediation-gate` gates its pull requests.
4. Enable Settings > General > Pull Requests > Allow auto-merge.
5. Add a branch ruleset targeting `refs/heads/eval/**/*` that requires the `remediation-gate` status check. The campaign verifies this and the previous setting before it starts.
6. Make sure the Hetzner project has room for four servers at a time: the four snapshot builds run in parallel and finish before the four cluster servers of the first cell are created.

Then dispatch the Eval Campaign workflow with `target: hetzner`. Cell branches, the `docs/eval-results` results branch, snapshots and teardown are handled by the workflow.

## Provision

```bash
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform apply
```

## After apply

The kubeconfig is written to `~/.kube/hetzner-vigil-<group_name>`. The orchestrator listens on port 9099 of the agent host:

```bash
ssh root@"$(terraform -chdir=infra/terraform output -raw agent_public_ip)" curl -sf http://localhost:9099/healthz
```

## Tear down

```bash
terraform -chdir=infra/terraform destroy
```

This removes the servers, network, firewall and SSH key. Every resource and snapshot carries `vigil-managed=true` and `vigil-run=<run id>`: the cleanup job of the Eval Campaign workflow deletes the ones of its run at the end of the campaign, and the Hetzner Sweep workflow runs daily and deletes any that are older than 12 hours and belong to no queued or running campaign or snapshot build.

## State

State is local and holds the generated webhook secret and the provider tokens. [`.gitignore`](.gitignore) excludes it from git.
