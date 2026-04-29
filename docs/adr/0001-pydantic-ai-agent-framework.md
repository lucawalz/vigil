# ADR-0001: Pydantic AI as agent orchestration framework

**Status**: Accepted

## Context

Vigil requires an agent framework that provides:

- Structured, typed outputs (Pydantic models) as first-class results from agent runs
- Native MCP client support without a custom integration layer
- Sub-agent delegation with typed handoffs between Orchestrator, Diagnosis, Remediation, and Watchdog
- A provider-agnostic interface compatible with OpenAI-compatible endpoints (Anthropic, Ollama Cloud)

Alternatives evaluated include calling the Anthropic API directly (high boilerplate, no structured output guarantees) and LangChain (mature but heavyweight, lacks native MCP client).

## Decision

Use [Pydantic AI](https://ai.pydantic.dev/) as the agent orchestration framework for all Python agents.

## Consequences

- Structured agent outputs (`DiagnosisReport`, `RemediationResult`) are validated at the framework boundary, preventing malformed results from propagating downstream
- Native MCP client support eliminates the need for a custom subprocess-stdio wrapper
- Sub-agent delegation is expressed as typed function calls with Pydantic model inputs and outputs
- Pydantic AI is a relatively young library; community resources are limited compared to LangChain
- Async-first design requires careful asyncio lifecycle management, especially during agent teardown
