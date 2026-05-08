---
status: Accepted
date: 2026-04-20
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0005: Dedicated-role multi-agent architecture

## Context and Problem Statement

Fault diagnosis and remediation in a Kubernetes + NixOS system involve distinct reasoning tasks that compete for context window space when merged into a single agent. Three concerns shape the agent decomposition:

1. **Diagnosis** requires a ReAct-style iterative loop over Kubernetes and OS state (fetching logs, inspecting node conditions, escalating to NixOS diagnostics) to identify root causes. The intermediate reasoning steps (e.g., CrashLoopBackOff → log fetch → OOM signal → node memory pressure check) must remain coherent across many tool calls.
2. **Remediation** requires selecting and executing the correct repair action against a typed `DiagnosisReport` (suspending Flux, patching resources, or invoking `nixos-mcp` for OS-layer repairs) without re-running the diagnostic reasoning chain.
3. **Monitoring** requires a deterministic parallel health baseline capture and rollback trigger. No LLM is involved; the Watchdog agent polls `get_pods` on a fixed interval and compares `HealthSnapshot` deltas.

A monolithic agent would carry diagnosis context, remediation state, and watchdog history simultaneously, increasing token costs and forcing the LLM to keep all four reasoning concerns active in a single context window.

## Decision Drivers

- Focused context window per agent reduces token costs and reasoning error rates
- Typed handoffs between agents (`DiagnosisReport`, `RemediationResult`, `WatchdogResult`) eliminate implicit state passing
- Remediation and Watchdog can run concurrently, reducing overall MTTR
- Orchestrator can own circuit-breaker and rollback decisions without delegating control flow to an agent

## Considered Options

- Multi-agent decomposition with dedicated roles (Orchestrator, Diagnosis, Remediation, Watchdog)
- Monolithic single agent carrying all reasoning concerns
- Pipeline-of-functions without agent reasoning (no ReAct loop)

## Decision Outcome

Chosen option: "Multi-agent decomposition with dedicated roles", because focused context windows reduce per-agent token costs, typed handoffs make inter-agent state explicit, and the Remediation + Watchdog parallel execution pattern (via `asyncio.TaskGroup`) reduces MTTR while keeping rollback authority with the Orchestrator.

### Consequences

- Good: Each agent operates with a focused context window; diagnosis reasoning does not bleed into remediation state
- Good: Watchdog runs concurrently with Remediation via `asyncio.TaskGroup` (Python 3.11+ structured concurrency); when either task raises, the sibling is cancelled and the orchestrator handles the `ExceptionGroup` via `except*`
- Good: Agent handoffs use typed Pydantic models, preventing implicit state passing between agents
- Good: Watchdog observes health only; the Orchestrator owns the rollback decision and issues `kubectl-mcp rollout_undo` when `WatchdogResult.degraded=True`
- Bad: Four distinct agent lifecycles require careful asyncio management, particularly around MCP client teardown
- Bad: The Orchestrator coordinates workflow without reasoning about fault semantics directly; it delegates all LLM work to sub-agents

**Validation Status:** Verified — `asyncio.TaskGroup` pattern confirmed in production; circuit breaker essential; v1.0 Hetzner eval campaign confirms parallel pattern reduces MTTR vs sequential remediation and monitoring.

### Confirmation

The `asyncio.TaskGroup` pattern is confirmed in `agents/orchestrator/src/orchestrator/agent.py`. The four-agent split is verified by the module structure: `agents/orchestrator/`, `agents/diagnosis/`, `agents/remediation/`, `agents/watchdog/`. All eval campaign results use this decomposition.

### Pros and Cons of the Options

#### Multi-agent decomposition with dedicated roles

- Good: Diagnosis context isolation prevents remediation from seeing intermediate diagnostic reasoning, reducing token overhead per agent
- Good: Typed `DiagnosisReport` output is the only information passed to Remediation; no shared mutable state between agents
- Good: `asyncio.TaskGroup` semantics cancel both tasks on any exception, preventing a hung Watchdog from blocking orchestration
- Bad: Four agent lifecycles multiplied by four MCP server subprocesses require a careful lifespan strategy; `MCPServerStdio` boot-once in the FastAPI lifespan is the critical pattern

#### Monolithic single agent

- Good: Single context window means no typed handoff schema required
- Bad: A monolithic Pydantic AI agent would carry diagnosis context, remediation state, and watchdog history simultaneously, multiplying token costs and forcing the LLM to keep all four reasoning concerns active in one context window. A planned monolith evaluation campaign exists precisely to quantify this overhead; the multi-agent split is the baseline against which monolith performance will be measured.

#### Pipeline-of-functions (no ReAct loop)

- Good: Purely deterministic: no LLM token cost during execution
- Bad: A non-agent function pipeline would lose the ReAct iterative-reasoning property that Diagnosis requires for multi-step root-cause analysis (e.g. seeing CrashLoopBackOff → fetching logs → spotting OOM → checking node memory pressure). Hardcoding that decision tree per scenario does not scale to 18 fault types.

## More Information

- Agent responsibilities and tool scopes: `docs/architecture/agent-design.md`
- Orchestrator implementation: `agents/orchestrator/src/orchestrator/agent.py`
- Multi-agent coordination and the asyncio.TaskGroup pattern: see `docs/architecture/agent-design.md` §Parallel Remediation and Watchdog
