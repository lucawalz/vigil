---
status: Accepted
date: 2026-05-08
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0009: Hetzner Cloud cluster provisioning for eval campaigns

## Context and Problem Statement

Each eval campaign needs a fresh Kubernetes cluster. The permanent home-lab cluster retains state between runs (leftover namespaces, secrets, resource quotas) which causes cross-run interference. The eval harness must provision, run a full campaign, and tear down without manual steps beyond `terraform apply`.

## Decision Drivers

- Cluster state must be clean at campaign start; stale resources from prior runs skew results
- Provisioning must be scriptable so GitHub Actions can drive the full pipeline without SSH
- Flux v2 must reconcile eval workloads before scenarios begin; bootstrap must be automatic
- The SOPS age key for decrypting cluster secrets must survive re-provisions (Flux reads sealed secrets on every reconcile)
- Hetzner Cloud costs must stay within thesis budget (~20 EUR/month idle, ~5 EUR per campaign)

## Considered Options

- Hetzner Cloud + Terraform + Flux v2 bootstrap (chosen)
- Re-use permanent home-lab cluster with namespace isolation
- Managed Kubernetes (EKS, GKE)

## Decision Outcome

Chosen option: "Hetzner Cloud + Terraform + Flux v2 bootstrap", because each campaign starts from a clean cluster, cost stays within budget, and it integrates with the existing Flux GitOps setup.

`terraform apply` in `infra/terraform/` provisions three CX22 nodes, writes kubeconfigs, and bootstraps Flux via `null_resource.flux_bootstrap`. The public key (`age1sd72gjj4689pgw6lnzu7kac8dlstxt2elfxgr0urv5nml20569zsrkylka`) is registered in `infra/overlays/hetzner/.sops.yaml`; the matching SOPS age secret must be present in `flux-system` before Flux reconciles sealed secrets. See [ADR-0010](0010-github-actions-eval-runner.md) for how the secret is injected in the automated runner path.

### Consequences

- Good: Clean cluster state per campaign; stale resources from prior runs cannot interfere
- Good: Cost-effective; cluster is destroyed after each campaign and re-provisioned in ~5 minutes
- Bad: Running outside GitHub Actions requires SSH into the provisioned node, manual `kubectl create secret` for the SOPS age key, and triggering the eval harness by hand
- Bad: Hetzner availability zone outages affect campaign availability; no multi-region failover

**Validation Status:** Verified — Terraform apply provisioned the cluster and Flux reconciled eval workloads successfully in the v1.0 Hetzner eval campaign.

### Confirmation

Running `kubectl get nodes` after `terraform apply` shows three Ready nodes. Running `flux get kustomizations` shows `flux-system` reconciled. `eval/results/summary.json` contains runs produced against this cluster.

### Pros and Cons of the Options

#### Hetzner Cloud + Terraform + Flux v2 bootstrap

- Good: Each campaign starts from a fresh cluster; no state carries over between runs
- Good: Terraform state lives in `infra/terraform/`; provisioning is reproducible from any machine with the hcloud token
- Bad: `SOPS_AGE_KEY` must be set as a GitHub Actions secret; missing or wrong key causes Flux to fail silently on sealed secret decryption

#### Re-use permanent home-lab cluster with namespace isolation

- Good: No provisioning time; cluster is always available
- Bad: Namespace isolation does not prevent ResourceQuota, NetworkPolicy, or node-taint state from leaking between scenarios; the eval harness reset scripts assume a clean default namespace
- Bad: Home-lab hardware failures affect campaign availability with no recovery path

#### Managed Kubernetes (EKS, GKE)

- Good: High availability; managed control plane
- Bad: Significantly higher cost per campaign; IAM and VPC setup is out of scope for a thesis project

## More Information

- Terraform configuration: `infra/terraform/`
- SOPS encryption config: `infra/overlays/hetzner/.sops.yaml`
- Provisioning details and env vars: CLAUDE.md (Hetzner eval cluster section)
