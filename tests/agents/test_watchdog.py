"""Watchdog: deterministic poll + degradation detection tests.

Uses mocked kubectl-mcp via AsyncMock so tests run without a live cluster.
Poll interval and window are monkey-patched to sub-second values to keep
the suite under 60 s total.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

import pytest
from watchdog import agent as watchdog_agent_mod
from watchdog.agent import (
    _health_degraded,
    capture_health_snapshot,
    run_watchdog,
)
from watchdog.models import HealthSnapshot, WatchdogDeps, WatchdogResult


def _snap(ready: int, total: int, healthy: bool) -> HealthSnapshot:
    return HealthSnapshot(
        ready_pods=ready,
        total_pods=total,
        endpoints_healthy=healthy,
        captured_at="2026-04-18T10:00:00Z",
    )


def test_health_degraded_detects_pod_regression() -> None:
    baseline = _snap(3, 3, True)
    current = _snap(1, 3, True)
    assert _health_degraded(baseline, current) is True


def test_health_degraded_detects_endpoint_flip() -> None:
    baseline = _snap(3, 3, True)
    current = _snap(3, 3, False)
    assert _health_degraded(baseline, current) is True


def test_health_degraded_false_when_steady() -> None:
    baseline = _snap(3, 3, True)
    current = _snap(3, 3, True)
    assert _health_degraded(baseline, current) is False


def test_health_degraded_false_when_improved() -> None:
    baseline = _snap(2, 3, True)
    current = _snap(3, 3, True)
    assert _health_degraded(baseline, current) is False


async def test_capture_health_snapshot_builds_snapshot() -> None:
    mock = AsyncMock()
    mock.call_tool = AsyncMock(
        return_value={"content": "pod/a Running\npod/b Running\npod/c Running"}
    )
    deps = WatchdogDeps(kubectl_mcp=mock)
    snap = await capture_health_snapshot(deps)
    assert isinstance(snap, HealthSnapshot)
    assert snap.total_pods == 3
    assert snap.ready_pods == 3
    assert snap.endpoints_healthy is True
    assert snap.captured_at.endswith("Z")
    mock.call_tool.assert_awaited()


async def test_run_watchdog_returns_degraded_when_pods_drop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(watchdog_agent_mod, "POLL_INTERVAL_S", 0.05)
    monkeypatch.setattr(watchdog_agent_mod, "WINDOW_S", 2.0)

    mock = AsyncMock()
    mock.call_tool = AsyncMock(return_value={"content": ""})  # zero ready pods
    deps = WatchdogDeps(kubectl_mcp=mock)
    baseline = _snap(3, 3, True)

    result = await run_watchdog(deps, baseline)
    assert isinstance(result, WatchdogResult)
    assert result.degraded is True
    assert result.snapshot is not None
    assert result.snapshot.ready_pods == 0


async def test_run_watchdog_returns_not_degraded_when_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(watchdog_agent_mod, "POLL_INTERVAL_S", 0.05)
    monkeypatch.setattr(watchdog_agent_mod, "WINDOW_S", 0.3)

    mock = AsyncMock()
    mock.call_tool = AsyncMock(
        return_value={"content": "pod/a Running\npod/b Running\npod/c Running"}
    )
    deps = WatchdogDeps(kubectl_mcp=mock)
    baseline = _snap(3, 3, True)

    result = await run_watchdog(deps, baseline)
    assert result.degraded is False


def test_watchdog_has_no_llm_dependency() -> None:
    """Watchdog is deterministic -- no build_model or pydantic_ai.Agent."""
    src = inspect.getsource(watchdog_agent_mod)
    assert "build_model" not in src
    assert "pydantic_ai.Agent" not in src


def test_watchdog_source_has_no_mutation_tool_names() -> None:
    """Watchdog OBSERVES. No suspend/patch/undo references in the module."""
    src = inspect.getsource(watchdog_agent_mod)
    for forbidden in ("apply_patch", "rollout_undo", "suspend_kustomization"):
        assert forbidden not in src, f"Watchdog must not reference {forbidden}"
