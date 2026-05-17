---
status: Accepted
date: 2026-05-17
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0014: Multi-adapter model factory via Pydantic AI

## Context and Problem Statement

ADR-0006 selected a single OpenAI-compatible REST interface for every eval provider. That held while the model panel was open-weight models served via OpenAI-compat endpoints. Adding Claude Sonnet 4.6 to the panel exposed two limits of continuing to route Anthropic through its OpenAI-compat endpoint:

1. Pydantic AI agents rely on the full native tool-call and structured-output surface, which is more completely covered by Pydantic AI's native Anthropic adapter than by Anthropic's OpenAI-compatibility shim.
2. Pydantic AI already provides provider dispatch from a `"<provider>:<model>"` string via `infer_model`. Re-using it removes a layer of indirection (no second `base_url`, no compat shim) and avoids the `DeprecationWarning` Pydantic AI emits for bare `claude-*` names on the OpenAI path.

The factory boundary is unchanged: `build_model()` in `agents/common/src/common/provider.py` is still the only place an adapter is constructed, and every agent receives a `pydantic_ai.models.Model` without knowing which adapter produced it.

## Decision Drivers

- Adding Claude Sonnet 4.6 must not lose feature parity with the native Anthropic API for tool-use and structured outputs.
- Provider switching must remain env-var-driven; no agent code changes between runs.
- Agents must not import provider SDKs directly; the adapter choice stays inside `build_model()`.
- Inter-provider comparisons remain code-path-identical at the agent level — every agent calls `build_model()` and receives a `Model`.

## Considered Options

- Multi-adapter factory: `build_model()` dispatches on model-name prefix, returning `AnthropicModel` for `claude-*` and `OpenAIChatModel` otherwise.
- Continue routing Claude through Anthropic's OpenAI-compatible endpoint (ADR-0006 status quo).
- Adopt LiteLLM or a similar aggregator that hides both providers behind one API.

## Decision Outcome

Chosen option: "Multi-adapter factory", because Pydantic AI already encapsulates per-provider differences behind a single `Model` interface, the dispatch is one prefix check, and the agent code path is unchanged.

### Consequences

- Good: Native tool-call and structured-output coverage for Claude; no compat-shim limitations.
- Good: Adding a provider in future is one more branch in the factory; agent code never touches provider SDKs directly.
- Good: Env-var-driven config preserved — `LLM_MODEL_NAME` selects the adapter, `OLLAMA_*` and `ANTHROPIC_API_KEY` are read on demand.
- Bad: Token-accounting and latency normalisation now depend on Pydantic AI normalising across two `Model` subclasses rather than on a single shared REST schema.
- Bad: Cross-provider eval metrics must caveat that Anthropic and Ollama-compat paths use different Pydantic AI adapters; small inter-adapter differences may be absorbed into reported deltas.

**Validation Status:** Pending — covered by `tests/agents/test_provider.py`; runtime verification arrives with the first claude-* eval campaign.

### Confirmation

- `agents/common/src/common/provider.py` `build_model()` dispatches on model-name prefix; the function is the single construction site.
- `tests/agents/test_provider.py` covers both branches and the env-var default fallback.
- Eval campaign run records (`eval/runs/{run_id}.json`) keep the `model_version` tag and share the same `run_orchestration()` code path across adapters.

### Pros and Cons of the Options

#### Multi-adapter factory

- Good: One factory, one return abstraction (`pydantic_ai.models.Model`), zero agent-side coupling to the adapter choice.
- Bad: Two adapters in play instead of one REST contract; each future provider needs a dedicated branch rather than a pure env-var change.

#### Continue routing Claude through Anthropic's OpenAI-compat endpoint

- Good: Preserves ADR-0006 literally; one REST contract for every provider.
- Bad: Anthropic's OpenAI-compat shim does not cover Pydantic AI's tool-call and structured-output surface as cleanly as the native adapter; eval runs would either degrade Claude's tool-use fidelity or require workarounds in agent code, which defeats ADR-0006's reason for existing.

#### LiteLLM-style aggregator

- Good: Single configuration point; supports many providers out of the box.
- Bad: Adds a network hop and a third-party rate-limit envelope on top of every provider's. For long-running eval campaigns (one run = up to 25 Diagnosis + 20 Remediation requests), aggregator rate limits would fragment the campaign into resume cycles, breaking run-id traceability.

## More Information

- Provider configuration implementation: `agents/common/src/common/provider.py`
- Eval model panel: [ADR-0008](0008-evaluation-model-selection.md)
- Superseded ADR: [ADR-0006](0006-openai-compatible-provider-interface.md)
