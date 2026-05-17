---
status: Accepted
date: 2026-04-17
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0006: OpenAI-compatible provider interface for LLM hot-swap

## Context and Problem Statement

The evaluation campaign compares multiple LLM providers across the same 18 fault scenarios. Forking agent code per provider would make inter-provider comparisons unreliable and maintenance expensive. Three constraints shape the interface decision:

1. All targeted providers expose an OpenAI-compatible REST API: Anthropic Claude (via Anthropic's OpenAI-compatible endpoint) and Ollama Cloud (hosted open-weight models).
2. The eval harness requires identical agent code paths across providers so that performance differences reflect model capability, not implementation variance.
3. Provider switching must require zero code changes (only environment variables) so that the campaign can hot-swap models between runs without redeployment.

## Decision Drivers

- Inter-provider eval comparisons must be apples-to-apples; any code divergence per provider invalidates the comparison
- Provider switching for Ollama-compatible providers must be achievable by changing `OLLAMA_BASE_URL`, `LLM_MODEL_NAME`, and `OLLAMA_API_KEY`; claude-* models use the native Anthropic SDK path via `ANTHROPIC_API_KEY`
- No provider SDK may be imported directly into agent code
- The OpenAI-compatible REST layer must cover the full tool-call and structured-output surface used by Pydantic AI agents

## Considered Options

- OpenAI-compatible REST interface via Pydantic AI `OpenAIChatModel` (single interface, env-var hot-swap)
- Per-provider native SDKs (Anthropic SDK, Ollama SDK, etc.)
- LiteLLM-style aggregator as a unified proxy layer

## Decision Outcome

Chosen option: "OpenAI-compatible REST interface via Pydantic AI `OpenAIChatModel`", because all targeted providers expose a compatible endpoint, it enforces identical code paths across the campaign, and provider switching requires only environment variable changes.

### Consequences

- Good: Switching providers requires changing three environment variables; no code changes are needed
- Good: All evaluation models run through identical agent code, ensuring a fair inter-provider comparison
- Good: The v1.0 Hetzner eval campaign across qwen3-coder-next and deepseek-v3.2 ran without any code changes between providers, confirming the interface holds in practice
- Bad: Provider-specific features (Anthropic's extended thinking mode, Ollama-specific sampling parameters) are inaccessible through the compatibility layer
- Bad: Token accounting and latency metrics are normalized at the OpenAI response schema level, which may differ slightly from provider-native SDKs

**Validation Status:** Verified — `OpenAIChatModel` interface holds across two providers; v1.0 Hetzner eval campaign (qwen3-coder-next and deepseek-v3.2) ran with zero code changes between providers.

### Confirmation

The `OpenAIChatModel` configuration is verified in `agents/common/src/common/provider.py`. For Ollama-compatible providers, the env vars `OLLAMA_BASE_URL`, `LLM_MODEL_NAME`, and `OLLAMA_API_KEY` are the complete configuration surface. claude-* models use the native Anthropic SDK path instead, configured via `ANTHROPIC_API_KEY`. Eval campaign results show runs from two providers in `eval/results/summary.json` with identical `run_orchestration()` code paths.

### Pros and Cons of the Options

#### OpenAI-compatible REST interface via Pydantic AI `OpenAIChatModel`

- Good: Single code path across all providers; Pydantic AI's `OpenAIChatModel` handles tool-call schema translation
- Good: Env-var configuration is auditable and reproducible: `eval/runs/{run_id}.json` records the model tag used for each run
- Bad: Provider-specific capabilities (extended thinking, provider-native streaming formats) are unavailable

#### Per-provider native SDKs

- Good: Full access to provider-specific features and native error types
- Bad: Per-provider SDK forks would multiply agent code by the number of providers (Anthropic, Ollama Cloud, future Groq); inter-provider eval comparisons would no longer be apples-to-apples because token-accounting and tool-call schemas differ. The v1.0 Hetzner eval campaign across two providers ran identical agent code precisely because the provider boundary is one OpenAI-compatible HTTP request.

#### LiteLLM-style aggregator

- Good: Single configuration point for all providers; supports many providers out of the box
- Bad: An aggregator adds a network hop and a third-party rate-limit envelope on top of the provider's. For long-running eval campaigns (one run = up to 25 Diagnosis + 20 Remediation requests), aggregator rate limits would fragment the campaign into resume cycles, breaking the run-id traceability invariant.

## More Information

- Provider configuration implementation: `agents/common/src/common/provider.py`
- Model selection rationale: [ADR-0008](0008-evaluation-model-selection.md)
- Agent design and request limits: `docs/architecture/agent-design.md`
