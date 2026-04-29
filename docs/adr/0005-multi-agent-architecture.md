# ADR-0005: Dedicated-role multi-agent architecture

**Status**: Accepted

## Context

Fault diagnosis and remediation involve distinct reasoning tasks that compete for context window space when merged into a single agent:

- **Diagnosis**: ReAct-style iteration over Kubernetes and OS state to identify root causes
- **Remediation**: Selection and execution of the correct repair action
- **Monitoring**: Parallel health baseline capture and rollback trigger

A monolithic agent would carry diagnosis context, remediation state, and monitoring history simultaneously, increasing token costs and making it harder to reason about agent failures.

## Decision

Decompose into four agents with exclusive responsibilities:

| Agent | Responsibility |
|-------|---------------|
| **Orchestrator** | Entry point; receives `FaultEvent`; sequences Diagnosis → Remediation + Watchdog; owns circuit-breaker logic |
| **Diagnosis** | ReAct loop over Kubernetes and OS state; returns a typed `DiagnosisReport` |
| **Remediation** | Selects and executes the correct repair action; returns a typed `RemediationResult` |
| **Watchdog** | Runs in parallel with Remediation; captures health baseline; triggers rollback if health degrades |

## Consequences

- Each agent operates with a focused context window; diagnosis reasoning does not bleed into remediation
- Watchdog runs concurrently with Remediation via `asyncio.gather`, reducing overall MTTR
- Agent handoffs use typed Pydantic models, preventing implicit state passing between agents
- Four distinct agent lifecycles require careful asyncio management, particularly around MCP client teardown
- The Orchestrator coordinates workflow without reasoning about fault semantics directly
