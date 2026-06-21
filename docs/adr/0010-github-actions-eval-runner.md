---
status: Accepted
date: 2026-05-08
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0010: GitHub Actions as eval campaign runner

## Context and Problem Statement

Running a campaign manually requires SSH into the provisioned Hetzner node, installing the SOPS age key by hand, and triggering the eval harness from the command line. At 117 runs (3 models x 13 scenarios x 3 seeds) this is impractical and not reproducible across machines. The runner must manage the cluster lifecycle, inject secrets, sequence execution, and collect artifacts without manual steps.

## Decision Drivers

- Campaigns must be triggerable without SSH into the cluster node
- Scenarios must run sequentially; all share the same `default` namespace, so no two can run concurrently
- Secrets (hcloud token, LLM API key, SOPS age key) must never appear in the repo
- Artifacts from all groups must be merged into a single summary after all groups finish
- Trigger must be manual; campaigns are deliberate runs, not automatic on every push

## Considered Options

- GitHub Actions `workflow_dispatch` (chosen)
- Manual runs via SSH + shell script
- Self-hosted runner on the Hetzner node

## Decision Outcome

Chosen option: "GitHub Actions `workflow_dispatch`", because it requires no SSH, keeps all secrets in GitHub Actions secrets, and the matrix job model maps directly onto the sequential per-group execution pattern.

`eval-campaign.yml` has three jobs:

1. **`setup`**: builds the scenario matrix consumed by `run-scenarios`
2. **`run-scenarios`**: a matrix over two groups (`k8s`, `os`) with `max-parallel: 1` so the groups run sequentially; the job runs `terraform apply`, waits for Flux to reconcile, injects the SOPS age key from `SOPS_AGE_KEY` into `flux-system/sops-age` using `--dry-run=client | kubectl apply` (idempotent across retries), then runs each group's scenarios sequentially with `reset.sh` before `inject.sh`, uploading a trace artifact on completion
3. **`aggregate`**: downloads all group artifacts, runs `vigil-eval aggregate` to produce `summary.json` and `REPORT.md`, and uploads the result

The aggregate step is implemented and wired into the workflow but has not been validated against a full 117-run campaign. Output format and pass/fail thresholds should be verified before treating the summary as authoritative.

### Consequences

- Good: No SSH required; the full 117-run campaign is triggered by a single `workflow_dispatch`
- Good: The full campaign (provision, both scenario groups, aggregate) runs unattended from a single `workflow_dispatch`
- Good: All secrets live in GitHub Actions secrets; nothing is stored in the repo or on disk after the run
- Bad: `vigil-eval aggregate` is implemented but untested end-to-end; summary format and thresholds not yet validated
- Bad: `workflow_dispatch` only trigger; campaigns do not run automatically on push

**Validation Status:** Partial. The `setup`, `run-scenarios`, and `aggregate` jobs completed end-to-end in run `27908461169` (2026-06-21); the full 117-run campaign is pending.

### Confirmation

Latest successful run: `gh run view 27908461169`. Both scenario groups (`k8s`, `os`) completed and the `aggregate` job finished successfully.

### Pros and Cons of the Options

#### GitHub Actions `workflow_dispatch`

- Good: Secrets managed by GitHub; no credential files on disk
- Good: Matrix parallelism is a first-class primitive; no custom orchestration needed
- Bad: GitHub-hosted runners add cold-start overhead (~2 min per job); not suitable for sub-minute iteration

#### Manual runs via SSH

- Good: No CI setup required
- Bad: Not reproducible; depends on local state and manual sequencing of reset/inject steps
- Bad: Cannot parallelise scenario groups without custom tooling

#### Self-hosted runner on the Hetzner node

- Good: No cold-start; direct cluster access
- Bad: Runner process lives on the same node as the cluster; a bad scenario could kill the runner
- Bad: Requires the Hetzner node to be provisioned and kept alive between campaigns, removing the cost benefit of ephemeral clusters

## More Information

- Workflow: `.github/workflows/eval-campaign.yml`
- Cluster provisioning decision: [ADR-0009](0009-hetzner-cluster-provisioning.md)
- Eval harness entry point: `uv run vigil-eval campaign ...`
