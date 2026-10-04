"""Typed contracts for the Orchestrator: webhook input, run record, circuit breaker."""

import os
from typing import Any, Literal, cast, get_args

from common.toolset_guards import CircuitBreakerTripped
from pydantic import BaseModel, Field

__all__ = [
    "CircuitBreakerTripped",
    "DEFAULT_EVAL_TARGET",
    "EVAL_TARGETS",
    "EvalTarget",
    "FaultEvent",
    "RunRecord",
    "eval_target_from_env",
]

EvalTarget = Literal["hetzner", "runner", "lab"]
EVAL_TARGETS: tuple[str, ...] = get_args(EvalTarget)
DEFAULT_EVAL_TARGET: EvalTarget = "hetzner"


def eval_target_from_env() -> EvalTarget:
    value = os.environ.get("VIGIL_EVAL_TARGET", DEFAULT_EVAL_TARGET)
    if value not in EVAL_TARGETS:
        raise ValueError(
            f"VIGIL_EVAL_TARGET must be one of {', '.join(EVAL_TARGETS)}, got {value!r}"
        )
    return cast(EvalTarget, value)


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
        "flux_degraded",
        "abort",
        "quota_exhausted",
        "baseline_degraded",
        "escalated",
        "awaiting_human_review",
        "inject_did_not_break",
        "commit_generation_failed",
    ]
    success_rate: bool | None
    remediation_success: bool | None = None
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
    merge_commit_sha: str | None = None
    forbidden_action_violations: list[str] | None = Field(default_factory=list)
    target: EvalTarget = DEFAULT_EVAL_TARGET
