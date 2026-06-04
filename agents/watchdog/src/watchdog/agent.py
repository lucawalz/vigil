"""Watchdog agent: deterministic poll loop asserting absolute workload health.

Watchdog OBSERVES only. It does not call mutation tools and does not issue
rollbacks. When the target has not converged to a healthy state, it returns
WatchdogResult(degraded=True) to the Orchestrator, which owns the rollback
decision.

Poll interval and window are env-var overridable:
  WATCHDOG_POLL_INTERVAL_S (default 5.0)
  WATCHDOG_WINDOW_S        (default 300.0)

This module intentionally does NOT use pydantic-ai Agent -- Watchdog logic is
deterministic: capture snapshot, evaluate an absolute-health predicate, sleep,
repeat. No LLM reasoning is required and adding one would increase latency and
cost for no benefit.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from common.constants import WATCHDOG_HEALTHY_STREAK_K
from common.flux_status import extract_mcp_text, parse_kust_text
from common.mcp_call import call_tool

from .models import (
    HealthSnapshot,
    HealthSnapshotUnavailable,
    WatchdogDeps,
    WatchdogResult,
)

log = logging.getLogger(__name__)

WATCHDOG_POLL_INTERVAL_S: float = float(
    os.environ.get("WATCHDOG_POLL_INTERVAL_S", "5.0")
)
WATCHDOG_WINDOW_S: float = float(os.environ.get("WATCHDOG_WINDOW_S", "300.0"))

# Module-level aliases so tests can monkeypatch POLL_INTERVAL_S / WINDOW_S directly.
POLL_INTERVAL_S = WATCHDOG_POLL_INTERVAL_S
WINDOW_S = WATCHDOG_WINDOW_S
HEALTHY_STREAK_K = WATCHDOG_HEALTHY_STREAK_K

_WORKLOAD_KINDS = frozenset({"Deployment", "StatefulSet"})
_PROGRESS_DEADLINE_REASON = "ProgressDeadlineExceeded"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pod_line_ready(line: str) -> bool:
    """Report whether a `get_pods` text line describes a fully-ready pod.

    A pod is ready only when its READY column numerator equals the denominator
    (e.g. 2/2, not 0/1) AND its phase is Running or Succeeded. A crashlooping
    pod shown as `Running 0/1` is not ready.
    """
    tokens = line.split()
    if not any(phase in tokens for phase in ("Running", "Succeeded")):
        return False
    for token in tokens:
        if "/" in token:
            num, _, den = token.partition("/")
            if num.isdigit() and den.isdigit():
                return den != "0" and num == den
    return False


def _parse_pod_counts(tool_output: object) -> tuple[int, int]:
    """Extract (ready_pods, total_pods) from a kubectl-mcp get_pods response.

    Accepts a dict with a "content" key (string or list) or a bare string/list.
    A pod counts as ready only when its READY fraction is fully satisfied and
    its phase is Running/Succeeded. Raises HealthSnapshotUnavailable on
    unrecognised shapes: returning (0, 0) would let a transient or malformed
    response masquerade as zero ready pods and fabricate degradation mid-poll.
    """
    if isinstance(tool_output, dict):
        content: object = tool_output.get("content", tool_output)
    else:
        content = tool_output

    if isinstance(content, str):
        lines = [line for line in content.splitlines() if line.strip()]
        total = len(lines)
        ready = sum(1 for line in lines if _pod_line_ready(line))
        return ready, total

    if isinstance(content, list):
        total = len(content)
        ready = sum(
            1
            for item in content
            if isinstance(item, dict) and item.get("status") in ("Running", "Ready")
        )
        return ready, total

    raise HealthSnapshotUnavailable(
        f"unrecognised get_pods response shape: {type(content).__name__}"
    )


def _strip_flux_revision(revision: str | None) -> str | None:
    """Return the bare SHA from a Flux revision like `branch/name@sha1:abc123`."""
    if not revision:
        return None
    sha = revision.rsplit("@", 1)[-1]
    if ":" in sha:
        sha = sha.split(":", 1)[1]
    return sha or None


def _revision_matches(flux_revision: str | None, expected_revision: str) -> bool:
    sha = _strip_flux_revision(flux_revision)
    if not sha:
        return False
    return sha.startswith(expected_revision) or expected_revision.startswith(sha)


def _apply_workload_status(snapshot_fields: dict, status: dict) -> None:
    snapshot_fields["workload_found"] = bool(status.get("found"))
    snapshot_fields["generation"] = status.get("generation")
    snapshot_fields["observed_generation"] = status.get("observedGeneration")
    snapshot_fields["spec_replicas"] = status.get("specReplicas")
    snapshot_fields["ready_replicas"] = status.get("readyReplicas")
    snapshot_fields["updated_replicas"] = status.get("updatedReplicas")
    snapshot_fields["available_replicas"] = status.get("availableReplicas")
    for condition in status.get("conditions") or []:
        ctype = condition.get("type")
        cstatus = condition.get("status")
        if ctype == "Available":
            snapshot_fields["available_condition"] = cstatus == "True"
        elif ctype == "Progressing":
            snapshot_fields["progressing_ok"] = cstatus != "False"
            snapshot_fields["progress_deadline_exceeded"] = (
                condition.get("reason") == _PROGRESS_DEADLINE_REASON
            )


def _coerce_rollout_status(result: object) -> dict:
    """Return the rollout_status payload as a dict.

    pydantic-ai auto-decodes a tool result whose text begins with "{" via
    pydantic_core.from_json, so a JSON rollout_status arrives already parsed; it
    may otherwise be a JSON string or a {"content": ...} wrapper. A payload that
    is none of these is surfaced as an indeterminate poll rather than aborting
    the run.
    """
    if isinstance(result, dict) and "content" not in result:
        return result
    text = extract_mcp_text(result)
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise HealthSnapshotUnavailable(
            f"rollout_status not JSON-decodable: {text[:120]}"
        ) from exc
    if not isinstance(parsed, dict):
        raise HealthSnapshotUnavailable("rollout_status payload is not an object")
    return parsed


async def capture_health_snapshot(deps: WatchdogDeps) -> HealthSnapshot:
    """Single-shot absolute-health probe via kubectl-mcp and flux-mcp.

    For Deployment/StatefulSet targets it reads structured rollout status; it
    always reads pod counts (namespace-liveness fallback and crashloop coverage)
    and the Flux Kustomization Ready state plus its applied revision.
    """
    snapshot_fields: dict = {
        "workload_found": False,
        "generation": None,
        "observed_generation": None,
        "spec_replicas": None,
        "ready_replicas": None,
        "updated_replicas": None,
        "available_replicas": None,
        "available_condition": None,
        "progressing_ok": None,
        "progress_deadline_exceeded": False,
    }

    if deps.target_kind in _WORKLOAD_KINDS and deps.target_name:
        rollout_result = await call_tool(
            deps.kubectl_mcp,
            "rollout_status",
            {"namespace": deps.namespace, "deployment": deps.target_name},
        )
        status = _coerce_rollout_status(rollout_result)
        _apply_workload_status(snapshot_fields, status)

    pods_result = await call_tool(
        deps.kubectl_mcp, "get_pods", {"namespace": deps.namespace}
    )
    ready, total = _parse_pod_counts(pods_result)

    flux_ready: bool | None = None
    flux_revision: str | None = None
    try:
        kust_result = await call_tool(
            deps.flux_mcp,
            "get_kustomization_status",
            {
                "namespace": deps.flux_kustomization_namespace,
                "name": deps.flux_kustomization_name,
            },
        )
        kust_data = parse_kust_text(extract_mcp_text(kust_result))
        flux_ready = kust_data.get("ready") == "True"
        flux_revision = kust_data.get("revision")
    except (RuntimeError, ValueError, AttributeError, TimeoutError) as exc:
        log.warning("flux kustomization status unavailable: %s", exc)
        flux_ready = None

    return HealthSnapshot(
        ready_pods=ready,
        total_pods=total,
        flux_ready=flux_ready,
        flux_revision=flux_revision,
        captured_at=_now_iso(),
        **snapshot_fields,
    )


def is_workload_healthy(
    snapshot: HealthSnapshot, expected_revision: str | None
) -> bool:
    """Return True when the target has converged to an absolutely healthy state.

    For a workload target (rollout status present) this mirrors the Kubernetes
    rollout-complete criteria: generation observed, all replicas updated, ready,
    and available, Available not False, Progressing not False, and never
    ProgressDeadlineExceeded. For a non-workload target it falls back to
    namespace liveness. Either path additionally requires Flux not to be
    Not-Ready and, when an expected revision is supplied, the applied revision
    to match it.
    """
    if snapshot.progress_deadline_exceeded:
        return False

    is_workload = (
        snapshot.observed_generation is not None and snapshot.spec_replicas is not None
    )
    if is_workload:
        if not snapshot.workload_found:
            return False
        if snapshot.observed_generation != snapshot.generation:
            return False
        replicas = (
            snapshot.ready_replicas,
            snapshot.updated_replicas,
            snapshot.available_replicas,
        )
        if any(value != snapshot.spec_replicas for value in replicas):
            return False
        if snapshot.available_condition is False:
            return False
        if snapshot.progressing_ok is False:
            return False
    else:
        if not (snapshot.total_pods > 0 and snapshot.ready_pods == snapshot.total_pods):
            return False

    if snapshot.flux_ready is False:
        return False
    if expected_revision and snapshot.flux_revision:
        if not _revision_matches(snapshot.flux_revision, expected_revision):
            return False
    return True


async def run_watchdog(deps: WatchdogDeps) -> WatchdogResult:
    """Poll until the target is healthy for K consecutive observations.

    Returns degraded=False, reason="healthy" once HEALTHY_STREAK_K consecutive
    healthy polls are seen. Fast-fails with reason="progress_deadline_exceeded"
    when the rollout reports ProgressDeadlineExceeded. On reaching the
    WATCHDOG_WINDOW_S deadline without a healthy streak returns degraded=True,
    reason="deadline_reached" carrying the last snapshot. An indeterminate read
    (HealthSnapshotUnavailable) skips that poll rather than fabricating a result.
    No rollback action is taken here -- the Orchestrator decides.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + WINDOW_S
    last_snapshot: HealthSnapshot | None = None
    healthy_streak = 0
    while loop.time() < deadline:
        try:
            snapshot = await capture_health_snapshot(deps)
        except HealthSnapshotUnavailable as exc:
            log.warning("watchdog poll indeterminate, skipping: %s", exc)
            await asyncio.sleep(POLL_INTERVAL_S)
            continue
        last_snapshot = snapshot
        if snapshot.progress_deadline_exceeded:
            return WatchdogResult(
                degraded=True,
                snapshot=snapshot,
                reason="progress_deadline_exceeded",
            )
        if is_workload_healthy(snapshot, deps.expected_revision):
            healthy_streak += 1
            if healthy_streak >= HEALTHY_STREAK_K:
                return WatchdogResult(
                    degraded=False, snapshot=snapshot, reason="healthy"
                )
        else:
            healthy_streak = 0
        await asyncio.sleep(POLL_INTERVAL_S)
    return WatchdogResult(
        degraded=True, snapshot=last_snapshot, reason="deadline_reached"
    )
