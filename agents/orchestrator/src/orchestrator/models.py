"""Typed contracts for the Orchestrator: webhook input, run record, circuit breaker."""

from typing import Any, Literal

from common.toolset_guards import CircuitBreakerTripped
from pydantic import BaseModel, Field

__all__ = ["CircuitBreakerTripped", "FaultEvent", "RunRecord"]


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
    outcome: Literal[
        "success",
        "rollback_succeeded",
        "rollback_failed",
        "gate_failed",
        "budget_exhausted",
        "abort",
        "quota_exhausted",
        "baseline_degraded",
        "escalated",
        "awaiting_human_review",
        "inject_did_not_break",
        "commit_generation_failed",
    ]
    success_rate: bool | None
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
    attempts: int = 1
    model_version: str | None = None
    setup_error: str | None = None
    agent_branch: str | None = None
    agent_commits: list[str] | None = None
    gate_status: str | None = None
    forbidden_action_violations: list[str] | None = Field(default_factory=list)
