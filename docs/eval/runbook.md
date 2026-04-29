# Eval runbook

SSH into the agent host, `cd ~/vigil`, then:

```bash
vigil-eval run --scenario os-1 --seed 1 --model qwen3-coder-next:cloud
```

The harness resets the cluster, injects the fault, fires the webhook, waits for the agent run to finish, and prints a summary. Results land in `eval/runs/` and `eval/runs_index.jsonl`.

Scenarios: `os-1`, `os-2`, `os-3`, `boundary-1`, `cross-1`, `cross-2`, `cross-3`, `k8s-1` through `k8s-5`.

Run them sequentially — each one resets cluster state before injecting.

```bash
for s in os-1 os-2 os-3 boundary-1 cross-1 cross-2 cross-3; do
  vigil-eval run --scenario $s --seed 1 --model qwen3-coder-next:cloud
done
```

Check results:

```bash
tail -n 20 eval/runs_index.jsonl | jq '{scenario, outcome, MTTR_s}'
```

## Switching providers

Set these environment variables before running:

| Provider | `LLM_BASE_URL` | `LLM_MODEL_NAME` | Notes |
|----------|---------------|-----------------|-------|
| Ollama Cloud | `https://api.ollama.com/v1` | `qwen3-coder-next:cloud` | Eval campaign |
| Anthropic | `https://api.anthropic.com/v1` | `claude-sonnet-4-6` | Eval campaign |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | Dev iteration only |

Set `LLM_API_KEY` to the corresponding provider API key.
