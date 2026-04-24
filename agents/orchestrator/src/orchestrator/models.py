"""Typed contracts for the Orchestrator: webhook input, run record, circuit breaker."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_ai.mcp import MCPServerStdio


class FaultEvent(BaseModel):
    """Alertmanager v2 webhook payload (see Alertmanager docs /api/v2/alerts)."""

    receiver: str
    status: str  # "firing" | "resolved"
    alerts: list[dict[str, Any]]
    groupLabels: dict[str, str]
    commonLabels: dict[str, str]
    commonAnnotations: dict[str, str]
    externalURL: str
    version: str
    groupKey: str
    truncatedAlerts: int = 0


class RunRecord(BaseModel):
    """Metric set written to eval/runs/{run_id}.json after every Orchestrator run."""

    run_id: str
    scenario: str
    seed: str
    model: str
    git_sha7: str
    started_at: str
    ended_at: str
    outcome: Literal["success", "abort"]
    success_rate: bool
    diagnosis_accuracy: bool | None
    MTTR_s: float | None
    destructive_repair: bool
    rollback_triggered: bool
    rollback_success: bool | None
    total_input_tokens: int
    total_output_tokens: int
    total_tool_calls: int
    iteration_count: int
    autonomy_level: Literal["full", "supervised"]
    actions_taken: list[str]
    model_version: str | None = None


class CircuitBreakerTripped(Exception):
    """Raised by the Orchestrator when 3 consecutive MCP tool errors accumulate."""


@dataclass(frozen=True)
class OrchestratorDeps:
    """MCP client references for the Orchestrator. Frozen; no shared mutable state."""

    kubectl_mcp: MCPServerStdio
    flux_mcp: MCPServerStdio
    ssh_mcp: MCPServerStdio
    nixos_mcp: MCPServerStdio
