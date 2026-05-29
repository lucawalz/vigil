"""Watchdog agent: deterministic poll loop comparing live health to baseline.

Watchdog OBSERVES only. It does not call mutation tools and does not issue
rollbacks. When degradation is detected, it returns WatchdogResult(degraded=True)
to the Orchestrator, which owns the rollback decision.

Poll interval and window are env-var overridable:
  WATCHDOG_POLL_INTERVAL_S (default 5.0)
  WATCHDOG_WINDOW_S        (default 120.0)

This module intentionally does NOT use pydantic-ai Agent -- Watchdog logic is
deterministic: capture snapshot, compare, sleep, repeat. No LLM reasoning
is required and adding one would increase latency and cost for no benefit.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from common.flux_status import extract_mcp_text, parse_kust_text

from .models import HealthSnapshot, WatchdogDeps, WatchdogResult

log = logging.getLogger(__name__)

WATCHDOG_POLL_INTERVAL_S: float = float(
    os.environ.get("WATCHDOG_POLL_INTERVAL_S", "5.0")
)
WATCHDOG_WINDOW_S: float = float(os.environ.get("WATCHDOG_WINDOW_S", "120.0"))

# Module-level aliases so tests can monkeypatch POLL_INTERVAL_S / WINDOW_S directly.
POLL_INTERVAL_S = WATCHDOG_POLL_INTERVAL_S
WINDOW_S = WATCHDOG_WINDOW_S


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_pod_counts(tool_output: object) -> tuple[int, int]:
    """Extract (ready_pods, total_pods) from a kubectl-mcp get_pods response.

    Accepts a dict with a "content" key (string or list) or a bare string/list.
    Falls back to (0, 0) on unrecognised shapes so the poll loop records a
    degraded-looking state rather than crashing.
    """
    if isinstance(tool_output, dict):
        content: object = tool_output.get("content", tool_output)
    else:
        content = tool_output

    if isinstance(content, str):
        lines = [line for line in content.splitlines() if line.strip()]
        total = len(lines)
        ready = sum(1 for line in lines if "Running" in line or "Ready" in line)
        return ready, total

    if isinstance(content, list):
        total = len(content)
        ready = sum(
            1
            for item in content
            if isinstance(item, dict) and item.get("status") in ("Running", "Ready")
        )
        return ready, total

    return 0, 0


async def capture_health_snapshot(deps: WatchdogDeps) -> HealthSnapshot:
    """Single-shot health probe via kubectl-mcp and flux-mcp.

    Called once to capture the pre-remediation baseline, then repeatedly
    inside run_watchdog's poll loop.
    """
    pods_result = await deps.kubectl_mcp.direct_call_tool(
        "get_pods", {"namespace": deps.namespace}
    )
    ready, total = _parse_pod_counts(pods_result)
    endpoints_healthy = ready > 0

    flux_ready: bool | None = None
    try:
        kust_result = await deps.flux_mcp.direct_call_tool(
            "get_kustomization_status",
            {"namespace": "flux-system", "name": "cluster-apps"},
        )
        kust_data = parse_kust_text(extract_mcp_text(kust_result))
        flux_ready = kust_data.get("ready") == "True"
    except (RuntimeError, ValueError, AttributeError) as exc:
        log.warning("flux kustomization status unavailable: %s", exc)
        flux_ready = False

    return HealthSnapshot(
        ready_pods=ready,
        total_pods=total,
        endpoints_healthy=endpoints_healthy,
        flux_ready=flux_ready,
        captured_at=_now_iso(),
    )


def _health_degraded(baseline: HealthSnapshot, current: HealthSnapshot) -> bool:
    """Return True when cluster health deteriorates relative to baseline.

    Three rules:
      1. Ready pod count dropped below baseline.
      2. Endpoints were healthy at baseline but are now unhealthy.
      3. Flux cluster-apps was Ready at baseline but is now Not-Ready.
    Improvement is not degradation. Missing flux data (None) is not degradation.
    """
    if current.ready_pods < baseline.ready_pods:
        return True
    if baseline.endpoints_healthy and not current.endpoints_healthy:
        return True
    if baseline.flux_ready is True and current.flux_ready is False:
        return True
    return False


async def run_watchdog(deps: WatchdogDeps, baseline: HealthSnapshot) -> WatchdogResult:
    """Poll cluster health for up to WATCHDOG_WINDOW_S seconds.

    Returns WatchdogResult(degraded=True, snapshot=<first degraded obs>) on
    first detected degradation, or WatchdogResult(degraded=False,
    snapshot=<last obs>) if the deadline is reached without degradation.
    No rollback action is taken here -- the Orchestrator decides.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + WINDOW_S
    current = baseline
    while loop.time() < deadline:
        current = await capture_health_snapshot(deps)
        if _health_degraded(baseline, current):
            return WatchdogResult(degraded=True, snapshot=current)
        await asyncio.sleep(POLL_INTERVAL_S)
    return WatchdogResult(degraded=False, snapshot=current)
