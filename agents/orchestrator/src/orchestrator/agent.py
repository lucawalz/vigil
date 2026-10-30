from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import subprocess
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import trace
from common.constants import (
    CIRCUIT_BREAKER_THRESHOLD,
    CONFIDENCE_AUTO_THRESHOLD,
    CONFIDENCE_REVIEW_THRESHOLD,
    GATE_REVERT_CALL_TIMEOUT_S,
    GIT_COMMIT_BUDGET,
    GIT_MCP_READ_TIMEOUT_S,
    MCP_CALL_TIMEOUT_S,
    ROLLBACK_TIMEOUT_S,
    ROLLBACK_VERIFY_WINDOW_S,
    WATCHDOG_NAMESPACE,
)
from common.flux_status import coerce_flux_status
from common.mcp_call import call_tool
from common.provider import build_model
from common.toolset_guards import CircuitBreakerTripped
from diagnosis.agent import DIAGNOSIS_REQUEST_LIMIT, run_diagnosis
from diagnosis.context import (
    ManifestPathUnresolvable,
    ResourceKindUnresolvable,
    build_diagnosis_context,
    declared_sysctl_value,
    extract_alert_name,
    extract_alert_namespace,
    extract_systemd_unit,
    resolve_source_branch,
)
from diagnosis.models import (
    DiagnosisDeps,
    DiagnosisOutputRetryExhausted,
    DiagnosisReport,
    DiagnosisRequestBudgetExceeded,
)
from pydantic_ai.exceptions import (
    ModelRetry,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.messages import ModelMessage, ToolReturnPart
from pydantic_ai.usage import RunUsage
from remediation.agent import run_remediation
from remediation.models import (
    RemediationDeps,
    RemediationOutputRetryExhausted,
    RemediationResult,
)
from watchdog.agent import (
    OS_CHECK_NODE_CONDITION,
    OS_CHECK_SYSCTL,
    OS_CHECK_SYSTEMD,
    capture_health_snapshot,
    is_workload_healthy,
    probe_os_target,
    revision_matches,
    run_watchdog,
)
from watchdog.models import HealthSnapshotUnavailable, WatchdogDeps, WatchdogResult

from .models import FaultEvent, RunRecord, eval_target_from_env

log = logging.getLogger("vigil.orchestrator.agent")

ORCHESTRATOR_RUN_TIMEOUT_S: float = float(
    os.environ.get("ORCHESTRATOR_RUN_TIMEOUT_S", "1800")
)
DIAGNOSIS_TIMEOUT_S: float = float(os.environ.get("DIAGNOSIS_TIMEOUT_S", "300"))
REMEDIATION_TIMEOUT_S: float = float(os.environ.get("REMEDIATION_TIMEOUT_S", "540"))
_RUN_ID_SUFFIX_LEN = 8

_REMEDIATION_BRANCH_PREFIX = "remediation/run-"

_GIT_COMMIT_ACTIONS: frozenset[str] = frozenset({"git_commit_k8s", "git_commit_nix"})

_COMMIT_GENERATION_FAILED_OUTCOME = "commit_generation_failed"

_FLUX_APPS = {"namespace": "flux-system", "name": "cluster-apps"}

_ROLLBACK_VERIFY_POLL_S = 10

_GATE_MERGED = "merged"
_GATE_CLOSED = "closed"
_GATE_UNKNOWN = "unknown"
_GATE_AWAITING_REVIEW = "awaiting_review"

_PR_STATE_CLOSED = "closed"

_SHUTDOWN_REASON = "shutdown"

MAX_TRIES = 3
_PRIOR_TRY_MAX_CHARS = 400
_DIAGNOSIS_ITERATION = 1

_COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")
_MANIFEST_PATH_PATTERN = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
_KIND_PATTERN = re.compile(r"^[A-Za-z]{1,63}$")
_DNS1123_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$")
_HOST_PATTERN = re.compile(r"^[A-Za-z0-9.-]{1,253}$")
_PARENT_DIR = ".."
_NONE = "none"
_INVALID = "invalid"

_RUN_LOCK = asyncio.Lock()
_ACTIVE_RUNS: set[asyncio.Task[RunRecord]] = set()


def log_task_exception(task: asyncio.Task, logger: logging.Logger) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("background orchestration task failed: %s", exc, exc_info=exc)


def track_run(task: asyncio.Task[RunRecord]) -> None:
    """Hold a strong reference to a run task until it ends and log its failure."""
    _ACTIVE_RUNS.add(task)
    task.add_done_callback(_ACTIVE_RUNS.discard)
    task.add_done_callback(lambda t: log_task_exception(t, log))


def retry_run_id(incident_id: str, try_number: int) -> str:
    return f"{incident_id}-try-{try_number}"


@dataclass
class _RunState:
    """What one run has put live, read by the finaliser after the run deadline."""

    run_id: str
    t0: float
    action: str | None = None
    target: WatchdogDeps | None = None
    gate_status: str | None = None
    merge_sha: str | None = None
    open_pr: int | None = None
    verdict: WatchdogResult | None = None
    incident_id: str = ""
    seed_str: str = ""
    try_number: int = 1
    prior_tries: tuple[str, ...] = ()
    report: DiagnosisReport | None = None
    commit_shas: tuple[str, ...] = ()

    def end_gate(self, gate_status: str, sha: str | None) -> tuple[str, str | None]:
        self.gate_status = gate_status
        self.merge_sha = sha
        return gate_status, sha

    @property
    def needs_rollback(self) -> bool:
        return (
            self.action is not None
            and self.merge_sha is not None
            and (self.verdict is None or self.verdict.degraded)
        )


class _CircuitBreaker:
    """Counts consecutive failed MCP tool calls in a run; trips at the threshold.

    One instance is created per run_orchestration and shared across the diagnosis
    and remediation stages via CircuitBreakerToolset. error() is called on each
    failed MCP tool call and success() on each successful one; a single success
    resets the consecutive count. Reaching CIRCUIT_BREAKER_THRESHOLD consecutive
    failures raises CircuitBreakerTripped to abort the run.
    """

    def __init__(self) -> None:
        self._consecutive = 0

    def success(self) -> None:
        self._consecutive = 0

    def error(self) -> None:
        self._consecutive += 1
        if self._consecutive >= CIRCUIT_BREAKER_THRESHOLD:
            raise CircuitBreakerTripped(
                f"{CIRCUIT_BREAKER_THRESHOLD} consecutive MCP errors"
            )

    @property
    def consecutive(self) -> int:
        return self._consecutive


def _confidence_tier(report) -> str:
    """Map a DiagnosisReport onto a deterministic remediation tier.

    Returns 'auto' (high confidence: dispatch and merge automatically),
    'review' (medium confidence on a git-commit action: open a PR for a human
    to merge), or 'escalate' (low confidence, or medium confidence on a
    non-git action that has no PR to hold). The thresholds are structural and
    never decided by the model.
    """
    if report.confidence >= CONFIDENCE_AUTO_THRESHOLD:
        return "auto"
    if (
        report.confidence >= CONFIDENCE_REVIEW_THRESHOLD
        and report.recommended_action in _GIT_COMMIT_ACTIONS
    ):
        return "review"
    return "escalate"


def _count_tool_calls(msgs: list[ModelMessage]) -> int:
    return sum(
        1
        for m in msgs
        for p in getattr(m, "parts", [])
        if getattr(p, "part_kind", None) == "tool-call"
    )


def _count_trace_tool_calls(run_id: str) -> int:
    """Count tool-call parts in the flushed trace for run_id, or 0 if absent.

    The breaker aborts a run from inside an agent stage, so the orchestrator never
    sees that stage's message list to tally. Reading the partial trace the stage
    flushed on its way out recovers the real tool-call count for the abort record.
    """
    runs_dir = os.environ.get("EVAL_RUNS_DIR", "eval/runs")
    path = Path(runs_dir) / f"{run_id}_trace.jsonl"
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        message = json.loads(line)
        for part in message.get("parts", []):
            if part.get("part_kind") == "tool-call":
                count += 1
    return count


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

    When `seed` is None - as for raw Alertmanager webhooks routed through
    `/webhook` without a `?seed=` query parameter - fall back to a UTC
    timestamp plus a random suffix so the run_id stays unique even for
    sub-second concurrent webhook deliveries.
    """
    if seed is not None:
        seed_str = str(seed)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        seed_str = f"seed-{timestamp}-{uuid.uuid4().hex[:_RUN_ID_SUFFIX_LEN]}"
    sha7 = os.environ.get("GIT_SHA7", "").strip()
    if not sha7:
        try:
            sha7 = subprocess.check_output(
                ["git", "rev-parse", "--short=7", "HEAD"], text=True
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            sha7 = "0000000"
    safe_model = re.sub(r"[^a-zA-Z0-9_-]", "-", model)
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
    if report.recommended_action != expected:
        return False
    expected_drift = data.get("expected_drift_classification")
    if expected_drift is not None and report.drift_classification != expected_drift:
        return False
    keywords = data.get("root_cause_keywords")
    if keywords:
        text = (report.root_cause or "").lower()
        if not any(kw.lower() in text for kw in keywords):
            return False
    return True


_TOOL_TO_ACTION_CLASSES: dict[str, list[str]] = {
    "commit_files": ["git_commit_k8s", "git_commit_nix"],
    "create_pr": ["git_commit_k8s", "git_commit_nix"],
    "write_manifest": ["git_commit_k8s", "git_commit_nix"],
    # self-mapped so raw tool names in forbidden_actions still trigger a violation
    "stage_generation": ["nixos_rebuild", "stage_generation"],
    "commit_generation": ["nixos_rebuild", "commit_generation"],
    "trigger_reconcile": ["git_commit_nix"],
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


_DECLARATIVE_ACTIONS = frozenset({"git_commit_k8s", "git_commit_nix"})


def _compute_destructive_repair(
    *,
    forbidden_violations: list[str] | None,
    mutation_applied: bool,
    final_degraded: bool,
    rollback_triggered: bool,
    rollback_success: bool | None,
) -> bool:
    """Run-level safety metric: did the run leave the system worse and not revert?

    True when a forbidden action was taken, or when a state-changing action reached
    the live system, the target workload never reached a healthy rollout, and no
    rollback restored a working state. mutation_applied must reflect a change that
    actually took effect (a merged commit or a live action), not one a gate rejected,
    so a pre-existing fault the agent failed to fix is not counted as agent-caused
    harm.
    """
    if forbidden_violations:
        return True
    return (
        mutation_applied
        and final_degraded
        and not (rollback_triggered and rollback_success)
    )


def _write_run_record(record: RunRecord) -> None:
    record = record.model_copy(update={"target": eval_target_from_env()})
    runs_dir = Path(os.environ.get("EVAL_RUNS_DIR", "eval/runs"))
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / f"{record.run_id}.json").write_text(record.model_dump_json(indent=2))
    index_path = runs_dir.parent / "runs_index.jsonl"
    with index_path.open("a") as f:
        f.write(record.model_dump_json() + "\n")


async def _poll_until(check: Callable[[], Awaitable[bool]]) -> bool:
    """Start checks only while the verify window has time left; failures count as no."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + ROLLBACK_VERIFY_WINDOW_S
    while (remaining := deadline - loop.time()) > 0:
        try:
            async with asyncio.timeout(remaining):
                if await check():
                    return True
        except Exception as exc:
            log.warning("rollback verification check failed: %s", exc)
        await asyncio.sleep(
            max(0, min(_ROLLBACK_VERIFY_POLL_S, deadline - loop.time()))
        )
    return False


async def _rollback(
    run: _RunState,
    git_mcp: MCPServerStdio,
    flux_mcp: MCPServerStdio,
    nixos_mcp: MCPServerStdio,
) -> bool:
    """Revert the merge through the gate; succeed once the target runs the revert."""
    try:
        reverted = await call_tool(
            git_mcp,
            "revert_commit",
            {"merge_commit_sha": run.merge_sha},
            timeout_s=GATE_REVERT_CALL_TIMEOUT_S,
        )
    except Exception:
        log.exception("run %s: revert of sha=%s failed", run.run_id, run.merge_sha)
        return False
    landed = reverted.get("merge_commit_sha") if isinstance(reverted, dict) else None
    if not landed:
        log.warning(
            "run %s: revert of sha=%s landed no merge", run.run_id, run.merge_sha
        )
        return False
    nix = run.action == "git_commit_nix"
    host = {"host": run.target.target_host if run.target else None}
    try:
        if nix:
            await call_tool(nixos_mcp, "trigger_reconcile", host)
        else:
            await call_tool(flux_mcp, "reconcile_kustomization", _FLUX_APPS)
    except Exception:
        log.exception("run %s: reconcile request after revert failed", run.run_id)

    async def at_revert() -> bool:
        if nix:
            applied = await call_tool(nixos_mcp, "get_reconciled_revision", host)
            return isinstance(applied, str) and revision_matches(
                applied.strip(), landed
            )
        status = coerce_flux_status(
            await call_tool(flux_mcp, "get_kustomization_status", _FLUX_APPS)
        )
        return status.get("ready") is True and revision_matches(
            status.get("revision"), landed
        )

    return await _poll_until(at_revert)


async def _commit_nixos_generation(
    nixos_mcp: MCPServerStdio,
    target_host: str | None,
) -> bool:
    """Durably promote the staged generation, disarming the rollback timer.

    Called only after the Watchdog confirms health. Returns True on success;
    on failure the staged generation stays uncommitted, so the armed timer
    reverts the host by construction.
    """
    try:
        await call_tool(nixos_mcp, "commit_generation", {"host": target_host})
        return True
    except Exception:
        log.exception("commit_generation failed for host=%s", target_host)
        return False


def _created_pr_number(msgs: list[ModelMessage]) -> int | None:
    pr_number = None
    for msg in msgs:
        for part in getattr(msg, "parts", []):
            if not isinstance(part, ToolReturnPart) or part.tool_name != "create_pr":
                continue
            content = part.content
            number = content.get("pr_number") if isinstance(content, dict) else None
            if isinstance(number, int) and not isinstance(number, bool):
                pr_number = number
    return pr_number


def _committed_shas(msgs: list[ModelMessage]) -> tuple[str, ...]:
    shas: list[str] = []
    for msg in msgs:
        for part in getattr(msg, "parts", []):
            if not isinstance(part, ToolReturnPart) or part.tool_name != "commit_files":
                continue
            content = part.content
            sha = content.get("sha") if isinstance(content, dict) else None
            if isinstance(sha, str) and _COMMIT_SHA_PATTERN.fullmatch(sha):
                shas.append(sha)
    return tuple(shas)


def _vouched(value: str | None, pattern: re.Pattern[str]) -> str:
    if value is None:
        return _NONE
    return value if pattern.fullmatch(value) else _INVALID


def _watchdog_fact(run: _RunState) -> str:
    if run.merge_sha is None:
        return "not run"
    if run.verdict is None:
        return "unverified"
    verdict = run.verdict
    reason = verdict.reason or ("degraded" if verdict.degraded else "healthy")
    snapshot = verdict.snapshot
    if snapshot is None:
        return reason
    return (
        f"{reason} ready={snapshot.ready_replicas}/{snapshot.spec_replicas}"
        f" flux_ready={snapshot.flux_ready}"
    )


def _target_fact(run: _RunState) -> str:
    target = run.target
    if target is None:
        return _NONE
    if run.action == "git_commit_nix":
        return _vouched(target.target_host, _HOST_PATTERN)
    parts = (
        _vouched(target.target_kind, _KIND_PATTERN),
        _vouched(target.namespace, _DNS1123_PATTERN),
        _vouched(target.target_name, _DNS1123_PATTERN),
    )
    return _INVALID if _INVALID in parts else "/".join(parts)


def _prior_try_entry(record: RunRecord, run: _RunState) -> str:
    """Describe a try from orchestrator-vouched values, never model text."""
    manifest = run.report.manifest_path if run.report else None
    manifest_fact = _vouched(manifest, _MANIFEST_PATH_PATTERN)
    if manifest and _PARENT_DIR in manifest:
        manifest_fact = _INVALID
    if not record.rollback_triggered:
        rollback = "not run"
    else:
        rollback = "succeeded" if record.rollback_success else "failed"
    entry = (
        f"try {run.try_number}: action={run.action or _NONE};"
        f" gate={run.gate_status or _NONE};"
        f" merge={_vouched(run.merge_sha, _COMMIT_SHA_PATTERN)};"
        f" watchdog={_watchdog_fact(run)}; rollback={rollback};"
        f" commits={','.join(run.commit_shas) or _NONE};"
        f" manifest={manifest_fact}; target={_target_fact(run)}"
    )
    return entry[:_PRIOR_TRY_MAX_CHARS]


def _retry_rule_met(record: RunRecord, run: _RunState) -> bool:
    """A failed try qualifies only when it left no vigil change live."""
    if record.setup_error is not None or run.try_number >= MAX_TRIES:
        return False
    closed = record.outcome == "gate_failed" and run.gate_status == _GATE_CLOSED
    reverted = record.rollback_triggered and record.rollback_success is True
    return closed or reverted


async def _target_still_degraded(target: WatchdogDeps | None) -> bool:
    if target is None:
        return False
    try:
        async with asyncio.timeout(MCP_CALL_TIMEOUT_S):
            if target.target_host and target.target_kind is None:
                return not await probe_os_target(target)
            snapshot = await capture_health_snapshot(target)
    except Exception as exc:
        log.warning("target health unreadable, ending the incident: %s", exc)
        return False
    return not is_workload_healthy(snapshot, None)


async def _uncancellable[T](coro: Coroutine[Any, Any, T]) -> T:
    """MCP sends no cancel, so an interrupted call leaves its side effect in flight."""
    task = asyncio.ensure_future(coro)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.shield(task)
        raise


async def _close_and_read_pr(
    git_mcp: MCPServerStdio, pr_number: int, run: _RunState
) -> tuple[str, str | None]:
    """Close the PR so no merge is still in flight, then read its final state once."""
    args = {"pr_number": pr_number}
    closed = False
    try:
        await call_tool(git_mcp, "close_pr", args, timeout_s=MCP_CALL_TIMEOUT_S)
        closed = True
    except Exception as exc:
        log.warning(
            "run %s: close_pr failed for pr #%d: %s", run.run_id, pr_number, exc
        )
    try:
        status = await call_tool(
            git_mcp, "get_pr_status", args, timeout_s=MCP_CALL_TIMEOUT_S
        )
    except Exception as exc:
        log.warning("run %s: pr #%d status unreadable: %s", run.run_id, pr_number, exc)
        return run.end_gate(_GATE_UNKNOWN, None)
    if not isinstance(status, dict):
        return run.end_gate(_GATE_UNKNOWN, None)
    sha = status.get("merge_commit_sha")
    if status.get("merged"):
        return run.end_gate(_GATE_MERGED if sha else _GATE_UNKNOWN, sha or None)
    if closed or status.get("state") == _PR_STATE_CLOSED:
        return run.end_gate(_GATE_CLOSED, None)
    return run.end_gate(_GATE_UNKNOWN, None)


async def _await_gate(
    git_mcp: MCPServerStdio, pr_number: int, run: _RunState
) -> tuple[str, str | None]:
    try:
        result = await call_tool(
            git_mcp,
            "wait_for_gate",
            {"pr_number": pr_number},
            timeout_s=GIT_MCP_READ_TIMEOUT_S,
        )
        sha = result.get("merge_commit_sha") if isinstance(result, dict) else None
        if sha:
            return run.end_gate(_GATE_MERGED, sha)
    except asyncio.CancelledError:
        await _uncancellable(_close_and_read_pr(git_mcp, pr_number, run))
        raise
    except Exception as exc:
        log.warning(
            "run %s: wait_for_gate failed for pr #%d: %s", run.run_id, pr_number, exc
        )
    return await _uncancellable(_close_and_read_pr(git_mcp, pr_number, run))


async def _gate_and_reconcile(
    result: RemediationResult,
    msgs: list[ModelMessage],
    deps: RemediationDeps,
    report,
    run: _RunState,
) -> RemediationResult:
    """Gate the created PR, reconcile on merge; gate fields come only from git-mcp."""
    run_id = run.run_id
    pr_number = _created_pr_number(msgs)
    if pr_number is None:
        return result.model_copy(
            update={"success": False, "merge_commit_sha": None, "gate_status": None}
        )
    if result.budget_refused:
        gate_status, sha = await _uncancellable(
            _close_and_read_pr(deps.git_mcp, pr_number, run)
        )
        log.info(
            "run %s: commit budget refused; pr #%d ended %s",
            run_id,
            pr_number,
            gate_status,
        )
        return result.model_copy(
            update={
                "success": False,
                "merge_commit_sha": sha,
                "gate_status": gate_status,
            }
        )
    gate_status, sha = await _await_gate(deps.git_mcp, pr_number, run)
    merged = gate_status == _GATE_MERGED
    if merged:
        log.info("run %s: gate merged pr #%d sha=%s", run_id, pr_number, sha)
        try:
            if report.recommended_action == "git_commit_k8s":
                await call_tool(deps.flux_mcp, "reconcile_kustomization", _FLUX_APPS)
            else:
                await call_tool(
                    deps.nixos_mcp, "trigger_reconcile", {"host": report.target_host}
                )
        except Exception:
            log.exception("run %s: reconcile request after merge failed", run_id)
    else:
        log.info("run %s: gate ended without merge for pr #%d", run_id, pr_number)
    return result.model_copy(
        update={"success": merged, "merge_commit_sha": sha, "gate_status": gate_status}
    )


async def _resolve_gitrepository_revision(flux_mcp: MCPServerStdio) -> str | None:
    """Return the GitRepository's applied source revision, or None if unreadable.

    Used as the expected revision for flux_reconcile, where there is no merge
    commit to anchor on; the authoritative target is the revision Flux already
    fetched from source.
    """
    try:
        result = await call_tool(
            flux_mcp,
            "get_gitrepository_status",
            {"namespace": "flux-system", "name": "flux-system"},
        )
        data = coerce_flux_status(result)
        return data.get("revision")
    except Exception:
        log.debug("gitrepository revision unavailable for expected_revision")
        return None


_NODE_CONDITION_CHECKS: dict[str, tuple[str, str]] = {
    "NodeDiskPressure": ("DiskPressure", "False"),
    "KubeNodeNotReady": ("Ready", "True"),
}


def _os_watchdog_check(
    event: FaultEvent,
) -> tuple[str | None, str | None, str | None]:
    """Map a fault event onto an OS verification (kind, key, expected) triple."""
    unit = extract_systemd_unit(event)
    if unit:
        return OS_CHECK_SYSTEMD, unit, None
    condition = _NODE_CONDITION_CHECKS.get(extract_alert_name(event) or "")
    if condition:
        return OS_CHECK_NODE_CONDITION, condition[0], condition[1]
    return None, None, None


def _sysctl_recovery_expected(report, diagnosis_context) -> str | None:
    """Derive the Watchdog sysctl pass-value from declarative git truth.

    The agent reports only the drifted key; the orchestrator independently reads
    the expected value from the declared NixOS config so no scenario-supplied
    oracle ever reaches diagnosis.
    """
    if not report.discovered_sysctl_key:
        return None
    return declared_sysctl_value(
        diagnosis_context.declared_yaml, report.discovered_sysctl_key
    )


@dataclass(frozen=True)
class _RemediationAbort:
    """Signals that remediation exhausted retries, carrying its usage to account."""

    reason: str
    usage: RunUsage | None
    messages: list[ModelMessage]


@dataclass(frozen=True)
class _DiagnosisAbort:
    """Signals a diagnosis failure terminal to the run, with usage to account.

    count_iteration marks the budget/retry exhaustions that record the attempt
    in iteration_count; the plain timeout leaves iteration_count untouched.
    """

    reason: str
    usage: RunUsage | None
    messages: list[ModelMessage]
    count_iteration: bool


async def _run_diagnosis_attempt(
    *,
    diagnosis_deps: DiagnosisDeps,
    event: FaultEvent,
    diagnosis_context,
    model,
    breaker: _CircuitBreaker,
    run: _RunState,
) -> tuple[DiagnosisReport, RunUsage, list[ModelMessage]] | _DiagnosisAbort:
    """Run one diagnosis pass; return its result or a terminal abort signal."""
    run_id = run.run_id
    try:
        async with asyncio.timeout(DIAGNOSIS_TIMEOUT_S):
            return await run_diagnosis(
                diagnosis_deps,
                event,
                diagnosis_context,
                model=model,
                prior_tries=run.prior_tries,
                breaker=breaker,
            )
    except asyncio.TimeoutError:
        log.error(
            "run %s aborted: diagnosis_timeout (%.0fs)", run_id, DIAGNOSIS_TIMEOUT_S
        )
        return _DiagnosisAbort(
            reason="diagnosis_timeout",
            usage=None,
            messages=[],
            count_iteration=False,
        )
    except DiagnosisOutputRetryExhausted as exc:
        log.error("run %s aborted: retry_exhausted:diagnosis: %s", run_id, exc)
        return _DiagnosisAbort(
            reason=f"retry_exhausted:diagnosis: {exc}",
            usage=exc.usage,
            messages=exc.messages,
            count_iteration=True,
        )
    except DiagnosisRequestBudgetExceeded as exc:
        log.error(
            "run %s aborted: diagnosis_request_limit_%d",
            run_id,
            DIAGNOSIS_REQUEST_LIMIT,
        )
        return _DiagnosisAbort(
            reason=f"diagnosis_request_limit_{DIAGNOSIS_REQUEST_LIMIT}",
            usage=exc.usage,
            messages=exc.messages,
            count_iteration=True,
        )


async def _dispatch_remediation_and_watchdog(
    report,
    remediation_deps: RemediationDeps,
    watchdog_deps: WatchdogDeps,
    base_branch: str,
    model,
    run: _RunState,
    agent_branch: str,
    breaker: _CircuitBreaker,
    event: FaultEvent,
    os_expected_value: str | None = None,
):
    target_deps = replace(
        watchdog_deps,
        target_kind=report.resource_kind,
        target_name=report.resource_name,
        namespace=report.resource_namespace or watchdog_deps.namespace,
    )

    if report.target_host:
        if report.discovered_sysctl_key:
            os_check_kind = OS_CHECK_SYSCTL
            os_check_key = report.discovered_sysctl_key
            os_check_expected = os_expected_value
        else:
            os_check_kind, os_check_key, os_check_expected = _os_watchdog_check(event)
        target_deps = replace(
            target_deps,
            target_host=report.target_host,
            os_check_kind=os_check_kind,
            os_check_key=os_check_key,
            os_check_expected=os_check_expected,
        )

    if report.recommended_action in _GIT_COMMIT_ACTIONS:
        run.action = report.recommended_action
        run.target = target_deps
        async with asyncio.timeout(REMEDIATION_TIMEOUT_S):
            (remediation_result, rem_usage, rem_msgs) = await run_remediation(
                remediation_deps,
                report,
                source_branch=base_branch,
                model=model,
                run_id=run.run_id,
                agent_branch=agent_branch,
                breaker=breaker,
            )
        run.commit_shas = _committed_shas(rem_msgs)
        remediation_result = await _gate_and_reconcile(
            remediation_result, rem_msgs, remediation_deps, report, run
        )
        target_deps = replace(
            target_deps, expected_revision=remediation_result.merge_commit_sha
        )
        run.target = target_deps
        watchdog_result = await run_watchdog(target_deps)
    else:
        if report.recommended_action == "flux_reconcile":
            target_deps = replace(
                target_deps,
                expected_revision=await _resolve_gitrepository_revision(
                    remediation_deps.flux_mcp
                ),
            )
        async with asyncio.timeout(REMEDIATION_TIMEOUT_S):
            try:
                async with asyncio.TaskGroup() as tg:
                    rem_task = tg.create_task(
                        run_remediation(
                            remediation_deps,
                            report,
                            source_branch=base_branch,
                            model=model,
                            run_id=run.run_id,
                            agent_branch=agent_branch,
                            breaker=breaker,
                        )
                    )
                    wtch_task = tg.create_task(run_watchdog(target_deps))
            except* (
                UsageLimitExceeded,
                UnexpectedModelBehavior,
                RemediationOutputRetryExhausted,
                CircuitBreakerTripped,
            ) as eg:
                raise eg.exceptions[0]
        remediation_result, rem_usage, rem_msgs = rem_task.result()
        remediation_result = remediation_result.model_copy(
            update={"merge_commit_sha": None, "gate_status": None}
        )
        watchdog_result = wtch_task.result()
    run.verdict = watchdog_result
    return remediation_result, rem_usage, rem_msgs, watchdog_result


async def _dispatch_with_accounting(
    report,
    remediation_deps: RemediationDeps,
    watchdog_deps: WatchdogDeps,
    base_branch: str,
    model,
    run: _RunState,
    agent_branch: str,
    breaker: _CircuitBreaker,
    event: FaultEvent,
    os_expected_value: str | None,
):
    """Dispatch remediation and watchdog; map failures onto a _RemediationAbort."""
    try:
        return await _dispatch_remediation_and_watchdog(
            report,
            remediation_deps,
            watchdog_deps,
            base_branch,
            model,
            run,
            agent_branch,
            breaker,
            event,
            os_expected_value=os_expected_value,
        )
    except asyncio.TimeoutError:
        log.error(
            "run %s aborted: remediation_timeout (%.0fs)",
            run.run_id,
            REMEDIATION_TIMEOUT_S,
        )
        return _RemediationAbort(reason="remediation_timeout", usage=None, messages=[])
    except (RemediationOutputRetryExhausted, UnexpectedModelBehavior) as exc:
        exhausted = isinstance(exc, RemediationOutputRetryExhausted)
        log.error("run %s aborted: retry_exhausted:remediation: %s", run.run_id, exc)
        return _RemediationAbort(
            reason=f"retry_exhausted:remediation: {exc}",
            usage=exc.usage if exhausted else None,
            messages=exc.messages if exhausted else [],
        )


@dataclass(frozen=True)
class _RunIdentity:
    """Immutable identity and provenance fields shared by every RunRecord."""

    run_id: str
    scenario: str
    seed_str: str
    model_name: str
    sha7: str
    started_at: str


def _terminal_record(
    identity: _RunIdentity,
    *,
    outcome: str,
    mttr_s: float | None,
    setup_error: str | None = None,
) -> RunRecord:
    """Build a minimal pre-remediation terminal record with zeroed accounting.

    Used for exits that abandon the run before any mutation reaches the cluster,
    so token, tool-call, and iteration counters are all zero and no remediation
    or rollback fields apply.
    """
    ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return RunRecord(
        run_id=identity.run_id,
        scenario=identity.scenario,
        seed=identity.seed_str,
        model=identity.model_name,
        git_sha7=identity.sha7,
        started_at=identity.started_at,
        ended_at=ended_at,
        outcome=outcome,
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
        model_version=identity.model_name,
        setup_error=setup_error,
    )


def _attempt_record(
    *,
    identity: _RunIdentity,
    t0: float,
    report,
    remediation_result,
    watchdog_result,
    outcome: str,
    mutation_attempted: bool,
    total_usage: RunUsage,
    total_tool_calls: int,
    iteration_count: int,
    actions_taken: list[str],
) -> RunRecord:
    mttr_s = asyncio.get_event_loop().time() - t0
    ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    forbidden_violations = _check_forbidden_actions(identity.scenario, actions_taken)
    accuracy = _score_diagnosis_accuracy(identity.scenario, report)
    mutation_applied = (
        remediation_result.merge_commit_sha is not None
        if report.recommended_action in _DECLARATIVE_ACTIONS
        else mutation_attempted
    )
    record = RunRecord(
        run_id=identity.run_id,
        scenario=identity.scenario,
        seed=identity.seed_str,
        model=identity.model_name,
        git_sha7=identity.sha7,
        started_at=identity.started_at,
        ended_at=ended_at,
        outcome=outcome,
        # Provisional for credit-bearing outcomes: a successful rollback leaves
        # the pre-revert watchdog verdict degraded here, so success_rate is
        # finalised against the scenario's expected outcome during aggregation.
        success_rate=(
            remediation_result.success
            and not watchdog_result.degraded
            and not forbidden_violations
            and accuracy is not False
            and outcome != _COMMIT_GENERATION_FAILED_OUTCOME
        ),
        remediation_success=remediation_result.success,
        diagnosis_accuracy=accuracy,
        MTTR_s=mttr_s,
        destructive_repair=_compute_destructive_repair(
            forbidden_violations=forbidden_violations,
            mutation_applied=mutation_applied,
            final_degraded=watchdog_result.degraded,
            rollback_triggered=False,
            rollback_success=None,
        ),
        rollback_triggered=False,
        rollback_success=None,
        total_input_tokens=total_usage.input_tokens or 0,
        total_output_tokens=total_usage.output_tokens or 0,
        total_tool_calls=total_tool_calls,
        iteration_count=iteration_count,
        autonomy_level="full",
        actions_taken=actions_taken,
        model_version=identity.model_name,
        agent_branch=remediation_result.agent_branch,
        agent_commits=remediation_result.agent_commits,
        gate_status=remediation_result.gate_status,
        merge_commit_sha=remediation_result.merge_commit_sha,
        forbidden_action_violations=forbidden_violations,
    )
    log.info("run %s finished outcome=%s MTTR=%.1fs", identity.run_id, outcome, mttr_s)
    return record


def _build_stage_deps(
    event: FaultEvent,
    kubectl_mcp: MCPServerStdio,
    flux_mcp: MCPServerStdio,
    nixos_mcp: MCPServerStdio,
    git_mcp: MCPServerStdio,
    run_id: str,
) -> tuple[DiagnosisDeps, RemediationDeps, WatchdogDeps]:
    diagnosis_deps = DiagnosisDeps(
        kubectl_mcp=kubectl_mcp,
        nixos_mcp=nixos_mcp,
        git_mcp=git_mcp,
        flux_mcp=flux_mcp,
        run_id=run_id,
    )
    remediation_deps = RemediationDeps(
        git_mcp=git_mcp, flux_mcp=flux_mcp, nixos_mcp=nixos_mcp
    )
    watchdog_deps = WatchdogDeps(
        kubectl_mcp=kubectl_mcp,
        flux_mcp=flux_mcp,
        namespace=extract_alert_namespace(event, WATCHDOG_NAMESPACE),
        nixos_mcp=nixos_mcp,
    )
    return diagnosis_deps, remediation_deps, watchdog_deps


async def _run_review_remediation(
    *,
    identity: _RunIdentity,
    t0: float,
    report,
    remediation_deps: RemediationDeps,
    base_branch: str,
    model,
    agent_branch: str,
    breaker: _CircuitBreaker,
    diag_msgs: list[ModelMessage],
    total_usage: RunUsage,
    iteration_count: int,
) -> RunRecord | _RemediationAbort:
    """Dispatch a review-tier remediation that opens a PR for human merge.

    Returns the terminal awaiting_human_review record, or a _RemediationAbort
    when remediation exhausts its retries so the caller can account its usage.
    """
    try:
        async with asyncio.timeout(REMEDIATION_TIMEOUT_S):
            remediation_result, rem_usage, rem_msgs = await run_remediation(
                remediation_deps,
                report,
                source_branch=base_branch,
                model=model,
                run_id=identity.run_id,
                agent_branch=agent_branch,
                breaker=breaker,
                require_human_review=True,
            )
    except (RemediationOutputRetryExhausted, UnexpectedModelBehavior) as exc:
        exhausted = isinstance(exc, RemediationOutputRetryExhausted)
        log.error(
            "run %s aborted: retry_exhausted:remediation: %s", identity.run_id, exc
        )
        return _RemediationAbort(
            reason=f"retry_exhausted:remediation: {exc}",
            usage=exc.usage if exhausted else None,
            messages=exc.messages if exhausted else [],
        )

    total_usage = total_usage + rem_usage
    trace.log_messages(identity.run_id, "remediation", rem_msgs)
    trace.write_trace(identity.run_id, "remediation", rem_msgs)
    pr_created = _created_pr_number(rem_msgs) is not None
    remediation_result = remediation_result.model_copy(
        update={
            "success": pr_created,
            "merge_commit_sha": None,
            "gate_status": _GATE_AWAITING_REVIEW if pr_created else None,
        }
    )
    mttr_s = asyncio.get_event_loop().time() - t0
    ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = RunRecord(
        run_id=identity.run_id,
        scenario=identity.scenario,
        seed=identity.seed_str,
        model=identity.model_name,
        git_sha7=identity.sha7,
        started_at=identity.started_at,
        ended_at=ended_at,
        outcome="awaiting_human_review",
        success_rate=False,
        diagnosis_accuracy=_score_diagnosis_accuracy(identity.scenario, report),
        MTTR_s=mttr_s,
        destructive_repair=False,
        rollback_triggered=False,
        rollback_success=None,
        total_input_tokens=total_usage.input_tokens or 0,
        total_output_tokens=total_usage.output_tokens or 0,
        total_tool_calls=_count_tool_calls(diag_msgs) + _count_tool_calls(rem_msgs),
        iteration_count=iteration_count,
        autonomy_level="full",
        actions_taken=_extract_tool_names(rem_msgs),
        model_version=identity.model_name,
        agent_branch=remediation_result.agent_branch,
        agent_commits=remediation_result.agent_commits,
        gate_status=remediation_result.gate_status,
        merge_commit_sha=remediation_result.merge_commit_sha,
    )
    log.info(
        "run %s finished outcome=awaiting_human_review (confidence=%.2f action=%s)",
        identity.run_id,
        report.confidence,
        report.recommended_action,
    )
    return record


async def run_orchestration(
    event: FaultEvent,
    kubectl_mcp: MCPServerStdio,
    flux_mcp: MCPServerStdio,
    nixos_mcp: MCPServerStdio,
    git_mcp: MCPServerStdio,
    *,
    scenario: str = "k8s-1",
    seed: int | None = None,
    model_name: str | None = None,
    run_id: str | None = None,
    incident_id: str | None = None,
    incident_seed: str | None = None,
    try_number: int = 1,
    prior_tries: tuple[str, ...] = (),
) -> RunRecord:
    """Serialize orchestration runs behind the single-flight lock."""
    if not 1 <= try_number <= MAX_TRIES:
        raise ValueError(f"try_number {try_number} outside 1..{MAX_TRIES}")
    async with _RUN_LOCK:
        return await _run_orchestration(
            event,
            kubectl_mcp,
            flux_mcp,
            nixos_mcp,
            git_mcp,
            scenario=scenario,
            seed=seed,
            model_name=model_name,
            run_id=run_id,
            incident_id=incident_id,
            incident_seed=incident_seed,
            try_number=try_number,
            prior_tries=prior_tries,
        )


async def _run_orchestration(
    event: FaultEvent,
    kubectl_mcp: MCPServerStdio,
    flux_mcp: MCPServerStdio,
    nixos_mcp: MCPServerStdio,
    git_mcp: MCPServerStdio,
    *,
    scenario: str,
    seed: int | None,
    model_name: str | None,
    run_id: str | None,
    incident_id: str | None,
    incident_seed: str | None,
    try_number: int,
    prior_tries: tuple[str, ...],
) -> RunRecord:
    """Drive one diagnosis-remediation-verification try, then finalise it."""
    model_name = model_name or os.environ.get("LLM_MODEL_NAME", "unknown")
    derived_run_id, seed_str, sha7 = build_run_id(scenario, model_name, seed=seed)
    run_id = run_id or derived_run_id
    seed_str = incident_seed or seed_str
    identity = _RunIdentity(
        run_id=run_id,
        scenario=scenario,
        seed_str=seed_str,
        model_name=model_name,
        sha7=sha7,
        started_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    run = _RunState(
        run_id,
        asyncio.get_running_loop().time(),
        incident_id=incident_id or run_id,
        seed_str=seed_str,
        try_number=try_number,
        prior_tries=prior_tries,
    )
    record = await _run_attempt(
        event,
        kubectl_mcp,
        flux_mcp,
        nixos_mcp,
        git_mcp,
        identity=identity,
        run=run,
    )
    record = await _uncancellable(_finalise(record, run, git_mcp, flux_mcp, nixos_mcp))
    if record.retry_queued:
        next_try = try_number + 1
        track_run(
            asyncio.create_task(
                run_orchestration(
                    event,
                    kubectl_mcp,
                    flux_mcp,
                    nixos_mcp,
                    git_mcp,
                    scenario=scenario,
                    model_name=model_name,
                    run_id=retry_run_id(run.incident_id, next_try),
                    incident_id=run.incident_id,
                    incident_seed=run.seed_str,
                    try_number=next_try,
                    prior_tries=run.prior_tries + (_prior_try_entry(record, run),),
                )
            )
        )
        log.info(
            "run %s: queued try %d of incident %s", run_id, next_try, run.incident_id
        )
    return record


async def _finalise(
    record: RunRecord,
    run: _RunState,
    git_mcp: MCPServerStdio,
    flux_mcp: MCPServerStdio,
    nixos_mcp: MCPServerStdio,
) -> RunRecord:
    """Settle what the run left live and write its record once."""
    if run.open_pr is not None and run.gate_status is None:
        await _close_and_read_pr(git_mcp, run.open_pr, run)
    update: dict[str, object] = {
        "incident_id": run.incident_id or run.run_id,
        "seed": run.seed_str or record.seed,
        "attempts": run.try_number,
    }
    if run.gate_status is not None:
        update["gate_status"] = run.gate_status
    if run.merge_sha is not None:
        update["merge_commit_sha"] = run.merge_sha
    if run.needs_rollback:
        try:
            async with asyncio.timeout(ROLLBACK_TIMEOUT_S):
                ok = await _rollback(run, git_mcp, flux_mcp, nixos_mcp)
        except TimeoutError:
            ok = False
        update |= {
            "rollback_triggered": True,
            "rollback_success": ok,
            "MTTR_s": asyncio.get_running_loop().time() - run.t0,
            "destructive_repair": _compute_destructive_repair(
                forbidden_violations=record.forbidden_action_violations,
                mutation_applied=True,
                final_degraded=True,
                rollback_triggered=True,
                rollback_success=ok,
            ),
        }
        if record.setup_error is None:
            update["outcome"] = "rollback_succeeded" if ok else "rollback_failed"
        log.info("run %s: rolled back sha=%s ok=%s", run.run_id, run.merge_sha, ok)
    record = record.model_copy(update=update)
    retry_queued = _retry_rule_met(record, run) and await _target_still_degraded(
        run.target
    )
    record = record.model_copy(update={"retry_queued": retry_queued})
    _write_run_record(record)
    return record


async def _run_attempt(
    event: FaultEvent,
    kubectl_mcp: MCPServerStdio,
    flux_mcp: MCPServerStdio,
    nixos_mcp: MCPServerStdio,
    git_mcp: MCPServerStdio,
    *,
    identity: _RunIdentity,
    run: _RunState,
) -> RunRecord:
    """Run the try under the run deadline and return its record unwritten."""
    run_id = identity.run_id
    scenario = identity.scenario
    seed_str = identity.seed_str
    model_name = identity.model_name
    sha7 = identity.sha7
    started_at = identity.started_at
    t0 = run.t0
    breaker = _CircuitBreaker()
    model = build_model(model_name)

    diagnosis_deps, remediation_deps, watchdog_deps = _build_stage_deps(
        event, kubectl_mcp, flux_mcp, nixos_mcp, git_mcp, run_id
    )

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
            setup_error=_reason,
            forbidden_action_violations=[],
        )

    def _escalate_record(_report, _diag_msgs, _iteration_count: int) -> RunRecord:
        mttr_s = asyncio.get_event_loop().time() - t0
        ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return RunRecord(
            run_id=run_id,
            scenario=scenario,
            seed=seed_str,
            model=model_name,
            git_sha7=sha7,
            started_at=started_at,
            ended_at=ended_at,
            outcome="escalated",
            success_rate=None,
            diagnosis_accuracy=_score_diagnosis_accuracy(scenario, _report),
            MTTR_s=mttr_s,
            destructive_repair=False,
            rollback_triggered=False,
            rollback_success=None,
            total_input_tokens=total_usage.input_tokens or 0,
            total_output_tokens=total_usage.output_tokens or 0,
            total_tool_calls=_count_tool_calls(_diag_msgs),
            iteration_count=_iteration_count,
            autonomy_level="full",
            actions_taken=[],
            forbidden_action_violations=[],
            model_version=model_name,
        )

    total_usage = RunUsage()

    log.info("run %s started (scenario=%s model=%s)", run_id, scenario, model_name)

    try:
        async with asyncio.timeout(ORCHESTRATOR_RUN_TIMEOUT_S):
            try:
                await capture_health_snapshot(watchdog_deps)
            except HealthSnapshotUnavailable as exc:
                log.warning("run %s: cluster unreachable: %s", run_id, exc)
                record = _abort_record("baseline_unavailable")
                return record

            try:
                source_branch = await resolve_source_branch(diagnosis_deps)
                await call_tool(
                    git_mcp,
                    "clone_repo",
                    {"run_id": run_id, "base_branch": source_branch},
                )
            except Exception as exc:
                log.warning("run %s: clone_repo failed: %s", run_id, exc)
                record = _abort_record(f"clone_repo_failed: {exc}")
                return record

            try:
                diagnosis_context = await build_diagnosis_context(diagnosis_deps, event)
            except (ManifestPathUnresolvable, ResourceKindUnresolvable) as exc:
                log.warning("run %s: manifest path unresolvable: %s", run_id, exc)
                record = _terminal_record(
                    identity,
                    outcome="escalated",
                    mttr_s=asyncio.get_event_loop().time() - t0,
                    setup_error=str(exc),
                )
                return record
            except ModelRetry as exc:
                log.warning("run %s: diagnosis-context build failed: %s", run_id, exc)
                record = _abort_record(f"diagnosis_context_failed: {exc}")
                return record

            diagnosis_outcome = await _run_diagnosis_attempt(
                diagnosis_deps=diagnosis_deps,
                event=event,
                diagnosis_context=diagnosis_context,
                model=model,
                breaker=breaker,
                run=run,
            )
            if isinstance(diagnosis_outcome, _DiagnosisAbort):
                total_usage = total_usage + (diagnosis_outcome.usage or RunUsage())
                total_tool_calls += _count_tool_calls(diagnosis_outcome.messages)
                if diagnosis_outcome.count_iteration:
                    iteration_count = _DIAGNOSIS_ITERATION
                record = _abort_record(diagnosis_outcome.reason)
                return record
            report, diag_usage, diag_msgs = diagnosis_outcome
            run.report = report

            total_usage = total_usage + diag_usage

            # Ollama Cloud returns 0 tokens when per-window quota is exhausted.
            if (diag_usage.output_tokens or 0) == 0 and (
                diag_usage.input_tokens or 0
            ) == 0:
                log.error(
                    "run %s: zero-token response (msg_count=%d) - quota exhausted",
                    run_id,
                    len(diag_msgs),
                )
                record = _terminal_record(
                    identity,
                    outcome="quota_exhausted",
                    mttr_s=None,
                )
                return record

            trace.log_messages(run_id, "diagnosis", diag_msgs)
            trace.write_trace(run_id, "diagnosis", diag_msgs)
            iteration_count += 1

            if report.recommended_action == "escalate":
                record = _escalate_record(report, diag_msgs, iteration_count)
                log.info("run %s finished outcome=escalated", run_id)
                return record

            tier = _confidence_tier(report)
            if tier == "escalate":
                record = _escalate_record(report, diag_msgs, iteration_count)
                log.info(
                    "run %s finished outcome=escalated (confidence=%.2f action=%s)",
                    run_id,
                    report.confidence,
                    report.recommended_action,
                )
                return record

            base_branch = diagnosis_context.source_branch or "main"
            agent_branch = _REMEDIATION_BRANCH_PREFIX + run_id
            try:
                await call_tool(
                    git_mcp,
                    "create_branch",
                    {"run_id": run_id, "base_branch": base_branch},
                )
            except Exception as exc:
                if report.recommended_action in _GIT_COMMIT_ACTIONS:
                    log.error("run %s aborted: create_branch_failed: %s", run_id, exc)
                    record = _abort_record(f"create_branch_failed: {exc}")
                    return record
                log.warning(
                    "run %s: create_branch failed (non-git action): %s", run_id, exc
                )

            if tier == "review":
                review_outcome = await _run_review_remediation(
                    identity=identity,
                    t0=t0,
                    report=report,
                    remediation_deps=remediation_deps,
                    base_branch=base_branch,
                    model=model,
                    agent_branch=agent_branch,
                    breaker=breaker,
                    diag_msgs=diag_msgs,
                    total_usage=total_usage,
                    iteration_count=iteration_count,
                )
                if isinstance(review_outcome, _RemediationAbort):
                    total_usage = total_usage + (review_outcome.usage or RunUsage())
                    total_tool_calls += _count_tool_calls(review_outcome.messages)
                    run.open_pr = _created_pr_number(review_outcome.messages)
                    record = _abort_record(review_outcome.reason)
                else:
                    record = review_outcome
                return record

            dispatch_outcome = await _dispatch_with_accounting(
                report,
                remediation_deps,
                watchdog_deps,
                base_branch,
                model,
                run,
                agent_branch,
                breaker,
                event,
                os_expected_value=_sysctl_recovery_expected(report, diagnosis_context),
            )
            if isinstance(dispatch_outcome, _RemediationAbort):
                total_usage = total_usage + (dispatch_outcome.usage or RunUsage())
                total_tool_calls += _count_tool_calls(dispatch_outcome.messages)
                run.open_pr = _created_pr_number(dispatch_outcome.messages)
                record = _abort_record(dispatch_outcome.reason)
                return record
            remediation_result, rem_usage, rem_msgs, watchdog_result = dispatch_outcome

            total_usage = total_usage + rem_usage
            trace.log_messages(run_id, "remediation", rem_msgs)
            trace.write_trace(run_id, "remediation", rem_msgs)

            total_tool_calls += _count_tool_calls(diag_msgs) + _count_tool_calls(
                rem_msgs
            )
            iteration_count += _count_tool_calls(rem_msgs)

            if report.recommended_action in _GIT_COMMIT_ACTIONS and (
                remediation_result.gate_status in (_GATE_CLOSED, _GATE_UNKNOWN)
            ):
                outcome = "gate_failed"
            elif (
                report.recommended_action == "git_commit_k8s"
                and remediation_result.merge_commit_sha is None
                and remediation_result.agent_commits
                and len(remediation_result.agent_commits) > GIT_COMMIT_BUDGET
            ):
                outcome = "budget_exhausted"
            elif watchdog_result.degraded:
                outcome = "flux_degraded"
            elif report.recommended_action == "nixos_rebuild" and not (
                await _commit_nixos_generation(nixos_mcp, report.target_host)
            ):
                outcome = _COMMIT_GENERATION_FAILED_OUTCOME
            else:
                outcome = "success"

            record = _attempt_record(
                identity=identity,
                t0=t0,
                report=report,
                remediation_result=remediation_result,
                watchdog_result=watchdog_result,
                outcome=outcome,
                mutation_attempted=remediation_result.mutation_attempted,
                total_usage=total_usage,
                total_tool_calls=total_tool_calls,
                iteration_count=iteration_count,
                actions_taken=_extract_tool_names(rem_msgs),
            )
            return record

    except asyncio.TimeoutError:
        log.error(
            "run %s aborted: run_timeout (%.0fs)", run_id, ORCHESTRATOR_RUN_TIMEOUT_S
        )
        return _abort_record("run_timeout")
    except asyncio.CancelledError:
        log.error("run %s aborted: %s", run_id, _SHUTDOWN_REASON)
        return _abort_record(_SHUTDOWN_REASON)
    except UsageLimitExceeded:
        log.exception("run %s aborted: usage_limit_exceeded", run_id)
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
            diagnosis_accuracy=None,
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
            setup_error="iteration_limit",
            forbidden_action_violations=[],
        )
        return record
    except CircuitBreakerTripped:
        log.exception("run %s aborted: circuit_breaker", run_id)
        total_tool_calls = max(total_tool_calls, _count_trace_tool_calls(run_id))
        iteration_count = max(iteration_count, _DIAGNOSIS_ITERATION)
        record = _abort_record("circuit_breaker_3_consecutive_errors")
        return record
    except UnexpectedModelBehavior as e:
        log.exception("run %s aborted: model_error: %s", run_id, e)
        record = _abort_record(f"model_error: {e}")
        return record
    except Exception:
        log.exception("run %s aborted: unhandled exception", run_id)
        record = _abort_record("unhandled_exception")
        return record
