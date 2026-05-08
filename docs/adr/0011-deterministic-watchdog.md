---
status: Accepted
date: 2026-05-08
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0011: Deterministic Watchdog

## Context and Problem Statement

During OS-layer remediation the Watchdog agent runs concurrently with Remediation (via `asyncio.TaskGroup`) and observes cluster health on a fixed poll interval. When health degrades, the Watchdog signals `WatchdogResult.degraded=True` and the Orchestrator issues `kubectl-mcp rollout_undo`. This path is safety-critical: a false negative (missed degradation) leaves a broken node live; a false positive triggers an unnecessary rollback that aborts a valid repair.

Two properties of LLM-backed health assessment make it unsuitable for this path:

1. **Hallucination surface**: An LLM interpreting `get_pods` output could reason itself into "the pods look mostly fine" despite a CrashLoopBackOff, particularly when tool output is incomplete. A deterministic snapshot diff has no such failure mode.
2. **Token cost and latency**: The Watchdog polls every few seconds throughout the entire remediation window. Calling an LLM per poll tick adds hundreds of milliseconds per call and accumulates significant token cost over a 24 s window with no accuracy gain over a simple pod-count comparison.

## Decision Drivers

- Zero hallucination surface in the rollback decision
- No token cost in the Watchdog poll loop
- No added latency: deterministic snapshot diff is sub-millisecond vs. 100–500 ms per LLM call
- Clean separation of concerns: Watchdog observes and classifies; Orchestrator decides and acts

## Considered Options

- Deterministic Watchdog (pure Python `HealthSnapshot` delta comparison, no LLM)
- LLM-backed Watchdog (Pydantic AI agent calling `get_pods` + LLM health reasoning)
- External alerting (Prometheus AlertManager driving rollback via webhook)

## Decision Outcome

Chosen option: "Deterministic Watchdog", because it eliminates hallucination surface from the rollback path entirely, operates at poll-loop frequency with no token overhead, and the Orchestrator retains sole rollback authority.

### Consequences

- Good: The rollback trigger path contains no LLM call; degradation classification is a deterministic comparison of `HealthSnapshot` fields (ready-pod count, restart counts, node-ready status)
- Good: Watchdog poll loop incurs zero token cost regardless of how many ticks occur during the remediation window
- Good: The Watchdog only returns `WatchdogResult`; the Orchestrator calls `rollout_undo`. No agent can bypass this boundary.
- Bad: The deterministic diff cannot reason about partial degradation (e.g., a pod that is Ready but serving 5xx responses); application-layer health is outside the Watchdog's scope
- Bad: Health classification logic must be maintained in Python; adding a new signal (e.g., HPA scale-down event) requires a code change, not a prompt update

**Validation Status:** Verified — Watchdog implementation in `agents/watchdog/` contains no LLM calls; health assessment is a `HealthSnapshot` delta in pure Python. ADR-0005 confirms Watchdog runs concurrently with Remediation via `asyncio.TaskGroup`.

### Confirmation

The decision holds as long as:
- `agents/watchdog/src/watchdog/agent.py` contains no `model=` parameter or LLM client instantiation
- `HealthSnapshot` comparison is the sole basis for `WatchdogResult.degraded`
- The Orchestrator (not the Watchdog) issues `rollout_undo` in response to `WatchdogResult.degraded=True`

### Pros and Cons of the Options

#### Deterministic Watchdog

- Good: Snapshot delta comparison is a pure function; given identical cluster state it always produces the same `WatchdogResult`
- Good: Poll loop can run at 1–5 s intervals with no cost; LLM-backed polling at the same cadence would accumulate hundreds of LLM calls per eval scenario
- Bad: Cannot infer health signals outside the MCP tool surface (e.g., application-level error rates in Prometheus)

#### LLM-backed Watchdog

- Good: Could reason about ambiguous partial-degradation states that a threshold comparison would miss
- Bad: An LLM interpreting `get_pods` output can produce a "mostly healthy" conclusion from a degraded cluster because it is trained to hedge uncertainty. In the rollback path, this hallucination surface directly delays a safety-critical intervention: a node running a bad NixOS configuration would remain active past the dead-man's switch window, potentially losing quorum.

#### External alerting (Prometheus AlertManager)

- Good: Purpose-built for production alerting; handles sustained degradation, flap suppression, and routing
- Bad: AlertManager requires a Prometheus stack inside the cluster. During OS-layer repairs the cluster itself may be partially degraded; relying on in-cluster alerting to detect cluster degradation creates a circular dependency where the monitor and the monitored share the same failure domain. A pod-count diff executed from outside the cluster (via `kubectl-mcp`) does not share this failure domain.

## More Information

- Multi-agent architecture and `asyncio.TaskGroup` concurrency: `docs/adr/0005-multi-agent-architecture.md`
- Dead-man's switch and rollback gate: `docs/adr/0004-nixos-dead-mans-switch.md`
- Watchdog implementation: `agents/watchdog/src/watchdog/agent.py`
