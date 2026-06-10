---
status: Accepted
date: 2026-04-22
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0008: Evaluation model selection

> Updated 2026-06-10: scenario set consolidated to the 13-scenario panel; run-count arithmetic restated accordingly.

## Context and Problem Statement

The evaluation campaign needs multiple LLMs to assess agent capability across the same 13 fault scenarios and compare open-weight models against a frontier reference. Three constraints drive model selection:

1. Models must expose an OpenAI-compatible API (per [ADR-0006](0006-openai-compatible-provider-interface.md))
2. Models must handle multi-step tool-use reasoning over Kubernetes and NixOS diagnostics with a context window of at least 32K tokens
3. The campaign needs at least one commercial frontier model as an upper-bound reference alongside open-weight alternatives, to support the thesis claim about open-weight viability for autonomous infrastructure remediation

Groq was evaluated as a fourth option but its rate limits make it impractical for a multi-run campaign.

## Decision Drivers

- Inter-provider comparison requires models at different capability tiers (open-weight and frontier)
- Campaign duration and Hetzner compute cost must remain within thesis budget
- All models must use the OpenAI-compatible endpoint to guarantee identical agent code paths (per ADR-0006)
- DeepSeek V3.2's 128K context window is the binding constraint; all scenarios must fit within it

## Considered Options

- Three-model panel: Qwen3 Coder Next + DeepSeek V3.2 + Claude Sonnet 4.6
- Groq-only (single provider, high throughput)
- Single-provider Anthropic-only
- Six-or-more model comparison

## Decision Outcome

Chosen option: "Three-model panel: Qwen3 Coder Next + DeepSeek V3.2 + Claude Sonnet 4.6", because three models cover the open-weight tier (Qwen3, DeepSeek) plus a frontier reference (Sonnet 4.6), the inter-provider variance signal is sufficient for the thesis claim, and campaign duration remains within budget at 3 models × 13 scenarios × 3 seeds = 117 runs.

| Model | Provider | Tag | Context | Rationale |
|-------|----------|-----|---------|-----------|
| Qwen3 Coder Next | Ollama Cloud | `qwen3-coder-next:cloud` | 256K | Strongest tool-use capability in the open-weight tier; MoE efficiency suits tool-call-heavy workloads |
| DeepSeek V3.2 | Ollama Cloud | `deepseek-v3.2:cloud` | 128K | Strong multi-step reasoning for complex diagnostic chains |
| Claude Sonnet 4.6 | Anthropic | `claude-sonnet-4-6` | 200K | Frontier reference; state-of-the-art agentic reasoning |

### Consequences

- Good: 3 models × 13 scenarios × 3 seeds = 117 evaluation runs total
- Good: All three providers expose an OpenAI-compatible endpoint; no agent code changes between runs
- Good: Open-weight tier (Qwen3, DeepSeek) plus frontier reference (Sonnet 4.6) spans the capability range needed for the thesis claim
- Bad: Groq is excluded from the eval campaign but documented for dev use; its rate limits preclude campaign-scale runs
- Bad: DeepSeek V3.2's 128K context window is the binding constraint; all scenarios must fit within it
- Bad: Claude Sonnet 4.6 run deferred to v2.0 pending Anthropic API key provisioning

**Validation Status:** Partial. The open-weight tier has been evaluated across the 13-scenario campaign; the Claude Sonnet 4.6 frontier reference remains deferred pending Anthropic API key provisioning.

### Confirmation

The eval campaign results published to the `docs/eval-results` branch record open-weight runs for `qwen3-coder-next:cloud` across the 13 scenarios. All runs use identical `run_orchestration()` code with only env-var provider changes.

### Pros and Cons of the Options

#### Three-model panel: Qwen3 Coder Next + DeepSeek V3.2 + Claude Sonnet 4.6

- Good: Covers open-weight and frontier tiers with three models; sufficient to support the thesis claim about open-weight viability
- Good: Campaign duration is bounded: the two open-weight models complete on the automated harness; the frontier reference is deferred without blocking thesis results
- Bad: Panel depth is limited; a fourth model (e.g. Llama 3.3) would add signal but multiplies campaign duration and cost

#### Groq-only

- Good: High token throughput; useful for rapid development iteration without rate-limit delays
- Bad: Groq's free-tier rate limits (per-minute token caps) would fragment a 117-run campaign into hundreds of resume cycles, breaking the campaign's wall-clock determinism and complicating run-id traceability. Useful for dev iteration; impractical as the campaign's sole provider.

#### Single-provider Anthropic-only

- Good: Single API key, consistent billing, strong agentic capability
- Bad: Running only Claude Sonnet 4.6 would eliminate the open-weight vs. frontier comparison that is central to the thesis argument; the research question about open-weight viability cannot be answered with a single frontier provider.

#### Six-or-more model comparison

- Good: Broader inter-model variance signal; more statistical power for capability claims
- Bad: Each additional model multiplies campaign duration and Hetzner spend; the marginal research value drops sharply past three models because the inter-provider variance signal saturates. Three models cover the open-weight tier (Qwen3, DeepSeek) plus a frontier reference (Sonnet 4.6), sufficient for the thesis claim.

## More Information

- Provider interface decision: [ADR-0006](0006-openai-compatible-provider-interface.md)
- Campaign results: published to the `docs/eval-results` branch
