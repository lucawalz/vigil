# Eval harness

The harness drives one run as inject, then webhook, then orchestration, then a RunRecord JSON written to `eval/runs/`. Each RunRecord captures outcome, success rate, diagnosis accuracy, mean time to recovery, token and tool-call counts, iteration count, rollback status, and a destructive-repair safety metric.

## Where it runs

Runs execute on the agent host of the eval cluster provisioned by [`infra/terraform/`](../infra/terraform/README.md). The repository is checked out at `/root/vigil`, and the login shell loads `/etc/vigil/env` with the orchestrator URL, kubeconfigs and paths the scenario scripts need. The orchestrator listens on `http://localhost:9099`. The same scripts run against the local lab described in [`infra/lab/`](../infra/lab/README.md), where `lab.env` provides the variables.

## Scenarios

[`scenarios/`](scenarios/) holds 13 scenarios, eight Kubernetes and five OS. Each directory contains:

- `scenario.yaml` - layer, expected action, injected fault parameters, alert and verification
- `inject.sh` - applies the fault deterministically
- `reset.sh` - reverts it

## Commands

Run one scenario, seed and model:

```bash
uv run vigil-eval run --scenario k8s-1g --seed 1 --model qwen3.5:cloud
```

Sweep every scenario for the given models and seeds; the campaign pauses on provider quota exhaustion, and `--retry-failed` re-runs only failed combinations:

```bash
uv run vigil-eval campaign --models claude-sonnet-4-6 --models deepseek-v3.2:cloud --seeds 1 --seeds 2 --seeds 3
```

Aggregate completed runs:

```bash
uv run vigil-eval aggregate --seed-count 3
```

`uv run vigil-eval <command> --help` lists every option and its environment variable.

## Outputs

- `eval/runs/<run_id>.json` - one RunRecord per run
- `eval/runs/<run_id>_trace.jsonl` - the run trace; the campaign prints its path after each run
- `eval/runs_index.jsonl` - index of completed runs
- `eval/results/` - `summary.json`, `REPORT.md` and `step_summary.md` from `aggregate`

## Campaign workflow

The Eval Campaign workflow (`.github/workflows/eval-campaign.yml`) is started manually with a model, seed count, location and target. `target: hetzner` builds the NixOS snapshots for the campaign and provisions a fresh Terraform cluster for each scenario group at each seed, one after another, runs the scenarios on the agent host and destroys the clusters; `target: runner` boots the lab VMs on the GitHub runner, and `parallel` runs those cells side by side. The workflow then aggregates the results. Each cell works on its own branch `eval/<run_id>/<group>-<seed>`, created from `main` and deleted after aggregation. The run records carry their target, and aggregation covers one target at a time. The secrets come from the `eval` environment: `VIGIL_GITHUB_TOKEN` and `TF_VAR_LLM_MODEL_NAME` for every target, `TF_VAR_HCLOUD_TOKEN`, `OPERATOR_SSH_PUBKEY` and `SOPS_AGE_KEY` for `target: hetzner`, and the provider key for the chosen model. [`scripts/local-eval.sh`](../scripts/local-eval.sh) runs the same workflow locally with `act`.
