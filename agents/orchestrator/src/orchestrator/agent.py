from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from common import trace
from common.constants import GIT_COMMIT_BUDGET
from common.provider import build_model
from diagnosis.agent import run_diagnosis
from diagnosis.models import DiagnosisDeps
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import Usage
from remediation.agent import run_remediation
from remediation.models import RemediationDeps
from watchdog.agent import capture_health_snapshot, run_watchdog
from watchdog.models import WatchdogDeps

from .models import CircuitBreakerTripped, FaultEvent, RunRecord

log = logging.getLogger("vigil.orchestrator.agent")

ORCHESTRATOR_RUN_TIMEOUT_S: float = float(
    os.environ.get("ORCHESTRATOR_RUN_TIMEOUT_S", "750")
)
DIAGNOSIS_TIMEOUT_S: float = float(os.environ.get("DIAGNOSIS_TIMEOUT_S", "300"))
REMEDIATION_TIMEOUT_S: float = float(os.environ.get("REMEDIATION_TIMEOUT_S", "600"))
WATCHDOG_RECONCILE_GRACE_S: float = float(
    os.environ.get("WATCHDOG_RECONCILE_GRACE_S", "90")
)


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


def _count_tool_calls(msgs: list[ModelMessage]) -> int:
    return sum(
        1
        for m in msgs
        for p in getattr(m, "parts", [])
        if getattr(p, "part_kind", None) == "tool-call"
    )


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
    sha7 = os.environ.get("GIT_SHA7", "").strip()
    if not sha7:
        try:
            sha7 = subprocess.check_output(
                ["git", "rev-parse", "--short=7", "HEAD"], text=True
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            sha7 = "0000000"
    safe_model = model.replace(":", "-").replace("/", "-")
    run_id = f"{scenario}_{seed_str}_{safe_model}_{sha7}"
    return run_id, seed_str, sha7


_OS_LAYERS = frozenset({"os", "cross"})
_OS_REPAIR_ACTIONS = frozenset({"rebuild_nixos"})
_K8S_REPAIR_ACTIONS = frozenset({"git_commit"})


def _score_diagnosis_accuracy(scenario: str, report) -> bool | None:
    # yaml.safe_load — no arbitrary code execution from scenario files.
    import yaml

    scenarios_dir = Path(os.environ.get("VIGIL_SCENARIOS_DIR", "eval/scenarios"))
    scenario_yaml = scenarios_dir / scenario / "scenario.yaml"
    if not scenario_yaml.exists():
        return None
    with scenario_yaml.open() as f:
        data = yaml.safe_load(f) or {}
    expected_layer = data.get("root_cause_layer")
    if expected_layer is None:
        return None
    expected_os = expected_layer in _OS_LAYERS
    layer_correct = report.requires_os_level == expected_os
    if data.get("layer") == "boundary" and report.requires_os_level:
        return False
    return layer_correct


def _write_run_record(record: RunRecord) -> None:
    runs_dir = Path(os.environ.get("EVAL_RUNS_DIR", "eval/runs"))
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / f"{record.run_id}.json").write_text(record.model_dump_json(indent=2))
    index_path = runs_dir.parent / "runs_index.jsonl"
    with index_path.open("a") as f:
        f.write(record.model_dump_json() + "\n")


async def _issue_rollback(
    git_mcp: MCPServerStdio,
    flux_mcp: MCPServerStdio,
    merge_commit_sha: str,
) -> bool:
    """Revert the merged PR and force Flux reconcile. Returns True on full success."""
    try:
        await git_mcp.direct_call_tool(
            "revert_commit",
            {"merge_commit_sha": merge_commit_sha},
        )
        await flux_mcp.direct_call_tool(
            "reconcile_kustomization",
            {"namespace": "flux-system", "name": "cluster-apps"},
        )
        return True
    except Exception:
        log.exception("rollback failed for merge_commit_sha=%s", merge_commit_sha)
        return False


async def run_orchestration(
    event: FaultEvent,
    kubectl_mcp: MCPServerStdio,
    flux_mcp: MCPServerStdio,
    ssh_mcp: MCPServerStdio,
    nixos_mcp: MCPServerStdio,
    git_mcp: MCPServerStdio,
    *,
    scenario: str = "k8s-1",
    seed: int | None = None,
    model_name: str | None = None,
) -> RunRecord:
    """Drive one full diagnosis -> remediation -> verification cycle."""
    model_name = model_name or os.environ.get("LLM_MODEL_NAME", "unknown")
    run_id, seed_str, sha7 = build_run_id(scenario, model_name, seed=seed)
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    t0 = asyncio.get_event_loop().time()
    breaker = _CircuitBreaker()
    model = build_model(model_name)

    diagnosis_deps = DiagnosisDeps(kubectl_mcp=kubectl_mcp, nixos_mcp=nixos_mcp)
    remediation_deps = RemediationDeps(
        git_mcp=git_mcp, flux_mcp=flux_mcp, nixos_mcp=nixos_mcp
    )
    watchdog_deps = WatchdogDeps(kubectl_mcp=kubectl_mcp)

    destructive_repair = False
    rollback_triggered = False
    rollback_success: bool | None = None
    total_tool_calls = 0
    iteration_count = 0

    def _abort_record(_reason: str, _outcome: str = "abort") -> RunRecord:
        ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return RunRecord(
            run_id=run_id,
            scenario=scenario,
            seed=seed_str,
            model=model_name,
            git_sha7=sha7,
            started_at=started_at,
            ended_at=ended_at,
            outcome=_outcome,
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
            actions_taken=[],
            model_version=model_name,
        )

    total_usage = Usage()

    log.info("run %s started (scenario=%s model=%s)", run_id, scenario, model_name)

    try:
        async with asyncio.timeout(ORCHESTRATOR_RUN_TIMEOUT_S):
            try:
                async with asyncio.timeout(DIAGNOSIS_TIMEOUT_S):
                    report, diag_usage, diag_msgs = await run_diagnosis(
                        diagnosis_deps, event, model=model
                    )
            except asyncio.TimeoutError:
                log.error(
                    "run %s aborted: diagnosis_timeout (%.0fs)",
                    run_id,
                    DIAGNOSIS_TIMEOUT_S,
                )
                record = _abort_record("diagnosis_timeout")
                _write_run_record(record)
                return record

            total_usage = total_usage + diag_usage

            # Ollama Cloud returns 0 output tokens when per-window quota is exhausted.
            if (total_usage.output_tokens or 0) == 0 and (
                total_usage.input_tokens or 0
            ) == 0:
                log.error(
                    "run %s: zero-token response (msg_count=%d) — quota exhausted",
                    run_id,
                    len(diag_msgs),
                )
                ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                record = RunRecord(
                    run_id=run_id,
                    scenario=scenario,
                    seed=seed_str,
                    model=model_name,
                    git_sha7=sha7,
                    started_at=started_at,
                    ended_at=ended_at,
                    outcome="quota_exhausted",
                    success_rate=False,
                    diagnosis_accuracy=None,
                    MTTR_s=None,
                    destructive_repair=False,
                    rollback_triggered=False,
                    rollback_success=None,
                    total_input_tokens=0,
                    total_output_tokens=0,
                    total_tool_calls=0,
                    iteration_count=0,
                    autonomy_level="full",
                    actions_taken=[],
                    model_version=model_name,
                )
                _write_run_record(record)
                return record

            trace.log_messages(run_id, "diagnosis", diag_msgs)
            trace.write_trace(run_id, "diagnosis", diag_msgs)
            breaker.success()
            iteration_count += 1

            action_is_os = report.recommended_action in _OS_REPAIR_ACTIONS
            action_is_k8s = report.recommended_action in _K8S_REPAIR_ACTIONS
            layer_os = report.requires_os_level
            if (layer_os and action_is_k8s) or (not layer_os and action_is_os):
                log.error(
                    "run %s aborted: diagnosis_inconsistent "
                    "(requires_os_level=%s recommended_action=%s)",
                    run_id,
                    report.requires_os_level,
                    report.recommended_action,
                )
                ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                record = RunRecord(
                    run_id=run_id,
                    scenario=scenario,
                    seed=seed_str,
                    model=model_name,
                    git_sha7=sha7,
                    started_at=started_at,
                    ended_at=ended_at,
                    outcome="abort",
                    success_rate=False,
                    diagnosis_accuracy=_score_diagnosis_accuracy(scenario, report),
                    MTTR_s=None,
                    destructive_repair=False,
                    rollback_triggered=False,
                    rollback_success=None,
                    total_input_tokens=total_usage.input_tokens or 0,
                    total_output_tokens=total_usage.output_tokens or 0,
                    total_tool_calls=total_tool_calls,
                    iteration_count=iteration_count,
                    autonomy_level="full",
                    actions_taken=[],
                    model_version=model_name,
                    setup_error="diagnosis_inconsistent",
                )
                _write_run_record(record)
                return record

            if action_is_k8s:
                try:
                    kust_status = await flux_mcp.direct_call_tool(
                        "get_kustomization_status",
                        {"namespace": "flux-system", "name": "cluster-apps"},
                    )
                    kust_text = str(kust_status)
                    if (
                        "Ready: False" in kust_text
                        or "Stalled: True" in kust_text
                        or "Suspended: true" in kust_text
                    ):
                        log.error(
                            "run %s aborted: flux_degraded (cluster-apps unhealthy): %s",
                            run_id,
                            kust_text,
                        )
                        record = _abort_record(
                            "flux_degraded_kustomization", "flux_degraded"
                        )
                        _write_run_record(record)
                        return record

                    repo_status = await flux_mcp.direct_call_tool(
                        "get_gitrepository_status",
                        {"namespace": "flux-system", "name": "flux-system"},
                    )
                    if "Ready: False" in str(repo_status):
                        log.error(
                            "run %s aborted: flux_degraded (gitrepository unhealthy)",
                            run_id,
                        )
                        record = _abort_record(
                            "flux_degraded_gitrepository", "flux_degraded"
                        )
                        _write_run_record(record)
                        return record
                except Exception:
                    log.exception(
                        "run %s: flux pre-check failed; emitting flux_degraded", run_id
                    )
                    record = _abort_record("flux_precheck_exception", "flux_degraded")
                    _write_run_record(record)
                    return record

            baseline = await capture_health_snapshot(watchdog_deps)

            if action_is_k8s:
                try:
                    async with asyncio.timeout(REMEDIATION_TIMEOUT_S):
                        remediation_result, rem_usage, rem_msgs = await run_remediation(
                            remediation_deps, report, model=model
                        )
                except asyncio.TimeoutError:
                    log.error(
                        "run %s aborted: remediation_timeout (%.0fs)",
                        run_id,
                        REMEDIATION_TIMEOUT_S,
                    )
                    record = _abort_record("remediation_timeout")
                    _write_run_record(record)
                    return record

                await asyncio.sleep(WATCHDOG_RECONCILE_GRACE_S)
                watchdog_result = await run_watchdog(watchdog_deps, baseline)

            else:
                try:
                    async with asyncio.timeout(REMEDIATION_TIMEOUT_S):
                        try:
                            async with asyncio.TaskGroup() as tg:
                                rem_task = tg.create_task(
                                    run_remediation(
                                        remediation_deps, report, model=model
                                    )
                                )
                                wtch_task = tg.create_task(
                                    run_watchdog(watchdog_deps, baseline)
                                )
                        except* (
                            UsageLimitExceeded,
                            UnexpectedModelBehavior,
                            CircuitBreakerTripped,
                        ) as eg:
                            raise eg.exceptions[0]
                except asyncio.TimeoutError:
                    log.error(
                        "run %s aborted: remediation_timeout (%.0fs)",
                        run_id,
                        REMEDIATION_TIMEOUT_S,
                    )
                    record = _abort_record("remediation_timeout")
                    _write_run_record(record)
                    return record

                remediation_result, rem_usage, rem_msgs = rem_task.result()
                watchdog_result = wtch_task.result()

            total_usage = total_usage + rem_usage
            trace.log_messages(run_id, "remediation", rem_msgs)
            trace.write_trace(run_id, "remediation", rem_msgs)

            destructive_repair = remediation_result.destructive_repair
            total_tool_calls = _count_tool_calls(diag_msgs) + _count_tool_calls(rem_msgs)
            iteration_count += _count_tool_calls(rem_msgs)

            outcome: str
            if action_is_k8s and remediation_result.gate_status == "closed":
                outcome = "gate_failed"
                rollback_triggered = False
                rollback_success = None
            elif (
                action_is_k8s
                and remediation_result.merge_commit_sha is None
                and remediation_result.agent_commits
                and len(remediation_result.agent_commits) > GIT_COMMIT_BUDGET
            ):
                outcome = "budget_exhausted"
                rollback_triggered = False
                rollback_success = None
            elif watchdog_result.degraded:
                rollback_triggered = True
                if action_is_k8s and remediation_result.merge_commit_sha:
                    rollback_success = await _issue_rollback(
                        git_mcp, flux_mcp, remediation_result.merge_commit_sha
                    )
                    outcome = "rollback_succeeded" if rollback_success else "rollback_failed"
                else:
                    rollback_success = False
                    outcome = "rollback_failed"
            else:
                outcome = "success"
                rollback_triggered = False
                rollback_success = None

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
                outcome=outcome,
                success_rate=(
                    remediation_result.success and not watchdog_result.degraded
                ),
                diagnosis_accuracy=_score_diagnosis_accuracy(scenario, report),
                MTTR_s=mttr_s,
                destructive_repair=destructive_repair,
                rollback_triggered=rollback_triggered,
                rollback_success=rollback_success,
                total_input_tokens=total_usage.input_tokens or 0,
                total_output_tokens=total_usage.output_tokens or 0,
                total_tool_calls=total_tool_calls,
                iteration_count=iteration_count,
                autonomy_level="full",
                actions_taken=remediation_result.actions_taken,
                model_version=model_name,
            )
            log.info("run %s finished outcome=%s MTTR=%.1fs", run_id, outcome, mttr_s)
            _write_run_record(record)
            return record

    except asyncio.TimeoutError:
        log.error(
            "run %s aborted: run_timeout (%.0fs)", run_id, ORCHESTRATOR_RUN_TIMEOUT_S
        )
        record = _abort_record("run_timeout")
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
