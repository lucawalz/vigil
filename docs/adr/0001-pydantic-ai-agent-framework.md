---
status: Accepted
date: 2026-04-14
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0001: Pydantic AI as agent orchestration framework

## Context and Problem Statement

Vigil requires an agent framework that provides structured, typed outputs as first-class results from agent runs, native MCP client support without a custom integration layer, sub-agent delegation with typed handoffs between Orchestrator, Diagnosis, Remediation, and Watchdog, and a provider-agnostic interface compatible with OpenAI-compatible endpoints (Anthropic, Ollama Cloud).

The framework must support a multi-agent architecture where each agent is a distinct reasoning unit returning a typed Pydantic model (`DiagnosisReport`, `RemediationResult`, `WatchdogResult`). It must also boot MCP server subprocesses once per FastAPI lifespan, hold them open across many agent runs, and expose their tools to the relevant agent without a custom subprocess-stdio wrapper. The Diagnosis agent additionally requires a filtered view of each MCP server (read-only tools only) without bespoke filtering logic.

## Decision Drivers

- Structured, validated outputs at the framework boundary prevent malformed agent results from propagating downstream
- Native MCP client (`MCPServerStdio`) eliminates subprocess management boilerplate
- Provider-agnostic `OpenAIProvider(base_url=...)` enables hot-swap between Anthropic and Ollama Cloud without code changes
- Typed sub-agent delegation expressed as function calls with Pydantic model inputs and outputs
- `FilteredToolset` from `pydantic_ai.toolsets` provides a read-only tool scope without a custom wrapper
- Async-first design must align with FastAPI's async lifespan and `asyncio.TaskGroup` parallel execution

## Considered Options

- Pydantic AI
- Anthropic SDK direct
- LangChain

## Decision Outcome

Chosen option: "Pydantic AI", because it is the only evaluated framework that natively integrates MCP client support, validates structured outputs at the framework boundary, and provides `FilteredToolset` for read-only agent scopes, all without custom integration code.

### Consequences

- Good: Structured agent outputs (`DiagnosisReport`, `RemediationResult`) are validated at the framework boundary, preventing malformed results from propagating downstream
- Good: Native MCP client support eliminates the need for a custom subprocess-stdio wrapper
- Good: Sub-agent delegation is expressed as typed function calls with Pydantic model inputs and outputs
- Good: `FilteredToolset` from `pydantic_ai.toolsets` provides the read-only Diagnosis tool scope without a custom wrapper; write tools (`delete_resource`, `stage_generation`, `commit_generation`, `etcd_snapshot_save`) are filtered at the framework boundary
- Bad: Pydantic AI is a relatively young library; community resources are limited compared to LangChain
- Bad: Async-first design requires careful asyncio lifecycle management, especially during agent teardown

**Validation Status:** Verified. `MCPServerStdio` boot-once-in-lifespan pattern confirmed in production; structured outputs validated across the v1.0 Hetzner eval campaign.

### Confirmation

The decision holds as long as:
- `MCPServerStdio` boots exactly once per FastAPI lifespan and serves all agent runs without reconnection
- `DiagnosisReport`, `RemediationResult`, and `WatchdogResult` are validated at the framework boundary with no manual parsing
- `FilteredToolset` correctly excludes write tools from the Diagnosis agent's tool scope
- Hot-swap between Ollama-compatible providers requires changing `OLLAMA_BASE_URL`; claude-* models use the native Anthropic SDK path configured via `ANTHROPIC_API_KEY`

### Pros and Cons of the Options

#### Pydantic AI

- Good: Native `MCPServerStdio` integration boots MCP servers as managed subprocesses with reconnect and retry support
- Good: `output_type=DiagnosisReport` validates structured outputs at the framework boundary without a hand-rolled validation layer
- Good: `FilteredToolset` provides scoped, read-only tool access for the Diagnosis agent without bespoke filtering logic
- Good: `OpenAIProvider(base_url=...)` enables provider-agnostic operation across Anthropic and Ollama Cloud endpoints
- Bad: Younger ecosystem with fewer community resources and less production track record than LangChain

#### Anthropic SDK direct

- Good: No framework dependency; full control over every API call and token count
- Bad: Direct SDK calls produce unstructured string outputs; reaching `DiagnosisReport`-grade typed outputs would require a hand-rolled validation layer per agent, multiplied across four agents. The same effort is encapsulated by Pydantic AI's `output_type=` parameter and validated at the framework boundary.

#### LangChain

- Good: Mature framework with large community and extensive integrations
- Bad: LangChain has no native MCP client; integrating it would require a custom subprocess-stdio wrapper duplicating what Pydantic AI's `MCPServerStdio` already provides, introducing a second asyncio lifecycle to manage and breaking the `mcptest` in-process test strategy that exercises `mcp-go` directly.

## More Information

- MCP-only tool surface decision: [`0002-mcp-exclusive-tool-surface.md`](0002-mcp-exclusive-tool-surface.md)
- OpenAI-compatible provider interface decision: [`0006-openai-compatible-provider-interface.md`](0006-openai-compatible-provider-interface.md)
