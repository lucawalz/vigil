from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from common import trace
from common.constants import GIT_COMMIT_BUDGET
from common.provider import build_model
from diagnosis.agent import run_diagnosis
from diagnosis.context import (
    ManifestPathUnresolvable,
    ResourceKindUnresolvable,
    build_diagnosis_context,
)
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

_TRANSIENT_FLUX_REASONS: frozenset[str] = frozenset(
    {"DependencyNotReady", "Progressing", "HealthCheckFailed"}
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


def _extract_tool_names(msgs: list[ModelMessage]) -> list[str]:
    from pydantic_ai.messages import ToolCallPart

    names: list[str] = []
    for msg in msgs:
        for part in getattr(msg, "parts", []):
            if isinstance(part, ToolCallPart):
                names.append(part.tool_name)
    return names


def build_run_id(
    scenario: str,
    model: str,
    seed: int | None = None,
) -> tuple[str, str, str]:
    """Return (run_id, seed_str, sha7).

    When `seed` is None — as for raw Alertmanager webhooks routed through
    `/webhook` without a `?seed=` query parameter — fall back to a UTC
    timestamp so the run_id remains unique across concurrent webhook deliveries.
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


def _load_scenario_data(scenario: str) -> dict:
    import yaml

    scenarios_dir = Path(os.environ.get("VIGIL_SCENARIOS_DIR", "eval/scenarios"))
    scenario_yaml = scenarios_dir / scenario / "scenario.yaml"
    if not scenario_yaml.exists():
        return {}
    with scenario_yaml.open() as f:
        return yaml.safe_load(f) or {}


def _score_diagnosis_accuracy(scenario: str, report) -> bool | None:
    data = _load_scenario_data(scenario)
    if not data:
        return None
    expected = data.get("expected_action")
    if expected is None:
        return None
    return report.recommended_action == expected


_TOOL_TO_ACTION_CLASSES: dict[str, list[str]] = {
    "commit_files": ["git_commit_k8s", "git_commit_nix"],
    "create_pr": ["git_commit_k8s", "git_commit_nix"],
    "write_manifest": ["git_commit_k8s", "git_commit_nix"],
    # self-mapped so raw tool names in forbidden_actions still trigger a violation
    "switch_generation": ["nixos_rebuild", "switch_generation"],
    "trigger_reconcile": ["nixos_rebuild"],
    "reconcile_kustomization": ["flux_reconcile"],
}


def _check_forbidden_actions(scenario: str, actions_taken: list[str]) -> list[str]:
    data = _load_scenario_data(scenario)
    forbidden = set(data.get("forbidden_actions", []))
    violations: list[str] = []
    for tool in actions_taken:
        for action_class in _TOOL_TO_ACTION_CLASSES.get(tool, []):
            if action_class in forbidden and tool not in violations:
                violations.append(tool)
    return violations


def _write_run_record(record: RunRecord) -> None:
    runs_dir = Path(os.environ.get("EVAL_RUNS_DIR", "eval/runs"))
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / f"{record.run_id}.json").write_text(record.model_dump_json(indent=2))
    index_path = runs_dir.parent / "runs_index.jsonl"
    with index_path.open("a") as f:
        f.write(record.model_dump_json() + "\n")


def _parse_kust_text(text: str) -> dict:
    m = re.search(r"^\s*Ready:\s*([A-Za-z]+)(?:\s*[—-]\s*(.*))?$", text, re.MULTILINE)
    if m:
        return {
            "ready": m.group(1),
            "reason": (m.group(2) or "").strip(),
            "message": "",
        }
    return {"ready": "Unknown", "reason": "parse_error", "message": text[:200]}


def _extract_mcp_text(result: object) -> str:
    if isinstance(result, dict) and "content" in result:
        return str(result["content"])
    return str(result)


async def _fetch_flux_snapshot(flux_mcp: MCPServerStdio) -> dict:
    kust_result = await flux_mcp.direct_call_tool(
        "get_kustomization_status", {"namespace": "flux-system", "name": "cluster-apps"}
    )
    infra_result = await flux_mcp.direct_call_tool(
        "get_kustomization_status",
        {"namespace": "flux-system", "name": "cluster-infrastructure"},
    )
    return {
        "cluster_apps": _parse_kust_text(_extract_mcp_text(kust_result)),
        "cluster_infra": _parse_kust_text(_extract_mcp_text(infra_result)),
    }


async def _issue_rollback(
    recommended_action: str,
    git_mcp: MCPServerStdio,
    flux_mcp: MCPServerStdio,
    nixos_mcp: MCPServerStdio,
    merge_commit_sha: str | None,
    target_host: str | None,
) -> bool:
    """Dispatch rollback by recommended_action class. Returns True on full success."""
    try:
        if recommended_action == "flux_reconcile":
            await flux_mcp.direct_call_tool(
                "reconcile_kustomization",
                {"namespace": "flux-system", "name": "cluster-apps"},
            )
        elif recommended_action == "git_commit_k8s":
            await git_mcp.direct_call_tool(
                "revert_commit",
                {"merge_commit_sha": merge_commit_sha},
            )
            await flux_mcp.direct_call_tool(
                "reconcile_kustomization",
                {"namespace": "flux-system", "name": "cluster-apps"},
            )
        elif recommended_action == "nixos_rebuild":
            await nixos_mcp.direct_call_tool(
                "switch_generation",
                {"host": target_host},
            )
        elif recommended_action == "git_commit_nix":
            await git_mcp.direct_call_tool(
                "revert_commit",
                {"merge_commit_sha": merge_commit_sha},
            )
            await nixos_mcp.direct_call_tool(
                "trigger_reconcile",
                {"host": target_host},
            )
        else:
            return False
        return True
    except Exception:
        log.exception("rollback failed for action=%s", recommended_action)
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

    diagnosis_deps = DiagnosisDeps(
        kubectl_mcp=kubectl_mcp, nixos_mcp=nixos_mcp, git_mcp=git_mcp, run_id=run_id
    )
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
            setup_error=_reason if _outcome != "abort" else None,
        )

    total_usage = Usage()

    log.info("run %s started (scenario=%s model=%s)", run_id, scenario, model_name)

    try:
        async with asyncio.timeout(ORCHESTRATOR_RUN_TIMEOUT_S):
            try:
                diagnosis_context = await build_diagnosis_context(diagnosis_deps, event)
            except (ManifestPathUnresolvable, ResourceKindUnresolvable) as exc:
                log.warning("run %s: manifest path unresolvable: %s", run_id, exc)
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
                    outcome="escalated",
                    success_rate=False,
                    diagnosis_accuracy=None,
                    MTTR_s=mttr_s,
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
                    setup_error=str(exc),
                )
                _write_run_record(record)
                return record

            try:
                async with asyncio.timeout(DIAGNOSIS_TIMEOUT_S):
                    report, diag_usage, diag_msgs = await run_diagnosis(
                        diagnosis_deps, event, diagnosis_context, model=model
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

            if report.recommended_action == "escalate":
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
                    outcome="escalated",
                    success_rate=None,
                    diagnosis_accuracy=_score_diagnosis_accuracy(scenario, report),
                    MTTR_s=mttr_s,
                    destructive_repair=False,
                    rollback_triggered=False,
                    rollback_success=None,
                    total_input_tokens=total_usage.input_tokens or 0,
                    total_output_tokens=total_usage.output_tokens or 0,
                    total_tool_calls=_count_tool_calls(diag_msgs),
                    iteration_count=iteration_count,
                    autonomy_level="full",
                    actions_taken=[],
                    model_version=model_name,
                )
                log.info("run %s finished outcome=escalated", run_id)
                _write_run_record(record)
                return record

            if report.recommended_action == "git_commit_k8s":
                try:
                    current = await _fetch_flux_snapshot(flux_mcp)
                    baseline = event.flux_baseline
                    if baseline is not None:
                        was_ready = (
                            baseline.get("cluster_apps", {}).get("ready") == "True"
                        )
                        now_ready = (
                            current.get("cluster_apps", {}).get("ready") == "True"
                        )
                        if was_ready and not now_ready:
                            reason = current["cluster_apps"].get("reason", "")
                            if reason in _TRANSIENT_FLUX_REASONS:
                                log.info(
                                    "run %s: cluster-apps Not-Ready reason=%s "
                                    "(transient cascade, proceeding)",
                                    run_id,
                                    reason,
                                )
                            else:
                                log.error(
                                    "run %s aborted: flux degraded since injection "
                                    "(cluster-apps reason=%s)",
                                    run_id,
                                    reason,
                                )
                                record = _abort_record(
                                    "flux_degraded_since_injection", "flux_degraded"
                                )
                                _write_run_record(record)
                                return record
                        if not was_ready:
                            log.info(
                                "run %s: cluster-apps was already Not-Ready before "
                                "injection (reason=%s) — proceeding with diagnosis",
                                run_id,
                                baseline["cluster_apps"].get("reason"),
                            )
                    else:
                        if current.get("cluster_apps", {}).get("ready") == "False":
                            reason = current.get("cluster_apps", {}).get("reason", "")
                            if reason not in _TRANSIENT_FLUX_REASONS:
                                log.error(
                                    "run %s aborted: flux_degraded "
                                    "(no baseline; snapshot-only check)",
                                    run_id,
                                )
                                record = _abort_record(
                                    "flux_degraded_snapshot_fallback", "flux_degraded"
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

            base_branch = diagnosis_context.source_branch or "main"
            try:
                await git_mcp.direct_call_tool(
                    "create_branch",
                    {"run_id": run_id, "base_branch": base_branch},
                )
            except Exception:
                log.debug("run %s: base_branch pre-call skipped (non-fatal)", run_id)

            if report.recommended_action == "git_commit_k8s":
                try:
                    async with asyncio.timeout(REMEDIATION_TIMEOUT_S):
                        remediation_result, rem_usage, rem_msgs = await run_remediation(
                            remediation_deps,
                            report,
                            source_branch=base_branch,
                            model=model,
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
                                        remediation_deps,
                                        report,
                                        source_branch=base_branch,
                                        model=model,
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
            total_tool_calls = _count_tool_calls(diag_msgs) + _count_tool_calls(
                rem_msgs
            )
            iteration_count += _count_tool_calls(rem_msgs)
            actions_taken = _extract_tool_names(rem_msgs)

            outcome: str
            if (
                report.recommended_action == "git_commit_k8s"
                and remediation_result.gate_status == "closed"
            ):
                outcome = "gate_failed"
                rollback_triggered = False
                rollback_success = None
            elif (
                report.recommended_action == "git_commit_k8s"
                and remediation_result.merge_commit_sha is None
                and remediation_result.agent_commits
                and len(remediation_result.agent_commits) > GIT_COMMIT_BUDGET
            ):
                outcome = "budget_exhausted"
                rollback_triggered = False
                rollback_success = None
            elif watchdog_result.degraded:
                rollback_triggered = True
                rollback_success = await _issue_rollback(
                    report.recommended_action,
                    git_mcp,
                    flux_mcp,
                    nixos_mcp,
                    remediation_result.merge_commit_sha,
                    report.target_host,
                )
                outcome = (
                    "rollback_succeeded" if rollback_success else "rollback_failed"
                )
            else:
                outcome = "success"
                rollback_triggered = False
                rollback_success = None

            mttr_s = asyncio.get_event_loop().time() - t0
            ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            forbidden_violations = _check_forbidden_actions(scenario, actions_taken)
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
                    remediation_result.success
                    and not watchdog_result.degraded
                    and not forbidden_violations
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
                actions_taken=actions_taken,
                model_version=model_name,
                agent_branch=remediation_result.agent_branch,
                agent_commits=remediation_result.agent_commits,
                gate_status=remediation_result.gate_status,
                forbidden_action_violations=forbidden_violations,
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
