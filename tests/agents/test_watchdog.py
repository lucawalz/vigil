"""Watchdog: deterministic poll + absolute-health predicate tests.

Uses mocked kubectl-mcp / flux-mcp via AsyncMock so tests run without a live
cluster. Poll interval, window, and the healthy streak are monkey-patched to
sub-second / tiny values to keep the suite fast.
"""

from __future__ import annotations

import inspect
import json
from unittest.mock import AsyncMock

import pytest
from watchdog import agent as watchdog_agent_mod
from watchdog.agent import (
    _coerce_rollout_status,
    _parse_pod_counts,
    capture_health_snapshot,
    is_workload_healthy,
    run_watchdog,
)
from watchdog.models import (
    HealthSnapshot,
    HealthSnapshotUnavailable,
    WatchdogDeps,
    WatchdogResult,
)


def _healthy_workload_snapshot(**overrides) -> HealthSnapshot:
    fields = {
        "workload_found": True,
        "generation": 4,
        "observed_generation": 4,
        "spec_replicas": 3,
        "ready_replicas": 3,
        "updated_replicas": 3,
        "available_replicas": 3,
        "available_condition": True,
        "progressing_ok": True,
        "progress_deadline_exceeded": False,
        "ready_pods": 3,
        "total_pods": 3,
        "flux_ready": True,
        "flux_revision": None,
        "captured_at": "2026-06-01T10:00:00Z",
    }
    fields.update(overrides)
    return HealthSnapshot(**fields)


def _rollout_json(**overrides) -> dict:
    status = {
        "kind": "Deployment",
        "namespace": "default",
        "name": "web",
        "found": True,
        "generation": 4,
        "observedGeneration": 4,
        "specReplicas": 3,
        "replicas": 3,
        "updatedReplicas": 3,
        "readyReplicas": 3,
        "availableReplicas": 3,
        "conditions": [
            {
                "type": "Available",
                "status": "True",
                "reason": "MinimumReplicasAvailable",
            },
            {
                "type": "Progressing",
                "status": "True",
                "reason": "NewReplicaSetAvailable",
            },
        ],
    }
    status.update(overrides)
    return status


def test_is_workload_healthy_true_for_converged_deployment() -> None:
    assert is_workload_healthy(_healthy_workload_snapshot(), None) is True


def test_is_workload_healthy_false_when_generation_not_observed() -> None:
    snap = _healthy_workload_snapshot(observed_generation=3)
    assert is_workload_healthy(snap, None) is False


def test_is_workload_healthy_false_on_replica_inequality() -> None:
    snap = _healthy_workload_snapshot(ready_replicas=2)
    assert is_workload_healthy(snap, None) is False


def test_is_workload_healthy_false_when_available_condition_false() -> None:
    snap = _healthy_workload_snapshot(available_condition=False)
    assert is_workload_healthy(snap, None) is False


def test_is_workload_healthy_fast_fails_on_progress_deadline() -> None:
    snap = _healthy_workload_snapshot(progress_deadline_exceeded=True)
    assert is_workload_healthy(snap, None) is False


def test_is_workload_healthy_statefulset_without_conditions() -> None:
    snap = _healthy_workload_snapshot(available_condition=None, progressing_ok=None)
    assert is_workload_healthy(snap, None) is True


def test_is_workload_healthy_false_when_workload_not_found() -> None:
    snap = _healthy_workload_snapshot(workload_found=False)
    assert is_workload_healthy(snap, None) is False


def test_is_workload_healthy_false_on_revision_mismatch() -> None:
    snap = _healthy_workload_snapshot(
        flux_revision="chore/eval-cluster-baseline@sha1:deadbeefcafe"
    )
    assert is_workload_healthy(snap, "abc123") is False


def test_is_workload_healthy_true_on_revision_prefix_match() -> None:
    snap = _healthy_workload_snapshot(
        flux_revision="chore/eval-cluster-baseline@sha1:abc1234567890"
    )
    assert is_workload_healthy(snap, "abc123") is True


def test_is_workload_healthy_false_when_flux_not_ready() -> None:
    snap = _healthy_workload_snapshot(flux_ready=False)
    assert is_workload_healthy(snap, None) is False


def test_is_workload_healthy_nonworkload_namespace_liveness() -> None:
    snap = HealthSnapshot(
        ready_pods=2,
        total_pods=2,
        flux_ready=True,
        captured_at="2026-06-01T10:00:00Z",
    )
    assert is_workload_healthy(snap, None) is True


def test_is_workload_healthy_nonworkload_fallback_unhealthy() -> None:
    snap = HealthSnapshot(
        ready_pods=1,
        total_pods=2,
        flux_ready=True,
        captured_at="2026-06-01T10:00:00Z",
    )
    assert is_workload_healthy(snap, None) is False


def test_parse_pod_counts_running_partial_not_ready() -> None:
    ready, total = _parse_pod_counts(
        {"content": "pod/a Running 0/1\npod/b Running 1/1"}
    )
    assert total == 2
    assert ready == 1


def test_parse_pod_counts_full_fraction_ready() -> None:
    ready, total = _parse_pod_counts(
        {"content": "pod/a Running 2/2\npod/b Running 2/2"}
    )
    assert total == 2
    assert ready == 2


def test_parse_pod_counts_raises_on_unrecognised_shape() -> None:
    with pytest.raises(HealthSnapshotUnavailable):
        _parse_pod_counts({"content": 42})


async def test_capture_health_snapshot_reads_rollout_for_workload() -> None:
    kubectl = AsyncMock()

    async def _call(name, args):
        if name == "rollout_status":
            return _rollout_json()
        return {"content": "pod/a Running 1/1\npod/b Running 1/1\npod/c Running 1/1"}

    kubectl.direct_call_tool = AsyncMock(side_effect=_call)
    flux = AsyncMock()
    flux.direct_call_tool = AsyncMock(
        return_value={"content": "Ready: True\nLastAppliedRevision: main@sha1:abc123"}
    )
    deps = WatchdogDeps(
        kubectl_mcp=kubectl,
        flux_mcp=flux,
        target_kind="Deployment",
        target_name="web",
    )

    snap = await capture_health_snapshot(deps)

    assert snap.workload_found is True
    assert snap.observed_generation == 4
    assert snap.ready_replicas == 3
    assert snap.available_condition is True
    assert snap.progressing_ok is True
    assert snap.progress_deadline_exceeded is False
    assert snap.ready_pods == 3
    assert snap.flux_ready is True
    assert snap.flux_revision == "main@sha1:abc123"


def test_coerce_rollout_status_resolves_every_transport_shape() -> None:
    parsed = _rollout_json()
    assert _coerce_rollout_status(parsed) == parsed
    assert _coerce_rollout_status(json.dumps(parsed)) == parsed
    for key in ("content", "text", "result"):
        assert _coerce_rollout_status({key: json.dumps(parsed)}) == parsed


def test_coerce_rollout_status_indeterminate_on_unresolvable() -> None:
    for bad in ({"content": "Deployment: web\nDesired: 1"}, "not json", {"foo": "bar"}):
        with pytest.raises(HealthSnapshotUnavailable):
            _coerce_rollout_status(bad)


async def test_capture_health_snapshot_nonworkload_skips_rollout() -> None:
    kubectl = AsyncMock()
    kubectl.direct_call_tool = AsyncMock(return_value={"content": "pod/a Running 1/1"})
    flux = AsyncMock()
    flux.direct_call_tool = AsyncMock(return_value={"content": "Ready: True"})
    deps = WatchdogDeps(kubectl_mcp=kubectl, flux_mcp=flux, namespace="payments")

    snap = await capture_health_snapshot(deps)

    kubectl.direct_call_tool.assert_awaited_once_with(
        "get_pods", {"namespace": "payments"}
    )
    assert snap.workload_found is False
    assert snap.ready_pods == 1


async def test_capture_health_snapshot_flux_error_leaves_unknown() -> None:
    kubectl = AsyncMock()
    kubectl.direct_call_tool = AsyncMock(return_value={"content": "pod/a Running 1/1"})
    flux = AsyncMock()
    flux.direct_call_tool = AsyncMock(side_effect=RuntimeError("mcp blip"))
    deps = WatchdogDeps(kubectl_mcp=kubectl, flux_mcp=flux)

    snap = await capture_health_snapshot(deps)

    assert snap.flux_ready is None
    assert snap.flux_revision is None


def test_watchdog_deps_defaults() -> None:
    deps = WatchdogDeps(kubectl_mcp=AsyncMock(), flux_mcp=AsyncMock())
    assert deps.namespace == "default"
    assert deps.flux_kustomization_name == "cluster-apps"
    assert deps.flux_kustomization_namespace == "flux-system"
    assert deps.target_kind is None


async def test_run_watchdog_healthy_after_streak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(watchdog_agent_mod, "POLL_INTERVAL_S", 0.01)
    monkeypatch.setattr(watchdog_agent_mod, "WINDOW_S", 5.0)
    monkeypatch.setattr(watchdog_agent_mod, "HEALTHY_STREAK_K", 3)

    unhealthy = _rollout_json(readyReplicas=1, availableReplicas=1)
    healthy = _rollout_json()

    sequence = [unhealthy, healthy, healthy, healthy]
    calls = {"i": 0}

    async def _call(name, args):
        if name == "rollout_status":
            payload = sequence[min(calls["i"], len(sequence) - 1)]
            calls["i"] += 1
            return payload
        return {"content": "pod/a Running 1/1\npod/b Running 1/1\npod/c Running 1/1"}

    kubectl = AsyncMock()
    kubectl.direct_call_tool = AsyncMock(side_effect=_call)
    flux = AsyncMock()
    flux.direct_call_tool = AsyncMock(return_value={"content": "Ready: True"})
    deps = WatchdogDeps(
        kubectl_mcp=kubectl,
        flux_mcp=flux,
        target_kind="Deployment",
        target_name="web",
    )

    result = await run_watchdog(deps)

    assert isinstance(result, WatchdogResult)
    assert result.degraded is False
    assert result.reason == "healthy"


async def test_run_watchdog_degraded_at_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(watchdog_agent_mod, "POLL_INTERVAL_S", 0.01)
    monkeypatch.setattr(watchdog_agent_mod, "WINDOW_S", 0.2)
    monkeypatch.setattr(watchdog_agent_mod, "HEALTHY_STREAK_K", 3)

    kubectl = AsyncMock()

    async def _call(name, args):
        if name == "rollout_status":
            return _rollout_json(readyReplicas=0)
        return {"content": "pod/a Running 0/1"}

    kubectl.direct_call_tool = AsyncMock(side_effect=_call)
    flux = AsyncMock()
    flux.direct_call_tool = AsyncMock(return_value={"content": "Ready: True"})
    deps = WatchdogDeps(
        kubectl_mcp=kubectl,
        flux_mcp=flux,
        target_kind="Deployment",
        target_name="web",
    )

    result = await run_watchdog(deps)

    assert result.degraded is True
    assert result.reason == "deadline_reached"
    assert result.snapshot is not None


async def test_run_watchdog_fast_fails_on_progress_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(watchdog_agent_mod, "POLL_INTERVAL_S", 0.01)
    monkeypatch.setattr(watchdog_agent_mod, "WINDOW_S", 5.0)
    monkeypatch.setattr(watchdog_agent_mod, "HEALTHY_STREAK_K", 3)

    rollout = _rollout_json(
        conditions=[
            {
                "type": "Available",
                "status": "True",
                "reason": "MinimumReplicasAvailable",
            },
            {
                "type": "Progressing",
                "status": "False",
                "reason": "ProgressDeadlineExceeded",
            },
        ]
    )
    kubectl = AsyncMock()

    async def _call(name, args):
        if name == "rollout_status":
            return rollout
        return {"content": "pod/a Running 0/1"}

    kubectl.direct_call_tool = AsyncMock(side_effect=_call)
    flux = AsyncMock()
    flux.direct_call_tool = AsyncMock(return_value={"content": "Ready: True"})
    deps = WatchdogDeps(
        kubectl_mcp=kubectl,
        flux_mcp=flux,
        target_kind="Deployment",
        target_name="web",
    )

    result = await run_watchdog(deps)

    assert result.degraded is True
    assert result.reason == "progress_deadline_exceeded"


async def test_run_watchdog_skips_indeterminate_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(watchdog_agent_mod, "POLL_INTERVAL_S", 0.01)
    monkeypatch.setattr(watchdog_agent_mod, "WINDOW_S", 0.2)
    monkeypatch.setattr(watchdog_agent_mod, "HEALTHY_STREAK_K", 3)

    kubectl = AsyncMock()
    kubectl.direct_call_tool = AsyncMock(return_value={"content": 42})
    flux = AsyncMock()
    flux.direct_call_tool = AsyncMock(return_value={"content": "Ready: True"})
    deps = WatchdogDeps(kubectl_mcp=kubectl, flux_mcp=flux)

    result = await run_watchdog(deps)

    assert result.degraded is True
    assert result.reason == "deadline_reached"


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
