# ADR-0008: Evaluation model selection

**Status**: Accepted

## Context

The evaluation campaign needs multiple LLMs to assess capability across the same 12 fault scenarios. Three constraints drive model selection:

1. Models must expose an OpenAI-compatible API (per ADR-0006)
2. Models must handle multi-step tool-use reasoning over Kubernetes and NixOS diagnostics with a context window of at least 32K tokens
3. The campaign needs at least one commercial frontier model as an upper-bound reference alongside open-weight alternatives

Groq was evaluated as a fourth option but its rate limits make it impractical for a 108-run campaign. It remains useful for local development iteration.

## Decision

Three models for the evaluation campaign:

| Model | Provider | Tag | Context | Rationale |
|-------|----------|-----|---------|-----------|
| Qwen3 Coder Next | Ollama Cloud | `qwen3-coder-next:cloud` | 256K | Strongest tool-use capability in the open-weight tier; MoE efficiency suits tool-call-heavy workloads |
| DeepSeek V3.2 | Ollama Cloud | `deepseek-v3.2:cloud` | 128K | Strong multi-step reasoning for complex diagnostic chains |
| Claude Sonnet 4.6 | Anthropic | `claude-sonnet-4-6` | 200K | Frontier reference; state-of-the-art agentic reasoning |

## Consequences

- 3 models × 12 scenarios × 3 seeds = 108 evaluation runs total
- All three providers expose an OpenAI-compatible endpoint; no agent code changes between runs
- Groq is excluded from the eval campaign but documented in `docs/eval/runbook.md` for dev use
- DeepSeek V3.2's 128K context window is the binding constraint; all scenarios must fit within it
