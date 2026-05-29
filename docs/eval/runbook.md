# Eval runbook

SSH into the agent host, `cd ~/vigil`, then:

```bash
vigil-eval run --scenario os-1 --seed 1 --model qwen3-coder-next:cloud
```

The harness resets the cluster, injects the fault, fires the webhook, waits for the agent run to finish, and prints a summary. Results land in `eval/runs/` and `eval/runs_index.jsonl`.

Scenarios: `deceptive-2`, `disk-pressure`, `k8s-1g` through `k8s-5g`, `live-quota-injected`, `os-1`, `os-1g`, `os-drift-sysctl`, `os-stale-generation`. See [scenarios/README.md](scenarios/README.md) for the ground-truth label of each.

Run them sequentially — each one resets cluster state before injecting.

```bash
for s in k8s-1g k8s-2g k8s-3g k8s-4g k8s-5g os-1 os-1g os-drift-sysctl os-stale-generation deceptive-2 disk-pressure live-quota-injected; do
  vigil-eval run --scenario $s --seed 1 --model qwen3-coder-next:cloud
done
```

Check results:

```bash
tail -n 20 eval/runs_index.jsonl | jq '{scenario, outcome, MTTR_s}'
```

## Switching providers

Set these environment variables before running:

| Provider | `OLLAMA_BASE_URL` | `LLM_MODEL_NAME` | Notes |
|----------|-----------------|-----------------|-------|
| Ollama Cloud | `https://api.ollama.com/v1` | `qwen3-coder-next:cloud` | Eval campaign |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | Dev iteration only |

Set `OLLAMA_API_KEY` to the corresponding provider API key. For Anthropic (claude-* models), set `ANTHROPIC_API_KEY` instead — claude-* uses the native Anthropic SDK path, not `OLLAMA_BASE_URL`.

## Methodology and limitations

### Synthetic trigger

The harness does not exercise the detection path. Rather than wait for Prometheus to evaluate an alert rule, Alertmanager to fire, and the orchestrator's poller to pick it up, the harness hand-builds an Alertmanager-shaped webhook payload for the scenario and POSTs it directly to the orchestrator's `/webhook` endpoint (`eval/src/eval/harness.py`, `_build_fault_event` and `trigger_and_wait`). The payload carries the scenario's `alert_name` and the labels the diagnosis needs.

This deliberately bypasses Prometheus, Alertmanager, and the poller. It exercises the diagnosis → remediation → watchdog loop against genuinely injected faults — the inject scripts mutate real cluster and OS state before the webhook fires — but it does not validate the detection path (alert rules → Alertmanager → poller). Whether the right alert fires for a given fault in production is therefore out of scope for these runs and is a stated limitation of the evaluation.

### Reproducibility caveats

The following constrain how reproducible and statistically robust the results are:

- **Temperature is 1.0.** `build_model` sets `ModelSettings(temperature=1.0)` (`agents/common/src/common/provider.py`, `DEFAULT_TEMPERATURE`). Sampling is not greedy, so outputs vary run to run.
- **The "seed" is a run label, not a sampling seed.** The `--seed` value names the run and feeds the `run_id`; it is not passed to the model API. No sampling seed is set, so it cannot pin generation.
- **The model alias is not a dated snapshot.** Models are referenced by a moving alias (for example `qwen3-coder-next:cloud`), not a pinned dated snapshot, so the served weights may change over time.
- **Single seed per scenario (n=1).** Each scenario runs once per model; there is no repetition and therefore no measured variance. Reported per-scenario outcomes are single observations, not means with confidence intervals.
