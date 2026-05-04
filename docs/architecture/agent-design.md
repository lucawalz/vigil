# Vigil — Agent Design

Vigil decomposes autonomous fault diagnosis and remediation into four agents with exclusive responsibilities: an Orchestrator that manages control flow without reasoning about fault semantics, a Diagnosis agent that applies a ReAct loop over read-only Kubernetes and OS state, a Remediation agent that executes repair actions through write-capable MCP tools, and a Watchdog that deterministically monitors cluster health in parallel with remediation. Each agent's context window carries only the information relevant to its task, preventing diagnosis reasoning from bleeding into remediation state and keeping each failure domain isolated.

## Agent Topology

| Agent | Package | Entry Point | Output Type | Tool Scope | LLM? |
|-------|---------|-------------|-------------|------------|------|
| Orchestrator | `agents/orchestrator` | `run_orchestration()` | `RunRecord` | None directly; delegates | No (control only) |
| Diagnosis | `agents/diagnosis` | `run_diagnosis()` | `DiagnosisReport` | kubectl-mcp (read-only via FilteredToolset), nixos-mcp (read-only via FilteredToolset) | Yes — ReAct, 25-request cap |
| Remediation | `agents/remediation` | `run_remediation()` | `RemediationResult` | kubectl-mcp, flux-mcp, nixos-mcp | Yes — 20-request cap |
| Watchdog | `agents/watchdog` | `run_watchdog()` + `capture_health_snapshot()` | `WatchdogResult` | kubectl-mcp (`get_pods` only) | No — deterministic poll loop |

## Orchestrator

The Orchestrator receives `FaultEvent` objects from two sources: an Alertmanager webhook on the fast path (`POST /alert`) and a Prometheus poller that queries `GET /api/v1/alerts` every `PROM_POLL_INTERVAL_S` seconds (default 120). Fingerprint-based deduplication with a `PROM_HANDLED_TTL_S` TTL (default 600 seconds) prevents duplicate dispatch when both paths detect the same alert.

The `run_orchestration()` function drives the complete fault-to-record lifecycle:

1. Ingest `FaultEvent` and generate a `run_id` keyed on scenario, seed, model name, and git SHA.
2. Run the Diagnosis agent to produce a `DiagnosisReport`.
3. Call `capture_health_snapshot()` via Watchdog deps to record the pre-remediation baseline.
4. Launch Remediation and Watchdog in parallel via `asyncio.TaskGroup`.
5. Inspect `WatchdogResult.degraded`: if `True`, issue `rollout_undo` through kubectl-mcp. The Orchestrator owns this rollback decision; the Watchdog only observes.
6. Write the final `RunRecord` to `eval/runs/{run_id}.json`.

The Orchestrator holds no LLM agent; it is pure control flow. The decomposition rationale is documented in [ADR-0005](../adr/0005-multi-agent-architecture.md).

## Diagnosis

The Diagnosis agent operates a ReAct [1] loop over read-only Kubernetes and OS state. Its tool scope is enforced by `FilteredToolset`, which filters out write-capable tools before they reach the agent:

```python
# agents/diagnosis/src/diagnosis/agent.py
_nixos_write_tools = frozenset({"switch_generation", "etcd_snapshot_save"})
_kubectl_write_tools = frozenset({"apply_patch", "rollout_undo"})
kubectl_readonly = FilteredToolset(
    deps.kubectl_mcp,
    filter_func=lambda _ctx, tool_def: tool_def.name not in _kubectl_write_tools,
)
nixos_readonly = FilteredToolset(
    deps.nixos_mcp,
    filter_func=lambda _ctx, tool_def: tool_def.name not in _nixos_write_tools,
)
```

This makes read-only enforcement a structural property, not a prompt convention: the write tools are absent from the agent's tool list at construction time.

The Diagnosis agent implements two-tier escalation. It begins with kubectl-mcp tools (`get_nodes`, `get_pods`, `describe_pod`, `get_logs`, `rollout_status`). When kubectl evidence is insufficient and the fault implicates a node condition or NixOS service, the agent sets `requires_os_level=True` in the `DiagnosisReport` and records the `target_host` value from the alert's `node` label. The `target_host` field then propagates to all nixos-mcp calls in the Remediation phase. The Diagnosis agent is capped at 25 requests (`DIAGNOSIS_REQUEST_LIMIT` env var, default 25).

### ReAct Background

The Reason+Act pattern [1] interleaves explicit reasoning traces with action calls, allowing an agent to observe tool outputs and revise its hypothesis before committing to a conclusion. In Vigil's Diagnosis agent, each iteration consists of the agent reasoning about accumulated kubectl or nixos-mcp evidence, selecting the next tool call, observing the output, and updating its working hypothesis. The loop terminates when the agent emits a structured `DiagnosisReport` or the request cap is reached.

This interleaved trace structure is what distinguishes a ReAct agent from a one-shot tool-use call: the agent's intermediate reasoning is visible in the message history, making the diagnosis process auditable per run via the trace files written to `eval/runs/{run_id}/`.

## Remediation

The Remediation agent selects and executes repair actions based on the `DiagnosisReport.requires_os_level` flag. The Pydantic AI `UsageLimits` mechanism enforces a hard cap of 20 requests (see [ADR-0001](../adr/0001-pydantic-ai-agent-framework.md) for the framework choice that supplies this capability).

**K8s path** (`requires_os_level=False`):

1. `suspend_kustomization` — mandatory first call; the flux-mcp `guardMutation` middleware rejects any subsequent mutation unless the named Kustomization is registered in the server's `suspendedNames` map.
2. `apply_patch` or `rollout_undo` — the repair action per `recommended_action`.
3. `resume_kustomization` — closes the suspension window so Flux reconciliation resumes on the corrected manifest.

**OS path** (`requires_os_level=True`):

1. Skip Flux tooling entirely — no Kustomization is involved in an OS-layer fault.
2. `rebuild_test(host=target_host)` — trial activation of the current NixOS configuration. Success requires both `"nixos-rebuild exit: 0"` and `"k8s-node-ready: True"` in the output.
3. If `rebuild_test` fails: `get_generations` to list available generations, then `switch_generation(host, prev_gen)` to activate the previous generation. `switch_generation` is the primary OS remediation verb validated across the OS and cross-layer eval scenarios.

The `target_host` value (from the alert `node` label) is threaded from `DiagnosisReport` through all nixos-mcp calls, ensuring every OS operation targets the correct node.

## Watchdog

The Watchdog agent runs a deterministic poll loop with no LLM involvement. Its operation divides into two phases within a single run.

Before remediation starts, `capture_health_snapshot()` records the pre-remediation baseline: a single `get_pods` call to kubectl-mcp produces a `HealthSnapshot` with `ready_pods`, `total_pods`, and `endpoints_healthy`. This baseline is passed into `run_watchdog()`.

During remediation, `run_watchdog()` polls `get_pods` every `WATCHDOG_POLL_INTERVAL_S` seconds (default 5) for a window of `WATCHDOG_WINDOW_S` seconds (default 120). Each observation is compared to the baseline: `WatchdogResult(degraded=True)` is returned on the first poll where `ready_pods` falls below baseline or `endpoints_healthy` transitions from `True` to `False`.

Watchdog observes only. It does not call mutation tools and does not issue rollbacks. When `degraded=True` is returned, the Orchestrator is the decision-maker: it calls `rollout_undo` through kubectl-mcp for each resource in `DiagnosisReport.affected_resources`.

## Parallel Remediation and Watchdog

The parallel execution of Remediation and Watchdog is the architectural centerpiece of Vigil's multi-agent design. The two tasks are launched inside a Python 3.11+ `asyncio.TaskGroup`:

```python
# agents/orchestrator/src/orchestrator/agent.py
async with asyncio.TaskGroup() as tg:
    rem_task = tg.create_task(
        run_remediation(remediation_deps, report, model=model)
    )
    wtch_task = tg.create_task(
        run_watchdog(watchdog_deps, baseline)
    )
```

The matching exception handler uses the `except*` syntax introduced alongside `TaskGroup` in Python 3.11:

```python
except* (UsageLimitExceeded, UnexpectedModelBehavior, CircuitBreakerTripped) as eg:
    raise eg.exceptions[0]
```

`asyncio.TaskGroup` provides structured concurrency semantics that `asyncio.gather` does not. When any child task raises an exception, the `TaskGroup` immediately cancels all remaining sibling tasks and aggregates all exceptions into an `ExceptionGroup`. The `except*` clause then consumes the `ExceptionGroup` and re-raises the first exception for the Orchestrator to handle.

The practical consequence for Vigil is deterministic failure handling: if Remediation hits the circuit breaker or the request cap, the Watchdog poll loop is cancelled immediately rather than continuing to accumulate observations against a remediation that has already aborted. The Orchestrator receives a single exception rather than a partial result paired with a still-running task. Using `asyncio.gather` would require explicit cancellation logic and expose a window where the Watchdog continues polling after the Remediation future has settled, producing a race between the gather result and the Watchdog's next poll.

## Circuit Breaker

The `_CircuitBreaker` class in `agents/orchestrator/src/orchestrator/agent.py` counts consecutive MCP tool errors. At 3 consecutive errors it raises `CircuitBreakerTripped`, which propagates out of the `asyncio.TaskGroup` as described above.

Request caps are enforced at the Pydantic AI `UsageLimits` layer independently of the circuit breaker:

- Diagnosis: 25 requests (`DIAGNOSIS_REQUEST_LIMIT` env var, default 25)
- Remediation: 20 requests (`UsageLimits(request_limit=20)`, fixed)

When either cap is exceeded, Pydantic AI raises `UsageLimitExceeded`. The Orchestrator catches this at line 349 of `agent.py` and writes a `RunRecord` with `outcome="abort"` and `abort_reason="iteration_limit_20"`. The abort string `"iteration_limit_20"` is a fixed literal in the codebase derived from the Remediation agent's cap; it also applies when the Diagnosis 25-request cap triggers the exception. This is an implementation naming quirk and carries no architectural significance.

All dependency structs (`OrchestratorDeps`, `DiagnosisDeps`, `RemediationDeps`, `WatchdogDeps`) are frozen dataclasses, ensuring no shared mutable state between agents during a run. The one session-level stateful object is the flux-mcp server's `suspendedNames` map, which lives in the Go process and is therefore isolated to the server boundary.

## Fault Handling — Sequence Diagram

```mermaid
sequenceDiagram
    participant Prom as Prometheus
    participant AM as Alertmanager
    participant Orch as Orchestrator
    participant Diag as Diagnosis
    participant Rem as Remediation
    participant Watch as Watchdog
    participant KM as kubectl-mcp
    participant FM as flux-mcp
    participant NM as nixos-mcp

    Prom->>AM: alert fires
    AM->>Orch: POST /alert (FaultEvent)
    Orch->>Diag: run_diagnosis(FaultEvent)

    alt Happy path — K8s fault
        loop ReAct iterations (up to 25 requests)
            Diag->>KM: get_pods / describe_pod / get_logs
            KM-->>Diag: tool output
        end
        Diag-->>Orch: DiagnosisReport(requires_os_level=False)
        Orch->>KM: capture_health_snapshot (get_pods)
        KM-->>Orch: HealthSnapshot (baseline)
        par asyncio.TaskGroup
            Orch->>Rem: run_remediation(report)
            Rem->>FM: suspend_kustomization
            FM-->>Rem: ok
            Rem->>KM: apply_patch
            KM-->>Rem: ok
            Rem->>FM: resume_kustomization
            FM-->>Rem: ok
            Rem-->>Orch: RemediationResult(success=True)
        and
            Orch->>Watch: run_watchdog(baseline)
            loop every 5 s for 120 s
                Watch->>KM: get_pods
                KM-->>Watch: pod counts
            end
            Watch-->>Orch: WatchdogResult(degraded=False)
        end
        Orch->>Orch: write RunRecord(outcome=success)
    end

    alt Circuit breaker trip
        loop ReAct iterations
            Diag->>KM: get_pods
            KM-->>Diag: tool output
        end
        Diag-->>Orch: DiagnosisReport
        Orch->>KM: capture_health_snapshot
        KM-->>Orch: HealthSnapshot
        par asyncio.TaskGroup
            Orch->>Rem: run_remediation(report)
            Rem->>KM: apply_patch (error 1)
            Rem->>KM: apply_patch (error 2)
            Rem->>KM: apply_patch (error 3)
            Rem-->>Orch: CircuitBreakerTripped
        and
            Orch->>Watch: run_watchdog(baseline)
            Note over Watch: cancelled by TaskGroup on exception
        end
        Orch->>Orch: write RunRecord(outcome=abort, abort_reason=circuit_breaker_3_consecutive_errors)
    end

    alt Watchdog rollback trigger
        Diag-->>Orch: DiagnosisReport
        Orch->>KM: capture_health_snapshot
        KM-->>Orch: HealthSnapshot
        par asyncio.TaskGroup
            Orch->>Rem: run_remediation(report)
            Rem-->>Orch: RemediationResult(success=True)
        and
            Orch->>Watch: run_watchdog(baseline)
            Watch->>KM: get_pods
            KM-->>Watch: ready_pods < baseline
            Watch-->>Orch: WatchdogResult(degraded=True)
        end
        Orch->>KM: rollout_undo(affected_resources)
        KM-->>Orch: ok
        Orch->>Orch: write RunRecord(rollback_triggered=True)
    end

    alt Iteration limit abort (Diagnosis)
        loop ReAct — 25 requests reached
            Diag->>KM: get_pods
            KM-->>Diag: tool output
        end
        Diag-->>Orch: UsageLimitExceeded
        Orch->>Orch: write RunRecord(outcome=abort, abort_reason=iteration_limit_20)
    end
```

## References

[1] S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan, and Y. Cao, "ReAct: Synergizing Reasoning and Acting in Language Models," in *Proc. 11th Int. Conf. Learning Representations (ICLR)*, 2023. Available: https://arxiv.org/abs/2210.03629
