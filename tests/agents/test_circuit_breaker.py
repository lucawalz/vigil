"""Circuit breaker + iteration limit failure-mode tests.

Two layers of coverage:
  1. Unit tests for _CircuitBreaker (pure state machine).
  2. Integration tests for run_orchestration ABORT paths
     (UsageLimitExceeded, UnexpectedModelBehavior, CircuitBreakerTripped) --
     all produce a valid RunRecord with outcome="abort" written to the audit log.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.exceptions import (
    ModelRetry,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")

from common.constants import CIRCUIT_BREAKER_THRESHOLD
from common.toolset_guards import CircuitBreakerToolset
from orchestrator import agent as orch_mod
from orchestrator.agent import _CircuitBreaker, run_orchestration
from orchestrator.models import CircuitBreakerTripped, FaultEvent
from watchdog.models import HealthSnapshot


def _baseline_snapshot() -> HealthSnapshot:
    return HealthSnapshot(
        ready_pods=3,
        total_pods=3,
        endpoints_healthy=True,
        captured_at="2026-04-18T10:00:00Z",
    )


def test_circuit_breaker_does_not_trip_before_three_errors() -> None:
    cb = _CircuitBreaker()
    cb.error()
    cb.error()
    assert cb.consecutive == 2


def test_circuit_breaker_trips_on_third_consecutive_error() -> None:
    cb = _CircuitBreaker()
    cb.error()
    cb.error()
    with pytest.raises(CircuitBreakerTripped):
        cb.error()


def test_circuit_breaker_success_resets_counter() -> None:
    cb = _CircuitBreaker()
    cb.error()
    cb.error()
    cb.success()
    cb.error()
    cb.error()
    assert cb.consecutive == 2


def _make_toolset(
    breaker: _CircuitBreaker, wrapped: AsyncMock
) -> CircuitBreakerToolset:
    return CircuitBreakerToolset(wrapped=wrapped, breaker=breaker)


async def test_toolset_calls_success_on_successful_tool_call() -> None:
    cb = _CircuitBreaker()
    cb.error()
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(return_value={"content": "ok"})
    toolset = _make_toolset(cb, wrapped)

    result = await toolset.call_tool("get_pods", {}, None, None)

    assert result == {"content": "ok"}
    assert cb.consecutive == 0


async def test_toolset_recoverable_hint_does_not_count_and_reraises() -> None:
    cb = _CircuitBreaker()
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(
        side_effect=ModelRetry("path not found, call resolve_manifest_path")
    )
    toolset = _make_toolset(cb, wrapped)

    with pytest.raises(ModelRetry):
        await toolset.call_tool("read_file", {}, None, None)
    assert cb.consecutive == 0


async def test_toolset_counts_hard_error_and_reraises() -> None:
    cb = _CircuitBreaker()
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(side_effect=ConnectionError("transport down"))
    toolset = _make_toolset(cb, wrapped)

    with pytest.raises(ConnectionError):
        await toolset.call_tool("get_pods", {}, None, None)
    assert cb.consecutive == 1


async def test_toolset_trips_after_threshold_consecutive_hard_errors() -> None:
    cb = _CircuitBreaker()
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(side_effect=RuntimeError("MCP crashed"))
    toolset = _make_toolset(cb, wrapped)

    for _ in range(CIRCUIT_BREAKER_THRESHOLD - 1):
        with pytest.raises(RuntimeError):
            await toolset.call_tool("get_pods", {}, None, None)

    with pytest.raises(CircuitBreakerTripped):
        await toolset.call_tool("get_pods", {}, None, None)


async def test_toolset_success_between_hard_errors_resets_count() -> None:
    cb = _CircuitBreaker()
    failing = AsyncMock(side_effect=RuntimeError("MCP crashed"))
    ok = AsyncMock(return_value={"content": "ok"})
    wrapped = AsyncMock()
    toolset = _make_toolset(cb, wrapped)

    wrapped.call_tool = failing
    for _ in range(CIRCUIT_BREAKER_THRESHOLD - 1):
        with pytest.raises(RuntimeError):
            await toolset.call_tool("get_pods", {}, None, None)

    wrapped.call_tool = ok
    await toolset.call_tool("get_pods", {}, None, None)
    assert cb.consecutive == 0

    wrapped.call_tool = failing
    for _ in range(CIRCUIT_BREAKER_THRESHOLD - 1):
        with pytest.raises(RuntimeError):
            await toolset.call_tool("get_pods", {}, None, None)
    assert cb.consecutive == CIRCUIT_BREAKER_THRESHOLD - 1


async def test_toolset_diagnosis_search_loop_never_trips_breaker() -> None:
    cb = _CircuitBreaker()
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(
        side_effect=ModelRetry("path not found, call resolve_manifest_path")
    )
    toolset = _make_toolset(cb, wrapped)

    for _ in range(CIRCUIT_BREAKER_THRESHOLD):
        with pytest.raises(ModelRetry):
            await toolset.call_tool("read_file", {}, None, None)
    assert cb.consecutive == 0

    wrapped.call_tool = AsyncMock(side_effect=ConnectionError("transport down"))
    with pytest.raises(ConnectionError):
        await toolset.call_tool("get_pods", {}, None, None)
    assert cb.consecutive == 1


def _mock_diagnosis_context() -> AsyncMock:
    from diagnosis.context import DiagnosisContext

    ctx = DiagnosisContext(
        source_branch="main",
        manifest_path="apps/vigil-app.yaml",
        live_yaml="live: yaml",
        declared_yaml="declared: yaml",
        diff="",
    )
    return AsyncMock(return_value=ctx)


async def test_run_orchestration_abort_on_usage_limit_exceeded(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(orch_mod, "build_diagnosis_context", _mock_diagnosis_context())
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(side_effect=UsageLimitExceeded("request_limit (20) exceeded")),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "abort"
    assert record.success_rate is False
    assert record.MTTR_s is None
    written = (tmp_path / "runs" / f"{record.run_id}.json").read_text()
    assert json.loads(written)["outcome"] == "abort"


async def test_run_orchestration_abort_on_diagnosis_budget_records_real_metrics(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from diagnosis.models import DiagnosisRequestBudgetExceeded
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.usage import RunUsage

    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_baseline_snapshot()),
    )
    monkeypatch.setattr(orch_mod, "build_diagnosis_context", _mock_diagnosis_context())

    usage = RunUsage(input_tokens=1234, output_tokens=567)
    messages = [
        ModelResponse(parts=[ToolCallPart(tool_name="get_pods", args={})]),
        ModelResponse(parts=[ToolCallPart(tool_name="get_events", args={})]),
    ]
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(side_effect=DiagnosisRequestBudgetExceeded(usage, messages)),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "abort"
    assert record.success_rate is False
    assert record.total_tool_calls == 2
    assert record.total_input_tokens == 1234
    assert record.total_output_tokens == 567
    assert record.iteration_count >= 1
    written = json.loads((tmp_path / "runs" / f"{record.run_id}.json").read_text())
    assert written["setup_error"].startswith("diagnosis_request_limit_")


async def test_run_orchestration_abort_on_unexpected_model_behavior(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_baseline_snapshot()),
    )
    monkeypatch.setattr(orch_mod, "build_diagnosis_context", _mock_diagnosis_context())
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(
            side_effect=UnexpectedModelBehavior("model returned malformed output")
        ),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "abort"
    assert record.success_rate is False


async def test_run_orchestration_abort_on_circuit_breaker_tripped(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_baseline_snapshot()),
    )
    monkeypatch.setattr(orch_mod, "build_diagnosis_context", _mock_diagnosis_context())
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(side_effect=CircuitBreakerTripped("3 consecutive MCP errors")),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "abort"


async def test_run_orchestration_aborts_when_wired_breaker_trips(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_baseline_snapshot()),
    )
    monkeypatch.setattr(orch_mod, "build_diagnosis_context", _mock_diagnosis_context())

    failing_tool = AsyncMock(side_effect=ConnectionError("MCP transport down"))

    async def _drive_breaker_until_trip(
        *_args: object, breaker=None, **_kwargs: object
    ):
        wrapped = AsyncMock()
        wrapped.call_tool = failing_tool
        toolset = CircuitBreakerToolset(wrapped=wrapped, breaker=breaker)
        while True:
            try:
                await toolset.call_tool("get_pods", {}, None, None)
            except ConnectionError:
                continue

    monkeypatch.setattr(
        orch_mod, "run_diagnosis", AsyncMock(side_effect=_drive_breaker_until_trip)
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "abort"
    assert record.setup_error == "circuit_breaker_3_consecutive_errors"
    assert failing_tool.await_count == CIRCUIT_BREAKER_THRESHOLD
