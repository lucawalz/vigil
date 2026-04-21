"""Orchestrator: central control flow for a single fault-to-remediation run.

Flow:
  1. Ingest FaultEvent.
  2. Run Diagnosis agent -> DiagnosisReport.
  3. Capture baseline HealthSnapshot.
  4. Launch Remediation + Watchdog in parallel via asyncio.TaskGroup.
  5. If Watchdog reports degradation, issue rollback via kubectl-mcp rollout_undo.
  6. Write RunRecord to eval/runs/{run_id}.json + append to runs_index.jsonl.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timezone

log = logging.getLogger("vigil.orchestrator.agent")

from diagnosis.agent import run_diagnosis
from diagnosis.models import DiagnosisDeps
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.usage import Usage
from remediation.agent import run_remediation
from remediation.models import RemediationDeps
from watchdog.agent import capture_health_snapshot, run_watchdog
from watchdog.models import WatchdogDeps

from .models import CircuitBreakerTripped, FaultEvent, RunRecord


class _CircuitBreaker:
    """Counts consecutive MCP tool errors; trips at 3."""

    def __init__(self) -> None:
        self._consecutive = 0

    def success(self) -> None:
        self._consecutive = 0

    def error(self) -> None:
        self._consecutive += 1
        if self._consecutive >= 3:
            raise CircuitBreakerTripped("3 consecutive MCP errors")

    @property
    def consecutive(self) -> int:
        return self._consecutive


def build_run_id(
    scenario: str,
    model: str,
    seed: int | None = None,
) -> tuple[str, str, str]:
    """Return (run_id, seed_str, sha7).

    When `seed` is provided, it is stringified and used verbatim in the run_id
    ({scenario}_{seed}_{model}_{sha7}). When `seed` is None, the legacy
    UTC-timestamp fallback preserves backward compatibility for pre-Phase-7
    callers that do not supply a seed (e.g., raw Alertmanager webhooks).
    """
    if seed is not None:
        seed_str = str(seed)
    else:
        seed_str = f"seed-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    try:
        sha7 = subprocess.check_output(
            ["git", "rev-parse", "--short=7", "HEAD"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sha7 = "0000000"
    run_id = f"{scenario}_{seed_str}_{model}_{sha7}"
    return run_id, seed_str, sha7


def _write_run_record(record: RunRecord) -> None:
    """Write {runs_dir}/{run_id}.json + append one line to runs_index.jsonl."""
    runs_dir = os.environ.get("EVAL_RUNS_DIR", "eval/runs")
    os.makedirs(runs_dir, exist_ok=True)
    path = os.path.join(runs_dir, f"{record.run_id}.json")
    with open(path, "w") as f:
        f.write(record.model_dump_json(indent=2))
    index_path = os.path.join(os.path.dirname(runs_dir) or ".", "runs_index.jsonl")
    with open(index_path, "a") as f:
        f.write(record.model_dump_json() + "\n")


async def _issue_rollback(
    kubectl_mcp: MCPServerStdio, affected_resources: list[str]
) -> bool:
    """Issue rollout_undo for each affected resource. Return True if all succeed."""
    all_ok = True
    for resource in affected_resources:
        try:
            await kubectl_mcp.call_tool(
                "rollout_undo", arguments={"resource": resource}
            )
        except Exception:
            all_ok = False
    return all_ok


async def run_orchestration(
    event: FaultEvent,
    kubectl_mcp: MCPServerStdio,
    flux_mcp: MCPServerStdio,
    ssh_mcp: MCPServerStdio,
    nixos_mcp: MCPServerStdio,
    *,
    scenario: str = "k8s-1",
    seed: int | None = None,
) -> RunRecord:
    """Drive one full diagnosis -> remediation -> verification cycle."""
    model_name = os.environ.get("LLM_MODEL_NAME", "unknown")
    run_id, seed_str, sha7 = build_run_id(scenario, model_name, seed=seed)
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    t0 = asyncio.get_event_loop().time()
    breaker = _CircuitBreaker()

    diagnosis_deps = DiagnosisDeps(
        kubectl_mcp=kubectl_mcp, nixos_mcp=nixos_mcp
    )
    remediation_deps = RemediationDeps(
        kubectl_mcp=kubectl_mcp, flux_mcp=flux_mcp, nixos_mcp=nixos_mcp
    )
    watchdog_deps = WatchdogDeps(kubectl_mcp=kubectl_mcp)

    destructive_repair = False
    rollback_triggered = False
    rollback_success: bool | None = None
    total_tool_calls = 0
    iteration_count = 0

    def _abort_record(_reason: str) -> RunRecord:
        ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return RunRecord(
            run_id=run_id,
            scenario=scenario,
            seed=seed_str,
            model=model_name,
            git_sha7=sha7,
            started_at=started_at,
            ended_at=ended_at,
            outcome="abort",
            success_rate=False,
            diagnosis_accuracy=None,
            MTTR_s=None,
            destructive_repair=destructive_repair,
            rollback_triggered=rollback_triggered,
            rollback_success=rollback_success,
            total_input_tokens=0,
            total_output_tokens=0,
            total_tool_calls=total_tool_calls,
            iteration_count=iteration_count,
            autonomy_level="full",
        )

    total_usage = Usage()

    try:
        report, diag_usage = await run_diagnosis(diagnosis_deps, event)
        total_usage = total_usage + diag_usage
        breaker.success()
        iteration_count += 1

        baseline = await capture_health_snapshot(watchdog_deps)

        async with asyncio.TaskGroup() as tg:
            rem_task = tg.create_task(run_remediation(remediation_deps, report))
            wtch_task = tg.create_task(run_watchdog(watchdog_deps, baseline))
        remediation_result, rem_usage = rem_task.result()
        watchdog_result = wtch_task.result()
        total_usage = total_usage + rem_usage

        destructive_repair = remediation_result.destructive_repair
        total_tool_calls = remediation_result.tool_calls_count
        iteration_count += remediation_result.tool_calls_count

        if watchdog_result.degraded:
            rollback_triggered = True
            rollback_success = await _issue_rollback(
                kubectl_mcp, report.affected_resources
            )

        mttr_s = asyncio.get_event_loop().time() - t0
        ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        record = RunRecord(
            run_id=run_id,
            scenario=scenario,
            seed=seed_str,
            model=model_name,
            git_sha7=sha7,
            started_at=started_at,
            ended_at=ended_at,
            outcome="success",
            success_rate=remediation_result.success and not watchdog_result.degraded,
            diagnosis_accuracy=None,
            MTTR_s=mttr_s,
            destructive_repair=destructive_repair,
            rollback_triggered=rollback_triggered,
            rollback_success=rollback_success,
            total_input_tokens=total_usage.input_tokens or 0,
            total_output_tokens=total_usage.output_tokens or 0,
            total_tool_calls=total_tool_calls,
            iteration_count=iteration_count,
            autonomy_level="full",
        )
        _write_run_record(record)
        return record

    except UsageLimitExceeded:
        log.exception("run %s aborted: iteration_limit_20", run_id)
        record = _abort_record("iteration_limit_20")
        _write_run_record(record)
        return record
    except CircuitBreakerTripped:
        log.exception("run %s aborted: circuit_breaker", run_id)
        record = _abort_record("circuit_breaker_3_consecutive_errors")
        _write_run_record(record)
        return record
    except UnexpectedModelBehavior as e:
        log.exception("run %s aborted: model_error: %s", run_id, e)
        record = _abort_record(f"model_error: {e}")
        _write_run_record(record)
        return record
    except Exception:
        log.exception("run %s aborted: unhandled exception", run_id)
        record = _abort_record("unhandled_exception")
        _write_run_record(record)
        return record
