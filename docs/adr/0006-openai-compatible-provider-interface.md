# ADR-0006: OpenAI-compatible provider interface for LLM hot-swap

**Status**: Accepted

## Context

The evaluation campaign compares three LLM providers across the same 12 fault scenarios. Forking agent code per provider would make inter-provider comparisons unreliable and maintenance expensive.

All targeted providers — Anthropic Claude (via Anthropic's OpenAI-compatible endpoint), Ollama Cloud (hosted open-weight models), Groq — expose an OpenAI-compatible REST API.

## Decision

Configure all agents against Pydantic AI's `OpenAIModel` class, pointed at a provider-specific `base_url` and `api_key` read from environment variables (`VIGIL_MODEL_BASE_URL`, `VIGIL_MODEL_NAME`, `VIGIL_API_KEY`). No provider SDK is imported directly.

## Consequences

- Switching providers requires changing two environment variables; no code changes are needed
- All three evaluation models run through identical agent code, ensuring a fair comparison
- Provider-specific features — Anthropic's extended thinking mode, Ollama-specific sampling parameters — are inaccessible through the compatibility layer
- Token accounting and latency metrics are normalized at the OpenAI response schema level, which may differ slightly from provider-native SDKs
