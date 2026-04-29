# Eval harness

Run a single scenario: `uv run vigil-eval run --scenario k8s-1 --seed 1 --model qwen3`.

Run the full campaign: `uv run vigil-eval campaign --models qwen3 --models deepseek --seeds 1 --seeds 2 --seeds 3`.

Trace files are written to `eval/runs/{run_id}_trace.jsonl`. The campaign command prints the trace path after each run.
